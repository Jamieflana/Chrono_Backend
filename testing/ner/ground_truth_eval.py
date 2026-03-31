import argparse
import csv
import json
import sys
from pathlib import Path

# Add the Backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from services.filter_entities import filter_ner_entities
from services.ner_engines import BertNER
from services.ner_post_processing import merge_adjacent_spans
from services.new_normalize import normalize_v2

# Toggle behavior here:
# - PROCESS_ALL = True  -> use all entries
# - PROCESS_ALL = False -> use only SINGLE_ENTRY_INDEX (0-based)
PROCESS_ALL = True
SINGLE_ENTRY_INDEX = 0


def load_ground_truth() -> list[dict]:
    gt_path = Path(__file__).with_name("ground_truth.json")
    with gt_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("ground_truth.json must contain a JSON list.")
    return data


def to_span_set(entities: list[dict]) -> set[tuple[int, int, str]]:
    spans = set()
    for ent in entities:
        start = int(ent.get("start", -1))
        end = int(ent.get("end", -1))
        label = str(ent.get("label", ""))
        if start >= 0 and end > start and label:
            spans.add((start, end, label))
    return spans


def evaluate(gold_entities: list[dict], pred_entities: list[dict]) -> dict:
    gold_set = to_span_set(gold_entities)
    pred_set = to_span_set(pred_entities)

    tp = gold_set & pred_set
    fp = pred_set - gold_set
    fn = gold_set - pred_set

    precision = len(tp) / len(pred_set) if pred_set else 0.0
    recall = len(tp) / len(gold_set) if gold_set else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    return {
        "gold_count": len(gold_set),
        "pred_count": len(pred_set),
        "tp_count": len(tp),
        "fp_count": len(fp),
        "fn_count": len(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def print_metrics(title: str, m: dict) -> None:
    print(f"\n--- {title} ---")
    print(f"Gold: {m['gold_count']}  Pred: {m['pred_count']}")
    print(f"TP: {m['tp_count']}  FP: {m['fp_count']}  FN: {m['fn_count']}")
    print(
        f"Precision: {m['precision']:.4f}  Recall: {m['recall']:.4f}  F1: {m['f1']:.4f}"
    )


def print_raw_vs_norm_diff(raw_preds: list[dict], norm_projected: list[dict]) -> None:
    raw_set = to_span_set(raw_preds)
    norm_set = to_span_set(norm_projected)
    only_raw = sorted(raw_set - norm_set)
    only_norm = sorted(norm_set - raw_set)

    print("\n--- Raw vs Normalized Span Diff ---")
    if not only_raw and not only_norm:
        print(
            "No span differences after projection (raw and normalized are identical)."
        )
        return
    if only_raw:
        print("Only in Raw:")
        for s in only_raw:
            print(f"  {s}")
    if only_norm:
        print("Only in Normalized:")
        for s in only_norm:
            print(f"  {s}")


def clean_bert_entities_from_normalized_text(
    entities: list[dict], normalized_text: str, max_gap: int = 6
) -> list[dict]:
    nt_len = len(normalized_text)
    aligned = []
    for ent in entities:
        start = max(0, int(ent.get("start", 0)))
        end = min(nt_len, int(ent.get("end", 0)))
        if end <= start:
            continue
        rebuilt = normalized_text[start:end].strip()
        if not rebuilt:
            continue
        fixed = dict(ent)
        fixed["start"] = start
        fixed["end"] = end
        fixed["text"] = rebuilt
        aligned.append(fixed)

    return merge_adjacent_spans(
        aligned,
        text=normalized_text,
        labels=("PER", "LOC"),
        max_gap=max_gap,
        merge_min_score=0.55,
        extend_irish_o_surname=True,
    )


def reconstruct_spans_from_lookup(
    unique_entities: list[dict], spans_lookup: dict
) -> list[dict]:
    reconstructed = []
    for ent in unique_entities:
        key = f"{ent['text']}|||{ent['label']}"
        for sp in spans_lookup.get(key, []):
            rebuilt = dict(ent)
            rebuilt["start"] = int(sp["start"])
            rebuilt["end"] = int(sp["end"])
            rebuilt["score"] = float(sp.get("score", ent.get("score", 0.0)))
            reconstructed.append(rebuilt)
    return reconstructed


def project_entities_to_raw(
    normalized_entities: list[dict], char_map: dict[int, int], raw_text: str
) -> list[dict]:
    projected = []
    raw_len = len(raw_text)
    for ent in normalized_entities:
        start = int(ent.get("start", -1))
        end = int(ent.get("end", -1))
        label = str(ent.get("label", ""))
        if end <= start or not label:
            continue
        if start not in char_map or (end - 1) not in char_map:
            continue
        raw_start = int(char_map[start])
        raw_end = int(char_map[end - 1]) + 1
        if raw_start < 0 or raw_end <= raw_start:
            continue
        if raw_start >= raw_len:
            continue
        if raw_end > raw_len:
            raw_end = raw_len
        projected.append(
            {
                "text": raw_text[raw_start:raw_end],
                "start": raw_start,
                "end": raw_end,
                "label": label,
            }
        )
    return projected


def accumulate(totals: dict, metrics: dict) -> None:
    for k in totals:
        totals[k] += int(metrics[k])


def summarize(title: str, totals: dict) -> None:
    precision = (
        totals["tp_count"] / (totals["tp_count"] + totals["fp_count"])
        if (totals["tp_count"] + totals["fp_count"])
        else 0.0
    )
    recall = (
        totals["tp_count"] / (totals["tp_count"] + totals["fn_count"])
        if (totals["tp_count"] + totals["fn_count"])
        else 0.0
    )
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    print(f"\n=== {title} ===")
    print(
        f"Gold: {totals['gold_count']}  Pred: {totals['pred_count']}  TP: {totals['tp_count']}  FP: {totals['fp_count']}  FN: {totals['fn_count']}"
    )
    print(f"Precision: {precision:.4f}  Recall: {recall:.4f}  F1: {f1:.4f}")


def metrics_from_totals(totals: dict) -> dict:
    precision = (
        totals["tp_count"] / (totals["tp_count"] + totals["fp_count"])
        if (totals["tp_count"] + totals["fp_count"])
        else 0.0
    )
    recall = (
        totals["tp_count"] / (totals["tp_count"] + totals["fn_count"])
        if (totals["tp_count"] + totals["fn_count"])
        else 0.0
    )
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    out = dict(totals)
    out["precision"] = precision
    out["recall"] = recall
    out["f1"] = f1
    return out


def write_metrics_csv(rows: list[dict], output_csv: str) -> None:
    if not output_csv:
        return
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record",
        "filename",
        "entry",
        "mode",
        "gold_count",
        "pred_count",
        "tp_count",
        "fp_count",
        "fn_count",
        "precision",
        "recall",
        "f1",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Wrote metrics CSV: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate raw BERT vs normalized pipeline against ground truth."
    )
    parser.add_argument(
        "--output-csv",
        default="",
        help="Optional path to write per-record and overall metrics as CSV.",
    )
    args = parser.parse_args()

    ground_truth = load_ground_truth()
    if PROCESS_ALL:
        selected = ground_truth
        mode = "all entries"
    else:
        if SINGLE_ENTRY_INDEX < 0 or SINGLE_ENTRY_INDEX >= len(ground_truth):
            raise IndexError(
                f"SINGLE_ENTRY_INDEX={SINGLE_ENTRY_INDEX} is out of range for {len(ground_truth)} records."
            )
        selected = [ground_truth[SINGLE_ENTRY_INDEX]]
        mode = f"single entry at index {SINGLE_ENTRY_INDEX}"

    print(
        f"Loaded {len(selected)} record(s) from ground_truth.json ({mode}; total={len(ground_truth)})"
    )

    bert = BertNER()
    irish_names_path = backend_dir / "services" / "normalize" / "irish_names.json"
    historical_override_path = (
        backend_dir / "services" / "normalize" / "hist_override.json"
    )

    raw_totals = {
        "gold_count": 0,
        "pred_count": 0,
        "tp_count": 0,
        "fp_count": 0,
        "fn_count": 0,
    }
    norm_totals = {
        "gold_count": 0,
        "pred_count": 0,
        "tp_count": 0,
        "fp_count": 0,
        "fn_count": 0,
    }
    csv_rows: list[dict] = []

    for rec in selected:
        paragraph = str(rec.get("paragraph", ""))
        filename = rec.get("filename")
        entry = rec.get("entry")
        gold_ents = list(rec.get("ents", []))
        print(f"\n=== Record: {filename} entry={entry} ===")

        # Raw path: no changes or filtering.
        raw_preds = bert.fast_analyse(paragraph)
        raw_metrics = evaluate(gold_ents, raw_preds)
        print_metrics("Raw BERT vs Ground Truth", raw_metrics)
        accumulate(raw_totals, raw_metrics)
        csv_rows.append(
            {
                "record": f"{filename}:{entry}",
                "filename": filename,
                "entry": entry,
                "mode": "raw",
                "gold_count": raw_metrics["gold_count"],
                "pred_count": raw_metrics["pred_count"],
                "tp_count": raw_metrics["tp_count"],
                "fp_count": raw_metrics["fp_count"],
                "fn_count": raw_metrics["fn_count"],
                "precision": f"{raw_metrics['precision']:.4f}",
                "recall": f"{raw_metrics['recall']:.4f}",
                "f1": f"{raw_metrics['f1']:.4f}",
            }
        )

        # Normalized path:
        # 1) normalize raw text
        # 2) run BERT on normalized text
        # 3) post-process like norm_ner_router
        # 4) reconstruct duplicates from spans_lookup
        # 5) map spans back to raw-text offsets and evaluate vs ground truth
        normalized_text, char_map = normalize_v2(
            paragraph,
            irish_names_path=str(irish_names_path),
            historical_override_path=str(historical_override_path),
        )
        norm_raw_preds = bert.fast_analyse(normalized_text)
        norm_prepped = clean_bert_entities_from_normalized_text(
            norm_raw_preds, normalized_text, max_gap=6
        )
        norm_filtered, spans_lookup = filter_ner_entities(norm_prepped)
        norm_span_level = reconstruct_spans_from_lookup(norm_filtered, spans_lookup)
        norm_projected = project_entities_to_raw(norm_span_level, char_map, paragraph)
        norm_metrics = evaluate(gold_ents, norm_projected)
        print_metrics("Normalized Pipeline vs Ground Truth", norm_metrics)
        print_raw_vs_norm_diff(raw_preds, norm_projected)
        accumulate(norm_totals, norm_metrics)
        csv_rows.append(
            {
                "record": f"{filename}:{entry}",
                "filename": filename,
                "entry": entry,
                "mode": "normalized",
                "gold_count": norm_metrics["gold_count"],
                "pred_count": norm_metrics["pred_count"],
                "tp_count": norm_metrics["tp_count"],
                "fp_count": norm_metrics["fp_count"],
                "fn_count": norm_metrics["fn_count"],
                "precision": f"{norm_metrics['precision']:.4f}",
                "recall": f"{norm_metrics['recall']:.4f}",
                "f1": f"{norm_metrics['f1']:.4f}",
            }
        )

    summarize("Overall Raw BERTNER", raw_totals)
    summarize("Overall Normalized Pipeline", norm_totals)
    raw_overall = metrics_from_totals(raw_totals)
    norm_overall = metrics_from_totals(norm_totals)
    csv_rows.append(
        {
            "record": "OVERALL",
            "filename": "",
            "entry": "",
            "mode": "raw",
            "gold_count": raw_overall["gold_count"],
            "pred_count": raw_overall["pred_count"],
            "tp_count": raw_overall["tp_count"],
            "fp_count": raw_overall["fp_count"],
            "fn_count": raw_overall["fn_count"],
            "precision": f"{raw_overall['precision']:.4f}",
            "recall": f"{raw_overall['recall']:.4f}",
            "f1": f"{raw_overall['f1']:.4f}",
        }
    )
    csv_rows.append(
        {
            "record": "OVERALL",
            "filename": "",
            "entry": "",
            "mode": "normalized",
            "gold_count": norm_overall["gold_count"],
            "pred_count": norm_overall["pred_count"],
            "tp_count": norm_overall["tp_count"],
            "fp_count": norm_overall["fp_count"],
            "fn_count": norm_overall["fn_count"],
            "precision": f"{norm_overall['precision']:.4f}",
            "recall": f"{norm_overall['recall']:.4f}",
            "f1": f"{norm_overall['f1']:.4f}",
        }
    )
    write_metrics_csv(csv_rows, args.output_csv)
