import re
from typing import Set


class VRTIQuery:

    @staticmethod
    def person_query(entity_name: str) -> str:
        clean = re.sub(r"[,]+", " ", entity_name).strip()
        parts = [p for p in clean.split() if p]

        if not parts:
            raise ValueError("entity_name is empty")

        # Basic heuristic:
        # - surname = last token
        # - forenames = everything before surname
        surname = parts[-1]
        forenames = parts[:-1]

        # Build a small set of exact candidate strings the KG might use
        candidates = set()

        if forenames:
            # Surname_First (e.g., Jones_Henry)
            candidates.add(f"{surname}_{forenames[0]}")
            # Surname_AllForenames (e.g., Jones_Henry_MacNaughton)
            candidates.add(f"{surname}_" + "_".join(forenames))
        else:
            # single token entity, keep as-is
            candidates.add(surname)

        # Also include the original token order as a defensive option
        # (sometimes labels/ids are stored in that order)
        candidates.add("_".join(parts))

        # Build VALUES blocks for exact IRIs (both spellings)
        normalised_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalised-appellation-surname-forename/{c}>"
            for c in candidates
        )
        normalized_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalized-appellation-surname-forename/{c}>"
            for c in candidates
        )

        # Exact label matches to try (no substring scanning)
        label_literals = "\n".join(f'"{c}"' for c in candidates)

        query = f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?person ?label
        WHERE {{
        ?person rdf:type cidoc:E21_Person .
        OPTIONAL {{ ?person rdfs:label ?label }}

        {{
            # Path 1: exact label match against a small candidate set
            VALUES ?labelWanted {{
            {label_literals}
            }}
            FILTER(BOUND(?label) && STR(?label) = ?labelWanted)
        }}
        UNION
        {{
            # Path 2: exact match against "normalised" surname-forename identifiers
            VALUES ?nameId {{
            {normalised_ids}
            }}
            ?person cidoc:P1_is_identified_by ?nameId .
        }}
        UNION
        {{
            # Path 3: exact match against "normalized" surname-forename identifiers
            VALUES ?nameId {{
            {normalized_ids}
            }}
            ?person cidoc:P1_is_identified_by ?nameId .
        }}
        }}
        LIMIT 50
        """
        return query

    @staticmethod
    def place_query(entity_name: str) -> str:
        """
        Generate SPARQL query for place entities.
        Uses CONTAINS for flexible matching of place names.
        """
        if not entity_name or not entity_name.strip():
            raise ValueError("entity_name is empty")

        # Clean the entity name
        clean_name = entity_name.strip()

        query = f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        
        SELECT DISTINCT ?place ?app
        WHERE {{
          ?place a cidoc:E53_Place ;
                 cidoc:P1_is_identified_by ?app .
          
          # Match place name in both place and appellation URIs
          FILTER(CONTAINS(STR(?place), "{clean_name}"))
          FILTER(CONTAINS(STR(?app), "{clean_name}"))
          
          # Only use kg.virtualtreasury.ie domain
          FILTER(CONTAINS(STR(?place), "kg.virtualtreasury.ie"))
        }}
        LIMIT 100
        """
        return query

    @staticmethod
    def place_query_rich(entity_name: str):
        if not entity_name:
            raise ValueError("Entity name is empyt")

        clean_name = entity_name.strip()  # remove whitespace

        query = f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?place ?labelEn ?labelGa 
              (GROUP_CONCAT(DISTINCT ?type; separator=" | ") as ?types)
              (GROUP_CONCAT(DISTINCT ?parentPlace; separator=" | ") as ?parentPlaces)
        WHERE {{
          ?place a cidoc:E53_Place.
          FILTER(CONTAINS(STR(?place), "kg.virtualtreasury.ie"))
          FILTER(CONTAINS(STR(?place), "{clean_name}"))
          
          OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
          OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
          OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
          OPTIONAL {{ ?place cidoc:P89_falls_within ?parentPlace }}
        }}
        GROUP BY ?place ?labelEn ?labelGa
        LIMIT 100
        """
        return query

    @staticmethod
    def deduplicate_places(results: list) -> list:
        """
        Deduplicate place results by time-period/type/appellation-name.
        This matches the behavior of the Virtual Treasury website.
        """
        seen = {}
        unique = []

        for result in results:
            place_uri = str(result.get("place", ""))
            app_uri = str(result.get("app", ""))

            # Extract time-period/type/name from place URI
            # e.g., "present-day/townland/Corkeeran"
            place_parts = place_uri.split("/place/")[-1].split("/")

            # Extract name from appellation URI (more reliable for grouping)
            app_parts = app_uri.split("/appellation/")[-1].split("/")

            if len(place_parts) >= 3 and len(app_parts) >= 1:
                time_period = place_parts[0]
                place_type = place_parts[1]
                app_name = app_parts[0]  # Use appellation name

                key = f"{time_period}/{place_type}/{app_name}"
            else:
                # Fallback to full URI if parsing fails
                key = place_uri

            # Keep first occurrence only
            if key not in seen:
                seen[key] = result
                unique.append(result)

        return unique

    @staticmethod
    def person_query_2(entity_name: str) -> str:
        clean = re.sub(r"[,]+", " ", entity_name).strip()
        parts = [p for p in clean.split() if p]

        if not parts:
            raise ValueError("entity_name is empty")

        # Basic heuristic:
        # - surname = last token
        # - forenames = everything before surname
        surname = parts[-1]
        forenames = parts[:-1]

        # Build a small set of exact candidate strings the KG might use
        candidates = set()

        if forenames:
            # Surname_First (e.g., Jones_Henry)
            candidates.add(f"{surname}_{forenames[0]}")
            # Surname_AllForenames (e.g., Jones_Henry_MacNaughton)
            candidates.add(f"{surname}_" + "_".join(forenames))
        else:
            # single token entity, keep as-is
            candidates.add(surname)

        # Also include the original token order as a defensive option
        candidates.add("_".join(parts))

        # Build VALUES blocks for exact IRIs (both spellings)
        normalised_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalised-appellation-surname-forename/{c}>"
            for c in candidates
        )
        normalized_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalized-appellation-surname-forename/{c}>"
            for c in candidates
        )

        # Exact label matches to try (no substring scanning)
        label_literals = "\n".join(f'"{c}"' for c in candidates)

        # Enriched query:
        # - Outer query expands context and aggregates to one row per ?person
        query = f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX dct:   <http://purl.org/dc/terms/>
        PREFIX prov:  <http://www.w3.org/ns/prov#>
        PREFIX vrt:   <https://www.w3id.org/virtual-treasury/ontology#>

        SELECT
          ?person
          (SAMPLE(?label) AS ?label)

          (GROUP_CONCAT(DISTINCT STR(?idNode); SEPARATOR=" | ") AS ?idNodes)
          (GROUP_CONCAT(DISTINCT ?idLabel; SEPARATOR=" | ") AS ?idLabels)
          (COUNT(DISTINCT ?idNode) AS ?identifierCount)

          (GROUP_CONCAT(DISTINCT STR(?gender); SEPARATOR=" | ") AS ?genders)

          (GROUP_CONCAT(DISTINCT STR(?era); SEPARATOR=" | ") AS ?eras)

          (GROUP_CONCAT(DISTINCT STR(?residence); SEPARATOR=" | ") AS ?residences)
          (GROUP_CONCAT(DISTINCT ?residenceLabel; SEPARATOR=" | ") AS ?residenceLabels)

          (GROUP_CONCAT(DISTINCT STR(?docSource); SEPARATOR=" | ") AS ?documentSources)
          (COUNT(DISTINCT ?docSource) AS ?documentSourceCount)

          (GROUP_CONCAT(DISTINCT STR(?event); SEPARATOR=" | ") AS ?events)
          (COUNT(DISTINCT ?event) AS ?eventCount)

          (GROUP_CONCAT(DISTINCT ?matchKind; SEPARATOR=" | ") AS ?matchKinds)

        WHERE {{

          
          
          
          {{
            SELECT DISTINCT ?person ?label ?matchKind
            WHERE {{
              ?person rdf:type cidoc:E21_Person .
              OPTIONAL {{ ?person rdfs:label ?label }}

              {{
                VALUES ?labelWanted {{
                  {label_literals}
                }}
                FILTER(BOUND(?label) && STR(?label) = ?labelWanted)
                BIND("label" AS ?matchKind)
              }}
              UNION
              {{
                VALUES ?nameId {{
                  {normalised_ids}
                }}
                ?person cidoc:P1_is_identified_by ?nameId .
                BIND("normalised_id" AS ?matchKind)
              }}
              UNION
              {{
                VALUES ?nameId {{
                  {normalized_ids}
                }}
                ?person cidoc:P1_is_identified_by ?nameId .
                BIND("normalized_id" AS ?matchKind)
              }}
            }}
            LIMIT 50
          }}

          # ----------------------------
          # Enrichment
          # ----------------------------

          OPTIONAL {{
            ?person cidoc:P1_is_identified_by ?idNode .
            OPTIONAL {{ ?idNode rdfs:label ?idLabel }}
          }}

          OPTIONAL {{
            ?person cidoc:P2_has_type ?gender .
          }}

          OPTIONAL {{
            ?person vrt:has_era_type ?era .
          }}
          OPTIONAL {{
            ?person vrt:VRTI_ERA ?era .
          }}

          OPTIONAL {{
            ?person cidoc:P74_has_current_or_former_residence ?residence .
            OPTIONAL {{ ?residence rdfs:label ?residenceLabel }}
          }}

          OPTIONAL {{
            ?docSource cidoc:P70_documents ?person .
          }}

          OPTIONAL {{
            ?event cidoc:P11_had_participant ?person .
          }}
        }}
        GROUP BY ?person
        ORDER BY DESC(?documentSourceCount) DESC(?eventCount) DESC(?identifierCount)
        LIMIT 50
        """
        return query

    @staticmethod
    def build_fast_person_rank_query(entity_name: str, limit: int = 50) -> str:
        """

        Parameters
        ----------
        entity_name : str
            Raw entity text from NER (e.g. "Henry Jones")
        limit : int
            Max number of candidate persons to return/enrich.

        Returns
        -------
        str
            SPARQL query string.
        """
        clean = re.sub(r"[,]+", " ", entity_name).strip()
        parts = [p for p in clean.split() if p]
        if not parts:
            raise ValueError("entity_name is empty")

        surname = parts[-1]
        forenames = parts[:-1]

        candidates: Set[str] = set()
        if forenames:
            candidates.add(f"{surname}_{forenames[0]}")
            candidates.add(f"{surname}_" + "_".join(forenames))
        else:
            candidates.add(surname)

        candidates.add("_".join(parts))

        # VALUES blocks
        label_literals = " ".join(f'"{c}"' for c in candidates)

        normalised_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalised-appellation-surname-forename/{c}>"
            for c in candidates
        )
        normalized_ids = "\n".join(
            f"<https://kg.virtualtreasury.ie/normalized-appellation-surname-forename/{c}>"
            for c in candidates
        )

        return f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX vrt:   <https://www.w3id.org/virtual-treasury/ontology#>

        SELECT
        ?person
        (SAMPLE(?label) AS ?label)

        (COUNT(DISTINCT ?idNode) AS ?identifierCount)
        (COUNT(DISTINCT ?docSource) AS ?documentSourceCount)
        (COUNT(DISTINCT ?event) AS ?eventCount)

        (GROUP_CONCAT(DISTINCT ?residenceLabel; SEPARATOR=" | ") AS ?residenceLabels)

        (GROUP_CONCAT(DISTINCT REPLACE(STR(?gender), "^.*[#/]", ""); SEPARATOR=" | ") AS ?genderLocal)
        (GROUP_CONCAT(DISTINCT REPLACE(STR(?era), "^.*[#/]", ""); SEPARATOR=" | ") AS ?eraLocal)

        (GROUP_CONCAT(DISTINCT ?matchKind; SEPARATOR=" | ") AS ?matchKinds)

        WHERE {{
        {{
            SELECT DISTINCT ?person ?label ?matchKind
            WHERE {{
            ?person rdf:type cidoc:E21_Person .
            OPTIONAL {{ ?person rdfs:label ?label }}

            {{
                VALUES ?labelWanted {{ {label_literals} }}
                FILTER(BOUND(?label) && STR(?label) = ?labelWanted)
                BIND("label" AS ?matchKind)
            }}
            UNION {{
                VALUES ?nameId {{
        {normalised_ids}
                }}
                ?person cidoc:P1_is_identified_by ?nameId .
                BIND("normalised_id" AS ?matchKind)
            }}
            UNION {{
                VALUES ?nameId {{
        {normalized_ids}
                }}
                ?person cidoc:P1_is_identified_by ?nameId .
                BIND("normalized_id" AS ?matchKind)
            }}
            }}
            LIMIT {int(limit)}
        }}

        OPTIONAL {{ ?person cidoc:P1_is_identified_by ?idNode . }}
        OPTIONAL {{ ?person cidoc:P2_has_type ?gender . }}

        OPTIONAL {{ ?person vrt:has_era_type ?era . }}
        OPTIONAL {{ ?person vrt:VRTI_ERA ?era . }}

        OPTIONAL {{
            ?person cidoc:P74_has_current_or_former_residence ?residence .
            OPTIONAL {{ ?residence rdfs:label ?residenceLabel }}
        }}

        OPTIONAL {{ ?docSource cidoc:P70_documents ?person . }}
        OPTIONAL {{ ?event cidoc:P11_had_participant ?person . }}
        }}
        GROUP BY ?person
        ORDER BY DESC(?documentSourceCount) DESC(?eventCount) DESC(?identifierCount)
        LIMIT {int(limit)}
        """.strip()
