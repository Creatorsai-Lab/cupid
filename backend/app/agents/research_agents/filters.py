"""Retrieval, content filtering, scoring, and selection for the research pipeline."""

from __future__ import annotations

import hashlib
import ipaddress
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

from app.agents.research_agents.config import CONFIG, Config
from app.agents.research_agents.models import (
    CandidatePage,
    EvaluatedPage,
    ExtractedDocument,
    FreshnessMode,
    PageScores,
    ResearchBrief,
)
from app.agents.research_agents.planning import (
    _normalized_text,
    _required_freshness_window,
)

# indetify actual published domain
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())
# recognize url tracking parameters
_TRACKING_QUERY_KEY = re.compile(r"^(?:utm_[^=]*|fbclid|gclid)$", re.IGNORECASE)
# remove metadata/header lines produced
_JINA_HEADER = re.compile(
    r"^(?:Title|URL Source|Published Time|Number of Pages|Warning|Markdown Content):\s*.*$",
    re.IGNORECASE,
)
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]+)\]\([^)]*\)")
_MARKDOWN_LINK_DESTINATION = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# detects URLs appearing directly in text.
_BARE_URL = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]{}]+", re.IGNORECASE)
_SPACE = re.compile(r"[^\S\r\n]+")
_LISTING_SEGMENTS = frozenset(
    {
        "category",
        "categories",
        "tag",
        "tags",
        "archive",
        "archives",
        "feed",
        "search",
        "results",
        "page",
        "author",
    }
)
_FEED_PATHS = frozenset({"rss", "feed", "atom", "atom.xml", "rss.xml", "feed.xml"})
_LISTING_TITLES = re.compile(
    r"\b(?:search results?|latest (?:stories|posts|articles)|all (?:posts|articles)|archive|categories|tags)\b",
    re.IGNORECASE,
)
_PAYWALL_OR_BOT = re.compile(
    r"\b(?:subscribe to continue|subscription required|sign in to continue|access denied|"
    r"captcha|verify you are human|unusual traffic|temporarily unavailable|error 404|page not found|"
    r"request blocked|enable cookies to continue)\b",
    re.IGNORECASE,
)
# detect writing systems
_SCRIPT_PATTERNS = {
    "arabic": re.compile(
        r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]"
    ),
    "bengali": re.compile(r"[\u0980-\u09ff]"),
    "cyrillic": re.compile(r"[\u0400-\u052f\u2de0-\u2dff\ua640-\ua69f]"),
    "devanagari": re.compile(r"[\u0900-\u097f\ua8e0-\ua8ff]"),
    "greek": re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]"),
    "gujarati": re.compile(r"[\u0a80-\u0aff]"),
    "gurmukhi": re.compile(r"[\u0a00-\u0a7f]"),
    "han": re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"),
    "hangul": re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]"),
    "hebrew": re.compile(r"[\u0590-\u05ff\ufb1d-\ufb4f]"),
    "hiragana": re.compile(r"[\u3040-\u309f]"),
    "kannada": re.compile(r"[\u0c80-\u0cff]"),
    "katakana": re.compile(r"[\u30a0-\u30ff\u31f0-\u31ff]"),
    "malayalam": re.compile(r"[\u0d00-\u0d7f]"),
    "tamil": re.compile(r"[\u0b80-\u0bff]"),
    "telugu": re.compile(r"[\u0c00-\u0c7f]"),
    "thai": re.compile(r"[\u0e00-\u0e7f]"),
}
_EXPECTED_SCRIPTS_BY_LANGUAGE = {
    "ar": frozenset({"arabic"}),
    "bn": frozenset({"bengali"}),
    "en": frozenset(),
    "el": frozenset({"greek"}),
    "fa": frozenset({"arabic"}),
    "gu": frozenset({"gujarati"}),
    "he": frozenset({"hebrew"}),
    "hi": frozenset({"devanagari"}),
    "ja": frozenset({"han", "hiragana", "katakana"}),
    "kn": frozenset({"kannada"}),
    "ko": frozenset({"han", "hangul"}),
    "ml": frozenset({"malayalam"}),
    "mr": frozenset({"devanagari"}),
    "ne": frozenset({"devanagari"}),
    "pa": frozenset({"gurmukhi"}),
    "ru": frozenset({"cyrillic"}),
    "ta": frozenset({"tamil"}),
    "te": frozenset({"telugu"}),
    "th": frozenset({"thai"}),
    "uk": frozenset({"cyrillic"}),
    "ur": frozenset({"arabic"}),
    "zh": frozenset({"han"}),
}
_ENGLISH_COMMON_WORDS = frozenset(
    {
        "the",
        "and",
        "of",
        "to",
        "in",
        "for",
        "with",
        "that",
        "this",
        "is",
        "on",
        "as",
        "by",
        "from",
    }
)
_CLEAR_NON_ENGLISH_STOPWORDS = (
    frozenset(
        {
            "el",
            "la",
            "los",
            "las",
            "de",
            "del",
            "y",
            "en",
            "que",
            "para",
            "por",
            "con",
            "una",
            "un",
            "es",
            "este",
            "esta",
            "artículo",
            "articulo",
            "políticas",
            "politicas",
            "públicas",
            "publicas",
        }
    ),
    frozenset(
        {
            "le",
            "la",
            "les",
            "de",
            "des",
            "et",
            "en",
            "que",
            "pour",
            "avec",
            "une",
            "un",
            "est",
            "ce",
            "cette",
            "article",
            "politiques",
            "publiques",
        }
    ),
    frozenset(
        {
            "der",
            "die",
            "das",
            "und",
            "den",
            "von",
            "mit",
            "für",
            "eine",
            "ein",
            "ist",
            "dieser",
            "artikel",
            "politik",
        }
    ),
    frozenset(
        {
            "o",
            "a",
            "os",
            "as",
            "de",
            "do",
            "da",
            "e",
            "em",
            "que",
            "para",
            "com",
            "uma",
            "um",
            "este",
            "artigo",
            "políticas",
            "publicas",
        }
    ),
)
_GENERIC_PATH_SEGMENTS = frozenset(
    {
        "about",
        "archive",
        "article",
        "articles",
        "blog",
        "category",
        "home",
        "news",
        "post",
        "posts",
        "section",
        "story",
        "tag",
        "topics",
    }
)
_NON_ARTICLE_TYPES = frozenset({"collectionpage", "itemlist", "searchresultspage"})
_NAVIGATION_LABELS = frozenset(
    {
        "about",
        "account",
        "archive",
        "contact",
        "cookie",
        "cookies",
        "home",
        "log in",
        "login",
        "menu",
        "news",
        "privacy",
        "search",
        "sign in",
        "signin",
        "subscribe",
        "terms",
        "topics",
    }
)
_FOOTER_BOILERPLATE = re.compile(
    r"^(?:"
    r"all rights reserved\.?|"
    r"(?:privacy|cookie) policy|"
    r"terms of (?:service|use)|"
    r"(?:©|copyright)\s*(?:\d{4}(?:[-–]\d{4})?\s*)?[^.]*?\.\s*all rights reserved\.?"
    r")$",
    re.IGNORECASE,
)
_EMPTY_LINK = re.compile(r"!?\[\s*\]\([^)]*\)")
_JINA_LIST_PREFIX = re.compile(r"^list \d+ of \d+\s*", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_CHECKBOX = re.compile(r"^\[[ xX]\]\s*")
# Section headings whose whole section is site furniture, not article content.
_NOISE_HEADING = re.compile(
    r"^(?:most (?:viewed|read|popular|shared)|more (?:from|stories|on)|related(?: (?:articles|stories|content|topics))?|"
    r"read (?:next|more|also)|you may also like|recommended(?: for you)?|trending|popular(?: now)?|"
    r"top stories|latest(?: stories| news)?|explore more(?: on these topics)?|share(?: this)?|"
    r"support (?:us|the \w+)|newsletters?|sign up.*|subscribe.*|follow us|comments?|advertisement|"
    r"sponsored(?: content)?|contents|table of contents|in this article|on this page|navigation|footer)\b",
    re.IGNORECASE,
)
# Whole-line site chrome that survives link stripping.
_STANDALONE_BOILERPLATE = re.compile(
    r"^(?:skip to (?:main )?content(?:skip to navigation)?|skip to navigation|sign in|log ?in|sign up|subscribe|"
    r"print subscriptions?|newsletters?|support (?:us|once.*|another way)|renews (?:every|annually).*|"
    r"cancel anytime\.?|free trial|\d+-day(?: free trial)?|annual|intro offer|\$\d+(?:\.\d+)?(?:/monthly| a month)?|"
    r"support \$\d.*|we welcome support of any size.*|"
    r"\d+% off|become an insider.*|this story is available exclusively.*|you'?re currently following this author.*|"
    r"click to unsubscribe.*|view image in fullscreen|toggle caption|close dialogue.*|next image|previous image|"
    r"show more|hide expanded menu|search input.*|download the app|have an account\??\s*\.?|learn more\s*\|?|continue|"
    r"remind me in \w+|unlock.*benefits:?|accepted payment methods.*|explore more on these topics|"
    r"this article is more than .*old|share|reuse this content|back to top|prefer .* on google|claim discount(?:claim discount)?|"
    r"read (?:more|next)|related(?: (?:articles|stories|content))?|advertisement|sponsored(?: content)?|"
    r"most (?:viewed|read|popular)(?: .*)?|more from app.agents.research_agents.*|trending|comments?|image \d+(?:\b.*)?|list of \d+ items?|"
    r"list \d+ of \d+|(?:[a-z]{2}|international|europe|australia) edition|\+\d+(?: more)?)$",
    re.IGNORECASE,
)
_GLUED_BYLINE = re.compile(r"^By[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}$")
# Reader-appeal and subscription copy: a paragraph matching two or more of these is a plea,
# and a section where at least 40% of paragraphs are pleas is a fundraising block.
_APPEAL_MARKERS = (
    re.compile(
        r"\bsupport (?:us|the \w+|once|of any size|\$|we)|\bsupport(?:ers)? like you\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsubscri", re.IGNORECASE),
    re.compile(r"\bdonat", re.IGNORECASE),
    re.compile(r"\$\d"),
    re.compile(r"\b(?:a|per) month\b|\bmonthly\b|\bannual(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bjournalism\b", re.IGNORECASE),
    re.compile(r"\bpaywall", re.IGNORECASE),
    re.compile(r"\bcancel anytime\b|\bfree trial\b|\bintro offer\b", re.IGNORECASE),
    re.compile(r"\bsign up\b|\bnewsletter", re.IGNORECASE),
    re.compile(r"\bunlimited access\b|\bad-free\b|\ball-access\b", re.IGNORECASE),
    re.compile(
        r"\bfundrais|\bgratefully received\b|\breaders like you\b", re.IGNORECASE
    ),
)
_CARD_CALL_TO_ACTION = re.compile(r"^(?:read|learn|view) more$", re.IGNORECASE)
_SCORE_COMPONENTS = (
    "relevance",
    "freshness",
    "authority",
    "information_density",
    "persona_utility",
    "novelty",
    "content_quality",
)


ValidatedPage = tuple[CandidatePage, ExtractedDocument, str, str]


# ensure datetime represented in UTC
def _as_utc(value: datetime) -> datetime:
    return (
        value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    ).astimezone(UTC)


def canonicalize_url(url: str) -> str:
    """Convert different versions of the same URL into one stable identity.
    Return a stable URL identity key while leaving fetch URLs untouched."""
    normalized_url = url.strip()
    try:
        parsed = urlsplit(normalized_url)
        port = parsed.port
    except (TypeError, ValueError):
        return normalized_url
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    netloc = hostname
    try:
        is_ipv6 = ipaddress.ip_address(hostname).version == 6
    except ValueError:
        is_ipv6 = False
    if is_ipv6:
        netloc = f"[{hostname}]"
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _TRACKING_QUERY_KEY.match(key)
    ]
    query = urlencode(
        sorted(query_pairs), doseq=True
    )  # Sort urls query parameters for proper filtering
    return urlunsplit((scheme, netloc, path, query, ""))


