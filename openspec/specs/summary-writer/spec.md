# summary-writer

Structured AI news summarization: Claude synthesizes accumulated search results into a dated Markdown summary and appends it to a configured output file.

## Overview

- **Module**: `writer.py` (append logic) + system prompt in `agent.py` (structure enforcement)
- **Output format**: append-only Markdown file, one `## YYYY-MM-DD HH:MM` section per run
- **API**: `append_summary(text: str, output_file: str) -> None`

## Requirements

### Requirement: Summary is appended to output file with a date header

The writer SHALL prepend a `## YYYY-MM-DD HH:MM` header to each summary and append it to the configured output file.

#### Scenario: First run creates the file

- **WHEN** `OUTPUT_FILE` does not exist and a summary is written
- **THEN** the file SHALL be created and contain the date header followed by the summary text

#### Scenario: Subsequent run appends

- **WHEN** `OUTPUT_FILE` already contains a previous summary
- **THEN** the new summary SHALL be appended after the existing content, separated by a blank line

##### Example: two runs same day

- **GIVEN** summaries.md contains a section from `## 2026-06-04 08:00`
- **WHEN** the agent runs again at `09:30`
- **THEN** summaries.md contains both `## 2026-06-04 08:00` and `## 2026-06-04 09:30` sections in order

---
### Requirement: Summary is structured Markdown

The summary text produced by Claude SHALL be structured Markdown containing both an English block and a Chinese block. Each headline in the Headlines section SHALL include an inline citation listing up to 3 sources used for that story, each with its own published date. Sources for one story MAY have different dates. After verification, citations are rewritten as links (`[Name](url)`) by the program (see source-verifier).

#### Scenario: Each EN headline includes inline citation

- **WHEN** the agent completes a run
- **THEN** every bullet item under `### Headlines` SHALL end with `*(Sources: [Publication A], YYYY-MM-DD; [Publication B], YYYY-MM-DD)*` (one or more sources; `date unknown` when the tool reports no date)
- **THEN** every bullet item under `### 頭條新聞` SHALL end with `*(來源：[媒體 A]，YYYY-MM-DD；[媒體 B]，YYYY-MM-DD)*`（日期不明時寫「日期不明」）

##### Example: headline with inline citation

- **GIVEN** the agent has found articles about OpenAI from TechCrunch (2026-06-08) and Reuters (2026-06-07)
- **THEN** the EN headline SHALL be formatted as:
  ```
  - **OpenAI announces new model:** Brief description. *(Sources: TechCrunch, 2026-06-08; Reuters, 2026-06-07)*
  ```
- **THEN** the ZH headline SHALL be formatted as:
  ```
  - **OpenAI 宣布新模型：** 簡短說明。*(來源：TechCrunch，2026-06-08；Reuters，2026-06-07)*
  ```

---
### Requirement: Successful write is reported to stdout

The writer SHALL print `Summary written to <output_file>` to stdout after a successful append.

#### Scenario: Write confirmation

- **WHEN** the summary is written without error
- **THEN** stdout SHALL contain the message `Summary written to summaries.md` (or whichever path is configured)

---
### Requirement: Sources section lists specific article URLs

The `### Sources` and `### 來源` sections SHALL list the direct URL to each individual article, not a publication's homepage.

#### Scenario: Sources contain article-level URLs

- **WHEN** the agent writes the Sources section
- **THEN** each entry SHALL include a URL that points to the specific article page
- **THEN** each entry SHALL include the publication date in `YYYY-MM-DD` format
- **THEN** URLs pointing only to a publication's homepage (e.g., `https://techcrunch.com`) SHALL NOT appear

##### Example: sources format

```
### Sources
- TechCrunch: https://techcrunch.com/2026/06/08/openai-new-model (published 2026-06-08)
- The Verge: https://www.theverge.com/2026/6/8/article-slug (published 2026-06-08)
```

---
### Requirement: Stories are new to the monitor, not necessarily new in time

"New" SHALL mean not yet published by this monitor. The system prompt SHALL include today's UTC date and the list of EN headline titles published in the last 45 days (`known_headlines()`, see the story-novelty spec), and SHALL instruct Claude not to report those stories again. A story from up to about a month ago MAY be reported if it is not in that list. Year-in-review articles and historical summaries SHALL be excluded. Claude SHALL copy each source's date from the `Published:` line of the tool result, writing "date unknown" when the tool reports `unknown`.

#### Scenario: Known stories are listed in the prompt

- **WHEN** `run_agent(topic, today, known)` is called with known titles
- **THEN** the system prompt SHALL contain `NEW TO THIS MONITOR` and each known title as a `- ` line under `ALREADY PUBLISHED`
- **THEN** the system prompt SHALL NOT restrict sources to a date window

---

## Implementation Notes

- `append_summary` opens the file in `"a"` mode with `encoding="utf-8"`, creating it if absent
- When the file already exists, a leading `"\n"` is written before the header to separate sections
- The system prompt in `agent.py` explicitly instructs Claude to output both an `<!-- EN -->` block (with `### Headlines`, `### Analysis`, `### Sources`) and a `<!-- ZH -->` block (with `### 頭條新聞`, `### 分析`, `### 來源`), EN before ZH
- Timestamp is generated with `datetime.now().strftime("%Y-%m-%d %H:%M")` at write time
