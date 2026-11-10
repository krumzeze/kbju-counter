import { Link } from "react-router-dom";
import { tr } from "../lib/i18n";
import { useMe } from "../lib/queries";
import { Icon } from "./Icon";

export function PremiumNote({ text }: { text?: string }) {
  const { data: me } = useMe();
  if (!me || me.has_access) return null;
  return (
    <Link to="/premium" className="card premium-note">
      <span>
        {text ??
          tr(
            `Показаны последние ${me.free_history_days} дней. Вся история в Premium`,
            `Showing the last ${me.free_history_days} days. Full history with Premium`,
          )}
      </span>
      <Icon name="chevron" />
    </Link>
  );
}
