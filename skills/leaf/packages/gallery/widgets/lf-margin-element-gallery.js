/* A fixed developer exhibit of the complete margin element schema. It deliberately uses the
 * public marginElement factory rather than reproducing any margin element anatomy or state paint;
 * the only local rendering is the comparison grid and the words that name each cell. */
import { marginElement, once, offer, relabel } from "/runtime/widget-api.js";

const GROUPS = [
  {
    heading: "Roles and behavior",
    summary: "Every role · action, disclosure, status · every tone",
    specimens: [
      {
        name: "Save",
        detail: "complete · positive action",
        icon: "check",
        behavior: "action",
        tone: "positive",
        role: "complete",
      },
      {
        name: "Cancel",
        detail: "escape · negative action",
        icon: "cross",
        behavior: "action",
        tone: "negative",
        role: "escape",
      },
      {
        name: "Accept",
        detail: "primary · positive action",
        icon: "check",
        behavior: "action",
        tone: "positive",
        role: "primary",
      },
      {
        name: "Reject",
        detail: "secondary · negative action",
        icon: "cross",
        behavior: "action",
        tone: "negative",
        role: "secondary",
      },
      {
        name: "Thread",
        detail: "reading · neutral disclosure",
        icon: "comment",
        behavior: "disclosure",
        tone: "neutral",
        role: "reading",
      },
      {
        name: "More",
        detail: "overflow · neutral disclosure",
        icon: "more",
        behavior: "disclosure",
        tone: "neutral",
        role: "overflow",
      },
      {
        name: "Sent",
        detail: "reading · neutral status",
        icon: "sent",
        behavior: "status",
        tone: "neutral",
        role: "reading",
      },
    ],
  },
  {
    heading: "Lifecycle",
    summary: "Only work in flight is marked; the rest rank without painting",
    specimens: [
      {
        name: "Idle",
        detail: "no mark",
        icon: "dot",
        state: "idle",
      },
      {
        name: "Engaged",
        detail: "no mark · ranks above idle",
        icon: "edit",
        state: "engaged",
      },
      {
        name: "Busy",
        detail: "moving open ring",
        icon: "sent",
        state: "busy",
      },
      {
        name: "Failed",
        detail: "no mark · ranks first",
        icon: "retry",
        state: "failed",
      },
    ],
  },
];

function generated(tag, className, words = null) {
  const node = document.createElement(tag);
  node.className = className;
  if (words != null) relabel(node, words, { says: false });
  return node;
}

function specimenNode(specimen, groupIndex, specimenIndex) {
  const item = generated("div", "margin-element-gallery-item");
  item.dataset.marginElementSpecimen = specimen.name.toLowerCase();
  const behavior = specimen.behavior ?? "action";
  const control = marginElement(
    offer(behavior === "status" ? "span" : "button", "margin-element-gallery-face"),
    {
      key: `gallery-${groupIndex}-${specimenIndex}`,
      label: specimen.name,
      icon: specimen.icon,
      behavior,
      tone: specimen.tone ?? "neutral",
      role: specimen.role ?? "primary",
      state: specimen.state ?? "idle",
    },
  );
  if (control instanceof HTMLButtonElement) control.disabled = true;
  if (behavior !== "status") control.setAttribute("aria-disabled", "true");

  const copy = generated("span", "margin-element-gallery-copy");
  copy.append(
    generated("span", "margin-element-gallery-name", specimen.name),
    generated("span", "margin-element-gallery-detail", specimen.detail),
  );
  item.append(control, copy);
  return item;
}

function groupNode(group, groupIndex) {
  const row = generated("div", "margin-element-gallery-group");
  const introduction = generated("div", "margin-element-gallery-introduction");
  introduction.append(
    generated("strong", "margin-element-gallery-heading", group.heading),
    generated("span", "margin-element-gallery-summary", group.summary),
  );
  const items = generated("div", "margin-element-gallery-items");
  items.append(
    ...group.specimens.map((specimen, specimenIndex) =>
      specimenNode(specimen, groupIndex, specimenIndex),
    ),
  );
  row.append(introduction, items);
  return row;
}

customElements.define(
  "lf-margin-element-gallery",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.append(...GROUPS.map(groupNode));
    }
  },
);
