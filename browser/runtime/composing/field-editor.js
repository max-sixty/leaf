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
import {
  loadMarkdown,
  markdownReady,
  placedMarkdownTokens,
  isBlockPlacement,
} from "../markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "../media.js";

/** @typedef {import("@codemirror/state").EditorState} EditorState
 * @typedef {import("@codemirror/view").EditorView} EditorView
 * @typedef {import("@codemirror/view").Decoration} Decoration
 * @typedef {ReturnType<typeof placedMarkdownTokens>} PlacedTokens
 * @typedef {{type: string, start: number, end: number, padStart: number, padEnd: number, inset: string, indent: string}} BlockFace
 * @typedef {{base: string, text: string, anchor: number, head: number, steps: readonly (readonly [() => void, () => void])[]}} FieldWords
 * @typedef {{typed: (native: boolean, insert: () => void) => void, returned: () => boolean,
 * oneLine: () => boolean, revealed: (view: EditorView, pos: number) => void,
 * focused: () => void, readOnly: boolean, attributes: Record<string, string>}} FieldConfiguration
 */

/** @param {string} text */
const indentation = (text) => text.length - text.replace(/^[ \t]*/, "").length;

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
/** @param {EditorState} state @param {number} from @param {number} to */
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. Empty until the renderer has loaded.
/** @param {EditorState} state */
const read = (state) => {
  return placedMarkdownTokens(state.doc.toString());
};

