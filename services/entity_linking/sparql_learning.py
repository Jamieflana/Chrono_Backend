import time
from typing import List

from services.entity_linking.sparql_querys import VRTIQuery
from services.sparql_client import VirtualTreasurySPARQL


# /home/jamie/Documents/FinalYear/Dissertation/Chrono/Backend/services/sparql_client.py
KG_BASE = "https://kg.virtualtreasury.ie/"
ENTITY_CARD_BASE = "https://vrti-graph.adaptcentre.ie/entity-card/"

EARLY_MODERN_ERA = "Early-Modern-1500-1749"

raw_data = [
    {
        "text": "Jane Armstrong",
        "label": "PER",
        "score": 0.9999856352806091,
        "start": 19,
        "end": 33,
    },
    {
        "text": "Donegal",
        "label": "LOC",
        "score": 0.9997882843017578,
        "start": 51,
        "end": 58,
    },
    {
        "text": "Henry Finch",
        "label": "PER",
        "score": 0.9999756217002869,
        "start": 93,
        "end": 104,
    },
    {
        "text": "Londonderry",
        "label": "LOC",
        "score": 0.9285251498222351,
        "start": 135,
        "end": 146,
    },
    {
        "text": "George Carew",
        "label": "PER",
        "score": 0.9999857544898987,
        "start": 151,
        "end": 163,
    },
    {
        "text": "Ulster",
        "label": "LOC",
        "score": 0.9802047610282898,
        "start": 231,
        "end": 237,
    },
    {
        "text": "Edmond oge Oneale",
        "label": "PER",
        "score": 0.9993804097175598,
        "start": 347,
        "end": 364,
    },
    {
        "text": "Neale oge Oneale",
        "label": "PER",
        "score": 0.9981517195701599,
        "start": 368,
        "end": 384,
    },
    {
        "text": "Neale O Neale",
        "label": "PER",
        "score": 0.980708658695221,
        "start": 395,
        "end": 408,
    },
    {
        "text": "William Betty",
        "label": "PER",
        "score": 0.9999836087226868,
        "start": 422,
        "end": 435,
    },
    {
        "text": "Edmond Oneale",
        "label": "PER",
        "score": 0.9999924898147583,
        "start": 526,
        "end": 539,
    },
    {
        "text": "Edmond O Neale",
        "label": "PER",
        "score": 0.9999408721923828,
        "start": 682,
        "end": 696,
    },
    {
        "text": "David Long",
        "label": "PER",
        "score": 0.9999738931655884,
        "start": 1021,
        "end": 1031,
    },
    {
        "text": "Sum",
        "label": "PER",
        "score": 0.577739953994751,
        "start": 1165,
        "end": 1168,
    },
    {
        "text": "God",
        "label": "PER",
        "score": 0.584430992603302,
        "start": 1173,
        "end": 1176,
    },
    {
        "text": "Sayeth",
        "label": "LOC",
        "score": 0.9898233413696289,
        "start": 1211,
        "end": 1217,
    },
]

jane_data = [
    {
        "text": "Jane Armstrong",
        "label": "PER",
        "score": 0.9999756217002869,
        "start": 93,
        "end": 104,
    },
]

Donegal_Data = [
    {
        "text": "Cork",
        "label": "LOC",
        "score": 0.9997882843017578,
        "start": 51,
        "end": 58,
    }
]

Ulster_data = [
    {
        "text": "Ulster",
        "label": "LOC",
        "score": 0.9997882843017578,
        "start": 51,
        "end": 58,
    },
    {
        "text": "Donegal",
        "label": "LOC",
        "score": 0.9997882843017578,
        "start": 51,
        "end": 58,
    },
]

Oneil_data = [
    {
        "text": "Neale O Neale",
        "label": "PER",
        "score": 0.9999756217002869,
        "start": 93,
        "end": 104,
    },
]

LOCATION_HIERARCHY_GRAPH = {}


