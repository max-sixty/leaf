/* lf-diff uses Pierre's static renderer rather than hydrating Pierre's custom
 * element. Its ordinary DOM can live in Leaf's declared shadow root, so the
 * rendered lines support selection anchors. A source revision updates evidence
 * under stable file owners: reader controls, disclosure and code scrollports stay
 * connected. A changed file kind replaces only its inner presentation and hands
 * source focus to that same file; supplied thread/composer outlets keep core focus
 * ownership across replacement. Unchanged parsed files keep their rendering; changed files
 * reconcile unchanged lines by their datum coordinate, retaining selection and line threads.
 * Manifest evidence commits together after open files load, and a closed file shows
 * none of the previous revision while it loads current evidence. */
import {
  DISCLOSE,
  announce,
  beginWalk,
  dataBody,
  failSoft,
  focusDestination,
  focused,
  holdFocus,
  inChrome,
  inBaseLayer,
  commands,
  keeps,
  keepsText,
  langForPath,
  layoutChanged,
  loadDeferred,
  listWalkPosition,
  offer,
  paintKeys,
  projectData,
  consumeThreads,
  relabel,
  retainUserIntent,
  scrollBehavior,
  scrollIntoReadingBand,
  setChildren,
  shadowStage,
  notice,
  widgetController,
  watchData,
} from "/runtime/widget-api.js";
import "../vendor/webawesome.esm.js";
// Pierre's renderer is by far the largest thing a Leaf page can pull, and only a diff
// that is actually rendering has any use for it — an authored <lf-diff> bound to data
// that has not arrived yet does not. So it is imported on first use rather than at
// module load: the page pays for the renderer when it draws a diff, and a version whose
// diff has been taken back out stops paying on the next load. The promise is kept, so
// every later file, every other diff on the page, and every re-render share one import.
let renderer = null;
const pierre = () => (renderer ??= import("/vendor/pierre-diffs.esm.js"));

const OPTIONS = Object.freeze({
  diffStyle: "unified",
  diffIndicators: "classic",
  disableLineNumbers: false,
  disableFileHeader: true,
  hunkSeparators: "line-info-basic",
  lineDiffType: "word-alt",
  overflow: "scroll",
  theme: { light: "github-light", dark: "github-dark" },
});

// Pierre's two fixed Shiki themes are reduced to the same small role vocabulary
// lf-code uses. The diff geometry and inline spans remain Pierre's; Leaf's theme
// keeps syntax ink consistent across the two code surfaces.
const TOKEN_ROLES = new Map([
  ["#6A737D/#6A737D", "cm"],
  ["#D73A49/#F97583", "kw"],
  ["#032F62/#9ECBFF", "st"],
  ["#032F62/#DBEDFF", "st"],
  ["#005CC5/#79B8FF", "nu"],
  ["#6F42C1/#B392F0", "fn"],
  ["#22863A/#85E89D", "ty"],
  ["#E36209/#FFAB70", "ty"],
  ["#B31D28/#FDAEB7", "kw"],
]);

function adoptSyntaxRoles(root) {
  for (const token of root.querySelectorAll("[style*='--diffs-token-light']")) {
    const light = token.style
      .getPropertyValue("--diffs-token-light")
      .trim()
      .toUpperCase();
    const dark = token.style
      .getPropertyValue("--diffs-token-dark")
      .trim()
      .toUpperCase();
    const role = TOKEN_ROLES.get(`${light}/${dark}`);
    token.style.removeProperty("--diffs-token-light");
    token.style.removeProperty("--diffs-token-dark");
    if (!token.style.length) token.removeAttribute("style");
    if (role) token.dataset.lfSyn = role;
  }
}

const changeCounts = (file) =>
  Number.isInteger(file.additions) && Number.isInteger(file.deletions)
    ? { adds: file.additions, dels: file.deletions }
    : file.hunks.reduce(
        (counts, hunk) => ({
          adds: counts.adds + hunk.additionLines,
          dels: counts.dels + hunk.deletionLines,
        }),
        { adds: 0, dels: 0 },
      );

// Each record carries the index of the hunk it came out of. A hunk is the unit a
// reviewer actually moves in — one `@@` header is one place the author changed
// something — and it is knowable only here, where the parse is still grouped; the
// rendered rows are a flat run with the separator chrome between them, so recovering
// the grouping from the DOM afterwards would be reading a rendering for a fact the
// parse already had. It rides on the same record the anchor coordinate is read off,
// and `lineKey` names only the four fields that make a comment's coordinate, so a row
// knowing which hunk it is in changes no anchor.
function sourceLines(file) {
  const lines = [];
  for (const [hunk, chunk] of file.hunks.entries()) {
    let oldLine = chunk.deletionStart;
    let newLine = chunk.additionStart;
    for (const part of chunk.hunkContent) {
      if (part.type === "context") {
        for (let index = 0; index < part.lines; index++) {
          lines.push({ path: file.name, hunk, side: "both", oldLine, newLine });
          oldLine++;
          newLine++;
        }
        continue;
      }
      if (part.type !== "change")
        throw new Error(`unsupported ${part.type} line in ${file.name}`);
      for (let index = 0; index < part.deletions; index++)
        lines.push({ path: file.name, hunk, side: "old", oldLine: oldLine++ });
      for (let index = 0; index < part.additions; index++)
        lines.push({ path: file.name, hunk, side: "new", newLine: newLine++ });
    }
  }
  return lines;
}

// The first rendered row of each hunk: the places `]` and `[` land. Read off the
// records rather than counted in the DOM, so an unloaded file simply has none.
const hunkHeads = (entry) =>
  (entry.lines ?? []).filter(
    (line, index) => index === 0 || line.hunk !== entry.lines[index - 1].hunk,
  );

const lineKey = ({ path, side, oldLine, newLine }) =>
  JSON.stringify(
    side === "both"
      ? [path, side, oldLine, newLine]
      : [path, side, side === "old" ? oldLine : newLine],
  );

const lineLabel = ({ path, side, oldLine, newLine }) => {
  const file = path || "(unnamed file)";
  if (side === "old") return `${file} · old line ${oldLine}`;
  if (side === "new") return `${file} · new line ${newLine}`;
  return `${file} · old line ${oldLine} · new line ${newLine}`;
};

const fileKey = ({ path }) => JSON.stringify([path, "file"]);
const fileLabel = ({ path }) => `${path || "(unnamed file)"} · file`;
const fileNode = (entry) => entry.node;
const fileDatum = (entry, origin = null) => ({
  file: true,
  path: entry.record.path,
  node: fileNode(entry),
  ...(origin ? { origin } : {}),
});
const datumKey = (record) => (record.file ? fileKey(record) : lineKey(record));
const datumLabel = (record) => (record.file ? fileLabel(record) : lineLabel(record));

function renderedLines(file, rendered) {
  const records = sourceLines(file);
  const nodes = [...rendered.querySelectorAll("[data-content] [data-line]")];
  if (nodes.length !== records.length)
    throw new Error(
      `Pierre returned ${nodes.length} source lines for ${file.name}; expected ${records.length}`,
    );
  return records.map((record, index) => {
    const node = nodes[index];
    const type =
      record.side === "both"
        ? "context"
        : record.side === "old"
          ? "change-deletion"
          : "change-addition";
    const shown = record.side === "old" ? record.oldLine : record.newLine;
    const alternate = record.side === "both" ? record.oldLine : null;
    if (
      node.dataset.lineType !== type ||
      node.dataset.line !== String(shown) ||
      (alternate !== null && node.dataset.altLine !== String(alternate))
    )
      throw new Error(`Pierre returned an unexpected source line for ${file.name}`);
    return { ...record, node };
  });
}

