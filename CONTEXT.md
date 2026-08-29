# Eventide — Project Context

> Reference document for generating a presentation. Everything about what Eventide
> is, why it exists, how it works, and what it proves.

---

## 1. One-paragraph summary

**Eventide is a live space-debris collision-avoidance dashboard that closes the
full loop from raw orbital data to a vetted avoidance maneuver.** It ingests
current two-line element sets (TLEs) from CelesTrak, propagates the catalogue with
SGP4, screens every object pair for close approaches, scores each conjunction's
probability of collision with the Foster–Estes method, and — the part almost
nothing else does — **generates candidate avoidance burns, re-propagates each one,
re-screens it against the entire catalogue, and rejects any burn that fails to
clear the risk or that creates a brand-new conjunction.** The operator sees a
risk-ranked alert list, a 2-D separation-vs-time plot, a 3-D globe of the
encounter, and — for any alert — a ranked set of safe maneuvers alongside every
rejected candidate and the exact reason it was rejected.

The name: *eventide* is the hour of dusk, when satellites catch the last sunlight
and become visible against a dark sky — the moment you look up and actually watch
what is overhead.

---

## 2. The problem — why Eventide exists

### 2.1 Orbital congestion is now an operational, daily problem

- Roughly **30,000+ objects larger than 10 cm** are tracked in Earth orbit;
  estimates run to **~1 million objects larger than 1 cm** and **>100 million
  larger than 1 mm** — any of which can disable a spacecraft.
- Low Earth orbit (LEO) is filling fast: mega-constellations (Starlink, OneWeb,
  Kuiper) add thousands of active satellites; anti-satellite (ASAT) tests
  (Fengyun-1C in 2007, Cosmos-1408 in 2021) and past accidental collisions
  (Iridium-33 / Cosmos-2251 in 2009) have left long-lived debris clouds.
- Closing speeds in LEO are **7–15 km/s**. At those speeds a 1 cm fragment carries
  the kinetic energy of a hand grenade. A collision is not a fender-bender; it is
  a cascade risk (the Kessler syndrome).

### 2.2 The decision loop today is slow and manual

- The US 18th/19th Space Defense Squadron issues **Conjunction Data Messages
  (CDMs)** to operators — typically several days before the time of closest
  approach (TCA), refined as tracking improves.
- Deciding **whether** to maneuver, and **which** maneuver, is largely a manual,
  expert-in-the-loop process: analysts weigh probability of collision against fuel
  cost, mission disruption, and — critically — whether the proposed burn puts the
  spacecraft into a *new* conjunction with something else.
- Existing tooling (NASA CARA, ESA DRAMA/CRASS, commercial services from Kayhan
  Space, Slingshot, LeoLabs) is mostly closed, subscription-gated, or focused on
  screening rather than on producing an explainable, catalogue-checked
  recommendation.

### 2.3 The gap Eventide targets

An **open, live, explainable** tool that goes end to end:

```
raw TLE  →  conjunctions  →  probability of collision  →  ranked SAFE maneuvers
                                                          + why the rest were rejected
```

The core insight: **generating an avoidance maneuver is trivial; proving it
doesn't just move the problem is the hard, valuable part.** A burn that dodges
debris A but drives you toward debris B is worse than useless. Eventide's
re-screening loop is built specifically to catch that, and to *show its work*.

---

## 3. What Eventide does — the pipeline

Three stages, matching the "Detect → Assess → Act" framing.

### Stage 1 — DETECT
Ingest TLEs → propagate with SGP4 over a configurable window (default 48 h) →
cheaply eliminate impossible pairs with a geometric prefilter → for surviving
pairs, find the true time and distance of closest approach.
**Output:** `GET /conjunctions` → a list of close approaches, each with the two
objects, the TCA, the miss distance, and the relative speed.

### Stage 2 — ASSESS
For each conjunction, project the relative geometry and the combined position
uncertainty onto the encounter plane and integrate a 2-D Gaussian over the
combined hard-body radius → probability of collision (Pc). Combine Pc with
timing urgency and closeness into a composite risk score; assign a Low/Medium/High
tier.
**Output:** the same conjunction list, now with `pc`, `risk_score`, `risk_tier`,
sorted by risk.

### Stage 3 — ACT
For a chosen conjunction and a chosen object to maneuver: generate a grid of
candidate Δv burns (radial / along-track / cross-track × several magnitudes) at a
lead time before TCA. **Re-propagate each candidate's post-burn trajectory and
re-run the full Detect+Assess pipeline against the whole catalogue.** Reject any
candidate whose residual Pc against the original threat stays too high, **or** that
creates a new conjunction with any other object. Rank the survivors by residual
risk, then Δv cost, then timing margin.
**Output:** `POST /recommend-maneuver` → ranked safe maneuvers **plus every
rejected candidate with its rejection reason**.

---

## 4. System architecture

### 4.1 Repository layout

