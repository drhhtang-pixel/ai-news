import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import tools
from agent import unseen_source_urls
from tools import execute_tool, log_tool_call, normalize_url


class NormalizeUrlTest(unittest.TestCase):
    def test_loose_comparison(self):
        self.assertEqual(normalize_url("https://www.TechCrunch.com/2026/10/17/x/"), "techcrunch.com/2026/10/17/x")
        self.assertEqual(normalize_url("http://techcrunch.com/2026/10/17/x"), "techcrunch.com/2026/10/17/x")


class SeenUrlsTest(unittest.TestCase):
    def setUp(self):
        tools.SEEN_URLS.clear()

    @patch.dict("os.environ", {"TAVILY_API_KEY": "test"})
    @patch("tools.TavilyClient")
    def test_search_and_extract_record_urls(self, client_cls):
        client = client_cls.return_value
        client.search.return_value = {"results": [{"title": "A", "content": "x", "url": "https://a.com/1"}]}
        client.extract.return_value = {"results": [{"title": "B", "raw_content": "y", "url": "https://b.com/2"}]}
        execute_tool("web_search", {"query": "q"})
        execute_tool("extract_url", {"url": "https://www.b.com/2/"})
        self.assertEqual(tools.SEEN_URLS, {"a.com/1", "b.com/2"})

    @patch.dict("os.environ", {"TAVILY_API_KEY": "test"})
    @patch("tools.TavilyClient")
    def test_search_date_is_remembered_for_later_extract(self, client_cls):
        tools.URL_DATES.clear()
        client = client_cls.return_value
        client.search.return_value = {"results": [
            {"title": "A", "content": "x", "url": "https://a.com/1", "published_date": "Fri, 16 Oct 2026 10:00:00 GMT"}]}
        client.extract.return_value = {"results": [{"title": "A", "raw_content": "no date", "url": "https://a.com/1"}]}
        execute_tool("web_search", {"query": "q"})
        execute_tool("extract_url", {"url": "https://a.com/1"})
        self.assertEqual(tools.URL_DATES, {"a.com/1": "2026-10-16"})

    @patch.dict("os.environ", {"TAVILY_API_KEY": "test"})
    @patch("tools.TavilyClient")
    def test_failed_extract_records_nothing(self, client_cls):
        client_cls.return_value.extract.return_value = {"results": []}
        execute_tool("extract_url", {"url": "https://made.up/404"})
        self.assertEqual(tools.SEEN_URLS, set())


class UnseenSourceUrlsTest(unittest.TestCase):
    def test_flags_only_urls_no_tool_returned(self):
        summary = (
            "- TechCrunch: https://techcrunch.com/2026/10/17/real (published 2026-10-17)\n"
            "- TechCrunch (Grok): https://techcrunch.com/2026/10/16/xai-grok-4-release/ (published 2026-10-16)\n"
            "- Again: https://techcrunch.com/2026/10/17/real (published 2026-10-17)\n"
        )
        seen = {"techcrunch.com/2026/10/17/real"}
        self.assertEqual(unseen_source_urls(summary, seen),
                         ["https://techcrunch.com/2026/10/16/xai-grok-4-release/"])


class LogToolCallTest(unittest.TestCase):
    def test_one_line_with_status(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            log_tool_call("writer", "web_search", {"query": "AI news"}, "**A**")
            log_tool_call("verifier", "extract_url", {"url": "https://x.com/a"}, "Error: No content extracted")
        self.assertEqual(buf.getvalue().splitlines(), [
            "  [writer] web_search ok: AI news",
            "  [verifier] extract_url ERROR: https://x.com/a",
        ])


if __name__ == "__main__":
    unittest.main()
