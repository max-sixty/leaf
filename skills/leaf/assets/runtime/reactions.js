/* The response bar's reaction row and the standing tokens a strip or circle wears.

   An open anchored composer owns its general response disclosure: reactions only
   contribute declared actions to it, and `r` opens that local group focused on its
   first reaction. With no composer open, `r` contributes the reaction margin elements to the
   selected item's existing margin cluster. While that explicit mode stands, its
   contribution owns all six margin elements; standing readings and unrelated actions remain
   in Page map and return when the mode closes. Those temporary margin elements dock with the
   cluster when necessary and claim no permanent rail width. A thread-local `r` opens
   the conversation-owned row on the latest agent message. `REACT` claims the keyboard
   only for those margin and message lists; the composer's response scope owns its
   local list. Arrow keys wrap through the visible margin elements in the active list.
   Tab and Shift-Tab follow that same order. The Page-map dialog remains part of the
   response's target context but owns its native keyboard walk and Escape while open.
   Closing it restores its exact opener; selecting overflow presses the original margin element
   before its temporary target is released. Enter or Space presses the focused choice,
   digits remain optional reaction accelerators in declaration order, and a stray key
   closes the list before keeping its ordinary meaning.

   The margin form shows the declared reaction margin elements together within the six-item
   budget. Comment retains its separate `c` route. The digit register and visible
   choices therefore name the same complete set. The choices do not widen the rail or
   open a separate palette below the target. The compact response bar's More controller
   owns its state, focus return, and geometry independently.
   Conversation reactions remain in their conversation-owned strip. The event still
   carries its durable authored anchor, while
   the temporary item resolves selected text to the first rendered block, matching the
   target where replay later seats its standing reaction. */
import {
  marginElementChoices,
  marginElementContextContains,
  foldMarginElementOptions,
  marginElement,
  openMarginElementOptions,
  registerMarginContribution,
  unfoldedMarginElements,
} from "./living-margin.js";
import { runtime } from "./context.js";
import { CONTROL_WORD_CAP, designOn } from "./design.js";
import { registry } from "./registry.js";
import {
  fabBar,
  fabOptions,
  hideComposer,
  syncResponseOptions,
} from "./composing/selection.js";
import { el, offer, responseAction } from "./widget-elements.js";
import {
  fabAnchorAt,
  fabReturnTo,
  fabTargetAt,
  hasPageSelectionTarget,
  showFab,
} from "./composing/surface.js";
import { cut, elementById } from "./passages.js";
import { itemWord, visualActionAnchor, visualPartLabel } from "./anchors.js";
import { undoable, withdraw } from "./projection.js";
import { post } from "./outbox.js";
import { announce, notice } from "./notifications.js";
import { claimsEsc, focused, paintHere, saying } from "./keyboard/scopes.js";
import { standingConversation } from "./conversation/landing.js";
import { allButTheReference, standingItem } from "./keyboard/page.js";
import { PRESS } from "./keyboard/bindings.js";
import { anchorLabel } from "./conversation/messages.js";
import { iconElement } from "./icons.js";

// Standing tokens wear their emoji wherever they stand, and `aria-pressed` is the whole
// of what a palette chip adds — the fill it reads carries the same fact for the eye.
// Both carry the event a second press takes back. The reaction rides the chip rather
// than a map beside it, so a reconcile that keeps the node keeps the fact with it.
export function paintReactionStanding(strip, standing) {
  const by = new Map(standing.map((x) => [x.token, x]));
  for (const chip of strip.querySelectorAll(".lf-react-palette > .lf-react")) {
    const on = by.get(chip.dataset.token) ?? null;
    chip.setAttribute("aria-pressed", on ? "true" : "false");
    chip.lfReaction = on;
  }
}

const reactionVocabulary = () => registry.$reactions?.tokens;
// The layer's reaction vocabulary, in declared order. The bar, a reply's strip, the
// page row and the keyboard accelerators all read this one list, so a layer that
// renames, adds or removes a token moves every surface at once, and core never learns
// a token's name. Empty until the registry has arrived: the register checks every core
// row's bindings as the module evaluates, before the vocabulary is known.
export const reactionTokens = () => Object.entries(reactionVocabulary() ?? {});