```
eventide/
├── backend/                        FastAPI + SGP4 + NumPy/SciPy — physics & API
│   ├── app/
│   │   ├── main.py                  FastAPI app: CORS, routes, startup hook
│   │   ├── config.py                all tunable thresholds (pydantic-settings)
│   │   ├── container.py             composition root — the ONLY place concrete classes are named
│   │   ├── domain.py                plain dataclasses passed between services
│   │   ├── models.py                pydantic request/response schemas
│   │   ├── interfaces/              abstract base classes (the SOLID seams)
│   │   │   ├── tle_source.py        TLESource
│   │   │   ├── conjunction_filter.py ConjunctionFilter
│   │   │   └── risk_model.py        RiskModel
│   │   ├── services/
│   │   │   ├── tle_fetch.py         CelesTrak / File / Static TLE sources + TTL cache
│   │   │   ├── propagate.py         SGP4 wrapper, two-body propagator, apsis altitudes
│   │   │   ├── filters.py           ApsisFilter, AcceptAllFilter
│   │   │   ├── detect.py            detection pipeline orchestrator
│   │   │   ├── tca.py               shared TCA refinement + segment-minimum helper
│   │   │   ├── risk_models.py       FosterEstesModel
│   │   │   ├── assess.py            RiskAssessor — scoring, tiering, ranking
│   │   │   ├── maneuver.py          ManeuverGenerator + ManeuverPlanner (re-screen, recommend)
│   │   │   ├── scenario.py          synthetic collision-course TLE injector
│   │   │   ├── metrics_store.py     process-local metrics
│   │   │   └── synthetic_eval.py    labelled synthetic set for the recall metric
│   │   └── routes/
│   │       ├── health.py            GET /health
│   │       ├── conjunctions.py      GET /conjunctions
│   │       ├── maneuvers.py         POST /recommend-maneuver
│   │       ├── tracks.py            GET /conjunctions/{id}/separation and /geometry
│   │       └── metrics.py           GET /metrics
│   └── tests/                       27 tests, zero network access (fixture-backed)
│
└── frontend/                        React + Vite + Plotly + CesiumJS
    └── src/
        ├── api/client.js            fetch wrapper (VITE_API_BASE)
        ├── App.jsx                  layout, state, data loading
        └── components/
            ├── MetricsPanel.jsx     6 stat cards
            ├── AlertList.jsx        risk-ranked conjunction cards
            ├── ConjunctionDetail.jsx  facts + 2-D plot + maneuver panel
            ├── OrbitPlot2D.jsx      Plotly separation-vs-time (log axis)
            ├── ManeuverDetail.jsx   recommend button + accepted/rejected cards
            └── Globe3D.jsx          CesiumJS globe, orbit paths, TCA highlight
```

### 4.2 SOLID — how each principle is applied

The spec required SOLID not as polish but as the thing that lets Stage 3 plug into
Stage 1 without rewriting either. Concretely:

| Principle | Application in Eventide |
|---|---|
| **Single Responsibility** | Each service module does exactly one job. `tle_fetch` only fetches and caches. `propagate` only turns elements into state vectors. `detect` only orchestrates the detection pipeline. `assess` only scores. `maneuver` only plans. No module reaches into another's internals. |
| **Open/Closed** | `ConjunctionFilter` and `RiskModel` are **strategy interfaces**. A new prefilter (a PATH/along-track filter, an ML prefilter) is added by subclassing `ConjunctionFilter` and inserting it into the detector's filter chain — `detect.py` does not change. A new Pc method (Chan, Alfano, Monte-Carlo) is added by subclassing `RiskModel` — `assess.py` does not change. |
| **Liskov Substitution** | Enforced with ABCs, not duck typing. `AcceptAllFilter` is substituted for `ApsisFilter` **inside a test** to measure the filter's reduction rate. Any `RiskModel` drops into `RiskAssessor`. |
| **Interface Segregation** | `TLESource` exposes only `fetch()`. Caching, staleness flags, and ephemeris storage are implementation details, not interface methods — a consumer that only needs TLEs is not forced to depend on them. |
| **Dependency Inversion** | `ConjunctionDetector`, `RiskAssessor`, and `ManeuverPlanner` receive their dependencies (`TLESource`, list of `ConjunctionFilter`, `RiskModel`, `Propagator`) as constructor arguments. `app/container.py` is the single composition root that names concrete classes. This is exactly what makes the test suite possible without hitting the real CelesTrak API. |

Rule of thumb used throughout: *if you cannot unit-test a module without mocking
half the codebase, it is violating one of these.*

### 4.3 Request lifecycle

```
GET /conjunctions?window_hours=48
  → Container.get_detection(48)                         [5-minute per-window cache]
      → ConjunctionDetector.screen(48)
          → TLESource.fetch()                           [1-hour TTL, stale fallback]
          → sample evenly to max_objects
          → SGP4 propagate all objects on a 60 s grid   [vectorised sgp4_array]
          → generate all i<j pairs                      → pairs_before_filter
          → ApsisFilter chain                           → pairs_after_filter
          → segment-minimum scan (chunked, vectorised)
          → scipy refine TCA for close segments
          → drop docked/co-orbiting pairs
          → collapse synthetic to closest partner
      → RiskAssessor.assess(events)
          → FosterEstesModel.collision_probability(event) for each
          → composite score, tier, sort
  → serialise to JSON, record metrics
```

