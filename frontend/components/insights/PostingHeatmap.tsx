"use client";

import { Calendar } from "lucide-react";
import type { HeatmapCell, HeatmapResponse } from "@/lib/api";

/**
 * PostingHeatmap — 7×24 grid showing avg views by day-of-week × hour.
 *
 * Each cell's color intensity reflects average views.
 * Empty cells (no posts at that time) are subtly gray.
 *
 * Compact display: shows hours grouped by 3-hour blocks (0, 3, 6, ..., 21)
 * to avoid 24 narrow columns on smaller screens.
 */
export function PostingHeatmap({ data }: { data: HeatmapResponse }) {
  // Group cells into 7 day-rows × 8 three-hour blocks
  const grid = buildGrid(data.cells);
  const maxAvgViews = Math.max(...data.cells.map((c) => c.avg_views), 1);

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hourBlocks = ["12a", "3a", "6a", "9a", "12p", "3p", "6p", "9p"];

  return (
    <div className="rounded-4xl border bg-white p-5" style={{ borderColor: "var(--color-border)" }}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar size={14} style={{ color: "var(--color-primary)" }} />
          <h3
            className="text-sm font-medium"
            style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
          >
            When you post
          </h3>
        </div>
      </div>

      {/* Insight callout */}
      <div
        className="mb-5 rounded-lg px-4 py-3 text-sm"
        style={{
          backgroundColor: "#fff6ed",
          color: "var(--color-text)",
          fontFamily: "var(--font-body)",
        }}
      >
        {data.insight}
      </div>

      {/* Heatmap grid */}
      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Header row: hours */}
          <div className="mb-1 ml-10 flex gap-1">
            {hourBlocks.map((label) => (
              <div
                key={label}
                className="w-9 text-center text-[10px]"
                style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Day rows */}
          {days.map((dayLabel, dayIdx) => (
            <div key={dayLabel} className="mb-1 flex items-center gap-1">
              <div
                className="w-9 pr-2 text-right text-[11px]"
                style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
              >
                {dayLabel}
              </div>
              {hourBlocks.map((_, blockIdx) => {
                const cellData = grid[dayIdx][blockIdx];
                return (
                  <Cell
                    key={blockIdx}
                    avgViews={cellData.avg_views}
                    postCount={cellData.post_count}
                    maxAvgViews={maxAvgViews}
                    dayLabel={dayLabel}
                    hourLabel={hourBlocks[blockIdx]}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div
        className="mt-4 flex items-center gap-2 text-[10px]"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        <span>Less</span>
        <div className="flex gap-0.5">
          {[0.1, 0.3, 0.5, 0.7, 1.0].map((intensity) => (
            <div
              key={intensity}
              className="h-3 w-3 rounded-sm"
              style={{
                backgroundColor: intensityToColor(intensity),
              }}
            />
          ))}
        </div>
        <span>More views</span>
      </div>
    </div>
  );
}

function Cell({
  avgViews,
  postCount,
  maxAvgViews,
  dayLabel,
  hourLabel,
}: {
  avgViews: number;
  postCount: number;
  maxAvgViews: number;
  dayLabel: string;
  hourLabel: string;
}) {
  const hasData = postCount > 0;
  const intensity = hasData ? avgViews / maxAvgViews : 0;
  const bgColor = hasData ? intensityToColor(intensity) : "#f9fafb";
  const tooltip = hasData
    ? `${dayLabel} ${hourLabel}: ${postCount} post${postCount > 1 ? "s" : ""}, avg ${Math.round(avgViews).toLocaleString()} views`
    : `${dayLabel} ${hourLabel}: no posts`;

  return (
    <div
      className="h-9 w-9 cursor-default rounded-md transition-transform hover:scale-110"
      style={{ backgroundColor: bgColor }}
      title={tooltip}
    />
  );
}

function intensityToColor(intensity: number): string {
  // Map [0..1] to a brand-orange gradient.
  // 0 → light tint, 1 → primary orange.
  if (intensity === 0) return "#f9fafb";
  if (intensity < 0.2) return "#fff6ed";
  if (intensity < 0.4) return "#ffe9ce";
  if (intensity < 0.6) return "#ffc890";
  if (intensity < 0.8) return "#f5a14b";
  return "#d47a03";
}

/**
 * Group raw cells into 7×8 grid of 3-hour blocks.
 * Each block aggregates (avg, count) across the three hours within it.
 */
function buildGrid(cells: HeatmapCell[]): Array<Array<{ avg_views: number; post_count: number }>> {
  const grid: Array<Array<{ avg_views: number; post_count: number }>> = [];

  for (let day = 0; day < 7; day++) {
    const row: Array<{ avg_views: number; post_count: number }> = [];
    for (let block = 0; block < 8; block++) {
      const blockStartHour = block * 3;
      // Find cells matching this day × hour block
      const matching = cells.filter(
        (c) => c.day_of_week === day && c.hour >= blockStartHour && c.hour < blockStartHour + 3,
      );
      if (matching.length === 0) {
        row.push({ avg_views: 0, post_count: 0 });
      } else {
        const totalCount = matching.reduce((s, c) => s + c.post_count, 0);
        const totalViews = matching.reduce((s, c) => s + c.avg_views * c.post_count, 0);
        row.push({
          avg_views: totalCount > 0 ? totalViews / totalCount : 0,
          post_count: totalCount,
        });
      }
    }
    grid.push(row);
  }

  return grid;
}
