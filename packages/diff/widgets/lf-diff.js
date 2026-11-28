/* lf-diff uses Pierre's static renderer rather than hydrating Pierre's custom
 * element. Its ordinary DOM can live in Leaf's declared shadow root, so the
 * rendered lines support selection anchors. `view="file"` draws one active file
 * for a separate navigator; datum reveal selects it without changing file or line identities. A source revision updates evidence
 * under stable file owners: reader controls, disclosure and code scrollports stay
 * connected. A source of two files or more draws a search over them; one file draws
 * none, since there is nothing to filter or open all of, and its count would restate the
 * file's own header. The search reserves its current source's longest count label, so
 * filtering files leaves its field and controls in place. A quiet press after the count
 * opens every file the filter shows, or closes them once all are open. Changed file
 * evidence replaces only its inner presentation and hands
 * source focus to that same file; supplied thread/composer outlets keep core focus
 * ownership across replacement. Unchanged parsed files keep their rendering; changed files
 * reconcile unchanged lines by their datum coordinate, retaining selection and line threads.
 * Every source form, an inline or bound patch text, a file manifest or a file's two
 * texts (`before` and `after`), which the widget turns into their patch, becomes one
 * list of per-file records and renders through one path (`sourceRecords`), so a closed file
 * renders only when it opens, whichever form supplied it; the alternative, a second
 * pipeline for patch text that rendered every file eagerly, drifted from the manifest's
 * on every fix. A source's evidence commits together after open files load. Lazy
 * disclosure joins the pending source render before rendering its file, and a closed file shows
 * none of the previous revision while it renders the current one. Line conversations
 * follow the visible reader width while source lines may scroll horizontally. The
 * browser sizes those conversations from the reader container. Each source row owns
 * its gutter control; ordinary block flow places conversations between rows. Passage reveal
 * clears this widget's file filter; addressed datum reveal also hydrates its file.
 * Pierre parses file paths, modes and hunks; Leaf checks that every source file
 * and its evidence can be represented before any listing metadata appears;
 * closed files retain that parse and defer only textual rendering. Native
 * operations and textual hunks are independent: metadata-only files have a commentable
 * row without an empty disclosure, and a file-type replacement keeps one file identity.
 * Author notes use the same source coordinate resolver as cross-widget navigation;
 * their authored nodes move into the stage, never copied into generated data rows.
 *
 * Bound with `for` to a widget whose current text takes a replacement, as an editor's
 * does while it holds a `revision`, two compared texts offer Revert on each change: a
 * run of changed rows with no unchanged row inside it, the unit every diff tool's
 * Revert takes back, of which a hunk may hold several. Its seat is the change's first
 * row (`revertButton`), after the row's words, so Tab from the row `]` and `[` land on
 * reaches the hunk's first Revert. A press asks the widget, with the `text-document`
 * contract's `--replace`, to hold its text with that change taken back, as jsdiff makes
 * it from the patch of the two texts with no context, whose hunks are the drawing's
 * changes in order (`revertedText`). The widget may fold the request around the user's
 * typing or refuse it, and the diff draws whatever text it then holds. Where the text
 * names its file by `key`, a taken Revert follows the link to its restored line, so the
 * user lands in the file's editor, whose own Undo takes the replacement back; a draft
 * records it, so the page's Undo takes it back from here, where the user stands on the
 * change's row to go on reviewing. A refusal is said as a notice (`lf-error`). Pierre's
 * renderer offers no control of a change's own, so the seat is Leaf's. The widget is
 * portable, so it finds the target by id in its own tree and travels by the link a
 * page could write.
 *
 * Two texts compare line by line with a line's trailing CR set aside, so a file an
 * editor holds with LF breaks reads as unchanged beside the CRLF text it was read
 * from, rather than every line changed, with a Revert no editor could take. */
import { html, nothing, keyed, render } from "/vendor/lit.js";
import {
  focusDestination,
  holdFocus,
  langForPath,
  move,
  threadSurface,
  retainUserIntent,
  searchField,
  setChildren,
  shadowStage,
  whileConnected,
  scrollIntoView,
} from "/runtime/portable-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import { failSoft } from "/runtime/lib/failure.js";
import { nameAction, offer, offerAction } from "/runtime/lib/controls.js";
import { nextRender, sizeObserver } from "/runtime/lib/frame-pass.js";
import { keeps, keepsText, layoutPx } from "/runtime/lib/keeps.js";
import { ensureSyntaxLanguage } from "/runtime/lib/syntax-tokens.js";
import { describeFailure } from "/runtime/lib/exception.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";
import {
  diffDatumKey,
  diffLocationKey,
  findDiffFile,
  findDiffLine,
  readDiffCoordinate,
} from "./diff-coordinates.js";
import { overflowFor } from "./overflow.js";
// The search field's `wa-input`, which a plain page has no chrome to define.
import "/vendor/webawesome-chrome.js";
import { pierre, markSyntax } from "/widgets/pierre.js";
// Only a diff that is actually rendering has any use for Pierre's renderer —
// an authored <lf-diff> bound to data
// that has not arrived yet does not. So it is imported on first use rather than at
// module load: the page pays for the renderer when it draws a diff, and a version whose
// diff has been taken back out stops paying on the next load. The promise is kept, so
// every later file, every other diff on the page, and every re-render share one import.
// Metadata must be parsed before its row commits; unopened text needs no renderer.
/** @typedef {import("@pierre/diffs").FileDiffMetadata} NativeFile */
/** @typedef {{path: string, previousPath?: string, operation: "copy" | "rename" | "add" | "delete" | "modify", hunkCount: number, binary: boolean, oldMode?: string, newMode?: string, additions: number, deletions: number}} FileRecord */
/** @typedef {NativeFile & {record: FileRecord}} ParsedFile */
/** @typedef {{path: string} & ({file: ParsedFile} | {error: unknown})} SourceRecord */
/** @typedef {import("../../../browser/types/contract.js").DataTextDocument} TextDocument */
/** Two texts of one file, `before` and `after` as bound, which the widget compares.
 * @typedef {{before: TextDocument, after: TextDocument}} Comparison */
/** @typedef {import("../../../browser/types/contract.js").DataUnifiedDiff | Comparison} DiffSource */
/** @typedef {{path: string, hunk: number, change?: number} & ({side: "both", oldLine: number, newLine: number} | {side: "old", oldLine: number, newLine?: never} | {side: "new", newLine: number, oldLine?: never})} SourceLine */
/** @typedef {SourceLine & {node: HTMLElement, row: HTMLDivElement, content: string}} RenderedLine */
/** @typedef {Pick<FileRecord, "path"> & Partial<Omit<FileRecord, "path">>} FileSummary */
/** @typedef {{outlet: HTMLElement, row: Element | null, active: boolean}} ThreadSeat */
/** @typedef {{kind: "text", row: HTMLDetailsElement, details: HTMLDetailsElement, header: HTMLElement} | {kind: "metadata", row: HTMLDivElement, details: null, header: HTMLDivElement}} FilePresentation */
/** @typedef {{node: HTMLDivElement, actions: HTMLDivElement, record: FileSummary, source: SourceRecord, rendered: Awaited<ReturnType<typeof renderFile>> | null, filtered: boolean, loaded: boolean, refused: boolean, renderKey: string | null, loading: {rendering: number, promise: Promise<void>} | null, disclosure: {node: HTMLDetailsElement, open: boolean, changed: () => void} | null} & FilePresentation} FileEntry */
/** @typedef {FileEntry & {kind: "text"}} TextEntry */
/** @typedef {FilePresentation & {kind: "text"}} TextPresentation */
/** @typedef {{error: unknown} | {file: ParsedFile, renderKey: string | null, rendered: Awaited<ReturnType<typeof renderFile>> | null}} EntryPreparation */
/** @typedef {typeof import("/vendor/pierre-parser.esm.js")} Parser */
/** @type {Promise<Parser> | null} */
let parser = null;
const parse = () => (parser ??= import("/vendor/pierre-parser.esm.js"));

/** @type {Readonly<import("@pierre/diffs").DiffHunksRendererOptions>} */
const OPTIONS = Object.freeze({
  diffStyle: "unified",
  diffIndicators: "classic",
  disableLineNumbers: false,
  disableFileHeader: true,
  hunkSeparators: "line-info-basic",
  lineDiffType: "word-alt",
});

// The records every source form renders from, one per file, each holding its parsed
// file or the error that refused it. A patch text is parsed once, strictly, so a
// malformed hunk never becomes incomplete evidence, and a failure refuses the whole
// source. A manifest's patches are parsed one by one, so a patch this widget cannot
// draw refuses only its own file; `applyEntry` reports it to the agent that stored
// it, since the manifest's producer leaves judging a patch to this widget. The path
// keys a record in either form; the contract refuses a manifest that repeats one, and
// `parsedFiles` refuses a patch text that does. Two compared texts read as the patch
// of them (`comparedRecords`).
/** @param {DiffSource} source @returns {Promise<readonly SourceRecord[]>} */
async function sourceRecords(source) {
  if (typeof source === "object" && "after" in source) return comparedRecords(source);
  if (typeof source === "string")
    return (await parsedFiles(source)).map((file) => ({ path: file.name, file }));
  return Promise.all(
    source.files.map(async ({ path, patch }) => {
      try {
        return { path, file: await recordFile(patch, path) };
      } catch (error) {
        return { path, error };
      }
    }),
  );
}

// A manifest's patch must describe its keyed logical file, including both native
// sections of a file-type replacement. All display metadata comes from this parse.
/** @param {string} patch @param {string} path */
async function recordFile(patch, path) {
  const [file, extra] = await parsedFiles(patch);
  if (!file || extra || file.name !== path)
    throw new Error(`the patch for ${path} does not contain that one file`);
  return file;
}

// Two texts of one file read as the Git patch of them, with Git's three lines of
// context, and as no file where they are the same. The file takes the name the current
// text gives it, or else the earlier text's, or else `UNNAMED`, since two plain strings
// still compare. A patch holds only its hunks, so the comparison draws as any patch
// does. Handing Pierre both whole texts instead (`parseDiffFromFile`) makes the diff
// expandable: Pierre then draws an unchanged run of one line beside a hunk as a row of
// its own, which the hunks (`sourceLines`) don't hold, and puts expand controls in its
// separators, which nothing here answers.
/** @param {Comparison} comparison @returns {Promise<readonly SourceRecord[]>} */
async function comparedRecords(comparison) {
  const { before, after } = comparison;
  if (textOf(before) === textOf(after)) return [];
  const name =
    [after, before].find((side) => typeof side === "object")?.name ?? UNNAMED;
  const parser = await parse();
  const compared = comparedPatch(parser, comparison, name, 3);
  if (!compared.hunks.length) return [];
  return sourceRecords(parser.formatPatch({ ...compared, isGit: true }));
}

/** @param {TextDocument} side */
const textOf = (side) => (typeof side === "string" ? side : side.text);

// The patch of two compared texts with `context` lines of context: with Git's three,
// the hunks the drawing shows; with none, one hunk for each change those hunks hold,
// in the same order, since only the grouping differs (`sourceLines`).
/** @param {Parser} parser @param {Comparison} comparison @param {string} name
 *  @param {number} context */
