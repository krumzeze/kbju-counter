import { NavLink, Outlet } from "react-router-dom";
import { isMiniApp, useTelegramBackButton } from "../lib/telegram";

const TABS = [
  { to: "/", label: "Сегодня", icon: "◐" },
  { to: "/workouts", label: "Зал", icon: "▮▮" },
  { to: "/weight", label: "Вес", icon: "◇" },
  { to: "/profile", label: "Профиль", icon: "○" },
];

export function Layout() {
  useTelegramBackButton();
  return (
    <div className={isMiniApp ? "app mini" : "app"}>
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
      <nav className="tabbar" aria-label="Разделы">
        {TABS.map((tab) => (
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
