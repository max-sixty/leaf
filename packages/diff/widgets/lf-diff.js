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
 * Every source form, an inline or bound patch text or a file manifest, becomes one list
 * of per-file records and renders through one path (`sourceRecords`), so a closed file
 * renders only when it opens, whichever form supplied it; the alternative, a second
 * pipeline for patch text that rendered every file eagerly, drifted from the manifest's
 * on every fix. A source's evidence commits together after open files load. Lazy
 * disclosure joins the pending source render before reading its evidence, and a closed file shows
 * none of the previous revision while it loads current evidence. Line conversations
 * follow the visible reader width while source lines may scroll horizontally. The
 * browser sizes those conversations from the reader container. Each source row owns
 * its gutter control; ordinary block flow places conversations between rows. Passage reveal
 * clears this widget's file filter; addressed datum reveal also hydrates its file.
 * Pierre parses file paths, modes and hunks; Leaf checks that every source file
 * and its evidence can be represented before any listing metadata appears;
 * closed files retain that parse and defer only textual rendering. Native
 * operations and textual hunks are independent: metadata-only files have a commentable
 * row without an empty disclosure, and a file-type replacement keeps one file identity. */
import {
  DISCLOSE,
  HOLDS_WORD,
  announce,
  beginWalk,
  dataBody,
  failSoft,
  ensureSyntaxLanguage,
  focusDestination,
  generated,
  generatedElement,
  holdFocus,
  html,
  nothing,
  keyed,
  render,
  relabel,
  inChrome,
  nameAction,
  commands,
  keeps,
  keepsText,
  langForPath,
  layoutChanged,
  loadDeferred,
  listWalkPosition,
  move,
  nextRender,
  offer,
  offerAction,
  LeafElement,
  paintKeys,
  publishOutput,
  projectedDatum,
  threadSurface,
  releaseOutlets,
  reportFailure,
  retainUserIntent,
  scrollBehavior,
  scrollIntoReadingBand,
  searchField,
  setChildren,
  shadowStage,
  sizeObserver,
  whileConnected,
  scrollIntoView,
  layoutPx,
  focused,
  currentLocationIn,
} from "/runtime/widget-api.js";
import {
  diffDatumKey,
  findDiffFile,
  findDiffLine,
  readDiffCoordinate,
} from "./diff-coordinates.js";
import { overflowFor } from "./overflow.js";
import "/vendor/webawesome.esm.js";
import { pierre, markSyntax } from "/widgets/pierre.js";
// Only a diff that is actually rendering has any use for Pierre's renderer —
// an authored <lf-diff> bound to data
// that has not arrived yet does not. So it is imported on first use rather than at
// module load: the page pays for the renderer when it draws a diff, and a version whose
// diff has been taken back out stops paying on the next load. The promise is kept, so
// every later file, every other diff on the page, and every re-render share one import.
// Metadata must be parsed before its row commits; unopened text needs no renderer.
let parser = null;
const parse = () => (parser ??= import("/vendor/pierre-parser.esm.js"));

const OPTIONS = Object.freeze({
  diffStyle: "unified",
  diffIndicators: "classic",
  disableLineNumbers: false,
  disableFileHeader: true,
  hunkSeparators: "line-info-basic",
  lineDiffType: "word-alt",
});

// The records every source form renders from, in the shape of the contract's file
// manifest. A patch text is parsed once, strictly, so a malformed hunk never becomes
// incomplete evidence, and each record carries its parsed file where a manifest's
// record defers its patch. The path keys a record in either form; the contract
// refuses a manifest that repeats one, and this refuses a patch text that does.
async function sourceRecords(source) {
  if (typeof source !== "string") return source.files;
  return (await parsedFiles(source)).map((file) => ({ path: file.name, parsed: file }));
}

// A deferred patch must describe its keyed logical file, including both native
// sections of a file-type replacement. All display metadata comes from this parse.
async function deferredFile(patch, record) {
  const { path } = record;
  const files = await parsedFiles(patch);
  if (files.length !== 1 || files[0].name !== path)
    throw new Error(`the deferred patch for ${path} does not contain that one file`);
  return files[0];
}

// Each record carries the index of the hunk it came out of. A hunk is the unit a
// reviewer actually moves in — one `@@` header is one place the author changed
// something — and it is knowable only here, where the parse is still grouped; the
// rendered rows are a flat run with the separator chrome between them, so recovering
// the grouping from the DOM afterwards would be reading a rendering for a fact the
// parse already had. It rides on the same record the anchor coordinate is read off,
// and `diffDatumKey` names only the fields that make a comment's coordinate, so a row
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

const LINE_KEY = "data-lf-line";

/** @param {import("./diff-coordinates.js").DiffCoordinate} coordinate */
const lineLabel = ({ path, side, oldLine, newLine }) => {
  const file = path || "(unnamed file)";
  if (side === "old") return `${file} · old line ${oldLine}`;
  if (side === "new") return `${file} · new line ${newLine}`;
  return `${file} · old line ${oldLine} · new line ${newLine}`;
};

