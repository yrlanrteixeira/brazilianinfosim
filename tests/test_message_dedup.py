"""
tests/test_message_dedup.py

Deduplicação de mensagens recebidas: uma exposição por boato por tick.

A dedup era por texto exato, e mutação gera texto novo: cada variante voltava
para a fila de quem já tinha visto a anterior. Medido sem LLM, com a mesma
rede e a mesma semente, mutação a cada 3 decisões custava 215.968 vezes o caso
sem mutação, com alcance idêntico.

Reexposição entre ticks é preservada de propósito: é ela que move belief_level
e é mecanismo central em contágio social.
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
        self.message_audit = []


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


def _rumor(content=ORIGINAL, parent=None):
    return Message(content=content, original_content=ORIGINAL, hops=0,
                   parent_content=parent)


def _next_tick(agent):
    agent.model.tick += 1
    agent.inbox.clear()


def test_first_exposure_is_accepted(agent):
    agent.receive(_rumor())
    assert len(agent.inbox) == 1


def test_same_rumor_twice_in_one_tick_is_ignored(agent):
    agent.receive(_rumor())
    agent.receive(_rumor())
    assert len(agent.inbox) == 1


def test_mutated_variant_in_the_same_tick_is_ignored(agent):
    """O caso que explodia: variante nova do mesmo boato voltava para a fila."""
    agent.receive(_rumor())
    agent.receive(_rumor(content="URGENTE: repasse, meu primo confirmou",
                         parent=ORIGINAL))
    assert len(agent.inbox) == 1


def test_reexposure_in_a_later_tick_is_accepted(agent):
    """Reexposição é mecanismo do modelo, não desperdício."""
    agent.receive(_rumor())
    _next_tick(agent)
    agent.receive(_rumor())
    assert len(agent.inbox) == 1


def test_refutation_gets_through_in_the_same_tick(agent):
    """Sem isto, a intervenção de fact-checkers vira no-op."""
    agent.receive(_rumor())
    agent.receive(Message(
        content="[REFUTAÇÃO] isso é falso, veja a fonte",
        original_content=ORIGINAL, hops=1, is_refutation=True,
    ))
    assert len(agent.inbox) == 2


def test_two_refutations_in_one_tick_count_once(agent):
    refutation = Message(content="[REFUTAÇÃO] isso é falso",
                         original_content=ORIGINAL, hops=1, is_refutation=True)
    agent.receive(refutation)
    agent.receive(refutation)
    assert len(agent.inbox) == 1


def test_another_rumor_is_a_separate_exposure(agent):
    agent.receive(_rumor())
    agent.receive(Message(content="ALERTA: outro boato", hops=0,
                          original_content="ALERTA: outro boato"))
    assert len(agent.inbox) == 2


def test_mutate_and_forward_keep_the_lineage():
    message = _rumor()
    assert message.mutate("versão alterada", sender_id=1).dedup_key == message.dedup_key
    assert message.forward(sender_id=2).dedup_key == message.dedup_key


def test_mutating_a_refutation_keeps_it_a_refutation():
    refutation = Message(content="[REFUTAÇÃO] falso", original_content=ORIGINAL,
                         is_refutation=True)
    assert refutation.mutate("falso, olha a fonte").is_refutation is True
