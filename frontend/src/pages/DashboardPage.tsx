import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import { api } from "../lib/api";
import { formatInterval, timeAgo } from "../lib/format";
import type { Monitor, Paginated } from "../lib/types";

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["monitors"],
    queryFn: () => api<Paginated<Monitor>>("/api/v1/monitors/"),
    refetchInterval: 15_000,
  });

  const monitors = data?.results ?? [];
  const up = monitors.filter((m) => m.status === "up" && !m.is_paused).length;
  const down = monitors.filter((m) => m.status === "down" && !m.is_paused).length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Monitors</h1>
        <Link
          to="/monitors/new"
          className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400"
        >
          + New monitor
        </Link>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-3">
        <SummaryCard label="Total" value={monitors.length} />
        <SummaryCard label="Up" value={up} tone="text-emerald-300" />
        <SummaryCard label="Down" value={down} tone={down ? "text-rose-300" : undefined} />
      </div>

      {isLoading && <p className="text-slate-400">Loading monitors…</p>}
      {error != null && <p className="text-rose-400">Failed to load monitors.</p>}

      {!isLoading && monitors.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
          <p className="text-lg font-medium">No monitors yet</p>
          <p className="mt-1 text-sm text-slate-400">
            Create your first monitor to start tracking availability, latency and SSL health
            from every region.
          </p>
        </div>
      )}

      <ul className="space-y-2">
        {monitors.map((monitor) => (
          <li key={monitor.id}>
            <Link
              to={`/monitors/${monitor.id}`}
              className="flex items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition-colors hover:border-slate-600"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{monitor.name}</p>
                <p className="truncate text-sm text-slate-500">
                  {monitor.monitor_type === "http"
                    ? monitor.url
                    : monitor.monitor_type === "tcp"
                      ? `${monitor.host}:${monitor.port}`
                      : monitor.host}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-4 text-right">
                <span className="hidden text-xs text-slate-500 sm:block">
                  every {formatInterval(monitor.interval_seconds)}
                  {monitor.status_changed_at && (
                    <>
                      <br />
                      since {timeAgo(monitor.status_changed_at)}
                    </>
                  )}
                </span>
                <StatusBadge status={monitor.status} paused={monitor.is_paused} />
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone = "text-slate-100",
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p>
    </div>
  );
}
