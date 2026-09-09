/* A root workspace can spend the page's available height on reading regions. Embedded
   workspaces keep the same semantic structure in ordinary document flow. */
import {
  arrangeReadingElement,
  LAYOUT,
  once,
  registerArrangedElement,
  settle,
} from "/runtime/widget-api.js";

const MIN_BODY_HEIGHT = 160;
const MIN_PANE_WIDTH = 240;
const MIN_WORKSPACE_WIDTH = 560;

const direct = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

const furniture = (owner) => {
  const nodes = [...owner.querySelectorAll(":scope > .lf-arranged-furniture")];
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

const ARRANGED = ".lf-workspace-arranged, .lf-pane-arranged, .lf-split-arranged";

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
    nodes.length !== (owner.classList.contains("lf-split-arranged") ? 2 : 1)
  )
    return null;
  return nodes;
};

const minimumSize = (owner) => {
  if (
    !owner.hasAttribute("data-lf-root-workspace") &&
    owner.dataset.lfPosture === "flow"
  )
    return null;
  const frame = frameSize(owner);
  if (owner.classList.contains("lf-pane-arranged")) {
    const furnitureSize = furniture(owner);
    return {
      height: frame.height + furnitureSize.height + MIN_BODY_HEIGHT,
      width: frame.width + MIN_PANE_WIDTH,
    };
  }
  const content = owner.querySelector(":scope > .lf-arranged-content");
  const children = content ? arrangedChildren(owner, content) : [];
  if (!children?.length) return null;
  const minima = children.map(minimumSize);
  if (minima.some((size) => size === null)) return null;
  let size;
  if (
    owner.classList.contains("lf-split-arranged") &&
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
        (owner.classList.contains("lf-split-arranged") ? frame.height : 0),
      width:
        owner.classList.contains("lf-split-arranged") &&
        owner.dataset.lfDirection === "columns"
          ? minima.length * Math.max(...minima.map((item) => item.width)) +
            (minima.length - 1) *
              (Number.parseFloat(getComputedStyle(content).columnGap) || 0) +
            frame.width
          : Math.max(...minima.map((item) => item.width)) +
            (owner.classList.contains("lf-split-arranged") ? frame.width : 0),
    };
  if (owner.classList.contains("lf-workspace-arranged")) {
    size.height += furniture(owner).height + frame.height;
    size.width += frame.width;
  }
  return size;
};

customElements.define(
  "lf-workspace",
  class extends HTMLElement {
    #arrangement = null;
    #resize = null;
    #content = null;
    #scheduledPosture = null;

    connectedCallback() {
      if (once(this)) {
        const arranged = arrangeReadingElement({
          owner: this,
          kind: "workspace",
          header: direct(this, "header"),
          footer: direct(this, "footer"),
        });
        this.#arrangement = arranged.arrangement;
        this.#content = arranged.content;
      } else {
        this.#content = this.querySelector(":scope > .lf-workspace-content");
        this.#arrangement = registerArrangedElement({
          owner: this,
          content: this.#content,
        });
      }
      if (!this.hasAttribute("data-lf-root-workspace")) {
        void this.#arrangement.setPosture("flow");
        return;
      }
      this.#resize = new ResizeObserver(this.#schedulePosture);
      this.#resize.observe(document.body);
      window.addEventListener("resize", this.#schedulePosture);
      this.addEventListener(LAYOUT, this.#schedulePosture);
      settle(this.#schedulePosture());
    }

    disconnectedCallback() {
      this.#resize?.disconnect();
      this.#resize = null;
      window.removeEventListener("resize", this.#schedulePosture);
      this.removeEventListener(LAYOUT, this.#schedulePosture);
      this.#arrangement?.cleanup();
      this.#arrangement = null;
    }

    #choosePosture = async () => {
      if (!this.#arrangement || !this.#content?.isConnected) return;
      const bodyMinimum = minimumSize(this);
      const rootStyle = getComputedStyle(document.documentElement);
      const availableHeight =
        innerHeight -
        (Number.parseFloat(getComputedStyle(document.body, "::before").height) || 0) -
        (Number.parseFloat(rootStyle.getPropertyValue("--lf-bottom-chrome-clear")) ||
          0);
      const mainStyle = getComputedStyle(this.parentElement);
      const availableWidth =
        document.body.getBoundingClientRect().width -
        (Number.parseFloat(mainStyle.paddingLeft) || 0) -
        (Number.parseFloat(mainStyle.paddingRight) || 0);
      const bounded =
        bodyMinimum !== null &&
        availableWidth >= Math.max(MIN_WORKSPACE_WIDTH, bodyMinimum.width) &&
        availableHeight >= bodyMinimum.height;
      await this.#arrangement.setPosture(bounded ? "bounded" : "flow");
    };

    #schedulePosture = () => {
      if (!this.#scheduledPosture)
        this.#scheduledPosture = new Promise((resolve, reject) => {
          requestAnimationFrame(() => {
            this.#choosePosture()
              .then(resolve, reject)
              .finally(() => (this.#scheduledPosture = null));
          });
        });
      return this.#scheduledPosture;
    };
  },
);
