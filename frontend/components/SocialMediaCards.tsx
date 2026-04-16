"use client";

/**
 * SocialMediaCards.tsx
 *
 * Platform-accurate post card components with full media support.
 * Each card shows the provided mediaUrl (image or video thumbnail).
 * When no mediaUrl is given, a branded placeholder is shown automatically.
 *
 * Usage:
 *   import { XCard, InstagramReelCard, LinkedInCard } from "@/components/SocialMediaCards";
 *
 *   <XCard name="Adya Prasad" handle="adyaprasad" content="Your post." />
 *   <InstagramReelCard name="Adya" handle="adyaprasad" content="Caption here." mediaUrl="/reel.jpg" />
 * // No media — shows placeholder
    <InstagramReelCard name="Adya Prasad" handle="adyaprasad_" content="Your caption." />

    // With image — shows the photo as reel thumbnail
    <InstagramReelCard name="Adya Prasad" handle="adyaprasad_" content="Your caption." mediaUrl="/photo.jpg" />

    // Dynamic by platform
    <SocialMediaCard platform="youtube" name="Adya Prasad" content="Post text." mediaUrl="/thumb.jpg" />
 */

import {
    ThumbsUp,
    MessageCircle,
    Share2,
    Send,
    Heart,
    Bookmark,
    MoreHorizontal,
    Globe,
    Repeat2,
    Play,
    Bell,
    Music2,
    ImageIcon,
    Video,
    Users,
    MoreVertical
} from "lucide-react";

// ─── Shared types ──────────────────────────────────────────────

export interface CardProps {
    name: string;
    handle?: string;
    content: string;
    time?: string;
    avatarUrl?: string;
    /** Image or video thumbnail URL. Omit to show a platform-styled placeholder. */
    mediaUrl?: string;
}

// ─── Avatar ────────────────────────────────────────────────────

function Avatar({
    name,
    avatarUrl,
    size = 40,
    ringColor,
    ringGradient,
}: {
    name: string;
    avatarUrl?: string;
    size?: number;
    ringColor?: string;
    ringGradient?: boolean;
}) {
    const initials = name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);

    const ring = ringGradient
        ? "outline-[2.5px] outline-offset-[2px]"
        : ringColor
            ? `ring-2 ring-offset-1`
            : "";

    if (avatarUrl) {
        return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
                src={avatarUrl}
                alt={name}
                className={`rounded-full object-cover flex-shrink-0 ${ring}`}
                style={{
                    width: size,
                    height: size,
                    ...(ringColor ? { outlineColor: ringColor, outline: `2.5px solid ${ringColor}`, outlineOffset: "2px" } : {}),
                }}
            />
        );
    }

    return (
        <div
            className="rounded-full flex items-center justify-center font-bold text-white flex-shrink-0"
            style={{
                width: size,
                height: size,
                fontSize: size * 0.35,
                background: "linear-gradient(135deg,#667eea,#764ba2)",
                ...(ringColor ? { outline: `2.5px solid ${ringColor}`, outlineOffset: "2px" } : {}),
            }}
        >
            {initials}
        </div>
    );
}

// ─── Media / Placeholder ───────────────────────────────────────

/**
 * Shows the image/video when mediaUrl is provided.
 * Falls back to a branded placeholder matching the platform's color.
 */
