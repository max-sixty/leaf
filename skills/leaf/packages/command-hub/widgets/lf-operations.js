/* One-shot host operations. The package declares the verbs; Leaf's kernel only
 * validates and transports request/receipt events. The event log is the whole
 * lifecycle: a request without its linked receipt is pending, and a receipt's
 * terminal status is the outcome. */
import {
  offer,
  once,
  quoted,
  registerDecisionActions,
  requestAvailable,
  sendRequest,
  watchRequestLifecycle,
} from "/runtime/widget-api.js";

const children = (holder) => [...holder.querySelectorAll(":scope > lf-operation")];

function title(option) {
  return (
    option.querySelector(":scope > strong")?.textContent.trim() ||
    option.getAttribute("verb").replaceAll("-", " ")
  );
}

function statusLine(holder, request, receipt) {
  const line = holder.querySelector(":scope > .lf-operation-status");
  if (!request) {
    line.hidden = true;
    line.textContent = "";
    return;
  }
  line.hidden = false;
  const operation = request.action.replaceAll("-", " ");
  line.textContent = receipt
    ? `${operation} ${receipt.status} · ${receipt.text}`
    : `${operation} requested · waiting for the host`;
  line.dataset.status = receipt?.status ?? "pending";
}

function paint(holder, lifecycle) {
  holder._lifecycle = lifecycle;
  const { request, receipt } = lifecycle.latest ?? {};
  const locked = holder._sending || lifecycle.phase !== "ready";
  for (const option of children(holder)) {
    const available = !locked && requestAvailable(holder, option.getAttribute("verb"));
    const selected = request?.action === option.getAttribute("verb");
    option.toggleAttribute("data-lf-requested", selected);
    const control = option.querySelector(":scope > .lf-operation-press");
    control.setAttribute("aria-disabled", String(!available));
    control.tabIndex = available ? 0 : -1;
  }
  statusLine(holder, request, receipt);
  holder._decisionActions?.update();
}

customElements.define(
  "lf-operations",
  class extends HTMLElement {
    connectedCallback() {
      if (!this._wired) {
        if (!once(this)) return;
        this._wired = true;
        // An exhibit preserves the authored operation and its consequences as
        // readable evidence, but offers no host door — the same quoted-material
        // boundary as every replayable input widget.
        if (quoted(this)) return;
        for (const option of children(this)) {
          const control = offer("button", "lf-operation-press", "Do this");
          control.setAttribute("aria-label", title(option));
          control.onclick = async () => {
            if (
              this._sending ||
              this._lifecycle.phase !== "ready" ||
              !requestAvailable(this, option.getAttribute("verb"))
            )
              return;
            this._sending = true;
            paint(this, this._lifecycle);
            const accepted = await sendRequest(this, option.getAttribute("verb"), {
              target: this.getAttribute("target"),
              worker: this.getAttribute("worker"),
              worktree: this.getAttribute("worktree"),
            });
            this._sending = false;
            if (!accepted) paint(this, this._lifecycle);
          };
          option.append(control);
        }
        const line = document.createElement("div");
        line.className = "lf-operation-status lf-ui";
        line.dataset.lfGen = "1";
        line.setAttribute("role", "status");
        line.hidden = true;
        this.append(line);
      }
      if (quoted(this)) return;
      if (!this._stop)
        this._stop = watchRequestLifecycle(this, (lifecycle) => paint(this, lifecycle));
      this._decisionActions ??= registerDecisionActions(this, () =>
        children(this).map((option) => ({
          control: option.querySelector(":scope > .lf-operation-press"),
          label: title(option),
        })),
      );
    }

    disconnectedCallback() {
      this._stop?.();
      this._stop = null;
    }
  },
);