def publisher_domain(url: str) -> str:
    """Return the registrable publisher domain without consulting the network."""
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not hostname:
        return ""
    extracted = _EXTRACT(hostname)
    return extracted.top_domain_under_public_suffix or hostname


def _unsafe_url(url: str) -> bool:
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in {"http", "https"}:
            return True
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return True
        parsed.port
        hostname = parsed.hostname.rstrip(".").lower()
    except (TypeError, ValueError):
        return True

    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return not _valid_hostname(hostname)
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_reserved,
            address.is_multicast,
            address.is_unspecified,
        )
    )


def _valid_hostname(hostname: str) -> bool:
    """Validate a DNS name after URL parsing, including IDNA hostnames."""
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if not ascii_hostname or len(ascii_hostname) > 253 or ".." in ascii_hostname:
        return False
    label = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
    return all(label.fullmatch(part) is not None for part in ascii_hostname.split("."))


def _is_blocked_domain(hostname: str, blocked_domains: frozenset[str]) -> bool:
    """Check whether a domain is in configured blocked list"""
    normalized = hostname.lower().rstrip(".")
    return any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in blocked_domains
    )


def _is_listing_url_or_title(url: str, title: str) -> bool:
    """check whether this page list/link other pages rather than the actual article?
    Ex: /search, /archieve, /category"""
    parsed = urlsplit(url)
    segments = [segment.lower() for segment in parsed.path.split("/") if segment]
    if not segments:
        return True
    if any(segment in _LISTING_SEGMENTS for segment in segments):
        return True
    if segments[-1] in _FEED_PATHS:
        return True
    if (
        len(segments) == 2
        and re.fullmatch(r"\d{4}", segments[0])
        and re.fullmatch(r"(?:0?[1-9]|1[0-2])", segments[1])
    ):
        return True
    if len(segments) >= 2 and segments[-2] == "page" and segments[-1].isdigit():
        return True
    query_keys = {
        key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    }
    if {"s", "search", "paged", "page", "category", "tag"} & query_keys:
        return True
    return bool(_LISTING_TITLES.search(title))


