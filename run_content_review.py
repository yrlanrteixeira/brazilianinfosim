"""Revê exposições a partir dos textos gravados, sem executar o LLM."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from metrics.content_review import paired_content_effects, review_exposure, update_review_template
from simulation.persistence import atomic_json


def export_content_review(source: Path, output: Path, annotations_path: Path | None = None):
    annotations_bytes = annotations_path.read_bytes() if annotations_path else None
    annotations = json.loads(annotations_bytes) if annotations_bytes else {}
    records = []
    if source.is_file():
        paths = [source]
    elif (source / "attempts").is_dir():
        records = [json.loads(path.read_text(encoding="utf-8"))
                   for path in sorted((source / "attempts").glob("*.json"))]
        paths = [source / "results" / f"{record['id']}.json"
                 for record in records if record["status"] == "success"]
    else:
        paths = sorted(source.glob("*.json"))
    if not paths:
        raise ValueError("Nenhum resultado completo encontrado.")
    protected_results = {path.resolve() for path in paths}
    protected = set(protected_results)
    if annotations_path:
        protected.add(annotations_path.resolve())
    report_path = output / "exposure.json"
    template_path = output / "review_template.json"
    if report_path.resolve() in protected or template_path.resolve() in protected_results:
        raise ValueError("A saída não pode sobrescrever resultados ou anotações de origem.")
    reports, inventory = {}, {}
    for path in paths:
        raw = path.read_bytes()
        review = review_exposure(json.loads(raw), annotations)
        inventory.update(review.pop("inventory"))
        reports[path.stem] = {
            "source_file": str(path.resolve()), "source_sha256": sha256(raw).hexdigest(),
            **review,
        }
    report = {
        "schema_version": 1, "new_llm_calls": 0,
        "annotations_sha256": sha256(annotations_bytes).hexdigest() if annotations_bytes else None,
        "bounds_meaning": "classification_bounds_not_confidence_intervals",
        "runs": reports, "paired_effects": paired_content_effects(records, reports),
    }
    atomic_json(report_path, report)
    update_review_template(template_path, inventory)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="JSON de resultado, pasta de resultados ou campanha")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotations", type=Path)
    args = parser.parse_args()
    try:
        report = export_content_review(args.source, args.output, args.annotations)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"{len(report['runs'])} resultados revisados; nenhuma chamada ao LLM.")


if __name__ == "__main__":
    main()
