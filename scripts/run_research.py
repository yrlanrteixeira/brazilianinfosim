"""Campanha pareada para QP1 a QP4; dados brutos também alimentam QP5."""

import argparse
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

from loguru import logger
from dotenv import load_dotenv
import pandas as pd

from run_impact import local_model_metadata, run
from agents.profiles import AgentType
from network.topology import Topology
from simulation.engine import SimulationConfig
from simulation.persistence import atomic_json
from simulation.research_messages import CORPUS_METADATA, STIMULI


def design(n_seeds=12, repeats=2, n_agents=50, ticks=12,
           model="qwen3:4b-instruct-2507-q4_K_M", pilot=False):
    """Um controle compartilhado por bloco, com todos os contrastes antes do próximo."""
    if min(n_seeds, repeats) < 1 or ticks < 3:
        raise ValueError("Sementes e réplicas positivas; horizonte de pelo menos três rodadas.")
    blocks = [(seed, stimulus) for seed in range(n_seeds) for stimulus in STIMULI]
    random.Random(20261013).shuffle(blocks)
    if pilot:
        blocks, repeats, n_agents, ticks = [(0, STIMULI[1])], 1, 10, 3
    cases = []
    for seed, stimulus in blocks:
        for repetition in range(repeats):
            block = f"s{seed:03d}-{stimulus['id']}-r{repetition}"
            base = SimulationConfig(
                n_agents=n_agents, max_ticks=ticks, topology=list(Topology)[seed % 3],
                network_degree=4, seed=61000 + seed, network_seed=161000 + seed,
                profile_seed=261000 + seed, activation_seed=361000 + seed,
                llm_seed=71000 + repetition, initial_message=stimulus["text"],
                inject_at="random", emitter_type="amplificador", skeptic_fraction=0.2,
                synchronous_updates=True, indifferent_uses_llm=True,
                intervention_tick=0,
                llm_provider="ollama", llm_model=model, cache_mode="off", temperature=0.3,
            )
            arms = [("topology", kind.value, replace(base, topology=kind))
                    for kind in Topology if kind != base.topology]
            arms += [("skeptics", f"fraction_{fraction:g}", replace(base, skeptic_fraction=fraction))
                     for fraction in (0, 0.4, 0.6, 0.8, 1)]
            arms += [("emitter", kind.value, replace(base, emitter_type=kind.value))
                     for kind in AgentType if kind != AgentType.AMPLIFIER]
            arms += [("mutation", "literal_forwarding", replace(base, mutation_enabled=False))]
            arms += [("intervention", f"{kind}_t{tick}", replace(base, intervention=kind, intervention_tick=tick))
                     for tick in (0, 2) for kind in
                     ("factcheckers_hub", "factcheckers_peripheral", "remove_hubs", "limit_forwarding")]
            arms += [("persistence", "double_horizon", replace(base, max_ticks=2 * ticks))]
            random.Random(f"arms:{seed}:{stimulus['id']}:{repetition}").shuffle(arms)
            if pilot:
                arms = [arm for arm in arms if arm[1] in
                        {"literal_forwarding", "limit_forwarding_t0", "fact_checker"}]
            reference = None
            for family, condition, cfg in [("reference", "control", base), *arms]:
                key = sha256(json.dumps({"block": block, "config": asdict(cfg)}, sort_keys=True).encode()).hexdigest()[:20]
                reference = reference or key
                cases.append({"id": key, "block": block, "reference_id": reference,
                              "family": family, "condition": condition, "seed_index": seed,
                              "subject": stimulus["theme"], "stimulus_id": stimulus["id"],
                              "claim": stimulus["claim"], "replicate": repetition, "config": cfg})
    return cases


