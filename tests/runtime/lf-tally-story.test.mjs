/* The tally's update as a story (`Story`, @effect/ui/testing): what a press asks of
   Leaf, with no page, element or Leaf behind it. The drawing on a page is the browser
   suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { NextOnMe } from "/runtime/widget-services.js";
import { Tally } from "../../packages/default/widgets/lf-tally.js";

const props = {
  next: true,
  ready: true,
  done: false,
  generic: "",
  named: "",
  words: "1 waits on you",
  onUser: 1,
};

test("a press on Next On Me asks Leaf to step within the tally's region", () => {
  const region = { id: "queue" };
  Effect.gen(function* () {
    const s = yield* Story.make(Tally, { ...props, region });
    s.send({ _tag: "ClickedNext" })
      .expectExact(NextOnMe.make({ within: region }))
      .resolve(NextOnMe, Component.noop);
  }).pipe(Effect.scoped, Effect.runSync);
});

test("a press before the region is found asks nothing", () => {
  Effect.gen(function* () {
    const s = yield* Story.make(Tally, props);
    s.send({ _tag: "ClickedNext" });
    assert.deepEqual(s.model, {});
  }).pipe(Effect.scoped, Effect.runSync);
});
