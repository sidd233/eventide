import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { useRouter } from "./router";
import Header from "./components/Header";
import Dashboard from "./pages/Dashboard";
import Wiki from "./pages/Wiki";

const WINDOW_HOURS = 48;

export default function App() {
  const { path } = useRouter();
  const [health, setHealth] = useState(null);
  const [conjunctions, setConjunctions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [geometry, setGeometry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const pollHealth = useCallback(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "unreachable" }));
  }, []);

  const load = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.conjunctions(WINDOW_HOURS, refresh);
        setConjunctions(data.conjunctions);
        setSelected((prev) => {
          if (prev) {
            const still = data.conjunctions.find(
              (c) => c.conjunction_id === prev.conjunction_id
            );
            if (still) return still;
          }
          return data.conjunctions[0] || null;
        });
        pollHealth();
      } catch (e) {
        setError(String(e.message || e));
      } finally {
        setLoading(false);
      }
    },
    [pollHealth]
  );

  useEffect(() => {
    pollHealth();
    load();
  }, [load, pollHealth]);

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

  return (
    <div className="app">
      <Header health={health} loading={loading} onRecompute={() => load(true)} />
      {path.startsWith("/wiki") ? (
        <Wiki />
      ) : (
        <Dashboard
          conjunctions={conjunctions}
          selected={selected}
          onSelect={setSelected}
          geometry={geometry}
          loading={loading}
          error={error}
        />
      )}
    </div>
  );
}
