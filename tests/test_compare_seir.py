"""
tests/test_compare_seir.py

Comparação pareada entre o alcance dos agentes e o de referências SIR e SEIR.

Dois pontos decidem se a comparação vale: a divisão entre fit e avaliação tem
de ser por seed, porque execuções da mesma seed compartilham graph e população;
e a referência tem de rodar no mesmo graph e na mesma origem da execução, senão
a diferença medida inclui estrutura em vez de só dinâmica.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from compare_seir import (
    reference_reach, evaluate, split_seeds, horizon_by_condition, ks,
    best_fit, emitter_only,
)


def _case(seed=1, llm=2.0, n=10, horizon=5):
    """Caminho simples: alcance da referência cresce com a transmissão."""
    return {"id": f"r{seed}", "seed": seed, "n_agents": n, "source": 0,
            "edges": [(i, i + 1) for i in range(n - 1)],
            "horizon": horizon, "llm": llm}


# ── Divisão entre fit e avaliação ──────────────────────────────────────

def test_the_split_is_by_seed_and_disjoint():
    fit, evaluation = split_seeds(["3", "1", "2", "4"])
    assert fit & evaluation == set()
    assert fit | evaluation == {"1", "2", "3", "4"}


def test_the_same_seed_never_falls_on_both_sides():
    """Duas execuções da mesma seed têm de ficar do mesmo lado."""
    fit, evaluation = split_seeds(["7", "7", "8", "8"])
    assert ("7" in fit) != ("7" in evaluation)
    assert ("8" in fit) != ("8" in evaluation)


def test_the_split_is_deterministic():
    assert split_seeds(["1", "2", "3"]) == split_seeds(["3", "2", "1"])


# ── Horizonte ─────────────────────────────────────────────────────────────

def test_the_horizon_comes_from_the_longest_run_of_the_condition():
    rows = [{"condition": "control", "ticks_run": "3"},
            {"condition": "control", "ticks_run": "12"},
            {"condition": "double_horizon", "ticks_run": "24"}]
    assert horizon_by_condition(rows) == {"control": 12, "double_horizon": 24}


# ── Distância entre distribuições ─────────────────────────────────────────

def test_identical_distributions_have_no_distance():
    assert ks([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_disjoint_distributions_have_the_maximum_distance():
    assert ks([0.0, 0.0], [100.0, 100.0]) == 1.0


def test_the_distance_catches_shape_not_only_mean():
    """Mesma média, formas opostas: a distância tem de acusar."""
    concentrada = [50.0] * 10
    extrema = [0.0] * 5 + [100.0] * 5
    assert sum(concentrada) == sum(extrema)
    assert ks(concentrada, extrema) >= 0.5


def test_an_empty_sample_does_not_fake_a_distance():
    assert math.isnan(ks([], [1.0]))


# ── Referência no mesmo graph ─────────────────────────────────────────────

def test_zero_transmission_leaves_the_reference_at_the_source():
    assert reference_reach(_case(n=10), 0.0, 0.0, latent=False) == 10.0


def test_full_transmission_spreads_along_the_path():
    """Caminho de 10 nós, transmissão 1, horizonte 5: a frente avança por tick."""
    alcance = reference_reach(_case(n=10, horizon=5), 1.0, 0.0, latent=False)
    assert alcance > 10.0


def test_the_latent_state_slows_the_front():
    rapido = reference_reach(_case(n=20, horizon=4), 1.0, 0.0, latent=False)
    lento = reference_reach(_case(n=20, horizon=4), 1.0, 0.0, latent=True)
    assert lento < rapido


def test_the_reference_is_reproducible_for_the_same_seed():
    a = reference_reach(_case(seed=5, n=20), 0.3, 0.2, latent=False)
    b = reference_reach(_case(seed=5, n=20), 0.3, 0.2, latent=False)
    assert a == b


# ── Ajuste e avaliação ────────────────────────────────────────────────────

def test_the_fit_picks_the_grid_point_closest_to_the_target():
    """Alvo preso no emissor: a transmissão escolhida tem de ser a menor."""
    cases = [_case(seed=i, llm=10.0, n=10) for i in range(8)]
    transmission, _, distance = best_fit(cases, latent=False)
    assert transmission == min(t for t in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.80))
    assert distance == 0.0


def test_the_evaluation_reports_both_sides_of_the_comparison():
    cases = [_case(seed=i, llm=10.0, n=10) for i in range(6)]
    line = evaluate(cases, 0.02, 0.1, latent=False)
    assert line["modelo"] == "SIR"
    assert line["media_llm"] == 10.0
    assert "media_referencia" in line and "ks" in line


def test_only_at_the_emitter_follows_the_population_size():
    assert emitter_only([2.0, 2.0, 50.0], n_agents=50) == round(2 / 3, 3)
    assert emitter_only([10.0], n_agents=10) == 1.0
