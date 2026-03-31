from typing import List
import re

from services.entity_linking.sparql_queries import VRTIQuery
from services.sparql_client import VirtualTreasurySPARQL

KG_BASE = "https://kg.virtualtreasury.ie/"
ENTITY_CARD_BASE = "https://vrti-graph.adaptcentre.ie/entity-card/"

EARLY_MODERN_ERA = "Early-Modern-1500-1749"

LOCATION_HIERARCHY_GRAPH = {}


def enrich_with_entity_cards(sparql_json: dict, era: str) -> list[dict]:
    rows = sparql_json.get("results", {}).get("bindings", [])
    enriched_by_uri: dict[str, dict] = {}
    for row in rows:
        person_uri = row["person"]["value"]
        label = row.get("fullName", {}).get("value")
        if label and "," in label:
            surname, forename = label.split(",", 1)
            label = f"{forename.strip()} {surname.strip()}"

        # Extract residences (used in get_residence_score).
        residences = row.get("residences", {}).get("value", "")
        raw_residences_labels = row.get("residenceLabels", {}).get("value", "")
        if raw_residences_labels:
            residencesLabels = split_by_pipe(raw_residences_labels)
        elif residences:
            residencesLabels = []
            for residence_uri in residences.split("|"):
                residence_uri = residence_uri.strip()
                if not residence_uri:
                    continue
                parts = residence_uri.rstrip("/").split("/")
                # VRTI place URI shape is typically .../<placeName>/<id>.
                if len(parts) >= 2:
                    derived = parts[-2].replace("_", " ")
                    if derived and derived not in residencesLabels:
                        residencesLabels.append(derived)
        else:
            residencesLabels = []

        # Extract floruit dates (used in get_floruit_score)
        floruitEarliest = row.get("floruitLower", {}).get("value", "")
        floruitLatest = row.get("floruitUpper", {}).get("value", "")

        # dib - external link
        dib_reference = row.get("dib", {}).get("value", "")

        # Fallback for label if not present
        if not label:
            label = person_uri.rstrip("/").split("/")[-2]

        vrti_card = to_entity_card_url(person_uri)
        candidate = {
            "person": person_uri,
            "label": label,
            "entity_card": vrti_card,
            "eras": era,
            "residences": residences,
            "residencesLabels": residencesLabels,
            "floruitEarliest": floruitEarliest,
            "floruitLatest": floruitLatest,
            "external_dib": dib_reference,
        }

        existing = enriched_by_uri.get(person_uri)
        if not existing:
            enriched_by_uri[person_uri] = candidate
            continue

        # Merge duplicates by URI, preferring non-empty values.
        for field in (
            "label",
            "entity_card",
            "eras",
            "floruitEarliest",
            "floruitLatest",
            "external_dib",
        ):
            if not existing.get(field) and candidate.get(field):
                existing[field] = candidate[field]

        if not existing.get("residences") and candidate.get("residences"):
            existing["residences"] = candidate["residences"]

        merged_labels = list(existing.get("residencesLabels", []))
        for lbl in candidate.get("residencesLabels", []):
            if lbl and lbl not in merged_labels:
                merged_labels.append(lbl)
        existing["residencesLabels"] = merged_labels

    return list(enriched_by_uri.values())


def split_by_pipe(entity_row: str):
    label_list = []
    labels = entity_row.split("|")
    for label in labels:
        label = label.strip()
        if "," in label:
            # label = label.replace(",", "")
            surname, forename = label.split(",", 1)
            label = forename + " " + surname
        label_list.append(label)
    return label_list


def extract_by_hash(entity_row: str) -> List[str]:
    row_values = []
    for uri in entity_row.split("|"):
        uri = uri.strip()
        if not uri:
            continue
        if "#" in uri:
            entity_element = uri.rsplit("#", 1)[-1]
        if entity_element not in row_values:
            row_values.append(entity_element)
    return row_values


def extract_uri_metadata(uri: str):
    if "kg.virtualtreasury.ie" not in uri:
        return "External Link"
    segments = uri.split("/")
    if len(segments) > 4:
        return segments[4]
    return "Not Known"


