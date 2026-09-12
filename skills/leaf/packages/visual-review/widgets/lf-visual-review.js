/* A visual run is external evidence: one source supplies its cases, while Leaf's event
 * log owns case dispositions and threads. The module keeps browsing and inspection
 * choices local, projects each case with source provenance, and reshapes the existing
 * aligned lf-shot comparison without introducing another evidence model. */
import "/widgets/lf-shot.js";

import {
  actionAvailable,
  arrangeReadingElement,
  commands,
  compoundReadingRegionId,
  effectiveScroller,
  failSoft,
  fitRootReadingElement,
  layoutChanged,
  notice,
  offer,
  once,
  paintKeys,
  PRESS,
  projectData,
  registerReadingElement,
  registerThreadSurface,
  relabel,
  scopedMediaUrl,
  sendAction,
  settle,
  standingState,
  watchActions,
  watchData,
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
    #arrangements = [];
    #caseEntries = new Map();
    #casesBody = null;
    #commands = null;
    #copyObserver = null;
    #dialog = null;
    #dialogBody = null;
    #evidenceHost = null;
    #expand = null;
    #expandedOrigin = null;
    #expandedPlace = null;
    #fitting = null;
    #inspector = null;
    #layoutFrame = null;
    #mode = "compare";
    #onResize = () => this.#scheduleEvidenceLayout();
    #onBeforePrint = () => {
      this.#returnExpandedInspection();
    };
    #opacity = 50;
    #progress = null;
    #queue = null;
    #queueHost = null;
    #run = null;
    #scale = "fit";
    #scope = "focus";
    #selected = null;
    #snapshot = null;
    #partition = null;
    #sizes = null;
    #threadSurface = null;
    #title = null;

    connectedCallback() {
      if (once(this)) this.#buildLayout();
      else this.#registerLayout();
      this.#fitting = fitRootReadingElement({
        owner: this,
        readingArrangement: this.#arrangements.at(-1),
        minimumSize: () => ({ width: 720, height: 600 }),
      });
      this.#sizes = new ResizeObserver(() => this.#scheduleEvidenceLayout());
      this.#sizes.observe(this);
      for (const stage of this.querySelectorAll(".lf-vr-shot-host"))
        this.#sizes.observe(stage);
      window.addEventListener("resize", this.#onResize);
      window.addEventListener("beforeprint", this.#onBeforePrint);
      this.#copyObserver = new MutationObserver(() => {
        if (
          document.documentElement.classList.contains("lf-copy") &&
          this.#dialog?.open
        )
          this.#returnExpandedInspection();
      });
      this.#copyObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"],
      });
      settle(this.#fitting.update());
      this.#threadSurface ??= registerThreadSurface(this, {
        begin: () => {},
        outletFor: (entry) => this.#threadOutlet(entry),
        end: () => {},
      });
      this.stopActions ??= watchActions(this, null, () => this.#paintAvailability());
      this.stopWatching ??= watchData(this, "run", (snapshot) => this.#show(snapshot));
    }

    disconnectedCallback() {
      this.stopActions?.();
      this.stopActions = null;
      this.stopWatching?.();
      this.stopWatching = null;
      this.#threadSurface?.unregister();
      this.#threadSurface = null;
      this.#fitting?.cleanup();
      this.#fitting = null;
      this.#sizes?.disconnect();
      this.#sizes = null;
      window.removeEventListener("resize", this.#onResize);
      window.removeEventListener("beforeprint", this.#onBeforePrint);
      this.#copyObserver?.disconnect();
      this.#copyObserver = null;
      this.#returnExpandedInspection();
      if (this.#layoutFrame !== null) cancelAnimationFrame(this.#layoutFrame);
      this.#layoutFrame = null;
      this.#cleanupLayout();
    }

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
      this.#queue = offer("select", "lf-vr-case-select");
      this.#queue.name = "visual-case";
      this.#queue.setAttribute("aria-label", "Selected visual case");
      this.#queue.addEventListener("change", () => this.#select(this.#queue.value));
      const next = offer("button", "lf-btn lf-vr-next", "Next");
      next.type = "button";
      next.addEventListener("click", () => this.#step(1));
      this.#queueHost.append(previous, this.#queue, next);
      const queue = arrangeReadingElement({
        owner: this.#queueHost,
        role: "pane",
        regions: [
          {
            id: compoundReadingRegionId(this, "cases"),
            host: this.#queueHost,
          },
        ],
      });

      this.#evidenceHost = make("section", "lf-vr-evidence-region");
      this.#evidenceHost.setAttribute("aria-label", "Selected visual evidence");
      this.#inspector = this.#buildInspector();
      this.#casesBody = make("div", "lf-vr-cases");
      this.#evidenceHost.append(this.#casesBody);
      const evidence = arrangeReadingElement({
        owner: this.#evidenceHost,
        role: "pane",
        regions: [
          {
            id: compoundReadingRegionId(this, "evidence"),
            host: this.#evidenceHost,
          },
        ],
      });

      this.#partition = make("div", "lf-vr-partition");
      this.#partition.append(this.#queueHost, this.#evidenceHost);
      const partition = arrangeReadingElement({
        owner: this.#partition,
        role: "partition",
      });

      this.append(header, this.#partition);
      const workspace = arrangeReadingElement({
        owner: this,
        role: "workspace",
        header,
      });
      this.#arrangements = [
        queue.readingArrangement,
        evidence.readingArrangement,
        partition.readingArrangement,
        workspace.readingArrangement,
      ];
      this.#buildExpandedInspection();
      this.#registerCommands();
      this.#paintInspector();
    }

    #registerLayout() {
      const workspaceContent = this.querySelector(":scope > .lf-workspace-content");
      this.#partition = workspaceContent?.querySelector(":scope > .lf-vr-partition");
      const partitionContent = this.#partition?.querySelector(
        ":scope > .lf-partition-content",
      );
      this.#queueHost = partitionContent?.querySelector(":scope > .lf-vr-queue-region");
      this.#evidenceHost = partitionContent?.querySelector(
        ":scope > .lf-vr-evidence-region",
      );
      this.#queue = this.#queueHost?.querySelector(".lf-vr-case-select");
      this.#inspector = this.#evidenceHost?.querySelector(".lf-vr-inspector");
      this.#dialog = this.querySelector(":scope > .lf-vr-expanded");
      this.#dialogBody = this.#dialog?.querySelector(":scope > .lf-vr-expanded-body");
      this.#expand = this.#inspector?.querySelector(".lf-vr-expand");
      this.#casesBody = this.#evidenceHost?.querySelector(".lf-vr-cases");
      this.#title = this.querySelector(".lf-vr-title");
      this.#progress = this.querySelector(".lf-vr-progress");
      if (
        !workspaceContent ||
        !this.#partition ||
        !partitionContent ||
        !this.#queueHost ||
        !this.#evidenceHost ||
        !this.#queue ||
        !this.#inspector ||
        !this.#dialog ||
        !this.#dialogBody ||
        !this.#expand ||
        !this.#casesBody ||
        !this.#title ||
        !this.#progress
      )
        throw new Error("visual review lost its reading regions");
      this.#arrangements = [
        registerReadingElement({
          owner: this.#queueHost,
          content: this.#queueHost.querySelector(":scope > .lf-pane-content"),
          body: this.#queueHost.querySelector(
            ":scope > .lf-pane-content > .lf-pane-body",
          ),
          regions: [
            {
              id: compoundReadingRegionId(this, "cases"),
              host: this.#queueHost,
            },
          ],
        }),
        registerReadingElement({
          owner: this.#evidenceHost,
          content: this.#evidenceHost.querySelector(":scope > .lf-pane-content"),
          body: this.#evidenceHost.querySelector(
            ":scope > .lf-pane-content > .lf-pane-body",
          ),
          regions: [
            {
              id: compoundReadingRegionId(this, "evidence"),
              host: this.#evidenceHost,
            },
          ],
        }),
        registerReadingElement({
          owner: this.#partition,
          content: partitionContent,
        }),
        registerReadingElement({ owner: this, content: workspaceContent }),
      ];
      this.#registerCommands();
      this.#paintInspector();
    }

    #buildExpandedInspection() {
      this.#expand = offer("button", "lf-btn lf-vr-expand", "Expand inspection");
      this.#expand.type = "button";
      this.#expand.setAttribute("aria-haspopup", "dialog");
      this.#expand.setAttribute("aria-expanded", "false");
      this.#expand.addEventListener("click", () => this.#openExpandedInspection());
      commands(this.#expand, "On visual evidence", [
        {
          id: "visual.expand",
          keys: PRESS,
          does: "Expand visual inspection",
          line: "expand inspection",
          returnFrame: () => ({
            active: () => Boolean(this.#dialog?.open),
            close: () => this.#returnExpandedInspection(),
            does: "Return to the visual review",
            line: "return to review",
          }),
          run: () => this.#expand.click(),
        },
      ]);
      this.#inspector.append(this.#expand);

      this.#dialog = make("dialog", "lf-vr-expanded lf-ui", null, false);
      this.#dialog.setAttribute("aria-labelledby", `lf-${this.id}-expanded-title`);
      const head = make("header", "lf-vr-expanded-head", null, false);
      const title = make("strong", "lf-vr-expanded-title", "Expanded visual evidence");
      title.id = `lf-${this.id}-expanded-title`;
      const close = offer("button", "lf-btn lf-vr-expanded-close", "Close");
      close.type = "button";
      close.addEventListener("click", () => this.#returnExpandedInspection());
      head.append(title, close);
      this.#dialogBody = make("div", "lf-vr-expanded-body", null, false);
      this.#dialog.append(head, this.#dialogBody);
      this.#dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        this.#returnExpandedInspection();
      });
      this.#dialog.addEventListener("close", () => {
        if (this.#dialog.open) return;
        this.#returnExpandedInspection();
      });
      this.append(this.#dialog);
    }

    #openExpandedInspection() {
      if (this.#dialog.open) return;
      if (!this.#caseEntries.has(this.#selected)) return;
      this.#expandedOrigin = document.activeElement;
      const workspaceContent = this.querySelector(":scope > .lf-workspace-content");
      const scroller = effectiveScroller(this);
      this.#expandedPlace = {
        scroller,
        scrollTop: scroller.scrollTop,
        overflowAnchor: scroller.style.overflowAnchor,
        workspaceContent,
        minimumHeight: workspaceContent.style.minHeight,
      };
      scroller.style.overflowAnchor = "none";
      workspaceContent.style.minHeight = `${this.#partition.getBoundingClientRect().height}px`;
      this.#dialogBody.append(this.#partition);
      this.dataset.inspectionExpanded = "true";
      this.#expand.setAttribute("aria-expanded", "true");
      this.#dialog.showModal();
      this.#dialog
        .querySelector(".lf-vr-expanded-close")
        .focus({ preventScroll: true });
      this.#scheduleEvidenceLayout();
    }

    #returnExpandedInspection() {
      const place = this.#expandedPlace;
      if (!place) return;
      place.workspaceContent.append(this.#partition);
      place.workspaceContent.style.minHeight = place.minimumHeight;
      this.#expandedPlace = null;
      delete this.dataset.inspectionExpanded;
      this.#expand.setAttribute("aria-expanded", "false");
      const origin = this.#expandedOrigin;
      this.#expandedOrigin = null;
      if (this.#dialog.open) this.#dialog.close();
      this.#paintEvidenceLayout();
      // Resolve the returned partition's CSS-owned flow height before restoring the
      // document position; no later evidence paint changes that outer geometry.
      this.#partition.getBoundingClientRect();
      place.scroller.scrollTop = place.scrollTop;
      if (origin?.isConnected) origin.focus({ preventScroll: true });
      place.scroller.scrollTop = place.scrollTop;
      place.scroller.style.overflowAnchor = place.overflowAnchor;
      layoutChanged(this);
    }

    #buildInspector() {
      const inspector = offer("div", "lf-vr-inspector");
      inspector.setAttribute("aria-label", "Inspection controls");

      for (const [kind, values] of [
        ["scope", SCOPE],
        ["mode", INSPECTION],
        ["scale", SCALE],
      ]) {
        const group = offer("div", `lf-vr-inspector-group lf-vr-${kind}-group`);
        group.setAttribute("role", "group");
        group.setAttribute(
          "aria-label",
          { scope: "Scope", mode: "View", scale: "Size" }[kind],
        );
        for (const [value, text] of Object.entries(values)) {
          const button = offer("button", "lf-vr-inspector-button", text);
          button.dataset[kind] = value;
          button.addEventListener("click", () => {
            if (kind === "scope") this.#setScope(value);
            else if (kind === "mode") this.#setMode(value);
            else this.#setScale(value);
          });
          commands(button, "On visual evidence", [
            {
              id: `visual.${kind}.${value}`,
              keys: PRESS,
              does: `${text} visual evidence`,
              line: text.toLowerCase(),
              run: () => button.click(),
            },
          ]);
          group.append(button);
        }
        inspector.append(group);
      }

      const opacity = offer("label", "lf-vr-opacity-control");
      const opacityLabel = offer("span", "lf-vr-inspector-label", "Candidate opacity");
      const slider = offer("input", "lf-vr-opacity", undefined, "range");
      slider.min = "0";
      slider.max = "100";
      slider.name = "candidate-opacity";
      slider.step = "5";
      slider.value = String(this.#opacity);
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
      for (const button of scopeGroup.querySelectorAll("[data-scope]"))
        button.setAttribute("aria-pressed", String(button.dataset.scope === scope));
      for (const button of this.#inspector.querySelectorAll("[data-mode]"))
        button.setAttribute("aria-pressed", String(button.dataset.mode === this.#mode));
      for (const button of this.#inspector.querySelectorAll("[data-scale]"))
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.scale === this.#scale),
        );
      const opacity = this.#inspector.querySelector(".lf-vr-opacity-control");
      const slider = opacity.querySelector(".lf-vr-opacity");
      const active = this.#mode === "overlay";
      opacity.dataset.active = String(active);
      slider.disabled = !active;
      slider.value = String(this.#opacity);
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
      this.#layoutFrame = requestAnimationFrame(() => {
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
      const stageWidth = entry.shotHost.clientWidth;
      const bounded = this.#dialog?.open || this.dataset.lfReadingPosture === "bounded";
      if (bounded) entry.shotHost.style.setProperty("--lf-vr-stage-height", "100%");
      else entry.shotHost.style.removeProperty("--lf-vr-stage-height");
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
      // Geometry chooses the comparison, not another preference for the reader to
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

    #cleanupLayout() {
      for (const arrangement of this.#arrangements) arrangement.cleanup();
      this.#arrangements = [];
    }

    #registerCommands() {
      if (this.#commands) return;
      this.#commands = commands(this.#partition, "In a visual review", [
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
        this.#renderStandingState();
        settle(this.#fitting?.update());
      } catch (error) {
        failSoft(this, error);
      }
    }

    #renderMissing(snapshot) {
      setText(this.#title, "Waiting for a visual run");
      this.#inspector.hidden = true;
      this.#evidenceHost.append(this.#inspector);
      this.#queue.replaceChildren();
      for (const { shotHost } of this.#caseEntries.values())
        this.#sizes?.unobserve(shotHost);
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
      const option = document.createElement("option");
      option.value = id;

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
      return { article, option, shotHost, record: null, index: 0, total: 0 };
    }

    #updateCase(entry, record, index, total) {
      entry.article.dataset.classification = record.classification;
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
      if (id !== this.#selected) this.#scope = "focus";
      this.#selected = id;
      for (const [caseId, entry] of this.#caseEntries) {
        const selected = caseId === id;
        entry.article.hidden = !selected;
        entry.option.selected = selected;
      }
      const selected = this.#caseEntries.get(id);
      selected.article.querySelector(".lf-vr-toolbar-slot").append(this.#inspector);
      this.#paintInspector();
      this.#threadSurface?.update();
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
      paintKeys();
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
      if (!actionAvailable(this, "review")) return;
      this.#setDisposition(id, disposition);
      const accepted = await sendAction(this, "review", { case: id, disposition });
      if (accepted) notice(`${DISPOSITION[disposition]} — sent`);
      else this.#renderStandingState();
    }

    #renderStandingState() {
      const current = standingState().find(({ widget }) => widget === this);
      this.renderState(current?.state);
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
      const available = actionAvailable(this, "review");
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
      const units = state?.disposition?.units ?? {};
      for (const id of this.#caseEntries.keys())
        this.#setDisposition(id, units[id]?.detail?.disposition ?? null);
      this.#paintAvailability();
      return true;
    }
  },
);
