/* Immutable interaction-receipt readings and their retained Lit presentation.

   Thread receipts belong to their displayed source message, falling back to the root;
   event-backed widget receipts use membership captured from that message's validated
   authored fragment. Page-widget receipts remain with the page's margin projection.
   Message templates exclusively place keyed receipt nodes. Visible wording may age,
   while the separate live region changes only with semantic phase or detail. */
import { ago } from "../presence.js";
import { agentWorkflowStage } from "../updates.js";
import { turns } from "./model.js";
import { LitElement, html } from "../../vendor/browser-runtime.js";

const phaseText = (receipt, includeAge = true) => {
  const workflowStage = agentWorkflowStage(receipt);
  if (["working", "was_working"].includes(workflowStage)) {
    const phase =
      workflowStage === "was_working"
        ? `● Was working${includeAge ? ` ${ago(receipt.ts)}` : ""}`
        : "● Working";
    return receipt.detail ? `${phase} — ${receipt.detail}` : phase;
  }
  if (workflowStage === "queued") return "✓ Queued";
  if (workflowStage === "picked_up") return "✓ Picked up";
  if (workflowStage === "picked_up_ended") return "○ Picked up · turn ended";
  if (workflowStage === "waiting") return "○ Waiting for pickup";
  return "✓ Sent";
};

const RECEIPT_TAG = "leaf-interaction-receipt";

class InteractionReceipt extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  constructor() {
    super();
    this.model = null;
  }

  createRenderRoot() {
    return this;
  }

  present(model) {
    this.model = model;
    this.performUpdate();
  }

  updated() {
    this.classList.toggle("is-working", this.model.workflowStage === "working");
    this.classList.toggle("is-picked-up", this.model.workflowStage === "picked_up");
    this.dataset.lfPhase = this.model.phase;
    this.toggleAttribute("data-lf-dropped", this.model.dropped);
  }

  render() {
    if (!this.model) return null;
    return html`
      <span class="lf-receipt-state" aria-hidden="true" title=${this.model.semantic}
        >${this.model.semantic}</span
      >
      <span class="lf-receipt-live" role="status" aria-live="polite" aria-atomic="true"
        >${this.model.announced}</span
      >
    `;
  }
}

if (!customElements.get(RECEIPT_TAG))
  customElements.define(RECEIPT_TAG, InteractionReceipt);

export const receiptReading = (receipt) =>
  Object.freeze({
    id: receipt.id,
    announced: phaseText(receipt, false),
    dropped: Boolean(receipt.dropped),
    phase: receipt.phase,
    semantic: phaseText(receipt),
    workflowStage: agentWorkflowStage(receipt),
  });

// Membership comes from the gate-validated frozen fragment, never from the live DOM.
export function messageReceipts(thread, message, widgets, interactions, revision) {
  return Object.freeze(
    interactions
      .filter((receipt) => {
        if (receipt.target.kind === "thread") {
          if (thread.resolved || receipt.target.id !== thread.root.id) return false;
          const source = turns(thread).some((item) => item.id === receipt.event)
            ? receipt.event
            : thread.root.id;
          return source === message.id;
        }
        return (
          receipt.target.kind === "widget" &&
          receipt.event &&
          receipt.revision <= revision &&
          widgets.includes(receipt.target.id)
        );
      })
      .map(receiptReading),
  );
}

export function createReceipt() {
  const node = document.createElement(RECEIPT_TAG);
  node.className = "lf-receipt lf-ui lf-message-receipt";
  node.dataset.lfGen = "1";
  return node;
}
