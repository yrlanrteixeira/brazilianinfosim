"""
tests/test_campaign_persistence.py

Persistência incremental e retomada da campanha.

Uma campanha longa precisa sobreviver a queda: gravar só no fim significa
perder tudo o que já rodou.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "legacy"))

import pandas as pd
import pytest

import run_mutation


class FakeResult:
    def __init__(self, seed):
        self.mutations = [{
            "hop": 1, "content": f"variante {seed}", "parent_content": "original",
            "original_content": "original", "sender_id": 1,
        }]


class FakeModel:
    """Falha no run de índice `fail_at`, para simular queda no meio."""

    fail_at = None
    built = 0

    def __init__(self, config):
        self.config = config
        type(self).built += 1
        if self.fail_at is not None and type(self).built == self.fail_at:
            raise RuntimeError("queda simulada")

    def run(self):
        return FakeResult(self.config.seed)


@pytest.fixture(autouse=True)
def fake_engine(monkeypatch, tmp_path):
    FakeModel.built = 0
    FakeModel.fail_at = None
    monkeypatch.setattr(run_mutation, "InfoSimModel", FakeModel)
    monkeypatch.setattr(
        run_mutation, "summarize_result",
        lambda result, with_mutation=True: {"final_reach_pct": 50.0,
                                            "refusals_agents": 0},
    )
    monkeypatch.setattr(run_mutation, "OUT_DIR", tmp_path)
    return tmp_path


SUBJECTS = {"Economia/benefícios": "mensagem de economia"}


def test_each_run_is_persisted_as_it_finishes(fake_engine):
    run_mutation.run_campaign(SUBJECTS, [42, 123, 999], 50, 1.0,
                              prefix="camp")
    rows = pd.read_csv(fake_engine / "camp_runs.csv")
    assert len(rows) == 3


def test_a_crash_keeps_what_already_ran(fake_engine):
    FakeModel.fail_at = 3
    with pytest.raises(RuntimeError):
        run_mutation.run_campaign(SUBJECTS, [42, 123, 999], 50, 1.0,
                                  prefix="camp")

    rows = pd.read_csv(fake_engine / "camp_runs.csv")
    assert len(rows) == 2, "os runs concluídos antes da queda têm que estar no disco"

    raw = pd.read_csv(fake_engine / "camp_raw.csv")
    assert len(raw) == 2


def test_resume_skips_pairs_already_done(fake_engine):
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    built_before = FakeModel.built

    run_mutation.run_campaign(SUBJECTS, [42, 123], 50, 1.0, prefix="camp",
                              resume=True)

    assert FakeModel.built == built_before + 1, "só a semente que faltava roda"
    rows = pd.read_csv(fake_engine / "camp_runs.csv")
    assert sorted(rows["seed"]) == [42, 123]


def test_resume_without_previous_file_runs_everything(fake_engine):
    run_mutation.run_campaign(SUBJECTS, [42, 123], 50, 1.0, prefix="camp",
                              resume=True)
    assert FakeModel.built == 2


def test_a_run_with_every_call_failing_aborts_the_campaign(monkeypatch, fake_engine):
    """
    O contador dentro do cliente não protege: cada run cria um cliente novo, e
    um run que morre cedo faz uma ou duas chamadas só.
    """
    monkeypatch.setattr(
        run_mutation, "summarize_result",
        lambda result, with_mutation=True: {
            "final_reach_pct": 2.0, "refusals_agents": 0,
            "api_calls": 2, "backend_errors": 2,
        },
    )
    with pytest.raises(run_mutation.BackendUnavailable):
        run_mutation.run_campaign(SUBJECTS, [42, 123], 50, 1.0, prefix="camp")


def test_the_poisoned_run_is_not_persisted(monkeypatch, fake_engine):
    monkeypatch.setattr(
        run_mutation, "summarize_result",
        lambda result, with_mutation=True: {
            "final_reach_pct": 2.0, "refusals_agents": 0,
            "api_calls": 1, "backend_errors": 1,
        },
    )
    with pytest.raises(run_mutation.BackendUnavailable):
        run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")

    assert not (fake_engine / "camp_runs.csv").exists(), (
        "run envenenado não pode entrar no CSV: o --resume o trataria como feito"
    )


def test_a_run_without_llm_calls_is_not_mistaken_for_failure(monkeypatch, fake_engine):
    """Run que morre sem chamar o LLM é desfecho legítimo, não backend caído."""
    monkeypatch.setattr(
        run_mutation, "summarize_result",
        lambda result, with_mutation=True: {
            "final_reach_pct": 2.0, "refusals_agents": 0,
            "api_calls": 0, "backend_errors": 0,
        },
    )
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    assert len(pd.read_csv(fake_engine / "camp_runs.csv")) == 1


def test_partial_backend_failure_does_not_abort(monkeypatch, fake_engine):
    """Blip isolado no meio de um run bom não pode derrubar a campanha."""
    monkeypatch.setattr(
        run_mutation, "summarize_result",
        lambda result, with_mutation=True: {
            "final_reach_pct": 90.0, "refusals_agents": 0,
            "api_calls": 200, "backend_errors": 1,
        },
    )
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    assert len(pd.read_csv(fake_engine / "camp_runs.csv")) == 1


def test_without_resume_existing_campaign_is_preserved(fake_engine):
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    with pytest.raises(ValueError, match="já existe"):
        run_mutation.run_campaign(SUBJECTS, [123], 50, 1.0, prefix="camp")

    rows = pd.read_csv(fake_engine / "camp_runs.csv")
    assert sorted(rows["seed"]) == [42]


@pytest.mark.parametrize("n_agents,temperature,subjects", [
    (60, 1.0, SUBJECTS), (50, 0.3, SUBJECTS),
    (50, 1.0, {"Economia/benefícios": "outro estímulo"}),
])
def test_resume_rejects_changed_experiment(fake_engine, n_agents, temperature, subjects):
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    with pytest.raises(ValueError, match="mudou"):
        run_mutation.run_campaign(subjects, [123], n_agents, temperature,
                                  prefix="camp", resume=True)


def test_resume_rejects_changed_model(monkeypatch, fake_engine):
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    monkeypatch.setenv("LLM_MODEL", "modelo-diferente")
    with pytest.raises(ValueError, match="mudou"):
        run_mutation.run_campaign(SUBJECTS, [123], 50, 1.0, prefix="camp", resume=True)


def test_resume_rejects_legacy_csv_without_provenance(fake_engine):
    pd.DataFrame([{"subject": next(iter(SUBJECTS)), "seed": 42}]).to_csv(
        fake_engine / "camp_runs.csv", index=False)
    with pytest.raises(ValueError, match="sem manifesto"):
        run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp", resume=True)


def test_resume_recovers_both_exports_from_atomic_checkpoint(monkeypatch, fake_engine):
    original = pd.DataFrame.to_csv

    def crash_export(frame, path, **kwargs):
        if str(path).endswith("_raw.csv"):
            raise OSError("disco interrompido entre dois CSVs")
        return original(frame, path, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_csv", crash_export)
    with pytest.raises(OSError):
        run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    assert json.loads((fake_engine / "camp_checkpoint.json").read_text(encoding="utf-8"))["rows"]
    monkeypatch.setattr(pd.DataFrame, "to_csv", original)
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp", resume=True)
    assert FakeModel.built == 1
    assert len(pd.read_csv(fake_engine / "camp_raw.csv")) == 1


def test_zero_mutations_exports_empty_table_with_schema(monkeypatch, fake_engine):
    def no_mutations(self):
        result = FakeResult(self.config.seed)
        result.mutations = []
        return result

    monkeypatch.setattr(FakeModel, "run", no_mutations)
    run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    assert pd.read_csv(fake_engine / "camp_raw.csv").empty


def test_invalid_response_is_logged_and_never_completed(monkeypatch, fake_engine):
    def fail(self):
        raise run_mutation.InvalidLLMResponse("objeto inválido", "[]")

    monkeypatch.setattr(FakeModel, "run", fail)
    with pytest.raises(run_mutation.InvalidLLMResponse):
        run_mutation.run_campaign(SUBJECTS, [42], 50, 1.0, prefix="camp")
    failure = json.loads((fake_engine / "camp_failure.json").read_text(encoding="utf-8"))
    assert failure["raw_response"] == "[]"
    assert not (fake_engine / "camp_checkpoint.json").exists()
