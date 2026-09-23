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
    from simulation.engine import SimulationResult


_EMBEDDER = None


def _get_embedder():
    """Carrega o modelo de embeddings uma única vez por processo."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _EMBEDDER


def _cossim(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


_ENCODE_MEMO: dict[str, object] = {}


def reset_encode_memo() -> None:
    """Limpa o memo. Necessário ao trocar de embedder (testes)."""
    _ENCODE_MEMO.clear()


def _encode(text: str):
    """Encoding memoizado: os mesmos textos reaparecem entre linhas."""
    if text not in _ENCODE_MEMO:
        _ENCODE_MEMO[text] = _get_embedder().encode(text)
    return _ENCODE_MEMO[text]


def semantic_mutation_rate(messages: list[str], original: str) -> float:
    """
    Similaridade média de cosseno entre as mensagens mutadas e a original.
    Retorna similaridade no intervalo [-1, 1]. Não mede veracidade.

    ATENÇÃO: esta função retorna SIMILARIDADE, não o índice M do artigo.
    O artigo define M = média de (1 - cossim entre versões CONSECUTIVAS),
    com distância no intervalo [0, 2]. Use `mutation_index()` para isso.
    """
    if not messages:
        return 1.0
    try:
        model = _get_embedder()
        original_emb = model.encode(original)
        sims = [_cossim(original_emb, model.encode(m)) for m in messages]
        return float(np.mean(sims))
    except ImportError:
        return -1.0  # sentence-transformers não instalado


def mutation_index(mutations: list[dict]) -> float:
    """
    Índice de mutação semântica M do artigo, sobre versões CONSECUTIVAS:

        M = (1/N) * sum_t [ 1 - cossim(e_t, e_{t-1}) ]

    Cada item de `mutations` traz `content` (versão t) e `parent_content`
    (versão t-1). A distância está em [0, 2] e não mede veracidade.
    """
    # Vindo de CSV, um parent ausente volta como NaN, que é truthy.
    pares = [(m["content"], m["parent_content"]) for m in mutations
             if m.get("parent_content") and not pd.isna(m["parent_content"])]
    if not pares:
        return 0.0
    try:
        vals = [1.0 - _cossim(_encode(atual), _encode(anterior))
                for atual, anterior in pares]
        return float(np.mean(vals))
    except ImportError:
        return -1.0


def mutation_by_hop(mutations: list[dict]) -> pd.DataFrame:
    """
    Distância agregada por hop, sem pressupor crescimento monotônico.
    Colunas: hop, n, M, M_vs_original.
    """
    cols = ["hop", "n", "M", "M_vs_original"]
    if not mutations:
        return pd.DataFrame(columns=cols)
    try:
        _get_embedder()
    except ImportError:
        return pd.DataFrame(columns=cols)

    linhas = []
    for hop, grupo in pd.DataFrame(mutations).groupby("hop"):
        consec, vs_orig = [], []
        for _, r in grupo.iterrows():
            e_t = _encode(r["content"])
            if r.get("parent_content") and not pd.isna(r["parent_content"]):
                consec.append(1.0 - _cossim(e_t, _encode(r["parent_content"])))
            if r.get("original_content") and not pd.isna(r["original_content"]):
                vs_orig.append(1.0 - _cossim(e_t, _encode(r["original_content"])))
        linhas.append({
            "hop": int(hop),
            "n": len(grupo),
            "M": float(np.mean(consec)) if consec else np.nan,
            "M_vs_original": float(np.mean(vs_orig)) if vs_orig else np.nan,
        })
    return pd.DataFrame(linhas).sort_values("hop").reset_index(drop=True)


def summarize_result(result: "SimulationResult", with_mutation: bool = True) -> dict:
    """
    Gera um dicionário de métricas resumidas de uma simulação.

    with_mutation=False desliga o cálculo do índice de mutação (que exige
    embeddings e é o passo mais lento) — útil em campanhas grandes onde a
    mutação será calculada depois, em lote.
    """
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
        "intervention_tick": result.config.intervention_tick if result.config.intervention else None,
        "seed":              result.config.seed,
        "inject_at":         result.config.inject_at,
        "final_reach_pct":   round(result.final_reach_pct, 2),
        "final_reach_pct_active": round(result.final_reach_pct_active, 2),
        "extinction_tick":   result.extinction_tick,
        "ticks_run":         result.ticks_run,
        "stop_reason":       result.stop_reason,
        "final_correction_reach_pct": round(result.final_correction_reach_pct, 2),
        "intervention_applied": result.intervention_applied,
        "intervention_applied_tick": result.intervention_applied_tick,
        "intervention_nodes": ",".join(map(str, result.intervention_nodes)),
        "final_believers":   int(df["believers"].iloc[-1]),
        "n_removed":         result.n_removed,
        "refusals_agents":   result.refusals_total,
        "n_mutations":       len(result.mutations),
        "mutation_index_M":  (round(mutation_index(result.mutations), 4)
                              if with_mutation and result.mutations else None),
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
    if result.intervention_applied:
        ax1.axvline(x=result.intervention_applied_tick, color="#457B9D", linestyle=":", linewidth=1.5,
                    label=f"Intervenção aplicada (tick {result.intervention_applied_tick})")
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
    last_step = result.agent_data.index.get_level_values("Step").max()
    agent_df = result.agent_data.xs(last_step, level="Step")
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
        ax3.set_title("Alcance entre Agentes Ativos por Tipo Final")
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


def plot_mutation_by_hop(df: pd.DataFrame, save_path: str = None) -> None:
    """
    Painel de mutação semântica por hop (QP3). Espera as colunas hop, n, M,
    M_vs_original e, opcionalmente, subject para uma série por assunto.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    fig.suptitle(
        "Mutação semântica ao longo da cascata (QP3)",
        fontsize=13, fontweight="bold"
    )

    grupos = df.groupby("subject") if "subject" in df.columns else [("todos", df)]
    for nome, g in grupos:
        g = g.sort_values("hop")
        ax1.plot(g["hop"], g["M"], marker="o", linewidth=1.8, label=nome)
        ax2.plot(g["hop"], g["M_vs_original"], marker="o", linewidth=1.8, label=nome)

    ax1.set_title("M entre versões consecutivas")
    ax1.set_ylabel("Distância semântica (1 - cosseno)")
    ax2.set_title("Distância em relação à mensagem original")
    ax2.set_ylabel("1 - cossim(versão, original)")
    for ax in (ax1, ax2):
        ax.set_xlabel("Hop")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

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
