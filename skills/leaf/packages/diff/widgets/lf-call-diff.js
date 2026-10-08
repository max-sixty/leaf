/* CallDiff's plain output is a unified call-tree diff: a two-character status gutter,
 * tree glyphs and call text, then an optional source location separated by two spaces.
 * The host owns analysis and the captured text; this widget only parses that display
 * grammar and projects each row as commentable evidence. Each root keeps its native
 * disclosure separate from its source link, which remains available when closed.
 * Ordinary activation travels to the exact line; modified activation keeps the
 * native link's separate-tab, separate-window and context-menu routes. CallDiff
 * locations name the after tree for added and unchanged rows, and the before tree
 * for removed rows (calldiff's diffNode/pickLoc contract). Source navigation keeps
 * that side even when the same number names a different line on the other side. */
import {
  announce,
  html,
  render,
  el,
  keeps,
  keepsText,
  navigateToDatum,
  offer,
  projectData,
  setChildren,
  watchData,
  once,
} from "/runtime/widget-api.js";

import { diffLocationKey } from "./diff-coordinates.js";

const LOCATION = /^(.*?)(?: {2,})(\S+:\d+(?:-\d+)?)$/;

function parse(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (!lines[0]?.startsWith("calldiff diff "))
    throw new Error("the first line must be a CallDiff diff header");
  let entry = "Call diff";
  let groupKey = "meta";
  const occurrences = new Map();
  return lines.map((line, index) => {
    const meta = index === 0;
    if (!meta && !/^(?:  |\+ |\- )/.test(line))
      throw new Error(`line ${index + 1} has no CallDiff status gutter`);
    const status = line.startsWith("+ ")
      ? "added"
      : line.startsWith("- ")
        ? "removed"
        : "unchanged";
    const displayed =
      status === "unchanged" && line.startsWith("  ")
        ? line.slice(2)
        : status === "unchanged"
          ? line
          : line.slice(2);
    const matched = displayed.match(LOCATION);
    if (!meta && !matched)
      throw new Error(
        `line ${index + 1} has no source location; capture --locs output`,
      );
    const body = matched ? matched[1] : displayed;
    const location = matched?.[2] ?? "";
    const root = !meta && !/[├└]/u.test(body);
    if (!meta && !root && groupKey === "meta")
      throw new Error(`line ${index + 1} appears before a changed root`);
    if (root) entry = body.trim();
    const identity = `${entry}\u0000${status}\u0000${body}\u0000${location}`;
    const occurrence = occurrences.get(identity) ?? 0;
    occurrences.set(identity, occurrence + 1);
    const key = JSON.stringify([entry, status, body, location, occurrence]);
    if (root) groupKey = key;
    return {
      body,
      entry,
      groupKey,
      key,
      location,
      meta,
      root,
      status,
    };
  });
}

function buildLine(tag = "div") {
  return el(tag, "lf-call-line");
}

function updateDisclosureControl(owner) {
  const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
  const button = owner.querySelector(":scope > .lf-call-tools .lf-call-toggle");
  if (!button) return;
  const expand = groups.some((group) => !group.open);
  keepsText(button, `${expand ? "Expand" : "Collapse"} all`);
  keeps(
    button,
    "aria-label",
    `${expand ? "Expand" : "Collapse"} all ${groups.length} call-tree ${groups.length === 1 ? "root" : "roots"}`,
  );
}

