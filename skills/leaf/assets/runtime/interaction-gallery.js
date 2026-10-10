/* The interaction gallery owns the outer playback controls and viewport. Every
 * sample runs in an opaque sandbox: scenarios, illustrative pointer, package imports,
 * and production transitions belong to its child document. The gallery exchanges
 * cloneable configuration, commands and state notices over the sample bridge. It
 * never reads a child DOM or calls functions across browsing contexts. */

import { afterScript } from "./rendering.js";
import { onMotionPreferenceChange, reducedMotion } from "./motion.js";
import { mountSample } from "./sample.js";
import { deferredArrival } from "./presentation.js";
import { offer, reserve } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";

// Every word the playback control can say, out here because the row reserves the width
// of all of them before it says the first. The button rewrites its own word as a demo
// runs, so a word that costs a different width moves the controls beside it while the
// user is aiming. Reserved by the runtime rather than by the page, because the runtime
// injects this row and the generated corpus may carry no rule for it.
const TOGGLE_WORDS = {
  idle: "Loading…",
  ready: "Play",
  playing: "Pause",
  paused: "Play",
  finished: "Replay",
  error: "Unavailable",
};

const VIEWPORT_SIZES = ["1", "2", "4"];

class Demo {
  constructor(panel, changed) {
    this.panel = panel;
    this.figure = panel.querySelector("[data-interaction-demo]");
    this.frameElement = this.figure.querySelector("[data-interaction-frame]");
    if (!this.frameElement)
      throw new Error(
        `interaction gallery page is missing for ${this.figure.dataset.interactionDemo}`,
      );
    this.changed = changed;
    this.loadState = "loading";
    this.state = "idle";
    this.pausedByView = false;
  }

  async load() {
    const template = this.figure.querySelector(":scope > template[data-sample]");
    this.sample = mountSample(this.frameElement, {
      template: template?.id,
      passive: true,
    });
    this.stopNotices = this.sample.on("gallery.state", ({ state, pausedByView }) => {
      this.pausedByView = pausedByView;
      this.setState(state);
    });
    await this.sample.ready;
    const modulePath = this.figure.dataset.interactionModule;
    await this.sample.call("gallery.configure", {
      name: this.figure.dataset.interactionDemo,
      target: this.figure.dataset.interactionTarget,
      threadId: this.figure.dataset.interactionThreadId,
      keypress: this.figure.dataset.interactionKeypress,
      modulePath: modulePath ?? null,
      viewport: Number(
        this.figure.closest("[data-interaction-gallery]").dataset.interactionViewport,
      ),
    });
    this.frameElement.toggleAttribute("data-interaction-ready", true);
    this.loadState = "ready";
  }

  setState(state) {
    this.state = state;
    this.changed(this);
  }

  command(method, detail) {
    return this.sample.call(`gallery.${method}`, detail).catch((error) => {
      if (!this.figure.isConnected && error.name === "AbortError") return;
      console.error(error);
      this.setState("error");
    });
  }

