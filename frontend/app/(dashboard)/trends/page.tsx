"use client";

import { useEffect, useState } from "react";
import {
  Newspaper,
  MessageSquare,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  Loader2,
} from "lucide-react";

import { trendsApi, type TrendsResponse } from "@/lib/api";
import { NewsCard } from "@/components/TrendsCard";
import ProtectedRoute from "@/components/ProtectedRoute";   


type Tab = "news" | "posts";


export default function TrendsPage() {
  const [tab, setTab] = useState<Tab>("news");

  // News tab data state
  const [data, setData] = useState<TrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch the trends feed. Called on mount and on manual refresh.
   *
   * @param force  Pass true when user clicks refresh — bypasses Redis cache.
   */
  const loadTrends = async (force: boolean = false) => {
    // Show different spinners for first-load vs refresh
    if (force) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await trendsApi.getNews(force);
      setData(response);
    } catch (err: any) {
      setError(err?.message ?? "Could not load trends");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Fetch on mount only
  useEffect(() => {
    loadTrends(false);
  }, []);


  return (
    <ProtectedRoute>
      <main
        className="min-h-[calc(100vh-60px)] px-6 py-10"
        style={{ backgroundColor: "var(--color-background)" }}
      >
        <div className="max-w-3xl mx-auto">

          {/* Page header */}
            <div className="flex items-baseline gap-3 mb-6">
              <TrendingUp size={22} style={{ color: "var(--color-primary)" }} />
              <h1 className="font-normal tracking-tight text-[1.6rem]">
                Current Trends and Recommendation in your niche:{" "}
                <em style={{ color: "var(--color-primary)", fontStyle: "italic" }}>
                  {data?.niche ?? "niche"}
                </em>
              </h1>
            </div>

          {/* Tab bar + actions */}
          <div className="flex items-center justify-between mb-6 bg-[var(--inline-bg)] rounded-lg">
            <div className="flex gap-1">
              <TabButton
                active={tab === "news"}
                onClick={() => setTab("news")}
                icon={Newspaper}
                label="News"
                count={data?.articles.length}
              />
              <TabButton
                active={tab === "posts"}
                onClick={() => setTab("posts")}
                icon={MessageSquare}
                label="Posts"
              />
            </div>

            {/* Refresh button  only shown on News tab */}
            {tab === "news" && data && !error && (
              <button
                onClick={() => loadTrends(true)}
                disabled={refreshing}
                className="flex items-center gap-1.5 px-3 py-1.5 mb-2 text-xs rounded-md transition-colors hover:bg-[#fff6ed] disabled:opacity-50"
                style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                title="Bypass cache and recompute"
              >
                <RefreshCw size={12} className={refreshing ? "animate-spin" : ""}/>
                {refreshing ? "Refreshing" : "Refresh"}
              </button>
            )}
          </div>

          {/* Tab content */}
          {tab === "news" && (
            <NewsTab
              data={data}
              loading={loading}
              error={error}
              onRetry={() => loadTrends(false)}
            />
          )}

          {tab === "posts" && <PostsTab />}

        </div>
      </main>
    </ProtectedRoute>
  );
}


//  Sub-components

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Newspaper;
  label: string;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors -mb-px border-b-2 ${
        active
          ? "text-[var(--color-primary)]"
          : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
      }`}
      style={{ fontFamily: "var(--font-body)" }}
    >
      <Icon size={14} />
      {label}
      {count !== undefined && count > 0 && (
        <span
          className="text-xs px-1.5 py-0.5 rounded-full"
          style={{
            backgroundColor: active ? "#fff6ed" : "var(--color-border)",
            color: active ? "var(--color-primary)" : "var(--color-muted)",
          }}
        >
          {count}
        </span>
      )}
    </button>
  );
}


function NewsTab({
  data,
  loading,
  error,
  onRetry,
}: {
  data: TrendsResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  // Loading state
  if (loading && !data) {
    return <NewsLoadingSkeleton />;
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <AlertCircle size={28} className="text-red-400 mb-3" />
        <p
          className="text-sm mb-1 font-medium"
          style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
        >
          Could not load trends
        </p>
        <p
          className="text-xs mb-4 max-w-sm"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          {error}
        </p>
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-md text-white"
          style={{ backgroundColor: "var(--color-primary)", fontFamily: "var(--font-body)" }}
        >
          <RefreshCw size={12} />
          Try again
        </button>
      </div>
    );
  }

  // Empty state
  if (!data || data.articles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Newspaper size={28} className="opacity-30 mb-3" style={{ color: "var(--color-muted)" }} />
        <p
          className="text-sm mb-1 font-medium"
          style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
        >
          No trending articles yet
        </p>
        <p
          className="text-xs max-w-sm"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          Articles will appear here once ingestion runs. Check back in a few minutes.
        </p>
      </div>
    );
  }

  // Success state
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {data.articles.map((article) => (
        <NewsCard key={article.id} article={article} />
      ))}

      {/* Footer meta — useful for debugging, can hide later */}
      <div
        className="flex items-center justify-between pt-4 mt-4 text-xs border-t border-[var(--color-border)]"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        <span>
          Showing {data.articles.length} of {data.total_pool} items
        </span>
        {data.cached && (
          <span className="px-2 py-0.5 rounded-full bg-[#fff6ed] text-[var(--color-primary)]">
            cached
          </span>
        )}
      </div>
    </div>
  );
}


function PostsTab() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <MessageSquare size={28} className="opacity-30 mb-3" style={{ color: "var(--color-muted)" }} />
      <p
        className="text-sm mb-1 font-medium"
        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
      >
        Trending posts coming soon
      </p>
      <p
        className="text-xs max-w-sm"
        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
      >
        We will surface viral posts and conversations from social media here in
        a future update.
      </p>
    </div>
  );
}


function NewsLoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
        <div
          key={i}
          className="flex gap-4 p-3 rounded-xl border border-[var(--color-border)] bg-white"
        >
          <div className="flex-shrink-0 w-24 h-24 rounded-lg bg-[#fff6ed] animate-pulse" />
          <div className="flex-1 flex flex-col justify-between min-w-0">
            <div className="space-y-2">
              <div className="h-3 rounded bg-[#fff6ed] animate-pulse w-full" />
              <div className="h-3 rounded bg-[#fff6ed] animate-pulse w-4/5" />
              <div className="h-3 rounded bg-[#fff6ed] animate-pulse w-2/3" />
            </div>
            <div className="flex gap-2 mt-2">
              <div className="h-2 rounded bg-[#fff6ed] animate-pulse w-16" />
              <div className="h-2 rounded bg-[#fff6ed] animate-pulse w-12" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}