"""
metrics/analysis.py
Coleta, análise e visualização dos resultados de simulação.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

if TYPE_CHECKING:
    from ..simulation.engine import SimulationResult


def semantic_mutation_rate(messages: list[str], original: str) -> float:
    """
    Calcula a taxa de mutação semântica média usando similaridade de cosseno.
    Retorna valor entre 0 (muito mutado) e 1 (idêntico).
    """
    if not messages:
        return 1.0
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        original_emb = model.encode(original)
        sims = []
        for msg in messages:
            emb = model.encode(msg)
            cos = np.dot(original_emb, emb) / (
                np.linalg.norm(original_emb) * np.linalg.norm(emb) + 1e-9
            )
            sims.append(cos)
        return float(np.mean(sims))
    except ImportError:
        return -1.0  # sentence-transformers não instalado


def summarize_result(result: "SimulationResult") -> dict:
    """Gera um dicionário de métricas resumidas de uma simulação."""
    df = result.model_data

    # Velocidade: tick em que atingiu 25%, 50%, 75%
    n = result.config.n_agents
    milestones = {}
    for pct in [25, 50, 75]:
        threshold = pct
        reached = df[df["reach_pct"] >= threshold]
        milestones[f"tick_to_{pct}pct"] = int(reached.index[0]) if len(reached) > 0 else None

    return {
        "topology":          result.config.topology.value,
        "n_agents":          result.config.n_agents,
        "intervention":      result.config.intervention or "none",
        "final_reach_pct":   round(result.final_reach_pct, 2),
        "extinction_tick":   result.extinction_tick,
        "final_believers":   int(df["believers"].iloc[-1]),
        **milestones,
        **result.llm_stats,
    }


def plot_simulation(result: "SimulationResult", save_path: str = None) -> None:
    """Gera painel visual com 3 gráficos: propagação, crença e grau."""
    df = result.model_data
    cfg = result.config

    fig = plt.figure(figsize=(15, 5))
    fig.suptitle(
        f"BrazilianInfoSim — {cfg.topology.value} | N={cfg.n_agents} | "
        f"Intervenção: {cfg.intervention or 'nenhuma'}",
        fontsize=13, fontweight="bold"
    )
    gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35)

    # 1. Curva de propagação
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df.index, df["reach_pct"], color="#E63946", linewidth=2)
    ax1.axhline(y=result.final_reach_pct, color="gray", linestyle="--", alpha=0.5)
    if cfg.intervention:
        ax1.axvline(x=cfg.intervention_tick, color="#457B9D", linestyle=":", linewidth=1.5,
                    label=f"Intervenção (tick {cfg.intervention_tick})")
        ax1.legend(fontsize=8)
    ax1.set_xlabel("Tick")
    ax1.set_ylabel("Alcance (%)")
    ax1.set_title("Propagação da Desinformação")
    ax1.set_ylim(0, 105)
    ax1.grid(alpha=0.3)

    # 2. Crença média ao longo do tempo
    ax2 = fig.add_subplot(gs[1])
    ax2.plot(df.index, df["believers"] / cfg.n_agents * 100, color="#2A9D8F", linewidth=2)
    ax2.set_xlabel("Tick")
    ax2.set_ylabel("% Acreditam")
    ax2.set_title("Evolução da Crença na Rede")
    ax2.set_ylim(0, 105)
    ax2.grid(alpha=0.3)

    # 3. Alcance final por tipo de agente (última coleta)
    ax3 = fig.add_subplot(gs[2])
    agent_df = result.agent_data.xs(result.extinction_tick - 1, level="Step") \
        if result.extinction_tick > 1 else result.agent_data.xs(0, level="Step")
    if "agent_type" in agent_df.columns:
        reach_by_type = agent_df.groupby("agent_type")["has_seen"].mean() * 100
        colors = {
            "amplificador": "#E63946",
            "cetico":       "#457B9D",
            "influenciador":"#F4A261",
            "fact_checker": "#2A9D8F",
            "indiferente":  "#ADB5BD",
        }
        bars = ax3.bar(
            reach_by_type.index,
            reach_by_type.values,
            color=[colors.get(t, "#888") for t in reach_by_type.index]
        )
        ax3.set_ylabel("% que recebeu a mensagem")
        ax3.set_title("Alcance por Tipo de Agente")
        ax3.set_ylim(0, 110)
        ax3.tick_params(axis="x", rotation=30)
        ax3.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, reach_by_type.values):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                     f"{val:.0f}%", ha="center", fontsize=8)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Gráfico salvo em: {save_path}")
    else:
        plt.show()


def compare_results(results: list["SimulationResult"]) -> pd.DataFrame:
    """Cria tabela comparativa entre múltiplas simulações."""
    rows = [summarize_result(r) for r in results]
    return pd.DataFrame(rows)
