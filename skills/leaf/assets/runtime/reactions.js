/* The response bar's reaction row and the standing tokens a strip or circle wears.

   For a page target, `r` contributes Comment, Suggest where available, and the reaction
   Buttons to that target's existing Button options. Those temporary Buttons borrow the
   cluster's room and dock with it when necessary; they do not claim permanent rail
   width. A thread-local `r` opens the conversation-owned row on the latest agent
   message. With none of those targets, it shows “Select something to react to” and
   opens nothing. `REACT` claims the keyboard while a list is open. Arrow keys wrap
   through every visible Button in the target's shared cluster, including its primary
   actions and Page-map overflow; floating and message-local rows walk their own choices.
   Tab and Shift-Tab follow that same order. The Page-map dialog remains part of the
   response's target context but owns its native keyboard walk and Escape while open.
   Closing it restores its exact opener; selecting overflow presses the original Button
   before its temporary target is released. Enter or Space presses the focused choice,
   digits remain optional reaction accelerators in declaration order, and a stray key
   closes the list before keeping its ordinary meaning.

   The `r` key unfolds this same cluster's secondary Button group for a page selection
   or item and shows the declared reaction Buttons together within the six-fitting
   budget. Comment and Suggest retain their separate `c` and compact response-bar routes
   rather than displacing reactions from the mode that explicitly asked for them. The
   digit register and visible choices therefore name the same complete set. The choices
   do not widen the rail or open a separate palette below the target. The compact
   response bar's Tab state stays in that bar. Conversation reactions remain in their
   conversation-owned strip. The event still carries its durable authored anchor, while
   the temporary item resolves selected text to the first rendered block, matching the
   target where replay later seats its standing reaction. */
import {
  buttonChoices,
  buttonContextContains,
  foldButtonOptions,
  marginButton,
  marginButtonState,
  openButtonOptions,
  registerMarginItem,
  unfoldedButtons,
} from "./living-margin.js";
import { runtime } from "./context.js";
import { CONTROL_WORD_CAP, designOn } from "./design.js";
import { registry } from "./registry.js";
import { fabBar, hideComposer, setSuggestionMode } from "./composing/selection.js";
import { el, offer, responseAction } from "./widget-elements.js";
import { fabAnchorAt, fabReturnTo, fabTargetAt, showFab } from "./composing/surface.js";
import { cut, elementById } from "./passages.js";
import { itemWord, visualPartLabel } from "./anchors.js";
import { undoable, withdraw } from "./projection.js";
import { post } from "./outbox.js";
import { announce, notice } from "./notifications.js";
import { claimsEsc, focused, paintHere, saying } from "./keyboard/scopes.js";
import { standingConversation } from "./conversation/landing.js";
import { EVERYTHING, standingItem } from "./keyboard/page.js";
import { PRESS } from "./keyboard/bindings.js";
import { anchorLabel } from "./conversation/messages.js";

// Standing tokens wear their word in strips and the settled witness in margin circles.
// Both carry the event a second press takes back. The reaction rides the pill rather
// than a map beside it, so a reconcile that keeps the node keeps the fact with it.
export function paintReactionStanding(strip, standing) {
  const by = new Map(standing.map((x) => [x.token, x]));
  for (const pill of strip.querySelectorAll(":scope > .lf-react-palette > .lf-react")) {
    const on = by.get(pill.dataset.token) ?? null;
    pill.setAttribute("aria-pressed", on ? "true" : "false");
    if (pill.classList.contains("lf-margin-button"))
      marginButtonState(pill, on ? "settled" : "idle");
    pill.lfReaction = on;
  }
}

const reactionVocabulary = () => registry.$reactions?.tokens;
const suggestHere = () => setSuggestionMode(true);

// The layer's reaction vocabulary, in declared order. The bar, a reply's strip, the
// page row and the keyboard accelerators all read this one list, so a layer that
// renames, adds or removes a token moves every surface at once, and core never learns
// a token's name. Empty until the registry has arrived: the register checks every core
// row's bindings as the module evaluates, before the vocabulary is known.
export const reactionTokens = () => Object.entries(reactionVocabulary() ?? {});

