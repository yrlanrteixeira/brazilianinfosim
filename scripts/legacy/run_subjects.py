"""
run_subjects.py
Experimento de virulência por ASSUNTO.

Pergunta: qual assunto se dissemina mais, e isso muda com a topologia?
Varia 4 temas de desinformação típicos no Brasil x 3 topologias x N sementes,
mantendo o ponto de injeção (hub) fixo. Mede ignição, alcance e crentes.

Saída: data/outputs/subjects_experiment.csv
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
from simulation.engine import SimulationConfig, InfoSimModel
from network.topology import Topology
from metrics.analysis import summarize_result
from simulation.messages import SUBJECTS
from simulation.persistence import campaign_directory, save_result

TOPOS = [Topology.RANDOM, Topology.SCALE_FREE, Topology.SMALL_WORLD]

SEEDS = [42, 123, 999, 7, 2024, 55, 2026, 314, 1, 88]

def main():
    OUT_DIR = campaign_directory("subjects")

    rows = []
    total = len(SUBJECTS) * len(TOPOS) * len(SEEDS)
    i = 0
    for subject, msg in SUBJECTS.items():
        for topo in TOPOS:
            for seed in SEEDS:
                i += 1
                cfg = SimulationConfig(
                    n_agents=50, topology=topo, max_ticks=100, seed=seed,
                    initial_message=msg, intervention=None, inject_at="hub",
                    cache_mode="off",
                )
                result = InfoSimModel(cfg).run()
                save_result(result, OUT_DIR / "subject_runs", f"{list(SUBJECTS).index(subject)}_{topo.value}_{seed}")
                s = summarize_result(result, with_mutation=False)
                s.update(subject=subject, seed=seed)
                rows.append(s)
                pd.DataFrame(rows).to_csv(OUT_DIR / "subjects_experiment.csv", index=False)
                print(f"[{i}/{total}] {subject:20s} {topo.value:16s} seed={seed} "
                      f"-> {s['final_reach_pct']:.0f}%", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "subjects_experiment.csv", index=False)
    print(f"\nsubjects_experiment.csv salvo ({len(df)} runs)", flush=True)

    df["ign"] = df["final_reach_pct"] > 10
    print("\n=== Ignição por assunto (média entre topologias) ===", flush=True)
    print(df.groupby("subject")["ign"].mean().round(2).sort_values(ascending=False), flush=True)
    print("\n=== Alcance médio por assunto x topologia ===", flush=True)
    print(df.pivot_table(index="subject", columns="topology",
                         values="final_reach_pct", aggfunc="mean").round(1), flush=True)
    print("DONE_SUBJECTS", flush=True)


if __name__ == "__main__":
    main()
