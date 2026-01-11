# services/normalize_services.py

import json
import re
from dataclasses import dataclass
from typing import Dict, Set, Optional


@dataclass
class NormalizedDocument:
    visual_layer: str
    normalized_layer: str
    char_map: Dict[int, int]


class HistoricalNormalizer:
    """
    General 17th-century English normalizer:

      - collapses whitespace
      - applies broad spelling rules (v/u, i/j, ff, vv, bee/mee/hee/shee, etc.)
      - preserves Irish personal/place names using irish_names.json
      - builds a char_map so BERT spans can be mapped back to original text
    """

    def __init__(self, irish_names_path: str):
        with open(irish_names_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.irish_prefixes: Set[str] = {p.lower() for p in data.get("prefixes", [])}
        self.irish_surnames: Set[str] = {s.lower() for s in data.get("surnames", [])}
        self.irish_first_names: Set[str] = {
            n.lower() for n in data.get("first_names", [])
        }
        self.irish_places = {p.lower() for p in data.get("place_names", [])}
        self.historical_place_map = data.get("historical_spellings", {})

    # ---------- name protection helpers ----------

    @staticmethod
    def _clean_for_match(tok: str) -> str:
        """
        Simplify a token for name matching:
        - keep letters + apostrophes
        - lowercase
        """
        return re.sub(r"[^A-Za-z'ÁÉÍÓÚáéíóú]", "", tok).lower()

    def _is_irish_token(self, tok: str, pending_prefix: bool):
        """
        Decide if a token should be protected as Irish name:

        - direct match against surname or first_name
        - prefix (O, Ó, Mac, Mc, etc) -> protect this and mark next token
        - if previous token was a prefix, protect this as well
        """
        clean = self._clean_for_match(tok)
        if not clean:
            return False, False

        # direct matches
        if clean in self.irish_surnames or clean in self.irish_first_names:
            return True, False

        if clean in self.irish_places:
            return True, False

        # prefix like "O", "Ó", "Mac", etc.
        if clean in self.irish_prefixes:
            return True, True  # this is protected, and next word will be too

        # previous token was a prefix: treat this as probable surname
        if pending_prefix:
            return True, False

        return False, False

    # ---------- spelling normalisation ----------

    @staticmethod
    def _preserve_case(modern: str, original: str) -> str:
        """Apply original casing style to a lowercased modern form."""
        if original.isupper():
            return modern.upper()
        if original and original[0].isupper():
            return modern.capitalize()
        return modern

    def _normalize_word(self, word: str) -> str:
        """
        Pattern-based historical -> modern spelling:
        - not tied to any specific document
        - targets COMMON 17th-century forms seen across 1641 depositions
        """
        lower = word.lower()

        # 1) "vv" used as "w"
        lower = lower.replace("vv", "w")

        # 2) initial "ff" -> "f" (e.g. "ffrancis" -> "francis", "ffleminge" -> "fleminge")
        if lower.startswith("ff") and len(lower) > 2:
            lower = "f" + lower[2:]

        # 3) v/u patterns (generic)
        lower = re.sub(r"\bvppon\b", "upon", lower)
        lower = re.sub(r"\bvpon\b", "upon", lower)
        lower = re.sub(r"\bvnder\b", "under", lower)
        lower = re.sub(r"\bvnto\b", "unto", lower)
        lower = re.sub(r"\bvntil\b", "until", lower)
        lower = re.sub(r"\bvntill\b", "until", lower)

        # 4) very common verb/noun forms
        lower = re.sub(r"\bhaue\b", "have", lower)
        lower = re.sub(r"\bgiue\b", "give", lower)
        lower = re.sub(r"\bdiuinity\b", "divinity", lower)

        # 5) long-s style v/u swaps in frequent words
        lower = re.sub(r"\bseruice\b", "service", lower)
        lower = re.sub(r"\bsaue\b", "save", lower)
        lower = re.sub(r"\bdiscouery\b", "discovery", lower)
        lower = re.sub(r"\bdiscouer\b", "discover", lower)

        # 6) i/j confusion
        lower = re.sub(r"\biustice\b", "justice", lower)
        lower = re.sub(r"\biudg", "judg", lower)  # iudge/iudgment -> judge/judgment

        # 7) common elongated pronouns/verbs
        lower = re.sub(r"\bbee\b", "be", lower)
        lower = re.sub(r"\bbeeing\b", "being", lower)
        lower = re.sub(r"\bmee\b", "me", lower)
        lower = re.sub(r"\bhee\b", "he", lower)
        lower = re.sub(r"\bshee\b", "she", lower)

        # 8) a few very common lexical forms in these depositions
        lower = re.sub(r"\baccompt\b", "account", lower)
        lower = re.sub(
            r"\bmaiest(y|ies)\b", r"majest\1", lower
        )  # maiesty/maiesties -> majesty/majesties

        # 9) Irish historical place spellings
        if lower in self.historical_place_map:
            lower = self.historical_place_map[lower]
        return self._preserve_case(lower, word)

    # ---------- main entry ----------

    def normalize(self, text: str) -> NormalizedDocument:
        """
        Input:
            text  (visual layer) - raw extracted deposition (e.g. output.txt)
        Output:
            NormalizedDocument with:
              - visual_layer      (original text)
              - normalized_layer  (cleaner, modernized text)
              - char_map          (aux_index -> visual_index)
        """
        visual = text
        normalized_chars = []
        char_map: Dict[int, int] = {}

        pending_prefix = False  # "O", "Mac", etc seen just before
        a_i = 0  # index in normalized_layer

        # Tokenize into words, numbers, and single-character punctuation/whitespace
        for m in re.finditer(r"[A-Za-z']+|\d+|\s+|.", text, re.UNICODE):
            tok = m.group(0)
            start = m.start()

            # Word token (letters/apostrophes only)
            if re.fullmatch(r"[A-Za-z']+", tok):
                is_irish, pending_prefix = self._is_irish_token(tok, pending_prefix)

                if is_irish:
                    new_tok = tok
                else:
                    new_tok = self._normalize_word(tok)

                # Map each character in new_tok back to some position in the original token
                for j, ch in enumerate(new_tok):
                    normalized_chars.append(ch)
                    orig_pos = start + min(j, len(tok) - 1)
                    char_map[a_i] = orig_pos
                    a_i += 1

            # Whitespace
            elif tok.isspace():
                # treat runs of whitespace as either paragraph break or single space
                if "\n\n" in tok:
                    new_tok = "\n\n"
                else:
                    new_tok = " "

                for ch in new_tok:
                    if normalized_chars and normalized_chars[-1] == ch:
                        continue
                    normalized_chars.append(ch)
                    char_map[a_i] = start
                    a_i += 1

                # reset prefix flag on hard breaks
                if "\n" in tok:
                    pending_prefix = False

            # Punctuation / everything else
            else:
                for j, ch in enumerate(tok):
                    normalized_chars.append(ch)
                    char_map[a_i] = start + j
                    a_i += 1
                # punctuation ends any pending prefix chain
                pending_prefix = False

        normalized = "".join(normalized_chars)

        return NormalizedDocument(
            visual_layer=visual,
            normalized_layer=normalized,
            char_map=char_map,
        )


# ---------- convenience function for FastAPI router ----------

_NORMALIZER: Optional[HistoricalNormalizer] = None


def normalize(
    visual_text: str, irish_names_path: str = "services/normalize/irish_names.json"
):
    """

    It caches a HistoricalNormalizer instance so the JSON isn't reloaded on every call.
    """
    global _NORMALIZER
    if _NORMALIZER is None:
        _NORMALIZER = HistoricalNormalizer(irish_names_path)

    doc = _NORMALIZER.normalize(visual_text)
    return doc.normalized_layer, doc.char_map
