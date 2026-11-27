/* lf-code: upgraded because it splits lines. The body is code verbatim in a <pre>
 * (data); `hi` highlights line ranges; lf-note children beside that <pre> anchor a
 * remark at a line. Notes are moved, never rewritten, so their text stays quotable
 * — the annotated-walkthrough shape.
 *
 * A `language-…` class colors it, on a `<code>` inside the `<pre>` as on any code
 * block (`codeLanguage`). A token can span a newline (a docstring, a block comment)
 * and a line is the unit this widget numbers, so the tokens are cut at each
 * newline (tokenLines) rather than the source being colored a line at a time —
 * coloring line by line would restart the tokenizer inside the docstring and
 * read its second line as code.
 *
 * `lines` makes the body an excerpt: the line numbers it quotes, in the grammar `hi`
 * speaks ("1505-1507,1520-1527"). A gutter number is the line's number in its source,
 * a gap between ranges draws an elided row, and every reference into the block — `hi`,
 * a note's `at`, another widget's key — names lines by those numbers. Without `lines`
 * the body is lines 1..N, so a quick snippet reads exactly as before. A line has one
 * number and nothing else to be called by: a driver that wants readable names keeps
 * them in its own vocabulary, where it uses them.
 *
 * Every number from the first shown line to the last addresses a row: its own line,
 * or the elided row standing in for the stretch it falls in. So a left-out line is
 * referenced like any other — `hi` tints the elided row, and a note whose `at` falls
 * there becomes that row's caption, saying what was left out.
 *
 * `lfElementsFor(key)` answers a reference into the block (`navigateToDatum`) in that
 * same grammar. A number outside the block addresses nothing.
 * The reader can switch wrapping through the code block’s command scope without rebuilding source rows. This
 * is tab-local reading state, retained by widget id across revisions, not a decision.
 * Until the reader chooses, authored presentation remains the default. Paper wraps
 * complete lines regardless of the screen choice.
 *
 * A docked note carries its line's indent (`--lf-code-indent`, as the line does), so
 * the theme stands it under the line's first character. A block with notes offers a
 * mark in its toolbar, beside Copy, and `n` in its scope: Collapse all's fold hides
 * them, named Hide notes, and Expand all's shows them again, named Show 8 notes, so a
 * reader can read the code whole. It is reading state kept as wrapping is, and paper
 * shows the notes whatever the screen's choice. A hidden note's line keeps its number
 * in the accent, so the reader sees where the notes were. The maintainer chose the
 * toolbar, which shows while the pointer or focus is on the block or after a tap,
 * over a word standing above the block, which kept a strip of room over every block
 * with notes. The mark is Leaf's control, drawn only where Leaf runs, since only
 * Leaf's register answers its press.
 *
 * `playhead` is the lines another widget is at, in `hi`'s grammar, or null: Leaf sets
 * it from the `source-lines` output of the widget `for` names (registry `inputs`), and
 * a plain host sets the property itself. The block marks the rows those numbers address
 * (`data-lf-at`). Several excerpts of one file can follow one widget, since a number
 * outside an excerpt marks nothing there.
 *
 * So that a reader watching that widget sees the marked line beside it, the block keeps
 * the first marked line in the box that scrolls it. When the line stands outside a band
 * of that box, from 15% of its height to 70%, the block sets the box's scroll at once
 * so the line stands a third of the way down, with the lines that run next below it.
 * Where that box is the page, or the page doesn't render the line, as in a closed
 * disclosure, it moves nothing. The first value a block is handed only marks its line,
 * as an arrival moves nothing, and the block follows from the next.
 *
 * The reader's hand inside the box, a press, wheel, touch or key there, stops the
 * following, so the box holds still while they read or scroll it, and their hand on
 * the widget `for` names starts it again for the blocks that name it. Rejected:
 * following again once a marked line came into the reader's view, which took the pane
 * from a reader who had scrolled up to read the lede as soon as the film lit a line
 * beside it.
 *
 * It is a `LeafElement` only to be handed `playhead`; it draws no Lit template, and its
 * source draw is the update's completion, so Leaf's first anchor pass waits for the
 * lines.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too: coloured, numbered by its own stylesheet where
 * the page loads it, and with nothing of Leaf's. What Leaf adds it reads from outside:
 * the wrap and notes keys as the element's `lfCommands`, the Copy control from the
 * block's `data-lf-copy`, standing in the block's toolbar (`lfBar`) where it has one,
 * and the word a listener hears on a highlighted line from its `data-lf-quiet`. */
import { onUserInput, scrollersOf, tabStore } from "/runtime/portable-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { bodyText } from "/runtime/lib/data-body.js";
import { failSoft } from "/runtime/lib/failure.js";
import { nameAction, offer, offerAction } from "/runtime/lib/controls.js";
import {
  codeLanguage,
  synNodes,
  syntax,
  tokenLines,
} from "/runtime/lib/syntax-tokens.js";
import { keeps } from "/runtime/lib/keeps.js";
import { scrollMoves } from "/runtime/lib/scroll-range.js";

