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
from simulation.persistence import campaign_directory, save_result


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
        intervention_tick=args.intervention_tick,
        cache_mode=args.cache_mode,
        llm_provider=args.provider,
        llm_model=args.model,
    )
    output_dir = campaign_directory("single")
    label = f"sim_{config.topology.value}_{config.seed}_{config.intervention or 'none'}_t{config.intervention_tick}"
    if args.record:
        config.record_path = str(Path("data/outputs/recordings") / f"{output_dir.name}_{label}.json")

    print(f"\n{'='*60}")
    print(f"  BrazilianInfoSim")
    print(f"  Topologia: {config.topology.value}")
    print(f"  Agentes: {config.n_agents} | Ticks: {config.max_ticks}")
    print(f"  Intervenção: {config.intervention or 'nenhuma'}")
    print(f"{'='*60}\n")

    model = InfoSimModel(config)
    result = model.run()

    save_result(result, output_dir, label)

    summary = summarize_result(result)
    print("\n📊 Resultados:")
    for k, v in summary.items():
        print(f"  {k:30s}: {v}")

    # Salva gráfico
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / f"{label}.png"
    plot_simulation(result, save_path=str(plot_path))


def run_all(args) -> None:
    """Roda a matriz experimental completa.

    3 topologias × 2 intervenções × 2 mensagens × 3 seeds = 36 runs.
    """
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
    output_dir = campaign_directory("matrix")

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
                        intervention_tick=args.intervention_tick, cache_mode=args.cache_mode,
                        llm_provider=args.provider, llm_model=args.model,
                    )
                    label = f"{topology.value}_{intervention or 'none'}_{msg_name}_{seed}"
                    if args.record:
                        config.record_path = str(
                            Path("data/outputs/recordings") / f"{output_dir.name}_{label}.json"
                        )
                    model = InfoSimModel(config)
                    result = model.run()
                    save_result(result, output_dir / "runs", label)
                    results.append(result)

    # Tabela comparativa
    df = compare_results(results)
    output_path = output_dir / "experiment_matrix.csv"
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
    parser.add_argument("--provider",    type=str,  default=None,
                        choices=["ollama", "anthropic"],
                        help="Provedor de LLM (default: env LLM_PROVIDER ou 'ollama')")
    parser.add_argument("--intervention-tick", type=int, default=0,
                        help="Tick da intervenção; 0 aplica antes da primeira decisão")
    parser.add_argument("--cache-mode", choices=["off", "exact", "semantic"], default="off",
                        help="Campanhas científicas devem manter off")
    parser.add_argument("--model",       type=str,  default=None,
                        help="Modelo LLM (default: env LLM_MODEL ou default do provider)")
    parser.add_argument("--all",         action="store_true",            help="Roda matriz experimental completa")
    parser.add_argument("--record", action="store_true",
                        help="Salva cada execução em data/outputs/recordings para replay")
    args = parser.parse_args()

    # Só exige a chave da Anthropic quando o provider efetivo for "anthropic".
    effective_provider = (args.provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
    if effective_provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ provider=anthropic mas ANTHROPIC_API_KEY não encontrada. "
              "Configure o .env ou use --provider ollama")
        sys.exit(1)

    if args.all:
        run_all(args)
    else:
        run_single(args)


if __name__ == "__main__":
    main()