```
POST /recommend-maneuver {object_id, conjunction_id}
  → look up the conjunction in the cached detection
  → ManeuverGenerator.generate(event)                   → 30 candidates
  → ManeuverPlanner.recommend(...)
      for each candidate:
        → post_burn_state_fn: SGP4 baseline + (two-body burned − two-body unburned)
        → residual Pc vs the original threat
        → scan every other catalogue object for a NEW conjunction
        → verdict: ACCEPT / REJECT(residual) / REJECT(new conjunction)
      → sort survivors by (residual_pc, Δv magnitude, −timing_margin)
  → return recommended[] + rejected[] + stats + message
```

---

## 5. Algorithms in detail

### 5.1 SGP4 propagation (`services/propagate.py`)

- Uses the reference `sgp4` library (Vallado's implementation, Spacetrack Report
  #3 / Vallado 2006), specifically the vectorised `Satrec.sgp4_array` path.
- A **screening run** picks a common epoch (now, in UTC), builds an absolute
  Julian-date time grid, and propagates every satellite to those absolute times —
  the per-satellite TLE epoch is handled internally by SGP4.
- Output frame is **TEME** (True Equator, Mean Equinox), km and km/s.
- Objects whose SGP4 call returns an error code, produces non-finite output, or
  whose derived perigee altitude is below −50 km (decayed / garbage elements) are
  dropped before screening.
- **Verification:** `tests/test_propagate.py` checks satellite 00005 from the
  official SGP4-VER.TLE against the published `tcppver.out` position at t = 0
  (7022.46529266, −1400.08296755, 0.03995155 km) to a tolerance of 1e-4 km, and
  against the reference implementation's own output at t = 360 and 720 minutes.

### 5.2 Two-body propagator (`TwoBodyPropagator` in `propagate.py`)

- Universal-variable formulation (Vallado, Algorithm 8) with Stumpff functions
  c2(ψ), c3(ψ); handles elliptic, parabolic, and hyperbolic cases; Newton
  iteration on the universal anomaly χ.
- Seeded by a **state vector**, not a TLE — deliberately *not* a subclass of the
  `Propagator` ABC (Interface Segregation: a state-seeded propagator has a
  different contract).
- Used only for the **maneuvered object's post-burn arc**, and only differentially
  (see §5.8). Re-fitting an SGP4 mean-element set from a post-burn state would be
  the "correct" approach but is overkill for an MVP; the differential trick
  removes most of the resulting error.
- A test asserts two-body energy conservation to 1e-6 relative.

### 5.3 APSIS prefilter (`services/filters.py`, `ApsisFilter`)

- The cheapest useful filter: two objects can only conjunct if their **radial
  altitude ranges overlap**. Perigee and apogee altitude are computed from the
  TLE's mean motion and eccentricity:
  `a = (μ / n²)^(1/3)`, `perigee_alt = a(1−e) − Rₑ`, `apogee_alt = a(1+e) − Rₑ`.
- `keep_pair(a, b)` returns true iff `[perigee_a−pad, apogee_a+pad]` overlaps
  `[perigee_b−pad, apogee_b+pad]` (default pad 15 km).
- **Conservative by construction:** it ignores phasing entirely, so it can never
  drop a pair that could actually come close. It only removes pairs that are
  geometrically incapable of a close approach (different altitude shells).
- Implemented as a `ConjunctionFilter` strategy so additional sieves stack in a
  chain without touching `detect.py`.

### 5.4 Close-approach detection — the segment-minimum scan (`services/tca.py`, `detect.py`)

- Naïve approach: sample separation on a coarse grid, take the minimum. **This
  fails for fast conjunctions.** At 15 km/s relative speed and a 60 s grid, two
  objects move 900 km between samples — a sub-km encounter can sit entirely
  between two grid points, both of which show the objects hundreds of km apart.
- Eventide's fix: `segment_closest_approach(dr)`. Given relative-position samples
  `dr` of shape `(pairs, T, 3)`, for each consecutive pair of samples it computes
  the closest distance of the **straight line segment** between them to the
  origin:
  `frac = clip(−(d0·seg)/(seg·seg), 0, 1)`, `d_min = |d0 + frac·seg|`.
  Even when both endpoints are 400 km out, the segment itself may pass within
  metres of zero — and that is detected.
- Fully vectorised, run in chunks of 1200 pairs to bound memory.
- For any pair whose minimum segment distance is below the refine threshold
  (25 km), the global-minimum segment is handed to the refinement step.

### 5.5 TCA refinement (`refine_tca` in `services/tca.py`)

- Given two trajectory callables and a time bracket `[t_i − step, t_{i+1} + step]`,
  `scipy.optimize.minimize_scalar(method="bounded", xatol=1e-3)` finds the
  separation minimum.
- The trajectory callables are polymorphic: `sgp4_state_fn` for a catalogue
  object, the differential post-burn function for a maneuvered object, or an
  injected analytic function in tests (`object_state_fn` picks the right one).
- Returns TCA (seconds from run epoch), miss distance (km), and both objects'
  position and velocity at TCA.
- A **docked/co-orbiting guard** drops any refined event with miss < 20 m and
  relative speed < 20 m/s — that is a docked spacecraft or a deployment pair, not
  a collision risk.
- Per pair, only the single closest approach in the window is reported
  (`_dedupe_keep_closest`).

### 5.6 Foster–Estes 2-D probability of collision (`services/risk_models.py`, `FosterEstesModel`)

The NASA JSC (1992) short-encounter method. Steps:

1. **Relative state at TCA:** `dr = r_b − r_a`, `dv = v_b − v_a`.
2. **Conjunction-plane basis** (the "B-plane"), perpendicular to the relative
   velocity: `w = dv/|dv|`, `η = (dr × w)/|…|`, `ξ = η × w`. The 2×3 projection
   matrix is `M = [ξ; η]`.
3. **Combined covariance:** `C = C_a + C_b`. Each object's covariance is
   `R_RTN · diag(σ_r², σ_t², σ_n²) · R_RTNᵀ`, where `R_RTN` rotates a
   radial/in-track/cross-track vector into the inertial frame the state is
   expressed in. The **along-track** sigma grows linearly with time to TCA
   (`σ_t = σ_t0 + growth · t_TCA_hours`) — a representative model of how
   propagated TLE error accumulates.
4. **Project to 2-D:** `cov2 = M · C · Mᵀ` (2×2), `miss2 = M · dr` (2-vector).
5. **Diagonalise** `cov2` → eigenvalues σx², σy²; rotate `miss2` into the
   eigenframe → (mx, my).
6. **Integrate** the 2-D Gaussian over a disk of radius = **combined hard-body
   radius** (default 2 × 5 m = 10 m), on a polar grid (60 radial × 120 angular):
   `Pc = Σ exp(−½[((r cosθ − mx)/σx)² + ((r sinθ − my)/σy)²]) · r · Δr · Δθ / (2π σx σy)`.

Properties enforced by tests:
- **Monotonic:** holding covariance and relative geometry fixed, smaller miss
  distance never yields smaller Pc.
- **Bounded** to [0, 1]; a direct hit with a large hard-body radius gives Pc > 1e-3;
  a 500 km miss gives Pc < 1e-6.

**Covariance choice matters and is deliberate.** TLE-derived state uncertainty is
km-scale and along-track-dominated — nothing like the sub-100 m uncertainty of a
precise GPS ephemeris. Defaults: σ_radial 500 m, σ_in-track 2000 m (+120 m/hour),
σ_cross-track 1000 m. These are intentionally conservative (large) so the model
does not understate risk — the spec's high-recall requirement.

### 5.7 Risk scoring and tiering (`services/assess.py`, `RiskAssessor`)

- **Composite score** (0–1):
  `score = 0.7 · pc_component + 0.2 · urgency + 0.1 · closeness`
  - `pc_component = clamp((log10(Pc) + 9) / 9, 0, 1)` — maps Pc 1e-9 → 0, 1e0 → 1.
  - `urgency = clamp(1 − t_TCA_hours / window_hours, 0, 1)` — sooner is more urgent.
  - `closeness = clamp(1 − miss_km / 10, 0, 1)`.
- **Tier:**
  - `Pc ≥ 1e-5` → **High** (a crewed-asset posture; many operators escalate
    crewed conjunctions at 1e-5 rather than the 1e-4 used for routine robotic
    assets).
  - `Pc ≥ 1e-7` → **Medium**.
  - otherwise `score ≥ 0.5` → **Medium** (very close geometry still warrants
    attention even at low modelled Pc).
  - else **Low**.
- Events are returned sorted by score, descending.

### 5.8 Maneuver generation (`services/maneuver.py`, `ManeuverGenerator`)

- Grid: **6 directions** (±radial, ±along-track, ±cross-track) × **5 magnitudes**
  ({0.02, 0.05, 0.1, 0.2, 0.5} m/s) = **30 candidates**.
- Burn time: `max(0, t_TCA − lead_hours · 3600)`, default lead 12 h.
- Along-track burns are by far the most fuel-efficient way to change arrival
  timing (and thus miss distance); the grid includes radial and cross-track so the
  re-screening can demonstrate rejecting the inefficient / unsafe ones.

### 5.9 Differential post-burn propagation (`ManeuverPlanner.post_burn_state_fn`)

The modelling problem: the catalogue is on SGP4; the post-burn arc would naturally
be on two-body; comparing a two-body trajectory against SGP4 over ~27 hours
introduces kilometres of spurious drift that can both **mask** a real residual
risk and **fabricate** a fake new conjunction.

The fix — a **differential** model:

```
state(t) = SGP4_baseline(t) + [ twobody(r0, v0 + Δv, t) − twobody(r0, v0, t) ]
```

for `t > t_burn` (and just the SGP4 baseline before the burn). The two large,
error-prone two-body integrations **cancel** in the difference, leaving only the
small, accurate *delta* the burn actually produces. Consequences:

- A zero Δv reproduces the SGP4 baseline **exactly** → a null "maneuver" correctly
  shows residual Pc = baseline and is rejected.
- A real burn is tracked accurately across the whole screening window.

This is a standard linearised-maneuver technique; it is documented as a modelling
simplification (the "correct" alternative is re-fitting SGP4 mean elements).

### 5.10 Re-screening loop (`ManeuverPlanner.re_screen`)

For one candidate:

1. Get the maneuvered object's state at burn time; apply Δv in the RTN frame
   (`v0_new = v0 + R_RTN · Δv`).
2. Build the post-burn position arc over the coarse grid (differential model).
3. **Residual Pc** against the original threat: segment-minimum scan → refine →
   Foster–Estes. This is the number that tells you whether the burn *worked*.
4. **New-conjunction scan:** for every other object in the catalogue —
   - Skip it if its *pre-burn* minimum gap to the maneuvered object was already
     below the refine threshold (co-orbiting neighbour, docked craft, or a
     pre-existing conjunction — a burn cannot be blamed for those).
   - Otherwise run the segment-minimum scan on the *post-burn* arc; if a refined
     approach comes within the report threshold and its Foster–Estes Pc is at or
     above the reject threshold (1e-6), record it as a newly created conjunction
     with full detail (object, TCA, miss, Pc).
5. **Verdict:**
   - residual Pc ≥ reject threshold → **REJECT**, reason cites residual Pc and the
     baseline.
   - else if any new conjunction → **REJECT**, reason names the worst new
     conjunction (object, miss, Pc).
   - else → **ACCEPT**.
6. `timing_margin_hours = burn_time / 3600` (how much lead time the operator has).

### 5.11 Recommendation and ranking (`ManeuverPlanner.recommend`)

- Re-screen all 30 candidates, timing the whole batch.
- Accepted candidates are sorted by **(residual Pc ascending, Δv magnitude
  ascending, timing margin descending)** — safest first, then cheapest, then most
  lead time.
- Returns: recommended list, full rejected list (with reasons), and stats
  (candidates generated, candidates rejected, rejection rate, seconds per
  candidate). If nothing survives, the message is an explicit
  "NO SAFE CANDIDATE FOUND".

### 5.12 Synthetic conjunction injection (`services/scenario.py`)

**Why it exists:** a genuinely dangerous (<1 km, high-Pc) conjunction inside a
48-hour window is rare in any few-hundred-object sample. The maneuver-rejection
demo — the whole pitch — needs a guaranteed, dramatic scenario every time.

**How it works:**

1. Pick a target from the live catalogue (ISS by default, or a name hint, or the
   first object).
2. Build a synthetic debris TLE that keeps the target's **altitude** (same mean
   motion, same eccentricity) but sits in a **steeply different orbit plane**
   (inclination offset +70°). Two circular orbits at the same altitude in
   different planes intersect twice per revolution; the closing speed at the
   crossing is `2 · v_orbital · sin(Δi/2)` ≈ 15 km/s here — a realistic
   hypervelocity conjunction.
