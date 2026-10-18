import unittest
from types import SimpleNamespace
from unittest.mock import patch

import agent
from tools import _normalize_date, allowed_dates, execute_tool


def _tool_use_response():
    block = SimpleNamespace(type="tool_use", id="t1", name="web_search", input={"query": "q"})
    return SimpleNamespace(stop_reason="tool_use", content=[block])


def _text_response(text):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


class AllowedDatesTest(unittest.TestCase):
    def test_window(self):
        self.assertEqual(allowed_dates("2026-10-14"), ("2026-10-13", "2026-10-14"))
        self.assertEqual(allowed_dates("2026-11-01"), ("2026-10-31", "2026-11-01"))
        self.assertEqual(allowed_dates("2027-01-01"), ("2026-12-31", "2027-01-01"))


class NormalizeDateTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(_normalize_date("Tue, 14 Oct 2026 12:34:56 GMT"), "2026-10-14")
        self.assertEqual(_normalize_date("2026-10-14T03:00:00Z"), "2026-10-14")
        self.assertEqual(_normalize_date("2026-10-14"), "2026-10-14")
        self.assertIsNone(_normalize_date("not a date"))
        self.assertIsNone(_normalize_date(None))


    def test_converts_to_utc(self):
        # Codex review #3: dates near midnight in other time zones must use the UTC day.
        self.assertEqual(_normalize_date("Wed, 14 Oct 2026 23:30:00 -0700"), "2026-10-15")
        self.assertEqual(_normalize_date("Thu, 15 Oct 2026 00:30:00 +0800"), "2026-10-14")
        self.assertEqual(_normalize_date("2026-10-15T00:30:00+08:00"), "2026-10-14")


class WebSearchTest(unittest.TestCase):
    @patch.dict("os.environ", {"TAVILY_API_KEY": "test"})
    @patch("tools.TavilyClient")
    def test_news_topic_and_dates(self, client_cls):
        client = client_cls.return_value
        client.search.return_value = {"results": [
            {"title": "A", "content": "x", "url": "https://a.com/story",
             "published_date": "Tue, 14 Oct 2026 12:00:00 GMT"},
            {"title": "B", "content": "y", "url": "https://b.com/2026/10/13/story"},
            {"title": "C", "content": "z", "url": "https://c.com/story"},
        ]}
        out = execute_tool("web_search", {"query": "AI news"})
        kwargs = client.search.call_args.kwargs
        self.assertEqual(kwargs["topic"], "news")
        self.assertEqual(kwargs["days"], 2)
        self.assertIn("Published: 2026-10-14\nURL: https://a.com/story", out)
        self.assertIn("Published: 2026-10-13\nURL: https://b.com/2026/10/13/story", out)
        self.assertIn("Published: unknown\nURL: https://c.com/story", out)


class GuardFinalCallTest(unittest.TestCase):
    """When the tool budget runs out, the final call must still declare tools (history has tool_use)."""

    def _run(self, module, fn, *args):
        with patch.object(module, "execute_tool", return_value="ok"), \
             patch.object(module.anthropic, "Anthropic") as client_cls:
            create = client_cls.return_value.messages.create
            create.side_effect = lambda **kw: (
                _text_response("<!-- EN -->done") if kw.get("tool_choice") else _tool_use_response()
            )
            result = fn(*args)
            return result, create.call_args_list

    def test_agent_guard(self):
        result, calls = self._run(agent, agent.run_agent, "AI news", "2026-10-14")
        self.assertEqual(len(calls), agent.MAX_TOOL_CALLS + 1)
        final = calls[-1].kwargs
        self.assertEqual(final["tool_choice"], {"type": "none"})
        self.assertIs(final["tools"], agent.TOOLS)
        self.assertEqual(result, "<!-- EN -->done")

class PromptDatesTest(unittest.TestCase):
    def test_writer_prompt_uses_known_stories_not_a_date_window(self):
        with patch.object(agent.anthropic, "Anthropic") as client_cls:
            create = client_cls.return_value.messages.create
            create.return_value = _text_response("<!-- EN -->done")
            agent.run_agent("AI news", "2026-10-14", ["Old story A", "Old story B"])
            system = create.call_args.kwargs["system"]
        self.assertIn("NEW TO THIS MONITOR", system)
        self.assertIn("- Old story A\n- Old story B", system)
        self.assertNotIn("2026-10-13", system)

class HeadlineTotalTest(unittest.TestCase):
    def test_counts_en_headlines_only(self):
        text = (
            "<!-- EN -->\n### Headlines\n- **A:** x\n- **B:** y\n### Analysis\n- **T:** z\n"
            "<!-- ZH -->\n### 頭條新聞\n- **甲：** x\n"
        )
        self.assertEqual(agent._headline_total(text), 2)
        self.assertEqual(agent._headline_total("no markers"), 0)


if __name__ == "__main__":
    unittest.main()
