import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { buildQuery, severityBadgeClass } from "../../lib/admin";
import { api } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import type { AuditEvent, AuditSummary, Paginated } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

const SEVERITIES = ["info", "low", "medium", "high", "critical"] as const;

export default function AdminAuditPage() {
  const [days, setDays] = useState(7);
  const [severity, setSeverity] = useState("");
  const [eventType, setEventType] = useState("");
  const [actor, setActor] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const summaryQuery = useQuery({
    queryKey: ["admin", "audit-summary", days],
    queryFn: () => api<AuditSummary>(`/api/v1/admin/audit/summary/${buildQuery({ days })}`),
  });

  const filters = { severity, event_type: eventType, actor, q, page: page > 1 ? page : undefined };
  const eventsQuery = useQuery({
    queryKey: ["admin", "audit", filters],
    queryFn: () => api<Paginated<AuditEvent>>(`/api/v1/admin/audit/${buildQuery(filters)}`),
  });

  const summary = summaryQuery.data;
  const events = eventsQuery.data?.results ?? [];
  const count = eventsQuery.data?.count ?? 0;
  const hasNext = Boolean(eventsQuery.data?.next);

  function setFilter(setter: (value: string) => void) {
    return (value: string) => {
      setter(value);
      setPage(1);
    };
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Activity — last {summary?.days ?? days} days
          </h2>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
        </div>
        {summary && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-2 text-2xl font-bold">{summary.total}</span>
            {SEVERITIES.map(
              (level) =>
                (summary.by_severity[level] ?? 0) > 0 && (
                  <span
                    key={level}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${severityBadgeClass(level)}`}
                  >
                    {level}: {summary.by_severity[level]}
                  </span>
                ),
            )}
          </div>
        )}
        {summary && Object.keys(summary.by_event_type).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            {Object.entries(summary.by_event_type).map(([type, n]) => (
              <button
                key={type}
                onClick={() => setFilter(setEventType)(type === eventType ? "" : type)}
                className={`hover:text-slate-300 ${type === eventType ? "text-sky-300" : ""}`}
              >
                {type} ({n})
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <select
          value={severity}
          onChange={(e) => setFilter(setSeverity)(e.target.value)}
          className={inputClass}
        >
          <option value="">Any severity</option>
          {SEVERITIES.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
        <input
          value={eventType}
          onChange={(e) => setFilter(setEventType)(e.target.value)}
          placeholder="event type, e.g. monitor.created"
          className={inputClass}
        />
        <input
          value={actor}
          onChange={(e) => setFilter(setActor)(e.target.value)}
          placeholder="actor"
          className={inputClass}
        />
        <input
          value={q}
          onChange={(e) => setFilter(setQ)(e.target.value)}
          placeholder="search message…"
          className={inputClass}
        />
      </div>

      <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Event</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Source IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {events.map((event) => (
              <tr key={event.id}>
                <td className="whitespace-nowrap px-4 py-3 text-slate-400">
                  {timeAgo(event.created_at)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${severityBadgeClass(event.severity)}`}
                  >
                    {event.severity}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <p className="font-mono text-xs text-slate-500">{event.event_type}</p>
                  <p className="mt-0.5">{event.message}</p>
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {event.actor || "—"}
                  <p className="text-xs text-slate-600">{event.actor_type}</p>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-400">
                  {event.source_ip || "—"}
                </td>
              </tr>
            ))}
            {events.length === 0 && !eventsQuery.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No audit events match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {(page > 1 || hasNext) && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="rounded-lg border border-slate-700 px-3 py-1.5 hover:bg-slate-800 disabled:opacity-40"
          >
            ← Newer
          </button>
          <span>
            Page {page} · {count} events
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={!hasNext}
            className="rounded-lg border border-slate-700 px-3 py-1.5 hover:bg-slate-800 disabled:opacity-40"
          >
            Older →
          </button>
        </div>
      )}
    </div>
  );
}
