import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface DailyCount {
  date: string; // YYYY-MM-DD
  count: number;
}

interface Point {
  time: number;
  count: number;
}

function toSeries(byDay: DailyCount[]): Point[] {
  // Midday UTC keeps every point inside its own calendar day in any timezone.
  return byDay.map((entry) => ({
    time: Date.parse(`${entry.date}T12:00:00Z`),
    count: entry.count,
  }));
}

const formatTick = (value: number) =>
  new Date(value).toLocaleDateString([], { month: "short", day: "numeric" });

/** Daily alert counts with the same drag-to-zoom interaction as the latency
 * chart: drag across a range to zoom in, reset to return to the full window. */
export default function AlertStatsChart({ byDay }: { byDay: DailyCount[] }) {
  const points = useMemo(() => toSeries(byDay), [byDay]);

  const [zoom, setZoom] = useState<{ left: number; right: number } | null>(null);
  const [selectStart, setSelectStart] = useState<number | null>(null);
  const [selectEnd, setSelectEnd] = useState<number | null>(null);

  const visiblePoints = useMemo(() => {
    if (!zoom) return points;
    return points.filter((p) => p.time >= zoom.left && p.time <= zoom.right);
  }, [points, zoom]);

  if (points.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-slate-500">
        No data yet.
      </div>
    );
  }

  const applyZoom = () => {
    if (selectStart === null || selectEnd === null || selectStart === selectEnd) {
      setSelectStart(null);
      setSelectEnd(null);
      return;
    }
    const left = Math.min(selectStart, selectEnd);
    const right = Math.max(selectStart, selectEnd);
    setSelectStart(null);
    setSelectEnd(null);
    setZoom({ left, right });
  };

  const domain: [number | string, number | string] = zoom
    ? [zoom.left, zoom.right]
    : ["dataMin", "dataMax"];

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span className="select-none">Drag across the chart to zoom into a date range.</span>
        {zoom && (
          <button
            onClick={() => setZoom(null)}
            className="rounded border border-slate-700 px-2 py-0.5 text-slate-300 hover:bg-slate-800"
          >
            Reset zoom
          </button>
        )}
      </div>
      <div className="h-48 w-full select-none md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={visiblePoints}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            onMouseDown={(e) => {
              if (e?.activeLabel != null) setSelectStart(Number(e.activeLabel));
            }}
            onMouseMove={(e) => {
              if (selectStart !== null && e?.activeLabel != null)
                setSelectEnd(Number(e.activeLabel));
            }}
            onMouseUp={applyZoom}
            onMouseLeave={applyZoom}
          >
            <defs>
              <linearGradient id="alertStatsFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
            <XAxis
              dataKey="time"
              type="number"
              domain={domain}
              allowDataOverflow
              tickFormatter={formatTick}
              stroke="#475569"
              fontSize={11}
            />
            <YAxis stroke="#475569" fontSize={11} width={40} allowDecimals={false} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
              labelFormatter={(value: number) => new Date(value).toLocaleDateString()}
              formatter={(value: number) => [
                `${value} alert${value === 1 ? "" : "s"}`,
                "received",
              ]}
            />
            <Area
              dataKey="count"
              stroke="#38bdf8"
              strokeWidth={1.75}
              fill="url(#alertStatsFill)"
              isAnimationActive={false}
            />
            {selectStart !== null && selectEnd !== null && (
              <ReferenceArea
                x1={selectStart}
                x2={selectEnd}
                strokeOpacity={0.3}
                fill="#38bdf8"
                fillOpacity={0.15}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
