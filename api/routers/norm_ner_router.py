from collections import defaultdict
from enum import Enum
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from services.entity_linking.sparql_learning import query_sparql
from services.ner.filter_entities import filter_ner_entities
from services.ner_engines import BertNER, FlairNER, SpacyNER, StanzaNER
from services.new_normalize import normalize_v2
from services.ranking.candidate_ranker import CandidateRanker
from services.text_extraction.parser import extract_and_format

router = APIRouter(prefix="/pipeline", tags=["Part NLP Pipeline"])

NER_ENGINES = {
    "spacy": SpacyNER(),
    # "flair": FlairNER(),
    "bert": BertNER(),
    "stanza": StanzaNER(),
}


class NERModel(str, Enum):
    BERT = "bert"
    SPACY = "spacy"
    # FLAIR = "flair"
    STANZA = "stanza"


class DebugRequest(BaseModel):
    text: str


# bert_ner = BertNER()


def process_ner(visual_text: str, ner_engine: str):
    normalized_text, char_map = normalize_v2(visual_text)
    engine = NER_ENGINES.get(ner_engine)
    ner_raw = engine.fast_analyse(normalized_text)
    filter_entities, spans_lookup = filter_ner_entities(ner_raw)
    query_resp, loc_graph = query_sparql(filter_entities)
    data_block = {
        "visual": visual_text,
        "normalized": normalized_text,
        "ents": query_resp,
        "spans_lookup": spans_lookup,
    }

    cr = CandidateRanker(data_block, loc_graph)
    ranked_ents = cr.rank()
    return {
        "visual": visual_text,
        "normalized": normalized_text,
        "ranked_entities": data_block["ents"],
        "char_map": char_map,
        "spans_lookup": spans_lookup,
    }


@router.post("/upload/text")
async def run_debug(
    request: DebugRequest,
    ner_engine: str = Query("bert", enum=list(NER_ENGINES.keys())),
):

    visual_text = request.text

    normalized_text, char_map = normalize_v2(visual_text)
    engine = NER_ENGINES.get(ner_engine)
    ner_raw = engine.fast_analyse(normalized_text)
    filter_entities, spans_lookup = filter_ner_entities(ner_raw)
    print(spans_lookup)
    query_resp, loc_graph = query_sparql(filter_entities)
    data_block = {
        "visual": visual_text,
        "normalized": normalized_text,
        "ents": query_resp,
        "spans_lookup": spans_lookup,
    }

    cr = CandidateRanker(data_block, loc_graph)
    ranked_ents = cr.rank()
    return {
        "visual": visual_text,
        "normalized": normalized_text,
        "ranked_entities": data_block["ents"],
        "char_map": char_map,
        "spans_lookup": spans_lookup,
    }


@router.post("/upload/file")
async def run_file(
    file: UploadFile = File(..., description="Text or TEI/XML file to analyze"),
    ner_engine: str = Query("bert", enum=list(NER_ENGINES.keys())),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    filename = file.filename or "unknown.txt"
    file_extension = Path(filename).suffix.lower()
    is_xml = file_extension in {".xml", ".tei", ".tei.xml"}
    if not is_xml:
        try:
            decoded = content.decode("utf-8")
            is_xml = decoded.strip().startswith("<?xml") or "<TEI" in decoded[:500]
        except UnicodeDecodeError:
            raise HTTPException(400, "File must be UTF-8 encoded text")

    if is_xml:
        try:
            visual_text, paragraphs, pages = extract_and_format(xml_content=content)
        except Exception as e:
            raise HTTPException(400, f"Error parsing XML")
    else:
        # Plain text file
        try:
            visual_text = content.decode("utf-8")
            print(f"✓ Loaded plain text file: {file.filename}")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="File must be UTF-8 encoded text"
            )
    return process_ner(visual_text, ner_engine)


"""
@router.post("/upload/file")
async def run_file(
    file: UploadFile = File(...),  # REQUIRED file
    ner_engine: str = Query("bert", enum=list(NER_ENGINES.keys())),
):
    # Just print the filename and return it
    print(f"Uploaded file: {file.filename}")

    return {
        "filename": file.filename,
        "message": f"File '{file.filename}' uploaded successfully",
    }
"""


@router.post("/ner_only")
def run_ner_only(
    request: DebugRequest,
    ner_engine: str = Query("bert", enum=list(NER_ENGINES.keys()) + ["all"]),
):
    text = request.text
    normalized_text, char_map = normalize_v2(text)
    engine = NER_ENGINES.get(ner_engine)
    results = {}
    if not engine:
        raise HTTPException(status_code=400, detail=f"Unknown engine '{ner_engine}'")
    results[ner_engine] = engine.analyze(normalized_text)
    return {
        "visual": text,
        "norm": normalized_text,
        "ner": results,
        "engine": ner_engine,
    }


@router.post("fine-tune")
def fine_tune_debug(
    request: DebugRequest,
    ner_engine: str = Query("bert", enum=list(NER_ENGINES.keys()) + ["all"]),
):
    text = request.text
    normalized_text, char_map = normalize_v2(text)
    engine = NER_ENGINES.get(ner_engine)
    ner_results = engine.analyze(normalized_text)
    entities = [(ent["start"], ent["end"], ent["label"]) for ent in ner_results]
    training_format = {"text": normalized_text, "entities": entities}
    entity_preview = [
        {
            "span": normalized_text[ent[0] : ent[1]],
            "start": ent[0],
            "end": ent[1],
            "label": ent[2],
            "score": next(
                (e["score"] for e in ner_results if e["start"] == ent[0]), None
            ),
        }
        for ent in entities
    ]

    return {
        "training_format": training_format,  # Ready to save as-is
        "preview": entity_preview,  # For human review
        "visual_text": text,  # Original for reference
        "normalized_text": normalized_text,  # What BERT sees
        "total_entities": len(entities),
    }


def remember_duplicates(entities):
    entity_map = defaultdict(lambda: {"entity": None, "spans": []})
    for ent in entities:
        key = (ent["text"], ent["label"])
        if entity_map[key]["entity"] is None:
            entity_map[key]["entity"] = ent.copy()

        # Collect all spans
        entity_map[key]["spans"].append(
            {"start": ent["start"], "end": ent["end"], "score": ent["score"]}
        )
        unique_entities = [v["entity"] for v in entity_map.values()]

    # Create spans lookup: {(text, label): [list of spans]}
    spans_lookup = {
        (v["entity"]["text"], v["entity"]["label"]): v["spans"]
        for v in entity_map.values()
    }

    return unique_entities, spans_lookup
