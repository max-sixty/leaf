/* The motion study's update as a story (`Story`, @effect/ui/testing): what the clock
   does with the user's presses, the frames it is sent and what its mount reads, with no
   page, element or Leaf behind it. The drawing and the recordings on a page are the
   browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { KeepInTab } from "/runtime/widget-services.js";
import { Motion, MotionMessage } from "../../packages/motion/widgets/lf-motion.js";

const props = {
  key: "motion:study",
  duration: 1000,
  label: "A study",
  saved: null,
  renderFrame: () => {},
};

/** @param {(s: any) => void} steps @param {object} [given] */
const story = (steps, given = {}) =>
  Effect.gen(function* () {
    steps(yield* Story.make(Motion, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

const kept = (/** @type {number} */ time, rate = 1) =>
  KeepInTab.make({ key: "motion:study", value: JSON.stringify({ time, rate }) });

test("the study starts paused where the tab kept it", () =>
  story(
    (s) =>
      assert.deepEqual(
        [s.model.time, s.model.rate, s.model.playing],
        [250, 0.5, false],
      ),
    { saved: { time: 250, rate: 0.5 } },
  ));

test("Play runs the clock on animation frames at the chosen speed, to rest at the end", () =>
  story((s) => {
    s.send(MotionMessage.ChoseRate({ rate: 0.5 }))
      .expectExact(kept(0, 0.5))
      .resolve(KeepInTab, Component.noop);
    s.send(MotionMessage.ClickedPlay());
    assert.equal(s.model.playing, true);
    s.send(MotionMessage.TickedFrame({ delta: 400 }));
    assert.equal(s.model.time, 200);
    s.send(MotionMessage.TickedFrame({ delta: 2000 }))
      .expectExact(kept(1000, 0.5))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual([s.model.time, s.model.playing], [1000, false]);
    // Play at the end starts again from the beginning.
    s.send(MotionMessage.ClickedPlay());
    assert.deepEqual([s.model.time, s.model.playing], [0, true]);
  }));

test("the user's own input pauses playback and keeps where it stopped", () =>
  story((s) => {
    s.send(MotionMessage.ClickedPlay());
    s.send(MotionMessage.TickedFrame({ delta: 120 }));
    s.send(MotionMessage.Interrupted())
      .expectExact(kept(120))
      .resolve(KeepInTab, Component.noop);
    assert.equal(s.model.playing, false);
  }));

test("seeking pauses, clamps to the duration and clears a failed playback", () =>
  story(
    (s) => {
      s.send(MotionMessage.FoundVideos({ any: true }));
      s.send(MotionMessage.ClickedPlay());
      s.send(MotionMessage.FailedPlayback())
        .expectExact(kept(0))
        .resolve(KeepInTab, Component.noop);
      assert.deepEqual([s.model.failure, s.model.playing], ["Failed", false]);
      s.send(MotionMessage.Sought({ time: 5000 }))
        .expectExact(kept(1000))
        .resolve(KeepInTab, Component.noop);
      assert.deepEqual([s.model.time, s.model.failure], [1000, null]);
    },
    { renderFrame: undefined },
  ));

test("recordings keep the time while they play, and their end stops the clock", () =>
  story(
    (s) => {
      s.send(MotionMessage.FoundVideos({ any: true }));
      s.send(MotionMessage.ClickedPlay());
      // The recordings' clock, not the frame's, moves the time.
      s.send(MotionMessage.TickedFrame({ delta: 400 }));
      assert.equal(s.model.time, 0);
      s.send(MotionMessage.ReadVideos({ time: 330, ended: false }));
      assert.deepEqual([s.model.time, s.model.playing], [330, true]);
      s.send(MotionMessage.ReadVideos({ time: 990, ended: true }))
        .expectExact(kept(1000))
        .resolve(KeepInTab, Component.noop);
      assert.deepEqual([s.model.time, s.model.playing], [1000, false]);
    },
    { renderFrame: undefined },
  ));

test("a study with nothing to play takes no press", () =>
  story(
    (s) => {
      s.send(MotionMessage.ClickedPlay());
      assert.equal(s.model.playing, false);
    },
    { renderFrame: undefined },
  ));

test("a frame that fails to draw stops the clock until one draws", () =>
  story((s) => {
    s.send(MotionMessage.ClickedPlay());
    s.send(MotionMessage.FailedDraw({ message: "the frame broke" }))
      .expectExact(kept(0))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual([s.model.broken, s.model.playing], ["the frame broke", false]);
    s.send(MotionMessage.Drew());
    assert.equal(s.model.broken, null);
  }));

test("under reduced motion Play shows the end, and asking for less motion ends playback", () =>
  story((s) => {
    s.send(MotionMessage.ClickedPlay());
    s.send(MotionMessage.ChangedMotion({ reduced: true }))
      .expectExact(kept(1000))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual([s.model.time, s.model.playing], [1000, false]);
    s.send(MotionMessage.Sought({ time: 0 }))
      .expectExact(kept(0))
      .resolve(KeepInTab, Component.noop);
    s.send(MotionMessage.ClickedPlay())
      .expectExact(kept(1000))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual([s.model.time, s.model.playing], [1000, false]);
  }));
