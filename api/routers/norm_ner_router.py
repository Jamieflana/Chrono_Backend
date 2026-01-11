from fastapi import APIRouter
from pydantic import BaseModel
from services.new_normalize import normalize_v2
from services.ner_engines import BertNER
from services.entity_linking.sparql_learning import query_sparql
from services.ranking.candidate_ranker import CandidateRanker

router = APIRouter(prefix="/pipeline", tags=["Part NLP Pipeline"])


class DebugRequest(BaseModel):
    text: str


bert_ner = BertNER()


@router.post("/debug")
def run_debug(request: DebugRequest):
    visual_text = request.text
    normalized_text, char_map = normalize_v2(visual_text)
    # 2) NER

    ner_raw = bert_ner.analyze(normalized_text)
    query_resp = query_sparql(ner_raw)
    # cr = CandidateRanker(visual_text, normalized_text)
    # candidates_ranked = cr.rank_candidates(query_resp)

    return {"visual": visual_text, "normalized": normalized_text, "ents": query_resp}
