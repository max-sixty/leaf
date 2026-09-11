/* A fixed developer exhibit of margin entry controls and agent ownership. It uses
 * the public marginEntry and ownership helpers rather than reproducing anatomy or
 * paint; the package owns only the comparison grid and the words naming each cell. */
import {
  marginEntry,
  once,
  offer,
  relabel,
  syncMarginAgentPhase,
} from "/runtime/widget-api.js";

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
    heading: "Agent ownership",
    summary: "Not held, picked up, working · whether the agent has the item",
    specimens: [
      {
        name: "Not held",
        detail: "Thread · neutral ring",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
      },
      {
        name: "Picked up",
        detail: "Thread · single blue ring",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        agentPhase: "picked_up",
      },
      {
        name: "Working",
        detail: "Thread · green double ring",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        agentPhase: "active",
      },
      {
        name: "Working alone",
        detail: "Activity dot · no other control can carry it",
        icon: "activity",
        behavior: "disclosure",
        rank: "reading",
        agentPhase: "active",
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
  const key = `gallery-${groupIndex}-${specimenIndex}`;
  const control = marginEntry(
    offer(behavior === "status" ? "span" : "button", "margin-entry-gallery-face"),
    {
      key,
      label: specimen.name,
      icon: specimen.icon,
      behavior,
      tone: specimen.tone ?? "neutral",
      rank: specimen.rank ?? "primary",
      state: specimen.state ?? "idle",
    },
  );
  if (specimen.agentPhase)
    syncMarginAgentPhase(control, {
      id: key,
      target: { kind: "widget", id: key },
      phase: specimen.agentPhase,
    });
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
