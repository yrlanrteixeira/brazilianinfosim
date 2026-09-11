"""
tests/test_coupling.py

Testes de regressão para o bug de acoplamento.

O bug: a intervenção alterava `profile.agent_type`, mas a decisão do agente
(e a chave do cache semântico) é guiada pelo texto de
`to_prompt_description()`, que não lia `agent_type` nem `confirmation_bias`.
Resultado: "promover" um agente a fact-checker era um no-op comportamental.

Rodam sem LLM e sem rede.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from agents.profiles import (
    AgentProfile, AgentType, AgeGroup, Region, Education,
    generate_profile, FACTCHECKER_CONVERSION,
)


def _profile(**kwargs) -> AgentProfile:
    """Perfil base para os testes, sobrescrevível por kwargs."""
    base = dict(
        agent_type=AgentType.AMPLIFIER,
        skepticism=0.10,
        share_propensity=0.90,
        confirmation_bias=0.80,
        social_capital=30,
        age_group=AgeGroup.ADULT,
        region=Region.SUDESTE,
        education=Education.MEDIO,
        uses_whatsapp=True,
    )
    base.update(kwargs)
    return AgentProfile(**base)


# ── 1. Todo parâmetro comportamental precisa aparecer no prompt ────────────

def test_skepticism_shows_up_in_the_prompt():
    assert "muito cético" in _profile(skepticism=0.95).to_prompt_description()
    assert "pouco cético" in _profile(skepticism=0.05).to_prompt_description()


def test_share_propensity_shows_up_in_the_prompt():
    assert "compartilha facilmente" in _profile(share_propensity=0.95).to_prompt_description()
    assert "raramente compartilha" in _profile(share_propensity=0.05).to_prompt_description()


def test_confirmation_bias_shows_up_in_the_prompt():
    """Este é o parâmetro que era amostrado e NUNCA chegava ao LLM."""
    high = _profile(confirmation_bias=0.90).to_prompt_description()
    low = _profile(confirmation_bias=0.10).to_prompt_description()
    assert high != low, (
        "confirmation_bias não altera a descrição enviada ao LLM — "
        "o bug de acoplamento voltou."
    )


@pytest.mark.parametrize("field,values", [
    ("skepticism",        (0.05, 0.95)),
    ("share_propensity",  (0.05, 0.95)),
    ("confirmation_bias", (0.05, 0.95)),
])
def test_every_behavioral_parameter_changes_the_prompt(field, values):
    """Varredura genérica: nenhum parâmetro pode ser inerte."""
    lo = _profile(**{field: values[0]}).to_prompt_description()
    hi = _profile(**{field: values[1]}).to_prompt_description()
    assert lo != hi, f"'{field}' não tem efeito no prompt do LLM"


# ── 2. A intervenção precisa alterar os parâmetros de decisão ─────────────

def test_conversion_changes_the_behavioral_parameters():
    p = _profile()  # amplificador: pouco cético, compartilha muito
    before = (p.skepticism, p.share_propensity, p.confirmation_bias)

    p.apply_factchecker_conversion()

    assert p.agent_type == AgentType.FACTCHECKER
    assert p.skepticism == FACTCHECKER_CONVERSION["skepticism"]
    assert p.share_propensity == FACTCHECKER_CONVERSION["share_propensity"]
    assert p.confirmation_bias == FACTCHECKER_CONVERSION["confirmation_bias"]
    assert (p.skepticism, p.share_propensity, p.confirmation_bias) != before
    assert p.converted_by_intervention is True


def test_conversion_changes_the_description_sent_to_the_llm():
    """
    O teste central do bug: antes da correção esta asserção falhava, porque a
    descrição não dependia de nada que a intervenção alterava.
    """
    p = _profile()
    before = p.to_prompt_description()
    p.apply_factchecker_conversion()
    after = p.to_prompt_description()

    assert before != after, (
        "A intervenção não alterou a descrição enviada ao LLM. "
        "A conversão em fact-checker voltou a ser um no-op comportamental."
    )
    assert "muito cético" in after
    assert "raramente compartilha" in after
    assert "verificar informações" in after


def test_native_factchecker_also_gets_the_verification_instruction():
    """
    Antes da correção, nem os fact-checkers nativos (5% da população) eram
    descritos como verificadores ao LLM — o perfil inteiro era inerte.
    """
    native = _profile(agent_type=AgentType.FACTCHECKER, skepticism=0.9,
                     share_propensity=0.6, confirmation_bias=0.1)
    assert "verificar informações" in native.to_prompt_description()


def test_non_factchecker_agents_do_not_get_the_verification_instruction():
    for t in (AgentType.AMPLIFIER, AgentType.SKEPTIC,
              AgentType.INFLUENCER, AgentType.INDIFFERENT):
        desc = _profile(agent_type=t).to_prompt_description()
        assert "verificar informações" not in desc, f"tipo {t} não deveria verificar"


# ── 3. Reprodutibilidade dos perfis ───────────────────────────────────────

def test_profile_generation_is_deterministic_with_a_seed():
    a = generate_profile(seed=42)
    b = generate_profile(seed=42)
    assert a.to_prompt_description() == b.to_prompt_description()
    assert (a.skepticism, a.share_propensity, a.confirmation_bias) == \
           (b.skepticism, b.share_propensity, b.confirmation_bias)


def test_different_seeds_generate_different_profiles():
    perfis = {generate_profile(seed=s).to_prompt_description() for s in range(30)}
    assert len(perfis) > 1, "geração de perfis não está variando com a seed"
