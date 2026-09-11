"""
tests/test_replay.py

Testes do modelo de replay. Ele finge ser um mesa.Model para reaproveitar
play, pause, step e reset do SolaraViz, mas cada passo só avança um índice na
gravação, sem chamar LLM.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from simulation.replay import NodeState, ReplayModel


@pytest.fixture
def recording(tmp_path):
    def agents(seen):
        return {
            str(i): {
                "has_seen": i in seen,
                "belief": 0.9 if i in seen else 0.5,
                "agent_type": "amplificador" if i == 0 else "cetico",
            }
            for i in range(6)
        }

    data = {
        "meta": {
            "n_agents": 6, "topology": "barabasi_albert", "seed": 42,
            "seed_node": 0, "inject_at": "hub", "temperature": 1.0,
            "cache_mode": "off", "provider": "ollama", "model": "llama3.1:8b",
            "initial_message": "mensagem",
        },
        "ticks": [
            {"tick": 0, "agents": agents(set()), "reached": 0,
             "believers": 0, "api_calls": 0, "refusals": 0},
            {"tick": 1, "agents": agents({0, 1}), "reached": 2,
             "believers": 2, "api_calls": 4, "refusals": 0},
            {"tick": 2, "agents": agents({0, 1, 2, 3}), "reached": 4,
             "believers": 4, "api_calls": 9, "refusals": 1},
        ],
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_starts_at_the_first_tick(recording):
    model = ReplayModel(str(recording))
    assert model.tick == 0
    assert model.current["reached"] == 0


def test_step_advances_one_tick(recording):
    model = ReplayModel(str(recording))
    model.step()
    assert model.tick == 1
    assert model.current["reached"] == 2


def test_stops_at_the_end_without_overflow(recording):
    model = ReplayModel(str(recording))
    for _ in range(10):
        model.step()
    assert model.tick == 2
    assert model.running is False


def test_rebuilds_the_graph_from_meta(recording):
    model = ReplayModel(str(recording))
    assert model.G.number_of_nodes() == 6
    assert set(model.pos) == set(model.G.nodes())


def test_layout_is_stable_between_steps(recording):
    """Layout recalculado a cada tick faz o grafo pular e vira ilegível."""
    model = ReplayModel(str(recording))
    before = dict(model.pos)
    model.step()
    assert model.pos == before


def test_node_state_reflects_the_snapshot(recording):
    model = ReplayModel(str(recording))
    assert model.node_state(0) == NodeState.SEED
    assert model.node_state(1) == NodeState.UNREACHED
    model.step()
    assert model.node_state(1) == NodeState.BELIEVER


def test_datacollector_feeds_the_plot(recording):
    model = ReplayModel(str(recording))
    model.step()
    model.step()
    df = model.datacollector.get_model_vars_dataframe()
    assert list(df["reach_pct"].round(0)) == [0.0, 33.0, 67.0]


def test_meta_is_available_to_the_interface(recording):
    model = ReplayModel(str(recording))
    assert model.meta["model"] == "llama3.1:8b"
    assert model.total_ticks == 3
