import { marginAction, registerMarginItem } from "./living-margin.js";

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
  anchorLabel,
  announce,
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
  itemWord,
  offer,
  paintHere,
  post,
  reactionVocabulary,
  saying,
  showFab,
  showToast,
  standingConversation,
  standingItem,
  undoable,
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
  function reactPill(name, entry, pressed, { margin = false } = {}) {
    const pill = offer("button", `${margin ? "" : "lf-pill "}lf-react`);
    pill.dataset.token = name;
    pill.title = `${name} — ${entry.means}`;
    pill.setAttribute("aria-label", name);
    if (margin)
      marginAction(pill, {
        glyph: entry.glyph,
        label: name,
      });
    else
      pill.append(
        el("span", "lf-react-glyph", entry.glyph),
        el("span", "lf-react-word", name),
      );
    pill.onclick = () => pressed(name, pill);
    return pill;
  }

  const surfaces = new WeakMap();
  let surfaceOrdinal = 0;
  let marginSurface = null;
  let marginOffer = null;
  function buildReactSurface(
    surface,
    pressed,
    { label, target, marginActions = false },
  ) {
    if (!reactionTokens().length) return surface;
    surface.classList.add("lf-react-surface");
    const trigger = offer("button", "lf-pill lf-react-trigger", "…");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", "Show reactions");
    trigger.title = "Show reactions";
    const palette = el("span", "lf-react-palette");
    palette.id = `lf-reactions-${++surfaceOrdinal}`;
    palette.setAttribute("role", "group");
    palette.setAttribute("aria-label", label);
    trigger.setAttribute("aria-controls", palette.id);
    for (const [name, entry] of reactionTokens())
      palette.append(reactPill(name, entry, pressed, { margin: marginActions }));
    surface.append(trigger, palette);
    surfaces.set(surface, { palette, target, trigger });
    trigger.onclick = () => {
      if (surface === fabBar)
        setReact(!(reactArmed && reactSurface === marginSurface), {
          focusPicker: true,
        });
      else setReact(!(reactArmed && reactSurface === surface), { surface });
    };
    return surface;
  }

  function buildReactBar() {
    buildReactSurface(fabBar, reactHere, {
      label: "Reactions for this selection or item",
      target: () => anchorWord(fabAnchorAt()),
    });
    marginSurface = el("div", "lf-margin-reactions");
    marginSurface.setAttribute("role", "group");
    marginSurface.setAttribute("aria-label", "Comment or react");
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

  async function reactHere(name, pill) {
    const anchor = fabAnchorAt();
    const returnTo = fabReturnTo();
    if (!anchor) return;
    if (pill.lfReaction) {
      await withdraw(pill.lfReaction);
      seatCommentInBar(true);
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
    seatCommentInBar(true);
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
  let reactFrom = null;
  let reactSurface = null;
  const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
  const pickerFor = (surface) => surfaces.get(surface);

  function raiseMarginSurface() {
    const anchor = fabAnchorAt();
    const target = anchor && fabTargetAt();
    if (!marginSurface || !target) return false;
    const comment = fabBar.querySelector(":scope > .lf-fab");
    if (comment) {
      marginAction(comment, { glyph: "💬", label: "Comment" });
      marginSurface.prepend(comment);
    }
    fabBar.dataset.lfMarginRaised = "1";
    paintReactionStanding(
      marginSurface,
      [...fabBar.querySelectorAll(".lf-react[aria-pressed='true']")]
        .map((pill) => pill.lfReaction)
        .filter(Boolean),
    );
    marginOffer = registerMarginItem({
      target,
      controls: marginSurface,
      side: "after",
      // The choices borrow whatever RHS is available and dock as one item when it is
      // not. Reserving their temporary width would move the page the first time `r`
      // opened and leave that larger rail behind after the choices closed.
      claim: false,
    });
    return true;
  }

  function lowerMarginSurface() {
    marginOffer?.unregister();
    marginOffer = null;
    seatCommentInBar(false);
    delete fabBar.dataset.lfMarginRaised;
  }

  function seatCommentInBar(takeFocus) {
    const comment = marginSurface?.querySelector(":scope > .lf-fab");
    if (!comment) return;
    fabBar.prepend(comment);
    marginAction(comment, {
      glyph: "💬",
      label: "Comment",
      collapse: "always",
    });
    if (takeFocus) comment.focus({ preventScroll: true });
  }

  function closeSurface(surface) {
    surface?.classList.remove("lf-react-open");
    pickerFor(surface)?.trigger.setAttribute("aria-expanded", "false");
  }

  // A page picker lives in the shared margin item and therefore owns its geometry.
  // Returning true keeps the floating Comment bar from trying to re-place the same
  // gesture while the margin has it; message-local reaction strips need no such claim.
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
            showToast("That reaction target is no longer available");
            return;
          }
          reactSurface = marginSurface;
        } else {
          reactSurface = null;
          reactFrom = null;
          showToast("Select something to react to");
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
      if (focusPicker || (surface && reactFrom === pickerFor(reactSurface).trigger))
        pickerFor(reactSurface).palette.querySelector(".lf-react")?.focus({
          preventScroll: true,
        });
      else if (reactFrom === pickerFor(fabBar)?.trigger)
        pickerFor(reactSurface).palette.querySelector(".lf-react")?.focus({
          preventScroll: true,
        });
      announce(`React — ${saying(REACT.rows)}`);
    } else {
      const from = reactFrom;
      const trigger = pickerFor(reactSurface)?.trigger;
      const active = focused();
      reactArmed = false;
      reactSurface = null;
      reactFrom = null;
      if (reactRaised) showFab(null);
      reactRaised = false;
      lowerMarginSurface();
      if (fabAnchorAt()) showFab(fabAnchorAt());
      if (active?.closest?.(".lf-react-palette")) {
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

  function stepReaction(binding) {
    const pills = [
      ...(pickerFor(reactSurface)?.palette.querySelectorAll(".lf-react") ?? []),
    ];
    if (!pills.length) return;
    const at = pills.indexOf(focused());
    const backward = binding === "ArrowLeft" || binding === "ArrowUp";
    const next =
      at < 0
        ? backward
          ? pills.length - 1
          : 0
        : (at + (backward ? -1 : 1) + pills.length) % pills.length;
    pills[next].focus({ preventScroll: true });
  }

  const reactTargetWord = () =>
    typeof pickerFor(reactSurface)?.target === "function"
      ? pickerFor(reactSurface).target()
      : (pickerFor(reactSurface)?.target ?? "the target");

  const REACT = {
    title: "With r armed",
    at: () => reactArmed,
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
        keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
        does: "Move through reactions",
        line: "move",
        repeat: true,
        run: stepReaction,
      },
      {
        id: "reaction.activate",
        runFromReference: false,
        keys: ["Enter", "Space"],
        does: "Use the focused reaction",
        line: "choose",
        when: () => Boolean(focused()?.closest?.(".lf-react-palette .lf-react")),
        run: () => focused()?.click(),
      },
      {
        id: "reaction.cancel",
        keys: ["Escape"],
        does: "Put the reaction down",
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
    reactionTokens,
    sendReaction,
    setReact,
    syncReactLayout,
    undoSentence,
  };
}
