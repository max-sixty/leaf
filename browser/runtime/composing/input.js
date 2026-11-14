// One helper wires every durable composition surface: the general box, each per-thread
// reply, the compact anchored composer, and composition boxes contributed by widgets.
// `wireInput` gives every such text field one input contract: persist each edit, keep the
// action button and placeholder current, prevent parallel submissions of one local
// surface (an impatient second click), and submit with Enter on a physical keyboard. A
// press on a submit control is that Enter, pressed from the box.
// Shift+Enter inserts a line, the field's own binding; on touch keyboards Enter does too,
// except in a one-line field (`aria-multiline="false"`), where Return sends everywhere.
// Mod+Enter remains another route to submit. The field grows with its words, within the
// room supplied by floating placement; script does not derive its height from its text. When the surface
// accepts images, a paste or capture uploads bytes to page media; one that does not says
// so in a notice, so no box answers an image with silence. The draft keeps the resulting
// Markdown, while the field shows only the user's words and a thumbnail projection.
// An upload completion changes that draft; it is not another typing or focus gesture.
// The field retains focus while read-only, and completion preserves wherever the user
// has moved since the attachment began.
// So the box holds more than its .value, and wire() returns the seam that says so:
// sync.value() reads the complete draft, sync.addMedia() attaches images, sync.load()
// replaces it — a stored record, a draft mirrored from another tab, or the emptiness a
// send leaves — and sync() says the box's standing changed. Outside this module,
// .value is the user's words alone and
// nothing writes it.
// The submit binding owns the shortcut spelling used by the placeholder and tooltip.
//
// An error about a box (errors.js, its `subject`), such as a refused send's whose words
// came back to it or an image it would not take, stands over the box's words and
// actions, wrapping within its lines, until the user comes back to them: an edit there,
// an image attached, a press on the cover or a key there, a send key or a press putting
// the caret at the words' end and sending nothing, or Resume writing (drafts.js). While it stands the box sends nothing, so words the user
// has not seen again are never sent. The error is about the words, not the node, so it
// also passes once the box stops showing them: it takes up another draft (`arrive`), as
// the one passage composer does on each passage, or it is hidden or leaves the page
// (`unshown`). Every box takes this from here, the floating panel's field and a
// passage's comment box alike, and a passed error waits in the leaf's menu.
//
// Lit owns the generated field, hint, errors and action controls. The native editor is
// retained as a Node part: rendering chrome never replaces its words, caret or history.
// Local draft callbacks request Lit updates; shared readings subscribe
// through SignalWatcher, including focus and errors, without a repaint registry.
import { capitalized, counted } from "../words.js";
import { describeFailure } from "../exception.js";
import { rememberWriting } from "../drafts.js";
import { keys, paintKeysWithin } from "../keyboard/scopes.js";
import { keeps } from "../keeps.js";
import {
  advertisesKeys,
  ariaBindings,
  submitBindings,
  spell,
} from "../keyboard/bindings.js";
import { readAttachedMedia, scopedMediaUrl, writeAttachedMedia } from "../media.js";
import { announce, keepsNotice } from "../notifications.js";
import { selectableOffered } from "../element-markers.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  neutralSteps,
} from "../keyboard/key-sequence.js";
import { drawingThumbnail } from "./drawing-context.js";
import {
  LitElement,
  html,
  render,
  SignalWatcher,
  signal,
  computed,
  nothing,
  guard,
  ref,
  untracked,
} from "/runtime/framework.js";
import "./text-field.js";
import { followBoxGrowth, readBoxPlace } from "../thread/reply-landing.js";
import { focusDestination, focused, focusRevision } from "../focus.js";
import { whileConnected } from "../arrivals.js";
import { errorsReading, passErrorsAt, raiseError } from "../errors.js";
import { sizeObserver } from "../rendering.js";
import { scrollIntoView } from "../landing-scroll.js";
import { retainUserIntent } from "../user-intent.js";
import { coarsePointer } from "../pointer.js";
import { offeredAction } from "../widget-elements.js";

/** @typedef {import("./drawing-record.js").DraftDrawing} Drawing
 * @typedef {import("./text-field.js").LeafTextElement} TextField
 * @typedef {(text: string, raw: string, stillCurrent: () => boolean, typed: string) => unknown} Sender
 * @typedef {{word: string, keys: readonly string[], run: () => unknown}} BoxPress
 * @typedef {Object} InputOptions
 * @property {import("../keyboard/bindings.js").Cell<string>} hint
 * @property {(() => unknown) | null} [hintParts]
 * @property {() => unknown} [hintLead]
 * @property {() => string | BoxPress} [enters]
 * @property {import("../keyboard/bindings.js").Cell<string> | null} [accessibleName]
 * @property {(value: string) => unknown} save
 * @property {Sender} send
 * @property {string} [sendClass]
 * @property {import("../keyboard/bindings.js").Cell<string>} sends
 * @property {import("../keyboard/bindings.js").Cell<string>} [action]
 * @property {string | null} [altLabel]
 * @property {Sender | null} [altSend]
 * @property {() => true | string} [allowsMedia]
 * @property {() => boolean} [busy]
 * @property {(raw: string) => boolean} [hasContent]
 * @property {{read: () => Drawing | null, target: () => Element | null, replace: (drawing: Drawing | null) => unknown, undoStroke: () => unknown, remove: () => unknown} | null} [drawing]
 * @property {readonly import("../keyboard/bindings.js").Command[]} [rows]
 * @property {HTMLElement | null} [submitIn]
 * @property {boolean} [sentMedia]
 * @typedef {{(): void, value: () => string, hasMedia: () => boolean,
 * arrive: () => void, load: (value: string) => void, button: HTMLButtonElement | null,
 * composition: () => {field: HTMLElement, frame: CompositionField}, addMedia: (images: readonly Blob[]) => Promise<boolean>}} InputSync
 * @typedef {TextField & {[INPUT_DRAFT]?: InputSync}} WiredInput
 */

