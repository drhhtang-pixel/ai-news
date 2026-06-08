## ADDED Requirements

### Requirement: Search results are filtered to the past 24 hours

The `web_search` tool SHALL pass `days=1` to the Tavily API on every call, restricting results to articles published or indexed within the past 24 hours.

#### Scenario: Recency filter is applied on every search

- **WHEN** `execute_tool("web_search", {"query": "..."})` is called
- **THEN** the Tavily client SHALL be invoked with `days=1` alongside `search_depth="basic"`
- **THEN** articles older than 24 hours SHALL NOT appear in the returned results

##### Example: parameter presence

| Call | Expected Tavily parameters |
|---|---|
| `execute_tool("web_search", {"query": "AI news 2026-06-08"})` | `query="AI news 2026-06-08"`, `search_depth="basic"`, `days=1` |

---

## MODIFIED Requirements

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
