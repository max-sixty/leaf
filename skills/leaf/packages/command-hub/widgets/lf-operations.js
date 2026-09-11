/* One-shot host operations. The package declares the verbs and bound host detail;
   Leaf's shared request element owns the control and receipt lifecycle. */
import { defineRequestElement } from "/runtime/widget-api.js";

defineRequestElement("lf-operations", {
  itemTag: "lf-operation",
  commandContext: "On a host operation",
  commandPrefix: "operation",
  detail: (holder) => ({
    target: holder.getAttribute("target"),
    worker: holder.getAttribute("worker"),
    worktree: holder.getAttribute("worktree"),
  }),
});
