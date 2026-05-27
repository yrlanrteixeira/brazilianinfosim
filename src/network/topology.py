"""
network/topology.py
Geração das topologias de rede social para simulação.
"""

from enum import Enum
import networkx as nx
import random


class Topology(str, Enum):
    RANDOM       = "erdos_renyi"       # linha de base
    SCALE_FREE   = "barabasi_albert"   # Twitter/Instagram
    SMALL_WORLD  = "watts_strogatz"    # WhatsApp (grupos familiares)


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
