## Why

`extract_url` 對某些頁面（如 newsletter alert 頁）無法取得 `published_date`，回傳 `"unknown"`。現有 verifier prompt 沒有處理這個情況，導致 Claude 以文章內容的「時效感」猜測日期，讓這類來源通過驗證，進入每日摘要。

## What Changes

- verifier prompt 新增規則：`published_date` 為 `unknown` 時，視同驗證失敗，直接呼叫 `web_search` 搜尋替代來源
- `extract_url` 回傳的 `raw_content` 上限從 500 字擴展至 1,000 字，提供更完整的文章上文給 Claude 判斷

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `source-verifier`: 新增 unknown 日期的處理規則——`published_date: unknown` 視同日期驗證失敗

## Impact

- Affected specs: `source-verifier`
- Affected code:
  - Modified: `verifier.py`
  - Modified: `tools.py`
