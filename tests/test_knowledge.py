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
        self.assertEqual(held[0]["sources"][0], ("Archive", "https://archive.example/old", "2026-09-01"))
        self.assertNotIn("- **Old story", kept)
        self.assertNotIn("- **舊消息", kept)
        self.assertIn("New story", kept)
        self.assertIn("無日期", kept)

    def test_sources_removed_by_url_in_both_languages(self):
        kept, _ = hold_old_stories(SUMMARY, "2026-10-18")
        self.assertNotIn("archive.example/old", kept)
        # Two "Wire" entries: the cited date picks the right one, so only the held story's
        # Wire article is removed (Codex review #3).
        self.assertIn("wire.example/new", kept)
        self.assertNotIn("wire.example/old", kept)
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
        self.assertIn("It passed source verification, and it was **not published**", body)
        self.assertIn("### 1. Old story", body)
        self.assertIn("  - Archive, 2026-09-01: https://archive.example/old", body)

    def test_linked_citations_carry_their_own_urls(self):
        summary = SUMMARY.replace(
            "*(Sources: Archive, 2026-09-01; Wire, 2026-10-16)*",
            "*(Sources: [Archive](https://archive.example/old), 2026-09-01; [Wire](https://wire.example/old), 2026-10-16)*")
        _, held = hold_old_stories(summary, "2026-10-18")
        self.assertEqual(held[0]["sources"], [("Archive", "https://archive.example/old", "2026-09-01"),
                                              ("Wire", "https://wire.example/old", "2026-10-16")])

    def test_url_with_parentheses_keeps_its_date(self):
        # Codex review R2-1: an older source whose URL contains ")" must still count for age.
        line = ("- **Story:** x. *(Sources: [Wire](https://wire.example/Story_(AI)), 2026-09-01; "
                "[Daily](https://daily.example/new), 2026-10-17)*")
        from knowledge import citation_earliest_date, citation_sources
        self.assertEqual(citation_sources(line), [
            ("Wire", "https://wire.example/Story_(AI)", "2026-09-01"),
            ("Daily", "https://daily.example/new", "2026-10-17"),
        ])
        self.assertEqual(citation_earliest_date(line), "2026-09-01")
        summary = SUMMARY.replace("- **New story:** Fresh. *(Sources: Wire, 2026-10-17; Daily, date unknown)*", line)
        _, held = hold_old_stories(summary, "2026-10-18")
        self.assertIn("Story", [h["title"] for h in held])

    def test_dates_in_urls_and_names_do_not_count(self):
        # Codex review R3-1: only each source's date field decides a story's age.
        from knowledge import citation_earliest_date
        recent_url = ("- **Fresh:** x. *(Sources: [Wire](https://wire.example/2020-01-01-retrospective), "
                      "2026-10-17)*")
        self.assertEqual(citation_earliest_date(recent_url), "2026-10-17")
        unknown_query = "- **Fresh:** x. *(Sources: [Wire](https://wire.example/a?event=2020-01-01), date unknown)*"
        self.assertIsNone(citation_earliest_date(unknown_query))
        dated_name = "- **Fresh:** x. *(Sources: [Archive 2020-01-01 edition](https://a.example/x), 2026-10-17)*"
        self.assertEqual(citation_earliest_date(dated_name), "2026-10-17")
        plain_dated_name = "- **Fresh:** x. *(Sources: Archive 2020-01-01 edition, 2026-10-17)*"
        self.assertEqual(citation_earliest_date(plain_dated_name), "2026-10-17")
        summary = SUMMARY.replace("- **New story:** Fresh. *(Sources: Wire, 2026-10-17; Daily, date unknown)*",
                                  recent_url).replace(
            "- **Undated story:** No dates. *(Sources: Blog, date unknown)*", unknown_query)
        _, held = hold_old_stories(summary, "2026-10-18")
        self.assertEqual([h["title"] for h in held], ["Old story"])  # only the genuinely old one

    def test_unparseable_links_with_commas_do_not_leak_url_dates(self):
        # Codex review R4-1: nested parentheses defeat link parsing; commas in the name or URL
        # must still not make a URL date count. Only the trailing date field may.
        from knowledge import _clean_source, citation_earliest_date
        nested = "https://wire.example/Story_(AI_(history))/2020-01-01"
        self.assertIsNotNone(_clean_source({"name": "Smith, Jones & Co", "url": nested, "date": "2026-10-17"}))
        cases = {
            f"[Smith, Jones & Co]({nested}), 2026-10-17": "2026-10-17",
            f"[Smith, Jones & Co]({nested}), date unknown": None,
            "[Wire](https://wire.example/Story_(AI_(history))?event=x,2020-01-01), 2026-10-17": "2026-10-17",
            "[Wire](https://wire.example/Story_(AI_(history))?event=x,2020-01-01), date unknown": None,
            "Smith, Archive 2020-01-01 edition, 2026-10-17": "2026-10-17",
            "[Wire](https://wire.example/x), , 2026-10-17": "2026-10-17",
        }
        for citation, expected in cases.items():
            line = f"- **Fresh:** x. *(Sources: {citation})*"
            self.assertEqual(citation_earliest_date(line), expected, citation)
        # A genuinely old source next to a recent one still decides the age (R2-1).
        mixed = (f"- **Old:** x. *(Sources: [Smith, Jones & Co]({nested}), 2026-09-01; "
                 "[Daily](https://daily.example/new), 2026-10-17)*")
        self.assertEqual(citation_earliest_date(mixed), "2026-09-01")

    def test_semicolons_in_source_names_cannot_fake_a_date_field(self):
        # Codex review R5-1: a name like "Archive, 2020-01-01; News" must not split into a
        # fake source that ends in a date. Built through the real apply_verification path.
        from knowledge import _clean_source, apply_verification, citation_earliest_date, headline_items
        for name in ("Archive, 2020-01-01; News", "Archive，2020-01-01；News"):
            for date, expected in (("2026-10-17", "2026-10-17"), ("unknown", None)):
                decisions = [
                    {"index": 1, "action": "keep", "sources": [
                        {"name": name, "url": "https://wire.example/x", "date": date}]},
                    {"index": 2, "action": "remove", "sources": []},
                    {"index": 3, "action": "remove", "sources": []},
                ]
                en, _ = headline_items(apply_verification(SUMMARY, decisions))
                self.assertEqual(citation_earliest_date(en[0]), expected, (name, date, en[0]))
                self.assertNotIn(";", en[0].split("](")[0])
        # A genuinely old date in the date field still wins.
        decisions = [{"index": 1, "action": "keep", "sources": [
            {"name": "Archive, 2020-01-01; News", "url": "https://wire.example/x", "date": "2026-09-01"},
            {"name": "Daily", "url": "https://daily.example/new", "date": "2026-10-17"}]},
            {"index": 2, "action": "remove", "sources": []}, {"index": 3, "action": "remove", "sources": []}]
        en, _ = headline_items(apply_verification(SUMMARY, decisions))
        self.assertEqual(citation_earliest_date(en[0]), "2026-09-01")
        # URLs may not carry a full-width separator; an ASCII ";" without a space is fine.
        self.assertIsNone(_clean_source({"name": "W", "url": "https://wire.example/x,2020-01-01；tail", "date": ""}))
        self.assertIsNotNone(_clean_source({"name": "W", "url": "https://wire.example/a;b", "date": ""}))
        self.assertEqual(_clean_source({"name": "A; B", "url": "https://x.example", "date": ""})[0], "A, B")

    def test_whitespace_in_source_names_keeps_citations_on_one_line(self):
        # Codex review R6-1: a name with leading/trailing newlines must not split the citation,
        # or the real old date is lost and the story is published instead of held.
        from knowledge import _clean_source, apply_verification, hold_old_stories
        for name in ("\nWire\n", "\tWire\t", "\u3000Wire\u3000", "Wi\nre", "Wire\u2028", "\x85Wire"):
            decisions = [{"index": 1, "action": "keep", "sources": [
                {"name": name, "url": "https://wire.example/old", "date": "2026-09-01"}]},
                {"index": 2, "action": "remove", "sources": []}, {"index": 3, "action": "remove", "sources": []}]
            summary = apply_verification(SUMMARY, decisions)
            _, held = hold_old_stories(summary, "2026-10-18")
            self.assertEqual([h["title"] for h in held], ["New story"], repr(name))
        for blank in ("\n", "\t", "\u3000", " ; ", "\n;\n"):
            self.assertIsNone(_clean_source({"name": blank, "url": "https://x.example", "date": ""}), repr(blank))
        self.assertEqual(_clean_source({"name": "\nWire\n", "url": "https://x.example", "date": ""})[0], "Wire")
        self.assertEqual(_clean_source({"name": "Wi\nre", "url": "https://x.example", "date": ""})[0], "Wi re")

    def test_unparseable_source_date_still_counts(self):
        line = "- **Story:** x. *(Sources: [Odd](not-a-url), 2026-09-01; [Daily](https://daily.example/new), 2026-10-17)*"
        from knowledge import citation_earliest_date
        self.assertEqual(citation_earliest_date(line), "2026-09-01")

    def test_invalid_calendar_date_is_ignored(self):
        summary = SUMMARY.replace("Archive, 2026-09-01; Wire, 2026-10-16", "Archive, 2026-02-30")
        _, held = hold_old_stories(summary, "2026-10-18")  # must not raise
        self.assertEqual(held, [])

    def test_ambiguous_name_is_not_guessed(self):
        from knowledge import _lookup
        entries = [("Wire", "https://wire.example/a", "2026-10-17"), ("Wire", "https://wire.example/b", "2026-10-17")]
        self.assertIsNone(_lookup(entries, "Wire", "2026-10-17"))
        self.assertIsNone(_lookup([("Wire Extra", "https://x.example", None)], "Wire", None))
        self.assertEqual(_lookup([("AP News (torpedo)", "https://ap.example", None)], "AP News", None),
                         "https://ap.example")


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
