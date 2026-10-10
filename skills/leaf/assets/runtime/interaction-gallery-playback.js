/* The developer interaction gallery replays focused demonstrations against real Leaf
 * surfaces in the product gallery. It owns only the illustrative pointer, timing
 * controls, and ephemeral orchestration of each surface's canonical transition.
 * Document-global chrome runs in an opaque sandbox frame so it remains inside the sample;
 * each sequence invokes the surface's canonical transition without dispatching a
 * gesture or writing to the event log. The product gallery opts in with
 * data-interaction-gallery, so ordinary Leaf pages pay no runtime or behavior cost
 * for this developer surface. */

import { nextFrame } from "./rendering.js";
import { keepsHidden, keepsText } from "./keeps.js";
import { registerSampleCommand, sampleNotice } from "./sample-child.js";

const overlayStyle = `
.lf-interaction-overlay { position: fixed; inset: 0; z-index: 2147483647; pointer-events: none; }
.interaction-pointer {
  position: absolute; z-index: 5; top: 0; left: 0;
  width: calc(22px * var(--interaction-overlay-scale));
  height: calc(28px * var(--interaction-overlay-scale));
  background: var(--ink); pointer-events: none;
  transform-origin: calc(2px * var(--interaction-overlay-scale)) calc(2px * var(--interaction-overlay-scale));
  clip-path: polygon(0 0, 78% 71%, 47% 73%, 63% 100%, 49% 100%, 34% 76%, 0 100%);
  filter: drop-shadow(0 calc(1px * var(--interaction-overlay-scale)) 0 var(--paper))
    drop-shadow(0 calc(2px * var(--interaction-overlay-scale)) calc(3px * var(--interaction-overlay-scale)) var(--shade));
  will-change: transform, opacity;
}
.interaction-keypress {
  position: absolute; z-index: 4;
  right: calc(18px * var(--interaction-overlay-scale));
  bottom: calc(18px * var(--interaction-overlay-scale));
  padding: calc(7px * var(--interaction-overlay-scale)) calc(10px * var(--interaction-overlay-scale));
  border: calc(1px * var(--interaction-overlay-scale)) solid var(--border-2); border-radius: calc(8px * var(--interaction-overlay-scale));
  background: var(--card);
  box-shadow: 0 calc(4px * var(--interaction-overlay-scale)) calc(14px * var(--interaction-overlay-scale)) var(--shade);
  color: var(--ink);
  font: 650 calc(var(--t-6) * var(--interaction-overlay-scale)) / 1 var(--sans);
  pointer-events: none;
}
.interaction-pointer[hidden], .interaction-keypress[hidden] { display: none; }
@media print { .lf-interaction-overlay { display: none; } }
`;

class StaleDemo extends Error {}

const ARRIVAL_PAUSE = 900;
const POINTER_TRAVEL = 1400;
const RESULT_PAUSE = 1200;

const delay = (demo, ms, generation) =>
  demo.animate(
    demo.stage,
    [{ opacity: 1 }, { opacity: 1 }],
    { duration: ms },
    generation,
  );

async function boundedRead(
  read,
  message,
  pause = () => new Promise((resolve) => setTimeout(resolve, 25)),
) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const value = read();
    if (value) return value;
    await pause();
  }
  throw new Error(message);
}

