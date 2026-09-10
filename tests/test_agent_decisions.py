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


def _perfil(tipo=AgentType.AMPLIFIER):
    return AgentProfile(
        agent_type=tipo, skepticism=0.1, share_propensity=0.9,
        confirmation_bias=0.8, social_capital=20,
        age_group=AgeGroup.ADULT, region=Region.SUDESTE,
        education=Education.MEDIO,
    )


def _monta(monkeypatch, decision, content):
    """Cria um agente ligado a um vizinho, com o LLM fake."""
    monkeypatch.setattr(InfoAgent, "__init__", _init_simples, raising=False)
    model = FakeModel()
    emissor = InfoAgent(model, _perfil(), FakeLLM(decision, content), 0)
    vizinho = InfoAgent(model, _perfil(), FakeLLM(Decision.IGNORE, ""), 1)
    model.register(emissor)
    model.register(vizinho)
    return emissor, vizinho


def _init_simples(self, model, profile, llm_client, node_id):
    """Evita mesa.Agent.__init__, que exige um Model de verdade."""
    self.model = model
    self.node_id = node_id
    self.profile = profile
    self.llm = llm_client
    self.inbox = []
    self.sent_messages = []
    self.received_contents = set()
    self.interaction_history = []
    self.belief_level = 0.5
    self.refusal_count = 0


ORIGINAL = "mensagem original"


def _mensagem():
    return Message(content=ORIGINAL, original_content=ORIGINAL, hops=0)


def test_mutacao_com_conteudo_vazio_nao_vira_mutacao(monkeypatch):
    emissor, vizinho = _monta(monkeypatch, Decision.MUTATE, "")
    emissor._process_message(_mensagem())

    assert emissor.mutated_messages == [], "mutação vazia não é mutação"
    assert len(emissor.sent_messages) == 1, "deve repassar, não engolir"
    assert emissor.sent_messages[0].content == ORIGINAL


def test_mutacao_so_com_espacos_tambem_nao_conta(monkeypatch):
    emissor, _ = _monta(monkeypatch, Decision.MUTATE, "   \n  ")
    emissor._process_message(_mensagem())
    assert emissor.mutated_messages == []
    assert emissor.sent_messages[0].content == ORIGINAL


def test_mutacao_com_conteudo_e_registrada(monkeypatch):
    novo = "olha o que estão dizendo, repassa"
    emissor, _ = _monta(monkeypatch, Decision.MUTATE, novo)
    emissor._process_message(_mensagem())

    assert len(emissor.mutated_messages) == 1
    m = emissor.mutated_messages[0]
    assert m.content == novo
    assert m.parent_content == ORIGINAL
    assert m.original_content == ORIGINAL
    assert m.hops == 1


def test_compartilhar_sem_alterar_nao_gera_mutacao(monkeypatch):
    emissor, _ = _monta(monkeypatch, Decision.SHARE, "")
    emissor._process_message(_mensagem())
    assert emissor.mutated_messages == []
    assert emissor.sent_messages[0].content == ORIGINAL
