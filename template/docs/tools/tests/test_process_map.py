"""Guard tests for docs/tools/process_map.py, the how-why process map.

Every case pins one check on a small synthetic repo, so removing or
weakening that check turns its case red. There is no "the real map is
clean" case here, unlike a consuming project's own copy of this test: the
template ships no committed `docs/tools/process-map.yaml` of its own (a
project writes its first one when `.agents/skills/process-map-setup/SKILL.md`
runs at stage 0), so there is nothing real to check yet.

    python3 docs/tools/tests/test_process_map.py
"""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import process_map  # noqa: E402

LAYERS = {k: "x" for k in process_map.LAYER_ORDER}


def _data() -> dict:
    return {
        "layers": LAYERS,
        "nodes": [
            {"id": "rules", "path": "CLAUDE.md", "layer": "instructions", "purpose": "Rules."},
            {
                "id": "skill-a",
                "path": ".agents/skills/a/SKILL.md",
                "layer": "skill",
                "purpose": "A.",
            },
            {
                "id": "tool",
                "path": ".agents/skills/b/SKILL.md",
                "layer": "skill",
                "purpose": "B.",
                "discretionary": True,
            },
            {"id": "gate", "path": "gate.sh", "layer": "guard", "purpose": "Gate."},
        ],
        "edges": [
            {"from": "rules", "to": "skill-a", "note": "Runs it."},
            {"from": "rules", "to": "gate", "note": "Enforces it."},
        ],
    }


def _write_index(repo: Path, data: dict) -> None:
    index = repo / process_map.INDEX_NAME
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(process_map.render_index(data), encoding="utf-8")


def _check(repo: Path, data: dict) -> list[process_map.Problem]:
    output = repo / "map.md"
    output.write_text(process_map.render(data), encoding="utf-8")
    _write_index(repo, data)
    return process_map.problems(data, root=repo, output=output)


def _check_unrendered(repo: Path, data: dict) -> list[process_map.Problem]:
    return process_map.problems(data, root=repo, output=repo / "absent.md")


class ProcessMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for rel in ("CLAUDE.md", ".agents/skills/a/SKILL.md", ".agents/skills/b/SKILL.md", "gate.sh"):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_synthetic_map_is_clean(self) -> None:
        self.assertEqual(_check(self.repo, _data()), [])

    def test_index_lists_skills_and_references_with_discretionary_section_last(self) -> None:
        data = _data()
        data["nodes"].append(
            {
                "id": "lessons",
                "path": "docs/agents/lessons.md",
                "layer": "reference",
                "purpose": "History.",
            }
        )
        lines = process_map.render_index(data).splitlines()
        entry_a = "- **skill-a** -- A. -- `.agents/skills/a/SKILL.md`"
        entry_lessons = "- **lessons** -- History. -- `docs/agents/lessons.md`"
        entry_tool = "- **tool** -- B. -- `.agents/skills/b/SKILL.md`"
        discretionary = lines.index("## Discretionary (pick up ad hoc, no policy link)")
        self.assertLess(lines.index(entry_a), lines.index(entry_lessons))
        self.assertLess(lines.index(entry_lessons), discretionary)
        self.assertGreater(lines.index(entry_tool), discretionary)
        self.assertFalse(any("gate.sh" in line for line in lines))

    def test_stale_index_is_reported(self) -> None:
        data = _data()
        _write_index(self.repo, data)
        changed = copy.deepcopy(data)
        changed["nodes"][1]["purpose"] = "Changed."
        problems = process_map.problems(
            changed,
            root=self.repo,
            output=self.repo / "map.md",
            index_output=self.repo / process_map.INDEX_NAME,
        )
        self.assertTrue(any(f"{process_map.INDEX_NAME} differs" in p for p in problems))

    def test_missing_index_is_reported(self) -> None:
        problems = process_map.problems(_data(), root=self.repo, output=self.repo / "absent.md")
        self.assertTrue(any(f"{process_map.INDEX_NAME} is missing" in p for p in problems))

    def test_missing_path_is_reported(self) -> None:
        (self.repo / "gate.sh").unlink()
        self.assertTrue(any("gate.sh does not exist" in p for p in _check(self.repo, _data())))

    def test_structure_problem_is_tagged_structure(self) -> None:
        """A structural problem (a missing path here) is always
        `kind="structure"`, regardless of what its message says."""
        (self.repo / "gate.sh").unlink()
        structure_problems = _check(self.repo, _data())
        self.assertTrue(structure_problems)
        self.assertTrue(all(p.kind == "structure" for p in structure_problems))

    def test_drift_problem_is_tagged_drift(self) -> None:
        """A stale/missing generated file is always `kind="drift"`,
        regardless of what its message says."""
        drift_problems = _check_unrendered(self.repo, _data())
        self.assertTrue(drift_problems)
        self.assertTrue(all(p.kind == "drift" for p in drift_problems))

    def test_build_and_index_refuse_structure_problems_even_if_reworded(self) -> None:
        """Rewording a structure problem's message must not let
        `build`/`index` treat it as safe to proceed past -- only `kind` decides."""
        data = _data()
        reworded_structure = process_map.Problem("a totally different wording", kind="structure")
        original_load, original_problems = process_map.load, process_map.problems
        original_output, original_index = process_map.OUTPUT, process_map.INDEX_OUTPUT
        process_map.load = lambda: data
        process_map.problems = lambda d: [reworded_structure]
        process_map.OUTPUT = self.repo / "map.md"
        process_map.INDEX_OUTPUT = self.repo / process_map.INDEX_NAME
        try:
            self.assertEqual(process_map.main(["build"]), 1)
            self.assertEqual(process_map.main(["index"]), 1)
            self.assertFalse((self.repo / "map.md").exists())
        finally:
            process_map.load, process_map.problems = original_load, original_problems
            process_map.OUTPUT, process_map.INDEX_OUTPUT = original_output, original_index

    def test_build_and_index_proceed_past_drift_problems_even_if_reworded(self) -> None:
        """Rewording a drift problem's message must not make `build`/`index`
        refuse to regenerate -- only `kind` decides."""
        data = _data()
        reworded_drift = process_map.Problem("a totally different wording", kind="drift")
        index_output = self.repo / process_map.INDEX_NAME
        index_output.parent.mkdir(parents=True, exist_ok=True)
        original_load, original_problems = process_map.load, process_map.problems
        original_output, original_index = process_map.OUTPUT, process_map.INDEX_OUTPUT
        process_map.load = lambda: data
        process_map.problems = lambda d: [reworded_drift]
        process_map.OUTPUT = self.repo / "map.md"
        process_map.INDEX_OUTPUT = index_output
        try:
            self.assertEqual(process_map.main(["build"]), 0)
            self.assertEqual(
                (self.repo / "map.md").read_text(encoding="utf-8"), process_map.render(data)
            )
            self.assertEqual(process_map.main(["index"]), 0)
            self.assertEqual(
                index_output.read_text(encoding="utf-8"), process_map.render_index(data)
            )
        finally:
            process_map.load, process_map.problems = original_load, original_problems
            process_map.OUTPUT, process_map.INDEX_OUTPUT = original_output, original_index

    def test_process_file_without_a_node_is_reported(self) -> None:
        extra = self.repo / ".agents/skills/c/SKILL.md"
        extra.parent.mkdir(parents=True)
        extra.write_text("x")
        self.assertTrue(
            any("c/SKILL.md is a process file with no node" in p for p in _check(self.repo, _data()))
        )

    def test_agent_doc_or_workflow_without_a_node_is_reported(self) -> None:
        for rel in ("docs/agents/extra.md", ".github/workflows/extra.yml"):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                for base in ("CLAUDE.md", ".agents/skills/a/SKILL.md", ".agents/skills/b/SKILL.md", "gate.sh"):
                    path = repo / base
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("x")
                extra = repo / rel
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text("x")
                self.assertTrue(
                    any(f"{rel} is a process file with no node" in p for p in _check(repo, _data()))
                )

    def test_dangling_edge_is_reported(self) -> None:
        data = _data()
        data["edges"].append({"from": "rules", "to": "nowhere", "note": "n."})
        self.assertTrue(
            any("rules -> nowhere has a missing end" in p for p in _check_unrendered(self.repo, data))
        )

    def test_edge_without_a_note_is_reported(self) -> None:
        data = _data()
        data["edges"][0]["note"] = " "
        self.assertTrue(any("rules -> skill-a has no note" in p for p in _check(self.repo, data)))

    def test_cycle_is_reported(self) -> None:
        data = _data()
        data["edges"].append({"from": "skill-a", "to": "rules", "note": "Back up."})
        self.assertTrue(any(p.startswith("cycle:") for p in _check(self.repo, data)))

    def test_guard_without_a_why_edge_is_reported(self) -> None:
        data = _data()
        data["edges"] = data["edges"][:1]
        self.assertTrue(any("guard gate has no why edge above it" in p for p in _check(self.repo, data)))

    def test_instruction_without_a_how_edge_is_reported(self) -> None:
        data = _data()
        data["edges"] = []
        problems = _check(self.repo, data)
        self.assertTrue(any("instructions node rules has no how edge beneath it" in p for p in problems))

    def test_unlinked_skill_must_be_marked_discretionary(self) -> None:
        data = _data()
        del data["nodes"][2]["discretionary"]
        self.assertTrue(any("skill tool has no why edge above it" in p for p in _check(self.repo, data)))

    def test_discretionary_skill_with_a_why_edge_is_reported(self) -> None:
        data = _data()
        data["edges"].append({"from": "rules", "to": "tool", "note": "Now policy."})
        self.assertTrue(
            any("skill tool is marked discretionary but has a why edge" in p for p in _check(self.repo, data))
        )

    def test_stale_rendered_map_is_reported(self) -> None:
        data = _data()
        output = self.repo / "map.md"
        output.write_text(process_map.render(data), encoding="utf-8")
        changed = copy.deepcopy(data)
        changed["nodes"][1]["purpose"] = "Changed."
        problems = process_map.problems(changed, root=self.repo, output=output)
        self.assertTrue(any("differs from docs/tools/process-map.yaml" in p for p in problems))

    def test_self_edge_is_reported(self) -> None:
        data = _data()
        data["edges"].append({"from": "rules", "to": "rules", "note": "Loop."})
        self.assertTrue(any("rules -> rules points at itself" in p for p in _check(self.repo, data)))

    def test_duplicate_edge_is_reported(self) -> None:
        data = _data()
        data["edges"].append({"from": "rules", "to": "skill-a", "note": "Again."})
        self.assertTrue(any("rules -> skill-a is listed twice" in p for p in _check(self.repo, data)))

    def test_duplicate_node_id_is_reported(self) -> None:
        data = _data()
        data["nodes"].append({**data["nodes"][3], "path": "CLAUDE.md"})
        self.assertTrue(any("duplicate node id gate" in p for p in _check(self.repo, data)))

    def test_duplicate_node_path_is_reported(self) -> None:
        data = _data()
        data["nodes"].append({**data["nodes"][3], "id": "gate-2"})
        self.assertTrue(any("gate.sh is listed as more than one node" in p for p in _check(self.repo, data)))

    def test_unknown_layer_is_reported(self) -> None:
        data = _data()
        data["nodes"][3]["layer"] = "nonsense"
        problems = process_map.problems(data, root=self.repo, output=self.repo / "absent.md")
        self.assertTrue(any("node gate has unknown layer nonsense" in p for p in problems))

    def test_empty_purpose_is_reported(self) -> None:
        data = _data()
        data["nodes"][3]["purpose"] = " "
        self.assertTrue(any("node gate has no purpose" in p for p in _check(self.repo, data)))

    def test_missing_rendered_map_is_reported(self) -> None:
        problems = process_map.problems(_data(), root=self.repo, output=self.repo / "absent.md")
        self.assertTrue(any("docs/process-map.md is missing; run" in p for p in problems))

    def test_drift_is_only_compared_once_the_structure_is_sound(self) -> None:
        data = _data()
        data["edges"].append({"from": "rules", "to": "nowhere", "note": "n."})
        output = self.repo / "map.md"
        output.write_text("stale", encoding="utf-8")
        # Without the early return, rendering a dangling edge raises KeyError instead of reporting it.
        problems = process_map.problems(data, root=self.repo, output=output)
        self.assertTrue(any("missing end" in p for p in problems))

    def test_grouped_map_is_clean_and_renders_one_node_with_a_section(self) -> None:
        (self.repo / "gate2.sh").write_text("x")
        data = _data()
        data["groups"] = [
            {"id": "gates", "label": "Gates", "layer": "guard", "mode": "section", "purpose": "G."}
        ]
        data["nodes"][3]["group"] = "gates"
        data["nodes"].append(
            {"id": "gate2", "path": "gate2.sh", "layer": "guard", "purpose": "Two.", "group": "gates"}
        )
        data["edges"].append({"from": "rules", "to": "gate2", "note": "Also enforces it."})
        self.assertEqual(_check(self.repo, data), [])
        rendered = process_map.render(data)
        self.assertIn("### Gates", rendered)
        self.assertEqual(rendered.count('"Gates"'), 1)
        self.assertNotIn('"gate2"', rendered.split("## ")[1])


if __name__ == "__main__":
    unittest.main()
