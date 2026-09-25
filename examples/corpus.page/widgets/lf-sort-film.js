// <lf-sort-film>: the player around sort.js. It owns playback, the input choice and the
// narration, and paints in the page's own palette: every colour is a theme token resolved
// through a probe element, re-read when the page switches between light and dark.
//
// Each time the step changes it indicates the Rust source line that step executes, by
// its source line numbers, in the excerpts its three code attributes name, and dispatches `sort-step` (bubbling)
// so the page can keep that line in view.

import {
  indicate,
  inlineMarkdownFragment,
  loadMarkdown,
  offer,
  once,
  onMotionPreferenceChange,
  reducedMotion,
  registerVisualParts,
} from "/runtime/widget-api.js";
import {
  INPUTS,
  LINES,
  N,
  Painter,
  PHASE,
  frame,
  makeInput,
  plainMergeComparisons,
  stepAt,
  trace,
} from "../sort.js";

const SVGNS = "http://www.w3.org/2000/svg";

const TOKENS = {
  card: "var(--card)",
  field: "var(--field)",
  ink: "var(--ink)",
  ink2: "var(--ink-2)",
  muted: "var(--muted)",
  rule: "var(--rule)",
  faint: "color-mix(in srgb, var(--muted) 42%, var(--card))",
  accent: "var(--accent)",
  accentTint: "var(--accent-tint)",
  mark: "var(--mark-ink)",
  ok: "var(--ok)",
  warn: "var(--warn)",
  warnTint: "var(--warn-tint)",
  danger: "var(--danger)",
};

const PHASE_NAME = {
  scan: "Finding a natural run",
  insert: "Extending a short run with insertion sort",
  stack: "Pushing the run and checking the stack",
  merge: "Merging two adjacent runs",
  done: "Sorted",
};

const SPEEDS = [1, 2, 4, 0.5];
const AUTO_PLAY_DELAY = 1800;

function moment(id) {
  const match = /^moment:([a-z]+):(\d+):(\d+)$/.exec(id);
  if (!match || !Object.hasOwn(INPUTS, match[1])) return null;
  const seed = Number(match[2]);
  const index = Number(match[3]);
  return Number.isSafeInteger(seed) && Number.isSafeInteger(index)
    ? { input: match[1], seed, index }
    : null;
}

const momentLabel = (id) => {
  const at = moment(id);
  return at ? `${INPUTS[at.input]}, shuffle ${at.seed}, step ${at.index + 1}` : null;
};

