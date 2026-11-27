/* The response bar's reaction row and the reactions in force a strip or circle wears.

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

   Chip rendering and per-press submission helpers are passive exports. Boot
   constructs the reaction controller with auxiliary-surface, composer, and travel
   capabilities; thread views register their template-owned trigger and palette.
   mount installs the mode teardown listeners after composition. */

import { showNativeLayer, closeNativeLayer } from "../dom/keyboard/layer-stack.js";
import { shownRect, whenNone } from "../dom/geometry.js";
import { scrollIntoView } from "../readings/landing-scroll.js";
import { registerContribution } from "../features/contributions.js";
import { runtime } from "../state/context.js";
import { registry } from "../state/registry.js";
import { composerOpen, fabBar, fabOptions } from "./composing/selection.js";
import { pageSelection } from "./composing/capture.js";
import { responseAction } from "../dom/widget-elements.js";
import { el } from "../lib/elements.js";
import { offerAction } from "../lib/controls.js";
import { keeps } from "../lib/keeps.js";

import { elementById } from "../readings/passages.js";
import { addressableWord } from "../lib/element-word.js";
import {
  anchoringIsReady,
  resolveAnchor,
  visualPartLabel,
} from "../readings/anchor-resolution.js";
import { sameSegments, targetSegments } from "../readings/resolved-target.js";
import { sameAnchor } from "../base/anchor-coordinate.js";
import { announce } from "../transport/notifications.js";
import { claimsEsc, keys } from "../dom/keyboard/scopes.js";
import { saying } from "../dom/keyboard/control-keys.js";
import {
  handBack,
  focusDestination,
  focused,
  closeLayer,
  drawn,
  openerOf,
  openLayer,
} from "../dom/focus.js";
import { repaint } from "../dom/repaint.js";

import {
  allButCommandReference,
  pageCommand,
  pageScope,
} from "../dom/keyboard/register.js";
import {
  cycledRow,
  hasRows,
  nativePress,
  savedReadingSettled,
} from "../dom/keyboard/bindings.js";
import { emojiChoices, reactionsAt } from "../state/thread/model.js";
import { readThreads, threadList } from "../records/thread/state.js";
import { effect, untracked } from "/vendor/signals-core.js";
import { annotationSelection } from "../features/annotation-inventory.js";
import { readPart } from "../state/semantic-state.js";
import { raiseError } from "../transport/errors.js";
import { PRESS, rowArrows } from "../lib/keys.js";
import type { Anchor } from "../../types/domain.js";
import type { createResponseSurface } from "./composing/surface.js";
import type { createMarginProjection } from "./annotation-overlay/margin-projection.js";
import type { createCommandDispatch } from "../records/pending/dispatch.js";
import type { createUndo } from "../records/undo.js";
import type { createCurrentTarget } from "./composing/current-target.js";
import type { Scope } from "../dom/keyboard/bindings.js";
import type { Thread } from "../records/thread/placement.js";

type ResponseSurface = ReturnType<typeof createResponseSurface>;
type Margin = ReturnType<typeof createMarginProjection>;
type Post = ReturnType<typeof createCommandDispatch>["post"];
type ReactionCommands = {
  withdrawReaction: ReturnType<typeof createUndo>["withdraw"];
  postReaction: Post;
};

