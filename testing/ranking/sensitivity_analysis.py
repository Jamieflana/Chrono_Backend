"""
Ranking weight sensitivity analysis.

Retrieves candidates from SPARQL once (cached to sensitivity_cache.json),
then sweeps weight configurations and reports Accuracy@1, MRR, Recall@3
for each. Outputs a results table and saves to sensitivity_results.json.

Usage:
    cd Backend
    python -m testing.ranking.sensitivity_analysis
"""

from __future__ import annotations

import copy
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

GOLD_PATH = Path(__file__).parent / "all_docs_el_gold.jsonl"
CACHE_PATH = Path(__file__).parent / "sensitivity_cache.json"
OUT_PATH = Path(__file__).parent / "sensitivity_results.json"
DOC_ROOT = BACKEND_DIR.parent / "depositions"

# ---------------------------------------------------------------------------
# Baseline weights (as used in the dissertation)
# ---------------------------------------------------------------------------
PER_BASELINE = {
    "name": 0.32,
    "era": 0.20,
    "residence": 0.18,
    "floruit": 0.12,
    "neural": 0.18,
}
LOC_BASELINE = {
    "name": 0.25,
    "hierarchy": 0.25,
    "type_match": 0.18,
    "historical": 0.12,
    "neural": 0.20,
}


def redistribute(base: dict, target: str, new_val: float) -> dict:
    """Hold one weight at new_val, redistribute the remainder proportionally."""
    others = {k: v for k, v in base.items() if k != target}
    other_sum = sum(others.values())
    remaining = 1.0 - new_val
    result = {k: (v / other_sum) * remaining for k, v in others.items()}
    result[target] = new_val
    return result


# ---------------------------------------------------------------------------
# Weight configurations to evaluate
# ---------------------------------------------------------------------------
CONFIGS: list[tuple[str, dict, dict]] = []

# PER name sweep (0.20 -> 0.44)
for v in [0.20, 0.25, 0.32, 0.38, 0.44]:
    label = f"PER name={v:.2f} (others prop to baseline)"
    CONFIGS.append((label, redistribute(PER_BASELINE, "name", v), LOC_BASELINE))

# PER era sweep (0.10 -> 0.30)
for v in [0.10, 0.15, 0.20, 0.25, 0.30]:
    label = f"PER era={v:.2f} (others prop to baseline)"
    CONFIGS.append((label, redistribute(PER_BASELINE, "era", v), LOC_BASELINE))

# LOC hierarchy sweep (0.15-> 0.35)
for v in [0.15, 0.20, 0.25, 0.30, 0.35]:
    label = f"LOC hierarchy={v:.2f} (others prop to baseline)"
    CONFIGS.append((PER_BASELINE, redistribute(LOC_BASELINE, "hierarchy", v), label))
    CONFIGS[-1] = (label, PER_BASELINE, redistribute(LOC_BASELINE, "hierarchy", v))

# LOC name sweep (0.15 -> 0.35)
for v in [0.15, 0.20, 0.25, 0.30, 0.35]:
    label = f"LOC name={v:.2f} (others prop to baseline)"
    CONFIGS.append((label, PER_BASELINE, redistribute(LOC_BASELINE, "name", v)))


# ---------------------------------------------------------------------------
# Helpers (mirrored from eval_ranking.py)
# ---------------------------------------------------------------------------


