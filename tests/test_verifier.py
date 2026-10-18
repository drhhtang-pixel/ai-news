import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import verifier
from tests.test_knowledge import SUMMARY

DECISIONS = [
    {"index": 1, "action": "keep", "reason": "ok",
     "sources": [{"name": "Wire", "url": "https://wire.example/new", "date": "2026-10-17"}]},
    {"index": 2, "action": "remove", "reason": "not supported", "sources": []},
    {"index": 3, "action": "keep", "reason": "ok",
     "sources": [{"name": "Blog", "url": "https://blog.example/x", "date": "unknown"}]},
]


def _tool_use(name="web_search", tool_input=None):
    block = SimpleNamespace(type="tool_use", id="t1", name=name, input=tool_input or {"query": "q"})
    return SimpleNamespace(stop_reason="tool_use", content=[block])


def _submit(decisions):
    return _tool_use(verifier.SUBMIT_TOOL["name"], {"headlines": decisions})


def _text(text, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class VerifierRunTest(unittest.TestCase):
    """Drive run_verifier with a fake streaming client that returns `responses` in order,
    or calls `respond(kwargs)` for each request."""

    def _run(self, respond, known=None):
        calls = []

        def stream(**kwargs):
            calls.append(kwargs)
            ctx = MagicMock()
            ctx.__enter__.return_value.get_final_message.return_value = respond(kwargs)
            return ctx

        with patch.object(verifier, "execute_tool", return_value="ok"), \
             patch.object(verifier.anthropic, "Anthropic") as client_cls:
            client_cls.return_value.messages.stream.side_effect = stream
            result = verifier.run_verifier(SUMMARY, "2026-10-18", known)
        return result, calls

    def test_submitted_decisions_are_applied(self):
        responses = iter([_tool_use(), _submit(DECISIONS)])
        result, calls = self._run(lambda kw: next(responses))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("- **Old story", result)
        self.assertIn("*(Sources: Wire, 2026-10-17)*", result)
        self.assertIn("*(來源：Blog，日期不明)*", result)
        self.assertIn("Text.", result)  # Analysis untouched

    def test_budget_exhausted_forces_submission(self):
        result, calls = self._run(lambda kw: _submit(DECISIONS) if kw.get("tool_choice") else _tool_use())
        self.assertEqual(len(calls), verifier.MAX_VERIFIER_TOOL_CALLS + 1)
        self.assertEqual(calls[-1]["tool_choice"], {"type": "tool", "name": "submit_verification"})
        self.assertIn("*(Sources: Wire, 2026-10-17)*", result)

    def test_end_turn_without_submission_forces_it(self):
        responses = iter([_text("I checked everything."), _submit(DECISIONS)])
        result, calls = self._run(lambda kw: next(responses))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1]["tool_choice"]["name"], "submit_verification")
        self.assertNotIn("- **Old story", result)

    def test_max_tokens_without_submission_returns_empty(self):
        result, _ = self._run(lambda kw: _text("long rambling", stop_reason="max_tokens"))
        self.assertEqual(result, "")

    def test_prompt_and_tools(self):
        _, calls = self._run(lambda kw: _submit(DECISIONS), known=["Old story A"])
        first = calls[0]
        self.assertIn("supported by the CONTENT", first["system"])
        self.assertIn("Publication dates are NOT a reason", first["system"])
        self.assertIn("- Old story A", first["system"])
        self.assertIn("submit_verification", [t["name"] for t in first["tools"]])
        self.assertEqual(first["max_tokens"], verifier.VERIFIER_MAX_TOKENS)

    def test_verify_summary_falls_back_to_original(self):
        with patch.object(verifier, "run_verifier", return_value=""):
            self.assertEqual(verifier.verify_summary(SUMMARY, "2026-10-18"), SUMMARY)


class ApplyVerificationTest(unittest.TestCase):
    def test_rebuilds_both_languages_and_sources(self):
        from knowledge import apply_verification
        out = apply_verification(SUMMARY, DECISIONS)
        self.assertNotIn("archive.example", out)
        self.assertNotIn("- **舊消息", out)
        self.assertEqual(out.count("- Wire: https://wire.example/new (published 2026-10-17)"), 2)
        self.assertEqual(out.count("- Blog: https://blog.example/x (published date unknown)"), 2)
        self.assertNotIn("daily.example", out)  # dropped from headline 1's citation

    def test_caps_sources_and_rejects_bad_ones(self):
        from knowledge import apply_verification
        many = [{"name": f"S{i}", "url": f"https://s{i}.example", "date": f"2026-10-1{i}"} for i in range(5)]
        out = apply_verification(SUMMARY, [
            {"index": 1, "action": "keep", "sources": [{"name": "Bad", "url": "not a url", "date": "x"}] + many},
        ])
        self.assertIn("*(Sources: S0, 2026-10-10; S1, 2026-10-11; S2, 2026-10-12)*", out)
        self.assertNotIn("S3", out)
        self.assertNotIn("Bad", out)

    def test_keep_without_sources_removes_headline(self):
        from knowledge import apply_verification
        out = apply_verification(SUMMARY, [{"index": 3, "action": "keep", "sources": []}])
        self.assertNotIn("Undated story", out)
        self.assertNotIn("無日期", out)
        self.assertIn("Old story", out)  # no decision -> unchanged

    def test_undecided_headline_keeps_its_own_sources(self):
        from knowledge import apply_verification
        out = apply_verification(SUMMARY, [{"index": 1, "action": "keep", "sources": [
            {"name": "Wire", "url": "https://wire.example/new", "date": "2026-10-17"}]}])
        # Headline 2 cites "Wire, 2026-10-16": that is wire.example/old, not the other Wire entry.
        self.assertIn("- Wire: https://wire.example/old (published 2026-10-16)", out)
        self.assertIn("- Wire: https://wire.example/new (published 2026-10-17)", out)


if __name__ == "__main__":
    unittest.main()
