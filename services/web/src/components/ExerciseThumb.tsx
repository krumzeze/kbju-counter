import { useState } from "react";
import type { MuscleGroup } from "../api/types";
import { GROUP_MUSCLES, imageUrl } from "../lib/catalog";
import { BACK_FIRST, BodyMap, GROUP_VIEW } from "./BodyMap";

export function groupValues(group: MuscleGroup | null): Record<string, number> {
  return Object.fromEntries((group ? GROUP_MUSCLES[group] : []).map((m) => [m, 1]));
}

export function ExerciseThumb({
  catalogId,
  group,
  className = "thumb",
}: {
  catalogId: string | null;
  group: MuscleGroup | null;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (catalogId && !failed) {
    return (
      <img
        className={className}
        src={imageUrl(catalogId)}
        loading="lazy"
        alt=""
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <div className={`${className} thumb-map`}>
      <BodyMap
        values={groupValues(group)}
        side={group && BACK_FIRST.has(group) ? "back" : "front"}
        view={group ? GROUP_VIEW[group] : undefined}
      />
    </div>
  );
}
