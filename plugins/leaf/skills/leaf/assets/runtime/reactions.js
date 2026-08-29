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
  BANNER_CLEAR,
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
  function reactPill(name, entry, pressed) {
    const pill = offer("button", "lf-pill lf-react");
    pill.dataset.token = name;
    pill.title = `${name} — ${entry.means}`;
    pill.setAttribute("aria-label", name);
    pill.append(
      el("span", "lf-react-glyph", entry.glyph),
      el("span", "lf-react-word", name),
    );
    pill.onclick = () => pressed(name, pill);
    return pill;
  }

  const surfaces = new WeakMap();
  let surfaceOrdinal = 0;
  function buildReactSurface(surface, pressed, { label, target }) {
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
      palette.append(reactPill(name, entry, pressed));
    surface.append(trigger, palette);
    surfaces.set(surface, { palette, target, trigger });
    trigger.onclick = () =>
      setReact(!(reactArmed && reactSurface === surface), { surface });
    return surface;
  }

  function buildReactBar() {
    buildReactSurface(fabBar, reactHere, {
      label: "Reactions for this selection or item",
      target: () => anchorWord(fabAnchorAt()),
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
    if (!anchor) return;
    if (pill.lfReaction) {
      await withdraw(pill.lfReaction);
      showFab(null);
      setReact(false);
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
    showFab(null);
    setReact(false);
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
  // Comments alone. Page-wide reactions remain an explicit surface inside that panel.
  let reactArmed = false;
  let reactRaised = false;
  let reactFrom = null;
  let reactSurface = null;
  const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
  const pickerFor = (surface) => surfaces.get(surface);

  function closeSurface(surface) {
    surface?.classList.remove("lf-react-open");
    pickerFor(surface)?.trigger.setAttribute("aria-expanded", "false");
  }

  function placePalette(surface) {
    if (surface !== fabBar) return;
    const palette = pickerFor(surface)?.palette;
    if (!palette) return;
    surface.classList.remove("lf-react-above", "lf-react-stacked");
    palette.style.transform = "";
    let bar = fabBar.getBoundingClientRect();
    if (
      !document.body.hasAttribute("data-lf-panel") &&
      bar.left >= 8 &&
      bar.right <= innerWidth - 8
    )
      return;
    surface.classList.add("lf-react-stacked");
    let box = palette.getBoundingClientRect();
    const shift = Math.max(8 - box.left, Math.min(0, innerWidth - 8 - box.right));
    if (shift) palette.style.transform = `translateX(${shift}px)`;
    box = palette.getBoundingClientRect();
    bar = fabBar.getBoundingClientRect();
    if (box.bottom > innerHeight - 8 && bar.top - box.height - 6 >= BANNER_CLEAR)
      surface.classList.add("lf-react-above");
  }

  // Growing the compact surface is not a new target, so keep Comment fixed while only
  // placing the list. Layout calls this before it would reanchor the bar.
  function syncReactLayout() {
    if (!reactArmed || reactSurface !== fabBar) return false;
    placePalette(fabBar);
    return true;
  }

  function setReact(on, { surface = null } = {}) {
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
            showFab({ section: here.id });
            reactRaised = true;
          }
          reactSurface = fabBar;
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
      placePalette(reactSurface);
      if (surface && reactFrom === pickerFor(reactSurface).trigger)
        pickerFor(reactSurface).palette.querySelector(".lf-react")?.focus({
          preventScroll: true,
        });
      announce(`React — ${saying(REACT.rows)}`);
    } else {
      const from = reactFrom;
      const trigger = pickerFor(reactSurface)?.trigger;
      reactArmed = false;
      reactSurface = null;
      reactFrom = null;
      if (reactRaised) showFab(null);
      reactRaised = false;
      const active = focused();
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
