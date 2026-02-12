from typing import Optional
import re

from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz.distance import Levenshtein
from fuzzywuzzy import fuzz  # Jaro-Winkler approximation
import numpy as np
from sentence_transformers import SentenceTransformer

from services.ranking.score_explainer import ScoreExplainer


class Eras:
    EARLY_MODERN = "early-modern-1500-1749"
    MODERN = "modern-1750-1922"
    PRESENT_DAY = "present-day"

    ERA_RANGES = {
        EARLY_MODERN: (1500, 1749),
        MODERN: (1750, 1922),
        PRESENT_DAY: (1923, 2100),  # Bit of extra padding incase this does amazing
    }
    ALL_ERAS = [EARLY_MODERN, MODERN, PRESENT_DAY]

    @classmethod
    def get_doc_era(cls, year: int):
        for era, (start, end) in cls.ERA_RANGES.items():
            if start <= year <= end:
                return era
        return None


class SemanticRanker:
    "Candidate Generation via string similarity"

    def __init__(self, model):
        self.model = model
        self.minimum_candidates = 10
        self.default_top_k = 8

    def rank_by_sim(
        self,
        mention,
        candidates,
        weights=(0.5, 0.25, 0.25),
        threshold=70.0,
        top_k=None,
        min_candidates=None,
    ):
        """
        Docstring for rank_by_sim

        :param self: Description
        :param mention: NER entity
        :param candidates: List of candidates from SPARQL
        :param weights: Semantics levenstien, Jarowrinkler
        :param threshold: Min hybrid score to be passed onto context
        :param top_k: Max numbers of candidates to return
        :param min_candidates: Override minimum candidates
        """

        if top_k is None:
            top_k = self.default_top_k
        if min_candidates is None:
            min_candidates = self.minimum_candidates

        if len(candidates) <= min_candidates:
            return candidates
        if self.model is None:
            return candidates

        # Semantics
        texts = [mention.lower()] + [c.lower() for c in candidates]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        label_vector = embeddings[0].reshape(1, -1)
        candidate_vectors = embeddings[1:]
        semantic_similarity = (
            cosine_similarity(label_vector, candidate_vectors)[0] * 100  # Fixed
        )

        results = []
        for i, candidate in enumerate(candidates):
            sim_score = float(semantic_similarity[i])
            lev_sim = (
                Levenshtein.normalized_similarity(mention.lower(), candidate.lower())
                * 100
            )
            jw_sim = fuzz.ratio(mention.lower(), candidate.lower())

            hybrid_score = round(
                sim_score * weights[0] + lev_sim * weights[1] + jw_sim * weights[2],
                1,
            )
            if hybrid_score >= threshold:
                results.append(
                    {
                        "candidate": candidate,
                        "hybrid": hybrid_score,
                        "semantic": round(sim_score, 1),
                        "levenshtein": round(lev_sim, 1),
                        "jaro_winkler": round(jw_sim, 1),
                    }
                )
        ranked = sorted(results, key=lambda x: x["hybrid"], reverse=True)
        filtered_candidates = [r["candidate"] for r in ranked[:top_k]]

        # print(
        #    f"Filtered: {len(filtered_candidates)}/{len(results)} passed threshold {threshold}%"
        # )
        return filtered_candidates


def _load_semantic_model():
    """
    Prefer local model loading so backend still starts in offline environments.
    Falls back to None (neutral neural scoring) when model isn't available.
    """
    try:
        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception:
        try:
            return SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            return None


SEMANTIC_RANKER = SemanticRanker(model=_load_semantic_model())


