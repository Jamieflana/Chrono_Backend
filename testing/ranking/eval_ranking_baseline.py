"""
Naive candidate ranking baseline for entity linking.

This baseline reuses the same retrieval step and gold dataset as the main
ranking evaluation, but orders candidates using surface-form similarity only.

Primary metrics:
  - Accuracy@1
  - MRR
  - Recall@k

Expected gold input (JSONL preferred):
  {"doc_id":"doc1","mention":"Jane Armstrong","label":"PER","gold_uri":"https://...","context":"optional"}
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[2]
ORIGINAL_CWD = Path.cwd()
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


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


def reciprocal_rank(gold_uri: str, ranked_uris: List[str]) -> float:
    for i, uri in enumerate(ranked_uris, start=1):
        if uri == gold_uri:
            return 1.0 / i
    return 0.0


def hit_at_k(gold_uri: str, ranked_uris: List[str], k: int) -> int:
    return int(gold_uri in ranked_uris[:k])


def extract_doc_number(doc_id: str) -> str | None:
    if not doc_id:
        return None
    match = re.search(r"(?:doc(?:ument)?_?)(\d+)", doc_id, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def resolve_doc_context(
    rows: List[Dict],
    doc_root: Path,
    normalize_v2,
    cache: dict[str, str],
) -> str:
    for row in rows:
        row_context = (row.get("context") or "").strip()
        if row_context:
            return row_context

    doc_id = (rows[0].get("doc_id") or "").strip() if rows else ""
    doc_num = extract_doc_number(doc_id)
    if not doc_num:
        return ""

    cache_key = f"document_{doc_num}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    doc_path = doc_root / f"document_{doc_num}.txt"
    if not doc_path.exists():
        return ""

    raw_text = doc_path.read_text(encoding="utf-8")
    normalized_text, _ = normalize_v2(raw_text)
    cache[cache_key] = normalized_text
    return normalized_text


def to_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_query_input(rows: List[Dict], context: str) -> List[Dict]:
    query_input: List[Dict] = []
    normalized_context = context or ""
    context_lower = normalized_context.lower()
    cursor_by_mention: dict[tuple[str, str], int] = {}

    for row in rows:
        mention = (row.get("mention") or "").strip()
        label = row.get("label", "")

        start = to_int(row.get("start"), -1)
        end = to_int(row.get("end"), -1)
        has_valid_span = (
            start >= 0
            and end > start
            and end <= len(normalized_context)
            and mention != ""
        )

        if not has_valid_span:
            mention_key = (label, mention.lower())
            cursor = cursor_by_mention.get(mention_key, 0)
            idx = context_lower.find(mention.lower(), cursor) if mention else -1
            if idx < 0 and mention:
                idx = context_lower.find(mention.lower())
            if idx >= 0:
                start = idx
                end = idx + len(mention)
                cursor_by_mention[mention_key] = end
            else:
                start = 0
                end = len(mention)

        query_input.append(
            {
                "text": mention,
                "label": label,
                "score": 1.0,
                "start": start,
                "end": end,
            }
        )

    return query_input


def normalized_string(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def get_candidate_label(candidate: Dict, label: str) -> str:
    preferred = (candidate.get("label") or "").strip()
    if preferred:
        return preferred

    if label == "PER":
        fallbacks = (
            candidate.get("name"),
            candidate.get("personLabel"),
            candidate.get("person"),
        )
    else:
        fallbacks = (
            candidate.get("english_label"),
            candidate.get("placeLabel"),
            candidate.get("place"),
        )

    for value in fallbacks:
        text = (value or "").strip()
        if text:
            return text
    return ""


def baseline_score(mention: str, candidate_label: str) -> float:
    mention_norm = normalized_string(mention)
    label_norm = normalized_string(candidate_label)

    if not mention_norm or not label_norm:
        return 0.0

    exact_match = 1.0 if mention_norm == label_norm else 0.0
    seq_sim = difflib.SequenceMatcher(None, mention_norm, label_norm).ratio()
    token_seq_sim = difflib.SequenceMatcher(
        None,
        " ".join(sorted(mention_norm.split())),
        " ".join(sorted(label_norm.split())),
    ).ratio()

    return (0.5 * exact_match) + (0.3 * seq_sim) + (0.2 * token_seq_sim)


def rank_candidates_baseline(mention: str, label: str, candidates: List[Dict]) -> List[Dict]:
    scored = []
    for index, candidate in enumerate(candidates):
        candidate_label = get_candidate_label(candidate, label)
        score = baseline_score(mention, candidate_label)
        scored.append((score, index, candidate))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, _, candidate in scored]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate naive ranking baseline.")
    parser.add_argument(
        "--gold",
        type=Path,
        default=BACKEND_DIR / "testing" / "pipeline_tests" / "el_gold.jsonl",
        help="Path to gold mentions JSONL/JSON.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=BACKEND_DIR / "testing" / "ranking" / "ranking_baseline_results_all_docs.json",
        help="Where to write evaluation output JSON.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Optional cutoff after baseline ordering. Use 0 for no truncation.",
    )
    parser.add_argument(
        "--doc-root",
        type=Path,
        default=BACKEND_DIR.parent / "depositions",
        help="Directory containing document_X.txt files for context normalization.",
    )
    args = parser.parse_args()
    args.gold = args.gold if args.gold.is_absolute() else (ORIGINAL_CWD / args.gold).resolve()
    args.out = args.out if args.out.is_absolute() else (ORIGINAL_CWD / args.out).resolve()
    args.doc_root = (
        args.doc_root
        if args.doc_root.is_absolute()
        else (ORIGINAL_CWD / args.doc_root).resolve()
    )

    from services.entity_linking.candidate_retrieval import query_sparql
    from services.new_normalize import normalize_v2

    gold = load_gold(args.gold)
    for i, row in enumerate(gold):
        validate_row(row, i)

    ks = (1, 3, 5)
    total = len(gold)
    retrieved_coverage = 0
    acc1 = 0
    mrr_sum = 0.0
    recall_hits = {k: 0 for k in ks}
    details = []
    normalized_context_cache: dict[str, str] = {}
    rows_by_doc: "OrderedDict[str, List[Dict]]" = OrderedDict()

    for i, row in enumerate(gold):
        doc_id = (row.get("doc_id") or "").strip() or f"__row_{i}"
        rows_by_doc.setdefault(doc_id, []).append(row)

    for doc_id, doc_rows in rows_by_doc.items():
        context = resolve_doc_context(
            doc_rows, args.doc_root, normalize_v2, normalized_context_cache
        )
        if not context:
            context = (doc_rows[0].get("mention") or "").strip()

        query_input = build_query_input(doc_rows, context)
        ents, _ = query_sparql(query_input)

        for idx, row in enumerate(doc_rows):
            mention = row["mention"].strip()
            label = row["label"]
            gold_uri = row["gold_uri"].strip()
            entity_block = ents[idx] if idx < len(ents) else {}
            candidates = entity_block.get("candidate_entities", [])
            ranked_candidates = rank_candidates_baseline(mention, label, candidates)
            if args.top_k and len(ranked_candidates) > args.top_k:
                ranked_candidates = ranked_candidates[: args.top_k]

            ranked_uris = [
                u for u in (candidate_uri(c, label) for c in ranked_candidates) if u
            ]

            was_retrieved = int(gold_uri in ranked_uris)
            retrieved_coverage += was_retrieved

            rr = reciprocal_rank(gold_uri, ranked_uris)
            mrr_sum += rr
            if ranked_uris and ranked_uris[0] == gold_uri:
                acc1 += 1
            for k in ks:
                recall_hits[k] += hit_at_k(gold_uri, ranked_uris, k)

            details.append(
                {
                    "doc_id": row.get("doc_id", doc_id),
                    "mention": mention,
                    "label": label,
                    "gold_uri": gold_uri,
                    "retrieved": was_retrieved,
                    "ranked_uris": ranked_uris,
                    "rr": rr,
                    "hit@1": hit_at_k(gold_uri, ranked_uris, 1),
                    "hit@3": hit_at_k(gold_uri, ranked_uris, 3),
                    "hit@5": hit_at_k(gold_uri, ranked_uris, 5),
                }
            )

    summary = {
        "total_mentions": total,
        "retrieval_coverage": (retrieved_coverage / total) if total else 0.0,
        "accuracy@1": (acc1 / total) if total else 0.0,
        "mrr": (mrr_sum / total) if total else 0.0,
        "recall@1": (recall_hits[1] / total) if total else 0.0,
        "recall@3": (recall_hits[3] / total) if total else 0.0,
        "recall@5": (recall_hits[5] / total) if total else 0.0,
    }

    output = {
        "summary": summary,
        "details": details,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
