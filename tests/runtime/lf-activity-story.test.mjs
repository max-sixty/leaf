/* The activity feed's update as a story (`Story`, @effect/ui/testing): what its notice
   and a thread's row ask of Leaf, and what the feed remembers, with no page, element or
   Leaf behind it. The drawing on a page, held arrivals included, is the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { OpenThread, ShowHeld } from "/runtime/widget-services.js";
import { Activity } from "../../packages/default/widgets/lf-activity.js";

/** @param {string} id */
const row = (id) => ({
  id,
  ts: "2026-10-21T00:00:00Z",
  actor: "Me",
  what: "commented on",
  label: id,
  thread: `thread-${id}`,
  excerpt: null,
  undone: false,
});
const first = [row("a")];
const props = {
  key: "activity-reading:feed",
  ready: true,
  printing: false,
  current: first,
  held: first,
  baseline: first,
  targets: [],
  initialOpen: false,
};

/** @param {(s: any) => void} steps @param {object} [given] */
const story = (steps, given = {}) =>
  Effect.gen(function* () {
    steps(yield* Story.make(Activity, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

test("the notice opens a shut feed and asks Leaf to show what it holds", () =>
  story((s) => {
    s.send({ _tag: "ClickedNotice" })
      .expectExact(ShowHeld.make())
      .resolve(ShowHeld, Component.noop);
    assert.equal(s.model.open, true);
  }));

test("closing an open feed remembers the rows it showed, to count arrivals against", () =>
  story(
    (s) => {
      s.send({ _tag: "ClickedNotice" })
        .expectExact(ShowHeld.make())
        .resolve(ShowHeld, Component.noop);
      assert.deepEqual(s.model, { open: false, seen: first });
    },
    { initialOpen: true },
  ));

test("a notice announcing held news opens onto it rather than closing", () =>
  story(
    (s) => {
      s.send({ _tag: "ClickedNotice" })
        .expectExact(ShowHeld.make())
        .resolve(ShowHeld, Component.noop);
      assert.deepEqual(s.model, { open: true, seen: null });
    },
    { initialOpen: true, current: [row("b"), ...first] },
  ));

test("a thread's row asks Leaf to open that thread", () =>
  story((s) => {
    s.send({ _tag: "ClickedThread", id: "thread-a" })
      .expectExact(OpenThread.make({ id: "thread-a" }))
      .resolve(OpenThread, Component.noop);
  }));
