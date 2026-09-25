import React, { useEffect, useRef, useState } from 'react'

const REPO = 'https://github.com/THEROCKSSS/typesafe-ai-bot'

// Scene boundaries from docs/narration/timeline.json (the reel's own edit).
const SCENES = [
  { t: 0,      name: 'The hook' },
  { t: 11730,  name: 'What it watches' },
  { t: 26300,  name: 'The five steps' },
  { t: 39630,  name: 'Automod catch' },
  { t: 56120,  name: 'Voice moderation' },
  { t: 69470,  name: 'Community vote' },
  { t: 83000,  name: 'Alert routing' },
  { t: 98910,  name: 'Setup in 4' },
  { t: 111680, name: 'The receipts' },
]

const STEPS = [
  ['01', 'Screened in one call', 'Every enabled rule rides in a single batched AI call — the message never waits on a queue of per-rule models.'],
  ['02', 'Probability, not punishment', 'The model returns a confidence per rule. It has never muted anyone and never will: it only suggests.'],
  ['03', 'Code owns the bands', 'At ≥0.85 plain code acts, at ≥0.60 it logs for review, below that it stays quiet. The numbers are yours in .env.'],
  ['04', 'Every action leaves a trail', 'Action, reason, names, timestamp — a case record with a jump link back to the original message.'],
]

const SHOTS = [
  ['demo-cases.png', 'Case log', 'Every decision with action, kind, reason and mode — click through the audit trail.'],
  ['demo-votes.png', 'Live votes', 'Vote tallies with thresholds, running unattended on their 10-minute clock.'],
  ['briefing-vote.png', 'The member view', 'The embed members actually see in Discord when a case goes to vote.'],
  ['briefing-pipeline.png', 'The chain', 'Heuristic floor, AI layer, bands, case record — how a decision gets made.'],
]

function fmt(ms) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function App() {
  const videoRef = useRef(null)
  const [active, setActive] = useState(0)

  const seek = (i) => {
    const v = videoRef.current
    if (!v) return
    v.currentTime = SCENES[i].t / 1000
    v.play().catch(() => {})
    setActive(i)
  }

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onTime = () => {
      const ms = v.currentTime * 1000
      for (let i = SCENES.length - 1; i >= 0; i--) {
        if (ms >= SCENES[i].t - 400) { setActive(i); break }
      }
    }
    v.addEventListener('timeupdate', onTime)
    return () => v.removeEventListener('timeupdate', onTime)
  }, [])

  return (
    <>
      <nav className="nav">
        <a className="brand" href="#top" aria-label="TypeSafe AI Bot — top of page">
          <span className="mark" aria-hidden="true">TS</span>
          <span>TypeSafe <b>AI Bot</b></span>
        </a>
        <div className="nav-links">
          <a href="#demo">Demo</a>
          <a href="#how">How it works</a>
          <a href="#shots">Screens</a>
          <a href="#setup">Setup</a>
          <a className="ghost" href={REPO} rel="noreferrer">GitHub ↗</a>
        </div>
      </nav>

      <header className="hero" id="top">
        <p className="kick"><span className="d" />self-hosted · single-guild · MIT</p>
        <h1>Reads your rules.<br /><em>Shows the receipts.</em></h1>
        <p className="lede">
          TypeSafe screens chat and voice against <b>your server's written rulebook</b>,
          asks an AI to score each rule — and lets plain, auditable code decide what happens.
          Every action is a case record with a reason. Serious calls go to a community vote.
        </p>
        <div className="cta">
          <a className="btn primary" href="#demo">▶&ensp;Watch the 2-minute demo</a>
          <a className="btn" href={REPO} rel="noreferrer">View on GitHub</a>
        </div>
        <dl className="stats">
          <div title="pytest unit + mocked-Discord integration tests, run in CI on every push">
            <dt>89</dt><dd>automated tests</dd>
          </div>
          <div title="Slash commands across everyone / moderator / owner roles">
            <dt>17</dt><dd>slash commands</dd>
          </div>
          <div title="Vote thresholds: 5 votes minimum, 60% to pass, 10-minute window — all configurable">
            <dt>5 · 60% · 10′</dt><dd>vote quorum · pass · window</dd>
          </div>
          <div title="The bot runs on your hardware with your keys; the dashboard binds to 127.0.0.1 only">
            <dt>0</dt><dd>cloud dependencies</dd>
          </div>
        </dl>
      </header>

      <section className="demo" id="demo">
        <h2>The reel</h2>
        <p className="sub">
          Two minutes, narrated, built from the live decision engine. Footage anonymized;
          numbers are from the real case database.
        </p>
        <div className="player">
          <video
            ref={videoRef}
            controls
            preload="metadata"
            playsInline
            poster="briefing-hero.png"
            src="demo-reel-v3.mp4"
          />
          <ol className="chapters" aria-label="Video chapters">
            {SCENES.map((s, i) => (
              <li key={s.name}>
                <button
                  className={i === active ? 'on' : ''}
                  onClick={() => seek(i)}
                  title={`Jump to ${fmt(s.t)} — ${s.name}`}
                >
                  <span className="t">{fmt(s.t)}</span>{s.name}
                </button>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="how" id="how">
        <h2>How a decision gets made</h2>
        <div className="grid">
          {STEPS.map(([n, h, b]) => (
            <article key={n}>
              <span className="n" aria-hidden="true">{n}</span>
              <h3>{h}</h3>
              <p>{b}</p>
            </article>
          ))}
        </div>
        <div className="nuke">
          <h3>Server-wide actions are two-tier by design</h3>
          <p>
            Mass role deletion, channel deletion, webhook floods: the <b>heuristic floor</b> acts
            first — under a second, model-free, no AI in the loop — and a community vote confirms or
            vetoes. Nothing waits on a prompt to stop a nuke.
          </p>
        </div>
      </section>

      <section className="shots" id="shots">
        <h2>What you'll be running</h2>
        <div className="wall">
          {SHOTS.map(([src, h, b]) => (
            <figure key={src}>
              <a href={src} target="_blank" rel="noreferrer" title={`Open ${h} full size`}>
                <img src={src} alt={h} loading="lazy" />
              </a>
              <figcaption><b>{h}</b> — {b}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="setup" id="setup">
        <h2>Four steps to your server</h2>
        <ol className="steps">
          <li><code>git clone {REPO}.clone && cd typesafe-ai-bot</code></li>
          <li><code>python -m venv .venv && pip install -r requirements.txt</code></li>
          <li><code>copy .env.example .env</code> — fill the Discord token + your bot's guild ID</li>
          <li><code>python -m pytest tests -q && python -m tsabot.main</code> — 89 green, then it's live in dry-run</li>
        </ol>
        <p className="note">
          <b>Dry-run is the default.</b> The bot logs and reports without touching anyone until
          you flip <code>DRY_RUN=0</code> yourself. Rulebook, bands, vote math and alert routing are
          all yours to set — <code>policy/rules.json</code> is a starting point, not a doctrine.
        </p>
        <p className="sub docs">
          Full guide in <a href={`${REPO}/blob/main/docs/SETUP.md`} rel="noreferrer">docs/SETUP.md</a> ·
          spec in <a href={`${REPO}/blob/main/docs/SPEC.md`} rel="noreferrer">docs/SPEC.md</a>.
        </p>
      </section>

      <footer>
        <span className="mark sm" aria-hidden="true">TS</span>
        <p>
          TypeSafe AI Bot · MIT · self-hosted.<br />
          Reads your rules. Shows the receipts.
        </p>
      </footer>
    </>
  )
}
