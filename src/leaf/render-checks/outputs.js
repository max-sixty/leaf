/* Check-only observation across page and sample realms. A widget holds each output
 * it declares as a property, which its readers read again at each `change` the
 * element hears (data.js), so this reads the declared properties of each element a
 * `change` reaches, as the event passes the window, and reports each value before a
 * later change replaces or withdraws it. It reads on the event's way in, before any
 * listener in the page, and where the event bubbles, again on its way out, after the
 * listener that may have set the value a reader read. The
 * Playwright binding keeps each value outside the frame, so reset/disposal cannot
 * erase a violation. A value is copied before it is counted, so one that can't be
 * copied throws here, as the page's error, and leaves the count as it was. A producer
 * standing in a shadow stage is heard only where its `change` is composed and its
 * stage open, since no other `change` reaches the window with its own target. */
import { declarationFor } from "/runtime/check-api.js";

let reporting = 0;
export function observeOutputValues() {
  /** @param {Event} event */
  const read = (event) => {
    // Each element the event reaches: the one that said it, which a shadow host
    // stands in for as `target`, and where it bubbles, each element round that one.
    const path = event.composedPath();
    for (const heard of event.bubbles ? path : path.slice(0, 1)) {
      if (!(heard instanceof Element)) continue;
      const outputs = declarationFor(heard)?.outputs ?? {};
      for (const [output, { contract }] of Object.entries(outputs)) {
        const held = /** @type {Record<string, unknown>} */ (
          /** @type {unknown} */ (heard)
        )[output];
        if (held === null || held === undefined) continue;
        const value = structuredClone(held);
        reporting += 1;
        globalThis
          .__leafOutputValue({
            tag: heard.localName,
            id: heard.id,
            output,
            contract,
            value,
          })
          .finally(() => {
            reporting -= 1;
          });
      }
    }
  };
  addEventListener("change", read, true);
  addEventListener("change", read);
}

export const outputsReported = () => reporting === 0;