const INPUT_DRAFT = Symbol("composition draft");
// What Shift+Return does in a box that holds lines, as its hint and Send's tooltip say it.
const NEW_LINE = "New line";
// How long the pointer rests on Send's corner, once words reach it, before Send takes
// presses there: longer than a press aimed at the words' end takes to land.
const SEND_DWELL = 150;

/** @typedef {CompositionField} CompositionFieldElement For its tag. */
class CompositionField extends SignalWatcher(LitElement) {
  createRenderRoot() {
    return this;
  }
  // A send can settle after its row left. Do not reconnect signal subscriptions
  // for a detached view; connection requests the next draw when it returns.
  shouldUpdate() {
    return this.isConnected || !this.hasUpdated;
  }

  // Wiring configures Lit's hooks and flushes the initial controls before returning.
  render() {
    return super.render();
  }
  updated() {}
  performUpdate() {
    super.performUpdate();
  }
}
customElements.define("leaf-composition-field", CompositionField);

// Another tab's copy of a drawing is a different object holding the same strokes.
/** @param {Drawing | null} a @param {Drawing | null} b */
const sameDrawing = (a, b) => a === b || JSON.stringify(a) === JSON.stringify(b);
let thumbnailVersion = 0;

// What the draft carries beside its words: the drawing a stroke attached, then each attached
// image. Each shows itself rather than its transport and each comes off with its own
// control, so nothing rides along with a comment unseen or beyond the user's reach. The
// drawing also takes back its last stroke here: the route a pointer or a finger has to
// that, wherever the composer stands.
/** @param {{drawing: {record: Drawing, target: Element | null, undoStroke: () => unknown, removeDrawing: () => unknown} | null, media: {index: number, url: string}[], sent: boolean, removeMedia: (index: number) => unknown}} options */
function mediaTemplate({ drawing, media, sent, removeMedia }) {
  const strokes = drawing?.record.strokes.length ?? 0;
  return [
    drawing
      ? html`
          <span class="lf-composer-media-item lf-composer-drawing">
            <button
              type="button"
              ${offeredAction("picture", "lf-media-open lf-composer-media-open")}
              data-lf-frame
              data-lf-media-canvas
              aria-label=${`Inspect drawing, ${counted(strokes, "stroke")}`}
              title="Inspect drawing"
              @click=${
                /** @param {MouseEvent & {currentTarget: HTMLButtonElement & {firstElementChild: HTMLCanvasElement}}} event */ (
                  event,
                ) => {
                  const canvas = event.currentTarget.firstElementChild;
                  keeps(
                    event.currentTarget,
                    "data-lf-media-alt",
                    canvas.dataset.lfDrawingContext === "ready"
                      ? "Drawing over its frozen page context"
                      : "Drawing",
                  );
                  keeps(
                    event.currentTarget,
                    "data-lf-media-caption",
                    canvas.dataset.lfDrawingContext === "ready"
                      ? ""
                      : canvas.dataset.lfDrawingContext === "pending"
                        ? "Drawing only; page preview was not ready when opened."
                        : "Drawing only; page preview unavailable.",
                  );
                }
              }
            >
              ${guard([JSON.stringify(drawing.record), drawing.target], () => {
                const canvas = drawingThumbnail(drawing.record, drawing.target);
                // Pixels do not appear in markup. Give each new picture an identity
                // so DOM readers distinguish its changed ink.
                canvas.dataset.lfDrawingVersion = String(++thumbnailVersion);
                return canvas;
              })}
            </button>
            <button
              ${offeredAction("mark", "lf-composer-drawing-undo", "Undo last stroke", {
                action: "undo",
              })}
              data-lf-corner
              @mousedown=${
                /** @param {MouseEvent} event */ (event) => event.preventDefault()
              }
              @click=${drawing.undoStroke}
            ></button>
            <button
              ${offeredAction("mark", "", "Remove drawing", { action: "remove" })}
              data-lf-corner
              @mousedown=${
                /** @param {MouseEvent} event */ (event) => event.preventDefault()
              }
              @click=${drawing.removeDrawing}
            ></button>
          </span>
        `
      : null,
    media.map(({ index, url }) => {
      const remove = html`<button
        ${offeredAction(
          "mark",
          "lf-composer-media-remove",
          `Remove attached image ${index + 1}`,
          { action: "remove" },
        )}
        data-lf-corner
        @click=${() => removeMedia(index)}
      ></button>`;
      // A sent message's picture is the one its message draws (markdown.js, the image
      // rule), in a paragraph of its own as the message sets it, with the removal mark
      // a rewrite adds.
      return sent
        ? html`<p class="lf-composer-media-item">
            <button
              type="button"
              ${offeredAction("picture", "lf-media-open lf-message-media")}
              data-lf-media-url=${url}
              aria-label=${`View attached image ${index + 1}`}
            >
              <img src=${url} alt="" /></button
            >${remove}
          </p>`
        : html`<span class="lf-composer-media-item">
            <button
              type="button"
              ${offeredAction("picture", "lf-media-open lf-composer-media-open")}
              data-lf-frame
              data-lf-media-url=${url}
              aria-label=${`View attached image ${index + 1}`}
            >
              <img src=${url} alt="" /></button
            >${remove}
          </span>`;
    }),
  ];
}

