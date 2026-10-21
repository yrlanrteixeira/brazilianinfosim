"""Distância entre textos publicados; não classifica veracidade ou distorção factual."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from simulation.persistence import atomic_json, load_campaigns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaigns", type=Path, nargs="+", help="Uma pasta ou as fatias (--shard) da mesma campanha")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(2)
    encoder = SentenceTransformer(str(args.model_path), device="cpu", local_files_only=True)
    events, inputs = [], []
    _, attempts, _ = load_campaigns(args.campaigns)
    for campaign, record in attempts:
        if record["status"] != "success":
            continue
        raw = (campaign / "results" / f"{record['id']}.json").read_bytes()
        inputs.append({"id": record["id"], "sha256": sha256(raw).hexdigest()})
        for event in json.loads(raw)["message_audit"]:
            if event["event"] != "sent":
                continue
            content = event["content"].removeprefix("[REFUTAÇÃO]").strip()
            parent = (event["parent_content"] or "").removeprefix("[REFUTAÇÃO]").strip()
            if parent and content != parent:
                events.append({"case_id": record["id"], "node_id": event["node_id"], "tick": event["tick"],
                               "content": content, "parent": parent, "original": event["original_content"]})
    texts = sorted({event[key] for event in events for key in ("content", "parent", "original")})
    vectors = dict(zip(texts, encoder.encode(texts, normalize_embeddings=True))) if texts else {}
    for event in events:
        event["distance_parent"] = float(1 - np.clip(np.dot(vectors[event["content"]], vectors[event["parent"]]), -1, 1))
        event["distance_original"] = float(1 - np.clip(np.dot(vectors[event["content"]], vectors[event["original"]]), -1, 1))
    report = {"embedding_model_snapshot": args.model_path.name, "published_changes": len(events),
              "source_results": inputs, "events": events,
              "mean_distance_parent": float(np.mean([e["distance_parent"] for e in events])) if events else None,
              "interpretation": "Distância de cosseno; não mede veracidade. Prefixo de instrumentação removido. Inclui contestações e reformulações."}
    atomic_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("published_changes", "mean_distance_parent", "embedding_model_snapshot")}))


if __name__ == "__main__":
    main()
