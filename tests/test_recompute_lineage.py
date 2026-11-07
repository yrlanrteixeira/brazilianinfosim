"""
tests/test_recompute_lineage.py

Reconstrução da profundidade de refutação a partir da auditoria gravada.

A conferência que importa é `reach_legacy_pct`: ela reproduz a contagem antiga
a partir dos mesmos eventos. Se bater com o `final_reach_pct` do resultado, a
reconstrução leu a auditoria certo, e só então o alcance estrito tem valor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recompute_lineage import depth_by_content, exposures, recompute, removed_nodes

RUMOR = "URGENTE: repasse isso agora"
CORRECAO = "[REFUTAÇÃO] isso é falso"
CONTESTACAO = "não é bem assim"


def _event(event, node, tick, content, parent, refutation, parent_refutation):
    return {"event": event, "node_id": node, "tick": tick, "content": content,
            "original_content": RUMOR, "parent_content": parent, "hops": tick,
            "is_refutation": refutation, "parent_is_refutation": parent_refutation}


def _audit():
    """Emissor 0 recebe o boato, refuta; 1 recebe e contesta; 2 recebe a contestação."""
    return [
        _event("received", 0, 0, RUMOR, None, False, False),
        _event("sent", 0, 0, CORRECAO, RUMOR, True, False),
        _event("received", 1, 0, CORRECAO, RUMOR, True, False),
        _event("sent", 1, 1, CONTESTACAO, CORRECAO, False, True),
        _event("received", 2, 1, CONTESTACAO, CORRECAO, False, True),
    ]


def _payload(events, n_agents=10, seed=0):
    return {"summary": {"n_agents": n_agents}, "initial_state": {"injection_node": seed},
            "message_audit": events}


def test_depth_grows_at_each_refutation():
    depths = depth_by_content(_audit())
    assert depths[(RUMOR, False)] == 0
    assert depths[(CORRECAO, True)] == 1
    assert depths[(CONTESTACAO, False)] == 2


def test_forward_inherits_the_depth():
    events = _audit() + [
        _event("sent", 2, 2, CONTESTACAO, CONTESTACAO, False, False),
        _event("received", 3, 2, CONTESTACAO, CONTESTACAO, False, False),
    ]
    assert depth_by_content(events)[(CONTESTACAO, False)] == 2
    assert exposures(_payload(events))[3] == {2}


def test_parity_of_the_depth_matches_the_recorded_flag():
    depths = depth_by_content(_audit())
    for (_, refutation), depth in depths.items():
        assert (depth % 2 == 1) is refutation


def test_contested_correction_leaves_the_strict_reach():
    metrics = recompute(_payload(_audit()), removed=set())
    assert metrics["reach_strict_pct"] == 10.0, "só o emissor viu o boato"
    assert metrics["reach_ambiguous_pct"] == 10.0
    assert metrics["correction_strict_pct"] == 10.0


def test_legacy_column_reproduces_the_old_count():
    """A contagem antiga é a exposição a qualquer linhagem de profundidade par."""
    metrics = recompute(_payload(_audit()), removed=set())
    assert metrics["reach_legacy_pct"] == 20.0
    assert metrics["reach_upper_pct"] == metrics["reach_legacy_pct"]


def test_active_reach_discounts_removed_nodes():
    events = _audit() + [_event("received", 3, 0, RUMOR, RUMOR, False, False)]
    metrics = recompute(_payload(events), removed={3})
    assert metrics["reach_strict_pct"] == 20.0
    assert metrics["reach_strict_pct_active"] == 11.11


def test_results_without_audit_are_reported_not_guessed():
    assert recompute({"summary": {"n_agents": 10}, "message_audit": []}, removed=set()) == {}


def test_removed_nodes_only_when_the_intervention_removed():
    assert removed_nodes({"n_removed": "0", "intervention_nodes": "1,2"}) == set()
    assert removed_nodes({"n_removed": "2", "intervention_nodes": "1,2"}) == {1, 2}
