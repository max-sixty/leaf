/* Check-only observation across page and sample realms. A widget holds each output
 * it declares as a property and says `change` when it moves, so this reads the
 * declared properties of whichever element says so, as the event passes the window,
 * and reports each value before a later change replaces or withdraws it. The
 * Playwright binding keeps each value outside the frame, so reset/disposal cannot
 * erase a violation. A value is copied before it is counted, so one that can't be
 * copied throws here, as the page's error, and leaves the count as it was. A producer
 * standing in a shadow stage is heard only where its `change` is composed and its
 * stage open, since no other `change` reaches the window with its own target. */
import { declarationFor } from "/runtime/check-api.js";

let reporting = 0;
export function observeOutputValues() {
  addEventListener(
    "change",
    (event) => {
      // The element that said it, which a shadow host stands in for as `target`.
      const [said] = event.composedPath();
      if (!(said instanceof Element)) return;
      const outputs = declarationFor(said)?.outputs ?? {};
      for (const [output, { contract }] of Object.entries(outputs)) {
        const held = /** @type {Record<string, unknown>} */ (
          /** @type {unknown} */ (said)
        )[output];
        if (held === null || held === undefined) continue;
        const value = structuredClone(held);
        reporting += 1;
        globalThis
          .__leafOutputValue({
            tag: said.localName,
            id: said.id,
            output,
            contract,
            value,
          })
          .finally(() => {
            reporting -= 1;
          });
      }
    },
    true,
  );
}

export const outputsReported = () => reporting === 0;
