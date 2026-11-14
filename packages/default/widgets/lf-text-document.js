/* A document owns one text and its source/preview readings. The text is its `value`,
 * which Leaf sets from a bound source or widget output, or from the `<pre>` the page
 * wrote when the markup binds neither (element-data.js, "Bound values"). Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. Each reading has its own bounded
 * viewport, which keeps its scroll place independent, and switching keeps the page
 * still. Where the text can arrive after first paint, the viewport is `--lf-bound`
 * tall. A Markdown preview of written text instead takes its rendered height, which
 * its first paint already holds (`x-prepaint`), and its Source tab takes the same
 * height (`holdSource`), drawn on it or switched to it. Where that height cuts the
 * source, a press shows every line (`cut`), as a thread's Full quote shows a whole
 * quote: a reflow the reader asks for. The cut box doesn't scroll, so the press is the
 * one way to the rest, and stays at the box's foot rather than scrolling off with the
 * lines.
 * The source reading is a numbered listing of plain rows, one a line (`listing`), so
 * every document's whole text stands in the page for find-in-page, selection, copy
 * and comments, in a tab nobody has opened too; held back until its tab opened, a
 * document's text would be out of Find's reach. Line numbers are generated content
 * (text-document.css), so selecting or copying the source never includes them. The
 * rows stand in runs that the browser draws only in view (`inRuns`), each sized ahead
 * of drawing by the lines its rows fill (`sizeRuns`), and syntax colour is painted on
 * the runs in view alone, as highlights over their text (`RunColours`). Built whole,
 * with a span for each token and a gutter cell for each number, 30 documents of 4 MB
 * took 23 s and 8.6 GB to show the one in view. The Markdown preview renders a file,
 * whose soft line breaks are spaces, so a paragraph wraps to the preview's width. The
 * source and Markdown renderers reconcile unchanged text across source updates, the
 * source's rows across the whole listing (`reconcileRuns`). HTML lives in a separate
 * frame so its styles and scripts cannot access Leaf’s document. Source provenance is
 * stamped with its text before awaiting the frame's presentation. */
import { nothing } from "/vendor/lit.js";
import {
  failSoft,
  ensureSyntaxLanguage,
  keeps,
  LeafElement,
  whileConnected,
  keepsText,
  setRenderedChildren,
  setChildLists,
  setChildren,
  focusDestination,
  keepsHidden,
  generatedElement,
  offer,
  offerAction,
  loadMarkdown,
  renderMarkdown,
  reportFailure,
  sizeObserver,
  layoutPx,
  syntax,
  textWidth,
  nextFrame,
  MAX_EDIT_LENGTH,
  afterPresentation,
} from "/runtime/widget-api.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

// A Markdown preview of text written in the page, whose rendering sets the box both
// tabs share (text-document.css).
const WRITTEN = '[preview="markdown"]:not([source], [for])';

// Each reading shows the same document whatever text its source holds, so its key is
// also its identity (projection/data.js). A comment on a passage then follows the
// passage's words across replacements, and stays marked while they still stand.
/** @param {HTMLElement} node @param {string} key */
const mark = (node, key) => {
  keeps(node, "data-lf-datum", key);
  keeps(node, "data-lf-identity", key);
};

// Rows per run: several times the lines a document's box shows, so the runs in view
// are cheap to draw and colour, and a megabyte of text makes about 150 runs.
const RUN = 128;

// The source as the listing draws it: a `pre`, which owns scroll and provenance,
// holding a `code`, which owns the native reach stop, holding the rows in runs (`inRuns`).
// A row is one line's text and its ending, exactly as the source has them, so the
// listing's text is the source, a final newline (or its absence) included; its number
// is its place, counted in the stylesheet. `text` is the lines without their endings.
/** @param {string} source */
function listing(source) {
  const text = source.split(/\r\n|\r|\n/);
  const endings = source.match(/\r\n|\r|\n/g) ?? [];
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  // Every number takes the width of the text's widest one, so every row's text starts
  // at the same x.
  pre.style.setProperty("--lf-number-digits", `${String(text.length).length}`);
  pre.append(code);
  const rows = text.map((line, at) => {
    const row = document.createElement("div");
    const words = line + (endings[at] ?? "");
    if (words) row.append(words);
    return row;
  });
  inRuns(code, rows);
  return { pre, code, text };
}

