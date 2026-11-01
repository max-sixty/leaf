/* lf-code: upgraded because it splits lines. The body is code verbatim in a <pre>
 * (data); `hi` highlights line ranges; lf-note children beside that <pre> anchor a
 * remark at a line. Notes are moved, never rewritten, so their text stays quotable
 * — the annotated-walkthrough shape.
 *
 * `language` colors it. A token can span a newline (a docstring, a block comment)
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
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too: coloured, numbered by its own stylesheet where
 * the page loads it, and with nothing of Leaf's. What Leaf adds it reads from outside:
 * the drawing under way as a `pending-task` event, the wrap key as the element's
 * `lfCommands`, the Copy control from the block's `data-lf-copy`, and the word a
 * listener hears on a highlighted line from its `data-lf-quiet`. */
import {
  setScroll,
  PendingTaskEvent,
  bodyText,
  commandsChanged,
  failSoft,
  layoutChanged,
  once,
  synNodes,
  syntax,
  tabStore,
  tokenLines,
} from "/runtime/portable-api.js";

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
    ? [Number(row.dataset.from), Number(row.dataset.to)]
    : [Number(row.dataset.line)];

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
  class extends HTMLElement {
    // The rendered lines a range addresses, none before the lines are in.
    /** @param {string} key */
    lfElementsFor(key) {
      const addressed = within(key);
      return [
        ...[...this.querySelectorAll("pre")]
          .filter((pre) => pre.parentElement === this)
          .flatMap((pre) =>
            [...pre.querySelectorAll("span")].filter(
              (row) =>
                row.parentElement === pre &&
                row.matches(".lf-code-line, .lf-code-elided"),
            ),
          ),
      ].filter((row) => addressed(...rowSpan(row)));
    }

    connectedCallback() {
      if (!once(this)) return;
      // Announced as a pending task so the runtime holds the first anchor pass until
      // the lines are in — the tokenizer loads lazily, so even an uncolored block
      // lands a microtask late and one writer has to finish before another reads.
      this.dispatchEvent(new PendingTaskEvent(this.render()));
    }

    async render() {
      // The code is the <pre>'s and nothing else's; notes are its siblings and say
      // which line they are about, so a note never sits between two halves of the
      // source and there is no interrupted-line arithmetic to get right.
      const notes = [...this.querySelectorAll(":scope > lf-note")];
      const source = bodyText(this);
      try {
        const lang = this.getAttribute("language");
        // One representation either way: an uncolored block is the whole source as a
        // single unstyled token, so the line walk below has one shape to handle.
        const lines = tokenLines(
          lang ? await syntax(source, lang) : [{ text: source, style: {} }],
        );
        const numbers = numbering(this);
        const rows = lines.map((tokens) => ({ tokens, n: numbers.next().value }));
        const hi = within(this.getAttribute("hi"));
        const byLine = new Map();
        for (const note of notes) {
          const at = Number(note.getAttribute("at"));
          byLine.set(at, [...(byLine.get(at) ?? []), note]);
        }
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
          line.className = `lf-code-line${hi(n) ? " hi" : ""}`;
          line.dataset.line = String(n);
          // A line too long for the frame wraps, and its later rows hang from its own
          // indent (the theme's `--lf-code-indent`), so a wrapped line keeps its place
          // in the code's structure.
          const indent = indentColumns(tokens);
          if (indent) line.style.setProperty("--lf-code-indent", String(indent));
          line.append(...synNodes(tokens), "\n");
          // The tint says "this is the line" to the eye and nothing to a user
          // listening, who is handed the whole block with no idea which of it the note
          // beside it is about. A word per highlighted line rather than one at the top
          // saying which numbers: the numbers are painted from data-line, into no text
          // node on purpose — a line number in the text would be a line number in the
          // clipboard — so "lines 3 to 4" would name something the user cannot hear.
          // Said per line, it arrives where it is true. The one word rides the same
          // clip as every other quiet word, out of the selection with it, so a copied
          // block is still the source and nothing else. Leaf writes it from the
          // declaration, since only Leaf's theme keeps it off the screen.
          if (hi(n)) line.dataset.lfQuiet = "highlighted";
          pre.append(line);
          // Moved, not copied: the authored element keeps its text and id.
          pre.append(...(byLine.get(n) ?? []));
          previous = n;
        });
        pre.append(...notes.filter((note) => !pre.contains(note)));
        // Copied as the source the lines were drawn from, never as the lines' text,
        // which carries the notes docked among them.
        pre.dataset.lfCopy = "code";
        pre.lfCopy = () => source;
        this.replaceChildren(pre);
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
          if (!wrapped) setScroll(pre, { left: horizontal, behavior: "instant" });
          layoutChanged(this);
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
          ],
        };
        commandsChanged(this);
        layoutChanged(this);
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
  row.className = `lf-code-elided${highlighted ? " hi" : ""}`;
  row.dataset.from = String(from);
  row.dataset.to = String(to);
  const count = to - from + 1;
  row.dataset.elided = `${count} line${count === 1 ? "" : "s"}`;
  if (highlighted) row.dataset.lfQuiet = "highlighted";
  row.append(...captions);
  return row;
}
