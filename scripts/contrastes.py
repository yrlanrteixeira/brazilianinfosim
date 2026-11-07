"""
Contrastes pareados por condição, nas duas métricas de alcance lado a lado.

Cada tratamento é comparado ao controle do seu próprio bloco. A coluna antiga
mede a linhagem operacional e a corrigida mede a profundidade 0; a distância
entre as duas é o que este trabalho mede.

Intervenções em t=2 só ocorrem quando a cascata chega ao tick 2, então a linha
delas descreve um subconjunto selecionado. A coluna `descartados` diz quantos
pares ficaram de fora por intervenção não aplicada.

Grava `tabelas/contrastes.csv` e `tabelas/contrastes.tex`.

    python scripts/contrastes.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import median

from analisar_corrigido import clustered_ci, cluster_totals

CLUSTER = "seed_index"
ANTIGO = "lineage_reach_difference_pp"
ESTRITO = "reach_difference_pp_strict"

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
    return [p for p in pairs if p.get(ESTRITO) not in (None, "")]


def applied_only(family: str, grupo: list[dict]) -> list[dict]:
    """Só a família de intervenção tem tratamento a aplicar. Nas demais a flag é
    falsa por construção, e filtrar por ela esvaziaria o grupo."""
    if family != "intervention":
        return grupo
    return [p for p in grupo if p["intervention_applied"] == "True"]


def groups(pairs: list[dict]) -> dict[tuple[str, str], list[dict]]:
    agrupado: dict[tuple[str, str], list[dict]] = {}
    for pair in pairs:
        agrupado.setdefault((pair["family"], pair["condition"]), []).append(pair)
    return agrupado


def effect(grupo: list[dict], column: str,
           level: float = 0.95) -> tuple[float, float, float, float]:
    valores = [float(p[column]) for p in grupo]
    baixo, alto = clustered_ci(cluster_totals(grupo, lambda p: float(p[column]), CLUSTER),
                               level=level)
    return (round(sum(valores) / len(valores), 2), round(median(valores), 2), baixo, alto)


def bonferroni_level(condicoes: int, alfa: float = 0.05) -> float:
    """Intervalo de um teste entre vários: o nível sobe para o alfa dividido
    pelo número de condições declaradas."""
    return 1 - alfa / condicoes


def table(pairs: list[dict], level: float = 0.95) -> list[dict]:
    lines = []
    for (family, condition), grupo in sorted(groups(pairs).items()):
        usados = applied_only(family, grupo)
        if not usados:
            continue
        a_media, _, a_baixo, a_alto = effect(usados, ANTIGO, level)
        e_media, e_mediana, e_baixo, e_alto = effect(usados, ESTRITO, level)
        lines.append({
            "familia": family, "condicao": condition,
            "n": len(usados), "descartados": len(grupo) - len(usados),
            "seeds": len({p[CLUSTER] for p in usados}),
            "antigo_media": a_media, "antigo_ic95_baixo": a_baixo, "antigo_ic95_alto": a_alto,
            "estrito_media": e_media, "estrito_mediana": e_mediana,
            "estrito_ic95_baixo": e_baixo, "estrito_ic95_alto": e_alto,
        })
    return lines


def escape(text: str) -> str:
    return text.replace("_", r"\_")


def num(valor: float) -> str:
    """Grupo com uma seed só não tem intervalo, e nan no texto final é pior que
    um travessão."""
    return "--" if valor != valor else f"{valor:.2f}"


def to_tex(lines: list[dict], level: float = 0.95) -> str:
    out = [
        r"% Gerado por scripts/contrastes.py. Nao editar a mao.",
        f"% Intervalos de {level * 100:.2f}%, bootstrap agrupado pela seed estrutural.",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        f"Família & Condição & $n$ & Seeds & "
        f"Antigo (p.p.) & Estrito (p.p.) \\\\",
        r"\midrule",
    ]
    anterior = None
    for linha in lines:
        familia = linha["familia"]
        if anterior is not None and familia != anterior:
            out.append(r"\midrule")
        rotulo = escape(familia) if familia != anterior else ""
        anterior = familia
        antigo = (f"{num(linha['antigo_media'])} "
                  f"[{num(linha['antigo_ic95_baixo'])}, {num(linha['antigo_ic95_alto'])}]")
        estrito = (f"{num(linha['estrito_media'])} "
                   f"[{num(linha['estrito_ic95_baixo'])}, {num(linha['estrito_ic95_alto'])}]")
        out.append(f"{rotulo} & \\texttt{{{escape(linha['condicao'])}}} & "
                   f"{linha['n']} & {linha['seeds']} & {antigo} & {estrito} \\\\")
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

    condicoes = len(table(pairs))
    level = bonferroni_level(condicoes) if args.bonferroni else 0.95
    lines = table(pairs, level)
    saida = args.campaign / "tabelas"
    saida.mkdir(exist_ok=True)
    with (saida / "contrastes.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(lines)
    (saida / "contrastes.tex").write_text(to_tex(lines, level), encoding="utf-8")

    print(f"{saida / 'contrastes.csv'}")
    print(f"{saida / 'contrastes.tex'}")
    ajuste = "com Bonferroni" if args.bonferroni else "sem ajuste de multiplicidade"
    print(f"\n{len(pairs)} pares, {len(lines)} condições, "
          f"intervalos de {level * 100:.2f}% {ajuste}.")
    print(f"{'familia':<14}{'condicao':<30}{'n':>5}{'desc':>6}"
          f"{'antigo':>10}{'estrito':>10}")
    for linha in lines:
        print(f"{linha['familia']:<14}{linha['condicao']:<30}{linha['n']:>5}"
              f"{linha['descartados']:>6}{linha['antigo_media']:>10.2f}"
              f"{linha['estrito_media']:>10.2f}")


if __name__ == "__main__":
    main()
