// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { describeFailure } from "./exception.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { elementsDeclaring, declarationFor } from "./registry.js";
import { alignText } from "./text-alignment.js";
import { dataBody } from "./widget-upgrade.js";
import { isElement } from "./shadow-tree.js";

/** @typedef {import("markdown-it").Token} NativeToken
 * @typedef {import("markdown-it").MarkdownIt} MarkdownIt
 * @typedef {NonNullable<ReturnType<MarkdownIt["linkify"]["match"]>>[number]} LinkMatch
 * @typedef {{token: NativeToken, source: [number, number] | undefined, spellings: [number, number, string][]}} TokenSnapshot
 * @typedef {{token: NativeToken, content: string, source: [number, number] | undefined, links: LinkMatch[]}} BeforeLink
 * @typedef {Object} TokenSource
 * @property {[number, number]} [source]
 * @property {number} [sourceAt]
 * @property {number} [indent]
 * @property {[number, number, string][]} [spelled]
 * @property {[number, number, number][]} [markers]
 * @property {string} [sourceContent]
 * @property {string | null} [url]
 * @property {TokenSnapshot[]} [beforeJoin]
 * @property {BeforeLink[]} [beforeLinks]
 */

/** @param {string} text */
const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** @param {string} text */
const escapedSource = (text) => escapeHtml(text);
/** @type {(text: string, breaks?: boolean) => string} */
let render = escapedSource;
/** @type {(text: string, breaks?: boolean) => string} */
let renderInline = escapedSource;
/** @type {((source: string) => NativeToken[]) | null} */
let tokenize = null;
/** @type {Promise<void> | undefined} */
let ready;

// `breaks` reads a soft line break as a hard one, since a message keeps the breaks its
// writer typed. A Markdown file's soft breaks are spaces, as CommonMark and GitHub
// render a file: its lines wrap for its editor, not its reader. A Markdown body
// (`paintMarkdown`), such as a draft, reads as a file.
/** @param {string} text @param {boolean} [breaks] */
export const renderMarkdown = (text, breaks = true) => render(text, breaks);
// The words a user sees in rendered Markdown, for a surface that shows them as plain
// text: an excerpt, a label, a passage. Until the parser lands they are the source.
/** @param {string} html @param {boolean} [imageAlt] */
export function renderedWords(html, imageAlt = false) {
  const parsed = document.createElement("template");
  parsed.innerHTML = html;
  return fragmentWords(parsed.content, imageAlt);
}

// Read a disposable fragment so excerpts and caret coordinates count the same
// semantic breaks, including a break with no formatting text node after it.
/** @param {DocumentFragment | HTMLElement} fragment @param {boolean} [imageAlt] */
function fragmentWords(fragment, imageAlt = false) {
  for (const br of fragment.querySelectorAll("br"))
    br.replaceWith(document.createTextNode("\n"));
  if (imageAlt)
    for (const image of fragment.querySelectorAll("img"))
      image.replaceWith(document.createTextNode(image.alt));
  return fragment.textContent;
}
/** @param {string} text */
export const markdownWords = (text) => renderedWords(renderMarkdown(text));
/** @param {string} text @param {boolean} [breaks] */
export const renderInlineMarkdown = (text, breaks = true) => renderInline(text, breaks);
// Passage readings recognize the fragment's semantic <br> as visible separation.
/** @param {string} text @param {boolean} [breaks] */
export function inlineMarkdownFragment(text, breaks = true) {
  const parsed = document.createElement("template");
  parsed.innerHTML = renderInlineMarkdown(text, breaks);
  return parsed.content;
}

// Registry text formatting belongs to the layer, so a package declaration cannot
// make file-side passages read words the browser leaves as raw Markdown.
/** @param {Element | Document | DocumentFragment} scope */
export async function loadDeclaredMarkdown(scope) {
  if (
    !(isElement(scope) && declarationFor(scope, "x-text-format")) &&
    !elementsDeclaring(scope, "x-text-format").length
  )
    return;
  /** @type {unknown} */
  let failure;
  if (!(await loadMarkdown((error) => (failure = error))))
    throw new Error(
      `leaf: Markdown renderer failed to load: ${describeFailure(failure)}`,
    );
}

