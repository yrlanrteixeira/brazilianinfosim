"""
tests/test_cache.py

Testes do cache de decisões. Regressão do bug em que a chave era o embedding
do prompt inteiro: o template dominava a similaridade e perfis opostos
compartilhavam a mesma resposta.

Rodam sem LLM: o provider é um fake que conta chamadas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from agents.agent import Decision
from agents.profiles import (
    AgentProfile, AgentType, AgeGroup, Region, Education,
)
from llm.client import LLMClient, DECISION_PROMPT


class FakeProvider:
    """Provider que conta chamadas e responde COMPARTILHAR sempre."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt: str, max_tokens: int = 300,
                 temperature: float = 0.3) -> str:
        self.calls.append(prompt)
        return json.dumps({
            "decision": Decision.SHARE.value,
            "content": f"resposta {len(self.calls)}",
        })

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"


def _client(monkeypatch, **kwargs) -> tuple[LLMClient, FakeProvider]:
    fake = FakeProvider()
    monkeypatch.setattr("llm.client.make_provider", lambda **_: fake)
    return LLMClient(**kwargs), fake


def _perfil(tipo, skepticism, share, bias) -> AgentProfile:
    return AgentProfile(
        agent_type=tipo, skepticism=skepticism, share_propensity=share,
        confirmation_bias=bias, social_capital=20,
        age_group=AgeGroup.ADULT, region=Region.SUDESTE,
        education=Education.MEDIO,
    )


AMPLIFICADOR = _perfil(AgentType.AMPLIFIER, 0.10, 0.90, 0.80)
CETICO = _perfil(AgentType.SKEPTIC, 0.90, 0.10, 0.10)

MSG_A = "URGENTE: a vacina esta causando arritmia em idosos. Repasse!"
MSG_B = "ALERTA: quadrilha sequestrando criancas em vans brancas. Repasse!"


def _decide(client, perfil, msg, history=None):
    return client.decide(
        agent_description=perfil.to_prompt_description(),
        message_content=msg,
        history=history or [],
    )


# ── Regressão do colapso ──────────────────────────────────────────────────

def test_perfis_opostos_nao_compartilham_entrada_de_cache(monkeypatch):
    """O bug em uma linha: amplificador e cético, mesma mensagem, davam hit."""
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, AMPLIFICADOR, MSG_A)
    _decide(client, CETICO, MSG_A)
    assert len(fake.calls) == 2


def test_mensagens_diferentes_nao_compartilham_entrada_de_cache(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, CETICO, MSG_A)
    _decide(client, CETICO, MSG_B)
    assert len(fake.calls) == 2


def test_historico_diferente_nao_compartilha_entrada_de_cache(monkeypatch):
    """O histórico entra no prompt, então muda a situação e a chave."""
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, CETICO, MSG_A)
    _decide(client, CETICO, MSG_A, history=[
        {"decision": Decision.IGNORE.value, "received": MSG_B, "sent": ""},
    ])
    assert len(fake.calls) == 2


def test_situacao_identica_reusa_a_resposta(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="exact")
    primeira = _decide(client, CETICO, MSG_A)
    segunda = _decide(client, CETICO, MSG_A)
    assert len(fake.calls) == 1
    assert primeira == segunda
    assert client.stats["cache_hits"] == 1


# ── Modos ─────────────────────────────────────────────────────────────────

def test_modo_off_nunca_reusa(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="off")
    _decide(client, CETICO, MSG_A)
    _decide(client, CETICO, MSG_A)
    assert len(fake.calls) == 2
    assert client.stats["cache_hits"] == 0


def test_modo_exact_e_o_default(monkeypatch):
    monkeypatch.delenv("CACHE_MODE", raising=False)
    monkeypatch.delenv("ENABLE_CACHE", raising=False)
    client, _ = _client(monkeypatch)
    assert client.cache_mode == "exact"


def test_modo_invalido_falha_rapido(monkeypatch):
    with pytest.raises(ValueError, match="cache_mode"):
        _client(monkeypatch, cache_mode="fuzzy")


def test_modo_aparece_nas_stats(monkeypatch):
    client, _ = _client(monkeypatch, cache_mode="exact")
    assert client.stats["cache_mode"] == "exact"


def test_enable_cache_false_ainda_desliga(monkeypatch):
    """Compatibilidade: run_mutation.py e SimulationConfig usam enable_cache."""
    client, fake = _client(monkeypatch, enable_cache=False)
    _decide(client, CETICO, MSG_A)
    _decide(client, CETICO, MSG_A)
    assert client.cache_mode == "off"
    assert len(fake.calls) == 2


# ── O artefato, preservado para poder ser medido ──────────────────────────

def test_modo_semantic_ainda_colapsa_perfis_opostos(monkeypatch):
    """O modo é mantido para medir o artefato: trava o comportamento dele."""
    pytest.importorskip("sentence_transformers")
    client, fake = _client(monkeypatch, cache_mode="semantic",
                           similarity_threshold=0.92)
    _decide(client, AMPLIFICADOR, MSG_A)
    _decide(client, CETICO, MSG_A)
    assert len(fake.calls) == 1, "o colapso do cache semântico deixou de ocorrer"


def test_prompt_e_dominado_pelo_template():
    """A causa raiz, em números: template fixo maior que a parte variável."""
    descricao = AMPLIFICADOR.to_prompt_description()
    prompt = DECISION_PROMPT.format(
        agent_description=descricao, message=MSG_A, history_block=""
    )
    parte_variavel = len(descricao) + len(MSG_A)
    assert parte_variavel < len(prompt) - parte_variavel
