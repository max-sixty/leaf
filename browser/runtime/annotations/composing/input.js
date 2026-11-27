// Compiled from input.ts by build/typescript.mjs; edit that file.
// One helper wires every durable composition surface: the general box, each per-thread
// reply, the compact anchored composer, and composition boxes contributed by widgets.
// `wireInput` gives every such text field one input contract: persist each edit, keep the
// action button and placeholder current, prevent parallel submissions of one local
// surface (an impatient second click), and submit with Enter on a physical keyboard. A
// press on a submit control is that Enter, pressed from the box.
// Where native speech recognition is available, an empty comment offers a microphone
// in Send's place. Where it is not, as in a Firefox without it, the empty box keeps
// Send, grey and unavailable (`aria-disabled`). The user chose that over a box that
// shows no Send until it holds words.
// Dictation uses the same draft and send contract in every surface:
// empty-field status stays in the placeholder, words keep their place, and the mic's
// face carries listening. Sending and explicit closing retire capture before the
// draft can change; Escape keeps its existing close-and-keep-draft meaning.
// Shift+Enter inserts a line, the field's own binding; on touch keyboards Enter does too,
// except in a one-line field (`one-line`), where Return sends everywhere.
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
// The user writes in a box while focus is in it, on its editor or a press in its
// corner such as Dictate, or while a dictation runs in it (`writesIn`). The box's press
// at rest (`enters`) stands only while they don't, so it never stands beside the press
// in the corner, nor while the box holds a draft, an attachment alone included. A box
// whose corner stays empty at rest (`cornerAtRest` false), as the floating panel's
// field is, shows Dictate or Send there only while the user writes, or while it holds
// words the user put there (`ownWords`), and its owner keeps the corner's room exactly
// while one shows (floating-panel.css). Words that arrive in it empty from elsewhere
// (`sync.load`), such as a draft mirrored from another tab, bring no Send until the
// user's own move, so no Send arrives under a pointer resting where the corner stood
// empty (browser/AGENTS.md, "Controls stay where the user aims").
//
// An error about a box (transport/errors.js, its `subject`), such as a refused send's whose words
// came back to it or an image it would not take, stands over the box's words and
// actions, wrapping within its lines, until the user comes back to them: an edit there,
// an image attached, a press on the cover or a key there, a send key or a press putting
// the caret at the words' end and sending nothing, or Resume writing (records/drafts.js). While it stands the box sends nothing, so words the user
// has not seen again are never sent. The error is about the words, not the node, so it
// also passes once the box stops showing them: it takes up another draft (`arrive`), as
// the one passage composer does on each passage, or it is hidden or leaves the page
// (`unshown`). Every box takes this from here, the floating panel's field and a
// passage's comment box alike, and a passed error waits in the leaf's menu.
//
// Lit owns the generated field, hint, errors and action controls. The native editor is
// retained as a Node part: rendering chrome never replaces its words, caret or history.
// Local draft and dictation callbacks request Lit updates; shared readings subscribe
// through SignalWatcher, including focus and errors, without a repaint registry.
import { capitalized, counted } from "../../lib/words.js";
import { describeFailure } from "../../lib/exception.js";
import { rememberWriting } from "../../records/drafts.js";
import { keys, paintKeysWithin } from "../../dom/keyboard/scopes.js";
import { keeps } from "../../lib/keeps.js";
import {
  advertisesKeys,
  ariaBindings,
  submitBindings,
  spell,
} from "../../dom/keyboard/bindings.js";
import {
  readAttachedMedia,
  scopedMediaUrl,
  writeAttachedMedia,
} from "../../records/media.js";
import { announce, keepsNotice } from "../../transport/notifications.js";
import { offeredAction, selectableOffered } from "../../lib/controls.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  neutralSteps,
} from "../../dom/keyboard/key-sequence.js";
import { drawingThumbnail } from "./drawing-context.js";
import { LitElement, html, render, nothing, guard, ref } from "/vendor/lit.js";
import { SignalWatcher, signal, computed, untracked } from "/vendor/signals-core.js";
import "./text-field.js";
import { followBoxGrowth, readBoxPlace } from "../../records/thread/reply-landing.js";
import {
  currentLocationIn,
  focusDestination,
  focused,
  focusRevision,
} from "../../dom/focus.js";
import { whileConnected } from "../../dom/arrivals.js";
import { applicationState } from "../../state/semantic-state.js";
import { errorOver, passErrorsAt, raiseError } from "../../transport/errors.js";
import { holdRendering } from "../../base/rendering.js";
import { sizeObserver } from "../../lib/frame-pass.js";
import { scrollIntoView } from "../../readings/landing-scroll.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { coarsePointer } from "../../base/pointer.js";
import { PRESS } from "../../lib/keys.js";
import { restArming } from "../../lib/rest-arming.js";

