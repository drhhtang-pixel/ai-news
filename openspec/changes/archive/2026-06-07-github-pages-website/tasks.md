## 1. 更新 Agent 雙語輸出

- [x] 1.1 修改 `agent.py` 中的 system prompt，實作「summaries.md 雙語格式使用 HTML 注釋分隔」設計決策：要求 Claude 一次輸出中英雙語結構，先輸出 `<!-- EN -->` 區塊（含 `### Headlines`、`### Analysis`、`### Sources`），再輸出 `<!-- ZH -->` 區塊（含 `### 頭條新聞`、`### 分析`、`### 來源`）— 滿足「Agent output includes both EN and ZH content blocks」與「Summary is structured Markdown（雙語版）」。驗證方式：執行 `python3 agent.py` 後，檢查 `summaries.md` 最新區塊中同時包含 `<!-- EN -->` 和 `<!-- ZH -->` 標記。

## 2. 實作靜態網站生成器

- [x] 2.1 建立 `publish.py`：以正規表示式 `^## \d{4}-\d{2}-\d{2}` 將 `summaries.md` 拆分為各日期區塊，提取日期字串（`YYYY-MM-DD`）與內容 — 這是 `publish.py generates daily HTML pages` 的基礎解析邏輯。驗證方式：在 Python REPL 中 import publish 並對測試字串呼叫解析函式，確認回傳正確的日期與內容對。

- [x] 2.2 在 `publish.py` 中實作雙語內容提取：依 `<!-- EN -->` 和 `<!-- ZH -->` 分隔符將每個區塊內容拆為 `en_content` 和 `zh_content` 字串；對不含分隔符的舊格式區塊，`en_content` 設為完整內容，`zh_content` 設為 `(No Chinese version available)` — 滿足「publish.py handles legacy summaries without bilingual delimiters」。驗證方式：對含舊格式與新格式的測試字串各呼叫一次，確認回傳值符合預期。

- [x] 2.3 在 `publish.py` 中實作 HTML 頁面模板，採用「語言切換使用原生 JavaScript classList toggle」設計決策：生成含語言切換按鈕（右上角 `EN | ZH`）、`<div class="lang-en">` 和 `<div class="lang-zh">` 兩個內容區塊，以及 localStorage 語言偏好邏輯（key: `lang`，預設 `en`）的完整 HTML 字串 — 滿足「Every page has an EN/ZH language toggle button」與「Language preference is persisted in localStorage」。驗證方式：在瀏覽器中開啟生成的 HTML，點擊切換按鈕確認 EN/ZH 內容正確顯示/隱藏，重新整理後語言偏好保留。

- [x] 2.4 在 `publish.py` 中實作每日頁面輸出，採用「每日頁面採用子目錄結構」與「publish.py 使用純 Python 生成 HTML，不依賴框架」設計決策：對每個日期區塊，將套用模板後的 HTML 寫入 `docs/YYYY-MM-DD/index.html`（不存在的目錄自動建立）— 滿足「publish.py generates daily HTML pages from summaries.md」。驗證方式：執行 `python3 publish.py` 後，確認 `docs/2026-06-07/index.html` 存在且包含摘要內容。

- [x] 2.5 在 `publish.py` 中實作 index 頁面生成：每次執行時重新生成 `docs/index.html`，列出所有日期連結（最新在前）以及導覽至 about 頁的連結 — 滿足「publish.py generates an index page listing all summaries」。驗證方式：執行後在瀏覽器開啟 `docs/index.html`，確認日期列表由新到舊排列，點擊連結能進入對應頁面。

- [x] 2.6 在 `publish.py` 中實作 about.html 生成邏輯：若 `docs/about.html` 不存在則建立，包含中英雙語說明（EN：描述 Agent 運作原理；ZH：同內容繁體中文版）；若已存在則不覆蓋 — 滿足「publish.py creates docs/about.html if absent」。驗證方式：首次執行時確認 `docs/about.html` 被建立；第二次執行時修改檔案內容，確認修改被保留。

- [x] 2.7 在 `publish.py` 最後加入完成訊息：印出 `Published N pages to docs/`，其中 N 為當次生成的每日頁面數量 — 滿足「publish.py reports completion to stdout」。驗證方式：執行 `python3 publish.py` 後確認 stdout 包含正確頁數的訊息。

## 3. 更新排程入口

- [x] 3.1 修改 `run.sh`：在 `python3 agent.py` 成功執行後，依序執行 `python3 publish.py`、`git -C "$SCRIPT_DIR" add docs/ summaries.md`、`git -C "$SCRIPT_DIR" commit -m "Daily summary $(date +%Y-%m-%d)"`、`git -C "$SCRIPT_DIR" push`；git push 失敗時印出錯誤至 stderr 但 exit 0 — 滿足「run.sh provides a cron-compatible wrapper（含 publish 與 git push）」。驗證方式：在已初始化 git remote 的環境中執行 `bash run.sh`，確認 `docs/` 更新並出現在 GitHub repo。

## 4. 初始化 GitHub 部署

- [x] 4.1 初始化 git repo 並設定 remote，實作「GitHub Pages 從 docs/ 目錄提供服務」部署設計：在專案目錄執行 `git init`（若尚未初始化）、建立 `.gitignore`（排除 `.env`、`__pycache__/`、`*.pyc`、`summaries.md` 不排除），執行首次 `git add . && git commit -m "Initial commit" && git push -u origin main`，並在 GitHub repo Settings → Pages → Source 設定 main branch / docs 資料夾。驗證方式：`git remote -v` 顯示正確的 origin URL；GitHub Pages 顯示網站 URL。

## 5. 歸檔後補充：改用 launchd 排程

- [x] 5.1 以 macOS launchd 取代 cron：建立 `~/Library/LaunchAgents/com.drhhtang.ainews.plist`，設定每天 08:00 執行 `run.sh`，並以 `launchctl load` 載入；移除原 crontab 條目。原因：cron 在電腦睡眠時直接跳過排程，launchd 醒機後會補跑，確保每日摘要不漏跑。

- [x] 5.2 更新 `docs/about.html` 中英文版本，將所有 `cron` 相關描述改為 `launchd`，包含架構圖、元件說明、「為什麼這樣設計」及開發歷程段落（共 9 處）。

- [x] 5.3 更新 `openspec/specs/scheduler-entrypoint/spec.md`，將 7 處 cron 相關描述改為 launchd：overview 描述、退出碼 requirement、環境變數 requirement、wrapper requirement 標題、invocation scenario、scheduling comment scenario，以及 Implementation Notes（新增 plist 路徑與補跑說明，保留原 cron 注釋供非 macOS 環境參考）。

- [x] 5.4 在 `docs/about.html` 中英文版 Part 2 新增「完整紀錄是公開的 / The full record is public」段落：說明 `openspec/` 目錄結構、附上 GitHub 公開連結，並說明每個決策的脈絡都記錄於人類可讀的文件中。
