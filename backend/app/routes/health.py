from fastapi import APIRouter

from app.container import get_container
from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    src = get_container().tle_source
    return HealthResponse(
        tle_source_error=src.last_error,
        tle_served_stale=src.served_stale,
    )
