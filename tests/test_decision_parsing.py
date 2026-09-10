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
from llm.client import LLMClient


class FakeProvider:
    """Devolve as respostas cruas da fila, na ordem."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.temperaturas = []
        self.calls = 0

    def complete(self, prompt: str, max_tokens: int = 300,
                 temperature: float = None) -> str:
        self.calls += 1
        self.temperaturas.append(temperature)
        return self.respostas.pop(0)

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"


def _client(monkeypatch, respostas, **kwargs):
    fake = FakeProvider(respostas)
    monkeypatch.setattr("llm.client.make_provider", lambda **_: fake)
    return LLMClient(cache_mode="off", **kwargs), fake


def _raw(decision, content=""):
    return json.dumps({"decision": decision, "content": content})


def _decide(client):
    return client.decide(agent_description="perfil", message_content="msg",
                         history=[])


# ── Casamento tolerante de label ──────────────────────────────────────────

@pytest.mark.parametrize("digitado,esperado", [
    ("COM_PARTILHAR", Decision.SHARE),
    ("QUESTRONAR", Decision.QUESTION),
    ("QUESTOINAR", Decision.QUESTION),
    ("compartilhar", Decision.SHARE),
    ("  IGNORAR  ", Decision.IGNORE),
    ("COMPARTILHAR_COM_COMENTARIO", Decision.MUTATE),
])
def test_label_com_ruido_e_recuperado(monkeypatch, digitado, esperado):
    client, _ = _client(monkeypatch, [_raw(digitado, "texto")])
    decision, _, refused = _decide(client)
    assert decision == esperado
    assert refused is False


def test_label_irrecuperavel_vira_ignorar_e_conta_erro(monkeypatch):
    client, _ = _client(monkeypatch, [_raw("BANANA", "texto")])
    decision, _, _ = _decide(client)
    assert decision == Decision.IGNORE
    assert client.stats["parse_errors"] == 1


def test_recuperacao_nao_inventa_decisao_distante(monkeypatch):
    """Tolerância corrige typo, não adivinha intenção."""
    client, _ = _client(monkeypatch, [_raw("REFUTAR_TUDO_SEMPRE", "x")])
    decision, _, _ = _decide(client)
    assert decision == Decision.IGNORE
    assert client.stats["parse_errors"] == 1


def test_json_malformado_continua_sendo_erro_de_parse(monkeypatch):
    client, _ = _client(monkeypatch, ["isto nao e json"])
    decision, _, refused = _decide(client)
    assert decision == Decision.IGNORE
    assert refused is False
    assert client.stats["parse_errors"] == 1


def test_recusa_continua_sendo_detectada(monkeypatch):
    client, _ = _client(monkeypatch, ["Desculpe, não posso ajudar com isso."])
    decision, _, refused = _decide(client)
    assert decision == Decision.IGNORE
    assert refused is True
    assert client.stats["refusals"] == 1


# ── Temperatura ───────────────────────────────────────────────────────────

def test_temperatura_chega_ao_provider(monkeypatch):
    client, fake = _client(monkeypatch, [_raw(Decision.SHARE.value)],
                           temperature=1.0)
    _decide(client)
    assert fake.temperaturas == [1.0]


def test_temperatura_aparece_nas_stats(monkeypatch):
    client, _ = _client(monkeypatch, [], temperature=0.7)
    assert client.stats["temperature"] == 0.7


def test_temperatura_default_preserva_o_valor_do_tcc_1(monkeypatch):
    """0,3 é o valor do TCC I: mudar o default quebra a comparação."""
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    client, _ = _client(monkeypatch, [])
    assert client.temperature == 0.3