// One token as a press, built the same way wherever it stands. The token names the
// control; a layer may add an explanation without making prose part of the platform's
// vocabulary. The compact face stays the declared mark. Digits remain keyboard
// accelerators without changing the shape of every chip.
function reactionChip(
  name,
  entry,
  pressed,
  { margin = false, response = false, ordinal = 0 } = {},
) {
  const chip = offer("button", `${margin || response ? "" : "lf-chip "}lf-react`);
  const meaning = entry.means ? `${name} — ${entry.means}` : name;
  chip.dataset.token = name;
  if (margin) {
    chip.setAttribute("aria-label", meaning);
    marginElement(chip, {
      key: `reaction:${String(ordinal).padStart(4, "0")}:${name}`,
      glyph: entry.glyph,
      label: meaning,
      role: "secondary",
    });
  } else {
    chip.title = meaning;
    chip.setAttribute("aria-label", meaning);
    if (response)
      responseAction(chip, { glyph: entry.glyph, label: name, collapse: true });
    else chip.append(el("span", "lf-react-glyph", entry.glyph));
  }
  chip.onclick = () => pressed(name, chip);
  return chip;
}

const surfaces = new WeakMap();
let surfaceOrdinal = 0;
let marginSurface = null;
let marginOffer = null;
let marginTarget = null;
export function buildReactSurface(
  surface,
  pressed,
  { label, target, marginActions = false, triggerLabel = null },
) {
  if (!reactionTokens().length) return surface;
  surface.classList.add("lf-react-surface");
  const trigger = offer("button", "lf-react-trigger");
  trigger.append(iconElement("reaction", "lf-react-trigger-icon"));
  trigger.setAttribute("aria-expanded", "false");
  const showLabel = triggerLabel ?? "Add reaction";
  trigger.setAttribute("aria-label", showLabel);
  trigger.title = showLabel;
  const palette = el("span", "lf-react-palette");
  palette.id = `lf-reactions-${++surfaceOrdinal}`;
  palette.setAttribute("role", "group");
  palette.setAttribute("aria-label", label);
  trigger.setAttribute("aria-controls", palette.id);
  for (const [ordinal, [name, entry]] of reactionTokens().entries())
    palette.append(
      reactionChip(name, entry, pressed, {
        margin: marginActions,
        ordinal,
      }),
    );
  surface.append(trigger, palette);
  surfaces.set(surface, { palette, target, trigger });
  trigger.onclick = () =>
    setReact(!(reactArmed && reactSurface === surface), { surface });
  return surface;
}

export function buildReactBar() {
  const palette = el("span", "lf-react-palette");
  palette.setAttribute("role", "group");
  palette.setAttribute("aria-label", "Reactions for this selection or item");
  for (const [ordinal, [name, entry]] of reactionTokens().entries())
    palette.append(reactionChip(name, entry, reactHere, { response: true, ordinal }));
  fabOptions.append(palette);
  syncResponseOptions();
  marginSurface = el("div", "lf-margin-reactions");
  marginSurface.setAttribute("role", "group");
  marginSurface.setAttribute("aria-label", "Other responses");
  buildReactSurface(marginSurface, reactHere, {
    label: "Reactions for this selection or item",
    target: () => anchorWord(fabAnchorAt()),
    marginActions: true,
  });
}

const anchorWord = (anchor) => {
  if (!anchor) return "the target";
  if (anchor.quote) return "the selection";
  const item = elementById(anchor.section);
  if (anchor.visual) return visualPartLabel(item, anchor.visual) ?? anchor.visual;
  return itemWord(item) || "the item";
};

