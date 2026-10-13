"""Proveniência e gravação atômica dos resultados experimentais."""

from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import platform
import tempfile
from datetime import datetime, timezone
from uuid import uuid4


def campaign_directory(name: str) -> Path:
    """Uma pasta por invocação para preservar campanhas anteriores."""
    return Path("data/outputs/tcc2") / f"{name}_{uuid4().hex[:12]}"


def manifest(settings: dict) -> dict:
    root = Path(__file__).resolve().parents[2]
    files = sorted([*root.glob("src/**/*.py"), *root.glob("run_*.py"), root / "requirements.txt"])
    digest = sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    provider = settings.get("llm_provider") or os.getenv("LLM_PROVIDER", "ollama")
    model = settings.get("llm_model") or os.getenv(
        "LLM_MODEL", "llama3.1:8b" if provider == "ollama" else "claude-haiku-4-5-20251001"
    )
    packages = {}
    for package in ("mesa", "networkx", "numpy", "pandas", "openai", "anthropic", "sentence-transformers"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    return {"schema_version": 3, "source_sha256": digest.hexdigest(),
            "python": platform.python_version(), "packages": packages,
            "provider": provider, "model": model, "model_digest": None,
            "llm_seed": settings.get("llm_seed"), "settings": settings}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_result(result, directory: Path, label: str) -> None:
    """Salva antes de calcular embeddings ou gráficos; JSON é a fonte canônica."""
    from metrics.analysis import summarize_result

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest(asdict(result.config)),
        "summary": summarize_result(result, with_mutation=False),
        "model_data": json.loads(result.model_data.to_json(orient="records")),
        "agent_data": json.loads(result.agent_data.reset_index().to_json(orient="records")),
        "mutations": result.mutations,
        "initial_state": result.initial_state,
        "decision_audit": result.decision_audit,
        "message_audit": result.message_audit,
        "metric_semantics": {
            "final_reach_pct": "rumor_lineage_exposure",
            "final_correction_reach_pct": "refutation_lineage_exposure",
            "final_believers": "action_derived_state_above_0.5",
            "content_stance": "requires_separate_annotation",
        },
    }
    atomic_json(directory / f"{label}.json", payload)
