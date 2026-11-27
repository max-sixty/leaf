/* A document owns one text and its source/preview readings. The text is its `value`,
 * which Leaf sets from a bound source or widget output, or from the `<pre>` the page
 * wrote when the markup binds neither (host/element-data.js, "Bound values"). A value
 * may name its file beside the text, which the caption shows and the readings' identity
 * carries (`mark`). Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. A document takes its text's height,
 * up to `--lf-bound`, and a preview's Source tab takes the preview's height
 * (`holdSource`), so switching tabs keeps the page still. A document drawn on its
 * Source tab, as after a reload, has not drawn its preview, so its Source tab keeps
 * the box the page first painted, and switching to the preview then takes the
 * preview's height. Where that height cuts the text, a press shows the whole document
 * in every reading (`cuts`), as a quote's label opens a thread's whole quote: a reflow
 * the reader asks for. A cut box doesn't scroll, so the press is the reader's way to
 * the rest, and what the cut hides is folded `hidden="until-found"`, so travel to a
 * comment on it and find-in-page show the whole document too (`cut`). An author sets
 * where the cut falls with `--lf-bound`, in lines with `lh`, or shows the whole
 * document with `none`.
 * Filling a workspace pane, a document scrolls inside the pane instead
 * (text-document.css). Bound text arrives after first paint, so its box changes
 * height as the text arrives and as later writes change its length.
 * The source reading is a numbered listing of plain rows, one a line (`listing`), so
 * every document's whole text stands in the page for find-in-page, selection, copy
 * and comments, in a tab nobody has opened too; held back until its tab opened, a
 * document's text would be out of Find's reach. Line numbers are generated content
 * (text-document.css), so selecting or copying the source never includes them. The
 * rows stand in runs that the browser draws only in view (`run`), each sized ahead
 * of drawing by the lines its rows fill (`sizeRuns`), and syntax colour is painted on
 * the runs in view alone, as highlights over their text (`RunColours`). Built whole,
 * with a span for each token and a gutter cell for each number, a page of large
 * documents would take seconds and gigabytes to show the one in view. The Markdown
 * preview renders a file,
 * whose soft line breaks are spaces, so a paragraph wraps to the preview's width. A new
 * text rewrites only the source rows it changes (`rewrite`) and the preview's text it
 * changes, so code and formulas it leaves stay as drawn (`preparePreview`).
 * A double-click on a word in the Markdown preview of the file an editor holds puts the
 * editor's caret at the start of that word's line in the file (`editAtLine`), as a
 * double-click on VS Code's preview does (the user's decision). Its second press
 * selects no word, so in that preview a reader selects words to comment on by
 * dragging. The reader reaches the same caret in the editor itself, so the
 * double-click needs no keyboard or touch route of its own. HTML lives in a separate
 * frame so its styles and scripts cannot access Leaf’s document. Source provenance is
 * stamped with its text before awaiting the frame's presentation. */
