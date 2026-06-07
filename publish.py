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
    <h1><a href="/" style="text-decoration:none;color:inherit;">AI News Monitor</a></h1>
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
    <h1>AI News Monitor</h1>
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
      <h2>About This Project</h2>
      <h3>What it does</h3>
      <p>AI News Monitor is an autonomous agent that searches the web for the latest AI news every day and publishes a structured bilingual summary.</p>
      <h3>How it works</h3>
      <ul>
        <li><strong>Schedule</strong>: A cron job runs <code>run.sh</code> every day at 08:00.</li>
        <li><strong>Search</strong>: Claude (claude-sonnet-4-6) uses the Tavily search API to find current AI news, running 3–10 targeted queries autonomously.</li>
        <li><strong>Summarise</strong>: Claude synthesises results into a structured Markdown summary with Headlines, Analysis, and Sources — in both English and Traditional Chinese.</li>
        <li><strong>Publish</strong>: <code>publish.py</code> converts the summaries into static HTML pages and <code>git push</code> deploys them to GitHub Pages automatically.</li>
      </ul>
      <h3>Tech stack</h3>
      <ul>
        <li>Python 3.12 · Anthropic SDK · Tavily API</li>
        <li>GitHub Pages (static hosting, zero cost)</li>
        <li>Vanilla HTML/CSS/JS (no frameworks)</li>
      </ul>
    </div>
    <div class="lang-zh">
      <h2>關於本專案</h2>
      <h3>功能說明</h3>
      <p>AI 新聞監控器是一個自主運行的 Agent，每天自動搜尋最新 AI 資訊，並發布中英雙語結構化摘要。</p>
      <h3>運作原理</h3>
      <ul>
        <li><strong>排程</strong>：每天早上 08:00，cron 自動執行 <code>run.sh</code>。</li>
        <li><strong>搜尋</strong>：Claude（claude-sonnet-4-6）透過 Tavily 搜尋 API 自主決定搜尋策略，執行 3–10 次針對性查詢。</li>
        <li><strong>摘要</strong>：Claude 將搜尋結果整理為包含頭條新聞、分析與來源的結構化 Markdown，同時提供中英兩個版本。</li>
        <li><strong>發布</strong>：<code>publish.py</code> 將摘要轉換為靜態 HTML 頁面，並透過 <code>git push</code> 自動部署至 GitHub Pages。</li>
      </ul>
      <h3>技術架構</h3>
      <ul>
        <li>Python 3.12 · Anthropic SDK · Tavily API</li>
        <li>GitHub Pages（靜態托管，完全免費）</li>
        <li>純 HTML/CSS/JS（無前端框架）</li>
      </ul>
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
