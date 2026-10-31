import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { Day } from "../api/types";
import { Art } from "../components/Art";
import { Avatar } from "../components/Avatar";
import { CalorieRing } from "../components/CalorieRing";
import { Icon } from "../components/Icon";
import { MacroBars } from "../components/MacroBars";
import { MealCard } from "../components/MealCard";
import { ErrorState, Spinner } from "../components/States";
import { count, round, shiftDay, todayIso } from "../lib/format";
import { locale, tr } from "../lib/i18n";
import { useDay, useInvalidate, useMe, useWeights } from "../lib/queries";

const STEP_GOAL = 10000;

export function Today() {
  const [day, setDay] = useState(todayIso());
  const { data, isPending, error, refetch } = useDay(day);
  const { data: me } = useMe();
  const isToday = day === todayIso();
  const name = me?.first_name?.split(" ")[0];

  return (
    <div className="page">
      <header className="hello">
        <div>
          <p className="hello-date capitalize">{longDate(day)}</p>
          <h1>
            {name ? tr(`Привет, ${name}!`, `Hi, ${name}!`) : tr("Привет!", "Hi there!")}
            <br />
            {isToday ? tr("Вот твой день", "Here's your day") : tr("Итоги дня", "Day summary")}
          </h1>
        </div>
        <Link to="/profile" className="avatar">
          <Avatar name={me?.first_name ?? me?.username ?? null} />
          {tr("Профиль", "Profile")}
        </Link>
      </header>

      <DateStrip value={day} onChange={setDay} />

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <>
          <Summary data={data} />

          <section className="tiles">
            <WeightTile />
            <StepsTile steps={data.steps} editable={isToday} />
            <Link to="/workouts" className="tile-card tone-blush">
              <h3>{tr("Тренировка", "Training")}</h3>
              <div>
                <strong>{data.sets.length}</strong>
                <span className="unit">
                  {data.sets.length
                    ? count(data.sets.length, ["подход", "подхода", "подходов"], ["set", "sets"])
                    : tr("начать в зале", "start at the gym")}
                </span>
              </div>
            </Link>
            <Link to="/add" className="tile-card tone-peach">
              <h3>{tr("Добавить еду", "Add food")}</h3>
              <span className="tile-icon">
                <Icon name="camera" size={26} />
              </span>
              <span className="unit">{tr("фото или текстом", "photo or text")}</span>
            </Link>
          </section>

          <section>
            <div className="section-head">
              <h2>{tr("Приёмы пищи", "Meals")}</h2>
              {data.meals.length > 0 && (
                <span className="muted small">
                  {data.meals.length} · {round(data.eaten.kcal)} {tr("ккал", "kcal")}
                </span>
              )}
            </div>
            {data.meals.length === 0 ? (
              <div className="empty">
                <Art name="empty-meals" />
                <p>
                  {tr(
                    "Пока пусто. Сфотографируй тарелку или опиши, что съел, а я посчитаю КБЖУ.",
                    "Nothing yet. Snap your plate or describe what you ate and I'll count the calories and macros.",
                  )}
                </p>
                {isToday && (
                  <Link to="/add" className="btn btn-primary">
                    <Icon name="plus" size={20} />
                    {tr("Добавить еду", "Add food")}
                  </Link>
                )}
              </div>
            ) : (
              <div className="stack">
                {[...data.meals].reverse().map((meal) => (
                  <MealCard key={meal.id} meal={meal} />
                ))}
              </div>
            )}
          </section>
        </>
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

function Summary({ data }: { data: Day }) {
  const target = data.target;
  const left = target ? target.kcal - data.eaten.kcal : null;
  return (
    <section className="card peach summary">
      <div>
        <div className="summary-head">
          <h2>{tr("Итоги", "Summary")}</h2>
          <Link to="/profile" className="link">
            {tr("Норма", "Target")}
          </Link>
        </div>
        <div className="summary-top">
          <dl className="summary-list">
            <dt>{tr("Съедено", "Eaten")}</dt>
            <dd>{round(data.eaten.kcal)}</dd>
            {left !== null && (
              <>
                <dt>{left >= 0 ? tr("Осталось", "Left") : tr("Сверх нормы", "Over")}</dt>
                <dd>{round(Math.abs(left))}</dd>
                <dt>{tr("Норма", "Target")}</dt>
                <dd>{round(target!.kcal)}</dd>
              </>
            )}
          </dl>
          {target && <CalorieRing eaten={data.eaten.kcal} target={target.kcal} />}
        </div>
      </div>
      <MacroBars eaten={data.eaten} target={target} />
      {target && data.activity_kcal >= 1 && (
        <p className="summary-note">
          {tr(
            `Норма включает +${round(data.activity_kcal)} ккал за среднюю активность за 7 дней`,
            `Target includes +${round(data.activity_kcal)} kcal for your average activity over 7 days`,
          )}
        </p>
      )}
    </section>
  );
}

function WeightTile() {
  const { data } = useWeights();
  const points = (data ?? []).slice(-12);
  const last = points.at(-1);
  return (
    <Link to="/weight" className="tile-card tone-sage">
      <h3>{tr("Вес", "Weight")}</h3>
      {points.length > 1 && <Spark values={points.map((p) => p.weight_kg)} />}
      <div>
        <strong>{last ? last.weight_kg.toFixed(1) : "—"}</strong>
        <span className="unit">{last ? tr("кг", "kg") : tr("записать вес", "log weight")}</span>
      </div>
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

function StepsTile({ steps, editable }: { steps: number; editable: boolean }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(steps || ""));
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (n: number) => api.saveSteps(n),
    onSuccess: async () => {
      await invalidate("day");
      setEditing(false);
    },
  });

  if (editing) {
    return (
      <form
        className="tile-card tone-sand"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(value);
          if (Number.isInteger(n) && n >= 0 && n <= 100000) save.mutate(n);
        }}
      >
        <h3>{tr("Шаги за день", "Steps today")}</h3>
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

  const filled = Math.min(10, Math.floor((steps / STEP_GOAL) * 10));
  return (
    <button className="tile-card tone-sand" onClick={() => editable && setEditing(true)} disabled={!editable}>
      <h3>{tr("Шаги", "Steps")}</h3>
      <div className="bars-mini" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <i key={i} className={i < filled ? "on" : ""} style={{ height: `${40 + ((i * 37) % 60)}%` }} />
        ))}
      </div>
      <div>
        <strong>{round(steps)}</strong>
        <span className="unit">
          {steps > 0 ? tr("шагов", "steps") : tr("нажми, чтобы ввести", "tap to enter")}
        </span>
      </div>
    </button>
  );
}