3. Search RAAN offset (24 points) × mean-anomaly offset (36 points), evaluating
   the minimum separation over the window with a 4-stage adaptive time refinement,
   then a shrinking local grid (up to 6 iterations) until the miss distance is
   below the target (0.3 km).
4. Reformat TLE line 2 with the perturbed elements and a **recomputed checksum**.
5. `ScenarioInjectingTLESource` decorates the real `TLESource`, builds the
   scenario once, caches it, and appends the synthetic TLE (NORAD **99001**) to
   every fetch.

**Honesty:** every conjunction involving NORAD 99001 is flagged `synthetic: true`
in the API and labelled `SYNTHETIC` in the UI. Typical result: ~0.65 km miss,
~15 km/s closing speed, TCA ~27 h out, Pc ~3e-5 → **High** tier. The scenario is
disabled with `EVENTIDE_DEMO_INJECT_SCENARIO=false` for a pure real-data run.

### 5.13 TLE ingest and caching (`services/tle_fetch.py`)

- `CelesTrakTLESource` fetches one or more CelesTrak **GP groups**
  (`https://celestrak.org/NORAD/elements/gp.php?GROUP=<g>&FORMAT=tle`), merges and
  de-duplicates by NORAD id.
- **TTL cache** (monotonic clock, default 1 hour) so a live `/conjunctions` call
  does not re-fetch every time.
