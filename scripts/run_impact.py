"""Campanha de intervenções com orçamento de tempo, auditoria e retomada.

python scripts/run_impact.py --hours 8 --output data/outputs/tcc2/impacto
python scripts/run_impact.py --output data/outputs/tcc2/impacto --resume
python scripts/run_impact.py --dry-run
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

from dotenv import load_dotenv
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm.client import BackendUnavailable, ComputeBudgetExceeded, InvalidLLMResponse
from metrics.analysis import summarize_result
from network.topology import Topology, network_stats
from simulation.engine import InfoSimModel, SimulationConfig
from simulation.messages import SUBJECTS
from simulation.persistence import archive_source, atomic_json, manifest, save_result


def design(n_seeds=20, repeats=2, n_agents=50, ticks=30, pilot=False):
    """Controle único por bloco; tratamentos pareados em quatro momentos."""
    configurations = [(topology, subject, seed)
                      for seed in range(n_seeds)
                      for topology in Topology for subject in SUBJECTS]
    random.Random(90823).shuffle(configurations)
    blocks = [(*configuration, repetition)
              for configuration in configurations for repetition in range(repeats)]
    if pilot:
        blocks = [(Topology.SCALE_FREE, next(iter(SUBJECTS)), 0, 0)]
    cases = []
    for index, (topology, subject, seed, repetition) in enumerate(blocks):
        base = dict(n_agents=n_agents, max_ticks=ticks, topology=topology,
                    seed=30000 + seed, network_seed=10000 + seed,
                    profile_seed=20000 + seed, activation_seed=40000 + seed,
                    llm_seed=50000 + repetition, inject_at="random",
                    initial_message=SUBJECTS[subject], llm_provider="ollama",
                    llm_model="llama3.1:8b", cache_mode="off", temperature=0.3)
        block = f"b{index:04d}"
        arms = [(None, 0)]
        times = [0] if pilot else [0, 1, 3, 10]
        for tick in times:
            treatments = [(name, tick) for name in
                          ("factcheckers_hub", "factcheckers_peripheral", "remove_hubs")]
            random.Random(index * 31 + tick).shuffle(treatments)
            arms.extend(treatments)
        for intervention, tick in arms:
            cfg = SimulationConfig(**base, intervention=intervention, intervention_tick=tick)
            key = sha256(json.dumps(asdict(cfg), sort_keys=True).encode()).hexdigest()[:20]
            cases.append({"id": key, "block": block, "subject": subject,
                          "replicate": repetition, "config": cfg})
    # Cada bloco cobre todos os momentos; as réplicas de LLM vêm em seguida.
    return cases


def local_model_metadata(model_name="llama3.1:8b"):
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    with urlopen(f"{base}/api/tags", timeout=10) as response:
        models = json.load(response)["models"]
    model = next((m for m in models if m["name"] == model_name), None)
    if model is None:
        raise RuntimeError(f"{model_name} não está instalado no Ollama configurado.")
    with urlopen(f"{base}/api/version", timeout=10) as response:
        server = json.load(response)
    return {"model": model, "server": server, "base_url": base}


def export_analysis(directory, records, planned, status):
    """Contrastes descritivos; execuções inválidas nunca entram como alcance zero."""
    successful = [r for r in records if r["status"] == "success"]
    rows = [{"case_id": r["id"], "block": r["block"], "subject": r["subject"],
             "replicate": r["replicate"], "elapsed_seconds": r["elapsed_seconds"],
             **r["summary"]} for r in successful]
    pd.DataFrame(rows).to_csv(directory / "runs.csv", index=False)
    controls = {r["block"]: r for r in successful if r["summary"]["intervention"] == "none"}
    pairs = []
    for row in successful:
        summary = row["summary"]
        control = controls.get(row["block"])
        if summary["intervention"] == "none" or control is None:
            continue
        pairs.append({"case_id": row["id"], "block": row["block"],
                      "subject": row["subject"], "topology": summary["topology"],
                      "seed": summary["seed"], "replicate": row["replicate"],
                      "intervention": summary["intervention"],
                      "intervention_tick": summary["intervention_tick"],
                      "intervention_applied": summary["intervention_applied"],
                      "control_reach_pct": control["summary"]["final_reach_pct"],
                      "treated_reach_pct": summary["final_reach_pct"],
                      "difference_pp": summary["final_reach_pct"] - control["summary"]["final_reach_pct"]})
    pd.DataFrame(pairs, columns=["case_id", "block", "subject", "topology", "seed", "replicate",
                                "intervention", "intervention_tick", "intervention_applied",
                                "control_reach_pct", "treated_reach_pct", "difference_pp"]).to_csv(
        directory / "paired_effects.csv", index=False)
    atomic_json(directory / "status.json", {
        "status": status, "updated_at": datetime.now(timezone.utc).isoformat(),
        "planned": planned, "attempted": len(records), "successful": len(successful),
        "failed": sum(r["status"] == "failed" for r in records),
        "interrupted": sum(r["status"] == "interrupted" for r in records),
        "paired_comparisons": len(pairs),
        "api_calls": sum(r.get("llm_stats", {}).get("api_calls", 0) for r in records),
        "elapsed_seconds_completed_attempts": sum(r["elapsed_seconds"] for r in records),
        "interpretation": "Contrastes descritivos. Conferir pareamento, aplicação e tamanho amostral antes de inferir eficácia.",
    })


def run(cases, directory, hours, resume=False, metadata=None, exporter=None,
        session_budget=False, retry_incomplete=False):
    exporter = exporter or export_analysis
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "campaign.json"
    settings = {"cases": [{**c, "config": asdict(c["config"])} for c in cases],
                "llm_provider": cases[0]["config"].llm_provider if cases else None,
                "llm_model": cases[0]["config"].llm_model if cases else None}
    identity = manifest(settings)
    if manifest_path.exists():
        if not resume:
            raise ValueError("Campanha já existe. Use --resume ou outra pasta.")
        campaign = json.loads(manifest_path.read_text(encoding="utf-8"))
        if campaign["identity"] != identity:
            raise ValueError("Código ou desenho mudou; não é permitido misturar campanhas.")
        if metadata is not None and campaign["model_metadata"] != metadata:
            raise ValueError("Modelo ou servidor mudou; abra outra campanha.")
        if campaign.get("session_budget", False) != session_budget:
            raise ValueError("Regra de orçamento mudou; abra outra campanha.")
    else:
        started = time.time()
        campaign = {"identity": identity, "started_epoch": started,
                    "deadline_epoch": started + hours * 3600,
                    "model_metadata": metadata, "hours": hours, "session_budget": session_budget}
        archive_source(directory, identity["source_sha256"])
        atomic_json(manifest_path, campaign)
    if session_budget:
        session_started = time.time()
        atomic_json(directory / "budget_sessions" / f"{uuid4().hex}.json", {
            "started_epoch": session_started, "hours": hours,
            "deadline_epoch": session_started + hours * 3600, "retry_incomplete": retry_incomplete,
        })
        deadline = time.monotonic() + max(0, hours * 3600)
    else:
        deadline = time.monotonic() + max(0, campaign["deadline_epoch"] - time.time())
    attempts_dir = directory / "attempts"
    attempts_dir.mkdir(exist_ok=True)
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(attempts_dir.glob("*.json"))]
    attempted = {r["id"] for r in records if r["status"] == "success" or not retry_incomplete}
    status = "running"
    exporter(directory, records, len(cases), status)
    failures = 0
    for case in cases:
        if case["id"] in attempted:
            continue
        if time.monotonic() >= deadline:
            status = "budget_exhausted"
            break
        start = time.monotonic()
        model = None
        previous = next((r for r in records if r["id"] == case["id"]), None)
        attempt_number = previous.get("attempt_number", 1) + 1 if previous else 1
        if previous:
            archive = directory / "attempt_history" / case["id"] / f"{attempt_number - 1:04d}.json"
            if archive.exists() and json.loads(archive.read_text(encoding="utf-8")) != previous:
                raise ValueError("Histórico de tentativa diverge; não será sobrescrito.")
            if not archive.exists():
                atomic_json(archive, previous)
        record = {k: v for k, v in case.items() if k != "config"}
        record["attempt_number"] = attempt_number
        record["config"] = asdict(case["config"])
        record["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            model = InfoSimModel(case["config"])
            structure = network_stats(model.G)
            result = model.run(deadline=deadline)
            save_result(result, directory / "results", case["id"])
            record.update(status="success", summary=summarize_result(result, with_mutation=False),
                          network=structure, llm_stats=result.llm_stats)
            failures = 0
        except (BackendUnavailable, InvalidLLMResponse, ComputeBudgetExceeded) as error:
            expired = time.monotonic() >= deadline or isinstance(error, ComputeBudgetExceeded)
            record.update(status="interrupted" if expired else "failed",
                          error=type(error).__name__, detail=str(error),
                          decision_audit=getattr(getattr(model, "llm", None), "audit_log", []),
                          message_audit=getattr(model, "message_audit", []),
                          llm_stats=getattr(getattr(model, "llm", None), "stats", {}))
            failures += 1
            if expired:
                status = "budget_exhausted"
            elif failures >= 3:
                status = "paused_after_three_failures"
        record["elapsed_seconds"] = time.monotonic() - start
        atomic_json(attempts_dir / f"{case['id']}.json", record)
        records = [r for r in records if r["id"] != case["id"]]
        records.append(record)
        exporter(directory, records, len(cases), status)
        print(f"{len(records)}/{len(cases)} {record['status']} {case['subject']} "
              f"{case['config'].intervention or 'control'} t={case['config'].intervention_tick} "
              f"{record['elapsed_seconds']:.1f}s", flush=True)
        if status != "running":
            break
    else:
        status = "finished_with_failures" if any(r["status"] != "success" for r in records) else "completed"
    exporter(directory, records, len(cases), status)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/outputs/tcc2/impacto"))
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--seed-count", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--ticks", type=int, default=30)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.hours <= 0 or args.seed_count < 1 or args.repeats < 1:
        parser.error("Orçamento, sementes e repetições devem ser positivos.")
    load_dotenv()
    cases = design(args.seed_count, args.repeats, args.agents, args.ticks, args.pilot)
    print(f"{len(cases)} casos planejados; teto {args.hours:g} horas; pasta {args.output}", flush=True)
    if args.dry_run:
        return
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    run(cases, args.output, args.hours, args.resume, local_model_metadata())


if __name__ == "__main__":
    main()
