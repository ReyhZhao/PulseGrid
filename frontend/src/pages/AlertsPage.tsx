import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { describeFailure, formatLatency, timeAgo } from "../lib/format";
import type { AlertEvent, AlertRegionError, Paginated } from "../lib/types";

function regionFailures(event: AlertEvent): AlertRegionError[] {
  const details = event.details ?? {};
  if (details.region_errors?.length) return details.region_errors;
  // Events recorded before per-region breakdowns only carry the error of the
  // check that tripped the alert.
  if (details.error || details.status_code != null) {
    return [
      {
        region: details.region ?? "",
        error: details.error ?? "",
        status_code: details.status_code ?? null,
      },
    ];
  }
  return [];
}

function DownDetails({ event }: { event: AlertEvent }) {
  const failures = regionFailures(event);
  if (failures.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1.5">
      {failures.map((failure, index) => (
        <li key={failure.region || index} className="flex flex-wrap items-baseline gap-2 text-sm">
          <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-xs font-medium text-rose-300">
            {describeFailure(failure.error, failure.status_code)}
          </span>
          {failure.region && (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
              {failure.region}
            </span>
          )}
          {failure.error && (
            <span
              className="min-w-0 max-w-full truncate font-mono text-xs text-slate-400"
              title={failure.error}
            >
              {failure.error}
            </span>
          )}
          {failure.consecutive_failures != null && failure.consecutive_failures > 1 && (
            <span className="text-xs text-slate-500">
              ×{failure.consecutive_failures} consecutive
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function SslDetails({ event }: { event: AlertEvent }) {
  const details = event.details ?? {};
  if (details.ssl_days_left == null && !details.ssl_expires_at) return null;
  return (
    <p className="mt-2 text-sm text-amber-300/90">
      {details.ssl_days_left != null && `Certificate expires in ${details.ssl_days_left} day(s)`}
      {details.ssl_expires_at &&
        ` · ${new Date(details.ssl_expires_at).toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        })}`}
    </p>
  );
}

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
              {event.details?.regions_down != null &&
                event.details.regions_down > 1 &&
                ` · ${event.details.regions_down} regions affected`}
              {event.details?.latency_ms != null &&
                ` · ${formatLatency(event.details.latency_ms)}`}
            </p>

            {event.event_type === "down" ? (
              <DownDetails event={event} />
            ) : (
              <SslDetails event={event} />
            )}

            {event.status === "resolved" && event.details?.resolution && (
              <p className="mt-2 text-sm text-emerald-300/80">{event.details.resolution}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
