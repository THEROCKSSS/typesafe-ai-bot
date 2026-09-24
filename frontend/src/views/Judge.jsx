import { Badge, Card, BarRow, Empty, ErrorBox, Loading, Sparkline } from "../components.jsx";
import { fmt, useApi } from "../api.js";

const LAYER_TONE = { jev: "green", opencode: "indigo", heuristic: "amber" };

export default function Judge() {
  const { data: j, error, loading } = useApi("/api/judge");
  if (loading) return <Loading what="judge chain" />;
  if (error) return <ErrorBox message={error} />;

  const layers = j.by_layer || [];
  const max = layers.length ? Math.max(...layers.map((r) => r.n)) : 0;
  const recent = j.recent || [];
  const series = (j.series || []).map((p) => p.latency_ms || 0);

  return (
    <>
      {j.last_error && (
        <div className="notice err">
          <strong>Last judge error:</strong> {j.last_error}
          <br />
          <small>
            Layer 1 (TypeSafe Jev) needs credits at console.typesafe.ai — until then the
            chain falls back to OpenCode, then to heuristics + human review. Nothing
            auto-punishes while degraded.
          </small>
        </div>
      )}

      <div className="grid two">
        <Card title="Calls by layer · 24h" right="layer share">
          {layers.length ? (
            <div className="bars">
              {layers.map((l) => (
                <BarRow key={l.layer} label={l.layer} value={l.n} max={max}
                        tone={LAYER_TONE[l.layer] ?? ""} />
              ))}
            </div>
          ) : <Empty />}
        </Card>
        <Card title="Latency · recent calls">
          {series.length ? (
            <>
              <Sparkline values={series} tone="indigo" />
              <div className="spark-stats">
                <span>min <b className="mono">{Math.min(...series)} ms</b></span>
                <span>avg <b className="mono">{Math.round(series.reduce((a, b) => a + b, 0) / series.length)} ms</b></span>
                <span>max <b className="mono">{Math.max(...series)} ms</b></span>
              </div>
            </>
          ) : <Empty />}
        </Card>
      </div>

      <Card title="Recent judge calls" right={`${recent.length} shown`}>
        {recent.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>When</th><th>Layer</th><th>Model</th><th>Result</th>
                    <th>Tokens</th><th>Latency</th><th>Error</th></tr>
              </thead>
              <tbody>
                {recent.map((r, i) => (
                  <tr key={i}>
                    <td className="mono nowrap">{fmt.when(r.created_at)}</td>
                    <td><Badge tone={LAYER_TONE[r.layer] ?? ""}>{r.layer}</Badge></td>
                    <td className="mono dim">{r.model || "—"}</td>
                    <td>{r.ok ? <Badge tone="green">ok</Badge> : <Badge tone="red">failed</Badge>}</td>
                    <td className="mono">{fmt.n(r.input_tokens)}</td>
                    <td className="mono">{fmt.n(r.latency_ms)} ms</td>
                    <td className="dim" title={r.error || ""}>{(r.error || "—").slice(0, 70)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty title="No judge calls yet" hint="The chain records every call — layers, tokens, latency." />}
      </Card>
    </>
  );
}
