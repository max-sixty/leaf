/* A root workspace can spend the page's available height on reading regions. Embedded
   workspaces keep the same semantic structure in ordinary document flow. */
import {
  arrangeReadingElement,
  fitRootReadingElement,
  once,
  registerReadingElement,
  settle,
} from "/runtime/widget-api.js";

const MIN_BODY_HEIGHT = 160;
const MIN_PANE_WIDTH = 240;
const MIN_WORKSPACE_WIDTH = 560;

const direct = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

const readingFrameSize = (owner) => {
  const nodes = [...owner.querySelectorAll(":scope > .lf-reading-frame")];
  return {
    height: nodes.reduce(
      (height, node) => height + node.getBoundingClientRect().height,
      0,
    ),
  };
};

const lengths = (node, names) => {
  const style = getComputedStyle(node);
  return names.reduce(
    (total, name) => total + (Number.parseFloat(style[name]) || 0),
    0,
  );
};

const frameSize = (node) => ({
  height: lengths(node, [
    "paddingTop",
    "paddingBottom",
    "borderTopWidth",
    "borderBottomWidth",
  ]),
  width: lengths(node, [
    "paddingLeft",
    "paddingRight",
    "borderLeftWidth",
    "borderRightWidth",
  ]),
});

const ARRANGED = ".lf-workspace-reading, .lf-pane-reading, .lf-partition-reading";

const arrangedChildren = (owner, content) => {
  const nodes = [...content.childNodes].filter(
    (node) =>
      node.nodeType === Node.ELEMENT_NODE ||
      (node.nodeType === Node.TEXT_NODE && node.textContent.trim()),
  );
  if (
    nodes.some(
      (node) => node.nodeType !== Node.ELEMENT_NODE || !node.matches(ARRANGED),
    ) ||
    nodes.length !== (owner.classList.contains("lf-partition-reading") ? 2 : 1)
  )
    return null;
  return nodes;
};

const minimumSize = (owner) => {
  if (
    owner.dataset.lfWorkspaceContext !== "root" &&
    owner.dataset.lfReadingPosture === "flow"
  )
    return null;
  const frame = frameSize(owner);
  if (owner.classList.contains("lf-pane-reading")) {
    const furnitureSize = readingFrameSize(owner);
    return {
      height: frame.height + furnitureSize.height + MIN_BODY_HEIGHT,
      width: frame.width + MIN_PANE_WIDTH,
    };
  }
  const content = owner.querySelector(":scope > .lf-reading-content");
  const children = content ? arrangedChildren(owner, content) : [];
  if (!children?.length) return null;
  const minima = children.map(minimumSize);
  if (minima.some((size) => size === null)) return null;
  let size;
  if (
    owner.classList.contains("lf-partition-reading") &&
    owner.dataset.lfDirection === "rows"
  )
    size = {
      height:
        minima.length * Math.max(...minima.map((item) => item.height)) +
        (minima.length - 1) *
          (Number.parseFloat(getComputedStyle(content).rowGap) || 0) +
        frame.height,
      width: Math.max(...minima.map((size) => size.width)) + frame.width,
    };
  else
    size = {
      height:
        Math.max(...minima.map((item) => item.height)) +
        (owner.classList.contains("lf-partition-reading") ? frame.height : 0),
      width:
        owner.classList.contains("lf-partition-reading") &&
        owner.dataset.lfDirection === "columns"
          ? minima.length * Math.max(...minima.map((item) => item.width)) +
            (minima.length - 1) *
              (Number.parseFloat(getComputedStyle(content).columnGap) || 0) +
            frame.width
          : Math.max(...minima.map((item) => item.width)) +
            (owner.classList.contains("lf-partition-reading") ? frame.width : 0),
    };
  if (owner.classList.contains("lf-workspace-reading")) {
    size.height += readingFrameSize(owner).height + frame.height;
    size.width += frame.width;
  }
  return size;
};

customElements.define(
  "lf-workspace",
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
        minimumSize: () => {
          const size = minimumSize(this);
          return (
            size && {
              height: size.height,
              width: Math.max(MIN_WORKSPACE_WIDTH, size.width),
            }
          );
        },
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