// The elements the renderer sends each block as, in an order that stands each one
// between others, as a block inside a body stands.
const FACE_ELEMENTS = {
  p: () => document.createElement("p"),
  h1: () => document.createElement("h1"),
  h2: () => document.createElement("h2"),
  h3: () => document.createElement("h3"),
  h4: () => document.createElement("h4"),
  h5: () => document.createElement("h5"),
  h6: () => document.createElement("h6"),
  pre: () => document.createElement("pre"),
  blockquote: () => document.createElement("blockquote"),
  ul: () => document.createElement("ul"),
  ol: () => document.createElement("ol"),
  li: () => document.createElement("li"),
};
// The gap two blocks' margins leave between them, collapsed as the platform collapses
// adjoining margins, in px or as CSS over the two a gap line names (`standBlocks`).
/** @param {number} a @param {number} b */
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
/** @param {HTMLElement} field @param {HTMLElement} display */
export function readFaces(field, display) {
  const probe = display.cloneNode(false);
  probe.removeAttribute("id");
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText =
    "position: absolute; visibility: hidden; inline-size: 0; display: block";
  const preNode = FACE_ELEMENTS.pre();
  const quoteNode = FACE_ELEMENTS.blockquote();
  const liNode = FACE_ELEMENTS.li();
  const ulNode = FACE_ELEMENTS.ul();
  ulNode.append(FACE_ELEMENTS.li(), liNode);
  /** @type {[string, HTMLElement][]} */
  const nodes = [];
  probe.append(document.createElement("div"));
  for (const [tag, create] of Object.entries(FACE_ELEMENTS)) {
    if (tag === "li") continue;
    const node =
      tag === "pre"
        ? preNode
        : tag === "blockquote"
          ? quoteNode
          : tag === "ul"
            ? ulNode
            : create();
    nodes.push([tag, node]);
    if (tag === "ul") nodes.push(["li", liNode]);
    probe.append(node);
  }
  probe.append(document.createElement("div"));
  field.after(probe);
  // Type the field already inherits stays inherited.
  const own = getComputedStyle(field);
  const TYPE = ["font-size", "line-height", "font-weight", "letter-spacing"];
  /** @param {HTMLElement} node @returns {BlockFace} */
  const readFace = (node) => {
    const style = getComputedStyle(node);
    /** @param {string} value */
    const px = (value) => Number.parseFloat(value) || 0;
    return {
      type: TYPE.filter(
        (name) => style.getPropertyValue(name) !== own.getPropertyValue(name),
      )
        .map((name) => `${name}: ${style.getPropertyValue(name)}`)
        .join("; "),
      start: px(style.marginTop),
      end: px(style.marginBottom),
      padStart: px(style.paddingTop),
      padEnd: px(style.paddingBottom),
      inset: style.paddingInlineStart,
      indent: style.marginInlineStart,
    };
  };
  const li = readFace(liNode),
    pre = readFace(preNode),
    quote = readFace(quoteNode);
  /** @type {[string, BlockFace][]} */
  const faces = nodes.map(([tag, node]) => [
    tag,
    tag === "li"
      ? li
      : tag === "pre"
        ? pre
        : tag === "blockquote"
          ? quote
          : readFace(node),
  ]);
  probe.remove();
  const rules = [];
  for (const [tag, { type, start, end }] of faces) {
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
    `.lf-face-rule { line-height: 0 }`,
    `.lf-face-gap-above { padding-block-start: ${GAP} }`,
    `.lf-face-fence-open { line-height: ${pre.padStart}px }`,
    `.lf-face-fence-close { line-height: ${pre.padEnd}px }`,
    `.lf-face-code { padding-inline: ${pre.inset} }`,
    `.lf-face-quote { margin-inline-start: ${quote.indent}; padding-inline-start: ${quote.inset}; --lf-marker-inset: ${quote.inset} }`,
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
// names (`readFaces`); elsewhere only a fence's do. A code fence's lines stand for its
// block's padding while the caret is away, and an item after the first in a list stands
// its gap above it. The display trims the outer margins of its first and last blocks,
// so the field leaves none there, but a list's first and last items keep theirs.
/** @param {import("markdown-it").Token} token */
const blockTag = (token) =>
  token.type === "fence" || token.type === "code_block" ? "pre" : token.tag;
/** @param {EditorState} state @param {PlacedTokens} placed @param {import("@codemirror/state").Range<Decoration>[]} out @param {(name: string) => Decoration} line */
function standBlocks(state, placed, out, line) {
  /** @param {number} from @param {number} to @param {(line: import("@codemirror/state").Line) => void} each */
  const lines = (from, to, each) => {
    for (let at = from; at < to;) {
      const current = state.doc.lineAt(at);
      each(current);
      at = current.to + 1;
    }
  };
  /** @param {number} from @param {string} cls */
  const named = (from, cls) => out.push(line(cls).range(from));
  // A run of blank lines stands as one gap, shared among them.
  /** @param {number} from @param {number} to @param {string} gap */
  const gapLines = (from, to, gap) => {
    const runs = state.doc.lineAt(to).number - state.doc.lineAt(from).number;
    const share = runs > 1 ? ` lf-face-share-${Math.min(runs, 3)}` : "";
    lines(from, to, (each) => named(each.from, `lf-face-gap${share} ${gap}`));
  };
  /** @param {number} at */
  const lineTouched = (at) => {
    const { from, to } = state.doc.lineAt(at);
    return touches(state, from, to);
  };
  // The block before the one being read in each container still open, by level: the
  // draft itself and each quote. A list's items stand apart by their own gap.
  /** @type {({tag: string, to: number} | null)[]} */
  const before = [];
  /** @type {{type: string, to: number, level: number}[]} */
  const open = [];
  /** @type {{to: number} | null} */
  let item = null;
  /** @param {number} at */
  const blank = (at) => /^[\s>]*$/.test(state.doc.lineAt(at).text);
  for (const placement of placed) {
    const { token, from, to } = placement;
    if (!token.block) continue;
    const tag = blockTag(token);
    // A heading and a fence wear their faces wherever they stand.
    if (isBlockPlacement(placement, "heading_open")) {
      lines(...placement.contentLines, (each) => named(each.from, `lf-face-${tag}`));
      if (!token.markup.startsWith("#"))
        for (const [at] of placement.markers)
          if (!lineTouched(at)) named(state.doc.lineAt(at).from, "lf-face-rule");
    } else if (token.type === "fence" || token.type === "code_block") {
      lines(from, to, (each) => named(each.from, "lf-face-code"));
      const opener = state.doc.lineAt(from).number;
      for (const [at] of isBlockPlacement(placement, "fence")
        ? placement.markers
        : []) {
        const fence = state.doc.lineAt(at);
        if (lineTouched(at)) continue;
        const side = fence.number === opener ? "open" : "close";
        named(fence.from, `lf-face-fence-${side}`);
      }
    }
    let enclosing = open.at(-1);
    while (enclosing && enclosing.to <= from) {
      open.pop();
      before.length = enclosing.level + 1;
      enclosing = open.at(-1);
    }
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
    if (!Object.hasOwn(FACE_ELEMENTS, tag)) {
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
      lines(from, end, (each) => named(each.from, "lf-face-quote"));
      named(from, "lf-face-quote-first");
      named(state.doc.lineAt(Math.max(from, end - 1)).from, "lf-face-quote-last");
    }
  }
  // Blank lines after the last block, short of the line the next words will start on,
  // stand as the gap before a paragraph, so typing that paragraph moves no line.
  const last = state.doc.line(state.doc.lines);
  const final = before[0];
  if (final && final.to < last.from)
    gapLines(final.to, last.from, `lf-ends-${final.tag} lf-starts-p`);
}

/** @type {Promise<ReturnType<typeof fieldEditor>> | null} */
let loaded = null;
/** The field's editor, CodeMirror loaded under it. */
export const loadFieldEditor = () =>
  (loaded ??= import("/vendor/codemirror.esm.js").then((codemirror) =>
    fieldEditor(codemirror, leafEditorView(codemirror)),
  ));

/** What a field's editor needs CodeMirror for, built from the loaded module. */
/** @param {typeof import("/vendor/codemirror.esm.js")} codemirror @param {ReturnType<typeof leafEditorView>} LeafEditorView */
function fieldEditor(
  {
    EditorView,
    EditorState,
    StateEffect,
    Compartment,
    WidgetType,
    Decoration,
    LanguageSupport,
    ViewPlugin,
    keymap,
    history,
    standardKeymap,
    historyKeymap,
    isolateHistory,
    invertedEffects,
    markdownLanguage,
    insertNewlineContinueMarkup,
    insertNewline,
  },
  LeafEditorView,
) {
  // A step an owner recorded in the words' history (`record`): `run` makes it happen when
  // the history reaches it, and `back` is the step the other way.
  /** @type {import("@codemirror/state").StateEffectType<{run: () => void, back: () => void}>} */
  const ownerStep = StateEffect.define();

  const hide = Decoration.replace({});
  const dim = Decoration.mark({ class: "lf-md-mark" });
  const link = Decoration.mark({ class: "lf-md-link" });
  const unseen = Decoration.mark({
    class: "lf-md-unseen",
    attributes: { "aria-hidden": "true" },
  });
  const marker = Decoration.mark({
    class: "lf-md-marker lf-md-unseen",
    attributes: { "aria-hidden": "true" },
  });
  const shownMarker = Decoration.mark({ class: "lf-md-marker lf-md-mark" });
  /** @param {string} cls */
  const line = (cls) => Decoration.line({ class: cls });
  // A list item's line at its depth, wearing the marker a message's list draws there: the
  // bullet the platform's style sheet nests, or the item's number in its list. An item's
  // later line, and one whose source marker shows, wear none.
  /** @param {number} depth */
  const bullet = (depth) =>
    depth === 1 ? "lf-md-disc" : depth === 2 ? "lf-md-circle" : "lf-md-square";
  /** @param {number} depth @param {string | null | undefined} kind @param {number | null | undefined} number */
  const itemLine = (depth, kind, number) =>
    Decoration.line({
      class: kind ? `lf-md-item lf-md-listed ${kind}` : "lf-md-item",
      attributes: {
        style: `--lf-list-depth: ${depth}${kind === "lf-md-number" ? `; counter-set: list-item ${number}` : ""}`,
      },
    });

  // The inline constructs the preview draws, by the renderer's token type: each as the
  // element the renderer sends it as.
  /** @type {Readonly<Partial<Record<string, Decoration>>>} */
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
    /** @param {string} src @param {string} alt */
    constructor(src, alt) {
      super();
      this.src = isCanonicalMediaUrl(src) ? scopedMediaUrl(src) : src;
      this.alt = alt;
    }
    /** @param {Picture} other */
    eq(other) {
      return other.src === this.src && other.alt === this.alt;
    }
    /** @param {EditorView} view */
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

  /** @param {EditorState} state @param {PlacedTokens} placed */
  function decorate(state, placed) {
    /** @type {import("@codemirror/state").Range<Decoration>[]} */
    const out = [];
    // The ends of the lists open at the token being read, each list line's item, and the
    // code blocks, whose lines their own reading indents.
    /** @type {{to: number, next: number | null}[]} */
    const lists = [];
    /** @type {Map<number, {depth: number, kind?: string | null | undefined, number?: number | null, continued?: boolean}>} */
    const items = new Map();
    /** @type {[number, number][]} */
    const code = [];
    /** @param {number} from @param {number} to @param {Decoration} deco */
    const add = (from, to, deco) => {
      if (from >= to) return;
      // A hidden range may not hold a line break; such syntax stays drawn.
      if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
      out.push(deco.range(from, to));
    };
    /** @param {number} from @param {number} to @param {(line: import("@codemirror/state").Line) => void} each */
    const lines = (from, to, each) => {
      for (let at = from; at < to;) {
        const current = state.doc.lineAt(at);
        each(current);
        at = current.to + 1;
      }
    };
    for (const placement of placed) {
      const { token, from, to, content, escapes, markers, words: said } = placement;
      const syntax = touches(state, from, to) ? dim : hide;
      /** @type {[number, number] | undefined} */
      const words =
        token.type === "code_inline"
          ? [from + token.markup.length, to - token.markup.length]
          : content;
      if (words) {
        if (words[0] > words[1]) continue;
        const inline = INLINE[token.type];
        if (inline) add(from, to, inline);
        else if (
          token.type === "link_open" &&
          typeof token.lfSource?.url === "string"
        ) {
          add(words[0], words[1], link);
          if (opensElsewhere(token.lfSource.url))
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
        const widget = new Picture(String(token.attrGet("src")), token.content);
        out.push(
          touches(state, from, to)
            ? Decoration.widget({ widget, side: 1 }).range(to)
            : Decoration.replace({ widget }).range(from, to),
        );
      } else if (token.type === "text") {
        for (const at of escapes ?? [])
          add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
      } else if (isBlockPlacement(placement, "heading_open")) {
        lines(...placement.contentLines, (each) => {
          out.push(line("lf-md-heading").range(each.from));
        });
        // A Setext heading's rule is a line of its own, which keeps its room unseen while
        // the caret is away, as a fence's does.
        for (const [a, b] of placement.markers) {
          const rule = state.doc.lineAt(a);
          const shown = touches(state, rule.from, rule.to) ? dim : unseen;
          add(a, b, token.markup.startsWith("#") ? syntax : shown);
        }
      } else if (token.type === "fence" || token.type === "code_block") {
        code.push([from, to]);
        // Each line of code keeps the indent the parser's reading of it keeps; the rest,
        // a list item's or an indented block's own four spaces, the message drops.
        const body = token.content.split("\n");
        const opened = state.doc.lineAt(from).number + (token.type === "fence" ? 1 : 0);
        lines(from, to, (each) => {
          const ends = [
            each.from <= from ? " lf-md-code-first" : "",
            each.to + 1 >= to ? " lf-md-code-last" : "",
            token.type === "code_block" ? " lf-md-code-bare" : "",
          ].join("");
          out.push(line(`lf-md-code-block${ends}`).range(each.from));
          const kept = body[each.number - opened];
          if (kept === undefined || each.number - opened >= body.length - 1) return;
          const lead = indentation(each.text);
          add(each.from, each.from + lead - indentation(kept), hide);
        });
        // A fence's lines stand for the message's code padding (`standBlocks`), and each
        // shows its marks, at a line's height, while the caret is on it.
        for (const [a, b] of markers ?? []) {
          const fence = state.doc.lineAt(a);
          add(a, b, touches(state, fence.from, fence.to) ? dim : unseen);
        }
      } else if (isBlockPlacement(placement, "blockquote_open")) {
        lines(from, to, (each) => {
          out.push(line("lf-md-quote").range(each.from));
        });
        for (const [a, b] of placement.markers)
          add(a, b, touches(state, a, b) ? shownMarker : marker);
      } else if (
        token.type === "bullet_list_open" ||
        token.type === "ordered_list_open"
      ) {
        let enclosing = lists.at(-1);
        while (enclosing && enclosing.to <= from) {
          lists.pop();
          enclosing = lists.at(-1);
        }
        const ordered = token.type === "ordered_list_open";
        lists.push({ to, next: ordered ? Number(token.attrGet("start") ?? 1) : null });
      } else if (isBlockPlacement(placement, "list_item_open")) {
        let enclosing = lists.at(-1);
        while (enclosing && enclosing.to <= from) {
          lists.pop();
          enclosing = lists.at(-1);
        }
        const list = lists.at(-1);
        if (!list) throw new Error("leaf: Markdown list item has no containing list");
        const depth = lists.length;
        // An item's later lines stand under its words, their indent hidden as the
        // message drops it, and never revealed, so the words don't jump as the caret
        // arrives: a paragraph's whole indent, and in code what the code's reading drops
        // (above). A nested item, read after its parent, takes its own lines.
        const head = state.doc.lineAt(from);
        const [at, end] = placement.markers[0];
        // The marker's own indent stands in the inset with it. A quote's line keeps the
        // quote's rule and prefix at its start, where the platform's marker can't stand,
        // so an item there keeps its source marker, drawn as the prefix is.
        const start =
          head.from + head.text.slice(0, at - head.from).replace(/[ \t]*$/, "").length;
        if (head.text.slice(0, start - head.from).trim()) {
          add(start, end, dim);
          continue;
        }
        lines(head.to + 1, Math.min(to, state.doc.length), (each) => {
          items.set(each.from, { depth, continued: true });
        });
        const kind = list.next === null ? bullet(depth) : "lf-md-number";
        const shown = state.selection.ranges.some(
          (range) => range.from < end && range.to >= start,
        );
        items.set(head.from, { depth, kind: shown ? null : kind, number: list.next });
        if (list.next !== null) list.next++;
        add(start, end, shown ? shownMarker : marker);
      }
    }
    for (const [from, { depth, kind, number, continued }] of items) {
      out.push(itemLine(depth, kind, number).range(from));
      if (!continued || code.some(([a, b]) => from >= a && from < b)) continue;
      add(from, from + indentation(state.doc.lineAt(from).text), hide);
    }
    standBlocks(state, placed, out, line);
    return Decoration.set(out, true);
  }

  // The draft is read by the renderer that will send it, so the preview styles exactly what
  // the message will: the same constructs, the same links. The reading is taken again when
  // the words change and the styling when the selection moves. The renderer loads lazily;
  // until it has, the words stand plain, and its arrival draws every open field.
  const livePreview = ViewPlugin.fromClass(
    class {
      /** @param {EditorView} view */
      constructor(view) {
        this.live = true;
        this.placed = read(view.state);
        this.decorations = decorate(view.state, this.placed);
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
      /** @param {import("@codemirror/view").ViewUpdate} update */
      update(update) {
        const judged = markdownReady();
        if (update.docChanged || judged !== this.judged) {
          this.judged = judged;
          this.placed = read(update.state);
        } else if (!update.selectionSet) return;
        this.decorations = decorate(update.state, this.placed);
      }
    },
    { decorations: (plugin) => plugin.decorations },
  );

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
   * line, `field.revealed(view, pos)` shows the row holding `pos` in the field's
   * host, and `field.focused()` hears the editor take or lose focus. */
  /** @param {FieldWords} words @param {FieldConfiguration} field */
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
          /** @type {import("@codemirror/state").ChangeSpec[]} */
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
          { key: "Shift-Enter", run: insertNewlineContinueMarkup },
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
        new LanguageSupport(markdownLanguage),
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

  /** @param {boolean} on */
  const readOnly = (on) => ({
    effects: editable.reconfigure(EditorState.readOnly.of(on)),
  });
  /** @param {Record<string, string>} wanted */
  const contentAttributes = (wanted) => ({
    effects: attributes.reconfigure(EditorView.contentAttributes.of(wanted)),
  });
  // A step in the history that changes no words, standing alone: taking it back calls
  // `undo`, redoing it calls `redo`.
  /** @param {() => void} undo @param {() => void} redo */
  const record = (undo, redo) => ({
    effects: ownerStep.of({ run: redo, back: undo }),
    annotations: isolateHistory.of("full"),
  });
  // Dropping the history's field and adding it back starts it empty, in two successive
  // transactions.
  const forgetHistory = { effects: histories.reconfigure([]) };
  const startHistory = () => ({ effects: histories.reconfigure(history()) });

  /** Run the owner's steps an undo or redo reached. */
  /** @param {readonly import("@codemirror/state").Transaction[]} transactions */
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
