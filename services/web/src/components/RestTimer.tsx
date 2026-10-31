import { useCallback, useEffect, useState } from "react";
import { tr } from "../lib/i18n";
import { haptic } from "../lib/telegram";

const KEY = "belok.rest";
const DEFAULT_KEY = "belok.rest.default";

interface Rest {
  endsAt: number;
  total: number;
}

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage unavailable: the timer still works for this page view
  }
}

export function useRestTimer() {
  const [rest, setRest] = useState<Rest | null>(() => load<Rest | null>(KEY, null));
  const [now, setNow] = useState(Date.now());

  const update = useCallback((value: Rest | null) => {
    save(KEY, value);
    setRest(value);
  }, []);

  useEffect(() => {
    if (!rest) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [rest]);

  useEffect(() => {
    if (rest && now >= rest.endsAt) {
      haptic("success");
      navigator.vibrate?.([200, 100, 200]);
      update(null);
    }
  }, [now, rest, update]);

  const start = useCallback(() => {
    const total = load<number>(DEFAULT_KEY, 90);
    update({ endsAt: Date.now() + total * 1000, total });
  }, [update]);

  const adjust = (delta: number) => {
    if (!rest) return;
    const total = Math.max(15, rest.total + delta);
    save(DEFAULT_KEY, total);
    update({ endsAt: Math.max(Date.now() + 1000, rest.endsAt + delta * 1000), total });
  };

  const remaining = rest ? Math.max(0, Math.ceil((rest.endsAt - now) / 1000)) : 0;
  return { active: rest !== null, remaining, total: rest?.total ?? 0, start, adjust, stop: () => update(null) };
}

export function RestBar({ timer }: { timer: ReturnType<typeof useRestTimer> }) {
  if (!timer.active) return null;
  const m = Math.floor(timer.remaining / 60);
  const s = String(timer.remaining % 60).padStart(2, "0");
  return (
    <div className="rest-bar" role="timer" aria-live="off">
      <div className="rest-progress" style={{ width: `${(timer.remaining / timer.total) * 100}%` }} />
      <span className="muted small">{tr("Отдых", "Rest")}</span>
      <strong className="rest-time">
        {m}:{s}
      </strong>
      <button className="chip" onClick={() => timer.adjust(-15)}>
        −15
      </button>
      <button className="chip" onClick={() => timer.adjust(15)}>
        +15
      </button>
      <button className="chip" onClick={timer.stop}>
        {tr("Пропустить", "Skip")}
      </button>
    </div>
  );
}
