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

        self.G: nx.Graph = build_network(
            topology=Topology(self.meta["topology"]),
            n_agents=self.meta["n_agents"],
            seed=self.meta["seed"],
        )
        # Layout fixo: recalcular a cada tick faz o grafo pular na tela.
        self.pos = nx.spring_layout(self.G, seed=self.meta["seed"])

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
        self.datacollector.collect(self)
