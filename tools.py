import os
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from tavily import TavilyClient

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$|[?#])")
# A whole path segment that starts with YYYY-MM-DD, e.g. bloomberg.com/news/articles/2026-10-16/...
_URL_ISO_SEGMENT_RE = re.compile(r"/(\d{4})-(\d{2})-(\d{2})(?=[/?#]|$|-)")
ISO_DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?!\d)")
_MDY_RE = re.compile(
    r"\b(" + "|".join(_MONTHS.keys()) + r")\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)
_DMY_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS.keys()) + r")\.?\s+(\d{4})\b",
    re.IGNORECASE,
)
_PUBLISHED_LABEL_RE = re.compile(
    r"\b(?:published(?: on)?|posted(?: on)?|publication date|date published)\b\s*:?",
    re.IGNORECASE,
)
# Separators allowed between a publication label and its date: whitespace, colon,
# Markdown emphasis/table marks and dashes. Anything else (author names, "Updated")
# breaks the association.
_LABEL_GAP_RE = re.compile(r"[\s:*_|\-\u2013\u2014]*")


def _format_date(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _date_from_url(url: str) -> str | None:
    m = _URL_DATE_RE.search(url or "") or _URL_ISO_SEGMENT_RE.search(url or "")
    if not m:
        return None
    return _format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _date_from_content(content: str) -> str | None:
    # Only trust a content date that immediately follows an explicit publication label
    # ("Published", "Posted", ...), separated by nothing but punctuation. Bare dates in
    # navigation, sidebars or "Updated" lines are ignored, as is "Published by <author>"
    # followed by another field; in those cases we return None so the caller reports
    # "unknown" and the verifier looks for a better-dated source.
    window = (content or "")[:15000]
    if not window:
        return None
    for label in _PUBLISHED_LABEL_RE.finditer(window):
        start = _LABEL_GAP_RE.match(window, label.end()).end()
        d = _date_at_start(window[start:start + 40])
        if d:
            return d
    return None


def _date_at_start(text: str) -> str | None:
    """Return the date that begins exactly at the start of `text`, if any."""
    text = text.replace("_", " ")  # Markdown italics would defeat the trailing \b of the date regexes
    candidates = []
    for m in _ISO_DATE_RE.finditer(text):
        d = _format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            candidates.append((m.start(), d))
    for m in _MDY_RE.finditer(text):
        d = _format_date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            candidates.append((m.start(), d))
    for m in _DMY_RE.finditer(text):
        d = _format_date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            candidates.append((m.start(), d))
    return next((d for pos, d in candidates if pos == 0), None)


def _normalize_date(value) -> str | None:
    """Normalize Tavily's ISO or RFC 2822 (news topic) dates to a UTC YYYY-MM-DD."""
    if not value:
        return None
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            m = _ISO_DATE_RE.match(value)
            return _format_date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _resolve_published_date(tavily_field, url: str, raw_content: str) -> str:
    """Layered date resolution: Tavily field → URL path → content scan → 'unknown'."""
    d = _normalize_date(tavily_field)
    if d:
        return d
    d = _date_from_url(url)
    if d:
        return d
    d = _date_from_content(raw_content)
    if d:
        return d
    return "unknown"


def allowed_dates(today_date: str) -> tuple[str, str]:
    """Return (yesterday, today): the freshness window of two UTC calendar days."""
    today = datetime.strptime(today_date, "%Y-%m-%d")
    return (today - timedelta(days=1)).strftime("%Y-%m-%d"), today_date


TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current information on a topic. "
            "Returns a summary of relevant results from multiple sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "extract_url",
        "description": (
            "Fetch the full content of a specific article URL using Tavily extract. "
            "Use this to verify a URL is a real article and check its publication date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the article to extract"
                }
            },
            "required": ["url"]
        }
    }
]


# Every URL a tool actually returned during this run. A source URL in the final summary
# that is not in this set was never seen by the agents, i.e. it was made up.
SEEN_URLS: set[str] = set()
# Best known published date per URL (normalized), from any tool result that had one.
# extract_url often has no date for a page that web_search already dated.
URL_DATES: dict[str, str] = {}


def _remember(url: str, date: str) -> None:
    key = normalize_url(url)
    SEEN_URLS.add(key)
    if date != "unknown":
        URL_DATES.setdefault(key, date)


def normalize_url(url: str) -> str:
    """Compare URLs loosely: ignore scheme, a leading 'www.', host case and a trailing slash."""
    # Scheme and host are case-insensitive; path and query are not (RFC 3986 6.2.2.1).
    m = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]*)(.*)$", url.strip(), re.IGNORECASE)
    return (m.group(1).lower() + m.group(2)).rstrip("/")


# Token usage per agent for this run, e.g. {"writer": {"input": 1200, "output": 300, ...}}.
USAGE: dict[str, dict[str, int]] = {}


def record_usage(agent: str, response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    totals = USAGE.setdefault(agent, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
    totals["input"] += getattr(usage, "input_tokens", 0) or 0
    totals["output"] += getattr(usage, "output_tokens", 0) or 0
    totals["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    totals["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0


def usage_report() -> str:
    """One line per agent; cost uses Sonnet 4.6 list prices ($3 / $15 per million tokens)."""
    lines = []
    for agent, t in USAGE.items():
        cost = (t["input"] * 3 + t["output"] * 15 + t["cache_read"] * 0.3 + t["cache_write"] * 3.75) / 1_000_000
        lines.append(f"Token usage [{agent}]: input {t['input']}, output {t['output']}, "
                     f"cache read {t['cache_read']}, cache write {t['cache_write']} (~US${cost:.2f})")
    return "\n".join(lines)


def log_tool_call(agent: str, name: str, input: dict, result: str) -> None:
    """One line per tool call in the run log, so we can see what each agent actually did."""
    arg = input.get("query") or input.get("url") or ""
    status = "ERROR" if result.startswith("Error") else "ok"
    print(f"  [{agent}] {name} {status}: {arg[:100]}")


def execute_tool(name: str, input: dict) -> str:
    if name == "web_search":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.search(query=input["query"], search_depth="basic", topic="news", days=2)
            parts = []
            for item in result.get("results", []):
                title = item.get("title", "No title")
                content = item.get("content", "") or ""
                url = item.get("url", "")
                date = _resolve_published_date(item.get("published_date"), url, content)
                if url:
                    _remember(url, date)
                parts.append(f"**{title}**\n{content}\nPublished: {date}\nURL: {url}")
            return "\n\n".join(parts) if parts else "No results found."
        except Exception as e:
            return f"Error: {e}"
    if name == "extract_url":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.extract(urls=[input["url"]])
            results = result.get("results", [])
            if not results:
                return "Error: No content extracted"
            item = results[0]
            title = item.get("title", "No title")
            raw_content = item.get("raw_content", "") or ""
            content = raw_content[:1000]
            url = item.get("url", input["url"])
            date = _resolve_published_date(item.get("published_date"), url, raw_content)
            _remember(url, date)
            _remember(input["url"], date)
            return f"**{title}**\n{content}\nPublished: {date}\nURL: {url}"
        except Exception as e:
            return f"Error: {e}"
    return f"Error: Unknown tool '{name}'"