const INPUT_DRAFT = Symbol("composition draft");
// What Shift+Return does in a box that holds lines, as its hint and Send's tooltip say it.
const NEW_LINE = "New line";

/** For its tag. */

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
const sameDrawing = (a, b) => a === b || JSON.stringify(a) === JSON.stringify(b);
let thumbnailVersion = 0;

// What the draft carries beside its words: the drawing a stroke attached, then each attached
// image. Each shows itself rather than its transport and each comes off with its own
// control, so nothing rides along with a comment unseen or beyond the user's reach. The
// drawing also takes back its last stroke here: the route a pointer or a finger has to
// that, wherever the composer stands.
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
              @click=${(event) => {
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
              }}
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
              @mousedown=${(event) => event.preventDefault()}
              @click=${drawing.undoStroke}
            ></button>
            <button
              ${offeredAction("mark", "", "Remove drawing", { action: "remove" })}
              data-lf-corner
              @mousedown=${(event) => event.preventDefault()}
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
      // A sent message's picture is the one its message draws (records/page-markdown.js,
      // `pageLinks`), in a paragraph of its own as the message sets it, with the removal
      // mark a rewrite adds.
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
export const draftOf = (ta) => ta?.[INPUT_DRAFT]?.value() ?? ta?.value ?? "";
// Ask a wired field to paint again, as its own `sync()` does, where what its hint or
// name reads has changed and the caller holds the field rather than its wiring.
export const syncInput = (ta) => ta?.[INPUT_DRAFT]?.();
// Whether the user writes in a wired box (the module header).
export const writesIn = (ta) => Boolean(ta?.[INPUT_DRAFT]?.writing());
// Whether a wired box takes no words now (`closed`), as the panel's field while a
// stance stands. It asks `closed` rather than `readOnly`, which an upload in flight
// also sets on a box that `c` may still move to another passage.
export const takesNoWords = (ta) => Boolean(ta?.[INPUT_DRAFT]?.closed());
// A box shows the key that enters it: in its placeholder while it is empty, and once its words cover the placeholder, as a draft's
// do, in its own corner before Send, over the words as Send stands (`.lf-compose-key`,
// response.css). So a box the user isn't in says how to get back into its words, as a
// thread card's reply box holding a draft does while `t` stands on the card. The user
// chose this rule, accepting one more mark wherever the key would go into a box holding
// words, over the key only in an empty box. They chose the corner inside the box, where
// the key gives way to words that reach it, leaving the key unsaid until the words
// leave it room, over a key chip hung on the box's corner, which stood over the page
// beside the box, and over a column kept for the key beside Send, which wrapped the
// words sooner. This is the box's frame and the key it lends the key hints, while its
// words cover its placeholder and the caret isn't in them. The key is the comment key
// (annotations/composing/surface.js, `coveredEntry`); a box focus stands on lends it
// `text.enter`'s instead (below).
export const coveredBox = (ta) => ta?.[INPUT_DRAFT]?.covered() ?? null;
// Whether an error stands at a box, which says it there; the panel's dot marks only
// those that stand nowhere. A box that stops showing the words passes its errors, so a
// standing one is always on screen.
export const standsAtItsBox = (error) => {
  const subject = error.subject;
  return Boolean(subject?.[INPUT_DRAFT]) && !error.passed;
};
// A box's own press at rest (`enters`, `BoxPress`), at its placeholder's far end, the
// field's `end` slot (text-field.js), as the entering word and its key are, so it
// stands only while the box's words do, and reads in their face. Its mousedown keeps
// the caret and focus where they are, and the press keeps the notice that offers it
// (transport/notifications.js, `keepsNotice`). The keyboard's route is the press's own command
// and a finger's is this, so it takes no tab stop.
const pressAtRest = (press, keys) =>
  html`<span
    slot="end"
    ${selectableOffered("button", "lf-compose-press", "inline")}
    data-lf-hint
    tabindex="-1"
    ${keepsNotice()}
    @mousedown=${(event) => event.preventDefault()}
    @click=${press.run}
    ><span class="lf-compose-press-word">${press.word}</span>${
      keys.length ? keySequenceTemplate(keySequenceModel(neutralSteps(keys))) : nothing
    }</span
  >`;

