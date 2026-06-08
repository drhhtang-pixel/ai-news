## Context

目前 `agent.py` 執行一次搜尋 loop 後直接輸出摘要，沒有任何後置驗證步驟。Headlines 不帶來源標注，Sources 區塊有時只列首頁 URL 而非文章 URL，發布日期也可能與實際不符。讀者無從快速判斷每條新聞的可信度。

現有 pipeline：
```
run_agent() → append_summary()
```

目標 pipeline：
```
run_agent() → verify_summary() → append_summary()
```

## Goals / Non-Goals

**Goals:**

- 每條 headline 附上 inline source citation（出版商名稱 + 日期）
- Sources 區塊必須列具體文章 URL，不得只列首頁
- 新增獨立 verifier agent，在寫入前驗證每條 headline 的來源 URL 確實存在且發布日期為當天
- 驗證失敗時：先嘗試搜尋替代來源；無替代則刪除該 headline
- EN 與 ZH 兩個語言區塊都需通過驗證

**Non-Goals:**

- 不驗證 Analysis 或 Sources 段落的文字正確性（只驗證 headlines 的 URL 與日期）
- 不對 Sources 區塊的 URL 逐一驗證（僅驗證 headlines 的 citation URL）
- 不支援非 Tavily 的 URL 抓取後端
- 不修改 `publish.py` 的 HTML 渲染邏輯

## Decisions

### Verifier 為獨立 LLM agent，非規則式 parser

使用 Claude 呼叫（`client.messages.create`）從摘要文字中解析結構化清單，而非自行撰寫 regex parser。

**理由**：摘要格式會因 Claude 輸出略有差異，LLM 解析比 regex 更健壯；驗證結果的「是否同一事件」也需要語意判斷，不適合規則式邏輯。

**Alternative**：純 Python regex 解析 → 脆弱，輸出格式變化即失效。

---

### Verifier 工具組：`extract_url` + `web_search`

Verifier agent 有兩個工具：
1. `extract_url(url: str)` → 呼叫 Tavily `client.extract(urls=[url])`，回傳文章 raw content（含 `published_date` 若可取得）
2. `web_search(query: str)` → 現有工具，用於找替代來源

**理由**：`extract_url` 比 re-search 更精準，直接指向已知 URL；search 作為備援，在 URL 失效時找替代。

---

### Verifier 策略：verify → repair → remove

每條 headline 的處理流程：
1. 呼叫 `extract_url(url)` 取得文章內容
2. 判斷：URL 可抓取且日期符合當天 → 保留
3. 失敗（抓取錯誤 / 日期不符 / 非文章頁）→ 呼叫 `web_search` 搜尋同一事件的替代來源
4. 找到有效替代 → 更新 URL 與 source name
5. 無替代 → 從摘要中刪除該 headline

**理由**：刪除比保留 `[unverified]` 標注更乾淨，讀者看到的每條 headline 都是已驗證的。

---

### Inline citation 格式

```
- **[Headline]:** [Description]. *(Source: [Publication], [Month Day])*
```

中文版：
```
- **[標題]：** [說明]。*(來源：[媒體]，[月 日])*
```

**理由**：括號內的斜體 citation 視覺上區分於正文，不干擾閱讀；與 Sources 區塊的完整 URL 互補。

---

### Sources 區塊格式要求（系統提示強化）

```
- [Publication Name]: https://specific-article-url (published YYYY-MM-DD)
```

系統提示中明確要求：不得使用首頁 URL（如 `https://techcrunch.com`），必須為具體文章路徑（如 `https://techcrunch.com/2026/06/08/article-title`）。

## Implementation Contract

**新增模組 `verifier.py`**：
- 公開函式：`verify_summary(summary: str, today_date: str) -> str`
- 輸入：`run_agent()` 回傳的完整雙語 markdown 字串
- 輸出：驗證並修正後的完整雙語 markdown 字串（格式與輸入相同）
- 若驗證過程全部失敗（無任何 headline 通過），回傳原始 summary 並印出警告至 stderr，不丟出 exception
- MAX_TOOL_CALLS 限制：verifier loop 上限 20 次工具呼叫（headlines 數量通常 5–8 條，每條最多 2 次工具呼叫）

**`tools.py` 新增工具**：
- `extract_url` tool schema：`{ url: string }` → 呼叫 `client.extract(urls=[url])`
- `execute_tool` dispatcher 新增 `extract_url` 分支
- 回傳格式：`**[title]**\n[content excerpt]\nPublished: [date]\nURL: [url]`；抓取失敗時回傳 `"Error: [message]"`

**`agent.py` `main()` pipeline 更新**：
```python
summary = run_agent(search_topic, today_date)
summary = verify_summary(summary, today_date)   # 新插入
append_summary(summary, output_file)
```

**系統提示更新（`agent.py` `SYSTEM_PROMPT`）**：
- Headlines 每條必須附 `*(Source: Name, Month Day)*`（EN）/ `*(來源：媒體，月 日)*`（ZH）
- Sources 區塊每條格式：`- Name: URL (published YYYY-MM-DD)`，URL 必須為具體文章頁

**驗收條件**：
- 執行 `python3 agent.py` 後，`summaries.md` 最新區塊的每條 headline 都有 inline citation
- 執行後 stdout 無 Python exception；verifier 驗證失敗時有 stderr 警告
- `verifier.py` 可獨立 import（`from verifier import verify_summary`）不觸發副作用

## Risks / Trade-offs

- **Tavily extract 速率限制**：免費方案每月 1,000 次請求；verifier 每次執行最多消耗 20 次，每日一次執行仍在限額內。若未來增加執行頻率需評估升級方案。
- **文章頁無 published_date meta tag**：部分站台不輸出結構化日期，verifier LLM 需從正文推斷。以「內容提及當天事件」作為輔助判斷。
- **Verifier 延長執行時間**：每次執行新增 LLM 呼叫 + 最多 20 次 API calls，預計增加 30–60 秒。可接受，因為精確度優先。
- **ZH headlines 驗證**：ZH 區塊的來源與 EN 相同，verifier 優先驗證 EN 區塊，再將結果同步套用至 ZH 對應條目（同一事件）。
