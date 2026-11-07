"""
tests/test_decision_parsing.py

Testes do parsing da decisão e da temperatura. Em temperatura alta o modelo
erra a grafia do label (`COM_PARTILHAR`, `QUESTRONAR`), e sem casamento
tolerante cada typo vira IGNORAR silencioso.

Rodam sem LLM: o provider é um fake.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from agents.agent import Decision
from llm.client import InvalidLLMResponse, LLMClient


class FakeProvider:
    """Devolve as respostas cruas da fila, na ordem."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.temperatures = []
        self.calls = 0

    def complete(self, prompt: str, max_tokens: int = 300,
                 temperature: float = None) -> str:
        self.calls += 1
        self.temperatures.append(temperature)
        return self.responses.pop(0)

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"


def _client(monkeypatch, responses, **kwargs):
    fake = FakeProvider(responses)
    monkeypatch.setattr("llm.client.make_provider", lambda **_: fake)
    return LLMClient(cache_mode="off", **kwargs), fake


def _raw(decision, content=""):
    return json.dumps({"decision": decision, "content": content})


def _decide(client):
    return client.decide(agent_description="perfil", message_content="msg",
                         history=[])


# ── Casamento tolerante de label ──────────────────────────────────────────

@pytest.mark.parametrize("written,expected", [
    ("COM_PARTILHAR", Decision.SHARE),
    ("QUESTRONAR", Decision.QUESTION),
    ("QUESTOINAR", Decision.QUESTION),
    ("compartilhar", Decision.SHARE),
    ("  IGNORAR  ", Decision.IGNORE),
    ("COMPARTILHAR_COM_COMENTARIO", Decision.MUTATE),
])
def test_noisy_label_is_recovered(monkeypatch, written, expected):
    client, _ = _client(monkeypatch, [_raw(written, "texto")])
    decision, _, refused = _decide(client)
    assert decision == expected
    assert refused is False


def test_unrecoverable_label_raises_and_counts_an_error(monkeypatch):
    client, _ = _client(monkeypatch, [_raw("BANANA", "texto")])
    with pytest.raises(InvalidLLMResponse):
        _decide(client)
    assert client.stats["parse_errors"] == 1


def test_recovery_does_not_invent_a_distant_decision(monkeypatch):
    """Tolerância corrige typo, não adivinha intenção."""
    client, _ = _client(monkeypatch, [_raw("REFUTAR_TUDO_SEMPRE", "x")])
    with pytest.raises(InvalidLLMResponse):
        _decide(client)
    assert client.stats["parse_errors"] == 1


def test_malformed_json_is_still_a_parse_error(monkeypatch):
    client, _ = _client(monkeypatch, ["isto nao e json"])
    with pytest.raises(InvalidLLMResponse):
        _decide(client)
    assert client.stats["parse_errors"] == 1


@pytest.mark.parametrize("raw", [
    "[]", "null", "42", '"texto"', '{}',
    _raw("REFUTAR", ""), _raw("COMPARTILHAR_COM_COMENTARIO", "  "),
    _raw("COMPARTILHAR", None), _raw("COMPARTILHAR", []), _raw(123, "texto"),
])
def test_invalid_schema_never_becomes_agent_behavior(monkeypatch, raw):
    client, _ = _client(monkeypatch, [raw])
    with pytest.raises(InvalidLLMResponse):
        _decide(client)
    assert client.stats["parse_errors"] == 1
    assert client.stats["backend_errors"] == 0


def test_refusal_is_still_detected(monkeypatch):
    client, _ = _client(monkeypatch, ["Desculpe, não posso ajudar com isso."])
    decision, _, refused = _decide(client)
    assert decision == Decision.IGNORE
    assert refused is True
    assert client.stats["refusals"] == 1


# ── Temperatura ───────────────────────────────────────────────────────────

def test_temperature_reaches_the_provider(monkeypatch):
    client, fake = _client(monkeypatch, [_raw(Decision.SHARE.value)],
                           temperature=1.0)
    _decide(client)
    assert fake.temperatures == [1.0]


def test_temperature_shows_up_in_stats(monkeypatch):
    client, _ = _client(monkeypatch, [], temperature=0.7)
    assert client.stats["temperature"] == 0.7


def test_default_temperature_keeps_the_tcc1_value(monkeypatch):
    """0,3 é o valor do TCC I: mudar o default quebra a comparação."""
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    client, _ = _client(monkeypatch, [])
    assert client.temperature == 0.3
