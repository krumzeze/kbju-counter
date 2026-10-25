import { useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { LineChart } from "../components/LineChart";
import { ErrorState, Spinner } from "../components/States";
import { shortDate } from "../lib/format";
import { useProgress } from "../lib/queries";

export function ExerciseProgress() {
  const name = decodeURIComponent(useParams().name ?? "");
  const { data, isPending, error, refetch } = useProgress(name);

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const points = data.points;
  const first = points[0]?.e1rm ?? 0;
  const last = points[points.length - 1]?.e1rm ?? 0;
  const best = Math.max(0, ...points.map((p) => p.e1rm));

  return (
    <div className="page">
      <h1 className="capitalize">{data.exercise}</h1>
      {points.length === 0 ? (
        <p className="empty">Записей пока нет.</p>
      ) : (
        <>
          <section className="stats-row three">
            <div className="card stat">
              <span className="muted">Рекорд 1ПМ</span>
              <strong>{best.toFixed(1)}</strong>
              <span className="muted small">кг, расчётный</span>
            </div>
            <div className="card stat">
              <span className="muted">Изменение</span>
              <strong className={last - first >= 0 ? "positive" : "negative"}>
                {last - first >= 0 ? "+" : ""}
                {(last - first).toFixed(1)}
              </strong>
              <span className="muted small">кг за период</span>
            </div>
            <div className="card stat">
              <span className="muted">Тренировок</span>
              <strong>{points.length}</strong>
              <span className="muted small">в истории</span>
            </div>
          </section>

          <section className="card">
            <h2>Расчётный максимум на 1 раз</h2>
            <LineChart points={points.map((p) => ({ day: p.day, value: p.e1rm }))} unit="кг" />
          </section>

          <section>
            <h2>История</h2>
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Лучший подход</th>
                    <th>1ПМ</th>
                    <th>Подходов</th>
                  </tr>
                </thead>
                <tbody>
                  {[...points].reverse().map((p) => (
                    <tr key={p.day}>
                      <td>{shortDate(p.day)}</td>
                      <td>
                        {p.top_weight_kg} × {p.top_reps}
                      </td>
                      <td>{p.e1rm.toFixed(1)}</td>
                      <td>{p.sets}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
