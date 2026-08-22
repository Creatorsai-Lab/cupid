"use client";

import { useState } from "react";
import { ExternalLink, Image as ImageIcon } from "lucide-react";
import { type TrendArticle } from "@/lib/api";
import { timeAgo } from "@/lib/timeAgo";

/**
 * A single news article card.
 * Layout: image (left) + title/meta (right). Tailwind only.
 *
 * States handled:
 *   - With image:    show the image
 *   - No image:      show a placeholder with icon
 *   - Image fails:   onError swaps to placeholder
 *   - Long title:    line-clamp-3 prevents overflow
 *
 * Click anywhere on the card opens the article in a new tab.
 */
export function NewsCard({ article }: { article: TrendArticle }) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = article.image_url && !imageFailed;

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group border-grey-500 flex gap-4 rounded-4xl border bg-white p-2 transition-all duration-200 hover:border-[var(--color-primary)] hover:shadow-sm"
    >
      {/* Image (or placeholder) */}
      <div className="h-24 w-24 flex-shrink-0 overflow-hidden rounded-lg bg-[#fff6ed]">
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={article.image_url!}
            alt=""
            className="h-full w-full object-cover"
            onError={() => setImageFailed(true)}
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon size={24} className="text-[var(--color-primary)] opacity-50" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <h3
          className="line-clamp-3 text-sm leading-snug font-medium transition-colors group-hover:text-[var(--color-primary)]"
          style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
        >
          {article.title}
        </h3>

        <div
          className="mt-2 flex items-center gap-2 text-xs"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          <span className="max-w-[140px] truncate font-medium">{article.source}</span>
          <span>·</span>
          <span>{timeAgo(article.published_at)}</span>
          <ExternalLink
            size={11}
            className="ml-auto flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          />
        </div>
      </div>
    </a>
  );
}
