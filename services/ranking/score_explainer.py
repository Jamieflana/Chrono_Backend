from typing import Dict, List


class ScoreExplainer:
    """
    Generates human-readable explanations for entity candidate scores.

    This class analyzes why candidates receive their scores based on:
    - Era alignment between candidate and document
    - Geographic/residence overlap with document locations
    - Temporal alignment (floruit dates for persons)
    - Type matching (for locations)
    """

    def __init__(self, candidate_ranker):
        self.ranker = candidate_ranker
        self.location_graph = candidate_ranker.location_graph
        self.document_year = candidate_ranker.document_year
        self.document_era = candidate_ranker.document_era
        self.possible_locations = candidate_ranker.possible_locations

    def explain_score(self, mention: str, candidate: Dict, label: str) -> str:
        """
        Generate a detailed explanation for why a candidate received their score.

        Args:
            mention: The entity mention text from the document
            candidate: The candidate entity dictionary with score
            label: Entity type ("PER" for person, "LOC" for location)

        Returns:
            A human-readable explanation string
        """
        score = candidate.get("score", 0.0)
        entity_name = candidate.get("label", mention)

        if label == "PER":
            return self._explain_person_score(entity_name, candidate, score)
        elif label == "LOC":
            return self._explain_location_score(entity_name, candidate, score)
        else:
            return f"{entity_name} scores {score:.3f}."

    def _explain_person_score(
        self, entity_name: str, candidate: Dict, score: float
    ) -> str:
        """Generate explanation for person entity scores."""
        explanations = []
        explanations.append(f"{entity_name} scores {score:.3f}")
        feature_scores = candidate.get("_feature_scores", {})

        # NAME EXPLANATION
        name_score = feature_scores.get("name")
        if name_score is not None:
            if name_score >= 0.85:
                explanations.append("their name closely matches the mention")
            elif name_score >= 0.6:
                explanations.append("their name partially matches the mention")
            else:
                explanations.append("their name has a weak match to the mention")

        # ERA EXPLANATION
        era_score = feature_scores.get("era")
        if era_score is None:
            era_score = self.ranker.get_era_score(candidate, "PER")
        candidate_era = candidate.get("eras", "unknown")

        if era_score == 1.0:
            explanations.append(
                f"their VRTI era ({candidate_era}) aligns with the "
                f"document era ({self.document_era})"
            )
        elif era_score == 0:
            explanations.append(
                f"their VRTI era ({candidate_era}) does not match the "
                f"document era ({self.document_era})"
            )
        else:
            explanations.append("their era information is incomplete")

        # RESIDENCE EXPLANATION
        residence_score = feature_scores.get("residence")
        if residence_score is None:
            residence_score = self.ranker.get_residence_score(candidate)
        residence_labels = candidate.get("residencesLabels", [])

        if residence_score == 1.0 and residence_labels:
            matching_residence = None
            for res in residence_labels:
                if res.lower() in self.possible_locations:
                    matching_residence = res
                    break

            if matching_residence:
                explanations.append(
                    f"they reside in {matching_residence}, which is "
                    f"mentioned in the document"
                )

        elif residence_score == 0.75:
            residence_uri = candidate.get("residences", "")
            if residence_uri and residence_uri in self.location_graph:
                residence_node = self.location_graph[residence_uri]
                ancestors = residence_node.get("all_ancestors", [])

                for ancestor in ancestors:
                    ancestor_label = ancestor.get("label", "")
                    if ancestor_label.lower() in self.possible_locations:
                        residence_name = (
                            residence_labels[0] if residence_labels else "a location"
                        )
                        explanations.append(
                            f"they reside in {residence_name}, which has an "
                            f"ancestor ({ancestor_label}) mentioned in the document"
                        )
                        break

        elif residence_score == 0.3:
            explanations.append("no residence information is available")

        elif residence_score == 0:
            explanations.append(
                "their known residences are not mentioned in the document"
            )

        # FLORUIT EXPLANATION
        floruit_score = feature_scores.get("floruit")
        if floruit_score is None:
            floruit_score = self.ranker.get_floruit_score(candidate)
        start = candidate.get("floruitEarliest", "")
        end = candidate.get("floruitLatest", "")

        if floruit_score == 1.0 and self.document_year:
            explanations.append(
                f"their floruit period ({start} to {end}) encompasses "
                f"the document year ({self.document_year})"
            )
        elif floruit_score == 0.8 and self.document_year:
            explanations.append(
                f"their floruit period ({start} to {end}) is very close "
                f"to the document year ({self.document_year})"
            )
        elif floruit_score == 0.6 and self.document_year:
            explanations.append(
                f"their floruit period ({start} to {end}) is within 20 years "
                f"of the document year ({self.document_year})"
            )
        elif floruit_score == 0.1 and self.document_year:
            explanations.append(
                f"their floruit period ({start} to {end}) is distant from "
                f"the document year ({self.document_year})"
            )
        elif not start or not end:
            explanations.append("their floruit dates are incomplete")
        elif not self.document_year:
            explanations.append(
                "floruit comparison is not possible without a document year"
            )

        neural_score = feature_scores.get("neural")
        if neural_score is not None:
            if neural_score >= 0.75:
                explanations.append(
                    "the semantic context strongly matches this candidate profile"
                )
            elif neural_score >= 0.6:
                explanations.append(
                    "the semantic context moderately matches this candidate profile"
                )
            else:
                explanations.append(
                    "the semantic context provides limited support for this candidate"
                )

        return self._format_explanation(explanations)

    def _explain_location_score(
        self, entity_name: str, candidate: Dict, score: float
    ) -> str:
        """Generate explanation for location entity scores."""
        explanations = []
        explanations.append(f"{entity_name} scores {score:.3f}")
        feature_scores = candidate.get("_feature_scores", {})

        # NAME EXPLANATION
        name_score = feature_scores.get("name")
        if name_score is not None:
            if name_score >= 0.95:
                explanations.append("its name is an exact match to the mention")
            elif name_score >= 0.75:
                explanations.append("its name is a close match to the mention")
            elif name_score >= 0.5:
                explanations.append("its name partially matches the mention")
            else:
                explanations.append("its name is a weak match to the mention")

        # TYPE MATCH EXPLANATION
        mention = candidate.get("english", entity_name)
        type_score = feature_scores.get("type_match")
        if type_score is None:
            type_score = self.ranker.get_type_score(candidate, mention, "LOC")
        candidate_types = candidate.get("types", [])
        context = self.ranker.get_entity_context(mention, window=50).lower()

        if type_score == 1.0:
            type_keywords = [
                "county",
                "city",
                "citty",
                "town",
                "towne",
                "parish",
                "barony",
                "province",
                "prouince",
            ]
            matched_type = None

            for keyword in type_keywords:
                if keyword in context:
                    matched_type = (
                        keyword.replace("citty", "city")
                        .replace("towne", "town")
                        .replace("prouince", "province")
                    )
                    break

            if matched_type and candidate_types:
                types_str = ", ".join(candidate_types)
                explanations.append(
                    f"its type ({types_str}) aligns with the document context "
                    f"mentioning '{matched_type}'"
                )

        elif type_score < 0.5:
            types_str = ", ".join(candidate_types) if candidate_types else "unknown"
            explanations.append(
                f"its type ({types_str}) does not match the document context"
            )

        elif type_score == 0.5:
            explanations.append(
                "no specific location type is mentioned in the nearby context"
            )

        # HIERARCHY EXPLANATION
        hierarchy_score = feature_scores.get("hierarchy")
        if hierarchy_score is None:
            hierarchy_score = self.ranker.get_hierarchy_score(candidate, mention)

        if hierarchy_score == 1.0:
            explanations.append("it is directly mentioned elsewhere in the document")

        elif hierarchy_score >= 0.75:
            parent_labels = candidate.get("parentLabels", []) or []
            child_labels = candidate.get("childLabels", []) or []
            matched_parent = None
            matched_children = []

            for parent_label in parent_labels:
                if (parent_label or "").lower() in self.possible_locations:
                    matched_parent = parent_label
                    break

            for child_label in child_labels:
                if (child_label or "").lower() in self.possible_locations:
                    matched_children.append(child_label)

            if matched_parent:
                explanations.append(
                    f"its parent place ({matched_parent}) is mentioned in the document"
                )
            if matched_children:
                shown_children = ", ".join(matched_children[:3])
                explanations.append(
                    f"its child places include {shown_children}, which are mentioned in the document"
                )
            if not matched_parent and not matched_children:
                explanations.append(
                    "it has geographic overlap with other locations mentioned in the document"
                )

        elif hierarchy_score == 0:
            explanations.append(
                "it has no geographic overlap with other locations mentioned "
                "in the document"
            )

        # HISTORICAL EXPLANATION
        historical_score = feature_scores.get("historical")
        if historical_score is not None:
            if historical_score == 1.0:
                explanations.append(
                    "it has an early-modern historical approximation in VRTI"
                )
            elif historical_score >= 0.7:
                explanations.append("it has historical approximation links in VRTI")
            else:
                explanations.append("it has no historical approximation link")

        neural_score = feature_scores.get("neural")
        if neural_score is not None:
            if neural_score >= 0.75:
                explanations.append(
                    "its contextual semantic match to the mention is strong"
                )
            elif neural_score >= 0.6:
                explanations.append(
                    "its contextual semantic match to the mention is moderate"
                )
            else:
                explanations.append(
                    "its contextual semantic match to the mention is weak"
                )

        return self._format_explanation(explanations)

    def _format_explanation(self, parts: List[str]) -> str:
        """Format explanation parts into a coherent sentence."""
        if len(parts) == 0:
            return ""
        elif len(parts) == 1:
            return parts[0] + "."
        elif len(parts) == 2:
            return f"{parts[0]} as {parts[1]}."
        else:
            main_parts = ", ".join(parts[1:-1])
            return f"{parts[0]} as {main_parts}, and {parts[-1]}."
