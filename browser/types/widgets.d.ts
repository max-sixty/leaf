/* Native custom-element queries resolve the package class that owns the tag. */
interface HTMLElementTagNameMap {
  "lf-sample": import("../../packages/default/widgets/lf-sample.js").Sample;
  "lf-option": HTMLElement;
  "lf-column": HTMLElement;
  "lf-card": HTMLElement;
  "lf-shot": import("../../packages/default/widgets/lf-shot.js").Shot;
  "lf-trace": import("../../packages/playwright/widgets/lf-trace.js").Trace;
}
interface HTMLElementEventMap {
  "lf-trace-moment": CustomEvent<{ key: string }>;
}
