"""
Recalcula o alcance por linhagem nos resultados já gravados, sem reexecutar.

A flag `is_refutation` alterna a cada refutação, então a contestação de uma
correção voltava a ser contada como exposição ao boato. A profundidade se
reconstrói da auditoria de mensagens: quem refuta soma um, quem repassa herda.

Grava `runs_corrigido.csv` e `paired_effects_corrigido.csv` em cada pasta, com
o alcance estrito (profundidade 0), o ambíguo (2 em diante) e o limite
superior. A coluna `reach_legacy_pct` reproduz a contagem antiga e serve de
conferência: divergir de `final_reach_pct` indica reconstrução malfeita.

    python scripts/recompute_lineage.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def depth_by_content(events: list[dict]) -> dict[tuple[str, bool], int]:
    """Profundidade por (texto, flag de canal). Separar pela flag impede que um
    mesmo texto em níveis diferentes colapse; empate entre ramos fica com a
    menor profundidade, que favorece a contagem antiga."""
    ordered = sorted(events, key=lambda e: (e["tick"], e["event"] == "received"))
    depths: dict[tuple[str, bool], int] = {}
    for _ in range(2):
        for event in ordered:
            base = depths.get((event.get("parent_content"), event["parent_is_refutation"]), 0)
            refuted = event["is_refutation"] != event["parent_is_refutation"]
            depth = base + 1 if refuted else base
            key = (event["content"], event["is_refutation"])
            previous = depths.get(key)
            depths[key] = depth if previous is None else min(previous, depth)
    return depths


def exposures(payload: dict) -> dict[int, set[int]] | None:
    events = payload.get("message_audit")
    if not events:
        return None
    depths = depth_by_content(events)
    seen: dict[int, set[int]] = {}
    for event in events:
        if event["event"] == "received":
            key = (event["content"], event["is_refutation"])
            seen.setdefault(event["node_id"], set()).add(depths.get(key, 0))
    seed = payload.get("initial_state", {}).get("injection_node")
    if seed is not None:
        seen.setdefault(seed, set()).add(0)
    return seen


def recompute(payload: dict, removed: set[int]) -> dict:
    seen = exposures(payload)
    if seen is None:
        return {}
    n_agents = payload["summary"]["n_agents"]
    rumor = {node for node, depths in seen.items() if 0 in depths}
    correction = {node for node, depths in seen.items() if 1 in depths}
    ambiguous = {node for node, depths in seen.items() if any(d >= 2 for d in depths)}
    legacy = {node for node, depths in seen.items() if any(d % 2 == 0 for d in depths)}
    active = max(1, n_agents - len(removed))
    pct = lambda nodes, total=n_agents: round(len(nodes) / total * 100, 2)
    return {
        "reach_strict_pct": pct(rumor),
        "reach_ambiguous_pct": pct(ambiguous),
        "reach_upper_pct": pct(rumor | ambiguous),
        "correction_strict_pct": pct(correction),
        "reach_strict_pct_active": pct(rumor - removed, active),
        "reach_legacy_pct": pct(legacy),
    }


def removed_nodes(row: dict) -> set[int]:
    if not row.get("n_removed") or float(row["n_removed"]) == 0:
        return set()
    return {int(node) for node in row.get("intervention_nodes", "").split(",") if node.strip()}


def id_column(row: dict) -> str:
    """Campanhas antigas gravam `case_id`; as novas, `id`."""
    for name in ("id", "case_id"):
        if name in row:
            return name
    raise SystemExit("runs.csv sem coluna de identificador (`id` ou `case_id`).")


def process(folder: Path) -> dict:
    rows = list(csv.DictReader((folder / "runs.csv").open(encoding="utf-8")))
    identifier = id_column(rows[0])
    recomputed, mismatched, unaudited = [], [], []
    for row in rows:
        path = folder / "results" / f"{row[identifier]}.json"
        extra = {}
        if path.exists():
            extra = recompute(json.loads(path.read_text(encoding="utf-8")), removed_nodes(row))
        if not extra:
            unaudited.append(row[identifier])
        elif abs(extra["reach_legacy_pct"] - float(row["final_reach_pct"])) > 0.01:
            mismatched.append((row[identifier], row["final_reach_pct"], extra["reach_legacy_pct"]))
        recomputed.append({**row, **extra})

    fields = list(rows[0].keys()) + [c for c in recomputed[0] if c not in rows[0]]
    with (folder / "runs_corrigido.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(recomputed)

    strict = {line[identifier]: line.get("reach_strict_pct") for line in recomputed}
    source = folder / "paired_effects.csv"
    written = 0
    pairs = list(csv.DictReader(source.open(encoding="utf-8"))) if source.exists() else []
    # O pareamento antigo não gravava o controle de cada caso; sem ele não há
    # contraste a recalcular.
    if pairs and "reference_id" in pairs[0]:
        for pair in pairs:
            treated, control = strict.get(pair[identifier]), strict.get(pair["reference_id"])
            pair["reach_difference_pp_strict"] = (round(treated - control, 2)
                                                  if None not in (treated, control) else "")
        with (folder / "paired_effects_corrigido.csv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=list(pairs[0].keys()))
            writer.writeheader()
            writer.writerows(pairs)
        written = len(pairs)
    return {"runs": len(recomputed), "pairs": written,
            "unaudited": unaudited, "mismatched": mismatched}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha ou de um shard")
    args = parser.parse_args()
    folders = ([args.campaign] if (args.campaign / "runs.csv").exists()
               else sorted(p.parent for p in args.campaign.glob("*/runs.csv")))
    if not folders:
        raise SystemExit(f"Nenhum runs.csv encontrado em {args.campaign}")
    for folder in folders:
        report = process(folder)
        print(f"{folder.name}: {report['runs']} runs, {report['pairs']} pares, "
              f"{len(report['unaudited'])} sem auditoria, "
              f"{len(report['mismatched'])} divergentes")
        for run_id, stored, rebuilt in report["mismatched"][:5]:
            print(f"    divergência em {run_id}: gravado {stored}, reconstruído {rebuilt}")


if __name__ == "__main__":
    main()