def enrich_with_entity_cards(sparql_json: dict, era: str) -> list[dict]:
    rows = sparql_json.get("results", {}).get("bindings", [])
    enriched = []
    for row in rows:
        person_uri = row["person"]["value"]
        label = row.get("personLabel", {}).get("value")

        # Extract residences (used in get_residence_score)
        residences = row.get("residences", {}).get("value", "")
        raw_residences_labels = row.get("residenceLabels", {}).get("value", "")
        residencesLabels = (
            split_by_pipe(raw_residences_labels) if raw_residences_labels else []
        )

        # Extract floruit dates (used in get_floruit_score)
        floruitEarliest = row.get("floruitEarliest", {}).get("value", "")
        floruitLatest = row.get("floruitLatest", {}).get("value", "")

        # Fallback for label if not present
        if not label:
            label = person_uri.rstrip("/").split("/")[-2]

        vrti_card = to_entity_card_url(person_uri)
        enriched.append(
            {
                "person": person_uri,
                "label": label,
                "entity_card": vrti_card,
                "eras": era,
                "residences": residences,
                "residencesLabels": residencesLabels,
                "floruitEarliest": floruitEarliest,
                "floruitLatest": floruitLatest,
            }
        )

    return enriched


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


def ancestor_format(ancestor_data: str):
    ancestors = []
    if not ancestor_data:
        return []

    for uri in ancestor_data.split("|"):
        uri = uri.strip()
        if not uri:
            continue
        segments = uri.split("/")
        if len(segments) >= 7:
            place_name = segments[-2]
            place_type = segments[-3]

            ancestors.append({"uri": uri, "type": place_type, "label": place_name})
        else:
            ancestors.append(
                {
                    "uri": uri,
                    "type": "unknown",
                    "label": uri.split("/")[-1] if "/" in uri else uri,
                }
            )
    return ancestors


def parent_place_2(place_data: str, current_uri: str):
    places = []
    uri_list = []
    if not place_data:
        # Add to graph
        LOCATION_HIERARCHY_GRAPH[current_uri] = {
            "parents": [],
            "children": LOCATION_HIERARCHY_GRAPH.get(current_uri, {}).get(
                "children", []
            ),
        }
        return []

    for uri in place_data.split("|"):
        uri = uri.strip()
        segments = uri.split("/")
        place_name = segments[-2]
        place_type = segments[-3]
        # print(place_name, place_type)

        places.append({"uri": uri, "type": place_type, "label": place_name})
        uri_list.append(uri)

        # Now add to the graph?
        if uri not in LOCATION_HIERARCHY_GRAPH:
            LOCATION_HIERARCHY_GRAPH[uri] = {"parents": [], "children": []}
        if current_uri not in LOCATION_HIERARCHY_GRAPH[uri]["children"]:
            LOCATION_HIERARCHY_GRAPH[uri]["children"].append(current_uri)
    if current_uri not in LOCATION_HIERARCHY_GRAPH:
        LOCATION_HIERARCHY_GRAPH[current_uri] = {
            "parents": uri_list,
            "children": [],
        }
    else:
        LOCATION_HIERARCHY_GRAPH[current_uri]["parents"] = uri_list
    return places


def parent_place_extract(place_data: str):
    place_list = []
    place_uris = []
    if not place_data:
        return []
    # 1. Split by pipe:
    for uri in place_data.split("|"):
        uri = uri.strip()
        segments = uri.split("/")
        place_name = segments[-2]
        place_type = segments[-3]

        place_list.append({f"{place_type} - {place_name}": uri})
    return place_list


