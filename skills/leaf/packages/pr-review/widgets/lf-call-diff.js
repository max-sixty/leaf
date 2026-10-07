/* CallDiff's plain output is a unified call-tree diff: a two-character status gutter,
 * tree glyphs and call text, then an optional source location separated by two spaces.
 * The host owns analysis and the captured text; this widget only parses that display
 * grammar and projects each row as commentable evidence. */
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
  const summary = buildLine("summary");
  const body = el("div", "lf-call-group-body lf-text-scroller");
  const rootLink = el("a", "lf-call-location lf-call-root-link");
  rootLink.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await travelToLine(owner, rootLink.record);
  });
  group.dataset.callGroup = key;
  summary.classList.add("lf-call-group-summary");
  group.append(summary, body);
  group.addEventListener("toggle", () => updateDisclosureControl(owner));
  return { body, group, summary, rootLink };
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
  return JSON.stringify([path, side, Number(rawLine)]);
}

async function travelToLine(owner, record) {
  const key = lineKey(record);
  if (!key) return false;
  return navigateToDatum(owner, "diff", key, {
    success: `Opened ${record.location} in the exact patch`,
    missing: `${record.location} is not present in the exact patch`,
  });
}

function renderLine(record, line, owner, count = null) {
  keeps(line, "data-status", record.status);
  line.toggleAttribute("data-root", record.root);
  line.toggleAttribute("data-meta", record.meta);
  render(
    html`<span class="lf-call-marker" aria-hidden="true"
        >${record.status === "added" ? "+" : record.status === "removed" ? "−" : " "}</span
      ><span class="lf-call-body">${record.body}</span>${
        record.location && record.root
          ? html`<span class="lf-call-location">${record.location}</span>`
          : record.location
            ? html`<a
              class="lf-call-location"
              href=${`#${owner.getAttribute("diff")}`}
              @click=${async (event) => {
                event.preventDefault();
                event.stopPropagation();
                await travelToLine(owner, record);
              }}
              >${record.location}</a
            >`
            : html`<a class="lf-call-location" hidden></a>`
      }${count === null ? "" : html`<span class="lf-call-group-count" data-lf-gen="1">${count}</span>`}`,
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
        const count = record.root
          ? groupLabel(records.filter((row) => row.groupKey === record.groupKey))
          : null;
        renderLine(record, node, this, count);
        rows.set(record.key, node);
        return { node, key: record.key, label: labelOf(record) };
      });
      for (const [key, { group, body, rootLink }] of groups) {
        const groupRows = records.filter((record) => record.groupKey === key);
        const root = groupRows.find((record) => record.root);
        rootLink.record = root;
        keeps(rootLink, "href", `#${this.getAttribute("diff")}`);
        keepsText(rootLink, `Open ${root.location} in the exact patch`);
        setChildren(
          body,
          [
            rootLink,
            ...groupRows
              .filter((record) => !record.root)
              .map((record) => rows.get(record.key)),
          ],
        );
        setChildren(group, [
          rows.get(root.key),
          body,
        ]);
      }
      setChildren(this, [
        toolbar,
        rows.get(records[0].key),
        ...[...groups.values()].map(({ group }) => group),
      ]);
      this.groups = groups;
      this.rows = rows;
      projectData(this, datums, { snapshot });
      updateDisclosureControl(this);
    }
  },
);
