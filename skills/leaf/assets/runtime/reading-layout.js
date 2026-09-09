/* Shared light-DOM construction for structural and compound arrangements.

   The caller chooses which direct authored nodes are furniture and whether the
   remaining content is a reading region. This helper owns only the common DOM and
   registration lifecycle; CSS owns division and scrolling, while each widget decides
   when its outermost arrangement receives bounded posture. */
import { registerArrangement } from "./reading-regions.js";
import { LAYOUT, layoutChanged } from "./widget-elements.js";

const generated = (className) => {
  const node = document.createElement("div");
  node.className = className;
  return node;
};

const syncRootWorkspace = (owner) => {
  const main = owner.parentElement;
  const isRoot =
    owner.classList.contains("lf-workspace-arranged") &&
    main?.matches("body > main") &&
    [...main.children].filter((child) => !child.matches("script, style, template"))
      .length === 1;
  owner.toggleAttribute("data-lf-root-workspace", Boolean(isRoot));
};

export function arrangeReadingElement({
  owner,
  kind,
  header = null,
  footer = null,
  regions = [],
}) {
  if (!owner || !["workspace", "pane", "split"].includes(kind))
    throw new Error("leaf: an arranged element needs an owner and layout kind");

  const content = generated(`lf-arranged-content lf-${kind}-content`);
  const body = kind === "pane" ? generated("lf-arranged-body lf-pane-body") : content;
  const furniture = new Set([header, footer].filter(Boolean));
  const arrangement = registerArrangement({
    owner,
    content,
    regions: regions.map((region) => ({
      ...region,
      host: region.host ?? owner,
      body: region.body ?? body,
    })),
  });
  for (const child of [...owner.childNodes]) {
    if (!furniture.has(child)) body.append(child);
  }
  if (body !== content) content.append(body);
  header?.classList.add("lf-arranged-furniture", "lf-arranged-before");
  footer?.classList.add("lf-arranged-furniture", "lf-arranged-after");
  owner.replaceChildren(...[header, content, footer].filter(Boolean));
  owner.classList.add("lf-arranged", `lf-${kind}-arranged`);
  syncRootWorkspace(owner);

  layoutChanged(owner);
  return { body, content, arrangement };
}

export function registerArrangedElement({
  owner,
  content,
  body = content,
  regions = [],
}) {
  const arrangement = registerArrangement({
    owner,
    content,
    regions: regions.map((region) => ({
      ...region,
      host: region.host ?? owner,
      body: region.body ?? body,
    })),
  });
  syncRootWorkspace(owner);
  layoutChanged(owner);
  return arrangement;
}

export function fitRootReadingElement({ owner, arrangement, minimumSize }) {
  if (!owner || !arrangement?.setPosture || typeof minimumSize !== "function")
    throw new Error(
      "leaf: root fitting needs an owner, arrangement, and minimum-size reader",
    );

  let active = true;
  let scheduled = null;
  let resize = null;

  const choosePosture = async () => {
    if (!active || !owner.isConnected) return;
    if (!owner.hasAttribute("data-lf-root-workspace")) {
      await arrangement.setPosture("flow");
      return;
    }

    const minimum = minimumSize();
    if (
      minimum !== null &&
      (!Number.isFinite(minimum?.width) ||
        !Number.isFinite(minimum?.height) ||
        minimum.width < 0 ||
        minimum.height < 0)
    )
      throw new Error("leaf: a root minimum must be null or a finite width and height");

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
    const bounded =
      minimum !== null &&
      availableWidth >= minimum.width &&
      availableHeight >= minimum.height;
    await arrangement.setPosture(bounded ? "bounded" : "flow");
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

  if (owner.hasAttribute("data-lf-root-workspace")) {
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
