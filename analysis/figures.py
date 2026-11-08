"""
Gera as figuras do artigo a partir das saídas do recálculo.

As duas cores identificam os dois critérios de medida e são as mesmas nas três
figuras. Vêm da paleta Okabe-Ito, validada para daltonismo, e cada série também
se distingue por traço e marcador, porque a revista imprime em escala de cinza.

    python analysis/figures.py data/outputs/tcc2/conclusao --output figuras
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MARK = "#D55E00"
DEPTH = "#0072B2"
INK = "#1a1a1a"
INK_SOFT = "#5a5a5a"
GRID = "#d8d8d8"

LABEL_MARK = "Critério de marca"
LABEL_DEPTH = "Critério de profundidade"

STIMULI = ["benefit_auto_a", "benefit_auto_b", "health_dna_a", "health_dna_b"]


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 10,
        "legend.fontsize": 8.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
        "axes.edgecolor": GRID, "grid.color": GRID, "grid.linewidth": 0.6,
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


def ecdf(values: list[float]) -> tuple[list[float], list[float]]:
    """Distribuição acumulada sem escolha de binagem, que esconderia o degrau
    em 2% onde se concentram as execuções que não saíram do emissor."""
    ordered = sorted(values)
    n = len(ordered)
    return ordered, [(i + 1) / n for i in range(n)]


def mean_by_stimulus(rows: list[dict], column: str) -> list[float]:
    means = []
    for stimulus in STIMULI:
        group = [float(r[column]) for r in rows if r["stimulus_id"] == stimulus]
        means.append(sum(group) / len(group) if group else 0.0)
    return means


def figure_distribution(rows: list[dict], target: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    for column, color, label, dash, marker in (
        ("reach_legacy_pct", MARK, LABEL_MARK, "-", "o"),
        ("reach_strict_pct", DEPTH, LABEL_DEPTH, "--", "s"),
    ):
        x, y = ecdf([float(r[column]) for r in rows])
        ax.plot(x, y, dash, color=color, label=label,
                marker=marker, markevery=max(1, len(x) // 12), markersize=4.5)
    ax.set_xlabel("Alcance do boato na execução (% da população)")
    ax.set_ylabel("Proporção acumulada de execuções")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1.02)
    ax.grid(axis="both", alpha=0.6)
    ax.legend(frameon=False, loc="lower right")
    path = target / "fig_criterios_distribuicao.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure_stimuli(rows: list[dict], target: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    mark = mean_by_stimulus(rows, "reach_legacy_pct")
    strict = mean_by_stimulus(rows, "reach_strict_pct")
    pos = range(len(STIMULI))
    width = 0.38
    ax.bar([p - width / 2 - 0.01 for p in pos], mark, width,
           color=MARK, label=LABEL_MARK)
    ax.bar([p + width / 2 + 0.01 for p in pos], strict, width,
           color=DEPTH, label=LABEL_DEPTH)
    for p, (a, b) in enumerate(zip(mark, strict)):
        ax.text(p - width / 2 - 0.01, a + 1.4, f"{a:.1f}", ha="center",
                fontsize=8, color=INK)
        ax.text(p + width / 2 + 0.01, b + 1.4, f"{b:.1f}", ha="center",
                fontsize=8, color=INK)
    ax.set_xticks(list(pos))
    ax.set_xticklabels(STIMULI, fontsize=8)
    ax.set_ylabel("Alcance médio do boato (%)")
    ax.set_ylim(0, max(mark) * 1.22)
    ax.grid(axis="y", alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    path = target / "fig_criterios_estimulos.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def contrast_lines(contrasts: Path) -> list[dict]:
    return list(csv.DictReader(contrasts.open(encoding="utf-8")))


def figure_contrasts(lines: list[dict], target: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 7.6))
    labels, positions, borders = [], [], []
    inverted = list(reversed(lines))
    for i, line in enumerate(inverted):
        y = i
        if i and line["familia"] != inverted[i - 1]["familia"]:
            borders.append(y - 0.5)
        positions.append(y)
        labels.append(line["condicao"])
        for prefix, color, marker, offset in (
            ("antigo", MARK, "o", 0.18),
            ("estrito", DEPTH, "s", -0.18),
        ):
            mean = float(line[f"{prefix}_media"])
            low = float(line[f"{prefix}_ic95_baixo"])
            high = float(line[f"{prefix}_ic95_alto"])
            ax.plot([low, high], [y + offset] * 2, "-", color=color, linewidth=1.6)
            ax.plot(mean, y + offset, marker, color=color, markersize=5,
                    markeredgecolor="white", markeredgewidth=0.6)
    ax.axvline(0, color=INK_SOFT, linewidth=1.0, linestyle=":")
    # Sem isso o leitor não vê onde uma família termina e a outra começa.
    for y in borders:
        ax.axhline(y, color=GRID, linewidth=0.8)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_ylim(-0.8, len(lines) - 0.2)
    ax.set_xlabel("Efeito pareado: tratamento menos controle (pontos percentuais)")
    ax.grid(axis="x", alpha=0.6)
    ax.set_axisbelow(True)
    ax.plot([], [], "o-", color=MARK, label=LABEL_MARK, markersize=5)
    ax.plot([], [], "s-", color=DEPTH, label=LABEL_DEPTH, markersize=5)
    # Fora da área de dados: com 22 condições, legenda interna cobriria linhas.
    ax.legend(frameon=False, ncol=2, loc="lower center",
              bbox_to_anchor=(0.5, 1.01), borderaxespad=0)
    path = target / "fig_criterios_contrastes.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path, help="pasta da campanha")
    parser.add_argument("--output", type=Path, default=Path("figuras"))
    args = parser.parse_args()

    style()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = load_runs(args.campaign)
    if not rows:
        raise SystemExit(f"Nenhum runs_corrigido.csv com alcance em {args.campaign}.")

    print(figure_distribution(rows, args.output))
    print(figure_stimuli(rows, args.output))

    contrasts = args.campaign / "tabelas" / "contrastes.csv"
    if contrasts.exists():
        print(figure_contrasts(contrast_lines(contrasts), args.output))
    else:
        print(f"sem {contrasts}; rode contrasts.py para a figura de efeitos")


if __name__ == "__main__":
    main()
