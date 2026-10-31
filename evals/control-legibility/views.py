"""Capture each view this eval asks about: a picture with every control numbered, and
what each numbered control does.

A `leaf-dev probe` journey (README.md, "Run"). The views draw Leaf's own controls
from this working tree into a fixture page, so a capture shows what the runtime draws.

A view is a region of the page. `NUMBER` tags each control in it with a magenta number
beside it, outside the control, so the picture shows the control as the user sees it
and the number only names it. A control's truth is the actions it may stand for, each
with what pressing it does (`actions.json`): for a symbol drawn alone, every action
that shows it, since the symbol can't say which of them it is.
"""

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path(os.environ.get("LEGIBILITY_OUT", ".tmp/control-legibility"))

# Every action a press can show as a symbol, read from the module that owns them, and
# what each does, which only this eval records.
ACTIONS = json.loads(
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "const { ACTIONS } = await import(process.argv[1]);"
            " console.log(JSON.stringify(ACTIONS));",
            str((HERE / "../../browser/runtime/icon-paths.js").resolve()),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
)
DOES = json.loads((HERE / "actions.json").read_text())
if unknown := set(ACTIONS) ^ set(DOES):
    raise SystemExit(
        f"actions.json and ACTIONS differ on: {', '.join(sorted(unknown))}"
    )
VOCABULARY = [{"name": ACTIONS[a]["name"], "does": DOES[a]} for a in ACTIONS]

# Each icon once, as the symbol press of the first action that shows it, in a grid.
SYMBOL_SHEET = """async (actions) => {
  const entry = document.querySelector("script[data-lf-entry]").dataset.lfEntry;
  const api = new URL("runtime/widget-api.js", new URL(entry, location.href));
  const { offerAction } = await import(api);
  const byIcon = new Map();
  for (const [action, { icon }] of Object.entries(actions))
    byIcon.set(icon, [...(byIcon.get(icon) ?? []), action]);
  const sheet = document.createElement("div");
  sheet.id = "legibility-symbols";
  sheet.style.cssText =
    "display:grid;grid-template-columns:repeat(8,64px);gap:28px 20px;padding:32px 40px;background:var(--paper);";
  for (const shown of byIcon.values()) {
    const press = offerAction("symbol", "", undefined, { action: shown[0] });
    press.type = "button";
    press.dataset.legibility = JSON.stringify(shown);
    const cell = document.createElement("div");
    cell.style.cssText = "display:flex;justify-content:center;";
    cell.append(press);
    sheet.append(cell);
  }
  document.querySelector("main").append(sheet);
  sheet.scrollIntoView({ block: "center" });
}"""

# Number every visible control inside the region; return each one's actions, or, for
# a control the view didn't mark, its accessible name.
NUMBER = """(region) => {
  const controls = [...region.querySelectorAll("button, [role=button], a[href], summary")]
    .filter((c) => c.checkVisibility() && c.getBoundingClientRect().width > 0);
  const layer = document.createElement("div");
  layer.style.cssText = "position:absolute;inset:0;pointer-events:none;z-index:2147483647;";
  document.body.append(layer);
  return controls.map((control, i) => {
    const box = control.getBoundingClientRect();
    const tag = document.createElement("span");
    tag.textContent = String(i + 1);
    tag.style.cssText = `position:absolute;left:${box.left + scrollX - 14}px;top:${box.top + scrollY - 14}px;font:600 11px/1 system-ui;color:#c0007a;`;
    layer.append(tag);
    return control.dataset.legibility
      ? { n: i + 1, actions: JSON.parse(control.dataset.legibility) }
      : { n: i + 1, name: control.getAttribute("aria-label") || control.textContent.trim() };
  });
}"""


def capture(name, region, context):
    controls = [
        {
            "n": control["n"],
            "stands_for": [
                {"name": ACTIONS[a]["name"], "does": DOES[a]}
                for a in control["actions"]
            ]
            if "actions" in control
            else [{"name": control["name"], "does": control["name"]}],
        }
        for control in region.evaluate(NUMBER)
    ]
    region.screenshot(path=str(OUT / f"{name}.png"))
    return {
        "description": name,
        "vars": {"image": str((OUT / f"{name}.png").resolve()), "context": context},
        "metadata": {"controls": controls, "vocabulary": VOCABULARY},
    }


def run(page):
    OUT.mkdir(parents=True, exist_ok=True)
    browser = page.context.browser.new_context(
        storage_state=page.context.storage_state(),
        device_scale_factor=2,
        viewport={"width": 1000, "height": 900},
    )
    view = browser.new_page()
    view.goto(page.url)
    view.locator("main").wait_for()
    view.evaluate(SYMBOL_SHEET, ACTIONS)
    tests = [
        capture(
            "symbols",
            view.locator("#legibility-symbols"),
            "These are the icon buttons a web app uses across its interface, each "
            "shown alone. The app shows documents and reports that an AI agent "
            "writes, and the user reviews, comments on and edits them.",
        )
    ]
    browser.close()
    (OUT / "tests.json").write_text(json.dumps(tests, indent=2) + "\n")
    return [test["description"] for test in tests]
