/* The margin-entry exhibit's one grid producer. It runs while the authored document
 * arrives, before widget upgrade, so labels wrap in the actual viewer's fonts and
 * column. Upgrade adopts these nodes and adds the runtime's contribution paint and
 * handlers; the fixed face hosts use that paint's shared geometry from first paint. */

const GROUPS = [
  {
    heading: "Rank and behavior",
    summary: "Every action and disclosure rank · every tone",
    samples: [
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
    heading: "Turn and agent workflow",
    summary: "On you · awaiting agent · picked up · working · awaiting continuation",
    samples: [
      {
        name: "On you",
        detail: "Thread · your answer is needed",
        icon: "comment",
        behavior: "disclosure",
        rank: "reading",
        awaitsUser: true,
      },
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
        name: "Update stale",
        detail: "work went quiet · awaiting continuation",
        icon: "activity",
        behavior: "disclosure",
        rank: "reading",
      },
      {
        name: "Turn ended",
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
    samples: [
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
    heading: "User interaction",
    summary: "Resting · hover or focus · open · selected",
    samples: [
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

function render(host, { offer }) {
  const labels = [];
  const samples = [];
  const generated = (tag, className, words = null) => {
    const node = document.createElement(tag);
    node.className = className;
    if (words !== null) {
      node.textContent = words;
      labels.push({ node, words });
    }
    return node;
  };

  const sampleNode = (sample, groupIndex, sampleIndex) => {
    const item = generated("div", "margin-entry-gallery-item");
    item.dataset.marginEntrySample = sample.name.toLowerCase();
    const key = `${host.id}-gallery-${groupIndex}-${sampleIndex}`;
    const control = offer(
      sample.behavior === "status" ? "span" : "button",
      "margin-entry-gallery-face lf-margin-entry",
    );
    control.setAttribute("aria-label", sample.name);
    if (control instanceof HTMLButtonElement) {
      control.type = "button";
      control.disabled = true;
    }
    let disclosure = null;
    if (sample.interactive) {
      disclosure = generated("span", "margin-entry-gallery-disclosure", sample.reveals);
      disclosure.id = `${key}-disclosure`;
      disclosure.hidden = !sample.expanded;
    }
    const copy = generated("span", "margin-entry-gallery-copy");
    copy.append(
      generated("span", "margin-entry-gallery-name", sample.name),
      generated("span", "margin-entry-gallery-detail", sample.detail),
    );
    item.append(control, copy, ...(disclosure ? [disclosure] : []));
    samples.push({ sample, key, control, disclosure });
    return item;
  };

  const groupNode = (group, groupIndex) => {
    const row = generated("div", "margin-entry-gallery-group");
    const introduction = generated("div", "margin-entry-gallery-introduction");
    introduction.append(
      generated("strong", "margin-entry-gallery-heading", group.heading),
      generated("span", "margin-entry-gallery-summary", group.summary),
    );
    const items = generated("div", "margin-entry-gallery-items");
    items.append(
      ...group.samples.map((sample, index) => sampleNode(sample, groupIndex, index)),
    );
    row.append(introduction, items);
    return row;
  };

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
  result.id = `${host.id}-projection-result`;
  result.hidden = true;
  projection.append(result);
  host.append(...GROUPS.map(groupNode), projection);
  return { samples, labels, result };
}

document.documentElement.lfInitial.register("lf-margin-entry-gallery", render);
