/* About this page brings page identity and on-demand diagnostics together. The server
 * owns exact source attribution; user-view.js owns passive browser observations. Capture the tab before opening the modal, keep
 * that revision throughout the request, and label the captured reading rather than
 * pretending it follows later edits or resizes. Closing releases the request. Nothing
 * here changes authored content, starts a website session, or polls for updates.
 * Page controls own identity values; copyable-text.js supplies every read-only text
 * block with its copy control. This module loads only when About opens. */
import { describeFailure } from "./exception.js";
import { html, nothing, render } from "/runtime/framework.js";
import { chromeForeground } from "./chrome.js";
import { offlineInteractive, pageUrl, runtime } from "./context.js";
import { copyControl } from "./copy-control.js";
import { copyableText } from "./copyable-text.js";
import { pageControls } from "./page-controls.js";
import {
  closeLayer,
  focusDestination,
  handBack,
  openLayer,
  openerOf,
  currentLocationIn,
} from "./focus.js";
import { showNativeLayer, closeNativeLayer } from "./keyboard/layer-stack.js";
import { requestJson, sessionIsActive } from "./layer-client.js";
import { retainUserIntent } from "./user-intent.js";
import { scrollIntoView } from "./landing-scroll.js";
import { scrollBehavior } from "./motion.js";
import { readCurrentUserView } from "./user-view.js";
import {
  closeControl,
  el,
  offerAction,
  offeredAction,
  reveal,
} from "./widget-elements.js";

/** Source diagnostics are served by `page_inspection.inspect_artifact`.
 * @typedef {{bytes: number, rules: number, declarations: number, inline_styles: number, important: number}} CssCounts
 * @typedef {{page: CssCounts, layer: CssCounts, sources: (CssCounts & {owner: string, path: string, line: number, kind: string, documents: string[], syntax_errors: {text: string}[]})[], coverage: string[]}} CssReport
 * @typedef {{page: {bytes: number, inline_scripts: number, files: number}, sources: {path: string, line: number, owner: string, kind: string, bytes: number}[]}} ScriptReport
 * @typedef {{basis: {revision: number | null}, css: CssReport, javascript: ScriptReport, page_widgets: {tag: string, path: string}[]}} SourceReport
 * @typedef {Awaited<ReturnType<typeof readCurrentUserView>>} CurrentView
 * @typedef {(SourceReport | {basis: {revision: number | null} | null, css: null, javascript?: never, page_widgets?: never}) & {current_view: CurrentView, source_unavailable?: string | null, source_pending?: boolean}} Report
 * @typedef {{at: string, place?: import("/checks/locate.js").Place}} Observation
 */
const dialog = el("dialog", "lf-ui lf-inspection-dialog");
dialog.setAttribute("aria-label", "About this page");
const head = el("div", "lf-dialog-head");
head.append(el("strong", "lf-dialog-title", "About this page"));
const copy = copyControl("", {
  label: "Copy diagnostics",
  success: "Diagnostics copied",
  error: "Diagnostics not copied. Select the report text to copy it manually.",
});
const copyLabel = offerAction("word", "", "Copy diagnostics");
copy.append(copyLabel);
const close = closeControl({
  name: "Close about this page",
  title: "Close about this page (Esc)",
});
head.append(copy, close);
// The page's status line is behind this modal. Keep copy outcomes beside its
// trigger; Web Awesome still owns clipboard access and the spoken announcement.
const copyResult = el("p");
copyResult.hidden = true;
const scroll = el("div", "lf-inspection-body");
const identity = el("section");
identity.setAttribute("aria-label", "Page details");
const body = el("div");
scroll.append(identity, body);
dialog.append(head, copyResult, scroll);
for (const type of ["wa-copy", "wa-error"]) {
  copy.addEventListener(type, () => {
    if (!dialog.open) return;
    const failed = type === "wa-error";
    const fallback = failed
      ? html`<button ${offeredAction("word")} @click=${selectReport}>
          Select report text
        </button>`
      : nothing;
    render(
      html`<span>${failed ? copy.errorLabel : copy.successLabel}</span> ${fallback}`,
      copyResult,
    );
    if (copyResult.hidden) copyResult.hidden = false;
  });
}

