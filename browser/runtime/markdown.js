// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { elementsDeclaring, declarationFor } from "./registry.js";
import { alignText } from "./text-alignment.js";
import { dataBody } from "./widget-upgrade.js";

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const escapedSource = (text) => escapeHtml(text);
let render = escapedSource;
/** @type {(text: string, breaks?: boolean) => string} */
let renderInline = escapedSource;
let tokenize = null;
let ready;

export const renderMarkdown = (text) => render(text);
// The words a user sees in rendered Markdown, for a surface that shows them as plain
// text: an excerpt, a label, a passage. Until the parser lands they are the source.
export function renderedWords(html, imageAlt = false) {
  const parsed = document.createElement("template");
  parsed.innerHTML = html;
  return fragmentWords(parsed.content, imageAlt);
}

// Read a disposable fragment so excerpts and caret coordinates count the same
// semantic breaks, including a break with no formatting text node after it.
function fragmentWords(fragment, imageAlt = false) {
  for (const br of fragment.querySelectorAll("br"))
    br.replaceWith(document.createTextNode("\n"));
  if (imageAlt)
    for (const image of fragment.querySelectorAll("img"))
      image.replaceWith(document.createTextNode(image.alt));
  return fragment.textContent;
}
export const markdownWords = (text) => renderedWords(render(text));
export const renderInlineMarkdown = (text, breaks = true) => renderInline(text, breaks);
// Passage readings recognize the fragment's semantic <br> as visible separation.
export function inlineMarkdownFragment(text, breaks = true) {
  const parsed = document.createElement("template");
  parsed.innerHTML = renderInlineMarkdown(text, breaks);
  return parsed.content;
}

// Registry text formatting belongs to the layer, so a package declaration cannot
// make file-side passages read words the browser leaves as raw Markdown.
export async function loadDeclaredMarkdown(scope) {
  if (
    !declarationFor(scope, "x-text-format") &&
    !elementsDeclaring(scope, "x-text-format").length
  )
    return;
  let failure;
  if (!(await loadMarkdown((error) => (failure = error))))
    throw new Error(
      `leaf: Markdown renderer failed to load: ${failure?.message ?? failure}`,
    );
}

// Only presentation nodes are formatted. Source documents stay intact for typed state,
// revision patching and provenance; arrivals call this after capture, before connection.
// Their import preparation has already made the parser ready, so this step is synchronous.
export function formatDeclaredMarkdown(scope) {
  const elements = elementsDeclaring(scope, "x-text-format");
  if (declarationFor(scope, "x-text-format")) elements.unshift(scope);
  if (!elements.length) return;
  if (!tokenize)
    throw new Error("leaf: Markdown formatting requires its loaded renderer");
  for (const element of elements) {
    if (declarationFor(element, "x-text-format") === "markdown") {
      const pre = element.querySelector(":scope > pre");
      if (!pre) continue;
      const body =
        element.querySelector(":scope > .lf-markdown-body") ??
        document.createElement("div");
      if (body.className !== "lf-markdown-body") body.className = "lf-markdown-body";
      paintMarkdown(body, dataBody(element));
      body.removeAttribute("data-lf-prepaint");
      body.removeAttribute("data-lf-gen");
      pre.replaceWith(body);
      continue;
    }
    for (const node of [...element.childNodes]) {
      if (node.nodeType !== Node.TEXT_NODE || !node.data.trim()) continue;
      const parsed = inlineMarkdownFragment(node.data, false);
      if (!parsed.firstElementChild && parsed.textContent === node.data) continue;
      const words = document.createElement("span");
      words.className = "lf-markdown-words";
      words.dataset.lfMarkdownWords = "";
      words.dataset.lfSourceWords = node.data;
      words.append(parsed);
      node.replaceWith(words);
    }
  }
}
// Keep the exact source on its reading surface. Passage capture reads the rendered
// children; revision comparison reads source, so formatting never becomes state.
export function paintMarkdown(element, source) {
  if (
    element.dataset.lfSourceWords === source &&
    !element.hasAttribute("data-lf-prepaint")
  )
    return;
  const markup = renderMarkdown(source);
  if (element.dataset.lfSourceWords !== source) element.dataset.lfSourceWords = source;
  if (element.innerHTML !== markup) element.innerHTML = markup;
}

