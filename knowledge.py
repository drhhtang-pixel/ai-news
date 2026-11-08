"""What the monitor already knows, which stories are too old to publish without review, and how
the verifier's per-headline decisions are applied to a summary.

"New" means new to this monitor, not new in time: a story that has not been published
before may be reported even if it happened weeks ago. Stories whose earliest dated source
is older than MAX_STORY_AGE_DAYS are held back for the manager instead of published.

Verified headlines carry their sources as links, e.g.
*(Sources: [Wire](https://wire.example/a), 2026-10-17; [Daily](https://daily.example/b), date unknown)*,
so every source stays tied to its own story without guessing from publication names.
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
MAX_SOURCES_PER_HEADLINE = 3

_ENTRY_HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})", re.MULTILINE)
_TITLE_RE = re.compile(r"^- \*\*(.+?)\*\*")
_CITATION_RE = re.compile(r"\*\((?:Sources?|來源)\s*[:：]\s*(.*?)\)\*\s*$")
# URLs may contain balanced parentheses, e.g. https://example.com/Story_(AI)
_URL_IN_LINK = r"https?://(?:[^\s()]|\([^\s()]*\))+"
_LINKED_SOURCE_RE = re.compile(r"\[([^\]]+)\]\((" + _URL_IN_LINK + r")\)\s*[,，]\s*([^;；]*)")
# A source's date field: the date that ENDS the source, right after its last comma, as the
# program writes it ("[name](url), 2026-10-17" / "name, 2026-10-17"). Dates inside names or
# URLs are never at the end, so they can't match however the URL is shaped.
_TRAILING_DATE_RE = re.compile(r"[,，]\s*(\d{4}-\d{2}-\d{2})\s*$")
# Sources are separated by "; " (EN) or "；" (ZH); a URL can contain ";" but never "; ".
_SOURCE_SEPARATOR_RE = re.compile(r";\s+|；")
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_SOURCE_ENTRY_RE = re.compile(r"^- (.+?):\s*(https?://\S+)")


class InvalidDecisions(ValueError):
    """The verifier's decisions cannot be applied safely to this summary."""


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


def known_stories_prompt(known: list[str] | None) -> str:
    """The 'already published' list shared by the writer and the verifier."""
    listed = "\n".join(f"- {title}" for title in known) if known else "(none)"
    return (
        "\n\nALREADY PUBLISHED by this monitor (do NOT report these stories again, even from new "
        f"sources or with new wording):\n{listed}"
    )


def headline_items(summary: str) -> tuple[list[str], list[str]]:
    """(EN headline lines, ZH headline lines) in order."""
    if EN_MARKER not in summary or ZH_MARKER not in summary:
        return [], []
    lines = summary.splitlines()
    zh_start = _zh_start(lines)
    en = [lines[i] for i in _headline_indexes(lines, 0, zh_start, EN_HEADLINES)]
    zh = [lines[i] for i in _headline_indexes(lines, zh_start, len(lines), ZH_HEADLINES)]
    return en, zh