class Demo {
  constructor(metadata, frameApi, changed) {
    this.metadata = metadata;
    this.name = metadata.name;
    this.stage = document.createElement("div");
    this.stage.className = "lf-interaction-overlay";
    this.stage.setAttribute("aria-hidden", "true");
    document.body.append(this.stage);
    this.pointer = document.createElement("span");
    this.pointer.className = "interaction-pointer";
    keepsHidden(this.pointer, true);
    this.pointer.setAttribute("aria-hidden", "true");
    this.stage.append(this.pointer);
    if (metadata.keypress) {
      this.keypress = document.createElement("kbd");
      this.keypress.className = "interaction-keypress";
      this.keypress.dataset.interactionKeypress = metadata.keypress;
      keepsHidden(this.keypress, true);
      this.stage.append(this.keypress);
    }
    this.frameApi = frameApi;
    this.changed = changed;
    this.state = "idle";
    this.generation = 0;
    this.animations = new Set();
    this.pausedWidgetAnimations = new Set();
    this.pointerPosition = null;
    this.pausedByView = false;
    this.scenario = scenarios[this.name] ?? null;
    const style = document.createElement("style");
    style.textContent = overlayStyle;
    document.head.append(style);
    this.viewport(metadata.viewport);
  }

  viewport(scale) {
    this.stage.style.setProperty("--interaction-overlay-scale", scale);
  }

  async load() {
    this.frameApi.resetThreads();
    if (!this.scenario)
      throw new Error(`interaction gallery has no scenario for ${this.name}`);
  }

  // The sequence the replay is pressing, shown only while it is being pressed. The word
  // travels as an attribute and lives in the caption for as long as the caption stands.
  keypressCaption(shown) {
    if (!this.keypress) return;
    keepsText(this.keypress, shown ? this.keypress.dataset.interactionKeypress : "");
    keepsHidden(this.keypress, !shown);
  }

  setState(state) {
    this.state = state;
    this.changed(this);
  }

  assertCurrent(generation) {
    if (generation !== this.generation) throw new StaleDemo();
  }

  reset() {
    this.generation += 1;
    this.stopAnimations();
    keepsHidden(this.pointer, true);
    this.keypressCaption(false);
    this.pointerPosition = null;
    this.pausedByView = false;
    if (!this.scenario) {
      this.setState("error");
      return;
    }
    this.scenario.reset(this);
    // Reset is the starting frame, not a third transition before the demonstration.
    this.stopAnimations();
    this.setState("ready");
  }

  activate() {
    this.reset();
  }

  deactivate() {
    this.generation += 1;
    this.stopAnimations();
    this.scenario?.deactivate?.(this);
    this.setState("idle");
  }

  async play() {
    if (this.state === "paused") {
      this.resume();
      return;
    }
    if (this.state !== "ready") return;
    const generation = this.generation;
    this.setState("playing");
    try {
      await this.scenario.play(this, generation);
      this.assertCurrent(generation);
      this.setState("finished");
    } catch (error) {
      if (error instanceof StaleDemo) return;
      if (generation === this.generation) {
        console.error(error);
        this.setState("error");
      }
    }
  }

  pause(byView = false) {
    if (this.state !== "playing") return;
    for (const animation of this.animations) animation.pause();
    for (const animation of this.widgetAnimations()) {
      if (animation.playState !== "running" || this.animations.has(animation)) continue;
      animation.pause();
      this.pausedWidgetAnimations.add(animation);
    }
    this.pausedByView = byView;
    this.setState("paused");
  }

  resume() {
    if (this.state !== "paused") return;
    for (const animation of this.animations) animation.play();
    for (const animation of this.pausedWidgetAnimations) {
      if (animation.playState === "paused") animation.play();
    }
    this.pausedWidgetAnimations.clear();
    this.pausedByView = false;
    this.setState("playing");
  }

  replay() {
    this.reset();
    return this.play();
  }

  stopAnimations() {
    for (const animation of this.animations) animation.cancel();
    this.animations.clear();
    for (const animation of this.widgetAnimations()) animation.cancel();
    this.pausedWidgetAnimations.clear();
  }

  widgetAnimations() {
    return document.getAnimations({ subtree: true });
  }

  async animate(element, keyframes, options, generation) {
    const animation = element.animate(keyframes, { fill: "forwards", ...options });
    await this.track(animation, generation);
    return animation;
  }

