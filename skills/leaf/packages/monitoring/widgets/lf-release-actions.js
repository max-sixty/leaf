/* Release operations bind the candidate and stable versions and own their copy; the
   shared request element owns the control and receipt lifecycle. */
import { defineRequestElement } from "/runtime/widget-api.js";

defineRequestElement("lf-release-actions", {
  itemTag: "lf-release-action",
  controlText: "Request",
  commandContext: "On a release",
  commandPrefix: "release",
  commandText: (label) => ({
    decision: label,
    does: label,
    line: label.toLowerCase(),
  }),
  detail: (holder) => ({
    candidate: holder.getAttribute("candidate"),
    stable: holder.getAttribute("stable"),
  }),
  statusText: (_request, receipt) =>
    receipt
      ? `Rollback ${receipt.status} · ${receipt.text}`
      : "Rollback requested · waiting for the host",
});