import { nothing } from "/vendor/lit.js";
import {
  whileConnected,
  setRenderedChildren,
  setChildLists,
  setChildren,
  focusDestination,
  afterPresentation,
  pageLinks,
  dressCode,
  aimedAt,
  navigateToDatum,
  boundFile,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { failSoft } from "/runtime/lib/failure.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { sizeObserver, nextFrame } from "/runtime/lib/frame-pass.js";
import { plainPress } from "/runtime/lib/keys.js";
import {
  loadMarkdown,
  markdownFileFragment,
  markdownSourceOffset,
} from "/runtime/lib/markdown.js";
import { MAX_EDIT_LENGTH } from "/runtime/lib/text-alignment.js";
import { keeps, keepsText, layoutPx } from "/runtime/lib/keeps.js";
import {
  codeLanguage,
  ensureSyntaxLanguage,
  syntax,
} from "/runtime/lib/syntax-tokens.js";
import { textWidth } from "/runtime/lib/text-width.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

/** @typedef {import("../../../browser/types/contract.js").DataTextDocument} DocumentValue */

// A fragment's words, as a heading's address spells them (`headingSlugs`).
/** @param {string} fragment */
const slugWords = (fragment) => {
  try {
    return decodeURIComponent(fragment);
  } catch {
    return fragment;
  }
};

// A node of a rendering as its markup, the same for nodes that draw the same.
/** @param {Node} node */
const drawnMarkup = (node) =>
  node instanceof Element ? node.outerHTML : `${node.nodeType}:${node.textContent}`;

// The key a place of the Markdown preview takes before its name (`lfElementsFor`).
const PLACE = "preview:";
// Whether a reading's box clips its text at its bound rather than scrolling it, as it
// does filling a pane (text-document.css).
/** @param {Element} box */
const cutting = (box) => /^(hidden|clip)$/.test(getComputedStyle(box).overflowY);

// Each reading shows the same document whatever text its source holds, so its key is
// also its identity (records/projection/data.js), with the file's where the value names
// one, since one document can show several files in turn, as an editor's open file. A
// comment on a passage then follows the passage's words across replacements, stays
// marked while they still stand, and stays with the file it was made on.
/** @param {HTMLElement} node @param {string} key @param {string | null} file */
const mark = (node, key, file) => {
  keeps(node, "data-lf-datum", key);
  keeps(node, "data-lf-identity", file ? `${key}:${file}` : key);
};

// A heading's address in a file, as GitHub writes it for a link from the file to the
// heading: its words lowercased, without punctuation, each space a hyphen, and a count
// after an address an earlier heading took (github-slugger).
/** @param {Iterable<Element>} headings @returns {Map<string, Element>} */
function headingSlugs(headings) {
  /** @type {Map<string, Element>} */
  const slugs = new Map();
  /** @type {Map<string, number>} */
  const taken = new Map();
  for (const heading of headings) {
    const base = heading.textContent
      .toLowerCase()
      .replace(
        /[^\p{Letter}\p{Mark}\p{Decimal_Number}\p{Letter_Number}\p{Connector_Punctuation} -]/gu,
        "",
      )
      .replace(/ /g, "-");
    let slug = base;
    while (taken.has(slug)) {
      const count = (taken.get(base) ?? 0) + 1;
      taken.set(base, count);
      slug = `${base}-${count}`;
    }
    taken.set(slug, 0);
    slugs.set(slug, heading);
  }
  return slugs;
}

// The file a value names: its stable key where it gives one, else its name.
/** @param {DocumentValue | null} value */
const fileOf = (value) =>
  typeof value === "string" ? null : (value?.key ?? value?.name ?? null);

// The candidates of a `srcset`, each its URL and its size, as `640w` or `2x`: a URL runs
// to HTML's whitespace, and a comma it ends with, or the first after its size, ends the
// candidate (HTML's "parse a srcset attribute").
/** @param {string} srcset @returns {[string, string][]} */
function srcsetCandidates(srcset) {
  /** @type {[string, string][]} */
  const candidates = [];
  let at = 0;
  while (at < srcset.length) {
    const start = srcset.slice(at).search(/[^\t\n\f\r ,]/);
    if (start < 0) break;
    at += start;
    const end = at + srcset.slice(at).search(/[\t\n\f\r ]|$/);
    const url = srcset.slice(at, end);
    at = end;
    if (url.endsWith(",")) {
      candidates.push([url.replace(/,+$/, ""), ""]);
      continue;
    }
    const comma = srcset.indexOf(",", at);
    const stop = comma < 0 ? srcset.length : comma;
    candidates.push([url, srcset.slice(at, stop).trim()]);
    at = stop + 1;
  }
  return candidates;
}

// The places in a Markdown file a link of the file can name, as GitHub's rendering
// answers it: each heading by its address (`headingSlugs`), and each element the file
// names by `id` or `name`, as `<a name="top">`, by that name (`data-lf-place`), which
// the preview carries rather than give the page the file's ids (`preparePreview`).
/** @param {ParentNode} root */
function filePlaces(root) {
  const places = headingSlugs(root.querySelectorAll("h1, h2, h3, h4, h5, h6"));
  for (const element of root.querySelectorAll("[data-lf-place]")) {
    const name = element.getAttribute("data-lf-place") ?? "";
    if (!places.has(name)) places.set(name, element);
  }
  return places;
}

// Rows per run: several times the lines a document's box shows, so the runs in view
// are cheap to draw and colour, and a megabyte of text makes about 150 runs.
const RUN = 128;

// A text as the listing draws it, a row a line: each line without its ending (`text`),
// and the ending after it (`endings`). A row holds both, exactly as the source has
// them, so the listing's text is the source, a final newline (or its absence) included.
/** @typedef {{text: readonly string[], endings: readonly string[]}} Lines */
/** @param {string} source @returns {Lines} */
function lines(source) {
  return {
    text: source.split(/\r\n|\r|\n/),
    endings: source.match(/\r\n|\r|\n/g) ?? [],
  };
}

/** The words of row `at` of `drawn`. @param {Lines} drawn @param {number} at */
const words = ({ text, endings }, at) => (text[at] ?? "") + (endings[at] ?? "");

/** A new row holding `words`. @param {string} words */
function row(words) {
  const row = document.createElement("div");
  if (words) row.append(words);
  return row;
}

// The source as the listing draws it: a `pre`, which owns scroll and provenance,
// holding a `code`, which owns the native reach stop, holding the rows in runs of
// `RUN` (`run`), and the line each run starts on (`starts`). A row's number is its
// place, counted in the stylesheet.
/** @param {Lines} drawn */
function listing(drawn) {
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  pre.style.setProperty("--lf-number-digits", digits(drawn));
  pre.append(code);
  const starts = [];
  for (let first = 0; first < drawn.text.length; first += RUN) {
    const count = Math.min(RUN, drawn.text.length - first);
    const held = run(count);
    for (let at = first; at < first + count; at++) held.append(row(words(drawn, at)));
    number(held.firstElementChild, first);
    code.append(held);
    starts.push(first);
  }
  return { pre, code, starts };
}

// Every number takes the width of the text's widest one, so every row's text starts at
// the same x.
/** @param {Lines} drawn */
const digits = ({ text }) => `${String(text.length).length}`;

// A run for `count` rows: a box the browser skips while it is out of view
// (`content-visibility: auto`). The browser styles and lays out a skipped run only when
// it comes into view, a search lands in it, or a script measures it, and its text stays
// in the DOM for find-in-page, selection, copy and comments. With every row styled on
// each change to the page, a few megabytes of text would take seconds and gigabytes of
// memory to draw. A lone run stays drawn (text-document.css): skipping it
// buys nothing, and its rows would stand undrawn for the frames after the document
// scrolls into view.
/** @param {number} count */
function run(count) {
  const run = document.createElement("div");
  run.className = "lf-text-document-run";
  // A line a row until the drawn listing says how long a line is (`sizeRuns`).
  run.style.containIntrinsicBlockSize = `auto ${count}lh`;
  return run;
}

// A run counts its numbers on from its first line, which its first row holds
// (`--lf-lines-before`, text-document.css). Held by the run, it would reach every row,
// and a line added at the top of a long text would have Firefox, which styles the rows
// of runs it skips, restyle all of them. A row no longer first keeps a number the
// stylesheet doesn't read.
/** @param {Element | null | undefined} row a run's first row @param {number} first */
function number(row, first) {
  /** @type {HTMLElement | null | undefined} */ (row)?.style.setProperty(
    "--lf-lines-before",
    `${first}`,
  );
}

/** The place of the run holding line `line`, from the runs' first lines. @param {readonly number[]} firsts @param {number} line */
function runAt(firsts, line) {
  let low = 0;
  let high = firsts.length - 1;
  while (low < high) {
    const middle = (low + high + 1) >> 1;
    if (/** @type {number} */ (firsts[middle]) <= line) low = middle;
    else high = middle - 1;
  }
  return low;
}

// What a new text changes in the rows of `before`, each change `{at, removed, to,
// added}`: the `removed` rows from row `at` give way to the `added` rows of `after` from
// row `to`, in order, from a walk over whole rows capped as the runtime's text alignment
// is; null where a rewrite runs past the cap (`refill`). Two rows are the same where
// their lines and endings are. Exported for its test.
/** @typedef {{at: number, removed: number, to: number, added: number}} Change */
/** @param {Lines} before @param {Lines} after @param {number} [maxEditLength] @returns {Change[] | null} */
export function changes(before, after, maxEditLength = MAX_EDIT_LENGTH) {
  const walked = diffArrays([...before.text.keys()], [...after.text.keys()], {
    comparator: (/** @type {number} */ old, /** @type {number} */ now) =>
      before.text[old] === after.text[now] &&
      before.endings[old] === after.endings[now],
    maxEditLength,
  });
  if (!walked) return null;
  /** @type {Change[]} */
  const found = [];
  let at = 0;
  let to = 0;
  for (const { count = 0, added, removed } of walked) {
    if (!added && !removed) {
      at += count;
      to += count;
      continue;
    }
    // jsdiff puts a removed run before the added run that replaces it.
    let change = found.at(-1);
    if (!change || change.at + change.removed !== at || change.to + change.added !== to)
      found.push((change = { at, removed: 0, to, added: 0 }));
    if (removed) {
      change.removed += count;
      at += count;
    } else {
      change.added += count;
      to += count;
    }
  }
  return found;
}

// Makes the rows on the page (`code`) the rows of `after`, by `found` (`changes`), and
// returns the runs whose rows changed. A row a change replaces keeps its node, and
// takes the new row's words as its text's least edit (`setRenderedChildren`), so a
// selection in the words it keeps stays; a row past the new ones leaves, and a new row
// past the old ones stands beside the last it follows, or before the row after it.
// The changes apply last to first, so each finds its rows by the runs' first lines as
// they were. Runs are a drawing boundary, not a row's place: lines added or removed
// leave every other run's rows where they were (`regroup`). Rejected: reconciling over
// every row and moving rows so each run holds `RUN`, which makes a one-line rewrite of a
// long text a pass over every row, and carries the lines added across each later run's
// edge, the runtime hearing each row move. `firsts` is the line each run starts on.
/** @param {Element} code @param {readonly Change[]} found @param {Lines} after @param {Set<Element>} shown @param {readonly number[]} firsts */
function rewrite(code, found, after, shown, firsts) {
  const runs = [...code.children];
  const heads = runs.map((held) => held.firstElementChild);
  /** @type {Set<Element>} */
  const touched = new Set();
  for (const { at, removed, to, added } of [...found].reverse()) {
    let place = runAt(firsts, at);
    let held = /** @type {Element} */ (runs[place]);
    /** @type {Element | null} */
    let next = held.children[at - /** @type {number} */ (firsts[place])] ?? null;
    /** @type {Element | null} */
    let last = null;
    for (let line = 0; line < removed; line++) {
      while (!next && place + 1 < runs.length)
        next = (held = /** @type {Element} */ (runs[++place])).firstElementChild;
      if (!next) break;
      const old = next;
      next = old.nextElementSibling;
      touched.add(held);
      if (line < added) {
        const now = words(after, to + line);
        setRenderedChildren(old, now ? [document.createTextNode(now)] : []);
        last = old;
      } else old.remove();
    }
    if (added <= removed) continue;
    const rows = [];
    for (let line = removed; line < added; line++)
      rows.push(row(words(after, to + line)));
    if (last) last.after(...rows);
    else if (next) next.before(...rows);
    else held.append(...rows);
    touched.add(last?.parentElement ?? next?.parentElement ?? held);
  }
  return regroup(code, runs, touched, shown, firsts, heads);
}

// Past the line walk's cap, each run reconciles its rows with as many of the new
// text's rows at its place (`setRenderedChildren`), and runs of `RUN` hold the rows the
// new text adds past the old ones. The reconciliation finds a row's words wherever they
// stand in its run, so a selection on lines a rewrite reindented and moved a line stays
// on its words; patched row by row, each row took the words of the line before it.
// The cap spares a walk to the end of a large text rewritten throughout.
/** @param {Element} code @param {Lines} after @param {Set<Element>} shown @param {readonly number[]} firsts */
function refill(code, after, shown, firsts) {
  const runs = [...code.children];
  const heads = runs.map((held) => held.firstElementChild);
  const count = after.text.length;
  let line = 0;
  for (const held of runs) {
    const rows = [];
    const first = line;
    for (const end = Math.min(line + held.childElementCount, count); line < end; line++)
      rows.push(row(words(after, line)));
    // The reconciliation gives each row the new row's attributes, so the first carries
    // its number in: patched bare, it lost the number, and where the run kept its first
    // line and first row, nothing numbered it again (`regroup`).
    number(rows[0], first);
    setRenderedChildren(held, rows);
  }
  /** @type {Element[]} */
  const added = [];
  for (; line < count; line += RUN) {
    const held = run(0);
    for (let at = line; at < Math.min(line + RUN, count); at++)
      held.append(row(words(after, at)));
    added.push(held);
  }
  const all = [...runs, ...added];
  return regroup(code, all, new Set(all), shown, firsts, heads);
}

// Puts the runs (`runs`, in order) in `code` after a rewrite, numbers each whose first
// line or first row changed (`number`), and returns the runs whose rows changed
// (`touched`) and the line each run now starts on (`starts`). A run
// the rewrite `touched` folds onto the end of the run before it where the two fit in
// `RUN` rows, or where it fell under a quarter of `RUN`, and one it filled to twice
// `RUN` splits into runs of `RUN`. So the runs a session's rewrites leave are bounded by
// the text's size rather than the session's length. Both move rows (`setChildLists`,
// which keeps a selection in a
// row it moves), and a moved row lands only at a run's end or in a run the split has
// just made, never at the head of a run the page holds: Chromium drops the line number
// of a row `moveBefore` puts first in a run it skips, and numbers the rows after it
// from 1 (notes/browser-support.md). A run the browser draws (`shown`) passes that on to
// the runs its rows move into, since the browser reports their drawing only after the
// frame. `firsts` and `heads` are the first line and first row of each run before the
// rewrite.
/** @param {Element} code @param {readonly Element[]} runs @param {Set<Element>} touched @param {Set<Element>} shown @param {readonly number[]} firsts @param {readonly (Element | null)[]} heads */
function regroup(code, runs, touched, shown, firsts, heads) {
  const was = new Map(runs.map((held, at) => [held, at]));
  // A run's rows: counted where the rewrite touched it, and otherwise known from where
  // it and the run after it started, so a rewrite counts only the rows it touched.
  const size = (/** @type {Element} */ held) => {
    const at = was.get(held) ?? -1;
    const next = firsts[at + 1];
    return touched.has(held) || at < 0 || next === undefined
      ? held.childElementCount
      : next - /** @type {number} */ (firsts[at]);
  };
  // Each run that stays, with its rows where they change.
  /** @type {[Element, Element[] | null][]} */
  const folded = [];
  for (const held of runs) {
    const before = folded.at(-1);
    if (!touched.has(held) || !before) {
      if (size(held)) folded.push([held, null]);
      continue;
    }
    const count = held.childElementCount;
    if (!count) continue;
    const together = (before[1]?.length ?? size(before[0])) + count;
    if (count < RUN / 4 || together <= RUN) {
      before[1] = [...(before[1] ?? before[0].children), ...held.children];
      touched.add(before[0]);
      if (shown.has(held)) shown.add(before[0]);
    } else folded.push([held, null]);
  }
  /** @type {[Element, Element[] | null][]} */
  const placed = [];
  for (const [held, moved] of folded) {
    const rows =
      moved ??
      (touched.has(held) && held.childElementCount >= 2 * RUN
        ? [...held.children]
        : null);
    if (!rows || rows.length < 2 * RUN) {
      placed.push([held, moved]);
      continue;
    }
    // A short last part stays with the one before it.
    for (let first = 0; first < rows.length;) {
      const end = rows.length - first < RUN + RUN / 4 ? rows.length : first + RUN;
      const part = first ? run(0) : held;
      placed.push([part, rows.slice(first, end)]);
      touched.add(part);
      if (shown.has(held)) shown.add(part);
      first = end;
    }
  }
  const kept = placed.map(([held]) => held);
  /** @type {[Element, Element[]][]} */
  const lists = [];
  for (const [held, rows] of placed) if (rows) lists.push([held, rows]);
  if (
    kept.length !== code.childElementCount ||
    kept.some((held, at) => code.children[at] !== held) ||
    lists.length
  )
    setChildLists([[code, kept], ...lists]);
  const starts = [];
  let line = 0;
  for (const held of kept) {
    const at = was.get(held) ?? -1;
    if (firsts[at] !== line || heads[at] !== held.firstElementChild)
      number(held.firstElementChild, line);
    starts.push(line);
    line += size(held);
  }
  return { touched: new Set(kept.filter((held) => touched.has(held))), starts };
}

// The runs of `code` that its `pre` and the window show, found by their boxes, which a
// run has whether or not the browser draws its rows.
/** @param {Element} code */
function runsInView(code) {
  const box = code.parentElement?.getBoundingClientRect();
  const runs = [...code.children];
  if (!box) return [];
  const top = Math.max(box.top, 0);
  const bottom = Math.min(box.bottom, innerHeight);
  let low = 0;
  let high = runs.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (/** @type {Element} */ (runs[middle]).getBoundingClientRect().bottom <= top)
      low = middle + 1;
    else high = middle;
  }
  const shown = [];
  for (const run of runs.slice(low)) {
    if (run.getBoundingClientRect().top >= bottom) break;
    shown.push(run);
  }
  return shown;
}

