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
  flip: "Flip",
  side: "Side by side",
  opacity: "Opacity",
};

const SCALE = {
  fit: "Fit",
  actual: "Actual size",
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

function setEcho(element, text) {
  if (element.textContent !== text) relabel(element, text, { says: "echo" });
}

function previewUrl(target, path) {
  const base = new URL(target.url);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path.replace(/^\/+/, ""), base).href;
}

function captureText(capture) {
  return [
    `${capture.browser} ${capture.browserVersion}`,
    `${capture.viewport.width} × ${capture.viewport.height}`,
    `${capture.deviceScaleFactor}×`,
    capture.colorScheme,
    capture.locale,
    capture.timezone,
  ].join(" · ");
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
    #footer = null;
    #inspector = null;
    #mode = "flip";
    #opacity = 50;
    #queue = null;
    #queueHost = null;
    #run = null;
    #scale = "fit";
    #selected = null;
    #snapshot = null;
    #partition = null;
    #threadSurface = null;
    #title = null;

    connectedCallback() {
      if (once(this)) this.#buildLayout();
      else this.#registerLayout();
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
      this.#cleanupLayout();
    }

    #buildLayout() {
      const header = make("header", "lf-vr-head");
      const eyebrow = make("p", "lf-vr-eyebrow", "Visual review");
      this.#title = make("h2", "lf-vr-title", "Waiting for a visual run");
      header.append(eyebrow, this.#title);

      this.#queueHost = make("nav", "lf-vr-queue-region");
      this.#queueHost.setAttribute("aria-label", "Visual review cases");
      const queueHeader = make("p", "lf-vr-region-title", "Cases", false);
      this.#queue = document.createElement("ol");
      this.#queue.className = "lf-vr-queue";
      this.#queueHost.append(queueHeader, this.#queue);
      const queue = arrangeReadingElement({
        owner: this.#queueHost,
        role: "pane",
        header: queueHeader,
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
      this.#evidenceHost.append(this.#inspector, this.#casesBody);
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
      this.#partition.dataset.lfDirection = "columns";
      this.#partition.append(this.#queueHost, this.#evidenceHost);
      const partition = arrangeReadingElement({
        owner: this.#partition,
        role: "partition",
      });

      this.#footer = make("footer", "lf-vr-foot", "No cases reviewed");
      this.append(header, this.#partition, this.#footer);
      const workspace = arrangeReadingElement({
        owner: this,
        role: "workspace",
        header,
        footer: this.#footer,
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
      this.#queue = this.#queueHost?.querySelector(".lf-vr-queue");
      this.#inspector = this.#evidenceHost?.querySelector(".lf-vr-inspector");
      this.#casesBody = this.#evidenceHost?.querySelector(".lf-vr-cases");
      this.#title = this.querySelector(".lf-vr-title");
      this.#footer = this.querySelector(":scope > .lf-reading-after");
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
        !this.#footer
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
        const label = make(
          "span",
          "lf-vr-inspector-label",
          kind === "mode" ? "View" : "Size",
          false,
        );
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", label.textContent);
        group.append(label);
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
      const opacityLabel = make(
        "span",
        "lf-vr-inspector-label",
        "Candidate opacity",
        false,
      );
      const slider = offer("input", "lf-vr-opacity", undefined, "range");
      slider.min = "0";
      slider.max = "100";
      slider.name = "candidate-opacity";
      slider.step = "5";
      slider.value = String(this.#opacity);
      slider.setAttribute("aria-label", "Candidate opacity");
      slider.addEventListener("input", () => this.#setOpacity(Number(slider.value)));
      const output = make("output", "lf-vr-opacity-value", `${this.#opacity}%`, false);
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
      const active = this.#mode === "opacity";
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
          if (this.#mode !== "side") {
            oldLabel?.remove();
            continue;
          }
          if (oldLabel) continue;
          const label = make(
            "span",
            "lf-vr-frame-label lf-ui",
            frame.dataset.lfState === "before" ? "Base" : "Candidate",
            false,
          );
          label.setAttribute("aria-hidden", "true");
          frame.prepend(label);
        }
      }
      layoutChanged(this);
      paintKeys();
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
        this.#paintInspector();
        const fallback = this.#run.cases.find(
          ({ classification }) => classification !== "clean",
        );
        if (!this.#caseEntries.has(this.#selected))
          this.#selected = fallback?.id ?? ids[0];
        this.#select(this.#selected);
        this.#renderStandingState();
      } catch (error) {
        failSoft(this, error);
      }
    }

    #renderMissing(snapshot) {
      setText(this.#title, "Waiting for a visual run");
      this.#inspector.hidden = true;
      this.#queue.replaceChildren();
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
      setText(this.#footer, "No cases reviewed");
      layoutChanged(this);
      paintKeys();
    }

    #reconcileCases(cases) {
      const wanted = new Set(cases.map(({ id }) => id));
      for (const [id, entry] of this.#caseEntries) {
        if (wanted.has(id)) continue;
        entry.item.remove();
        entry.article.remove();
        this.#caseEntries.delete(id);
      }
      const items = [];
      const articles = [];
      for (const [index, record] of cases.entries()) {
        let entry = this.#caseEntries.get(record.id);
        if (!entry) {
          entry = this.#createCase(record.id);
          this.#caseEntries.set(record.id, entry);
        }
        this.#updateCase(entry, record, index, cases.length);
        items.push(entry.item);
        articles.push(entry.article);
      }
      orderChildren(this.#queue, items);
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
      const item = document.createElement("li");
      item.className = "lf-vr-queue-item lf-ui";
      const tab = offer("button", "lf-vr-case-tab");
      tab.type = "button";
      tab.dataset.case = id;
      tab.addEventListener("click", () => this.#select(id));
      const marker = make("span", "lf-vr-case-marker");
      marker.setAttribute("aria-hidden", "true");
      const label = make("span", "lf-vr-case-label");
      const classification = make("span", "lf-vr-case-classification");
      tab.append(marker, label, classification);
      item.append(tab);

      const article = make("article", "lf-vr-case");
      const heading = make("header", "lf-vr-case-head");
      const position = make("p", "lf-vr-case-position");
      const title = make("h3", "lf-vr-case-title");
      const path = make("code", "lf-vr-path");
      heading.append(position, title, path);
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
      const provenance = make("p", "lf-vr-provenance");
      const shotHost = make("div", "lf-vr-shot-host");
      const review = make("footer", "lf-vr-review");
      const reviewLabel = make("span", "lf-vr-review-label", "Case disposition");
      const dispositions = make("div", "lf-vr-dispositions");
      for (const [value, text] of Object.entries(DISPOSITION)) {
        const button = offer("button", `lf-btn lf-vr-disposition lf-vr-${value}`, text);
        button.type = "button";
        button.dataset.disposition = value;
        button.addEventListener("click", () => this.#review(id, value));
        dispositions.append(button);
      }
      review.append(reviewLabel, dispositions);
      const threadOutlet = make("section", "lf-vr-thread-outlet lf-ui");
      threadOutlet.dataset.lfGen = "1";
      threadOutlet.setAttribute("aria-label", "Threads on this visual case");
      article.append(heading, claim, links, provenance, shotHost, review, threadOutlet);
      return { article, item, tab, shotHost };
    }

    #updateCase(entry, record, index, total) {
      entry.article.dataset.classification = record.classification;
      entry.tab.dataset.classification = record.classification;
      setEcho(entry.tab.querySelector(".lf-vr-case-label"), record.title);
      setEcho(
        entry.tab.querySelector(".lf-vr-case-classification"),
        CLASSIFICATION[record.classification],
      );
      setText(
        entry.article.querySelector(".lf-vr-case-position"),
        `Case ${index + 1} of ${total} · ${CLASSIFICATION[record.classification]}`,
      );
      setText(entry.article.querySelector(".lf-vr-case-title"), record.title);
      setText(entry.article.querySelector(".lf-vr-path"), record.path);
      setText(entry.article.querySelector(".lf-vr-action"), record.action);
      setText(entry.article.querySelector(".lf-vr-result"), record.result);
      setText(
        entry.article.querySelector(".lf-vr-provenance"),
        `${captureText(record.capture)} · observed ${this.#run.observedAt} · base ${this.#run.base.revision} · candidate ${this.#run.candidate.revision}`,
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
        entry.tab.setAttribute("aria-current", selected ? "step" : "false");
        entry.tab.setAttribute("aria-pressed", String(selected));
      }
      this.#threadSurface?.update();
      layoutChanged(this);
      paintKeys();
    }

    #step(delta) {
      const ids = this.#run.cases.map(({ id }) => id);
      const current = Math.max(0, ids.indexOf(this.#selected));
      const next = ids[(current + delta + ids.length) % ids.length];
      this.#select(next);
      this.#caseEntries.get(next).tab.focus({ preventScroll: true });
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
      this.#paintProgress();
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
        this.#footer,
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