customElements.define(
  "lf-sort-film",
  class extends HTMLElement {
    #input = "random";
    #seed = 7;
    #film = null;
    #values = null;
    #plain = 0;
    #t = 0;
    #playing = false;
    #speed = 2;
    #last = 0;
    #raf = 0;
    #step = -1;
    #C = null;
    #themeWatch = null;
    #autoPlayTimer = 0;

    connectedCallback() {
      this.#resolvePalette();
      if (once(this)) {
        this.#build();
        if (!reducedMotion())
          this.#autoPlayTimer = setTimeout(() => {
            this.#autoPlayTimer = 0;
            if (
              this.isConnected &&
              this.getClientRects().length &&
              document.visibilityState === "visible"
            )
              this.#play();
          }, AUTO_PLAY_DELAY);
      }
      loadMarkdown().then((ready) => {
        if (ready && this.isConnected && this.#step >= 0) this.#renderNote();
      });
      const repaint = () => {
        this.#resolvePalette();
        this.#paintTimeline();
        this.#paint();
      };
      const scheme = matchMedia("(prefers-color-scheme: dark)");
      scheme.addEventListener("change", repaint);
      const stopMotionWatch = onMotionPreferenceChange((reduce) => {
        if (reduce) this.#pause();
      });
      const observer = new MutationObserver(repaint);
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme", "class", "style"],
      });
      this.#themeWatch = () => {
        scheme.removeEventListener("change", repaint);
        stopMotionWatch();
        observer.disconnect();
      };
      this.#paint();
    }

    // One key to every excerpt: each quotes its own stretch of slice.rs, so a line
    // number lights in the one block that shows it and addresses nothing in the rest.
    #indicate(key) {
      for (const attr of ["sort-code", "head-code", "merge-code"])
        if (this.hasAttribute(attr)) indicate(this, attr, key);
    }

    disconnectedCallback() {
      this.#indicate(null);
      this.#themeWatch?.();
      this.#pause();
    }

    #resolvePalette() {
      const probe = document.createElement("span");
      probe.style.display = "none";
      this.append(probe);
      const C = {};
      for (const [k, expr] of Object.entries(TOKENS)) {
        probe.style.color = expr;
        C[k] = getComputedStyle(probe).color;
      }
      probe.remove();
      const root = getComputedStyle(document.documentElement);
      C.sans = root.getPropertyValue("--sans").trim() || "system-ui, sans-serif";
      C.mono = root.getPropertyValue("--mono").trim() || "ui-monospace, monospace";
      this.#C = C;
    }

    #build() {
      const stage = document.createElement("div");
      stage.className = "sort-stage";
      this.svg = document.createElementNS(SVGNS, "svg");
      this.svg.setAttribute("role", "img");
      this.svg.setAttribute(
        "aria-label",
        "The slice, the scratch buffer and the run stack at this step",
      );
      stage.append(this.svg);
      this.painter = new Painter(this.svg, N);
      // Each slot of v, the scratch lane, the run stack and each collapse() clause is a
      // visual part: Leaf's Alt-click targets that part, and the click pauses the sort
      // so the part holds still under the comment.
      this.parts = registerVisualParts(
        this,
        () => [
          ...this.painter.parts(),
          {
            id: this.momentEl.dataset.part,
            element: this.momentEl,
            label: momentLabel(this.momentEl.dataset.part),
          },
        ],
        { reveal: (id) => this.#revealMoment(id), label: momentLabel },
      );
      stage.addEventListener("click", (e) => {
        if (e.target.closest?.("[data-part]")) this.#pause();
      });

      this.narration = document.createElement("div");
      this.narration.className = "sort-narration";
      this.narration.setAttribute("aria-live", "polite");
      this.phaseEl = document.createElement("strong");
      this.noteEl = document.createElement("span");
      this.noteEl.dataset.lfMarkdownWords = "";
      this.momentEl = document.createElement("span");
      this.momentEl.className = "sort-moment";
      this.momentEl.addEventListener("click", () => this.#pause());
      this.momentCount = document.createElement("span");
      this.momentCount.className = "sort-moment-count";
      this.momentTail = document.createElement("span");
      this.momentTail.className = "sort-moment-tail";
      this.momentEl.append("Step ", this.momentCount, this.momentTail);
      this.narration.append(this.phaseEl, this.noteEl, this.momentEl);

      this.timeline = document.createElementNS(SVGNS, "svg");
      this.timeline.classList.add("sort-timeline");
      this.timeline.setAttribute("preserveAspectRatio", "none");
      this.timeline.setAttribute("viewBox", "0 0 1000 10");
      this.timeline.setAttribute("aria-hidden", "true");
      this.timeline.addEventListener("click", (e) => {
        const box = this.timeline.getBoundingClientRect();
        this.#pause();
        this.#t = ((e.clientX - box.left) / box.width) * this.#film.total;
        this.#paint();
      });

      const bar = offer("div", "sort-bar");
      this.playBtn = offer("button", "sort-play", "Play");
      this.playBtn.setAttribute("aria-keyshortcuts", "k , . ArrowLeft ArrowRight Home");
      this.playBtn.title = "k play/pause · ← → or , . one step · Home restart";
      this.playBtn.addEventListener("click", () => this.#toggle());
      const back = offer("button", "sort-step-btn", "‹");
      back.setAttribute("aria-label", "Previous step");
      back.addEventListener("click", () => this.#stepBy(-1));
      const fwd = offer("button", "sort-step-btn", "›");
      fwd.setAttribute("aria-label", "Next step");
      fwd.addEventListener("click", () => this.#stepBy(1));
      this.scrub = offer("input", "sort-scrub", "", "range");
      this.scrub.name = "sort-position";
      this.scrub.setAttribute("aria-label", "Position in the sort");
      this.scrub.min = 0;
      this.scrub.step = 0.01;
      this.scrub.addEventListener("input", () => {
        this.#pause();
        this.#t = Number(this.scrub.value);
        this.#paint();
      });
      this.speedBtn = offer("button", "sort-speed", `${this.#speed}×`);
      this.speedBtn.setAttribute("aria-label", "Playback speed");
      this.speedBtn.addEventListener("click", () => {
        this.#speed = SPEEDS[(SPEEDS.indexOf(this.#speed) + 1) % SPEEDS.length];
        this.speedBtn.textContent = `${this.#speed}×`;
      });
      bar.append(this.playBtn, back, fwd, this.scrub, this.speedBtn);

      const inputs = offer("fieldset", "sort-inputs");
      const legend = document.createElement("legend");
      legend.textContent = "Input";
      inputs.append(legend);
      this.radios = Object.entries(INPUTS).map(([key, label]) => {
        const wrap = document.createElement("label");
        const radio = offer("input", "", "", "radio");
        radio.name = `sort-input-${this.id}`;
        radio.value = key;
        radio.checked = key === this.#input;
        radio.addEventListener("change", () => {
          this.#input = key;
          this.#load();
        });
        const text = document.createElement("span");
        text.textContent = label;
        wrap.append(radio, text);
        inputs.append(wrap);
        return radio;
      });
      this.shuffleBtn = offer("button", "sort-shuffle", "Shuffle");
      this.shuffleBtn.addEventListener("click", () => {
        this.#seed++;
        this.#load();
      });
      inputs.append(this.shuffleBtn);

      this.stats = document.createElement("p");
      this.stats.className = "sort-stats";

      this.addEventListener("keydown", (e) => this.#key(e));
      this.append(stage, this.narration, this.timeline, bar, inputs, this.stats);
      this.#load();
    }

    #load() {
      this.#pause();
      this.#values = makeInput(this.#input, this.#seed);
      this.#film = trace(this.#values);
      this.#plain = plainMergeComparisons(this.#values);
      this.shuffleBtn.disabled = this.#input !== "random";
      this.#t = 0;
      this.#step = -1;
      this.scrub.max = this.#film.total;
      this.momentCount.style.width = `${String(this.#film.steps.length).length}ch`;
      this.momentTail.textContent = ` of ${this.#film.steps.length} · click to pause · Option/Alt-click to comment`;
      this.#paintTimeline();
      this.#paint();
    }

    #renderNote() {
      this.noteEl.replaceChildren(
        inlineMarkdownFragment(this.#film.steps[this.#step].note, false),
      );
    }

    // The timeline strip: each step's span coloured by phase, so where the time goes
    // (scanning, insertion, merging) is visible before playing.
    #paintTimeline() {
      const C = this.#C ?? {};
      const tl = this.timeline;
      tl.replaceChildren();
      const color = {
        scan: C.ink2,
        insert: C.warn,
        stack: C.mark,
        merge: C.accent,
        done: C.ok,
      };
      let phase = "scan";
      for (const s of this.#film.steps) {
        if (PHASE[s.kind]) phase = PHASE[s.kind];
        const r = document.createElementNS(SVGNS, "rect");
        r.setAttribute("x", (1000 * s.start) / this.#film.total);
        r.setAttribute("width", Math.max(0.6, (1000 * s.dur) / this.#film.total));
        r.setAttribute("height", 10);
        r.setAttribute("fill", color[phase] ?? C.muted);
        tl.append(r);
      }
      this.playhead = document.createElementNS(SVGNS, "rect");
      this.playhead.setAttribute("width", 3);
      this.playhead.setAttribute("height", 10);
      this.playhead.setAttribute("fill", C.ink);
      tl.append(this.playhead);
    }

    #paint() {
      if (!this.#film || !this.#C) return;
      const fr = frame(this.#film, this.#t);
      this.painter.paint(this.#film, fr, this.#C);
      this.scrub.value = this.#t;
      this.playhead?.setAttribute("x", (1000 * this.#t) / this.#film.total - 1.5);
      if (fr.i !== this.#step) {
        this.#step = fr.i;
        const s = fr.step;
        this.phaseEl.textContent = PHASE_NAME[s.phase];
        this.#renderNote();
        this.momentEl.dataset.part = `moment:${this.#input}:${this.#seed}:${fr.i}`;
        this.momentCount.textContent = fr.i + 1;
        this.dataset.phase = s.phase;
        const final = s.kind === "done";
        this.stats.textContent =
          `${s.cmp} comparisons and ${s.moves} element moves so far` +
          (final
            ? `. A plain top-down merge sort needs ${this.#plain} comparisons on this input.`
            : `, of ${this.#film.comparisons} in all.`);
        this.#indicate(s.line ? LINES[s.line] : null);
        this.dispatchEvent(
          new CustomEvent("sort-step", {
            bubbles: true,
            detail: { line: s.line, kind: s.kind, phase: s.phase },
          }),
        );
        // The stack and the clauses move as runs push and merge; re-read their geometry.
        this.parts?.update();
      }
    }

    #key(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target.type === "radio" && e.key.startsWith("Arrow")) return;
      const handled = {
        k: () => this.#toggle(),
        ",": () => this.#stepBy(-1),
        ".": () => this.#stepBy(1),
        ArrowLeft: () => this.#stepBy(-1),
        ArrowRight: () => this.#stepBy(1),
        Home: () => {
          this.#pause();
          this.#t = 0;
        },
      }[e.key];
      if (!handled) return;
      e.preventDefault();
      e.stopPropagation();
      handled();
      this.#paint();
    }

    // One step: land at its end, so the change is fully drawn.
    #stepBy(dir) {
      this.#pause();
      const i = stepAt(this.#film, this.#t);
      const j = Math.max(0, Math.min(this.#film.steps.length - 1, i + dir));
      const target = this.#film.steps[j];
      this.#t = target.start + target.dur - 0.01;
      this.#paint();
    }

    // A moment's address includes the exact input, so following a thread restores the
    // trace it described before seeking to the step.
    #revealMoment(id) {
      const at = moment(id);
      if (!at) return;
      const { input, seed, index } = at;
      if (index >= trace(makeInput(input, seed)).steps.length) return;
      if (input !== this.#input || seed !== this.#seed) {
        this.#input = input;
        this.#seed = seed;
        for (const radio of this.radios) radio.checked = radio.value === input;
        this.#load();
      } else this.#pause();
      const step = this.#film.steps[index];
      if (!step) return;
      this.#t = step.start + step.dur - 0.01;
      this.#paint();
    }

    #toggle() {
      this.#playing ? this.#pause() : this.#play();
    }

    #play() {
      clearTimeout(this.#autoPlayTimer);
      this.#autoPlayTimer = 0;
      if (this.#t >= this.#film.total - 0.01) this.#t = 0;
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
      clearTimeout(this.#autoPlayTimer);
      this.#autoPlayTimer = 0;
      this.#playing = false;
      cancelAnimationFrame(this.#raf);
      if (this.playBtn)
        this.playBtn.textContent =
          this.#film && this.#t >= this.#film.total - 0.01 ? "Replay" : "Play";
    }
  },
);
