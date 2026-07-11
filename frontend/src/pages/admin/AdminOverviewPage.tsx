import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { PlatformStats } from "../../lib/types";

function StatCard({
  title,
  value,
  detail,
  alert,
}: {
  title: string;
  value: number;
  detail: string;
  alert?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
      <p className={`mt-1 text-3xl font-bold ${alert ? "text-rose-300" : ""}`}>{value}</p>
      <p className="mt-1 text-sm text-slate-500">{detail}</p>
    </div>
  );
}

export default function AdminOverviewPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api<PlatformStats>("/api/v1/admin/stats"),
    refetchInterval: 30_000,
  });

  if (isLoading) return <p className="text-slate-400">Loading…</p>;
  if (!stats) return <p className="text-slate-400">Statistics unavailable.</p>;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        title="Users"
        value={stats.users.total}
        detail={`${stats.users.active} active · ${stats.users.staff} staff · ${stats.users.new_30d} new (30d)`}
      />
      <StatCard
        title="Organizations"
        value={stats.organizations.total}
        detail={`${stats.organizations.active} active · ${stats.organizations.disabled} disabled`}
        alert={stats.organizations.disabled > 0}
      />
      <StatCard
        title="Monitors"
        value={stats.monitors.total}
        detail={`${stats.monitors.up} up · ${stats.monitors.down} down · ${stats.monitors.paused} paused`}
        alert={stats.monitors.down > 0}
      />
      <StatCard
        title="Workers"
        value={stats.workers.total}
        detail={`${stats.workers.online} online · ${stats.workers.active} enabled`}
        alert={stats.workers.active > 0 && stats.workers.online === 0}
      />
      <StatCard
        title="Regions"
        value={stats.regions.total}
        detail={`${stats.regions.active} active`}
      />
      <StatCard
        title="Checks (24h)"
        value={stats.checks_24h.total}
        detail={`${stats.checks_24h.failed} failed`}
        alert={stats.checks_24h.failed > 0}
      />
      <StatCard
        title="Alerts"
        value={stats.alerts.open}
        detail={`open now · ${stats.alerts.opened_24h} opened (24h)`}
        alert={stats.alerts.open > 0}
      />
      <StatCard
        title="Audit events (24h)"
        value={stats.audit_24h.total}
        detail={`${stats.audit_24h.high_or_critical} high or critical`}
        alert={stats.audit_24h.high_or_critical > 0}
      />
    </div>
  );
}
