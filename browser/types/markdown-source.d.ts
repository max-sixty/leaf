import "markdown-it";

declare module "markdown-it" {
  interface Token {
    /** Source facts produced by Leaf's parser instrumentation, separate from plugin metadata. */
    lfSource?: import("../runtime/markdown.js").TokenSource;
  }
  interface StateInline {
    sourcePendingFrom?: number | null;
  }
}