- **Stale-cache fallback:** on any network/parse error, if a previous cache
  exists it is served with `served_stale = true` and `last_error` set (surfaced
  on `/health` and in the UI status bar). Only if there is no cache at all does
  the error propagate. This is the "don't fail silently" requirement.
- `StaticTLESource` and `FileTLESource` exist for tests and offline runs.
- `parse_tle_text` handles both 2-line and 3-line (named) TLE formats.

---

## 6. API surface

Base: FastAPI, OpenAPI docs at `/docs`.

| Endpoint | Purpose | Key response fields |
|---|---|---|
| `GET /health` | liveness + TLE source status | `status`, `service`, `tle_source_error`, `tle_served_stale` |
| `GET /conjunctions?window_hours=48&refresh=false` | run/return the detection+assessment | `epoch`, `object_count`, `pairs_before_filter`, `pairs_after_filter`, `prefilter_reduction_rate`, `screening_latency_s`, `conjunctions[]` |
| `POST /recommend-maneuver` `{object_id, conjunction_id}` | generate + re-screen + rank maneuvers | `baseline_pc`, `candidates_generated`, `candidates_rejected`, `rejection_rate`, `rescreen_s_per_candidate`, `recommended[]`, `rejected[]`, `message` |
| `GET /conjunctions/{id}/separation` | 2-D plot data | `times_hours[]`, `separation_km[]`, `tca_hours`, `miss_distance_km` (trimmed to ±6 h around TCA) |
| `GET /conjunctions/{id}/geometry?points=240` | 3-D globe data | `epoch`, `times_hours[]`, `object_a.path_km[]`, `object_b.path_km[]`, `tca_index`, `tca_point_a_km`, `tca_point_b_km` |
| `GET /metrics` | live metrics snapshot | see §7 |
| `GET /` | service banner | `service`, `docs` |

