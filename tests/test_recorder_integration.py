"""
tests/test_recorder_integration.py

Grava uma simulação de ponta a ponta com o LLM substituído por um fake, e
confere que a gravação basta para o replay redesenhar a rede e a cascata.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from agents.agent import Decision
from network.topology import Topology, build_network
from simulation.engine import InfoSimModel, SimulationConfig


class FakeLLM:
    """Compartilha sempre, para a cascata de fato acontecer."""

    provider = type("P", (), {"name": "fake", "model": "fake-model"})()
    temperature = 1.0
    cache_mode = "off"
    stats = {"api_calls": 0, "cache_hits": 0}

    def decide(self, agent_description, message_content, history):
        self.stats["api_calls"] += 1
        return Decision.SHARE, "", False


@pytest.fixture
def recording(tmp_path, monkeypatch):
    monkeypatch.setattr("simulation.engine.LLMClient", lambda **_: FakeLLM())
    target = tmp_path / "run.json"
    config = SimulationConfig(
        n_agents=12, topology=Topology.SCALE_FREE, max_ticks=8, seed=42,
        record_path=str(target),
    )
    InfoSimModel(config).run()
    return json.loads(target.read_text(encoding="utf-8"))


def test_recording_has_initial_and_following_ticks(recording):
    ticks = recording["ticks"]
    assert ticks[0]["tick"] == 0
    assert len(ticks) > 1, "sem progressão não há o que reproduzir"


def test_first_tick_has_nobody_processed_yet(recording):
    assert recording["ticks"][0]["reached"] == 0


def test_cascade_advances_over_ticks(recording):
    reach_series = [t["reached"] for t in recording["ticks"]]
    assert reach_series[-1] > reach_series[0]
    assert reach_series == sorted(reach_series), "alcance não pode regredir"


def test_meta_rebuilds_the_same_graph(recording):
    """O replay redesenha a rede a partir da meta, sem grafo gravado."""
    meta = recording["meta"]
    graph = build_network(
        topology=Topology(meta["topology"]),
        n_agents=meta["n_agents"],
        seed=meta["seed"],
    )
    recorded_nodes = {int(k) for k in recording["ticks"][0]["agents"]}
    assert set(graph.nodes()) == recorded_nodes


def test_meta_records_provenance(recording):
    meta = recording["meta"]
    assert meta["seed_node"] is not None
    assert meta["temperature"] == 1.0
    assert meta["cache_mode"] == "off"
    assert meta["provider"] == "fake"


def test_without_record_path_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr("simulation.engine.LLMClient", lambda **_: FakeLLM())
    model = InfoSimModel(SimulationConfig(n_agents=8, max_ticks=3, seed=1))
    model.run()
    assert model.recorder is None
    assert not list(tmp_path.glob("*.json"))
