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
 */
import {
  LeafElement,
  initialRender,
  render,
  commands,
  whileConnected,
  nextAnimation,
  cancelAnimation,
  reducedMotion,
  onMotionPreferenceChange,
  onUserInput,
  paintKeys,
  signal,
  tabStore,
  raiseError,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-motion",
  class extends LeafElement {
    #ui;
    #draw;
    #time = 0;
    #playing = signal(false);
    #frame = null;
    #last = 0;
    #rate = 1;

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
      paintKeys();
    }

    setup() {
      this.#ui = initialRender(this);
      this.#time = Number(this.#ui.time.value);
      this.#rate = Number(this.#ui.speed.value);
      commands(this, "In a motion study", [
        {
          id: "motion.play",
          title: () => this.#playLabel(),
          control: this.#ui.play,
          when: () => this.#playable,
          run: () => this.#toggle(),
        },
      ]);
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
        const input = onUserInput((event) => {
          if (
            event.type === "blur" ||
            (this.contains(event.target) && !this.#ui.controls.contains(event.target))
          )
            this.#pause();
        });
        const preference = onMotionPreferenceChange(() => {
          if (reducedMotion() && this.#playing.value) this.currentTime = this.duration;
          else {
            this.#paintControls();
            paintKeys();
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
          input();
          preference();
        };
      });
    }

    render() {
      return this.#ui.render({
        time: this.#time,
        rate: this.#rate,
        label: this.#playLabel(),
        playing: this.#playing.value,
      });
    }

    #playLabel() {
      if (this.#playing.value) return "Pause";
      if (reducedMotion()) return "Show end";
      return "Play";
    }

    #pause() {
      if (this.#frame !== null) cancelAnimation(this.#frame);
      this.#frame = null;
      const readVideo =
        this.#playing.value && this.#videos.length && this.#time < this.duration;
      if (readVideo) this.#readVideoTime();
      this.#playing.value = false;
      for (const video of this.#videos) video.pause();
      this.#seekVideos();
      this.#paintControls();
      if (this.#ui) this.#save();
      if (readVideo && this.isConnected) this.#draw?.(this.#time);
    }

    #save() {
      tabStore.set(
        `motion:${this.id}`,
        JSON.stringify({ time: this.#time, rate: this.#rate }),
      );
    }

    #toggle() {
      if (this.#playing.value) {
        this.#pause();
        return;
      }
      if (reducedMotion()) {
        this.currentTime = this.duration;
        return;
      }
      if (this.#time >= this.duration) this.#time = 0;
      this.#seekVideos();
      this.#playing.value = true;
      this.#last = performance.now();
      this.#paint();
      for (const video of this.#videos) {
        video.playbackRate = this.#rate;
        video.play().catch((error) => {
          // A pause or seek may interrupt the browser's pending play request.
          if (error.name === "AbortError") return;
          this.#pause();
          raiseError(`Playback failed: ${error.message}`);
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
      if (this.#playing.value) this.#frame = nextAnimation(() => this.#tick());
    }

    #paintControls() {
      if (!this.#ui) return;
      // The media clock changes local inspection, not the page's state. Commit
      // the shared template without claiming semantic presentation every frame.
      render(this.render(), this, this.renderOptions);
    }

    #paint() {
      this.#paintControls();
      if (!this.isConnected) return;
      try {
        this.#draw?.(this.#time);
      } catch (error) {
        this.#pause();
        throw error;
      }
    }
  },
);
