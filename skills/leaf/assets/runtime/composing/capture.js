/* Selection capture, snapping and the last passage the user selected.
 *
 * The response surface calls `remember` only at genuine selection gestures, refining
 * a completed pointer selection after snapping. One semantic anchor and direction survive same-page revisions;
 * neither editor selections nor programmatic restoration choose that passage.
 * Browser history separately owns the native working place at each return checkpoint.
 * Restore selection resolves current words through shared travel, refusing a missing
 * or ambiguous passage rather than choosing another occurrence. */
import { COLLAPSE } from "../collapse.js";
import {
  closestAcross,
  pageRange,
  pageText,
  pageWords,
  pointAt,
  selectEnds,
  selectionBackward,
  segmentBlock,
  segmentsIn,
  spanIn,
} from "../passages.js";
import { textUnits } from "../text-alignment.js";
import { anchorForRange, anchoringIsReady } from "../anchor-resolution.js";
import { takesLetters, focused } from "../focus.js";
import { notice } from "../notifications.js";
import { retainUserIntent } from "../user-intent.js";

// Selection and control-context capture use the same durable passage producer.
export const selectionAnchor = (sel) => anchorForRange(pageRange(sel));

// A selection of the page's own words, as against none, a bare caret, or one made inside
// the runtime's own layer. That is the line between a user reaching for a passage and
// one working the chrome, and it is the question every caller here is really asking.
//
// Whether anything is selected is asked of the range the user drew (`pageRange`), not of
// `isCollapsed`. A drag wholly inside an x-shadow widget comes back from Chrome with both
// ends clamped to the host's one place in the light DOM, so the selection reports itself
// collapsed while it paints and copies the words: code dragged across in a rendered diff
// raised no Comment field, and `c` opened a comment on the page with no passage at all.
// The anchor's side is still read off the clamped node, which is the host's place, and
// so answers for the widget the words are in.
const drawn = (sel) => Boolean(sel?.rangeCount) && !pageRange(sel).collapsed;
export const pageSelection = () => {
  const sel = getSelection();
  return drawn(sel) && pageWords(sel.anchorNode) ? sel : null;
};

export function createPassageSelection({ restore }) {
  let previous = null;
  return {
    remember(selection = pageSelection()) {
      if (!anchoringIsReady() || !selection || takesLetters(focused())) return;
      const anchor = selectionAnchor(selection);
      if (anchor.quote) previous = { anchor, backward: selectionBackward(selection) };
    },
    command: {
      id: "selection.restore",
      keys: ["v"],
      title: "Restore selection",
      description: "Restore the last selected passage",
      touch: "Restore selection",
      covering: true,
      when: () => previous !== null,
      run: async () => {
        const intent = retainUserIntent();
        const restored = await restore(previous.anchor, {
          backward: previous.backward,
          intent,
        });
        if (!restored && intent())
          notice("That selected passage is unavailable on this version");
      },
    },
  };
}
// Where a selection ends, as against where it began: the near end is what `pageSelection`
// asks about, and the far end is the one a drag can throw. The layer stands after and to
// the right of the document, so a hand that overshoots it puts the browser's own extension
// through everything in between — a passage five words long, a pointer 40px past the panel
// edge, and the capture came back holding 14,387 characters, a mark over 22,140 of them,
// and a field whose accessible name read the whole document out.
//
// Not a question `pageSelection` may fold in, and ⌘A is why: select-all means the document
// and lands its far end past the page's last words by definition, so a rule over every
// selection would refuse the one gesture that legitimately covers everything. Which
// gesture made it is what tells the two apart, and only the pointer release knows
// (composing/surface.js, where a drag that left the document is put back to what it had
// inside it).
export const leftThePage = (sel = getSelection()) =>
  drawn(sel) && !pageWords(sel.focusNode);
