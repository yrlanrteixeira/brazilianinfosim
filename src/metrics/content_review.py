"""Medição por conteúdo, independente da ação e da linhagem operacional."""

from hashlib import sha256
import json
from pathlib import Path

from simulation.persistence import atomic_json


STANCES = ("supports", "rejects", "mixed", "unrelated")
UNRESOLVED = ("pending", "ambiguous")


def content_key(original: str, content: str) -> str:
    pair = json.dumps([original, content], ensure_ascii=False)
    return sha256(pair.encode("utf-8")).hexdigest()


def update_review_template(path: Path, inventory: dict) -> None:
    """Acrescenta textos novos sem substituir anotações já editadas."""
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not path.exists() or inventory.keys() - existing.keys():
        atomic_json(path, {**inventory, **existing})


def review_exposure(payload: dict, annotations: dict) -> dict:
    """Conta agentes únicos; limites refletem classificação ausente, não incerteza amostral."""
    events = payload.get("message_audit")
    if not events or not any(event["event"] == "received" for event in events):
        raise ValueError("Resultado sem auditoria de recebimentos; alcance por conteúdo indisponível.")
    n_agents = payload["manifest"]["settings"]["n_agents"]
    inventory = {}
    for event in events:
        original, content = event["original_content"], event["content"]
        key = content_key(original, content)
        annotation = annotations.get(key, {})
        for field, expected in (("original_content", original), ("content", content)):
            if field in annotation and annotation[field] != expected:
                raise ValueError("Texto da anotação difere do par identificado pelo hash.")
        stance = annotation.get("stance", "pending")
        if stance not in STANCES + UNRESOLVED:
            raise ValueError(f"Classificação desconhecida: {stance}")
        if stance != "pending" and not all(
            isinstance(annotation.get(field), str) and annotation[field].strip()
            for field in ("reviewer", "rationale")
        ):
            raise ValueError("Revisão exige autoria e justificativa.")
        inventory[key] = {
            "original_content": original, "content": content,
            "literal_original": content == original, "stance": stance,
            "reviewer": annotation.get("reviewer", ""),
            "rationale": annotation.get("rationale", ""),
        }

    exposure = {stance: set() for stance in STANCES + UNRESOLVED}
    literal = set()
    received_keys = set()
    for event in events:
        if event["event"] != "received":
            continue
        key = content_key(event["original_content"], event["content"])
        received_keys.add(key)
        item = inventory[key]
        exposure[item["stance"]].add(event["node_id"])
        if item["literal_original"]:
            literal.add(event["node_id"])
    unresolved = exposure["pending"] | exposure["ambiguous"]
    complete = not unresolved

    def pct(nodes):
        return 100 * len(nodes) / n_agents

    return {
        "n_agents_initial": n_agents, "classification_complete": complete,
        "original_text_reach_pct": pct(literal),
        "stance_reach_pct": {
            stance: pct(exposure[stance]) if complete else None for stance in STANCES
        },
        "stance_reach_bounds_pct": {
            stance: {"lower": pct(exposure[stance]), "upper": pct(exposure[stance] | unresolved)}
            for stance in STANCES
        },
        "unresolved_reach_pct": pct(unresolved),
        "received_texts": len(received_keys),
        "pending_received_texts": sum(inventory[key]["stance"] == "pending" for key in received_keys),
        "factual_accuracy": "not_assessed",
        "inventory": inventory,
    }


def paired_content_effects(records: list[dict], reports: dict) -> list[dict]:
    successful = [record for record in records if record["status"] == "success"]
    controls = {record["block"]: record for record in successful
                if record["summary"]["intervention"] == "none"}
    by_id = {record["id"]: record for record in successful}
    pairs = []
    for record in successful:
        control = (by_id.get(record["reference_id"]) if "reference_id" in record
                   else controls.get(record["block"]))
        if control is None or control["id"] == record["id"]:
            continue
        treated_review, control_review = reports.get(record["id"]), reports.get(control["id"])
        complete = bool(treated_review and control_review
                        and treated_review["classification_complete"]
                        and control_review["classification_complete"])
        pairs.append({
            "case_id": record["id"], "control_id": control["id"], "block": record["block"],
            "classification_complete": complete,
            "supports_difference_pp": (
                treated_review["stance_reach_pct"]["supports"]
                - control_review["stance_reach_pct"]["supports"] if complete else None
            ),
        })
    return pairs
