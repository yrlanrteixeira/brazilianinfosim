"""
tests/test_mutation.py

Testes do índice de mutação semântica (QP3) e da persistência das mutações.

O embedder real (sentence-transformers) é substituído por um encoder falso
determinístico: os testes rodam offline e em milissegundos, e as asserções
passam a ser sobre a agregação, que é o que o código faz de fato.
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
    Encoder determinístico por texto. Textos iguais geram vetores iguais,
    textos diferentes geram vetores quase ortogonais.
    """

    def encode(self, text: str):
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        v = rng.normal(size=16)
        return v / np.linalg.norm(v)


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    monkeypatch.setattr(analysis, "_get_embedder", lambda: FakeEmbedder())
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

def test_mutation_index_zero_quando_texto_nao_muda():
    muts = [_mut(1, "mesmo texto", "mesmo texto")]
    assert analysis.mutation_index(muts) == pytest.approx(0.0, abs=1e-6)


def test_mutation_index_alto_quando_texto_diverge():
    muts = [_mut(1, "texto completamente outro", "mesmo texto")]
    assert analysis.mutation_index(muts) > 0.5


def test_mutation_index_ignora_itens_sem_parent():
    """Sem versão anterior não há par consecutivo para comparar."""
    muts = [_mut(1, "a", None), _mut(2, "b", "b")]
    assert analysis.mutation_index(muts) == pytest.approx(0.0, abs=1e-6)


def test_mutation_index_vazio_retorna_zero():
    assert analysis.mutation_index([]) == 0.0


# ── mutation_by_hop ───────────────────────────────────────────────────────

def test_mutation_by_hop_agrupa_e_ordena():
    muts = [
        _mut(2, "c", "b"),
        _mut(1, "b", "a"),
        _mut(1, "b2", "a"),
    ]
    df = analysis.mutation_by_hop(muts)
    assert list(df.columns) == ["hop", "n", "M", "M_vs_original"]
    assert list(df["hop"]) == [1, 2]
    assert list(df["n"]) == [2, 1]


def test_mutation_by_hop_vazio_retorna_dataframe_com_colunas():
    df = analysis.mutation_by_hop([])
    assert df.empty
    assert list(df.columns) == ["hop", "n", "M", "M_vs_original"]


def test_mutation_by_hop_nao_reencoda_o_mesmo_texto(monkeypatch):
    """
    O memo de encoding existe porque a agregação compara content, parent e
    original de cada linha, e os mesmos textos reaparecem entre linhas.
    """
    chamadas = []

    class Contador(FakeEmbedder):
        def encode(self, text: str):
            chamadas.append(text)
            return super().encode(text)

    monkeypatch.setattr(analysis, "_get_embedder", lambda: Contador())
    analysis.reset_encode_memo()

    muts = [_mut(1, "b", "a"), _mut(1, "b", "a"), _mut(2, "c", "b")]
    analysis.mutation_by_hop(muts)

    assert len(chamadas) == len(set(chamadas))


# ── persistência ──────────────────────────────────────────────────────────

def test_round_trip_csv_preserva_colunas_do_indice(tmp_path):
    """
    O M é calculado depois da campanha, a partir do CSV bruto. Se o round-trip
    perder uma coluna, o recálculo silenciosamente muda de valor.
    """
    muts = [_mut(1, "b", "a"), _mut(2, "c", "b")]
    esperado = analysis.mutation_index(muts)

    caminho = tmp_path / "mutations_raw.csv"
    pd.DataFrame(muts).to_csv(caminho, index=False)
    lidos = pd.read_csv(caminho).to_dict("records")

    analysis.reset_encode_memo()
    assert analysis.mutation_index(lidos) == pytest.approx(esperado)


def test_mutation_index_por_assunto_usa_apenas_o_subconjunto():
    """Agregação por assunto não pode misturar pares de assuntos diferentes."""
    muts_a = [_mut(1, "b", "a")]
    muts_b = [_mut(1, "z", "z")]
    linhas = (
        [dict(m, subject="A") for m in muts_a]
        + [dict(m, subject="B") for m in muts_b]
    )
    df = pd.DataFrame(linhas)

    m_a = analysis.mutation_index(df[df.subject == "A"].to_dict("records"))
    m_b = analysis.mutation_index(df[df.subject == "B"].to_dict("records"))

    assert m_a > 0.5
    assert m_b == pytest.approx(0.0, abs=1e-6)


# ── mensagens compartilhadas ──────────────────────────────────────────────

def test_filtro_de_assunto_ignora_acento():
    """O guia de setup usa `--subjects saude`, sem acento."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_mutation import filtra_subjects

    assert list(filtra_subjects(SUBJECTS, "saude")) == ["Saúde/vacinas"]
    assert list(filtra_subjects(SUBJECTS, "saúde")) == ["Saúde/vacinas"]
    assert set(filtra_subjects(SUBJECTS, "saude,economia")) == {
        "Saúde/vacinas", "Economia/benefícios",
    }
    assert filtra_subjects(SUBJECTS, "inexistente") == {}


def test_subjects_compartilhado_tem_os_quatro_temas():
    assert set(SUBJECTS) == {
        "Saúde/vacinas",
        "Política/eleições",
        "Economia/benefícios",
        "Segurança/crime",
    }
    assert all(isinstance(v, str) and v for v in SUBJECTS.values())
