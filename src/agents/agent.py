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
    from ..llm.client import LLMClient


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

    def mutate(self, new_content: str) -> "Message":
        return Message(
            content=new_content,
            original_content=self.original_content,
            hops=self.hops + 1,
            sender_id=self.sender_id,
        )

    def forward(self, sender_id: int) -> "Message":
        return Message(
            content=self.content,
            original_content=self.original_content,
            hops=self.hops + 1,
            sender_id=sender_id,
        )


class InfoAgent(mesa.Agent):
    """
    Agente que representa um usuário de rede social brasileira.
    Recebe mensagens dos vizinhos e decide, via LLM, o que fazer.
    """

    def __init__(
        self,
        unique_id: int,
        model: mesa.Model,
        profile: AgentProfile,
        llm_client: "LLMClient",
    ):
        super().__init__(unique_id, model)
        self.profile = profile
        self.llm = llm_client

        # Estado dinâmico
        self.inbox: list[Message] = []
        self.sent_messages: list[Message] = []
        self.received_contents: set[str] = set()
        self.belief_level: float = 0.5   # 0=desacredita, 1=acredita totalmente
        self.interaction_history: list[dict] = []

    @property
    def has_seen_disinformation(self) -> bool:
        return len(self.received_contents) > 0

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
        import random
        self.received_contents.add(message.content)
        if random.random() < 0.10:   # 10% de chance de compartilhar
            self._broadcast(message.forward(self.unique_id))

    def _process_message(self, message: Message) -> None:
        self.received_contents.add(message.content)

        decision, new_content = self.llm.decide(
            agent_description=self.profile.to_prompt_description(),
            message_content=message.content,
            history=self.interaction_history[-5:],  # últimas 5 interações
        )

        self.interaction_history.append({
            "tick": self.model.schedule.time,
            "received": message.content,
            "decision": decision.value,
            "sent": new_content,
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
                sender_id=self.unique_id,
            )
            self._broadcast(refutation)

        elif decision == Decision.SHARE:
            self.belief_level = min(1.0, self.belief_level + 0.15)
            self._broadcast(message.forward(self.unique_id))

        elif decision == Decision.MUTATE:
            self.belief_level = min(1.0, self.belief_level + 0.10)
            mutated = message.mutate(new_content)
            self._broadcast(mutated)

    def _broadcast(self, message: Message) -> None:
        """Envia mensagem para todos os vizinhos no grafo."""
        self.sent_messages.append(message)
        neighbors = list(self.model.G.neighbors(self.unique_id))
        for neighbor_id in neighbors:
            neighbor = self.model.agents_by_id.get(neighbor_id)
            if neighbor:
                neighbor.receive(message)
