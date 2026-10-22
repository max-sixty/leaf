/* A visual review is a queue of claims, with one readable comparison open.
 * The source owns cases and captures; Leaf owns approvals and discussion. The
 * dashboard derives its queue and counts from that state. Selection
 * and inspection are transient view choices. Retained articles preserve their
 * controls and thread outlets; canonical reading regions preserve capture positions. */
import "/widgets/lf-shot.js";
import {
  LeafElement,
  html,
  nothing,
  repeat,
  keyed,
  ref,
  live,
  offered,
  commands,
  paintKeys,
  holdFocus,
  focused,
  scrollIntoView,
  focusDestination,
  readThreads,
  threadActions,
  threadSummary,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  projectData,
  releaseOutlets,
  threadSurface,
  scopedMediaUrl,
  describeDifference,
  frameFor,
  sizeObserver,
  whileConnected,
  layoutChanged,
  keeps,
  registerReadingRegion,
  compoundReadingRegionId,
  preserveReadingRegions,
} from "/runtime/widget-api.js";

const MODES = { compare: "Before & after", flip: "Slider" };
const READABLE_SCALE = 0.7;
const fact = (name, value) =>
  html`<div>
    <dt data-lf-gen="1" data-lf-said>${name}</dt>
    <dd data-lf-gen="1" data-lf-said>${value}</dd>
  </div>`;
const destination = (target, path) => {
  if (!target.url) return null;
  const base = new URL(target.url);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path.replace(/^\/+/, ""), base).href;
};

