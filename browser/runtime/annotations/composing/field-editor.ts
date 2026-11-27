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
import { indentColumns } from "../../readings/code-lines.js";
import { opensElsewhere } from "../../records/declared-words.js";

import { leafEditorView } from "../editor-view.js";
import {
  loadMarkdown,
  markdownReady,
  markdownWords,
  placedMarkdownTokens,
  isBlockPlacement,
  renderMarkdown,
} from "../../lib/markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "../../records/media.js";
import type {
  ChangeSpec,
  EditorState,
  Range,
  StateEffectType,
  Text,
  Transaction,
  ChangeSet,
  Line,
  RangeSet,
} from "@codemirror/state";
import type {
  BlockInfo,
  BlockWrapper,
  Decoration,
  DecorationSet,
  EditorView,
  ViewUpdate,
} from "@codemirror/view";
import type { Token } from "markdown-it";
import type { BlockPlacement, PlacedToken } from "../../lib/markdown.js";
import type * as CodeMirror from "/vendor/codemirror.esm.js";

type Changes = ChangeSet;
type StateTarget = { state: EditorState; dispatch: (tr: Transaction) => void };
type PlacedTokens = ReturnType<typeof placedMarkdownTokens>;
type BlockFace = {
  type: string;
  start: number;
  end: number;
  padStart: number;
  padEnd: number;
  inset: string;
  indent: string;
};
type FieldWords = {
  base: string;
  text: string;
  anchor: number;
  head: number;
  steps: readonly (readonly [() => void, () => void])[];
};
export type FieldConfiguration = {
  typed: (native: boolean, insert: () => void) => void;
  returned: () => boolean;
  oneLine: () => boolean;
  message: () => boolean;
  revealed: (view: EditorView, pos: number) => void;
  focused: () => void;
  readOnly: boolean;
  attributes: Record<string, string>;
};

const indentation = (text: string) => text.length - text.replace(/^[ \t]*/, "").length;
const trailingIndentation = (text: string) =>
  text.length - text.replace(/[ \t]*$/, "").length;
// A fenced or an indented code block; only a file reads indentation as code.
const isCode = (token: Token) => token.type === "fence" || token.type === "code_block";

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state: EditorState, from: number, to: number) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. A last line holding nothing past its
// quotes' `>`, its items' markers and a task's box (`BARE`) is where the next words will
// be typed, so it is read holding a word, and stands in whichever block those words
// will join, as a line of an open fence's code, or of a quote or list item they continue
// lazily, and not in a list the line only trails; a block that takes it ends past the
// draft. So a new nested item is an item from its marker on, though the message reads an
// empty one as words of the paragraph above it. Nothing is placed in the word itself.
// Empty until the renderer has loaded. The last reading is kept, so a key that reads
// the draft it would leave, to choose its edit, and the field reading the draft the key
// leaves parse it once.
const BARE = /^(?:[\s>]|(?:[-+*]|\d{1,9}[.)])[ \t](?:\[[ xX]\][ \t])?)*$/;
const lastRead: { source: string | null; message: boolean; placed: PlacedTokens } = {
  source: null,
  message: false,
  placed: [],
};
/** @param message the reading (lib/markdown.js, `renderMarkdown`) */
const readSource = (source: string, message: boolean) => {
  if (lastRead.source === source && lastRead.message === message)
    return lastRead.placed;
  const placed = BARE.test(source.slice(source.lastIndexOf("\n") + 1))
    ? placedMarkdownTokens(`${source}x`, message).filter(
        ({ token, to }) => token.block || to <= source.length,
      )
    : placedMarkdownTokens(source, message);
  if (placed.length) Object.assign(lastRead, { source, message, placed });
  return placed;
};
const read = (state: EditorState, message: boolean) =>
  readSource(state.doc.toString(), message);

// The characters a draft shows, whitespace aside, each with how often, in the reading
// `read` takes: a bare last line holds a word nothing shows yet. The last few drafts'
// are kept, as a key weighs each of its candidate edits against the draft before it,
// and the edit it makes is the draft the next key starts from.
const recentlyShown: {
  source: string;
  message: boolean;
  shown: Map<string, number>;
}[] = [];
const shownCharacters = (source: string, message: boolean) => {
  const kept = recentlyShown.find((r) => r.source === source && r.message === message);
  if (kept) return kept.shown;
  const word = BARE.test(source.slice(source.lastIndexOf("\n") + 1)) ? "\u2063" : "";
  const shown = counted(markdownWords(source + word, message).replace(/\u2063/g, ""));
  recentlyShown.unshift({ source, message, shown });
  recentlyShown.length = Math.min(recentlyShown.length, 4);
  return shown;
};
// The characters of `text`, whitespace aside, each with how often.
const counted = (text: string) => {
  const counts = new Map<string, number>();
  for (const ch of text.replace(/\s/g, "")) counts.set(ch, (counts.get(ch) ?? 0) + 1);
  return counts;
};

// Columns of leading whitespace, a tab reaching the next multiple of four, as the
// renderer counts them.
const columns = (text: string) => {
  let col = 0;
  for (const ch of text) col = ch === "\t" ? col + 4 - (col % 4) : col + 1;
  return col;
};
type Placement = PlacedToken;
type ItemPlacement = Placement &
  BlockPlacement["list_item_open"] & { token: Token & { type: "list_item_open" } };
type QuotePlacement = Placement &
  BlockPlacement["blockquote_open"] & { token: Token & { type: "blockquote_open" } };
type ContainerPlacement = ItemPlacement | QuotePlacement;
const ITEM = "list_item_open";
const LIST = /^(bullet|ordered)_list_open$/;
type ListReading = {
  placement: Placement;
  items: ListItem[];
  last: ItemPlacement;
  depth: number;
};
type ListItem = ItemPlacement & {
  source: ItemPlacement;
  list: ListReading;
  number: number | null;
};
// The parser places a list before its items. Build the ownership from each list's
// range and level once; consumers retain the containing list and its complete items.
function readLists(placed: PlacedTokens) {
  const open: {
    placement: Placement;
    reading: ListReading | null;
    next: number | null;
    depth: number;
  }[] = [];
  const groups: ListReading[] = [];
  const items: ListItem[] = [];
  for (const placement of placed) {
    for (
      let last = open.at(-1);
      last && last.placement.to <= placement.from;
      last = open.at(-1)
    )
      open.pop();
    if (LIST.test(placement.token.type)) {
      open.push({
        placement,
        reading: null,
        depth: open.length + 1,
        next:
          placement.token.type === "ordered_list_open"
            ? Number(placement.token.attrGet("start") ?? 1)
            : null,
      });
    } else if (isBlockPlacement(placement, "list_item_open")) {
      const owner = open.at(-1);
      if (owner) {
        if (!owner.reading) {
          owner.reading = {
            placement: owner.placement,
            items: [],
            last: placement,
            depth: owner.depth,
          };
          groups.push(owner.reading);
        }
        const item = {
          ...placement,
          source: placement,
          list: owner.reading,
          number: owner.next,
        };
        owner.reading.items.push(item);
        owner.reading.last = placement;
        items.push(item);
        if (owner.next !== null) owner.next++;
      }
    }
  }
  return { groups, items };
}

