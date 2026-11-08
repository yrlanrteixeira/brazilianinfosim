"""
agents/agent.py
Agente de simulação baseado em Mesa, integrado com LLM.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional
import random
import mesa

from .profiles import AgentProfile

if TYPE_CHECKING:
    from llm.client import LLMClient


class Decision(str, Enum):
    IGNORE   = "IGNORAR"
    SHARE    = "COMPARTILHAR"
    MUTATE   = "COMPARTILHAR_COM_COMENTARIO"
    QUESTION = "QUESTIONAR"
    REFUTE   = "REFUTAR"


@dataclass
class Message:
    content: str
    original_content: str
    hops: int = 0               # quantos compartilhamentos já ocorreram
    sender_id: Optional[int] = None
    # Versão anterior: o índice de mutação compara versões consecutivas.
    parent_content: Optional[str] = None
    # Canal de entrega, não postura do texto: alterna a cada refutação para que
    # a correção chegue a quem já viu o boato. Quem classifica é refutation_depth.
    is_refutation: bool = False
    parent_is_refutation: bool = False
    # Refutações acumuladas na linhagem. 0 é o boato, 1 é a correção dele. De 2
    # em diante a postura do texto só se resolve por anotação de conteúdo.
    refutation_depth: int = 0

    def __post_init__(self) -> None:
        if self.is_refutation and self.refutation_depth == 0:
            self.refutation_depth = 1

    @property
    def dedup_key(self) -> tuple[str, bool]:
        """Uma exposição por boato, não por variante do texto."""
        return (self.original_content, self.is_refutation)

    @property
    def lineage_key(self) -> tuple[str, int]:
        """Identifica a linhagem para medição, separando contestações sucessivas."""
        return (self.original_content, self.refutation_depth)

    def mutate(self, new_content: str, sender_id: Optional[int] = None) -> "Message":
        return Message(
            content=new_content,
            original_content=self.original_content,
            hops=self.hops + 1,
            # Antes propagava self.sender_id (o remetente ANTERIOR), atribuindo
            # a mutação ao agente errado na cadeia de propagação.
            sender_id=sender_id if sender_id is not None else self.sender_id,
            parent_content=self.content,
            is_refutation=self.is_refutation,
            parent_is_refutation=self.is_refutation,
            refutation_depth=self.refutation_depth,
        )

    def forward(self, sender_id: int) -> "Message":
        return Message(
            content=self.content,
            original_content=self.original_content,
            hops=self.hops + 1,
            sender_id=sender_id,
            parent_content=self.content,
            is_refutation=self.is_refutation,
            parent_is_refutation=self.is_refutation,
            refutation_depth=self.refutation_depth,
        )


class InfoAgent(mesa.Agent):
    """
    Agente que representa um usuário de rede social brasileira.
    Recebe mensagens dos vizinhos e decide, via LLM, o que fazer.
    """

    def __init__(
        self,
        model: mesa.Model,
        profile: AgentProfile,
        llm_client: "LLMClient",
        node_id: int,
    ):
        # Mesa 3.x: Agent.__init__ recebe apenas o model; unique_id é
        # atribuído automaticamente. Guardamos node_id para casar com o grafo.
        super().__init__(model)
        self.node_id = node_id
        self.profile = profile
        self.llm = llm_client

        # Estado dinâmico
        self.inbox: list[Message] = []
        self.sent_messages: list[Message] = []
        self.seen_lineages: set[tuple[str, int]] = set()
        # Reexposição é permitida entre ticks, não dentro do mesmo tick.
        self._tick_seen: set[tuple[str, bool]] = set()
        self._tick_seen_at: int = -1
        self.belief_level: float = 0.5   # 0=desacredita, 1=acredita totalmente
        self.interaction_history: list[dict] = []
        self.refusal_count: int = 0      # recusas do LLM (guardrail) neste agente

    @property
    def has_seen_disinformation(self) -> bool:
        return any(depth == 0 for _, depth in self.seen_lineages)

    @property
    def has_seen_correction(self) -> bool:
        return any(depth == 1 for _, depth in self.seen_lineages)

    @property
    def has_seen_ambiguous(self) -> bool:
        """Contestação de correção: só a leitura do texto resolve a postura."""
        return any(depth >= 2 for _, depth in self.seen_lineages)

    @property
    def mutated_messages(self) -> list[Message]:
        """Mensagens que este agente enviou com conteúdo alterado."""
        return [m for m in self.sent_messages
                if m.refutation_depth == 0
                and m.parent_content is not None and m.content != m.parent_content]

    def receive(self, message: Message) -> None:
        """
        Entrega uma mensagem, no máximo uma por boato por tick.

        A dedup é pela linhagem (`dedup_key`), não pelo texto: mutação gera
        conteúdo novo, e deduplicar por texto fazia cada variante voltar para a
        fila de quem já tinha visto a anterior, multiplicando as chamadas ao
        LLM sem alterar o alcance.
        """
        key = message.dedup_key
        if self._tick_seen_at != self.model.tick:
            self._tick_seen_at = self.model.tick
            self._tick_seen = set()
        if key in self._tick_seen or any(m.dedup_key == key for m in self.inbox):
            return
        self._tick_seen.add(key)
        self.seen_lineages.add(message.lineage_key)
        self.inbox.append(message)
        self._audit_message("received", message)

    def step(self) -> None:
        """Executado a cada tick pelo Mesa."""
        round_inboxes = getattr(self.model, "round_inboxes", None)
        messages = self.inbox if round_inboxes is None else round_inboxes[self.node_id]
        if not messages:
            return

        if round_inboxes is None:
            self.inbox = []
        if self._tick_seen_at != self.model.tick:
            self._tick_seen_at = self.model.tick
            self._tick_seen = set()
        if round_inboxes is None:
            self._tick_seen.update(m.dedup_key for m in messages)
        for message in messages:
            if (self.profile.agent_type.value == "indiferente"
                    and not getattr(getattr(self.model, "config", None), "indifferent_uses_llm", False)):
                self._handle_indifferent(message)
            else:
                self._process_message(message)

    def _handle_indifferent(self, message: Message) -> None:
        # Usava `random` global (não semeado), tornando a ignição de sementes
        # indiferentes irreprodutível entre execuções. Agora usa o RNG do modelo.
        self.seen_lineages.add(message.lineage_key)
        if self.model.rng.random() < 0.10:   # 10% de chance de compartilhar
            self._broadcast(message.forward(self.node_id))

    def _process_message(self, message: Message) -> None:
        self.seen_lineages.add(message.lineage_key)

        content = message.content
        if message.is_refutation and not content.startswith("[REFUTAÇÃO]"):
            content = f"[REFUTAÇÃO] {content}"
        self.llm.audit_context = {"node_id": self.node_id, "tick": self.model.tick,
                                  "is_refutation": message.is_refutation,
                                  "agent_type": self.profile.agent_type.value}
        decision, new_content, refused = self.llm.decide(
            agent_description=self.profile.to_prompt_description(),
            message_content=content,
            history=self.interaction_history[-5:],  # últimas 5 interações
        )

        if refused:
            self.refusal_count += 1

        mutation_suppressed = decision == Decision.MUTATE and not getattr(
            getattr(self.model, "config", None), "mutation_enabled", True
        )
        sent_content = ""
        if not refused:
            if decision == Decision.SHARE or mutation_suppressed:
                sent_content = message.content
            elif decision in {Decision.MUTATE, Decision.REFUTE}:
                sent_content = new_content
        self.interaction_history.append({
            "tick": self.model.tick,
            "received": message.content,
            "decision": decision.value,
            "sent": sent_content,
            "mutation_suppressed": mutation_suppressed,
            "refused": refused,   # distingue recusa do LLM de decisão do perfil
            "is_refutation": message.is_refutation,
        })

        if refused or decision == Decision.IGNORE:
            return

        direction = -1 if message.is_refutation else 1
        changes = {Decision.QUESTION: -0.1, Decision.REFUTE: -0.2,
                   Decision.SHARE: 0.15, Decision.MUTATE: 0.10}
        self.belief_level = min(1.0, max(0.0, self.belief_level + direction * changes[decision]))

        if decision == Decision.REFUTE:
            # O canal alterna para a mensagem ser entregue; a profundidade só
            # cresce, porque contestar uma correção não devolve o texto ao boato.
            refutation = Message(
                content=new_content if message.is_refutation else f"[REFUTAÇÃO] {new_content}",
                original_content=message.original_content,
                hops=message.hops + 1,
                sender_id=self.node_id,
                parent_content=message.content,
                is_refutation=not message.is_refutation,
                parent_is_refutation=message.is_refutation,
                refutation_depth=message.refutation_depth + 1,
            )
            self._broadcast(refutation)

        elif decision == Decision.SHARE:
            self._broadcast(message.forward(self.node_id))

        elif decision == Decision.MUTATE:
            # O modelo às vezes muta com `content` vazio: repassa sem alterar.
            if new_content.strip() and not mutation_suppressed:
                self._broadcast(message.mutate(new_content, sender_id=self.node_id))
            else:
                self._broadcast(message.forward(self.node_id))

    def _broadcast(self, message: Message) -> None:
        """Envia mensagem para todos os vizinhos no grafo."""
        self.sent_messages.append(message)
        # Nós removidos por remove_hubs saem do grafo; evita NetworkXError.
        if self.node_id not in self.model.G:
            return
        self._audit_message("sent", message)
        neighbors = list(self.model.G.neighbors(self.node_id))
        limit = getattr(self.model, "active_forwarding_limit", None)
        if limit is not None and len(neighbors) > limit:
            selection = random.Random(
                f"forward:{self.model.config.seed}:{self.model.tick}:{self.node_id}:{message.dedup_key}"
            )
            neighbors = selection.sample(sorted(neighbors), limit)
        for neighbor_id in neighbors:
            neighbor = self.model.agents_by_id.get(neighbor_id)
            if neighbor:
                neighbor.receive(message)

    def _audit_message(self, event: str, message: Message) -> None:
        self.model.message_audit.append({
            "event": event, "node_id": self.node_id, "tick": self.model.tick,
            "content": message.content, "original_content": message.original_content,
            "parent_content": message.parent_content, "sender_id": message.sender_id,
            "hops": message.hops, "is_refutation": message.is_refutation,
            "parent_is_refutation": message.parent_is_refutation,
            "refutation_depth": message.refutation_depth,
        })
