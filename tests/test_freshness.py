import unittest
from types import SimpleNamespace
from unittest.mock import patch

import agent
import verifier
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
        self.assertIsNone(_normalize_date("not a date"))
        self.assertIsNone(_normalize_date(None))


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

    def test_verifier_guard(self):
        result, calls = self._run(verifier, verifier.run_verifier, "<!-- EN -->x", "2026-10-14")
        self.assertEqual(len(calls), verifier.MAX_VERIFIER_TOOL_CALLS + 1)
        final = calls[-1].kwargs
        self.assertEqual(final["tool_choice"], {"type": "none"})
        self.assertIs(final["tools"], verifier.TOOLS)
        self.assertEqual(result, "<!-- EN -->done")


class PromptDatesTest(unittest.TestCase):
    def _system_prompt(self, module, fn, *args):
        with patch.object(module.anthropic, "Anthropic") as client_cls:
            create = client_cls.return_value.messages.create
            create.return_value = _text_response("<!-- EN -->done")
            fn(*args)
            return create.call_args.kwargs["system"]

    def test_both_prompts_name_the_24h_window(self):
        for module, fn, args in [
            (agent, agent.run_agent, ("AI news", "2026-10-14")),
            (verifier, verifier.run_verifier, ("<!-- EN -->x", "2026-10-14")),
        ]:
            system = self._system_prompt(module, fn, *args)
            self.assertIn("2026-10-13", system, module.__name__)
            self.assertIn("2026-10-14", system, module.__name__)


if __name__ == "__main__":
    unittest.main()
