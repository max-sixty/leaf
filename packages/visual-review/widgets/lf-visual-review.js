/* A visual review is a queue of claims, with one readable comparison open.
 * The source owns cases and captures; Leaf owns approvals and discussion. The
 * dashboard derives its queue and counts from that state. Selection
 * is transient. lf-shot owns comparison controls, layout and capture scrolling;
 * the dashboard supplies capture metadata and retains case articles and threads.
 * A case's header names only the capture size and browser, with Capture details
 * holding the rest: on 2026-10-26 the user chose this over a line that also said the
 * images were captured screenshots whose links don't work, which they show
 * themselves. */
import "/widgets/lf-shot.js";
/** @typedef {import("/widgets/lf-shot.js").Shot} Shot */
import {
  LeafElement,
  html,
  nothing,
  repeat,
  ref,
  generatedElement,
  render,
  live,
  generated,
  offered,
  offeredAction,
  cycledRow,
  beginWalk,
  listWalkPosition,
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
  keeps,
  releaseOutlets,
  threadSurface,
  scopedMediaUrl,
  whileConnected,
  registerReadingRegion,
  compoundReadingRegionId,
  preserveReadingRegions,
  commandsChanged,
  iconTemplate,
} from "/runtime/widget-api.js";

/** @typedef {import("../../../browser/types/contract.js").DataVisualRun} VisualRun */
/** @typedef {import("../../../browser/types/contract.js").DataVisualRunCase} VisualCase */
/** @typedef {import("../../../browser/types/contract.js").DataVisualRunTarget} VisualTarget */
/** @typedef {{record: VisualCase, article: HTMLElement, threads: HTMLElement, shot: Shot, before: string, after: string, difference: import("../../default/widgets/lf-shot.js").DescribedDifference | null, pendingDifference: Shot["difference"] | null, controls: () => ReturnType<typeof readCaseControls>}} VisualEntry */
/** @param {HTMLElement} article */
function readCaseControls(article) {
  /** @type {HTMLElement | null} */
  const popup = article.querySelector(".lf-vr-details");
  /** @type {HTMLButtonElement | null} */
  const source = article.querySelector(".lf-vr-inspect");
  /** @type {HTMLElement | null} */
  const heading = article.querySelector(".lf-vr-title");
  const close = popup?.querySelector("button");
  if (!popup || !source || !heading || !close)
    throw new Error("Visual case controls did not render");
  return { popup, source, heading, close };
}

// A popover's way out wears the face of every surface's close control in Leaf: the
// cross, named for what it closes (runtime/widget-elements.js, `closeControl`).
/** @param {string} popover @param {string} name */
const closeButton = (popover, name) =>
  html`<button
    ${offeredAction("symbol", "", name, { title: `${name} (Esc)`, action: "close" })}
    popovertarget=${popover}
    popovertargetaction="hide"
  ></button>`;
/** @param {string} name @param {string | number} value */
const fact = (name, value) =>
  html`<div>
    <dt ${generated({ says: true })}>${name}</dt>
    <dd ${generated({ says: true })}>${value}</dd>
  </div>`;
/** @param {VisualTarget} target @param {string} path */
const destination = (target, path) => {
  if (!target.url) return null;
  const base = new URL(target.url);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path.replace(/^\/+/, ""), base).href;
};

