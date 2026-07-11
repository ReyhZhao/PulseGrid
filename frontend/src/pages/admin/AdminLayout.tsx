import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/admin", label: "Overview" },
  { to: "/admin/workers", label: "Workers" },
  { to: "/admin/regions", label: "Regions" },
  { to: "/admin/orgs", label: "Organizations" },
  { to: "/admin/users", label: "Users" },
  { to: "/admin/audit", label: "Audit log" },
];

export default function AdminLayout() {
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-bold tracking-tight">Platform admin</h1>
      <p className="mt-1 text-sm text-slate-400">
        Cross-tenant management — visible to staff and superusers only.
      </p>

      <nav className="mt-4 mb-6 flex gap-1 overflow-x-auto border-b border-slate-800 pb-px">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === "/admin"}
            className={({ isActive }) =>
              `whitespace-nowrap rounded-t-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "border-b-2 border-sky-400 text-sky-300"
                  : "text-slate-400 hover:text-slate-200"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
