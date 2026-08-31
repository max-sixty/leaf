/* CallDiff's plain output is a unified call-tree diff: a two-character status gutter,
 * tree glyphs and call text, then an optional source location separated by two spaces.
 * The host owns analysis and the captured text; this widget only parses that display
 * grammar and projects each row as commentable evidence. */
import {
  announce,
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
    if (root) entry = body.trim();
    const identity = `${entry}\u0000${status}\u0000${body}\u0000${location}`;
    const occurrence = occurrences.get(identity) ?? 0;
    occurrences.set(identity, occurrence + 1);
    return {
      body,
      entry,
      key: JSON.stringify([entry, status, body, location, occurrence]),
      location,
      meta,
      root,
      status,
    };
  });
}

function buildLine() {
  const line = make("div", "lf-call-line");
  const marker = make("span", "lf-call-marker");
  const body = make("span", "lf-call-body");
  const location = make("a", "lf-call-location");
  marker.setAttribute("aria-hidden", "true");
  line.append(marker, body, location);
  return line;
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

function travelToLine(owner, record) {
  const diff = document.getElementById(owner.getAttribute("diff"));
  const target = matchingLine(diff, record);
  if (!diff || !target) return false;
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
  location.href = `#${owner.getAttribute("diff")}`;
  location.onclick = (event) => {
    if (!travelToLine(owner, record)) return;
    event.preventDefault();
  };
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
      let projected;
      try {
        const records = snapshot?.value ? parse(snapshot.value) : [];
        projected = records.length ? records : [{ key: "unavailable", missing: true }];
      } catch (error) {
        projected = [{ key: "invalid", invalid: error.message }];
      }
      projectData(
        this,
        projected,
        ({ key }) => key,
        (record, prior) =>
          record.missing
            ? renderMessage(prior, "Waiting for call-diff data.")
            : record.invalid
              ? renderMessage(
                  prior,
                  `Call-diff data is invalid: ${record.invalid}.`,
                  "lf-call-invalid",
                )
              : renderLine(record, prior, this),
        { labelOf },
      );
    }
  },
);
