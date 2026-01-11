import requests
from urllib.parse import urlencode

# VT_ENDPOINT = "https://virtuoso.virtualtreasury.ie/sparql"

# VT_ENDPOINT = "https://vrti-graph.adaptcentre.ie/" this aint working
VT_ENDPOINT = "https://vrti-graph-explorer.adaptcentre.ie/sparql/"


class VirtualTreasurySPARQL:
    """
    Client for VT sparql endpoint, acts as the way of accessing it
    """

    @staticmethod
    def query(sparql_query: str):
        params = {"query": sparql_query, "format": "application/sparql-results+json"}
        url = VT_ENDPOINT + "?" + urlencode(params)
        response = requests.get(url)
        if response.status_code != 200:
            raise RuntimeError(
                f"SPARQL Query Failed [{response.status_code}]: {response.text}"
            )
        return response.json()


# https://vrti-graph.adaptcentre.ie/