// How many characters a line of the listing holds, and a tab's width in them: a row's
// text box over the average advance of the first run's one-line rows, as drawn. The
// face drawn need not be the one named: a freshly started Firefox sets the listing in a
// proportional fallback until its font list loads, seconds later. Null while the rows
// aren't drawn, as in a closed tab, which is asked before any box: Chromium lays a
// closed tab's rows out to answer for their width.
/** @param {Element} code */
function lineColumns(code) {
  const rows = [...(code.firstElementChild?.children ?? [])];
  const first = rows[0];
  if (!(first instanceof HTMLElement) || !code.checkVisibility() || !first.clientWidth)
    return null;
  const style = getComputedStyle(first);
  const line = parseFloat(style.lineHeight);
  const range = document.createRange();
  let width = 0;
  let characters = 0;
  for (const row of rows) {
    const text = row.textContent.replace(/\r?\n$/, "");
    if (text.length < 8 || text.includes("\t")) continue;
    if (row.getBoundingClientRect().height > line * 1.5) continue;
    range.selectNodeContents(row);
    width += range.getBoundingClientRect().width;
    characters += text.length;
    if (characters > 1000) break;
  }
  const face = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const advance = characters ? width / characters : textWidth("0", face);
  const room =
    first.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  return {
    columns: Math.max(1, Math.floor(room / advance)),
    tab: parseFloat(style.tabSize) || 8,
  };
}

// The lines a row takes in a line of `columns` characters, broken as `pre-wrap` breaks
// it: after a space, where the spaces past a line's end hang, and within a word longer
// than a line. A tab counts `tab` characters.
/** @param {string} row @param {number} columns @param {number} tab */
function rowLines(row, columns, tab) {
  if (row.length <= columns && !row.includes("\t")) return 1;
  let lines = 1;
  let used = 0;
  for (const piece of row.replaceAll("\t", " ".repeat(tab)).split(/(?<= )(?=[^ ])/)) {
    const word = piece.trimEnd().length;
    if (used && used + word > columns) {
      lines++;
      used = 0;
    }
    if (word > columns) {
      lines += Math.ceil(word / columns) - 1;
      used = word % columns || columns;
      used += piece.length - word;
    } else used += piece.length;
  }
  return lines;
}

// The height the browser gives each run until it draws it, in lines (`rowLines`). That
// is exact for a monospaced face and close for any other. A run the browser has drawn
// keeps its drawn height (`auto`). Estimated a line a row, wrapped text was thousands
// of pixels short, and End, a drag to the bottom and travel to a line each stopped
// short as the runs they passed took their real heights.
//
// A skipped run keeps the height it was last drawn at, whatever its size says, until
// its style resolves with neither `auto` nor `content-visibility: auto`. Chromium,
// Firefox and WebKit all do so, though css-sizing-4 says otherwise
// (notes/browser-support.md). Narrowed after its last runs were drawn, a long text
// can leave End short. So when the line length changes, each run the
// browser has `drawn` that is skipped now resolves its style once as `hidden` without
// `auto`, and takes both back before anything is drawn. Only those runs, since
// resolving every resized run costs Firefox far more on a large text.
// A rewrite sizes only the runs whose rows it changed (`only`).
/** @param {Element} code @param {readonly string[]} text @param {readonly number[]} starts the line each run starts on @param {{columns: number, tab: number}} length @param {WeakSet<Element>} [drawn] the runs drawn since they last forgot a height @param {ReadonlySet<Element>} [only] */
function sizeRuns(code, text, starts, { columns, tab }, drawn, only) {
  /** @type {[HTMLElement, number][]} */
  const resized = [];
  for (const [place, run] of [...code.children].entries()) {
    if (!(run instanceof HTMLElement) || (only && !only.has(run))) continue;
    let lines = 0;
    for (
      let at = starts[place] ?? 0, end = starts[place + 1] ?? text.length;
      at < end;
      at++
    )
      lines += rowLines(text[at] ?? "", columns, tab);
    if (run.style.containIntrinsicBlockSize !== `auto ${lines}lh`)
      resized.push([run, lines]);
  }
  const forgetting = resized.filter(
    ([run]) =>
      drawn?.has(run) &&
      run.firstElementChild?.checkVisibility({
        contentVisibilityAuto: true,
      }) === false,
  );
  for (const [run, lines] of forgetting) {
    drawn?.delete(run);
    run.style.contentVisibility = "hidden";
    run.style.containIntrinsicBlockSize = `${lines}lh`;
  }
  for (const [run] of forgetting) getComputedStyle(run).contentVisibility;
  for (const [run] of forgetting) run.style.removeProperty("content-visibility");
  for (const [run, lines] of resized)
    run.style.containIntrinsicBlockSize = `auto ${lines}lh`;
}

