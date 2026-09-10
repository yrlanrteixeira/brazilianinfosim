"""
agents/agent.py
Agente de simulação baseado em Mesa, integrado com LLM.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional
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

    def mutate(self, new_content: str, sender_id: Optional[int] = None) -> "Message":
        return Message(
            content=new_content,
            original_content=self.original_content,
            hops=self.hops + 1,
            # Antes propagava self.sender_id (o remetente ANTERIOR), atribuindo
            # a mutação ao agente errado na cadeia de propagação.
            sender_id=sender_id if sender_id is not None else self.sender_id,
            parent_content=self.content,
        )

    def forward(self, sender_id: int) -> "Message":
        return Message(
            content=self.content,
            original_content=self.original_content,
            hops=self.hops + 1,
            sender_id=sender_id,
            parent_content=self.content,
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
        self.received_contents: set[str] = set()
        self.belief_level: float = 0.5   # 0=desacredita, 1=acredita totalmente
        self.interaction_history: list[dict] = []
        self.refusal_count: int = 0      # recusas do LLM (guardrail) neste agente

    @property
    def has_seen_disinformation(self) -> bool:
        return len(self.received_contents) > 0

    @property
    def mutated_messages(self) -> list[Message]:
        """Mensagens que este agente enviou com conteúdo alterado."""
        return [m for m in self.sent_messages
                if m.parent_content is not None and m.content != m.parent_content]

    def receive(self, message: Message) -> None:
        """Chamado pelo motor de simulação para entregar uma mensagem."""
        if message.content not in self.received_contents:
            self.inbox.append(message)

    def step(self) -> None:
        """Executado a cada tick pelo Mesa."""
        if not self.inbox:
            return

        # Agentes indiferentes: decisão determinística sem chamar LLM
        if self.profile.agent_type.value == "indiferente":
            for msg in self.inbox:
                self._handle_indifferent(msg)
            self.inbox.clear()
            return

        for message in self.inbox:
            self._process_message(message)

        self.inbox.clear()

    def _handle_indifferent(self, message: Message) -> None:
        # Usava `random` global (não semeado), tornando a ignição de sementes
        # indiferentes irreprodutível entre execuções. Agora usa o RNG do modelo.
        self.received_contents.add(message.content)
        if self.model.rng.random() < 0.10:   # 10% de chance de compartilhar
            self._broadcast(message.forward(self.node_id))

    def _process_message(self, message: Message) -> None:
        self.received_contents.add(message.content)

        decision, new_content, refused = self.llm.decide(
            agent_description=self.profile.to_prompt_description(),
            message_content=message.content,
            history=self.interaction_history[-5:],  # últimas 5 interações
        )

        if refused:
            self.refusal_count += 1

        self.interaction_history.append({
            "tick": self.model.tick,
            "received": message.content,
            "decision": decision.value,
            "sent": new_content,
            "refused": refused,   # distingue recusa do LLM de decisão do perfil
        })

        if decision == Decision.IGNORE or decision == Decision.QUESTION:
            self.belief_level = max(0.0, self.belief_level - 0.1)

        elif decision == Decision.REFUTE:
            self.belief_level = max(0.0, self.belief_level - 0.2)
            # Fact-checkers notificam vizinhos com refutação
            refutation = Message(
                content=f"[REFUTAÇÃO] {new_content}",
                original_content=message.original_content,
                hops=message.hops + 1,
                sender_id=self.node_id,
                parent_content=message.content,
            )
            self._broadcast(refutation)

        elif decision == Decision.SHARE:
            self.belief_level = min(1.0, self.belief_level + 0.15)
            self._broadcast(message.forward(self.node_id))

        elif decision == Decision.MUTATE:
            self.belief_level = min(1.0, self.belief_level + 0.10)
            # O modelo às vezes muta com `content` vazio: repassa sem alterar.
            if new_content.strip():
                self._broadcast(message.mutate(new_content, sender_id=self.node_id))
            else:
                self._broadcast(message.forward(self.node_id))

    def _broadcast(self, message: Message) -> None:
        """Envia mensagem para todos os vizinhos no grafo."""
        self.sent_messages.append(message)
        # Nós removidos por remove_hubs saem do grafo; evita NetworkXError.
        if self.node_id not in self.model.G:
            return
        neighbors = list(self.model.G.neighbors(self.node_id))
        for neighbor_id in neighbors:
            neighbor = self.model.agents_by_id.get(neighbor_id)
            if neighbor:
                neighbor.receive(message)
