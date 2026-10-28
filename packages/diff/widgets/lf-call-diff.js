/* CallDiff owns the call hierarchy, status and source coordinates in its native JSON.
 * This widget draws trees[].tree as commentable evidence, retaining unchanged nodes
 * and deriving only the visible tree rails. Its optional locations are used directly,
 * including paths with whitespace; terminal output is never read back as data.
 * Each root keeps its disclosure separate from its source link.
 * Ordinary activation travels to the exact line; modified activation keeps the
 * native link's separate-tab, separate-window and context-menu routes. CallDiff
 * locations name the after tree for added and unchanged rows, and the before tree
 * for removed rows (calldiff's diffNode/pickLoc contract). Source navigation keeps
 * that side even when the same number names a different line on the other side.
 * Comments stay bound to the capture's source revision: callee keys do not identify
 * persistent invocation instances. Rows are keyed by call and placed with setChildren rather than a Lit repeat per root:
 * a capture can move a call under another root, and a row leaving one repeat list
 * for another is recreated, which would drop the focus of a user on it. */
import {
  announce,
  html,
  nameAction,
  render,
  el,
  generated,
  generatedElement,
  keeps,
  keepsText,
  LeafElement,
  navigateToDatum,
  nothing,
  offerAction,
  setChildLists,
  setChildren,
  plainPress,
  focused,
} from "/runtime/widget-api.js";

import { diffLocationKey } from "./diff-coordinates.js";

function recordsOf(document) {
  const records = [
    {
      body: `calldiff diff ${document.from} → ${document.to}`,
      key: "meta",
      groupKey: "meta",
      entry: "",
      location: "",
      path: undefined,
      line: null,
      root: false,
      meta: true,
      status: "unchanged",
      originPath: [],
    },
  ];
  const occurrences = new Map();
  for (const [treeIndex, { entry, tree }] of document.trees.entries()) {
    let groupKey;
    const walk = (node, indent, last, root, originPath) => {
      const status = node.status === "same" ? "unchanged" : node.status;
      const location =
        node.file && node.line != null
          ? `${node.file}:${node.line}${node.endLine != null && node.endLine !== node.line ? `-${node.endLine}` : ""}`
          : "";
      // Native keys identify calls independently of their displayed labels and rails.
      // Occurrences distinguish repeated calls without tying them to their parent.
      const keyParts = [entry, node.key, status, node.file, node.line];
      const occurrenceKey = JSON.stringify(keyParts);
      const occurrence = occurrences.get(occurrenceKey) ?? 0;
      occurrences.set(occurrenceKey, occurrence + 1);
      const key = JSON.stringify([...keyParts, occurrence]);
      if (root) groupKey = key;
      records.push({
        body: `${indent}${root ? "" : last ? "└─ " : "├─ "}${node.label}`,
        entry,
        originPath,
        groupKey,
        key,
        location,
        path: node.file,
        line: node.line,
        root,
        meta: false,
        status,
      });
      const rail = node.kind === "branch" || last || root ? "   " : "│  ";
      const childIndent = root ? "" : `${indent}${rail}`;
      node.children.forEach((child, index) =>
        walk(child, childIndent, index === node.children.length - 1, false, [
          ...originPath,
          "children",
          index,
        ]),
      );
    };
    walk(tree, "", true, true, ["trees", treeIndex, "tree"]);
  }
  if (!document.trees.length && document.message) records[0].body = document.message;
  return records;
}

function buildLine(tag = "div") {
  return el(tag, "lf-call-line");
}

function updateDisclosureControl(owner) {
  const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
  const button = owner.querySelector(":scope > .lf-call-tools .lf-call-toggle");
  if (!button) return;
  const expand = groups.some((group) => !group.open);
  const label = `${expand ? "Expand" : "Collapse"} all ${groups.length} call-tree ${groups.length === 1 ? "root" : "roots"}`;
  nameAction(button, expand ? "expand-all" : "collapse-all", { label });
}