async function reactHere(name, chip) {
  const anchor = fabAnchorAt();
  const returnTo = fabReturnTo();
  const restoreTargetFocus = () => {
    const destination = returnTo?.isConnected ? returnTo : visualActionAnchor(anchor);
    destination?.focus({ preventScroll: true });
  };
  if (!anchor) return;
  if (chip.lfReaction) {
    await withdraw(chip.lfReaction);
    hideComposer();
    showFab(null);
    setReact(false);
    restoreTargetFocus();
    return;
  }
  const event = {
    kind: "comment",
    revision: runtime.currentRevision,
    token: name,
    anchor: structuredClone(anchor),
  };
  if (designOn) event.about = "layer";
  const sent = await sendReaction(event, chip, anchorWord(anchor));
  if (!sent) return;
  hideComposer();
  showFab(null);
  setReact(false);
  restoreTargetFocus();
  getSelection()?.removeAllRanges();
}

export async function sendReaction(event, chip, where) {
  chip.setAttribute("aria-busy", "true");
  try {
    const sent = await post(event);
    if (sent) announce(`${event.token} on ${where}`);
    return sent;
  } finally {
    chip.removeAttribute("aria-busy");
  }
}

// The react press opens one surface's list. `r` uses the latest agent reply in the
// thread the reader is standing in, an already raised bar, a completed native
// selection, or the item holding focus. This same reading decides whether the page
// command exists, so dispatch cannot advertise a reaction before its target.
let reactArmed = false;
let reactRaised = false;
// Whether this raise is what unfolded the target's cluster, and so whether putting the
// choices away has a fold of its own to put back. A reader who pressed `…` themselves
// and then `r` opened that layer before the raise found it, and it is theirs to keep.
let marginUnfolded = false;
let reactFrom = null;
let reactSurface = null;
const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
const pickerFor = (surface) => surfaces.get(surface);

function reactionTarget() {
  const said = standingConversation();
  const strip = said && latestAgentStrip(said.held);
  if (strip) return { kind: "surface", surface: strip };
  if (fabAnchorAt()) return { kind: "anchor" };
  if (hasPageSelectionTarget()) return { kind: "selection" };
  const item = standingItem();
  return item ? { kind: "item", item } : null;
}
export const hasReactionTarget = () => Boolean(reactionTarget());

function raiseMarginSurface() {
  const anchor = fabAnchorAt();
  const target = anchor && fabTargetAt();
  if (!marginSurface || !target) return false;
  // `r` is an explicit reaction mode. Comment remains on `c`, so this temporary
  // contribution contains reactions alone.
  fabBar.dataset.lfMarginRaised = "1";
  const standing = unfoldedMarginElements()?.lfTarget === target;
  // Register the response surface in the state it is about to show. Registering its
  // collapsed face first makes the projection treat the six choices as hidden owner
  // content; a fast `r` can then arm their digit shortcuts while only the old floating
  // ellipsis remains on screen.
  marginSurface.classList.add("lf-react-open");
  paintReactionStanding(
    marginSurface,
    [...fabBar.querySelectorAll(".lf-react[aria-pressed='true']")]
      .map((chip) => chip.lfReaction)
      .filter(Boolean),
  );
  marginOffer = registerMarginContribution({
    key: "responses",
    target,
    controls: marginSurface,
    side: "after",
    // The choices borrow whatever RHS is available and dock as one item when it is
    // not. Reserving their temporary width would move the page the first time `r`
    // opened and leave that larger rail behind after the choices closed.
    claim: false,
  });
  marginTarget = target;
  if (openMarginElementOptions(target, { owner: "responses" })) {
    marginUnfolded = !standing;
    return true;
  }
  marginSurface.classList.remove("lf-react-open");
  marginOffer.unregister();
  marginOffer = null;
  marginTarget = null;
  return false;
}

function lowerMarginSurface() {
  marginOffer?.unregister();
  marginOffer = null;
  marginTarget = null;
  delete fabBar.dataset.lfMarginRaised;
  // A raise that unfolded the target's margin elements to stand these choices in puts that fold
  // back, so cancelling leaves the cluster as the press found it rather than an empty
  // fold the reader has to close themselves. Only that raise: this runs on every
  // disarm, including one whose surface was a reply strip and which never raised the
  // margin at all, and including one over a fold the reader had already opened for
  // themselves — folding either takes away a layer the gesture never put on.
  if (marginUnfolded) foldMarginElementOptions();
  marginUnfolded = false;
}

