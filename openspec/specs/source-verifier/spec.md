# source-verifier Specification

## Purpose

TBD - created by archiving change 'strengthen-summary-accuracy'. Update Purpose after archive.

## Requirements

### Requirement: Verifier validates each headline's source URL

For each headline in the `<!-- EN -->` block that contains an inline citation, the verifier SHALL call `extract_url` on the cited URL to confirm it resolves to an actual article page.

#### Scenario: Valid article URL

- **WHEN** `extract_url(url)` returns content for a headline's cited URL
- **THEN** the verifier SHALL retain that headline unchanged

#### Scenario: URL does not resolve or returns an error

- **WHEN** `extract_url(url)` returns an error string
- **THEN** the verifier SHALL attempt to find a replacement source via `web_search`

##### Example: URL validation outcomes

| extract_url result | Action |
|---|---|
| Article content returned | Keep headline |
| `"Error: ..."` | Attempt web_search for replacement |
| Empty content | Attempt web_search for replacement |

---
### Requirement: Verifier checks that each cited source supports the headline

For each headline, the verifier SHALL check every cited source (at most 3 kept per headline) by content: the article must exist and must report the facts stated in the headline and its description. Publication dates SHALL NOT be a reason to keep or remove a source or headline; one story MAY be supported by several sources published on different dates. Each kept source's date SHALL be the `Published:` value returned by `extract_url`, or "date unknown" when the tool reports `unknown`.

#### Scenario: Source supports the headline

- **WHEN** `extract_url` returns article content that reports the headline's facts
- **THEN** the verifier SHALL keep the source and show its date from the tool result

#### Scenario: Source does not support the headline

- **WHEN** the article content does not report the headline's facts, or the URL fails
- **THEN** the verifier SHALL drop that source from the headline's citation

#### Scenario: Description overstates the sources

- **WHEN** the headline's description states something no kept source supports
- **THEN** the verifier SHALL correct the description to match the sources instead of removing the headline

##### Example: content check decision table

| Source content | Published | Action |
|---|---|---|
| Reports the story | `2026-10-18` | Keep, cite `2026-10-18` |
| Reports the story | `2026-10-12` | Keep, cite `2026-10-12` |
| Reports the story | `unknown` | Keep, cite "date unknown" |
| Different story / homepage / error | any | Drop this source |

---
### Requirement: Verifier attempts repair before removal

When a headline has no supporting source left, the verifier SHALL search for an article that reports the same story before removing the headline.

#### Scenario: Replacement found

- **WHEN** `web_search` and `extract_url` find an article that reports the story
- **THEN** the verifier SHALL cite it with its name and the date from the tool result

#### Scenario: No replacement found

- **WHEN** no article reporting the story is found
- **THEN** the verifier SHALL remove the headline from the summary entirely

#### Scenario: Sources section is rebuilt

- **WHEN** verification finishes
- **THEN** the Sources / 來源 sections SHALL list exactly the sources still cited by headlines, each as `- Name: URL (published YYYY-MM-DD)` or `(published date unknown)`
- **THEN** the Analysis / 分析 sections SHALL be unchanged

#### Scenario: Verifier output is cut off

- **WHEN** the verifier's response stops with `stop_reason == "max_tokens"` (limit `VERIFIER_MAX_TOKENS = 16000`)
- **THEN** the verifier SHALL treat the output as empty, so `verify_summary` falls back to the writer's draft with a warning
- **WHEN** the response contains several `<!-- EN -->` drafts
- **THEN** only the text from the last `<!-- EN -->` marker SHALL be used

---
### Requirement: Verifier tool call loop is bounded

The verifier's tool-use loop SHALL terminate after at most 40 tool calls.

#### Scenario: Guard triggers

- **WHEN** the number of tool calls reaches 40
- **THEN** the loop SHALL exit and return the verified/repaired state accumulated so far
- **THEN** the final API call SHALL pass `tools=TOOLS` and `tool_choice={"type": "none"}` (keeps the tool definitions consistent with the `tool_use` blocks in the history while forbidding further tool calls)

##### Example: guard boundary

| Tool calls made | Action |
|---|---|
| 12 | Continue verifying |
| 40 | Exit loop, return current state |

---
### Requirement: Verifier failure is non-fatal

If the verifier encounters an unhandled exception or produces no valid output, it SHALL return the original unmodified summary and print a warning to stderr.

#### Scenario: Verifier crashes

- **WHEN** an unhandled exception occurs in `verify_summary()`
- **THEN** the function SHALL catch it, print `"Warning: verifier failed: <error>"` to stderr
- **THEN** the function SHALL return the original `summary` string unchanged

##### Example: safe fallback

- **GIVEN** Tavily API key is invalid
- **WHEN** `verify_summary()` is called
- **THEN** the original summary is returned unchanged and stderr contains `"Warning: verifier failed: ..."`

---
### Requirement: ZH headlines are updated to match EN verification results

After EN headlines are verified and repaired, the verifier SHALL apply the same citation updates and removals to the corresponding `<!-- ZH -->` block.

#### Scenario: EN headline updated

- **WHEN** an EN headline's citation URL is replaced with a valid one
- **THEN** the corresponding ZH headline (same position) SHALL use the same updated URL

#### Scenario: EN headline removed

- **WHEN** an EN headline is removed because no valid source was found
- **THEN** the ZH headline at the same list position SHALL also be removed

---
### Requirement: extract_url returns up to 1,000 characters of article content

The `extract_url` tool SHALL return up to 1,000 characters of `raw_content` from the fetched article, providing sufficient context for the verifier to evaluate article relevance.

#### Scenario: Content truncation limit

- **WHEN** `extract_url` fetches an article with raw content longer than 1,000 characters
- **THEN** the returned content SHALL be truncated to 1,000 characters

#### Scenario: Short article content

- **WHEN** `extract_url` fetches an article with raw content shorter than 1,000 characters
- **THEN** the returned content SHALL not be padded and reflects the full available content

<!-- @trace
source: fix-unknown-date-verification
updated: 2026-06-09
code:
  - cron.log
-->