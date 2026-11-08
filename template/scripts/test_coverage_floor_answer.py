"""Guard test: the coverage floor's stated percentage, its copier answer, and
stage 0's own instruction to set it are held together.

Run standalone: python3 scripts/test_coverage_floor_answer.py

This is prose an agent reads and a human sets, not executable code, so this
test pins the exact sentences and values it can hold generically: the rule's
stated percentage against the `coverage_floor` answer, and stage 0's own text
against naming that answer. The suite's own coverage-configuration file is
stage 0's own choice of test tool and does not exist in the template, so
keeping that third value in step stays a PR-process rule, not a check here.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jinja_paths import ROOT, is_rendered, rendered_or_jinja  # noqa: E402

CI_AND_CHECKS = rendered_or_jinja(".forge", "ci-and-checks.md")
FEATURE_PIPELINE = rendered_or_jinja(".forge", "feature-pipeline.md")
PROJECT_INIT_CHECKLIST = rendered_or_jinja("scripts", "project_init_checklist.md")
ANSWERS = ROOT / ".copier-answers.yml"

# Pre-render, the rule's own `{{ coverage_floor }}%` holds a Jinja expression,
# not yet a digit; both forms are "the right shape" for test_rule_states_the_floor_with_the_right_shape.
COVERAGE_FLOOR_SENTENCE = re.compile(
    r"coverage floor \((\d+|\{\{\s*coverage_floor\s*\}\})%, the `coverage_floor` answer"
)
ANSWERS_FLOOR_LINE = re.compile(r"(?m)^coverage_floor:\s*(\d+)$")


class CoverageFloorMatchesTheRuleAndTheAnswer(unittest.TestCase):
    """The rule text and the answers file state the same floor; a hand edit to either goes red here."""

    def test_rule_states_the_floor_with_the_right_shape(self) -> None:
        rule = CI_AND_CHECKS.read_text(encoding="utf-8")
        self.assertIsNotNone(
            COVERAGE_FLOOR_SENTENCE.search(rule),
            "coverage floor sentence not found in ci-and-checks.md, or reworded",
        )

    def test_rule_states_the_same_floor_as_the_answer(self) -> None:
        if not is_rendered():
            self.skipTest("unrendered template: no .copier-answers.yml to compare the rule's stated floor against")

        answers = ANSWERS.read_text(encoding="utf-8")
        answer_match = ANSWERS_FLOOR_LINE.search(answers)
        self.assertIsNotNone(answer_match, "no coverage_floor answer in .copier-answers.yml")

        rule = CI_AND_CHECKS.read_text(encoding="utf-8")
        rule_match = COVERAGE_FLOOR_SENTENCE.search(rule)
        self.assertIsNotNone(rule_match)

        self.assertEqual(int(rule_match.group(1)), int(answer_match.group(1)))


class Stage0NamesTheCoverageFloorAnswer(unittest.TestCase):
    """Stage 0's own text says to set `coverage_floor`, not just to pick a coverage tool."""

    def test_feature_pipeline_stage_0_names_the_answer(self) -> None:
        text = FEATURE_PIPELINE.read_text(encoding="utf-8")
        stage_0 = text.split("## Stage 1", 1)[0]
        self.assertIn("coverage_floor", stage_0)

    def test_project_init_checklist_names_the_coverage_floor(self) -> None:
        text = PROJECT_INIT_CHECKLIST.read_text(encoding="utf-8")
        self.assertIn("coverage floor", text)


if __name__ == "__main__":
    unittest.main()
