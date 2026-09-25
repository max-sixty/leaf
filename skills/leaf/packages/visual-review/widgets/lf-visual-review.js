/* A visual run is external evidence: one source supplies its cases, while Leaf's event
 * log owns case dispositions and threads. The module keeps browsing and inspection
 * choices local, projects each case with source provenance, and reshapes the existing
 * aligned lf-shot comparison without introducing another evidence model. */
import "/widgets/lf-shot.js";
import "../vendor/webawesome.esm.js";

import {
  cancelRender,
  commands,
  compoundReadingRegionId,
  consumeThreads,
  failSoft,
  layoutChanged,
  nextRender,
  notice,
  offer,
  once,
  paintKeys,
  PRESS,
  projectData,
  registerReadingRegion,
  relabel,
  scopedMediaUrl,
  sizeObserver,
  watchData,
  widgetController,
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
  if (element.textContent !== text) relabel(element, text, { says: true });
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

function orderChildren(parent, children) {
  let cursor = parent.firstElementChild;
  for (const child of children) {
    if (child === cursor) cursor = cursor.nextElementSibling;
    else parent.insertBefore(child, cursor);
  }
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
    #onResize = () => this.#scheduleEvidenceLayout();
    #opacity = 50;
    #progress = null;
    #queue = null;
    #queueHost = null;
    #run = null;
    #scale = "fit";
    #scope = "focus";
    #selected = null;
    #snapshot = null;
    #sizes = null;
    #threadSurface = null;
    #title = null;

    connectedCallback() {
      if (once(this)) this.#buildLayout();
      this.#stopEvidence ??= registerReadingRegion({
        id: compoundReadingRegionId(this, "evidence"),
        host: this.#evidenceHost,
        body: this.#casesBody,
      });
      for (const [id, entry] of this.#caseEntries) this.#registerCaseRegion(id, entry);
      this.#sizes = sizeObserver(() => this.#scheduleEvidenceLayout());
      this.#sizes.observe(this);
      for (const stage of this.querySelectorAll(".lf-vr-shot-host"))
        this.#sizes.observe(stage);
      window.addEventListener("resize", this.#onResize);
      this.#threadSurface ??= consumeThreads(this, (collection, surfaces) => {
        for (const thread of collection.threads) {
          if (thread.anchor?.section !== this.id || !thread.anchor.datum) continue;
          const target = surfaces.target(thread.key);
          const outlet = target && this.#threadOutlet(target);
          if (outlet) surfaces.place(thread.key, outlet);
        }
        const outlet = surfaces.composition && this.#threadOutlet(surfaces.composition);
        if (outlet) surfaces.placeComposition(outlet);
      });
      this.stopActions ??= this.#controller.subscribe(() => this.#paintAvailability());
      this.stopWatching ??= watchData(this, "run", (snapshot) => this.#show(snapshot));
    }

    disconnectedCallback() {
      this.stopActions?.();
      this.stopActions = null;
      this.stopWatching?.();
      this.stopWatching = null;
      this.#threadSurface?.unregister();
      this.#threadSurface = null;
      for (const entry of this.#caseEntries.values()) {
        entry.stopReading?.();
        entry.stopReading = null;
      }
      this.#sizes?.disconnect();
      this.#sizes = null;
      window.removeEventListener("resize", this.#onResize);
      if (this.#layoutFrame !== null) cancelRender(this.#layoutFrame);
      this.#layoutFrame = null;
      this.#stopEvidence?.();
      this.#stopEvidence = null;
    }

    // The review composes the layer's pane grammar rather than choosing a posture: a
    // heading, then one evidence pane whose header is the case navigation and whose
    // body holds the cases. The theme decides whether that body scrolls, from the
    // workspace the review stands in, so the same boxes fill a bounded root workspace
    // and flow in a document.
    #buildLayout() {
      const header = make("header", "lf-vr-head");
      this.#title = make("h2", "lf-vr-title", "Waiting for a visual run");
      this.#progress = make("p", "lf-vr-progress", "No cases reviewed");
      header.append(this.#title, this.#progress);

      this.#queueHost = offer("nav", "lf-vr-queue-region");
      this.#queueHost.setAttribute("aria-label", "Visual review cases");
      const previous = offer("button", "lf-btn lf-vr-previous", "Previous");
      previous.type = "button";
      previous.addEventListener("click", () => this.#step(-1));
      this.#queue = offer("wa-select", "lf-vr-case-select");
      this.#queue.name = "visual-case";
      this.#queue.size = "s";
      this.#queue.label = "Selected visual case";
      this.#queue.setAttribute("aria-label", "Selected visual case");
      this.#queue.addEventListener("change", () => this.#select(this.#queue.value));
      const next = offer("button", "lf-btn lf-vr-next", "Next");
      next.type = "button";
      next.addEventListener("click", () => this.#step(1));
      this.#queueHost.append(previous, this.#queue, next);
      const queue = make("header", "lf-vr-queue");
      queue.append(this.#queueHost);

      this.#evidenceHost = make("section", "lf-vr-evidence-region");
      this.#evidenceHost.dataset.lfReadingRole = "pane";
      this.#evidenceHost.setAttribute("aria-label", "Selected visual evidence");
      this.#inspector = this.#buildInspector();
      this.#casesBody = make("div", "lf-vr-cases");
      this.#evidenceHost.append(queue, this.#casesBody);

      this.append(header, this.#evidenceHost);
      this.#registerCommands();
      this.#paintInspector();
    }

    #buildInspector() {
      const inspector = offer("div", "lf-vr-inspector");
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
              does: `${text} visual evidence`,
              line: text.toLowerCase(),
              run: () => radio.click(),
            },
          ]);
          group.append(radio);
        }
        inspector.append(group);
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
      inspector.append(opacity);
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

    #paintInspector() {
      if (!this.#inspector) return;
      this.dataset.inspectionMode = this.#mode;
      this.dataset.inspectionScale = this.#scale;
      const focus = this.#caseEntries.get(this.#selected)?.record?.focus;
      const focusAvailable = Boolean(focus && FOCUS_CROP_SUPPORTED);
      const scope = focusAvailable ? this.#scope : "full";
      this.dataset.inspectionScope = scope;
      this.style.setProperty("--lf-vr-opacity", String(this.#opacity / 100));
      const scopeGroup = this.#inspector.querySelector(".lf-vr-scope-group");
      scopeGroup.hidden = !focusAvailable;
      scopeGroup.value = scope;
      this.#inspector.querySelector(".lf-vr-mode-group").value = this.#mode;
      this.#inspector.querySelector(".lf-vr-scale-group").value = this.#scale;
      const opacity = this.#inspector.querySelector(".lf-vr-opacity-control");
      const slider = opacity.querySelector(".lf-vr-opacity");
      const active = this.#mode === "overlay";
      opacity.dataset.active = String(active);
      slider.disabled = !active;
      slider.value = this.#opacity;
      const readout = opacity.querySelector(".lf-vr-opacity-value");
      const percent = `${this.#opacity}%`;
      if (readout.textContent !== percent) relabel(readout, percent, { says: false });
      for (const shot of this.querySelectorAll("lf-shot")) {
        const flip = this.#mode === "flip";
        if (flip) shot.removeAttribute("data-lf-shot-controls");
        else shot.dataset.lfShotControls = "off";
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
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
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
        if (!image.complete)
          image.addEventListener("load", () => this.#scheduleEvidenceLayout(), {
            once: true,
          });
        return image.naturalHeight ? image.naturalHeight / ratio : fallbackHeight;
      });
      const widths = images.map((image) =>
        image.naturalWidth ? image.naturalWidth / ratio : capture.viewport.width,
      );
      const focus = entry.record.focus;
      if (
        focus &&
        images.some((image) => !image.naturalWidth || !image.naturalHeight)
      ) {
        if (images.every((image) => image.complete))
          failSoft(
            entry.shotHost,
            new Error(`case '${entry.record.id}' focus needs two decoded images`),
          );
        return;
      }
      if (
        focus &&
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
      // The theme sizes the stage: the height the pane leaves it where the pane's body
      // is bounded, and a height from the widget's own width in flow, so a paint-only
      // inspection control never resizes the evidence and moves the document.
      const stageWidth = entry.shotHost.clientWidth;
      const stageHeight = entry.shotHost.clientHeight;
      if (stageHeight <= 0) return;

      const gap = 8;
      const frameBorder = 2;
      const labelHeight = 24;
      const sideWidthScale = (stageWidth - gap - 2 * frameBorder) / (2 * width);
      const sideContainScale = Math.min(
        sideWidthScale,
        (stageHeight - labelHeight) / Math.max(...visibleHeights),
      );
      const stackContainScale = Math.min(
        (stageWidth - frameBorder) / width,
        (stageHeight - 2 * labelHeight - gap) / (visibleHeights[0] + visibleHeights[1]),
      );
      // Geometry chooses the comparison, not another preference for the user to
      // manage. Wide captures stack so their scan lines remain readable in the scrolling
      // stage; other pairs take the arrangement with the larger common scale.
      const wideCapture = width / Math.max(...visibleHeights) >= 1.5;
      const compareLayout =
        wideCapture || stackContainScale >= sideContainScale ? "stack" : "side";
      const fitScale =
        this.#mode === "compare"
          ? compareLayout === "stack"
            ? (stageWidth - frameBorder) / width
            : sideWidthScale
          : Math.min(
              (stageWidth - frameBorder) / width,
              stageHeight / Math.max(...visibleHeights),
            );
      // A comparison is a reading surface: fit the pair to its available width and let
      // the bounded stage scroll through its height. Containing both frames vertically
      // made tall mobile captures unreadably small even when both fit side by side.
      const scale = this.#scale === "actual" ? 1 : Math.min(1, fitScale);
      this.dataset.compareLayout = compareLayout;
      entry.shotHost.dataset.focusAuthored = String(Boolean(focus));
      entry.shotHost.dataset.focusActive = String(Boolean(activeFocus));
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
          const image = images[index];
          frame.style.setProperty(
            "--lf-vr-focus-view",
            `inset(${focus.y * ratio}px ${image.naturalWidth - (focus.x + focus.width) * ratio}px ` +
              `${image.naturalHeight - (focus.y + focus.height) * ratio}px ${focus.x * ratio}px)`,
          );
        });
      }
      const beforeLabel = frames[0].querySelector(".lf-vr-frame-label");
      if (beforeLabel)
        beforeLabel.dataset.label =
          compareLayout === "stack" ? "Base · Candidate below" : "Base";
      entry.shotHost.style.setProperty(
        "--lf-vr-frame-width",
        `${Math.max(1, width * scale)}px`,
      );
    }

    #registerCommands() {
      if (this.#commands) return;
      this.#commands = commands(this, "In a visual review", [
        {
          id: "visual.next-case",
          keys: ["ArrowDown"],
          does: "Show the next visual case",
          line: "next case",
          when: () => this.#caseEntries.size > 1,
          run: () => this.#step(1),
        },
        {
          id: "visual.previous-case",
          keys: ["ArrowUp"],
          does: "Show the previous visual case",
          line: "previous case",
          when: () => this.#caseEntries.size > 1,
          run: () => this.#step(-1),
        },
      ]);
    }

    #show(snapshot) {
      const resume = this.#controller.defer();
      try {
        this.#snapshot = snapshot;
        this.#run = snapshot?.value ?? null;
        if (!this.#run) {
          this.#renderMissing(snapshot);
          return;
        }
        this.#inspector.hidden = false;
        this.#casesBody.querySelector(":scope > .lf-vr-empty")?.remove();
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
        this.#select(this.#selected);
        this.#paintInspector();
      } catch (error) {
        failSoft(this, error);
      } finally {
        resume();
      }
    }

    #renderMissing(snapshot) {
      setText(this.#title, "Waiting for a visual run");
      this.#inspector.hidden = true;
      this.#evidenceHost.append(this.#inspector);
      this.#queue.replaceChildren();
      for (const { shotHost, stopReading } of this.#caseEntries.values()) {
        this.#sizes?.unobserve(shotHost);
        stopReading?.();
      }
      this.#caseEntries.clear();
      this.#selected = null;
      this.#paintNavigation();
      const empty = make("p", "lf-vr-empty", "Waiting for visual-run data.");
      this.#casesBody.replaceChildren(empty);
      projectData(
        this,
        [{ id: "unavailable", node: empty }],
        ({ id }) => id,
        ({ node }) => node,
        {
          nested: true,
          labelOf: () => "Visual run unavailable",
          snapshot,
        },
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
        entry.stopReading?.();
        entry.option.remove();
        entry.article.remove();
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
      orderChildren(this.#queue, options);
      orderChildren(this.#casesBody, articles);
      for (const entry of this.#caseEntries.values()) this.#syncCaptureWidth(entry);
      projectData(
        this,
        cases,
        ({ id }) => id,
        ({ id }) => this.#caseEntries.get(id).article,
        {
          nested: true,
          labelOf: (record, index) => `Case ${index + 1}: ${record.title}`,
          snapshot: this.#snapshot,
          originOf: (_, index) => ({
            ...this.#snapshot.origin,
            path: ["cases", index],
          }),
        },
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
      review.setAttribute("aria-label", "Case disposition");
      const dispositions = make("div", "lf-vr-dispositions");
      for (const [value, text] of Object.entries(DISPOSITION)) {
        const button = offer("button", `lf-btn lf-vr-disposition lf-vr-${value}`, text);
        button.type = "button";
        button.dataset.disposition = value;
        button.addEventListener("click", () => this.#review(id, value));
        dispositions.append(button);
      }
      review.append(dispositions);
      heading.append(headingText, review);
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
      provenance.append(revisions);
      details.append(detailsSummary, provenance);
      const support = make("footer", "lf-vr-support");
      support.append(links, details);
      const toolbar = make("div", "lf-vr-toolbar-slot", null, false);
      const shotHost = make("div", "lf-vr-shot-host");
      this.#sizes?.observe(shotHost);
      const threadOutlet = make("section", "lf-vr-thread-outlet lf-ui");
      threadOutlet.dataset.lfGen = "1";
      threadOutlet.setAttribute("aria-label", "Threads on this visual case");
      article.append(heading, claim, toolbar, shotHost, support, threadOutlet);
      const entry = {
        article,
        option,
        shotHost,
        stopReading: null,
        record: null,
        index: 0,
        total: 0,
      };
      this.#registerCaseRegion(id, entry);
      return entry;
    }

    #registerCaseRegion(id, entry) {
      if (entry.stopReading) return;
      // The case's prose and controls are its furniture; the aligned captures are what
      // the user pages through. Making that relationship a nested reading region lets
      // the shared d/u and j/k routes follow the selected case without a package key.
      entry.stopReading = registerReadingRegion({
        id: compoundReadingRegionId(this, `case-${id}`),
        host: entry.article,
        body: entry.shotHost,
      });
    }

    #updateCase(entry, record, index, total) {
      entry.article.dataset.classification = record.classification;
      entry.article.setAttribute(
        "aria-label",
        `Visual review case ${index + 1} of ${total}`,
      );
      entry.record = record;
      entry.index = index;
      entry.total = total;
      this.#paintOption(entry);
      setText(
        entry.article.querySelector(".lf-vr-case-position"),
        `Case ${index + 1} of ${total} · ${CLASSIFICATION[record.classification]}`,
      );
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
      focus.closest(".lf-vr-detail").hidden = !record.focus;
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
      setText(observed, this.#run.observedAt);
      observed.dateTime = this.#run.observedAt;
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
      base.href = previewUrl(this.#run.base, record.path);
      candidate.href = previewUrl(this.#run.candidate, record.path);
      const trace = entry.article.querySelector(".lf-vr-trace-link");
      trace.hidden = !record.traceUrl;
      if (record.traceUrl) trace.href = record.traceUrl;

      const current = entry.shotHost.querySelector("lf-shot");
      const alt = `${record.title}. ${record.result}`;
      const before = scopedMediaUrl(record.before);
      const after = scopedMediaUrl(record.after);
      if (
        !current ||
        current.getAttribute("before") !== before ||
        current.getAttribute("after") !== after ||
        current.getAttribute("alt") !== alt
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
        entry.shotHost.replaceChildren(shot);
      }
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

    #select(id) {
      if (!this.#caseEntries.has(id)) return;
      const currentEntry = this.#caseEntries.get(this.#selected);
      const active = document.activeElement;
      const leavingCase = Boolean(active && currentEntry?.article.contains(active));
      const disposition = leavingCase
        ? active.closest(".lf-vr-disposition")?.dataset.disposition
        : null;
      if (id !== this.#selected) this.#scope = "focus";
      this.#selected = id;
      this.#queue.value = id;
      for (const [caseId, entry] of this.#caseEntries) {
        const selected = caseId === id;
        entry.article.hidden = !selected;
      }
      const selected = this.#caseEntries.get(id);
      const toolbar = selected.article.querySelector(".lf-vr-toolbar-slot");
      if (this.#inspector.parentElement !== toolbar) toolbar.append(this.#inspector);
      this.#paintInspector();
      this.#threadSurface?.update();
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
      paintKeys();
      // Moving the shared inspector between articles makes the browser drop its focus.
      // Restore that exact destination; a hidden case-local control instead lands on
      // the corresponding disposition — or the primary disposition when it has no
      // counterpart — rather than leaving a keyboard user on the document body.
      if (
        leavingCase &&
        (document.activeElement !== active ||
          !active.isConnected ||
          !active.checkVisibility())
      ) {
        const counterpart =
          active.isConnected && active.checkVisibility()
            ? active
            : disposition
              ? selected.article.querySelector(`[data-disposition="${disposition}"]`)
              : selected.article.querySelector(".lf-vr-disposition");
        counterpart?.focus({ preventScroll: true });
      }
    }

    #step(delta) {
      if (!this.#run?.cases.length) return;
      const ids = this.#run.cases.map(({ id }) => id);
      const current = Math.max(0, ids.indexOf(this.#selected));
      const next = ids[(current + delta + ids.length) % ids.length];
      this.#select(next);
    }

    #paintNavigation() {
      const count = this.#caseEntries.size;
      this.#queue.disabled = count === 0;
      for (const button of this.#queueHost.querySelectorAll("button"))
        button.disabled = count < 2;
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
      entry.article.dataset.disposition = disposition ?? "";
      for (const button of entry.article.querySelectorAll(".lf-vr-disposition"))
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.disposition === disposition),
        );
      this.#paintOption(entry);
      this.#paintProgress();
    }

    #paintOption(entry) {
      if (!entry.record) return;
      const disposition = entry.article.dataset.disposition;
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
        button.disabled = !available;
      paintKeys();
    }

    #paintProgress() {
      const total = this.#caseEntries.size;
      const reviewed = [...this.#caseEntries.values()].filter(
        ({ article }) => article.dataset.disposition,
      ).length;
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
      const units = state?.review?.units ?? {};
      for (const id of this.#caseEntries.keys())
        this.#setDisposition(id, units[id]?.detail?.disposition ?? null);
      this.#paintAvailability();
      return true;
    }
  },
);
