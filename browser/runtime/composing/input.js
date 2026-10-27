// One helper wires every durable composition surface: the general box, each per-thread
// reply, the compact anchored composer, and composition boxes contributed by widgets.
// `wireInput` gives every such text field one input contract: persist each edit, keep the
// action button and placeholder current, prevent parallel submissions of one local
// surface (an impatient second click), and submit with Enter on a physical keyboard. A
// press on a submit control is that Enter, pressed from the box.
// Where native speech recognition is available, an empty comment offers a microphone
// in Send's place. Dictation uses the same draft and send contract in every surface:
// empty-field status stays in the placeholder, words keep their place, and the mic's
// face carries listening. Sending and explicit closing retire capture before the
// draft can change; Escape keeps its existing close-and-keep-draft meaning.
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
// What the box holds changes in the turn that changes it: the words and attached images
// (the field's own value, which its caret and every reader after the writer depend on),
// and whether a send or upload is under way. What that looks like is painted once per
// frame, in the runtime's one repaint frame (repaint.js): the send button's name, its
// disabled state and the placeholder in `paintInputs`, and the floating composer's
// placement in chrome layout's pass, which runs first. A change marks its box stale and
// asks for that paint, so a keystroke, an open that loads a draft twice, and a send that
// settles and closes the box each paint and measure once, after their writes, instead of
// interleaving a forced style recalculation with each. That paint runs in the frame the
// change first shows in, so the button and placeholder never trail the words.
import { rememberWriting } from "../drafts.js";
import { keys, paintKeysWithin } from "../keyboard/scopes.js";
import { keeps, keepsHidden, keepsText } from "../keeps.js";
import { advertisesKeys, submitBindings, spell, PRESS } from "../keyboard/bindings.js";
import { readAttachedMedia, scopedMediaUrl, writeAttachedMedia } from "../media.js";
import { announce } from "../notifications.js";
import { iconElement, iconTemplate } from "../icons.js";
import { offeredAction } from "../widget-elements.js";
import { drawingThumbnail } from "./drawing-context.js";
import {
  LitElement,
  html,
  render as renderHint,
  effect,
  untracked,
} from "/runtime/framework.js";
import "./text-field.js";
import { followBoxGrowth, readBoxPlace } from "../thread/reply-landing.js";
import { focusDestination, focused } from "../focus.js";
import { whileConnected } from "../arrivals.js";
import { move } from "../dom-move.js";
import { applicationState } from "../semantic-state.js";
import { errorsReading, passErrorsAt, raiseError } from "../errors.js";
import { repaint } from "../repaint.js";
import { sizeObserver } from "../rendering.js";
import { scrollIntoView } from "../landing-scroll.js";
import { retainUserIntent } from "../user-intent.js";

const inputDrafts = new WeakMap();

const MEDIA_SHELF_TAG = "leaf-attached-media-shelf";
// Another tab's copy of a drawing is a different object holding the same strokes.
const sameDrawing = (a, b) => a === b || JSON.stringify(a) === JSON.stringify(b);
let thumbnailVersion = 0;