// Groups the rows into runs, each a box the browser skips while it is out of view
// (`content-visibility: auto`). The browser styles and lays out a skipped run only
// when it comes into view, a search lands in it, or a script measures it, and its text
// stays in the DOM for find-in-page, selection, copy and comments. When every row was
// styled on each change to the page, a few megabytes of text took tens of seconds and
// gigabytes of memory to draw. A lone run stays drawn (text-document.css): skipping it
// buys nothing, and its rows would stand undrawn for the frames after the document
// scrolls into view. Each run counts its numbers on from the lines before it
// (`--lf-lines-before`, text-document.css).
/** @param {Element} code @param {readonly Element[]} rows */
function inRuns(code, rows) {
  for (let first = 0; first < rows.length; first += RUN) {
    const run = document.createElement("div");
    run.className = "lf-text-document-run";
    const count = Math.min(RUN, rows.length - first);
    // A line a row until the drawn listing says how long a line is (`sizeRuns`).
    run.style.containIntrinsicBlockSize = `auto ${count}lh`;
    run.style.setProperty("--lf-lines-before", `${first}`);
    run.append(...rows.slice(first, first + count));
    code.append(run);
  }
}

// Which line of `before` each line of `after` stands for, or -1 for a line it adds,
// from a walk over whole lines capped as the runtime's text alignment is; null where a
// rewrite runs past the cap. A run of lines replaced by as many others stands for them
// one for one, so an edited line keeps the row of the line it replaced. Exported for
// its test.
/** @param {readonly string[]} before @param {readonly string[]} after @param {number} [maxEditLength] @returns {number[] | null} */
export function keptLines(before, after, maxEditLength = MAX_EDIT_LENGTH) {
  const changes = diffArrays([...before], [...after], { maxEditLength });
  if (!changes) return null;
  const kept = after.map(() => -1);
  let from = 0;
  let to = 0;
  // jsdiff puts a removed run before the added run that replaces it.
  let removed = 0;
  for (const { count = 0, added, removed: gone } of changes) {
    if (gone) {
      removed = count;
      from += count;
      continue;
    }
    if (added) {
      if (count === removed)
        for (let line = 0; line < count; line++) kept[to + line] = from - count + line;
      to += count;
    } else for (const end = to + count; to < end;) kept[to++] = from++;
    removed = 0;
  }
  return kept;
}

