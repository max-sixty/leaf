"""What `tests/js_facts.mjs` reads out of a module: each press with how a role dresses
it."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def facts(command, module):
    result = subprocess.run(
        ["node", "tests/js_facts.mjs", command, str(module)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)[str(module)]


# One press a line, each in a block of its own. The first four are presses the press
# check once missed: spacing or a bound role that hid one, and a method named after
# `copyControl` taken for it. Then the ways a role dresses a press: in its tag,
# through a name, as it is made, in a copy control's options, around a trigger, and
# through the name a made button is bound to; a scripted role never dressed; a name
# dressed and then given another button, over two lines of one block, whose buttons
# neither reads as dressed; and a pure template that writes a role's face into its
# class.
PRESSES = """\
{ document.createElement ("button"); }
{ html`<div role = "button" class="lf-grip">`; }
{ html`<div role=${"button"} class="lf-grip">`; }
{ class M { #copyControl() { return copyControl("lf-x", { role: "symbol" }); } go() { this.#copyControl(); } } }
{ html`<button class="own-face">`; }
{ offer("button", "own-face"); }
{ html`<button ${offeredAction("word", "lf-x")}>`; }
{ const close = offeredAction("symbol", "", "Close"); html`<button ${close}>`; }
{ offerActionElement(document.createElement("button"), "symbol"); }
{ copyControl("lf-x", { role: "symbol" }); }
{ copyControl("lf-x", { trigger: true }); }
{ const button = document.createElement("button"); offerActionElement(button, "word", "lf-x"); }
{ const grip = offer("span", "lf-grip"); grip.setAttribute("role", "button"); }
{ let button = document.createElement("button"); offerActionElement(button, "word", "lf-old");
  button = document.createElement("button"); }
{ html`<button class=${`${actionClass("word", "lf-x")} lf-ui`}>`; }
"""
# Each line's press: the kind it is read as and how a role dresses it.
READ = [
    ("made", None),
    ("template", None),
    ("template", None),
    ("copy control", "role in its options"),
    ("template", None),
    ("made", None),
    ("template", "role in its tag"),
    ("template", "role through a name"),
    ("made", "role as it is made"),
    ("copy control", "role in its options"),
    ("copy control", "trigger in its options"),
    ("made", "role as it is made"),
    ("scripted role", None),
    ("made", None),
    ("made", None),
    ("template", "role in its tag"),
]


def test_each_press_is_read_with_how_a_role_dresses_it(tmp_path):
    module = tmp_path / "presses.js"
    module.write_text(PRESSES)
    read = [(p["line"], p["kind"], p["built"]) for p in facts("presses", module)]
    assert read == [(line, *press) for line, press in enumerate(READ, 1)]
