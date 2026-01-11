from fastapi import APIRouter
from pydantic import BaseModel
from services.entity_linking.entity_linker import EntityLinker

router = APIRouter(prefix="/link", tags=["Entity Linking"])


class NERItem(BaseModel):
    text: str
    label: str


class LinkRequest(BaseModel):
    mentions: list[NERItem]


@router.post("/")
def link_entities(request: LinkRequest):
    """
    Take filtered NER output and query Virtual Treasury SPARQL endpoint
    """
    output = []

    for item in request.mentions:
        linked = EntityLinker.link_entity(item.text, item.label)
        output.append(
            {
                "mention": item.text,
                "label": item.label,
                "candidates": linked,
            },
        )
    return output
