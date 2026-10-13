"""Referências SIR e SEIR discretas, sem reinfecção e sem texto."""

import random


def run_epidemic(graph, source, max_ticks, transmission, recovery, seed, latent=False):
    """I transmite por aresta antes da recuperação; E espera uma rodada."""
    if not 0 <= transmission <= 1 or not 0 <= recovery <= 1:
        raise ValueError("Probabilidades devem estar entre zero e um.")
    if source not in graph or max_ticks < 1:
        raise ValueError("Emissor e horizonte inválidos.")
    rng = random.Random(seed)
    susceptible = set(graph) - {source}
    exposed, infectious, recovered = set(), {source}, set()
    ever_infectious = {source}
    rows = []
    for tick in range(max_ticks + 1):
        rows.append({"tick": tick, "S": len(susceptible), "E": len(exposed),
                     "I": len(infectious), "R": len(recovered),
                     "reached": len(graph) - len(susceptible),
                     "ever_infectious": len(ever_infectious)})
        if tick == max_ticks or not (exposed or infectious):
            break
        new_exposed = set()
        for node in sorted(infectious):
            for neighbor in sorted(graph.neighbors(node)):
                if neighbor in susceptible and rng.random() < transmission:
                    new_exposed.add(neighbor)
        new_recovered = {node for node in sorted(infectious) if rng.random() < recovery}
        susceptible -= new_exposed
        infectious = (infectious - new_recovered) | exposed | (set() if latent else new_exposed)
        recovered |= new_recovered
        exposed = new_exposed if latent else set()
        ever_infectious |= infectious
    return rows
