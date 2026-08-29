export default function AlertList({ conjunctions, selectedId, onSelect, onRefresh, loading }) {
  return (
    <div>
      <div className="section-title">
        <span>Conjunction alerts ({conjunctions.length})</span>
        <button onClick={onRefresh} disabled={loading}>
          {loading ? "Screening…" : "Refresh"}
        </button>
      </div>
      {conjunctions.length === 0 && !loading && (
        <div className="loading">No conjunctions in the current window.</div>
      )}
      {conjunctions.map((c) => (
        <div
          key={c.conjunction_id}
          className={`alert ${selectedId === c.conjunction_id ? "selected" : ""}`}
          onClick={() => onSelect(c)}
        >
          <div className="row1">
            <span className="pair">
              {c.object_a.name} ↔ {c.object_b.name}
              {c.synthetic && <span className="badge-syn">SYNTHETIC</span>}
            </span>
            <span className={`tier ${c.risk_tier}`}>{c.risk_tier}</span>
          </div>
          <div className="meta">
            <span>miss {c.miss_distance_km.toFixed(3)} km</span>
            <span>Δv-rel {c.rel_speed_km_s.toFixed(1)} km/s</span>
            <span>TCA +{c.tca_hours_from_now.toFixed(1)} h</span>
            <span>Pc {c.pc != null ? c.pc.toExponential(1) : "—"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
