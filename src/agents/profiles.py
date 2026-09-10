"""
agents/profiles.py
Definição dos perfis comportamentais dos agentes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random


class AgentType(str, Enum):
    AMPLIFIER   = "amplificador"    # compartilha tudo sem questionar
    SKEPTIC     = "cetico"          # pede fontes, questiona
    INFLUENCER  = "influenciador"   # alta conectividade, grande alcance
    FACTCHECKER = "fact_checker"    # tenta corrigir ativamente
    INDIFFERENT = "indiferente"     # raramente interage


class AgeGroup(str, Enum):
    YOUNG  = "jovem"        # 18-30
    ADULT  = "adulto"       # 31-50
    SENIOR = "idoso"        # 51+


class Region(str, Enum):
    NORTE     = "norte"
    NORDESTE  = "nordeste"
    CENTROOESTE = "centro_oeste"
    SUDESTE   = "sudeste"
    SUL       = "sul"


class Education(str, Enum):
    FUNDAMENTAL = "fundamental"
    MEDIO       = "medio"
    SUPERIOR    = "superior"


# ── Parâmetros aplicados na conversão para fact-checker (intervenção) ──────
# A intervenção precisa alterar os parâmetros que REALMENTE guiam a decisão,
# e não apenas o rótulo agent_type.
FACTCHECKER_CONVERSION = dict(
    skepticism=0.90,
    share_propensity=0.05,
    confirmation_bias=0.10,
)


@dataclass
class AgentProfile:
    """Perfil comportamental estático de um agente."""

    agent_type: AgentType

    # Dimensões comportamentais [0.0, 1.0]
    skepticism: float           # ceticismo epistêmico
    share_propensity: float     # propensão a compartilhar
    confirmation_bias: float    # viés de confirmação
    social_capital: int         # número esperado de conexões

    # Contexto demográfico brasileiro
    age_group: AgeGroup
    region: Region
    education: Education
    uses_whatsapp: bool = True

    # Marca se este agente foi convertido por uma intervenção (para análise)
    converted_by_intervention: bool = False

    def apply_factchecker_conversion(self) -> None:
        """
        Converte o agente em fact-checker de forma efetiva.

        Antes desta correção a intervenção alterava apenas `agent_type`, que não
        é lido por `to_prompt_description()` — logo o LLM continuava recebendo a
        mesma descrição de antes e a intervenção era um no-op comportamental.
        Agora a conversão altera os três parâmetros que guiam a decisão (e que
        também compõem a chave do cache semântico).
        """
        self.agent_type        = AgentType.FACTCHECKER
        self.skepticism        = FACTCHECKER_CONVERSION["skepticism"]
        self.share_propensity  = FACTCHECKER_CONVERSION["share_propensity"]
        self.confirmation_bias = FACTCHECKER_CONVERSION["confirmation_bias"]
        self.converted_by_intervention = True

    def to_prompt_description(self) -> str:
        """Gera descrição em português para injetar no prompt do LLM."""
        edu_map = {
            Education.FUNDAMENTAL: "ensino fundamental",
            Education.MEDIO:       "ensino médio",
            Education.SUPERIOR:    "ensino superior",
        }
        age_map = {
            AgeGroup.YOUNG:  "jovem (18-30 anos)",
            AgeGroup.ADULT:  "adulto (31-50 anos)",
            AgeGroup.SENIOR: "idoso (51+ anos)",
        }
        skepticism_label = (
            "muito cético" if self.skepticism > 0.7
            else "moderadamente cético" if self.skepticism > 0.4
            else "pouco cético"
        )
        share_label = (
            "compartilha facilmente" if self.share_propensity > 0.7
            else "compartilha com moderação" if self.share_propensity > 0.4
            else "raramente compartilha"
        )
        # O viés de confirmação era amostrado e nunca chegava ao LLM.
        bias_label = (
            "tende a aceitar sem questionar aquilo que confirma o que já acredita"
            if self.confirmation_bias > 0.6
            else "avalia informações com relativa imparcialidade"
            if self.confirmation_bias > 0.35
            else "procura evidências contrárias antes de aceitar uma informação"
        )
        # O papel de fact-checker é um repertório de comportamento (verificar e
        # corrigir) que os parâmetros numéricos não expressam. Sem isto, nem os
        # fact-checkers nativos eram descritos como tal ao LLM.
        role_note = (
            " Você tem o hábito de verificar informações em fontes confiáveis "
            "antes de repassar qualquer coisa e de publicar correções quando "
            "identifica conteúdo falso circulando."
            if self.agent_type == AgentType.FACTCHECKER else ""
        )
        return (
            f"Você é uma pessoa {age_map[self.age_group]}, "
            f"com {edu_map[self.education]}, da região {self.region.value} do Brasil. "
            f"Você é {skepticism_label} em relação a informações que recebe. "
            f"Você {share_label} conteúdo nas redes sociais. "
            f"Você {bias_label}. "
            f"{'Usa WhatsApp frequentemente.' if self.uses_whatsapp else ''}"
            f"{role_note}"
        )


# ── Distribuição padrão calibrada para o contexto brasileiro ──────────────
BRAZIL_DISTRIBUTION = {
    AgentType.AMPLIFIER:   0.25,
    AgentType.INDIFFERENT: 0.40,
    AgentType.SKEPTIC:     0.20,
    AgentType.INFLUENCER:  0.10,
    AgentType.FACTCHECKER: 0.05,
}

# Parâmetros comportamentais por tipo (média, desvio)
PROFILE_PARAMS = {
    AgentType.AMPLIFIER:   dict(skepticism=(0.15, 0.10), share_propensity=(0.85, 0.10), confirmation_bias=(0.75, 0.10)),
    AgentType.INDIFFERENT: dict(skepticism=(0.50, 0.15), share_propensity=(0.15, 0.10), confirmation_bias=(0.50, 0.15)),
    AgentType.SKEPTIC:     dict(skepticism=(0.80, 0.10), share_propensity=(0.30, 0.15), confirmation_bias=(0.25, 0.10)),
    AgentType.INFLUENCER:  dict(skepticism=(0.40, 0.15), share_propensity=(0.70, 0.15), confirmation_bias=(0.55, 0.15)),
    AgentType.FACTCHECKER: dict(skepticism=(0.90, 0.05), share_propensity=(0.60, 0.15), confirmation_bias=(0.10, 0.05)),
}


def _clamp(value: float, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, value))


def generate_profile(agent_type: Optional[AgentType] = None, seed: Optional[int] = None) -> AgentProfile:
    """
    Gera um perfil aleatório calibrado para o contexto brasileiro.
    Se agent_type=None, sorteia conforme BRAZIL_DISTRIBUTION.
    """
    rng = random.Random(seed)

    if agent_type is None:
        types, weights = zip(*BRAZIL_DISTRIBUTION.items())
        agent_type = rng.choices(types, weights=weights, k=1)[0]

    params = PROFILE_PARAMS[agent_type]

    def sample(mean, std): return _clamp(rng.gauss(mean, std))

    social_capital_map = {
        AgentType.INFLUENCER:  rng.randint(50, 200),
        AgentType.AMPLIFIER:   rng.randint(10, 50),
        AgentType.FACTCHECKER: rng.randint(10, 40),
        AgentType.SKEPTIC:     rng.randint(5, 30),
        AgentType.INDIFFERENT: rng.randint(2, 20),
    }

    return AgentProfile(
        agent_type=agent_type,
        skepticism=sample(*params["skepticism"]),
        share_propensity=sample(*params["share_propensity"]),
        confirmation_bias=sample(*params["confirmation_bias"]),
        social_capital=social_capital_map[agent_type],
        age_group=rng.choice(list(AgeGroup)),
        region=rng.choices(
            list(Region),
            weights=[0.08, 0.27, 0.08, 0.42, 0.15],  # distribuição IBGE
            k=1
        )[0],
        education=rng.choices(
            list(Education),
            weights=[0.40, 0.37, 0.23],  # distribuição IBGE
            k=1
        )[0],
        uses_whatsapp=rng.random() < 0.92,  # 92% dos brasileiros
    )
