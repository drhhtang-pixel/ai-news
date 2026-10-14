import unittest

from agent import validate_summary

VALID = """<!-- EN -->
### Headlines
- **Model launch:** A lab released a model. *(Source: TechCrunch, Oct 14)*

### Sources
- TechCrunch: https://techcrunch.com/2026/10/14/model (published 2026-10-14)

<!-- ZH -->
### 頭條新聞
- **模型發布：** 某實驗室發布了新模型。*(來源：TechCrunch，10 月 14 日)*
"""


class ValidateSummaryTest(unittest.TestCase):
    def test_valid_summary_has_no_errors(self):
        self.assertEqual(validate_summary(VALID), [])

    def test_empty_summary(self):
        self.assertEqual(validate_summary(""), ["summary is empty"])
        self.assertEqual(validate_summary("  \n "), ["summary is empty"])

    def test_missing_markers(self):
        errors = validate_summary("- **Headline:** text")
        self.assertIn("missing <!-- EN --> marker", errors)
        self.assertIn("missing <!-- ZH --> marker", errors)

    def test_markers_out_of_order(self):
        swapped = "<!-- ZH -->\n- **a:** b\n<!-- EN -->\n- **c:** d\n"
        self.assertEqual(validate_summary(swapped), ["<!-- ZH --> appears before <!-- EN -->"])

    def test_block_without_headlines(self):
        no_zh = VALID.split("<!-- ZH -->")[0] + "<!-- ZH -->\n### 頭條新聞\n（無）\n"
        self.assertEqual(
            validate_summary(no_zh), ["ZH block has no headlines (no '- **' bullets under '### 頭條新聞')"]
        )

    def test_bold_bullets_outside_headlines_do_not_count(self):
        # Codex review #2: empty headline sections must fail even if Analysis has bold bullets.
        text = (
            "<!-- EN -->\n### Headlines\n*(none verified)*\n\n### Analysis\n- **Trend:** x\n"
            "<!-- ZH -->\n### 頭條新聞\n（無）\n\n### 分析\n- **趨勢：** x\n"
        )
        self.assertEqual(validate_summary(text), [
            "EN block has no headlines (no '- **' bullets under '### Headlines')",
            "ZH block has no headlines (no '- **' bullets under '### 頭條新聞')",
        ])

    def test_missing_headline_heading(self):
        text = VALID.replace("### 頭條新聞", "### 新聞")
        self.assertEqual(validate_summary(text), ["ZH block has no '### 頭條新聞' section"])

    def test_latest_real_summary_passes(self):
        # Guard against the check rejecting the format the agent actually produces.
        with open("summaries.md", encoding="utf-8") as f:
            text = f.read()
        last = text[text.rfind("<!-- EN -->"):]
        self.assertEqual(validate_summary(last), [])


if __name__ == "__main__":
    unittest.main()
