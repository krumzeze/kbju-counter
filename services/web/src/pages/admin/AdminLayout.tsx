import { NavLink, Outlet } from "react-router-dom";

const SECTIONS = [
  { to: "/admin", label: "Обзор" },
  { to: "/admin/users", label: "Пользователи" },
  { to: "/admin/broadcasts", label: "Рассылки" },
  { to: "/admin/promos", label: "Промокоды" },
  { to: "/admin/referrals", label: "Рефералы" },
  { to: "/admin/log", label: "Журнал" },
  { to: "/admin/settings", label: "Уведомления" },
];

export function AdminLayout() {
  return (
    <div className="page">
      <nav className="admin-nav" aria-label="Разделы админки">
        {SECTIONS.map((s) => (
          <NavLink key={s.to} to={s.to} end={s.to === "/admin"}>
            {s.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