const characters = new Intl.Segmenter(undefined, { granularity: "grapheme" });
// Align within the parser's declared block span, rather than reimplement its block
// normalization. That normalization can both remove prefixes and expand a tab into
// spaces. The shared lossless aligner maps either transformation back to source.
function inlineSourcePositions(source, raw, at, limit) {
  // Even an empty inline token has one boundary (for example, an empty table cell).
  const positions = [at];
  let sourceAt = at;
  let inlineAt = 0;
  for (const run of alignText(source.slice(at, limit), raw, characters, Infinity)) {
    if (run.kind === "delete") sourceAt += run.text.length;
    else {
      for (let i = 0; i < run.text.length; i++) {
        positions[inlineAt++] = sourceAt;
        if (run.kind === "same") sourceAt++;
      }
      positions[inlineAt] = sourceAt;
    }
  }
  return positions;
}

// Native parser tokens, each located in the exact source. Opening inline tokens carry
// the paired construct's whole span and the span of its words for editor decoration.
// Native block rules record markers before container prefixes are restored. Their
// line-relative spans survive newline normalization when mapped onto the source.
export function placedMarkdownTokens(source) {
  const tokens = markdownTokens(source);
  if (!tokens) return [];
  const starts = [0];
  for (let at = 0; at < source.length; at++) {
    if (source[at] === "\r" && source[at + 1] === "\n") at++;
    if (source[at] === "\r" || source[at] === "\n") starts.push(at + 1);
  }
  starts.push(source.length);
  const found = [];
  let inlineAt = 0;
  for (const [index, token] of tokens.entries()) {
    const from = token.map ? starts[token.map[0]] : 0;
    const to = token.map ? starts[token.map[1]] : source.length;
    if (token.type !== "inline") {
      if (
        token.map &&
        (token.nesting === 1 || token.type === "fence" || token.type === "code_block")
      )
        found.push({
          token,
          from,
          to,
          markers: token.meta?.markers?.map(([line, a, b]) => [
            starts[line] + a,
            starts[line] + b,
          ]),
          // A heading's inline token owns its content lines, excluding Setext syntax.
          contentLines:
            token.type === "heading_open"
              ? tokens[index + 1].map.map((at) => starts[at])
              : undefined,
          words: token.nesting ? null : token.content,
        });
      continue;
    }
    const positions = inlineSourcePositions(
      source,
      token.meta.sourceContent,
      Math.max(from, inlineAt),
      to,
    );
    const stack = [];
    for (const child of token.children) {
      if (!child.meta?.source) continue;
      let [a, b] = child.meta.source;
      if (child.nesting === 1) {
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          a = b - child.markup.length;
        const placed = {
          token: child,
          from: positions[a],
          to: positions[b],
          contentFrom: positions[b],
        };
        found.push(placed);
        stack.push(placed);
      } else if (child.nesting === -1) {
        const placed = stack.pop();
        if (!placed) continue;
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          b = a + child.markup.length;
        placed.to = positions[b];
        placed.contentTo = positions[a];
      } else if (child.type !== "html_inline") {
        found.push({
          token: child,
          from: positions[a],
          to: positions[b],
          words:
            child.type === "softbreak" || child.type === "hardbreak"
              ? "\n"
              : child.type === "image"
                ? safeUrl(child.attrGet("src"))
                  ? ""
                  : renderedWords(
                      renderInlineMarkdown(source.slice(positions[a], positions[b])),
                    )
                : child.content,
          escapes: (child.meta.escapes ?? []).map((at) => positions[at]),
        });
      }
    }
    inlineAt = positions.at(-1);
  }
  return found;
}