// A path is its folders and then the file's own name, each a span, so a row too narrow
// for the whole path gives way from the folders and keeps the name (shadow.css). Where
// a path wraps, as in a rename's row, it breaks after its slashes before anywhere else:
// with no break in it but the one the stylesheet forces, a narrow row cut names mid-word
// ("skills/wor|ktrunk", "preview.|rs"). The text is unchanged; a <wbr> adds only the
// opportunity, and the title holds the whole path wherever the row cuts it.
function pathNode(className, path) {
  const node = Object.assign(document.createElement("span"), {
    className,
    title: path,
  });
  const parts = path.split("/");
  const base = parts.pop();
  if (parts.length) {
    const dir = Object.assign(document.createElement("span"), {
      className: "lf-diff-dir",
    });
    for (const part of parts) dir.append(`${part}/`, document.createElement("wbr"));
    node.append(dir);
  }
  node.append(
    Object.assign(document.createElement("span"), {
      className: "lf-diff-base",
      textContent: base,
    }),
  );
  return node;
}

function summaryNode(file, open) {
  const details = document.createElement("details");
  details.className = "lf-diff-fold";
  details.open = open;
  const summary = document.createElement("summary");
  summary.className = "lf-diff-head";
  const path = file.name || "(unnamed file)";
  const { adds, dels } = changeCounts(file);
  const stat = Object.assign(document.createElement("span"), {
    className: "lf-diff-stat",
    textContent: `+${adds} −${dels}`,
  });
  stat.dataset.lfGen = "1";
  summary.append(pathNode("lf-diff-path", path), stat);
  commands(summary, "On a diff", [
    {
      id: "diff.toggle",
      keys: () => DISCLOSE(summary),
      does: () => `${details.open ? "Hide" : "Show"} that file's diff`,
      line: () => `${details.open ? "hide" : "show"} this file`,
    },
  ]);
  details.append(summary);
  return details;
}

// A file's row and its review press. The press cannot go inside the <summary>: a
// disclosure is itself a control, and a control nested in one is announced as a single
// thing — the serious `nested-interactive` finding the corpus's axe sweep reports, once
// per file. They are siblings in this wrapper instead, the press first, and shadow.css
// draws it back onto the summary line. First because the line pins: the summary sticks
// under the banner while its rows go past, and the press sticks with it only as a box
// in the flow ahead of the disclosure, since a box placed against the file's top would
// stay there and drift off the header it belongs to.
function fileRow(row) {
  const file = document.createElement("div");
  file.className = "lf-diff-file";
  const actions = document.createElement("div");
  actions.className = "lf-diff-file-actions lf-ui";
  actions.dataset.lfGen = "1";
  file.append(actions, row);
  return file;
}

function reviewButton(entry, changed) {
  const button = offer("button", "lf-btn lf-diff-review");
  button.addEventListener("click", () => changed(entry, !entry.reviewed));
  return button;
}

function commentButton(label, opened, className) {
  const button = offer("button", `lf-btn lf-diff-comment ${className}`, "+");
  button.type = "button";
  button.setAttribute("aria-label", `Comment on ${label}`);
  button.title = `Comment on ${label}`;
  button.addEventListener("click", opened);
  return button;
}

// A shared body lets the checkbox style its own subtree. WebKit does not repaint
// a shadow-root sibling selected through the toolbar's :has() after a native tap.
function diffBody(nodes) {
  const body = document.createElement("div");
  body.className = "lf-diff-body";
  body.append(...nodes);
  return body;
}

// File and listing controls are browser-owned inspection state. Updating the evidence
// keeps their owners connected; only changed rendered content is replaced. A line's
// existing datum coordinate supplies its focus counterpart when that content changes.
function rowSpan(node) {
  const value = node.style.gridRow || getComputedStyle(node).gridRow;
  const matches = [...value.matchAll(/span\s+(\d+)/g)];
  const count = Number(matches.at(-1)?.[1]);
  if (!Number.isInteger(count))
    throw new Error("Pierre returned a diff grid without a finite row span");
  return count;
}

// A file's datum owns its controls even when its evidence changes kind. Only the
// inner presentation changes; a focus that no longer has a line or disclosure lands
// on that same file, while surviving controls keep their own native focus.
// Supplied outlets belong to core thread/composition presentation. It carries focus
// when one leaves this file; the file's source fallback must not replace that standing.
function holdFileFocus(entry, outlets) {
  for (const { outlet } of outlets?.values() ?? []) if (holdFocus(outlet)) return null;
  return holdFocus(entry.node);
}

function replaceFileRendering(entry, rendered, outlets) {
  const restore = holdFileFocus(entry, outlets);
  setChildren(entry.node, [entry.node.firstElementChild, rendered.node]);
  entry.details = rendered.node.matches("details") ? rendered.node : null;
  entry.lines = rendered.lines;
  entry.renderKey = null;
  return () => restore?.(entry.details?.firstElementChild, entry.node);
}

function replaceFileContent(entry, rendered, pairs, outlets) {
  const held = focused();
  const line = entry.lines.find(
    ({ node, comment }) => node.contains(held) || comment === held,
  );
  const restore = holdFileFocus(entry, outlets);
  const details = entry.details;
  const pre = details.querySelector("pre");
  const nextPre = rendered.node.querySelector("pre");
  const prior = new Map(entry.lines.map((record) => [lineKey(record), record]));
  const retained = new Map();
  const gutters = new Map();
  for (const next of rendered.lines) {
    const previous = prior.get(lineKey(next));
    if (!previous || previous.node.innerHTML !== next.node.innerHTML) continue;
    retained.set(next.node, previous.node);
    const nextGutter = nextPre.querySelector(
      `[data-gutter] [data-line-index="${next.node.dataset.lineIndex}"]`,
    );
    const gutter = pre.querySelector(
      `[data-gutter] [data-line-index="${previous.node.dataset.lineIndex}"]`,
    );
    gutters.set(nextGutter, gutter);
    keeps(previous.node, "data-line-index", next.node.dataset.lineIndex);
    keeps(gutter, "data-line-index", next.node.dataset.lineIndex);
    next.node = previous.node;
    next.comment = previous.comment;
  }
  if (pre && nextPre) {
    for (const { name } of [...pre.attributes])
      if (!nextPre.hasAttribute(name)) pre.removeAttribute(name);
    for (const { name, value } of nextPre.attributes) keeps(pre, name, value);
    setChildren(
      pre,
      [...nextPre.childNodes].map((next) => {
        if (!next.matches?.("code[data-code]")) return next;
        const code = pre.querySelector("code[data-code]");
        if (!code) return next;
        code.style.gridRow = next.style.gridRow;
        setChildren(
          code,
          [...next.childNodes].map((column) => {
            const kind = column.hasAttribute?.("data-content")
              ? "content"
              : column.hasAttribute?.("data-gutter")
                ? "gutter"
                : null;
            if (!kind) return column;
            const current = code.querySelector(`[data-${kind}]`);
            if (!current) return column;
            const content = code.querySelector("[data-content]");
            const pair = pairs?.get(content);
            if (pair) {
              pair[`${kind}Rows`] = rowSpan(column);
              pair[`${kind}GridRow`] = column.style.gridRow;
            }
            current.style.gridRow = column.style.gridRow;
            const kept = kind === "content" ? retained : gutters;
            const children = [...column.childNodes].flatMap((child) => {
              const previous = kept.get(child);
              if (!previous) return [child];
              const outlets = [];
              for (
                let sibling = previous.nextElementSibling;
                sibling?.matches(".lf-diff-thread-outlet, .lf-diff-thread-gutter");
                sibling = sibling.nextElementSibling
              )
                outlets.push(sibling);
              return [previous, ...outlets];
            });
            setChildren(current, children);
            return current;
          }),
        );
        return code;
      }),
    );
  }
  keepsText(
    details.querySelector(".lf-diff-stat"),
    rendered.node.querySelector(".lf-diff-stat").textContent,
  );
  setChildren(details, [
    details.firstElementChild,
    ...[...rendered.node.children]
      .slice(1)
      .map((node) => (node === nextPre && pre ? pre : node)),
  ]);
  entry.lines = rendered.lines;
  const counterpart =
    line && entry.lines.find((next) => lineKey(next) === lineKey(line));
  return () =>
    restore?.(
      counterpart && (held === line.comment ? counterpart.comment : counterpart.node),
      details.firstElementChild,
    );
}

