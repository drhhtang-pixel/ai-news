## Context

This is a greenfield Python project. There is no existing codebase. The agent runs autonomously on a schedule, uses the Anthropic SDK tool-use loop to decide which web searches to perform, and appends a structured summary to a local Markdown file.

External dependencies:
- Anthropic SDK (`anthropic`) — Claude tool-use API
- Tavily Python SDK (`tavily-python`) — web search returning LLM-ready content
- Python 3.12 (already available on the target machine)

## Goals / Non-Goals

**Goals:**
- Autonomous agent loop: Claude drives the search strategy without human input
- Configurable topic via environment variable (defaults to "AI news")
- Append-only Markdown output with date headers
- Cron-compatible invocation — no interactive input, exits cleanly

**Non-Goals:**
- No web UI or API endpoint
- No database storage (flat file only)
- No email/Slack alerting
- No multi-topic parallel runs in a single invocation
- No deduplication across runs

## Decisions

### Use Tavily for web search

Tavily is designed for agentic use — it returns pre-processed, LLM-ready summaries rather than raw HTML. Alternatives considered:

| Option | Pros | Cons |
|---|---|---|
| Tavily | Agent-optimized output, Python SDK, free tier | Paid above free tier |
| Brave Search | Cheap, raw results | Requires HTML parsing |
| SerpAPI | Google results | Expensive, raw HTML |

Tavily wins because it reduces prompt token usage and parsing complexity.

### Direct Anthropic SDK tool-use loop (no framework)

Avoid LangChain, CrewAI, or other agent frameworks. The loop is simple enough to implement in ~50 lines. Frameworks add abstraction complexity and version-pinning risk.

The loop pattern:
1. Send initial prompt + tool definitions to Claude
2. If response contains `tool_use` blocks, execute each tool, collect results
3. Append tool results as `tool_result` blocks and call the API again
4. Stop when `stop_reason == "end_turn"`

### Markdown append-only output

Each run appends a `## YYYY-MM-DD HH:MM` section to `summaries.md`. No database, no migration, no schema. The file is human-readable and grep-able.

### System cron for scheduling

`run.sh` exports environment variables and calls `python agent.py`. The user adds a crontab entry. No daemon, no Python scheduler, no persistent process.

## Implementation Contract

**Entry point behavior:**
- `python agent.py` runs the full agent loop and exits 0 on success, non-zero on failure
- All errors are printed to stderr; normal output (summary written) goes to stdout
- The script reads `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SEARCH_TOPIC` (default: "AI news today"), and `OUTPUT_FILE` (default: `summaries.md`) from environment

**Tool definitions (`tools.py`):**
- Exports a single `TOOLS` list containing one tool: `web_search`
- `web_search` schema: `{ query: string }` → returns string (Tavily result)
- Exports `execute_tool(name, input) -> str` dispatcher function

**Agent loop (`agent.py`):**
- Calls `anthropic.messages.create` with model `claude-sonnet-4-6`, `tools=TOOLS`, and an initial user message instructing it to search for AI news
- Loops on `tool_use` stop reason: extracts tool calls, executes via `execute_tool`, appends `tool_result` content blocks, and calls the API again
- Exits the loop when `stop_reason == "end_turn"`
- Extracts the final text response and passes it to `writer.py`

**Summary writer (`writer.py`):**
- Exports `append_summary(text: str, output_file: str) -> None`
- Prepends a `## YYYY-MM-DD HH:MM` header to the text
- Appends to `output_file`, creating it if it does not exist
- A successful write prints: `Summary written to <output_file>`

**Cron entry point (`run.sh`):**
- Sources `.env` file if present (for local dev)
- Calls `python agent.py`
- Sample crontab line included as a comment in the file

**Acceptance criteria:**
- Running `python agent.py` with valid API keys produces a dated section appended to `summaries.md`
- Running with a missing `ANTHROPIC_API_KEY` exits non-zero and prints an error to stderr
- Running twice in the same day appends two dated sections (no dedup)

**Scope boundaries:**
- In scope: agent.py, tools.py, writer.py, run.sh, requirements.txt, .env.example
- Out of scope: tests, CI configuration, deployment scripts, deduplication logic

## Risks / Trade-offs

- [Tavily free tier limit (1000 searches/month)] → Mitigation: Claude typically calls search 3–5 times per run; at daily frequency, ~150 searches/month — well within free tier
- [Claude may search excessively in a loop] → Mitigation: Set `max_tokens` and add a max-iteration guard (stop after 10 tool calls)
- [API key exposure in .env file] → Mitigation: .env is listed in .env.example; document that .env must not be committed
