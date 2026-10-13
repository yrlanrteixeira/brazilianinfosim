"""Análise das questões sem tratar agentes ou mensagens como réplicas."""

import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean, median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from metrics.content_review import content_key, review_exposure
from simulation.persistence import atomic_json


def write_csv(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_metrics(payload, annotations):
    review = review_exposure(payload, annotations)
    n = review["n_agents_initial"]
    first = {kind: {} for kind in ("any", "literal", "supports", "rejects")}
    publications = defaultdict(set)
    changed = []
    for event in payload["message_audit"]:
        stance = review["inventory"][content_key(event["original_content"], event["content"])]["stance"]
        if event["event"] == "sent":
            publications["any"].add(event["node_id"])
            publications[stance].add(event["node_id"])
            parent = (event.get("parent_content") or "").removeprefix("[REFUTAÇÃO]").strip()
            content = event["content"].removeprefix("[REFUTAÇÃO]").strip()
            if parent and content != parent:
                changed.append(1 - SequenceMatcher(None, parent, content, autojunk=False).ratio())
            continue
        tick = event["tick"] + (event["sender_id"] is not None)
        kinds = ["any"]
        if event["content"] == event["original_content"]:
            kinds.append("literal")
        if stance in ("supports", "rejects"):
            kinds.append(stance)
        for kind in kinds:
            first[kind].setdefault(event["node_id"], tick)
    summary = payload["summary"]
    row = {"classification_complete": review["classification_complete"],
           "any_reach_pct": 100 * len(first["any"]) / n,
           "literal_reach_pct": review["original_text_reach_pct"],
           "supports_reach_pct": review["stance_reach_pct"]["supports"],
           "supports_lower_pct": review["stance_reach_bounds_pct"]["supports"]["lower"],
           "supports_upper_pct": review["stance_reach_bounds_pct"]["supports"]["upper"],
           "unique_publishers_any": len(publications["any"]),
           "published_changes": len(changed), "lexical_distance_mean": mean(changed) if changed else None,
           "ticks_observed": summary["ticks_run"], "censored": summary["stop_reason"] == "max_ticks",
           "intervention_applied": summary["intervention_applied"]}
    for kind in ("literal", "supports"):
        for threshold in (25, 50, 75):
            times = sorted(first[kind].values())
            eligible = [tick for index, tick in enumerate(times, 1) if index / n * 100 >= threshold]
            row[f"{kind}_T{threshold}"] = (eligible[0] if eligible else None) if (
                kind == "literal" or review["classification_complete"]) else None
    return row, review["inventory"]


def cluster_summary(rows, metric, iterations=2000):
    groups = defaultdict(list)
    for row in rows:
        if row.get(metric) is not None:
            groups[row["seed_index"]].append(row[metric])
    values = [value for group in groups.values() for value in group]
    result = {"pairs": len(values), "independent_seed_clusters": len(groups),
              "mean": mean(values) if values else None, "median": median(values) if values else None,
              "ci95_cluster_bootstrap": None}
    if len(groups) >= 6:
        rng = random.Random(20261013)
        keys = sorted(groups)
        samples = sorted(mean([value for key in rng.choices(keys, k=len(keys)) for value in groups[key]])
                         for _ in range(iterations))
        result["ci95_cluster_bootstrap"] = [samples[int(0.025 * iterations)], samples[int(0.975 * iterations)]]
    return result


def analyze(campaign, output, annotations_path=None):
    annotations_bytes = annotations_path.read_bytes() if annotations_path else None
    annotations = json.loads(annotations_bytes) if annotations_bytes else {}
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((campaign / "attempts").glob("*.json"))]
    good = {r["id"]: r for r in records if r["status"] == "success"}
    rows, inventory, profiles, provenance = {}, {}, Counter(), []
    for key, record in good.items():
        raw = (campaign / "results" / f"{key}.json").read_bytes()
        payload = json.loads(raw)
        metrics, texts = run_metrics(payload, annotations)
        inventory.update(texts)
        rows[key] = {"id": key, **{field: record[field] for field in
                     ("block", "family", "condition", "seed_index", "stimulus_id", "replicate")}, **metrics}
        rows[key]["actual_skeptics"] = sum(p["agent_type"] == "cetico" for p in payload["initial_state"]["profiles"])
        rows[key]["n_agents"] = record["config"]["n_agents"]
        rows[key]["skeptic_fraction_nominal"] = record["config"]["skeptic_fraction"]
        for event in payload["decision_audit"]:
            if "decision" in event:
                profiles[(event.get("agent_type", "unknown"), event["decision"], bool(event.get("refused")))] += 1
        provenance.append({"id": key, "sha256": sha256(raw).hexdigest()})
    pairs = []
    for key, record in good.items():
        reference_id = record["reference_id"]
        if key == reference_id or reference_id not in rows:
            continue
        ref = rows[reference_id]
        row = rows[key]
        pair = {"id": key, "reference_id": reference_id, "family": record["family"],
                "condition": record["condition"], "seed_index": record["seed_index"],
                "reference_topology": good[reference_id]["config"]["topology"],
                "treated_topology": record["config"]["topology"]}
        for metric in ("literal_reach_pct", "supports_reach_pct", "ticks_observed", "published_changes"):
            a, b = row[metric], ref[metric]
            pair[f"delta_{metric}"] = a - b if a is not None and b is not None else None
        pairs.append(pair)
    grouped = defaultdict(list)
    for pair in pairs:
        # A referência de topologia varia entre blocos; não agregar direções opostas.
        contrast = (pair["family"], pair["condition"], pair["reference_topology"] if pair["family"] == "topology" else "shared")
        grouped[contrast].append(pair)
    effects = [{"family": key[0], "condition": key[1], "reference": key[2],
                "support_reach": cluster_summary(group, "delta_supports_reach_pct"),
                "literal_reach": cluster_summary(group, "delta_literal_reach_pct")}
               for key, group in sorted(grouped.items())]
    containment = []
    plan = json.loads((campaign / "campaign.json").read_text(encoding="utf-8"))["identity"]["settings"]["cases"]
    for cutoff in (5, 10, 20):
        for fraction in (0, 0.2, 0.4, 0.6, 0.8, 1):
            selected = [row for row in rows.values() if row["family"] in {"reference", "skeptics"}
                        and row["skeptic_fraction_nominal"] == fraction]
            classified = [r for r in selected if r["supports_reach_pct"] is not None]
            containment.append({"cutoff_pct": cutoff, "fraction": fraction, "runs": len(selected),
                                "classified": len(classified),
                                "planned": sum(c["family"] in {"reference", "skeptics"}
                                               and c["config"]["skeptic_fraction"] == fraction for c in plan),
                                "contained": sum(r["supports_reach_pct"] <= cutoff for r in classified),
                                "proportion": mean(r["supports_reach_pct"] <= cutoff for r in classified) if classified else None,
                                "uncertainty": cluster_summary([
                                    {"seed_index": r["seed_index"], "contained": int(r["supports_reach_pct"] <= cutoff)}
                                    for r in classified], "contained")})
    thresholds = []
    for cutoff in (5, 10, 20):
        grid = [point for point in containment if point["cutoff_pct"] == cutoff]
        adequate = all(point["planned"] > 0 and point["classified"] == point["planned"]
                       and point["uncertainty"]["independent_seed_clusters"] >= 6 for point in grid)
        candidates = [point["fraction"] for index, point in enumerate(grid)
                      if adequate and all(p["proportion"] >= 0.8 for p in grid[index:])]
        thresholds.append({"cutoff_pct": cutoff, "grid_complete": adequate,
                           "estimated_grid_threshold": min(candidates) if candidates else None,
                           "status": "evaluated" if adequate else "insufficient_complete_reviewed_blocks"})
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "content_runs.csv", list(rows.values()))
    write_csv(output / "paired_effects.csv", pairs)
    write_csv(output / "containment.csv", containment)
    write_csv(output / "decisions_by_profile.csv", [{"profile": p, "action": a, "refused": r, "count": count}
                                                     for (p, a, r), count in sorted(profiles.items())])
    template = output / "review_template.json"
    if not template.exists():
        atomic_json(template, inventory)
    result = {"completed_runs": len(good), "attempt_statuses": dict(Counter(r["status"] for r in records)),
              "fully_classified_runs": sum(r["classification_complete"] for r in rows.values()),
              "unique_texts": len(inventory), "effects": effects,
              "containment_thresholds": thresholds,
              "archived_attempts": len(list((campaign / "attempt_history").glob("*/*.json"))),
              "factual_accuracy": "not_assessed", "independent_human_review": "not_assessed",
              "source_results": provenance,
              "analysis_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "annotations_sha256": sha256(annotations_bytes).hexdigest() if annotations_bytes else None,
              "interpretation": "Intervalos exploratórios por semente; sem correção para múltiplos contrastes. Tempo observado não é tempo de extinção quando censurado."}
    atomic_json(output / "analysis.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotations", type=Path)
    args = parser.parse_args()
    result = analyze(args.campaign, args.output, args.annotations)
    print(json.dumps({key: result[key] for key in ("completed_runs", "fully_classified_runs", "unique_texts")}))


if __name__ == "__main__":
    main()
