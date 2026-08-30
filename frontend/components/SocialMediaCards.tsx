"use client";

import { useState, useRef } from "react";

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
  ThumbsDown,
  MessageCircle,
  MessageSquareText,
  Share2,
  Send,
  Heart,
  Bookmark,
  MoreHorizontal,
  Earth,
  Repeat2,
  Play,
  Bell,
  Music2,
  ImageIcon,
  Video,
  Users,
  MoreVertical,
  ChartNoAxesColumn,
  EllipsisVertical,
  MessageCircleMore,
  CornerUpRight,
  ArrowLeft,
  Square,
} from "lucide-react";

// True when the media URL points at a video file (so we render <video>, not <img>).
function isVideoSrc(url?: string): boolean {
  return !!url && /\.(mp4|webm|mov|ogg)$/i.test(url);
}

/**
 * LazyVideo — never autoplays. Until the user clicks Play it only renders a
 * lightweight poster: the browser fetches metadata + the single frame at ~0.5s
 * (the `#t=0.5` media fragment), NOT the whole file. On click it swaps to the
 * real <video> and plays WITH sound (a user gesture lifts the autoplay-with-
 * audio block). Fills its (positioned) parent via `absolute inset-0`.
 */
function LazyVideo({ src }: { src: string }) {
  const [playing, setPlaying] = useState(false);

  if (playing) {
    return (
      <video
        src={src}
        className="absolute inset-0 h-full w-full bg-black object-cover cursor-pointer"
        autoPlay
        loop // Added: Makes the short loop automatically
        playsInline
        preload="auto"
        onClick={() => setPlaying(false)} // Added: Clicking the video pauses it and brings back the play button
        /* Notice `controls` has been completely removed from here */
      />
    );
  }

  return (
    <div className="absolute inset-0">
      {/* Poster frame only — preload="metadata" keeps this cheap */}
      <video
        src={`${src}#t=0.5`}
        className="absolute inset-0 h-full w-full object-cover"
        preload="metadata"
        muted
        playsInline
        tabIndex={-1}
        aria-hidden
      />
      <button
        type="button"
        onClick={() => setPlaying(true)}
        aria-label="Play video"
        className="absolute inset-0 grid place-items-center bg-black/10 transition-colors hover:bg-black/20"
      >
        <span className="grid h-14 w-14 place-items-center rounded-full bg-black/55 backdrop-blur-sm transition-transform hover:scale-105">
          <Play size={24} className="translate-x-0.5 text-white" fill="white" />
        </span>
      </button>
    </div>
  );
}
// ─── Shared types ──────────────────────────────────────────────

export interface CardProps {
  name: string;
  handle?: string;
  content: string;
  time?: string;
  avatarUrl?: string;
  /** Image or video thumbnail URL. Omit to show a platform-styled placeholder. */
  mediaUrl?: string;
  subscribers?:string;
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
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

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
        className={`flex-shrink-0 rounded-full object-cover ${ring}`}
        style={{
          width: size,
          height: size,
          ...(ringColor
            ? { outlineColor: ringColor, outline: `2.5px solid ${ringColor}`, outlineOffset: "2px" }
            : {}),
        }}
      />
    );
  }

  return (
    <div
      className="flex flex-shrink-0 items-center justify-center rounded-full font-bold text-white"
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
    const isVid = isVideoSrc(mediaUrl);
    return (
      <div className={`relative w-full overflow-hidden ${className}`}>
        {isVid ? (
          <LazyVideo src={mediaUrl} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl} alt={alt ?? "post media"} className="h-full w-full object-cover" />
        )}
        {isVideo && !isVid && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-full bg-black/50 p-3 backdrop-blur-sm">
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
      className={`relative flex w-full flex-col items-center justify-center gap-2 ${className}`}
      style={{
        background: `linear-gradient(135deg, ${platformColor}18, ${platformColor}30)`,
        borderTop: `1px solid ${platformColor}20`,
        borderBottom: `1px solid ${platformColor}20`,
      }}
    >
      <div className="rounded-full p-3" style={{ background: `${platformColor}20` }}>
        {isVideo ? (
          <Video size={28} style={{ color: platformColor, opacity: 0.7 }} />
        ) : (
          <ImageIcon size={28} style={{ color: platformColor, opacity: 0.7 }} />
        )}
      </div>
      <p className="text-sm font-medium" style={{ color: platformColor, opacity: 0.6 }}>
        {isVideo ? "Video" : platformLabel}
      </p>
    </div>
  );
}

