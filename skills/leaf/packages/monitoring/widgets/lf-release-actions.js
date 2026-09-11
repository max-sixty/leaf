/* Release operations bind the candidate and stable versions; the shared request
   element owns the control and receipt lifecycle. */
import { defineRequestElement } from "/runtime/widget-api.js";

defineRequestElement("lf-release-actions", {
  itemTag: "lf-release-action",
  commandContext: "On a release",
  commandPrefix: "release",
  detail: (holder) => ({
    candidate: holder.getAttribute("candidate"),
    stable: holder.getAttribute("stable"),
  }),
});
