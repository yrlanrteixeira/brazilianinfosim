"""
run_mutation.py
Campanha do índice de mutação semântica (QP3).

Pergunta: a mensagem se distorce ao longo da cascata, e isso varia por assunto?
Varia 4 temas x N sementes com topologia scale-free e ponto de injeção (hub)
fixos, para isolar o assunto como único fator.

Roda sem cache: um hit devolveria o mesmo `content`, e mutações idênticas
mediriam distorção zero. As mutações cruas são persistidas antes do cálculo de
embedding, para que o índice possa ser refeito sem re-executar o LLM.

Saídas em data/outputs/:
  <prefix>_raw.csv        uma linha por mensagem mutada
  <prefix>_runs.csv       resumo por run
  <prefix>_by_hop.csv     índice agregado por hop e assunto
  fig_<prefix>.png        painel de mutação por hop

Campanha longa roda por partes (`--subjects economia --prefix mut_economia`) e
depois consolida com `--from-raw "data/outputs/mut_*_raw.csv"`.
"""
import argparse
import glob
import json
import sys
import unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
from simulation.engine import SimulationConfig, InfoSimModel
from simulation.messages import SUBJECTS
from network.topology import Topology
from llm.client import BackendUnavailable, InvalidLLMResponse
from simulation.persistence import atomic_json, manifest
from metrics.analysis import (
    summarize_result, mutation_index, mutation_by_hop, plot_mutation_by_hop,
)

OUT_DIR = Path("data/outputs/tcc2")
DEFAULT_SEEDS = [42, 123, 999, 7, 2024, 55, 2026, 314, 1, 88]


