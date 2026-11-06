/* Pointing reads; pressing acts (browser/AGENTS.md, "Pointing reads; pressing acts"):
   the one owner of what a mark, control or value says before a press acts on it.

   Anything may preview, and the innermost under the pointer, the focus or the finger
   does:

   - An element declares what pointing at it reads as its `lfPreview()`: words or a
     template in the tooltip face, `{popover: words}` in the larger popover face
     (`.lf-popover`, controls.css), or null where it says nothing now. A widget declares
     it with no import, as it declares `lfCommands` and `lfCopy()`, so off Leaf it reads
     nothing (module-input.md, "Previews").
   - A control previews its word and its keys without declaring either: the accessible
     name its symbol doesn't say, any `aria-description` the runtime gave it, and each
     press that reaches it (control-keys.js, `controlKeys`) as key chips, which a
     coarse pointer leaves out with every other advertised key. A control whose face
     says its word and that no key reaches previews nothing. A field the user types in
     previews nothing: its words are what they read.
   - A link into the page previews the place it names, and what that place holds
     (place-preview.js), since that is what pressing it opens.
   - A range with no element of its own, as a passage mark is, is its owner's to hit
     test, so the owner says where the pointer rests (`pointRange`) and this module does
     the rest, placing the preview by the line the pointer is on.

   Nothing standing open (`aria-expanded="true"`) previews, since what pressing it opens
   is already in front of the user, and the search goes on outward from it, as it does
   from a proxy, whose thing previews for it. A preview is read once, as it shows, so its
   words keep still while the user reads them, as a status that ages beneath them would
   not.

   One preview stands at a time, in one element: a hint popover (`popover="hint"`), in
   the top layer, so it stands over a modal or an open popover around its target, and a
   hint closes no popover the user opened. It takes no pointer and holds no control, so
   it is no layer the keyboard tiers its scopes over (layer-stack.js). It stands beside
   its target by CSS anchor positioning, the target named by css-anchors.js: centred
   below it, above where the window has no room below, and above a finger that holds it,
   which covers what lies below. The browser carries it through every scroll that moves
   its target, and nothing around the target moves. A range's preview stands by insets
   from the element holding the range, measured when it shows.

   Its routes:

   - A pointer resting on a target for `DWELL` shows its preview; moving onto another
     target within `WARM` of the last one shows the next at once, so reading along a row
     of controls waits once. Leaving the target hides it, and so do a press and any key,
     as the platform's tooltip goes; the target then stays quiet until the pointer comes
     back to it. A target that arrives under a pointer the user hasn't moved shows
     nothing, so news landing under a resting pointer never covers what the user reads,
     and nor does one a pointer reaches while it carries a press, as in a drag. A tab the
     user leaves takes its preview away.
   - Keyboard focus the browser shows (`:focus-visible`) shows its target's preview at
     once, and leaving the target hides it. A screen reader hears a declared preview as
     the focused target's description (`ariaDescribedByElements`) while it stands; a
     control's preview says what its accessible name and `aria-keyshortcuts` already do,
     and a proxy describes what it stands for with its own markup, as a gloss's does.
   - A finger held on a target for `DWELL` shows its preview, and the finger reads its
     neighbours by sliding onto them: one of the same parent shows its own instead.
     Releasing after the preview showed presses the target it ends on, or none when it
     ends off them, so a finger that reads the wrong word slides off before letting go;
     a tap releases before then and the browser's own click presses. The release presses
     by dispatching the target's click, counted as a pointer's, and claims the browser's
     own click after it (`claimReleaseClick`, focus.js), since a finger held long enough
     to read may get none and the press may put something else under the finger, such
     as the thread a margin entry opens. It first focuses the target without a ring, as
     a pointer's press does, so what the press opens is laid out with the user on it. A
     press or release with a modifier is not this gesture (`plainPress`). Touch capture
     is released at the press so the slide is heard over each neighbour, and a finger
     that starts scrolling ends the hold with `pointercancel`, which presses nothing; a
     target that should not scroll from a press says so with `touch-action`. While a
     preview is held, the platform's long-press menu stays shut.
   - Escape hides the preview standing and still takes its own step (keyboard/AGENTS.md,
     "Escape"): a preview is in front of the user, not a step of what they are doing,
     so dismissing one never costs a press.

   Each pointer boundary costs the path it walks: the nodes under the pointer, and for a
   control the page's commands, never the page's elements (root AGENTS.md,
   "Responsiveness"). The target a finger holds wears `data-lf-held` while the preview
   stands, so its surface can keep it where the finger is (margin-layout.js, `HELD`).

   Decisions: one dwell for the pointer and the finger, 200 ms, hides a flicker as either
   crosses targets without holding the user up; the margin's labels waited 90 ms, the
   platform's tooltips about a second. A preview says its words whole, wrapping where
   they run long, where a margin entry's label cut its question to one line. It stands by
   its own target and may cover a neighbouring entry, which still takes the pointer
   through it: the margin's labels each measured every entry on the page to stand clear
   of them, a page-wide read on every hover. Rejected: `interestfor`, which gives a
   control the same three routes natively but ships only in Chromium; the platform's
   `title`, which no finger or keyboard reads and which can't draw a key chip; a popover's
   implicit anchor (`showPopover({source})`), which Firefox 157 keeps on the first source
   it was shown with; and a preview that follows its target by a script, which trails
   each scroll by a frame. */
