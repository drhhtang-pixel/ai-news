"""What the monitor already knows, which stories are too old to publish without review, and how
the verifier's per-headline decisions are applied to a summary.

"New" means new to this monitor, not new in time: a story that has not been published
before may be reported even if it happened weeks ago. Stories whose earliest dated source
is older than MAX_STORY_AGE_DAYS are held back for the manager instead of published.
"""
import re
from datetime import datetime, timedelta

EN_MARKER = "<!-- EN -->"
ZH_MARKER = "<!-- ZH -->"
EN_HEADLINES = "### Headlines"
ZH_HEADLINES = "### 頭條新聞"
EN_SOURCES = "### Sources"
ZH_SOURCES = "### 來源"

KNOWN_HISTORY_DAYS = 45
MAX_STORY_AGE_DAYS = 30

_ENTRY_HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})", re.MULTILINE)
_TITLE_RE = re.compile(r"^- \*\*(.+?)\*\*")
_CITATION_RE = re.compile(r"\*\((?:Sources?|來源)\s*[:：]\s*(.*?)\)\*\s*$")
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_SOURCE_ENTRY_RE = re.compile(r"^- (.+?):\s*(https?://\S+)")


def known_headlines(path: str, today_date: str, days: int = KNOWN_HISTORY_DAYS) -> list[str]:
    """EN headline titles published in the last `days` days, newest first."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return []
    cutoff = _parse_date(today_date) - timedelta(days=days)
    headers = list(_ENTRY_HEADER_RE.finditer(text))
    titles: list[str] = []
    for i, header in enumerate(headers):
        if _parse_date(header.group(1)) < cutoff:
            continue
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        entry = text[header.end():end]
        en = entry.split(ZH_MARKER)[0]
        titles.extend(_TITLE_RE.match(line).group(1).rstrip(":：")
                      for line in _section_lines(en, EN_HEADLINES) if _TITLE_RE.match(line))
    titles.reverse()
    return titles


def hold_old_stories(summary: str, today_date: str,
                     max_age_days: int = MAX_STORY_AGE_DAYS) -> tuple[str, list[dict]]:
    """Remove headlines whose earliest dated source is older than `max_age_days`.

    Returns the remaining summary and the held stories. A headline with no dated source
    is kept. The matching ZH headline (same position) and Sources entries cited only by
    held headlines are removed too.
    """
    if EN_MARKER not in summary or ZH_MARKER not in summary:
        return summary, []
    cutoff = _parse_date(today_date) - timedelta(days=max_age_days)
    lines = summary.splitlines()
    zh_start = next(i for i, line in enumerate(lines) if line.strip() == ZH_MARKER)

    en_items = [i for i in _section_indexes(lines, 0, zh_start, EN_HEADLINES) if lines[i].lstrip().startswith("- **")]
    zh_items = [i for i in _section_indexes(lines, zh_start, len(lines), ZH_HEADLINES)
                if lines[i].lstrip().startswith("- **")]
    source_urls = _source_urls(lines, 0, zh_start)

    held: list[dict] = []
    drop: set[int] = set()
    kept_names: set[str] = set()
    held_names: set[str] = set()
    for pos, idx in enumerate(en_items):
        sources = _citation_sources(lines[idx])
        dates = [d for _, d in sources if d]
        earliest = min(dates) if dates else None
        if earliest and _parse_date(earliest) < cutoff:
            drop.add(idx)
            if pos < len(zh_items):
                drop.add(zh_items[pos])
            held_names.update(name for name, _ in sources)
            held.append({
                "title": _TITLE_RE.match(lines[idx].lstrip()).group(1).rstrip(":："),
                "headline": lines[idx].strip(),
                "earliest": earliest,
                "sources": [(name, date, _lookup(source_urls, name)) for name, date in sources],
            })
        else:
            kept_names.update(name for name, _ in sources)

    if not held:
        return summary, []

    # Match Sources entries by URL: ZH entries often use translated publication names.
    held_urls = {url for name, url in source_urls.items()
                 if _matches(name, held_names) and not _matches(name, kept_names)}
    for start, end, heading in ((0, zh_start, EN_SOURCES), (zh_start, len(lines), ZH_SOURCES)):
        for i in _section_indexes(lines, start, end, heading):
            m = _SOURCE_ENTRY_RE.match(lines[i].strip())
            if m and m.group(2) in held_urls:
                drop.add(i)

    kept = [line for i, line in enumerate(lines) if i not in drop]
    return _collapse_blank_lines("\n".join(kept)), held


def known_stories_prompt(known: list[str] | None) -> str:
    """The 'already published' list shared by the writer and the verifier."""
    listed = "\n".join(f"- {title}" for title in known) if known else "(none)"
    return (
        "\n\nALREADY PUBLISHED by this monitor (do NOT report these stories again, even from new "
        f"sources or with new wording):\n{listed}"
    )


MAX_SOURCES_PER_HEADLINE = 3


def apply_verification(summary: str, decisions: list[dict]) -> str:
    """Apply the verifier's per-headline decisions to the summary.

    Each decision is {"index": 1-based EN headline position, "action": "keep"|"remove",
    "sources": [{"name", "url", "date"}]}. Kept headlines get their EN and ZH citations
    rebuilt from the decision's sources; removed ones (or ones left with no source) are
    dropped in both languages. Headlines without a decision are left unchanged. Both
    Sources sections are rebuilt from the citations that remain. Analysis is untouched.
    """
    if EN_MARKER not in summary or ZH_MARKER not in summary:
        return summary
    lines = summary.splitlines()
    zh_start = next(i for i, line in enumerate(lines) if line.strip() == ZH_MARKER)
    en_items = [i for i in _section_indexes(lines, 0, zh_start, EN_HEADLINES) if lines[i].lstrip().startswith("- **")]
    zh_items = [i for i in _section_indexes(lines, zh_start, len(lines), ZH_HEADLINES)
                if lines[i].lstrip().startswith("- **")]
    original = _source_entries(lines, 0, zh_start)
    by_index = {d.get("index"): d for d in decisions if isinstance(d, dict)}

    drop: set[int] = set()
    entries: dict[str, tuple[str, str | None]] = {}  # url -> (name, date), in citation order
    for pos, idx in enumerate(en_items):
        zh_idx = zh_items[pos] if pos < len(zh_items) else None
        decision = by_index.get(pos + 1)
        if decision is None:
            for name, date in _citation_sources(lines[idx]):
                # Same-named publications can appear twice; prefer the entry with the cited date.
                candidates = [(u, d) for n, u, d in original if _matches(n, {name})]
                url = next((u for u, d in candidates if d == date), candidates[0][0] if candidates else None)
                if url:
                    entries.setdefault(url, (name, date))
            continue
        sources = [_clean_source(src) for src in decision.get("sources") or []]
        sources = [src for src in sources if src][:MAX_SOURCES_PER_HEADLINE]
        if decision.get("action") != "keep" or not sources:
            drop.add(idx)
            if zh_idx is not None:
                drop.add(zh_idx)
            continue
        lines[idx] = _with_citation(lines[idx], "*(Sources: " + "; ".join(
            f"{name}, {date or 'date unknown'}" for name, _, date in sources) + ")*")
        if zh_idx is not None:
            lines[zh_idx] = _with_citation(lines[zh_idx], "*(來源：" + "；".join(
                f"{name}，{date or '日期不明'}" for name, _, date in sources) + ")*")
        for name, url, date in sources:
            entries.setdefault(url, (name, date))

    rebuilt = [f"- {name}: {url} (published {date or 'date unknown'})" for url, (name, date) in entries.items()]
    for start, end, heading in ((0, zh_start, EN_SOURCES), (zh_start, len(lines), ZH_SOURCES)):
        old = [i for i in _section_indexes(lines, start, end, heading) if _SOURCE_ENTRY_RE.match(lines[i].strip())]
        if old:
            lines[old[0]] = "\n".join(rebuilt)
            drop.update(old[1:])
    kept = [line for i, line in enumerate(lines) if i not in drop]
    return _collapse_blank_lines("\n".join(kept))


def _clean_source(src) -> tuple[str, str, str | None] | None:
    if not isinstance(src, dict):
        return None
    name, url = str(src.get("name") or "").strip(), str(src.get("url") or "").strip()
    if not name or not url.startswith("http"):
        return None
    date = str(src.get("date") or "")
    return name, url, date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else None


def _with_citation(line: str, citation: str) -> str:
    if _CITATION_RE.search(line):
        return _CITATION_RE.sub(lambda _: citation, line)
    return f"{line.rstrip()} {citation}"


def format_held(held: list[dict], today_date: str, max_age_days: int = MAX_STORY_AGE_DAYS) -> str:
    """Markdown body for the manager's review issue."""
    out = [
        f"The {today_date} run held back {len(held)} "
        f"{'story' if len(held) == 1 else 'stories'} whose earliest dated source is more than "
        f"{max_age_days} days old. {'It' if len(held) == 1 else 'They'} passed source verification but "
        f"{'was' if len(held) == 1 else 'were'} **not published**.",
        "",
        "Please decide whether each one is worth publishing. To publish one, add its headline "
        "and sources to `summaries.md` by hand.",
    ]
    for n, story in enumerate(held, 1):
        out += ["", f"### {n}. {story['title']}", f"- Earliest source date: {story['earliest']}", "- Sources:"]
        for name, date, url in story["sources"]:
            out.append(f"  - {name}, {date or 'date unknown'}" + (f": {url}" if url else ""))
        out += ["", "```", story["headline"], "```"]
    return "\n".join(out) + "\n"


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _section_indexes(lines: list[str], start: int, end: int, heading: str) -> list[int]:
    """Line indexes inside `heading` (up to the next '### ' or block marker) within [start, end)."""
    for i in range(start, end):
        if lines[i].strip() == heading:
            out = []
            for j in range(i + 1, end):
                stripped = lines[j].strip()
                if stripped.startswith("### ") or stripped in (EN_MARKER, ZH_MARKER):
                    break
                out.append(j)
            return out
    return []


