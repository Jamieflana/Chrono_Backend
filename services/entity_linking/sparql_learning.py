from typing import List
from services.entity_linking.sparql_querys import VRTIQuery
from services.sparql_client import VirtualTreasurySPARQL

# /home/jamie/Documents/FinalYear/Dissertation/Chrono/Backend/services/sparql_client.py
KG_BASE = "https://kg.virtualtreasury.ie/"
ENTITY_CARD_BASE = "https://vrti-graph.adaptcentre.ie/entity-card/"

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

henry_data = [
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
        "text": "Donegal",
        "label": "LOC",
        "score": 0.9997882843017578,
        "start": 51,
        "end": 58,
    }
]


def enrich_with_entity_cards(sparql_json: dict) -> list[dict]:
    rows = sparql_json.get("results", {}).get("bindings", [])
    enriched = []
    for row in rows:
        person_iri = row["person"]["value"]
        label = row.get("label", {}).get("value")
        idNodes = row.get("idNodes").get("value")
        idLabels = row.get("idLabels").get("value")
        labels = split_by_pipe(idLabels)
        identifierCount = row.get("identifierCount").get("value")
        genders_raw = row.get("genders").get("value", "")  # extract at the end of the #
        genders = extract_by_hash(genders_raw)
        eras_raw = row.get("eras").get("value")  # extract at the end of the #
        eras = extract_by_hash(eras_raw)
        residences = row.get("residences").get("value")
        raw_residences_labels = row.get("residenceLabels").get("value")
        residencesLabels = split_by_pipe(raw_residences_labels)
        documentSources = row.get("documentSources").get("value")
        events = row.get("events").get("value")
        event_appearences = row.get("eventCount").get("value")
        if not label:
            # fallback: derive from person IRI
            person_iri = row["person"]["value"]
            label = person_iri.rstrip("/").split("/")[-2]  # e.g. "Jones_Henry_c17"

        enriched.append(
            {
                "person": person_iri,
                "label": label,
                "entityCard": to_entity_card_url(person_iri),
                "idNodes": idNodes,
                "idLabels": labels,
                "identifierCount": identifierCount,
                "genders": genders,
                "eras": eras,
                "residences": residences,
                "residencesLabels": residencesLabels,
                "documentSources": documentSources,
                "events": events,
                "eventCount": event_appearences,
            }
        )

    return enriched


def split_by_pipe(entity_row: str):
    label_list = []
    labels = entity_row.split("|")
    for label in labels:
        label = label.strip()
        # print("Label is:", label)
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
    segments = uri.split("/")
    era = segments[4]
    return era


def parent_place_extract(place_data: str):
    place_list = []
    if place_data == "":
        return
    # 1. Split by pipe:
    for uri in place_data.split("|"):
        second_last = uri.split("/")
        place_list.append({second_last[-2]: uri})
    return place_list


def extract_info(data):
    rows = data.get("results", {}).get("bindings", [])
    candidates = []
    for row in rows:
        irishLabel = ""
        place = row.get("place").get("value")
        era = extract_uri_metadata(place)
        englishLabel = row.get("labelEn").get("value")
        isIrishLabel = row.get("labelGa", "No Irish")
        if isIrishLabel != "No Irish":
            irishLabel = isIrishLabel.get("value")
        placeType = row.get("types", "No Type link").get("value")
        types = extract_by_hash(placeType)
        parentPlace = row.get("parentPlaces").get("value")  # extract here
        places = parent_place_extract(parentPlace)
        entity_dict = {
            "place": place,
            "era": era,
            "english": englishLabel,
            "irish": irishLabel,
            "types": types,
            "parentPlace": places,
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


def query_person(entity_name: str):
    # q = VRTIQuery.person_query(entity_name)
    q_2 = VRTIQuery.person_query_2(entity_name)
    # q_1 = VRTIQuery.person_query(entity_name)
    resp_2 = VirtualTreasurySPARQL.query(q_2)
    # resp_1 = VirtualTreasurySPARQL.query(q_1)
    # print(resp_2)
    result = enrich_with_entity_cards(resp_2)
    # print(result)

    # return replies
    return result


def query_location(entity_name: str):
    # q = VRTIQuery.place_query(entity_name) OLD
    q = VRTIQuery.place_query_rich(entity_name)  # New
    resp = VirtualTreasurySPARQL.query(q)
    # unique_resp = deduplicate_places(resp)

    enriched_resp = extract_info(resp)
    return enriched_resp


def query_sparql(entities):
    ents = []
    for entity in entities:
        # 1. Extract the actual entity
        entity_name = entity.get("text")
        entity_label = entity.get("label")
        entity_score = entity.get("score")
        entity_start = entity.get("start")
        entity_end = entity.get("end")

        if entity_label == "PER":

            found_entities = query_person(entity_name)
        elif entity_label == "LOC":
            found_entities = query_location(entity_name)
        if found_entities:
            entity_block = {
                "entity_meta_data": entity,
                "candidate_entities": found_entities,
            }
            ents.append(entity_block)
    print(ents)
    return ents


# print("Starting")
query_sparql(raw_data)
# query_sparql(Donegal_Data)