// Locate a rendered caret in the parser's leaf token, then align only that token's
// exact source and rendered text. The history diff's bounded whole-document alignment
// is unsuitable here: its deliberate coarse replacement must never send a caret to
// the end of a long formatted document. Token placement gives an ordered source span;
// the local exact alignment handles omitted delimiters, entities and escapes.
export function markdownSourceOffset(body, node, offset) {
  if (!body.contains(node)) return null;
  const range = document.createRange();
  range.selectNodeContents(body);
  range.setEnd(node, offset);
  const aim = fragmentWords(range.cloneContents()).length;
  const source = body.dataset.lfSourceWords;
  const shown = fragmentWords(body.cloneNode(true));
  let shownAt = 0;
  let sourceEnd = 0;
  for (const placed of placedMarkdownTokens(source)) {
    const { token, from, to } = placed;
    if (token.nesting) continue;
    const words = placed.words;
    if (!words) continue;
    const start = shown.indexOf(words, shownAt);
    if (start < 0) continue;
    if (aim < start) return from;
    if (aim <= start + words.length) {
      let sourceAt = from;
      let tokenAt = start;
      for (const run of alignText(
        source.slice(from, to),
        words,
        characters,
        Infinity,
      )) {
        if (run.kind === "delete") sourceAt += run.text.length;
        else {
          if (aim <= tokenAt + run.text.length)
            return sourceAt + (run.kind === "same" ? aim - tokenAt : 0);
          tokenAt += run.text.length;
          if (run.kind === "same") sourceAt += run.text.length;
        }
      }
      return to;
    }
    shownAt = start + words.length;
    sourceEnd = to;
  }
  return sourceEnd;
}

// The blocks an excerpt is cut at: those that hold words, a fence, and a table, whose
// rows read as one only under its head. A fence or table a range crosses goes whole,
// since part of one doesn't parse as the rest of it.
const EXCERPT_BLOCKS = new Set([
  "paragraph_open",
  "heading_open",
  "fence",
  "code_block",
  "table_open",
]);
const SOLID_BLOCKS = new Set(["fence", "code_block", "table_open"]);
// An address is its own words, so part of one is a different address.
const WHOLE_INLINE = new Set(["autolink", "linkify"]);

