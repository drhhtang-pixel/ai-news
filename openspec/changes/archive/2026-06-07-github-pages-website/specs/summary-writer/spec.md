## MODIFIED Requirements

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
