/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights, a
 * link as a link, a heading in bold, a quote and a list item at the message's insets at
 * every level, an item under the message's own marker, a task item's box as the
 * message's disabled checkbox, a rule as the rule, an entity as the character it
 * names, a picture as the picture, drawn after its source while the caret is in it,
 * and a link that leaves the page with the mark the page draws after one
 * (records/declared-words.js). The syntax that produces each (backticks, asterisks, brackets,
 * hashes, list markers, a rule's dashes, an escape's or a break's backslash, an
 * entity's name, a picture's source) is hidden unless the selection touches the
 * construct; the spaces that lead a line, which the message drops, stay hidden. A
 * table and a link's reference definition stay as typed (`DRAWN` in field-editor.js
 * lists what is drawn). List markers reveal their source only inside the marker: the
 * caret after its trailing space is ready to type content, so even an empty new item
 * already shows its bullet or number. The user can move back into the marker to edit every source
 * character. Nothing is converted: the value is always the source, which is what the
 * agent reads, holding what the user typed and the markers and line breaks their keys
 * write. The constructs come from the renderer that sends the message
 * (`markdownTokens`), never from a second grammar, so the preview and the message agree
 * on what is a link, a heading or code, Shift+Enter and pasted code continue the quotes
 * and list items the message will hold, and Tab and Shift+Tab nest a list item and take
 * it out a level.
 * A fence is left as a code span is, by typing its marks, wherever the code's last line
 * ends, and the next words go below it (field-editor.js, `fenceBreak`). Down from the
 * draft's last line leaves it too, and leaves the indented code a body reads
 * (`leaveCode`).
 *
 * A field that edits words where they are shown, as a draft's does over its prose, names
 * the element that shows them (`facesOf`) and draws them in that display's faces
 * instead of the message's: each heading and code block in the type, padding and indent
 * the page gives it there, each quote's inset, and the display's gap between two
 * outermost blocks in place of the blank line that parts them in the source, so no
 * word moves as the editor opens (browser/AGENTS.md, "Editing something keeps it where
 * it stood and as it read"). Such a display is a Markdown body, which reads as a file,
 * so the field draws a line break inside a paragraph as a space, and Return among a
 * paragraph's words writes a hard break, which the body draws as a line too
 * (field-editor.js, `joints`, `newLine`).
 *
 * Every blank line shows. In a run of them between two blocks, the first and last lines
 * stand as the gaps around a paragraph and the rest as its lines (field-editor.js,
 * `standBlocks`). So each Return shows a line, and Return on a blank line or before a
 * paragraph's first words leaves the caret with a blank line on each side, where the
 * words typed next stand as a paragraph of their own (`newLine`). Words typed after one
 * Return move nothing. After two or more, the line above them becomes a gap, and the
 * words below rise by a line less a gap. The display draws a run as one gap, so an
 * owner saves it as one blank line (`valueToSave`) and the words reopen where they
 * read. A source written with a run opens with the run's lines drawn, which moves the
 * words below it down; an agent rarely writes one, and the user takes the move in at a
 * glance. The user chose this for how dependable it is: a line's height follows from
 * the words alone, so no caret move, click or selection lays a run out again.
 * Rejected: one gap shared among a run's lines, which showed nothing for a Return
 * between paragraphs until a word was typed, and then opened the gap under it; a run
 * drawn as lines only while the caret stands in it, whose lines moved as the caret came
 * and went, so a click could land on a moving line. A ¶ on each line saving drops would
 * add a widget beside those lines, and can join this rule later.
 *
 * The cascade answers what those faces are: as the editor builds, and when its width
 * changes, an empty copy of that element holding one of each block stands hidden
 * beside the field, where the page's own rules and density reach it, and is read and
 * removed in the same task. The rules it yields go in a sheet of the field's own, which
 * the classes of the lines and of the quotes' boxes name, so the field draws nothing
 * differently without one. A list's inner gaps, a quote's inner blocks, a rule, a code
 * fence's lines and a table keep the source's lines. So does a setext heading's
 * underline, for which the display draws no line, so opening the editor over one moves
 * the words below it down a line; a draft rarely holds one. Rejected: rules the theme
 * states for each element also stated for parts the field exposes, which can set type
 * but not the gaps, since CodeMirror measures a line without its margins and a gap
 * collapses two blocks'; and a style attribute on each line, which CodeMirror writes
 * again on every redraw.
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
 * That bracket bubbles across enclosing shadow stages, as a textarea's input does.
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
 * It is drawn in the theme's quiet ink (`--lf-quiet`); a box that wants another face for
 * it styles `::part(placeholder)`, which a slotted child inherits. The words are hidden from
 * assistive technology, which reads them as the content node's `aria-placeholder`.
 * A child in slot `end` is a press of the box's own at the placeholder's far end, such
 * as a Resolve's Next thread: it wears the placeholder's face and stands exactly while the
 * words do, the words shorten before it, and it stays in the accessibility tree, beside
 * the textbox rather than in it (below), and takes the pointer, so a press on it is its
 * own and never a press on the field.
 * Rejected: the press among the slotted words, whose `aria-hidden` took it out of the
 * accessibility tree.
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
 * CodeMirror isn't part of the page's opening: it loads once the page has presented
 * (field-editor.js, `loadFieldEditor`), well before a reader usually starts writing, so
 * arriving in a field still builds its editor in the same turn. A field that must build
 * sooner, holding words before then or with the user arriving in it, keeps a rendering
 * hold until CodeMirror arrives, draws its words plain in the empty line's place, and
 * keeps the user's focus there; what they type meanwhile lands natively in that place,
 * which the field reads back as its value, so the editor builds holding it. Rejected:
 * loading CodeMirror with the page, adding its bytes to those before the server's
 * state shows, for a capability most openings never use.
 *
 * The content node inside is the field's one textbox, where focus and assistive
 * technology land: it wears the host's `aria-label`, the placeholder as
 * `aria-placeholder`, whether it holds one line as `aria-multiline`, and the host's
 * description through `ariaDescribedByElements`, the one reference that reaches from
 * inside a shadow root to the page around it. The host is the group around that
 * textbox and the box's own press, and the control accessibility tooling addresses,
 * since nothing outside a closed root sees into it: it takes `role="group"` and a tab
 * stop unless the page gave it its own, and it carries the name, description and busy
 * state the page writes on it. Rejected: the host as a textbox too, which the browser
 * reads the way it reads any textbox that isn't a native one, its slotted words as its
 * value, hidden ones included, and its slotted press as content, so a screen reader
 * heard an empty box hold its placeholder and its press, beside a second textbox.
 *
 * A box whose Send action stands in the field's trailing corner sets
 * `--lf-field-end-room` to the room the action takes beyond the field's end padding.
 * The field keeps that room at the end of every line, so where its words wrap depends
 * only on the words and the box's width, never on which line Send stands beside or on
 * what follows the last word. A sent message that keeps the draft's wrapping keeps the
 * same room. Rejected: the room after the last words only, which ran
 * the lines above under Send's column but made the last line's wrapping turn on the
 * caret's surroundings: an inline spacer after the last word wrapped alone or carried
 * that word with it, so typing a space after a word could pull it back up a line,
 * and it needed separate modes under a finger and while the field scrolled.
 *
 * A box may instead give the words the whole line and set `--lf-field-corner` to the
 * square at the field's trailing foot its action stands in. The field then says
 * whether words in view, or its caret, reach that square (`:state(corner-taken)`), and
 * the box shows its action while the corner is free, and over the words only when
 * focus comes to it or the pointer rests on it. Wrapping still turns on nothing but the words; only the
 * action comes and goes. Under a mouse, Return sends when the action is hidden. A box
 * that stands a key before its action sets `--lf-field-key-corner` to the corner's
 * width with the key, read on the same row (`:state(key-corner-taken)`), so the key
 * gives way to the words as the action does.
 *
 * Leaf's key dispatcher owns submission and Escape. Return inserts a newline unless
 * its owner cancels `lf-edit-return` to reserve the press for submission. Android's
 * EditContext supplies no native insertion after CodeMirror handles the press, so this
 * editing route is explicit. Shift+Enter inserts a line and continues each quote and
 * list item the caret stands in; on a line holding only their markers, it leaves the
 * innermost (`continueBlocks`, field-editor.js). A host the page marks `one-line`,
 * such as an option's title, holds one line: Shift+Enter inserts nothing, a line break
 * pasted or inserted any other way becomes a space, and its owner reserves Return. Mod+Z
 * and Mod+Shift+Z walk one history: the words' edits, and the steps an owner records
 * for what its draft holds beside them (`record`), such as a composer's drawing, each
 * taken back or redone in the order it was made.
 *
 * A key typed in the field stops at the host once the editor and Leaf's key dispatcher
 * have handled it, so the page's listeners never hear it bubble (base/field-keys.js).
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
import { scrollIntoView } from "../../readings/landing-scroll.js";
import { moveScrollerBy } from "../../dom/scrolling.js";
import { TEXT_FIELD } from "../../dom/control-selectors.js";
import { afterPresentation } from "../../readings/presentation.js";
import { loadFieldEditor, readFaces } from "./field-editor.js";
import { inputs } from "../../base/inputs.js";
import { holdRendering } from "../../base/rendering.js";
import { sizeObserver } from "../../lib/frame-pass.js";
import { contentsRects } from "../../lib/shown-box.js";
import { keepFieldKeys } from "../../base/field-keys.js";
import { marksSheet } from "../../base/stylesheets.js";
import type { Box } from "../../base/box.js";
import type { EditorState, TransactionSpec } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import type { FieldConfiguration } from "./field-editor.js";

const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  /* The caret is drawn in the ink of the words it stands in, unless a rule on the
     field gives it another colour, as one on a textarea does. A screenshot's style
     hides it that way where the browser can't hold its blink
     (dev/leaf_dev/browser.py, \`screenshot\`). */
  :host { display: block; cursor: text; caret-color: currentColor; }
  /* CodeMirror's provider places its defaults in lf-base. This control owns the
     unlayered editor face: the host supplies type and colour, caret colour included,
     and these are the only internal padding declarations before Markdown's explicit
     insets below. */
  .cm-editor { font: inherit; color: inherit; background-color: transparent; }
  .cm-editor.cm-focused { outline: none; }
  .cm-scroller { font-family: inherit; line-height: inherit; overflow: visible; }
  .cm-content { padding: 0; caret-color: inherit; min-height: 1lh; }
  /* An empty field draws no editor until the user arrives in it (#build). This box
     holds the empty line's place, as tall as the editor's line, and takes the focus
     that builds the editor; while the editor loads, it holds the words, wrapped as
     the editor wraps them. */
  .lf-field-rest { box-sizing: border-box; width: 100%;
    min-height: 1lh; margin: 0; padding: 0; border: 0; outline: none;
    background: transparent; color: inherit; font: inherit; line-height: inherit;
    letter-spacing: inherit; white-space: pre-wrap; overflow-wrap: break-word;
    resize: none; overflow: hidden; field-sizing: content; }
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
     --lf-field-cut (base.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. The clip
     reaches 2px past that box, the caret's width at a line's end: Firefox paints the
     caret from its offset onward and pulls it inside only a scroll container, so a
     caret after a line that fills the box, as a trailing space can, would be
     cut away whole. Words an owner carries down from above the box, as a line removed
     carries them, need more: it sets --lf-field-reach as far as they travel, and
     stops the host scrolling meanwhile. Chrome refuses calc() here, so the reach
     replaces the caret's margin rather than adding to it, so the owner keeps at
     least 2px there and at the moving content's inline clip edges. */
  .lf-field { overflow: clip; overflow-clip-margin: var(--lf-field-reach, 2px); }
  .lf-field > * {
    translate: var(--lf-field-carry);
    clip-path: inset(var(--lf-field-cut));
  }
  /* The words after a change (data-lf-after, field-editor.js) keep their place from the
     field's end edge, as layout keeps them, so an owner carrying the words by the start
     edge draws these farther by --lf-field-after. */
  .cm-content > [data-lf-after],
  .cm-content > [data-lf-after] ~ * {
    translate: var(--lf-field-after);
  }
  /* The placeholder is one line that never widens the box — a response bar sizes to the
     words — and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; display: flex; align-items: baseline;
    block-size: 1lh; contain: inline-size; color: var(--lf-quiet); }
  .lf-field-placeholder-words { flex: 1 1 auto; min-width: 0; white-space: nowrap;
    overflow-x: clip; text-overflow: ellipsis; }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* The box's own press at the far end takes the pointer where it reads, so while one
     stands the placeholder stands over the empty line; the rest of it passes the
     pointer on to the line beneath, as any placeholder does. A box offers one only
     while its field is empty and the caret is elsewhere (annotations/composing/input.js,
     \`pressAtRest\`), so it stands over no caret. */
  .lf-field-end::slotted(*) { flex: none; pointer-events: auto; }
  :host(:state(end-held)) .lf-field-placeholder { z-index: 1; }
  /* The trailing action's room, on every line. */
  .lf-field { padding-inline-end: var(--lf-field-end-room); }
  /* A draft wears the sent message's faces, or where it stands in place, those its
     display gives each block (\`standBlocks\`), written on its lines over these. Strong,
     emphasis and strikethrough are the elements themselves, which the platform dresses
     here as it does in the message; the rest read the theme's tokens, since its element
     rules stop at this root. A heading is bold, as the platform draws one, at the size
     of the words around it. A block is drawn line by line, so a code block's frame is
     each line's sides, closed above its first line and below its last, and each code
     line hangs the rows it wraps onto from its indent behind the mark, as the sent
     block's lines do (marks.css, \`[data-lf-pre-line]\`).
     Syntax that holds its room while the caret is away, as a rule's or a code fence's
     line does, is there unseen and unspoken. Its glyphs go unfilled while its colour
     stays the words', because the caret can stand at the end of unseen text, as just
     past a new item's marker, and the browser draws it in that text's colour. */
  .lf-md-mark { color: var(--lf-muted); }
  .lf-md-unseen { -webkit-text-fill-color: transparent; }
  code { font-family: var(--lf-mono); font-size: var(--lf-code-inline-size);
    background: var(--lf-chip); border-radius: var(--lf-r-s);
    padding: var(--lf-code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--lf-accent); text-decoration: underline var(--lf-link-underline);
    text-underline-offset: var(--lf-link-underline-offset); }
  /* A quote and a list item are boxes around their lines (field-editor.js, \`box\`), as
     the message's blockquote and li are, so their words stand where the message's do at
     every level of nesting. An item stands one list inset in, under the platform's own
     list marker, as in the message, so it is the same bullet or number at the same
     place: the inset is the item's margin, as it is its list's padding in the message,
     since the platform draws the marker outside the item's border. */
  .lf-md-quote { border-inline-start: var(--lf-quote-rule); font-style: var(--lf-quote-style);
    padding-inline-start: var(--lf-quote-inset); color: var(--lf-muted); }
  .lf-md-item { margin-inline-start: var(--lf-list-inset); }
  /* The source's markers that open a line stand in the insets before its words, each as
     wide as its container's rule and inset, so each stands beside the rule it draws,
     unseen while the caret is away, and revealing one moves no word: their run takes no
     room, and stands back from the words by its own width. */
  .lf-md-markers { display: inline-flex; inline-size: 0; justify-content: flex-end; }
  .lf-md-marker { display: inline-flex; flex: none; justify-content: flex-end;
    white-space: pre; box-sizing: content-box; }
  .lf-md-item-marker { inline-size: var(--lf-list-inset); }
  .lf-md-quote-marker { inline-size: var(--lf-quote-inset);
    border-inline-start: var(--lf-quote-rule); border-inline-start-color: transparent; }
  .lf-md-listed { display: list-item; }
  .lf-md-disc { list-style-type: disc; }
  .lf-md-circle { list-style-type: circle; }
  .lf-md-square { list-style-type: square; }
  .lf-md-number { list-style-type: decimal; }
  .lf-md-code-block { color-scheme: var(--lf-code-scheme, inherit); font-family: var(--lf-mono);
    font-size: var(--lf-code-size);
    line-height: var(--lf-code-line); color: var(--lf-code-ink); background: var(--lf-pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--lf-code-border);
    padding-inline: var(--lf-pre-inset); --lf-pre-line-inset: var(--lf-pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--lf-code-border);
    border-start-start-radius: var(--lf-r); border-start-end-radius: var(--lf-r); }
  .cm-line.lf-md-code-last { border-block-end: 1px solid var(--lf-code-border);
    border-end-start-radius: var(--lf-r); border-end-end-radius: var(--lf-r); }
  /* A picture fits the field as media fits its container on the page, centred on its
     line (base.css), and the mark after a link that leaves the page is the page's
     own (surfaces.css). */
  .lf-md-picture { max-width: 100%; height: auto; vertical-align: middle; }
  /* A rule's line is the sent hr, a line tall with its stroke through the middle
     (reading.css, \`.lf-msg-body hr\`), its source on that line under the caret, so
     reaching it moves nothing (browser/AGENTS.md, "The page holds still under the
     user's aim"). */
  .lf-md-rule {
    background: linear-gradient(var(--lf-rule), var(--lf-rule)) center / 100% 1px no-repeat; }
  /* A press on a task's box reaches the line, which puts the caret in its brackets, as a
     press on any drawn source does; Chromium's disabled box would take it and do
     nothing. */
  .task-list-item-checkbox { pointer-events: none; }
  /* The mark after a link stands beside the link's words, not in them, so it takes
     their colour here. */
  .lf-external-mark { color: var(--lf-accent); }
  /* A fence's line is a line of the code box, the sent pre's padding of one code line
     (reading.css, \`.lf-msg-body pre\`), and an end where no fence line stands, as
     where a fence's container or the draft ends it, where code shares its opening line
     and at both ends of an indented block, takes that padding on the code's own line
     instead. */
  .cm-line.lf-md-code-pad-start { padding-block-start: var(--lf-code-line); }
  .cm-line.lf-md-code-pad-end { padding-block-end: var(--lf-code-line); }
`);

type FieldEditor = Awaited<ReturnType<typeof loadFieldEditor>>;

// The field's editor (field-editor.js), once CodeMirror under it has loaded. It loads as
// soon as the page has presented, as an arrival the page answers for, so a field the
// user arrives in builds its editor in the turn that brings them, as it did when
// CodeMirror loaded with the page; a field that must draw before then asks for it
// sooner.
let editor: FieldEditor | null = null;
const loadEditor = () => loadFieldEditor().then((loaded) => (editor = loaded));
afterPresentation(loadEditor);

// A field's words before it has an editor: the source, the selection, and the steps an
// owner recorded in its history (`record`), which the editor's history takes up as it
// builds.
// `base` is the words the history starts from, which a `value` write sets and the
// user's typing doesn't.
class Draft {
  declare text: string;
  declare base: string;
  declare anchor: number;
  declare head: number;

  steps: [() => void, () => void][] = [];
  constructor(text: string) {
    this.text = this.base = text;
    this.anchor = this.head = text.length;
  }
}

// The last Return and whether it held Shift, which a field without its editor reads: a
// textarea's Return and Shift+Return are both a line break to `beforeinput`
// (`#typeAtRest`). Seen from the window as it goes down, a key typed in a field is the
// field's host's; once dispatched, an event from a shadow tree names no target.
let lastReturn: { field: EventTarget | null; shifted: boolean } | null = null;
inputs.observe((event) => {
  if (event instanceof KeyboardEvent && event.key === "Enter")
    lastReturn = { field: event.target, shifted: event.shiftKey };
});

/** For its tag (`runtime-globals.d.ts`). */
export type LeafTextElement = LeafText;
type FieldView = InstanceType<FieldEditor["LeafEditorView"]>;

class LeafText extends HTMLElement {
  // The field's one model. Until the field has first built an editor it is a Draft;
  // building the editor hands it to the view that edits it from then on (`#build`),
  // and an editor destroyed as the field leaves the page hands back its state, undo
  // history included.
  #content:
    | { kind: "draft"; draft: Draft }
    | {
        kind: "state";
        state: EditorState;
        module: FieldEditor;
      }
    | { kind: "view"; view: FieldView; module: FieldEditor } = {
    kind: "draft",
    draft: new Draft(""),
  };
  get #view() {
    return this.#content.kind === "view" ? this.#content.view : null;
  }
  // The empty line's place while the field has no editor, and the node focus lands on
  // there, whichever route brought it. While the editor loads, it holds the words, plain,
  // and takes what the user types (`#typeAtRest`). It is a textarea: Firefox types into
  // a `contenteditable` that stands after `body`, as the chrome does, but deletes
  // nothing from it, so Backspace did nothing until the editor built
  // (notes/browser-support.md).
  #rest = document.createElement("textarea");
  // The rendering hold of a field waiting for its editor to load (`#build`).
  #waiting: (() => void) | null = null;
  // Whether an input method is composing in the empty line's place. The words it
  // holds are unfinished until it ends, so they join the draft, and the editor builds,
  // only then.
  #composing = false;
  #nativeInput = false;
  #root;
  // The field's custom states, held: WebKit lets the set go, and `states` then reads as
  // a new, empty set while the host still matches the old one's states
  // (notes/browser-support.md, "A custom state set's own contents in WebKit").
  #states = this.attachInternals().states;
  /** The element whose blocks a field editing words where they are shown shows them
   * as, such as a draft's prose; unset, the field draws a sent message's faces. */
  facesOf: HTMLElement | null = null;
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
  #end = document.createElement("slot");
  #frame = document.createElement("div");
  #readOnly = false;
  #sizes = sizeObserver(() => {
    // A new width can set the display's blocks in other faces, as a heading sized to
    // its container's width is.
    this.#readFaces();
    const content = this.#content;
    if (content.kind === "view" && content.view.hasFocus)
      content.view.requestMeasure({
        key: this,
        read: () =>
          this.#rowTravel(
            content.module,
            content.view,
            content.view.state.selection.main.head,
          ),
        write: (travel) => moveScrollerBy(this, travel),
      });
  });

  // How far the host scrolls to show the row holding `pos` whole, its leading as well
  // as the caret, inside the host's padding (see the header). The words wrap, so the
  // host scrolls only down and up.
  #rowTravel(module: FieldEditor, view: EditorView, pos: number) {
    const { destination, rectangle: caret } = module.LeafEditorView.caretAt(view, pos);
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

  // Whether the host's words overflow it (`overflows`), and which edges they run
  // past (`more-above`, `more-below`), read again as the host scrolls, so an owner can
  // show there is more without a scrollbar. The host stops at the page's height limit
  // while words grow inside it, so the reading watches the editor's content too, in the
  // editor's read/write phase. A scroll timeline could fade the edges in CSS, but this
  // reading runs on each scroll anyway for `corner-taken`, so the timeline would add two
  // registered properties and their keyframes and save no work.
  #overflow = sizeObserver(() => this.#measureOverflow());

  #measureOverflow() {
    const content = this.#content;
    if (content.kind !== "view") return;
    content.view.requestMeasure({
      key: this.#overflow,
      // Words, not the host's padding, run past an edge.
      read: (view) => {
        const style = getComputedStyle(this);
        return {
          scrolls: this.scrollHeight > this.clientHeight,
          above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
          below:
            this.scrollTop + this.clientHeight <
            this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1,
          ...this.#cornerTaken(content.module, view, style),
        };
      },
      write: (reading) => {
        const states: readonly (readonly [string, boolean])[] = [
          ["overflows", reading.scrolls],
          ["more-above", reading.scrolls && reading.above],
          ["more-below", reading.scrolls && reading.below],
          ["corner-taken", reading.corner],
          ["key-corner-taken", reading.keyCorner],
        ];
        for (const [state, on] of states) {
          // Adding a state already set restyles all the same, on every scrolled frame.
          if (this.#states.has(state) === on) continue;
          if (on) this.#states.add(state);
          else this.#states.delete(state);
        }
      },
    });
  }

  // Whether words in view, or the caret, reach the square `--lf-field-corner` wide at
  // the host's trailing foot, where a box stands its action over the words. The action
  // stands beside one row, the one across the square's middle, counted at its line
  // height. Rejected: every row whose line box touches the square, since the action
  // is taller than a row, so a row above that ran to the edge hid it beside a short
  // last row, and a new empty line brought it back.
  //
  // The reading answers for the words where layout puts them. An edit that adds or
  // removes a line sets an owner's tween carrying them there from where they were drawn
  // (`--lf-field-carry`), and the reading the edit takes falls inside it, so the square
  // is read where the carry draws it, beside the words it carries. Rejected: reading
  // the words as drawn, which nothing reads again when the tween ends: a line removed
  // left Send over the words the carry brought down to it, and a line added left the
  // corner free with Send hidden.
  //
  // The key a box stands before its action is read on the same row, across the wider
  // `--lf-field-key-corner`, which holds the square.
  #cornerTaken(module: FieldEditor, view: EditorView, style: CSSStyleDeclaration) {
    const size = Number.parseFloat(style.getPropertyValue("--lf-field-corner"));
    if (!(size > 0)) return { corner: false, keyCorner: false };
    const wide = Math.max(
      size,
      Number.parseFloat(style.getPropertyValue("--lf-field-key-corner")) || 0,
    );
    const { scaleX, scaleY } = view;
    const carry = style.getPropertyValue("--lf-field-carry").trim();
    const [dx = 0, dy = 0] =
      carry === "none" ? [] : carry.split(/\s+/).map(Number.parseFloat);
    const at = this.getBoundingClientRect();
    const box = {
      left: at.left + dx * scaleX,
      right: at.right + dx * scaleX,
      bottom: at.bottom + dy * scaleY,
    };
    const rtl = style.direction === "rtl";
    // The span `width` wide in from the field's trailing edge.
    const span = (width: number) =>
      rtl
        ? { left: box.left, right: box.left + width * scaleX }
        : { left: box.right - width * scaleX, right: box.right };
    const square = span(size);
    const withKey = span(wide);
    const top = box.bottom - size * scaleY;
    const middle = box.bottom - (size * scaleY) / 2;
    const reading = { corner: false, keyCorner: false };
    const reach = (rect: Box, leading: number) => {
      if (rect.top - leading > middle || rect.bottom + leading <= middle) return;
      const across = (at: { left: number; right: number }) =>
        rect.left < at.right && rect.right > at.left;
      if (across(square)) reading.corner = true;
      if (across(withKey)) reading.keyCorner = true;
    };
    for (const line of view.contentDOM.children) {
      // A line after the change carries farther than the words' carry
      // (`--lf-field-after`), so it is read back by that much.
      const lineStyle = getComputedStyle(line);
      const [ox = 0, oy = 0] =
        lineStyle.translate === "none"
          ? []
          : lineStyle.translate.split(/\s+/).map(Number.parseFloat);
      const back = (rect: Box) => ({
        left: rect.left - ox * scaleX,
        right: rect.right - ox * scaleX,
        top: rect.top - oy * scaleY,
        bottom: rect.bottom - oy * scaleY,
      });
      const block = back(line.getBoundingClientRect());
      if (block.bottom <= top || block.top >= box.bottom) continue;
      const height = Number.parseFloat(lineStyle.lineHeight) * scaleY;
      for (const rect of contentsRects(line)) {
        reach(back(rect), Math.max(0, (height - rect.height) / 2) || 0);
        if (reading.corner) return reading;
      }
    }
    if (!view.hasFocus) return reading;
    const { rectangle: caret } = module.LeafEditorView.caretAt(
      view,
      view.state.selection.main.head,
    );
    const { left: x, top: y, bottom: foot } = caret;
    reach({ left: x, right: x + 1, top: y, bottom: foot }, 0);
    return reading;
  }

  static observedAttributes = [
    "aria-label",
    "aria-describedby",
    "one-line",
    "placeholder",
  ];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("part", "placeholder");
    const words = document.createElement("span");
    words.className = "lf-field-placeholder-words";
    words.setAttribute("aria-hidden", "true");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    words.append(hint);
    this.#end.name = "end";
    this.#end.className = "lf-field-end";
    this.#end.addEventListener("slotchange", () => {
      if (this.#end.assignedElements().length) this.#states.add("end-held");
      else this.#states.delete("end-held");
    });
    this.#placeholderLayer.append(words, this.#end);
    this.#rest.className = "lf-field-rest";
    this.#rest.rows = 1;
    // Chrome raises a DevTools issue for a form field with neither an id nor a name,
    // which every page's render check would report as the page's. The host keeps
    // whatever name its owner gives it; this node is the field's own, so its name is
    // fixed.
    this.#rest.name = "words";
    // In `focusin`, never `focus`: Chromium, Firefox and WebKit send no `focusin` for
    // a node that passes focus on in its own `focus` handler, and the move inside the
    // closed root reaches nothing outside it, so the page would never hear the field
    // take focus.
    this.#rest.addEventListener("focusin", () => this.#build());
    for (const type of ["beforeinput", "input", "compositionstart", "compositionend"])
      this.#rest.addEventListener(type, (event) => this.#typeAtRest(event));
    this.#frame.append(this.#placeholderLayer, this.#rest);
    this.#root.append(this.#frame);
    this.#dressRest();
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
    // Words dragged in drop where the editor will take them.
    this.addEventListener("dragenter", () => {
      if (!this.#view) this.#build();
    });
    this.addEventListener("scroll", () => this.#measureOverflow(), {
      passive: true,
    });
    this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), {
      capture: true,
    });
    // The content node's own input events would reach the host too, retargeted, and
    // announce every edit twice. The host's is the one the page hears.
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
    keepFieldKeys(this);
  }

  // What the user types before the editor has loaded lands natively in the empty line's
  // place, and the draft takes it from there, words and caret, so the editor builds
  // holding it: read again after each input, as the page's own `input`, and after an
  // input method finishes. Return asks its owner first, as in the editor, whether it
  // may make a new line; Shift+Return, a line break, does unless the field holds one
  // line (`#oneLine`).
  #typeAtRest(event: Event) {
    if (this.#content.kind !== "draft") return;
    if (event.type === "compositionstart") {
      this.#composing = true;
      return;
    }
    if (event instanceof InputEvent && event.type === "beforeinput") {
      if (event.inputType !== "insertLineBreak") return;
      const shifted = lastReturn?.field === this && lastReturn.shifted;
      if ((!shifted && !this.#returned()) || this.#oneLine) event.preventDefault();
      return;
    }
    if (event.type === "compositionend") this.#composing = false;
    else if (this.#composing || (event instanceof InputEvent && event.isComposing))
      return;
    this.#readRest(this.#content.draft);
    this.#paintEmpty();
    this.#emit("input");
    if (event.type === "compositionend" && editor) this.#build();
  }

  // Takes the words and caret of the empty line's place into the draft. A one-line
  // field takes a pasted line break as a space, as its editor does.
  #readRest(draft: Draft) {
    const { value, selectionStart, selectionEnd, selectionDirection } = this.#rest;
    const text = this.#oneLine ? value.replaceAll("\n", " ") : value;
    const backward = selectionDirection === "backward";
    Object.assign(draft, {
      text,
      anchor: backward ? selectionEnd : selectionStart,
      head: backward ? selectionStart : selectionEnd,
    });
    if (text !== value) this.#paintRest();
  }

  // The words a field without an editor shows, plain, in the empty line's place, and,
  // while the user is in it, the draft's caret there.
  #paintRest() {
    if (this.#composing) return;
    const text = this.#view ? "" : this.#text;
    if (this.#rest.value !== text) this.#rest.value = text;
    if (this.#view || this.#root.activeElement !== this.#rest) return;
    const { anchor, head } = this.#range;
    const [start, end] = anchor <= head ? [anchor, head] : [head, anchor];
    const direction = anchor <= head ? "forward" : "backward";
    const rest = this.#rest;
    if (
      rest.selectionStart !== start ||
      rest.selectionEnd !== end ||
      rest.selectionDirection !== direction
    )
      rest.setSelectionRange(start, end, direction);
  }

  #returned() {
    return this.dispatchEvent(new Event("lf-edit-return", { cancelable: true }));
  }

  // The hooks the editor's state calls (`fieldState`).
  #hooks(module: FieldEditor): FieldConfiguration {
    return {
      readOnly: this.#readOnly,
      attributes: this.#contentAttributes(),
      returned: () => this.#returned(),
      oneLine: () => this.#oneLine,
      // Words edited where a Markdown body shows them read as that body does.
      message: () => this.facesOf === null,
      // The caret counts toward the corner only while it shows.
      focused: () => this.#measureOverflow(),
      revealed: (view, pos) => moveScrollerBy(this, this.#rowTravel(module, view, pos)),
      typed: (native, insert) => {
        this.#nativeInput = native;
        try {
          insert();
        } finally {
          this.#nativeInput = false;
        }
      },
    };
  }

  // The field's model as it stands: the editor's state, the state a destroyed editor
  // left, or the draft.
  get #state() {
    const content = this.#content;
    return content.kind === "view"
      ? content.view.state
      : content.kind === "state"
        ? content.state
        : content.draft;
  }
  get #text() {
    const state = this.#state;
    return state instanceof Draft ? state.text : state.doc.toString();
  }
  get #length() {
    const state = this.#state;
    return state instanceof Draft ? state.text.length : state.doc.length;
  }
  // The selection's `anchor` and `head`.
  get #range() {
    const state = this.#state;
    return state instanceof Draft ? state : state.selection.main;
  }

  /** Applies a change to the editor, to the state a destroyed editor left, or, before
   * the field has an editor, to its draft (`draft`). `spec` reads the editor module. */
  #change(
    spec: (module: FieldEditor) => TransactionSpec,
    draft: (draft: Draft) => unknown = () => {},
  ) {
    const content = this.#content;
    if (content.kind === "view") content.view.dispatch(spec(content.module));
    else if (content.kind === "draft") draft(content.draft);
    else
      this.#content = {
        ...content,
        state: content.state.update(spec(content.module)).state,
      };
  }

  attributeChangedCallback(name: string) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    this.#dressRest();
    this.#change((module) => module.contentAttributes(this.#contentAttributes()));
  }

  // A move by `moveBefore` keeps the editor and its focus but collapses the native
  // selection in it, which CodeMirror would read back as a caret at the start. With this
  // callback the move is no disconnection, and the view puts its caret back as it lands.
  connectedMoveCallback() {
    this.#view?.placeSelection();
  }

  connectedCallback() {
    this.toggleAttribute("data-lf-scroll", true);
    // A move by `insertBefore` reconnects within the task, keeping the view
    // (`disconnectedCallback`); the hold that returns the user restores the caret.
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "group");
    // A tab stop, as a textarea is: delegation already stops Tab in the words, and a
    // host reading -1 is one every stop-counting walk would miss.
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#root.adoptedStyleSheets = [sheet, this.#faces, marksSheet];
    if (this.#length) this.#build();
    else this.#describe();
    this.#paintEmpty();
    this.#states.add("ready");
  }

  // Until the field has an editor, its empty line's place stands in for the editor's
  // content node to assistive technology, so the tree reads the same before and after
  // the editor builds. CodeMirror's node is a multiline textbox, read-only while the
  // field is, and it wears the field's name, hint and description (`#describe`). This
  // place, a textarea, is the same, and a tab stop where the editor's node is.
  #dressRest() {
    const wanted = this.#contentAttributes();
    for (const name of ["aria-label", "aria-placeholder"])
      if (!(name in wanted)) this.#rest.removeAttribute(name);
    for (const [name, value] of Object.entries(wanted))
      if (this.#rest.getAttribute(name) !== value) this.#rest.setAttribute(name, value);
    if (this.#rest.readOnly !== this.#readOnly) this.#rest.readOnly = this.#readOnly;
  }

  // A connected field draws its words in an editor, and an empty one builds its editor
  // only when the user arrives in it, by its own `focus()`, a press, or native focus by
  // any route, which lands on the empty line's place, or when words are written into
  // it. Building on arrival hands focus to the words in the same task, so the first key
  // the user types lands in them. A page holding many fields, such as one under each
  // list of options, builds none of them to show itself.
  //
  // Before the editor module has loaded, the field holds a rendering hold and builds
  // the moment it arrives, showing its words plain in the empty line's place until then,
  // with the user's focus there, so what they type meanwhile is the editor's first words
  // (`#typeAtRest`).
  #build() {
    if (this.#content.kind === "view") return;
    if (!editor) {
      this.#paintRest();
      if (this.#waiting) return;
      const release = holdRendering();
      this.#waiting = release;
      // The hold covers the load. An input method still composing as it lands holds
      // the build until it ends, which waits on the user rather than on the page.
      void loadEditor()
        .then(() => this.isConnected && this.#build())
        .finally(() => {
          release();
          this.#waiting = null;
        });
      return;
    }
    // An input method composing in the empty line's place builds the editor as it
    // ends (`#typeAtRest`).
    if (this.#composing) return;
    if (this.#content.kind === "draft" && this.#root.activeElement === this.#rest)
      this.#readRest(this.#content.draft);
    // A field that stands where its words are shown takes their faces from there, read
    // as the editor builds: the field is in place, and nothing has drawn its words yet.
    this.#readFaces();
    const module = editor;
    const view = new module.LeafEditorView({
      root: this.#root,
      parent: this.#frame,
      state:
        this.#content.kind === "draft"
          ? module.fieldState(this.#content.draft, this.#hooks(module))
          : this.#content.state,
      // Dispatched word changes are the user's. The value setter updates the view
      // directly and silently; an owner's `record` changes no words.
      dispatchTransactions: (transactions, view) => {
        const edited = transactions.some((tr) => tr.docChanged);
        if (edited && !this.#nativeInput) this.#beforeEdit();
        view.update(transactions);
        module.runOwnerSteps(transactions);
        this.#paintEmpty();
        this.#measureOverflow();
        if (edited) this.#emit("input");
        else if (transactions.some((tr) => tr.isUserEvent("select")))
          this.dispatchEvent(new Event("lf-caret-move", { bubbles: true }));
      },
    });
    this.#content = { kind: "view", view, module };
    this.#sizes.observe(this);
    this.#overflow.observe(this);
    // The host can keep the same height when a long draft shrinks. Watch the words'
    // box too: its height changes even when the scroller's viewport does not.
    this.#overflow.observe(view.contentDOM);
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    // Focus that landed on the empty line's place moves on into the words, in that
    // place's `focusin`, which goes on to reach the page as the field's.
    if (this.#root.activeElement === this.#rest) {
      view.contentDOM.focus({ preventScroll: true });
      view.placeSelection();
    }
    this.#rest.hidden = true;
    this.#paintRest();
    this.#measureOverflow();
  }

  #emit(type: string) {
    this.dispatchEvent(new Event(type, { bubbles: true, composed: true }));
  }

  #beforeEdit() {
    this.#emit("lf-before-edit");
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#states.delete("ready");
      this.#states.delete("corner-taken");
      this.#states.delete("key-corner-taken");
      const content = this.#content;
      if (content.kind !== "view") return;
      this.#content = {
        kind: "state",
        state: content.view.state,
        module: content.module,
      };
      this.#sizes.disconnect();
      this.#overflow.disconnect();
      content.view.destroy();
      this.#rest.hidden = false;
    });
  }

  #describe() {
    if (!this.isConnected) return;
    const content = this.#view?.contentDOM ?? this.#rest;
    const described = this.ariaDescribedByElements ?? [];
    const current = content.ariaDescribedByElements ?? [];
    if (
      described.length !== current.length ||
      described.some((element, at) => element !== current[at])
    )
      content.ariaDescribedByElements = described;
  }

  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus. While
  // the editor loads, the user stands in the empty line's place.
  focus(options?: FocusOptions) {
    if (!this.isConnected) return;
    this.#build();
    if (this.#view) this.#view.focus();
    else this.#rest.focus({ preventScroll: true });
    if (this.#root.activeElement !== (this.#view?.contentDOM ?? this.#rest)) return;
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }

  blur() {
    (this.#view?.contentDOM ?? this.#rest).blur();
  }

  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  #pressPadding(event: MouseEvent) {
    // A press on the box's own press at the placeholder's end is that press's. The
    // slot is in a closed root, so the event's path seen from the host leaves it out;
    // the press itself is the host's child.
    const target = event.target as Node;
    const onEnd = this.#end.assignedElements().some((press) => press.contains(target));
    if (event.button !== 0 || onEnd) return;
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
    const clamp = (value: number, low: number, high: number) =>
      Math.min(Math.max(value, low), high - 1);
    const at = this.#view.posAtCoords(
      {
        x: clamp(x, area.left, area.right),
        y: clamp(y, area.top, area.bottom),
      },
      false,
    );
    this.#view.focus();
    this.#view.dispatch({ selection: { anchor: at } });
  }

  get #oneLine() {
    return this.hasAttribute("one-line");
  }

  #contentAttributes() {
    const attributes: Record<string, string> = {
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
    if (this.#length) this.#states.delete("placeholder-shown");
    else this.#states.add("placeholder-shown");
  }

  get value(): string {
    return this.#text;
  }

  /** The words as an owner that shows them in `facesOf` saves them: each run of blank
   * lines between two blocks written as one, as the display draws it (field-editor.js,
   * `oneLinePerGap`). Until the editor has built, the field draws no gaps, and these are
   * the words as they stand. */
  get valueToSave() {
    const content = this.#content;
    if (content.kind === "draft") return content.draft.text;
    return content.module.oneLinePerGap(
      content.kind === "view" ? content.view.state : content.state,
    );
  }

  edit(text: string) {
    text = String(text).replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    this.#change(
      () => ({
        changes: { from: 0, to: this.#length, insert: text },
        selection: { anchor: text.length },
        userEvent: "input.dictation",
      }),
      (draft) => {
        if (this.isConnected) this.#beforeEdit();
        draft.text = text;
        draft.anchor = draft.head = text.length;
        if (!this.isConnected) return;
        this.#paintRest();
        this.#paintEmpty();
        this.#emit("input");
      },
    );
  }

  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo: () => void, redo: () => void) {
    this.#change(
      (module) => module.record(undo, redo),
      (draft) => draft.steps.push([undo, redo]),
    );
  }

  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands.
  restartHistory() {
    this.#change(
      (module) => module.forgetHistory,
      (draft) => Object.assign(draft, { steps: [], base: draft.text }),
    );
    this.#change((module) => module.startHistory());
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

  /** As a textarea's, a missing value writes no words: a widget may seed the box from
   * a draft that doesn't exist yet (module-input.md, "Text entry and drafts"). */
  set value(text: string | null | undefined) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    const storage = this.#content;
    if (storage.kind !== "view") {
      this.#content = { kind: "draft", draft: new Draft(text) };
      if (!this.isConnected) return;
      this.#paintRest();
      this.#paintEmpty();
      return;
    }
    // Loading another draft ends the old native composition. Deactivating its
    // attachment resets the platform's replacement range without moving focus.
    const { module, view } = storage;
    const content = view.contentDOM;
    const composing = view.composing && content.editContext;
    if (composing) content.editContext = null;
    // Updating the live view keeps its native input context in sync with the words.
    // Remove and restore history in successive states so the loaded draft starts it
    // empty, while both transactions paint together and announce no user edit.
    const reset = view.state.update({
      changes: { from: 0, to: view.state.doc.length, insert: text },
      selection: { anchor: text.length },
      ...module.forgetHistory,
    });
    const fresh = reset.state.update(module.startHistory());
    view.update([reset, fresh]);
    if (composing) content.editContext = composing;
    this.#paintEmpty();
    this.#measureOverflow();
  }

  get selectionStart() {
    const { anchor, head } = this.#range;
    return Math.min(anchor, head);
  }
  get selectionEnd() {
    const { anchor, head } = this.#range;
    return Math.max(anchor, head);
  }
  get selectionDirection() {
    const { anchor, head } = this.#range;
    return anchor === head ? "none" : head < anchor ? "backward" : "forward";
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(
    start: number,
    end: number,
    direction: "none" | "forward" | "backward" = "none",
  ) {
    const length = this.#length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    const [anchor, head] = direction === "backward" ? [to, from] : [from, to];
    // A draft's caret also stands in its place, where typing lands until the editor
    // builds and which the editor builds from (`#readRest`).
    this.#change(
      () => ({ selection: { anchor, head } }),
      (draft) => {
        Object.assign(draft, { anchor, head });
        this.#paintRest();
      },
    );
  }
  select() {
    this.setSelectionRange(0, this.#length);
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
    this.#change((module) => module.readOnly(this.#readOnly));
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
