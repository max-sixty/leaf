/* Server-projected interaction receipts and explicit work claims.

   `paintAcknowledgmentsNow` is the one writer of `.lf-receipt`. A thread interaction
   carries its receipt in the source message's existing metadata row. An eventless thread
   claim belongs to the root message that identifies the thread, while an event-backed
   widget frozen into conversation chrome uses the metadata row of the message that owns
   it. Inline page conversations and page widgets use their target's existing margin
   cluster instead; an explicit page-widget claim is the cluster's **Active** reading.
   Every receipt wears `lf-ui` and `data-lf-gen`: it is an account of the conversation,
   not authored words, so selection and diff readings skip it. Reconcile widget state
   first and paint receipts afterward, so each receipt describes the state the widget
   now displays. Keep surviving nodes across state
   applications, and in their place, so an unchanged phase is not re-announced: a node
   taken out of the document and put back replays every animation it wears and
   re-announces its live region. A phase change updates words and semantic color with no
   motion. Its live state span changes only with semantic phase, detail, or the rounded
   age carried by a past-active state. A newly constructed margin card uses the same
   writer on its detached subtree before display. */
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
// phase, detail, or rounded-age change touches its live region, so the heartbeat does
// not make a screen reader repeat an unchanged state every two seconds. A semantic
// change is a change of words and paint and nothing else: motion here would answer
// a question the reader already asked, and an animation the line wore would replay
// on any move the heartbeat made (below).
function paintReceipt(host, receipt, wanted) {
  if (!host) return;
  let line = [...host.children].find(
    (child) => child.matches(".lf-receipt") && child.dataset.receiptId === receipt.id,
  );
  if (!line) {
    line = el("span", "lf-receipt lf-ui lf-message-receipt");
    line.dataset.lfGen = "1";
    line.dataset.receiptId = receipt.id;
    const state = el("span", "lf-receipt-state");
    state.setAttribute("role", "status");
    state.setAttribute("aria-live", "polite");
    state.setAttribute("aria-atomic", "true");
    line.append(state);
  }
  // Leave a receipt already at the end of its metadata row where it stands. Removing
  // and reinserting it would restart any animation and re-announce its live region.
  if (line.parentElement !== host || line.nextSibling !== null) host.append(line);
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
        const message = (event) =>
          view.querySelector(
            `:scope > :is(.lf-msg[data-mid="${CSS.escape(event)}"], ` +
              `.lf-conversation-msg[data-event="${CSS.escape(event)}"])`,
          );
        const source = (receipt.event ? message(receipt.event) : null) ?? message(id);
        const messageHead = source?.querySelector(
          ":scope > :is(.lf-msg-head, .lf-conversation-head)",
        );
        paintReceipt(messageHead, receipt, wanted);
      }
      continue;
    }
    if (kind !== "widget") continue;
    if (receipt.revision > runtime.currentRevision) continue;
    const owner =
      root === document ? elementById(id) : root.querySelector(`#${CSS.escape(id)}`);
    // A frozen widget sent in a message has no page edge of its own, so its event-backed
    // receipt uses that message's metadata. A page widget uses its existing target margin
    // entry; standalone claims in chrome remain unsupported claim subjects.
    const message = owner?.closest(":is(.lf-msg, .lf-conversation-msg)");
    const messageHead = message?.querySelector(
      ":scope > :is(.lf-msg-head, .lf-conversation-head)",
    );
    if (owner && receipt.event && inChrome(owner))
      paintReceipt(messageHead, receipt, wanted);
  }
  for (const line of query(".lf-receipt")) if (!wanted.has(line)) line.remove();
}
