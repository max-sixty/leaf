import { focused, keys } from "../keyboard/scopes.js";
import { spell } from "../keyboard/bindings.js";
import { readPastedMedia, scopedMediaUrl, writePastedMedia } from "../media.js";
import { notice } from "../notifications.js";
import { iconElement } from "../icons.js";
// One helper wires every durable composition surface: the general box, each per-thread
// reply, the compact anchored composer, and composition boxes contributed by widgets.
// `wireInput` gives every such textarea one input contract: persist each edit, keep the
// action button and placeholder current, prevent parallel submissions of one local
// surface (an impatient second click), and submit with `Mod+Enter`. Enter retains the
// textarea's native newline. The stylesheet owns
// textarea growth through `field-sizing: content`, within the room supplied by floating
// placement; script does not derive textarea height from its text. wire() returns a
// sync() the caller runs after setting .value programmatically, so the send button and
// any containing chrome agree with what's in the box: that sync refreshes the composer's
// placement for typed and programmatic edits alike, including drafts mirrored from
// another tab. When the surface accepts images, a paste uploads bytes to page media. The
// draft keeps the resulting Markdown, while the textarea shows only the reader's words
// and a thumbnail projection.
// The submit binding owns the shortcut spelling used by the placeholder and tooltip.
const SEND = "Mod+Enter";
let uploadMedia;
let inputAddress = () => null;
export const configureInput = ({ upload, address }) => {
  uploadMedia = upload;
  inputAddress = address;
};
const inputDrafts = new WeakMap();
// A wired textarea's visible value omits generated image Markdown. Readers outside
// this module ask through this seam for the complete draft; an unwired textarea keeps
// the platform's ordinary value.
export const draftOf = (ta) => inputDrafts.get(ta)?.value() ?? ta?.value ?? "";
// Focus and contextual-entry hints join the runtime's one standing paint. Repaint the
// previous and current box for each fact, since either may need to lose or gain its hint.
const inputPaints = new WeakMap();
let paintedInput = null;
let paintedAddress = null;
export const paintInputs = () => {
  const held = focused();
  const input = held && inputPaints.has(held) ? held : null;
  const addressed = inputAddress();
  const address =
    addressed?.box && inputPaints.has(addressed.box) ? addressed.box : null;
  for (const ta of new Set([paintedInput, input, paintedAddress, address]))
    inputPaints.get(ta)?.(addressed);
  paintedInput = input;
  paintedAddress = address;
};
// `sends` and `icon` state the box's own submit action. A composer in suggestion mode,
// a thread reply, and an added option share the input contract without sharing meaning.
export function wireInput(
  ta,
  {
    hint,
    accessibleName = null,
    save,
    send,
    sendBtn,
    sends,
    icon,
    altBtn = null,
    altSend = null,
    allowsMedia = () => true,
    busy = () => false,
    hasContent = (raw) => Boolean(raw.trim()),
    layout = () => {},
  },
) {
  const field = document.createElement("div");
  field.className = "lf-compose-field";
  ta.before(field);
  field.append(ta, sendBtn);
  sendBtn.classList.add("lf-icon-action", "lf-compose-submit");
  sendBtn.replaceChildren(iconElement(icon, "lf-action-icon"));
  const mediaShelf = document.createElement("div");
  mediaShelf.className = "lf-composer-media";
  mediaShelf.setAttribute("role", "group");
  mediaShelf.setAttribute("aria-label", "Pasted images");
  field.before(mediaShelf);
  let pastedMedia = [];
  let visibleValue = ta.value;
  const draftValue = () => writePastedMedia(ta.value, pastedMedia);
  const renderMedia = () => {
    mediaShelf.replaceChildren();
    mediaShelf.hidden = pastedMedia.length === 0;
    pastedMedia.forEach((path, index) => {
      const item = document.createElement("span");
      item.className = "lf-composer-media-item";
      const view = document.createElement("button");
      view.type = "button";
      view.className = "lf-media-open lf-composer-media-open";
      view.dataset.lfMediaUrl = scopedMediaUrl(path);
      view.setAttribute("aria-label", `View pasted image ${index + 1}`);
      const image = document.createElement("img");
      image.src = scopedMediaUrl(path);
      image.alt = "";
      view.append(image);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "lf-composer-media-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove pasted image ${index + 1}`);
      remove.addEventListener("click", () => {
        pastedMedia.splice(index, 1);
        renderMedia();
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        ta.focus({ preventScroll: true });
      });
      item.append(view, remove);
      mediaShelf.append(item);
    });
  };
  const hydrate = (value) => {
    const restored = readPastedMedia(value);
    pastedMedia = restored.paths;
    ta.value = restored.text;
    visibleValue = ta.value;
    renderMedia();
  };
  hydrate(ta.value);
  // The hint goes in the placeholder, where it's visible exactly while the box is
  // empty; the stable accessible name remains independent of that changing hint. The
  // button's tooltip spells the send key out. The send shortcut is focus-scoped, so
  // only the focused box may claim it. Unfocused, the placeholder may carry the live
  // contextual key that enters this exact box. These readings may be functions because
  // their labels can change while the box stands.
  const label = () => (typeof hint === "function" ? hint() : hint);
  const name = () =>
    typeof accessibleName === "function" ? accessibleName() : accessibleName;
  const sendKeys = spell(SEND);
  const sendWord = () => (typeof sends === "function" ? sends() : sends);
  const sendLabel = () => {
    const word = sendWord();
    return word.charAt(0).toUpperCase() + word.slice(1);
  };
  const paint = (addressed = inputAddress()) => {
    // Read the shared logical focus so this hint agrees with the key line and rings.
    const standing = focused() === ta;
    const suffix = standing ? sendKeys : addressed?.box === ta ? addressed.label : "";
    const placeholder = suffix ? `${label()} · ${suffix}` : label();
    if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
    const ariaLabel = name();
    if (ariaLabel && ta.getAttribute("aria-label") !== ariaLabel)
      ta.setAttribute("aria-label", ariaLabel);
  };
  inputPaints.set(ta, paint);
  const repaint = () => {
    const label = sendLabel();
    if (sendBtn.getAttribute("aria-label") !== label)
      sendBtn.setAttribute("aria-label", label);
    sendBtn.title = `${label} (${sendKeys})`;
    if (focused() === ta) paintInputs();
    else paint();
  };
  if (altBtn) altBtn.title = altBtn.textContent;
  let sending = false;
  let uploading = false;
  // Keep a disabled send reachable so the reader can discover why it will not send;
  // submit() is the behavioral guard and aria-disabled exposes the same state.
  const refresh = () => {
    repaint();
    const disabled = String(
      sending || uploading || busy() || !hasContent(draftValue()),
    );
    sendBtn.setAttribute("aria-disabled", disabled);
    altBtn?.setAttribute("aria-disabled", disabled);
    layout();
  };
  // Callers use sync after replacing .value with a stored draft. Other calls repaint
  // state without disturbing the thumbnail projection of the value already on screen.
  const sync = () => {
    if (ta.value !== visibleValue) hydrate(ta.value);
    refresh();
  };
  sync.value = draftValue;
  sync.hasMedia = () => pastedMedia.length > 0;
  inputDrafts.set(ta, sync);
  // A runtime-built box is normally wired before it can receive focus. Preserve the
  // bookkeeping too if a caller wires one that is already standing.
  repaint();
  const submit = async (sender) => {
    if (sending || uploading || busy()) return;
    // A send key on an empty box answered with silence reads as a send that
    // happened — the blind drive believed exactly that. Say the nothing out loud
    // (the notice announces too).
    const raw = draftValue();
    const text = raw.trim();
    if (!hasContent(raw)) return notice(`Nothing to ${sendWord()} — the box is empty`);
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
    visibleValue = ta.value;
    save(draftValue());
    refresh();
  });
  ta.addEventListener("paste", async (event) => {
    const images = [...(event.clipboardData?.items ?? [])]
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (!images.length) return;
    if (!allowsMedia) return;
    event.preventDefault();
    if (!allowsMedia()) {
      notice("Images can be added to comments, not replacement text");
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
  // The box's own scope: one row, so the key line's word, the "?" overlay's sentence and
  // the press are the same object. Every box the runtime wires gets it — the general box,
  // each thread's reply, the selection composer, a widget conversation — where the reference
  // used to carry one row saying "in the focused composer" for a chord that fires in all
  // of them, including widget-owned text boxes.
  // The sentence is the same in every box, so the reference names the binding once however
  // many boxes the page holds; the word is this box's, because what the press does here is
  // what the line is for — a composer in suggestion mode and a thread's reply are one
  // binding doing two things.
  keys(ta, "In a text box", [
    {
      id: "text.send",
      keys: [SEND],
      does: "Submit what you have typed",
      line: sends,
      run: () => sendBtn.click(),
    },
  ]);
  sendBtn.addEventListener("click", () => submit(send));
  altBtn?.addEventListener("click", () => submit(altSend));
  return sync;
}
