"""
tests/test_analisar_corrigido.py

Tabelas do artigo a partir do recálculo.

O que importa aqui é o agrupamento: execuções que compartilham a seed não são
independentes, e um intervalo que as trate como independentes fica estreito
demais. Os testes fixam o agrupamento, o limiar do emissor sozinho e a
reprodutibilidade do bootstrap.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from analisar_corrigido import (
    artefato, cluster_totals, clustered_ci, conferir_total, controls, load,
    so_emissor, summarize, tabela_alcances, tabela_artefato,
)


def _row(seed="s1", strict=2.0, legacy=40.0, agents=50, intervention="",
         stimulus="saude", correction=60.0, ambiguous=10.0, upper=12.0):
    return {
        "seed": seed, "n_agents": str(agents), "intervention": intervention,
        "stimulus_id": stimulus, "reach_strict_pct": str(strict),
        "reach_legacy_pct": str(legacy), "correction_strict_pct": str(correction),
        "reach_ambiguous_pct": str(ambiguous), "reach_upper_pct": str(upper),
    }


# ── Desfechos ─────────────────────────────────────────────────────────────

def test_artefato_is_what_the_old_count_added_beyond_the_rumor():
    assert artefato(_row(strict=7.71, legacy=37.35)) == 37.35 - 7.71


def test_only_the_emitter_is_one_exposure_in_the_population():
    assert so_emissor(_row(strict=2.0, agents=50)) == 1.0
    assert so_emissor(_row(strict=4.0, agents=50)) == 0.0
    assert so_emissor(_row(strict=1.0, agents=100)) == 1.0


def test_the_threshold_follows_the_population_size():
    """Com 20 agentes, uma exposição é 5%, não 2%."""
    assert so_emissor(_row(strict=5.0, agents=20)) == 1.0
    assert so_emissor(_row(strict=2.0, agents=20)) == 1.0
    assert so_emissor(_row(strict=10.0, agents=20)) == 0.0


# ── Agrupamento ───────────────────────────────────────────────────────────

def test_rows_of_the_same_seed_collapse_into_one_cluster():
    rows = [_row(seed="a", strict=1), _row(seed="a", strict=3), _row(seed="b", strict=5)]
    totals = cluster_totals(rows, lambda r: float(r["reach_strict_pct"]))
    assert sorted(totals) == [(4.0, 2), (5.0, 1)]


def test_summary_reports_how_many_seeds_support_it():
    rows = [_row(seed="a"), _row(seed="a"), _row(seed="b")]
    linha = summarize(rows, so_emissor, "x")
    assert linha["n"] == 3
    assert linha["seeds"] == 2


def test_an_empty_group_does_not_invent_numbers():
    assert summarize([], so_emissor, "x")["n"] == 0


# ── Bootstrap ─────────────────────────────────────────────────────────────

def test_identical_clusters_leave_no_room_for_an_interval():
    totals = [(10.0, 1)] * 8
    assert clustered_ci(totals, resamples=200) == (10.0, 10.0)


def test_the_interval_brackets_the_point_estimate():
    totals = [(0.0, 1), (10.0, 1), (20.0, 1), (30.0, 1), (40.0, 1), (50.0, 1)]
    baixo, alto = clustered_ci(totals, resamples=2000)
    assert baixo < 25.0 < alto


def test_the_bootstrap_is_reproducible_and_depends_on_the_seed():
    totals = [(0.0, 1), (10.0, 2), (20.0, 1), (30.0, 3), (40.0, 1)]
    assert clustered_ci(totals, seed=1, resamples=500) == clustered_ci(totals, seed=1, resamples=500)
    assert clustered_ci(totals, seed=1, resamples=500) != clustered_ci(totals, seed=2, resamples=500)


def test_a_single_cluster_cannot_produce_an_interval():
    baixo, alto = clustered_ci([(10.0, 1)])
    assert math.isnan(baixo) and math.isnan(alto)


def test_clusters_weigh_by_their_size_not_by_their_count():
    """Razão de somas: um grupo com muitas execuções pesa mais na estimativa."""
    totals = [(100.0, 10), (0.0, 1)]
    baixo, alto = clustered_ci(totals, resamples=2000)
    assert baixo >= 0.0 and alto <= 10.0


# ── Seleção ───────────────────────────────────────────────────────────────

def test_controls_are_the_rows_without_intervention():
    rows = [_row(intervention=""), _row(intervention="factcheckers_hub")]
    assert len(controls(rows)) == 1


def test_reach_table_falls_back_to_all_rows_when_there_is_no_control():
    linhas = tabela_alcances([_row(intervention="factcheckers_hub")])
    assert linhas[0]["n"] == 1


def test_artifact_table_has_both_primary_outcomes():
    linhas = tabela_artefato([_row(seed="a"), _row(seed="b")])
    assert len(linhas) == 2
    assert linhas[0]["media"] == 38.0


def test_load_skips_runs_the_recompute_could_not_measure(tmp_path):
    (tmp_path / "runs_corrigido.csv").write_text(
        "seed,reach_strict_pct\ns1,2.0\ns2,\n", encoding="utf-8")
    assert len(load(tmp_path)) == 1


def test_a_partial_copy_stops_the_analysis_instead_of_reporting_it():
    """Cópia defasada de campanha gera tabela com cara de completa."""
    with pytest.raises(SystemExit, match="Esperava 1723 e carreguei 900|Esperava 1723"):
        conferir_total([_row()] * 900, esperado=1723)


def test_without_a_declared_total_the_check_stays_out_of_the_way():
    conferir_total([_row()] * 900, esperado=0)
