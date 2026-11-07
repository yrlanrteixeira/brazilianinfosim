"""
Produz as tabelas do artigo a partir dos `runs_corrigido.csv` do recálculo.

Os intervalos vêm de bootstrap agrupado pela seed estrutural: execuções que
compartilham a seed compartilham o grafo e a população inicial, então não são
independentes e a reamostragem sorteia seeds inteiras.

Grava em `tabelas/` uma linha por medida, com média, mediana, intervalo de 95% e
o número de seeds que sustenta cada linha.

    python scripts/analisar_corrigido.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from statistics import median

RESAMPLES = 10000
CLUSTER = "seed"

ALCANCES = [
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
        soma, n = totals.get(row[cluster], (0.0, 0))
        totals[row[cluster]] = (soma + value(row), n + 1)
    return list(totals.values())


def clustered_ci(totals: list[tuple[float, int]], seed: int = 0,
                 resamples: int = RESAMPLES) -> tuple[float, float]:
    if len(totals) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    draws = []
    size = len(totals)
    for _ in range(resamples):
        soma = contagem = 0.0
        for _ in range(size):
            parcela, n = totals[rng.randrange(size)]
            soma += parcela
            contagem += n
        draws.append(soma / contagem if contagem else 0.0)
    draws.sort()
    return (round(draws[int(0.025 * resamples)], 2),
            round(draws[int(0.975 * resamples) - 1], 2))


def summarize(rows: list[dict], value, label: str) -> dict:
    if not rows:
        return {"medida": label, "n": 0, "seeds": 0, "media": "", "mediana": "",
                "ic95_baixo": "", "ic95_alto": ""}
    valores = [value(row) for row in rows]
    totals = cluster_totals(rows, value)
    baixo, alto = clustered_ci(totals)
    return {
        "medida": label,
        "n": len(rows),
        "seeds": len(totals),
        "media": round(sum(valores) / len(valores), 2),
        "mediana": round(median(valores), 2),
        "ic95_baixo": baixo,
        "ic95_alto": alto,
    }


def pct(column: str):
    return lambda row: float(row[column])


def artefato(row: dict) -> float:
    """O tamanho do defeito: quanto a contagem antiga somava além do boato."""
    return float(row["reach_legacy_pct"]) - float(row["reach_strict_pct"])


def so_emissor(row: dict) -> float:
    """Uma exposição em n agentes é o emissor sozinho, e nada mais circulou."""
    return 1.0 if float(row["reach_strict_pct"]) <= 100.0 / float(row["n_agents"]) + 1e-9 else 0.0


def conferir_total(rows: list[dict], esperado: int) -> None:
    """Cópia parcial de campanha produz tabela com cara de completa. Quem sabe o
    total declara, e a análise para antes de gerar número errado."""
    if esperado and len(rows) != esperado:
        raise SystemExit(f"Esperava {esperado} execuções e carreguei {len(rows)}. "
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


def tabela_alcances(rows: list[dict]) -> list[dict]:
    """O escopo vai na tabela: sem controle identificado, a linha descreve a
    campanha inteira, e isso não pode ficar implícito."""
    base = controls(rows)
    escopo = "controles" if base else "todas as execucoes"
    return [{**summarize(base or rows, pct(column), label), "escopo": escopo}
            for column, label in ALCANCES]


def tabela_artefato(rows: list[dict]) -> list[dict]:
    return [
        summarize(rows, artefato, "Diferença pareada, contagem antiga menos estrito (p.p.)"),
        summarize(rows, so_emissor, "Proporção de execuções em que o boato não passou do emissor"),
    ]


def tabela_por_estimulo(rows: list[dict]) -> list[dict]:
    lines = []
    for stimulus in sorted({row["stimulus_id"] for row in rows}):
        grupo = [row for row in rows if row["stimulus_id"] == stimulus]
        for column, label in (("reach_strict_pct", "estrito"), ("reach_legacy_pct", "antigo")):
            linha = summarize(grupo, pct(column), f"{stimulus}: alcance {label}")
            lines.append(linha)
        lines.append(summarize(grupo, so_emissor, f"{stimulus}: só o emissor"))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha ou de um shard")
    parser.add_argument("--esperado", type=int, default=0,
                        help="total de execuções da campanha; para a análise se não bater")
    args = parser.parse_args()

    rows = load(args.campaign)
    if not rows:
        raise SystemExit(f"Nenhum runs_corrigido.csv com alcance em {args.campaign}. "
                         "Rode recompute_lineage.py antes.")
    conferir_total(rows, args.esperado)

    saida = args.campaign / "tabelas"
    saida.mkdir(exist_ok=True)
    for name, lines in (("alcances.csv", tabela_alcances(rows)),
                        ("artefato.csv", tabela_artefato(rows)),
                        ("por_estimulo.csv", tabela_por_estimulo(rows))):
        print(f"{write(saida, name, lines)}")

    print(f"\n{len(rows)} execuções, {len(controls(rows))} controles, "
          f"{len({row[CLUSTER] for row in rows})} seeds estruturais")
    for linha in tabela_artefato(rows) + tabela_alcances(rows):
        print(f"  {linha['medida']}: media {linha['media']}, mediana {linha['mediana']}, "
              f"IC95 [{linha['ic95_baixo']}, {linha['ic95_alto']}]")


if __name__ == "__main__":
    main()
