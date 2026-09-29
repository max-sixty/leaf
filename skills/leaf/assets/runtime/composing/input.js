import { focused, keys } from "../keyboard/scopes.js";
import { repaint } from "../repaint.js";
import { keeps, keepsText } from "../widget-elements.js";
import { advertisesKeys, submitBindings, submitLabel } from "../keyboard/bindings.js";
import { readPastedMedia, scopedMediaUrl, writePastedMedia } from "../media.js";
import { notice } from "../notifications.js";
import { iconElement } from "../icons.js";
import { LitElement, html } from "../../vendor/browser-runtime.js";
import "./text-field.js";
import { followBoxGrowth, readBoxPlace } from "../thread/reply-landing.js";
// One helper wires every durable composition surface: the general box, each per-thread
// reply, the compact anchored composer, and composition boxes contributed by widgets.
// `wireInput` gives every such text field one input contract: persist each edit, keep the
// action button and placeholder current, prevent parallel submissions of one local
// surface (an impatient second click), and submit with Enter on a physical keyboard. A
// press on a submit control is that Enter: it leaves the user in the box.
// Shift+Enter inserts a line, the field's own binding; on touch keyboards Enter does too.
// Mod+Enter remains another route to submit. The field grows with its words, within the
// room supplied by floating placement; script does not derive its height from its text. When the surface
// accepts images, a paste uploads bytes to page media; one that does not says so in a
// notice, so no box answers a pasted picture with silence. The draft keeps the resulting
// Markdown, while the field shows only the user's words and a thumbnail projection.
// So the box holds more than its .value, and wire() returns the seam that says so:
// sync.value() reads the complete draft, sync.load() replaces it — a stored record, a
// draft mirrored from another tab, or the emptiness a send leaves — and sync() says the
// box's standing changed. Outside this module, .value is the user's words alone and
// nothing writes it.
// The submit binding owns the shortcut spelling used by the placeholder and tooltip.
//
// What the box holds changes in the turn that changes it: the words and pasted images
// (the field's own value, which its caret and every reader after the writer depend on),
// and whether a send or upload is under way. What that looks like is painted once per
// frame, in the runtime's one standing paint (repaint.js): the send button's name, its
// disabled state and the placeholder in `paintInputs`, and the floating composer's
// placement in chrome layout's pass, which runs first. A change marks its box stale and
// asks for that paint, so a keystroke, an open that loads a draft twice, and a send that
// settles and closes the box each paint and measure once, after their writes, instead of
// interleaving a forced style recalculation with each. That paint runs in the frame the
// change first shows in, so the button and placeholder never trail the words.
const inputDrafts = new WeakMap();

const MEDIA_SHELF_TAG = "leaf-pasted-media-shelf";

class PastedMediaShelf extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  constructor() {
    super();
    this.model = [];
    this.removeMedia = null;
  }

  createRenderRoot() {
    return this;
  }

  present(model, removeMedia) {
    this.model = model;
    this.removeMedia = removeMedia;
    this.performUpdate();
  }

  updated() {
    this.hidden = this.model.length === 0;
  }

  render() {
    return this.model.map(
      ({ index, url }) => html`
        <span class="lf-composer-media-item">
          <button
            type="button"
            class="lf-media-open lf-composer-media-open"
            data-lf-media-url=${url}
            aria-label=${`View pasted image ${index + 1}`}
          >
            <img src=${url} alt="" />
          </button>
          <button
            type="button"
            class="lf-composer-media-remove"
            aria-label=${`Remove pasted image ${index + 1}`}
            @click=${() => this.removeMedia(index)}
          >
            ×
          </button>
        </span>
      `,
    );
  }
}

if (!customElements.get(MEDIA_SHELF_TAG))
  customElements.define(MEDIA_SHELF_TAG, PastedMediaShelf);