// Reconciles a new text's runs (`drawn`) into the runs on the page (`code`), as a
// drawing boundary rather than a row's identity: each row the new text keeps first
// moves into the run the new text puts it in (`setChildLists`, which keeps a selection
// in it), and each run then reconciles its rows (`setRenderedChildren`), finding its
// kept rows in place. An edited line keeps the row of the line it replaced, so its
// text is patched in place. A row's number is its place, so it follows the row.
// Reconciled run by run alone, a row that lines added above it carried across a run's
// edge was drawn anew, and a selection in it was lost, or grew to take in the row
// before it. Where a rewrite runs past the line walk's cap (`keptLines`), nothing moves
// and each run reconciles its own rows: walked to the end, every line of 4 MB
// rewritten took 285 s.
/** @param {Element} code @param {Element} drawn @param {readonly string[]} before @param {readonly string[]} after */
function reconcileRuns(code, drawn, before, after) {
  const held = [...code.children];
  const kept = keptLines(before, after);
  const fresh = [...drawn.children];
  const runs = fresh.map((run, at) => {
    const live = held[at];
    if (live) return live;
    const shell = /** @type {Element} */ (run.cloneNode(false));
    code.append(shell);
    return shell;
  });
  if (kept) {
    const lines = held.flatMap((run) => [...run.children]);
    let line = 0;
    setChildLists(
      runs.map((run, at) => {
        const rows = kept
          .slice(line, (line += fresh[at]?.childElementCount ?? 0))
          .filter((row) => row >= 0);
        return [run, rows.flatMap((row) => lines[row] ?? [])];
      }),
    );
  }
  runs.forEach((run, at) => setRenderedChildren(run, fresh[at]?.childNodes ?? []));
  setChildren(code, runs);
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
    const text = row.textContent?.replace(/\r?\n$/, "") ?? "";
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
// left End 240 to 1,834 px short. So when the line length changes, each run the
// browser has `drawn` that is skipped now resolves its style once as `hidden` without
// `auto`, and takes both back before anything is drawn. Only those runs: the
// resolution cost Firefox about 60 ms on 4 MB, and 426 ms over every resized run.
/** @param {Element} code @param {readonly string[]} text @param {{columns: number, tab: number}} length @param {WeakSet<Element>} [drawn] the runs drawn since they last forgot a height */
function sizeRuns(code, text, { columns, tab }, drawn) {
  /** @type {[HTMLElement, number][]} */
  const resized = [];
  let line = 0;
  for (const run of code.children) {
    if (!(run instanceof HTMLElement)) continue;
    let lines = 0;
    for (const end = line + run.childElementCount; line < end; line++)
      lines += rowLines(text[line] ?? "", columns, tab);
    if (run.style.containIntrinsicBlockSize !== `auto ${lines}lh`)
      resized.push([run, lines]);
  }
  const forgetting = resized.filter(
    ([run]) =>
      drawn?.has(run) &&
      run.firstElementChild?.checkVisibility({ contentVisibilityAuto: true }) === false,
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
// appears: Firefox restyled the whole page for each rule a sheet gained, 0.85 s a rule
// beside a long document, and End there showed its scroll 1.5 s after the press.
// They rank under the comment marks (priority -1), whose ink the marked words wear
// however late a colour first appears: at equal priority the highlight registered
// last paints on top, and a string scrolled to after the marks were painted kept its
// syntax colour inside a violet mark.
/** @type {Map<string, Highlight>} */
const tokenHighlights = new Map();
/** @param {{color?: string}} style */
function tokenHighlight(style) {
  const colour = style.color?.match(/^var\(--([\w-]+)\)$/)?.[1];
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
// main thread at a time: waiting for its state, End on 4 MB of Python stood uncoloured
// for 2.1 s in Chromium and 18.5 s in Firefox. Until then only a construct open across
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
    this.version = 0;
    /** @type {Promise<void>} */
    this.queue = Promise.resolve();
    this.walking = false;
  }

  // The text's lines from `from` on are new: the paint and states past that run go.
  /** @param {readonly string[]} text @param {Element} code @param {number} from */
  changed(text, code, from) {
    this.text = text;
    this.version++;
    const run = Math.floor(from / RUN);
    this.states.length = Math.min(this.states.length, run + 1);
    const runs = [...code.children];
    this.unpaint(
      [...this.painted.keys()].filter((painted) => {
        const place = runs.indexOf(painted);
        return place < 0 || place >= run;
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
    const lengths = rows.map((_, index) => this.text[at * RUN + index]?.length ?? 0);
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

  /** The lines of the run at `at`, as the tokenizer reads them. @param {number} at */
  lines(at) {
    return this.text.slice(at * RUN, (at + 1) * RUN).join("\n");
  }

  // Takes the paint off `runs`. Each highlight it touches is rebuilt from the ranges it
  // keeps rather than losing each of its ranges in turn: Firefox finds a range to delete
  // by walking the highlight's list, and taking two runs scrolled out of view off it
  // held a frame for over 100 ms.
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
// its data stands on the document (anchor-resolution.js).
/** @type {{doc: TextDocument, value: string | null, rendering: number}[]} */
const drawingLater = [];
/** @type {Promise<void> | null} */
let drawingAfterPresentation = null;
/** @param {TextDocument} doc @param {string | null} value @param {number} rendering */
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
  /** @type {(() => void) | null} */
  finishFrame = null;
  /** @type {Promise<void> | undefined} */
  frameLoaded;
  /** @type {ReturnType<TextDocument["build"]> | undefined} */
  view;
  /** @type {{pre: HTMLPreElement, code: HTMLElement} | null} */
  sourceView = null;
  /** @type {readonly string[]} */
  text = [];
  /** @type {{columns: number, tab: number} | null} */
  lineLength = null;
  // A new width gives the listing's lines another length, and its runs another height.
  // So can a new face, which shows where a drawn run changes height. The runs are
  // sized again in the next frame, outside the observer's delivery: sized in it when
  // Firefox's face arrived, they resized the code it watches, and Firefox reported the
  // notification it couldn't deliver as an error. A document the page shows is sized
  // as it draws (`show`), so the observer's first delivery already sees its runs at
  // their lines' heights; left to the next frame, Firefox on Linux CI reported a loop
  // of undelivered notifications for a long document.
  // A hidden one is sized by the observer once its listing has a box: measured as each
  // document drew, every closed tab's listing was a read of the page's layout, and
  // Chromium's answer took longer for each document drawn before it, 0.8 s over 30
  // documents of 4 MB.
  sizes = sizeObserver((entries) => {
    for (const { target, contentRect } of entries)
      if (target === this.view?.listing) this.list(contentRect.width > 0);
    nextFrame(() => {
      this.refit();
      this.holdSource();
      this.measureCut();
    });
  });
  // A written preview's Source tab, which shows what the preview's height holds, and
  // the press that shows the rest where that height cuts the source.
  /** @type {{panel: HTMLElement, box: HTMLElement, press: HTMLButtonElement} | null} */
  cut = null;
  // The Source tab takes the preview's height, so switching to it moves nothing below
  // the document. A closed tab skips its contents' layout (`hidden="until-found"`), so
  // the height is read while the preview shows, after each of its resizes. A document
  // drawn on Source, as after a reload, never showed its preview; it keeps the box the
  // page first painted (`firstBox`), which holds the preview's rendering (`x-prepaint`).
  // Either reaches the Source tab before the frame paints.
  /** @param {number | null} [firstBox] */
  holdSource(firstBox = null) {
    const preview = this.view?.preview;
    const tab = preview?.parentElement;
    if (!this.cut || !preview || !tab) return;
    const { panel } = this.cut;
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
  // The press shows only while the box cuts lines off, as a thread's Full quote does.
  measureCut() {
    if (!this.cut) return;
    const { panel, box } = this.cut;
    keepsHidden(
      box,
      panel.hidden ||
        panel.hasAttribute("data-lf-all") ||
        panel.scrollHeight <= panel.clientHeight + 1,
    );
  }
  // The runs the browser has drawn since they last forgot a height (`sizeRuns`).
  drawn = new WeakSet();
  // The runs the browser draws now, which syntax colour paints (`RunColours`), while
  // the listing has a box (`listed`). Firefox reports the runs of a closed tab's
  // listing drawn, and every document in a closed tab was coloured as the page loaded.
  /** @type {Set<Element>} */
  shown = new Set();
  listed = false;
  /** @type {RunColours | null} */
  colours = null;
  /** @param {boolean} listed */
  list(listed) {
    if (listed === this.listed) return;
    this.listed = listed;
    this.colourShown();
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
    sizeRuns(code, this.text, length, this.drawn);
  }

  setup() {
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
  // (the registry's `x-data.document.property`), or from the written `<pre>`; null
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
        if (target.parentElement !== code || !code) return;
        if (skipped) this.shown.delete(target);
        else this.shown.add(target);
        this.colourShown();
      },
      { capture: true },
    );
    /** @type {string | null} */
    this.value = null;
  }

  // A lone run is never skipped (`inRuns`), so no change of state says it shows.
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

  /** @param {string | null} value @param {boolean} [presented] whether this draw waited for the page to present */
  async show(value, presented = false) {
    const rendering = this.rendering + 1;
    this.rendering = rendering;
    const source = value ?? "";
    const preview = this.getAttribute("preview");
    try {
      if (preview) await import("./lf-tabs.js");
      const language = this.getAttribute("language") ?? preview;
      // A language with no grammar fails the document here, before it draws.
      if (language) await ensureSyntaxLanguage(language);
      if (preview === "markdown") {
        let failure;
        if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
      }
      // A document the page shows draws at once; one it doesn't, as in a closed tab,
      // first draws once the page has presented (`drawLater`), and this update
      // completes without it: the page counts the draws as an arrival. Drawn in page
      // order, a reload on the 30th of 30 tabs of 4 MB showed its document only after
      // the 29 before it: 2.8 s in Chromium, 33 s in Firefox. Drawn before
      // presentation, they held it back, and Firefox, which styles a closed tab's rows
      // too, restyled every one of them as the page presented: 2.6 s for 30 documents
      // of 50,000 lines.
      if (!this.sourceView) {
        this.listed = this.checkVisibility();
        if (!this.listed && !presented) return drawLater(this, value, rendering);
      }
      if (rendering !== this.rendering || !this.isConnected) return;
      const { pre: drawnPre, code: drawnCode, text } = listing(source);
      if (this.colours?.lang !== language) {
        this.colours?.clear();
        this.colours = language
          ? new RunColours(language, (error) => {
              if (this.isConnected) reportFailure(this, error);
            })
          : null;
      }
      const view = (this.view ??= this.build(preview));
      const label =
        this.getAttribute("label") ??
        this.getAttribute("source") ??
        this.getAttribute("for");
      keepsText(view.caption, value == null ? `${label} · no data` : label);
      const previous = this.text;
      this.text = text;
      if (this.cut) keepsText(this.cut.press, `Show all ${text.length} lines`);
      // The first line the new text changes, past the end where it changes none.
      let from = 0;
      while (from < text.length && previous[from] === text[from]) from++;
      if (from === text.length && previous.length === text.length) from = Infinity;
      if (!this.sourceView) {
        setChildren(view.listing, [drawnPre]);
        this.sourceView = { pre: drawnPre, code: drawnCode };
        this.sizes.observe(view.listing);
        this.sizes.observe(drawnCode);
        if (this.cut && view.preview) {
          this.sizes.observe(this.cut.panel);
          this.sizes.observe(view.preview);
        }
      } else {
        // The pre owns provenance and scroll; the code owns its native reach stop.
        // Reconcile only their source children, leaving those independent owners
        // in place while unchanged lines keep their text nodes and selection.
        reconcileRuns(this.sourceView.code, drawnCode, previous, text);
        if (this.lineLength)
          sizeRuns(this.sourceView.code, text, this.lineLength, this.drawn);
        const digits = "--lf-number-digits";
        this.sourceView.pre.style.setProperty(
          digits,
          drawnPre.style.getPropertyValue(digits),
        );
      }
      const { code } = this.sourceView;
      for (const run of [...this.shown])
        if (run.parentElement !== code) this.shown.delete(run);
      if (this.colours) {
        this.colours.changed(text, code, from);
        this.colourShown();
      }
      let loaded = this.frameLoaded;
      const previewNode = view.preview;
      if (previewNode instanceof HTMLDivElement) {
        const template = document.createElement("template");
        template.innerHTML = renderMarkdown(source, false);
        setRenderedChildren(previewNode, template.content.childNodes);
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
        this.cut && !view.figure.isConnected
          ? this.getBoundingClientRect().height
          : null;
      setChildren(this, [view.figure]);
      this.showLone();
      if (this.listed) this.refit();
      // Reports the draw: marks its text's items for whoever hosts the widget, in the
      // turn that announces them (`drawn`), so on a Leaf page comments on them anchor to
      // the document's data.
      if (view.preview) {
        mark(this.sourceView.pre, "source");
        mark(view.preview, "preview");
      } else mark(view.figure, "document");
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      if (loaded) await loaded;
      if (rendering !== this.rendering || !this.isConnected) return;
      this.classList.toggle("lf-rendered", true);
      // Measured once drawn, since until then the host wears the source face
      // (reading.css).
      this.holdSource(firstBox);
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
    generatedElement(tabs, { says: false });
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
    if (drawn instanceof HTMLIFrameElement) {
      drawn.title = `${this.getAttribute("label") ?? this.getAttribute("source") ?? this.getAttribute("for")} preview`;
      drawn.setAttribute("sandbox", "allow-scripts");
    }
    rendered.append(drawn);
    literal.append(listing);
    if (this.matches(WRITTEN)) {
      const box = offer("div", "lf-text-document-cut");
      box.hidden = true;
      const press = offerAction("inline", "lf-text-document-more", "");
      // The press goes once it has shown the lines, so focus moves to the listing.
      press.addEventListener("click", () => {
        literal.toggleAttribute("data-lf-all", true);
        keepsHidden(box, true);
        if (this.sourceView) focusDestination(this.sourceView.pre, "return");
      });
      box.append(press);
      literal.append(box);
      this.cut = { panel: literal, box, press };
    }
    tabs.append(rendered, literal);
    figure.append(tabs);
    return { figure, caption, listing, preview: drawn };
  }
}
customElements.define("lf-text-document", TextDocument);
