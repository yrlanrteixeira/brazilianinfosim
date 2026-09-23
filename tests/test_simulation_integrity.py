"""Contratos científicos do motor, com decisões controladas e sem rede externa."""

import sys
import json
from pathlib import Path

import pytest
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.agent import Decision, Message
from agents.profiles import AgentType, generate_profile
from metrics.analysis import summarize_result
from simulation.persistence import save_result
import simulation.engine as engine


class ControlledLLM:
    def __init__(self, decision=Decision.SHARE, content="", refused=False):
        self.decision, self.content, self.refused = decision, content, refused
        self.stats = {"api_calls": 0}

    def decide(self, **kwargs):
        self.stats["api_calls"] += 1
        if "verificar informações" in kwargs["agent_description"]:
            if kwargs["message_content"].startswith("[REFUTAÇÃO]"):
                return Decision.SHARE, "", False
            return Decision.REFUTE, "Correção sintética", False
        return self.decision, self.content, self.refused


def build(monkeypatch, llm=None, uniform_profiles=True, **kwargs):
    monkeypatch.setattr(engine, "LLMClient", lambda **_: llm or ControlledLLM())
    model = engine.InfoSimModel(engine.SimulationConfig(n_agents=10, **kwargs))
    if uniform_profiles:
        for agent in model.agents_by_id.values():
            agent.profile = generate_profile(AgentType.AMPLIFIER, seed=agent.node_id)
    return model


def fresh_agent(model):
    agent = next(a for a in model.agents_by_id.values() if not a.inbox)
    return agent


def correction():
    return Message("[REFUTAÇÃO] Correção sintética", "Boato sintético", is_refutation=True)


def use_active_ring(model, monkeypatch):
    # Uma entrega cruza a fronteira de cada tick, mesmo após alcançar todos.
    model.G = nx.DiGraph((i, (i + 1) % 10) for i in range(10))
    monkeypatch.setattr(model.agents, "shuffle_do",
                        lambda method: model.agents.sort("node_id", ascending=False).do(method))


@pytest.mark.parametrize("decision,content", [
    (Decision.SHARE, ""), (Decision.MUTATE, "Correção reformulada"),
])
def test_sharing_corrections_reduces_rumor_belief(monkeypatch, decision, content):
    model = build(monkeypatch, ControlledLLM(decision, content))
    agent = fresh_agent(model)
    agent.receive(correction())
    agent.step()
    assert agent.belief_level < 0.5
    assert not agent.has_seen_disinformation
    assert agent.has_seen_correction
    assert agent.mutated_messages == []
    assert agent.sent_messages[0].is_refutation


def test_refutation_is_not_a_rumor_mutation(monkeypatch):
    model = build(monkeypatch, ControlledLLM(Decision.REFUTE, "Correção sintética"))
    model.run()
    assert model._collect_mutations() == []


@pytest.mark.parametrize("refused", [False, True])
def test_ignoring_or_refusing_does_not_infer_disbelief(monkeypatch, refused):
    model = build(monkeypatch, ControlledLLM(Decision.IGNORE, refused=refused))
    agent = fresh_agent(model)
    agent.receive(Message("Boato", "Boato"))
    agent.step()
    assert agent.belief_level == 0.5


def test_saturated_cascade_runs_until_limit_if_messages_remain(monkeypatch):
    model = build(monkeypatch, max_ticks=12)
    use_active_ring(model, monkeypatch)
    result = model.run()
    assert result.stop_reason == "max_ticks"
    assert result.ticks_run == 12
    assert result.extinction_tick is None
    assert sum(len(a.inbox) for a in model.agents_by_id.values()) > 0


def test_empty_queue_extinguishes_without_waiting_for_late_intervention(monkeypatch):
    model = build(monkeypatch, ControlledLLM(Decision.IGNORE),
                  intervention="factcheckers_hub", intervention_tick=10)
    result = model.run()
    assert result.stop_reason == "extinct"
    assert result.extinction_tick == 1
    assert result.intervention_applied is False


def test_delayed_intervention_happens_during_active_cascade(monkeypatch):
    model = build(monkeypatch, max_ticks=25, intervention="factcheckers_hub", intervention_tick=10)
    use_active_ring(model, monkeypatch)
    result = model.run()
    assert result.intervention_applied
    assert result.intervention_applied_tick == 10
    assert len(result.intervention_nodes) == 1
    converted = model.agents_by_id[result.intervention_nodes[0]]
    assert converted.profile.converted_by_intervention
    assert any(m.is_refutation for m in converted.sent_messages)


def test_preventive_factchecker_changes_action_before_first_broadcast(monkeypatch):
    control = build(monkeypatch, max_ticks=1).run()
    treated_model = build(monkeypatch, max_ticks=1,
                          intervention="factcheckers_hub", intervention_tick=0)
    treated = treated_model.run()
    assert treated.intervention_applied_tick == 0
    assert treated.final_reach_pct == 10
    assert treated.final_correction_reach_pct > 0
    assert treated.final_reach_pct < control.final_reach_pct


