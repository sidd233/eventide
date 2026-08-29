from fastapi import APIRouter

from app.services.metrics_store import metrics

router = APIRouter()


@router.get("/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()
