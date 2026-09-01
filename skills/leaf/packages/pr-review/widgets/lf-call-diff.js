/* CallDiff's plain output is a unified call-tree diff: a two-character status gutter,
 * tree glyphs and call text, then an optional source location separated by two spaces.
 * The host owns analysis and the captured text; this widget only parses that display
 * grammar and projects each row as commentable evidence. */
import {
  announce,
  offer,
  projectData,
  scrollBehavior,
  watchData,
} from "/runtime/widget-api.js";

const LOCATION = /^(.*?)(?: {2,})(\S+:\d+(?:-\d+)?)$/;

const setText = (element, value) => {
  if (element.textContent !== value) element.textContent = value;
};

function make(tag, className) {
  const element = document.createElement(tag);
  element.className = className;
  return element;
}

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

function reconcileChildren(parent, wanted) {
  const retained = new Set(wanted);
  for (const child of [...parent.childNodes])
    if (child.nodeType !== Node.ELEMENT_NODE) child.remove();
  let cursor = parent.firstElementChild;
  for (const child of wanted) {
    if (child !== cursor) parent.insertBefore(child, cursor);
    cursor = child.nextElementSibling;
  }
  for (const child of [...parent.children]) if (!retained.has(child)) child.remove();
}

function buildLine(tag = "div") {
  const line = make(tag, "lf-call-line");
  const marker = make("span", "lf-call-marker");
  const body = make("span", "lf-call-body");
  const location = make("a", "lf-call-location");
  marker.setAttribute("aria-hidden", "true");
  line.append(marker, body, location);
  return line;
}

function updateDisclosureControl(owner) {
  const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
  const button = owner.querySelector(":scope > .lf-call-tools .lf-call-toggle");
  if (!button) return;
  const expand = groups.some((group) => !group.open);
  setText(button, `${expand ? "Expand" : "Collapse"} all`);
  button.setAttribute(
    "aria-label",
    `${expand ? "Expand" : "Collapse"} all ${groups.length} call-tree ${groups.length === 1 ? "root" : "roots"}`,
  );
}

function buildToolbar(owner) {
  const toolbar = make("div", "lf-call-tools");
  const summary = make("p", "lf-call-summary");
  // `offer`, not a bare button: the disclosure control is chrome this widget injected
  // and a handler is all it ever was, so the markers it writes are what tells the
  // exported copy to take the press away rather than draw a hand over a dead one.
  const button = offer("button", "lf-call-toggle");
  button.addEventListener("click", () => {
    const groups = [...owner.querySelectorAll(":scope > .lf-call-group")];
    const open = groups.some((group) => !group.open);
    for (const group of groups) group.open = open;
    updateDisclosureControl(owner);
    announce(`${open ? "Expanded" : "Collapsed"} all call-tree roots`);
  });
  toolbar.append(summary, button);
  return toolbar;
}

function buildGroup(owner, key) {
  const group = make("details", "lf-call-group");
  const summary = buildLine("summary");
  const body = make("div", "lf-call-group-body");
  group.dataset.callGroup = key;
  summary.classList.add("lf-call-group-summary");
  group.append(summary, body);
  group.addEventListener("toggle", () => updateDisclosureControl(owner));
  return { body, group, summary };
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

function matchingLine(diff, record) {
  const matched = record.location.match(/^(.*):(\d+)(?:-\d+)?$/);
  if (!matched || !diff?.shadowRoot) return null;
  const [, path, rawLine] = matched;
  const line = Number(rawLine);
  const sides = record.status === "removed" ? ["old", "both"] : ["new", "both", "old"];
  const candidates = [];
  for (const element of diff.shadowRoot.querySelectorAll("[data-lf-datum]")) {
    let coordinate;
    try {
      coordinate = JSON.parse(element.dataset.lfDatum);
    } catch {
      continue;
    }
    if (!Array.isArray(coordinate) || coordinate[0] !== path) continue;
    const [, side, first, second] = coordinate;
    const atLine = side === "both" ? first === line || second === line : first === line;
    if (atLine) candidates.push({ element, rank: sides.indexOf(side) });
  }
  candidates.sort((left, right) => left.rank - right.rank);
  return candidates.find(({ rank }) => rank >= 0)?.element ?? null;
}

async function travelToLine(owner, record) {
  const diff = document.getElementById(owner.getAttribute("diff"));
  if (!diff) return false;
  let target = matchingLine(diff, record);
  if (!target) {
    const matched = record.location.match(/^(.*):(\d+)(?:-\d+)?$/);
    if (matched) {
      const [, path, rawLine] = matched;
      const side = record.status === "removed" ? "old" : "new";
      await diff.lfRevealDatum?.(JSON.stringify([path, side, Number(rawLine)]));
      target = matchingLine(diff, record);
    }
  }
  if (!target) return false;
  const disclosure = target.closest("details");
  if (disclosure) disclosure.open = true;
  disclosure?.querySelector("summary")?.focus({ preventScroll: true });
  target.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
  const url = new URL(window.location.href);
  url.hash = diff.id;
  history.pushState(null, "", url);
  announce(`Opened ${record.location} in the exact patch`);
  return true;
}

function renderLine(record, prior, owner) {
  const line = prior ?? buildLine();
  const marker = line.querySelector(".lf-call-marker");
  const body = line.querySelector(".lf-call-body");
  const location = line.querySelector(".lf-call-location");
  line.dataset.status = record.status;
  line.toggleAttribute("data-root", record.root);
  line.toggleAttribute("data-meta", record.meta);
  setText(
    marker,
    record.status === "added" ? "+" : record.status === "removed" ? "−" : " ",
  );
  setText(body, record.body);
  setText(location, record.location);
  location.hidden = !record.location;
  // Two rows have the element and no journey to offer, and an `href` on either is a way
  // in that leads nowhere. The header names no location at all, and its hidden anchor
  // answered the scroll sweep's question — "is there a way into this box?" — for a box
  // whose words run off the side, so a copy shipped it with no keyboard route at all.
  // A group's own row is the disclosure, and a link inside a <summary> is two gestures
  // on one box: the press folds and the anchor travels. The calls beneath it keep the
  // link, which is where following the root's own location leads anyway.
  if (record.location && !line.matches("summary")) {
    location.href = `#${owner.getAttribute("diff")}`;
    location.onclick = async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (await travelToLine(owner, record)) return;
      const url = new URL(window.location.href);
      url.hash = owner.getAttribute("diff");
      history.pushState(null, "", url);
      document.getElementById(owner.getAttribute("diff"))?.scrollIntoView({
        behavior: scrollBehavior(),
        block: "start",
      });
      announce(`${record.location} is not present in the exact patch`);
    };
  } else {
    location.removeAttribute("href");
    location.onclick = null;
  }
  return line;
}

