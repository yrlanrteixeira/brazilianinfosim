"""
simulation/recorder.py
Gravação de execução, insumo do replay visual.

A rede fica de fora: topologia, n_agents e seed a reconstroem por
build_network, que é determinístico.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunRecorder:
    meta: dict
    ticks: list[dict] = field(default_factory=list)

    def snapshot(self, model) -> None:
        agents = {
            str(node_id): {
                "has_seen": bool(a.has_seen_disinformation),
                "belief": round(float(a.belief_level), 3),
                "agent_type": a.profile.agent_type.value,
            }
            for node_id, a in model.agents_by_id.items()
        }
        believers = sum(
            1 for a in model.agents_by_id.values() if a.belief_level > 0.5
        )
        self.ticks.append({
            "tick": model.tick,
            "agents": agents,
            "reached": model._count_reached(),
            "believers": believers,
            "api_calls": model.llm.stats.get("api_calls", 0),
            "refusals": sum(a.refusal_count for a in model.agents_by_id.values()),
        })

    def to_dict(self) -> dict:
        return {"meta": self.meta, "ticks": self.ticks}

    def save(self, path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return target