const comparedPatch = ({ structuredPatch }, { before, after }, name, context) =>
  structuredPatch(
    `a/${name}`,
    `b/${name}`,
    textOf(before),
    textOf(after),
    undefined,
    undefined,
    { context, stripTrailingCr: true },
  );

// The current text with change `index` of the comparison taken back, and the line of
// the current text where that change stands, which after the Revert is where the
// earlier text's lines stand again; null where the change doesn't apply.
/** @param {Parser} parser @param {Comparison} comparison @param {number} index */
function revertedText(parser, comparison, index) {
  const patch = comparedPatch(parser, comparison, UNNAMED, 0);
  const hunk = patch.hunks[index];
  if (!hunk) return null;
  const text = parser.applyPatch(
    textOf(comparison.after),
    parser.reversePatch({ ...patch, hunks: [hunk] }),
  );
  if (text === false) return null;
  return { text, line: Math.max(1, hunk.newStart) };
}

// Each record carries the index of the hunk it came out of. A hunk is the unit a
// reviewer actually moves in — one `@@` header is one place the author changed
// something — and it is knowable only here, where the parse is still grouped; the
// rendered rows are a flat run with the separator chrome between them, so recovering
// the grouping from the DOM afterwards would be reading a rendering for a fact the
// parse already had. It rides on the same record the anchor coordinate is read off,
// and `diffDatumKey` names only the fields that make a comment's coordinate, so a row
// knowing which hunk it is in changes no anchor.
// A changed row also carries the index of its change in the file, a run of changed
// rows with no unchanged row inside it, which Revert takes back alone.
/** @param {NativeFile} file @returns {SourceLine[]} */
function sourceLines(file) {
  /** @type {SourceLine[]} */
  const lines = [];
  let change = -1;
  for (const [hunk, chunk] of file.hunks.entries()) {
    let oldLine = chunk.deletionStart;
    let newLine = chunk.additionStart;
    let changing = false;
    for (const part of chunk.hunkContent) {
      if (part.type === "context") {
        changing = false;
        for (let index = 0; index < part.lines; index++) {
          lines.push({ path: file.name, hunk, side: "both", oldLine, newLine });
          oldLine++;
          newLine++;
        }
        continue;
      }
      if (!changing) change++;
      changing = true;
      for (let index = 0; index < part.deletions; index++)
        lines.push({ path: file.name, hunk, change, side: "old", oldLine: oldLine++ });
      for (let index = 0; index < part.additions; index++)
        lines.push({ path: file.name, hunk, change, side: "new", newLine: newLine++ });
    }
  }
  return lines;
}

// The first rendered row of each hunk: the places `]` and `[` land. Read off the
// records rather than counted in the DOM, so an unloaded file simply has none.
/** @param {FileEntry} entry */
const hunkHeads = (entry) =>
  (entry.rendered?.lines ?? []).filter(
    (line, index, lines) => line.hunk !== lines[index - 1]?.hunk,
  );
// The first rendered row of each change, where its Revert stands.
/** @param {FileEntry} entry */
const changeHeads = (entry) =>
  (entry.rendered?.lines ?? []).filter(
    (line, index, lines) =>
      line.change !== undefined && line.change !== lines[index - 1]?.change,
  );
/** @template {Element} T @param {{node: T}} holder */
const nodeOf = ({ node }) => node;

const LINE_KEY = "data-lf-line";
// What a file with no name is called.
const UNNAMED = "(unnamed file)";

/** @param {import("./diff-coordinates.js").DiffCoordinate} coordinate */
const lineLabel = ({ path, side, oldLine, newLine }) => {
  const file = path || UNNAMED;
  if (side === "old") return `${file} · old line ${oldLine}`;
  if (side === "new") return `${file} · new line ${newLine}`;
  return `${file} · old line ${oldLine} · new line ${newLine}`;
};

// A line number's name holds the numbers its gutter shows in the order it shows them,
// so a user who speaks what they see reaches it (WCAG 2.5.3, Label in Name).
/** @param {import("./diff-coordinates.js").DiffCoordinate} coordinate */
const gutterLabel = (coordinate) =>
  coordinate.side === "both"
    ? `${coordinate.path || UNNAMED} · old and new line ${coordinate.oldLine} ${coordinate.newLine}`
    : lineLabel(coordinate);

/** @param {{path: string}} record */
const fileLabel = ({ path }) => `${path || UNNAMED} · file`;
// Only the header represents the file datum. The body contains independently
// addressed lines and authored prose, whose comments must not inherit its identity.
/** @param {FileEntry} entry */
const fileNode = (entry) => entry.header;
/** @param {FileEntry} entry @returns {import("./diff-coordinates.js").DiffCoordinate & {file: true, node: HTMLElement}} */
const fileDatum = (entry) => ({
  file: true,
  path: entry.record.path,
  node: fileNode(entry),
});

// The marks that make a drawn file row or line a datum on a Leaf page
// (`module-state.md`, "Marking drawn data"), and their removal from a node kept
// after it stops showing one.
const MARKS = ["data-lf-datum", "data-lf-datum-label", "data-lf-origin-path"];
/** @param {(import("./diff-coordinates.js").DiffCoordinate & {node: Element})} record @param {readonly (string | number)[] | null} path */
const mark = (record, path) => {
  keeps(record.node, "data-lf-datum", diffDatumKey(record));
  keeps(
    record.node,
    "data-lf-datum-label",
    record.file ? fileLabel(record) : lineLabel(record),
  );
  keeps(record.node, "data-lf-origin-path", path ? JSON.stringify(path) : null);
};
/** @param {Element} node */
const unmark = (node) => {
  for (const name of MARKS) node.removeAttribute(name);
};

/** @param {SourceLine} line @param {boolean} canComment */
function lineNumber(line, canComment) {
  const number = canComment
    ? offerAction("gutter", "lf-diff-line-number lf-diff-comment lf-diff-line-comment")
    : offer("span", "lf-diff-line-number");
  if (number instanceof HTMLButtonElement) {
    number.type = "button";
    number.tabIndex = -1;
    number.setAttribute("aria-label", `Comment on ${gutterLabel(line)}`);
    number.setAttribute(LINE_KEY, diffDatumKey(line));
  }
  // Two cells, the old file's number and the new file's, as a unified diff reads: one
  // column holding whichever number a row has would mix the two files' counts, which
  // drift apart once a hunk adds or removes lines. A space stands between the cells,
  // where the gutter's grid draws nothing, so the numbers read as two words.
  number.toggleAttribute("data-lf-echo", true);
  /** @param {number | string} value */
  const cell = (value) => {
    const span = document.createElement("span");
    span.textContent = String(value);
    return span;
  };
  number.replaceChildren(
    cell(line.side === "new" ? "" : line.oldLine),
    " ",
    cell(line.side === "old" ? "" : line.newLine),
  );
  return number;
}

// Pierre owns parsing, highlighting and word differences. Leaf gives each source
// line one native row: its numbers offer Comment while a surface is registered, and a
// conversation can follow that row without a separate gutter element to reconcile or
// measure.
/** @param {NativeFile} file @param {DocumentFragment} content */
function renderedLines(file, content) {
  const records = sourceLines(file);
  /** @type {NodeListOf<HTMLElement>} */
  const sourceNodes = content.querySelectorAll("[data-line]");
  const nodes = [...sourceNodes];
  if (nodes.length !== records.length)
    throw new Error(
      `Pierre returned ${nodes.length} source lines for ${file.name}; expected ${records.length}`,
    );
  const iterator = nodes.values();
  return records.map((record) => {
    const next = iterator.next();
    if (next.done) throw new Error("Pierre returned no node for a source line");
    const node = next.value;
    // Pierre represents an empty source row with a newline placeholder.
    if (node.textContent === "\n") node.replaceChildren();
    const key = diffDatumKey(record);
    node.setAttribute(LINE_KEY, key);
    const row = document.createElement("div");
    row.className = "lf-diff-line";
    keeps(row, "data-line-type", node.getAttribute("data-line-type"));
    const number = lineNumber(record, false);
    node.replaceWith(row);
    row.append(number, node);
    return { ...record, node, row, content: node.innerHTML };
  });
}

// A path separates ancestors, the immediate parent, and the basename. A narrow row
// elides ancestors first so repeated basenames keep their distinguishing parent;
// a rename shares the space between both basenames before folders (widget-shadow.css). Where
// a path wraps, as in a rename's row, it breaks after its slashes before anywhere else:
// with no break in it but the one the stylesheet forces, a narrow row cut names mid-word
// ("skills/wor|ktrunk", "preview.|rs"). The text is unchanged; a <wbr> adds only the
// opportunity.
/** @param {string} path */
function pathTemplate(path) {
  const parts = path.split("/");
  const base = parts.pop();
  const parent = parts.pop();
  return html`${
      parts.length
        ? html`<span class="lf-diff-dir lf-diff-dir-ancestor"
            >${parts.map((part) => html`${part}/<wbr />`)}</span
          >`
        : ""
    }${
      parent !== undefined
        ? html`<span class="lf-diff-dir lf-diff-dir-parent">${parent}/</span><wbr />`
        : ""
    }<span class="lf-diff-base">${base}</span>`;
}

// While a file's row cuts its path short, the row's preview is the whole path, which a
// resting pointer, the keyboard and a held press read (`lfPreview`,
// module-previews.md). A path the row shows whole previews nothing, since it would repeat it.
// Whether the row cuts the path changes only with the width
// of a part of it, the folders or the name (at a new window width, face or press beside
// it), so each part's size is watched rather than polled. A part is cut where its words
// run past its box, measured by a Range to the layout unit: `scrollWidth` rounds to
// whole pixels, and the ellipsis is drawn for a fraction of one. A folder region too
// small for this font's ellipsis is left blank: the browser otherwise paints a glyph
// sliver. Its CSS measurement box supplies the native width. Opacity elides only paint,
// leaving flex allocation and the full path for accessibility and the preview intact.
//
// One observer watches every file's row, so a delivery reads every row it names before
// writing any. A summary's paint starts watching its path parts and moves that
// observation when their identity changes (`paintSummary`); replacing its row stops
// the old observations (`replaceFileRendering`). Summaries are created only within
// the synchronous source commit, after its evidence is prepared. Rendered evidence goes
// into the kept row (`replaceFileContent`) and brings no row of its own. A
// row that leaves the page with its file or its diff is not unwatched: an observer
// holds what it watches weakly, so the row is collected with its observation.
/** @param {Element} part */
const runsPast = (part) => {
  const words = new Range();
  words.selectNodeContents(part);
  return words.getBoundingClientRect().width > part.getBoundingClientRect().width;
};
/** @param {FilePresentation} view @returns {HTMLSpanElement[]} */
const pathParts = (view) =>
  view.kind === "text"
    ? [...view.header.querySelectorAll("span")].filter((span) =>
        span.matches(".lf-diff-dir, .lf-diff-base"),
      )
    : [];
