import re


_TRUNCATED_O_SURNAME_RE = re.compile(r"^[Oo]['’][A-Za-z]{1,3}$")


def _canonicalize_person_text(text: str) -> str:
    """Lightweight canonicalization for Irish O' surnames."""
    # Normalize apostrophe style first.
    text = text.replace("’", "'")
    # Ensure the first letter after O' is capitalized: O'neill -> O'Neill
    return re.sub(r"\bO'([a-z])", lambda m: "O'" + m.group(1).upper(), text)


def filter_ner_entities(entities: list) -> tuple:
    """
    1. Remove PER labels < 3 chars
    2. Remove entities with score < 0.7
    3. Deduplicate by (text, label) while keeping all spans

    Returns: (unique_entities, spans_lookup)
    """
    from collections import defaultdict

    # Step 1 & 2: Filter
    filtered = []
    for ent in entities:
        text = ent["text"].strip()
        ent_fixed = ent.copy()
        if ent_fixed.get("label") == "PER":
            text = _canonicalize_person_text(text)
            ent_fixed["text"] = text
        if (
            text == "County of"
            or text == "City of"
            or text == "County"
            or text == "City"
            or text == "Proportion of"
            or text == "county"
        ):
            continue

        # Drop clipped Irish surname fragments, e.g. "O'ne", caused by OCR/spacing token splits.
        if ent["label"] == "PER" and _TRUNCATED_O_SURNAME_RE.match(text):
            continue

        if ent["label"] and len(text) < 3:
            continue

        # Rule 2: Remove low confidence
        if ent["score"] < 0.7:
            continue

        filtered.append(ent_fixed)

    # Step 3: Deduplicate by (text, label), keep all spans
    entity_map = defaultdict(lambda: {"entity": None, "spans": []})
    seen_spans = set()

    for ent in filtered:
        key = (ent["text"], ent["label"])

        # Store first occurrence as canonical entity
        if entity_map[key]["entity"] is None:
            entity_map[key]["entity"] = ent.copy()

        span_key = f"{ent['start']}-{ent['end']}"
        if span_key not in seen_spans:
            seen_spans.add(span_key)
            entity_map[key]["spans"].append(
                {"start": ent["start"], "end": ent["end"], "score": ent["score"]}
            )

    # Extract unique entities
    unique_entities = [v["entity"] for v in entity_map.values()]

    # Create spans lookup: {(text, label): [list of spans]}
    spans_lookup = {
        f"{v['entity']['text']}|||{v['entity']['label']}": v["spans"]  # String key
        for v in entity_map.values()
    }

    return unique_entities, spans_lookup