// Each token colour's highlight, registered once for every document in the page and
// named by the token theme's colour variable, which text-document.css paints. A
// highlight paints only what doesn't change layout (css-highlight-api-1), so a token
// keeps its theme colour but not its font style: a comment, italic in a code block,
// stands upright here. A token whose colour is no variable, or that has none, has no
// highlight (null). The rules are declared rather than written as each colour first
// appears: Firefox can restyle the whole page for each rule a sheet gains, which beside
// a long document delays even End's scroll.
// They rank under the comment marks (priority -1), whose ink the marked words wear
// however late a colour first appears: at equal priority the highlight registered
// last paints on top, so a string scrolled to after the marks were painted would keep
// its syntax colour inside a violet mark.
/** @type {Map<string, Highlight>} */
const tokenHighlights = new Map();
/** @param {{color?: string}} style */
function tokenHighlight(style) {
  const colour = style.color?.match(/^var\(--lf-([\w-]+)\)$/)?.[1];
  if (!colour) return null;
  let highlight = tokenHighlights.get(colour);
  if (!highlight) {
    highlight = Object.assign(new Highlight(), { priority: -1 });
    CSS.highlights.set(`lf-token-${colour}`, highlight);
    tokenHighlights.set(colour, highlight);
  }
  return highlight;
}

// Syntax colour for the runs the browser draws and their neighbours (`follow`), painted
// over their rows' text as highlights rather than spans, so the rows stay one text each
// and colour costs nothing where the reader isn't looking. A run is tokenized from the
// grammar state the run before it ended in (`syntax`), so a run starting inside a block
// comment or a fenced code block is coloured as the whole text would be. Those states
// are kept, and a run far down whose state isn't known yet is painted at once from a
// fresh state, then again once `walk` has tokenized the runs before it, a slice of the
// main thread at a time: waiting for its state, End on a large text would stand
// uncoloured for seconds. Until then only a construct open across
// the run's first line, such as a docstring, reads wrong. A new text keeps the states
// and the paint of the runs before its first changed line.
/** @typedef {{exact: boolean, ranges: [Highlight, StaticRange][]}} Paint */
class RunColours {
  /** @param {string} lang @param {(error: unknown) => void} failed */
  constructor(lang, failed) {
    this.lang = lang;
    this.failed = failed;
    /** The state each run starts in, as far down as it is known.
     * @type {Awaited<ReturnType<typeof syntax>>["state"][]} */
    this.states = [undefined];
    /** @type {Map<Element, Paint>} */
    this.painted = new Map();
    /** The runs to paint (`follow`). @type {Set<Element>} */
    this.near = new Set();
    /** @type {readonly string[]} */
    this.text = [];
    /** The line each run starts on. @type {readonly number[]} */
    this.starts = [];
    this.version = 0;
    /** @type {Promise<void>} */
    this.queue = Promise.resolve();
    this.walking = false;
  }

  // The text's lines from `from` on are new, and each run now starts on its line in
  // `starts`, which change only here, through a new text. A state stands for its run
  // while the run starts on the line it did and that line comes before the change: the
  // lines before it are the same, so the tokenizer is in the same state there. So the
  // states go from the first run that holds the change, before the new text or after
  // it, or that starts elsewhere, and the paint of the runs from there on with them. A
  // split run's later parts start mid-way through the old run, where no state was kept.
  /** @param {readonly string[]} text @param {Element} code @param {number} from @param {readonly number[]} starts */
  changed(text, code, from, starts) {
    const before = this.starts;
    this.text = text;
    this.starts = starts;
    this.version++;
    let cut =
      from === Infinity ? Infinity : Math.min(runAt(before, from), runAt(starts, from));
    // The states known: through the start of the run holding the change.
    let known = cut + 1;
    for (let at = 0; at <= cut && at < starts.length; at++)
      if (before[at] !== starts[at]) {
        cut = known = at;
        break;
      }
    this.states.length = Math.max(1, Math.min(this.states.length, known));
    const runs = [...code.children];
    this.unpaint(
      [...this.painted.keys()].filter((painted) => {
        const place = runs.indexOf(painted);
        return place < 0 || place >= cut;
      }),
    );
  }

  // Paint the runs the browser draws (`shown`) and the run on either side of each, and
  // no others, so a run scrolling into view is coloured before it shows: Firefox draws
  // a run only once it enters the view, and painted then, its first frame there stood
  // uncoloured.
  /** @param {Element} code @param {ReadonlySet<Element>} shown */
  follow(code, shown) {
    const runs = [...code.children];
    this.near.clear();
    for (const run of shown) {
      const at = runs.indexOf(run);
      if (at >= 0)
        for (const near of runs.slice(Math.max(0, at - 1), at + 2)) this.near.add(near);
    }
    this.unpaint([...this.painted.keys()].filter((run) => !this.near.has(run)));
    for (const run of this.near) if (!this.painted.has(run)) this.paint(code, run);
    this.walk(code).catch(this.failed);
  }

  /** @param {Element} code @param {Element} run */
  paint(code, run) {
    const { version } = this;
    this.queue = this.queue
      .then(() => this.#paint(code, run, version))
      .catch(this.failed);
  }

  // Paints `run` from its state where that is known, else from a fresh one, replacing
  // its paint in the same task, so it never stands uncoloured between the two.
  /** @param {Element} code @param {Element} run @param {number} version */
  async #paint(code, run, version) {
    const current = () => version === this.version && this.near.has(run);
    if (!current() || this.painted.get(run)?.exact) return;
    const at = [...code.children].indexOf(run);
    if (at < 0) return;
    const exact = at < this.states.length;
    const first = this.starts[at] ?? 0;
    const { tokens, state } = await syntax(
      this.lines(at),
      this.lang,
      exact ? this.states[at] : undefined,
    );
    if (!current() || this.painted.get(run)?.exact) return;
    if (exact && this.states.length === at + 1) this.states.push(state);
    /** @type {[Highlight, StaticRange][]} */
    const ranges = [];
    const rows = [...run.children];
    // Where each row's text starts in the run's, a newline between rows. An offset at
    // a line's end, its newline's place, stays on its line.
    let row = 0;
    let start = 0;
    const lengths = rows.map((_, index) => this.text[first + index]?.length ?? 0);
    /** @param {number} offset */
    const place = (offset) => {
      while (row < rows.length - 1 && offset > start + (lengths[row] ?? 0)) {
        start += (lengths[row] ?? 0) + 1;
        row++;
      }
      const node = rows[row]?.firstChild;
      return (
        node && {
          node,
          offset: Math.min(offset - start, node.textContent?.length ?? 0),
        }
      );
    };
    let offset = 0;
    for (const { text, style } of tokens) {
      const highlight = tokenHighlight(style);
      if (highlight) {
        const from = place(offset);
        const to = place(offset + text.length);
        if (from && to) {
          const range = new StaticRange({
            startContainer: from.node,
            startOffset: from.offset,
            endContainer: to.node,
            endOffset: to.offset,
          });
          highlight.add(range);
          ranges.push([highlight, range]);
        }
      }
      offset += text.length;
    }
    this.unpaint([run]);
    this.painted.set(run, { exact, ranges });
  }

