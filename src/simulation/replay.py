"""
simulation/replay.py
Reprodução de uma execução gravada.

Finge ser um mesa.Model para reaproveitar play, pause, step e reset do
SolaraViz, mas cada passo só avança um índice na gravação: não há LLM
envolvido, então a cascata roda instantânea sobre dado real.
"""

from __future__ import annotations
import json
from enum import Enum
from pathlib import Path

import mesa
import networkx as nx

from network.topology import Topology, build_network


class NodeState(str, Enum):
    SEED       = "seed"          # nó onde a mensagem foi injetada
    UNREACHED  = "unreached"     # ainda não recebeu
    REACHED    = "reached"       # recebeu, mas não acredita
    BELIEVER   = "believer"      # recebeu e acredita
    FACTCHECKER = "factchecker"  # verificador, nativo ou convertido


class ReplayModel(mesa.Model):
    """Percorre os snapshots de uma gravação, um por step()."""

    def __init__(self, recording: str):
        super().__init__()
        data = json.loads(Path(recording).read_text(encoding="utf-8"))
        self.meta: dict = data["meta"]
        self.snapshots: list[dict] = data["ticks"]
        self.index = 0

        if "initial_edges" in self.meta:
            self._initial_graph = nx.Graph()
            self._initial_graph.add_nodes_from(range(self.meta["n_agents"]))
            self._initial_graph.add_edges_from(self.meta["initial_edges"])
        else:
            self._initial_graph = build_network(
                topology=Topology(self.meta["topology"]),
                n_agents=self.meta["n_agents"],
                seed=self.meta.get("network_seed", self.meta["seed"]),
            )
        # Layout fixo: recalcular a cada tick faz o grafo pular na tela.
        self.pos = nx.spring_layout(self._initial_graph, seed=self.meta["seed"])
        self._sync_graph()

        self.datacollector = mesa.DataCollector(model_reporters={
            "reach_pct": lambda m: m.current["reached"] / m.meta["n_agents"] * 100,
            "believers": lambda m: m.current["believers"],
            "api_calls": lambda m: m.current["api_calls"],
        })
        self.datacollector.collect(self)

    @property
    def current(self) -> dict:
        return self.snapshots[self.index]

    @property
    def tick(self) -> int:
        return self.current["tick"]

    @property
    def total_ticks(self) -> int:
        return len(self.snapshots)

    def _sync_graph(self) -> None:
        active_nodes = [int(node) for node in self.current["agents"]]
        self.G = self._initial_graph.subgraph(active_nodes).copy()

    def node_state(self, node_id: int) -> NodeState:
        agent = self.current["agents"][str(node_id)]
        if agent["agent_type"] == "fact_checker":
            return NodeState.FACTCHECKER
        if not agent["has_seen"]:
            return (NodeState.SEED if node_id == self.meta["seed_node"]
                    else NodeState.UNREACHED)
        if agent["belief"] > 0.5:
            return NodeState.BELIEVER
        return NodeState.REACHED

    def step(self) -> None:
        if self.index >= len(self.snapshots) - 1:
            self.running = False
            return
        self.index += 1
        self._sync_graph()
        self.datacollector.collect(self)
