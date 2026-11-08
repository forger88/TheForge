#!/usr/bin/env python3
"""Builds and checks docs/process-map.md from docs/tools/process-map.yaml.

The YAML file is the single source: the D2 graph (emitted as a fenced
```d2``` block the project's own doc-build pipeline renders, not a
separately pre-rendered image), the node tables and the ASCII annex are
all rendered from it, so they cannot disagree.

    python3 docs/tools/process_map.py build   # rewrite docs/process-map.md
    python3 docs/tools/process_map.py index   # rewrite docs/agents/skills-index.md
    python3 docs/tools/process_map.py check   # exit 1 on any problem

Needs pyyaml; the `process-map` pre-commit hook that
`.agents/skills/process-map-setup/SKILL.md` wires in runs this as a
pre-commit `language: python` hook, which installs it into that hook's own
isolated venv automatically (see `additional_dependencies` on that hook)
-- no project-wide install is needed just to run `check` on every commit.

`check` fails on: a node whose path is missing, a process file (skill,
agent doc, workflow) with no node, a dangling or duplicate edge, an edge
without a note, a cycle, a guard with nothing above it, an instruction or
foundation node with nothing beneath it, a skill whose discretionary flag
disagrees with its edges, and a rendered map or skills index that differs
from the source.
The skills index is a flat list of the skill and reference nodes: one line each,
name, purpose and path, generated so a thread can find a skill without reading
every rule file by hand.
Graph code (cycle check, transitive reduction, tree walk) is hand-rolled, about
60 lines, rather than networkx: the pre-commit hook then needs only pyyaml.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "tools" / "process-map.yaml"
OUTPUT_NAME = "docs/process-map.md"
OUTPUT = ROOT / OUTPUT_NAME
INDEX_NAME = "docs/agents/skills-index.md"
INDEX_OUTPUT = ROOT / INDEX_NAME
INDEX_LAYERS = ("skill", "reference")


class Problem(str):
    """A `problems()` entry, tagged with the kind of check that raised it.

    `"structure"` (the default) is a source-file error `build` and `index`
    must refuse to regenerate past (a dangling edge, a missing path, and
    the like). `"drift"` is a generated file (the map, its SVG, the skills
    index) not yet matching its source -- the normal state right before
    `build`/`index` write it, so those two commands skip only this kind
    rather than matching message text against a prefix list, which would
    silently stop meaning "ignore this" the moment the message's wording
    changed.
    """

    kind: str

    def __new__(cls, message: str, kind: str = "structure") -> Problem:
        self = super().__new__(cls, message)
        self.kind = kind
        return self


LAYER_ORDER = [
    "instructions",
    "foundation",
    "settings",
    "tracker",
    "skill",
    "reference",
    "guard",
]
LAYER_TITLES = {
    "instructions": "Instructions",
    "foundation": "Foundation",
    "settings": "Settings",
    "tracker": "Tracker tickets",
    "skill": "Skills",
    "reference": "Reference",
    "guard": "Guards",
}
LAYER_FILL = {
    "instructions": "#f4c7c3",
    "foundation": "#fce8b2",
    "settings": "#d9d2e9",
    "tracker": "#fff2cc",
    "skill": "#cfe2f3",
    "reference": "#e6e6e6",
    "guard": "#d9ead3",
}
# Directories whose every matching file must be a node (one node per file).
# Generic across every forge-generated project; a project that adds its own
# process-relevant directory (e.g. a second skills tree) extends this list
# at the same time it edits process-map.yaml to match.
COMPLETE_GLOBS = [
    ".agents/skills/*/SKILL.md",
    "docs/agents/*.md",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
]


def load(source: Path = SOURCE) -> dict:
    return yaml.safe_load(source.read_text(encoding="utf-8"))


def _node_problems(data: dict, root: Path) -> list[Problem]:
    found: list[Problem] = []
    nodes = data["nodes"]
    ids = [n["id"] for n in nodes]
    by_id = {n["id"]: n for n in nodes}
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        found.append(Problem(f"duplicate node id {dup}"))
    paths = [n["path"] for n in nodes if "path" in n]
    for dup in sorted({p for p in paths if paths.count(p) > 1}):
        found.append(Problem(f"path {dup} is listed as more than one node"))
    groups = {g["id"]: g for g in data.get("groups", [])}
    for gid in groups:
        if gid in by_id:
            found.append(Problem(f"group id {gid} is also a node id"))
    for n in nodes:
        if n["layer"] not in data["layers"]:
            found.append(Problem(f"node {n['id']} has unknown layer {n['layer']}"))
        if n["layer"] == "tracker":
            if not re.fullmatch(r"#\d+", str(n.get("ref", ""))):
                # No literal "#" + digits here: this file is itself scanned by the
                # no-issue-refs pre-commit hook, which can't tell a format example
                # from a real reference.
                found.append(Problem(f"tracker node {n['id']} needs a ref shaped like '#' + digits"))
        elif "path" not in n:
            found.append(Problem(f"node {n['id']} has no path"))
        elif not (root / n["path"]).is_file():
            found.append(Problem(f"node {n['id']}: path {n['path']} does not exist"))
        if not n.get("purpose", "").strip():
            found.append(Problem(f"node {n['id']} has no purpose"))
        if "group" in n:
            group = groups.get(n["group"])
            if group is None:
                found.append(Problem(f"node {n['id']} is in unknown group {n['group']}"))
            elif group["layer"] != n["layer"]:
                found.append(
                    Problem(f"node {n['id']} and its group {n['group']} are in different layers")
                )
    for gid, group in groups.items():
        if group.get("mode") not in ("section", "row"):
            found.append(Problem(f"group {gid} has unknown mode {group.get('mode')}"))
        if not any(n.get("group") == gid for n in nodes):
            found.append(Problem(f"group {gid} has no members"))
    listed = set(paths)
    for pattern in COMPLETE_GLOBS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            # The generated index sits under docs/agents/ but is an output, not a process file.
            if rel not in listed and rel != INDEX_NAME:
                found.append(Problem(f"{rel} is a process file with no node"))
    return found


def _edge_problems(data: dict) -> tuple[list[Problem], dict[str, int], dict[str, int]]:
    found: list[Problem] = []
    nodes = data["nodes"]
    ids = [n["id"] for n in nodes]
    by_id = {n["id"]: n for n in nodes}
    incoming: dict[str, int] = {i: 0 for i in ids}
    outgoing: dict[str, int] = {i: 0 for i in ids}
    seen: set[tuple[str, str]] = set()
    children: dict[str, list[str]] = {i: [] for i in ids}
    for e in data["edges"]:
        src, dst = e["from"], e["to"]
        if src not in by_id or dst not in by_id:
            found.append(Problem(f"edge {src} -> {dst} has a missing end"))
            continue
        if src == dst:
            found.append(Problem(f"edge {src} -> {dst} points at itself"))
            continue
        if (src, dst) in seen:
            found.append(Problem(f"edge {src} -> {dst} is listed twice"))
        seen.add((src, dst))
        if not str(e.get("note", "")).strip():
            found.append(Problem(f"edge {src} -> {dst} has no note"))
        outgoing[src] += 1
        incoming[dst] += 1
        children[src].append(dst)
    found.extend(Problem(c) for c in _cycles(children))
    return found, incoming, outgoing


def _connectivity_problems(
    nodes: list[dict], incoming: dict[str, int], outgoing: dict[str, int]
) -> list[Problem]:
    found: list[Problem] = []
    for n in nodes:
        i, layer = n["id"], n["layer"]
        if layer in ("guard", "tracker") and incoming[i] == 0:
            found.append(Problem(f"{layer} {i} has no why edge above it"))
        if layer in ("instructions", "foundation") and outgoing[i] == 0:
            found.append(Problem(f"{layer} node {i} has no how edge beneath it"))
        if layer == "skill":
            if n.get("discretionary") and incoming[i]:
                found.append(
                    Problem(f"skill {i} is marked discretionary but has a why edge above it")
                )
            if not n.get("discretionary") and incoming[i] == 0:
                found.append(
                    Problem(f"skill {i} has no why edge above it; link it or mark it discretionary")
                )
    return found


def _drift_problems(data: dict, root: Path, output: Path, index_output: Path | None) -> list[Problem]:
    found: list[Problem] = []
    if not output.exists():
        found.append(Problem(f"{OUTPUT_NAME} is missing; run `process_map.py build`", "drift"))
    elif output.read_text(encoding="utf-8") != render(data):
        found.append(
            Problem(
                f"{OUTPUT_NAME} differs from docs/tools/process-map.yaml; run `process_map.py build`",
                "drift",
            )
        )
    index = index_output if index_output is not None else root / INDEX_NAME
    if not index.exists():
        found.append(Problem(f"{INDEX_NAME} is missing; run `process_map.py index`", "drift"))
    elif index.read_text(encoding="utf-8") != render_index(data):
        found.append(
            Problem(
                f"{INDEX_NAME} differs from docs/tools/process-map.yaml; run `process_map.py index`",
                "drift",
            )
        )
    return found


def problems(
    data: dict,
    root: Path = ROOT,
    output: Path = OUTPUT,
    index_output: Path | None = None,
) -> list[Problem]:
    found = _node_problems(data, root)
    edge_found, incoming, outgoing = _edge_problems(data)
    found += edge_found
    found += _connectivity_problems(data["nodes"], incoming, outgoing)
    if found:
        return found  # a drift comparison would only repeat these, or crash on a dangling edge
    return _drift_problems(data, root, output, index_output)


def _cycles(children: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    found: list[str] = []

    def visit(node: str, trail: list[str]) -> None:
        state[node] = 1
        for nxt in children[node]:
            if state.get(nxt) == 1:
                found.append("cycle: " + " -> ".join(trail + [node, nxt]))
            elif nxt not in state:
                visit(nxt, trail + [node])
        state[node] = 2

    for start in children:
        if start not in state:
            visit(start, [])
    return found


def _view(data: dict) -> dict:
    """The map as drawn: grouped members collapse into one node each.

    Edges are rewritten to the group, duplicates merged (their notes
    joined) and edges inside a group dropped; ungrouped data passes through.
    """
    groups = {g["id"]: g for g in data.get("groups", [])}
    member_of = {n["id"]: n["group"] for n in data["nodes"] if "group" in n}
    nodes = [n for n in data["nodes"] if "group" not in n]
    for gid, group in groups.items():
        members = [n for n in data["nodes"] if n.get("group") == gid]
        nodes.append(
            {
                "id": gid,
                "label": group["label"],
                "layer": group["layer"],
                "purpose": group["purpose"],
                "mode": group["mode"],
                "members": members,
            }
        )
    merged: dict[tuple[str, str], list[str]] = {}
    for e in data["edges"]:
        src, dst = member_of.get(e["from"], e["from"]), member_of.get(e["to"], e["to"])
        if src == dst:
            continue
        notes = merged.setdefault((src, dst), [])
        note = e["note"].rstrip(".")
        if note not in notes:
            notes.append(note)
    edges = [
        {"from": s, "to": d, "note": "; ".join(notes) + "."} for (s, d), notes in merged.items()
    ]
    return {"nodes": nodes, "edges": edges}


def _label(node: dict) -> str:
    return node.get("label", node["id"])


def _ordered(data: dict) -> list[dict]:
    rank = {layer: i for i, layer in enumerate(LAYER_ORDER)}
    return sorted(data["nodes"], key=lambda n: (rank[n["layer"]], n["id"]))


def _d2(view: dict) -> str:
    lines = ["direction: down", ""]
    linked = [n for n in _ordered(view) if not n.get("discretionary")]
    for layer in LAYER_ORDER:
        lines.append(f"# {LAYER_TITLES[layer]}")
        for n in linked:
            if n["layer"] == layer:
                fill = LAYER_FILL[layer]
                lines.append(f'{_d2id(n["id"])}: "{_label(n)}" {{style.fill: "{fill}"}}')
    lines.append("")
    for e in _reduced(view):
        lines.append(f"{_d2id(e['from'])} -> {_d2id(e['to'])}")
    return "\n".join(lines)


def _reduced(data: dict) -> list[dict]:
    """Edges not already implied by a longer path (transitive reduction)."""
    children: dict[str, set[str]] = {n["id"]: set() for n in data["nodes"]}
    for e in data["edges"]:
        children[e["from"]].add(e["to"])

    def reachable(start: str, skip: str, target: str) -> bool:
        stack = [c for c in children[start] if c != skip]
        seen = set(stack)
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            for nxt in children[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    return [e for e in data["edges"] if not reachable(e["from"], e["to"], e["to"])]


def _d2id(node_id: str) -> str:
    return node_id.replace("-", "_")


def _ascii(view: dict) -> str:
    by_id = {n["id"]: n for n in view["nodes"]}
    children: dict[str, list[tuple[str, str]]] = {n["id"]: [] for n in view["nodes"]}
    has_parent: set[str] = set()
    for e in view["edges"]:
        children[e["from"]].append((e["to"], e["note"]))
        has_parent.add(e["to"])
    order = {n["id"]: i for i, n in enumerate(_ordered(view))}
    for kids in children.values():
        kids.sort(key=lambda kv: order[kv[0]])
    roots = [
        n["id"] for n in _ordered(view) if n["id"] not in has_parent and not n.get("discretionary")
    ]
    out: list[str] = []
    printed: set[str] = set()

    def walk(node: str, prefix: str, note: str | None, last: bool, top: bool) -> None:
        label = _label(by_id[node])
        if top:
            out.append(label)
        else:
            branch = "`-- " if last else "|-- "
            suffix = f"  [{note}]" if note else ""
            again = "  (above)" if node in printed else ""
            out.append(f"{prefix}{branch}{label}{again}{suffix}")
        if node in printed:
            return
        printed.add(node)
        kids = children[node]
        child_prefix = prefix if top else prefix + ("    " if last else "|   ")
        for i, (kid, kid_note) in enumerate(kids):
            walk(kid, child_prefix, kid_note, i == len(kids) - 1, False)

    for root in roots:
        walk(root, "", None, True, True)
        out.append("")
    out.append("Discretionary skills (no policy link):")
    for n in [n for n in _ordered(view) if n.get("discretionary")]:
        out.append(f"  {n['id']} ({n['path']})")
    return "\n".join(out)


def _file_cell(n: dict) -> str:
    if n["layer"] == "tracker":
        return n["ref"]
    if "members" in n:
        if n["mode"] == "section":
            return f"see the {_label(n)} section below"
        return "see Purpose"
    return f"`{n['path']}`"


def _node_table(nodes: list[dict]) -> list[str]:
    rows = ["| Layer | Node | File | Purpose |", "| --- | --- | --- | --- |"]
    for n in nodes:
        purpose = n["purpose"].rstrip(".") + "."
        if n.get("mode") == "row":
            files = ", ".join(f"`{m['path']}`" for m in n["members"])
            purpose += f" Files: {files}."
        rows.append(f"| {LAYER_TITLES[n['layer']]} | `{_label(n)}` | {_file_cell(n)} | {purpose} |")
    return rows


def render(data: dict) -> str:
    view = _view(data)
    parts = [
        "<!-- Generated by docs/tools/process_map.py from docs/tools/process-map.yaml. Do not edit by hand. -->",
        "",
        "# Process map: how and why",
        "",
        "This map shows how the files that carry this project's development process build on each",
        "other: the instructions, the skills, the agent reference and settings files, the standing",
        "tracker tickets, and the mechanical guards. It is not a map of the product documents.",
        "",
        "Each edge points from the file that sets an intent to the file that implements or enforces",
        "part of it. Read downwards for **how** (what implements this) and upwards for **why** (what",
        "this serves). The reverse of an edge is not stored separately.",
        "",
        "Source: `docs/tools/process-map.yaml`. Rebuild with `python3 docs/tools/process_map.py build`",
        "(needs pyyaml); the graph below renders as an image once this document is built through the",
        "project's doc-build pipeline. The same script's `check` command, run by the pre-commit hooks",
        "this project's `process-map-setup` skill wired in, fails when a listed path is missing, a",
        "process file has no node, an edge is dangling, or a guard, tracker, instruction or foundation",
        "node is unlinked.",
        "",
        "Scope: this repository only. Every skill, agent doc, workflow and listed guard file is one",
        "entry in the source file. The graph draws a group of files as one node, and the tables list",
        "the files inside it. Tracker tickets are nodes too, named by issue number. Discretionary",
        "skills are tools, not policy: they have no why edge and appear in the tables, not the graph.",
        "",
        "## Graph",
        "",
        "```d2",
        _d2(view),
        "```",
        "",
        "## Nodes on the graph",
        "",
    ]
    parts += _node_table([n for n in _ordered(view) if not n.get("discretionary")])
    parts += ["", "## Discretionary nodes", ""]
    parts += _node_table([n for n in _ordered(view) if n.get("discretionary")])
    for n in _ordered(view):
        if n.get("mode") == "section":
            parts += ["", f"### {_label(n)}", "", "| File | Purpose |", "| --- | --- |"]
            for m in sorted(n["members"], key=lambda m: m["path"]):
                parts.append(f"| `{m['path']}` | {m['purpose'].rstrip('.')}. |")
    parts += [
        "",
        "## Annex: linkage diagram (plain text)",
        "",
        "The same edges as an indented tree, for when the graph cannot be rendered or read. A node",
        "that already appeared is marked `(above)` and not expanded again. Notes are in brackets.",
        "",
        "```text",
        _ascii(view),
        "```",
        "",
    ]
    return "\n".join(parts)


def render_index(data: dict) -> str:
    """Flat list of skill and reference nodes: one line each, sorted by path.

    Discretionary skills follow in their own section, so an agent sees which
    entries carry no policy link.
    """
    entries = sorted(
        (n for n in data["nodes"] if n["layer"] in INDEX_LAYERS), key=lambda n: n["path"]
    )

    def line(n: dict) -> str:
        return f"- **{n['id']}** -- {n['purpose']} -- `{n['path']}`"

    linked = [line(n) for n in entries if not n.get("discretionary")]
    loose = [line(n) for n in entries if n.get("discretionary")]
    parts = [
        "<!-- Generated by docs/tools/process_map.py index from docs/tools/process-map.yaml. Do not edit by hand. -->",
        "",
        "# Skills and reference docs index",
        "",
        "One line per skill and reference doc: name, trigger, and path. Regenerate with",
        "`python3 docs/tools/process_map.py index` (needs pyyaml) after changing",
        "`docs/tools/process-map.yaml`.",
        "",
        "## Policy-linked skills and reference docs",
        "",
        *linked,
        "",
        "## Discretionary (pick up ad hoc, no policy link)",
        "",
        *loose,
        "",
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in ("build", "check", "index"):
        print("usage: process_map.py build|check|index", file=sys.stderr)
        return 2
    data = load()
    if args[0] == "build":
        found = [p for p in problems(data) if p.kind != "drift"]
        if found:
            print("\n".join(found), file=sys.stderr)
            return 1
        OUTPUT.write_text(render(data), encoding="utf-8")
        return 0
    if args[0] == "index":
        found = [p for p in problems(data) if p.kind != "drift"]
        if found:
            print("\n".join(found), file=sys.stderr)
            return 1
        INDEX_OUTPUT.write_text(render_index(data), encoding="utf-8")
        return 0
    found = problems(data)
    for line in found:
        print(f"process-map: {line}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