const fileLabel = ({ path }) => `${path || "(unnamed file)"} · file`;
const fileNode = (entry) => entry.node;
const fileDatum = (entry) => ({
  file: true,
  path: entry.record.path,
  node: fileNode(entry),
});

// The marks that make a drawn file row or line a datum on a Leaf page
// (`module-state.md`, "Marking drawn data"), and their removal from a node kept
// after it stops showing one.
const MARKS = ["data-lf-datum", "data-lf-datum-label", "data-lf-origin-path"];
const mark = (record, path) => {
  keeps(record.node, "data-lf-datum", diffDatumKey(record));
  keeps(
    record.node,
    "data-lf-datum-label",
    record.file ? fileLabel(record) : lineLabel(record),
  );
  keeps(record.node, "data-lf-origin-path", path ? JSON.stringify(path) : null);
};
const unmark = (node) => {
  for (const name of MARKS) node.removeAttribute(name);
};

// Pierre owns parsing, highlighting and word differences. Leaf gives each source
// line one native row: its number is the comment control, and a conversation can
// follow that row without a second gutter column to reconcile or measure.
function renderedLines(file, content) {
  const records = sourceLines(file);
  const nodes = [...content.querySelectorAll("[data-line]")];
  if (nodes.length !== records.length)
    throw new Error(
      `Pierre returned ${nodes.length} source lines for ${file.name}; expected ${records.length}`,
    );
  return records.map((record, index) => {
    const node = nodes[index];
    // Pierre represents an empty source row with a newline placeholder.
    if (node.textContent === "\n") node.replaceChildren();
    const key = diffDatumKey(record);
    node.setAttribute(LINE_KEY, key);
    const row = document.createElement("div");
    row.className = "lf-diff-line";
    row.dataset.lineType = node.dataset.lineType;
    const comment = offer("button", "lf-diff-comment lf-diff-line-comment");
    comment.type = "button";
    comment.tabIndex = -1;
    comment.setAttribute("aria-label", `Comment on ${lineLabel(record)}`);
    comment.setAttribute(LINE_KEY, key);
    relabel(comment, String(record.side === "old" ? record.oldLine : record.newLine), {
      says: "echo",
    });
    node.replaceWith(row);
    row.append(comment, node);
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

// While a file's row cuts its path short, the row wears `data-path-cut`, which draws the
// whole path for the keyboard and a held press (widget-shadow.css), and the path's title holds
// it for a pointer resting there. A path the row shows whole has neither, since each
// would repeat it. Whether the row cuts the path changes only with the width of a part
// of it, the folders or the name (at a new window width, face or press beside it), so
// each part's size is watched rather than polled. A part is cut where its words run
// past its box, measured by a Range to the layout unit: `scrollWidth` rounds to whole
// pixels, and the ellipsis is drawn for a fraction of one. A folder region too small
// for this font's ellipsis is left blank: the browser otherwise paints a glyph sliver.
// Its CSS measurement box supplies the native width. Opacity elides only paint, leaving
// flex allocation and the full path for accessibility, title and held-word intact.
//
// One observer watches every file's row, so a delivery reads every row it names before
// writing any. A summary's paint starts watching its path parts and moves that
// observation when their identity changes (`paintSummary`); replacing its row stops
// the old observations (`replaceFileRendering`). Summaries are created only within
// the synchronous source commit, after its evidence is prepared. Rendered evidence goes
// into the kept row (`replaceFileContent`) and brings no row of its own. A
// row that leaves the page with its file or its diff is not unwatched: an observer
// holds what it watches weakly, so the row is collected with its observation.
const runsPast = (part) => {
  const words = new Range();
  words.selectNodeContents(part);
  return words.getBoundingClientRect().width > part.getBoundingClientRect().width;
};
const pathParts = (details) =>
  details?.matches("details")
    ? [...details.firstElementChild.querySelectorAll(".lf-diff-dir, .lf-diff-base")]
    : [];
const pathSizes = sizeObserver((entries) => {
  const paths = new Set(
    entries.map(({ target }) =>
      target.closest(".lf-diff-head").querySelector(".lf-diff-path"),
    ),
  );
  const readings = [...paths].map((path) => {
    const parts = [...path.querySelectorAll(".lf-diff-dir, .lf-diff-base")];
    return {
      path,
      cut: parts.some(runsPast),
      folders: parts
        .filter((part) => part.matches(".lf-diff-dir"))
        .map((part) => {
          return [
            part,
            Number.parseFloat(getComputedStyle(part, "::before").width) >
              part.getBoundingClientRect().width,
          ];
        }),
    };
  });
  for (const { path, cut, folders } of readings) {
    path.parentElement.toggleAttribute("data-path-cut", cut);
    keeps(path, "title", cut ? path.textContent : null);
    for (const [part, hidden] of folders)
      part.toggleAttribute("data-folder-hidden", hidden);
  }
});
function unwatchPathCut(details) {
  for (const part of pathParts(details)) pathSizes.unobserve(part);
}

function filePathTemplate({ path, previousPath }) {
  const name = path || "(unnamed file)";
  // The held-word presentation uses generated content, so it needs a soft break
  // after each slash alongside the visible path's <wbr> opportunities. A cut path
  // is read whole on keyboard focus or a held press (`paintSummary`, held-word.js).
  const displayPath = previousPath ? `${previousPath} → ${path}` : name;
  return html`<span
    class="lf-diff-path"
    data-path=${displayPath.replaceAll("/", "/\u200b")}
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
function paintSummary(details, record, verified = true) {
  const { path, previousPath, additions, deletions } = record;
  const previous = pathParts(details);
  render(
    html`${keyed(
      JSON.stringify([path, verified && previousPath ? previousPath : null]),
      filePathTemplate(verified ? record : { path }),
    )}${
      verified
        ? html`<span class="lf-diff-stat" ${generated({ says: false })}
            ><span class="lf-diff-additions">+${additions}</span>${" "}<span
              class="lf-diff-deletions"
              >−${deletions}</span
            ><span class="lf-diff-metadata-words"
              >${operationWord(record) ? ` · ${operationWord(record)}` : ""}</span
            ></span
          >`
        : null
    }`,
    details.firstElementChild,
  );
  const current = pathParts(details);
  for (const part of previous) if (!current.includes(part)) pathSizes.unobserve(part);
  for (const part of current) if (!previous.includes(part)) pathSizes.observe(part);
}

function summaryNode(record, open, verified = true) {
  const details = document.createElement("details");
  details.className = "lf-diff-fold";
  details.open = open;
  const summary = document.createElement("summary");
  summary.className = `lf-diff-head lf-disclosure-marker ${HOLDS_WORD}`;
  details.append(summary);
  paintSummary(details, record, verified);
  commands(summary, "On a diff", [
    {
      id: "diff.toggle",
      keys: () => DISCLOSE(summary),
      title: () => `${details.open ? "hide" : "show"} this file`,
    },
  ]);
  paintFileDetails(details, verified ? record : {});
  return details;
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
function fileEntry(row) {
  const node = document.createElement("div");
  node.className = "lf-diff-file";
  const actions = offer("div", "lf-diff-file-actions");
  node.append(actions, row);
  return {
    node,
    details: row.matches("details") ? row : null,
    lines: [],
    filtered: false,
  };
}

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

// Keep file controls and evidence under one retained body across source revisions.
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
const holdFileFocus = (entry) => holdFocus(entry.node, { key: LINE_KEY });

function replaceFileRendering(entry, row) {
  const restore = holdFileFocus(entry);
  unwatchPathCut(entry.details);
  // Out of the replaced row first, which takes everything still in it.
  const outlets = [...entry.node.querySelectorAll(".lf-diff-thread-outlet")];
  for (const outlet of outlets)
    if (outlet.parentNode !== entry.node) move(entry.node, outlet, null);
  setChildren(entry.node, [entry.node.firstElementChild, row, ...outlets]);
  entry.details = row.matches("details") ? row : null;
  entry.lines = [];
  entry.renderKey = null;
  return () => restore?.(entry.details?.firstElementChild, entry.node);
}

// The line each thread outlet in a file follows once the file is
// drawn anew, as `{lead, after}`: its own datum's line in `rows` where that is drawn
// again, which its record now names, or else the line that stood before it, or `lead`,
// the file's start, where none did.
function outletPlaces(content, rows, outlets) {
  const lead = [];
  const after = new Map();
  let last = null;
  for (const child of content?.children ?? []) {
    const key = child.matches(".lf-diff-line")
      ? child.querySelector(`[${LINE_KEY}]`).getAttribute(LINE_KEY)
      : null;
    if (key !== null) {
      if (rows.has(key)) last = key;
      continue;
    }
    const datum = child.dataset.lfThreadDatum;
    const record = outlets?.get(datum);
    if (record?.outlet !== child) continue;
    if (rows.has(datum)) record.row = rows.get(datum).querySelector("[data-line]");
    const place = rows.has(datum) ? datum : last;
    if (place === null) lead.push(record);
    else {
      if (!after.has(place)) after.set(place, []);
      after.get(place).push(record);
    }
  }
  return { lead, after };
}

// A file's evidence goes under its kept disclosure, whose summary the record paints.
function replaceFileContent(entry, rendered, outlets) {
  const restore = holdFileFocus(entry);
  const details = entry.details;
  const pre = details.querySelector("pre");
  const prior = new Map(entry.lines.map((line) => [diffDatumKey(line), line]));
  const retained = new Map();
  for (const next of rendered.lines) {
    const previous = prior.get(diffDatumKey(next));
    if (!previous || previous.content !== next.content) continue;
    retained.set(next.row, previous.row);
    next.node = previous.node;
    next.row = previous.row;
  }
  const rows = new Map(rendered.lines.map((line) => [diffDatumKey(line), line.row]));
  const content = pre?.querySelector(".lf-diff-rows");
  const { lead, after } = outletPlaces(content, rows, outlets);
  const nextContent = rendered.pre.querySelector(".lf-diff-rows");
  const children = [
    ...lead.map(({ outlet }) => outlet),
    ...[...nextContent.children].flatMap((row) => [
      retained.get(row) ?? row,
      ...(
        after.get(row.querySelector(`[${LINE_KEY}]`)?.getAttribute(LINE_KEY)) ?? []
      ).map(({ outlet }) => outlet),
    ]),
  ];
  if (pre) {
    keeps(pre, "data-overflow", rendered.pre.dataset.overflow);
    keeps(content, "style", nextContent.getAttribute("style"));
    setChildren(content, children);
  } else setChildren(nextContent, children);
  setChildren(details, [details.firstElementChild, pre ?? rendered.pre]);
  entry.lines = rendered.lines;
  return () => restore?.(details.firstElementChild);
}

function diffTools(host) {
  const search = searchField("lf-diff-tools lf-diff-search", {
    name: "diff-search",
    label: "Filter diff files",
    placeholder: "Filter files",
  });
  search.addEventListener("input", () => host.filterFiles(search.value));
  const progress = document.createElement("span");
  progress.className = "lf-diff-progress";
  generatedElement(progress, { says: false });
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

function operationWord(record) {
  return (
    {
      add: "added",
      delete: "deleted",
      rename: "renamed",
      copy: "copied",
    }[record.operation] ?? ""
  );
}

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

function metadataWords(record) {
  return [operationWord(record), evidenceWords(record)].filter(Boolean).join(" · ");
}

// Header counts and the short operation keep their columns. Longer mode/binary
// evidence belongs with the disclosed text, where it can wrap without hiding a path.
function paintFileDetails(details, record) {
  const words = evidenceWords(record);
  let evidence = details.querySelector(":scope > .lf-diff-evidence");
  if (!words) {
    evidence?.remove();
    return;
  }
  if (!evidence) {
    evidence = document.createElement("div");
    evidence.className = "lf-diff-evidence";
    generatedElement(evidence, { says: false });
    details.firstElementChild.after(evidence);
  }
  keepsText(evidence, words);
}

function metadataNode(record) {
  const row = document.createElement("div");
  row.className = "lf-diff-metadata";
  generatedElement(row, { says: false });
  render(
    html`${filePathTemplate(record)}<span class="lf-diff-stat"
        >${metadataWords(record)}</span
      >`,
    row,
  );
  return row;
}

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
    const header = section.split(/^--- /m, 1)[0];
    const metadata = parsePatchFiles(header, undefined, true).flatMap(
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
  template.innerHTML = renderHTML(highlighted.unifiedContentAST);
  const content = template.content;
  content.querySelector("svg[data-icon-sprite]")?.remove();
  for (const separator of content.querySelectorAll(
    "[data-separator], [data-no-newline]",
  ))
    separator.classList.add("lf-ui");
  markSyntax(content, foreground);
  const lines = renderedLines(file, content);
  const pre = document.createElement("pre");
  pre.dataset.overflow = overflow;
  const viewport = document.createElement("code");
  viewport.dataset.code = "";
  viewport.className = "lf-text-scroller scroll";
  viewport.setAttribute("role", "region");
  viewport.setAttribute("aria-label", file.name || "diff");
  const rows = document.createElement("div");
  rows.className = "lf-diff-rows";
  const largest = lines.reduce(
    (max, line) => Math.max(max, line.newLine ?? line.oldLine),
    0,
  );
  rows.style.setProperty("--lf-diff-gutter", `${String(largest).length + 3}ch`);
  rows.append(content);
  viewport.append(rows);
  const frame = document.createElement("span");
  frame.className = "lf-diff-frame";
  frame.setAttribute("aria-hidden", "true");
  pre.append(viewport, frame);
  return { pre, lines };
}

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
  // when both carry identical text. The maintained comparator keeps that meaning.
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
        { comparator: () => false },
        true,
      )
    : { name: added.name, hunks: [] };
  file.record = {
    path: added.name,
    operation: "modify",
    hunkCount,
    binary: deleted.record.binary || added.record.binary,
    oldMode,
    newMode,
    additions: added.record.additions,
    deletions: deleted.record.deletions,
  };
  return file;
}

// What the widget can present, which it alone judges: the diff package's
// `patch_manifest.py` preserves the evidence, and an entry refused here reports when
// its listing appears, even when its textual file stays closed. `tests/diff_patch_cases.json`
// is the table of cases.
async function parsedFiles(source) {
  const { parsePatchFiles, parseDiffFromFile } = await parse();
  const files = parsePatchFiles(source, undefined, true).flatMap(
    (patch) => patch.files,
  );
  const sections = source
    .split(/(?=^diff --git )/m)
    .filter((section) => section.startsWith("diff --git "));
  if (!files.length) throw new Error("empty diff");
  if (files.length !== sections.length)
    throw new Error(
      "Expected a Git patch with a diff --git header for each file; preserve the file headers from git diff.",
    );
  const owners = new Map();
  for (const [index, file] of files.entries()) {
    file.record = fileRecord(file, sections[index], parsePatchFiles);
    const owned = owners.get(file.name) ?? [];
    owned.push(file);
    owners.set(file.name, owned);
  }
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
function joinChangeRuns(file) {
  for (const hunk of file.hunks ?? []) {
    const content = [];
    for (const part of hunk.hunkContent) {
      const last = content.at(-1);
      const piece =
        part.type === "change" &&
        last?.type === "change" &&
        [part, last].some((change) => !change.deletions || !change.additions);
      if (!piece) {
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
// first: a user writing about one of them stays in it, and the hold below, which
// would hand them to Retry, finds them outside the file. A patch the widget cannot draw
// offers no Retry, and the hold lands on the file's header.
function deferredError(details, error, retry) {
  releaseOutlets(details);
  const restore = holdFocus(details);
  const header = details.firstElementChild;
  const message = error?.message || error;
  const box = document.createElement("div");
  box.className = "lf-error";
  generatedElement(box, { says: false });
  box.textContent = retry
    ? `That file's diff failed to load: ${message}`
    : `That file's diff cannot be shown: ${message}`;
  let standIn = header;
  if (retry) {
    standIn = offerAction("symbol", "", undefined, { action: "retry" });
    standIn.addEventListener("click", () => {
      if (standIn.getAttribute("aria-disabled") === "true") return;
      standIn.setAttribute("aria-disabled", "true");
      retry();
    });
    box.append(" ", standIn);
  }
  setChildren(details, [header, box]);
  restore?.(standIn);
}

customElements.define(
  "lf-diff",
  class extends LeafElement {
    // The source the last render read, a bound value or an inline patch, and the one
    // whose rendering last started; a departure that cuts a rendering short forgets
    // it, so the return draws it again.
    #delivered;
    #shown;
    #showing = false;
    // The rendering the update under way started, which its `updateComplete` waits for.
    #rendered;
    // The nodes the last marking marked as data.
    #marked = new Set();

    // The patch text or file manifest, set by whoever hosts the widget: Leaf from the
    // bound source (the registry's `x-data.document.property`), or null while that
    // source has none.
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      /** @type {string | {files: any[]} | null} */
      this.value = null;
    }

    shouldUpdate(changed) {
      const ready = super.shouldUpdate(changed);
      if (!ready) return false;
      // Only new evidence or preparation interrupted by departure needs a draw;
      // a no-op update would clear a completed refusal.
      const source = this.hasAttribute("source") ? this.value : this.inlineSource;
      return this.#shown === undefined || source !== this.#shown;
    }

    setup() {
      this.singleFile = this.getAttribute("view") === "file";
      commands(
        this,
        "In a diff review",
        [
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
              return (
                currentLocationIn(this) &&
                Boolean(search.value || currentLocationIn(search))
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
        () => Boolean(this.fileEntries?.length),
      );
      if (!this.hasAttribute("source")) {
        // Not bodyText: a diff's trailing whitespace is content — a hunk's last line
        // can be a lone space — so only the closing newline is the <pre>'s layout.
        this.inlineSource = dataBody(this).replace(/^\n+/, "").replace(/\n$/, "");
      }
      whileConnected(this, (signal) => {
        // A page diff's file header pins at `--lf-top`, the top of the page's box that
        // scrolls it; one an agent sent in a reply scrolls inside the panel's own list,
        // which declares no such edge. The theme cannot ask that question from inside a shadow tree, so
        // the module answers it once with the layer's own predicate and paints the answer.
        this.toggleAttribute("data-lf-diff-pinned", !inChrome(this));
        return () => {
          this.rendering = (this.rendering ?? 0) + 1;
          if (this.#showing) this.#shown = undefined;
          // Leaf retires this surface when it leaves, after this cleanup, and puts
          // core's views back, so every outlet goes.
          if (this.threadSeats) {
            for (const record of this.threadSeats.values()) record.active = false;
            this.retireThreadOutlets();
          }
          this.threadSeats = null;
        };
      });
    }

    render() {
      this.#delivered = this.hasAttribute("source") ? this.value : this.inlineSource;
      return nothing;
    }

    // A patch renders each source once, after the draw that read it, whose
    // `updateComplete` waits for the rendering.
    updated(changed) {
      super.updated(changed);
      this.#rendered = undefined;
      if (this.#delivered === this.#shown) return;
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

    // `source` is a patch text or a file manifest, or null when a bound source has
    // none.
    async show(source) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      try {
        if (source === null) {
          releaseOutlets(this);
          this.fileEntries = null;
          this.publishFiles();
          this.diffTools = null;
          this.filesBody = null;
          shadowStage(this, []);
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
        const plans = await Promise.all(
          records.map(async (record) => {
            const evidence = await this.readEntry(source, record);
            return {
              record: evidence.file?.record ?? record,
              evidence,
              previous: prior.get(record.path),
              prepared: evidence.error ? evidence : null,
            };
          }),
        );
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
                source,
                plan.record,
                plan.previous?.details ? plan.previous.renderKey : null,
                plan.evidence,
              );
            }),
          );
        }
        const activePath = currentPath();
        const fresh = [];
        const restores = [];
        const resume = this.controller.defer();
        try {
          const entries = plans.map(({ record, evidence, previous, prepared }) => {
            let entry = previous;
            const metadata = record.hunkCount === 0 && !prepared?.error;
            if (
              metadata
                ? !entry ||
                  entry.details ||
                  JSON.stringify(entry.record) !== JSON.stringify(record)
                : !entry?.details
            ) {
              const row = metadata
                ? metadataNode(record)
                : summaryNode(
                    record,
                    !!prepared?.error ||
                      record.hunkCount === 0 ||
                      (this.singleFile ? record.path === activePath : open),
                    !prepared?.error,
                  );
              if (entry) restores.push(replaceFileRendering(entry, row));
              else fresh.push((entry = fileEntry(row)));
            }
            Object.assign(entry, {
              record,
              file: evidence.file,
              loaded: metadata,
              failed: false,
              refused: false,
              loading: null,
            });
            generatedElement(entry.node, { says: false });
            if (metadata) {
              entry.lines = [];
              entry.renderKey = null;
              return entry;
            }
            if (prepared) restores.push(this.applyEntry(entry, prepared));
            else {
              paintSummary(entry.details, record);
              entry.details.querySelector("pre")?.toggleAttribute("hidden", true);
              paintFileDetails(entry.details, record);
            }
            return entry;
          });
          this.drawnSource = source;
          this.fileEntries = entries;
          this.activePath = activePath;
          if (this.singleFile || entries.length < 2) this.diffTools = null;
          else this.diffTools ??= diffTools(this);
          for (const entry of fresh) this.attachEntryControls(entry);
          for (const entry of entries) this.attachDisclosure(entry);
          this.filesBody ??= diffBody([]);
          // A file the patch dropped goes with its outlets, which core's composer leaves first.
          for (const entry of prior.values())
            if (!entries.includes(entry)) releaseOutlets(entry.node);
          setChildren(this.filesBody, [
            ...(this.diffTools ? [this.diffTools.search] : []),
            ...entries.map(({ node }) => node),
          ]);
          this.markRuns();
          this.stageFiles();
          this.markFiles(source);
          this.classList.toggle("lf-rendered", true);
          this.filterFiles(this.diffTools?.search.value ?? "");
          this.publishFiles();
          for (const restore of restores) restore?.();
        } finally {
          resume();
        }
      } catch (err) {
        if (rendering !== this.rendering || !this.isConnected) return;
        this.fileEntries = null;
        this.publishFiles();
        this.diffTools = null;
        this.filesBody = null;
        this.classList.toggle("lf-rendered", false);
        // The failure box quotes a patch text; a manifest has none to quote. It takes
        // the place of every outlet, which core's composer leaves first.
        releaseOutlets(this);
        failSoft(this, err, typeof source === "string" ? source : undefined);
        this.markFiles(source);
      }
    }

    // The inventory belongs to this parse, rather than to any particular navigator.
    // Keys are opaque addresses in this widget's existing datum space; consumers
    // neither parse patches nor know how a diff encodes a file identity.
    publishFiles() {
      const status = {
        add: "added",
        delete: "deleted",
        modify: "modified",
        rename: "renamed",
      };
      publishOutput(
        this,
        "files",
        this.fileEntries
          ? {
              ...(this.singleFile ? { current: this.activePath } : {}),
              files: this.fileEntries.map(({ record }) => ({
                path: record.path,
                key: diffDatumKey({ path: record.path, file: true }),
                ...(status[record.operation]
                  ? { status: status[record.operation] }
                  : {}),
              })),
            }
          : null,
      );
    }

    // A patch that fails to load may load on Retry. One this widget cannot draw never
    // will, so it offers no Retry, and `applyEntry` reports it to the agent, which stored
    // it, once the current rendering shows it: the manifest's producer leaves judging a
    // patch to this widget.
    async readEntry(source, record) {
      let patch;
      if (!record.parsed)
        try {
          patch = await loadDeferred(source, record.path);
        } catch (error) {
          return { error, retry: true };
        }
      try {
        return { file: record.parsed ?? (await deferredFile(patch, record)) };
      } catch (error) {
        return { error };
      }
    }

    async prepareEntry(source, record, renderKey, evidence) {
      const reading = evidence ?? (await this.readEntry(source, record));
      if (reading.error) return reading;
      try {
        const { file } = reading;
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
      shadowStage(this, [this.filesBody]);
    }

    // Marks each drawn file row, and each line of a loaded file, as data drawn from
    // `source`, and reports it. A manifest names the field each datum came from; a
    // patch text's datums take the whole delivery's origin, and an inline patch has no
    // delivery.
    markFiles(source) {
      const manifest = source !== null && typeof source === "object";
      const marked = new Set();
      for (const [index, entry] of (this.fileEntries ?? []).entries())
        for (const [record, field] of [
          [fileDatum(entry), "path"],
          ...(entry.loaded ? entry.lines : []).map((line) => [line, "patch"]),
        ]) {
          mark(record, manifest ? ["files", index, field] : null);
          marked.add(record.node);
        }
      for (const node of this.#marked) if (!marked.has(node)) unmark(node);
      this.#marked = marked;
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value: source } }));
    }

    // x-thread-surface: Leaf asks for one outlet, or null, per target it hands over, and
    // the outlets this placement no longer uses come down once it commits.
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
      this.threadSeats ??= new Map();
      for (const record of this.threadSeats.values()) record.active = false;
    }

    threadOutletFor({ anchor, placement }) {
      const coordinate = readDiffCoordinate(anchor.datum);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!entry || entry.filtered) return null;
      const file = coordinate.file;
      const line =
        !file && entry.lines.find((line) => diffDatumKey(line) === anchor.datum);
      if (file) {
        if (placement.datumElement !== entry.node) return null;
      } else if (
        !entry.loaded ||
        (entry.details && !entry.details.open) ||
        placement.datumElement !== line?.node
      )
        return null;

      const row = placement.datumElement;
      let record = this.threadSeats.get(anchor.datum);
      if (!record) {
        const outlet = document.createElement("section");
        outlet.className = `lf-diff-thread-outlet lf-ui${
          file ? " lf-diff-file-thread-outlet" : ""
        }`;
        generatedElement(outlet, { says: false });
        outlet.dataset.lfThreadDatum = anchor.datum;
        outlet.setAttribute(
          "aria-label",
          `Thread on ${row.dataset.lfDatumLabel || (file ? "file" : "diff line")}`,
        );
        record = { outlet, row: null };
        this.threadSeats.set(anchor.datum, record);
      }
      // A datum drawn anew takes its outlet along, which keeps whoever stands in it.
      if (record.row !== row) {
        if (file) move(entry.node, record.outlet, null);
        else move(row.parentNode.parentNode, record.outlet, row.parentNode.nextSibling);
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

    async loadEntry(entry) {
      for (;;) {
        const rendering = this.sourceRendering;
        await rendering;
        if (!this.isConnected) return;
        if (rendering === this.sourceRendering) break;
      }
      if (!this.fileEntries?.includes(entry)) return;
      if (entry.loaded || entry.refused) return;
      // A disconnect abandons a load, and the entry stays loadable: an inline patch
      // keeps its entries across a reconnection, so a later open starts afresh.
      if (entry.loading?.rendering === this.rendering) return entry.loading.promise;
      const rendering = this.rendering;
      const promise = (async () => {
        const prepared = await this.prepareEntry(
          this.drawnSource,
          entry.record,
          entry.renderKey,
          entry.file ? { file: entry.file } : undefined,
        );
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
    commitLoaded(entry, prepared, rendering) {
      this.loadedQueue ??= new Map();
      this.loadedQueue.set(entry, { prepared, rendering });
      this.loadedCommit ??= new Promise((resolve, reject) =>
        nextRender(() => {
          const queue = this.loadedQueue;
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
    applyEntry(entry, { error, retry, file, renderKey, rendered }) {
      if (error) {
        entry.failed = true;
        paintSummary(entry.details, entry.record, false);
        paintFileDetails(entry.details, {});
        if (!entry.details.open) entry.details.open = true;
        entry.disclosureOpen = true;
        // Reopening retries a load; nothing loads a patch this widget refused again.
        entry.refused = !retry;
        if (entry.refused) reportFailure(this, error);
        entry.lines = [];
        entry.renderKey = null;
        deferredError(
          entry.details,
          error,
          retry &&
            (() => {
              if (!entry.failed) return;
              entry.failed = false;
              this.present(this.loadEntry(entry));
            }),
        );
        return null;
      }
      entry.file = file;
      entry.record = file.record;
      paintSummary(entry.details, entry.record);
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
      paintFileDetails(entry.details, entry.record);
      return restore;
    }

    // Core can place an existing line thread at its file disclosure before that file's
    // patch exists in the DOM. Navigation asks the second method to make the exact line
    // real, then the ordinary datum resolver and anchor painter take over.
    lfDataDatum(key, { outdated = false } = {}) {
      const coordinate = readDiffCoordinate(key);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!entry) return null;
      if (coordinate.file) return fileNode(entry);
      if (outdated) return entry.node;
      if (!entry.loaded || entry.filtered) return entry.node;
      const line = findDiffLine(entry.lines, coordinate);
      return line ? projectedDatum(this, diffDatumKey(line)) : null;
    }

    // A datum's label is its coordinate's, so a thread on a line of a file not yet
    // loaded is named as the drawn line will be.
    lfDatumLabel(key) {
      const coordinate = readDiffCoordinate(key);
      if (!coordinate || coordinate.source) return null;
      return coordinate.file ? fileLabel(coordinate) : lineLabel(coordinate);
    }

    lfRevealDatum(key) {
      const coordinate = readDiffCoordinate(key);
      const entry = findDiffFile(this.fileEntries, coordinate);
      if (!entry) return null;
      if (this.singleFile) this.selectFile(entry);
      else if (entry.filtered) this.clearFilter();
      if (!entry.details) return null;
      if (!entry.details.open) entry.details.open = true;
      if (entry.loaded || entry.failed) return null;
      return this.loadEntry(entry);
    }

    attachDisclosure(entry) {
      if (entry.disclosureNode === entry.details) return;
      entry.disclosureNode?.removeEventListener("toggle", entry.disclose);
      entry.disclosureNode = entry.details;
      if (!entry.details) return;
      entry.disclosureOpen = entry.details.open;
      entry.disclose ??= () => {
        const previous = entry.disclosureOpen;
        entry.disclosureOpen = entry.details.open;
        threadSurface(this).update();
        this.paintFoldAll();
        if (previous === entry.disclosureOpen) return;
        if (!entry.details.open || !this.fileEntries?.includes(entry) || entry.refused)
          return;
        entry.failed = false;
        this.present(this.loadEntry(entry));
      };
      entry.details.addEventListener("toggle", entry.disclose);
    }

    attachEntryControls(entry) {
      entry.node.addEventListener("click", (event) => {
        const button = event.target.closest(".lf-diff-line-comment");
        if (button) threadSurface(this).open(button.nextElementSibling);
      });
      entry.node.addEventListener("beforematch", () => {
        if (this.singleFile) this.selectFile(entry);
        else this.clearFilter();
      });
      const label = entry.record.path || "file";
      entry.fileComment = commentButton(
        label,
        () => threadSurface(this).open(entry.node),
        "lf-diff-file-comment",
      );
      entry.node
        .querySelector(":scope > .lf-diff-file-actions")
        .prepend(entry.fileComment);
    }

    present(promise) {
      return this.controller.present(promise);
    }

    filterFiles(query) {
      const needle = query.trim().toLocaleLowerCase();
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
      layoutChanged(this);
      threadSurface(this).update();
    }

    // The file view keeps every datum under its retained owner; only the active
    // file is visible. A thread or any navigator can reveal another through the
    // same datum route, without knowing which presentation the page chose.
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
      const talks = (entry) =>
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
      keeps(this.diffTools.progress, "data-room", `${all}\n${total} of ${total}`);
      keepsText(this.diffTools.count, shown.length === total ? all : matching);
      this.paintFoldAll();
      paintKeys();
    }

    // The files the filter shows: all opened while any is closed, and all closed once
    // every one is open, so the press does what its face says.
    foldAll() {
      const folds = this.shownFolds();
      const open = folds.some((details) => !details.open);
      for (const details of folds) if (details.open !== open) details.open = open;
      this.paintFoldAll();
      announce(`${open ? "Expanded" : "Collapsed"} all files`);
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
      const currentLocation = this.shadowRoot && focused(this.shadowRoot);
      return currentLocation && this.shadowRoot.contains(currentLocation)
        ? currentLocation
        : null;
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

    markFileWalk() {
      beginWalk("diff-file", "File", () => {
        const entries = this.navigationEntries();
        return listWalkPosition(
          entries.map(({ node }) => node),
          this.entryAroundFocus()?.node,
        );
      });
    }

    async openEntry(entry) {
      if (!entry.details) return;
      if (!entry.details.open) entry.details.open = true;
      await this.loadEntry(entry);
    }

    // The walk starts in the file the user is in and goes on through the
    // ones after it, so a closed file is opened only once the step has actually reached
    // it: a user on the last hunk of the third file loads the fourth and stops, rather
    // than every remaining file to discover there is nothing past them.
    // Opening a file may wait on the network, and the user may have moved on by then:
    // both walks capture the pressing gesture's intent first and land only while it stands.
    async stepHunk(back) {
      const mayLand = retainUserIntent();
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      const currentLocation = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      for (let index = Math.max(currentLocation, 0); index < order.length; index++) {
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
      if (!entry) return this.markFileWalk();
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
      this.markFileWalk();
      announce(entry.record.path);
    }

    // Arrival: scrolled to the band the document declares landable, which the pinned
    // header's own room has been added to, and then the focus without the browser
    // scrolling a second time. A row is not a tab stop — a patch is thousands of them —
    // so it is made focusable for the press that lands on it, and wears the band inset
    // inside its own box (widget-shadow.css). A file header
    // already is one, and writing a tabindex of -1 onto it would take it out of the
    // order a user tabs through.
    //
    // The shared reading-region landing moves only vertically, including through
    // the shadow host. Neither the file nor a region around it loses its sideways place.
    land(box, node = box) {
      scrollIntoReadingBand(box, box, "start", scrollBehavior());
      focusDestination(node, "move");
    }

    entryAroundFocus() {
      const here = this.hereNode();
      const focusedEntry =
        this.fileEntries?.find(({ node }) => here && node.contains(here)) ?? null;
      if (focusedEntry) return focusedEntry;
      return this.fileEntries?.includes(this.fileCursor) ? this.fileCursor : null;
    }
  },
);