  async track(animation, generation) {
    if (!animation) {
      this.assertCurrent(generation);
      return null;
    }
    this.animations.add(animation);
    if (this.state === "paused") animation.pause();
    try {
      await animation.finished;
    } catch (error) {
      if (animation.playState !== "idle") throw error;
    } finally {
      this.animations.delete(animation);
    }
    this.assertCurrent(generation);
    return animation;
  }

  async wait(ms, generation) {
    const animation = await delay(this, ms, generation);
    animation.cancel();
  }

  async frame(generation) {
    await new Promise((resolve) => nextFrame(resolve));
    this.assertCurrent(generation);
  }

  async arrive(generation) {
    this.showPointer();
    await this.wait(ARRIVAL_PAUSE, generation);
  }

  async finish(generation) {
    await this.wait(RESULT_PAUSE, generation);
    await this.hidePointer(generation);
  }

  async waitFor(read, message, generation) {
    return boundedRead(read, message, () => this.wait(25, generation));
  }

  query(selector) {
    return document.querySelector(selector);
  }

  pointAt(target) {
    const box = target.getBoundingClientRect();
    return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
  }

  showPointer() {
    const from = {
      x: innerWidth * 0.16,
      y: innerHeight * 0.82,
    };
    this.pointerPosition = from;
    keepsHidden(this.pointer, false);
    this.pointer.style.transform = `translate(${from.x}px, ${from.y}px)`;
    this.pointer.style.opacity = "1";
  }

  async movePointer(target, generation) {
    const to = this.pointAt(target);
    const from = this.pointerPosition;
    const animation = await this.animate(
      this.pointer,
      [
        { transform: `translate(${from.x}px, ${from.y}px)` },
        { transform: `translate(${to.x}px, ${to.y}px)` },
      ],
      { duration: POINTER_TRAVEL, easing: "cubic-bezier(.22,.7,.2,1)" },
      generation,
    );
    this.pointerPosition = to;
    this.pointer.style.transform = `translate(${to.x}px, ${to.y}px)`;
    animation.cancel();
  }

  async press(generation) {
    const { x, y } = this.pointerPosition;
    const animation = await this.animate(
      this.pointer,
      [
        { transform: `translate(${x}px, ${y}px) scale(1)` },
        { transform: `translate(${x}px, ${y}px) scale(.78)`, offset: 0.48 },
        { transform: `translate(${x}px, ${y}px) scale(1)` },
      ],
      { duration: 260, easing: "ease-out" },
      generation,
    );
    this.pointer.style.transform = `translate(${x}px, ${y}px)`;
    animation.cancel();
  }

  async pressKeys(generation) {
    if (!this.keypress) return;
    this.keypressCaption(true);
    const animation = await this.animate(
      this.keypress,
      [
        { opacity: 0, transform: "translateY(4px) scale(.94)" },
        { opacity: 1, transform: "translateY(0) scale(1)", offset: 0.35 },
        { opacity: 1, transform: "translateY(0) scale(.96)", offset: 0.7 },
        { opacity: 0, transform: "translateY(-2px) scale(1)" },
      ],
      { duration: 720, easing: "ease-out" },
      generation,
    );
    animation.cancel();
    this.keypressCaption(false);
  }

  async hidePointer(generation) {
    const animation = await this.animate(
      this.pointer,
      [{ opacity: 1 }, { opacity: 0 }],
      { duration: 220, easing: "linear" },
      generation,
    );
    animation.cancel();
    keepsHidden(this.pointer, true);
  }
}

const placements = {
  ready: {
    "bg-motion-ready": ["bg-motion-card"],
    "bg-motion-tried": [],
  },
  tried: {
    "bg-motion-ready": [],
    "bg-motion-tried": ["bg-motion-card"],
  },
};

