"""
tests/test_agent_decisions.py

Testes de como o agente age sobre a decisão devolvida pelo LLM. O modelo às
vezes muta com `content` vazio, o que sem guarda propaga mensagem vazia e a
conta como mutação.

Rodam sem LLM e sem rede: o cliente é um fake e o modelo é um duplo mínimo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import networkx as nx
import pytest

from agents.agent import Decision, InfoAgent, Message
from agents.profiles import (
    AgentProfile, AgentType, AgeGroup, Region, Education,
)

ORIGINAL = "mensagem original"


class FakeLLM:
    def __init__(self, decision, content=""):
        self.decision = decision
        self.content = content

    def decide(self, agent_description, message_content, history):
        return self.decision, self.content, False


class FakeModel:
    """Duplo mínimo de mesa.Model: só o que InfoAgent usa."""

    def __init__(self):
        self.G = nx.Graph()
        self.G.add_edge(0, 1)
        self.agents_by_id = {}
        self.tick = 0
        import random
        self.rng = random.Random(42)

    def register(self, agent):
        self.agents_by_id[agent.node_id] = agent


def _profile(agent_type=AgentType.AMPLIFIER):
    return AgentProfile(
        agent_type=agent_type, skepticism=0.1, share_propensity=0.9,
        confirmation_bias=0.8, social_capital=20,
        age_group=AgeGroup.ADULT, region=Region.SUDESTE,
        education=Education.MEDIO,
    )


def _init_simple(self, model, profile, llm_client, node_id):
    """Evita mesa.Agent.__init__, que exige um Model de verdade."""
    self.model = model
    self.node_id = node_id
    self.profile = profile
    self.llm = llm_client
    self.inbox = []
    self.sent_messages = []
    self.seen_lineages = set()
    self._tick_seen = set()
    self._tick_seen_at = -1
    self.interaction_history = []
    self.belief_level = 0.5
    self.refusal_count = 0


def _build(monkeypatch, decision, content):
    """Cria um agente ligado a um vizinho, com o LLM fake."""
    monkeypatch.setattr(InfoAgent, "__init__", _init_simple, raising=False)
    model = FakeModel()
    sender = InfoAgent(model, _profile(), FakeLLM(decision, content), 0)
    neighbor = InfoAgent(model, _profile(), FakeLLM(Decision.IGNORE, ""), 1)
    model.register(sender)
    model.register(neighbor)
    return sender, neighbor


def _message():
    return Message(content=ORIGINAL, original_content=ORIGINAL, hops=0)


def test_mutation_with_empty_content_is_not_a_mutation(monkeypatch):
    sender, _ = _build(monkeypatch, Decision.MUTATE, "")
    sender._process_message(_message())

    assert sender.mutated_messages == [], "mutação vazia não é mutação"
    assert len(sender.sent_messages) == 1, "deve repassar, não engolir"
    assert sender.sent_messages[0].content == ORIGINAL


def test_mutation_with_only_whitespace_does_not_count(monkeypatch):
    sender, _ = _build(monkeypatch, Decision.MUTATE, "   \n  ")
    sender._process_message(_message())
    assert sender.mutated_messages == []
    assert sender.sent_messages[0].content == ORIGINAL


def test_mutation_with_content_is_recorded(monkeypatch):
    new_content = "olha o que estão dizendo, repassa"
    sender, _ = _build(monkeypatch, Decision.MUTATE, new_content)
    sender._process_message(_message())

    assert len(sender.mutated_messages) == 1
    mutated = sender.mutated_messages[0]
    assert mutated.content == new_content
    assert mutated.parent_content == ORIGINAL
    assert mutated.original_content == ORIGINAL
    assert mutated.hops == 1


def test_sharing_unchanged_does_not_create_a_mutation(monkeypatch):
    sender, _ = _build(monkeypatch, Decision.SHARE, "")
    sender._process_message(_message())
    assert sender.mutated_messages == []
    assert sender.sent_messages[0].content == ORIGINAL


def test_refutation_is_flagged_as_such(monkeypatch):
    """A refutação precisa ser linhagem à parte para escapar da dedup."""
    sender, _ = _build(monkeypatch, Decision.REFUTE, "isso é falso")
    sender._process_message(_message())

    sent = sender.sent_messages[0]
    assert sent.is_refutation is True
    assert sent.content.startswith("[REFUTAÇÃO]")
