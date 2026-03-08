import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Dict, Optional


# Allow punctuation-only gaps and historical connectors such as " oge ".
_DEFAULT_GAP_RE = re.compile(r"^(?:[\s'’.-]{0,3}|\s+oge\s+)$", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z]+")


def _canon_alpha(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


@lru_cache(maxsize=1)
def _irish_surnames() -> set:
    p = Path(__file__).resolve().parent / "normalize" / "irish_names.json"
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {_canon_alpha(str(s).strip()) for s in data.get("surnames", []) if str(s).strip()}


def _allow_historical_per_gap_merge(cur: Dict, nxt: Dict, between: str) -> bool:
    """
    Allow a very narrow merge case for OCR/spacing artifacts:
    "og" + "e " + "O'ne..."  -> "oge O'ne..."
    """
    if cur.get("label") != "PER" or nxt.get("label") != "PER":
        return False

    gap_letters = _canon_alpha(between)
    if gap_letters != "e":
        return False

    cur_text = str(cur.get("text", ""))
    nxt_text = str(nxt.get("text", ""))
    return _canon_alpha(cur_text).endswith("og") and nxt_text.lower().startswith("o'")


def _drop_contained_same_label(entities: List[Dict], debug: bool) -> List[Dict]:
    entities.sort(key=lambda e: (int(e.get("start", 0)), int(e.get("end", 0))))
    pruned: List[Dict] = []
    for ent in entities:
        s = int(ent.get("start", 0))
        e = int(ent.get("end", 0))
        lbl = ent.get("label")
        contained = False
        for keep in pruned:
            ks = int(keep.get("start", 0))
            ke = int(keep.get("end", 0))
            if keep.get("label") == lbl and ks <= s and e <= ke and (ks != s or ke != e):
                contained = True
                if debug:
                    print(
                        "[merge_adjacent_spans] drop contained:",
                        f"({s},{e},{lbl},{ent.get('text','')!r}) inside ({ks},{ke},{lbl},{keep.get('text','')!r})",
                    )
                break
        if not contained:
            pruned.append(ent)
    return pruned


def _looks_like_valid_token(token: str, label: str) -> bool:
    """Guardrail: only accept conservative token expansions for PER/LOC."""
    if not token:
        return False
    if re.search(r"\d", token):
        return False

    alpha_count = sum(1 for c in token if c.isalpha())
    if alpha_count < 3:
        return False

    if label == "PER":
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z'’-]*", token))
    if label == "LOC":
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z'’.-]*", token))
    return False


def _extend_clipped_midword_spans(entities: List[Dict], text: str, debug: bool) -> List[Dict]:
    """
    Extend clipped PER/LOC spans that end mid-word:
    e.g. "Magw" -> "Magwires", "O'ne" -> "O'neill".
    """
    out: List[Dict] = [dict(e) for e in entities]
    n = len(text)

    def _token_char(ch: str) -> bool:
        return ch.isalpha() or ch in {"'", "’", "-"}

    for ent in out:
        label = ent.get("label")
        if label not in {"PER", "LOC"}:
            continue

        start = int(ent.get("start", 0))
        end = int(ent.get("end", 0))
        if start < 0 or end <= start or end >= n:
            continue

        prev_ch = text[end - 1]
        next_ch = text[end]
        next_alpha = next_ch.isalpha() or (
            next_ch in {"'", "’"} and end + 1 < n and text[end + 1].isalpha()
        )
        if not (prev_ch.isalpha() and next_alpha):
            continue

        j = end
        while j < n and _token_char(text[j]):
            j += 1
        if j <= end:
            continue

        candidate = text[start:j]
        if not _looks_like_valid_token(candidate, label):
            continue

        old_end = end
        ent["end"] = j
        ent["text"] = candidate
        if debug:
            print(
                "[merge_adjacent_spans] extend clipped mid-word:",
                f"({start},{old_end}) -> ({start},{j}) label={label} text={candidate!r}",
            )

    return _drop_contained_same_label(out, debug)


def _extend_o_prefixed_person_spans(entities: List[Dict], text: str, debug: bool) -> List[Dict]:
    """
    If a PER span ends with O / O' and the following surname token is Irish,
    extend the span to include that surname.
    """
    surnames = _irish_surnames()
    out: List[Dict] = [dict(e) for e in entities]

    for ent in out:
        if ent.get("label") != "PER":
            continue
        start = int(ent.get("start", 0))
        end = int(ent.get("end", 0))
        if end <= start or end > len(text):
            continue

        cur_text = text[start:end].rstrip()
        if not re.search(r"\bO'?$", cur_text, flags=re.IGNORECASE):
            continue

        i = end
        if i < len(text) and text[i] in {"'", "’"}:
            i += 1

        m = _WORD_RE.match(text, i)
        if not m:
            continue

        surname = _canon_alpha(m.group(0))
        if surname not in surnames:
            # Handle partial forms like "O'ne" followed by "ill" => "O'neill".
            frag_match = re.search(r"\bO'[A-Za-z]{1,4}$", cur_text, flags=re.IGNORECASE)
            if not frag_match:
                continue
            tail = _WORD_RE.match(text, end)
            if not tail:
                continue
            combined = _canon_alpha(frag_match.group(0) + tail.group(0))
            if combined not in surnames:
                continue
            ent["end"] = tail.end()
            ent["text"] = text[start : tail.end()]
            if debug:
                print(
                    "[merge_adjacent_spans] extend partial O-surname:",
                    f"({start},{end}) -> ({start},{tail.end()}) text={ent['text']!r}",
                )
            continue

        ent["end"] = m.end()
        ent["text"] = text[start : m.end()]
        if debug:
            print(
                "[merge_adjacent_spans] extend O-surname:",
                f"({start},{end}) -> ({start},{m.end()}) text={ent['text']!r}",
            )

    return _drop_contained_same_label(out, debug)


def merge_adjacent_spans(
    entities: Iterable[Dict],
    *,
    text: Optional[str] = None,
    labels: Iterable[str] = ("PER", "LOC"),
    max_gap: int = 2,
    merge_min_score: float = 0.0,
    extend_irish_o_surname: bool = False,
    extend_clipped_midword: bool = True,
    debug: bool = False,
) -> List[Dict]:
    """
    Merge adjacent spans with the same label into a single span.
    If `text` is provided, the gap between spans must match _DEFAULT_GAP_RE.
    """
    def _dbg(msg: str):
        if debug:
            print(f"[merge_adjacent_spans] {msg}")

    label_set = set(labels)
    # entities can be any iterable; materialize once for stable filtering/sorting and debug counts.
    entities = list(entities)
    _dbg(
        f"start: total_entities={len(entities)}, labels={sorted(label_set)}, "
        f"max_gap={max_gap}, merge_min_score={merge_min_score}, "
        f"extend_irish_o_surname={extend_irish_o_surname}, "
        f"extend_clipped_midword={extend_clipped_midword}, text_provided={text is not None}"
    )
    ents = [
        e
        for e in entities
        if e.get("label") in label_set and "start" in e and "end" in e
    ]
    others = [e for e in entities if e not in ents]
    _dbg(f"candidates={len(ents)}, passthrough_others={len(others)}")

    ents.sort(key=lambda e: (e["start"], e["end"]))
    if not ents:
        _dbg("no candidate entities; returning original entities unchanged")
        return list(entities)

    merged: List[Dict] = []
    cur = dict(ents[0])
    _dbg(
        f"seed cur=({cur.get('start')},{cur.get('end')},{cur.get('label')},{cur.get('text', '')!r},score={cur.get('score')})"
    )

    for nxt in ents[1:]:
        _dbg(
            f"consider cur=({cur.get('start')},{cur.get('end')},{cur.get('label')},{cur.get('text', '')!r},score={cur.get('score')}) "
            f"nxt=({nxt.get('start')},{nxt.get('end')},{nxt.get('label')},{nxt.get('text', '')!r},score={nxt.get('score')})"
        )
        if nxt["label"] != cur["label"]:
            _dbg("skip merge: label mismatch -> flush cur and advance")
            merged.append(cur)
            cur = dict(nxt)
            continue

        gap = nxt["start"] - cur["end"]
        if gap < 0:
            _dbg(f"skip merge: overlapping spans (gap={gap}) -> drop nxt")
            continue

        if gap <= max_gap:
            cur_score = float(cur.get("score", 1.0))
            nxt_score = float(nxt.get("score", 1.0))
            if cur_score < merge_min_score or nxt_score < merge_min_score:
                _dbg(
                    f"skip merge: score gate failed (cur_score={cur_score}, nxt_score={nxt_score}, min={merge_min_score})"
                )
                merged.append(cur)
                cur = dict(nxt)
                continue

            if text is not None:
                between = text[cur["end"] : nxt["start"]]
                if not _DEFAULT_GAP_RE.match(between):
                    if _allow_historical_per_gap_merge(cur, nxt, between):
                        _dbg(
                            f"merge allowed by historical PER heuristic gap={gap} between={between!r}"
                        )
                    else:
                        _dbg(
                            f"skip merge: gap text failed regex gap={gap} between={between!r} regex={_DEFAULT_GAP_RE.pattern}"
                        )
                        merged.append(cur)
                        cur = dict(nxt)
                        continue

            # Merge
            _dbg(f"merge success: gap={gap}")
            cur["end"] = nxt["end"]
            if text is not None:
                cur["text"] = text[cur["start"] : cur["end"]]
            else:
                if "text" in cur and "text" in nxt:
                    cur["text"] = (cur["text"] + " " + nxt["text"]).strip()
            # Score: keep max
            if "score" in cur or "score" in nxt:
                cur["score"] = max(cur.get("score", 0.0), nxt.get("score", 0.0))
            _dbg(
                f"merged cur now=({cur.get('start')},{cur.get('end')},{cur.get('label')},{cur.get('text', '')!r},score={cur.get('score')})"
            )
        else:
            _dbg(f"skip merge: gap too large (gap={gap} > max_gap={max_gap})")
            merged.append(cur)
            cur = dict(nxt)

    merged.append(cur)
    _dbg(f"done: merged_count={len(merged)}, passthrough_others={len(others)}")
    final = merged + others
    if text is not None and extend_clipped_midword:
        final = _extend_clipped_midword_spans(final, text, debug)
    if text is not None and extend_irish_o_surname:
        final = _extend_o_prefixed_person_spans(final, text, debug)
    return final