def early_rejection_reason(url: str, title: str, config: Config) -> str | None:
    """Return the combined deterministic early-rejection code, if any."""
    if _unsafe_url(url):
        return "unsafe_url"
    parsed = urlsplit(url.strip())
    if _is_blocked_domain(parsed.hostname or "", config.blocked_domains):
        return "blocked_domain"
    if not title.strip():
        return "empty_title"
    if _is_listing_url_or_title(url, title):
        return "listing_url"
    return None


FRESH = "fresh"
STALE = "stale"
UNKNOWN_FRESHNESS = "unknown"


def freshness_status(
    candidate: CandidatePage, brief: ResearchBrief, now: datetime
) -> str:
    """Classify a candidate as fresh, stale, or unknown against the brief's freshness policy.

    Only ``stale`` is a fact that justifies dropping a page before spending a fetch on it.
    ``unknown`` means no publication date was found anywhere; such pages stay in the
    pipeline and receive a freshness *score* penalty later instead of a rejection.
    """
    if brief.freshness_mode == FreshnessMode.EVERGREEN:
        return FRESH
    if candidate.published_at is None:
        return UNKNOWN_FRESHNESS

    published = _as_utc(candidate.published_at)
    current = _as_utc(now)

    # A publication time slightly in the future is a timezone artefact, not a stale page.
    if published > current:
        return FRESH if published - current <= timedelta(hours=24) else STALE

    window = _required_freshness_window(brief)
    if window is None:
        raise ValueError("a time-sensitive brief needs a freshness window")
    return FRESH if current - published <= timedelta(days=window) else STALE


