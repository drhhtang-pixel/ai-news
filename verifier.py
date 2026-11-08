import sys
import anthropic
from knowledge import InvalidDecisions, apply_verification, headline_items, known_stories_prompt
import tools
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


def _submission(response):
    """The submit_verification tool_use block in the response, if any."""
    return next((b for b in response.content if b.type == "tool_use" and b.name == SUBMIT_TOOL["name"]), None)


def _apply_tool_dates(decisions):
    """Dates come from tool evidence only: the earliest date a tool returned for each URL during
    this run (tools.tool_date), never the model's own value. A URL no tool dated is 'unknown'."""
    if not isinstance(decisions, list):
        return decisions
    for d in decisions:
        sources = d.get("sources") if isinstance(d, dict) else None
        if not isinstance(sources, list):
            continue  # malformed; check_decisions rejects it and asks for a resubmission
        for src in sources:
            if isinstance(src, dict):
                src["date"] = tools.tool_date(str(src.get("url") or "")) or "unknown"
    return decisions


def _log_decisions(decisions: list[dict]) -> None:
    for d in decisions:
        print(f"  [verifier] #{d.get('index')} {d.get('action')}: {str(d.get('reason', ''))[:120]}")


def run_verifier(summary: str, today_date: str, known: list[str] | None = None) -> str:
    """Return the summary with the verifier's decisions applied, or "" if verification did not
    complete (no valid submission, or EN/ZH headlines that do not line up)."""
    en, zh = headline_items(summary)
    if len(en) != len(zh):
        print(f"Warning: draft has {len(en)} EN but {len(zh)} ZH headlines; cannot verify safely", file=sys.stderr)
        return ""
    client = anthropic.Anthropic()
    system = VERIFIER_SYSTEM_PROMPT + f"\n\nToday's date is {today_date} (UTC)." + known_stories_prompt(known)
    messages = [{"role": "user", "content": f"Please verify the following news summary.\n\n{summary}"}]
    request = dict(model="claude-sonnet-4-6", max_tokens=VERIFIER_MAX_TOKENS, system=system,
                   tools=VERIFIER_TOOLS)
    force_submit = {"tool_choice": {"type": "tool", "name": SUBMIT_TOOL["name"]}}
    tool_call_count = 0
    resubmissions_left = 1
    forced = False

    response = _call(client, messages=messages, **request)
    while True:
        tools.record_usage("verifier", response)
        messages.append({"role": "assistant", "content": response.content})

        submission = _submission(response)
        if submission is not None:
            decisions = _apply_tool_dates(submission.input.get("headlines"))
            try:
                result = apply_verification(summary, decisions)
            except InvalidDecisions as e:
                print(f"Warning: verifier decisions rejected: {e}", file=sys.stderr)
                if not resubmissions_left:
                    return ""
                resubmissions_left -= 1
                # Every tool_use in this reply needs a result: reject each submission and run any
                # research calls that came with it.
                rejection = (f"Rejected: {e}. Call submit_verification again with exactly one decision "
                             f"for each headline 1..{len(en)}.")
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    if block.name == SUBMIT_TOOL["name"]:
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "is_error": True, "content": rejection})
                    else:
                        tool_call_count += 1
                        output = execute_tool(block.name, block.input)
                        log_tool_call("verifier", block.name, block.input, output)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
                messages.append({"role": "user", "content": results})
                forced = True
                response = _call(client, messages=messages, **request, **force_submit)
                continue
            _log_decisions(decisions)
            return result

        if forced:
            print("Warning: verifier did not submit decisions", file=sys.stderr)
            return ""
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
            forced = True
            response = _call(client, messages=messages, **request, **force_submit)
        else:
            response = _call(client, messages=messages, **request)


def verify_summary(summary: str, today_date: str, known: list[str] | None = None) -> tuple[str, bool]:
    """(summary, verified). On any verifier failure, the unverified draft and False."""
    try:
        result = run_verifier(summary, today_date, known)
        if not result:
            print("Warning: verifier returned empty output, using original summary", file=sys.stderr)
            return summary, False
        return result, True
    except Exception as e:
        print(f"Warning: verifier failed: {e}", file=sys.stderr)
        return summary, False
