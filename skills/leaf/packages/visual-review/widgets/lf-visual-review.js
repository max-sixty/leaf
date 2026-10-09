/* A visual run is external evidence: one source supplies its cases, while Leaf's event
 * log owns case dispositions and threads. The module keeps browsing and inspection
 * choices local, projects each case with source provenance, and reshapes the existing
 * aligned lf-shot comparison without introducing another evidence model. Evidence
 * precedes judgment; inspection is a local disclosure. Remaining-case navigation
 * reads the same projected dispositions as their buttons, while the case picker
 * retains every case so a reviewer can revisit a judgment. */
import "/widgets/lf-shot.js";
import "../vendor/webawesome.esm.js";

import {
  cancelRender,
  commands,
  countAreas,
  describeDifference,
  compoundReadingRegionId,
  placeThreads,
  placeKeeper,
  failSoft,
  focusDestination,
  holdFocus,
  keeps,
  keepsHidden,
  layoutChanged,
  nextRender,
  notice,
  offer,
  once,
  paintKeys,
  PRESS,
  projectData,
  readingPosture,
  registerReadingRegion,
  relabel,
  scopedMediaUrl,
  scrollerFor,
  scrollIntoReadingBand,
  scrollBehavior,
  setChildren,
  shownWindow,
  sizeObserver,
  watchData,
  widgetController,
  focused,
} from "/runtime/widget-api.js";

const CLASSIFICATION = {
  changed: "Changed",
  clean: "Clean",
};

const DISPOSITION = {
  "looks-right": "Looks right",
  "needs-work": "Needs work",
};

const INSPECTION = {
  compare: "Compare",
  flip: "Flip",
  overlay: "Overlay",
};

const SCALE = {
  fit: "Fit",
  actual: "100%",
};

// The smallest scale Fit shrinks a pair to so it fits its pane whole: at it, a captured
// page's 16px body text stays above 11px.
const READABLE_SCALE = 0.7;

const SCOPE = {
  focus: "Focus change",
  full: "Full frame",
};

// The object-view-box crop keeps the image itself at the focused size without an
// overflowing render surface. Browsers that do not ship it still show the complete
// evidence and the authored region, rather than presenting a distorted full image as
// a focused crop.
const FOCUS_CROP_SUPPORTED =
  globalThis.CSS?.supports?.("object-view-box", "inset(0px)") === true;

function make(tag, className, text = null, says = true) {
  const element = document.createElement(tag);
  element.className = className;
  if (text !== null) relabel(element, text, { says });
  return element;
}

function setText(element, text) {
  relabel(element, text, { says: true });
}

function previewUrl(target, path) {
  const base = new URL(target.url);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path.replace(/^\/+/, ""), base).href;
}

