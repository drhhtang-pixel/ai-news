import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import agent
from tests.test_knowledge import SUMMARY


class UnverifiedSummaryIsNotPublishedTest(unittest.TestCase):
    """Policy (2026-10-19): if source verification does not complete, nothing is published."""

    def _main(self, verified: bool):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "summaries.md")
            env = {"ANTHROPIC_API_KEY": "x", "TAVILY_API_KEY": "x", "OUTPUT_FILE": out,
                   "HELD_FILE": os.path.join(d, "held.md")}
            with patch.dict(os.environ, env), \
                 patch.object(agent, "run_agent", return_value=SUMMARY), \
                 patch.object(agent, "verify_summary", return_value=(SUMMARY, verified)), \
                 patch.object(agent, "append_summary") as append, \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                try:
                    agent.main()
                    code = 0
                except SystemExit as e:
                    code = e.code
            return code, append, err.getvalue(), os.path.exists(env["HELD_FILE"])

    def test_unverified_run_exits_without_writing(self):
        code, append, err, held_written = self._main(verified=False)
        self.assertEqual(code, 1)
        append.assert_not_called()
        self.assertFalse(held_written)
        self.assertIn("source verification did not complete", err)


if __name__ == "__main__":
    unittest.main()
