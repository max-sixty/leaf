/* One tally drawing from first paint through live updates. The hidden rooms hold
 * the widest words without exposing an inventory before the server has read it.
 * The behavior module supplies words and the Next action to this retained template,
 * keeping its native control from parser delivery through live updates. */
import { html, nothing, ref } from "/vendor/lit.js";

export function initialTally(host, { generatedElement, offerActionElement, keeps }) {
  const next = host.hasAttribute("next");
  let advance = null;
  const mark = (node) => node && generatedElement(node, { says: false });
  const control = (node) => node && offerActionElement(node, "word", "lf-tally-next");
  const template = (
    {
      ready = false,
      done = false,
      generic = "00 left to answer · 00 on the agent",
      named = generic,
      words = "",
      onUser = false,
    } = {},
    onNext = null,
  ) => {
    advance = onNext;
    keeps(host, "data-lf-ready", ready ? "" : null);
    return html`<span class="lf-tally-face" ${ref(mark)}>
      <span class=${done ? "lf-tally-count lf-chip ok" : "lf-tally-count lf-chip"}>
        <span class="lf-tally-room" aria-hidden="true">${generic}</span>
        <span class="lf-tally-room" aria-hidden="true">${named}</span>
        <span class="lf-tally-words">${words}</span>
      </span>
      ${
        next
          ? html`<button
              ${ref(control)}
              type="button"
              title="Next on me here"
              aria-controls=${host.getAttribute("for")}
              ?disabled=${!ready || !onUser}
              @mousedown=${(event) => event.preventDefault()}
              @click=${() => advance?.()}
            >
              Next on me
            </button>`
          : nothing
      }
    </span>`;
  };
  host.replaceChildren();
  return { render: template };
}
