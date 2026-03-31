import re


class VRTIQuery:

    @staticmethod
    def person_query_profile_early_modern(entity_name: str) -> str:
        if not entity_name or not entity_name.strip():
            raise ValueError("entity_name is empty")

        clean = re.sub(r"[,]+", " ", entity_name).strip()
        parts = [p for p in clean.split() if p]
        if not parts:
            raise ValueError("entity_name is empty")
        safe_last_name = parts[-1].lower().replace('"', '\\"')

        query = f"""
PREFIX crm: <http://erlangen-crm.org/current/>
PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX vrtivocab: <https://www.w3id.org/virtual-treasury/vocabulary#>
SELECT DISTINCT ?person
       ?fullName
       ?gender
       ?era
       ?floruitLower
       ?floruitUpper
       ?wikidata
	     ?residences
       ?dib
       (GROUP_CONCAT(DISTINCT ?birthPlace; separator=", ") AS ?birthPlaces)
       (GROUP_CONCAT(DISTINCT ?deathPlace; separator=", ") AS ?deathPlaces)
FROM <https://kg.virtualtreasury.ie/graph/DIB-v1>
FROM <https://kg.virtualtreasury.ie/graph/VOICES-freewomen-v1>
FROM <https://kg.virtualtreasury.ie/graph/VOICES-Prob11-v1>
FROM <https://kg.virtualtreasury.ie/graph/VOICES-wills-v1>
FROM <https://kg.virtualtreasury.ie/graph/VOICES-1641-v1>
FROM NAMED <https://kg.virtualtreasury.ie/graph/present-day-places-v1>
WHERE {{
    ?person a crm:E21_Person ;
            crm:P2_has_type ?gender ;
            crm:P1_is_identified_by ?nameResource ;
            vrti:VRTI_ERA|vrti:has_era_type vrtivocab:Early-Modern-1500-1749 .
    ?nameResource crm:P2_has_type vrti:Name ;
                  rdfs:label ?fullName .
    FILTER(CONTAINS(LCASE(?fullName), "{safe_last_name}"))
    OPTIONAL {{ ?person vrti:VRTI_ERA ?era }}
    OPTIONAL {{ ?person owl:sameAs ?wikidata }}
    OPTIONAL {{ ?person crm:P71i_is_listed_in ?dib }}
    OPTIONAL {{ ?person crm:P74_has_current_or_former_residence ?residences }}
    OPTIONAL {{
        ?birthResource a crm:E67_Birth ;
                       crm:P98_brought_into_life ?person .
        OPTIONAL {{
            ?birthResource crm:P7_took_place_at ?birthPlaceResource .
            GRAPH <https://kg.virtualtreasury.ie/graph/present-day-places-v1> {{
                ?birthPlaceResource rdfs:label ?birthPlace .
                FILTER(LANG(?birthPlace) = "en")
            }}
        }}
    }}
    OPTIONAL {{
        ?deathResource a crm:E69_Death ;
                       crm:P93_took_out_of_existence ?person .
        OPTIONAL {{
            ?deathResource crm:P7_took_place_at ?deathPlaceResource .
            GRAPH <https://kg.virtualtreasury.ie/graph/present-day-places-v1> {{
                ?deathPlaceResource rdfs:label ?deathPlace .
                FILTER(LANG(?deathPlace) = "en")
            }}
        }}
    }}
    OPTIONAL {{
        ?floruitResource crm:P2_has_type vrti:Floruit ;
                         crm:P4_has_time-span ?floruitDateResource ;
                         (crm:P12_occurred_in_the_presence_of | crm:P11_had_participant) ?person .
        ?floruitDateResource crm:P81a_end_of_the_begin ?floruitLower ;
                              crm:P82b_end_of_the_end ?floruitUpper .
    }}
}}
LIMIT 30
"""
        return query

    @staticmethod
    def final_place_query(entity_name: str) -> str:
        if not entity_name or not entity_name.strip():
            raise ValueError("entity_name is empty")

        safe_name = entity_name.strip().lower().replace('"', '\\"')

        query = f"""
PREFIX crm: <http://erlangen-crm.org/current/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX vrti: <https://ont.virtualtreasury.ie/ontology#>
PREFIX ogcgs: <http://www.opengis.net/ont/geosparql#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT
    ?place
    (SAMPLE(?logainmUri) AS ?logainmUri)
    (SAMPLE(?labelEn) AS ?labelEn)
    (SAMPLE(?labelGa) AS ?labelGa)
    (GROUP_CONCAT(DISTINCT STR(?type); SEPARATOR=" | ") AS ?types)
    (GROUP_CONCAT(DISTINCT STR(?parent); SEPARATOR=" | ") AS ?parentPlaces)
    (GROUP_CONCAT(DISTINCT ?parentLabel; SEPARATOR=" | ") AS ?parentLabels)
    (GROUP_CONCAT(DISTINCT STR(?sameAs); SEPARATOR=" | ") AS ?sameAsLinks)
    (GROUP_CONCAT(DISTINCT STR(?listedIn); SEPARATOR=" | ") AS ?externalResources)
    (SAMPLE(?vrtiId) AS ?vrtiIdentifier)
    (GROUP_CONCAT(DISTINCT STR(?approximatedBy); SEPARATOR=" | ") AS ?historicalApproximations)
FROM <https://kg.virtualtreasury.ie/graph/present-day-places-v1>
WHERE {{
    ?place a crm:E53_Place ;
           rdfs:label ?name .

    FILTER(langMatches(lang(?name), "en"))
    FILTER(CONTAINS(LCASE(?name), "{safe_name}"))

    OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
    OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}

    OPTIONAL {{ ?place crm:P2_has_type ?type }}

    OPTIONAL {{ ?place owl:sameAs ?sameAs }}
    OPTIONAL {{ ?place crm:P71i_is_listed_in ?listedIn }}

    OPTIONAL {{ ?place vrti:VrtiIdentifier ?vrtiId }}

    OPTIONAL {{
      ?place owl:sameAs ?logainmUri .
      FILTER(CONTAINS(STR(?logainmUri), "data.logainm.ie"))
    }}

    OPTIONAL {{
      ?approximatedBy crm:P189_approximates ?place .
    }}

    OPTIONAL {{
        ?place crm:P89_falls_within ?parent .
        OPTIONAL {{ ?parent rdfs:label ?parentLabel FILTER(lang(?parentLabel) = "en") }}
    }}
}}
GROUP BY ?place
LIMIT 1000
"""
        return query
