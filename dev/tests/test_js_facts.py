"""What `tests/js_facts.mjs` reads out of a module: a dynamic import's namespace past
rejection handling, and each press with the classes it is built with."""

import json
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "handlers",
    [
        ".catch(() => null)",
        ".finally(() => {})",
        ".catch(() => null).finally(() => {})",
    ],
)
def test_dynamic_import_with_rejection_handler(tmp_path, handlers):
    target = tmp_path / "target.js"
    target.write_text("export const used = 1; export const unused = 2;")
    reader = tmp_path / "reader.js"
    reader.write_text(
        f'const namespace = ready ? await import("./target.js"){handlers} : null;'
        "if (namespace) namespace.used;"
    )
    assert facts("imports", reader)["reads"] == [
        [str(target.relative_to(ROOT, walk_up=True)), "used"]
    ]


# One press a line, each in a block of its own. The first eight, and the five after
# them, are presses the press check once misread: a family name in a title or a label
# taken for a class, a `className` given to another block's `button`, spacing or a
# bound role that hid a press, a `>` inside a quoted attribute that ended the tag; a
# `className` on a parameter given to an unrelated `button`, a family name joined to
# more text, an escaped quote read raw, and Lit's `classMap` unread; and a method
# named after `copyControl` taken for it. Then a copy control around a trigger, a
# made button dressed by role through the name it is bound to, one never dressed, and
# a name dressed and then given another button, over two lines of one block, whose
# buttons neither reads as dressed.
PRESSES = """\
{ html`<button class="own-face" title="lf-react">`; }
{ offer("button", "own-face", "lf-react"); }
{ const button = document.createElement("button"); }
{ const button = document.createElement("button"); button.className = "lf-media-open"; }
{ document.createElement ("button"); }
{ html`<div role = "button" class="lf-grip">`; }
{ html`<div role=${"button"} class="lf-grip">`; }
{ html`<button title="a > b" class="lf-react">`; }
{ html`<button ${offeredAction("word", "lf-x")}>`; }
{ const close = offeredAction("symbol", "", "Close"); html`<button ${close}>`; }
{ offerActionElement(document.createElement("button"), "symbol"); }
{ copyControl("lf-x", { role: "symbol" }); }
{ const grip = offer("span", "lf-grip"); grip.setAttribute("role", "button"); }
{ function style(button) { button.className = "lf-react"; } function make() { return document.createElement("button"); } }
{ offer("button", "lf-react" + "-icon"); }
{ html`<button class="lf-react${suffix}">`; }
{ html`<button title=\\"a > b\\" class="lf-react">`; }
{ html`<button class=${classMap({ "lf-react": true, "lf-off": false, own: on })}>`; }
{ class M { #copyControl() { return copyControl("lf-x", { role: "symbol" }); } go() { this.#copyControl(); } } }
{ copyControl("lf-x", { trigger: true }); }
{ const button = document.createElement("button"); offerActionElement(button, "word", "lf-x"); }
{ const button = document.createElement("button"); button.className = "lf-x"; }
{ let button = document.createElement("button"); offerActionElement(button, "word", "lf-old");
  button = document.createElement("button"); }
"""
# Each line's press: the kind it is read as, how a role dresses it, and its classes.
READ = [
    ("template", None, ["own-face"]),
    ("made", None, ["own-face"]),
    ("made", None, []),
    ("made", None, ["lf-media-open"]),
    ("made", None, []),
    ("template", None, ["lf-grip"]),
    ("template", None, ["lf-grip"]),
    ("template", None, ["lf-react"]),
    ("template", "role in its tag", ["lf-x"]),
    ("template", "role through a name", []),
    ("made", "role as it is made", []),
    ("copy control", "role in its options", ["lf-x"]),
    ("scripted role", None, ["lf-grip"]),
    ("made", None, []),
    ("made", None, []),
    ("template", None, []),
    ("template", None, ["lf-react"]),
    ("template", None, ["lf-react", "own"]),
    ("copy control", "role in its options", ["lf-x"]),
    ("copy control", "trigger in its options", ["lf-x"]),
    ("made", "role as it is made", ["lf-x"]),
    ("made", None, ["lf-x"]),
    ("made", None, []),
    ("made", None, []),
]


def test_each_press_is_read_with_the_classes_it_is_built_with(tmp_path):
    module = tmp_path / "presses.js"
    module.write_text(PRESSES)
    read = [
        (p["line"], p["kind"], p["built"], p["classes"])
        for p in facts("presses", module)
    ]
    assert read == [(line, *press) for line, press in enumerate(READ, 1)]
