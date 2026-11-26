/* Leaf's Markdown dialect: one reading of Markdown to HTML, in a message's reading and
   a file's (`renderMarkdown`), the words a rendering shows (`markdownWords`), and the
   source offset under a caret in a rendering (`markdownSourceOffset`). Python reads the
   same dialect (`leaf.source.passages.markdown_dialect`), and the shared case files
   (`tests/*markdown*_cases.json`, `tests/message_html_cases.json`) hold the two to the
   same words.

   A renderer returns an HTML string, such as for Lit's `unsafeHTML`;
   `inlineMarkdownFragment` and `markdownFileFragment` return a fragment and
   `paintMarkdown` writes into an element. Each is safe for any source, since it shows a
   tag as the words that spell it, except `renderAuthoredMarkdown`, which keeps raw HTML,
   and `markdownFileFragment`, which keeps a file's HTML but its script. A destination the reading
   doesn't admit leaves its words and no link. The caller passes `links`
   (`MarkdownLinks`), which say how to write each link and picture the reading admits:
   `{}` writes each as the source wrote it, and a Leaf page's are `pageLinks`, from
   `/runtime/widget-api.js`.

   The parser stays lazy, since most pages hold no Markdown supplied at runtime. Until
   it loads, each renderer returns the escaped source; `loadMarkdown()` resolves once it
   has, and `markdownReady()` says whether it has, so a widget showing changing prose
   paints again then. */
import { alignText } from "./text-alignment.js";

/** How a host writes the links and pictures a reading admits. `link(href)` gives
 * attributes for a link's opening tag, an `href` among them taking the written one's
 * place. `picture(image)` gives the node to write for an image the reading built: the
 * image, changed or not, or an element holding it. The image stands in an inert
 * document, where the browser fetches nothing, so `picture` makes any element it adds
 * in `image.ownerDocument`: one from the live `document` would adopt the image there and
 * fetch its source. Only the markup of what `picture` returns is kept.
 * @typedef {{link?: (href: string) => Record<string, string> | undefined,
 *   picture?: (image: HTMLImageElement) => Element}} MarkdownLinks */

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
/** @type {(text: string, links: MarkdownLinks, message: boolean) => string} */
let render = escapedSource;
/** @type {(text: string, links: MarkdownLinks, message: boolean) => string} */
let renderInline = escapedSource;
/** @type {(text: string, links: MarkdownLinks) => string} */
let renderAuthored = escapedSource;
/** @type {(text: string) => Promise<string>} */
let renderFile = async (text) => escapedSource(text);
/** @type {((source: string, message: boolean) => NativeToken[]) | null} */
let tokenize = null;
/** @type {Promise<void> | undefined} */
let ready;

// `message` picks the reading. A message keeps each line break its writer typed, and
// reads neither a line's leading spaces as code nor a `---` under a line as a heading's
// underline, since a person typing a message rarely means either; a fence is a
// message's one way to write code, and the words on its opening line are that code's
// first line, unless one word names the language of the code below (`fence_words`). A
// Markdown file reads as CommonMark and GitHub
// render a file: a soft line break is a space, since a file's lines wrap for its editor
// rather than its reader, four spaces after a blank line open code, and a line of `=`
// or `-` underlines a heading. A Markdown body (`paintMarkdown`), such as a draft,
// reads as a file.
/** @param {string} text @param {MarkdownLinks} links @param {boolean} [message] */
export const renderMarkdown = (text, links, message = true) =>
  render(text, links, message);
