"""
tests/test_mutation.py

Testes do índice de mutação semântica (QP3) e da persistência das mutações.
O embedder é substituído por um encoder falso determinístico, para os testes
rodarem offline e as asserções serem sobre a agregação.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from metrics import analysis
from simulation.messages import SUBJECTS


class FakeEmbedder:
    """
    Vetores ortogonais por texto, sem depender de hash aleatório ou modelo.
    """

    def __init__(self):
        self.vocabulary = {}

    def encode(self, text: str):
        index = self.vocabulary.setdefault(text, len(self.vocabulary))
        vector = np.zeros(64)
        vector[index] = 1.0
        return vector


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    embedder = FakeEmbedder()
    monkeypatch.setattr(analysis, "_get_embedder", lambda: embedder)
    analysis.reset_encode_memo()
    yield
    analysis.reset_encode_memo()


def _mut(hop, content, parent, original="ORIGINAL"):
    return {
        "hop": hop,
        "content": content,
        "parent_content": parent,
        "original_content": original,
        "sender_id": 1,
    }


# ── mutation_index ────────────────────────────────────────────────────────

def test_mutation_index_is_zero_when_text_does_not_change():
    mutations = [_mut(1, "mesmo texto", "mesmo texto")]
    assert analysis.mutation_index(mutations) == pytest.approx(0.0, abs=1e-6)


def test_mutation_index_is_high_when_text_diverges():
    mutations = [_mut(1, "texto completamente outro", "mesmo texto")]
    assert analysis.mutation_index(mutations) > 0.5


def test_mutation_index_skips_items_without_parent():
    """Sem versão anterior não há par consecutivo para comparar."""
    mutations = [_mut(1, "a", None), _mut(2, "b", "b")]
    assert analysis.mutation_index(mutations) == pytest.approx(0.0, abs=1e-6)


def test_mutation_index_of_empty_input_is_zero():
    assert analysis.mutation_index([]) == 0.0


def test_cosine_distance_accepts_values_above_one(monkeypatch):
    vectors = {"a": np.array([1.0, 0.0]), "b": np.array([-1.0, 0.0])}
    monkeypatch.setattr(analysis, "_encode", vectors.__getitem__)
    assert analysis.mutation_index([_mut(1, "b", "a")]) == pytest.approx(2.0)


# ── mutation_by_hop ───────────────────────────────────────────────────────

def test_mutation_by_hop_groups_and_sorts():
    mutations = [
        _mut(2, "c", "b"),
        _mut(1, "b", "a"),
        _mut(1, "b2", "a"),
    ]
    df = analysis.mutation_by_hop(mutations)
    assert list(df.columns) == ["hop", "n", "M", "M_vs_original"]
    assert list(df["hop"]) == [1, 2]
    assert list(df["n"]) == [2, 1]


def test_mutation_by_hop_of_empty_input_keeps_columns():
    df = analysis.mutation_by_hop([])
    assert df.empty
    assert list(df.columns) == ["hop", "n", "M", "M_vs_original"]


def test_mutation_by_hop_does_not_reencode_the_same_text(monkeypatch):
    """A agregação compara content, parent e original: textos se repetem."""
    calls = []

    class CountingEmbedder(FakeEmbedder):
        def encode(self, text: str):
            calls.append(text)
            return super().encode(text)

    embedder = CountingEmbedder()
    monkeypatch.setattr(analysis, "_get_embedder", lambda: embedder)
    analysis.reset_encode_memo()

    mutations = [_mut(1, "b", "a"), _mut(1, "b", "a"), _mut(2, "c", "b")]
    analysis.mutation_by_hop(mutations)

    assert len(calls) == len(set(calls))


# ── persistência ──────────────────────────────────────────────────────────

def test_csv_round_trip_preserves_the_index_columns(tmp_path):
    """O M é recalculado a partir do CSV: perder coluna muda o valor."""
    mutations = [_mut(1, "b", "a"), _mut(2, "c", "b")]
    expected = analysis.mutation_index(mutations)

    path = tmp_path / "mutations_raw.csv"
    pd.DataFrame(mutations).to_csv(path, index=False)
    reloaded = pd.read_csv(path).to_dict("records")

    analysis.reset_encode_memo()
    assert analysis.mutation_index(reloaded) == pytest.approx(expected)


def test_mutation_index_per_subject_uses_only_that_subset():
    """Agregação por assunto não pode misturar pares de assuntos diferentes."""
    rows = (
        [dict(_mut(1, "b", "a"), subject="A")]
        + [dict(_mut(1, "z", "z"), subject="B")]
    )
    df = pd.DataFrame(rows)

    m_a = analysis.mutation_index(df[df.subject == "A"].to_dict("records"))
    m_b = analysis.mutation_index(df[df.subject == "B"].to_dict("records"))

    assert m_a > 0.5
    assert m_b == pytest.approx(0.0, abs=1e-6)


# ── mensagens compartilhadas ──────────────────────────────────────────────

def test_subject_filter_ignores_accents():
    """O guia de setup usa `--subjects saude`, sem acento."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_mutation import filter_subjects

    assert list(filter_subjects(SUBJECTS, "saude")) == ["Saúde/vacinas"]
    assert list(filter_subjects(SUBJECTS, "saúde")) == ["Saúde/vacinas"]
    assert set(filter_subjects(SUBJECTS, "saude,economia")) == {
        "Saúde/vacinas", "Economia/benefícios",
    }
    assert filter_subjects(SUBJECTS, "inexistente") == {}


def test_load_raw_merges_several_csvs(tmp_path):
    """A campanha roda por assunto: a agregação junta os pedaços."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_mutation import load_raw

    for name, subject in [("a", "Saúde/vacinas"), ("b", "Economia/benefícios")]:
        pd.DataFrame([dict(_mut(1, "b", "a"), subject=subject)]).to_csv(
            tmp_path / f"mut_{name}_raw.csv", index=False
        )

    records = load_raw(str(tmp_path / "mut_*_raw.csv"))
    assert len(records) == 2
    assert {r["subject"] for r in records} == {
        "Saúde/vacinas", "Economia/benefícios",
    }


def test_load_raw_without_files_fails_loudly(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_mutation import load_raw

    with pytest.raises(SystemExit):
        load_raw(str(tmp_path / "nao_existe_*.csv"))


def test_shared_subjects_has_the_four_themes():
    assert set(SUBJECTS) == {
        "Saúde/vacinas",
        "Política/eleições",
        "Economia/benefícios",
        "Segurança/crime",
    }
    assert all(isinstance(v, str) and v for v in SUBJECTS.values())
