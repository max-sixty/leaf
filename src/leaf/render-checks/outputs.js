/* Check-only observation across page and sample realms. A widget holds each output
 * it declares as a property and says `change` when it moves, so this reads the
 * declared properties of whichever element says so, as the event passes the window,
 * and reports each value before a later change replaces or withdraws it. The
 * Playwright binding keeps each value outside the frame, so reset/disposal cannot
 * erase a violation. An output held inside a shadow tree is heard only where its
 * `change` is composed. */
import { declarationFor } from "/runtime/check-api.js";

let reporting = 0;
export function observeOutputValues() {
  addEventListener(
    "change",
    ({ target }) => {
      if (!(target instanceof Element)) return;
      const outputs = declarationFor(target, "x-output") ?? {};
      for (const [output, { contract }] of Object.entries(outputs)) {
        const value = /** @type {Record<string, unknown>} */ (
          /** @type {unknown} */ (target)
        )[output];
        if (value === null || value === undefined) continue;
        reporting += 1;
        globalThis
          .__leafOutputValue({
            tag: target.localName,
            id: target.id,
            output,
            contract,
            value: structuredClone(value),
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
