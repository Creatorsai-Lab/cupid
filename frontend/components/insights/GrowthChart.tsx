"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Area,
  AreaChart,
} from "recharts";
import { TrendingUp } from "lucide-react";
import type { TimeSeriesPoint } from "@/lib/api";

/**
 * GrowthChart — line chart of subscriber growth over the selected range.
 *
 * Uses an area chart (filled below the line) for visual weight.
 * Chooses a reasonable Y-axis floor based on the data range so small
 * variations are still visible (a chart that goes 100 → 105 should
 * not start at 0).
 */
export function GrowthChart({
  points,
  rangeDays,
}: {
  points: TimeSeriesPoint[];
  rangeDays: number;
}) {
  // Format data for Recharts. Trim "2026-05-07" → "May 7" for X-axis.
  const data = useMemo(
    () =>
      points.map((p) => ({
        date: p.date,
        dateLabel: formatDate(p.date),
        subscribers: p.follower_count,
        views: p.total_views,
      })),
    [points],
  );

  // Compute Y domain so charts of small channels still look meaningful
  const subscriberDomain = useMemo<[number, number]>(() => {
    if (data.length === 0) return [0, 10];
    const values = data.map((d) => d.subscribers);
    const min = Math.min(...values);
    const max = Math.max(...values);
    // Pad 10% above and below
    const padding = Math.max(1, (max - min) * 0.1);
    return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
  }, [data]);

  if (data.length === 0) {
    return (
      <ChartShell title="Subscriber growth" rangeDays={rangeDays}>
        <EmptyState message="No data yet — your first sync will populate this chart." />
      </ChartShell>
    );
  }

  if (data.length === 1) {
    return (
      <ChartShell title="Subscriber growth" rangeDays={rangeDays}>
        <EmptyState message="Only one snapshot so far. The line chart appears once you have a few days of data." />
      </ChartShell>
    );
  }

  return (
    <ChartShell title="Subscriber growth" rangeDays={rangeDays}>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="subGrowth" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d47a03" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#d47a03" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 11, fill: "#7a8499" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={subscriberDomain}
            tick={{ fontSize: 11, fill: "#7a8499" }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "white",
              border: "1px solid #e8e2da",
              borderRadius: "8px",
              fontSize: "12px",
              fontFamily: "var(--font-body)",
            }}
            labelStyle={{ color: "#2a3852" }}
            formatter={(v) => [Number(v).toLocaleString(), "Subscribers"]}
          />
          <Area
            type="monotone"
            dataKey="subscribers"
            stroke="#d47a03"
            strokeWidth={2}
            fill="url(#subGrowth)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

function ChartShell({
  title,
  rangeDays,
  children,
}: {
  title: string;
  rangeDays: number;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border bg-white p-5" style={{ borderColor: "var(--color-border)" }}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} style={{ color: "var(--color-primary)" }} />
          <h3
            className="text-sm font-medium"
            style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
          >
            {title}
          </h3>
        </div>
        <span
          className="text-xs"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          Last {rangeDays} days
        </span>
      </div>
      {children}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      className="flex h-[260px] items-center justify-center px-8 text-center text-sm"
      style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
    >
      {message}
    </div>
  );
}

function formatDate(iso: string): string {
  // "2026-05-07" → "May 7"
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
