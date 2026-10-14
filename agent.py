import os
import sys
from datetime import datetime, timezone
import anthropic
from tools import TOOLS, allowed_dates, execute_tool
from writer import append_summary
from verifier import verify_summary

SYSTEM_PROMPT = """You are an AI news monitor. Your job is to search the web for the latest AI news and produce a bilingual structured summary in both English and Traditional Chinese.

Use the web_search tool to find current AI news, research papers, product launches, and notable developments. Run multiple targeted searches to get comprehensive coverage — vary your queries to cover different angles.

When you have gathered enough information, write your final answer using EXACTLY this format — the HTML comment markers are required:

<!-- EN -->
### Headlines
A bullet list of the most important news items. Each item MUST follow this exact format:
- **[Headline]:** [One-sentence description]. *(Source: [Publication Name], [Month Day])*

Example:
- **OpenAI releases new model:** The company launched GPT-5 with improved reasoning capabilities. *(Source: TechCrunch, June 8)*

### Analysis
2-3 paragraphs analyzing key trends and implications.

### Sources
A list of all sources with their direct article URLs (NOT homepage URLs). Each entry MUST follow this format:
- [Publication Name]: https://specific-article-url (published YYYY-MM-DD)

STRICT RULES for Sources:
- Only include articles published within the last 24 hours (the dates given below). Do NOT list background articles, primary documents, or older coverage.
- If the only source you found for a story is older than that, find a recent article that covers the same story instead.
- The (published YYYY-MM-DD) date MUST be copied from the "Published:" line of the tool result for that URL. Never guess or infer a date. Do not use an article whose Published date is "unknown" or outside the allowed dates.
- URLs must point to specific articles, not homepages.

Example:
- TechCrunch: https://techcrunch.com/2026/06/08/openai-gpt5 (published 2026-06-08)

<!-- ZH -->
### 頭條新聞
以繁體中文列出最重要的新聞。每條必須遵循以下格式：
- **[標題]：** [一句話說明]。*(來源：[媒體名稱]，[月 日])*

範例：
- **OpenAI 發布新模型：** 該公司推出具備更強推理能力的 GPT-5。*(來源：TechCrunch，6 月 8 日)*

### 分析
2-3段繁體中文分析，說明主要趨勢與影響。

### 來源
列出所有來源的直接文章網址（非首頁網址）。每條格式：
- [媒體名稱]: https://specific-article-url (published YYYY-MM-DD)

來源嚴格規定：只列過去 24 小時內（下方指定日期）發布的文章。不得列出背景資料、原始文件或更早的報導。發布日期必須照抄工具結果的「Published:」值，不可推測。

IMPORTANT: You MUST include both <!-- EN --> and <!-- ZH --> blocks in your response, in that order. Do not omit either block. Every headline MUST include an inline source citation."""

MAX_TOOL_CALLS = 10


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


def run_agent(search_topic: str, today_date: str) -> str:
    client = anthropic.Anthropic()
    yesterday, _ = allowed_dates(today_date)

    dated_system_prompt = (
        SYSTEM_PROMPT
        + f"\n\nToday's date is {today_date} (UTC). Only report news published on {yesterday} or {today_date} "
        "(the last 24 hours). Exclude year-in-review articles, historical summaries, and any content "
        "published outside these dates."
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
            final = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                system=dated_system_prompt,
                tools=TOOLS,
                tool_choice={"type": "none"},
                messages=messages,
            )
            for block in final.content:
                if hasattr(block, "text"):
                    return block.text
            return ""


EN_MARKER = "<!-- EN -->"
ZH_MARKER = "<!-- ZH -->"


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
        if not any(line.lstrip().startswith("- **") for line in en_block.splitlines()):
            errors.append("EN block has no headlines (no '- **' bullets)")
        if not any(line.lstrip().startswith("- **") for line in zh_block.splitlines()):
            errors.append("ZH block has no headlines (no '- **' bullets)")

    return errors


def main() -> None:
    _, _, search_topic, output_file = validate_env()
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    search_topic = os.environ.get("SEARCH_TOPIC", f"AI news {today_date}")
    print(f"Searching for: {search_topic}")
    summary = run_agent(search_topic, today_date)
    summary = verify_summary(summary, today_date)

    errors = validate_summary(summary)
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
