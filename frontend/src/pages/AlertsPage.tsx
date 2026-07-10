import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import type { AlertEvent, Paginated } from "../lib/types";

export default function AlertsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api<Paginated<AlertEvent>>("/api/v1/alerts/"),
    refetchInterval: 30_000,
  });

  const events = data?.results ?? [];

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Alerts</h1>

      {isLoading && <p className="text-slate-400">Loading…</p>}
      {!isLoading && events.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-slate-400">
          No alerts. Everything has been quiet.
        </div>
      )}

      <ul className="space-y-2">
        {events.map((event) => (
          <li
            key={event.id}
            className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link
                to={`/monitors/${event.monitor}`}
                className="font-medium hover:text-sky-300"
              >
                {event.summary}
              </Link>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  event.status === "open"
                    ? "bg-rose-500/15 text-rose-300"
                    : "bg-emerald-500/15 text-emerald-300"
                }`}
              >
                {event.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {event.event_type === "down" ? "Availability" : "SSL certificate"} · opened{" "}
              {timeAgo(event.opened_at)}
              {event.resolved_at && ` · resolved ${timeAgo(event.resolved_at)}`}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
