"""Controles experimentais testados sem produzir evidência empírica."""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import networkx as nx
import pytest

from agents.agent import Decision, Message
from agents.profiles import AgentType
from metrics.content_review import content_key
from network.topology import Topology
import simulation.engine as engine
from simulation.baseline import run_epidemic
import run_research as research


class ProbeLLM:
    def __init__(self, decision=Decision.SHARE, content=""):
        self.decision, self.content = decision, content
        self.stats = {"api_calls": 0}

    def decide(self, **kwargs):
        self.stats["api_calls"] += 1
        return self.decision, self.content, False


def build(monkeypatch, **kwargs):
    monkeypatch.setattr(engine, "LLMClient", lambda **_: ProbeLLM())
    return engine.InfoSimModel(engine.SimulationConfig(n_agents=10, **kwargs))


def test_synchronous_round_has_one_edge_latency_and_allows_reexposure(monkeypatch):
    outcomes = []
    for ascending in (True, False):
        model = build(monkeypatch, synchronous_updates=True, indifferent_uses_llm=True)
        model.G = nx.path_graph([model.seed_node, *[n for n in model.G if n != model.seed_node]])
        monkeypatch.setattr(model.agents, "shuffle_do",
                            lambda method, m=model, asc=ascending: m.agents.sort("node_id", ascending=asc).do(method))
        model.step()
        assert model._count_reached() == 2
        assert model.llm.stats["api_calls"] == 1
        model.step()
        assert model._count_reached() == 3
        for _ in range(6):
            model.step()
        outcomes.append(sorted((node, len(a.inbox)) for node, a in model.agents_by_id.items()))
    assert outcomes[0] == outcomes[1]


def test_density_and_profiles_match_across_network_families(monkeypatch):
    models = [build(monkeypatch, topology=kind, network_degree=4, inject_at="random",
                    emitter_type="amplificador", skeptic_fraction=0.2) for kind in Topology]
    assert all(nx.is_connected(m.G) and m.G.number_of_edges() == 20 for m in models)
    assert models[0].initial_state["profiles"] == models[1].initial_state["profiles"] == models[2].initial_state["profiles"]
    assert len({m.seed_node for m in models}) == 1


def test_skeptic_fractions_are_nested_and_keep_unchanged_agents(monkeypatch):
    low = build(monkeypatch, skeptic_fraction=0.2, emitter_type="amplificador")
    high = build(monkeypatch, skeptic_fraction=0.6, emitter_type="amplificador")
    skeptics = lambda m: {n for n, a in m.agents_by_id.items() if a.profile.agent_type == AgentType.SKEPTIC}
    assert len(skeptics(low)) == 2 and len(skeptics(high)) == 5
    assert skeptics(low) < skeptics(high)
    for node in set(low.agents_by_id) - skeptics(high):
        assert low.agents_by_id[node].profile == high.agents_by_id[node].profile


def test_mutation_suppression_keeps_forwarding_and_receipt_audit(monkeypatch):
    model = build(monkeypatch, mutation_enabled=False, emitter_type="amplificador",
                  synchronous_updates=True)
    model.llm.decision, model.llm.content = Decision.MUTATE, "Nova redação sintética"
    model.step()
    sender = model.agents_by_id[model.seed_node]
    assert sender.sent_messages[0].content == model.config.initial_message
    assert sender.interaction_history[0]["mutation_suppressed"]
    assert sender.mutated_messages == []
    assert model._count_reached() > 1
    assert any(e["event"] == "sent" for e in model.message_audit)


def test_forwarding_limit_starts_at_scheduled_round(monkeypatch):
    model = build(monkeypatch, intervention="limit_forwarding", intervention_tick=1,
                  synchronous_updates=True, indifferent_uses_llm=True)
    model.G = nx.complete_graph(10)
    model.step()
    assert model._count_reached() == 10 and model.active_forwarding_limit is None
    model.step()
    assert model.active_forwarding_limit == 2 and model.intervention_applied_tick == 1
    for agent in model.agents_by_id.values():
        agent.inbox.clear()
    model.tick += 1
    sender = model.agents_by_id[model.seed_node]
    sender._broadcast(Message("Outro texto", "Outra alegação", sender_id=sender.node_id))
    assert sum(bool(a.inbox) for a in model.agents_by_id.values()) == 2


