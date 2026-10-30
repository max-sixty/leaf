import { render as motionTemplate } from "./motion-view.js";
/* One transport for page-authored illustrations and compared video recordings.
 * A synchronous renderFrame(time) paints illustrations from milliseconds, while
 * descendant videos play on their native media clocks. The furthest video time
 * drives the shared timeline; seeking and pausing align all views to that time.
 * Never seek videos on animation frames: the browser owns decoding and playback.
 * The author owns geometry, duration and meaning. Assigning a renderer draws
 * immediately, so either module may load first.
 *
 * Playback, speed and scrubbing are local inspection, never page events. The
 * clock starts still, stops on disconnect/inspection, and resumes only on Play.
 * Reduced motion skips playback to the end but leaves manual seeking available.
 * Author callbacks must draw a complete frame, including when seeking backward.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` plays it too, by its own controls. The element draws its
 * single Lit transport itself, in the task that changes it, so a frame never claims the page's
 * presentation and nothing waits on it. Play is the widget's own button: its click
 * plays, and the transport draws it `aria-disabled` while there is nothing to play.
 * Leaf reads the Play command, which binds no key, from `lfCommands`, and names the
 * button by it in its command reference. A playback failure says so in the
 * clock's place, on any page, and reaches Leaf as the `error` event `reportFailure`
 * dispatches. A failure to draw shows the fail-soft box beside the transport, with the
 * study still standing under it, and stops the clock: the box stays until a draw
 * succeeds. The input that pauses playback is the user's own (a press, key, wheel,
 * touch or text inside the study but outside its transport, or the window losing
 * focus), read from the window as Leaf's prepaint counts input. */
import {
  cancelAnimation,
  commandsChanged,
  failSoft,
  nextAnimation,
  onMotionPreferenceChange,
  once,
  placesFailure,
  reducedMotion,
  render,
  reportFailure,
  tabStore,
  whileConnected,
} from "/runtime/portable-api.js";

const INPUTS = ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"];

class MotionStudy extends HTMLElement {
  #ui;
  #transport;
  #draw;
  #time = 0;
  #playing = false;
  #frame = null;
  #last = 0;
  #rate = 1;
  #failure = null;
  #box = null;
  #drawFailed = false;

