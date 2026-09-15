/* A developer exhibit of the complete margin-entry face and its projection.
 * It uses the public immutable margin-entry reading and presentation helpers
 * rather than reproducing anatomy or paint. The package owns only the comparison grid,
 * the words naming each cell, and one local disclosure that makes the compact margin
 * control and its full Page Map row directly exercisable. */
import {
  marginEntry,
  once,
  offer,
  presentMarginEntry,
  registerMarginContribution,
  relabel,
} from "/runtime/widget-api.js";

const GROUPS = [
  {
    heading: "Rank and behavior",
    summary: "Every action and disclosure rank · every tone",
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
    ],
  },
  {
    heading: "Agent workflow",
    summary: "Awaiting agent · picked up · working · awaiting continuation",
    specimens: [
      {
        name: "Sent",
        detail: "recorded · awaiting agent",
        icon: "sent",
        behavior: "status",
        rank: "reading",
      },
      {
        name: "Waiting for pickup",
        detail: "unaccepted after the grace period",
        icon: "waiting",
        behavior: "status",
        rank: "reading",
      },
      {
        name: "Queued",
        detail: "accepted for a later turn",
        icon: "pickup",
        behavior: "status",
        rank: "reading",
      },
      {
        name: "Picked up",
        detail: "Thread · agent turn opened",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        workflowStage: "picked_up",
      },
      {
        name: "Working",
        detail: "Thread · agent preparing it",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        workflowStage: "working",
      },
      {
        name: "Was working",
        detail: "claim quiet · awaiting continuation",
        icon: "activity",
        behavior: "disclosure",
        rank: "reading",
      },
      {
        name: "Picked up · turn ended",
        detail: "unsettled · awaiting continuation",
        icon: "waiting",
        behavior: "status",
        rank: "reading",
      },
      {
        name: "Working · fallback",
        detail: "no target control available",
        icon: "activity",
        behavior: "disclosure",
        rank: "reading",
        workflowStage: "working",
      },
    ],
  },
  {
    heading: "Face anatomy",
    summary: "Icon or glyph · count badge · transient label and context",
    specimens: [
      {
        name: "Glyph face",
        detail: "author-supplied glyph",
        glyph: "🤔",
        behavior: "disclosure",
        rank: "reading",
      },
      {
        name: "Count badge",
        detail: "3 related readings",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        count: 3,
      },
      {
        name: "Label + context",
        detail: "hover or focus reveals both lines",
        icon: "question",
        behavior: "disclosure",
        rank: "reading",
        context: "Patch ready",
        interactive: true,
        reveals: "Patch context revealed.",
        showLabel: true,
      },
    ],
  },
  {
    heading: "Reader interaction",
    summary: "Resting · hover or focus · open · selected",
    specimens: [
      {
        name: "Resting",
        detail: "neutral disclosure",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
      },
      {
        name: "Hover or focus",
        detail: "direct pointer and keyboard feedback",
        icon: "question",
        behavior: "disclosure",
        rank: "reading",
        context: "Inspect the source",
        interactive: true,
        reveals: "Source context revealed.",
        showLabel: true,
      },
      {
        name: "Open",
        detail: "expanded disclosure",
        icon: "question",
        behavior: "disclosure",
        rank: "reading",
        expanded: true,
        interactive: true,
        reveals: "Source context revealed.",
      },
      {
        name: "Selected",
        detail: "Thread · accent border",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        selected: true,
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
  const control = offer(
    behavior === "status" ? "span" : "button",
    "margin-entry-gallery-face",
  );
  let expanded = Boolean(specimen.expanded);
  let disclosure = null;
  if (specimen.interactive) {
    disclosure = generated("span", "margin-entry-gallery-disclosure", specimen.reveals);
    disclosure.id = `${key}-disclosure`;
  }
  const paint = () => {
    if (disclosure) disclosure.hidden = !expanded;
    presentMarginEntry(
      control,
      marginEntry({
        key,
        label: specimen.name,
        ...(specimen.icon ? { icon: specimen.icon } : { glyph: specimen.glyph }),
        context: specimen.context,
        behavior,
        tone: specimen.tone ?? "neutral",
        rank: specimen.rank ?? "primary",
        state: specimen.state ?? "idle",
        count: specimen.count ?? 1,
        disabled: !specimen.interactive,
        workflowReceipt: specimen.workflowStage
          ? {
              id: key,
              target: { kind: "widget", id: key },
              phase:
                specimen.workflowStage === "working"
                  ? "active"
                  : specimen.workflowStage,
            }
          : null,
        relation: disclosure ? { kind: "element", id: disclosure.id, expanded } : null,
      }),
      { selected: specimen.selected ?? false },
    );
  };
  paint();
  if (specimen.showLabel) control.dataset.marginEntryLabelLive = "";
  if (disclosure) {
    control.addEventListener("click", () => {
      expanded = !expanded;
      paint();
    });
  }

  const copy = generated("span", "margin-entry-gallery-copy");
  copy.append(
    generated("span", "margin-entry-gallery-name", specimen.name),
    generated("span", "margin-entry-gallery-detail", specimen.detail),
  );
  item.append(control, copy, ...(disclosure ? [disclosure] : []));
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
    #projection = null;

    connectedCallback() {
      if (once(this)) {
        const projection = generated("div", "margin-entry-gallery-projection");
        projection.append(
          generated("strong", "margin-entry-gallery-heading", "Projection"),
          generated(
            "span",
            "margin-entry-gallery-summary",
            "Compact margin face · full Page Map row",
          ),
          generated(
            "p",
            "margin-entry-gallery-projection-guide",
            "Use the live Inspect projection control at this exhibit's margin. Press g then Shift+M to find the same disclosure as a labeled Page Map row.",
          ),
        );
        const result = generated(
          "p",
          "margin-entry-gallery-projection-result",
          "The same contributed action serves both projections.",
        );
        result.id = `${this.id}-projection-result`;
        result.hidden = true;
        projection.append(result);
        this.append(...GROUPS.map(groupNode), projection);
      }
      this.#registerProjection();
    }

    disconnectedCallback() {
      this.#projection?.unregister();
      this.#projection = null;
    }

    #registerProjection() {
      if (this.#projection) return;
      const result = this.querySelector(".margin-entry-gallery-projection-result");
      this.#projection = registerMarginContribution({
        key: `gallery-projection:${this.id}`,
        target: () => this,
        read: () => ({
          subject: "Margin entry projection",
          entries: [
            {
              key: "inspect-projection",
              icon: "question",
              label: "Inspect projection",
              context: "Compact face · full row",
              behavior: "disclosure",
              rank: "reading",
              relation: { kind: "element", id: result.id, expanded: !result.hidden },
            },
          ],
          readings: [],
        }),
        activate: () => {
          result.hidden = !result.hidden;
          this.#projection.update({ immediate: true });
        },
      });
    }
  },
);