/** @type {WeakMap<Element, {path: HTMLElement, header: HTMLElement}>} */
const pathOwners = new WeakMap();
// The whole path a row cuts short, by its row.
/** @type {WeakMap<Element, string>} */
const cutPaths = new WeakMap();
/** @this {Element} */
function cutPath() {
  const path = cutPaths.get(this);
  return path === undefined ? null : { name: path };
}
const pathSizes = sizeObserver((entries) => {
  const owners = new Set(
    entries.flatMap(({ target }) => {
      const owner = pathOwners.get(target);
      return owner ? [owner] : [];
    }),
  );
  const readings = [...owners].map(({ path, header }) => {
    const parts = [...path.querySelectorAll(".lf-diff-dir, .lf-diff-base")];
    return {
      path,
      header,
      cut: parts.some(runsPast),
      folders: parts
        .filter((part) => part.matches(".lf-diff-dir"))
        .map((part) => ({
          part,
          hidden:
            Number.parseFloat(getComputedStyle(part, "::before").width) >
            part.getBoundingClientRect().width,
        })),
    };
  });
  for (const { path, header, cut, folders } of readings) {
    if (cut) cutPaths.set(header, path.textContent);
    else cutPaths.delete(header);
    for (const { part, hidden } of folders)
      part.toggleAttribute("data-lf-folder-hidden", hidden);
  }
});

/** @param {FilePresentation} view */
function unwatchPathCut(view) {
  for (const part of pathParts(view)) pathSizes.unobserve(part);
}

/** @param {FileSummary} record */
function filePathTemplate({ path, previousPath }) {
  const name = path || UNNAMED;
  return html`<span class="lf-diff-path"
    >${
      previousPath
        ? html`<span class="lf-diff-source-path">${pathTemplate(previousPath)}</span
            ><span class="lf-diff-arrow"> → </span
            ><span class="lf-diff-destination-path">${pathTemplate(path)}</span>`
        : pathTemplate(name)
    }</span
  >`;
}

// Lit owns only the summary's contents. The native disclosure and Pierre's body
// stay connected across revisions, including loading and failed evidence.
/** @param {TextPresentation} view @param {FileSummary} record @param {boolean} [verified] */
function paintSummary(view, record, verified = true) {
  const { path, previousPath, additions, deletions } = record;
  const previous = pathParts(view);
  render(
    html`${keyed(
      JSON.stringify([path, verified && previousPath ? previousPath : null]),
      filePathTemplate(verified ? record : { path }),
    )}${
      verified
        ? html`<span class="lf-diff-stat" data-lf-gen="1"
            ><span class="lf-diff-additions">+${additions}</span>${" "}<span
              class="lf-diff-deletions"
              >−${deletions}</span
            ><span class="lf-diff-metadata-words"
              >${operationWord(record) ? ` · ${operationWord(record)}` : ""}</span
            ></span
          >`
        : null
    }`,
    view.header,
  );
  const current = pathParts(view);
  /** @type {HTMLElement | null} */
  const pathNode = view.header.querySelector(".lf-diff-path");
  if (!pathNode) throw new Error("Diff summary did not draw its path");
  const owner = { path: pathNode, header: view.header };
  for (const part of current) pathOwners.set(part, owner);
  for (const part of previous) if (!current.includes(part)) pathSizes.unobserve(part);
  for (const part of current) if (!previous.includes(part)) pathSizes.observe(part);
}

/** @param {FileSummary} record @param {boolean} open @param {boolean} [verified] */
function summaryNode(record, open, verified = true) {
  const details = document.createElement("details");
  details.className = "lf-diff-fold";
  details.open = open;
  const summary = document.createElement("summary");
  summary.className = "lf-diff-head lf-disclosure-marker";
  summary.lfPreview = cutPath;
  details.append(summary);
  /** @type {TextPresentation} */
  const view = { kind: "text", row: details, details, header: summary };
  paintSummary(view, record, verified);
  paintFileDetails(view, verified ? record : {});
  return view;
}

// A file's entry: its row, a disclosure or a rename's line, beside its comment control.
// The press cannot go inside the <summary>: a disclosure is itself a control, and a
// control nested in one is announced as a single thing — the serious
// `nested-interactive` finding the corpus's axe sweep reports, once per file. They are
// siblings in this wrapper instead, the press first, and widget-shadow.css draws it back onto
// the summary line. First because the line pins: the summary sticks at the window's top
// while its rows go past, and the press sticks with it only as a box in the flow ahead
// of the disclosure, since a box placed against the file's top would stay there and
// drift off the header it belongs to.
/** @param {FilePresentation} view @param {FileSummary} record @param {SourceRecord} source @returns {FileEntry} */
function fileEntry(view, record, source) {
  const node = document.createElement("div");
  node.className = "lf-diff-file";
  const actions = offer("div", "lf-diff-file-actions");
  node.append(actions, view.row);
  return {
    ...view,
    node,
    actions,
    record,
    source,
    loaded: false,
    refused: false,
    renderKey: null,
    loading: null,
    disclosure: null,
    rendered: null,
    filtered: false,
  };
}

/** @param {string} label @param {(() => void) | null} opened @param {string} className */
function commentButton(label, opened, className) {
  const button = offerAction(
    "symbol",
    `lf-diff-comment ${className}`,
    `Comment on ${label}`,
    {
      action: "comment",
    },
  );
  if (opened) button.addEventListener("click", opened);
  return button;
}

// A change's Revert, Leaf's U-turn standing in its first row's gutter
// (widget-shadow.css), after the row's words, keyed as the line is, so a redraw that
// takes it away hands its focus to the nearest line that stays.
/** @param {RenderedLine} line */
function revertButton(line) {
  const button = offerAction("symbol", "lf-diff-revert", undefined, {
    action: "revert",
  });
  button.setAttribute(LINE_KEY, diffDatumKey(line));
  line.row.append(button);
}

// Keep file controls and evidence under one retained body across source revisions.
/** @param {readonly Node[]} nodes */
function diffBody(nodes) {
  const body = document.createElement("div");
  body.className = "lf-diff-body";
  body.append(...nodes);
  return body;
}

// File and listing controls are browser-owned inspection state. Updating the evidence
// keeps their owners connected; only changed rendered content is replaced. A line's
// existing datum coordinate supplies its focus counterpart when that content changes.
// A file's datum owns its controls even when its evidence changes kind. Only the
// inner presentation changes; a focus that no longer has a line or disclosure lands
// on that same file, while surviving controls keep their own native focus.
//
// Thread outlets hold core's composer and thread views, so neither replacement takes one
// out of the document: an outlet stays in its file until the thread surface has placed
// what stands in it and retires it (`retireThreadOutlets`). The user writing in one
// keeps their place natively, and no hold of this file's stands in for theirs.
/** @param {FileEntry} entry */
const holdFileFocus = (entry) => holdFocus(entry.node, { key: LINE_KEY });

/** @param {FileEntry} entry @param {FilePresentation} view */
function replaceFileRendering(entry, view) {
  const restore = holdFileFocus(entry);
  unwatchPathCut(entry);
  // Out of the replaced row first, which takes everything still in it.
  const outlets = [
    ...entry.node.querySelectorAll(".lf-diff-thread-outlet, lf-diff-note"),
  ];
  for (const outlet of outlets)
    if (outlet.parentNode !== entry.node) move(entry.node, outlet, null);
  setChildren(entry.node, [entry.actions, view.row, ...outlets]);
  Object.assign(entry, view);
  entry.rendered = null;
  entry.renderKey = null;
  return () => restore?.(entry.header, entry.node);
}

// The line each thread outlet in a file follows once the file is
// drawn anew, as `{lead, after}`: its own datum's line in `rows` where that is drawn
// again, which its record now names, or else the line that stood before it, or `lead`,
// the file's start, where none did.
/** @param {HTMLElement | undefined} content @param {Map<string, RenderedLine>} rows @param {Map<string, ThreadSeat>} outlets @param {Map<Element, RenderedLine>} previous */
function outletPlaces(content, rows, outlets, previous) {
  /** @type {ThreadSeat[]} */
  const lead = [];
  /** @type {Map<string, ThreadSeat[]>} */
  const after = new Map();
  /** @type {string | null} */
  let last = null;
  for (const child of content?.children ?? []) {
    const line = previous.get(child);
    if (line) {
      const key = diffDatumKey(line);
      if (rows.has(key)) last = key;
      continue;
    }
    const datum = child.getAttribute("data-lf-thread-datum");
    if (datum === null) continue;
    const record = outlets.get(datum);
    if (record?.outlet !== child) continue;
    const next = rows.get(datum);
    if (next) record.row = next.node;
    const place = next ? datum : last;
    if (place === null) lead.push(record);
    else {
      const following = after.get(place);
      if (following) following.push(record);
      else after.set(place, [record]);
    }
  }
  return { lead, after };
}

// A file's evidence goes under its kept disclosure, whose summary the record paints.
/** @param {TextEntry} entry @param {Awaited<ReturnType<typeof renderFile>>} rendered @param {Map<string, ThreadSeat>} outlets */
function replaceFileContent(entry, rendered, outlets) {
  const restore = holdFileFocus(entry);
  // These authored members have an independent lifetime from the source rows.
  const notes = [...entry.node.querySelectorAll("lf-diff-note")];
  for (const note of notes) move(entry.node, note, null);
  const details = entry.details;
  const previousRender = entry.rendered;
  const pre = previousRender?.pre;
  const prior = new Map(
    (previousRender?.lines ?? []).map((line) => [diffDatumKey(line), line]),
  );
  const retained = new Map();
  /** @type {Map<Element, RenderedLine>} */
  const byRow = new Map(rendered.lines.map((line) => [line.row, line]));
  for (const next of rendered.lines) {
    const previous = prior.get(diffDatumKey(next));
    if (!previous || previous.content !== next.content) continue;
    retained.set(next.row, previous.row);
    next.node = previous.node;
    next.row = previous.row;
  }
  const rows = new Map(rendered.lines.map((line) => [diffDatumKey(line), line]));
  const content = previousRender?.rows;
  /** @type {Map<Element, RenderedLine>} */
  const previous = new Map(
    (entry.rendered?.lines ?? []).map((line) => [line.row, line]),
  );
  const { lead, after } = outletPlaces(content, rows, outlets, previous);
  const nextContent = rendered.rows;
  const children = [
    ...lead.map(({ outlet }) => outlet),
    ...[...nextContent.children].flatMap((row) => {
      const line = byRow.get(row);
      const following = line ? (after.get(diffDatumKey(line)) ?? []) : [];
      return [retained.get(row) ?? row, ...following.map(({ outlet }) => outlet)];
    }),
  ];
  if (previousRender) {
    keeps(previousRender.pre, "data-overflow", rendered.pre.dataset.overflow);
    keeps(previousRender.rows, "style", nextContent.getAttribute("style"));
    setChildren(previousRender.rows, children);
  } else setChildren(nextContent, children);
  setChildren(details, [entry.header, pre ?? rendered.pre]);
  entry.rendered = {
    ...rendered,
    pre: pre ?? rendered.pre,
    rows: content ?? rendered.rows,
  };
  return () => restore?.(entry.header);
}