def _section_lines(block: str, heading: str) -> list[str]:
    lines = block.splitlines()
    return [lines[i].lstrip() for i in _section_indexes(lines, 0, len(lines), heading)]


def _citation_sources(line: str) -> list[tuple[str, str | None]]:
    """[(source name, YYYY-MM-DD or None)] from a headline's *(Sources: A, date; B, date)*."""
    m = _CITATION_RE.search(line)
    if not m:
        return []
    sources = []
    for part in re.split(r"[;；]", m.group(1)):
        part = part.strip()
        if not part:
            continue
        date = _ISO_DATE_RE.search(part)
        name = re.split(r"[,，]", part)[0].strip()
        sources.append((name, date.group(1) if date else None))
    return sources


def _source_entries(lines: list[str], start: int, end: int) -> list[tuple[str, str, str | None]]:
    """[(name, url, YYYY-MM-DD or None)] from the EN Sources section."""
    out = []
    for i in _section_indexes(lines, start, end, EN_SOURCES):
        line = lines[i].strip()
        m = _SOURCE_ENTRY_RE.match(line)
        if m:
            date = _ISO_DATE_RE.search(line[m.end():])
            out.append((m.group(1), m.group(2), date.group(1) if date else None))
    return out


def _source_urls(lines: list[str], start: int, end: int) -> dict[str, str]:
    urls = {}
    for i in _section_indexes(lines, start, end, EN_SOURCES):
        m = _SOURCE_ENTRY_RE.match(lines[i].strip())
        if m:
            urls[m.group(1)] = m.group(2)
    return urls


def _matches(entry_name: str, names: set[str]) -> bool:
    """Sources entries may add a note, e.g. 'AP News (North Korea torpedo)' for citation 'AP News'."""
    return any(entry_name.startswith(name) or name.startswith(entry_name) for name in names if name)


def _lookup(urls: dict[str, str], name: str) -> str | None:
    return next((url for entry, url in urls.items() if _matches(entry, {name})), None)


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)
