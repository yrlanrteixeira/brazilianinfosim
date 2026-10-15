from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyze_completion import cluster_summary, run_metrics
from analysis.benchmark_external import cascade_features, distribution_distance, empirical_features


def test_normalized_times_preserve_singletons_as_undefined():
    assert cascade_features([15]) == {"publishers": 1, "duration": 0, "u50": None, "u90": None}
    assert cascade_features([10, 20, 30, 50])["u50"] == 0.25
    assert cascade_features([])["publishers"] == 0


def test_distribution_distances_and_missing_predictions():
    assert distribution_distance([1, 1], [3, 3]) == {"wasserstein": 2, "ks_statistic": 1}
    assert distribution_distance([1, 2, 3], [1, 2, 3])["wasserstein"] == 0
    assert distribution_distance([1], [])["wasserstein"] is None


def test_empirical_repeated_posts_do_not_become_new_publishers(tmp_path):
    path = tmp_path / "shares.txt"
    path.write_text("cluster_image_name\tuser_id\ttimestamp\nimage\ta\t10000\nimage\ta\t30000\nimage\tb\t20000\n", encoding="utf-8")
    rows, audit = empirical_features(path)
    assert audit["shares"] == 3
    assert rows[0]["publishers"] == 2 and rows[0]["duration"] == 10


def test_many_messages_from_one_seed_do_not_produce_a_confidence_interval():
    result = cluster_summary([{"seed_index": 1, "effect": 10}] * 200, "effect")
    assert result["pairs"] == 200 and result["independent_seed_clusters"] == 1
    assert result["ci95_cluster_bootstrap"] is None


def test_unclassified_support_and_unreached_milestones_are_not_zero():
    payload = {"manifest": {"settings": {"n_agents": 10}},
               "summary": {"ticks_run": 1, "stop_reason": "extinct", "intervention_applied": False},
               "message_audit": [{"event": "received", "tick": 0, "node_id": 0, "sender_id": None,
                                  "content": "Mensagem sintética", "original_content": "Mensagem sintética"}]}
    row, _ = run_metrics(payload, {})
    assert row["supports_reach_pct"] is None and row["supports_T50"] is None
    assert row["literal_reach_pct"] == 10 and row["literal_T25"] is None
    assert row["unique_publishers_any"] == 0