def is_fresh_enough(
    candidate: CandidatePage, brief: ResearchBrief, now: datetime
) -> bool:
    """Strict boolean view: only a page with a known in-window date counts as fresh."""
    return freshness_status(candidate, brief, now) == FRESH


def _date_freshness_score(
    published_at: datetime, now: datetime, window_days: int
) -> float:
    """Map page age inside the window to 10 (very recent) .. 5 (at the window edge) .. 0."""
    age_days = max(0.0, (_as_utc(now) - _as_utc(published_at)).total_seconds() / 86_400)
    if age_days <= window_days * 0.25:
        return 10.0
    if age_days <= window_days:
        # Linear decay from 10 at a quarter of the window to 5 at the edge.
        fraction = (age_days - window_days * 0.25) / (window_days * 0.75)
        return round(10.0 - 5.0 * fraction, 6)
    # Beyond the window (only reachable for pages whose date surfaced after search):
    # decay to 0 at twice the window.
    overshoot = min(1.0, (age_days - window_days) / window_days)
    return round(5.0 * (1.0 - overshoot), 6)


def freshness_component(
    evaluator_freshness: float,
    candidate: CandidatePage,
    brief: ResearchBrief,
    now: datetime,
    config: Config,
) -> tuple[float, bool]:
    """Combine the evaluator's content-based freshness with the page date, if one exists.

    Returns ``(score, freshness_known)``. For evergreen briefs the date barely matters, so
    the evaluator's judgement is used as-is. For time-sensitive briefs a known date is the
    stronger signal and dominates the blend; an unknown date is penalised multiplicatively
    rather than treated as fatal.
    """
    evaluator_freshness = max(0.0, min(10.0, float(evaluator_freshness)))
    if brief.freshness_mode == FreshnessMode.EVERGREEN:
        return evaluator_freshness, candidate.published_at is not None
    if candidate.published_at is None:
        return round(
            evaluator_freshness * config.undated_freshness_multiplier, 6
        ), False
    window = _required_freshness_window(brief)
    if window is None:
        raise ValueError("a time-sensitive brief needs a freshness window")

    date_score = _date_freshness_score(candidate.published_at, now, window)
    weight = config.date_freshness_weight
    blended = weight * date_score + (1.0 - weight) * evaluator_freshness
    return round(max(0.0, min(10.0, blended)), 6), True


def _published_at_from_url(url: str) -> datetime | None:
    """Infer a publication date encoded in the URL path when the provider gives none.

    Accepts only complete calendar dates: ``/2026/09/03/`` style paths and compact
    ``20260903`` runs (optionally followed by a six-digit time, as many news CMSs emit).
    Year/month-only paths stay undated because the day is genuinely unknown.
    """
    try:
        path = urlsplit(url).path
    except (TypeError, ValueError):
        return None
    match = re.search(
        r"(?:^|/)(20\d{2})(?:/|-)(0?[1-9]|1[0-2])(?:/|-)(0?[1-9]|[12]\d|3[01])(?:/|$)",
        path,
    )
    if match is None:
        match = re.search(
            r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\d{6})?(?!\d)",
            path,
        )
    if match is None:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()), tzinfo=UTC)
    except ValueError:
        return None


def extract_media_urls(content: str) -> list[str]:
    """Extract image URLs from markdown content."""
    media_urls = []
    for match in _MARKDOWN_IMAGE.finditer(content):
        url = match.group(2).strip()
        if url and (url.startswith("http://") or url.startswith("https://")):
            media_urls.append(url)
    return list(dict.fromkeys(media_urls))  # Remove duplicates while preserving order


def _is_link_only_line(line: str) -> bool:
    """True for a line whose only visible content is links or images (menus, story cards)."""
    if not (_MARKDOWN_LINK.search(line) or _EMPTY_LINK.search(line)):
        return False
    visible = _EMPTY_LINK.sub("", line)
    visible = _MARKDOWN_LINK.sub("", visible)
    visible = _BARE_URL.sub("", visible).strip()
    visible = _LIST_MARKER.sub("", visible)
    visible = _CHECKBOX.sub("", visible)
    visible = _LIST_MARKER.sub("", visible)
    visible = _CHECKBOX.sub("", visible)
    return not re.search(r"\w", visible)


