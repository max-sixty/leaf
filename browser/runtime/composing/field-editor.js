/* A field's editor: CodeMirror under the runtime's text field (text-field.js), and the
 * Markdown preview that draws the field's source the way a sent message reads.
 *
 * CodeMirror loads on request (`loadFieldEditor`; text-field.js says when). Only what
 * needs CodeMirror is built once it arrives (`fieldEditor`); the rest of this module,
 * and the runtime it reads, loads with the page. Rejected: importing this module
 * lazily, which gave the kernel's compiler a new entry whose runtime imports regrouped
 * its shared chunks, adding four requests to every opening. text-field.js owns the
 * field's behavior and its contract with owners; this module owns what CodeMirror needs
 * to carry it out: the state a field's words start from (`fieldState`), the
 * transactions that reconfigure it, and the preview's decorations and faces. The
 * compartments are shared by every field's state, as a compartment names a slot in a
 * state's configuration rather than holding one.
 */
import { externalMark as externalLinkMark, opensElsewhere } from "../declared-words.js";

import { leafEditorView } from "../editor-view.js";
import { loadMarkdown, markdownReady, placedMarkdownTokens } from "../markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "../media.js";

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. A last line holding nothing past its
// quotes' `>` and its items' markers is where the next words will be typed, so it is
// read holding a word, and stands in whichever block those words will join, as a line
// of an open fence's code, or of a quote or list item they continue lazily, and not in a
// list the line only trails; a block that takes it ends past the draft. So a new nested
// item is an item from its marker on, though the message reads an empty one as words of
// the paragraph above it. Nothing is placed in the word itself. Empty until the renderer
// has loaded.
const read = (state) => {
  const source = state.doc.toString();
  const last = state.doc.line(state.doc.lines).text;
  if (!/^(?:[\s>]|(?:[-+*]|\d{1,9}[.)])[ \t])*$/.test(last))
    return placedMarkdownTokens(source);
  return placedMarkdownTokens(`${source}x`).filter(
    ({ token, to }) => token.block || to <= source.length,
  );
};

// Columns of leading whitespace, a tab reaching the next multiple of four, as the
// renderer counts them.
const columns = (text) => {
  let col = 0;
  for (const ch of text) col = ch === "\t" ? col + 4 - (col % 4) : col + 1;
  return col;
};
const ITEM = "list_item_open";
const LIST = /^(bullet|ordered)_list_open$/;
// A list item's reading takes in the blank lines after its blocks, but words typed on
// one stand outside it: it ends with its last block, or its last item's marker line.
const itemEnd = (placed, item) =>
  Math.max(
    ...placed
      .filter(
        ({ token, from, to }) =>
          token.block && !LIST.test(token.type) && from >= item.from && to <= item.to,
      )
      .map((b) => (b.token.type === ITEM ? b.from + 1 : b.to)),
  );

/** Tab nests the list items the selection is in under the item above each, and
 * Shift+Tab takes them out a level, as the message will read the draft (`read`), the
 * reading Shift+Enter continues by (`continueBlocks`). A nested item's marker stands
 * where the words of the item above start, so the message reads it as the next item
 * of the list already nested there, in that list's marker, or as the first of a new
 * one, numbered from 1. Taken out, it stands where its parent's marker stands, as the
 * next item of the parent's list in that list's marker, and the items after it in its
 * own list stay where they are, nested in it now. An item's later lines and the items
 * nested in it move with it, and each line keeps its quotes' `>`. Selected items move
 * together: one whose item above moves too moves as far as that one. Returns the
 * changes to `source`, none for an item with nowhere to go (the first in its list, or
 * one in no other item), or null where the selection is in no list item. Touch has
 * no Tab: typing the spaces nests an item there, as it does anywhere. */
export function nestItems(source, placed, from, to, deeper) {
  const starts = [0];
  for (let at = source.indexOf("\n"); at !== -1; at = source.indexOf("\n", at + 1))
    starts.push(at + 1);
  const lineStart = (pos) => starts.findLast((start) => start <= pos);
  const lineEnd = (start) => {
    const at = source.indexOf("\n", start);
    return at === -1 ? source.length : at;
  };
  const items = placed.filter(({ token }) => token.type === ITEM);
  const end = (item) => Math.min(source.length, itemEnd(placed, item));
  const within = (c, at) => c.from <= at && at < c.to;
  const first = lineStart(from);
  const last = to > from && lineStart(to) === to ? lineStart(to - 1) : lineStart(to);
  const holding = items.filter((i) => i.from <= first && first < end(i)).at(-1);
  const chosen = items.filter(
    (i) => i === holding || (i.from >= first && i.from <= last),
  );
  if (!chosen.length) return null;

  const listOf = (i) =>
    placed.findLast(
      (c) =>
        LIST.test(c.token.type) &&
        c.token.level === i.token.level - 1 &&
        within(c, i.from),
    );
  const siblings = (i) =>
    items.filter((s) => s.token.level === i.token.level && within(listOf(i), s.from));
  const above = (i) => siblings(i).findLast((s) => s.from < i.from);
  const parent = (i) => {
    const list = listOf(i);
    return items.findLast(
      (c) => c.token.level === list.token.level - 1 && within(c, list.from),
    );
  };
  // The marker of the item after `c` in its list.
  const next = ({ token }) => `${token.info && Number(token.info) + 1}${token.markup}`;
  // Where an item's line starts past the `>` of the quotes it stands in, the column
  // its marker stands at past that, its marker, and the columns from the marker to
  // its words, one for an item with none or more than four, as the renderer reads it.
  const quotes = (i) =>
    placed.filter(
      (c) =>
        c.token.type === "blockquote_open" &&
        c.token.level < i.token.level &&
        within(c, i.from),
    );
  const base = (i, start) =>
    Math.max(
      start,
      ...quotes(i)
        .flatMap((q) => q.markers)
        .filter(([a]) => a >= start && a <= lineEnd(start))
        .map(([, b]) => b),
    );
  const shape = (i) => {
    const at = base(i, i.from);
    const [a, b] = i.markers[0];
    const mark = source.slice(a, b).trimEnd();
    const rest = source.slice(a + mark.length, lineEnd(i.from));
    const gap = rest.trim() ? columns(rest.match(/^[ \t]*/)[0]) : 1;
    const lead = source.slice(at, a);
    return {
      at,
      lead,
      marker: a,
      col: columns(lead),
      mark,
      words: columns(lead) + mark.length + (gap > 4 ? 1 : gap),
    };
  };

  const changes = [];
  const moved = [];
  for (const item of chosen) {
    if (moved.some(({ item: m }) => m.from < item.from && item.from < end(m))) continue;
    const own = shape(item);
    // An item whose marker follows another's on its line moves only with that one.
    if (/\S/.test(own.lead)) continue;
    let col;
    let mark = own.mark;
    if (deeper) {
      const before = above(item);
      if (!before) continue;
      const along = moved.find((m) => m.item === before);
      if (along) col = own.col + along.shift;
      else {
        col = shape(before).words;
        const inside = placed.filter(
          (c) =>
            c.token.block &&
            c.token.level === before.token.level + 1 &&
            within(before, c.from),
        );
        const list = inside.at(-1);
        if (list && LIST.test(list.token.type))
          mark = next(
            items.findLast(
              (c) => c.token.level === list.token.level + 1 && within(list, c.from),
            ),
          );
        else if (item.token.info) mark = `1${item.token.markup}`;
      }
    } else {
      const outer = parent(item);
      if (!outer) continue;
      col = shape(outer).col;
      mark = next(outer);
    }
    const shift = col - own.col;
    // The words move as far as the marker, and as far again as the marker grows.
    const by = shift + mark.length - own.mark.length;
    changes.push(
      mark === own.mark
        ? { from: own.at, to: own.marker, insert: " ".repeat(col) }
        : {
            from: own.at,
            to: own.marker + own.mark.length,
            insert: " ".repeat(col) + mark,
          },
    );
    for (const start of starts) {
      if (start <= item.from || start >= end(item)) continue;
      const at = base(item, start);
      const lead = source.slice(at, lineEnd(start)).match(/^[ \t]*/)[0];
      if (at + lead.length === lineEnd(start)) continue;
      changes.push({
        from: at,
        to: at + lead.length,
        insert: " ".repeat(Math.max(0, columns(lead) + by)),
      });
    }
    moved.push({ item, shift });
  }
  return changes.filter(({ from, to, insert }) => source.slice(from, to) !== insert);
}

