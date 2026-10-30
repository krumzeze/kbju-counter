import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { ErrorState, Spinner } from "../../components/States";
import { useReferrers } from "../../lib/adminQueries";
import { displayName, round } from "../../lib/format";

export function Referrals() {
  const { data, isPending, error, refetch } = useReferrers();
  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <section className="card">
      <div className="card-head">
        <h2>Топ пригласивших</h2>
        <span className="muted small">награда начисляется за каждую оплату друга</span>
      </div>
      {data.length === 0 ? (
        <p className="muted">По приглашениям ещё никто не пришёл</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th className="num">Пригласил</th>
                <th className="num">Оплатили</th>
                <th className="num">Дней получил</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link className="positive" to={`/admin/users/${r.id}`}>
                      {displayName(r)}
                    </Link>
                  </td>
                  <td className="num">{round(r.invited)}</td>
                  <td className="num">{round(r.paid)}</td>
                  <td className="num">{round(r.days)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