/** @param {{filterFiles: (value: string | null) => void, foldAll: () => void}} host */
function diffTools(host) {
  const search = searchField("lf-diff-tools lf-diff-search", {
    name: "diff-search",
    label: "Filter diff files",
    placeholder: "Filter files…",
  });
  search.addEventListener("input", () => host.filterFiles(search.value));
  const progress = document.createElement("span");
  progress.className = "lf-diff-progress";
  keeps(progress, "data-lf-gen", "1");
  progress.slot = "end";
  const count = document.createElement("span");
  progress.append(count);
  // Opening every file is rare beside opening one, so it is a quiet icon after the count
  // of the files it opens rather than a labelled button of its own (widget-shadow.css).
  const foldAll = offerAction("symbol", "lf-diff-fold-all", undefined, {
    action: "expand-all",
  });
  foldAll.slot = "end";
  foldAll.addEventListener("click", () => host.foldAll());
  search.append(progress, foldAll);
  return { search, progress, count, foldAll };
}

/** @param {FileSummary} record */
function operationWord(record) {
  return record.operation === "add"
    ? "added"
    : record.operation === "delete"
      ? "deleted"
      : record.operation === "rename"
        ? "renamed"
        : record.operation === "copy"
          ? "copied"
          : "";
}

/** @param {Partial<FileRecord>} record */
function evidenceWords(record) {
  const words = [];
  if (record.binary) words.push("binary content");
  // Added/deleted ordinary files need no mode label; retain every actual mode
  // change and the type or executable bit of a file with only one side.
  if ((record.oldMode ?? "100644") !== (record.newMode ?? "100644")) {
    words.push(
      record.oldMode && record.newMode
        ? `mode ${record.oldMode} → ${record.newMode}`
        : `mode ${record.newMode ?? record.oldMode}`,
    );
  }
  return words.join(" · ");
}

/** @param {FileSummary} record */
function metadataWords(record) {
  return [operationWord(record), evidenceWords(record)].filter(Boolean).join(" · ");
}

// Header counts and the short operation keep their columns. Longer mode/binary
// evidence belongs with the disclosed text, where it can wrap without hiding a path.
/** @param {TextPresentation} view @param {Partial<FileRecord>} record */
function paintFileDetails(view, record) {
  const { details, header } = view;
  const words = evidenceWords(record);
  let evidence = details.querySelector(":scope > .lf-diff-evidence");
  if (!words) {
    evidence?.remove();
    return;
  }
  if (!evidence) {
    evidence = document.createElement("div");
    evidence.className = "lf-diff-evidence";
    keeps(evidence, "data-lf-gen", "1");
    header.after(evidence);
  }
  keepsText(evidence, words);
}

/** @param {FileSummary} record @returns {FilePresentation & {kind: "metadata"}} */
function metadataNode(record) {
  const row = document.createElement("div");
  row.className = "lf-diff-metadata";
  keeps(row, "data-lf-gen", "1");
  render(
    html`${filePathTemplate(record)}<span class="lf-diff-stat"
        >${metadataWords(record)}</span
      >`,
    row,
  );
  return { kind: "metadata", row, header: row, details: null };
}

/** @param {NativeFile} file @param {string} section @param {typeof import("@pierre/diffs").parsePatchFiles} parsePatchFiles @returns {FileRecord} */
function fileRecord(file, section, parsePatchFiles) {
  const copyFrom = /^copy from /m.test(section);
  const copyTo = /^copy to /m.test(section);
  const renameFrom = /^rename from /m.test(section);
  const renameTo = /^rename to /m.test(section);
  if (copyFrom !== copyTo || renameFrom !== renameTo)
    throw new Error("diff has incomplete copy or rename headers");
  if (/^old mode /m.test(section) !== /^new mode /m.test(section))
    throw new Error("diff has incomplete mode headers");
  if (copyFrom || renameFrom) {
    // Pierre resolves a path from the source headers too. Read its metadata alone
    // to catch a conflicting copy or rename source without decoding Git paths here.
    const header = section.slice(
      0,
      section.search(/^--- /m) < 0 ? section.length : section.search(/^--- /m),
    );
    const metadata = parsePatchFiles(header, { throwOnError: true }).flatMap(
      (patch) => patch.files,
    )[0];
    if (metadata?.prevName !== file.prevName || metadata?.name !== file.name)
      throw new Error("diff has conflicting copy or rename paths");
  }
  const operation = copyFrom
    ? "copy"
    : renameFrom
      ? "rename"
      : file.type === "new"
        ? "add"
        : file.type === "deleted"
          ? "delete"
          : "modify";
  const binary = /^(?:Binary files .+ differ|GIT binary patch)$/m.test(section);
  // A file header without hunks would silently omit its source evidence.
  if (!file.hunks.length && /^(?:---|\+\+\+) /m.test(section))
    throw new Error("diff has source headers without textual hunks");
  const oldMode = operation === "add" ? undefined : (file.prevMode ?? file.mode);
  const newMode = operation === "delete" ? undefined : file.mode;
  const { additions, deletions } = file.hunks.reduce(
    (counts, hunk) => ({
      additions: counts.additions + hunk.additionLines,
      deletions: counts.deletions + hunk.deletionLines,
    }),
    { additions: 0, deletions: 0 },
  );
  return {
    path: file.name,
    ...(file.prevName ? { previousPath: file.prevName } : {}),
    operation,
    hunkCount: file.hunks.length,
    binary,
    ...(oldMode ? { oldMode } : {}),
    ...(newMode ? { newMode } : {}),
    additions,
    deletions,
  };
}

// Prepare only the dependency's highlighted source. Leaf's own block layout needs
// neither Pierre's parallel-column DOM nor its layout stylesheet and resize manager.
/** @param {NativeFile} file @param {import("@pierre/diffs").DiffHunksRendererOptions["overflow"]} overflow */
async function renderFile(file, overflow) {
  const lang = langForPath(file.name);
  const [{ DiffHunksRenderer, renderHTML }, { themeName, foreground }] =
    await Promise.all([pierre(), ensureSyntaxLanguage(lang)]);
  const renderer = new DiffHunksRenderer({
    ...OPTIONS,
    overflow,
    theme: themeName,
    useTokenTransformer: false,
  });
  const highlighted = await renderer.asyncRender({ ...file, lang: lang ?? "text" });
  const template = document.createElement("template");
  template.innerHTML = renderHTML(
    (highlighted.columns.unified ?? []).map(
      (/** @type {import("@pierre/diffs").RowSpec} */ row) => row.content,
    ),
  );
  const content = template.content;
  content.querySelector("svg[data-icon-sprite]")?.remove();
  for (const separator of content.querySelectorAll(
    "[data-separator], [data-no-newline]",
  ))
    separator.classList.add("lf-ui");
  markSyntax(content, foreground);
  const lines = renderedLines(file, content);
  // The block is its source's ring frame (surfaces.css, `.lf-ring-frame`): the ring
  // stands over the rows the source scrolls, outside its scrollport.
  const pre = document.createElement("pre");
  pre.className = "lf-ring-frame";
  pre.dataset.overflow = overflow;
  const viewport = document.createElement("code");
  viewport.dataset.code = "";
  viewport.className = "lf-text-scroller";
  viewport.toggleAttribute("data-lf-scroll", true);
  viewport.setAttribute("role", "region");
  viewport.setAttribute("aria-label", file.name || "diff");
  const rows = document.createElement("div");
  rows.className = "lf-diff-rows";
  const largest = lines.reduce(
    (max, line) => Math.max(max, line.oldLine ?? 0, line.newLine ?? 0),
    0,
  );
  const digits = String(largest).length;
  rows.style.setProperty("--lf-diff-digits", `${digits}ch`);
  rows.style.setProperty("--lf-diff-gutter", `${2 * digits + 4}ch`);
  rows.append(content);
  viewport.append(rows);
  pre.append(viewport);
  return { pre, rows, lines };
}

/** @param {readonly [ParsedFile, ...ParsedFile[]]} files @param {typeof import("@pierre/diffs").parseDiffFromFile} parseDiffFromFile @returns {ParsedFile} */
function replacementFile(files, parseDiffFromFile) {
  const deleted = files.find((file) => file.record.operation === "delete");
  const added = files.find((file) => file.record.operation === "add");
  const oldMode = deleted?.record.oldMode;
  const newMode = added?.record.newMode;
  if (
    files.length !== 2 ||
    !deleted ||
    !added ||
    !oldMode ||
    !newMode ||
    (parseInt(oldMode, 8) & 0o170000) === (parseInt(newMode, 8) & 0o170000)
  )
    throw new Error(`unified diff repeats file path ${files[0].name}`);
  const hunkCount = Number(files.some((file) => file.record.hunkCount > 0));
  // A different file type consumes the old object and produces the new one, even
  // when both carry identical text. jsdiff's comparator keeps that meaning. Pierre
  // passes it on to jsdiff, though its options type lists only @pierre/patches' keys.
  /** @type {import("@pierre/diffs").ParseDiffOptions & import("diff").CreatePatchOptionsNonabortable} */
  const everyLineChanges = { preferredDiffLib: "jsdiff", comparator: () => false };
  /** @param {ParsedFile} file @param {readonly string[]} lines */
  const side = (file, lines) =>
    file.record.binary
      ? null
      : {
          name: file.name,
          contents: lines.join(""),
        };
  const file = hunkCount
    ? parseDiffFromFile(
        side(deleted, deleted.deletionLines),
        side(added, added.additionLines),
        everyLineChanges,
        true,
      )
    : { ...added, hunks: [] };
  /** @type {FileRecord} */
  const record = {
    path: added.name,
    operation: "modify",
    hunkCount,
    binary: deleted.record.binary || added.record.binary,
    oldMode,
    newMode,
    additions: added.record.additions,
    deletions: deleted.record.deletions,
  };
  return { ...file, record };
}

// What the widget can present, which it alone judges: the diff package's
// `patch_manifest.py` preserves the evidence, and an entry refused here reports when
// its listing appears, even when its textual file stays closed. `tests/diff_patch_cases.json`
// is the table of cases.
/** @param {string} source @returns {Promise<ParsedFile[]>} */
async function parsedFiles(source) {
  const { parsePatchFiles, parseDiffFromFile } = await parse();
  const files = parsePatchFiles(source, { throwOnError: true }).flatMap(
    (patch) => patch.files,
  );
  const sections = source
    .split(/(?=^diff --git )/m)
    .filter((section) => section.startsWith("diff --git "));
  if (!files.length) throw new Error("empty diff");
  const alignmentError = () =>
    new Error(
      "Expected a Git patch with a diff --git header for each file; preserve the file headers from git diff.",
    );
  /** @type {Map<string, [ParsedFile, ...ParsedFile[]]>} */
  const owners = new Map();
  const parsed = files.values();
  for (const section of sections) {
    const next = parsed.next();
    if (next.done) throw alignmentError();
    const file = {
      ...next.value,
      record: fileRecord(next.value, section, parsePatchFiles),
    };
    const owned = owners.get(file.name);
    if (owned) owned.push(file);
    else owners.set(file.name, [file]);
  }
  if (!parsed.next().done) throw alignmentError();
  return [...owners.values()].map((files) =>
    joinChangeRuns(
      files.length === 1 ? files[0] : replacementFile(files, parseDiffFromFile),
    ),
  );
}

