"""
Gera as figuras do artigo a partir das saídas do recálculo.

As duas cores identificam os dois critérios de medida e são as mesmas nas três
figuras. Vêm da paleta Okabe-Ito, validada para daltonismo, e cada série também
se distingue por traço e marcador, porque a revista imprime em escala de cinza.

    python scripts/figuras.py data/outputs/tcc2/conclusao --saida figuras
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MARCA = "#D55E00"
PROFUNDIDADE = "#0072B2"
TINTA = "#1a1a1a"
TINTA_FRACA = "#5a5a5a"
GRADE = "#d8d8d8"

ROTULO_MARCA = "Critério de marca"
ROTULO_PROFUNDIDADE = "Critério de profundidade"

ESTIMULOS = ["benefit_auto_a", "benefit_auto_b", "health_dna_a", "health_dna_b"]


def estilo() -> None:
    plt.rcParams.update({
        "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
        "legend.fontsize": 8.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "text.color": TINTA, "axes.labelcolor": TINTA,
        "xtick.color": TINTA_FRACA, "ytick.color": TINTA_FRACA,
        "axes.edgecolor": GRADE, "grid.color": GRADE, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "lines.linewidth": 2.0,
    })


def load_runs(campaign: Path) -> list[dict]:
    files = ([campaign / "runs_corrigido.csv"]
             if (campaign / "runs_corrigido.csv").exists()
             else sorted(campaign.glob("*/runs_corrigido.csv")))
    rows = []
    for path in files:
        rows.extend(csv.DictReader(path.open(encoding="utf-8")))
    return [r for r in rows if r.get("reach_strict_pct")]


def load_pairs(campaign: Path) -> list[dict]:
    files = ([campaign / "paired_effects_corrigido.csv"]
             if (campaign / "paired_effects_corrigido.csv").exists()
             else sorted(campaign.glob("*/paired_effects_corrigido.csv")))
    pairs = []
    for path in files:
        pairs.extend(csv.DictReader(path.open(encoding="utf-8")))
    return [p for p in pairs if p.get("reach_difference_pp_strict")]


def ecdf(valores: list[float]) -> tuple[list[float], list[float]]:
    """Distribuição acumulada sem escolha de binagem, que esconderia o degrau
    em 2% onde se concentram as execuções que não saíram do emissor."""
    ordenados = sorted(valores)
    n = len(ordenados)
    return ordenados, [(i + 1) / n for i in range(n)]


def media_por_estimulo(rows: list[dict], coluna: str) -> list[float]:
    medias = []
    for estimulo in ESTIMULOS:
        grupo = [float(r[coluna]) for r in rows if r["stimulus_id"] == estimulo]
        medias.append(sum(grupo) / len(grupo) if grupo else 0.0)
    return medias


def figura_distribuicao(rows: list[dict], destino: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    for coluna, cor, rotulo, traco, marcador in (
        ("reach_legacy_pct", MARCA, ROTULO_MARCA, "-", "o"),
        ("reach_strict_pct", PROFUNDIDADE, ROTULO_PROFUNDIDADE, "--", "s"),
    ):
        x, y = ecdf([float(r[coluna]) for r in rows])
        ax.plot(x, y, traco, color=cor, label=rotulo,
                marker=marcador, markevery=max(1, len(x) // 12), markersize=4.5)
    ax.set_xlabel("Alcance do boato na execução (% da população)")
    ax.set_ylabel("Proporção acumulada de execuções")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1.02)
    ax.grid(axis="both", alpha=0.6)
    ax.legend(frameon=False, loc="lower right")
    caminho = destino / "fig_criterios_distribuicao.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def figura_estimulos(rows: list[dict], destino: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    marca = media_por_estimulo(rows, "reach_legacy_pct")
    estrito = media_por_estimulo(rows, "reach_strict_pct")
    pos = range(len(ESTIMULOS))
    largura = 0.38
    ax.bar([p - largura / 2 - 0.01 for p in pos], marca, largura,
           color=MARCA, label=ROTULO_MARCA)
    ax.bar([p + largura / 2 + 0.01 for p in pos], estrito, largura,
           color=PROFUNDIDADE, label=ROTULO_PROFUNDIDADE)
    for p, (a, b) in enumerate(zip(marca, estrito)):
        ax.text(p - largura / 2 - 0.01, a + 1.4, f"{a:.1f}", ha="center",
                fontsize=8, color=TINTA)
        ax.text(p + largura / 2 + 0.01, b + 1.4, f"{b:.1f}", ha="center",
                fontsize=8, color=TINTA)
    ax.set_xticks(list(pos))
    ax.set_xticklabels(ESTIMULOS, fontsize=8)
    ax.set_ylabel("Alcance médio do boato (%)")
    ax.set_ylim(0, max(marca) * 1.22)
    ax.grid(axis="y", alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    caminho = destino / "fig_criterios_estimulos.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def linhas_contraste(contrastes: Path) -> list[dict]:
    return list(csv.DictReader(contrastes.open(encoding="utf-8")))


def figura_contrastes(linhas: list[dict], destino: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 7.6))
    rotulos, posicoes = [], []
    for i, linha in enumerate(reversed(linhas)):
        y = i
        posicoes.append(y)
        rotulos.append(linha["condicao"])
        for prefixo, cor, marcador, deslocamento in (
            ("antigo", MARCA, "o", 0.18),
            ("estrito", PROFUNDIDADE, "s", -0.18),
        ):
            media = float(linha[f"{prefixo}_media"])
            baixo = float(linha[f"{prefixo}_ic95_baixo"])
            alto = float(linha[f"{prefixo}_ic95_alto"])
            ax.plot([baixo, alto], [y + deslocamento] * 2, "-", color=cor, linewidth=1.6)
            ax.plot(media, y + deslocamento, marcador, color=cor, markersize=5,
                    markeredgecolor="white", markeredgewidth=0.6)
    ax.axvline(0, color=TINTA_FRACA, linewidth=1.0, linestyle=":")
    ax.set_yticks(posicoes)
    ax.set_yticklabels(rotulos, fontsize=7.5)
    ax.set_ylim(-0.8, len(linhas) - 0.2)
    ax.set_xlabel("Efeito pareado: tratamento menos controle (pontos percentuais)")
    ax.grid(axis="x", alpha=0.6)
    ax.set_axisbelow(True)
    ax.plot([], [], "o-", color=MARCA, label=ROTULO_MARCA, markersize=5)
    ax.plot([], [], "s-", color=PROFUNDIDADE, label=ROTULO_PROFUNDIDADE, markersize=5)
    ax.legend(frameon=False, loc="lower left", ncol=1)
    caminho = destino / "fig_criterios_contrastes.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha")
    parser.add_argument("--saida", type=Path, default=Path("figuras"))
    args = parser.parse_args()

    estilo()
    args.saida.mkdir(parents=True, exist_ok=True)
    rows = load_runs(args.campaign)
    if not rows:
        raise SystemExit(f"Nenhum runs_corrigido.csv com alcance em {args.campaign}.")

    print(figura_distribuicao(rows, args.saida))
    print(figura_estimulos(rows, args.saida))

    contrastes = args.campaign / "tabelas" / "contrastes.csv"
    if contrastes.exists():
        print(figura_contrastes(linhas_contraste(contrastes), args.saida))
    else:
        print(f"sem {contrastes}; rode contrastes.py para a figura de efeitos")


if __name__ == "__main__":
    main()
