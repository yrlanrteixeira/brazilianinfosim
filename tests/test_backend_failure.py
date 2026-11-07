"""
tests/test_backend_failure.py

Falha de backend não pode virar decisão de agente.

Com o Ollama fora do ar, toda chamada caía no `except Exception` genérico,
era contada como erro de parse e devolvia IGNORAR. A campanha seguia rodando e
gravando runs, produzindo dado fabricado sem nenhum erro visível.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from agents.agent import Decision
from llm.client import BackendUnavailable, ComputeBudgetExceeded, InvalidLLMResponse, LLMClient, MAX_BACKEND_ATTEMPTS


class FlakyProvider:
    """Levanta o que estiver na fila; string na fila é resposta bem sucedida."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.prompts = []

    def complete(self, prompt: str, max_tokens: int = 300,
                 temperature: float = 0.3) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"


def _client(monkeypatch, script):
    fake = FlakyProvider(script)
    monkeypatch.setattr("llm.client.make_provider", lambda **_: fake)
    return LLMClient(cache_mode="off"), fake


def _decide(client):
    return client.decide(agent_description="perfil", message_content="msg",
                         history=[])


def _ok(decision=Decision.SHARE.value):
    return json.dumps({"decision": decision, "content": ""})


class ConnectionDown(Exception):
    """Fica no lugar de openai.APIConnectionError, sem depender do SDK."""


def test_backend_error_is_not_counted_as_parse_error(monkeypatch):
    client, _ = _client(monkeypatch, [ConnectionDown("recusou"), _ok()])
    _decide(client)
    assert client.stats["parse_errors"] == 0
    assert client.stats["backend_errors"] == 1


def test_isolated_backend_error_does_not_abort(monkeypatch):
    """Uma falha pontual não pode derrubar uma campanha de horas."""
    client, fake = _client(monkeypatch, [ConnectionDown("blip"), _ok()])
    decision, _, _ = _decide(client)
    assert decision == Decision.SHARE
    assert fake.calls == 2
    assert len(set(fake.prompts)) == 1


def test_consecutive_backend_errors_abort_loudly(monkeypatch):
    script = [ConnectionDown("caiu")] * MAX_BACKEND_ATTEMPTS
    client, _ = _client(monkeypatch, script)

    with pytest.raises(BackendUnavailable):
        _decide(client)


def test_a_success_resets_the_streak(monkeypatch):
    script = ([ConnectionDown("x")] * (MAX_BACKEND_ATTEMPTS - 1) + [_ok()]) * 2
    client, _ = _client(monkeypatch, script)

    for _ in range(2):
        _decide(client)

    assert client.stats["backend_errors"] == (MAX_BACKEND_ATTEMPTS - 1) * 2


def test_parse_error_does_not_count_as_backend(monkeypatch):
    client, _ = _client(monkeypatch, ["isto nao e json"])
    with pytest.raises(InvalidLLMResponse):
        _decide(client)
    assert client.stats["parse_errors"] == 1
    assert client.stats["backend_errors"] == 0


def test_parse_error_aborts_instead_of_fabricating_a_decision(monkeypatch):
    client, _ = _client(monkeypatch, ["lixo"])
    with pytest.raises(InvalidLLMResponse) as error:
        _decide(client)
    assert error.value.raw_response == "lixo"


def test_backend_errors_show_up_in_stats(monkeypatch):
    client, _ = _client(monkeypatch, [])
    assert "backend_errors" in client.stats


def test_expired_deadline_makes_no_provider_call(monkeypatch):
    client, fake = _client(monkeypatch, [])
    client.deadline = 0
    with pytest.raises(ComputeBudgetExceeded):
        _decide(client)
    assert fake.calls == 0


def test_audit_preserves_prompt_response_and_context(monkeypatch):
    client, _ = _client(monkeypatch, [_ok()])
    client.audit_context = {"node_id": 7, "tick": 3}
    _decide(client)
    event = client.audit_log[0]
    assert event["node_id"] == 7 and event["tick"] == 3
    assert event["raw_response"] == _ok()
    assert "perfil" in event["prompt"]