// Pierre splits a change whose deleted and added line counts differ into pieces, so
// its most similar lines pair up (`realignChangeContentBySimilarity`, run by
// `parsePatchFiles` since @pierre/diffs 1.3.0). That serves a split view, which Leaf never draws. In the unified
// view it moved a rewrite's four deleted lines between the 11th and 12th of its 19
// added ones, cutting the new function in two and painting the indentation it had
// paired as changed words. Leaf joins the pieces back into the one change git wrote,
// its deletions above its additions. A git patch never puts two changes side by side
// without context, so a one-sided change beside another is always such a piece. The
// rows, line numbers and comment coordinates are the same either way.
/** @template {NativeFile} T @param {T} file @returns {T} */
function joinChangeRuns(file) {
  for (const hunk of file.hunks) {
    /** @type {NativeFile["hunks"][number]["hunkContent"]} */
    const content = [];
    for (const part of hunk.hunkContent) {
      const last = content.at(-1);
      if (
        part.type !== "change" ||
        last?.type !== "change" ||
        ![part, last].some((change) => !change.deletions || !change.additions)
      ) {
        content.push({ ...part });
        continue;
      }
      last.deletions += part.deletions;
      last.additions += part.additions;
    }
    hunk.hunkContent = content;
  }
  return file;
}

// The box takes the place of the file's lines, so core's composer leaves their outlets
// first: a user writing about one of them stays in it. Focus left inside the file
// moves to its header.
/** @param {TextPresentation} view @param {unknown} error
 * @param {ReturnType<typeof threadSurface>} surface the diff's own */
function fileError(view, error, surface) {
  const { details, header } = view;
  surface.release(details);
  const restore = holdFocus(details);
  const box = document.createElement("div");
  box.className = "lf-error";
  keeps(box, "data-lf-gen", "1");
  box.textContent = `That file's diff cannot be shown: ${describeFailure(error)}`;
  setChildren(details, [header, box]);
  restore?.(header);
}

