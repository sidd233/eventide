# Eventide — Space Debris Tracking & Satellite Collision Risk Prediction Dashboard

Detect → Assess → Act. A live pipeline that ingests current TLEs, screens the
catalogue for conjunctions with SGP4, scores collision probability with the
Foster–Estes method, and — the differentiator — **generates avoidance maneuvers,
re-screens each one against the whole catalogue, and rejects any that don't
actually clear the risk or that create a new conjunction.**

```
backend/   FastAPI + SGP4 + NumPy/SciPy   — the physics and the API
frontend/  React + Vite + Plotly + CesiumJS — hero globe, alert list, 2-D plot, metrics, /wiki
```

---

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Python 3.11–3.13 recommended
pip install -r requirements.txt
uvicorn app.main:app --reload                          # http://localhost:8000  (/docs for Swagger)
```

### Frontend

```bash
cd frontend
nvm use lts            # once per shell
pnpm install
cp .env.example .env   # point VITE_API_BASE at the backend if not localhost:8000
pnpm dev               # http://localhost:5173
```

### Tests

```bash
cd backend && source .venv/bin/activate
pytest -q              # 27 tests: SGP4 vectors, filter logic, Pc monotonicity/recall,
                       # detection integration, maneuver re-screening, full API
```

The test suite never touches the network — it runs against `tests/fixtures/sample_tles.txt`.

---

## What the pipeline does (phase by phase)

| Phase | Module | What it produces |
|---|---|---|
| **1 Detect** | `services/tle_fetch.py`, `propagate.py`, `filters.py`, `detect.py` | `GET /conjunctions?window_hours=48` → ranked close approaches with refined TCA & miss distance |
| **2 Assess** | `services/risk_models.py`, `assess.py` | adds `pc`, `risk_score`, `risk_tier` (Low/Medium/High) to each conjunction |
| **3 Act** | `services/maneuver.py` | `POST /recommend-maneuver {object_id, conjunction_id}` → ranked **safe** maneuvers **plus every rejected candidate and why** |
| **4–5 UI** | `frontend/src/components/*`, `pages/*` | hero 3-D globe, alert list with per-object focus filter, continuous separation-vs-time plot, maneuver explainability panel, and an in-app `/wiki` explaining every algorithm |
| **6 Metrics** | `services/metrics_store.py`, `routes/metrics.py` | `GET /metrics` — real numbers from the running system |

### Algorithms
- **SGP4** propagation (`sgp4`, Vallado 2006). Verified against the published
  test vector for satellite 00005 (`tests/test_propagate.py`).
- **APSIS prefilter** — perigee/apogee altitude-band overlap; a conservative
  geometric sieve applied before any pairwise propagation.
- **Range-rate / segment-minimum TCA search** — catches multi-km/s passes that a
  plain coarse-grid minimum would step over — then `scipy` bounded minimisation
  to pin TCA and miss distance.
- **Foster–Estes 2-D Pc** — relative position and combined covariance projected
  onto the conjunction plane, 2-D Gaussian integrated over the combined
  hard-body radius. Covariance is km-scale and along-track-dominated (a
  representative propagated-TLE error model) and grows with time to TCA.
- **Δv grid search** — radial / along-track / cross-track × {0.02 … 0.5 m/s},
  executed at a configurable lead time before TCA.
- **Re-screening loop** — the maneuvered arc is propagated with a *differential*
  two-body model (SGP4 baseline + burned-minus-unburned two-body delta, so the
  bulk of the modelling error cancels), then re-checked against the whole
  catalogue. A candidate is rejected if residual Pc stays above the reject
  threshold **or** it creates a new conjunction that didn't exist before.

---

## Architecture — SOLID

Every seam the spec calls for is an abstract base class with injected implementations:

| Principle | Where |
|---|---|
| **S**RP | one job per module: `tle_fetch` fetches, `propagate` propagates, `detect` orchestrates, `assess` scores, `maneuver` plans. |
| **O**CP | `ConjunctionFilter` and `RiskModel` are strategies — add `PathFilter` or a Chan Pc model by subclassing, no edits to `detect.py` / `assess.py`. |
| **L**SP | `AcceptAllFilter` is substituted for `ApsisFilter` in a test to *measure* reduction rate; any `RiskModel` slots into `RiskAssessor`. |
| **I**SP | `TLESource` exposes only `fetch()`; caching/ephemeris are not on the interface. |
| **D**IP | `ConjunctionDetector`, `RiskAssessor`, `ManeuverPlanner` take abstractions in their constructors. `app/container.py` is the only place concrete classes are named. |

---

## Metrics (`GET /metrics`, shown as the dashboard strip)

| Metric | Meaning |
|---|---|
| `prefilter_reduction_rate` | fraction of pairs the APSIS filter eliminates before propagation |
| `end_to_end_screening_latency_s` | wall-clock for a full `/conjunctions` call at the current catalogue size |
| `false_negative_rate_synthetic` | recall on a 78-case labelled synthetic set, computed at startup — must be 0% |
| `maneuver_rejection_rate` | fraction of generated candidates rejected by re-screening |
| `rescreen_latency_s_per_candidate` | cost of re-screening one candidate against the catalogue |
| `live_catalog_objects` / `pairs_*` | real scale of the current run |

**Note on the prefilter reduction rate:** the literature figure (~62%, Stevenson
et al. 2023) is for a full multi-shell catalogue. The default object set here is
dominated by debris clouds (Fengyun-1C, Iridium-33, Cosmos-2251/1408) that sit in
a narrow altitude band, so the APSIS filter has less to remove (~30–45%). Widen
`EVENTIDE_TLE_GROUPS` to span more altitudes and the rate rises. The mechanism is the
same; only the input distribution differs.

---

## Real data vs. the injected demo scenario

The alert list is **real**: current CelesTrak TLEs, real conjunctions between
tracked debris objects.

One conjunction is **synthetic**, flagged `synthetic: true` in the API and
`SYNTHETIC` in the UI. A genuinely dangerous (<1 km, high-Pc) conjunction inside
a 48 h window is rare in any few-hundred-object sample, so `services/scenario.py`
crafts one debris TLE on a real crossing trajectory with the ISS (~15 km/s
closing speed) to guarantee the maneuver-rejection demo always has something to
act on. Set `EVENTIDE_DEMO_INJECT_SCENARIO=false` for a pure real-data run.

---

## Deploy

- **Backend → Render:** `backend/render.yaml` is a blueprint. Set
  `EVENTIDE_CORS_ORIGINS` to your frontend origin (JSON array). Health check: `/health`.
  Also works on Railway / Fly / any `uvicorn app.main:app` host (`Procfile` included).
- **Frontend → Vercel or Netlify:** `frontend/vercel.json` / `netlify.toml`
  included. Set `VITE_API_BASE` to the deployed backend URL. SPA rewrites configured.

CORS also allows any `*.vercel.app` / `*.netlify.app` origin out of the box for
preview deploys.

---

## Explicitly out of scope for the MVP (spec §6)

- **No ML ranking model** — the composite `risk_score` is a transparent heuristic
  (log-Pc + urgency + closeness). scikit-learn/LightGBM ranking is a documented
  extension, not built.
- **Not the full ~28 000-object catalogue in real time** — the screened set is
  capped (`EVENTIDE_MAX_OBJECTS`, default 250–350). Scaling to the full catalogue is
  an engineering problem (spatial hashing, GPU pairwise, incremental screening),
  not a physics one.
- **No database / accounts** — everything is computed live per session and cached
  in-process for 5 minutes.

## Known modelling limitations

- Covariance is an assumed model, not per-object derived from observation
  residuals (no SP data / Space-Track covariance ingested).
- Post-burn propagation uses the differential two-body approximation described
  above rather than re-fitting an SGP4 mean element set.
- TEME is treated as inertial for the 3-D globe (Cesium's
  `computeTemeToPseudoFixedMatrix` handles the Earth-rotation part; nutation and
  polar motion are ignored).
- The 3-D globe is capped to the selected conjunction's two objects; it is the
  optional layer — the 2-D view is the guaranteed fallback.