// One token as a press, built the same way wherever it stands. The word shows only
// while the token stands on its target, so a closed surface keeps the reader's marks
// without offering the whole vocabulary. Digits remain keyboard accelerators without
// changing the shape of every pill.
function reactPill(
  name,
  entry,
  pressed,
  { margin = false, response = false, ordinal = 0 } = {},
) {
  const pill = offer("button", `${margin || response ? "" : "lf-pill "}lf-react`);
  const meaning = `${name} — ${entry.means}`;
  pill.dataset.token = name;
  if (margin) {
    pill.setAttribute("aria-label", meaning);
    marginButton(pill, {
      key: `reaction:${String(ordinal).padStart(4, "0")}:${name}`,
      glyph: entry.glyph,
      label: meaning,
      role: "secondary",
    });
  } else {
    pill.title = meaning;
    pill.setAttribute("aria-label", name);
    if (response) responseAction(pill, { glyph: entry.glyph, label: name });
    else
      pill.append(
        el("span", "lf-react-glyph", entry.glyph),
        el("span", "lf-react-word", name),
      );
  }
  pill.onclick = () => pressed(name, pill);
  return pill;
}

const surfaces = new WeakMap();
let surfaceOrdinal = 0;
let marginSurface = null;
let marginOffer = null;
export function buildReactSurface(
  surface,
  pressed,
  {
    label,
    target,
    marginActions = false,
    responseActions = false,
    forceTrigger = false,
    triggerLabel = null,
  },
) {
  if (!reactionTokens().length && !forceTrigger) return surface;
  surface.classList.add("lf-react-surface");
  const floatingResponses = surface === fabBar;
  const trigger = offer(
    "button",
    floatingResponses ? "lf-react-trigger" : "lf-pill lf-react-trigger",
    // The strip's trigger is a disclosure and wears the register's verb with the
    // margin's own "…" suffix (visibleButtonLabel): a bare "…" under a reply was a
    // control nobody could name without hovering it.
    floatingResponses ? "" : "React…",
  );
  if (floatingResponses)
    responseAction(trigger, {
      icon: "more",
      label: "Other responses",
      behavior: "options",
      collapse: true,
    });
  trigger.setAttribute("aria-expanded", "false");
  // The strip's trigger says its own word; only the icon-only floating trigger needs a
  // name written on it, and a label that differed from the visible "React…" would fail
  // a reader who works the page by saying what they see.
  if (floatingResponses) {
    const showLabel = triggerLabel ?? "Show reactions";
    trigger.setAttribute("aria-label", showLabel);
    trigger.title = showLabel;
  }
  const palette = el("span", "lf-react-palette");
  palette.id = `lf-reactions-${++surfaceOrdinal}`;
  palette.setAttribute("role", "group");
  palette.setAttribute("aria-label", label);
  trigger.setAttribute("aria-controls", palette.id);
  for (const [ordinal, [name, entry]] of reactionTokens().entries())
    palette.append(
      reactPill(name, entry, pressed, {
        margin: marginActions,
        response: responseActions,
        ordinal,
      }),
    );
  surface.append(trigger, palette);
  surfaces.set(surface, { palette, target, trigger });
  trigger.onclick = () => {
    if (surface === fabBar)
      setReact(!(reactArmed && reactSurface === fabBar), {
        surface: fabBar,
        focusPicker: true,
      });
    else setReact(!(reactArmed && reactSurface === surface), { surface });
  };
  return surface;
}

export function buildReactBar() {
  const fabSuggest = responseAction(offer("button", "lf-fab-suggest"), {
    icon: "edit",
    label: "Suggest",
    behavior: "disclosure",
  });
  fabSuggest.onclick = () => {
    if (!fabAnchorAt()?.quote || designOn) return;
    setReact(false);
    suggestHere();
  };
  fabBar.append(fabSuggest);
  buildReactSurface(fabBar, reactHere, {
    label: "Reactions for this selection or item",
    target: () => anchorWord(fabAnchorAt()),
    responseActions: true,
    forceTrigger: true,
    triggerLabel: "Show other responses",
  });
  marginSurface = el("div", "lf-margin-reactions");
  marginSurface.setAttribute("role", "group");
  marginSurface.setAttribute("aria-label", "Other responses");
  buildReactSurface(marginSurface, reactHere, {
    label: "Reactions for this selection or item",
    target: () => anchorWord(fabAnchorAt()),
    marginActions: true,
    forceTrigger: true,
  });
}

