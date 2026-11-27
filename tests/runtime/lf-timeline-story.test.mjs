/* The timeline's update as a story (`Story`, @effect/ui/testing): where a press puts
   the step, and what it asks of Leaf, with no page, element or Leaf behind it. The
   drawing is lf-timeline.test.mjs's and the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { Announce, KeepInTab } from "/runtime/widget-services.js";
import {
  Timeline,
  TimelineMessage,
  readTimeline,
} from "../../packages/timeline/widgets/lf-timeline.js";

const host = document.createElement("div");
host.innerHTML =
  '<lf-lane label="Job A"><lf-event id="a-read" at="0" label="Reads"></lf-event>' +
  '<lf-event id="a-write" at="4200" label="Writes"></lf-event></lf-lane>' +
  '<lf-lane label="Job B"><lf-event id="b-read" at="1000" label="Reads"></lf-event>' +
  '<lf-event id="b-write" at="4200" label="Writes too"></lf-event></lf-lane>';
const props = {
  id: "race",
  label: "The race",
  reading: readTimeline(host),
  saved: null,
};

/** @param {(s: any) => void} story @param {object} [given] */
const tell = (story, given = props) =>
  Effect.gen(function* () {
    story(yield* Story.make(Timeline, given));
  }).pipe(Effect.scoped, Effect.runSync);

test("Next keeps the step it reached for the tab and says it aloud", () => {
  tell((s) => {
    s.send(TimelineMessage.PressedStepControl({ step: 1 }))
      .expectExact(
        KeepInTab.make({ key: "timeline:race", value: "1000" }),
        Announce.make({ words: "Step 2 of 3. Job B: Reads" }),
      )
      .resolve(KeepInTab, Component.noop)
      .resolve(Announce, Component.noop);
    assert.equal(s.model.current, 1);
    // Every event of the step is said, in lane order.
    s.send(TimelineMessage.PressedStepControl({ step: 9 }))
      .expectExact(
        KeepInTab.make({ key: "timeline:race", value: "4200" }),
        Announce.make({ words: "Step 3 of 3. Job A: Writes; Job B: Writes too" }),
      )
      .resolve(KeepInTab, Component.noop)
      .resolve(Announce, Component.noop);
    assert.equal(s.model.current, 2, "a step past the end clamps to the last");
  });
});

test("A row, a mark or a comment's event moves the step without a word", () => {
  tell((s) => {
    s.send(TimelineMessage.PickedStep({ step: 2 }))
      .expectExact(KeepInTab.make({ key: "timeline:race", value: "4200" }))
      .resolve(KeepInTab, Component.noop);
    s.send(TimelineMessage.RevealedEvent({ step: 0 }))
      .expectExact(KeepInTab.make({ key: "timeline:race", value: "0" }))
      .resolve(KeepInTab, Component.noop);
    assert.equal(s.model.current, 0);
  });
});

test("A press that stays on the step asks nothing", () => {
  tell((s) => {
    s.send(TimelineMessage.PressedStepControl({ step: -1 }));
    s.send(TimelineMessage.PickedStep({ step: 0 }));
    assert.equal(s.model.current, 0);
  });
});

test("The timeline opens at the step the tab kept, by its time", () => {
  tell(
    (s) => {
      assert.equal(s.model.current, 1);
    },
    { ...props, saved: 1000 },
  );
  // A kept time no step stands at any more opens the timeline at its start.
  tell(
    (s) => {
      assert.equal(s.model.current, 0);
    },
    { ...props, saved: 300 },
  );
});

test("The ruler's measure lays the labels out once per width and font", () => {
  tell((s) => {
    s.send(TimelineMessage.MeasuredRuler({ width: 600, font: "600 12px serif" }));
    const laidOut = s.model;
    assert.deepEqual(laidOut.ruler, { width: 600, font: "600 12px serif" });
    s.send(TimelineMessage.MeasuredRuler({ width: 600, font: "600 12px serif" }));
    assert.equal(s.model, laidOut);
  });
});