def load_gold(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def candidate_uri(c: dict, label: str) -> str:
    if label == "PER":
        return (c.get("person") or "").strip()
    return (c.get("place") or "").strip()


def reciprocal_rank(gold_uri: str, ranked_uris: list[str]) -> float:
    for i, uri in enumerate(ranked_uris, start=1):
        if uri == gold_uri:
            return 1.0 / i
    return 0.0


def hit_at_k(gold_uri: str, ranked_uris: list[str], k: int) -> int:
    return int(gold_uri in ranked_uris[:k])


# ---------------------------------------------------------------------------
# Candidate retrieval + caching
# ---------------------------------------------------------------------------


def build_query_input(rows: list[dict], context: str) -> list[dict]:
    context_lower = (context or "").lower()
    result = []
    cursor: dict[tuple, int] = {}
    for row in rows:
        mention = (row.get("mention") or "").strip()
        label = row.get("label", "")
        key = (label, mention.lower())
        cur = cursor.get(key, 0)
        idx = context_lower.find(mention.lower(), cur) if mention else -1
        if idx < 0 and mention:
            idx = context_lower.find(mention.lower())
        start = idx if idx >= 0 else 0
        end = start + len(mention)
        cursor[key] = end
        result.append(
            {"text": mention, "label": label, "score": 1.0, "start": start, "end": end}
        )
    return result


def retrieve_and_cache(gold: list[dict]) -> list[dict]:
    from services.entity_linking.candidate_retrieval import query_sparql
    from services.new_normalize import normalize_v2

    norm_cache: dict[str, str] = {}
    rows_by_doc: OrderedDict[str, list[dict]] = OrderedDict()
    for i, row in enumerate(gold):
        doc_id = (row.get("doc_id") or f"__row_{i}").strip()
        rows_by_doc.setdefault(doc_id, []).append(row)

    cached_entries = []  # list of {doc_id, rows, ents, loc_graph, context}

    for doc_id, doc_rows in rows_by_doc.items():
        # Try to load document text for context
        context = ""
        doc_num_str = doc_id.replace(".txt", "").split("_")[-1]
        doc_path = DOC_ROOT / f"document_{doc_num_str}.txt"
        if doc_path.exists():
            raw = doc_path.read_text(encoding="utf-8")
            if doc_id not in norm_cache:
                norm_cache[doc_id], _ = normalize_v2(raw)
            context = norm_cache[doc_id]
        if not context:
            context = " ".join(r.get("mention", "") for r in doc_rows)

        query_input = build_query_input(doc_rows, context)
        ents, loc_graph = query_sparql(query_input)
        data = {"visual": context, "normalized": context, "ents": ents}
        cached_entries.append(
            {
                "doc_id": doc_id,
                "rows": doc_rows,
                "ents": ents,
                "loc_graph": loc_graph,
                "context": context,
            }
        )
        print(f"  Retrieved {doc_id}: {len(doc_rows)} mentions")

    return cached_entries


# ---------------------------------------------------------------------------
# Ranking with patched weights
# ---------------------------------------------------------------------------


def rank_with_weights(
    cached_entries: list[dict], per_w: dict, loc_w: dict
) -> list[dict]:
    """Re-rank all cached candidate sets using given weights. Returns per-mention detail rows."""
    import importlib
    import services.ranking.candidate_ranker as ranker_mod

    # Patch weights into the ranker class for this run
    original_score_person = ranker_mod.CandidateRanker.score_person_candidate
    original_score_loc = ranker_mod.CandidateRanker.score_location_candidate

    def patched_score_person(self, mention, candidate, label):
        features = {
            "name": self.get_name_score(mention, candidate),
            "era": self.get_era_score(candidate, label),
            "residence": self.get_residence_score(candidate),
            "floruit": self.get_floruit_score(candidate),
            "neural": self.get_neural_score(mention, candidate, label),
        }
        candidate["_feature_scores"] = features
        return sum(features[f] * per_w[f] for f in features)

    def patched_score_loc(self, mention, candidate, label):
        features = {
            "name": self.get_location_name_score(mention, candidate),
            "hierarchy": self.get_hierarchy_score(candidate, mention),
            "type_match": self.get_type_score(candidate, mention, label),
            "historical": self.get_historical_score(candidate),
            "neural": self.get_neural_score(mention, candidate, label),
        }
        candidate["_feature_scores"] = features
        return sum(features[f] * loc_w[f] for f in features)

    ranker_mod.CandidateRanker.score_person_candidate = patched_score_person
    ranker_mod.CandidateRanker.score_location_candidate = patched_score_loc

    details = []
    try:
        for entry in cached_entries:
            doc_id = entry["doc_id"]
            doc_rows = entry["rows"]
            context = entry["context"]
            loc_graph = entry["loc_graph"]

            # Deep copy ents so scores from previous config don't persist
            ents_copy = copy.deepcopy(entry["ents"])
            data = {"visual": context, "normalized": context, "ents": ents_copy}

            ranker = ranker_mod.CandidateRanker(data, loc_graph)
            ranker.rank(top_k=0)

            for idx, row in enumerate(doc_rows):
                label = row["label"]
                gold_uri = row["gold_uri"].strip()
                entity_block = ents_copy[idx] if idx < len(ents_copy) else {}
                candidates = entity_block.get("candidate_entities", [])
                ranked_uris = [
                    u for u in (candidate_uri(c, label) for c in candidates) if u
                ]

                details.append(
                    {
                        "doc_id": doc_id,
                        "mention": row["mention"],
                        "label": label,
                        "gold_uri": gold_uri,
                        "ranked_uris": ranked_uris,
                        "rr": reciprocal_rank(gold_uri, ranked_uris),
                        "hit@1": hit_at_k(gold_uri, ranked_uris, 1),
                        "hit@3": hit_at_k(gold_uri, ranked_uris, 3),
                        "hit@5": hit_at_k(gold_uri, ranked_uris, 5),
                    }
                )
    finally:
        ranker_mod.CandidateRanker.score_person_candidate = original_score_person
        ranker_mod.CandidateRanker.score_location_candidate = original_score_loc

    return details


def compute_summary(details: list[dict]) -> dict:
    n = len(details)
    per = [d for d in details if d["label"] == "PER"]
    loc = [d for d in details if d["label"] == "LOC"]

    def metrics(rows):
        if not rows:
            return {"n": 0, "acc@1": 0.0, "mrr": 0.0, "recall@3": 0.0}
        total = len(rows)
        return {
            "n": total,
            "acc@1": sum(r["hit@1"] for r in rows) / total,
            "mrr": sum(r["rr"] for r in rows) / total,
            "recall@3": sum(r["hit@3"] for r in rows) / total,
        }

    return {
        "overall": metrics(details),
        "PER": metrics(per),
        "LOC": metrics(loc),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    gold = load_gold(GOLD_PATH)
    print(f"Loaded {len(gold)} gold mentions from {GOLD_PATH.name}")

    # Phase 1: retrieve (or load from cache)
    if CACHE_PATH.exists():
        print(f"\nLoading cached candidates from {CACHE_PATH.name} ...")
        cached_entries = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    else:
        print("\nRetrieving candidates from SPARQL (this may take a minute) ...")
        cached_entries = retrieve_and_cache(gold)
        CACHE_PATH.write_text(json.dumps(cached_entries, indent=2), encoding="utf-8")
        print(f"Cached to {CACHE_PATH.name}")

    # Phase 2: sweep weight configurations
    print(f"\nRunning {len(CONFIGS)} weight configurations ...\n")
    all_results = []
    header = f"{'Configuration':<58} {'Acc@1':>6} {'MRR':>6} {'R@3':>5} | {'PER Acc@1':>9} {'LOC Acc@1':>9}"
    print(header)
    print("-" * len(header))

    for config_label, per_w, loc_w in CONFIGS:
        details = rank_with_weights(cached_entries, per_w, loc_w)
        summary = compute_summary(details)
        ov = summary["overall"]
        per_s = summary["PER"]
        loc_s = summary["LOC"]

        # Mark baseline row
        is_baseline = per_w == PER_BASELINE and loc_w == LOC_BASELINE
        marker = " *" if is_baseline else "  "
        row_label = config_label[:56]
        print(
            f"{row_label:<58}{marker}"
            f"{ov['acc@1']:>6.4f} {ov['mrr']:>6.4f} {ov['recall@3']:>5.3f}"
            f" | {per_s['acc@1']:>9.4f} {loc_s['acc@1']:>9.4f}"
        )
        all_results.append(
            {
                "config": config_label,
                "per_weights": per_w,
                "loc_weights": loc_w,
                "summary": summary,
            }
        )

    print("\n* = dissertation baseline\n")

    OUT_PATH.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"Full results saved to {OUT_PATH.name}")


if __name__ == "__main__":
    main()