// ─── 1. Facebook Card ──────────────────────────────────────────
export function FacebookCard({
  name,
  content,
  time = "Just now",
  avatarUrl,
  mediaUrl,
}: CardProps) {
  return (
    <div className="h-fit w-full max-w-[500px] overflow-hidden rounded-4xl border border-[#ddd] bg-white font-sans text-[#050505] shadow-sm">
      <div className="flex items-start gap-2.5 p-3 pb-2">
        <Avatar name={name} avatarUrl={avatarUrl} size={40} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{name}</p>
          <div className="m-0 flex items-center gap-1">
            <span className="text-sm text-[#65676b]">{time}</span>
            <span className="text-[#65676b]">·</span>
            <Earth size={11} className="text-[#65676b]" />
          </div>
        </div>
        <MoreHorizontal size={18} className="flex-shrink-0 text-[#65676b]" />
      </div>

      <p className="px-3 pb-2.5 text-sm leading-relaxed whitespace-pre-line">{content}</p>

      {/* Conditionally render MediaBlock only if mediaUrl exists */}
      {mediaUrl && (
        <MediaBlock mediaUrl={mediaUrl} />
      )}

      <div className="flex items-center justify-between px-3 py-1.5">
        <div className="flex items-center gap-1">
          <div className="flex -space-x-1">
            <div className="flex h-[18px] w-[18px] items-center justify-center rounded-full border border-white bg-[#1877f2]">
              <ThumbsUp size={9} className="text-white" strokeWidth={2.5} />
            </div>
            <div className="flex h-[18px] w-[18px] items-center justify-center rounded-full border border-white bg-[#f02849]">
              <Heart size={9} className="fill-white text-white" strokeWidth={0} />
            </div>
          </div>
          <span className="text-sm text-[#65676b]">0 comment · 4 shares</span>
        </div>
      </div>

      <div className="color-gray-500 flex gap-4 p-3">
        <ThumbsUp size={15} />
        <MessageCircle size={15} />
        <CornerUpRight size={15} />
      </div>
    </div>
  );
}
// ─── 2. Instagram Reel Card ────────────────────────────────────

export function InstagramReelCard({
  name,
  handle,
  content,
  time = "2h",
  avatarUrl,
  mediaUrl,
}: CardProps) {
  const user = handle ?? name.toLowerCase().replace(/\s/g, "");

  return (
    <div
      className="relative h-fit w-full max-w-[320px] overflow-hidden rounded-2xl bg-black font-sans text-white select-none"
      style={{ aspectRatio: "10/16" }}
    >
      {/* Full-bleed background media */}
      {mediaUrl ? (
        isVideoSrc(mediaUrl) ? (
          <LazyVideo src={mediaUrl} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl} alt="Reel" className="absolute inset-0 h-full w-full object-cover" />
        )
      ) : (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center gap-3"
          style={{ background: "linear-gradient(160deg,#833ab4,#fd1d1d,#fcb045)" }}
        >
          <div className="rounded-full bg-white/20 p-5 backdrop-blur-sm">
            <Video size={40} className="text-white" />
          </div>
          <p className="text-sm font-medium text-white/70">Reel</p>
        </div>
      )}

      {/* Gradient overlays */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />

      {/* Top bar */}
      <div className="absolute top-0 right-0 left-0 flex items-center justify-between px-4 pt-4">
        <div className="flex gap-4">
          <span className="border-b border-white pb-0.5 text-sm font-semibold">Reels</span>
          <span className="text-sm text-white/60">Friends</span>
        </div>
        <div className="rounded-full bg-white/20 p-1.5 backdrop-blur-sm">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
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
            <button className="rounded-full bg-black/20 p-2 backdrop-blur-sm transition-transform active:scale-90">
              <Icon size={24} className="text-white" strokeWidth={1.75} />
            </button>
            <span className="text-sm font-semibold text-white drop-shadow">{count}</span>
          </div>
        ))}
        {/* More */}
        <button className="mt-1">
          <MoreHorizontal size={22} className="text-white" />
        </button>
      </div>

      {/* Bottom info overlay */}
      <div className="absolute right-0 bottom-0 left-0 px-3 pr-16 pb-4">
        {/* Username row */}
        <div className="mb-2 flex items-center gap-2">
          <Avatar name={name} avatarUrl={avatarUrl} size={32} />
          <span className="text-sm font-semibold drop-shadow">{user}</span>
          {/* Verified */}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="#fff" className="flex-shrink-0">
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <button className="ml-auto rounded-md border border-white px-2.5 py-0.5 text-sm font-semibold transition-colors hover:bg-white/20">
            Follow
          </button>
        </div>

        {/* Caption */}
        <p className="line-clamp-2 text-sm leading-relaxed text-white/90 drop-shadow">{content}</p>

        {/* Audio */}
        <div className="mt-2 flex items-center gap-1.5">
          <Music2 size={12} className="flex-shrink-0 text-white/80" />
          <span className="truncate text-sm text-white/80">Original audio · {user}</span>
        </div>
      </div>
    </div>
  );
}

