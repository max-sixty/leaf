/* One finite clock for page-authored illustrations. The author supplies a
 * synchronous renderFrame(time) in milliseconds; it paints every compared view
 * from the same instant and owns their geometry and meaning. Assigning the
 * renderer draws immediately, so either module may load first. This is not
 * recorded evidence: recordings retain their native clocks in lf-trace.
 *
 * Playback, speed and scrubbing are local inspection, never page events. The
 * clock starts still, stops on disconnect/inspection, and resumes only on Play.
 * Reduced motion skips playback to the end but leaves manual seeking available.
 * Author callbacks must draw a complete frame, including when seeking backward.
 */
import {
  LeafElement,
  initialRender,
  commands,
  whileConnected,
  nextAnimation,
  cancelAnimation,
  reducedMotion,
  onMotionPreferenceChange,
  onUserInput,
  keeps,
  keepsText,
  relabel,
  paintKeys,
  tabStore,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-motion",
  class extends LeafElement {
    #ui;
    #draw;
    #time = 0;
    #playing = false;
    #frame = null;
    #last = 0;
    #label;
    #rate = 1;

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
          when: () => Boolean(this.#draw),
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
          if (reducedMotion() && this.#playing) this.currentTime = this.duration;
          else this.#paintControls();
        });
        this.#paint();
        return () => {
          this.#pause();
          input();
          preference();
        };
      });
    }

    // Initial markup and authored figures are retained, not template-owned.
    render() {
      return;
    }

    #playLabel() {
      if (this.#playing) return "Pause";
      if (reducedMotion()) return "Show end";
      return this.#time >= this.duration ? "Replay" : "Play";
    }

    #pause() {
      if (this.#frame !== null) cancelAnimation(this.#frame);
      this.#frame = null;
      this.#playing = false;
      this.#paintControls();
      if (this.#ui) this.#save();
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
      this.#playing = true;
      this.#last = performance.now();
      this.#paint();
      this.#frame = nextAnimation(() => this.#tick());
    }

    #tick() {
      this.#frame = null;
      const now = performance.now();
      this.#time = Math.min(
        this.duration,
        this.#time + (now - this.#last) * this.#rate,
      );
      this.#last = now;
      if (this.#time >= this.duration) {
        this.#playing = false;
        this.#save();
      }
      this.#paint();
      if (this.#playing) this.#frame = nextAnimation(() => this.#tick());
    }

    #paintControls() {
      if (!this.#ui) return;
      this.#ui.time.value = String(this.#time);
      keeps(this.#ui.time, "aria-valuetext", `${Math.round(this.#time)} milliseconds`);
      keepsText(this.#ui.clock, `${Math.round(this.#time)} ms`);
      const label = this.#playLabel();
      if (this.#label !== label) {
        this.#label = label;
        relabel(this.#ui.playLabel, label, { says: false });
        paintKeys();
      }
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
