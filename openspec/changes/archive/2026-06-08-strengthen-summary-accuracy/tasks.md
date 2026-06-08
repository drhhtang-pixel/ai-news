## 1. 修改 tools.py：新增 extract_url 工具

- [x] 1.1 在 `tools.py` 的 `TOOLS` 清單中新增 `extract_url` 工具定義，實作「verifier 工具組：`extract_url` + `web_search`」設計決策，滿足「extract_url tool is available for URL content retrieval」需求：工具名稱為 `"extract_url"`，input schema 為 `{ "url": { "type": "string", "description": "The URL of the article to extract" } }`，required `["url"]`；description 說明「Fetch the full content of a specific article URL using Tavily extract. Use this to verify a URL is a real article and check its publication date.」驗證方式：確認 `TOOLS` 清單中出現 `"extract_url"` 工具定義。

- [x] 1.2 在 `tools.py` 的 `execute_tool()` 函式中新增 `extract_url` 分支，滿足「extract_url tool is available for URL content retrieval」需求：呼叫 `client.extract(urls=[input["url"]])`，從結果取第一個 result 的 `title`、`raw_content`（截取前 500 字元）、`published_date`（若無則為 `"unknown"`）和 `url`，組成格式為 `**{title}**\n{content}\nPublished: {date}\nURL: {url}` 的字串回傳；若 `results` 為空回傳 `"Error: No content extracted"`；`TavilyClient.extract()` 拋出例外時回傳 `"Error: {e}"`。驗證方式：以真實 URL 呼叫 `execute_tool("extract_url", {"url": "..."})` 確認回傳格式正確；以無效 URL 確認回傳 `"Error: ..."` 而非拋出例外。

## 2. 修改 agent.py：更新系統提示

- [x] 2.1 修改 `agent.py` 的 `SYSTEM_PROMPT`，實作「inline citation 格式」與「sources 區塊格式要求（系統提示強化）」設計決策，滿足「Summary is structured Markdown」（inline citation）與「Sources section lists specific article URLs」需求：EN headlines 每條格式改為 `- **[Headline]:** [One-sentence description]. *(Source: [Publication Name], [Month Day])*`；ZH 每條格式改為 `- **[標題]：** [一句說明]。*(來源：[媒體名稱]，[月 日])*`；在 `### Sources` / `### 來源` 說明中加入「每條必須為具體文章 URL（非首頁），格式：`- [Publication Name]: https://specific-article-url (published YYYY-MM-DD)`」。驗證方式：執行 `python3 agent.py` 後，確認 `summaries.md` 最新 Headlines 區塊的每條 bullet 包含 `*(Source:` 或 `*(來源：` 字樣。

## 3. 建立 verifier.py

- [x] 3.1 建立 `verifier.py`，定義 `VERIFIER_SYSTEM_PROMPT` 與 `MAX_VERIFIER_TOOL_CALLS = 20`，實作「verifier 為獨立 LLM agent，非規則式 parser」與「verifier 策略：verify → repair → remove」設計決策，滿足「Verifier validates each headline's source URL」、「Verifier checks that source was published on today's date」、「Verifier attempts repair before removal」與「ZH headlines are updated to match EN verification results」需求：`VERIFIER_SYSTEM_PROMPT` 說明 verifier 的任務——解析摘要中每條 EN headline 的 inline citation URL，逐一呼叫 `extract_url` 確認 URL 為有效文章頁（驗證 URL 可存取）且發布日期符合今天（`today_date`）（驗證日期），失敗時呼叫 `web_search` 搜尋替代（repair），有替代則更新 citation，無替代則刪除該 headline（remove），同步將 EN 驗證結果套用至對應 ZH headline；最後輸出格式與輸入相同的完整雙語摘要。驗證方式：確認 `verifier.py` 可被 import（`from verifier import verify_summary`）且不觸發副作用。

- [x] 3.2 在 `verifier.py` 中實作 `run_verifier(summary: str, today_date: str) -> str`，滿足「Verifier tool call loop is bounded」需求：以 `VERIFIER_SYSTEM_PROMPT + f"\n\nToday's date is {today_date}."` 為 system prompt，`summary` 為 user message，工具為 `tools.py` 中的 `TOOLS`（包含 `web_search` 與 `extract_url`）；agentic loop 結構與 `agent.py` 的 `run_agent()` 相同（`while True` + `stop_reason` 判斷）；`tool_call_count` 達 `MAX_VERIFIER_TOOL_CALLS = 20` 時強制結束，回傳目前 Claude 已輸出的文字或原始 `summary`。驗證方式：以含 inline citation 的測試摘要字串呼叫 `run_verifier`，確認回傳字串不為空且保持雙語結構。

- [x] 3.3 在 `verifier.py` 中實作公開函式 `verify_summary(summary: str, today_date: str) -> str`，滿足「Verifier failure is non-fatal」需求：以 `try/except Exception as e` 包覆 `run_verifier()` 呼叫；捕獲例外時印出 `f"Warning: verifier failed: {e}"` 至 `sys.stderr` 並回傳原始 `summary`；`run_verifier` 回傳空字串時同樣回傳原始 `summary` 並印出警告。驗證方式：傳入一個會導致 API 錯誤的輸入（例如空字串），確認函式回傳原始輸入且不拋出例外。

## 4. 修改 agent.py：在 pipeline 插入 verifier

- [x] 4.1 在 `agent.py` 的 `main()` 函式中，在 `summary = run_agent(search_topic, today_date)` 之後、`append_summary(summary, output_file)` 之前插入 `summary = verify_summary(summary, today_date)`，並在頂部加入 `from verifier import verify_summary`，滿足「Verifier validates each headline's source URL」pipeline 整合需求。驗證方式：執行 `python3 agent.py` 後，stdout 顯示 `Summary written to summaries.md`；確認 `summaries.md` 最新區塊的 headlines 皆有 inline citation 且已通過 verifier 處理。
