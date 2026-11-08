"""
Compara o alcance medido nos agentes LLM com o de referências SIR e SEIR
rodadas no mesmo grafo, com a mesma origem e o mesmo horizonte.

O pareamento é por execução: cada referência recebe a rede e o nó de injeção
daquela execução, de modo que a diferença não vem de estrutura nem de ponto de
partida. As seeds estruturais são divididas em ajuste e avaliação, porque medir
aderência na mesma amostra que escolheu os parâmetros não mede nada.

A estatística é a distância de Kolmogorov-Smirnov entre as distribuições de
alcance, que compara a forma inteira e não só a média.

    python analysis/compare_seir.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import networkx as nx

from recompute_lineage import id_column, load_result
from simulation.baseline import run_epidemic

TRANSMISSION = (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.80)
RECOVERY = (0.10, 0.30, 0.50)


def horizon_by_condition(rows: list[dict]) -> dict[str, int]:
    """O horizonte configurado não é gravado; o maior `ticks_run` da condição o
    revela, porque as execuções que não se extinguem param nele."""
    highest: dict[str, int] = {}
    for row in rows:
        condition = row["condition"]
        highest[condition] = max(highest.get(condition, 1), int(row["ticks_run"]))
    return highest


def split_seeds(seeds: list[str]) -> tuple[set[str], set[str]]:
    """Divide por seed, não por execução. A lista chega com repetição, uma
    entrada por execução; sem o conjunto, a mesma seed cai dos dois lados."""
    ordered = sorted(set(seeds))
    return set(ordered[::2]), set(ordered[1::2])


def ks(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return float("nan")
    points = sorted(set(a) | set(b))
    highest = 0.0
    for x in points:
        fa = sum(1 for v in a if v <= x) / len(a)
        fb = sum(1 for v in b if v <= x) / len(b)
        highest = max(highest, abs(fa - fb))
    return round(highest, 4)


def reference_reach(case: dict, transmission: float, recovery: float,
                    latent: bool) -> float:
    graph = nx.Graph()
    graph.add_nodes_from(range(case["n_agents"]))
    graph.add_edges_from(case["edges"])
    lines = run_epidemic(graph, case["source"], case["horizon"],
                         transmission, recovery, case["seed"], latent=latent)
    return round(lines[-1]["reached"] / case["n_agents"] * 100, 2)


def load(campaign: Path) -> list[dict]:
    folders = ([campaign] if (campaign / "runs_corrigido.csv").exists()
               else sorted(p.parent for p in campaign.glob("*/runs_corrigido.csv")))
    cases = []
    for folder in folders:
        rows = [r for r in csv.DictReader((folder / "runs_corrigido.csv").open(encoding="utf-8"))
                if r.get("reach_strict_pct")]
        if not rows:
            continue
        identifier = id_column(rows[0])
        horizons = horizon_by_condition(rows)
        for row in rows:
            path = folder / "results" / f"{row[identifier]}.json"
            if not path.exists():
                continue
            state = load_result(path).get("initial_state", {})
            if state.get("injection_node") is None or not state.get("edges"):
                continue
            cases.append({
                "id": row[identifier], "seed": int(row["seed"]),
                "n_agents": int(row["n_agents"]),
                "source": state["injection_node"],
                "edges": [tuple(e) for e in state["edges"]],
                "horizon": horizons[row["condition"]],
                "llm": float(row["reach_strict_pct"]),
            })
    return cases


def best_fit(cases: list[dict], latent: bool) -> tuple[float, float, float]:
    target = [c["llm"] for c in cases]
    best = (float("nan"), float("nan"), float("inf"))
    for transmission in TRANSMISSION:
        for recovery in RECOVERY:
            reference = [reference_reach(c, transmission, recovery, latent)
                         for c in cases]
            distance = ks(target, reference)
            if distance < best[2]:
                best = (transmission, recovery, distance)
    return best


def emitter_only(values: list[float], n_agents: int) -> float:
    threshold = 100.0 / n_agents + 1e-9
    return round(sum(1 for v in values if v <= threshold) / len(values), 3)


def evaluate(cases: list[dict], transmission: float, recovery: float,
             latent: bool) -> dict:
    target = [c["llm"] for c in cases]
    reference = [reference_reach(c, transmission, recovery, latent) for c in cases]
    n_agents = cases[0]["n_agents"]
    return {
        "modelo": "SEIR" if latent else "SIR",
        "transmissao": transmission, "recuperacao": recovery,
        "n": len(cases), "ks": ks(target, reference),
        "media_llm": round(sum(target) / len(target), 2),
        "media_referencia": round(sum(reference) / len(reference), 2),
        "so_emissor_llm": emitter_only(target, n_agents),
        "so_emissor_referencia": emitter_only(reference, n_agents),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    cases = load(args.campaign)
    if not cases:
        raise SystemExit(f"Nenhuma execução com grafo gravado em {args.campaign}.")
    fit_seeds, eval_seeds = split_seeds([str(c["seed"]) for c in cases])
    fit = [c for c in cases if str(c["seed"]) in fit_seeds]
    evaluation = [c for c in cases if str(c["seed"]) in eval_seeds]
    print(f"{len(cases)} execuções com grafo; ajuste {len(fit)}, "
          f"avaliação {len(evaluation)}, seeds {len(fit_seeds)}/{len(eval_seeds)}")

    lines = []
    for latent in (False, True):
        transmission, recovery, distance = best_fit(fit, latent)
        print(f"\n{'SEIR' if latent else 'SIR'}: melhor ajuste "
              f"transmissão {transmission}, recuperação {recovery}, KS {distance}")
        line = evaluate(evaluation, transmission, recovery, latent)
        lines.append(line)
        for key, value in line.items():
            print(f"    {key}: {value}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=list(lines[0]))
            writer.writeheader()
            writer.writerows(lines)
        print(f"\n{args.output}")


if __name__ == "__main__":
    main()
