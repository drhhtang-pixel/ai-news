import os
import re
import sys
from datetime import datetime, timezone
import anthropic
from knowledge import (
    KNOWN_HISTORY_DAYS,
    MAX_STORY_AGE_DAYS,
    format_held,
    hold_old_stories,
    known_headlines,
    known_stories_prompt,
)
import tools
from tools import TOOLS, execute_tool, log_tool_call
from writer import append_summary
from verifier import verify_summary

SYSTEM_PROMPT = """You are an AI news monitor. Your job is to search the web for the latest AI news and produce a bilingual structured summary in both English and Traditional Chinese.

Use the web_search tool to find current AI news, research papers, product launches, and notable developments. Run multiple targeted searches to get comprehensive coverage — vary your queries to cover different angles.

When you have gathered enough information, write your final answer using EXACTLY this format — the HTML comment markers are required:

<!-- EN -->
### Headlines
A bullet list of the most important news items. Each item MUST follow this exact format:
- **[Headline]:** [One-sentence description]. *(Sources: [Publication A], YYYY-MM-DD; [Publication B], YYYY-MM-DD)*

List up to 3 sources for that story (the most authoritative ones), each with its own published date. One source is enough; sources with different dates are fine when they cover the same story.

Example:
- **OpenAI releases new model:** The company launched GPT-5 with improved reasoning capabilities. *(Sources: TechCrunch, 2026-06-08; Reuters, 2026-06-07)*

### Analysis
2-3 paragraphs analyzing key trends and implications.

### Sources
A list of all sources with their direct article URLs (NOT homepage URLs). Each entry MUST follow this format:
- [Publication Name]: https://specific-article-url (published YYYY-MM-DD)

STRICT RULES for Sources:
- Every source cited in a headline MUST appear here, and every entry here MUST be cited by at least one headline.
- Each source must actually report the story it is cited for. Do not cite background articles that do not cover the story.
- The (published YYYY-MM-DD) date MUST be copied from the "Published:" line of the tool result for that URL. Never guess or infer a date. If the tool reported "unknown", write "(published date unknown)" and "date unknown" in the headline citation.
- URLs must point to specific articles, not homepages.

Example:
- TechCrunch: https://techcrunch.com/2026/06/08/openai-gpt5 (published 2026-06-08)

<!-- ZH -->
### 頭條新聞
以繁體中文列出最重要的新聞。每條必須遵循以下格式：
- **[標題]：** [一句話說明]。*(來源：[媒體 A]，YYYY-MM-DD；[媒體 B]，YYYY-MM-DD)*

每則新聞最多列 3 個來源（選最具代表性的），每個來源各自標明發布日期。一個來源即可；不同日期的來源報導同一則新聞也沒有問題。

範例：
- **OpenAI 發布新模型：** 該公司推出具備更強推理能力的 GPT-5。*(來源：TechCrunch，2026-06-08；Reuters，2026-06-07)*

### 分析
2-3段繁體中文分析，說明主要趨勢與影響。

### 來源
列出所有來源的直接文章網址（非首頁網址）。每條格式：
- [媒體名稱]: https://specific-article-url (published YYYY-MM-DD)

來源嚴格規定：頭條引用的每個來源都要列在這裡，這裡的每個來源也都要被至少一則頭條引用。來源必須確實報導了該則新聞。發布日期必須照抄工具結果的「Published:」值，不可推測；工具回報 unknown 時寫「(published date unknown)」，頭條引用寫「日期不明」。

IMPORTANT: You MUST include both <!-- EN --> and <!-- ZH --> blocks in your response, in that order. Do not omit either block. Every headline MUST include an inline citation listing its sources and their dates."""

MAX_TOOL_CALLS = 15