customElements.define(
  "lf-visual-review",
  class extends LeafElement {
    /** @param {unknown} value */
    static answerWords(value) {
      return value !== null &&
        typeof value === "object" &&
        "approved" in value &&
        value.approved === true
        ? "Looks right"
        : "Unchecked";
    }

    // The run, set by whoever hosts the widget: Leaf from the bound source (the
    // registry's `x-data.run.property`), or null while that source has none.
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      /** @type {import("../../../browser/types/contract.js").DataVisualRun | null} */
      this.value = null;
    }

    /** @type {Map<string, VisualEntry>} */
    #entries = new Map();
    /** @type {VisualEntry[]} */
    #cases = [];
    // The run the last render reconciled, and the one whose cases were last marked.
    /** @type {import("../../../browser/types/contract.js").DataVisualRun | null | undefined} */
    #run;
    /** @type {import("../../../browser/types/contract.js").DataVisualRun | null | undefined} */
    #marked;
    /** @type {VisualEntry | null} */
    #selected = null;
    /** @type {ReturnType<typeof holdFocus> | null} */
    #restoreFocus = null;
    /** @type {Element | undefined} */
    #queue;
    #placeQueue = (/** @type {Element | undefined} */ body) => {
      if (!body || this.#queue === body) return;
      this.#queue = body;
      this.#readingRegion(body, "queue");
    };
    /** @param {Element} body @param {string} key */
    #readingRegion(body, key) {
      whileConnected(body, () => {
        const host = body.parentElement;
        if (!host) throw new Error("Visual review region needs its containing pane");
        return registerReadingRegion({
          id: compoundReadingRegionId(this, key),
          host,
          body,
        });
      });
    }
    #presentShot = (/** @type {Promise<unknown>} */ promise) =>
      this.controller.present(promise);

    setup() {
      /** @param {string} selector */
      const selectedControl = (selector) => () =>
        this.#selected?.article.querySelector(selector) ?? null;
      this.lfCommands = {
        title: "In a visual review",
        rows: [
          {
            id: "visual.next-case",
            title: "Next case",
            travels: true,
            keys: ["n"],
            when: () => this.#entries.size > 1,
            run: () => this.#step(1),
          },
          {
            id: "visual.previous-case",
            title: "Previous case",
            travels: true,
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
              Boolean(
                this.#selected && this.controller.read().actions.review?.available,
              ),
            run: () => {
              const selected = this.#selected;
              if (selected)
                this.#review(selected.record, !this.#approved(selected.record.id));
            },
          },
          {
            id: "visual.feedback",
            title: "Add feedback",
            keys: ["c"],
            control: selectedControl(".lf-vr-feedback"),
            when: () => Boolean(this.#selected),
            run: () => {
              if (this.#selected) threadSurface(this).open(this.#selected.article);
            },
          },
          {
            id: "visual.inspection",
            title: "Capture details",
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
            run: () => this.#select(this.#nextUnchecked()?.id, true),
          },
        ],
      };
      commandsChanged(this);
    }

    /** @param {import("../../../browser/types/contract.js").DataVisualRun | null} run */
    #reconcile(run) {
      const records = run?.cases ?? [];
      const ids = new Set(records.map((record) => record.id));
      for (const [id, entry] of this.#entries) {
        if (ids.has(id)) continue;
        if (entry.article) releaseOutlets(entry.article);
        this.#entries.delete(id);
      }
      this.#restoreFocus = holdFocus(this);
      this.#cases = records.map((record) => {
        let entry = this.#entries.get(record.id);
        const before = scopedMediaUrl(record.before),
          after = scopedMediaUrl(record.after);
        if (!entry) {
          const article = document.createElement("article");
          article.className = "lf-vr-case";
          article.id = `${this.id}-${record.id}`;
          article.addEventListener("beforematch", (event) => {
            if (event.target === event.currentTarget) this.#select(record.id);
          });
          const threads = document.createElement("div");
          threads.className = "lf-vr-threads lf-ui";
          generatedElement(threads, { says: false });
          this.#readingRegion(threads, `discussion-${record.id}`);
          const shot = document.createElement("lf-shot");
          shot.id = `${this.id}-${record.id}-capture`;
          shot._lfPresentGenerated = this.#presentShot;
          /** @type {ReturnType<typeof readCaseControls> | undefined} */
          let controls;
          entry = {
            record,
            article,
            threads,
            shot,
            before,
            after,
            difference: null,
            pendingDifference: null,
            controls: () => (controls ??= readCaseControls(article)),
          };
          this.#entries.set(record.id, entry);
        }
        if (entry.before !== before || entry.after !== after) entry.difference = null;
        Object.assign(entry, { record, before, after });
        return entry;
      });
      if (!this.#selected || !ids.has(this.#selected.record.id))
        this.#selected =
          this.#cases.find(({ record }) => record.classification !== "clean") ??
          this.#cases[0] ??
          null;
      this.#run = run;
    }

    /** @param {string} id */
    #approved(id) {
      const review = this.state?.review;
      return Boolean(
        review && "units" in review && review.units[id]?.detail.approved === true,
      );
    }
    // n and Shift+n walk the cases, coming round at either end, and say where the
    // landing stands among them as every walk does.
    /** @param {-1 | 1} delta */
    #step(delta) {
      const ids = () => this.#cases.map(({ record }) => record.id);
      this.#select(cycledRow(ids(), this.#selected?.record.id, delta), true);
      beginWalk("visual-case", "Case", () =>
        listWalkPosition(ids(), this.#selected?.record.id),
      );
    }
    #inspection() {
      if (!this.#selected) return;
      const { popup, source, close } = this.#selected.controls();
      if (isNativeLayer(popup)) closeNativeLayer(popup);
      else {
        focusDestination(source, "press");
        showNativeLayer(popup, { source });
        focusDestination(close, "move");
      }
    }
    /** @param {string | undefined} id @param {boolean} [land] */
    #select(id, land = false) {
      const selected = id ? this.#entries.get(id) : undefined;
      if (!selected) return;
      const previous = this.#selected?.article;
      const active = focused();
      const leaveHiddenControl = previous?.contains(active);
      /** @type {NodeListOf<HTMLDivElement> | undefined} */
      const popups = previous?.querySelectorAll("div[popover]");
      for (const popup of popups ?? []) {
        if (isNativeLayer(popup)) closeNativeLayer(popup);
      }
      return preserveReadingRegions(this, () => {
        this.#selected = selected;
        this.requestUpdate();
        this.performUpdate();
        const queueButton = this.#queue?.querySelector('[aria-current="true"]');
        if (queueButton)
          scrollIntoView(queueButton, { block: "nearest", behavior: "instant" });
        if (land || leaveHiddenControl) {
          const { heading } = selected.controls();
          focusDestination(heading, "move");
          scrollIntoView(heading, { block: "nearest", behavior: "instant" });
        }
        return this.updateComplete;
      });
    }
    #nextUnchecked() {
      const records = this.#run?.cases ?? [];
      const index = records.findIndex(
        (record) => record.id === this.#selected?.record.id,
      );
      return [...records.slice(index + 1), ...records.slice(0, index)].find(
        (record) => !this.#approved(record.id),
      );
    }

    render() {
      const run = this.value;
      if (run !== this.#run) this.#reconcile(run);
      if (!run)
        return html`<p class="lf-vr-empty" ${generated({ says: true })}>
          Waiting for visual evidence.
        </p>`;
      const approvedCount = run.cases.filter((record) =>
        this.#approved(record.id),
      ).length;

      const available = Boolean(this.reading?.actions.review?.available);
      return html`<div class="lf-vr-dashboard">
        <header class="lf-vr-heading">
          <h2 ${generated({ says: true })}>${run.title}</h2>
          <div class="lf-vr-progress" role="status" aria-live="polite">
            <span ${generated({ says: true })}
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
                this.#cases,
                ({ record }) => record.id,
                ({ record }) => {
                  const approved = this.#approved(record.id);
                  return html`<button
                    type="button"
                    ${offeredAction("row", "lf-vr-case-button")}
                    aria-current=${record.id === this.#selected?.record.id ? "true" : nothing}
                    aria-controls=${`${this.id}-${record.id}`}
                    @click=${() => this.#select(record.id)}
                  >
                    <span class="lf-vr-case-number lf-row-lead" aria-hidden="true"
                      >${run.cases.indexOf(record) + 1}</span
                    ><span class="lf-row-main">${record.title}</span
                    ><span
                      class="lf-vr-case-status lf-row-end"
                      data-approved=${String(approved)}
                      >${iconTemplate("check")}<span class="lf-quiet"
                        >Looks right</span
                      ></span
                    >
                  </button>`;
                },
              )}
            </div>
          </nav>
          <div class="lf-vr-detail">
            ${repeat(
              this.#cases,
              ({ record }) => record.id,
              (entry) =>
                this.#case(entry, this.#approved(entry.record.id), available, run),
            )}
          </div>
        </div>
      </div>`;
    }

    /** @param {import("lit").PropertyValues} changed */
    updated(changed) {
      super.updated(changed);
      this.classList.toggle("lf-rendered", Boolean(this.#run));
      if (this.#run !== this.#marked) {
        // Each case's article is a datum on a Leaf page (`module-state.md`, "Marking
        // drawn data"), following its case by id across runs.
        for (const [index, { record, article }] of this.#cases.entries()) {
          keeps(article, "data-lf-datum", record.id);
          keeps(article, "data-lf-identity", record.id);
          keeps(article, "data-lf-datum-label", record.title);
          keeps(article, "data-lf-origin-path", JSON.stringify(["cases", index]));
        }
        this.dispatchEvent(new CustomEvent("drawn", { detail: { value: this.#run } }));
        for (const entry of this.#entries.values()) {
          const { shot, record } = entry;
          shot?.inspect({
            pixelRatio: record.capture.deviceScaleFactor,
            captureWidth: record.capture.viewport.width,
            focus: record.focus,
          });
          if (!shot || entry.pendingDifference === shot.difference) continue;
          const pending = shot.difference;
          entry.pendingDifference = pending;
          pending.then(
            (reading) => {
              if (
                entry.pendingDifference !== pending ||
                this.#entries.get(record.id) !== entry
              )
                return;
              entry.difference = reading;
              this.requestUpdate();
            },
            () => {},
          );
        }
        this.#marked = this.#run;
      }
      threadSurface(this).update();
      this.#restoreFocus?.(() => {
        const heading = this.#selected?.controls().heading;
        if (!heading) return false;
        focusDestination(heading, "return");
        return true;
      });
      this.#restoreFocus = null;
      commandsChanged(this);
    }

    /** @param {VisualCase} record @param {boolean} approved */
    #review(record, approved) {
      if (!this.controller.read().actions.review?.available) return;
      this.controller.dispatch({
        kind: "action",
        verb: "review",
        detail: { case: record.id, approved },
        says: approved ? "Looks right" : "Approval removed",
      });
    }

    /** @param {VisualEntry} entry @param {boolean} approved @param {boolean} available @param {VisualRun} run */
    #case(entry, approved, available, run) {
      const { record, before, after } = entry;
      keeps(
        entry.article,
        "hidden",
        record.id !== this.#selected?.record.id ? "until-found" : null,
      );
      keeps(
        entry.article,
        "inert",
        record.id !== this.#selected?.record.id ? "" : null,
      );
      keeps(entry.shot, "before", before);
      keeps(entry.shot, "after", after);
      keeps(entry.shot, "alt", `${record.title}. ${record.result}`);
      const threads = readThreads().threads.filter(
        (thread) =>
          thread.anchor?.section === this.id && thread.anchor.datum === record.id,
      );
      /** @param {string} label @param {string | null | undefined} href */
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
      render(
        html` <div class="lf-vr-caption">
            <h3 class="lf-vr-title" ${generated({ says: true })}>${record.title}</h3>
          </div>
          <div class="lf-vr-decision">
            <div class="lf-vr-review-actions">
              <label class="lf-vr-approval"
                ><input
                  ${offered("lf-vr-approval-input")}
                  type="checkbox"
                  ?disabled=${!available}
                  .checked=${live(approved)}
                  @change=${(/** @type {Event} */ event) => event.currentTarget instanceof HTMLInputElement && this.#review(record, event.currentTarget.checked)}
                />Looks right</label
              >
              <button ${offeredAction("word", "lf-vr-feedback")}>Add feedback</button>
              ${
                threads.length
                  ? html`<button
                        ${offeredAction("word", "lf-vr-open-threads")}
                        popovertarget=${`${this.id}-${record.id}-threads`}
                      >
                        ${threads.length} ${threads.length === 1 ? "thread" : "threads"}
                      </button>
                      <div
                        class="lf-vr-thread-list scroll"
                        id=${`${this.id}-${record.id}-threads`}
                        popover
                      >
                        <header class="lf-vr-inspection-heading">
                          <h4>Threads on this case</h4>
                          ${closeButton(
                            `${this.id}-${record.id}-threads`,
                            "Close threads on this case",
                          )}
                        </header>
                        ${repeat(
                          threads,
                          (thread) => thread.key,
                          (thread) =>
                            html`<button
                              ${offeredAction("word", "lf-vr-thread-link")}
                              @click=${(/** @type {MouseEvent} */ event) => {
                                const control = event.currentTarget;
                                /** @type {HTMLDivElement | null} */
                                const popup =
                                  control instanceof HTMLElement
                                    ? control.closest("div[popover]")
                                    : null;
                                if (popup) closeNativeLayer(popup);
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
            <button ${offeredAction("word", "lf-vr-next")}>
              Next unchecked <span aria-hidden="true">→</span>
            </button>
          </div>
          <div class="lf-vr-evidence" data-lf-reading-role="pane" data-lf-generated>
            <header>
              <p class="lf-vr-evidence-note" ${generated({ says: true })}>
                ${record.capture.viewport.width} × ${record.capture.viewport.height} ·
                ${record.capture.browser}
              </p>
              <button
                ${offeredAction("word", "lf-vr-inspect")}
                aria-controls=${`${this.id}-${record.id}-inspection`}
              >
                Capture details
              </button>
              <div
                class="lf-vr-details scroll"
                id=${`${this.id}-${record.id}-inspection`}
                popover
              >
                <header class="lf-vr-inspection-heading">
                  <h4>Capture details</h4>
                  ${closeButton(
                    `${this.id}-${record.id}-inspection`,
                    "Close capture details",
                  )}
                </header>
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
                      ? fact("Full-frame difference", entry.difference.description)
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
            </header>
            <div class="lf-vr-capture">
              ${entry.shot}
              <div class="lf-vr-claim">
                <p class="lf-vr-result" ${generated({ says: true })}>
                  ${record.result}
                </p>
                <p class="lf-vr-action" ${generated({ says: true })}>
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
            ${entry.threads}
          </section>`,
        entry.article,
        { host: this },
      );
      return entry.article;
    }

    /** @param {readonly import("/runtime/thread/surfaces.js").OutletTarget[]} targets */
    threadOutlets(targets) {
      return targets.map(({ anchor, placement }) => {
        const article = this.#entries.get(anchor.datum)?.article;
        return article &&
          anchor.datum === this.#selected?.record.id &&
          placement.datumElement === article
          ? article.querySelector(".lf-vr-threads")
          : null;
      });
    }
  },
);
