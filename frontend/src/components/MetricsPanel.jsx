function fmt(v, digits = 2) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    if (v !== 0 && (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e6)) return v.toExponential(2);
    return v.toLocaleString(undefined, { maximumFractionDigits: digits });
  }
  return String(v);
}

export default function MetricsPanel({ metrics }) {
  const m = metrics || {};
  const cards = [
    {
      label: "Prefilter reduction",
      value: m.prefilter_reduction_rate != null ? `${(m.prefilter_reduction_rate * 100).toFixed(1)}%` : "—",
      sub: `${fmt(m.pairs_after_filter, 0)} / ${fmt(m.pairs_before_filter, 0)} pairs`,
    },
    {
      label: "Screening latency",
      value: m.end_to_end_screening_latency_s != null ? `${fmt(m.end_to_end_screening_latency_s)} s` : "—",
      sub: `${fmt(m.live_catalog_objects, 0)} objects`,
    },
    {
      label: "False-negative rate",
      value: m.false_negative_rate_synthetic != null ? `${(m.false_negative_rate_synthetic * 100).toFixed(1)}%` : "—",
      sub: `${fmt(m.synthetic_test_cases, 0)} synthetic cases`,
    },
    {
      label: "Maneuver rejection rate",
      value: m.maneuver_rejection_rate != null ? `${(m.maneuver_rejection_rate * 100).toFixed(0)}%` : "—",
      sub: `${fmt(m.maneuver_candidates_last_run, 0)} candidates`,
    },
    {
      label: "Re-screen / candidate",
      value: m.rescreen_latency_s_per_candidate != null ? `${fmt(m.rescreen_latency_s_per_candidate)} s` : "—",
      sub: "post-burn vs full catalog",
    },
    {
      label: "Screening window",
      value: m.screening_window_hours != null ? `${fmt(m.screening_window_hours, 0)} h` : "—",
      sub: "propagation horizon",
    },
  ];
  return (
    <div className="metrics-strip">
      {cards.map((c) => (
        <div className="stat" key={c.label}>
          <div className="label">{c.label}</div>
          <div className="value">
            {c.value} <small>{c.sub}</small>
          </div>
        </div>
      ))}
    </div>
  );
}
