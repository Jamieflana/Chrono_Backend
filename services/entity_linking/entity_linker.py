from services.sparql_client import VirtualTreasurySPARQL


class EntityLinker:
    """
    Entity Linking In VT
    """

    @staticmethod
    def query_person(name: str):
        tokens = name.lower().replace(",", "").split()

        token_filters = "\n".join(
            f'FILTER(CONTAINS(LCASE(STR(?label)), "{t}"))' for t in tokens
        )

        query = f"""
        PREFIX cidoc: <http://erlangen-crm.org/current/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?entity ?label ?g
        WHERE {{
        GRAPH ?g {{
            ?entity cidoc:P1_is_identified_by ?appellation .
            ?appellation rdfs:label ?label .
            {token_filters}
        }}
        }}
        LIMIT 50
        """
        return VirtualTreasurySPARQL.query(query)

    @staticmethod
    def query_location(name: str):
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX geo: <https://ont.virtualtreasury.ie/ontology#>
        PREFIX cidoc: <http://erlangen-crm.org/current/>

        SELECT ?entity ?label
        WHERE {{
            ?entity rdfs:label ?label .
            ?entity cidoc:P2_has_type ?type .

            FILTER(CONTAINS(LCASE(STR(?type)), "place"))  # FIXED

            FILTER(CONTAINS(LCASE(?label), LCASE("{name}")))
        }}
        LIMIT 20
        """
        return VirtualTreasurySPARQL.query(query)

    @staticmethod
    def link_entity(mention: str, label: str):
        """
        label = 'PER' or 'LOC'
        """

        if label == "PER":
            return EntityLinker.query_person(mention)

        if label == "LOC":
            return EntityLinker.query_location(mention)

        return None
