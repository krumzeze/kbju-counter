import { tr } from "../lib/i18n";

interface Part {
  m: string | null;
  d: string;
  mirror?: boolean;
}

const ell = (cx: number, cy: number, rx: number, ry: number) =>
  `M${cx - rx},${cy}a${rx},${ry} 0 1,0 ${2 * rx},0a${rx},${ry} 0 1,0 ${-2 * rx},0Z`;

const HEAD: Part = { m: null, d: ell(50, 14, 9, 10.5) };
const PELVIS: Part = { m: null, d: "M38,89L62,89L61,101L50,107L39,101Z" };
const LIMB_ENDS: Part[] = [
  { m: null, d: ell(26, 100, 3.6, 5.5), mirror: true },
  { m: null, d: ell(43, 149, 4.2, 4.2), mirror: true },
  { m: null, d: ell(42, 194, 5.5, 3.6), mirror: true },
];

const FRONT: Part[] = [
  HEAD,
  PELVIS,
  ...LIMB_ENDS,
  { m: "neck", d: "M45,23h10v9h-10Z" },
  { m: "traps", d: "M45,30L36,35L45,34Z", mirror: true },
  { m: "shoulders", d: ell(33, 41, 7, 8), mirror: true },
  { m: "chest", d: "M49.5,36L39,36Q34,40 36,50Q40,57 49.5,55Z", mirror: true },
  { m: "biceps", d: ell(30, 60, 4.8, 10), mirror: true },
  { m: "forearms", d: ell(27, 83, 4.2, 12), mirror: true },
  { m: "abdominals", d: "M43.5,58h6v31h-6Z", mirror: true },
  { m: "abdominals", d: "M42,58L37.5,57Q35.5,74 40,87L42,89Z", mirror: true },
  { m: "abductors", d: ell(37, 101, 3.2, 8), mirror: true },
  { m: "quadriceps", d: ell(42, 125, 6.8, 20.5), mirror: true },
  { m: "adductors", d: ell(47.6, 113, 2.4, 11), mirror: true },
  { m: "calves", d: ell(42, 170, 4.6, 15), mirror: true },
];

const BACK: Part[] = [
  HEAD,
  PELVIS,
  ...LIMB_ENDS,
  { m: "shoulders", d: ell(33, 41, 7, 8), mirror: true },
  { m: "middle back", d: "M49.5,36L39,44L42,58L49.5,63Z", mirror: true },
  { m: "lats", d: "M38,47Q33.5,59 38,72L46,83L48,66L41,58Z", mirror: true },
  { m: "traps", d: "M50,23L39,33L44,40L50,58L56,40L61,33Z" },
  { m: "lower back", d: "M44,70h5.5v18h-5.5Z", mirror: true },
  { m: "triceps", d: ell(30, 59, 4.8, 10), mirror: true },
  { m: "forearms", d: ell(27, 83, 4.2, 12), mirror: true },
  { m: "glutes", d: ell(43, 100, 7.4, 9), mirror: true },
  { m: "hamstrings", d: ell(42.5, 128, 6.5, 19), mirror: true },
  { m: "adductors", d: ell(47.8, 116, 2, 9), mirror: true },
  { m: "calves", d: ell(42, 166, 5.6, 14), mirror: true },
];

const HEART =
  "M44,52c-6-4.5-9-7.5-9-11a4.5,4.5 0 0,1 9-1.5a4.5,4.5 0 0,1 9,1.5c0,3.5-3,6.5-9,11Z";

const MIRROR = "matrix(-1 0 0 1 100 0)";

function Figure({
  parts,
  values,
  heart,
  view,
}: {
  parts: Part[];
  values: Record<string, number>;
  heart: number;
  view: string;
}) {
  const fill = (m: string | null) => {
    const v = m ? Math.min(1, values[m] ?? 0) : 0;
    return v > 0 ? `color-mix(in srgb, var(--muscle) ${Math.round(35 + v * 65)}%, var(--body))` : undefined;
  };
  return (
    <svg viewBox={view} className="figure" aria-hidden>
      {parts.map((p, i) => (
        <g key={i} className={p.m ? "muscle" : "bone"} style={{ fill: fill(p.m) }}>
          <path d={p.d} />
          {p.mirror && <path d={p.d} transform={MIRROR} />}
        </g>
      ))}
      {heart > 0 && <path className="heart" d={HEART} transform="translate(6 -2)" />}
    </svg>
  );
}

export function BodyMap({
  values,
  side = "both",
  view = "0 0 100 200",
  className,
}: {
  values: Record<string, number>;
  side?: "front" | "back" | "both";
  view?: string;
  className?: string;
}) {
  const heart = values.heart ?? 0;
  return (
    <div
      className={className ? `body-map ${className}` : "body-map"}
      role="img"
      aria-label={tr("Схема мышц", "Muscle map")}
    >
      {side !== "back" && <Figure parts={FRONT} values={values} heart={heart} view={view} />}
      {side !== "front" && <Figure parts={BACK} values={values} heart={0} view={view} />}
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
