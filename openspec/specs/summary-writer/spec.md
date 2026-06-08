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

The summary text produced by Claude SHALL be structured Markdown containing both an English block and a Chinese block, each with headlines, analysis, and sources sections.

#### Scenario: Summary contains required bilingual sections

- **WHEN** the agent completes a run
- **THEN** the written summary SHALL contain the marker `<!-- EN -->` followed by `### Headlines`, `### Analysis`, and `### Sources`
- **THEN** the written summary SHALL contain the marker `<!-- ZH -->` followed by `### 頭條新聞`, `### 分析`, and `### 來源`
- **THEN** `<!-- EN -->` SHALL appear before `<!-- ZH -->` in the output

##### Example: bilingual section structure

- **GIVEN** the agent has completed its search loop
- **WHEN** the final summary is written to summaries.md
- **THEN** the section content SHALL match this structure:
  ```
  <!-- EN -->
  ### Headlines
  ...
  ### Analysis
  ...
  ### Sources
  ...

  <!-- ZH -->
  ### 頭條新聞
  ...
  ### 分析
  ...
  ### 來源
  ...
  ```

---
### Requirement: Successful write is reported to stdout

The writer SHALL print `Summary written to <output_file>` to stdout after a successful append.

#### Scenario: Write confirmation

- **WHEN** the summary is written without error
- **THEN** stdout SHALL contain the message `Summary written to summaries.md` (or whichever path is configured)

## Implementation Notes

- `append_summary` opens the file in `"a"` mode with `encoding="utf-8"`, creating it if absent
- When the file already exists, a leading `"\n"` is written before the header to separate sections
- The system prompt in `agent.py` explicitly instructs Claude to output both an `<!-- EN -->` block (with `### Headlines`, `### Analysis`, `### Sources`) and a `<!-- ZH -->` block (with `### 頭條新聞`, `### 分析`, `### 來源`), EN before ZH
- Timestamp is generated with `datetime.now().strftime("%Y-%m-%d %H:%M")` at write time
