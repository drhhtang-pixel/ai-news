## 1. 修改 tools.py：擴展 raw_content 截斷上限

- [x] 1.1 `extract_url` 回傳的 `raw_content` 截斷上限從 500 字元改為 1,000 字元，使 verifier 有更完整的文章上文可參考。驗證方式：在 `tools.py` 中確認 `raw_content` 截斷值為 1000，手動呼叫 `extract_url` 確認回傳內容長度可達 1,000 字元（符合 Requirement: extract_url returns up to 1,000 characters of article content）

## 2. 修改 verifier.py：unknown 日期視為驗證失敗

- [x] 2.1 在 `VERIFIER_SYSTEM_PROMPT` 中新增明確規則：當 `extract_url` 回傳 `Published: unknown` 時，verifier 不得嘗試從文章內文猜測日期，必須直接視為日期驗證失敗，並呼叫 `web_search` 尋找替代來源。驗證方式：以一個 `published_date` 為 unknown 的 URL 作為摘要輸入執行 verifier，確認 verifier 呼叫 `web_search` 而非保留該來源（符合 Requirement: Verifier checks that source was published on today's date）
