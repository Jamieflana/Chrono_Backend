# Chrono Backend

This backend powers the live NLP pipeline for the Chrono dissertation system. It takes raw historical text or TEI/XML input, normalises the transcription, runs Named Entity Recognition using BERT, retrieves candidate VRTI entities through SPARQL, ranks those candidates, and returns a structured response for the React frontend.

## Backend API

The mounted FastAPI app exposes a single live router:

- `api/main.py`
- `api/routers/norm_ner_router.py`

That router runs the end-to-end pipeline used by the frontend:

1. Normalise historical transcription with `services/new_normalize.py`
2. Run BERT NER with `services/ner_engines.py`
3. Merge and clean spans with `services/ner_post_processing.py`
4. Deduplicate/filter entities with `services/filter_entities.py`
5. Retrieve VRTI candidates with `services/entity_linking/candidate_retrieval.py`
6. Build SPARQL queries with `services/entity_linking/sparql_queries.py`
7. Rank candidates with `services/ranking/candidate_ranker.py`
8. Generate score explanations with `services/ranking/score_explainer.py`

## Live API Endpoints

All live endpoints are mounted under `/pipeline`.

- `POST /pipeline/upload/text`
  Accepts form text input and returns the full normalized + ranked entity output.

- `POST /pipeline/upload/file`
  Accepts plain text or TEI/XML upload and runs the same pipeline.

- `POST /pipeline/ner_only`
  Runs normalisation + NER only and returns entity spans without entity linking.

## Key Files

- `api/main.py`
  FastAPI app entrypoint. Only `norm_ner_router` is mounted here.

- `api/routers/norm_ner_router.py`
  Main runtime router used by the system.

- `services/new_normalize.py`
  Historical text normalizer used by the backend.

- `services/ner_engines.py`
  NER model loading and inference.

- `services/ner_post_processing.py`
  Span repair and merge logic for noisy historical NER output.

- `services/filter_entities.py`
  Deduplication and lightweight entity filtering before retrieval.

- `services/entity_linking/candidate_retrieval.py`
  Candidate retrieval orchestration and candidate shaping.

- `services/entity_linking/sparql_queries.py`
  The SPARQL query builders used by the live retrieval path.

- `services/sparql_client.py`
  HTTP client for the VRTI SPARQL endpoint.

- `services/ranking/candidate_ranker.py`
  Feature-based candidate ranking for `PER` and `LOC` entities.

- `services/ranking/score_explainer.py`
  Natural-language explanation generation for ranked candidates.

- `services/text_extraction/parser.py`
  TEI/XML parsing used by the file upload route.

### Runtime code

- `api/`
- `services/`

### Evaluations used in the dissertation report. 

- `testing/ner`
- `testing/retrieval`
- `testing/ranking`

These folders contain the NER, retrieval, and ranking evaluation material, datasets and results.


## Requirements

Core runtime dependencies are listed in `requirements.txt`.

Important libraries used by the live system include:

- `fastapi`
- `uvicorn`
- `requests`
- `transformers`
- `torch`
- `sentence-transformers`
- `numpy`

Some optional or legacy libraries are still present in the requirements file for broader experimentation, but the live route is centered around the current BERT-based pipeline.

## Running The Backend

From the `Backend` directory:

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

By default the frontend expects the backend at:

```text
http://127.0.0.1:8000
```

## External Dependency

Candidate retrieval depends on the Virtual Treasury SPARQL endpoint configured in:

- `services/sparql_client.py`

Current endpoint:

```text
https://vrti-graph-explorer.adaptcentre.ie/sparql/
```

If that endpoint is unavailable, entity linking and ranking will fail even if normalization and NER still work.

## Input / Output Shape

The main pipeline routes return:

- original visual text
- normalized text
- ranked entity blocks
- `char_map` for mapping normalized offsets back to original text
- `spans_lookup` for repeated mentions

This response is consumed directly by the frontend annotation interface.