// An agent's message holding HTML (`html` on its served message) reads as a message
// that keeps the raw HTML in it, as Python checked it (`leaf.source.passages.message_markup`),
// so it is for markup its caller has already checked. Every other reading shows a tag
// as the words that spell it, since what the user types is no markup Leaf checked. The
// HTML reads by CommonMark's rules, as GitHub reads a comment's, which agents already
// write to. Rejected: a widget's block running past blank lines to its closing tag,
// and a `<code>` holding its words as written, since no author knows either rule from
// Markdown.
/** @param {string} text @param {MarkdownLinks} links */
export const renderAuthoredMarkdown = (text, links) => renderAuthored(text, links);
// A Markdown file with the HTML its author wrote, so a README's folds, pictures, styles
// and centred headers draw. DOMPurify's defaults take out what would run script, which
// would act as the user on the page, and elements HTML doesn't define, such as Leaf's
// widgets, whose controls would act for the page. A `data-` attribute goes
// too, since Leaf's own marks are spelled so, and a file's would speak for Leaf. Only a
// file's preview reads a file so. A draft's body shows a tag as the words that spell
// it, since the server draws a body too (`leaf.source.passages.markdown_markup`) and
// has no sanitizer. The host's `links` apply after the sanitizer, to each link and
// picture of the file's HTML as of its Markdown, so what they add is the host's.
/** @param {string} text @param {MarkdownLinks} links @returns {Promise<DocumentFragment>} */
export async function markdownFileFragment(text, links) {
  const parsed = document.createElement("template");
  parsed.innerHTML = await renderFile(text);
  for (const link of parsed.content.querySelectorAll("a[href]"))
    for (const [name, value] of Object.entries(
      links.link?.(/** @type {string} */ (link.getAttribute("href"))) ?? {},
    ))
      link.setAttribute(name, value);
  // An image of an HTML `<picture>` stays its own, since its sources choose among
  // themselves only while it stands in the `<picture>`.
  const picture = links.picture;
  if (picture)
    for (const image of parsed.content.querySelectorAll("img")) {
      if (image.parentElement?.localName === "picture") continue;
      // `picture` may move the image into what it returns, so that takes its place.
      const place = image.ownerDocument.createTextNode("");
      image.before(place);
      place.replaceWith(picture(image));
    }
  return parsed.content;
}
// The words a user sees in rendered Markdown, for a surface that shows them as plain
// text: an excerpt, a label, a passage. Until the parser lands they are the source.
// With `imageAlt`, an image counts as the words its control is named by, its alt text,
// else Image.
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
      image.replaceWith(document.createTextNode(image.alt || "Image"));
  return fragment.textContent;
}
// A host's `links` change where a link or picture leads, never its words, so the words
// take none.
/** @param {string} text @param {boolean} [message] the reading (`renderMarkdown`) */
export const markdownWords = (text, message = true) =>
  renderedWords(renderMarkdown(text, {}, message));
/** @param {string} text @param {MarkdownLinks} links @param {boolean} [message] */
export const renderInlineMarkdown = (text, links, message = true) =>
  renderInline(text, links, message);
// Passage readings recognize the fragment's semantic <br> as visible separation.
/** @param {string} text @param {MarkdownLinks} links @param {boolean} [message] */
export function inlineMarkdownFragment(text, links, message = true) {
  const parsed = document.createElement("template");
  parsed.innerHTML = renderInlineMarkdown(text, links, message);
  return parsed.content;
}

// Keep the exact source on its reading surface, as `data-lf-source-words`, so a click
// on the rendering finds its place in the source (`markdownSourceOffset`). Passage
// capture reads the rendered children; revision
// comparison reads source, so formatting never becomes state. An element stamped with
// this source already holds its rendering and is left as it is; a paint before the
// parser loads leaves the element unstamped, so the next paint renders. The body reads
// as a Markdown file (`renderMarkdown`), as the server's prepaint draws it
// (`leaf.source.passages.markdown_markup`) and the field editing it in place reads it
// (annotations/composing/field-editor.js, `read`).
/** @param {Element} element @param {string} source @param {MarkdownLinks} links */
export function paintMarkdown(element, source, links) {
  if (element.getAttribute("data-lf-source-words") === source) return;
  const markup = renderMarkdown(source, links, false);
  if (markdownReady()) element.setAttribute("data-lf-source-words", source);
  else element.removeAttribute("data-lf-source-words");
  if (element.innerHTML !== markup) element.innerHTML = markup;
}