function buildToolbar(owner) {
  const toolbar = el("div", "lf-call-tools");
  // The counts this widget writes are an account of the tree, not words the page holds,
  // so `data-lf-gen` takes them out of the version diff and makes each its own passage
  // cell — the marker `lf-diff` puts on its own injected stat. It does not stop a drag
  // quoting them: that is `.lf-ui`, which `lf-diff` adds beside it on its line numbers.
  const summary = el("p", "lf-call-summary");
  generatedElement(summary, { says: false });
  // An offer, not a bare button: the disclosure control is chrome this widget injected,
  // and the offer gives it the press markers the theme and the keyboard read.
  const button = offerAction("symbol", "lf-call-toggle", undefined, {
    action: "expand-all",
  });
  button.addEventListener("click", () => {
    const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
    const open = groups.some((group) => !group.open);
    for (const group of groups) if (group.open !== open) group.open = open;
    updateDisclosureControl(owner);
    announce(`${open ? "Expanded" : "Collapsed"} all call-tree roots`);
  });
  toolbar.append(summary, button);
  return toolbar;
}

function buildGroup(owner, key, open) {
  const group = el("details", "lf-call-group");
  group.open = open;
  // Source navigation and disclosure are separate controls: a link nested in summary
  // disappears from some accessibility readings. Keep the summary as the tight root
  // datum, and its source control beside it rather than around the whole call tree.
  const location = el("div", "lf-call-root-location");
  const summary = buildLine("summary");
  const body = el("div", "lf-call-group-body lf-text-scroller scroll");
  group.dataset.callGroup = key;
  summary.classList.add("lf-call-group-summary", "lf-disclosure-marker");
  group.append(summary, body);
  group.addEventListener("toggle", () => updateDisclosureControl(owner));
  return { body, group, location, summary };
}

