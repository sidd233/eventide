import { api } from "../api/client";
import { Link } from "../router";

export default function Header({ health, loading, onRecompute }) {
  const dot = !health
    ? "warn"
    : health.status === "ok"
    ? health.tle_served_stale
      ? "warn"
      : "ok"
    : "err";

  const statusTitle =
    `backend ${api.base}` +
    (!health ? " · connecting…" : "") +
    (health?.tle_served_stale ? " · TLE cache stale" : "") +
    (health?.tle_source_error ? ` · ${health.tle_source_error}` : "");

  return (
    <header className="header">
      <span className="wordmark">Eventide</span>
      <nav>
        <Link to="/" className="nav-link" activeClassName="active">
          Dashboard
        </Link>
        <Link to="/wiki" className="nav-link" activeClassName="active">
          Wiki
        </Link>
      </nav>
      <span className="spacer" />
      <span className={`status-dot ${dot}`} title={statusTitle} />
      <button className="btn sm" onClick={onRecompute} disabled={loading}>
        {loading ? "Recomputing…" : "Recompute"}
      </button>
    </header>
  );
}