def _is_standalone_boilerplate(body: str) -> bool:
    """True for a short, whole-line piece of site chrome left behind after link stripping."""
    compact = body.strip(" *_|-")
    if not compact:
        return False
    if re.match(r"^image \d+\b", compact, re.IGNORECASE):
        return True
    if len(compact.split()) > 14:
        return False
    return bool(
        _STANDALONE_BOILERPLATE.fullmatch(compact) or _GLUED_BYLINE.fullmatch(compact)
    )


def _appeal_marker_count(block: str) -> int:
    return sum(bool(pattern.search(block)) for pattern in _APPEAL_MARKERS)


def _split_heading_blocks(blocks: list[str]) -> list[str]:
    """Give every heading its own block so a heading glued to its paragraph is not a bare heading."""
    expanded: list[str] = []
    for block in blocks:
        lines = block.split("\n")
        if lines[0].startswith("#") and len(lines) > 1:
            expanded.append(lines[0])
            expanded.append("\n".join(lines[1:]).strip("\n"))
        else:
            expanded.append(block)
    return [block for block in expanded if block]


def _drop_furniture_sections(blocks: list[str]) -> list[str]:
    """Remove headings with no body and sections that are mostly reader appeals."""
    blocks = _split_heading_blocks(blocks)
    kept: list[str] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if not block.startswith("#"):
            kept.append(block)
            index += 1
            continue
        end = index + 1
        while end < len(blocks) and not blocks[end].startswith("#"):
            end += 1
        body = blocks[index + 1 : end]
        if not body:
            index = end
            continue
        counts = [_appeal_marker_count(paragraph) for paragraph in body]
        pleas = sum(count >= 2 for count in counts)
        hints = sum(count == 1 for count in counts)
        # Fundraising blocks mix hard pleas with filler prose; weight the filler at half.
        if pleas >= 2 and (pleas + 0.5 * hints) / len(body) >= 0.3:
            index = end
            continue
        kept.append(block)
        kept.extend(body)
        index = end
    # A leading run of appeal paragraphs before any heading is site furniture too.
    while kept and not kept[0].startswith("#") and _appeal_marker_count(kept[0]) >= 2:
        kept.pop(0)
    return kept


