/* The developer interaction gallery replays focused demonstrations against real Leaf
 * surfaces in the product gallery. It owns only the illustrative pointer, timing
 * controls, and ephemeral orchestration of each surface's canonical transition.
 * Document-global chrome runs in a same-origin frame so it remains inside the specimen;
 * a package-specific sequence comes from that package's widget module. No sequence
 * dispatches a gesture or writes to the page's event log. The product gallery opts in
 * with data-interaction-gallery, so ordinary Leaf pages pay no runtime or behavior cost
 * for this developer surface. */

import { onMotionPreferenceChange, reducedMotion } from "./motion.js";
import { runtime } from "./context.js";
import { offer } from "./widget-elements.js";

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

function frameSource(frame) {
  const theme = new URL("../theme.css", import.meta.url).href;
  const leafEntry = new URL("../leaf.js", import.meta.url).href;
  const adapter = new URL("./interaction-gallery-frame.js", import.meta.url).href;
  const content = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = frame.dataset.interactionEyebrow;
  content.append(eyebrow);
  if (frame.dataset.interactionTitle) {
    const heading = document.createElement("h1");
    heading.textContent = frame.dataset.interactionTitle;
    content.append(heading);
  }
  const copy = document.createElement("p");
  copy.append(frame.dataset.interactionCopy);
  if (frame.dataset.interactionTarget) {
    copy.id = frame.dataset.interactionTarget;
    copy.className = "interaction-frame-target";
  }
  content.append(copy);
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="lf-revision" data-lf-runtime content="${runtime.currentRevision}">
    <meta name="lf-version" data-lf-runtime content="${runtime.currentStamp}">
    <link rel="stylesheet" href="${theme}">
    <style>
      body { overflow: hidden; }
      main {
        box-sizing: border-box;
        min-height: 24rem;
        padding-block: 6.5rem 3rem;
      }
      .interaction-frame-target {
        max-width: 31rem;
        font-size: var(--t-3);
        line-height: 1.7;
      }
    </style>
  </head>
  <body>
    <main>${content.innerHTML}</main>
    <script type="module" src="${leafEntry}"></script>
    <script type="module" src="${adapter}"></script>
  </body>
</html>`;
}

class Demo {
  constructor(panel, changed) {
    this.panel = panel;
    this.figure = panel.querySelector("[data-interaction-demo]");
    this.name = this.figure.dataset.interactionDemo;
    this.stage = this.figure.querySelector(".interaction-stage");
    this.pointer = this.figure.querySelector(".interaction-pointer");
    this.keypress = this.figure.querySelector("[data-interaction-keypress]");
    this.frameElement = this.figure.querySelector("[data-interaction-frame]");
    this.frameApi = null;
    this.changed = changed;
    this.loadState = "loading";
    this.state = "idle";
    this.generation = 0;
    this.animations = new Set();
    this.pausedWidgetAnimations = new Set();
    this.pointerPosition = null;
    this.pausedByView = false;
    this.scenario = scenarios[this.name] ?? null;
  }

  async load() {
    if (this.frameElement) {
      const loaded = new Promise((resolve) =>
        this.frameElement.addEventListener("load", resolve, { once: true }),
      );
      this.frameElement.srcdoc = frameSource(this.frameElement);
      await loaded;
      this.frameApi = await boundedRead(
        () => this.frameElement.contentWindow?.leafInteractionGalleryFrame,
        "the contained Leaf page did not expose its gallery adapter",
      );
      await boundedRead(
        () => this.frameElement.contentDocument?.body.hasAttribute("data-lf-presented"),
        "the contained Leaf page did not finish presenting",
      );
      await this.frameApi.ready;
      this.frameElement.dataset.interactionReady = "";
    }
    const modulePath = this.figure.dataset.interactionModule;
    if (modulePath) {
      const loaded = await import(modulePath);
      const scenario = loaded.interactionGalleryScenario;
      if (!scenario?.reset || !scenario?.play)
        throw new Error(
          `${modulePath} does not export an interaction gallery scenario`,
        );
      this.scenario = {
        reset: () => scenario.reset(this.figure),
        play: (_, generation) =>
          scenario.play(
            Object.freeze({
              root: this.figure,
              arrive: () => this.arrive(generation),
              press: async (target) => {
                await this.movePointer(target, generation);
                await this.wait(360, generation);
                await this.press(generation);
              },
              track: (animation) => this.track(animation, generation),
              until: (read, message) => this.waitFor(read, message, generation),
              finish: () => this.finish(generation),
            }),
          ),
      };
    }
    if (!this.scenario)
      throw new Error(`interaction gallery has no scenario for ${this.name}`);
    this.loadState = "ready";
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
    this.pointer.hidden = true;
    if (this.keypress) this.keypress.hidden = true;
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
    this.setState(this.loadState === "error" ? "error" : "idle");
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
    return [
      ...this.stage.getAnimations({ subtree: true }),
      ...(this.frameElement?.contentDocument?.getAnimations({ subtree: true }) ?? []),
    ];
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
    await new Promise((resolve) => requestAnimationFrame(resolve));
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

  pointAt(target) {
    const stage = this.stage.getBoundingClientRect();
    const box = target.getBoundingClientRect();
    const frame = target.ownerDocument.defaultView?.frameElement;
    const frameBox = frame?.getBoundingClientRect();
    return {
      x: (frameBox?.left ?? 0) + box.left - stage.left + box.width / 2,
      y: (frameBox?.top ?? 0) + box.top - stage.top + box.height / 2,
    };
  }

  showPointer() {
    const from = {
      x: this.stage.clientWidth * 0.16,
      y: this.stage.clientHeight * 0.82,
    };
    this.pointerPosition = from;
    this.pointer.hidden = false;
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
    this.keypress.hidden = false;
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
    this.keypress.hidden = true;
  }

  async hidePointer(generation) {
    const animation = await this.animate(
      this.pointer,
      [{ opacity: 1 }, { opacity: 0 }],
      { duration: 220, easing: "linear" },
      generation,
    );
    animation.cancel();
    this.pointer.hidden = true;
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
    reset() {
      document
        .querySelector("#bg-motion-accept")
        .renderState({ settlement: { value: null } });
    },
    async play(demo, generation) {
      await demo.arrive(generation);
      const suggestion = document.querySelector("#bg-motion-accept");
      const accept = await demo.waitFor(
        () =>
          document.querySelector(
            '.lf-sug-actions[data-lf-for="bg-motion-accept"] [aria-label^="Accept"]',
          ),
        "the suggestion did not expose its Accept control",
        generation,
      );
      await demo.movePointer(accept, generation);
      await demo.wait(360, generation);
      await demo.press(generation);
      suggestion.renderState({ settlement: { value: "accept" } });
      await demo.waitFor(
        () => suggestion.dataset.lfState === "accept",
        "the suggestion did not settle",
        generation,
      );
      await demo.finish(generation);
    },
  },
  "move-card": {
    reset() {
      document
        .querySelector("#bg-motion-board")
        .renderState({ placement: { value: placements.ready } });
    },
    async play(demo, generation) {
      await demo.arrive(generation);
      const board = document.querySelector("#bg-motion-board");
      const grip = await demo.waitFor(
        () => document.querySelector("#bg-motion-card > .lf-grip"),
        "the card did not expose its grip",
        generation,
      );
      await demo.movePointer(grip, generation);
      await demo.press(generation);
      await demo.wait(480, generation);
      board.renderState({ placement: { value: placements.tried } });
      await demo.waitFor(
        () =>
          document.querySelector("#bg-motion-card").parentElement?.id ===
          "bg-motion-tried",
        "the card did not move",
        generation,
      );
      await demo.finish(generation);
    },
  },
  "send-comment": {
    reset(demo) {
      demo.frameApi.resetComment(
        "Gallery conversation: should the practice exercise come before lunch? " +
          "Try replying here; the agenda is fictional.",
      );
    },
    async play(demo, generation) {
      await demo.wait(ARRIVAL_PAUSE, generation);
      await demo.pressKeys(generation);
      const thread = demo.frameApi.submitComment(
        demo.figure.dataset.interactionThreadId,
      );
      if (!thread) throw new Error("the comment did not open its inline thread");
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
      await demo.track(demo.frameApi.setThreads(true), generation);
      await demo.waitFor(
        demo.frameApi.threadsOpen,
        "the Threads panel did not open",
        generation,
      );
      await demo.wait(RESULT_PAUSE, generation);
      await demo.movePointer(toggle, generation);
      await demo.press(generation);
      await demo.track(demo.frameApi.setThreads(false), generation);
      await demo.finish(generation);
    },
  },
};

let installedGallery = null;
let uninstallGallery = () => {};

export function installInteractionGallery() {
  const gallery = document.querySelector("[data-interaction-gallery]");
  if (gallery === installedGallery) return;
  uninstallGallery();
  installedGallery = gallery;
  uninstallGallery = () => {};
  if (!gallery) return;
  gallery.dataset.interactionInstalled = "1";
  const tabs = gallery.querySelector("lf-tabs");
  const panels = [...tabs.querySelectorAll(":scope > lf-tab")];
  const controls = offer("div", "interaction-controls");
  controls.setAttribute("aria-label", "Animation controls");
  const toggle = offer("button", "interaction-control", "Loading…");
  toggle.dataset.interactionToggle = "";
  const replay = offer("button", "interaction-control", "Replay");
  replay.dataset.interactionReplay = "";
  const status = offer("span", "interaction-status", "Loading the first interaction…");
  status.dataset.interactionStatus = "";
  status.setAttribute("aria-live", "polite");
  controls.append(toggle, replay, status);
  tabs.before(controls);
  let active = null;
  let onScreen = false;

  const demos = new Map(
    panels.map((panel) => [panel, new Demo(panel, () => renderControls())]),
  );

  function selectedPanel() {
    return panels.find((panel) => !panel.hasAttribute("hidden"));
  }

  function renderControls() {
    if (!active) return;
    const words = {
      idle: "Loading…",
      ready: "Play",
      playing: "Pause",
      paused: "Play",
      finished: "Played",
      error: "Unavailable",
    };
    toggle.textContent = words[active.state];
    toggle.disabled = ["idle", "finished", "error"].includes(active.state);
    replay.disabled = active.state === "error";
    const label = active.panel.getAttribute("label");
    const states = {
      idle: "Loading",
      ready: reducedMotion()
        ? "Ready — motion will start only when you press Play"
        : "Ready",
      playing: "Playing",
      paused: "Paused",
      finished: "Complete",
      error: "Could not play",
    };
    status.textContent = `${label} · ${states[active.state]}`;
    toggle.setAttribute("aria-label", `${words[active.state]} ${label} animation`);
    replay.setAttribute("aria-label", `Replay ${label} animation`);
  }

  function maybePlay() {
    if (!active || !onScreen || reducedMotion()) return;
    if (active.state === "ready") void active.play();
    else if (active.state === "paused" && active.pausedByView) active.resume();
  }

  function syncActive() {
    if (!tabs.classList.contains("lf-rendered")) return;
    const next = demos.get(selectedPanel());
    if (!next) return;
    if (next !== active) {
      active?.deactivate();
      active = next;
    }
    if (active.loadState === "ready" && active.state === "idle") active.activate();
    renderControls();
    maybePlay();
  }

  const togglePlayback = () => {
    if (active?.state === "playing") active.pause();
    else if (active?.state === "paused") active.resume();
    else void active?.play();
  };
  const replayActive = () => void active?.replay();
  toggle.addEventListener("click", togglePlayback);
  replay.addEventListener("click", replayActive);

  const tabObserver = new MutationObserver(syncActive);
  tabObserver.observe(tabs, {
    attributes: true,
    attributeFilter: ["class", "hidden"],
    subtree: true,
  });
  const viewObserver = new window.IntersectionObserver(
    ([entry]) => {
      onScreen = entry.isIntersecting;
      if (onScreen) maybePlay();
      else active?.pause(true);
    },
    { threshold: 0.2 },
  );
  viewObserver.observe(gallery);
  const stopMotionPreference = onMotionPreferenceChange((reduced) => {
    if (reduced) active?.pause();
    else maybePlay();
    renderControls();
  });

  uninstallGallery = () => {
    active?.deactivate();
    for (const demo of demos.values()) demo.stopAnimations();
    tabObserver.disconnect();
    viewObserver.disconnect();
    toggle.removeEventListener("click", togglePlayback);
    replay.removeEventListener("click", replayActive);
    stopMotionPreference();
  };

  for (const demo of demos.values()) {
    void demo
      .load()
      .catch((error) => {
        console.error(error);
        demo.loadState = "error";
        demo.setState("error");
      })
      .finally(() => {
        if (gallery === installedGallery) syncActive();
      });
  }
  syncActive();
}