/** The renderer's token types the preview draws (`decorate`), each as close to the
 * message as the editor's lines allow; it reads no other, so the source of any other
 * stays as typed. tests/runtime/markdown-preview.test.mjs holds every rule the renderer
 * enables to this list or to its recorded exceptions, such as a table. */
export const DRAWN = new Set([
  "paragraph_open",
  "heading_open",
  "blockquote_open",
  "bullet_list_open",
  "ordered_list_open",
  "list_item_open",
  "fence",
  "hr",
  "text",
  "hardbreak",
  "code_inline",
  "em_open",
  "strong_open",
  "s_open",
  "link_open",
  "image",
  "html_inline",
]);

// The elements the renderer sends each block as, in an order that stands each one
// between others, as a block inside a body stands.
const FACE_PROBE =
  "<div></div><p></p><h1></h1><h2></h2><h3></h3><h4></h4><h5></h5><h6></h6><pre></pre>" +
  "<blockquote></blockquote><hr><ul><li></li><li></li></ul><ol></ol><div></div>";
// The gap two blocks' margins leave between them, collapsed as the platform collapses
// adjoining margins, in px or as CSS over the two a gap line names (`standBlocks`).
const collapsed = (a, b) => Math.max(a, b, 0) + Math.min(a, b, 0);
const GAP =
  "calc(max(var(--lf-gap-end), var(--lf-gap-start), 0px) + " +
  "min(var(--lf-gap-end), var(--lf-gap-start), 0px))";
// The rules that draw each block in the face the cascade gives it in `display`, the
// element whose blocks the field's words are shown as: their type, and the margins and
// padding that set them apart from their neighbours. The probe is an empty copy of that
// element standing beside the field, in its place among its siblings, so the page's own
// rules, which skip Leaf's interface, and its density reach the probe's blocks as they
// reach the display's. A list's outer margins collapse with its first and last items'.
export function readFaces(field, display) {
  const probe = /** @type {HTMLElement} */ (display.cloneNode(false));
  probe.removeAttribute("id");
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText =
    "position: absolute; visibility: hidden; inline-size: 0; display: block";
  probe.innerHTML = FACE_PROBE;
  field.after(probe);
  const face = {};
  // Type the field already inherits stays inherited: a line height restated in pixels
  // can round otherwise than the one it resolves from.
  const own = getComputedStyle(field);
  const TYPE = ["font-size", "line-height", "font-weight", "letter-spacing"];
  for (const node of probe.querySelectorAll(":scope > :not(div), li + li")) {
    const s = getComputedStyle(node);
    const px = (value) => Number.parseFloat(value) || 0;
    face[node.localName] = {
      type: TYPE.filter(
        (name) => s.getPropertyValue(name) !== own.getPropertyValue(name),
      )
        .map((name) => `${name}: ${s.getPropertyValue(name)}`)
        .join("; "),
      start: px(s.marginTop),
      end: px(s.marginBottom),
      padStart: px(s.paddingTop),
      padEnd: px(s.paddingBottom),
      inset: s.paddingInlineStart,
      indent: s.marginInlineStart,
    };
  }
  probe.remove();
  const { li, pre, blockquote: quote } = face;
  const rules = [];
  for (const [tag, { type, start, end }] of Object.entries(face)) {
    const list = tag === "ul" || tag === "ol";
    rules.push(
      `.lf-face-${tag} { ${type} }`,
      `.lf-starts-${tag} { --lf-gap-start: ${list ? collapsed(start, li.start) : start}px }`,
      `.lf-ends-${tag} { --lf-gap-end: ${list ? collapsed(end, li.end) : end}px }`,
    );
  }
  rules.push(
    `.lf-face-gap { line-height: ${GAP} }`,
    `.lf-face-gap.lf-face-share-2 { line-height: calc(${GAP} / 2) }`,
    `.lf-face-gap.lf-face-share-3 { line-height: calc(${GAP} / 3) }`,
    `.lf-face-gap-above { padding-block-start: ${GAP} }`,
    `.lf-face-code { padding-inline: ${pre.inset} }`,
    `.lf-face-quote { margin-inline-start: ${quote.indent}; --quote-inset: ${quote.inset} }`,
    `.lf-face-quote-first { padding-block-start: ${quote.padStart}px }`,
    `.lf-face-gap-above.lf-face-quote-first { padding-block-start: calc(${GAP} + ${quote.padStart}px) }`,
    `.lf-face-quote-last { padding-block-end: ${quote.padEnd}px }`,
    `.lf-face-item { padding-block-start: ${collapsed(li.end, li.start)}px }`,
    `.lf-face-list-lead { padding-block-start: ${collapsed(0, li.start)}px }`,
    `.lf-face-list-tail { padding-block-end: ${collapsed(0, li.end)}px }`,
  );
  return rules.join("\n");
}

