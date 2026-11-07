"""Comparação exploratória com publicadores de imagens checadas no Brasil."""

import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import random
from statistics import mean, median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from metrics.content_review import content_key, review_exposure
from network.topology import Topology, build_network, match_edge_count
from simulation.baseline import run_epidemic
from simulation.persistence import atomic_json, load_campaigns


def cascade_features(first_times):
    times = sorted(first_times)
    n = len(times)
    duration = times[-1] - times[0] if times else 0
    return {"publishers": n, "duration": duration,
            "u50": (times[math.ceil(0.5 * n) - 1] - times[0]) / duration if duration else None,
            "u90": (times[math.ceil(0.9 * n) - 1] - times[0]) / duration if duration else None}


def distribution_distance(a, b):
    if not a or not b:
        return {"wasserstein": None, "ks_statistic": None}
    points = sorted(set(a + b))
    cdf_differences = [abs(sum(x <= p for x in a) / len(a) - sum(x <= p for x in b) / len(b)) for p in points]
    return {"wasserstein": sum((q - p) * d for p, q, d in zip(points, points[1:], cdf_differences)),
            "ks_statistic": max(cdf_differences)}


def compare(observed, simulated):
    metrics = {}
    for name in ("publishers", "u50", "u90"):
        obs = [row[name] for row in observed if row[name] is not None]
        sim = [row[name] for row in simulated if row[name] is not None]
        if name == "publishers":
            obs, sim = [math.log1p(x) for x in obs], [math.log1p(x) for x in sim]
        metrics[name] = {**distribution_distance(obs, sim), "observed_n": len(obs), "simulated_n": len(sim)}
    return metrics


def baseline_sample(n, ticks, beta, gamma, latent, seed, repetitions=30):
    rows = []
    for index in range(repetitions):
        kind = list(Topology)[index % 3]
        options = {"k": 4, "m": 2}
        if kind == Topology.RANDOM:
            options["p"] = 4 / (n - 1)
        graph = build_network(kind, n, seed=seed + index, **options)
        match_edge_count(graph, n * 2, seed + index)
        source = random.Random(seed + index).randrange(n)
        trajectory = run_epidemic(graph, source, ticks, beta, gamma, seed + 10000 + index, latent)
        first_times, previous = [], 0
        for row in trajectory:
            first_times.extend([row["tick"]] * (row["ever_infectious"] - previous))
            previous = row["ever_infectious"]
        rows.append(cascade_features(first_times))
    return rows


def empirical_features(path):
    clusters = defaultdict(dict)
    shares, timestamps = 0, []
    with path.open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            shares += 1
            timestamp = int(row["timestamp"]) / 1000
            timestamps.append(timestamp)
            group = clusters[row["cluster_image_name"]]
            user = row["user_id"]
            group[user] = min(timestamp, group.get(user, timestamp))
    features = [{"cluster": key, **cascade_features(times.values())} for key, times in sorted(clusters.items())]
    return features, {"shares": shares, "clusters": len(clusters), "first_epoch": min(timestamps),
                      "last_epoch": max(timestamps), "timestamp_unit": "milliseconds in source; seconds in duration"}


