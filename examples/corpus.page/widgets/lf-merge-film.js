// <lf-merge-film>: the player around film.js. It owns playback and the flag controls.
//
// The stage is a Leaf visual with parts, not a control, so it is neither an offer nor a
// tab stop. Hovering a commit, ref, worktree or hook shows what it is and lights a
// commit's ancestry. A click or tap on a part pauses the film and reads its details;
// Inspect and `i` cycle through parts when the drawing is too small to aim at. A tap
// on empty stage or Escape closes inspection. Leaf's own target gestures (Alt-click,
// or `s` after pointing) comment on a part. Terminal lines seek to their printed moment.
// A narrow stage reads the same frame as vertical history, worktree rows and a
// terminal disclosure, with step buttons holding each outcome.
//
// The film opens paused on its poster, the fully drawn branch just before `wt merge`
// runs, so a first look (or a capture) reads the setup at once; Play runs it from the
// start.
//
// Every paint dispatches `film-frame` with the chapter, its caption and the run's status,
// so the page can tell the current step beside the film.

import {
  keeps,
  keepsHidden,
  keepsText,
  offer,
  once,
  registerVisualParts,
  scrollIntoReadingBand,
  sizeObserver,
} from "/runtime/widget-api.js";
import { DEFAULT_FLAGS, EXAMPLE, Painter, compile, frame } from "../film.js";

import { PhonePainter } from "../phone.js";

const SVG = "http://www.w3.org/2000/svg";
const chapterEnd = (film, key) => {
  const last = film.scenes.findLast((scene) => scene.chapter === key);
  return last.start + last.dur;
};

const FLAG_CONTROLS = [
  ["moved", "main moved on", false],
  ["conflict", "main touched the same lines", false],
  ["hookFails", "a pre-merge test fails", false],
  ["squash", "--no-squash", true],
  ["rebase", "--no-rebase", true],
  ["ff", "--no-ff", true],
  ["remove", "--no-remove", true],
];

