/* A fixed developer exhibit of the complete Button grammar. It deliberately uses the
 * public marginButton factory rather than reproducing any Button anatomy or state paint;
 * the only local rendering is the comparison grid and the words that name each cell. */
import { marginButton, once, offer, relabel } from "/runtime/widget-api.js";

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
    summary: "Every state remains visible at the same time",
    specimens: [
      {
        name: "Idle",
        detail: "no mark",
        icon: "dot",
        state: "idle",
      },
      {
        name: "Engaged",
        detail: "dot",
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
        detail: "diamond",
        icon: "retry",
        state: "failed",
      },
      {
        name: "Settled",
        detail: "square",
        icon: "undo",
        state: "settled",
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
  const item = generated("div", "button-atlas-item");
  item.dataset.buttonSpecimen = specimen.name.toLowerCase();
  const behavior = specimen.behavior ?? "action";
  const control = marginButton(
    offer(behavior === "status" ? "span" : "button", "button-atlas-button"),
    {
      key: `atlas-${groupIndex}-${specimenIndex}`,
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

  const copy = generated("span", "button-atlas-copy");
  copy.append(
    generated("span", "button-atlas-name", specimen.name),
    generated("span", "button-atlas-detail", specimen.detail),
  );
  item.append(control, copy);
  return item;
}

function groupNode(group, groupIndex) {
  const row = generated("div", "button-atlas-group");
  const introduction = generated("div", "button-atlas-introduction");
  introduction.append(
    generated("strong", "button-atlas-heading", group.heading),
    generated("span", "button-atlas-summary", group.summary),
  );
  const items = generated("div", "button-atlas-items");
  items.append(
    ...group.specimens.map((specimen, specimenIndex) =>
      specimenNode(specimen, groupIndex, specimenIndex),
    ),
  );
  row.append(introduction, items);
  return row;
}

customElements.define(
  "lf-button-atlas",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.append(...GROUPS.map(groupNode));
    }
  },
);
