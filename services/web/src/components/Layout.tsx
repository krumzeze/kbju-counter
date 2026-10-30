import { NavLink, Outlet, useLocation } from "react-router-dom";
import { isMiniApp, useTelegramBackButton } from "../lib/telegram";

const TABS = [
  { to: "/", label: "Сегодня", icon: "◐" },
  { to: "/workouts", label: "Зал", icon: "▮▮" },
  { to: "/weight", label: "Вес", icon: "◇" },
  { to: "/profile", label: "Профиль", icon: "○" },
];

const ADMIN_TAB = { to: "/admin", label: "Админка", icon: "⚙" };

export function Layout({ admin = false }: { admin?: boolean }) {
  useTelegramBackButton();
  const inAdmin = useLocation().pathname.startsWith("/admin");
  const tabs = admin ? [...TABS, ADMIN_TAB] : TABS;
  const classes = ["app", isMiniApp && "mini", inAdmin && "admin"].filter(Boolean).join(" ");
  return (
    <div className={classes}>
      {!isMiniApp && (
        <header className="topbar">
          <NavLink to="/" className="brand">
            <img src="/favicon.svg" alt="" width={28} height={28} />
            Белок
          </NavLink>
        </header>
      )}
      <main className="content">
        <Outlet />
      </main>
      <nav className={admin ? "tabbar five" : "tabbar"} aria-label="Разделы">
        {tabs.map((tab) => (
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
