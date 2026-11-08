"""
tests/test_sample_texts.py

Sorteio da amostra de anotação de postura.

O que importa aqui é que o estrato siga a profundidade reconstruída, que o
sorteio seja reprodutível pela seed e que o peso devolva o estrato ao tamanho
da população. Um sorteio enviesado invalida a anotação inteira.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import pytest

from sample_texts import (
    STRATA, collect, draw, merge, parse_sizes, published, stratum, text_id,
)

RUMOR = "URGENTE: repasse isso agora"
CORRECAO = "[REFUTAÇÃO] isso é falso"
CONTESTACAO = "não é bem assim"


def _event(event, node, tick, content, parent, refutation, parent_refutation):
    return {"event": event, "node_id": node, "tick": tick, "content": content,
            "original_content": RUMOR, "parent_content": parent, "hops": tick,
            "is_refutation": refutation, "parent_is_refutation": parent_refutation}


def _audit():
    """Emissor 0 refuta o boato; 1 contesta a correção; 2 repassa a contestação."""
    return [
        _event("received", 0, 0, RUMOR, None, False, False),
        _event("sent", 0, 0, CORRECAO, RUMOR, True, False),
        _event("received", 1, 0, CORRECAO, RUMOR, True, False),
        _event("sent", 1, 1, CONTESTACAO, CORRECAO, False, True),
        _event("received", 2, 1, CONTESTACAO, CORRECAO, False, True),
        _event("sent", 2, 2, CONTESTACAO, CONTESTACAO, False, False),
    ]


def _payload(events):
    return {"summary": {"n_agents": 10}, "initial_state": {"injection_node": 0},
            "message_audit": events}


def _pool(size_by_stratum):
    pool = {}
    for name, size in size_by_stratum.items():
        depth = {"boato": 0, "correcao": 1, "ambiguo": 2}[name]
        for index in range(size):
            content = f"{name}-{index}"
            pool[(content, depth % 2 == 1)] = {
                "text_id": text_id(content), "estrato": name,
                "refutation_depth": depth, "subject": "s", "run_id": "r",
                "node_id": 0, "tick": 0, "ocorrencias": 1, "texto": content,
            }
    return pool


# ── Estratificação ────────────────────────────────────────────────────────

def test_stratum_follows_the_depth():
    assert [stratum(d) for d in (0, 1, 2, 5)] == ["boato", "correcao", "ambiguo", "ambiguo"]


def test_published_keeps_one_record_per_distinct_text():
    records = published(_payload(_audit()), "run-1", "saude")
    assert {r["texto"] for r in records.values()} == {CORRECAO, CONTESTACAO}
    assert records[(CORRECAO, True)]["estrato"] == "correcao"
    assert records[(CONTESTACAO, False)]["refutation_depth"] == 2


def test_published_carries_the_claim_the_text_will_be_judged_against():
    """Sem a alegação original na planilha, o anotador não tem contra o que decidir."""
    records = published(_payload(_audit()), "run-1", "saude")
    assert all(r["alegacao"] == RUMOR for r in records.values())


def test_published_counts_repeated_publications():
    records = published(_payload(_audit()), "run-1", "saude")
    assert records[(CONTESTACAO, False)]["ocorrencias"] == 2


def test_results_without_audit_contribute_nothing():
    assert published({"summary": {"n_agents": 10}, "message_audit": []}, "r", "s") == {}


def test_merge_sums_occurrences_and_keeps_the_smaller_depth():
    pool = published(_payload(_audit()), "run-1", "saude")
    other = {(CONTESTACAO, False): {**pool[(CONTESTACAO, False)],
                                    "refutation_depth": 0, "estrato": "boato",
                                    "ocorrencias": 3}}
    merge(pool, other)
    assert pool[(CONTESTACAO, False)]["ocorrencias"] == 5
    assert pool[(CONTESTACAO, False)]["estrato"] == "boato"


# ── Sorteio ───────────────────────────────────────────────────────────────

def test_draw_respects_the_requested_sizes():
    sample = draw(_pool({"boato": 80, "correcao": 80, "ambiguo": 200}),
                  {"boato": 60, "correcao": 60, "ambiguo": 180}, seed=0)
    counts = {name: sum(1 for r in sample if r["estrato"] == name) for name in STRATA}
    assert counts == {"boato": 60, "correcao": 60, "ambiguo": 180}


def test_draw_is_reproducible_by_the_seed():
    pool = _pool({"boato": 80, "correcao": 10, "ambiguo": 10})
    first = [r["text_id"] for r in draw(pool, {"boato": 20, "correcao": 5, "ambiguo": 5}, 7)]
    second = [r["text_id"] for r in draw(pool, {"boato": 20, "correcao": 5, "ambiguo": 5}, 7)]
    third = [r["text_id"] for r in draw(pool, {"boato": 20, "correcao": 5, "ambiguo": 5}, 8)]
    assert first == second
    assert first != third


def test_weight_returns_the_stratum_to_its_population():
    sample = draw(_pool({"boato": 100, "correcao": 1, "ambiguo": 1}),
                  {"boato": 25, "correcao": 1, "ambiguo": 1}, seed=0)
    boato = [r for r in sample if r["estrato"] == "boato"]
    assert boato[0]["peso"] == 4.0
    assert boato[0]["textos_no_estrato"] == 100
    assert len(boato) * boato[0]["peso"] == 100


def test_small_stratum_is_taken_whole_instead_of_failing():
    sample = draw(_pool({"boato": 3, "correcao": 0, "ambiguo": 0}),
                  {"boato": 60, "correcao": 60, "ambiguo": 180}, seed=0)
    assert len(sample) == 3
    assert sample[0]["peso"] == 1.0


def test_annotation_columns_start_empty():
    sample = draw(_pool({"boato": 2, "correcao": 0, "ambiguo": 0}),
                  {"boato": 2, "correcao": 0, "ambiguo": 0}, seed=0)
    assert all(r["rotulo"] == "" and r["justificativa"] == "" for r in sample)


# ── Entrada ───────────────────────────────────────────────────────────────

def test_unknown_stratum_fails_fast():
    with pytest.raises(SystemExit, match="Estrato desconhecido"):
        parse_sizes("boatos=10")


def test_collect_skips_results_that_were_not_written(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "runs.csv").write_text("id,subject\nausente,saude\n", encoding="utf-8")
    assert collect(tmp_path) == {}