customElements.define(
  "lf-merge-film",
  class extends HTMLElement {
    #flags = { ...DEFAULT_FLAGS };
    #film = compile(this.#flags, EXAMPLE);
    #t = this.#poster();
    #fresh = true;
    #playing = false;
    #speed = 1;
    #last = 0;
    #raf = 0;
    #focus = null;
    #inspected = null;

    connectedCallback() {
      if (once(this)) this.#build();
      this.sizing.observe(this.stage);
      this.#paint();
    }

    disconnectedCallback() {
      this.sizing.disconnect();
      cancelAnimationFrame(this.#raf);
      this.#playing = false;
    }

    #build() {
      const stage = document.createElement("div");
      stage.className = "film-stage";
      this.svg = document.createElementNS(SVG, "svg");
      this.svg.setAttribute("role", "img");
      this.svg.setAttribute("aria-label", "wt merge, animated");
      stage.append(this.svg);
      this.desktopPainter = new Painter(this.svg);
      this.phonePainter = new PhonePainter(stage);
      this.painter = this.desktopPainter;
      this.sizing = sizeObserver(() => this.#paint());
      this.inspector = document.createElement("div");
      this.inspector.className = "film-inspect";
      this.inspector.hidden = true;
      this.inspector.setAttribute("role", "status");
      this.inspectorTitle = document.createElement("strong");
      this.inspectorBody = document.createElement("span");
      this.inspector.append(this.inspectorTitle, this.inspectorBody);
      stage.append(this.inspector);
      stage.addEventListener("click", (e) => this.#click(e));
      stage.addEventListener("pointermove", (e) => this.#hover(e));
      stage.addEventListener("pointerleave", (e) => {
        if (e.pointerType !== "touch") this.#inspect(null);
      });
      this.addEventListener("keydown", (e) => this.#key(e));

      this.parts = registerVisualParts(this, () =>
        this.painter.parts().map(({ id, element, label }) => ({ id, element, label })),
      );

      const bar = offer("div", "film-bar");
      this.playBtn = offer("button", "film-play", "Play");
      this.playBtn.setAttribute(
        "aria-keyshortcuts",
        "k ArrowLeft ArrowRight j l i Escape",
      );
      this.playBtn.title =
        "k play/pause · ←/→ steps · j/l ±2s · i inspect the next element · Esc close";
      this.playBtn.addEventListener("click", () => this.#toggle());
      this.scrub = offer("input", "film-scrub", "", "range");
      this.scrub.name = "film-position";
      this.scrub.setAttribute("aria-label", "Film position");
      this.scrub.min = 0;
      this.scrub.step = 0.01;
      this.scrub.addEventListener("input", () => {
        this.#pause();
        this.#t = Number(this.scrub.value);
        this.#inspect(null);
        this.#paint();
      });
      this.speedBtn = offer("button", "film-speed", "1×");
      this.speedBtn.setAttribute("aria-label", "Playback speed");
      this.speedBtn.addEventListener("click", () => {
        this.#speed = this.#speed === 1 ? 2 : this.#speed === 2 ? 0.5 : 1;
        this.speedBtn.textContent = `${this.#speed}×`;
      });
      this.previous = offer("button", "film-previous", "Previous");
      this.next = offer("button", "film-next", "Next");
      this.previous.setAttribute("aria-label", "Previous step");
      this.next.setAttribute("aria-label", "Next step");
      for (const [button, direction] of [
        [this.previous, -1],
        [this.next, 1],
      ])
        button.addEventListener("click", () => {
          this.#pause();
          this.#holdChapter(direction);
          this.#paint();
        });
      const inspectBtn = offer("button", "film-inspect-next", "Inspect");
      inspectBtn.setAttribute("aria-label", "Inspect next element");
      inspectBtn.setAttribute("aria-keyshortcuts", "i");
      inspectBtn.addEventListener("click", () => this.#cycle());
      bar.append(
        this.playBtn,
        this.previous,
        this.scrub,
        this.next,
        this.speedBtn,
        inspectBtn,
      );
      this.caption = document.createElement("p");
      this.caption.className = "film-caption";

      const flags = offer("fieldset", "film-flags");
      const legend = document.createElement("legend");
      legend.textContent = "Change the run";
      flags.append(legend);
      for (const [key, label, inverted] of FLAG_CONTROLS) {
        const wrap = document.createElement("label");
        const box = offer("input", "", "", "checkbox");
        box.name = `film-flag-${key}`;
        box.checked = inverted ? !this.#flags[key] : this.#flags[key];
        box.addEventListener("change", () => {
          this.#flags[key] = inverted ? !box.checked : box.checked;
          this.#recompile();
        });
        const text = document.createElement(inverted ? "code" : "span");
        text.textContent = label;
        wrap.append(box, text);
        flags.append(wrap);
      }

      this.settings = document.createElement("details");
      this.settings.className = "film-settings";
      const settingsTitle = document.createElement("summary");
      settingsTitle.textContent = "Change the run";
      this.settings.append(settingsTitle, flags);
      this.append(this.caption, stage, bar, this.settings);
      this.stage = stage;
      this.scrub.max = this.#film.total;
    }

    // Dispatch film-frame for the current moment, for a listener that arrived late.
    announce() {
      this.#paint();
    }

    seek(t) {
      this.#pause();
      this.#inspect(null);
      this.#t = Math.max(0, Math.min(this.#film.total, t));
      this.#paint();
      this.#reveal();
    }

    seekChapter(key) {
      const at = this.#film.starts[key];
      if (at === undefined) return;
      this.#inspect(null);
      this.#fresh = false;
      this.#t = at;
      this.#paint();
      if (!this.#playing) this.#play();
      this.#reveal();
    }

    #reveal() {
      if (this.hasAttribute("data-phone")) {
        if (this.settings.open) this.settings.open = false;
        scrollIntoReadingBand(this, this, "start", "smooth");
      }
    }

    // The last moment before the first step: every commit, ref and worktree drawn.
    #poster() {
      return this.#film.starts.commit - 0.01;
    }

    #recompile() {
      const chapter = frame(this.#film, this.#t).chapter;
      const start = this.#film.starts[chapter];
      const progress = (this.#t - start) / (chapterEnd(this.#film, chapter) - start);
      this.#film = compile(this.#flags, EXAMPLE);
      this.#t = this.#fresh
        ? this.#poster()
        : this.#film.starts[chapter] !== undefined
          ? this.#film.starts[chapter] +
            progress * (chapterEnd(this.#film, chapter) - this.#film.starts[chapter])
          : Math.min(this.#t, this.#film.total);
      keeps(this.scrub, "max", this.#film.total);
      this.#inspect(null);
      this.#paint();
    }

    #partAt(target) {
      const g = target.closest?.("[data-label]");
      if (!g) return null;
      return this.painter.parts().find((p) => p.element === g) ?? null;
    }

    #click(e) {
      const line = e.target.closest?.("[data-at]");
      if (line) {
        this.#pause();
        this.#inspect(null);
        this.#t = Number(line.dataset.at);
        this.#paint();
      } else {
        const part = this.#partAt(e.target);
        if (part) this.#pause();
        // Alt-click belongs to Leaf's visual comment route.
        if (!e.altKey) this.#inspect(part?.id ?? null);
      }
    }

    #hover(e) {
      if (e.pointerType === "touch") return;
      const part = this.#partAt(e.target);
      this.stage.classList.toggle("film-seekable", !!e.target.closest?.("[data-at]"));
      this.#inspect(part?.id ?? null);
    }

    #inspect(id) {
      this.#inspected = id;
      const focus = id?.startsWith("commit:") ? id.slice(7) : null;
      if (focus !== this.#focus) {
        this.#focus = focus;
        this.#paint();
      } else this.#placeInspector();
    }

    // The inspector sits beside its part, in stage pixels, and follows it while the
    // film plays; it closes when the part leaves the frame.
    #placeInspector() {
      const part =
        this.#inspected && this.painter.parts().find((p) => p.id === this.#inspected);
      for (const p of this.painter.parts())
        p.element.classList.toggle("film-picked", p === part);
      if (!part) {
        keepsHidden(this.inspector, true);
        if (this.#inspected) this.#inspect(null);
        return;
      }
      const box = part.element.getBoundingClientRect();
      const stage = this.stage.getBoundingClientRect();
      keepsText(this.inspectorTitle, part.label);
      keepsText(this.inspectorBody, part.info);
      keepsHidden(this.inspector, false);
      const left = Math.min(
        box.right - stage.left + 10,
        stage.width - this.inspector.offsetWidth - 10,
      );
      const bottom = this.hasAttribute("data-phone")
        ? Math.min(stage.bottom, window.innerHeight)
        : stage.bottom;
      const top = Math.min(
        box.top - stage.top,
        bottom - stage.top - this.inspector.offsetHeight - 10,
      );
      this.inspector.style.left = `${Math.max(10, left)}px`;
      const visibleTop = this.hasAttribute("data-phone")
        ? Math.max(10, 10 - stage.top)
        : 10;
      this.inspector.style.top = `${Math.max(visibleTop, top)}px`;
    }

    // Film keys work from any of the film's controls. Keys a focused control already
    // uses for itself (arrows on the scrubber, Space on a button) stay the control's.
    #key(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target === this.scrub && e.key.startsWith("Arrow")) return;
      const handled = {
        k: () => this.#toggle(),
        Escape: () => (this.#inspected ? this.#inspect(null) : null),
        i: () => this.#cycle(),
        Home: () => (this.#t = 0),
        j: () => (this.#t = Math.max(0, this.#t - 2)),
        l: () => (this.#t = Math.min(this.#film.total, this.#t + 2)),
        ArrowRight: () => this.#stepChapter(1),
        ArrowLeft: () => this.#stepChapter(-1),
      }[e.key];
      if (!handled) return;
      // Escape with nothing open belongs to Leaf, which returns focus to the page.
      if (e.key === "Escape" && !this.#inspected) return;
      e.preventDefault();
      e.stopPropagation();
      if (e.key !== "k") this.#fresh = false;
      if (["Home", "j", "l"].includes(e.key)) this.#inspect(null);
      handled();
      this.#paint();
    }

    #cycle() {
      this.#pause();
      if (this.hasAttribute("data-phone")) {
        this.settings.open = false;
        scrollIntoReadingBand(this.playBtn.parentElement, this, "start", "instant");
      }
      const parts = this.painter.parts();
      if (!parts.length) return;
      const at = parts.findIndex((p) => p.id === this.#inspected);
      const next = parts[(at + 1) % parts.length];
      this.#inspect(next.id);
    }

    #stepChapter(dir) {
      this.#inspect(null);
      const starts = [...new Set(Object.values(this.#film.starts))].sort(
        (a, b) => a - b,
      );
      this.#t =
        dir > 0
          ? (starts.find((s) => s > this.#t + 0.05) ?? this.#t)
          : (starts.findLast((s) => s < this.#t - 0.6) ?? 0);
    }

    // The phone's step buttons hold the outcome, rather than the first frame of a
    // transition. Playback and the keyboard's timeline keys retain their own routes.
    #holdChapter(direction) {
      this.#inspect(null);
      const keys = Object.keys(this.#film.starts);
      const current = keys.indexOf(frame(this.#film, this.#t).chapter);
      const chapter = keys[Math.max(0, Math.min(keys.length - 1, current + direction))];
      this.#t = chapterEnd(this.#film, chapter) - 0.01;
    }

    #toggle() {
      this.#playing ? this.#pause() : this.#play();
    }

    #play() {
      if (this.#fresh || this.#t >= this.#film.total - 0.01) this.#t = 0;
      this.#fresh = false;
      this.#playing = true;
      this.#last = performance.now();
      this.playBtn.textContent = "Pause";
      const tick = (now) => {
        if (!this.#playing) return;
        this.#t += ((now - this.#last) / 1000) * this.#speed;
        this.#last = now;
        if (this.#t >= this.#film.total) {
          this.#t = this.#film.total;
          this.#pause();
        }
        this.#paint();
        if (this.#playing) this.#raf = requestAnimationFrame(tick);
      };
      this.#raf = requestAnimationFrame(tick);
    }

    #pause() {
      this.#fresh = false;
      this.#playing = false;
      cancelAnimationFrame(this.#raf);
      keepsText(this.playBtn, this.#t >= this.#film.total - 0.01 ? "Replay" : "Play");
    }

    #paint() {
      const fr = frame(this.#film, this.#t);
      const width = this.stage.clientWidth;
      const narrow = width < 560;
      if (this.hasAttribute("data-phone") !== narrow) this.settings.open = !narrow;
      else if (!narrow && !this.settings.open) this.settings.open = true;
      this.stage.toggleAttribute("data-phone", narrow);
      this.toggleAttribute("data-phone", narrow);
      this.painter = narrow ? this.phonePainter : this.desktopPainter;
      if (narrow) this.painter.paint(this.#film, fr, width);
      else this.painter.paint(this.#film, fr, this.#focus);
      keepsText(this.caption, fr.caption);
      keeps(this.caption, "data-tone", fr.captionTone);
      const first = fr.chapter === "setup";
      const last = fr.chapter === "end";
      if (this.previous.disabled !== first) this.previous.disabled = first;
      if (this.next.disabled !== last) this.next.disabled = last;
      this.scrub.value = this.#t;
      this.#placeInspector();
      // Every paint can move a part, so Leaf re-reads the inventory and its geometry.
      this.parts.update();
      this.dispatchEvent(
        new CustomEvent("film-frame", {
          bubbles: true,
          detail: {
            chapter: fr.chapter,
            caption: fr.caption,
            captionTone: fr.captionTone,
            status: this.#film.status,
          },
        }),
      );
    }
  },
);