Each conjunction object: `conjunction_id` (e.g. `"25544-99001"`, the sorted NORAD
pair), `object_a` / `object_b` (`{norad_id, name}`), `tca` (ISO 8601 UTC),
`tca_hours_from_now`, `miss_distance_km`, `rel_speed_km_s`, `pc`, `risk_score`,
`risk_tier`, `synthetic`.

Each maneuver object (`ManeuverOut`): `dv_rtn_mps` (3-vector), `dv_magnitude_mps`,
`burn_time` (ISO), `timing_margin_hours`, `accepted`, `rejection_reason`,
`residual_pc`, `new_conjunctions[]` (`{object_id, object_name, tca_hours,
miss_distance_km, pc}`).

---

## 7. Metrics — what each proves

`GET /metrics` returns a flat snapshot, rendered as a 6-card strip in the UI.
This is the "show, don't tell" moment — every number is generated by the running
system, not a slide.

| Metric | What it proves | How it's computed |
|---|---|---|
| `prefilter_reduction_rate` | the scalability claim is real, not just cited | `1 − pairs_after_filter / pairs_before_filter`, logged on every `/conjunctions` call |
| `end_to_end_screening_latency_s` | feasible on standard hardware | wall-clock of a full `/conjunctions` call at the current object-set size |
| `false_negative_rate_synthetic` | the high-recall safety claim is real | a 78-case labelled synthetic set (miss 0.05–15 km × 3 relative speeds; "dangerous" = miss ≤ 1 km) is run at startup; every dangerous case must score above the medium Pc threshold. **Result: 0%.** |
| `maneuver_rejection_rate` | the core differentiator actually does something | `candidates_rejected / candidates_generated` per recommendation request |
| `rescreen_latency_s_per_candidate` | re-screening is cheap enough to run for every candidate | wall-clock of the candidate batch / number of candidates |
| `live_catalog_objects`, `pairs_before/after_filter` | real scale, not the paper's numbers | current run counts |

**On the prefilter reduction rate:** the literature figure (~62%, Stevenson et
al. 2023) is for a full multi-shell catalogue. Eventide's default object set is
deliberately debris-cloud-heavy (Fengyun-1C, Iridium-33, Cosmos-2251, Cosmos-1408)
— those clouds sit in a narrow altitude band, so the APSIS filter has less it can
legitimately remove (~30–45% observed). Widening `EVENTIDE_TLE_GROUPS` to span
more altitude shells raises the rate. The mechanism is identical; only the input
distribution differs. This is stated openly rather than tuned to hit a target.

---

## 8. Representative results (from an actual run)

Configuration: 250 objects, 48-hour window, groups = stations + Cosmos-2251 +
Iridium-33 + Cosmos-1408 + Fengyun-1C debris, scenario injection on.

- **Detection:** 250 objects, 19,900 pairs before filter, ~13,400 after
  (reduction ~0.32), **~10 s** cold screening latency, **28 conjunctions** found.
- **Top alert (synthetic):** `ISS (ZARYA) ↔ SYNTHETIC DEBRIS 99001`, miss
  **0.654 km**, relative speed **15.3 km/s**, TCA **+27.1 h**, Pc **3.17e-5**,
  tier **High**.
- **Real conjunctions detected:** multiple `FENGYUN 1C DEB ↔ FENGYUN 1C DEB`,
  `IRIDIUM 33 DEB ↔ FENGYUN 1C DEB` approaches at 1.5–4 km miss and 7–15 km/s,
  Pc 1e-7 to 9e-6, tiers Medium/Low — real debris-on-debris close approaches.
