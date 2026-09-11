"""
tests/test_cascade_cost.py

Trava o custo da cascata quando há mutação.

Sem este teste a regressão volta calada: ela não quebra resultado nenhum, só
multiplica o número de chamadas ao LLM até a campanha ficar inviável.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from agents.agent import Decision
from network.topology import Topology
import simulation.engine as engine
from simulation.engine import InfoSimModel, SimulationConfig

N_AGENTS = 30
MAX_TICKS = 12


class CountingLLM:
    """Compartilha sempre, mutando a cada `mutate_every` decisões."""

    provider = type("P", (), {"name": "fake", "model": "fake"})()
    temperature = 1.0
    cache_mode = "off"

    def __init__(self, mutate_every=0):
        self.stats = {"api_calls": 0, "cache_hits": 0}
        self.mutate_every = mutate_every
        self.calls = 0

    def decide(self, agent_description, message_content, history):
        self.stats["api_calls"] += 1
        self.calls += 1
        if self.mutate_every and self.calls % self.mutate_every == 0:
            return Decision.MUTATE, f"versão alterada {self.calls}", False
        return Decision.SHARE, "", False


def _run(monkeypatch, mutate_every):
    llm = CountingLLM(mutate_every=mutate_every)
    monkeypatch.setattr(engine, "LLMClient", lambda **_: llm)
    config = SimulationConfig(
        n_agents=N_AGENTS, topology=Topology.SCALE_FREE, max_ticks=MAX_TICKS,
        seed=123, inject_at="influencer",
    )
    result = InfoSimModel(config).run()
    return llm.calls, result


def test_mutation_does_not_blow_up_the_call_count(monkeypatch):
    """
    Antes da correção, mutação a cada 3 decisões custava 215.968 vezes o caso
    sem mutação, com o mesmo alcance.
    """
    baseline, _ = _run(monkeypatch, mutate_every=0)
    heavy, _ = _run(monkeypatch, mutate_every=3)

    assert heavy <= baseline * 2, (
        f"mutação multiplicou as chamadas: {baseline} -> {heavy}"
    )


def test_call_count_stays_within_the_theoretical_ceiling(monkeypatch):
    """Cada agente decide no máximo uma vez por exposição por tick."""
    calls, _ = _run(monkeypatch, mutate_every=3)
    assert calls <= N_AGENTS * MAX_TICKS


def test_mutation_does_not_change_the_reach(monkeypatch):
    """O custo explodia sem entregar propagação nenhuma a mais."""
    _, sem_mutacao = _run(monkeypatch, mutate_every=0)
    _, com_mutacao = _run(monkeypatch, mutate_every=3)

    assert com_mutacao.final_reach_pct == pytest.approx(
        sem_mutacao.final_reach_pct, abs=10.0
    )


def test_mutations_are_still_collected(monkeypatch):
    """A correção não pode zerar o insumo de QP3."""
    _, result = _run(monkeypatch, mutate_every=3)
    assert len(result.mutations) > 0
