import sys
import anthropic
from knowledge import apply_verification, known_stories_prompt
from tools import TOOLS, execute_tool, log_tool_call

VERIFIER_SYSTEM_PROMPT = """You are a news source verifier. You receive a bilingual AI news summary (English and Chinese). Your job is to check that each EN headline is supported by the CONTENT of the sources it cites. Publication dates are NOT a reason to keep or remove anything: one story may be reported by several sources on different dates, and that is fine.

Your task:
1. Number the headlines under "### Headlines" in the <!-- EN --> block 1, 2, 3, ... in order. For each one, read its inline citation *(Sources: Name, Date; ...)* and find each cited source's URL in the Sources section.
2. Call extract_url on each cited URL and check:
   - The URL resolves to an actual article (not a homepage, index page, video page, or error page)
   - The article content actually reports the facts stated in the headline and its description
3. Keep a source only if it supports the headline. Keep at most 3 sources per headline — the ones that best support it. Use the "Published:" value returned by the tool as its date ("unknown" if the tool says unknown). Never guess a date.
4. If a headline has no supporting source left, call web_search to find an article that reports the same story and confirm it with extract_url. If none is found, remove the headline.
5. Remove a headline if its story is in the ALREADY PUBLISHED list below (same event, even if worded differently), or if its description states something important that no source supports.
6. When you have checked every headline, call submit_verification exactly ONCE with one decision per headline. Do not write the summary yourself — the program rebuilds it from your decisions."""

SUBMIT_TOOL = {
    "name": "submit_verification",
    "description": (
        "Submit the final verification result: one decision per EN headline, numbered from 1 in the "
        "order they appear. Call this once, after all checks are done."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "headlines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "1-based position of the EN headline"},
                        "action": {"type": "string", "enum": ["keep", "remove"]},
                        "reason": {"type": "string", "description": "One short sentence"},
                        "sources": {
                            "type": "array",
                            "description": "Supporting sources to cite (max 3); empty when removing",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Publication name"},
                                    "url": {"type": "string"},
                                    "date": {"type": "string", "description": "YYYY-MM-DD from the tool, or 'unknown'"},
                                },
                                "required": ["name", "url", "date"],
                            },
                        },
                    },
                    "required": ["index", "action", "reason", "sources"],
                },
            }
        },
        "required": ["headlines"],
    },
}

VERIFIER_TOOLS = TOOLS + [SUBMIT_TOOL]
MAX_VERIFIER_TOOL_CALLS = 40
# Decisions are small, but stream with a generous limit as a safety net against long replies.
VERIFIER_MAX_TOKENS = 32000


def _call(client, **kwargs):
    with client.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def _submitted(response) -> list[dict] | None:
    for block in response.content:
        if block.type == "tool_use" and block.name == SUBMIT_TOOL["name"]:
            return block.input.get("headlines") or []
    return None


def _log_decisions(decisions: list[dict]) -> None:
    for d in decisions:
        print(f"  [verifier] #{d.get('index')} {d.get('action')}: {str(d.get('reason', ''))[:120]}")


def run_verifier(summary: str, today_date: str, known: list[str] | None = None) -> str:
    """Return the summary with the verifier's decisions applied, or "" if it never submitted any."""
    client = anthropic.Anthropic()
    system = VERIFIER_SYSTEM_PROMPT + f"\n\nToday's date is {today_date} (UTC)." + known_stories_prompt(known)
    messages = [{"role": "user", "content": f"Please verify the following news summary.\n\n{summary}"}]
    request = dict(model="claude-sonnet-4-6", max_tokens=VERIFIER_MAX_TOKENS, system=system,
                   tools=VERIFIER_TOOLS)
    tool_call_count = 0

    while True:
        response = _call(client, messages=messages, **request)
        messages.append({"role": "assistant", "content": response.content})

        decisions = _submitted(response)
        if decisions is not None:
            _log_decisions(decisions)
            return apply_verification(summary, decisions)

        if response.stop_reason == "max_tokens":
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            print(f"Warning: verifier hit max_tokens without submitting; it wrote: {text[:300]!r}", file=sys.stderr)
            return ""

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_call_count += 1
                result = execute_tool(block.name, block.input)
                log_tool_call("verifier", block.name, block.input, result)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        if not tool_results or tool_call_count >= MAX_VERIFIER_TOOL_CALLS:
            # Stopped without submitting, or out of budget: force the decisions now.
            note = ("You have reached the maximum number of tool calls. " if tool_results else "") + \
                "Call submit_verification now with your decisions so far."
            messages.append({"role": "user", "content": note})
            final = _call(client, messages=messages, **request,
                          tool_choice={"type": "tool", "name": SUBMIT_TOOL["name"]})
            decisions = _submitted(final)
            if decisions is None:
                print("Warning: verifier did not submit decisions", file=sys.stderr)
                return ""
            _log_decisions(decisions)
            return apply_verification(summary, decisions)


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