  // Tokenizes the runs before the farthest run near the view whose state isn't known,
  // in order, yielding to input between slices, and paints each near run again once its
  // state is known. One walk at a time; a new text or view steers the walk under way.
  /** @param {Element} code */
  async walk(code) {
    if (this.walking) return;
    this.walking = true;
    try {
      let slice = performance.now();
      for (;;) {
        const runs = [...code.children];
        const known = this.states.length;
        for (const run of this.near) {
          const at = runs.indexOf(run);
          if (at >= 0 && at < known && this.painted.get(run)?.exact === false)
            this.paint(code, run);
        }
        const far = Math.max(-1, ...[...this.near].map((run) => runs.indexOf(run)));
        if (far < known) return;
        const { version } = this;
        const before = known - 1;
        const { state } = await syntax(
          this.lines(before),
          this.lang,
          this.states[before],
        );
        if (version === this.version && this.states.length === known)
          this.states.push(state);
        if (performance.now() - slice > 8) {
          await new Promise((resolve) => setTimeout(resolve));
          slice = performance.now();
        }
      }
    } finally {
      this.walking = false;
    }
  }

  // The lines of the run at `at`, as the tokenizer reads them, found by where it and
  // the next run start: counted from each run's rows instead, colouring the way to the
  // end of a long text would count every row before each run it tokenized, which
  // Chromium does one child at a time.
  /** @param {number} at */
  lines(at) {
    return this.text
      .slice(this.starts[at] ?? 0, this.starts[at + 1] ?? this.text.length)
      .join("\n");
  }

  // Takes the paint off `runs`. Each highlight it touches is rebuilt from the ranges it
  // keeps rather than losing each of its ranges in turn: Firefox finds a range to delete
  // by walking the highlight's list, so taking runs off it range by range can hold a
  // frame. The highlights hold only the ranges of the runs in
  // view and beside them, since a fold takes a closed tab's out (`fold`), so the rebuild
  // costs what the window shows.
  /** @param {Iterable<Element>} runs */
  unpaint(runs) {
    /** @type {Map<Highlight, Set<AbstractRange>>} */
    const gone = new Map();
    for (const run of runs) {
      for (const [highlight, range] of this.painted.get(run)?.ranges ?? []) {
        const ranges = gone.get(highlight) ?? new Set();
        gone.set(highlight, ranges.add(range));
      }
      this.painted.delete(run);
    }
    for (const [highlight, ranges] of gone) {
      const kept = [...highlight].filter((range) => !ranges.has(range));
      highlight.clear();
      for (const range of kept) highlight.add(range);
    }
  }

  clear() {
    this.version++;
    this.near.clear();
    this.unpaint([...this.painted.keys()]);
  }
}

// First draws the page doesn't show, as in a closed tab, made once it has presented, one
// a task in the order their updates asked (`show`). Until a document draws, a comment on
// its data stands on the document (readings/anchor-resolution.js).
/** @type {{doc: TextDocument, value: DocumentValue | null, rendering: number}[]} */
const drawingLater = [];
/** @type {Promise<void> | null} */
let drawingAfterPresentation = null;
/** @param {TextDocument} doc @param {DocumentValue | null} value @param {number} rendering */
function drawLater(doc, value, rendering) {
  drawingLater.push({ doc, value, rendering });
  drawingAfterPresentation ??= afterPresentation(async () => {
    for (let next; (next = drawingLater.shift());) {
      await new Promise((resolve) => setTimeout(resolve));
      if (next.rendering !== next.doc.rendering) continue;
      await next.doc.show(next.value, true);
    }
    drawingAfterPresentation = null;
  });
}

