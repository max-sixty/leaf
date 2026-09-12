/* Shared light-DOM construction for structural and compound reading arrangements.

   The caller chooses which direct authored nodes are furniture and whether the
   remaining content is a reading region. This helper owns the common DOM and
   registration lifecycle, plus the page-room observation a root fits against; CSS owns
   division and scrolling, while each root supplies its own minimum-size policy. */
import {
  readReadingArrangementAt,
  registerReadingArrangement,
} from "./reading-regions.js";
import { LAYOUT, layoutChanged } from "./widget-elements.js";
import { once } from "./widget-upgrade.js";

const generated = (className) => {
  const node = document.createElement("div");
  node.className = className;
  return node;
};

const syncWorkspaceContext = (owner) => {
  if (!owner.classList.contains("lf-workspace-reading")) {
    owner.removeAttribute("data-lf-workspace-context");
    return;
  }
  const main = owner.parentElement;
  const isRoot =
    main?.matches("body > main") &&
    [...main.children].filter((child) => !child.matches("script, style, template"))
      .length === 1;
  owner.dataset.lfWorkspaceContext = isRoot ? "root" : "embedded";
};

export function arrangeReadingElement({
  owner,
  role,
  header = null,
  footer = null,
  regions = [],
}) {
  if (!owner || !["workspace", "pane", "partition"].includes(role))
    throw new Error("leaf: a reading element needs an owner and reading role");

  const content = generated(`lf-reading-content lf-${role}-content`);
  const body = role === "pane" ? generated("lf-reading-body lf-pane-body") : content;
  const frame = new Set([header, footer].filter(Boolean));
  const readingArrangement = registerReadingArrangement({
    owner,
    content,
    regions: regions.map((region) => ({
      ...region,
      host: region.host ?? owner,
      body: region.body ?? body,
    })),
  });
  for (const child of [...owner.childNodes]) {
    if (!frame.has(child)) body.append(child);
  }
  if (body !== content) content.append(body);
  header?.classList.add("lf-reading-frame", "lf-reading-before");
  footer?.classList.add("lf-reading-frame", "lf-reading-after");
  owner.replaceChildren(...[header, content, footer].filter(Boolean));
  owner.classList.add("lf-reading", `lf-${role}-reading`);
  syncWorkspaceContext(owner);

  layoutChanged(owner);
  return { body, content, readingArrangement };
}

export function registerReadingElement({
  owner,
  content,
  body = content,
  regions = [],
}) {
  const readingArrangement = registerReadingArrangement({
    owner,
    content,
    regions: regions.map((region) => ({
      ...region,
      host: region.host ?? owner,
      body: region.body ?? body,
    })),
  });
  syncWorkspaceContext(owner);
  layoutChanged(owner);
  return readingArrangement;
}

const directChild = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

export function defineReadingPaneElement(tagName) {
  customElements.define(
    tagName,
    class extends HTMLElement {
      #readingArrangement = null;

      connectedCallback() {
        if (!once(this)) {
          const content = this.querySelector(":scope > .lf-pane-content");
          const body = this.querySelector(":scope > .lf-pane-content > .lf-pane-body");
          this.#readingArrangement = registerReadingElement({
            owner: this,
            content,
            body,
            regions: [{ id: this.id, host: this, body }],
          });
          return;
        }
        const header = directChild(this, "header");
        const footer = directChild(this, "footer");
        this.setAttribute("role", "region");
        this.setAttribute("aria-label", this.getAttribute("label"));
        this.#readingArrangement = arrangeReadingElement({
          owner: this,
          role: "pane",
          header,
          footer,
          regions: [{ id: this.id, host: this }],
        }).readingArrangement;
      }

      disconnectedCallback() {
        this.#readingArrangement?.cleanup();
        this.#readingArrangement = null;
      }
    },
  );
}

export function fitRootReadingElement({ owner, readingArrangement, minimumSize }) {
  if (
    !owner ||
    !readingArrangement?.setReadingPosture ||
    typeof minimumSize !== "function"
  )
    throw new Error(
      "leaf: root fitting needs an owner, reading arrangement, and minimum-size reader",
    );

  let active = true;
  let scheduled = null;
  let resize = null;

  /* A root's minimum is a reading of its live layout. Read the bounded candidate in
     the box it would receive so wrapping furniture, nested partitions, and package
     posture rules cannot make the same window answer differently based on the posture
     currently drawn. The temporary style and posture writes are restored in the same
     task, before anything can paint. Height stays pinned because temporarily shortening
     a flow document would otherwise clamp a reader's scroll position. */
  const readBoundedMinimum = (availableWidth) => {
    const main = owner.parentElement;
    const root = document.documentElement;
    const styles = new Map(
      [root, main, owner].map((element) => [element, element.getAttribute("style")]),
    );
    root.style.overflowY = getComputedStyle(root).overflowY;
    main.style.height = `${main.getBoundingClientRect().height}px`;
    owner.style.height = `${owner.getBoundingClientRect().height}px`;
    owner.style.width = `${availableWidth}px`;
    try {
      return readReadingArrangementAt(readingArrangement, "bounded", minimumSize);
    } finally {
      for (const [element, style] of styles) {
        if (style === null) element.removeAttribute("style");
        else element.setAttribute("style", style);
      }
    }
  };

  const choosePosture = async () => {
    if (!active || !owner.isConnected) return;
    if (owner.dataset.lfWorkspaceContext !== "root") {
      await readingArrangement.setReadingPosture("flow");
      return;
    }

    const rootStyle = getComputedStyle(document.documentElement);
    const availableHeight =
      innerHeight -
      (Number.parseFloat(getComputedStyle(document.body, "::before").height) || 0) -
      (Number.parseFloat(rootStyle.getPropertyValue("--lf-bottom-chrome-clear")) || 0);
    const mainStyle = getComputedStyle(owner.parentElement);
    const availableWidth =
      document.body.getBoundingClientRect().width -
      (Number.parseFloat(mainStyle.paddingLeft) || 0) -
      (Number.parseFloat(mainStyle.paddingRight) || 0);
    const minimum = readBoundedMinimum(availableWidth);
    if (
      minimum !== null &&
      (!Number.isFinite(minimum?.width) ||
        !Number.isFinite(minimum?.height) ||
        minimum.width < 0 ||
        minimum.height < 0)
    )
      throw new Error("leaf: a root minimum must be null or a finite width and height");

    const bounded =
      minimum !== null &&
      availableWidth >= minimum.width &&
      availableHeight >= minimum.height;
    await readingArrangement.setReadingPosture(bounded ? "bounded" : "flow");
  };

  const update = () => {
    if (!scheduled)
      scheduled = new Promise((resolve, reject) => {
        requestAnimationFrame(() => {
          choosePosture()
            .then(resolve, reject)
            .finally(() => (scheduled = null));
        });
      });
    return scheduled;
  };

  if (owner.dataset.lfWorkspaceContext === "root") {
    resize = new ResizeObserver(update);
    resize.observe(document.body);
    window.addEventListener("resize", update);
    owner.addEventListener(LAYOUT, update);
  }

  return {
    update,
    cleanup() {
      active = false;
      resize?.disconnect();
      resize = null;
      window.removeEventListener("resize", update);
      owner.removeEventListener(LAYOUT, update);
    },
  };
}