// Which of the reader's gestures last had their hand on or inside each element, counted
// from the first. A block follows in its box unless their hand was in the box after it
// was last on the widget the block follows (see the header), so a hand in the box holds
// it from the page's load, before any block there has followed a line. The hand is read
// from the document's one reading of the reader's inputs (`onUserInput`), which binds
// no key, and is one of its gestures: an `input` follows a gesture already counted, and
// a script that moves the followed widget dispatches one with no reader behind it.
/** @type {WeakMap<Element, number>} */
const hands = new WeakMap();
let gestures = 0;
const HAND = new Set(["pointerdown", "wheel", "touchstart", "keydown"]);
onUserInput((event) => {
  if (!HAND.has(event.type)) return;
  gestures += 1;
  for (const node of event.composedPath())
    if (node instanceof Element) hands.set(node, gestures);
});

// "3-5,8" → [[3, 5], [8, 8]].
/** @param {string | null} spec @returns {[number, number][]} */
const spans = (spec) =>
  (spec ? spec.split(",") : []).map((part) => {
    const [start, end] = part.split("-");
    const from = Number(start);
    return [from, end === undefined ? from : Number(end)];
  });

// Whether a range spec names any of the lines lo..hi: one line, or the stretch an
// elided row stands for. A range may run across a gap in an excerpt, and then
// addresses the lines on either side of it and the elided row between.
/** @param {string | null} spec */
const within = (spec) => {
  const ranges = spans(spec);
  return (/** @type {number} */ lo, hi = lo) =>
    ranges.some(([from, to]) => from <= hi && lo <= to);
};

// The rows a range addresses: a numbered line by its number, an elided row by the
// stretch it stands for.
/** @param {HTMLSpanElement} row @returns {[number, number?]} */
const rowSpan = (row) =>
  row.classList.contains("lf-code-elided")
    ? [Number(row.dataset.lfFrom), Number(row.dataset.lfTo)]
    : [Number(row.dataset.lfLine)];

// How many columns a line's leading whitespace takes, a tab reaching the next stop of
// eight (the <pre>'s tab-size).
/** @param {{text: string}[]} tokens */
const indentColumns = (tokens) => {
  const leading = tokens
    .map((token) => token.text)
    .join("")
    .replace(/[^ \t][\s\S]*/, "");
  let columns = 0;
  for (const char of leading)
    columns = char === "\t" ? columns - (columns % 8) + 8 : columns + 1;
  return columns;
};

// The numbers the body's lines carry, in body order: the authored `lines` ranges, one
// number per body line, or 1 to N without them. A body longer than its ranges goes on
// counting from the last number, and ranges past the body's end number nothing.
// Each range is walked only as far as the body needs, so a range far longer than the
// body costs nothing.
/** @param {HTMLElement} el @returns {Generator<number, never>} */
function* numbering(el) {
  let last = 0;
  for (const [from, to] of spans(el.getAttribute("lines")))
    for (let n = from; n <= to; n++) {
      last = n;
      yield n;
    }
  while (true) yield ++last;
}