// Only presentation nodes are formatted. Source documents stay intact for typed state,
// revision patching and provenance; arrivals call this after capture, before connection.
// Their import preparation has already made the parser ready, so this step is synchronous.
/** @param {Element | Document | DocumentFragment} scope */
export function formatDeclaredMarkdown(scope) {
  const elements = elementsDeclaring(scope, "x-text-format");
  if (isElement(scope) && declarationFor(scope, "x-text-format"))
    elements.unshift(scope);
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
      if (!(node instanceof Text) || !node.data.trim()) continue;
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
// children; revision comparison reads source, so formatting never becomes state. The
// body reads as a Markdown file, its soft line breaks spaces, as the server's prepaint
// draws it (`leaf.passages.markdown_markup`) and the field editing it in place draws
// them (composing/field-editor.js, `joints`).
/** @param {Element} element @param {string} source */
export function paintMarkdown(element, source) {
  if (
    element.getAttribute("data-lf-source-words") === source &&
    !element.hasAttribute("data-lf-prepaint")
  )
    return;
  const markup = renderMarkdown(source, false);
  if (element.getAttribute("data-lf-source-words") !== source)
    element.setAttribute("data-lf-source-words", source);
  if (element.innerHTML !== markup) element.innerHTML = markup;
}

const characters = new Intl.Segmenter(undefined, { granularity: "grapheme" });
// Align within the parser's declared block span, rather than reimplement its block
// normalization. That normalization can both remove prefixes and expand a tab into
// spaces. The shared lossless aligner maps either transformation back to source.
/** @param {string} source @param {string} raw @param {number} at @param {number} limit @param {boolean} cell */
function inlineSourcePositions(source, raw, at, limit, cell) {
  // A verbatim block ends with its words, past the opening markers. A cell shares its line.
  const start = at + source.slice(at, limit).trimEnd().length - raw.length;
  if (!cell && start >= at && source.startsWith(raw, start))
    return Array.from({ length: raw.length + 1 }, (_, i) => start + i);
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

/** Native parser offsets become editor coordinates only through this boundary. An
 * invalid offset must fail here rather than reach a caret as undefined or NaN.
 * @template T @param {readonly T[]} values @param {number} index @returns {T} */
function parserItem(values, index) {
  const value = values[index];
  if (value === undefined)
    throw new Error(
      `leaf: Markdown parser index ${index} is outside its ${values.length} source positions`,
    );
  return value;
}

/** @param {NativeToken} token @returns {token is NativeToken & {type: "inline", children: NativeToken[], map: [number, number]}} */
const isInlineToken = (token) => token.type === "inline";
/** After source_content, inline tokens carry their original words through the remaining core passes.
 * @param {NativeToken} token @returns {token is NativeToken & {type: "inline", children: NativeToken[], map: [number, number], lfSource: TokenSource & {sourceContent: string}}} */
const isPositionedInline = (token) => token.type === "inline";
/** @param {NativeToken} token @returns {token is NativeToken & {lfSource: TokenSource & {source: [number, number]}}} */
const hasSourceSpan = (token) => token.lfSource?.source !== undefined;

/** @param {NativeToken} token @returns {token is NativeToken & {type: "inline", children: NativeToken[], lfSource: TokenSource & {beforeLinks: BeforeLink[]}}} */
const isBeforeLinkifiedInline = (token) => token.type === "inline";
/** @param {NativeToken} token @returns {token is NativeToken & {type: "inline", children: NativeToken[], lfSource: TokenSource & {beforeJoin: TokenSnapshot[]}}} */
const isBeforeJoinedInline = (token) => token.type === "inline";

// Native parser tokens, each located in the exact source. Opening inline tokens carry
// the paired construct's whole span and the span of its words for editor decoration.
// Native block rules record markers before container prefixes are restored. Their
// line-relative spans survive newline normalization when mapped onto the source.
/** @typedef {{token: import("markdown-it").Token,
 * from: number, to: number, markers?: [number, number][] | undefined,
 * content?: [number, number],
 * words?: string | null, spelled?: [number, number, string][]}} PlacedToken */
/** Source metadata supplied by the native block producers and the completed placement pass.
 * @typedef {{heading_open: {markers: [number, number][]},
 * fence: {markers: [number, number][]}, blockquote_open: {markers: [number, number][]},
 * list_item_open: {markers: [[number, number], ...[number, number][]], token: NativeToken & {lfSource: TokenSource & {indent: number}}}}} BlockPlacement
 */
/** @template {keyof BlockPlacement} K @param {PlacedToken} placed @param {K} type
 * @returns {placed is PlacedToken & BlockPlacement[K] & {token: NativeToken & {type: K}}} */
export const isBlockPlacement = (placed, type) => placed.token.type === type;

/** @param {string} source @returns {PlacedToken[]} */
export function placedMarkdownTokens(source) {
  const tokens = markdownTokens(source);
  if (!tokens) return [];
  const starts = [0];
  for (let at = 0; at < source.length; at++) {
    if (source[at] === "\r" && source[at + 1] === "\n") at++;
    if (source[at] === "\r" || source[at] === "\n") starts.push(at + 1);
  }
  starts.push(source.length);
  /** @type {PlacedToken[]} */
  const found = [];
  let inlineAt = 0;
  /** @type {NativeToken | undefined} */
  let previous;
  for (const token of tokens) {
    const before = previous;
    previous = token;
    const from = token.map ? parserItem(starts, token.map[0]) : 0;
    const to = token.map ? parserItem(starts, token.map[1]) : source.length;
    if (!isPositionedInline(token)) {
      if (token.map && (token.nesting === 1 || BLOCK_LEAVES.has(token.type))) {
        /** @type {PlacedToken} */
        const placed = {
          token,
          from,
          to,
          markers: token.lfSource?.markers?.map(([line, a, b]) => [
            parserItem(starts, line) + a,
            parserItem(starts, line) + b,
          ]),
          words: token.nesting ? null : token.content,
        };
        found.push(placed);
      }
      continue;
    }
    // Container prefixes precede the inline words; a list marker is not emphasis.
    let wordsAt = Math.max(from, inlineAt);
    for (const block of found)
      if (
        isBlockPlacement(block, "blockquote_open") ||
        isBlockPlacement(block, "list_item_open")
      )
        for (const [a, b] of block.markers)
          if (a >= wordsAt && a < parserItem(starts, token.map[0] + 1) && b > wordsAt)
            wordsAt = b;
    const positions = inlineSourcePositions(
      source,
      token.lfSource.sourceContent,
      wordsAt,
      to,
      before?.type === "td_open" || before?.type === "th_open",
    );
    /** @type {(PlacedToken & {content: [number, number]})[]} */
    const stack = [];
    for (const child of token.children) {
      if (!hasSourceSpan(child)) continue;
      let [a, b] = child.lfSource.source;
      if (child.nesting === 1) {
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          a = b - child.markup.length;
        /** @type {PlacedToken & {content: [number, number]}} */
        const placed = {
          token: child,
          from: parserItem(positions, a),
          to: parserItem(positions, b),
          content: [parserItem(positions, b), parserItem(positions, b)],
        };
        found.push(placed);
        stack.push(placed);
      } else if (child.nesting === -1) {
        const placed = stack.pop();
        if (!placed) continue;
        if (child.markup && child.markup !== "linkify" && child.markup !== "autolink")
          b = a + child.markup.length;
        placed.to = parserItem(positions, b);
        placed.content[1] = parserItem(positions, a);
      } else {
        found.push({
          token: child,
          from: parserItem(positions, a),
          to: parserItem(positions, b),
          words:
            child.type === "softbreak" || child.type === "hardbreak"
              ? "\n"
              : child.type === "image"
                ? admittedUrl(child.attrGet("src")) !== null
                  ? ""
                  : renderedWords(
                      renderInlineMarkdown(
                        source.slice(
                          parserItem(positions, a),
                          parserItem(positions, b),
                        ),
                      ),
                    )
                : child.type === "html_inline"
                  ? ""
                  : child.content,
          spelled: (child.lfSource.spelled ?? []).map(([from, to, shown]) => [
            parserItem(positions, from),
            parserItem(positions, to),
            shown,
          ]),
        });
      }
    }
    inlineAt = parserItem(positions, positions.length - 1);
  }
  return found;
}

// Locate a rendered caret in the parser's leaf token, then align only that token's
// exact source and rendered text. The history diff's bounded whole-document alignment
// is unsuitable here: its deliberate coarse replacement must never send a caret to
// the end of a long formatted document. Token placement gives an ordered source span;
// the local exact alignment handles omitted delimiters, entities and escapes.
/** @param {HTMLElement} body @param {Node} node @param {number} offset */
export function markdownSourceOffset(body, node, offset) {
  if (!body.contains(node)) return null;
  const range = document.createRange();
  range.selectNodeContents(body);
  const shown = fragmentWords(range.cloneContents());
  range.setEnd(node, offset);
  const aim = fragmentWords(range.cloneContents()).length;
  const source = body.dataset.lfSourceWords;
  if (source === undefined) return null;
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

// Whether a rendering taken now is the parser's or the escaped source location in for
// it. A caller that keeps what it painted needs to know which it kept, so the words can
// be given their Markdown once the import lands.
export const markdownReady = () => render !== escapedSource;

const WEB_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

/** @param {string | number | null} href */
function admittedUrl(href) {
  if (href === null) return null;
  href = String(href);
  if (href.startsWith("#")) return href;
  try {
    return WEB_PROTOCOLS.has(new URL(href, location.href).protocol) ? href : null;
  } catch {
    return null;
  }
}

const probe = document.createElement("template");
/** @param {string} markup @param {string} tag */
function renderedElement(markup, tag) {
  probe.innerHTML = markup;
  const element = probe.content.firstElementChild;
  if (!element || element.localName !== tag)
    throw new Error(`leaf: Markdown renderer did not produce its ${tag} element`);
  return element;
}

// Native Markdown tokens are the editor's reading, too. Link admission annotates the
// opening token before it reaches either renderer, so both draw the same safe label.
/** @param {string} text */
const markdownTokens = (text) => tokenize?.(text) ?? null;

// Source spans are recorded where the parser consumes them, before its presentation
// passes join text tokens or recognize bare links. No second Markdown grammar lives
// here: the same native rules decide the renderer's constructs and the editor's.
/** @param {MarkdownIt} markdown */
function sourcePositions(markdown) {
  const NativeState = markdown.inline.State;
  markdown.inline.State = class extends NativeState {
    /** @type {number | null} */
    sourcePendingFrom = null;
    pushPending() {
      const from = this.sourcePendingFrom ?? this.pos - this.pending.length;
      const to = from + this.pending.length;
      const token = super.pushPending();
      token.lfSource = { ...token.lfSource, source: [from, to] };
      this.sourcePendingFrom = null;
      return token;
    }
    /** @param {Parameters<import("markdown-it").StateInline["push"]>} args */
    push(...args) {
      const token = super.push(...args);
      token.lfSource = { ...token.lfSource, sourceAt: this.pos };
      return token;
    }
  };
  const nativeRules = markdown.inline.ruler.getRules.bind(markdown.inline.ruler);
  /** @typedef {(state: import("markdown-it").StateInline, silent: boolean) => boolean} InlineRule */
  /** @type {WeakMap<InlineRule, InlineRule>} */
  const wrapped = new WeakMap();
  markdown.inline.ruler.getRules = (chain) =>
    nativeRules(chain).map((rule) => {
      const known = wrapped.get(rule);
      if (known) return known;
      /** @type {InlineRule} */
      const instrumented = (state, silent) => {
        const from = state.pos;
        const pendingFrom = from - state.pending.length;
        if (!silent && !state.pending) state.sourcePendingFrom = from;
        const count = state.tokens.length;
        const ok = rule(state, silent);
        if (!ok || silent) return ok;
        const emitted = state.tokens
          .slice(count)
          .filter(
            /** @returns {token is NativeToken & {lfSource: TokenSource & {sourceAt: number}}} */ (
              token,
            ) => !token.lfSource?.source,
          );
        let delimiterAt = from;
        for (const token of emitted) {
          /** @type {[number, number]} */
          let span = [from, state.pos];
          if (token.type === "text" && emitted.every((item) => item.type === "text")) {
            span = [delimiterAt, delimiterAt + token.content.length];
            delimiterAt = span[1];
          } else if (token.type === "link_open") {
            span = [from, token.lfSource.sourceAt];
          } else if (token.type === "link_close") {
            span = [token.lfSource.sourceAt, state.pos];
          }
          // A bare URL's inline rule starts at its colon, with the scheme still pending.
          if (
            token.markup === "linkify" ||
            (emitted.some((item) => item.markup === "linkify") && token.type === "text")
          ) {
            const kept = state.tokens
              .slice(count)
              .find((item) => !emitted.some((emitted) => emitted === item));
            const start = kept?.lfSource?.source?.[1] ?? pendingFrom;
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
          token.lfSource = {
            ...token.lfSource,
            source: span,
            spelled:
              token.type === "text_special" && token.content !== token.markup
                ? [[...span, token.content]]
                : token.type === "hardbreak" && state.src[span[0]] === "\\"
                  ? [[span[0], span[0] + 1, ""]]
                  : [],
          };
        }
        return ok;
      };
      wrapped.set(rule, instrumented);
      return instrumented;
    });
  // Joining is a parser optimization. Preserve the first source coordinate when it
  // merges several native text tokens into their final survivor.
  /** @param {TokenSnapshot[]} before @param {NativeToken[]} after */
  const keepJoined = (before, after) => {
    const alive = new Set(after);
    /** @type {[number, number] | null} */
    let first = null;
    /** @type {[number, number, string][]} */
    let spelled = [];
    for (const { token, source, spellings } of before) {
      spelled.push(...spellings);
      // Emphasis combines two delimiter tokens and erases the spare text token.
      // Its source delimiter must not become part of the following joined words.
      if (source && !first && (token.type !== "text" || token.content)) first = source;
      if (alive.has(token)) {
        if (source && first && token.type === "text")
          token.lfSource = { ...token.lfSource, source: [first[0], source[1]] };
        if (token.lfSource) token.lfSource.spelled = spelled;
        first = null;
        spelled = [];
      }
    }
  };
  /** @param {NativeToken[]} tokens @returns {TokenSnapshot[]} */
  const snapshot = (tokens) =>
    tokens.map((token) => ({
      token,
      source: token.lfSource?.source,
      spellings: token.lfSource?.spelled ?? [],
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
      if (isInlineToken(token))
        token.lfSource = { ...token.lfSource, sourceContent: token.content };
  });
  markdown.core.ruler.before("linkify", "source_before_linkify", (state) => {
    for (const token of state.tokens)
      if (isPositionedInline(token)) {
        let inLink = 0;
        token.lfSource.beforeLinks = token.children.map((child, index) => {
          if (child.type === "link_open") inLink++;
          else if (child.type === "link_close") inLink--;
          let source = child.lfSource?.source;
          if (!inLink && source && child.type === "text" && child.content) {
            // Task-list presentation removes its checkbox prefix from the text token.
            // Retain the exact words' source, before linkify splits or normalizes them.
            const raw = token.lfSource.sourceContent.slice(source[0], source[1]);
            const at = raw.indexOf(child.content);
            if (at < 0) throw new Error("leaf: Markdown text token lost its source");
            const box = token.children[index - 1];
            if (at && box?.type === "html_inline")
              box.lfSource = { source: [source[0], source[0] + at] };
            source = [source[0] + at, source[0] + at + child.content.length];
            child.lfSource = { ...child.lfSource, source };
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
      if (isBeforeLinkifiedInline(inline)) {
        const before = inline.lfSource.beforeLinks;
        let at = 0;
        let textAt = 0;
        /** @type {LinkMatch | null} */
        let link = null;
        for (const token of inline.children) {
          if (token.lfSource?.source || before[at]?.token === token) {
            while (at < before.length && parserItem(before, at).token !== token) at++;
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
          /** @type {[number, number]} */
          let span;
          if (token.type === "link_open") {
            link =
              original.links.find(
                (match) =>
                  match.index >= textAt &&
                  markdown.normalizeLink(match.url) === token.attrGet("href"),
              ) ?? null;
            if (!link) throw new Error("leaf: Markdown autolink lost its source");
            textAt = link.index;
            span = [textAt, textAt];
          } else if (token.type === "link_close") {
            if (!link)
              throw new Error("leaf: Markdown autolink closed without its source");
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
          token.lfSource = {
            ...token.lfSource,
            source: [original.source[0] + span[0], original.source[0] + span[1]],
          };
        }
        Reflect.deleteProperty(inline.lfSource, "beforeLinks");
      }
  });
  markdown.core.ruler.before("text_join", "source_before_join", (state) => {
    for (const token of state.tokens)
      if (isPositionedInline(token))
        token.lfSource.beforeJoin = snapshot(token.children);
  });
  markdown.core.ruler.after("text_join", "source_after_join", (state) => {
    for (const token of state.tokens)
      if (isBeforeJoinedInline(token)) {
        keepJoined(token.lfSource.beforeJoin, token.children);
        Reflect.deleteProperty(token.lfSource, "beforeJoin");
      }
  });
}

// The blocks the parser emits whole, with no opening and closing pair.
const BLOCK_LEAVES = new Set(["fence", "hr"]);

/** @param {typeof import("/vendor/markdown-it.esm.js")} module @param {boolean} breaks */
export function makeMarkdown(module, breaks) {
  const markdown = new module.MarkdownIt({ html: false, breaks, linkify: true })
    .disable(["lheading", "code"])
    .use(module.taskLists, { enabled: false });
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
        if (parserItem(lines, at).replace(/^[\s>]*/, "")) break;
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
  /** @param {NativeToken[]} tokens @returns {void} */
  const admitLinks = (tokens) => {
    /** @type {(string | null)[]} */
    const links = [];
    for (const token of tokens) {
      if (token.type === "link_open") {
        const url = admittedUrl(token.attrGet("href"));
        token.lfSource = { ...token.lfSource, url };
        links.push(url);
      } else if (token.type === "link_close") {
        const url = links.pop();
        if (url === undefined)
          throw new Error("leaf: Markdown link closed without its opening");
        token.lfSource = { ...token.lfSource, url };
      }
      // Image labels may contain parsed links or further images. Their inline
      // rendering follows the same URL admission as ordinary document prose.
      if (token.children) admitLinks(token.children);
    }
  };
  markdown.core.ruler.push("safe_links", (state) => {
    for (const block of state.tokens)
      if (isInlineToken(block)) admitLinks(block.children);
  });
  // Nested image labels can retain special text tokens beyond the core's joining
  // pass. Entities and escapes are text there, just as they are in document prose.
  markdown.renderer.rules.text_special = (tokens, at, options, env, renderer) =>
    markdown.utils.escapeHtml(parserItem(tokens, at).content);
  markdown.renderer.rules.link_open = (tokens, at, options, env, renderer) => {
    const token = parserItem(tokens, at);
    const href = token.lfSource?.url;
    if (href === null || href === undefined) return "";
    if (isCanonicalMediaUrl(href)) token.attrSet("href", scopedMediaUrl(href));
    return renderer.renderToken(tokens, at, options);
  };
  markdown.renderer.rules.link_close = (tokens, at, options, env, renderer) => {
    const url = parserItem(tokens, at).lfSource?.url;
    return url !== null && url !== undefined
      ? renderer.renderToken(tokens, at, options)
      : "";
  };
  markdown.renderer.rules.image = (tokens, at, options, env, renderer) => {
    const token = parserItem(tokens, at);
    const href = admittedUrl(token.attrGet("src"));
    if (!token.children) throw new Error("leaf: Markdown image has no parsed label");
    const alt = renderedWords(
      renderer.renderInline(token.children, options, env),
      true,
    );
    token.attrSet("alt", alt);
    if (href === null) return escapeHtml(alt);
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

/** @param {((error: unknown) => void) | null} [onError] */
export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/markdown-it.esm.js").then((module) => {
    const markdown = makeMarkdown(module, true);
    /** @type {MarkdownIt | undefined} */
    let softBreaks;
    /** @type {MarkdownIt | undefined} */
    let positioned;
    /** @param {boolean | undefined} breaks */
    const dialect = (breaks) =>
      breaks ? markdown : (softBreaks ??= makeMarkdown(module, false));
    render = (text, breaks) => dialect(breaks).render(text);
    renderInline = (text, breaks) => dialect(breaks).renderInline(text);
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
