import { paintReactionStanding } from "../reactions.js";

/* Reaction surfaces rendered in every complete Thread view. */
export function createConversationReactionStrips(dependencies) {
  const {
    bareReaction,
    buildReactSurface,
    designIsOn,
    el,
    generalRow,
    isReaction,
    reactDone,
    removeNode,
    registry,
    runtime,
    sendReaction,
    withdraw,
  } = dependencies;

  // The strip under each agent message keeps the reader's standing marks visible and
  // offers one ellipsis. The latest reply offers it at rest; older replies reveal theirs
  // while the reader is in the thread. A list opens only on the surface the reader chose.
  // Rebuilt from the thread on each reconcile rather than from the press, so a reaction
  // arriving from another tab and an undo land the same way. A resolved thread offers none.
  function paintReactStrips(node, t) {
    const latest = t.msgs.findLast((x) => x.author === "claude")?.id ?? null;
    for (const msg of node.querySelectorAll(
      ":scope > .lf-msg, :scope > .lf-conversation-msg",
    )) {
      const m = t.msgs.find((x) => x.id === (msg.dataset.mid ?? msg.dataset.event));
      if (!m || m.author !== "claude") continue;
      let strip = msg.querySelector(":scope > .lf-react-strip");
      if (t.resolved) {
        if (strip) removeNode(strip);
        continue;
      }
      if (!strip) {
        strip = el("div", "lf-react-strip");
        strip.setAttribute("role", "group");
        strip.setAttribute("aria-label", "React to this reply");
        buildReactSurface(strip, (name, pill) => pressStrip(m, name, pill), {
          label: "Reactions for this reply",
          target: "the reply",
        });
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
      pageStrip = el("div", "lf-react-strip lf-page-strip");
      pageStrip.setAttribute("role", "group");
      pageStrip.setAttribute("aria-label", "React to the page");
      buildReactSurface(pageStrip, pressPage, {
        label: "Reactions for the page",
        target: "the page",
      });
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
