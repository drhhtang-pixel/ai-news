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

- **WHEN** the headline's description states something important that no kept source supports
- **THEN** the verifier SHALL remove the headline (it only returns keep/remove decisions and never rewrites text)

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

---
### Requirement: Verifier returns decisions; the program rebuilds the summary

The verifier SHALL NOT rewrite the summary text. When done, it SHALL call the `submit_verification` tool once with one decision per EN headline: `{index (1-based), action: keep|remove, reason, sources: [{name, url, date}]}`. `knowledge.apply_verification()` SHALL then:

- refuse (`InvalidDecisions`) unless the EN and ZH headline counts match and `check_decisions()` finds exactly one decision per headline: integer indexes covering `1..N` with no duplicates or out-of-range values, `action` in keep/remove, `sources` a list
- drop removed headlines, and kept headlines left with no valid source, in both EN and ZH (same position)
- rebuild kept headlines' citations as links from the decision's sources: `*(Sources: [Name](url), YYYY-MM-DD; ...)*` and `*(來源：[Name](url)，YYYY-MM-DD；...)*` (max 3; invalid URLs dropped; anything but a real calendar date shown as "date unknown" / 「日期不明」)
- rebuild both Sources / 來源 sections from the remaining citations, as `- Name: URL (published YYYY-MM-DD)` or `(published date unknown)`, even when the section was empty, adding the section if it is missing
- leave Analysis / 分析 unchanged

Dates SHALL come from tool evidence only: before applying, every source's date SHALL be replaced by `tools.tool_date(url)`: the EARLIEST of all dates any tool returned for that URL during the run (`tools.URL_DATES` keeps every reported date), or "unknown" if no tool dated it. The model's own date is never used, and conflicting tool dates can only make a story look older, so neither can make an old story look recent. If a reply carries a rejected submission together with other tool calls, every tool_use in it SHALL get a tool_result (research calls are executed, submissions get the rejection as an error) before resubmission.

If the draft's EN and ZH headline counts differ, `run_verifier` SHALL return "" without calling the model. If the decisions are rejected, the verifier SHALL get one forced resubmission with the rejection reason (as an error `tool_result`); a second rejection SHALL return "".

Every decision SHALL be logged as `  [verifier] #<index> <action>: <reason>`.

#### Scenario: Verifier stops or runs out of budget without submitting

- **WHEN** the verifier ends its turn, or reaches the tool-call limit, without calling `submit_verification`
- **THEN** one more request SHALL be sent with `tool_choice={"type": "tool", "name": "submit_verification"}`
- **THEN** if it still does not submit, `run_verifier` SHALL return "" and the run SHALL publish nothing (see "An unverified summary is never published")

#### Scenario: Safety net for long replies

- **WHEN** a verifier request is sent
- **THEN** it SHALL be streamed with `max_tokens = VERIFIER_MAX_TOKENS` (32000)
- **WHEN** a response stops at `max_tokens` without a submission
- **THEN** the first 300 characters of its text SHALL be logged and `run_verifier` SHALL return ""

Background: on 2026-10-18 the full-text verifier hit its 8192- and then 16000-token limits twice, which left one run unpublished and one run unverified.

---
### Requirement: Verifier tool call loop is bounded

The verifier's tool-use loop SHALL terminate after at most 40 tool calls.

#### Scenario: Guard triggers

- **WHEN** the number of tool calls reaches 40
- **THEN** the loop SHALL exit and return the verified/repaired state accumulated so far
- **THEN** a final request SHALL force `submit_verification` (see above)

##### Example: guard boundary

| Tool calls made | Action |
|---|---|
| 12 | Continue verifying |
| 40 | Exit loop, return current state |

---
### Requirement: An unverified summary is never published

`verify_summary()` SHALL return `(summary, verified)`. If the verifier raises, produces no valid submission, or cannot verify safely, it SHALL print a warning to stderr and return `(draft, False)` without raising. `main()` SHALL then print `"Error: source verification did not complete; nothing is published today."` and exit with code `1` before holding stories or writing anything (policy chosen by 唐老師 on 2026-10-19: a missing day is better than unchecked headlines).

#### Scenario: Verifier crashes

- **WHEN** an unhandled exception occurs in `verify_summary()`
- **THEN** it SHALL print `"Warning: verifier failed: <error>"` to stderr and return `(draft, False)`
- **THEN** `main()` SHALL exit with code `1`, the output file SHALL be unchanged, and no held-story file SHALL be written

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