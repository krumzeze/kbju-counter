import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { LineChart } from "../components/LineChart";
import { ErrorState, Spinner } from "../components/States";
import { useInvalidate, useWeights } from "../lib/queries";
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
      <h1>Вес</h1>
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
          placeholder="Вес сегодня, кг"
          value={value}
          onChange={(e) => setValue(e.target.value.replace(/[^\d.,]/g, ""))}
        />
        <button className="btn btn-primary" disabled={!valid || save.isPending}>
          Записать
        </button>
      </form>
      {save.isError && <p className="error">{errorMessage(save.error)}</p>}
      <p className="muted small">
        Взвешивайся утром натощак, так цифры сравнимы между собой.
      </p>

      {isPending ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <p className="empty">Записей пока нет.</p>
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
      <section className="stats-row">
        <div className="card stat">
          <span className="muted">Сейчас</span>
          <strong>{last.toFixed(1)}</strong>
          <span className="muted small">кг</span>
        </div>
        <div className="card stat">
          <span className="muted">Изменение</span>
          <strong>
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)}
          </strong>
          <span className="muted small">кг с первой записи</span>
        </div>
      </section>
      {points.length > 1 && (
        <section className="card">
          <LineChart points={points.map((p) => ({ day: p.day, value: p.weight_kg }))} unit="кг" />
        </section>
      )}
    </>
  );
}