const characters = new Intl.Segmenter(undefined, { granularity: "grapheme" });
// Align within the parser's declared block span, rather than reimplement its block
// normalization. That normalization can both remove prefixes and expand a tab into
// spaces. The shared lossless aligner maps either transformation back to source.
/** @param {string} source @param {string} raw @param {number} at @param {number} limit @param {boolean} cell */
function inlineSourcePositions(source, raw, at, limit, cell) {
  // A verbatim block ends with its words, past the opening markers. A cell's words are
  // the first on its row past the cell before it, spelled with a `\` before each `|`:
  // the table reads `\|` as a pipe in a cell's words, and a bare `|` as one between
  // cells.
  const span = source.slice(at, limit);
  const spelled = cell ? raw.replaceAll("|", "\\|") : raw;
  const start =
    at + (cell ? span.indexOf(spelled) : span.trimEnd().length - raw.length);
  if (start >= at && source.startsWith(spelled, start)) {
    const positions = [start];
    let sourceAt = start;
    for (let i = 0; i < raw.length; i++)
      positions.push((sourceAt += cell && raw[i] === "|" ? 2 : 1));
    return positions;
  }
  // Even an empty inline token has one boundary.
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

/** @param {string} source @param {boolean} [message] the reading (`renderMarkdown`)
 * @returns {PlacedToken[]} */
export function placedMarkdownTokens(source, message = true) {
  const tokens = markdownTokens(source, message);
  if (!tokens) return [];
  const starts = [0];
  for (let at = 0; at < source.length; at++) {
    if (source[at] === "\r" && source[at + 1] === "\n") at++;
    if (source[at] === "\r" || source[at] === "\n") starts.push(at + 1);
  }
  starts.push(source.length);
  /** @type {PlacedToken[]} */
  const found = [];
  // The blockquotes and list items open around the token, outermost first. Only their
  // markers can stand on an inline's first line, so an inline reads these rather than
  // every block placed before it.
  /** @type {(PlacedToken | null)[]} */
  const open = [];
  let inlineAt = 0;
  /** @type {NativeToken | undefined} */
  let previous;
  /** @type {[number, number] | null} */
  let row = null;
  for (const token of tokens) {
    const before = previous;
    previous = token;
    if (token.type === "tr_open") row = token.map;
    // A table cell's words name no lines of their own; they stand on their row's.
    const map = token.map ?? (isPositionedInline(token) ? row : null);
    const from = map ? parserItem(starts, map[0]) : 0;
    const to = map ? parserItem(starts, map[1]) : source.length;
    if (!isPositionedInline(token)) {
      /** @type {PlacedToken | null} */
      const placed =
        token.map && (token.nesting === 1 || BLOCK_LEAVES.has(token.type))
          ? {
              token,
              from,
              to,
              markers: token.lfSource?.markers?.map(([line, a, b]) => [
                parserItem(starts, line) + a,
                parserItem(starts, line) + b,
              ]),
              words: token.nesting ? null : token.content,
            }
          : null;
      if (placed) found.push(placed);
      if (token.type === "blockquote_open" || token.type === "list_item_open")
        open.push(placed);
      else if (token.type === "blockquote_close" || token.type === "list_item_close")
        open.pop();
      continue;
    }
    // Container prefixes precede the inline words; a list marker is not emphasis.
    let wordsAt = Math.max(from, inlineAt);
    for (const block of open)
      if (
        block &&
        map &&
        (isBlockPlacement(block, "blockquote_open") ||
          isBlockPlacement(block, "list_item_open"))
      )
        for (const [a, b] of block.markers)
          if (a >= wordsAt && a < parserItem(starts, map[0] + 1) && b > wordsAt)
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
                        {},
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
// the local exact alignment handles omitted delimiters, entities and escapes. `body`
// holds the rendering of `source`, read as a Markdown file.
/** @param {HTMLElement} body @param {string} source @param {Node} node @param {number} offset */
export function markdownSourceOffset(body, source, node, offset) {
  if (!body.contains(node)) return null;
  const range = document.createRange();
  range.selectNodeContents(body);
  const shown = fragmentWords(range.cloneContents());
  range.setEnd(node, offset);
  const aim = fragmentWords(range.cloneContents()).length;
  let shownAt = 0;
  let sourceEnd = 0;
  for (const placed of placedMarkdownTokens(source, false)) {
    const { token, from, to } = placed;
    if (token.nesting) continue;
    const words = placed.words;
    if (!words) continue;
    const start = shown.indexOf(words, shownAt);
    if (start < 0) continue;
    if (aim < start) return from;
    if (aim <= start + words.length) {
      // A fence's code starts on the line after its opening marker, whose info string
      // can spell the code's first word, as `sh` does in a fence of shell commands.
      let sourceAt = token.type === "fence" ? lineAfter(source, from) : from;
      let tokenAt = start;
      for (const run of alignText(
        source.slice(sourceAt, to),
        words,
        characters,
        Infinity,
      )) {
        // A caret before an escaped first character stands before its backslash, which
        // a key there would split from the character.
        if (run.kind === "delete") {
          if (aim === tokenAt && placed.spelled?.some(([a]) => a === sourceAt))
            return sourceAt;
          sourceAt += run.text.length;
        } else {
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

/** Where the line after the one holding `at` starts. @param {string} source @param {number} at */
function lineAfter(source, at) {
  const ending = /\r\n|\r|\n/g;
  ending.lastIndex = at;
  return ending.exec(source) ? ending.lastIndex : source.length;
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
  return WEB_PROTOCOLS.has(URL.parse(href, location.href)?.protocol ?? "")
    ? href
    : null;
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
/** @param {string} text @param {boolean} message */
const markdownTokens = (text, message) => tokenize?.(text, message) ?? null;

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

// A render's `links` ride in the parser's per-render `env`, which markdown-it hands
// every rule, the nested renders of an image's label included.
/** @param {unknown} env @returns {MarkdownLinks | undefined} */
const linksOf = (env) =>
  /** @type {{links?: MarkdownLinks} | undefined} */ (env)?.links;

// The blocks the parser emits whole, with no opening and closing pair.
const BLOCK_LEAVES = new Set(["fence", "code_block", "hr"]);

// Each code span between a text's closing `$` and the next text's opening one, before
// text joining, while an escaped `\$` is still a token of its own.
/** @param {import("markdown-it").StateCore} state */
function inlineFormulas(state) {
  for (const block of state.tokens) {
    if (!isInlineToken(block)) continue;
    const children = block.children;
    for (let at = 1; at < children.length - 1; at++) {
      const [before, code, after] = children.slice(at - 1, at + 2);
      if (
        code?.type !== "code_inline" ||
        before?.type !== "text" ||
        after?.type !== "text" ||
        !before.content.endsWith("$") ||
        !after.content.startsWith("$")
      )
        continue;
      before.content = before.content.slice(0, -1);
      after.content = after.content.slice(1);
      code.attrJoin("class", "language-math");
      // The dollars are the formula's markers, as its backticks are, in the reading that
      // places tokens in the source (`sourcePositions`), so a field editing the file
      // treats them as it does the backticks.
      code.markup = "$" + code.markup;
      const [a, b, c] = [before, code, after].map((token) => token.lfSource?.source);
      if (a && b && c && before.lfSource && code.lfSource && after.lfSource) {
        before.lfSource.source = [a[0], a[1] - 1];
        code.lfSource.source = [b[0] - 1, b[1] + 1];
        after.lfSource.source = [c[0] + 1, c[1]];
      }
    }
  }
}

// The sanitizer of a file's HTML (`markdownFileFragment`), loaded for the first file
// that holds some (`holdsHtml`).
/** @type {Promise<import("dompurify").DOMPurify> | undefined} */
let purifier;
const sanitizer = () =>
  (purifier ??= import("/vendor/purify.esm.js").then(
    ({ DOMPurify }) => DOMPurify,
    (error) => {
      // A later draw tries again, as a failed parser load does (`loadMarkdown`).
      purifier = undefined;
      throw error;
    },
  ));

/** @param {NativeToken} token @returns {boolean} */
const holdsHtml = (token) =>
  token.type === "html_block" ||
  token.type === "html_inline" ||
  Boolean(token.children?.some(holdsHtml));

// The parser for a reading (`renderMarkdown`, `renderAuthoredMarkdown`), which
// passages.py reads the same (`markdown_dialect`).
/** @param {typeof import("/vendor/markdown-it.esm.js")} module @param {boolean} message
 * @param {boolean} [html] */
export function makeMarkdown(module, message, html = false) {
  const markdown = new module.MarkdownIt({
    html,
    breaks: message,
    linkify: true,
  }).use(module.taskLists, { enabled: false });
  if (message) {
    markdown.disable(["lheading", "code"]);
    // CommonMark takes all of a fence's opening line as its info string and shows none
    // of it, so a person who typed or pasted code after the marks lost those words. Only
    // one word over code below it stays a language. Rejected: a label on the box for
    // every info string, which would caption each block an agent names a language for.
    markdown.core.ruler.after("block", "fence_words", (state) => {
      for (const token of state.tokens) {
        const words = token.info.trim();
        if (token.type !== "fence" || !words) continue;
        if (token.content && !/\s/.test(words)) continue;
        token.content = `${words}\n${token.content}`;
        token.info = "";
        const opening = token.lfSource?.markers?.[0];
        if (opening) opening[2] = opening[1] + token.markup.length;
      }
    });
  }
  // A file's inline formula is GitHub's: a code span with a `$` against each of its
  // backticks, as in $`x^2`$. It draws as the page writes a formula, a code span in
  // the math language (readings/formulas.js), without the dollars. An escaped `\$`
  // beside a code span leaves it code. Left out: GitHub's bare `$x$`, whose dollars
  // GitHub tells from prices by rules of its own.
  if (!message)
    markdown.core.ruler.before("text_join", "file_formulas", inlineFormulas);
  // A bare domain is indistinguishable from a file name such as setup.py. Require
  // an explicit URL or Markdown link instead of inventing an external destination.
  markdown.linkify.set({ fuzzyLink: false });
  // Each block of a message says how many blank lines stand before it in the source,
  // a quote's `>` aside, so the message spaces its blocks as the draft it was typed in
  // showed them (reading.css, `data-lf-gap`). Three stand for any more. A file draws
  // each run of blank lines as one gap, so its blocks say nothing, and a message's
  // spacing doesn't reach a file shown inside it, such as a draft's body.
  if (message)
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
  markdown.renderer.rules.text_special = (tokens, at) =>
    markdown.utils.escapeHtml(parserItem(tokens, at).content);
  markdown.renderer.rules.link_open = (tokens, at, options, env, renderer) => {
    const token = parserItem(tokens, at);
    const href = token.lfSource?.url;
    if (href === null || href === undefined) return "";
    for (const [name, value] of Object.entries(linksOf(env)?.link?.(href) ?? {}))
      token.attrSet(name, value);
    return renderer.renderToken(tokens, at, options);
  };
  markdown.renderer.rules.link_close = (tokens, at, options, _env, renderer) => {
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
    const picture = linksOf(env)?.picture;
    // The image stands in the parser's inert template document, where its source
    // isn't fetched, and only the markup of what `picture` returns is kept.
    return picture
      ? picture(/** @type {HTMLImageElement} */ (renderedElement(markup, "img")))
          .outerHTML
      : markup;
  };
  return markdown;
}

/** @param {((error: unknown) => void) | null} [onError] */
export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/markdown-it.esm.js").then((module) => {
    const markdown = makeMarkdown(module, true);
    /** @type {MarkdownIt | undefined} */
    let file;
    /** @param {boolean | undefined} message */
    const dialect = (message) =>
      message ? markdown : (file ??= makeMarkdown(module, false));
    render = (text, links, message) => dialect(message).render(text, { links });
    renderInline = (text, links, message) =>
      dialect(message).renderInline(text, { links });
    /** @type {MarkdownIt | undefined} */
    let authored;
    renderAuthored = (text, links) =>
      (authored ??= makeMarkdown(module, true, true)).render(text, { links });
    /** @type {MarkdownIt | undefined} */
    let fileHtml;
    renderFile = async (text) => {
      const parser = (fileHtml ??= makeMarkdown(module, false, true));
      const env = { links: {} };
      const tokens = parser.parse(text, env);
      const markup = parser.renderer.render(tokens, parser.options, env);
      return tokens.some(holdsHtml)
        ? (await sanitizer()).sanitize(markup, { ALLOW_DATA_ATTR: false })
        : markup;
    };
    /** @type {Map<boolean, MarkdownIt>} */
    const positioned = new Map();
    tokenize = (text, message) => {
      let parser = positioned.get(message);
      if (!parser) {
        parser = makeMarkdown(module, message);
        sourcePositions(parser);
        positioned.set(message, parser);
      }
      return parser.parse(text, {});
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
