"""
tests/test_contrasts.py

Contrastes pareados por condição.

Dois pontos decidem a validade da tabela: só a família de intervenção pode ser
filtrada por tratamento aplicado, porque nas demais a flag é falsa por
construção; e o agrupamento do bootstrap é a seed estrutural, não a execução.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from contrasts import (
    applied_only, bonferroni_level, escape, groups, load, num, table, to_tex,
)


def _pair(family="intervention", condition="remove_hubs_t0", seed="1",
          legacy=-10.0, strict=0.0, applied="True"):
    return {"family": family, "condition": condition, "seed_index": seed,
            "lineage_reach_difference_pp": str(legacy),
            "reach_difference_pp_strict": str(strict),
            "intervention_applied": applied}


# ── Filtro de tratamento aplicado ─────────────────────────────────────────

def test_only_the_intervention_family_is_filtered_by_applied():
    """Nas outras famílias não há tratamento a aplicar, e filtrar esvaziaria."""
    ceticos = [_pair(family="skeptics", condition="fraction_1", applied="False")]
    assert len(applied_only("skeptics", ceticos)) == 1


def test_unapplied_interventions_leave_the_effect():
    group = [_pair(applied="True"), _pair(applied="False")]
    assert len(applied_only("intervention", group)) == 1


def test_discarded_pairs_are_counted_in_the_table():
    lines = table([_pair(seed="1", applied="True"), _pair(seed="2", applied="True"),
                   _pair(seed="3", applied="False")])
    assert lines[0]["n"] == 2
    assert lines[0]["descartados"] == 1


def test_a_condition_with_nothing_applied_is_left_out():
    assert table([_pair(applied="False")]) == []


# ── Agrupamento ───────────────────────────────────────────────────────────

def test_pairs_group_by_family_and_condition():
    pairs = [_pair(condition="remove_hubs_t0"), _pair(condition="remove_hubs_t2"),
             _pair(family="skeptics", condition="fraction_1", applied="False")]
    assert len(groups(pairs)) == 3


def test_the_bootstrap_groups_by_structural_seed():
    """Mesma seed em duas execuções não dá dois grupos independentes."""
    same_seed = table([_pair(seed="7", strict=-5.0), _pair(seed="7", strict=-15.0)])
    assert same_seed[0]["n"] == 2
    assert same_seed[0]["seeds"] == 1


def test_bonferroni_raises_the_level_by_the_number_of_conditions():
    assert bonferroni_level(1) == 0.95
    assert round(bonferroni_level(22), 5) == round(1 - 0.05 / 22, 5)
    assert bonferroni_level(22) > bonferroni_level(2)


def test_the_adjusted_interval_is_never_narrower_than_the_unadjusted():
    """Ajustar por multiplicidade alarga o intervalo; estreitar seria o erro."""
    pairs = [_pair(seed=str(i), strict=float(i - 10)) for i in range(20)]
    largo = table(pairs, level=bonferroni_level(22))[0]
    estreito = table(pairs, level=0.95)[0]
    assert largo["estrito_ic95_baixo"] <= estreito["estrito_ic95_baixo"]
    assert largo["estrito_ic95_alto"] >= estreito["estrito_ic95_alto"]


def test_both_metrics_appear_side_by_side():
    lines = table([_pair(seed="1", legacy=-72.0, strict=0.0),
                   _pair(seed="2", legacy=-72.0, strict=0.0)])
    assert lines[0]["antigo_media"] == -72.0
    assert lines[0]["estrito_media"] == 0.0


# ── Saída LaTeX ───────────────────────────────────────────────────────────

def test_underscores_are_escaped_once():
    assert escape("remove_hubs_t0") == r"remove\_hubs\_t0"


def test_a_group_without_an_interval_prints_a_dash_instead_of_nan():
    assert num(float("nan")) == "--"
    assert num(-12.5) == "-12.50"


def test_the_tex_table_is_closed_and_escaped():
    out = to_tex(table([_pair(seed="1"), _pair(seed="2")]))
    assert out.startswith("%")
    assert r"\begin{tabular}" in out and r"\end{tabular}" in out
    assert r"remove\_hubs\_t0" in out
    assert r"\_t0}" in out, "a condição vai em texttt escapado"


def test_the_tex_table_states_its_own_interval_level():
    """Tabela solta no artigo tem que dizer de que nível é o intervalo."""
    out = to_tex(table([_pair(seed="1"), _pair(seed="2")]), level=bonferroni_level(22))
    assert "99.77%" in out


def test_a_family_change_draws_a_rule():
    """Um do cabeçalho, mais um por troca de família."""
    pairs = [_pair(seed="1"), _pair(seed="2"),
             _pair(family="skeptics", condition="fraction_1", seed="1", applied="False"),
             _pair(family="skeptics", condition="fraction_1", seed="2", applied="False")]
    assert to_tex(table(pairs)).count(r"\midrule") == 2


# ── Entrada ───────────────────────────────────────────────────────────────

def test_pairs_without_the_corrected_column_are_skipped(tmp_path):
    (tmp_path / "paired_effects_corrigido.csv").write_text(
        "family,condition,seed_index,lineage_reach_difference_pp,"
        "reach_difference_pp_strict,intervention_applied\n"
        "intervention,remove_hubs_t0,1,-10,0,True\n"
        "intervention,remove_hubs_t0,2,-10,,True\n", encoding="utf-8")
    assert len(load(tmp_path)) == 1
