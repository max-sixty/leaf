/* This module owns the panel's message reaction surfaces, rendered in every complete
 * Thread view. */
import {
  buildReactSurface,
  paintReactionStanding,
  sendReaction,
} from "../reactions.js";
import { el } from "../widget-elements.js";
import { isReaction } from "./model.js";
import { withdraw } from "../projection.js";
import { runtime } from "../context.js";
import { reactDone, removeNode } from "./reconcile.js";

/* Reaction surfaces rendered in every complete Thread view.

   `paintReactStrips` puts one reaction surface on each agent message and marks the
   latest one `lf-open`, which makes it the thread's `r` target. A message reveals its
   overlaid add-reaction affordance on hover or keyboard focus. A closed surface shows
   only standing emoji; opening it replaces the trigger with the complete list. A token
   press closes the list and
   returns focus to the trigger; any standing mark remains visible as its own eraser. */
// The strip on each agent message keeps the reader's standing marks visible and offers
// one overlaid trigger when that message is under the pointer or keyboard focus. A list
// opens only on the surface the reader chose.
// Rebuilt from the thread on each reconcile rather than from the press, so a reaction
// arriving from another tab and an undo land the same way. A resolved thread offers none.
export function paintReactStrips(node, t) {
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
