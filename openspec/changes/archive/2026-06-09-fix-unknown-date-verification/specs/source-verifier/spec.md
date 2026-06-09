## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: extract_url returns up to 1,000 characters of article content

The `extract_url` tool SHALL return up to 1,000 characters of `raw_content` from the fetched article, providing sufficient context for the verifier to evaluate article relevance.

#### Scenario: Content truncation limit

- **WHEN** `extract_url` fetches an article with raw content longer than 1,000 characters
- **THEN** the returned content SHALL be truncated to 1,000 characters

#### Scenario: Short article content

- **WHEN** `extract_url` fetches an article with raw content shorter than 1,000 characters
- **THEN** the returned content SHALL not be padded and reflects the full available content
