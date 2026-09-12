/* Server-projected interaction receipts and explicit work claims.

   `.lf-receipt` is transient runtime chrome for a subject with no page-edge margin entry.
   `paintAcknowledgmentsNow` is its one writer. An unsettled reader message carries the
   receipt in its existing metadata row; an event-backed widget frozen into conversation
   chrome keeps the full-width fallback beneath its owner. A claim with no preceding
   message uses that fallback too. Inline page conversations and page widgets use their
   target's existing margin cluster instead; an explicit page-widget claim is the
   cluster's **Active** reading. Every receipt wears `lf-ui` and `data-lf-gen`: it is an
   account of the conversation, not authored words, so selection and diff readings skip
   it. Reconcile widget state first and paint receipts afterward, so each receipt
   describes the state the widget now displays. Keep surviving nodes across state
   applications, and in their place, so an unchanged phase is not re-announced: a node
   taken out of the document and put back replays every animation it wears and
   re-announces its live region. A phase change updates words and semantic color with no
   motion. Its live state span changes only with semantic phase, detail, or the age
   carried by a past-active state; the separate age clock may repaint on a heartbeat
   without entering the live region. A newly
   constructed margin card uses the same writer on its detached subtree before display. */
import { ago } from "../presence.js";
import { el } from "../widget-elements.js";
import { runtime } from "../context.js";
import { agentWorkPhase } from "../updates.js";
import { elementById, inChrome, pageQueryAll } from "../passages.js";
import { threadList } from "./state.js";

const phaseText = (receipt) => {
  if (receipt.phase === "active") {
    const phase = receipt.quiet ? `● Was active ${ago(receipt.ts)}` : "● Active";
    return receipt.detail ? `${phase} — ${receipt.detail}` : phase;
  }
  if (receipt.phase === "queued") return "✓ Queued";
  if (receipt.phase === "picked_up")
    return receipt.dropped ? "○ Picked up · turn ended" : "✓ Picked up";
  if (receipt.phase === "waiting") return "○ Waiting for pickup";
  return "✓ Sent";
};

// One retained node follows one reader move through every semantic phase. Only a
// phase/detail change touches its live region; the heartbeat updates the separate
// clock without making a screen reader repeat the state every two seconds. A phase
// change is a change of words and paint and nothing else: motion here would answer
// a question the reader already asked, and an animation the line wore would replay
// on any move the heartbeat made (below).
function paintReceipt(host, receipt, before, wanted, metadata = false) {
  if (!host) return;
  let line = [...host.children].find(
    (child) => child.matches(".lf-receipt") && child.dataset.receiptId === receipt.id,
  );
  if (!line) {
    line = el(
      metadata ? "span" : "div",
      `lf-receipt lf-ui${metadata ? " lf-message-receipt" : ""}`,
    );
    line.dataset.lfGen = "1";
    line.dataset.receiptId = receipt.id;
    const state = el("span", "lf-receipt-state");
    state.setAttribute("role", "status");
    state.setAttribute("aria-live", "polite");
    state.setAttribute("aria-atomic", "true");
    line.append(state);
    if (!metadata) line.append(el("time"));
  }
  // `before` names the slot the line belongs in by the node standing there now, and
  // for an event-backed line that node is the line itself once it has been placed.
  // Inserting a node before itself is a move that changes nothing, but the platform
  // still takes it out of the document and puts it back — cancelling and restarting
  // every animation it wears, and re-announcing its live region — so a line already
  // in its slot is left where it stands.
  const next = before ?? null;
  if (next !== line && (line.parentElement !== host || line.nextSibling !== next))
    host.insertBefore(line, next);
  wanted.add(line);

  const state = line.querySelector(":scope > .lf-receipt-state");
  const semantic = phaseText(receipt);
  if (state.textContent !== semantic) state.textContent = semantic;
  if (state.title !== semantic) state.title = semantic;
  const workPhase = agentWorkPhase(receipt);
  line.classList.toggle("is-active", workPhase === "active");
  line.classList.toggle("is-picked-up", workPhase === "picked_up");
  line.dataset.lfPhase = receipt.phase;
  line.toggleAttribute("data-lf-dropped", Boolean(receipt.dropped));

  const time = line.querySelector(":scope > time");
  if (time) {
    const age = ago(receipt.ts);
    const shownAge = receipt.phase === "active" && receipt.quiet ? "" : age;
    if (time.textContent !== shownAge) time.textContent = shownAge;
  }
}

export function paintAcknowledgmentsNow(root = document) {
  const query = (selector) =>
    root === document ? pageQueryAll(selector) : [...root.querySelectorAll(selector)];
  const wanted = new Set();
  const receipts = runtime.activity?.interactions ?? [];
  for (const receipt of receipts) {
    const { kind, id } = receipt.target;
    if (kind === "thread") {
      const thread = threadList().find((candidate) => candidate.root.id === id);
      if (!thread || thread.resolved) continue;
      const views = query(
        `.lf-thread[data-id="${CSS.escape(id)}"], ` +
          `.lf-conversation-thread[data-thread="${CSS.escape(id)}"]`,
      );
      for (const view of views) {
        const source = receipt.event
          ? view.querySelector(
              `:scope > :is(.lf-msg[data-mid="${CSS.escape(receipt.event)}"], ` +
                `.lf-conversation-msg[data-event="${CSS.escape(receipt.event)}"])`,
            )
          : null;
        const messageHead = source?.querySelector(
          ":scope > :is(.lf-msg-head, .lf-conversation-head)",
        );
        paintReceipt(
          messageHead ?? view,
          receipt,
          messageHead
            ? null
            : view.querySelector(
                ":scope > :is(.lf-compose, .lf-say, .lf-thread-actions)",
              ),
          wanted,
          Boolean(messageHead),
        );
      }
      continue;
    }
    if (kind !== "widget") continue;
    if (receipt.revision > runtime.currentRevision) continue;
    const owner =
      root === document ? elementById(id) : root.querySelector(`#${CSS.escape(id)}`);
    // Frozen widgets sent in a message have no page edge of their own, so their
    // event-backed receipt remains local to the conversation. A page widget uses
    // its existing target margin entry instead of growing another row inside authored
    // content; standalone claims in chrome remain unsupported claim subjects.
    if (owner && receipt.event && inChrome(owner))
      paintReceipt(owner, receipt, null, wanted);
  }
  for (const line of query(".lf-receipt")) if (!wanted.has(line)) line.remove();
}
