"""
tests/test_prompt_framing.py

O bloco que explica o marcador `[REFUTAÇÃO]` só pode aparecer quando a mensagem
recebida é uma refutação.

Ele entrava em toda decisão, inclusive na do boato, e avisava ao agente que
havia uma fake news circulando antes de ele escolher o que fazer. Na campanha
medida, o emissor refutava o próprio boato e a linhagem morria no primeiro nó.

Roda sem LLM: o provider é um fake.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from llm.client import LLMClient, REFUTATION_BLOCK

BOATO = "URGENTE: repasse isso agora"
CORRECAO = "[REFUTAÇÃO] isso é falso, veja a fonte"
RESPOSTA = json.dumps({"decision": "COMPARTILHAR", "content": ""})


class CapturingProvider:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str, max_tokens: int = 300, temperature: float = None) -> str:
        self.prompts.append(prompt)
        return RESPOSTA

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"


@pytest.fixture
def client(monkeypatch):
    provider = CapturingProvider()
    monkeypatch.setattr("llm.client.make_provider", lambda **_: provider)
    return LLMClient(cache_mode="off"), provider


def _decide(client, provider, message):
    client.decide(agent_description="Você é uma pessoa adulta.",
                  message_content=message, history=[])
    return provider.prompts[-1]


def test_the_rumor_prompt_does_not_mention_fake_news(client):
    prompt = _decide(*client, BOATO)
    assert REFUTATION_BLOCK.strip() not in prompt
    assert "fake news" not in prompt
    assert BOATO in prompt


def test_the_correction_prompt_keeps_the_explanation(client):
    prompt = _decide(*client, CORRECAO)
    assert REFUTATION_BLOCK.strip() in prompt


def test_the_two_prompts_differ_only_by_the_block(client):
    rumor = _decide(*client, BOATO)
    correction = _decide(*client, CORRECAO)
    assert correction.replace(REFUTATION_BLOCK, "").replace(CORRECAO, BOATO) == rumor


def test_the_block_is_not_glued_to_the_next_instruction(client):
    prompt = _decide(*client, CORRECAO)
    assert "dissonância cognitiva.\n\nCom base no seu perfil" in prompt
