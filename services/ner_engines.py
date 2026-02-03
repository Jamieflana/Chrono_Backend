import spacy
from flair.models import SequenceTagger
from flair.data import Sentence
from transformers import pipeline
import stanza
import re
import json
from pathlib import Path


def load_irish_names():
    # Adjust path based on where your file is relative to bert_ner.py
    json_path = (
        Path(__file__).parent.parent / "services" / "normalize" / "irish_names.json"
    )

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


IRISH_DATA = load_irish_names()
IRISH_COUNTIES = set(county.lower() for county in IRISH_DATA["all_counties"])


_SENT_END_RE = re.compile(r"[.!?]")


class BaseNER:
    def analyze(self, text: str):
        raise NotImplementedError

    def _standardize_label(self, label: str):
        label_upper = label.upper()
        if label_upper in {"PERSON", "PER", "PERS"}:
            return "PER"

        if label_upper in {"GPE", "LOC", "LOCATION", "PLACE", "FAC", "FACILITY"}:
            return "LOC"

        # Return None for labels we don't want to keep
        return None

    def chunk_text(self, text, max_chars: int = 600, overlap: int = 80):
        """
        Split text into overlapping chunks, preferring sentence boundaries
        and never cutting in the middle of a word.
        """
        chunks = []
        n = len(text)
        start = 0

        while start < n:
            hard_limit = min(start + max_chars, n)
            cut = hard_limit

            window = text[start:hard_limit]

            # 1) Try to find the last sentence terminator in this window
            last_sent_rel = None
            for m in _SENT_END_RE.finditer(window):
                last_sent_rel = m.end()  # end index *within* window

            if last_sent_rel is not None and last_sent_rel > 40:
                # cut at sentence end
                cut = start + last_sent_rel
            else:
                # 2) Fall back to last space before hard_limit
                last_space = text.rfind(" ", start, hard_limit)
                if last_space != -1 and last_space > start + 40:
                    cut = last_space
                # else leave cut at hard_limit (very long no‑space run)

            chunk = text[start:cut]
            chunks.append((start, chunk))

            # Compute next start with overlap
            new_start = cut - overlap
            if new_start <= start:
                new_start = cut

            # Skip leading whitespace at new_start
            while new_start < n and text[new_start].isspace():
                new_start += 1

            start = new_start

        return chunks

    def _analyze_single(self, text: str):
        """Override this method in subclasses to implement model-specific analysis"""
        raise NotImplementedError

    def analyze(self, text: str):
        """
        Main analyze method with optional chunking support.
        With chunking=False, analyzes text directly.
        With chunking=True, splits long texts into chunks.
        """
        if not self.use_chunking:
            return self._analyze_single(text)

        # Chunking mode
        chunks = self.chunk_text(text)
        all_ents = []

        for offset, chunk in chunks:
            ents = self._analyze_single(chunk)
            # Add offsets to entities if not already present
            for ent in ents:
                if "start" not in ent or "end" not in ent:
                    # Try to find entity position in original text
                    start_idx = text.find(ent["text"], offset)
                    if start_idx != -1:
                        ent["start"] = start_idx
                        ent["end"] = start_idx + len(ent["text"])
                else:
                    # Adjust existing offsets
                    ent["start"] += offset
                    ent["end"] += offset
            all_ents.extend(ents)

        # Deduplicate by text + label
        seen = set()
        unique = []
        for ent in all_ents:
            key = (ent["text"], ent["label"])
            if key not in seen:
                seen.add(key)
                unique.append(ent)

        return unique


# ---------- spaCy ----------
class SpacyNER(BaseNER):
    def __init__(self, model_name="en_core_web_sm"):
        print(f"Loading spacy model: {model_name}")
        self.nlp = spacy.load(model_name)

    def analyze(self, text: str):
        print("in spacey analyze")
        doc = self.nlp(text)
        return [{"text": ent.text, "label": ent.label_} for ent in doc.ents]


