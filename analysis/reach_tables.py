"""
Produz as tabelas do artigo a partir dos `runs_corrigido.csv` do recálculo.

Os intervalos vêm de bootstrap agrupado pela seed estrutural: execuções que
compartilham a seed compartilham o grafo e a população inicial, então não são
independentes e a reamostragem sorteia seeds inteiras.

Grava em `tabelas/` uma linha por medida, com média, mediana, intervalo de 95% e
o número de seeds que sustenta cada linha. Os cabeçalhos ficam em português
porque alimentam as tabelas do artigo.

    python analysis/reach_tables.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from statistics import median

RESAMPLES = 10000
CLUSTER = "seed"

REACH_COLUMNS = [
    ("reach_legacy_pct", "Alcance pela contagem antiga"),
    ("reach_strict_pct", "Alcance estrito do boato"),
    ("correction_strict_pct", "Alcance da correção"),
    ("reach_ambiguous_pct", "Alcance ambíguo"),
    ("reach_upper_pct", "Limite superior do boato"),
]


def cluster_totals(rows: list[dict], value, cluster: str = CLUSTER) -> list[tuple[float, int]]:
    """Soma e contagem por grupo. Reduz cada reamostragem ao número de grupos."""
    totals: dict[str, tuple[float, int]] = {}
    for row in rows:
        acc, n = totals.get(row[cluster], (0.0, 0))
        totals[row[cluster]] = (acc + value(row), n + 1)
    return list(totals.values())


def clustered_ci(totals: list[tuple[float, int]], seed: int = 0,
                 resamples: int = RESAMPLES, level: float = 0.95) -> tuple[float, float]:
    """Nível acima de 95% serve ao ajuste de multiplicidade. A cauda fica fina:
    em 0,9977 sobram cerca de onze reamostragens de cada lado."""
    if len(totals) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    draws = []
    size = len(totals)
    for _ in range(resamples):
        acc = count = 0.0
        for _ in range(size):
            part, n = totals[rng.randrange(size)]
            acc += part
            count += n
        draws.append(acc / count if count else 0.0)
    draws.sort()
    low = max(0, int((1 - level) / 2 * resamples))
    high = min(resamples - 1, int((1 + level) / 2 * resamples) - 1)
    return (round(draws[low], 2), round(draws[high], 2))


def summarize(rows: list[dict], value, label: str, cluster: str = CLUSTER) -> dict:
    if not rows:
        return {"medida": label, "n": 0, "seeds": 0, "media": "", "mediana": "",
                "ic95_baixo": "", "ic95_alto": ""}
    values = [value(row) for row in rows]
    totals = cluster_totals(rows, value, cluster)
    low, high = clustered_ci(totals)
    return {
        "medida": label,
        "n": len(rows),
        "seeds": len(totals),
        "media": round(sum(values) / len(values), 2),
        "mediana": round(median(values), 2),
        "ic95_baixo": low,
        "ic95_alto": high,
    }


def pct(column: str):
    return lambda row: float(row[column])


def artifact(row: dict) -> float:
    """O tamanho do defeito: quanto a contagem antiga somava além do boato."""
    return float(row["reach_legacy_pct"]) - float(row["reach_strict_pct"])


def emitter_only(row: dict) -> float:
    """Uma exposição em n agentes é o emissor sozinho, e nada mais circulou."""
    return 1.0 if float(row["reach_strict_pct"]) <= 100.0 / float(row["n_agents"]) + 1e-9 else 0.0


def check_total(rows: list[dict], expected: int) -> None:
    """Cópia parcial de campanha produz tabela com cara de completa. Quem sabe o
    total declara, e a análise para antes de gerar número errado."""
    if expected and len(rows) != expected:
        raise SystemExit(f"Esperava {expected} execuções e carreguei {len(rows)}. "
                         "A cópia da campanha está incompleta ou desatualizada.")


def load(campaign: Path) -> list[dict]:
    files = ([campaign / "runs_corrigido.csv"]
             if (campaign / "runs_corrigido.csv").exists()
             else sorted(campaign.glob("*/runs_corrigido.csv")))
    rows = []
    for path in files:
        rows.extend(csv.DictReader(path.open(encoding="utf-8")))
    return [row for row in rows if row.get("reach_strict_pct")]


CONTROL_CONDITIONS = {"control", "controle"}
NO_INTERVENTION = {"", "none"}


def controls(rows: list[dict]) -> list[dict]:
    """Controle é a condição de referência do pareamento. As demais condições
    sem intervenção também gravam `none`, e não são controle."""
    named = [row for row in rows
             if row.get("condition", "").strip().lower() in CONTROL_CONDITIONS]
    if named:
        return named
    return [row for row in rows
            if row.get("intervention", "").strip().lower() in NO_INTERVENTION]


def write(folder: Path, name: str, lines: list[dict]) -> Path:
    path = folder / name
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(lines[0]))
        writer.writeheader()
        writer.writerows(lines)
    return path


def reach_table(rows: list[dict]) -> list[dict]:
    """O escopo vai na tabela: sem controle identificado, a linha descreve a
    campanha inteira, e isso não pode ficar implícito."""
    base = controls(rows)
    scope = "controles" if base else "todas as execucoes"
    return [{**summarize(base or rows, pct(column), label), "escopo": scope}
            for column, label in REACH_COLUMNS]


def artifact_table(rows: list[dict]) -> list[dict]:
    return [
        summarize(rows, artifact, "Diferença pareada, contagem antiga menos estrito (p.p.)"),
        summarize(rows, emitter_only, "Proporção de execuções em que o boato não passou do emissor"),
    ]


def table_by_group(rows: list[dict], key: str, keep=None) -> list[dict]:
    """Uma linha por valor da coluna, nas duas métricas mais a proporção presa
    ao emissor. Serve para estímulo, topologia e fração de céticos."""
    target = [row for row in rows if keep is None or keep(row)]
    lines = []
    for value in sorted({row[key] for row in target}):
        group = [row for row in target if row[key] == value]
        for column, label in (("reach_strict_pct", "estrito"), ("reach_legacy_pct", "marca")):
            lines.append(summarize(group, pct(column), f"{value}: alcance {label}"))
        lines.append(summarize(group, emitter_only, f"{value}: só o emissor"))
    return lines


def table_by_stimulus(rows: list[dict]) -> list[dict]:
    return table_by_group(rows, "stimulus_id")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha ou de um shard")
    parser.add_argument("--expected", type=int, default=0,
                        help="total de execuções da campanha; para a análise se não bater")
    args = parser.parse_args()

    rows = load(args.campaign)
    if not rows:
        raise SystemExit(f"Nenhum runs_corrigido.csv com alcance em {args.campaign}. "
                         "Rode recompute_lineage.py antes.")
    check_total(rows, args.expected)

    out_dir = args.campaign / "tabelas"
    out_dir.mkdir(exist_ok=True)
    tables = [
        ("alcances.csv", reach_table(rows)),
        ("artefato.csv", artifact_table(rows)),
        ("por_estimulo.csv", table_by_stimulus(rows)),
        # Topologia sobre a campanha inteira, não só a família que a varia:
        # toda execução tem uma, e o recorte da família perde a maior parte.
        ("por_topologia.csv", table_by_group(rows, "topology")),
        ("por_ceticos.csv", table_by_group(
            rows, "condition", lambda row: row["family"] == "skeptics")),
    ]
    for name, lines in tables:
        if lines:
            print(f"{write(out_dir, name, lines)}")

    print(f"\n{len(rows)} execuções, {len(controls(rows))} controles, "
          f"{len({row[CLUSTER] for row in rows})} seeds estruturais")
    for line in artifact_table(rows) + reach_table(rows):
        print(f"  {line['medida']}: media {line['media']}, mediana {line['mediana']}, "
              f"IC95 [{line['ic95_baixo']}, {line['ic95_alto']}]")


if __name__ == "__main__":
    main()
