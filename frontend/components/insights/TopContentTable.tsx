"use client";

import { useState } from "react";
import { Eye, Heart, MessageSquare, Trophy, ExternalLink, Image as ImageIcon } from "lucide-react";
import type { TopContentItem } from "@/lib/api";


/**
 * TopContentTable — leaderboard of best-performing videos.
 *
 * Compact horizontal cards (thumbnail left, metrics right).
 * Click row → opens video on YouTube in new tab.
 */
export function TopContentTable({
    items,
    snapshotDate,
}: {
    items: TopContentItem[];
    snapshotDate: string;
}) {
    return (
        <div
            className="rounded-xl border bg-white"
            style={{ borderColor: "var(--color-border)" }}
        >
            <div
                className="flex items-center justify-between p-5 border-b"
                style={{ borderColor: "var(--color-border)" }}
            >
                <div className="flex items-center gap-2">
                    <Trophy size={14} style={{ color: "var(--color-primary)" }} />
                    <h3
                        className="text-sm font-medium"
                        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                    >
                        Top performing videos
                    </h3>
                </div>
                <span
                    className="text-xs"
                    style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                >
                    as of {formatDate(snapshotDate)}
                </span>
            </div>

            {items.length === 0 ? (
                <div
                    className="px-5 py-12 text-center text-sm"
                    style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                >
                    No videos to rank yet.
                </div>
            ) : (
                <ol className="divide-y" style={{ borderColor: "var(--color-border)" }}>
                    {items.map((item) => (
                        <TopContentRow key={item.content_id} item={item} />
                    ))}
                </ol>
            )}
        </div>
    );
}


function TopContentRow({ item }: { item: TopContentItem }) {
    const [imageFailed, setImageFailed] = useState(false);
    const showThumb = item.thumbnail_url && !imageFailed;

    return (
        <li>
            <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-4 p-4 hover:bg-[#fff9f3] transition-colors group"
            >
                {/* Rank badge */}
                <div
                    className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium"
                    style={{
                        backgroundColor: item.rank <= 3 ? "#fff6ed" : "#f3f4f6",
                        color: item.rank <= 3 ? "var(--color-primary)" : "var(--color-muted)",
                        fontFamily: "var(--font-body)",
                    }}
                >
                    {item.rank}
                </div>

                {/* Thumbnail */}
                <div
                    className="flex-shrink-0 w-20 h-12 rounded-md overflow-hidden bg-[#fff6ed] flex items-center justify-center"
                >
                    {showThumb ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={item.thumbnail_url!}
                            alt=""
                            className="w-full h-full object-cover"
                            onError={() => setImageFailed(true)}
                            loading="lazy"
                        />
                    ) : (
                        <ImageIcon size={16} className="opacity-40" style={{ color: "var(--color-primary)" }} />
                    )}
                </div>

                {/* Title + metrics */}
                <div className="flex-1 min-w-0">
                    <p
                        className="text-sm font-medium line-clamp-1 group-hover:text-[var(--color-primary)] transition-colors"
                        style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
                    >
                        {item.title}
                    </p>
                    <div
                        className="flex items-center gap-4 mt-1.5 text-xs"
                        style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
                    >
                        <span className="flex items-center gap-1">
                            <Eye size={11} />
                            {formatNumber(item.views)}
                        </span>
                        <span className="flex items-center gap-1">
                            <Heart size={11} />
                            {formatNumber(item.likes)}
                        </span>
                        <span className="flex items-center gap-1">
                            <MessageSquare size={11} />
                            {formatNumber(item.comments)}
                        </span>
                    </div>
                </div>

                <ExternalLink
                    size={12}
                    className="flex-shrink-0 opacity-0 group-hover:opacity-50 transition-opacity"
                    style={{ color: "var(--color-muted)" }}
                />
            </a>
        </li>
    );
}


function formatNumber(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
    if (n >= 1_000) return n.toLocaleString();
    return n.toString();
}


function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}