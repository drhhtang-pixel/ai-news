## Why

每日 AI 新聞摘要目前只儲存在本機的 `summaries.md`，無法與他人分享。需要一個公開網站，讓任何人都能透過瀏覽器閱讀摘要，並支援中英文切換。

## What Changes

- 新增 `publish.py`：將 `summaries.md` 解析並生成靜態 HTML 頁面到 `docs/` 目錄
- 新增 `docs/about.html`：靜態說明頁，介紹程式的運作原理（中英雙語）
- 新增每日摘要頁面 `docs/YYYY-MM-DD/index.html`：每天一個獨立頁面，永久 URL
- 新增 `docs/index.html`：過往摘要的日期索引列表
- 所有網頁支援 EN/ZH 切換按鈕
- **BREAKING** 修改 `summaries.md` 輸出格式：新增 `<!-- EN -->` 和 `<!-- ZH -->` 分隔符，Agent 一次生成中英雙語內容
- 修改 `agent.py`：更新 system prompt，要求輸出中英雙語結構化摘要
- 修改 `run.sh`：在執行 Agent 後依序執行 `publish.py` 和 `git push`

## Capabilities

### New Capabilities

- `static-site-generator`: 解析 `summaries.md`，生成 `docs/` 下的靜態 HTML 頁面，包含 index、about 及每日獨立頁面
- `bilingual-website`: 所有頁面支援 EN/ZH 語言切換；Agent 輸出格式包含 `<!-- EN -->` 和 `<!-- ZH -->` 雙語內容區塊

### Modified Capabilities

- `summary-writer`: 摘要輸出格式新增雙語分隔符，需包含 `<!-- EN -->` 和 `<!-- ZH -->` 兩個內容區塊
- `scheduler-entrypoint`: `run.sh` 在執行 Agent 後新增 `publish.py` 執行步驟與 `git push` 部署流程

## Impact

- Affected specs: static-site-generator, bilingual-website, summary-writer, scheduler-entrypoint
- Affected code:
  - New: publish.py
  - New: docs/about.html
  - Modified: agent.py
  - Modified: run.sh
