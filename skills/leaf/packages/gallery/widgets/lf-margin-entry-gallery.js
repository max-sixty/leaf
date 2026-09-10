/* A fixed developer exhibit of the complete margin entry schema. It deliberately uses the
 * public marginEntry factory rather than reproducing any margin entry anatomy or state paint;
 * the only local rendering is the comparison grid and the words that name each cell. */
import { marginEntry, once, offer, relabel } from "/runtime/widget-api.js";

const GROUPS = [
  {
    heading: "Rank and behavior",
    summary: "Every rank · action, disclosure, status · every tone",
    specimens: [
      {
        name: "Save",
        detail: "complete · positive action",
        icon: "check",
        behavior: "action",
        tone: "positive",
        rank: "complete",
      },
      {
        name: "Cancel",
        detail: "escape · negative action",
        icon: "cross",
        behavior: "action",
        tone: "negative",
        rank: "escape",
      },
      {
        name: "Accept",
        detail: "primary · positive action",
        icon: "check",
        behavior: "action",
        tone: "positive",
        rank: "primary",
      },
      {
        name: "Reject",
        detail: "secondary · negative action",
        icon: "cross",
        behavior: "action",
        tone: "negative",
        rank: "secondary",
      },
      {
        name: "Thread",
        detail: "reading · neutral disclosure",
        icon: "comment",
        behavior: "disclosure",
        tone: "neutral",
        rank: "reading",
      },
      {
        name: "More",
        detail: "overflow · neutral disclosure",
        icon: "more",
        behavior: "disclosure",
        tone: "neutral",
        rank: "overflow",
      },
      {
        name: "Sent",
        detail: "reading · neutral status",
        icon: "sent",
        behavior: "status",
        tone: "neutral",
        rank: "reading",
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
  const item = generated("div", "margin-entry-gallery-item");
  item.dataset.marginEntrySpecimen = specimen.name.toLowerCase();
  const behavior = specimen.behavior ?? "action";
  const control = marginEntry(
    offer(behavior === "status" ? "span" : "button", "margin-entry-gallery-face"),
    {
      key: `gallery-${groupIndex}-${specimenIndex}`,
      label: specimen.name,
      icon: specimen.icon,
      behavior,
      tone: specimen.tone ?? "neutral",
      rank: specimen.rank ?? "primary",
      state: specimen.state ?? "idle",
    },
  );
  if (control instanceof HTMLButtonElement) control.disabled = true;
  if (behavior !== "status") control.setAttribute("aria-disabled", "true");

  const copy = generated("span", "margin-entry-gallery-copy");
  copy.append(
    generated("span", "margin-entry-gallery-name", specimen.name),
    generated("span", "margin-entry-gallery-detail", specimen.detail),
  );
  item.append(control, copy);
  return item;
}

function groupNode(group, groupIndex) {
  const row = generated("div", "margin-entry-gallery-group");
  const introduction = generated("div", "margin-entry-gallery-introduction");
  introduction.append(
    generated("strong", "margin-entry-gallery-heading", group.heading),
    generated("span", "margin-entry-gallery-summary", group.summary),
  );
  const items = generated("div", "margin-entry-gallery-items");
  items.append(
    ...group.specimens.map((specimen, specimenIndex) =>
      specimenNode(specimen, groupIndex, specimenIndex),
    ),
  );
  row.append(introduction, items);
  return row;
}

customElements.define(
  "lf-margin-entry-gallery",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.append(...GROUPS.map(groupNode));
    }
  },
);