def test_complete_design_has_paired_seeds_and_shared_reference():
    cases = research.design(n_seeds=3, repeats=2)
    assert len(cases) == len({c["id"] for c in cases}) == 528
    by_id, seen = {c["id"]: c for c in cases}, set()
    for case in cases:
        ref = by_id[case["reference_id"]]
        assert case["block"] == ref["block"]
        assert ref["id"] == case["id"] or ref["id"] in seen
        a, b = asdict(case["config"]), asdict(ref["config"])
        for key in ("seed", "network_seed", "profile_seed", "activation_seed", "llm_seed", "initial_message"):
            assert a[key] == b[key]
        seen.add(case["id"])
    first_block = [c for c in cases if c["block"] == cases[0]["block"]]
    assert len(first_block) == 22
    assert {c["config"].skeptic_fraction for c in first_block} == {0, 0.2, 0.4, 0.6, 0.8, 1}


def test_baselines_conserve_population_and_latent_delay():
    graph = nx.path_graph(4)
    sir = run_epidemic(graph, 0, 4, 1, 1, 1)
    seir = run_epidemic(graph, 0, 4, 1, 1, 1, latent=True)
    assert sir[2]["reached"] == 3 and seir[2]["reached"] == 2
    assert all(sum(row[k] for k in ("S", "E", "I", "R")) == 4 for row in sir + seir)
    assert run_epidemic(graph, 0, 4, 0, 1, 1)[-1]["reached"] == 1


@pytest.mark.parametrize("kwargs", [{"network_degree": 3}, {"skeptic_fraction": -0.1},
                                    {"skeptic_fraction": 1.1}, {"forwarding_limit": 0}])
def test_invalid_controls_are_rejected(kwargs):
    with pytest.raises(ValueError):
        engine.SimulationConfig(**kwargs)


def test_research_pipeline_saves_auditable_data_without_real_llm(tmp_path, monkeypatch):
    import llm.client as client
    from analysis.analyze_completion import analyze

    class Provider:
        name = "ollama"
        model = "synthetic-test-provider"

        def complete(self, **kwargs):
            return '{"decision":"COMPARTILHAR_COM_COMENTARIO","content":"Texto sintético de teste"}'

    monkeypatch.setattr(client, "make_provider", lambda **_: Provider())
    cases = research.design(pilot=True)
    records = research.run(cases, tmp_path, hours=1, exporter=research.export_analysis, session_budget=True)
    assert len(records) == 4 and all(r["status"] == "success" for r in records)
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["complete_blocks"] == 1
    research.export_analysis(tmp_path, records[:-1], len(cases), "running")
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["complete_blocks"] == 0
    research.export_analysis(tmp_path, [*records[:-1], {**records[-1], "status": "failed"}],
                             len(cases), "finished_with_failures")
    state = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["complete_blocks"] == 0
    output = tmp_path / "review"
    output.mkdir()
    original = cases[0]["config"].initial_message
    key = content_key(original, original)
    annotation = {"stance": "supports", "reviewer": "teste controlado",
                  "rationale": "Classificação sintética para verificar a preservação."}
    template = output / "review_template.json"
    template.write_text(json.dumps({key: annotation}), encoding="utf-8")
    result = analyze(tmp_path, tmp_path / "review")
    assert result["completed_runs"] == 4 and result["fully_classified_runs"] == 0
    assert result["unique_texts"] > 1
    updated = json.loads(template.read_text(encoding="utf-8"))
    assert len(updated) == result["unique_texts"]
    assert updated[key] == annotation
    identity = json.loads((tmp_path / "campaign.json").read_text(encoding="utf-8"))["identity"]
    digest = sha256()
    with ZipFile(tmp_path / "source_snapshot.zip") as archive:
        for name in archive.namelist():
            digest.update(name.encode())
            digest.update(archive.read(name))
    assert digest.hexdigest() == identity["source_sha256"]
