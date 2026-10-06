"""Literal CSS readers retain relevant tests across real Git snapshots and facades."""

import os
import subprocess

import pytest
from leaf_dev.test_select.css import literal_witnesses
from leaf_dev.test_select.evidence import EvidenceIndex


@pytest.mark.parametrize(
    ("initial", "candidate", "selected"),
    [
        (":root {--room: 4px}", ":root {--room: 7px}", True),
        (":root {--room: 4px}", "html.dark {--room: 4px}", True),
        (
            "@media (width < 800px) {:root {--room: 4px}}",
            "@media (width < 700px) {:root {--room: 4px}}",
            True,
        ),
        (":root {--room: 4px}", ":root {--room: 4em}", True),
        (":root {--room: 4px}", "/* prose var(--room) */ :root {--room: 4px}", False),
    ],
)
def test_literal_reads_follow_changed_producer_through_facade(
    tmp_path, initial, candidate, selected
):
    root = tmp_path / "repository"
    root.mkdir()
    sources = {
        "theme.css": initial + "\n:root {--alias: var(--room); --other: 9px}\n",
        "tests/origin.py": """MEASURE = "() => getComputedStyle(document.body).getPropertyValue('--alias')"
PAGE = "<style>p {width: var(--alias)}</style><p style='height:var(--alias)'>hi</p>"
PROBE = "() => { const p=document.createElement('i'); p.style.cssText='height:0;'+'width:var(--alias)'; return p.getBoundingClientRect().width; }"
""",
        "tests/facade.py": "from origin import MEASURE, PAGE, PROBE\n",
        "tests/test_readings.py": """from facade import MEASURE, PAGE, PROBE
def test_measure():
    assert MEASURE
def test_page():
    assert PAGE
def test_probe():
    assert PROBE
def test_independent():
    assert "() => getComputedStyle(document.body).getPropertyValue('--other')"
def test_prose():
    assert "var(--alias)"
    assert "<p>var(--alias)</p>"
    assert "() => 1 /* getComputedStyle(document.body).getPropertyValue('--alias') */"
    assert "<style>p {content:'var(--alias)'}</style>"
""",
    }
    for path, source in sources.items():
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }

    def git(*arguments):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgsign=false", *arguments],
            cwd=root,
            env=env,
            text=True,
        ).strip()

    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (root / "theme.css").write_text(
        candidate + "\n:root {--alias: var(--room); --other: 9px}\n"
    )
    git("add", ".")
    git("commit", "-qm", "candidate")
    after = EvidenceIndex(root, git("rev-parse", "HEAD"))
    module = after.module("tests/test_readings.py")
    manifest = [
        {
            "nodeid": f"tests/test_readings.py::{name}",
            "file": "tests/test_readings.py",
            "function": name,
            "line": node.lineno,
            "params": {},
        }
        for name, node in module["definitions"].items()
    ]
    result = literal_witnesses(
        EvidenceIndex(root, base),
        after,
        manifest,
        contexts={item["nodeid"]: after.test_context(item) for item in manifest},
    )
    assert set(result["witnesses"]) == (
        {
            "tests/test_readings.py::test_measure",
            "tests/test_readings.py::test_page",
            "tests/test_readings.py::test_probe",
        }
        if selected
        else set()
    )
    for witnesses in result["witnesses"].values():
        witness = witnesses[0]
        assert witness["property"] == "--alias"
        assert witness["reader"]["path"] == "tests/origin.py"
        assert witness["producer"]["property"] == "--room"
        assert witness["aliases"][0]["source"]["path"] == "theme.css"
        assert 1 <= witness["reader"]["start"] <= witness["reader"]["end"] <= 3
