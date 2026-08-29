from fastapi import APIRouter, Query

from app.container import get_container
from app.models import ConjunctionsResponse
from app.routes._serialize import event_to_out
from app.services.metrics_store import metrics

router = APIRouter()


@router.get("/conjunctions", response_model=ConjunctionsResponse)
def conjunctions(
    window_hours: float = Query(default=48.0, ge=1.0, le=168.0),
    refresh: bool = Query(default=False),
) -> ConjunctionsResponse:
    container = get_container()
    result = container.get_detection(window_hours, force=refresh)
    metrics.record_detection(result)

    return ConjunctionsResponse(
        epoch=result.epoch_iso,
        window_hours=result.window_hours,
        object_count=result.object_count,
        pairs_before_filter=result.pairs_before_filter,
        pairs_after_filter=result.pairs_after_filter,
        prefilter_reduction_rate=round(result.reduction_rate, 4),
        screening_latency_s=round(result.screening_latency_s, 3),
        conjunctions=[event_to_out(ev, result) for ev in result.events],
    )
