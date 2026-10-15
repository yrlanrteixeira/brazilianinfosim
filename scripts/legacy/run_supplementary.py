"""
run_supplementary.py
Experimento suplementar: testa o TIMING da intervenção.

A matriz principal aplica fact-checkers no tick 10, mas as cascatas saturam
no tick ~3. Aqui comparamos, nos cenarios que ignem, intervencao precoce
(tick 1) contra o controle (sem intervencao), mantendo seed/mensagem fixos.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from simulation.engine import SimulationConfig, InfoSimModel
from network.topology import Topology
from metrics.analysis import summarize_result
import pandas as pd
from simulation.persistence import campaign_directory, save_result

MSG = {
    "saude": ("URGENTE: Médicos escondem que vitamina C em altas doses cura "
              "câncer! Compartilhe antes que a big pharma tire do ar!"),
    "politica": ("Relatório técnico indica que sistema eleitoral precisa "
                 "de auditoria mais detalhada segundo especialistas."),
}

# Cenarios que ignem no controle (extraidos da matriz principal)
CASES = [
    (Topology.RANDOM, "saude", 42),
    (Topology.RANDOM, "politica", 123),
    (Topology.SCALE_FREE, "saude", 123),
    (Topology.SCALE_FREE, "politica", 123),
]

def main():
    OUT_DIR = campaign_directory("timing")

    rows = []
    for topo, msg_name, seed in CASES:
        for interv, tick in [(None, 0), ("factcheckers_hub", 1)]:
            cfg = SimulationConfig(
                n_agents=50, topology=topo, max_ticks=100, seed=seed,
                initial_message=MSG[msg_name], intervention=interv,
                intervention_tick=tick,
                cache_mode="off",
            )
            result = InfoSimModel(cfg).run()
            save_result(result, OUT_DIR / "timing_runs", f"{topo.value}_{msg_name}_{seed}_{interv or 'none'}_t{tick}")
            s = summarize_result(result, with_mutation=False)
            s["msg"] = msg_name
            s["seed"] = seed
            s["interv_tick"] = tick if interv else "-"
            rows.append(s)
            pd.DataFrame(rows).to_csv(OUT_DIR / "supplementary_timing.csv", index=False)
            print(f"{topo.value:16s} {msg_name:9s} seed={seed} "
                  f"interv={interv or 'none':16s}(tick={tick}) -> reach={s['final_reach_pct']:.0f}% "
                  f"crentes={s['final_believers']}")

    df = pd.DataFrame(rows)
    out = OUT_DIR / "supplementary_timing.csv"
    df.to_csv(out, index=False)
    print(f"\nSalvo em {out}")


if __name__ == "__main__":
    main()