def construct_location_graph_edge(parent_data: str, current_uri: str):
    """
    Docstring for construct_location_graph_edge

    :param parent_data: String of Direct parent
    :type parent_data: str
    :param current_uri: Current URI making graph edges for
    :type current_uri: str
    """
    parent_uris = []

    if not parent_data:
        # No parents, it is top level?
        if current_uri not in LOCATION_HIERARCHY_GRAPH:
            LOCATION_HIERARCHY_GRAPH[current_uri] = {
                "parents": [],
                "children": [],
            }
        return []

    # Now split the parents by |
    for uri in parent_data.split("|"):
        uri = uri.strip()
        if not uri:
            continue

        if not uri.startswith("https://kg.virtualtreasury.ie"):
            continue
        parent_uris.append(uri)

        if uri not in LOCATION_HIERARCHY_GRAPH:
            LOCATION_HIERARCHY_GRAPH[uri] = {"parents": [], "children": []}

        # BI directional edge
        if current_uri not in LOCATION_HIERARCHY_GRAPH[uri]["children"]:
            LOCATION_HIERARCHY_GRAPH[uri]["children"].append(current_uri)

    if current_uri not in LOCATION_HIERARCHY_GRAPH:
        LOCATION_HIERARCHY_GRAPH[current_uri] = {
            "parents": parent_uris,
            "children": [],
        }
    else:
        LOCATION_HIERARCHY_GRAPH[current_uri]["parents"] = parent_uris
    return parent_uris


def extract_info(data):
    rows = data.get("results", {}).get("bindings", [])
    candidates = []
    for row in rows:
        place = row.get("place").get("value")
        if not place:
            continue

        era = extract_uri_metadata(place)
        englishLabel = row.get("labelEn", {}).get("value")
        irishLabel = row.get("labelGa", {}).get("value")

        placeType = row.get("types", {}).get("value")
        types = extract_by_hash(placeType) if placeType else []

        parentPlaces = row.get("parentPlaces", {}).get("value")
        parentLabels = row.get("parentLabels", {}).get("value")

        logainmUri = row.get("logainmUri", {}).get("value")
        sameAsLinks = row.get("sameAsLinks", {}).get("value")
        externalResources = row.get("externalResources", {}).get("value")
        vrtiIdentifier = row.get("vrtiIdentifier", {}).get("value")
        historicalApproximations = row.get("historicalApproximations", {}).get("value")

        same_as_list = (
            [s.strip() for s in sameAsLinks.split(" | ")] if sameAsLinks else []
        )
        external_list = (
            [e.strip() for e in externalResources.split(" | ")]
            if externalResources
            else []
        )
        historical_list = (
            [h.strip() for h in historicalApproximations.split(" | ")]
            if historicalApproximations
            else []
        )
        parent_labels_list = (
            [p.strip() for p in parentLabels.split(" | ")] if parentLabels else []
        )

        construct_location_graph_edge(parentPlaces, place)

        if place in LOCATION_HIERARCHY_GRAPH:
            LOCATION_HIERARCHY_GRAPH[place].update(
                {
                    "english": englishLabel,
                    "irish": irishLabel,
                    "era": era,
                    "types": types,
                    "logainm": logainmUri,
                    "same_as": same_as_list,
                    "external_resources": external_list,
                    "vrti_id": vrtiIdentifier,
                    "historical_approximations": historical_list,
                }
            )

        entity_dict = {
            "place": place,
            "era": era,
            "english": englishLabel,
            "irish": irishLabel,
            "types": types,
            "parentPlace": parentPlaces,
            "parentLabels": parent_labels_list,
            "logainm": logainmUri,
            "sameAs": same_as_list,
            "externalResources": external_list,
            "vrtiIdentifier": vrtiIdentifier,
            "historicalApproximations": historical_list,
        }
        candidates.append(entity_dict)
    return candidates


def to_entity_card_url(person_iri: str) -> str:
    if person_iri.startswith(KG_BASE):
        return ENTITY_CARD_BASE + person_iri[len(KG_BASE) :]
    return person_iri  # fallback if unexpected IRI format


def query_person_entity(entity_name: str, era):
    if not entity_name:
        return []
    q1 = VRTIQuery.person_query_profile_early_modern(entity_name)
    res = VirtualTreasurySPARQL.query(q1)
    result = enrich_with_entity_cards(res, era)
    return result


def query_location_entity(entity_name: str, era: str):
    if not entity_name:
        return []
    q1 = VRTIQuery.final_place_query(entity_name)
    res = VirtualTreasurySPARQL.query(q1)
    enriched_resp = extract_info(res)
    return enriched_resp


def query_sparql(entities):
    LOCATION_HIERARCHY_GRAPH.clear()
    ents = []
    for entity in entities:
        # 1. Extract the actual entity
        entity_name = entity.get("text")
        entity_label = entity.get("label")
        found_entities = []
        if entity_label == "PER":
            found_entities = query_person_entity(entity_name, EARLY_MODERN_ERA)
        elif entity_label == "LOC":
            found_entities = query_location_entity(entity_name, EARLY_MODERN_ERA)
        entity_block = {
            "entity_meta_data": entity,
            "candidate_entities": found_entities,
        }
        ents.append(entity_block)
    return ents, LOCATION_HIERARCHY_GRAPH
