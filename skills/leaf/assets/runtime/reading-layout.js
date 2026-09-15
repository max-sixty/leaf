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
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";

const generated = (className) => {
  const node = document.createElement("div");
  node.className = className;
  return node;
};

const substantiveChildren = (owner) =>
  [...owner.childNodes].filter(
    (child) =>
      (child.nodeType === Node.ELEMENT_NODE &&
        !child.matches("script, style, template")) ||
      (child.nodeType === Node.TEXT_NODE && child.textContent.trim()),
  );

/* A root arrangement may stand directly in the content frame or in a package-owned
   root slot. The marker is the open capability: core does not need to know whether the
   slot is a tab panel, a disclosure, or another structural composition. A slot grants
   root posture only to its sole substantive child, so wrapping a workspace in ordinary
   prose keeps it embedded. */
const rootReadingSlot = (owner) => {
  const main = owner.closest("body > main");
  if (!main) return null;
  if (owner.parentElement === main && substantiveChildren(main).length === 1)
    return owner;
  const slot = owner.parentElement?.closest("[data-lf-root-reading]");
  return slot &&
    substantiveChildren(slot).length === 1 &&
    substantiveChildren(slot)[0] === owner
    ? slot
    : null;
};

const syncWorkspaceContext = (owner) => {
  if (!owner.classList.contains("lf-workspace-reading")) {
    owner.removeAttribute("data-lf-workspace-context");
    return;
  }
  owner.dataset.lfWorkspaceContext = rootReadingSlot(owner) ? "root" : "embedded";
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
  const onLayout = (event) => {
    // Composition markers change synchronously with their panel. Publish that context
    // before the queued fit so page-level constraints and native history restoration
    // see the new allocation immediately.
    syncWorkspaceContext(owner);
    const ready = update();
    event.detail?.present?.(ready);
  };

  /* A root's fit is a reading of its live layout. Read both the room and the minimum
     inside the bounded candidate so scrollbar allocation, wrapping furniture, nested
     partitions, and package posture rules cannot make the same window answer
     differently based on the posture currently drawn. The temporary style and posture
     writes are restored in the same task, before anything can paint. The root, main,
     and owner heights stay pinned because temporarily removing document-end room or
     shortening a flow document would otherwise clamp a reader's scroll position. */
  const readBoundedFit = () => {
    const main = owner.closest("body > main");
    const slot = rootReadingSlot(owner);
    const root = document.documentElement;
    const styles = new Map(
      [root, main, owner].map((element) => [element, element.getAttribute("style")]),
    );
    setRuntimeRootStyle(root, "min-height", `${root.scrollHeight}px`);
    main.style.height = `${main.getBoundingClientRect().height}px`;
    owner.style.height = `${owner.getBoundingClientRect().height}px`;
    try {
      return readReadingArrangementAt(readingArrangement, "bounded", () => {
        const rootStyle = getComputedStyle(root);
        const mainStyle = getComputedStyle(main);
        const mainBox = main.getBoundingClientRect();
        const slotBox = (slot ?? owner).getBoundingClientRect();
        const slotOffset = Math.max(
          0,
          slotBox.top -
            mainBox.top -
            (Number.parseFloat(mainStyle.borderTopWidth) || 0) -
            (Number.parseFloat(mainStyle.paddingTop) || 0),
        );
        const availableHeight =
          innerHeight -
          (Number.parseFloat(getComputedStyle(document.body, "::before").height) || 0) -
          (Number.parseFloat(rootStyle.getPropertyValue("--lf-bottom-chrome-clear")) ||
            0) -
          slotOffset -
          (Number.parseFloat(mainStyle.paddingTop) || 0) -
          (Number.parseFloat(mainStyle.paddingBottom) || 0) -
          (Number.parseFloat(mainStyle.borderTopWidth) || 0) -
          (Number.parseFloat(mainStyle.borderBottomWidth) || 0);
        const availableWidth =
          main.getBoundingClientRect().width -
          (Number.parseFloat(mainStyle.paddingLeft) || 0) -
          (Number.parseFloat(mainStyle.paddingRight) || 0) -
          (Number.parseFloat(mainStyle.borderLeftWidth) || 0) -
          (Number.parseFloat(mainStyle.borderRightWidth) || 0);
        owner.style.width = `${availableWidth}px`;
        return { availableHeight, availableWidth, minimum: minimumSize() };
      });
    } finally {
      removeRuntimeRootStyle(root, "min-height");
      for (const [element, style] of styles) {
        if (style === null) element.removeAttribute("style");
        else element.setAttribute("style", style);
      }
    }
  };

  const choosePosture = async () => {
    if (!active || !owner.isConnected) return;
    syncWorkspaceContext(owner);
    if (owner.dataset.lfWorkspaceContext !== "root") {
      await readingArrangement.setReadingPosture("flow");
      return;
    }

    const { availableHeight, availableWidth, minimum } = readBoundedFit();
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

  // A package composition can promote or retire this arrangement as its active root
  // slot without reconnecting the workspace. Keep the same layout doors in either
  // context; update synchronizes the context before it chooses a posture.
  resize = new ResizeObserver(update);
  resize.observe(document.body);
  window.addEventListener("resize", update);
  owner.addEventListener(LAYOUT, onLayout);

  return {
    update,
    cleanup() {
      active = false;
      resize?.disconnect();
      resize = null;
      window.removeEventListener("resize", update);
      owner.removeEventListener(LAYOUT, onLayout);
    },
  };
}
