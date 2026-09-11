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
    #evidenceHost = null;
    #fitting = null;
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

    #buildInspector() {
      const inspector = offer("div", "lf-vr-inspector");
      inspector.setAttribute("aria-label", "Inspection controls");

      for (const [kind, values] of [
        ["mode", INSPECTION],
        ["scale", SCALE],
      ]) {
        const group = offer("div", `lf-vr-inspector-group lf-vr-${kind}-group`);
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", kind === "mode" ? "View" : "Size");
        for (const [value, text] of Object.entries(values)) {
          const button = offer("button", "lf-vr-inspector-button", text);
          button.dataset[kind] = value;
          button.addEventListener("click", () => {
            if (kind === "mode") this.#setMode(value);
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
      this.style.setProperty("--lf-vr-opacity", String(this.#opacity / 100));
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
      const heights = frames.map((frame) => {
        const image = frame.querySelector("img");
        if (!image.complete)
          image.addEventListener("load", () => this.#scheduleEvidenceLayout(), {
            once: true,
          });
        return image.naturalHeight ? image.naturalHeight / ratio : fallbackHeight;
      });
      const width = capture.viewport.width;
      const stageWidth = entry.shotHost.clientWidth;
      const bounded = this.dataset.lfReadingPosture === "bounded";
      // Flow layout follows the widget's own width, so scrolling cannot make a later
      // paint-only inspection control resize the evidence and move the document.
      const stageHeight = bounded
        ? entry.shotHost.clientHeight
        : Math.max(220, Math.min(560, stageWidth / 2));
      if (stageHeight <= 0) return;

      const gap = 8;
      const frameBorder = 2;
      const labelHeight = 24;
      const sideScale = Math.min(
        (stageWidth - gap - 2 * frameBorder) / (2 * width),
        (stageHeight - labelHeight) / Math.max(...heights),
      );
      const stackScale = Math.min(
        (stageWidth - frameBorder) / width,
        (stageHeight - 2 * labelHeight - gap) / (heights[0] + heights[1]),
      );
      // Geometry chooses the comparison, not another preference for the reader to
      // manage. Wide captures stack so their scan lines remain readable in the scrolling
      // stage; other pairs take the arrangement with the larger common scale.
      const wideCapture = width / Math.max(...heights) >= 1.5;
      const compareLayout = wideCapture || stackScale >= sideScale ? "stack" : "side";
      const fitScale =
        this.#mode === "compare"
          ? compareLayout === "stack"
            ? stackScale
            : sideScale
          : Math.min(
              (stageWidth - frameBorder) / width,
              stageHeight / Math.max(...heights),
            );
      // A stacked comparison is a vertical reading surface: fit each capture to the
      // available width and let the bounded stage scroll through the pair. Containing
      // both frames in the stage makes shallow captures unreadably small even when the
      // workspace has ample horizontal room.
      const stackFitScale = (stageWidth - frameBorder) / width;
      const scale =
        this.#scale === "actual"
          ? 1
          : Math.min(
              1,
              this.#mode === "compare" && compareLayout === "stack"
                ? stackFitScale
                : fitScale,
            );
      this.dataset.compareLayout = compareLayout;
      const beforeLabel = frames[0].querySelector(".lf-vr-frame-label");
      if (beforeLabel)
        beforeLabel.dataset.label =
          compareLayout === "stack" ? "Base · Candidate below" : "Base";
      entry.shotHost.style.setProperty(
        "--lf-vr-frame-width",
        `${Math.max(1, width * scale)}px`,
      );
      entry.shotHost.style.setProperty(
        "--lf-vr-stage-height",
        bounded ? "100%" : `${stageHeight}px`,
      );
    }

    #cleanupLayout() {
      for (const arrangement of this.#arrangements) arrangement.cleanup();
      this.#arrangements = [];
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
      entry.shotHost.style.setProperty(
        "--lf-vr-capture-width",
        `${record.capture.viewport.width}px`,
      );
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

    #select(id) {
      if (!this.#caseEntries.has(id)) return;
      this.#selected = id;
      for (const [caseId, entry] of this.#caseEntries) {
        const selected = caseId === id;
        entry.article.hidden = !selected;
        entry.option.selected = selected;
      }
      const selected = this.#caseEntries.get(id);
      selected.article.querySelector(".lf-vr-toolbar-slot").append(this.#inspector);
      this.#threadSurface?.update();
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
      paintKeys();
    }

    #step(delta) {
      const ids = this.#run.cases.map(({ id }) => id);
      const current = Math.max(0, ids.indexOf(this.#selected));
      const next = ids[(current + delta + ids.length) % ids.length];
      this.#select(next);
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