class CandidateRanker:

    def __init__(
        self,
        data: dict,
        loc_graph,
        document_year: Optional[int] = None,
        use_semantic_filter: bool = False,
        semantic_threshold: float = 70.0,
        semantic_top_k: int = 8,
        use_neural_rerank: bool = True,
    ):
        self.data = data
        self.entities = data["ents"]
        self.raw_text = data["visual"]
        self.normalised_text = data["normalized"]
        self.location_graph = loc_graph
        self.document_year = 1641  # document_year
        self.document_era = "early-modern-1500-1749"
        self.use_neural_rerank = use_neural_rerank
        self.semantic_model = SEMANTIC_RANKER.model
        self._embedding_cache = {}
        if use_semantic_filter:
            self._apply_semantic_filtering(
                SEMANTIC_RANKER, semantic_threshold, semantic_top_k
            )
        self.possible_locations = self.get_locations()
        self.explainer = ScoreExplainer(self)

    def _apply_semantic_filtering(
        self, semantic_ranker: SemanticRanker, threshold: float, top_k: int
    ):
        """Apply semantic filtering to location entities before ranking"""
        filtered_count = 0
        for entity in self.entities:
            mention = entity["entity_meta_data"]["text"]
            candidates = entity.get("candidate_entities", [])
            if len(candidates) <= semantic_ranker.minimum_candidates:
                continue
            candidate_labels = [c.get("label", "") for c in candidates]

            filtered_labels = semantic_ranker.rank_by_sim(
                mention=mention,
                candidates=candidate_labels,
                threshold=threshold,
                top_k=top_k,
            )
            filtered_candidates = [
                c for c in candidates if c.get("label", "") in filtered_labels
            ]

            entity["candidate_entities"] = filtered_candidates
            filtered_count += len(filtered_candidates)

            # print(
            #    f"Semantic filter '{mention}': {len(candidates)} → {len(filtered_candidates)} candidates"
            # )

        # print(f"Semantic filtering total: {filtered_count} candidates kept")

    def get_locations(self):
        location_entities = set()
        # print(self.entities)
        for entity in self.entities:
            # print(entity)
            if entity["entity_meta_data"]["label"] == "LOC":
                location_mention = entity["entity_meta_data"]["text"]
                location_entities.add(location_mention.lower())
        return location_entities

    # Main rank
    def rank(self, top_k=5):
        """Function to rank the top 5 entites if applicable"""
        rank_results = {}
        for entity in self.entities:
            entity_mention = entity["entity_meta_data"]["text"]
            rank = self.rank_entity_mention(entity, top_k)
        return

    def rank_entity_mention(self, entity, top_k: int = 5):
        mention = entity["entity_meta_data"]["text"]
        label = entity["entity_meta_data"]["label"]
        candidates = entity.get("candidate_entities", [])
        start = entity["entity_meta_data"]["start"]
        end = entity["entity_meta_data"]["end"]
        print(mention)

        if not candidates:
            return []

        scored_mentions = []
        for candidate in candidates:
            score = self.score_candidate(mention, candidate, label)
            candidate["score"] = score
            candidate["confidence"] = self.get_confidence_level(score)
            candidate["explanation"] = self.explainer.explain_score(
                mention, candidate, label
            )
            print(candidate)
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        if top_k and len(candidates) > top_k:
            entity["candidate_entities"] = candidates[:top_k]

    def score_candidate(self, mention, candidate, label):
        """Calculate the score for a candidate"""

        if label == "PER":
            return self.score_person_candidate(mention, candidate, label)
        elif label == "LOC":
            return self.score_location_candidate(mention, candidate, label)
        return 0.0

    def score_person_candidate(self, mention, candidate, label):
        person_features = {
            "name": self.get_name_score(mention, candidate),
            "era": self.get_era_score(candidate, label),
            "residence": self.get_residence_score(candidate),
            "floruit": self.get_floruit_score(candidate),
            "neural": self.get_neural_score(mention, candidate, label),
        }
        candidate["_feature_scores"] = person_features

        weights = {
            "name": 0.32,
            "era": 0.20,
            "residence": 0.18,
            "floruit": 0.12,
            "neural": 0.18,
        }

        weighted_sum = sum(person_features[f] * weights[f] for f in person_features)
        return weighted_sum

    def score_location_candidate(self, mention, candidate, label):
        location_features = {
            "name": self.get_location_name_score(mention, candidate),
            "hierarchy": self.get_hierarchy_score(candidate, mention),
            "type_match": self.get_type_score(candidate, mention, label),
            "historical": self.get_historical_score(candidate),
            "neural": self.get_neural_score(mention, candidate, label),
        }
        candidate["_feature_scores"] = location_features

        weights = {
            "name": 0.25,
            "hierarchy": 0.25,
            "type_match": 0.18,
            "historical": 0.12,
            "neural": 0.20,
        }
        weighted_total = sum(
            location_features[feature] * weights[feature]
            for feature in location_features
        )
        return weighted_total

    def _get_embedding(self, text):
        key = (text or "").strip()
        if not key:
            return None
        emb = self._embedding_cache.get(key)
        if emb is not None:
            return emb
        if self.semantic_model is None:
            return None
        emb = self.semantic_model.encode(key, show_progress_bar=False)
        self._embedding_cache[key] = emb
        return emb

    def _build_candidate_profile_text(self, candidate, label):
        if label == "PER":
            parts = [
                candidate.get("label") or "",
                candidate.get("eras") or "",
                candidate.get("floruitEarliest") or "",
                candidate.get("floruitLatest") or "",
            ]
            residences = candidate.get("residencesLabels") or []
            if residences:
                parts.append(" ".join(str(x) for x in residences if x))
            return " | ".join(str(p) for p in parts if p)

        if label == "LOC":
            parts = [
                candidate.get("english") or "",
                candidate.get("irish") or "",
                candidate.get("era") or "",
            ]
            types = candidate.get("types") or []
            if types:
                parts.append(" ".join(str(x) for x in types if x))
            parent_labels = candidate.get("parentLabels") or []
            if parent_labels:
                parts.append(" ".join(str(x) for x in parent_labels if x))
            historical = candidate.get("historicalApproximations") or []
            if historical:
                parts.append(" ".join(str(x) for x in historical if x))
            return " | ".join(str(p) for p in parts if p)

        return ""

    def get_neural_score(self, mention, candidate, label):
        if not self.use_neural_rerank:
            return 0.5

        mention_text = (mention or "").strip()
        if not mention_text:
            return 0.5

        context = self.get_entity_context(mention, window=120)
        query_text = mention_text if not context else f"{mention_text}. context: {context}"
        candidate_text = self._build_candidate_profile_text(candidate, label)
        if not candidate_text:
            return 0.5

        query_emb = self._get_embedding(query_text)
        cand_emb = self._get_embedding(candidate_text)
        if query_emb is None or cand_emb is None:
            return 0.5

        cosine = float(cosine_similarity([query_emb], [cand_emb])[0][0])
        normalized = (cosine + 1.0) / 2.0
        return float(np.clip(normalized, 0.0, 1.0))

    def get_location_name_score(self, mention, candidate):
        mention_norm = self._normalize_place_text(mention)
        label_norm = self._normalize_place_text(candidate.get("english") or "")
        if not mention_norm or not label_norm:
            return 0.0
        if mention_norm == label_norm:
            return 1.0
        if mention_norm in label_norm or label_norm in mention_norm:
            return 0.8
        token_ratio = fuzz.token_sort_ratio(mention_norm, label_norm) / 100.0
        if token_ratio >= 0.85:
            return 0.8
        if token_ratio >= 0.7:
            return 0.5
        return 0.0

    def get_floruit_score(self, candidate):
        if not self.document_year:
            return 0.5

        start = candidate.get("floruitEarliest", "")
        end = candidate.get("floruitLatest", "")

        if not start or not end:
            return 0.4

        try:  # date parsing
            start_year = int(start.split("-")[0])
            end_year = int(end.split("-")[0])
        except (ValueError, IndexError):
            return 0.3

        if start_year <= self.document_year <= end_year:
            return 1.0

        if self.document_year < start_year:
            year_gap = start_year - self.document_year
        else:
            year_gap = self.document_year - end_year

        if year_gap <= 5:
            return 0.8  # Close
        elif year_gap <= 20:
            return 0.6
        return 0.1

    def get_name_score(self, mention, candidate):
        """Score name similarity between mention text and candidate label."""
        mention_text = (mention or "").strip().lower()
        raw_label = (candidate.get("label") or "").strip().lower()
        if not mention_text or not raw_label:
            return 0.0

        # Convert labels like "Finch_Martha_c17" to "martha finch".
        parts = [p for p in raw_label.split("_") if p]
        parts = [p for p in parts if not re.fullmatch(r"c\d{1,2}", p)]
        if len(parts) >= 2:
            label_text = f"{' '.join(parts[1:])} {parts[0]}"
        else:
            label_text = raw_label.replace("_", " ")

        mention_tokens = mention_text.split()
        label_tokens = label_text.split()

        mention_last = mention_tokens[-1] if mention_tokens else ""
        label_last = label_tokens[-1] if label_tokens else ""
        mention_first = mention_tokens[0] if mention_tokens else ""
        label_first = label_tokens[0] if label_tokens else ""

        # If surname doesn't match, this is likely the wrong person.
        if mention_last and label_last and mention_last != label_last:
            return 0.0

        full_ratio = fuzz.token_sort_ratio(mention_text, label_text) / 100.0
        first_ratio = fuzz.ratio(mention_first, label_first) / 100.0
        last_ratio = fuzz.ratio(mention_last, label_last) / 100.0

        score = (0.5 * last_ratio) + (0.35 * first_ratio) + (0.15 * full_ratio)
        return round(score, 3)

    def get_residence_score(self, candidate):
        # Start with possible locations, then use the URI's with the Global graph after
        if not self.possible_locations:
            return 0.5  # neutral if the document doesnt mention locations
        residences = candidate.get("residencesLabels", [])

        if not residences or residences == "":
            return 0.3  # penalty

        for residence in residences:
            if residence.lower() in self.possible_locations:
                return 1.0  # direct match

        # Later I want to use the URI for the residence to check if a places parents or children are mentioned
        residence_uri = candidate.get("residences", "")
        if residence_uri and residence_uri in self.location_graph:
            residence_node = self.location_graph[residence_uri]
            ancestors = residence_node.get("all_ancestors", [])

            for ancestor in ancestors:
                ancestor_label = ancestor.get("label", "").lower()
                if ancestor_label in self.possible_locations:
                    return 0.75  # They reside somewhere to do with a possible location.
        return 0.0

    def get_type_score(self, candidate, mention, label):
        """Match type to what is said around the entity mention
        e.g if County is mentioned we want to increase the score for entries with county but decrease for others
        """

        entity_context = self.get_entity_context(mention, window=50).lower()
        candidate_types = candidate.get("types", [])
        if not candidate_types:
            return 0.3  # no type data = no boost

        types_str = " ".join(candidate_types).lower()

        # Here we make a list of keywords and if that is in the context window then we increase the score
        # Rough function at the moment will ask Declan what he thinks
        if "county" in entity_context:
            if "county" in types_str:
                return 1.0
            else:
                return 0.3

        if "city" in entity_context or "citty" in entity_context:
            if "city" in types_str:
                return 1.0
            else:
                return 0.2

        if "town" in entity_context or "towne" in entity_context:
            if "town" in types_str:
                return 1.0
            else:
                return 0.2

        if "parish" in entity_context:
            if "parish" in types_str:
                return 1.0
            else:
                return 0.2

        if "barony" in entity_context:
            if "barony" in types_str:
                return 1.0
            else:
                return 0.2

        if "province" in entity_context or "prouince" in entity_context:
            if "province" in types_str:
                return 1.0
            else:
                return 0.2

        # No explicit type keyword in context: apply light default priors.
        if "county" in types_str or "province" in types_str:
            return 1.0
        if "town" in types_str and "townland" not in types_str:
            return 0.7
        if "barony" in types_str:
            return 0.6
        if "parish" in types_str:
            return 0.5
        if "townland" in types_str:
            return 0.3
        return 0.5

    def get_hierarchy_score(self, candidate, mention):
        # Reuse geographic consistency against other location mentions in text.
        return self.get_geographic_score(candidate, mention)

    def get_historical_score(self, candidate):
        historical = candidate.get("historicalApproximations") or []
        if not historical:
            return 0.3
        for uri in historical:
            if "/early-modern-1500-1749/" in (uri or "").lower():
                return 1.0
        return 0.7

    def get_geographic_score(self, candidate, mention):
        """
        Use the location graph and other document locations to give merit to candidates
        with hierarchy overlap against other mentioned locations.
        """

        if not self.possible_locations:
            return 0.5

        mention_norm = self._normalize_place_text(mention)
        possible_places = {
            self._normalize_place_text(p) for p in self.possible_locations
        }
        possible_places.discard(mention_norm)
        if not possible_places:
            return 0.5

        candidate_label = self._normalize_place_text(candidate.get("english") or "")
        best_score = 0.0
        if candidate_label and candidate_label in possible_places:
            return 1.0

        # Direct mention-to-candidate fuzzy match for strings like:
        # "Londonderry" <-> "The Towne of Londonderry".
        if mention_norm and candidate_label:
            # Exact self-name match belongs in name_score, not hierarchy_score.
            # Keep only a small hierarchy contribution here.
            if mention_norm == candidate_label:
                best_score = max(best_score, 0.2)
            if mention_norm in candidate_label or candidate_label in mention_norm:
                best_score = max(best_score, 0.35)

        # Soft token overlap for historical prefixes/suffixes.
        if mention_norm and candidate_label:
            mention_tokens = set(mention_norm.split())
            candidate_tokens = set(candidate_label.split())
            if mention_tokens and candidate_tokens:
                overlap_ratio = len(mention_tokens & candidate_tokens) / len(
                    mention_tokens
                )
                if overlap_ratio >= 0.5:
                    best_score = max(best_score, 0.65)

        # If a candidate contains one of the other location mentions,
        # treat as moderate geographic consistency.
        for place in possible_places:
            if place and (place in candidate_label or candidate_label in place):
                best_score = max(best_score, 0.7)

        parent_labels = candidate.get("parentLabels") or []
        for parent_label in parent_labels:
            parent_norm = self._normalize_place_text(parent_label)
            if parent_norm in possible_places:
                best_score = max(best_score, 0.8)

        child_labels = candidate.get("childLabels") or []
        for child_label in child_labels:
            child_norm = self._normalize_place_text(child_label)
            if child_norm in possible_places:
                best_score = max(best_score, 0.7)

        # Province-aware disambiguation:
        # if document context mentions a province (e.g., Ulster),
        # prefer candidates whose province lineage matches it.
        province_names = {"ulster", "munster", "leinster", "connacht", "connaught"}
        mentioned_provinces = {p for p in possible_places if p in province_names}
        if mentioned_provinces:
            candidate_provinces = set()
            for parent_label in candidate.get("parentLabels") or []:
                parent_norm = self._normalize_place_text(parent_label)
                if parent_norm in province_names:
                    candidate_provinces.add(parent_norm)

            if candidate_provinces:
                if candidate_provinces & mentioned_provinces:
                    best_score = max(best_score, 0.95)
                else:
                    # Mismatched province should not outrank in-context geography.
                    best_score = min(best_score, 0.35)
        return best_score

    def _normalize_place_text(self, value):
        value = (value or "").lower()
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        value = re.sub(r"\b(the|of|towne|town)\b", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def get_entity_context(self, mention, window=50):
        text = self.normalised_text.lower()
        mention = mention.lower()

        index = text.find(mention)
        if index == -1:
            return ""

        start = max(0, index - window)
        end = min(len(text), index + len(mention) + window)

        return text[start:end]

    def get_era_score(self, candidate, label):
        if not self.document_era:
            return 0.5  # We have no ERA so must rely on other methods

        if label == "PER":
            return self.check_person_era(candidate)
        elif label == "LOC":
            return self.check_location_era(candidate)
        return 0

    def check_person_era(self, candidate):
        eras = candidate.get("eras")
        if not eras:
            return 0.3  # No certaintiy on era = less score

        if eras.lower() == self.document_era:
            return 1.0
        return 0

    def check_location_era(self, candidate):
        candidate_era = candidate.get("era")
        if not candidate_era:
            return 0.3

        if candidate_era.lower() == self.document_era:
            return 1.0

        # Location name probably matches but need to factor in Historical changes
        if (
            candidate_era.lower() == "present-day"
            and self.document_era != "present-day"
        ):
            return 0.4

        return 0

    def get_confidence_level(self, score):
        if score > 0.75:
            return "High confidence"
        elif score >= 0.5:
            return "Medium Confidence"
        else:
            return "Low confidence"


# cr = CandidateRanker(data, graph)
# x = cr.rank()


if __name__ == "__main__":
    print("Starting")

    data = {
        "visual": "The examination of Jane Armstrong of the County of Dunnigall beinge Sworne -- examined before Vs Henry Finch Esquire Major of the Citty of Londonderry and George Carew Justice of the Peace by Authoryty of Parliment for the Prouince of Vlster, 23 Aprill 1653 Sworned -- examined sayeth In the yeare 1641 there came to her husbands house in the morning Edmond oge Oneale -- Neale oge Oneale, the Sayd Neale O Neale came Caulled William Betty her husband to Come forth to him shee was vnwilling hee should goe be reason shee sawe that Edmond Oneale was there whom shee Knew to be a blody man, but her husband haueing Some hopes that Neale O Neale would not See him receaue hurt cam forth, -- Edmond O Neale Commanded his men to Kill him who flocked aboute him -- one with a peese went to shoote him -- the examinent went between to saue her husband, -- they did not shoote him but Cutt him downe with Swords -- afterwards Came rune after his sonne William Betty who came rune away when they were Killing his father -- Killed him -- Killd Dauid Long stripped the examinent -- Seuerall other -- Commanded his men to hange her if shee would not Confes her mony but by the perswasions of Sume and Gods mercy shee escaped -- no farther Sayeth. Henry Finch",
        "normalized": "The examination of Jane Armstrong of the County of Donegal being Sworn -- examined before Vs Henry Finch Esquire Major of the City of Londonderry and George Carew Justice of the Peace by Authoryty of Parliment for the Province of Ulster, 23 Aprill 1653 Sworned -- examined sayeth In the year 1641 there came to her husbands house in the morning Edmond óg O'neill -- Neill óg O'neill, the Said Neill O'Neill came Caulled William Betty her husband to Come forth to him shee was unwilling he should goe be reason shee saw that Edmond O'neill was there whom shee Knew to be a blody man, but her husband having Some hopes that Neill O'Neill would not See him receaue hurt cam forth, -- Edmond O'Neill Commanded his men to Kill him who flocked about him -- one with a pees went to shoot him -- the examinent went between to save her husband, -- they did not shoot him but Cutt him Down with Swords -- afterwards Came run after his sonne William Betty who came run away when they were Killing his father -- Killed him -- Killd David Long stripped the examinent -- Severall other -- Commanded his men to hang her if shee would not Confs her moni but by the persuasions of Sum and Gods mercy shee escaped -- no farther Sayeth. Henry Finch",
        "ents": [
            {
                "entity_meta_data": {
                    "text": "Jane Armstrong",
                    "label": "PER",
                    "score": 0.9990804195404053,
                    "start": 19,
                    "end": 33,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Armstrong_Jane_c17/v12pgt5",
                        "label": "Armstrong_Jane",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Armstrong_Jane_c17/v12pgt5",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/county/Donegal/v14g1sb",
                        "residencesLabels": ["Donegal", "Dún na nGall"],
                        "floruitEarliest": "1635-01-01",
                        "floruitLatest": "1658-12-31",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Armstrong_Jane_c17/v1g74tz",
                        "label": "Armstrong_Jane",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Armstrong_Jane_c17/v1g74tz",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Belfast/v1sw3d3",
                        "residencesLabels": ["Belfast", "Béal Feirste"],
                        "floruitEarliest": "1636-01-01",
                        "floruitLatest": "1658-12-31",
                        "external_dib": "",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Donegal",
                    "label": "LOC",
                    "score": 0.9438145756721497,
                    "start": 51,
                    "end": 58,
                },
                "candidate_entities": [
                    {
                        "place": "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Donegal/v1qf2y7",
                        "era": "early-modern-1500-1749",
                        "english": "Donegal",
                        "irish": None,
                        "types": ["County", "EarlyModernCounty"],
                        "parentPlace": "",
                        "ancestorHierarchy": [],
                        "all_ancestors": [],
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Henry Finch",
                    "label": "PER",
                    "score": 0.9988594055175781,
                    "start": 93,
                    "end": 104,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Finch_Martha_c17/v1r9nr3",
                        "label": "Finch_Martha",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Finch_Martha_c17/v1r9nr3",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1621-01-01",
                        "floruitLatest": "1647-01-01",
                        "external_dib": "",
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Londonderry",
                    "label": "LOC",
                    "score": 0.9568139314651489,
                    "start": 134,
                    "end": 145,
                },
                "candidate_entities": [
                    {
                        "place": "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/townland/The-Towne-of-Londonderry/v1jty53",
                        "era": "early-modern-1500-1749",
                        "english": "The Towne of Londonderry",
                        "irish": None,
                        "types": ["EarlyModernTownland", "Townland"],
                        "parentPlace": "https://kb.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy | https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy",
                        "ancestorHierarchy": [
                            {
                                "uri": "https://kb.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy",
                                "type": "county",
                                "label": "Derry",
                            },
                            {
                                "uri": "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy",
                                "type": "county",
                                "label": "Derry",
                            },
                        ],
                        "all_ancestors": [
                            "https://kb.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy",
                            "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy",
                        ],
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "George Carew",
                    "label": "PER",
                    "score": 0.8408181667327881,
                    "start": 150,
                    "end": 162,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Carew_George_c17/v1yh3v3",
                        "label": "Carew_George_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Carew_George_c17/v1yh3v3",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-05-29",
                        "floruitLatest": "1629-03-27",
                        "external_dib": "https://www.dib.ie/biography/Carew-Sir-George-a1464",
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Ulster",
                    "label": "LOC",
                    "score": 0.9675813317298889,
                    "start": 230,
                    "end": 236,
                },
                "candidate_entities": [],
            },
            {
                "entity_meta_data": {
                    "text": "Edmond",
                    "label": "PER",
                    "score": 0.9962263107299805,
                    "start": 345,
                    "end": 351,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/FitzGibbon_Edmond-fitzJohn_c17/v14zd3j",
                        "label": "FitzGibbon_Edmond-fitzJohn_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/FitzGibbon_Edmond-fitzJohn_c17/v14zd3j",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1552-01-01",
                        "floruitLatest": "1608-04-23",
                        "external_dib": "https://www.dib.ie/biography/FitzGibbon-Edmond-fitzJohn-a3204",
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "O'neill",
                    "label": "PER",
                    "score": 0.9565929770469666,
                    "start": 355,
                    "end": 362,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v156wgc",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v156wgc",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1520-01-01",
                        "floruitLatest": "1574-10-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Sir-Brian-a6948",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v177wbg",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v177wbg",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1460-01-01",
                        "floruitLatest": "1513-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6955-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v173hhk",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v173hhk",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1490-01-01",
                        "floruitLatest": "1562-04-12",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Brian-a6947",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "label": "ONeill_Conn-Bacach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1484-01-01",
                        "floruitLatest": "1559-07-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Conn-Bacach-a6949",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v1wh85v",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v1wh85v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-01-01",
                        "floruitLatest": "1592-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6915",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Neill",
                    "label": "PER",
                    "score": 0.9960745573043823,
                    "start": 366,
                    "end": 371,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v156wgc",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v156wgc",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1520-01-01",
                        "floruitLatest": "1574-10-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Sir-Brian-a6948",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v177wbg",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v177wbg",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1460-01-01",
                        "floruitLatest": "1513-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6955-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v173hhk",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v173hhk",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1490-01-01",
                        "floruitLatest": "1562-04-12",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Brian-a6947",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "label": "ONeill_Conn-Bacach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1484-01-01",
                        "floruitLatest": "1559-07-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Conn-Bacach-a6949",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v1wh85v",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v1wh85v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-01-01",
                        "floruitLatest": "1592-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6915",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Neill O'Neill",
                    "label": "PER",
                    "score": 0.881671667098999,
                    "start": 393,
                    "end": 406,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v156wgc",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v156wgc",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1520-01-01",
                        "floruitLatest": "1574-10-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Sir-Brian-a6948",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v177wbg",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v177wbg",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1460-01-01",
                        "floruitLatest": "1513-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6955-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v173hhk",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v173hhk",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1490-01-01",
                        "floruitLatest": "1562-04-12",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Brian-a6947",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "label": "ONeill_Conn-Bacach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1484-01-01",
                        "floruitLatest": "1559-07-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Conn-Bacach-a6949",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v1wh85v",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v1wh85v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-01-01",
                        "floruitLatest": "1592-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6915",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "William Betty",
                    "label": "PER",
                    "score": 0.9984279870986938,
                    "start": 420,
                    "end": 433,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Betty_Maria_c18/v1tz58q",
                        "label": "Betty_Maria",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Betty_Maria_c18/v1tz58q",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1687-01-01",
                        "floruitLatest": "1713-01-01",
                        "external_dib": "",
                    }
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Edmond O'neill",
                    "label": "PER",
                    "score": 0.9988471269607544,
                    "start": 524,
                    "end": 538,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v156wgc",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v156wgc",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1520-01-01",
                        "floruitLatest": "1574-10-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Sir-Brian-a6948",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Daniel_c17/v15f5pv",
                        "label": "ONeill_Daniel_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Daniel_c17/v15f5pv",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1612-01-01",
                        "floruitLatest": "1664-10-24",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Daniel-a6919",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Phelim_c17/v1sr1z2",
                        "label": "ONeill_Phelim_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Phelim_c17/v1sr1z2",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1604-01-01",
                        "floruitLatest": "1653-03-10",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Phelim-a6937",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Muirchertach-Duileanach_c16/v17fzj5",
                        "label": "ONeill_Muirchertach-Duileanach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Muirchertach-Duileanach_c16/v17fzj5",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1500-01-01",
                        "floruitLatest": "1560-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Muirchertach-Duileanach-a6964-C",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Owen-Roe_c17/v1y32qy",
                        "label": "ONeill_Owen-Roe_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Owen-Roe_c17/v1y32qy",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1580-01-01",
                        "floruitLatest": "1649-11-06",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Owen-Roe-Ó-Néill-Eoghan-Rua-a6936",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Toirdhealbhach_c17/v1k5p3y",
                        "label": "ONeill_Toirdhealbhach_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Toirdhealbhach_c17/v1k5p3y",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1562-01-01",
                        "floruitLatest": "1640-02-24",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Toirdhealbhach-a6942",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn_c17/v19zct9",
                        "label": "ONeill_Conn_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn_c17/v19zct9",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1575-01-01",
                        "floruitLatest": "1619-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Conn-a6918",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Hugh_c17/v15fr3c",
                        "label": "ONeill_Hugh_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Hugh_c17/v15fr3c",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1605-01-01",
                        "floruitLatest": "1660-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Hugh-Aodh-Dubh-Ó-Néill-a6926",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v177wbg",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v177wbg",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1460-01-01",
                        "floruitLatest": "1513-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6955-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Matthew_c16/v1g9h3v",
                        "label": "ONeill_Matthew_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Matthew_c16/v1g9h3v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1510-01-01",
                        "floruitLatest": "1558-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Matthew-Feardorcha-a6954",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Hugh_c17/v184nnv",
                        "label": "ONeill_Hugh_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Hugh_c17/v184nnv",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1550-07-01",
                        "floruitLatest": "1616-07-20",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Hugh-a6962",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Niall-Óg_c16/v14x4wy",
                        "label": "ONeill_Niall-Óg_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Niall-Óg_c16/v14x4wy",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1485-01-01",
                        "floruitLatest": "1537-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Niall-Óg-a6964-B",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Niall-Mór_c16/v1zzv22",
                        "label": "ONeill_Niall-Mór_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Niall-Mór_c16/v1zzv22",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1450-01-01",
                        "floruitLatest": "1512-04-11",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Niall-Mór-a6964",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v173hhk",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v173hhk",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1490-01-01",
                        "floruitLatest": "1562-04-12",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Brian-a6947",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Shane_c16/v13yd5f",
                        "label": "ONeill_Shane_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Shane_c16/v13yd5f",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1530-01-01",
                        "floruitLatest": "1567-06-02",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Shane-Seaán-a6966",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Aodh-Buidhe_c16/v15nth8",
                        "label": "ONeill_Aodh-Buidhe_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Aodh-Buidhe_c16/v15nth8",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1480-01-01",
                        "floruitLatest": "1524-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Aodh-Buidhe-a6964-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Turlough-Luineach_c16/v11zc1k",
                        "label": "ONeill_Turlough-Luineach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Turlough-Luineach_c16/v11zc1k",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1530-01-01",
                        "floruitLatest": "1595-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Turlough-Luineach-a6967",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "label": "ONeill_Conn-Bacach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1484-01-01",
                        "floruitLatest": "1559-07-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Conn-Bacach-a6949",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Domhnall-Clárach_c16/v1dnb54",
                        "label": "ONeill_Domhnall-Clárach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Domhnall-Clárach_c16/v1dnb54",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1445-01-01",
                        "floruitLatest": "1509-08-06",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Domhnall-Clárach-a9193-B",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Neil_c17/v14rc4m",
                        "label": "ONeill_Neil_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Neil_c17/v14rc4m",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1657-01-01",
                        "floruitLatest": "1690-07-08",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Neil-Niall-a6935",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v1wh85v",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v1wh85v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-01-01",
                        "floruitLatest": "1592-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6915",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "Edmond O'Neill",
                    "label": "PER",
                    "score": 0.9978647232055664,
                    "start": 681,
                    "end": 695,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v156wgc",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v156wgc",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1520-01-01",
                        "floruitLatest": "1574-10-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Sir-Brian-a6948",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Daniel_c17/v15f5pv",
                        "label": "ONeill_Daniel_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Daniel_c17/v15f5pv",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1612-01-01",
                        "floruitLatest": "1664-10-24",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Daniel-a6919",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Phelim_c17/v1sr1z2",
                        "label": "ONeill_Phelim_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Phelim_c17/v1sr1z2",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1604-01-01",
                        "floruitLatest": "1653-03-10",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Phelim-a6937",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Muirchertach-Duileanach_c16/v17fzj5",
                        "label": "ONeill_Muirchertach-Duileanach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Muirchertach-Duileanach_c16/v17fzj5",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1500-01-01",
                        "floruitLatest": "1560-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Muirchertach-Duileanach-a6964-C",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Owen-Roe_c17/v1y32qy",
                        "label": "ONeill_Owen-Roe_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Owen-Roe_c17/v1y32qy",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1580-01-01",
                        "floruitLatest": "1649-11-06",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Owen-Roe-Ó-Néill-Eoghan-Rua-a6936",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Toirdhealbhach_c17/v1k5p3y",
                        "label": "ONeill_Toirdhealbhach_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Toirdhealbhach_c17/v1k5p3y",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1562-01-01",
                        "floruitLatest": "1640-02-24",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Toirdhealbhach-a6942",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn_c17/v19zct9",
                        "label": "ONeill_Conn_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn_c17/v19zct9",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1575-01-01",
                        "floruitLatest": "1619-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Conn-a6918",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Hugh_c17/v15fr3c",
                        "label": "ONeill_Hugh_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Hugh_c17/v15fr3c",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1605-01-01",
                        "floruitLatest": "1660-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Hugh-Aodh-Dubh-Ó-Néill-a6926",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v177wbg",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v177wbg",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1460-01-01",
                        "floruitLatest": "1513-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6955-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Matthew_c16/v1g9h3v",
                        "label": "ONeill_Matthew_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Matthew_c16/v1g9h3v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1510-01-01",
                        "floruitLatest": "1558-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Matthew-Feardorcha-a6954",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Hugh_c17/v184nnv",
                        "label": "ONeill_Hugh_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Hugh_c17/v184nnv",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1550-07-01",
                        "floruitLatest": "1616-07-20",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Hugh-a6962",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Niall-Óg_c16/v14x4wy",
                        "label": "ONeill_Niall-Óg_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Niall-Óg_c16/v14x4wy",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1485-01-01",
                        "floruitLatest": "1537-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Niall-Óg-a6964-B",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Niall-Mór_c16/v1zzv22",
                        "label": "ONeill_Niall-Mór_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Niall-Mór_c16/v1zzv22",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1450-01-01",
                        "floruitLatest": "1512-04-11",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Niall-Mór-a6964",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Brian_c16/v173hhk",
                        "label": "ONeill_Brian_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Brian_c16/v173hhk",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1490-01-01",
                        "floruitLatest": "1562-04-12",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Brian-a6947",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Shane_c16/v13yd5f",
                        "label": "ONeill_Shane_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Shane_c16/v13yd5f",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1530-01-01",
                        "floruitLatest": "1567-06-02",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Shane-Seaán-a6966",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Aodh-Buidhe_c16/v15nth8",
                        "label": "ONeill_Aodh-Buidhe_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Aodh-Buidhe_c16/v15nth8",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1480-01-01",
                        "floruitLatest": "1524-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Aodh-Buidhe-a6964-A",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Turlough-Luineach_c16/v11zc1k",
                        "label": "ONeill_Turlough-Luineach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Turlough-Luineach_c16/v11zc1k",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1530-01-01",
                        "floruitLatest": "1595-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Turlough-Luineach-a6967",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "label": "ONeill_Conn-Bacach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Conn-Bacach_c16/v1x83zq",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1484-01-01",
                        "floruitLatest": "1559-07-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Ó-Néill-Conn-Bacach-a6949",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Domhnall-Clárach_c16/v1dnb54",
                        "label": "ONeill_Domhnall-Clárach_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Domhnall-Clárach_c16/v1dnb54",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1445-01-01",
                        "floruitLatest": "1509-08-06",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Domhnall-Clárach-a9193-B",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Neil_c17/v14rc4m",
                        "label": "ONeill_Neil_c17",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Neil_c17/v14rc4m",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1657-01-01",
                        "floruitLatest": "1690-07-08",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Sir-Neil-Niall-a6935",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/ONeill_Art_c16/v1wh85v",
                        "label": "ONeill_Art_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/ONeill_Art_c16/v1wh85v",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1555-01-01",
                        "floruitLatest": "1592-12-31",
                        "external_dib": "https://www.dib.ie/biography/ONeill-Art-a6915",
                    },
                ],
            },
            {
                "entity_meta_data": {
                    "text": "David Long",
                    "label": "PER",
                    "score": 0.9648051261901855,
                    "start": 1020,
                    "end": 1030,
                },
                "candidate_entities": [
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_Mary_c17/v1y3g4j",
                        "label": "Long_Mary",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_Mary_c17/v1y3g4j",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/townland/Killowen/v19qrd9",
                        "residencesLabels": ["Cill Eoghain", "Killowen"],
                        "floruitEarliest": "1624-01-01",
                        "floruitLatest": "1647-12-31",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Longford_Elizabeth_c17/v1h4gd3",
                        "label": "Longford_Elizabeth",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Longford_Elizabeth_c17/v1h4gd3",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1616-01-01",
                        "floruitLatest": "1642-01-01",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_John_c16/v1zy2t9",
                        "label": "Long_John_c16",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_John_c16/v1zy2t9",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "",
                        "residencesLabels": [],
                        "floruitEarliest": "1545-01-01",
                        "floruitLatest": "1589-12-31",
                        "external_dib": "https://www.dib.ie/biography/Long-John-a4880",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Longe_Joan_c17/v14ns2j",
                        "label": "Longe_Joan",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Longe_Joan_c17/v14ns2j",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1613-01-01",
                        "floruitLatest": "1639-01-01",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_Joan_c17/0100",
                        "label": "Long_Joan",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_Joan_c17/0100",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/county/Dublin/v1s4kv2",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1596-09-19",
                        "floruitLatest": "1606-09-19",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_Margaret_c16/v1qgx81",
                        "label": "Long_Margaret",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_Margaret_c16/v1qgx81",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1573-01-01",
                        "floruitLatest": "1599-01-01",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_Eleanor_c17/v1w91gv",
                        "label": "Long_Eleanor",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_Eleanor_c17/v1w91gv",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1584-01-01",
                        "floruitLatest": "1610-01-01",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Long_Agnes_c16/v14ynw6",
                        "label": "Long_Agnes",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Long_Agnes_c16/v14ynw6",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1558-01-01",
                        "floruitLatest": "1584-01-01",
                        "external_dib": "",
                    },
                    {
                        "person": "https://kg.virtualtreasury.ie/person/Longe_Catherine_c16/v19dxc2",
                        "label": "Longe_Catherine",
                        "entity_card": "https://vrti-graph.adaptcentre.ie/entity-card/person/Longe_Catherine_c16/v19dxc2",
                        "eras": "Early-Modern-1500-1749",
                        "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Dublin/v12cw6w",
                        "residencesLabels": ["Baile Átha Cliath", "Dublin"],
                        "floruitEarliest": "1572-01-01",
                        "floruitLatest": "1598-01-01",
                        "external_dib": "",
                    },
                ],
            },
        ],
    }
    cr = CandidateRanker(data, graph)
    x = cr.rank()
