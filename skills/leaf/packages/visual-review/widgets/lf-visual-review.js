/* A visual run is external evidence: one source supplies its cases, while Leaf's event
 * log owns case dispositions and threads. The module keeps browsing and inspection
 * choices local, projects each case with source provenance, and reshapes the existing
 * lf-shot inspection API without owning the pair's frame markup or styles. Evidence
 * precedes judgment; inspection is a local disclosure. Remaining-case navigation
 * reads the same projected dispositions as their buttons, while the case picker
 * retains every case so a reviewer can revisit a judgment. */
import "/widgets/lf-shot.js";
import "/vendor/webawesome.esm.js";

import {
  commands,
  commandsOn,
  countAreas,
  describeDifference,
  compoundReadingRegionId,
  placeKeeper,
  failSoft,
  frameFor,
  focusDestination,
  holdFocus,
  keeps,
  layoutChanged,
  notice,
  nothing,
  offered,
  html,
  keyed,
  live,
  ref,
  render,
  repeat,
  once,
  paintKeys,
  PRESS,
  projectData,
  readingPosture,
  registerReadingRegion,
  releaseOutlets,
  scopedMediaUrl,
  scrollerFor,
  scrollIntoReadingBand,
  scrollIntoView,
  scrollBehavior,
  shownWindow,
  sizeObserver,
  threadSurface,
  watchData,
  whileConnected,
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

const detail = (name, cls, value, tag = "span") =>
  html`<div class="lf-vr-detail">
    <dt class="lf-vr-detail-term" data-lf-gen="1" data-lf-said>${name}</dt>
    <dd class="lf-vr-detail-value">
      ${
        tag === "code"
          ? html`<code class=${cls} data-lf-gen="1" data-lf-said>${value}</code>`
          : html`<span class=${cls} data-lf-gen="1" data-lf-said>${value}</span>`
      }
    </dd>
  </div>`;

const formatOpacity = (value) => `${value}%`;

function previewUrl(target, path) {
  const base = new URL(target.url);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path.replace(/^\/+/, ""), base).href;
}