def llm_features(campaigns, annotations, n_agents, ticks):
    rows, counts = [], defaultdict(int)
    corpus = json.loads((campaigns[0] / "corpus.json").read_text(encoding="utf-8"))
    if corpus.get("pilot"):
        return [], {"pilot_excluded": True}
    _, attempts, _ = load_campaigns(campaigns)
    for campaign, record in attempts:
        if record["status"] != "success" or record["family"] != "reference":
            continue
        if (record["config"]["n_agents"], record["config"]["max_ticks"]) != (n_agents, ticks):
            counts["incompatible_population_or_horizon"] += 1
            continue
        payload = json.loads((campaign / "results" / f"{record['id']}.json").read_text(encoding="utf-8"))
        review = review_exposure(payload, annotations)
        sent = [event for event in payload["message_audit"] if event["event"] == "sent"]
        inventory = review["inventory"]
        if any(inventory[content_key(e["original_content"], e["content"])]["stance"] in {"pending", "ambiguous"} for e in sent):
            counts["unclassified_reference_runs"] += 1
            continue
        first = {}
        for event in sent:
            if inventory[content_key(event["original_content"], event["content"])]["stance"] == "supports":
                first.setdefault(event["node_id"], event["tick"])
        if not first:
            counts["runs_without_support_publication"] += 1
            continue
        rows.append(cascade_features(first.values()))
        counts["eligible_reference_runs"] += 1
    return rows, dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--campaign", type=Path, nargs="+", help="Uma pasta ou as fatias (--shard) da mesma campanha")
    parser.add_argument("--annotations", type=Path)
    args = parser.parse_args()
    if args.agents < 7 or args.ticks < 1:
        parser.error("População e horizonte inválidos.")
    observed, audit = empirical_features(args.dataset)
    random.Random(20261013).shuffle(observed)
    split = int(0.7 * len(observed))
    training, evaluation = observed[:split], observed[split:]
    if not training or not evaluation:
        parser.error("Dados insuficientes para separar ajuste e avaliação.")
    results, grid = {}, []
    for latent, name in ((False, "SIR"), (True, "SEIR")):
        candidates = []
        for beta in (0.05, 0.1, 0.2, 0.4, 0.8):
            for gamma in (0.2, 0.5, 1.0):
                sample = baseline_sample(args.agents, args.ticks, beta, gamma, latent, 820000)
                distances = compare(training, sample)
                temporal = distances["u50"]["wasserstein"]
                loss = distances["publishers"]["wasserstein"] + (temporal if temporal is not None else 1)
                candidates.append((loss, beta, gamma))
                grid.append({"model": name, "beta": beta, "gamma": gamma, "training_loss": loss})
        loss, beta, gamma = min(candidates)
        test_sample = baseline_sample(args.agents, args.ticks, beta, gamma, latent, 920000, 120)
        results[name] = {"beta": beta, "gamma": gamma, "training_loss": loss,
                         "evaluation": compare(evaluation, test_sample)}
    if args.campaign:
        annotations = json.loads(args.annotations.read_text(encoding="utf-8")) if args.annotations else {}
        features, counts = llm_features(args.campaign, annotations, args.agents, args.ticks)
        results["LLM"] = {"eligibility": counts, "evaluation": compare(evaluation, features),
                          "conditional_on": "at least one observed publication supporting the initial claim"}
    report = {"dataset": audit, "dataset_sha256": sha256(args.dataset.read_bytes()).hexdigest(),
              "source": "https://doi.org/10.5281/zenodo.3779157", "n_agents": args.agents, "ticks": args.ticks,
              "train_clusters": [r["cluster"] for r in training], "evaluation_clusters": [r["cluster"] for r in evaluation],
              "observed_publishers_mean": mean(r["publishers"] for r in observed),
              "observed_publishers_median": median(r["publishers"] for r in observed),
              "clusters_larger_than_simulation": sum(r["publishers"] > args.agents for r in observed),
              "observed": observed, "calibration_grid": grid, "models": results,
              "analysis_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "limitations": ["Publicadores observados, não leitores nem trajetórias completas de transmissão.",
                              "Imagens políticas e textos sintéticos diferem em conteúdo, modalidade e período.",
                              "Tempos normalizados pela duração de cada série; rodadas não foram convertidas em horas.",
                              "Separação por cluster de imagem, sem garantia de alegações semanticamente independentes.",
                              "Tamanho da simulação limita a distribuição possível; não constitui calibração populacional.",
                              "SEIR usa primeira entrada em I como proxy de primeira publicação; não há decisão textual."]}
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output / "benchmark.json", report)
    print(json.dumps({k: report[k] for k in ("dataset", "observed_publishers_mean", "observed_publishers_median", "clusters_larger_than_simulation", "models")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
