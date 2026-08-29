from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from app.container import get_container
from app.domain import ManeuverCandidate
from app.models import ManeuverOut, ManeuverRequest, ManeuverResponse, ObjectRef
from app.services.metrics_store import metrics

router = APIRouter()


def _candidate_out(c: ManeuverCandidate, epoch: datetime) -> ManeuverOut:
    return ManeuverOut(
        dv_rtn_mps=[round(x, 4) for x in c.dv_rtn_mps],
        dv_magnitude_mps=c.dv_magnitude_mps,
        burn_time=(epoch + timedelta(seconds=c.burn_time_s)).isoformat(),
        timing_margin_hours=c.timing_margin_hours,
        accepted=c.accepted,
        rejection_reason=c.rejection_reason,
        residual_pc=c.residual_pc,
        new_conjunctions=c.new_conjunctions,
    )


@router.post("/recommend-maneuver", response_model=ManeuverResponse)
def recommend_maneuver(req: ManeuverRequest) -> ManeuverResponse:
    container = get_container()
    result = container.get_detection(container.settings.default_window_hours)

    event = next((e for e in result.events if e.pair_id == req.conjunction_id), None)
    if event is None:
        raise HTTPException(404, f"unknown conjunction_id '{req.conjunction_id}'. "
                                 "Call GET /conjunctions first.")

    if req.object_id == event.object_a.norad_id:
        target, secondary = event.object_a, event.object_b
    elif req.object_id == event.object_b.norad_id:
        target, secondary = event.object_b, event.object_a
    else:
        raise HTTPException(422, f"object_id {req.object_id} is not part of "
                                 f"conjunction {req.conjunction_id}")

    candidates = container.maneuver_generator.generate(event)
    baseline_pc = event.pc if event.pc is not None else 0.0
    accepted, stats = container.maneuver_planner.recommend(
        target, secondary, candidates, result.objects,
        result.times_s, result.epoch_jd, result.epoch_fr,
        baseline_pc=baseline_pc,
    )
    metrics.record_maneuver_run(
        candidates=stats["candidates_generated"],
        rejected=stats["candidates_rejected"],
        total_rescreen_s=stats["total_rescreen_s"],
    )

    epoch = datetime.fromisoformat(result.epoch_iso)
    rejected = [c for c in candidates if not c.accepted]

    if accepted:
        msg = (f"{len(accepted)} safe maneuver(s) found; "
               f"{stats['candidates_rejected']} of {stats['candidates_generated']} "
               f"candidates rejected by re-screening.")
    else:
        msg = ("NO SAFE CANDIDATE FOUND: every generated maneuver was rejected by "
               "re-screening (residual risk too high or a new conjunction created).")

    return ManeuverResponse(
        conjunction_id=req.conjunction_id,
        maneuvered_object=ObjectRef(norad_id=target.norad_id, name=target.name),
        secondary_object=ObjectRef(norad_id=secondary.norad_id, name=secondary.name),
        baseline_pc=baseline_pc,
        baseline_miss_distance_km=round(event.miss_distance_km, 4),
        candidates_generated=stats["candidates_generated"],
        candidates_rejected=stats["candidates_rejected"],
        rejection_rate=stats["rejection_rate"],
        rescreen_s_per_candidate=stats["rescreen_s_per_candidate"],
        recommended=[_candidate_out(c, epoch) for c in accepted],
        rejected=[_candidate_out(c, epoch) for c in rejected],
        message=msg,
    )