def clean_article_content(text: str) -> str:
    """Remove extraction boilerplate and URL noise without rewriting article prose.

    Line pass: strip reader metadata, navigation rows, link-only menu and card lines,
    whole-line site chrome, image placeholders and glued bylines; skip entire sections
    under furniture headings such as "Most viewed" or "More from". Block pass: drop
    headings left with no body and sections that are mostly subscription appeals.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and _JINA_HEADER.match(lines[0].strip()):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)

    cleaned_lines: list[str] = []
    blank_pending = False
    skipping_below_level: int | None = None
    for line in lines:
        stripped = line.strip()
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading is not None:
            level = len(heading.group(1))
            if skipping_below_level is not None and level > skipping_below_level:
                continue
            skipping_below_level = None
            title = _MARKDOWN_LINK.sub(
                lambda match: match.group(1), heading.group(2)
            ).strip(" #*_")
            if _NOISE_HEADING.match(title):
                skipping_below_level = level
                continue
        elif skipping_below_level is not None and stripped:
            continue
        if _is_navigation_or_footer_line(line) or _is_link_only_line(line):
            continue
        line = _EMPTY_LINK.sub("", line)
        line = _MARKDOWN_LINK.sub(lambda match: match.group(1), line)
        line = _BARE_URL.sub("", line)
        indentation = line[: len(line) - len(line.lstrip(" \t"))]
        body = _SPACE.sub(" ", line[len(indentation) :]).strip()
        marker = _LIST_MARKER.match(body)
        if marker is not None:
            item = _JINA_LIST_PREFIX.sub("", body[marker.end() :]).strip()
            if not item or _is_standalone_boilerplate(item):
                continue
            line = f"{indentation}{marker.group()}{item}"
        else:
            if _is_standalone_boilerplate(body):
                continue
            line = body
        if not line:
            blank_pending = bool(cleaned_lines)
            continue
        if blank_pending:
            cleaned_lines.append("")
            blank_pending = False
        cleaned_lines.append(line)

    blocks = [
        block.strip("\n")
        for block in re.split(r"\n\s*\n", "\n".join(cleaned_lines))
        if block.strip()
    ]
    blocks = _drop_furniture_sections(blocks)
    return "\n\n".join(blocks).strip()


def _looks_like_listing_body(document: ExtractedDocument, cleaned: str) -> bool:
    """check actual extracted content to determine whether it resembles a listing page."""
    raw_links = len(
        re.findall(
            r"(?:!?\[[^\]]+\]\([^)]*\)|https?://)", document.content, re.IGNORECASE
        )
    )
    blocks = [block.strip() for block in re.split(r"\n\s*\n", cleaned) if block.strip()]
    short_blocks = [block for block in blocks if len(block) <= 280]
    link_dense = raw_links >= 8 and raw_links / max(len(blocks), 1) >= 0.4
    normalized_blocks = [_normalized_text(block) for block in short_blocks]
    repeated = any(count >= 3 for count in Counter(normalized_blocks).values())
    card_calls_to_action = sum(
        bool(_CARD_CALL_TO_ACTION.fullmatch(match.group(1).strip()))
        for match in _MARKDOWN_LINK.finditer(document.content)
    )
    return link_dense and (repeated or card_calls_to_action >= 3)


def _is_navigation_or_footer_line(line: str) -> bool:
    """Recognize only standalone navigation and legal-footer rows, not article prose."""
    compact = _SPACE.sub(" ", line).strip()
    if not compact:
        return False
    if _FOOTER_BOILERPLATE.search(compact):
        return True

    link_labels = [
        match.group(1).strip().casefold() for match in _MARKDOWN_LINK.finditer(compact)
    ]
    if (
        len(link_labels) >= 3
        and sum(label in _NAVIGATION_LABELS for label in link_labels) >= 3
    ):
        return True

    visible = _MARKDOWN_LINK.sub(lambda match: match.group(1), compact)
    visible = _BARE_URL.sub("", visible)
    labels = [part.strip().casefold() for part in visible.split("|") if part.strip()]
    return (
        len(labels) >= 3 and sum(label in _NAVIGATION_LABELS for label in labels) >= 3
    )


def _navigation_or_footer_ratio(document: ExtractedDocument, cleaned: str) -> float:
    boilerplate_characters = sum(
        len(line.strip())
        for line in document.content.replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
        if _is_navigation_or_footer_line(line)
    )
    return boilerplate_characters / max(len(cleaned), 1)


def _link_to_visible_text_ratio(document: ExtractedDocument, cleaned: str) -> float:
    link_characters = sum(
        len(match.group(1).strip())
        for match in _MARKDOWN_LINK_DESTINATION.finditer(document.content)
    )
    without_markdown_links = _MARKDOWN_LINK.sub("", document.content)
    link_characters += sum(
        len(match.group(0)) for match in _BARE_URL.finditer(without_markdown_links)
    )
    return link_characters / max(len(cleaned), 1)


def article_rejection_reason(
    document: ExtractedDocument, cleaned: str, config: Config
) -> str | None:
    """Return a post-extraction rejection code only for content the composer could never use.

    Length bounds and paywall/bot interstitials are hard failures. Structural weaknesses
    (link density, navigation chrome, listing shape, repetition) are *scored* by
    :func:`structural_quality` instead so a slightly noisy but substantive page still ranks.
    """
    size = len(cleaned)
    if size < config.minimum_article_chars:
        return "too_short"
    if size > config.max_clean_content_chars:
        return "too_long"
    if _PAYWALL_OR_BOT.search(cleaned):
        return "error_or_paywall"
    return None


def _ratio_penalty(ratio: float, maximum: float, floor: float) -> float:
    """1.0 while inside the limit; decays linearly to ``floor`` at twice the limit."""
    if maximum <= 0.0:
        return 1.0 if ratio <= 0.0 else floor
    if ratio <= maximum:
        return 1.0
    excess = min(1.0, (ratio - maximum) / maximum)
    return round(max(floor, 1.0 - (1.0 - floor) * excess), 6)


def structural_quality(
    document: ExtractedDocument, cleaned: str, config: Config
) -> tuple[float, tuple[str, ...]]:
    """Score page structure as a multiplier in [floor, 1] plus the flags that lowered it.

    The same heuristics that used to reject pages outright now degrade the
    ``information_density`` component proportionally to how far each ratio exceeds its
    configured limit. Flags are returned for diagnostics so a run log still explains
    *why* a page ranked lower.
    """
    floor = config.structural_penalty_floor
    multiplier = 1.0
    flags: list[str] = []

    navigation_ratio = _navigation_or_footer_ratio(document, cleaned)
    penalty = _ratio_penalty(
        navigation_ratio, config.maximum_navigation_footer_ratio, floor
    )
    if penalty < 1.0:
        flags.append("navigation_or_footer_heavy")
        multiplier *= penalty

    if _looks_like_listing_body(document, cleaned):
        flags.append("listing_body")
        multiplier *= config.listing_body_penalty

    link_ratio = _link_to_visible_text_ratio(document, cleaned)
    penalty = _ratio_penalty(
        link_ratio, config.maximum_link_to_visible_text_ratio, floor
    )
    if penalty < 1.0:
        flags.append("link_dominated")
        multiplier *= penalty

    density = _information_density(cleaned)
    minimum = config.minimum_structural_information_density
    if minimum > 0.0 and density < minimum:
        flags.append("low_information_density")
        multiplier *= max(floor, density / minimum)

    return round(max(floor, min(1.0, multiplier)), 6), tuple(flags)


def _content_clearly_mismatches_language(content: str, expected_language: str) -> bool:
    """Conservatively identify a dominant script incompatible with the requested language."""
    language_code = expected_language.casefold().split("-", 1)[0]
    expected_scripts = _EXPECTED_SCRIPTS_BY_LANGUAGE.get(language_code)
    if expected_scripts is not None:
        script_counts = {
            name: len(pattern.findall(content))
            for name, pattern in _SCRIPT_PATTERNS.items()
        }
        incompatible_characters = sum(
            count
            for name, count in script_counts.items()
            if name not in expected_scripts
        )
        script_characters = sum(script_counts.values())
        alphabetic = sum(character.isalpha() for character in content)
        if (
            incompatible_characters >= 48
            and incompatible_characters / max(alphabetic, script_characters, 1) >= 0.70
        ):
            return True

    if language_code != "en":
        return False

    tokens = re.findall(r"\b[^\W\d_]{2,}\b", content.casefold())
    if len(tokens) < 40:
        return False
    english_hits = sum(token in _ENGLISH_COMMON_WORDS for token in tokens)
    return any(
        (hits := sum(token in stopwords for token in tokens))
        >= max(8, int(len(tokens) * 0.12))
        and hits >= english_hits + 4
        for stopwords in _CLEAR_NON_ENGLISH_STOPWORDS
    )


def _extraction_error_reason(error: Exception) -> str:
    """Preserve only stable codes defined by the provider extraction hierarchy."""
    # This import remains local because providers imports this module's pure helpers.
    from app.agents.research_agents.providers import ExtractionError

    if (
        isinstance(error, ExtractionError)
        and isinstance(error.code, str)
        and error.code
    ):
        return error.code
    return "extraction_error"


def _content_identity(cleaned: str) -> str:
    """Return the normalized full-body identity used across all extraction passes."""
    normalized = re.sub(r"\s+", " ", cleaned).casefold()
    # sha256 to create content fingerprint
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _append_with_limit(parts: list[str], candidate: str, limit: int) -> None:
    if not candidate or sum(len(part) for part in parts) + (2 * len(parts)) >= limit:
        return
    remaining = limit - sum(len(part) for part in parts) - (2 * len(parts))
    if remaining <= 0:
        return
    parts.append(candidate[:remaining].rstrip())


def build_ranking_view(content: str, brief: ResearchBrief, limit: int) -> str:
    """Create a bounded evaluator view while retaining the complete stored content."""
    if limit <= 0:
        return ""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    if not blocks:
        return ""

    introduction_index = next(
        (index for index, block in enumerate(blocks) if not block.startswith("#")), 0
    )
    parts: list[str] = []
    _append_with_limit(parts, blocks[introduction_index], limit)
    terms = {
        term.lower()
        for phrase in (*brief.main_keywords, *brief.required_angles, brief.topic)
        for term in re.findall(r"\w+", phrase.lower())
        if len(term) >= 3
    }
    consumed = {introduction_index}
    if introduction_index and blocks[introduction_index - 1].startswith("#"):
        consumed.add(introduction_index - 1)
    for index, block in enumerate(blocks):
        if index in consumed:
            continue
        section = block
        if (
            block.startswith("#")
            and index + 1 < len(blocks)
            and not blocks[index + 1].startswith("#")
        ):
            section = f"{block}\n\n{blocks[index + 1]}"
            consumed.add(index + 1)
        words = set(re.findall(r"\w+", section.lower()))
        if terms & words:
            _append_with_limit(parts, section, limit)
    return "\n\n".join(parts)[:limit].rstrip()


def _score_value(page: EvaluatedPage) -> float:
    if page.scores is None or page.scores.composite is None:
        return -1.0
    return page.scores.composite


def _page_domain(page: EvaluatedPage) -> str:
    """Use the fetch URL's registrable domain, never the shared search provider."""
    return (
        publisher_domain(page.candidate.url)
        or page.candidate.publisher_domain.casefold()
    )


