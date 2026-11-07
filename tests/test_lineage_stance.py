"""
tests/test_lineage_stance.py

Classificação da linhagem medida, separada do canal de entrega.

A flag `is_refutation` alternava a cada refutação e também decidia se a
exposição contava como boato. Com isso, a refutação de uma refutação voltava a
ser contada como alcance da desinformação, mesmo quando o texto corrigia o
boato. O canal continua alternando, porque é ele que entrega a correção a quem
já viu o boato; quem classifica agora é `refutation_depth`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import networkx as nx
import pytest

from agents.agent import InfoAgent, Message
from agents.profiles import (
    AgentProfile, AgentType, AgeGroup, Region, Education,
)

ORIGINAL = "URGENTE: repasse isso agora"


def _profile(agent_type=AgentType.AMPLIFIER):
    return AgentProfile(
        agent_type=agent_type, skepticism=0.1, share_propensity=0.9,
        confirmation_bias=0.8, social_capital=20,
        age_group=AgeGroup.ADULT, region=Region.SUDESTE,
        education=Education.MEDIO,
    )


class FakeModel:
    def __init__(self):
        self.G = nx.Graph()
        self.G.add_edge(0, 1)
        self.agents_by_id = {}
        self.tick = 0


def _init_simple(self, model, profile, llm_client, node_id):
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


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr(InfoAgent, "__init__", _init_simple, raising=False)
    return InfoAgent(FakeModel(), _profile(), None, 0)


def _rumor():
    return Message(content=ORIGINAL, original_content=ORIGINAL, hops=0)


def _refute(message, content):
    """Reproduz a construção que o agente faz ao decidir REFUTAR."""
    return Message(
        content=content,
        original_content=message.original_content,
        hops=message.hops + 1,
        parent_content=message.content,
        is_refutation=not message.is_refutation,
        parent_is_refutation=message.is_refutation,
        refutation_depth=message.refutation_depth + 1,
    )


def test_refuting_a_refutation_does_not_return_to_the_rumor():
    correction = _refute(_rumor(), "[REFUTAÇÃO] isso é falso")
    contested = _refute(correction, "não é bem assim")
    assert (correction.refutation_depth, contested.refutation_depth) == (1, 2)
    assert contested.is_refutation is False, "o canal precisa alternar para entregar"


def test_contested_correction_is_not_counted_as_rumor(agent):
    contested = _refute(_refute(_rumor(), "[REFUTAÇÃO] isso é falso"), "não é bem assim")
    agent.receive(contested)
    assert not agent.has_seen_disinformation
    assert not agent.has_seen_correction
    assert agent.has_seen_ambiguous


def test_rumor_and_correction_keep_their_classification(agent):
    agent.receive(_rumor())
    agent.receive(_refute(_rumor(), "[REFUTAÇÃO] isso é falso"))
    assert agent.has_seen_disinformation
    assert agent.has_seen_correction
    assert not agent.has_seen_ambiguous


def test_a_refutation_built_directly_starts_at_depth_one():
    assert Message("[REFUTAÇÃO] falso", ORIGINAL, is_refutation=True).refutation_depth == 1


def test_forward_and_mutate_preserve_the_depth():
    contested = _refute(_refute(_rumor(), "[REFUTAÇÃO] falso"), "não é bem assim")
    assert contested.forward(sender_id=1).refutation_depth == 2
    assert contested.mutate("outra versão", sender_id=1).refutation_depth == 2


def test_delivery_channel_is_unchanged(agent):
    """A profundidade mede, não entrega: mexer no dedup mudaria as dinâmicas."""
    contested = _refute(_refute(_rumor(), "[REFUTAÇÃO] falso"), "não é bem assim")
    assert contested.dedup_key == _rumor().dedup_key
    agent.receive(_rumor())
    agent.receive(contested)
    assert len(agent.inbox) == 1


def test_mutation_index_ignores_descendants_of_refutations(agent):
    contested = _refute(_refute(_rumor(), "[REFUTAÇÃO] falso"), "não é bem assim")
    agent.sent_messages = [
        _rumor().mutate("versão alterada", sender_id=0),
        contested.mutate("outra versão", sender_id=0),
    ]
    assert [m.content for m in agent.mutated_messages] == ["versão alterada"]