def strip_accents(text: str) -> str:
    """Normaliza para o filtro de assunto aceitar 'saude' e 'saúde'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def filter_subjects(subjects: dict, patterns: str) -> dict:
    targets = [strip_accents(f.strip()) for f in patterns.split(",") if f.strip()]
    return {k: v for k, v in subjects.items()
            if any(a in strip_accents(k) for a in targets)}


def parse_args():
    p = argparse.ArgumentParser(description="Campanha de mutação semântica (QP3)")
    p.add_argument("--n-agents", type=int, default=50)
    p.add_argument("--seeds", type=str, default=None,
                   help="lista separada por vírgula (default: 10 sementes do TCC I)")
    p.add_argument("--subjects", type=str, default=None,
                   help="filtra assuntos por substring, separados por vírgula")
    p.add_argument("--prefix", type=str, default="mutation",
                   help="prefixo dos CSVs de saída")
    p.add_argument("--temperature", type=float, default=1.0,
                   help="temperatura do modelo (fixar antes da campanha)")
    p.add_argument("--from-raw", type=str, default=None,
                   help="agrega CSVs crus já existentes (glob) sem rodar o LLM")
    p.add_argument("--resume", action="store_true",
                   help="pula os pares (assunto, semente) já gravados")
    return p.parse_args()


def load_raw(pattern: str) -> list[dict]:
    """Junta os CSVs crus de campanhas rodadas por partes."""
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f"Nenhum arquivo casou com {pattern!r}")
    dfs = [pd.read_csv(a) for a in files]
    print(f"Agregando {len(files)} arquivo(s): "
          f"{', '.join(Path(a).name for a in files)}", flush=True)
    return pd.concat(dfs, ignore_index=True).to_dict("records")


def run_campaign(subjects: dict, seeds: list[int], n_agents: int,
                 temperature: float, prefix: str,
                 resume: bool = False) -> tuple[list, list]:
    """
    Executa a campanha, gravando a cada run concluído.

    Campanha longa cai: gravar só no fim perde tudo o que já rodou.
    """
    if Path(prefix).name != prefix or not prefix:
        raise ValueError("prefix deve ser um nome simples de arquivo")
    metadata = manifest({"subjects": subjects, "n_agents": n_agents,
                         "temperature": temperature, "cache_mode": "off",
                         "topology": Topology.SCALE_FREE.value, "max_ticks": 100,
                         "inject_at": "hub", "intervention": None})
    rows, raw = [], []
    checkpoint = OUT_DIR / f"{prefix}_checkpoint.json"
    existing_csv = any((OUT_DIR / f"{prefix}_{kind}.csv").exists() for kind in ("runs", "raw"))
    if resume and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved["manifest"] != metadata:
            raise ValueError("Configuração, modelo ou código mudou. Use outro prefixo de campanha.")
        rows, raw = saved["rows"], saved["raw"]
        _persist(rows, raw, prefix, metadata)  # repara exportações interrompidas
    elif resume and existing_csv:
        raise ValueError("CSV sem manifesto verificável. Use outro prefixo de campanha.")
    elif not resume and (checkpoint.exists() or existing_csv):
        raise ValueError("Campanha já existe. Use --resume ou outro prefixo.")
    done = {(r["subject"], r["seed"]) for r in rows}

    total = len(subjects) * len(seeds)
    i = 0
    for subject, msg in subjects.items():
        for seed in seeds:
            i += 1
            if (subject, seed) in done:
                print(f"[{i}/{total}] {subject:20s} seed={seed} -> já feito",
                      flush=True)
                continue

            cfg = SimulationConfig(
                n_agents=n_agents, topology=Topology.SCALE_FREE, max_ticks=100,
                seed=seed, initial_message=msg, intervention=None,
                inject_at="hub", enable_cache=False,
                temperature=temperature,
            )
            try:
                result = InfoSimModel(cfg).run()
            except (BackendUnavailable, InvalidLLMResponse) as error:
                atomic_json(OUT_DIR / f"{prefix}_failure.json", {
                    "manifest": metadata, "subject": subject, "seed": seed,
                    "error": type(error).__name__, "detail": str(error),
                    "raw_response": getattr(error, "raw_response", None),
                })
                raise

            # O embedder roda depois, em lote.
            s = summarize_result(result, with_mutation=False)
            s.update(subject=subject, seed=seed, cache_enabled=False)

            # Run curto faz uma ou duas chamadas, então a sequência dentro do
            # cliente nunca dispara: a checagem tem que ser por run.
            chamadas = s.get("api_calls", 0)
            falhas = s.get("backend_errors", 0)
            if falhas and falhas == chamadas:
                raise BackendUnavailable(
                    f"{subject} seed={seed}: todas as {falhas} chamada(s) ao "
                    f"provider falharam. Sem isto o run entraria no CSV como "
                    f"concluído."
                )

            rows.append(s)
            raw.extend(dict(m, subject=subject, seed=seed)
                       for m in result.mutations)

            _persist(rows, raw, prefix, metadata)
            done.add((subject, seed))

            print(f"[{i}/{total}] {subject:20s} seed={seed} -> "
                  f"alcance {s['final_reach_pct']:.0f}%, "
                  f"{len(result.mutations)} mutações, "
                  f"{s['refusals_agents']} recusas", flush=True)
    return rows, raw


def _persist(rows: list[dict], raw: list[dict], prefix: str, metadata: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT_DIR / f"{prefix}_checkpoint.json",
                {"manifest": metadata, "rows": rows, "raw": raw})
    pd.DataFrame(rows).to_csv(OUT_DIR / f"{prefix}_runs.csv", index=False)
    pd.DataFrame(raw, columns=["hop", "content", "parent_content", "original_content",
                              "sender_id", "subject", "seed"]).to_csv(
        OUT_DIR / f"{prefix}_raw.csv", index=False)


def main():
    args = parse_args()
    if args.from_raw:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        aggregate(load_raw(args.from_raw), args.prefix)
        return

    seeds = ([int(x) for x in args.seeds.split(",")] if args.seeds
             else DEFAULT_SEEDS)
    subjects = SUBJECTS
    if args.subjects:
        subjects = filter_subjects(SUBJECTS, args.subjects)
        if not subjects:
            sys.exit(f"Nenhum assunto casou com {args.subjects!r}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        rows, raw = run_campaign(subjects, seeds, args.n_agents,
                                 args.temperature, args.prefix,
                                 resume=args.resume)
    except (BackendUnavailable, InvalidLLMResponse, ValueError) as e:
        runs_csv = OUT_DIR / f"{args.prefix}_runs.csv"
        onde = (f"Os runs concluídos antes da falha estão em {runs_csv}."
                if runs_csv.exists() else "Nenhum run foi gravado.")
        sys.exit(f"\nCampanha abortada: {e}\n{onde}\n"
                 f"Religue o provider e retome com --resume.")

    print(f"\n{OUT_DIR / f'{args.prefix}_runs.csv'} ({len(rows)} runs)",
          flush=True)
    if not raw:
        print("Nenhuma mutação coletada: nada a agregar.", flush=True)
        return
    print(f"{OUT_DIR / f'{args.prefix}_raw.csv'} ({len(raw)} mutações)",
          flush=True)

    aggregate(raw, args.prefix)


def aggregate(raw: list[dict], prefix: str) -> None:
    """Calcula o índice e os gráficos. Única etapa que usa embeddings."""
    by_subject = []
    by_hop = []
    for subject in dict.fromkeys(m["subject"] for m in raw):
        mutations = [m for m in raw if m["subject"] == subject]
        if not mutations:
            continue
        by_subject.append({
            "subject": subject,
            "n_mutations": len(mutations),
            "M": round(mutation_index(mutations), 4),
        })
        df_hop = mutation_by_hop(mutations)
        df_hop["subject"] = subject
        by_hop.append(df_hop)

    df_hop = pd.concat(by_hop, ignore_index=True)
    hop_csv = OUT_DIR / f"{prefix}_by_hop.csv"
    df_hop.to_csv(hop_csv, index=False)
    print(f"{hop_csv} salvo", flush=True)

    print("\n=== Índice de mutação M por assunto ===", flush=True)
    print(pd.DataFrame(by_subject).sort_values("M", ascending=False)
          .to_string(index=False), flush=True)
    print("\n=== Mutação por hop ===", flush=True)
    print(df_hop.round(4).to_string(index=False), flush=True)

    plot_mutation_by_hop(df_hop, save_path=str(OUT_DIR / f"fig_{prefix}.png"))
    print("DONE_MUTATION", flush=True)


if __name__ == "__main__":
    main()