def test_last_collection_matches_final_state_and_plot_index(monkeypatch):
    model = build(monkeypatch, max_ticks=1)
    result = model.run()
    summary = summarize_result(result, with_mutation=False)
    assert len(result.model_data) == 2
    assert result.model_data.iloc[-1].reach_pct == result.final_reach_pct
    assert summary["final_believers"] == model._count_believers() > 0
    assert result.agent_data.index.get_level_values("Step").max() == result.ticks_run


def test_removed_agents_keep_historical_exposure_and_mutations(monkeypatch):
    model = build(monkeypatch, intervention="remove_hubs")
    for agent in model.agents_by_id.values():
        agent.receive(Message("Boato", "Boato"))
        agent.sent_messages.append(Message("Variação", "Boato", parent_content="Boato"))
    model._apply_intervention()
    assert model._count_reached() == 10
    assert len(model._collect_mutations()) == 10
    assert model._count_reached_active() == 5


def test_adjacent_seeds_do_not_reuse_the_same_profile_population(monkeypatch):
    a = build(monkeypatch, seed=2024, uniform_profiles=False)
    b = build(monkeypatch, seed=2026, uniform_profiles=False)
    fingerprints = lambda m: {(x.profile.skepticism, x.profile.share_propensity,
                               x.profile.confirmation_bias) for x in m.agents_by_id.values()}
    assert fingerprints(a).isdisjoint(fingerprints(b))


def test_queued_exposure_is_not_duplicated_across_ticks(monkeypatch):
    model = build(monkeypatch)
    agent = fresh_agent(model)
    msg = Message("Boato", "Boato")
    agent.receive(msg)
    model.tick += 1
    agent.receive(msg.mutate("Variante"))
    assert len(agent.inbox) == 1


def test_single_seed_reproduces_controlled_run(monkeypatch):
    first = build(monkeypatch, seed=123, max_ticks=4).run()
    second = build(monkeypatch, seed=123, max_ticks=4).run()
    assert first.model_data.equals(second.model_data)


def test_network_and_population_seeds_can_vary_independently(monkeypatch):
    a = build(monkeypatch, uniform_profiles=False, network_seed=1, profile_seed=9)
    b = build(monkeypatch, uniform_profiles=False, network_seed=2, profile_seed=9)
    c = build(monkeypatch, uniform_profiles=False, network_seed=1, profile_seed=8)
    assert a.initial_state["profiles"] == b.initial_state["profiles"]
    assert a.initial_state["edges"] != b.initial_state["edges"]
    assert a.initial_state["edges"] == c.initial_state["edges"]
    assert a.initial_state["profiles"] != c.initial_state["profiles"]


@pytest.mark.parametrize("intervention", ["factcheckers_hub", "factcheckers_peripheral"])
def test_each_factchecker_intervention_changes_selected_profiles(monkeypatch, intervention):
    model = build(monkeypatch, intervention=intervention, intervention_tick=0, max_ticks=1)
    result = model.run()
    assert result.intervention_applied
    converted = [a for a in model.agents if a.profile.converted_by_intervention]
    assert [a.node_id for a in converted] == result.intervention_nodes
    for agent in converted:
        assert "verificar informações" in agent.profile.to_prompt_description()


def test_removal_changes_network_and_retains_exposure_in_result(monkeypatch):
    model = build(monkeypatch, intervention="remove_hubs", intervention_tick=0)
    result = model.run()
    assert result.intervention_applied_tick == 0
    assert result.n_removed == 5
    assert result.final_reach_pct == 10
    assert result.final_reach_pct_active == 0
    assert model.G.number_of_nodes() == len(model.agents) == 5


def test_result_json_contains_final_metrics_and_provenance(monkeypatch, tmp_path):
    result = build(monkeypatch, max_ticks=1, intervention="factcheckers_hub", intervention_tick=0).run()
    save_result(result, tmp_path, "controle")
    saved = json.loads((tmp_path / "controle.json").read_text(encoding="utf-8"))
    assert saved["summary"]["intervention_applied"]
    assert saved["model_data"][-1]["reach_pct"] == result.final_reach_pct
    assert len(saved["manifest"]["source_sha256"]) == 64
    assert saved["manifest"]["settings"]["intervention_tick"] == 0


def test_expanded_runner_applies_treatment_and_saves_before_analysis(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import run_expanded

    monkeypatch.setattr(engine, "LLMClient", lambda **_: ControlledLLM())
    monkeypatch.setattr(run_expanded, "OUT_DIR", tmp_path)
    row = run_expanded.run_one(engine.Topology.SCALE_FREE, "factcheckers_hub", "saude", 42)
    assert row["intervention_applied"]
    assert row["intervention_applied_tick"] == 0
    assert row["final_reach_pct"] == 2.0
    record = json.loads(next((tmp_path / "matrix").glob("*.json")).read_text(encoding="utf-8"))
    assert record["manifest"]["settings"]["cache_mode"] == "off"
