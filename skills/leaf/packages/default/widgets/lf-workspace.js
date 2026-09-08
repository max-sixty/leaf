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

const isRootWorkspace = (owner) => {
  const main = owner.parentElement;
  return (
    main?.matches("body > main") &&
    [...main.children].filter((child) => !child.matches("script, style, template"))
      .length === 1
  );
};

const furniture = (owner) => {
  const nodes = [":scope > header", ":scope > footer"]
    .map((selector) => owner.querySelector(selector))
    .filter(Boolean);
  return {
    height: nodes.reduce(
      (height, node) => height + node.getBoundingClientRect().height,
      0,
    ),
  };
};

const outerHeight = (node) => {
  const style = getComputedStyle(node);
  return (
    node.getBoundingClientRect().height +
    (Number.parseFloat(style.marginTop) || 0) +
    (Number.parseFloat(style.marginBottom) || 0)
  );
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

const margins = (node) => ({
  height: lengths(node, ["marginTop", "marginBottom"]),
  width: lengths(node, ["marginLeft", "marginRight"]),
});

const ARRANGED = ".lf-workspace-arranged, .lf-pane-arranged, .lf-split-arranged";

const bridgeFor = (owner, content) => {
  if (!owner.classList.contains("lf-workspace-arranged")) return null;
  const bridge = content.children.length === 1 ? content.firstElementChild : null;
  return bridge?.matches("lf-ask") &&
    bridge.firstElementChild?.matches("h1, h2, h3, h4, h5, h6")
    ? bridge
    : null;
};

const arrangedChildren = (owner, content) => {
  const direct = [...content.children].filter((child) => child.matches(ARRANGED));
  if (direct.length || !owner.classList.contains("lf-workspace-arranged"))
    return direct;
  const bridge = bridgeFor(owner, content);
  if (!bridge) return [];
  const arranged = bridge.lastElementChild;
  return arranged?.matches(ARRANGED) ? [arranged] : [];
};

const minimumSize = (owner) => {
  const frame = frameSize(owner);
  if (owner.classList.contains("lf-pane-arranged")) {
    const furnitureSize = furniture(owner);
    return {
      height: frame.height + furnitureSize.height + MIN_BODY_HEIGHT,
      width: frame.width + MIN_PANE_WIDTH,
    };
  }
  const content = owner.querySelector(
    `:scope > .lf-${owner.classList.contains("lf-split-arranged") ? "split" : "workspace"}-content`,
  );
  const children = content ? arrangedChildren(owner, content) : [];
  if (!children.length) return null;
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
    const bridge = bridgeFor(owner, content);
    if (bridge) {
      const childMargins = margins(children[0]);
      size.height += outerHeight(bridge.firstElementChild) + childMargins.height;
      size.width += childMargins.width;
    }
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
      this.toggleAttribute("data-lf-root-workspace", isRootWorkspace(this));
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
        (Number.parseFloat(rootStyle.getPropertyValue("--lf-shortcut-bar-clear")) || 0);
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