// Boot binds one input owner to the app's upload command and contextual-hint
// reading. Fields keep those capabilities for their lifetime; importing this module
// never installs or replaces application callbacks.
export function createCompositionInputs({ uploadMedia, inputHint }) {
  // Contextual destinations include geometry the application reads in its repaint.
  // Publish those two values; each field reads them with its other reactive inputs.
  const hintedBox = signal(null);
  const hintLabel = signal("");
  // A box's press stands only while a key of its would make it
  // (dom/keyboard/control-keys.js, `commandKeysNow`), which the dispatcher decides from
  // focus and the keys' liveness rather than from anything a box reads, so this frame
  // reads each offered press again, as it gives every box the comment key's
  // destination, and repaints a box whose press now reads otherwise than it drew.
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
      // as the entering word and its key are, and pressed where they read by a pointer,
      // since it stands where the box's own words do and goes when they go
      // (`pressAtRest`). It stands only while one of its keys would make it now, so never
      // on a touchscreen, which is shown no keys: there a word alone reads as status
      // rather than a control, the user judged, and the panel's menu and lists reach each
      // press's result.
      // Null where no key enters the box at rest, so not even its key stands there, as
      // while the page holds keys pressed before it loaded, which a key would only join.
      enters = () => "",
      accessibleName = null,
      // Whether the box takes no words now, as the panel's field while a stance
      // stands (panel/field-readings.js, `still`): its draft stays, unwritable, and it
      // offers neither Send nor the microphone until this says otherwise.
      closed = () => false,
      // Whether the corner shows Dictate, or Send, while the user isn't writing in the
      // empty box; false leaves it empty then.
      cornerAtRest = () => true,
      save,
      send,
      sendClass = "",
      sends,
      action: submitAction = "send",
      // The words of a second send, standing beside the field while they are given,
      // whose press calls `send` with `alternate` true.
      altLabel = null,
      // `true` to take an attached image; otherwise the sentence the user is told instead.
      // True, or why the box takes no image.
      allowsMedia = () => true,
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
    const focusInBox = computed(() => {
      focusRevision();
      return currentLocationIn(field);
    });
    const enteringHint = computed(() =>
      hintedBox.value === ta ? hintLabel.value : "",
    );
    const inputError = computed(() => errorOver(ta));
    // A one-line field, such as an option's title, has no line for Return to break, so
    // Return sends it from every keyboard, a phone's included.
    const oneLine = ta.hasAttribute("one-line");
    const sendBindings = () => (oneLine ? ["Enter", "Mod+Enter"] : submitBindings());
    const sendKey = () => sendBindings().slice(0, 1).map(spell).join("");
    // Where Return sends a box that holds lines, Shift+Return makes one.
    const lineKeyOf = (sendKeys) =>
      sendKeys === spell("Enter") && !oneLine ? spell("Shift+Enter") : "";
    // The editor is kept whole in Lit's Node part. A rewrite's submit root sits
    // beside its existing Discard control, without an extra layout box.
    const submitEnd = document.createComment("");
    if (submitIn) submitIn.append(submitEnd);
    let sendBtn = null;
    let mic = null;
    let composing = false;
    // Firefox lacks speech recognition; WebKit has it only under its prefix.
    const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    const actionWord = () =>
      typeof submitAction === "function" ? submitAction() : submitAction;
    const offersDictation = Boolean(
      Recognition && actionWord() === "send" && !submitIn,
    );
    let dictation = null;
    let loadingDictation = false;
    let dictationGeneration = 0;
    let loadingFailure = "";
    let stopDictationRevision = null;
    const dictationPhase = () =>
      loadingDictation ? "starting" : (dictation?.phase ?? "idle");
    // A signal, so a reader of `writesIn` outside the box hears a dictation end.
    const dictating = signal(false);
    const writing = () => focusInBox.value || dictating.value;
    const dictationStatus = () =>
      loadingDictation
        ? "Starting microphone…"
        : loadingFailure || dictation?.status || "";
    // A send key on covered words lifts the cover and sends nothing.
    const uncover = () => {
      passErrorsAt(ta);
      const end = ta.value.length;
      focusDestination(ta, "move", { caret: [end, end] });
    };
    const held = () => busy() || inputError.value !== null;
    let mediaShelf;
    let attachedMedia = [];
    const draftValue = () => writeAttachedMedia(ta.value, attachedMedia);
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
    let shelfSeen = null;
    let arrivals = 0;
    const putDrawing =
      drawing &&
      ((drawn) => {
        shelfSeen = { drawing: drawn, media: [...attachedMedia] };
        drawing.replace(drawn);
        const strokes = drawn?.strokes.length ?? 0;
        announce(strokes ? `Drawing, ${counted(strokes, "stroke")}.` : "No drawing.");
      });
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
    const hydrate = (value) => {
      cancelDictation();
      const restored = readAttachedMedia(value);
      attachedMedia = restored.paths;
      ta.value = restored.text;
      ta.restartHistory();
      shelfSeen = null;
    };
    hydrate(ta.value);
    // Whether the box's words are the user's own: those it was made holding, or ones
    // they wrote in it since it was last empty, not ones loaded into it empty.
    let ownWords = hasContent(draftValue());
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
    // takes presses only once the pointer has rested on it (`restArming`,
    // response.css), so a quick press at the words' end places the caret. Typing, or a
    // press on the words, puts Send away until the pointer next comes to it, so a
    // second press of a double-click selects rather than sends.
    const sendArming = restArming(() => sendBtn, {
      point: () => ta.parentElement?.setAttribute("data-lf-send-pointed", ""),
      arm: () => ta.parentElement?.setAttribute("data-lf-send-armed", ""),
      unpoint: () => {
        ta.parentElement?.removeAttribute("data-lf-send-pointed");
        ta.parentElement?.removeAttribute("data-lf-send-armed");
      },
    });
    const point = sendArming.move;
    const unpoint = sendArming.reset;
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
      const status = dictationStatus();
      const offered = writing() || hasWords || status ? "" : enters();
      const press = typeof offered === "string" ? null : offered;
      const suffix =
        !advertising || offered === null
          ? ""
          : focusedHere.value
            ? sendKeys
            : press
              ? ""
              : enteringHint.value;
      const pressKeys = press && advertising ? press.keys : [];
      const word = status || label();
      // Where Return sends a box that holds lines, the box says which key makes one,
      // beside the key that sends, so a writer meets Shift+Return before Return sends
      // half a message; the send control's tooltip says the same.
      const lineKey = lineKeyOf(sendKeys);
      const lineHint = focusedHere.value && !status ? lineKey : "";
      const entering = suffix && typeof offered === "string" ? offered : "";
      // What a press says at rest: its word and the keys that would make it now, or
      // nothing where none would (`enters`).
      const said = (reading) =>
        reading.keys.length ? [reading.word, ...reading.keys].join(" ") : "";
      const pressText = press ? said(press) : "";
      // The press as drawn, whose keys its owner reads at each ask, so the recheck
      // costs that reading alone rather than the box's words.
      if (press) pressing.set(field, () => said(press) !== pressText);
      else pressing.delete(field);
      const shown = pressText ? press : null;
      // A box whose words are all at its end, as an open thread's Reply is in the
      // panel, starts with them.
      const keyed = [[word, entering].filter(Boolean).join(" · "), suffix]
        .filter(Boolean)
        .join(" ");
      const placeholder =
        (suffix || shown) && !status
          ? [keyed, pressText, lineHint && `${NEW_LINE} ${lineHint}`]
              .filter(Boolean)
              .join(" · ")
          : word;
      if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
      // The paint is the one writer of `readOnly`: a box that takes no words, and one
      // whose image is still uploading (`addMedia`), which keeps its Send and microphone.
      const shut = closed();
      const locked = shut || uploading;
      if (ta.readOnly !== locked) ta.readOnly = locked;
      const ariaLabel = name();
      if (ariaLabel) keeps(ta, "aria-label", ariaLabel);
      const parts = status ? null : hintParts?.();
      const lead = status ? "" : hintLead();
      const richHint = ((suffix || shown) && !status) || parts != null || lead;
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
        }${shown && !status ? pressAtRest(shown, pressKeys) : nothing}`,
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
      const phase = dictationPhase();
      const live = phase === "starting" || phase === "listening";
      const failed = loadingFailure || dictation?.failure;
      const corner = cornerAtRest() || writing();
      const micShown =
        offersDictation && !shut && (phase !== "idle" || (!hasWords && corner));
      const micAction = live
        ? "Stop dictation"
        : phase === "stopping"
          ? "Finishing dictation"
          : failed
            ? "Retry dictation"
            : "Dictate";
      const submitControl = html`<button
        type="button"
        ${offeredAction("symbol", `${sendClass} lf-compose-submit`.trim(), action, {
          action: actionWord(),
        })}
        ?data-lf-disc=${!submitIn}
        data-lf-tone="accent"
        aria-disabled=${String(!canSend())}
        ?data-lf-empty=${!hasWords}
        ?hidden=${micShown || shut || (!corner && !(hasWords && ownWords))}
        aria-keyshortcuts=${sendBindings().flatMap(ariaBindings).join(" ")}
        @mousedown=${keepEditing}
        @click=${() => pressed()}
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
      const dictationState =
        phase !== "idle"
          ? phase
          : failed && dictation?.failure?.error !== "no-speech"
            ? "failed"
            : nothing;
      const dictationControl = offersDictation
        ? html`<button
            type="button"
            ${offeredAction("symbol", "lf-compose-dictate", micAction, {
              action: "dictate",
            })}
            ?hidden=${!micShown}
            data-lf-disc
            data-lf-tone=${dictationState === "failed" ? "negative" : nothing}
            data-lf-dictation=${dictationState}
            aria-pressed=${String(live)}
            aria-description=${status || nothing}
            @mousedown=${(event) => event.preventDefault()}
          ></button>`
        : nothing;
      const content = html`
        ${ta}${sentMedia ? shelf : nothing} ${submitIn ? nothing : submitControl}
        ${dictationControl}
        <kbd
          class="lf-key-badge lf-binding-seat lf-compose-key"
          aria-hidden="true"
        ></kbd>
        <p
          class="lf-compose-error"
          aria-hidden="true"
          ?hidden=${!error}
          .lfPreview=${() => (error ? { name: error.message } : null)}
          @pointerdown=${(event) => {
            event.preventDefault();
            uncover();
          }}
        >
          <span>${error?.message ?? ""}</span>
        </p>
      `;
      const altWord = typeof altLabel === "function" ? altLabel() : altLabel;
      const alternate = altWord
        ? html`<button
            type="button"
            ${offeredAction("word", "lf-compose-alt")}
            aria-disabled=${String(!canSend())}
            @mousedown=${keepEditing}
            @click=${() => pressed(true)}
          >
            ${altWord}
          </button>`
        : nothing;
      return html`${sentMedia ? nothing : shelf}
        <div
          class="lf-compose-field"
          ?data-lf-words=${hasWords}
          @pointermove=${point}
          @pointerleave=${point}
          @pointerdown=${(event) => {
            if (!event.composedPath().some((node) => node === sendBtn)) unpoint();
          }}
        >
          ${content}
        </div>
        ${alternate}`;
    };
    field.updated = () =>
      untracked(() => {
        if (sendBtn?.hidden && focused() === sendBtn) focusDestination(ta, "return");
        if (mic?.hidden && focused() === mic) focusDestination(ta, "return");
        paintKeysWithin(field);
        if (submitIn) paintKeysWithin(submitIn);
      });
    const refresh = () => {
      dictating.value = dictationPhase() !== "idle";
      if (dictationPhase() === "idle") {
        stopDictationRevision?.();
        stopDictationRevision = null;
      }
      recordMedia();
      field.requestUpdate();
    };
    const draftChanged = () => {
      ownWords = hasContent(draftValue());
      save(draftValue());
      refresh();
    };
    // sync() asks for the paint of what the box holds. It is not how a draft gets in:
    // what the user would miss is the words and the attached images together, and the
    // images show only in the shelf, so a caller writing .value states half a draft.
    // Emptying a box that way would leave an image in a box the runtime then reads as
    // still holding something — the box would say "draft kept" over a comment it just
    // sent, and the picture would ride into the next passage's draft.
    const sync = () => refresh();
    // Closing belongs to each surface's existing owner, rather than a DOM observer
    // guessing whether a hidden field is merely outside the viewport.
    sync.cancelDictation = cancelDictation;
    sync.value = draftValue;
    sync.closed = closed;
    sync.writing = writing;
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
      if (!value) ownWords = false;
      refresh();
    };
    ta[INPUT_DRAFT] = sync;
    // The box's first paint names its send button and placeholder, and keeps the focus
    // bookkeeping if a caller wires one the user is already in.
    refresh();
    // Wiring needs actual controls for their keyboard declarations. First render is
    // synchronous; subsequent updates use Lit's microtask batching.
    field.performUpdate();
    const visualField = field.querySelector("div.lf-compose-field");
    if (!visualField) throw new Error("Composition template has no field frame");
    sync.composition = () => ({ field: visualField, frame: field });
    const boxKey = visualField.querySelector(":scope > .lf-compose-key");
    if (!boxKey) throw new Error("Composition template has no box key");
    sync.covered = () =>
      focused() !== ta && hasContent(draftValue())
        ? { frame: visualField, key: boxKey }
        : null;
    // A box the user stands on rather than in, as a walk's stop at a kept comment
    // leaves them (features/anchor-travel.js, `onFrame`), takes `c` or Enter into its
    // words, with the caret after them. It keeps its resting edge (response.css) and
    // says `c` in its own corner (`bindingBadge`), since its words cover the
    // placeholder, as every box whose words do says the key that enters it
    // (`coveredBox`). The user chose this. Rejected: the key after the words, where the
    // caret will stand, which has no room where the last line runs to the box's end,
    // as a one-line comment's does in a wide window; the key in the panel's walk
    // status, away from the box the user is reading; and the words greyed until the
    // caret enters, which reads as a placeholder.
    keys(visualField, "On a text box", [
      {
        id: "text.enter",
        touch: false,
        keys: ["c", "Enter"],
        title: "write",
        control: visualField,
        bindingBadge: boxKey,
        when: () => focused() === visualField,
        run: () => {
          const end = ta.value.length;
          focusDestination(ta, "move", { caret: [end, end] });
        },
      },
    ]);
    sendBtn = (submitIn ?? field).querySelector("button.lf-compose-submit");
    // The key that sends from the box is the box's own `text.send`, which sends rather
    // than pressing Send, so the box says it beside Send: as a key chip in Send's
    // preview (annotations/preview.js), with the key that makes a new line where Return sends, and
    // in its `aria-keyshortcuts`, both from `sendBindings`.
    if (sendBtn)
      sendBtn.lfPreview = () => {
        const line = advertisesKeys() ? lineKeyOf(sendKey()) : "";
        return {
          keys: [sendBindings().slice(0, 1)],
          detail: [line && html`${NEW_LINE} <kbd class="lf-key-badge">${line}</kbd>`],
        };
      };
    mic = field.querySelector("button.lf-compose-dictate");
    sync.button = sendBtn;
    whileConnected(field, (signal) => {
      coarsePointer.addEventListener("change", refresh, { signal });
      return () => {
        watchError.disconnect();
        watchedError = false;
        passErrorsAt(ta);
      };
    });
    const submit = async (alternate = false) => {
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
        await send(text, raw, () => draftValue() === raw, ta.value, alternate);
      } finally {
        sending = false;
        refresh();
      }
    };
    ta.addEventListener("input", () => {
      unpoint();
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
    // A press on a box that takes no words leaves the caret where it was (`closed`),
    // and goes on to whatever the box's owner does with it, such as commenting on words
    // selected on the page.
    ta.addEventListener("pointerdown", (event) => {
      if (closed()) event.preventDefault();
    });
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
    if (mic && Recognition) {
      const activateDictation = async () => {
        if (dictationPhase() === "stopping" || sending || uploading || held()) return;
        if (loadingDictation) {
          cancelDictation();
          return;
        }
        if (dictation && dictation.phase !== "idle") {
          dictation.stop();
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
      whileConnected(ta, (signal) => {
        window.addEventListener("pagehide", cancelDictation, { signal });
        return cancelDictation;
      });
    }
    // Paste and page capture enter through the same command. It owns delivery and the
    // whole draft's history, and refuses a second upload while the first owns the field.
    // The arrival generation prevents an image reaching another draft when the floating
    // composer moves to another passage before its bytes reach the server.
    // Attaching is the user coming back to the box, as an edit is. The upload and the
    // thumbnail it ends in belong to the rendering of the gesture that attached them
    // (base/rendering.js, `holdRendering`), so the box moves for the thumbnail as for the
    // user's own change rather than for news (dom/box-motion.js, "Whose change it is").
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
      uploading = true;
      ta.setAttribute("aria-busy", "true");
      refresh();
      // The thumbnail arriving in the shelf is the attachment's result, so only a
      // listener is told; a failure, which shows nothing, is a notice.
      announce(
        images.length === 1 ? "Adding image…" : `Adding ${images.length} images…`,
      );
      const attachedAt = arrivals;
      const attached = holdRendering();
      try {
        const paths = await Promise.all(images.map((image) => uploadMedia(image)));
        if (!paths.every((path) => path !== null)) return false;
        // A thumbnail arrives at its picture's size. A picture that decodes after its
        // tile is drawn grows the tile from its empty size, moving the shelf without
        // input, so each picture is decoded first and the tile's image draws from it.
        await Promise.all(
          paths.map((path) => {
            const picture = document.createElement("img");
            picture.src = scopedMediaUrl(path);
            return picture.decode().catch(() => {});
          }),
        );
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
        ta.removeAttribute("aria-busy");
        refresh();
        attached();
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
    // each thread's reply, the selection composer, a widget thread — rather than one row in
    // the reference saying "in the focused composer" for a sequence that fires in all
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
        run: () => pressed(),
      },
      ...rows,
    ]);
    // The field owns text editing; this owner alone reserves Return for its declared
    // submit binding. An unwired source editor therefore keeps Return on every device.
    ta.addEventListener("lf-edit-return", (event) => {
      if (sendBindings().includes("Enter")) event.preventDefault();
    });
    // A press on a submit control is the send key pressed from the box, so it leaves the
    // user where Enter does: wherever the send hands them on to, as every message does to
    // its thread (`landSent`), or else in the box, as a widget's box that stays to take
    // more, or a press that sent nothing, leaves them, never on the control, where the
    // next letters would fall on nothing. A pointer press never takes the focus (moving
    // it is mousedown's default), so the box keeps it until the send moves it. A keyboard
    // press on the control, or a pointer press while the user was elsewhere, puts the
    // user in the box only where the send left them where they were, so a send that
    // lands takes them from the control to its thread without passing through the box.
    //
    // Except while an input method holds unfinished words: leaving the box is what
    // finishes them, so there the press takes the focus, and the words
    // are committed before the click sends them. Held in the box, they would be sent
    // unfinished, and the input method's later commit would write them back into the box
    // the send just emptied. Enter never meets this, since the input method takes Enter.
    ta.addEventListener("compositionstart", () => (composing = true));
    ta.addEventListener("compositionend", () => (composing = false));
    // A send key, or Send reached by the keyboard, in a covered box lifts the cover and
    // sends nothing (`uncover`).
    const pressed = (alternate = false) => {
      if (inputError.value) return uncover();
      const from = focused();
      void submit(alternate);
      if (from !== ta && focused() === from) focusDestination(ta, "return");
    };
    return sync;

    function keepEditing(event) {
      if (!composing) event.preventDefault();
    }

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

  return { wireInput, publishInputHint };
}