import { html, nothing, render } from "/runtime/framework.js";
import { anchorAt, anchorElement, anchorName } from "./css-anchors.js";
import { closeNativeLayer, showNativeLayer } from "./keyboard/layer-stack.js";
import { controlKeys } from "./keyboard/control-keys.js";
import { advertisesKeys } from "./keyboard/bindings.js";
import {
  claimReleaseClick,
  focused,
  nativeFocusTarget,
  onCurrentLocation,
  typesText,
} from "./focus.js";
import { plainPress } from "./pointer.js";
import { isElement, renderedParent } from "./shadow-tree.js";
import { keeps } from "./keeps.js";
import { watchOwner } from "./arrivals.js";
import { actionClass } from "./control-faces.js";
import { linkPreview } from "./place-preview.js";

/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Words
 * @typedef {Words | {popover: Words}} Preview
 * @typedef {() => Preview | null | undefined} Read
 * @typedef {Element | Range} Target
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {{target: Target, holder: Element, route: Route, stop: () => void, described: readonly Element[] | null}} Shown
 * @typedef {{pointerId: number, parent: Element | null, target: Element | null, read: Read | null, shown: boolean, timer: ReturnType<typeof setTimeout>}} Hold */

const DWELL = 200;
const WARM = 400;
// The space between a preview and what it previews.
const GAP = 6;

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");

/** A control's word and the presses that reach it, each its steps as key chips: the
 * preview every control shows, and one a control whose key another owner answers
 * declares itself, as a box's Send does for the key that sends from the box.
 * @param {Element} control @param {readonly (readonly string[])[]} presses @returns {Preview} */
export function pressPreview(control, presses) {
  const word = control.getAttribute("aria-label") ?? control.textContent?.trim() ?? "";
  const about = control.hasAttribute("data-lf-gen")
    ? control.getAttribute("aria-description")
    : null;
  return html`<span class="lf-preview-line"
      ><span class="lf-preview-word">${word}</span>${presses.map(
        (steps) =>
          html`<span class="lf-preview-keys"
            >${steps.map((step) => html`<kbd class="lf-key-badge">${step}</kbd>`)}</span
          >`,
      )}</span
    >${about ? html`<span class="lf-preview-more">${about}</span>` : nothing}`;
}
// What a control previews, read off the control as it shows: its word where its face
// shows a symbol (a generated control's accessible name), and its keys.
/** @param {Element} control @returns {Preview | null} */
function controlPreview(control) {
  const named =
    control.hasAttribute("data-lf-gen") && control.hasAttribute("aria-label");
  const keys = advertisesKeys() ? controlKeys(control) : [];
  return named || keys.length ? pressPreview(control, keys) : null;
}

const CONTROL = 'button, summary, a[href], [role="button"], [data-lf-offer]';
// A proxy stands in for what the pointer takes by itself (control-faces.js, `proxy`),
// so what it stands for previews: a gloss's proxy, its phrase.
const PROXY = `.${actionClass("proxy")}`;
// What pointing at `node` reads, or null where it says nothing of its own.
/** @param {Element} node @returns {Read | null} */
function readerOf(node) {
  if (node.getAttribute("aria-expanded") === "true" || node.matches(PROXY)) return null;
  const declared = node.lfPreview;
  if (typeof declared === "function") return () => declared.call(node);
  // A link into the page previews the place it opens (place-preview.js).
  if (node.matches(CONTROL) && !typesText(node))
    return () => linkPreview(node) ?? controlPreview(node);
  return null;
}
// The innermost node along `path` that previews something now.
/** @param {Iterable<EventTarget>} path @returns {{target: Element, read: Read} | null} */
function previewing(path) {
  for (const node of path) {
    if (!isElement(node)) continue;
    if (node === tip) return null;
    const read = readerOf(node);
    if (read && read()) return { target: node, read };
  }
  return null;
}
/** @param {Element} node */
function* climb(node) {
  for (let at = /** @type {Element | null} */ (node); at; at = renderedParent(at))
    yield at;
}

