/* lf-diff: upgraded because it parses. The body is a unified diff (data, not
 * prose), rendered as one <details> per file — native disclosure — with add/del
 * tints and per-file +/− counts. The evidence rule mechanized for code changes:
 * paste the real diff instead of paraphrasing it.
 *
 * Syntax colour rides on top, from each file's own path (langForPath): the tints
 * are the widget's statement about a line and the token colours are the file's
 * about its words, and they are a background and an ink, so neither is spending
 * the other's channel. A diff sits beside lf-code on the pages that carry both —
 * pr-walkthrough shows the same four lines twice — and leaving one plain says the
 * evidence is not code.
 *
 * What gets tokenized is a hunk, one side at a time, with the +/−/space column
 * cut off. Each of those is load-bearing; see colorHunks.
 *
 * A tint says a line changed and stops there, which on a line that changed by one
 * word leaves the reader to eyeball-diff it against the line above. So a deletion
 * paired with the addition answering it marks the words that moved — the layer's own
 * answer to which words differ, gated on shared ink (movedWords) — and the marks nest
 * inside the token spans the colouring already built. Which line answers which is worked
 * out from that same shared ink rather than assumed from the order the lines stand in
 * (blockPairs); what a mark is made of, and why it is a wrapper here where the document
 * paints, is bodyNodes; why it is ruled rather than tinted deeper is the theme's own
 * comment, and the answer is that the tint spent the contrast. */
