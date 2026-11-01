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

/** @typedef {{body: string, key: string, location: {text: string, path: string, line: number} | null, root: boolean, meta: boolean, status: "unchanged" | "added" | "removed", originPath: (string | number)[]}} CallRecord */
/** @param {import("../../../browser/types/contract.js").DataCalldiff} document */
function recordsOf(document) {
  /** @type {CallRecord} */
  const meta = {
    body:
      (!document.trees.length && document.message) ||
      `calldiff diff ${document.from} → ${document.to}`,
    key: "meta",
    location: null,
    root: false,
    meta: true,
    status: "unchanged",
    originPath: [],
  };
  const occurrences = new Map();
  const groups = document.trees.map(({ entry, tree }, treeIndex) => {
    /** @param {import("../../../browser/types/contract.js").DataCalldiffNode} node
     * @param {string} indent @param {boolean} last @param {boolean} root
     * @param {(string | number)[]} originPath @returns {[CallRecord, ...CallRecord[]]} */
    const walk = (node, indent, last, root, originPath) => {
      const status = node.status === "same" ? "unchanged" : node.status;
      const location =
        node.file && node.line != null
          ? {
              text: `${node.file}:${node.line}${node.endLine != null && node.endLine !== node.line ? `-${node.endLine}` : ""}`,
              path: node.file,
              line: node.line,
            }
          : null;
      // Occurrences distinguish repeated native keys without tying a row to its parent.
      const keyParts = [entry, node.key, status, node.file, node.line];
      const occurrenceKey = JSON.stringify(keyParts);
      const occurrence = occurrences.get(occurrenceKey) ?? 0;
      occurrences.set(occurrenceKey, occurrence + 1);
      const key = JSON.stringify([...keyParts, occurrence]);
      /** @type {CallRecord} */
      const record = {
        body: `${indent}${root ? "" : last ? "└─ " : "├─ "}${node.label}`,
        originPath,
        key,
        location,
        root,
        meta: false,
        status,
      };
      const rail = node.kind === "branch" || last || root ? "   " : "│  ";
      const childIndent = root ? "" : `${indent}${rail}`;
      return [
        record,
        ...node.children.flatMap((child, index) =>
          walk(child, childIndent, index === node.children.length - 1, false, [
            ...originPath,
            "children",
            index,
          ]),
        ),
      ];
    };
    const [root, ...children] = walk(tree, "", true, true, [
      "trees",
      treeIndex,
      "tree",
    ]);
    return { root, children };
  });
  return { meta, groups };
}

/** @param {"div" | "summary"} [tag] */
function buildLine(tag = "div") {
  return el(tag, "lf-call-line");
}

/** @param {HTMLElement} owner */
function updateDisclosureControl(owner) {
  const groups = [...owner.querySelectorAll("details")].filter(
    (group) =>
      group.parentElement === owner && group.classList.contains("lf-call-group"),
  );
  const button = owner.querySelector(":scope > .lf-call-tools .lf-call-toggle");
  if (!button) return;
  const expand = groups.some((group) => !group.open);
  const label = `${expand ? "Expand" : "Collapse"} all ${groups.length} call-tree ${groups.length === 1 ? "root" : "roots"}`;
  nameAction(button, expand ? "expand-all" : "collapse-all", { label });
}

/** @param {HTMLElement} owner */
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
    const groups = [...owner.querySelectorAll("details")].filter(
      (group) =>
        group.parentElement === owner && group.classList.contains("lf-call-group"),
    );
    const open = groups.some((group) => !group.open);
    for (const group of groups) if (group.open !== open) group.open = open;
    updateDisclosureControl(owner);
    announce(`${open ? "Expanded" : "Collapsed"} all call-tree roots`);
  });
  toolbar.append(summary, button);
  return { element: toolbar, summary };
}

/** @param {HTMLElement} owner @param {string} key @param {boolean} open */
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

/** @param {CallRecord[]} records */
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

/** @param {HTMLElement} owner @param {CallRecord} record */
async function travelToLine(owner, record) {
  const location = record.location;
  if (!location) return false;
  const key = diffLocationKey(
    location.path,
    record.status === "removed" ? "old" : "new",
    location.line,
  );
  return navigateToDatum(owner, "diff", key, {
    success: `Opened ${location.text} in the exact patch`,
    missing: `${location.text} is not present in the exact patch`,
  });
}