function selectReport() {
  const text = body.querySelector('pre[aria-label="Structured diagnostics"]');
  const selection = getSelection();
  if (!text || !selection) return;
  const intent = retainUserIntent();
  reveal(text, intent);
  focusDestination(text, "move");
  const range = document.createRange();
  range.selectNodeContents(text);
  selection.removeAllRanges();
  selection.addRange(range);
  scrollIntoView(text, { block: "start", behavior: scrollBehavior() });
}
chromeForeground.append(dialog);

/** @type {AbortController | null} */
let request = null;
/** @type {Report | null} */
let report = null;
/** @type {string | null} */
let sourceError = null;
let loading = false;
/** @type {WeakMap<object, WeakRef<Element>>} */
let destinations = new WeakMap();
/** @type {string | null} */
let navigationError = null;
/** @param {number} value */
const number = (value) => value.toLocaleString();
/** @param {CssCounts} values */
const metrics = (values) =>
  html`<dl class="lf-inspection-metrics">
    ${Object.entries({
      "UTF-8 bytes": values.bytes,
      "CSS rules": values.rules,
      Declarations: values.declarations,
      "Inline styles": values.inline_styles,
      "!important": values.important,
    }).map(
      ([label, value]) =>
        html`<div>
          <dt>${label}</dt>
          <dd>${number(value)}</dd>
        </div>`,
    )}
  </dl>`;

/** @param {CssReport} css @param {string} owner */
const sourcesOf = (css, owner) =>
  css.sources.filter((source) => source.owner === owner);
/** @param {CssReport} css @param {string} owner */
const sourceRows = (css, owner) =>
  html`<dl>
    ${sourcesOf(css, owner).map(
      (source) => html`
        <dt><code>${source.path}:${source.line}</code></dt>
        <dd>
          ${number(source.bytes)} bytes · ${number(source.rules)} rules ·
          ${number(source.declarations)} declarations · ${number(source.inline_styles)}
          inline · ${number(source.important)} !important
          <br />${[source.kind, ...source.documents].join(" · ")}
          ${source.syntax_errors.map((finding) => html`<p>${finding.text}</p>`)}
        </dd>
      `,
    )}
  </dl>`;

/** @template {Observation} T @param {string} label @param {readonly T[]} rows @param {(row: T) => string} describe */
const observations = (label, rows, describe) =>
  html` <dt>${label}</dt>
    <dd>
      ${
        rows.length
          ? html`<ul>
              ${rows.map(
                (row) =>
                  html` <li>
                    <code>${row.at}</code>: ${describe(row)}
                    ${
                      destinations.has(row)
                        ? html`<button
                            ${offeredAction("symbol", "", "Show on page", { action: "show" })}
                            @click=${() => showOnPage(row)}
                          ></button>`
                        : nothing
                    }
                  </li>`,
              )}
            </ul>`
          : "None observed"
      }
    </dd>`;

/** @param {Observation} row */
async function showOnPage(row) {
  const target = destinations.get(row)?.deref();
  const view = report?.current_view;
  if (!view) return;
  if (runtime.currentRevision !== view.revision || !target?.isConnected) {
    navigationError =
      "This location changed. Close and reopen diagnostics to inspect the current page.";
    present();
    return;
  }
  const intent = retainUserIntent();
  if (!intent.handoff(() => dismiss(false))) return;
  const exposure = reveal(target, intent);
  await exposure.ready;
  if (!intent() || !target.isConnected || runtime.currentRevision !== view.revision)
    return;
  focusDestination(target, "move");
  scrollIntoView(target, { block: "center", behavior: scrollBehavior() });
}

