/* A monitoring root shares Leaf's page-fit lifecycle while keeping its own asymmetric
   minimum: one release panel beside the checks and log that explain its state. */
import { arrangeReadingElement, once, widgetController } from "/runtime/widget-api.js";

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
      length(style, "--lf-monitor-release-min-width") +
      length(style, "--lf-monitor-evidence-min-width") +
      length(style, "--lf-monitor-gap"),
  };
};

customElements.define(
  "lf-monitor",
  class extends HTMLElement {
    #layout = null;

    connectedCallback() {
      if (!this.#layout) {
        this.#layout = arrangeReadingElement({
          owner: this,
          role: "workspace",
          header: direct(this, "header"),
          footer: direct(this, "footer"),
          minimumSize: () => minimumSize(this, this.#layout.content),
        });
        once(this);
      }
      widgetController(this).present(this.#layout.connect());
    }

    disconnectedCallback() {
      this.#layout?.disconnect();
    }
  },
);