function link(className, label) {
  const anchor = offer("a", className, label);
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

customElements.define(
  "lf-visual-review",
  class extends HTMLElement {
    #controller = widgetController(this);
    #caseEntries = new Map();
    #casesBody = null;
    #commands = null;
    #evidenceHost = null;
    #stopEvidence = null;
    #inspector = null;
    #layoutFrame = null;
    #mode = "compare";
    #onGeometryChange = () => this.#scheduleEvidenceLayout();
    #opacity = 50;
    #progress = null;
    #queue = null;
    #queueHost = null;
    #reviewUnits = {};
    #run = null;
    #scale = "fit";
    #scope = "focus";
    #selected = null;
    #snapshot = null;
    #sizes = null;
    #threadSurface = null;
    #title = null;

    connectedCallback() {
      const firstConnection = once(this);
      if (firstConnection) this.#buildLayout();
      this.#stopEvidence ??= registerReadingRegion({
        id: compoundReadingRegionId(this, "evidence"),
        host: this.#evidenceHost,
        body: this.#casesBody,
      });
      this.#sizes = sizeObserver(() => this.#scheduleEvidenceLayout());
      this.#sizes.observe(this);
      this.#sizes.observe(this.#casesBody);
      for (const stage of this.querySelectorAll(
        ".lf-vr-shot-host, .lf-vr-case-head, .lf-vr-toolbar-slot",
      ))
        this.#sizes.observe(stage);
      window.addEventListener("resize", this.#onGeometryChange);
      this.#threadSurface ??= placeThreads(this, (targets) =>
        targets.map((target) => this.#threadOutlet(target)),
      );
      if (firstConnection) this.#controller.subscribe(() => this.#paintAvailability());
      if (firstConnection) watchData(this, "run", (snapshot) => this.#show(snapshot));
    }

    disconnectedCallback() {
      this.#threadSurface?.unregister();
      this.#threadSurface = null;
      this.#sizes?.disconnect();
      this.#sizes = null;
      window.removeEventListener("resize", this.#onGeometryChange);
      if (this.#layoutFrame !== null) cancelRender(this.#layoutFrame);
      this.#layoutFrame = null;
      this.#stopEvidence?.();
      this.#stopEvidence = null;
    }

    // The review composes the layer's pane grammar rather than choosing a posture: a
    // heading, then one evidence pane whose header is the case navigation and whose
    // body holds the cases.
    #buildLayout() {
      const header = make("header", "lf-vr-head");
      this.#title = make("h2", "lf-vr-title", "Waiting for a visual run");
      this.#progress = make("p", "lf-vr-progress", "No cases reviewed");
      header.append(this.#title, this.#progress);

      this.#queueHost = offer("nav", "lf-vr-queue-region");
      this.#queueHost.setAttribute("aria-label", "Visual review cases");
      const previous = offer("button", "lf-btn lf-vr-previous", "Previous");
      previous.type = "button";
      this.#queue = offer("wa-select", "lf-vr-case-select");
      this.#queue.name = "visual-case";
      this.#queue.size = "s";
      this.#queue.label = "Selected visual case";
      this.#queue.setAttribute("aria-label", "Selected visual case");
      this.#queue.addEventListener("change", () => this.#select(this.#queue.value));
      const next = offer("button", "lf-btn lf-vr-next", "Next");
      next.type = "button";
      this.#queueHost.append(this.#queue, previous, next);
      const queue = make("header", "lf-vr-queue");
      queue.append(this.#queueHost);

      this.#evidenceHost = make("section", "lf-vr-evidence-region");
      this.#evidenceHost.dataset.lfReadingRole = "pane";
      this.#evidenceHost.dataset.lfGenerated = "";
      this.#evidenceHost.setAttribute("aria-label", "Selected visual evidence");
      this.#inspector = this.#buildInspector();
      this.#casesBody = make("div", "lf-vr-cases");
      this.#evidenceHost.append(queue, this.#casesBody);

      this.append(header, this.#evidenceHost);
      this.#registerCommands();
      this.#paintInspector();
    }

    #buildInspector() {
      const inspector = make("details", "lf-vr-inspection");
      const summary = offer(
        "summary",
        "lf-vr-inspection-summary",
        "Inspect comparison",
      );
      const controls = offer("div", "lf-vr-inspector");
      inspector.append(summary, controls);
      inspector.setAttribute("aria-label", "Inspection controls");

      for (const [kind, values] of [
        ["scope", SCOPE],
        ["mode", INSPECTION],
        ["scale", SCALE],
      ]) {
        const group = offer(
          "wa-radio-group",
          `lf-vr-inspector-group lf-vr-${kind}-group`,
        );
        group.label = { scope: "Scope", mode: "View", scale: "Size" }[kind];
        group.name = `${this.id}-${kind}`;
        group.size = "s";
        group.orientation = "horizontal";
        group.addEventListener("change", () => {
          if (kind === "scope") this.#setScope(group.value);
          else if (kind === "mode") this.#setMode(group.value);
          else this.#setScale(group.value);
        });
        for (const [value, text] of Object.entries(values)) {
          const radio = offer(
            "wa-radio",
            "lf-vr-inspector-choice",
            text,
            undefined,
            true,
          );
          radio.value = value;
          radio.appearance = "button";
          radio.dataset[kind] = value;
          commands(radio, "On visual evidence", [
            {
              id: `visual.${kind}.${value}`,
              keys: PRESS,
              title: text.toLowerCase(),
              run: () => radio.click(),
            },
          ]);
          group.append(radio);
        }
        controls.append(group);
      }

      const opacity = offer("div", "lf-vr-opacity-control");
      const opacityLabel = offer("span", "lf-vr-inspector-label", "Candidate opacity");
      const slider = offer("wa-slider", "lf-vr-opacity");
      slider.size = "s";
      slider.label = "Candidate opacity";
      slider.valueFormatter = (value) => `${value}%`;
      slider.min = 0;
      slider.max = 100;
      slider.name = "candidate-opacity";
      slider.step = 5;
      slider.value = this.#opacity;
      slider.setAttribute("aria-label", "Candidate opacity");
      slider.addEventListener("input", () => this.#setOpacity(Number(slider.value)));
      const output = offer("output", "lf-vr-opacity-value", `${this.#opacity}%`);
      opacity.append(opacityLabel, slider, output);
      controls.append(opacity);
      return inspector;
    }

    #setScope(scope) {
      if (!(scope in SCOPE) || scope === this.#scope) return;
      if (
        scope === "focus" &&
        (!FOCUS_CROP_SUPPORTED || !this.#caseEntries.get(this.#selected)?.record.focus)
      )
        return;
      this.#scope = scope;
      this.#paintInspector();
      notice(`${SCOPE[scope]} evidence`);
    }

    #setMode(mode) {
      if (!(mode in INSPECTION) || mode === this.#mode) return;
      this.#mode = mode;
      this.#paintInspector();
      notice(`${INSPECTION[mode]} view`);
    }

    #setScale(scale) {
      if (!(scale in SCALE) || scale === this.#scale) return;
      this.#scale = scale;
      this.#paintInspector();
      notice(`${SCALE[scale]} evidence`);
    }

    #setOpacity(opacity) {
      if (!Number.isFinite(opacity)) return;
      this.#opacity = Math.max(0, Math.min(100, opacity));
      this.#paintInspector();
    }

    // A shot offers its own flip controls only in Flip.
    #paintShotControls(shot) {
      keeps(shot, "data-lf-shot-controls", this.#mode === "flip" ? null : "off");
    }

    #paintInspector() {
      if (!this.#inspector) return;
      keeps(this, "data-inspection-mode", this.#mode);
      keeps(this, "data-inspection-scale", this.#scale);
      const focus = this.#caseEntries.get(this.#selected)?.record?.focus;
      const focusAvailable = Boolean(focus && FOCUS_CROP_SUPPORTED);
      const scope = focusAvailable ? this.#scope : "full";
      keeps(this, "data-inspection-scope", scope);
      this.style.setProperty("--lf-vr-opacity", String(this.#opacity / 100));
      const scopeGroup = this.#inspector.querySelector(".lf-vr-scope-group");
      keepsHidden(scopeGroup, !focusAvailable);
      scopeGroup.value = scope;
      this.#inspector.querySelector(".lf-vr-mode-group").value = this.#mode;
      this.#inspector.querySelector(".lf-vr-scale-group").value = this.#scale;
      const opacity = this.#inspector.querySelector(".lf-vr-opacity-control");
      const slider = opacity.querySelector(".lf-vr-opacity");
      const active = this.#mode === "overlay";
      keeps(opacity, "data-active", active);
      slider.toggleAttribute("disabled", !active);
      slider.value = this.#opacity;
      const readout = opacity.querySelector(".lf-vr-opacity-value");
      const percent = `${this.#opacity}%`;
      relabel(readout, percent, { says: false });
      for (const shot of this.querySelectorAll("lf-shot")) {
        this.#paintShotControls(shot);
        for (const frame of shot.querySelectorAll(".lf-shotframe")) {
          const oldLabel = frame.querySelector(":scope > .lf-vr-frame-label");
          if (this.#mode !== "compare") {
            oldLabel?.remove();
            continue;
          }
          if (oldLabel) continue;
          const label = make("span", "lf-vr-frame-label lf-ui", null, false);
          label.dataset.label =
            frame.dataset.lfState === "before" ? "Base" : "Candidate";
          label.setAttribute("aria-hidden", "true");
          frame.prepend(label);
        }
      }
      // The selected case already declares its focus geometry. Allocate it in
      // this paint, before an undecoded shot can draw the wrong comparison shape.
      this.#paintEvidenceLayout();
      layoutChanged(this);
      paintKeys();
    }

    #scheduleEvidenceLayout() {
      if (this.#layoutFrame !== null) return;
      this.#layoutFrame = nextRender(() => {
        this.#layoutFrame = null;
        this.#paintEvidenceLayout();
      });
    }

    #paintEvidenceLayout() {
      const entry = this.#caseEntries.get(this.#selected);
      const shot = entry?.shotHost.querySelector("lf-shot");
      const frames = shot ? [...shot.querySelectorAll(".lf-shotframe")] : [];
      if (!entry?.record || frames.length !== 2 || !entry.shotHost.clientWidth) return;

      const { capture } = entry.record;
      const ratio = capture.deviceScaleFactor;
      const fallbackHeight = capture.viewport.height;
      const images = frames.map((frame) => frame.querySelector("img"));
      const heights = images.map((image) => {
        if (!image.complete) {
          image.addEventListener("load", this.#onGeometryChange, { once: true });
          image.addEventListener("error", this.#onGeometryChange, { once: true });
        }
        return image.naturalHeight ? image.naturalHeight / ratio : fallbackHeight;
      });
      const widths = images.map((image) =>
        image.naturalWidth ? image.naturalWidth / ratio : capture.viewport.width,
      );
      const focus = entry.record.focus;
      const decoded = images.every(
        (image) => image.naturalWidth && image.naturalHeight,
      );
      if (focus && !decoded && images.every((image) => image.complete)) {
        failSoft(
          entry.shotHost,
          new Error(`case '${entry.record.id}' focus needs two decoded images`),
        );
        return;
      }
      if (
        focus &&
        decoded &&
        images.some(
          (image) =>
            focus.x + focus.width > image.naturalWidth / ratio ||
            focus.y + focus.height > image.naturalHeight / ratio,
        )
      ) {
        failSoft(
          entry.shotHost,
          new Error(
            `case '${entry.record.id}' focus ${focus.x},${focus.y} ${focus.width}×${focus.height} ` +
              "CSS px falls outside its captured images",
          ),
        );
        return;
      }
      const activeFocus =
        focus && FOCUS_CROP_SUPPORTED && this.#scope === "focus" ? focus : null;
      // Focus coordinates name captured CSS pixels, so the decoded capture and the
      // rendered source must share one width authority. The recorded viewport remains
      // provenance; using it here could silently shift a valid focus when they differ.
      const sourceWidth = widths[0];
      const width = activeFocus?.width ?? sourceWidth;
      const visibleHeights = activeFocus
        ? [activeFocus.height, activeFocus.height]
        : heights;
      // The height a reader sees the pair in at once. Where the evidence pane scrolls on
      // its own, as in a workspace that fills the window, it is the pane body's, from the
      // stage's top down, and Fit contains the pair in it. Elsewhere the page scrolls
      // the review, and it is the window the chrome leaves.
      const bounded = readingPosture(this.#evidenceHost) === "bounded";
      const stageWidth = entry.shotHost.clientWidth;
      const stageHeight = bounded
        ? this.#casesBody.clientHeight -
          (entry.shotHost.getBoundingClientRect().top -
            this.#casesBody.getBoundingClientRect().top +
            this.#casesBody.scrollTop) -
          (entry.shotHost.offsetHeight - entry.shotHost.clientHeight)
        : shownWindow({ viewport: "layout" }).height;

      const stageStyle = getComputedStyle(entry.shotHost);
      const gap = parseFloat(stageStyle.getPropertyValue("--lf-vr-gap"));
      const frameBorder =
        2 * parseFloat(stageStyle.getPropertyValue("--lf-vr-frame-border"));
      const labelHeight = parseFloat(
        stageStyle.getPropertyValue("--lf-vr-label-height"),
      );
      const sideWidthScale = (stageWidth - gap - 2 * frameBorder) / (2 * width);
      const sideContainScale = Math.min(
        sideWidthScale,
        (stageHeight - labelHeight - frameBorder) / Math.max(...visibleHeights),
      );
      const stackContainScale = Math.min(
        (stageWidth - frameBorder) / width,
        (stageHeight - 2 * (labelHeight + frameBorder)) /
          (visibleHeights[0] + visibleHeights[1]),
      );
      // Geometry chooses the comparison, not another preference for the user to
      // manage. Wide captures stack so their scan lines remain readable as the reader
      // scrolls; other pairs take the arrangement with the larger common scale.
      const wideCapture = width / Math.max(...visibleHeights) >= 1.5;
      const compareLayout =
        wideCapture || stackContainScale >= sideContainScale ? "stack" : "side";
      const widthScale =
        this.#mode === "compare"
          ? compareLayout === "stack"
            ? (stageWidth - frameBorder) / width
            : sideWidthScale
          : (stageWidth - frameBorder) / width;
      // Flip shows one frame under lf-shot's rail of controls.
      const rail =
        this.#mode === "flip"
          ? (shot.querySelector(".lf-shotrail")?.offsetHeight ?? 0)
          : 0;
      const containScale =
        this.#mode === "compare"
          ? compareLayout === "stack"
            ? stackContainScale
            : sideContainScale
          : Math.min(
              widthScale,
              (stageHeight - rail - frameBorder) / Math.max(...visibleHeights),
            );
      // Where the evidence pane scrolls on its own, Fit shrinks the pair to fit the
      // pane, so the reader sees all of it at once, unless that takes it below
      // `READABLE_SCALE`: a tall mobile capture shrunk to fit whole was unreadably small.
      // Such a pair takes the width instead and its pane scrolls, as the page does where
      // the page scrolls the review.
      const fitScale =
        bounded && containScale >= READABLE_SCALE ? containScale : widthScale;
      const scale = this.#scale === "actual" ? 1 : Math.min(1, fitScale);
      keeps(this, "data-compare-layout", compareLayout);
      keeps(entry.shotHost, "data-focus-authored", Boolean(focus));
      keeps(entry.shotHost, "data-focus-active", Boolean(activeFocus));
      if (focus) {
        entry.shotHost.style.setProperty("--lf-vr-focus-x", `${focus.x * scale}px`);
        entry.shotHost.style.setProperty("--lf-vr-focus-y", `${focus.y * scale}px`);
        entry.shotHost.style.setProperty(
          "--lf-vr-focus-width",
          `${focus.width * scale}px`,
        );
        entry.shotHost.style.setProperty(
          "--lf-vr-focus-height",
          `${focus.height * scale}px`,
        );
        frames.forEach((frame, index) => {
          frame.style.setProperty(
            "--lf-vr-focus-view",
            `inset(${focus.y * ratio}px ${(widths[index] - focus.x - focus.width) * ratio}px ` +
              `${(heights[index] - focus.y - focus.height) * ratio}px ${focus.x * ratio}px)`,
          );
        });
      }
      const beforeLabel = frames[0].querySelector(".lf-vr-frame-label");
      keeps(
        beforeLabel,
        "data-label",
        compareLayout === "stack" ? "Base · Candidate below" : "Base",
      );
      // The frames take their width from here a pass after the host took its own, so
      // the host keeps its box while what it holds resizes: say so, or a reading made
      // of the host at its resize (reach.js) keeps the frames' old width.
      const frameWidth = `${Math.max(1, width * scale)}px`;
      if (entry.shotHost.style.getPropertyValue("--lf-vr-frame-width") !== frameWidth) {
        entry.shotHost.style.setProperty("--lf-vr-frame-width", frameWidth);
        layoutChanged(this);
      }
    }

    #registerCommands() {
      if (this.#commands) return;
      this.#commands = commands(this, "In a visual review", [
        {
          id: "visual.next-case",
          control: () => this.#queueHost.querySelector(".lf-vr-next"),
          keys: ["ArrowDown"],
          title: "next case",
          when: () => this.#caseEntries.size > 1,
          run: () => this.#step(1),
        },
        {
          id: "visual.next-remaining",
          control: () =>
            this.#caseEntries
              .get(this.#selected)
              ?.article.querySelector(".lf-vr-next-remaining"),
          keys: [],
          title: "next unreviewed case",
          when: () => this.#remaining().some(({ id }) => id !== this.#selected),
          run: () => this.#nextRemaining(),
        },
        {
          id: "visual.previous-case",
          control: () => this.#queueHost.querySelector(".lf-vr-previous"),
          keys: ["ArrowUp"],
          title: "previous case",
          when: () => this.#caseEntries.size > 1,
          run: () => this.#step(-1),
        },
      ]);
    }

    #show(snapshot) {
      const restoreFocus = holdFocus(this);
      const resume = this.#controller.defer();
      try {
        const places = placeKeeper(scrollerFor(this), {
          items: `#${CSS.escape(this.id)} :is(.lf-vr-case-title, .lf-vr-disposition, .lf-vr-next-remaining, .lf-vr-details-summary, .lf-vr-action, .lf-vr-result)`,
          identity: (node) =>
            `${node.closest(".lf-vr-case").dataset.lfDatum}/${node.dataset.disposition ?? [...node.classList].find((name) => name.startsWith("lf-vr-"))}`,
        });
        places.around(() => {
          this.#snapshot = snapshot;
          this.#run = snapshot?.value ?? null;
          // Drawn from its data, which lifts the height the page reserved (x-height),
          // and held at that height again while the data is absent.
          this.classList.toggle("lf-rendered", this.#run !== null);
          if (!this.#run) {
            this.#renderMissing(snapshot);
            return;
          }
          keepsHidden(this.#inspector, false);
          const ids = this.#run.cases.map(({ id }) => id);
          if (new Set(ids).size !== ids.length)
            throw new Error("visual run repeats a case id");
          setText(this.#title, this.#run.title);
          this.#reconcileCases(this.#run.cases);
          this.#paintNavigation();
          const fallback = this.#run.cases.find(
            ({ classification }) => classification !== "clean",
          );
          if (!this.#caseEntries.has(this.#selected))
            this.#selected = fallback?.id ?? ids[0];
          this.#select(this.#selected, false, null);
          this.#paintInspector();
        });
        restoreFocus?.(() => {
          if (!this.#selected) return false;
          this.#landOnEvidence("return");
          return true;
        });
      } catch (error) {
        failSoft(this, error);
      } finally {
        resume();
      }
    }

    #renderMissing(snapshot) {
      setText(this.#title, "Waiting for a visual run");
      keepsHidden(this.#inspector, true);
      if (this.#evidenceHost.lastChild !== this.#inspector)
        this.#evidenceHost.append(this.#inspector);
      this.#queue.replaceChildren();
      for (const { shotHost, article } of this.#caseEntries.values()) {
        this.#sizes?.unobserve(shotHost);
        this.#sizes?.unobserve(article.querySelector(".lf-vr-case-head"));
        this.#sizes?.unobserve(article.querySelector(".lf-vr-toolbar-slot"));
      }
      this.#caseEntries.clear();
      this.#selected = null;
      this.#paintNavigation();
      const empty =
        this.#casesBody.querySelector(":scope > .lf-vr-empty") ??
        make("p", "lf-vr-empty", "Waiting for visual-run data.");
      setChildren(this.#casesBody, [empty]);
      projectData(
        this,
        [{ key: "unavailable", node: empty, label: "Visual run unavailable" }],
        { snapshot },
      );
      setText(this.#progress, "No cases reviewed");
      layoutChanged(this);
      paintKeys();
    }

    #reconcileCases(cases) {
      const wanted = new Set(cases.map(({ id }) => id));
      for (const [id, entry] of this.#caseEntries) {
        if (wanted.has(id)) continue;
        this.#sizes?.unobserve(entry.shotHost);
        this.#sizes?.unobserve(entry.article.querySelector(".lf-vr-case-head"));
        this.#sizes?.unobserve(entry.article.querySelector(".lf-vr-toolbar-slot"));
        this.#caseEntries.delete(id);
      }
      const options = [];
      const articles = [];
      for (const [index, record] of cases.entries()) {
        let entry = this.#caseEntries.get(record.id);
        if (!entry) {
          entry = this.#createCase(record.id);
          this.#caseEntries.set(record.id, entry);
        }
        this.#updateCase(entry, record, index, cases.length);
        options.push(entry.option);
        articles.push(entry.article);
      }
      setChildren(this.#queue, options);
      setChildren(this.#casesBody, articles);
      for (const entry of this.#caseEntries.values()) this.#syncCaptureWidth(entry);
      projectData(
        this,
        cases.map((record, index) => ({
          node: this.#caseEntries.get(record.id).article,
          key: record.id,
          identity: record.id,
          label: `Case ${index + 1}: ${record.title}`,
          origin: { ...this.#snapshot.origin, path: ["cases", index] },
        })),
        { snapshot: this.#snapshot },
      );
    }

    #createCase(id) {
      const option = offer("wa-option", "");
      option.setAttribute("value", id);

      const article = make("article", "lf-vr-case");
      const heading = make("header", "lf-vr-case-head");
      const headingText = make("div", "lf-vr-case-heading");
      const position = make("p", "lf-vr-case-position");
      const title = make("h3", "lf-vr-case-title");
      headingText.append(position, title);
      const review = make("div", "lf-vr-review");
      review.setAttribute("role", "group");
      review.setAttribute("aria-label", "Case review");
      const dispositions = make("div", "lf-vr-dispositions");
      for (const [value, text] of Object.entries(DISPOSITION)) {
        const button = offer("button", `lf-btn lf-vr-disposition lf-vr-${value}`, text);
        button.type = "button";
        button.dataset.disposition = value;
        button.addEventListener("click", () => this.#review(id, value));
        dispositions.append(button);
      }
      const remaining = offer(
        "button",
        "lf-btn lf-vr-next-remaining",
        "Next unreviewed",
      );
      remaining.type = "button";
      const status = make("p", "lf-vr-review-status");
      review.append(dispositions, remaining, status);
      heading.append(headingText);
      const claim = make("dl", "lf-vr-claim");
      for (const [termClass, valueClass, term] of [
        ["lf-vr-action-term", "lf-vr-action", "Action"],
        ["lf-vr-result-term", "lf-vr-result", "Observed result"],
      ]) {
        const dt = make("dt", termClass, term);
        const dd = make("dd", valueClass);
        claim.append(dt, dd);
      }
      const links = make("div", "lf-vr-links");
      const base = link("lf-btn lf-vr-base-link", "Open base");
      const candidate = link("lf-btn lf-vr-candidate-link", "Open candidate");
      const trace = link("lf-btn lf-vr-trace-link", "Open trace");
      links.append(base, candidate, trace);
      const details = make("details", "lf-vr-details");
      const detailsSummary = offer(
        "summary",
        "lf-vr-details-summary",
        "Capture details",
      );
      const provenance = make("dl", "lf-vr-provenance");
      const revisions = make("div", "lf-vr-revisions");
      for (const [group, fields] of [
        [
          provenance,
          [
            ["Path", "lf-vr-path", "code"],
            ["Browser", "lf-vr-browser", "span"],
            ["Viewport", "lf-vr-viewport", "span"],
            ["Focus area", "lf-vr-focus", "span"],
            ["Appearance", "lf-vr-appearance", "span"],
            ["Observed", "lf-vr-observed", "time"],
          ],
        ],
        [
          revisions,
          [
            ["Base revision", "lf-vr-base-revision", "code"],
            ["Candidate revision", "lf-vr-candidate-revision", "code"],
          ],
        ],
      ]) {
        for (const [name, valueClass, valueTag] of fields) {
          const detail = make("div", "lf-vr-detail");
          const value = make(valueTag, valueClass);
          const definition = make("dd", "lf-vr-detail-value");
          definition.append(value);
          detail.append(make("dt", "lf-vr-detail-term", name), definition);
          group.append(detail);
        }
      }
      const analysis = make("p", "lf-vr-analysis");
      provenance.append(analysis, revisions);
      details.append(detailsSummary, provenance);
      const support = make("footer", "lf-vr-support");
      support.append(links, details);
      const toolbar = make("div", "lf-vr-toolbar-slot", null, false);
      const shotHost = make("div", "lf-vr-shot-host");
      this.#sizes?.observe(shotHost);
      this.#sizes?.observe(heading);
      this.#sizes?.observe(toolbar);
      const threadOutlet = make("section", "lf-vr-thread-outlet lf-ui");
      threadOutlet.dataset.lfGen = "1";
      threadOutlet.setAttribute("aria-label", "Threads on this visual case");
      article.append(heading, toolbar, shotHost, claim, review, support, threadOutlet);
      const entry = {
        article,
        option,
        shotHost,
        record: null,
        index: 0,
        total: 0,
        // The shown lf-shot's `difference`, once it has read its pair.
        difference: undefined,
      };
      return entry;
    }

    #updateCase(entry, record, index, total) {
      keeps(entry.article, "data-classification", record.classification);
      keeps(entry.article, "aria-label", `Visual review case ${index + 1} of ${total}`);
      entry.record = record;
      entry.index = index;
      entry.total = total;
      this.#paintOption(entry);
      this.#paintPosition(entry);
      setText(entry.article.querySelector(".lf-vr-case-title"), record.title);
      setText(entry.article.querySelector(".lf-vr-path"), record.path);
      setText(entry.article.querySelector(".lf-vr-action"), record.action);
      setText(entry.article.querySelector(".lf-vr-result"), record.result);
      setText(
        entry.article.querySelector(".lf-vr-browser"),
        `${record.capture.browser} ${record.capture.browserVersion}`,
      );
      setText(
        entry.article.querySelector(".lf-vr-viewport"),
        `${record.capture.viewport.width} × ${record.capture.viewport.height} · ${record.capture.deviceScaleFactor}×`,
      );
      const focus = entry.article.querySelector(".lf-vr-focus");
      keepsHidden(focus.closest(".lf-vr-detail"), !record.focus);
      if (record.focus)
        setText(
          focus,
          `${record.focus.x}, ${record.focus.y} · ${record.focus.width} × ${record.focus.height} CSS px`,
        );
      setText(
        entry.article.querySelector(".lf-vr-appearance"),
        `${record.capture.colorScheme} · ${record.capture.locale} · ${record.capture.timezone}`,
      );
      const observed = entry.article.querySelector(".lf-vr-observed");
      setText(observed, record.capture.observedAt);
      keeps(observed, "datetime", record.capture.observedAt);
      setText(
        entry.article.querySelector(".lf-vr-base-revision"),
        this.#run.base.revision,
      );
      setText(
        entry.article.querySelector(".lf-vr-candidate-revision"),
        this.#run.candidate.revision,
      );
      const base = entry.article.querySelector(".lf-vr-base-link");
      const candidate = entry.article.querySelector(".lf-vr-candidate-link");
      for (const [control, target] of [
        [base, this.#run.base],
        [candidate, this.#run.candidate],
      ]) {
        keepsHidden(control, !target.url);
        keeps(control, "href", target.url ? previewUrl(target, record.path) : null);
      }
      const trace = entry.article.querySelector(".lf-vr-trace-link");
      keepsHidden(trace, !record.traceUrl);
      if (record.traceUrl) keeps(trace, "href", record.traceUrl);

      const current = entry.shotHost.querySelector("lf-shot");
      const alt = `${record.title}. ${record.result}`;
      const before = scopedMediaUrl(record.before);
      const after = scopedMediaUrl(record.after);
      if (
        !current ||
        current.getAttribute("before") !== before ||
        current.getAttribute("after") !== after
      ) {
        const shot = document.createElement("lf-shot");
        // This generated presentation region has no authored semantic descriptor.
        // Its nearest authored owner joins every child's distinct preparation to
        // Leaf's page barrier; several cases may register during this same paint.
        shot._lfPresentGenerated = (promise) => this.#controller.present(promise);
        shot.id = `lf-${this.id}-${record.id}-comparison`;
        shot.setAttribute("before", before);
        shot.setAttribute("after", after);
        shot.setAttribute("alt", alt);
        shot.toggleAttribute("outlines", true);
        // Before the shot connects, so it declares its keys once, for this mode.
        this.#paintShotControls(shot);
        entry.shotHost.replaceChildren(shot);
        entry.difference = undefined;
        this.#paintPosition(entry);
        // A refused or failed comparison is lf-shot's to report, in its own box.
        shot.difference.then(
          (reading) => {
            if (entry.shotHost.querySelector("lf-shot") !== shot) return;
            entry.difference = reading;
            this.#paintPosition(entry);
          },
          () => {},
        );
      } else keeps(current, "alt", alt);
    }

    // lf-shot's rail stays hidden outside Flip, and a focus crop hides the outlines,
    // so Capture details states the complete reading in every view, including
    // changes outside a focus. The heading contains only captured facts: computing
    // differences happens after presentation and must not move evidence or controls.
    #paintPosition(entry) {
      const { record, index, total, difference } = entry;
      const parts = [
        `Case ${index + 1} of ${total}`,
        CLASSIFICATION[record.classification],
      ];
      if (difference) {
        const ratio = record.capture.deviceScaleFactor;
        const focus = record.focus;
        const outside = focus
          ? countAreas(
              difference.regions.filter(
                (region) =>
                  region.x >= (focus.x + focus.width) * ratio ||
                  region.x + region.width <= focus.x * ratio ||
                  region.y >= (focus.y + focus.height) * ratio ||
                  region.y + region.height <= focus.y * ratio,
              ),
            )
          : { changed: 0, moved: 0 };
        const left = outside.changed + outside.moved;
        parts.push(
          describeDifference(difference) + (left ? ` (${left} outside the focus)` : ""),
        );
      }
      setText(
        entry.article.querySelector(".lf-vr-case-position"),
        `${parts.slice(0, 2).join(" · ")}${record.focus ? " · Focused capture" : ""}`,
      );
      setText(entry.article.querySelector(".lf-vr-analysis"), parts.join(" · "));
    }

    #syncCaptureWidth(entry) {
      const shot = entry.shotHost.querySelector("lf-shot");
      const images = shot ? [...shot.querySelectorAll("img")] : [];
      if (images.length !== 2) return;
      const ratio = entry.record.capture.deviceScaleFactor;
      const paint = () => {
        // A source update replaces the lf-shot. A load event from the detached pair
        // must not project its dimensions through the new record.
        if (entry.shotHost.querySelector("lf-shot") !== shot) return false;
        const currentImages = [...shot.querySelectorAll("img")];
        const widths = currentImages.map((image) => image.naturalWidth / ratio);
        if (widths.some((width) => !width)) return false;
        entry.shotHost.style.setProperty(
          "--lf-vr-capture-width",
          `${Math.max(1, widths[0])}px`,
        );
        return true;
      };
      if (paint()) return;
      for (const image of images)
        if (!image.complete) image.addEventListener("load", paint, { once: true });
    }

    #select(id, land = false, restoreFocus = holdFocus(this)) {
      if (!this.#caseEntries.has(id)) return;
      // Changing case from a verdict is a route to its counterpart, not a passive
      // return to the old control. The focus owner reveals that destination; a
      // source refresh supplies its own hold and passes null here.
      const disposition = restoreFocus
        ? focused()?.closest?.(".lf-vr-disposition")?.dataset.disposition
        : null;
      if (id !== this.#selected) this.#scope = "focus";
      this.#selected = id;
      this.#queue.value = id;
      for (const [caseId, entry] of this.#caseEntries) {
        const selected = caseId === id;
        keepsHidden(entry.article, !selected);
      }
      const selected = this.#caseEntries.get(id);
      const toolbar = selected.article.querySelector(".lf-vr-toolbar-slot");
      if (this.#inspector.parentElement !== toolbar) toolbar.append(this.#inspector);
      this.#paintInspector();
      this.#threadSurface?.update();
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
      paintKeys();
      if (land) this.#landOnEvidence("move");
      else if (disposition)
        focusDestination(
          selected.article.querySelector(
            `.lf-vr-disposition[data-disposition="${disposition}"]`,
          ),
          "move",
          { scroll: true },
        );
      else
        restoreFocus?.(() => {
          this.#landOnEvidence("move");
          return true;
        });
    }

    #step(delta) {
      if (!this.#run?.cases.length) return;
      const ids = this.#run.cases.map(({ id }) => id);
      const current = Math.max(0, ids.indexOf(this.#selected));
      const next = ids[(current + delta + ids.length) % ids.length];
      this.#select(next);
    }

    #disposition(id) {
      return this.#reviewUnits[id]?.detail.disposition ?? null;
    }

    #remaining() {
      return this.#run?.cases.filter(({ id }) => !this.#disposition(id)) ?? [];
    }

    #nextRemaining() {
      const remaining = this.#remaining().filter(({ id }) => id !== this.#selected);
      if (!remaining.length) return;
      const current = this.#run.cases.findIndex(({ id }) => id === this.#selected);
      const next =
        remaining.find(
          ({ id }) => this.#run.cases.findIndex((record) => record.id === id) > current,
        ) ?? remaining[0];
      this.#select(next.id, true);
    }

    #landOnEvidence(cause) {
      const heading = this.#caseEntries
        .get(this.#selected)
        .article.querySelector(".lf-vr-case-title");
      focusDestination(heading, cause);
      const header = heading.closest(".lf-vr-case-head");
      scrollIntoReadingBand(header, header, "start", scrollBehavior());
    }

    #paintNavigation() {
      const count = this.#caseEntries.size;
      this.#queue.toggleAttribute("disabled", count === 0);
      paintKeys();
    }

    async #review(id, disposition) {
      if (!this.#controller.read().actions.review.available) return;
      const accepted = await this.#controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { case: id, disposition },
      })?.delivery;
      if (accepted) notice(`${DISPOSITION[disposition]} — sent`);
    }

    #setDisposition(id, disposition) {
      const entry = this.#caseEntries.get(id);
      if (!entry) return;
      keeps(entry.article, "data-disposition", disposition ?? "");
      for (const button of entry.article.querySelectorAll(".lf-vr-disposition"))
        keeps(button, "aria-pressed", button.dataset.disposition === disposition);
      this.#paintOption(entry);
      this.#paintProgress();
    }

    #paintOption(entry) {
      if (!entry.record) return;
      const disposition = this.#disposition(entry.record.id);
      const status = disposition
        ? DISPOSITION[disposition]
        : CLASSIFICATION[entry.record.classification];
      relabel(
        entry.option,
        `${entry.index + 1} of ${entry.total} · ${entry.record.title} · ${status}`,
        { says: false },
      );
    }

    #paintAvailability() {
      const available = this.#controller.read().actions.review?.available ?? false;
      for (const button of this.querySelectorAll(".lf-vr-disposition"))
        button.toggleAttribute("disabled", !available);
      paintKeys();
    }

    #paintProgress() {
      const total = this.#caseEntries.size;
      const reviewed = total - this.#remaining().length;
      setText(
        this.#progress,
        total ? `${reviewed} of ${total} cases reviewed` : "No cases reviewed",
      );
    }

    #threadOutlet({ anchor, placement }) {
      const entry = this.#caseEntries.get(anchor.datum);
      if (
        !entry ||
        anchor.datum !== this.#selected ||
        placement.datumElement !== entry.article
      )
        return null;
      return entry.article.querySelector(".lf-vr-thread-outlet");
    }

    renderState(state) {
      const units = (this.#reviewUnits = state?.review?.units ?? {});
      for (const id of this.#caseEntries.keys())
        this.#setDisposition(id, units[id]?.detail?.disposition ?? null);
      const remaining = this.#remaining().length;
      for (const [id, { article }] of this.#caseEntries) {
        const disposition = this.#disposition(id);
        setText(
          article.querySelector(".lf-vr-review-status"),
          remaining === 0
            ? "All cases reviewed · revisit any case above"
            : remaining === 1 && !disposition
              ? "Current case is the last unreviewed"
              : `${disposition ? DISPOSITION[disposition] : "Not reviewed"} · ${remaining} unreviewed`,
        );
      }
      this.#paintAvailability();
      return true;
    }
  },
);
