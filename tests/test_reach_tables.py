"""
tests/test_reach_tables.py

Tabelas do artigo a partir do recálculo.

O que importa aqui é o agrupamento: execuções que compartilham a seed não são
independentes, e um intervalo que as trate como independentes fica estreito
demais. Os testes fixam o agrupamento, o limiar do emissor sozinho e a
reprodutibilidade do bootstrap.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import pytest

from reach_tables import (
    artifact, artifact_table, check_total, cluster_totals, clustered_ci,
    controls, emitter_only, load, reach_table, summarize, table_by_group,
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
    assert artifact(_row(strict=7.71, legacy=37.35)) == 37.35 - 7.71


def test_only_the_emitter_is_one_exposure_in_the_population():
    assert emitter_only(_row(strict=2.0, agents=50)) == 1.0
    assert emitter_only(_row(strict=4.0, agents=50)) == 0.0
    assert emitter_only(_row(strict=1.0, agents=100)) == 1.0


def test_the_threshold_follows_the_population_size():
    """Com 20 agentes, uma exposição é 5%, não 2%."""
    assert emitter_only(_row(strict=5.0, agents=20)) == 1.0
    assert emitter_only(_row(strict=2.0, agents=20)) == 1.0
    assert emitter_only(_row(strict=10.0, agents=20)) == 0.0


# ── Agrupamento ───────────────────────────────────────────────────────────

def test_rows_of_the_same_seed_collapse_into_one_cluster():
    rows = [_row(seed="a", strict=1), _row(seed="a", strict=3), _row(seed="b", strict=5)]
    totals = cluster_totals(rows, lambda r: float(r["reach_strict_pct"]))
    assert sorted(totals) == [(4.0, 2), (5.0, 1)]


def test_summary_reports_how_many_seeds_support_it():
    rows = [_row(seed="a"), _row(seed="a"), _row(seed="b")]
    line = summarize(rows, emitter_only, "x")
    assert line["n"] == 3
    assert line["seeds"] == 2


def test_an_empty_group_does_not_invent_numbers():
    assert summarize([], emitter_only, "x")["n"] == 0


# ── Bootstrap ─────────────────────────────────────────────────────────────

def test_identical_clusters_leave_no_room_for_an_interval():
    totals = [(10.0, 1)] * 8
    assert clustered_ci(totals, resamples=200) == (10.0, 10.0)


def test_the_interval_brackets_the_point_estimate():
    totals = [(0.0, 1), (10.0, 1), (20.0, 1), (30.0, 1), (40.0, 1), (50.0, 1)]
    low, high = clustered_ci(totals, resamples=2000)
    assert low < 25.0 < high


def test_the_bootstrap_is_reproducible_and_depends_on_the_seed():
    totals = [(0.0, 1), (10.0, 2), (20.0, 1), (30.0, 3), (40.0, 1)]
    assert clustered_ci(totals, seed=1, resamples=500) == clustered_ci(totals, seed=1, resamples=500)
    assert clustered_ci(totals, seed=1, resamples=500) != clustered_ci(totals, seed=2, resamples=500)


def test_a_single_cluster_cannot_produce_an_interval():
    low, high = clustered_ci([(10.0, 1)])
    assert math.isnan(low) and math.isnan(high)


def test_clusters_weigh_by_their_size_not_by_their_count():
    """Razão de somas: um grupo com muitas execuções pesa mais na estimativa."""
    totals = [(100.0, 10), (0.0, 1)]
    low, high = clustered_ci(totals, resamples=2000)
    assert low >= 0.0 and high <= 10.0


# ── Seleção ───────────────────────────────────────────────────────────────

def test_controls_are_the_rows_without_intervention():
    rows = [_row(intervention=""), _row(intervention="factcheckers_hub")]
    assert len(controls(rows)) == 1


def test_the_named_control_condition_wins_over_the_none_intervention():
    """A campanha grava `none` em toda condição sem intervenção de rede. Só a
    condição de referência é controle."""
    rows = [dict(_row(intervention="none"), condition="control"),
            dict(_row(intervention="none"), condition="fraction_0.4"),
            dict(_row(intervention="none"), condition="cetico")]
    assert [r["condition"] for r in controls(rows)] == ["control"]


def test_without_a_named_control_it_falls_back_to_no_intervention():
    rows = [dict(_row(intervention="none"), condition="cetico"),
            dict(_row(intervention="remove_hubs"), condition="remove_hubs_t0")]
    assert len(controls(rows)) == 1


def test_reach_table_falls_back_to_all_rows_and_says_so():
    lines = reach_table([_row(intervention="factcheckers_hub")])
    assert lines[0]["n"] == 1
    assert lines[0]["escopo"] == "todas as execucoes"


def test_reach_table_marks_when_it_describes_the_controls():
    lines = reach_table([dict(_row(intervention="none"), condition="control")])
    assert lines[0]["escopo"] == "controles"


def test_artifact_table_has_both_primary_outcomes():
    lines = artifact_table([_row(seed="a"), _row(seed="b")])
    assert len(lines) == 2
    assert lines[0]["media"] == 38.0


def test_grouping_covers_every_value_in_three_measures():
    rows = [dict(_row(), topology=t) for t in ("erdos_renyi", "watts_strogatz")]
    lines = table_by_group(rows, "topology")
    assert len(lines) == 6, "duas topologias vezes estrito, marca e só o emissor"
    assert any("erdos_renyi: alcance estrito" == l["medida"] for l in lines)


def test_the_filter_restricts_the_grouping_to_one_family():
    """A fração de céticos só faz sentido dentro da família que a varia."""
    rows = [dict(_row(), family="skeptics", condition="fraction_1"),
            dict(_row(), family="topology", condition="erdos_renyi")]
    lines = table_by_group(rows, "condition", lambda r: r["family"] == "skeptics")
    assert {l["medida"].split(":")[0] for l in lines} == {"fraction_1"}


def test_grouping_an_empty_selection_yields_nothing():
    assert table_by_group([_row()], "topology", lambda r: False) == []


def test_load_skips_runs_the_recompute_could_not_measure(tmp_path):
    (tmp_path / "runs_corrigido.csv").write_text(
        "seed,reach_strict_pct\ns1,2.0\ns2,\n", encoding="utf-8")
    assert len(load(tmp_path)) == 1


def test_a_partial_copy_stops_the_analysis_instead_of_reporting_it():
    """Cópia defasada de campanha gera tabela com cara de completa."""
    with pytest.raises(SystemExit, match="Esperava 1723 e carreguei 900|Esperava 1723"):
        check_total([_row()] * 900, expected=1723)


def test_without_a_declared_total_the_check_stays_out_of_the_way():
    check_total([_row()] * 900, expected=0)
