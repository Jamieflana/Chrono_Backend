import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Set, Optional, Iterable, Tuple


@dataclass
class NormalizedDocument:
    visual_layer: str
    normalized_layer: str
    char_map: Dict[int, int]


class _ModernWordScorer:
    """
    Optional scorer using `wordfreq` if available.
    If unavailable, returns None and we use heuristic scoring.
    """

    def __init__(self, min_zipf: float = 2.5):
        self.min_zipf = min_zipf
        try:
            from wordfreq import zipf_frequency  # type: ignore

            self._zipf = zipf_frequency
        except Exception:
            self._zipf = None

    def score(self, word_lower: str) -> Optional[float]:
        if self._zipf is None:
            return None
        return float(self._zipf(word_lower, "en"))


class HistoricalNormalizerV2:
    """
    General 17th-century English normalizer using systematic transformations and scoring.
    """

    # Include Irish vowels with fadas + common Latin letters.
    _LETTER_CLASS = r"A-Za-zÁÉÍÓÚáéíóúÓóÍíÉéÁáÚú"
    # Allow straight or curly apostrophes inside words
    _WORD_RE = re.compile(rf"[{_LETTER_CLASS}]+(?:['’][{_LETTER_CLASS}]+)*", re.UNICODE)
    _TOKEN_RE = re.compile(
        rf"[{_LETTER_CLASS}]+(?:['’][{_LETTER_CLASS}]+)*|\d+|\s+|.",
        re.UNICODE,
    )

    def __init__(
        self,
        irish_names_path: str,
        historical_override_path: Optional[str] = None,
        *,
        keep_double_newlines: bool = True,
        use_wordfreq: bool = True,
        wordfreq_min_zipf: float = 2.5,
        max_candidates: int = 24,
        force_overrides: bool = False,
        override_bonus: float = 0.25,
    ):
        """
        force_overrides:
          - If True: always apply override mapping when present (exact-match).
          - If False: treat override mapping as a strongly preferred candidate.

        override_bonus:
          - preference applied to override candidates in heuristic path (lower is better),
            and as a tie-breaker in frequency path.
        """
        with open(irish_names_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.irish_prefixes: Set[str] = {p.lower() for p in data.get("prefixes", [])}
        self.irish_surnames: Set[str] = {s.lower() for s in data.get("surnames", [])}
        self.irish_first_names: Set[str] = {
            n.lower() for n in data.get("first_names", [])
        }
        self.irish_places: Set[str] = {p.lower() for p in data.get("place_names", [])}
        self.historical_place_map: Dict[str, str] = data.get("historical_spellings", {})

        # Load historical override mappings (data-driven)
        self.historical_override: Dict[str, str] = {}
        if historical_override_path:
            with open(historical_override_path, "r", encoding="utf-8") as f:
                override_data = json.load(f)
            self.historical_override = {
                str(k).lower(): str(v).lower() for k, v in override_data.items()
            }

        self.keep_double_newlines = keep_double_newlines
        self.max_candidates = max_candidates
        self.force_overrides = force_overrides
        self.override_bonus = float(override_bonus)

        self._freq = (
            _ModernWordScorer(min_zipf=wordfreq_min_zipf)
            if use_wordfreq
            else _ModernWordScorer(min_zipf=999.0)
        )

    # ---------- name protection helpers ----------

    @staticmethod
    def _clean_for_match(tok: str) -> str:
        # normalize curly apostrophe to straight for matching
        tok = tok.replace("'", "'")
        return re.sub(rf"[^{HistoricalNormalizerV2._LETTER_CLASS}'-]", "", tok).lower()

    def _is_irish_token(self, tok: str, pending_prefix: bool) -> Tuple[bool, bool]:
        clean = self._clean_for_match(tok)
        if not clean:
            return False, False

        is_prefix = clean in self.irish_prefixes
        if is_prefix:
            return True, False

        if clean in self.irish_surnames or clean in self.irish_first_names:
            return True, False
        if clean in self.irish_places:
            return True, False
        if clean in self.irish_prefixes:
            return True, True
        if pending_prefix:
            return True, False

        return False, False

    # ---------- casing ----------

    @staticmethod
    def _preserve_case(modern: str, original: str) -> str:
        if original.isupper():
            return modern.upper()
        if original and original[0].isupper():
            return modern.capitalize()
        return modern

    # ---------- preprocessing ----------

    @staticmethod
    def _pre_normalize_text(text: str) -> str:
        """
        Docstring for _pre_normalize_text

        :param text: Description
        :type text: str
        :return: Description
        :rtype: str
        """
        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # Normalize smart quotes/apostrophes
        text = text.replace("“", '"').replace("”", '"')
        text = text.replace("'", "'").replace("`", "'")

        # Normalize dashes
        text = text.replace("—", "--").replace("-", "-")

        # text = re.sub(r"^I\s+(?=[A-Z][a-z]+\s+[A-Z])", "I, ", text, flags=re.MULTILINE)

        return text

    # ---------- candidate generation helpers ----------

    @staticmethod
    def _only_letters_apostrophes(word: str) -> bool:
        return bool(re.fullmatch(rf"[{HistoricalNormalizerV2._LETTER_CLASS}'-]+", word))

    @staticmethod
    def _dedupe(seq: Iterable[str]) -> list:
        seen = set()
        out = []
        for x in seq:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    def _gen_candidates(self, lower: str, protect_terminal_e: bool = False) -> list:
        cands = [lower]

        # Override candidate (data-driven). Not hard-forced here.
        ov = self.historical_override.get(lower)
        if ov and ov != lower:
            cands.append(ov)

        # Place map candidate (scoped to place names)
        mapped = self.historical_place_map.get(lower)
        if mapped:
            cands.append(mapped.lower())

        # vv -> w
        if "vv" in lower:
            cands.append(lower.replace("vv", "w"))

        # w -> u
        if "w" in lower:
            cands.append(lower.replace("w", "u"))

        # initial ff -> f
        if lower.startswith("ff") and len(lower) > 2:
            cands.append("f" + lower[2:])

        # long s ſ -> s
        if "ſ" in lower:
            cands.append(lower.replace("ſ", "s"))

        # i/j normalization: initial i -> j
        if lower.startswith("i") and len(lower) > 2:
            cands.append("j" + lower[1:])

        # i/j inside word (controlled): proiects -> projects, subiect -> subject, etc.
        if "oi" in lower:
            cands.append(lower.replace("oi", "oj"))

        # terminal -ie -> -y (e.g., Dorothie -> Dorothy)
        if lower.endswith("ie") and len(lower) > 3:
            cands.append(lower[:-2] + "y")

        if "i" in lower:
            cands.append(lower.replace("i", "y"))

        if (not protect_terminal_e) and lower.endswith("es") and len(lower) > 3:
            cands.append(lower[:-2] + "s")

        # u/v: initial v -> u
        if lower.startswith("v") and len(lower) > 2:
            cands.append("u" + lower[1:])

        # u/v: interior u -> v (seruant -> servant)
        if "u" in lower:
            cands.append(re.sub(r"(?<=[a-z])u(?=[a-z])", "v", lower))

        # v->u between consonants (rare; candidate only)
        if "v" in lower:
            cands.append(
                re.sub(
                    r"(?<=[bcdfghjklmnpqrstvwxyz])v(?=[bcdfghjklmnpqrstvwxyz])",
                    "u",
                    lower,
                )
            )

        # -eing -> -ing
        if lower.endswith("eing") and len(lower) > 5:
            cands.append(lower[:-4] + "ing")

        # terminal -e drop
        if (not protect_terminal_e) and lower.endswith("e") and len(lower) > 3:
            cands.append(lower[:-1])

        # collapse repeated vowel at end: bee -> be, hee -> he
        if re.search(r"(aa|ee|ii|oo|uu)$", lower):
            cands.append(re.sub(r"(aa|ee|ii|oo|uu)$", lambda m: m.group(0)[0], lower))

        # Common historical variant: "shanon" -> "shannon" (e.g., ballyshanon).
        if "shanon" in lower:
            cands.append(lower.replace("shanon", "shannon"))

        # Filter + dedupe + cap
        cands = [c for c in cands if c and self._only_letters_apostrophes(c)]
        cands = self._dedupe(cands)
        if len(cands) > self.max_candidates:
            cands = cands[: self.max_candidates]
        return cands

    # ---------- scoring ----------

    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)

        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, start=1):
            cur = [i]
            for j, cb in enumerate(b, start=1):
                ins = cur[j - 1] + 1
                dele = prev[j] + 1
                sub = prev[j - 1] + (0 if ca == cb else 1)
                cur.append(min(ins, dele, sub))
            prev = cur
        return prev[-1]

    @staticmethod
    def _heuristic_modernness_penalty(w: str) -> float:
        pen = 0.0
        if "vv" in w:
            pen += 2.0
        if w.startswith("ff"):
            pen += 1.5
        if "ſ" in w:
            pen += 2.0
        if w.startswith("v"):
            pen += 0.6
        if w.endswith("e") and len(w) > 3:
            pen += 0.2
        return pen

    def _is_override_candidate(self, orig_lower: str, cand_lower: str) -> bool:
        return self.historical_override.get(orig_lower) == cand_lower

    def _choose_candidate(self, original: str) -> str:
        lower = original.lower()

        # Optional: hard-force overrides
        if self.force_overrides and lower in self.historical_override:
            return self.historical_override[lower]

        protect_terminal_e = bool(original) and original[0].isupper()
        cands = self._gen_candidates(lower, protect_terminal_e=protect_terminal_e)
        # Frequency scoring
        freq_scores: Dict[str, float] = {}
        for c in cands:
            fs = self._freq.score(c)
            if fs is not None:
                freq_scores[c] = fs

        if freq_scores:
            # Prefer higher frequency; use override as tie-breaker; then edit distance/penalty
            passing = [
                (c, s) for c, s in freq_scores.items() if s >= self._freq.min_zipf
            ]
            pool = passing if passing else list(freq_scores.items())

            def rank(item):
                c, s = item
                override_tiebreak = 0 if self._is_override_candidate(lower, c) else 1
                return (
                    -s,
                    override_tiebreak,
                    self._edit_distance(lower, c),
                    self._heuristic_modernness_penalty(c),
                )

            return sorted(pool, key=rank)[0][0]

        # Heuristic-only ranking
        def hkey(c: str):
            bonus = (
                -self.override_bonus if self._is_override_candidate(lower, c) else 0.0
            )
            return (
                self._heuristic_modernness_penalty(c) + bonus,
                self._edit_distance(lower, c),
                abs(len(c) - len(lower)),
                len(c),
            )

        return sorted(cands, key=hkey)[0]

    # ---------- main normalize ----------

    def normalize(self, text: str) -> NormalizedDocument:
        visual = text
        text = self._pre_normalize_text(text)
        normalized_chars = []
        char_map: Dict[int, int] = {}

        pending_prefix = False
        a_i = 0
        line_start = True

        tokens = list(self._TOKEN_RE.finditer(text))
        i = 0
        while i < len(tokens):
            m = tokens[i]
            tok = m.group(0)
            start = m.start()

            if line_start and tok == "I":
                normalized_chars.append("I")
                char_map[a_i] = start
                a_i += 1

                normalized_chars.append(",")
                char_map[a_i] = start
                a_i += 1

                line_start = False
                i += 1
                continue

            if self._WORD_RE.fullmatch(tok):
                # ---- O + IrishSurname -> O'IrishSurname join rule ----
                if tok.lower() in {"o", "ó"}:
                    j = i + 1
                    # Skip whitespace and punctuation tokens
                    while j < len(tokens):
                        t = tokens[j].group(0)
                        if self._WORD_RE.fullmatch(t):
                            break
                        if t.isspace() or (len(t) == 1 and not t.isalnum()):
                            j += 1
                            continue
                        break

                    if j < len(tokens) and self._WORD_RE.fullmatch(tokens[j].group(0)):
                        next_m = tokens[j]
                        next_tok = next_m.group(0)
                        next_start = next_m.start()

                        # Normalize the next token first (so Neale -> Neill happens)
                        next_is_irish, _ = self._is_irish_token(next_tok, False)
                        if next_is_irish:
                            next_out = next_tok
                        else:
                            next_out = self._preserve_case(
                                self._choose_candidate(next_tok), next_tok
                            )

                        clean_next_out = self._clean_for_match(next_out)
                        if clean_next_out in self.irish_surnames:
                            joined = tok + "'" + next_out

                            # Emit joined token; map O' to O's start and surname to its own start
                            for k_idx, ch in enumerate(joined):
                                normalized_chars.append(ch)
                                if k_idx <= 1:  # "O'"
                                    orig_pos = start
                                else:
                                    k = int(
                                        (k_idx - 2)
                                        * (max(len(next_tok) - 1, 0))
                                        / max(len(next_tok) - 1, 1)
                                    )
                                    orig_pos = next_start + min(k, len(next_tok) - 1)

                                char_map[a_i] = orig_pos
                                a_i += 1

                            pending_prefix = False
                            line_start = False
                            i = j + 1
                            continue
                # ---- end join rule ----

                is_irish, pending_prefix = self._is_irish_token(tok, pending_prefix)

                if is_irish:
                    out = tok
                else:
                    chosen_lower = self._choose_candidate(tok)
                    out = self._preserve_case(chosen_lower, tok)

                # capitalize known place names for BERT
                clean_out = self._clean_for_match(out)
                if clean_out in self.irish_places:
                    out = out.capitalize()

                for j, ch in enumerate(out):
                    normalized_chars.append(ch)
                    if len(out) == 1:
                        orig_pos = start
                    else:
                        k = int(j * (max(len(tok) - 1, 0)) / max(len(out) - 1, 1))
                        orig_pos = start + min(k, len(tok) - 1)
                    char_map[a_i] = orig_pos
                    a_i += 1

            elif tok.isspace():
                if self.keep_double_newlines and "\n\n" in tok:
                    new_tok = "\n\n"
                else:
                    new_tok = " "

                for ch in new_tok:
                    if normalized_chars and normalized_chars[-1] == ch:
                        continue
                    normalized_chars.append(ch)
                    char_map[a_i] = start
                    a_i += 1

                if "\n" in tok:
                    pending_prefix = False

            else:
                for j, ch in enumerate(tok):
                    normalized_chars.append(ch)
                    char_map[a_i] = start + j
                    a_i += 1
                pending_prefix = False

            line_start = False
            i += 1

        return NormalizedDocument(
            visual_layer=visual,
            normalized_layer="".join(normalized_chars),
            char_map=char_map,
        )


# ---------- convenience wrapper ----------

_NORMALIZER_V2: Optional[HistoricalNormalizerV2] = None


def normalize_v2(
    visual_text: str,
    irish_names_path: str = "services/normalize/irish_names.json",
    historical_override_path: str = "services/normalize/hist_override.json",
) -> Tuple[str, Dict[int, int]]:
    global _NORMALIZER_V2
    if _NORMALIZER_V2 is None:
        _NORMALIZER_V2 = HistoricalNormalizerV2(
            irish_names_path=irish_names_path,
            historical_override_path=historical_override_path,
            keep_double_newlines=True,
            use_wordfreq=True,
            wordfreq_min_zipf=2.5,
            max_candidates=24,
            force_overrides=True,  # safer default
            override_bonus=0.25,
        )

    doc = _NORMALIZER_V2.normalize(visual_text)
    return doc.normalized_layer, doc.char_map
