/* A release operation is a durable host request, not local page state. The package
 * owns the verb and presentation; Leaf validates and transports the request/receipt
 * lifecycle without pretending a button press completed the deployment operation. */
import {
  commands,
  offer,
  once,
  quoted,
  requestAvailable,
  sendRequest,
  watchRequestLifecycle,
} from "/runtime/widget-api.js";

const actions = (holder) => [...holder.querySelectorAll(":scope > lf-release-action")];

const title = (action) =>
  action.querySelector(":scope > strong")?.textContent.trim() ||
  action.getAttribute("verb").replaceAll("-", " ");

function paint(holder, lifecycle) {
  holder._lifecycle = lifecycle;
  const { request, receipt } = lifecycle.latest ?? {};
  const locked = holder._sending || lifecycle.phase !== "ready";
  for (const action of actions(holder)) {
    const verb = action.getAttribute("verb");
    const control = action.querySelector(":scope > .lf-release-action-press");
    const selected = request?.action === verb;
    action.toggleAttribute("data-lf-requested", selected);
    control.setAttribute(
      "aria-disabled",
      String(locked || !requestAvailable(holder, verb)),
    );
    control.tabIndex = locked || !requestAvailable(holder, verb) ? -1 : 0;
  }

  const status = holder.querySelector(":scope > .lf-release-action-status");
  if (!request) {
    status.hidden = true;
    status.textContent = "";
    return;
  }
  status.hidden = false;
  status.dataset.status = receipt?.status ?? "pending";
  status.textContent = receipt
    ? `Rollback ${receipt.status} · ${receipt.text}`
    : "Rollback requested · waiting for the host";
}

customElements.define(
  "lf-release-actions",
  class extends HTMLElement {
    connectedCallback() {
      if (!this._wired) {
        if (!once(this)) return;
        this._wired = true;
        if (quoted(this)) return;
        for (const action of actions(this)) {
          const control = offer("button", "lf-btn lf-release-action-press", "Request");
          const label = title(action);
          control.setAttribute("aria-label", label);
          control.onclick = async () => {
            const verb = action.getAttribute("verb");
            if (
              this._sending ||
              this._lifecycle.phase !== "ready" ||
              !requestAvailable(this, verb)
            )
              return;
            this._sending = true;
            paint(this, this._lifecycle);
            const accepted = await sendRequest(this, verb, {
              candidate: this.getAttribute("candidate"),
              stable: this.getAttribute("stable"),
            });
            this._sending = false;
            if (!accepted) paint(this, this._lifecycle);
          };
          action.append(control);
        }
        commands(
          this,
          "On a release",
          actions(this).map((action) => {
            const control = action.querySelector(":scope > .lf-release-action-press");
            const label = title(action);
            return {
              id: `release.${action.getAttribute("verb")}`,
              keys: [],
              control,
              decision: label,
              does: label,
              line: label.toLowerCase(),
              run: () => control.click(),
            };
          }),
        );
        const status = document.createElement("div");
        status.className = "lf-release-action-status lf-ui";
        status.dataset.lfGen = "1";
        status.setAttribute("role", "status");
        status.hidden = true;
        this.append(status);
      }
      if (quoted(this)) return;
      if (!this._stop)
        this._stop = watchRequestLifecycle(this, (lifecycle) => paint(this, lifecycle));
    }

    disconnectedCallback() {
      this._stop?.();
      this._stop = null;
    }
  },
);
