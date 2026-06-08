## Why

每日執行的新聞摘要包含大量過去幾個月甚至去年的舊文章（如年終回顧），而非當天發生的新聞。根本原因是 Tavily 搜尋未設定日期限制，且 Claude 不知道執行當下的日期，導致搜尋引擎回傳熱門舊文章。

## What Changes

- 修改 `tools.py`：`TavilyClient.search()` 加入 `days=1` 參數，限制只回傳 24 小時內的文章
- 修改 `agent.py`：system prompt 注入執行當天日期，要求 Claude 只報導當天新聞，並排除回顧性文章
- 修改 `agent.py`：預設 `SEARCH_TOPIC` 改為 `"AI news {YYYY-MM-DD}"`，在搜尋 query 中直接帶入日期

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `news-search`：搜尋結果加入 24 小時日期過濾（`days=1`）；搜尋 query 帶入今日日期
- `summary-writer`：system prompt 加入當天日期，要求摘要只涵蓋當天新聞

## Impact

- Affected specs: news-search, summary-writer
- Affected code:
  - Modified: tools.py
  - Modified: agent.py
