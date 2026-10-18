import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import tools
import verifier
from knowledge import InvalidDecisions, apply_verification, check_decisions
from tests.test_knowledge import SUMMARY

DECISIONS = [
    {"index": 1, "action": "keep", "reason": "ok",
     "sources": [{"name": "Wire", "url": "https://wire.example/new", "date": "2026-10-17"}]},
    {"index": 2, "action": "remove", "reason": "not supported", "sources": []},
    {"index": 3, "action": "keep", "reason": "ok",
     "sources": [{"name": "Blog", "url": "https://blog.example/x", "date": "unknown"}]},
]


def _decisions(changes=None):
    """A copy of DECISIONS with {index: {field: value}} changes applied."""
    out = [dict(d, sources=[dict(s) for s in d["sources"]]) for d in DECISIONS]
    for d in out:
        d.update((changes or {}).get(d["index"], {}))
    return out


def _tool_use(name="web_search", tool_input=None):
    block = SimpleNamespace(type="tool_use", id="t1", name=name, input=tool_input or {"query": "q"})
    return SimpleNamespace(stop_reason="tool_use", content=[block])


def _submit(decisions):
    return _tool_use(verifier.SUBMIT_TOOL["name"], {"headlines": decisions})


def _text(text, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class VerifierRunTest(unittest.TestCase):
    """Drive run_verifier with a fake streaming client; `respond(kwargs)` returns each reply."""

    def setUp(self):
        tools.URL_DATES.clear()
        tools.URL_DATES["wire.example/new"] = "2026-10-17"

    def _run(self, respond, known=None, summary=SUMMARY):
        calls = []

        def stream(**kwargs):
            calls.append(kwargs)
            ctx = MagicMock()
            ctx.__enter__.return_value.get_final_message.return_value = respond(kwargs)
            return ctx

        with patch.object(verifier, "execute_tool", return_value="ok"), \
             patch.object(verifier.anthropic, "Anthropic") as client_cls:
            client_cls.return_value.messages.stream.side_effect = stream
            result = verifier.run_verifier(summary, "2026-10-18", known)
        return result, calls

    def test_submitted_decisions_are_applied_as_linked_citations(self):
        responses = iter([_tool_use(), _submit(_decisions())])
        result, calls = self._run(lambda kw: next(responses))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("- **Old story", result)
        self.assertIn("*(Sources: [Wire](https://wire.example/new), 2026-10-17)*", result)
        self.assertIn("*(來源：[Blog](https://blog.example/x)，日期不明)*", result)
        self.assertIn("Text.", result)  # Analysis untouched

    def test_model_dates_are_replaced_by_tool_dates(self):
        # Codex review #1: a fresher date written by the model must not bypass the age rule.
        result, _ = self._run(lambda kw: _submit(_decisions({1: {"sources": [
            {"name": "Wire", "url": "https://wire.example/new", "date": "2026-10-18"}]}, 3: {"sources": [
            {"name": "Blog", "url": "https://blog.example/x", "date": "2026-10-18"}]}})))
        self.assertIn("[Wire](https://wire.example/new), 2026-10-17", result)
        self.assertIn("[Blog](https://blog.example/x), date unknown", result)  # no tool dated it

    def test_invalid_decisions_get_one_resubmission(self):
        # Codex review #5: incomplete decisions are rejected and must be resubmitted.
        responses = iter([_submit(DECISIONS[:2]), _submit(_decisions())])
        result, calls = self._run(lambda kw: next(responses))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["tool_choice"]["name"], "submit_verification")
        # The fake client shares one message list, so find the rejection by content.
        rejection = next(m["content"][0] for m in calls[1]["messages"]
                         if m["role"] == "user" and isinstance(m["content"], list) and m["content"][0].get("is_error"))
        self.assertTrue(rejection["is_error"])
        self.assertIn("missing decisions for headlines [3]", rejection["content"])
        self.assertIn("[Wire](https://wire.example/new)", result)

    def test_invalid_twice_returns_empty(self):
        result, _ = self._run(lambda kw: _submit([]))
        self.assertEqual(result, "")

    def test_mismatched_languages_are_not_verified(self):
        # Codex review #2: EN/ZH that do not line up are never verified by position.
        lopsided = SUMMARY.replace("- **舊消息：** 舊。*(來源：Archive，2026-09-01；Wire，2026-10-16)*\n", "")
        result, calls = self._run(lambda kw: _submit(_decisions()), summary=lopsided)
        self.assertEqual(result, "")
        self.assertEqual(calls, [])

    def test_budget_exhausted_forces_submission(self):
        result, calls = self._run(lambda kw: _submit(_decisions()) if kw.get("tool_choice") else _tool_use())
        self.assertEqual(len(calls), verifier.MAX_VERIFIER_TOOL_CALLS + 1)
        self.assertEqual(calls[-1]["tool_choice"], {"type": "tool", "name": "submit_verification"})
        self.assertIn("[Wire](https://wire.example/new)", result)

    def test_end_turn_without_submission_forces_it(self):
        responses = iter([_text("I checked everything."), _submit(_decisions())])
        result, calls = self._run(lambda kw: next(responses))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1]["tool_choice"]["name"], "submit_verification")
        self.assertNotIn("- **Old story", result)

    def test_forced_call_without_submission_gives_up(self):
        result, calls = self._run(lambda kw: _text("still talking"))
        self.assertEqual(result, "")
        self.assertEqual(len(calls), 2)

    def test_max_tokens_without_submission_returns_empty(self):
        result, _ = self._run(lambda kw: _text("long rambling", stop_reason="max_tokens"))
        self.assertEqual(result, "")

    def test_prompt_and_tools(self):
        _, calls = self._run(lambda kw: _submit(_decisions()), known=["Old story A"])
        first = calls[0]
        self.assertIn("supported by the CONTENT", first["system"])
        self.assertIn("Publication dates are NOT a reason", first["system"])
        self.assertIn("- Old story A", first["system"])
        self.assertIn("submit_verification", [t["name"] for t in first["tools"]])
        self.assertEqual(first["max_tokens"], verifier.VERIFIER_MAX_TOKENS)

    def test_verify_summary_reports_whether_it_verified(self):
        with patch.object(verifier, "run_verifier", return_value=""):
            self.assertEqual(verifier.verify_summary(SUMMARY, "2026-10-18"), (SUMMARY, False))
        with patch.object(verifier, "run_verifier", return_value="done"):
            self.assertEqual(verifier.verify_summary(SUMMARY, "2026-10-18"), ("done", True))


