"""
Candidate retrieval evaluation for entity linking.

Evaluates unordered candidate-set coverage (not ranking):
  - set_recall: gold URI appears anywhere in the retrieved candidate set
  - avg_candidates_per_mention
  - avg_candidates_when_hit / avg_candidates_when_miss

Expected gold input (JSONL preferred):
  {"doc_id":"doc1","mention":"Jane Armstrong","label":"PER","gold_uri":"https://...","context":"optional"}

Also supports JSON array with the same keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


def load_gold(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Gold file not found: {path}")

    if path.suffix.lower() == ".jsonl":
        rows: List[Dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, list):
        raise ValueError("JSON gold file must be a list of records.")
    return obj


def validate_row(row: Dict, idx: int) -> None:
    required = ("mention", "label", "gold_uri")
    missing = [k for k in required if not row.get(k)]
    if missing:
        raise ValueError(f"Row {idx} missing required fields: {missing}")
    if row["label"] not in ("PER", "LOC"):
        raise ValueError(f"Row {idx} has invalid label: {row['label']}")


def candidate_uri(c: Dict, label: str) -> str:
    if label == "PER":
        return (c.get("person") or "").strip()
    return (c.get("place") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate candidate retrieval.")
    parser.add_argument(
        "--gold",
        type=Path,
        default=BACKEND_DIR / "testing" / "pipeline_tests" / "el_gold.jsonl",
        help="Path to gold mentions JSONL/JSON.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=BACKEND_DIR / "testing" / "retrieval" / "retrieval_results.json",
        help="Where to write evaluation output JSON.",
    )
    args = parser.parse_args()

    from entity_linking.candidate_retrieval import (
        EARLY_MODERN_ERA,
        query_location_entity,
        query_person_entity,
    )

    gold = load_gold(args.gold)
    for i, row in enumerate(gold):
        validate_row(row, i)

    total = len(gold)
    per_label_counts = {"PER": 0, "LOC": 0}
    per_label_hits = {"PER": 0, "LOC": 0}
    overall_hits = 0
    total_candidates = 0
    hit_candidates_total = 0
    miss_candidates_total = 0
    miss_count = 0
    details = []

    for row in gold:
        mention = row["mention"].strip()
        label = row["label"]
        gold_uri = row["gold_uri"].strip()

        if label == "PER":
            candidates = query_person_entity(mention, EARLY_MODERN_ERA)
        else:
            candidates = query_location_entity(mention, EARLY_MODERN_ERA)

        uris = [u for u in (candidate_uri(c, label) for c in candidates) if u]
        total_candidates += len(uris)
        per_label_counts[label] += 1

        hit = int(gold_uri in uris)
        overall_hits += hit
        per_label_hits[label] += hit
        if hit:
            hit_candidates_total += len(uris)
        else:
            miss_count += 1
            miss_candidates_total += len(uris)

        details.append(
            {
                "doc_id": row.get("doc_id", ""),
                "mention": mention,
                "label": label,
                "gold_uri": gold_uri,
                "retrieved_count": len(uris),
                "retrieved_uris": uris,
                "set_hit": hit,
            }
        )

    def ratio(num: int, den: int) -> float:
        return (num / den) if den else 0.0

    summary = {
        "total_mentions": total,
        "avg_candidates_per_mention": ratio(total_candidates, total),
        "set_recall": ratio(overall_hits, total),
        "avg_candidates_when_hit": ratio(hit_candidates_total, overall_hits),
        "avg_candidates_when_miss": ratio(miss_candidates_total, miss_count),
        "by_label": {},
    }

    for lbl in ("PER", "LOC"):
        n = per_label_counts[lbl]
        summary["by_label"][lbl] = {
            "count": n,
            "set_recall": ratio(per_label_hits[lbl], n),
        }

    result = {"summary": summary, "details": details}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