function buildToolbar(owner) {
  const toolbar = el("div", "lf-call-tools");
  // The counts this widget writes are an account of the tree, not words the page holds,
  // so `data-lf-gen` takes them out of the version diff and makes each its own passage
  // cell — the marker `lf-diff` puts on its own injected stat. It does not stop a drag
  // quoting them: that is `.lf-ui`, which `lf-diff` adds beside it on its line numbers.
  const summary = el("p", "lf-call-summary");
  summary.dataset.lfGen = "1";
  // `offer`, not a bare button: the disclosure control is chrome this widget injected,
  // and `offer` gives it the press markers the theme and the keyboard read.
  const button = offer("button", "lf-btn lf-call-toggle");
  button.addEventListener("click", () => {
    const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
    const open = groups.some((group) => !group.open);
    for (const group of groups) group.toggleAttribute("open", open);
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
  const body = el("div", "lf-call-group-body lf-text-scroller");
  group.dataset.callGroup = key;
  summary.classList.add("lf-call-group-summary");
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
  const matched = record.location.match(/^(.*):(\d+)(?:-\d+)?$/);
  if (!matched) return null;
  const [, path, rawLine] = matched;
  const side = record.status === "removed" ? "old" : "new";
  return diffLocationKey(path, side, Number(rawLine));
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
          if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
          )
            return;
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
          : html`<span class="lf-call-group-count" data-lf-gen="1">${count}</span>`
      }`,
    line,
  );
  return line;
}

function labelOf(record) {
  if (record.missing) return "Call-diff data unavailable";
  if (record.invalid) return "Invalid call-diff data";
  if (record.meta) return record.body;
  const location = record.location ? ` at ${record.location}` : "";
  return `${record.status} call-tree item ${record.body.trim()}${location}`;
}

customElements.define(
  "lf-call-diff",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      watchData(this, "document", (snapshot) => this.show(snapshot));
    }

    message(key, message, snapshot) {
      this.groups = new Map();
      this.rows = new Map();
      const node = (this.messageNode ??= el("div", "lf-call-line"));
      keeps(
        node,
        "class",
        `lf-call-line lf-call-${key === "invalid" ? "invalid" : "missing"}`,
      );
      keepsText(node, message);
      setChildren(this, [node]);
      projectData(
        this,
        [
          {
            node,
            key,
            label: labelOf(key === "invalid" ? { invalid: true } : { missing: true }),
          },
        ],
        { snapshot },
      );
    }

    show(snapshot) {
      let records;
      try {
        records = snapshot?.value ? parse(snapshot.value) : [];
      } catch (error) {
        this.classList.toggle("lf-rendered", true);
        this.message(
          "invalid",
          `Call-diff data is invalid: ${error.message}.`,
          snapshot,
        );
        return;
      }
      // Drawn from its data, which lifts the height the page reserved (x-height), and
      // held at that height again while the data is absent.
      this.classList.toggle("lf-rendered", records.length > 0);
      if (!records.length) {
        this.message("unavailable", "Waiting for call-diff data.", snapshot);
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
      const datums = records.map((record) => {
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
        return { node, key: record.key, label: labelOf(record) };
      });
      const placements = [...groups].map(([key, { group, body }]) => {
        const [root, ...children] = groupRows.get(key);
        return {
          group,
          body,
          summary: rows.get(root.key),
          children: children.map((record) => rows.get(record.key)),
        };
      });
      // Connect destinations and transfer surviving rows before any old body or
      // group is drained. Native moves can then keep their controls live even
      // when a capture puts the same call under a newly arriving root.
      const arrivals = placements
        .map(({ group }) => group)
        .filter((group) => group.parentNode !== this);
      if (arrivals.length) setChildren(this, [...this.childNodes, ...arrivals]);
      const focused = this.getRootNode().activeElement;
      for (const { group, body, children } of placements) {
        const transfers = children.filter(
          (node) => node.parentNode !== body && node.isConnected,
        );
        if (transfers.some((node) => node.contains(focused))) group.open = true;
        if (transfers.length) setChildren(body, [...body.childNodes, ...transfers]);
      }
      for (const { group, body, summary, children } of placements) {
        setChildren(body, children);
        setChildren(group, [summary, body]);
      }
      setChildren(this, [
        toolbar,
        rows.get(records[0].key),
        ...[...groups.values()].flatMap(({ group, location }) => [location, group]),
      ]);
      this.groups = groups;
      this.rows = rows;
      projectData(this, datums, { snapshot });
      updateDisclosureControl(this);
    }
  },
);