// A list item's reading takes in the blank lines after its blocks, but words typed on
// one stand outside it: it ends with its last block, or its last item's marker line.
const itemEnd = (placed: PlacedTokens, item: Placement) =>
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
export function nestItems(
  source: string,
  placed: PlacedTokens,
  from: number,
  to: number,
  deeper: boolean,
) {
  const starts = [0];
  for (let at = source.indexOf("\n"); at !== -1; at = source.indexOf("\n", at + 1))
    starts.push(at + 1);
  const lineStart = (pos: number) => source.slice(0, pos).lastIndexOf("\n") + 1;
  const lineEnd = (start: number) => {
    const at = source.indexOf("\n", start);
    return at === -1 ? source.length : at;
  };
  const { groups, items } = readLists(placed);
  const end = (item: Placement) => Math.min(source.length, itemEnd(placed, item));
  const within = (c: Placement, at: number) => c.from <= at && at < c.to;
  const first = lineStart(from);
  const last = to > from && lineStart(to) === to ? lineStart(to - 1) : lineStart(to);
  const holding = items.filter((i) => i.from <= first && first < end(i)).at(-1);
  const chosen = items.filter(
    (i) => i === holding || (i.from >= first && i.from <= last),
  );
  if (!chosen.length) return null;

  const above = (i: ListItem) => i.list.items.findLast((s) => s.from < i.from);
  const parent = (i: ListItem) => {
    const list = i.list.placement;
    return items.findLast(
      (c) => c.token.level === list.token.level - 1 && within(c, list.from),
    );
  };
  // The marker of the item after `c` in its list.
  const next = ({ token }: ItemPlacement) =>
    `${token.info && Number(token.info) + 1}${token.markup}`;
  // Where an item's line starts past the `>` of the quotes it stands in, the column
  // its marker stands at past that, its marker, and the columns from the marker to
  // its words, one for an item with none or more than four, as the renderer reads it.
  const quotes = (i: ItemPlacement) =>
    placed
      .filter((c) => isBlockPlacement(c, "blockquote_open"))
      .filter((c) => c.token.level < i.token.level && within(c, i.from));
  const base = (i: ItemPlacement, start: number) =>
    Math.max(
      start,
      ...quotes(i)
        .flatMap((q) => q.markers)
        .filter(([a]) => a >= start && a <= lineEnd(start))
        .map(([, b]) => b),
    );
  const shape = (i: ItemPlacement) => {
    const at = base(i, i.from);
    const [a, b] = i.markers[0];
    const mark = source.slice(a, b).trimEnd();
    const rest = source.slice(a + mark.length, lineEnd(i.from));
    const gap = rest.trim() ? columns(rest.slice(0, indentation(rest))) : 1;
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

  const changes: { from: number; to: number; insert: string }[] = [];
  const moved: { item: ItemPlacement; shift: number }[] = [];
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
        const list = groups.find((group) => group.placement === inside.at(-1));
        if (list) mark = next(list.last);
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
      const lead = source.slice(at, at + indentation(source.slice(at, lineEnd(start))));
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
 * enables to this list or to its recorded exceptions, such as a link's definition. */
export const DRAWN = new Set([
  "paragraph_open",
  "heading_open",
  "blockquote_open",
  "bullet_list_open",
  "ordered_list_open",
  "list_item_open",
  "fence",
  "code_block",
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
  "table_open",
  "tr_open",
]);

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
  hr: () => document.createElement("hr"),
  table: () => document.createElement("table"),
  ul: () => document.createElement("ul"),
  ol: () => document.createElement("ol"),
  li: () => document.createElement("li"),
};
// The gap two blocks' margins leave between them, collapsed as the platform collapses
// adjoining margins, in px or as CSS over the two a gap line names (`standBlocks`).
const collapsed = (a: number, b: number) => Math.max(a, b, 0) + Math.min(a, b, 0);
const GAP =
  "calc(max(var(--lf-gap-end), var(--lf-gap-start), 0px) + " +
  "min(var(--lf-gap-end), var(--lf-gap-start), 0px))";
// The rules that draw each block in the face the cascade gives it in `display`, the
// element whose blocks the field's words are shown as: their type, and the margins and
// padding that set them apart from their neighbours. The probe is an empty copy of that
// element standing beside the field, in its place among its siblings, so the page's own
// rules, which skip Leaf's interface, and its density reach the probe's blocks as they
// reach the display's. A list's outer margins collapse with its first and last items'.
export function readFaces(field: HTMLElement, display: HTMLElement) {
  const probe = display.cloneNode(false);
  probe.removeAttribute("id");
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText =
    "position: absolute; visibility: hidden; inline-size: 0; display: block";
  const preNode = FACE_ELEMENTS.pre();
  const quoteNode = FACE_ELEMENTS.blockquote();
  // A table of a head row and a body row, three cells each, so the middle cells show
  // the padding between columns and the outer ones that at the table's edges.
  const tableNode = FACE_ELEMENTS.table();
  const headRow = tableNode.createTHead().insertRow();
  const bodyRow = tableNode.createTBody().insertRow();
  for (let i = 0; i < 3; i++) {
    headRow.append(document.createElement("th"));
    bodyRow.insertCell();
  }
  const liNode = FACE_ELEMENTS.li();
  const ulNode = FACE_ELEMENTS.ul();
  ulNode.append(FACE_ELEMENTS.li(), liNode);
  const nodes: [string, HTMLElement][] = [];
  probe.append(document.createElement("div"));
  for (const [tag, create] of Object.entries(FACE_ELEMENTS)) {
    if (tag === "li") continue;
    const node =
      tag === "pre"
        ? preNode
        : tag === "blockquote"
          ? quoteNode
          : tag === "table"
            ? tableNode
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
  const readFace = (node: HTMLElement): BlockFace => {
    const style = getComputedStyle(node);
    const px = (value: string) => Number.parseFloat(value) || 0;
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
    quote = readFace(quoteNode),
    table = readFace(tableNode);
  // A cell's type leaves out its line height, which the field keeps as the factor of
  // its size the sent table sets (text-field.js), since a computed height in pixels
  // would hold a code span in the cell to the cell's line rather than its own.
  const cell = (row: HTMLTableRowElement) => {
    const [first, middle, last] = [...row.cells].map((c) => getComputedStyle(c));
    const face = readFace(row.cells[1] as HTMLElement);
    return {
      face: {
        ...face,
        type: face.type
          .split("; ")
          .filter((part) => !part.startsWith("line-height"))
          .join("; "),
      },
      inline: `${middle?.paddingInlineStart} ${middle?.paddingInlineEnd}`,
      edges: [first?.paddingInlineStart, last?.paddingInlineEnd],
    };
  };
  const th = cell(headRow),
    td = cell(bodyRow);
  const faces: [string, BlockFace][] = nodes.map(([tag, node]) => [
    tag,
    tag === "li"
      ? li
      : tag === "pre"
        ? pre
        : tag === "blockquote"
          ? quote
          : tag === "table"
            ? table
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
    `.lf-face-gap-above { padding-block-start: ${GAP} }`,
    `.lf-face-code { padding-inline: ${pre.inset} }`,
    `.lf-face-quote { margin-inline-start: ${quote.indent}; --lf-quote-inset: ${quote.inset} }`,
    `.lf-face-quote-first { padding-block-start: ${quote.padStart}px }`,
    `.lf-face-gap-above.lf-face-quote-first { padding-block-start: calc(${GAP} + ${quote.padStart}px) }`,
    `.lf-face-quote-last { padding-block-end: ${quote.padEnd}px }`,
    `.lf-face-table-last { padding-block-end: ${table.padEnd}px }`,
    // A table's rows (\`decorate\`): the head's lower padding is its delimiter row's line.
    `.lf-face-table .lf-md-cell { padding-block: ${td.face.padStart}px ${td.face.padEnd}px; padding-inline: ${td.inline} }`,
    `.lf-face-table .lf-md-cell:first-child { padding-inline-start: ${td.edges[0]} }`,
    `.lf-face-table .lf-md-cell:last-child { padding-inline-end: ${td.edges[1]} }`,
    `.lf-face-table.lf-md-table-row:not(.lf-md-table-head, .lf-md-table-rule) { ${td.face.type} }`,
    `.lf-face-table.lf-md-table-head { ${th.face.type} }`,
    `.lf-face-table.lf-md-table-head .lf-md-cell { padding-block: ${th.face.padStart}px 0; padding-inline: ${th.inline} }`,
    `.lf-face-table.lf-md-table-head .lf-md-cell:first-child { padding-inline-start: ${th.edges[0]} }`,
    `.lf-face-table.lf-md-table-head .lf-md-cell:last-child { padding-inline-end: ${th.edges[1]} }`,
    `.lf-face-table.lf-md-table-rule { line-height: ${th.face.padEnd}px }`,
    `.lf-face-item { padding-block-start: ${collapsed(li.end, li.start)}px }`,
    `.lf-face-list-lead { padding-block-start: ${collapsed(0, li.start)}px }`,
    `.lf-face-list-tail { padding-block-end: ${collapsed(0, li.end)}px }`,
  );
  return rules.join("\n");
}

// A code block's lines as its reading holds them, and the number of the source line
// holding the first: the line after a fence's own, or the fence's own where words stand
// on it (lib/markdown.js, `fence_words`).
function codeRows(state: EditorState, c: PlacedToken) {
  const markers = c.markers ?? [];
  const opening = state.doc.lineAt(c.from);
  const inline = markers.length > 0 && (markers[0]?.[1] ?? 0) < opening.to;
  const body = c.token.content.split("\n");
  if (body.at(-1) === "") body.pop();
  return {
    body,
    opening,
    inline,
    first: opening.number + (markers.length && !inline ? 1 : 0),
  };
}

// Calls `each` with every line of `doc` that holds a position from `from` up to `to`.
function eachLine(doc: Text, from: number, to: number, each: (line: Line) => void) {
  for (let at = from; at < to;) {
    const current = doc.lineAt(at);
    each(current);
    at = current.to + 1;
  }
}

// The one edit that turns `was` into `put`, starting at `at` in the document: the run
// between their longest common prefix and the longest common suffix that doesn't
// overlap it.
function differing(
  was: string,
  put: string,
  at: number = 0,
): { from: number; to: number; insert: string } {
  const most = Math.min(was.length, put.length);
  let head = 0;
  while (head < most && was[head] === put[head]) head++;
  let tail = 0;
  while (
    tail < most - head &&
    was[was.length - 1 - tail] === put[put.length - 1 - tail]
  )
    tail++;
  return {
    from: at + head,
    to: at + was.length - tail,
    insert: put.slice(head, put.length - tail),
  };
}

// Each outermost block's lines name its face, and the lines between two blocks the gap
// the display leaves there: the blank lines that part them in the source, or the
// second's first line where none do. Only a field that edits in place has rules for the
// names (`readFaces`). A quote's and an item's insets are their boxes' (`decorate`). An
// item after the first in a list stands its gap above it.
// The display trims the outer margins of its first and last blocks, so the field
// leaves none there, but a list's first and last items keep theirs.
const blockTag = (token: Token) => (isCode(token) ? "pre" : token.tag);
const CONTAINER = /^(blockquote|bullet_list|ordered_list|list_item)_open$/;

// Whether a line, by its number, is blank where it stands: it holds nothing but spaces,
// tabs and the `>` of the quotes around it, no block opens on it, and no paragraph,
// heading, table or code block covers it. So a blank line inside code is not blank, nor
// a `>` that code shows, nor a link's definition, which the parser keeps for itself.
function blankLines(doc: Text, placed: PlacedTokens) {
  const taken = new Set<number>();
  const quotes = new Map<number, number>();
  for (const { token, from, to } of placed) {
    if (!token.block) continue;
    const first = doc.lineAt(from).number;
    const last = doc.lineAt(Math.max(from, to - 1)).number;
    taken.add(first);
    if (token.type === "blockquote_open")
      for (let n = first; n <= last; n++) quotes.set(n, (quotes.get(n) ?? 0) + 1);
    if (CONTAINER.test(token.type)) continue;
    for (let n = first + 1; n <= last; n++) taken.add(n);
  }
  return (n: number) => {
    if (taken.has(n)) return false;
    let text = doc.line(n).text;
    for (let quote = quotes.get(n) ?? 0; quote > 0; quote--)
      text = text.replace(/^[ \t]*>/, "");
    return /^[ \t]*$/.test(text);
  };
}
function standBlocks(
  state: EditorState,
  blocks: PlacedTokens,
  out: Range<Decoration>[],
  line: (className: string) => Decoration,
) {
  const named = (from: number, cls: string) => out.push(line(cls).range(from));
  // One blank line stands as the gap. In a run of them, the first and last lines stand
  // as the gaps the prose leaves above and below a paragraph, and each line between as
  // one of its lines, so every Return shows a line. Words typed on the one line between
  // two gaps move nothing. In a longer run, the lines beside the new paragraph become its
  // gaps, so the words below it rise by a line less a gap. The display draws the run as
  // one gap, and saving writes it as one blank line (`oneLinePerGap`).
  const gapLines = (from: number, to: number, prior: string, next: string) => {
    const first = state.doc.lineAt(from);
    const last = state.doc.lineAt(to - 1);
    if (first.number === last.number) {
      named(first.from, `lf-face-gap lf-ends-${prior} lf-starts-${next}`);
      return;
    }
    named(first.from, `lf-face-gap lf-ends-${prior} lf-starts-p`);
    for (let n = first.number + 1; n < last.number; n++)
      named(state.doc.line(n).from, "lf-face-p");
    named(last.from, `lf-face-gap lf-ends-p lf-starts-${next}`);
  };
  // The block before the one being read in each container still open, by level: the
  // draft itself and each quote. A list's items stand apart by their own gap.
  const before: ({ tag: string; to: number } | null)[] = [];
  const open: { type: string; to: number; level: number }[] = [];
  let item: { to: number } | null = null;
  const blank = blankLines(state.doc, blocks);
  for (const { token, from, to } of blocks) {
    if (!token.block) continue;
    const tag = blockTag(token);
    // A heading and a code block wear their faces wherever they stand.
    if (token.type === "heading_open")
      eachLine(state.doc, from, to, (each) => named(each.from, `lf-face-${tag}`));
    else if (isCode(token))
      eachLine(state.doc, from, to, (each) => named(each.from, "lf-face-code"));
    else if (token.type === "table_open") {
      eachLine(state.doc, from, to, (each) => named(each.from, "lf-face-table"));
      named(state.doc.lineAt(Math.max(from, to - 1)).from, "lf-face-table-last");
    }
    for (let last = open.at(-1); last && last.to <= from; last = open.at(-1)) {
      before.length = last.level + 1;
      open.pop();
    }
    const within = open.at(-1)?.type;
    if (token.type === "list_item_open" && within !== "list_item_open") {
      if (item?.to === from) named(from, "lf-face-item");
      item = { to };
    }
    if (CONTAINER.test(token.type))
      open.push({ type: token.type, to, level: token.level });
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
    if (prior && prior.to < from) gapLines(prior.to, from, prior.tag, tag);
    else if (prior)
      named(from, `lf-face-gap-above lf-ends-${prior.tag} lf-starts-${tag}`);
    // A block's reading can take in the blank lines after it, which part it from the next.
    let end = to;
    while (end > from && blank(state.doc.lineAt(end - 1).number))
      end = state.doc.lineAt(end - 1).from;
    before[level] = { tag, to: end };
    before.length = level + 1;
    if (token.type === "paragraph_open" && level === 0)
      eachLine(state.doc, from, to, (each) => named(each.from, "lf-face-p"));
    else if (token.type === "blockquote_open" && level === 0) {
      named(from, "lf-face-quote-first");
      named(state.doc.lineAt(Math.max(from, end - 1)).from, "lf-face-quote-last");
    }
  }
}

let loaded: Promise<ReturnType<typeof fieldEditor>> | null = null;
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
    insertNewline,
    ChangeSet,
  }: typeof CodeMirror,
  LeafEditorView: ReturnType<typeof leafEditorView>,
) {
  // A step an owner recorded in the words' history (`record`): `run` makes it happen when
  // the history reaches it, and `back` is the step the other way.
  const ownerStep: StateEffectType<{ run: () => void; back: () => void }> =
    StateEffect.define();

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
  const markerFace = (kind: "quote" | "item") => ({
    hidden: Decoration.mark({
      class: `lf-md-marker lf-md-${kind}-marker lf-md-unseen`,
      attributes: { "aria-hidden": "true" },
    }),
    shown: Decoration.mark({
      class: `lf-md-marker lf-md-${kind}-marker lf-md-mark`,
    }),
  });
  const markerFaces = { quote: markerFace("quote"), item: markerFace("item") };
  const markerRun = Decoration.mark({
    class: "lf-md-markers",
    inclusiveEnd: true,
  });
  // A cell's `|`, unseen or shown, taking no room: the one opening a cell stands in the
  // padding before its words, and the one closing a row after them.
  const pipeFace = (side: "open" | "close") => ({
    hidden: Decoration.mark({
      class: `lf-md-pipe lf-md-pipe-${side} lf-md-unseen`,
      attributes: { "aria-hidden": "true" },
    }),
    shown: Decoration.mark({ class: `lf-md-pipe lf-md-pipe-${side} lf-md-mark` }),
  });
  const pipeFaces = { open: pipeFace("open"), close: pipeFace("close") };
  // A table's cell, a grid item of its row (`decorate`), aligned as its column's
  // delimiter says. It holds every character of its stretch of the row, and the hidden
  // spaces at its ends, since anything outside every cell would stand in the grid as a
  // cell of its own.
  const cellFace = (align: string) =>
    Decoration.mark({ class: `lf-md-cell lf-md-align-${align}`, inclusive: true });
  const cellFaces = {
    start: cellFace("start"),
    center: cellFace("center"),
    right: cellFace("right"),
  };
  // A column's alignment, as the renderer reads its delimiter: a left one is the
  // start's.
  const alignment = (align: string | undefined) =>
    align === "center" || align === "right" ? align : "start";
  // The room a container's marker takes in a run, for a container whose marker the line
  // doesn't hold, as a quote's lazy line and an item's later line don't, so the markers
  // before it stand in their own containers' insets.
  class Inset extends WidgetType {
    declare kind: "quote" | "item";

    constructor(kind: "quote" | "item") {
      super();
      this.kind = kind;
    }
    eq(other: Inset) {
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
  const line = (cls: string) => Decoration.line({ class: cls });
  // A quote and a list item are each a box around their lines, as the message's
  // blockquote and li are, so a nested one stands inside its container with the
  // container's rule and inset beside it, and so does a code block in either. An item
  // wears the marker a message's list draws there: the bullet the platform's style sheet
  // nests, or the item's number in its list; one whose source marker shows wears none.
  // A box takes the lines that start in its range, including one starting at its end,
  // so it ends on its last line's break. CodeMirror carries a box on into a later one
  // that equals it, so each names its level, and a container is ranked outside its
  // contents. Rejected: a class on each line, which CodeMirror
  // merges, so every level of a nested quote drew one rule at one inset and a code
  // block's frame replaced its quote's; and boxes for quotes alone, which put a quote's
  // rule outside the item holding it, and the item's bullet inside the quote.
  const BULLETS = ["lf-md-disc", "lf-md-circle", "lf-md-square"];
  const box = (
    from: number,
    to: number,
    level: number,
    attributes: Record<string, string>,
  ) =>
    BlockWrapper.create({
      tagName: "div",
      attributes: { ...attributes, "data-lf-level": String(level) },
      rank: 100 - level,
    }).range(from, Math.max(from, to - 1));

  // The inline constructs the preview draws, by the renderer's token type: each as the
  // element the renderer sends it as.
  const INLINE: Readonly<Partial<Record<string, Decoration>>> = {
    code_inline: Decoration.mark({ tagName: "code" }),
    em_open: Decoration.mark({ tagName: "em" }),
    strong_open: Decoration.mark({ tagName: "strong" }),
    s_open: Decoration.mark({ tagName: "s" }),
  };

  // A picture's syntax, while the caret is away, is the picture the message shows for it,
  // from the source the parser resolved, a reference's included, at the address the
  // renderer gives page media (records/page-markdown.js, `pageLinks`). A press on it puts the
  // caret in its source.
  class Picture extends WidgetType {
    declare src: string;
    declare alt: string;

    constructor(src: string, alt: string) {
      super();
      this.src = isCanonicalMediaUrl(src) ? scopedMediaUrl(src) : src;
      this.alt = alt;
    }
    eq(other: Picture) {
      return other.src === this.src && other.alt === this.alt;
    }
    toDOM(view: EditorView) {
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
  // The mark after a link that leaves the page, which the page's rule draws through
  // the part (surfaces.css). It stands before its position, where CodeMirror puts no
  // buffer between it and the link's words, so it keeps to their line.
  class ExternalMark extends WidgetType {
    eq() {
      return true;
    }
    toDOM() {
      const mark = document.createElement("span");
      mark.className = "lf-ui lf-external-mark";
      mark.setAttribute("part", "lf-external-mark");
      mark.ariaHidden = "true";
      return mark;
    }
  }
  const externalMark = Decoration.widget({
    widget: new ExternalMark(),
    side: -1,
  });
  // The character an entity names, where the message shows it.
  class Spelled extends WidgetType {
    declare shown: string;

    constructor(shown: string) {
      super();
      this.shown = shown;
    }
    eq(other: Spelled) {
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
    declare checked: boolean;

    constructor(checked: boolean) {
      super();
      this.checked = checked;
    }
    eq(other: TaskBox) {
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
  function decorate(state: EditorState, placed: PlacedTokens) {
    const out: Range<Decoration>[] = [];
    const runs: Range<Decoration>[] = [];
    const boxes: Range<BlockWrapper>[] = [];
    // The lines whose leading
    // spaces the message drops, by the level of the block they lead, the blocks whose
    // lines draw their own leading spaces (code, by its reading, and a rule), the
    // containers' markers, and the containers.
    const items: Map<Placement, ListItem> = new Map(
      readLists(placed).items.map((item) => [item.source, item]),
    );
    const leads: [number, number][] = [];
    const whole: [number, number][] = [];
    // The table whose rows the placements after it read.
    let table: {
      from: number;
      to: number;
      level: number;
      aligns: string[];
      shown: boolean;
    } | null = null;
    const opening: {
      from: number;
      to: number;
      kind: "quote" | "item";
      level: number;
      line: number;
      shown?: boolean;
    }[] = [];
    const held: { from: number; to: number; kind: "quote" | "item"; level: number }[] =
      [];
    // Where the markers end that open the line starting at `line` for the containers
    // outside `level`: a block inside them starts on that line no earlier.
    const after = (line: number, level: number) =>
      Math.max(
        line,
        ...opening.filter((m) => m.line === line && m.level < level).map((m) => m.to),
      );
    const add = (from: number, to: number, deco: Decoration) => {
      if (from >= to) return;
      // A hidden range may not hold a line break; such syntax stays drawn.
      if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
      out.push(deco.range(from, to));
    };
    for (const placement of placed) {
      const { token, from, to, content, spelled, words: said } = placement;
      const item = items.get(placement);
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
      const words: [number, number] | undefined =
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
        // In a table's cell it stands before the position after its source, so it
        // stays in that cell when the next one starts there, since anything outside
        // every cell stands in the grid as a cell of its own.
        const celled = table !== null && from >= table.from && to <= table.to;
        out.push(
          touches(state, from, to)
            ? Decoration.widget({ widget, side: celled ? -1 : 1 }).range(to)
            : Decoration.replace({ widget }).range(from, to),
        );
      } else if (token.type === "html_inline") {
        // A task item's box (lib/markdown.js), drawn in place of its brackets.
        if (touches(state, from, to)) add(from, to, dim);
        else
          out.push(
            Decoration.replace({
              widget: new TaskBox(token.content.includes("checked")),
            }).range(from, to),
          );
      } else if (token.type === "paragraph_open") {
        eachLine(state.doc, from, to, (each) => leads.push([each.from, token.level]));
      } else if (isBlockPlacement(placement, "heading_open")) {
        eachLine(state.doc, from, to, (each) => {
          out.push(line("lf-md-heading").range(each.from));
          leads.push([each.from, token.level]);
        });
        for (const [a, b] of placement.markers) add(a, b, syntax);
      } else if (token.type === "hr") {
        // A rule is the line the message draws, its source on it, unseen while the
        // caret is away from it, and the spaces leading it hidden, as below.
        const rule = state.doc.lineAt(from);
        whole.push([rule.from, rule.to + 1]);
        out.push(line("lf-md-rule").range(rule.from));
        const start = after(rule.from, token.level);
        const marks = start + indentation(state.doc.sliceString(start, rule.to));
        add(start, marks, hide);
        add(marks, rule.to, touches(state, rule.from, rule.to) ? dim : unseen);
      } else if (isCode(token)) {
        whole.push([from, to]);
        // Each line of code keeps the indent the parser's reading of it keeps; the rest,
        // a list item's indent after its containers' markers or an indented block's
        // four spaces, the rendered code drops. The code's reading ends each line it
        // holds with a break, except a last line the draft's end ends, and holds none
        // for a fence with no code. An end no fence line stands for, as at both ends of
        // an indented block, takes the padding on the code's own line.
        const markers = placement.markers ?? [];
        // Words on the opening line are the code's first line (lib/markdown.js,
        // `fence_words`), which then takes the padding its fence line stood for.
        const { body, opening, inline, first: opened } = codeRows(state, placement);
        eachLine(state.doc, from, to, (each) => {
          const first = each.from <= from;
          const last = each.to + 1 >= to;
          const ends = [
            first ? " lf-md-code-first" : "",
            first && (!markers.length || inline) ? " lf-md-code-pad-start" : "",
            last ? " lf-md-code-last" : "",
            last && markers.length < 2 ? " lf-md-code-pad-end" : "",
          ].join("");
          const kept = body[each.number - opened];
          // A code line's rows hang from its indent, as the sent block's do
          // (marks.css, `[data-lf-pre-line]`), which the line states as the block's
          // boxes do.
          const indent = kept === undefined ? 0 : indentColumns(kept, state.tabSize);
          out.push(
            Decoration.line({
              class: `lf-md-code-block${ends}`,
              attributes: {
                "data-lf-pre-line": "",
                ...(indent && { style: `--lf-code-indent: ${indent}` }),
              },
            }).range(each.from),
          );
          if (kept === undefined) return;
          const start = after(each.from, token.level);
          const lead = indentation(state.doc.sliceString(start, each.to));
          add(start, start + lead - indentation(kept), hide);
        });
        // A fence's lines stand for the message's code padding, and each shows its
        // marks while the caret is on it. Marks with code beside them hide as a code
        // span's do, standing the code under the line below.
        for (const [a, b] of markers) {
          const fence = state.doc.lineAt(a);
          const away = inline && fence.from === opening.from ? hide : unseen;
          add(a, b, touches(state, fence.from, fence.to) ? dim : away);
        }
      } else if (token.type === "table_open") {
        // A table is a grid around its rows (`box`), each row a line whose cells stand
        // in the grid's columns, so a column is as wide as its widest cell, as the
        // message's table draws it. Each `|` takes no room and is unseen while the
        // caret is away from the table, and the spaces around a cell's words, which
        // the message drops, stay hidden, so reaching the table moves no word. The
        // delimiter row is the rule under the head, its source unseen while the caret
        // is away and standing for the rule once shown.
        const aligns = token.lfSource?.aligns ?? [];
        const shown = touches(
          state,
          from,
          state.doc.line(lastLine(state, placement)).to,
        );
        table = { from, to, level: token.level, aligns, shown };
        boxes.push(
          box(from, to, token.level, {
            class: "lf-md-table",
            style: `--lf-table-columns: ${aligns.length}`,
          }),
        );
        const rule = state.doc.line(state.doc.lineAt(from).number + 1);
        // With the caret on it, the delimiter row takes a line's height and wraps, so
        // the caret stays in sight where its source runs past the field: the rows below
        // move then, on a row the caret seldom visits.
        const editing = touches(state, rule.from, rule.to);
        out.push(
          line(
            `lf-md-table-row lf-md-table-rule${shown ? " lf-md-shown" : ""}${editing ? " lf-md-editing" : ""}`,
          ).range(rule.from),
        );
        leads.push([rule.from, token.level]);
        add(after(rule.from, token.level), rule.to, shown ? dim : unseen);
      } else if (isBlockPlacement(placement, "tr_open") && table && from < table.to) {
        // A row's cells are the source between its `|`s the renderer's split found
        // (lib/markdown.js), each drawn from the `|` before it to the next cell's, the
        // first from the line's start and the last to its end, so the cells cover the
        // line. The cells past the head's count, which the message drops, stand in the
        // last column, hidden while the caret is away from the table, and a row the
        // split found no cell in, as one holding only a `|`, is one cell of its source.
        const row = state.doc.lineAt(from);
        const head = row.from === table.from;
        out.push(
          line(`lf-md-table-row${head ? " lf-md-table-head" : ""}`).range(row.from),
        );
        leads.push([row.from, table.level]);
        // A row the field reads a bare last line as holding (`read`) stands past the
        // draft's end.
        const at = (n: number) => Math.min(n, row.to);
        const spans = placement.markers.map(([a, b]) => [at(a), at(b)] as const);
        const { aligns, shown, level } = table;
        const cells = spans.slice(0, aligns.length);
        const surplus = spans[aligns.length];
        const face = shown ? "shown" : "hidden";
        if (!cells.length && row.from < row.to) {
          runs.push(
            Decoration.mark({
              class: "lf-md-cell",
              attributes: { style: "grid-column: 1 / -1" },
            }).range(row.from, row.to),
          );
          add(after(row.from, table.level), row.to, shown ? dim : unseen);
        }
        cells.forEach(([a, b], column) => {
          const pipe = state.sliceDoc(a - 1, a) === "|" ? a - 1 : null;
          const last = column === cells.length - 1;
          const close = last && !surplus && state.sliceDoc(b, b + 1) === "|" ? b : null;
          const cellFrom = column === 0 ? row.from : (pipe ?? a);
          const cellTo = last ? row.to : (cells[column + 1]?.[0] ?? b + 1) - 1;
          // A row short of cells runs its last to the table's end, ruled across as the
          // message's empty cells are.
          const rest = last && cells.length < aligns.length;
          if (cellFrom < cellTo)
            runs.push(
              (rest
                ? Decoration.mark({
                    class: `lf-md-cell lf-md-align-${alignment(aligns[column])}`,
                    attributes: { style: `grid-column: ${column + 1} / -1` },
                    inclusive: true,
                  })
                : cellFaces[alignment(aligns[column])]
              ).range(cellFrom, cellTo),
            );
          // Leading white space the parser trims and the spaces the field hides
          // (`leads`) leave, such as a non-breaking space before the first `|`.
          if (column === 0 && pipe !== null) {
            const start = after(row.from, level);
            add(start + indentation(state.sliceDoc(start, pipe)), pipe, hide);
          }
          const text = state.sliceDoc(a, b);
          const words = [
            a + text.length - text.trimStart().length,
            a + text.trimEnd().length,
          ] as const;
          if (pipe !== null) add(pipe, pipe + 1, pipeFaces.open[face]);
          add(a, words[0], hide);
          add(words[1], b, hide);
          // A `\` before a `|` in the words keeps the `|` from parting cells, and
          // shows as an escape does, hidden until the caret reaches it.
          for (const { index } of text.matchAll(/\\\|/g)) {
            const at = a + index;
            add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
          }
          if (close !== null) {
            add(close, close + 1, pipeFaces.close[face]);
            add(close + 1, row.to, hide);
          }
        });
        if (surplus) add(surplus[0] - 1, row.to, shown ? dim : hide);
      } else if (isBlockPlacement(placement, "blockquote_open")) {
        boxes.push(box(from, to, token.level, { class: "lf-md-quote lf-face-quote" }));
        held.push({ from, to, level: token.level, kind: "quote" });
        for (const [a, b] of placement.markers) {
          const line = state.doc.lineAt(a).from;
          opening.push({
            from: a,
            to: b,
            kind: "quote",
            level: token.level,
            line,
          });
          leads.push([line, token.level]);
        }
      } else if (item) {
        const depth = item.list.depth;
        // An item's later lines stand under its words, their indent hidden as the
        // message drops it, and never revealed, so the words don't jump as the caret
        // arrives: a paragraph's whole indent, and in code what the code's reading drops
        // (above). A nested item, read after its parent, takes its own lines.
        const head = state.doc.lineAt(from);
        const [at, end] = item.markers[0];
        // The marker's own indent stands in the inset with it, after the markers of the
        // containers that open the line before it.
        const start = Math.max(
          at - trailingIndentation(head.text.slice(0, at - head.from)),
          after(head.from, token.level),
        );
        eachLine(state.doc, head.to + 1, to, (each) =>
          leads.push([each.from, token.level]),
        );
        const kind =
          item.number === null
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
                  ...(item.number !== null && {
                    style: `counter-set: list-item ${item.number}`,
                  }),
                },
          ),
        );
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
      add(start, start + indentation(state.doc.sliceString(start, to)), hide);
    }
    // The markers that open a line stand, in order, in the insets of the containers they
    // open, right to left from the line's words, unseen while the caret is away, so
    // revealing one moves no word. A container the line stands in without a marker, as
    // a quote's lazy line and an item's later line do, keeps its inset after the markers
    // of the containers outside it.
    opening.sort((a, b) => a.from - b.from);
    type Marker = (typeof opening)[number];
    const groups: { first: Marker; last: Marker; markers: Marker[] }[] = [];
    for (const marker of opening) {
      const prior = groups.at(-1);
      if (prior && marker.from === prior.last.to) {
        prior.last = marker;
        prior.markers.push(marker);
      } else groups.push({ first: marker, last: marker, markers: [marker] });
    }
    for (const { first, last, markers: run } of groups) {
      runs.push(markerRun.range(first.from, last.to));
      for (const { from, to, kind, shown } of run) {
        const faces = markerFaces[kind];
        out.push(
          ((shown ?? touches(state, from, to)) ? faces.shown : faces.hidden).range(
            from,
            to,
          ),
        );
      }
      const { line } = first;
      for (const container of held
        .filter(
          (c) =>
            c.from <= line &&
            line < c.to &&
            !opening.some((m) => m.line === line && m.level === c.level),
        )
        .sort((a, b) => a.level - b.level)) {
        const outside = run.findLast((m) => m.level < container.level);
        if (outside) out.push(insets[container.kind].range(outside.to));
      }
    }
    standBlocks(state, placed, out, line);
    return {
      decorations: Decoration.set(out, true),
      runs: Decoration.set(runs, true),
      boxes: BlockWrapper.set(boxes, true),
    };
  }

  // Up and Down step to the next line, however short the preview draws it. CodeMirror's
  // vertical motion aims half a line of text past the caret's line, so it passes over a
  // line shorter than that, as a blank line can be where it stands as the gap a field
  // that edits in place draws between two blocks (`standBlocks`). Where its step
  // passes over the line beside the caret's, the caret goes to that line instead, at
  // the goal column CodeMirror aimed for, found in its own map of line heights.
  // Without Shift, a selection collapses to its end that way, as CodeMirror's own step
  // does.
  const lineStep =
    (forward: boolean, extend: boolean): ((view: EditorView) => boolean) =>
    (view) => {
      const { selection, doc } = view.state;
      const moved = EditorSelection.create(
        selection.ranges.map((range) => {
          if (!extend && !range.empty)
            return EditorSelection.cursor(forward ? range.to : range.from);
          let step = view.moveVertically(range, forward);
          const here = view.lineBlockAt(range.head);
          const at = forward ? here.to + 1 : here.from - 1;
          const beside = at >= 0 && at <= doc.length ? view.lineBlockAt(at) : null;
          const passed = (block: BlockInfo) =>
            step.head < block.from || step.head > block.to;
          if (
            beside &&
            passed(here) &&
            passed(beside) &&
            step.goalColumn !== undefined
          ) {
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
      // A step that moves no caret leaves the press to the keys after this one, as Down
      // on the last line leaves a code block (`leaveCode`), though it would drop the goal
      // column a vertical step carries.
      if (
        moved.ranges.every(
          (range, at) =>
            range.anchor === selection.ranges[at]?.anchor &&
            range.head === selection.ranges[at].head,
        )
      )
        return false;
      view.dispatch({
        selection: moved,
        scrollIntoView: true,
        userEvent: "select",
      });
      return true;
    };
  const LINE_STEPS = [
    {
      key: "ArrowUp",
      run: lineStep(false, false),
      shift: lineStep(false, true),
    },
    {
      key: "ArrowDown",
      run: lineStep(true, false),
      shift: lineStep(true, true),
    },
  ];

  // Whether the field's words read as a message (`field.message()`), or as the Markdown
  // file a field editing a body in place shows (text-field.js, `facesOf`).
  const message = Facet.define({ combine: (values) => values.every(Boolean) });
  // The words as the renderer that will draw them reads them (`read`), in the field's
  // reading. Taken again when the words change or the renderer arrives. The preview,
  // Shift+Enter and the joints below read it from the state, where CodeMirror takes a
  // replacement across a line break.
  const readField = (state: EditorState) => ({
    placed: read(state, state.facet(message)),
    judged: markdownReady(),
  });
  const reading = StateField.define({
    create: readField,
    update: (value, tr) =>
      tr.docChanged || markdownReady() !== value.judged ? readField(tr.state) : value,
  });

  const container = (c: Placement): c is ContainerPlacement =>
    isBlockPlacement(c, "blockquote_open") || isBlockPlacement(c, "list_item_open");
  const item = (c: Placement | undefined): c is ItemPlacement =>
    c !== undefined && isBlockPlacement(c, "list_item_open");
  // Whether a quote or list item, as the renderer reads it, holds a line (`itemEnd`).
  // An item ends at its parsed end or before, so one ending earlier needs no reading of
  // its end, which scans the draft.
  const holding = (placed: PlacedTokens, line: Line) => (c: Placement) =>
    c.from <= line.from &&
    line.from < c.to &&
    (!item(c) || line.from < itemEnd(placed, c));
  const markerOn = (c: ContainerPlacement, l: Line) =>
    c.markers.find(([a]) => a >= l.from && a <= l.to);
  // Where the markers that open a line end.
  const opened = (l: Line, among: ContainerPlacement[]) =>
    Math.max(l.from, ...among.map((c) => markerOn(c, l)?.[1] ?? l.from));
  // A line a container holds without its marker carries the quote's `>`, or the item's
  // indent.
  const carried = (c: ContainerPlacement) =>
    isBlockPlacement(c, "blockquote_open") ? "> " : " ".repeat(c.token.lfSource.indent);

  // A field that edits a Markdown body in place reads its words as the body does, as a
  // file (lib/markdown.js, `paintMarkdown`), where a line break among a paragraph's words,
  // in a code span or a link's destination as anywhere else, is a space, and only a
  // hard break's is a line. Each such break, with the spaces ending its line and the
  // next line's markers and indent, stands as one space the caret steps over, and
  // deleting it joins the words, so a paragraph wrapped for a wider editor wraps to the
  // field as it does in the body. It is never revealed, since revealing it would rewrap
  // the paragraph under the caret.
  const joint = Decoration.replace({ widget: new Spelled(" ") });
  const jointsOf = (state: EditorState) => {
    if (state.facet(message)) return Decoration.none;
    const { placed } = state.field(reading);
    const inline = placed.filter(({ token }) => !token.block);
    const hard = inline.filter(({ token }) => token.type === "hardbreak");
    const containers = placed.filter(container);
    const breaks = new Set<number>();
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
          at - trailingIndentation(line.text),
          words + indentation(state.sliceDoc(words, next.to)),
        ),
      );
    }
    return Decoration.set(out);
  };
  const joints = StateField.define({
    create: jointsOf,
    update: (set, tr) =>
      tr.state.field(reading) === tr.startState.field(reading) &&
      tr.state.facet(message) === tr.startState.facet(message)
        ? set
        : jointsOf(tr.state),
    provide: (field) => [
      EditorView.decorations.from(field),
      EditorView.atomicRanges.of((view) => view.state.field(field)),
    ],
  });
  // The first line whose words all come after the last change: the line the change
  // ended in where it ended at that line's start, as Backspace at the start of a line
  // leaves it, and otherwise the line below; none where the change ended at the field's
  // end, as clearing or replacing all its words does, since no words follow. A line a
  // key takes away moves those words with the field's end edge, and the words before
  // them with its start edge, so an owner carrying the words splits its carry there
  // (text-field.js, `--lf-field-after`).
  const afterMark = Decoration.line({ attributes: { "data-lf-after": "" } });
  const afterChange = StateField.define({
    create: () => Decoration.none,
    update(lines, tr) {
      if (!tr.docChanged) return lines;
      let end = 0;
      tr.changes.iterChangedRanges((_fromA, _toA, _fromB, toB) => {
        end = Math.max(end, toB);
      });
      const { doc } = tr.state;
      if (end === doc.length) return Decoration.none;
      const line = doc.lineAt(end);
      if (end === line.from) return Decoration.set([afterMark.range(line.from)]);
      if (line.number === doc.lines) return Decoration.none;
      return Decoration.set([afterMark.range(line.to + 1)]);
    },
    provide: (field) => EditorView.decorations.from(field),
  });

  // Return in a field that reads as a file begins a line the body shows too, carrying
  // the markers of the containers the caret's line stands in. Among a paragraph's words
  // it writes a hard break, whose backslash the preview hides, in place of any joint the
  // selection touches, keeping the spaces beside it, so Backspace on the new line takes
  // the break and gives the words back as they stood (`deletionBefore`). At a hard
  // break it begins the line after it.
  // After a paragraph's last words, where a hard break would end its block and show its
  // backslash, it begins a new paragraph, and in a list item the next item
  // (`continueBlocks`). With none of a paragraph's words before the caret, in a
  // container it continues the container as Shift+Enter does, leaving it on a bare line,
  // and elsewhere, as after a heading, it is a plain line. At the start of a heading, a
  // rule, code, a table or an HTML block, or among the markup opening it, it opens a
  // paragraph above, the caret in it, outside a list item; among a rule's or a fence
  // line's marks it acts at the line's end. Among the markers opening a paragraph's
  // line it acts at the paragraph's words. Shift+Enter does the same here, since a line
  // it continued in a container would join the paragraph above.
  // A paragraph's words are what it shows. Where the caret has them on one side only,
  // with markup between, as after a bold first word's `**`, Return acts past that
  // markup, so the markup stays with its words, and Undo puts the caret back where it
  // stood. So it does where the caret stands at the start or end of a construct's words
  // among others, as before a code span's first letter, and inside code or a picture,
  // which no break may enter, it acts at the nearer end.
  function newLine(view: StateTarget): boolean {
    const { state } = view;
    if (state.readOnly) return false;
    if (state.facet(message)) return insertNewline(view);
    const { from, to } = state.selection.main;
    const { placed } = state.field(reading);
    // Return as though the caret stood at `at`.
    const actAt = (at: number): boolean =>
      newLine({
        state: state.update({ selection: { anchor: at } }).state,
        dispatch: (tr) =>
          view.dispatch(
            state.update({
              changes: tr.changes,
              selection: tr.newSelection,
              scrollIntoView: true,
              userEvent: "input",
            }),
          ),
      });
    const parts = lineParts(state, state.doc.lineAt(from));
    const { block } = parts;
    // On a line holding no words after a hard break, the break ends its paragraph and a
    // new one begins, as Return after a paragraph's last words does: a hard break with
    // no words after it would show as `\`.
    const broken = hardBreakBefore(state, parts.line);
    if (from === to && broken && !state.sliceDoc(parts.markers, parts.line.to).trim()) {
      const carry = parts.containers.map(carried).join("");
      const insert = `\n${carry.trimEnd()}\n${carry}`;
      view.dispatch(
        state.update(
          {
            changes: { from: broken.from, to: parts.line.to, insert },
            selection: { anchor: broken.from + insert.length },
          },
          { scrollIntoView: true, userEvent: "input" },
        ),
      );
      return true;
    }
    if (from === to && block && block.token.type !== "paragraph_open") {
      const opens = state.doc.lineAt(block.from).number === parts.line.number;
      if (
        opens &&
        parts.markers <= from &&
        from <= parts.words &&
        !parts.containers.some(item)
      ) {
        const carry = parts.containers.map(carried).join("");
        view.dispatch(
          state.update(
            {
              changes: {
                from: parts.markers,
                insert: `\n${carry.trimEnd()}\n${carry}`,
              },
              selection: { anchor: parts.markers },
            },
            { scrollIntoView: true, userEvent: "input" },
          ),
        );
        return true;
      }
      // A setext heading's underline is the heading's end wherever the caret stands in it.
      const setext = isBlockPlacement(block, "heading_open") && !opens;
      if (parts.marks && (setext || parts.words < from) && from < parts.line.to)
        return actAt(parts.line.to);
    }
    if (
      from === to &&
      block?.token.type === "paragraph_open" &&
      parts.first &&
      from < parts.words
    )
      return actAt(parts.words);
    const paragraph = placed.find(
      ({ token, from: a, to: b }) =>
        token.type === "paragraph_open" && a <= from && to <= b,
    );
    // A paragraph's or a heading's inline source, with a task's box, which opens its
    // item's line, left to the markers, and the spaces beside its words.
    const words =
      paragraph ??
      placed.find(
        ({ token, from: a, to: b }) =>
          token.type === "heading_open" && a <= from && to <= b,
      );
    const inline = words
      ? placed.filter(
          ({ token, from: a, to: b }) =>
            !token.block &&
            token.type !== "softbreak" &&
            token.type !== "html_inline" &&
            a >= words.from &&
            b <= words.to,
        )
      : [];
    const before = inline.some(
      ({ from: a, to: b }) =>
        a < from && /\S/.test(state.sliceDoc(a, Math.min(b, from))),
    );
    const after = inline.some(
      ({ from: a, to: b }) => b > to && /\S/.test(state.sliceDoc(Math.max(a, to), b)),
    );
    if (from === to && (before || after)) {
      // A delimiter the parser kept as text, as each `*` of `**`, shows nothing, and
      // code shows what stands between its backticks (`shownSpan`).
      const shown = inline.flatMap((c) =>
        c.token.nesting !== 0 ||
        c.token.type === "hardbreak" ||
        (c.token.content === "" && c.token.type !== "image")
          ? []
          : [shownSpan(state, c)],
      );
      const shownBefore = shown.some(
        ([a, b]) => a < from && /\S/.test(state.sliceDoc(a, Math.min(b, from))),
      );
      const shownAfter = shown.some(
        ([a, b]) => b > to && /\S/.test(state.sliceDoc(Math.max(a, to), b)),
      );
      let edge =
        before && !shownBefore && shownAfter
          ? Math.min(...inline.map(({ from: a }) => a))
          : after && shownBefore && !shownAfter
            ? Math.max(...inline.map(({ to: b }) => b))
            : from;
      // Among words on both sides, at the start of a construct's words or among the
      // markup opening them, the break goes before the construct, and at their end
      // after it, the innermost first. A heading's break parts it into two blocks,
      // which no construct spans, so there, as inside code or a picture anywhere, a break
      // among its words goes to the end they stand nearer.
      const constructs = inline.flatMap((c) => constructsOf(state, c));
      const parting = words?.token.type === "heading_open";
      for (let moved = edge === from; moved;) {
        moved = false;
        for (const [start, end, a, b, sealed] of constructs) {
          const out =
            start < edge && edge <= a
              ? start
              : b <= edge && edge < end
                ? end
                : (sealed || parting) && a < edge && edge < b
                  ? edge - a <= b - edge
                    ? start
                    : end
                  : edge;
          moved ||= out !== edge;
          edge = out;
        }
      }
      if (edge !== from) return actAt(edge);
    }
    const line = state.doc.lineAt(from);
    const holds = holding(placed, line);
    const containers = placed.filter(container).filter(holds);
    const inner = containers.at(-1);
    // On a blank line between blocks it leaves the caret on a blank line with a blank
    // line on each side, where the next words make a paragraph of their own: words on
    // a line beside a paragraph would join it.
    const blankLine = (n: number) => /^[ \t]*$/.test(state.doc.line(n).text);
    const inCode = placed.some(
      ({ token, from: a, to: b }) => isCode(token) && a <= line.from && line.from < b,
    );
    // Before a paragraph's first words it opens a paragraph above, the caret in it, as
    // after its last words it opens one below.
    if (from === to && !inner && paragraph && !before && after) {
      view.dispatch(
        state.update(
          { changes: { from, insert: "\n\n" }, selection: { anchor: from } },
          { scrollIntoView: true, userEvent: "input" },
        ),
      );
      return true;
    }
    if (from === to && !inner && !inCode && blankLine(line.number)) {
      const above = line.number > 1 && !blankLine(line.number - 1);
      const below = line.number < state.doc.lines && !blankLine(line.number + 1);
      const insert = above && below ? "\n\n" : "\n";
      const anchor = !above && below ? from : from + 1;
      view.dispatch(
        state.update(
          { changes: { from, insert }, selection: { anchor } },
          { scrollIntoView: true, userEvent: "input" },
        ),
      );
      return true;
    }
    if (inner && (!before || (!after && item(inner))) && continueBlocks(view, true))
      return true;
    // Inside a heading's words the words after the break leave it, a paragraph below it,
    // past a setext heading's underline, which stays with the words before; after them,
    // Return acts below the underline, or past a heading's closing `#`s.
    const heading =
      block && isBlockPlacement(block, "heading_open") ? block : undefined;
    const underline = heading?.markers.find(([a]) => a > line.to);
    if (heading && from === to && from >= parts.end && (underline || from < line.to))
      return actAt(underline ? state.doc.lineAt(underline[0]).to : line.to);
    const prefix = containers.map(carried).join("");
    if (heading && from === to && from > parts.words) {
      // A heading's closing `#`s stay with it.
      const close = underline ? state.doc.lineAt(underline[0]) : line;
      const end = underline ? close.from - 1 : Math.max(from, parts.end);
      const rest = state.sliceDoc(from, end);
      const words = rest.slice(indentation(rest));
      const opens = close.to - (end - from) + 1;
      const start = opens + prefix.length;
      const moved = state.changes([
        { from, to: end },
        { from: close.to, insert: `\n${prefix}${words}` },
      ]);
      // The words open a paragraph of their own below the heading, with a blank line
      // after them where the line below would otherwise take them in (`keeps`). Where
      // neither reads as before, as where the words left in the heading would read as
      // a table's header row over its underline, Return changes nothing.
      const changes =
        escapedWhere(state, moved, start)?.changes ??
        escapedWhere(
          state,
          moved.compose(
            ChangeSet.of(
              {
                from: moved.mapPos(close.to, 1),
                insert: `\n${prefix.trimEnd()}`,
              },
              moved.newLength,
            ),
          ),
          start,
        )?.changes;
      if (!changes) return true;
      view.dispatch(
        state.update(
          { changes, selection: { anchor: start } },
          { scrollIntoView: true, userEvent: "input" },
        ),
      );
      return true;
    }
    if (!before) return insertNewline(view);
    let spec;
    if (after) {
      let [a, b] = [from, to];
      // A joint shows as a space, which stays before the break.
      let space = "";
      state.field(joints).between(a, b, (jointFrom, jointTo) => {
        a = Math.min(a, jointFrom);
        b = Math.max(b, jointTo);
        space = " ";
      });
      // A hard break, with the spaces before it, is a line already: one the range starts
      // inside goes with the range, and one where it ends stays, the new line after it.
      const breaks = placed
        .filter(({ token }) => token.type === "hardbreak")
        .map(({ from: at, to: end }): [number, number] => [
          at - trailingIndentation(state.sliceDoc(state.doc.lineAt(at).from, at)),
          end,
        ]);
      a = breaks.find(([at, end]) => at < a && a < end)?.[0] ?? a;
      const hard = breaks.find(([at, end]) => at <= b && b <= end);
      // The break is the first of `BREAKS` the whole draft reads as one, and the draft
      // reads as before around it (`keeps`): words it leaves at a line's start that
      // would open a block there, as a list's marker, a `#` or a table's row does, keep
      // reading as words, their first mark escaped. Where no break does, Return changes
      // nothing.
      const rest = hard ? hard[1] : b;
      const broken = (mark: string) => {
        const insert = `${space}${mark}\n${prefix}`;
        return state.changes(
          hard
            ? [
                { from: Math.min(a, hard[0]), to: hard[0] },
                { from: hard[1], insert },
              ]
            : { from: a, to: b, insert },
        );
      };
      for (const mark of BREAKS) {
        const changes = broken(mark);
        const anchor = changes.mapPos(rest, 1);
        const made = escapedWhere(state, changes, anchor, "", (read) =>
          breaksAt(read, anchor - prefix.length - 1),
        );
        if (made) {
          spec = { changes: made.changes, selection: { anchor } };
          break;
        }
      }
      if (!spec) return true;
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
      declare live: boolean;
      declare read: { placed: PlacedToken[]; judged: boolean };
      declare drawn: {
        decorations: DecorationSet;
        runs: DecorationSet;
        boxes: RangeSet<BlockWrapper>;
      };

      constructor(view: EditorView) {
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
      update(update: ViewUpdate) {
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
  // CodeMirror's Markdown continuation, whose grammar, a second
  // beside the renderer's, read the whole draft again on every key, ended a quote or
  // item at a fence inside it, and took three presses to leave a list.
  const CHECKBOX = "[ ] ";
  function continueBlocks(view: StateTarget, nextItem: boolean = false) {
    const { state } = view;
    const { placed } = state.field(reading);
    const { from, to } = state.selection.main;
    const line = state.doc.lineAt(from);
    const all = placed.filter(container);
    const holds = holding(placed, line);
    const containers = all.filter(holds);
    const inner = containers.at(-1);
    if (!inner) return false;
    const code = placed.some((c) => isCode(c.token) && holds(c));
    // A line holding nothing past its markers is bare.
    const bare = (l: Line) => {
      const rest = state.sliceDoc(opened(l, all), l.to).trim();
      return !rest || `${rest} ` === CHECKBOX;
    };
    if (from < opened(line, containers)) return false;
    const task = ({ token }: ContainerPlacement) =>
      String(token.attrGet("class")).split(" ").includes("task-list-item");
    const next = (c: ContainerPlacement) =>
      `${c.token.info && Number(c.token.info) + 1}${c.token.markup} ${task(c) ? CHECKBOX : ""}`;
    const outside = containers.slice(0, -1);
    let change;
    let before: { from: number; insert: string } | null = null;
    let cut: { from: number; to: number } | null = null;
    if (!code && to <= line.to && bare(line)) {
      const parent = outside.at(-1);
      const outdent = item(inner) && item(parent);
      const around = outdent ? outside.slice(0, -1) : outside;
      // What a line keeps of its markers for the containers it stays in.
      const kept = (l: Line) => {
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
      // At a task's words its box goes with them, and the item opened above is plain:
      // an empty task item shows its brackets. Words selected there go.
      const box = placed.find(
        ({ token, from: a, to: b }) =>
          token.type === "html_inline" &&
          b <= from &&
          !state.sliceDoc(opened(line, containers), a).trim() &&
          !state.sliceDoc(b, from).trim(),
      );
      const moves = box !== undefined && marker !== carried(inner);
      const insert = `\n${outside.map(carried).join("")}${moves ? marker.replace(CHECKBOX, "") : marker}`;
      change = moves ? { from: box.from, to: box.from, insert } : { from, to, insert };
      if (moves && from < to) cut = { from, to };
      // An empty first item can't interrupt a paragraph, which would read its marker
      // as words, so a list that follows one directly takes a blank line first.
      const paragraphAbove =
        line.number > 1 &&
        placed.some(
          ({ token, from: a, to: b }) =>
            token.type === "paragraph_open" &&
            a < line.from &&
            line.from <= b &&
            !holds({ token, from: a, to: b }),
        );
      if (
        marker !== carried(inner) &&
        paragraphAbove &&
        placed.some((c) => LIST.test(c.token.type) && c.from === line.from) &&
        !state.sliceDoc(opened(line, containers), change.from).trim()
      )
        before = {
          from: line.from,
          insert: `${outside.map(carried).join("").trimEnd()}\n`,
        };
    }
    if (!cut && state.sliceDoc(change.from, change.to) === change.insert) return false;
    const changes = state.changes([before, change, cut].filter((c) => c !== null));
    view.dispatch(
      state.update({
        changes,
        selection: { anchor: changes.mapPos(to, 1) },
        scrollIntoView: true,
        userEvent: "input",
      }),
    );
    return true;
  }

  // What begins a line below the one holding `at` in the quotes and list items that
  // line stands in, as the preview reads the draft, or null where `at` stands before
  // their markers end.
  function beginBelow(state: EditorState, at: number) {
    const { placed } = state.field(reading);
    const line = state.doc.lineAt(at);
    const containers = placed.filter(container).filter(holding(placed, line));
    if (at < opened(line, containers)) return null;
    return `\n${containers.map(carried).join("")}`;
  }

  // The code block, fenced or indented, that the line holding `at` stands in, as the
  // preview reads the draft, and which of its fence's lines that line is, or null where
  // no code holds it.
  function codeAt(state: EditorState, at: number) {
    const { placed } = state.field(reading);
    const line = state.doc.lineAt(at);
    const holds = holding(placed, line);
    const fence = placed.find((c) => isCode(c.token) && holds(c));
    if (!fence) return null;
    const markers = fence.markers ?? [];
    const [opening, closing] = markers.map(([a]) => a >= line.from && a <= line.to);
    const containers = placed.filter(container).filter(holds);
    return {
      line,
      fence,
      opening,
      closing,
      // No marks close it, and this line is the last it holds.
      open: markers.length < 2 && line.to + 1 >= fence.to,
      begin: beginBelow(state, line.to) ?? "\n",
      // The words on a line up to `to`, past its containers' markers.
      words: (l: Line, to: number = l.to) =>
        state.sliceDoc(opened(l, containers), to).trim(),
    };
  }

  // Down from the draft's last line begins a line below the code block that holds it, in
  // place of the blank lines ending its code: after the closing marks an open fence
  // lacks, or after a blank line that ends an indented block's code, whose indent the
  // preview hides and Return carries outside a quote or list item. Nothing else reaches
  // a line below code the draft ends with. Rich editors leave a code block the same way.
  function leaveCode(view: EditorView) {
    const { state } = view;
    const { main } = state.selection;
    const at = main.empty ? codeAt(state, main.head) : null;
    if (!at || state.readOnly) return false;
    const { line, fence, closing, begin, words } = at;
    let last = line;
    while (!closing && !words(last) && last.number > 1)
      last = state.doc.line(last.number - 1);
    const change = closing
      ? { from: line.to, insert: begin }
      : {
          from: last.to,
          to: line.to,
          insert: begin + fence.token.markup + begin,
        };
    view.dispatch(
      state.update({
        changes: change,
        selection: { anchor: change.from + change.insert.length },
        scrollIntoView: true,
        userEvent: "input",
        annotations: isolateHistory.of("full"),
      }),
    );
    return true;
  }

  // The source an inline token's words show from and to: a code span's between the
  // padding its reading strips, and a text's past the backslash of an escape opening it.
  function shownSpan(state: EditorState, c: Placement): [number, number] {
    const { token } = c;
    if (token.type === "code_inline") {
      const at = state
        .sliceDoc(c.from, c.to)
        .indexOf(token.content, token.markup.length);
      const start = c.from + (at < 0 ? token.markup.length : at);
      return [
        start,
        at < 0 ? c.to - token.markup.length : start + token.content.length,
      ];
    }
    if (token.nesting === 1) return c.content ?? [c.from, c.from];
    const [escape] = c.spelled ?? [];
    if (
      escape?.[0] === c.from &&
      state.sliceDoc(escape[0], escape[1]).endsWith(escape[2])
    )
      return [escape[1] - escape[2].length, c.to];
    return [c.from, c.to];
  }
  // The constructs an inline token's source holds, each as its start and end, the start
  // and end of the words it shows, and whether no line break may stand inside it: an
  // emphasis or a link, a code span or a picture, which may not, and each escape or
  // entity in a text, which shows one character for several, its first.
  function constructsOf(
    state: EditorState,
    c: Placement,
  ): [number, number, number, number, boolean][] {
    if (c.token.nesting === 1) return [[c.from, c.to, ...shownSpan(state, c), false]];
    if (c.token.type === "code_inline" || c.token.type === "image")
      return [[c.from, c.to, ...shownSpan(state, c), true]];
    return (c.spelled ?? []).map(([a, b, shown]) =>
      state.sliceDoc(a, b).endsWith(shown)
        ? [a, b, b - shown.length, b, false]
        : [a, b, a, a + 1, false],
    );
  }

  // Whether the draft `changes` leave reads as before, apart from what the edit means to
  // change: the check every edit a key makes at the edge of a line's shown words passes
  // (`deleteAtEdge`, `escapedWhere`). A key proposes its candidate edits in order, and
  // the first that passes is made.
  // - The blocks beside the lines the changes touch read as they did: each block ending
  //   above the first of them, a list, quote or item as much as a paragraph, keeps its
  //   kind, depth and lines, and each ending below the last still ends there, of the
  //   same kind and depth. One starting below them keeps its start too, unless it is
  //   what is left of a block that held part of those lines, as the paragraph's lines
  //   after one that Delete joins to a heading above.
  // - The draft shows no character it didn't, except those the user put, `typed`, and
  //   those they spell, as `©` for `&copy;`.
  // - It shows each character it showed, except those the changes take from the source
  //   and don't put back, and except those typing hides, as a `)` typed after
  //   `[link](url` makes a link of them.
  // So an edit never turns markup into words, as a hard break left at a paragraph's end
  // shows as `\`, never takes a word, and never changes a block beyond the lines it
  // edits, as words that a paragraph above would take in, a `---` that the words above
  // would make a heading's underline, or two lists that a line between them kept apart.
  // A block's end past the draft's, where it takes in the word a bare last line is read
  // as holding (`read`), counts as the draft's end. Characters are counted, not matched
  // to their places in the source, so an edit that hides one `#` and shows another
  // passes, as Backspace at `# ▏# T` does.
  function keeps(state: EditorState, changes: Changes, typed: string = "") {
    const doc = changes.apply(state.doc);
    const source = doc.toString();
    const inMessage = state.facet(message);
    let [startA, endA, startB, endB] = [Infinity, -1, Infinity, -1];
    let [taken, put] = ["", ""];
    changes.iterChanges((fromA, toA, fromB, toB, inserted) => {
      [startA, endA] = [Math.min(startA, fromA), Math.max(endA, toA)];
      [startB, endB] = [Math.min(startB, fromB), Math.max(endB, toB)];
      taken += state.sliceDoc(fromA, toA);
      put += inserted.toString();
    });
    if (endA < 0) return true;
    // Each block beside the lines from `from` to `to`, as its kind, depth and end, and
    // its start where it starts outside them: those ending above, those starting below,
    // and those starting among them or above and ending below.
    const beside = (
      placed: Placement[],
      text: Text,
      from: number,
      to: number,
      place: (at: number) => number,
    ) => {
      const [first, last] = [text.lineAt(from).from, text.lineAt(to).to];
      const above: string[] = [];
      const below: string[] = [];
      const ends: string[] = [];
      for (const { token, from: a, to } of placed) {
        if (!(LEAF.test(token.type) || CONTAINER.test(token.type)) || a >= text.length)
          continue;
        // A list or quote ends at its last line that holds anything, though the parser
        // gives it the blank lines after.
        let b = to;
        while (b <= text.length && b > a + 1 && !text.lineAt(b - 1).text.trim())
          b = text.lineAt(b - 1).from;
        const kind = `${token.type} ${token.level} ${place(Math.min(b, text.length))}`;
        if (b <= first) above.push(`${kind} ${a}`);
        else if (b > last + 1 && a > last) below.push(`${kind} ${place(a)}`);
        else if (b > last + 1) ends.push(kind);
      }
      return { above: above.join(), below, ends };
    };
    const was = beside(state.field(reading).placed, state.doc, startA, endA, (at) =>
      at > endA ? changes.mapPos(at) : at,
    );
    const is = beside(readSource(source, inMessage), doc, startB, endB, (at) => at);
    if (was.above !== is.above) return false;
    const take = (list: string[], entry: string) => {
      const at = list.indexOf(entry);
      return at >= 0 && list.splice(at, 1).length > 0;
    };
    // A block starting below that didn't is what is left of one that ended there.
    for (const entry of is.below)
      if (
        !take(was.below, entry) &&
        !take(was.ends, entry.slice(0, entry.lastIndexOf(" ")))
      )
        return false;
    for (const entry of is.ends) if (!take(was.ends, entry)) return false;
    if (was.below.length || was.ends.length) return false;
    const before = shownCharacters(state.doc.toString(), inMessage);
    const after = shownCharacters(source, inMessage);
    // The characters of source text and those it shows, as `©` for `&copy;`.
    const spelled = (text: string) => {
      const counts = counted(text);
      for (const [ch, n] of counted(markdownWords(text, inMessage)))
        counts.set(ch, Math.max(n, counts.get(ch) ?? 0));
      return counts;
    };
    const own = spelled(typed);
    for (const [ch, n] of after)
      if (n - (before.get(ch) ?? 0) > (own.get(ch) ?? 0)) return false;
    if (typed) return true;
    const gone = spelled(taken);
    const added = counted(put);
    for (const [ch, n] of before)
      if (
        n - (after.get(ch) ?? 0) >
        Math.max(0, (gone.get(ch) ?? 0) - (added.get(ch) ?? 0))
      )
        return false;
    return true;
  }

  // `changes`, or the same with a backslash before the first mark of the words that
  // start at `start` in the changed draft, whichever the draft reads as before under
  // (`keeps`, with `typed`) and `means` holds of, read whole, with where the backslash
  // goes in the changed draft; null where neither is. The backslash goes before the
  // mark of the block the words would open, as the `.` of `1.` or the `|` of a table's
  // row.
  function escapedWhere(
    state: EditorState,
    changes: Changes,
    start: number,
    typed: string = "",
    means: (placed: Placement[], changes: Changes) => boolean = () => true,
  ): { changes: Changes; escape: number | null } | null {
    const holds = (c: Changes) =>
      means(readSource(c.apply(state.doc).toString(), state.facet(message)), c) &&
      keeps(state, c, typed);
    if (holds(changes)) return { changes, escape: null };
    const doc = changes.apply(state.doc);
    const mark = firstMark(doc.sliceString(start, doc.lineAt(start).to));
    if (mark === null) return null;
    const escaped = changes.compose(
      ChangeSet.of({ from: start + mark, insert: "\\" }, changes.newLength),
    );
    return holds(escaped) ? { changes: escaped, escape: start + mark } : null;
  }

  // Where in `words` the first mark stands that could open a block, past a list's
  // number, or null.
  const firstMark = (words: string) => {
    const mark = /^[ \t]*\d*[!-/:-@[-`{-~]/.exec(words);
    return mark ? mark[0].length - 1 : null;
  };

  // The ways to write a hard break, in the order an edit tries them against the whole
  // draft: a backslash; one more, where a backslash ending the words before it would
  // escape the break's; and a space first, where a link's address would take both.
  const BREAKS = ["\\", "\\\\", " \\"];
  // Whether the reading `read` breaks the line at the line break at `at`.
  const breaksAt = (read: Placement[], at: number) =>
    read.some(
      ({ token, from: a, to: b }) => token.type === "hardbreak" && a < at && at < b,
    );

  // Keys at the edge of a line's shown words act on what the field shows there: a
  // block, its marker and the lines around it, never the source characters the preview
  // hides or dims beside the words one at a time, which a key would otherwise turn into
  // words (`#Title`, `-second item`, a stray `\`). Inline markup the preview shows at
  // the caret, as a revealed `**`, is edited as the characters it is.
  // - Backspace at the start of a block's words takes the marker opening the block, the
  //   innermost first: a heading's `#` (a setext heading's underline), a task's box, an
  //   item's marker, a quote's `>` with the rest of its first paragraph's, which leaves
  //   the quote whole (`unwrap`). With no marker left it joins the block to the one
  //   before, after taking one at a time the blank lines the field draws as lines.
  //   Delete at the end of a block's words does the same to the block after it, the
  //   blank lines first. On a blank line between blocks, either key takes the line where
  //   the blocks around it read the same without it (`keeps`).
  // - Inside a block, a line break goes with the markup carrying it: a hard break's
  //   backslash and the next line's markers, so Backspace after Return gives back the
  //   words as they stood, and a file's soft break with the joint that stands for it
  //   (`joints`). A hard break left with no words after it goes too, since it would
  //   show as `\`.
  // - Code, a rule, a table and an HTML block are never joined to another block, and a
  //   fence's lines stay whole, so Backspace at the start of code keeps its fence.
  // - A line holding nothing past its markers, as a new item does, goes whole.
  // These rules propose each key's edits; the edit made is the first the draft reads as
  // before under (`keeps`), and where none does the key changes nothing.
  // Return (`newLine`) and Home take the same reading of the line, and words typed on a
  // line that held none stand apart from the lines beside it (`gapAround`). Rejected:
  // making hidden markup one of CodeMirror's atomic ranges, as a file's joints are. The
  // preview shows a heading's `# ` and a hard break's `\` dimmed while the caret stands
  // beside them, so no range hidden there would hold them, and CodeMirror's motion skips
  // an atomic range, so the caret could no longer reach an item's marker to change it.
  const LEAF =
    /^(?:paragraph_open|heading_open|fence|code_block|hr|table_open|html_block)$/;
  const whole = (c: Placement) =>
    c.token.type !== "paragraph_open" && c.token.type !== "heading_open";
  type Edit = { from: number; to?: number; insert?: string };

  // Where a code block's line shows its code from, past its containers' markers and the
  // indent the code's reading drops (`decorate`), and whether it is the code's first or
  // last line; null for a fence's own line.
  function codeLine(
    state: EditorState,
    c: Placement,
    l: Line,
    containers: ContainerPlacement[],
  ) {
    const markers = c.markers ?? [];
    const { body, opening, inline, first } = codeRows(state, c);
    const kept = body[l.number - first];
    if (kept === undefined) return null;
    const start =
      inline && l.number === opening.number
        ? (markers[0]?.[1] ?? l.from)
        : opened(l, containers);
    const lead = indentation(state.sliceDoc(start, l.to));
    return {
      words: start + lead - Math.min(lead, indentation(kept)),
      first: l.number === first,
      last: l.number === first + body.length - 1,
    };
  }

  // What a line holds as the field draws it: the quotes and list items holding it and
  // where their markers end, the leaf block it stands in and whether that block starts
  // on it, the innermost marker opening a block that starts on it, and where its shown
  // words start and end. A line holding only its block's marks, as a fence's does, is
  // marks, and a line in a container holding nothing past its markers is bare.
  function lineParts(state: EditorState, line: Line) {
    const { placed } = state.field(reading);
    const containers = placed.filter(container).filter(holding(placed, line));
    const block = placed.find(
      (c) => LEAF.test(c.token.type) && c.from <= line.from && line.from < c.to,
    );
    const markers = opened(line, containers);
    const code =
      block && isCode(block.token) ? codeLine(state, block, line, containers) : null;
    const startsHere = (c: Placement) =>
      state.doc.lineAt(c.from).number === line.number;
    let own = null as [number, number] | null;
    const consider = (range: [number, number] | undefined) => {
      if (range && (!own || range[0] > own[0])) own = range;
    };
    for (const c of containers) if (startsHere(c)) consider(markerOn(c, line));
    const first = Boolean(block && (code ? code.first : startsHere(block)));
    // A heading's `#` opens its line. A setext heading's underline is a line of marks,
    // the marker that opens the heading though it stands below its words.
    const heading = block && isBlockPlacement(block, "heading_open") ? block : null;
    const marked = heading?.markers.find(([a]) => a >= line.from && a <= line.to);
    if (marked && first) consider(marked);
    let words = Math.max(markers, own?.[1] ?? line.from);
    words += indentation(state.sliceDoc(words, line.to));
    if (heading && first && !marked) consider(heading.markers[0]);
    // A task's box opens the words of the item it starts.
    const box = placed.find(
      ({ token, from, to }) =>
        token.type === "html_inline" && from === words && to <= line.to,
    );
    if (box && containers.some((c) => item(c) && startsHere(c))) {
      consider([box.from, box.to]);
      words = box.to + indentation(state.sliceDoc(box.to, line.to));
    }
    if (code) words = code.words;
    // A hard break's backslash and a heading's closing marks end the line's words.
    let end = line.to;
    if (!code) {
      for (const { token, from } of placed)
        if (token.type === "hardbreak" && from >= words && from <= line.to)
          end = Math.min(end, from);
      const close = first ? heading?.markers[1] : null;
      if (close && close[0] < close[1] && close[0] >= words)
        end = Math.min(end, close[0]);
      end = Math.max(words, end - trailingIndentation(state.sliceDoc(words, end)));
    }
    return {
      line,
      containers,
      markers,
      block,
      first,
      own,
      words,
      end,
      code,
      // A line holding only its block's marks: a fence's, a rule's, a setext underline.
      marks: Boolean(
        block &&
        ((isCode(block.token) && !code) ||
          block.token.type === "hr" ||
          (marked && !first)),
      ),
      bare: containers.length > 0 && !state.sliceDoc(markers, line.to).trim(),
    };
  }
  type LineParts = ReturnType<typeof lineParts>;

  // The hard break ending the line above `line`, from its backslash, or the spaces
  // that make one, into `line`.
  const hardBreakBefore = (state: EditorState, line: Line) =>
    state
      .field(reading)
      .placed.find(
        ({ token, from, to }) =>
          token.type === "hardbreak" && from < line.from && to >= line.from,
      );

  // A block's opening marker goes: a heading's `#` with its closing marks, and a quote's
  // `>` with those of each line of the block's first paragraph and of the blank line
  // after it, so the paragraph leaves the quote whole and the blank line parts it from
  // what stays quoted. A setext heading's underline goes with its line. A line the
  // paragraph above would then take in as its own words (`keeps`) stands apart from it:
  // an item's after a hard break, on a line of its own in the item above, as a rich
  // editor keeps a line whose bullet goes in its list; any other, and an item's where
  // no break the whole draft reads as one fits, after a blank line. Where none of these
  // keeps the draft, as for an item's words that would read as a rule, the marker
  // stays.
  function unwrap(
    state: EditorState,
    parts: LineParts & { own: [number, number] },
  ): Edit[][] {
    const { line, own, block, containers } = parts;
    const [from] = own;
    if (from > line.to) {
      const underline = state.doc.lineAt(from);
      return [[{ from: underline.from - 1, to: underline.to }]];
    }
    const heading = block && isBlockPlacement(block, "heading_open") ? block : null;
    const owner = containers.find((c) => markerOn(c, line)?.[0] === from);
    const changes: Edit[] = [{ from, to: parts.words }];
    const close =
      heading && own === heading.markers[0] ? heading.markers[1] : undefined;
    if (close && close[0] < close[1])
      changes.push({ from: parts.end, to: Math.max(parts.end, close[1]) });
    if (owner && isBlockPlacement(owner, "blockquote_open") && block) {
      const last = lastLine(state, block);
      for (let n = line.number + 1; n <= Math.min(last + 1, state.doc.lines); n++) {
        const l = state.doc.line(n);
        const mark = markerOn(owner, l);
        if (!mark) continue;
        if (n > last && state.sliceDoc(mark[1], l.to).trim()) break;
        changes.push({ from: mark[0], to: mark[1] });
      }
    }
    const carry = containers
      .filter((c) => c !== owner)
      .map(carried)
      .join("")
      .trimEnd();
    const apart = [changes, [...changes, { from: line.from, insert: `${carry}\n` }]];
    const above =
      line.number > 1 ? lineParts(state, state.doc.line(line.number - 1)) : null;
    if (
      !owner ||
      !item(owner) ||
      above?.block?.token.type !== "paragraph_open" ||
      hardBreakBefore(state, line) ||
      !above.containers.some((c) => item(c) && c !== owner && c.from !== owner.from)
    )
      return apart;
    const broken = BREAKS.map((mark) => [
      ...changes,
      { from: above.end, to: above.line.to, insert: mark },
    ]).find((edits) => {
      const made = state.changes(edits);
      const read = readSource(made.apply(state.doc).toString(), state.facet(message));
      return breaksAt(read, made.mapPos(above.line.to, 1)) && keeps(state, made);
    });
    return broken ? [broken, ...apart] : apart;
  }

  // Where taking `line` away starts: at the line break before it, and where that break
  // is a hard one, at its backslash, and at the breaks of the lines above it that hold
  // nothing else, since a hard break with no words after it shows as `\`.
  function brokenFrom(state: EditorState, line: Line) {
    let from = line.from - 1;
    for (let l = line, hard = hardBreakBefore(state, l); hard;) {
      from = hard.from;
      l = state.doc.lineAt(hard.from);
      const before = state.sliceDoc(
        opened(l, lineParts(state, l).containers),
        hard.from,
      );
      hard = before.trim() ? undefined : hardBreakBefore(state, l);
    }
    return from;
  }

  // The joint, in a file's reading, that stands for the line break before `line`
  // (`joints`), whose space a key takes whole; null in a message's.
  function jointBefore(state: EditorState, line: Line) {
    let found = null as { from: number; to: number } | null;
    state.field(joints).between(line.from - 1, line.from, (from, to) => {
      if (from < line.from && to >= line.from) found = { from, to };
    });
    return found;
  }

  // The lines next to `line`, upward or downward, past those the field shows blank: the
  // first that holds anything, null at the draft's end, and how many blank lines stand
  // between.
  function nextHolding(state: EditorState, line: Line, forward: boolean) {
    const blank = blankLines(state.doc, state.field(reading).placed);
    const step = forward ? 1 : -1;
    let n = line.number + step;
    while (n >= 1 && n <= state.doc.lines && blank(n)) n += step;
    const held = n >= 1 && n <= state.doc.lines ? state.doc.line(n) : null;
    return { held, between: Math.abs(n - line.number) - 1 };
  }

  // How many blank lines between two blocks the field draws as the gap between them
  // rather than as lines: one in a file, where the gap stands for it, and none in a
  // message, which shows each.
  const gapLines = (state: EditorState) => (state.facet(message) ? 0 : 1);

  // What Backspace at `at` takes (above): the edits it would make, in the order tried,
  // of which the first the draft reads as before under is made (`keeps`), and none where
  // none is; true where it takes nothing, and false where CodeMirror's own deletion acts.
  function deletionBefore(state: EditorState, at: number): Edit[][] | boolean {
    const line = state.doc.lineAt(at);
    const parts = lineParts(state, line);
    if (parts.bare)
      return lineGone(line, {
        from: line.number > 1 ? brokenFrom(state, line) : line.from,
        to: line.to,
      });
    const { block, own, words } = parts;
    // A blank line of a file goes whole where the blocks around it read as they did
    // without it, and otherwise stays, as between a paragraph and the `---` that would
    // make it a heading.
    if (!block && !line.text.trim() && !state.facet(message) && line.number > 1)
      return [[{ from: line.from - 1, to: line.to }]];
    if (!block) return false;
    if (!parts.first) {
      const hard = hardBreakBefore(state, line);
      // A hard break with no words after it ends its block and shows as `\`, so the
      // last character after it goes with it, and the line after joins the one before.
      if (hard && at === parts.end && [...state.sliceDoc(words, at)].length === 1)
        return [[{ from: brokenFrom(state, line), to: at }]];
      if (at > words) return false;
      if (parts.code) return [[{ from: line.from - 1, to: words }]];
      if (parts.marks) return true;
      // A table's and an HTML block's lines show their source at the caret, which keys
      // edit as characters.
      if (whole(block)) return false;
      if (hard) return [[{ from: hard.from, to: parts.markers }]];
      return [[jointBefore(state, line) ?? { from: line.from - 1, to: parts.markers }]];
    }
    if (at > words) return false;
    if (own) return unwrap(state, { ...parts, own });
    if (whole(block)) return true;
    const { held, between } = nextHolding(state, line, false);
    if (!held) return false;
    // The blank line above goes, from the end of the block before, which it joins in a
    // message, which shows each blank line.
    if (between > gapLines(state)) {
      const blank = state.doc.line(line.number - 1);
      return [
        [{ from: held.to, to: line.from, insert: state.sliceDoc(held.to, blank.from) }],
      ];
    }
    return joined(state, lineParts(state, held), words);
  }

  // The block ending on the line `prior` holds, joined by the words starting at `words`:
  // they follow its last word. An item or quote line holding none goes whole instead,
  // with the blank lines after it, and the words keep their own block. True where it is
  // a block never joined, one whose last line is its marks, as a setext heading's
  // underline, or source the field draws as typed, as a link's definition.
  function joined(
    state: EditorState,
    prior: LineParts,
    words: number,
  ): Edit[][] | boolean {
    if (prior.block)
      return (
        whole(prior.block) ||
        prior.marks || [
          [{ from: prior.end, to: words }, ...intoHeading(state, prior, words)],
        ]
      );
    if (!prior.bare) return true;
    return lineGone(prior.line, {
      from: prior.line.from,
      to: state.doc.lineAt(words).from,
    });
  }

  // Takes a line holding nothing past its markers by `change`, which removes it whole,
  // or, where the blocks beside it would then read as one, as a paragraph and the `---`
  // under it would, leaves it blank (`keeps`).
  const lineGone = (line: Line, change: Edit): Edit[][] => [
    [change],
    [{ from: line.from, to: line.to }],
  ];

  // A heading holds one line, so words joining it from a line that ends in a hard break
  // leave that break, which would show as `\` at the heading's end, and the lines after
  // stand below it as a paragraph.
  function intoHeading(state: EditorState, prior: LineParts, words: number) {
    if (!prior.block || !isBlockPlacement(prior.block, "heading_open")) return [];
    const line = state.doc.lineAt(words);
    const hard = state
      .field(reading)
      .placed.find(
        ({ token, from }) =>
          token.type === "hardbreak" && from >= words && from <= line.to,
      );
    return hard ? [{ from: hard.from, to: line.to }] : [];
  }

  // The number of the last line a block holds: the draft's last where the block takes in
  // the word the field reads a bare last line as holding (`read`).
  const lastLine = (state: EditorState, block: Placement) =>
    block.to > state.doc.length
      ? state.doc.lines
      : state.doc.lineAt(Math.max(block.from, block.to - 1)).number;

  // What Delete at `at` takes, as `deletionBefore` says.
  function deletionAfter(state: EditorState, at: number): Edit[][] | boolean {
    const line = state.doc.lineAt(at);
    const parts = lineParts(state, line);
    const below =
      line.number < state.doc.lines ? state.doc.line(line.number + 1) : null;
    if (parts.bare)
      return below !== null && lineGone(line, { from: line.from, to: below.from });
    const { block, end } = parts;
    // A blank line goes whole, as Backspace takes it, so the line below keeps its start
    // rather than taking the blank line's spaces, which can make it code, or keep a `#`
    // from opening a heading. A message shows each line, so there it goes even where the
    // blocks beside it then join, and the edit runs from the end of the block above, so
    // the check sees the blocks it joins.
    if (!block && below && !line.text.trim()) {
      const { held } = nextHolding(state, line, false);
      return [
        [
          state.facet(message) && held
            ? {
                from: held.to,
                to: below.from,
                insert: state.sliceDoc(held.to, line.from),
              }
            : { from: line.from, to: below.from },
        ],
      ];
    }
    if (!block) return false;
    const hard = hardBreakBefore(state, line);
    if (
      hard &&
      !parts.first &&
      at === parts.words &&
      [...state.sliceDoc(at, end)].length === 1
    )
      return [[{ from: brokenFrom(state, line), to: end }]];
    if (at < end || !below) return false;
    if (isCode(block.token)) {
      if (!parts.code || parts.code.last) return true;
      return [[{ from: line.to, to: lineParts(state, below).words }]];
    }
    if (whole(block)) return at === line.to && line.number === lastLine(state, block);
    if (line.number < lastLine(state, block)) {
      const next = lineParts(state, below);
      if (next.marks) return true;
      const breaks = hardBreakBefore(state, below);
      if (breaks) return [[{ from: breaks.from, to: next.markers }]];
      return [[jointBefore(state, below) ?? { from: line.to, to: next.markers }]];
    }
    if (parts.marks) return true;
    const { held, between } = nextHolding(state, line, true);
    if (!held) return false;
    if (between > gapLines(state))
      return [
        [{ from: line.to, to: held.from, insert: state.sliceDoc(below.to, held.from) }],
      ];
    const next = lineParts(state, held);
    if (next.bare) return lineGone(held, { from: held.from - 1, to: held.to });
    if (next.own) return unwrap(state, { ...next, own: next.own });
    if (!next.block || whole(next.block)) return true;
    return [[{ from: at, to: next.words }, ...intoHeading(state, parts, next.words)]];
  }

  // `changes` without the source each edit puts back as it was, so the field rewrites
  // only what the key changes: an edit spans the blocks it joins for `keeps` to check
  // them, as Backspace on a message's blank line runs from the end of the block above.
  function narrowed(state: EditorState, changes: Changes) {
    const edits: Edit[] = [];
    changes.iterChanges((from, to, _fromB, _toB, inserted) =>
      edits.push(differing(state.sliceDoc(from, to), inserted.toString(), from)),
    );
    return state.changes(edits);
  }

  const deleteAtEdge =
    (forward: boolean): ((view: StateTarget) => boolean) =>
    (view) => {
      const { state } = view;
      const { main } = state.selection;
      if (state.readOnly || !main.empty || state.selection.ranges.length > 1)
        return false;
      const taken = (forward ? deletionAfter : deletionBefore)(state, main.head);
      if (typeof taken === "boolean") return taken;
      const changes = taken
        .map((edits) => state.changes(edits))
        .find((made) => keeps(state, made));
      if (changes)
        view.dispatch(
          state.update({
            changes: narrowed(state, changes),
            // The caret stays before the words it stood before, past a line put above them.
            selection: { anchor: changes.mapPos(main.head, 1) },
            scrollIntoView: true,
            userEvent: forward ? "delete.forward" : "delete.backward",
          }),
        );
      return true;
    };

  // Home stops at the first word a line shows, past its markers and a heading's `#`;
  // from there it goes to the line's start, where they show.
  const home =
    (extend: boolean): ((view: EditorView) => boolean) =>
    (view) => {
      const { state } = view;
      const selection = EditorSelection.create(
        state.selection.ranges.map((range) => {
          const { words } = lineParts(state, state.doc.lineAt(range.head));
          let { head } = view.moveToLineBoundary(range, false);
          if (range.head > words && head < words) head = words;
          return extend
            ? EditorSelection.range(range.anchor, head)
            : EditorSelection.cursor(head);
        }),
        state.selection.mainIndex,
      );
      if (selection.eq(state.selection)) return false;
      view.dispatch({ selection, scrollIntoView: true, userEvent: "select" });
      return true;
    };

  // Where words put at `at`, on a line of a body that held none past its markers, need a
  // line break before or after them to stand as blocks of their own, as Return on a
  // blank line leaves them (`newLine`): the parser would otherwise read them into a
  // block beside them, above or below, as a paragraph's words, a heading's underline or
  // an item's lazy line. On a line a hard break opens they continue its paragraph
  // instead, with where in them a backslash goes to keep them in it, as Return keeps
  // words after its break. Null where they need none of these, or the field reads as a
  // message, whose lines stand alone.
  /** @param doc the words with them put */
  function gapAround(state: EditorState, at: number, put: string, doc: Text) {
    if (state.facet(message)) return null;
    const line = state.doc.lineAt(at);
    const begin = beginBelow(state, at);
    if (begin === null) return null;
    const { placed } = state.field(reading);
    const holds = state
      .sliceDoc(opened(line, placed.filter(container)), line.to)
      .trim();
    // Words on a line a hard break opens continue its paragraph, the first mark of the
    // line's words escaped where it would open a block there, as a space after `1.`
    // would. A table's head row aside, a line opens a block by the marks, digits and
    // spaces it starts with, so only text put among them, or just after them, can make
    // it open one, and a line of words starting with no mark opens none.
    if (hardBreakBefore(state, line)) {
      const { words } = lineParts(state, line);
      const start = Math.min(words, at);
      const shown = doc.sliceString(start, doc.lineAt(start).to);
      const lead = shown.length - shown.replace(/^[ \t\d!-/:-@[-`{-~]+/, "").length;
      if (!put.includes("\n") && (at > start + lead || firstMark(shown) === null))
        return { before: "", after: "", escape: null };
      const made = escapedWhere(
        state,
        state.changes({ from: at, insert: put }),
        start,
        put,
        (read) =>
          read.some(
            ({ token, from: p, to: q }) =>
              token.type === "paragraph_open" && p < line.from && at < q,
          ),
      );
      if (made) return { before: "", after: "", escape: made.escape };
    }
    if (holds || !/\S/.test(put)) return null;
    const { block } = lineParts(state, line);
    const leaves = (source: string) =>
      placedMarkdownTokens(source, false).filter(({ token }) => LEAF.test(token.type));
    const read = leaves(doc.toString());
    // On a blank line inside code they are the code's while it holds them, as indented
    // code doesn't once they stand left of its indent, and what follows them still parts
    // from them. Otherwise a block above reaching into them, as a paragraph they continue,
    // a heading whose underline they make or a table whose row they make, and then, with
    // them parted from it, a block from them reaching past their last line.
    const held =
      block !== undefined &&
      isCode(block.token) &&
      read.some((c) => isCode(c.token) && c.from <= at && at < c.to);
    const above = !held && read.some(({ from, to }) => from < line.from && to > at);
    const before = above ? begin : "";
    const source = doc.sliceString(0, at) + before + doc.sliceString(at);
    const end = at + before.length + put.length;
    const last = source.indexOf("\n", end);
    const lineEnd = last === -1 ? source.length : last;
    const below = (above ? leaves(source) : read).some(
      ({ from, to }) => line.from <= from && from < end && to > lineEnd + 1,
    );
    if (!above && !below) return null;
    return {
      before,
      after: below ? begin.replace(/[ \t]+$/, "") : "",
      escape: null,
    };
  }

  // What text `put` in place of the selection, at `at` in `doc`, the draft with it put,
  // takes around it. Pasted lines stay in the quotes and list items the caret stands in,
  // as a line begun with Shift+Enter does: code's, which don't continue them lazily, and
  // prose's, whose second paragraph would leave them. In a list item a pasted line of
  // prose that opens an item opens the next of its list, so a pasted item stays the item
  // it was. Words put on a line that held none stand apart (`gapAround`), and marks put
  // at a fence's line stay marks (`fenceBreak`).
  function settled(
    state: EditorState,
    put: string,
    pasted: boolean,
    at: number,
    doc: Text,
  ): ChangeSpec[] {
    const { from: start, empty } = state.selection.main;
    const begin = beginBelow(state, start);
    const code = codeAt(state, start) !== null || /^ {0,3}(`{3,}|~{3,})/m.test(put);
    const { placed } = state.field(reading);
    const holders = placed
      .filter(container)
      .filter(holding(placed, state.doc.lineAt(start)));
    const lines =
      pasted && begin && begin !== "\n"
        ? [...put.matchAll(/\n/g)].map(({ index }) => ({
            from: at + index,
            to: at + index + 1,
            insert:
              !code &&
              item(holders.at(-1)) &&
              /^[ \t]*(?:[-+*]|\d{1,9}[.)])(?:[ \t]|$)/.test(put.slice(index + 1))
                ? `\n${holders.slice(0, -1).map(carried).join("")}`
                : begin,
          }))
        : [];
    const gap = empty ? gapAround(state, start, put, doc) : null;
    const from = fenceBreak(state, put, pasted);
    return [
      ...(gap?.before ? [{ from: at, insert: gap.before }] : []),
      ...(gap?.escape != null ? [{ from: gap.escape, insert: "\\" }] : []),
      ...(from === null ? [] : [{ from, insert: begin ?? "\n" }]),
      ...lines,
      ...(gap?.after ? [{ from: at + put.length, insert: gap.after }] : []),
    ];
  }

  // Where a line break goes so that text put at the caret leaves a fence's marks as
  // marks, or null where it needs none. Words after closing marks start the line below,
  // as words after a code span's closing backtick stand outside it. A paste after
  // opening marks, or after a language, starts the code. A run of marks completed at the
  // end of an open fence's code takes a line of its own, where it closes the fence, and
  // the caret stays after it for the words that go below. The source stays a fence every
  // Markdown reader takes alike, and marks meant as code stay code in a longer fence or
  // a paste. Rejected: a closing fence the message's reading finds at a line's end, which
  // leaves the next words in the code and misreads an agent's code whose line ends in
  // marks; and closing only as the caret leaves the line, which shows nothing at the
  // closing backtick.
  function fenceBreak(state: EditorState, put: string, pasted: boolean) {
    const { head: caret, empty } = state.selection.main;
    const at = empty ? codeAt(state, caret) : null;
    if (!at || caret !== at.line.to) return null;
    const { fence, line, opening, closing, open, words } = at;
    const { markup } = fence.token;
    const mark = markup.charAt(0);
    if (closing) return put.startsWith(mark) ? null : caret;
    if (opening) {
      const marks = (fence.markers?.[0]?.[0] ?? line.from) + markup.length;
      const language = !/\s/.test(state.sliceDoc(marks, caret).trim());
      return pasted && language ? caret : null;
    }
    const run = caret - markup.length + 1;
    const closes = put === mark && line.text.endsWith(markup.slice(1));
    return open && !pasted && closes && words(line, run) ? run : null;
  }

  const nest =
    (deeper: boolean): ((view: EditorView) => boolean) =>
    (view) => {
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
   * line, `field.message()` whether its words read as a message or, where it edits a
   * Markdown body in place, as a file, which joins a paragraph's lines (`joints`),
   * `field.revealed(view, pos)` shows the row holding `pos` in the field's
   * host, and `field.focused()` hears the editor take or lose focus. */
  function fieldState(words: FieldWords, field: FieldConfiguration) {
    // The run of words that differs between `base` and `text`: where the user typed.
    const { base, text } = words;
    const typed = differing(base, text);
    let state = EditorState.create({
      doc: base,
      // Taking the typing back leaves the caret where it went in.
      selection: { anchor: typed.from },
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
        // 6.43). The beforeinput already opened the edit's bracket. An input method's
        // composition, whose beforeinput can't be cancelled, starts once the editor
        // has taken the selected words away, since Firefox drops one begun over them
        // and keeps the words (Firefox 159); its first update is the one before the
        // editor reads it as composing. EditContext composes in the editor's model.
        EditorView.domEventHandlers({
          beforeinput(event, view) {
            const text = event.data;
            if (
              event.inputType === "insertCompositionText" &&
              !view.composing &&
              !view.state.selection.main.empty &&
              !view.state.readOnly &&
              !view.contentDOM.editContext
            ) {
              field.typed(true, () =>
                view.dispatch(
                  view.state.update(view.state.replaceSelection(""), {
                    userEvent: "input.type.compose.start",
                  }),
                ),
              );
              return false;
            }
            if (
              event.inputType !== "insertText" ||
              text === null ||
              view.state.selection.main.empty ||
              view.state.readOnly ||
              view.composing
            )
              return false;
            event.preventDefault();
            field.typed(true, () =>
              view.dispatch(
                view.state.update(view.state.replaceSelection(text), {
                  scrollIntoView: true,
                  userEvent: "input.type",
                }),
              ),
            );
            return true;
          },
        }),
        // An edit's reveal shows the caret's row in the host first; the view's own
        // reveal (annotations/editor-view.js) then carries the caret out through the page.
        EditorView.scrollHandler.of((view, range) => {
          field.revealed(view, range.head);
          return false;
        }),
        EditorView.updateListener.of((update) => {
          if (update.focusChanged) field.focused();
        }),
        // A double press selects the word its first press put the caret in, where that
        // press showed the markup the caret stands beside, as the `**` before a bold
        // first word, and so moved the word from under the pointer before the second
        // press read where it stands. Dragging on extends the selection by words, as the
        // platform's does.
        EditorView.mouseSelectionStyle.of((view, event) => {
          if (event.detail !== 2 || event.button !== 0 || event.shiftKey) return null;
          const { head } = view.state.selection.main;
          // Where nothing moved, as on a word whose markup was already shown, the press
          // selects as CodeMirror's does, a mark or a space alone included.
          const at = view.posAtCoords({ x: event.clientX, y: event.clientY }, false);
          if (at === head) return null;
          let word = view.state.wordAt(head);
          if (!word) return null;
          return {
            get(current) {
              if (!word) return view.state.selection;
              if (current === event) return EditorSelection.create([word]);
              const pos = view.posAtCoords(
                { x: current.clientX, y: current.clientY },
                false,
              );
              const other = view.state.wordAt(pos) ?? EditorSelection.cursor(pos);
              return EditorSelection.create([
                pos < word.from
                  ? EditorSelection.range(word.to, other.from)
                  : EditorSelection.range(word.from, Math.max(word.to, other.to)),
              ]);
            },
            update(update) {
              if (update.docChanged && word) word = word.map(update.changes);
            },
          };
        }),
        histories.of(history()),
        // A one-line field holds one line, so a line break pasted or inserted by the
        // platform, as Android's editing does, becomes a space.
        EditorState.transactionFilter.of((tr) => {
          if (!tr.docChanged || !field.oneLine()) return tr;
          const breaks: ChangeSpec[] = [];
          tr.changes.iterChanges((_fromA, _toA, fromB, _toB, inserted) => {
            const text = inserted.toString();
            for (
              let at = text.indexOf("\n");
              at !== -1;
              at = text.indexOf("\n", at + 1)
            )
              breaks.push({
                from: fromB + at,
                to: fromB + at + 1,
                insert: " ",
              });
          });
          return breaks.length ? [tr, { changes: breaks, sequential: true }] : tr;
        }),
        EditorState.transactionFilter.of((tr) => {
          const pasted = tr.isUserEvent("input.paste");
          if (
            field.oneLine() ||
            !(pasted || tr.isUserEvent("input.type")) ||
            tr.isUserEvent("input.type.compose")
          )
            return tr;
          // The one change that puts text in place of the selection.
          const { startState: state } = tr;
          const { from: start, to: end } = state.selection.main;
          let put = "";
          let at = start;
          tr.changes.iterChanges((from, to, fromB, _toB, inserted) => {
            if (from === start && to === end) {
              put = inserted.toString();
              at = fromB;
            }
          });
          if (!put) return tr;
          const settle = (changes: ChangeSpec[]) =>
            changes.length
              ? [
                  {
                    changes,
                    sequential: true,
                    annotations: isolateHistory.of("full"),
                  },
                ]
              : [];
          // Words put after a hard break's backslash, where the caret stands at its
          // line's end, go before it, so the backslash stays the break it shows as.
          const broken = state
            .field(reading)
            .placed.find(
              ({ token, from, to: brokenTo }) =>
                token.type === "hardbreak" &&
                from < start &&
                start < brokenTo &&
                start <= state.doc.lineAt(from).to,
            );
          if (broken && start === end) {
            const insert = { from: broken.from, insert: put };
            const moved = state.update({ selection: { anchor: broken.from } });
            return [
              {
                changes: insert,
                selection: { anchor: broken.from + put.length },
                scrollIntoView: true,
                userEvent: pasted ? "input.paste" : "input.type",
              },
              ...settle(
                settled(
                  moved.state,
                  put,
                  pasted,
                  broken.from,
                  moved.state.update({ changes: insert }).newDoc,
                ),
              ),
            ];
          }
          const changes = settle(settled(state, put, pasted, at, tr.newDoc));
          return changes.length ? [tr, ...changes] : tr;
        }),
        invertedEffects.of((tr) =>
          tr.effects
            .filter((effect) => effect.is(ownerStep))
            .map(({ value }) => ownerStep.of({ run: value.back, back: value.run })),
        ),
        keymap.of([
          // A one-line field takes no line break (`field.oneLine`).
          {
            key: "Shift-Enter",
            run: (view) => field.oneLine() || view.state.readOnly,
          },
          { key: "Enter", run: (view) => field.returned() && newLine(view) },
          {
            key: "Shift-Enter",
            run: (view) => !view.state.facet(message) && newLine(view),
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
          // Down reaches here only where the caret has no line below (`lineStep`).
          {
            key: "ArrowDown",
            run: (view) => !field.oneLine() && leaveCode(view),
          },
          // Keys at the edge of a line's shown words (`deleteAtEdge`, `home`).
          { key: "Backspace", run: deleteAtEdge(false) },
          { key: "Delete", run: deleteAtEdge(true) },
          { key: "Home", run: home(false), shift: home(true) },
          { mac: "Cmd-ArrowLeft", run: home(false), shift: home(true) },
          ...standardKeymap.filter(
            ({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter",
          ),
          ...historyKeymap,
        ]),
        reading,
        message.of(field.message()),
        joints,
        afterChange,
        livePreview,
        EditorView.lineWrapping,
        editable.of(EditorState.readOnly.of(field.readOnly)),
        attributes.of(EditorView.contentAttributes.of(field.attributes)),
      ],
    });
    state = state.update({
      ...(text !== base && {
        changes: typed,
        annotations: isolateHistory.of("full"),
        userEvent: "input.type",
      }),
      selection: { anchor: words.anchor, head: words.head },
    }).state;
    for (const [undo, redo] of words.steps)
      state = state.update(record(undo, redo)).state;
    return state;
  }

  // The words as a field that edits in place saves them: each run of blank lines
  // between two lines that hold words or markup written as its last line, the one blank
  // line the display draws as the gap there (`standBlocks`), so the words reopen where
  // the display shows them. A run inside a quote or a list goes the same way. Blank
  // lines at the start or end, and those code holds, stay. So does a run without whose
  // lines the display would draw the words otherwise, as it starts a second list after
  // an empty item and two blank lines. Only the renderer knows each such rule, so saving
  // draws the words both ways and compares them, run by run where dropping every run at
  // once draws them otherwise.
  const oneLinePerGap = (state: EditorState) => {
    const { doc } = state;
    const reading = state.facet(message);
    const source = doc.toString();
    const blank = blankLines(doc, placedMarkdownTokens(source, reading));
    const runs: { from: number; to: number }[] = [];
    let run = 0;
    for (let n = 1; n <= doc.lines; n++) {
      if (blank(n)) {
        run ||= n;
        continue;
      }
      if (run > 1 && n - run > 1)
        runs.push({ from: doc.line(run).from, to: doc.line(n - 1).from });
      run = 0;
    }
    if (!runs.length) return source;
    const shown = renderMarkdown(source, {}, reading);
    const saved = (dropped: { from: number; to: number }[]) =>
      state.changes(dropped).apply(doc).toString();
    if (renderMarkdown(saved(runs), {}, reading) === shown) return saved(runs);
    const spare: { from: number; to: number }[] = [];
    for (const drop of runs)
      if (renderMarkdown(saved([...spare, drop]), {}, reading) === shown)
        spare.push(drop);
    return saved(spare);
  };

  const readOnly = (on: boolean) => ({
    effects: editable.reconfigure(EditorState.readOnly.of(on)),
  });
  const contentAttributes = (wanted: Record<string, string>) => ({
    effects: attributes.reconfigure(EditorView.contentAttributes.of(wanted)),
  });
  // A step in the history that changes no words, standing alone: taking it back calls
  // `undo`, redoing it calls `redo`.
  const record = (undo: () => void, redo: () => void) => ({
    effects: ownerStep.of({ run: redo, back: undo }),
    annotations: isolateHistory.of("full"),
  });
  // Dropping the history's field and adding it back starts it empty, in two successive
  // transactions.
  const forgetHistory = { effects: histories.reconfigure([]) };
  const startHistory = () => ({ effects: histories.reconfigure(history()) });

  /** Run the owner's steps an undo or redo reached. */
  function runOwnerSteps(transactions: readonly Transaction[]) {
    for (const tr of transactions)
      if (tr.isUserEvent("undo") || tr.isUserEvent("redo"))
        for (const effect of tr.effects) if (effect.is(ownerStep)) effect.value.run();
  }

  return {
    LeafEditorView,
    fieldState,
    oneLinePerGap,
    readOnly,
    contentAttributes,
    record,
    forgetHistory,
    startHistory,
    runOwnerSteps,
  };
}