// The Markdown a reader copies from the rendered `range` of `body`, which lies inside
// it: the source between its ends, which renders what the range shows.
// - Every inline construct an end falls inside keeps its markers, so part of
//   `**a bold run**` still reads bold and part of a link's words keeps its address.
// - A range covering all of one block's words takes the block whole, with its list,
//   quote or heading markers. A range across blocks takes the block at each end from
//   its line's start where it covers that block's first words, and to its end where it
//   covers its last.
// - A line break keeps no container prefix, which an excerpt cut inside a quote or
//   list would misread; a reference link takes its address inline, since its
//   definition stays behind; and a block taken whole loses its first line's indent,
//   which would read as code once nothing stands around it.
export function markdownSourceExcerpt(body, range) {
  const source = body.dataset.lfSourceWords;
  const placed = placedMarkdownTokens(source);
  let start = markdownSourceOffset(body, range.startContainer, range.startOffset);
  let end = markdownSourceOffset(body, range.endContainer, range.endOffset);
  const inline = placed.filter(({ token }) => !token.block);
  const marked = inline.flatMap((placed) =>
    placed.contentFrom != null
      ? [placed]
      : placed.token.type === "code_inline"
        ? [
            {
              ...placed,
              contentFrom: placed.from + placed.token.markup.length,
              contentTo: placed.to - placed.token.markup.length,
            },
          ]
        : // A reference link's opening records no span of its own: it is the `[`.
          placed.token.type === "link_open"
          ? [{ ...placed, contentFrom: placed.from + 1 }]
          : [],
  );
  // An end on a construct's marker, or at the edge of its words, takes the marker.
  // Inner constructs go first, so an end moved onto one's opening marker is then read
  // against the construct around it.
  for (const { token, from, contentFrom, contentTo, to } of marked.toReversed()) {
    if (WHOLE_INLINE.has(token.markup)) {
      if (from < start && start < to) start = from;
      if (from < end && end < to) end = to;
      continue;
    }
    if (from < start && start <= contentFrom) start = from;
    else if (contentTo <= start && start < to) start = to;
    if (contentTo <= end && end < to) end = to;
    else if (from < end && end <= contentFrom) end = from;
  }
  const blocks = placed.filter(({ token }) => EXCERPT_BLOCKS.has(token.type));
  const words = (block) =>
    inline.filter(({ from, to }) => from >= block.from && to <= block.to);
  // A fence's code is no words, so no end covers them: a range inside one copies code.
  const wordsFrom = (block) => words(block)[0]?.from ?? -Infinity;
  const wordsTo = (block) => {
    const held = words(block);
    return held.length ? Math.max(...held.map(({ to }) => to)) : Infinity;
  };
  let first = blocks.findLast(({ from, to }) => from <= start && start < to);
  let last = blocks.findLast(({ from, to }) => from < end && end <= to);
  // An end at the edge of a block's words holds none of them, as where a triple click
  // ends its range at the start of the next block.
  if (first && last && first !== last && end <= wordsFrom(last)) {
    last = blocks.findLast(({ to }) => to <= last.from) ?? last;
    end = Math.min(end, last.to);
  }
  if (first && last && first !== last && start >= wordsTo(first)) {
    first = blocks.find(({ from }) => from >= first.to) ?? first;
    start = Math.max(start, first.from);
  }
  const crosses =
    first !== last ||
    (first?.token.type === "table_open" && source.slice(start, end).includes("\n"));
  const fromStart =
    first &&
    ((crosses && SOLID_BLOCKS.has(first.token.type)) || start <= wordsFrom(first));
  const toEnd =
    last && ((crosses && SOLID_BLOCKS.has(last.token.type)) || end >= wordsTo(last));
  if (crosses ? fromStart : fromStart && toEnd) start = first.from;
  if (crosses ? toEnd : fromStart && toEnd) end = last.to;
  const cut = marked.filter(({ token }) => !WHOLE_INLINE.has(token.markup));
  const closing = ({ token, contentTo, to }) =>
    token.type === "link_open" && !source.startsWith("](", contentTo)
      ? `](${token.attrGet("href")})`
      : source.slice(contentTo, to);
  const rewrites = [
    ...inline
      .filter(({ token }) => token.type === "softbreak" || token.type === "hardbreak")
      .map(({ from, to }) => ({
        from,
        to,
        text: source.slice(from, source.indexOf("\n", from) + 1),
      })),
    ...cut
      .filter(({ token }) => token.type === "link_open")
      .map((link) => ({ from: link.contentTo, to: link.to, text: closing(link) })),
  ]
    .filter(({ from, to }) => start <= from && to <= end)
    .sort((a, b) => a.from - b.from);
  const between = (a, b) => {
    let text = "";
    let at = a;
    for (const { from, to, text: rewritten } of rewrites)
      if (a <= from && to <= b) {
        text += source.slice(at, from) + rewritten;
        at = to;
      }
    return text + source.slice(at, b);
  };
  // The indent goes from the first block's lines only, since a later block's own,
  // such as a fence's code, is its content.
  const indent = start === first?.from ? /^[ \t]*/.exec(source.slice(start))[0] : "";
  const head = indent ? Math.min(end, first.to) : start;
  const excerpt = [
    ...cut
      .filter(({ contentFrom, contentTo }) => contentFrom < start && start < contentTo)
      .map(({ from, contentFrom }) => source.slice(from, contentFrom)),
    between(start, head).replace(new RegExp(`^[ \\t]{0,${indent.length}}`, "gm"), ""),
    between(head, end),
    ...cut
      .filter(({ contentFrom, contentTo }) => contentFrom < end && end < contentTo)
      .toReversed()
      .map(closing),
  ].join("");
  return excerpt.replace(/^\n+/, "").trimEnd();
}

// A copy of words inside one surface painted from Markdown, as a thread message's words
// and a page's Markdown body are (`paintMarkdown`), puts their Markdown on the clipboard
// as its plain text, beside the rendered words as HTML, so a paste into a text field or
// editor gets the Markdown and a paste into a rich editor the formatting. Words painted
// inline (`formatDeclaredMarkdown`) read their source as one line, which the block
// parsing here would misread, so they copy as the browser would, as does a selection
// reaching past the surface's words or made before the parser loads.
document.addEventListener("copy", (event) => {
  const selection = document.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed || !markdownReady()) return;
  const range = selection.getRangeAt(0);
  const start = range.startContainer;
  const body = (start instanceof Element ? start : start.parentElement)?.closest(
    "[data-lf-source-words]:not([data-lf-markdown-words])",
  );
  if (!body) return;
  // A triple click on the last paragraph ends the range just past it.
  const words = range.cloneRange();
  if (!body.contains(range.endContainer)) words.setEnd(body, body.childNodes.length);
  if (words.toString().trim() !== range.toString().trim()) return;
  const rendered = document.createElement("div");
  rendered.append(words.cloneContents());
  event.clipboardData.setData("text/plain", markdownSourceExcerpt(body, words));
  event.clipboardData.setData("text/html", rendered.innerHTML);
  event.preventDefault();
});

