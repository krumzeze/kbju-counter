import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, setToken } from "../api/client";
import type { Goal, Me, Sex } from "../api/types";
import { daysLeft, plural, round } from "../lib/format";
import { PromoCard, ReferralCard } from "../components/Growth";
import { useSaveProfile } from "../lib/queries";
import { isMiniApp } from "../lib/telegram";

const GOALS: { value: Goal; label: string; hint: string }[] = [
  { value: "lose", label: "Похудеть", hint: "дефицит 15%" },
  { value: "maintain", label: "Держать вес", hint: "по норме" },
  { value: "gain", label: "Набрать массу", hint: "профицит 10%" },
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
          <h1>Давай знакомиться</h1>
          <p className="muted">
            Пять вопросов, и я рассчитаю твою норму калорий и БЖУ. Шаги и тренировки будут добавлять
            к ней калории каждый день.
          </p>
        </>
      ) : (
        <>
          <h1>Профиль</h1>
          <AccessCard me={me} />
          {me.base_target && (
            <div className="card">
              <span className="muted">Базовая норма без активности</span>
              <p className="target-line">
                <strong>{round(me.base_target.kcal)} ккал</strong> · Б {round(me.base_target.protein)}{" "}
                · Ж {round(me.base_target.fat)} · У {round(me.base_target.carbs)}
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
          <span>Пол</span>
          <div className="segmented">
            <button type="button" aria-selected={sex === "m"} onClick={() => setSex("m")}>
              Мужской
            </button>
            <button type="button" aria-selected={sex === "f"} onClick={() => setSex("f")}>
              Женский
            </button>
          </div>
        </div>
        <div className="fields-3">
          <NumberField label="Возраст" value={age} onChange={setAge} placeholder="25" />
          <NumberField label="Рост, см" value={height} onChange={setHeight} placeholder="178" />
          <NumberField label="Вес, кг" value={weight} onChange={setWeight} placeholder="74.5" decimal />
        </div>
        <div className="field">
          <span>Цель</span>
          <div className="goal-list">
            {GOALS.map((g) => (
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
        {save.isSuccess && !onboarding && <p className="success">Сохранено</p>}
        <button className="btn btn-primary btn-block" disabled={!valid || save.isPending}>
          {onboarding ? "Рассчитать норму" : "Сохранить"}
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
          Выйти
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
    return <div className="card access">Бесплатный доступ навсегда</div>;
  }
  if (me.status === "active") {
    return (
      <div className="card access">
        Доступ активен до {new Date(me.access_until).toLocaleDateString("ru-RU")}
      </div>
    );
  }
  const left = daysLeft(me.trial_ends_at);
  return (
    <div className="card access">
      {left > 0
        ? `Пробный период: осталось ${left} ${plural(left, "день", "дня", "дней")}`
        : "Пробный период закончился"}
    </div>
  );
}