// What the draft carries beside its words: the drawing a stroke attached, then each attached
// image. Each shows itself rather than its transport and each comes off with its own
// control, so nothing rides along with a comment unseen or beyond the user's reach. The
// drawing also takes back its last stroke here: the route a pointer or a finger has to
// that, wherever the composer stands.
/** @typedef {AttachedMediaShelf} AttachedMediaShelfElement For its tag (`runtime-globals.d.ts`). */
class AttachedMediaShelf extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  constructor() {
    super();
    this.model = { drawing: null, media: [] };
    this.actions = null;
    // Whether the pictures are a sent message's, drawn in its face (`sentMedia`).
    this.sent = false;
    this.undoIcon = iconElement("undo", "lf-mark-icon");
    this.removeIcon = iconElement("cross", "lf-mark-icon");
    // The picture is rebuilt only when the drawing changes, so a repaint that changes
    // nothing about it leaves its node in place.
    this.pictured = { drawing: null, target: null, node: null };
  }

  picture(drawing) {
    if (
      !sameDrawing(drawing, this.pictured.drawing) ||
      this.model.target !== this.pictured.target
    ) {
      const node = drawingThumbnail(drawing, this.model.target);
      // A canvas's changed pixels are not reflected in its markup. Give each rebuilt
      // picture an identity so DOM readers can distinguish its new ink from the old.
      node.dataset.lfDrawingVersion = String(++thumbnailVersion);
      this.pictured = {
        drawing,
        target: this.model.target,
        node,
      };
    }
    return this.pictured.node;
  }

  createRenderRoot() {
    return this;
  }

  present(model, actions) {
    this.model = model;
    this.actions = actions;
    this.performUpdate();
  }

  updated() {
    keepsHidden(this, !this.model.drawing && this.model.media.length === 0);
  }

  render() {
    const { drawing, media } = this.model;
    const strokes = drawing?.strokes.length ?? 0;
    return [
      drawing
        ? html`
            <span class="lf-composer-media-item lf-composer-drawing">
              <button
                type="button"
                class="lf-media-open lf-composer-media-open lf-media-frame"
                data-lf-media-canvas
                aria-label=${`Inspect drawing, ${strokes} ${strokes === 1 ? "stroke" : "strokes"}`}
                title="Inspect drawing"
                @click=${(event) => {
                  const canvas = this.picture(drawing);
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
                }}
              >
                ${this.picture(drawing)}
              </button>
              <button
                ${offeredAction(
                  "mark",
                  "lf-corner-mark lf-composer-drawing-undo",
                  "Undo last stroke",
                )}
                @mousedown=${(event) => event.preventDefault()}
                @click=${() => this.actions.undoStroke()}
              >
                ${this.undoIcon}
              </button>
              <button
                ${offeredAction("mark", "lf-corner-mark", "Remove drawing")}
                @mousedown=${(event) => event.preventDefault()}
                @click=${() => this.actions.removeDrawing()}
              >
                ${this.removeIcon}
              </button>
            </span>
          `
        : null,
      media.map(({ index, url }) => {
        const remove = html`<button
          ${offeredAction(
            "mark",
            "lf-corner-mark lf-composer-media-remove",
            `Remove attached image ${index + 1}`,
          )}
          @click=${() => this.actions.removeMedia(index)}
        >
          ${iconTemplate("cross", "lf-mark-icon")}
        </button>`;
        // A sent message's picture is the one its message draws (markdown.js, the image
        // rule), in a paragraph of its own as the message sets it, with the removal mark
        // a rewrite adds.
        return this.sent
          ? html`<p class="lf-composer-media-item">
              <button
                type="button"
                class="lf-media-open lf-message-media"
                data-lf-media-url=${url}
                aria-label=${`View attached image ${index + 1}`}
              >
                <img src=${url} alt="" /></button
              >${remove}
            </p>`
          : html`<span class="lf-composer-media-item">
              <button
                type="button"
                class="lf-media-open lf-composer-media-open lf-media-frame"
                data-lf-media-url=${url}
                aria-label=${`View attached image ${index + 1}`}
              >
                <img src=${url} alt="" /></button
              >${remove}
            </span>`;
      }),
    ];
  }
}

if (!customElements.get(MEDIA_SHELF_TAG))
  customElements.define(MEDIA_SHELF_TAG, AttachedMediaShelf);

// A wired field's visible value omits generated image Markdown. Readers outside
// this module ask through this seam for the complete draft; an unwired box keeps
// its ordinary value.
export const draftOf = (ta) => inputDrafts.get(ta)?.value() ?? ta?.value ?? "";
// Ask a wired field to paint again, as its own `sync()` does, where what its hint or
// name reads has changed and the caller holds the field rather than its wiring.
export const syncInput = (ta) => inputDrafts.get(ta)?.();
// The newest error about a box the user has not come back to, which covers its words.
const errorOver = (ta) =>
  errorsReading().find((error) => error.subject === ta && !error.passed) ?? null;
