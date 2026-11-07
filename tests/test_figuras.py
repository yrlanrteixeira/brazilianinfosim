"""
tests/test_figuras.py

Preparo dos dados das figuras. O desenho em si não é testado; o que erra em
silêncio é a agregação por trás dele.

A distribuição acumulada é testada porque é ela que mostra o degrau em 2%, onde
se concentram as execuções em que o boato não saiu do emissor. Binagem errada
esconderia justamente o achado.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from figuras import ESTIMULOS, ecdf, load_runs, media_por_estimulo


def _run(estimulo="health_dna_a", legacy=63.0, strict=2.0):
    return {"stimulus_id": estimulo, "reach_legacy_pct": str(legacy),
            "reach_strict_pct": str(strict)}


# ── Distribuição acumulada ────────────────────────────────────────────────

def test_the_ecdf_ends_at_one_and_is_sorted():
    x, y = ecdf([40.0, 2.0, 2.0, 100.0])
    assert x == [2.0, 2.0, 40.0, 100.0]
    assert y[-1] == 1.0


def test_a_repeated_value_shows_up_as_a_step():
    """Metade das execuções em 2% tem que virar degrau de 0,5 nessa altura."""
    x, y = ecdf([2.0, 2.0, 50.0, 90.0])
    assert y[x.index(50.0) - 1] == 0.5


def test_a_single_run_still_produces_a_curve():
    x, y = ecdf([7.0])
    assert x == [7.0] and y == [1.0]


# ── Agregação por estímulo ────────────────────────────────────────────────

def test_the_mean_per_stimulus_keeps_the_declared_order():
    rows = [_run(e, legacy=i * 10.0) for i, e in enumerate(ESTIMULOS)]
    assert media_por_estimulo(rows, "reach_legacy_pct") == [0.0, 10.0, 20.0, 30.0]


def test_a_stimulus_without_runs_does_not_break_the_figure():
    rows = [_run("health_dna_a", legacy=50.0)]
    medias = media_por_estimulo(rows, "reach_legacy_pct")
    assert medias[ESTIMULOS.index("health_dna_a")] == 50.0
    assert medias[ESTIMULOS.index("benefit_auto_a")] == 0.0


def test_the_two_columns_are_read_independently():
    rows = [_run(legacy=63.19, strict=2.0), _run(legacy=63.19, strict=2.0)]
    assert media_por_estimulo(rows, "reach_legacy_pct")[2] == 63.19
    assert media_por_estimulo(rows, "reach_strict_pct")[2] == 2.0


# ── Entrada ───────────────────────────────────────────────────────────────

def test_runs_without_the_recomputed_column_are_skipped(tmp_path):
    (tmp_path / "runs_corrigido.csv").write_text(
        "stimulus_id,reach_legacy_pct,reach_strict_pct\n"
        "health_dna_a,63.0,2.0\n"
        "health_dna_a,63.0,\n", encoding="utf-8")
    assert len(load_runs(tmp_path)) == 1
