import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CheckResult } from "../lib/types";

const REGION_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#22d3ee"];

interface Point {
  time: number;
  [region: string]: number | null;
}

function toSeries(results: CheckResult[]): { points: Point[]; regions: string[] } {
  const regions = [...new Set(results.map((r) => r.region_code))].sort();
  const byTime = new Map<number, Point>();
  for (const result of [...results].reverse()) {
    const time = new Date(result.checked_at).getTime();
    // bucket to the nearest 30s so parallel regions share an x position
    const bucket = Math.round(time / 30_000) * 30_000;
    const point = byTime.get(bucket) ?? { time: bucket };
    point[result.region_code] = result.ok ? result.latency_ms : null;
    byTime.set(bucket, point);
  }
  return { points: [...byTime.values()].sort((a, b) => a.time - b.time), regions };
}

const formatTick = (value: number) =>
  new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export default function LatencyChart({ results }: { results: CheckResult[] }) {
  const { points, regions } = useMemo(() => toSeries(results), [results]);

  // The currently zoomed-in time window; null means "show everything".
  const [zoom, setZoom] = useState<{ left: number; right: number } | null>(null);
  // While the user is dragging, the two edges of the in-progress selection.
  const [selectStart, setSelectStart] = useState<number | null>(null);
  const [selectEnd, setSelectEnd] = useState<number | null>(null);

  const visiblePoints = useMemo(() => {
    if (!zoom) return points;
    return points.filter((p) => p.time >= zoom.left && p.time <= zoom.right);
  }, [points, zoom]);

  if (points.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center text-sm text-slate-500">
        No check results yet — data appears within one interval.
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
        <span className="select-none">Drag across the chart to zoom into a time window.</span>
        {zoom && (
          <button
            onClick={() => setZoom(null)}
            className="rounded border border-slate-700 px-2 py-0.5 text-slate-300 hover:bg-slate-800"
          >
            Reset zoom
          </button>
        )}
      </div>
      <div className="h-56 w-full select-none md:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
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
            <YAxis stroke="#475569" fontSize={11} unit=" ms" width={64} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
              labelFormatter={(value: number) => new Date(value).toLocaleString()}
              formatter={(value: number, name: string) => [`${Math.round(value)} ms`, name]}
            />
            {regions.map((region, index) => (
              <Line
                key={region}
                dataKey={region}
                name={region}
                stroke={REGION_COLORS[index % REGION_COLORS.length]}
                dot={false}
                strokeWidth={1.75}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            {selectStart !== null && selectEnd !== null && (
              <ReferenceArea
                x1={selectStart}
                x2={selectEnd}
                strokeOpacity={0.3}
                fill="#38bdf8"
                fillOpacity={0.15}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
