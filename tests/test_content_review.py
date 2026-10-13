"""Exposição textual não pode ser inferida da alternância de REFUTAR."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.agent import Decision, Message
from metrics.content_review import content_key, paired_content_effects, review_exposure
from run_content_review import export_content_review
from simulation.persistence import save_result
from tests.test_simulation_integrity import ControlledLLM, build, fresh_agent


def annotation(stance):
    return {"stance": stance, "reviewer": "teste controlado",
            "rationale": "Texto sintético cuja posição é definida pelo teste."}


def test_refuting_a_correction_does_not_count_as_textual_support(monkeypatch, tmp_path):
    model = build(monkeypatch, ControlledLLM(Decision.REFUTE, "A alegação inicial é falsa."),
                  initial_message="Alegação sintética", max_ticks=3)
    result = model.run()
    save_result(result, tmp_path, "run")
    payload = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    annotations = {}
    for event in payload["message_audit"]:
        stance = "supports" if event["content"] == model.config.initial_message else "rejects"
        annotations[content_key(event["original_content"], event["content"])] = annotation(stance)
    review = review_exposure(payload, annotations)
    assert any(event["event"] == "received" and not event["is_refutation"]
               and event["content"] != model.config.initial_message for event in result.message_audit)
    assert review["classification_complete"]
    assert review["stance_reach_pct"]["supports"] == 10
    assert review["stance_reach_pct"]["rejects"] > 10
    assert result.final_reach_pct > review["stance_reach_pct"]["supports"]
    assert review["factual_accuracy"] == "not_assessed"
    assert payload["metric_semantics"]["final_reach_pct"] == "rumor_lineage_exposure"


def test_audit_keeps_only_accepted_receipts_and_actual_publications(monkeypatch):
    model = build(monkeypatch, ControlledLLM(Decision.SHARE, "Proposta descartada"))
    agent = fresh_agent(model)
    message = Message("Texto recebido", "Boato sintético")
    agent.receive(message)
    agent.receive(message.mutate("Variante descartada pela deduplicação"))
    accepted = [event for event in model.message_audit
                if event["node_id"] == agent.node_id and event["event"] == "received"]
    assert len(accepted) == 1
    agent.step()
    sent = [event for event in model.message_audit if event["event"] == "sent"]
    assert sent[0]["content"] == "Texto recebido"
    assert not any(event["content"] == "Proposta descartada" for event in model.message_audit)


def test_audit_retains_queued_exposure_after_emitter_removal(monkeypatch):
    model = build(monkeypatch, intervention="remove_hubs", intervention_tick=0, max_ticks=1)
    result = model.run()
    assert result.message_audit[0]["node_id"] in model.removed_nodes
    assert result.message_audit[0]["event"] == "received"
    assert result.message_audit[0]["tick"] == 0


@pytest.fixture
def payload():
    def event(node, content, event_type="received"):
        return {"event": event_type, "node_id": node, "original_content": "Boato",
                "content": content, "is_refutation": False}

    return {"manifest": {"settings": {"n_agents": 10}}, "message_audit": [
        event(0, "Boato"), event(0, "Boato"), event(1, "Variante"), event(2, "Boato", "sent")
    ]}


def test_pending_reviews_have_no_point_estimate_or_automatic_literal_stance(payload):
    review = review_exposure(payload, {})
    assert review["original_text_reach_pct"] == 10
    assert review["unresolved_reach_pct"] == 20
    assert not review["classification_complete"]
    assert review["stance_reach_pct"]["supports"] is None
    assert review["stance_reach_bounds_pct"]["supports"] == {"lower": 0, "upper": 20}


def test_classification_counts_unique_receivers_and_separates_mixed_text(payload):
    annotations = {content_key("Boato", "Boato"): annotation("supports"),
                   content_key("Boato", "Variante"): annotation("mixed")}
    review = review_exposure(payload, annotations)
    assert review["classification_complete"]
    assert review["stance_reach_pct"] == {"supports": 10, "rejects": 0, "mixed": 10, "unrelated": 0}


@pytest.mark.parametrize("stance", ["pending", "ambiguous"])
def test_unresolved_texts_keep_bounds_without_filling_missing_reach(payload, stance):
    annotations = {content_key("Boato", "Boato"): annotation("supports"),
                   content_key("Boato", "Variante"): annotation(stance)}
    review = review_exposure(payload, annotations)
    assert not review["classification_complete"]
    assert review["stance_reach_pct"]["supports"] is None
    assert review["stance_reach_bounds_pct"]["supports"] == {"lower": 10, "upper": 20}


@pytest.mark.parametrize("bad_annotation", [
    {"stance": "supports"}, {"stance": "supports", "reviewer": "", "rationale": "texto"},
    {"stance": "invalid"},
])
def test_review_rejects_missing_attribution_and_unknown_stance(payload, bad_annotation):
    with pytest.raises(ValueError):
        review_exposure(payload, {content_key("Boato", "Boato"): bad_annotation})


def test_legacy_results_cannot_be_reported_as_zero_exposure():
    with pytest.raises(ValueError, match="sem auditoria"):
        review_exposure({"manifest": {"settings": {"n_agents": 10}}}, {})


@pytest.mark.parametrize("field", ["content", "original_content"])
def test_annotation_cannot_change_text_without_changing_its_key(payload, field):
    wrong = {**annotation("supports"), field: "Outro texto"}
    with pytest.raises(ValueError, match="hash"):
        review_exposure(payload, {content_key("Boato", "Boato"): wrong})


def test_paired_effect_requires_complete_review_of_both_cases():
    records = [
        {"id": "control", "block": "a", "status": "success", "summary": {"intervention": "none"}},
        {"id": "treated", "block": "a", "status": "success", "summary": {"intervention": "remove_hubs"}},
    ]
    reports = {
        "control": {"classification_complete": True, "stance_reach_pct": {"supports": 80}},
        "treated": {"classification_complete": False, "stance_reach_pct": {"supports": None}},
    }
    assert paired_content_effects(records, reports)[0]["supports_difference_pp"] is None
    reports["treated"] = {"classification_complete": True, "stance_reach_pct": {"supports": 20}}
    assert paired_content_effects(records, reports)[0]["supports_difference_pp"] == -60


def test_research_reference_is_used_when_both_arms_have_no_intervention():
    records = [{"id": key, "reference_id": "control", "block": "b", "status": "success",
                "summary": {"intervention": "none"}} for key in ("control", "mutation_disabled")]
    reports = {key: {"classification_complete": True, "stance_reach_pct": {"supports": value}}
               for key, value in (("control", 40), ("mutation_disabled", 20))}
    pairs = paired_content_effects(records, reports)
    assert len(pairs) == 1 and pairs[0]["supports_difference_pp"] == -20


def test_review_export_preserves_source_and_existing_annotations(payload, tmp_path):
    source = tmp_path / "run.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    original = source.read_bytes()
    output = tmp_path / "review"
    report = export_content_review(source, output)
    assert report["new_llm_calls"] == 0
    template = output / "review_template.json"
    annotations = json.loads(template.read_text(encoding="utf-8"))
    for item in annotations.values():
        item.update(annotation("rejects"))
    template.write_text(json.dumps(annotations), encoding="utf-8")
    edited = template.read_bytes()
    report = export_content_review(source, output, template)
    assert report["runs"]["run"]["classification_complete"]
    assert len(report["annotations_sha256"]) == 64
    assert len(report["runs"]["run"]["source_sha256"]) == 64
    assert source.read_bytes() == original
    assert template.read_bytes() == edited


def test_campaign_review_cli_excludes_failed_attempts(payload, tmp_path, monkeypatch):
    import run_content_review

    campaign = tmp_path / "campaign"
    (campaign / "attempts").mkdir(parents=True)
    (campaign / "results").mkdir()
    for case_id, intervention, status in [
        ("control", "none", "success"), ("treated", "remove_hubs", "success"),
        ("failed", "factcheckers_hub", "failed"),
    ]:
        record = {"id": case_id, "block": "b0", "status": status,
                  "summary": {"intervention": intervention}}
        (campaign / "attempts" / f"{case_id}.json").write_text(json.dumps(record), encoding="utf-8")
        if status == "success":
            (campaign / "results" / f"{case_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "review"
    monkeypatch.setattr(sys, "argv", ["run_content_review.py", str(campaign), "--output", str(output)])
    run_content_review.main()
    report = json.loads((output / "exposure.json").read_text(encoding="utf-8"))
    assert set(report["runs"]) == {"control", "treated"}
    assert len(report["paired_effects"]) == 1
    assert report["paired_effects"][0]["supports_difference_pp"] is None
