import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { MuscleGroup } from "../api/types";
import { tr } from "../lib/i18n";
import { ExerciseThumb } from "./ExerciseThumb";

const PAGE = 24;

export interface ExerciseCardItem {
  key: string;
  name: string;
  hint: string;
  catalogId: string | null;
  group: MuscleGroup | null;
  to?: string;
  onPick?: () => void;
}

export function ExerciseCards({ items }: { items: ExerciseCardItem[] }) {
  const [shown, setShown] = useState(PAGE);
  const signature = items.map((x) => x.key).join("|");
  useEffect(() => setShown(PAGE), [signature]);
  const rest = items.length - shown;

  return (
    <>
      <ul className="ex-grid">
        {items.slice(0, shown).map((x) => {
          const body = (
            <>
              <ExerciseThumb catalogId={x.catalogId} group={x.group} className="ex-img" />
              <span className="ex-text">
                <strong className="capitalize">{x.name}</strong>
                {x.hint && <span>{x.hint}</span>}
              </span>
            </>
          );
          return (
            <li key={x.key}>
              {x.to ? (
                <Link to={x.to} className="ex-card">
                  {body}
                </Link>
              ) : (
                <button className="ex-card" onClick={x.onPick}>
                  {body}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {rest > 0 && (
        <button className="btn btn-block" onClick={() => setShown(shown + PAGE)}>
          {tr(`Показать ещё (${rest})`, `Show more (${rest})`)}
        </button>
      )}
    </>
  );
}
