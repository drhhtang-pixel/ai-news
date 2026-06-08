## ADDED Requirements

### Requirement: extract_url tool is available for URL content retrieval

The `tools.py` module SHALL define an `extract_url` tool that fetches the content of a specific URL using the Tavily extract API.

#### Scenario: Successful URL extraction

- **WHEN** `execute_tool("extract_url", {"url": "https://example.com/article"})` is called
- **THEN** the function SHALL call `TavilyClient.extract(urls=["https://example.com/article"])`
- **THEN** the function SHALL return a formatted string containing the article title, a content excerpt, the published date (if available), and the URL

#### Scenario: URL extraction fails

- **WHEN** `TavilyClient.extract()` raises an exception
- **THEN** `execute_tool` SHALL return `"Error: <exception message>"`
- **THEN** the caller SHALL NOT receive an exception

##### Example: extract_url tool schema and return format

- **GIVEN** tool name `"extract_url"` with input `{"url": "https://techcrunch.com/2026/06/08/article"}`
- **THEN** the tool is defined in `TOOLS` with input schema:
  ```json
  {
    "type": "object",
    "properties": {
      "url": { "type": "string", "description": "The URL of the article to extract" }
    },
    "required": ["url"]
  }
  ```
- **THEN** a successful call returns a string in this format:
  ```
  **[Article Title]**
  [Content excerpt]
  Published: [date or "unknown"]
  URL: [url]
  ```
