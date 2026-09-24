import { useState } from "react";
import { Routes, Route, useNavigate, useParams, Link } from "react-router-dom";
import { Badge, Card, Empty, ErrorBox, Loading } from "../components.jsx";
import { fmt, useApi, ACTION_TONE } from "../api.js";

function CaseDetail({ id }) {
  const { data: c, error } = useApi(`/api/case/${id}`);
  if (error) return <Card><div className="notice err">Case #{id} not found.</div></Card>;
  if (!c) return <Loading what={`case #${id}`} />;
  return (
    <Card title={`Case #${c.id}`}>
      <dl className="kv">
        <dt>Action</dt><dd><Badge tone={ACTION_TONE[c.action]}>{c.action}</Badge></dd>
        <dt>Kind</dt><dd>{c.kind}</dd>
        <dt>Target</dt>
        <dd className="mono">{c.target_name || "—"}
          {c.target_id ? <> <span className="dim">({c.target_id})</span></> : null}</dd>
        <dt>Reporter</dt>
        <dd className="mono">{c.reporter_name || "—"}
          {c.reporter_id ? <> <span className="dim">({c.reporter_id})</span></> : null}</dd>
        <dt>Moderator</dt>
        <dd className="mono">{c.actor_name || "—"}
          {c.actor_id ? <> <span className="dim">({c.actor_id})</span></> : null}</dd>
        <dt>Voice channel</dt><dd>{c.voice_channel || "—"}</dd>
        <dt>Reason</dt><dd>{c.reason || "—"}</dd>
        <dt>When</dt><dd>{fmt.when(c.created_at)}</dd>
        <dt>Mode</dt><dd>{c.dry_run ? <Badge tone="dry">dry-run</Badge> : <Badge tone="red">live</Badge>}</dd>
      </dl>
      {c.detail_json && (
        <>
          <h3 className="sub-head">Detail</h3>
          <pre className="json">{c.detail_json}</pre>
        </>
      )}
    </Card>
  );
}

function CaseList() {
  const nav = useNavigate();
  const [offset, setOffset] = useState(0);
  const limit = 25;
  const { data, error, loading } = useApi(`/api/cases?limit=${limit}&offset=${offset}`, [offset]);
  if (loading) return <Loading what="cases" />;
  if (error) return <ErrorBox message={error} />;
  const rows = data.rows || [];
  return (
    <Card title="Case log" right={`${fmt.n(data.total)} total`}>
      {rows.length ? (
        <>
          <div className="table-wrap">
            <table>
              <thead><tr><th>#</th><th>When</th><th>Action</th><th>Kind</th>
                         <th>Target</th><th>Reason</th><th>Mode</th></tr></thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => nav(`/cases/${c.id}`)}>
                    <td className="mono">#{c.id}</td>
                    <td className="mono nowrap">{fmt.rel(c.created_at)}</td>
                    <td><Badge tone={ACTION_TONE[c.action]}>{c.action}</Badge></td>
                    <td className="dim">{c.kind}</td>
                    <td className="mono" title={c.target_id ? String(c.target_id) : ""}>
                      {c.target_name || c.target_id || "—"}</td>
                    <td title={c.reason}>{(c.reason || "—").slice(0, 64)}</td>
                    <td>{c.dry_run ? <Badge tone="dry">dry</Badge> : <Badge tone="red">live</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button disabled={offset <= 0} onClick={() => setOffset(Math.max(0, offset - limit))}>← Newer</button>
            <span className="p-info mono">page {Math.floor(offset / limit) + 1} · {fmt.n(data.total)} total</span>
            <button disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>Older →</button>
          </div>
        </>
      ) : <Empty />}
    </Card>
  );
}

export default function Cases() {
  return (
    <Routes>
      <Route index element={<CaseList />} />
      <Route path=":id" element={<CaseRoute />} />
    </Routes>
  );
}

function CaseRoute() {
  const { id } = useParams();
  return (
    <>
      <Link className="link back" to="/cases">← back to cases</Link>
      <CaseDetail id={id} />
    </>
  );
}
