/* Shared light-DOM construction for structural and compound reading arrangements.

   The caller chooses which direct authored nodes are furniture and whether the
   remaining content is a reading region. This helper owns the common DOM and
   registration lifecycle, plus the page-room observation a root fits against; CSS owns
   division and scrolling, while each root supplies its own minimum-size policy. */
import { registerReadingArrangement } from "./reading-regions.js";
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

  /* A root's minimum is a reading of its own live layout, and flow lays that layout out
     in the narrow measure column rather than the wide box bounded would give it. Header
     text that wraps to an extra line there reports a minimum taller than the posture
     being decided would ever have, so one window has two stable answers: a root already
     in flow reads itself too tall to leave it, while the same window entered from
     bounded stays bounded. The reading is therefore taken with the root pinned to the
     width bounded allocates, which is what the available box already describes. The
     write, the reading, and the restore are one task, so nothing paints between them —
     and the root keeps the height it already occupies across the reading, because
     furniture that grows shorter at the wider width would otherwise shorten the
     document under a reader who has scrolled down it, and the browser clamps their
     position to the page it measured rather than the one it restores. */
  const readMinimumAt = (availableWidth) => {
    const style = { width: owner.style.width, height: owner.style.height };
    owner.style.height = `${owner.getBoundingClientRect().height}px`;
    owner.style.width = `${availableWidth}px`;
    try {
      return minimumSize();
    } finally {
      owner.style.width = style.width;
      owner.style.height = style.height;
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
    const minimum = readMinimumAt(availableWidth);
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
