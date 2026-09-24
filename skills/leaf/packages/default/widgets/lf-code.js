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
 * referenced like any other — `hi` tints the elided row, an indication lights it, and
 * a note whose `at` falls there becomes that row's caption, saying what was left out.
 *
 * `lfElementsFor(key)` answers another widget's indication (runtime/indication.js,
 * experimental) in that same grammar. A number outside the block addresses nothing,
 * so a driver can offer one key to several excerpts of the same file. */
import {
  dataBody,
  once,
  failSoft,
  layoutChanged,
  quietWord,
  widgetController,
  synNodes,
  syntax,
  tokenLines,
} from "/runtime/widget-api.js";

// "3-5,8" → [[3, 5], [8, 8]].
const spans = (spec) =>
  (spec ? spec.split(",") : []).map((part) => {
    const [from, to] = part.split("-").map(Number);
    return [from, to ?? from];
  });

// Whether a range spec names any of the lines lo..hi: one line, or the stretch an
// elided row stands for. A range may run across a gap in an excerpt, and then
// addresses the lines on either side of it and the elided row between.
const within = (spec) => {
  const ranges = spans(spec);
  return (lo, hi = lo) => ranges.some(([from, to]) => from <= hi && lo <= to);
};

// The rows a range addresses: a numbered line by its number, an elided row by the
// stretch it stands for.
const rowSpan = (row) =>
  row.classList.contains("lf-code-elided")
    ? [Number(row.dataset.from), Number(row.dataset.to)]
    : [Number(row.dataset.line)];

// The numbers the body's lines carry, in body order. `version check` holds `lines` to
// one strictly ascending number per body line (x-numbering), so the two agree here.
const numbering = (el, count) =>
  el.hasAttribute("lines")
    ? spans(el.getAttribute("lines")).flatMap(([from, to]) =>
        Array.from({ length: to - from + 1 }, (_, i) => from + i),
      )
    : Array.from({ length: count }, (_, i) => i + 1);

customElements.define(
  "lf-code",
  class extends HTMLElement {
    // The rendered lines a range addresses, none before the lines are in; the render
    // states their arrival through layoutChanged, and an indication resolves again then.
    lfElementsFor(key) {
      const addressed = within(key);
      return [
        ...this.querySelectorAll(":scope > pre > :is(.lf-code-line, .lf-code-elided)"),
      ].filter((row) => addressed(...rowSpan(row)));
    }

    connectedCallback() {
      if (!once(this)) return;
      // Registered with the controller so the runtime holds the first anchor pass until
      // the lines are in — the tokenizer loads lazily, so even an uncolored block
      // lands a microtask late and one writer has to finish before another reads.
      widgetController(this).present(this.render());
    }

    async render() {
      // The code is the <pre>'s and nothing else's; notes are its siblings and say
      // which line they are about, so a note never sits between two halves of the
      // source and there is no interrupted-line arithmetic to get right.
      const notes = [...this.querySelectorAll(":scope > lf-note")];
      const source = dataBody(this).replace(/^\n+/, "").replace(/\s+$/, "");
      try {
        const lang = this.getAttribute("language");
        // One representation either way: an uncolored block is the whole source as a
        // single roleless token, so the line walk below has one shape to handle.
        const lines = tokenLines(
          lang ? await syntax(source, lang) : [{ text: source }],
        );
        const numbers = numbering(this, lines.length);
        const hi = within(this.getAttribute("hi"));
        const byLine = new Map();
        for (const note of notes) {
          const at = Number(note.getAttribute("at"));
          byLine.set(at, [...(byLine.get(at) ?? []), note]);
        }
        // No tab stop written here: the box scrolls in the light DOM, where the
        // runtime's reachScrollers pass grants one to every scrollable box alike —
        // lf-diff writes its own only because that pass cannot see into a shadow
        // tree.
        const pre = document.createElement("pre");
        // The gutter fits the widest number, so an excerpt from deep in a file keeps
        // its code aligned with its notes.
        pre.style.setProperty("--lf-code-digits", String(numbers.at(-1)).length);
        // Every note's line has a row: `version check` refuses an `at` outside the
        // block (x-lines), so there is no leftover to sweep up.
        lines.forEach((tokens, i) => {
          const n = numbers[i];
          if (i && n > numbers[i - 1] + 1) {
            const [from, to] = [numbers[i - 1] + 1, n - 1];
            const captions = [...byLine]
              .filter(([at]) => from <= at && at <= to)
              .sort(([a], [b]) => a - b)
              .flatMap(([, list]) => list);
            pre.append(elided(from, to, hi(from, to), captions));
          }
          const line = document.createElement("span");
          line.className = `lf-code-line${hi(n) ? " hi" : ""}`;
          line.dataset.line = n;
          line.append(...synNodes(tokens), "\n");
          // The tint says "this is the line" to the eye and nothing to a user
          // listening, who is handed the whole block with no idea which of it the note
          // beside it is about. A word per highlighted line rather than one at the top
          // saying which numbers: the numbers are painted from data-line, into no text
          // node on purpose — a line number in the text would be a line number in the
          // clipboard — so "lines 3 to 4" would name something the user cannot hear.
          // Said per line, it arrives where it is true. The one word rides the same
          // clip as every other quiet word, out of the selection with it, so a copied
          // block is still the source and nothing else.
          if (hi(n)) quietWord(line, "highlighted");
          pre.append(line);
          for (const note of byLine.get(n) ?? []) pre.append(noteNode(note));
        });
        this.replaceChildren(pre);
        this.classList.add("lf-rendered");
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
function elided(from, to, highlighted, captions) {
  const row = document.createElement("span");
  row.className = `lf-code-elided${highlighted ? " hi" : ""}`;
  row.dataset.from = from;
  row.dataset.to = to;
  const count = to - from + 1;
  row.dataset.elided = `${count} line${count === 1 ? "" : "s"}`;
  if (highlighted) quietWord(row, "highlighted");
  row.append(...captions);
  return row;
}

function noteNode(note) {
  const box = document.createElement("div");
  box.className = "lf-code-note";
  box.append(note); // moved, not copied: the authored element keeps its text and id
  return box;
}
