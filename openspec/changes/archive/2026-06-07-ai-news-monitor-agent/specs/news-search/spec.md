## ADDED Requirements

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
