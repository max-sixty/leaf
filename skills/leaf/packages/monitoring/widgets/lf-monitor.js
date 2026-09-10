/* A monitoring root shares Leaf's page-fit lifecycle while keeping its own asymmetric
   minimum: compact overview, wide evidence, and a persistent exception column. */
import {
  arrangeReadingElement,
  fitRootReadingElement,
  once,
  registerReadingElement,
  settle,
} from "/runtime/widget-api.js";

const direct = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

const length = (style, name) => Number.parseFloat(style.getPropertyValue(name)) || 0;

const frameSize = (node) => {
  const style = getComputedStyle(node);
  return {
    height:
      length(style, "padding-top") +
      length(style, "padding-bottom") +
      length(style, "border-top-width") +
      length(style, "border-bottom-width"),
    width:
      length(style, "padding-left") +
      length(style, "padding-right") +
      length(style, "border-left-width") +
      length(style, "border-right-width"),
  };
};

const minimumSize = (owner, content) => {
  const grid = content?.querySelector(":scope > lf-monitor-grid");
  if (!grid) return null;
  const style = getComputedStyle(owner);
  const frame = frameSize(owner);
  const furnitureHeight = [...owner.children]
    .filter((node) => node.classList.contains("lf-reading-frame"))
    .reduce((height, node) => height + node.getBoundingClientRect().height, 0);
  return {
    height:
      frame.height + furnitureHeight + length(style, "--lf-monitor-body-min-height"),
    width:
      frame.width +
      length(style, "--lf-monitor-overview-min-width") +
      length(style, "--lf-monitor-evidence-min-width") +
      length(style, "--lf-monitor-exception-min-width") +
      2 * length(style, "--lf-monitor-gap"),
  };
};

customElements.define(
  "lf-monitor",
  class extends HTMLElement {
    #readingArrangement = null;
    #content = null;
    #fitting = null;

    connectedCallback() {
      if (once(this)) {
        const arranged = arrangeReadingElement({
          owner: this,
          role: "workspace",
          header: direct(this, "header"),
          footer: direct(this, "footer"),
        });
        this.#readingArrangement = arranged.readingArrangement;
        this.#content = arranged.content;
      } else {
        this.#content = this.querySelector(":scope > .lf-workspace-content");
        this.#readingArrangement = registerReadingElement({
          owner: this,
          content: this.#content,
        });
      }
      this.#fitting = fitRootReadingElement({
        owner: this,
        readingArrangement: this.#readingArrangement,
        minimumSize: () => minimumSize(this, this.#content),
      });
      settle(this.#fitting.update());
    }

    disconnectedCallback() {
      this.#fitting?.cleanup();
      this.#fitting = null;
      this.#readingArrangement?.cleanup();
      this.#readingArrangement = null;
    }
  },
);