function MediaBlock({
    mediaUrl,
    alt,
    aspectRatio = "16/9",
    platformColor = "#667eea",
    platformLabel = "Image",
    isVideo = false,
    className = "",
}: {
    mediaUrl?: string;
    alt?: string;
    aspectRatio?: string;
    platformColor?: string;
    platformLabel?: string;
    isVideo?: boolean;
    className?: string;
}) {
    if (mediaUrl) {
        return (
            <div className={`relative w-full overflow-hidden ${className}`} style={{ aspectRatio }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={mediaUrl} alt={alt ?? "post media"} className="w-full h-full object-cover" />
                {isVideo && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="bg-black/50 rounded-full p-3 backdrop-blur-sm">
                            <Play size={22} className="text-white" fill="white" />
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // Placeholder
    return (
        <div
            className={`relative w-full flex flex-col items-center justify-center gap-2 ${className}`}
            style={{ aspectRatio, background: `linear-gradient(135deg, ${platformColor}18, ${platformColor}30)`, borderTop: `1px solid ${platformColor}20`, borderBottom: `1px solid ${platformColor}20` }}
        >
            <div className="rounded-full p-3" style={{ background: `${platformColor}20` }}>
                {isVideo
                    ? <Video size={28} style={{ color: platformColor, opacity: 0.7 }} />
                    : <ImageIcon size={28} style={{ color: platformColor, opacity: 0.7 }} />
                }
            </div>
            <p className="text-xs font-medium" style={{ color: platformColor, opacity: 0.6 }}>
                {isVideo ? "Video" : platformLabel}
            </p>
        </div>
    );
}

// ─── 1. Facebook Card ──────────────────────────────────────────

export function FacebookCard({
    name, handle, content, time = "Just now", avatarUrl, mediaUrl,
}: CardProps) {
    return (
        <div className="bg-white rounded-xl border border-[#ddd] max-w-[500px] w-full font-sans text-[#050505] shadow-sm overflow-hidden h-fit">
            <div className="flex items-start gap-2.5 p-3 pb-2">
                <Avatar name={name} avatarUrl={avatarUrl} size={40} />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold">{name}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                        <span className="text-xs text-[#65676b]">{time}</span>
                        <span className="text-[#65676b]">·</span>
                        <Globe size={11} className="text-[#65676b]" />
                    </div>
                </div>
                <MoreHorizontal size={18} className="text-[#65676b] mt-0.5 flex-shrink-0" />
            </div>

            <p className="px-3 pb-2.5 text-sm leading-relaxed whitespace-pre-line">{content}</p>

            <MediaBlock
                mediaUrl={mediaUrl}
                alt="Facebook post"
                aspectRatio="16/9"
                platformColor="#1877f2"
                platformLabel="Photo"
            />

            <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#ced0d4]">
                <div className="flex items-center gap-1">
                    <div className="flex -space-x-1">
                        <div className="w-[18px] h-[18px] rounded-full bg-[#1877f2] flex items-center justify-center border border-white">
                            <ThumbsUp size={9} className="text-white" strokeWidth={2.5} />
                        </div>
                        <div className="w-[18px] h-[18px] rounded-full bg-[#f02849] flex items-center justify-center border border-white">
                            <Heart size={9} className="text-white fill-white" strokeWidth={0} />
                        </div>
                    </div>
                    <span className="text-xs text-[#65676b] ml-1">124</span>
                </div>
                <div className="flex gap-3">
                    <span className="text-xs text-[#65676b]">18 comments</span>
                    <span className="text-xs text-[#65676b]">4 shares</span>
                </div>
            </div>

            <div className="flex divide-x divide-[#ced0d4]">
                {[
                    { icon: ThumbsUp, label: "Like" },
                    { icon: MessageCircle, label: "Comment" },
                    { icon: Share2, label: "Share" },
                ].map(({ icon: Icon, label }) => (
                    <button key={label} className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[#65676b] text-xs font-semibold hover:bg-[#f2f2f2] transition-colors">
                        <Icon size={16} strokeWidth={1.75} />
                        {label}
                    </button>
                ))}
            </div>
        </div>
    );
}

// ─── 2. Instagram Reel Card ────────────────────────────────────

export function InstagramReelCard({
    name, handle, content, time = "2h", avatarUrl, mediaUrl,
}: CardProps) {
    const user = handle ?? name.toLowerCase().replace(/\s/g, "");

    return (
        <div className="relative bg-black rounded-2xl max-w-[320px] w-full font-sans text-white overflow-hidden select-none h-fit" style={{ aspectRatio: "10/16" }}>

            {/* Full-bleed background media */}
            {mediaUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={mediaUrl} alt="Reel" className="absolute inset-0 w-full h-full object-cover" />
            ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3" style={{ background: "linear-gradient(160deg,#833ab4,#fd1d1d,#fcb045)" }}>
                    <div className="bg-white/20 rounded-full p-5 backdrop-blur-sm">
                        <Video size={40} className="text-white" />
                    </div>
                    <p className="text-white/70 text-sm font-medium">Reel</p>
                </div>
            )}

            {/* Gradient overlays */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30 pointer-events-none" />

            {/* Top bar */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 pt-4">
                <div className="flex gap-4">
                    <span className="text-sm font-semibold border-b border-white pb-0.5">Reels</span>
                    <span className="text-sm text-white/60">Friends</span>
                </div>
                <div className="bg-white/20 rounded-full p-1.5 backdrop-blur-sm">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                    </svg>
                </div>
            </div>

            {/* Right-side action icons */}
            <div className="absolute right-3 bottom-24 flex flex-col items-center gap-5">
                {[
                    { icon: Heart, count: "823k" },
                    { icon: MessageCircle, count: "952" },
                    { icon: Share2, count: "2.7k" },
                    { icon: Send, count: "15.1k" },
                ].map(({ icon: Icon, count }, i) => (
                    <div key={i} className="flex flex-col items-center gap-1">
                        <button className="bg-black/20 p-2 rounded-full backdrop-blur-sm active:scale-90 transition-transform">
                            <Icon size={24} className="text-white" strokeWidth={1.75} />
                        </button>
                        <span className="text-xs font-semibold text-white drop-shadow">{count}</span>
                    </div>
                ))}
                {/* More */}
                <button className="mt-1">
                    <MoreHorizontal size={22} className="text-white" />
                </button>
            </div>

            {/* Bottom info overlay */}
            <div className="absolute bottom-0 left-0 right-0 px-3 pb-4 pr-16">
                {/* Username row */}
                <div className="flex items-center gap-2 mb-2">
                    <Avatar name={name} avatarUrl={avatarUrl} size={32} />
                    <span className="text-sm font-semibold drop-shadow">{user}</span>
                    {/* Verified */}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="#fff" className="flex-shrink-0">
                        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <button className="ml-auto text-xs font-semibold border border-white rounded-md px-2.5 py-0.5 hover:bg-white/20 transition-colors">
                        Follow
                    </button>
                </div>

                {/* Caption */}
                <p className="text-xs leading-relaxed text-white/90 drop-shadow line-clamp-2">
                    {content}
                </p>

                {/* Audio */}
                <div className="flex items-center gap-1.5 mt-2">
                    <Music2 size={12} className="text-white/80 flex-shrink-0" />
                    <span className="text-xs text-white/80 truncate">Original audio · {user}</span>
                </div>
            </div>
        </div>
    );
}

// Keep the old name as an alias for backwards compatibility
export const InstagramCard = InstagramReelCard;

// ─── 3. X Card ────────────────────────────────────────────────

export function XCard({
    name, handle, content, time = "2h", avatarUrl, mediaUrl,
}: CardProps) {
    const user = handle ?? name.toLowerCase().replace(/\s/g, "");

    return (
        <div className="bg-black border border-[#2f3336] rounded-2xl max-w-[500px] w-full font-sans text-white overflow-hidden h-fit">
            <div className="flex gap-3 p-4 pb-3">
                <Avatar name={name} avatarUrl={avatarUrl} size={40} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between">
                        <div>
                            <div className="flex items-center gap-1.5">
                                <span className="text-sm font-bold">{name}</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="#1d9bf0">
                                    <path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91-1.01-1-2.52-1.26-3.9-.8-.66-1.31-1.9-2.19-3.34-2.19-1.44 0-2.68.88-3.34 2.19-1.38-.46-2.9-.2-3.91.81-1 1.01-1.26 2.52-.8 3.91C1.63 9.33.75 10.57.75 12c0 1.43.88 2.67 2.19 3.34-.46 1.39-.2 2.9.81 3.91 1.01 1 2.52 1.26 3.91.81.67 1.31 1.9 2.19 3.34 2.19 1.43 0 2.67-.88 3.33-2.19 1.39.45 2.9.19 3.91-.81 1.01-1.01 1.27-2.52.81-3.91 1.31-.67 2.19-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.26 2.26 4.8-5.23 1.47 1.36-6.2 6.77z" />
                                </svg>
                            </div>
                            <p className="text-xs text-[#71767b]">@{user}</p>
                        </div>
                        <MoreHorizontal size={18} className="text-[#71767b]" />
                    </div>

                    <p className="text-sm leading-relaxed mt-2 text-[#e7e9ea] whitespace-pre-line">{content}</p>
                </div>
            </div>

            <MediaBlock
                mediaUrl={mediaUrl}
                alt="X post media"
                aspectRatio="16/9"
                platformColor="#1d9bf0"
                platformLabel="Media"
                className="mx-4 rounded-2xl overflow-hidden mb-3"
            />

            <div className="px-4 pb-1">
                <p className="text-xs text-[#71767b]">{time} · X</p>
            </div>

            <div className="flex items-center justify-between px-4 py-2 border-t border-[#2f3336]">
                {[
                    { icon: MessageCircle, count: "24" },
                    { icon: Repeat2, count: "18" },
                    { icon: Heart, count: "247" },
                    { icon: Bookmark, count: null },
                    { icon: Share2, count: null },
                ].map(({ icon: Icon, count }, i) => (
                    <button key={i} className="flex items-center gap-1 text-[#71767b] hover:text-[#1d9bf0] transition-colors group">
                        <div className="p-1.5 rounded-full group-hover:bg-[#1d9bf0]/10 transition-colors">
                            <Icon size={16} strokeWidth={1.75} />
                        </div>
                        {count && <span className="text-xs">{count}</span>}
                    </button>
                ))}
            </div>
        </div>
    );
}

// ─── 4. LinkedIn Card ──────────────────────────────────────────

export function LinkedInCard({
    name, handle, content, time = "2h", avatarUrl, mediaUrl,
}: CardProps) {
    const subtitle = handle ?? "Content Creator · Building in public";
    const preview = content.length > 220 ? content.slice(0, 220) : content;
    const hasMore = content.length > 220;

    return (
        <div className="bg-white border border-[#e0e0e0] rounded-lg max-w-[555px] w-full font-sans text-[#191919] shadow-sm overflow-hidden h-fit">
            <div className="flex items-start gap-2.5 p-4 pb-3">
                <Avatar name={name} avatarUrl={avatarUrl} size={48} />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold">{name}</p>
                    <p className="text-xs text-[#666] mt-0.5 truncate">{subtitle}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                        <span className="text-xs text-[#666]">{time} ·</span>
                        <Globe size={11} className="text-[#666]" />
                    </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <button className="text-xs font-semibold text-[#0a66c2] border border-[#0a66c2] rounded-full px-3 py-1 hover:bg-[#0a66c2]/5 transition-colors">
                        + Follow
                    </button>
                    <MoreHorizontal size={18} className="text-[#666]" />
                </div>
            </div>

            <div className="px-4 pb-3 text-sm leading-relaxed whitespace-pre-line text-[#191919]">
                {preview}
                {hasMore && (
                    <span className="text-[#666]">
                        …<button className="text-[#191919] font-semibold ml-1">see more</button>
                    </span>
                )}
            </div>

            <MediaBlock
                mediaUrl={mediaUrl}
                alt="LinkedIn post"
                aspectRatio="16/9"
                platformColor="#0a66c2"
                platformLabel="Image"
            />

            <div className="flex items-center justify-between px-4 py-2 border-t border-[#e0e0e0] border-b text-xs text-[#666]">
                <div className="flex items-center gap-1.5">
                    <div className="flex -space-x-0.5">
                        {["#0a66c2", "#7fc15e", "#e7a33e"].map((c, i) => (
                            <div key={i} className="w-4 h-4 rounded-full border border-white flex items-center justify-center" style={{ background: c }}>
                                <ThumbsUp size={7} className="text-white" strokeWidth={2.5} />
                            </div>
                        ))}
                    </div>
                    <span>1,482</span>
                </div>
                <span>87 comments · 34 reposts</span>
            </div>

            <div className="flex divide-x divide-[#e0e0e0]">
                {[
                    { icon: ThumbsUp, label: "Like" },
                    { icon: MessageCircle, label: "Comment" },
                    { icon: Repeat2, label: "Repost" },
                    { icon: Send, label: "Send" },
                ].map(({ icon: Icon, label }) => (
                    <button key={label} className="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[#666] text-xs font-semibold hover:bg-[#f2f2f2] transition-colors">
                        <Icon size={15} strokeWidth={1.75} />
                        {label}
                    </button>
                ))}
            </div>
        </div>
    );
}

// ─── 5. YouTube wide Card ─────────────────────────────────

export function YouTubeCard({
    name, handle, content, time = "2 hours ago", avatarUrl, mediaUrl,
}: CardProps) {
    return (
        <div className="bg-white border border-[#e5e5e5] rounded-xl max-w-[540px] w-full font-sans text-[#0f0f0f] overflow-hidden h-fit">
            <MediaBlock
                mediaUrl={mediaUrl}
                alt="YouTube post"
                aspectRatio="16/9"
                platformColor="#ff0000"
                platformLabel="Video"
                isVideo
                className="p-5 m-5 rounded-xl overflow-hidden "
            />
            <div className="flex gap-3 p-4 pb-3">
                <Avatar name={name} avatarUrl={avatarUrl} size={40} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold">{name}</span>
                        <span className="text-xs text-[#606060]">· {time}</span>
                    </div>
                    
                </div>
            </div>

            <div className="flex items-center gap-2 px-4 pb-4">
                <div className="flex rounded-full border border-[#e5e5e5] overflow-hidden">
                    <button className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium hover:bg-[#f2f2f2] transition-colors border-r border-[#e5e5e5]">
                        <ThumbsUp size={14} strokeWidth={1.75} />
                        8.4K
                    </button>
                    <button className="px-3 py-1.5 hover:bg-[#f2f2f2] transition-colors">
                        <ThumbsUp size={14} strokeWidth={1.75} className="rotate-180" />
                    </button>
                </div>
                <button className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium hover:bg-[#f2f2f2] transition-colors border border-[#e5e5e5]">
                    <MessageCircle size={14} strokeWidth={1.75} />
                    342 replies
                </button>
                <button className="ml-auto p-2 rounded-full hover:bg-[#f2f2f2] transition-colors">
                    <Bell size={16} strokeWidth={1.75} className="text-[#606060]" />
                </button>
                
            </div>
            <p className="text-sm leading-relaxed mt-2 text-[#0f0f0f] whitespace-pre-line">{content}</p>
        </div>
    );
}

// 6. YouTube Short Card

export function YouTubeShortsCard({
    name, handle, content, time, avatarUrl, mediaUrl,
  }: CardProps) {
    const user = handle ?? name.toLowerCase().replace(/\s/g, "");
  
    return (
      <div
        className="relative bg-black rounded-2xl overflow-hidden font-sans text-white h-fit"
        style={{ width: 260, aspectRatio: "10/16" }}
      >
        {/* Background media or placeholder */}
        {mediaUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl} alt="Short" className="absolute inset-0 w-full h-full object-cover" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4"
            style={{ background: "linear-gradient(160deg,#1a1a2e,#16213e,#0f3460)" }}>
            <div className="rounded-full p-6 border-2 border-red-600/40"
              style={{ background: "rgba(255,0,0,.15)" }}>
              <Play size={42} className="text-[#ff0000]" fill="#ff0000" strokeWidth={0} />
            </div>
            <div className="flex items-center gap-2">
              {/* Shorts wordmark */}
              <svg width="18" height="14" viewBox="0 0 90 90">
                <path d="M43.4 2.3C20.5 3.2 2 22.2 2 45c0 23.7 19.3 43 43 43 23.7 0 43-19.3 43-43 0-4.2-.6-8.3-1.7-12.2L74 45.4c.1.9.2 1.8.2 2.8C74.2 66.6 61 79.2 45 79.2S15.8 66.6 15.8 48 29 16.8 45 16.8c4.6 0 8.9 1.1 12.7 3.1L69.5 8.2C62 4.2 53 2 43.4 2.3z" fill="#ff0000"/>
                <path d="M88.3 1.7L45 45 32 32 22.8 41.2 45 63.4l56.7-56.7z" fill="#ff0000"/>
              </svg>
              <span className="text-sm font-bold tracking-wide text-[#ff0000]">Shorts</span>
            </div>
          </div>
        )}
  
        {/* Gradient overlays */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(to top,rgba(0,0,0,.85) 0%,transparent 45%,rgba(0,0,0,.2) 100%)" }} />
  
        {/* Top bar */}
        <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-3.5 pt-3.5">
          <div className="flex items-center gap-2">
            <svg width="20" height="14" viewBox="0 0 90 90">
              <path d="M43.4 2.3C20.5 3.2 2 22.2 2 45c0 23.7 19.3 43 43 43 23.7 0 43-19.3 43-43 0-4.2-.6-8.3-1.7-12.2L74 45.4c.1.9.2 1.8.2 2.8C74.2 66.6 61 79.2 45 79.2S15.8 66.6 15.8 48 29 16.8 45 16.8c4.6 0 8.9 1.1 12.7 3.1L69.5 8.2C62 4.2 53 2 43.4 2.3z" fill="#fff"/>
              <path d="M88.3 1.7L45 45 32 32 22.8 41.2 45 63.4l56.7-56.7z" fill="#fff"/>
            </svg>
            <span className="text-sm font-bold tracking-wide">Shorts</span>
          </div>
          <div className="flex gap-3.5 text-white">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <MoreHorizontal size={19} />
          </div>
        </div>
  
        {/* Right action column */}
        <div className="absolute right-2.5 bottom-28 flex flex-col items-center gap-5">
  
          {/* Avatar + subscribe button */}
          <div className="flex flex-col items-center">
            <Avatar name={name} avatarUrl={avatarUrl} size={36} ringColor="#fff" />
            {/* Red plus badge */}
            <div className="w-[18px] h-[18px] rounded-full bg-[#ff0000] flex items-center justify-center -mt-2 border-2 border-black z-10">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </div>
          </div>
  
          {/* Like */}
          <ActionIcon icon={Heart} count="47K" />
          {/* Comment */}
          <ActionIcon icon={MessageCircle} count="1.2K" />
          {/* Share */}
          <ActionIcon icon={Share2} count="Share" />
          {/* More */}
          <div className="bg-white/15 rounded-full p-2.5 backdrop-blur-sm">
            <MoreVertical size={22} className="text-white" />
          </div>
  
          {/* Spinning record disc */}
          <div className="w-9 h-9 rounded-full flex items-center justify-center border-[3px] border-white/30"
            style={{ background: "linear-gradient(135deg,#1a1a1a,#333)" }}>
            <div className="w-3 h-3 rounded-full"
              style={{ background: "linear-gradient(135deg,#667eea,#764ba2)" }} />
          </div>
        </div>
  
        {/* Bottom info */}
        <div className="absolute bottom-0 left-0 right-0 px-3.5 pb-5 pr-14">
          <p className="text-sm font-bold mb-1 drop-shadow">@{user}</p>
          <p className="text-xs leading-relaxed text-white/90 drop-shadow line-clamp-2">{content}</p>
          <div className="flex items-center gap-1.5 mt-2">
            <Music2 size={12} className="text-white/80 flex-shrink-0" />
            <span className="text-xs text-white/80 truncate">Original audio · {name}</span>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-[2px] rounded-full bg-white/25 overflow-hidden">
            <div className="h-full w-[38%] rounded-full bg-white" />
          </div>
        </div>
      </div>
    );
  }
  
  // helper used only inside YouTubeShortsCard
  function ActionIcon({ icon: Icon, count }: { icon: React.ElementType; count: string }) {
    return (
      <div className="flex flex-col items-center gap-1">
        <div className="bg-white/15 rounded-full p-2.5 backdrop-blur-sm">
          <Icon size={24} strokeWidth={1.75} className="text-white" />
        </div>
        <span className="text-[11px] font-bold drop-shadow">{count}</span>
      </div>
    );
  }

// 7. Poll Card
export interface PollCardProps {
    name: string;
    handle?: string;
    avatarUrl?: string;
    question: string;
    options: [string, string, string, string];
    /** 0–100 vote percentages matching options order. Omit to show unvoted state. */
    votes?: [number, number, number, number];
    totalVotes?: number;
    timeLeft?: string;
    time?: string;
  }
  
  export function PollCard({
    name,
    handle,
    avatarUrl,
    question,
    options,
    votes,
    totalVotes = 0,
    timeLeft = "24h left",
    time = "1h",
  }: PollCardProps) {
    const user    = handle ?? name.toLowerCase().replace(/\s/g, "");
    const voted   = !!votes;
    const leading = voted ? votes.indexOf(Math.max(...votes)) : -1;
  
    return (
      <div className="bg-white border border-[#e2e8f0] rounded-2xl max-w-[420px] w-full font-sans text-[#1a202c] shadow-sm overflow-hidden h-fit">
  
        {/* Header */}
        <div className="flex items-start gap-3 p-4 pb-3">
          <Avatar name={name} avatarUrl={avatarUrl} size={42} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-bold leading-tight">{name}</p>
                <p className="text-xs text-[#718096] mt-0.5">@{user} · {time}</p>
              </div>
              <MoreHorizontal size={18} className="text-[#a0aec0] flex-shrink-0" />
            </div>
            <p className="text-sm leading-relaxed mt-2.5 font-medium text-[#2d3748]">
              {question}
            </p>
          </div>
        </div>
  
        {/* Poll Options */}
        <div className="px-4 pb-1 space-y-2">
          {options.map((label, i) => {
            const pct      = voted ? votes[i] : 0;
            const isLeader = voted && i === leading;
            const isVoted  = voted;
  
            return (
              <div
                key={i}
                className="relative h-11 rounded-xl overflow-hidden border transition-colors"
                style={{
                  borderColor: isLeader ? "#d47a03" : "#e2e8f0",
                  cursor: isVoted ? "default" : "pointer",
                }}
              >
                {/* Fill bar */}
                {isVoted && (
                  <div
                    className="absolute left-0 top-0 h-full rounded-xl transition-all duration-700"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: isLeader ? "#d47a0320" : "#f7fafc",
                    }}
                  />
                )}
  
                {/* Label */}
                <span
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-medium z-10"
                  style={{ color: isLeader ? "#b86a02" : "#2d3748" }}
                >
                  {label}
                </span>
  
                {/* Percentage */}
                {isVoted && (
                  <span
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold z-10"
                    style={{ color: isLeader ? "#d47a03" : "#718096" }}
                  >
                    {pct}%
                  </span>
                )}
  
                {/* Leading checkmark */}
                {isLeader && (
                  <div className="absolute right-10 top-1/2 -translate-y-1/2 z-10">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#d47a03" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                )}
              </div>
            );
          })}
        </div>
  
        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 mt-1">
          <div className="flex items-center gap-1.5 text-[#a0aec0]">
            <Users size={13} strokeWidth={1.75} />
            <span className="text-xs">
              {totalVotes > 0
                ? `${totalVotes.toLocaleString()} votes · ${timeLeft}`
                : timeLeft}
            </span>
          </div>
          <div className="flex items-center gap-4 text-[#a0aec0]">
            <button className="flex items-center gap-1 text-xs hover:text-[#2d3748] transition-colors">
              <MessageCircle size={15} strokeWidth={1.75} /> 48
            </button>
            <button className="flex items-center gap-1 text-xs hover:text-[#2d3748] transition-colors">
              <Heart size={15} strokeWidth={1.75} /> 312
            </button>
            <button className="hover:text-[#2d3748] transition-colors">
              <Share2 size={15} strokeWidth={1.75} />
            </button>
          </div>
        </div>
      </div>
    );
  }


// ─── Convenience map ───────────────────────────────────────────

export const PLATFORM_CARDS = {
    facebook: FacebookCard,
    instagram: InstagramReelCard,
    x: XCard,
    linkedin: LinkedInCard,
    youtube: YouTubeCard,
} as const;

export type Platform = keyof typeof PLATFORM_CARDS;

/**
 * Auto-selects the right card by platform name.
 *
 * <SocialMediaCard platform="x" name="Adya Prasad" content="..." />
 */
export function SocialMediaCard({ platform, ...props }: CardProps & { platform: Platform }) {
    const Card = PLATFORM_CARDS[platform];
    return <Card {...props} />;
}