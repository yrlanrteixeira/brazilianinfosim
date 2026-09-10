"""
run_mutation.py
Campanha do índice de mutação semântica (QP3).

Pergunta: a mensagem se distorce ao longo da cascata, e isso varia por assunto?
Varia 4 temas x N sementes com topologia scale-free e ponto de injeção (hub)
fixos, para isolar o assunto como único fator.

O cache semântico fica DESLIGADO: um hit devolve o mesmo `content` gerado
antes, então mutações repetidas entrariam idênticas no índice e mediriam
distorção zero por artefato de implementação.

As mutações cruas são persistidas antes de qualquer cálculo de embedding, de
modo que o índice e os gráficos possam ser refeitos sem re-executar o LLM.

Saídas em data/outputs/:
  <prefix>_raw.csv        uma linha por mensagem mutada
  <prefix>_runs.csv       resumo por run
  <prefix>_by_hop.csv     índice agregado por hop e assunto
  fig_mutacao.png         painel de mutação por hop
"""
import argparse
import sys
import unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
from simulation.engine import SimulationConfig, InfoSimModel
from simulation.messages import SUBJECTS
from network.topology import Topology
from metrics.analysis import (
    summarize_result, mutation_index, mutation_by_hop, plot_mutation_by_hop,
)

OUT_DIR = Path("data/outputs")
DEFAULT_SEEDS = [42, 123, 999, 7, 2024, 55, 2026, 314, 1, 88]


def sem_acento(texto: str) -> str:
    """Normaliza para o filtro de assunto aceitar 'saude' e 'saúde'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def filtra_subjects(subjects: dict, filtros: str) -> dict:
    alvos = [sem_acento(f.strip()) for f in filtros.split(",") if f.strip()]
    return {k: v for k, v in subjects.items()
            if any(a in sem_acento(k) for a in alvos)}


def parse_args():
    p = argparse.ArgumentParser(description="Campanha de mutação semântica (QP3)")
    p.add_argument("--n-agents", type=int, default=50)
    p.add_argument("--seeds", type=str, default=None,
                   help="lista separada por vírgula (default: 10 sementes do TCC I)")
    p.add_argument("--subjects", type=str, default=None,
                   help="filtra assuntos por substring, separados por vírgula")
    p.add_argument("--prefix", type=str, default="mutation",
                   help="prefixo dos CSVs de saída")
    return p.parse_args()


def run_campaign(subjects: dict, seeds: list[int], n_agents: int) -> tuple[list, list]:
    """Executa a campanha e devolve (resumos por run, mutações cruas)."""
    raw, rows = [], []
    total = len(subjects) * len(seeds)
    i = 0
    for subject, msg in subjects.items():
        for seed in seeds:
            i += 1
            cfg = SimulationConfig(
                n_agents=n_agents, topology=Topology.SCALE_FREE, max_ticks=100,
                seed=seed, initial_message=msg, intervention=None,
                inject_at="hub", enable_cache=False,
            )
            result = InfoSimModel(cfg).run()

            # with_mutation=False: o embedder roda depois, em lote
            s = summarize_result(result, with_mutation=False)
            s.update(subject=subject, seed=seed, cache_enabled=False)
            rows.append(s)

            for m in result.mutations:
                raw.append(dict(m, subject=subject, seed=seed))

            print(f"[{i}/{total}] {subject:20s} seed={seed} -> "
                  f"alcance {s['final_reach_pct']:.0f}%, "
                  f"{len(result.mutations)} mutações, "
                  f"{s['refusals_agents']} recusas", flush=True)
    return rows, raw


def main():
    args = parse_args()
    seeds = ([int(x) for x in args.seeds.split(",")] if args.seeds
             else DEFAULT_SEEDS)
    subjects = SUBJECTS
    if args.subjects:
        subjects = filtra_subjects(SUBJECTS, args.subjects)
        if not subjects:
            sys.exit(f"Nenhum assunto casou com {args.subjects!r}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, raw = run_campaign(subjects, seeds, args.n_agents)

    runs_csv = OUT_DIR / f"{args.prefix}_runs.csv"
    pd.DataFrame(rows).to_csv(runs_csv, index=False)
    print(f"\n{runs_csv} salvo ({len(rows)} runs)", flush=True)

    if not raw:
        print("Nenhuma mutação coletada: nada a agregar.", flush=True)
        return

    raw_csv = OUT_DIR / f"{args.prefix}_raw.csv"
    pd.DataFrame(raw).to_csv(raw_csv, index=False)
    print(f"{raw_csv} salvo ({len(raw)} mutações)", flush=True)

    # ── Agregação (única etapa que usa embeddings) ────────────────────────
    por_assunto = []
    por_hop = []
    for subject in subjects:
        muts = [m for m in raw if m["subject"] == subject]
        if not muts:
            continue
        por_assunto.append({
            "subject": subject,
            "n_mutations": len(muts),
            "M": round(mutation_index(muts), 4),
        })
        df_hop = mutation_by_hop(muts)
        df_hop["subject"] = subject
        por_hop.append(df_hop)

    df_hop = pd.concat(por_hop, ignore_index=True)
    hop_csv = OUT_DIR / f"{args.prefix}_by_hop.csv"
    df_hop.to_csv(hop_csv, index=False)
    print(f"{hop_csv} salvo", flush=True)

    print("\n=== Índice de mutação M por assunto ===", flush=True)
    print(pd.DataFrame(por_assunto).sort_values("M", ascending=False)
          .to_string(index=False), flush=True)
    print("\n=== Mutação por hop ===", flush=True)
    print(df_hop.round(4).to_string(index=False), flush=True)

    plot_mutation_by_hop(df_hop, save_path=str(OUT_DIR / "fig_mutacao.png"))
    print("DONE_MUTATION", flush=True)


if __name__ == "__main__":
    main()