// A wired field's visible value omits generated image Markdown. Readers outside
// this module ask through this seam for the complete draft; an unwired box keeps
// its ordinary value.
/** @param {(Element & {value?: string | null, [INPUT_DRAFT]?: InputSync}) | null | undefined} ta */
export const draftOf = (ta) => ta?.[INPUT_DRAFT]?.value() ?? ta?.value ?? "";
// Ask a wired field to paint again, as its own `sync()` does, where what its hint or
// name reads has changed and the caller holds the field rather than its wiring.
/** @param {(Element & {[INPUT_DRAFT]?: InputSync}) | null | undefined} ta */
export const syncInput = (ta) => ta?.[INPUT_DRAFT]?.();
// The newest error about a box the user has not come back to, which covers its words.
/** @param {Element} ta */
const errorOver = (ta) =>
  errorsReading().find((error) => error.subject === ta && !error.passed) ?? null;
// Whether an error stands at a box, which says it there; the panel's dot marks only
// those that stand nowhere. A box that stops showing the words passes its errors, so a
// standing one is always on screen.
/** @param {ReturnType<typeof errorsReading>[number]} error */
export const standsAtItsBox = (error) => {
  /** @type {(Element & {[INPUT_DRAFT]?: InputSync}) | null | undefined} */
  const subject = error.subject;
  return Boolean(subject?.[INPUT_DRAFT]) && !error.passed;
};
// A box's own press at rest (`enters`, `BoxPress`), at its placeholder's far end, the
// field's `end` slot (text-field.js), as the entering word and its key are, so it
// stands exactly while the box's words do and reads in their face. Its mousedown keeps
// the caret and focus where they are, and the press keeps the notice that offers it
// (notifications.js, `keepsNotice`). The keyboard's route is the press's own command
// and a finger's is this, so it takes no tab stop.
/** @param {BoxPress} press @param {readonly string[]} keys */
const pressAtRest = (press, keys) =>
  html`<span
    slot="end"
    ${selectableOffered("button", "lf-compose-press", "inline")}
    data-lf-hint
    tabindex="-1"
    ${keepsNotice()}
    @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
    @click=${press.run}
    ><span class="lf-compose-press-word">${press.word}</span>${
      keys.length ? keySequenceTemplate(keySequenceModel(neutralSteps(keys))) : nothing
    }</span
  >`;