// Each outermost block's lines name its face, and the lines between two blocks the gap
// the display leaves there: the blank lines that part them in the source, or the
// second's first line where none do. Only a field that edits in place has rules for the
// names (`readFaces`). A quote's and an item's insets are their boxes' (`decorate`). An
// item after the first in a list stands its gap above it.
// The display trims the outer margins of its first and last blocks, so the field
// leaves none there, but a list's first and last items keep theirs.
const blockTag = (token) => (token.type === "fence" ? "pre" : token.tag);
function standBlocks(state, blocks, out, line) {
  const lines = (from, to, each) => {
    for (let at = from; at < to;) {
      const current = state.doc.lineAt(at);
      each(current);
      at = current.to + 1;
    }
  };
  const named = (from, cls) => out.push(line(cls).range(from));
  // A run of blank lines stands as one gap, shared among them.
  const gapLines = (from, to, gap) => {
    const runs = state.doc.lineAt(to).number - state.doc.lineAt(from).number;
    const share = runs > 1 ? ` lf-face-share-${Math.min(runs, 3)}` : "";
    lines(from, to, (each) => named(each.from, `lf-face-gap${share} ${gap}`));
  };
  // The block before the one being read in each container still open, by level: the
  // draft itself and each quote. A list's items stand apart by their own gap.
  const before = [];
  const open = [];
  let item = null;
  const blank = (at) => /^[\s>]*$/.test(state.doc.lineAt(at).text);
  for (const { token, from, to } of blocks) {
    if (!token.block) continue;
    const tag = blockTag(token);
    // A heading and a fence wear their faces wherever they stand.
    if (token.type === "heading_open")
      lines(from, to, (each) => named(each.from, `lf-face-${tag}`));
    else if (token.type === "fence")
      lines(from, to, (each) => named(each.from, "lf-face-code"));
    while (open.at(-1)?.to <= from) before.length = open.pop().level + 1;
    const within = open.at(-1)?.type;
    if (token.type === "list_item_open" && within !== "list_item_open") {
      if (item?.to === from) named(from, "lf-face-item");
      item = { to };
    }
    const container = /^(blockquote|bullet_list|ordered_list|list_item)_open$/.test(
      token.type,
    );
    if (container) open.push({ type: token.type, to, level: token.level });
    if (token.type === "list_item_open" || within === "list_item_open") continue;
    const level = token.level;
    if (!FACE_PROBE.includes(`<${tag}>`)) {
      before[level] = null;
      continue;
    }
    const list = tag === "ul" || tag === "ol";
    if (list && from === 0) named(0, "lf-face-list-lead");
    if (list && to >= state.doc.length)
      named(state.doc.lineAt(state.doc.length).from, "lf-face-list-tail");
    const prior = before[level];
    const gap = `lf-ends-${prior?.tag} lf-starts-${tag}`;
    if (prior && prior.to < from) gapLines(prior.to, from, gap);
    else if (prior) named(from, `lf-face-gap-above ${gap}`);
    // A block's reading can take in the blank lines after it, which part it from the next.
    let end = to;
    while (end > from && blank(end - 1)) end = state.doc.lineAt(end - 1).from;
    before[level] = { tag, to: end };
    before.length = level + 1;
    if (token.type === "paragraph_open" && level === 0)
      lines(from, to, (each) => named(each.from, "lf-face-p"));
    else if (token.type === "blockquote_open" && level === 0) {
      named(from, "lf-face-quote-first");
      named(state.doc.lineAt(Math.max(from, end - 1)).from, "lf-face-quote-last");
    }
  }
}

/** @type {Promise<ReturnType<typeof fieldEditor>> | null} */
let loaded = null;
/** The field's editor, CodeMirror loaded under it. The renderer loads beside it, so an
 * editor never stands without the reading its preview and Shift+Enter (`continueBlocks`)
 * take, which made a Shift+Enter pressed as the field opened a plain line. */
export const loadFieldEditor = () =>
  (loaded ??= Promise.all([import("/vendor/codemirror.esm.js"), loadMarkdown()]).then(
    ([codemirror]) => fieldEditor(codemirror, leafEditorView(codemirror)),
  ));

