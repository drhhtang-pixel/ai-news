import unittest
from unittest.mock import patch

from tools import _date_from_content, _date_from_url, _resolve_published_date, execute_tool


class DateFromUrlTest(unittest.TestCase):
    def test_year_month_day_path(self):
        self.assertEqual(_date_from_url("https://techcrunch.com/2026/10/05/openai-watermark"), "2026-10-05")
        self.assertEqual(_date_from_url("https://example.com/2026/1/7"), "2026-01-07")
        self.assertEqual(_date_from_url("https://example.com/2026/10/05?ref=x"), "2026-10-05")

    def test_no_or_invalid_date(self):
        self.assertIsNone(_date_from_url("https://apnews.com/article/ai-fbi-7f512b"))
        self.assertIsNone(_date_from_url("https://example.com/2026/13/40/x"))
        self.assertIsNone(_date_from_url(""))
        self.assertIsNone(_date_from_url(None))


class DateFromContentTest(unittest.TestCase):
    def test_labeled_formats(self):
        self.assertEqual(_date_from_content("Posted 2026-10-14 by staff"), "2026-10-14")
        self.assertEqual(_date_from_content("Published: October 13, 2026 — Reuters"), "2026-10-13")
        self.assertEqual(_date_from_content("Posted on Sept. 3 2026"), "2026-09-03")
        self.assertEqual(_date_from_content("Publication date 13 Oct 2026"), "2026-10-13")

    def test_unlabeled_dates_are_ignored(self):
        self.assertIsNone(_date_from_content("October 13, 2026 — Reuters"))
        self.assertIsNone(_date_from_content("Updated 13 Oct 2026"))

    def test_navigation_date_does_not_override_published_label(self):
        # Codex review #1: a newer date in navigation must not win over the publication label.
        text = "Navigation: Latest news 2026-10-15\nArticle published 2024-01-01\nOld report body"
        self.assertEqual(_date_from_content(text), "2024-01-01")
        self.assertIsNone(_date_from_content("Navigation: Latest news 2026-10-15\nOld report body"))

    def test_only_scans_first_15000_chars(self):
        self.assertIsNone(_date_from_content("x" * 15000 + " Published 2026-10-14"))

    def test_invalid_and_empty(self):
        self.assertIsNone(_date_from_content("February 30, 2026"))
        self.assertIsNone(_date_from_content(""))
        self.assertIsNone(_date_from_content(None))


class ResolvePublishedDateTest(unittest.TestCase):
    def test_priority_order(self):
        url = "https://example.com/2026/10/13/story"
        self.assertEqual(_resolve_published_date("2026-10-14", url, "2026-10-12"), "2026-10-14")
        self.assertEqual(_resolve_published_date(None, url, "2026-10-12"), "2026-10-13")
        self.assertEqual(_resolve_published_date("", "https://example.com/a", "Published 2026-10-12"), "2026-10-12")
        self.assertEqual(_resolve_published_date(None, "https://example.com/a", "no date"), "unknown")


class ExtractUrlToolTest(unittest.TestCase):
    @patch.dict("os.environ", {"TAVILY_API_KEY": "test"})
    @patch("tools.TavilyClient")
    def test_extract_uses_resolved_date(self, client_cls):
        client_cls.return_value.extract.return_value = {"results": [{
            "title": "Story",
            "url": "https://example.com/2026/10/13/story",
            "raw_content": "body",
            "published_date": None,
        }]}
        out = execute_tool("extract_url", {"url": "https://example.com/2026/10/13/story"})
        self.assertIn("Published: 2026-10-13", out)


if __name__ == "__main__":
    unittest.main()