// A drag stops where the hand stopped, not where the user aimed: a release two glyphs
// short of a word's end meant the word, and the capture would store the fragment as if
// the fragment were the point. The pointer path therefore grows outward to word
// boundaries. When those words are also the opening and closing words of a sentence,
// the same pass includes its surrounding punctuation. A shorter phrase remains a
// phrase. Keyboard selections never come here: shift-arrow is the user being precise.
//
// One end, because the two are the same question asked at two places, and the words are
// read in the indexed text every other reading of the page uses. That is what keeps a
// snap from claiming what the capture would refuse: a word never continues across a
// fence, and never across a block seam, which is where the collapse writes the space the
// markup doesn't hold. One seam is snapping's own, past what the collapse knows: where
// machine-placed words (data-lf-gen) stand flush against the author's — a chip row is
// written with no space after the title it follows — the two runs read as one word, and
// growing across that seam would hand a selection of the chip the title too.
//
// Asked of two points of the page reading (`pointAt`), by the block and the generated
// element (`gen`) their segments carry.
const sameRun = (left, right) =>
  Boolean(left && right) &&
  segmentBlock(left.segment) === segmentBlock(right.segment) &&
  left.segment.gen === right.segment.gen;
const sentenceUnits = new Intl.Segmenter(undefined, { granularity: "sentence" });

// An EDGE in the reading: a position inside it that holds no character.
const edgeAt = (reading, i) =>
  i >= 0 && i < reading.raw.length && pointAt(reading, i) === null;

function snapOut(reading, at, back) {
  const { raw, fences } = reading;
  const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= at) ?? raw.length;
  // An EDGE's neighbours are the nearest characters, not the nearest cells: an empty
  // text node is an empty segment, which puts two EDGEs flush, and every reader of the
  // reading's points steps over its edges.
  const joined = (i) => {
    if (!edgeAt(reading, i)) return true;
    let a = i - 1;
    while (edgeAt(reading, a)) a--;
    let b = i + 1;
    while (edgeAt(reading, b)) b++;
    return sameRun(pointAt(reading, a), pointAt(reading, b));
  };
  const inRun = (i) => !/\s/.test(raw[i]) && joined(i);
  let lo = at;
  while (lo > behind && inRun(lo - 1)) lo--;
  let hi = at;
  while (hi < ahead && inRun(hi)) hi++;
  let run = "";
  let boundary = 0; // the end's own index within `run`
  const from = []; // from[i] = the raw index run[i] came from; an EDGE holds no character
  for (let i = lo; i < hi; i++) {
    if (edgeAt(reading, i)) continue;
    if (i < at) boundary++;
    from.push(i);
    run += raw[i];
  }
  const word = textUnits.segment(run).containing(boundary);
  if (!word || word.index >= boundary || !word.isWordLike) return at;
  return back ? from[word.index] : from[word.index + word.segment.length - 1] + 1;
}