class TextDocument extends LeafElement {
  rendering = 0;
  // A key names a reading's datum (`mark`), or, after `preview:`, a heading of the
  // Markdown preview by its address in the file (`headingSlugs`), so a heading's
  // address never takes a datum's.
  /** @param {string} key @returns {Element[]} */
  lfElementsFor(key) {
    const preview = this.view?.preview;
    if (key.startsWith(PLACE)) {
      if (!(preview instanceof HTMLDivElement)) return [];
      const place = filePlaces(preview).get(key.slice(PLACE.length));
      return place ? [place] : [];
    }
    const datum = this.querySelector(`[data-lf-datum="${CSS.escape(key)}"]`);
    return datum ? [datum] : [];
  }
  // The language the text is coloured in (`codeLanguage`), read at setup while the
  // written `<pre>` that may name it stands: the first draw replaces the `<pre>`, and a
  // revision that names another language brings a new element. Only a document naming
  // none takes its preview's: one naming a language Leaf can't colour stays uncoloured,
  // as `page check` tells its author.
  /** @type {string | null | undefined} */
  language;
  /** @type {(() => void) | null} */
  finishFrame = null;
  /** @type {Promise<void> | undefined} */
  frameLoaded;
  /** @type {ReturnType<TextDocument["build"]> | undefined} */
  view;
  /** @type {{pre: HTMLPreElement, code: HTMLElement} | null} */
  sourceView = null;
  /** The text the listing draws. @type {Lines} */
  lines = { text: [], endings: [] };
  // The line each run starts on, counted as the runs are made or regrouped (`listing`,
  // `regroup`) rather than from their rows when a run's lines are read (`RunColours`).
  /** @type {readonly number[]} */
  starts = [];
  /** @type {{columns: number, tab: number} | null} */
  lineLength = null;
  // A new width gives the listing's lines another length, and its runs another height.
  // So can a new face, which shows where a drawn run changes height. The runs are
  // sized again in the next frame, outside the observer's delivery: sized in it as
  // Firefox's face arrives, they would resize the code it watches, and Firefox can
  // report the notification it couldn't deliver as an error. A document the page shows
  // is sized as it draws (`show`), so the observer's first delivery already sees its
  // runs at their lines' heights; left to the next frame, Firefox can report a loop of
  // undelivered notifications for a long document.
  // A hidden one is sized by the observer once its listing has a box: measured as each
  // document drew, every closed tab's listing would be a read of the page's layout, and
  // Chromium's answer can take longer for each document drawn before it.
  sizes = sizeObserver((entries) => {
    for (const { target, contentRect } of entries)
      if (target === this.view?.listing) this.list(contentRect.width > 0);
    nextFrame(() => {
      this.refit();
      this.holdSource();
      this.measureCut();
    });
  });
  // Each reading, with the press that shows the whole document where its height cuts
  // its text: the bound for the preview and for a document without one, and the
  // preview's height for the Source tab.
  /** @typedef {{panel: HTMLElement, box: HTMLElement, press: HTMLButtonElement}} Cut */
  /** @type {{preview?: Cut, source: Cut} | null} */
  cuts = null;
  // What the cuts fold (`cutText`).
  /** @type {Set<Element>} */
  tail = new Set();
  // A cut on `panel`, its press at the foot of `holder`. What the cut folds is
  // `hidden="until-found"`, so Leaf's travel to a comment on it and the browser's
  // find-in-page open it as they open any fold, firing `beforematch` first, and the
  // document shows whole before they place what they reached.
  /** @param {HTMLElement} panel @param {HTMLElement} holder @param {() => HTMLElement | undefined} shown
   * @returns {Cut} */
  cut(panel, holder, shown) {
    const box = offer("div", "lf-text-document-cut");
    box.hidden = true;
    const press = offerAction("inline", "lf-text-document-more", "");
    box.append(press);
    holder.append(box);
    press.addEventListener("click", () => {
      this.showWhole();
      const text = shown();
      if (text) focusDestination(text, "return");
    });
    panel.addEventListener("beforematch", (event) => {
      if (event.target instanceof Element && this.tail.has(event.target))
        this.showWhole(event.target);
    });
    return { panel, box, press };
  }
  // Shows the whole document in every reading, its presses gone. Whoever opens `found`,
  // the fold travel or find reached, takes its attribute off itself.
  /** @param {Element | null} [found] */
  showWhole(found = null) {
    for (const { panel, box } of Object.values(this.cuts ?? {})) {
      panel.toggleAttribute("data-lf-all", true);
      box.toggleAttribute("hidden", true);
    }
    for (const unit of this.tail) if (unit !== found) unit.removeAttribute("hidden");
    this.tail.clear();
  }
  // The Source tab takes the preview's height once the preview has shown, so switching
  // to it moves nothing below the document. A closed tab skips its contents' layout
  // (`hidden="until-found"`), so the height is read while the preview shows, after
  // each of its resizes. A document drawn on Source, as after a reload, never showed
  // its preview; it keeps the box the page first painted (`firstBox`), the written
  // source's (text-document.css), so the draw moves nothing either. Either reaches the
  // Source tab before the frame paints.
  /** @param {number | null} [firstBox] */
  holdSource(firstBox = null) {
    const preview = this.view?.preview;
    const tab = preview?.parentElement;
    if (!this.cuts?.preview || !preview || !tab) return;
    const { panel } = this.cuts.source;
    let measured;
    if (!tab.hidden) measured = preview.getBoundingClientRect().height;
    else if (firstBox !== null)
      measured =
        panel.getBoundingClientRect().height +
        firstBox -
        this.getBoundingClientRect().height;
    else return;
    panel.style.setProperty("--lf-preview-block", layoutPx(measured));
  }
  // Each reading shown folds the text its height cuts off, and shows its press only
  // while it cuts some, as a thread's quote label does. A closed tab keeps its folds
  // until it shows, since measuring it would lay out what the browser skips.
  measureCut() {
    if (!this.cuts) return;
    for (const { panel, box } of Object.values(this.cuts)) {
      if (panel.hidden) continue;
      const text =
        panel === this.cuts.preview?.panel ? this.view?.preview : this.sourceView?.code;
      box.toggleAttribute("hidden", !text || !this.cutText(panel, text));
    }
  }
  // The width and text each reading last cut at (`cutText`).
  /** @type {WeakMap<HTMLElement, {width: number, lines: Lines}>} */
  cutFor = new WeakMap();
  // Folds what of `text` stands below the foot of `panel`, whose bound clips it
  // (text-document.css): `hidden="until-found"` on the first unit that ends past the
  // foot and on every unit after it (`cut`). A unit is a block of the preview or a row
  // of the listing; the runs after the one the foot falls in fold whole. The first unit
  // stays, clipped where it alone outgrows the bound. A folded unit has no box to
  // measure, so where the reading's width or text has changed since it cut, it unfolds
  // its units and cuts again in the next frame, from what that frame lays out; the
  // bound's clip hides them meanwhile. Answers whether the panel cuts any text. A
  // reading that fills a pane scrolls instead, and cuts nothing.
  /** @param {HTMLElement} panel @param {Element} text */
  cutText(panel, text) {
    const folded = [...this.tail].filter((unit) => text.contains(unit));
    const unfold = () => {
      for (const unit of folded) {
        unit.removeAttribute("hidden");
        this.tail.delete(unit);
      }
    };
    if (panel.hasAttribute("data-lf-all") || !cutting(panel)) {
      unfold();
      return false;
    }
    const width = panel.clientWidth;
    const made = this.cutFor.get(panel);
    if (folded.length && (made?.width !== width || made?.lines !== this.lines)) {
      unfold();
      this.cutFor.delete(panel);
      nextFrame(() => this.measureCut());
      return true;
    }
    this.cutFor.set(panel, { width, lines: this.lines });
    const foot =
      panel.getBoundingClientRect().top + panel.clientTop + panel.clientHeight;
    if (text.getBoundingClientRect().bottom <= foot + 0.5) return folded.length > 0;
    /** @param {Element} unit */
    const fold = (unit) => {
      if (this.tail.has(unit)) return;
      unit.setAttribute("hidden", "until-found");
      this.tail.add(unit);
    };
    /** @param {Element} parent @param {boolean} first */
    const cutWithin = (parent, first) => {
      const units = [...parent.children];
      const at = units.findIndex(
        (unit) => unit.getBoundingClientRect().bottom > foot + 0.5,
      );
      const unit = units[at];
      if (!unit) return;
      const keep = first && at === 0;
      if (unit.classList.contains("lf-text-document-run")) cutWithin(unit, keep);
      else if (!keep) fold(unit);
      for (const after of units.slice(at + 1)) fold(after);
    };
    cutWithin(text, true);
    return true;
  }
  // The runs the browser has drawn since they last forgot a height (`sizeRuns`).
  drawn = new WeakSet();
  // The runs the browser draws now, which syntax colour paints (`RunColours`), while
  // the listing has a box (`listed`), so a document in a tab closed since the page
  // loaded takes no colour.
  /** @type {Set<Element>} */
  shown = new Set();
  listed = false;
  /** @type {RunColours | null} */
  colours = null;
  /** @param {boolean} listed */
  // As the listing takes a box, the runs it shows are read off their boxes
  // (`runsInView`), since the browser reports which runs it draws only after the frame;
  // without a box it shows none. Kept from before a fold instead, the runs a rewrite
  // made while the fold was shut, which hold the lines now in view, stood uncoloured
  // for a frame or two as it opened.
  /** @param {boolean} listed */
  list(listed) {
    if (listed === this.listed) return;
    this.listed = listed;
    const code = this.sourceView?.code;
    this.shown.clear();
    if (listed && code) for (const run of runsInView(code)) this.shown.add(run);
    this.colourShown();
  }
  // A fold closing over the listing, a closed tab's panel or a shut details, takes the
  // colour of its runs out of the highlights every document shares. The fold makes the
  // runs `visible` (text-document.css), so they report nothing as it closes, but the
  // rows stop meeting their `pre`, which an intersection observer reports after the
  // frame (`show`). Kept, the colour of every tab a reader had opened would stand in
  // those highlights for the rest of the session, and the ranges they hold, growing with
  // each tab opened, would slow uncolouring (`unpaint`) and hit tests at every scroll
  // step. A size
  // observer reports only a change from the size it last reported, and the fold opens
  // at that size, so the listing is observed afresh: the observer then reports its box
  // before the frame that shows it paints, and the runs in view are coloured in that
  // frame (`list`), as they would be if the fold kept their colour.
  fold() {
    const listing = this.view?.listing;
    if (!listing) return;
    this.list(false);
    this.sizes.unobserve(listing);
    this.sizes.observe(listing);
  }
  colourShown() {
    const code = this.sourceView?.code;
    if (code) this.colours?.follow(code, this.listed ? this.shown : new Set());
  }
  // Size the drawn runs again where the listing's line length changed.
  refit() {
    const code = this.sourceView?.code;
    const length = code && lineColumns(code);
    const last = this.lineLength;
    if (!length || (length.columns === last?.columns && length.tab === last.tab))
      return;
    this.lineLength = length;
    sizeRuns(code, this.lines.text, this.starts, length, this.drawn);
  }

  setup() {
    this.language = codeLanguage(this);
    // A departure abandons the rendering in flight and its frame's wait, and the
    // colour of the runs it drew, which a return draws again as they show.
    whileConnected(this, () => {
      this.showLone();
      return () => {
        this.rendering = this.rendering + 1;
        this.finishFrame?.();
        this.colours?.clear();
        this.shown.clear();
      };
    });
  }

  // The text, set by whoever hosts the widget: Leaf from the bound source or output
  // (the registry's `inputs.document.property`), or from the written `<pre>`; null
  // while a bound source has none.
  static properties = { value: { attribute: false } };

  constructor() {
    super();
    this.addEventListener(
      "contentvisibilityautostatechange",
      (event) => {
        const { skipped, target } =
          /** @type {ContentVisibilityAutoStateChangeEvent} */ (event);
        if (!(target instanceof Element)) return;
        if (!skipped) this.drawn.add(target);
        const code = this.sourceView?.code;
        if (target.parentElement !== code) return;
        // A run reported skipped while it stands in view stays shown, read off the
        // boxes as `list` reads them. As a tab opens again, Chromium reports the runs
        // in view skipped before it draws them, and its report that they draw can
        // come after the frame that does.
        if (skipped) {
          if (runsInView(code).includes(target)) return;
          this.shown.delete(target);
        } else this.shown.add(target);
        this.colourShown();
      },
      { capture: true },
    );
    /** @type {DocumentValue | null} */
    this.value = null;
  }

  // A lone run is never skipped (`run`), so no change of state says it shows.
  showLone() {
    const code = this.sourceView?.code;
    const run = code?.childElementCount === 1 ? code.firstElementChild : null;
    if (!code || !run) return;
    this.shown.add(run);
    this.colourShown();
  }

  render() {
    return nothing;
  }

  // Highlighting and the preview load after the draw; `updateComplete` waits for
  // them, as a Lit element's completion does for work its update starts.
  /** @param {import("lit").PropertyValues} changed */
  updated(changed) {
    super.updated(changed);
    this.showing = this.show(this.value);
  }

  // Also waits for the drawing the latest update started: a newer update's drawing
  // replaces one still pending.
  async getUpdateComplete() {
    const result = await super.getUpdateComplete();
    await this.showing;
    return result;
  }

  // The markup each block of the Markdown preview was drawn from (`preparePreview`).
  /** @type {WeakMap<Node, string>} */
  drawnFrom = new WeakMap();
  // The value the Markdown preview draws, set in the task that draws it, so a gesture
  // on the preview reads the text it shows though a newer value is still drawing.
  /** @type {DocumentValue | null} */
  previewed = null;
  // Whether the latest first click on the Markdown preview went to a link or control in
  // it, which a double-click there must not begin with (`editAtLine`).
  clickedControl = false;

