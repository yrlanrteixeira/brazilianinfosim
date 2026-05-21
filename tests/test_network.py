"""
tests/test_network.py
Testes da geração de topologias de rede — sem LLM.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from network.topology import Topology, build_network, get_hub_nodes, network_stats


def test_all_topologies_build():
    for topology in Topology:
        G = build_network(topology=topology, n_agents=20, seed=42)
        assert G.number_of_nodes() == 20
        assert G.number_of_edges() > 0


def test_network_is_connected():
    import networkx as nx
    for topology in Topology:
        G = build_network(topology=topology, n_agents=30, seed=42)
        assert nx.is_connected(G), f"Grafo desconexo para {topology}"


def test_hub_nodes_have_high_degree():
    G = build_network(Topology.SCALE_FREE, n_agents=50, seed=42)
    hubs = get_hub_nodes(G, top_k=3)
    degrees = [G.degree(h) for h in hubs]
    avg_degree = sum(d for _, d in G.degree()) / G.number_of_nodes()
    assert all(d >= avg_degree for d in degrees)


def test_network_stats_keys():
    G = build_network(Topology.RANDOM, n_agents=20, seed=42)
    stats = network_stats(G)
    assert "n_nodes" in stats
    assert "avg_degree" in stats
    assert "density" in stats


if __name__ == "__main__":
    test_all_topologies_build()
    test_network_is_connected()
    test_hub_nodes_have_high_degree()
    test_network_stats_keys()
    print("✅ Todos os testes de rede passaram!")