def _normalized_angles(angles: tuple[str, ...] | list[str]) -> set[str]:
    return {angle.casefold().strip() for angle in angles if angle.strip()}


def select_for_coverage(
    pages: list[EvaluatedPage],
    required_angles: list[str] | tuple[str, ...],
    target_pages: int,
    max_pages: int,
    max_per_domain: int,
    config: Config = CONFIG,
) -> list[EvaluatedPage]:
    """Select a deterministic, publisher-diverse set with marginal coverage gain."""
    cap = min(5, max(0, max_pages))
    target = min(max(0, target_pages), cap)
    if cap == 0 or target == 0 or max_per_domain <= 0:
        return []

    eligible = [
        page
        for page in pages
        if page.accepted
        and page.scores is not None
        and page.scores.composite is not None
    ]
    if not eligible:
        return []
    eligible.sort(
        key=lambda page: (
            -_score_value(page),
            page.candidate.canonical_url,
            page.candidate.id,
        )
    )

    selected: list[EvaluatedPage] = []
    domain_counts: Counter[str] = Counter()
    covered: set[str] = set()
    required = _normalized_angles(required_angles)

    def allowed(page: EvaluatedPage) -> bool:
        return domain_counts[_page_domain(page)] < max_per_domain

    def choose_best(candidates: list[EvaluatedPage]) -> EvaluatedPage | None:
        available = [
            page for page in candidates if page not in selected and allowed(page)
        ]
        if not available:
            return None

        def utility(page: EvaluatedPage) -> tuple[float, float, str, str]:
            marginal_required = len(
                (_normalized_angles(page.covered_angles) & required) - covered
            )
            joint_score = _score_value(page) + min(2.5, 1.5 * marginal_required)
            return (
                -joint_score,
                -_score_value(page),
                page.candidate.canonical_url,
                page.candidate.id,
            )

        return min(available, key=utility)

    strongest = next((page for page in eligible if allowed(page)), None)
    if strongest is not None:
        selected.append(strongest)
        domain_counts[_page_domain(strongest)] += 1
        covered.update(_normalized_angles(strongest.covered_angles))

    while len(selected) < target:
        chosen = choose_best(eligible)
        if chosen is None:
            break
        selected.append(chosen)
        domain_counts[_page_domain(chosen)] += 1
        covered.update(_normalized_angles(chosen.covered_angles))

    if len(selected) >= target and len(selected) < cap:
        selected_dates = [
            _as_utc(page.candidate.published_at)
            for page in selected
            if page.candidate.published_at is not None
        ]

        def qualifies_as_fourth(page: EvaluatedPage) -> bool:
            fourth_angles = _normalized_angles(page.covered_angles)
            adds_missing_required = bool((fourth_angles & required) - covered)
            materially_newer = bool(
                page.candidate.published_at is not None
                and selected_dates
                and _as_utc(page.candidate.published_at)
                >= max(selected_dates) + timedelta(days=7)
            )
            scores = page.scores
            credible_distinct_perspective = bool(
                fourth_angles - covered
                and scores is not None
                and (scores.authority or 0.0)
                >= config.minimum_distinct_fourth_authority_score
                and (scores.content_quality or 0.0)
                >= config.minimum_distinct_fourth_content_quality_score
                and (scores.composite or 0.0)
                >= config.minimum_distinct_fourth_composite_score
            )
            return (
                adds_missing_required
                or materially_newer
                or credible_distinct_perspective
            )

        fourth = choose_best([page for page in eligible if qualifies_as_fourth(page)])
        if fourth is not None:
            selected.append(fourth)

    return selected


