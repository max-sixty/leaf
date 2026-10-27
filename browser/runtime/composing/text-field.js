/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights, a
 * link as a link, a heading in bold, a list item at the message's inset under the
 * message's own marker, a picture as the picture, drawn after its source while the
 * caret is in it, and a link that leaves the page with the mark the page draws after
 * one (prepaint.js). The syntax that produces each (backticks, asterisks, brackets,
 * hashes, list markers, a picture's source) is hidden unless the selection touches the
 * construct. List markers reveal their source only inside the marker: the caret after
 * its trailing space is ready to type content, so even an empty new item already shows
 * its bullet or number. The user can move back into the marker to edit every source
 * character. Nothing is converted: the value is always the source the user typed,
 * which is what the agent reads. The constructs come from the renderer that sends the
 * message (`markdownTokens`), never from a second grammar, so the preview and the
 * message agree on what is a link, a heading or code. CodeMirror's own Markdown
 * grammar serves only editing: Shift+Enter continuing a list.
 *
 * A field that edits words where they are shown, as a draft's does over its prose, names
 * the element that shows them (`facesOf`) and draws them in that display's faces
 * instead of the message's: each heading and code block in the type, padding and indent
 * the page gives it there, each outermost block's quote and list insets, and the
 * display's gap between two outermost blocks in place of the blank lines that part them
 * in the source, so no word moves as the editor opens (browser/AGENTS.md, "Editing in
 * place"). The cascade answers what those faces are: as the editor builds, and when its
 * width changes, an empty copy of that element holding one of each block stands hidden
 * beside the field, where the page's own rules and density reach it, and is read and
 * removed in the same task. The rules it yields go in a sheet of the field's own, which
 * the lines' classes name, so the field draws nothing differently without one. A code
 * fence's line and a Setext heading's rule then stand for the block's padding while the
 * caret is away from that line. A list's inner gaps, a quote's inner blocks and a table
 * keep the source's lines. Rejected: rules the theme states for each element also stated
 * for parts the field exposes, which can set type but not the gaps, since CodeMirror
 * measures a line without its margins and a gap collapses two blocks'; and a style
 * attribute on each line, which CodeMirror writes again on every redraw.
 *
 * Focus is the field's own, as a textarea's is. `focus()` puts the user in the words
 * with the caret where it stood, `blur()` takes them out, and a press anywhere in the
 * box's padding puts the caret at the nearest character. The root delegates focus, so a
 * focus that never meets the element's own `focus()` — the platform's, or a test
 * driver's from its isolated world — still lands in the words rather than on a host
 * that takes none; CodeMirror's scroller gives up its tab stop so that it is not the
 * node delegation picks.
 *
 * The root is closed because the field is one control, the way a native textarea is:
 * focus, the scope climb and every `focused() === box` comparison land on the host,
 * never on CodeMirror's content node. Outside, the host answers the textarea members the
 * runtime uses — `value`, the selection triple, `setSelectionRange`, `placeholder`,
 * `readOnly`, `name` — and brackets user edits with `lf-before-edit` and `input`.
 * The first announces the old layout before browser text input or an editor command
 * changes the words; the second announces the updated value and layout. A
 * write to `value` fires nothing, puts the caret at the end, and starts a new undo
 * history, so undo never walks back into a draft the runtime swapped out.
 * `edit(text)` replaces the words as external text input, such as dictation: it keeps
 * undo history and emits the same before-edit/input bracket as native typing.
 * `lf-caret-move` says the user moved the caret or selection without editing, as an
 * arrow key does; a write to the selection triple fires nothing.
 * A box owner that takes pasted pictures intercepts paste in capture; otherwise the field pastes
 * the clipboard's text, including text carried beside a picture.
 * `naturalBlockSize` reads the field's intrinsic border-box block size in CSS pixels,
 * before the host's block size or its minimum and maximum constrain the writing room.
 *
 * The placeholder is a layer under the words, shown while the field is empty. It reads
 * the `placeholder` attribute, and a child in slot `placeholder` stands in its place when
 * a box wants more than one run of text there, such as a label and the key that sends.
 * It is drawn in the theme's muted ink; a box that wants another face for it styles
 * `::part(placeholder)`, which a slotted child inherits.
 *
 * A connected field holding words draws them in its editor. An empty one builds its
 * editor when the user arrives in it (`#build`), since a page can show many empty
 * fields the user never writes in. A field removed and not put back in the same task
 * keeps its state and destroys its editor, which releases the listeners CodeMirror
 * holds on the window and document; reconnecting builds another. `:state(ready)` means
 * the connected field draws its words: in its editor, or as an empty line. A reading
 * surface being replaced can keep its words in flow until then, so measuring the
 * connecting field never collapses the scrollport before it has content.
 *
 * The host is also the control accessibility tooling addresses, since nothing outside a
 * closed root sees into it: it takes `role="textbox"`, `aria-multiline` and a tab stop
 * unless the page gave it its own, and it carries the name, description and busy state
 * the page writes on it. The content node inside is where focus and assistive
 * technology land, so it wears the same `aria-label`, the placeholder as
 * `aria-placeholder`, and the host's description through `ariaDescribedByElements`,
 * the one reference that reaches from inside a shadow root to the page around it.
 *
 * A box whose Send action stands in the field's trailing corner sets
 * `--lf-field-end-room` to the room the action takes beyond the field's end padding.
 * The field keeps that room at the end of every line, so where its words wrap depends
 * only on the words and the box's width, never on which line Send stands beside or on
 * what follows the last word. A sent message that keeps the draft's wrapping keeps the
 * same room. Rejected: the room after the last words only (#1871 to #3678), which ran
 * the lines above under Send's column but made the last line's wrapping turn on the
 * caret's surroundings: an inline spacer after the last word wrapped alone or carried
 * that word with it, so typing a space after a word could pull it back up a line,
 * and it needed separate modes under a finger and while the field scrolled.
 *
 * Leaf's key dispatcher owns submission and Escape. Return inserts a newline unless
 * its owner cancels `lf-edit-return` to reserve the press for submission. Android's
 * EditContext supplies no native insertion after CodeMirror handles the press, so this
 * editing route is explicit. Shift+Enter inserts a line and continues a list or
 * quote. A host the page marks `aria-multiline="false"`, such as an option's title,
 * holds one line: Shift+Enter inserts nothing, a line break pasted or inserted any other
 * way becomes a space, and its owner reserves Return. Mod+Z
 * and Mod+Shift+Z walk one history: the words' edits, and the steps an owner records
 * for what its draft holds beside them (`record`), such as a composer's drawing, each
 * taken back or redone in the order it was made.
 *
 * The host is the textarea's scrollport. CodeMirror's content-sized inner scroller
 * never clips the words; the page sizes the host. The field reveals the caret's whole
 * row, its leading as well as the caret, inside the host's padding, so typing on the
 * last line rests the words at their end with nothing more to scroll to. A native
 * textarea reveals only the caret and leaves its foot's padding, and in Chromium part
 * of the row, out of view. An edit's reveal does this before the view carries the
 * caret out through the page, and when the host's room changes the field reveals its
 * focused caret again under the new constraint: CodeMirror's edit reveal may have
 * preceded the owner's sizing pass, and its own resize observer watches the inner
 * scroller, whose natural height need not change with the host. The resize reveal
 * belongs to the host alone: resizing a focused field does not move a reading pane
 * the user scrolled away from it.
 */
import { scrollIntoView } from "../landing-scroll.js";
import { moveScrollerBy } from "../scrolling.js";
import {
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
} from "../../vendor/codemirror.esm.js";
import { caretAt, LeafEditorView } from "../editor-view.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { loadMarkdown, markdownReady, placedMarkdownTokens } from "../markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "../media.js";
import { sizeObserver } from "../rendering.js";

const insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;

const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* CodeMirror's provider places its defaults in lf-base. This control owns the
     unlayered editor face: the host supplies type and colour, and these are the
     only internal padding declarations before Markdown's explicit insets below. */
  .cm-editor { font: inherit; color: inherit; background-color: transparent; }
  .cm-editor.cm-focused { outline: none; }
  .cm-scroller { font-family: inherit; line-height: inherit; overflow: visible; }
  .cm-content { padding: 0; caret-color: currentColor; min-height: 1lh; }
  /* An empty field draws no editor until the user arrives in it (#build). This box
     holds the empty line's place, as tall as the editor's line, and takes the focus
     that builds the editor. */
  .lf-field-rest { min-height: 1lh; outline: none; }
  .cm-line { padding: 0; }
  /* A space after a line's last word hangs past its end, as in a textarea and in the
     sent message (reading.css, \`.lf-msg-text > p\`), rather than taking room on the
     line and carrying the word to the next one, as CodeMirror's \`break-spaces\`
     does. */
  .cm-editor .cm-content.cm-lineWrapping { white-space: pre-wrap; }
  /* CodeMirror's caret stops beside a widget hang from the text's top, which stands
     above a line set tighter than its type, as a heading's is, and would make that
     line taller than the heading it draws. The field's caret is the platform's. */
  .cm-widgetBuffer { vertical-align: top; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* An owner moving the field's edges can carry the words from where they were with
     them, by the host's --lf-field-carry, and cut them to the box it draws growing, by
     --lf-field-cut (theme.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. The clip
     reaches 2px past that box, the caret's width at a line's end: Firefox paints the
     caret from its offset onward and pulls it inside only a scroll container, so a
     caret after a line that fills the box, as a trailing space can, was
     cut away whole. Words an owner carries down from above the box, as a line removed
     carries them, need more: it sets --lf-field-reach as far as they travel, and
     stops the host scrolling meanwhile. Chrome refuses calc() here, so the reach
     replaces the caret's margin rather than adding to it. */
  .lf-field { overflow: clip; overflow-clip-margin: var(--lf-field-reach, 2px); }
  .lf-field > * {
    translate: var(--lf-field-carry);
    clip-path: inset(var(--lf-field-cut));
  }
  /* The placeholder is one line that never widens the box — a response bar sizes to the
     words — and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; white-space: nowrap;
    contain: inline-size; overflow-x: clip; text-overflow: ellipsis;
    color: var(--muted); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* The trailing action's room, on every line. */
  .lf-field { padding-inline-end: var(--lf-field-end-room); }
  /* A draft wears the sent message's faces, or where it stands in place, those its
     display gives each block (\`standBlocks\`), written on its lines over these. Strong,
     emphasis and strikethrough are the elements themselves, which the platform dresses
     here as it does in the message; the rest read the theme's tokens, since its element
     rules stop at this root. A heading is bold, as the platform draws one, at the size
     of the words around it. A block is drawn line by line, so a code block's frame is
     each line's sides, closed above its first line and below its last. Syntax that holds
     its room while the caret is away, as a code fence's line does, is there unseen and
     unspoken. Its glyphs go unfilled while its colour stays the words', because the
     caret can stand at the end of unseen text, as just past a new item's marker, and the
     browser draws it in that text's colour. */
  .lf-md-mark { color: var(--muted); }
  .lf-md-unseen { -webkit-text-fill-color: transparent; }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset); color: var(--muted);
    --lf-marker-inset: var(--quote-inset); }
  /* A quote's and a list item's words stand where the message's do, and the source's
     marker stands in the inset before them, unseen while the caret is away, so
     revealing it moves no word. A list item's lines stand one list inset in per level,
     under the platform's own list marker, as in the message, so it is the same bullet
     or number at the same place. */
  .lf-md-item { margin-inline-start: calc(var(--lf-list-depth) * var(--list-inset));
    --lf-marker-inset: var(--list-inset); }
  .lf-md-marker { display: inline-flex; justify-content: flex-end; white-space: pre;
    inline-size: var(--lf-marker-inset);
    margin-inline-start: calc(-1 * var(--lf-marker-inset)); }
  .lf-md-listed { display: list-item; }
  .lf-md-disc { list-style-type: disc; }
  .lf-md-circle { list-style-type: circle; }
  .lf-md-square { list-style-type: square; }
  .lf-md-number { list-style-type: decimal; }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  /* A sent pre reserves 8px below its lines for a horizontal scrollbar. */
  .cm-line.lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r);
    padding-block-end: 8px; }
  /* A picture fits the field as media fits its container on the page, centred on its
     line (theme.css), and the mark after a link that leaves the page is the page's
     own (surfaces.css). */
  .lf-md-picture { max-width: 100%; height: auto; vertical-align: middle; }
  .lf-external-mark { display: inline-block; width: 0.75em; height: 0.75em;
    margin-inline-start: 0.24em; vertical-align: 0.03em; color: var(--accent);
    fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round;
    stroke-linejoin: round; overflow: visible; user-select: none;
    -webkit-user-select: none; }
  /* A fence's line, while the caret is away from it, stands for the sent pre's padding,
     and code with no fence lines takes that padding at its ends instead. A field that
     edits in place reads its display's padding over this (\`readFaces\`). */
  .lf-face-fence-open, .lf-face-fence-close { line-height: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-first { padding-block-start: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-last { padding-block-end: calc(var(--pre-pad-block) + 8px); }
`);

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
const marker = Decoration.mark({
  class: "lf-md-marker lf-md-unseen",
  attributes: { "aria-hidden": "true" },
});
const shownMarker = Decoration.mark({ class: "lf-md-marker lf-md-mark" });
const line = (cls) => Decoration.line({ class: cls });
// A list item's line at its depth, wearing the marker a message's list draws there: the
// bullet the platform's style sheet nests, or the item's number in its list. An item's
// later line, and one whose source marker shows, wear none.
const BULLETS = ["lf-md-disc", "lf-md-circle", "lf-md-square"];
const itemLine = (depth, kind, number) =>
  Decoration.line({
    class: kind ? `lf-md-item lf-md-listed ${kind}` : "lf-md-item",
    attributes: {
      style: `--lf-list-depth: ${depth}${kind === "lf-md-number" ? `; counter-set: list-item ${number}` : ""}`,
    },
  });

// The inline constructs the preview draws, by the renderer's token type: each as the
// element the renderer sends it as.
const INLINE = {
  code_inline: Decoration.mark({ tagName: "code" }),
  em_open: Decoration.mark({ tagName: "em" }),
  strong_open: Decoration.mark({ tagName: "strong" }),
  s_open: Decoration.mark({ tagName: "s" }),
};

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. Empty until the renderer has loaded.
const read = (state) => {
  return placedMarkdownTokens(state.doc.toString());
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
function readFaces(field, display) {
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

function decorate(state, placed) {
  const out = [];
  // The ends of the lists open at the token being read, each list line's item, and the
  // code blocks, whose lines their own reading indents.
  const lists = [];
  const items = new Map();
  const code = [];
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
    contentLines,
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
      lines(...contentLines, (each) => {
        out.push(line("lf-md-heading").range(each.from));
      });
      // A Setext heading's rule is a line of its own, which keeps its room unseen while
      // the caret is away, as a fence's does.
      for (const [a, b] of markers) {
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
        const lead = each.text.match(/^[ \t]*/)[0].length;
        add(each.from, each.from + lead - kept.match(/^[ \t]*/)[0].length, hide);
      });
      // A fence's lines stand for the message's code padding (`standBlocks`), and each
      // shows its marks, at a line's height, while the caret is on it.
      for (const [a, b] of markers ?? []) {
        const fence = state.doc.lineAt(a);
        add(a, b, touches(state, fence.from, fence.to) ? dim : unseen);
      }
    } else if (token.type === "blockquote_open") {
      lines(from, to, (each) => {
        out.push(line("lf-md-quote").range(each.from));
      });
      for (const [a, b] of markers)
        add(a, b, touches(state, a, b) ? shownMarker : marker);
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
      // The marker's own indent stands in the inset with it. A quote's line keeps the
      // quote's rule and prefix at its start, where the platform's marker can't stand,
      // so an item there keeps its source marker, drawn as the prefix is.
      const start = at - head.text.slice(0, at - head.from).match(/[ \t]*$/)[0].length;
      if (head.text.slice(0, start - head.from).trim()) {
        add(start, end, dim);
        continue;
      }
      lines(head.to + 1, Math.min(to, state.doc.length), (each) => {
        items.set(each.from, { depth, continued: true });
      });
      const kind =
        list.next === null
          ? BULLETS[Math.min(depth, BULLETS.length) - 1]
          : "lf-md-number";
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
    add(from, from + state.doc.lineAt(from).text.match(/^[ \t]*/)[0].length, hide);
  }
  standBlocks(state, placed, out);
  return Decoration.set(out, true);
}

// Each outermost block's lines name its face, and the lines between two blocks the gap
// the display leaves there: the blank lines that part them in the source, or the
// second's first line where none do. A field that edits in place has rules for the
// names (`readFaces`); elsewhere only a fence's do. A code fence's lines stand for its
// block's padding while the caret is away, and an item after the first in a list stands
// its gap above it. The display trims the outer margins of its first and last blocks,
// so the field leaves none there, but a list's first and last items keep theirs.
const blockTag = (token) =>
  token.type === "fence" || token.type === "code_block" ? "pre" : token.tag;
function standBlocks(state, placed, out) {
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
  for (const { token, from, to, markers, contentLines } of placed) {
    if (!token.block) continue;
    const tag = blockTag(token);
    // A heading and a fence wear their faces wherever they stand.
    if (token.type === "heading_open") {
      lines(...contentLines, (each) => named(each.from, `lf-face-${tag}`));
      if (!token.markup.startsWith("#"))
        for (const [at] of markers)
          if (!lineTouched(at)) named(state.doc.lineAt(at).from, "lf-face-rule");
    } else if (token.type === "fence" || token.type === "code_block") {
      lines(from, to, (each) => named(each.from, "lf-face-code"));
      const opener = state.doc.lineAt(from).number;
      for (const [at] of token.type === "fence" ? markers : []) {
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

// The draft is read by the renderer that will send it, so the preview styles exactly what
// the message will: the same constructs, the same links. The reading is taken again when
// the words change and the styling when the selection moves. The renderer loads lazily;
// until it has, the words stand plain, and its arrival draws every open field.
const livePreview = ViewPlugin.fromClass(
  class {
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

/** @typedef {LeafText} LeafTextElement For its tag (`runtime-globals.d.ts`). */
class LeafText extends HTMLElement {
  // The field's one model. Until the field has an editor it is a bare EditorState,
  // which holds the value, selection and configuration without a DOM; building the
  // editor hands it to the view that edits it from then on (`#build`).
  #model;
  #view = null;
  // The empty line's place while the field has no editor, and the node focus lands on
  // there, whichever route brought it.
  #rest = document.createElement("div");
  #nativeInput = false;
  #root;
  #internals = null;
  #editable = new Compartment();
  #history = new Compartment();
  #attributes = new Compartment();
  /** The element whose blocks a field editing words where they are shown shows them
   * as, such as a draft's prose; unset, the field draws a sent message's faces.
   * @type {Element | null} */
  facesOf = null;
  // The rules that draw the words in its blocks' faces (`readFaces`), as last read.
  #faces = new CSSStyleSheet();
  #facesRead = "";
  #readFaces() {
    if (!this.facesOf?.isConnected || !this.isConnected) return;
    const rules = readFaces(this, this.facesOf);
    if (rules === this.#facesRead) return;
    this.#facesRead = rules;
    this.#faces.replaceSync(rules);
  }
  #placeholderLayer = document.createElement("div");
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;
  #sizes = sizeObserver(() => {
    // A new width can set the display's blocks in other faces, as a heading sized to
    // its container's width is.
    this.#readFaces();
    const view = this.#view;
    if (view?.hasFocus)
      view.requestMeasure({
        key: this,
        read: () => this.#rowTravel(view, view.state.selection.main.head),
        write: (travel) => moveScrollerBy(this, travel),
      });
  });

  // How far the host scrolls to show the row holding `pos` whole, its leading as well
  // as the caret, inside the host's padding (see the header). The words wrap, so the
  // host scrolls only down and up.
  #rowTravel(view, pos) {
    const { destination, rectangle: caret } = caretAt(view, pos);
    const node =
      destination instanceof Range ? destination.startContainer : destination;
    const row =
      (node instanceof Element ? node : node.parentElement)?.closest(".cm-line") ??
      this;
    const { scaleY } = view;
    const leading =
      Math.max(
        0,
        (parseFloat(getComputedStyle(row).lineHeight) * scaleY -
          (caret.bottom - caret.top)) /
          2,
      ) || 0;
    const style = getComputedStyle(this);
    const box = this.getBoundingClientRect();
    const top = box.top + (this.clientTop + parseFloat(style.paddingTop)) * scaleY;
    // client dimensions round fractional CSS sizes. Keep the bottom on the actual box,
    // inset by its native border and scrollbar.
    const bottom =
      box.bottom -
      (this.offsetHeight -
        this.clientTop -
        this.clientHeight +
        parseFloat(style.paddingBottom)) *
        scaleY;
    const travel =
      (Math.min(0, caret.top - leading - top) +
        Math.max(0, caret.bottom + leading - bottom)) /
      scaleY;
    // Native scroll offsets quantize a fractional correction. Round away from zero so
    // a row just beyond an edge actually enters.
    return travel < 0 ? Math.floor(travel) : Math.ceil(travel);
  }

  // Whether the host's words overflow it (`data-scrolls`), and which edges they run
  // past (`more-above`, `more-below`), read again as the host scrolls, so an owner can
  // show there is more without a scrollbar. The host stops at the page's height limit
  // while words grow inside it, so the reading watches the editor's content too, in the
  // editor's read/write phase. A scroll timeline would say it in CSS alone, but Firefox
  // lacks scroll timelines.
  #overflow = sizeObserver(() => this.#measureOverflow());

  #measureOverflow() {
    this.#view?.requestMeasure({
      key: this.#overflow,
      // Words, not the host's padding, run past an edge.
      read: () => {
        const style = getComputedStyle(this);
        return {
          scrolls: this.scrollHeight > this.clientHeight,
          above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
          below:
            this.scrollTop + this.clientHeight <
            this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1,
        };
      },
      write: (reading) => {
        // WebKit can retain style from a removed custom state after the words shrink.
        // An attribute invalidates the field's CSS at the same layout boundary.
        if (this.hasAttribute("data-scrolls") !== reading.scrolls)
          this.toggleAttribute("data-scrolls", reading.scrolls);
        for (const [state, on] of [
          ["more-above", reading.scrolls && reading.above],
          ["more-below", reading.scrolls && reading.below],
        ]) {
          // Adding a state already set restyles all the same, on every scrolled frame.
          if (this.#internals.states.has(state) === on) continue;
          if (on) this.#internals.states.add(state);
          else this.#internals.states.delete(state);
        }
      },
    });
  }

  static observedAttributes = ["aria-label", "aria-describedby", "placeholder"];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    this.#placeholderLayer.setAttribute("part", "placeholder");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    this.#placeholderLayer.append(hint);
    this.#rest.className = "lf-field-rest";
    // The break an empty editable line holds, as the editor's own empty line does, so
    // the place reads the same value to assistive technology.
    this.#rest.append(document.createElement("br"));
    // In `focusin`, never `focus`: Chrome and Firefox send no `focusin` for a node that
    // passes focus on in its own `focus` handler, and the move inside the closed root
    // reaches nothing outside it, so the page would never hear the field take focus.
    this.#rest.addEventListener("focusin", () => this.#build());
    this.#frame.append(this.#placeholderLayer, this.#rest);
    this.#root.append(this.#frame);
    this.#model = this.#create("");
    this.#dressRest();
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
    // Words dragged in drop where the editor will take them.
    this.addEventListener("dragenter", () => {
      if (!this.#view) this.#build();
    });
    this.addEventListener("scroll", () => this.#measureOverflow(), { passive: true });
    this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), {
      capture: true,
    });
    // The content node's own input events would reach the host too, retargeted, and
    // announce every edit twice. The host's is the one the page hears.
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
  }

  // A fresh state holding `text`, caret at its end, under the field's current
  // configuration. A new state is also a new undo history.
  #create(text) {
    return EditorState.create({
      doc: text,
      selection: { anchor: text.length },
      extensions: [
        // DOM input has already changed the words when CodeMirror reads it, so its
        // bracket started at beforeinput. EditContext leaves rendering to the editor;
        // its transactions, like commands, still start before the DOM changes.
        EditorView.inputHandler.of((view, _from, _to, _text, insert) => {
          this.#nativeInput = !view.contentDOM.editContext;
          try {
            view.dispatch(insert());
          } finally {
            this.#nativeInput = false;
          }
          return true;
        }),
        // An edit's reveal shows the caret's row in the host first; the view's own
        // reveal (editor-view.js) then carries the caret out through the page.
        EditorView.scrollHandler.of((view, range) => {
          moveScrollerBy(this, this.#rowTravel(view, range.head));
          return false;
        }),
        this.#history.of(history()),
        // A one-line field holds one line, so a line break pasted or inserted by the
        // platform, as Android's editing does, becomes a space.
        EditorState.transactionFilter.of((tr) => {
          if (!tr.docChanged || !this.#oneLine) return tr;
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
          // A one-line field takes no line break (`#oneLine`).
          { key: "Shift-Enter", run: () => this.#oneLine },
          {
            key: "Enter",
            run: (view) =>
              this.dispatchEvent(new Event("lf-edit-return", { cancelable: true })) &&
              insertNewline(view),
          },
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
        this.#editable.of(EditorState.readOnly.of(this.#readOnly)),
        this.#attributes.of(EditorView.contentAttributes.of(this.#contentAttributes())),
      ],
    });
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    this.#dressRest();
    this.#apply({
      effects: this.#attributes.reconfigure(
        EditorView.contentAttributes.of(this.#contentAttributes()),
      ),
    });
  }

  // A move by `moveBefore` keeps the editor and its focus but collapses the native
  // selection in it, which CodeMirror would read back as a caret at the start. With this
  // callback the move is no disconnection, and the view puts its caret back as it lands.
  connectedMoveCallback() {
    this.#view?.placeSelection();
  }

  connectedCallback() {
    this.classList.toggle("scroll", true);
    // A move by `insertBefore` reconnects within the task, keeping the view
    // (`disconnectedCallback`); the hold that returns the user restores the caret.
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    // A tab stop, as a textarea is: delegation already stops Tab in the words, and a
    // host reading -1 is one every stop-counting walk would miss.
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#internals ??= this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet, this.#faces];
    if (this.#model.doc.length) this.#build();
    else this.#describe();
    this.#paintEmpty();
    this.#internals.states.add("ready");
  }

  // Until the field has an editor, its empty line's place stands in for the editor's
  // content node to assistive technology, so the tree reads the same before and after
  // the editor builds. CodeMirror's node is a multiline textbox, `contenteditable` (its
  // theme makes it plain text only) and `aria-readonly` while the field is read-only,
  // and it wears the field's name, hint and description (`#describe`). This place
  // declares the same, and being editable it is a tab stop where the editor's node is.
  #dressRest() {
    const wanted = {
      ...this.#contentAttributes(),
      role: "textbox",
      contenteditable: "plaintext-only",
      ...(this.#readOnly && { "aria-readonly": "true" }),
    };
    for (const name of ["aria-label", "aria-placeholder", "aria-readonly"])
      if (!(name in wanted)) this.#rest.removeAttribute(name);
    for (const [name, value] of Object.entries(wanted))
      if (this.#rest.getAttribute(name) !== value) this.#rest.setAttribute(name, value);
  }

  // A connected field draws its words in an editor, and an empty one builds its editor
  // only when the user arrives in it, by its own `focus()`, a press, or native focus by
  // any route, which lands on the empty line's place, or when words are written into
  // it. Building on arrival hands focus to the words in the same task, so the first key
  // the user types lands in them. A page holding many fields, such as one under each
  // list of options, builds none of them to show itself.
  #build() {
    // A field that stands where its words are shown takes their faces from there, read
    // as the editor builds: the field is in place, and nothing has drawn its words yet.
    this.#readFaces();
    this.#view = new LeafEditorView({
      root: this.#root,
      parent: this.#frame,
      state: this.#model,
      // Dispatched word changes are the user's. The value setter updates the view
      // directly and silently; an owner's `record` changes no words.
      dispatchTransactions: (transactions, view) => {
        const edited = transactions.some((tr) => tr.docChanged);
        if (edited && !this.#nativeInput) this.#beforeEdit();
        view.update(transactions);
        for (const tr of transactions)
          if (tr.isUserEvent("undo") || tr.isUserEvent("redo"))
            for (const effect of tr.effects)
              if (effect.is(ownerStep)) effect.value.run();
        this.#paintEmpty();
        this.#measureOverflow();
        if (edited) this.dispatchEvent(new Event("input", { bubbles: true }));
        else if (transactions.some((tr) => tr.isUserEvent("select")))
          this.dispatchEvent(new Event("lf-caret-move", { bubbles: true }));
      },
    });
    this.#model = null;
    this.#sizes.observe(this);
    this.#overflow.observe(this);
    // The host can keep the same height when a long draft shrinks. Watch the words'
    // box too: its height changes even when the scroller's viewport does not.
    this.#overflow.observe(this.#view.contentDOM);
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    // Focus that landed on the empty line's place moves on into the words, in that
    // place's `focusin`, which goes on to reach the page as the field's.
    if (this.#root.activeElement === this.#rest) {
      this.#view.contentDOM.focus({ preventScroll: true });
      this.#view.placeSelection();
    }
    this.#rest.hidden = true;
    this.#measureOverflow();
  }

  #beforeEdit() {
    this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#internals.states.delete("ready");
      if (!this.#view) return;
      this.#model = this.#view.state;
      this.#sizes.disconnect();
      this.#overflow.disconnect();
      this.#view.destroy();
      this.#view = null;
      this.#rest.hidden = false;
    });
  }

  #describe() {
    if (!this.isConnected) return;
    const content = this.#view?.contentDOM ?? this.#rest;
    const root = /** @type {Document | ShadowRoot} */ (this.getRootNode());
    const described = (this.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => root.getElementById(id))
      .filter(Boolean);
    const current = content.ariaDescribedByElements ?? [];
    if (
      described.length !== current.length ||
      described.some((element, at) => element !== current[at])
    )
      content.ariaDescribedByElements = described;
  }

  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus.
  focus(options) {
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) return;
    this.#view.focus();
    if (this.#root.activeElement !== this.#view.contentDOM) return;
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }

  blur() {
    this.#view?.contentDOM.blur();
  }

  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  #pressPadding(event) {
    if (event.button !== 0) return;
    if (!this.#view) {
      // The field is empty, so wherever the press lands the caret stands at its start.
      // Another button's press focuses the empty line's place natively, which builds the
      // editor before the press's own action, such as a context menu's, reads its target.
      event.preventDefault();
      this.focus({ preventScroll: true });
      return;
    }
    const area = this.#view.scrollDOM.getBoundingClientRect();
    const { clientX: x, clientY: y } = event;
    if (x >= area.left && x < area.right && y >= area.top && y < area.bottom) return;
    event.preventDefault();
    const clamp = (value, low, high) => Math.min(Math.max(value, low), high - 1);
    const at = this.#view.posAtCoords(
      { x: clamp(x, area.left, area.right), y: clamp(y, area.top, area.bottom) },
      false,
    );
    this.#view.focus();
    this.#view.dispatch({ selection: { anchor: at } });
  }

  get #state() {
    return this.#view?.state ?? this.#model;
  }

  #apply(spec) {
    if (!this.#view && spec.changes && this.isConnected) this.#build();
    if (this.#view) this.#view.dispatch(spec);
    else this.#model = this.#model.update(spec).state;
  }

  get #oneLine() {
    return this.getAttribute("aria-multiline") === "false";
  }

  #contentAttributes() {
    const attributes = {
      spellcheck: "true",
      autocorrect: "on",
      autocapitalize: "sentences",
      "aria-multiline": String(!this.#oneLine),
    };
    if (this.placeholder) attributes["aria-placeholder"] = this.placeholder;
    const label = this.getAttribute("aria-label");
    if (label !== null) attributes["aria-label"] = label;
    return attributes;
  }

  #paintEmpty() {
    if (this.#state.doc.length) this.#internals.states.delete("placeholder-shown");
    else this.#internals.states.add("placeholder-shown");
  }

  get value() {
    return this.#state.doc.toString();
  }

  edit(text) {
    text = String(text).replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    this.#apply({
      changes: { from: 0, to: this.#state.doc.length, insert: text },
      selection: { anchor: text.length },
      userEvent: "input.dictation",
    });
  }

  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo, redo) {
    this.#apply({
      effects: ownerStep.of({ run: redo, back: undo }),
      annotations: isolateHistory.of("full"),
    });
  }

  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands. Dropping the history's field and adding it back
  // starts it empty.
  restartHistory() {
    this.#apply({ effects: this.#history.reconfigure([]) });
    this.#apply({ effects: this.#history.reconfigure(history()) });
  }

  get naturalBlockSize() {
    const host = getComputedStyle(this);
    return (
      parseFloat(getComputedStyle(this.#frame).blockSize) +
      parseFloat(host.paddingBlockStart) +
      parseFloat(host.paddingBlockEnd) +
      parseFloat(host.borderBlockStartWidth) +
      parseFloat(host.borderBlockEndWidth)
    );
  }

  set value(text) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) {
      this.#model = this.#create(text);
      return;
    }
    // Loading another draft ends the old native composition. Deactivating its
    // attachment resets the platform's replacement range without moving focus.
    const content = this.#view.contentDOM;
    const composing = this.#view.composing && content.editContext;
    if (composing) content.editContext = null;
    // Updating the live view keeps its native input context in sync with the words.
    // Remove and restore history in successive states so the loaded draft starts it
    // empty, while both transactions paint together and announce no user edit.
    const reset = this.#view.state.update({
      changes: { from: 0, to: this.#view.state.doc.length, insert: text },
      selection: { anchor: text.length },
      effects: this.#history.reconfigure([]),
    });
    const fresh = reset.state.update({
      effects: this.#history.reconfigure(history()),
    });
    this.#view.update([reset, fresh]);
    if (composing) content.editContext = composing;
    this.#paintEmpty();
    this.#measureOverflow();
  }

  get selectionStart() {
    return this.#state.selection.main.from;
  }
  get selectionEnd() {
    return this.#state.selection.main.to;
  }
  get selectionDirection() {
    const { main } = this.#state.selection;
    return main.empty ? "none" : main.head < main.anchor ? "backward" : "forward";
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(start, end, direction = "none") {
    const length = this.#state.doc.length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    this.#apply({
      selection:
        direction === "backward"
          ? { anchor: to, head: from }
          : { anchor: from, head: to },
    });
  }
  select() {
    this.setSelectionRange(0, this.#state.doc.length);
  }

  get placeholder() {
    return this.getAttribute("placeholder") ?? "";
  }
  set placeholder(text) {
    this.setAttribute("placeholder", text);
  }

  get readOnly() {
    return this.#readOnly;
  }
  set readOnly(on) {
    this.#readOnly = Boolean(on);
    this.#dressRest();
    this.#apply({
      effects: this.#editable.reconfigure(EditorState.readOnly.of(this.#readOnly)),
    });
  }

  get name() {
    return this.getAttribute("name") ?? "";
  }
  set name(value) {
    this.setAttribute("name", value);
  }
}

if (!customElements.get(TEXT_FIELD)) customElements.define(TEXT_FIELD, LeafText);

export const textField = () => document.createElement(TEXT_FIELD);
