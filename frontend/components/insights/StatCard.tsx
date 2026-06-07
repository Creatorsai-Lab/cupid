"use client";

import { ArrowDown, ArrowUp, Minus } from "lucide-react";

/**
 * StatCard — a single big-number stat with optional delta indicator.
 *
 * Used 4× across the top of the insights dashboard:
 *   - Subscribers
 *   - Total views
 *   - Total videos
 *   - Total engagement
 */
export function StatCard({
  label,
  value,
  delta,
  icon: Icon,
  color = "var(--color-primary)",
}: {
  label: string;
  value: number;
  delta?: number;
  icon: typeof ArrowUp;
  color?: string;
}) {
  const deltaPositive = delta !== undefined && delta > 0;
  const deltaNegative = delta !== undefined && delta < 0;
  const DeltaIcon = deltaPositive ? ArrowUp : deltaNegative ? ArrowDown : Minus;
  const deltaColor = deltaPositive ? "#10b981" : deltaNegative ? "#dc2626" : "var(--color-muted)";

  return (
    <div className="rounded-xl border bg-white p-5" style={{ borderColor: "var(--color-border)" }}>
      <div className="mb-3 flex items-center justify-between">
        <p
          className="text-xs font-medium tracking-wide uppercase"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          {label}
        </p>
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ backgroundColor: `${color}15` }}
        >
          <Icon size={14} style={{ color }} />
        </div>
      </div>

      <p
        className="mb-1 font-normal tracking-tight"
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "1.85rem",
          color: "var(--color-text)",
          lineHeight: 1.1,
        }}
      >
        {formatNumber(value)}
      </p>

      {delta !== undefined && (
        <div className="mt-2 flex items-center gap-1">
          <DeltaIcon size={11} style={{ color: deltaColor }} />
          <span
            className="text-xs font-medium"
            style={{ color: deltaColor, fontFamily: "var(--font-body)" }}
          >
            {delta === 0 ? "no change" : formatNumber(Math.abs(delta))}
          </span>
          <span
            className="text-xs"
            style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
          >
            last 30 days
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Format big numbers compactly (1.2K, 3.4M, etc).
 * Avoids rendering "12,345,678" which is wide and hard to scan.
 */
function formatNumber(n: number): string {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 10_000) return (n / 1_000).toFixed(1) + "K";
  if (Math.abs(n) >= 1_000) return n.toLocaleString();
  return n.toString();
}
