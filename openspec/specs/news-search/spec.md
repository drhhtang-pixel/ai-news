# news-search

Autonomous web search loop in which Claude decides which queries to execute, calls the Tavily `web_search` tool iteratively, and accumulates results until it has sufficient coverage to produce a final answer.

## Overview

- **Module**: `agent.py` + `tools.py`
- **Model**: `claude-sonnet-4-6`
- **Search backend**: Tavily Python SDK (`TavilyClient`, `search_depth="basic"`)
- **Tool name**: `web_search` — schema: `{ query: string }` → returns formatted string of results

## Requirements

### Requirement: Agent drives search strategy autonomously

The agent SHALL determine which search queries to execute without human input, based solely on the configured search topic. The default search topic SHALL include today's date in `YYYY-MM-DD` format to anchor queries to the current day.

#### Scenario: Agent performs multiple searches

- **WHEN** the agent is invoked with a search topic
- **THEN** it SHALL call the `web_search` tool at least once and up to 10 times before producing a final answer

##### Example: typical run

- **GIVEN** the agent runs on 2026-06-08 with default `SEARCH_TOPIC`
- **WHEN** the agent starts
- **THEN** the resolved search topic SHALL be `"AI news 2026-06-08"`
- **THEN** Claude calls `web_search` with queries derived from that topic, e.g. `"AI news 2026-06-08"`, `"latest AI product launches June 8 2026"`, `"AI research announcements 2026-06-08"`

---
### Requirement: Search loop terminates with a guard

The agent SHALL stop the tool-use loop after 10 tool calls even if Claude has not yet reached `end_turn`, to prevent runaway API usage.

#### Scenario: Guard triggers on excessive tool calls

- **WHEN** the number of tool calls in a single run reaches 10
- **THEN** the loop SHALL exit and the agent SHALL use whatever results have been collected to generate the summary

##### Example: guard boundary

| Tool calls made | stop_reason | Action |
|---|---|---|
| 5 | tool_use | Continue loop |
| 10 | tool_use | Exit loop, proceed to summary |
| 3 | end_turn | Exit loop normally |

---
### Requirement: Tool execution errors are non-fatal

The agent SHALL continue the loop if a single `web_search` call fails, passing the error string back to Claude as the tool result.

#### Scenario: Tavily returns an error

- **WHEN** a `web_search` call raises an exception
- **THEN** the agent SHALL pass `"Error: <exception message>"` as the `tool_result` content
- **THEN** the agent SHALL NOT exit or raise

---
### Requirement: extract_url tool is available for URL content retrieval

The `tools.py` module SHALL define an `extract_url` tool that fetches the content of a specific URL using the Tavily extract API.

#### Scenario: Successful URL extraction

- **WHEN** `execute_tool("extract_url", {"url": "https://example.com/article"})` is called
- **THEN** the function SHALL call `TavilyClient.extract(urls=["https://example.com/article"])`
- **THEN** the function SHALL return a formatted string containing the article title, a content excerpt, the published date (if available), and the URL

#### Scenario: URL extraction fails

- **WHEN** `TavilyClient.extract()` raises an exception
- **THEN** `execute_tool` SHALL return `"Error: <exception message>"`
- **THEN** the caller SHALL NOT receive an exception

##### Example: extract_url tool schema and return format

- **GIVEN** tool name `"extract_url"` with input `{"url": "https://techcrunch.com/2026/06/08/article"}`
- **THEN** the tool is defined in `TOOLS` with input schema:
  ```json
  {
    "type": "object",
    "properties": {
      "url": { "type": "string", "description": "The URL of the article to extract" }
    },
    "required": ["url"]
  }
  ```
- **THEN** a successful call returns a string in this format:
  ```
  **[Article Title]**
  [Content excerpt]
  Published: [date or "unknown"]
  URL: [url]
  ```

---
### Requirement: Search uses Tavily news mode and returns publication dates

The `web_search` tool SHALL call Tavily with `topic="news"` and `days=2` (Tavily applies `days` only in news mode), so results cover the 24-hour freshness window (UTC yesterday and today) regardless of when the run starts. Each result SHALL include a `Published:` line with a `YYYY-MM-DD` date resolved by the same layered logic as `extract_url` (Tavily field → URL path → content scan → `"unknown"`).

#### Scenario: Recency filter and dates on every search

- **WHEN** `execute_tool("web_search", {"query": "..."})` is called
- **THEN** the Tavily client SHALL be invoked with `search_depth="basic"`, `topic="news"`, `days=2`
- **THEN** each result SHALL be formatted as `**{title}**\n{content}\nPublished: {date}\nURL: {url}`

##### Example: date resolution in search results

| Tavily `published_date` | URL | `Published:` |
|---|---|---|
| `"Tue, 14 Oct 2026 12:00:00 GMT"` | any | `2026-10-14` |
| missing | `https://b.com/2026/10/13/story` | `2026-10-13` |
| missing | `https://c.com/story` (no date in content) | `unknown` |

---

## Implementation Notes

- `TOOLS` list and `execute_tool(name, input) -> str` dispatcher are defined in `tools.py`
- The loop in `agent.py` tracks `tool_call_count`; when it reaches `MAX_TOOL_CALLS = 10`, a follow-up API call is issued with `tools=TOOLS` and `tool_choice={"type": "none"}` to force a text answer (the tools must still be declared because the history contains `tool_use` blocks)
- Each Tavily result item is formatted as `**{title}**\n{content}\nPublished: {date}\nURL: {url}`; items are joined with double newlines
- Unknown tool names return `"Error: Unknown tool '{name}'"` — treated as a non-fatal error by the loop
