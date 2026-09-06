/* The developer interaction gallery replays small, local demonstrations against the
 * real upgraded widgets in the product gallery. It owns only the illustrative pointer,
 * timing controls, and ephemeral calls to each widget's canonical renderState surface;
 * it never dispatches a widget gesture or writes to the page's event log. The product
 * gallery opts in with data-interaction-gallery, so ordinary Leaf pages pay no runtime
 * or behavior cost for this developer surface. */

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

class Demo {
  constructor(panel, changed) {
    this.panel = panel;
    this.figure = panel.querySelector("[data-interaction-demo]");
    this.name = this.figure.dataset.interactionDemo;
    this.stage = this.figure.querySelector(".interaction-stage");
    this.pointer = this.figure.querySelector(".interaction-pointer");
    this.changed = changed;
    this.state = "idle";
    this.generation = 0;
    this.animations = new Set();
    this.pausedWidgetAnimations = new Set();
    this.pointerPosition = null;
    this.pausedByView = false;
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
    this.pointerPosition = null;
    this.pausedByView = false;
    scenarios[this.name].reset(this);
    // Reset is the starting frame, not a third transition before the demonstration.
    this.stopAnimations();
    this.setState("ready");
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
      await scenarios[this.name].play(this, generation);
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
    for (const animation of this.stage.getAnimations({ subtree: true })) {
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
    for (const animation of this.stage.getAnimations({ subtree: true }))
      animation.cancel();
    this.pausedWidgetAnimations.clear();
  }

  async animate(element, keyframes, options, generation) {
    const animation = element.animate(keyframes, { fill: "forwards", ...options });
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

  async waitFor(read, message, generation) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const value = read();
      if (value) return value;
      await this.wait(25, generation);
    }
    throw new Error(message);
  }

  pointAt(target) {
    const stage = this.stage.getBoundingClientRect();
    const box = target.getBoundingClientRect();
    return {
      x: box.left - stage.left + box.width / 2,
      y: box.top - stage.top + box.height / 2,
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
      demo.showPointer();
      await demo.wait(ARRIVAL_PAUSE, generation);
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
      await demo.wait(RESULT_PAUSE, generation);
      await demo.hidePointer(generation);
    },
  },
  "move-card": {
    reset() {
      document
        .querySelector("#bg-motion-board")
        .renderState({ placement: { value: placements.ready } });
    },
    async play(demo, generation) {
      demo.showPointer();
      await demo.wait(ARRIVAL_PAUSE, generation);
      const board = document.querySelector("#bg-motion-board");
      const grip = await demo.waitFor(
        () => document.querySelector("#bg-motion-card > .lf-grip"),
        "the card did not expose its grip",
        generation,
      );
      await demo.movePointer(grip, generation);
      await demo.press(generation);
      grip.focus({ preventScroll: true });
      await demo.wait(480, generation);
      board.renderState({ placement: { value: placements.tried } });
      await demo.waitFor(
        () =>
          document.querySelector("#bg-motion-card").parentElement?.id ===
          "bg-motion-tried",
        "the card did not move",
        generation,
      );
      await demo.wait(RESULT_PAUSE, generation);
      await demo.hidePointer(generation);
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
  const toggle = gallery.querySelector("[data-interaction-toggle]");
  const replay = gallery.querySelector("[data-interaction-replay]");
  const status = gallery.querySelector("[data-interaction-status]");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
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
      ready: reduced.matches
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
    if (!active || !onScreen || reduced.matches) return;
    if (active.state === "ready") void active.play();
    else if (active.state === "paused" && active.pausedByView) active.resume();
  }

  function syncActive() {
    if (!tabs.classList.contains("lf-rendered")) return;
    const next = demos.get(selectedPanel());
    if (!next || next === active) return;
    active?.reset();
    active = next;
    active.reset();
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
  const motionPreferenceChanged = () => {
    if (reduced.matches) active?.pause();
    else maybePlay();
    renderControls();
  };
  reduced.addEventListener("change", motionPreferenceChanged);

  uninstallGallery = () => {
    for (const demo of demos.values()) {
      demo.generation += 1;
      demo.stopAnimations();
    }
    tabObserver.disconnect();
    viewObserver.disconnect();
    toggle.removeEventListener("click", togglePlayback);
    replay.removeEventListener("click", replayActive);
    reduced.removeEventListener("change", motionPreferenceChanged);
  };

  syncActive();
}
