import { useEffect, useState } from "react";
import { api } from "../api/client";

const ROWS = [
  {
    key: "prefilter_reduction_rate",
    name: "Prefilter reduction rate",
    proves: "The scalability claim is real — the APSIS sieve removes a measurable share of pairs before any pairwise propagation.",
    fmt: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`),
  },
  {
    key: "pairs_before_filter",
    name: "Pairs before → after filter",
    proves: "Real screening scale for this run.",
    fmt: (v, m) =>
      v == null ? "—" : `${v.toLocaleString()} → ${(m.pairs_after_filter ?? 0).toLocaleString()}`,
  },
  {
    key: "end_to_end_screening_latency_s",
    name: "End-to-end screening latency",
    proves: "A full /conjunctions run is feasible on ordinary hardware.",
    fmt: (v) => (v == null ? "—" : `${v.toFixed(2)} s`),
  },
  {
    key: "live_catalog_objects",
    name: "Live catalogue objects",
    proves: "Object count actually propagated this run (capped by EVENTIDE_MAX_OBJECTS).",
    fmt: (v) => (v == null ? "—" : v.toLocaleString()),
  },
  {
    key: "false_negative_rate_synthetic",
    name: "False-negative rate (synthetic)",
    proves:
      "The high-recall safety claim. A 78-case labelled set (miss 0.05–15 km × 3 relative speeds) runs at startup; every dangerous case (miss ≤ 1 km) must score above the medium-Pc threshold. Target: 0%.",
    fmt: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`),
  },
  {
    key: "maneuver_rejection_rate",
    name: "Maneuver rejection rate",
    proves: "The core differentiator does something — most generated burns are rejected by re-screening.",
    fmt: (v) => (v == null ? "— (run a recommendation)" : `${(v * 100).toFixed(0)}%`),
  },
  {
    key: "rescreen_latency_s_per_candidate",
    name: "Re-screen latency per candidate",
    proves: "Re-screening is cheap enough to run for every one of the 30 candidates.",
    fmt: (v) => (v == null ? "— (run a recommendation)" : `${v.toFixed(2)} s`),
  },
];

export default function LiveMetrics() {
  const [m, setM] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.metrics().then(setM).catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <div className="error">{err}</div>;
  if (!m) return <div className="loading">Loading live metrics…</div>;

  return (
    <div className="wiki-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value now</th>
            <th>What it proves</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.key}>
              <td>{r.name}</td>
              <td className="mono">{r.fmt(m[r.key], m)}</td>
              <td>{r.proves}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