// Boot binds one input owner to the app's upload command and contextual-hint
// reading. Fields keep those capabilities for their lifetime; importing this module
// never installs or replaces application callbacks.
/** @param {{uploadMedia: (blob: Blob) => Promise<string | null>, inputHint: () => {box: Element | null, label: string} | null}} options */
export function createCompositionInputs({ uploadMedia, inputHint }) {
  // Contextual destinations include geometry the application reads in its repaint.
  // Publish those two values; each field reads them with its other reactive inputs.
  /** @type {import("@preact/signals-core").Signal<Element | null>} */
  const hintedBox = signal(null);
  const hintLabel = signal("");
  // A box's press says its key only while that key would make it (floating-panel.js,
  // `noticePress`), which the dispatcher decides from focus and the keys' liveness
  // rather than from anything a box reads, so this frame reads each standing press
  // again, as it gives every box the comment key's destination, and repaints a box
  // whose press now reads otherwise than it drew.
  /** @type {Map<CompositionField, () => boolean>} */
  const pressing = new Map();
  const publishInputHint = () => {
    const hint = inputHint();
    hintedBox.value = hint?.box ?? null;
    hintLabel.value = hint?.label ?? "";
    for (const [field, moved] of pressing)
      if (!field.isConnected) pressing.delete(field);
      else if (moved()) field.requestUpdate();
  };
  // `sends` states the box's own submit action, and `action` the symbol its control
  // shows. Composers send by default; a caller whose action differs, such as adding an
  // option, names that action, and one whose action turns on what the box holds, as an
  // emptied rewrite deletes its message, answers both as it stands.
  /** @param {WiredInput} ta @param {InputOptions} options */
  function wireInput(
    ta,
    {
      hint,
      // A structured visual hint can mark the exact words its owner observes. It
      // shares the existing placeholder slot and send key; null keeps the plain hint.
      hintParts = null,
      // Words that stand before the hint while it does, such as whose turn it is, which
      // send the hint and its key to the empty box's far end and move none of its
      // controls as they come and go.
      hintLead = () => "",
      // What entering the box does, said with the key that enters it, where the box's
      // own words at rest say something else, as the panel's status does. Those words
      // stay first, and this word and its key stand after them, in a part of its own,
      // so the words never move between parts as focus comes and goes. Or, as a
      // `BoxPress`, the one press the box offers at rest in that place, such as a
      // passing notice's Undo: its word and the keys of the command that makes it, read
      // as the entering word and its key are, and pressed where they read, by a pointer
      // or a finger, since it stands where the box's own words do and goes when they go
      // (`pressAtRest`). A finger is shown its word alone, as no key is shown there.
      enters = () => "",
      accessibleName = null,
      save,
      send,
      sendClass = "",
      sends,
      action: submitAction = "send",
      altLabel = null,
      altSend = null,
      // `true` to take an attached image; otherwise the sentence the user is told instead.
      // True, or why the box takes no image.
      allowsMedia = /** @type {() => true | string} */ (() => true),
      busy = () => false,
      hasContent = (raw) => Boolean(raw),
      // A box whose draft can carry a drawing: `read` returns it or null, `replace` puts
      // another in its place (null takes it off), `undoStroke` takes back its last stroke
      // and `remove` takes it off the draft.
      drawing = null,
      // Keys this box answers beyond submitting, in its own scope, such as a rewrite's
      // ↑ to the message before it.
      rows = [],
      // Where the submit control stands: in the field beside the words, or in a group of
      // the caller's that holds it elsewhere, as a rewrite's stands at its message's head.
      submitIn = null,
      // A box rewriting a sent message, whose attachments are the message's: they stand
      // where and as the message draws them (`.lf-msg-media`), in the field under its
      // words and each whole, rather than in a new draft's shelf over the field.
      sentMedia = false,
    },
  ) {
    const field = document.createElement("leaf-composition-field");
    ta.before(field);
    // Changes elsewhere in the page reach a field only when its own reading changes.
    const focusedHere = computed(() => {
      focusRevision();
      return focused() === ta;
    });
    const enteringHint = computed(() =>
      hintedBox.value === ta ? hintLabel.value : "",
    );
    const inputError = computed(() => errorOver(ta));
    // A one-line field, such as an option's title, has no line for Return to break, so
    // Return sends it from every keyboard, a phone's included.
    const oneLine = ta.getAttribute("aria-multiline") === "false";
    const sendBindings = () => (oneLine ? ["Enter", "Mod+Enter"] : submitBindings());
    const sendKey = () => sendBindings().slice(0, 1).map(spell).join("");
    // Where Return sends a box that holds lines, Shift+Return makes one.
    /** @param {string} sendKeys */
    const lineKeyOf = (sendKeys) =>
      sendKeys === spell("Enter") && !oneLine ? spell("Shift+Enter") : "";
    // The editor is kept whole in Lit's Node part. A rewrite's submit root sits
    // beside its existing Discard control, without an extra layout box.
    const submitEnd = document.createComment("");
    if (submitIn) submitIn.append(submitEnd);
    /** @type {HTMLButtonElement | null} */
    let sendBtn = null;
    let composing = false;
    const actionWord = () =>
      typeof submitAction === "function" ? submitAction() : submitAction;
    // A send key on covered words lifts the cover and sends nothing.
    const uncover = () => {
      passErrorsAt(ta);
      const end = ta.value.length;
      focusDestination(ta, "move", { caret: [end, end] });
    };
    const held = () => busy() || inputError.value !== null;
    /** @type {Element | undefined} */
    let mediaShelf;
    /** @type {string[]} */
    let attachedMedia = [];
    const draftValue = () => writeAttachedMedia(ta.value, attachedMedia);
    /** @param {number} index */
    const removeMedia = (index) => {
      attachedMedia.splice(index, 1);
      draftChanged();
      rememberWriting(ta);
      focusDestination(ta, "return");
    };
    // ⌘Z and ⌘⇧Z walk the whole draft in the order it changed. The words have the field's
    // own history, and each change to what the shelf holds beside them takes a step in
    // that history, whichever control made it: a stroke, a press on the shelf, Draw
    // mode's undo, an attached image. A step is one part of the shelf, the drawing or the
    // images, and taking it back or redoing it puts that part as it stood. What reaches
    // the box from outside is where its history stands rather than a step in it: a draft
    // loaded whole (`hydrate`), or one the box takes up afresh (`sync.arrive`), so no step
    // reaches across drafts or takes back another tab's change.
    /** @type {{drawing: Drawing | null, media: readonly string[]} | null} */
    let shelfSeen = null;
    let arrivals = 0;
    /** @type {((drawn: Drawing | null) => void) | null | undefined} */
    const putDrawing =
      drawing &&
      ((drawn) => {
        shelfSeen = { drawing: drawn, media: [...attachedMedia] };
        drawing.replace(drawn);
        const strokes = drawn?.strokes.length ?? 0;
        announce(strokes ? `Drawing, ${counted(strokes, "stroke")}.` : "No drawing.");
      });
    /** @param {readonly string[]} media */
    const putMedia = (media) => {
      shelfSeen = { drawing: drawing?.read() ?? null, media };
      attachedMedia = [...media];
      draftChanged();
    };
    const recordMedia = () => {
      const drawn = drawing?.read() ?? null;
      const media = [...attachedMedia];
      if (putDrawing && shelfSeen && !sameDrawing(drawn, shelfSeen.drawing)) {
        const before = shelfSeen.drawing;
        ta.record(
          () => putDrawing(before),
          () => putDrawing(drawn),
        );
      }
      if (shelfSeen && media.join("\n") !== shelfSeen.media.join("\n")) {
        const before = shelfSeen.media;
        ta.record(
          () => putMedia(before),
          () => putMedia(media),
        );
      }
      shelfSeen = { drawing: drawn, media };
    };
    const mediaActions = drawing && {
      target: drawing.target,
      removeMedia,
      // Keeping a drawing leaves its Undo under the user; removing it returns to words.
      undoStroke: () => {
        drawing.undoStroke();
        if (!drawing.read()) focusDestination(ta, "return");
      },
      removeDrawing: () => {
        drawing.remove();
        focusDestination(ta, "return");
      },
    };
    /** @param {string} value */
    const hydrate = (value) => {
      const restored = readAttachedMedia(value);
      attachedMedia = restored.paths;
      ta.value = restored.text;
      ta.restartHistory();
      shelfSeen = null;
    };
    hydrate(ta.value);
    // Keep the full native placeholder, but paint a copy so only the key can use mono.
    // The accessible name stays independent of that changing hint. The send button's
    // tooltip spells out its keys. A focused box claims the send key, and where Return
    // sends a box that holds lines, the key for a new line after it; an unfocused box
    // may show the contextual key that enters it; a finger is shown none
    // (`advertisesKeys`). Labels can change while a box stands.
    const label = () => (typeof hint === "function" ? hint() : hint);
    const name = () =>
      typeof accessibleName === "function" ? accessibleName() : accessibleName;
    // The field can become visible before its first scheduled paint. Give a static
    // name to the native control in the task that constructs it.
    const initialName = name();
    if (initialName) keeps(ta, "aria-label", initialName);
    const sendWord = () => (typeof sends === "function" ? sends() : sends);
    const sendLabel = () => capitalized(sendWord());
    // Once words reach Send's corner, Send shows there as the pointer comes to it, and
    // takes presses only once the pointer has rested on it (response.css), so a quick
    // press at the words' end places the caret. Typing, or a press on the words, puts
    // Send away until the pointer next moves, so a second press of a double-click
    // selects rather than sends. Where the pointer is decides, read from each move and
    // leave alike: the user's Firefox follows nearly every move with a `pointerleave`
    // out to the document at the same point, and a leave taken as the pointer going put
    // Send away on every move.
    let dwell = 0;
    const unpoint = () => {
      clearTimeout(dwell);
      dwell = 0;
      ta.parentElement?.removeAttribute("data-lf-send-pointed");
      ta.parentElement?.removeAttribute("data-lf-send-armed");
    };
    /** @param {PointerEvent & {currentTarget: HTMLElement}} event */
    const point = (event) => {
      if (event.pointerType === "touch") return;
      const box = event.currentTarget;
      const send = sendBtn?.getBoundingClientRect();
      const on =
        send &&
        event.clientX >= send.left &&
        event.clientX < send.right &&
        event.clientY >= send.top &&
        event.clientY < send.bottom;
      if (!on) return unpoint();
      if (box.hasAttribute("data-lf-send-pointed")) return;
      box.setAttribute("data-lf-send-pointed", "");
      dwell = setTimeout(() => {
        dwell = 0;
        box.setAttribute("data-lf-send-armed", "");
      }, SEND_DWELL);
    };
    let sending = false;
    let uploading = false;
    const canSend = () => !sending && !uploading && !held() && hasContent(draftValue());
    // These are values of native editor state, rather than generated DOM. The
    // placeholder's rich projection and every action's attributes belong to Lit.
    const watchError = sizeObserver(() => {
      if (!ta.isConnected || !ta.checkVisibility()) passErrorsAt(ta);
    });
    let watchedError = false;
    field.render = () => {
      const hasWords = hasContent(draftValue());
      const advertising = advertisesKeys();
      const sendKeys = advertising ? sendKey() : "";
      const offered = focusedHere.value ? "" : enters();
      const press = typeof offered === "string" ? null : offered;
      const suffix = !advertising
        ? ""
        : focusedHere.value
          ? sendKeys
          : press
            ? ""
            : enteringHint.value;
      const pressKeys = press && advertising ? press.keys : [];
      const word = label();
      // Where Return sends a box that holds lines, the box says which key makes one,
      // beside the key that sends, so a writer meets Shift+Return before Return sends
      // half a message; the send control's tooltip says the same.
      const lineKey = lineKeyOf(sendKeys);
      const lineHint = focusedHere.value ? lineKey : "";
      const entering = suffix && typeof offered === "string" ? offered : "";
      const pressText = press ? [press.word, ...pressKeys].join(" ") : "";
      /** @param {BoxPress} reading */
      const said = (reading) =>
        [reading.word, ...(advertisesKeys() ? reading.keys : [])].join(" ");
      // The press as drawn, whose keys its owner reads at each ask, so the recheck
      // costs that reading alone rather than the box's words.
      if (press) pressing.set(field, () => said(press) !== pressText);
      else pressing.delete(field);
      const placeholder =
        suffix || press
          ? `${word}${entering ? ` · ${entering}` : ""}${suffix ? ` ${suffix}` : ""}${pressText ? ` · ${pressText}` : ""}${lineHint ? ` · ${NEW_LINE} ${lineHint}` : ""}`
          : word;
      if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
      const ariaLabel = name();
      if (ariaLabel) keeps(ta, "aria-label", ariaLabel);
      const parts = hintParts?.();
      const lead = hintLead();
      const richHint = suffix || press || parts != null || lead;
      render(
        html`${
          richHint
            ? html` <span class="lf-compose-placeholder" slot="placeholder">
                <span class="lf-compose-placeholder-lead">${lead}</span
                ><span class="lf-compose-placeholder-words">${parts ?? word}</span
                ><span class="lf-compose-placeholder-enters">${entering}</span
                ><kbd class="lf-key-badge">${suffix}</kbd>${
                  lineHint
                    ? html`<span class="lf-compose-placeholder-line"
                        >· ${NEW_LINE} <kbd class="lf-key-badge">${lineHint}</kbd></span
                      >`
                    : nothing
                }
              </span>`
            : nothing
        }${press ? pressAtRest(press, pressKeys) : nothing}`,
        ta,
      );
      let error = inputError.value;
      if (error && !(ta.isConnected && ta.checkVisibility())) {
        passErrorsAt(ta);
        error = null;
      }
      if (Boolean(error) !== watchedError) {
        watchedError = Boolean(error);
        if (error) watchError.observe(ta);
        else watchError.unobserve(ta);
      }
      const action = sendLabel();
      const submitControl = html`<button
        type="button"
        ${offeredAction("symbol", `${sendClass} lf-compose-submit`.trim(), action, {
          action: actionWord(),
        })}
        ?data-lf-disc=${!submitIn}
        data-lf-tone="accent"
        aria-disabled=${String(!canSend())}
        ?data-lf-empty=${!hasWords}
        aria-keyshortcuts=${sendBindings().flatMap(ariaBindings).join(" ")}
        @mousedown=${keepEditing}
        @click=${() => pressed(send)}
      ></button>`;
      if (submitIn) render(submitControl, submitIn, { renderBefore: submitEnd });
      const drawn = drawing?.read() ?? null;
      const media = mediaTemplate({
        drawing:
          drawn && mediaActions
            ? {
                record: drawn,
                target: mediaActions.target(),
                undoStroke: mediaActions.undoStroke,
                removeDrawing: mediaActions.removeDrawing,
              }
            : null,
        media: attachedMedia.map((path, index) => ({
          index,
          url: scopedMediaUrl(path),
        })),
        sent: sentMedia,
        removeMedia,
      });
      const shelf = html`<div
        class=${sentMedia ? "lf-msg-media" : "lf-composer-media"}
        ?data-lf-scroll=${!sentMedia}
        role="group"
        aria-label="Attachments"
        ?hidden=${!drawn && attachedMedia.length === 0}
        ${ref((node) => {
          mediaShelf = node;
        })}
      >
        ${media}
      </div>`;
      const content = html`
        ${ta}${sentMedia ? shelf : nothing} ${submitIn ? nothing : submitControl}
        <p
          class="lf-compose-error"
          aria-hidden="true"
          ?hidden=${!error}
          .lfPreview=${() => (error ? { name: error.message } : null)}
          @pointerdown=${
            /** @param {PointerEvent} event */ (event) => {
              event.preventDefault();
              uncover();
            }
          }
        >
          <span>${error?.message ?? ""}</span>
        </p>
      `;
      const alternate =
        altSend && altLabel
          ? html`<button
              type="button"
              ${offeredAction("word", "lf-compose-alt")}
              aria-disabled=${String(!canSend())}
              @mousedown=${keepEditing}
              @click=${() => pressed(altSend)}
            >
              ${altLabel}
            </button>`
          : nothing;
      return html`${sentMedia ? nothing : shelf}
        <div
          class="lf-compose-field"
          ?data-lf-words=${hasWords}
          @pointermove=${point}
          @pointerleave=${point}
          @pointerdown=${
            /** @param {PointerEvent} event */ (event) => {
              if (!event.composedPath().some((node) => node === sendBtn)) unpoint();
            }
          }
        >
          ${content}
        </div>
        ${alternate}`;
    };
    field.updated = () =>
      untracked(() => {
        paintKeysWithin(field);
        if (submitIn) paintKeysWithin(submitIn);
      });
    const refresh = () => {
      recordMedia();
      field.requestUpdate();
    };
    const draftChanged = () => {
      save(draftValue());
      refresh();
    };
    // sync() asks for the paint of what the box holds. It is not how a draft gets in:
    // what the user would miss is the words and the attached images together, and the
    // images show only in the shelf, so a caller writing .value states half a draft.
    // Emptying a box that way left an image in a box the runtime then read as
    // still holding something — the box said "draft kept" over a comment it had just
    // sent, and the picture rode into the next passage's draft.
    /** @type {InputSync} */
    const sync = () => refresh();
    sync.value = draftValue;
    sync.hasMedia = () => attachedMedia.length > 0;
    // The box takes up the draft it now stands on as it is, with a history of its own:
    // another draft, or this one as another tab left it. The caller's next paint shows
    // it, and shows any change made to it since as a step of that history.
    sync.arrive = () => {
      passErrorsAt(ta);
      arrivals += 1;
      ta.restartHistory();
      shelfSeen = { drawing: drawing?.read() ?? null, media: [...attachedMedia] };
    };
    // The one way a draft enters from outside: the complete value, words and image Markdown
    // together, as the store holds it. Writing .value moves a focused caret to its end, so a
    // value the box already holds is left where it is — which is what lets another tab's
    // notification, a reopened composer, and a mirrored panel box all say it unconditionally.
    sync.load = /** @param {string} value */ (value) => {
      if (draftValue() !== value) hydrate(value);
      refresh();
    };
    ta[INPUT_DRAFT] = sync;
    // The box's first paint names its send button and placeholder, and keeps the focus
    // bookkeeping if a caller wires one the user is already in.
    refresh();
    // Wiring needs actual controls for their keyboard declarations. First render is
    // synchronous; subsequent updates use Lit's microtask batching.
    field.performUpdate();
    /** @type {HTMLElement | null} */
    const visualField = field.querySelector("div.lf-compose-field");
    if (!visualField) throw new Error("Composition template has no field frame");
    sync.composition = () => ({ field: visualField, frame: field });
    sendBtn = (submitIn ?? field).querySelector("button.lf-compose-submit");
    // The key that sends from the box is the box's own `text.send`, which sends rather
    // than pressing Send, so the box says it beside Send: as a key chip in Send's
    // preview (preview.js), with the key that makes a new line where Return sends, and
    // in its `aria-keyshortcuts`, both from `sendBindings`.
    if (sendBtn)
      sendBtn.lfPreview = () => {
        const line = advertisesKeys() ? lineKeyOf(sendKey()) : "";
        return {
          keys: [[sendKey()]],
          detail: [line && html`${NEW_LINE} <kbd class="lf-key-badge">${line}</kbd>`],
        };
      };
    sync.button = sendBtn;
    whileConnected(field, (signal) => {
      coarsePointer.addEventListener("change", refresh, { signal });
      return () => {
        watchError.disconnect();
        watchedError = false;
        passErrorsAt(ta);
      };
    });
    /** @param {Sender} sender */
    const submit = async (sender) => {
      if (sending || uploading || held()) return;
      // A send key on an empty box answered with silence reads as a send that
      // happened — the blind drive believed exactly that. Say the nothing out loud; the
      // empty box already shows it to anyone who sees it.
      const raw = draftValue();
      const text = raw.trim();
      if (!hasContent(raw))
        return announce(`Nothing to ${sendWord()} — the box is empty`);
      sending = true;
      refresh();
      try {
        await sender(text, raw, () => draftValue() === raw, ta.value);
      } finally {
        sending = false;
        refresh();
      }
    };
    ta.addEventListener("input", () => {
      unpoint();
      draftChanged();
      // A box a thread or seat holds keeps its controls in view as it grows
      // (`followBoxGrowth`). On the user's own keystrokes and nothing else: a send settling
      // after they scrolled away, or a draft mirrored from another tab, must not pull the
      // page back. Instant, not smooth — a line typed while the last line's glide is still
      // running lands where that glide was going, two lines short of the box it is now.
      if (focused() === ta) followBoxGrowth(ta);
    });
    ta.addEventListener("focus", () => readBoxPlace(ta));
    ta.addEventListener(
      "lf-before-edit",
      () => {
        readBoxPlace(ta);
        passErrorsAt(ta);
      },
      { capture: true },
    );
    // A key in a covered box lifts the cover, as a press on it does, and keeps its
    // meaning: an edit (`lf-before-edit` above) or a caret move lands as typed. A send
    // key only lifts it, through the box's own send binding (`pressed`), so nothing is
    // sent unseen and the next press sends. A modifier alone, Tab and Escape neither
    // edit nor move the caret, so none of them lifts it.
    ta.addEventListener("lf-caret-move", () => passErrorsAt(ta));
    // Paste and page capture enter through the same command. It owns delivery and the
    // whole draft's history, and refuses a second upload while the first owns the field.
    // The arrival generation prevents an image reaching another draft when the floating
    // composer moves to another passage before its bytes reach the server.
    // Attaching is the user coming back to the box, as an edit is.
    sync.addMedia = /** @param {readonly Blob[]} images */ async (images) => {
      if (images.length) passErrorsAt(ta);
      if (!images.length || sending || uploading || held()) return false;
      const allowed = allowsMedia();
      if (allowed !== true) {
        raiseError(allowed, { subject: ta });
        return false;
      }
      rememberWriting(ta);
      const wasReadOnly = ta.readOnly;
      uploading = true;
      ta.readOnly = true;
      ta.setAttribute("aria-busy", "true");
      refresh();
      // The thumbnail arriving in the shelf is the attachment's result, so only a
      // listener is told; a failure, which shows nothing, is a notice.
      announce(
        images.length === 1 ? "Adding image…" : `Adding ${images.length} images…`,
      );
      const attachedAt = arrivals;
      try {
        const paths = await Promise.all(images.map((image) => uploadMedia(image)));
        if (!paths.every((path) => path !== null)) return false;
        if (arrivals !== attachedAt) {
          raiseError(
            "Image not added — the comment moved before it finished uploading",
            { subject: ta },
          );
          return false;
        }
        attachedMedia.push(...paths);
        draftChanged();
        // A sent message's pictures stand under its words, where a new one can arrive out
        // of view: it is the attachment's result, so it comes into view once it has its
        // size, unless the user has moved on meanwhile.
        if (sentMedia) {
          // This command reveals the attachment it just added, after its Lit commit.
          field.performUpdate();
          const added = mediaShelf?.lastElementChild;
          const mayReveal = retainUserIntent();
          void added
            ?.querySelector("img")
            ?.decode()
            .catch(() => {})
            .then(() => mayReveal() && scrollIntoView(added, { block: "nearest" }));
        }
        announce(images.length === 1 ? "Image added" : `${images.length} images added`);
        return true;
      } catch (error) {
        raiseError(`Could not add image — ${describeFailure(error)}`, { subject: ta });
        return false;
      } finally {
        uploading = false;
        ta.readOnly = wasReadOnly;
        ta.removeAttribute("aria-busy");
        refresh();
      }
    };
    // The composer owns picture admission. Capture declines the field's ordinary text
    // paste before CodeMirror handles it; a direct editor without this owner keeps the
    // clipboard's text even when the payload also contains a picture.
    ta.addEventListener(
      "paste",
      (event) => {
        const images = [...(event.clipboardData?.items ?? [])]
          .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
          .map((item) => item.getAsFile())
          .filter((file) => file !== null);
        if (!images.length) return;
        event.preventDefault();
        void sync.addMedia(images);
      },
      { capture: true },
    );
    // The box's own scope: one row, so the hint's word, the command reference dialog's sentence and
    // the press are the same object. Every box the runtime wires gets it — the general box,
    // each thread's reply, the selection composer, a widget thread — where the reference
    // used to carry one row saying "in the focused composer" for a sequence that fires in all
    // of them, including widget-owned text boxes.
    // The sentence is the same in every box, so the reference names the binding once however
    // many boxes the page holds; the word is this box's, because what the press does here is
    // what the line is for — a composer in suggestion mode and a thread's reply are one
    // binding doing two things.
    // An empty box sends nothing, so where it has another key live, as a reply's ↑ to
    // the user's last message, the line offers that key in the send hint's place; the
    // placeholder still shows the send key.
    keys(ta, "In a text box", [
      {
        id: "text.send",
        keys: sendBindings,
        label: sendKey,
        title: sends,
        run: () => pressed(send),
      },
      ...rows,
    ]);
    // The field owns text editing; this owner alone reserves Return for its declared
    // submit binding. An unwired source editor therefore keeps Return on every device.
    ta.addEventListener("lf-edit-return", (event) => {
      if (sendBindings().includes("Enter")) event.preventDefault();
    });
    // A press on a submit control is the send key pressed from the box, so it leaves the
    // user where Enter does: in the box, for a box that stays to take more, or wherever the
    // send hands them on to, as a first message does to its thread (`landSent`), never on the
    // control, where the next letters would fall on nothing. A pointer press never takes
    // the focus (moving it is mousedown's default), so the box keeps it until the send
    // moves it. A keyboard press on the control, or a pointer press while the user was
    // elsewhere, puts the user in the box before the submission, so what the send does
    // next starts from the state Enter starts it from.
    //
    // Except while an input method holds unfinished words: leaving the box is what
    // finishes them, so there the press takes the focus as it always did, and the words
    // are committed before the click sends them. Held in the box, they were sent
    // unfinished, and the input method's later commit wrote them back into the box the
    // send had just emptied. Enter never meets this, since the input method takes Enter.
    ta.addEventListener("compositionstart", () => (composing = true));
    ta.addEventListener("compositionend", () => (composing = false));
    // A send key, or Send reached by the keyboard, in a covered box lifts the cover and
    // sends nothing (`uncover`).
    /** @param {Sender} sender */
    const pressed = (sender) => {
      if (inputError.value) return uncover();
      if (focused() !== ta) focusDestination(ta, "return");
      submit(sender);
    };
    return sync;

    /** @param {MouseEvent} event */
    function keepEditing(event) {
      if (!composing) event.preventDefault();
    }
  }

  return { wireInput, publishInputHint };
}