// Sentence segmentation reads one passage cell inside one rendered block. Authored line
// wraps collapse to spaces, and edges between inline text nodes disappear. `from` keeps
// the path back to the DOM reading. A declared generated label is a separate speaking run
// even when it sits flush inside the same block.
function snapSentence(reading, lo, hi) {
  const { raw, fences } = reading;
  const point = (i) => pointAt(reading, i);
  const first = point(lo);
  const last = point(hi - 1);
  if (!first || !last) return [lo, hi];
  // Sentence punctuation is prose structure. In code, the same glyphs are syntax:
  // the closing brace and quote after a selected interpolation are not part of the
  // expression the user selected. Token highlighting makes that boundary especially
  // visible by putting the delimiters in their own text nodes, but the semantic answer
  // is the same for plain and highlighted code.
  if (closestAcross(first.node, "pre,code")) return [lo, hi];

  const belongs = (part) => sameRun(first, part);
  if (!belongs(last) || fences.some((f) => f > lo && f < hi)) return [lo, hi];
  for (let at = lo; at < hi; at++) {
    const part = point(at);
    if (part && !belongs(part)) return [lo, hi];
  }

  const behind = fences.filter((f) => f <= lo).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= hi) ?? raw.length;
  const inScope = (at) => {
    const part = point(at);
    if (part) return belongs(part);
    let before = at - 1;
    while (before >= behind && edgeAt(reading, before)) before--;
    let after = at + 1;
    while (after < ahead && edgeAt(reading, after)) after++;
    return belongs(point(before)) && belongs(point(after));
  };

  let start = lo;
  while (start > behind && inScope(start - 1)) start--;
  let stop = hi;
  while (stop < ahead && inScope(stop)) stop++;

  let text = "";
  let selectedStart = 0;
  let selectedStop = 0;
  const from = [];
  let inWhitespace = false;
  for (let at = start; at < stop; at++) {
    if (edgeAt(reading, at)) continue;
    const character = raw[at].replace(COLLAPSE, " ");
    const whitespace = character === " ";
    if (whitespace && inWhitespace) continue;
    inWhitespace = whitespace;
    if (at < lo) selectedStart++;
    if (at < hi) selectedStop++;
    from.push(at);
    text += character;
  }

  const sentences = [...sentenceUnits.segment(text)];
  const atStart = sentences.find(
    (sentence) =>
      sentence.index <= selectedStart &&
      selectedStart < sentence.index + sentence.segment.length,
  );
  const atStop = sentences.find(
    (sentence) =>
      sentence.index < selectedStop &&
      selectedStop <= sentence.index + sentence.segment.length,
  );
  const edges = (sentence) => {
    if (!sentence) return null;
    const words = [...textUnits.segment(sentence.segment)].filter(
      (part) => part.isWordLike,
    );
    if (!words.length) return null;
    const firstWord = words[0].index;
    const lastWord = words.at(-1).index + words.at(-1).segment.length;
    const leading = sentence.segment.slice(0, firstWord).match(/\p{P}+$/u)?.[0] ?? "";
    const trailing = sentence.segment.slice(lastWord).match(/^\p{P}+/u)?.[0] ?? "";
    return {
      contentStart: sentence.index + firstWord - leading.length,
      contentStop: sentence.index + lastWord + trailing.length,
      firstWord: sentence.index + firstWord,
      lastWord: sentence.index + lastWord,
    };
  };

  let snappedStart = selectedStart;
  const startEdges = edges(atStart);
  if (
    startEdges &&
    selectedStart >= startEdges.contentStart &&
    selectedStart <= startEdges.firstWord
  )
    snappedStart = startEdges.contentStart;

  let snappedStop = selectedStop;
  const stopEdges = edges(atStop);
  if (
    stopEdges &&
    selectedStop >= stopEdges.lastWord &&
    selectedStop <= stopEdges.contentStop
  )
    snappedStop = stopEdges.contentStop;

  return [
    snappedStart === selectedStart ? lo : from[snappedStart],
    snappedStop === selectedStop ? hi : from[snappedStop - 1] + 1,
  ];
}
// An end the snap didn't move keeps the boundary the browser gave it: a drag out into
// chrome ends past the last quotable character, and rewriting that end from the reading
// would pull the visible selection off words the user chose to cover. The gesture's
// direction survives too, or the shift-click that next extends the selection would
// extend it from the wrong end.
export function snapSelection() {
  if (!anchoringIsReady()) return;
  const sel = pageSelection();
  if (!sel) return;
  const range = pageRange(sel);
  const segments = segmentsIn(range);
  if (!segments.length) return;
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  let lo = snapOut(reading, start, true);
  let hi = snapOut(reading, stop, false);
  [lo, hi] = snapSentence(reading, lo, hi);
  if (lo === start && hi === stop) return;
  const first = pointAt(reading, lo);
  const last = pointAt(reading, hi - 1);
  const head =
    lo === start
      ? [range.startContainer, range.startOffset]
      : [first.node, first.offset];
  const tail =
    hi === stop ? [range.endContainer, range.endOffset] : [last.node, last.offset + 1];
  if (selectionBackward(sel, range)) selectEnds(tail, head);
  else selectEnds(head, tail);
}
