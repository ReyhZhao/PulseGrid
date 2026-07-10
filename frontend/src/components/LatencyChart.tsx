import {
  CartesianGrid,
  Line,
  LineChart,
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

export default function LatencyChart({ results }: { results: CheckResult[] }) {
  const { points, regions } = toSeries(results);

  if (points.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center text-sm text-slate-500">
        No check results yet — data appears within one interval.
      </div>
    );
  }

  return (
    <div className="h-56 w-full md:h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis
            dataKey="time"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(value: number) =>
              new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            }
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
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