customElements.define(
  "lf-visual-review",
  class extends LeafElement {
    static answerWords(value) {
      return value.approved ? "Looks right" : "Unchecked";
    }

    #entries = new Map();
    #snapshot;
    #projected;
    #sizes;
    #selected;
    #restoreFocus;
    #queue;
    #placeQueue = (body) => {
      if (!body || this.#queue === body) return;
      this.#queue = body;
      this.#readingRegion(body, "queue");
    };
    #readingRegion(body, key) {
      whileConnected(body, () =>
        registerReadingRegion({
          id: compoundReadingRegionId(this, key),
          host: body.parentElement,
          body,
        }),
      );
    }
    #fit = frameFor(this, () => {
      const entry = this.#entries.get(this.#selected);
      if (entry) this.#inspect(entry);
      layoutChanged(this);
    });
    #presentShot = (promise) => this.controller.present(promise);

    setup() {
      const selectedControl = (selector) => () =>
        this.#entries.get(this.#selected)?.article.querySelector(selector);
      commands(this, "In a visual review", [
        {
          id: "visual.next-case",
          title: "Next case",
          keys: ["n"],
          when: () => this.#entries.size > 1,
          run: () => this.#step(1),
        },
        {
          id: "visual.previous-case",
          title: "Previous case",
          keys: ["Shift+n"],
          when: () => this.#entries.size > 1,
          run: () => this.#step(-1),
        },
        {
          id: "visual.approve",
          title: "Toggle Looks right",
          keys: ["a"],
          decision: true,
          control: selectedControl(".lf-vr-approval-input"),
          when: () =>
            Boolean(this.#selected) && this.controller.read().actions.review.available,
          run: () =>
            this.#review(
              this.#entries.get(this.#selected).record,
              !this.#approved(this.#selected),
            ),
        },
        {
          id: "visual.feedback",
          title: "Add feedback",
          keys: ["c"],
          control: selectedControl(".lf-vr-feedback"),
          when: () => Boolean(this.#selected),
          run: () =>
            threadSurface(this).open(this.#entries.get(this.#selected).article),
        },
        {
          id: "visual.inspection",
          title: "More inspection",
          keys: ["i"],
          control: selectedControl(".lf-vr-inspect"),
          when: () => Boolean(this.#selected),
          run: () => this.#inspection(),
        },
        {
          id: "visual.next-remaining",
          title: "Next unchecked case",
          keys: [],
          control: selectedControl(".lf-vr-next"),
          when: () => Boolean(this.#nextUnchecked()),
          run: () => this.#select(this.#nextUnchecked().id, true),
        },
      ]);
      whileConnected(this, (signal) => {
        this.addEventListener(
          "lf-reveal",
          (event) => {
            const { target, mayReveal, present, replacedView } = event.detail;
            if (!mayReveal()) return;
            const entry = [...this.#entries.values()].find((item) =>
              item.article?.contains(target),
            );
            if (!entry || entry.record.id === this.#selected) return;
            replacedView();
            present(this.#select(entry.record.id));
          },
          { signal },
        );
        this.#sizes = sizeObserver(this.#fit);
        this.#sizes.observe(this);
        this.#fit();
        return () => {
          this.#sizes.disconnect();
          this.#sizes = null;
        };
      });
    }

    #reconcile(snapshot) {
      const records = snapshot?.value.cases ?? [];
      const ids = new Set(records.map((record) => record.id));
      for (const [id, entry] of this.#entries) {
        if (ids.has(id)) continue;
        if (entry.article) releaseOutlets(entry.article);
        this.#entries.delete(id);
      }
      this.#restoreFocus = holdFocus(this);
      for (const record of records) {
        let entry = this.#entries.get(record.id);
        if (!entry) {
          entry = { mode: "compare", full: false, actual: false };
          entry.place = (article) => {
            entry.article = article;
          };
          entry.capturePlace = (body) => {
            if (!body || entry.body === body) return;
            entry.body = body;
            this.#readingRegion(body, `case-${record.id}`);
          };
          entry.threadPlace = (body) => {
            if (!body || entry.threads === body) return;
            entry.threads = body;
            this.#readingRegion(body, `discussion-${record.id}`);
          };
          entry.prepare = (shot) => {
            entry.shot = shot;
            if (!shot) return;
            shot.inspect({
              mode: entry.mode,
              pixelRatio: entry.record.capture.deviceScaleFactor,
              captureWidth: entry.record.capture.viewport.width,
              focus: entry.record.focus,
              crop: !entry.full,
              labels: { before: "Before", after: "After" },
            });
            this.#fit();
            shot.difference.then(
              (reading) => {
                if (entry.shot !== shot || this.#entries.get(record.id) !== entry)
                  return;
                entry.difference = reading;
                this.requestUpdate();
              },
              () => {},
            );
          };
          this.#entries.set(record.id, entry);
        }
        const before = scopedMediaUrl(record.before);
        const after = scopedMediaUrl(record.after);
        const imageKey = `${before}\n${after}`;
        if (entry.imageKey !== imageKey) entry.difference = null;
        Object.assign(entry, { record, before, after, imageKey });
      }
      if (!ids.has(this.#selected))
        this.#selected = (
          records.find((record) => record.classification !== "clean") ?? records[0]
        )?.id;
      this.#snapshot = snapshot;
    }

    #approved(id) {
      return this.state?.review?.units?.[id]?.detail.approved === true;
    }
    #step(delta) {
      const ids = this.#snapshot.value.cases.map((record) => record.id);
      this.#select(
        ids[(ids.indexOf(this.#selected) + delta + ids.length) % ids.length],
        true,
      );
    }
    #inspection() {
      const article = this.#entries.get(this.#selected)?.article;
      const popup = article?.querySelector(".lf-vr-details");
      if (isNativeLayer(popup)) closeNativeLayer(popup);
      else {
        const source = article.querySelector(".lf-vr-inspect");
        focusDestination(source, "press");
        showNativeLayer(popup, { source });
        focusDestination(popup.querySelector("button"), "move");
      }
    }
    #select(id, land = false) {
      if (!this.#entries.has(id)) return;
      const previous = this.#entries.get(this.#selected)?.article;
      const active = focused();
      const leaveHiddenControl = previous?.contains(active);
      for (const popup of previous?.querySelectorAll("[popover]") ?? []) {
        if (isNativeLayer(popup)) closeNativeLayer(popup);
      }
      return preserveReadingRegions(this, () => {
        this.#selected = id;
        this.requestUpdate();
        this.performUpdate();
        const queueButton = this.#queue?.querySelector('[aria-current="true"]');
        if (queueButton)
          scrollIntoView(queueButton, { block: "nearest", behavior: "instant" });
        if (land || leaveHiddenControl) {
          const heading = this.#entries.get(id).article.querySelector(".lf-vr-title");
          focusDestination(heading, "move");
          scrollIntoView(heading, { block: "nearest", behavior: "instant" });
        }
        return this.updateComplete;
      });
    }
    #nextUnchecked() {
      const records = this.#snapshot?.value.cases ?? [];
      const index = records.findIndex((record) => record.id === this.#selected);
      return [...records.slice(index + 1), ...records.slice(0, index)].find(
        (record) => !this.#approved(record.id),
      );
    }

    render() {
      const snapshot = this.data("run");
      if (snapshot !== this.#snapshot) this.#reconcile(snapshot);
      const run = snapshot?.value;
      if (!run)
        return html`<p class="lf-vr-empty" data-lf-gen="1" data-lf-said>
          Waiting for visual evidence.
        </p>`;
      const approvedCount = run.cases.filter((record) =>
        this.#approved(record.id),
      ).length;

      const available = this.reading.actions.review.available;
      return html`<div class="lf-vr-dashboard">
        <header class="lf-vr-heading">
          <h2 data-lf-gen="1" data-lf-said>${run.title}</h2>
          <div class="lf-vr-progress" role="status" aria-live="polite">
            <span data-lf-gen="1" data-lf-said
              ><strong>${approvedCount}</strong> of ${run.cases.length} look right</span
            >
          </div>
        </header>
        <div class="lf-vr-workspace">
          <nav
            class="lf-vr-queue"
            aria-label="Review cases"
            data-lf-reading-role="pane"
            data-lf-generated
          >
            <div class="lf-vr-case-list" ${ref(this.#placeQueue)}>
              ${repeat(
                run.cases,
                (record) => record.id,
                (record) => {
                  const approved = this.#approved(record.id);
                  return html`<button
                    type="button"
                    ${offered("lf-vr-case-button")}
                    aria-current=${record.id === this.#selected ? "true" : nothing}
                    aria-controls=${`${this.id}-${record.id}`}
                    @click=${() => this.#select(record.id)}
                  >
                    <span class="lf-vr-case-number" aria-hidden="true"
                      >${String(run.cases.indexOf(record) + 1).padStart(2, "0")}</span
                    >
                    <span class="lf-vr-case-label"
                      ><span class="lf-vr-case-name">${record.title}</span>
                      <span class="lf-vr-case-status" data-approved=${String(approved)}
                        >${approved ? "Looks right" : "Unchecked"}</span
                      ></span
                    >
                  </button>`;
                },
              )}
            </div>
          </nav>
          <div class="lf-vr-detail">
            ${repeat(
              run.cases,
              (record) => record.id,
              (record) =>
                this.#case(
                  this.#entries.get(record.id),
                  this.#approved(record.id),
                  available,
                ),
            )}
          </div>
        </div>
      </div>`;
    }

    updated(changed) {
      super.updated(changed);
      this.classList.toggle("lf-rendered", Boolean(this.#snapshot));
      if (this.#snapshot !== this.#projected) {
        projectData(
          this,
          (this.#snapshot?.value.cases ?? []).map((record, index) => ({
            node: this.#entries.get(record.id).article,
            key: record.id,
            identity: record.id,
            label: record.title,
            origin: { ...this.#snapshot.origin, path: ["cases", index] },
          })),
          { snapshot: this.#snapshot ?? null },
        );
        this.#projected = this.#snapshot;
      }
      threadSurface(this).update();
      this.#restoreFocus?.(() => {
        const heading = this.#entries
          .get(this.#selected)
          ?.article.querySelector(".lf-vr-title");
        if (!heading) return false;
        focusDestination(heading, "return");
        return true;
      });
      this.#restoreFocus = null;
      paintKeys();
      this.#fit();
    }

    #inspect(entry) {
      const { shot, record } = entry;
      if (!shot || record.id !== this.#selected) return;
      shot.inspect({
        mode: entry.mode,
        pixelRatio: record.capture.deviceScaleFactor,
        captureWidth: record.capture.viewport.width,
        focus: record.focus,
        crop: !entry.full,
        labels: { before: "Before", after: "After" },
      });
      const geometry = shot.captureGeometry;
      const stage = shot.parentElement;
      const stageWidth = stage?.clientWidth;
      if (geometry?.images.length !== 2 || !stageWidth) return;
      const crop = record.focus && !entry.full && shot.supportsCrop;
      const width = crop
        ? record.focus.width
        : geometry.images[0].width / record.capture.deviceScaleFactor ||
          record.capture.viewport.width;
      if (!width) return;
      const border = geometry.frameBorder * 2;
      const sideScale = (stageWidth - geometry.gap - 2 * border) / (2 * width);
      const layout = sideScale >= READABLE_SCALE ? "side" : "stack";
      const fit =
        entry.mode === "compare" && layout === "side"
          ? sideScale
          : (stageWidth - border) / width;
      const scale = entry.actual ? 1 : Math.max(READABLE_SCALE, Math.min(1, fit));
      shot.inspect({ layout, scale });
      const frameWidth = width * scale + border;
      const contentWidth =
        entry.mode === "compare" && layout === "side"
          ? 2 * frameWidth + geometry.gap
          : frameWidth;
      const overflowing = contentWidth > stageWidth + 1;
      const hint = stage.parentElement.querySelector(".lf-vr-pan-hint");
      keeps(hint, "hidden", overflowing ? null : "");
      const order =
        entry.mode === "compare"
          ? layout === "side"
            ? "Before left · After right. "
            : "Before above · After below. "
          : "";
      const hintText = `${order}Scroll sideways to inspect the full capture`;
      if (hint.textContent !== hintText) hint.textContent = hintText;
      keeps(
        stage,
        "aria-label",
        overflowing ? "Capture comparison; scroll horizontally" : null,
      );
    }

    #change(entry, key, value) {
      entry[key] = value;
      this.requestUpdate();
      this.performUpdate();
      this.#inspect(entry);
    }

    #review(record, approved) {
      if (!this.controller.read().actions.review.available) return;
      this.controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { case: record.id, approved },
        says: approved ? "Looks right" : "Approval removed",
      });
    }

    #case(entry, approved, available) {
      const { record, before, after, imageKey } = entry;
      const run = this.#snapshot.value;
      const threads = readThreads().threads.filter(
        (thread) =>
          thread.anchor?.section === this.id && thread.anchor.datum === record.id,
      );
      const link = (label, href) =>
        href
          ? html`<a
              ${offered("lf-vr-source")}
              href=${href}
              target="_blank"
              rel="noopener noreferrer"
              >${label}</a
            >`
          : nothing;
      return html`<article
        class="lf-vr-case"
        id=${`${this.id}-${record.id}`}
        aria-hidden=${record.id !== this.#selected ? "true" : "false"}
        ?inert=${record.id !== this.#selected}
        ${ref(entry.place)}
      >
        <div class="lf-vr-caption">
          <h3 class="lf-vr-title" data-lf-gen="1" data-lf-said>${record.title}</h3>
        </div>
        <div class="lf-vr-decision">
          <div class="lf-vr-review-actions">
            <label class="lf-vr-approval"
              ><input
                ${offered("lf-vr-approval-input")}
                type="checkbox"
                ?disabled=${!available}
                .checked=${live(approved)}
                @change=${(event) => this.#review(record, event.currentTarget.checked)}
              />Looks right</label
            >
            <button
              type="button"
              ${offered("lf-btn lf-quiet-action lf-compact-control lf-vr-feedback")}
            >
              Add feedback
            </button>
            ${
              threads.length
                ? html`<button
                      type="button"
                      ${offered(
                        "lf-btn lf-quiet-action lf-compact-control lf-vr-open-threads",
                      )}
                      popovertarget=${`${this.id}-${record.id}-threads`}
                    >
                      ${threads.length} ${threads.length === 1 ? "thread" : "threads"}
                    </button>
                    <div
                      class="lf-vr-thread-list"
                      id=${`${this.id}-${record.id}-threads`}
                      popover
                    >
                      <header class="lf-vr-inspection-heading">
                        <h4>Threads on this case</h4>
                        <button
                          type="button"
                          ${offered("lf-btn lf-quiet-action lf-compact-control")}
                          popovertarget=${`${this.id}-${record.id}-threads`}
                          popovertargetaction="hide"
                        >
                          Close
                        </button>
                      </header>
                      ${repeat(
                        threads,
                        (thread) => thread.key,
                        (thread) =>
                          html`<button
                            type="button"
                            ${offered("lf-btn lf-quiet-action lf-vr-thread-link")}
                            @click=${(event) => {
                              closeNativeLayer(
                                event.currentTarget.closest("[popover]"),
                              );
                              threadActions.open(thread.key, {
                                part: "thread",
                                travel: false,
                              });
                            }}
                          >
                            ${threadSummary(thread).topic}${
                              thread.resolved ? " · Resolved" : ""
                            }
                          </button>`,
                      )}
                    </div>`
                : nothing
            }
          </div>
          <button
            type="button"
            ${offered("lf-btn lf-quiet-action lf-compact-control lf-vr-next")}
          >
            Next unchecked <span aria-hidden="true">→</span>
          </button>
        </div>
        <div class="lf-vr-tools">
          <div class="lf-vr-view" role="group" aria-label="Comparison view">
            ${Object.entries(MODES).map(
              ([value, text]) =>
                html`<button
                  type="button"
                  ${offered(
                    "lf-btn lf-quiet-action lf-compact-control lf-vr-mode-button",
                  )}
                  aria-pressed=${entry.mode === value ? "true" : "false"}
                  @click=${() => this.#change(entry, "mode", value)}
                >
                  ${text}
                </button>`,
            )}
          </div>
          <button
            type="button"
            ${offered("lf-btn lf-quiet-action lf-compact-control lf-vr-inspect")}
            aria-controls=${`${this.id}-${record.id}-inspection`}
          >
            More inspection
          </button>
          <div class="lf-vr-details" id=${`${this.id}-${record.id}-inspection`} popover>
            <header class="lf-vr-inspection-heading">
              <h4>Inspection settings</h4>
              <button
                type="button"
                ${offered(
                  "lf-btn lf-quiet-action lf-compact-control lf-vr-inspection-close",
                )}
                popovertarget=${`${this.id}-${record.id}-inspection`}
                popovertargetaction="hide"
                aria-label="Close inspection"
              >
                Close
              </button>
            </header>
            <div class="lf-vr-inspection">
              ${
                record.focus
                  ? html`<label
                      ><input
                        ${offered("lf-vr-full")}
                        type="checkbox"
                        .checked=${live(entry.full)}
                        @change=${(event) =>
                          this.#change(entry, "full", event.currentTarget.checked)}
                      />Full frame</label
                    >`
                  : nothing
              }
              <label
                ><input
                  ${offered("lf-vr-actual")}
                  type="checkbox"
                  .checked=${live(entry.actual)}
                  @change=${(event) =>
                    this.#change(entry, "actual", event.currentTarget.checked)}
                />Actual size</label
              >
            </div>
            <dl class="lf-vr-provenance">
              ${fact(
                "Capture",
                `${record.capture.viewport.width} × ${record.capture.viewport.height} · ${record.capture.deviceScaleFactor}× · ${record.capture.colorScheme}`,
              )}
              ${fact(
                "Browser",
                `${record.capture.browser} ${record.capture.browserVersion}`,
              )}
              ${fact("Observed", record.capture.observedAt)}${fact(
                "Locale",
                `${record.capture.locale} · ${record.capture.timezone}`,
              )}
              ${fact("Path", record.path)}${fact(
                "Before revision",
                run.base.revision,
              )}${fact("After revision", run.candidate.revision)}
              ${
                record.focus
                  ? fact(
                      "Focus",
                      `${record.focus.x}, ${record.focus.y} · ${record.focus.width} × ${record.focus.height} CSS px`,
                    )
                  : nothing
              }
              ${
                entry.difference
                  ? fact("Full-frame difference", describeDifference(entry.difference))
                  : nothing
              }
            </dl>
            <div class="lf-vr-sources">
              ${link("Open before page", destination(run.base, record.path))}${link(
                "Open after page",
                destination(run.candidate, record.path),
              )}${link("Capture trace", record.traceUrl)}
            </div>
          </div>
        </div>
        <div class="lf-vr-evidence" data-lf-reading-role="pane" data-lf-generated>
          <header>
            <p class="lf-vr-evidence-note" data-lf-gen="1" data-lf-said>
              Captured screenshots · ${record.capture.viewport.width} ×
              ${record.capture.viewport.height} · ${record.capture.browser}. Links
              inside these images are not interactive.
            </p>
            <p class="lf-vr-pan-hint" data-lf-gen="1" data-lf-said hidden>
              Scroll sideways to inspect the full capture
            </p>
          </header>
          <div class="lf-vr-capture" ${ref(entry.capturePlace)}>
            ${keyed(
              imageKey,
              html`<lf-shot
                id=${`${this.id}-${record.id}-capture`}
                before=${before}
                after=${after}
                alt=${`${record.title}. ${record.result}`}
                outlines
                ._lfPresentGenerated=${this.#presentShot}
                ${ref(entry.prepare)}
                @captureload=${this.#fit}
              ></lf-shot>`,
            )}
            <div class="lf-vr-claim">
              <p class="lf-vr-result" data-lf-gen="1" data-lf-said>${record.result}</p>
              <p class="lf-vr-action" data-lf-gen="1" data-lf-said>
                <strong>Check:</strong> ${record.action}
              </p>
            </div>
          </div>
        </div>
        <section
          class="lf-vr-discussion"
          data-lf-reading-role="pane"
          data-lf-generated
          aria-label="Threads on this visual case"
        >
          <div
            class="lf-vr-threads lf-ui"
            data-lf-gen="1"
            ${ref(entry.threadPlace)}
          ></div>
        </section>
      </article>`;
    }

    threadOutlets(targets) {
      return targets.map(({ anchor, placement }) => {
        const article = this.#entries.get(anchor.datum)?.article;
        return article &&
          anchor.datum === this.#selected &&
          placement.datumElement === article
          ? article.querySelector(".lf-vr-threads")
          : null;
      });
    }
  },
);
