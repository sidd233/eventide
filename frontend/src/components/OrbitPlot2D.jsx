import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

export default function OrbitPlot2D({ separation }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !separation) return;
    const { times_hours, separation_km, tca_hours, miss_distance_km } = separation;
    Plotly.react(
      ref.current,
      [
        {
          x: times_hours,
          y: separation_km,
          mode: "lines",
          line: { color: "#4da3ff", width: 2 },
          name: "separation",
        },
        {
          x: [tca_hours],
          y: [miss_distance_km],
          mode: "markers+text",
          marker: { color: "#ff4d5e", size: 10 },
          text: [`  ${miss_distance_km.toFixed(3)} km`],
          textposition: "middle right",
          textfont: { color: "#ff4d5e" },
          name: "TCA",
        },
      ],
      {
        margin: { l: 55, r: 20, t: 10, b: 40 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#8b98a9", size: 11 },
        xaxis: { title: "hours from epoch", gridcolor: "#26303f", zeroline: false },
        yaxis: { title: "separation (km)", gridcolor: "#26303f", type: "log", zeroline: false },
        showlegend: false,
      },
      { displayModeBar: false, responsive: true }
    );
  }, [separation]);

  return <div className="plot" ref={ref} />;
}
