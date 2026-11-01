import { tr } from "../lib/i18n";

export type Sort = "frequent" | "recent";

export function SortChips({ value, onChange }: { value: Sort; onChange: (sort: Sort) => void }) {
  return (
    <div className="chips">
      <button className="chip" aria-pressed={value === "frequent"} onClick={() => onChange("frequent")}>
        {tr("Частые", "Frequent")}
      </button>
      <button className="chip" aria-pressed={value === "recent"} onClick={() => onChange("recent")}>
        {tr("Недавние", "Recent")}
      </button>
    </div>
  );
}