// Keep the old name as an alias for backwards compatibility
export const InstagramCard = InstagramReelCard;

// ─── 3. X Card ────────────────────────────────────────────────

export function XCard({ name, handle, content, time = "2h", avatarUrl, mediaUrl }: CardProps) {
  const user = handle ?? name.toLowerCase().replace(/\s/g, "");

  return (
    <div className="h-fit w-full max-w-[500px] overflow-hidden rounded-2xl border border-[#2f3336] bg-black font-sans text-white">
      <div className="flex gap-2 p-3">
        {/* Left Column: Avatar */}
        <div className="shrink-0">
          <Avatar name={name} avatarUrl={avatarUrl} size={40} />
        </div>

        {/* Right Column: Text, Media, and Actions */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold">{name}</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="#1d9bf0">
                  <path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91-1.01-1-2.52-1.26-3.9-.8-.66-1.31-1.9-2.19-3.34-2.19-1.44 0-2.68.88-3.34 2.19-1.38-.46-2.9-.2-3.91.81-1 1.01-1.26 2.52-.8 3.91C1.63 9.33.75 10.57.75 12c0 1.43.88 2.67 2.19 3.34-.46 1.39-.2 2.9.81 3.91 1.01 1 2.52 1.26 3.91.81.67 1.31 1.9 2.19 3.34 2.19 1.43 0 2.67-.88 3.33-2.19 1.39.45 2.9.19 3.91-.81 1.01-1.01 1.27-2.52.81-3.91 1.31-.67 2.19-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.26 2.26 4.8-5.23 1.47 1.36-6.2 6.77z" />
                </svg>
                <p className="text-sm text-[#71767b]">@{user}</p>
              </div>
            </div>
            <MoreHorizontal size={18} className="text-[#71767b]" />
          </div>

          <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-[#e7e9ea]">
            {content}
          </p>

          {/* MediaBlock is now nested inside the right column */}
          <MediaBlock
            mediaUrl={mediaUrl}
            alt="X post media"
            aspectRatio="16/9"
            platformColor="#1d9bf0"
            platformLabel="Media"
            className="mt-3 rounded-2xl border border-[#2f3336]"
          />

          {/* Action buttons are now nested inside the right column */}
          <div className="mt-3 flex items-center justify-between pr-2">
            {[
              { icon: MessageCircle, count: "" },
              { icon: Repeat2, count: "" },
              { icon: Heart, count: "" },
              { icon: ChartNoAxesColumn, count: "" },
              { icon: Bookmark, count: null },
              { icon: Share2, count: null },
            ].map(({ icon: Icon, count }, i) => (
              <button
                key={i}
                className="group flex items-center gap-1 text-[#71767b] transition-colors hover:text-[#1d9bf0]"
              >
                <div className="rounded-full p-1.5 transition-colors group-hover:bg-[#1d9bf0]/10">
                  <Icon size={16} strokeWidth={1.75} />
                </div>
                {count && <span className="text-sm">{count}</span>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── 4. LinkedIn Card ──────────────────────────────────────────

export function LinkedInCard({
  name,
  handle,
  content,
  time = "2h",
  avatarUrl,
  mediaUrl,
}: CardProps) {
  const subtitle = handle ?? "Content Creator · Building in public";
  const preview = content.length > 200 ? content.slice(0, 200) : content;
  const hasMore = content.length > 200;

  return (
    <div className="h-fit w-full max-w-[555px] overflow-hidden rounded-lg border border-[#e0e0e0] bg-white font-sans text-[#191919] shadow-sm">
      <div className="flex items-start gap-2.5 p-4 pb-3">
        <Avatar name={name} avatarUrl={avatarUrl} size={48} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{name}</p>
          <p className="truncate text-sm text-[#666]">{subtitle}</p>
          <div className="flex items-center gap-1">
            <span className="text-sm text-[#666]">{time} ·</span>
            <Earth size={11} className="text-[#666]" />
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <button className="text-[12px] font-semibold text-[#0a66c2]">+ Follow</button>
          <EllipsisVertical size={16} className="text-[#666]" />
        </div>
      </div>

      <div className="px-4 pb-3 text-sm leading-relaxed whitespace-pre-line text-[#191919]">
        {preview}
        {hasMore && (
          <span className="text-[#666]">
            …<button className="ml-1 font-semibold text-[#191919]">see more</button>
          </span>
        )}
      </div>

      <MediaBlock
        mediaUrl={mediaUrl}
        alt="LinkedIn post"
        platformColor="#0a66c2"
        platformLabel="Image"
      />

      <div className="flex items-center justify-end border-t border-b border-[#e0e0e0] px-4 py-2 text-sm text-[#666]">
        <span>0 comments · 0 reposts</span>
      </div>

      <div className="flex justify-between p-4">
        <ThumbsUp size={15} strokeWidth={1.75} />
        <MessageCircleMore size={15} strokeWidth={1.75} />
        <Repeat2 size={15} strokeWidth={1.75} />
        <Send size={15} strokeWidth={1.75} />
      </div>
    </div>
  );
}

// 1. The minimal Lazy Video Component for standard 16:9 landscape videos
function LazyLandscapeVideo({ src }: { src: string }) {
  const [playing, setPlaying] = useState(false);

  if (playing) {
    return (
      <video
        src={src}
        className="absolute inset-0 h-full w-full cursor-pointer bg-black object-cover"
        autoPlay
        playsInline
        preload="auto"
        onClick={() => setPlaying(false)} // Pauses the video on click
        /* Notice `controls` has been completely removed */
      />
    );
  }

  return (
    <div className="absolute inset-0">
      {/* Poster frame */}
      <video
        src={`${src}#t=0.5`}
        className="absolute inset-0 h-full w-full object-cover"
        preload="metadata"
        muted
        playsInline
        tabIndex={-1}
        aria-hidden
      />
      {/* Play Button Overlay */}
      <button
        type="button"
        onClick={() => setPlaying(true)}
        aria-label="Play video"
        className="group absolute inset-0 grid place-items-center bg-black/10 transition-colors hover:bg-black/20"
      >
        {/* YouTube style pill/rectangle play button */}
        <span className="grid h-12 w-16 place-items-center rounded-4xl bg-black/70 backdrop-blur-sm transition-all group-hover:scale-105 group-hover:bg-[#ff0000]">
          <Play size={24} className="text-white" fill="white" />
        </span>
      </button>
    </div>
  );
}

// ─── 5. YouTube wide Card ─────────────────────────────────
// 2. The Updated YouTube Card
export function YouTubeCard({
  name,
  content,
  avatarUrl,
  mediaUrl,
}: CardProps) {
  return (
    <div className="h-fit w-full max-w-[540px] overflow-hidden rounded-4xl border border-[#e5e5e5] bg-white p-3 font-sans text-[#0f0f0f]">

      {/* Replaced MediaBlock with a relative 16:9 container for the LazyVideo */}
      {mediaUrl && (
        <div className="relative w-full aspect-video overflow-hidden rounded-4xl bg-gray-100">
          <LazyLandscapeVideo src={mediaUrl} />
        </div>
      )}

      <p className="mt-3 text-base leading-relaxed whitespace-pre-line text-[#0f0f0f]">
        {content}
      </p>

      <div className="mt-3">
        <div className="flex items-center gap-3">
          <Avatar name={name} avatarUrl={avatarUrl} size={36} />

          {/* flex-1 pushes the buttons to the right */}
          <div className="flex flex-1 flex-col">
            <span className="text-sm font-bold">{name}</span>
          </div>

          <div className="flex items-center gap-2">
            <button className="rounded-full bg-[#0f0f0f] px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#272727]">
              Subscribe
            </button>

            {/* Grouped Like/Dislike together */}
            <div className="flex items-center">
              <button className="flex items-center gap-1.5 rounded-l-full px-2 py-1.5 text-sm font-medium transition-colors hover:bg-[#e5e5e5]">
                <ThumbsUp size={16} strokeWidth={1.5} />
              </button>
              <button className="rounded-r-full px-2 py-1.5 transition-colors hover:bg-[#e5e5e5]">
                <ThumbsUp size={16} strokeWidth={1.5} className="rotate-180" />
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

// 6. YouTube Short Card

export function YouTubeShortsCard({ name, handle, content, avatarUrl, mediaUrl }: CardProps) {
  const user = handle ?? name.toLowerCase().replace(/\s/g, "");

  return (
    <div
      className="relative h-fit overflow-hidden rounded-2xl bg-black font-sans text-white"
      style={{ width: 320, aspectRatio: "10/16" }}
    >
      {/* Background media or placeholder */}
      {mediaUrl ? (
        isVideoSrc(mediaUrl) ? (
          <LazyVideo src={mediaUrl} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={mediaUrl} alt="Short" className="absolute inset-0 h-full w-full object-cover" />
        )
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
          <Play size={28} fill="#ffffffff" strokeWidth={0} />
        </div>
      )}

      {/* Gradient overlays */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(to top,rgba(0,0,0,.85) 0%,transparent 45%,rgba(192, 192, 192, 0) 100%)",
        }}
      />

      {/* Top bar */}
      <div className="absolute top-0 right-0 left-0 flex items-center justify-between px-3.5 pt-3.5">
        <div className="flex items-center gap-2">
          <ArrowLeft size={18} strokeWidth={2} />
        </div>
        <div className="flex gap-3.5 text-white">
          <svg
            width="19"
            height="19"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <MoreVertical size={19} />
        </div>
      </div>

      {/* Right action column */}
      <div className="absolute right-2.5 bottom-2 flex flex-col items-center gap-2 bg-transparent">
        {/* Like */}
        <ActionIcon icon={ThumbsUp} count="" />
        {/* Comment */}
        <ActionIcon icon={ThumbsDown} count="" />
        <ActionIcon icon={MessageSquareText} count="" />
        <ActionIcon icon={CornerUpRight} count="" />
      </div>

      {/* Bottom info */}
      <div className="absolute right-0 bottom-0 left-0 px-3 pr-16 pb-4">
        {/* Username row */}
        <div className="mb-2 flex items-center gap-2">
          <Avatar name={name} avatarUrl={avatarUrl} size={28} />
          <span className="text-sm drop-shadow">@{user}</span>
          <button className="rounded-2xl bg-white px-2.5 py-0.5 text-[11px] text-black">
            Subscribe
          </button>
        </div>
        {/* Caption */}
        <p className="line-clamp-2 text-sm leading-relaxed text-white/90 drop-shadow">{content}</p>
      </div>
    </div>
  );
}

// helper used only inside YouTubeShortsCard
function ActionIcon({ icon: Icon, count }: { icon: React.ElementType; count: string }) {
  return (
    <div className="flex flex-col items-center">
      <div className="p-2.5 drop-shadow">
        <Icon size={18} strokeWidth={1.75} className="text-white" />
      </div>
      <span className="text-[11px] font-bold drop-shadow">{count}</span>
    </div>
  );
}

// 7. Poll Card
export interface QuizCardProps {
  name: string;
  handle?: string;
  avatarUrl?: string;
  question: string;
  options: [string, string, string, string];
  votes?: [number, number, number, number];
  totalVotes?: number;
  timeLeft?: string;
  time?: string;
}

export function QuizCard({
  name,
  handle,
  avatarUrl,
  question,
  options,
  votes,
  totalVotes = 0,
  timeLeft = "24h left",
  time = "1h",
}: QuizCardProps) {
  const user = handle ?? name.toLowerCase().replace(/\s/g, "");
  const voted = !!votes;
  const leading = voted ? votes.indexOf(Math.max(...votes)) : -1;

  return (
    <div className="h-fit w-full max-w-[420px] overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white font-sans text-[#1a202c] shadow-sm">
      {/* Header */}
      <div className="flex items-start gap-3 p-4 pb-3">
        <Avatar name={name} avatarUrl={avatarUrl} size={42} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm leading-tight font-bold">{name}</p>
              <p className="mt-0.5 text-sm text-[#718096]">
                @{user} · {time}
              </p>
            </div>
            <MoreHorizontal size={18} className="flex-shrink-0 text-[#a0aec0]" />
          </div>
          <p className="mt-2.5 text-sm leading-relaxed font-medium text-[#2d3748]">{question}</p>
        </div>
      </div>

      {/* Poll Options */}
      <div className="space-y-2 px-4 pb-1">
        {options.map((label, i) => {
          const pct = voted ? votes[i] : 0;
          const isLeader = voted && i === leading;
          const isVoted = voted;

          return (
            <div
              key={i}
              className="relative h-11 overflow-hidden rounded-4xl border transition-colors"
              style={{
                borderColor: isLeader ? "#d47a03" : "#e2e8f0",
                cursor: isVoted ? "default" : "pointer",
              }}
            >
              {/* Fill bar */}
              {isVoted && (
                <div
                  className="absolute top-0 left-0 h-full rounded-4xl transition-all duration-700"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: isLeader ? "#d47a0320" : "#f7fafc",
                  }}
                />
              )}

              {/* Label */}
              <span
                className="absolute top-1/2 left-3 z-10 -translate-y-1/2 text-sm font-medium"
                style={{ color: isLeader ? "#b86a02" : "#2d3748" }}
              >
                {label}
              </span>

              {/* Percentage */}
              {isVoted && (
                <span
                  className="absolute top-1/2 right-3 z-10 -translate-y-1/2 text-sm font-bold"
                  style={{ color: isLeader ? "#d47a03" : "#718096" }}
                >
                  {pct}%
                </span>
              )}

              {/* Leading checkmark */}
              {isLeader && (
                <div className="absolute top-1/2 right-10 z-10 -translate-y-1/2">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#d47a03"
                    strokeWidth="2.5"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="mt-1 flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-1.5 text-[#a0aec0]">
          <Users size={13} strokeWidth={1.75} />
          <span className="text-sm">
            {totalVotes > 0 ? `${totalVotes.toLocaleString()} votes · ${timeLeft}` : timeLeft}
          </span>
        </div>
        <div className="flex items-center gap-4 text-[#a0aec0]">
          <button className="flex items-center gap-1 text-sm transition-colors hover:text-[#2d3748]">
            <MessageCircle size={15} strokeWidth={1.75} /> 48
          </button>
          <button className="flex items-center gap-1 text-sm transition-colors hover:text-[#2d3748]">
            <Heart size={15} strokeWidth={1.75} /> 312
          </button>
          <button className="transition-colors hover:text-[#2d3748]">
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
