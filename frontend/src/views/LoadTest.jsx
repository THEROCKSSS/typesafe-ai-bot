import { Badge, Card, Kpi, BarRow, Empty, Loading } from "../components.jsx";
import { fmt, useApi } from "../api.js";

/** Live load-test view: reads data/loadtest_results.json via the API. */
export default function LoadTest() {
  const { data, loading } = useApi("/api/loadtest");
  if (loading) return <Loading what="load test results" />;

  if (!data || !data.available) {
    return (
      <Card title="1,000-case benchmark">
        <Empty
          title="No results yet"
          hint='Run: python tools/loadtest/runner.py --mode local  (then refresh)'
        />
      </Card>
    );
  }

  const r = data.summary || {};
  const cats = Object.entries(r.by_category || {});
  const maxCat = cats.length ? Math.max(...cats.map(([, s]) => s.total)) : 0;

  return (
    <>
      <div className="notice">
        <strong>What this measures.</strong> {fmt.n(r.total)} labeled messages
        ({fmt.n(r.violations)} violations, {fmt.n(r.clean)} clean) through the live
        judge chain + policy engine. <b>Leak rate</b> = violations the bot missed.
        {" "}<b>False positives</b> = clean messages wrongly flagged.
        {r.mode === "live" && " (live webhook run — real Discord round-trip)"}
      </div>

      <div className="grid kpis">
        <Kpi label="Cases run" value={fmt.n(r.total)} tone="accent"
             note={`${r.mode || "local"} mode · ${r.seconds ? r.seconds + "s" : "—"}`} />
        <Kpi label="Caught" value={fmt.n(r.caught)} tone="green"
             note={`recall ${fmt.pct(r.recall, 1)}`} />
        <Kpi label="Leaked through" value={fmt.n(r.missed)} tone="red"
             note={`leak rate ${fmt.pct(r.leak_rate, 1)}`}
             title="Violations that produced no decision" />
        <Kpi label="False positives" value={fmt.n(r.false_positives)} tone="amber"
             note={`fp rate ${fmt.pct(r.fp_rate, 1)} · precision ${fmt.pct(r.precision, 1)}`}
             title="Clean messages wrongly flagged" />
      </div>

      <Card title="By category">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Category</th><th>Total</th><th>Caught</th><th>Missed</th>
                  <th>False pos</th><th>Coverage</th></tr>
            </thead>
            <tbody>
              {cats.map(([cat, s]) => {
                const cov = s.total ? (s.total - s.missed) / s.total : 0;
                return (
                  <tr key={cat}>
                    <td className="mono">{cat}</td>
                    <td className="mono">{s.total}</td>
                    <td className="mono" style={{ color: "var(--accent)" }}>{s.caught}</td>
                    <td className="mono" style={{ color: s.missed ? "var(--red)" : "inherit" }}>{s.missed}</td>
                    <td className="mono" style={{ color: s.fp ? "var(--amber)" : "inherit" }}>{s.fp}</td>
                    <td style={{ minWidth: 130 }}>
                      <span className="bar-track">
                        <span className="bar-fill" style={{ width: `${Math.round(cov * 100)}%` }} />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {(r.missed_samples?.length > 0) && (
        <Card title="Sample leaks" right={<Badge tone="red">{r.missed} total</Badge>}>
          <p className="dim small">
            Violations that produced no decision on the current judge layer. With Jev
            credits enabled these shrink dramatically (semantic understanding vs regex);
            this view exists to measure exactly that.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Case</th><th>Category</th><th>Message</th></tr></thead>
              <tbody>
                {r.missed_samples.slice(0, 25).map((m) => (
                  <tr key={m.id}>
                    <td className="mono">{m.id}</td>
                    <td className="dim">{m.category}</td>
                    <td className="mono">{(m.text || "").slice(0, 90)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {(r.fp_samples?.length > 0) && (
        <Card title="Sample false positives" right={<Badge tone="amber">{r.false_positives} total</Badge>}>
          <p className="dim small">Clean messages wrongly flagged — these are what erode trust.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Case</th><th>Category</th><th>Message</th></tr></thead>
              <tbody>
                {r.fp_samples.slice(0, 20).map((m) => (
                  <tr key={m.id}>
                    <td className="mono">{m.id}</td>
                    <td className="dim">{m.category}</td>
                    <td className="mono">{(m.text || "").slice(0, 90)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="How to re-run">
        <pre className="json">{`# full 1,000-case local run (fast, ~15s)
python tools/loadtest/runner.py --mode local

# live webhook sample (real Discord round-trip, real-time)
python tools/loadtest/runner.py --mode live --sample 20

# gate the run: nonzero exit when thresholds are exceeded
python tools/loadtest/runner.py --mode local --max-leak 0.2 --max-fp 0.05`}</pre>
      </Card>
    </>
  );
}
