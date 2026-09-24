import { Badge, Card, Empty, ErrorBox, Loading } from "../components.jsx";
import { useApi } from "../api.js";

const SEV_TONE = { critical: "red", high: "amber", medium: "indigo", low: "" };

export default function Rulebook() {
  const { data, error, loading } = useApi("/api/rules");
  if (loading) return <Loading what="rulebook" />;
  if (error) return <ErrorBox message={error} />;

  if (data.error) {
    return (
      <Card title="Rulebook problem">
        <div className="notice err">
          <strong>Could not load the rulebook.</strong> {data.error}
          <br /><small className="mono">{data.path}</small>
        </div>
      </Card>
    );
  }

  return (
    <>
      <div className="notice">
        Screened by <strong>one batched Jev call per message</strong> — every enabled rule
        is questioned together. File: <span className="mono">{data.path}</span>
      </div>

      <Card title="Rules" right={`${data.rules.length} defined`}>
        {data.rules.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Rule</th><th>Severity</th><th>Auto action</th>
                    <th>Timeout</th><th>Description</th><th>State</th></tr>
              </thead>
              <tbody>
                {data.rules.map((r) => (
                  <tr key={r.id}>
                    <td className="mono">{r.id}</td>
                    <td>{r.title}</td>
                    <td><Badge tone={SEV_TONE[r.severity]}>{r.severity}</Badge></td>
                    <td><Badge tone={r.auto_action === "timeout" ? "amber" : ""}>{r.auto_action || "—"}</Badge></td>
                    <td className="mono">{r.timeout_minutes ? `${r.timeout_minutes}m` : "—"}</td>
                    <td className="dim" title={r.description}>{(r.description || "").slice(0, 110)}</td>
                    <td>{r.enabled === false ? <Badge>off</Badge> : <Badge tone="green">on</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty title="No rules defined" hint="Edit policy/rules.json to add your server's rules." />}
      </Card>

      <Card title="How banding works">
        <div className="bands">
          <div className="band"><Badge tone="amber">action</Badge>
            <span>Jev probability ≥ <b className="mono">AUTOMOD_HIGH</b> (default 0.85) — the rule's
            auto-action fires (timeout, with the rule's configured minutes). Critical rules act
            from the medium band.</span></div>
          <div className="band"><Badge tone="indigo">review</Badge>
            <span>probability ≥ <b className="mono">AUTOMOD_MEDIUM</b> (default 0.60) — owners get a
            DM with a jump link; nothing is enforced.</span></div>
          <div className="band"><Badge>log</Badge>
            <span>below the medium band — recorded for the numbers, no notification.</span></div>
        </div>
      </Card>
    </>
  );
}