  // The words a plain primary press on the Markdown preview lands on, as a caret in
  // their text, with the file the preview draws, when `for` names the widget holding
  // the file. Null for a press on a link, a control or a picture, and for a preview
  // bound otherwise.
  /** @param {MouseEvent} event */
  wordsAt(event) {
    const value = this.previewed;
    const preview = this.view?.preview;
    if (
      typeof value !== "object" ||
      !value?.key ||
      !preview ||
      !plainPress(event) ||
      !this.hasAttribute("for") ||
      aimedAt(event, preview) !== preview
    )
      return null;
    const caret = document.caretPositionFromPoint(event.clientX, event.clientY);
    return caret?.offsetNode instanceof Text
      ? { key: value.key, name: value.name, text: value.text, preview, caret }
      : null;
  }

  // Puts the editor's caret at the start of the double-clicked word's line in the
  // file. The dialect's alignment of rendered words to source finds the word in the
  // file (`markdownSourceOffset`), reading the file's HTML as the preview draws it
  // (`markdownFileFragment`), and the widget `for` names reveals `<key>:<line>`,
  // as the file editor does for a link to that line (lf-file-editor.js,
  // `lfRevealDatum`). The widget is assumed to answer such a key: the file editor is
  // the one widget whose `text-document` value names a file by `key`. A double-click
  // whose first click followed a link acts no further, though the link scrolled other
  // words under its second press.
  /** @param {MouseEvent} event */
  editAtLine(event) {
    const words = this.clickedControl ? null : this.wordsAt(event);
    const offset =
      words &&
      markdownSourceOffset(
        words.preview,
        words.text,
        words.caret.offsetNode,
        words.caret.offset,
        true,
      );
    if (!words || offset === null) return;
    const line = words.text.slice(0, offset).split(/\r\n|\r|\n/).length;
    void navigateToDatum(this, "for", `${words.key}:${line}`, {
      missing: `${words.name} is no longer available.`,
    });
  }

