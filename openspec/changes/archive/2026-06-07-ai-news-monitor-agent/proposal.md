## Why

Staying current with AI developments is time-consuming and requires constant manual effort. An autonomous agent can monitor AI news on a schedule, search and synthesize results automatically, and persist summaries without any human intervention.

## What Changes

- New Python agent script that runs the Claude tool-use loop autonomously
- Web search integration via Tavily API to find current AI news
- Markdown file output for persisting daily summaries
- Cron-based scheduling via a shell script entry point
- Configuration via environment variables (API keys, search topics, output path)

## Capabilities

### New Capabilities

- `news-search`: Autonomous web search loop — Claude decides which queries to run and calls the Tavily search tool iteratively until sufficient coverage is achieved
- `summary-writer`: Structured AI news summarization — Claude synthesizes search results into a dated Markdown summary with sections for headlines, analysis, and sources
- `scheduler-entrypoint`: Cron-compatible entry point — a Python script that can be invoked by system cron or any task scheduler with no interactive input required

### Modified Capabilities

(none)

## Impact

- Affected specs: news-search, summary-writer, scheduler-entrypoint
- Affected code:
  - New: agent.py
  - New: tools.py
  - New: writer.py
  - New: run.sh
  - New: requirements.txt
  - New: .env.example
