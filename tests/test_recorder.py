"""
tests/test_recorder.py

Testes da gravação de execução usada pelo replay visual.

A rede não é gravada: topologia, n_agents e seed a reconstroem por
build_network, que é determinístico.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from simulation.recorder import RunRecorder


class FakeAgent:
    def __init__(self, node_id, has_seen, belief, agent_type):
        self.node_id = node_id
        self.has_seen_disinformation = has_seen
        self.belief_level = belief
        self.profile = type(
            "P", (), {"agent_type": type("T", (), {"value": agent_type})()}
        )()
        self.refusal_count = 0


class FakeModel:
    def __init__(self, tick=0):
        self.tick = tick
        self.agents_by_id = {
            0: FakeAgent(0, True, 0.9, "amplificador"),
            1: FakeAgent(1, False, 0.5, "cetico"),
        }
        self.llm = type("L", (), {"stats": {"api_calls": 7, "cache_hits": 0}})()
        self.config = type("C", (), {"n_agents": 2})()


def _recorder():
    return RunRecorder(
        meta={
            "n_agents": 2, "topology": "barabasi_albert", "seed": 42,
            "inject_at": "hub", "seed_node": 0, "temperature": 1.0,
            "subject": "Economia/benefícios",
        }
    )


def test_snapshot_records_per_agent_state():
    recorder = _recorder()
    recorder.snapshot(FakeModel(tick=0))

    assert len(recorder.ticks) == 1
    agents = recorder.ticks[0]["agents"]
    assert agents["0"]["has_seen"] is True
    assert agents["0"]["agent_type"] == "amplificador"
    assert agents["1"]["has_seen"] is False


def test_snapshot_records_model_metrics():
    recorder = _recorder()
    recorder.snapshot(FakeModel(tick=3))

    entry = recorder.ticks[0]
    assert entry["tick"] == 3
    assert entry["reached"] == 1
    assert entry["believers"] == 1
    assert entry["api_calls"] == 7


def test_multiple_snapshots_keep_order():
    recorder = _recorder()
    for i in range(3):
        recorder.snapshot(FakeModel(tick=i))
    assert [t["tick"] for t in recorder.ticks] == [0, 1, 2]


def test_save_writes_readable_json(tmp_path):
    recorder = _recorder()
    recorder.snapshot(FakeModel(tick=0))
    path = recorder.save(tmp_path / "run.json")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["meta"]["seed"] == 42
    assert data["meta"]["seed_node"] == 0
    assert len(data["ticks"]) == 1


def test_save_does_not_store_the_graph():
    """A rede é reconstruída por build_network: gravá-la duplicaria a verdade."""
    recorder = _recorder()
    recorder.snapshot(FakeModel())

    dumped = json.dumps(recorder.to_dict())
    assert "edges" not in dumped
    assert "nodes" not in dumped


def test_meta_carries_what_rebuilds_the_graph():
    recorder = _recorder()
    for key in ("n_agents", "topology", "seed"):
        assert key in recorder.meta, f"sem {key} o replay não redesenha a rede"


def test_save_creates_missing_directory(tmp_path):
    recorder = _recorder()
    recorder.snapshot(FakeModel())
    target = tmp_path / "recordings" / "run.json"
    recorder.save(target)
    assert target.exists()