class CheckDecisionsTest(unittest.TestCase):
    def test_complete_decisions(self):
        self.assertEqual(check_decisions(DECISIONS, 3), [])

    def test_problems(self):
        self.assertEqual(check_decisions([], 3), ["missing decisions for headlines [1, 2, 3] (there are 3)"])
        dup = [DECISIONS[0], DECISIONS[0], DECISIONS[1], DECISIONS[2]]
        self.assertEqual(check_decisions(dup, 3), ["duplicate indexes: [1]"])
        self.assertIn("indexes out of range: [4] (there are 3)",
                      check_decisions(DECISIONS + [dict(DECISIONS[0], index=4)], 3))
        self.assertIn("#1: action must be keep or remove, got 'maybe'",
                      check_decisions([dict(DECISIONS[0], action="maybe")] + DECISIONS[1:], 3))
        self.assertIn("index must be an integer: '1'", check_decisions([dict(DECISIONS[0], index="1")], 1))
        self.assertEqual(check_decisions("nope", 1), ["decisions must be a list"])


class ApplyVerificationTest(unittest.TestCase):
    def test_rebuilds_both_languages_and_sources(self):
        out = apply_verification(SUMMARY, DECISIONS)
        self.assertNotIn("archive.example", out)
        self.assertNotIn("- **舊消息", out)
        self.assertEqual(out.count("- Wire: https://wire.example/new (published 2026-10-17)"), 2)
        self.assertEqual(out.count("- Blog: https://blog.example/x (published date unknown)"), 2)
        self.assertNotIn("daily.example", out)  # dropped from headline 1's citation

    def test_caps_sources_and_rejects_bad_ones(self):
        many = [{"name": f"S{i}", "url": f"https://s{i}.example", "date": f"2026-10-1{i}"} for i in range(5)]
        out = apply_verification(SUMMARY, [
            {"index": 1, "action": "keep", "sources": [{"name": "Bad", "url": "not a url", "date": "x"}] + many},
            DECISIONS[1], DECISIONS[2],
        ])
        self.assertIn("*(Sources: [S0](https://s0.example), 2026-10-10; [S1](https://s1.example), 2026-10-11; "
                      "[S2](https://s2.example), 2026-10-12)*", out)
        self.assertNotIn("S3", out)
        self.assertNotIn("Bad", out)

    def test_impossible_date_becomes_unknown(self):
        out = apply_verification(SUMMARY, _decisions({1: {"sources": [
            {"name": "Wire", "url": "https://wire.example/new", "date": "2026-02-30"}]}}))
        self.assertIn("[Wire](https://wire.example/new), date unknown", out)

    def test_keep_without_sources_removes_headline(self):
        out = apply_verification(SUMMARY, _decisions({3: {"sources": []}}))
        self.assertNotIn("Undated story", out)
        self.assertNotIn("無日期", out)

    def test_rejects_incomplete_or_mismatched_input(self):
        with self.assertRaises(InvalidDecisions):
            apply_verification(SUMMARY, DECISIONS[:2])
        lopsided = SUMMARY.replace("- **舊消息：** 舊。*(來源：Archive，2026-09-01；Wire，2026-10-16)*\n", "")
        with self.assertRaisesRegex(InvalidDecisions, "EN has 3 headlines but ZH has 2"):
            apply_verification(lopsided, DECISIONS)

    def test_empty_sources_sections_are_filled(self):
        # Codex review #6: an empty Sources section must still receive the verified URLs.
        bare = "\n".join(line for line in SUMMARY.splitlines()
                         if not line.startswith("- ") or line.startswith("- **"))
        out = apply_verification(bare, DECISIONS)
        self.assertEqual(out.count("- Wire: https://wire.example/new (published 2026-10-17)"), 2)

    def test_missing_sources_section_is_added(self):
        no_section = SUMMARY.replace("### 來源", "### 參考")
        out = apply_verification(no_section, DECISIONS)
        zh = out.split("<!-- ZH -->")[1]
        self.assertIn("### 來源\n- Wire: https://wire.example/new", zh)


if __name__ == "__main__":
    unittest.main()