/** @type {Shown | null} */
let shown = null;
// When the last preview went, for the warm switch.
let cooled = -Infinity;
// The target under a hovering pointer, and the dwell before its preview.
/** @type {Target | null} */
let pointing = null;
/** @type {ReturnType<typeof setTimeout> | undefined} */
let dwell;
// The target whose preview a press, a key or Escape put away, quiet until the user
// points at something else or focus arrives anew.
/** @type {Target | null} */
let quiet = null;
/** @type {Hold | null} */
let hold = null;
// Where the pointer last stood, which tells a target the user moved onto from one
// that arrived under a still pointer.
let rest = { x: NaN, y: NaN };

/** @param {Preview} preview */
const popoverFace = (preview) =>
  typeof preview === "object" && preview !== null && "popover" in preview;

/** @param {Target} target @param {Read} read @param {Route} route @param {{x: number, y: number}} [at] */
function show(target, read, route, at) {
  if (shown?.target === target && shown.route === route) return;
  hide();
  const holder =
    target instanceof Range
      ? isElement(target.startContainer)
        ? target.startContainer
        : target.startContainer.parentElement
      : target;
  const preview = holder?.isConnected ? read() : null;
  if (!holder || !preview) return;
  const popover = popoverFace(preview);
  keeps(tip, "class", popover ? "lf-ui lf-preview lf-popover" : "lf-ui lf-preview");
  render(popover ? /** @type {{popover: Words}} */ (preview).popover : preview, tip);
  /** @type {Shown} */
  const record = { target, holder, route, stop: () => {}, described: null };
  // A target that leaves the page, as a re-render replaces it, takes its preview along.
  record.stop = watchOwner(holder, { disconnect: () => shown === record && hide() });
  shown = record;
  const anchor = anchorElement(holder);
  keeps(tip, "data-lf-route", route);
  keeps(tip, "data-lf-at", target instanceof Range ? "range" : null);
  if (target instanceof Range) tip.style.removeProperty("position-anchor");
  else {
    for (const inset of ["position", "left", "top", "position-visibility"])
      tip.style.removeProperty(inset);
    tip.style.setProperty("position-anchor", anchorName(anchor));
  }
  if (route === "hold") keeps(holder, "data-lf-held", "");
  showNativeLayer(tip);
  if (target instanceof Range) standByRange(target, anchor, at);
  if (route === "focus" && holder.lfPreview && focused() === holder) {
    const described = holder.ariaDescribedByElements ?? [];
    record.described = described;
    holder.ariaDescribedByElements = [...described, tip];
  }
}

// A range's preview stands below the line the pointer is on, or above it where the
// window has no room below, inside the window's width.
/** @param {Range} range @param {Element} anchor @param {{x: number, y: number}} [at] */
function standByRange(range, anchor, at) {
  const lines = [...range.getClientRects()];
  const line =
    lines.find(
      (rect) =>
        at &&
        at.x >= rect.left &&
        at.x <= rect.right &&
        at.y >= rect.top &&
        at.y <= rect.bottom,
    ) ?? lines[0];
  if (!line) return;
  const { width, height } = tip.getBoundingClientRect();
  const room = document.documentElement.clientWidth;
  const left = Math.max(GAP, Math.min(line.left, room - width - GAP));
  const top =
    line.bottom + GAP + height > innerHeight
      ? line.top - GAP - height
      : line.bottom + GAP;
  anchorAt(tip, anchor, { left, top }, undefined, "anchors-visible");
}

function hide() {
  if (!shown) return;
  const record = shown;
  shown = null;
  record.stop();
  if (record.described) record.holder.ariaDescribedByElements = record.described;
  if (record.route === "hold") record.holder.removeAttribute("data-lf-held");
  // Its words stay in the closed popover, so the next preview that says the same
  // writes nothing.
  closeNativeLayer(tip);
  cooled = performance.now();
}

// The pointer's target changed: start its dwell, or show it at once while warm.
/** @param {Target | null} target @param {Read | null} [read] @param {{x: number, y: number}} [at] */
function point(target, read = null, at) {
  if (target === pointing) return;
  pointing = target;
  clearTimeout(dwell);
  if (shown && shown.route !== "focus" && shown.target !== target) hide();
  if (target !== quiet) quiet = null;
  if (!target || !read || target === quiet) return;
  if (performance.now() - cooled < WARM) show(target, read, "pointer", at);
  else
    dwell = setTimeout(() => {
      if (pointing === target) show(target, read, "pointer", at);
    }, DWELL);
}

