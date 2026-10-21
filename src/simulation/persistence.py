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
from zipfile import ZipFile, ZIP_DEFLATED


def campaign_directory(name: str) -> Path:
    """Uma pasta por invocação para preservar campanhas anteriores."""
    return Path("data/outputs/tcc2") / f"{name}_{uuid4().hex[:12]}"


def source_files() -> list:
    """Quebras de linha normalizadas: o mesmo commit tem o mesmo hash no Windows e no Linux."""
    root = Path(__file__).resolve().parents[2]
    files = sorted([*root.glob("src/**/*.py"), *root.glob("scripts/**/*.py"), root / "requirements.txt"])
    return [(path.relative_to(root).as_posix(), path.read_bytes().replace(b"\r\n", b"\n")) for path in files]


def source_digest(contents: list) -> str:
    digest = sha256()
    for name, raw in contents:
        digest.update(name.encode())
        digest.update(raw)
    return digest.hexdigest()


def manifest(settings: dict) -> dict:
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
    return {"schema_version": 3, "source_sha256": source_digest(source_files()),
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


def archive_source(directory: Path, expected_sha256: str) -> None:
    """Preserva os bytes do código medido, inclusive alterações locais."""
    contents = source_files()
    if source_digest(contents) != expected_sha256:
        raise ValueError("Código mudou durante a criação da campanha.")
    with ZipFile(directory / "source_snapshot.zip", "x", compression=ZIP_DEFLATED) as archive:
        for name, raw in contents:
            archive.writestr(name, raw)


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


def load_campaigns(directories):
    """Junta fatias de uma campanha; recusa código, modelo, desenho ou casos divergentes."""
    sources, attempts, plan, corpora = [], [], [], []
    for directory in directories:
        campaign = json.loads((directory / "campaign.json").read_text(encoding="utf-8"))
        corpus_path = directory / "corpus.json"
        corpus = json.loads(corpus_path.read_text(encoding="utf-8")) if corpus_path.exists() else {}
        metadata = campaign.get("model_metadata") or {}
        sources.append({"path": str(directory), "shard": corpus.get("shard"),
                        "source_sha256": campaign["identity"]["source_sha256"],
                        "model_digest": (metadata.get("model") or {}).get("digest"),
                        "server": metadata.get("server"), "python": campaign["identity"]["python"],
                        "planned": len(campaign["identity"]["settings"]["cases"])})
        corpora.append({key: value for key, value in corpus.items() if key != "shard"})
        plan += campaign["identity"]["settings"]["cases"]
        attempts += [(directory, json.loads(path.read_text(encoding="utf-8")))
                     for path in sorted((directory / "attempts").glob("*.json"))]
    first = sources[0]
    for source, corpus in zip(sources, corpora):
        if (source["source_sha256"], source["model_digest"]) != (first["source_sha256"], first["model_digest"]):
            raise ValueError(f"{source['path']} usa outro código ou modelo; não junte essas campanhas.")
        if corpus != corpora[0]:
            raise ValueError(f"{source['path']} tem outro desenho ou corpus; não junte essas campanhas.")
    if len(sources) > 1:
        shards = [tuple(source["shard"] or ()) for source in sources]
        if not all(shards) or len({count for _, count in shards}) != 1 or len(set(shards)) != len(shards):
            raise ValueError("Só fatias distintas da mesma divisão (--shard I/N) podem ser juntadas.")
    ids = [case["id"] for case in plan]
    if len(ids) != len(set(ids)):
        raise ValueError("Casos repetidos entre as campanhas.")
    return sources, attempts, plan
