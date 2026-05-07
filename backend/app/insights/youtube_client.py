"""
YouTube API Client - wraps the YouTube Data + Analytics APIs.

1. WHY A SEPARATE FILE
----------------------
The HTTP details of YouTube's APIs (URLs, auth header format, response
parsing) are messy. We isolate them in this client so the sync logic
in sync.py can stay focused on "what do we want" rather than "how does
YouTube format their response."

2. THREE API ENDPOINTS WE USE
-----------------------------
i) Channels API (Data API v3)
   GET https://www.googleapis.com/youtube/v3/channels?mine=true&part=...
   Returns: subscriber count, total view count, total video count
   Cost: 1 quota unit per call

ii) Search API (Data API v3)
   GET https://www.googleapis.com/youtube/v3/search?forMine=true&type=video
   Returns: list of recent videos by this channel
   Cost: 100 quota units per call (THE EXPENSIVE ONE)

iii) Videos API (Data API v3)
   GET https://www.googleapis.com/youtube/v3/videos?id=...&part=statistics
   Returns: per-video views, likes, comments
   Cost: 1 unit per call

For 1 user x 1 sync: ~100-110 units. With 10K daily quota, we can
sync 90 users x 1 sync/day OR 15 users x 6 syncs/day. Plenty for MVP.

3. ERRORS WE EXPLICITLY HANDLE
-----------------------------
- 401: token expired (shouldn't happen — token_manager should prevent)
- 403: quota exceeded OR insufficient scopes
- 404: channel deleted / video deleted (skip and continue)
- 429: rate limited (back off; not common at our scale)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TypedDict

import httpx

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


# ─── Type definitions ──────────────────────────────────────────

class ChannelStats(TypedDict):
    """Aggregated channel-level numbers."""
    channel_id: str
    title: str
    subscriber_count: int
    total_views: int
    total_videos: int
    custom_url: str | None


class VideoStats(TypedDict):
    """Per-video metrics."""
    video_id: str
    title: str
    published_at: datetime
    thumbnail_url: str | None
    views: int
    likes: int
    comments: int
    duration_seconds: int | None


# ─── Exceptions ────────────────────────────────────────────────

class YouTubeAPIError(Exception):
    """Raised when YouTube returns a non-recoverable error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"YouTube API {status_code}: {message}")


# ─── Channel stats ─────────────────────────────────────────────

async def get_channel_stats(access_token: str) -> ChannelStats:
    """
    Fetch the authenticated user's channel stats.

    Single API call, returns the high-level numbers used for stat cards.
    """
    url = f"{YOUTUBE_API_BASE}/channels"
    params = {
        "mine":  "true",
        "part":  "snippet,statistics",
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params, headers=headers)

    _raise_for_status(response, "channel stats")

    data = response.json()
    items = data.get("items", [])
    if not items:
        raise YouTubeAPIError(
            404,
            "No YouTube channel found. User may have deleted it.",
        )

    channel = items[0]
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})

    return {
        "channel_id":       channel["id"],
        "title":            snippet.get("title", ""),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "total_views":      int(stats.get("viewCount", 0)),
        "total_videos":     int(stats.get("videoCount", 0)),
        "custom_url":       snippet.get("customUrl"),
    }


# ─── Recent videos ─────────────────────────────────────────────

async def get_recent_videos(
    access_token: str,
    max_results: int = 25,
) -> list[VideoStats]:
    """
    Fetch the user's most recent videos with full metric data.

    Two-step process to be quota-efficient:
        1. Search to get video IDs (1 expensive call, 100 units)
        2. Videos endpoint to get stats for those IDs (1 cheap call, 1 unit)

    Returns up to max_results videos sorted by publish date (newest first).
    Empty list if the channel has no videos.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 1: Search for video IDs
    search_url = f"{YOUTUBE_API_BASE}/search"
    search_params = {
        "forMine":     "true",
        "type":        "video",
        "part":        "id",
        "maxResults":  str(min(max_results, 50)),
        "order":       "date",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        search_resp = await client.get(
            search_url, params=search_params, headers=headers,
        )
    _raise_for_status(search_resp, "search videos")

    search_data = search_resp.json()
    video_ids = [
        item["id"]["videoId"]
        for item in search_data.get("items", [])
        if item.get("id", {}).get("videoId")
    ]

    if not video_ids:
        return []

    # Step 2: Get full stats for those videos
    videos_url = f"{YOUTUBE_API_BASE}/videos"
    videos_params = {
        "id":   ",".join(video_ids),
        "part": "snippet,statistics,contentDetails",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        videos_resp = await client.get(
            videos_url, params=videos_params, headers=headers,
        )
    _raise_for_status(videos_resp, "video stats")

    videos_data = videos_resp.json()

    return [_parse_video(item) for item in videos_data.get("items", [])]


def _parse_video(item: dict[str, Any]) -> VideoStats:
    """Convert a YouTube API video item to our normalized shape."""
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    # Thumbnails: prefer high-res, fall back to medium, then default
    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = (
        (thumbnails.get("maxres") or {}).get("url")
        or (thumbnails.get("high") or {}).get("url")
        or (thumbnails.get("medium") or {}).get("url")
        or (thumbnails.get("default") or {}).get("url")
    )

    return {
        "video_id":     item["id"],
        "title":        snippet.get("title", ""),
        "published_at": _parse_iso(snippet.get("publishedAt", "")),
        "thumbnail_url": thumbnail_url,
        "views":        int(stats.get("viewCount", 0)),
        "likes":        int(stats.get("likeCount", 0)),
        "comments":     int(stats.get("commentCount", 0)),
        "duration_seconds": _parse_iso8601_duration(content.get("duration")),
    }


# ─── Helpers ───────────────────────────────────────────────────

def _raise_for_status(response: httpx.Response, operation: str) -> None:
    """Convert YouTube API errors into our exception type."""
    if response.status_code < 400:
        return

    try:
        body = response.json()
        message = body.get("error", {}).get("message", response.text[:200])
    except Exception:
        message = response.text[:200]

    logger.warning(
        "[youtube_client] %s failed: %d %s",
        operation, response.status_code, message,
    )
    raise YouTubeAPIError(response.status_code, message)


def _parse_iso(raw: str) -> datetime:
    """Parse ISO 8601 datetime; fall back to now() if malformed."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now()


def _parse_iso8601_duration(raw: str | None) -> int | None:
    """
    YouTube returns durations like "PT4M13S" (ISO 8601 duration format).
    We parse to seconds. None on malformed input.

    Why parse? Useful for filtering Shorts (<60s) vs regular videos.
    """
    if not raw or not raw.startswith("PT"):
        return None

    import re
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
    match = pattern.match(raw)
    if not match:
        return None

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds