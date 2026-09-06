/* The public interaction strip orchestrates real Leaf pages in same-origin frames.
 * The scenes own their widgets and motion; this file owns only the explanatory cursor,
 * timing controls, and resetting the frame to its authored state. */

const gallery = document.querySelector("[data-interaction-gallery]");

if (gallery) {
  const tabs = gallery.querySelector("lf-tabs");
  const panels = [...tabs.querySelectorAll(":scope > lf-tab")];
  const toggle = gallery.querySelector("[data-interaction-toggle]");
  const replay = gallery.querySelector("[data-interaction-replay]");
  const status = gallery.querySelector("[data-interaction-status]");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let active = null;
  let onScreen = false;

  const after = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  class Demo {
    constructor(panel, changed) {
      this.panel = panel;
      this.figure = panel.querySelector("[data-interaction-demo]");
      this.name = this.figure.dataset.interactionDemo;
      this.stage = this.figure.querySelector(".interaction-stage");
      this.frame = this.figure.querySelector("iframe");
      this.pointer = this.figure.querySelector(".interaction-pointer");
      this.changed = changed;
      this.state = "idle";
      this.generation = 0;
      this.loadPromise = null;
      this.animations = new Set();
      this.pausedChildAnimations = new Set();
      this.childObserver = null;
      this.pointerPosition = null;
    }

    setState(state) {
      this.state = state;
      this.changed(this);
    }

    async load({ reset = false } = {}) {
      if (!reset && this.loadPromise) return this.loadPromise;
      const generation = ++this.generation;
      this.stopAnimations();
      this.pointer.hidden = true;
      this.pointerPosition = null;
      this.setState("loading");
      const source = this.frame.dataset.src;
      const url = reset ? `${source}?replay=${generation}` : source;
      this.loadPromise = (async () => {
        await new Promise((resolve, reject) => {
          const loaded = () => {
            cleanup();
            resolve();
          };
          const failed = () => {
            cleanup();
            reject(new Error(`${source} did not load`));
          };
          const cleanup = () => {
            this.frame.removeEventListener("load", loaded);
            this.frame.removeEventListener("error", failed);
          };
          this.frame.addEventListener("load", loaded);
          this.frame.addEventListener("error", failed);
          this.frame.src = url;
        });
        for (let attempt = 0; attempt < 200; attempt += 1) {
          if (generation !== this.generation) return false;
          if (this.frame.contentDocument?.body?.hasAttribute("data-lf-presented")) {
            this.setState("ready");
            return true;
          }
          await after(25);
        }
        throw new Error(`${source} never reached Leaf's presented state`);
      })().catch((error) => {
        if (generation === this.generation) {
          console.error(error);
          this.setState("error");
        }
        return false;
      });
      return this.loadPromise;
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
        await scenarios[this.name](this);
        if (generation === this.generation && this.state !== "error") {
          this.setState("finished");
        }
      } catch (error) {
        if (generation === this.generation) {
          console.error(error);
          this.setState("error");
        }
      }
    }

    pause() {
      if (this.state !== "playing") return;
      for (const animation of this.animations) animation.pause();
      this.pauseChildAnimations();
      this.setState("paused");
    }

    resume() {
      if (this.state !== "paused") return;
      this.stopChildObserver();
      for (const animation of this.animations) animation.play();
      for (const animation of this.pausedChildAnimations) {
        if (animation.playState === "paused") animation.play();
      }
      this.pausedChildAnimations.clear();
      this.setState("playing");
    }

    async restart() {
      const loaded = await this.load({ reset: true });
      if (loaded && this === active) await this.play();
    }

    unload() {
      this.generation += 1;
      this.stopAnimations();
      this.frame.src = "about:blank";
      this.loadPromise = null;
      this.pointer.hidden = true;
      this.pointerPosition = null;
      this.setState("idle");
    }

    stopAnimations() {
      this.stopChildObserver();
      for (const animation of this.animations) animation.cancel();
      this.animations.clear();
      for (const animation of this.frame.contentDocument?.getAnimations() ?? []) {
        animation.cancel();
      }
      this.pausedChildAnimations.clear();
    }

    pauseChildAnimations() {
      const doc = this.frame.contentDocument;
      if (!doc) return;
      const pauseRunning = () => {
        for (const animation of doc.getAnimations()) {
          if (animation.playState !== "running") continue;
          animation.pause();
          this.pausedChildAnimations.add(animation);
        }
      };
      pauseRunning();
      this.childObserver = new doc.defaultView.MutationObserver(() => {
        doc.defaultView.requestAnimationFrame(pauseRunning);
      });
      this.childObserver.observe(doc, {
        attributes: true,
        childList: true,
        subtree: true,
      });
    }

    stopChildObserver() {
      this.childObserver?.disconnect();
      this.childObserver = null;
    }

    async animate(element, keyframes, options) {
      const animation = element.animate(keyframes, { fill: "forwards", ...options });
      this.animations.add(animation);
      if (this.state === "paused") animation.pause();
      try {
        await animation.finished;
      } finally {
        this.animations.delete(animation);
      }
      return animation;
    }

    async wait(ms) {
      const animation = await this.animate(this.stage, [{}, {}], { duration: ms });
      animation.cancel();
    }

    async waitFor(read, message) {
      for (let attempt = 0; attempt < 120; attempt += 1) {
        const value = read();
        if (value) return value;
        await this.wait(25);
      }
      throw new Error(message);
    }

    target(selector) {
      const target = this.frame.contentDocument?.querySelector(selector);
      if (!target) throw new Error(`${this.name} cannot find ${selector}`);
      return target;
    }

    pointAt(target) {
      const stage = this.stage.getBoundingClientRect();
      const frame = this.frame.getBoundingClientRect();
      const box = target.getBoundingClientRect();
      return {
        x: frame.left - stage.left + box.left + box.width / 2,
        y: frame.top - stage.top + box.top + box.height / 2,
      };
    }

    async movePointer(target) {
      const to = this.pointAt(target);
      const from = this.pointerPosition ?? {
        x: this.stage.clientWidth * 0.16,
        y: this.stage.clientHeight * 0.82,
      };
      this.pointer.hidden = false;
      this.pointer.style.transform = `translate(${from.x}px, ${from.y}px)`;
      this.pointer.style.opacity = "1";
      const animation = await this.animate(
        this.pointer,
        [
          { transform: `translate(${from.x}px, ${from.y}px)` },
          { transform: `translate(${to.x}px, ${to.y}px)` },
        ],
        { duration: 760, easing: "cubic-bezier(.22,.7,.2,1)" },
      );
      this.pointerPosition = to;
      this.pointer.style.transform = `translate(${to.x}px, ${to.y}px)`;
      animation.cancel();
    }

    async click(target) {
      const { x, y } = this.pointerPosition;
      target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      target.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      const animation = await this.animate(
        this.pointer,
        [
          { transform: `translate(${x}px, ${y}px) scale(1)` },
          { transform: `translate(${x}px, ${y}px) scale(.78)`, offset: 0.48 },
          { transform: `translate(${x}px, ${y}px) scale(1)` },
        ],
        { duration: 180, easing: "ease-out" },
      );
      animation.cancel();
      this.pointer.style.transform = `translate(${x}px, ${y}px)`;
      target.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
      target.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
      target.click();
    }

    async hidePointer() {
      const animation = await this.animate(
        this.pointer,
        [{ opacity: 1 }, { opacity: 0 }],
        { duration: 180, easing: "linear" },
      );
      animation.cancel();
      this.pointer.hidden = true;
    }
  }

  const key = (target, value) => {
    const init = { key: value, code: value, bubbles: true, cancelable: true };
    target.dispatchEvent(new KeyboardEvent("keydown", init));
    target.dispatchEvent(new KeyboardEvent("keyup", init));
  };

  const scenarios = {
    async accept(demo) {
      await demo.wait(800);
      const suggestion = demo.target("#accept-change");
      if (suggestion.dataset.lfState) return;
      const accept = demo.target('[aria-label^="Accept the suggested change:"]');
      await demo.movePointer(accept);
      await demo.wait(260);
      if (!suggestion.dataset.lfState && accept.isConnected) {
        await demo.click(accept);
      }
      await demo.waitFor(
        () => suggestion.dataset.lfState,
        "the suggestion did not settle",
      );
      await demo.wait(700);
      await demo.hidePointer();
    },

    async "move-card"(demo) {
      await demo.wait(800);
      const grip = demo.target("#move-card > .lf-grip");
      await demo.movePointer(grip);
      await demo.click(grip);
      grip.focus({ preventScroll: true });
      await demo.wait(320);
      key(grip, "Enter");
      await demo.wait(500);
      key(grip, "ArrowRight");
      await demo.waitFor(
        () => demo.target("#move-card").parentElement?.id === "move-tried",
        "the card did not move",
      );
      await demo.wait(700);
      key(grip, "Enter");
      await demo.hidePointer();
    },
  };

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
      loading: "Loading…",
      ready: "Play",
      playing: "Pause",
      paused: "Play",
      finished: "Played",
      error: "Unavailable",
    };
    toggle.textContent = words[active.state];
    toggle.disabled = ["idle", "loading", "finished", "error"].includes(active.state);
    replay.disabled = ["idle", "loading", "error"].includes(active.state);
    const label = active.panel.getAttribute("label");
    const states = {
      idle: "Waiting",
      loading: "Loading",
      ready: reduced.matches
        ? "Ready — motion will start only when you press Play"
        : "Ready",
      playing: "Playing",
      paused: "Paused",
      finished: "Complete",
      error: "Could not load",
    };
    status.textContent = `${label} · ${states[active.state]}`;
    toggle.setAttribute("aria-label", `${words[active.state]} ${label} animation`);
    replay.setAttribute("aria-label", `Replay ${label} animation`);
  }

  async function prepareActive() {
    const demo = active;
    if (!demo) return;
    const loaded = await demo.load();
    if (
      loaded &&
      active === demo &&
      onScreen &&
      !reduced.matches &&
      demo.state === "ready"
    ) {
      await demo.play();
    }
  }

  function syncActive() {
    if (!tabs.classList.contains("lf-rendered")) return;
    const next = demos.get(selectedPanel());
    if (!next || next === active) return;
    const previous = active;
    active = next;
    if (previous) previous.unload();
    else {
      for (const demo of demos.values()) {
        if (demo !== next) demo.unload();
      }
    }
    renderControls();
    void prepareActive();
  }

  toggle.addEventListener("click", () => {
    if (active?.state === "playing") active.pause();
    else void active?.play();
  });
  replay.addEventListener("click", () => void active?.restart());

  new MutationObserver(syncActive).observe(tabs, {
    attributes: true,
    attributeFilter: ["class", "hidden"],
    subtree: true,
  });
  new IntersectionObserver(
    ([entry]) => {
      onScreen = entry.isIntersecting;
      if (onScreen) void prepareActive();
      else active?.pause();
    },
    { threshold: 0.2 },
  ).observe(gallery);
  reduced.addEventListener("change", () => {
    if (reduced.matches) active?.pause();
    renderControls();
  });

  syncActive();
}
