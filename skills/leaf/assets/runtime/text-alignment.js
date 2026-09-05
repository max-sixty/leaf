/* Lossless, language-aware alignment of whole-text states, and the one rendering of an
 * alignment.
 *
 * Two surfaces explain how a text came to say what it says: a draft's own history, and
 * the version comparison's earlier reading of a block. A reader who meets one has to
 * recognise the other, so the runs and the elements they become are stated together
 * here rather than once per surface. Only the paint stays with each surface's sheet,
 * because that is the part that has to differ — a widget's rendering is reached by its
 * package's theme and a shadow slice, the comparison's by the comment layer's own
 * stylesheet. */

// One lossless text alignment for every widget that needs to explain a sequence of
// whole-text states. Segmenter keeps the language-aware units this runtime already
// assumes; a linear-space Hirschberg walk supplies the ordered shared spine. Its
// quadratic *time* is capped: after stripping a common prefix and suffix, a very large
// divergent middle is one replacement instead of a page-freezing attempt at fine-grained
// alignment. Joining same+delete reconstructs `before`, and joining same+insert
// reconstructs `after`, exactly.
//
// The unit is the caller's, because the two texts it holds decide what a difference
// between them can mean. Successive edits of one draft differ by words, and words are
// the smallest thing that says where. Two versions of a paragraph differ by having been
// rewritten, and a word walk over a rewrite matches every "the" and "a" it passes: the
// spine it finds is real and the reading it produces is shredded — two texts interleaved
// a word at a time, which no reader can follow and no screen reader can speak. Sentences
// are what a rewrite works in, so a sentence walk marks a rewritten sentence whole and
// leaves a surviving one alone.
export const textUnits = new Intl.Segmenter(undefined, { granularity: "word" });
export const sentenceUnits = new Intl.Segmenter(undefined, {
  granularity: "sentence",
});
const ALIGN_CELLS = 1_000_000;

function lcsRow(left, lo, hi, right, rlo, rhi, reverse) {
  const width = rhi - rlo;
  let previous = new Uint32Array(width + 1);
  for (let at = 0; at < hi - lo; at++) {
    const current = new Uint32Array(width + 1);
    const word = reverse ? left[hi - at - 1] : left[lo + at];
    for (let across = 1; across <= width; across++) {
      const other = reverse ? right[rhi - across] : right[rlo + across - 1];
      current[across] =
        word === other
          ? previous[across - 1] + 1
          : Math.max(previous[across], current[across - 1]);
    }
    previous = current;
  }
  return previous;
}

function lcsMatches(left, lo, hi, right, rlo, rhi, matches) {
  if (lo === hi || rlo === rhi) return;
  if (hi - lo === 1) {
    for (let at = rlo; at < rhi; at++)
      if (left[lo] === right[at]) {
        matches.push([lo, at]);
        break;
      }
    return;
  }

  const middle = lo + Math.floor((hi - lo) / 2);
  let split = 0;
  {
    const forward = lcsRow(left, lo, middle, right, rlo, rhi, false);
    const backward = lcsRow(left, middle, hi, right, rlo, rhi, true);
    let best = -1;
    const width = rhi - rlo;
    for (let at = 0; at <= width; at++) {
      const score = forward[at] + backward[width - at];
      if (score > best) {
        best = score;
        split = at;
      }
    }
  }
  lcsMatches(left, lo, middle, right, rlo, rlo + split, matches);
  lcsMatches(left, middle, hi, right, rlo + split, rhi, matches);
}

export function alignText(before, after, units = textUnits) {
  const left = [...units.segment(before)].map((part) => part.segment);
  const right = [...units.segment(after)].map((part) => part.segment);
  const runs = [];
  const push = (kind, text) => {
    if (!text) return;
    const last = runs.at(-1);
    if (last?.kind === kind) last.text += text;
    else runs.push({ kind, text });
  };

  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  )
    prefix++;
  let suffix = 0;
  while (
    prefix + suffix < left.length &&
    prefix + suffix < right.length &&
    left[left.length - suffix - 1] === right[right.length - suffix - 1]
  )
    suffix++;

  push("same", left.slice(0, prefix).join(""));
  const leftEnd = left.length - suffix;
  const rightEnd = right.length - suffix;
  const matches = [];
  if ((leftEnd - prefix) * (rightEnd - prefix) <= ALIGN_CELLS)
    lcsMatches(left, prefix, leftEnd, right, prefix, rightEnd, matches);

  let i = prefix;
  let j = prefix;
  for (const [li, rj] of matches) {
    push("delete", left.slice(i, li).join(""));
    push("insert", right.slice(j, rj).join(""));
    push("same", left[li]);
    i = li + 1;
    j = rj + 1;
  }
  push("delete", left.slice(i, leftEnd).join(""));
  push("insert", right.slice(j, rightEnd).join(""));
  push("same", left.slice(leftEnd).join(""));
  return runs;
}

// The alignment as elements: `same` is plain text, what the later text dropped is a
// <del>, what it gained an <ins>. Semantic rather than classed, so a copy of the passage
// and a reader hearing it keep the two apart with no stylesheet.
export function alignedNodes(runs) {
  return runs.map((run) => {
    const node = document.createElement(
      run.kind === "delete" ? "del" : run.kind === "insert" ? "ins" : "span",
    );
    node.textContent = run.text;
    return node;
  });
}