import {
  DISCLOSE,
  dataBody,
  failSoft,
  keys,
  movedWords,
  once,
  settle,
  shadowStage,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "/runtime/widget-api.js";

// One entry per file: {path, adds, dels, lines: [{kind, text}]} where kind is
// add | del | ctx | hunk | note. Tolerates both `diff --git` and bare ---/+++
// file headers; anything before the first header fails the parse. Whether a
// `--- ` line is a header is the format's own statement, not a guess from what
// the line looks like: an @@ header declares how many old and new lines the hunk
// holds, so while either count is outstanding every line is the hunk's — a
// *deleted* line whose content starts with `-- ` (a SQL comment, say) renders as
// `--- …` and stays a deletion even when an added `++ …` renders `+++ …` right
// under it. Only once the hunk is paid off can `--- ` followed by `+++ ` open
// the next file.
function parseDiff(text) {
  const files = [];
  let file = null;
  let expectPlus = false;
  let oldLeft = 0; // hunk lines the last @@ header still promises, per side
  let newLeft = 0;
  const start = (path) => {
    file = { path, adds: 0, dels: 0, lines: [] };
    files.push(file);
  };
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // A hunk's own lines start with +, -, space or backslash, so `diff --git` and
    // `@@` are headers wherever they stand; only a `--- `-shaped line needs the
    // counts to say which it is.
    const inHunk = oldLeft > 0 || newLeft > 0;
    if (line.startsWith("diff --git ")) {
      start(line.split(" b/").pop());
      expectPlus = false;
      oldLeft = newLeft = 0;
      continue;
    }
    if (
      line.startsWith("--- ") &&
      lines[i + 1]?.startsWith("+++ ") &&
      // A header, not a deleted `-- ` line: outside a hunk by the counts, or the
      // full ---/+++/@@ header run, which no hunk content can spell — a ctx line
      // starts with a space, so `@@` third is the format's own signature and
      // rescues a hand-written hunk whose counts overstate.
      (!inHunk || lines[i + 2]?.startsWith("@@"))
    ) {
      // A bare ---/+++ pair opens a file unless `diff --git` already did.
      if (!file || file.lines.some((l) => l.kind === "hunk")) start("");
      oldLeft = newLeft = 0;
      expectPlus = true;
      continue;
    }
    if (file === null) throw new Error("not a unified diff (no file header)");
    if (expectPlus && line.startsWith("+++ ")) {
      expectPlus = false;
      const path = line.slice(4).replace(/^b\//, "");
      if (!file.path && path !== "/dev/null") file.path = path;
    } else if (line.startsWith("@@")) {
      const counts = /^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@/.exec(line);
      oldLeft = counts ? +(counts[1] ?? 1) : 0;
      newLeft = counts ? +(counts[2] ?? 1) : 0;
      file.lines.push({ kind: "hunk", text: line });
    } else if (line.startsWith("\\ ")) {
      // `\ No newline at end of file` — git remarking on the line above rather than
      // showing one of its own. Shown, because it is something the diff says, but its
      // own kind: read as context it would be a line of the file that isn't there, and
      // the colouring would hand it to the tokenizer as source. Not one of the hunk's
      // counted lines either.
      file.lines.push({ kind: "note", text: line });
    } else if (line.startsWith("+")) {
      // Anywhere, not only inside a paid hunk, so a hand-written diff carrying no
      // @@ headers still shows its changes.
      newLeft--;
      file.adds++;
      file.lines.push({ kind: "add", text: line });
    } else if (line.startsWith("-")) {
      oldLeft--;
      file.dels++;
      file.lines.push({ kind: "del", text: line });
    } else if (inHunk || line.startsWith(" ") || line === "") {
      // Context by shape wherever the counts don't claim it: a space-led line can
      // only be context — in a hand-written hunk whose numbers are approximate,
      // and in a body carrying no @@ headers at all. The counts decide only the
      // `--- ` question above, where the shapes genuinely collide.
      oldLeft--;
      newLeft--;
      file.lines.push({ kind: "ctx", text: line });
    }
    // Outside a hunk everything else is git's metadata about the file — index,
    // mode, rename, copy, similarity, Binary files — not lines of it: skipped,
    // rather than shown as content the file never had.
  }
  return files;
}

// A file's lines coloured: index into file.lines → the line's tokens, absent where
// nothing coloured it. Three decisions, and the simpler answer to each is wrong in a way
// only a real diff shows:
//
// The hunk is the unit. A hunk's lines are contiguous source; a file's are not, and
// gluing them across an @@ boundary would lex code that never sat together. It also
// bounds the one failure a fragment cannot avoid — a hunk opening inside a docstring
// has no opener to close, so its closing `"""` opens a string that eats the rest — to
// the hunk it happened in.
//
// Each side, separately. A hunk interleaves two versions, so read straight through it
// the deleted `if x:` and the added `if x is None:` are consecutive. The old side is
// ctx+del and the new side ctx+add; each is a version of the file that really existed.
// A context line is written twice and the new side lands last, because the new side is
// the text the user is being asked to approve.
//
// Without the +/−/space column. The prefix is the diff's word about the line, not the
// file's, and a tokenizer reads it as the file's: yaml calls a leading `-` a sequence
// bullet (keyword ink) and a leading `+` a string, so leaving it on paints the deletion
// marker red and the addition marker blue — the widget's own signal, restated wrong.
async function colorHunks(file, lang) {
  const runs = []; // one per (hunk, side): the line indices it covers, in order
  let hunk = [];
  const close = () => {
    if (hunk.length)
      for (const kinds of [
        ["ctx", "del"],
        ["ctx", "add"],
      ])
        runs.push(hunk.filter((i) => kinds.includes(file.lines[i].kind)));
    hunk = [];
  };
  file.lines.forEach((line, i) => {
    // A hunk runs until the diff stops showing the file's lines. git's remark doesn't
    // stop it — the hunk carries on past a `\ No newline` — the remark just isn't one of
    // those lines, so it goes into neither side.
    if (line.kind === "hunk") close();
    else if (line.kind !== "note") hunk.push(i);
  });
  close();

  const colored = new Map();
  for (const run of runs) {
    if (!run.length) continue;
    const source = run.map((i) => file.lines[i].text.slice(1)).join("\n");
    let lines;
    try {
      lines = tokenLines(await syntax(source, lang));
    } catch (err) {
      // The partition promise broke, or the bundle lacks a language $languages names.
      // Either way these tokens can't be trusted to line up, so this run stays plain and
      // says so — the console error is what `version check --render` fails on. Per run rather
      // than per diff, the way highlightBlocks fails per block: the diff itself parsed.
      console.error(`leaf: lf-diff could not color a ${lang} hunk`, err);
      continue;
    }
    // One array per line and no default: syntax promises the tokens rejoin the source,
    // and the source is these lines joined by newlines, so tokenLines returns exactly
    // this many. Should that ever stop being true, an absent entry leaves the line
    // uncoloured rather than substituting an empty one, which would blank its text.
    run.forEach((i, n) => colored.set(i, lines[n]));
  }
  return colored;
}

// Which line answers which, inside one change block: `[deletion, addition, moved]` per
// pair, as indices into `dels` and `adds`. No pair crosses another, and the pairing holds
// as much ink still as any such pairing can, over the pairs `movedWords` is willing to mark
// at all — so the gate is untouched and nothing here measures likeness a second way. Ties
// go to the pair, so a block whose lines answer each other in order comes out exactly as
// reading straight down does.
//
// Reading straight down — the i-th deletion against the i-th addition — is the pairing a
// reader's eye makes, and it holds until a line is added. On examples/pr-walkthrough.html
// a two-line body grows to four, and `return request.remote_addr` met `if request.token:`,
// two lines above its own answer; they share `request.` and the gate passes them, so four
// words were ruled as having moved between two lines with nothing to do with each other.
// The marks read perfectly well, so nothing on the rendered page gave the pairing away.
// Over 10,352 change blocks from this repo's own history, 12.3% of the pairs that carried
// marks had another addition in the same block sharing strictly more ink with that
// deletion, and 15.2% of blocks left a deletion unmarked with its answer standing
// elsewhere in the same block.
//
// The search slides by the block's own count difference and no further, since the extra
// lines on one side are what push the two out of step: a block that adds as many lines as
// it removes is read straight down, which is where git's own contrib/diff-highlight stops
// ("we could try to be clever and match up similar lines") and what a line-for-line rewrite
// means. The block says how far to look, so no constant here does, and over the corpus
// above the search finds 98.6% of the ink an unbounded one pairs, against 77.8% for
// reading straight down.
//
// It bounds the work too, and hardest where an unbounded search is worst: a wholesale
// replacement of 400 lines is 400 comparisons rather than 160,000. What it does not bound
// is a block long on both sides *and* lopsided, where the counts differ enough to open the
// slack wide and there are still many lines to slide through it — 200 deletions under 400
// additions is 60,100 comparisons, a hundred and fifty times the replacement above. The
// largest block in the corpus was 3,087, that shape wanting hundreds of consecutive changed
// lines with no unchanged one among them, so the cost is left where the block puts it
// rather than answered with a ceiling nothing has reached.
function blockPairs(dels, adds) {
  const width = adds.length;
  const slack = Math.abs(width - dels.length);
  const found = new Map(); // deletion * width + addition → what movedWords said of the pair
  for (let i = 0; i < dels.length; i++)
    for (let k = Math.max(0, i - slack); k <= Math.min(width - 1, i + slack); k++) {
      const moved = movedWords(dels[i], adds[k]);
      // A replacement rather than an edit: the tint said that, and marking every word of
      // both lines would say no more — so it is no answer to which line this one is.
      if (moved) found.set(i * width + k, moved);
    }
  // Every pairing's total, taken from the end backwards, so the walk out from (0, 0) reads
  // its own next step off them rather than a second table recording one. Held by how far a
  // cell stands off the diagonal, so the table costs what the search costs: a file replaced
  // line for line has no slack, and a table over every (deletion, addition) would spend the
  // whole rectangle — 25 million cells on a 5,000-line replacement — to say that each line
  // answers the one beneath it.
  //
  // One column wider than the band either side, because the walk between two pairs inside
  // it steps one at a time: taking the deletion first dips an offset below the lower of the
  // two, taking the addition first lifts it above the higher, and one of those has to
  // happen wherever the two pairs sit at the same offset. One column is also enough, which
  // is a claim to check rather than reason out — with none, this and a table over the whole
  // rectangle part company on 95 of the corpus's 10,352 blocks; with one, on none of them.
  const reach = slack + 1;
  const span = 2 * reach + 3; // and a column either side of that, standing in for the zero
  const rest = new Uint32Array((dels.length + 1) * span);
  const cell = (i, k) => i * span + (k - i + reach + 1);
  const total = (i, k) => (Math.abs(k - i) > reach + 1 ? 0 : rest[cell(i, k)]);
  const withPair = (i, k) => {
    const moved = found.get(i * width + k);
    return moved ? moved.shared + total(i + 1, k + 1) : 0;
  };
  for (let i = dels.length - 1; i >= 0; i--)
    for (let k = Math.min(width - 1, i + reach); k >= Math.max(0, i - reach); k--)
      rest[cell(i, k)] = Math.max(withPair(i, k), total(i + 1, k), total(i, k + 1));

  const pairs = [];
  // A standing total of nothing is a block with no pair left in it, which is where a walk
  // over a table this shape has to stop: every step from here is a step further out of the
  // band, and out there the table holds the zero rather than an answer.
  for (let i = 0, k = 0; i < dels.length && k < width && total(i, k);) {
    const moved = found.get(i * width + k);
    if (moved && withPair(i, k) === total(i, k)) {
      pairs.push([i, k, moved]);
      i++;
      k++;
    } else if (total(i + 1, k) >= total(i, k + 1)) i++;
    else k++;
  }
  return pairs;
}

// The words that moved, per line: index into file.lines → [from, to) spans into that
// line's text with its +/−/space column off, the same slice colorHunks tokenizes and for
// the same reason — the prefix is the diff's word about the line rather than the file's,
// so an alignment that keeps it aligns a `-` with a `+` and marks the marker as a word
// that moved.
//
// A word-level mark compares one deletion against one addition and a hunk offers a block
// of each, so something has to say which line answers which. A change block is a run of
// deletions and the run of additions under it, and a unified diff records no
// correspondence between the two sides at all, so the correspondence is worked out from
// what the lines say — by the layer's own reading of it, since `movedWords` already
// returns how much ink a pair holds still (blockPairs). A pair the gate refuses is no
// candidate, and a deletion left without one is unmarked: the tint is the whole statement
// about a line nothing was compared against.
//
// A note is transparent here, exactly as it is to colorHunks. `\ No newline at end of
// file` is git remarking on the line above rather than a line of the file, and it stands
// between a deletion and the addition answering it whenever the old file ended without
// one — read as a line it would close the block and cost that pair its marks.
function movedInFile(file) {
  const marks = new Map();
  let dels = [];
  let adds = [];
  const close = () => {
    const body = (i) => file.lines[i].text.slice(1);
    for (const [n, m, moved] of blockPairs(dels.map(body), adds.map(body))) {
      marks.set(dels[n], moved.del);
      marks.set(adds[m], moved.ins);
    }
    dels = [];
    adds = [];
  };
  file.lines.forEach((line, i) => {
    if (line.kind === "note") return;
    if (line.kind === "add") adds.push(i);
    else if (line.kind === "del" && !adds.length) dels.push(i);
    else {
      // A context or hunk line ends the block; so does a deletion after an addition,
      // which opens the next one.
      close();
      if (line.kind === "del") dels.push(i);
    }
  });
  close();
  return marks;
}

// Tokens re-cut so none crosses `from`..`to`, the way tokenLines re-cuts so none crosses a
// newline: a token's run and a moved word are two different spans of the same characters,
// and this is where they are reconciled. Cutting is what keeps synNodes the one thing that
// turns a token into a node — the alternative is a second place building a role span, and
// a second place to forget the attribute.
const tokensIn = (tokens, from, to) => {
  const cut = [];
  let at = 0;
  for (const { text, role } of tokens) {
    const start = Math.max(from, at);
    const end = Math.min(to, at + text.length);
    if (end > start) cut.push({ text: text.slice(start - at, end - at), role });
    at += text.length;
  }
  return cut;
};

// One line's body as nodes: the moved words wrapped, everything else as it was. The
// wrapper is the module's own chrome and wears the module's own attribute (data-lf-diff,
// valued with the side it marks), the author's namespace on a widget being the registry's
// to state and nothing else being a module's to write in.
//
// Wrapping, where the document's own emphasis paints (Paint; don't wrap): ::highlight()
// takes Ranges the document can reach and a shadow tree is not one of them. What that norm
// is about is a redraw swapping the node under a pointer between a mousedown and its
// mouseup — these are built once, in the pass that builds the line, before any of it is
// staged, and nothing repaints them after.
//
// The text is untouched either way. A <span> is no text block, so both readings of the
// page (says/wrote) return exactly the characters they did before the marks went in, and
// an uncoloured line takes the same path with its whole body as one roleless token.
function bodyNodes(tokens, spans, side) {
  const nodes = [];
  const total = tokens.reduce((n, token) => n + token.text.length, 0);
  let at = 0;
  for (const [from, to] of spans) {
    nodes.push(...synNodes(tokensIn(tokens, at, from)));
    const mark = document.createElement("span");
    mark.dataset.lfDiff = side;
    mark.append(...synNodes(tokensIn(tokens, from, to)));
    nodes.push(mark);
    at = to;
  }
  nodes.push(...synNodes(tokensIn(tokens, at, total)));
  return nodes;
}

function fileNode(file, colored) {
  const details = document.createElement("details");
  details.open = true;
  const summary = document.createElement("summary");
  summary.append(
    Object.assign(document.createElement("code"), {
      textContent: file.path || "(unnamed file)",
    }),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-stat",
      textContent: `+${file.adds} −${file.dels}`,
    }),
  );
  // The keys a disclosure answers are the runtime's, so this binds no `run` — one would
  // work a disclosure the disclosure scope has already worked — and exists to say the word
  // in this file's own terms. Which word depends on what the reader can see standing here,
  // so it is read where it is painted rather than named once for both branches. The
  // bindings are read the same way and off the same declaration, because a row that named
  // one key fewer than the row running them would take the rest off the line, and one key
  // more would promise a press nothing makes.
  keys(summary, "On a diff", [
    {
      keys: () => DISCLOSE(summary),
      does: () => `${details.open ? "Hide" : "Show"} that file's diff`,
      line: () => `${details.open ? "hide" : "show"} this file`,
    },
  ]);

  const pre = document.createElement("pre");
  // A line longer than the measure scrolls inside this box, and a region only a
  // wheel can move is off-limits to a keyboard: the box takes a tab stop and a
  // name, and the browser scrolls it with the arrows — in a dead copy too, since
  // scrolling needs no handler (the lf-shot bargain).
  pre.tabIndex = 0;
  pre.setAttribute("role", "region");
  pre.setAttribute("aria-label", file.path || "diff");
  const moved = movedInFile(file);
  file.lines.forEach(({ kind, text }, i) => {
    const line = Object.assign(document.createElement("span"), { className: kind });
    // The prefix goes back exactly as it came, at full ink: where a rendering drops
    // backgrounds it is the only thing left saying the line changed, and it is outside
    // every mark for the same reason — the marks are about the line's words. Neither
    // colour nor emphasis adds a character or moves one, so what the page says here is
    // what the file says.
    if (text) line.append(text.slice(0, 1));
    // An uncoloured line is its own body as one roleless token, so both take the same
    // path: a path with no language, a hunk the tokenizer refused, and a coloured line
    // are one case here rather than a branch that only one of them ever marks.
    const body = text.slice(1);
    const tokens = colored.get(i) ?? (body ? [{ text: body }] : []);
    line.append(...bodyNodes(tokens, moved.get(i) ?? [], kind), "\n");
    pre.append(line);
  });
  details.append(summary, pre);
  return details;
}