// The checkbox is the complete wrap state.
function wrapSwitch() {
  const label = offer("label", "lf-diff-wrap-label");
  const box = offer("input", "lf-diff-wrap", undefined, "checkbox");
  box.name = "soft-wrap";
  // The words beside the control are its accessible name (WCAG Label in Name); the
  // label element supplies them, so nothing here restates them as an aria-label.
  label.append(box, "Soft wrap");
  // A toggle moves no focus, so nothing else would repaint the word this press changes.
  box.addEventListener("change", paintKeys);
  return { node: label, box };
}

function diffTools(host, reviewing) {
  const tools = offer("div", "lf-diff-tools");
  const label = offer("div", "lf-diff-search-label");
  const search = offer("wa-input", "lf-diff-search lf-label-hidden");
  search.type = "search";
  search.size = "s";
  search.label = "Filter diff files";
  search.name = "diff-search";
  search.placeholder = "Filter files";
  search.value = "";
  search.setAttribute("aria-label", "Filter diff files");
  search.addEventListener("input", () => host.filterFiles(search.value));
  label.append(search);
  const progress = document.createElement("span");
  progress.className = "lf-diff-progress";
  progress.dataset.lfGen = "1";
  const next = reviewing
    ? offer("button", "lf-btn lf-diff-next", "Next unreviewed")
    : null;
  next?.addEventListener("click", () => host.present(host.nextUnreviewed()));
  const wrap = wrapSwitch();
  tools.append(label, progress, wrap.node);
  if (next) tools.append(next);
  return { node: tools, search, progress, next, wrap: wrap.box };
}

function renameNode(file) {
  const row = document.createElement("div");
  row.className = "lf-diff-rename";
  row.dataset.lfGen = "1";
  row.append(
    pathNode("lf-diff-path lf-diff-before", file.prevName),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-arrow",
      textContent: " → ",
    }),
    pathNode("lf-diff-path lf-diff-after", file.name),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-stat",
      textContent: "renamed",
    }),
  );
  return row;
}

function headerPath(side, path) {
  return path.startsWith('"') && path.endsWith('"')
    ? `"${side}/${path.slice(1)}`
    : `${side}/${path}`;
}

