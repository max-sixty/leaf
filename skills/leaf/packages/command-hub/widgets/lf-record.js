/* The record as receipts. The log remains the only state; this is a read-only list. */
import { declarationFor, once, watchHistory } from "/runtime/widget-api.js";

const kinds = new Set([
  "action",
  "request",
  "receipt",
  "comment",
  "resolve",
  "unresolve",
  "report",
  "note",
  "done",
  "undo",
]);

function pageName(id) {
  const element = id && document.getElementById(id);
  if (!element) return id || "the page";
  return (
    element.querySelector(":scope > strong")?.textContent.trim() ||
    element.getAttribute("label") ||
    id
  );
}

function actionReceipt(event) {
  const element = document.getElementById(event.widget);
  const target = pageName(event.widget);
  const state = declarationFor(element, "x-state")?.[event.action];
  const value = state?.record?.value;
  if (state?.record?.kind === "attribute" && value) {
    const ids = Array.isArray(event.detail[value]) ? event.detail[value] : [];
    const choices = ids.map(pageName).join(", ") || "no option";
    return `${event.author === "page" ? "Default fired" : "Selected"}: ${choices} · ${target} (${event.widget})`;
  }
  if (state?.record?.kind === "body")
    return `Saved input · ${target} (${event.widget})`;
  const detail = Object.values(event.detail ?? {}).filter(
    (item) => typeof item === "string" || typeof item === "number",
  );
  return `${event.action}${detail.length ? `: ${detail.join(", ")}` : ""} · ${target} (${event.widget})`;
}

function reportReceipt(event) {
  const element = document.getElementById(event.widget);
  const report = declarationFor(element, "x-report")?.[event.action];
  const value = report?.record?.value;
  const detail = value ? event.detail[value] : Object.values(event.detail ?? {})[0];
  return `${pageName(event.widget)} reported ${detail ?? event.action} (${event.widget})`;
}

function hostRequestReceipt(event) {
  const target = event.detail?.target;
  return `Requested ${event.action.replaceAll("-", " ")} · ${pageName(target)}${target ? ` (${target})` : ""}`;
}

function hostOutcomeReceipt(event, events) {
  const request = events.find((candidate) => candidate.id === event.request);
  const operation = request?.action?.replaceAll("-", " ") ?? "request";
  const target = request?.detail?.target;
  return `${operation} ${event.status} · ${pageName(target)}${target ? ` (${target})` : ""} · ${event.text}`;
}

function threadRoot(event, events) {
  let current = event;
  const seen = new Set();
  while (current?.parent && !seen.has(current.id)) {
    seen.add(current.id);
    current = events.find((candidate) => candidate.id === current.parent);
  }
  return current?.kind === "comment" ? current : null;
}

function receipt(event, events) {
  const row = document.createElement("li");
  row.dataset.lfGen = "1";
  const time = document.createElement("time");
  time.dateTime = event.ts;
  time.textContent = new Date(event.ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  let words;
  if (event.kind === "action") words = actionReceipt(event);
  else if (event.kind === "request") words = hostRequestReceipt(event);
  else if (event.kind === "receipt") words = hostOutcomeReceipt(event, events);
  else if (event.holds)
    words = `sent and paused · ${pageName(event.holds)} (${event.holds})`;
  else if (event.kind === "report") words = reportReceipt(event);
  else if (event.kind === "resolve" || event.kind === "unresolve") {
    const root = threadRoot(event, events);
    const target = root?.holds || root?.anchor?.section;
    words = `${event.kind === "resolve" ? "Released" : "Reopened"} · ${pageName(target)}${target ? ` (${target})` : ""}`;
  } else if (event.kind === "undo") words = `Took back event ${event.undoes}`;
  else if (event.kind === "note") words = `Published v${event.version} · ${event.text}`;
  else if (event.kind === "done") words = `Approved v${event.version}`;
  else words = `${event.kind} · ${pageName(event.anchor?.section || event.parent)}`;
  row.append(time, ` · ${words}`);
  return row;
}

customElements.define(
  "lf-record",
  class extends HTMLElement {
    #stop = null;
    #signature = null;

    connectedCallback() {
      if (!once(this) && this.#stop) return;
      this.#stop = watchHistory(this, (events) => {
        const relevant = events.filter((event) => kinds.has(event.kind));
        const next = JSON.stringify(relevant);
        if (next === this.#signature) return;
        this.#signature = next;
        const list = document.createElement("ol");
        list.dataset.lfGen = "1";
        if (relevant.length)
          list.append(...relevant.map((event) => receipt(event, events)));
        else
          list.append(
            Object.assign(document.createElement("li"), {
              textContent: "No gestures recorded yet.",
            }),
          );
        this.replaceChildren(list);
      });
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }
  },
);
