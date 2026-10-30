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


def test_javascript_import_reads_typescript_owner(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    owner = tmp_path / "owner.ts"
    owner.write_text(
        "export interface Reading { read(): number }; export const value = 1;"
    )
    (tmp_path / "owner.js").write_text("export const value = 1;")
    reader = tmp_path / "reader.js"
    reader.write_text(
        '/** @typedef {import("./owner.js").Reading} Reading */\nimport {value} from "./owner.js"; console.log(value);'
    )
    result = subprocess.run(
        ["node", "tests/js_facts.mjs", "imports", str(reader)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    reads = json.loads(result.stdout)[str(reader)]["reads"]
    relative = str(owner.relative_to(root, walk_up=True))
    assert sorted(reads) == sorted([[relative, "Reading"], [relative, "value"]])
