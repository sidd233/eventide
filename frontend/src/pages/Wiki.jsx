import { useEffect, useRef, useState } from "react";
import { sections } from "../content/wikiSections";

export default function Wiki() {
  const bodyRef = useRef(null);
  const [active, setActive] = useState(sections[0].id);

  useEffect(() => {
    const root = bodyRef.current;
    if (!root) return;
    const headings = sections.map((s) => document.getElementById(s.id)).filter(Boolean);

    const onScroll = () => {
      const top = root.getBoundingClientRect().top + 96;
      let current = headings[0]?.id ?? sections[0].id;
      for (const h of headings) {
        if (h.getBoundingClientRect().top <= top) current = h.id;
      }
      setActive(current);
    };

    root.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => root.removeEventListener("scroll", onScroll);
  }, []);

  const go = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="wiki">
      <nav className="wiki-toc">
        <div className="toc-title">Contents</div>
        {sections.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            onClick={go(s.id)}
            className={`${active === s.id ? "active" : ""} lvl-${s.level}`}
          >
            {s.title}
          </a>
        ))}
      </nav>

      <div className="wiki-body" ref={bodyRef}>
        <div className="wiki-inner">
          <h1>Eventide — how it works</h1>
          <p className="lede">
            Everything about the project: the data it ingests, the algorithms it runs, how it
            scores risk, and how it recommends — and vets — avoidance maneuvers. Written to be
            readable without an orbital-mechanics background.
          </p>

          {sections.map((s) => {
            const Tag = s.level === 3 ? "h3" : "h2";
            return (
              <section key={s.id}>
                <Tag id={s.id}>{s.title}</Tag>
                {s.body}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
