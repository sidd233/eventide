import { useEffect, useRef } from "react";
import * as Cesium from "cesium";

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
    timeline: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
  });
  viewer.scene.globe.enableLighting = true;
  viewer.scene.skyAtmosphere.show = true;
  return viewer;
}

function temePathToFixed(pathKm, epochIso, timesHours) {
  const epoch = Cesium.JulianDate.fromIso8601(epochIso);
  const out = [];
  for (let i = 0; i < pathKm.length; i++) {
    const date = Cesium.JulianDate.addHours(epoch, timesHours[i], new Cesium.JulianDate());
    const m = Cesium.Transforms.computeTemeToPseudoFixedMatrix(date, new Cesium.Matrix3());
    const teme = new Cesium.Cartesian3(
      pathKm[i][0] * 1000, pathKm[i][1] * 1000, pathKm[i][2] * 1000
    );
    out.push(Cesium.Matrix3.multiplyByVector(m, teme, new Cesium.Cartesian3()));
  }
  return out;
}

export default function Globe3D({ geometry }) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    viewerRef.current = makeViewer(containerRef.current);
    return () => {
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !geometry) return;
    viewer.entities.removeAll();

    const draw = (obj, color) => {
      const pts = temePathToFixed(obj.path_km, geometry.epoch, geometry.times_hours);
      viewer.entities.add({
        name: obj.name,
        polyline: { positions: pts, width: 2, material: color, arcType: Cesium.ArcType.NONE },
      });
      const tca = pts[geometry.tca_index];
      viewer.entities.add({
        name: `${obj.name} @ TCA`,
        position: tca,
        point: { pixelSize: 9, color, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
        label: {
          text: obj.name,
          font: "12px sans-serif",
          pixelOffset: new Cesium.Cartesian2(0, -16),
          fillColor: color,
          showBackground: true,
          backgroundColor: new Cesium.Color(0, 0, 0, 0.5),
        },
      });
      return tca;
    };

    const tcaA = draw(geometry.object_a, Cesium.Color.fromCssColorString("#4da3ff"));
    draw(geometry.object_b, Cesium.Color.fromCssColorString("#ff4d5e"));

    viewer.entities.add({
      name: "conjunction",
      position: tcaA,
      ellipsoid: {
        radii: new Cesium.Cartesian3(120000, 120000, 120000),
        material: Cesium.Color.YELLOW.withAlpha(0.35),
      },
    });

    viewer.flyTo(viewer.entities, { duration: 1.2 });
  }, [geometry]);

  return <div className="globe-wrap" ref={containerRef} />;
}
