import type { MonitorStatus } from "../lib/types";

const styles: Record<MonitorStatus, { dot: string; text: string; label: string }> = {
  up: { dot: "bg-emerald-400", text: "text-emerald-300", label: "Up" },
  down: { dot: "bg-rose-400", text: "text-rose-300", label: "Down" },
  unknown: { dot: "bg-slate-500", text: "text-slate-400", label: "Pending" },
};

export default function StatusBadge({
  status,
  paused = false,
}: {
  status: MonitorStatus;
  paused?: boolean;
}) {
  if (paused) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-amber-300">
        <span className="h-2 w-2 rounded-full bg-amber-400" aria-hidden />
        Paused
      </span>
    );
  }
  const style = styles[status] ?? styles.unknown;
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${style.text}`}>
      <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden />
      {style.label}
    </span>
  );
}
