/* The response bar's reaction row and the tokens in force a strip or circle wears.

   An open anchored composer owns its general response disclosure: reactions only
   contribute declared actions to it, and `e` opens that local group focused on its
   first reaction. With no composer open, `e` contributes the reaction margin entries to the
   selected element's existing margin cluster. While that explicit mode stands, its
   contribution owns all six margin entries; readings in force and unrelated actions remain
   in Page Map and return when the mode closes. Those temporary margin entries unfold the
   cluster where it stands, in the rail or as a pin, and claim no permanent rail width. A thread-local `e` opens
   the thread-owned row on the latest agent message. `REACT` claims the keyboard
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
   open a separate palette below the target. The compact response bar's disclosure controller
   owns its state, focus return, and geometry independently.
   Thread reactions remain in their thread-owned strip. The event still
   carries its durable authored anchor, while
   the temporary addressable resolves selected text to the first rendered block, matching the
   target where replay later seats its reaction in force.

   Putting a reaction on or taking it back ends the response gesture synchronously,
   after admission to the local ledger. Its durable answer never closes a newer composer
   or returns focus: those belong to the gesture that has already ended.

   Token rendering and per-press submission helpers are passive exports. Boot
   constructs the reaction controller with auxiliary-surface, composer, and travel
   capabilities; thread views register their template-owned trigger and palette.
   mount installs the mode teardown listeners after composition. */

import { showNativeLayer, closeNativeLayer } from "./keyboard/layer-stack.js";
import { clipsPastSurfaces, seenRect, whenNone } from "./geometry.js";
import { scrollIntoReadingBand } from "./landing-scroll.js";
import { registerContribution } from "./contributions.js";
import { runtime } from "./context.js";
import { registry } from "./registry.js";
import { composerOpen, fabBar, fabOptions } from "./composing/selection.js";
import { pageSelection } from "./composing/capture.js";
import { el, offerAction, responseAction } from "./widget-elements.js";
import { HOLDS_WORD } from "./held-word.js";
import { keeps } from "./keeps.js";

import { elementById } from "./passages.js";
import { addressableWord } from "./addressable-names.js";
import { anchoringIsReady, visualPartLabel } from "./anchor-resolution.js";
import { announce } from "./notifications.js";
import { claimsEsc, keys, saying } from "./keyboard/scopes.js";
import {
  handBack,
  focusDestination,
  focused,
  closeLayer,
  drawn,
  openerOf,
  openLayer,
} from "./focus.js";
import { repaint } from "./repaint.js";

import { allButCommandReference, pageCommand, pageScope } from "./keyboard/register.js";
import {
  PRESS,
  cycledRow,
  hasRows,
  nativePress,
  rowArrows,
  savedReadingSettled,
} from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { anchorLabel } from "./thread/messages.js";
import { reactionsAt, tokenChoices } from "./thread/model.js";
import { allThreads, readThreads } from "./thread/state.js";
import { effect, untracked } from "/runtime/framework.js";
import { annotationSelection } from "./annotation-inventory.js";
import { readPart } from "./semantic-state.js";
import { raiseError } from "./errors.js";

/** @typedef {import("../types/domain.js").Anchor} Anchor
 * @typedef {ReturnType<typeof import("./composing/surface.js").createResponseSurface>} ResponseSurface
 * @typedef {ReturnType<typeof import("./annotation-overlay/margin-projection.js").createMarginProjection>} Margin
 * @typedef {ReturnType<typeof import("./pending/dispatch.js").createCommandDispatch>["post"]} Post
 * @typedef {{withdrawReaction: ReturnType<typeof import("./undo.js").createUndo>["withdraw"], postReaction: Post}} ReactionCommands
 */

const reactionVocabulary = () => registry.$reactions?.tokens ?? {};
// The layer's reaction vocabulary, in declared order. The bar, a reply's strip, the
// page row and the keyboard accelerators all read this one list, so a layer that
// renames, adds or removes a token moves every surface at once, and core never learns
// a token's name. Empty until the registry has arrived: the register checks every core
// row's bindings as the module evaluates, before the vocabulary is known.
export const reactionTokens = () => Object.entries(reactionVocabulary());
// A toggle needs the saved reaction in force, including proof that none stands.
export const reactionAvailable = () => readThreads().phase === "ready";
// The choices on one anchor, from the threads' current reading.
/** @param {Anchor | null} anchor */
const anchorChoices = (anchor) =>
  reactionAvailable()
    ? tokenChoices(
        reactionVocabulary(),
        anchor ? reactionsAt(allThreads(), anchor) : [],
      )
    : [];