def _information_density(content: str) -> float:
    words = re.findall(r"\b[\w'-]+\b", content.casefold())
    if not words:
        return 0.0
    substantive = [word for word in words if len(word) >= 4]
    lexical_variety = len(set(substantive)) / max(len(substantive), 1)
    length_score = min(3.0, len(content) / 2_000 * 3.0)
    variety_score = min(3.0, lexical_variety * 6.0)
    four_grams = tuple(zip(words, words[1:], words[2:], words[3:]))
    phrase_variety = len(set(four_grams)) / max(len(four_grams), 1)
    repetition_adjustment = 0.5 + 0.5 * min(1.0, phrase_variety / 0.25)
    return round(
        min(10.0, (4.0 + length_score + variety_score) * repetition_adjustment), 6
    )


def _novelty_score(
    candidate: CandidatePage, covered_angles: tuple[str, ...], brief: ResearchBrief
) -> float:
    required = _normalized_angles(brief.required_angles)
    covered = _normalized_angles(covered_angles)
    if required:
        angle_component = 8.0 * len(required & covered) / len(required)
    else:
        angle_component = 4.0 if covered else 0.0
    provenance_component = min(2.0, float(len(set(candidate.discovered_by))))
    return round(min(10.0, angle_component + provenance_component), 6)


def _composite_score(scores: PageScores, config: Config, mode: FreshnessMode) -> float:
    weights = (
        config.evergreen_score_weights
        if mode == FreshnessMode.EVERGREEN
        else config.time_sensitive_score_weights
    )
    total = sum(
        float(getattr(scores, field_name) or 0.0) * weight
        for field_name, weight in zip(_SCORE_COMPONENTS, weights, strict=True)
    )
    # Relevance is the gatekeeper of the ranking: cap the composite relative to it so a
    # fresh, authoritative page about the wrong subject cannot outrank the right one.
    total = min(total, float(scores.relevance) + config.relevance_cap_margin)
    return round(max(0.0, min(10.0, total)), 6)


def _extraction_quality(document: ExtractedDocument, content: str) -> float:
    score = 0.55 + min(0.35, len(content) / 10_000)
    if document.article_type and document.article_type.casefold() in {
        "article",
        "newsarticle",
        "report",
    }:
        score += 0.10
    return round(min(1.0, score), 6)
