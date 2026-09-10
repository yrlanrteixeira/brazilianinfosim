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


def _perfil(**kwargs) -> AgentProfile:
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

def test_ceticismo_aparece_no_prompt():
    assert "muito cético" in _perfil(skepticism=0.95).to_prompt_description()
    assert "pouco cético" in _perfil(skepticism=0.05).to_prompt_description()


def test_propensao_a_compartilhar_aparece_no_prompt():
    assert "compartilha facilmente" in _perfil(share_propensity=0.95).to_prompt_description()
    assert "raramente compartilha" in _perfil(share_propensity=0.05).to_prompt_description()


def test_vies_de_confirmacao_aparece_no_prompt():
    """Este é o parâmetro que era amostrado e NUNCA chegava ao LLM."""
    alto = _perfil(confirmation_bias=0.90).to_prompt_description()
    baixo = _perfil(confirmation_bias=0.10).to_prompt_description()
    assert alto != baixo, (
        "confirmation_bias não altera a descrição enviada ao LLM — "
        "o bug de acoplamento voltou."
    )


@pytest.mark.parametrize("campo,valores", [
    ("skepticism",        (0.05, 0.95)),
    ("share_propensity",  (0.05, 0.95)),
    ("confirmation_bias", (0.05, 0.95)),
])
def test_todo_parametro_comportamental_muda_o_prompt(campo, valores):
    """Varredura genérica: nenhum parâmetro pode ser inerte."""
    lo = _perfil(**{campo: valores[0]}).to_prompt_description()
    hi = _perfil(**{campo: valores[1]}).to_prompt_description()
    assert lo != hi, f"'{campo}' não tem efeito no prompt do LLM"


# ── 2. A intervenção precisa alterar os parâmetros de decisão ─────────────

def test_conversao_altera_parametros_comportamentais():
    p = _perfil()  # amplificador: pouco cético, compartilha muito
    antes = (p.skepticism, p.share_propensity, p.confirmation_bias)

    p.apply_factchecker_conversion()

    assert p.agent_type == AgentType.FACTCHECKER
    assert p.skepticism == FACTCHECKER_CONVERSION["skepticism"]
    assert p.share_propensity == FACTCHECKER_CONVERSION["share_propensity"]
    assert p.confirmation_bias == FACTCHECKER_CONVERSION["confirmation_bias"]
    assert (p.skepticism, p.share_propensity, p.confirmation_bias) != antes
    assert p.converted_by_intervention is True


def test_conversao_muda_a_descricao_enviada_ao_llm():
    """
    O teste central do bug: antes da correção esta asserção falhava, porque a
    descrição não dependia de nada que a intervenção alterava.
    """
    p = _perfil()
    antes = p.to_prompt_description()
    p.apply_factchecker_conversion()
    depois = p.to_prompt_description()

    assert antes != depois, (
        "A intervenção não alterou a descrição enviada ao LLM. "
        "A conversão em fact-checker voltou a ser um no-op comportamental."
    )
    assert "muito cético" in depois
    assert "raramente compartilha" in depois
    assert "verificar informações" in depois


def test_factchecker_nativo_tambem_recebe_instrucao_de_verificacao():
    """
    Antes da correção, nem os fact-checkers nativos (5% da população) eram
    descritos como verificadores ao LLM — o perfil inteiro era inerte.
    """
    nativo = _perfil(agent_type=AgentType.FACTCHECKER, skepticism=0.9,
                     share_propensity=0.6, confirmation_bias=0.1)
    assert "verificar informações" in nativo.to_prompt_description()


def test_agentes_nao_factchecker_nao_recebem_instrucao_de_verificacao():
    for t in (AgentType.AMPLIFIER, AgentType.SKEPTIC,
              AgentType.INFLUENCER, AgentType.INDIFFERENT):
        desc = _perfil(agent_type=t).to_prompt_description()
        assert "verificar informações" not in desc, f"tipo {t} não deveria verificar"


# ── 3. Reprodutibilidade dos perfis ───────────────────────────────────────

def test_geracao_de_perfil_e_deterministica_com_seed():
    a = generate_profile(seed=42)
    b = generate_profile(seed=42)
    assert a.to_prompt_description() == b.to_prompt_description()
    assert (a.skepticism, a.share_propensity, a.confirmation_bias) == \
           (b.skepticism, b.share_propensity, b.confirmation_bias)


def test_seeds_diferentes_geram_perfis_diferentes():
    perfis = {generate_profile(seed=s).to_prompt_description() for s in range(30)}
    assert len(perfis) > 1, "geração de perfis não está variando com a seed"
