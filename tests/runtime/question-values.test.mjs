/* The Python fold generates these cases from authored markup and standing state.
   The browser must publish the same typed values, including empty answers, custom
   actions withdrawn by undo, member-unit records and complete position maps. */
import assert from "node:assert/strict";
import test from "node:test";
import { foldWidgetStates, questionValue } from "/runtime/projection/model.js";

import { servedQuestionValues } from "../served.mjs";

const cases = servedQuestionValues();

for (const fixture of cases) {
  test(`Question value agrees with Python: ${fixture.name}`, () => {
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
      questionValue(widgets.get("owner"), "set", fixture.answered),
      fixture.expected,
    );
  });
}
