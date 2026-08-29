import { useEffect, useRef } from "react";
import * as Cesium from "cesium";

const BLUE = "#3987e5";
const AMBER = "#fab219";
const RED = "#d03b3b";

// Natural Earth II imagery bundled with Cesium - no Ion token required.
function makeViewer(container) {
  const viewer = new Cesium.Viewer(container, {
    baseLayer: Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(
        Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
      )
    ),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: true,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    shouldAnimate: true,
  });
  const globe = viewer.scene.globe;
  // Even lighting so the whole planet is visible whichever side the encounter
  // is on, plus a solid fallback colour if the offline imagery ever fails to
  // load (otherwise the globe renders transparent and the orbits show through).
  globe.enableLighting = false;
  globe.baseColor = Cesium.Color.fromCssColorString("#0b1d33");
  globe.showGroundAtmosphere = true;
  viewer.scene.skyAtmosphere.show = true;
  return viewer;
}

function icrfToFixed(date) {
  return (
    Cesium.Transforms.computeIcrfToFixedMatrix(date, new Cesium.Matrix3()) ||
    Cesium.Transforms.computeTemeToPseudoFixedMatrix(date, new Cesium.Matrix3())
  );
}

export default function Globe3D({ geometry }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const viewer = makeViewer(containerRef.current);
    viewerRef.current = viewer;
    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !geometry) return;

    const { epoch, times_s, tca_index, object_a, object_b } = geometry;
    const epochJd = Cesium.JulianDate.fromIso8601(epoch);
    const times = times_s.map((s) =>
      Cesium.JulianDate.addSeconds(epochJd, s, new Cesium.JulianDate())
    );

    const sampled = (obj) => {
      const p = new Cesium.SampledPositionProperty(Cesium.ReferenceFrame.INERTIAL);
      p.setInterpolationOptions({
        interpolationDegree: 2,
        interpolationAlgorithm: Cesium.LagrangePolynomialApproximation,
      });
      for (let i = 0; i < times.length; i++) {
        const r = obj.path_km[i];
        p.addSample(
          times[i],
          new Cesium.Cartesian3(r[0] * 1000, r[1] * 1000, r[2] * 1000)
        );
      }
      return p;
    };

    const posA = sampled(object_a);
    const posB = sampled(object_b);

    viewer.entities.removeAll();

    const start = times[0];
    const stop = times[times.length - 1];
    const spanSec = Cesium.JulianDate.secondsDifference(stop, start);

    viewer.clock.startTime = start.clone();
    viewer.clock.stopTime = stop.clone();
    viewer.clock.currentTime = start.clone();
    viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP;
    viewer.clock.multiplier = Math.max(30, spanSec / 20); // ~20 s per loop
    viewer.clock.shouldAnimate = true;
    viewer.timeline.zoomTo(start, stop);

    const availability = new Cesium.TimeIntervalCollection([
      new Cesium.TimeInterval({ start, stop }),
    ]);

    const addObject = (obj, pos, cssColor) => {
      const color = Cesium.Color.fromCssColorString(cssColor);
      viewer.entities.add({
        availability,
        position: pos,
        point: {
          pixelSize: 11,
          color,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: obj.name,
          font: "13px Inter, sans-serif",
          fillColor: color,
          showBackground: true,
          backgroundColor: new Cesium.Color(0, 0, 0, 0.55),
          pixelOffset: new Cesium.Cartesian2(0, -18),
          scale: 0.9,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        path: {
          leadTime: 0,
          trailTime: spanSec,
          width: 2,
          resolution: 5,
          material: color,
        },
      });
    };

    addObject(object_a, posA, BLUE);
    addObject(object_b, posB, AMBER);

    // Live separation line between the two objects, coloured by current distance
    // (red at contact, green far away). It collapses to the miss distance at TCA.
    viewer.entities.add({
      availability,
      polyline: {
        positions: new Cesium.CallbackProperty((time) => {
          const a = posA.getValue(time);
          const b = posB.getValue(time);
          return a && b ? [a, b] : [];
        }, false),
        width: 2,
        arcType: Cesium.ArcType.NONE,
        material: new Cesium.ColorMaterialProperty(
          new Cesium.CallbackProperty((time) => {
            const a = posA.getValue(time);
            const b = posB.getValue(time);
            if (!a || !b) return Cesium.Color.GRAY.withAlpha(0.5);
            const km = Cesium.Cartesian3.distance(a, b) / 1000;
            const f = Math.min(1, km / 200);
            return Cesium.Color.lerp(
              Cesium.Color.fromCssColorString(RED),
              Cesium.Color.fromCssColorString("#0ca30c"),
              f,
              new Cesium.Color()
            ).withAlpha(0.9);
          }, false)
        ),
      },
    });

    // Static pulsing marker at the closest-approach midpoint.
    const aT = object_a.path_km[tca_index];
    const bT = object_b.path_km[tca_index];
    const midInertial = new Cesium.Cartesian3(
      ((aT[0] + bT[0]) / 2) * 1000,
      ((aT[1] + bT[1]) / 2) * 1000,
      ((aT[2] + bT[2]) / 2) * 1000
    );
    const midFixed = Cesium.Matrix3.multiplyByVector(
      icrfToFixed(times[tca_index]),
      midInertial,
      new Cesium.Cartesian3()
    );

    viewer.entities.add({
      position: midFixed,
      point: {
        pixelSize: new Cesium.CallbackProperty(
          () => 10 + 5 * (1 + Math.sin(Date.now() / 180)),
          false
        ),
        color: Cesium.Color.fromCssColorString(RED).withAlpha(0.9),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: `closest approach · ${geometry.miss_distance_km} km`,
        font: "12px Inter, sans-serif",
        fillColor: Cesium.Color.fromCssColorString("#f0908f"),
        showBackground: true,
        backgroundColor: new Cesium.Color(0, 0, 0, 0.55),
        pixelOffset: new Cesium.Cartesian2(0, 20),
        scale: 0.9,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    // Frame the encounter, not the whole orbit.
    viewer.camera.flyToBoundingSphere(
      new Cesium.BoundingSphere(midFixed, 4_000_000),
      { duration: 1.2 }
    );
  }, [geometry]);

  return (
    <>
      <div className="globe-fill" ref={containerRef} />
      {geometry && (
        <div className="globe-legend">
          <span>
            <i style={{ background: BLUE }} />
            {geometry.object_a.name}
          </span>
          <span>
            <i style={{ background: AMBER }} />
            {geometry.object_b.name}
          </span>
          <span>
            <i style={{ background: RED }} />
            closest approach
          </span>
        </div>
      )}
    </>
  );
}
