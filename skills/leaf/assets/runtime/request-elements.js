/* Shared wiring for one-shot package requests. Packages supply the child tag, bound
   detail, and every reader-facing word; this module owns the repeated control,
   command, request lifecycle, and receipt-state mechanics. */
import { keys as commands } from "./keyboard/scopes.js";
import { offer, quoted } from "./widget-elements.js";
import { once } from "./widget-upgrade.js";

const title = (option) =>
  option.querySelector(":scope > strong")?.textContent.trim() ||
  option.getAttribute("verb").replaceAll("-", " ");

export function createDefineRequestElement({
  requestAvailable,
  sendRequest,
  watchRequestLifecycle,
}) {
  return function defineRequestElement(
    tagName,
    {
      itemTag,
      controlText,
      commandContext,
      commandPrefix,
      commandText,
      detail,
      statusText,
    },
  ) {
    const children = (holder) => [...holder.querySelectorAll(`:scope > ${itemTag}`)];

    const paint = (holder, lifecycle) => {
      holder._requestLifecycle = lifecycle;
      const { request, receipt } = lifecycle.latest ?? {};
      const locked = holder._sendingRequest || lifecycle.phase !== "ready";
      for (const option of children(holder)) {
        const verb = option.getAttribute("verb");
        const control = option.querySelector(":scope > .lf-request-press");
        const available = !locked && requestAvailable(holder, verb);
        option.toggleAttribute("data-lf-requested", request?.action === verb);
        control.setAttribute("aria-disabled", String(!available));
        control.tabIndex = available ? 0 : -1;
      }

      const status = holder.querySelector(":scope > .lf-request-status");
      if (!request) {
        status.hidden = true;
        status.textContent = "";
        return;
      }
      status.hidden = false;
      status.dataset.status = receipt?.status ?? "pending";
      status.textContent = statusText(request, receipt);
    };

    customElements.define(
      tagName,
      class extends HTMLElement {
        connectedCallback() {
          if (!this._requestWired) {
            if (!once(this)) return;
            this._requestWired = true;
            if (quoted(this)) return;
            for (const option of children(this)) {
              const control = offer("button", "lf-btn lf-request-press", controlText);
              const label = title(option);
              control.setAttribute("aria-label", label);
              control.onclick = async () => {
                const verb = option.getAttribute("verb");
                if (
                  this._sendingRequest ||
                  this._requestLifecycle.phase !== "ready" ||
                  !requestAvailable(this, verb)
                )
                  return;
                this._sendingRequest = true;
                paint(this, this._requestLifecycle);
                const accepted = await sendRequest(this, verb, detail(this));
                this._sendingRequest = false;
                if (!accepted) paint(this, this._requestLifecycle);
              };
              option.append(control);
            }
            commands(
              this,
              commandContext,
              children(this).map((option) => {
                const control = option.querySelector(":scope > .lf-request-press");
                const label = title(option);
                return {
                  id: `${commandPrefix}.${option.getAttribute("verb")}`,
                  keys: [],
                  control,
                  ...commandText(label),
                  run: () => control.click(),
                };
              }),
              {
                answer: () => {
                  const action = this._requestLifecycle?.latest?.request?.action;
                  const selected = children(this).find(
                    (option) => option.getAttribute("verb") === action,
                  );
                  return selected ? title(selected) : "";
                },
              },
            );
            const status = document.createElement("div");
            status.className = "lf-request-status lf-ui";
            status.dataset.lfGen = "1";
            status.setAttribute("role", "status");
            status.hidden = true;
            this.append(status);
          }
          if (quoted(this)) return;
          if (!this._stopRequestWatch)
            this._stopRequestWatch = watchRequestLifecycle(this, (lifecycle) =>
              paint(this, lifecycle),
            );
        }

        disconnectedCallback() {
          this._stopRequestWatch?.();
          this._stopRequestWatch = null;
        }
      },
    );
  };
}