function groupLabel(records) {
  const added = records.filter((record) => record.status === "added").length;
  const removed = records.filter((record) => record.status === "removed").length;
  const context = records.length - added - removed;
  return [
    added ? `${added} added` : "",
    removed ? `${removed} removed` : "",
    context ? `${context} context` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function lineKey(record) {
  if (!record.location) return null;
  const side = record.status === "removed" ? "old" : "new";
  return diffLocationKey(record.path, side, record.line);
}

async function travelToLine(owner, record) {
  const key = lineKey(record);
  if (!key) return false;
  return navigateToDatum(owner, "diff", key, {
    success: `Opened ${record.location} in the exact patch`,
    missing: `${record.location} is not present in the exact patch`,
  });
}

function locationLink(record, owner) {
  return record.location
    ? html`<a
        class="lf-call-location"
        href=${`#${owner.getAttribute("diff")}`}
        @click=${async (event) => {
          if (event.defaultPrevented || !plainPress(event)) return;
          event.preventDefault();
          event.stopPropagation();
          await travelToLine(owner, record);
        }}
        >${record.location}</a
      >`
    : html`<a class="lf-call-location" hidden></a>`;
}

function renderLine(record, line, owner, count = null) {
  keeps(line, "data-status", record.status);
  line.toggleAttribute("data-root", record.root);
  line.toggleAttribute("data-meta", record.meta);
  render(
    html`<span class="lf-call-marker" aria-hidden="true"
        >${
          record.status === "added" ? "+" : record.status === "removed" ? "−" : " "
        }</span
      ><span class="lf-call-body">${record.body}</span>${
        record.root ? "" : locationLink(record, owner)
      }${
        count === null
          ? ""
          : html`<span class="lf-call-group-count" ${generated({ says: false })}
              >${count}</span
            >`
      }`,
    line,
  );
  return line;
}

// A drawn row's marks, which make it a datum on a Leaf page (`module-state.md`,
// "Marking drawn data").
function mark(node, key, label, path) {
  keeps(node, "data-lf-datum", key);
  keeps(node, "data-lf-datum-label", label);
  keeps(node, "data-lf-origin-path", path ? JSON.stringify(path) : null);
}

function labelOf(record) {
  if (record.meta) return record.body;
  const location = record.location ? ` at ${record.location}` : "";
  return `${record.status} call-tree item ${record.body.trim()}${location}`;
}

customElements.define(
  "lf-call-diff",
  class extends LeafElement {
    // The CallDiff document, set by whoever hosts the widget: Leaf from the bound
    // source (the registry's `x-data.document.property`), or null while it has none.
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      this.value = null;
    }

    render() {
      this.show(this.value);
      return nothing;
    }

    message(value) {
      this.groups = new Map();
      this.rows = new Map();
      /** @type {HTMLElement} */
      this.messageNode = this.messageNode ?? el("div", "lf-call-line");
      const node = this.messageNode;
      keeps(node, "class", "lf-call-line lf-call-missing");
      keepsText(node, "Waiting for call-diff data.");
      setChildren(this, [node]);
      mark(node, "unavailable", "Call-diff data unavailable", null);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
    }

    show(value) {
      const records = value ? recordsOf(value) : [];
      // Drawn from its data, which lifts the height the page reserved (x-height), and
      // held at that height again while the data is absent.
      this.classList.toggle("lf-rendered", records.length > 0);
      if (!records.length) {
        this.message(value);
        return;
      }

      const toolbar =
        this.querySelector(":scope > .lf-call-tools") ?? buildToolbar(this);
      const summary = toolbar.querySelector(".lf-call-summary");
      const dataRows = records.filter((record) => !record.meta);
      const roots = records.filter((record) => record.root);
      const groupRows = new Map(roots.map((root) => [root.groupKey, []]));
      for (const record of dataRows) groupRows.get(record.groupKey).push(record);
      const added = dataRows.filter((record) => record.status === "added").length;
      const removed = dataRows.filter((record) => record.status === "removed").length;
      keepsText(
        summary,
        `${roots.length} changed ${roots.length === 1 ? "root" : "roots"} · ${added} added · ${removed} removed · ${dataRows.length} items`,
      );

      const oldGroups = this.groups ?? new Map();
      const oldRows = this.rows ?? new Map();
      const groups = new Map(
        roots.map((root, index) => [
          root.groupKey,
          oldGroups.get(root.groupKey) ?? buildGroup(this, root.groupKey, index === 0),
        ]),
      );
      const rows = new Map();
      for (const record of records) {
        const group = groups.get(record.groupKey);
        const node =
          oldRows.get(record.key) ?? (record.root ? group.summary : buildLine());
        const count = record.root ? groupLabel(groupRows.get(record.groupKey)) : null;
        renderLine(record, node, this, count);
        if (record.root) {
          keeps(group.location, "data-status", record.status);
          render(locationLink(record, this), group.location);
        }
        rows.set(record.key, node);
        mark(node, record.key, labelOf(record), record.originPath);
      }
      const placements = [...groups].map(([key, { group, body }]) => {
        const [root, ...children] = groupRows.get(key);
        return {
          group,
          body,
          summary: rows.get(root.key),
          children: children.map((record) => rows.get(record.key)),
        };
      });
      // Placed at once, a row changing groups, even to a newly arriving root, moves
      // straight across and keeps its controls live; its group opens to show it.
      const currentLocation = focused(this.getRootNode());
      for (const { group, body, children } of placements)
        if (
          children.some(
            (node) => node.parentNode !== body && node.contains(currentLocation),
          )
        )
          if (!group.open) group.open = true;
      setChildLists([
        [
          this,
          [
            toolbar,
            rows.get(records[0].key),
            ...[...groups.values()].flatMap(({ group, location }) => [location, group]),
          ],
        ],
        ...placements.flatMap(({ group, body, summary, children }) => [
          [group, [summary, body]],
          [body, children],
        ]),
      ]);
      this.groups = groups;
      this.rows = rows;
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      updateDisclosureControl(this);
    }
  },
);
