## Context

現有系統每天由 Mac cron 執行 `run.sh`，呼叫 `agent.py` 搜尋 AI 新聞，並將摘要附加到本機的 `summaries.md`。本次變更在此基礎上新增靜態網站生成與 GitHub Pages 部署，無需後端伺服器。

現有限制：
- `summaries.md` 採用 `## YYYY-MM-DD HH:MM` 分隔每日內容，目前為純英文
- Agent 每天跑一次，輸出追加至單一檔案
- 現有 `run.sh` 不包含版本控制操作

## Goals / Non-Goals

**Goals:**
- 每日摘要有獨立的永久 URL（`/YYYY-MM-DD/`）
- 全站支援 EN/ZH 語言切換，狀態由 localStorage 記憶
- Agent 一次 API call 生成中英雙語內容
- 零伺服器成本，完全靜態

**Non-Goals:**
- 不支援留言或互動功能
- 不提供 RSS feed
- 不做搜尋功能
- 不在雲端執行 Agent（Agent 繼續在本機 Mac 執行）

## Decisions

### summaries.md 雙語格式使用 HTML 注釋分隔

每個日期區塊內用 `<!-- EN -->` 和 `<!-- ZH -->` 作為語言分隔符：

```
## 2026-06-07 09:52

<!-- EN -->
### Headlines
...
### Analysis
...
### Sources
...

<!-- ZH -->
### 頭條新聞
...
### 分析
...
### 來源
...
```

替代方案考量：YAML frontmatter（需改寫 writer.py 結構）、獨立雙語檔案（git push 需管理兩個檔案）。HTML 注釋方案最輕量，writer.py 無需修改。

### publish.py 使用純 Python 生成 HTML，不依賴框架

不採用 Jekyll / Hugo 等靜態網站生成器，原因：需要額外學習成本且與 Python 生態不一致。`publish.py` 用 Python 內建的字串處理解析 `summaries.md`，用 f-string 生成 HTML，無第三方依賴。

### 語言切換使用原生 JavaScript classList toggle

每頁包含兩個 `<div>`：`<div class="lang-en">` 和 `<div class="lang-zh">`。切換按鈕觸發 JS，隱藏其中一個並以 localStorage 記住偏好。不採用 React/Vue，因為頁面為靜態內容，不需要狀態管理框架。

### GitHub Pages 從 docs/ 目錄提供服務

在 GitHub repo 設定中選擇「Deploy from branch: main, folder: /docs」。相對於獨立的 `gh-pages` branch，此方案讓程式碼與網站內容在同一 branch，git 操作更簡單。

### 每日頁面採用子目錄結構

URL 格式：`yourname.github.io/ai-news/2026-06-07/`（而非 `2026-06-07.html`）。子目錄讓 URL 不帶副檔名，更簡潔，且未來如需在頁面旁加入其他資源也有空間。

## Implementation Contract

**`agent.py` system prompt 修改：**
- 新 system prompt 要求 Claude 輸出格式必須包含 `<!-- EN -->` 區塊（含 `### Headlines`、`### Analysis`、`### Sources`）和 `<!-- ZH -->` 區塊（含 `### 頭條新聞`、`### 分析`、`### 來源`）
- `<!-- EN -->` 必須在 `<!-- ZH -->` 之前
- writer.py 不需修改；雙語文字直接由 Claude 生成後寫入 summaries.md

**`publish.py` 行為：**
- 讀取 `summaries.md`，以 `^## \d{4}-\d{2}-\d{2}` 正規表示式分割為各日期區塊
- 對每個區塊，依 `<!-- EN -->` 和 `<!-- ZH -->` 分隔符提取雙語內容
- 輸出：`docs/YYYY-MM-DD/index.html`（每日頁面）、`docs/index.html`（最新日期列表）、`docs/about.html`（靜態說明頁，若不存在則建立）
- `docs/` 目錄不存在時自動建立
- 每次執行時完整重新生成 `docs/index.html` 和所有每日頁面
- 執行完畢印出：`Published N pages to docs/`

**語言切換介面：**
- 每頁右上角有 `EN | ZH` 切換按鈕
- 預設顯示語言：若 localStorage 有 `lang` 鍵則使用，否則預設 `en`
- 切換時同步更新所有具 `lang-en` / `lang-zh` class 的元素可見性

**`run.sh` 新流程：**
```
python3 agent.py
python3 publish.py
git -C "$SCRIPT_DIR" add docs/ summaries.md
git -C "$SCRIPT_DIR" commit -m "Daily summary $(date +%Y-%m-%d)"
git -C "$SCRIPT_DIR" push
```
- git 操作失敗（如網路中斷）時印出錯誤訊息，但不影響 exit code（Agent 已成功跑完）

**驗收條件：**
- 執行 `python3 publish.py` 後，`docs/` 下有對應日期的子目錄
- 在瀏覽器開啟 `docs/index.html`，能看到日期列表並點入每日頁面
- 點擊語言切換按鈕，EN/ZH 內容正確切換；重新整理頁面後語言偏好保留
- `run.sh` 執行後，變更自動推送到 GitHub，GitHub Pages 更新

**範圍邊界：**
- 範圍內：publish.py、docs/ HTML 頁面、agent.py prompt 修改、run.sh 修改
- 範圍外：GitHub repo 建立、GitHub Pages 設定（需使用者手動操作）

## Risks / Trade-offs

- [summaries.md 舊格式與新格式不相容] → 緩解：publish.py 解析時對不含 `<!-- EN -->` 的舊區塊，整個內容視為英文，ZH 顯示「（無中文版本）」
- [git push 需要 SSH key 或 Personal Access Token 設定] → 緩解：在 Migration Plan 中說明設定步驟
- [docs/ 資料夾隨時間增長] → 無影響，靜態 HTML 極小，數年份也不到 10MB

## Migration Plan

1. 在 GitHub 建立新 repo（例如 `ai-news`）
2. 將本機專案目錄初始化為 git repo：`git init && git remote add origin <repo-url>`
3. 首次執行 `python3 publish.py` 生成 `docs/`
4. `git add . && git commit -m "Initial commit" && git push -u origin main`
5. 在 GitHub repo Settings → Pages → Source 選擇 `main` branch，`/docs` 資料夾
6. 之後每天 cron 自動執行，無需手動操作
