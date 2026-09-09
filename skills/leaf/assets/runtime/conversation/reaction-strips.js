/* This module owns the panel's message reaction surfaces, rendered in every complete
 * Thread view. */
import {
  buildReactSurface,
  paintReactionStanding,
  sendReaction,
  setReact,
} from "../reactions.js";
import { el } from "../widget-elements.js";
import { isAddressable, isReaction } from "./model.js";
import { withdraw } from "../projection.js";
import { runtime } from "../context.js";

// A reaction list owns the keyboard until it closes. Conversation reconciliation can
// remove its surface without a local gesture, so disarm it before detaching that tree.
export function removeConversationNode(node) {
  if (node.matches?.(".lf-react-open") || node.querySelector?.(".lf-react-open"))
    setReact(false);
  node.remove();
}

/* Reaction surfaces rendered in every complete Thread view.

   `paintReactStrips` puts one reaction surface on each agent message and marks the
   latest one `lf-open`, which makes it the thread's `r` target. A message reveals its
   overlaid add-reaction affordance on hover or keyboard focus. A closed surface shows
   only standing emoji; opening it floats the complete list below the trigger. A token
   press closes the list and returns focus to the trigger; any standing mark remains
   visible as its own eraser. */
// The strip on each agent message keeps the reader's standing marks visible and offers
// one overlaid trigger when that message is under the pointer or keyboard focus. A list
// opens only on the surface the reader chose.
// Rebuilt from the thread on each reconcile rather than from the press, so a reaction
// arriving from another tab and an undo land the same way. A resolved thread offers none.
export function paintReactStrips(node, t) {
  const latest = t.msgs.findLast((x) => x.author === "claude" && isAddressable(x))?.id;
  for (const msg of node.querySelectorAll(
    ":scope > .lf-msg, :scope > .lf-conversation-msg",
  )) {
    const m = t.msgs.find((x) => x.id === (msg.dataset.mid ?? msg.dataset.event));
    if (!m || m.author !== "claude" || !isAddressable(m)) {
      const strip = msg.querySelector(":scope > .lf-react-strip");
      if (strip) removeConversationNode(strip);
      continue;
    }
    let strip = msg.querySelector(":scope > .lf-react-strip");
    if (t.resolved) {
      if (strip) removeConversationNode(strip);
      continue;
    }
    if (!strip) {
      strip = el("div", "lf-react-strip");
      strip.setAttribute("role", "group");
      strip.setAttribute("aria-label", "React to this reply");
      buildReactSurface(strip, (name, chip) => pressStrip(m, name, chip), {
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

async function pressStrip(m, name, chip) {
  if (chip.lfReaction) await withdraw(chip.lfReaction);
  else
    await sendReaction(
      { kind: "reply", parent: m.id, revision: runtime.currentRevision, token: name },
      chip,
      `${m.agent || "the agent"}'s reply`,
    );
  setReact(false);
}
