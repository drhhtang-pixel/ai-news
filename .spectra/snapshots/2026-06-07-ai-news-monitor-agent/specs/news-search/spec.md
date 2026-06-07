# news-search

Autonomous web search loop in which Claude decides which queries to execute, calls the Tavily `web_search` tool iteratively, and accumulates results until it has sufficient coverage to produce a final answer.

## Overview

- **Module**: `agent.py` + `tools.py`
- **Model**: `claude-sonnet-4-6`
- **Search backend**: Tavily Python SDK (`TavilyClient`, `search_depth="basic"`)
- **Tool name**: `web_search` — schema: `{ query: string }` → returns formatted string of results

## Requirements

### Requirement: Agent drives search strategy autonomously

The agent SHALL determine which search queries to execute without human input, based solely on the configured search topic.

#### Scenario: Agent performs multiple searches

- **WHEN** the agent is invoked with a search topic
- **THEN** it SHALL call the `web_search` tool at least once and up to 10 times before producing a final answer

##### Example: typical run

- **GIVEN** `SEARCH_TOPIC=AI news today`
- **WHEN** the agent starts
- **THEN** Claude calls `web_search` with queries such as "AI news today", "latest AI research 2026", "AI product releases this week" before generating the summary

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

### Requirement: Tool execution errors are non-fatal

The agent SHALL continue the loop if a single `web_search` call fails, passing the error string back to Claude as the tool result.

#### Scenario: Tavily returns an error

- **WHEN** a `web_search` call raises an exception
- **THEN** the agent SHALL pass `"Error: <exception message>"` as the `tool_result` content
- **THEN** the agent SHALL NOT exit or raise

## Implementation Notes

- `TOOLS` list and `execute_tool(name, input) -> str` dispatcher are defined in `tools.py`
- The loop in `agent.py` tracks `tool_call_count`; when it reaches `MAX_TOOL_CALLS = 10`, a follow-up API call with no tools is issued to force `end_turn`
- Each Tavily result item is formatted as `**{title}**\n{content}\nURL: {url}`; items are joined with double newlines
- Unknown tool names return `"Error: Unknown tool '{name}'"` — treated as a non-fatal error by the loop