  activate() {
    this.setState("ready");
    void this.command("activate");
  }
  deactivate() {
    this.setState("idle");
    if (this.loadState === "ready") void this.command("deactivate");
  }
  play() {
    return this.command("play");
  }
  pause(byView = false) {
    if (this.loadState !== "ready") return;
    return this.command("pause", byView);
  }
  resume() {
    return this.command("resume");
  }
  replay() {
    return this.command("replay");
  }
  viewport(size) {
    return this.command("viewport", Number(size));
  }
  destroy() {
    this.stopNotices?.();
    return this.sample?.destroy();
  }
}

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
  const controls = offer("div", "lf-interaction-controls");
  controls.setAttribute("aria-label", "Animation controls");
  const toggle = offer("button", "lf-btn lf-interaction-control", "Loading…");
  toggle.dataset.interactionToggle = "";
  const loopLabel = offer("label", "lf-interaction-setting");
  const loop = offer("input", "lf-interaction-loop", undefined, "checkbox");
  loop.name = "lf-interaction-loop";
  loop.dataset.interactionLoop = "";
  loopLabel.append(loop, " Loop");
  const viewportLabel = offer("label", "lf-interaction-setting");
  viewportLabel.append("Viewport ");
  const viewport = offer("select", "lf-interaction-viewport");
  viewport.name = "lf-interaction-viewport";
  viewport.dataset.interactionViewportSelect = "";
  for (const size of VIEWPORT_SIZES) {
    const option = document.createElement("option");
    option.value = size;
    option.textContent = `${size}×`;
    viewport.append(option);
  }
  if (!VIEWPORT_SIZES.includes(gallery.dataset.interactionViewport))
    throw new Error("interaction gallery has an invalid viewport size");
  viewport.value = gallery.dataset.interactionViewport;
  viewportLabel.append(viewport);
  const status = offer("span", "lf-interaction-status", "Loading…");
  status.dataset.interactionStatus = "";
  status.setAttribute("aria-live", "polite");
  controls.append(toggle, loopLabel, viewportLabel, status);
  tabs.before(controls);
  // After the row is in the document, which is where a width can be measured at all.
  reserve(toggle, Object.values(TOGGLE_WORDS));
  let active = null;
  let onScreen = false;

  // A step through the demonstration can pass through states in one script (a switch
  // deactivates one demo, readies the next and starts it), so the controls are painted
  // once, from where the script leaves them.
  const paintControls = () => afterScript(renderControls);
  const demos = new Map(
    panels.map((panel) => [
      panel,
      new Demo(panel, (demo) => {
        paintControls();
        // Commands and view crossings can arrive in either order. Reconcile the
        // acknowledged playback state against the current view. A motion preference
        // blocks autoplay; the user's explicit Play still runs under reduced motion.
        if (demo !== active) return;
        if (demo.state === "playing" && !onScreen) demo.pause(true);
        else if (demo.pausedByView) maybePlay();
      }),
    ]),
  );

  function selectedPanel() {
    return panels.find((panel) => !panel.hasAttribute("hidden"));
  }

  function renderControls() {
    if (!active) return;
    const words = TOGGLE_WORDS;
    keepsText(toggle, words[active.state]);
    toggle.toggleAttribute("disabled", ["idle", "error"].includes(active.state));
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
    keepsText(status, states[active.state]);
    keeps(toggle, "aria-label", `${words[active.state]} ${label} animation`);
    if (active.state === "finished" && loop.checked && onScreen) {
      const completed = active;
      queueMicrotask(() => {
        if (
          active === completed &&
          active.state === "finished" &&
          loop.checked &&
          onScreen
        )
          void active.replay();
      });
    }
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
    paintControls();
    maybePlay();
  }

  const togglePlayback = () => {
    if (active?.state === "playing") active.pause();
    else if (active?.state === "paused") active.resume();
    else if (active?.state === "finished") void active.replay();
    else void active?.play();
  };
  const changeLoop = () => {
    if (loop.checked && active?.state === "finished" && onScreen) void active.replay();
  };
  const changeViewport = () => {
    gallery.dataset.interactionViewport = viewport.value;
    for (const demo of demos.values()) {
      if (demo.loadState === "ready") void demo.viewport(viewport.value);
    }
    if (!active || !["playing", "paused"].includes(active.state)) return;
    const paused = active.state === "paused";
    void active.replay();
    if (paused) active.pause();
  };
  toggle.addEventListener("click", togglePlayback);
  loop.addEventListener("change", changeLoop);
  viewport.addEventListener("change", changeViewport);

  const tabObserver = new MutationObserver(syncActive);
  tabObserver.observe(tabs, {
    attributes: true,
    attributeFilter: ["class", "hidden"],
    subtree: true,
  });
  // Whether any of the gallery is in view, which is the question playback asks, so the
  // boundary the observer reports is the boundary the answer is read at. A ratio the
  // observer never notifies about would be a second reading of the same fact, free to
  // disagree with the deliveries that maintain it.
  //
  // A delivery carries every record accumulated since the last one, and only its last
  // says where the gallery is now. The arrival alone crosses the gallery out of view and
  // back — the fragment lands it, the page settles, the semantic arrival pass scrolls to
  // it — so a loaded machine hands both crossings over together. Read at the first, that
  // left the flag holding a position the gallery had already left, and since the observer
  // reports crossings rather than a state, nothing came afterwards to correct it: the
  // demonstration stayed at Ready for the rest of the page's life.
  const viewObserver = new window.IntersectionObserver((entries) => {
    onScreen = entries.at(-1).isIntersecting;
    if (onScreen) maybePlay();
    else active?.pause(true);
  });
  viewObserver.observe(gallery);
  const stopMotionPreference = onMotionPreferenceChange((reduced) => {
    if (reduced) active?.pause();
    else maybePlay();
    paintControls();
  });

  uninstallGallery = () => {
    active?.deactivate();
    for (const demo of demos.values()) {
      void demo.destroy();
    }
    tabObserver.disconnect();
    viewObserver.disconnect();
    toggle.removeEventListener("click", togglePlayback);
    loop.removeEventListener("change", changeLoop);
    viewport.removeEventListener("change", changeViewport);
    stopMotionPreference();
  };

  for (const demo of demos.values()) {
    // A contained document lays itself out in this page's process when it arrives, and
    // it arrives after the page has presented. The page carries that as its own
    // unfinished arrival, so nothing outside it has to know the gallery is here.
    void deferredArrival(
      demo
        .load()
        .catch((error) => {
          if (!demo.figure.isConnected && error.name === "AbortError") return;
          console.error(error);
          demo.loadState = "error";
          demo.setState("error");
        })
        .finally(() => {
          if (gallery === installedGallery) syncActive();
        }),
    );
  }
  syncActive();
}
