import { NavLink, Outlet, useLocation } from "react-router-dom";
import { tr } from "../lib/i18n";
import { isMiniApp, useTelegramBackButton } from "../lib/telegram";

const tabs = () => [
  { to: "/", label: tr("Сегодня", "Today"), icon: "◐" },
  { to: "/workouts", label: tr("Зал", "Gym"), icon: "▮▮" },
  { to: "/weight", label: tr("Вес", "Weight"), icon: "◇" },
  { to: "/profile", label: tr("Профиль", "Profile"), icon: "○" },
];

const ADMIN_TAB = { to: "/admin", label: "Админка", icon: "⚙" };

export function Layout({ admin = false }: { admin?: boolean }) {
  useTelegramBackButton();
  const inAdmin = useLocation().pathname.startsWith("/admin");
  const items = admin ? [...tabs(), ADMIN_TAB] : tabs();
  const classes = ["app", isMiniApp && "mini", inAdmin && "admin"].filter(Boolean).join(" ");
  return (
    <div className={classes}>
      {!isMiniApp && (
        <header className="topbar">
          <NavLink to="/" className="brand">
            <img src="/favicon.svg" alt="" width={28} height={28} />
            {tr("Белок", "Belok")}
          </NavLink>
        </header>
      )}
      <main className="content">
        <Outlet />
      </main>
      <nav className={admin ? "tabbar five" : "tabbar"} aria-label={tr("Разделы", "Sections")}>
        {items.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end={tab.to === "/"} className="tab">
            <span className="tab-icon" aria-hidden>
              {tab.icon}
            </span>
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
