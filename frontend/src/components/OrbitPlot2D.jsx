import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

export default function OrbitPlot2D({ separation }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !separation) return;
    const { times_hours, separation_km, tca_hours, miss_distance_km } = separation;

    Plotly.react(
      el,
      [
        {
          x: times_hours,
          y: separation_km,
          mode: "lines",
          line: { color: "#3987e5", width: 2 },
          hovertemplate: "%{x:.3f} h · %{y:.3f} km<extra></extra>",
          name: "separation",
        },
        {
          x: [tca_hours],
          y: [miss_distance_km],
          mode: "markers",
          marker: {
            color: "#d03b3b",
            size: 9,
            line: { color: "#161719", width: 2 },
          },
          hovertemplate: "TCA · %{y:.3f} km<extra></extra>",
          name: "TCA",
        },
      ],
      {
        margin: { l: 60, r: 18, t: 12, b: 42 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#a4a5ab", size: 11, family: "JetBrains Mono, monospace" },
        xaxis: {
          title: { text: "hours from epoch", font: { size: 11 } },
          gridcolor: "#2b2c2f",
          zeroline: false,
          showspikes: true,
          spikecolor: "#74757b",
          spikethickness: 1,
          spikedash: "solid",
          spikemode: "across",
        },
        yaxis: {
          title: { text: "separation (km)", font: { size: 11 } },
          type: "log",
          gridcolor: "#2b2c2f",
          zeroline: false,
        },
        shapes: [
          {
            type: "line",
            x0: tca_hours,
            x1: tca_hours,
            yref: "paper",
            y0: 0,
            y1: 1,
            line: { color: "#74757b", width: 1 },
          },
        ],
        annotations: [
          {
            x: tca_hours,
            yref: "paper",
            y: 1,
            yanchor: "bottom",
            text: "TCA",
            showarrow: false,
            font: { color: "#a4a5ab", size: 10 },
          },
        ],
        showlegend: false,
        hovermode: "x unified",
      },
      { displayModeBar: false, responsive: true }
    );

    const ro = new ResizeObserver(() => {
      if (ref.current) Plotly.Plots.resize(ref.current);
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      Plotly.purge(el);
    };
  }, [separation]);

  return <div className="plot-wrap" ref={ref} />;
}
