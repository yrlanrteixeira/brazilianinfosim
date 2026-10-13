"""
app.py
Interface visual de replay: reproduz uma execução gravada.

    solara run app.py

Não chama LLM. Os dados vêm das gravações em data/outputs/recordings/,
produzidas pelas campanhas com --record.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import networkx as nx
import solara
from matplotlib.figure import Figure
from mesa.visualization import SolaraViz, make_plot_component
from mesa.visualization.utils import update_counter

from simulation.replay import NodeState, ReplayModel

RECORDINGS_DIR = Path("data/outputs/recordings")

STATE_STYLE = {
    NodeState.SEED:        ("#7C3AED", "Semeado"),
    NodeState.UNREACHED:   ("#D5DAE6", "Não alcançado"),
    NodeState.REACHED:     ("#F4A261", "Exposto; estado ≤ 0,5"),
    NodeState.BELIEVER:    ("#E63946", "Exposto; estado > 0,5"),
    NodeState.FACTCHECKER: ("#2A9D8F", "Fact-checker"),
}


def available_recordings() -> list[str]:
    return sorted(str(p) for p in RECORDINGS_DIR.glob("*.json"))


@solara.component
def NetworkPanel(model):
    """Grafo da rede, colorido pelo estado de cada agente no tick atual."""
    update_counter.get()

    fig = Figure(figsize=(6.5, 5.2))
    ax = fig.add_subplot()
    ax.set_axis_off()

    states = {n: model.node_state(n) for n in model.G.nodes()}
    colors = [STATE_STYLE[states[n]][0] for n in model.G.nodes()]
    sizes = [80 + 26 * model.G.degree(n) for n in model.G.nodes()]

    nx.draw_networkx_edges(model.G, model.pos, ax=ax, alpha=0.25, width=0.8)
    nx.draw_networkx_nodes(
        model.G, model.pos, ax=ax, node_color=colors, node_size=sizes,
        edgecolors="#1B2440", linewidths=0.6,
    )

    seed_node = model.meta.get("seed_node")
    if seed_node in model.G:
        nx.draw_networkx_nodes(
            model.G, model.pos, ax=ax, nodelist=[seed_node],
            node_color="none", node_size=[240], edgecolors="#7C3AED",
            linewidths=2.2,
        )

    snapshot = model.current
    ax.set_title(
        f"Tick {model.tick} de {model.total_ticks - 1}  |  "
        f"linhagem do boato {snapshot['reached']}/{model.meta['n_agents']}  |  "
        f"estado > 0,5: {snapshot['believers']}",
        fontsize=11,
    )
    for state, (color, label) in STATE_STYLE.items():
        ax.scatter([], [], c=color, s=60, label=label)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=3,
              fontsize=8, frameon=False)

    solara.FigureMatplotlib(fig, dependencies=[model.index])


@solara.component
def RunInfo(model):
    """Procedência da gravação: sem isso o gráfico não é interpretável."""
    update_counter.get()
    meta = model.meta
    with solara.Card("Execução gravada"):
        solara.Markdown(
            f"""
| | |
|---|---|
| Modelo | `{meta.get('provider')} / {meta.get('model')}` |
| Temperatura | {meta.get('temperature')} |
| Cache | `{meta.get('cache_mode')}` |
| Topologia | {meta.get('topology')} |
| Agentes | {meta.get('n_agents')} |
| Semente | {meta.get('seed')} |
| Injeção | {meta.get('inject_at')} (nó {meta.get('seed_node')}) |
| Chamadas ao LLM | {model.current.get('api_calls')} |
| Recusas | {model.current.get('refusals')} |

O alcance acompanha a linhagem operacional. O estado numérico deriva das ações;
nenhum dos dois comprova apoio textual ou crença humana.

> {meta.get('initial_message', '')}
"""
        )


_recordings = available_recordings()

if not _recordings:
    @solara.component
    def Page():
        solara.Error(
            f"Nenhuma gravação em {RECORDINGS_DIR}/. "
            "Execute python run_simulation.py --record antes de abrir o replay."
        )
else:
    model = ReplayModel(_recordings[0])

    Page = SolaraViz(
        model,
        components=[
            NetworkPanel,
            make_plot_component(["reach_pct", "believers"]),
            RunInfo,
        ],
        model_params={
            "recording": {
                "type": "Select",
                "label": "Gravação",
                "value": _recordings[0],
                "values": _recordings,
            },
        },
        play_interval=600,
        name="BrazilianInfoSim, replay de execução",
    )
