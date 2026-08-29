export default function AlertList({
  items,
  total,
  objects,
  focus,
  onFocus,
  selectedId,
  onSelect,
  loading,
}) {
  return (
    <>
      <div className="focus-bar">
        <select
          value={focus ?? ""}
          onChange={(e) => onFocus(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Focus on an object…</option>
          {objects.map((o) => (
            <option key={o.norad_id} value={o.norad_id}>
              {o.name} · {o.norad_id}
            </option>
          ))}
        </select>
        {focus != null && (
          <span className="focus-chip" onClick={() => onFocus(null)}>
            × showing {items.length} of {total} — clear
          </span>
        )}
      </div>

      <div className="section-title bar">
        <span>Conjunction alerts</span>
        <span className="num">
          {items.length}
          {focus != null ? ` / ${total}` : ""}
        </span>
      </div>

      <div className="alert-list">
        {items.length === 0 && (
          <div className="loading">
            {loading ? "Screening…" : "No conjunctions match."}
          </div>
        )}
        {items.map((c) => (
          <div
            key={c.conjunction_id}
            className={`alert ${selectedId === c.conjunction_id ? "selected" : ""}`}
            onClick={() => onSelect(c)}
          >
            <div className="row">
              <span className="pair">
                {c.object_a.name} ↔ {c.object_b.name}
              </span>
              <span className={`tier ${c.risk_tier}`}>{c.risk_tier}</span>
            </div>
            <div className="sub">
              {c.synthetic && (
                <span className="badge" style={{ marginRight: 8 }}>
                  Synthetic
                </span>
              )}
              miss <span className="num">{c.miss_distance_km.toFixed(3)}</span> km
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
