/* One tally drawing from first paint through live updates. The hidden rooms hold
 * the widest words without exposing an inventory before the server has read it.
 * The behavior module supplies words and the Next action to this retained closure,
 * keeping both the initial template identity and its native control. */
import { html, nothing, ref, render } from "/vendor/lit.js";

export function initialTally(host, { generatedElement, offerActionElement, keeps }) {
  const next = host.hasAttribute("next");
  let advance = null;
  const mark = (node) => node && generatedElement(node, { says: false });
  const control = (node) => node && offerActionElement(node, "word", "lf-tally-next");
  const paint = (
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
    render(
      html`<span class="lf-tally-face" ${ref(mark)}>
        <span class=${done ? "lf-tally-count lf-tally-done" : "lf-tally-count"}>
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
      </span>`,
      host,
    );
  };
  host.replaceChildren();
  paint();
  return { paint };
}
