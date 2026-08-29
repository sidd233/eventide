"""FastAPI application: CORS, route registration. Nothing else lives here."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import conjunctions, health, maneuvers, metrics, tracks


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Record the risk model's false-negative rate on the labelled synthetic set
    # so /metrics reports a real recall figure from the first request.
    from app.container import get_container
    from app.services.metrics_store import metrics as metrics_store
    from app.services.synthetic_eval import evaluate_false_negative_rate

    rate, n = evaluate_false_negative_rate(get_container().risk_model)
    metrics_store.record_false_negative_rate(rate, n)
    yield


app = FastAPI(
    title="Eventide — Space Debris Collision Risk Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.netlify\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(conjunctions.router, tags=["conjunctions"])
app.include_router(tracks.router, tags=["tracks"])
app.include_router(maneuvers.router, tags=["maneuvers"])
app.include_router(metrics.router, tags=["metrics"])


@app.get("/")
def root() -> dict:
    return {"service": app.title, "docs": "/docs"}