// One token as a press in the response bar; a reply's strip builds its own
// (thread/reaction-strips.js). The token names the control and the compact face
// stays the declared mark. Digits remain keyboard accelerators without changing the
// shape of every chip.
/** @param {{name: string, glyph: string, label: string}} choice @param {(name: string) => unknown} pressed */
function reactionChip({ name, glyph, label }, pressed) {
  const chip = offerAction("response", `lf-react ${HOLDS_WORD}`);
  chip.dataset.token = name;
  chip.title = label;
  chip.setAttribute("aria-label", label);
  responseAction(chip, { glyph, label: name, collapse: true });
  keys(chip, "On a reaction", [
    {
      id: `reaction.${name}`,
      ready: savedReadingSettled,
      when: reactionAvailable,
      keys: [],
      control: chip,
      title: label,
      run: () => pressed(name),
    },
  ]);
  return chip;
}

// The bar's chips wear the reactions in force on its anchor, as a reply's strip does:
// pressed where one stands, from the press on. A press on a pressed chip
// takes that reaction back (reactHere).
/** @param {Anchor | null} anchor */
export function paintBarReactions(anchor) {
  const by = new Map(anchorChoices(anchor).map((choice) => [choice.name, choice]));
  for (const chip of fabBar.querySelectorAll(".lf-react-palette > .lf-react")) {
    const inForce = by.get(chip.getAttribute("data-token") ?? "")?.inForce;
    keeps(chip, "aria-pressed", String(Boolean(inForce)));
  }
}

/** @param {{marginEntryChoices: Margin["marginEntryChoices"] | undefined,
 * marginEntryContextContains: Margin["marginEntryContextContains"] | undefined,
 * openMarginEntryOptions: Margin["openMarginEntryOptions"] | undefined,
 * designModeActive: () => boolean,
 * currentLocationThread: typeof import("./thread/landing.js").currentLocationThread,
 * currentTarget: ReturnType<typeof import("./composing/current-target.js").createCurrentTarget>
 * } & Pick<ResponseSurface, "hideComposer" | "syncResponseOptions" | "fabAnchorAt" | "fabReturnPlaces" |
 * "fabTargetAt" | "hasPageSelectionTarget" | "showFab" | "showFabOptions" | "updateFab">} dependencies */
