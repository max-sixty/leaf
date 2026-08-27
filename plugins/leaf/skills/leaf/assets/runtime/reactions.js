export function createReactions({
  CONTROL_WORD_CAP,
  EVERYTHING,
  anchorLabel,
  announce,
  beside,
  claimsEsc,
  commentsReveal,
  conversation,
  cut,
  designIsOn,
  el,
  elementById,
  fab,
  fabAnchorAt,
  fabBar,
  focused,
  itemWord,
  offer,
  paintHere,
  post,
  registry,
  runtime,
  saying,
  showFab,
  shownBox,
  shownRect,
  standingConversation,
  standingItem,
  undoable,
  visualPartLabel,
  withdraw,
}) {
  // The layer's reaction vocabulary, in declared order. The bar, a thread's strip, the
  // page row and the armed digits all read this one list, so a layer that renames, adds
  // or removes a token moves every surface at once, and core never learns a token's name:
  // what a press means is the entry's `means`, printed to the agent by `leaf wait`, and
  // what it does structurally is the entry's own flag (`settles`, read by the panel).
  // Empty until the registry has arrived: the register checks every core row's bindings
  // as the module evaluates, which is before the vocabulary is known.
  const reactionTokens = () => Object.entries(registry.$reactions?.tokens ?? {});
  // One token as a press, built the same way wherever it stands — the bar beside a
  // selection, the strip under a message, the panel's page row. The digit is the address
  // the armed mode paints (the chip an option wears while its mark holds focus) and shows
  // only while armed; the word shows only while the token stands on its target, so a strip
  // reads "✓ ok" where the reader pressed and a bare glyph everywhere else. The chip is
  // aria-hidden the way the key line's are: the announcement made on arming says the keys.
  function reactPill(name, entry, ordinal, pressed) {
    const pill = offer("button", "lf-pill lf-react");
    pill.dataset.token = name;
    pill.title = `${name} — ${entry.means}`;
    pill.setAttribute("aria-label", name);
    const digit = el("span", "lf-address", String(ordinal));
    digit.setAttribute("aria-hidden", "true");
    pill.append(
      digit,
      el("span", "lf-react-glyph", entry.glyph),
      el("span", "lf-react-word", name),
    );
    pill.onclick = () => pressed(name, pill);
    return pill;
  }
  const reactPills = (pressed) =>
    reactionTokens().map(([name, entry], i) => reactPill(name, entry, i + 1, pressed));
  function buildReactBar() {
    for (const pill of reactPills(reactHere)) fabBar.insertBefore(pill, fab);
  }
  // What the bar's target is called, for the line, the reference and the announcement:
  // the selection, a declared visual part by its own label, or the item by its own word.
  const anchorWord = (anchor) => {
    if (anchor.quote) return "the selection";
    const item = elementById(anchor.section);
    if (anchor.visual) return visualPartLabel(item, anchor.visual) ?? anchor.visual;
    return itemWord(item) || "the item";
  };
  // A reaction aimed where the bar is: a comment carrying a token in place of words, on
  // the same anchor a comment from here would carry — the passage a selection named or
  // the item the bar was raised on — so the file meets it the way it meets a comment.
  // Design mode makes it about the layer, as it does a comment. Sent, the bar and the
  // selection stand down: the mark on the passage is the receipt, and a selection left
  // standing would cover it.
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
      revision: runtime.currentRevision,
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
  // One send for every reaction surface. A press whose result has not changed the DOM
  // waits for the log — the outbox's rule — so the pill says busy for the round trip and
  // the paint arrives with the accepted state. Announced, because the paint is silent.
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

  // The armed react press: `r` puts a digit on every token of one surface, and the digit
  // sends. Digits rather than letters because the vocabulary is configuration — a letter
  // spelled from a token's word breaks the day a layer replaces it, where position
  // survives any set. The surface is whichever strip of pills the reader's place names:
  // the strip under the latest agent message where they are standing in a thread; the bar,
  // where one stands or can be raised on the item they are standing on; and the panel's
  // page strip where nothing stands, the page whole being what an anchorless reaction is
  // aimed at. Armed, the mode owns the keys (REACT claims everything, as the address chord
  // does); Escape or a stray key lets it go, and what the arming raised — the bar, or the
  // panel — goes down with it, unless a digit spent it, which is the reader landing in
  // what the arming showed (the chord's `keepShown`).
  let reactArmed = false;
  let reactRaised = false;
  let reactRevealed = null;
  let reactSurface = null;
  // The strip the panel has open — the latest agent message's — asked of the class the
  // list paints it with rather than of DOM order, so arming and offering cannot disagree
  // about which message is the latest one.
  const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
  function setReact(on, { spent = false } = {}) {
    if (on === reactArmed) return;
    // Armed over a control that has claimed Escape, one press would have two owners, so
    // the mode refuses to arm there — the chord's own rule.
    if (on && claimsEsc(focused())) return;
    reactSurface?.classList.remove("lf-armed");
    if (on) {
      const said = standingConversation();
      const strip = said && latestAgentStrip(said.held);
      const here = !strip && !fabAnchorAt() && standingItem();
      if (strip) reactSurface = strip;
      else if (fabAnchorAt() || here) {
        if (here) {
          showFab(
            { section: here.id },
            ...beside(shownRect(here, new Map()) ?? shownBox(here)),
          );
          reactRaised = true;
        }
        reactSurface = fabBar;
      } else {
        reactSurface = conversation().pageStrip;
        if (!reactSurface) return;
        reactRevealed = commentsReveal();
      }
      reactArmed = true;
      reactSurface.classList.add("lf-armed");
      announce(`React — ${saying(REACT.rows)}`);
    } else {
      reactArmed = false;
      reactSurface = null;
      if (reactRaised) showFab(null);
      if (!spent) reactRevealed?.();
      reactRaised = false;
      reactRevealed = null;
    }
    paintHere();
  }
  const reactTargetWord = () =>
    reactSurface === fabBar
      ? anchorWord(fabAnchorAt())
      : reactSurface === conversation().pageStrip
        ? "the page"
        : "the reply";
  // The armed react press's own scope: the digits, and the way out. It claims everything
  // for the reason the chord does — a digit pressed while it stands belongs to it wherever
  // focus sits — and, as with the chord, any key it does not bind disarms it and keeps its
  // ordinary meaning (the dispatcher).
  const REACT = {
    title: "With r armed",
    at: () => reactArmed,
    claims: EVERYTHING,
    rows: [
      {
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
          // The surface's own pill, pressed: keyboard and pointer are one behaviour,
          // the busy paint and the announcement included.
          reactSurface?.querySelectorAll(".lf-react")[+binding - 1]?.click();
          setReact(false, { spent: true });
        },
      },
      {
        keys: ["Escape"],
        does: "Put the reaction down",
        line: "cancel",
        run: () => setReact(false),
      },
    ],
  };

  // The z row's sentence for a reaction: the token and where it stands, so the line is
  // the receipt after the press and the promise before the next.
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
    isReactArmed: () => reactArmed,
    reactPills,
    reactionTokens,
    sendReaction,
    setReact,
    undoSentence,
  };
}
