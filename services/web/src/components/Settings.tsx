import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, errorMessage } from "../api/client";
import type { Adaptive, Me, Settings } from "../api/types";
import { round } from "../lib/format";
import { tr } from "../lib/i18n";
import { PremiumNote } from "./PremiumNote";

function useUpdateSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Settings) => api.updateSettings(body),
    onSuccess: (updated) => {
      client.setQueryData(["me"], updated);
      client.invalidateQueries({ queryKey: ["day"] });
    },
  });
}

function Toggle(props: {
  label: string;
  hint?: ReactNode;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle">
      <span className="user-cell">
        {props.label}
        {props.hint && <span className="muted small">{props.hint}</span>}
      </span>
      <input
        type="checkbox"
        checked={props.checked}
        disabled={props.disabled}
        onChange={(e) => props.onChange(e.target.checked)}
      />
    </label>
  );
}

export function TargetSettings({ me }: { me: Me }) {
  const save = useUpdateSettings();
  const adaptive = me.adaptive;
  return (
    <section className="card stack">
      <h2>{tr("Расчёт нормы", "Target calculation")}</h2>
      <div>
        <Toggle
          label={tr("Учитывать активность при подсчёте КБЖУ", "Count activity in your macro target")}
          hint={tr("Шаги и тренировки", "Steps and workouts")}
          checked={me.activity_adjust}
          disabled={save.isPending}
          onChange={(v) => save.mutate({ activity_adjust: v })}
        />
        {me.has_access && adaptive && (adaptive.ready || me.adaptive_target) && (
          <Toggle
            label={tr("Норма по фактическому расходу", "Target from your real expenditure")}
            hint={adaptiveHint(adaptive, me.adaptive_target)}
            checked={me.adaptive_target}
            disabled={save.isPending}
            onChange={(v) => save.mutate({ adaptive_target: v })}
          />
        )}
      </div>
      {!me.has_access && adaptive?.ready && (
        <PremiumNote
          text={tr(
            "Норма по твоему реальному расходу готова. Включить её можно в Premium",
            "Your target from real expenditure is ready. Turn it on with Premium",
          )}
        />
      )}
      {adaptive && !adaptive.ready && !me.adaptive_target && <AdaptiveProgress data={adaptive} />}
      {save.isError && <p className="error small">{errorMessage(save.error)}</p>}
    </section>
  );
}

function adaptiveHint(a: Adaptive, enabled: boolean): string {
  if (!a.ready) {
    return tr(
      "Сейчас мало свежих данных, поэтому норма временно считается по формуле",
      "Not enough recent data right now, so the formula is used for the time being",
    );
  }
  const measured = round(a.tdee!);
  const formula = round(a.formula_tdee);
  const text = tr(
    `По весу и питанию за 4 недели твой расход ≈ ${measured} ккал, по формуле ${formula}.`,
    `From your weight and food over 4 weeks you burn ≈ ${measured} kcal, the formula says ${formula}.`,
  );
  return enabled
    ? text
    : `${text} ${tr("Включи, чтобы норма шла от реальной цифры.", "Turn on to base your target on the real number.")}`;
}

function AdaptiveProgress({ data }: { data: Adaptive }) {
  const rows = [
    [tr("Дни с записанной едой", "Days with food logged"), data.logged_days, data.need_logged_days],
    [tr("Взвешивания", "Weigh-ins"), data.weigh_ins, data.need_weigh_ins],
    [tr("Дней между первым и последним", "Days between first and last"), data.span_days, data.need_span_days],
  ] as const;
  return (
    <div className="adaptive-progress">
      <p className="small">
        <strong>{tr("Норма по фактическому расходу", "Target from your real expenditure")}</strong>
        <br />
        <span className="muted">
          {tr(
            "Когда наберётся данных за последние 4 недели, я посчитаю твой реальный расход по весу и питанию. Формула может ошибаться на 10–20%, а это точнее.",
            "Once there's enough data from the last 4 weeks, I'll work out your real expenditure from weight and food. The formula can be 10–20% off; this is more accurate.",
          )}
        </span>
      </p>
      {rows.map(([label, have, need]) => (
        <div key={label} className="adaptive-row">
          <span className="small">
            {label}
            <span className="muted">
              {" "}
              {Math.min(have, need)} / {need}
            </span>
          </span>
          <div className="progress">
            <span style={{ width: `${Math.min(100, (have / need) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function PhotoSettings({ me }: { me: Me }) {
  const save = useUpdateSettings();
  if (!me.photo_storage) return null;
  return (
    <section className="card stack">
      <h2>{tr("Фото еды", "Food photos")}</h2>
      <p className="muted small">
        {tr(
          "Уменьшенные копии фото хранятся 90 дней, чтобы показывать их в дневнике, потом удаляются.",
          "Small copies of your photos are kept for 90 days to show in your diary, then deleted.",
        )}
      </p>
      <div>
        <Toggle
          label={tr("Помогать улучшать распознавание", "Help improve recognition")}
          hint={tr(
            "Если ты исправишь блюдо на фото, я сохраню фото и исправление, чтобы проверять точность. Выключишь, и они удалятся.",
            "When you correct a photo meal, I'll keep the photo and the fix to check accuracy. Turn off to delete them.",
          )}
          checked={me.photo_eval_consent}
          disabled={save.isPending}
          onChange={(v) => save.mutate({ photo_eval_consent: v })}
        />
      </div>
      {save.isError && <p className="error small">{errorMessage(save.error)}</p>}
    </section>
  );
}

export function ReminderSettings({ me }: { me: Me }) {
  const save = useUpdateSettings();
  return (
    <section className="card stack">
      <h2>{tr("Напоминания в Telegram", "Telegram reminders")}</h2>
      {!me.features.reminders && (
        <p className="muted small">
          {tr("Напоминания временно приостановлены.", "Reminders are temporarily paused.")}
        </p>
      )}
      <div>
        <Toggle
          label={tr("Записать еду", "Log food")}
          hint={tr(
            "В 14:00 и 20:30, если приём пищи не записан",
            "At 2:00 pm and 8:30 pm if a meal isn't logged",
          )}
          checked={me.remind_meals}
          disabled={save.isPending}
          onChange={(v) => save.mutate({ remind_meals: v })}
        />
        <Toggle
          label={tr("Взвеситься", "Weigh in")}
          hint={tr("В 8:30, если не взвешивался 3 дня", "At 8:30 am if you haven't weighed in for 3 days")}
          checked={me.remind_weight}
          disabled={save.isPending}
          onChange={(v) => save.mutate({ remind_weight: v })}
        />
      </div>
      {save.isError && <p className="error small">{errorMessage(save.error)}</p>}
    </section>
  );
}
