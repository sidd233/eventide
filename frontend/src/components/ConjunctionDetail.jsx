import { useEffect, useState } from "react";
import { api } from "../api/client";
import OrbitPlot2D from "./OrbitPlot2D";
import ManeuverDetail from "./ManeuverDetail";

export default function ConjunctionDetail({ conjunction }) {
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

  const c = conjunction;

  return (
    <div className="detail">
      <h2>
        {c.object_a.name} ↔ {c.object_b.name}
        {c.synthetic && <span className="badge">Synthetic scenario</span>}
      </h2>
      <div className="headline-tier">
        <span className={`tier ${c.risk_tier}`}>{c.risk_tier} risk</span>
      </div>

      <dl className="facts">
        <dt>Miss distance</dt>
        <dd>
          <span className="num">{c.miss_distance_km.toFixed(4)}</span>{" "}
          <span className="unit">km</span>
        </dd>
        <dt>Relative speed</dt>
        <dd>
          <span className="num">{c.rel_speed_km_s.toFixed(3)}</span>{" "}
          <span className="unit">km/s</span>
        </dd>
        <dt>Time of closest approach</dt>
        <dd>
          <span className="num">{new Date(c.tca).toUTCString()}</span>{" "}
          <span className="unit">(+{c.tca_hours_from_now.toFixed(1)} h)</span>
        </dd>
        <dt>Collision probability</dt>
        <dd>
          <span className="num">
            {c.pc != null ? c.pc.toExponential(3) : "—"}
          </span>
        </dd>
        <dt>Composite risk score</dt>
        <dd>
          <span className="num">{c.risk_score ?? "—"}</span>
        </dd>
        <dt>NORAD ids</dt>
        <dd>
          <span className="num">
            {c.object_a.norad_id} / {c.object_b.norad_id}
          </span>
        </dd>
      </dl>

      <div className="section-title inline">Separation around TCA</div>
      {error && <div className="error">{error}</div>}
      {separation ? (
        <OrbitPlot2D separation={separation} />
      ) : (
        !error && <div className="loading">Loading…</div>
      )}
      <div className="plot-note">
        Log scale. The curve is re-sampled at 1-second spacing within ±3 minutes of TCA, so it
        reaches the true closest approach — the red point sits on the line rather than floating
        below a coarsely-sampled dip.
      </div>

      <ManeuverDetail key={conjunction.conjunction_id} conjunction={conjunction} />
    </div>
  );
}
