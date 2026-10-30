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
import { leafEditorView } from "../editor-view.js";
import { loadMarkdown, markdownReady, placedMarkdownTokens } from "../markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "../media.js";

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. A last line holding nothing past its
// quotes' `>` is where the next words will be typed, so it is read holding a word, and
// stands in whichever block those words will join, as a line of an open fence's code, or
// of a quote or list item they continue lazily, and not in a list the line only trails;
// a block that takes it ends past the draft. Nothing is placed in the word itself. Empty
// until the renderer has loaded.
const read = (state) => {
  const source = state.doc.toString();
  if (!/^[\s>]*$/.test(state.doc.line(state.doc.lines).text))
    return placedMarkdownTokens(source);
  return placedMarkdownTokens(`${source}x`).filter(
    ({ token, to }) => token.block || to <= source.length,
  );
};

// The elements the renderer sends each block as, in an order that stands each one
// between others, as a block inside a body stands.
const FACE_PROBE =
  "<div></div><p></p><h1></h1><h2></h2><h3></h3><h4></h4><h5></h5><h6></h6><pre></pre>" +
  "<blockquote></blockquote><ul><li></li><li></li></ul><ol></ol><div></div>";
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
    `.lf-face-fence-open { line-height: ${pre.padStart}px }`,
    `.lf-face-fence-close { line-height: ${pre.padEnd}px }`,
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
// second's first line where none do. A field that edits in place has rules for the
// names (`readFaces`); elsewhere only a fence's do. A quote's and an item's insets are
// their boxes' (`decorate`). A code fence's lines stand for its block's padding while
// the caret is away, and an item after the first in a list stands its gap above it.
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
  const lineTouched = (at) => {
    const { from, to } = state.doc.lineAt(at);
    return touches(state, from, to);
  };
  // The block before the one being read in each container still open, by level: the
  // draft itself and each quote. A list's items stand apart by their own gap.
  const before = [];
  const open = [];
  let item = null;
  const blank = (at) => /^[\s>]*$/.test(state.doc.lineAt(at).text);
  for (const { token, from, to, markers } of blocks) {
    if (!token.block) continue;
    const tag = blockTag(token);
    // A heading and a fence wear their faces wherever they stand.
    if (token.type === "heading_open") {
      lines(from, to, (each) => named(each.from, `lf-face-${tag}`));
    } else if (token.type === "fence") {
      lines(from, to, (each) => named(each.from, "lf-face-code"));
      const opener = state.doc.lineAt(from).number;
      for (const [at] of markers) {
        const fence = state.doc.lineAt(at);
        if (lineTouched(at)) continue;
        const side = fence.number === opener ? "open" : "close";
        named(fence.from, `lf-face-fence-${side}`);
      }
    }
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
    StateEffect,
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
  // The mark the page draws after a link that leaves it (prepaint.js).
  class ExternalMark extends WidgetType {
    eq() {
      return true;
    }
    toDOM() {
      return document.documentElement.lfExternalLink.mark();
    }
  }
  const externalMark = Decoration.widget({ widget: new ExternalMark(), side: -1 });
  const opensElsewhere = (href) =>
    document.documentElement.lfExternalLink?.opensElsewhere(href) ?? false;

  // The draft's decorations, and the boxes its quotes and list items stand in.
  function decorate(state, placed) {
    const out = [];
    const runs = [];
    const boxes = [];
    // The ends of the lists open at the token being read, an item's later lines by its
    // level, the code blocks, whose lines their own reading indents, the containers'
    // markers, and the containers.
    const lists = [];
    const continued = [];
    const code = [];
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
      escapes,
      markers,
      words: said,
    } of placed) {
      const syntax = touches(state, from, to) ? dim : hide;
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
      } else if (token.type === "text") {
        for (const at of escapes ?? [])
          add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
      } else if (token.type === "heading_open") {
        lines(from, to, (each) => {
          out.push(line("lf-md-heading").range(each.from));
        });
        for (const [a, b] of markers) add(a, b, syntax);
      } else if (token.type === "fence") {
        code.push([from, to]);
        // Each line of code keeps the indent the parser's reading of it keeps; the rest,
        // a list item's indent after its containers' markers, the message drops. The code's reading ends each line it holds with a
        // break, except a last line the draft's end ends, and holds none for a fence
        // with no code. An end no fence line stands for (`standBlocks`) takes the
        // padding on the code's own line.
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
        // A fence's lines stand for the message's code padding (`standBlocks`), and each
        // shows its marks, at a line's height, while the caret is on it.
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
        lines(head.to + 1, to, (each) => continued.push([each.from, token.level]));
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
    // Each item's indent on its later lines stands after its containers' markers there;
    // a nested item's own line keeps its indent in its marker.
    const indents = new Set();
    for (const [from, level] of continued) {
      if (code.some(([a, b]) => from >= a && from < b)) continue;
      if (opening.some((m) => m.kind === "item" && m.line === from)) continue;
      const start = after(from, level);
      if (indents.has(start)) continue;
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

  // The draft is read by the renderer that will send it, so the preview styles exactly what
  // the message will: the same constructs, the same links. The reading is taken again when
  // the words change and the styling when the selection moves. The renderer loads lazily;
  // until it has, the words stand plain, and its arrival draws every open field.
  const livePreview = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.live = true;
        this.placed = read(view.state);
        this.drawn = decorate(view.state, this.placed);
        this.judged = markdownReady();
        if (!this.judged)
          loadMarkdown().then(
            () => this.live && view.dispatch({}),
            () => {},
          );
      }
      destroy() {
        this.live = false;
      }
      update(update) {
        const judged = markdownReady();
        if (update.docChanged || judged !== this.judged) {
          this.judged = judged;
          this.placed = read(update.state);
        } else if (!update.selectionSet) return;
        this.drawn = decorate(update.state, this.placed);
      }
    },
    {
      decorations: (plugin) => plugin.drawn.decorations,
      // A run of markers holds its markers, even one with the same range.
      provide: (plugin) => [
        EditorView.outerDecorations.of(
          (view) => view.plugin(plugin)?.drawn.runs ?? Decoration.none,
        ),
        EditorView.blockWrappers.of(
          (view) => view.plugin(plugin)?.drawn.boxes ?? BlockWrapper.set([]),
        ),
      ],
    },
  );

  // Shift+Enter in a quote or a list item begins a line in each container the caret's
  // line stands in, as the preview reads the draft (`livePreview`), which is how the
  // message will read it, a fence's code included: each quote's `>`, each item's indent,
  // and on the line holding the innermost item's marker, the next item's marker. Pressed
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
  const CONTAINERS = new Set(["blockquote_open", "list_item_open"]);
  const CHECKBOX = "[ ] ";
  function continueBlocks(view) {
    const { state } = view;
    const placed = view.plugin(livePreview)?.placed ?? [];
    const { from, to } = state.selection.main;
    const line = state.doc.lineAt(from);
    const all = placed.filter(({ token }) => CONTAINERS.has(token.type));
    // An item's reading takes in the blank lines after its blocks, but words typed on
    // one stand outside it: it ends with its last block, or its last item's marker line.
    const blocks = placed.filter(
      ({ token }) => token.block && !token.type.endsWith("list_open"),
    );
    const end = (c) =>
      c.token.type === "list_item_open"
        ? Math.max(
            ...blocks
              .filter((b) => b.from >= c.from && b.to <= c.to)
              .map((b) => (b.token.type === "list_item_open" ? b.from + 1 : b.to)),
          )
        : c.to;
    const holding = (c) => c.from <= line.from && line.from < end(c);
    const containers = all.filter(holding);
    if (!containers.length) return false;
    const code = placed.some((c) => c.token.type === "fence" && holding(c));
    const markerOn = (c, l) => c.markers.find(([a]) => a >= l.from && a <= l.to);
    // Where the markers that open a line end: a line holding nothing past them is bare.
    const opened = (l, among) =>
      Math.max(l.from, ...among.map((c) => markerOn(c, l)?.[1] ?? l.from));
    const bare = (l) => {
      const rest = state.sliceDoc(opened(l, all), l.to).trim();
      return !rest || `${rest} ` === CHECKBOX;
    };
    if (from < opened(line, containers)) return false;
    // A line a container holds without its marker carries the quote's `>`, or the
    // item's indent.
    const carried = ({ token }) =>
      token.type === "blockquote_open" ? "> " : " ".repeat(token.meta.indent);
    const item = (c) => c?.token.type === "list_item_open";
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
        item(inner) && inner.from === line.from && !code ? next(inner) : carried(inner);
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
   * line, and `field.revealed(view, pos)` shows the row holding `pos` in the field's
   * host. */
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
          { key: "Enter", run: (view) => field.returned() && insertNewline(view) },
          { key: "Shift-Enter", run: continueBlocks },
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
