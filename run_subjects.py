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
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
from simulation.engine import SimulationConfig, InfoSimModel
from network.topology import Topology
from metrics.analysis import summarize_result

TOPOS = [Topology.RANDOM, Topology.SCALE_FREE, Topology.SMALL_WORLD]

# Mensagens realistas (estilo WhatsApp), registro comparável entre temas.
SUBJECTS = {
    "Saúde/vacinas": (
        "URGENTE: a vacina da gripe deste ano está causando arritmia em idosos "
        "e o Ministério da Saúde está escondendo. Repasse para sua família!"
    ),
    "Política/eleições": (
        "ATENÇÃO: documento vazado prova que as urnas eletrônicas foram "
        "adulteradas na última eleição. Compartilhe antes que apaguem!"
    ),
    "Economia/benefícios": (
        "URGENTE: o governo vai liberar um novo auxílio de R$ 1.200 para quem "
        "se cadastrar até sexta neste link. Avise todo mundo!"
    ),
    "Segurança/crime": (
        "ALERTA: uma quadrilha está sequestrando crianças na saída das escolas "
        "usando vans brancas. Já são 5 casos esta semana. Repasse!"
    ),
}
SEEDS = [42, 123, 999, 7, 2024, 55, 2026, 314, 1, 88]

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
            )
            s = summarize_result(InfoSimModel(cfg).run())
            s.update(subject=subject, seed=seed)
            rows.append(s)
            print(f"[{i}/{total}] {subject:20s} {topo.value:16s} seed={seed} "
                  f"-> {s['final_reach_pct']:.0f}%", flush=True)

df = pd.DataFrame(rows)
df.to_csv("data/outputs/subjects_experiment.csv", index=False)
print(f"\nsubjects_experiment.csv salvo ({len(df)} runs)", flush=True)

df["ign"] = df["final_reach_pct"] > 10
print("\n=== Ignição por assunto (média entre topologias) ===", flush=True)
print(df.groupby("subject")["ign"].mean().round(2).sort_values(ascending=False), flush=True)
print("\n=== Alcance médio por assunto x topologia ===", flush=True)
print(df.pivot_table(index="subject", columns="topology",
                     values="final_reach_pct", aggfunc="mean").round(1), flush=True)
print("DONE_SUBJECTS", flush=True)
