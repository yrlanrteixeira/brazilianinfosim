"""
run_simulation.py
Ponto de entrada principal do BrazilianInfoSim.

Uso:
    python run_simulation.py                         # configuração padrão
    python run_simulation.py --topology scale_free   # topologia específica
    python run_simulation.py --agents 100 --ticks 50 # tamanho customizado
    python run_simulation.py --all                   # roda matriz completa
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from simulation.engine import SimulationConfig, InfoSimModel
from network.topology import Topology
from metrics.analysis import plot_simulation, compare_results, summarize_result


def run_single(args) -> None:
    """Roda uma simulação única com os parâmetros fornecidos."""
    topology_map = {
        "random":      Topology.RANDOM,
        "scale_free":  Topology.SCALE_FREE,
        "small_world": Topology.SMALL_WORLD,
    }

    config = SimulationConfig(
        n_agents=args.agents,
        topology=topology_map[args.topology],
        max_ticks=args.ticks,
        seed=args.seed,
        intervention=args.intervention or None,
    )

    print(f"\n{'='*60}")
    print(f"  BrazilianInfoSim")
    print(f"  Topologia: {config.topology.value}")
    print(f"  Agentes: {config.n_agents} | Ticks: {config.max_ticks}")
    print(f"  Intervenção: {config.intervention or 'nenhuma'}")
    print(f"{'='*60}\n")

    model = InfoSimModel(config)
    result = model.run()

    summary = summarize_result(result)
    print("\n📊 Resultados:")
    for k, v in summary.items():
        print(f"  {k:30s}: {v}")

    # Salva gráfico
    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / f"sim_{config.topology.value}_{config.seed}.png"
    plot_simulation(result, save_path=str(plot_path))


def run_all() -> None:
    """Roda a matriz experimental completa (12 configurações × 3 seeds)."""
    topologies = [Topology.RANDOM, Topology.SCALE_FREE, Topology.SMALL_WORLD]
    interventions = [None, "factcheckers_hub"]
    messages = {
        "saude_emocional": (
            "URGENTE: Médicos escondem que vitamina C em altas doses cura "
            "câncer! Compartilhe antes que a big pharma tire do ar!"
        ),
        "politica_baixa": (
            "Relatório técnico indica que sistema eleitoral precisa "
            "de auditoria mais detalhada segundo especialistas."
        ),
    }
    seeds = [42, 123, 999]

    results = []
    total = len(topologies) * len(interventions) * len(messages) * len(seeds)
    count = 0

    for topology in topologies:
        for intervention in interventions:
            for msg_name, msg_content in messages.items():
                for seed in seeds:
                    count += 1
                    print(f"\n[{count}/{total}] {topology.value} | "
                          f"interv={intervention} | msg={msg_name} | seed={seed}")
                    config = SimulationConfig(
                        n_agents=50,
                        topology=topology,
                        max_ticks=100,
                        seed=seed,
                        initial_message=msg_content,
                        intervention=intervention,
                    )
                    model = InfoSimModel(config)
                    result = model.run()
                    results.append(result)

    # Tabela comparativa
    df = compare_results(results)
    output_path = Path("data/outputs/experiment_matrix.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n✅ Matriz experimental salva em: {output_path}")
    print(df.groupby(["topology", "intervention"])["final_reach_pct"].mean().round(1))


def main():
    parser = argparse.ArgumentParser(description="BrazilianInfoSim")
    parser.add_argument("--agents",      type=int,  default=50,          help="Número de agentes")
    parser.add_argument("--ticks",       type=int,  default=100,         help="Máximo de ticks")
    parser.add_argument("--topology",    type=str,  default="scale_free",
                        choices=["random", "scale_free", "small_world"],  help="Topologia da rede")
    parser.add_argument("--seed",        type=int,  default=42,          help="Seed aleatória")
    parser.add_argument("--intervention",type=str,  default=None,
                        choices=["factcheckers_hub", "factcheckers_peripheral", "remove_hubs"],
                        help="Tipo de intervenção")
    parser.add_argument("--all",         action="store_true",            help="Roda matriz experimental completa")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY não encontrada. Configure o arquivo .env")
        sys.exit(1)

    if args.all:
        run_all()
    else:
        run_single(args)


if __name__ == "__main__":
    main()