// Whether a rendering taken now is the parser's or the escaped source location in for
// it. A caller that keeps what it painted needs to know which it kept, so the words can
// be given their Markdown once the import lands.
export const markdownReady = () => render !== escapedSource;

const WEB_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function safeUrl(href) {
  if (href.startsWith("#")) return true;
  try {
    return WEB_PROTOCOLS.has(new URL(href, location.href).protocol);
  } catch {
    return false;
  }
}

const probe = document.createElement("template");
function renderedElement(markup, tag) {
  probe.innerHTML = markup;
  const element = probe.content.firstElementChild;
  return element?.localName === tag ? element : null;
}

// Native Markdown tokens are the editor's reading, too. Link admission annotates the
// opening token before it reaches either renderer, so both draw the same safe label.
const markdownTokens = (text) => tokenize?.(text) ?? null;

// Source spans are recorded where the parser consumes them, before its presentation
// passes join text tokens or recognize bare links. No second Markdown grammar lives
// here: the same native rules decide the renderer's constructs and the editor's.
function sourcePositions(markdown) {
  const NativeState = markdown.inline.State;
  markdown.inline.State = class extends NativeState {
    pushPending() {
      const from = this.sourcePendingFrom ?? this.pos - this.pending.length;
      const to = from + this.pending.length;
      const token = super.pushPending();
      token.meta = { ...token.meta, source: [from, to] };
      this.sourcePendingFrom = null;
      return token;
    }
    push(...args) {
      const token = super.push(...args);
      token.meta = { ...token.meta, sourceAt: this.pos };
      return token;
    }
  };
  const nativeRules = markdown.inline.ruler.getRules.bind(markdown.inline.ruler);
  const wrapped = new WeakMap();
  markdown.inline.ruler.getRules = (chain) =>
    nativeRules(chain).map((rule) => {
      if (!wrapped.has(rule))
        wrapped.set(rule, (state, silent) => {
          const from = state.pos;
          const pendingFrom = from - state.pending.length;
          if (!silent && !state.pending) state.sourcePendingFrom = from;
          const count = state.tokens.length;
          const ok = rule(state, silent);
          if (!ok || silent) return ok;
          const emitted = state.tokens
            .slice(count)
            .filter((token) => !token.meta?.source);
          let delimiterAt = from;
          for (const token of emitted) {
            let span = [from, state.pos];
            if (
              token.type === "text" &&
              emitted.every((item) => item.type === "text")
            ) {
              span = [delimiterAt, delimiterAt + token.content.length];
              delimiterAt = span[1];
            } else if (token.type === "link_open") {
              span = [from, token.meta.sourceAt];
            } else if (token.type === "link_close") {
              span = [token.meta.sourceAt, state.pos];
            }
            // A bare URL's inline rule starts at its colon, with the scheme still pending.
            if (
              token.markup === "linkify" ||
              (emitted.some((item) => item.markup === "linkify") &&
                token.type === "text")
            ) {
              const matched = markdown.linkify
                .match(state.src.slice(pendingFrom, state.pos))
                .at(-1);
              const start = pendingFrom + matched.index;
              span =
                token.type === "link_open"
                  ? [start, start]
                  : token.type === "link_close"
                    ? [state.pos, state.pos]
                    : [start, state.pos];
            } else if (emitted.some((item) => item.markup === "autolink")) {
              span =
                token.type === "link_open"
                  ? [from, from + 1]
                  : token.type === "link_close"
                    ? [state.pos - 1, state.pos]
                    : [from + 1, state.pos - 1];
            }
            token.meta = {
              ...token.meta,
              source: span,
              escapes:
                token.info === "escape" && token.content !== token.markup
                  ? [span[0]]
                  : [],
            };
          }
          return ok;
        });
      return wrapped.get(rule);
    });
  // Joining is a parser optimization. Preserve the first source coordinate when it
  // merges several native text tokens into their final survivor.
  const keepJoined = (before, after) => {
    const alive = new Set(after);
    let first = null;
    let escapes = [];
    for (const { token, source, escaped } of before) {
      escapes.push(...escaped);
      // Emphasis combines two delimiter tokens and erases the spare text token.
      // Its source delimiter must not become part of the following joined words.
      if (source && !first && (token.type !== "text" || token.content)) first = source;
      if (alive.has(token)) {
        if (source && first && token.type === "text")
          token.meta.source = [first[0], source[1]];
        if (token.meta) token.meta.escapes = escapes;
        first = null;
        escapes = [];
      }
    }
  };
  const snapshot = (tokens) =>
    tokens.map((token) => ({
      token,
      source: token.meta?.source,
      escaped: token.meta?.escapes ?? [],
    }));
  const secondRules = markdown.inline.ruler2.getRules.bind(markdown.inline.ruler2);
  markdown.inline.ruler2.getRules = (chain) =>
    secondRules(chain).map((rule) => (state) => {
      const before = snapshot(state.tokens);
      rule(state);
      keepJoined(before, state.tokens);
    });
  markdown.core.ruler.after("inline", "source_content", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline")
        token.meta = { ...token.meta, sourceContent: token.content };
  });
  markdown.core.ruler.before("linkify", "source_before_linkify", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") {
        token.meta ??= {};
        let inLink = 0;
        token.meta.beforeLinks = token.children.map((child) => {
          if (child.type === "link_open") inLink++;
          else if (child.type === "link_close") inLink--;
          let source = child.meta?.source;
          if (!inLink && source && child.type === "text" && child.content) {
            // Task-list presentation removes its checkbox prefix from the text token.
            // Retain the exact words' source, before linkify splits or normalizes them.
            const raw = token.meta.sourceContent.slice(source[0], source[1]);
            const at = raw.indexOf(child.content);
            if (at < 0) throw new Error("leaf: Markdown text token lost its source");
            source = [source[0] + at, source[0] + at + child.content.length];
            child.meta.source = source;
          }
          return {
            token: child,
            content: child.content,
            source,
            links:
              !inLink && child.type === "text"
                ? (markdown.linkify.match(child.content) ?? [])
                : [],
          };
        });
      }
  });
  markdown.core.ruler.after("linkify", "source_after_linkify", (state) => {
    for (const inline of state.tokens)
      if (inline.type === "inline") {
        const before = inline.meta.beforeLinks;
        let at = 0;
        let textAt = 0;
        let link = null;
        for (const token of inline.children) {
          if (token.meta?.source || before[at]?.token === token) {
            while (at < before.length && before[at].token !== token) at++;
            at++;
            textAt = 0;
            link = null;
            continue;
          }
          if (textAt === before[at]?.content.length && token.type !== "link_close") {
            at++;
            textAt = 0;
          }
          const original = before[at];
          if (!original?.source) continue;
          let span;
          if (token.type === "link_open") {
            link = original.links.find(
              (match) =>
                match.index >= textAt &&
                markdown.normalizeLink(match.url) === token.attrGet("href"),
            );
            if (!link) throw new Error("leaf: Markdown autolink lost its source");
            textAt = link.index;
            span = [textAt, textAt];
          } else if (token.type === "link_close") {
            textAt = link.lastIndex;
            span = [textAt, textAt];
            link = null;
          } else if (link) {
            span = [link.index, link.lastIndex];
            textAt = link.lastIndex;
          } else {
            const from = original.content.indexOf(token.content, textAt);
            if (from < 0)
              throw new Error("leaf: Markdown linkified text lost its source");
            textAt = from + token.content.length;
            span = [from, textAt];
          }
          token.meta = {
            ...token.meta,
            source: span.map((offset) => original.source[0] + offset),
          };
        }
        delete inline.meta.beforeLinks;
      }
  });
  markdown.core.ruler.before("text_join", "source_before_join", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") token.meta.beforeJoin = snapshot(token.children);
  });
  markdown.core.ruler.after("text_join", "source_after_join", (state) => {
    for (const token of state.tokens)
      if (token.type === "inline") {
        keepJoined(token.meta.beforeJoin, token.children);
        delete token.meta.beforeJoin;
      }
  });
}