function gitPath(path) {
  if (!path.startsWith('"')) return path;
  if (!path.endsWith('"')) return null;
  const inner = path.slice(1, -1);
  if (!/^(?:[^\\]|\\(?:[abtnvfr"\\]|[0-3][0-7]{2}|[0-7]{1,2}(?![0-7])))*$/.test(inner))
    return null;
  const escapes = { a: 7, b: 8, t: 9, n: 10, v: 11, f: 12, r: 13 };
  const bytes = [];
  const encoder = new globalThis.TextEncoder();
  for (let i = 0; i < inner.length; i++) {
    if (inner[i] !== "\\") {
      const point = inner.codePointAt(i);
      bytes.push(...encoder.encode(String.fromCodePoint(point)));
      if (point > 0xffff) i++;
      continue;
    }
    const match = /^(?:[0-3][0-7]{2}|[0-7]{1,2})/.exec(inner.slice(i + 1));
    if (match) {
      bytes.push(parseInt(match[0], 8));
      i += match[0].length;
    } else {
      const escaped = inner[++i];
      bytes.push(escapes[escaped] ?? escaped.charCodeAt(0));
    }
  }
  if (bytes.includes(0)) return null;
  try {
    return new globalThis.TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
      new Uint8Array(bytes),
    );
  } catch {
    return null;
  }
}

function pathOnlyRenames(source) {
  return source
    .split(/(?=^diff --git )/m)
    .filter((section) => section.startsWith("diff --git "))
    .flatMap((section) => {
      const lines = section.replace(/\n+$/, "").split("\n");
      if (lines.length !== 4 || lines[1] !== "similarity index 100%") return [];
      const prevName = /^rename from (.+)$/.exec(lines[2])?.[1];
      const name = /^rename to (.+)$/.exec(lines[3])?.[1];
      if (
        !prevName ||
        !name ||
        prevName === '""' ||
        name === '""' ||
        lines[0] !== `diff --git ${headerPath("a", prevName)} ${headerPath("b", name)}`
      )
        return [];
      const decodedPrevName = gitPath(prevName);
      const decodedName = gitPath(name);
      return decodedPrevName !== null && decodedName !== null
        ? [{ prevName: decodedPrevName, name: decodedName }]
        : [];
    });
}

async function renderFile(file, sharedStyles, open) {
  const { preloadDiffHTML } = await pierre();
  file.lang = langForPath(file.name) ?? "text";
  const template = document.createElement("template");
  template.innerHTML = await preloadDiffHTML({ fileDiff: file, options: OPTIONS });
  const rendered = template.content;

  // The static rendering has no Pierre interaction manager, so its unused icon sprite
  // goes. Line numbers and separator wording are useful chrome, but not source a comment
  // can quote; the source lines and file path remain in the reading.
  rendered.querySelector("svg[data-icon-sprite]")?.remove();
  for (const number of rendered.querySelectorAll("[data-line-number-content]")) {
    number.classList.add("lf-ui");
    number.dataset.lfGen = "1";
    number.setAttribute("aria-hidden", "true");
  }
  for (const separator of rendered.querySelectorAll("[data-separator]"))
    separator.classList.add("lf-ui");
  for (const style of [...rendered.children].filter(
    (child) => child.localName === "style",
  )) {
    // Vendor sublayers stay inside widget defaults, below Leaf's shared shadow rules.
    style.textContent = inBaseLayer(style.textContent);
    const kind = style.hasAttribute("data-core-css") ? "core" : "theme";
    if (!sharedStyles.has(kind)) sharedStyles.set(kind, style);
    else style.remove();
  }
  adoptSyntaxRoles(rendered);

  const pre = rendered.querySelector("pre");
  if (!pre) throw new Error(`Pierre returned no diff for ${file.name || "a file"}`);
  const viewport = pre.querySelector("code[data-code]") ?? pre;
  viewport.setAttribute("role", "region");
  viewport.setAttribute("aria-label", file.name || "diff");

  const details = summaryNode(file, open);
  const lines = renderedLines(file, rendered);
  details.append(rendered);
  return { node: details, lines };
}

async function parsedFiles(source) {
  if (/^copy (?:from|to) /m.test(source))
    throw new Error(
      "unsupported copy diff (copy entries belong in prose; omit " +
        "copy metadata and use textual @@ hunks for an edited destination)",
    );
  const { parsePatchFiles } = await pierre();
  const files = parsePatchFiles(source, undefined, true).flatMap(
    (patch) => patch.files,
  );
  if (!files.length) throw new Error("empty diff");
  const pureRenames = files.filter((file) => file.type === "rename-pure");
  const sourceRenames = pathOnlyRenames(source);
  if (
    sourceRenames.length !== pureRenames.length ||
    sourceRenames.some(
      (rename, index) =>
        rename.prevName !== pureRenames[index].prevName ||
        rename.name !== pureRenames[index].name,
    )
  )
    throw new Error(
      "unsupported hunkless rename (only an exact path-only block with " +
        "diff --git, similarity index 100%, rename from, and rename to " +
        "lines may omit textual @@ hunks)",
    );
  for (const file of files)
    if (!file.hunks.length && file.type !== "rename-pure")
      throw new Error(
        `unsupported hunkless diff for ${file.name || "a file"} ` +
          "(only path-only renames may omit @@ hunks; binary, mode-only, " +
          "and empty added/deleted entries belong in prose; changed files " +
          "need textual @@ hunks)",
      );
  return files;
}

function deferredError(details, error) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.dataset.lfGen = "1";
  box.textContent = `That file's diff failed to load: ${error?.message || error}`;
  details.replaceChildren(details.firstElementChild, box);
}

customElements.define(
  "lf-diff",
  class extends HTMLElement {
    controller = widgetController(this);

    connectedCallback() {
      this.stopActions ??= this.controller.subscribe(this.paintReviewAvailability);
      if (!this.threadSurface)
        this.threadSurface = consumeThreads(this, (collection, surfaces) => {
          this.beginThreadSurface();
          for (const thread of collection.threads) {
            if (thread.anchor?.section !== this.id || !thread.anchor.datum) continue;
            const target = surfaces.target(thread.key);
            const outlet = target && this.threadOutletFor(target);
            if (outlet) surfaces.place(thread.key, outlet);
          }
          const outlet =
            surfaces.composition && this.threadOutletFor(surfaces.composition);
          if (outlet) surfaces.placeComposition(outlet);
          this.endThreadSurface();
        });
      if (this.stopWatching) return;
      // A page diff's file header pins at `--lf-top`, the top of the page's box that
      // scrolls it; one an agent sent in a reply scrolls inside the panel's own list,
      // which declares no such edge. The theme cannot ask that question from inside a shadow tree, so
      // the module answers it once with the layer's own predicate and paints the answer.
      this.toggleAttribute("data-lf-diff-pinned", !inChrome(this));
      if (!this.reviewKeys) {
        this.reviewKeys = commands(
          this,
          "In a diff review",
          [
            // The walk leads the scope, because the shortcut bar's shortlist is its first
            // two live rows and moving is what a user standing on a diff row does
            // next: the line used to open with "filter files", which is the press for
            // someone who has not started reading yet. The rest of the scope is one `?`
            // away in the compact shortcut bar and complete in the reference dialog.
            //
            // `]` and `[` are the reviewer's own step, and `}` and `{` the same step one
            // unit out. Bracket pairs because that is what an editor and a review tool
            // already spell this walk with, and punctuation spends none of the page's
            // small alphabet: these live in the diff's own scope and answer only while
            // the user is standing in it.
            {
              id: "diff.next-hunk",
              keys: ["]"],
              does: "Go to the next hunk",
              line: "next hunk",
              when: () => this.hasHunks(),
              run: () => this.present(this.stepHunk(false)),
            },
            {
              id: "diff.previous-hunk",
              keys: ["["],
              does: "Go to the previous hunk",
              line: "previous hunk",
              when: () => this.hasHunks(),
              run: () => this.present(this.stepHunk(true)),
            },
            {
              id: "diff.next-file",
              keys: ["}"],
              does: "Go to the next file's header",
              line: "next file",
              when: () => this.shownEntries().length > 1,
              run: () => this.stepFile(false),
            },
            {
              id: "diff.previous-file",
              keys: ["{"],
              does: "Go to the previous file's header",
              line: "previous file",
              when: () => this.shownEntries().length > 1,
              run: () => this.stepFile(true),
            },
            // The mode, not the toggle: `does` and `line` say which way this press will
            // go. The press is the switch's own activation rather than a second route to
            // the same effect, so the box the theme reads stays the one place the state
            // lives. Alt+w rather than a bare letter, matching the row below it: a bare
            // `w` here would shadow the page's own narrowing for as long as a user
            // stood anywhere in a patch.
            {
              id: "diff.wrap",
              keys: ["Alt+w"],
              does: () =>
                this.wrapped() ? "Show long lines unwrapped" : "Wrap long lines",
              line: () => (this.wrapped() ? "stop wrapping" : "wrap long lines"),
              run: () => this.diffTools?.wrap.click(),
            },
            {
              id: "diff.search",
              keys: ["/"],
              does: "Filter the files in this diff",
              line: "filter files",
              run: () => this.diffTools?.search.focus(),
            },
            // The filter is a layer of this widget, so its way out is read off the
            // filter rather than off the press that put it on: a live query goes
            // first, from anywhere in the patch, and then the box itself.
            {
              id: "diff.search.back",
              keys: ["Escape"],
              when: () => {
                const search = this.diffTools?.search;
                if (!search) return false;
                return Boolean(
                  this.matches(":focus-within") &&
                  (search.value || this.diffTools.node.matches(":focus-within")),
                );
              },
              does: () =>
                this.diffTools?.search.value
                  ? "Show every file again"
                  : "Leave the diff filter",
              line: () => (this.diffTools?.search.value ? "show all files" : "back"),
              run: () => {
                const search = this.diffTools?.search;
                if (search?.value) {
                  this.clearFilter();
                  search.focus({ preventScroll: true });
                  return;
                }
                // The box's container is the patch it filters, so that is where it hands
                // the user back: a blur alone would drop them out of this widget's
                // scope with no ring anywhere, and the file walk would stop answering.
                focusDestination(this);
              },
            },
            {
              id: "diff.next-unreviewed",
              keys: ["Alt+ArrowDown"],
              does: "Open the next unreviewed matching file",
              line: "next unreviewed file",
              when: () => this.nextReviewEntry() !== null,
              run: () => this.present(this.nextUnreviewed()),
            },
          ],
          () => Boolean(this.fileEntries?.length),
        );
      }
      const bound = this.hasAttribute("source");
      if (!bound) {
        if (this.classList.contains("lf-rendered")) return;
        // Not bodyText: a diff's trailing whitespace is content — a hunk's last line
        // can be a lone space, the context line for a blank source line — so only the
        // closing newline is the <pre>'s layout.
        if (this.inlineSource === undefined)
          this.inlineSource = dataBody(this).replace(/^\n+/, "").replace(/\n$/, "");
        this.present(this.render(this.inlineSource));
        return;
      }
      this.stopWatching = watchData(this, "document", (snapshot) =>
        this.render(snapshot?.value ?? null, snapshot),
      );
    }

    disconnectedCallback() {
      this.stopActions?.();
      this.stopActions = null;
      this.rendering = (this.rendering ?? 0) + 1;
      this.stopWatching?.();
      this.stopWatching = null;
      this.manifestEntries = null;
      this.manifestSnapshot = null;
      this.threadSurface?.unregister();
      this.threadSurface = null;
      this.threadOutlets = null;
      this.threadPairs = null;
    }

    async render(source, snapshot) {
      const bound = snapshot !== undefined;
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      try {
        if (source === null) {
          this.manifestEntries = null;
          this.fileEntries = null;
          this.sharedStyles = null;
          this.diffTools = null;
          this.manifestBody = null;
          this.replaceChildren();
          shadowStage(this, []);
          projectData(
            this,
            [],
            () => "",
            () => null,
            { nested: true, snapshot },
          );
          this.classList.toggle("lf-rendered", false);
          return;
        }
        if (bound && typeof source === "object") {
          await this.renderManifest(snapshot, rendering);
          return;
        }
        if (typeof source !== "string")
          throw new Error("diff data must be unified patch text or a file manifest");
        // Strict parsing keeps a malformed hunk from becoming incomplete evidence.
        const files = await parsedFiles(source);
        const sharedStyles = this.sharedStyles ?? new Map();
        const prior = new Map(
          (this.fileEntries ?? []).map((entry) => [entry.record.path, entry]),
        );
        const prepared = [];
        const open = !this.hasAttribute("collapsed");
        for (const file of files) {
          const renderKey = JSON.stringify(file);
          const previous = prior.get(file.name);
          const rendered =
            previous?.renderKey === renderKey
              ? null
              : file.type === "rename-pure"
                ? { node: renameNode(file), lines: [] }
                : await renderFile(file, sharedStyles, previous?.details?.open ?? open);
          prepared.push({ file, renderKey, previous, rendered });
        }
        if (rendering !== this.rendering || !this.isConnected) return;
        const restores = [];
        const fresh = [];
        const entries = prepared.map(({ file, renderKey, previous, rendered }) => {
          let entry = previous;
          if (!entry) {
            entry = {
              ...rendered,
              node: fileRow(rendered.node),
              details: rendered.node.matches("details") ? rendered.node : null,
              reviewed: false,
              filtered: false,
            };
            fresh.push(entry);
          } else if (rendered && entry.details && file.type !== "rename-pure") {
            restores.push(
              replaceFileContent(entry, rendered, this.threadPairs, this.threadOutlets),
            );
          } else if (rendered) {
            restores.push(replaceFileRendering(entry, rendered, this.threadOutlets));
          }
          entry.record = {
            path: file.name,
            ...(file.prevName ? { previousPath: file.prevName } : {}),
          };
          entry.renderKey = renderKey;
          entry.loaded = true;
          entry.details?.querySelector("pre")?.toggleAttribute("hidden", false);
          return entry;
        });
        if (bound) for (const { node } of entries) keeps(node, "data-lf-gen", "1");
        const resume = this.controller.defer();
        try {
          this.fileEntries = entries;
          this.manifestEntries = null;
          this.sharedStyles = sharedStyles;
          this.diffTools ??= diffTools(this, this.reviewing());
          for (const entry of fresh)
            this.attachEntryControls(entry, { commentable: bound });
          for (const entry of entries) this.attachDisclosure(entry);
          if (bound) for (const entry of entries) this.attachLineComments(entry);
          this.manifestBody ??= diffBody([]);
          setChildren(this.manifestBody, [
            this.diffTools.node,
            ...entries.map(({ node }) => node),
          ]);
          this.replaceChildren();
          shadowStage(this, [...sharedStyles.values(), this.manifestBody]);
          if (bound)
            projectData(
              this,
              entries.flatMap((entry) => [fileDatum(entry), ...entry.lines]),
              datumKey,
              ({ node }) => node,
              { nested: true, labelOf: datumLabel, snapshot },
            );
          this.classList.toggle("lf-rendered", true);
          this.filterFiles(this.diffTools.search.value);
          for (const restore of restores) restore();
        } finally {
          resume();
        }
      } catch (err) {
        if (rendering !== this.rendering || !this.isConnected) return;
        this.manifestEntries = null;
        this.fileEntries = null;
        this.sharedStyles = null;
        this.diffTools = null;
        this.manifestBody = null;
        this.classList.toggle("lf-rendered", false);
        failSoft(this, err, source);
        if (this.shadowRoot) shadowStage(this, [...this.childNodes]);
        if (bound)
          projectData(
            this,
            [],
            () => "",
            () => null,
            { nested: true, snapshot },
          );
      }
    }

    async renderManifest(snapshot, rendering) {
      const source = snapshot.value;
      if (!Array.isArray(source.files) || !source.files.length)
        throw new Error("empty diff manifest");
      const prior = new Map(
        (this.fileEntries ?? []).map((entry) => [entry.record.path, entry]),
      );
      const sharedStyles = this.sharedStyles ?? new Map();
      const paths = new Set();
      const open = !this.hasAttribute("collapsed");
      const plans = source.files.map((record) => {
        if (
          !record ||
          typeof record !== "object" ||
          record.key !== record.path ||
          typeof record.path !== "string" ||
          !record.path ||
          paths.has(record.path)
        )
          throw new Error("diff manifest needs one unique path-keyed record per file");
        paths.add(record.path);
        if (
          record.kind === "rename" &&
          (typeof record.previousPath !== "string" || !record.previousPath)
        )
          throw new Error(`rename ${record.path} needs its previous path`);
        return { record, previous: prior.get(record.path), prepared: null };
      });
      // Open evidence is prepared without changing the current entries or their native
      // outlets. A disclosure opened while another file loads joins this same commit.
      for (;;) {
        const pending = plans.filter(
          ({ record, previous, prepared }) =>
            record.kind !== "rename" && !prepared && (previous?.details?.open ?? open),
        );
        if (!pending.length) break;
        await Promise.all(
          pending.map(async (plan) => {
            plan.prepared = await this.prepareManifestEntry(
              snapshot,
              plan.record,
              plan.previous?.details ? plan.previous.renderKey : null,
              sharedStyles,
            );
          }),
        );
        if (rendering !== this.rendering || !this.isConnected) return;
      }
      if (rendering !== this.rendering || !this.isConnected) return;
      const fresh = [];
      const restores = [];
      const resume = this.controller.defer();
      try {
        const entries = plans.map(({ record, previous, prepared }) => {
          let entry = previous;
          if (record.kind === "rename") {
            if (
              !previous ||
              previous.details ||
              previous.record.previousPath !== record.previousPath
            ) {
              const rendered = {
                node: renameNode({ prevName: record.previousPath, name: record.path }),
                lines: [],
              };
              if (entry)
                restores.push(
                  replaceFileRendering(entry, rendered, this.threadOutlets),
                );
              else {
                entry = {
                  node: fileRow(rendered.node),
                  lines: [],
                  reviewed: false,
                  filtered: false,
                };
                fresh.push(entry);
              }
            }
            entry.record = record;
            entry.loaded = true;
            return entry;
          }
          if (!entry?.details) {
            const details = summaryNode(
              {
                name: record.path,
                additions: record.additions,
                deletions: record.deletions,
              },
              open,
            );
            if (entry)
              restores.push(
                replaceFileRendering(
                  entry,
                  { node: details, lines: [] },
                  this.threadOutlets,
                ),
              );
            else {
              entry = {
                node: fileRow(details),
                details,
                lines: [],
                reviewed: false,
                filtered: false,
              };
              fresh.push(entry);
            }
          }
          Object.assign(entry, {
            record,
            loaded: false,
            failed: false,
            loading: null,
            prepared,
          });
          const { adds, dels } = changeCounts({
            additions: record.additions,
            deletions: record.deletions,
          });
          keepsText(entry.details.querySelector(".lf-diff-stat"), `+${adds} −${dels}`);
          if (prepared) this.applyManifestEntry(entry);
          else entry.details.querySelector("pre")?.toggleAttribute("hidden", true);
          return entry;
        });
        this.manifestEntries = entries;
        this.manifestSnapshot = snapshot;
        this.fileEntries = entries;
        this.sharedStyles = sharedStyles;
        this.diffTools ??= diffTools(this, this.reviewing());
        for (const entry of fresh)
          this.attachEntryControls(entry, { commentable: true });
        for (const entry of entries) {
          keeps(entry.node, "data-lf-gen", "1");
          this.attachDisclosure(entry);
        }
        this.manifestBody ??= diffBody([]);
        setChildren(this.manifestBody, [
          this.diffTools.node,
          ...entries.map(({ node }) => node),
        ]);
        this.replaceChildren();
        this.stageManifest();
        this.projectManifest();
        this.classList.toggle("lf-rendered", true);
        this.filterFiles(this.diffTools.search.value);
        for (const restore of restores) restore();
      } finally {
        resume();
      }
    }

    async prepareManifestEntry(snapshot, record, renderKey, sharedStyles) {
      try {
        const patch = await loadDeferred(snapshot, record.key);
        if (typeof patch !== "string")
          throw new Error("the deferred patch is not unified patch text");
        const files = await parsedFiles(patch);
        if (files.length !== 1 || files[0].name !== record.path)
          throw new Error(
            `the deferred patch for ${record.path} does not contain that one file`,
          );
        const nextKey = JSON.stringify(files[0]);
        const rendered =
          renderKey === nextKey ? null : await renderFile(files[0], sharedStyles, true);
        return { renderKey: nextKey, rendered };
      } catch (error) {
        return { error };
      }
    }

    stageManifest() {
      if (!this.manifestEntries) return;
      shadowStage(this, [...this.sharedStyles.values(), this.manifestBody]);
    }

    projectManifest() {
      projectData(
        this,
        (this.manifestEntries ?? []).flatMap((entry, index) => [
          fileDatum(entry, {
            ...this.manifestSnapshot.origin,
            path: ["files", index, "path"],
          }),
          ...(entry.loaded ? entry.lines : []).map((line) => ({
            ...line,
            origin: {
              ...this.manifestSnapshot.origin,
              path: ["files", index, "patch"],
            },
          })),
        ]),
        datumKey,
        ({ node }) => node,
        {
          nested: true,
          labelOf: datumLabel,
          snapshot: this.manifestSnapshot,
          originOf: ({ origin }) => origin,
        },
      );
    }

    beginThreadSurface() {
      this.threadOutlets ??= new Map();
      this.threadPairs ??= new Map();
      for (const [key, record] of this.threadOutlets) {
        if (
          !record.outlet.isConnected ||
          (record.gutterRow && !record.gutterRow.isConnected)
        ) {
          this.threadOutlets.delete(key);
          continue;
        }
        record.active = false;
      }
      for (const [content, pair] of this.threadPairs)
        if (!content.isConnected || !pair.gutter.isConnected)
          this.threadPairs.delete(content);
    }

    threadPair(row) {
      this.threadPairs ??= new Map();
      const content = row.parentElement;
      const pre = content?.closest("pre");
      const gutter = pre?.querySelector("[data-gutter]");
      const lineIndex = row.dataset.lineIndex;
      const gutterRow = [...(gutter?.children ?? [])].find(
        (candidate) => candidate.dataset.lineIndex === lineIndex,
      );
      if (!content?.matches("[data-content]") || !gutter || !gutterRow)
        throw new Error("Pierre returned a diff line without its paired gutter row");
      let pair = this.threadPairs.get(content);
      if (!pair) {
        pair = {
          content,
          gutter,
          contentRows: rowSpan(content),
          gutterRows: rowSpan(gutter),
          contentGridRow: content.style.gridRow,
          gutterGridRow: gutter.style.gridRow,
        };
        this.threadPairs.set(content, pair);
      }
      return { gutterRow, pair };
    }

    threadOutletFor({ anchor, placement }) {
      const entry = this.fileEntryForDatum(anchor.datum);
      if (!entry || entry.filtered) return null;
      let coordinate;
      try {
        coordinate = JSON.parse(anchor.datum);
      } catch {
        return null;
      }
      const file = coordinate[1] === "file";
      if (file) {
        if (placement.datumElement !== entry.node) return null;
      } else if (
        !entry.loaded ||
        (entry.details && !entry.details.open) ||
        placement.datumElement !==
          entry.lines.find((line) => lineKey(line) === anchor.datum)?.node
      )
        return null;

      let record = this.threadOutlets.get(anchor.datum);
      if (record && record.row !== placement.datumElement) {
        record.outlet.remove();
        record.gutterRow?.remove();
        this.threadOutlets.delete(anchor.datum);
        record = null;
      }
      if (!record) {
        const row = placement.datumElement;
        const outlet = document.createElement("section");
        outlet.className = `lf-diff-thread-outlet lf-ui${
          file ? " lf-diff-file-thread-outlet" : ""
        }`;
        outlet.dataset.lfGen = "1";
        outlet.dataset.lfThreadDatum = anchor.datum;
        outlet.setAttribute(
          "aria-label",
          `Thread on ${row.dataset.lfDatumLabel || (file ? "file" : "diff line")}`,
        );
        if (file) {
          entry.node.append(outlet);
          record = { active: true, gutterRow: null, outlet, pair: null, row };
        } else {
          const { gutterRow: lineGutter, pair } = this.threadPair(row);
          const gutterRow = document.createElement("div");
          gutterRow.className = "lf-diff-thread-gutter lf-ui";
          gutterRow.dataset.lfGen = "1";
          gutterRow.setAttribute("aria-hidden", "true");
          row.after(outlet);
          lineGutter.after(gutterRow);
          record = { active: true, gutterRow, outlet, pair, row };
        }
        this.threadOutlets.set(anchor.datum, record);
      }
      record.active = true;
      return record.outlet;
    }

    endThreadSurface() {
      for (const [key, record] of this.threadOutlets ?? []) {
        if (record.active) continue;
        record.outlet.remove();
        record.gutterRow?.remove();
        this.threadOutlets.delete(key);
      }
      const counts = new Map();
      for (const record of this.threadOutlets?.values() ?? [])
        if (record.pair) counts.set(record.pair, (counts.get(record.pair) ?? 0) + 1);
      for (const pair of this.threadPairs?.values() ?? []) {
        const count = counts.get(pair) ?? 0;
        const contentRow = count
          ? `span ${pair.contentRows + count}`
          : pair.contentGridRow;
        const gutterRow = count
          ? `span ${pair.gutterRows + count}`
          : pair.gutterGridRow;
        if (pair.content.style.gridRow !== contentRow)
          pair.content.style.gridRow = contentRow;
        if (pair.gutter.style.gridRow !== gutterRow)
          pair.gutter.style.gridRow = gutterRow;
      }
    }

    async loadManifestEntry(entry) {
      if (entry.loaded || entry.prepared) return;
      if (entry.loading) return entry.loading;
      const rendering = this.rendering;
      entry.loading = (async () => {
        const prepared = await this.prepareManifestEntry(
          this.manifestSnapshot,
          entry.record,
          entry.renderKey,
          this.sharedStyles,
        );
        if (rendering !== this.rendering || !this.isConnected) return;
        entry.loading = null;
        entry.prepared = prepared;
        this.applyManifestEntry(entry);
        this.stageManifest();
        this.projectManifest();
      })();
      return entry.loading;
    }

    applyManifestEntry(entry) {
      const { error, renderKey, rendered } = entry.prepared;
      entry.prepared = null;
      if (error) {
        entry.failed = true;
        entry.lines = [];
        entry.renderKey = null;
        deferredError(entry.details, error);
        return;
      }
      const restore =
        rendered &&
        replaceFileContent(entry, rendered, this.threadPairs, this.threadOutlets);
      entry.renderKey = renderKey;
      entry.loaded = true;
      entry.details.querySelector("pre")?.toggleAttribute("hidden", false);
      this.attachLineComments(entry);
      restore?.();
    }

    fileEntryForDatum(key) {
      if (!this.fileEntries) return null;
      let coordinate;
      try {
        coordinate = JSON.parse(key);
      } catch {
        return null;
      }
      if (!Array.isArray(coordinate) || typeof coordinate[0] !== "string") return null;
      return (
        this.fileEntries.find(({ record }) => record.path === coordinate[0]) ?? null
      );
    }

    // Core can place a standing line thread at its file disclosure before that file's
    // patch exists in the DOM. Navigation asks the second method to make the exact line
    // real, then the ordinary datum resolver and anchor painter take over.
    lfDataDatum(key, { outdated = false } = {}) {
      const entry = this.fileEntryForDatum(key);
      if (!entry) return null;
      let coordinate;
      try {
        coordinate = JSON.parse(key);
      } catch {
        return null;
      }
      if (coordinate[1] === "file") return fileNode(entry);
      if (outdated) return entry.node;
      if (!entry.loaded || entry.filtered) return entry.node;
      const exact = entry.lines.find((line) => lineKey(line) === key);
      if (exact) return exact.node;
      const [, side, at] = coordinate;
      if (!Number.isInteger(at) || !["old", "new"].includes(side)) return null;
      const context = entry.lines.find(
        (line) =>
          line.side === "both" && (side === "old" ? line.oldLine : line.newLine) === at,
      );
      if (context) return context.node;
      if (side === "new") {
        const priorContext = entry.lines.find(
          (line) => line.side === "both" && line.oldLine === at,
        );
        if (priorContext) return priorContext.node;
      }
      // A non-removed call-tree item normally names the new side. Falling back to an
      // old coordinate preserves travel for analyzers whose location still names the
      // pre-change call site, without making callers understand diff coordinates.
      if (side === "new")
        return (
          entry.lines.find((line) => line.side === "old" && line.oldLine === at)
            ?.node ?? null
        );
      return null;
    }

    lfRevealDatum(key) {
      const entry = this.fileEntryForDatum(key);
      if (!entry) return null;
      if (entry.filtered) this.clearFilter();
      try {
        if (JSON.parse(key)[1] === "file") return null;
      } catch {
        return null;
      }
      if (!entry.details || entry.loaded || entry.failed) return null;
      entry.details.toggleAttribute("open", true);
      return this.loadManifestEntry(entry);
    }

    attachDisclosure(entry) {
      if (entry.disclosureNode === entry.details) return;
      entry.disclosureNode?.removeEventListener("toggle", entry.disclose);
      entry.disclosureNode = entry.details;
      if (!entry.details) return;
      entry.disclose ??= () => {
        this.threadSurface?.update();
        if (!entry.details.open || !this.manifestEntries?.includes(entry)) return;
        entry.failed = false;
        this.present(this.loadManifestEntry(entry));
      };
      entry.details.addEventListener("toggle", entry.disclose);
    }

    attachReview(entry) {
      if (!this.reviewing()) return;
      entry.review = reviewButton(entry, (target, reviewed) => {
        if (!this.controller.read().actions.review.available) return;
        const sent = this.controller.dispatch({
          kind: "action",
          verb: "review",
          detail: { file: target.record.path, reviewed },
        });
        sent?.delivery.then((ok) => {
          if (ok)
            notice(
              `${reviewed ? "Reviewed" : "Reopened"} ${target.record.path} — sent`,
            );
        });
      });
      entry.node.querySelector(":scope > .lf-diff-file-actions").append(entry.review);
      this.setReviewed(entry, false, { repaint: false });
      this.paintReviewAvailability();
    }

    attachEntryControls(entry, { commentable }) {
      if (commentable) {
        const label = entry.record.path || "file";
        entry.fileComment = commentButton(
          label,
          () => this.threadSurface?.open(entry.node, { origin: entry.fileComment }),
          "lf-diff-file-comment",
        );
        entry.node
          .querySelector(":scope > .lf-diff-file-actions")
          .prepend(entry.fileComment);
        this.attachLineComments(entry);
      }
      this.attachReview(entry);
    }

    attachLineComments(entry) {
      for (const line of entry.lines) {
        const { gutterRow } = this.threadPair(line.node);
        if (line.comment?.parentElement === gutterRow) continue;
        line.comment = commentButton(
          lineLabel(line),
          () => this.threadSurface?.open(line.node, { origin: line.comment }),
          "lf-diff-line-comment",
        );
        // Thousands of lines must not become thousands of Tab stops. The page-level
        // target picker is the keyboard route to the same exact datum; this control is
        // the conventional pointer affordance in the line-number gutter.
        line.comment.tabIndex = -1;
        line.node.addEventListener("pointerenter", () =>
          gutterRow.classList.toggle("lf-diff-line-hover", true),
        );
        line.node.addEventListener("pointerleave", () =>
          gutterRow.classList.toggle("lf-diff-line-hover", false),
        );
        gutterRow.append(line.comment);
      }
    }

    paintReviewAvailability = () => {
      const available = this.controller.read().actions.review?.available ?? false;
      for (const entry of this.fileEntries ?? [])
        if (entry.review instanceof HTMLButtonElement)
          entry.review.toggleAttribute("disabled", !available);
    };

    setReviewed(entry, reviewed, { repaint = true } = {}) {
      if (!entry) return;
      entry.reviewed = reviewed;
      if (!entry.review) return;
      entry.node.toggleAttribute("data-reviewed", reviewed);
      keeps(entry.review, "aria-pressed", reviewed);
      keeps(
        entry.review,
        "aria-label",
        `Mark ${entry.record.path} ${reviewed ? "unreviewed" : "reviewed"}`,
      );
      relabel(entry.review, reviewed ? "✓ Reviewed" : "Mark reviewed", {
        says: reviewed,
      });
      if (repaint) this.refreshDiffTools();
    }

    present(promise) {
      return this.controller.present(promise);
    }

    filterFiles(query) {
      const needle = query.trim().toLocaleLowerCase();
      for (const entry of this.fileEntries ?? []) {
        const paths = [entry.record.path, entry.record.previousPath ?? ""]
          .join("\n")
          .toLocaleLowerCase();
        entry.filtered = Boolean(needle && !paths.includes(needle));
        entry.node.classList.toggle("lf-diff-filtered", entry.filtered);
      }
      this.refreshDiffTools();
      layoutChanged(this);
      this.threadSurface?.update();
    }

    clearFilter() {
      if (this.diffTools) this.diffTools.search.value = "";
      this.filterFiles("");
    }

    refreshDiffTools() {
      if (!this.diffTools || !this.fileEntries) return;
      const shown = this.fileEntries.filter((entry) => !entry.filtered);
      const reviewed = this.fileEntries.filter((entry) => entry.reviewed).length;
      const total = this.fileEntries.length;
      const suffix = shown.length === total ? "" : ` · ${shown.length} matching`;
      keepsText(
        this.diffTools.progress,
        this.reviewing()
          ? `${reviewed} of ${total} reviewed${suffix}`
          : `${total} file${total === 1 ? "" : "s"}${suffix}`,
      );
      this.diffTools.next?.toggleAttribute("disabled", this.nextReviewEntry() === null);
      paintKeys();
    }

    reviewing() {
      return this.hasAttribute("review");
    }

    wrapped() {
      return Boolean(this.diffTools?.wrap.checked);
    }

    shownEntries() {
      return (this.fileEntries ?? []).filter((entry) => !entry.filtered);
    }

    hasHunks() {
      return this.shownEntries().some((entry) => entry.details);
    }

    // Where the user stands inside this diff. A row, a header, or a control in the
    // tools row all answer; the walk only needs a node to compare document positions
    // against, and the tools row standing before every file is why a user who has
    // touched nothing steps to the first hunk rather than nowhere.
    hereNode() {
      const focused = this.shadowRoot?.activeElement;
      return focused && this.shadowRoot.contains(focused) ? focused : null;
    }

    // With nothing focused inside the shadow tree — the host itself is focused, which
    // is where an in-page link to the diff's id lands — every hunk counts as beyond, in
    // either direction: `order` is already reversed for a backward step, so the walk
    // opens the last file and lands on its last hunk, the mirror of the first hunk
    // forward. Answering false there matched no hunk in any file, and the walk opened
    // and fetched every one of them to land nowhere.
    beyond(node, here, back) {
      if (!here) return true;
      const where = here.compareDocumentPosition(node);
      return Boolean(
        where &
        (back ? Node.DOCUMENT_POSITION_PRECEDING : Node.DOCUMENT_POSITION_FOLLOWING),
      );
    }

    markHunkWalk() {
      beginWalk("diff-hunk", "Hunk", () => {
        const entry = this.entryAroundFocus();
        return entry
          ? listWalkPosition(
              hunkHeads(entry).map(({ node }) => node),
              this.hereNode(),
            )
          : null;
      });
    }

    markFileWalk(key = "diff-file", qualifier = "") {
      beginWalk(key, "File", () => {
        const entries = this.shownEntries().filter(
          (entry) => !qualifier || !entry.reviewed,
        );
        return listWalkPosition(
          entries.map(({ node }) => node),
          this.entryAroundFocus()?.node,
          { qualifier },
        );
      });
    }

    async openEntry(entry) {
      if (!entry.details) return;
      entry.details.toggleAttribute("open", true);
      await this.loadManifestEntry(entry);
    }

    // The walk starts in the file the user is standing in and goes on through the
    // ones after it, so a closed file is opened only once the step has actually reached
    // it: a user on the last hunk of the third file loads the fourth and stops, rather
    // than every remaining file to discover there is nothing past them.
    // Opening a file may wait on the network, and the user may have moved on by then:
    // both walks capture the pressing gesture's intent first and land only while it stands.
    async stepHunk(back) {
      const mayLand = retainUserIntent();
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      const standing = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      for (let index = Math.max(standing, 0); index < order.length; index++) {
        const entry = order[index];
        await this.openEntry(entry);
        if (!mayLand()) return;
        const heads = hunkHeads(entry);
        const head = (back ? [...heads].reverse() : heads).find((line) =>
          this.beyond(line.node, here, back),
        );
        if (!head) continue;
        this.land(head.node);
        this.markHunkWalk();
        announce(`${entry.record.path} · hunk ${head.hunk + 1} of ${heads.length}`);
        return;
      }
      this.markHunkWalk();
    }

    stepFile(back) {
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      // The whole file is the unit, so a step out of one starts past it rather than at
      // its own header — and a user standing in the tools row, which belongs to no
      // file, steps to the first (or, walking back, the last).
      const standing = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      const entry = order[standing + 1];
      if (!entry) return this.markFileWalk();
      this.reviewCursor = entry;
      // The box rather than the header, which is what the generated fold target settled for
      // the same shape: a header pinned to the banner is already where it is going, so
      // aligning it moves nothing, while aligning the file it heads starts the file at
      // its start. The header is still what takes the focus.
      this.land(entry.node, entry.details?.firstElementChild ?? entry.node);
      this.markFileWalk();
      announce(entry.record.path);
    }

    // Arrival: scrolled to the band the document declares landable, which the pinned
    // header's own room has been added to, and then the focus without the browser
    // scrolling a second time. A row is not a tab stop — a patch is thousands of them —
    // so it is made focusable for the press that lands on it, and wears the band inset
    // inside its own box (shadow.css). A file header
    // already is one, and writing a tabindex of -1 onto it would take it out of the
    // order a user tabs through.
    //
    // The shared reading-region landing moves only vertically, including through
    // the shadow host. Neither the file nor a region around it loses its sideways place.
    land(box, node = box) {
      if (node.tabIndex < 0) keeps(node, "tabindex", -1);
      scrollIntoReadingBand(box, box, "start", scrollBehavior());
      node.focus({ preventScroll: true });
    }

    entryAroundFocus() {
      const focused = this.hereNode();
      const focusedEntry =
        this.fileEntries?.find(({ node }) => focused && node.contains(focused)) ?? null;
      if (focusedEntry) return focusedEntry;
      return this.fileEntries?.includes(this.reviewCursor) ? this.reviewCursor : null;
    }

    nextReviewEntry() {
      if (!this.reviewing()) return null;
      const entries = (this.fileEntries ?? []).filter(
        (entry) => !entry.filtered && !entry.reviewed,
      );
      if (!entries.length) return null;
      const current = this.entryAroundFocus();
      if (!current) return entries[0];
      const after = entries.find((entry) =>
        Boolean(
          current.node.compareDocumentPosition(entry.node) &
          Node.DOCUMENT_POSITION_FOLLOWING,
        ),
      );
      return after ?? entries[0];
    }

    async nextUnreviewed() {
      const mayLand = retainUserIntent();
      const entry = this.nextReviewEntry();
      if (!entry) return;
      this.reviewCursor = entry;
      if (entry.details) {
        entry.details.toggleAttribute("open", true);
        await this.loadManifestEntry(entry);
        if (!mayLand()) return;
      }
      const target = entry.details?.firstElementChild ?? entry.review;
      scrollIntoReadingBand(target, target, "center", scrollBehavior());
      target.focus({ preventScroll: true });
      this.markFileWalk("diff-unreviewed", "unreviewed");
      notice(`Next unreviewed file: ${entry.record.path}`);
    }

    renderState(state) {
      const reviewed = state?.review?.units ?? {};
      for (const entry of this.fileEntries ?? [])
        this.setReviewed(entry, reviewed[entry.record.path]?.detail.reviewed ?? false, {
          repaint: false,
        });
      this.refreshDiffTools();
    }
  },
);
