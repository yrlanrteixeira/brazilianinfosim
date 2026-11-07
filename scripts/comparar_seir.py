"""
Compara o alcance medido nos agentes LLM com o de referências SIR e SEIR
rodadas no mesmo grafo, com a mesma origem e o mesmo horizonte.

O pareamento é por execução: cada referência recebe a rede e o nó de injeção
daquela execução, de modo que a diferença não vem de estrutura nem de ponto de
partida. As seeds estruturais são divididas em ajuste e avaliação, porque medir
aderência na mesma amostra que escolheu os parâmetros não mede nada.

A estatística é a distância de Kolmogorov-Smirnov entre as distribuições de
alcance, que compara a forma inteira e não só a média.

    python scripts/comparar_seir.py data/outputs/tcc2/conclusao
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import networkx as nx

from recompute_lineage import id_column, load_result
from simulation.baseline import run_epidemic

TRANSMISSAO = (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.80)
RECUPERACAO = (0.10, 0.30, 0.50)


def horizonte_por_condicao(rows: list[dict]) -> dict[str, int]:
    """O horizonte configurado não é gravado; o maior `ticks_run` da condição o
    revela, porque as execuções que não se extinguem param nele."""
    maior: dict[str, int] = {}
    for row in rows:
        condicao = row["condition"]
        maior[condicao] = max(maior.get(condicao, 1), int(row["ticks_run"]))
    return maior


def dividir_seeds(seeds: list[str]) -> tuple[set[str], set[str]]:
    """Divide por seed, não por execução. A lista chega com repetição, uma
    entrada por execução; sem o conjunto, a mesma seed cai dos dois lados."""
    ordenadas = sorted(set(seeds))
    return set(ordenadas[::2]), set(ordenadas[1::2])


def ks(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return float("nan")
    pontos = sorted(set(a) | set(b))
    maior = 0.0
    for x in pontos:
        fa = sum(1 for v in a if v <= x) / len(a)
        fb = sum(1 for v in b if v <= x) / len(b)
        maior = max(maior, abs(fa - fb))
    return round(maior, 4)


def alcance_referencia(caso: dict, transmissao: float, recuperacao: float,
                       latente: bool) -> float:
    grafo = nx.Graph()
    grafo.add_nodes_from(range(caso["n_agents"]))
    grafo.add_edges_from(caso["edges"])
    linhas = run_epidemic(grafo, caso["source"], caso["horizonte"],
                          transmissao, recuperacao, caso["seed"], latent=latente)
    return round(linhas[-1]["reached"] / caso["n_agents"] * 100, 2)


def carregar(campaign: Path) -> list[dict]:
    pastas = ([campaign] if (campaign / "runs_corrigido.csv").exists()
              else sorted(p.parent for p in campaign.glob("*/runs_corrigido.csv")))
    casos = []
    for pasta in pastas:
        rows = [r for r in csv.DictReader((pasta / "runs_corrigido.csv").open(encoding="utf-8"))
                if r.get("reach_strict_pct")]
        if not rows:
            continue
        identificador = id_column(rows[0])
        horizontes = horizonte_por_condicao(rows)
        for row in rows:
            caminho = pasta / "results" / f"{row[identificador]}.json"
            if not caminho.exists():
                continue
            estado = load_result(caminho).get("initial_state", {})
            if estado.get("injection_node") is None or not estado.get("edges"):
                continue
            casos.append({
                "id": row[identificador], "seed": int(row["seed"]),
                "n_agents": int(row["n_agents"]),
                "source": estado["injection_node"],
                "edges": [tuple(e) for e in estado["edges"]],
                "horizonte": horizontes[row["condition"]],
                "llm": float(row["reach_strict_pct"]),
            })
    return casos


def melhor_ajuste(casos: list[dict], latente: bool) -> tuple[float, float, float]:
    alvo = [c["llm"] for c in casos]
    melhor = (float("nan"), float("nan"), float("inf"))
    for transmissao in TRANSMISSAO:
        for recuperacao in RECUPERACAO:
            referencia = [alcance_referencia(c, transmissao, recuperacao, latente)
                          for c in casos]
            distancia = ks(alvo, referencia)
            if distancia < melhor[2]:
                melhor = (transmissao, recuperacao, distancia)
    return melhor


def so_emissor(valores: list[float], n_agents: int) -> float:
    limite = 100.0 / n_agents + 1e-9
    return round(sum(1 for v in valores if v <= limite) / len(valores), 3)


def avaliar(casos: list[dict], transmissao: float, recuperacao: float,
            latente: bool) -> dict:
    alvo = [c["llm"] for c in casos]
    referencia = [alcance_referencia(c, transmissao, recuperacao, latente) for c in casos]
    n_agents = casos[0]["n_agents"]
    return {
        "modelo": "SEIR" if latente else "SIR",
        "transmissao": transmissao, "recuperacao": recuperacao,
        "n": len(casos), "ks": ks(alvo, referencia),
        "media_llm": round(sum(alvo) / len(alvo), 2),
        "media_referencia": round(sum(referencia) / len(referencia), 2),
        "so_emissor_llm": so_emissor(alvo, n_agents),
        "so_emissor_referencia": so_emissor(referencia, n_agents),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()

    casos = carregar(args.campaign)
    if not casos:
        raise SystemExit(f"Nenhuma execução com grafo gravado em {args.campaign}.")
    ajuste_seeds, avaliacao_seeds = dividir_seeds([str(c["seed"]) for c in casos])
    ajuste = [c for c in casos if str(c["seed"]) in ajuste_seeds]
    avaliacao = [c for c in casos if str(c["seed"]) in avaliacao_seeds]
    print(f"{len(casos)} execuções com grafo; ajuste {len(ajuste)}, "
          f"avaliação {len(avaliacao)}, seeds {len(ajuste_seeds)}/{len(avaliacao_seeds)}")

    linhas = []
    for latente in (False, True):
        transmissao, recuperacao, distancia = melhor_ajuste(ajuste, latente)
        print(f"\n{'SEIR' if latente else 'SIR'}: melhor ajuste "
              f"transmissão {transmissao}, recuperação {recuperacao}, KS {distancia}")
        linha = avaliar(avaliacao, transmissao, recuperacao, latente)
        linhas.append(linha)
        for chave, valor in linha.items():
            print(f"    {chave}: {valor}")

    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        with args.saida.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=list(linhas[0]))
            writer.writeheader()
            writer.writerows(linhas)
        print(f"\n{args.saida}")


if __name__ == "__main__":
    main()