// Whether an error stands at a box, which says it there; the panel's dot marks only
// those that stand nowhere. A box that stops showing the words passes its errors, so a
// standing one is always on screen.
export const standsAtItsBox = (error) =>
  inputDrafts.has(error.subject) && !error.passed;
// Boot binds one input owner to the app's upload command and contextual-hint
// reading. Fields keep those capabilities for their lifetime; importing this module
// never installs or replaces application callbacks.
export function createCompositionInputs({ uploadMedia, inputHint }) {
  // The repaint frame paints every box whose own state changed since it last ran, and
  // the previous and current box for focus and for the contextual-entry hint, since
  // either may need to lose or gain its hint. The repaint owner asks for that paint on
  // every focus move (repaint.js).
  const inputPaints = new WeakMap();
  const stale = new Set();
  let paintedInput = null;
  let paintedHintTarget = null;
  const paintInputs = () => {
    const held = focused();
    const input = held && inputPaints.has(held) ? held : null;
    const hint = inputHint();
    const hintedInput = hint?.box && inputPaints.has(hint.box) ? hint.box : null;
    const boxes = new Set([
      ...stale,
      paintedInput,
      input,
      paintedHintTarget,
      hintedInput,
    ]);
    stale.clear();
    for (const ta of boxes) inputPaints.get(ta)?.(hint);
    paintedInput = input;
    paintedHintTarget = hintedInput;
  };
  // A box an error stands over is watched for the user no longer seeing its words: put
  // away, hidden with what holds it, or taken from the page. Its size reports each of
  // those; the box's own paint passes an error over a box already out of sight.
  const watched = new WeakSet();
  const unshown = sizeObserver((entries) => {
    for (const { target } of entries)
      if (!target.isConnected || !target.checkVisibility()) passErrorsAt(target);
  });
  // A box an error is about, or was about, paints its cover again when the errors change.
  /** @type {ReturnType<typeof errorsReading>} */
  let errorsPainted = [];
  effect(() => {
    const errors = errorsReading();
    for (const { subject } of [...errorsPainted, ...errors])
      if (inputPaints.has(subject)) stale.add(subject);
    errorsPainted = errors;
    untracked(repaint);
  });
  // `sends` states the box's own submit action. Composers send by default; a caller whose
  // action differs, such as adding an option, supplies the matching icon.
  function wireInput(
    ta,
    {
      hint,
      // A structured visual hint can mark the exact words its owner observes. It
      // shares the existing placeholder slot and send key; null keeps the plain hint.
      hintParts = null,
      // Words that pass while the hint stands, said at the empty box's far end after
      // the hint and its key, where they move none of the box's controls.
      hintAside = () => "",
      accessibleName = null,
      save,
      send,
      sendBtn,
      sends,
      icon = "send",
      altBtn = null,
      altSend = null,
      // `true` to take an attached image; otherwise the sentence the user is told instead.
      // True, or why the box takes no image.
      allowsMedia = /** @type {() => true | string} */ (() => true),
      busy = () => false,
      hasContent = (raw) => Boolean(raw),
      // The caller's own rendering of what the box holds, run in the box's paint.
      paint: paintOwn = () => {},
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
    const field = document.createElement("div");
    field.className = "lf-compose-field";
    ta.before(field);
    // A one-line field, such as an option's title, has no line for Return to break, so
    // Return sends it from every keyboard, a phone's included.
    const oneLine = ta.getAttribute("aria-multiline") === "false";
    const sendBindings = () => (oneLine ? ["Enter", "Mod+Enter"] : submitBindings());
    const sendKey = () => spell(sendBindings()[0]);
    // The placeholder with its send key drawn as a key: the field shows it in place of
    // the plain placeholder while it is in the field, which is while there is a key to
    // show.
    const visibleHint = document.createElement("span");
    visibleHint.className = "lf-compose-placeholder";
    visibleHint.slot = "placeholder";
    const hintLabel = document.createElement("span");
    const hintKey = document.createElement("kbd");
    hintKey.className = "lf-key-badge";
    const hintAsideWords = document.createElement("span");
    hintAsideWords.className = "lf-compose-placeholder-aside";
    visibleHint.append(hintLabel, hintKey, hintAsideWords);
    field.append(ta);
    (submitIn ?? field).append(sendBtn);
    // Firefox lacks speech recognition; WebKit has it only under its prefix.
    const Recognition =
      globalThis.SpeechRecognition ?? globalThis.webkitSpeechRecognition;
    const mic =
      Recognition && icon === "send" && !submitIn
        ? Object.assign(document.createElement("button"), {
            type: "button",
            className: "lf-compose-dictate",
          })
        : null;
    let dictation = null;
    let loadingDictation = false;
    let dictationGeneration = 0;
    let loadingFailure = "";
    let stopDictationRevision = null;
    const dictationPhase = () =>
      loadingDictation ? "starting" : (dictation?.phase ?? "idle");
    const dictationStatus = () =>
      loadingDictation
        ? "Starting microphone…"
        : loadingFailure || dictation?.status || "";
    if (mic) {
      mic.append(iconElement("microphone", "lf-action-icon"));
      field.append(mic);
    }
    // The error standing over the box (`errorOver`). It stands in the field, so a press
    // on it is a press in the box: a reply's stays in its row, which a press elsewhere
    // would put away (thread/replies.js).
    const cover = document.createElement("p");
    cover.className = "lf-compose-error";
    cover.setAttribute("aria-hidden", "true");
    cover.hidden = true;
    // Its words, clipped to the box's whole lines (response.css).
    const coverWords = document.createElement("span");
    cover.append(coverWords);
    field.append(cover);
    // The user coming back to the covered words by a press or a send key: the cover
    // lifts with the caret at their end, and nothing is sent.
    const uncover = () => {
      passErrorsAt(ta);
      const end = ta.value.length;
      focusDestination(ta, "move", { caret: [end, end] });
    };
    cover.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      uncover();
    });
    const held = () => busy() || errorOver(ta) !== null;
    // The press's whole face, its box and its glyph's ink (response.css), whatever face
    // its caller made it with, so a box cannot be handed a send button dressed as
    // something else. The caller's own classes only place it.
    sendBtn.classList.add("lf-compose-submit");
    sendBtn.replaceChildren(iconElement(icon, "lf-action-icon"));
    const mediaShelf = document.createElement(MEDIA_SHELF_TAG);
    mediaShelf.className = sentMedia ? "lf-msg-media" : "lf-composer-media scroll";
    mediaShelf.sent = sentMedia;
    mediaShelf.setAttribute("role", "group");
    mediaShelf.setAttribute("aria-label", "Attachments");
    if (sentMedia) field.append(mediaShelf);
    else field.before(mediaShelf);
    let attachedMedia = [];
    const draftValue = () => writeAttachedMedia(ta.value, attachedMedia);
    const removeMedia = (index) => {
      attachedMedia.splice(index, 1);
      renderMedia();
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
    let shelfSeen = null;
    let arrivals = 0;
    const putDrawing = (drawn) => {
      shelfSeen = { ...shelfSeen, drawing: drawn };
      drawing.replace(drawn);
      const strokes = drawn?.strokes.length ?? 0;
      announce(
        strokes
          ? `Drawing, ${strokes} stroke${strokes === 1 ? "" : "s"}.`
          : "No drawing.",
      );
    };
    const putMedia = (media) => {
      shelfSeen = { ...shelfSeen, media };
      attachedMedia = [...media];
      renderMedia();
      draftChanged();
    };
    const renderMedia = () => {
      const drawn = drawing?.read() ?? null;
      const media = [...attachedMedia];
      if (shelfSeen && !sameDrawing(drawn, shelfSeen.drawing)) {
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
      mediaShelf.present(
        Object.freeze({
          drawing: drawn,
          target: drawn ? drawing.target() : null,
          media: attachedMedia.map((path, index) =>
            Object.freeze({ index, url: scopedMediaUrl(path) }),
          ),
        }),
        {
          removeMedia,
          // A press that leaves the drawing keeps the user on the control, for the next
          // stroke back; one that takes the drawing, and the control with it, returns
          // them to the words.
          undoStroke: () => {
            drawing.undoStroke();
            if (!drawing.read()) focusDestination(ta, "return");
          },
          removeDrawing: () => {
            drawing.remove();
            focusDestination(ta, "return");
          },
        },
      );
    };
    const hydrate = (value) => {
      cancelDictation();
      const restored = readAttachedMedia(value);
      attachedMedia = restored.paths;
      ta.value = restored.text;
      ta.restartHistory();
      shelfSeen = null;
      renderMedia();
    };
    hydrate(ta.value);
    // Keep the full native placeholder, but paint a copy so only the key can use mono.
    // The accessible name stays independent of that changing hint. The send button's
    // tooltip spells out its keys. A focused box claims the send key; an unfocused box
    // may show the contextual key that enters it; a finger is shown neither
    // (`advertisesKeys`). Labels can change while a box stands.
    const label = () => (typeof hint === "function" ? hint() : hint);
    const name = () =>
      typeof accessibleName === "function" ? accessibleName() : accessibleName;
    // The field can become visible before its first scheduled paint. Give a static
    // name to the native control in the task that constructs it.
    const initialName = name();
    if (initialName) keeps(ta, "aria-label", initialName);
    const sendWord = () => (typeof sends === "function" ? sends() : sends);
    const sendLabel = () => {
      const word = sendWord();
      return word.charAt(0).toUpperCase() + word.slice(1);
    };
    if (altBtn) altBtn.title = altBtn.textContent;
    let sending = false;
    let uploading = false;
    const canSend = () => !sending && !uploading && !held() && hasContent(draftValue());
    // Everything the box shows about its standing, written only where it differs from
    // what stands: a text node replaced inside the chrome restyles far more than the node.
    const paint = (contextualHint) => {
      // Read the shared logical focus so this hint agrees with the key chips and rings.
      const currentLocation = focused() === ta;
      const advertising = advertisesKeys();
      const sendKeys = advertising ? sendKey() : "";
      const suffix = !advertising
        ? ""
        : currentLocation
          ? sendKeys
          : contextualHint?.box === ta
            ? contextualHint.label
            : "";
      const status = dictationStatus();
      const word = status || label();
      const placeholder = suffix && !status ? `${word} ${suffix}` : word;
      if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
      const parts = status ? null : hintParts?.();
      if (hintParts) renderHint(parts ?? word, hintLabel);
      const aside = status ? "" : hintAside();
      if ((suffix && !status) || (parts !== null && parts !== undefined) || aside) {
        if (!hintParts) keepsText(hintLabel, word);
        keepsText(hintKey, suffix);
        keepsText(hintAsideWords, aside);
        if (visibleHint.parentNode !== ta) move(ta, visibleHint, null);
      } else visibleHint.remove();
      const ariaLabel = name();
      if (ariaLabel) keeps(ta, "aria-label", ariaLabel);
      let error = errorOver(ta);
      if (error && !(ta.isConnected && ta.checkVisibility())) {
        passErrorsAt(ta);
        error = null;
      }
      if (Boolean(error) !== watched.has(ta)) {
        if (error) {
          watched.add(ta);
          unshown.observe(ta);
        } else {
          watched.delete(ta);
          unshown.unobserve(ta);
        }
      }
      keepsText(coverWords, error?.message ?? "");
      keeps(cover, "title", error?.message ?? null);
      keepsHidden(cover, !error);
      const action = sendLabel();
      keeps(sendBtn, "aria-label", action);
      // Where Return sends, a line breaks with Shift+Return, which the hover name says
      // beside the send key, since nothing in the box does.
      const newline =
        sendKeys === spell("Enter") && !oneLine
          ? ` · ${spell("Shift+Enter")} new line`
          : "";
      keeps(sendBtn, "title", sendKeys ? `${action} (${sendKeys})${newline}` : action);
      // These native input actions keep their focus seat while refusing a send.
      keeps(sendBtn, "aria-disabled", !canSend());
      if (altBtn) keeps(altBtn, "aria-disabled", !canSend());
      if (mic) {
        const phase = dictationPhase();
        const live = phase === "starting" || phase === "listening";
        const failed = loadingFailure || dictation?.failure;
        const action = live
          ? "Stop dictation"
          : phase === "stopping"
            ? "Finishing dictation"
            : failed
              ? "Retry dictation"
              : "Dictate";
        keeps(
          mic,
          "data-dictation",
          phase !== "idle"
            ? phase
            : failed && dictation?.failure?.error !== "no-speech"
              ? "failed"
              : null,
        );
        keeps(mic, "aria-label", action);
        keeps(mic, "aria-pressed", live);
        keeps(mic, "aria-description", status || null);
        keeps(mic, "title", live || !status ? action : `${action} (${status})`);
      }
    };
    inputPaints.set(ta, paint);
    let visibilityQueued = false;
    const paintSubmitVisibility = () => {
      visibilityQueued = false;
      // Whether the box holds a draft, which a control in its corner may read.
      keeps(field, "data-words", hasContent(draftValue()) ? "" : null);
      if (mic) {
        const shown = dictationPhase() !== "idle" || !hasContent(draftValue());
        keepsHidden(mic, !shown);
        keepsHidden(sendBtn, shown);
        if (shown && focused() === sendBtn) focusDestination(ta, "return");
        if (!shown && focused() === mic) focusDestination(ta, "return");
      }
      // Which of its controls the box shows moves its own keys, not the page's.
      paintKeysWithin(field);
      if (submitIn) paintKeysWithin(submitIn);
    };
    const refresh = () => {
      if (dictationPhase() === "idle") {
        stopDictationRevision?.();
        stopDictationRevision = null;
      }
      // A button whose visibility follows the draft must join the tab order before
      // the next key. A composer can load an empty draft and then its saved words
      // in one turn; paint the final choice once at the microtask checkpoint.
      paintOwn();
      if (drawing) renderMedia();
      stale.add(ta);
      if (!visibilityQueued) {
        visibilityQueued = true;
        queueMicrotask(paintSubmitVisibility);
      }
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
    const sync = () => refresh();
    // Closing belongs to each surface's existing owner, rather than a DOM observer
    // guessing whether a hidden field is merely outside the viewport.
    sync.cancelDictation = cancelDictation;
    sync.value = draftValue;
    sync.hasMedia = () => attachedMedia.length > 0;
    // The box takes up the draft it now stands on as it is, with a history of its own:
    // another draft, or this one as another tab left it. The caller's next paint shows
    // it, and shows any change made to it since as a step of that history.
    sync.arrive = () => {
      passErrorsAt(ta);
      cancelDictation();
      arrivals += 1;
      ta.restartHistory();
      shelfSeen = { drawing: drawing?.read() ?? null, media: [...attachedMedia] };
    };
    // The one way a draft enters from outside: the complete value, words and image Markdown
    // together, as the store holds it. Writing .value moves a focused caret to its end, so a
    // value the box already holds is left where it is — which is what lets another tab's
    // notification, a reopened composer, and a mirrored panel box all say it unconditionally.
    sync.load = (value) => {
      if (draftValue() !== value) hydrate(value);
      refresh();
    };
    inputDrafts.set(ta, sync);
    // The box's first paint names its send button and placeholder, and keeps the focus
    // bookkeeping if a caller wires one the user is already in.
    refresh();
    const submit = async (sender) => {
      if (sending || uploading || held()) return;
      cancelDictation();
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
      loadingFailure = "";
      dictation?.edited();
      // A user's edit also retires a microphone press still loading its module.
      if (loadingDictation) cancelDictation();
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
    if (mic) {
      const activateDictation = async () => {
        if (dictationPhase() === "stopping" || sending || uploading || held()) return;
        if (dictationPhase() !== "idle") {
          if (loadingDictation) cancelDictation();
          else dictation.stop();
          return;
        }
        focusDestination(ta, "return");
        const revision = applicationState.read().document.revision;
        if (!stopDictationRevision)
          stopDictationRevision = applicationState
            .select((root) => root.document.revision)
            .subscribe((next) => {
              if (next !== revision) cancelDictation();
            });
        if (!dictation) {
          const generation = ++dictationGeneration;
          loadingDictation = true;
          loadingFailure = "";
          refresh();
          let createDictation;
          try {
            ({ createDictation } = await import("./dictation.js"));
          } catch (error) {
            if (generation !== dictationGeneration) return;
            loadingDictation = false;
            loadingFailure = "Dictation couldn’t start";
            refresh();
            announce(loadingFailure);
            throw error;
          }
          if (generation !== dictationGeneration || !ta.isConnected) return;
          loadingDictation = false;
          dictation = createDictation({
            Recognition,
            language: document.documentElement.lang || navigator.language,
            read: () => ta.value,
            write: (words) => ta.edit(words),
            changed: refresh,
            announce,
          });
        }
        dictation.start();
      };
      keys(mic, "Dictation", [
        {
          id: "text.dictate",
          keys: PRESS,
          control: mic,
          title: () => (dictationPhase() === "idle" ? "dictate" : "stop dictation"),
          when: () =>
            !mic.hidden &&
            dictationPhase() !== "stopping" &&
            !sending &&
            !uploading &&
            !held(),
          run: () => void activateDictation(),
        },
      ]);
      mic.addEventListener("mousedown", (event) => event.preventDefault());
      whileConnected(ta, (signal) => {
        window.addEventListener("pagehide", cancelDictation, { signal });
        return cancelDictation;
      });
    }
    // Paste and page capture enter through the same command. It owns delivery and the
    // whole draft's history, and refuses a second upload while the first owns the field.
    // The arrival generation prevents an image reaching another draft when the floating
    // composer moves to another passage before its bytes reach the server.
    // Attaching is the user coming back to the box, as an edit is.
    sync.addMedia = async (images) => {
      if (images.length) passErrorsAt(ta);
      if (!images.length || sending || uploading || held()) return false;
      cancelDictation();
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
        if (paths.some((path) => path === null)) return false;
        if (arrivals !== attachedAt) {
          raiseError(
            "Image not added — the comment moved before it finished uploading",
            { subject: ta },
          );
          return false;
        }
        attachedMedia.push(...paths);
        renderMedia();
        draftChanged();
        // A sent message's pictures stand under its words, where a new one can arrive out
        // of view: it is the attachment's result, so it comes into view once it has its
        // size, unless the user has moved on meanwhile.
        if (sentMedia) {
          const added = mediaShelf.lastElementChild;
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
        raiseError(`Could not add image — ${error?.message ?? error}`, { subject: ta });
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
          .filter(Boolean);
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
    // send hands them on to, as a reply does to its thread (`landSent`), never on the
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
    let composing = false;
    ta.addEventListener("compositionstart", () => (composing = true));
    ta.addEventListener("compositionend", () => (composing = false));
    // A send key, or Send reached by the keyboard, in a covered box lifts the cover and
    // sends nothing (`uncover`).
    const pressed = (sender) => {
      if (errorOver(ta)) return uncover();
      if (focused() !== ta) focusDestination(ta, "return");
      submit(sender);
    };
    for (const [button, sender] of [
      [sendBtn, send],
      [altBtn, altSend],
    ]) {
      if (!button) continue;
      button.addEventListener("mousedown", (event) => {
        if (!composing) event.preventDefault();
      });
      button.addEventListener("click", () => pressed(sender));
    }
    return sync;

    function cancelDictation() {
      stopDictationRevision?.();
      stopDictationRevision = null;
      dictationGeneration += 1;
      const loading = loadingDictation;
      loadingDictation = false;
      loadingFailure = "";
      if (dictation) dictation.cancel();
      else if (loading) refresh();
    }
  }

  return { wireInput, paintInputs };
}
