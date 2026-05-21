"""
tests/test_profiles.py
Testes unitários dos perfis de agentes — sem dependência de LLM ou API.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.profiles import (
    AgentType, generate_profile, BRAZIL_DISTRIBUTION
)


def test_generate_profile_returns_valid():
    profile = generate_profile(seed=42)
    assert 0.0 <= profile.skepticism <= 1.0
    assert 0.0 <= profile.share_propensity <= 1.0
    assert 0.0 <= profile.confirmation_bias <= 1.0
    assert profile.social_capital > 0


def test_generate_profile_respects_type():
    for agent_type in AgentType:
        profile = generate_profile(agent_type=agent_type, seed=1)
        assert profile.agent_type == agent_type


def test_distribution_sums_to_one():
    total = sum(BRAZIL_DISTRIBUTION.values())
    assert abs(total - 1.0) < 1e-6


def test_prompt_description_is_portuguese():
    profile = generate_profile(seed=42)
    desc = profile.to_prompt_description()
    assert "Brasil" in desc or "região" in desc


def test_determinism():
    p1 = generate_profile(seed=99)
    p2 = generate_profile(seed=99)
    assert p1.agent_type == p2.agent_type
    assert p1.skepticism == p2.skepticism


if __name__ == "__main__":
    test_generate_profile_returns_valid()
    test_generate_profile_respects_type()
    test_distribution_sums_to_one()
    test_prompt_description_is_portuguese()
    test_determinism()
    print("✅ Todos os testes passaram!")
