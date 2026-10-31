import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { Art } from "../components/Art";
import { LineChart } from "../components/LineChart";
import { ErrorState, Spinner } from "../components/States";
import { useInvalidate, useWeights } from "../lib/queries";
import { tr } from "../lib/i18n";
import { haptic } from "../lib/telegram";

export function Weight() {
  const { data, isPending, error, refetch } = useWeights();
  const [value, setValue] = useState("");
  const invalidate = useInvalidate();
  const save = useMutation({
    mutationFn: (kg: number) => api.saveWeight(kg),
    onSuccess: async () => {
      haptic("success");
      setValue("");
      await invalidate("weights", "day", "me");
    },
  });
  const kg = Number(value.replace(",", "."));
  const valid = kg >= 30 && kg <= 300;

  return (
    <div className="page">
      <h1>{tr("Вес", "Weight")}</h1>
      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) save.mutate(kg);
        }}
      >
        <input
          className="input"
          inputMode="decimal"
          placeholder={tr("Вес сегодня, кг", "Today's weight, kg")}
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/[^\d.,]/g, ""))}
        />
        <button className="btn btn-primary" disabled={!valid || save.isPending}>
          {tr("Записать", "Log")}
        </button>
      </form>
      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <p className="muted small">
        {tr(
          "Взвешивайся утром натощак, так цифры сравнимы между собой.",
          "Weigh yourself in the morning before eating so the numbers are comparable.",
        )}
      </p>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <div className="empty">
          <Art name="empty-weight" />
          <p>{tr("Записей пока нет. Запиши первый вес, и здесь появится график.", "No entries yet. Log your first weight and a chart will appear here.")}</p>
        </div>
      ) : (
        <WeightStats points={data} />
      )}
    </div>
  );
}

function WeightStats({ points }: { points: { day: string; weight_kg: number }[] }) {
  const first = points[0].weight_kg;
  const last = points[points.length - 1].weight_kg;
  const delta = last - first;
  return (
    <>
      <section className="tiles">
        <div className="tile-card tone-sage short">
          <h3>{tr("Сейчас", "Now")}</h3>
          <div>
            <strong>{last.toFixed(1)}</strong>
            <span className="unit">{tr("кг", "kg")}</span>
          </div>
        </div>
        <div className="tile-card tone-blush short">
          <h3>{tr("Изменение", "Change")}</h3>
          <div>
            <strong>
              {delta > 0 ? "+" : ""}
              {delta.toFixed(1)}
            </strong>
            <span className="unit">{tr("кг с первой записи", "kg since first entry")}</span>
          </div>
        </div>
      </section>
      {points.length > 1 && (
        <section className="card">
          <LineChart points={points.map((p) => ({ day: p.day, value: p.weight_kg }))} unit={tr("кг", "kg")} />
        </section>
      )}
    </>
  );
}