// The layer's reactions, each its emoji, in declared order. The bar, a reply's strip,
// the page row and the keyboard accelerators all read this one list, so a layer that
// adds or removes an emoji moves every surface at once, and core never names one.
// Empty until the registry has arrived: the register checks every core row's bindings
// as the module evaluates, before the vocabulary is known.
export const reactionEmoji = (): readonly string[] => registry.$reactions?.emoji ?? [];
// A toggle needs the saved reaction in force, including proof that none stands.
export const reactionAvailable = () => readThreads().phase === "ready";
// Whether a thread stands on the bar's target, both read from the page as it stands. A
// quote stands only on the words it resolves to, so an edit beside them, which changes
// the context its anchor recorded, leaves its emoji pressed there, and a quote that
// resolves nowhere stands nowhere. Any other target stands by its anchor's record.
const wordsOf = (anchor: Anchor) => targetSegments(resolveAnchor(anchor));
const standsOn = (anchor: Anchor) => {
  if (!anchor.quote) return ({ anchor: its }: Thread) => sameAnchor(its, anchor);
  const words = wordsOf(anchor);
  // Only a reaction quoting the same words can stand on them, which spares resolving
  // the rest.
  return ({ anchor: its }: Thread) =>
    its !== null &&
    its.quote === anchor.quote &&
    words.length > 0 &&
    sameSegments(words, wordsOf(its));
};
// The choices on one anchor, from the threads' current reading.
const anchorChoices = (anchor: Anchor | null) =>
  reactionAvailable()
    ? emojiChoices(
        reactionEmoji(),
        anchor ? reactionsAt(threadList(), standsOn(anchor)) : [],
      )
    : [];

// One reaction as a press in the response bar; a reply's strip builds its own
// (records/thread/reaction-strips.js). Its emoji is its face and its name, which a
// screen reader says by the emoji's Unicode name. Digits remain keyboard accelerators
// without changing the shape of every chip.
function reactionChip(
  { emoji }: { emoji: string },
  pressed: (emoji: string) => unknown,
) {
  const chip = offerAction("response", "lf-react");
  // A toggle from the start, before the bar paints which reactions stand
  // (`paintBarReactions`), so it wears a reaction's face (controls.css).
  chip.setAttribute("aria-pressed", "false");
  chip.dataset.lfEmoji = emoji;
  responseAction(chip, { glyph: emoji, label: emoji, collapse: true });
  keys(chip, "On a reaction", [
    {
      // Each chip's scope is its own, so one stable id names its press on every chip.
      id: "reaction.press",
      ready: savedReadingSettled,
      when: reactionAvailable,
      keys: [],
      control: chip,
      title: emoji,
      run: () => pressed(emoji),
    },
  ]);
  return chip;
}

// The bar's chips wear the reactions in force on its anchor, as a reply's strip does:
// pressed where one stands, from the press on. A press on a pressed chip
// takes that reaction back (reactHere).
export function paintBarReactions(anchor: Anchor | null) {
  const by = new Map(anchorChoices(anchor).map((choice) => [choice.emoji, choice]));
  for (const chip of fabBar.querySelectorAll(".lf-react-palette > .lf-react")) {
    const inForce = by.get(chip.getAttribute("data-lf-emoji") ?? "")?.inForce;
    keeps(chip, "aria-pressed", String(Boolean(inForce)));
  }
}

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
}: {
  marginEntryChoices: Margin["marginEntryChoices"] | undefined;
  marginEntryContextContains: Margin["marginEntryContextContains"] | undefined;
  openMarginEntryOptions: Margin["openMarginEntryOptions"] | undefined;
  designModeActive: () => boolean;
  currentLocationThread: typeof import("../records/thread/landing.js").currentLocationThread;
  currentTarget: ReturnType<typeof createCurrentTarget>;
} & Pick<
  ResponseSurface,
  | "hideComposer"
  | "syncResponseOptions"
  | "fabAnchorAt"
  | "fabReturnPlaces"
  | "fabTargetAt"
  | "hasPageSelectionTarget"
  | "showFab"
  | "showFabOptions"
  | "updateFab"
