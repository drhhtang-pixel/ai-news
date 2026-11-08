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

After verification, `hold_old_stories()` SHALL compute each EN headline's age from the earliest real date among its citation's date fields (`citation_earliest_date()`). Sources are split on `; ` / `；` (a URL never contains "; "), and a source's date field is only a `YYYY-MM-DD` that ENDS the source right after its last comma, as the program writes citations (`[name](url), date` / `name, date`). This guarantee holds for citations built by `apply_verification`: every source passes `_clean_source`, which replaces `;`/`；` in names with `, ` and rejects URLs containing whitespace or `；`, so no source can fake a separator. For those citations, dates inside source names or URLs never count, whatever the URL's shape (nested parentheses, commas in the name or query), and a source whose link could not be parsed still contributes its trailing date field. Hand-written or legacy plain citations whose bare name or URL itself ends in `, YYYY-MM-DD` without a date field are ambiguous and not covered. If that date is more than `MAX_STORY_AGE_DAYS` days before today (UTC), the headline SHALL be removed from the summary, together with the ZH headline at the same position and the Sources / 來源 entries (matched by URL) cited only by held headlines. A headline with no dated source SHALL be kept.

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

When any story is held, `main()` SHALL write `format_held()` Markdown to `HELD_FILE` (default `held_stories.md`, git-ignored). In GitHub Actions, `HELD_FILE` SHALL be in the runner temp directory, and the step "Ask the manager to review stories older than a month" SHALL open a GitHub issue with that file as its body. That step SHALL run even if the agent step failed afterwards (`if: ${{ !cancelled() }}`; skipped when the run is cancelled), and SHALL do nothing when the file is missing or empty. The `issues: write` permission SHALL be granted to the summarize job only.

#### Scenario: Issue content

- **WHEN** stories are held
- **THEN** the issue SHALL list each held story's title, earliest cited source date, sources with dates and URLs, and the full headline line, and state that the stories were not published

Held stories' URLs SHALL come from their linked citations. Plain citations (only possible if a writer draft reaches this step, e.g. in tests) fall back to the Sources section, matching the exact publication name (optionally followed by a parenthesised note) and preferring the cited date; when several entries still match, no URL is guessed.

## Known limitations

- Age is approximated by the earliest dated source; the event itself may be older.
- Age is the earliest date among the (at most 3) cited sources, not among every source found.
- The "already published" check is semantic and done by the models; it is not enforced in code.
