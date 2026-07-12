export function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatUptime(pct: number | null | undefined): string {
  if (pct == null) return "—";
  return `${pct.toFixed(pct === 100 ? 0 : 2)}%`;
}

export function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds / 3600)} h`;
}

/**
 * Classify a raw worker error string into a short human-readable cause.
 * The strings matched here are the ones produced by the worker's checks
 * (DNS phase, httpx/socket errors, status/keyword validation, traceroute).
 */
export function describeFailure(
  error: string | null | undefined,
  statusCode?: number | null,
): string {
  const text = (error ?? "").toLowerCase();
  if (text.startsWith("dns resolution failed")) return "DNS failure";
  if (text.includes("timed out")) return "Timeout";
  if (text.includes("certificate") || text.includes("ssl") || text.includes("tls"))
    return "TLS/SSL error";
  if (text.includes("connection refused")) return "Connection refused";
  if (text.includes("connection reset")) return "Connection reset";
  if (
    text.includes("all connection attempts failed") ||
    text.includes("network is unreachable") ||
    text.includes("no route to host") ||
    text.includes("destination not reached")
  )
    return "Unreachable";
  if (text.startsWith("unexpected status") && statusCode != null) return `HTTP ${statusCode}`;
  if (text.includes("keyword")) return "Keyword missing";
  if (text.startsWith("internal check error")) return "Check error";
  if (statusCode != null) return `HTTP ${statusCode}`;
  if (!text) return "Unknown error";
  return "Error";
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}
