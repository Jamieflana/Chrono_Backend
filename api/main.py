from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from api.routers import (
    norm_ner_router,
)


app = FastAPI(title="Annotation Backend")


# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(norm_ner_router.router)
