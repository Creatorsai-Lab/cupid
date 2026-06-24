export function YouTubeCard({
  name,
  content,
  time = "19.6M subscribers", // Adapting the 'time' prop to act as the subscriber count for this layout
  avatarUrl,
  mediaUrl,
}: CardProps) {
  return (
    <div className="h-fit w-full max-w-[800px] bg-white font-sans text-[#0f0f0f]">
      {/* 1. Video Thumbnail */}
      <MediaBlock
        mediaUrl={mediaUrl}
        alt="YouTube video"
        aspectRatio="16/9"
        platformColor="#ff0000"
        platformLabel="Video"
        isVideo
        className="w-full overflow-hidden rounded-xl"
      />

      {/* 2. Video Title */}
      <h2 className="mt-3 px-1 text-xl font-bold leading-tight text-[#0f0f0f]">
        {content}
      </h2>

      {/* 3. Channel Info & Actions Row */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-y-4 px-1">

        {/* Left Side: Channel Info, Join, and Subscribe */}
        <div className="flex items-center gap-4">
          <Avatar name={name} avatarUrl={avatarUrl} size={40} />
          <div className="flex flex-col">
            <div className="flex items-center gap-1">
              <span className="font-semibold text-[15px]">{name}</span>
              {/* Verified Badge SVG */}
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-[#606060]">
                <path d="M12,2C6.5,2,2,6.5,2,12c0,5.5,4.5,10,10,10s10-4.5,10-10C22,6.5,17.5,2,12,2z M9.8,17.3l-4.2-4.1L7,11.8l2.8,2.7L17,7.4l1.4,1.4L9.8,17.3z" />
              </svg>
            </div>
            <span className="text-xs text-[#606060]">{time}</span>
          </div>

          <div className="ml-1 flex items-center gap-2">
            <button className="rounded-full bg-[#f2f2f2] px-4 py-2 text-sm font-medium transition-colors hover:bg-[#e5e5e5]">
              Join
            </button>
            <button className="rounded-full bg-[#0f0f0f] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#272727]">
              Subscribe
            </button>
          </div>
        </div>

        {/* Right Side: Video Action Buttons */}
        <div className="flex items-center gap-2">
          {/* Like / Dislike Pill */}
          <div className="flex items-center rounded-full bg-[#f2f2f2]">
            <button className="flex items-center gap-1.5 rounded-l-full px-4 py-2 text-sm font-medium transition-colors hover:bg-[#e5e5e5]">
              <ThumbsUp size={18} strokeWidth={1.5} />
              154K
            </button>
            <div className="h-5 w-[1px] bg-[#d9d9d9]"></div>
            <button className="rounded-r-full px-4 py-2 transition-colors hover:bg-[#e5e5e5]">
              {/* Using rotate-180 to flip ThumbsUp into a ThumbsDown */}
              <ThumbsUp size={18} strokeWidth={1.5} className="rotate-180" />
            </button>
          </div>

          {/* Share Button */}
          <button className="flex items-center gap-1.5 rounded-full bg-[#f2f2f2] px-4 py-2 text-sm font-medium transition-colors hover:bg-[#e5e5e5]">
            <Share2 size={18} strokeWidth={1.5} />
            Share
          </button>

          {/* More Options Button */}
          <button className="flex items-center justify-center rounded-full bg-[#f2f2f2] p-2 transition-colors hover:bg-[#e5e5e5]">
            <MoreHorizontal size={18} strokeWidth={1.5} />
          </button>
        </div>

      </div>
    </div>
  );
}