export function createReactionController({
  marginEntryChoices,
  marginEntryContextContains,
  openMarginEntryOptions,
  designModeActive,
  hideComposer,
  syncResponseOptions,
  fabAnchorAt,
  fabReturnPlaces,
  fabTargetAt,
  hasPageSelectionTarget,
  showFab,
  showFabOptions,
  updateFab,
  currentLocationThread,
  currentTarget,
}) {
  /** @type {WeakMap<Element, {palette: HTMLElement, trigger: HTMLElement}>} */
  const surfaces = new WeakMap();
  const marginSurface = Symbol("margin reactions");
  /** @type {ReturnType<typeof registerContribution> | null} */
  let marginOffer = null;
  /** @type {Element | null} */
  let marginTarget = null;
  /** @type {Anchor | null} */
  let marginAnchor = null;
  /** @type {ReactionCommands | null} */
  let pageCommands = null;
  /** @param {string} name @param {number} ordinal */
  const marginReactionKey = (name, ordinal) =>
    `reaction:${String(ordinal).padStart(4, "0")}:${name}`;
  /** @param {Element} surface @param {{palette: HTMLElement, trigger: HTMLElement}} picker */
  function registerReactSurface(surface, { palette, trigger }) {
    surfaces.set(surface, { palette, trigger });
    return {
      toggle: () => setReact(!(reactArmed && reactSurface === surface), { surface }),
      close: () => {
        if (reactSurface === surface) setReact(false);
      },
    };
  }

  /** @param {ReactionCommands} commands */
  function buildReactBar(commands) {
    pageCommands = commands;
    const palette = el("span", "lf-react-palette");
    palette.setAttribute("role", "group");
    palette.setAttribute("aria-label", "Reactions for this selection or element");
    for (const choice of tokenChoices(reactionVocabulary(), []))
      palette.append(reactionChip(choice, (token) => reactHere(token, commands)));
    fabOptions.append(palette);
    syncResponseOptions();
  }

  /** @param {Anchor | null} anchor */
  const anchorWord = (anchor) => {
    if (!anchor) return "the target";
    if (anchor.quote) return "the selection";
    const addressable = elementById(anchor.section);
    if (anchor.visual)
      return visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return addressableWord(addressable) || "the element";
  };

  /** @param {string} name @param {ReactionCommands} commands @param {Anchor | null} anchor */
  async function reactHere(name, commands, anchor = fabAnchorAt()) {
    const choice = anchorChoices(anchor).find((choice) => choice.name === name);
    if (!choice) return;
    const { inForce } = choice;
    // Read before the bar goes, because the reading is about the bar that is open.
    // The bar owns what that answer is. `setReact(false)` runs after the bar goes and the
    // palette makes a return of its own, so the user lands once, when everything has
    // settled, rather than once as the bar goes and again after the palette.
    const returnTo = fabReturnPlaces();
    const revision = runtime.currentRevision;
    if (!anchor || revision === null) return;
    let sent;
    if (inForce) sent = commands.withdrawReaction(inForce);
    else {
      /** @type {Extract<Parameters<Post>[0], {kind: "comment"}>} */
      const event = {
        kind: "comment",
        revision,
        token: name,
        anchor: structuredClone(anchor),
      };
      if (designModeActive()) event.about = "design";
      sent = sendReaction(event, anchorWord(anchor), commands.postReaction);
    }
    closeLayer(
      () => {
        hideComposer();
        showFab(null);
        setReact(false);
      },
      () => handBack(...returnTo),
    );
    getSelection()?.removeAllRanges();
    await sent;
  }

  // The react press opens one surface's list. `e` uses the latest agent reply in the
  // thread the user is in, an already raised bar, a completed native
  // selection, or the addressable element holding focus. This same reading decides whether the page
  // command exists, so dispatch cannot advertise a reaction before its target.
  let reactArmed = false;
  let reactRaised = false;
  // The margin lends reaction mode its disclosure and returns a release that restores
  // the user's previous fold only while this mode still owns it.
  /** @type {(() => void) | null} */
  let releaseMarginOptions = null;
  // React mode's opener (focus.js, `openLayer`): the control the user was on as the
  // press armed it, which the close hands them back to.
  const reactLayer = {};
  const reactFrom = () => openerOf(reactLayer);
  /** @type {Element | typeof marginSurface | null} */
  let reactSurface = null;
  // An open reply list closes once its trigger is out of view. The list is in the
  // top layer, and its anchor only stops painting it there, so without this the user
  // would read on through another thread while Tab, arrows and digits still answered
  // the reply scrolled away.
  /** @type {(() => void) | null} */
  let reactDeparture = null;
  /** @param {Element} held */
  const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
  /** @param {Element | typeof marginSurface | null} surface */
  const pickerFor = (surface) =>
    surface instanceof Element ? surfaces.get(surface) : undefined;

  /** @returns {{kind: "surface", surface: Element} | {kind: "anchor" | "selection"} | {kind: "target", target: NonNullable<ReturnType<typeof currentTarget>>} | null} */
  function reactionTarget() {
    const said = currentLocationThread();
    const strip = said && latestAgentStrip(said.held);
    if (strip) return { kind: "surface", surface: strip };
    if (fabAnchorAt()) return { kind: "anchor" };
    if (hasPageSelectionTarget()) return { kind: "selection" };
    const target = currentTarget();
    return target ? { kind: "target", target } : null;
  }
  const hasReactionTarget = () => Boolean(reactionTarget());

  function raiseMarginSurface() {
    const anchor = fabAnchorAt();
    const target = anchor && fabTargetAt();
    const commands = pageCommands;
    if (!commands || !target || !openMarginEntryOptions) return false;
    // `e` is an explicit reaction mode. Comment remains on `c`, so this temporary
    // contribution contains reactions alone.
    fabBar.dataset.lfMarginRaised = "1";
    marginAnchor = structuredClone(anchor);
    marginOffer = registerContribution({
      key: "responses",
      target,
      read: () => ({
        side: "after",
        entries: anchorChoices(marginAnchor).map((choice, ordinal) => ({
          key: marginReactionKey(choice.name, ordinal),
          activation: choice.name,
          glyph: choice.glyph,
          label: choice.label,
          rank: "secondary",
          className: "lf-react",
          pressed: Boolean(choice.inForce),
        })),
        readings: [],
      }),
      activate: (name) => reactHere(name, commands, marginAnchor),
    });
    marginTarget = target;
    const release = openMarginEntryOptions(target, "responses");
    if (release) {
      releaseMarginOptions = release;
      return true;
    }
    marginOffer.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    return false;
  }

  function lowerMarginSurface() {
    // Release before removing the choices so the repaint sees the restored fold.
    releaseMarginOptions?.();
    releaseMarginOptions = null;
    marginOffer?.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    delete fabBar.dataset.lfMarginRaised;
  }

  /** @param {Element | typeof marginSurface | null} surface */
  function closeSurface(surface) {
    if (surface === marginSurface) return;
    reactDeparture?.();
    reactDeparture = null;
    const picker = pickerFor(surface);
    // The platform hands focus back to the opener as the list closes, the layer's own
    // return (focus.js).
    if (picker) closeNativeLayer(picker.palette);
    picker?.trigger.setAttribute("aria-expanded", "false");
  }

  // A page picker lives in the target's shared margin entry options and therefore owns its
  // geometry. Returning true keeps the floating Comment bar from trying to re-place the
  // same gesture while the margin has it; message-local reaction strips need no claim.
  function syncReactLayout() {
    return reactArmed && reactSurface === marginSurface;
  }

  /** @param {boolean} on @param {{surface?: Element | null}} options */
  function setReact(on, { surface = null } = {}) {
    if (on && !reactionAvailable()) return;
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
    // Closing hides the palette synchronously. Capture its focused control first: a
    // reply's list hands focus back to its opener as it closes, and the margin's goes
    // with its contribution, after which the browser reports where focus went rather
    // than the choice the user was on, the fact the return below reads.
    const closingActive = on ? null : focused();
    if (!on) {
      closeReact(closingActive);
      repaint();
      return;
    }
    closeSurface(reactSurface);
    if (on) {
      openLayer(reactLayer);
      if (surface) reactSurface = surface;
      else {
        const target = reactionTarget();
        if (target?.kind === "surface") reactSurface = target.surface;
        else if (target?.kind === "anchor" || target?.kind === "target") {
          if (target.kind === "target") {
            // The target's margin row may stand where the target itself is
            // off screen. Keep the semantic anchor without
            // asking a floating bar to find geometry; the shared element is the surface.
            showFab(target.target.anchor, {
              place: false,
            });
            reactRaised = true;
          }
          if (!raiseMarginSurface()) {
            if (reactRaised) showFab(null);
            reactRaised = false;
            reactSurface = null;
            openLayer(reactLayer, null);
            raiseError("That reaction target is no longer available");
            return;
          }
          reactSurface = marginSurface;
        } else {
          reactSurface = null;
          openLayer(reactLayer, null);
          return;
        }
      }
      const picker = pickerFor(reactSurface);
      if (reactSurface !== marginSurface && !picker) {
        reactSurface = null;
        openLayer(reactLayer, null);
        return;
      }
      reactArmed = true;
      if (picker) {
        // `e` opens the latest reply of the thread the user is in, which may be
        // scrolled out of the list: it comes into view to be answered, since a list
        // hung from a trigger out of view would neither show nor stay open, and it
        // closes once none of the trigger is in front of the user (`seenRect`). The
        // list stands in the top layer, above the floating panel, so a surface standing
        // over the trigger does not take it away; a scroll carrying the trigger out of
        // sight does.
        scrollIntoReadingBand(picker.trigger, picker.trigger, "nearest", "instant");
        showNativeLayer(picker.palette, { source: picker.trigger });
        const opened = reactSurface;
        /** @param {Element} trigger */
        const seen = (trigger) => seenRect(trigger, clipsPastSurfaces());
        reactDeparture = whenNone([picker.trigger], seen, () => {
          if (reactSurface === opened) setReact(false);
        });
        picker.trigger.setAttribute("aria-expanded", "true");
        const first =
          surface &&
          reactFrom() === picker.trigger &&
          picker.palette.querySelector(".lf-react");
        if (first) focusDestination(first, "move");
      }
      announce(`React — ${saying(REACT.rows)}`);
    }
    repaint();
  }

  // Putting the reaction choices away is closing a layer (focus.js, `closeLayer`): the
  // palette's own hand-back as it hides reaches no reader, and a user who was in the
  // choices, the bar or the margin's raise goes back once, to the bar's field, the
  // control the press stood them on, or the list's trigger, whichever stands as the
  // choices go; one they covered then is no way back, and a later frame showing it again
  // must not pull the user onto it. `handBack` tries again a frame later only where the
  // one it chose is swapped by a repaint in that frame, as a reaction press releasing
  // held news repaints the thread. A press armed from nowhere has only the bar's field.
  /** @param {Element | null} active */
  function closeReact(active) {
    const from = reactFrom();
    const trigger = pickerFor(reactSurface)?.trigger;
    const input = fabBar.querySelector(".lf-fab-input");
    const owed =
      fabBar.contains(from) ||
      marginOffer?.contains(active) ||
      active === document.body ||
      active?.closest?.(".lf-react-palette");
    // Which candidates the user may go back to is read before the close, since it ends
    // the reading of where the press came from; which of them stand is read after it,
    // since the close itself may show one, as putting the bar back does its field.
    const candidates = from ? [input, from, trigger] : [input];
    closeLayer(
      () => {
        closeSurface(reactSurface);
        reactArmed = false;
        reactSurface = null;
        openLayer(reactLayer, null);
        if (reactRaised) showFab(null);
        reactRaised = false;
        lowerMarginSurface();
        if (fabAnchorAt()) showFab(fabAnchorAt());
      },
      owed && (() => handBack(...candidates.filter(drawn))),
    );
  }

  /** @param {Element | typeof marginSurface | null} surface @returns {Element[]} */
  function responseChoices(surface) {
    if (!surface) return [];
    if (surface === marginSurface) return marginEntryChoices?.(fabTargetAt()) ?? [];
    return [...surface.querySelectorAll(".lf-react-palette > .lf-react")].filter(
      (choice) => choice.checkVisibility(),
    );
  }

  /** @param {string} binding */
  function stepResponse(binding) {
    const choices = responseChoices(reactSurface);
    if (!hasRows(choices)) return;
    const backward = [rowArrows(choices[0])[0], "ArrowUp", "Shift+Tab"].includes(
      binding,
    );
    focusDestination(cycledRow(choices, focused(), backward ? -1 : 1), "move");
    beginWalk("reaction", "Reaction", () =>
      listWalkPosition(responseChoices(reactSurface), focused()),
    );
  }

  /** @satisfies {import("./keyboard/bindings.js").Scope} */
  const REACT = {
    title: "With reactions open",
    ready: savedReadingSettled,
    escape: "inner",
    // Opening the modal reference dismisses this transient mode. Its section still reads
    // the liveness captured at that boundary rather than listing every conditional choice.
    liveInCommandReference: true,
    at: () => reactArmed,
    // The open list is where the mode stands. The margin's list has no node of its own
    // and stands wherever its entry does.
    root: () => (reactSurface instanceof Element ? reactSurface : document),
    claims: allButCommandReference,
    rows: [
      {
        id: "reaction.choose",
        touch: false,
        runFromCommandReference: false,
        keys: () =>
          reactionTokens()
            .slice(0, 9)
            .map((_, i) => String(i + 1)),
        label: () => {
          const n = Math.min(reactionTokens().length, 9);
          return n > 1 ? `1–${n}` : "1";
        },
        description: () =>
          reactionTokens()
            .slice(0, 9)
            .map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`)
            .join(", "),
        title: "react",
        when: reactionAvailable,
        runKey: (binding) => {
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
          const buttons =
            pickerFor(reactSurface)?.palette.querySelectorAll(".lf-react");
          nativePress(buttons?.[+binding - 1])?.();
        },
      },
      {
        id: "reaction.move",
        touch: false,
        runFromCommandReference: false,
        keys: ["Tab", "Shift+Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
        title: "move",
        repeat: true,
        runKey: stepResponse,
      },
      {
        id: "response.activate",
        touch: false,
        runFromCommandReference: false,
        keys: PRESS,
        title: "choose",
        when: () =>
          responseChoices(reactSurface).some((choice) => choice === focused()),
        run: () => nativePress(focused())?.(),
      },
      {
        id: "reaction.cancel",
        touch: false,
        keys: ["Escape"],
        title: "cancel",
        run: () => setReact(false),
      },
    ],
  };

  const isReactArmed = () => reactArmed;
  /** @param {Element | null} node */
  const reactionContextContains = (node) =>
    reactArmed &&
    reactSurface === marginSurface &&
    marginEntryContextContains?.(fabTargetAt(), node);

  function mount() {
    document.addEventListener("lf-margin-entry-options-closed", () => {
      if (reactArmed && reactSurface === marginSurface) setReact(false);
    });
    // The margin's entries are drawn from the threads and the annotation inventory, so a
    // change to either may retire or move the offer's target. This reads the margin's
    // nodes, which the watcher cannot track, so it reads those parts itself.
    const margin = readPart((root) => ({
      threads: root.effective.thread.all,
      annotations: annotationSelection(root),
    }));
    effect(() => {
      margin();
      untracked(() => {
        if (
          reactArmed &&
          reactSurface === marginSurface &&
          (!marginTarget?.isConnected || fabTargetAt() !== marginTarget)
        )
          setReact(false);
        else if (reactArmed && reactSurface === marginSurface) marginOffer?.update();
      });
    });
  }
  pageScope("reactions", REACT);
  // `e` opens the list on the target the user has already named: the current selection,
  // item, or agent reply. Digits are optional accelerators in the registry's declared
  // order, and the mode's own scope above owns them once the list is open.
  // A finger opens the same choices through Other responses on a selection or item,
  // or through an agent reply’s reaction control.
  pageCommand({
    id: "reaction.open",
    ready: savedReadingSettled,
    touch: false,
    keys: ["e"],
    description: "On the selection, the focused item or the open reply",
    title: "reactions",
    when: () =>
      reactionAvailable() &&
      reactionTokens().length > 0 &&
      hasReactionTarget() &&
      (anchoringIsReady() || !pageSelection()),
    run: () => {
      // Selection capture normally follows the pointer gesture in its queued turn. A fast
      // `e` may arrive before that turn even though the native Selection is already
      // complete. Capture it now so the command cannot advertise reaction digits while
      // opening no corresponding choices.
      if (pageSelection() && !fabAnchorAt()) updateFab();
      if (composerOpen && fabAnchorAt()) showFabOptions({ reaction: true });
      else setReact(true);
    },
  });

  return {
    registerReactSurface,
    buildReactBar,
    hasReactionTarget,
    syncReactLayout,
    setReact,
    isReactArmed,
    reactionContextContains,
    mount,
  };
}

/** @param {Extract<Parameters<Post>[0], {kind: "comment" | "reply"}>} event @param {string} where @param {Post} postReaction */
export async function sendReaction(event, where, postReaction) {
  const sent = await postReaction(event);
  if (sent) announce(`${event.token} on ${where}`);
  return sent;
}
// Where a reaction stands, as Threads names its anchor.
/** @param {{kind: string, anchor?: Anchor | null | undefined, about?: import("../types/contract.js").EventMap["comment"]["about"]}} event */
export function reactionPlace(event) {
  if (event.kind === "reply") return "the reply";
  if (!event.anchor) return "the page";
  return anchorLabel(event.anchor, event.about);
}
