import os
import sys
import anthropic
from tools import TOOLS, execute_tool

VERIFIER_SYSTEM_PROMPT = """You are a news source verifier. You receive a bilingual AI news summary (English and Chinese) and must verify that each headline's inline source citation is accurate.

Your task:
1. Parse each headline in the <!-- EN --> block and extract the cited URL from *(Source: Name, Date)*
2. For each headline, call extract_url on the cited URL to verify it:
   - The URL must resolve to an actual article (not a homepage or error page)
   - The article must have been published on today's date
   - IMPORTANT: If extract_url returns "Published: unknown", treat this as a date verification failure — do NOT attempt to infer the date from article content. Proceed directly to step 3.
3. If validation fails (URL error, wrong date, published_date is unknown, or no article content):
   - Call web_search to find a replacement article about the same news story published today
   - If found: update the headline's source citation with the new URL and source name
   - If not found: remove the headline from the summary entirely
4. Apply the same updates (replacements and removals) to the corresponding <!-- ZH --> block by position (1st EN headline ↔ 1st ZH headline, etc.)
5. Output the complete corrected bilingual summary in EXACTLY the same format as the input, preserving all sections (Headlines, Analysis, Sources, 頭條新聞, 分析, 來源).

CRITICAL OUTPUT RULES:
- Your ENTIRE response must be ONLY the corrected summary — start directly with <!-- EN --> and end after the last 來源 entry
- Do NOT include any preamble, explanation, reasoning, log, verification report, or commentary
- Do NOT write anything before <!-- EN --> or after the last 來源 section
- Only verify and modify headlines — do NOT change Analysis or Sources sections
- Keep the exact same <!-- EN --> and <!-- ZH --> block structure
- If a headline has no inline citation, skip it (do not remove it)"""

MAX_VERIFIER_TOOL_CALLS = 20


def _extract_bilingual_summary(text: str) -> str:
    """Strip any preamble/postamble — return only the <!-- EN --> ... block."""
    marker = "<!-- EN -->"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx:].strip()


def run_verifier(summary: str, today_date: str) -> str:
    client = anthropic.Anthropic()

    system = VERIFIER_SYSTEM_PROMPT + f"\n\nToday's date is {today_date}."

    messages = [
        {
            "role": "user",
            "content": (
                f"Please verify and correct the following news summary. "
                f"Today's date is {today_date}.\n\n{summary}"
            )
        }
    ]

    tool_call_count = 0

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return _extract_bilingual_summary(block.text)
            return ""

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
            for block in response.content:
                if hasattr(block, "text"):
                    return _extract_bilingual_summary(block.text)
            return ""

        messages.append({"role": "user", "content": tool_results})

        if tool_call_count >= MAX_VERIFIER_TOOL_CALLS:
            messages.append({
                "role": "user",
                "content": (
                    "You have reached the maximum number of tool calls. "
                    "Output the corrected summary now based on verifications completed so far."
                )
            })
            final = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                system=system,
                messages=messages,
            )
            for block in final.content:
                if hasattr(block, "text"):
                    return _extract_bilingual_summary(block.text)
            return ""


def verify_summary(summary: str, today_date: str) -> str:
    try:
        result = run_verifier(summary, today_date)
        if not result:
            print("Warning: verifier returned empty output, using original summary", file=sys.stderr)
            return summary
        return result
    except Exception as e:
        print(f"Warning: verifier failed: {e}", file=sys.stderr)
        return summary
