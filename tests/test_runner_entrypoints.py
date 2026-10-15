"""Entradas de execução não iniciam campanhas ao serem importadas."""

import importlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from simulation import engine
from simulation.replay import ReplayModel
from tests.test_recorder_integration import FakeLLM


def test_research_cli_loads_environment_before_connecting(monkeypatch, tmp_path):
    from dotenv import load_dotenv
    import run_research

    environment = tmp_path / ".env"
    environment.write_text("OLLAMA_BASE_URL=http://synthetic-ollama.invalid:11434\n", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.delenv("OLLAMA_BASE_URL")
    monkeypatch.setattr(run_research, "load_dotenv", lambda: load_dotenv(environment))
    monkeypatch.setattr(sys, "argv", ["run_research.py", "--output", str(tmp_path / "campaign"), "--pilot"])
    endpoints = []
    monkeypatch.setattr(run_research, "local_model_metadata",
                        lambda model: endpoints.append(os.getenv("OLLAMA_BASE_URL")))
    monkeypatch.setattr(run_research, "run", lambda *args, **kwargs: None)

    run_research.main()

    assert endpoints == ["http://synthetic-ollama.invalid:11434"]


@pytest.mark.parametrize("module_name", ["run_subjects", "run_supplementary"])
def test_import_does_not_start_a_campaign(monkeypatch, module_name):
    def forbidden(*args, **kwargs):
        pytest.fail("Importar o módulo iniciou uma simulação.")

    monkeypatch.setattr(engine, "InfoSimModel", forbidden)
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    assert callable(module.main)


def test_cli_records_a_run_that_can_be_replayed_after_removal(monkeypatch, tmp_path):
    import run_simulation

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(engine, "LLMClient", lambda **_: FakeLLM())
    monkeypatch.setattr(run_simulation, "plot_simulation", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", [
        "run_simulation.py", "--agents", "12", "--ticks", "1", "--provider", "ollama",
        "--intervention", "remove_hubs", "--intervention-tick", "0", "--record",
    ])
    run_simulation.main()
    recordings = list((tmp_path / "data/outputs/recordings").glob("*.json"))
    assert len(recordings) == 1
    replay = ReplayModel(str(recordings[0]))
    replay.step()
    assert len(replay.G) == 7
    assert all(replay.node_state(node) for node in replay.G)
    result_file = next((tmp_path / "data/outputs/tcc2").rglob("*.json"))
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert Path(payload["manifest"]["settings"]["record_path"]).resolve() == recordings[0]
