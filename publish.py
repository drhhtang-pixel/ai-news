import os
import re
from datetime import datetime


SUMMARIES_FILE = "summaries.md"
DOCS_DIR = "docs"


# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_summaries(path: str) -> list[tuple[str, str]]:
    """Return list of (date_str, raw_content) tuples, newest first."""
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return []

    # Split on ## YYYY-MM-DD headers (with optional time)
    pattern = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    sections = []
    for i, match in enumerate(matches):
        date_str = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections.append((date_str, content))

    # Newest first — deduplicate dates by keeping last occurrence per date
    seen = {}
    for date_str, content in sections:
        seen[date_str] = content
    ordered = sorted(seen.items(), reverse=True)
    return ordered


def split_bilingual(content: str) -> tuple[str, str]:
    """Split content into (en_content, zh_content).
    Falls back to (full content, fallback message) for legacy format."""
    en_marker = "<!-- EN -->"
    zh_marker = "<!-- ZH -->"

    en_pos = content.find(en_marker)
    zh_pos = content.find(zh_marker)

    if en_pos == -1 or zh_pos == -1:
        # Legacy format: no bilingual markers
        return content, "(No Chinese version available)"

    en_start = en_pos + len(en_marker)
    en_end = zh_pos
    zh_start = zh_pos + len(zh_marker)

    en_content = content[en_start:en_end].strip()
    zh_content = content[zh_start:].strip()
    return en_content, zh_content


# ── Markdown → HTML (minimal) ──────────────────────────────────────────────────

def md_to_html(text: str) -> str:
    """Convert a subset of Markdown to HTML (headings, bold, bullets, links)."""
    lines = text.split("\n")
    html_lines = []
    in_ul = False

    for line in lines:
        # H3
        if line.startswith("### "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        # H2
        elif line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        # Bullet
        elif line.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(line[2:])}</li>")
        elif line.startswith("* "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(line[2:])}</li>")
        # Horizontal rule
        elif line.strip() in ("---", "***", "___"):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("<hr>")
        # Empty line
        elif line.strip() == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<p>{_inline(line)}</p>")

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _inline(text: str) -> str:
    """Process inline Markdown: bold, links."""
    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" target="_blank">\1</a>',
        text,
    )
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Bare URLs
    text = re.sub(
        r"(?<![\"'=])(https?://\S+)",
        r'<a href="\1" target="_blank">\1</a>',
        text,
    )
    return text


# ── HTML Template ──────────────────────────────────────────────────────────────

_TOGGLE_JS = """
  <script>
    (function () {
      var lang = localStorage.getItem('lang') || 'en';
      document.documentElement.setAttribute('data-lang', lang);
      function applyLang(l) {
        document.querySelectorAll('.lang-en').forEach(function(el) {
          el.style.display = l === 'en' ? '' : 'none';
        });
        document.querySelectorAll('.lang-zh').forEach(function(el) {
          el.style.display = l === 'zh' ? '' : 'none';
        });
        document.querySelectorAll('.lang-btn').forEach(function(btn) {
          btn.classList.toggle('active', btn.dataset.lang === l);
        });
      }
      document.addEventListener('DOMContentLoaded', function () {
        applyLang(lang);
        document.querySelectorAll('.lang-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            lang = btn.dataset.lang;
            localStorage.setItem('lang', lang);
            applyLang(lang);
          });
        });
      });
    })();
  </script>
"""

_CSS = """
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           line-height: 1.7; color: #222; background: #fafafa; }
    .container { max-width: 860px; margin: 0 auto; padding: 2rem 1.5rem; }
    header { display: flex; justify-content: space-between; align-items: center;
             border-bottom: 1px solid #e0e0e0; padding-bottom: 1rem; margin-bottom: 2rem; }
    header h1 { font-size: 1.2rem; font-weight: 600; }
    nav a { color: #555; text-decoration: none; margin-right: 1rem; font-size: 0.9rem; }
    nav a:hover { color: #000; }
    .lang-toggle { display: flex; gap: 0.3rem; }
    .lang-btn { padding: 0.25rem 0.6rem; border: 1px solid #ccc; background: #fff;
                border-radius: 4px; cursor: pointer; font-size: 0.85rem; color: #555; }
    .lang-btn.active { background: #222; color: #fff; border-color: #222; }
    h2 { font-size: 1.6rem; margin: 1.5rem 0 0.5rem; }
    h3 { font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 0.5rem; color: #333; }
    p { margin: 0.6rem 0; }
    ul { padding-left: 1.4rem; margin: 0.5rem 0; }
    li { margin: 0.3rem 0; }
    a { color: #0066cc; }
    hr { border: none; border-top: 1px solid #e0e0e0; margin: 1.5rem 0; }
    strong { font-weight: 600; }
    .date-list { list-style: none; padding: 0; }
    .date-list li { padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }
    .date-list a { font-size: 1rem; font-weight: 500; }
    footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0;
             font-size: 0.8rem; color: #999; }
  </style>
"""


