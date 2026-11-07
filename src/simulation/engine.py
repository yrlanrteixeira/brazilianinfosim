"""
simulation/engine.py
Motor de simulação principal — orquestra agentes, rede e coleta de dados.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
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
    network_seed: Optional[int] = None
    profile_seed: Optional[int] = None
    activation_seed: Optional[int] = None
    llm_seed: Optional[int] = None

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
    # None nos dois: o LLMClient resolve via env.
    cache_mode: Optional[str] = None     # None | "exact" | "semantic" | "off"
    temperature: Optional[float] = None

    def __post_init__(self):
        if self.n_agents < 7 or self.max_ticks < 1:
            raise ValueError("Use n_agents >= 7 e max_ticks >= 1.")
        if self.intervention_tick < 0:
            raise ValueError("intervention_tick deve ser não negativo.")
        if self.inject_at not in {"hub", "random", "influencer"}:
            raise ValueError("Ponto de injeção desconhecido.")
        if self.intervention not in {None, "factcheckers_hub", "factcheckers_peripheral", "remove_hubs"}:
            raise ValueError("Intervenção desconhecida.")


class InfoSimModel(mesa.Model):
    """
    Modelo principal do BrazilianInfoSim.
    Herda de mesa.Model para integração com o scheduler do Mesa.
    """

    def __init__(self, config: SimulationConfig):
        # Mesa 3.x: passamos a seed ao Model (RNG interno). Mantemos também
        # um Random próprio para sorteios reprodutíveis do modelo.
        super().__init__(rng=config.activation_seed if config.activation_seed is not None else config.seed)
        self.config = config
        self.rng = random.Random(config.seed)
        self.tick = 0   # contador próprio de ticks (Mesa 3.x removeu schedule.time)

        # Constrói rede
        self.G: nx.Graph = build_network(
            topology=config.topology,
            n_agents=config.n_agents,
            seed=config.network_seed if config.network_seed is not None else config.seed,
        )

        # Inicializa LLM
        self.llm = LLMClient(
            provider=config.llm_provider,
            model=config.llm_model,
            enable_cache=config.enable_cache,
            cache_mode=config.cache_mode,
            temperature=config.temperature,
            seed=config.llm_seed,
        )

        # Cria agentes (Mesa 3.x registra automaticamente em self.agents)
        self.agents_by_id: dict[int, InfoAgent] = {}
        profile_seed = config.profile_seed if config.profile_seed is not None else config.seed
        profile_rng = random.Random(f"profiles:{profile_seed}")
        for node_id in self.G.nodes():
            profile = generate_profile(seed=profile_rng.getrandbits(128))
            agent = InfoAgent(
                model=self,
                profile=profile,
                llm_client=self.llm,
                node_id=node_id,
            )
            self.agents_by_id[node_id] = agent
        self.initial_state = {
            "edges": [list(edge) for edge in self.G.edges()],
            "profiles": [{"node_id": node, **asdict(agent.profile)}
                         for node, agent in self.agents_by_id.items()],
        }

        # Nós removidos por intervenção (para a métrica de alcance ativo)
        self.removed_nodes: list[int] = []
        self.removed_agents: dict[int, InfoAgent] = {}
        self.intervention_applied_tick: Optional[int] = None
        self.intervention_nodes: list[int] = []

        # Coleta de dados por tick
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "reached_count": self._count_reached,
                "reach_pct": lambda m: m._count_reached() / m.config.n_agents * 100,
                "reach_pct_active": lambda m: (
                    m._count_reached_active() / max(1, len(m.agents_by_id)) * 100
                ),
                "correction_reach_pct": lambda m: m._count_corrections() / m.config.n_agents * 100,
                "ambiguous_reach_pct": lambda m: m._count_ambiguous() / m.config.n_agents * 100,
                "believers": self._count_believers,
                "pending_messages": lambda m: sum(len(a.inbox) for a in m.agents_by_id.values()),
                "tick": lambda m: m.tick,
            },
            agent_reporters={
                "belief_level": "belief_level",
                "agent_type": lambda a: a.profile.agent_type.value,
                "has_seen": "has_seen_disinformation",
                "has_seen_correction": "has_seen_correction",
                "has_seen_ambiguous": "has_seen_ambiguous",
            }
        )

        # Injeta mensagem inicial
        self._inject_initial_message()
        self.datacollector.collect(self)
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
        self.initial_state["injection_node"] = start_node
        seed_agent.receive(msg)
        logger.info(f"Fake news injetada no nó {start_node} (grau={self.G.degree(start_node)})")

    def _apply_intervention(self) -> None:
        """Aplica intervenção no tick configurado."""
        if not self.config.intervention or self.intervention_applied_tick is not None:
            return
        if self.config.intervention == "factcheckers_hub":
            hubs = get_hub_nodes(self.G, top_k=max(1, self.config.n_agents // 10))
            for node_id in hubs:
                # Antes fazia apenas `profile.agent_type = AgentType.FACTCHECKER`,
                # que não altera nada do que o LLM efetivamente lê.
                self.agents_by_id[node_id].profile.apply_factchecker_conversion()
            logger.info(f"Intervenção: {len(hubs)} fact-checkers inseridos em hubs")
            self.intervention_nodes = hubs

        elif self.config.intervention == "factcheckers_peripheral":
            from network.topology import get_peripheral_nodes
            peripheral = get_peripheral_nodes(self.G, bottom_k=max(1, self.config.n_agents // 10))
            for node_id in peripheral:
                # Antes fazia apenas `profile.agent_type = AgentType.FACTCHECKER`,
                # que não altera nada do que o LLM efetivamente lê.
                self.agents_by_id[node_id].profile.apply_factchecker_conversion()
            logger.info(f"Intervenção: {len(peripheral)} fact-checkers inseridos em nós periféricos")
            self.intervention_nodes = peripheral

        elif self.config.intervention == "remove_hubs":
            hubs = get_hub_nodes(self.G, top_k=5)
            self.G.remove_nodes_from(hubs)
            for node_id in hubs:
                agent = self.agents_by_id.pop(node_id)
                self.removed_agents[node_id] = agent
                agent.inbox.clear()
                agent.remove()
            self.removed_nodes.extend(hubs)
            self.intervention_nodes = hubs
            logger.info(f"Intervenção: {len(hubs)} supernós removidos da rede")
        self.intervention_applied_tick = self.tick

    def _population_agents(self):
        yield from self.agents_by_id.values()
        yield from self.removed_agents.values()

    def _count_reached(self) -> int:
        return sum(a.has_seen_disinformation for a in self._population_agents())

    def _count_reached_active(self) -> int:
        return sum(1 for a in self.agents_by_id.values() if a.has_seen_disinformation)

    def _count_corrections(self) -> int:
        return sum(a.has_seen_correction for a in self._population_agents())

    def _count_ambiguous(self) -> int:
        return sum(a.has_seen_ambiguous for a in self._population_agents())

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
            for agent in self._population_agents()
            for m in agent.mutated_messages
        ]

    def step(self) -> None:
        """Executa um tick de simulação."""
        # Aplica intervenção no tick configurado
        if self.config.intervention and self.tick == self.config.intervention_tick:
            self._apply_intervention()

        # Mesa 3.x: ativação aleatória dos agentes via AgentSet
        self.agents.shuffle_do("step")
        self.tick += 1
        self.datacollector.collect(self)

    def run(self, deadline: Optional[float] = None) -> "SimulationResult":
        """Executa a simulação completa até max_ticks ou extinção."""
        stop_reason = "max_ticks"
        self.llm.deadline = deadline
        while self.tick < self.config.max_ticks:
            if not any(a.inbox for a in self.agents_by_id.values()):
                stop_reason = "extinct"
                break
            self.step()
        if not any(a.inbox for a in self.agents_by_id.values()):
            stop_reason = "extinct"
        reached = self._count_reached()

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
            extinction_tick=self.tick if stop_reason == "extinct" else None,
            ticks_run=self.tick,
            stop_reason=stop_reason,
            llm_stats=self.llm.stats,
            final_reach_pct_active=self._count_reached_active() / max(1, len(self.agents_by_id)) * 100,
            final_correction_reach_pct=self._count_corrections() / self.config.n_agents * 100,
            final_ambiguous_reach_pct=self._count_ambiguous() / self.config.n_agents * 100,
            mutations=self._collect_mutations(),
            n_removed=len(self.removed_nodes),
            refusals_total=sum(a.refusal_count for a in self._population_agents()),
            intervention_applied=self.intervention_applied_tick is not None,
            intervention_applied_tick=self.intervention_applied_tick,
            intervention_nodes=list(self.intervention_nodes),
            initial_state=self.initial_state,
            decision_audit=list(getattr(self.llm, "audit_log", [])),
        )


@dataclass
class SimulationResult:
    config: SimulationConfig
    model_data: object       # DataFrame
    agent_data: object       # DataFrame
    final_reach_pct: float
    extinction_tick: Optional[int]
    llm_stats: dict
    # Alcance sobre os nós que restam: com remove_hubs, n_agents inflaria
    # artificialmente o efeito da intervenção.
    final_reach_pct_active: float = 0.0
    mutations: list = field(default_factory=list)
    n_removed: int = 0
    refusals_total: int = 0
    ticks_run: int = 0
    stop_reason: str = "unknown"
    final_correction_reach_pct: float = 0.0
    # Alcance da linhagem cuja postura depende de anotação. O limite superior do
    # alcance do boato é final_reach_pct mais este valor.
    final_ambiguous_reach_pct: float = 0.0
    intervention_applied: bool = False
    intervention_applied_tick: Optional[int] = None
    intervention_nodes: list[int] = field(default_factory=list)
    initial_state: dict = field(default_factory=dict)
    decision_audit: list[dict] = field(default_factory=list)
