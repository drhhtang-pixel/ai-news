import os
import sys
import anthropic
from tools import TOOLS, execute_tool
from writer import append_summary

SYSTEM_PROMPT = """You are an AI news monitor. Your job is to search the web for the latest AI news and produce a bilingual structured summary in both English and Traditional Chinese.

Use the web_search tool to find current AI news, research papers, product launches, and notable developments. Run multiple targeted searches to get comprehensive coverage — vary your queries to cover different angles.

When you have gathered enough information, write your final answer using EXACTLY this format — the HTML comment markers are required:

<!-- EN -->
### Headlines
A bullet list of the most important news items with one-sentence descriptions.

### Analysis
2-3 paragraphs analyzing key trends and implications.

### Sources
A list of sources you found, with URLs.

<!-- ZH -->
### 頭條新聞
以繁體中文列出最重要的新聞，每條一句話說明。

### 分析
2-3段繁體中文分析，說明主要趨勢與影響。

### 來源
列出所有來源網站及其網址。

IMPORTANT: You MUST include both <!-- EN --> and <!-- ZH --> blocks in your response, in that order. Do not omit either block."""

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


def run_agent(search_topic: str) -> str:
    client = anthropic.Anthropic()

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
            max_tokens=4096,
            system=SYSTEM_PROMPT,
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
            # stop_reason was tool_use but no tool_use blocks found — exit safely
            break

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
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            for block in final.content:
                if hasattr(block, "text"):
                    return block.text
            return ""


def main() -> None:
    _, _, search_topic, output_file = validate_env()
    print(f"Searching for: {search_topic}")
    summary = run_agent(search_topic)
    append_summary(summary, output_file)


if __name__ == "__main__":
    main()