// Put the standing preview away for its target, until the user comes to another.
function quieten() {
  clearTimeout(dwell);
  if (!shown) return;
  quiet = shown.target;
  hide();
}

/** A range's owner says the pointer rests on one of its ranges, or on none of them: what
 * pointing at it reads, and where the pointer is, which picks the line it stands by.
 * @param {Range | null} range @param {Read} [read] @param {{x: number, y: number}} [at] */
export function pointRange(range, read, at) {
  if (range) point(range, read, at);
  else if (pointing instanceof Range) point(null);
}

/** @param {HTMLElement} home */
export function mountPreviews(home) {
  home.append(tip);
  // The platform hides a hint as another popover opens over it, or as a press lands
  // elsewhere, and the record goes with it.
  tip.addEventListener("toggle", (event) => {
    if (/** @type {ToggleEvent} */ (event).newState === "closed" && shown) hide();
  });
  document.addEventListener(
    "pointerover",
    (event) => {
      if (event.pointerType === "touch") return;
      // Something that arrives under a pointer the user hasn't moved takes it, but
      // shows nothing: the user pointed at what was there before. A pointer carrying a
      // press, as a drag does, is acting, not reading.
      const still = event.clientX === rest.x && event.clientY === rest.y;
      rest = { x: event.clientX, y: event.clientY };
      const found = previewing(event.composedPath());
      if (still || event.buttons) {
        pointing = found?.target ?? null;
        clearTimeout(dwell);
        if (shown?.route === "pointer" && shown.target !== pointing) hide();
      } else if (found) point(found.target, found.read);
      else if (!(pointing instanceof Range)) point(null);
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      rest = { x: event.clientX, y: event.clientY };
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerout",
    (event) => {
      if (event.pointerType !== "touch" && event.relatedTarget === null) point(null);
    },
    { capture: true, passive: true },
  );
  // Focus arriving is a new reading, whatever put the target's last one away, and
  // focus leaving takes its preview along. It shows once the task that moved focus has
  // done, which may be opening a popover the platform lets no other open inside.
  onCurrentLocation((node) => {
    quiet = null;
    if (shown?.route === "focus" && shown.target !== node) hide();
    if (!node) return;
    queueMicrotask(() => {
      if (focused() !== node || !node.matches(":focus-visible")) return;
      const found = previewing(climb(node));
      if (found && shown?.target !== found.target)
        show(found.target, found.read, "focus");
    });
  });
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape" || shown?.route === "pointer") quieten();
    },
    { capture: true },
  );
  document.addEventListener(
    "pointerdown",
    (event) => {
      endHold();
      if (event.pointerType !== "touch") return quieten();
      if (!event.isPrimary || !plainPress(event)) return;
      const found = previewing(event.composedPath());
      if (!found || found.target.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (isElement(origin) && origin.hasPointerCapture(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      const held = {
        pointerId: event.pointerId,
        parent: found.target.parentElement,
        target: /** @type {Element | null} */ (found.target),
        read: /** @type {Read | null} */ (found.read),
        shown: false,
        timer: setTimeout(() => {
          if (hold !== held) return;
          held.shown = true;
          if (held.target && held.read) show(held.target, held.read, "hold");
        }, DWELL),
      };
      hold = held;
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      const found = previewing(event.composedPath());
      const neighbour = found?.target.parentElement === hold.parent ? found : null;
      if ((neighbour?.target ?? null) === hold.target) return;
      hold.target = neighbour?.target ?? null;
      hold.read = neighbour?.read ?? null;
      if (!hold.shown) return;
      if (neighbour) show(neighbour.target, neighbour.read, "hold");
      else hide();
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerup",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      const { shown: read, target } = hold;
      endHold();
      if (!read || !target || !plainPress(event)) return;
      claimReleaseClick();
      if (target instanceof HTMLElement || target instanceof SVGElement)
        nativeFocusTarget(target).focus({ preventScroll: true, focusVisible: false });
      target.dispatchEvent(
        new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          composed: true,
          detail: 1,
          clientX: event.clientX,
          clientY: event.clientY,
        }),
      );
    },
    { capture: true },
  );
  document.addEventListener(
    "pointercancel",
    (event) => {
      if (hold?.pointerId === event.pointerId) endHold();
    },
    { capture: true },
  );
  // A tab the user leaves ends what they were reading in it.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") (point(null), quieten(), endHold());
  });
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold?.shown) event.preventDefault();
    },
    { capture: true },
  );
}

function endHold() {
  if (!hold) return;
  clearTimeout(hold.timer);
  const wasShown = hold.shown;
  hold = null;
  if (wasShown && shown?.route === "hold") hide();
}
