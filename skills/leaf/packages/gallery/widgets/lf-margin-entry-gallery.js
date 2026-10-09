/* The early renderer owns the exhibit grid and words. This upgrade adopts its
 * controls, adds the public margin-entry paint and behavior, and registers one live
 * action shared by the exhibit's compact margin face and full Page Map row. */
import {
  contributionEntry,
  initialRender,
  once,
  presentContributionEntry,
  registerContribution,
  relabel,
} from "/runtime/widget-api.js";

function wireSample({ sample, key, control, disclosure }) {
  const behavior = sample.behavior ?? "action";
  let expanded = Boolean(sample.expanded);
  const paint = () => {
    presentContributionEntry(
      control,
      contributionEntry({
        key,
        label: sample.name,
        ...(sample.icon ? { icon: sample.icon } : { glyph: sample.glyph }),
        context: sample.context,
        behavior,
        tone: sample.tone ?? "neutral",
        rank: sample.rank ?? "primary",
        state: sample.state ?? "idle",
        count: sample.count ?? 1,
        disabled: !sample.interactive,
        workflowReceipt: sample.workflowStage
          ? {
              id: key,
              subject: { kind: "widget", id: key },
              stage: sample.workflowStage,
              detail: "",
            }
          : null,
        relation: disclosure ? { kind: "element", id: disclosure.id, expanded } : null,
      }),
      {
        selected: sample.selected ?? false,
        awaitsUser: sample.awaitsUser ?? false,
      },
    );
  };
  paint();
  if (sample.showLabel) control.dataset.marginEntryLabelLive = "";
  if (disclosure) {
    control.addEventListener("click", () => {
      expanded = !expanded;
      disclosure.hidden = !expanded;
      paint();
    });
  }
}

customElements.define(
  "lf-margin-entry-gallery",
  class extends HTMLElement {
    #projection = null;

    connectedCallback() {
      if (once(this)) {
        const initial = initialRender(this);
        for (const { node, words } of initial.labels)
          relabel(node, words, { says: false });
        initial.samples.forEach(wireSample);
      }
      this.#registerProjection();
    }

    disconnectedCallback() {
      this.#projection?.unregister();
      this.#projection = null;
    }

    #registerProjection() {
      if (this.#projection) return;
      const result = initialRender(this).result;
      this.#projection = registerContribution({
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