# ---------- Flair ----------
class FlairNER(BaseNER):
    def __init__(self, model_name="ner"):
        print(f"Loading flair model: {model_name}")
        self.tagger = SequenceTagger.load(model_name)

    def analyze(self, text: str):
        sentence = Sentence(text)
        self.tagger.predict(sentence)
        return [
            {
                "text": entity.text,
                "label": entity.labels[0].value,
                "score": entity.labels[0].score,
            }
            for entity in sentence.get_spans("ner")
        ]


# ---------- BERT (Transformers pipeline) ----------
class BertNER(BaseNER):
    def __init__(
        self,
        # model_name="xlm-roberta-large-finetuned-conll03-english",
        # model_name="/home/jamie/Documents/FinalYear/Dissertation/Chrono/Backend/trainer/irish-ner-final",
        model_name="dbmdz/bert-large-cased-finetuned-conll03-english",
        use_chunking=True,
    ):
        print(f"Initializing: {model_name}")
        self.pipeline = pipeline("ner", model=model_name, aggregation_strategy="simple")
        # self.allowed_labels = {"PER", "LOC", "DATE", "ORG"}
        self.allowed_labels = {"PER", "LOC"}
        self.use_chunking = use_chunking

    def chunk_text(self, text, max_chars: int = 1200, overlap: int = 100):
        """
        Split text into overlapping chunks, preferring sentence boundaries
        and never cutting in the middle of a word.
        """
        chunks = []
        n = len(text)
        start = 0

        while start < n:
            hard_limit = min(start + max_chars, n)
            cut = hard_limit

            window = text[start:hard_limit]

            # 1) Try to find the last sentence terminator in this window
            last_sent_rel = None
            for m in _SENT_END_RE.finditer(window):
                last_sent_rel = m.end()  # end index *within* window

            if last_sent_rel is not None and last_sent_rel > 40:
                # cut at sentence end
                cut = start + last_sent_rel
            else:
                # 2) Fall back to last space before hard_limit
                last_space = text.rfind(" ", start, hard_limit)
                if last_space != -1 and last_space > start + 40:
                    cut = last_space
                # else leave cut at hard_limit (very long no‑space run)

            chunk = text[start:cut]
            chunks.append((start, chunk))

            # Compute next start with overlap
            new_start = cut - overlap
            if new_start <= start:
                new_start = cut

            # Skip leading whitespace at new_start
            while new_start < n and text[new_start].isspace():
                new_start += 1

            start = new_start

        return chunks

    # Chunk analyze function
    def _analyze_chunk(self, text, offset=0):

        results = self.pipeline(text)
        filtered = []

        for r in results:
            label = r["entity_group"]
            if label not in self.allowed_labels:
                continue

            word = r["word"]
            if word.startswith("#"):
                continue

            # Get rid of words before entity
            original_word = word

            entry = {
                "text": word,
                "label": label,
                "score": float(r["score"]),
            }

            if self.use_chunking and "start" in r and "end" in r:
                entry["start"] = r["start"] + offset
                entry["end"] = r["end"] + offset

            filtered.append(entry)

        return filtered

    def analyze(self, text: str):
        """
        With chunking=False = FastAPI pipeline.
        With chunking=True, for longer texts
        """

        if not self.use_chunking:
            return self._analyze_chunk(text)

        # chunking mode
        chunks = self.chunk_text(text)
        all_ents = []

        for offset, chunk in chunks:
            ents = self._analyze_chunk(chunk, offset=offset)
            ents = self.postprocess_entities(text, ents)
            all_ents.extend(ents)

        all_entities = self.merge_wordpiece_entities(all_ents)
        all_entities = self.drop_contained_spans(all_ents)
        all_entities = self.correct_known_entities(all_entities)
        return all_entities

        # I actually want the duplicates
        # Deduplicate by location + label + text
        seen = set()
        unique = []

        for ent in all_ents:
            key = (
                # ent.get("start"),
                # ent.get("end"),
                ent["text"],
                ent["label"],
            )
            if key not in seen:
                seen.add(key)
                unique.append(ent)

        unique = self.merge_wordpiece_entities(unique)  # attempt to combine weird joins
        unique = self.drop_contained_spans(unique)
        return unique

    def fast_analyse(self, text: str):
        print("In fast analuse")
        if not self.use_chunking:
            return self.analyze_chunk(text)
        chunks = self.chunk_text(text)

        chunk_texts = [chunk for _, chunk in chunks]
        offsets = [offset for offset, _ in chunks]

        batch_results = self.pipeline(chunk_texts)
        all_ents = []
        for offset, results in zip(offsets, batch_results):
            # Convert pipeline results to our entity format
            ents = self._process_pipeline_results(results, offset)
            # Clean up entities
            ents = self.postprocess_entities(text, ents)
            all_ents.extend(ents)
        all_entities = self.merge_wordpiece_entities(all_ents)
        all_entities = self.drop_contained_spans(all_entities)
        all_entities = self.correct_known_entities(all_entities)
        return all_entities

    def _process_pipeline_results(self, results, offset=0):

        filtered = []

        for r in results:
            label = r["entity_group"]
            if label not in self.allowed_labels:
                continue

            word = r["word"]
            if word.startswith("#"):
                continue

            entry = {
                "text": word,
                "label": label,
                "score": float(r["score"]),
                "start": r["start"] + offset,
                "end": r["end"] + offset,
            }

            filtered.append(entry)

        return filtered

    def merge_wordpiece_entities(self, entities):
        """
        Merge consecutive subword tokens (##...) into full words.
        Example: "George Ra" + "##cliff" -> "George Radcliff"
        """
        merged = []
        i = 0

        while i < len(entities):
            current = entities[i]
            text = current["text"]
            start = current.get("start")
            end = current.get("end")
            label = current["label"]
            score = current["score"]

            # Merge following wordpieces
            j = i + 1
            while j < len(entities):
                nxt = entities[j]
                if nxt["label"] != label:
                    break

                if nxt["text"].startswith("##"):
                    # strip leading ##
                    piece = nxt["text"][2:]
                    text = text + piece

                    # expand end boundary
                    if "end" in nxt:
                        end = nxt["end"]

                    # average score
                    score = (score + nxt["score"]) / 2.0

                    j += 1
                else:
                    break

            merged.append(
                {
                    "text": text,
                    "label": label,
                    "score": score,
                    "start": start,
                    "end": end,
                }
            )

            i = j

        return merged

    # Getting rid of this worked bestter
    def fix_entity_labels(self, text: str, entities: list):
        """
        Use local context around each entity to fix incorrect NER labels.
        """

        PERSON_TITLES = {
            "mr",
            "mrs",
            "sir",
            "lord",
            "lady",
            "bishop",
            "doctor",
            "dr",
            "esquire",
            "esqr",
            "primate",
            "friar",
            "preist",
            "abbot",
            "earle",
            "erle",
            "duke",
            "count",
            "cardinal",
        }

        LOCATION_CUE_WORDS = {
            "in",
            "at",
            "near",
            "towne",
            "city",
            "citty",
            "county",
            "province",
            "kingdome",
            "kingdom",
            "sea",
            "river",
            "castle",
            "estate",
            "convent",
            "abbey",
        }

        corrected = []

        lower_text = text.lower()

        for ent in entities:
            start, end = ent["start"], ent["end"]
            label = ent["label"]
            word = ent["text"]

            # Get a small context window (safe slicing)
            ctx_start = max(0, start - 40)
            ctx_end = min(len(text), end + 40)
            context = lower_text[ctx_start:ctx_end]

            # RULE 1 — Titles imply PERSON
            for title in PERSON_TITLES:
                if title + " " in context:
                    label = "PER"
                    break

            # RULE 2 — Prepositions + place words imply LOC
            for cue in LOCATION_CUE_WORDS:
                if cue + " " in context:
                    # BUT don’t override known persons
                    if label != "PER":
                        label = "LOC"
                    break

            # RULE 3 — Words ending with -son, -ton, -ford etc.
            if word.lower().endswith(("son", "ton", "ford", "ham", "bury")):
                if label != "PER":  # avoid flipping real surnames
                    label = "LOC"

            # RULE 4 — Pure capitalized surnames often PER (historical texts)
            if word[0].isupper() and " " not in word:
                # If context mentions clan/lineage
                if "sonn to" in context or "eldest" in context:
                    label = "PER"

            ent["label"] = label
            corrected.append(ent)

        return corrected

    def drop_contained_spans(self, entities):
        if not entities:
            return []

        # Sort by start position, then by length (descending)
        sorted_ents = sorted(
            entities, key=lambda e: (e["start"], -(e["end"] - e["start"]))
        )

        cleaned = []
        for i, entity in enumerate(sorted_ents):
            entity_start, entity_end = entity["start"], entity["end"]
            entity_label = entity["label"]

            # Only check previous entities (they start at same or earlier position)
            contained = False
            for prev in cleaned:
                if prev["label"] != entity_label:
                    continue

                # If current is inside previous
                if entity_start >= prev["start"] and entity_end <= prev["end"]:
                    if (entity_end - entity_start) < (prev["end"] - prev["start"]):
                        contained = True
                        break

            if not contained:
                cleaned.append(entity)

        return cleaned

    def correct_known_entities(self, entities):
        for ent in entities:
            text_lower = ent["text"].lower()
            if text_lower in IRISH_COUNTIES and ent["label"] == "PER":
                ent["label"] = "LOC"
        return entities

    def postprocess_entities(
        self, full_text: str, entities: list, debug: bool = False
    ) -> list:
        # Trim LOC prefixes like "County of", "Province of", "of"

        min_score = 0.50

        LOC_PREFIX_RE = re.compile(
            r"^\s*(?:"
            r"county\s+of|"
            r"province\s+of|"
            r"city\s+of|citty\s+of|"
            r"town\s+of|towne\s+of|"
            r"kingdom\s+of|kingdome\s+of|"
            r"of"
            r")\s+",
            re.IGNORECASE,
        )

        # Trim PER prefixes like "the said", "said"
        PER_PREFIX_RE = re.compile(
            r"^\s*(?:the\s+)?(?:said\s+)+",
            re.IGNORECASE,
        )

        # Trim PER suffixes like "Esquire", "Major" (end of span)
        PER_SUFFIX_RE = re.compile(
            r"(?:\s*[,;:]?\s*)" r"(?:esquire|esqr|esq|major)\.?\s*$",
            re.IGNORECASE,
        )

        cleaned = []

        for ent in entities:

            score = float(ent.get("score", 1.0))
            if score < min_score:
                continue
            label = ent.get("label")
            start, end = ent.get("start"), ent.get("end")

            # If no offsets, just trim text and move on (cannot update offsets safely)
            if start is None or end is None or not (0 <= start < end <= len(full_text)):
                original = ent["text"]
                new = original
                if label == "LOC":
                    new = LOC_PREFIX_RE.sub("", new).strip()
                elif label == "PER":
                    new = PER_PREFIX_RE.sub("", new)
                    new = PER_SUFFIX_RE.sub("", new).strip()

                if len(span.strip()) < 3:
                    continue

                # if debug and new != original:
                # print(f"[POST] {label} (no offsets) '{original}' -> '{new}'")
                ent["text"] = new
                cleaned.append(ent)
                continue

            # Use true substring (offset-safe)
            span = full_text[start:end]
            original_span = span

            if label == "LOC":
                span = LOC_PREFIX_RE.sub("", span).strip()
            elif label == "PER":
                span = PER_PREFIX_RE.sub("", span)
                span = PER_SUFFIX_RE.sub("", span).strip()
            else:
                cleaned.append(ent)
                continue

            # If unchanged, keep
            if span == original_span:
                cleaned.append(ent)
                continue

            # Find trimmed span inside the original substring to compute new offsets
            idx = original_span.find(span)
            if idx == -1 or not span:
                # safer to keep original than corrupt offsets
                cleaned.append(ent)
                continue

            new_start = start + idx
            new_end = new_start + len(span)

            # if debug:

            cleaned.append({**ent, "text": span, "start": new_start, "end": new_end})

        return cleaned


# ---------- Stanford CoreNLP ----------
class StanzaNER:
    def __init__(self, lang="en"):

        stanza.download(lang, verbose=False)
        self.nlp = stanza.Pipeline(lang=lang, processors="tokenize,ner", use_gpu=False)

    def analyze(self, text: str):
        print("In stanza analyse")
        doc = self.nlp(text)
        print(doc)
        return [{"text": ent.text, "label": ent.type} for ent in doc.ents]
