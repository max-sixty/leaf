/* Lit view for the margin-entry exhibit, constructed during widget setup. */
import { html, ref } from "/runtime/widget-api.js";
import { offerActionElement, generatedElement } from "/runtime/widget-api.js";
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
    summary: "My turn · awaiting agent · delivered · working · awaiting continuation",
    samples: [
      {
        name: "My turn",
        detail: "Thread · my answer is needed",
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
        name: "Waiting for delivery",
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
        name: "Delivered",
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

export function createView(host) {
  const samples = GROUPS.map((group, groupIndex) =>
    group.samples.map((sample, sampleIndex) => ({
      sample,
      key: `${host.id}-gallery-${groupIndex}-${sampleIndex}`,
      control: null,
      disclosure: null,
    })),
  );
  const mark = ref((node) => node && generatedElement(node, { says: false }));
  const face = (entry) =>
    ref((node) => {
      if (node)
        entry.control = offerActionElement(
          node,
          "entry",
          "margin-entry-gallery-face lf-margin-entry",
        );
    });
  const sampleView = (entry) => {
    const { sample, key } = entry;
    return html`<div
      class="margin-entry-gallery-item"
      data-margin-entry-sample=${sample.name.toLowerCase()}
    >
      ${
        sample.behavior === "status"
          ? html`<span ${face(entry)} aria-label=${sample.name}></span>`
          : html`<button
              ${face(entry)}
              type="button"
              disabled
              aria-label=${sample.name}
            ></button>`
      }
      <span class="margin-entry-gallery-copy">
        <span class="margin-entry-gallery-name" ${mark}>${sample.name}</span>
        <span class="margin-entry-gallery-detail" ${mark}>${sample.detail}</span>
      </span>
      ${
        sample.interactive
          ? html`<span
              class="margin-entry-gallery-disclosure"
              ${mark}
              ${ref((node) => {
                if (node) entry.disclosure = node;
              })}
              id=${`${key}-disclosure`}
              ?hidden=${!sample.expanded}
              >${sample.reveals}</span
            >`
          : null
      }
    </div>`;
  };
  const view = {
    samples: samples.flat(),
    result: null,
    render: () =>
      html`${GROUPS.map(
          (group, index) => html`
            <div class="margin-entry-gallery-group">
              <div class="margin-entry-gallery-introduction">
                <strong class="margin-entry-gallery-heading" ${mark}
                  >${group.heading}</strong
                >
                <span class="margin-entry-gallery-summary" ${mark}
                  >${group.summary}</span
                >
              </div>
              <div class="margin-entry-gallery-items">
                ${samples[index].map(sampleView)}
              </div>
            </div>
          `,
        )}
        <div class="margin-entry-gallery-projection">
          <strong class="margin-entry-gallery-heading" ${mark}>Projection</strong>
          <span class="margin-entry-gallery-summary" ${mark}
            >Compact margin face · full Page Map row</span
          >
          <p class="margin-entry-gallery-projection-guide" ${mark}>
            Use the live Inspect projection control at this exhibit's margin. Press g
            then Shift+P to find the same disclosure as a labeled Page Map row.
          </p>
          <p
            class="margin-entry-gallery-projection-result"
            ${mark}
            ${ref((node) => {
              if (node) view.result = node;
            })}
            id=${`${host.id}-projection-result`}
            hidden
          >
            The same contributed action serves both projections.
          </p>
        </div>`,
  };
  host.replaceChildren();
  return view;
}
