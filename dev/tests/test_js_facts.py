"""The export audit follows a dynamic import's namespace past rejection handling."""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "handlers",
    [
        ".catch(() => null)",
        ".finally(() => {})",
        ".catch(() => null).finally(() => {})",
    ],
)
def test_dynamic_import_with_rejection_handler(tmp_path, handlers):
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "target.js"
    target.write_text("export const used = 1; export const unused = 2;")
    reader = tmp_path / "reader.js"
    reader.write_text(
        f'const namespace = ready ? await import("./target.js"){handlers} : null;'
        "if (namespace) namespace.used;"
    )
    result = subprocess.run(
        ["node", "tests/js_facts.mjs", "imports", str(reader)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    facts = json.loads(result.stdout)[str(reader)]
    assert facts["reads"] == [[str(target.relative_to(root, walk_up=True)), "used"]]


@pytest.mark.parametrize(
    ("tag", "names"),
    [
        ("{ Used } from", ["Used"]),
        ("{\n *   Used, Other as Alias\n * } from", ["Other", "Used"]),
        ("* as types from", ["*"]),
    ],
)
def test_jsdoc_import_tag_reads_its_names(tmp_path, tag, names):
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "types.d.ts"
    target.write_text("export type Used = 1; export type Other = 2;")
    reader = tmp_path / "reader.js"
    reader.write_text(f'/** @import {tag} "./types.js" */\nexport const value = 1;\n')
    result = subprocess.run(
        ["node", "tests/js_facts.mjs", "imports", str(reader)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    facts = json.loads(result.stdout)[str(reader)]
    assert sorted(name for _, name in facts["reads"]) == names