- **Maneuver recommendation** (maneuver the ISS to avoid the synthetic debris):
  - **30 candidates generated, 27 rejected (90% rejection rate)**, ~0.1 s per
    candidate re-screen.
  - Rejected examples: small radial burns (`+0.02 R`, `+0.05 R`) — "residual Pc
    3.10e-05 still above reject threshold 1e-06".
  - **Recommended (best):** `−0.5 m/s along-track`, residual Pc **~7e-16**,
    15.2 h of timing margin. A tiny retrograde nudge 12 hours out moves the
    station kilometres clear by TCA.
- **Recall metric:** false-negative rate **0.0%** over 78 synthetic cases.
- **SGP4 accuracy:** matches the published Vallado test vector to < 1e-4 km.

---

## 9. Frontend

- **Stack:** React 18, Vite 5, `vite-plugin-cesium`, `plotly.js-dist-min`.
  CesiumJS is served as an external bundle with **Natural Earth II imagery bundled
  offline** — no Cesium Ion token required.
- **`App.jsx`** — two-column layout. Loads `/health` and `/conjunctions` (48 h) on
  mount; selecting an alert fetches its `/geometry`; the maneuver panel refreshes
  `/metrics` after a recommendation. Health dot reflects backend reachability and
  TLE staleness.
- **`MetricsPanel`** — 6 stat cards bound to `/metrics`.
- **`AlertList`** — risk-ranked cards: object names, tier badge, `SYNTHETIC`
  badge, miss distance, relative speed, time to TCA, Pc. Refresh button forces a
  re-screen (`?refresh=true`).
- **`ConjunctionDetail`** — key/value facts (miss, relative speed, TCA, Pc, score,
  NORAD ids) + the 2-D plot + the maneuver panel.
- **`OrbitPlot2D`** — Plotly line chart of separation vs. time on a **log y-axis**,
  with the TCA marked and annotated with the miss distance. Trimmed to ±6 h around
  TCA.
- **`ManeuverDetail`** — dropdown to choose which object of the pair to maneuver,
  a "Recommend avoidance maneuver" button, then: the summary message, the stats
  line, recommended cards (green left border), and rejected cards (red left
  border) showing Δv, burn time, lead time, residual Pc, and — the explainability
  payload — the exact rejection reason and any newly created conjunctions. First 3
  rejected shown, expandable to all.
- **`Globe3D`** — CesiumJS viewer. Converts each TEME path sample to Earth-fixed
  coordinates via `Cesium.Transforms.computeTemeToPseudoFixedMatrix` (handles the
  Earth-rotation part; nutation and polar motion are ignored). Draws both orbit
  paths (blue for A, red for B), point markers with labels at TCA, and a
  translucent yellow sphere at the conjunction point, then flies the camera to
  frame it.

The 3-D globe is the **optional layer**. If Cesium misbehaves in a given browser,
the 2-D view is a complete, self-sufficient fallback — a deliberate design choice
per the spec.

---

## 10. Testing strategy

27 tests, **zero network access** (all run against
`tests/fixtures/sample_tles.txt`, ~607 real TLEs saved once).

| File | Covers |
|---|---|
| `test_propagate.py` | SGP4 vs Vallado sat 00005 at t = 0 / 360 / 720 min; apsis altitude sanity; two-body energy conservation |
| `test_filters.py` | ApsisFilter: overlapping bands kept, disjoint bands dropped, pad widens the band, eccentric orbit crossing a circular one kept, symmetry, AcceptAll substitution (Liskov) |
| `test_risk_models.py` | Pc monotonic in miss distance; Pc bounded [0,1]; direct hit → high Pc; **high-recall: 0 false negatives** on a labelled synthetic set |
| `test_detect_integration.py` | non-empty, sane result on the fixture catalogue; ApsisFilter reduces pair count vs AcceptAll by > 15%; deterministic output for a fixed epoch |
| `test_maneuver.py` | the pipeline produces a dangerous synthetic conjunction; re-screen **rejects a null maneuver** (reason cites residual Pc); re-screen **accepts a large safe burn**; re-screen **rejects a burn that creates a new conjunction** (via an injected shadow object on the post-burn path); `recommend` ranks survivors and reports a valid rejection rate |
| `test_api.py` | `/health`; `/conjunctions` (synthetic flagged, sane counts); `/recommend-maneuver` shows ≥ 1 rejected candidate with a reason; unknown `conjunction_id` → 404; `/metrics` returns real numbers |

The maneuver tests are the most thorough by design — that stage is the
differentiator, and the spec's line was "if this doesn't demonstrably reject a bad
maneuver live in the demo, the whole pitch falls flat."

---

## 11. Configuration (all via `EVENTIDE_*` env vars or `.env`)

