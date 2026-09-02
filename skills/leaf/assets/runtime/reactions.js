import { iconElement, marginAction, registerMarginItem } from "./living-margin.js";

// The anchored response bar has one control grammar of its own. Its buttons share the
// field's type, border, height, and floating elevation without claiming to be target-
// margin actions. The repeated anatomy lets Comment, Suggest, and package reactions
// change vocabulary without each inventing a button shape.
export function responseAction(
  control,
  { glyph = null, icon = null, label, behavior = "action", collapse = false },
) {
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A response action needs exactly one glyph or icon");
  control.classList.add("lf-response-control", "lf-response-action");
  control.dataset.lfBehavior = behavior;
  control.toggleAttribute("data-lf-collapse", collapse);
  if (behavior !== "action" && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (behavior === "action") control.removeAttribute("aria-expanded");
  const glyphNode = icon ? iconElement(icon) : document.createElement("span");
  if (!icon) {
    glyphNode.className = "lf-response-action-glyph";
    glyphNode.setAttribute("aria-hidden", "true");
    glyphNode.textContent = glyph;
  }
  const spaceNode = document.createElement("span");
  spaceNode.className = "lf-response-action-space";
  spaceNode.setAttribute("aria-hidden", "true");
  spaceNode.textContent = " ";
  const labelNode = document.createElement("span");
  labelNode.className = "lf-response-action-label";
  labelNode.textContent = label;
  control.replaceChildren(glyphNode, spaceNode, labelNode);
  if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
  return control;
}

// Which tokens stand on a target, painted on its strip: pressed, wearing the word, and
// carrying the event a second press takes back. The reaction rides the pill rather than
// a map beside it, so a reconcile that keeps the node keeps the fact with it.
export function paintReactionStanding(strip, standing) {
  const by = new Map(standing.map((x) => [x.token, x]));
  for (const pill of strip.querySelectorAll(":scope > .lf-react-palette > .lf-react")) {
    const on = by.get(pill.dataset.token) ?? null;
    pill.setAttribute("aria-pressed", on ? "true" : "false");
    pill.lfReaction = on;
  }
}

export function createReactions({
  CONTROL_WORD_CAP,
  EVERYTHING,
  PRESS,
  anchorLabel,
  announce,
  buttonChoices,
  buttonContextContains,
  claimsEsc,
  currentRevision,
  cut,
  designIsOn,
  el,
  elementById,
  fabAnchorAt,
  fabTargetAt,
  fabReturnTo,
  fabBar,
  focused,
  hideComposer,
  foldButtonOptions,
  itemWord,
  offer,
  openButtonOptions,
  paintHere,
  post,
  reactionVocabulary,
  saying,
  showFab,
  notice,
  standingConversation,
  standingItem,
  suggestHere,
  undoable,
  unfoldedButtons,
  visualPartLabel,
  withdraw,
}) {
  // The layer's reaction vocabulary, in declared order. The bar, a reply's strip, the
  // page row and the keyboard accelerators all read this one list, so a layer that
  // renames, adds or removes a token moves every surface at once, and core never learns
  // a token's name. Empty until the registry has arrived: the register checks every core
  // row's bindings as the module evaluates, before the vocabulary is known.
  const reactionTokens = () => Object.entries(reactionVocabulary() ?? {});

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
      marginAction(pill, {
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
  let marginSuggest = null;
  function buildReactSurface(
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
      floatingResponses ? "" : "…",
    );
    if (floatingResponses)
      responseAction(trigger, {
        icon: "more",
        label: "Other responses",
        behavior: "options",
        collapse: true,
      });
    trigger.setAttribute("aria-expanded", "false");
    const showLabel = triggerLabel ?? "Show reactions";
    trigger.setAttribute("aria-label", showLabel);
    trigger.title = showLabel;
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

  function buildReactBar() {
    const fabSuggest = responseAction(offer("button", "lf-fab-suggest"), {
      icon: "edit",
      label: "Suggest",
      behavior: "disclosure",
    });
    fabSuggest.onclick = () => {
      if (!fabAnchorAt()?.quote || designIsOn()) return;
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
    marginSuggest = marginAction(offer("button", "lf-fab-suggest"), {
      key: "suggest",
      icon: "edit",
      label: "Suggest",
      behavior: "disclosure",
      role: "secondary",
    });
    marginSuggest.onclick = () => {
      if (!fabAnchorAt()?.quote || designIsOn()) return;
      setReact(false);
      suggestHere();
    };
    const marginComment = marginAction(offer("button", "lf-fab"), {
      key: "comment",
      icon: "comment",
      label: "Comment",
      behavior: "disclosure",
      role: "primary",
    });
    marginComment.onclick = () => {
      setReact(false);
      fabBar.querySelector(":scope > .lf-fab")?.click();
    };
    marginSurface.append(marginComment, marginSuggest);
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
      revision: currentRevision(),
      token: name,
      anchor: structuredClone(anchor),
    };
    if (designIsOn()) event.about = "layer";
    const sent = await sendReaction(event, pill, anchorWord(anchor));
    if (!sent) return;
    hideComposer();
    showFab(null);
    setReact(false);
    if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
    getSelection()?.removeAllRanges();
  }

  async function sendReaction(event, pill, where) {
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
  // Threads alone. Page-wide reactions remain an explicit surface inside that panel.
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
    marginSuggest.hidden = !anchor.quote || designIsOn();
    fabBar.dataset.lfMarginRaised = "1";
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
  function syncReactLayout() {
    return reactArmed && reactSurface === marginSurface;
  }

  function setReact(on, { surface = null, focusPicker = false } = {}) {
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
        if (suggest) suggest.hidden = !fabAnchorAt()?.quote || designIsOn();
      }
      reactSurface.classList.add("lf-react-open");
      if (reactSurface === fabBar) showFab(fabAnchorAt());
      pickerFor(reactSurface).trigger.setAttribute("aria-expanded", "true");
      const firstChoice =
        reactSurface === fabBar
          ? responseChoices(fabBar)[0]
          : reactSurface === marginSurface && !marginSuggest.hidden
            ? marginSuggest
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

  function responseChoices(surface) {
    if (!surface) return [];
    if (surface === marginSurface) return buttonChoices(fabTargetAt());
    return [
      ...surface.querySelectorAll(
        ":scope > .lf-response-action, :scope > .lf-margin-action, :scope > .lf-react-palette > .lf-react",
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

  const REACT = {
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
  const undoSentence = () => {
    const event = undoable();
    return event?.token
      ? `Take back: ${event.token} on ${reactionPlace(event)}`
      : "Take back the last change you made here";
  };

  return {
    REACT,
    buildReactBar,
    buildReactSurface,
    isReactArmed: () => reactArmed,
    reactionContextContains: (node) =>
      reactArmed &&
      reactSurface === marginSurface &&
      buttonContextContains(fabTargetAt(), node),
    reactionTokens,
    sendReaction,
    setReact,
    syncReactLayout,
    undoSentence,
  };
}