def validate_env() -> tuple[str, str, str, str]:
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("Error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        print("Error: TAVILY_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    search_topic = os.environ.get("SEARCH_TOPIC", "AI news today")
    output_file = os.environ.get("OUTPUT_FILE", "summaries.md")

    return anthropic_key, tavily_key, search_topic, output_file


def run_agent(search_topic: str, today_date: str, known: list[str] | None = None) -> str:
    client = anthropic.Anthropic()

    dated_system_prompt = (
        SYSTEM_PROMPT
        + f"\n\nToday's date is {today_date} (UTC). Report AI news that is NEW TO THIS MONITOR: stories "
        "that are not in the already-published list below. Most will be from the last day or two, but a "
        "story from up to about a month ago is fine if this monitor has not reported it yet. A story's "
        "sources may have been published on different dates; cite each one with its own date. Exclude "
        "year-in-review articles and historical summaries."
        + known_stories_prompt(known)
    )

    messages = [
        {
            "role": "user",
            "content": f"Search for and summarize: {search_topic}"
        }
    ]

    tool_call_count = 0

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=dated_system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        tools.record_usage("writer", response)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Execute tool calls and check guard
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_call_count += 1
                result = execute_tool(block.name, block.input)
                log_tool_call("writer", block.name, block.input, result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        if not tool_results:
            # stop_reason was tool_use but no tool_use blocks found — return any text present
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        messages.append({"role": "user", "content": tool_results})

        if tool_call_count >= MAX_TOOL_CALLS:
            # Guard triggered: force a final answer with collected results
            messages.append({
                "role": "user",
                "content": (
                    "You have reached the maximum number of searches. "
                    "Please write your final structured summary now based on what you have found."
                )
            })
            text = ""
            for attempt in range(2):
                final = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    system=dated_system_prompt,
                    tools=TOOLS,
                    tool_choice={"type": "none"},
                    messages=messages,
                )
                tools.record_usage("writer", final)
                text = "".join(block.text for block in final.content if hasattr(block, "text"))
                if "<!-- EN -->" in text:
                    return text
                # The model sometimes answers with a plan ("Now let me verify...") instead of the
                # summary; it cannot call tools any more, so ask once more for the summary itself.
                print(f"Warning: writer gave no summary after the search limit: {text[:150]!r}", file=sys.stderr)
                messages.append({"role": "assistant", "content": text or "(no text)"})
                messages.append({
                    "role": "user",
                    "content": (
                        "That is not the summary. No more research is possible. Write the complete "
                        "bilingual summary now, starting with <!-- EN -->, using only what you have found."
                    )
                })
            return text


EN_MARKER = "<!-- EN -->"
ZH_MARKER = "<!-- ZH -->"


def _count_headlines(block: str, heading: str) -> int | None:
    """Count '- **' bullets between `heading` and the next '### ' heading; None if no heading."""
    lines = block.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    if not starts:
        return None
    count = 0
    for line in lines[starts[0] + 1:]:
        if line.lstrip().startswith("### "):
            break
        if line.lstrip().startswith("- **"):
            count += 1
    return count


def _headline_total(summary: str) -> int:
    en = summary.split(ZH_MARKER)[0]
    return _count_headlines(en, "### Headlines") or 0


# Balanced parentheses stay inside a URL ("…/Story_(AI)"); a closing one ends it ("[Name](url)").
_URL_RE = re.compile(r"https?://(?:[^\s()<>\]]|\([^\s()<>]*\))+")


def unseen_source_urls(summary: str, seen: set[str]) -> list[str]:
    """URLs in the summary that no tool returned during this run (i.e. made up)."""
    urls = dict.fromkeys(m.group(0).rstrip(".,;") for m in _URL_RE.finditer(summary))
    return [url for url in urls if tools.normalize_url(url) not in seen]


def validate_summary(summary: str) -> list[str]:
    """Return a list of integrity errors. Empty list means the summary is well-formed."""
    errors: list[str] = []

    if not summary or not summary.strip():
        errors.append("summary is empty")
        return errors

    en_idx = summary.find(EN_MARKER)
    zh_idx = summary.find(ZH_MARKER)

    if en_idx == -1:
        errors.append(f"missing {EN_MARKER} marker")
    if zh_idx == -1:
        errors.append(f"missing {ZH_MARKER} marker")
    if en_idx != -1 and zh_idx != -1 and zh_idx < en_idx:
        errors.append(f"{ZH_MARKER} appears before {EN_MARKER}")

    if en_idx != -1 and zh_idx != -1 and en_idx < zh_idx:
        en_block = summary[en_idx:zh_idx]
        zh_block = summary[zh_idx:]
        for lang, block, heading in (("EN", en_block, "### Headlines"), ("ZH", zh_block, "### 頭條新聞")):
            count = _count_headlines(block, heading)
            if count is None:
                errors.append(f"{lang} block has no '{heading}' section")
            elif count == 0:
                errors.append(f"{lang} block has no headlines (no '- **' bullets under '{heading}')")
        en_count = _count_headlines(en_block, "### Headlines") or 0
        zh_count = _count_headlines(zh_block, "### 頭條新聞") or 0
        if en_count and zh_count and en_count != zh_count:
            errors.append(f"EN has {en_count} headlines but ZH has {zh_count}")
        for lang, block, heading in (("EN", en_block, "### Sources"), ("ZH", zh_block, "### 來源")):
            section = block.split(heading, 1)[1].split("### ", 1)[0] if heading in block else ""
            if en_count and not _URL_RE.search(section):
                errors.append(f"{lang} block has no source URLs under '{heading}'")

    return errors


def main() -> None:
    _, _, search_topic, output_file = validate_env()
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    search_topic = os.environ.get("SEARCH_TOPIC", f"AI news {today_date}")
    print(f"Searching for: {search_topic}")
    known = known_headlines(output_file, today_date)
    print(f"Known stories from the last {KNOWN_HISTORY_DAYS} days: {len(known)}")
    summary = run_agent(search_topic, today_date, known)
    print(f"Writer headlines: {_headline_total(summary)}")
    summary, verified = verify_summary(summary, today_date, known)
    if not verified:
        # Policy (唐老師, 2026-10-19): never publish a summary whose sources were not checked.
        print("Error: source verification did not complete; nothing is published today.", file=sys.stderr)
        print(tools.usage_report())
        sys.exit(1)
    print(f"Headlines after verification: {_headline_total(summary)}")

    summary, held = hold_old_stories(summary, today_date)
    if held:
        held_file = os.environ.get("HELD_FILE", "held_stories.md")
        with open(held_file, "w", encoding="utf-8") as f:
            f.write(format_held(held, today_date))
        print(f"Held for manager review (older than {MAX_STORY_AGE_DAYS} days): {len(held)} -> {held_file}")
    print(f"Headlines to publish: {_headline_total(summary)}")

    print(tools.usage_report())

    errors = validate_summary(summary)
    errors += [f"source URL was never returned by a tool (made up?): {url}"
               for url in unseen_source_urls(summary, tools.SEEN_URLS)]
    if errors:
        print("Error: summary failed integrity check:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print("--- summary content ---", file=sys.stderr)
        print(summary or "(empty)", file=sys.stderr)
        sys.exit(1)

    append_summary(summary, output_file)


if __name__ == "__main__":
    main()
