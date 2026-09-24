import { useParams, Link } from "react-router-dom";
import { Badge, Card, BarRow, Empty, ErrorBox, Loading } from "../components.jsx";
import { fmt, useApi } from "../api.js";

const CHOICES = ["mute", "disconnect", "none"];
const TONE = { mute: "indigo", disconnect: "red", none: "" };

function VoteCard({ v }) {
  const counts = v.counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const max = Math.max(1, ...Object.values(counts));
  const statusTone = v.status === "open" ? "amber" : v.status === "passed" ? "red" : "";
  return (
    <Card
      title={`Vote #${v.id} — ${v.target_name || v.target_id}`}
      right={<>{<Badge tone={statusTone}>{v.status}</Badge>}
             {v.action ? <> <Badge tone="red">→ {v.action}</Badge></> : null}
             {v.ai_verdict ? <> <Badge tone="indigo">AI: {v.ai_verdict}</Badge></> : null}</>}
    >
      <p className="vote-reason">{v.reason || "—"}</p>
      <div className="bars">
        {CHOICES.map((c) => (
          <BarRow key={c} label={c} value={counts[c] || 0}
                  max={max} tone={TONE[c]} />
        ))}
      </div>
      <dl className="kv compact">
        <dt>Ballots</dt><dd>{total}</dd>
        <dt>Opened</dt><dd>{fmt.when(v.created_at)}</dd>
        <dt>Deadline</dt><dd>{fmt.when(v.deadline_at)}</dd>
        <dt>Closed</dt><dd>{fmt.when(v.closed_at)}</dd>
        {v.ai_note ? <><dt>AI review</dt><dd className="ai-note">{v.ai_note}</dd></> : null}
      </dl>
      <Link className="link" to={`/votes/${v.id}`}>detail →</Link>
    </Card>
  );
}

function VoteDetail() {
  const { id } = useParams();
  const { data: v, error } = useApi(`/api/vote/${id}`);
  if (error) return <Card><div className="notice err">Vote #{id} not found.</div></Card>;
  if (!v) return <Loading what={`vote #${id}`} />;
  const counts = v.counts || {};
  const total = v.ballots?.length || 0;
  const max = Math.max(1, ...Object.values(counts));
  return (
    <Card title={`Vote #${v.id}`}
          right={<Badge tone={v.status === "open" ? "amber" : v.status === "passed" ? "red" : ""}>{v.status}</Badge>}>
      <p className="vote-reason">{v.reason}</p>
      <div className="bars">
        {CHOICES.map((c) => (
          <BarRow key={c} label={c} value={counts[c] || 0} max={max} tone={TONE[c]} />
        ))}
      </div>
      <h3 className="sub-head">Ballots ({total})</h3>
      {v.ballots?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Choice</th><th>When</th></tr></thead>
            <tbody>
              {v.ballots.map((b, i) => (
                <tr key={i}>
                  <td className="mono">{b.user_id}</td>
                  <td><Badge tone={TONE[b.choice]}>{b.choice}</Badge></td>
                  <td className="mono nowrap">{fmt.when(b.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty title="No ballots yet" hint="Members vote with the buttons on the report card." />}
    </Card>
  );
}

export default function Votes() {
  const { id } = useParams();
  if (id) return (
    <>
      <Link className="link back" to="/votes">← back to votes</Link>
      <VoteDetail />
    </>
  );
  return <VoteList />;
}

function VoteList() {
  const { data, error, loading } = useApi("/api/votes");
  if (loading) return <Loading what="votes" />;
  if (error) return <ErrorBox message={error} />;
  const votes = data.votes || [];
  if (!votes.length) return <Card><Empty /></Card>;
  return <div className="grid two">{votes.map((v) => <VoteCard key={v.id} v={v} />)}</div>;
}
