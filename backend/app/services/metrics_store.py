"""Process-local metrics store. Services record numbers here as they run; the
``/metrics`` route reads them. No database — everything is per-process and
resets on restart, which is fine for the MVP (see spec §6)."""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsStore:
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Detection (Phase 1)
    last_reduction_rate: float | None = None
    last_pairs_before: int | None = None
    last_pairs_after: int | None = None
    last_screening_latency_s: float | None = None
    last_object_count: int | None = None
    last_window_hours: float | None = None

    # Assessment (Phase 2) - set from the labelled synthetic suite on demand.
    false_negative_rate: float | None = None
    synthetic_cases: int | None = None

    # Maneuver re-screening (Phase 3)
    last_maneuver_rejection_rate: float | None = None
    last_maneuver_candidates: int | None = None
    last_rescreen_latency_s_per_candidate: float | None = None

    _rescreen_latencies: deque = field(default_factory=lambda: deque(maxlen=200))

    def record_detection(self, result) -> None:
        with self._lock:
            self.last_reduction_rate = result.reduction_rate
            self.last_pairs_before = result.pairs_before_filter
            self.last_pairs_after = result.pairs_after_filter
            self.last_screening_latency_s = result.screening_latency_s
            self.last_object_count = result.object_count
            self.last_window_hours = result.window_hours

    def record_maneuver_run(
        self, candidates: int, rejected: int, total_rescreen_s: float
    ) -> None:
        with self._lock:
            self.last_maneuver_candidates = candidates
            self.last_maneuver_rejection_rate = (
                rejected / candidates if candidates else None
            )
            per = total_rescreen_s / candidates if candidates else None
            self.last_rescreen_latency_s_per_candidate = per
            if per is not None:
                self._rescreen_latencies.append(per)

    def record_false_negative_rate(self, rate: float, n_cases: int) -> None:
        with self._lock:
            self.false_negative_rate = rate
            self.synthetic_cases = n_cases

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avg_rescreen = (
                sum(self._rescreen_latencies) / len(self._rescreen_latencies)
                if self._rescreen_latencies
                else None
            )
            return {
                "prefilter_reduction_rate": self.last_reduction_rate,
                "pairs_before_filter": self.last_pairs_before,
                "pairs_after_filter": self.last_pairs_after,
                "end_to_end_screening_latency_s": self.last_screening_latency_s,
                "live_catalog_objects": self.last_object_count,
                "screening_window_hours": self.last_window_hours,
                "false_negative_rate_synthetic": self.false_negative_rate,
                "synthetic_test_cases": self.synthetic_cases,
                "maneuver_rejection_rate": self.last_maneuver_rejection_rate,
                "maneuver_candidates_last_run": self.last_maneuver_candidates,
                "rescreen_latency_s_per_candidate": self.last_rescreen_latency_s_per_candidate,
                "rescreen_latency_s_per_candidate_avg": avg_rescreen,
            }


metrics = MetricsStore()