/** @param {CurrentView} view */
function browserReading(view) {
  if (!("viewport" in view)) return html`<p>${view.unavailable}</p>`;
  const checks = view.checks?.reading.checks;
  return html` <p>
      Captured ${new Date(view.observed_at).toLocaleString()} ·
      ${view.revision === null ? "export" : `r${view.revision}`} ·
      ${view.viewport.width} × ${view.viewport.height} · ${view.color_scheme}
    </p>
    <details>
      <summary>Rendering environment</summary>
      ${copyableText("rendering environment", JSON.stringify(view.identity, null, 2))}
    </details>
    ${view.unavailable ? html`<p>${view.unavailable}</p>` : nothing}
    ${
      view.readiness
        ? html`<p>Captured while the page was settling: ${view.readiness}.</p>`
        : nothing
    }
    ${
      checks
        ? html`<dl>
            <dt>Horizontal overflow</dt>
            <dd>${number(checks.horizontal_overflow_px)} px</dd>
            ${observations(
              "Overflowing regions",
              checks.overflowing_regions,
              (row) => `${row.over} px beyond its scrollport`,
            )}
            ${observations(
              "Scrollbar clearance",
              checks.scrollbar_clearance,
              (row) =>
                `${row.clear} px available; ${row.required} px needed for ${row.content}`,
            )}
            ${observations(
              `Scaled labels below ${checks.shrunk_labels.threshold_px} px (heuristic)`,
              checks.shrunk_labels.drawings,
              (row) =>
                `${row.labels} labels; smallest ${row.drawn} px, authored ${row.set} px; “${row.words}”`,
            )}
            ${observations(
              "Arrangement",
              view.checks?.reading.layout.arrangement ?? [],
              (row) => `${row.rows} items by row · ${row.path}`,
            )}
          </dl>`
        : nothing
    }
    <details>
      <summary>Browser observations and locations</summary>
      ${copyableText("browser observations and locations", JSON.stringify(view, null, 2))}
    </details>`;
}

function present() {
  if (!report) return;
  report.source_unavailable = sourceError;
  report.source_pending = loading;
  const serialized = JSON.stringify(report, null, 2);
  copy.value = serialized;
  copy.disabled = loading;
  copyLabel.disabled = loading;
  if (body.ariaBusy !== String(loading)) body.ariaBusy = String(loading);
  if (loading) {
    render(html`<p role="status">Reading source…</p>`, body);
    return;
  }
  render(
    html`
      <p>
        Source inventory and passive browser observations. Counts describe the page;
        they do not rate its design.
      </p>
      ${navigationError ? html`<p role="status">${navigationError}</p>` : nothing}
      <section aria-label="Authored CSS">
        <h2 class="lf-label">Authored CSS</h2>
        ${loading ? html`<p role="status">Reading source…</p>` : nothing}
        ${
          sourceError
            ? html`<p role="status">${sourceError}</p>
                ${
                  report.basis
                    ? html`<button
                        ${offeredAction("symbol", "", "Retry source inspection", {
                          action: "retry",
                        })}
                        @click=${loadSource}
                      ></button>`
                    : nothing
                }`
            : nothing
        }
        ${
          // What the counts cover stands over them, and the page's sources under them
          // where it has any; its counts already say where it has none.
          report.css
            ? html`
                <p>
                  ${[
                    `Source captured for r${report.basis.revision}.`,
                    ...report.css.coverage,
                  ].join(" ")}
                </p>
                ${metrics(report.css.page)}
                ${
                  sourcesOf(report.css, "page").length
                    ? html`<h3>Page sources and locations</h3>
                        ${sourceRows(report.css, "page")}`
                    : nothing
                }
                <details>
                  <summary>Selected layer CSS</summary>
                  ${metrics(report.css.layer)}${sourceRows(report.css, "layer")}
                </details>
              `
            : nothing
        }
      </section>
      ${
        report.javascript
          ? html`<section aria-label="Authored JavaScript">
              <h2 class="lf-label">Authored JavaScript</h2>
              <p>
                ${number(report.javascript.page.bytes)} page-owned bytes ·
                ${number(report.javascript.page.inline_scripts)} inline scripts ·
                ${number(report.javascript.page.files)} files
              </p>
              <details>
                <summary>JavaScript sources</summary>
                <dl>
                  ${report.javascript.sources.map(
                    (source) =>
                      html`<dt><code>${source.path}:${source.line}</code></dt>
                        <dd>
                          ${source.owner} · ${source.kind} · ${number(source.bytes)}
                          bytes
                        </dd>`,
                  )}
                </dl>
              </details>
            </section>`
          : nothing
      }
      ${
        report.page_widgets?.length
          ? html`<section aria-label="Page-owned widgets">
              <h2 class="lf-label">Page-owned widgets</h2>
              <dl>
                ${report.page_widgets.map(
                  (widget) =>
                    html`<dt><code>${widget.tag}</code></dt>
                      <dd><code>${widget.path}</code></dd>`,
                )}
              </dl>
            </section>`
          : nothing
      }
      <section aria-label="Browser observation">
        <h2 class="lf-label">This tab at opening</h2>
        ${browserReading(report.current_view)}
        <p>
          The captured view stays fixed while this dialog is open. Close and reopen to
          inspect again.
        </p>
      </section>
      <details>
        <summary>Structured report</summary>
        ${copyableText("Structured diagnostics", serialized)}
      </details>
    `,
    body,
  );
}

