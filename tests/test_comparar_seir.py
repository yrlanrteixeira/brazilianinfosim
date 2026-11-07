"""
tests/test_comparar_seir.py

Comparação pareada entre o alcance dos agentes e o de referências SIR e SEIR.

Dois pontos decidem se a comparação vale: a divisão entre ajuste e avaliação tem
de ser por seed, porque execuções da mesma seed compartilham grafo e população;
e a referência tem de rodar no mesmo grafo e na mesma origem da execução, senão
a diferença medida inclui estrutura em vez de só dinâmica.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from comparar_seir import (
    alcance_referencia, avaliar, dividir_seeds, horizonte_por_condicao, ks,
    melhor_ajuste, so_emissor,
)


def _caso(seed=1, llm=2.0, n=10, horizonte=5):
    """Caminho simples: alcance da referência cresce com a transmissão."""
    return {"id": f"r{seed}", "seed": seed, "n_agents": n, "source": 0,
            "edges": [(i, i + 1) for i in range(n - 1)],
            "horizonte": horizonte, "llm": llm}


# ── Divisão entre ajuste e avaliação ──────────────────────────────────────

def test_the_split_is_by_seed_and_disjoint():
    ajuste, avaliacao = dividir_seeds(["3", "1", "2", "4"])
    assert ajuste & avaliacao == set()
    assert ajuste | avaliacao == {"1", "2", "3", "4"}


def test_the_same_seed_never_falls_on_both_sides():
    """Duas execuções da mesma seed têm de ficar do mesmo lado."""
    ajuste, avaliacao = dividir_seeds(["7", "7", "8", "8"])
    assert ("7" in ajuste) != ("7" in avaliacao)
    assert ("8" in ajuste) != ("8" in avaliacao)


def test_the_split_is_deterministic():
    assert dividir_seeds(["1", "2", "3"]) == dividir_seeds(["3", "2", "1"])


# ── Horizonte ─────────────────────────────────────────────────────────────

def test_the_horizon_comes_from_the_longest_run_of_the_condition():
    rows = [{"condition": "control", "ticks_run": "3"},
            {"condition": "control", "ticks_run": "12"},
            {"condition": "double_horizon", "ticks_run": "24"}]
    assert horizonte_por_condicao(rows) == {"control": 12, "double_horizon": 24}


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


# ── Referência no mesmo grafo ─────────────────────────────────────────────

def test_zero_transmission_leaves_the_reference_at_the_source():
    assert alcance_referencia(_caso(n=10), 0.0, 0.0, latente=False) == 10.0


def test_full_transmission_spreads_along_the_path():
    """Caminho de 10 nós, transmissão 1, horizonte 5: a frente avança por tick."""
    alcance = alcance_referencia(_caso(n=10, horizonte=5), 1.0, 0.0, latente=False)
    assert alcance > 10.0


def test_the_latent_state_slows_the_front():
    rapido = alcance_referencia(_caso(n=20, horizonte=4), 1.0, 0.0, latente=False)
    lento = alcance_referencia(_caso(n=20, horizonte=4), 1.0, 0.0, latente=True)
    assert lento < rapido


def test_the_reference_is_reproducible_for_the_same_seed():
    a = alcance_referencia(_caso(seed=5, n=20), 0.3, 0.2, latente=False)
    b = alcance_referencia(_caso(seed=5, n=20), 0.3, 0.2, latente=False)
    assert a == b


# ── Ajuste e avaliação ────────────────────────────────────────────────────

def test_the_fit_picks_the_grid_point_closest_to_the_target():
    """Alvo preso no emissor: a transmissão escolhida tem de ser a menor."""
    casos = [_caso(seed=i, llm=10.0, n=10) for i in range(8)]
    transmissao, _, distancia = melhor_ajuste(casos, latente=False)
    assert transmissao == min(t for t in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.80))
    assert distancia == 0.0


def test_the_evaluation_reports_both_sides_of_the_comparison():
    casos = [_caso(seed=i, llm=10.0, n=10) for i in range(6)]
    linha = avaliar(casos, 0.02, 0.1, latente=False)
    assert linha["modelo"] == "SIR"
    assert linha["media_llm"] == 10.0
    assert "media_referencia" in linha and "ks" in linha


def test_only_at_the_emitter_follows_the_population_size():
    assert so_emissor([2.0, 2.0, 50.0], n_agents=50) == round(2 / 3, 3)
    assert so_emissor([10.0], n_agents=10) == 1.0