function closeSurface(surface) {
  surface?.classList.remove("lf-react-open");
  pickerFor(surface)?.trigger.setAttribute("aria-expanded", "false");
}

// A page picker lives in the target's shared margin element options and therefore owns its
// geometry. Returning true keeps the floating Comment bar from trying to re-place the
// same gesture while the margin has it; message-local reaction strips need no claim.
export function syncReactLayout() {
  return reactArmed && reactSurface === marginSurface;
}

export function setReact(on, { surface = null } = {}) {
  if (!on && !reactArmed) {
    const residue =
      marginOffer ||
      fabBar.hasAttribute("data-lf-margin-raised") ||
      marginSurface?.classList.contains("lf-react-open");
    if (!residue) return;
    // Off is also the invariant repair path. A projection can retire the target and
    // its option group before the response scope observes the close; remove any
    // contributed surface that outlived that ordering.
    closeSurface(reactSurface);
    closeSurface(marginSurface);
    lowerMarginSurface();
    paintHere();
    return;
  }
  if (on === reactArmed && (surface === reactSurface || !surface)) return;
  if (on && claimsEsc(focused())) return;
  // Closing hides the palette synchronously. Capture its focused control first: once
  // CSS makes it invisible, the browser reports body and loses the fact needed to
  // return to the compact response that opened it.
  const closingActive = on ? null : focused();
  closeSurface(reactSurface);
  if (on) {
    reactFrom = focused();
    if (surface) reactSurface = surface;
    else {
      const target = reactionTarget();
      if (target?.kind === "surface") reactSurface = target.surface;
      else if (target?.kind === "anchor" || target?.kind === "item") {
        if (target.kind === "item") {
          // The item may be represented by a docked row after its containing block,
          // with the target itself off screen. Keep the semantic anchor without
          // asking a floating bar to find geometry; the shared item is the surface.
          showFab({ section: target.item.id }, null, {
            origin: reactFrom,
            place: false,
          });
          reactRaised = true;
        }
        if (!raiseMarginSurface()) {
          if (reactRaised) showFab(null);
          reactRaised = false;
          reactSurface = null;
          reactFrom = null;
          notice("That reaction target is no longer available");
          return;
        }
        reactSurface = marginSurface;
      } else {
        reactSurface = null;
        reactFrom = null;
        return;
      }
    }
    if (!pickerFor(reactSurface)) {
      reactSurface = null;
      reactFrom = null;
      return;
    }
    reactArmed = true;
    reactSurface.classList.add("lf-react-open");
    pickerFor(reactSurface).trigger.setAttribute("aria-expanded", "true");
    const firstChoice = pickerFor(reactSurface).palette.querySelector(".lf-react");
    if (surface && reactFrom === pickerFor(reactSurface).trigger)
      firstChoice?.focus({
        preventScroll: true,
      });
    announce(`React — ${saying(REACT.rows)}`);
  } else {
    const from = reactFrom;
    const trigger = pickerFor(reactSurface)?.trigger;
    const active = closingActive;
    reactArmed = false;
    reactSurface = null;
    reactFrom = null;
    if (reactRaised) showFab(null);
    reactRaised = false;
    lowerMarginSurface();
    if (fabAnchorAt()) showFab(fabAnchorAt());
    if (
      fabBar.contains(from) ||
      active === document.body ||
      active?.closest?.(".lf-react-palette")
    ) {
      const input = fabBar.querySelector(".lf-fab-input");
      const destination = input?.checkVisibility?.()
        ? input
        : from?.isConnected && from.checkVisibility?.()
          ? from
          : trigger?.checkVisibility?.()
            ? trigger
            : document.body;
      // Hiding a focused choice may leave focus on that now-hidden node or drop it to
      // body before the browser paints. The reader may choose another control during
      // that frame; only those two states mean the palette still owes its return.
      if (destination !== document.body)
        requestAnimationFrame(() => {
          if (
            destination.isConnected &&
            destination.checkVisibility?.() &&
            (focused() === active || focused() === document.body)
          )
            destination.focus({ preventScroll: true });
        });
    }
  }
  paintHere();
}

