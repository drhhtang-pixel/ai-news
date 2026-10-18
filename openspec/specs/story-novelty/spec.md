# story-novelty Specification

## Purpose

Decide what counts as news for this monitor. Per 唐老師 (2026-10-18), "new" means new to the monitor's knowledge, not new in time: a story the monitor has not published may be reported even if it happened weeks ago, but a story older than one month needs the manager's judgement before it is published.

## Overview

- **Module**: `knowledge.py`, called from `agent.py` `main()`
- **Constants**: `KNOWN_HISTORY_DAYS = 45`, `MAX_STORY_AGE_DAYS = 30`

## Requirements

### Requirement: Already-published stories are not reported again

Before searching, `main()` SHALL read the EN headline titles published in the last `KNOWN_HISTORY_DAYS` days from the output file (`known_headlines()`), newest first, and pass them to both the writer and the verifier (`known_stories_prompt()`). The writer SHALL NOT report those stories; the verifier SHALL remove any headline that reports one of them, even if worded differently.

#### Scenario: Story already published

- **WHEN** a story's title appears in the known list
- **THEN** it SHALL NOT be published again, even with new sources

---
### Requirement: Stories older than one month are held for the manager

After verification, `hold_old_stories()` SHALL compute each EN headline's age from the earliest dated source in its citation. If that date is more than `MAX_STORY_AGE_DAYS` days before today (UTC), the headline SHALL be removed from the summary, together with the ZH headline at the same position and the Sources / 來源 entries (matched by URL) cited only by held headlines. A headline with no dated source SHALL be kept.

#### Scenario: Old story is held

- **WHEN** the earliest dated source of a headline is 2026-09-01 and today is 2026-10-18
- **THEN** the headline SHALL be removed from the published summary and returned in the held list

#### Scenario: Undated story

- **WHEN** every source of a headline is "date unknown"
- **THEN** the headline SHALL be published if it is new to the monitor

##### Example: age decision table (today 2026-10-18)

| Earliest dated source | Action |
|---|---|
| 2026-10-17 | Publish |
| 2026-09-18 (exactly 30 days) | Publish |
| 2026-09-01 | Hold for manager |
| none (all "date unknown") | Publish |

---
### Requirement: The manager is notified of held stories

When any story is held, `main()` SHALL write `format_held()` Markdown to `HELD_FILE` (default `held_stories.md`, git-ignored). In GitHub Actions, `HELD_FILE` SHALL be in the runner temp directory, and the step "Ask the manager to review stories older than a month" SHALL open a GitHub issue with that file as its body. That step SHALL run even if the agent step failed afterwards (`if: always()`), and SHALL do nothing when the file is missing or empty.

#### Scenario: Issue content

- **WHEN** stories are held
- **THEN** the issue SHALL list each held story's title, earliest source date, sources with dates and URLs, and the full headline line, and state that the stories were not published

## Known limitations

- Age is approximated by the earliest dated source; the event itself may be older.
- When a held story and a kept story cite the same publication name, the held story's Sources entry for that publication can remain as a harmless leftover line.
- The "already published" check is semantic and done by the models; it is not enforced in code.
