from fastapi import APIRouter
from pydantic import BaseModel

from services.normalize_services import normalize
from services.new_normalize import normalize_v2
from services.ner_engines import BertNER
from services.entity_linking.entity_linker import EntityLinker
from services.ranking.ranker import CandidateRanker

router = APIRouter(prefix="/pipeline", tags=["Full NLP Pipeline"])


class PipelineRequest(BaseModel):
    text: str


# Old
@router.post("/run")
def run_pipeline(request: PipelineRequest):
    """Full pipeline: Normalization -> NER -> Linking -> Ranking"""

    input_text = request.text

    # 1. NORMALIZE
    # normalized_text, char_map = normalize(input_text)
    # print("Norm done")
    normalized_text = normalize_v2(input_text)
    print("Norm done")
    # print(normalized_text)

    # 2. NER (BERT, filter PER + LOC)
    ner_engine = BertNER()
    ner_raw = ner_engine.analyze(normalized_text)

    filtered_mentions = [ent for ent in ner_raw if ent["label"] in ("PER", "LOC")]
    # print("filtered mentions done")
    # print(filtered_mentions)

    # 3. ENTITY LINKING
    linked_output = []
    for ent in filtered_mentions:
        candidates = EntityLinker.link_entity(ent["text"], ent["label"])
        # print("Candidates", candidates)
        ranked = CandidateRanker.rank(
            ent["text"], ent["label"], candidates, document_text=normalized_text
        )  # pass in the text
        linked_output.append(
            {"mention": ent["text"], "label": ent["label"], "ranked_candidates": ranked}
        )
    print("linked_output done")
    # print(linked_output)
    # 4. FINAL OUTPUT
    return {
        "input": input_text,
        "normalized": normalized_text,
        "entities": linked_output,
    }


bert_ner = BertNER()


@router.post("/analyze")
def analyze(request: PipelineRequest):
    visual_text = request.text

    # 1) normalize
    # normalized_text, char_map = normalize(visual_text)
    normalized_text, char_map = normalize_v2(visual_text)
    # 2) NER

    ner_raw = bert_ner.analyze(normalized_text)

    # convert BERT output -> spans
    entities = []
    for ent in ner_raw:
        if ent["label"] not in ("PER", "LOC"):
            continue

        mention = ent["text"]
        start = normalized_text.lower().find(mention.lower())
        if start == -1:
            continue

        end = start + len(mention)

        candidates = EntityLinker.link_entity(mention, ent["label"])
        ranked = CandidateRanker.rank(
            ent["text"], ent["label"], candidates, document_text=normalized_text
        )

        entities.append(
            {
                "text": mention,
                "label": ent["label"],
                "start": start,
                "end": end,
                "ranked_candidates": ranked,
            }
        )

    return {"visual": visual_text, "normalized": normalized_text, "entities": entities}
