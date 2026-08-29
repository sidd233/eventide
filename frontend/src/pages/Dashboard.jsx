import { useEffect, useMemo, useState } from "react";
import AlertList from "../components/AlertList";
import ConjunctionDetail from "../components/ConjunctionDetail";
import Globe3D from "../components/Globe3D";

export default function Dashboard({ conjunctions, selected, onSelect, geometry, loading, error }) {
  const [focus, setFocus] = useState(null); // NORAD id, or null

  const objects = useMemo(() => {
    const seen = new Map();
    for (const c of conjunctions) {
      for (const o of [c.object_a, c.object_b]) {
        if (!seen.has(o.norad_id)) seen.set(o.norad_id, o);
      }
    }
    return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [conjunctions]);

  const visible = useMemo(() => {
    if (focus == null) return conjunctions;
    return conjunctions.filter(
      (c) => c.object_a.norad_id === focus || c.object_b.norad_id === focus
    );
  }, [conjunctions, focus]);

  // Keep the selection valid within the current filter.
  useEffect(() => {
    if (!visible.length) return;
    if (!selected || !visible.some((c) => c.conjunction_id === selected.conjunction_id)) {
      onSelect(visible[0]);
    }
  }, [visible, selected, onSelect]);

  return (
    <div className="dash">
      <div className="sidebar">
        <AlertList
          items={visible}
          total={conjunctions.length}
          objects={objects}
          focus={focus}
          onFocus={setFocus}
          selectedId={selected?.conjunction_id}
          onSelect={onSelect}
          loading={loading}
        />
      </div>

      <div className="main-col">
        <div className="globe-hero">
          <Globe3D geometry={geometry} />
          {!geometry && (
            <div className="empty">
              {loading
                ? "Screening the catalogue…"
                : selected
                ? "Loading encounter geometry…"
                : "Select an alert to view the encounter."}
            </div>
          )}
        </div>

        {error && <div className="error">{error}</div>}

        {selected ? (
          <ConjunctionDetail conjunction={selected} />
        ) : (
          <div className="loading">
            {loading
              ? "Screening the catalogue…"
              : "No conjunctions in the current window."}
          </div>
        )}
      </div>
    </div>
  );
}
