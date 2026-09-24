import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "./api.js";

import Overview from "./views/Overview.jsx";
import Judge from "./views/Judge.jsx";
import Cases from "./views/Cases.jsx";
import Votes from "./views/Votes.jsx";
import Rulebook from "./views/Rulebook.jsx";
import Scheduler from "./views/Scheduler.jsx";
import LoadTest from "./views/LoadTest.jsx";
import Guide from "./views/Guide.jsx";

const NAV = [
  { to: "/", label: "Overview", glyph: "◈", end: true },
  { to: "/judge", label: "Judge chain", glyph: "◇" },
  { to: "/cases", label: "Cases", glyph: "▤" },
  { to: "/votes", label: "Votes", glyph: "◉" },
  { to: "/loadtest", label: "Load test", glyph: "⌁" },
  { to: "/rulebook", label: "Rulebook", glyph: "§" },
  { to: "/scheduler", label: "Scheduler & owners", glyph: "≋" },
  { to: "/guide", label: "Command guide", glyph: "✎" },
];

const TITLES = {
  "/": ["Overview", "Live moderation state at a glance"],
  "/judge": ["Judge chain", "TypeSafe Jev → OpenCode → heuristics"],
  "/cases": ["Cases", "Every recorded moderation decision"],
  "/votes": ["Votes", "Community votes on member reports"],
  "/loadtest": ["Load test", "1,000-case moderation benchmark"],
  "/rulebook": ["Rulebook", "The machine-readable server rules"],
  "/scheduler": ["Scheduler & owners", "Timed jobs, owner registry, capabilities"],
  "/guide": ["Command guide", "Copy-paste instructions for every command"],
};

export default function App() {
  const loc = useLocation();
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    const load = () => {
      api("/api/health").then(setHealth).catch(() => setHealth({ status: "down" }));
      api("/api/summary").then(setSummary).catch(() => {});
    };
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const [title, sub] = TITLES[loc.pathname] || TITLES["/"];
  const dry = summary?.config?.dry_run;

  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <div className="brand-mark">TS</div>
          <div className="brand-text">
            <strong>TypeSafe AI Bot</strong>
            <span>command center</span>
          </div>
        </div>

        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
                     className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}>
              <i className="ico">{n.glyph}</i>{n.label}
            </NavLink>
          ))}
        </nav>

        <a className="nav-item briefing-link" href="/briefing">
          <i className="ico">◆</i>Team briefing
        </a>

        <div className="rail-foot">
          <div className={"status-pill" + (dry === false ? " live" : "")}>
            <span className="dot" />
            {dry === undefined ? "connecting…" : dry ? "DRY-RUN — not enforcing" : "LIVE — enforcing"}
          </div>
          <div className="health mono">
            {health ? `db ${health.status === "ok" ? "ok" : health.status} · ${
              (health.db || "").split(/[\\/]/).pop()}` : "api…"}
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{title}</h1>
            <p className="sub">{sub}</p>
          </div>
          <div className="top-meta">
            <span className="chip mono">
              {summary ? `data: ${new Date(summary.generated_at).toLocaleTimeString()}` : "—"}
            </span>
            <button className="refresh" onClick={() => window.dispatchEvent(new Event("refresh"))}>
              ↻ Refresh
            </button>
          </div>
        </header>
        <section className="view">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/judge" element={<Judge />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/votes" element={<Votes />} />
            <Route path="/loadtest" element={<LoadTest />} />
            <Route path="/rulebook" element={<Rulebook />} />
            <Route path="/scheduler" element={<Scheduler />} />
            <Route path="/guide" element={<Guide />} />
          </Routes>
        </section>
      </main>
    </div>
  );
}
