const BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

async function post(path, payload) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  base: BASE,
  health: () => get("/health"),
  conjunctions: (windowHours = 48, refresh = false) =>
    get(`/conjunctions?window_hours=${windowHours}${refresh ? "&refresh=true" : ""}`),
  separation: (cid) => get(`/conjunctions/${encodeURIComponent(cid)}/separation`),
  geometry: (cid) => get(`/conjunctions/${encodeURIComponent(cid)}/geometry`),
  metrics: () => get("/metrics"),
  recommendManeuver: (objectId, conjunctionId) =>
    post("/recommend-maneuver", { object_id: objectId, conjunction_id: conjunctionId }),
};
