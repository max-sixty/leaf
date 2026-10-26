/* Check-only observation across page and sample realms. The Playwright binding
 * keeps each value outside the frame, so reset/disposal cannot erase a violation. */
import { observeOutputs } from "/runtime/check-api.js";

let reporting = 0;
export function observeOutputValues() {
  observeOutputs(({ element, output, contract, value }) => {
    if (value === null) return;
    reporting += 1;
    globalThis
      .__leafOutputValue({
        tag: element.localName,
        id: element.id,
        output,
        contract,
        value: structuredClone(value),
      })
      .finally(() => {
        reporting -= 1;
      });
  });
}

export const outputsReported = () => reporting === 0;
