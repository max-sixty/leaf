/* The Python fold generates these cases from authored markup and current state.
   The browser must publish the same typed values, including empty answers, custom
   actions withdrawn by undo, member-unit records and complete position maps. */
import assert from "node:assert/strict";
import test from "node:test";
import { foldWidgetStates, obligationValue } from "/runtime/projection/model.js";

import { servedObligationValues } from "../served.mjs";

const cases = servedObligationValues();

for (const fixture of cases) {
  test(`Obligation value agrees with Python: ${fixture.name}`, () => {
    const authored = new Map([
      [
        "owner",
        {
          state: { set: fixture.authored },
          specs: new Map([["set", fixture.spec]]),
        },
      ],
    ]);
    const projection = {
      desired: new Map(fixture.entries.map((entry) => [entry.coordinate, entry])),
    };
    const widgets = foldWidgetStates(authored, projection);
    assert.deepEqual(
      obligationValue(widgets.get("owner"), "set", fixture.answered, fixture.unit),
      fixture.expected,
    );
  });
}
