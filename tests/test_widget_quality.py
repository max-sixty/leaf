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


def grows_at_upgrade(tag: str, style: str) -> str:
    """A widget module that writes `style` onto its element when it upgrades."""
    return f"""\
import {{ once }} from "/runtime/widget-api.js";

customElements.define(
  "{tag}",
  class extends HTMLElement {{
    connectedCallback() {{
      if (once(this)) this.style.cssText = "{style}";
    }}
  }},
);
"""


def test_package_check_render_reports_findings_as_advice(tmp_path, headless_shell):
    """`package check --render` names each finding by tag, check and measured fact,
    and still exits 0. `lf-grow` adds 40px at upgrade, on its own and inside two
    holders: `lf-holder` grows by exactly that and so is not named beside it, and
    `lf-padded` grows 10px more on its own and is. `lf-bare` has no worked example."""
    package = tmp_path / "package"
    for widget in ("lf-grow", "lf-holder", "lf-padded", "lf-bare"):
        made = CliRunner().invoke(
            cli_model.cli, ["package", "init", str(package), "--widget", widget]
        )
        assert made.exit_code == 0, made.output
    widgets = package / "widgets"
    (widgets / "lf-grow.js").write_text(
        grows_at_upgrade("lf-grow", "padding-bottom: 40px")
    )
    (widgets / "lf-padded.js").write_text(
        grows_at_upgrade("lf-padded", "padding-bottom: 10px")
    )
    # An element the theme does not style is inline, whose box a padding would not
    # grow the way a block's grows.
    (package / "theme.css").write_text(
        "lf-grow, lf-holder, lf-padded { display: block; }\n"
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-holder"]["x-example"] = (
        '<lf-holder id="holder"><lf-grow id="held">Held.</lf-grow></lf-holder>'
    )
    registry["lf-padded"]["x-example"] = (
        '<lf-padded id="padded"><lf-grow id="inner">Inner.</lf-grow></lf-padded>'
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
        f"widget quality: 5 finding(s) for 4 widget(s) in {headless_shell}, "
        "advice for the widgets' author:"
    )
    assert lines[2] == "  · <lf-bare> example: no worked example shows it"
    finding = re.compile(
        r"  · <(lf-[a-z]+) id='(\w+)'> keeps-first-box: "
        r"first painted (\d+)x(\d+), (\d+)x(\d+) once presented"
    )
    readings = [finding.fullmatch(line) for line in lines[3:]]
    assert all(readings), lines
    grown = {reading[2]: int(reading[6]) - int(reading[4]) for reading in readings}
    assert grown == {"grow": 40, "held": 40, "padded": 50, "inner": 40}, lines
