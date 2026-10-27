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
import {
  LeafElement,
  html,
  iconTemplate,
  nothing,
  repeat,
  ref,
  live,
  generated,
  offered,
  offeredAction,
  commands,
  cycledRow,
  beginWalk,
  listWalkPosition,
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
  keeps,
  releaseOutlets,
  threadSurface,
  scopedMediaUrl,
  whileConnected,
  registerReadingRegion,
  compoundReadingRegionId,
  preserveReadingRegions,
} from "/runtime/widget-api.js";

// A popover's way out wears the face of every surface's close control in Leaf: the
// cross, named for what it closes (runtime/widget-elements.js, `closeControl`).
const closeButton = (popover, name) =>
  html`<button
    ${offeredAction("symbol", "", name, { title: `${name} (Esc)` })}
    popovertarget=${popover}
    popovertargetaction="hide"
  >
    ${iconTemplate("cross", "lf-action-icon")}
  </button>`;
const fact = (name, value) =>
  html`<div>
    <dt ${generated({ says: true })}>${name}</dt>
    <dd ${generated({ says: true })}>${value}</dd>
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

    // The run, set by whoever hosts the widget: Leaf from the bound source (the
    // registry's `x-data.run.property`), or null while that source has none.
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      this.value = null;
    }

    #entries = new Map();
    // The run the last render reconciled, and the one whose cases were last marked.
    #run;
    #marked;
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
    #presentShot = (promise) => this.controller.present(promise);

    setup() {
      const selectedControl = (selector) => () =>
        this.#entries.get(this.#selected)?.article.querySelector(selector);
      commands(this, "In a visual review", [
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
      });
    }

    #reconcile(run) {
      const records = run?.cases ?? [];
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
          entry = {};
          entry.place = (article) => {
            entry.article = article;
          };
          entry.threadPlace = (body) => {
            if (!body || entry.threads === body) return;
            entry.threads = body;
            this.#readingRegion(body, `discussion-${record.id}`);
          };
          entry.prepare = (shot) => {
            entry.shot = shot;
          };
          this.#entries.set(record.id, entry);
        }
        const before = scopedMediaUrl(record.before);
        const after = scopedMediaUrl(record.after);
        if (entry.before !== before || entry.after !== after) entry.difference = null;
        Object.assign(entry, { record, before, after });
      }
      if (!ids.has(this.#selected))
        this.#selected = (
          records.find((record) => record.classification !== "clean") ?? records[0]
        )?.id;
      this.#run = run;
    }

    #approved(id) {
      return this.state?.review?.units?.[id]?.detail.approved === true;
    }
    // n and Shift+n walk the cases, coming round at either end, and say where the
    // landing stands among them as every walk does.
    #step(delta) {
      const ids = () => this.#run.cases.map((record) => record.id);
      this.#select(cycledRow(ids(), this.#selected, delta), true);
      beginWalk("visual-case", "Case", () => listWalkPosition(ids(), this.#selected));
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
      const records = this.#run?.cases ?? [];
      const index = records.findIndex((record) => record.id === this.#selected);
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

      const available = this.reading.actions.review.available;
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
      this.classList.toggle("lf-rendered", Boolean(this.#run));
      if (this.#run !== this.#marked) {
        // Each case's article is a datum on a Leaf page (`module-state.md`, "Marking
        // drawn data"), following its case by id across runs.
        for (const [index, record] of (this.#run?.cases ?? []).entries()) {
          const { article } = this.#entries.get(record.id);
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
        const heading = this.#entries
          .get(this.#selected)
          ?.article.querySelector(".lf-vr-title");
        if (!heading) return false;
        focusDestination(heading, "return");
        return true;
      });
      this.#restoreFocus = null;
      paintKeys();
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
      const { record, before, after } = entry;
      const run = this.#run;
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
                @change=${(event) => this.#review(record, event.currentTarget.checked)}
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
            <lf-shot
              id=${`${this.id}-${record.id}-capture`}
              before=${before}
              after=${after}
              alt=${`${record.title}. ${record.result}`}
              ._lfPresentGenerated=${this.#presentShot}
              ${ref(entry.prepare)}
            ></lf-shot>
            <div class="lf-vr-claim">
              <p class="lf-vr-result" ${generated({ says: true })}>${record.result}</p>
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
          <div
            class="lf-vr-threads lf-ui"
            ${generated({ says: false })}
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