const anchorWord = (anchor) => {
  if (!anchor) return "the target";
  if (anchor.quote) return "the selection";
  const item = elementById(anchor.section);
  if (anchor.visual) return visualPartLabel(item, anchor.visual) ?? anchor.visual;
  return itemWord(item) || "the item";
};

async function reactHere(name, pill) {
  const anchor = fabAnchorAt();
  const returnTo = fabReturnTo();
  if (!anchor) return;
  if (pill.lfReaction) {
    await withdraw(pill.lfReaction);
    hideComposer();
    showFab(null);
    setReact(false);
    if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
    return;
  }
  const event = {
    kind: "comment",
    revision: runtime.currentRevision,
    token: name,
    anchor: structuredClone(anchor),
  };
  if (designOn) event.about = "layer";
  const sent = await sendReaction(event, pill, anchorWord(anchor));
  if (!sent) return;
  hideComposer();
  showFab(null);
  setReact(false);
  if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
  getSelection()?.removeAllRanges();
}

export async function sendReaction(event, pill, where) {
  pill.setAttribute("aria-busy", "true");
  try {
    const sent = await post(event);
    if (sent) announce(`${event.token} on ${where}`);
    return sent;
  } finally {
    pill.removeAttribute("aria-busy");
  }
}

// The react press opens one surface's list. `r` uses the latest agent reply in the
// thread the reader is standing in, an already raised bar, or the item holding focus.
// A page with none of those has no reaction target: it says what is missing and leaves
// Threads alone.
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

function raiseMarginSurface() {
  const anchor = fabAnchorAt();
  const target = anchor && fabTargetAt();
  if (!marginSurface || !target) return false;
  // `r` is an explicit reaction mode. Comment and Suggest remain their own `c` and
  // response-bar routes, so this temporary contribution contains reactions alone.
  fabBar.dataset.lfMarginRaised = "1";
  // Register the response surface in the state it is about to show. Registering its
  // collapsed face first makes the projection treat the six choices as hidden owner
  // content; a fast `r` can then arm their digit shortcuts while only the old floating
  // ellipsis remains on screen.
  marginSurface.classList.add("lf-react-open");
  paintReactionStanding(
    marginSurface,
    [...fabBar.querySelectorAll(".lf-react[aria-pressed='true']")]
      .map((pill) => pill.lfReaction)
      .filter(Boolean),
  );
  marginOffer = registerMarginItem({
    key: "responses",
    target,
    controls: marginSurface,
    side: "after",
    // The choices borrow whatever RHS is available and dock as one item when it is
    // not. Reserving their temporary width would move the page the first time `r`
    // opened and leave that larger rail behind after the choices closed.
    claim: false,
  });
  const standing = unfoldedButtons()?.lfTarget === target;
  if (openButtonOptions(target)) {
    marginUnfolded = !standing;
    return true;
  }
  marginSurface.classList.remove("lf-react-open");
  marginOffer.unregister();
  marginOffer = null;
  return false;
}

function lowerMarginSurface() {
  marginOffer?.unregister();
  marginOffer = null;
  delete fabBar.dataset.lfMarginRaised;
  // A raise that unfolded the target's Buttons to stand these choices in puts that fold
  // back, so cancelling leaves the cluster as the press found it rather than an empty
  // fold the reader has to close themselves. Only that raise: this runs on every
  // disarm, including one whose surface was a reply strip and which never raised the
  // margin at all, and including one over a fold the reader had already opened for
  // themselves — folding either takes away a layer the gesture never put on.
  if (marginUnfolded) foldButtonOptions();
  marginUnfolded = false;
}

function closeSurface(surface) {
  surface?.classList.remove("lf-react-open");
  pickerFor(surface)?.trigger.setAttribute("aria-expanded", "false");
}

// A page picker lives in the target's shared Button options and therefore owns its
// geometry. Returning true keeps the floating Comment bar from trying to re-place the
// same gesture while the margin has it; message-local reaction strips need no claim.
export function syncReactLayout() {
  return reactArmed && reactSurface === marginSurface;
}

