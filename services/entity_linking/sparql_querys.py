import re
from typing import Optional, Set
import unicodedata


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

    # Old query
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
    def place_present_day_by_label(entity_name: str) -> str:
        safe_name = entity_name.lower().replace('"', '\\"')
        query = (
            query
        ) = f"""
        PREFIX crm:  <http://erlangen-crm.org/current/>
        PREFIX geo:  <http://www.opengis.net/ont/geosparql#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT
            ?place
            ?placeType
            ?name
        FROM <https://kg.virtualtreasury.ie/graph/present-day-places-v1>
        WHERE {{
            ?place a crm:E53_Place ;
                  crm:P2_has_type ?placeType ;
                  rdfs:label ?name .
            FILTER (langMatches(lang(?name), "en") && contains(lcase(str(?name)), "{safe_name}"))
        }}
        LIMIT 10"""
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
    def person_query_three(entity_name: str):
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
            # single token entity, keep as is
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
            ?idNodes ?idLabels ?identifierCount
            ?genders
            ?eras
            ?residences ?residenceLabels
            ?documentSources ?documentSourceCount
            ?events ?eventCount
            ?floruitEarliest ?floruitLatest
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

          OPTIONAL {{
            SELECT ?person
                (GROUP_CONCAT(DISTINCT STR(?idNode); SEPARATOR=" | ") AS ?idNodes)
                (GROUP_CONCAT(DISTINCT ?idLabel; SEPARATOR=" | ") AS ?idLabels)
                (COUNT(DISTINCT ?idNode) AS ?identifierCount)
        WHERE {{
            ?person cidoc:P1_is_identified_by ?idNode .
            OPTIONAL {{ ?idNode rdfs:label ?idLabel }}
            }}
            GROUP BY ?person
          }}

           OPTIONAL {{
            SELECT ?person
            (GROUP_CONCAT(DISTINCT STR(?gender); SEPARATOR=" | ") AS ?genders)
            WHERE {{
            ?person cidoc:P2_has_type ?gender .
            }}
            GROUP BY ?person
        }}

          OPTIONAL {{
    SELECT ?person
      (GROUP_CONCAT(DISTINCT STR(?era); SEPARATOR=" | ") AS ?eras)
    WHERE {{
      {{ ?person vrt:has_era_type ?era }}
      UNION
      {{ ?person vrt:VRTI_ERA ?era }}
    }}
    GROUP BY ?person
  }}
         

          OPTIONAL {{
    SELECT ?person
      (GROUP_CONCAT(DISTINCT STR(?residence); SEPARATOR=" | ") AS ?residences)
      (GROUP_CONCAT(DISTINCT ?residenceLabel; SEPARATOR=" | ") AS ?residenceLabels)
    WHERE {{
      ?person cidoc:P74_has_current_or_former_residence ?residence .
      OPTIONAL {{ ?residence rdfs:label ?residenceLabel }}
    }}
    GROUP BY ?person
  }}

          OPTIONAL {{
    SELECT ?person
      (GROUP_CONCAT(DISTINCT STR(?docSource); SEPARATOR=" | ") AS ?documentSources)
      (COUNT(DISTINCT ?docSource) AS ?documentSourceCount)
    WHERE {{
      ?docSource cidoc:P70_documents ?person .
    }}
    GROUP BY ?person
  }}

          OPTIONAL {{
            SELECT ?person
      (GROUP_CONCAT(DISTINCT STR(?event); SEPARATOR=" | ") AS ?events)
      (COUNT(DISTINCT ?event) AS ?eventCount)
        WHERE {{
      ?event cidoc:P11_had_participant ?person .
        }}
        GROUP BY ?person
        }}
        OPTIONAL {{
    SELECT ?person
      (MIN(?beginDate) AS ?floruitEarliest)
      (MAX(?endDate) AS ?floruitLatest)
    WHERE {{
      ?floruitEvent cidoc:P11_had_participant ?person .
      ?floruitEvent cidoc:P2_has_type vrt:Floruit .
      ?floruitEvent cidoc:P4_has_time-span ?timeSpan .
      
      OPTIONAL {{ ?timeSpan cidoc:P82a_begin_of_the_begin ?beginDate }}
      OPTIONAL {{ ?timeSpan cidoc:P82b_end_of_the_end ?endDate }}
    }}
    GROUP BY ?person
  }}
        }}
        GROUP BY
        ?person ?idNodes ?idLabels ?identifierCount ?genders ?eras
        ?residences ?residenceLabels ?documentSources ?documentSourceCount ?events ?eventCount
        ?floruitEarliest ?floruitLatest
        ORDER BY DESC(?documentSourceCount) DESC(?eventCount) DESC(?identifierCount)
        LIMIT 50
        """
        return query

    def forgiving_query(entity_name: str, ERA: str):
        parts = entity_name.strip().split()
        surname = parts[-1]

        query = f"""
          PREFIX cidoc: <http://erlangen-crm.org/current/>
          PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
          PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>

          SELECT DISTINCT ?person ?label
          WHERE {{
                ?person rdf:type cidoc:E21_Person .
                ?person rdfs:label ?label .
                ?place vrti:VRTI_ERA <{ERA}> .
                # Broad surname filter
                FILTER(CONTAINS(LCASE(?label), "{surname.lower()}"))
            }}
                LIMIT 100  # Get more candidates for filtering
        """
        return query

    @staticmethod
    def ancestor_place_query(entity_name: str):
        if not entity_name:
            raise ValueError("Entity name is empty")

        clean_name = entity_name.strip()  # remove whitespace

        query = f"""
            PREFIX cidoc: <http://erlangen-crm.org/current/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?place 
                (SAMPLE(?labelEn) as ?labelEn)
                (SAMPLE(?labelGa) as ?labelGa)
                (GROUP_CONCAT(DISTINCT ?type; separator=" | ") as ?types)
                (SAMPLE(?ancestors) as ?ancestorPlaces)
            WHERE {{
              ?place a cidoc:E53_Place.
              FILTER(CONTAINS(STR(?place), "kg.virtualtreasury.ie"))
              FILTER(CONTAINS(STR(?place), "{entity_name}"))
              
              OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
              OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
              OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
              
              OPTIONAL {{
                SELECT ?place (GROUP_CONCAT(DISTINCT ?anc; separator=" | ") as ?ancestors)
                WHERE {{
                  ?place cidoc:P89_falls_within+ ?anc
                }}
                GROUP BY ?place
              }}
            }}
            GROUP BY ?place
            LIMIT 100
        """
        return query

    # Need to add two checks for entries that are missing some stuff, then all data is nice and complete
    def fixed_place_query(entity_name: str, ERA: str):
        if not entity_name:
            raise ValueError("Entity name is empty")

        clean_name = entity_name.strip()  # remove whitespace

        query = f"""
          PREFIX cidoc: <http://erlangen-crm.org/current/>
          PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
          PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
          PREFIX thes: <https://kg.virtualtreasury.ie/thesauri#>

          SELECT ?place
            (SAMPLE(?labelEn) AS ?labelEn)
            (SAMPLE(?labelGa) AS ?labelGa)
            (GROUP_CONCAT(DISTINCT STR(?type); SEPARATOR=" | ") AS ?types)
            (GROUP_CONCAT(DISTINCT STR(?parent); SEPARATOR=" | ") AS ?parentPlaces)
            (SAMPLE(?ancestorPlaces) AS ?ancestorPlaces)
          WHERE {{
            ?place rdf:type cidoc:E53_Place .
            ?place vrti:VRTI_ERA thes:{era} .
            ?place cidoc:P1_is_identified_by ?appellation .
            ?appellation rdfs:label ?appellationName .
            ?appellationName bif:contains "'{entity_name}*'" .
            
            OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
            OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
            OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
            OPTIONAL {{ ?place cidoc:P89_falls_within ?parent }}
            
            OPTIONAL {{
              {{
                SELECT ?place (GROUP_CONCAT(DISTINCT STR(?anc); SEPARATOR=" | ") AS ?ancestorPlaces)
                WHERE {{
                  ?place cidoc:P89_falls_within+ ?anc
                }}
                GROUP BY ?place
              }}
            }}
          }}
          GROUP BY ?place
          LIMIT 100
        """
        return query

    def fixed_place_bif(entity_name: str, era: Optional[str] = None) -> str:
        """
        Build SPARQL query for place entity linking using bif:contains on appellations.

        Args:
            entity_name: The place name to search for (e.g., "Donegal", "Dublin")
            era: Optional era identifier (e.g., "Early-Modern-1500-1749")

        Returns:
            SPARQL query string
        """
        era_clause = f"?place vrti:VRTI_ERA thes:{era} ." if era else ""
        query = f"""
          PREFIX cidoc: <http://erlangen-crm.org/current/>
          PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
          PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
          PREFIX thes: <https://kg.virtualtreasury.ie/thesauri#>

          SELECT ?place
            (SAMPLE(?labelEn) AS ?labelEn)
            (SAMPLE(?labelGa) AS ?labelGa)
            (GROUP_CONCAT(DISTINCT STR(?type); SEPARATOR=" | ") AS ?types)
            (GROUP_CONCAT(DISTINCT STR(?parent); SEPARATOR=" | ") AS ?parentPlaces)
            (SAMPLE(?ancestorPlaces) AS ?ancestorPlaces)
          WHERE {{
            ?place rdf:type cidoc:E53_Place .
            {era_clause}
            ?place cidoc:P1_is_identified_by ?appellation .
            ?appellation rdfs:label ?appellationName .
            ?appellationName bif:contains "'{entity_name}*'" .
            
            OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
            OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
            OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
            OPTIONAL {{ ?place cidoc:P89_falls_within ?parent }}
            
            OPTIONAL {{
              {{
                SELECT ?place (GROUP_CONCAT(DISTINCT STR(?anc); SEPARATOR=" | ") AS ?ancestorPlaces)
                WHERE {{
                  ?place cidoc:P89_falls_within+ ?anc
                }}
                GROUP BY ?place
              }}
            }}
          }}
          GROUP BY ?place
          LIMIT 100
      """
        return query

    def location_query_no_wildcard(entity_name: str, era: Optional[str] = None):
        era_clause = f"?place vrti:VRTI_ERA thes:{era} ." if era else ""
        query = f"""
          PREFIX cidoc: <http://erlangen-crm.org/current/>
          PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
          PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
          PREFIX thes: <https://kg.virtualtreasury.ie/thesauri#>

          SELECT ?place
            (SAMPLE(?labelEn) AS ?labelEn)
            (SAMPLE(?labelGa) AS ?labelGa)
            (GROUP_CONCAT(DISTINCT STR(?type); SEPARATOR=" | ") AS ?types)
            (GROUP_CONCAT(DISTINCT STR(?parent); SEPARATOR=" | ") AS ?parentPlaces)
            (SAMPLE(?ancestorPlaces) AS ?ancestorPlaces)
          WHERE {{
            ?place rdf:type cidoc:E53_Place .
            {era_clause}
            ?place cidoc:P1_is_identified_by ?appellation .
            ?appellation rdfs:label ?appellationName .
            ?appellationName bif:contains "'{entity_name}'" .
            
            OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
            OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
            OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
            OPTIONAL {{ ?place cidoc:P89_falls_within ?parent }}
            
            OPTIONAL {{
              {{
                SELECT ?place (GROUP_CONCAT(DISTINCT STR(?anc); SEPARATOR=" | ") AS ?ancestorPlaces)
                WHERE {{
                  ?place cidoc:P89_falls_within+ ?anc
                }}
                GROUP BY ?place
              }}
            }}
          }}
          GROUP BY ?place
          LIMIT 100
      """
        return query

    def bif_contains(entity_name: str, era: str):

        parts = entity_name.strip().split()
        surname = parts[-1]
        escaped_name = escape_bif_contains(surname)
        query = ""
        print(surname)
        if len(surname) < 4:
            query = f"""
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
          PREFIX voc: <https://www.w3id.org/virtual-treasury/vocabulary#>

          SELECT DISTINCT ?person
          WHERE {{
            ?person a <http://erlangen-crm.org/current/E21_Person> .
            ?person vrti:VRTI_ERA|vrti:has_era_type voc:{era} .
            ?person <http://erlangen-crm.org/current/P1_is_identified_by> ?appellation .
            ?appellation <http://www.w3.org/2000/01/rdf-schema#label> ?name .
            ?name bif:contains "'{escaped_name}'" .
          }}
          """
        else:
            query = f"""
          PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
          PREFIX voc: <https://www.w3id.org/virtual-treasury/vocabulary#>

          SELECT DISTINCT ?person
          WHERE {{
            ?person a <http://erlangen-crm.org/current/E21_Person> .
            ?person vrti:VRTI_ERA|vrti:has_era_type voc:{era} .
            ?person <http://erlangen-crm.org/current/P1_is_identified_by> ?appellation .
            ?appellation <http://www.w3.org/2000/01/rdf-schema#label> ?name .
            ?name bif:contains "'{escaped_name}*'" .
          }}
          LIMIT 30
          """
        return query

    def expand_person_knowledge(uri_list: list):
        if not uri_list:
            return None

        values_clause = "\n".join(f"<{uri}>" for uri in uri_list)

        query = f"""
  PREFIX cidoc: <http://erlangen-crm.org/current/>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

  SELECT
      ?person
      (SAMPLE(?personLabel) AS ?personLabel)
      ?dibResource
      ?residences
      ?residenceLabels
      (MIN(?floruitBegin) AS ?floruitEarliest)
      (MAX(?floruitEnd) AS ?floruitLatest)
  WHERE {{
    VALUES ?person {{
      {values_clause}
    }}

    OPTIONAL {{ ?person rdfs:label ?personLabel }}

    OPTIONAL {{
      SELECT ?person (SAMPLE(STR(?dib)) AS ?dibResource)
      WHERE {{
        VALUES ?person {{
          {values_clause}
        }}
        ?person cidoc:P71i_is_listed_in ?dib .
      }}
      GROUP BY ?person
    }}


    OPTIONAL {{
      SELECT ?person
        (GROUP_CONCAT(DISTINCT STR(?residence); SEPARATOR=" | ") AS ?residences)
        (GROUP_CONCAT(DISTINCT ?residenceLabel; SEPARATOR=" | ") AS ?residenceLabels)
      WHERE {{
        ?person cidoc:P74_has_current_or_former_residence ?residence .
        FILTER(
          CONTAINS(STR(?residence), "kg.virtualtreasury.ie/place/") ||
          CONTAINS(STR(?residence), "/county/") ||
          CONTAINS(STR(?residence), "/townland/") ||
          CONTAINS(STR(?residence), "/parish/")
        )
        OPTIONAL {{ ?residence rdfs:label ?residenceLabel }}
      }}
      GROUP BY ?person
    }}

    OPTIONAL {{
      {{
        ?floruitEvent cidoc:P11_had_participant ?person .
        FILTER(CONTAINS(STR(?floruitEvent), "/floruit/"))
      }}
      UNION
      {{
        ?floruitEvent cidoc:P12_occurred_in_the_presence_of ?person .
        FILTER(CONTAINS(STR(?floruitEvent), "/floruit/"))
      }}

      ?floruitEvent cidoc:P4_has_time-span ?timeSpan .
      OPTIONAL {{ ?timeSpan cidoc:P82a_begin_of_the_begin ?floruitBegin }}
      OPTIONAL {{ ?timeSpan cidoc:P82b_end_of_the_end ?floruitEnd }}
    }}
  }}
  GROUP BY ?person ?dibResource ?residences ?residenceLabels
  """
        return query

    def final_person(entity_name: str, era: str):
        parts = [
            unicodedata.normalize("NFC", p.strip())
            for p in entity_name.split()
            if p.strip()
        ]

        # Virtuoso bif:contains expects apostrophe escaping as doubled single quotes, not backslash
        safe_parts = [p.replace("'", "''") for p in parts]

        if len(safe_parts) >= 2:
            bif_q = " AND ".join(f"'{p}'" for p in safe_parts)
        elif len(safe_parts) == 1:
            bif_q = f"'{safe_parts[0]}'"
        else:
            bif_q = "''"

        query = f"""
  PREFIX crm:  <http://erlangen-crm.org/current/>
  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
  PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
  PREFIX voc:  <https://www.w3id.org/virtual-treasury/vocabulary#>

  SELECT DISTINCT ?person ?name
  WHERE {{
    ?person a crm:E21_Person ;
            vrti:VRTI_ERA|vrti:has_era_type voc:{era} ;
            crm:P1_is_identified_by ?appellation .
    ?appellation rdfs:label ?name .
    ?name bif:contains "{bif_q}"
  }}
  LIMIT 10
  """
        return query

    def expand_location_knowledge(uri_list: list):
        if not uri_list:
            return None

        values_clause = "\n".join(f"<{uri}>" for uri in uri_list)

        query = f"""
  PREFIX cidoc: <http://erlangen-crm.org/current/>
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
      ?parentPlaces
      ?parentLabels
      (GROUP_CONCAT(DISTINCT STR(?sameAs); SEPARATOR=" | ") AS ?sameAsLinks)
      (GROUP_CONCAT(DISTINCT STR(?listedIn); SEPARATOR=" | ") AS ?externalResources)
      (SAMPLE(?vrtiId) AS ?vrtiIdentifier)
      (GROUP_CONCAT(DISTINCT STR(?approximatedBy); SEPARATOR=" | ") AS ?historicalApproximations)
  WHERE {{
    VALUES ?place {{
      {values_clause}
    }}

    OPTIONAL {{ ?place rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }}
    OPTIONAL {{ ?place rdfs:label ?labelGa FILTER(lang(?labelGa) = "ga") }}
    OPTIONAL {{ ?place cidoc:P2_has_type ?type }}
    OPTIONAL {{ ?place owl:sameAs ?sameAs }}
    OPTIONAL {{ ?place cidoc:P71i_is_listed_in ?listedIn }}
    OPTIONAL {{ ?place vrti:VrtiIdentifier ?vrtiId }}

    OPTIONAL {{
      ?place owl:sameAs ?logainmUri .
      FILTER(CONTAINS(STR(?logainmUri), "data.logainm.ie"))
    }}

    OPTIONAL {{
      ?approximatedBy cidoc:P189_approximates ?place .
    }}

    OPTIONAL {{
      SELECT ?place
        (GROUP_CONCAT(DISTINCT STR(?parent); SEPARATOR=" | ") AS ?parentPlaces)
        (GROUP_CONCAT(DISTINCT ?parentLabel; SEPARATOR=" | ") AS ?parentLabels)
      WHERE {{
        VALUES ?place {{
          {values_clause}
        }}
        ?place cidoc:P89_falls_within ?parent .
        OPTIONAL {{ ?parent rdfs:label ?parentLabel FILTER(lang(?parentLabel) = "en") }}
      }}
      GROUP BY ?place
    }}
  }}
  GROUP BY ?place ?parentPlaces ?parentLabels
  """
        return query


def escape_bif_contains(text: str) -> str:
    """
    Escape special characters for bif:contains search.
    Doubles single quotes (apostrophes) for Virtuoso.
    """
    # Double any single quotes/apostrophes
    text = text.replace("'", "''")
    # Also handle smart quotes
    text = text.replace("'", "''")
    text = text.replace("'", "''")
    return text
