import { Badge, Card, Kpi, BarRow, Empty, ErrorBox, Loading, Sparkline, Donut } from "../components.jsx";
import ModerationField from "../ModerationField.jsx";
import { fmt, useApi, ACTION_TONE } from "../api.js";

export default function Overview() {
  const { data: s, error, loading } = useApi("/api/summary");
  const { data: j } = useApi("/api/judge");
  const { data: cases } = useApi("/api/cases?limit=6");

  if (loading) return <Loading what="overview" />;
  if (error) return <ErrorBox message={error} />;

  const judge = s.judge_24h || {};
  const byAction = s.cases_by_action || [];
  const maxAction = byAction.length ? Math.max(...byAction.map((r) => r.n)) : 0;
  const series = (j?.series || []).map((p) => p.latency_ms || 0);
  const layers = j?.by_layer || [];
  const layerTotal = layers.reduce((a, l) => a + l.n, 0) || 1;
  const LAYER_COLORS = { jev: "#6ee7b7", opencode: "#818cf8", heuristic: "#f5b95f" };

  return (
    <>
      {/* hero: live field + headline numbers */}
      <div className="card hero">
        <div className="hero-left">
          <h2 className="hero-title">Moderation field</h2>
          <p className="hero-sub">
            One point per recent judge call, colored by which layer answered.
            The core is the bot; the field is your traffic.
          </p>
          <div className="legend">
            <span><i className="swatch" style={{ background: "#6ee7b7" }} /> Jev (primary)</span>
            <span><i className="swatch" style={{ background: "#818cf8" }} /> OpenCode (fallback)</span>
            <span><i className="swatch" style={{ background: "#f5b95f" }} /> heuristics (last resort)</span>
          </div>
        </div>
        <div className="hero-right">
          <ModerationField points={j?.recent || []} height={250} />
        </div>
      </div>

      {s.config.dry_run && (
        <div className="notice">
          <strong>DRY-RUN is ON.</strong> Every decision is logged, cased, and DM'd —
          nothing is enforced. Flip <code>DRY_RUN=0</code> in <code>.env</code> after your
          review week.
        </div>
      )}

      {/* KPI row */}
      <div className="grid kpis">
        <Kpi label="Cases · 7 days" value={fmt.n(s.cases_7d)} tone="accent"
             note={`${fmt.n(s.dry_run_cases)} lifetime in DRY-RUN`}
             title="All moderation cases recorded in the last 7 days" />
        <Kpi label="Open votes" value={fmt.n(s.open_votes)} tone={s.open_votes ? "red" : ""}
             note={`pass at ≥${s.config.vote_min} votes / ≥${fmt.pct(s.config.vote_pct)}`}
             title="Community votes currently open" />
        <Kpi label="Judge calls · 24h" value={fmt.n(judge.calls)} tone="indigo"
             note={`${fmt.n(judge.ok)} ok · avg ${judge.avg_latency_ms} ms`}
             title="Total judge-chain calls in the last 24 hours" />
        <Kpi label="Judge spend · 24h" value={fmt.usd(judge.est_cost_usd)} tone="amber"
             note={`${fmt.n(judge.tokens)} input tokens`}
             title="Estimated at $0.042 per million input tokens" />
      </div>

      <div className="grid side">
        <Card title="Cases by action · 7 days" right={`${fmt.n(s.cases_7d)} total`}>
          {byAction.length ? (
            <div className="bars">
              {byAction.map((r) => (
                <BarRow key={r.action} label={r.action} value={r.n} max={maxAction}
                        tone={ACTION_TONE[r.action] ?? ""} />
              ))}
            </div>
          ) : <Empty />}
        </Card>

        <Card title="Judge layer share · 24h">
          {layers.length ? (
            <div className="donut-wrap">
              <Donut
                segments={layers.map((l) => ({
                  label: l.layer, value: l.n,
                  color: LAYER_COLORS[l.layer] ?? "#9aa3b2",
                }))}
                center={`${fmt.n(judge.calls)}`}
              />
              <div className="donut-legend">
                {layers.map((l) => (
                  <div key={l.layer} className="dl-row">
                    <i className="swatch" style={{ background: LAYER_COLORS[l.layer] ?? "#9aa3b2" }} />
                    <span>{l.layer}</span>
                    <b className="mono">{l.n}</b>
                    <span className="dim mono">{Math.round((l.n / layerTotal) * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          ) : <Empty />}
        </Card>
      </div>

      <div className="grid side">
        <Card title="Judge latency · recent calls" right={series.length ? `${series.length} samples` : null}>
          {series.length ? (
            <>
              <Sparkline values={series} label="judge latency in ms" />
              <div className="spark-stats">
                <span>min <b className="mono">{Math.min(...series)} ms</b></span>
                <span>avg <b className="mono">{Math.round(series.reduce((a, b) => a + b, 0) / series.length)} ms</b></span>
                <span>max <b className="mono">{Math.max(...series)} ms</b></span>
              </div>
            </>
          ) : <Empty title="No judge calls yet"
                     hint="Latency chart appears once the bot screens its first messages." />}
        </Card>

        <Card title="Pipeline">
          <dl className="kv">
            <dt>Scheduler jobs</dt>
            <dd title="Pending timed jobs (vote deadlines, mute lifts)">{fmt.n(s.pending_jobs)} pending</dd>
            <dt>Judge model</dt><dd>{s.config.jev_model}</dd>
            <dt>Spam timeout</dt><dd>{s.config.spam_timeout_minutes} min</dd>
            <dt>Vote window</dt><dd>{s.config.vote_minutes} min</dd>
            <dt>Guild</dt><dd>{s.config.guild_id || "—"}</dd>
          </dl>
        </Card>
      </div>

      <Card title="Latest cases" right={<a className="link" href="/cases">view all →</a>}>
        {cases?.rows?.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>When</th><th>Action</th><th>Kind</th><th>Reason</th><th>Mode</th></tr></thead>
              <tbody>
                {cases.rows.map((c) => (
                  <tr key={c.id}>
                    <td className="mono nowrap">{fmt.rel(c.created_at)}</td>
                    <td><Badge tone={ACTION_TONE[c.action]}>{c.action}</Badge></td>
                    <td className="dim">{c.kind}</td>
                    <td title={c.reason}>{(c.reason || "—").slice(0, 78)}</td>
                    <td>{c.dry_run ? <Badge tone="dry">dry</Badge> : <Badge tone="red">live</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty />}
      </Card>
    </>
  );
}
