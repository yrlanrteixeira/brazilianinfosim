"""
Contrastes pareados por condição, nas duas métricas de alcance lado a lado.

Cada tratamento é comparado ao controle do seu próprio bloco. A coluna antiga
mede a linhagem operacional e a corrigida mede a profundidade 0; a distância
entre as duas é o que este trabalho mede.

Intervenções em t=2 só ocorrem quando a cascata chega ao tick 2, então a linha
delas descreve um subconjunto selecionado. A coluna `descartados` diz quantos
pares ficaram de fora por intervenção não aplicada.

Grava `tabelas/contrastes.csv` e `tabelas/contrastes.tex`.

    python analysis/contrasts.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import median

from reach_tables import clustered_ci, cluster_totals

CLUSTER = "seed_index"
LEGACY = "lineage_reach_difference_pp"
STRICT = "reach_difference_pp_strict"

FIELDS = ["familia", "condicao", "n", "descartados", "seeds",
          "antigo_media", "antigo_ic95_baixo", "antigo_ic95_alto",
          "estrito_media", "estrito_mediana", "estrito_ic95_baixo", "estrito_ic95_alto"]


def load(campaign: Path) -> list[dict]:
    files = ([campaign / "paired_effects_corrigido.csv"]
             if (campaign / "paired_effects_corrigido.csv").exists()
             else sorted(campaign.glob("*/paired_effects_corrigido.csv")))
    pairs = []
    for path in files:
        pairs.extend(csv.DictReader(path.open(encoding="utf-8")))
    return [p for p in pairs if p.get(STRICT) not in (None, "")]


def applied_only(family: str, group: list[dict]) -> list[dict]:
    """Só a família de intervenção tem tratamento a aplicar. Nas demais a flag é
    falsa por construção, e filtrar por ela esvaziaria o grupo."""
    if family != "intervention":
        return group
    return [p for p in group if p["intervention_applied"] == "True"]


def groups(pairs: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for pair in pairs:
        grouped.setdefault((pair["family"], pair["condition"]), []).append(pair)
    return grouped


def effect(group: list[dict], column: str,
           level: float = 0.95) -> tuple[float, float, float, float]:
    values = [float(p[column]) for p in group]
    low, high = clustered_ci(cluster_totals(group, lambda p: float(p[column]), CLUSTER),
                             level=level)
    return (round(sum(values) / len(values), 2), round(median(values), 2), low, high)


def bonferroni_level(conditions: int, alpha: float = 0.05) -> float:
    """Intervalo de um teste entre vários: o nível sobe para o alfa dividido
    pelo número de condições declaradas."""
    return 1 - alpha / conditions


def table(pairs: list[dict], level: float = 0.95) -> list[dict]:
    lines = []
    for (family, condition), group in sorted(groups(pairs).items()):
        used = applied_only(family, group)
        if not used:
            continue
        legacy_mean, _, legacy_low, legacy_high = effect(used, LEGACY, level)
        strict_mean, strict_median, strict_low, strict_high = effect(used, STRICT, level)
        lines.append({
            "familia": family, "condicao": condition,
            "n": len(used), "descartados": len(group) - len(used),
            "seeds": len({p[CLUSTER] for p in used}),
            "antigo_media": legacy_mean,
            "antigo_ic95_baixo": legacy_low, "antigo_ic95_alto": legacy_high,
            "estrito_media": strict_mean, "estrito_mediana": strict_median,
            "estrito_ic95_baixo": strict_low, "estrito_ic95_alto": strict_high,
        })
    return lines


def escape(text: str) -> str:
    return text.replace("_", r"\_")


def num(value: float) -> str:
    """Grupo com uma seed só não tem intervalo, e nan no texto final é pior que
    um travessão."""
    return "--" if value != value else f"{value:.2f}"


def to_tex(lines: list[dict], level: float = 0.95) -> str:
    out = [
        r"% Gerado por analysis/contrasts.py. Nao editar a mao.",
        f"% Intervalos de {level * 100:.2f}%, bootstrap agrupado pela seed estrutural.",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        f"Família & Condição & $n$ & Seeds & "
        f"Antigo (p.p.) & Estrito (p.p.) \\\\",
        r"\midrule",
    ]
    previous = None
    for line in lines:
        family = line["familia"]
        if previous is not None and family != previous:
            out.append(r"\midrule")
        label = escape(family) if family != previous else ""
        previous = family
        legacy = (f"{num(line['antigo_media'])} "
                  f"[{num(line['antigo_ic95_baixo'])}, {num(line['antigo_ic95_alto'])}]")
        strict = (f"{num(line['estrito_media'])} "
                  f"[{num(line['estrito_ic95_baixo'])}, {num(line['estrito_ic95_alto'])}]")
        out.append(f"{label} & \\texttt{{{escape(line['condicao'])}}} & "
                   f"{line['n']} & {line['seeds']} & {legacy} & {strict} \\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha ou de um shard")
    parser.add_argument("--bonferroni", action="store_true",
                        help="ajusta o nível pelo número de condições declaradas")
    args = parser.parse_args()

    pairs = load(args.campaign)
    if not pairs:
        raise SystemExit(f"Nenhum paired_effects_corrigido.csv em {args.campaign}. "
                         "Rode recompute_lineage.py antes.")

    conditions = len(table(pairs))
    level = bonferroni_level(conditions) if args.bonferroni else 0.95
    lines = table(pairs, level)
    out_dir = args.campaign / "tabelas"
    out_dir.mkdir(exist_ok=True)
    with (out_dir / "contrastes.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(lines)
    (out_dir / "contrastes.tex").write_text(to_tex(lines, level), encoding="utf-8")

    print(f"{out_dir / 'contrastes.csv'}")
    print(f"{out_dir / 'contrastes.tex'}")
    adjustment = "com Bonferroni" if args.bonferroni else "sem ajuste de multiplicidade"
    print(f"\n{len(pairs)} pares, {len(lines)} condições, "
          f"intervalos de {level * 100:.2f}% {adjustment}.")
    print(f"{'familia':<14}{'condicao':<30}{'n':>5}{'desc':>6}"
          f"{'antigo':>10}{'estrito':>10}")
    for line in lines:
        print(f"{line['familia']:<14}{line['condicao']:<30}{line['n']:>5}"
              f"{line['descartados']:>6}{line['antigo_media']:>10.2f}"
              f"{line['estrito_media']:>10.2f}")


if __name__ == "__main__":
    main()
