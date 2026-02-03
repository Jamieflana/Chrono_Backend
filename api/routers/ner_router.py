from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from services.ner_engines import SpacyNER, FlairNER, BertNER, StanzaNER

router = APIRouter(prefix="/ner", tags=["Named Entity Recognition"])

# Init the base engines
engines = {
    # "spacy": SpacyNER(),
    # "flair": FlairNER(),
    # "bert": BertNER(),
    # "stanza": StanzaNER()
}


class TextIn(BaseModel):
    text: str


@router.post("/annotate")
def annotate_text(
    text_in: TextIn, engine: str = Query("bert", enum=list(engines.keys()) + ["all"])
):
    """
    Run NER using one or multiple black-box engines.
    """
    text = text_in.text
    results = {}

    if engine == "all":
        # Dynamically run all engines in the registry
        for name, model in engines.items():
            results[name] = model.analyze(text)
    else:
        model = engines.get(engine)
        if not model:
            raise HTTPException(status_code=400, detail=f"Unknown engine '{engine}'")
        results[engine] = model.analyze(text)

    return results
