// <lf-merge-film>: the player around film.js. It owns playback, the flag controls and
// the theme the drawing takes.
//
// The stage is a Leaf visual with parts, not a control, so it is neither an offer nor a
// tab stop. Hovering a commit, ref, worktree or hook shows what it is and lights a
// commit's ancestry. A click on a part pauses the film so it holds still; Leaf's own
// target gestures (Alt-click, or `s` after pointing) comment on it. Terminal lines are
// SVG links, so a click on one seeks to the moment it printed.
//
// The film opens paused on its poster, the fully drawn branch just before `wt merge`
// runs, so a first look (or a capture) reads the setup at once; Play runs it from the
// start.
//
// Every paint dispatches `film-frame` with the chapter, its caption and the run's status,
// so the page can tell the current step beside the film.

import { offer, once, registerVisualParts } from "/runtime/widget-api.js";
import { DEFAULT_FLAGS, EXAMPLE, Painter, compile, frame, themePalette } from "../film.js";

const SVG = "http://www.w3.org/2000/svg";

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
    #partSig = "";
    #unwatchTheme = null;

    connectedCallback() {
      if (once(this)) this.#build();
      // The page theme can change under the film: the OS scheme, or Leaf's theme toggle.
      const retheme = () => {
        this.painter.setPalette(themePalette(this));
        this.#paint();
        this.parts.update();
      };
      const scheme = matchMedia("(prefers-color-scheme: dark)");
      scheme.addEventListener("change", retheme);
      const observer = new MutationObserver(retheme);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      this.#unwatchTheme = () => {
        scheme.removeEventListener("change", retheme);
        observer.disconnect();
      };
      this.#paint();
    }

    disconnectedCallback() {
      this.#unwatchTheme?.();
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
      this.painter = new Painter(this.svg, themePalette(this));
      this.inspector = document.createElement("div");
      this.inspector.className = "film-inspect";
      this.inspector.hidden = true;
      this.inspector.setAttribute("role", "status");
      stage.append(this.inspector);
      stage.addEventListener("click", (e) => this.#click(e));
      stage.addEventListener("pointermove", (e) => this.#hover(e));
      stage.addEventListener("pointerleave", () => {
        this.#inspect(null);
        this.#setFocus(null);
      });
      this.addEventListener("keydown", (e) => this.#key(e));

      this.parts = registerVisualParts(this, () =>
        this.painter.parts().map(({ id, element, label }) => ({ id, element, label })),
      );

      const bar = offer("div", "film-bar");
      this.playBtn = offer("button", "film-play", "Play");
      this.playBtn.setAttribute("aria-keyshortcuts", "k ArrowLeft ArrowRight j l i Escape");
      this.playBtn.title = "k play/pause · ←/→ steps · j/l ±2s · i inspect the next element · Esc close";
      this.playBtn.addEventListener("click", () => this.#toggle());
      this.scrub = offer("input", "film-scrub", "", "range");
      this.scrub.name = "film-position";
      this.scrub.setAttribute("aria-label", "Film position");
      this.scrub.min = 0;
      this.scrub.step = 0.01;
      this.scrub.addEventListener("input", () => {
        this.#pause();
        this.#t = Number(this.scrub.value);
        this.#paint();
      });
      this.speedBtn = offer("button", "film-speed", "1×");
      this.speedBtn.setAttribute("aria-label", "Playback speed");
      this.speedBtn.addEventListener("click", () => {
        this.#speed = this.#speed === 1 ? 2 : this.#speed === 2 ? 0.5 : 1;
        this.speedBtn.textContent = `${this.#speed}×`;
      });
      bar.append(this.playBtn, this.scrub, this.speedBtn);

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

      this.append(stage, bar, flags);
      this.stage = stage;
      this.scrub.max = this.#film.total;
    }

    // A static export keeps the drawing but not the script: freeze a poster moment that
    // shows the landed graph and the whole terminal, and drop controls that could not work.
    lfPrepareExport() {
      this.#pause();
      this.#inspect(null);
      const post = this.#film.starts.postmerge ?? this.#film.starts.end;
      this.#t = post + 2;
      this.#paint();
      for (const node of [...this.children]) if (node !== this.stage) node.remove();
    }

    // Dispatch film-frame for the current moment, for a listener that arrived late.
    announce() {
      this.#paint();
    }

    seek(t) {
      this.#pause();
      this.#t = Math.max(0, Math.min(this.#film.total, t));
      this.#paint();
    }

    seekChapter(key) {
      const at = this.#film.starts[key];
      if (at === undefined) return;
      this.#inspect(null);
      this.#fresh = false;
      this.#t = at;
      this.#paint();
      if (!this.#playing) this.#play();
    }

    // The last moment before the first step: every commit, ref and worktree drawn.
    #poster() {
      return this.#film.starts.commit - 0.01;
    }

    #recompile() {
      const chapter = frame(this.#film, this.#t).chapter;
      this.#film = compile(this.#flags, EXAMPLE);
      this.#t = this.#fresh ? this.#poster() : (this.#film.starts[chapter] ?? Math.min(this.#t, this.#film.total));
      this.scrub.max = this.#film.total;
      this.#inspect(null);
      this.#paint();
    }

    #partAt(target) {
      const g = target.closest?.("g[data-label]");
      if (!g) return null;
      return this.painter.parts().find((p) => p.element === g) ?? null;
    }

    #click(e) {
      const line = e.target.closest?.("[data-at]");
      if (line) {
        this.#pause();
        this.#t = Number(line.dataset.at);
        this.#paint();
      } else if (this.#partAt(e.target)) this.#pause();
    }

    #hover(e) {
      const part = this.#partAt(e.target);
      this.stage.classList.toggle("film-seekable", !!e.target.closest?.("[data-at]"));
      this.#inspect(part?.id ?? null);
      this.#setFocus(part?.id.startsWith("commit:") ? part.id.slice(7) : null);
    }

    #setFocus(id) {
      if (id === this.#focus) return;
      this.#focus = id;
      if (!this.#playing) this.#paint();
    }

    #inspect(id) {
      this.#inspected = id;
      this.#placeInspector();
    }

    // The inspector sits beside its part, in stage pixels, and follows it while the
    // film plays; it closes when the part leaves the frame.
    #placeInspector() {
      const part = this.#inspected && this.painter.parts().find((p) => p.id === this.#inspected);
      for (const p of this.painter.parts()) p.element.classList.toggle("film-picked", p === part);
      if (!part) {
        this.inspector.hidden = true;
        return;
      }
      const box = part.element.getBoundingClientRect();
      const stage = this.stage.getBoundingClientRect();
      this.inspector.replaceChildren();
      const title = document.createElement("strong");
      title.textContent = part.label;
      const body = document.createElement("span");
      body.textContent = part.info;
      this.inspector.append(title, body);
      this.inspector.hidden = false;
      const left = Math.min(box.right - stage.left + 10, stage.width - this.inspector.offsetWidth - 10);
      const top = Math.min(box.top - stage.top, stage.height - this.inspector.offsetHeight - 10);
      this.inspector.style.left = `${Math.max(10, left)}px`;
      this.inspector.style.top = `${Math.max(10, top)}px`;
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
      handled();
      this.#paint();
    }

    #cycle() {
      this.#pause();
      const parts = this.painter.parts();
      if (!parts.length) return;
      const at = parts.findIndex((p) => p.id === this.#inspected);
      const next = parts[(at + 1) % parts.length];
      this.#inspect(next.id);
      this.#setFocus(next.id.startsWith("commit:") ? next.id.slice(7) : null);
    }

    #stepChapter(dir) {
      this.#inspect(null);
      const starts = [...new Set(Object.values(this.#film.starts))].sort((a, b) => a - b);
      this.#t =
        dir > 0
          ? (starts.find((s) => s > this.#t + 0.05) ?? this.#t)
          : (starts.findLast((s) => s < this.#t - 0.6) ?? 0);
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
      this.playBtn.textContent = this.#t >= this.#film.total - 0.01 ? "Replay" : "Play";
      this.#announceParts(true);
    }

    #paint() {
      const fr = frame(this.#film, this.#t);
      this.painter.paint(this.#film, fr, this.#focus);
      this.scrub.value = this.#t;
      if (this.#inspected) this.#placeInspector();
      this.#announceParts(!this.#playing);
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

    // Leaf re-reads the part inventory and its geometry on update(). While playing,
    // announce only when the set of parts changes; paused, every paint may have moved them.
    #announceParts(always) {
      const sig = this.painter.parts().map((p) => p.id).join(" ");
      if (!always && sig === this.#partSig) return;
      this.#partSig = sig;
      this.parts.update();
    }
  },
);
