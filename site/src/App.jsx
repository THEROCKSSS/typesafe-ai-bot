import React, { useEffect, useMemo, useRef, useState } from 'react'

const REPO = 'https://github.com/THEROCKSSS/typesafe-ai-bot'
const IMG = (n) => `${import.meta.env.BASE_URL}${n}`

// Scene boundaries (from the reel's own edit, ms)
const SCENES = [
  [0, 11730, 'The hook'],
  [11730, 26300, 'What it does'],
  [26300, 39630, 'The five steps'],
  [39630, 56120, 'Chat use-cases'],
  [56120, 69470, 'Voice + nukes'],
  [69470, 83000, 'Community vote'],
  [83000, 98910, 'Alert routing'],
  [98910, 111680, 'Setup in four'],
  [116280, 121920, 'The receipts'],
]

function fmt(ms) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/* ── motion utilities ─────────────────────────────────────────────── */

function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const mq = matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}

function Reveal({ children, className = '', as: Tag = 'div', once = true, ...rest }) {
  const ref = useRef(null)
  const [shown, setShown] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { setShown(true); return }
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setShown(true); if (once) io.disconnect() } },
      { threshold: 0.16, rootMargin: '0px 0px -8% 0px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [once])
  return (
    <Tag ref={ref} className={`reveal ${shown ? 'is-in' : ''} ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

function useCountUp(target, { duration = 1200 } = {}) {
  const ref = useRef(null)
  const [val, setVal] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return
      io.disconnect()
      if (reduced) { setVal(target); return }
      const t0 = performance.now()
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / duration)
        setVal(Math.round(target * (1 - Math.pow(1 - p, 3))))
        if (p < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    }, { threshold: 0.6 })
    io.observe(el)
    return () => io.disconnect()
  }, [target, duration])
  return [val, ref]
}

function Stat({ value, label, mono, decimals = 0 }) {
  const [n, ref] = useCountUp(value)
  return (
    <div className="stat" ref={ref}>
      <span className="stat__num">
        {decimals ? (n / 10 ** decimals).toFixed(decimals) : n}
      </span>
      <span className="stat__label">{label}</span>
    </div>
  )
}

/* ── signature: the screening field ─────────────────────────────────
   Hand-built 2D canvas. Message packets drift through a rule lattice;
   a flagged packet pulses a verdict ring. Pointer-reactive, pauses off-
   screen and under prefers-reduced-motion, ~2 KB, no WebGL dependency. */

function ScreeningField() {
  const wrapRef = useRef(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      canvas.classList.add('is-static')
      return
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let W = 0, H = 0, dpr = 1, raf = 0, live = false
    const pointer = { x: 0.72, y: 0.3, on: false }
    let nodes = [], edges = [], verdict = null, verdictT = 0, nextVerdict = 2.2

    const css = getComputedStyle(document.documentElement)
    const col = (name, fb) => (css.getPropertyValue(name) || fb).trim()
    const INK = col('--ink', '#e9efe9'), MINT = col('--accent', '#7fe0b5')
    const AMBER = col('--highlight', '#ffb454'), DIM = col('--ink-faint', '#43514a')

    function seed() {
      const n = Math.max(20, Math.round(W / H * 24))
      nodes = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 7, vy: (Math.random() - 0.5) * 7,
        r: Math.random() < 0.18 ? 2.4 : 1.4,
        f: Math.random() < 0.12,
        p: Math.random() * Math.PI * 2,
      }))
      edges = []
      for (let i = 0; i < nodes.length; i++)
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d < Math.min(W, H) * 0.17) edges.push([i, j, d])
        }
    }

    function resize() {
      dpr = Math.min(2, devicePixelRatio || 1)
      W = wrap.clientWidth; H = wrap.clientHeight
      canvas.width = Math.max(1, W * dpr); canvas.height = Math.max(1, H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      seed()
    }

    function step(dt, t) {
      for (const nd of nodes) {
        nd.x += nd.vx * dt; nd.y += nd.vy * dt
        if (nd.x < 0) nd.x += W; if (nd.x > W) nd.x -= W
        if (nd.y < 0) nd.y += H; if (nd.y > H) nd.y -= H
      }
      if (pointer.on) {
        const px = pointer.x * W, py = pointer.y * H
        const R = Math.min(W, H) * 0.3
        for (const nd of nodes) {
          const dx = nd.x - px, dy = nd.y - py
          const d = Math.hypot(dx, dy) || 1
          if (d < R) { const push = (1 - d / R) * 16 * dt; nd.x += (dx / d) * push; nd.y += (dy / d) * push }
        }
      }
      // verdict pulse: a flagged packet resolves every few seconds
      nextVerdict -= dt
      if (!verdict && nextVerdict <= 0) {
        const flagged = nodes.filter((nd) => nd.f)
        if (flagged.length) { verdict = flagged[Math.floor(Math.random() * flagged.length)]; verdictT = 0 }
        nextVerdict = 3.4 + Math.random() * 2.6
      }
      if (verdict) {
        verdictT += dt
        if (verdictT > 2.4) { verdict = null; verdictT = 0 }
      }
    }

    function draw(t) {
      ctx.clearRect(0, 0, W, H)
      const px = pointer.on ? pointer.x * W : W * 0.72
      const py = pointer.on ? pointer.y * H : H * 0.3
      const g = ctx.createRadialGradient(px, py, 0, px, py, Math.min(W, H) * 0.7)
      g.addColorStop(0, 'rgba(127,224,181,0.075)'); g.addColorStop(1, 'rgba(127,224,181,0)')
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)

      ctx.lineWidth = 1
      for (const [i, j, d] of edges) {
        const a = nodes[i], b = nodes[j]
        const dx = a.x - b.x, dy = a.y - b.y
        const dd = Math.hypot(dx, dy)
        if (dd > Math.min(W, H) * 0.22) continue
        const near = Math.hypot((a.x + b.x) / 2 - px, (a.y + b.y) / 2 - py) < 160
        ctx.strokeStyle = near ? 'rgba(127,224,181,0.28)' : 'rgba(67,81,74,0.4)'
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
      }
      for (const nd of nodes) {
        const w = 0.6 + 0.4 * Math.sin(t * 1.6 + nd.p)
        ctx.fillStyle = nd.f
          ? `rgba(255,180,84,${0.55 + 0.35 * w})`
          : `rgba(233,239,233,${0.32 + 0.3 * w})`
        ctx.beginPath(); ctx.arc(nd.x, nd.y, nd.r, 0, Math.PI * 2); ctx.fill()
      }
      if (verdict) {
        const p = verdictT / 2.4
        const rr = 10 + p * 58
        ctx.strokeStyle = `rgba(255,180,84,${(1 - p) * 0.8})`
        ctx.lineWidth = 1.4
        ctx.beginPath(); ctx.arc(verdict.x, verdict.y, rr, 0, Math.PI * 2); ctx.stroke()
        if (p < 0.5) {
          ctx.fillStyle = `rgba(255,180,84,${(0.5 - p) * 1.6})`
          ctx.beginPath(); ctx.arc(verdict.x, verdict.y, 3, 0, Math.PI * 2); ctx.fill()
        }
      }
    }

    let last = 0
    function frame(t) {
      const dt = Math.min(0.05, (t - last) / 1000 || 0.016); last = t
      step(dt, t / 1000); draw(t / 1000)
      if (live) raf = requestAnimationFrame(frame)
    }

    const onMove = (e) => {
      const r = wrap.getBoundingClientRect()
      pointer.x = (e.clientX - r.left) / r.width
      pointer.y = (e.clientY - r.top) / r.height
      pointer.on = true
    }
    const onLeave = () => { pointer.on = false }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !live) { live = true; last = performance.now(); raf = requestAnimationFrame(frame) }
      else if (!e.isIntersecting && live) { live = false; cancelAnimationFrame(raf) }
    }, { threshold: 0.05 })

    const ro = new ResizeObserver(resize)
    ro.observe(wrap)
    resize()
    io.observe(wrap)
    wrap.addEventListener('pointermove', onMove)
    wrap.addEventListener('pointerleave', onLeave)
    return () => {
      live = false; cancelAnimationFrame(raf)
      io.disconnect(); ro.disconnect()
      wrap.removeEventListener('pointermove', onMove)
      wrap.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  return (
    <div className="field" ref={wrapRef} aria-hidden="true">
      <canvas ref={canvasRef} />
      <svg className="field__grain" xmlns="http://www.w3.org/2000/svg">
        <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="2" stitchTiles="stitch" /></filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
      <span className="field__tag">screening 31 messages/minute · 4 rules active</span>
    </div>
  )
}

/* ── chrome ────────────────────────────────────────────────────────── */

function Nav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    let last = -1
    const onScroll = () => {
      const s = window.scrollY > 24
      if (s !== last) { setScrolled(s); last = s }
    }
    onScroll()
    addEventListener('scroll', onScroll, { passive: true })
    return () => removeEventListener('scroll', onScroll)
  }, [])
  return (
    <header className="nav">
      <div className="shell nav__inner">
        <a className="brand" href="#top" aria-label="TypeSafe AI Bot — home">
          <span className="brand__mark" aria-hidden="true">TS</span>
          <span className="brand__word">TypeSafe <em>AI Bot</em></span>
        </a>
        <nav className="nav__links" aria-label="Sections">
          <a href="#reel">Reel</a>
          <a href="#engine">How it works</a>
          <a href="#proof">Screens</a>
          <a href="#setup">Setup</a>
        </nav>
        <a className="btn btn--ghost nav__cta" href={REPO} rel="noopener">
          GitHub <span aria-hidden="true">↗</span>
        </a>
      </div>
      <span className={`nav__bar ${scrolled ? 'is-scrolled' : ''}`} aria-hidden="true" />
    </header>
  )
}

function Hero() {
  return (
    <section className="hero" id="top">
      <ScreeningField />
      <div className="shell hero__inner">
        <p className="hero__meta load" style={{ '--i': 0 }}>self-hosted · single-guild · MIT — and it stays in your server</p>
        <h1 className="hero__display load" style={{ '--i': 1 }}>
          Reads your rules.<br />
          <span className="hero__display-2">Shows the receipts.</span>
        </h1>
        <p className="hero__lede load" style={{ '--i': 2 }}>
          TypeSafe screens chat and voice against <strong>your server's written rulebook</strong>,
          asks an AI to score each rule — and lets plain, auditable code decide what happens.
          Every action is a case record with a reason. Serious calls go to a community vote.
        </p>
        <div className="hero__actions load" style={{ '--i': 3 }}>
          <a className="btn btn--solid" href="#reel">▶&nbsp;&nbsp;Watch the 2-minute demo</a>
          <a className="btn btn--ghost" href={REPO} rel="noopener">View on GitHub</a>
        </div>
        <dl className="hero__stats load" style={{ '--i': 4 }}>
          <Stat value={89} label="automated tests" />
          <span className="stat__sep" aria-hidden="true" />
          <Stat value={17} label="slash commands" />
          <span className="stat__sep" aria-hidden="true" />
          <div className="stat"><span className="stat__num stat__num--mono">5 · 60% · 10′</span><span className="stat__label">vote quorum · pass · window</span></div>
          <span className="stat__sep" aria-hidden="true" />
          <Stat value={0} label="cloud dependencies" />
        </dl>
      </div>
      <div className="hero__cue" aria-hidden="true"><span></span>scroll</div>
    </section>
  )
}
/* ── the reel ──────────────────────────────────────────────────────── */

function Reel() {
  const vidRef = useRef(null)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    const v = vidRef.current
    if (!v) return
    const onT = () => setT(v.currentTime * 1000)
    const onP = () => setPlaying(true)
    const onPause = () => { setPlaying(false); onT() }
    v.addEventListener('timeupdate', onT)
    v.addEventListener('seeked', onT)
    v.addEventListener('play', onP)
    v.addEventListener('pause', onPause)
    return () => {
      v.removeEventListener('timeupdate', onT)
      v.removeEventListener('seeked', onT)
      v.removeEventListener('play', onP)
      v.removeEventListener('pause', onPause)
    }
  }, [])

  const seek = (ms) => {
    const v = vidRef.current
    if (!v) return
    v.currentTime = ms / 1000
    v.play().catch(() => {})
  }

  const active = SCENES.findIndex(([a, b]) => t >= a && t < b)

  return (
    <section className="reel" id="reel">
      <div className="shell">
        <Reveal className="reel__head">
          <h2 className="h2">The reel</h2>
          <p className="section-lede">
            Two minutes, narrated, built from the live decision engine.
            Footage anonymized; numbers are from the real case database.
          </p>
        </Reveal>
        <Reveal className="reel__grid" style={{ '--reveal-delay': '80ms' }}>
          <figure className="reel__frame">
            <video
              ref={vidRef}
              controls
              preload="metadata"
              playsInline
              poster={IMG('poster-16x9.png')}
              aria-label="Two-minute demo of TypeSafe AI Bot"
            >
              <source src={IMG('demo-reel-v3.mp4')} type="video/mp4" />
            </video>
            <div className="reel__progress" aria-hidden="true">
              <span style={{ transform: `scaleX(${Math.min(1, t / 121920)})` }} />
            </div>
            <figcaption className="reel__readout">
              <span className="mono">{fmt(t)}</span>
              <span className="reel__readout-title">{active >= 0 ? SCENES[active][2] : playing ? 'The receipts' : 'Paused'}</span>
              <span className="mono reel__readout-dur">02:01</span>
            </figcaption>
          </figure>
          <ol className="chapters" aria-label="Video chapters">
            {SCENES.map(([ms, end, label], i) => (
              <li key={ms}>
                <button
                  type="button"
                  className={`chapter ${i === active ? 'is-active' : ''}`}
                  onClick={() => seek(ms)}
                  aria-current={i === active ? 'true' : undefined}
                >
                  <span className="chapter__t mono">{fmt(ms)}</span>
                  <span className="chapter__l">{label}</span>
                  <span className="chapter__bar" aria-hidden="true">
                    <span
                      style={{
                        transform: `scaleX(${i === active ? Math.min(1, (t - ms) / (end - ms)) : t >= end ? 1 : 0})`,
                      }}
                    />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </Reveal>
      </div>
    </section>
  )
}

/* ── the engine: feature-stack (sticky copy, scrolling proof) ─────── */

const STEPS = [
  {
    k: 'detect',
    t: 'Every message is a case waiting to happen',
    d: 'Chat, voice and reports all land in the same pipeline. No rulebook parsing, no training data — it reads the rules you already wrote, the way your mods read them.',
    img: 'briefing-hero.png', cap: 'A live screening pass — four rules scored, one flagged.',
  },
  {
    k: 'judge',
    t: 'A heuristic floor, then an AI layer',
    d: 'A keyword and pattern floor catches the obvious. An AI judge then scores each rule 0–1 with a one-line reason. If the model is down, the heuristic floor still holds — the bot never goes blind.',
    img: 'briefing-pipeline.png', cap: 'Heuristic floor → AI layer → bands → case record.',
  },
  {
    k: 'decide',
    t: 'Bands decide, not vibes',
    d: 'Scores map to your configured bands: warn, timeout, vote, or strike. The bot logs its own reasoning on every action — what fired, what it cost, which path it chose. That log is the product.',
    img: 'demo-cases.png', cap: 'Every decision, actioned with a reason.',
  },
  {
    k: 'vote',
    t: 'Serious calls go to the guild',
    d: 'High-severity cases open a community vote with a quorum, a pass threshold and a clock. Members see the embed; mods see the tally. 5 members · 60% to pass · 10-minute window — yours to retune.',
    img: 'briefing-vote.png', cap: 'The member-facing vote embed.',
  },
]

function Engine() {
  const [activeK, setActiveK] = useState(STEPS[0].k)
  const [seen, setSeen] = useState(0) // bitmask of slides that have entered view
  const refs = useRef([])

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const idx = Number(e.target.dataset.i)
          if (e.isIntersecting) {
            setActiveK(e.target.dataset.k)
            setSeen((m) => m | (1 << idx))
          }
        }
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 },
    )
    refs.current.forEach((el) => el && io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <section className="engine" id="engine">
      <div className="shell engine__grid">
        <div className="engine__copy">
          <div className="engine__sticky">
            <h2 className="h2">How a decision<br />actually gets made</h2>
            <p className="section-lede">
              Five stages, plain code end to end. Scroll the proof →
            </p>
            <ol className="engine__rail" aria-hidden="true">
              {STEPS.map((s, i) => (
                <li key={s.k} className={activeK === s.k ? 'is-active' : ''}>
                  <span className="mono">0{i + 1}</span> {s.t.split(' ').slice(0, 3).join(' ')}…
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className="engine__stack">
          {STEPS.map((s, i) => (
            <figure
              className={`engine__slide reveal ${seen & (1 << i) ? 'is-in' : ''} ${activeK === s.k ? 'is-active' : ''}`}
              data-k={s.k}
              data-i={i}
              key={s.k}
              ref={(el) => (refs.current[i] = el)}
            >
              <span className="engine__num mono" aria-hidden="true">0{i + 1}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
              <img src={IMG(s.img)} alt={s.cap} loading="lazy" />
              <figcaption>{s.cap}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── proof: the screens you run ────────────────────────────────────── */

const PROOF = [
  { img: 'demo-cases.png', t: 'Case log', d: 'Every decision with action, kind, reason and mode — click through the audit trail.' },
  { img: 'demo-votes.png', t: 'Live votes', d: 'Vote tallies with thresholds, running unattended on their 10-minute clock.' },
  { img: 'briefing-vote.png', t: 'The member view', d: 'The embed members actually see in Discord when a case goes to vote.' },
]

function Proof() {
  return (
    <section className="proof" id="proof">
      <div className="shell">
        <Reveal>
          <h2 className="h2">What you'll be running</h2>
        </Reveal>
        <div className="proof__grid">
          {PROOF.map((p, i) => (
            <Reveal key={p.img} className="proof__item" style={{ '--reveal-delay': `${i * 90}ms` }} as="figure">
              <a href={IMG(p.img)} target="_blank" rel="noopener" title={`Open ${p.t} full size`}>
                <img src={IMG(p.img)} alt={`${p.t} screenshot`} loading="lazy" />
              </a>
              <figcaption><strong>{p.t}</strong> — {p.d}</figcaption>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── setup ─────────────────────────────────────────────────────────── */

const COMMANDS = [
  { i: 1, c: 'git clone https://github.com/THEROCKSSS/typesafe-ai-bot.git && cd typesafe-ai-bot' },
  { i: 2, c: 'python -m venv .venv && pip install -r requirements.txt' },
  { i: 3, c: 'copy .env.example .env', note: 'fill the Discord token + your bot’s guild ID' },
  { i: 4, c: 'python -m pytest tests -q && python -m tsabot.main', note: '89 green, then it’s live in dry-run' },
]

function Setup() {
  const [copied, setCopied] = useState(null)
  const copy = (i, text) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(i)
      setTimeout(() => setCopied(null), 1600)
    })
  }
  return (
    <section className="setup" id="setup">
      <div className="shell setup__grid">
        <Reveal className="setup__copy">
          <h2 className="h2">Four steps to your server</h2>
          <p className="section-lede">
            <strong>Dry-run is the default.</strong> The bot logs and reports without touching
            anyone until you flip <code className="mono">DRY_RUN=0</code> yourself. Rulebook, bands,
            vote math and alert routing are all yours to set — <code className="mono">policy/rules.json</code> is a starting point, not a doctrine.
          </p>
          <p className="setup__links">
            Full guide in <a href={`${REPO}/blob/main/docs/SETUP.md`} rel="noopener">docs/SETUP.md</a>
            {' · '}spec in <a href={`${REPO}/blob/main/docs/SPEC.md`} rel="noopener">docs/SPEC.md</a>.
          </p>
        </Reveal>
        <Reveal className="setup__steps" as="ol" style={{ '--reveal-delay': '80ms' }}>
          {COMMANDS.map((s) => (
            <li className="step" key={s.i}>
              <span className="step__n mono" aria-hidden="true">{s.i}</span>
              <div className="step__body">
                <code className="mono">{s.c}</code>
                {s.note && <span className="step__note">{s.note}</span>}
              </div>
              <button type="button" className="step__copy" onClick={() => copy(s.i, s.c)} aria-label={`Copy step ${s.i}`}>
                {copied === s.i ? 'copied' : 'copy'}
              </button>
            </li>
          ))}
        </Reveal>
      </div>
    </section>
  )
}

/* ── footer (Ft5 · statement) ─────────────────────────────────────── */

function Footer() {
  return (
    <footer className="footer">
      <div className="shell">
        <p className="footer__statement">
          Reads your rules.<br />
          <span>Shows the receipts.</span>
        </p>
        <div className="footer__line">
          <span className="mono">TypeSafe AI Bot · MIT · self-hosted</span>
          <a className="btn btn--ghost" href={REPO} rel="noopener">Source on GitHub <span aria-hidden="true">↗</span></a>
        </div>
      </div>
    </footer>
  )
}

export default function App() {
  // JS fallback for browsers without scroll-timeline
  useEffect(() => {
    if (CSS.supports('animation-timeline', 'scroll()')) return
    const fill = document.getElementById('scrollbar-fill')
    if (!fill) return
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - innerHeight
      fill.style.transform = `scaleX(${max > 0 ? scrollY / max : 0})`
    }
    onScroll()
    addEventListener('scroll', onScroll, { passive: true })
    return () => removeEventListener('scroll', onScroll)
  }, [])

  return (
    <>
      <div className="scrollbar" aria-hidden="true"><span id="scrollbar-fill" /></div>
      <Nav />
      <main>
        <Hero />
        <Reel />
        <Engine />
        <Proof />
        <Setup />
      </main>
      <Footer />
    </>
  )
}
