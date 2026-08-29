import { useEffect, useState } from "react";
import { api } from "../api/client";
import OrbitPlot2D from "./OrbitPlot2D";
import ManeuverDetail from "./ManeuverDetail";

export default function ConjunctionDetail({ conjunction, onMetricsRefresh }) {
  const [separation, setSeparation] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setSeparation(null);
    setError(null);
    api
      .separation(conjunction.conjunction_id)
      .then((d) => !cancelled && setSeparation(d))
      .catch((e) => !cancelled && setError(String(e.message || e)));
    return () => {
      cancelled = true;
    };
  }, [conjunction.conjunction_id]);

  return (
    <div className="detail">
      <h2>
        {conjunction.object_a.name} ↔ {conjunction.object_b.name}
        {conjunction.synthetic && <span className="badge-syn">SYNTHETIC SCENARIO</span>}
      </h2>
      <div className={`tier ${conjunction.risk_tier}`}>{conjunction.risk_tier} risk</div>

      <div className="kv">
        <span className="k">Miss distance</span><span>{conjunction.miss_distance_km.toFixed(4)} km</span>
        <span className="k">Relative speed</span><span>{conjunction.rel_speed_km_s.toFixed(3)} km/s</span>
        <span className="k">Time of closest approach</span><span>{new Date(conjunction.tca).toUTCString()}</span>
        <span className="k">TCA from now</span><span>{conjunction.tca_hours_from_now.toFixed(2)} h</span>
        <span className="k">Collision probability</span><span>{conjunction.pc != null ? conjunction.pc.toExponential(3) : "—"}</span>
        <span className="k">Composite risk score</span><span>{conjunction.risk_score ?? "—"}</span>
        <span className="k">NORAD ids</span><span>{conjunction.object_a.norad_id} / {conjunction.object_b.norad_id}</span>
      </div>

      <div className="section-title" style={{ padding: "10px 0", border: "none" }}>
        Separation around TCA
      </div>
      {error && <div className="error">{error}</div>}
      {separation ? <OrbitPlot2D separation={separation} /> : !error && <div className="loading">Loading…</div>}

      <ManeuverDetail conjunction={conjunction} onMetricsRefresh={onMetricsRefresh} />
    </div>
  );
}