/** @param {CallRecord} record @param {HTMLElement} owner */
function locationLink(record, owner) {
  return record.location
    ? html`<a
        class="lf-call-location"
        href=${`#${owner.getAttribute("diff")}`}
        @click=${async (/** @type {MouseEvent} */ event) => {
          if (event.defaultPrevented || !plainPress(event)) return;
          event.preventDefault();
          event.stopPropagation();
          await travelToLine(owner, record);
        }}
        >${record.location.text}</a
      >`
    : html`<a class="lf-call-location" hidden></a>`;
}

/** @param {CallRecord} record @param {HTMLElement} line @param {HTMLElement} owner @param {string | null} [count] */
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
/** @param {HTMLElement} node @param {string} key @param {string} label @param {(string | number)[] | null} path */
function mark(node, key, label, path) {
  keeps(node, "data-lf-datum", key);
  keeps(node, "data-lf-datum-label", label);
  keeps(node, "data-lf-origin-path", path ? JSON.stringify(path) : null);
}

/** @param {CallRecord} record */
function labelOf(record) {
  if (record.meta) return record.body;
  const location = record.location ? ` at ${record.location.text}` : "";
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
      /** @type {import("../../../browser/types/contract.js").DataCalldiff | null} */
      this.value = null;
    }

    /** @type {Map<string, ReturnType<typeof buildGroup>>} */
    groups = new Map();
    /** @type {Map<string, HTMLElement>} */
    rows = new Map();
    toolbar = buildToolbar(this);
    messageNode = el("div", "lf-call-line");

    render() {
      this.show(this.value);
      return nothing;
    }

    /** @param {import("../../../browser/types/contract.js").DataCalldiff | null} value */
    message(value) {
      this.groups = new Map();
      this.rows = new Map();
      const node = this.messageNode;
      keeps(node, "class", "lf-call-line lf-call-missing");
      keepsText(node, "Waiting for call-diff data.");
      setChildren(this, [node]);
      mark(node, "unavailable", "Call-diff data unavailable", null);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
    }

    /** @param {import("../../../browser/types/contract.js").DataCalldiff | null} value */
    show(value) {
      this.classList.toggle("lf-rendered", value !== null);
      if (!value) {
        this.message(value);
        return;
      }
      const records = recordsOf(value);
      const dataRows = records.groups.flatMap(({ root, children }) => [
        root,
        ...children,
      ]);
      const added = dataRows.filter((record) => record.status === "added").length;
      const removed = dataRows.filter((record) => record.status === "removed").length;
      keepsText(
        this.toolbar.summary,
        `${records.groups.length} changed ${records.groups.length === 1 ? "root" : "roots"} · ${added} added · ${removed} removed · ${dataRows.length} items`,
      );
      const oldRows = this.rows;
      /** @type {Map<string, HTMLElement>} */
      const rows = new Map();
      /** @param {CallRecord} record @param {() => HTMLElement} fallback @param {string | null} [count] */
      const draw = (record, fallback, count = null) => {
        const node = oldRows.get(record.key) ?? fallback();
        renderLine(record, node, this, count);
        rows.set(record.key, node);
        mark(node, record.key, labelOf(record), record.originPath);
        return node;
      };
      const meta = draw(records.meta, () => buildLine());
      const placements = records.groups.map(({ root, children }, index) => {
        const owned =
          this.groups.get(root.key) ?? buildGroup(this, root.key, index === 0);
        const summary = draw(
          root,
          () => owned.summary,
          groupLabel([root, ...children]),
        );
        keeps(owned.location, "data-status", root.status);
        render(locationLink(root, this), owned.location);
        return {
          key: root.key,
          ...owned,
          summary,
          children: children.map((record) => draw(record, () => buildLine())),
        };
      });
      const currentLocation = focused(this.getRootNode());
      for (const { group, body, children } of placements)
        if (
          children.some(
            (node) => node.parentNode !== body && node.contains(currentLocation),
          )
        )
          if (!group.open) group.open = true;
      /** @type {[HTMLElement, HTMLElement[]][]} */
      const lists = [
        [
          this,
          [
            this.toolbar.element,
            meta,
            ...placements.flatMap(({ group, location }) => [location, group]),
          ],
        ],
      ];
      for (const { group, body, summary, children } of placements)
        lists.push([group, [summary, body]], [body, children]);
      setChildLists(lists);
      this.groups = new Map(placements.map((group) => [group.key, group]));
      this.rows = rows;
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      updateDisclosureControl(this);
    }
  },
);
