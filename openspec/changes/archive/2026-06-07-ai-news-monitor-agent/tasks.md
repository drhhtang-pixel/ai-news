## 1. Project Setup

- [x] 1.1 Create requirements.txt listing `anthropic` and `tavily-python` as dependencies so the project can be installed with `pip install -r requirements.txt` without errors. Verify by running `pip install -r requirements.txt` in a clean venv.
- [x] 1.2 Create .env.example documenting all four configuration environment variables (`ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SEARCH_TOPIC`, `OUTPUT_FILE`) with placeholder values and inline comments. Verify by reading the file and confirming all variables are present.

## 2. Tool Layer

- [x] 2.1 Implement `tools.py` with a `TOOLS` list containing the `web_search` tool definition (JSON schema: `{ query: string }`) and an `execute_tool(name, input) -> str` dispatcher that calls the Tavily client — this satisfies "Use Tavily for web search". Verify by calling `execute_tool("web_search", {"query": "AI news"})` with a valid `TAVILY_API_KEY` and confirming a non-empty string is returned.
- [x] 2.2 Add exception handling in `execute_tool` so that tool execution errors are non-fatal: any exception is caught and returned as `"Error: <exception message>"` without raising. Verify by temporarily passing an invalid key and confirming the function returns an error string instead of raising.

## 3. Agent Loop

- [x] 3.1 Implement the agentic loop in `agent.py` using the direct Anthropic SDK tool-use loop (no framework): send initial prompt with `tools=TOOLS` to `claude-sonnet-4-6`, iterate on `tool_use` stop reason by executing tools and appending `tool_result` blocks, exit on `end_turn` — this satisfies "Agent drives search strategy autonomously". Verify by running `python agent.py` with valid API keys and confirming a summary text is returned.
- [x] 3.2 Add a loop iteration counter that enforces "Search loop terminates with a guard": exit the loop and proceed to summary generation after 10 tool calls even if `stop_reason` is still `tool_use`. Verify by inspecting the counter logic and confirming the guard constant is 10.
- [x] 3.3 Validate environment at startup so that "Configuration is read from environment variables" and "Agent exits cleanly with a status code": read `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SEARCH_TOPIC` (default: `"AI news today"`), and `OUTPUT_FILE` (default: `"summaries.md"`); print an error to stderr and `sys.exit(1)` if either API key is missing. Verify by unsetting `ANTHROPIC_API_KEY` and running `python agent.py`; confirm exit code is 1 and stderr contains `Error: ANTHROPIC_API_KEY is not set`.

## 4. Summary Writer

- [x] 4.1 Implement `writer.py` with `append_summary(text: str, output_file: str) -> None` that prepends a `## YYYY-MM-DD HH:MM` header and appends the content to the output file, creating it if absent — this satisfies "Summary is appended to output file with a date header" and implements the Markdown append-only output design decision. Verify by calling `append_summary` twice and confirming two dated sections appear in the output file.
- [x] 4.2 Add a system prompt in `agent.py` instructing Claude to structure its final answer as Markdown with `### Headlines`, `### Analysis`, and `### Sources` sections — this satisfies "Summary is structured Markdown". Verify by running the agent end-to-end and inspecting the written file for all three headings.
- [x] 4.3 Add a `print(f"Summary written to {output_file}")` call in `append_summary` after a successful write — this satisfies "Successful write is reported to stdout". Verify by running the agent and confirming the message appears in stdout.

## 5. Scheduling Entry Point

- [x] 5.1 Create `run.sh` implementing the System cron for scheduling design decision: sources `.env` if the file exists in the same directory, then calls `python agent.py`, and includes a commented example crontab line for daily execution at 08:00 — this satisfies "run.sh provides a cron-compatible wrapper". Verify by reviewing `run.sh` content for the crontab comment and running `bash run.sh` with a valid `.env` file.
