"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Eye,
  Users,
  Video,
  Heart,
  Youtube,
  AlertCircle,
  Loader2,
  Plus,
  RefreshCw,
} from "lucide-react";

import {
  insightsApi,
  type SummaryResponse,
  type TimeSeriesResponse,
  type TopContentResponse,
  type HeatmapResponse,
} from "@/lib/api";

import { StatCard } from "@/components/insights/StatCard";
import { GrowthChart } from "@/components/insights/GrowthChart";
import { TopContentTable } from "@/components/insights/TopContentTable";
import { PostingHeatmap } from "@/components/insights/PostingHeatmap";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function InsightsPage() {
  const [summaries, setSummaries] = useState<SummaryResponse[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Per-connection data
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesResponse | null>(null);
  const [topContent, setTopContent] = useState<TopContentResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);

  const [loadingList, setLoadingList] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load list of connections on mount
  useEffect(() => {
    loadList();
  }, []);

  // When activeId changes, load all four data sources for that connection
  useEffect(() => {
    if (!activeId) return;
    loadConnectionData(activeId);
  }, [activeId]);

  const loadList = async () => {
    setLoadingList(true);
    setError(null);
    try {
      const data = await insightsApi.list();
      setSummaries(data);
      // Auto-select first connection if any
      if (data.length > 0 && !activeId) {
        setActiveId(data[0].connection_id);
      }
    } catch (err: any) {
      setError(err?.message ?? "Failed to load connections");
    } finally {
      setLoadingList(false);
    }
  };

  const loadConnectionData = async (connectionId: string) => {
    setLoadingData(true);
    setError(null);
    try {
      // Fetch all four endpoints in parallel
      const [s, ts, tc, hm] = await Promise.all([
        insightsApi.summary(connectionId),
        insightsApi.timeseries(connectionId, 30),
        insightsApi.topContent(connectionId, 10),
        insightsApi.heatmap(connectionId),
      ]);
      setSummary(s);
      setTimeseries(ts);
      setTopContent(tc);
      setHeatmap(hm);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load insights");
    } finally {
      setLoadingData(false);
    }
  };

  return (
    <ProtectedRoute>
      <main className="mx-auto max-w-5xl p-3 transition-all duration-500">
        <div className="my-8 flex flex-col gap-1">
          <h1 className="text-[clamp(1.8rem, 4vw, 2.2rem)] tracking-tight">
            Insights From Your Channels
          </h1>
          <p>Analytics, growth, and posting patterns from your connected accounts</p>
        </div>

        {/* States */}
        {loadingList && !summaries && <ListSkeleton />}

        {error && !loadingList && <ErrorState message={error} onRetry={loadList} />}

        {!loadingList && summaries && summaries.length === 0 && <EmptyState />}

        {!loadingList && summaries && summaries.length > 0 && (
          <>
            {/* Connection selector — only shown if multiple */}
            {summaries.length > 1 && (
              <div className="mb-6 flex flex-wrap gap-2">
                {summaries.map((s) => (
                  <ConnectionTab
                    key={s.connection_id}
                    summary={s}
                    active={activeId === s.connection_id}
                    onClick={() => setActiveId(s.connection_id)}
                  />
                ))}
              </div>
            )}

            {/* Dashboard content */}
            {summary && timeseries && topContent && heatmap && (
              <Dashboard
                summary={summary}
                timeseries={timeseries}
                topContent={topContent}
                heatmap={heatmap}
                loading={loadingData}
              />
            )}
          </>
        )}
      </main>
    </ProtectedRoute>
  );
}

// ────────────────────────────────────────────────────────────────
//  Dashboard layout
// ────────────────────────────────────────────────────────────────

function Dashboard({
  summary,
  timeseries,
  topContent,
  heatmap,
  loading,
}: {
  summary: SummaryResponse;
  timeseries: TimeSeriesResponse;
  topContent: TopContentResponse;
  heatmap: HeatmapResponse;
  loading: boolean;
}) {
  return (
    <div className="relative space-y-6">
      {loading && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-white/40">
          <Loader2 size={20} className="animate-spin" style={{ color: "var(--color-primary)" }} />
        </div>
      )}

      {/* Stat cards row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Subscribers"
          value={summary.subscriber_count}
          delta={summary.subscriber_delta_30d}
          icon={Users}
          color="#d47a03"
        />
        <StatCard
          label="Total views"
          value={summary.total_views}
          delta={summary.views_delta_30d}
          icon={Eye}
          color="#0a66c2"
        />
        <StatCard label="Videos" value={summary.total_videos} icon={Video} color="#7c3aed" />
        <StatCard
          label="Total engagement"
          value={summary.total_engagement}
          icon={Heart}
          color="#ec4899"
        />
      </div>

      {/* Chart + Heatmap row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GrowthChart points={timeseries.points} rangeDays={timeseries.range_days} />
        <PostingHeatmap data={heatmap} />
      </div>

      {/* Top content full-width */}
      <TopContentTable items={topContent.items} snapshotDate={topContent.snapshot_date} />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
//  Sub-components: tabs, empty, error, skeleton
// ────────────────────────────────────────────────────────────────

function ConnectionTab({
  summary,
  active,
  onClick,
}: {
  summary: SummaryResponse;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors ${
        active
          ? "border-[var(--color-primary)] bg-[#fff6ed]"
          : "border-[var(--color-border)] bg-white hover:border-[var(--color-primary)]"
      }`}
      style={{
        color: active ? "var(--color-primary)" : "var(--color-text)",
        fontFamily: "var(--font-body)",
      }}
    >
      <Youtube size={14} style={{ color: "#FF0000" }} />
      {summary.handle ?? summary.platform}
    </button>
  );
}

function EmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-4xl border-2 border-dashed px-8 py-16 text-center"
      style={{ borderColor: "var(--color-border)" }}
    >
      <div
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-full"
        style={{ backgroundColor: "#fff6ed" }}
      >
        <Plus size={20} style={{ color: "var(--color-primary)" }} />
      </div>
      <h3
        className="mb-2 text-base font-medium"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        No connected channels yet
      </h3>
      <p
        className="mb-5 max-w-md text-sm"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        Connect your YouTube account in Settings to see growth charts, top videos, and posting
        insights.
      </p>
      <a
        href="/settings"
        className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm text-white"
        style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
      >
        <Plus size={12} />
        Go to Settings
      </a>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertCircle size={28} className="mb-3 text-red-400" />
      <p
        className="mb-1 text-sm font-medium"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        Could not load insights
      </p>
      <p
        className="mb-4 max-w-sm text-sm"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        {message}
      </p>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 rounded-md px-4 py-2 text-sm text-white"
        style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
      >
        <RefreshCw size={12} />
        Try again
      </button>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-28 animate-pulse rounded-4xl border bg-white p-5"
            style={{ borderColor: "var(--color-border)" }}
          >
            <div className="mb-4 h-3 w-16 rounded bg-[#fff6ed]" />
            <div className="mb-2 h-8 w-24 rounded bg-[#fff6ed]" />
            <div className="h-2 w-20 rounded bg-[#fff6ed]" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div
          className="h-72 animate-pulse rounded-4xl border bg-white p-5"
          style={{ borderColor: "var(--color-border)" }}
        />
        <div
          className="h-72 animate-pulse rounded-4xl border bg-white p-5"
          style={{ borderColor: "var(--color-border)" }}
        />
      </div>
    </div>
  );
}
