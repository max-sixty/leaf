"""Check each WAI-ARIA composite a Leaf page shows against its APG keyboard pattern.

A `leaf-dev probe --journey`: it imports UI SDK's experimental `checkPattern` from
jsDelivr, so it needs the network. It checks every visible element whose explicit
role names an APG pattern, open shadow roots included, plus menus and dialogs that
are open, and returns what `checkPattern` reported for each. Its known false reports
are in notes/dependency-candidates.md, "UI SDK".
"""

CHECK = r"""
async () => {
  const { checkPattern } = await import(
    "https://cdn.jsdelivr.net/npm/@ui-sdk/core@0.1.0-beta.1/testing/+esm"
  );
  const patterns = {
    tablist: "tabs", tree: "tree", radiogroup: "radio-group", toolbar: "toolbar",
    listbox: "listbox", menubar: "menubar", slider: "slider", switch: "switch",
    checkbox: "checkbox", combobox: "combobox", menu: "menu", dialog: "dialog",
  };
  const all = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      all.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  const controlled = new Set(
    all.filter((el) => el.getAttribute("role") === "combobox")
      .map((el) => el.getAttribute("aria-controls")),
  );
  // The nearest custom element around `el`, crossing shadow roots.
  const widget = (el) => {
    for (let at = el; at; at = at.parentElement ?? at.getRootNode().host) {
      if (at !== el && at.localName.includes("-")) return at.localName;
    }
  };
  const results = [];
  for (const el of all) {
    const role = el.getAttribute("role");
    const pattern = patterns[role];
    if (!pattern || !el.checkVisibility()) continue;
    // A combobox's check covers the listbox it controls.
    if (role === "listbox" && controlled.has(el.id)) continue;
    if ((role === "menu" || role === "dialog") && !el.matches(":popover-open, [open]"))
      continue;
    let problems = null;
    try {
      await checkPattern(el, pattern);
    } catch (error) {
      problems = String(error.message ?? error);
    }
    const label = el.getAttribute("aria-label");
    results.push({
      element: `${el.localName}[role=${role}]` + (el.id ? `#${el.id}` : "") +
        (label ? ` "${label}"` : ""),
      widget: widget(el) ?? null,
      pattern,
      problems,
    });
  }
  return results;
}
"""


def run(page):
    return page.evaluate(CHECK)