const scenarios = {
  accept: {
    reset(demo) {
      demo
        .query("#bg-motion-accept")
        .renderState({ decide: { action: null, value: null, detail: {} } });
    },
    async play(demo, generation) {
      await demo.arrive(generation);
      const suggestion = demo.query("#bg-motion-accept");
      const accept = await demo.waitFor(
        () => demo.query('[data-lf-margin-for="bg-motion-accept"] .lf-sug-accept'),
        "the suggestion did not expose its Accept control",
        generation,
      );
      await demo.movePointer(accept, generation);
      await demo.wait(360, generation);
      await demo.press(generation);
      suggestion.renderState({
        decide: { action: "decide", value: "decide", detail: { outcome: "accept" } },
      });
      await demo.waitFor(
        () => suggestion.dataset.lfState === "accept",
        "the suggestion did not settle",
        generation,
      );
      await demo.finish(generation);
    },
  },
  "move-card": {
    reset(demo) {
      demo.query("#bg-motion-board").renderState({ move: { value: placements.ready } });
    },
    async play(demo, generation) {
      await demo.arrive(generation);
      const board = demo.query("#bg-motion-board");
      const grip = await demo.waitFor(
        () => demo.query("#bg-motion-card > .lf-grip"),
        "the card did not expose its grip",
        generation,
      );
      await demo.movePointer(grip, generation);
      await demo.press(generation);
      await demo.wait(480, generation);
      board.renderState({ move: { value: placements.tried } });
      await demo.waitFor(
        () => demo.query("#bg-motion-card").parentElement?.id === "bg-motion-tried",
        "the card did not move",
        generation,
      );
      await demo.finish(generation);
    },
  },
  "send-comment": {
    reset(demo) {
      demo.frameApi.resetComment(
        demo.metadata.target,
        "Gallery thread: should the practice exercise come before lunch? " +
          "Try replying here; the agenda is fictional.",
      );
    },
    async play(demo, generation) {
      await demo.wait(ARRIVAL_PAUSE, generation);
      await demo.pressKeys(generation);
      const openThread = demo.frameApi.submitComment(demo.metadata.threadId);
      const destination = await openThread();
      demo.assertCurrent(generation);
      if (!destination) throw new Error("the comment did not reach its Thread");
      await demo.frame(generation);
      await Promise.all(
        demo
          .widgetAnimations()
          .filter((animation) => !demo.animations.has(animation))
          .map((animation) => demo.track(animation, generation)),
      );
      await demo.wait(RESULT_PAUSE, generation);
    },
  },
  "open-threads": {
    reset(demo) {
      demo.frameApi.resetThreads();
    },
    async play(demo, generation) {
      await demo.arrive(generation);
      const toggle = demo.frameApi.threadsButton();
      await demo.movePointer(toggle, generation);
      await demo.wait(360, generation);
      await demo.press(generation);
      // The panel stands and the page makes room for it in the press itself: nothing
      // follows it to wait out, so the replay's pause on the result is the only hold.
      demo.frameApi.setThreads(true);
      await demo.waitFor(
        demo.frameApi.threadsOpen,
        "the Threads panel did not open",
        generation,
      );
      await demo.wait(RESULT_PAUSE, generation);
      await demo.movePointer(toggle, generation);
      await demo.press(generation);
      demo.frameApi.setThreads(false);
      await demo.finish(generation);
    },
  },
};

export function mountPlayback(frameApi) {
  let demo;
  registerSampleCommand("gallery.configure", async (metadata) => {
    demo = new Demo(metadata, frameApi, () => {
      sampleNotice("gallery.state", {
        state: demo.state,
        pausedByView: demo.pausedByView,
      });
    });
    await demo.load();
  });
  for (const command of [
    "activate",
    "deactivate",
    "play",
    "pause",
    "resume",
    "replay",
    "viewport",
  ]) {
    registerSampleCommand(`gallery.${command}`, (detail) => {
      if (!demo) throw new Error("interaction gallery has not been configured");
      // Completion travels as state notices, leaving the channel free for pause.
      void demo[command](detail);
    });
  }
}
