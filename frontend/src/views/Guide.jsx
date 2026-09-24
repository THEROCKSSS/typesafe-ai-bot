import { useEffect, useState } from "react";
import { Badge, Card, ErrorBox, Loading } from "../components.jsx";
import { api } from "../api.js";
import { GUIDE_BY_AUDIENCE } from "../guide-content.js";

const AUD_TONE = { Members: "green", Moderators: "amber", Owners: "indigo" };

function CopyButton({ text, label = "Copy" }) {
  const [done, setDone] = useState(false);
  return (
    <button className="btn" onClick={async () => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // clipboard API can be blocked; fall back to a selection trick
        const ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta);
      }
      setDone(true);
      setTimeout(() => setDone(false), 1600);
    }}>
      {done ? "✓ Copied" : label}
    </button>
  );
}

function SendControls({ entry }) {
  const [channels, setChannels] = useState([]);
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/discord/channels").then((d) => {
      setChannels(d.channels || []);
      if (d.channels?.length) setChannel(String(d.channels[0].id));
    }).catch(() => {});
  }, []);

  const sendChannel = async () => {
    if (!channel) return;
    setBusy(true); setStatus(null);
    try {
      const r = await fetch("/api/discord/post", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ channel_id: Number(channel), content: entry.message }),
      });
      const d = await r.json();
      setStatus(r.ok && d.ok
        ? { ok: true, msg: `Posted to #${d.channel || channel}` }
        : { ok: false, msg: d.error || `HTTP ${r.status}` });
    } catch (e) {
      setStatus({ ok: false, msg: e.message });
    }
    setBusy(false); setTimeout(() => setStatus(null), 5000);
  };

  return (
    <div className="send-row">
      <select className="select" value={channel} onChange={(e) => setChannel(e.target.value)}>
        {!channels.length && <option value="">no channels found</option>}
        {channels.map((c) => <option key={c.id} value={c.id}>#{c.name}</option>)}
      </select>
      <button className="btn" disabled={busy || !channel} onClick={sendChannel}>
        {busy ? "…" : "Post to channel"}
      </button>
      {status && <span className={"send-status " + (status.ok ? "ok" : "bad")}>{status.msg}</span>}
    </div>
  );
}

function DmControls({ entry }) {
  const [members, setMembers] = useState([]);
  const [member, setMember] = useState("");
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/discord/members").then((d) => {
      setMembers(d.members || []);
      if (d.members?.length) setMember(String(d.members[0].id));
    }).catch(() => {});
  }, []);

  const sendDm = async () => {
    if (!member) return;
    setBusy(true); setStatus(null);
    try {
      const r = await fetch("/api/discord/dm", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ user_id: Number(member), content: entry.message }),
      });
      const d = await r.json();
      setStatus(r.ok && d.ok
        ? { ok: true, msg: `DM sent to ${d.user || member}` }
        : { ok: false, msg: d.error || `HTTP ${r.status}` });
    } catch (e) {
      setStatus({ ok: false, msg: e.message });
    }
    setBusy(false); setTimeout(() => setStatus(null), 5000);
  };

  return (
    <div className="send-row">
      <select className="select" value={member} onChange={(e) => setMember(e.target.value)}>
        {!members.length && <option value="">no members found</option>}
        {members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
      </select>
      <button className="btn" disabled={busy || !member} onClick={sendDm}>
        {busy ? "…" : "Send as DM"}
      </button>
      {status && <span className={"send-status " + (status.ok ? "ok" : "bad")}>{status.msg}</span>}
    </div>
  );
}

export default function Guide() {
  const [tab, setTab] = useState("Members");
  const audiences = Object.keys(GUIDE_BY_AUDIENCE);

  return (
    <>
      <div className="notice">
        <strong>Drop-in teaching messages.</strong> Copy any block into Discord yourself,
        or use <b>Post to channel</b> / <b>Send as DM</b> and the bot delivers it — Discord
        renders the markdown exactly as members see it. The dashboard talks to the
        Discord API through the bot's own token (never exposed to the browser).
      </div>

      <div className="tabs">
        {audiences.map((a) => (
          <button key={a} className={"tab" + (tab === a ? " active" : "")}
                  onClick={() => setTab(a)}>
            {a} <span className="dim">({GUIDE_BY_AUDIENCE[a].length})</span>
          </button>
        ))}
      </div>

      {GUIDE_BY_AUDIENCE[tab].map((g) => (
        <Card key={g.id}
              title={g.title}
              right={<Badge tone={AUD_TONE[g.audience]}>{g.audience}</Badge>}>
          <p className="dim small">{g.blurb}</p>
          <pre className="guide-pre">{g.message}</pre>
          <div className="guide-actions">
            <CopyButton text={g.message} />
            <CopyButton text={g.message.replace(/\*\*/g, "")} label="Copy plain" />
          </div>
          <SendControls entry={g} />
          <DmControls entry={g} />
        </Card>
      ))}
    </>
  );
}
