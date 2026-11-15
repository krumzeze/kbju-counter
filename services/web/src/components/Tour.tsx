import { useIsFetching, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { Me } from "../api/types";
import { tr } from "../lib/i18n";
import { useMe } from "../lib/queries";
import { TOURS, type TourStep } from "../lib/tours";

interface Run {
  steps: TourStep[];
  tourIds: string[];
  index: number;
}

const POLL_MS = 300;
const GIVE_UP_MS = 10_000;
const PAD = 6;
const GAP = 12;
const CARD_MAX = 360;
const SCROLL_TOP = 96;

const find = (target: string) => document.querySelector<HTMLElement>(`[data-tour="${target}"]`);
const visible = (el: HTMLElement | null): el is HTMLElement => !!el && el.getClientRects().length > 0;

/** Spotlight hints for the current screen, shown once per tour id. */
export function TourHost() {
  const { data: me } = useMe();
  const { pathname } = useLocation();
  const fetching = useIsFetching();
  const fetchingRef = useRef(fetching);
  fetchingRef.current = fetching;
  const [run, setRun] = useState<Run | null>(null);
  const client = useQueryClient();
  const markSeen = useMutation({
    mutationFn: (ids: string[]) => api.markTourSeen(ids),
    onMutate: (ids) =>
      client.setQueryData<Me>(["me"], (m) => m && { ...m, tour_seen: [...m.tour_seen, ...ids] }),
    onSuccess: (fresh) => client.setQueryData(["me"], fresh),
  });

  const pendingKey = useMemo(() => {
    if (!me) return "";
    return TOURS.filter((t) => t.path === pathname && !me.tour_seen.includes(t.id))
      .map((t) => t.id)
      .join(",");
  }, [me, pathname]);

  useEffect(() => {
    setRun(null);
    if (!pendingKey) return;
    const tours = TOURS.filter((t) => pendingKey.split(",").includes(t.id));
    const started = Date.now();
    let timer: number;
    const tick = () => {
      const settled = fetchingRef.current === 0 && !document.querySelector(".spinner");
      if (settled) {
        const shown = tours
          .map((t) => ({ id: t.id, steps: t.steps.filter((s) => visible(find(s.target))) }))
          .filter((t) => t.steps.length > 0);
        if (shown.length) {
          setRun({ steps: shown.flatMap((t) => t.steps), tourIds: shown.map((t) => t.id), index: 0 });
          return;
        }
      }
      if (Date.now() - started < GIVE_UP_MS) timer = window.setTimeout(tick, POLL_MS);
    };
    timer = window.setTimeout(tick, POLL_MS * 2);
    return () => window.clearTimeout(timer);
  }, [pendingKey]);

  if (!run) return null;
  const finish = () => {
    markSeen.mutate(run.tourIds);
    setRun(null);
  };
  const next = () => (run.index + 1 < run.steps.length ? setRun({ ...run, index: run.index + 1 }) : finish());
  return <Spotlight key={run.index} step={run.steps[run.index]} index={run.index} total={run.steps.length} onNext={next} onSkip={finish} />;
}

function Spotlight({
  step,
  index,
  total,
  onNext,
  onSkip,
}: {
  step: TourStep;
  index: number;
  total: number;
  onNext: () => void;
  onSkip: () => void;
}) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [cardHeight, setCardHeight] = useState(0);
  const nextButton = useRef<HTMLButtonElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const last = index + 1 === total;

  useLayoutEffect(() => {
    const el = find(step.target);
    if (!visible(el)) {
      onNext();
      return;
    }
    const margin = el.style.scrollMarginTop;
    el.style.scrollMarginTop = `${SCROLL_TOP}px`;
    el.scrollIntoView({ block: "start", behavior: "instant" });
    el.style.scrollMarginTop = margin;
    const measure = () => setRect(el.getBoundingClientRect());
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [step]);

  useLayoutEffect(() => {
    const h = card.current?.offsetHeight ?? 0;
    if (h !== cardHeight) setCardHeight(h);
  });

  useEffect(() => {
    nextButton.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onSkip();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSkip]);

  if (!rect) return null;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const top = Math.max(rect.top - PAD, 4);
  const hole = {
    top,
    left: Math.max(rect.left - PAD, 4),
    width: Math.min(rect.width + PAD * 2, vw - 8),
    height: Math.min(rect.bottom + PAD, vh - 4) - top,
  };
  const width = Math.min(CARD_MAX, vw - 32);
  const left = Math.min(Math.max(rect.left + rect.width / 2 - width / 2, 16), vw - width - 16);
  const below = hole.top + hole.height + GAP;
  const above = hole.top - GAP - cardHeight;
  const cardTop =
    below + cardHeight <= vh - 16
      ? below
      : above >= 16
        ? above
        : Math.min(Math.max(below, 16), vh - cardHeight - 16);

  return (
    <div className="tour" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-text">
      <div className="tour-hole" style={hole} />
      <div ref={card} className="tour-card" style={{ top: cardTop, left, width }}>
        <p className="tour-count">
          {index + 1} / {total}
        </p>
        <h3 id="tour-title">{tr(...step.title)}</h3>
        <p id="tour-text">{tr(...step.text)}</p>
        <div className="tour-actions">
          {!last && (
            <button type="button" className="btn-ghost" onClick={onSkip}>
              {tr("Пропустить", "Skip")}
            </button>
          )}
          <button ref={nextButton} type="button" className="btn btn-primary small" onClick={onNext}>
            {last ? tr("Понятно", "Got it") : tr("Далее", "Next")}
          </button>
        </div>
      </div>
    </div>
  );
}