  get #videos() {
    return [...this.querySelectorAll("video")].filter(
      (video) => video.closest("lf-motion") === this,
    );
  }

  get #playable() {
    return Boolean(this.#draw || this.#videos.length);
  }

  get duration() {
    return Number(this.getAttribute("duration"));
  }
  get currentTime() {
    return this.#time;
  }
  set currentTime(value) {
    if (!Number.isFinite(value))
      throw new TypeError("currentTime must be finite milliseconds");
    this.#pause();
    this.#failure = null;
    this.#time = Math.max(0, Math.min(this.duration, value));
    this.#seekVideos();
    this.#paint();
    this.#save();
  }
  get renderFrame() {
    return this.#draw;
  }
  set renderFrame(draw) {
    if (typeof draw !== "function")
      throw new TypeError("renderFrame must be a function");
    this.#draw = draw;
    this.#paint();
    commandsChanged(this);
  }

  connectedCallback() {
    if (!once(this)) return;
    // The box stands beside the transport, or first where there is none yet, so the
    // author's study under it stays readable. One failure said again keeps its box.
    placesFailure(this, (box) => {
      if (this.#box?.isConnected && this.#box.textContent === box.textContent)
        return true;
      this.#box?.remove();
      this.#box = box;
      const controls = this.#ui?.controls;
      if (controls?.isConnected) this.#transport.after(box);
      else this.prepend(box);
      return true;
    });
    try {
      this.#setup();
    } catch (error) {
      failSoft(this, error);
    }
  }

  #setup() {
    // The transport joins the authored content; native editors and media never move.
    this.#transport = document.createElement("div");
    this.#transport.className = "lf-motion-transport";
    this.#transport.setAttribute("data-lf-gen", "1");
    this.prepend(this.#transport);
    const saved = JSON.parse(
      tabStore.get(`motion:${this.id}`) || '{"time":0,"rate":1}',
    );
    this.#time = Math.min(this.duration, saved.time);
    this.#rate = saved.rate;
    render(this.#template(), this.#transport, { host: this });
    this.#ui = {
      controls: this.querySelector(".lf-motion-controls"),
      play: this.querySelector(".lf-motion-play"),
      time: this.querySelector(".lf-motion-time"),
      speed: this.querySelector(".lf-motion-speed select"),
    };
    // A row with no run names the press its control makes (keyboard/bindings.js).
    this.lfCommands = {
      title: "In a motion study",
      rows: [
        {
          id: "motion.play",
          title: () => this.#playLabel(),
          control: this.#ui.play,
        },
      ],
    };
    commandsChanged(this);
    this.#ui.play.addEventListener("click", () => {
      if (this.#playable) this.#toggle();
    });
    whileConnected(this, (signal) => {
      this.#ui.time.addEventListener(
        "input",
        () => {
          this.currentTime = Number(this.#ui.time.value);
        },
        { signal },
      );
      this.#ui.speed.addEventListener(
        "change",
        () => {
          this.#rate = Number(this.#ui.speed.value);
          for (const video of this.#videos) video.playbackRate = this.#rate;
          this.#save();
        },
        { signal },
      );
      this.addEventListener("lf-inspect", () => this.#pause(), { signal });
      document.addEventListener(
        "visibilitychange",
        () => {
          if (document.hidden) this.#pause();
        },
        { signal },
      );
      const input = (event) => {
        // Firefox can hand an arriving sandboxed window a foreign wheel object, which
        // is no Event of this realm (prepaint.js reads input the same way).
        if (!(event instanceof Event)) return;
        const { target } = event;
        if (
          event.type === "blur"
            ? target === window
            : target instanceof Node &&
              event.composedPath().includes(this) &&
              !event.composedPath().includes(this.#ui.controls)
        )
          this.#pause();
      };
      for (const type of INPUTS)
        addEventListener(type, input, { capture: true, passive: true, signal });
      const preference = onMotionPreferenceChange(() => {
        if (reducedMotion() && this.#playing) this.currentTime = this.duration;
        else {
          this.#paintControls();
          commandsChanged(this);
        }
      });
      for (const video of this.#videos) {
        video.addEventListener("loadedmetadata", () => this.#seekVideos(), {
          signal,
        });
      }
      this.#seekVideos();
      this.#paint();
      return () => {
        this.#pause();
        preference();
      };
    });
  }

  #playLabel() {
    if (this.#playing) return "Pause";
    if (reducedMotion()) return "Show end";
    return "Play";
  }

  #pause() {
    if (this.#frame !== null) cancelAnimation(this.#frame);
    this.#frame = null;
    const readVideo =
      this.#playing && this.#videos.length && this.#time < this.duration;
    if (readVideo) this.#readVideoTime();
    this.#playing = false;
    for (const video of this.#videos) video.pause();
    this.#seekVideos();
    this.#paintControls();
    if (this.#ui) this.#save();
    if (readVideo && this.isConnected) this.#drawFrame();
  }

  // The author's frame at the clock's time, or the fail-soft box where it throws;
  // whether it drew.
  #drawFrame() {
    if (!this.#draw) return true;
    try {
      this.#draw(this.#time);
    } catch (error) {
      this.#drawFailed = true;
      failSoft(this, error);
      return false;
    }
    if (this.#drawFailed) {
      this.#drawFailed = false;
      this.#box?.remove();
      this.#box = null;
    }
    return true;
  }

  #save() {
    tabStore.set(
      `motion:${this.id}`,
      JSON.stringify({ time: this.#time, rate: this.#rate }),
    );
  }

  #toggle() {
    if (this.#playing) {
      this.#pause();
      return;
    }
    if (reducedMotion()) {
      this.currentTime = this.duration;
      return;
    }
    if (this.#time >= this.duration) this.#time = 0;
    this.#failure = null;
    this.#seekVideos();
    // The first frame draws before the transport says Pause, so a frame that throws
    // leaves it saying Play rather than flipping it there and back.
    if (this.isConnected && !this.#drawFrame()) {
      this.#paintControls();
      return;
    }
    this.#playing = true;
    this.#last = performance.now();
    this.#paintControls();
    for (const video of this.#videos) {
      video.playbackRate = this.#rate;
      video.play().catch((error) => {
        // A pause or seek may interrupt the browser's pending play request.
        if (error.name === "AbortError") return;
        this.#failure = "Failed";
        this.#pause();
        reportFailure(this, new Error(`Playback failed: ${error.message}`));
      });
    }
    this.#frame = nextAnimation(() => this.#tick());
  }

  #seekVideos() {
    for (const video of this.#videos) {
      const time = Math.min(this.#time / 1000, video.duration || Infinity);
      if (video.currentTime !== time) video.currentTime = time;
    }
  }

  #readVideoTime() {
    this.#time = Math.min(
      this.duration,
      Math.max(...this.#videos.map((video) => video.currentTime * 1000)),
    );
  }

  #tick() {
    this.#frame = null;
    const now = performance.now();
    const videos = this.#videos;
    if (videos.length) {
      this.#readVideoTime();
      if (videos.every((video) => video.ended)) this.#time = this.duration;
    } else {
      this.#time = Math.min(
        this.duration,
        this.#time + (now - this.#last) * this.#rate,
      );
    }
    this.#last = now;
    if (this.#time >= this.duration) {
      this.#pause();
    }
    this.#paint();
    if (this.#playing) this.#frame = nextAnimation(() => this.#tick());
  }

  #template() {
    return motionTemplate(this, {
      time: this.#time,
      rate: this.#rate,
      label: this.#playLabel(),
      playing: this.#playing,
      playable: this.#playable,
      failure: this.#failure,
    });
  }

  #paintControls() {
    if (!this.#ui) return;
    try {
      render(this.#template(), this.#transport, { host: this });
    } catch (error) {
      failSoft(this, error);
    }
  }

  #paint() {
    this.#paintControls();
    if (this.isConnected && !this.#drawFrame()) this.#pause();
  }
}

customElements.define("lf-motion", MotionStudy);
