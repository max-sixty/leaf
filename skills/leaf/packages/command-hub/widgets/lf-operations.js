/* One-shot host operations. The package declares the verbs, bound host detail, and
   presentation; Leaf's shared request element owns the control and receipt lifecycle. */
import { defineRequestElement } from "/runtime/widget-api.js";

defineRequestElement("lf-operations", {
  itemTag: "lf-operation",
  controlText: "Do this",
  commandContext: "On a host operation",
  commandPrefix: "operation",
  commandText: (label) => ({
    decision: label,
    does: `Request ${label.toLowerCase()}`,
    line: `request ${label.toLowerCase()}`,
  }),
  detail: (holder) => ({
    target: holder.getAttribute("target"),
    worker: holder.getAttribute("worker"),
    worktree: holder.getAttribute("worktree"),
  }),
  statusText: (request, receipt) => {
    const operation = request.action.replaceAll("-", " ");
    return receipt
      ? `${operation} ${receipt.status} · ${receipt.text}`
      : `${operation} requested · waiting for the host`;
  },
});
