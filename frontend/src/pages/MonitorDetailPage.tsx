import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import LatencyChart from "../components/LatencyChart";
import StatusBadge from "../components/StatusBadge";
import { api } from "../lib/api";
import { formatLatency, formatUptime, timeAgo } from "../lib/format";
import type {
  AlertEvent,
  CheckResult,
  Monitor,
  MonitorStats,
  Paginated,
} from "../lib/types";

export default function MonitorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const monitorQuery = useQuery({
    queryKey: ["monitor", id],
    queryFn: () => api<Monitor>(`/api/v1/monitors/${id}/`),
  });
  const statsQuery = useQuery({
    queryKey: ["monitor", id, "stats"],
    queryFn: () => api<MonitorStats>(`/api/v1/monitors/${id}/stats/`),
    refetchInterval: 15_000,
  });
  const resultsQuery = useQuery({
    queryKey: ["monitor", id, "results"],
    queryFn: () => api<CheckResult[]>(`/api/v1/monitors/${id}/results/?hours=24`),
    refetchInterval: 30_000,
  });
  const alertsQuery = useQuery({
    queryKey: ["monitor", id, "alerts"],
    queryFn: () => api<Paginated<AlertEvent>>(`/api/v1/alerts/?monitor=${id}`),
  });

  const pauseMutation = useMutation({
    mutationFn: (paused: boolean) =>
      api(`/api/v1/monitors/${id}/${paused ? "pause" : "resume"}/`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["monitor", id] }),
  });
  const deleteMutation = useMutation({
    mutationFn: () => api(`/api/v1/monitors/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["monitors"] });
      void navigate("/");
    },
  });

  const monitor = monitorQuery.data;
  const stats = statsQuery.data;
  if (monitorQuery.isLoading) return <p className="text-slate-400">Loading…</p>;
  if (!monitor) return <p className="text-rose-400">Monitor not found.</p>;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="truncate text-2xl font-bold tracking-tight">{monitor.name}</h1>
            <StatusBadge status={monitor.status} paused={monitor.is_paused} />
          </div>
          <p className="mt-1 truncate text-sm text-slate-500">
            {monitor.monitor_type === "http"
              ? monitor.url
              : monitor.monitor_type === "tcp"
                ? `${monitor.host}:${monitor.port}`
                : monitor.host}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => pauseMutation.mutate(!monitor.is_paused)}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
          >
            {monitor.is_paused ? "Resume" : "Pause"}
          </button>
          <Link
            to={`/monitors/${monitor.id}/edit`}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
          >
            Edit
          </Link>
          <button
            onClick={() => {
              if (window.confirm(`Delete monitor "${monitor.name}"?`)) deleteMutation.mutate();
            }}
            className="rounded-lg border border-rose-900 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-950"
          >
            Delete
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(["24h", "7d", "30d"] as const).map((window) => (
            <div key={window} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <p className="text-xs uppercase tracking-wider text-slate-500">Uptime {window}</p>
              <p className="mt-1 text-xl font-bold">
                {formatUptime(stats.uptime[window]?.uptime_pct)}
              </p>
              <p className="text-xs text-slate-500">
                avg {formatLatency(stats.uptime[window]?.avg_latency_ms)}
              </p>
            </div>
          ))}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">Checks 24h</p>
            <p className="mt-1 text-xl font-bold">{stats.uptime["24h"]?.total_checks ?? 0}</p>
          </div>
        </div>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Latency by region (24h)
        </h2>
        <LatencyChart results={resultsQuery.data ?? []} />
      </section>

      {stats && stats.regions.length > 0 && (
        <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Region</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Latency</th>
                <th className="px-4 py-3">Last check</th>
                {monitor.monitor_type === "traceroute" ? (
                  <th className="px-4 py-3">Hops</th>
                ) : (
                  <th className="px-4 py-3">SSL expiry</th>
                )}
              </tr>
            </thead>
            <tbody>
              {stats.regions.map((region) => (
                <tr key={region.region} className="border-b border-slate-800/60 last:border-0">
                  <td className="px-4 py-3 font-medium">{region.region}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={region.status} />
                    {region.last_error && region.status === "down" && (
                      <p className="mt-1 max-w-xs truncate text-xs text-slate-500">
                        {region.last_error}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3">{formatLatency(region.last_latency_ms)}</td>
                  <td className="px-4 py-3 text-slate-400">{timeAgo(region.last_check_at)}</td>
                  {monitor.monitor_type === "traceroute" ? (
                    <td className="px-4 py-3">
                      {region.last_hop_count == null ? (
                        <span className="text-slate-500">—</span>
                      ) : (
                        <span
                          className={
                            (monitor.hop_threshold_min != null &&
                              region.last_hop_count < monitor.hop_threshold_min) ||
                            (monitor.hop_threshold_max != null &&
                              region.last_hop_count > monitor.hop_threshold_max)
                              ? "text-amber-300"
                              : "text-slate-300"
                          }
                        >
                          {region.last_hop_count} hops
                        </span>
                      )}
                    </td>
                  ) : (
                    <td className="px-4 py-3">
                      {region.ssl_days_left == null ? (
                        <span className="text-slate-500">—</span>
                      ) : (
                        <span
                          className={
                            region.ssl_days_left <= monitor.ssl_expiry_threshold_days
                              ? "text-amber-300"
                              : "text-slate-300"
                          }
                        >
                          {region.ssl_days_left} days
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Recent alerts
        </h2>
        {(alertsQuery.data?.results ?? []).length === 0 ? (
          <p className="text-sm text-slate-500">No alerts for this monitor.</p>
        ) : (
          <ul className="space-y-2">
            {alertsQuery.data!.results.map((event) => (
              <li
                key={event.id}
                className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-2.5 text-sm"
              >
                <span>{event.summary}</span>
                <span
                  className={event.status === "open" ? "text-rose-300" : "text-emerald-300"}
                >
                  {event.status === "open" ? `open · ${timeAgo(event.opened_at)}` : "resolved"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