async function loadSource() {
  const current = report;
  if (!current?.basis) return;
  request?.abort();
  const attempt = new AbortController();
  request = attempt;
  sourceError = null;
  loading = true;
  if (currentLocationIn(body)) focusDestination(close, "move");
  present();
  try {
    /** @type {SourceReport} */
    const source = await requestJson(
      pageUrl(`api/inspect?revision=${current.basis.revision}`),
      { signal: attempt.signal },
      "Page diagnostics",
    );
    if (request !== attempt || !dialog.open) return;
    report = { ...source, current_view: current.current_view };
  } catch (error) {
    if (request !== attempt || !dialog.open) return;
    sourceError = `Source inspection unavailable: ${describeFailure(error)}`;
  } finally {
    if (request === attempt && dialog.open) {
      loading = false;
      present();
    }
  }
}

/** @param {ReturnType<typeof retainUserIntent>} intent */
export async function openPageInspection(intent) {
  const resolver = offlineInteractive
    ? null
    : await import("/checks/locate.js").catch(() => null);
  const current_view = await readCurrentUserView();
  if (!intent()) return;
  destinations = new WeakMap();
  navigationError = null;
  if (!copyResult.hidden) copyResult.hidden = true;
  // Keep the captured node itself: a later redraw must not retarget an old observation.
  if (resolver && "checks" in current_view && current_view.checks) {
    const { checks, layout } = current_view.checks.reading;
    const observations = [
      ...checks.overflowing_regions,
      ...checks.scrollbar_clearance,
      ...checks.shrunk_labels.drawings,
      ...layout.arrangement,
    ];
    for (const observation of observations) {
      if (!observation.place) continue;
      const target = resolver.resolvePlace(observation.place);
      if (target) destinations.set(observation, new WeakRef(target));
    }
  }
  const available =
    !offlineInteractive && sessionIsActive() && Number.isInteger(current_view.revision);
  report = {
    basis: available ? { revision: current_view.revision } : null,
    css: null,
    current_view,
  };
  sourceError = available
    ? null
    : "Source inspection is unavailable in this export or public preview. Browser context is shown below.";
  loading = available;
  // Each text the menu copies, under its name, then what it grants beyond what it says
  // (page-controls.js, `title`). A row's terse `value` only shortens its text, so it
  // stands in the menu alone.
  render(
    html`<h2 class="lf-label">Page details</h2>
      ${pageControls()
        .filter((entry) => entry.copies)
        .map(
          (entry) =>
            html`${copyableText(
              entry.label.charAt(0).toUpperCase() + entry.label.slice(1),
              entry.copies,
            )}${entry.title ? html`<p>${entry.title}</p>` : nothing}`,
        )}`,
    identity,
  );
  openLayer(dialog);
  if (available) void loadSource();
  else present();
  showNativeLayer(dialog);
  focusDestination(close, "move");
}

function dismiss(returnFocus = true) {
  request?.abort();
  request = null;
  const returnTo = openerOf(dialog);
  closeLayer(
    () => closeNativeLayer(dialog),
    () => {
      if (returnFocus) handBack(returnTo);
    },
  );
}
close.onclick = () => dismiss();
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  dismiss();
});
