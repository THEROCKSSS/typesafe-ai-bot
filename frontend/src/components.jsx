export function Badge({ tone = "", children, title }) {
  return <span className={`badge ${tone}`} title={title}>{children}</span>;
}

export function Card({ title, right, children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      {(title || right) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {right && <span className="card-right">{right}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, note, tone = "", title }) {
  return (
    <div className={`card kpi ${tone}`} title={title}>
      <span className="k-label">{label}</span>
      <span className="k-value">{value}</span>
      {note && <span className="k-note">{note}</span>}
    </div>
  );
}

export function BarRow({ label, value, max, tone = "", title }) {
  const pct = max > 0 ? Math.max(value ? 3 : 0, Math.round((value / max) * 100)) : 0;
  return (
    <div className="bar-row">
      <span className="bar-label" title={label}>{label}</span>
      <span className="bar-track">
        <span className={`bar-fill ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="bar-count" title={title || `${value} of ${max}`}>{value}</span>
    </div>
  );
}

export function Empty({ title = "Nothing here yet", hint = "Data appears as the bot runs. DRY-RUN logs decisions without enforcing them." }) {
  return (
    <div className="empty">
      <div className="empty-glyph">◌</div>
      <p className="empty-title">{title}</p>
      <p className="empty-hint">{hint}</p>
    </div>
  );
}

export function ErrorBox({ message }) {
  return (
    <div className="notice err">
      <strong>Could not load.</strong> {message}
    </div>
  );
}

export function Loading({ what = "data" }) {
  return <div className="loading mono">loading {what}…</div>;
}

/** SVG sparkline with hover tooltips per point. */
export function Sparkline({ values, tone = "accent", height = 56, width = 640, label }) {
  if (!values || !values.length) return null;
  const max = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const pts = values.map((v, i) => [i * step, height - 8 - (v / max) * (height - 18)]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  return (
    <svg className={`spark tone-${tone}`} viewBox={`0 0 ${width} ${height}`}
         preserveAspectRatio="none" role="img"
         aria-label={`${label || "trend"}, latest ${values.at(-1)}`}>
      <path className="area" d={area} />
      <path className="line" d={line} />
      {pts.map(([x, y], i) => (
        <circle key={i} className="pt" cx={x} cy={y} r={i === pts.length - 1 ? 2.8 : 1.6}>
          <title>{`#${i + 1}: ${values[i]}`}</title>
        </circle>
      ))}
    </svg>
  );
}

/** Horizontal donut — pure SVG, no chart lib. */
export function Donut({ segments, size = 148, thickness = 16, center }) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
              stroke="var(--bg-inset)" strokeWidth={thickness} />
      {total > 0 && segments.map((s, i) => {
        const frac = s.value / total;
        const dash = frac * c;
        const el = (
          <circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none"
                  stroke={s.color} strokeWidth={thickness}
                  strokeDasharray={`${dash} ${c - dash}`}
                  strokeDashoffset={-offset}
                  transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            <title>{`${s.label}: ${s.value} (${Math.round(frac * 100)}%)`}</title>
          </circle>
        );
        offset += dash;
        return el;
      })}
      {center && (
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
              className="donut-center">{center}</text>
      )}
    </svg>
  );
}
