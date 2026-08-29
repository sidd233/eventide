import { useState } from "react";
import { api } from "../api/client";

function dvLabel(v) {
  const names = ["R", "T", "N"];
  return v.map((x, i) => (x !== 0 ? `${x > 0 ? "+" : ""}${x} ${names[i]}` : null))
    .filter(Boolean)
    .join(", ") || "0";
}

function Card({ c }) {
  return (
    <div className={`maneuver-card ${c.accepted ? "accepted" : "rejected"}`}>
      <div className="head">
        <span>Δv {c.dv_magnitude_mps} m/s · {dvLabel(c.dv_rtn_mps)}</span>
        <span className="muted">{c.accepted ? "SAFE" : "REJECTED"}</span>
      </div>
      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        burn {new Date(c.burn_time).toUTCString().slice(5, 22)} UTC · lead {c.timing_margin_hours} h ·
        residual Pc {c.residual_pc != null ? c.residual_pc.toExponential(1) : "—"}
      </div>
      {c.accepted ? (
        <div className="ok">✓ Clears the conjunction and creates no new high-risk approach.</div>
      ) : (
        <div className="reason">✗ {c.rejection_reason}</div>
      )}
      {c.new_conjunctions?.length > 0 && (
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          new conjunctions: {c.new_conjunctions.map((n) => `${n.object_name} (${n.miss_distance_km} km, Pc ${Number(n.pc).toExponential(1)})`).join("; ")}
        </div>
      )}
    </div>
  );
}

export default function ManeuverDetail({ conjunction, onMetricsRefresh }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAllRejected, setShowAllRejected] = useState(false);

  const a = conjunction.object_a;
  const b = conjunction.object_b;
  const [maneuverObj, setManeuverObj] = useState(a.norad_id);

  async function run() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.recommendManeuver(maneuverObj, conjunction.conjunction_id);
      setResult(r);
      onMetricsRefresh?.();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const rejected = result?.rejected || [];
  const shownRejected = showAllRejected ? rejected : rejected.slice(0, 3);

  return (
    <div style={{ marginTop: 20 }}>
      <div className="section-title" style={{ padding: "10px 0", border: "none" }}>
        Maneuver planning
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <label className="muted">Maneuver&nbsp;
          <select value={maneuverObj} onChange={(e) => setManeuverObj(Number(e.target.value))}>
            <option value={a.norad_id}>{a.name}</option>
            <option value={b.norad_id}>{b.name}</option>
          </select>
        </label>
        <button className="primary" onClick={run} disabled={loading}>
          {loading ? "Re-screening candidates…" : "Recommend avoidance maneuver"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{result.message}</div>
          <div className="muted" style={{ fontSize: 12 }}>
            {result.candidates_generated} candidates generated ·{" "}
            {result.candidates_rejected} rejected ({(result.rejection_rate * 100).toFixed(0)}%) ·{" "}
            {result.rescreen_s_per_candidate?.toFixed(2)} s/candidate
          </div>

          {result.recommended.length > 0 && (
            <>
              <div className="section-title" style={{ padding: "10px 0", border: "none" }}>Recommended</div>
              {result.recommended.map((c, i) => <Card c={c} key={`r${i}`} />)}
            </>
          )}

          <div className="section-title" style={{ padding: "10px 0", border: "none" }}>
            Rejected by re-screening
          </div>
          {shownRejected.map((c, i) => <Card c={c} key={`x${i}`} />)}
          {rejected.length > 3 && (
            <button onClick={() => setShowAllRejected((s) => !s)} style={{ marginTop: 4 }}>
              {showAllRejected ? "Show fewer" : `Show all ${rejected.length} rejected`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
