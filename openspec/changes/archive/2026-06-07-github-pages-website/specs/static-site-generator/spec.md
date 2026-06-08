## ADDED Requirements

### Requirement: publish.py generates daily HTML pages from summaries.md

`publish.py` SHALL parse `summaries.md`, extract each `## YYYY-MM-DD HH:MM` section, and generate a corresponding `docs/YYYY-MM-DD/index.html` file.

#### Scenario: New daily page created

- **WHEN** `publish.py` is run and `summaries.md` contains a section for `2026-06-07`
- **THEN** the file `docs/2026-06-07/index.html` SHALL exist and contain the summary content for that date

#### Scenario: Existing pages are regenerated

- **WHEN** `publish.py` is run multiple times
- **THEN** all daily pages SHALL be fully regenerated from the current `summaries.md` content

##### Example: page count matches sections

- **GIVEN** summaries.md contains sections for 2026-06-06 and 2026-06-07
- **WHEN** `python3 publish.py` is executed
- **THEN** both `docs/2026-06-06/index.html` and `docs/2026-06-07/index.html` SHALL exist

### Requirement: publish.py generates an index page listing all summaries

`publish.py` SHALL regenerate `docs/index.html` on every run, listing all available daily summaries newest-first as clickable links.

#### Scenario: Index reflects all available dates

- **WHEN** `publish.py` is run
- **THEN** `docs/index.html` SHALL contain a link to each daily page, ordered from most recent to oldest

### Requirement: publish.py creates docs/about.html if absent

`publish.py` SHALL create `docs/about.html` when it does not already exist, containing a bilingual description of the project.

#### Scenario: about.html created on first run

- **WHEN** `docs/about.html` does not exist and `publish.py` is run
- **THEN** `docs/about.html` SHALL be created with bilingual EN and ZH content sections

#### Scenario: about.html preserved on subsequent runs

- **WHEN** `docs/about.html` already exists and `publish.py` is run
- **THEN** `docs/about.html` SHALL NOT be overwritten

### Requirement: publish.py handles legacy summaries without bilingual delimiters

For `## YYYY-MM-DD` sections in `summaries.md` that do not contain `<!-- EN -->` or `<!-- ZH -->` delimiters, `publish.py` SHALL treat the entire section content as English and display a fallback message for the ZH view.

#### Scenario: Legacy section rendered as English-only

- **WHEN** a summary section contains no `<!-- EN -->` or `<!-- ZH -->` markers
- **THEN** the EN view SHALL show the full section content
- **THEN** the ZH view SHALL show the text `(No Chinese version available)`

### Requirement: publish.py reports completion to stdout

`publish.py` SHALL print `Published N pages to docs/` upon successful completion, where N is the number of daily pages generated.

#### Scenario: Completion message

- **GIVEN** summaries.md contains 2 dated sections
- **WHEN** `python3 publish.py` is executed
- **THEN** stdout SHALL contain `Published 2 pages to docs/`
