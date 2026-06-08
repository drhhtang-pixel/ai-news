## 1. 修改 tools.py：加入日期過濾

- [x] 1.1 實作「以 `days=1` 參數過濾 Tavily 搜尋結果」設計決策：在 `tools.py` 的 `execute_tool()` 函式中，將 `client.search(query=input["query"], search_depth="basic")` 改為 `client.search(query=input["query"], search_depth="basic", days=1)`，滿足「Search results are filtered to the past 24 hours」需求。驗證方式：在 `tools.py` 程式碼中確認 `days=1` 出現在 `client.search()` 呼叫內。

## 2. 修改 agent.py：注入今日日期

- [x] 2.1 實作「在 system prompt 注入執行日期」設計決策，滿足「System prompt includes today's date and excludes non-current articles」需求：在 `agent.py` 頂部加入 `from datetime import datetime`（若尚未 import），並修改 `run_agent()` 函式簽名為 `run_agent(search_topic: str, today_date: str) -> str`；在 `SYSTEM_PROMPT` 字串之後、`messages` 組合之前，建立 `dated_system_prompt = SYSTEM_PROMPT + f"\n\nToday's date is {today_date}. Only report news published on {today_date}. Exclude year-in-review articles, historical summaries, and any content not published on this date."`；將後續 `client.messages.create()` 的 `system=SYSTEM_PROMPT` 全部改為 `system=dated_system_prompt`（共兩處：主迴圈與 guard 的 final call）。驗證方式：執行 `python3 agent.py` 後，檢查輸出的摘要來源是否為當天文章。

- [x] 2.2 實作「搜尋 query 帶入今日日期」設計決策，滿足「Agent drives search strategy autonomously」的日期導向 query 需求：在 `main()` 函式中，在 `validate_env()` 呼叫後加入 `today_date = datetime.now().strftime("%Y-%m-%d")`；將 `search_topic = os.environ.get("SEARCH_TOPIC", "AI news today")` 改為 `search_topic = os.environ.get("SEARCH_TOPIC", f"AI news {today_date}")`；並將 `run_agent(search_topic)` 改為 `run_agent(search_topic, today_date)`。驗證方式：執行後確認 stdout 顯示的 `Searching for:` 訊息包含當天日期，例如 `Searching for: AI news 2026-06-08`。
