"""
Sorteia a amostra de textos publicados para anotação de postura, estratificada
pela profundidade de refutação.

A profundidade vem da mesma reconstrução de `recompute_lineage`, para que a
anotação e o alcance recalculado falem da mesma linhagem. A unidade é o texto
distinto: cada par (conteúdo, canal) tem uma única profundidade, então um texto
cai em um único estrato.

Grava um CSV com uma linha por texto sorteado, a alegação original contra a qual
ele será julgado, e as colunas que o anotador preenche. A coluna `peso` é a
razão entre o total do estrato e o tamanho sorteado, e é o que permite voltar da
amostra para a população. Os estratos e rótulos ficam em português porque é o
anotador quem os lê.

    python analysis/sample_texts.py data/outputs/tcc2/conclusao --output amostra_anotacao.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from pathlib import Path

from recompute_lineage import depth_by_content, id_column, load_result

STRATA = ("boato", "correcao", "ambiguo")
SIZES = {"boato": 60, "correcao": 60, "ambiguo": 180}

FIELDS = [
    "text_id", "estrato", "refutation_depth", "subject", "run_id", "node_id",
    "tick", "ocorrencias", "textos_no_estrato", "peso", "alegacao", "texto",
    "rotulo", "justificativa", "anotador",
]

LABELS = ("apoia", "rejeita", "misto", "nao_relacionado")


def stratum(depth: int) -> str:
    if depth == 0:
        return "boato"
    if depth == 1:
        return "correcao"
    return "ambiguo"


def text_id(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


def published(payload: dict, run_id: str, subject: str) -> dict[tuple[str, bool], dict]:
    """Um registro por texto distinto publicado na execução."""
    events = payload.get("message_audit")
    if not events:
        return {}
    depths = depth_by_content(events)
    records: dict[tuple[str, bool], dict] = {}
    for event in events:
        if event["event"] != "sent":
            continue
        key = (event["content"], event["is_refutation"])
        depth = depths.get(key, 0)
        record = records.setdefault(key, {
            "text_id": text_id(event["content"]),
            "estrato": stratum(depth),
            "refutation_depth": depth,
            "subject": subject,
            "run_id": run_id,
            "node_id": event["node_id"],
            "tick": event["tick"],
            "ocorrencias": 0,
            "alegacao": event["original_content"],
            "texto": event["content"],
        })
        record["ocorrencias"] += 1
    return records


def merge(pool: dict, found: dict) -> None:
    """Empate de profundidade entre execuções fica com a menor, como no recálculo."""
    for key, record in found.items():
        current = pool.get(key)
        if current is None:
            pool[key] = record
            continue
        current["ocorrencias"] += record["ocorrencias"]
        if record["refutation_depth"] < current["refutation_depth"]:
            current["refutation_depth"] = record["refutation_depth"]
            current["estrato"] = record["estrato"]


def collect(folder: Path) -> dict[tuple[str, bool], dict]:
    rows = list(csv.DictReader((folder / "runs.csv").open(encoding="utf-8")))
    identifier = id_column(rows[0])
    pool: dict[tuple[str, bool], dict] = {}
    for row in rows:
        path = folder / "results" / f"{row[identifier]}.json"
        if not path.exists():
            continue
        payload = load_result(path)
        subject = row.get("subject") or row.get("stimulus_id") or ""
        merge(pool, published(payload, row[identifier], subject))
    return pool


def draw(pool: dict, sizes: dict[str, int], seed: int) -> list[dict]:
    """Ordena por identificador antes de sortear: o sorteio não depende da
    ordem de leitura dos arquivos, só da seed."""
    rng = random.Random(seed)
    sample = []
    for name in STRATA:
        group = sorted((r for r in pool.values() if r["estrato"] == name),
                       key=lambda r: r["text_id"])
        size = min(sizes[name], len(group))
        if not size:
            continue
        for record in rng.sample(group, size):
            sample.append({**record, "textos_no_estrato": len(group),
                           "peso": round(len(group) / size, 4),
                           "rotulo": "", "justificativa": "", "anotador": ""})
    return sample


def parse_sizes(text: str) -> dict[str, int]:
    sizes = dict(SIZES)
    for part in text.split(","):
        name, _, value = part.partition("=")
        name = name.strip()
        if name not in STRATA:
            raise SystemExit(f"Estrato desconhecido: {name}. Use {', '.join(STRATA)}.")
        sizes[name] = int(value)
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha ou de um shard")
    parser.add_argument("--output", type=Path, default=Path("amostra_anotacao.csv"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sizes", default="boato=60,correcao=60,ambiguo=180")
    args = parser.parse_args()

    sizes = parse_sizes(args.sizes)
    folders = ([args.campaign] if (args.campaign / "runs.csv").exists()
               else sorted(p.parent for p in args.campaign.glob("*/runs.csv")))
    if not folders:
        raise SystemExit(f"Nenhum runs.csv encontrado em {args.campaign}")

    pool: dict[tuple[str, bool], dict] = {}
    for folder in folders:
        merge(pool, collect(folder))
    if not pool:
        raise SystemExit("Nenhum texto publicado com auditoria de mensagens.")

    sample = draw(pool, sizes, args.seed)
    with args.output.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sample)

    print(f"{len(pool)} textos distintos, {len(sample)} sorteados em {args.output}")
    for name in STRATA:
        total = sum(1 for r in pool.values() if r["estrato"] == name)
        drawn = sum(1 for r in sample if r["estrato"] == name)
        print(f"    {name}: {drawn} de {total}")
    print(f"Rótulos aceitos na coluna `rotulo`: {', '.join(LABELS)}")


if __name__ == "__main__":
    main()
