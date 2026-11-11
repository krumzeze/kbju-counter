import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Day } from "../api/types";
import { Avatar } from "../components/Avatar";
import { HomeScreenOffer } from "../components/HomeScreen";
import { Icon } from "../components/Icon";
import { MacroBars } from "../components/MacroBars";
import { MealCard } from "../components/MealCard";
import { ErrorState, Spinner } from "../components/States";
import { STEP_GOAL, count, decimal, round, shiftDay, todayIso } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useDay, useInvalidate, useMe, useWeights } from "../lib/queries";


export function Today() {
  const [day, setDay] = useState(todayIso());
  const { data, isPending, error, refetch } = useDay(day);
  const { data: me } = useMe();
  const isToday = day === todayIso();
  const title = isToday
    ? tr("Сегодня", "Today")
    : day === shiftDay(todayIso(), -1)
      ? tr("Вчера", "Yesterday")
      : tr("Итоги дня", "Day summary");

  return (
    <div className="page wide">
      <header className="hello">
        <div>
          <p className="hello-date eyebrow">{longDate(day)}</p>
          <h1>{title}</h1>
        </div>
        <Link to="/profile" className="avatar" aria-label={tr("Профиль", "Profile")}>
          <Avatar name={me?.first_name ?? me?.username ?? null} />
        </Link>
      </header>

      <DateStrip value={day} onChange={setDay} />
      <HomeScreenOffer />

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <div className="dash">
          <div className="dash-main">
            <Summary data={data} />
            <Link to="/add" className="btn btn-accent btn-cta today-cta">
              <Icon name="camera" size={22} />
              {tr("Сфотографировать еду", "Snap your food")}
            </Link>
            <section>
              <div className="section-head rule">
                <h2>{tr("Еда", "Food")}</h2>
                {data.meals.length > 0 && (
                  <span className="muted small">
                    {data.meals.length} · {round(data.eaten.kcal)} {tr("ккал", "kcal")}
                  </span>
                )}
              </div>
              {data.meals.length === 0 ? (
                <p className="empty-line muted">
                  {tr(
                    "Пока пусто. Сфотографируй тарелку или опиши, что съел, а я посчитаю КБЖУ.",
                    "Nothing yet. Snap your plate or describe what you ate and I'll count the calories and macros.",
                  )}
                </p>
              ) : (
                <div className="stack meal-list">
                  {[...data.meals].reverse().map((meal) => (
                    <MealCard key={meal.id} meal={meal} />
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="tiles-section">
            <h2>{tr("Активность", "Activity")}</h2>
            <div className="tiles">
              <WeightTile />
              <StepsTile key={`steps-${day}`} day={day} steps={data.steps} />
              <WaterTile key={`water-${day}`} day={day} ml={data.water_ml} target={data.water_target_ml} />
              <Link to="/workouts" className="tile-card wide-tile tile-row">
                <div>
                  <h3>{tr("Зал", "Gym")}</h3>
                  {data.sets.length > 0 ? (
                    <div>
                      <strong>{data.sets.length}</strong>
                      <span className="unit">
                        {count(data.sets.length, ["подход", "подхода", "подходов"], ["set", "sets"])}
                      </span>
                    </div>
                  ) : (
                    <span className="unit">{tr("Начать тренировку", "Start a workout")}</span>
                  )}
                </div>
                <Icon name="chevron" />
              </Link>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function longDate(iso: string) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString(locale(), {
    day: "numeric",
    month: "long",
    weekday: "long",
  });
}

function DateStrip({ value, onChange }: { value: string; onChange: (day: string) => void }) {
  const today = todayIso();
  const days = Array.from({ length: 7 }, (_, i) => shiftDay(today, i - 6));
  return (
    <div className="date-strip" role="group" aria-label={tr("Выбор дня", "Pick a day")}>
      {days.map((d) => {
        const date = new Date(`${d}T12:00:00Z`);
        return (
          <button key={d} aria-pressed={d === value} onClick={() => onChange(d)}>
            <strong>{date.getUTCDate()}</strong>
            <span>{date.toLocaleDateString(locale(), { weekday: "short", timeZone: "UTC" })}</span>
          </button>
        );
      })}
    </div>
  );
}

const SEGMENTS = 22;

function Summary({ data }: { data: Day }) {
  const target = data.target;
  const eaten = data.eaten.kcal;
  const left = target ? target.kcal - eaten : null;
  const over = left !== null && left < 0;
  const share = target ? eaten / target.kcal : 0;
  const filled = Math.min(SEGMENTS, Math.round(share * SEGMENTS));
  return (
    <section className={over ? "card hero summary over" : "card hero summary"}>
      <div className="summary-head">
        <span className="eyebrow">
          {left === null ? tr("Съедено", "Eaten") : over ? tr("Сверх нормы", "Over target") : tr("Осталось", "Left")}
        </span>
        <Link to="/profile" className="summary-target">
          {target ? `${tr("Норма", "Target")} ${round(target.kcal)}` : tr("Задать норму", "Set target")}
        </Link>
      </div>
      <p className="summary-big">{round(left === null ? eaten : Math.abs(left))}</p>
      <p className="summary-sub">
        {left === null ? tr("ккал", "kcal") : `${tr("ккал, съедено", "kcal, eaten")} ${round(eaten)}`}
      </p>
      {target && (
        <div className="segments" role="img" aria-label={`${Math.round(share * 100)}%`}>
          {Array.from({ length: SEGMENTS }, (_, i) => (
            <i key={i} className={i < filled ? "on" : ""} />
          ))}
        </div>
      )}
      <MacroBars eaten={data.eaten} target={target} />
      {target && <TargetNote data={data} />}
    </section>
  );
}

function TargetNote({ data }: { data: Day }) {
  if (data.target_source === "adaptive") {
    return (
      <p className="summary-note">
        {tr(
          "Норма рассчитана по твоему фактическому расходу за 4 недели",
          "Target is based on your real expenditure over the last 4 weeks",
        )}
      </p>
    );
  }
  if (data.adaptive_paused) {
    return (
      <p className="summary-note">
        {tr(
          "Мало свежих записей и взвешиваний, поэтому норма пока по формуле",
          "Not enough recent logs and weigh-ins, so the formula is used for now",
        )}
      </p>
    );
  }
  if (data.activity_kcal < 1) return null;
  return (
    <p className="summary-note">
      {tr(
        `Норма включает +${round(data.activity_kcal)} ккал за среднюю активность за 7 дней`,
        `Target includes +${round(data.activity_kcal)} kcal for your average activity over 7 days`,
      )}
    </p>
  );
}

const WATER_STEPS = [100, 250, 500];

function WaterTile({ day, ml, target }: { day: string; ml: number; target: number | null }) {
  const client = useQueryClient();
  const [last, setLast] = useState<number | null>(null);
  const add = useMutation({
    mutationFn: (delta: number) => api.addWater(delta, day),
    onSuccess: ({ water_ml }, delta) => {
      setLast(delta > 0 ? delta : null);
      client.setQueryData<Day>(["day", day], (d) => d && { ...d, water_ml });
    },
  });
  const share = target ? Math.min(100, (ml / target) * 100) : 0;
  const undo = Math.min(last ?? 250, ml);
  return (
    <div className="tile-card wide-tile water">
      <div className="water-head">
        <h3>{tr("Вода", "Water")}</h3>
        <span className="unit">
          <strong>{Number((ml / 1000).toFixed(2))}</strong>
          {target ? ` / ${(target / 1000).toFixed(1)} ${tr("л", "L")}` : ` ${tr("л", "L")}`}
        </span>
      </div>
      <div className="progress">
        <span style={{ width: `${share}%` }} />
      </div>
      <div className="water-steps">
        <button
          className="btn small undo"
          disabled={add.isPending || ml === 0}
          onClick={() => add.mutate(-undo)}
          aria-label={tr(`Убрать ${undo} мл`, `Remove ${undo} ml`)}
          title={tr(`Убрать ${undo} мл`, `Remove ${undo} ml`)}
        >
          −{undo || ""}
        </button>
        {WATER_STEPS.map((delta) => (
          <button
            key={delta}
            className="btn small add"
            disabled={add.isPending}
            onClick={() => add.mutate(delta)}
            aria-label={`+${delta} ${tr("мл", "ml")}`}
          >
            +{delta}
          </button>
        ))}
      </div>
    </div>
  );
}

function WeightTile() {
  const { data } = useWeights();
  const points = (data ?? []).slice(-12);
  const last = points.at(-1);
  return (
    <Link to="/stats" className="tile-card">
      <h3>{tr("Вес", "Weight")}</h3>
      <div>
        <strong>{last ? decimal(last.weight_kg) : "—"}</strong>
        <span className="unit">{last ? tr("кг", "kg") : tr("записать вес", "log weight")}</span>
      </div>
      {points.length > 1 && <Spark values={points.map((p) => p.weight_kg)} />}
    </Link>
  );
}

function Spark({ values }: { values: number[] }) {
  const w = 120;
  const h = 44;
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * (w - 8) + 4,
    h - 4 - ((v - min) / span) * (h - 8),
  ]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden>
      <path d={d} vectorEffect="non-scaling-stroke" />
      <circle cx={lx} cy={ly} r={3.5} />
    </svg>
  );
}

function StepsTile({ day, steps }: { day: string; steps: number }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(steps || ""));
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (n: number) => api.saveSteps(n, day),
    onSuccess: async () => {
      await invalidate("day");
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <form
        className="tile-card"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(value);
          if (Number.isInteger(n) && n >= 0 && n <= 100000) save.mutate(n);
        }}
      >
        <h3>{day === todayIso() ? tr("Шаги за день", "Steps today") : tr("Шаги за этот день", "Steps that day")}</h3>
        <input
          className="input"
          inputMode="numeric"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
        />
        <button className="btn btn-primary small" disabled={save.isPending}>
          {tr("Сохранить", "Save")}
        </button>
      </form>
    );
  }

  return (
    <button className="tile-card" onClick={() => setEditing(true)}>
      <h3>{tr("Шаги", "Steps")}</h3>
      <div>
        <strong>{round(steps)}</strong>
        <span className="unit">
          {steps > 0 ? `${tr("из", "of")} ${round(STEP_GOAL)}` : tr("нажми, чтобы ввести", "tap to enter")}
        </span>
      </div>
      <div className="bar" aria-hidden>
        <div className="bar-fill" style={{ width: `${Math.min(100, (steps / STEP_GOAL) * 100)}%` }} />
      </div>
    </button>
  );
}
