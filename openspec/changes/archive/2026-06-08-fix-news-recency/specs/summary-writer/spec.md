## ADDED Requirements

### Requirement: System prompt includes today's date and excludes non-current articles

The system prompt passed to Claude SHALL include the execution date in `YYYY-MM-DD` format and SHALL explicitly instruct Claude to report only news from that date, rejecting year-in-review articles, historical summaries, and content published on prior dates.

#### Scenario: System prompt contains today's date

- **WHEN** `run_agent()` is called
- **THEN** the system prompt SHALL contain the current date as a `YYYY-MM-DD` string
- **THEN** the system prompt SHALL instruct Claude to exclude retrospective or year-in-review articles

#### Scenario: Summary reflects current-day news only

- **WHEN** the agent completes a run on date D
- **THEN** the sources listed in the summary SHALL be articles published on date D or at most one calendar day prior
- **THEN** the summary SHALL NOT cite year-in-review or retrospective articles unless they were published on date D

##### Example: date injection

- **GIVEN** the agent runs on 2026-06-08
- **WHEN** the system prompt is assembled
- **THEN** the prompt SHALL contain the string `"2026-06-08"` and a directive such as `"Only report news published on 2026-06-08. Exclude year-in-review articles, historical summaries, and any content not published on this date."`