  // The Markdown preview's next children. A block whose markup is unchanged stands as a
  // copy of the block already drawn for it, its code coloured and formulas typeset
  // (`dressCode`); a changed block is dressed before it stands, so the reconciliation
  // keeps every node the text leaves as it was, and any selection in it, and the
  // dressing costs only what the text changed. A first draw stands undressed, and
  // `show` dresses it in place. The file reads with its HTML (`markdownFileFragment`),
  // and as GitHub's rendering of the file answers them, a
  // link the file makes to one of its own places names that place in the preview
  // (`filePlaces`), and a picture or a file it names by a path is the one beside the
  // file, where the page binds the file (`boundFile`). A link to another file opens
  // it in a new tab, as a link that leaves the page does (`pageLinks`). Any other
  // fragment names the page's own place. A fold the text changed inside stays as the
  // reader left it.
  /** @param {string} source @param {string | null} file @param {string | null} binding @param {number} rendering */
  async preparePreview(source, file, binding, rendering) {
    const content = await markdownFileFragment(source, pageLinks);
    for (const element of content.querySelectorAll("[id], a[name]")) {
      const name = element.getAttribute("id") ?? element.getAttribute("name") ?? "";
      element.removeAttribute("id");
      if (element.localName === "a") element.removeAttribute("name");
      element.setAttribute("data-lf-place", name);
    }
    const places = filePlaces(content);
    for (const link of content.querySelectorAll('a[href^="#"]')) {
      const name = (link.getAttribute("href") ?? "").slice(1);
      if (this.id && name && places.has(slugWords(name)))
        link.setAttribute("href", `#${this.id}:${PLACE}${name}`);
    }
    const files = binding ? boundFile(binding) : null;
    if (files) {
      // A reference with no scheme or root of its own, as `docs/guide.md` or
      // `../logo.svg`, names a file by its path from the bound file's folder.
      /** @param {string | null} reference */
      const beside = (reference) => {
        if (reference === null || URL.parse(reference) || /^[/?#]/.test(reference))
          return null;
        const path = reference.split(/[?#]/)[0];
        if (!path) return null;
        try {
          return files.beside(decodeURIComponent(path));
        } catch {
          return files.beside(path);
        }
      };
      for (const link of content.querySelectorAll("a[href]:not([href^='#'])")) {
        const href = beside(link.getAttribute("href"));
        if (!href) continue;
        link.setAttribute("href", href);
        link.setAttribute("target", "_blank");
      }
      for (const image of content.querySelectorAll("img[src]")) {
        const src = beside(image.getAttribute("src"));
        if (src) image.setAttribute("src", src);
      }
      for (const option of content.querySelectorAll("img[srcset], source[srcset]"))
        option.setAttribute(
          "srcset",
          srcsetCandidates(option.getAttribute("srcset") ?? "")
            .map(([url, size]) => [beside(url) ?? url, size].filter(Boolean).join(" "))
            .join(", "),
        );
    }
    const fresh = [...content.childNodes];
    const markups = fresh.map(drawnMarkup);
    const drawn = this.view?.preview;
    // Another file draws afresh, its folds as it writes them.
    if (
      !(drawn instanceof HTMLDivElement) ||
      !drawn.hasChildNodes() ||
      fileOf(this.previewed) !== file
    )
      return { nodes: fresh, markups };
    /** @type {Map<string, ChildNode[]>} */
    const standing = new Map();
    for (const node of drawn.childNodes) {
      const markup = this.drawnFrom.get(node);
      if (markup === undefined) continue;
      const nodes = standing.get(markup);
      if (nodes) nodes.push(node);
      else standing.set(markup, [node]);
    }
    /** @type {Map<string, number>} */
    const taken = new Map();
    const nodes = fresh.map((node, at) => {
      const markup = markups[at] ?? "";
      const count = taken.get(markup) ?? 0;
      taken.set(markup, count + 1);
      return standing.get(markup)?.[count]?.cloneNode(true) ?? node;
    });
    // A fold stays as the reader left it where the text changed inside it: it takes
    // the state of the fold drawn with the same summary, the first of them for the
    // first, since a block the text changed is drawn afresh.
    /** @type {Map<string, HTMLDetailsElement[]>} */
    const shown = new Map();
    for (const fold of drawn.querySelectorAll("details")) {
      const summary = fold.querySelector(":scope > summary")?.textContent ?? "";
      const folds = shown.get(summary);
      if (folds) folds.push(fold);
      else shown.set(summary, [fold]);
    }
    for (const node of nodes)
      if (node instanceof Element)
        for (const fold of [
          ...(node.localName === "details" ? [node] : []),
          ...node.querySelectorAll("details"),
        ]) {
          const summary = fold.querySelector(":scope > summary")?.textContent ?? "";
          const was = shown.get(summary)?.shift();
          if (was) fold.toggleAttribute("open", was.open);
        }
    await Promise.all(
      nodes
        .filter((node, at) => node === fresh[at] && node instanceof Element)
        .map((node) => dressCode(/** @type {Element} */ (node))),
    );
    return rendering === this.rendering ? { nodes, markups } : null;
  }

  /** @param {DocumentValue | null} value @param {boolean} [presented] whether this draw waited for the page to present */
  async show(value, presented = false) {
    const rendering = this.rendering + 1;
    this.rendering = rendering;
    const source = typeof value === "string" ? value : (value?.text ?? "");
    const name = typeof value === "string" ? null : (value?.name ?? null);
    // The file's identity: its stable key where the value gives one, else its name.
    const file = fileOf(value);
    // The binding of a file the page binds, which a bound file's value and its
    // editor's name by `key`.
    const binding = typeof value === "string" ? null : (value?.key ?? null);
    const preview = this.getAttribute("preview");
    try {
      if (preview) await import("./lf-tabs.js");
      const language = this.language === undefined ? preview : this.language;
      if (language) await ensureSyntaxLanguage(language);
      if (preview === "markdown") {
        let failure;
        if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
      }
      // A document the page shows draws at once; one it doesn't, as in a closed tab,
      // first draws once the page has presented (`drawLater`), and this update
      // completes without it: the page counts the draws as an arrival. Drawn in page
      // order, a reload on the last of many tabs would show its document only after all
      // the documents before it. Drawn before presentation, they would hold it back, and
      // Firefox, which styles a closed tab's rows too, would restyle every one of them as
      // the page presented.
      if (!this.sourceView) {
        this.listed = this.checkVisibility();
        if (!this.listed && !presented) return drawLater(this, value, rendering);
      }
      // The Markdown preview's next children, prepared before this draw writes
      // anything, so the source rows, the preview and the marks naming their revision
      // change together in one task (`preparePreview`).
      const blocks =
        preview === "markdown"
          ? await this.preparePreview(source, file, binding, rendering)
          : null;
      if (rendering !== this.rendering || !this.isConnected) return;
      const next = lines(source);
      const { text } = next;
      if (this.colours?.lang !== language) {
        this.colours?.clear();
        this.colours = language
          ? new RunColours(language, (error) => {
              if (this.isConnected)
                this.dispatchEvent(
                  new ErrorEvent("error", {
                    error,
                    bubbles: true,
                    composed: true,
                  }),
                );
            })
          : null;
      }
      const view = (this.view ??= this.build(preview));
      const label =
        this.getAttribute("label") ??
        name ??
        this.getAttribute("source") ??
        this.getAttribute("for");
      keepsText(view.caption, value == null ? `${label} · no data` : label);
      // An HTML preview's frame is named by the same label, the file's name included.
      if (view.preview instanceof HTMLIFrameElement)
        keeps(view.preview, "title", `${label} preview`);
      const previous = this.lines;
      this.lines = next;
      // The first line the new text changes, past the end where it changes none.
      let from = 0;
      if (!this.sourceView) {
        const { pre, code, starts } = listing(next);
        this.starts = starts;
        setChildren(view.listing, [pre]);
        this.sourceView = { pre, code };
        // The rows meet the `pre` while it shows them, and stop as a fold closes over
        // them (`fold`), or as the document leaves the page.
        new IntersectionObserver(
          (entries) => {
            if (entries.at(-1)?.isIntersecting === false) this.fold();
          },
          { root: pre },
        ).observe(code);
        this.sizes.observe(view.listing);
        this.sizes.observe(code);
        if (this.cuts?.preview && view.preview) {
          this.sizes.observe(this.cuts.preview.panel);
          this.sizes.observe(this.cuts.source.panel);
          this.sizes.observe(view.preview);
        } else this.cuts = { source: this.cut(pre, view.listing, () => pre) };
      } else {
        // The pre owns provenance and scroll; the code owns its native reach stop.
        // Rewrite only their source rows, leaving those independent owners in place
        // while unchanged lines keep their text nodes and selection.
        const { pre, code } = this.sourceView;
        const found = changes(previous, next);
        if (found) from = found[0]?.to ?? Infinity;
        else
          while (
            from < text.length &&
            previous.text[from] === text[from] &&
            previous.endings[from] === next.endings[from]
          )
            from++;
        const { touched, starts } = found
          ? rewrite(code, found, next, this.shown, this.starts)
          : refill(code, next, this.shown, this.starts);
        this.starts = starts;
        if (this.lineLength)
          sizeRuns(code, text, starts, this.lineLength, this.drawn, touched);
        if (pre.style.getPropertyValue("--lf-number-digits") !== digits(next))
          pre.style.setProperty("--lf-number-digits", digits(next));
      }
      const { code } = this.sourceView;
      for (const run of [...this.shown])
        if (run.parentElement !== code) this.shown.delete(run);
      if (this.colours) {
        this.colours.changed(text, code, from, this.starts);
        this.colourShown();
      }
      // Every press shows the same document, so they say the same: how long it is.
      for (const { press } of Object.values(this.cuts ?? {}))
        keepsText(press, `Show all ${text.length} lines`);
      let loaded = this.frameLoaded;
      const previewNode = view.preview;
      if (previewNode instanceof HTMLDivElement && blocks) {
        setRenderedChildren(previewNode, blocks.nodes);
        previewNode.childNodes.forEach((node, at) =>
          this.drawnFrom.set(node, blocks.markups[at] ?? ""),
        );
        this.previewed = value;
      } else if (
        previewNode instanceof HTMLIFrameElement &&
        (!previewNode.isConnected ||
          !previewNode.hasAttribute("srcdoc") ||
          previewNode.srcdoc !== source)
      ) {
        this.finishFrame?.();
        loaded = this.frameLoaded = new Promise((resolve) => {
          const finish = () => {
            previewNode.removeEventListener("load", finish);
            if (this.finishFrame === finish) this.finishFrame = null;
            resolve(undefined);
          };
          this.finishFrame = finish;
          previewNode.addEventListener("load", finish);
        });
        if (!previewNode.hasAttribute("srcdoc") || previewNode.srcdoc !== source)
          previewNode.srcdoc = source;
      }
      const firstBox =
        this.cuts && !view.figure.isConnected
          ? this.getBoundingClientRect().height
          : null;
      setChildren(this, [view.figure]);
      // The preview's code is coloured and its formulas typeset, as a Markdown body's
      // are, once it stands in the page, whose face decides its colour.
      const dressed =
        previewNode instanceof HTMLDivElement ? dressCode(previewNode) : null;
      this.showLone();
      if (this.listed) this.refit();
      // Reports the draw: marks its text's items for whoever hosts the widget, in the
      // turn that announces them (`drawn`), so on a Leaf page comments on them anchor to
      // the document's data.
      if (view.preview) {
        mark(this.sourceView.pre, "source", file);
        mark(view.preview, "preview", file);
      } else mark(view.figure, "document", file);
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      if (loaded) await loaded;
      if (rendering !== this.rendering || !this.isConnected) return;
      this.classList.toggle("lf-rendered", true);
      // Measured once drawn, since until then the host wears the source face
      // (reading.css), and before the dressing lands, in the task that drew the
      // document, so a reload on the Source tab moves nothing.
      this.holdSource(firstBox);
      await dressed;
    } catch (error) {
      if (rendering !== this.rendering || !this.isConnected) return;
      failSoft(this, error, source);
    }
  }

  /** @param {string | null} preview
   * @returns {{figure: HTMLElement, caption: HTMLElement, listing: HTMLDivElement, preview: HTMLElement | null}} */
  build(preview) {
    const figure = document.createElement("figure");
    figure.className = "lf-text-document-view";
    const caption = document.createElement("figcaption");
    const listing = document.createElement("div");
    listing.className = "lf-text-document-listing lf-ring-frame";
    listing.toggleAttribute("data-lf-scroll", true);
    figure.append(caption);
    if (!preview) {
      figure.append(listing);
      return { figure, caption, listing, preview: null };
    }
    const tabs = document.createElement("lf-tabs");
    tabs.id = `${this.id}--views`;
    // Its members are this document's data readings, not authored page content.
    keeps(tabs, "data-lf-gen", "1");
    const bound = this.getAttribute("data-lf-bound") ?? "start";
    const rendered = document.createElement("lf-tab");
    rendered.id = `${this.id}--preview`;
    rendered.setAttribute("label", "Preview");
    rendered.setAttribute("data-lf-bound", bound);
    const literal = document.createElement("lf-tab");
    literal.id = `${this.id}--source`;
    literal.setAttribute("label", "Source");
    literal.setAttribute("data-lf-bound", bound);
    const drawn =
      preview === "html"
        ? document.createElement("iframe")
        : document.createElement("div");
    drawn.className = "lf-text-document-preview";
    if (drawn instanceof HTMLIFrameElement)
      drawn.setAttribute("sandbox", "allow-scripts");
    else {
      // A first click is read as it descends, since a link's own handler may stop it.
      // `aimedAt` answers null for a click on selected words, where a double-click may
      // also begin.
      drawn.addEventListener(
        "click",
        (event) => {
          if (event.detail !== 1) return;
          const aim = aimedAt(event, drawn);
          this.clickedControl = aim !== null && aim !== drawn;
        },
        { capture: true },
      );
      // A double-click's second press selects no word, which would stand selected in
      // the preview as the editor takes the caret.
      drawn.addEventListener("mousedown", (event) => {
        if (event.detail > 1 && !this.clickedControl && this.wordsAt(event))
          event.preventDefault();
      });
      drawn.addEventListener("dblclick", (event) => this.editAtLine(event));
    }
    rendered.append(drawn);
    literal.append(listing);
    // A press moves focus to the text it showed.
    this.cuts = {
      preview: this.cut(rendered, rendered, () => rendered),
      source: this.cut(literal, literal, () => this.sourceView?.pre),
    };
    tabs.append(rendered, literal);
    figure.append(tabs);
    return { figure, caption, listing, preview: drawn };
  }
}
customElements.define("lf-text-document", TextDocument);
