import { useEffect, useState } from "react";

export async function api(path) {
  const res = await fetch(path, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

export const fmt = {
  n: (v) => (v ?? 0).toLocaleString(),
  when: (iso) => iso ? new Date(iso).toLocaleString(undefined,
    { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—",
  rel: (iso) => {
    if (!iso) return "—";
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${Math.floor(s)}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  },
  pct: (v, digits = 0) => `${((v ?? 0) * 100).toFixed(digits)}%`,
  usd: (v) => `$${(v ?? 0).toFixed(4)}`,
};

export const ACTION_TONE = {
  timeout: "amber", voice_mute: "indigo", disconnect: "red", warn: "indigo",
  invalid: "", no_action: "", lockdown: "red", review: "amber",
};

/** Re-runs `cb` on mount, on the global Refresh event, and when deps change. */
export function useRefresh(cb, deps = []) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    cb();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);
  useEffect(() => {
    const h = () => setTick((t) => t + 1);
    window.addEventListener("refresh", h);
    return () => window.removeEventListener("refresh", h);
  }, []);
}

/** Tiny fetch-hook: {data, error, loading} + refetch. */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = () => {
    api(path).then((d) => setState({ data: d, error: null, loading: false }))
      .catch((e) => setState({ data: null, error: e.message, loading: false }));
  };
  useRefresh(load, [path, ...deps]);
  return state;
}