/** What a field's editor needs CodeMirror for, built from the loaded module. */
function fieldEditor(
  {
    EditorView,
    EditorState,
    EditorSelection,
    Prec,
    StateEffect,
    StateField,
    Facet,
    Compartment,
    WidgetType,
    Decoration,
    BlockWrapper,
    ViewPlugin,
    keymap,
    history,
    standardKeymap,
    historyKeymap,
    isolateHistory,
    invertedEffects,
  },
  LeafEditorView,
) {
  const insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;

  // A step an owner recorded in the words' history (`record`): `run` makes it happen when
  // the history reaches it, and `back` is the step the other way.
  const ownerStep = StateEffect.define();

  const hide = Decoration.replace({});
  const dim = Decoration.mark({ class: "lf-md-mark" });
  const link = Decoration.mark({ class: "lf-md-link" });
  const unseen = Decoration.mark({
    class: "lf-md-unseen",
    attributes: { "aria-hidden": "true" },
  });
  // A container's marker in its source, a quote's `>` or an item's bullet or number,
  // unseen or shown, and the run of them that opens a line (`decorate`), which holds the
  // room kept at its end.
  const markerFaces = Object.fromEntries(
    ["quote", "item"].map((kind) => [
      kind,
      [
        Decoration.mark({
          class: `lf-md-marker lf-md-${kind}-marker lf-md-unseen`,
          attributes: { "aria-hidden": "true" },
        }),
        Decoration.mark({ class: `lf-md-marker lf-md-${kind}-marker lf-md-mark` }),
      ],
    ]),
  );
  const markerRun = Decoration.mark({ class: "lf-md-markers", inclusiveEnd: true });
  // The room a container's marker takes in a run, for a container whose marker the line
  // doesn't hold, as a quote's lazy line and an item's later line don't, so the markers
  // before it stand in their own containers' insets.
  class Inset extends WidgetType {
    constructor(kind) {
      super();
      this.kind = kind;
    }
    eq(other) {
      return other.kind === this.kind;
    }
    toDOM() {
      const room = document.createElement("span");
      room.className = `lf-md-marker lf-md-${this.kind}-marker`;
      room.setAttribute("aria-hidden", "true");
      return room;
    }
  }
  const insets = {
    quote: Decoration.widget({ widget: new Inset("quote"), side: -1 }),
    item: Decoration.widget({ widget: new Inset("item"), side: -1 }),
  };
  const line = (cls) => Decoration.line({ class: cls });
  // A quote and a list item are each a box around their lines, as the message's
  // blockquote and li are, so a nested one stands inside its container with the
  // container's rule and inset beside it, and so does a code block in either. An item
  // wears the marker a message's list draws there: the bullet the platform's style sheet
  // nests, or the item's number in its list; one whose source marker shows wears none.
  // A box takes the lines that start in its range, including one starting at its end,
  // so it ends on its last line's break. CodeMirror carries a box on into a later one
  // that equals it, so each names its level, and a container is ranked outside its
  // contents. Rejected: a class on each line (until October 2026), which CodeMirror
  // merges, so every level of a nested quote drew one rule at one inset and a code
  // block's frame replaced its quote's; and boxes for quotes alone, which put a quote's
  // rule outside the item holding it, and the item's bullet inside the quote.
  const BULLETS = ["lf-md-disc", "lf-md-circle", "lf-md-square"];
  const box = (from, to, level, attributes) =>
    BlockWrapper.create({
      tagName: "div",
      attributes: { ...attributes, "data-level": String(level) },
      rank: 100 - level,
    }).range(from, Math.max(from, to - 1));

  // The inline constructs the preview draws, by the renderer's token type: each as the
  // element the renderer sends it as.
  const INLINE = {
    code_inline: Decoration.mark({ tagName: "code" }),
    em_open: Decoration.mark({ tagName: "em" }),
    strong_open: Decoration.mark({ tagName: "strong" }),
    s_open: Decoration.mark({ tagName: "s" }),
  };

  // A picture's syntax, while the caret is away, is the picture the message shows for it,
  // from the source the parser resolved, a reference's included, at the address the
  // renderer gives page media (markdown.js). A press on it puts the caret in its source.
  class Picture extends WidgetType {
    constructor(src, alt) {
      super();
      this.src = isCanonicalMediaUrl(src) ? scopedMediaUrl(src) : src;
      this.alt = alt;
    }
    eq(other) {
      return other.src === this.src && other.alt === this.alt;
    }
    toDOM(view) {
      const img = document.createElement("img");
      img.className = "lf-md-picture";
      img.alt = this.alt;
      img.src = this.src;
      img.addEventListener("load", () => view.requestMeasure(), { once: true });
      return img;
    }
    ignoreEvent() {
      return false;
    }
  }
  // The mark the page draws after a link that leaves it (declared-words.js).
  class ExternalMark extends WidgetType {
    eq() {
      return true;
    }
    toDOM() {
      return externalLinkMark();
    }
  }
  const externalMark = Decoration.widget({ widget: new ExternalMark(), side: -1 });
  // The character an entity names, where the message shows it.
  class Spelled extends WidgetType {
    constructor(shown) {
      super();
      this.shown = shown;
    }
    eq(other) {
      return other.shown === this.shown;
    }
    toDOM() {
      const words = document.createElement("span");
      words.textContent = this.shown;
      return words;
    }
    ignoreEvent() {
      return false;
    }
  }
  // A task item's box, as the message draws it: disabled, so it shows the state the
  // source writes, which only the source changes.
  class TaskBox extends WidgetType {
    constructor(checked) {
      super();
      this.checked = checked;
    }
    eq(other) {
      return other.checked === this.checked;
    }
    toDOM() {
      const box = document.createElement("input");
      box.type = "checkbox";
      box.className = "task-list-item-checkbox";
      box.disabled = true;
      box.checked = this.checked;
      return box;
    }
    ignoreEvent() {
      return false;
    }
  }

  // The draft's decorations, and the boxes its quotes and list items stand in.
  function decorate(state, placed) {
    const out = [];
    const runs = [];
    const boxes = [];
    // The ends of the lists open at the token being read, the lines whose leading
    // spaces the message drops, by the level of the block they lead, the blocks whose
    // lines draw their own leading spaces (code, by its reading, and a rule), the
    // containers' markers, and the containers.
    const lists = [];
    const leads = [];
    const whole = [];
    const opening = [];
    const held = [];
    // Where the markers end that open the line starting at `line` for the containers
    // outside `level`: a block inside them starts on that line no earlier.
    const after = (line, level) =>
      Math.max(
        line,
        ...opening.filter((m) => m.line === line && m.level < level).map((m) => m.to),
      );
    const add = (from, to, deco) => {
      if (from >= to) return;
      // A hidden range may not hold a line break; such syntax stays drawn.
      if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
      out.push(deco.range(from, to));
    };
    const lines = (from, to, each) => {
      for (let at = from; at < to;) {
        const current = state.doc.lineAt(at);
        each(current);
        at = current.to + 1;
      }
    };
    for (const {
      token,
      from,
      to,
      contentFrom,
      contentTo,
      spelled,
      markers,
      words: said,
    } of placed) {
      if (!DRAWN.has(token.type)) continue;
      const syntax = touches(state, from, to) ? dim : hide;
      // Source the message shows as other characters: an escape's backslash and a
      // break's are hidden, and an entity is the character it names.
      for (const [a, b, shown] of spelled ?? []) {
        const touched = touches(state, a, b);
        if (state.doc.sliceString(a, b).endsWith(shown))
          add(a, b - shown.length, touched ? dim : hide);
        else if (touched) add(a, b, dim);
        else out.push(Decoration.replace({ widget: new Spelled(shown) }).range(a, b));
      }
      if (token.type === "code_inline" || contentFrom !== undefined) {
        const words =
          token.type === "code_inline"
            ? [from + token.markup.length, to - token.markup.length]
            : [contentFrom, contentTo];
        if (words[0] > words[1]) continue;
        if (INLINE[token.type]) add(from, to, INLINE[token.type]);
        else if (token.type === "link_open" && token.meta.linked) {
          add(words[0], words[1], link);
          if (opensElsewhere(token.attrGet("href")))
            out.push(externalMark.range(words[1]));
        }
        add(from, words[0], syntax);
        add(words[1], to, syntax);
      } else if (token.type === "image") {
        // A replacement a plugin draws may not take a line break, so a picture whose
        // source spans lines stays source. With the caret in its source the picture
        // stays drawn after it, so reaching the source adds its line and takes no
        // picture away from the page.
        if (said !== "" || state.doc.sliceString(from, to).includes("\n")) continue;
        const widget = new Picture(token.attrGet("src"), token.content);
        out.push(
          touches(state, from, to)
            ? Decoration.widget({ widget, side: 1 }).range(to)
            : Decoration.replace({ widget }).range(from, to),
        );
      } else if (token.type === "html_inline") {
        // A task item's box (markdown.js), drawn in place of its brackets.
        if (touches(state, from, to)) add(from, to, dim);
        else
          out.push(
            Decoration.replace({
              widget: new TaskBox(token.content.includes("checked")),
            }).range(from, to),
          );
      } else if (token.type === "paragraph_open") {
        lines(from, to, (each) => leads.push([each.from, token.level]));
      } else if (token.type === "heading_open") {
        lines(from, to, (each) => {
          out.push(line("lf-md-heading").range(each.from));
          leads.push([each.from, token.level]);
        });
        for (const [a, b] of markers) add(a, b, syntax);
      } else if (token.type === "hr") {
        // A rule is the line the message draws, its source on it, unseen while the
        // caret is away from it, and the spaces leading it hidden, as below.
        const rule = state.doc.lineAt(from);
        whole.push([rule.from, rule.to + 1]);
        out.push(line("lf-md-rule").range(rule.from));
        const start = after(rule.from, token.level);
        const marks =
          start + state.doc.sliceString(start, rule.to).match(/^[ \t]*/)[0].length;
        add(start, marks, hide);
        add(marks, rule.to, touches(state, rule.from, rule.to) ? dim : unseen);
      } else if (token.type === "fence") {
        whole.push([from, to]);
        // Each line of code keeps the indent the parser's reading of it keeps; the rest,
        // a list item's indent after its containers' markers, the message drops. The code's reading ends each line it holds with a
        // break, except a last line the draft's end ends, and holds none for a fence
        // with no code. An end no fence line stands for takes the padding on the
        // code's own line.
        const body = token.content.split("\n");
        if (body.at(-1) === "") body.pop();
        const opened = state.doc.lineAt(from).number + 1;
        lines(from, to, (each) => {
          const first = each.from <= from;
          const last = each.to + 1 >= to;
          const ends = [
            first ? " lf-md-code-first" : "",
            last ? " lf-md-code-last" : "",
            last && markers.length < 2 ? " lf-md-code-pad-end" : "",
          ].join("");
          out.push(line(`lf-md-code-block${ends}`).range(each.from));
          const kept = body[each.number - opened];
          if (kept === undefined) return;
          const start = after(each.from, token.level);
          const lead = state.doc.sliceString(start, each.to).match(/^[ \t]*/)[0].length;
          add(start, start + lead - kept.match(/^[ \t]*/)[0].length, hide);
        });
        // A fence's lines stand for the message's code padding, and each shows its
        // marks while the caret is on it.
        for (const [a, b] of markers ?? []) {
          const fence = state.doc.lineAt(a);
          add(a, b, touches(state, fence.from, fence.to) ? dim : unseen);
        }
      } else if (token.type === "blockquote_open") {
        boxes.push(box(from, to, token.level, { class: "lf-md-quote lf-face-quote" }));
        held.push({ from, to, level: token.level, kind: "quote" });
        for (const [a, b] of markers) {
          const line = state.doc.lineAt(a).from;
          opening.push({ from: a, to: b, kind: "quote", level: token.level, line });
          leads.push([line, token.level]);
        }
      } else if (
        token.type === "bullet_list_open" ||
        token.type === "ordered_list_open"
      ) {
        while (lists.at(-1)?.to <= from) lists.pop();
        const ordered = token.type === "ordered_list_open";
        lists.push({ to, next: ordered ? Number(token.attrGet("start") ?? 1) : null });
      } else if (token.type === "list_item_open") {
        while (lists.at(-1)?.to <= from) lists.pop();
        const list = lists.at(-1);
        const depth = lists.length;
        // An item's later lines stand under its words, their indent hidden as the
        // message drops it, and never revealed, so the words don't jump as the caret
        // arrives: a paragraph's whole indent, and in code what the code's reading drops
        // (above). A nested item, read after its parent, takes its own lines.
        const head = state.doc.lineAt(from);
        const [at, end] = markers[0];
        // The marker's own indent stands in the inset with it, after the markers of the
        // containers that open the line before it.
        const start = Math.max(
          at - head.text.slice(0, at - head.from).match(/[ \t]*$/)[0].length,
          after(head.from, token.level),
        );
        lines(head.to + 1, to, (each) => leads.push([each.from, token.level]));
        const kind =
          list.next === null
            ? BULLETS[Math.min(depth, BULLETS.length) - 1]
            : "lf-md-number";
        const shown = state.selection.ranges.some(
          (range) => range.from < end && range.to >= start,
        );
        boxes.push(
          box(
            head.from,
            to,
            token.level,
            shown
              ? { class: "lf-md-item" }
              : {
                  class: `lf-md-item lf-md-listed ${kind}`,
                  ...(list.next !== null && {
                    style: `counter-set: list-item ${list.next}`,
                  }),
                },
          ),
        );
        if (list.next !== null) list.next++;
        held.push({ from: head.from, to, level: token.level, kind: "item" });
        opening.push({
          from: start,
          to: end,
          kind: "item",
          shown,
          level: token.level,
          line: head.from,
        });
      }
    }
    // The spaces that lead a line, after its containers' markers, the message drops: an
    // item's indent on its later lines, and the spaces before a paragraph's or a
    // heading's words or a quote's marker. They stay hidden, never revealed, so the
    // words don't jump as the caret arrives or leaves. A nested item's own line keeps
    // its indent in its marker.
    const indents = new Set();
    for (const [from, level] of leads) {
      if (whole.some(([a, b]) => from >= a && from < b)) continue;
      const start = after(from, level);
      if (indents.has(start)) continue;
      if (opening.some((m) => m.kind === "item" && m.line === from && m.from === start))
        continue;
      indents.add(start);
      const { to } = state.doc.lineAt(from);
      add(
        start,
        start + state.doc.sliceString(start, to).match(/^[ \t]*/)[0].length,
        hide,
      );
    }
    // The markers that open a line stand, in order, in the insets of the containers they
    // open, right to left from the line's words, unseen while the caret is away, so
    // revealing one moves no word. A container the line stands in without a marker, as
    // a quote's lazy line and an item's later line do, keeps its inset after the markers
    // of the containers outside it.
    opening.sort((a, b) => a.from - b.from);
    for (let i = 0; i < opening.length;) {
      let j = i + 1;
      while (j < opening.length && opening[j].from === opening[j - 1].to) j++;
      const run = opening.slice(i, j);
      runs.push(markerRun.range(run[0].from, run.at(-1).to));
      for (const { from, to, kind, shown } of run)
        out.push(
          markerFaces[kind][+(shown ?? touches(state, from, to))].range(from, to),
        );
      const { line } = run[0];
      for (const container of held
        .filter(
          (c) =>
            c.from <= line &&
            line < c.to &&
            !opening.some((m) => m.line === line && m.level === c.level),
        )
        .sort((a, b) => a.level - b.level)) {
        const outside = run.filter((m) => m.level < container.level);
        if (outside.length) out.push(insets[container.kind].range(outside.at(-1).to));
      }
      i = j;
    }
    standBlocks(state, placed, out, line);
    return {
      decorations: Decoration.set(out, true),
      runs: Decoration.set(runs),
      boxes: BlockWrapper.set(boxes, true),
    };
  }

  // Up and Down step to the next line, however short the preview draws it. CodeMirror's
  // vertical motion aims half a line of text past the caret's line, so it passes over a
  // line shorter than that, as a blank line is where several share the gap a field
  // that edits in place stands between two blocks (`standBlocks`). Where its step
  // passes over the line beside the caret's, the caret goes to that line instead, at
  // the goal column CodeMirror aimed for, found in its own map of line heights.
  // Without Shift, a selection collapses to its end that way, as CodeMirror's own step
  // does.
  const lineStep = (forward, extend) => (view) => {
    const { selection, doc } = view.state;
    const moved = EditorSelection.create(
      selection.ranges.map((range) => {
        if (!extend && !range.empty)
          return EditorSelection.cursor(forward ? range.to : range.from);
        let step = view.moveVertically(range, forward);
        const here = view.lineBlockAt(range.head);
        const at = forward ? here.to + 1 : here.from - 1;
        const beside = at >= 0 && at <= doc.length ? view.lineBlockAt(at) : null;
        const passed = (block) => step.head < block.from || step.head > block.to;
        if (beside && passed(here) && passed(beside)) {
          const head = view.posAtCoords(
            {
              x: view.contentDOM.getBoundingClientRect().left + step.goalColumn,
              y: view.documentTop + beside.top + beside.height / 2,
            },
            false,
          );
          step = EditorSelection.cursor(head, 0, undefined, step.goalColumn);
        }
        return extend
          ? EditorSelection.range(range.anchor, step.head, step.goalColumn)
          : step;
      }),
      selection.mainIndex,
    );
    if (moved.eq(selection)) return false;
    view.dispatch({ selection: moved, scrollIntoView: true, userEvent: "select" });
    return true;
  };
  const LINE_STEPS = [
    { key: "ArrowUp", run: lineStep(false, false), shift: lineStep(false, true) },
    { key: "ArrowDown", run: lineStep(true, false), shift: lineStep(true, true) },
  ];

  // The draft as the renderer that will send it reads it (`read`), taken again when the
  // words change or the renderer arrives. The preview, Shift+Enter and the joints below
  // read it from the state, where CodeMirror takes a replacement across a line break.
  const reading = StateField.define({
    create: (state) => ({ placed: read(state), judged: markdownReady() }),
    update(value, tr) {
      const judged = markdownReady();
      return tr.docChanged || judged !== value.judged
        ? { placed: read(tr.state), judged }
        : value;
    },
  });

  const CONTAINERS = new Set(["blockquote_open", ITEM]);
  const item = (c) => c?.token.type === ITEM;
  // Whether a quote or list item, as the renderer reads it, holds a line (`itemEnd`).
  const holding = (placed, line) => (c) =>
    c.from <= line.from && line.from < (item(c) ? itemEnd(placed, c) : c.to);
  const markerOn = (c, l) => c.markers.find(([a]) => a >= l.from && a <= l.to);
  // Where the markers that open a line end.
  const opened = (l, among) =>
    Math.max(l.from, ...among.map((c) => markerOn(c, l)?.[1] ?? l.from));
  // A line a container holds without its marker carries the quote's `>`, or the item's
  // indent.
  const carried = ({ token }) =>
    token.type === "blockquote_open" ? "> " : " ".repeat(token.meta.indent);

  // A field that edits a Markdown body in place (`field.joined()`; text-field.js,
  // `facesOf`) reads its words as the body does, as a file (markdown.js,
  // `paintMarkdown`), where a line break among a paragraph's words, in a code span or a
  // link's destination as anywhere else, is a space, and only a hard break's is a line.
  // Each such break, with the spaces ending its line and the next line's markers and
  // indent, stands as one space the caret steps over, and deleting it joins the words, so
  // a paragraph wrapped for a wider editor wraps to the field as it does in the body. It
  // is never revealed, since revealing it would rewrap the paragraph under the caret.
  const joinsLines = Facet.define({ combine: (values) => values.some(Boolean) });
  const joint = Decoration.replace({ widget: new Spelled(" ") });
  const jointsOf = (state) => {
    if (!state.facet(joinsLines)) return Decoration.none;
    const { placed } = state.field(reading);
    const inline = placed.filter(({ token }) => !token.block);
    const hard = inline.filter(({ token }) => token.type === "hardbreak");
    const containers = placed.filter(({ token }) => CONTAINERS.has(token.type));
    const breaks = new Set();
    for (const { from, to } of inline) {
      const text = state.sliceDoc(from, to);
      for (let at = text.indexOf("\n"); at >= 0; at = text.indexOf("\n", at + 1))
        breaks.add(from + at);
    }
    const out = [];
    for (const at of [...breaks].sort((a, b) => a - b)) {
      if (hard.some(({ from, to }) => from <= at && at < to)) continue;
      const line = state.doc.lineAt(at);
      const next = state.doc.line(line.number + 1);
      const words = opened(next, containers);
      out.push(
        joint.range(
          at - line.text.match(/[ \t]*$/)[0].length,
          words + state.sliceDoc(words, next.to).match(/^[ \t]*/)[0].length,
        ),
      );
    }
    return Decoration.set(out);
  };
  const joints = StateField.define({
    create: jointsOf,
    update: (set, tr) =>
      tr.state.field(reading) === tr.startState.field(reading) &&
      tr.state.facet(joinsLines) === tr.startState.facet(joinsLines)
        ? set
        : jointsOf(tr.state),
    provide: (field) => [
      EditorView.decorations.from(field),
      EditorView.atomicRanges.of((view) => view.state.field(field)),
    ],
  });

  // Return in a field that joins lines begins a line the body shows too, carrying the
  // markers of the containers the caret's line stands in. Among a paragraph's words it
  // writes a hard break, whose backslash the preview hides, in place of the spaces, and
  // any joint, the selection touches. After a paragraph's last words, where a hard break
  // would end its block and show its backslash, it begins a new paragraph, and in a list
  // item the next item (`continueBlocks`). With none of a paragraph's words before the
  // caret, in a container it continues the container as Shift+Enter does, leaving it on a
  // bare line, and elsewhere, as after a heading, it is a plain line. Shift+Enter does
  // the same here, since a line it continued in a container would join the paragraph
  // above.
  function newLine(view) {
    const { state } = view;
    if (!state.facet(joinsLines)) return insertNewline(view);
    const { from, to } = state.selection.main;
    const { placed } = state.field(reading);
    const paragraph = placed.find(
      ({ token, from: a, to: b }) =>
        token.type === "paragraph_open" && a <= from && to <= b,
    );
    const words = paragraph
      ? placed.filter(
          ({ token, from: a, to: b }) =>
            !token.block &&
            token.type !== "softbreak" &&
            a >= paragraph.from &&
            b <= paragraph.to,
        )
      : [];
    const before = words.some(({ from: a }) => a < from);
    const after = words.some(({ to: b }) => b > to);
    const line = state.doc.lineAt(from);
    const holds = holding(placed, line);
    const containers = placed.filter((c) => CONTAINERS.has(c.token.type) && holds(c));
    const inner = containers.at(-1);
    if (inner && (!before || (!after && item(inner))) && continueBlocks(view, true))
      return true;
    if (!before) return insertNewline(view);
    const prefix = containers.map(carried).join("");
    let spec;
    if (after) {
      let [a, b] = [from, to];
      a -= state
        .sliceDoc(Math.min(a, opened(line, containers)), a)
        .match(/[ \t]*$/)[0].length;
      b += state.sliceDoc(b, state.doc.lineAt(b).to).match(/^[ \t]*/)[0].length;
      state.field(joints).between(a, b, (jointFrom, jointTo) => {
        a = Math.min(a, jointFrom);
        b = Math.max(b, jointTo);
      });
      const insert = `\\\n${prefix}`;
      spec = {
        changes: { from: a, to: b, insert },
        selection: { anchor: a + insert.length },
      };
    } else spec = state.replaceSelection(`\n${prefix.trimEnd()}\n${prefix}`);
    view.dispatch(state.update(spec, { scrollIntoView: true, userEvent: "input" }));
    return true;
  }

  // The draft is read by the renderer that will send it, so the preview styles exactly what
  // the message will: the same constructs, the same links. The styling is taken again when
  // the reading changes and when the selection moves. The renderer loads lazily; until it
  // has, the words stand plain, and its arrival draws every open field.
  const livePreview = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.live = true;
        this.read = view.state.field(reading);
        this.drawn = decorate(view.state, this.read.placed);
        if (!this.read.judged)
          loadMarkdown().then(
            () => this.live && view.dispatch({}),
            () => {},
          );
      }
      destroy() {
        this.live = false;
      }
      update(update) {
        const read = update.state.field(reading);
        if (read === this.read && !update.selectionSet) return;
        this.read = read;
        this.drawn = decorate(update.state, read.placed);
      }
    },
    {
      decorations: (plugin) => plugin.drawn.decorations,
      // A run of markers holds its markers, even one with the same range. A tab is as
      // wide as the message draws it, the platform's eight columns.
      provide: (plugin) => [
        EditorView.outerDecorations.of(
          (view) => view.plugin(plugin)?.drawn.runs ?? Decoration.none,
        ),
        EditorView.blockWrappers.of(
          (view) => view.plugin(plugin)?.drawn.boxes ?? BlockWrapper.set([]),
        ),
        EditorState.tabSize.of(8),
        Prec.high(keymap.of(LINE_STEPS)),
      ],
    },
  );

  // Shift+Enter in a quote or a list item begins a line in each container the caret's
  // line stands in, as the preview reads the draft (`livePreview`), which is how the
  // message will read it, a fence's code included: each quote's `>`, each item's indent,
  // and on the line holding the innermost item's marker, or on any of its lines where
  // `nextItem` asks (`newLine`), the next item's marker. Pressed
  // on a line holding nothing past its markers, outside code, it leaves the innermost
  // container. An item directly in another item outdents, as rich editors do: its line
  // becomes the next item of the list outside. Otherwise the line keeps what it holds
  // for the containers outside and becomes the blank line that parts the two blocks, or
  // the line above does where it is already bare, and the caret takes a new line in
  // them. A task's next item is an open task, and an item holding only that checkbox is
  // empty. With the caret among the markers, in no container, or on a line it would
  // leave as it stands, the press is a plain new line. The numbers of the items after a
  // new one stay as typed, since the message numbers a list from its first. Rejected:
  // CodeMirror's Markdown continuation (until October 2026), whose grammar, a second
  // beside the renderer's, read the whole draft again on every key, ended a quote or
  // item at a fence inside it, and took three presses to leave a list.
  const CHECKBOX = "[ ] ";
  function continueBlocks(view, nextItem = false) {
    const { state } = view;
    const { placed } = state.field(reading);
    const { from, to } = state.selection.main;
    const line = state.doc.lineAt(from);
    const all = placed.filter(({ token }) => CONTAINERS.has(token.type));
    const holds = holding(placed, line);
    const containers = all.filter(holds);
    if (!containers.length) return false;
    const code = placed.some((c) => c.token.type === "fence" && holds(c));
    // A line holding nothing past its markers is bare.
    const bare = (l) => {
      const rest = state.sliceDoc(opened(l, all), l.to).trim();
      return !rest || `${rest} ` === CHECKBOX;
    };
    if (from < opened(line, containers)) return false;
    const task = ({ token }) =>
      token.attrGet("class")?.split(" ").includes("task-list-item");
    const next = (c) =>
      `${c.token.info && Number(c.token.info) + 1}${c.token.markup} ${task(c) ? CHECKBOX : ""}`;
    const inner = containers.at(-1);
    const outside = containers.slice(0, -1);
    let change;
    if (!code && to <= line.to && bare(line)) {
      const parent = outside.at(-1);
      const outdent = item(inner) && item(parent);
      const around = outdent ? outside.slice(0, -1) : outside;
      // What a line keeps of its markers for the containers it stays in.
      const kept = (l) => {
        let text = "";
        for (const c of around) {
          const own = markerOn(c, l);
          text = own ? state.sliceDoc(l.from, own[1]) : text + carried(c);
        }
        return text;
      };
      const above = line.number > 1 && state.doc.line(line.number - 1);
      change = outdent
        ? { from: line.from, to: line.to, insert: kept(line) + next(parent) }
        : above && bare(above)
          ? {
              from: above.from,
              to: line.to,
              insert: `${kept(above).trimEnd()}\n${kept(line)}`,
            }
          : {
              from: line.from,
              to: line.to,
              insert: `${kept(line).trimEnd()}\n${around.map(carried).join("")}`,
            };
    } else {
      const marker =
        item(inner) && (nextItem || inner.from === line.from) && !code
          ? next(inner)
          : carried(inner);
      const insert = `\n${outside.map(carried).join("")}${marker}`;
      change = { from, to, insert };
    }
    if (state.sliceDoc(change.from, change.to) === change.insert) return false;
    view.dispatch(
      state.update({
        changes: change,
        selection: { anchor: change.from + change.insert.length },
        scrollIntoView: true,
        userEvent: "input",
      }),
    );
    return true;
  }

  const nest = (deeper) => (view) => {
    const { state } = view;
    if (state.readOnly) return false;
    const { from, to } = state.selection.main;
    const { placed } = state.field(reading);
    const changes = nestItems(state.doc.toString(), placed, from, to, deeper);
    if (!changes?.length) return Boolean(changes) && deeper;
    view.dispatch(
      state.update({
        changes,
        scrollIntoView: true,
        userEvent: deeper ? "indent.more" : "indent.less",
        // One press is one step of undo, never joined to the typing around it.
        annotations: isolateHistory.of("full"),
      }),
    );
    return true;
  };

  const editable = new Compartment();
  const histories = new Compartment();
  const attributes = new Compartment();

  /** The state a field's editor starts from: `words`, the field's draft, under the
   * field's configuration. The draft's history starts from its `base`; its `text`,
   * where the user changed it before the editor built, is one step after that, so
   * undo takes it back, followed by the `steps` an owner recorded. `anchor` and
   * `head` are its selection. `field.typed(native, insert)` runs text input the editor
   * takes, saying whether the DOM has already changed, `field.returned()` says
   * whether Return may insert a line, `field.oneLine()` whether the field holds one
   * line, `field.joined()` whether it joins a paragraph's lines (`joints`),
   * `field.revealed(view, pos)` shows the row holding `pos` in the field's
   * host, and `field.focused()` hears the editor take or lose focus. */
  function fieldState(words, field) {
    // The run of words that differs between `base` and `text`: where the user typed.
    const { base, text } = words;
    let from = 0;
    while (from < Math.min(base.length, text.length) && base[from] === text[from])
      from++;
    let kept = 0;
    while (
      kept < Math.min(base.length, text.length) - from &&
      base[base.length - 1 - kept] === text[text.length - 1 - kept]
    )
      kept++;
    let state = EditorState.create({
      doc: base,
      // Taking the typing back leaves the caret where it went in.
      selection: { anchor: from },
      extensions: [
        // DOM input has already changed the words when CodeMirror reads it, so its
        // bracket started at beforeinput. EditContext leaves rendering to the editor;
        // its transactions, like commands, still start before the DOM changes.
        EditorView.inputHandler.of((view, _from, _to, _text, insert) => {
          field.typed(!view.contentDOM.editContext, () => view.dispatch(insert()));
          return true;
        }),
        // Words typed over a selection replace it here, not in the DOM: in a shadow
        // root, Firefox inserts them beside a selection that crosses a decoration's
        // element and leaves the selected words in place (Firefox 157, CodeMirror
        // 6.43). The beforeinput already opened the edit's bracket.
        EditorView.domEventHandlers({
          beforeinput(event, view) {
            if (
              event.inputType !== "insertText" ||
              event.data === null ||
              view.state.selection.main.empty ||
              view.state.readOnly ||
              view.composing
            )
              return false;
            event.preventDefault();
            field.typed(true, () =>
              view.dispatch(
                view.state.update(view.state.replaceSelection(event.data), {
                  scrollIntoView: true,
                  userEvent: "input.type",
                }),
              ),
            );
            return true;
          },
        }),
        // An edit's reveal shows the caret's row in the host first; the view's own
        // reveal (editor-view.js) then carries the caret out through the page.
        EditorView.scrollHandler.of((view, range) => {
          field.revealed(view, range.head);
          return false;
        }),
        EditorView.updateListener.of((update) => {
          if (update.focusChanged) field.focused();
        }),
        histories.of(history()),
        // A one-line field holds one line, so a line break pasted or inserted by the
        // platform, as Android's editing does, becomes a space.
        EditorState.transactionFilter.of((tr) => {
          if (!tr.docChanged || !field.oneLine()) return tr;
          const breaks = [];
          tr.changes.iterChanges((_fromA, _toA, fromB, _toB, inserted) => {
            const text = inserted.toString();
            for (
              let at = text.indexOf("\n");
              at !== -1;
              at = text.indexOf("\n", at + 1)
            )
              breaks.push({ from: fromB + at, to: fromB + at + 1, insert: " " });
          });
          return breaks.length ? [tr, { changes: breaks, sequential: true }] : tr;
        }),
        invertedEffects.of((tr) =>
          tr.effects
            .filter((effect) => effect.is(ownerStep))
            .map(({ value }) => ownerStep.of({ run: value.back, back: value.run })),
        ),
        keymap.of([
          // A one-line field takes no line break (`field.oneLine`).
          { key: "Shift-Enter", run: () => field.oneLine() },
          { key: "Enter", run: (view) => field.returned() && newLine(view) },
          {
            key: "Shift-Enter",
            run: (view) => view.state.facet(joinsLines) && newLine(view),
          },
          { key: "Shift-Enter", run: (view) => continueBlocks(view) },
          // Tab in a list item nests it (`nestItems`), and stays in the field where
          // the item has nowhere to nest; Shift+Tab takes items out, and where none
          // can go moves focus back, so a draft that is all list still lets focus
          // out. Elsewhere both reach the page, which moves focus as from any field.
          {
            key: "Tab",
            run: nest(true),
            shift: nest(false),
            stopPropagation: true,
          },
          // Outside a list or quote, a plain new line, which asks to be seen as typing
          // does, so a field at its height limit scrolls to it.
          {
            key: "Shift-Enter",
            run: (view) => (
              view.dispatch(
                view.state.update(view.state.replaceSelection("\n"), {
                  scrollIntoView: true,
                  userEvent: "input",
                }),
              ),
              true
            ),
          },
          ...standardKeymap.filter(
            ({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter",
          ),
          ...historyKeymap,
        ]),
        reading,
        joinsLines.of(field.joined()),
        joints,
        livePreview,
        EditorView.lineWrapping,
        editable.of(EditorState.readOnly.of(field.readOnly)),
        attributes.of(EditorView.contentAttributes.of(field.attributes)),
      ],
    });
    state = state.update({
      ...(text !== base && {
        changes: {
          from,
          to: base.length - kept,
          insert: text.slice(from, text.length - kept),
        },
        annotations: isolateHistory.of("full"),
        userEvent: "input.type",
      }),
      selection: { anchor: words.anchor, head: words.head },
    }).state;
    for (const [undo, redo] of words.steps)
      state = state.update(record(undo, redo)).state;
    return state;
  }

  const readOnly = (on) => ({
    effects: editable.reconfigure(EditorState.readOnly.of(on)),
  });
  const contentAttributes = (wanted) => ({
    effects: attributes.reconfigure(EditorView.contentAttributes.of(wanted)),
  });
  // A step in the history that changes no words, standing alone: taking it back calls
  // `undo`, redoing it calls `redo`.
  const record = (undo, redo) => ({
    effects: ownerStep.of({ run: redo, back: undo }),
    annotations: isolateHistory.of("full"),
  });
  // Dropping the history's field and adding it back starts it empty, in two successive
  // transactions.
  const forgetHistory = { effects: histories.reconfigure([]) };
  const startHistory = () => ({ effects: histories.reconfigure(history()) });

  /** Run the owner's steps an undo or redo reached. */
  function runOwnerSteps(transactions) {
    for (const tr of transactions)
      if (tr.isUserEvent("undo") || tr.isUserEvent("redo"))
        for (const effect of tr.effects) if (effect.is(ownerStep)) effect.value.run();
  }

  return {
    LeafEditorView,
    fieldState,
    readOnly,
    contentAttributes,
    record,
    forgetHistory,
    startHistory,
    runOwnerSteps,
  };
}