customElements.define(
  "lf-diff",
  class extends LeafElement {
    // shadowStage owns the imperative diff; Lit owns no nodes in that stage.
    createRenderRoot() {
      return this;
    }

    // The source the last render read, a bound value, an inline patch or two compared
    // texts, and the one whose rendering last started; a departure that cuts a
    // rendering short forgets it, so the return draws it again.
    /** @type {DiffSource | null | undefined} */
    #delivered;
    /** @type {DiffSource | null | undefined} */
    #shown;
    // The comparison of the texts `beforeText` and `afterText` held when it was made, kept
    // while both stand, so an update that leaves them draws nothing again.
    /** @type {Comparison | null} */
    #comparison = null;
    #showing = false;
    // The rendering the update under way started, which its `updateComplete` waits for.
    /** @type {Promise<void> | undefined} */
    #rendered;
    // The nodes the last marking marked as data.
    /** @type {Set<Element>} */
    #marked = new Set();

    /** @type {{source: DiffSource, entries: FileEntry[]} | null} */
    committed = null;
    get fileEntries() {
      return this.committed?.entries ?? null;
    }
    get drawnSource() {
      return this.committed?.source ?? null;
    }
    /** @type {HTMLDivElement | null} */
    filesBody = null;
    /** @type {ReturnType<typeof diffTools> | null} */
    diffTools = null;
    /** @type {string | undefined} */
    activePath = undefined;
    /** @type {Promise<void> | undefined} */
    sourceRendering = undefined;
    /** @type {Map<string, ThreadSeat>} */
    threadSeats = new Map();
    /** @type {Map<TextEntry, {prepared: EntryPreparation, rendering: number}> | null} */
    loadedQueue = null;
    /** @type {Promise<void> | null} */
    loadedCommit = null;
    /** @type {FileEntry | null} */
    fileCursor = null;
    /** @type {Element[]} */
    authorNotes = [];
    rendering = 0;
    unplacedNotes = document.createElement("div");
    // The patch text or file manifest, set by whoever hosts the widget: Leaf from the
    // bound source (the registry's `inputs.document.property`), or from the
    // written `<pre>`; null while a bound source has none. In its place, a file's two
    // texts, `beforeText` and `afterText`, each set from its own input, which the
    // widget compares while it holds both. Neither is named `before` or `after`, which
    // every element already answers as a method.
    static properties = {
      value: { attribute: false },
      beforeText: { attribute: false },
      afterText: { attribute: false },
    };

    constructor() {
      super();
      /** @type {import("../../../browser/types/contract.js").DataUnifiedDiff | null} */
      this.value = null;
      /** @type {TextDocument | null} */
      this.beforeText = null;
      /** @type {TextDocument | null} */
      this.afterText = null;
    }

    /** @returns {DiffSource | null} */
    #source() {
      const { beforeText: before, afterText: after } = this;
      if (before == null || after == null) return this.value;
      if (this.#comparison?.before !== before || this.#comparison.after !== after)
        this.#comparison = { before, after };
      return this.#comparison;
    }

    setup() {
      // A diff comparing two texts draws no patch, and `page check` can't tell its
      // `<pre>` from one that an input beside it leaves in place, so the diff refuses
      // to draw rather than show a patch it was never meant to.
      if (this.hasAttribute("before") && this.querySelector(":scope > pre"))
        throw new Error("a diff comparing two texts holds no patch <pre>");
      this.singleFile = this.getAttribute("view") === "file";
      this.lfCommands = {
        title: "In a diff review",
        when: () => Boolean(this.fileEntries?.length),
        rows: [
          // The walk leads the scope, so the command reference lists it first: moving
          // is what a user on a diff row does next, where "filter files" is
          // the press for someone who has not started reading yet.
          //
          // `]` and `[` are the reviewer's own step, and `}` and `{` the same step one
          // unit out. Bracket pairs because that is what an editor and a review tool
          // already spell this walk with, and punctuation spends none of the page's
          // small alphabet: these live in the diff's own scope and answer only while
          // the user is in it.
          {
            id: "diff.next-hunk",
            keys: ["]"],
            title: "next hunk",
            travels: true,
            when: () => this.hasHunks(),
            run: () => this.present(this.stepHunk(false)),
          },
          {
            id: "diff.previous-hunk",
            keys: ["["],
            title: "previous hunk",
            travels: true,
            when: () => this.hasHunks(),
            run: () => this.present(this.stepHunk(true)),
          },
          {
            id: "diff.next-file",
            keys: ["}"],
            title: "next file",
            travels: true,
            when: () => this.navigationEntries().length > 1,
            run: () => this.present(this.stepFile(false)),
          },
          {
            id: "diff.previous-file",
            keys: ["{"],
            title: "previous file",
            travels: true,
            when: () => this.navigationEntries().length > 1,
            run: () => this.present(this.stepFile(true)),
          },
          {
            id: "diff.search",
            keys: ["/"],
            title: "filter files",
            when: () => Boolean(this.diffTools),
            run: () => {
              const search = this.diffTools?.search;
              if (search) {
                focusDestination(search, "move");
                scrollIntoView(search, { block: "nearest" });
              }
            },
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
              const root = /** @type {Document | ShadowRoot} */ (this.getRootNode());
              // The box holds its expand-all control, which counts as in the box.
              return (
                this.contains(root.activeElement) &&
                Boolean(
                  search.value ||
                  search.contains(this.shadowRoot?.activeElement ?? null),
                )
              );
            },
            title: () =>
              this.diffTools?.search.value ? "show all files" : "leave filter",
            run: () => {
              const search = this.diffTools?.search;
              if (search?.value) {
                this.clearFilter();
                focusDestination(search, "return");
                return;
              }
              // The box's container is the patch it filters, so that is where it hands
              // the user back: a blur alone would drop them out of this widget's
              // scope with no ring anywhere, and the file walk would stop answering.
              focusDestination(this, "return");
            },
          },
        ],
      };
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
      this.authorNotes = [...this.querySelectorAll(":scope > lf-diff-note")];
      this.unplacedNotes = document.createElement("div");
      whileConnected(this, () => {
        // A page diff's file header pins at `--lf-top`, the top of the page's box that
        // scrolls it; one an agent sent in a reply scrolls inside the panel's own list,
        // which declares no such edge. The theme cannot ask that question from inside a shadow tree, so
        // the module answers it once from the chrome's own mark and paints the answer.
        this.toggleAttribute("data-lf-diff-pinned", !closestAcross(this, ".lf-chrome"));
        return () => {
          this.rendering = this.rendering + 1;
          if (this.#showing) this.#shown = undefined;
          // Leaf retires this surface when it leaves, after this cleanup, and puts
          // core's views back, so every outlet goes.
          for (const record of this.threadSeats.values()) record.active = false;
          this.retireThreadOutlets();
          this.threadSeats.clear();
        };
      });
    }

    render() {
      this.#delivered = this.#source();
      // Drawn files offer Comment while a surface is registered; reading the opener
      // here draws again when it changes, and `updated` reconciles the controls.
      void threadSurface(this).open;
      return nothing;
    }

    // A patch renders each source once, after the draw that read it, whose
    // `updateComplete` waits for the rendering.
    /** @param {import("lit").PropertyValues} changed */
    updated(changed) {
      super.updated(changed);
      for (const entry of this.fileEntries ?? []) this.reconcileEntryComments(entry);
      if (this.#delivered === this.#shown) return;
      this.#rendered = undefined;
      this.#shown = this.#delivered;
      this.#showing = true;
      const rendering = this.show(this.#delivered);
      this.sourceRendering = rendering;
      this.#rendered = rendering.finally(() => {
        if (this.sourceRendering === rendering) {
          this.#showing = false;
          // Preparation may finish before the arrival batch reports departure.
          if (!this.isConnected) this.#shown = undefined;
        }
      });
    }

    // Also waits for the drawing the latest update started: a newer update's drawing
    // replaces one still pending.
    async getUpdateComplete() {
      const result = await super.getUpdateComplete();
      await this.#rendered;
      return result;
    }

    // `source` is a patch text, a file manifest or two compared texts, or null when a
    // bound source has none.
    /** @param {DiffSource | null | undefined} source */
    async show(source) {
      const rendering = this.rendering + 1;
      this.rendering = rendering;
      try {
        if (source == null) {
          threadSurface(this).release(this);
          this.committed = null;
          this.publishFiles();
          this.diffTools = null;
          this.filesBody = null;
          this.placeNotes();
          shadowStage(this, [this.unplacedNotes]);
          this.markFiles(source);
          this.classList.toggle("lf-rendered", false);
          return;
        }
        const records = await sourceRecords(source);
        // Navigation is mechanical and can move while source evidence prepares.
        // Each pass reads the latest surviving selection; preparation never owns it.
        const currentPath = () =>
          records.some((record) => record.path === this.activePath)
            ? this.activePath
            : records[0]?.path;
        const prior = new Map(
          (this.fileEntries ?? []).map((entry) => [entry.record.path, entry]),
        );
        const open = !this.hasAttribute("collapsed");
        /** @type {{record: FileSummary, evidence: SourceRecord, previous: FileEntry | undefined, prepared: EntryPreparation | null}[]} */
        const plans = records.map((evidence) => ({
          record: "file" in evidence ? evidence.file.record : { path: evidence.path },
          evidence,
          previous: prior.get(evidence.path),
          prepared: "error" in evidence ? evidence : null,
        }));
        // Every row's evidence is judged before its metadata commits. Only open files
        // need the textual renderer; closed files retain their one parsed reading.
        // Open evidence is prepared without changing the current entries or their native
        // outlets. A disclosure opened while another file loads joins this same commit.
        for (;;) {
          if (rendering !== this.rendering || !this.isConnected) return;
          const activePath = currentPath();
          const pending = plans.filter(
            ({ record, previous, prepared }) =>
              !prepared &&
              (record.hunkCount === 0 ||
                (this.singleFile
                  ? record.path === activePath
                  : (previous?.details?.open ?? open))),
          );
          if (!pending.length) break;
          await Promise.all(
            pending.map(async (plan) => {
              plan.prepared = await this.prepareEntry(
                plan.evidence,
                plan.previous?.details ? plan.previous.renderKey : null,
              );
            }),
          );
        }
        const activePath = currentPath();
        /** @type {FileEntry[]} */
        const fresh = [];
        /** @type {((() => unknown) | null)[]} */
        const restores = [];
        const resume = this.defer();
        // Where the user was in a file this source drops, as the last change's Revert
        // drops the only file, they land on the diff itself (below).
        const kept = this.filesBody && holdFocus(this.filesBody);
        try {
          const entries = plans.map(({ record, evidence, previous, prepared }) => {
            const metadata =
              record.hunkCount === 0 && !(prepared && "error" in prepared);
            const entry = (() => {
              const retain =
                previous &&
                (metadata
                  ? previous.kind === "metadata" &&
                    JSON.stringify(previous.record) === JSON.stringify(record)
                  : previous.kind === "text");
              if (retain) return previous;
              const view = metadata
                ? metadataNode(record)
                : summaryNode(
                    record,
                    Boolean(prepared && "error" in prepared) ||
                      record.hunkCount === 0 ||
                      (this.singleFile ? record.path === activePath : open),
                    !(prepared && "error" in prepared),
                  );
              if (previous) {
                restores.push(replaceFileRendering(previous, view));
                return previous;
              }
              const entry = fileEntry(view, record, evidence);
              fresh.push(entry);
              return entry;
            })();
            Object.assign(entry, {
              record,
              source: evidence,
              loaded: entry.kind === "metadata",
              refused: false,
              loading: null,
            });
            keeps(entry.node, "data-lf-gen", "1");
            if (entry.kind === "metadata") {
              entry.rendered = null;
              entry.renderKey = null;
              return entry;
            }
            if (prepared) restores.push(this.applyEntry(entry, prepared));
            else {
              paintSummary(entry, record);
              entry.details.querySelector("pre")?.toggleAttribute("hidden", true);
              paintFileDetails(entry, record);
            }
            return entry;
          });
          this.committed = { source, entries };
          this.activePath = activePath;
          if (this.singleFile || entries.length < 2) this.diffTools = null;
          else this.diffTools ??= diffTools(this);
          for (const entry of fresh) this.attachEntryControls(entry);
          for (const entry of entries) this.reconcileEntryComments(entry);
          for (const entry of entries) this.attachDisclosure(entry);
          this.filesBody ??= diffBody([]);
          // A file the patch dropped goes with its outlets, which core's composer leaves first.
          for (const entry of prior.values())
            if (!entries.includes(entry)) {
              for (const note of this.authorNotes)
                if (entry.node.contains(note)) move(this.unplacedNotes, note, null);
              threadSurface(this).release(entry.node);
            }
          // Two compared texts that are the same have no files, and say so where the
          // files would stand.
          setChildren(
            this.filesBody,
            entries.length
              ? [
                  ...(this.diffTools ? [this.diffTools.search] : []),
                  ...entries.map(({ node }) => node),
                ]
              : [offer("p", "lf-rows-empty", "No changes.")],
          );
          this.markRuns();
          this.stageFiles();
          this.markFiles(source);
          this.classList.toggle("lf-rendered", true);
          this.filterFiles(this.diffTools?.search.value ?? "");
          this.publishFiles();
          for (const restore of restores) restore?.();
          kept?.(this);
        } finally {
          resume();
        }
      } catch (err) {
        if (rendering !== this.rendering || !this.isConnected) return;
        this.committed = null;
        this.publishFiles();
        this.diffTools = null;
        this.filesBody = null;
        this.classList.toggle("lf-rendered", false);
        // The failure box quotes a patch text; a manifest or two compared texts have
        // none to quote. It takes the place of every outlet, which core's composer
        // leaves first. It stands as the shadow stage, as files do, so it lasts until
        // the next `show` stages another rendering; an update that leaves the source
        // unchanged keeps it.
        threadSurface(this).release(this);
        shadowStage(this, []);
        failSoft(this, err, typeof source === "string" ? source : undefined);
        this.markFiles(source);
      }
    }

    // The inventory belongs to this parse, rather than to any particular navigator.
    // Keys are opaque addresses in this widget's existing datum space; consumers
    // neither parse patches nor know how a diff encodes a file identity.
    publishFiles() {
      /** @param {FileSummary["operation"]} operation */
      const status = (operation) =>
        operation === "add"
          ? "added"
          : operation === "delete"
            ? "deleted"
            : operation === "modify"
              ? "modified"
              : operation === "rename"
                ? "renamed"
                : null;
      // The `files` output: held here, and `change` says it moved.
      this.files = this.fileEntries
        ? {
            ...(this.singleFile ? { current: this.activePath } : {}),
            files: this.fileEntries.map(({ record }) => ({
              path: record.path,
              key: diffDatumKey({ path: record.path, file: true }),
              ...(status(record.operation) ? { status: status(record.operation) } : {}),
            })),
          }
        : null;
      this.dispatchEvent(new Event("change"));
    }

    /** @param {SourceRecord} source @param {string | null | undefined} renderKey @returns {Promise<EntryPreparation>} */
    async prepareEntry(source, renderKey) {
      if ("error" in source) return source;
      try {
        const { file } = source;
        const overflow = overflowFor(file.name, this.getAttribute("overflow"));
        const nextKey = JSON.stringify([file, overflow]);
        const rendered =
          !file.hunks.length || renderKey === nextKey
            ? null
            : await renderFile(file, overflow);
        return { file, renderKey: nextKey, rendered };
      } catch (error) {
        return { error };
      }
    }

    stageFiles() {
      if (!this.filesBody) return;
      this.placeNotes();
      shadowStage(this, [this.filesBody, this.unplacedNotes]);
    }

    // Authored nodes survive source replacement and lazy loading. A closed file
    // keeps its notes in its disclosure until its source rows exist. Missing
    // coordinates remain readable at the file's foot (or the diff's foot when the
    // file itself vanished), with the address that could not be placed.
    placeNotes() {
      const after = new Map();
      for (const note of this.authorNotes) {
        const file = note.getAttribute("file"),
          side = note.getAttribute("side");
        const coordinate =
          file !== null && side !== null
            ? readDiffCoordinate(
                diffLocationKey(file, side, Number(note.getAttribute("at"))),
              )
            : null;
        const entry = findDiffFile(this.fileEntries, coordinate);
        const line =
          entry?.loaded && findDiffLine(entry.rendered?.lines ?? [], coordinate);
        const unmatched = !entry || (entry.loaded && !line);
        keeps(
          note,
          "data-lf-unmatched",
          unmatched
            ? `${note.getAttribute("file")} · ${note.getAttribute("side")} ${note.getAttribute("at")} — line unavailable`
            : null,
        );
        if (line) {
          const row = line.row;
          const previous = after.get(row) ?? row;
          if (entry.rendered) move(entry.rendered.rows, note, previous.nextSibling);
          after.set(row, note);
        } else {
          move(entry?.details ?? this.unplacedNotes, note, null);
        }
      }
    }

    // Marks each drawn file row, and each line of a loaded file, as data drawn from
    // `source`, and reports it. A manifest names the field each datum came from; a
    // patch text's datums take the whole delivery's origin, and an inline patch has no
    // delivery. Two compared texts report the `afterText` they drew, since a widget's
    // marks carry one input's origin: the current text is the one each edit moves, so a
    // comment on a row records the save it saw. A deleted row's words are the earlier
    // text's, which that origin leaves unnamed.
    /** @param {DiffSource | null | undefined} source */
    markFiles(source) {
      const compared =
        typeof source === "object" && source !== null && "after" in source;
      const manifest =
        typeof source === "object" && source !== null && "files" in source;
      /** @type {Set<Element>} */
      const marked = new Set();
      for (const [index, entry] of (this.fileEntries ?? []).entries()) {
        const file = fileDatum(entry);
        mark(file, manifest ? ["files", index, "path"] : null);
        marked.add(file.node);
        if (entry.loaded)
          for (const line of entry.rendered?.lines ?? []) {
            mark(line, manifest ? ["files", index, "patch"] : null);
            marked.add(line.node);
          }
      }
      for (const node of this.#marked) if (!marked.has(node)) unmark(node);
      this.#marked = marked;
      this.dispatchEvent(
        new CustomEvent("drawn", {
          detail: compared ? { afterText: source.after } : { value: source },
        }),
      );
    }

    // The widget's thread surface: Leaf asks for one outlet, or null, per target it hands over, and
    // the outlets this placement no longer uses come down once it commits.
    /** @param {readonly import("/runtime/records/thread/surfaces.js").OutletTarget[]} targets @param {import("/runtime/records/thread/surfaces.js").OutletContext} context */
    threadOutlets(targets, { onCommit }) {
      this.beginThreadSurface();
      const outlets = targets.map((target) => this.threadOutletFor(target));
      this.markRuns();
      onCommit(() => this.retireThreadOutlets());
      return outlets;
    }

    // One outlet per datum, kept beside its datum's drawn node for as long as the thread
    // surface returns it. One the surface stops returning still holds the composer or
    // a thread view core placed there, until that placement commits; only then does it
    // come down, so the user's editor never leaves the document with it.
    beginThreadSurface() {
      for (const record of this.threadSeats.values()) record.active = false;
    }

    /** @param {import("/runtime/records/thread/surfaces.js").OutletTarget} target */
    threadOutletFor({ anchor, placement }) {
      // A thread about the diff as a whole names no datum, and stays in the margin.
      if (!anchor.datum) return null;
      const coordinate = readDiffCoordinate(anchor.datum);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!coordinate || !entry || entry.filtered) return null;
      const file = coordinate.file;
      const drawing = entry.rendered;
      const line = file
        ? undefined
        : drawing?.lines.find((line) => diffDatumKey(line) === anchor.datum);
      let parent = entry.node;
      /** @type {ChildNode | null} */
      let before = null;
      if (file) {
        if (placement.datumElement !== fileNode(entry)) return null;
      } else {
        if (
          !entry.loaded ||
          !drawing ||
          !line ||
          (entry.details && !entry.details.open) ||
          placement.datumElement !== line.node
        )
          return null;
        parent = drawing.rows;
        before = line.row.nextSibling;
      }
      const row = placement.datumElement;
      let record = this.threadSeats.get(anchor.datum);
      if (!record) {
        const outlet = document.createElement("section");
        outlet.className = `lf-diff-thread-outlet lf-ui${
          file ? " lf-diff-file-thread-outlet" : ""
        }`;
        keeps(outlet, "data-lf-gen", "1");
        outlet.dataset.lfThreadDatum = anchor.datum;
        outlet.setAttribute(
          "aria-label",
          `Thread on ${row.getAttribute("data-lf-datum-label") || (file ? "file" : "diff line")}`,
        );
        record = { outlet, row: null, active: false };
        this.threadSeats.set(anchor.datum, record);
      }
      // A datum drawn anew takes its outlet along, which keeps whoever stands in it.
      if (record.row !== row) {
        move(parent, record.outlet, before);
        record.row = row;
      }
      record.active = true;
      return record.outlet;
    }

    // Take down the outlets the committed placement no longer uses.
    retireThreadOutlets() {
      for (const [key, record] of this.threadSeats) {
        if (record.active) continue;
        record.outlet.remove();
        this.threadSeats.delete(key);
      }
      this.markRuns();
    }

    /** @param {FileEntry} entry */
    async loadEntry(entry) {
      for (;;) {
        const rendering = this.sourceRendering;
        await rendering;
        if (!this.isConnected) return;
        if (rendering === this.sourceRendering) break;
      }
      const committed = this.committed;
      if (!committed?.entries.includes(entry)) return;
      if (entry.kind !== "text" || entry.loaded || entry.refused) return;
      // A disconnect abandons a load, and the entry stays loadable: an inline patch
      // keeps its entries across a reconnection, so a later open starts afresh.
      if (entry.loading?.rendering === this.rendering) return entry.loading.promise;
      const rendering = this.rendering;
      const promise = (async () => {
        const prepared = await this.prepareEntry(entry.source, entry.renderKey);
        if (rendering !== this.rendering || !this.isConnected) return;
        await this.commitLoaded(entry, prepared, rendering);
      })();
      entry.loading = { rendering, promise };
      return promise;
    }

    // Files whose loads finish before the next frame commit together in it. A commit
    // lays out, stages and projects every loaded file, so a commit per file made
    // opening many at once, as Expand all does, quadratic in their number; a commit
    // per frame still shows each file in the frame after it is ready.
    /** @param {TextEntry} entry @param {EntryPreparation} prepared @param {number} rendering */
    commitLoaded(entry, prepared, rendering) {
      const queue = (this.loadedQueue ??= new Map());
      queue.set(entry, { prepared, rendering });
      this.loadedCommit ??= new Promise((resolve, reject) =>
        nextRender(() => {
          this.loadedQueue = null;
          this.loadedCommit = null;
          try {
            const ready = [...queue].filter(
              ([entry, load]) =>
                load.rendering === this.rendering &&
                this.isConnected &&
                this.fileEntries?.includes(entry),
            );
            for (const [entry] of ready) entry.loading = null;
            const restores = ready.map(([entry, { prepared }]) =>
              this.applyEntry(entry, prepared),
            );
            if (ready.length) {
              this.markRuns();
              this.stageFiles();
              this.markFiles(this.drawnSource);
            }
            for (const restore of restores) restore?.();
            resolve(undefined);
          } catch (error) {
            reject(error);
          }
        }),
      );
      return this.loadedCommit;
    }

    // Returns the focus restore for the caller to run once the file's evidence is staged.
    /** @param {TextEntry} entry @param {EntryPreparation} prepared */
    applyEntry(entry, prepared) {
      if ("error" in prepared) {
        // Nothing loads a patch this widget refused again.
        entry.refused = true;
        paintSummary(entry, entry.record, false);
        paintFileDetails(entry, {});
        if (!entry.details.open) entry.details.open = true;
        if (entry.disclosure) entry.disclosure.open = true;
        this.dispatchEvent(
          new ErrorEvent("error", {
            error: prepared.error,
            bubbles: true,
            composed: true,
          }),
        );
        entry.rendered = null;
        entry.renderKey = null;
        fileError(entry, prepared.error, threadSurface(this));
        return null;
      }
      const { file, renderKey, rendered } = prepared;
      entry.record = file.record;
      paintSummary(entry, entry.record);
      if (entry.record.hunkCount === 0) {
        const restore = replaceFileRendering(entry, metadataNode(entry.record));
        entry.loaded = true;
        this.attachDisclosure(entry);
        return restore;
      }
      const restore = rendered && replaceFileContent(entry, rendered, this.threadSeats);
      entry.renderKey = renderKey;
      entry.loaded = true;
      entry.details.querySelector("pre")?.toggleAttribute("hidden", false);
      paintFileDetails(entry, entry.record);
      this.reconcileEntryComments(entry);
      return restore;
    }

    // Core can place an existing line thread at its file disclosure before that file's
    // patch exists in the DOM. Navigation asks the second method to make the exact line
    // real, then the ordinary datum resolver and anchor painter take over.
    /** @param {string} key */
    lfDataDatum(key, { outdated = false } = {}) {
      const coordinate = readDiffCoordinate(key);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!coordinate || !entry) return null;
      if (coordinate.file) return fileNode(entry);
      if (outdated) return entry.node;
      if (!entry.loaded || entry.filtered) return entry.node;
      const line = findDiffLine(entry.rendered?.lines ?? [], coordinate);
      return line?.node ?? null;
    }

    // A file navigation opens its evidence from the beginning. Its comment datum
    // stays on the header, which can remain visible while stuck over later lines.
    /** @param {string} key @returns {Element[]} */
    lfElementsFor(key) {
      const coordinate = readDiffCoordinate(key);
      const node = coordinate?.file
        ? findDiffFile(this.fileEntries, coordinate)?.node
        : this.lfDataDatum(key);
      return node ? [node] : [];
    }

    // A datum's label is its coordinate's, so a thread on a line of a file not yet
    // loaded is named as the drawn line will be.
    /** @param {string} key */
    lfDatumLabel(key) {
      const coordinate = readDiffCoordinate(key);
      if (!coordinate || coordinate.source) return null;
      return coordinate.file ? fileLabel(coordinate) : lineLabel(coordinate);
    }

    /** @param {string} key */
    lfRevealDatum(key) {
      const coordinate = readDiffCoordinate(key);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!entry) return null;
      // Leaf can ask again for a part it has shown, so each step does nothing once done.
      if (this.singleFile && this.activePath !== entry.record.path)
        this.selectFile(entry);
      else if (!this.singleFile && entry.filtered) this.clearFilter();
      if (!entry.details) return null;
      if (!entry.details.open) entry.details.open = true;
      if (entry.loaded || entry.refused) return null;
      return this.loadEntry(entry);
    }

    /** @param {FileEntry} entry */
    attachDisclosure(entry) {
      const previous = entry.disclosure,
        details = entry.details;
      if (previous?.node === details) return;
      if (previous) previous.node.removeEventListener("toggle", previous.changed);
      entry.disclosure = null;
      if (!details) return;
      const disclosure = {
        node: details,
        open: details.open,
        changed: () => {
          if (this.settleDisclosure(entry)) this.layoutChanged();
          this.paintFoldAll();
        },
      };
      entry.disclosure = disclosure;
      details.addEventListener("toggle", disclosure.changed);
    }

    // A file drawn open fires `toggle` though nothing changed, so only a change of the
    // open state counts. Returns whether it changed; a file that opens loads its patch.
    /** @param {FileEntry} entry */
    settleDisclosure(entry) {
      const disclosure = entry.disclosure;
      if (!disclosure || disclosure.open === disclosure.node.open) return false;
      disclosure.open = disclosure.node.open;
      if (disclosure.open && this.fileEntries?.includes(entry) && !entry.refused)
        this.present(this.loadEntry(entry));
      return true;
    }

    // A closed file seats no thread on its lines, so Leaf asks for the seats again.
    layoutChanged() {
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
    }

    /** @param {FileEntry} entry */
    attachEntryControls(entry) {
      entry.node.addEventListener("click", (event) => {
        const target = event.target;
        const revert =
          target instanceof Element ? target.closest(".lf-diff-revert") : null;
        if (revert) this.revert(entry, revert);
        const button =
          target instanceof Element ? target.closest(".lf-diff-line-comment") : null;
        const line = button?.nextElementSibling;
        if (line) threadSurface(this).open?.(line);
      });
      entry.node.addEventListener("beforematch", () => {
        if (this.singleFile) this.selectFile(entry);
        else this.clearFilter();
      });
    }

    // A surface owns whether Comment is available. Its registration can arrive after
    // the evidence, or leave while the same value remains, so this updates retained
    // affordances independently of parsing and preserves the source rows themselves.
    /** @param {FileEntry} entry */
    reconcileEntryComments(entry) {
      const opener = threadSurface(this).open;
      const fileComment = entry.actions.querySelector(".lf-diff-file-comment");
      if (opener && !fileComment) {
        entry.actions.prepend(
          commentButton(
            entry.record.path || "file",
            () => threadSurface(this).open?.(fileNode(entry)),
            "lf-diff-file-comment",
          ),
        );
      } else if (!opener && fileComment) {
        const restore = holdFocus(fileComment);
        fileComment.remove();
        restore?.(entry.header);
      }
      const heads = new Set(
        this.reverting() ? changeHeads(entry).map(({ row }) => row) : [],
      );
      for (const line of entry.rendered?.lines ?? []) {
        const revert = line.row.querySelector(":scope > .lf-diff-revert");
        if (revert && !heads.has(line.row)) {
          const restore = holdFocus(revert);
          revert.remove();
          restore?.(line.node);
        } else if (!revert && heads.has(line.row)) revertButton(line);
        const previous = line.row.firstElementChild;
        if (!previous || (previous.localName === "button") === Boolean(opener))
          continue;
        const restore = holdFocus(previous);
        const number = lineNumber(line, Boolean(opener));
        previous.replaceWith(number);
        restore?.(number);
      }
    }

    // Whether the texts drawn take a Revert: two compared texts, the current one bound
    // by `for` from a widget holding it with a `revision`.
    reverting() {
      const source = this.drawnSource;
      return Boolean(
        this.hasAttribute("for") &&
        typeof source === "object" &&
        source &&
        "after" in source &&
        typeof source.after === "object" &&
        source.after.revision,
      );
    }

    // Ask the widget `for` names to hold its text with the change `button` stands on
    // taken back (the header says how), from a button made off the page, since this
    // one stands in the diff's shadow tree. Its words name the gesture.
    /** @param {FileEntry} entry @param {Element} button */
    revert(entry, button) {
      const comparison = this.drawnSource;
      const line = entry.rendered?.lines.find(({ row }) => row.contains(button));
      const id = this.getAttribute("for");
      if (!line || !id || typeof comparison !== "object" || !comparison) return;
      if (!("after" in comparison)) return;
      const { after } = comparison;
      if (typeof after !== "object" || !after.revision) return;
      const root = /** @type {Document | ShadowRoot} */ (this.getRootNode());
      const { change } = line;
      if (change === undefined) return;
      void parse().then((parser) => {
        const reverted = revertedText(parser, comparison, change);
        const taken =
          reverted &&
          root.getElementById(id)?.dispatchEvent(
            new CommandEvent("command", {
              command: "--replace",
              source: Object.assign(document.createElement("button"), {
                value: JSON.stringify({
                  text: reverted.text,
                  revision: after.revision,
                }),
                textContent: `Reverted the change at line ${reverted.line}`,
              }),
              cancelable: true,
            }),
          );
        if (!reverted || !taken)
          window.dispatchEvent(
            new CustomEvent("lf-error", {
              detail: "Not reverted: the text stays as it is.",
            }),
          );
        else if (after.key) location.assign(`#${id}:${after.key}:${reverted.line}`);
        // Staying here, the user stands on the change's row, and the redraw that takes
        // the change away hands them to the nearest row that stays, as `]` lands.
        else if (this.shadowRoot?.activeElement === button)
          focusDestination(line.node, "move");
      });
    }

    /** @param {PromiseLike<unknown>} promise */
    present(promise) {
      this.dispatchEvent(new PendingTaskEvent(promise));
      return promise;
    }

    /** @param {string | null} query */
    filterFiles(query) {
      const needle = query?.trim().toLocaleLowerCase() ?? "";
      // A query narrows the files without pulling up what the window shows: while it
      // applies, the body keeps the height it reached on screen, down to the window's
      // foot. What follows the diff in view stays put, and near the page's end the
      // scroll cannot clamp the field out from under the caret; the room held is at
      // most one window, below the files that match. Clearing the query lets go.
      if (this.filesBody) {
        const { top, height } = this.filesBody.getBoundingClientRect();
        const hold = needle
          ? layoutPx(Math.max(0, Math.min(height, innerHeight - top)))
          : "";
        if (this.filesBody.style.minBlockSize !== hold)
          this.filesBody.style.minBlockSize = hold;
      }
      for (const entry of this.fileEntries ?? []) {
        const paths = [entry.record.path, entry.record.previousPath ?? ""]
          .join("\n")
          .toLocaleLowerCase();
        entry.filtered = this.singleFile
          ? entry.record.path !== this.activePath
          : Boolean(needle && !paths.includes(needle));
        // A file the filter leaves out is hidden until found, so the browser's find
        // and Leaf's travel to a passage in it show it again (`beforematch`).
        keeps(entry.node, "hidden", entry.filtered ? "until-found" : null);
      }
      this.markRuns();
      this.refreshDiffTools();
      this.layoutChanged();
    }

    // The file view keeps every datum under its retained owner; only the active
    // file is visible. A thread or any navigator can reveal another through the
    // same datum route, without knowing which presentation the page chose.
    /** @param {FileEntry} entry */
    selectFile(entry) {
      this.activePath = entry.record.path;
      this.filterFiles("");
      this.publishFiles();
    }

    // The files the filter shows are drawn as one bordered list, which a file's own
    // conversations break: they hang under that file in a box of their own, so the list
    // runs on from the next file the filter shows (widget-shadow.css). Only this pass knows
    // which file that is, since CSS reads a file's sibling before it, which may be
    // hidden, and not the nearest shown one. It runs whenever the shown files or a
    // file's conversations change: on filtering, and on each outlet layout.
    markRuns() {
      const shown = this.fileEntries?.filter((entry) => !entry.filtered) ?? [];
      const talks = (/** @type {FileEntry | undefined} */ entry) =>
        entry?.node.querySelector(":scope > .lf-diff-file-thread-outlet") != null;
      shown.forEach((entry, index) => {
        const { classList } = entry.node;
        classList.toggle("lf-diff-run-start", index === 0 || talks(shown[index - 1]));
        classList.toggle("lf-diff-run-end", index === shown.length - 1 || talks(entry));
      });
    }

    clearFilter() {
      if (this.diffTools) this.diffTools.search.value = "";
      this.filterFiles("");
    }

    refreshDiffTools() {
      if (!this.diffTools || !this.fileEntries) return;
      const shown = this.fileEntries.filter((entry) => !entry.filtered);
      const total = this.fileEntries.length;
      const all = `${total} file${total === 1 ? "" : "s"}`;
      const matching = `${shown.length} of ${total}`;
      // Filtering changes the count inside its room, never its containing field.
      keeps(this.diffTools.progress, "data-lf-room", `${all}\n${total} of ${total}`);
      keepsText(this.diffTools.count, shown.length === total ? all : matching);
      this.paintFoldAll();
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    // The files the filter shows: all opened while any is closed, and all closed once
    // every one is open, so the press does what its face says.
    foldAll() {
      const folds = this.shownFolds();
      const open = folds.some((details) => !details.open);
      for (const details of folds) if (details.open !== open) details.open = open;
      // Each file's `toggle` arrives in a task of its own and would ask for a pass of
      // its own, so the press settles every file now and asks for one.
      let changed = false;
      for (const entry of this.shownEntries())
        changed = this.settleDisclosure(entry) || changed;
      if (changed) this.layoutChanged();
      this.paintFoldAll();
      window.dispatchEvent(
        new CustomEvent("lf-announce", {
          detail: `${open ? "Expanded" : "Collapsed"} all files`,
        }),
      );
    }

    paintFoldAll() {
      const button = this.diffTools?.foldAll;
      if (!button) return;
      const folds = this.shownFolds();
      // With nothing to open it keeps its room, so the count beside it stays put.
      button.toggleAttribute("inert", !folds.length);
      const open = folds.some((details) => !details.open);
      // No number: the count beside it also counts files that have nothing to open.
      nameAction(button, open ? "expand-all" : "collapse-all", {
        label: `${open ? "Expand" : "Collapse"} all files`,
      });
    }

    shownFolds() {
      return this.shownEntries().flatMap(({ details }) => (details ? [details] : []));
    }

    shownEntries() {
      return (this.fileEntries ?? []).filter((entry) => !entry.filtered);
    }

    navigationEntries() {
      return this.singleFile ? (this.fileEntries ?? []) : this.shownEntries();
    }

    hasHunks() {
      return this.shownEntries().some((entry) => entry.details);
    }

    // Where the user is inside this diff. A row, a header, or a control in the
    // tools row all answer; the walk only needs a node to compare document positions
    // against, and the tools row standing before every file is why a user who has
    // touched nothing steps to the first hunk rather than nowhere.
    hereNode() {
      return this.shadowRoot?.activeElement ?? null;
    }

    // With nothing focused inside the shadow tree — the host itself is focused, which
    // is where an in-page link to the diff's id lands — every hunk counts as beyond, in
    // either direction: `order` is already reversed for a backward step, so the walk
    // opens the last file and lands on its last hunk, the mirror of the first hunk
    // forward. Answering false there matched no hunk in any file, and the walk opened
    // and fetched every one of them to land nowhere.
    /** @param {Node} node @param {Node | null} here @param {boolean} back */
    beyond(node, here, back) {
      if (!here) return true;
      const where = here.compareDocumentPosition(node);
      return Boolean(
        where &
        (back ? Node.DOCUMENT_POSITION_PRECEDING : Node.DOCUMENT_POSITION_FOLLOWING),
      );
    }

    // Where a step along a file's hunks or the diff's files landed, said for Leaf's
    // panel on the stop it landed on (`lf-walk`, module-input.md, "Walks"): each is a
    // list on screen, which its first and last stops bound. Returns the place a listener
    // hears, "Hunk 2 of 5", before the file it is in. A step with nowhere further to go
    // says the stop the user is still on, and none where they stand on no stop of the
    // list.
    /** @param {string} noun @param {readonly Element[]} stops @param {Element | null | undefined} stop */
    sayStep(noun, stops, stop) {
      const position = stop ? stops.indexOf(stop) + 1 : 0;
      if (!stop || !position) return null;
      const total = stops.length;
      stop.dispatchEvent(
        new CustomEvent("lf-walk", {
          bubbles: true,
          composed: true,
          detail: { noun, position, total, list: [stops[0], stops.at(-1)] },
        }),
      );
      return `${noun} ${position} of ${total}`;
    }

    /** @param {FileEntry} entry */
    async openEntry(entry) {
      if (!entry.details) return;
      if (!entry.details.open) entry.details.open = true;
      await this.loadEntry(entry);
    }

    // The walk starts in the file the user is in and goes on through the
    // ones after it, so a closed file is opened only once the step has actually reached
    // it: a user on the last hunk of the third file loads the fourth and stops, rather
    // than every remaining file to discover there is nothing past them.
    // Opening a file waits on its rendering, and the user may have moved on by then:
    // both walks capture the pressing gesture's intent first and land only while it stands.
    /** @param {boolean} back */
    async stepHunk(back) {
      const mayLand = retainUserIntent();
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      const currentLocation = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      for (const entry of order.slice(Math.max(currentLocation, 0))) {
        await this.openEntry(entry);
        if (!mayLand()) return;
        const heads = hunkHeads(entry);
        const head = (back ? [...heads].reverse() : heads).find((line) =>
          this.beyond(line.node, here, back),
        );
        if (!head) continue;
        this.land(head.node);
        const said = this.sayStep("Hunk", heads.map(nodeOf), head.node);
        window.dispatchEvent(
          new CustomEvent("lf-announce", { detail: `${said}: ${entry.record.path}` }),
        );
        return;
      }
      const around = this.entryAroundFocus();
      this.sayStep(
        "Hunk",
        around ? hunkHeads(around).map(nodeOf) : [],
        this.hereNode(),
      );
    }

    /** @param {boolean} back */
    async stepFile(back) {
      const mayLand = retainUserIntent();
      const here = this.hereNode();
      const entries = this.navigationEntries();
      const order = back ? [...entries].reverse() : entries;
      // The whole file is the unit, so a step out of one starts past it rather than at
      // its own header — and a user in the tools row, which belongs to no
      // file, steps to the first (or, walking back, the last).
      const currentLocation = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      const entry = order[currentLocation + 1];
      const files = entries.map(nodeOf);
      if (!entry) return this.sayStep("File", files, this.entryAroundFocus()?.node);
      this.fileCursor = entry;
      if (this.singleFile) {
        this.selectFile(entry);
        await this.openEntry(entry);
        if (!mayLand()) return;
      }
      // The box rather than the header, which is what the generated fold target settled for
      // the same shape: a header pinned to the window's top is already where it is going, so
      // aligning it moves nothing, while aligning the file it heads starts the file at
      // its start. The header is still what takes the focus.
      this.land(entry.node, entry.details?.firstElementChild ?? entry.node);
      const said = this.sayStep("File", files, entry.node);
      window.dispatchEvent(
        new CustomEvent("lf-announce", { detail: `${said}: ${entry.record.path}` }),
      );
    }

    // Arrival: scrolled to the band the document declares landable, which the pinned
    // header's own room has been added to, and then the focus without the browser
    // scrolling a second time. A row is not a tab stop — a patch is thousands of them —
    // so it is made focusable for the press that lands on it, and wears the band inset
    // inside its own box (widget-shadow.css). A file header
    // already is one, and writing a tabindex of -1 onto it would take it out of the
    // order a user tabs through.
    //
    // The landing moves only vertically, including through the shadow host, so neither
    // the file nor a region around it loses its sideways place.
    /** @param {Element} box @param {Element} [node] */
    land(box, node = box) {
      scrollIntoView(box, { block: "start", behavior: "smooth", sideways: false });
      focusDestination(node, "move");
    }

    entryAroundFocus() {
      const here = this.hereNode();
      const focusedEntry =
        this.fileEntries?.find(({ node }) => here && node.contains(here)) ?? null;
      if (focusedEntry) return focusedEntry;
      return this.fileCursor && this.fileEntries?.includes(this.fileCursor)
        ? this.fileCursor
        : null;
    }
  },
);