def check_decisions(decisions, headline_count: int) -> list[str]:
    """Problems that make the decisions unsafe to apply; empty list means they are complete."""
    if not isinstance(decisions, list):
        return ["decisions must be a list"]
    problems = []
    indexes = []
    for d in decisions:
        if not isinstance(d, dict):
            problems.append(f"decision is not an object: {d!r}")
            continue
        index, action = d.get("index"), d.get("action")
        if not isinstance(index, int) or isinstance(index, bool):
            problems.append(f"index must be an integer: {index!r}")
            continue
        indexes.append(index)
        if action not in ("keep", "remove"):
            problems.append(f"#{index}: action must be keep or remove, got {action!r}")
        if not isinstance(d.get("sources", []), list):
            problems.append(f"#{index}: sources must be a list")
    duplicates = sorted({i for i in indexes if indexes.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate indexes: {duplicates}")
    expected = set(range(1, headline_count + 1))
    missing, extra = sorted(expected - set(indexes)), sorted(set(indexes) - expected)
    if missing:
        problems.append(f"missing decisions for headlines {missing} (there are {headline_count})")
    if extra:
        problems.append(f"indexes out of range: {extra} (there are {headline_count})")
    return problems


def apply_verification(summary: str, decisions: list[dict]) -> str:
    """Apply the verifier's per-headline decisions to the summary.

    Raises InvalidDecisions unless the EN and ZH headline counts match and there is exactly one
    valid decision per headline (see check_decisions). Kept headlines get EN and ZH citations
    rebuilt as links from the decision's sources (at most 3; invalid URLs dropped; dates must
    be real YYYY-MM-DD dates, otherwise "date unknown"). Removed headlines, and kept ones left
    with no valid source, are dropped in both languages. Both Sources sections are rebuilt from
    the remaining citations, even if they were empty. Analysis is untouched.
    """
    if EN_MARKER not in summary or ZH_MARKER not in summary:
        raise InvalidDecisions("summary has no <!-- EN --> / <!-- ZH --> blocks")
    lines = summary.splitlines()
    zh_start = _zh_start(lines)
    en_items = _headline_indexes(lines, 0, zh_start, EN_HEADLINES)
    zh_items = _headline_indexes(lines, zh_start, len(lines), ZH_HEADLINES)
    if len(en_items) != len(zh_items):
        raise InvalidDecisions(f"EN has {len(en_items)} headlines but ZH has {len(zh_items)}")
    problems = check_decisions(decisions, len(en_items))
    if problems:
        raise InvalidDecisions("; ".join(problems))

    by_index = {d["index"]: d for d in decisions}
    drop: set[int] = set()
    entries: dict[str, tuple[str, str | None]] = {}  # url -> (name, date), in citation order
    for pos, (idx, zh_idx) in enumerate(zip(en_items, zh_items), 1):
        decision = by_index[pos]
        sources = [_clean_source(src) for src in decision.get("sources") or []]
        sources = [src for src in sources if src][:MAX_SOURCES_PER_HEADLINE]
        if decision["action"] != "keep" or not sources:
            drop.update((idx, zh_idx))
            continue
        lines[idx] = _with_citation(lines[idx], "*(Sources: " + "; ".join(
            f"[{name}]({url}), {date or 'date unknown'}" for name, url, date in sources) + ")*")
        lines[zh_idx] = _with_citation(lines[zh_idx], "*(來源：" + "；".join(
            f"[{name}]({url})，{date or '日期不明'}" for name, url, date in sources) + ")*")
        for name, url, date in sources:
            entries.setdefault(url, (name, date))

    rebuilt = [f"- {name}: {url} (published {date or 'date unknown'})" for url, (name, date) in entries.items()]
    lines = [line for i, line in enumerate(lines) if i not in drop]
    lines = _replace_sources(lines, EN_SOURCES, rebuilt, before=ZH_MARKER)
    lines = _replace_sources(lines, ZH_SOURCES, rebuilt, before=None)
    return _collapse_blank_lines("\n".join(lines))


def hold_old_stories(summary: str, today_date: str,
                     max_age_days: int = MAX_STORY_AGE_DAYS) -> tuple[str, list[dict]]:
    """Remove headlines whose earliest dated source is older than `max_age_days`.

    Returns the remaining summary and the held stories. A headline with no dated source is
    kept. The ZH headline at the same position, and Sources entries whose URL is cited only
    by held headlines, are removed too. Sources are taken from linked citations; plain
    citations (a writer draft; not published in production) fall back to matching the Sources
    section by name.
    """
    if EN_MARKER not in summary or ZH_MARKER not in summary:
        return summary, []
    cutoff = _parse_date(today_date) - timedelta(days=max_age_days)
    lines = summary.splitlines()
    zh_start = _zh_start(lines)
    en_items = _headline_indexes(lines, 0, zh_start, EN_HEADLINES)
    zh_items = _headline_indexes(lines, zh_start, len(lines), ZH_HEADLINES)
    by_name = _source_entries(lines, 0, zh_start)

    held: list[dict] = []
    drop: set[int] = set()
    kept_urls: set[str] = set()
    held_urls: set[str] = set()
    for pos, idx in enumerate(en_items):
        sources = [(name, url or _lookup(by_name, name, date), date)
                   for name, url, date in citation_sources(lines[idx])]
        # Age uses every source's date field, including sources the link parser could not
        # read, so a missing date can never make a story look newer.
        earliest = citation_earliest_date(lines[idx])
        if earliest and _parse_date(earliest) < cutoff:
            drop.add(idx)
            if pos < len(zh_items):
                drop.add(zh_items[pos])
            held_urls.update(url for _, url, _ in sources if url)
            held.append({
                "title": _TITLE_RE.match(lines[idx].lstrip()).group(1).rstrip(":："),
                "headline": lines[idx].strip(),
                "earliest": earliest,
                "sources": sources,
            })
        else:
            kept_urls.update(url for _, url, _ in sources if url)

    if not held:
        return summary, []

    held_urls -= kept_urls
    for start, end, heading in ((0, zh_start, EN_SOURCES), (zh_start, len(lines), ZH_SOURCES)):
        for i in _section_indexes(lines, start, end, heading):
            m = _SOURCE_ENTRY_RE.match(lines[i].strip())
            if m and m.group(2) in held_urls:
                drop.add(i)

    kept = [line for i, line in enumerate(lines) if i not in drop]
    return _collapse_blank_lines("\n".join(kept)), held


def format_held(held: list[dict], today_date: str, max_age_days: int = MAX_STORY_AGE_DAYS) -> str:
    """Markdown body for the manager's review issue (only verified summaries reach this point)."""
    one = len(held) == 1
    out = [
        f"The {today_date} run held back {len(held)} {'story' if one else 'stories'} whose earliest "
        f"cited source is more than {max_age_days} days old. {'It' if one else 'They'} passed source "
        f"verification, and {'it was' if one else 'they were'} **not published**.",
        "",
        "Please decide whether each one is worth publishing. To publish one, add its headline "
        "and sources to `summaries.md` by hand.",
    ]
    for n, story in enumerate(held, 1):
        out += ["", f"### {n}. {story['title']}", f"- Earliest cited source date: {story['earliest']}", "- Sources:"]
        for name, url, date in story["sources"]:
            out.append(f"  - {name}, {date or 'date unknown'}" + (f": {url}" if url else " (URL not found)"))
        out += ["", "```", story["headline"], "```"]
    return "\n".join(out) + "\n"


def citation_sources(line: str) -> list[tuple[str, str | None, str | None]]:
    """[(name, url or None, YYYY-MM-DD or None)] from a headline's *(Sources: ...)* citation.

    Linked sources ([Name](url), date) carry their URL; plain ones (Name, date) do not.
    """
    m = _CITATION_RE.search(line)
    if not m:
        return []
    body = m.group(1)
    linked = list(_LINKED_SOURCE_RE.finditer(body))
    if linked:
        return [(lm.group(1).strip(), lm.group(2), _valid_date(_first_iso(lm.group(3)))) for lm in linked]
    sources = []
    for part in re.split(r"[;；]", body):
        part = part.strip()
        if part:
            sources.append((re.split(r"[,，]", part)[0].strip(), None, _valid_date(_date_field(part))))
    return sources


def citation_earliest_date(line: str) -> str | None:
    """Earliest real date among the citation's DATE FIELDS: the date that ends each source.

    Dates inside source names or URLs (e.g. https://example.com/2020-01-01-retrospective or
    a URL with nested parentheses and commas) never count, because only a date at the very end
    of a source, after its last comma, is read. A source whose link could not be parsed still
    contributes its trailing date field.
    """
    m = _CITATION_RE.search(line)
    if not m:
        return None
    dates = [_valid_date(_date_field(part)) for part in _SOURCE_SEPARATOR_RE.split(m.group(1))]
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _date_field(part: str) -> str | None:
    """The date that ends a citation part, after its last comma; None for 'date unknown' etc."""
    m = _TRAILING_DATE_RE.search(part.strip())
    return m.group(1) if m else None


def _first_iso(text: str) -> str | None:
    m = _ISO_DATE_RE.search(text)
    return m.group(1) if m else None


def _valid_date(value: str | None) -> str | None:
    """The value if it is a real calendar date (YYYY-MM-DD), otherwise None."""
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        _parse_date(value)
    except ValueError:
        return None
    return value


def _clean_source(src) -> tuple[str, str, str | None] | None:
    if not isinstance(src, dict):
        return None
    name, url = str(src.get("name") or "").strip(), str(src.get("url") or "").strip()
    if not name or not re.match(r"https?://\S+$", url) or any(c in name for c in "[]"):
        return None
    return name, url, _valid_date(str(src.get("date") or ""))


def _with_citation(line: str, citation: str) -> str:
    if _CITATION_RE.search(line):
        return _CITATION_RE.sub(lambda _: citation, line)
    return f"{line.rstrip()} {citation}"


def _replace_sources(lines: list[str], heading: str, entries: list[str], before: str | None) -> list[str]:
    """Replace the entries under `heading` with `entries`; add the section if it is missing."""
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        at = next((i for i, line in enumerate(lines) if before and line.strip() == before), len(lines))
        return lines[:at] + ["", heading] + entries + [""] + lines[at:]
    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("### ") or stripped in (EN_MARKER, ZH_MARKER):
            break
        end += 1
    keep = [line for line in lines[start + 1:end] if line.strip() and not _SOURCE_ENTRY_RE.match(line.strip())]
    return lines[:start + 1] + entries + keep + [""] + lines[end:]


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _zh_start(lines: list[str]) -> int:
    return next(i for i, line in enumerate(lines) if line.strip() == ZH_MARKER)


def _headline_indexes(lines: list[str], start: int, end: int, heading: str) -> list[int]:
    return [i for i in _section_indexes(lines, start, end, heading) if lines[i].lstrip().startswith("- **")]


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


def _source_entries(lines: list[str], start: int, end: int) -> list[tuple[str, str, str | None]]:
    """[(name, url, YYYY-MM-DD or None)] from the EN Sources section."""
    out = []
    for i in _section_indexes(lines, start, end, EN_SOURCES):
        line = lines[i].strip()
        m = _SOURCE_ENTRY_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2), _valid_date(_first_iso(line[m.end():]))))
    return out


def _lookup(entries: list[tuple[str, str, str | None]], name: str, date: str | None) -> str | None:
    """URL for a plain (unlinked) citation: exact name match, preferring the cited date.

    Returns None when several entries match equally well, rather than guessing.
    """
    candidates = [(url, d) for n, url, d in entries if _same_name(n, name)]
    if date:
        dated = [url for url, d in candidates if d == date]
        if len(dated) == 1:
            return dated[0]
    urls = {url for url, _ in candidates}
    return urls.pop() if len(urls) == 1 else None


def _same_name(entry_name: str, name: str) -> bool:
    """'AP News (North Korea torpedo)' matches citation 'AP News'; 'Wire Extra' does not match 'Wire'."""
    return entry_name == name or re.match(re.escape(name) + r"\s*[(（]", entry_name) is not None


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)
