## Why

目前每條 headline 沒有來源標注，讀者無法直接判斷資訊可信度；且 agent 偶爾會引用不正確的 URL（首頁而非文章頁）或錯誤的發布日期。需要在輸出格式加上 inline source citation，並新增獨立的 verifier agent 在寫入前自動檢核。

## What Changes

- `agent.py` 系統提示更新：每條 headline 必須附上 `*(Source: 出版商名, 月 日)*` 格式的 inline citation；Sources 區塊必須列出具體文章 URL（非首頁）
- 新增 `verifier.py`：以 LLM 驅動的獨立 agent，在 `run_agent()` 之後、`append_summary()` 之前執行；逐一驗證每條 headline 的來源 URL 真實存在且發布日期為當天，驗證失敗時嘗試搜尋替代來源，無法替代則刪除該 headline
- `agent.py` `main()` 更新：在 pipeline 中插入 `verify_summary()` 呼叫
- `tools.py` 更新：新增 `extract_url` 工具（Tavily extract API）供 verifier 使用

## Capabilities

### New Capabilities

- `source-verifier`: 獨立 LLM agent，驗證摘要中每條 headline 的來源 URL 與發布日期，並在驗證失敗時進行修正或刪除

### Modified Capabilities

- `summary-writer`: headline 格式新增 inline source citation `*(Source: 名稱, 日期)*`；Sources 區塊必須列出具體文章 URL
- `news-search`: `tools.py` 新增 `extract_url` 工具定義供 verifier agent 使用

## Impact

- Affected specs: source-verifier（新增）、summary-writer（修改）、news-search（修改）
- Affected code:
  - New: verifier.py
  - Modified: agent.py, tools.py
  - Removed: (none)
