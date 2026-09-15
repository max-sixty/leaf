/* The response bar's reaction row and the standing tokens a strip or circle wears.

   An open anchored composer owns its general response disclosure: reactions only
   contribute declared actions to it, and `e` opens that local group focused on its
   first reaction. With no composer open, `e` contributes the reaction margin entries to the
   selected element's existing margin cluster. While that explicit mode stands, its
   contribution owns all six margin entries; standing readings and unrelated actions remain
   in Page Map and return when the mode closes. Those temporary margin entries dock with the
   cluster when necessary and claim no permanent rail width. A thread-local `e` opens
   the conversation-owned row on the latest agent message. `REACT` claims the keyboard
   only for those margin and message lists; the composer's response scope owns its
   local list. Arrow keys wrap through the visible margin entries in the active list.
   Tab and Shift-Tab follow that same order. The Page Map dialog remains part of the
   response's target context but owns its native keyboard walk and Escape while open.
   Closing it restores its exact opener; selecting overflow invokes the declared margin entry
   before its temporary target is released. Enter or Space presses the focused choice,
   digits remain optional reaction accelerators in declaration order, and a stray key
   closes the list before keeping its ordinary meaning.

   The margin form shows the declared reaction margin entries together within the six-item
   budget. Comment retains its separate `c` route. The digit register and visible
   choices therefore name the same complete set. The choices do not widen the rail or
   open a separate palette below the target. The compact response bar's More controller
   owns its state, focus return, and geometry independently.
   Conversation reactions remain in their conversation-owned strip. The event still
   carries its durable authored anchor, while
   the temporary addressable resolves selected text to the first rendered block, matching the
   target where replay later seats its standing reaction.

   Token rendering and per-press submission helpers are passive exports. Boot
   constructs the reaction controller with auxiliary-surface, composer, and travel
   capabilities; conversation views register their template-owned trigger and palette.
   mount installs the mode teardown listeners after composition. */

import { registerMarginContribution } from "./margin-entries.js";
import { runtime } from "./context.js";
import { CONTROL_WORD_CAP } from "./design-readings.js";
import { registry } from "./registry.js";
import { fabBar, fabOptions } from "./composing/selection.js";
import { el, offer, responseAction } from "./widget-elements.js";

import { cut, elementById } from "./passages.js";
import { addressableWord, visualPartLabel } from "./anchor-resolution.js";
import { announce, notice } from "./notifications.js";
import { claimsEsc, focused, saying } from "./keyboard/scopes.js";
import { repaint } from "./repaint.js";

