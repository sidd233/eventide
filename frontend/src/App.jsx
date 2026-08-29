import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import MetricsPanel from "./components/MetricsPanel";
import AlertList from "./components/AlertList";
import ConjunctionDetail from "./components/ConjunctionDetail";
import Globe3D from "./components/Globe3D";

const WINDOW_HOURS = 48;

export default function App() {
  const [health, setHealth] = useState(null);
  const [conjunctions, setConjunctions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [geometry, setGeometry] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refreshMetrics = useCallback(() => {
    api.metrics().then(setMetrics).catch(() => {});
  }, []);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.conjunctions(WINDOW_HOURS, refresh);
      setConjunctions(data.conjunctions);
      setSelected((prev) => {
        if (prev) {
          const still = data.conjunctions.find((c) => c.conjunction_id === prev.conjunction_id);
          if (still) return still;
        }
        return data.conjunctions[0] || null;
      });
      refreshMetrics();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [refreshMetrics]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "unreachable" }));
    load();
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setGeometry(null);
      return;
    }
    let cancelled = false;
    api
      .geometry(selected.conjunction_id)
      .then((g) => !cancelled && setGeometry(g))
      .catch(() => !cancelled && setGeometry(null));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const healthDot =
    !health ? "warn" : health.status === "ok" ? (health.tle_served_stale ? "warn" : "ok") : "err";

  return (
    <div className="app">
      <div className="topbar">
        <h1>Eventide</h1>
        <span className="sub">Space debris collision risk · SGP4 · APSIS prefilter · Foster–Estes Pc · Δv re-screening</span>
        <span className="status">
          <span className={`dot ${healthDot}`} />
          backend {api.base}
          {health?.tle_served_stale ? " · TLE cache stale" : ""}
          {health?.tle_source_error ? ` · ${health.tle_source_error}` : ""}
        </span>
      </div>

      <MetricsPanel metrics={metrics} />

      {error && <div className="error">{error}</div>}

      <div className="main">
        <div className="left">
          <AlertList
            conjunctions={conjunctions}
            selectedId={selected?.conjunction_id}
            onSelect={setSelected}
            onRefresh={() => load(true)}
            loading={loading}
          />
        </div>
        <div className="right">
          <div style={{ flex: "1 1 55%", overflow: "auto" }}>
            {selected ? (
              <ConjunctionDetail conjunction={selected} onMetricsRefresh={refreshMetrics} />
            ) : (
              <div className="loading">{loading ? "Screening the catalog…" : "Select an alert."}</div>
            )}
          </div>
          <Globe3D geometry={geometry} />
        </div>
      </div>
    </div>
  );
}
