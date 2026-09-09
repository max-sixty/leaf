/* Shared light-DOM construction for structural and compound arrangements.

   The caller chooses which direct authored nodes are furniture and whether the
   remaining content is a reading region. This helper owns only the common DOM and
   registration lifecycle; CSS owns division and scrolling, while each widget decides
   when its outermost arrangement receives bounded posture. */
import { registerArrangement } from "./reading-regions.js";
import { layoutChanged } from "./widget-elements.js";

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
