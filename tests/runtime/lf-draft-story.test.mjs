/* The draft's update as a story (`Story`, @effect/ui/testing): what the toolbar draws
   from what its editor reports, with no page, element or Leaf behind it. The editor and
   the save are the browser suite's (tests/browser/drafts). */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Effect } from "/vendor/effect-ui.js";
import { Draft } from "../../packages/default/widgets/lf-draft.js";

const props = { exhibit: false, named: "the draft" };
const rest = {
  editing: false,
  sending: false,
  failed: false,
  typing: false,
  pointed: false,
};

/** @param {(s: any) => void} steps */
const story = (steps) =>
  Effect.gen(function* () {
    steps(yield* Story.make(Draft, props));
  }).pipe(Effect.scoped, Effect.runSync);

test("typing puts the toolbar away until the pointer rests on it", () =>
  story((s) => {
    s.send({ _tag: "OpenedEditor" }).send({ _tag: "TypedInEditor" });
    assert.deepEqual(s.model, { ...rest, editing: true, typing: true });
    s.send({ _tag: "PointedAtTools" });
    assert.equal(s.model.pointed, true);
    s.send({ _tag: "KeptTools" });
    assert.deepEqual(s.model, { ...rest, editing: true });
  }));

test("a refused save shows Retry on the reopened editor until the user types", () =>
  story((s) => {
    s.send({ _tag: "OpenedEditor" })
      .send({ _tag: "StartedSave" })
      .send({ _tag: "ClosedEditor" })
      .send({ _tag: "RefusedSave" })
      .send({ _tag: "OpenedEditor" });
    assert.deepEqual(s.model, { ...rest, editing: true, failed: true });
    s.send({ _tag: "TypedInEditor" });
    assert.equal(s.model.failed, false);
  }));

test("closing the editor gives the toolbar back at rest", () =>
  story((s) => {
    s.send({ _tag: "OpenedEditor" })
      .send({ _tag: "TypedInEditor" })
      .send({ _tag: "PointedAtTools" })
      .send({ _tag: "ClosedEditor" });
    assert.deepEqual(s.model, rest);
  }));