function renderMessage(prior, message, className = "lf-call-missing") {
  const line = prior ?? make("div", "lf-call-line lf-call-missing");
  line.className = `lf-call-line ${className}`;
  setText(line, message);
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
      if (this.stopWatching) return;
      this.stopWatching = watchData(this, "document", (snapshot) =>
        this.show(snapshot),
      );
    }

    disconnectedCallback() {
      this.stopWatching?.();
      this.stopWatching = null;
    }

    show(snapshot) {
      let records;
      try {
        records = snapshot?.value ? parse(snapshot.value) : [];
      } catch (error) {
        this.replaceChildren();
        projectData(
          this,
          [{ key: "invalid", invalid: error.message }],
          ({ key }) => key,
          (record, prior) =>
            renderMessage(
              prior,
              `Call-diff data is invalid: ${record.invalid}.`,
              "lf-call-invalid",
            ),
          { labelOf },
        );
        return;
      }
      if (!records.length) {
        this.replaceChildren();
        projectData(
          this,
          [{ key: "unavailable", missing: true }],
          ({ key }) => key,
          (record, prior) => renderMessage(prior, "Waiting for call-diff data."),
          { labelOf },
        );
        return;
      }

      const toolbar =
        this.querySelector(":scope > .lf-call-tools") ?? buildToolbar(this);
      const summary = toolbar.querySelector(".lf-call-summary");
      const dataRows = records.filter((record) => !record.meta);
      const roots = records.filter((record) => record.root);
      const added = dataRows.filter((record) => record.status === "added").length;
      const removed = dataRows.filter((record) => record.status === "removed").length;
      setText(
        summary,
        `${roots.length} changed ${roots.length === 1 ? "root" : "roots"} · ${added} added · ${removed} removed · ${dataRows.length} items`,
      );

      const oldGroups = new Map(
        [...this.querySelectorAll(":scope > .lf-call-group")].map((group) => [
          group.dataset.callGroup,
          {
            body: group.querySelector(":scope > .lf-call-group-body"),
            group,
            summary: group.querySelector(":scope > .lf-call-group-summary"),
          },
        ]),
      );
      const groups = new Map();
      for (const root of roots)
        groups.set(
          root.groupKey,
          oldGroups.get(root.groupKey) ?? buildGroup(this, root.groupKey),
        );

      const headerTarget =
        this.querySelector(":scope > .lf-call-line[data-meta]") ?? buildLine();
      reconcileChildren(this, [
        toolbar,
        headerTarget,
        ...[...groups.values()].map(({ group }) => group),
      ]);

      const nodes = projectData(
        this,
        records,
        ({ key }) => key,
        (record, prior) => {
          if (record.meta) return renderLine(record, prior ?? headerTarget, this);
          const group = groups.get(record.groupKey);
          const rendered = renderLine(
            record,
            prior ?? (record.root ? group.summary : null),
            this,
          );
          if (!record.root && !rendered.isConnected) group.body.append(rendered);
          return rendered;
        },
        { nested: true, labelOf },
      );
      const nodesByKey = new Map(
        records.map((record, index) => [record.key, nodes[index]]),
      );
      const header = nodesByKey.get(records[0].key);
      for (const [key, parts] of groups) {
        const groupRecords = records.filter((record) => record.groupKey === key);
        const root = groupRecords.find((record) => record.root);
        const rootNode = nodesByKey.get(root.key);
        let count = rootNode.querySelector(".lf-call-group-count");
        if (!count) {
          count = make("span", "lf-call-group-count");
          count.dataset.lfUi = "";
          rootNode.append(count);
        }
        setText(count, groupLabel(groupRecords));
        reconcileChildren(
          parts.body,
          groupRecords
            .filter((record) => !record.root)
            .map((record) => nodesByKey.get(record.key)),
        );
        reconcileChildren(parts.group, [rootNode, parts.body]);
      }
      reconcileChildren(this, [
        toolbar,
        header,
        ...[...groups.values()].map(({ group }) => group),
      ]);
      updateDisclosureControl(this);
    }
  },
);
