# bilingual-website

Every generated HTML page supports English and Chinese content with a language toggle and localStorage-based preference persistence.

## Overview

- **Toggle button**: top-right corner of each page, switches between EN and ZH views
- **Persistence**: selected language stored in `localStorage` under key `lang`
- **Default**: English when no preference is stored
- **Content structure**: separate EN and ZH content divs per page, shown/hidden by the toggle

## Requirements

### Requirement: Every page has an EN/ZH language toggle button

Every generated HTML page SHALL include a language toggle button in the top-right corner that switches between English and Chinese content.

#### Scenario: Toggle switches language

- **WHEN** a user clicks the ZH button on a page showing English content
- **THEN** the English content div SHALL be hidden and the Chinese content div SHALL be shown

#### Scenario: Toggle switches back

- **WHEN** a user clicks the EN button on a page showing Chinese content
- **THEN** the Chinese content div SHALL be hidden and the English content div SHALL be shown

---
### Requirement: Language preference is persisted in localStorage

The selected language SHALL be stored in `localStorage` under the key `lang` and automatically applied when any page is loaded.

#### Scenario: Preference remembered across pages

- **GIVEN** a user selected ZH on the index page
- **WHEN** the user navigates to a daily summary page
- **THEN** the page SHALL load with Chinese content visible by default

#### Scenario: Default language is English

- **WHEN** no `lang` key exists in localStorage
- **THEN** the page SHALL display English content by default

##### Example: localStorage values

| localStorage `lang` value | Content shown on load |
|---|---|
| `"en"` | English content visible, Chinese hidden |
| `"zh"` | Chinese content visible, English hidden |
| (absent) | English content visible, Chinese hidden |

---
### Requirement: Agent output includes both EN and ZH content blocks

The system prompt in `agent.py` SHALL instruct Claude to output both an English block (delimited by `<!-- EN -->`) and a Chinese block (delimited by `<!-- ZH -->`) in every response.

#### Scenario: Both language blocks present in summaries.md

- **WHEN** the agent completes a run
- **THEN** the appended section in `summaries.md` SHALL contain both `<!-- EN -->` and `<!-- ZH -->` markers
- **THEN** the EN block SHALL contain `### Headlines`, `### Analysis`, and `### Sources`
- **THEN** the ZH block SHALL contain `### 頭條新聞`, `### 分析`, and `### 來源`

#### Scenario: EN block appears before ZH block

- **WHEN** the agent completes a run
- **THEN** the `<!-- EN -->` marker SHALL appear before the `<!-- ZH -->` marker in the output