document.addEventListener("lf-margin-element-options-closed", () => {
  if (reactArmed && reactSurface === marginSurface) setReact(false);
});
document.addEventListener("lf-actions", () => {
  if (
    reactArmed &&
    reactSurface === marginSurface &&
    (!marginTarget?.isConnected || fabTargetAt() !== marginTarget)
  )
    setReact(false);
});
// A card the panel's narrowing hid keeps its node (thread-list.js), so a list open on
// one of its messages is still connected and still armed; the card going out of sight
// is the removal it always was to the reader.
document.addEventListener("lf-thread-hidden", (event) => {
  if (reactArmed && event.detail.node.contains(reactSurface)) setReact(false);
});

function responseChoices(surface) {
  if (!surface) return [];
  if (surface === marginSurface) return marginElementChoices(fabTargetAt());
  return [...surface.querySelectorAll(".lf-react-palette > .lf-react")].filter(
    (choice) => choice.checkVisibility(),
  );
}

function stepResponse(binding) {
  const choices = responseChoices(reactSurface);
  if (!choices.length) return;
  const at = choices.indexOf(focused());
  const backward =
    binding === "ArrowLeft" || binding === "ArrowUp" || binding === "Shift+Tab";
  const next =
    at < 0
      ? backward
        ? choices.length - 1
        : 0
      : (at + (backward ? -1 : 1) + choices.length) % choices.length;
  choices[next].focus({ preventScroll: true });
}

const reactTargetWord = () =>
  typeof pickerFor(reactSurface)?.target === "function"
    ? pickerFor(reactSurface).target()
    : (pickerFor(reactSurface)?.target ?? "the target");

export const REACT = {
  title: "With reactions open",
  escape: "inner",
  // Opening the modal reference dismisses this transient mode. Its section still reads
  // the liveness captured at that boundary rather than listing every conditional choice.
  liveInReference: true,
  at: () => reactArmed,
  claims: allButTheReference,
  rows: [
    {
      id: "reaction.choose",
      runFromReference: false,
      keys: () =>
        reactionTokens()
          .slice(0, 9)
          .map((_, i) => String(i + 1)),
      label: () => {
        const n = Math.min(reactionTokens().length, 9);
        return n > 1 ? `1–${n}` : "1";
      },
      does: () =>
        `Put a reaction on ${reactTargetWord()}: ${reactionTokens()
          .slice(0, 9)
          .map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`)
          .join(", ")}`,
      line: "react",
      run: (binding) => {
        pickerFor(reactSurface)
          ?.palette.querySelectorAll(".lf-react")
          [+binding - 1]?.click();
      },
    },
    {
      id: "reaction.move",
      runFromReference: false,
      keys: ["Tab", "Shift+Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
      does: "Move through reactions",
      line: "move",
      repeat: true,
      run: stepResponse,
    },
    {
      id: "response.activate",
      runFromReference: false,
      keys: PRESS,
      does: "Use the focused response",
      line: "choose",
      when: () => responseChoices(reactSurface).includes(focused()),
      run: () => focused()?.click(),
    },
    {
      id: "reaction.cancel",
      keys: ["Escape"],
      does: "Close response choices",
      line: "cancel",
      run: () => setReact(false),
    },
  ],
};

function reactionPlace(event) {
  if (event.kind === "reply") return "the reply";
  if (!event.anchor) return "the page";
  const label = anchorLabel(event.anchor, event.about);
  return [...label].length > CONTROL_WORD_CAP
    ? cut(label, 0, CONTROL_WORD_CAP) + "…"
    : label;
}
export const undoSentence = () => {
  const event = undoable();
  return event?.token
    ? `Take back: ${event.token} on ${reactionPlace(event)}`
    : "Take back the last change you made here";
};

export const isReactArmed = () => reactArmed;
export const reactionContextContains = (node) =>
  reactArmed &&
  reactSurface === marginSurface &&
  marginElementContextContains(fabTargetAt(), node);
