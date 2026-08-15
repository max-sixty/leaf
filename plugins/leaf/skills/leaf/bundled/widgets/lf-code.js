/* lf-code: upgraded because it splits lines. The body is code verbatim in a <pre>
 * (data); `hi` highlights line ranges; lf-note children beside that <pre> anchor a
 * remark at a line. Notes are moved, never rewritten, so their text stays quotable
 * — the annotated-walkthrough shape.
 *
 * `language` colors it. A token can span a newline (a docstring, a block comment)
 * and a line is the unit this widget numbers, so the tokens are cut at each
 * newline (tokenLines) rather than the source being colored a line at a time —
 * coloring line by line would restart the tokenizer inside the docstring and
 * read its second line as code. */
import {
  dataBody,
  once,
  failSoft,
  settle,
  synNodes,
  syntax,
  tokenLines,
} from "/leaf.js";

// "3-5,8" → Set of line numbers.
function parseRanges(spec) {
  const lines = new Set();
  if (!spec) return lines;
  for (const part of spec.split(",")) {
    const [from, to] = part.split("-").map(Number);
    for (let n = from; n <= (to ?? from); n++) lines.add(n);
  }
  return lines;
}

customElements.define(
  "lf-code",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // Registered with settle() so the runtime holds the first anchor pass until
      // the lines are in — the tokenizer loads lazily, so even an uncolored block
      // lands a microtask late and one writer has to finish before another reads.
      settle(this.render());
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
        const hi = parseRanges(this.getAttribute("hi"));
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
        // Every note's line exists: `version check` refuses an `at` outside the
        // body (x-lines), so there is no leftover to sweep up.
        lines.forEach((tokens, i) => {
          const n = i + 1;
          const line = document.createElement("span");
          line.className = `lf-code-line${hi.has(n) ? " hi" : ""}`;
          line.append(...synNodes(tokens), "\n");
          pre.append(line);
          for (const note of byLine.get(n) ?? []) pre.append(noteNode(note));
        });
        this.replaceChildren(pre);
        this.classList.add("lf-rendered");
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);

function noteNode(note) {
  const box = document.createElement("div");
  box.className = "lf-code-note";
  box.append(note); // moved, not copied: the authored element keeps its text and id
  return box;
}
