import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/", label: "Monitors", icon: "◉" },
  { to: "/alerts", label: "Alerts", icon: "⚠" },
  { to: "/channels", label: "Channels", icon: "✉" },
];

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-sky-500/15 text-sky-300" : "text-slate-400 hover:bg-slate-800 hover:text-slate-100",
  ].join(" ");
}

export default function Layout() {
  const { me, logout } = useAuth();

  return (
    <div className="min-h-screen md:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 p-4 md:flex">
        <div className="mb-8 flex items-center gap-2 px-2">
          <span className="text-xl">🌐</span>
          <span className="text-lg font-bold tracking-tight">PulseGrid</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"} className={navClass}>
              <span aria-hidden>{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 pt-3 text-sm">
          <p className="truncate px-2 text-slate-400">{me?.user.email || me?.user.username}</p>
          <button
            onClick={() => void logout()}
            className="mt-2 w-full rounded-lg px-3 py-2 text-left text-slate-400 hover:bg-slate-800 hover:text-slate-100"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-4 py-3 md:hidden">
        <span className="text-lg font-bold">🌐 PulseGrid</span>
        <button onClick={() => void logout()} className="text-sm text-slate-400">
          Sign out
        </button>
      </header>

      <main className="min-w-0 flex-1 p-4 pb-24 md:p-8 md:pb-8">
        <Outlet />
      </main>

      {/* Mobile bottom navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-slate-800 bg-slate-900/95 py-2 backdrop-blur md:hidden">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/"}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-4 py-1 text-xs ${
                isActive ? "text-sky-300" : "text-slate-400"
              }`
            }
          >
            <span className="text-base" aria-hidden>
              {link.icon}
            </span>
            {link.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
