/* A patch first paints before its renderer, a different height from the drawing
 * that replaces it. This counts what the drawing stands on and writes the counts on
 * the host, where the theme turns them into its reserved height ("First paint",
 * base.css): each file's frame, and a row per source line and hunk separator, but
 * none for header lines or for a first hunk that starts the file. Prose files wrap
 * their rows (`overflowFor`), which only the width can say, so for those rows the
 * count is the greedy wrap of each row's text at the column the drawing will give
 * it. It draws nothing. Source-bound patches read their declared input from the
 * initial data delivery. A diff it cannot count (an unavailable input, a files
 * manifest or a shown file with no hunk) gets no
 * counts, and its box is its source's until the drawing lands; an authored
 * `data-height` holds the box instead, so it is left alone. */
import { overflowFor } from "../widgets/overflow.js";

document.documentElement.lfInitial.register("lf-diff", (host, tools) => {
  const pre = host.querySelector(":scope > pre");
  if (!pre || host.getAttribute("data-lf-height")) return null;
  const value = host.hasAttribute("source")
    ? tools.inputValue("document")
    : pre?.textContent;
  if (typeof value !== "string") return null;
  const authored = host.getAttribute("overflow");
  const lines = value.replace(/^\n+|\n+$/g, "").split("\n");
  const files = [];
  let file = null;
  let old = 0;
  let added = 0;
  for (const line of lines) {
    const hunk = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
    if (hunk && old <= 0 && added <= 0) {
      const [, a, b = "1", c, d = "1"] = hunk;
      if (!file)
        files.push((file = { path: "", hunks: 0, rows: 0, largest: 0, texts: [] }));
      old = Number(b);
      added = Number(d);
      file.rows += file.hunks++ || Number(a) > 1 || Number(c) > 1 ? 1 : 0;
      file.largest = Math.max(file.largest, Number(a) + old - 1, Number(c) + added - 1);
    } else if (file?.hunks && (old > 0 || added > 0 || line.startsWith("\\"))) {
      // A row of the hunk: context counts against both sides, as a blank line does.
      if (line[0] !== "+" && line[0] !== "\\") old--;
      if (line[0] !== "-" && line[0] !== "\\") added--;
      file.rows++;
      file.texts.push(line.slice(1));
    } else {
      // A header line: the first after a hunk, or a `diff --git`, starts a file.
      if (!file || file.hunks || line.startsWith("diff --git "))
        files.push((file = { path: "", hunks: 0, rows: 0, largest: 0, texts: [] }));
      const named = /^(?:\+\+\+ b\/|--- a\/|diff --git a\/\S+ b\/)(.+)$/.exec(line);
      if (named && named[1] !== "/dev/null") file.path = named[1];
    }
  }
  // A selected-file reader starts on the first file, open even when `collapsed`
  // was authored. The other files have no box until the reader selects them.
  const singleFile = host.getAttribute("view") === "file";
  const shown = singleFile ? files.slice(0, 1) : files;
  if (!shown.length || shown.some((each) => !each.hunks)) return null;
  // Folded patch listings draw their name rows alone.
  const open = singleFile || !host.hasAttribute("collapsed");
  let rows = 0;
  let style = null;
  let width = 0;
  let ch = 0;
  for (const each of open ? shown : []) {
    rows += each.rows;
    if (overflowFor(each.path, authored) !== "wrap") continue;
    if (!style) {
      // Both inline and source-bound patches have a pre. Let that code context
      // resolve CSS units; canvas resolves raw em tokens in its own context.
      style = getComputedStyle(pre);
      const context = document.createElement("canvas").getContext("2d");
      context.font = `${style.fontSize} ${style.fontFamily}`;
      ch = context.measureText("0").width;
      width = host.getBoundingClientRect().width;
    }
    // The row's text column, from the drawing's geometry: the file frame's two 1px
    // borders, the gutter of `digits + 3` ch (`renderFile`, lf-diff.js), and the 2ch
    // before the text and 8px after it (`.lf-diff-line > [data-line]`,
    // widget-shadow.css). `test_an_inline_patch_first_paints_at_the_height_it_draws_at`
    // holds these numbers to the drawing.
    const digits = String(each.largest).length;
    const cols = Math.floor((width - 2 - 8 - (digits + 5) * ch) / ch);
    if (cols > 0) for (const text of each.texts) rows += wraps(text, cols);
  }
  host.style.setProperty("--lf-diff-files", String(shown.length));
  host.style.setProperty("--lf-diff-rows", String(rows));
  host.style.setProperty("--lf-diff-open", open ? "1" : "0");
  return null;
});

// Extra lines `white-space: pre-wrap; overflow-wrap: anywhere` gives a row of
// monospace text: breaks before a word that doesn't fit, spaces hanging at the line's
// end, and inside a word only where the word alone is longer than the line.
function wraps(text, cols) {
  if (text.length <= cols) return 0;
  let extra = 0;
  let used = 0;
  for (const [, space, word] of text.matchAll(/( *)([^ ]*)/g)) {
    used += space.length;
    if (!word) continue;
    if (used > 0 && used + word.length > cols) {
      extra++;
      used = 0;
    }
    let rest = word.length;
    while (used + rest > cols) {
      rest -= cols - used;
      extra++;
      used = 0;
    }
    used += rest;
  }
  return extra;
}