def export_analysis(directory, records, planned, status):
    successful = {r["id"]: r for r in records if r["status"] == "success"}
    rows, pairs = [], []
    for record in successful.values():
        rows.append({**{key: record[key] for key in
                        ("id", "block", "family", "condition", "seed_index", "stimulus_id", "replicate")},
                     "elapsed_seconds": record["elapsed_seconds"], **record["summary"],
                     **record["network"]})
        reference = successful.get(record["reference_id"])
        if reference is None or record["id"] == reference["id"]:
            continue
        pairs.append({"id": record["id"], "reference_id": reference["id"],
                      "family": record["family"], "condition": record["condition"],
                      "seed_index": record["seed_index"], "stimulus_id": record["stimulus_id"],
                      "replicate": record["replicate"],
                      "lineage_reach_difference_pp": record["summary"]["final_reach_pct"] - reference["summary"]["final_reach_pct"],
                      "intervention_applied": record["summary"]["intervention_applied"]})
    pd.DataFrame(rows).to_csv(directory / "runs.csv", index=False)
    pd.DataFrame(pairs).to_csv(directory / "paired_effects.csv", index=False)
    counts = Counter(r["status"] for r in records)
    campaign = json.loads((directory / "campaign.json").read_text(encoding="utf-8"))
    block_sizes = Counter(case["block"] for case in campaign["identity"]["settings"]["cases"])
    completed = Counter(record["block"] for record in successful.values())
    atomic_json(directory / "status.json", {
        "status": status, "planned": planned, "attempted": len(records), **counts,
        "paired_comparisons": len(pairs),
        "archived_attempts": len(list((directory / "attempt_history").glob("*/*.json"))),
        "complete_blocks": sum(completed[block] == size for block, size in block_sizes.items()),
        "interpretation": "Métricas de linhagem são operacionais. Análise por conteúdo exige revisão separada.",
    })


def shard(value):
    index, count = (int(part) for part in value.split("/"))
    if not 0 <= index < count:
        raise ValueError(value)
    return [index, count]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=1)
    parser.add_argument("--seed-count", type=int, default=12)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-incomplete", action="store_true", help="Retenta falhas/interrupções preservando o histórico")
    parser.add_argument("--shard", type=shard, metavar="I/N",
                        help="Roda só as sementes de cenário com seed_index %% N == I, em pasta própria")
    args = parser.parse_args()
    if args.hours <= 0:
        parser.error("Orçamento de horas deve ser positivo.")
    if args.retry_incomplete and not args.resume:
        parser.error("Use --retry-incomplete somente com --resume.")
    load_dotenv()
    cases = design(args.seed_count, args.repeats, args.agents, args.ticks, args.model, args.pilot)
    if args.shard:
        # Fatia por semente de cenário: cada bloco pareado fica inteiro em uma máquina.
        cases = [case for case in cases if case["seed_index"] % args.shard[1] == args.shard[0]]
        if not cases:
            parser.error("Fatia sem casos.")
    print(json.dumps({"cases": len(cases), "families": Counter(c["family"] for c in cases),
                      "hours": args.hours, "shard": args.shard,
                      "pilot_excluded_from_main": args.pilot}, ensure_ascii=False), flush=True)
    if args.dry_run:
        return
    corpus = {**CORPUS_METADATA, "stimuli": STIMULI, "pilot": args.pilot, "shard": args.shard,
              "design": {"seed_count": args.seed_count, "repeats": args.repeats, "agents": args.agents,
                         "ticks": args.ticks, "model": args.model}}
    corpus_path = args.output / "corpus.json"
    if corpus_path.exists():
        if not args.resume or json.loads(corpus_path.read_text(encoding="utf-8")) != corpus:
            parser.error("Corpus existente: não será sobrescrito ou misturado.")
    elif args.resume:
        parser.error("Corpus ausente na campanha a retomar.")
    else:
        atomic_json(corpus_path, corpus)
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    run(cases, args.output, args.hours, args.resume, local_model_metadata(args.model), exporter=export_analysis,
        session_budget=True, retry_incomplete=args.retry_incomplete)


if __name__ == "__main__":
    main()