// The blocks the parser emits whole, with no opening and closing pair.
const BLOCK_LEAVES = new Set(["fence", "code_block", "hr"]);

function makeMarkdown(module, breaks) {
  const markdown = new module.MarkdownIt({ html: false, breaks, linkify: true }).use(
    module.taskLists,
    { enabled: false },
  );
  // A bare domain is indistinguishable from a file name such as setup.py. Require
  // an explicit URL or Markdown link instead of inventing an external destination.
  markdown.linkify.set({ fuzzyLink: false });
  // Each block says how many blank lines stand before it in the source, a quote's `>`
  // aside, so a message can space its blocks as the draft it was typed in showed them
  // (reading.css, `data-lf-gap`). Three stand for any more.
  markdown.core.ruler.after("block", "blank_lines", (state) => {
    const lines = state.src.split("\n");
    for (const token of state.tokens) {
      if (!token.map || !(token.nesting === 1 || BLOCK_LEAVES.has(token.type)))
        continue;
      let gap = 0;
      for (let at = token.map[0] - 1; at >= 0 && gap < 3; at--) {
        if (lines[at].replace(/^[\s>]*/, "")) break;
        gap++;
      }
      token.attrSet("data-lf-gap", String(gap));
    }
  });
  // Message paragraphs preserve typed spaces. A break has one visible carrier:
  // MarkdownIt's formatting newline after <br> would become a second line there.
  markdown.renderer.rules.softbreak = (_tokens, _at, options) =>
    options.breaks ? "<br>" : "\n";
  markdown.renderer.rules.hardbreak = () => "<br>";
  // Parse unsafe destinations to retain their visible labels. This owner strips the
  // destinations before HTML exists; there is no active unsafe intermediate markup.
  markdown.validateLink = () => true;
  const admitLinks = (tokens) => {
    const links = [];
    for (const token of tokens) {
      if (token.type === "link_open") {
        token.meta = { ...token.meta, linked: safeUrl(token.attrGet("href")) };
        links.push(token);
      } else if (token.type === "link_close") {
        token.meta = { ...token.meta, linked: links.pop().meta.linked };
      }
      // Image labels may contain parsed links or further images. Their inline
      // rendering follows the same URL admission as ordinary document prose.
      if (token.children) admitLinks(token.children);
    }
  };
  markdown.core.ruler.push("safe_links", (state) => {
    for (const block of state.tokens)
      if (block.type === "inline") admitLinks(block.children);
  });
  // Nested image labels can retain special text tokens beyond the core's joining
  // pass. Entities and escapes are text there, just as they are in document prose.
  markdown.renderer.rules.text_special = markdown.renderer.rules.text;
  markdown.renderer.rules.link_open = (tokens, at, options, env, renderer) => {
    const token = tokens[at];
    if (!token.meta.linked) return "";
    const href = token.attrGet("href");
    if (isCanonicalMediaUrl(href)) token.attrSet("href", scopedMediaUrl(href));
    return renderer.renderToken(tokens, at, options);
  };
  markdown.renderer.rules.link_close = (tokens, at, options, env, renderer) =>
    tokens[at].meta.linked ? renderer.renderToken(tokens, at, options) : "";
  markdown.renderer.rules.image = (tokens, at, options, env, renderer) => {
    const token = tokens[at];
    const href = token.attrGet("src");
    const alt = renderedWords(
      renderer.renderInline(token.children, options, env),
      true,
    );
    token.attrSet("alt", alt);
    if (!safeUrl(href)) return escapeHtml(alt);
    const markup = renderer.renderToken(tokens, at, options);
    if (!isCanonicalMediaUrl(href)) return markup;
    const image = renderedElement(markup, "img");
    const source = scopedMediaUrl(href);
    image.setAttribute("src", source);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "lf-media-open lf-message-media";
    button.setAttribute("data-lf-offer", "button");
    button.setAttribute("data-lf-said", "");
    button.setAttribute("data-lf-media-url", source);
    button.setAttribute("aria-label", `View ${alt || "Image"}`);
    button.append(image);
    return button.outerHTML;
  };
  return markdown;
}

export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/markdown-it.esm.js").then((module) => {
    const markdown = makeMarkdown(module, true);
    let singleLine;
    let positioned;
    render = (text) => markdown.render(text);
    renderInline = (text, breaks) =>
      (breaks ? markdown : (singleLine ??= makeMarkdown(module, false))).renderInline(
        text,
      );
    tokenize = (text) => {
      if (!positioned) {
        positioned = makeMarkdown(module, true);
        sourcePositions(positioned);
      }
      return positioned.parse(text, {});
    };
  }));
  return attempt
    .then(() => true)
    .catch((error) => {
      // A transient resource failure can recover on a later state read. Until then the
      // renderer remains the escaped source, which preserves every supplied word.
      if (ready === attempt) ready = undefined;
      onError?.(error);
      return false;
    });
}