>) {
  const surfaces: WeakMap<Element, { palette: HTMLElement; trigger: HTMLElement }> =
    new WeakMap();
  const marginSurface = Symbol("margin reactions");
  let marginOffer: ReturnType<typeof registerContribution> | null = null;
  let marginTarget: Element | null = null;
  let marginAnchor: Anchor | null = null;
  let pageCommands: ReactionCommands | null = null;
  const marginReactionKey = (emoji: string, ordinal: number) =>
    `reaction:${String(ordinal).padStart(4, "0")}:${emoji}`;
  function registerReactSurface(
    surface: Element,
    { palette, trigger }: { palette: HTMLElement; trigger: HTMLElement },
  ) {
    surfaces.set(surface, { palette, trigger });
    return {
      toggle: () => setReact(!(reactArmed && reactSurface === surface), { surface }),
      close: () => {
        if (reactSurface === surface) setReact(false);
      },
    };
  }

  function buildReactBar(commands: ReactionCommands) {
    pageCommands = commands;
    const palette = el("span", "lf-react-palette");
    palette.setAttribute("role", "group");
    palette.setAttribute("aria-label", "Reactions for this selection or element");
    for (const choice of emojiChoices(reactionEmoji(), []))
      palette.append(reactionChip(choice, (emoji) => reactHere(emoji, commands)));
    fabOptions.append(palette);
    syncResponseOptions();
  }

  const anchorWord = (anchor: Anchor | null) => {
    if (!anchor) return "the target";
    if (anchor.quote) return "the selection";
    const addressable = elementById(anchor.section);
    if (anchor.visual)
      return visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return addressableWord(addressable) || "the element";
  };

  async function reactHere(
    emoji: string,
    commands: ReactionCommands,
    anchor: Anchor | null = fabAnchorAt(),
  ) {
    const choice = anchorChoices(anchor).find((choice) => choice.emoji === emoji);
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
      const event: Extract<Parameters<Post>[0], { kind: "comment" }> = {
        kind: "comment",
        revision,
        emoji,
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
  let releaseMarginOptions: (() => void) | null = null;
  // React mode's opener (dom/focus.js, `openLayer`): the control the user was on as the
  // press armed it, which the close hands them back to.
  const reactLayer = {};
  const reactFrom = () => openerOf(reactLayer);
  let reactSurface: Element | typeof marginSurface | null = null;
  // An open reply list closes once its trigger is out of view. The list is in the
  // top layer, and its anchor only stops painting it there, so without this the user
  // would read on through another thread while Tab, arrows and digits still answered
  // the reply scrolled away.
  let reactDeparture: (() => void) | null = null;
  const latestAgentStrip = (held: Element) =>
    held.querySelector(".lf-react-strip.lf-open");
  const pickerFor = (surface: Element | typeof marginSurface | null) =>
    surface instanceof Element ? surfaces.get(surface) : undefined;

  function reactionTarget():
    | { kind: "surface"; surface: Element }
    | { kind: "anchor" | "selection" }
    | { kind: "target"; target: NonNullable<ReturnType<typeof currentTarget>> }
    | null {
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
          key: marginReactionKey(choice.emoji, ordinal),
          activation: choice.emoji,
          glyph: choice.emoji,
          label: choice.emoji,
          rank: "secondary",
          pressed: Boolean(choice.inForce),
        })),
        readings: [],
      }),
      activate: (emoji) => reactHere(emoji, commands, marginAnchor),
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

  function closeSurface(surface: Element | typeof marginSurface | null) {
    if (surface === marginSurface) return;
    reactDeparture?.();
    reactDeparture = null;
    const picker = pickerFor(surface);
    // The platform hands focus back to the opener as the list closes, the layer's own
    // return (dom/focus.js).
    if (picker) closeNativeLayer(picker.palette);
  }

  // A page picker lives in the target's shared margin entry options and therefore owns its
  // geometry. Returning true keeps the floating Comment bar from trying to re-place the
  // same gesture while the margin has it; message-local reaction strips need no claim.
  function syncReactLayout() {
    return reactArmed && reactSurface === marginSurface;
  }

  function setReact(
    on: boolean,
    { surface = null }: { surface?: Element | null } = {},
  ) {
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
      // closes once none of the trigger is within the window and the boxes around it
      // (`shownRect`). The list stands in the top layer, above the floating panel, so
      // the room the panel takes does not take it away; a scroll carrying the trigger
      // out of sight does.
      scrollIntoView(picker.trigger, { block: "nearest", behavior: "instant" });
      showNativeLayer(picker.palette, { source: picker.trigger });
      const opened = reactSurface;
      const seen = (trigger: Element) => shownRect(trigger, new Map());
      reactDeparture = whenNone([picker.trigger], seen, () => {
        if (reactSurface === opened) setReact(false);
      });
      const first =
        surface &&
        reactFrom() === picker.trigger &&
        picker.palette.querySelector(".lf-react");
      if (first) focusDestination(first, "move");
    }
    announce(() => ["React", saying(REACT.rows)].filter(Boolean).join(" — "));
    repaint();
  }

  // Putting the reaction choices away is closing a layer (dom/focus.js, `closeLayer`): the
  // palette's own hand-back as it hides reaches no reader, and a user who was in the
  // choices, the bar or the margin's raise goes back once, to the bar's field, the
  // control the press stood them on, or the list's trigger, whichever stands as the
  // choices go; one they covered then is no way back, and a later frame showing it again
  // must not pull the user onto it. `handBack` tries again a frame later only where the
  // one it chose is swapped by a repaint in that frame, as a reaction press releasing
  // held news repaints the thread. A press armed from nowhere has only the bar's field.
  function closeReact(active: Element | null) {
    const from = reactFrom();
    const trigger = pickerFor(reactSurface)?.trigger;
    const input = fabBar.querySelector(".lf-fab-input");
    const owed =
      fabBar.contains(from) ||
      marginOffer?.contains(active) ||
      active === document.body ||
      active?.closest(".lf-react-palette");
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

  function responseChoices(surface: Element | typeof marginSurface | null): Element[] {
    if (!surface) return [];
    if (surface === marginSurface) return marginEntryChoices?.(fabTargetAt()) ?? [];
    return [...surface.querySelectorAll(".lf-react-palette > .lf-react")].filter(
      (choice) => choice.checkVisibility(),
    );
  }

  function stepResponse(binding: string) {
    const choices = responseChoices(reactSurface);
    if (!hasRows(choices)) return;
    const backward = [rowArrows(choices[0])[0], "ArrowUp", "Shift+Tab"].includes(
      binding,
    );
    // The bar stands whole around the ring, so the step says no position.
    focusDestination(cycledRow(choices, focused(), backward ? -1 : 1), "move");
  }

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
          reactionEmoji()
            .slice(0, 9)
            .map((_, i) => String(i + 1)),
        label: () => {
          const n = Math.min(reactionEmoji().length, 9);
          return n > 1 ? `1–${n}` : "1";
        },
        description: () =>
          reactionEmoji()
            .slice(0, 9)
            .map((emoji, i) => `${i + 1} ${emoji}`)
            .join(", "),
        title: "react",
        when: reactionAvailable,
        runKey: (binding) => {
          if (reactSurface === marginSurface) {
            const ordinal = +binding - 1;
            const emoji = reactionEmoji()[ordinal];
            if (emoji)
              marginOffer?.activate(marginReactionKey(emoji, ordinal), {
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
  } satisfies Scope;

  const isReactArmed = () => reactArmed;
  const reactionContextContains = (node: Element | null) =>
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
      threads: root.effective.thread.collection.threads,
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
      reactionEmoji().length > 0 &&
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
    syncReactLayout,
    setReact,
    isReactArmed,
    reactionContextContains,
    mount,
  };
}

export async function sendReaction(
  event: Extract<Parameters<Post>[0], { kind: "comment" | "reply" }>,
  where: string,
  postReaction: Post,
) {
  const sent = await postReaction(event);
  if (sent) announce(`${event.emoji} on ${where}`);
  return sent;
}
