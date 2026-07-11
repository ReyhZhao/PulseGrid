import type { AuditSeverity, Me } from "./types";

/** A worker counts as online when it checked in within the last 5 minutes. */
export const WORKER_ONLINE_WINDOW_MS = 5 * 60 * 1000;

export type WorkerPresence = "online" | "offline" | "never" | "disabled";

export function workerPresence(
  worker: { is_active: boolean; last_seen_at: string | null },
  nowMs = Date.now(),
): WorkerPresence {
  if (!worker.is_active) return "disabled";
  if (!worker.last_seen_at) return "never";
  const seen = new Date(worker.last_seen_at).getTime();
  return nowMs - seen <= WORKER_ONLINE_WINDOW_MS ? "online" : "offline";
}

/** Builds "?a=b&c=d" from the given params, skipping empty values. */
export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export function isPlatformAdmin(me: Me | null): boolean {
  return Boolean(me && (me.user.is_staff || me.user.is_superuser));
}

export function severityBadgeClass(severity: AuditSeverity): string {
  switch (severity) {
    case "critical":
      return "bg-rose-500/25 text-rose-200";
    case "high":
      return "bg-rose-500/15 text-rose-300";
    case "medium":
      return "bg-amber-500/15 text-amber-300";
    case "low":
      return "bg-sky-500/15 text-sky-300";
    default:
      return "bg-slate-700/40 text-slate-300";
  }
}
