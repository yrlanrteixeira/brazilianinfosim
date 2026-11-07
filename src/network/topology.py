"""
network/topology.py
Geração das topologias de rede social para simulação.
"""

from enum import Enum
import networkx as nx
import random


class Topology(str, Enum):
    RANDOM       = "erdos_renyi"       # linha de base
    SCALE_FREE   = "barabasi_albert"   # conexão preferencial
    SMALL_WORLD  = "watts_strogatz"    # vizinhança local com reconexão


def build_network(
    topology: Topology,
    n_agents: int,
    seed: int = 42,
    **kwargs,
) -> nx.Graph:
    """
    Constrói o grafo de rede social conforme a topologia escolhida.

    Args:
        topology:  tipo de topologia
        n_agents:  número de nós (agentes)
        seed:      semente para reprodutibilidade
        **kwargs:  parâmetros específicos de cada topologia

    Returns:
        nx.Graph com atributos de grau calculados
    """
    if topology == Topology.RANDOM:
        # p = probabilidade de conexão entre cada par de nós
        p = kwargs.get("p", 0.08)
        G = nx.erdos_renyi_graph(n=n_agents, p=p, seed=seed)

    elif topology == Topology.SCALE_FREE:
        # m = número de arestas que cada novo nó cria ao entrar
        m = kwargs.get("m", 3)
        G = nx.barabasi_albert_graph(n=n_agents, m=m, seed=seed)

    elif topology == Topology.SMALL_WORLD:
        # k = cada nó conectado aos k vizinhos mais próximos
        # p = probabilidade de reconexão aleatória
        k = kwargs.get("k", 6)
        p = kwargs.get("p", 0.15)
        G = nx.watts_strogatz_graph(n=n_agents, k=k, p=p, seed=seed)

    else:
        raise ValueError(f"Topologia desconhecida: {topology}")

    # Garante que o grafo seja conexo (sem nós isolados).
    # Usa um RNG semeado para manter reprodutibilidade entre execuções.
    if not nx.is_connected(G):
        rng = random.Random(seed)
        components = list(nx.connected_components(G))
        for comp in components[1:]:
            u = rng.choice(list(components[0]))
            v = rng.choice(list(comp))
            G.add_edge(u, v)

    return G


def get_hub_nodes(G: nx.Graph, top_k: int = 5) -> list[int]:
    """Retorna os top_k nós com maior grau (supernós / influenciadores)."""
    degree_sorted = sorted(G.degree(), key=lambda x: x[1], reverse=True)
    return [node for node, _ in degree_sorted[:top_k]]


def match_edge_count(graph: nx.Graph, target: int, seed: int) -> nx.Graph:
    """Normaliza a densidade sem desconectar o grafo; altera a família geradora."""
    n = len(graph)
    if not n - 1 <= target <= n * (n - 1) // 2 or not nx.is_connected(graph):
        raise ValueError("Grafo conexo e número viável de arestas são obrigatórios.")
    rng = random.Random(f"edge-count:{seed}")
    before = graph.number_of_edges()
    if before < target:
        graph.add_edges_from(rng.sample(sorted(nx.non_edges(graph)), target - before))
    while graph.number_of_edges() > target:
        bridges = {frozenset(edge) for edge in nx.bridges(graph)}
        candidates = [edge for edge in sorted(graph.edges()) if frozenset(edge) not in bridges]
        graph.remove_edge(*rng.choice(candidates))
    graph.graph.update(edges_before_matching=before, edges_after_matching=target)
    return graph


def get_peripheral_nodes(G: nx.Graph, bottom_k: int = 5) -> list[int]:
    """Retorna os bottom_k nós com menor grau (periféricos)."""
    degree_sorted = sorted(G.degree(), key=lambda x: x[1])
    return [node for node, _ in degree_sorted[:bottom_k]]


def network_stats(G: nx.Graph) -> dict:
    """Calcula estatísticas descritivas da rede."""
    degrees = [d for _, d in G.degree()]
    return {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "avg_degree": sum(degrees) / len(degrees),
        "max_degree": max(degrees),
        "density": nx.density(G),
        "avg_clustering": nx.average_clustering(G),
        "avg_shortest_path": (
            nx.average_shortest_path_length(G)
            if nx.is_connected(G) else None
        ),
    }