def _page(title: str, body: str, back_link: str = "") -> str:
    nav_back = f'<a href="{back_link}">← Back</a>' if back_link else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
{_CSS}
{_TOGGLE_JS}
</head>
<body>
<div class="container">
  <header>
    <h1><a href="../" style="text-decoration:none;color:inherit;">AI News Monitor</a></h1>
    <nav>
      {nav_back}
      <a href="../">Archive</a>
      <a href="../about.html">About</a>
    </nav>
    <div class="lang-toggle">
      <button class="lang-btn" data-lang="en">EN</button>
      <button class="lang-btn" data-lang="zh">ZH</button>
    </div>
  </header>
  {body}
  <footer>Generated by AI News Monitor &middot; <a href="https://github.com">Source</a></footer>
</div>
</body>
</html>"""


def _index_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
{_CSS}
{_TOGGLE_JS}
</head>
<body>
<div class="container">
  <header>
    <h1><a href="index.html" style="text-decoration:none;color:inherit;">AI News Monitor</a></h1>
    <nav>
      <a href="about.html">About</a>
    </nav>
    <div class="lang-toggle">
      <button class="lang-btn" data-lang="en">EN</button>
      <button class="lang-btn" data-lang="zh">ZH</button>
    </div>
  </header>
  {body}
  <footer>Generated by AI News Monitor</footer>
</div>
</body>
</html>"""


# ── Page generators ────────────────────────────────────────────────────────────

def generate_daily_page(date_str: str, en_content: str, zh_content: str) -> str:
    en_html = md_to_html(en_content)
    zh_html = md_to_html(zh_content)
    body = f"""
    <div class="lang-en">
      <h2>{date_str} — AI News Summary</h2>
      {en_html}
    </div>
    <div class="lang-zh">
      <h2>{date_str} — AI 新聞摘要</h2>
      {zh_html}
    </div>
    """
    return _page(f"AI News {date_str}", body, back_link="../")


def generate_index_page(entries: list[tuple[str, str, str]]) -> str:
    """entries: list of (date_str, en_preview, zh_preview)"""
    en_items = "\n".join(
        f'<li><a href="{d}/">{d}</a></li>' for d, _, __ in entries
    )
    zh_items = "\n".join(
        f'<li><a href="{d}/">{d}</a></li>' for d, _, __ in entries
    )
    body = f"""
    <div class="lang-en">
      <h2>AI News Archive</h2>
      <p>Daily AI news summaries, generated automatically.</p>
      <ul class="date-list">{en_items}</ul>
    </div>
    <div class="lang-zh">
      <h2>AI 新聞彙整</h2>
      <p>每日自動生成的 AI 新聞摘要。</p>
      <ul class="date-list">{zh_items}</ul>
    </div>
    """
    return _index_page("AI News Monitor — Archive", body)


