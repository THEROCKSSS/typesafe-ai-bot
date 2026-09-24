import { Badge, Card, Empty, ErrorBox, Loading } from "../components.jsx";
import { fmt, useApi } from "../api.js";

export default function Scheduler() {
  const { data, error, loading } = useApi("/api/events");
  if (loading) return <Loading what="scheduler" />;
  if (error) return <ErrorBox message={error} />;

  const jobs = data.jobs || [];
  const owners = data.owners || [];
  const caps = data.caps || [];

  return (
    <>
      <div className="grid side">
        <Card title="Scheduled jobs" right="mute lifts · vote deadlines">
          {jobs.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>#</th><th>Kind</th><th>Payload</th><th>Due</th>
                      <th>Status</th><th>Error</th></tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td className="mono">#{j.id}</td>
                      <td><Badge tone={j.kind === "voice_unmute" ? "indigo" : "amber"}>{j.kind}</Badge></td>
                      <td className="mono dim" title={j.payload_json}>{(j.payload_json || "").slice(0, 34)}</td>
                      <td className="mono nowrap">{fmt.when(j.due_at)}</td>
                      <td>
                        {j.status === "done" ? <Badge tone="green">done</Badge>
                         : j.status === "failed" ? <Badge tone="red">failed</Badge>
                         : <Badge tone="amber">{j.status}</Badge>}
                      </td>
                      <td className="dim">{j.error || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Empty title="No scheduled jobs"
                     hint="Mute lifts and vote deadlines appear here — they survive restarts." />}
        </Card>

        <div className="stack">
          <Card title="Owners" right={`${owners.length} runtime`}>
            {owners.length ? (
              <ul className="owner-list">
                {owners.map((o, i) => (
                  <li key={i}>
                    <Badge tone={o.kind === "role" ? "indigo" : "green"}>{o.kind}</Badge>
                    <span className="mono">{o.subject_id}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dim small">
                No runtime owners yet — bootstrap owners come from <code>OWNER_IDS</code> in
                <code> .env</code>. Add more in Discord with <code>/owners add</code>.
              </p>
            )}
          </Card>

          <Card title="Role capabilities" right={`${caps.length} mappings`}>
            {caps.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Role ID</th><th>Capability</th></tr></thead>
                  <tbody>
                    {caps.map((c, i) => (
                      <tr key={i}>
                        <td className="mono">{c.role_id}</td>
                        <td>{c.capability}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="dim small">Nothing mapped yet — configure in Discord with <code>/setup</code>.</p>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
