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
### Requirement: Verifier checks that source was published on today's date

For each headline's cited URL that resolves successfully, the verifier SHALL verify that the article's published date matches `today_date`. If `extract_url` returns `published_date` as `"unknown"`, the verifier SHALL treat this as a date verification failure and attempt to find a replacement source via `web_search`.

#### Scenario: Article published on correct date

- **WHEN** `extract_url` returns content and the publication date matches `today_date`
- **THEN** the verifier SHALL retain the headline

#### Scenario: Article published on wrong date

- **WHEN** `extract_url` returns content but the publication date does not match `today_date`
- **THEN** the verifier SHALL attempt to find a replacement via `web_search`

#### Scenario: Publication date is unknown

- **WHEN** `extract_url` returns content but `published_date` is `"unknown"`
- **THEN** the verifier SHALL treat this as a date verification failure
- **THEN** the verifier SHALL attempt to find a replacement source via `web_search`

##### Example: date check decision table

| published_date returned | Action |
|---|---|
| `"2026-06-09"` (matches today) | Retain headline |
| `"2026-06-07"` (wrong date) | Search for replacement |
| `"unknown"` | Search for replacement |


<!-- @trace
source: fix-unknown-date-verification
updated: 2026-06-09
code:
  - cron.log
-->

---
### Requirement: Verifier attempts repair before removal

When a headline's source fails validation (URL error or wrong date), the verifier SHALL search for a replacement source before removing the headline.

#### Scenario: Replacement found

- **WHEN** `web_search` returns a result with a valid article URL published on `today_date`
- **THEN** the verifier SHALL update the headline's inline citation URL and source name

#### Scenario: No replacement found

- **WHEN** `web_search` returns no results matching `today_date`
- **THEN** the verifier SHALL remove the headline from the summary entirely

##### Example: repair flow

| Validation result | web_search result | Final action |
|---|---|---|
| Homepage URL (no article content) | Found article published today | Replace citation URL and source name |
| Date mismatch (2025 article) | No today's article found | Remove headline |
| extract_url error | Found article published today | Replace citation URL and source name |

---
### Requirement: Verifier tool call loop is bounded

The verifier's tool-use loop SHALL terminate after at most 20 tool calls.

#### Scenario: Guard triggers

- **WHEN** the number of tool calls reaches 20
- **THEN** the loop SHALL exit and return the verified/repaired state accumulated so far

##### Example: guard boundary

| Tool calls made | Action |
|---|---|
| 12 | Continue verifying |
| 20 | Exit loop, return current state |

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