customElements.define(
  "lf-visual-review",
  class extends HTMLElement {
    #controller = widgetController(this);
    #presentGenerated = (promise) => this.#controller.present(promise);
    #caseEntries = new Map();
    #casesBody = null;
    #commands = null;
    #evidenceHost = null;
    #stopEvidence = null;
    #inspector = null;
    #mode = "compare";
    #observedCase;
    #scheduleEvidenceLayout = frameFor(this, () => this.#paintEvidenceLayout());
    #opacity = 50;
    #reviewUnits = {};
    #run = null;
    #sourceReady = true;
    #scale = "fit";
    #scope = "focus";
    #selected = null;
    #snapshot = null;
    #sizes = null;

    connectedCallback() {
      if (!once(this)) return;
      this.#buildLayout();
      whileConnected(this, (signal) => {
        this.#sizes = sizeObserver(this.#scheduleEvidenceLayout);
        this.#bindEvidence();
        window.addEventListener("resize", this.#scheduleEvidenceLayout, { signal });
        return () => {
          this.#sizes.disconnect();
          this.#sizes = null;
          this.#stopEvidence();
          this.#stopEvidence = null;
        };
      });
      // renderState paints the complete reading; subscribing activates its lifecycle.
      this.#controller.subscribe(() => {});
      watchData(this, "run", (snapshot) => this.#show(snapshot));
    }

    // A recovered template has new evidence nodes under the same region identity.
    #bindEvidence() {
      this.#stopEvidence?.();
      this.#stopEvidence = registerReadingRegion({
        id: compoundReadingRegionId(this, "evidence"),
        host: this.#evidenceHost,
        body: this.#casesBody,
      });
      this.#observedCase = undefined;
      this.#observeSelected();
    }

    // The pair's allocation reads the pane, the selected case's stage and what stands
    // above it there. Hidden cases measure nothing, so only the selected one is observed.
    #observeSelected() {
      const article = this.#caseEntries.get(this.#selected)?.article ?? null;
      if (!this.#sizes || article === this.#observedCase) return;
      this.#observedCase = article;
      this.#sizes.disconnect();
      for (const node of [
        this,
        this.#casesBody,
        ...(article?.querySelectorAll(
          ":scope > :is(.lf-vr-case-head, .lf-vr-toolbar-slot, .lf-vr-shot-host)",
        ) ?? []),
      ])
        this.#sizes.observe(node);
    }

    // The review composes the layer's pane grammar rather than choosing a posture: a
    // heading, then one evidence pane whose header is the case navigation and whose
    // body holds the cases.
    #buildLayout() {
      // One retained inspection disclosure follows the selected case, including its
      // native open state and the reader's current control.
      this.#inspector = document.createElement("details");
      this.#inspector.className = "lf-vr-inspection";
      this.#inspector.setAttribute("aria-label", "Inspection controls");
      this.#render();
      this.#registerCommands();
    }

    #choices(kind, label, values, current, hidden = false) {
      return html`<wa-radio-group
        ${offered(`lf-vr-inspector-group lf-vr-${kind}-group`)}
        label=${label}
        name=${`${this.id}-${kind}`}
        size="s"
        orientation="horizontal"
        ?hidden=${hidden}
        .value=${live(current)}
        @change=${(event) => {
          const value = event.currentTarget.value;
          if (kind === "scope") this.#setScope(value);
          else if (kind === "mode") this.#setMode(value);
          else this.#setScale(value);
        }}
      >
        ${repeat(
          Object.entries(values),
          ([value]) => value,
          ([value, text]) =>
            html`<wa-radio
              ${offered("lf-vr-inspector-choice", true)}
              value=${value}
              appearance="button"
              ${commandsOn("On visual evidence", (radio) => [
                {
                  id: `visual.${kind}.${value}`,
                  keys: PRESS,
                  title: text.toLowerCase(),
                  run: () => radio.click(),
                },
              ])}
              >${text}</wa-radio
            >`,
        )}
      </wa-radio-group>`;
    }

    // Whether the selected case can show its focus crop.
    #focusAvailable() {
      const entry = this.#caseEntries.get(this.#selected);
      return Boolean(entry?.record.focus && entry.shot?.supportsCrop);
    }

    #renderInspector() {
      const focusAvailable = this.#focusAvailable();
      const scope = focusAvailable ? this.#scope : "full";
      const active = this.#mode === "overlay";
      keeps(this, "data-inspection-mode", this.#mode);
      keeps(this, "data-inspection-scale", this.#scale);
      keeps(this, "data-inspection-scope", scope);
      render(
        html`<summary ${offered("lf-vr-inspection-summary")}>
            Inspect comparison
          </summary>
          <div ${offered("lf-vr-inspector")}>
            ${this.#choices("scope", "Scope", SCOPE, scope, !focusAvailable)}
            ${this.#choices("mode", "View", INSPECTION, this.#mode)}
            ${this.#choices("scale", "Size", SCALE, this.#scale)}
            <div ${offered("lf-vr-opacity-control")} data-active=${active}>
              <span ${offered("lf-vr-inspector-label lf-label")}>Candidate opacity</span>
              <wa-slider
                ${offered("lf-vr-opacity")}
                size="s"
                label="Candidate opacity"
                aria-label="Candidate opacity"
                name="candidate-opacity"
                min="0"
                max="100"
                step="5"
                .valueFormatter=${formatOpacity}
                .value=${live(this.#opacity)}
                ?disabled=${!active}
                @input=${(event) => this.#setOpacity(Number(event.currentTarget.value))}
              ></wa-slider>
              <output ${offered("lf-vr-opacity-value")}>${this.#opacity}%</output>
            </div>
          </div>`,
        this.#inspector,
      );
    }

    #setScope(scope) {
      if (scope === "focus" && !this.#focusAvailable()) {
        this.#renderInspector();
        return;
      }
      if (scope === this.#scope) return;
      this.#scope = scope;
      this.#paintInspection();
      notice(`${SCOPE[scope]} evidence`);
    }

    #setMode(mode) {
      if (mode === this.#mode) return;
      this.#mode = mode;
      this.#paintInspection();
      notice(`${INSPECTION[mode]} view`);
    }

    #setScale(scale) {
      if (scale === this.#scale) return;
      this.#scale = scale;
      this.#paintInspection();
      notice(`${SCALE[scale]} evidence`);
    }

    #setOpacity(opacity) {
      this.#opacity = Math.max(0, Math.min(100, opacity));
      this.#renderInspector();
      this.#inspectShots();
    }

    // Every pair takes the current choices, so a case shows them when selected and on
    // paper. The selected pair's allocation follows in `#paintEvidenceLayout`.
    #inspectShots() {
      for (const { shot, record } of this.#caseEntries.values())
        if (shot) this.#inspectShot(shot, record);
    }

    #inspectShot(shot, record) {
      shot.inspect({
        mode: this.#mode,
        pixelRatio: record.capture.deviceScaleFactor,
        captureWidth: record.capture.viewport.width,
        focus: record.focus,
        crop: this.#scope === "focus",
        opacity: this.#opacity / 100,
        labels: { before: "Base", after: "Candidate" },
      });
    }

    // A source, review state or selection change renders the cases, then the inspection.
    #paintReview() {
      if (this.#render()) this.#paintInspection();
    }

    // An inspection choice repaints the inspector and the pairs; the cases stand.
    #paintInspection() {
      this.#renderInspector();
      this.#inspectShots();
      this.#paintEvidenceLayout();
      layoutChanged(this);
      paintKeys();
    }

    #paintEvidenceLayout() {
      const entry = this.#caseEntries.get(this.#selected);
      const shot = entry?.shot;
      const stage = shot?.parentElement;
      const geometry = shot?.captureGeometry;
      if (geometry?.images.length !== 2 || !stage.clientWidth) return;

      const { capture } = entry.record;
      const ratio = capture.deviceScaleFactor;
      const heights = geometry.images.map((image) =>
        image.height ? image.height / ratio : capture.viewport.height,
      );
      const widths = geometry.images.map((image) =>
        image.width ? image.width / ratio : capture.viewport.width,
      );
      const focus = entry.record.focus;
      const activeFocus =
        this.#focusAvailable() && this.#scope === "focus" ? focus : null;
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
      const stageWidth = stage.clientWidth;
      const stageHeight = bounded
        ? this.#casesBody.clientHeight -
          (stage.getBoundingClientRect().top -
            this.#casesBody.getBoundingClientRect().top +
            this.#casesBody.scrollTop) -
          (stage.offsetHeight - stage.clientHeight)
        : shownWindow({ viewport: "layout" }).height;

      const { gap, labelHeight } = geometry;
      const frameBorder = 2 * geometry.frameBorder;
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
      const rail = this.#mode === "flip" ? geometry.railHeight : 0;
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
      shot.inspect({ layout: compareLayout, scale });
    }

    #registerCommands() {
      if (this.#commands) return;
      this.#commands = commands(this, "In a visual review", [
        {
          id: "visual.next-case",
          control: () => this.querySelector(".lf-vr-next"),
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
          control: () => this.querySelector(".lf-vr-previous"),
          keys: ["ArrowUp"],
          title: "previous case",
          when: () => this.#caseEntries.size > 1,
          run: () => this.#step(-1),
        },
      ]);
    }

    #show(snapshot) {
      // A case the run drops goes with its thread outlet, so core's composer leaves it
      // first, before the hold below would land the user on the evidence instead.
      const cases = new Set(snapshot?.value?.cases.map(({ id }) => id));
      for (const [id, { article }] of this.#caseEntries)
        if (article && !cases.has(id)) releaseOutlets(article);
      const restoreFocus = holdFocus(this);
      const resume = this.#controller.defer();
      try {
        const places = placeKeeper(scrollerFor(this.#casesBody), {
          items: `#${CSS.escape(this.id)} :is(.lf-vr-case-title, .lf-vr-disposition, .lf-vr-next-remaining, .lf-vr-details-summary, .lf-vr-action, .lf-vr-result)`,
          identity: (node) =>
            `${node.closest(".lf-vr-case").dataset.lfDatum}/${node.dataset.disposition ?? [...node.classList].find((name) => name.startsWith("lf-vr-"))}`,
        });
        const run = snapshot?.value ?? null;
        places.around(() => {
          this.#sourceReady = true;
          this.#snapshot = snapshot;
          this.#run = run;
          // Drawn from its data, which lifts the height the page reserved (x-height),
          // and held at that height again while the data is absent.
          this.classList.toggle("lf-rendered", this.#run !== null);
          if (!this.#run) {
            this.#renderMissing();
            return;
          }
          this.#reconcileCases(this.#run.cases);
          const fallback = this.#run.cases.find(
            ({ classification }) => classification !== "clean",
          );
          if (!this.#caseEntries.has(this.#selected))
            this.#selected = fallback?.id ?? this.#run.cases[0].id;
          this.#paintReview();
          this.#project();
          threadSurface(this).update();
          this.#scheduleEvidenceLayout();
        });
        restoreFocus?.(() => {
          if (!this.#selected) return false;
          this.#landOnEvidence("return");
          return true;
        });
      } catch (error) {
        // Semantic and mechanical paints cannot revive evidence from a rejected source.
        // Only another successful source commit may replace this failure view, and
        // it rebuilds the cases the failure view discarded.
        this.#sourceReady = false;
        this.#caseEntries.clear();
        releaseOutlets(this);
        failSoft(this, error);
      } finally {
        resume();
      }
    }

    #renderMissing() {
      this.#selected = null;
      this.#reconcileCases([]);
      this.#render();
      this.#project();
      layoutChanged(this);
      paintKeys();
    }

    #reconcileCases(cases) {
      const wanted = new Set(cases.map(({ id }) => id));
      for (const id of this.#caseEntries.keys())
        if (!wanted.has(id)) this.#caseEntries.delete(id);
      for (const record of cases) {
        let entry = this.#caseEntries.get(record.id);
        if (!entry) {
          entry = { record, difference: undefined, attempt: 0, shot: null };
          entry.place = (article) => (entry.article = article ?? null);
          entry.prepare = (shot) => {
            entry.shot = shot ?? null;
            if (!shot) return;
            this.#inspectShot(shot, entry.record);
            shot.difference.then(
              (reading) => {
                if (this.#caseEntries.get(record.id) !== entry || entry.shot !== shot)
                  return;
                entry.difference = reading;
                this.#render();
              },
              () => {},
            );
          };
          this.#caseEntries.set(record.id, entry);
        } else if (!entry.shot?.captureGeometry.images.length) entry.attempt += 1;
        const before = scopedMediaUrl(record.before);
        const after = scopedMediaUrl(record.after);
        const shotKey = `${before}\n${after}\n${entry.attempt}`;
        if (entry.shotKey !== shotKey) entry.difference = undefined;
        Object.assign(entry, { record, before, after, shotKey });
      }
    }

    // lf-shot's rail stays hidden outside Flip, and a focus crop hides the outlines,
    // so Capture details states the complete reading in every view, including
    // regions extending beyond a focus, including groups crossing its edge.
    // The heading contains only captured facts: computing
    // differences happens after presentation and must not move evidence or controls.
    #position(record, index, total) {
      const difference = this.#caseEntries.get(record.id)?.difference;
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
                  region.x < focus.x * ratio ||
                  region.x + region.width > (focus.x + focus.width) * ratio ||
                  region.y < focus.y * ratio ||
                  region.y + region.height > (focus.y + focus.height) * ratio,
              ),
            )
          : { changed: 0, moved: 0 };
        const left = outside.changed + outside.moved;
        parts.push(
          describeDifference(difference) + (left ? ` (${left} beyond the focus)` : ""),
        );
      }
      return [
        `${parts.slice(0, 2).join(" · ")}${record.focus ? " · Focused capture" : ""}`,
        parts.join(" · "),
      ];
    }

    #select(id, land = false, restoreFocus = holdFocus(this)) {
      if (!this.#caseEntries.has(id)) return;
      // Changing case from a verdict is a route to its counterpart, not a passive
      // return to the old control. Reveal that destination through the document's
      // scroll owner; a source refresh supplies its own hold and passes null here.
      const disposition = restoreFocus
        ? focused()?.closest?.(".lf-vr-disposition")?.dataset.disposition
        : null;
      if (id !== this.#selected) this.#scope = "focus";
      this.#selected = id;
      this.#paintReview();
      const selected = this.#caseEntries.get(id);
      threadSurface(this).update();
      layoutChanged(this);
      this.#scheduleEvidenceLayout();
      paintKeys();
      if (land) this.#landOnEvidence("move");
      else if (disposition) {
        const destination = selected.article.querySelector(
          `.lf-vr-disposition[data-disposition="${disposition}"]`,
        );
        focusDestination(destination, "move");
        scrollIntoView(destination, { block: "nearest" });
      } else
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

    async #review(id, disposition) {
      if (!this.#controller.read().actions.review.available) return;
      const accepted = await this.#controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { case: id, disposition },
      })?.delivery;
      if (accepted) notice(`${DISPOSITION[disposition]} — sent`);
    }

    #caseView(record, index, total, remaining) {
      const disposition = this.#disposition(record.id);
      const selected = record.id === this.#selected;
      const available = this.#controller.read().actions.review?.available ?? false;
      const [heading, analysis] = this.#position(record, index, total);
      const { before, after, shotKey, prepare, place } = this.#caseEntries.get(
        record.id,
      );
      const link = (cls, label, href) =>
        html`<a
          ${offered(`lf-btn ${cls}`)}
          target="_blank"
          rel="noopener noreferrer"
          ?hidden=${!href}
          href=${href || nothing}
          >${label}</a
        >`;
      return html`<article
        class="lf-vr-case"
        data-classification=${record.classification}
        data-disposition=${disposition ?? ""}
        aria-label=${`Visual review case ${index + 1} of ${total}`}
        ?data-selected=${selected}
        ${ref(place)}
      >
        <header class="lf-vr-case-head">
          <div class="lf-vr-case-heading">
            <p class="lf-vr-case-position lf-label" data-lf-gen="1" data-lf-said>${heading}</p>
            <h3 class="lf-vr-case-title" data-lf-gen="1" data-lf-said>
              ${record.title}
            </h3>
          </div>
        </header>
        <div class="lf-vr-toolbar-slot">${selected ? this.#inspector : ""}</div>
        <div class="lf-vr-shot-host">
          ${keyed(
            shotKey,
            // Property and ref bindings commit before connection: the generated shot
            // joins its owner's presentation barrier and declares keys for this mode.
            html`<lf-shot
              id=${`lf-${this.id}-${record.id}-comparison`}
              before=${before}
              after=${after}
              alt=${`${record.title}. ${record.result}`}
              outlines
              ._lfPresentGenerated=${this.#presentGenerated}
              ${ref(prepare)}
              @captureload=${this.#scheduleEvidenceLayout}
            ></lf-shot>`,
          )}
        </div>
        <dl class="lf-vr-claim">
          <dt class="lf-vr-action-term" data-lf-gen="1" data-lf-said>Action</dt>
          <dd class="lf-vr-action" data-lf-gen="1" data-lf-said>${record.action}</dd>
          <dt class="lf-vr-result-term" data-lf-gen="1" data-lf-said>
            Observed result
          </dt>
          <dd class="lf-vr-result" data-lf-gen="1" data-lf-said>${record.result}</dd>
        </dl>
        <div class="lf-vr-review" role="group" aria-label="Case review">
          <div class="lf-vr-dispositions">
            ${Object.entries(DISPOSITION).map(
              ([value, text]) =>
                html`<button
                  ${offered(`lf-btn lf-vr-disposition lf-vr-${value}`)}
                  data-disposition=${value}
                  aria-pressed=${String(disposition === value)}
                  ?disabled=${!available}
                  @click=${() => this.#review(record.id, value)}
                >
                  ${text}
                </button>`,
            )}
          </div>
          <button ${offered("lf-btn lf-vr-next-remaining")}>Next unreviewed</button>
          <p class="lf-vr-review-status" data-lf-gen="1" data-lf-said>
            ${
              remaining === 0
                ? "All cases reviewed · revisit any case above"
                : remaining === 1 && !disposition
                  ? "Current case is the last unreviewed"
                  : `${disposition ? DISPOSITION[disposition] : "Not reviewed"} · ${remaining} unreviewed`
            }
          </p>
        </div>
        <footer class="lf-vr-support">
          <div class="lf-vr-links">
            ${link("lf-vr-base-link", "Open base", this.#run.base.url && previewUrl(this.#run.base, record.path))}
            ${link("lf-vr-candidate-link", "Open candidate", this.#run.candidate.url && previewUrl(this.#run.candidate, record.path))}
            ${link("lf-vr-trace-link", "Open trace", record.traceUrl)}
          </div>
          <details class="lf-vr-details">
            <summary ${offered("lf-vr-details-summary")}>Capture details</summary>
            <dl class="lf-vr-provenance">
              ${detail("Path", "lf-vr-path", record.path, "code")}
              ${detail("Browser", "lf-vr-browser", `${record.capture.browser} ${record.capture.browserVersion}`)}
              ${detail("Viewport", "lf-vr-viewport", `${record.capture.viewport.width} × ${record.capture.viewport.height} · ${record.capture.deviceScaleFactor}×`)}
              ${
                record.focus
                  ? detail(
                      "Focus area",
                      "lf-vr-focus",
                      `${record.focus.x}, ${record.focus.y} · ${record.focus.width} × ${record.focus.height} CSS px`,
                    )
                  : ""
              }
              ${detail("Appearance", "lf-vr-appearance", `${record.capture.colorScheme} · ${record.capture.locale} · ${record.capture.timezone}`)}
              <div class="lf-vr-detail">
                <dt class="lf-vr-detail-term" data-lf-gen="1" data-lf-said>Observed</dt>
                <dd class="lf-vr-detail-value">
                  <time
                    class="lf-vr-observed"
                    datetime=${record.capture.observedAt}
                    data-lf-gen="1"
                    data-lf-said
                    >${record.capture.observedAt}</time
                  >
                </dd>
              </div>
              <p class="lf-vr-analysis" data-lf-gen="1" data-lf-said>${analysis}</p>
              <div class="lf-vr-revisions">
                ${detail("Base revision", "lf-vr-base-revision", this.#run.base.revision, "code")}
                ${detail("Candidate revision", "lf-vr-candidate-revision", this.#run.candidate.revision, "code")}
              </div>
            </dl>
          </details>
        </footer>
        <section
          class="lf-vr-thread-outlet lf-ui"
          data-lf-gen="1"
          aria-label="Threads on this visual case"
        ></section>
      </article>`;
    }

    #render() {
      if (!this.#inspector || !this.#sourceReady) return false;
      const run = this.#run;
      const cases = run?.cases ?? [];
      const remaining = this.#remaining().length;
      const reviewed = cases.length - remaining;
      render(
        html`<header class="lf-vr-head">
            <h2 class="lf-vr-title" data-lf-gen="1" data-lf-said>
              ${run ? run.title : "Waiting for a visual run"}
            </h2>
            <p class="lf-vr-progress" data-lf-gen="1" data-lf-said>
              ${cases.length ? `${reviewed} of ${cases.length} cases reviewed` : "No cases reviewed"}
            </p>
          </header>
          <section
            class="lf-vr-evidence-region"
            data-lf-reading-role="pane"
            data-lf-generated
            aria-label="Selected visual evidence"
          >
            <header class="lf-vr-queue">
              <nav ${offered("lf-vr-queue-region")} aria-label="Visual review cases">
                <wa-select
                  ${offered("lf-vr-case-select")}
                  name="visual-case"
                  size="s"
                  label="Selected visual case"
                  aria-label="Selected visual case"
                  ?disabled=${!cases.length}
                  .value=${live(this.#selected ?? "")}
                  @change=${(event) => this.#select(event.currentTarget.value)}
                >
                  ${repeat(
                    cases,
                    (record) => record.id,
                    (record, index) =>
                      html`<wa-option ${offered("")} value=${record.id}
                        >${`${index + 1} of ${cases.length} · ${record.title} · ${
                          DISPOSITION[
                            this.#reviewUnits[record.id]?.detail.disposition
                          ] ?? CLASSIFICATION[record.classification]
                        }`}</wa-option
                      >`,
                  )}
                </wa-select>
                <button ${offered("lf-btn lf-vr-previous")}>Previous</button>
                <button ${offered("lf-btn lf-vr-next")}>Next</button>
              </nav>
            </header>
            <div class="lf-vr-cases">
              ${
                run
                  ? repeat(
                      cases,
                      (record) => record.id,
                      (record, index) =>
                        this.#caseView(record, index, cases.length, remaining),
                    )
                  : html`<p class="lf-vr-empty" data-lf-gen="1" data-lf-said>
                      Waiting for visual-run data.
                    </p> `
              }
            </div>
          </section>`,
        this,
      );
      const bodyChanged = this.#casesBody !== this.querySelector(".lf-vr-cases");
      this.#evidenceHost = this.querySelector(".lf-vr-evidence-region");
      this.#casesBody = this.querySelector(".lf-vr-cases");
      if (bodyChanged && this.#sizes) this.#bindEvidence();
      else this.#observeSelected();
      return true;
    }

    // Only a source commit changes datum membership or provenance. Inspection and
    // difference painters keep those seats and never invalidate document semantics.
    #project() {
      const cases = this.#run?.cases ?? [];
      projectData(
        this,
        this.#run
          ? cases.map((record, index) => ({
              node: this.#caseEntries.get(record.id).article,
              key: record.id,
              identity: record.id,
              label: `Case ${index + 1}: ${record.title}`,
              origin: { ...this.#snapshot.origin, path: ["cases", index] },
            }))
          : [
              {
                key: "unavailable",
                node: this.querySelector(".lf-vr-empty"),
                label: "Visual run unavailable",
              },
            ],
        { snapshot: this.#snapshot },
      );
    }

    // x-thread-surface: Leaf asks for one outlet, or null, per target it hands over.
    threadOutlets(targets) {
      return targets.map((target) => this.#threadOutlet(target));
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
      this.#reviewUnits = state?.review?.units ?? {};
      this.#paintReview();
      return true;
    }
  },
);