| Setting | Default | Meaning |
|---|---|---|
| `tle_groups` | stations, cosmos-2251-debris, iridium-33-debris, cosmos-1408-debris, fengyun-1c-debris | CelesTrak GP groups to screen |
| `tle_cache_ttl_s` | 3600 | TLE re-fetch interval |
| `max_objects` | 350 (250 on the deployed instance) | screened-set cap (keeps a cold call interactive) |
| `default_window_hours` | 48 | propagation / screening horizon |
| `coarse_step_s` | 60 | propagation grid step |
| `refine_threshold_km` | 25 | segment min below which a pair is refined |
| `report_threshold_km` | 10 | refined miss below which a conjunction is reported |
| `apsis_pad_km` | 15 | altitude-band pad in the APSIS filter |
| `sigma_radial_m` / `sigma_intrack_m` / `sigma_crosstrack_m` | 500 / 2000 / 1000 | per-object 1-σ position uncertainty (RTN) |
| `intrack_growth_m_per_hour` | 120 | along-track σ growth with time to TCA |
| `hard_body_radius_m` | 5 | per-object radius (combined HBR = 10 m) |
| `pc_high` / `pc_medium` | 1e-5 / 1e-7 | risk-tier cut points |
| `maneuver_dv_grid_mps` | 0.02, 0.05, 0.1, 0.2, 0.5 | Δv magnitudes |
| `maneuver_lead_hours` | 12 | burn lead time before TCA |
| `maneuver_pc_reject` | 1e-6 | residual/new-conjunction Pc that triggers rejection |
| `demo_inject_scenario` | true | inject the synthetic conjunction |

---

## 12. Deployment

- **Backend → Render** (`backend/render.yaml` blueprint) or Railway / Fly / any
  `uvicorn app.main:app` host (`Procfile` included). Health check `/health`.
  Set `EVENTIDE_CORS_ORIGINS` to the frontend origin (JSON array). Python 3.12
  pinned via `runtime.txt`.
- **Frontend → Vercel or Netlify** (`vercel.json` / `netlify.toml` included, SPA
  rewrites configured). Set `VITE_API_BASE` to the backend URL.
- CORS also allows any `*.vercel.app` / `*.netlify.app` origin by regex for
  preview deploys.
- No database. Everything is computed live per session and cached in-process
  (TLEs 1 h, detection results 5 min per window).

---

## 13. Explicitly out of scope for the MVP

- **No trained ML ranking model.** The composite `risk_score` is a transparent
  heuristic (log-Pc + urgency + closeness). A scikit-learn / LightGBM learning-to-
  rank layer is a documented extension; it would only ever re-order alerts, never
  gate a safety decision.
- **Not the full ~30,000-object catalogue in real time.** The screened set is
  capped. Scaling to the full catalogue is an **engineering** problem (spatial
  hashing / sort-and-sweep broad phase, GPU pairwise propagation, incremental
  screening as new TLEs arrive), **not a physics** problem — the algorithms are
  unchanged.
- **No user accounts or persistence.**

## 14. Known modelling limitations (stated openly)

- **Covariance is assumed, not derived.** No special-perturbations (SP) data or
  Space-Track covariance is ingested; the RTN sigma model is a representative
  stand-in for propagated TLE error.
- **Post-burn propagation is a differential two-body approximation**, not a
  re-fitted SGP4 mean-element set. The differential trick cancels most of the
  error, but a long-arc, high-eccentricity case would still be approximate.
- **Frame handling for the 3-D view** treats TEME as inertial and uses only the
  Earth-rotation (GMST) part of the TEME→ECEF transform; nutation and polar motion
  are ignored. Immaterial at globe-view scale.
- **One close approach per pair per window** is reported (the closest); a pair
  with two distinct encounters in 48 h shows only the worse one.

## 15. Roadmap / extensions

- Ingest real CDMs and Space-Track SP covariance; replace the assumed RTN model.
- Add a `PathFilter` (along-track/nodal) as a second prefilter stage — drops in
  behind the existing `ConjunctionFilter` interface with no other changes.
- Add alternative Pc models (Chan analytic, Alfano, Monte-Carlo) behind the
  `RiskModel` interface; let the operator compare.
- Fuel-budget-aware maneuver ranking; multi-burn and finite-burn modelling.
- Broad-phase spatial indexing to scale screening to the full catalogue.
- Learning-to-rank alert prioritisation (prioritisation only — never a gate).
- Historical replay mode (feed archived TLEs, replay a known event such as the
  2009 Iridium–Cosmos collision).

---

## 16. The demo narrative (for the presentation)

1. **Open the deployed link cold.** The alert list populates with real, current
   conjunction data — debris-on-debris close approaches happening in the next two
   days.
2. **Point at the metrics strip.** Real numbers from the running system: objects
   screened, pairs evaluated, prefilter reduction, screening latency, 0% false-
   negative rate.
3. **Select the top (High) alert** — ISS vs. a debris object, sub-kilometre miss,
   15 km/s closing speed. The 2-D plot shows the separation collapsing to the
   miss distance at TCA; the 3-D globe highlights the crossing.
4. **Click "Recommend avoidance maneuver."** The system generates 30 candidate
   burns and re-screens every one against the whole catalogue.
5. **The payoff:** most candidates come back **rejected**, each with a reason —
   "residual Pc still too high", or "creates a new conjunction with [object] at
   [miss] km". A handful are **recommended**, ranked, with the residual risk, the
   Δv cost, and how many hours of lead time remain.
6. **The point:** anyone can compute a probability of collision. Eventide tells
   you what to *do* about it — and proves the fix doesn't just move the problem.