def extract_info(data):
    rows = data.get("results", {}).get("bindings", [])
    candidates = []
    for row in rows:
        # print(row)
        irishLabel = ""

        place = row.get("place").get("value")
        if not place:
            continue

        era = extract_uri_metadata(place)

        englishLabel = row.get("labelEn", {}).get("value")
        irishLabel = row.get("labelGa", {}).get("value")

        placeType = row.get("types", {}).get("value")
        types = extract_by_hash(placeType) if placeType else []

        parentPlaces = row.get("parentPlaces", {}).get("value")
        ancestorPlaces = row.get("ancestorPlaces", {}).get("value")  # extract here

        # Now build the edges
        construct_location_graph_edge(parentPlaces, place)
        hierarchy = ancestor_format(ancestorPlaces)

        # places = parent_place_2(placeHierarchy, place)
        # places = parent_place_extract(placeHierarchy)
        # Put place in the graph
        if place in LOCATION_HIERARCHY_GRAPH:
            LOCATION_HIERARCHY_GRAPH[place].update(
                {
                    "english": englishLabel,
                    "irish": irishLabel,
                    "era": era,
                    "types": types,
                    "all_ancestors": hierarchy,
                }
            )

        entity_dict = {
            "place": place,
            "era": era,
            "english": englishLabel,
            "irish": irishLabel,
            "types": types,
            "parentPlace": parentPlaces,
            "ancestorHierarchy": hierarchy,
            "all_ancestors": [a["uri"] for a in hierarchy],
        }
        candidates.append(entity_dict)
    return candidates


def to_entity_card_url(person_iri: str) -> str:
    if person_iri.startswith(KG_BASE):
        return ENTITY_CARD_BASE + person_iri[len(KG_BASE) :]
    return person_iri  # fallback if unexpected IRI format


def deduplicate_places(results: list) -> list:
    """
    Deduplicate place results by time-period/type/appellation-name.
    This matches the behavior of the Virtual Treasury website.
    """
    # Get the bindings
    bindings = results.get("results", {}).get("bindings", [])

    seen = {}
    unique = []

    for binding in bindings:
        # Get the URI
        place_uri = binding.get("place", {}).get("value", "")
        app_uri = binding.get("app", {}).get("value", "")

        place_parts = place_uri.split("/place/")[-1].split("/")
        app_parts = app_uri.split("/appellation/")[-1].split("/")

        if len(place_parts) >= 3 and len(app_parts) >= 1:
            time_period = place_parts[0]
            place_type = place_parts[1]
            app_name = app_parts[0]  # Use appellation name

            # Create unique key
            key = f"{time_period}/{place_type}/{app_name}"
        else:
            # Fallback to full URI if parsing fails
            key = place_uri

        if key not in seen:
            seen[key] = binding
            unique.append(binding)

    return unique


def query_person(entity_name: str, era: str):
    if len(entity_name) < 4:
        return []

    q_2 = VRTIQuery.bif_contains(entity_name, era)
    resp_2 = VirtualTreasurySPARQL.query(q_2)
    results = resp_2["results"].get("bindings")
    person_uris = [row["person"]["value"] for row in results]
    if not person_uris:
        return []
    q = VRTIQuery.expand_person_knowledge(person_uris)
    resp_3 = VirtualTreasurySPARQL.query(q)

    result = enrich_with_entity_cards(resp_3, era)

    return result


def query_location(entity_name: str, era: str):
    if entity_name and len(entity_name) < 4:
        q = VRTIQuery.location_query_no_wildcard(entity_name, era)
    else:
        q = VRTIQuery.fixed_place_bif(entity_name, era)  # Leave the era in for now
    # print(q)
    resp = VirtualTreasurySPARQL.query(q)
    enriched_resp = extract_info(resp)
    return enriched_resp


def create_batches(entities):
    person_batch = []
    location_batch = []
    for entity in entities:
        if entity["label"] == "PER":
            person_batch.append(entity)
        elif entity["label"] == "LOC":
            location_batch.append(entity)
        else:
            print("Not person or location")  # change this to a logger
    return person_batch, location_batch


def query_sparql(entities):
    ents = []
    for entity in entities:
        # 1. Extract the actual entity
        entity_name = entity.get("text")
        entity_label = entity.get("label")
        found_entities = []
        if entity_label == "PER":
            found_entities = query_person(entity_name, EARLY_MODERN_ERA)
        elif entity_label == "LOC":
            found_entities = query_location(entity_name, EARLY_MODERN_ERA)
        # if found_entities:
        entity_block = {
            "entity_meta_data": entity,
            "candidate_entities": found_entities,
        }
        ents.append(entity_block)
        # print(ents)
    return ents, LOCATION_HIERARCHY_GRAPH
