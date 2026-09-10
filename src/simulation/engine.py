"""
simulation/engine.py
Motor de simulação principal — orquestra agentes, rede e coleta de dados.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import random

import mesa
import networkx as nx
from loguru import logger

from agents.agent import InfoAgent, Message
from agents.profiles import AgentType, generate_profile
from network.topology import Topology, build_network, get_hub_nodes
from llm.client import LLMClient


@dataclass
class SimulationConfig:
    """Parâmetros de uma simulação."""
    n_agents: int = 50
    topology: Topology = Topology.SCALE_FREE
    max_ticks: int = 100
    seed: int = 42

    # Mensagem inicial
    initial_message: str = (
        "URGENTE: Novo estudo mostra que beber água com limão em jejum "
        "cura 80% dos casos de COVID-19. Compartilhe antes que censurem!"
    )
    inject_at: str = "hub"   # "hub" | "random" | "influencer"

    # Intervenção
    intervention: Optional[str] = None   # None | "factcheckers_hub" | "factcheckers_peripheral" | "remove_hubs"
    intervention_tick: int = 10          # quando aplicar a intervenção

    # LLM (None = deixa o LLMClient resolver via env: LLM_PROVIDER / LLM_MODEL)
    llm_provider: Optional[str] = None   # None | "ollama" | "anthropic"
    llm_model: Optional[str] = None
    enable_cache: bool = True


class InfoSimModel(mesa.Model):
    """
    Modelo principal do BrazilianInfoSim.
    Herda de mesa.Model para integração com o scheduler do Mesa.
    """

    def __init__(self, config: SimulationConfig):
        # Mesa 3.x: passamos a seed ao Model (RNG interno). Mantemos também
        # um Random próprio para sorteios reprodutíveis do modelo.
        super().__init__(rng=config.seed)
        self.config = config
        self.rng = random.Random(config.seed)
        self.tick = 0   # contador próprio de ticks (Mesa 3.x removeu schedule.time)

        # Constrói rede
        self.G: nx.Graph = build_network(
            topology=config.topology,
            n_agents=config.n_agents,
            seed=config.seed,
        )

        # Inicializa LLM
        self.llm = LLMClient(
            provider=config.llm_provider,
            model=config.llm_model,
            enable_cache=config.enable_cache,
        )

        # Cria agentes (Mesa 3.x registra automaticamente em self.agents)
        self.agents_by_id: dict[int, InfoAgent] = {}
        for node_id in self.G.nodes():
            profile = generate_profile(seed=config.seed + node_id)
            agent = InfoAgent(
                model=self,
                profile=profile,
                llm_client=self.llm,
                node_id=node_id,
            )
            self.agents_by_id[node_id] = agent

        # Nós removidos por intervenção (para a métrica de alcance ativo)
        self.removed_nodes: list[int] = []

        # Coleta de dados por tick
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "reached_count": self._count_reached,
                "reach_pct": lambda m: m._count_reached() / m.config.n_agents * 100,
                "reach_pct_active": lambda m: (
                    m._count_reached() / max(1, len(m.agents_by_id)) * 100
                ),
                "believers": self._count_believers,
                "tick": lambda m: m.tick,
            },
            agent_reporters={
                "belief_level": "belief_level",
                "agent_type": lambda a: a.profile.agent_type.value,
                "has_seen": "has_seen_disinformation",
            }
        )

        # Injeta mensagem inicial
        self._inject_initial_message()
        logger.info(
            f"Simulação iniciada: {config.n_agents} agentes, "
            f"topologia={config.topology.value}, seed={config.seed}"
        )

    def _inject_initial_message(self) -> None:
        """Injeta a fake news no nó inicial conforme configuração."""
        if self.config.inject_at == "hub":
            hubs = get_hub_nodes(self.G, top_k=1)
            start_node = hubs[0]
        elif self.config.inject_at == "influencer":
            influencer_ids = [
                aid for aid, a in self.agents_by_id.items()
                if a.profile.agent_type == AgentType.INFLUENCER
            ]
            start_node = self.rng.choice(influencer_ids) if influencer_ids else 0
        else:
            start_node = self.rng.randint(0, self.config.n_agents - 1)

        msg = Message(
            content=self.config.initial_message,
            original_content=self.config.initial_message,
            hops=0,
            sender_id=None,
        )
        seed_agent = self.agents_by_id[start_node]
        seed_agent.receive(msg)
        logger.info(f"Fake news injetada no nó {start_node} (grau={self.G.degree(start_node)})")

    def _apply_intervention(self) -> None:
        """Aplica intervenção no tick configurado."""
        if self.config.intervention == "factcheckers_hub":
            hubs = get_hub_nodes(self.G, top_k=max(1, self.config.n_agents // 10))
            for node_id in hubs:
                # Antes fazia apenas `profile.agent_type = AgentType.FACTCHECKER`,
                # que não altera nada do que o LLM efetivamente lê.
                self.agents_by_id[node_id].profile.apply_factchecker_conversion()
            logger.info(f"Intervenção: {len(hubs)} fact-checkers inseridos em hubs")

        elif self.config.intervention == "factcheckers_peripheral":
            from network.topology import get_peripheral_nodes
            peripheral = get_peripheral_nodes(self.G, bottom_k=max(1, self.config.n_agents // 10))
            for node_id in peripheral:
                # Antes fazia apenas `profile.agent_type = AgentType.FACTCHECKER`,
                # que não altera nada do que o LLM efetivamente lê.
                self.agents_by_id[node_id].profile.apply_factchecker_conversion()
            logger.info(f"Intervenção: {len(peripheral)} fact-checkers inseridos em nós periféricos")

        elif self.config.intervention == "remove_hubs":
            hubs = get_hub_nodes(self.G, top_k=5)
            self.G.remove_nodes_from(hubs)
            for node_id in hubs:
                self.agents_by_id.pop(node_id).remove()
            self.removed_nodes.extend(hubs)
            logger.info(f"Intervenção: {len(hubs)} supernós removidos da rede")

    def _count_reached(self) -> int:
        return sum(1 for a in self.agents_by_id.values() if a.has_seen_disinformation)

    def _count_believers(self) -> int:
        return sum(1 for a in self.agents_by_id.values() if a.belief_level > 0.5)

    def _collect_mutations(self) -> list[dict]:
        """
        Reúne as mensagens mutadas da simulação, com hop e versão anterior —
        insumo para o índice de mutação semântica (QP3).
        """
        return [
            {
                "hop": m.hops,
                "content": m.content,
                "parent_content": m.parent_content,
                "original_content": m.original_content,
                "sender_id": m.sender_id,
            }
            for agent in self.agents_by_id.values()
            for m in agent.mutated_messages
        ]

    def step(self) -> None:
        """Executa um tick de simulação."""
        # Aplica intervenção no tick configurado
        if self.config.intervention and self.tick == self.config.intervention_tick:
            self._apply_intervention()

        self.datacollector.collect(self)
        # Mesa 3.x: ativação aleatória dos agentes via AgentSet
        self.agents.shuffle_do("step")
        self.tick += 1

    def run(self) -> "SimulationResult":
        """Executa a simulação completa até max_ticks ou extinção."""
        prev_reached = 0
        stagnation_count = 0
        reached = 0

        for tick in range(self.config.max_ticks):
            self.step()
            reached = self._count_reached()

            # Condição de parada: sem novos agentes atingidos por 5 ticks
            if reached == prev_reached:
                stagnation_count += 1
            else:
                stagnation_count = 0
                prev_reached = reached

            if stagnation_count >= 5:
                logger.info(f"Simulação extinta no tick {tick} (sem propagação por 5 ticks)")
                break

        logger.info(
            f"Simulação concluída | Alcance: {reached}/{self.config.n_agents} "
            f"({reached/self.config.n_agents*100:.1f}%) | "
            f"LLM: {self.llm.stats}"
        )

        return SimulationResult(
            config=self.config,
            model_data=self.datacollector.get_model_vars_dataframe(),
            agent_data=self.datacollector.get_agent_vars_dataframe(),
            final_reach_pct=reached / self.config.n_agents * 100,
            extinction_tick=self.tick,
            llm_stats=self.llm.stats,
            final_reach_pct_active=reached / max(1, len(self.agents_by_id)) * 100,
            mutations=self._collect_mutations(),
            n_removed=len(self.removed_nodes),
            refusals_total=sum(a.refusal_count for a in self.agents_by_id.values()),
        )


@dataclass
class SimulationResult:
    config: SimulationConfig
    model_data: object       # DataFrame
    agent_data: object       # DataFrame
    final_reach_pct: float
    extinction_tick: int
    llm_stats: dict
    # Alcance sobre os nós que continuam na rede. Com remove_hubs, o
    # denominador original (n_agents) faz o alcance máximo cair para 90% por
    # construção, o que favorece essa intervenção artificialmente.
    final_reach_pct_active: float = 0.0
    mutations: list = field(default_factory=list)
    n_removed: int = 0
    refusals_total: int = 0
