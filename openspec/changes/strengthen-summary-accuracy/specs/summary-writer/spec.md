## MODIFIED Requirements

### Requirement: Summary is structured Markdown

The summary text produced by Claude SHALL be structured Markdown containing both an English block and a Chinese block. Each headline in the Headlines section SHALL include an inline source citation.

#### Scenario: Each EN headline includes inline citation

- **WHEN** the agent completes a run
- **THEN** every bullet item under `### Headlines` SHALL end with `*(Source: [Publication Name], [Month Day])*`
- **THEN** every bullet item under `### 頭條新聞` SHALL end with `*(來源：[媒體名稱]，[月 日])*`

##### Example: headline with inline citation

- **GIVEN** the agent has found an article about OpenAI from TechCrunch published June 8
- **THEN** the EN headline SHALL be formatted as:
  ```
  - **OpenAI announces new model:** Brief description. *(Source: TechCrunch, June 8)*
  ```
- **THEN** the ZH headline SHALL be formatted as:
  ```
  - **OpenAI 宣布新模型：** 簡短說明。*(來源：TechCrunch，6 月 8 日)*
  ```

---

## ADDED Requirements

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
