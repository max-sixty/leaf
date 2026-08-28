import { paintReactionStanding } from "../reactions.js";

/* Reaction surfaces rendered in the comment panel. */
export function createConversationReactionStrips(dependencies) {
  const {
    bareReaction,
    designIsOn,
    el,
    generalRow,
    isReaction,
    reactDone,
    reactPills,
    registry,
    runtime,
    sendReaction,
    withdraw,
  } = dependencies;

  // The strip under each of the agent's messages: every token the layer declares, the
  // ones the reader has put on that message reading pressed and wearing their word.
  // Press one to put it there — a reply carrying the token, on that message — and press it
  // again to take it back, an ordinary undo naming the reply. Rebuilt from the thread on
  // each reconcile rather than from the press, so a reaction arriving from another tab,
  // and an undo, land the same way. A resolved thread offers none: resolve is the floor
  // after which a reaction stops painting, on the page and here alike.
  // Open — every token offered — on the latest agent message, which is the one `r`
  // arms and the one a `settles` token answers. The rest of the thread keeps the tokens
  // standing on it and offers its own row only while the reader is standing in the
  // thread (the stylesheet), so a thread at rest wears one row rather than one a turn.
  function paintReactStrips(node, t) {
    const latest = t.msgs.findLast((x) => x.author === "claude")?.id ?? null;
    for (const msg of node.querySelectorAll(":scope > .lf-msg")) {
      const m = t.msgs.find((x) => x.id === msg.dataset.mid);
      if (!m || m.author !== "claude") continue;
      let strip = msg.querySelector(":scope > .lf-react-strip");
      if (t.resolved) {
        strip?.remove();
        continue;
      }
      if (!strip) {
        strip = el("div", "lf-react-strip");
        strip.setAttribute("role", "group");
        strip.setAttribute("aria-label", "React to this reply");
        for (const pill of reactPills((name, pill) => pressStrip(m, name, pill)))
          strip.append(pill);
        msg.append(strip);
      }
      strip.classList.toggle("lf-open", m.id === latest);
      paintReactionStanding(
        strip,
        t.msgs.filter((x) => isReaction(x) && x.author === "user" && x.parent === m.id),
      );
    }
  }

  async function pressStrip(m, name, pill) {
    if (pill.lfReaction) await withdraw(pill.lfReaction);
    else
      await sendReaction(
        { kind: "reply", parent: m.id, revision: runtime.currentRevision, token: name },
        pill,
        `${m.agent || "the agent"}'s reply`,
      );
    reactDone();
  }

  // The page whole, from the panel: the same strip, above the general box, aimed at
  // nothing in particular — the shape an unanchored comment already has. What stands
  // here is every bare reaction with no anchor; a press puts one there or takes it back.
  let pageStrip = null;
  function paintPageStrip(threads) {
    if (!Object.keys(registry.$reactions.tokens).length) return;
    if (!pageStrip) {
      pageStrip = el("div", "lf-react-strip lf-page-strip lf-open");
      pageStrip.setAttribute("role", "group");
      pageStrip.setAttribute("aria-label", "React to the page");
      for (const pill of reactPills(pressPage)) pageStrip.append(pill);
      generalRow.before(pageStrip);
    }
    paintReactionStanding(
      pageStrip,
      threads
        .filter((t) => bareReaction(t) && !t.resolved && !t.root.anchor)
        .map((t) => t.root),
    );
  }

  // About the layer in design mode, as the general box's own comment is: the subject is
  // decided at the send, by the mode standing then.
  async function pressPage(name, pill) {
    if (pill.lfReaction) {
      await withdraw(pill.lfReaction);
      reactDone();
      return;
    }
    const event = { kind: "comment", revision: runtime.currentRevision, token: name };
    if (designIsOn()) event.about = "layer";
    await sendReaction(event, pill, "the page");
    reactDone();
  }

  return {
    paintPageStrip,
    paintReactStrips,
    get pageStrip() {
      return pageStrip;
    },
  };
}
