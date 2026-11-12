import { NavLink, Outlet, useLocation } from "react-router-dom";
import { tr } from "../lib/i18n";
import { isMiniApp, useTelegramBackButton } from "../lib/telegram";
import { Icon, type IconName } from "./Icon";
import { Logo } from "./Logo";

const tabs = (): { to: string; label: string; icon: IconName }[] => [
  { to: "/", label: tr("Главная", "Home"), icon: "home" },
  { to: "/workouts", label: tr("Зал", "Gym"), icon: "gym" },
  { to: "/recipes", label: tr("Рецепты", "Recipes"), icon: "book" },
  { to: "/stats", label: tr("Статистика", "Stats"), icon: "chart" },
];

export function Layout() {
  useTelegramBackButton();
  const { pathname } = useLocation();
  const inAdmin = pathname.startsWith("/admin");
  const inWorkout = /^\/workouts\/\d+$/.test(pathname);
  const classes = ["app", isMiniApp && "mini", inAdmin && "admin"].filter(Boolean).join(" ");
  const [home, gym, recipes, stats] = tabs();
  return (
    <div className={classes}>
      {!isMiniApp && (
        <header className="topbar">
          <NavLink to="/" className="brand">
            <Logo size={34} />
            belok
          </NavLink>
        </header>
      )}
      <main className="content">
        <Outlet />
      </main>
      <nav className="tabbar" aria-label={tr("Разделы", "Sections")}>
        <Tab {...home} />
        <Tab {...gym} />
        {inWorkout ? (
          <span />
        ) : (
          <NavLink to="/add" className="tab-add" aria-label={tr("Добавить еду", "Add food")}>
            <Icon name="plus" size={26} />
          </NavLink>
        )}
        <Tab {...recipes} />
        <Tab {...stats} />
      </nav>
    </div>
  );
}

function Tab({ to, label, icon }: { to: string; label: string; icon: IconName }) {
  return (
    <NavLink to={to} end={to === "/"} className="tab" aria-label={label}>
      <Icon name={icon} />
      <span className="tab-label">{label}</span>
    </NavLink>
  );
}
