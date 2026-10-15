"""
run_expanded.py
Experimento expandido: amplia a base de resultados preliminares.

Tres blocos:
  (A) Matriz expandida: 3 topologias x 4 intervencoes x 2 mensagens x N seeds.
  (B) Experimento de ponto de injecao: hub vs influenciador vs aleatorio.
  (C) Caracterizacao estrutural das redes (sem LLM).

Saidas em data/outputs/: expanded_matrix.csv, injection_experiment.csv,
network_structure.csv.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
from simulation.engine import SimulationConfig, InfoSimModel
from network.topology import Topology, build_network, network_stats
from metrics.analysis import summarize_result
from simulation.persistence import campaign_directory, save_result

OUT_DIR = campaign_directory("expanded")

TOPOS = [Topology.RANDOM, Topology.SCALE_FREE, Topology.SMALL_WORLD]
MSG = {
    "saude": ("URGENTE: Médicos escondem que vitamina C em altas doses cura "
              "câncer! Compartilhe antes que a big pharma tire do ar!"),
    "politica": ("Relatório técnico indica que sistema eleitoral precisa "
                 "de auditoria mais detalhada segundo especialistas."),
}
SEEDS = [42, 123, 999, 7, 2024]
INJ_SEEDS = [42, 123, 999, 7, 2024, 55]


def run_one(topo, interv, msg_name, seed, inject_at="hub", block="matrix"):
    cfg = SimulationConfig(
        n_agents=50, topology=topo, max_ticks=100, seed=seed,
        initial_message=MSG[msg_name], intervention=interv,
        inject_at=inject_at,
        intervention_tick=0, enable_cache=False, cache_mode="off",
    )
    result = InfoSimModel(cfg).run()
    save_result(result, OUT_DIR / block,
                f"{topo.value}_{interv or 'none'}_{msg_name}_{seed}_{inject_at}")
    s = summarize_result(result, with_mutation=False)
    s.update(msg=msg_name, seed=seed, inject_at=inject_at)
    return s


def block_a():
    interventions = [None, "factcheckers_hub", "factcheckers_peripheral", "remove_hubs"]
    rows, total = [], len(TOPOS) * len(interventions) * len(MSG) * len(SEEDS)
    i = 0
    for topo in TOPOS:
        for interv in interventions:
            for msg_name in MSG:
                for seed in SEEDS:
                    i += 1
                    s = run_one(topo, interv, msg_name, seed)
                    rows.append(s)
                    pd.DataFrame(rows).to_csv(OUT_DIR / "expanded_matrix.csv", index=False)
                    print(f"[A {i}/{total}] {topo.value} {interv} {msg_name} "
                          f"seed={seed} -> {s['final_reach_pct']:.0f}%", flush=True)
    print(f"[A] expanded_matrix.csv salvo ({len(rows)} runs)", flush=True)


def block_b():
    rows, total = [], len(TOPOS) * 3 * len(INJ_SEEDS)
    i = 0
    for topo in TOPOS:
        for inject in ["hub", "influencer", "random"]:
            for seed in INJ_SEEDS:
                i += 1
                s = run_one(topo, None, "politica", seed, inject_at=inject, block="injection")
                rows.append(s)
                pd.DataFrame(rows).to_csv(OUT_DIR / "injection_experiment.csv", index=False)
                print(f"[B {i}/{total}] {topo.value} inject={inject} "
                      f"seed={seed} -> {s['final_reach_pct']:.0f}%", flush=True)
    print(f"[B] injection_experiment.csv salvo ({len(rows)} runs)", flush=True)


def block_c():
    rows = []
    for topo in TOPOS:
        for seed in SEEDS:
            G = build_network(topology=topo, n_agents=50, seed=seed)
            st = network_stats(G)
            st.update(topology=topo.value, seed=seed)
            rows.append(st)
    df = pd.DataFrame(rows)
    agg = df.groupby("topology").mean(numeric_only=True).round(3)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUT_DIR / "network_structure.csv")
    print("[C] network_structure.csv salvo", flush=True)
    print(agg, flush=True)


if __name__ == "__main__":
    block_c()
    block_a()
    block_b()
    print("EXPANDED DONE", flush=True)