customElements.define(
  "lf-code",
  class extends LeafElement {
    static properties = { playhead: { attribute: false } };

    constructor() {
      super();
      /** @type {string | null} */
      this.playhead = null;
    }

    /** @type {Promise<void> | undefined} */
    #source;
    // The numbered and elided rows, in order, once the lines are in.
    /** @type {HTMLSpanElement[]} */
    #rows = [];
    // The rows the playhead marks.
    /** @type {HTMLSpanElement[]} */
    #at = [];
    // Whether the playhead has had a value. The first only marks, as an arrival moves
    // nothing (see the header).
    #arrived = false;

    // The rendered lines a range addresses, none before the lines are in.
    /** @param {string | null} key */
    lfElementsFor(key) {
      const addressed = within(key);
      return this.#rows.filter((row) => addressed(...rowSpan(row)));
    }

    // The tokenizer loads lazily, so even an uncolored block lands a microtask late,
    // and one writer has to finish before another reads: the update completes once the
    // lines are in, and Leaf's first anchor pass waits for it.
    setup() {
      this.#source = this.#draw();
    }

    async getUpdateComplete() {
      const result = await super.getUpdateComplete();
      await this.#source;
      return result;
    }

    /** @param {Map<PropertyKey, unknown>} changed */
    updated(changed) {
      super.updated(changed);
      if (changed.has("playhead")) this.#follow();
    }

    #mark() {
      const at = this.lfElementsFor(this.playhead);
      for (const row of this.#at) if (!at.includes(row)) keeps(row, "data-lf-at", null);
      for (const row of at) keeps(row, "data-lf-at", "");
      this.#at = at;
    }

    // Mark the new lines, and keep the first in sight as the header says.
    #follow() {
      this.#mark();
      const arrived = this.#arrived;
      this.#arrived ||= this.playhead !== null;
      const [row] = this.#at;
      // A row the page doesn't render, as in a closed disclosure, has no place to bring
      // into view.
      if (!arrived || !row?.checkVisibility()) return;
      const [scroller] = scrollersOf(row);
      if (!scroller || scroller === document.scrollingElement) return;
      const id = this.getAttribute("for");
      const followed =
        id &&
        /** @type {Document | ShadowRoot} */ (this.getRootNode()).getElementById(id);
      const resumed = (followed && hands.get(followed)) || 0;
      if ((hands.get(scroller) ?? 0) > resumed) return;
      const frame = scroller.getBoundingClientRect();
      const { top, bottom } = row.getBoundingClientRect();
      if (
        top >= frame.top + frame.height * 0.15 &&
        bottom <= frame.top + frame.height * 0.7
      )
        return;
      const to = scroller.scrollTop + top - frame.top - frame.height / 3;
      if (scrollMoves(scroller, { top: to }))
        scroller.scrollTo({ top: to, behavior: "instant" });
    }

    async #draw() {
      // The code is the <pre>'s and nothing else's; notes are its siblings and say
      // which line they are about, so a note never sits between two halves of the
      // source and there is no interrupted-line arithmetic to get right.
      const notes = /** @type {HTMLElement[]} */ ([
        ...this.querySelectorAll(":scope > lf-note"),
      ]);
      const source = bodyText(this);
      try {
        const lang = codeLanguage(this);
        // One representation either way: an uncolored block is the whole source as a
        // single unstyled token, so the line walk below has one shape to handle.
        const lines = tokenLines(
          lang ? (await syntax(source, lang)).tokens : [{ text: source, style: {} }],
        );
        const numbers = numbering(this);
        const rows = lines.map((tokens) => ({ tokens, n: numbers.next().value }));
        const hi = within(this.getAttribute("hi"));
        const byLine = Map.groupBy(notes, (note) => Number(note.getAttribute("at")));
        // Reading commands remain reachable when wrapping removes overflow.
        const pre = document.createElement("pre");
        pre.setAttribute("data-lf-carry", "source");
        pre.tabIndex = 0;
        // The gutter fits the widest number, so an excerpt from deep in a file keeps
        // its code aligned with its notes.
        pre.style.setProperty("--lf-code-digits", `${String(rows.at(-1)?.n).length}`);
        // A note stands at the row of the line it names, or the elided row standing
        // for it; one naming a line past either end of the block stands at its foot.
        /** @type {number | null} */
        let previous = null;
        const firstLine = document.createElement("span");
        rows.forEach(({ tokens, n }) => {
          if (previous !== null && n > previous + 1) {
            const [from, to] = [previous + 1, n - 1];
            const captions = [...byLine]
              .filter(([at]) => from <= at && at <= to)
              .sort(([a], [b]) => a - b)
              .flatMap(([, list]) => list);
            pre.append(elided(from, to, hi(from, to), captions));
          }
          const line = previous === null ? firstLine : document.createElement("span");
          line.className = "lf-code-line";
          line.dataset.lfLine = String(n);
          // A line too long for the frame wraps, and its later rows hang from its own
          // indent (the theme's `--lf-code-indent`), so a wrapped line keeps its place
          // in the code's structure.
          const indent = indentColumns(tokens);
          if (indent) line.style.setProperty("--lf-code-indent", String(indent));
          line.append(...synNodes(tokens), "\n");
          // The tint says "this is the line" to the eye and nothing to a user
          // listening, who is handed the whole block with no idea which of it the note
          // beside it is about. A word per highlighted line rather than one at the top
          // saying which numbers: the numbers are painted from data-lf-line, into no
          // text node on purpose — a line number in the text would be a line number in
          // the clipboard — so "lines 3 to 4" would name something the user cannot
          // hear. Said per line, it arrives where it is true. The one word rides the
          // same clip as every other quiet word, out of the selection with it, so a
          // copied block is still the source and nothing else. Leaf writes it from the
          // declaration, since only Leaf's theme keeps it off the screen.
          if (hi(n)) {
            line.dataset.lfHi = "";
            line.dataset.lfQuiet = "highlighted";
          }
          pre.append(line);
          // Moved, not copied: the authored element keeps its text and id.
          for (const note of byLine.get(n) ?? []) {
            if (indent) note.style.setProperty("--lf-code-indent", String(indent));
            else note.style.removeProperty("--lf-code-indent");
            pre.append(note);
          }
          previous = n;
        });
        const foot = notes.filter((note) => !pre.contains(note));
        for (const note of foot) note.style.removeProperty("--lf-code-indent");
        pre.append(...foot);
        this.#rows = /** @type {HTMLSpanElement[]} */ (
          [...pre.children].filter((row) =>
            row.matches(".lf-code-line, .lf-code-elided"),
          )
        );
        // Copied as the source the lines were drawn from, never as the lines' text,
        // which carries the notes docked among them.
        pre.dataset.lfCopy = "code";
        pre.lfCopy = () => source;
        const notesKey = `code-notes:${this.id}`;
        let notesShown = tabStore.get(notesKey) !== "hidden";
        const notesToggle =
          notes.length && document.documentElement.hasAttribute("data-lf-interactive")
            ? offerAction("mark", "lf-code-notes-toggle", "Hide notes", {
                action: "collapse-all",
              })
            : null;
        // Copy joins the mark here (`lfBar`), which the theme stands in the block's
        // corner and shows as it would show a lone Copy.
        const bar = notesToggle ? offer("div", "lf-code-bar lf-mark-bar") : null;
        // Its marks join into one toolbar (controls.css, `data-lf-joined`).
        if (bar) bar.dataset.lfJoined = "";
        if (bar && notesToggle) bar.append(notesToggle);
        if (bar) pre.lfBar = bar;
        // The press says what it will do, and hidden notes say how many wait.
        const showNotes = `Show ${notes.length} note${notes.length === 1 ? "" : "s"}`;
        const paintNotes = () => {
          if (notesShown) this.removeAttribute("data-lf-notes");
          else this.setAttribute("data-lf-notes", "hidden");
          if (notesToggle)
            nameAction(notesToggle, notesShown ? "collapse-all" : "expand-all", {
              label: notesShown ? "Hide notes" : showNotes,
              className: "lf-mark-icon",
            });
        };
        paintNotes();
        this.replaceChildren(pre, ...(bar ? [bar] : []));
        this.classList.add("lf-rendered");
        const key = `code-wrap:${this.id}`;
        const saved = tabStore.get(key);
        let wrapped = getComputedStyle(firstLine).whiteSpace !== "pre";
        let horizontal = 0;
        const paintWrap = (/** @type {boolean} */ value) => {
          wrapped = value;
          this.setAttribute("data-lf-reader-wrap", value ? "wrap" : "scroll");
        };
        if (saved !== null) paintWrap(saved === "true");
        const toggleWrap = () => {
          if (!wrapped) horizontal = pre.scrollLeft;
          paintWrap(!wrapped);
          tabStore.set(key, String(wrapped));
          // Wrapped, the block stood at its start, so only an offset it had is put back.
          if (!wrapped && horizontal)
            pre.scrollTo({ left: horizontal, behavior: "instant" });
          this.dispatchEvent(
            new CustomEvent("lf-layout", { bubbles: true, composed: true }),
          );
        };
        this.lfCommands = {
          title: "On a code block",
          rows: [
            {
              id: "code.wrap",
              keys: ["w"],
              title: () => (wrapped ? "unwrap lines" : "wrap lines"),
              run: toggleWrap,
            },
            ...(notesToggle
              ? [
                  {
                    id: "code.notes",
                    keys: ["n"],
                    title: () => (notesShown ? "hide notes" : "show notes"),
                    control: notesToggle,
                    touch: /** @type {false} */ (false),
                    run: () => {
                      notesShown = !notesShown;
                      tabStore.set(notesKey, notesShown ? "shown" : "hidden");
                      paintNotes();
                      this.dispatchEvent(
                        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
                      );
                    },
                  },
                ]
              : []),
          ],
        };
        this.dispatchEvent(
          new CustomEvent("lf-commands", { bubbles: true, composed: true }),
        );
        this.#mark();
        this.dispatchEvent(
          new CustomEvent("lf-layout", { bubbles: true, composed: true }),
        );
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);

// The row standing for the lines an excerpt leaves out. Its count is painted from the
// attribute, as the gutter's numbers are, so a copied excerpt is still only source and
// no passage anchors on text the author never wrote. A note docked in the stretch is
// the row's caption: moved in whole, so its authored text stays quotable.
/** @param {number} from @param {number} to @param {boolean} highlighted @param {Element[]} captions */
function elided(from, to, highlighted, captions) {
  const row = document.createElement("span");
  row.className = "lf-code-elided";
  row.dataset.lfFrom = String(from);
  row.dataset.lfTo = String(to);
  const count = to - from + 1;
  row.dataset.lfElided = `${count} line${count === 1 ? "" : "s"}`;
  if (highlighted) {
    row.dataset.lfHi = "";
    row.dataset.lfQuiet = "highlighted";
  }
  row.append(...captions);
  return row;
}
