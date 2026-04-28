"use client";

import { useState } from "react";
import { ExternalLink, Image as ImageIcon } from "lucide-react";
import { type TrendArticle } from "@/lib/api";
import {timeAgo} from "@/lib/timeAgo";

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
      className="group flex gap-4 p-2 rounded-xl border border-grey-500 bg-white hover:border-[var(--color-primary)] hover:shadow-sm transition-all duration-200"
    >
      {/* Image (or placeholder) */}
      <div className="flex-shrink-0 w-24 h-24 rounded-lg overflow-hidden bg-[#fff6ed]">
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={article.image_url!}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImageFailed(true)}
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon size={24} className="text-[var(--color-primary)] opacity-50" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 flex flex-col justify-between">
        <h3
          className="text-sm font-medium leading-snug line-clamp-3 group-hover:text-[var(--color-primary)] transition-colors"
          style={{ color: "var(--color-text)", fontFamily: "var(--font-body)" }}
        >
          {article.title}
        </h3>

        <div
          className="flex items-center gap-2 mt-2 text-xs"
          style={{ color: "var(--color-muted)", fontFamily: "var(--font-body)" }}
        >
          <span className="font-medium truncate max-w-[140px]">{article.source}</span>
          <span>·</span>
          <span>{timeAgo(article.published_at)}</span>
          <ExternalLink
            size={11}
            className="ml-auto flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          />
        </div>
      </div>
    </a>
  );
}