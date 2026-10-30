/* The exhibit grid and its contribution controls share one live Lit view. */
import { render } from "/runtime/widget-api.js";
import { createView } from "../margin-entry-gallery-view.js";
import {
  contributionEntry,
  once,
  presentContributionEntry,
  presentContributionReceipts,
  registerContribution,
  whileConnected,
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
        relation: disclosure ? { kind: "element", id: disclosure.id, expanded } : null,
      }),
      { selected: sample.selected ?? false },
    );
    presentContributionReceipts(
      control,
      sample.workflowStage
        ? {
            id: key,
            subject: { kind: "widget", id: key },
            stage: sample.workflowStage,
            detail: "",
          }
        : null,
      sample.awaitsUser ?? false,
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
    connectedCallback() {
      if (!once(this)) return;
      const initial = createView(this);
      render(initial.render(), this);
      initial.samples.forEach(wireSample);
      whileConnected(this, () => {
        const projection = this.#registerProjection(initial.result);
        return () => projection.unregister();
      });
    }

    #registerProjection(result) {
      const projection = registerContribution({
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
          projection.update({ immediate: true });
        },
      });
      return projection;
    }
  },
);
