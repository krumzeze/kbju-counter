import { tr } from "../lib/i18n";
import { BACK, FRONT } from "./bodyParts";

type Part = (typeof FRONT)[number];

const HEART =
  "M44,52c-6-4.5-9-7.5-9-11a4.5,4.5 0 0,1 9-1.5a4.5,4.5 0 0,1 9,1.5c0,3.5-3,6.5-9,11Z";

const MIRROR = "matrix(-1 0 0 1 100 0)";

function Figure({
  parts,
  values,
  heart,
  view,
  onPick,
}: {
  parts: Part[];
  values: Record<string, number>;
  heart: number;
  view: string;
  onPick?: (muscle: string) => void;
}) {
  const fill = (m: string | null) => {
    const v = m ? Math.min(1, values[m] ?? 0) : 0;
    return v > 0 ? `color-mix(in srgb, var(--muscle) ${Math.round(35 + v * 65)}%, var(--body))` : undefined;
  };
  return (
    <svg viewBox={view} className="figure" aria-hidden={!onPick}>
      {parts.map((p, i) => {
        const m = p.m;
        return (
          <g
            key={i}
            className={m ? "muscle" : "bone"}
            style={{ fill: fill(m) }}
            onClick={m && onPick ? () => onPick(m) : undefined}
          >
            <path d={p.d} />
            {!("whole" in p) && <path d={p.d} transform={MIRROR} />}
          </g>
        );
      })}
      {heart > 0 && <path className="heart" d={HEART} transform="translate(6 -2)" />}
    </svg>
  );
}

export function BodyMap({
  values,
  side = "both",
  view = "8 0 84 200",
  className,
  onPick,
}: {
  values: Record<string, number>;
  side?: "front" | "back" | "both";
  view?: string;
  className?: string;
  onPick?: (muscle: string) => void;
}) {
  const heart = values.heart ?? 0;
  return (
    <div
      className={["body-map", className, onPick && "pickable"].filter(Boolean).join(" ")}
      role="img"
      aria-label={tr("Схема мышц", "Muscle map")}
    >
      {side !== "back" && <Figure parts={FRONT} values={values} heart={heart} view={view} onPick={onPick} />}
      {side !== "front" && <Figure parts={BACK} values={values} heart={0} view={view} onPick={onPick} />}
    </div>
  );
}

export const BACK_FIRST = new Set(["back", "glutes", "calves"]);

const UPPER = "12 2 76 104";
export const GROUP_VIEW: Record<string, string> = {
  delts: UPPER,
  chest: UPPER,
  arms: UPPER,
  abs: UPPER,
  back: UPPER,
  cardio: UPPER,
  legs: "14 84 72 99",
  glutes: "14 74 72 99",
  calves: "10 128 80 80",
};
