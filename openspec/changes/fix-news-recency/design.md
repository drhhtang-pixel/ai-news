## Context

目前 `tools.py` 的 `TavilyClient.search()` 沒有日期限制，會回傳所有時間的相關文章；加上 `agent.py` 的 system prompt 未告知 Claude 當天日期，導致 Claude 無法辨別結果新舊。執行結果顯示，今日（2026-06-08）的摘要充滿 2025 年的年終回顧文章，而非當天新聞。

## Goals / Non-Goals

**Goals:**

- 搜尋結果限定在過去 24 小時內
- Claude 知道執行當天日期，能主動過濾過期內容
- 搜尋 query 帶入今日日期，提升搜尋相關性

**Non-Goals:**

- 不修改摘要格式或雙語結構
- 不更換搜尋引擎（保留 Tavily）
- 不調整 `MAX_TOOL_CALLS` 上限

## Decisions

### 以 `days=1` 參數過濾 Tavily 搜尋結果

在 `tools.py` 的 `TavilyClient.search()` 加入 `days=1`，限制只回傳最近 24 小時的文章。

替代方案考慮：
- `days=2`：緩衝時區差異，但可能帶入昨天的舊文章
- `days=3`：過於寬鬆，仍可能混入非當天新聞
- 選擇 `days=1`：對「當天新聞」的定義最精確；若某天真的沒有新聞，寧可回傳較少結果也不混入舊文章

### 在 system prompt 注入執行日期

`agent.py` 的 `run_agent()` 函式在組合 system prompt 時，動態插入 `datetime.now().strftime("%Y-%m-%d")`，並加入明確指示「只報導 {date} 當天的新聞，排除所有年終回顧、歷史整理和非當天發布的文章」。

替代方案考慮：
- 只靠 `days=1` 不加 prompt：Tavily 有時仍會回傳日期邊界附近的舊文章；prompt 提供 Claude 判斷的基準
- 選擇同時修改 prompt：雙重保障，`days=1` 過濾來源，prompt 要求 Claude 自我審核

### 搜尋 query 帶入今日日期

`SEARCH_TOPIC` 的預設值從 `"AI news today"` 改為在執行時動態生成 `f"AI news {date}"`。

替代方案考慮：
- 保留 `"AI news today"`：Tavily 不解析自然語言日期，"today" 對過濾無效
- 選擇帶入具體日期字串：讓搜尋引擎的關鍵字比對能鎖定包含該日期的文章

## Implementation Contract

**行為：**
- 每次執行 `agent.py` 時，Tavily 只會回傳過去 24 小時內發布的文章
- Claude 的 system prompt 包含當天日期，並明確要求排除非當天的回顧性文章
- 預設搜尋 topic 為 `"AI news YYYY-MM-DD"`（日期為執行當天）

**介面變更：**
- `execute_tool()` 在 `tools.py` 中：`client.search(query=..., search_depth="basic", days=1)`
- `run_agent(search_topic, today_date)` 在 `agent.py` 中：新增 `today_date` 參數，用於注入 prompt
- `main()` 在 `agent.py` 中：計算 `today_date = datetime.now().strftime("%Y-%m-%d")`，傳入 `run_agent()`，並用於組合預設 `SEARCH_TOPIC`

**驗收條件：**
- 執行 `python3 agent.py` 後，`summaries.md` 最新條目的來源 URL 皆為當天或前一天發布的文章
- Tavily 呼叫帶有 `days=1` 參數（可於 `tools.py` 程式碼驗證）
- System prompt 包含執行日期字串（可於輸出結果中間接驗證）

**範圍邊界：**
- 只修改 `tools.py` 和 `agent.py`，不動 `writer.py`、`publish.py`、`run.sh`

## Risks / Trade-offs

- [風險] 某些冷門日子的 AI 新聞極少，`days=1` 可能回傳很少結果 → 緩解：Claude 的 system prompt 已有「若結果不足則說明」的指示；未來可視需要升為 `days=2`
- [風險] Tavily 的 `days` 參數是以文章「索引時間」而非「發布時間」計算，可能有幾小時落差 → 可接受，比完全不過濾好得多