customElements.define(
  "lf-diff",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // Registered with settle() so the runtime holds the first anchor pass until the
      // lines are in: the tokenizer loads lazily, and one writer has to finish before
      // another reads.
      settle(this.render());
    }

    async render() {
      // Only blank edge lines are trimmed: diff content is column-sensitive
      // (a leading space means context), so the body is authored at column 0.
      const source = dataBody(this)
        .replace(/^\n+/, "")
        .replace(/\n\s*$/, "");
      try {
        const files = parseDiff(source);
        if (!files.length) throw new Error("empty diff");
        const nodes = [];
        for (const file of files) {
          // A path with no language — a Dockerfile, a .txt, an extension the table
          // doesn't name — is a file that stays plain, the way a lf-code without `language`
          // does. Nothing is guessed from what the lines look like.
          const lang = langForPath(file.path);
          nodes.push(fileNode(file, lang ? await colorHunks(file, lang) : new Map()));
        }
        // Into a shadow root (x-shadow). The runtime's reading follows the composed
        // tree, which is why the lines in here stay as quotable as any paragraph — see
        // textNodesUnder. The authored <pre> goes, exactly as it did when this rendered
        // in place: a host's light children stop rendering the moment it has a shadow
        // root, and markup that is in the file but on nobody's screen is what a copy
        // reports as content it can't show.
        this.replaceChildren();
        shadowStage(this, nodes);
        this.classList.add("lf-rendered");
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
