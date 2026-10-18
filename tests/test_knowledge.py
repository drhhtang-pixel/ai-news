import os
import tempfile
import unittest

from knowledge import format_held, hold_old_stories, known_headlines

SUMMARY = """<!-- EN -->
### Headlines

- **New story:** Fresh. *(Sources: Wire, 2026-10-17; Daily, date unknown)*

- **Old story:** Stale. *(Sources: Archive, 2026-09-01; Wire, 2026-10-16)*

- **Undated story:** No dates. *(Sources: Blog, date unknown)*

---

### Analysis
Text.

### Sources
- Wire: https://wire.example/new (published 2026-10-17)
- Daily: https://daily.example/a (published date unknown)
- Archive: https://archive.example/old (published 2026-09-01)
- Wire (old story): https://wire.example/old (published 2026-10-16)
- Blog: https://blog.example/x (published date unknown)

<!-- ZH -->
### 頭條新聞

- **新消息：** 新。*(來源：Wire，2026-10-17；Daily，日期不明)*

- **舊消息：** 舊。*(來源：Archive，2026-09-01；Wire，2026-10-16)*

- **無日期：** 無。*(來源：Blog，日期不明)*

### 分析
文字。

### 來源
- Wire: https://wire.example/new (published 2026-10-17)
- Daily: https://daily.example/a (published date unknown)
- 檔案館: https://archive.example/old (published 2026-09-01)
- Wire（舊消息）: https://wire.example/old (published 2026-10-16)
- Blog: https://blog.example/x (published date unknown)
"""


class HoldOldStoriesTest(unittest.TestCase):
    def test_holds_story_whose_earliest_source_is_over_30_days(self):
        kept, held = hold_old_stories(SUMMARY, "2026-10-18")
        self.assertEqual([h["title"] for h in held], ["Old story"])
        self.assertEqual(held[0]["earliest"], "2026-09-01")
        self.assertEqual(held[0]["sources"][0], ("Archive", "2026-09-01", "https://archive.example/old"))
        self.assertNotIn("- **Old story", kept)
        self.assertNotIn("- **舊消息", kept)
        self.assertIn("New story", kept)
        self.assertIn("無日期", kept)

    def test_sources_removed_by_url_in_both_languages(self):
        kept, _ = hold_old_stories(SUMMARY, "2026-10-18")
        self.assertNotIn("archive.example/old", kept)
        # 'Wire' is also cited by a kept story, so its entries stay -- including the held story's
        # Wire URL, which can't be told apart by name (a harmless leftover Sources line).
        self.assertIn("wire.example/new", kept)
        self.assertIn("wire.example/old", kept)
        self.assertEqual(kept.count("https://blog.example/x"), 2)

    def test_boundary_and_undated(self):
        _, held = hold_old_stories(SUMMARY, "2026-10-01")  # 2026-09-01 is exactly 30 days old
        self.assertEqual(held, [])

    def test_nothing_held_returns_summary_unchanged(self):
        kept, held = hold_old_stories(SUMMARY, "2026-09-15")
        self.assertEqual((kept, held), (SUMMARY, []))

    def test_malformed_summary_is_left_alone(self):
        self.assertEqual(hold_old_stories("no markers", "2026-10-18"), ("no markers", []))

    def test_format_held(self):
        _, held = hold_old_stories(SUMMARY, "2026-10-18")
        body = format_held(held, "2026-10-18")
        self.assertIn("held back 1 story", body)
        self.assertIn("It passed source verification but was **not published**", body)
        self.assertIn("### 1. Old story", body)
        self.assertIn("  - Archive, 2026-09-01: https://archive.example/old", body)


class KnownHeadlinesTest(unittest.TestCase):
    def test_reads_recent_en_headlines_newest_first(self):
        text = (
            "## 2026-08-01 08:00\n\n<!-- EN -->\n### Headlines\n- **Too old:** x\n<!-- ZH -->\n"
            "## 2026-10-10 08:00\n\n<!-- EN -->\n### Headlines\n- **First:** a\n- **Second：** b\n"
            "### Analysis\n- **Not a headline:** c\n<!-- ZH -->\n### 頭條新聞\n- **中文：** d\n"
            "## 2026-10-17 08:00\n\n<!-- EN -->\n### Headlines\n- **Latest:** e\n<!-- ZH -->\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "summaries.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(known_headlines(path, "2026-10-18"), ["Latest", "Second", "First"])

    def test_missing_file(self):
        self.assertEqual(known_headlines("/nonexistent/summaries.md", "2026-10-18"), [])


if __name__ == "__main__":
    unittest.main()
