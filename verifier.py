import os
import sys
import anthropic
from knowledge import known_stories_prompt
from tools import TOOLS, execute_tool

VERIFIER_SYSTEM_PROMPT = """You are a news source verifier. You receive a bilingual AI news summary (English and Chinese). Your job is to check that each headline is supported by the CONTENT of the sources it cites. Publication dates are NOT a reason to keep or remove anything: one story may be reported by several sources on different dates, and that is fine.

Your task:
1. For each headline in the <!-- EN --> block, read its inline citation *(Sources: Name, Date; ...)* and find each cited source's URL in the Sources section.
2. Call extract_url on each cited URL and check:
   - The URL resolves to an actual article (not a homepage, index page, video page, or error page)
   - The article content actually reports the facts stated in the headline and its description
3. For each cited source (keep at most 3 per headline — the ones that best support it):
   - If it supports the headline: keep it, and set its date to the "Published:" value returned by extract_url (write "date unknown" / "published date unknown" when the tool says unknown). Never guess a date.
   - If it does not support the headline, or the URL fails: drop that source from the headline's citation.
4. If a headline has no supporting source left:
   - Call web_search to find an article that reports the same story, and confirm it with extract_url
   - If found: cite it, with its name and the date from the tool result
   - If not found: remove the headline entirely
5. If a headline reports a story that is in the ALREADY PUBLISHED list below (same event, even if worded differently), remove it.
6. If a headline's description states something no source supports, correct the description to match the sources rather than removing the headline.
7. Rebuild the Sources / 來源 sections so they list exactly the sources still cited by headlines, each as "- Name: URL (published YYYY-MM-DD)" or "(published date unknown)".
8. Apply the same changes to the corresponding <!-- ZH --> block by position (1st EN headline ↔ 1st ZH headline, etc.).
9. Output the complete corrected bilingual summary in EXACTLY the same format as the input, preserving all sections (Headlines, Analysis, Sources, 頭條新聞, 分析, 來源).

CRITICAL OUTPUT RULES:
- Write the corrected summary exactly ONCE, in your final message, after all tool calls are finished. Never write drafts or partial summaries in earlier messages.
- Your ENTIRE response must be ONLY the corrected summary — start directly with <!-- EN --> and end after the last 來源 entry
- Do NOT include any preamble, explanation, reasoning, log, verification report, or commentary
- Do NOT write anything before <!-- EN --> or after the last 來源 section
- Modify only headlines, their citations, and the Sources / 來源 sections — do NOT change Analysis / 分析
- Keep the exact same <!-- EN --> and <!-- ZH --> block structure
- If a headline has no inline citation, skip it (do not remove it)"""

MAX_VERIFIER_TOOL_CALLS = 40
VERIFIER_MAX_TOKENS = 16000


def _final_text(response) -> str:
    """Return the response's summary text, or "" if the output was cut off by max_tokens."""
    if response.stop_reason == "max_tokens":
        print("Warning: verifier output hit max_tokens and was truncated", file=sys.stderr)
        return ""
    text = "".join(block.text for block in response.content if hasattr(block, "text"))
    return _extract_bilingual_summary(text) if text else ""


def _extract_bilingual_summary(text: str) -> str:
    """Strip any preamble/postamble — return only the <!-- EN --> ... block."""
    # Use the LAST marker: if the model wrote drafts before its final answer, keep the final one.
    marker = "<!-- EN -->"
    idx = text.rfind(marker)
    if idx == -1:
        return text
    return text[idx:].strip()


def run_verifier(summary: str, today_date: str, known: list[str] | None = None) -> str:
    client = anthropic.Anthropic()

    system = VERIFIER_SYSTEM_PROMPT + f"\n\nToday's date is {today_date} (UTC)." + known_stories_prompt(known)

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
            max_tokens=VERIFIER_MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason in ("end_turn", "max_tokens"):
            return _final_text(response)

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
            return _final_text(response)

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
                max_tokens=VERIFIER_MAX_TOKENS,
                system=system,
                tools=TOOLS,
                tool_choice={"type": "none"},
                messages=messages,
            )
            return _final_text(final)


def verify_summary(summary: str, today_date: str, known: list[str] | None = None) -> str:
    try:
        result = run_verifier(summary, today_date, known)
        if not result:
            print("Warning: verifier returned empty output, using original summary", file=sys.stderr)
            return summary
        return result
    except Exception as e:
        print(f"Warning: verifier failed: {e}", file=sys.stderr)
        return summary
