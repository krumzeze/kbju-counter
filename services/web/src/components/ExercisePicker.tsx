import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { ExerciseRef, MuscleGroup } from "../api/types";
import { GROUPS, GROUP_MUSCLES, equipmentLabel, groupLabel, searchCatalog, sortCatalog } from "../lib/catalog";
import { tr } from "../lib/i18n";
import { useCatalog, useExercises, useInvalidate } from "../lib/queries";
import { type ExerciseCardItem, ExerciseCards } from "./ExerciseCards";
import { type MuscleChoice, MuscleEditor } from "./MuscleEditor";
import { Spinner } from "./States";

interface Row extends Omit<ExerciseCardItem, "to" | "onPick"> {
  ref: ExerciseRef;
}

export function ExercisePicker({
  title,
  onPick,
  onClose,
}: {
  title: string;
  onPick: (ref: ExerciseRef) => void;
  onClose: () => void;
}) {
  const catalog = useCatalog();
  const exercises = useExercises();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<MuscleGroup | null>(null);
  const invalidate = useInvalidate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.classList.add("no-scroll");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("no-scroll");
    };
  }, [onClose]);

  const [draft, setDraft] = useState<(MuscleChoice & { cardio: boolean }) | null>(null);
  const create = useMutation({
    mutationFn: (d: MuscleChoice & { cardio: boolean }) =>
      api.createExercise({
        name: query.trim(),
        group: d.cardio ? "cardio" : null,
        cardio: d.cardio,
        primary: d.cardio ? [] : d.primary,
        secondary: d.cardio ? [] : d.secondary,
      }),
    onSuccess: async (e) => {
      await invalidate("exercises");
      onPick({ exercise_id: e.id });
    },
  });

  const { recent, rows } = useMemo(() => {
    const mine = exercises.data ?? [];
    const recent: Row[] = query || group
      ? []
      : mine
          .filter((e) => e.sets > 0)
          .slice(0, 8)
          .map((e) => ({
            key: `e${e.id}`,
            ref: { exercise_id: e.id },
            name: e.name,
            hint: e.group ? groupLabel(e.group) : "",
            catalogId: e.catalog_id,
            group: e.group,
          }));
    const custom = mine
      .filter((e) => !e.catalog_id && (!group || e.group === group))
      .filter((e) => e.name.toLowerCase().includes(query.trim().toLowerCase()))
      .map<Row>((e) => ({
        key: `e${e.id}`,
        ref: { exercise_id: e.id },
        name: e.name,
        hint: tr("своё", "custom"),
        catalogId: null,
        group: e.group,
      }));
    const pool = (catalog.data ?? []).filter((x) => !group || x.group === group);
    const found = sortCatalog(searchCatalog(pool, query)).map<Row>((x) => ({
      key: x.id,
      ref: { catalog_id: x.id },
      name: x.name,
      hint: `${groupLabel(x.group)} · ${equipmentLabel(x.equipment)}`,
      catalogId: x.id,
      group: x.group,
    }));
    return { recent: cards(recent, onPick), rows: cards([...custom, ...found], onPick) };
  }, [catalog.data, exercises.data, query, group, onPick]);

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2 className="capitalize">{draft ? query.trim() : title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={tr("Закрыть", "Close")}>
            ×
          </button>
        </div>
        {draft ? (
          <>
            <div className="sheet-body stack">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={draft.cardio}
                  onChange={(e) => setDraft({ ...draft, cardio: e.target.checked })}
                />
                {tr("Кардио: записывать минуты, а не вес", "Cardio: log minutes instead of weight")}
              </label>
              {!draft.cardio && (
                <>
                  <h3>{tr("Какие мышцы работают?", "Which muscles does it work?")}</h3>
                  <MuscleEditor value={draft} onChange={(v) => setDraft({ ...draft, ...v })} />
                </>
              )}
              {create.isError && <p className="error">{errorMessage(create.error)}</p>}
            </div>
            <div className="sheet-actions">
              <button className="btn" onClick={() => setDraft(null)}>
                {tr("Назад", "Back")}
              </button>
              <button className="btn btn-primary" disabled={create.isPending} onClick={() => create.mutate(draft)}>
                {tr("Создать упражнение", "Create exercise")}
              </button>
            </div>
          </>
        ) : (
          <>
            <input
              className="input"
              type="search"
              autoFocus
              placeholder={tr("Поиск: жим, присед, бицепс…", "Search: press, squat, biceps…")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="chips scroll-x">
              {GROUPS.map((g) => (
                <button
                  key={g}
                  className="chip"
                  aria-pressed={group === g}
                  onClick={() => setGroup(group === g ? null : g)}
                >
                  {groupLabel(g)}
                </button>
              ))}
            </div>

            <div className="sheet-body">
              {catalog.isPending ? (
                <Spinner />
              ) : (
                <>
                  {recent.length > 0 && (
                    <>
                      <h3 className="muted small">{tr("Недавние", "Recent")}</h3>
                      <ExerciseCards items={recent} />
                      <h3 className="muted small">{tr("Все упражнения", "All exercises")}</h3>
                    </>
                  )}
                  <ExerciseCards items={rows} />
                  {query.trim() && (
                    <button
                      className="btn btn-block"
                      onClick={() =>
                        setDraft({
                          cardio: group === "cardio",
                          primary: group && group !== "cardio" ? GROUP_MUSCLES[group] : [],
                          secondary: [],
                        })
                      }
                    >
                      ＋ {tr(`Создать «${query.trim()}»`, `Create "${query.trim()}"`)}
                    </button>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function cards(rows: Row[], onPick: (ref: ExerciseRef) => void): ExerciseCardItem[] {
  return rows.map((r) => ({
    key: r.key,
    name: r.name,
    hint: r.hint,
    catalogId: r.catalogId,
    group: r.group,
    onPick: () => onPick(r.ref),
  }));
}
