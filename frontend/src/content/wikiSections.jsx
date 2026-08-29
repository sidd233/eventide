import LiveMetrics from "../components/LiveMetrics";

export function Formula({ children }) {
  return <div className="formula">{children}</div>;
}

export function Callout({ children, kind }) {
  return <div className={`callout ${kind || ""}`}>{children}</div>;
}

export function Table({ head, rows }) {
  return (
    <div className="wiki-table-wrap">
      <table>
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const M = ({ children }) => <span className="mono">{children}</span>;

/* Flat list. `level` 2 → sidebar heading, 3 → indented sub-entry. */
export const sections = [
  /* ------------------------------------------------------------------ */
  {
    id: "overview",
    title: "Overview",
    level: 2,
    body: (
      <>
        <p>
          <strong>Eventide</strong> is a live space-debris collision-avoidance dashboard. It
          takes the same raw orbital data that satellite operators work from, screens the
          catalogue for close approaches over the next two days, scores how likely each one is
          to be a collision, and — the part that sets it apart — <strong>generates candidate
          avoidance maneuvers, re-simulates each one against the whole catalogue, and rejects
          any burn that fails to clear the risk or that creates a brand-new close
          approach.</strong>
        </p>
        <p>The pipeline has three stages, framed as “Detect → Assess → Act”:</p>
        <Table
          head={["Stage", "Question it answers", "Output"]}
          rows={[
            ["Detect", "What is going to pass close to what, and exactly when?", "A ranked list of conjunctions with a refined time and distance of closest approach"],
            ["Assess", "How dangerous is each one?", "A probability of collision, a composite risk score, and a Low / Medium / High tier"],
            ["Act", "What should we do about it, and does the fix actually work?", "Ranked safe maneuvers plus every rejected candidate and the exact reason it was rejected"],
          ]}
        />
        <Callout>
          The thesis: <strong>computing a probability of collision is easy; proving that a
          proposed fix does not simply move the problem somewhere else is the hard, valuable
          part.</strong> A burn that dodges debris A but drives you toward debris B is worse
          than useless. Eventide’s re-screening loop exists to catch exactly that, and to show
          its work.
        </Callout>
      </>
    ),
  },
  {
    id: "how-to-read",
    title: "Using the dashboard",
    level: 2,
    body: (
      <>
        <ul>
          <li>
            <strong>Alert list (left).</strong> Every detected conjunction, ranked by risk.
            Each row shows the two objects, the risk tier, and the miss distance. Use “Focus on
            an object…” to narrow the list to conjunctions involving a single satellite or
            debris fragment.
          </li>
          <li>
            <strong>3-D globe (top).</strong> The selected encounter — both orbit tracks, a
            marker on each object at closest approach, and a translucent sphere at the
            conjunction point.
          </li>
          <li>
            <strong>Separation plot.</strong> Distance between the two objects versus time, log
            scale, centred on closest approach. See{" "}
            <a href="#stage1-segmin">the segment-minimum scan</a> for why the curve is
            re-sampled near TCA.
          </li>
          <li>
            <strong>Maneuver panel.</strong> Pick which object to maneuver, then “Recommend
            avoidance maneuver”. The system generates 30 candidate burns, re-screens each, and
            returns the safe ones ranked — alongside every rejected candidate and its reason.
          </li>
          <li>
            <strong>Recompute (header).</strong> Drops the cached element sets, pulls fresh
            data, and re-runs the entire pipeline against a new epoch.
          </li>
        </ul>
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "prereqs",
    title: "Background you need first",
    level: 2,
    body: (
      <p>
        The rest of this page assumes a handful of orbital-mechanics concepts. This section
        builds them up from scratch; skip ahead if they are already familiar.
      </p>
    ),
  },
  {
    id: "prereq-orbits",
    title: "Orbits, LEO, and why congestion is a problem",
    level: 3,
    body: (
      <>
        <p>
          A satellite in orbit is in continuous free fall: its sideways speed is large enough
          that the ground curves away beneath it as fast as it falls. <strong>Low Earth
          Orbit (LEO)</strong> runs from roughly 200 km to 2 000 km altitude; a circular orbit
          at ~500 km completes one revolution in about 95 minutes at ~7.6 km/s.
        </p>
        <ul>
          <li>
            Around <strong>30 000+ objects larger than 10 cm</strong> are tracked; estimates
            run to ~1 million larger than 1 cm and far more below that. Any of them can
            disable a spacecraft.
          </li>
          <li>
            Closing speeds in LEO are <strong>7–15 km/s</strong>. At those speeds a 1 cm
            fragment carries the kinetic energy of a hand grenade.
          </li>
          <li>
            Debris begets debris: a collision produces thousands of new fragments, each of
            which is itself a collision hazard — the runaway feedback known as the{" "}
            <strong>Kessler syndrome</strong>. Real long-lived clouds already exist from the
            2007 Fengyun-1C anti-satellite test, the 2009 Iridium-33 / Cosmos-2251 collision,
            and the 2021 Cosmos-1408 test.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "prereq-elements",
    title: "Orbital elements and the TLE format",
    level: 3,
    body: (
      <>
        <p>
          An orbit is described by six numbers. Loosely: <strong>semi-major axis</strong>
          (size), <strong>eccentricity</strong> (how elliptical), <strong>inclination</strong>
          (tilt of the orbit plane relative to the equator), <strong>right ascension of the
          ascending node / RAAN</strong> (where the plane crosses the equator going north),
          <strong> argument of perigee</strong> (orientation of the ellipse within the plane),
          and <strong>mean anomaly</strong> (where along the orbit the object is at a reference
          time). Plus an <strong>epoch</strong> — the timestamp those numbers are valid for.
        </p>
        <p>
          The public distribution format for these is the <strong>Two-Line Element set
          (TLE)</strong> — a fixed-column ASCII record, optionally preceded by a name line:
        </p>
        <pre>{`ISS (ZARYA)
1 25544U 98067A   24179.51782528  .00016717  00000-0  30074-3 0  9993
2 25544  51.6400 247.4627 0006703 130.5360 325.0288 15.50120940 12345`}</pre>
        <Table
          head={["Field", "Where", "Meaning"]}
          rows={[
            ["Catalogue number", "line 1, cols 3–7", <>NORAD ID, e.g. <M>25544</M> for the ISS</>],
            ["Epoch", "line 1, cols 19–32", "Two-digit year + fractional day-of-year the elements are valid for"],
            ["Ballistic coeff. / drag", "line 1", <>First derivative of mean motion and the <M>B*</M> drag term</>],
            ["Inclination", "line 2, cols 9–16", "degrees"],
            ["RAAN", "line 2, cols 18–25", "degrees"],
            ["Eccentricity", "line 2, cols 27–33", <>implied leading decimal — <M>0006703</M> means 0.0006703</>],
            ["Argument of perigee", "line 2, cols 35–42", "degrees"],
            ["Mean anomaly", "line 2, cols 44–51", "degrees"],
            ["Mean motion", "line 2, cols 53–63", <>revolutions per day (this project reads it as <M>no_kozai</M>, the SGP4 “Kozai” mean motion)</>],
            ["Rev number + checksum", "line 2, cols 64–68", "revolution count at epoch, then a mod-10 checksum digit"],
          ]}
        />
        <p>
          Eventide fetches these as <strong>GP (General Perturbations)</strong> element sets
          from CelesTrak — the modern name for the same data, published so it feeds directly
          into the SGP4 propagator below. Perigee and apogee <em>altitude</em> are not stored
          directly; the project derives them from mean motion <M>n</M> and eccentricity{" "}
          <M>e</M>:
        </p>
        <Formula>
          a = (μ / n²)^(1/3)   ·   perigee_alt = a(1 − e) − Rₑ   ·   apogee_alt = a(1 + e) − Rₑ
        </Formula>
        <p>
          with <M>μ = 398 600.4418 km³/s²</M> (Earth’s gravitational parameter) and{" "}
          <M>Rₑ = 6 378.137 km</M>.
        </p>
      </>
    ),
  },
  {
    id: "prereq-frames",
    title: "Reference frames: TEME, RTN, ECEF",
    level: 3,
    body: (
      <>
        <ul>
          <li>
            <strong>TEME (True Equator, Mean Equinox)</strong> — the quasi-inertial frame SGP4
            outputs. Positions and velocities in this project are in TEME, kilometres and
            km/s, unless stated otherwise.
          </li>
          <li>
            <strong>RTN (Radial, Transverse, Normal)</strong>, also called RIC — a frame that
            travels with a spacecraft: <em>R</em> points away from Earth, <em>N</em> is along
            the orbital angular momentum, <em>T</em> completes the set (roughly the direction
            of travel). Position uncertainty and maneuver directions are naturally expressed
            here. The basis vectors are{" "}
            <M>r̂ = r/|r|</M>, <M>n̂ = (r×v)/|r×v|</M>, <M>t̂ = n̂ × r̂</M>.
          </li>
          <li>
            <strong>ECEF (Earth-Centred, Earth-Fixed)</strong> — rotates with the planet; used
            only to place orbit tracks on the 3-D globe. Eventide converts TEME → ECEF with
            the Earth-rotation (GMST) term only; nutation and polar motion are ignored, which
            is immaterial at globe-view scale.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "prereq-sgp4",
    title: "What SGP4 is",
    level: 3,
    body: (
      <>
        <p>
          <strong>SGP4 (Simplified General Perturbations 4)</strong> is the analytic orbit
          propagator that TLE/GP data is built for. Given an element set and a target time it
          returns a position and velocity, accounting for the dominant perturbations — Earth’s
          oblateness and atmospheric drag — with an empirical model rather than a numerical
          integration. It is fast (microseconds per evaluation, vectorisable) and its accuracy
          is roughly <strong>1–3 km at epoch, degrading to tens of kilometres over a few
          days</strong>. That error budget is precisely why the risk model below uses a
          kilometre-scale, along-track-dominated uncertainty.
        </p>
        <p>
          Eventide uses the reference <M>sgp4</M> library (Vallado’s implementation,
          Spacetrack Report #3 / Vallado 2006) and verifies it in the test suite against the
          published test vector for satellite 00005 to under <M>1e-4 km</M>.
        </p>
      </>
    ),
  },
  {
    id: "prereq-conjunction",
    title: "Conjunctions, TCA, miss distance, relative velocity",
    level: 3,
    body: (
      <>
        <ul>
          <li>
            <strong>Conjunction</strong> — a predicted close approach between two catalogued
            objects.
          </li>
          <li>
            <strong>TCA (Time of Closest Approach)</strong> — the instant the separation
            between the two objects is smallest.
          </li>
          <li>
            <strong>Miss distance</strong> — that smallest separation. Sub-kilometre miss
            distances at LEO closing speeds are the ones operators worry about.
          </li>
          <li>
            <strong>Relative velocity</strong> — the vector difference of the two velocities at
            TCA; its magnitude is the closing speed. For crossing orbits in different planes it
            is <M>≈ 2·v_orbital·sin(Δi/2)</M>, which reaches ~15 km/s for a 70° plane
            difference.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "prereq-pc",
    title: "Probability of collision, the B-plane, hard-body radius, covariance",
    level: 3,
    body: (
      <>
        <p>
          Neither object’s position is known exactly. The <strong>probability of collision
          (Pc)</strong> combines the predicted miss with those uncertainties:
        </p>
        <ul>
          <li>
            <strong>Position covariance</strong> — a 3×3 matrix describing the error ellipsoid
            around each predicted position. Combined for the pair, it defines how “fuzzy” the
            encounter is.
          </li>
          <li>
            <strong>Conjunction plane / B-plane</strong> — the plane perpendicular to the
            relative velocity at TCA. For a fast (“short”) encounter the two objects sweep past
            each other almost in a straight line, so the whole 3-D problem collapses onto this
            2-D plane.
          </li>
          <li>
            <strong>Hard-body radius (HBR)</strong> — the two objects are modelled as spheres;
            the combined HBR is the sum of their radii. A collision is “the projected miss
            lands within the combined HBR”.
          </li>
        </ul>
        <p>
          Pc is then the integral of the 2-D Gaussian (mean = projected miss vector, spread =
          projected combined covariance) over a disk of radius = combined HBR. Bigger miss,
          smaller covariance, or smaller objects all drive Pc down.
        </p>
      </>
    ),
  },
  {
    id: "prereq-dv",
    title: "Δv and burn directions",
    level: 3,
    body: (
      <>
        <p>
          A maneuver is a change in velocity, <strong>Δv</strong>, measured in metres per
          second; the fuel cost scales with its magnitude. Directions are given in the RTN
          frame:
        </p>
        <ul>
          <li>
            <strong>Along-track (±T)</strong> — speeds the object up or slows it down. This is
            by far the most efficient way to change <em>when</em> the object arrives at a given
            point, and therefore where it is at the original TCA. A fraction of a m/s a
            day ahead moves a spacecraft kilometres.
          </li>
          <li>
            <strong>Radial (±R)</strong> — raises/lowers the orbit locally; changes phasing
            far less efficiently.
          </li>
          <li>
            <strong>Cross-track (±N)</strong> — tilts the orbit plane; expensive, occasionally
            the only geometry that helps.
          </li>
        </ul>
        <p>
          Eventide’s grid includes all three so the re-screening step can visibly reject the
          inefficient and unsafe options.
        </p>
      </>
    ),
  },
  {
    id: "prereq-context",
    title: "The operational context: CDMs, screening services, why open matters",
    level: 3,
    body: (
      <>
        <p>
          Today the US 18th/19th Space Defense Squadron issues{" "}
          <strong>Conjunction Data Messages (CDMs)</strong> to operators, typically a few days
          before TCA and refined as tracking improves. Deciding <em>whether</em> to maneuver
          and <em>which</em> maneuver is largely a manual, expert-in-the-loop process — weigh
          Pc against fuel, mission disruption, and whether the burn creates a new conjunction.
          Existing tooling (NASA CARA, ESA DRAMA/CRASS, commercial services from Kayhan Space,
          Slingshot, LeoLabs) is mostly closed, subscription-gated, or focused on screening
          rather than on producing an explainable, catalogue-checked recommendation. Eventide
          targets the open, live, end-to-end version of that loop.
        </p>
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "data-sources",
    title: "Where the data comes from",
    level: 2,
    body: (
      <>
        <p>
          The alert list is <strong>real</strong>: current element sets from CelesTrak, real
          conjunctions between tracked objects. TLEs are fetched from{" "}
          <M>celestrak.org/NORAD/elements/gp.php</M> for a configurable set of GP groups,
          merged and de-duplicated by NORAD id. The default groups are chosen to guarantee an
          interesting demo — crewed stations plus four dense debris clouds:
        </p>
        <Table
          head={["Group", "What it is"]}
          rows={[
            [<M>stations</M>, "ISS, Tiangong, and craft docked at or near them"],
            [<M>cosmos-2251-debris</M>, "Fragments from the 2009 Iridium-33 / Cosmos-2251 collision"],
            [<M>iridium-33-debris</M>, "The other half of that 2009 collision"],
            [<M>cosmos-1408-debris</M>, "Fragments from the 2021 Russian ASAT test"],
            [<M>fengyun-1c-debris</M>, "Fragments from the 2007 Chinese ASAT test"],
          ]}
        />
        <p>
          The screened set is capped at <M>EVENTIDE_MAX_OBJECTS</M> (350 by default, 250 on
          the deployed instance) and sampled evenly across the fetched catalogue so a cold
          call stays interactive.
        </p>
        <ul>
          <li>
            <strong>TTL cache</strong> — fetched TLEs are cached for one hour (monotonic
            clock) so a live call does not re-hit CelesTrak every time.
          </li>
          <li>
            <strong>Stale-cache fallback</strong> — on any network or parse error, a previous
            cache is served with a <M>served_stale</M> flag and the error string, both
            surfaced on <M>GET /health</M> and by the status dot in the header. Only if there
            is no cache at all does the error propagate. Detection failures are never silent.
          </li>
          <li>
            <strong>Recompute</strong> forces a cache drop, so it genuinely re-pulls element
            sets rather than re-running over stale data.
          </li>
        </ul>
        <p>
          Detection results themselves are cached in-process for 5 minutes per window size.
          There is no database — everything is computed live per session.
        </p>
      </>
    ),
  },
  {
    id: "data-synthetic",
    title: "The one synthetic conjunction",
    level: 3,
    body: (
      <>
        <p>
          A genuinely dangerous (sub-kilometre, high-Pc) conjunction inside a 48-hour window
          is rare in any few-hundred-object sample, and the maneuver-rejection demo needs a
          guaranteed dramatic scenario. So one conjunction is <strong>synthetic</strong>,
          flagged <M>synthetic: true</M> in the API and labelled “Synthetic” everywhere in the
          UI — it is never presented as real data. Disable it entirely with{" "}
          <M>EVENTIDE_DEMO_INJECT_SCENARIO=false</M>.
        </p>
        <p>How it is built (<M>services/scenario.py</M>, NORAD <M>99001</M>):</p>
        <ol>
          <li>Pick a target from the live catalogue — the ISS by default, or a name hint.</li>
          <li>
            Build a debris element set that keeps the target’s <strong>altitude</strong> (same
            mean motion, same eccentricity) but sits in a <strong>steeply different orbit
            plane</strong> (inclination offset +70°). Two orbits at the same altitude in
            different planes cross twice per revolution at <M>≈ 2·v·sin(Δi/2) ≈ 15 km/s</M>.
          </li>
          <li>
            Search RAAN offset (24 points) × mean-anomaly offset (36 points) — coarse, then a
            shrinking local grid — with adaptive time refinement, until the crossing lands
            inside the window at under 0.3 km miss with usable maneuver lead time.
          </li>
          <li>Reformat line 2 with the perturbed elements and a recomputed checksum.</li>
        </ol>
        <p>
          Typical result: ~0.65 km miss, ~15 km/s closing speed, TCA ~27 h out, Pc ~3e-5 →
          High tier.
        </p>
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "stage1",
    title: "Stage 1 — Detect",
    level: 2,
    body: (
      <p>
        Fetch TLEs → propagate the catalogue onto a common time grid → cheaply eliminate pairs
        that cannot possibly conjunct → for the survivors, find the true time and distance of
        closest approach. Endpoint: <M>GET /conjunctions?window_hours=48</M>.
      </p>
    ),
  },
  {
    id: "stage1-propagation",
    title: "Propagation",
    level: 3,
    body: (
      <>
        <p>
          A screening run picks a common epoch (now, UTC), builds an absolute time grid at a{" "}
          <strong>60-second step</strong> over the window (2 881 samples for 48 h), and
          propagates every object to those times with the vectorised{" "}
          <M>Satrec.sgp4_array</M> path. Output is TEME, km and km/s. Objects whose SGP4 call
          errors, produces non-finite output, or whose derived perigee altitude is below{" "}
          <M>−50 km</M> (decayed / garbage elements) are dropped before screening.
        </p>
      </>
    ),
  },
  {
    id: "stage1-apsis",
    title: "The APSIS prefilter",
    level: 3,
    body: (
      <>
        <p>
          The cheapest useful filter. Two objects can only conjunct if their radial altitude
          bands overlap. Using the perigee/apogee altitudes derived above,{" "}
          <M>keep_pair(a, b)</M> is true iff
        </p>
        <Formula>
          [perigee_a − pad, apogee_a + pad] overlaps [perigee_b − pad, apogee_b + pad]
        </Formula>
        <p>
          with a default <M>pad</M> of 15 km. It ignores phasing entirely, so it can{" "}
          <strong>never</strong> drop a pair that could actually come close — it only removes
          pairs that are geometrically incapable of it (different altitude shells). It is
          implemented as a swappable strategy so more sieves (an along-track / nodal filter, an
          ML prefilter) can stack in the chain without touching the detector.
        </p>
        <Callout kind="warn">
          The reduction rate here (~30–45%) is lower than the ~62% quoted in the literature
          (Stevenson et al. 2023) because Eventide’s default input is dominated by debris
          clouds sitting in a single narrow altitude band — the filter simply has less it can
          legitimately remove. Widen the groups across more shells and the rate rises. The
          mechanism is identical; only the input distribution differs.
        </Callout>
      </>
    ),
  },
  {
    id: "stage1-segmin",
    title: "The segment-minimum scan — and why the plot is re-sampled",
    level: 3,
    body: (
      <>
        <p>
          The naïve approach — sample separation on the coarse grid and take the minimum —{" "}
          <strong>fails for fast conjunctions</strong>. At 15 km/s relative speed on a 60 s
          grid the two objects move ~900 km between samples; a sub-kilometre encounter can sit
          entirely between two grid points, both of which show the objects hundreds of km
          apart.
        </p>
        <p>
          The fix: for each consecutive pair of samples, compute the closest approach of the{" "}
          <strong>straight line segment</strong> between them to the origin of the relative
          frame:
        </p>
        <Formula>
          frac = clip( −(d₀·seg) / (seg·seg), 0, 1 )   ·   d_min = | d₀ + frac·seg |
        </Formula>
        <p>
          Even when both endpoints are 400 km out, the segment itself may pass within metres of
          zero — and that is detected. The scan is fully vectorised and runs in chunks of
          1 200 pairs. Any pair whose minimum segment distance is below the{" "}
          <strong>25 km refine threshold</strong> is handed to the refinement step.
        </p>
        <Callout>
          This same sampling problem is why the <strong>separation plot</strong> re-samples the
          curve at 1-second spacing within ±3 minutes of TCA. Without it the plotted blue line
          bottoms out where the 60 s grid happens to land — often hundreds of km above the true
          miss — while the refined red TCA point sits far below, looking disconnected. With the
          fine patch spliced in, the curve dives all the way down and the point sits on the
          line.
        </Callout>
      </>
    ),
  },
  {
    id: "stage1-tca",
    title: "TCA refinement",
    level: 3,
    body: (
      <>
        <p>
          Given the bracketing segment, <M>scipy.optimize.minimize_scalar</M> (bounded,{" "}
          <M>xatol = 1e-3 s</M>) finds the separation minimum on the continuous SGP4
          trajectory. It returns the TCA (seconds from the run epoch), the miss distance, and
          both objects’ full position and velocity at TCA — everything the risk model needs.
          The same routine is reused, with different trajectory callables, when re-screening a
          maneuvered arc.
        </p>
      </>
    ),
  },
  {
    id: "stage1-guards",
    title: "Guards: docked craft, duplicates, synthetic collapse",
    level: 3,
    body: (
      <ul>
        <li>
          <strong>Docked / co-orbiting guard.</strong> A refined event with miss under 20 m{" "}
          <em>and</em> relative speed under 20 m/s is a docked spacecraft or a deployment pair,
          not a collision risk — it is discarded.
        </li>
        <li>
          <strong>One approach per pair.</strong> Only the single closest approach in the
          window is reported for each object pair.
        </li>
        <li>
          <strong>Synthetic collapse.</strong> The injected debris object conjuncts with every
          craft near the station; only its single closest partner is kept so the alert list is
          not flooded.
        </li>
      </ul>
    ),
  },
  {
    id: "stage1-thresholds",
    title: "Detection thresholds",
    level: 3,
    body: (
      <Table
        head={["Setting", "Default", "Role"]}
        rows={[
          [<M>coarse_step_s</M>, "60 s", "Propagation grid step"],
          [<M>refine_threshold_km</M>, "25 km", "Segment minimum below which a pair is refined"],
          [<M>report_threshold_km</M>, "10 km", "Refined miss below which a conjunction is reported"],
          [<M>apsis_pad_km</M>, "15 km", "Altitude-band pad in the APSIS filter"],
          ["chunk size", "1 200 pairs", "Memory bound on the vectorised scan"],
          ["docked guard", "< 20 m & < 20 m/s", "Drops attached / deploying craft"],
        ]}
      />
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "stage2",
    title: "Stage 2 — Assess",
    level: 2,
    body: (
      <p>
        Each detected conjunction is scored for probability of collision, then combined with
        timing and closeness into a single risk score and tier. The Pc method is a swappable
        strategy; the default is Foster–Estes.
      </p>
    ),
  },
  {
    id: "stage2-foster",
    title: "Foster–Estes 2-D probability of collision",
    level: 3,
    body: (
      <>
        <p>The NASA JSC (1992) short-encounter method, step by step:</p>
        <ol>
          <li>
            <strong>Relative state at TCA:</strong> <M>dr = r_b − r_a</M>,{" "}
            <M>dv = v_b − v_a</M>.
          </li>
          <li>
            <strong>Conjunction-plane basis</strong> perpendicular to the relative velocity:{" "}
            <M>w = dv/|dv|</M>, <M>η = (dr × w)/|·|</M>, <M>ξ = η × w</M>. The 2×3 projection
            matrix is <M>M = [ξ; η]</M>.
          </li>
          <li>
            <strong>Combined covariance</strong> <M>C = C_a + C_b</M> (see next section),
            projected: <M>cov2 = M · C · Mᵀ</M> (2×2). Projected miss <M>miss2 = M · dr</M>.
          </li>
          <li>
            <strong>Diagonalise</strong> <M>cov2</M> → eigenvalues give <M>σx, σy</M>; rotate{" "}
            <M>miss2</M> into that eigenframe → <M>(mx, my)</M>.
          </li>
          <li>
            <strong>Integrate</strong> the 2-D Gaussian over a disk of radius = combined
            hard-body radius (default 2 × 5 m = 10 m), on a 60 × 120 polar grid:
          </li>
        </ol>
        <Formula>
          Pc = Σ exp(−½[((r·cosθ − mx)/σx)² + ((r·sinθ − my)/σy)²]) · r · Δr · Δθ / (2π·σx·σy)
        </Formula>
        <p>
          The result is clipped to [0, 1]. Tests enforce that Pc is monotonic in miss distance
          (closer never scores lower), bounded, and that a 500 km miss gives Pc under 1e-6.
        </p>
        <Callout kind="warn">
          The method assumes a <strong>short encounter</strong> — relative motion is
          effectively rectilinear through the conjunction and the covariance is constant over
          it. This holds well for the 7–15 km/s LEO crossings Eventide targets and breaks down
          for slow, drawn-out approaches between near-co-orbiting objects.
        </Callout>
      </>
    ),
  },
  {
    id: "stage2-covariance",
    title: "The covariance model",
    level: 3,
    body: (
      <>
        <p>
          Each object’s covariance is built in the RTN frame and rotated into TEME:{" "}
          <M>C = R_RTN · diag(σ_r², σ_t², σ_n²) · R_RTNᵀ</M>, summed over the two objects (no
          cross-correlation). The along-track sigma <strong>grows linearly with time to
          TCA</strong>:
        </p>
        <Formula>σ_t = σ_t0 + growth · t_TCA_hours</Formula>
        <Table
          head={["Component", "1-σ default", "Note"]}
          rows={[
            ["Radial", "500 m", "constant"],
            ["Along-track", "2 000 m + 120 m/hour", "dominant, and grows with propagation time"],
            ["Cross-track", "1 000 m", "constant"],
            ["Combined hard-body radius", "10 m", "sum of two 5 m spheres"],
          ]}
        />
        <p>
          These are deliberately large — a representative model of propagated-TLE error, chosen
          conservative so the model does not understate risk (the high-recall requirement).
          They are an <strong>assumed</strong> model, not derived per object from observation
          residuals; Eventide does not ingest Space-Track / special-perturbations covariance.
        </p>
      </>
    ),
  },
  {
    id: "stage2-score",
    title: "Risk score and tiers",
    level: 3,
    body: (
      <>
        <p>The composite score (0–1):</p>
        <Formula>
          score = 0.7·pc_c + 0.2·urgency + 0.1·closeness
        </Formula>
        <ul>
          <li>
            <M>pc_c = clamp((log₁₀(Pc) + 9) / 9, 0, 1)</M> — maps Pc 1e-9 → 0, 1e0 → 1.
          </li>
          <li>
            <M>urgency = clamp(1 − t_TCA_hours / window_hours, 0, 1)</M> — sooner is more
            urgent.
          </li>
          <li>
            <M>closeness = clamp(1 − miss_km / 10, 0, 1)</M>.
          </li>
        </ul>
        <p>Tier assignment (the values actually used in production):</p>
        <Table
          head={["Condition", "Tier"]}
          rows={[
            [<>Pc ≥ <M>1e-5</M></>, "High"],
            [<>Pc ≥ <M>1e-7</M></>, "Medium"],
            [<>otherwise, score ≥ 0.5</>, "Medium (close geometry, low modelled Pc)"],
            ["else", "Low"],
          ]}
        />
        <p>
          The 1e-5 High cut is a crewed-asset posture — many operators escalate crewed
          conjunctions there rather than at the 1e-4 used for routine robotic assets. Events
          are returned sorted by score, descending.
        </p>
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "stage3",
    title: "Stage 3 — Act",
    level: 2,
    body: (
      <p>
        For a chosen conjunction and a chosen object to maneuver: generate a grid of candidate
        burns, re-simulate each one against the whole catalogue, reject the unsafe ones, and
        rank the survivors. Endpoint:{" "}
        <M>POST /recommend-maneuver {"{ object_id, conjunction_id }"}</M>.
      </p>
    ),
  },
  {
    id: "stage3-grid",
    title: "The Δv grid",
    level: 3,
    body: (
      <>
        <p>
          <strong>6 directions</strong> (±radial, ±along-track, ±cross-track) ×{" "}
          <strong>5 magnitudes</strong> ({"{"}0.02, 0.05, 0.1, 0.2, 0.5{"}"} m/s) ={" "}
          <strong>30 candidates</strong>. Every candidate burns at{" "}
          <M>max(0, t_TCA − 12 h)</M> — a 12-hour lead time. There is no gradient search; the
          grid is fixed, and the re-screening step is what separates good from bad.
        </p>
      </>
    ),
  },
  {
    id: "stage3-diff",
    title: "Differential post-burn propagation",
    level: 3,
    body: (
      <>
        <p>
          The modelling problem: the catalogue is on SGP4, but a post-burn arc is naturally
          two-body. Comparing a two-body trajectory against SGP4 over ~27 hours introduces
          kilometres of spurious drift that can both <em>mask</em> a real residual risk and{" "}
          <em>fabricate</em> a fake new conjunction.
        </p>
        <p>The fix is a differential model:</p>
        <Formula>
          state(t) = SGP4_baseline(t) + [ twobody(r₀, v₀+Δv, t) − twobody(r₀, v₀, t) ]
        </Formula>
        <p>
          for <M>t {">"} t_burn</M> (and just the SGP4 baseline before it). The two large,
          error-prone two-body integrations <strong>cancel</strong> in the difference, leaving
          only the small, accurate delta the burn actually produces. A zero Δv reproduces the
          SGP4 baseline exactly — so a null “maneuver” correctly shows residual Pc = baseline
          and is rejected. The two-body propagation itself is a universal-variable formulation
          (Vallado, Algorithm 8) with Stumpff functions.
        </p>
        <Callout kind="warn">
          This is a standard linearised-maneuver technique and a documented simplification. The
          “correct” alternative — re-fitting an SGP4 mean-element set from the post-burn
          state — is overkill for this MVP; the differential trick removes most of the error.
        </Callout>
      </>
    ),
  },
  {
    id: "stage3-rescreen",
    title: "The re-screening loop",
    level: 3,
    body: (
      <>
        <p>For each of the 30 candidates:</p>
        <ol>
          <li>
            Apply the Δv in the RTN frame at burn time; build the post-burn position arc with
            the differential model.
          </li>
          <li>
            <strong>Residual Pc</strong> against the original threat: segment-minimum scan →
            refine → Foster–Estes. This number says whether the burn <em>worked</em>.
          </li>
          <li>
            <strong>New-conjunction scan.</strong> For every other object in the catalogue: if
            its <em>pre-burn</em> minimum gap to the maneuvered object was already below the
            25 km refine threshold, skip it — a co-orbiting neighbour, a docked craft, or a
            pre-existing conjunction cannot be blamed on the burn. Otherwise run the
            segment-minimum scan on the <em>post-burn</em> arc; if a refined approach comes
            within 10 km and its Pc is at or above <M>1e-6</M>, record it as a newly created
            conjunction with full detail.
          </li>
        </ol>
      </>
    ),
  },
  {
    id: "stage3-rank",
    title: "Verdict and ranking",
    level: 3,
    body: (
      <>
        <Table
          head={["Outcome", "Condition"]}
          rows={[
            ["REJECT (residual)", <>residual Pc ≥ <M>1e-6</M> — reason cites the residual Pc and the baseline</>],
            ["REJECT (new conjunction)", <>any newly created conjunction with Pc ≥ <M>1e-6</M> — reason names the worst one (object, miss, Pc)</>],
            ["ACCEPT", "neither of the above"],
          ]}
        />
        <p>
          Accepted candidates are sorted by <strong>(residual Pc ascending, then Δv magnitude
          ascending, then timing margin descending)</strong> — safest first, then cheapest,
          then most lead time. If nothing survives, the response is an explicit “NO SAFE
          CANDIDATE FOUND”. The API returns the recommended list, the full rejected list with
          reasons, and stats (candidates generated, rejected, rejection rate, seconds per
          candidate).
        </p>
      </>
    ),
  },
  {
    id: "worked-example",
    title: "A worked recommendation",
    level: 2,
    body: (
      <>
        <p>
          Maneuvering the ISS to avoid the synthetic debris object (representative run,
          250 objects, 48 h):
        </p>
        <ul>
          <li>Baseline: miss ~0.65 km, closing speed ~15 km/s, Pc ~3e-5, High tier.</li>
          <li>
            <strong>30 candidates generated, ~27 rejected (~90%)</strong>, ~0.1 s per
            candidate re-screen.
          </li>
          <li>
            Rejected examples: small radial burns (<M>+0.02 R</M>, <M>+0.05 R</M>) — “residual
            Pc 3.1e-05 still above reject threshold 1e-06”.
          </li>
          <li>
            <strong>Recommended (best):</strong> <M>−0.5 m/s along-track</M>, residual Pc
            ~7e-16, ~15 h of timing margin. A tiny retrograde nudge 12 hours out moves the
            station kilometres clear by TCA.
          </li>
        </ul>
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "metrics",
    title: "Metrics — and what each one proves",
    level: 2,
    body: (
      <>
        <p>
          <M>GET /metrics</M> returns a flat snapshot generated entirely by the running
          system. The dashboard shows a slim strip; the full annotated set is here, live:
        </p>
        <LiveMetrics />
      </>
    ),
  },

  /* ------------------------------------------------------------------ */
  {
    id: "api",
    title: "API reference",
    level: 2,
    body: (
      <>
        <Table
          head={["Endpoint", "Purpose", "Key response fields"]}
          rows={[
            [<M>GET /health</M>, "Liveness + TLE source status", <M>status, tle_source_error, tle_served_stale</M>],
            [<M>GET /conjunctions?window_hours=48&refresh=false</M>, "Run / return detection + assessment", <M>epoch, object_count, pairs_before_filter, pairs_after_filter, prefilter_reduction_rate, screening_latency_s, conjunctions[]</M>],
            [<M>POST /recommend-maneuver</M>, <>Body <M>{"{ object_id, conjunction_id }"}</M> — generate + re-screen + rank</>, <M>baseline_pc, candidates_generated, candidates_rejected, rejection_rate, rescreen_s_per_candidate, recommended[], rejected[], message</M>],
            [<M>GET /conjunctions/{"{id}"}/separation</M>, "2-D plot data (±6 h window, 1 s patch near TCA)", <M>times_hours[], separation_km[], tca_hours, miss_distance_km</M>],
            [<M>GET /conjunctions/{"{id}"}/geometry?points=240</M>, "3-D globe data", <M>epoch, times_hours[], object_a.path_km[], object_b.path_km[], tca_index, tca_point_a_km, tca_point_b_km</M>],
            [<M>GET /metrics</M>, "Live metrics snapshot", "see the Metrics section"],
          ]}
        />
        <p>
          Each conjunction object carries: <M>conjunction_id</M> (the sorted NORAD pair, e.g.{" "}
          <M>"25544-99001"</M>), <M>object_a</M> / <M>object_b</M>, <M>tca</M> (ISO 8601 UTC),{" "}
          <M>tca_hours_from_now</M>, <M>miss_distance_km</M>, <M>rel_speed_km_s</M>, <M>pc</M>,{" "}
          <M>risk_score</M>, <M>risk_tier</M>, <M>synthetic</M>. Interactive docs are at{" "}
          <M>/docs</M>.
        </p>
      </>
    ),
  },
  {
    id: "architecture",
    title: "Architecture",
    level: 2,
    body: (
      <>
        <p>
          FastAPI + SGP4 + NumPy/SciPy on the backend; React + Vite + Plotly + CesiumJS on the
          frontend. Every seam the design calls for is an abstract base class with an injected
          implementation, so Stage 3 plugs into Stage 1 without either being rewritten:
        </p>
        <Table
          head={["Seam", "Interface", "Swap in…"]}
          rows={[
            ["TLE source", <M>TLESource.fetch()</M>, "CelesTrak / local file / static fixture"],
            ["Prefilter", <M>ConjunctionFilter.keep_pair()</M>, "APSIS today; an along-track or ML sieve stacks in the chain"],
            ["Pc model", <M>RiskModel.collision_probability()</M>, "Foster–Estes today; Chan, Alfano, Monte-Carlo behind the same interface"],
          ]}
        />
        <p>
          <M>app/container.py</M> is the single composition root — the only place concrete
          classes are named. That is what makes the test suite (27 tests, zero network access,
          fixture-backed) possible.
        </p>
      </>
    ),
  },
  {
    id: "limitations",
    title: "Known modelling limitations",
    level: 2,
    body: (
      <ul>
        <li>
          <strong>Covariance is assumed, not observed.</strong> The RTN sigma model is a
          representative stand-in for propagated-TLE error; no CDM or Space-Track SP covariance
          is ingested.
        </li>
        <li>
          <strong>Post-burn propagation is a differential two-body approximation</strong>, not
          a re-fitted SGP4 mean-element set. The differential trick cancels most of the error,
          but a long-arc, high-eccentricity case would still be approximate.
        </li>
        <li>
          <strong>TEME is treated as inertial for the 3-D globe</strong>; only the
          Earth-rotation (GMST) part of the TEME→ECEF transform is applied. Immaterial at
          globe-view scale.
        </li>
        <li>
          <strong>One close approach per pair per window.</strong> A pair with two distinct
          encounters in 48 h shows only the worse one.
        </li>
        <li>
          <strong>Not the full catalogue in real time.</strong> The screened set is capped.
          Scaling up is an engineering problem (spatial hashing, GPU pairwise, incremental
          screening), not a physics one — the algorithms are unchanged.
        </li>
        <li>
          <strong>No trained ML ranking.</strong> The composite risk score is a transparent
          heuristic. A learning-to-rank layer would only ever re-order alerts, never gate a
          safety decision.
        </li>
      </ul>
    ),
  },
  {
    id: "config",
    title: "Configuration reference",
    level: 2,
    body: (
      <Table
        head={["Setting (EVENTIDE_*)", "Default", "Meaning"]}
        rows={[
          [<M>tle_groups</M>, "stations + 4 debris clouds", "CelesTrak GP groups to screen"],
          [<M>tle_cache_ttl_s</M>, "3600", "TLE re-fetch interval"],
          [<M>max_objects</M>, "350 (250 deployed)", "Screened-set cap"],
          [<M>default_window_hours</M>, "48", "Propagation / screening horizon"],
          [<M>coarse_step_s</M>, "60", "Propagation grid step"],
          [<M>refine_threshold_km</M>, "25", "Segment min below which a pair is refined"],
          [<M>report_threshold_km</M>, "10", "Refined miss below which a conjunction is reported"],
          [<M>apsis_pad_km</M>, "15", "APSIS altitude-band pad"],
          [<M>sigma_radial_m / sigma_intrack_m / sigma_crosstrack_m</M>, "500 / 2000 / 1000", "Per-object 1-σ position uncertainty (RTN)"],
          [<M>intrack_growth_m_per_hour</M>, "120", "Along-track σ growth with time to TCA"],
          [<M>hard_body_radius_m</M>, "5", "Per-object radius (combined HBR = 10 m)"],
          [<M>pc_high / pc_medium</M>, "1e-5 / 1e-7", "Risk-tier cut points"],
          [<M>maneuver_dv_grid_mps</M>, "0.02, 0.05, 0.1, 0.2, 0.5", "Δv magnitudes"],
          [<M>maneuver_lead_hours</M>, "12", "Burn lead time before TCA"],
          [<M>maneuver_pc_reject</M>, "1e-6", "Residual / new-conjunction Pc that triggers rejection"],
          [<M>demo_inject_scenario</M>, "true", "Inject the synthetic conjunction"],
        ]}
      />
    ),
  },
  {
    id: "glossary",
    title: "Glossary",
    level: 2,
    body: (
      <Table
        head={["Term", "Meaning"]}
        rows={[
          ["TLE / GP element set", "The public orbital-element record SGP4 consumes"],
          ["SGP4", "The analytic propagator that turns an element set + time into position & velocity"],
          ["Epoch", "The timestamp a set of orbital elements is valid for"],
          ["Conjunction", "A predicted close approach between two catalogued objects"],
          ["TCA", "Time of Closest Approach"],
          ["Miss distance", "The separation between the two objects at TCA"],
          ["Pc", "Probability of collision"],
          ["B-plane / conjunction plane", "The plane perpendicular to the relative velocity at TCA, onto which the 3-D encounter is projected"],
          ["HBR", "Hard-body radius — the objects modelled as spheres; combined HBR = sum of radii"],
          ["Covariance", "The 3×3 position-error matrix around a predicted state"],
          ["RTN / RIC", "Radial / Transverse (in-track) / Normal — a frame that travels with the spacecraft"],
          ["TEME", "True Equator, Mean Equinox — the quasi-inertial frame SGP4 outputs"],
          ["Δv", "A change in velocity — a maneuver, measured in m/s"],
          ["CDM", "Conjunction Data Message — the operational alert format issued to operators"],
          ["Kessler syndrome", "Runaway collisional cascade in orbit"],
        ]}
      />
    ),
  },
  {
    id: "references",
    title: "References",
    level: 2,
    body: (
      <ul>
        <li>
          Vallado, D. A. (2006). <em>Revisiting Spacetrack Report #3</em>. AIAA — the SGP4 and
          two-body reference implementations and test vectors.
        </li>
        <li>
          Foster, J. L., &amp; Estes, H. S. (1992). <em>A parametric analysis of orbital
          debris collision probability and maneuver rate for space vehicles</em>. NASA JSC —
          the 2-D short-encounter Pc method.
        </li>
        <li>
          Stevenson, E. et al. (2023). Work on catalogue prefilter reduction rates — the ~62%
          figure referenced for the APSIS filter.
        </li>
        <li>Chan, F. K. (2008). <em>Spacecraft Collision Probability</em> — analytic Pc alternatives.</li>
        <li>NASA CARA and ESA DRAMA/CRASS — operational conjunction-assessment tooling.</li>
        <li>CelesTrak (celestrak.org) — the GP element-set source.</li>
      </ul>
    ),
  },
];
