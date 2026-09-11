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


def _profile(agent_type, skepticism, share, bias) -> AgentProfile:
    return AgentProfile(
        agent_type=agent_type, skepticism=skepticism, share_propensity=share,
        confirmation_bias=bias, social_capital=20,
        age_group=AgeGroup.ADULT, region=Region.SUDESTE,
        education=Education.MEDIO,
    )


AMPLIFIER = _profile(AgentType.AMPLIFIER, 0.10, 0.90, 0.80)
SKEPTIC = _profile(AgentType.SKEPTIC, 0.90, 0.10, 0.10)

MSG_A = "URGENTE: a vacina esta causando arritmia em idosos. Repasse!"
MSG_B = "ALERTA: quadrilha sequestrando criancas em vans brancas. Repasse!"


def _decide(client, profile, message, history=None):
    return client.decide(
        agent_description=profile.to_prompt_description(),
        message_content=message,
        history=history or [],
    )


# ── Regressão do colapso ──────────────────────────────────────────────────

def test_opposite_profiles_do_not_share_a_cache_entry(monkeypatch):
    """O bug em uma linha: amplificador e cético, mesma mensagem, davam hit."""
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, AMPLIFIER, MSG_A)
    _decide(client, SKEPTIC, MSG_A)
    assert len(fake.calls) == 2


def test_different_messages_do_not_share_a_cache_entry(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, SKEPTIC, MSG_A)
    _decide(client, SKEPTIC, MSG_B)
    assert len(fake.calls) == 2


def test_different_history_does_not_share_a_cache_entry(monkeypatch):
    """O histórico entra no prompt, então muda a situação e a chave."""
    client, fake = _client(monkeypatch, cache_mode="exact")
    _decide(client, SKEPTIC, MSG_A)
    _decide(client, SKEPTIC, MSG_A, history=[
        {"decision": Decision.IGNORE.value, "received": MSG_B, "sent": ""},
    ])
    assert len(fake.calls) == 2


def test_identical_situation_reuses_the_response(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="exact")
    first = _decide(client, SKEPTIC, MSG_A)
    second = _decide(client, SKEPTIC, MSG_A)
    assert len(fake.calls) == 1
    assert first == second
    assert client.stats["cache_hits"] == 1


# ── Modos ─────────────────────────────────────────────────────────────────

def test_off_mode_never_reuses(monkeypatch):
    client, fake = _client(monkeypatch, cache_mode="off")
    _decide(client, SKEPTIC, MSG_A)
    _decide(client, SKEPTIC, MSG_A)
    assert len(fake.calls) == 2
    assert client.stats["cache_hits"] == 0


def test_exact_is_the_default_mode(monkeypatch):
    monkeypatch.delenv("CACHE_MODE", raising=False)
    monkeypatch.delenv("ENABLE_CACHE", raising=False)
    client, _ = _client(monkeypatch)
    assert client.cache_mode == "exact"


def test_invalid_mode_fails_fast(monkeypatch):
    with pytest.raises(ValueError, match="cache_mode"):
        _client(monkeypatch, cache_mode="fuzzy")


def test_mode_shows_up_in_stats(monkeypatch):
    client, _ = _client(monkeypatch, cache_mode="exact")
    assert client.stats["cache_mode"] == "exact"


def test_enable_cache_false_still_disables(monkeypatch):
    """Compatibilidade: run_mutation.py e SimulationConfig usam enable_cache."""
    client, fake = _client(monkeypatch, enable_cache=False)
    _decide(client, SKEPTIC, MSG_A)
    _decide(client, SKEPTIC, MSG_A)
    assert client.cache_mode == "off"
    assert len(fake.calls) == 2


# ── O artefato, preservado para poder ser medido ──────────────────────────

def test_semantic_mode_still_collapses_opposite_profiles(monkeypatch):
    """O modo é mantido para medir o artefato: trava o comportamento dele."""
    pytest.importorskip("sentence_transformers")
    client, fake = _client(monkeypatch, cache_mode="semantic",
                           similarity_threshold=0.92)
    _decide(client, AMPLIFIER, MSG_A)
    _decide(client, SKEPTIC, MSG_A)
    assert len(fake.calls) == 1, "o colapso do cache semântico deixou de ocorrer"


def test_prompt_is_dominated_by_the_template():
    """A causa raiz, em números: template fixo maior que a parte variável."""
    description = AMPLIFIER.to_prompt_description()
    prompt = DECISION_PROMPT.format(
        agent_description=description, message=MSG_A, history_block=""
    )
    variable_part = len(description) + len(MSG_A)
    assert variable_part < len(prompt) - variable_part