export function setReact(on, { surface = null, focusPicker = false } = {}) {
  if (on === reactArmed && (!on || surface === reactSurface || !surface)) return;
  if (on && claimsEsc(focused())) return;
  closeSurface(reactSurface);
  if (on) {
    reactFrom = focused();
    if (surface) reactSurface = surface;
    else {
      const said = standingConversation();
      const strip = said && latestAgentStrip(said.held);
      const here = !strip && !fabAnchorAt() && standingItem();
      if (strip) reactSurface = strip;
      else if (fabAnchorAt() || here) {
        if (here) {
          // The item may be represented by a docked row after its containing block,
          // with the target itself off screen. Keep the semantic anchor without
          // asking a floating bar to find geometry; the shared item is the surface.
          showFab({ section: here.id }, null, {
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
        notice("Select something to react to");
        return;
      }
    }
    if (!pickerFor(reactSurface)) {
      reactSurface = null;
      reactFrom = null;
      return;
    }
    reactArmed = true;
    if (reactSurface === fabBar) {
      const suggest = fabBar.querySelector(":scope > .lf-fab-suggest");
      if (suggest) suggest.hidden = !fabAnchorAt()?.quote || designOn;
    }
    reactSurface.classList.add("lf-react-open");
    if (reactSurface === fabBar) showFab(fabAnchorAt());
    pickerFor(reactSurface).trigger.setAttribute("aria-expanded", "true");
    const firstChoice =
      reactSurface === fabBar
        ? responseChoices(fabBar)[0]
        : pickerFor(reactSurface).palette.querySelector(".lf-react");
    if (focusPicker || (surface && reactFrom === pickerFor(reactSurface).trigger))
      firstChoice?.focus({
        preventScroll: true,
      });
    else if (reactFrom === pickerFor(fabBar)?.trigger)
      firstChoice?.focus({
        preventScroll: true,
      });
    announce(
      `${reactSurface === fabBar || reactSurface === marginSurface ? "Other responses" : "React"} — ${saying(REACT.rows)}`,
    );
  } else {
    const from = reactFrom;
    const closingFabChoices = reactSurface === fabBar;
    const trigger = pickerFor(reactSurface)?.trigger;
    const active = focused();
    reactArmed = false;
    reactSurface = null;
    reactFrom = null;
    if (reactRaised) showFab(null);
    reactRaised = false;
    lowerMarginSurface();
    if (fabAnchorAt()) showFab(fabAnchorAt());
    if (closingFabChoices && fabAnchorAt()) {
      fabBar.querySelector(".lf-fab-input")?.focus({ preventScroll: true });
    } else if (active?.closest?.(".lf-react-palette")) {
      const destination =
        from?.isConnected && from.checkVisibility?.()
          ? from
          : trigger?.checkVisibility?.()
            ? trigger
            : document.body;
      destination?.focus?.({ preventScroll: true });
    }
  }
  paintHere();
}

document.addEventListener("lf-button-options-closed", () => {
  if (reactArmed && reactSurface === marginSurface) setReact(false);
});
// A card the panel's narrowing hid keeps its node (thread-list.js), so a list open on
// one of its messages is still connected and still armed; the card going out of sight
// is the removal it always was to the reader.
document.addEventListener("lf-thread-hidden", (event) => {
  if (reactArmed && event.detail.node.contains(reactSurface)) setReact(false);
});

function responseChoices(surface) {
  if (!surface) return [];
  if (surface === marginSurface) return buttonChoices(fabTargetAt());
  return [
    ...surface.querySelectorAll(
      ":scope > .lf-response-action, :scope > .lf-margin-button, :scope > .lf-react-palette > .lf-react",
    ),
  ].filter((choice) => choice.checkVisibility());
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
  title: "With response choices open",
  // A modal may expose overflow from this same response interaction. Its native
  // focus walk and Escape own the keyboard until it closes; keep the anchor alive.
  at: () => reactArmed && !document.querySelector("dialog:modal"),
  claims: EVERYTHING,
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
      does: "Move through responses",
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
  buttonContextContains(fabTargetAt(), node);
