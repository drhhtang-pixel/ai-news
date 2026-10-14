import os
import re
from datetime import datetime
from tavily import TavilyClient

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$|[?#])")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?!\d)")
_MDY_RE = re.compile(
    r"\b(" + "|".join(_MONTHS.keys()) + r")\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)
_DMY_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS.keys()) + r")\.?\s+(\d{4})\b",
    re.IGNORECASE,
)


def _format_date(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _date_from_url(url: str) -> str | None:
    m = _URL_DATE_RE.search(url or "")
    if not m:
        return None
    return _format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _date_from_content(content: str) -> str | None:
    # Tavily extract strips raw HTML to ~20-30k chars of markdown-ish text; the article
    # byline/date often sits 3k-13k chars in, past navigation menus and share buttons.
    # Scan a wide window and return the EARLIEST date — first match is almost always
    # the publication date; later matches tend to be sidebar links or in-body references.
    window = (content or "")[:15000]
    if not window:
        return None
    candidates = []
    for m in _ISO_DATE_RE.finditer(window):
        d = _format_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            candidates.append((m.start(), d))
    for m in _MDY_RE.finditer(window):
        d = _format_date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            candidates.append((m.start(), d))
    for m in _DMY_RE.finditer(window):
        d = _format_date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            candidates.append((m.start(), d))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def _resolve_published_date(tavily_field, url: str, raw_content: str) -> str:
    """Layered date resolution: Tavily field → URL path → content scan → 'unknown'."""
    if tavily_field:
        return tavily_field
    d = _date_from_url(url)
    if d:
        return d
    d = _date_from_content(raw_content)
    if d:
        return d
    return "unknown"


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


def execute_tool(name: str, input: dict) -> str:
    if name == "web_search":
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            result = client.search(query=input["query"], search_depth="basic", days=1)
            parts = []
            for item in result.get("results", []):
                title = item.get("title", "No title")
                content = item.get("content", "")
                url = item.get("url", "")
                parts.append(f"**{title}**\n{content}\nURL: {url}")
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
            return f"**{title}**\n{content}\nPublished: {date}\nURL: {url}"
        except Exception as e:
            return f"Error: {e}"
    return f"Error: Unknown tool '{name}'"
