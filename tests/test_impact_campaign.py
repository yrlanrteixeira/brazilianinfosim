"""Orçamento e pareamento da campanha ampliada, sem inferência externa."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_impact


def test_design_has_unique_controls_and_complete_treatment_grid():
    cases = run_impact.design()
    assert len(cases) == len({c["id"] for c in cases}) == 6240
    blocks = {c["block"] for c in cases}
    assert len(blocks) == 480
    for block in blocks:
        configs = [c["config"] for c in cases if c["block"] == block]
        assert len(configs) == 13
        assert sum(c.intervention is None for c in configs) == 1
        assert {c.intervention_tick for c in configs} == {0, 1, 3, 10}
        assert len({(c.network_seed, c.profile_seed, c.activation_seed, c.llm_seed) for c in configs}) == 1


@pytest.fixture
def fake_campaign(monkeypatch):
    class FakeModel:
        fail = False
        built = 0

        def __init__(self, config):
            self.config = config
            self.llm = SimpleNamespace(stats={"api_calls": 1}, audit_log=[{"raw_response": "[]"}])
            self.G = None
            type(self).built += 1

        def run(self, deadline=None):
            if self.fail:
                raise run_impact.InvalidLLMResponse("inválido", "[]")
            return self

    def summarize(model, **kwargs):
        c = model.config
        return {"intervention": c.intervention or "none", "intervention_tick": c.intervention_tick,
                "intervention_applied": bool(c.intervention), "seed": c.seed,
                "topology": c.topology.value, "final_reach_pct": 20 if c.intervention else 80}

    FakeModel.llm_stats = {"api_calls": 1}
    monkeypatch.setattr(run_impact, "InfoSimModel", FakeModel)
    monkeypatch.setattr(run_impact, "save_result", lambda *args: None)
    monkeypatch.setattr(run_impact, "network_stats", lambda graph: {})
    monkeypatch.setattr(run_impact, "summarize_result", summarize)
    return FakeModel


def test_paired_effects_and_resume_do_not_duplicate_cases(fake_campaign, tmp_path):
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    run_impact.run(cases, tmp_path, hours=1)
    run_impact.run(cases, tmp_path, hours=1, resume=True)
    assert fake_campaign.built == 4
    pairs = run_impact.pd.read_csv(tmp_path / "paired_effects.csv")
    assert list(pairs.difference_pp) == [-60, -60, -60]
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["successful"] == 4
    assert state["paired_comparisons"] == 3


def test_expired_budget_never_starts_another_case(fake_campaign, tmp_path):
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    assert run_impact.run(cases, tmp_path, hours=0) == []
    assert fake_campaign.built == 0
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["status"] == "budget_exhausted"


def test_resume_with_more_hours_does_not_renew_expired_budget(fake_campaign, tmp_path):
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    run_impact.run(cases, tmp_path, hours=0)
    original = json.loads((tmp_path / "campaign.json").read_text(encoding="utf-8"))
    assert run_impact.run(cases, tmp_path, hours=16, resume=True) == []
    assert fake_campaign.built == 0
    assert json.loads((tmp_path / "campaign.json").read_text(encoding="utf-8")) == original
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["status"] == "budget_exhausted"


def test_resume_rejects_a_different_model(fake_campaign, tmp_path):
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    run_impact.run(cases, tmp_path, hours=1, metadata={"digest": "model-a"})
    with pytest.raises(ValueError, match="Modelo ou servidor mudou"):
        run_impact.run(cases, tmp_path, hours=1, resume=True, metadata={"digest": "model-b"})
    assert fake_campaign.built == 4


def test_repeated_invalid_outputs_pause_and_remain_outside_metrics(fake_campaign, tmp_path):
    fake_campaign.fail = True
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    records = run_impact.run(cases, tmp_path, hours=1)
    assert len(records) == 3
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["status"] == "paused_after_three_failures"
    assert state["successful"] == state["paired_comparisons"] == 0
    assert state["failed"] == 3
    assert records[0]["decision_audit"][0]["raw_response"] == "[]"


def test_resume_cannot_mix_designs(fake_campaign, tmp_path):
    cases = run_impact.design(n_seeds=1, repeats=1, pilot=True)
    run_impact.run(cases, tmp_path, hours=1)
    with pytest.raises(ValueError, match="desenho mudou"):
        run_impact.run(run_impact.design(n_agents=60, pilot=True), tmp_path, hours=1, resume=True)