def generate_about_page() -> str:
    body = """
    <div class="lang-en">

      <h2>Part 1 — How the Agent Works</h2>

      <h3>Architecture</h3>
      <pre style="background:#f4f4f4;padding:1rem;border-radius:6px;font-size:0.85rem;line-height:1.6;overflow-x:auto;">
Every day at 08:00
       │
       ▼
  cron / run.sh
       │
       ▼
  agent.py ◄──────────────────────────────────────────────────────┐
       │                                                           │
       │  "Search for AI news"                                     │
       ▼                                                           │
  Claude (claude-sonnet-4-6)                                       │
       │  decides what to search, runs tool calls autonomously     │
       ▼                                                           │
  Tavily Search API  ──── results ────────────────────────────────►│
       (3–10 queries)           Claude synthesises &amp; writes bilingual summary
       │
       ▼
  summaries.md  (append-only, bilingual Markdown)
       │
       ▼
  publish.py  →  docs/YYYY-MM-DD/index.html
             →  docs/index.html  (archive)
             →  docs/about.html
       │
       ▼
  git push  →  GitHub Pages  (public website, zero server cost)
      </pre>

      <h3>What each component does</h3>
      <ul>
        <li><strong>cron + run.sh</strong>: Triggers the entire pipeline daily at 08:00. No human intervention required after setup.</li>
        <li><strong>Claude (claude-sonnet-4-6)</strong>: The "brain" of the agent. It autonomously decides which queries to run, calls the search tool multiple times, then synthesises all results into a structured bilingual summary.</li>
        <li><strong>Tavily Search API</strong>: An AI-optimised search API that returns clean, structured results suitable for LLM consumption — no HTML scraping needed.</li>
        <li><strong>publish.py</strong>: Converts the append-only <code>summaries.md</code> into a static website. Parses dates, splits bilingual content, renders HTML with EN/ZH toggle.</li>
        <li><strong>GitHub Pages</strong>: Serves the static site for free. Each daily page gets a permanent URL (<code>/YYYY-MM-DD/</code>).</li>
      </ul>

      <h3>Why this design?</h3>
      <ul>
        <li><strong>Zero server cost</strong>: Static HTML on GitHub Pages — no cloud compute, no database, no maintenance.</li>
        <li><strong>Fully autonomous</strong>: Once the cron job is set, human involvement is zero. The agent decides its own search strategy each day.</li>
        <li><strong>Permanent archive</strong>: Every daily summary lives at its own URL forever. Nothing is overwritten.</li>
        <li><strong>Single source of truth</strong>: <code>summaries.md</code> is the canonical data store. The website is always regenerable from it.</li>
      </ul>

      <hr>

      <h2>Part 2 — How This Project Was Built (Agentic Coding)</h2>

      <h3>What is Agentic Coding?</h3>
      <p>Agentic coding is not "AI autocomplete." It is a development method where an AI participates in the <em>entire</em> software development lifecycle — understanding requirements, designing architecture, implementing features, and verifying results — while the human makes the high-level decisions and judgment calls.</p>
      <p>The difference: a copilot suggests the next line of code. An agent takes a task description and delivers a working implementation, asking for clarification only when genuinely needed.</p>

      <h3>The development flow used here</h3>
      <p>This project was built using <strong>Spectra</strong>, a spec-driven change management workflow for agentic development:</p>
      <pre style="background:#f4f4f4;padding:1rem;border-radius:6px;font-size:0.85rem;line-height:1.6;overflow-x:auto;">
Human describes requirement
       │
       ▼
/spectra-propose  →  AI writes: proposal.md + design.md + specs + tasks.md
       │              (human reviews &amp; approves before any code is written)
       ▼
/spectra-apply    →  AI implements each task in tasks.md, one by one
       │              (human can inspect, redirect, or veto at any point)
       ▼
/spectra-archive  →  change is archived; specs merged into the main spec index
      </pre>
      <p>This project was delivered in two changes:</p>
      <ul>
        <li><strong>ai-news-monitor-agent</strong>: The core agent — <code>agent.py</code>, <code>tools.py</code>, <code>writer.py</code>, <code>run.sh</code>, cron setup.</li>
        <li><strong>github-pages-website</strong>: The static site generator — <code>publish.py</code>, bilingual HTML templates, GitHub Pages deployment.</li>
      </ul>

      <h3>What AI did vs. what the human did</h3>
      <ul>
        <li><strong>Human</strong>: Described the goal ("I want an AI agent that monitors AI news and publishes it online"), made architectural choices (GitHub Pages over a server, bilingual EN/ZH, cron over cloud scheduling), reviewed specs before implementation.</li>
        <li><strong>AI</strong>: Wrote every proposal, design doc, spec, and task list. Implemented all code. Fixed bugs when they appeared. Translated the first summary retroactively into Chinese.</li>
      </ul>

      <h3>The key insight</h3>
      <p>This project is a double demonstration of agentic AI:</p>
      <ul>
        <li>The <strong>product</strong> (the news monitor) is an AI agent that acts autonomously every day.</li>
        <li>The <strong>process</strong> (how it was built) was itself agentic — AI drove implementation from spec to deployed code.</li>
      </ul>
      <p>The same reasoning that makes an AI agent useful for searching the web also makes it useful for writing software: give it a clear goal, the right tools, and the autonomy to decide how to proceed.</p>

      <h3>Tech stack</h3>
      <ul>
        <li>Python 3.12 · Anthropic SDK · Tavily API</li>
        <li>GitHub Pages (static hosting, zero cost)</li>
        <li>Vanilla HTML/CSS/JS (no frameworks)</li>
        <li>Spectra (agentic change management) · Claude Code (AI development environment)</li>
      </ul>

      <hr>

      <h2>Part 3 — Debate: Is This Really Agentic AI?</h2>
      <p>Two AI agents disagree on this question.</p>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1.5rem;">

        <div style="border:2px solid #2a7a2a;border-radius:8px;padding:1.2rem;">
          <p style="font-weight:700;color:#2a7a2a;margin-bottom:0.8rem;">🟢 Agent A — Yes, this is Agentic AI</p>
          <p><strong>Autonomous decision-making</strong>: The agent doesn't follow a fixed script — it decides what to search, when to stop, and how to synthesise results. Its search strategy differs on every run.</p>
          <p><strong>Tool use</strong>: The agent dynamically calls an external tool (Tavily) inside its reasoning loop and decides whether to search again based on what it finds. This is exactly the definition of a tool-use agent.</p>
          <p><strong>Goal-directed behaviour</strong>: Given a high-level objective ("summarise today's AI news"), the agent plans its own path to completion without step-by-step instructions.</p>
          <p><strong>Zero human intervention</strong>: From trigger to deployment, the entire pipeline runs without human input. Autonomy is the core criterion — and this project has it.</p>
          <p><strong>Verdict</strong>: Autonomy + tool use + goal-directed behaviour = Agentic AI. This project qualifies on all counts.</p>
        </div>

        <div style="border:2px solid #a0522d;border-radius:8px;padding:1.2rem;">
          <p style="font-weight:700;color:#a0522d;margin-bottom:0.8rem;">🟠 Agent B — Not enough — here's what's missing</p>
          <p><strong>No memory</strong>: Every run starts from scratch. A truly agentic system would remember what it searched last week, which sources proved reliable, and which trends are building — then adjust today's strategy accordingly.</p>
          <p><strong>No self-evaluation</strong>: The agent has no idea whether its summary is good. Agentic AI should evaluate its own output, detect gaps, and retry with a different approach (reflection loop).</p>
          <p><strong>No planning</strong>: The agent only does search → synthesise → output. A stronger agent would form a plan, decompose sub-goals, and replan when it hits obstacles.</p>
          <p><strong>No initiative</strong>: The task is human-defined ("search AI news"). The agent never discovers new topics worth tracking or expands its own scope.</p>
          <p><strong>Verdict</strong>: This is an LLM automation with tools — useful, but true agentic AI also needs memory, reflection, planning, and initiative.</p>
        </div>

      </div>

      <p style="margin-top:1.5rem;font-style:italic;color:#555;">Both agents make valid points. This project demonstrates the core traits of agentic AI — autonomous tool use and goal-directed behaviour — while being honest about its current limits. Agentic AI is a spectrum, not a binary label.</p>

    </div>
    <div class="lang-zh">

      <h2>第一部分 — 這個 Agent 怎麼運作？</h2>

      <h3>系統架構</h3>
      <pre style="background:#f4f4f4;padding:1rem;border-radius:6px;font-size:0.85rem;line-height:1.6;overflow-x:auto;">
每天早上 08:00
       │
       ▼
  cron / run.sh
       │
       ▼
  agent.py ◄──────────────────────────────────────────────────────┐
       │                                                           │
       │  「搜尋 AI 新聞」                                          │
       ▼                                                           │
  Claude（claude-sonnet-4-6）                                       │
       │  自主決定搜尋策略，執行工具呼叫                             │
       ▼                                                           │
  Tavily Search API  ──── 搜尋結果 ──────────────────────────────►│
       （執行 3–10 次查詢）     Claude 整合結果，生成中英雙語摘要
       │
       ▼
  summaries.md（只增不改，雙語 Markdown）
       │
       ▼
  publish.py  →  docs/YYYY-MM-DD/index.html（每日頁面）
             →  docs/index.html（過往摘要索引）
             →  docs/about.html（本頁）
       │
       ▼
  git push  →  GitHub Pages（公開網站，零伺服器成本）
      </pre>

      <h3>各元件功能說明</h3>
      <ul>
        <li><strong>cron + run.sh</strong>：每天早上 08:00 自動觸發整條流程，設定完成後不需要任何人工操作。</li>
        <li><strong>Claude（claude-sonnet-4-6）</strong>：Agent 的「大腦」。自主決定要搜尋什麼、多次呼叫搜尋工具，最後將所有結果整合為結構化的中英雙語摘要。</li>
        <li><strong>Tavily Search API</strong>：專為 AI 應用優化的搜尋 API，回傳乾淨的結構化結果，不需要解析 HTML。</li>
        <li><strong>publish.py</strong>：將只增不改的 <code>summaries.md</code> 轉換為靜態網站。解析日期、拆分雙語內容、生成含語言切換功能的 HTML 頁面。</li>
        <li><strong>GitHub Pages</strong>：免費提供靜態網站服務。每個每日頁面都有永久的 URL（<code>/YYYY-MM-DD/</code>）。</li>
      </ul>

      <h3>為什麼這樣設計？</h3>
      <ul>
        <li><strong>零伺服器成本</strong>：GitHub Pages 提供靜態 HTML 托管，不需要雲端運算、資料庫或維運。</li>
        <li><strong>全自動運行</strong>：cron job 設定完成後，人工介入次數為零。Agent 每天自行決定搜尋策略。</li>
        <li><strong>永久保存</strong>：每天的摘要都有自己的 URL，永遠不會被覆蓋。</li>
        <li><strong>單一資料來源</strong>：<code>summaries.md</code> 是唯一的資料儲存。網站隨時可以從它重新生成。</li>
      </ul>

      <hr>

      <h2>第二部分 — 這個專案怎麼被做出來的（Agentic Coding）</h2>

      <h3>什麼是 Agentic Coding？</h3>
      <p>Agentic Coding 不是「AI 幫你補全程式碼」。它是一種開發方法，讓 AI 參與完整的軟體開發流程——理解需求、設計架構、實作功能、驗收結果——而人負責做高層次的判斷與決策。</p>
      <p>差別在這裡：Copilot 建議下一行程式碼；Agent 接收任務描述，交付可運行的實作，只在真正不確定時才提問。</p>

      <h3>本專案使用的開發流程</h3>
      <p>本專案使用 <strong>Spectra</strong>——一套以 spec 為核心的 agentic 開發變更管理流程：</p>
      <pre style="background:#f4f4f4;padding:1rem;border-radius:6px;font-size:0.85rem;line-height:1.6;overflow-x:auto;">
人描述需求
       │
       ▼
/spectra-propose  →  AI 撰寫：proposal.md + design.md + specs + tasks.md
       │              （人在任何程式碼撰寫前先審閱並確認）
       ▼
/spectra-apply    →  AI 逐一實作 tasks.md 中的每個任務
       │              （人可以隨時查看、調整方向或否決）
       ▼
/spectra-archive  →  變更歸檔，spec 合併進主 spec 索引
      </pre>
      <p>本專案分兩個 change 完成：</p>
      <ul>
        <li><strong>ai-news-monitor-agent</strong>：核心 Agent——<code>agent.py</code>、<code>tools.py</code>、<code>writer.py</code>、<code>run.sh</code>、cron 設定。</li>
        <li><strong>github-pages-website</strong>：靜態網站生成器——<code>publish.py</code>、雙語 HTML 模板、GitHub Pages 部署。</li>
      </ul>

      <h3>AI 做了什麼，人做了什麼</h3>
      <ul>
        <li><strong>人</strong>：描述目標（「我要一個 AI Agent 監控 AI 新聞並發布上網」）、做架構決策（GitHub Pages 而非伺服器、中英雙語、cron 而非雲端排程）、在實作前審閱 spec。</li>
        <li><strong>AI</strong>：撰寫所有 proposal、設計文件、spec 和任務清單。實作所有程式碼。發現 bug 時自行修復。將舊版摘要補譯為中文。</li>
      </ul>

      <h3>核心洞察</h3>
      <p>這個專案是 agentic AI 的雙重示範：</p>
      <ul>
        <li><strong>產品</strong>（新聞監控器）是一個每天自主運行的 AI Agent。</li>
        <li><strong>過程</strong>（開發本身）也是 agentic 的——AI 從 spec 到部署，驅動了整個實作流程。</li>
      </ul>
      <p>讓 AI Agent 能有效搜尋網路的同樣邏輯，也讓它能有效撰寫軟體：給它明確的目標、適當的工具，以及自主決定執行方式的空間。</p>

      <h3>技術架構</h3>
      <ul>
        <li>Python 3.12 · Anthropic SDK · Tavily API</li>
        <li>GitHub Pages（靜態托管，完全免費）</li>
        <li>純 HTML/CSS/JS（無前端框架）</li>
        <li>Spectra（Agentic 變更管理）· Claude Code（AI 開發環境）</li>
      </ul>

      <hr>

      <h2>第三部分 — 辯論：這真的是 Agentic AI 嗎？</h2>
      <p>兩個 AI Agent 對這個問題看法不一。</p>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1.5rem;">

        <div style="border:2px solid #2a7a2a;border-radius:8px;padding:1.2rem;">
          <p style="font-weight:700;color:#2a7a2a;margin-bottom:0.8rem;">🟢 Agent A — 這就是 Agentic AI</p>
          <p><strong>自主決策</strong>：Agent 不是執行固定腳本——它決定搜尋什麼、何時停止、如何綜合結果。每次執行的搜尋策略都不同。</p>
          <p><strong>工具使用</strong>：Agent 在推理循環中動態呼叫外部工具（Tavily），根據結果決定是否繼續搜尋。這正是 tool-use agent 的定義。</p>
          <p><strong>目標導向</strong>：給定一個高層次目標（「摘要今日 AI 新聞」），Agent 自行規劃達成路徑，不需要逐步指令。</p>
          <p><strong>無人介入</strong>：從觸發到部署，整條流程零人工操作。這是自主性（autonomy）的核心定義。</p>
          <p><strong>結論</strong>：自主性 + 工具使用 + 目標導向行為 = Agentic AI。這個專案完全符合。</p>
        </div>

        <div style="border:2px solid #a0522d;border-radius:8px;padding:1.2rem;">
          <p style="font-weight:700;color:#a0522d;margin-bottom:0.8rem;">🟠 Agent B — 還不夠，缺少這些</p>
          <p><strong>沒有記憶</strong>：每次執行都從零開始。真正的 agentic 系統會記住過去搜尋了什麼、哪些來源可信、上週的重要趨勢——然後據此調整今天的策略。</p>
          <p><strong>沒有自我評估</strong>：Agent 不知道自己的摘要品質好不好。Agentic AI 應該能評估輸出、發現不足，並重新嘗試（reflection loop）。</p>
          <p><strong>沒有規劃</strong>：Agent 只會「搜尋 → 整合 → 輸出」。更強的 agent 會先制定計劃、分解子任務，並在遇到障礙時重新規劃。</p>
          <p><strong>沒有主動性</strong>：任務由人定義（「搜尋 AI 新聞」），Agent 不會自行發現值得追蹤的新領域或調整任務範圍。</p>
          <p><strong>結論</strong>：這是一個有工具的 LLM 自動化流程，但真正的 agentic AI 還需要記憶、反思、規劃與主動性。</p>
        </div>

      </div>

      <p style="margin-top:1.5rem;font-style:italic;color:#555;">兩個 Agent 都有道理。這個專案示範了 agentic AI 的核心特徵——自主工具使用與目標導向行為——同時也誠實地呈現了現階段的限制。Agentic AI 是一個光譜，不是二元標籤。</p>

    </div>
    """
    return _index_page("AI News Monitor — About", body)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    sections = parse_summaries(SUMMARIES_FILE)
    entries = []

    for date_str, raw_content in sections:
        en_content, zh_content = split_bilingual(raw_content)
        html = generate_daily_page(date_str, en_content, zh_content)

        page_dir = os.path.join(DOCS_DIR, date_str)
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

        entries.append((date_str, en_content[:100], zh_content[:100]))

    # Regenerate index
    index_html = generate_index_page(entries)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # Create about.html only if absent
    about_path = os.path.join(DOCS_DIR, "about.html")
    if not os.path.exists(about_path):
        with open(about_path, "w", encoding="utf-8") as f:
            f.write(generate_about_page())

    print(f"Published {len(entries)} pages to {DOCS_DIR}/")


if __name__ == "__main__":
    main()
