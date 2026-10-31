import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage, setToken } from "../api/client";
import type { Goal, Me, Sex } from "../api/types";
import { daysLeft, daysWord, round } from "../lib/format";
import { type Lang, locale, tr } from "../lib/i18n";
import { PromoCard, ReferralCard } from "../components/Growth";
import { Plans } from "../components/Plans";
import { useSaveProfile } from "../lib/queries";
import { isMiniApp } from "../lib/telegram";

const goals = (): { value: Goal; label: string; hint: string }[] => [
  { value: "lose", label: tr("Похудеть", "Lose weight"), hint: tr("дефицит 15%", "15% deficit") },
  {
    value: "maintain",
    label: tr("Держать вес", "Maintain weight"),
    hint: tr("по норме", "maintenance"),
  },
  { value: "gain", label: tr("Набрать массу", "Gain muscle"), hint: tr("профицит 10%", "10% surplus") },
];

export function Profile({ me, onboarding = false }: { me: Me; onboarding?: boolean }) {
  const [sex, setSex] = useState<Sex>(me.sex ?? "m");
  const [age, setAge] = useState(String(me.age ?? ""));
  const [height, setHeight] = useState(String(me.height_cm ?? ""));
  const [weight, setWeight] = useState(String(me.weight_kg ?? ""));
  const [goal, setGoal] = useState<Goal>(me.goal ?? "maintain");
  const save = useSaveProfile();
  const navigate = useNavigate();

  const ageN = Number(age);
  const heightN = Number(height);
  const weightN = Number(weight.replace(",", "."));
  const valid =
    ageN >= 12 && ageN <= 100 && heightN >= 120 && heightN <= 230 && weightN >= 30 && weightN <= 300;

  return (
    <div className="page">
      {onboarding ? (
        <>
          <h1>{tr("Давай знакомиться", "Let's get to know you")}</h1>
          <p className="muted">
            {tr(
              "Пять вопросов, и я рассчитаю твою норму калорий и БЖУ. Шаги и тренировки будут добавлять к ней калории каждый день.",
              "Five questions and I'll calculate your daily calorie and macro target. Steps and workouts add calories to it every day.",
            )}
          </p>
        </>
      ) : (
        <>
          <h1>{tr("Профиль", "Profile")}</h1>
          <AccessCard me={me} />
          {me.status !== "lifetime" && <Plans />}
          <LanguageCard me={me} />
          {me.base_target && (
            <div className="card">
              <span className="muted">{tr("Базовая норма без активности", "Base target before activity")}</span>
              <p className="target-line">
                <strong>
                  {round(me.base_target.kcal)} {tr("ккал", "kcal")}
                </strong>{" "}
                · {tr("Б", "P")} {round(me.base_target.protein)} · {tr("Ж", "F")}{" "}
                {round(me.base_target.fat)} · {tr("У", "C")} {round(me.base_target.carbs)}
              </p>
            </div>
          )}
        </>
      )}

      <form
        className="card form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          save.mutate(
            {
              sex,
              age: ageN,
              height_cm: heightN,
              weight_kg: weightN,
              goal,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            },
            { onSuccess: () => onboarding && navigate("/") },
          );
        }}
      >
        <div className="field">
          <span>{tr("Пол", "Sex")}</span>
          <div className="segmented">
            <button type="button" aria-selected={sex === "m"} onClick={() => setSex("m")}>
              {tr("Мужской", "Male")}
            </button>
            <button type="button" aria-selected={sex === "f"} onClick={() => setSex("f")}>
              {tr("Женский", "Female")}
            </button>
          </div>
        </div>
        <div className="fields-3">
          <NumberField label={tr("Возраст", "Age")} value={age} onChange={setAge} placeholder="25" />
          <NumberField
            label={tr("Рост, см", "Height, cm")}
            value={height}
            onChange={setHeight}
            placeholder="178"
          />
          <NumberField
            label={tr("Вес, кг", "Weight, kg")}
            value={weight}
            onChange={setWeight}
            placeholder="74.5"
            decimal
          />
        </div>
        <div className="field">
          <span>{tr("Цель", "Goal")}</span>
          <div className="goal-list">
            {goals().map((g) => (
              <button
                type="button"
                key={g.value}
                className="goal"
                aria-selected={goal === g.value}
                onClick={() => setGoal(g.value)}
              >
                <strong>{g.label}</strong>
                <span className="muted small">{g.hint}</span>
              </button>
            ))}
          </div>
        </div>
        {save.isError && <p className="error">{errorMessage(save.error)}</p>}
        {save.isSuccess && !onboarding && <p className="success">{tr("Сохранено", "Saved")}</p>}
        <button className="btn btn-primary btn-block" disabled={!valid || save.isPending}>
          {onboarding ? tr("Рассчитать норму", "Calculate my target") : tr("Сохранить", "Save")}
        </button>
      </form>

      {!onboarding && (
        <>
          <ReferralCard />
          <PromoCard />
        </>
      )}

      {!onboarding && !isMiniApp && (
        <button
          className="btn-ghost"
          onClick={() => {
            setToken(null);
            window.location.assign("/");
          }}
        >
          {tr("Выйти", "Sign out")}
        </button>
      )}
    </div>
  );
}

function NumberField(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  decimal?: boolean;
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <input
        className="input"
        inputMode={props.decimal ? "decimal" : "numeric"}
        placeholder={props.placeholder}
        value={props.value}
        onChange={(e) =>
          props.onChange(e.target.value.replace(props.decimal ? /[^\d.,]/g : /\D/g, ""))
        }
      />
    </label>
  );
}

function AccessCard({ me }: { me: Me }) {
  if (me.status === "lifetime") {
    return <div className="card access">{tr("Бесплатный доступ навсегда", "Free access forever")}</div>;
  }
  if (me.status === "active") {
    return (
      <div className="card access">
        {tr("Доступ активен до", "Access active until")}{" "}
        {new Date(me.access_until).toLocaleDateString(locale())}
      </div>
    );
  }
  const left = daysLeft(me.trial_ends_at);
  return (
    <div className="card access">
      {left > 0
        ? tr(`Пробный период: осталось ${left} ${daysWord(left)}`, `Free trial: ${left} ${daysWord(left)} left`)
        : tr("Пробный период закончился", "Your free trial has ended")}
    </div>
  );
}

function LanguageCard({ me }: { me: Me }) {
  const client = useQueryClient();
  const change = useMutation({
    mutationFn: (lang: Lang) => api.setLanguage(lang),
    onSuccess: (updated) => client.setQueryData(["me"], updated),
  });
  return (
    <div className="card field">
      <span>{tr("Язык", "Language")}</span>
      <div className="segmented">
        {(["ru", "en"] as const).map((lang) => (
          <button
            key={lang}
            type="button"
            aria-selected={me.language === lang}
            disabled={change.isPending}
            onClick={() => me.language !== lang && change.mutate(lang)}
          >
            {lang === "ru" ? "Русский" : "English"}
          </button>
        ))}
      </div>
    </div>
  );
}
