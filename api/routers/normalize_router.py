# api/routes/normalize.py
from fastapi import APIRouter
from pydantic import BaseModel

# from services.normalize_services import normalize
from services.new_normalize import normalize_v2

router = APIRouter(prefix="/normalize", tags=["Normalizer"])


class NormalizeRequest(BaseModel):
    text: str


class NormalizeResponse(BaseModel):
    input: str
    normalized: str
    char_map: dict[int, int]


@router.post("/", response_model=NormalizeResponse)
def normalize_text(request: NormalizeRequest):
    normalized_text, char_map = normalize_v2(request.text)

    return NormalizeResponse(
        input=request.text,
        normalized=normalized_text,
        char_map=char_map,
    )