// A wired field's visible value omits generated image Markdown. Readers outside
// this module ask through this seam for the complete draft; an unwired box keeps
// its ordinary value.
export const draftOf = (ta) => inputDrafts.get(ta)?.value() ?? ta?.value ?? "";
// Boot binds one input owner to the app's upload command and contextual-hint
// reading. Fields keep those capabilities for their lifetime; importing this module
// never installs or replaces application callbacks.
export function createCompositionInputs({ uploadMedia, inputHint }) {
  // The standing paint paints every box whose own state changed since it last ran, and
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
  // `sends` states the box's own submit action. Composers send by default; a caller whose
  // action differs, such as adding an option, supplies the matching icon.
  function wireInput(
    ta,
    {
      hint,
      accessibleName = null,
      save,
      send,
      sendBtn,
      sends,
      icon = "send",
      altBtn = null,
      altSend = null,
      // `true` to take a pasted image; otherwise the sentence the user is told instead.
      allowsMedia = () => true,
      busy = () => false,
      hasContent = (raw) => Boolean(raw),
      // The caller's own rendering of what the box holds, run in the box's paint.
      paint: paintOwn = () => {},
    },
  ) {
    const field = document.createElement("div");
    field.className = "lf-compose-field";
    ta.before(field);
    // The placeholder with its send key drawn as a key: the field shows it in place of
    // the plain placeholder while it is in the field, which is while there is a key to
    // show.
    const visibleHint = document.createElement("span");
    visibleHint.className = "lf-compose-placeholder";
    visibleHint.slot = "placeholder";
    const hintLabel = document.createElement("span");
    const hintKey = document.createElement("kbd");
    hintKey.className = "lf-key-badge";
    visibleHint.append(hintLabel, hintKey);
    field.append(ta, sendBtn);
    // These two are the press's whole face, and the theme keys the glyph's colour on the
    // pair, so a box cannot be handed a send button dressed as something else. `primary`
    // is a different face: it dresses the press's own box, which is the hit target and
    // stands larger than the disc wherever the pointer is coarse. A send press never
    // wears it.
    sendBtn.classList.add("lf-icon-action", "lf-compose-submit");
    sendBtn.replaceChildren(iconElement(icon, "lf-action-icon"));
    const mediaShelf = document.createElement(MEDIA_SHELF_TAG);
    mediaShelf.className = "lf-composer-media";
    mediaShelf.setAttribute("role", "group");
    mediaShelf.setAttribute("aria-label", "Pasted images");
    field.before(mediaShelf);
    let pastedMedia = [];
    const draftValue = () => writePastedMedia(ta.value, pastedMedia);
    const removeMedia = (index) => {
      pastedMedia.splice(index, 1);
      renderMedia();
      ta.dispatchEvent(new Event("input", { bubbles: true }));
      ta.focus({ preventScroll: true });
    };
    const renderMedia = () => {
      mediaShelf.present(
        Object.freeze(
          pastedMedia.map((path, index) =>
            Object.freeze({ index, url: scopedMediaUrl(path) }),
          ),
        ),
        removeMedia,
      );
    };
    const hydrate = (value) => {
      const restored = readPastedMedia(value);
      pastedMedia = restored.paths;
      ta.value = restored.text;
      renderMedia();
    };
    hydrate(ta.value);
    // Keep the full native placeholder, but paint a copy so only the key can use mono.
    // The accessible name stays independent of that changing hint. The send button's
    // tooltip spells out its key. A focused box claims the send key; an unfocused box
    // may show the contextual key that enters it; a finger is shown neither
    // (`advertisesKeys`). Labels can change while a box stands.
    const label = () => (typeof hint === "function" ? hint() : hint);
    const name = () =>
      typeof accessibleName === "function" ? accessibleName() : accessibleName;
    const sendWord = () => (typeof sends === "function" ? sends() : sends);
    const sendLabel = () => {
      const word = sendWord();
      return word.charAt(0).toUpperCase() + word.slice(1);
    };
    if (altBtn) altBtn.title = altBtn.textContent;
    let sending = false;
    let uploading = false;
    // Everything the box shows about its standing, written only where it differs from
    // what stands: a text node replaced inside the chrome restyles far more than the node.
    const paint = (contextualHint) => {
      // Read the shared logical focus so this hint agrees with the shortcut bar and rings.
      const standing = focused() === ta;
      const advertising = advertisesKeys();
      const sendKeys = advertising ? submitLabel() : "";
      const suffix = !advertising
        ? ""
        : standing
          ? sendKeys
          : contextualHint?.box === ta
            ? contextualHint.label
            : "";
      const word = label();
      const placeholder = suffix ? `${word} ${suffix}` : word;
      if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
      if (suffix) {
        keepsText(hintLabel, word);
        keepsText(hintKey, suffix);
        if (visibleHint.parentNode !== ta) ta.append(visibleHint);
      } else visibleHint.remove();
      const ariaLabel = name();
      if (ariaLabel) keeps(ta, "aria-label", ariaLabel);
      const action = sendLabel();
      keeps(sendBtn, "aria-label", action);
      keeps(sendBtn, "title", sendKeys ? `${action} (${sendKeys})` : action);
      // Keep a disabled send reachable so the user can discover why it will not send;
      // submit() is the behavioral guard and aria-disabled exposes the same state.
      const disabled = sending || uploading || busy() || !hasContent(draftValue());
      keeps(sendBtn, "aria-disabled", disabled);
      if (altBtn) keeps(altBtn, "aria-disabled", disabled);
      paintOwn();
    };
    inputPaints.set(ta, paint);
    const refresh = () => {
      stale.add(ta);
      repaint();
    };
    // sync() asks for the paint of what the box holds. It is not how a draft gets in:
    // what the user would miss is the words and the pasted images together, and the
    // images show only in the shelf, so a caller writing .value states half a draft.
    // Emptying a box that way left an image standing in a box the runtime then read as
    // still holding something — the box said "draft kept" over a comment it had just
    // sent, and the picture rode into the next passage's draft.
    const sync = () => refresh();
    sync.value = draftValue;
    sync.hasMedia = () => pastedMedia.length > 0;
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
    // bookkeeping if a caller wires one that is already standing.
    refresh();
    const submit = async (sender) => {
      if (sending || uploading || busy()) return;
      // A send key on an empty box answered with silence reads as a send that
      // happened — the blind drive believed exactly that. Say the nothing out loud
      // (the notice announces too).
      const raw = draftValue();
      const text = raw.trim();
      if (!hasContent(raw))
        return notice(`Nothing to ${sendWord()} — the box is empty`);
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
      save(draftValue());
      refresh();
      // A box a thread or seat holds keeps its controls in view as it grows
      // (`followBoxGrowth`). On the user's own keystrokes and nothing else: a send settling
      // after they scrolled away, or a draft mirrored from another tab, must not pull the
      // page back. Instant, not smooth — a line typed while the last line's glide is still
      // running lands where that glide was going, two lines short of the box it is now.
      if (focused() === ta) followBoxGrowth(ta);
    });
    ta.addEventListener("focus", () => readBoxPlace(ta));
    ta.addEventListener("paste", async (event) => {
      const images = [...(event.clipboardData?.items ?? [])]
        .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
        .map((item) => item.getAsFile())
        .filter(Boolean);
      if (!images.length) return;
      event.preventDefault();
      // A refusal is a sentence, so every box that will not take a picture says why it
      // will not. A silent one reads as a paste that worked — the same failure the empty
      // send below is written against — and the box that stayed silent was the one whose
      // caller declined images outright rather than the one that declines them in a mode.
      const allowed = allowsMedia();
      if (allowed !== true) {
        notice(allowed);
        return;
      }

      // Keep the current words visible while the bounded local upload runs. Send remains
      // reachable but inert and exposes the same busy state through aria-disabled.
      const wasReadOnly = ta.readOnly;
      uploading = true;
      ta.readOnly = true;
      ta.setAttribute("aria-busy", "true");
      refresh();
      notice(images.length === 1 ? "Adding image…" : `Adding ${images.length} images…`);
      try {
        const paths = await Promise.all(images.map((image) => uploadMedia(image)));
        if (paths.some((path) => path === null)) return;
        pastedMedia.push(...paths);
        renderMedia();
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        notice(images.length === 1 ? "Image added" : `${images.length} images added`);
      } catch (error) {
        notice(`Could not add image — ${error?.message ?? error}`);
      } finally {
        uploading = false;
        ta.readOnly = wasReadOnly;
        ta.removeAttribute("aria-busy");
        refresh();
        if (ta.isConnected) ta.focus();
      }
    });
    // The box's own scope: one row, so the shortcut bar's word, the command reference dialog's sentence and
    // the press are the same object. Every box the runtime wires gets it — the general box,
    // each thread's reply, the selection composer, a widget thread — where the reference
    // used to carry one row saying "in the focused composer" for a sequence that fires in all
    // of them, including widget-owned text boxes.
    // The sentence is the same in every box, so the reference names the binding once however
    // many boxes the page holds; the word is this box's, because what the press does here is
    // what the line is for — a composer in suggestion mode and a thread's reply are one
    // binding doing two things.
    keys(ta, "In a text box", [
      {
        id: "text.send",
        keys: submitBindings,
        label: submitLabel,
        does: "Submit what you have typed",
        line: sends,
        run: () => sendBtn.click(),
      },
    ]);
    // A press on a submit control is the send key pressed from the box, so it leaves the
    // user where Enter does: in the box, where the next letters are words rather than page
    // keys. A pointer press never takes the focus (moving it is mousedown's default), so the
    // box keeps it throughout and nothing hears it leave. A keyboard press on the control,
    // or a pointer press while the user stood elsewhere, puts the user in the box before
    // the submission, so what the send does next starts from the state Enter starts it
    // from — a composer that gives way to its thread hands the user on the same way.
    //
    // Except while an input method holds unfinished words: leaving the box is what
    // finishes them, so there the press takes the focus as it always did, and the words
    // are committed before the click sends them. Held in the box, they were sent
    // unfinished, and the input method's later commit wrote them back into the box the
    // send had just emptied. Enter never meets this, since the input method takes Enter.
    let composing = false;
    ta.addEventListener("compositionstart", () => (composing = true));
    ta.addEventListener("compositionend", () => (composing = false));
    const pressed = (sender) => {
      if (focused() !== ta) ta.focus({ preventScroll: true });
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
  }

  return { wireInput, paintInputs };
}
