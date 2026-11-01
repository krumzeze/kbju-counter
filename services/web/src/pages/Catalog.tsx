import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { MuscleGroup } from "../api/types";
import { BACK_FIRST, BodyMap, GROUP_VIEW } from "../components/BodyMap";
import { Art } from "../components/Art";
import { ExerciseThumb, groupValues } from "../components/ExerciseThumb";
import { ErrorState, Spinner } from "../components/States";
import {
  EQUIPMENT,
  EQUIPMENT_COVER,
  GROUPS,
  equipmentLabel,
  groupLabel,
  imageUrl,
  muscleLabel,
  searchCatalog,
  sortCatalog,
} from "../lib/catalog";
import { tr } from "../lib/i18n";
import { useCatalog } from "../lib/queries";

const LIMIT = 100;

export function Catalog() {
  const { data, isPending, error, refetch } = useCatalog();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const tab = params.get("tab") === "equipment" ? "equipment" : "muscles";
  const group = params.get("group") as MuscleGroup | null;
  const equipment = params.get("equipment");

  const results = useMemo(() => {
    const pool = (data ?? []).filter(
      (x) => (!group || x.group === group) && (!equipment || x.equipment === equipment),
    );
    return sortCatalog(searchCatalog(pool, query));
  }, [data, group, equipment, query]);

  if (isPending) return <Spinner />;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const filtered = group || equipment;
  const heading = group ? groupLabel(group) : equipment ? equipmentLabel(equipment) : tr("Упражнения", "Exercises");

  return (
    <div className="page wide">
      <h1>{heading}</h1>
      <input
        className="input search"
        type="search"
        placeholder={tr("Поиск", "Search")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {!filtered && !query && (
        <>
          <div className="segmented" role="tablist">
            <button
              role="tab"
              aria-selected={tab === "muscles"}
              onClick={() => setParams({}, { replace: true })}
            >
              {tr("Мышцы", "Muscles")}
            </button>
            <button
              role="tab"
              aria-selected={tab === "equipment"}
              onClick={() => setParams({ tab: "equipment" }, { replace: true })}
            >
              {tr("Оборудование", "Equipment")}
            </button>
          </div>
          {tab === "muscles" ? (
            <div className="tile-grid">
              {GROUPS.map((g) => (
                <Link key={g} to={`?group=${g}`} className="tile">
                  <div className="tile-art">
                    <Art
                      name={`muscle-${g}`}
                      fallback={
                        <BodyMap
                          values={groupValues(g)}
                          side={BACK_FIRST.has(g) ? "back" : "front"}
                          view={GROUP_VIEW[g]}
                        />
                      }
                    />
                  </div>
                  <span>{groupLabel(g)}</span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="tile-grid two">
              {EQUIPMENT.filter((e) => data.some((x) => x.equipment === e)).map((e) => (
                <Link key={e} to={`?equipment=${encodeURIComponent(e)}`} className="tile">
                  <div className="tile-art">
                    <Art
                      name={`equipment-${e.replace(/[^a-z]+/g, "-")}`}
                      fallback={<img className="cover" src={imageUrl(EQUIPMENT_COVER[e])} alt="" loading="lazy" />}
                    />
                  </div>
                  <span>
                    {equipmentLabel(e)}{" "}
                    <span className="muted small">{data.filter((x) => x.equipment === e).length}</span>
                  </span>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {(filtered || query) && (
        <>
          {results.length === 0 ? (
            <div className="empty">
              <Art name="empty-search" />
              <p>{tr("Ничего не нашлось.", "Nothing found.")}</p>
            </div>
          ) : (
            <ul className="pick-list">
              {results.slice(0, LIMIT).map((x) => (
                <li key={x.id}>
                  <Link to={`/catalog/${encodeURIComponent(x.id)}`}>
                    <ExerciseThumb catalogId={x.id} group={x.group} />
                    <span>
                      <strong className="capitalize">{x.name}</strong>
                      <span className="muted small">
                        {x.primary.map(muscleLabel).join(", ")} · {equipmentLabel(x.equipment)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {results.length > LIMIT && (
            <p className="muted small center">
              {tr(`Ещё ${results.length - LIMIT}, уточни поиск`, `${results.length - LIMIT} more, refine the search`)}
            </p>
          )}
        </>
      )}
    </div>
  );
}