import { allButCommandReference } from "./keyboard/register.js";
import { PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { anchorLabel } from "./conversation/messages.js";
import { reactionsAt } from "./conversation/model.js";
import { allThreads } from "./conversation/state.js";
import { watchProjection } from "./projection-watch.js";

// Standing tokens wear their emoji wherever they stand, and `aria-pressed` is the whole
// of what a palette chip adds — the fill it reads carries the same fact for the eye.
// Both carry the event a second press takes back. The reaction rides the chip rather
// than a map beside it, so a reconcile that keeps the node keeps the fact with it.
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
function reactionChip(name, entry, pressed, { response = false } = {}) {
  const chip = offer("button", `${response ? "" : "lf-chip "}lf-react`);
  const meaning = entry.means ? `${name} — ${entry.means}` : name;
  chip.dataset.token = name;
  chip.title = meaning;
  chip.setAttribute("aria-label", meaning);
  if (response)
    responseAction(chip, { glyph: entry.glyph, label: name, collapse: true });
  else chip.append(el("span", "lf-react-glyph", entry.glyph));
  chip.onclick = () => pressed(name, chip);
  return chip;
}

export function createReactionController({
  marginEntryChoices,
  marginEntryContextContains,
  foldMarginEntryOptions,
  openMarginEntryOptions,
  unfoldedMarginEntries,
  designModeActive,
  hideComposer,
  syncResponseOptions,
  fabAnchorAt,
  fabReturnTo,
  fabTargetAt,
  hasPageSelectionTarget,
  showFab,
  visualActionAnchor,
  standingConversation,
  standingElement,
}) {
  const surfaces = new WeakMap();
  const marginSurface = Symbol("margin reactions");
  let marginOffer = null;
  let marginTarget = null;
  let marginAnchor = null;
  let pageCommands = null;
  const marginReactionKey = (name, ordinal) =>
    `reaction:${String(ordinal).padStart(4, "0")}:${name}`;
  function registerReactSurface(surface, { palette, target, trigger }) {
    surfaces.set(surface, { palette, target, trigger });
    return {
      toggle: () => setReact(!(reactArmed && reactSurface === surface), { surface }),
      close: () => {
        if (reactSurface === surface) setReact(false);
      },
    };
  }

  function buildReactBar(commands) {
    pageCommands = commands;
    const palette = el("span", "lf-react-palette");
    palette.setAttribute("role", "group");
    palette.setAttribute("aria-label", "Reactions for this selection or element");
    for (const [name, entry] of reactionTokens())
      palette.append(
        reactionChip(name, entry, (token, chip) => reactHere(token, chip, commands), {
          response: true,
        }),
      );
    fabOptions.append(palette);
    syncResponseOptions();
  }

  const anchorWord = (anchor) => {
    if (!anchor) return "the target";
    if (anchor.quote) return "the selection";
    const addressable = elementById(anchor.section);
    if (anchor.visual)
      return visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return addressableWord(addressable) || "the element";
  };

  async function reactHere(
    name,
    chip,
    commands,
    standing = chip?.lfReaction,
    anchor = fabAnchorAt(),
  ) {
    const returnTo = fabReturnTo();
    const restoreTargetFocus = () => {
      const destination = returnTo?.isConnected ? returnTo : visualActionAnchor(anchor);
      destination?.focus({ preventScroll: true });
    };
    if (!anchor) return;
    if (standing) {
      await commands.withdrawReaction(standing);
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
    if (designModeActive()) event.about = "design";
    const sent = sendReaction(event, chip, anchorWord(anchor), commands.postReaction);
    hideComposer();
    showFab(null);
    setReact(false);
    restoreTargetFocus();
    getSelection()?.removeAllRanges();
    await sent;
  }

  // The react press opens one surface's list. `e` uses the latest agent reply in the
  // thread the reader is standing in, an already raised bar, a completed native
  // selection, or the addressable element holding focus. This same reading decides whether the page
  // command exists, so dispatch cannot advertise a reaction before its target.
  let reactArmed = false;
  let reactRaised = false;
  // Whether this raise is what unfolded the target's cluster, and so whether putting the
  // choices away has a fold of its own to put back. A reader who pressed `…` themselves
  // and then `e` opened that layer before the raise found it, and it is theirs to keep.
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
    const addressable = standingElement();
    return addressable ? { kind: "addressable", addressable } : null;
  }
  const hasReactionTarget = () => Boolean(reactionTarget());

  function raiseMarginSurface() {
    const anchor = fabAnchorAt();
    const target = anchor && fabTargetAt();
    if (!pageCommands || !target) return false;
    // `e` is an explicit reaction mode. Comment remains on `c`, so this temporary
    // contribution contains reactions alone.
    fabBar.dataset.lfMarginRaised = "1";
    const standing = unfoldedMarginEntries()?.lfTarget === target;
    marginAnchor = structuredClone(anchor);
    marginOffer = registerMarginContribution({
      key: "responses",
      target,
      read: () => {
        const standing = new Set(
          reactionsAt(allThreads(), marginAnchor).map((reaction) => reaction.token),
        );
        return {
          side: "after",
          // Temporary response choices use existing room; they never widen the page rail.
          claim: false,
          entries: reactionTokens().map(([name, entry], ordinal) => ({
            key: marginReactionKey(name, ordinal),
            activation: name,
            glyph: entry.glyph,
            label: entry.means ? `${name} — ${entry.means}` : name,
            rank: "secondary",
            className: "lf-react",
            pressed: standing.has(name),
          })),
          readings: [],
        };
      },
      activate: (name) =>
        reactHere(
          name,
          null,
          pageCommands,
          reactionsAt(allThreads(), marginAnchor).find(
            (reaction) => reaction.token === name,
          ),
          marginAnchor,
        ),
    });
    marginTarget = target;
    if (openMarginEntryOptions(target, { owner: "responses" })) {
      marginUnfolded = !standing;
      return true;
    }
    marginOffer.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    return false;
  }

  function lowerMarginSurface() {
    marginOffer?.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    delete fabBar.dataset.lfMarginRaised;
    // A raise that unfolded the target's margin entries to stand these choices in puts that fold
    // back, so cancelling leaves the cluster as the press found it rather than an empty
    // fold the reader has to close themselves. Only that raise: this runs on every
    // disarm, including one whose surface was a reply strip and which never raised the
    // margin at all, and including one over a fold the reader had already opened for
    // themselves — folding either takes away a layer the gesture never put on.
    if (marginUnfolded) foldMarginEntryOptions();
    marginUnfolded = false;
  }

  function closeSurface(surface) {
    if (surface === marginSurface) return;
    surface?.classList.remove("lf-react-open");
    pickerFor(surface)?.trigger.setAttribute("aria-expanded", "false");
  }

  // A page picker lives in the target's shared margin entry options and therefore owns its
  // geometry. Returning true keeps the floating Comment bar from trying to re-place the
  // same gesture while the margin has it; message-local reaction strips need no claim.
  function syncReactLayout() {
    return reactArmed && reactSurface === marginSurface;
  }

  function setReact(on, { surface = null } = {}) {
    if (!on && !reactArmed) {
      const residue = marginOffer || fabBar.hasAttribute("data-lf-margin-raised");
      if (!residue) return;
      // Off is also the invariant repair path. A projection can retire the target and
      // its option group before the response scope observes the close; remove any
      // contributed surface that outlived that ordering.
      closeSurface(reactSurface);
      lowerMarginSurface();
      repaint();
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
        else if (target?.kind === "anchor" || target?.kind === "addressable") {
          if (target.kind === "addressable") {
            // The addressable element may be represented by a docked row after its containing block,
            // with the target itself off screen. Keep the semantic anchor without
            // asking a floating bar to find geometry; the shared element is the surface.
            showFab({ section: target.addressable.id }, null, {
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
      if (reactSurface !== marginSurface && !pickerFor(reactSurface)) {
        reactSurface = null;
        reactFrom = null;
        return;
      }
      reactArmed = true;
      if (reactSurface !== marginSurface) {
        reactSurface.classList.add("lf-react-open");
        const picker = pickerFor(reactSurface);
        picker.trigger.setAttribute("aria-expanded", "true");
        if (surface && reactFrom === picker.trigger)
          picker.palette.querySelector(".lf-react")?.focus({ preventScroll: true });
      }
      announce(`React — ${saying(REACT.rows)}`);
    } else {
      const from = reactFrom;
      const trigger = pickerFor(reactSurface)?.trigger;
      const active = closingActive;
      const stoodInMargin = marginOffer?.contains(active);
      reactArmed = false;
      reactSurface = null;
      reactFrom = null;
      if (reactRaised) showFab(null);
      reactRaised = false;
      lowerMarginSurface();
      if (fabAnchorAt()) showFab(fabAnchorAt());
      if (
        fabBar.contains(from) ||
        stoodInMargin ||
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
    repaint();
  }

  // A card the panel's narrowing hid keeps its node (thread-list.js), so a list open on
  // one of its messages is still connected and still armed; the card going out of sight
  // is the removal it always was to the reader.

  function responseChoices(surface) {
    if (!surface) return [];
    if (surface === marginSurface) return marginEntryChoices(fabTargetAt());
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
    beginWalk("reaction", "Reaction", () =>
      listWalkPosition(responseChoices(reactSurface), focused()),
    );
  }

  const reactTargetWord = () =>
    reactSurface === marginSurface
      ? anchorWord(marginAnchor)
      : typeof pickerFor(reactSurface)?.target === "function"
        ? pickerFor(reactSurface).target()
        : (pickerFor(reactSurface)?.target ?? "the target");

  const REACT = {
    title: "With reactions open",
    escape: "inner",
    // Opening the modal reference dismisses this transient mode. Its section still reads
    // the liveness captured at that boundary rather than listing every conditional choice.
    liveInCommandReference: true,
    at: () => reactArmed,
    claims: allButCommandReference,
    rows: [
      {
        id: "reaction.choose",
        runFromCommandReference: false,
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
          if (reactSurface === marginSurface) {
            const ordinal = +binding - 1;
            const token = reactionTokens()[ordinal]?.[0];
            if (token)
              marginOffer?.activate(marginReactionKey(token, ordinal), {
                origin: focused(),
                input: "keyboard",
                surface: "margin",
              });
            return;
          }
          pickerFor(reactSurface)
            ?.palette.querySelectorAll(".lf-react")
            [+binding - 1]?.click();
        },
      },
      {
        id: "reaction.move",
        runFromCommandReference: false,
        keys: ["Tab", "Shift+Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
        does: "Move through reactions",
        line: "move",
        repeat: true,
        run: stepResponse,
      },
      {
        id: "response.activate",
        runFromCommandReference: false,
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

  const isReactArmed = () => reactArmed;
  const reactionContextContains = (node) =>
    reactArmed &&
    reactSurface === marginSurface &&
    marginEntryContextContains(fabTargetAt(), node);

  function mount() {
    document.addEventListener("lf-margin-entry-options-closed", () => {
      if (reactArmed && reactSurface === marginSurface) setReact(false);
    });
    watchProjection(document.body, () => {
      if (
        reactArmed &&
        reactSurface === marginSurface &&
        (!marginTarget?.isConnected || fabTargetAt() !== marginTarget)
      )
        setReact(false);
      else if (reactArmed && reactSurface === marginSurface) marginOffer?.update();
    });
    document.addEventListener("lf-thread-hidden", (event) => {
      if (
        reactArmed &&
        reactSurface instanceof Node &&
        event.detail.node.contains(reactSurface)
      )
        setReact(false);
    });
  }
  return {
    registerReactSurface,
    buildReactBar,
    hasReactionTarget,
    syncReactLayout,
    setReact,
    REACT,
    isReactArmed,
    reactionContextContains,
    mount,
  };
}

export async function sendReaction(event, chip, where, postReaction) {
  chip?.setAttribute("aria-busy", "true");
  try {
    const sent = await postReaction(event);
    if (sent) announce(`${event.token} on ${where}`);
    return sent;
  } finally {
    chip?.removeAttribute("aria-busy");
  }
}
function reactionPlace(event) {
  if (event.kind === "reply") return "the reply";
  if (!event.anchor) return "the page";
  const label = anchorLabel(event.anchor, event.about);
  return [...label].length > CONTROL_WORD_CAP
    ? cut(label, 0, CONTROL_WORD_CAP) + "…"
    : label;
}
export const undoSentence = (undoable) => {
  const event = undoable();
  return event?.token
    ? `Take back: ${event.token} on ${reactionPlace(event)}`
    : "Take back the last change you made here";
};
