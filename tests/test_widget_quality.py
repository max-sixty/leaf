"""The widget quality report (`leaf/render_gate/widget_quality.py`): Leaf's own widgets
held to it, and `package check --render` telling a package's author what it found."""

import json
import os
import re
import subprocess

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import SKILL_ROOT
from known_widget_findings import KNOWN
from leaf import cli as cli_model
from leaf import schema as schema_model
from leaf.render_gate.widget_quality import widget_findings

# The base layer's two halves and every bundled package, each reported on its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(path for path in (SKILL_ROOT / "packages").iterdir() if path.is_dir()),
]


def test_every_known_finding_names_a_bundled_package():
    """An entry under a package that is gone is never compared, so never deleted."""
    assert set(KNOWN) <= {package.name for package in PACKAGES}


@pytest.mark.parametrize("package", PACKAGES, ids=lambda package: package.name)
def test_bundled_widgets_meet_the_widget_quality_checks(browser, package):
    """Each bundled package's report finds exactly what `known_widget_findings.py`
    lists for it: a new finding is a regression to fix, and a listed one that no
    longer occurs was fixed, so its entry goes. The pages it reads are full of the
    shifts the check exists to find, so it reads them unwatched."""
    findings = widget_findings(browser.unwatched, package)
    known = KNOWN.get(package.name, set())
    new = [
        str(finding)
        for finding in findings
        if (finding.tag, finding.check) not in known
    ]
    assert not new, "findings known_widget_findings.py does not list:\n" + "\n".join(
        new
    )
    fixed = known - {(finding.tag, finding.check) for finding in findings}
    assert not fixed, f"fixed, so delete from known_widget_findings.py: {sorted(fixed)}"


GROWS_AT_UPGRADE = """\
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-grow",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const grown = document.createElement("div");
      grown.style.height = "40px";
      this.append(grown);
    }
  },
);
"""


def test_package_check_render_reports_findings_as_advice(tmp_path, headless_shell):
    """`package check --render` names each finding by tag, check and measured fact,
    and still exits 0. `lf-grow` adds 40px at upgrade, on its own and inside
    `lf-holder`, which grows by exactly that and so is not named beside it; `lf-bare`
    has no worked example."""
    package = tmp_path / "package"
    for widget in ("lf-grow", "lf-holder", "lf-bare"):
        made = CliRunner().invoke(
            cli_model.cli, ["package", "init", str(package), "--widget", widget]
        )
        assert made.exit_code == 0, made.output
    (package / "widgets" / "lf-grow.js").write_text(GROWS_AT_UPGRADE)
    # An element the theme does not style is inline, and a block it gains at
    # upgrade would widen it as well as grow it.
    (package / "theme.css").write_text("lf-grow, lf-holder { display: block; }\n")
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-holder"]["x-example"] = (
        '<lf-holder id="holder"><lf-grow id="held">Held.</lf-grow></lf-holder>'
    )
    del registry["lf-bare"]["x-example"]
    registry_path.write_text(json.dumps(registry))

    ran = subprocess.run(
        [*LEAF_COMMAND, "package", "check", str(package), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert lines[1] == (
        f"widget quality: 3 finding(s) for 3 widget(s) in {headless_shell}, "
        "advice for the widgets' author:"
    )
    assert lines[2] == "  · <lf-bare> example: no worked example shows it"
    grew = re.compile(
        r"  · <lf-grow id='(\w+)'> keeps-first-box: "
        r"first painted (\d+)x(\d+), (\d+)x(\d+) once presented"
    )
    readings = [grew.fullmatch(line) for line in lines[3:]]
    assert all(readings), lines
    assert [reading[1] for reading in readings] == ["grow", "held"]
    for reading in readings:
        first_height, now_height = int(reading[3]), int(reading[5])
        assert now_height - first_height == 40, reading[0]
