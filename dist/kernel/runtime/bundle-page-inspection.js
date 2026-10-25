import { closeControl, closeNativeLayer, el, offlineInteractive, pageUrl, requestJson, sessionIsActive, showNativeLayer } from "./bundle-layer-client.js";
import { closeLayer, currentLocationIn, focusDestination, handBack, html, nothing, openLayer, openerOf, render } from "./bundle-dom-move.js";
import { chromeForeground } from "./bundle-css-anchors.js";
import { copyControl } from "./bundle-surfaces.js";
import { readCurrentUserView } from "./bundle-user-view.js";

//#region runtime/page-inspection.js
const dialog = el("dialog", "lf-ui lf-inspection-dialog");
dialog.setAttribute("aria-label", "Page diagnostics");
const head = el("div", "lf-inspection-head");
head.append(el("strong", "", "Page diagnostics"));
const copy = copyControl("", {
	label: "Copy diagnostics",
	success: "Diagnostics copied",
	error: "Diagnostics not copied · open Structured report to select the text"
});
const copyLabel = el("button", "lf-btn", "Copy diagnostics");
copyLabel.type = "button";
copy.append(copyLabel);
const close = closeControl({
	name: "Close page diagnostics",
	title: "Close page diagnostics (Esc)"
});
head.append(copy, close);
const body = el("div", "lf-inspection-body");
dialog.append(head, body);
chromeForeground.append(dialog);
let request = null;
let report = null;
let sourceError = null;
let loading = false;
const number = (value) => value.toLocaleString();
const metrics = (values) => html`<dl class="lf-inspection-metrics">
    ${[
	["UTF-8 bytes", values.bytes],
	["CSS rules", values.rules],
	["Declarations", values.declarations],
	["Inline styles", values.inline_styles],
	["!important", values.important]
].map(([label, value]) => html`<div>
          <dt>${label}</dt>
          <dd>${number(value)}</dd>
        </div>`)}
  </dl>`;
const sourceRows = (owner) => html`<dl>
    ${report.css.sources.filter((source) => source.owner === owner).map((source) => html`
          <dt><code>${source.path}:${source.line}</code></dt>
          <dd>
            ${number(source.bytes)} bytes · ${number(source.rules)} rules ·
            ${number(source.declarations)} declarations ·
            ${number(source.inline_styles)} inline · ${number(source.important)}
            !important <br />${[source.kind, ...source.documents].join(" · ")}
            ${source.syntax_errors.map((finding) => html`<p>${finding.text}</p>`)}
          </dd>
        `)}
  </dl>`;
const observations = (label, rows, describe) => html` <dt>${label}</dt>
    <dd>
      ${rows.length ? html`<ul>
              ${rows.map((row) => html` <li><code>${row.at}</code>: ${describe(row)}</li>`)}
            </ul>` : "None observed"}
    </dd>`;
function browserReading(view) {
	if (!view.viewport) return html`<p>${view.unavailable}</p>`;
	const checks = view.checks?.reading.checks;
	return html` <p>
      Captured ${new Date(view.observed_at).toLocaleString()} ·
      ${view.revision === null ? "export" : `r${view.revision}`} ·
      ${view.viewport.width} × ${view.viewport.height} · ${view.color_scheme}
    </p>
    ${view.unavailable ? html`<p>${view.unavailable}</p>` : nothing}
    ${view.readiness ? html`<p>Captured while the page was settling: ${view.readiness}.</p>` : nothing}
    ${checks ? html`<dl>
            <dt>Horizontal overflow</dt>
            <dd>${number(checks.horizontal_overflow_px)} px</dd>
            ${observations("Overflowing regions", checks.overflowing_regions, (row) => `${row.over} px beyond its scrollport`)}
            ${observations("Scrollbar clearance", checks.scrollbar_clearance, (row) => `${row.clear} px available; ${row.required} px needed for ${row.content}`)}
            ${observations(`Scaled labels below ${checks.shrunk_labels.threshold_px} px (heuristic)`, checks.shrunk_labels.drawings, (row) => `${row.labels} labels; smallest ${row.drawn} px, authored ${row.set} px; “${row.words}”`)}
            ${observations("Arrangement", view.checks.reading.layout.arrangement, (row) => `${row.rows} items by row · ${row.path}`)}
          </dl>` : nothing}
    <details>
      <summary>Browser observations and locations</summary>
      <pre>${JSON.stringify(view, null, 2)}</pre>
    </details>`;
}
function present() {
	report.source_unavailable = sourceError;
	report.source_pending = loading;
	const serialized = JSON.stringify(report, null, 2);
	copy.value = serialized;
	copy.disabled = loading;
	copyLabel.disabled = loading;
	body.setAttribute("aria-busy", String(loading));
	if (loading) {
		render(html`<p role="status">Reading source…</p>`, body);
		return;
	}
	render(html`
      <p>
        Source inventory and passive browser observations. Counts describe the page;
        they do not rate its design.
      </p>
      <section aria-label="Authored CSS">
        <h2>Authored CSS</h2>
        ${loading ? html`<p role="status">Reading source…</p>` : nothing}
        ${sourceError ? html`<p role="status">${sourceError}</p>
                ${report.basis ? html`<button class="lf-btn" @click=${loadSource}>
                        Retry source inspection
                      </button>` : nothing}` : nothing}
        ${report.css ? html`
                <p>Source captured for r${report.basis.revision}. Static CSS only.</p>
                ${metrics(report.css.page)}
                <h3>Page sources and locations</h3>
                ${sourceRows("page")}
                <details>
                  <summary>Selected layer CSS</summary>
                  ${metrics(report.css.layer)}${sourceRows("layer")}
                </details>
                ${report.css.coverage.map((line) => html`<p>${line}</p>`)}
              ` : nothing}
      </section>
      <section aria-label="Browser observation">
        <h2>This tab at opening</h2>
        ${browserReading(report.current_view)}
        <p>
          The captured view stays fixed while this dialog is open. Close and reopen to
          inspect again.
        </p>
      </section>
      <details>
        <summary>Structured report</summary>
        <pre tabindex="0" aria-label="Structured diagnostics">${serialized}</pre>
      </details>
    `, body);
}
async function loadSource() {
	request?.abort();
	const attempt = new AbortController();
	request = attempt;
	sourceError = null;
	loading = true;
	if (currentLocationIn(body)) focusDestination(close, "move");
	present();
	try {
		const source = await requestJson(pageUrl(`api/inspect?revision=${report.basis.revision}`), { signal: attempt.signal }, "Page diagnostics");
		if (request !== attempt || !dialog.open) return;
		report = {
			...source,
			current_view: report.current_view
		};
	} catch (error) {
		if (request !== attempt || !dialog.open) return;
		sourceError = `Source inspection unavailable: ${error.message}`;
	} finally {
		if (request === attempt && dialog.open) {
			loading = false;
			present();
		}
	}
}
async function openPageInspection(intent) {
	const current_view = await readCurrentUserView();
	if (!intent()) return;
	const available = !offlineInteractive && sessionIsActive() && Number.isInteger(current_view.revision);
	report = {
		basis: available ? { revision: current_view.revision } : null,
		css: null,
		current_view
	};
	sourceError = available ? null : "Source inspection is unavailable in this export or public preview. Browser context is shown below.";
	loading = available;
	openLayer(dialog);
	if (available) loadSource();
	else present();
	showNativeLayer(dialog);
	focusDestination(close, "move");
}
function dismiss() {
	request?.abort();
	request = null;
	const returnTo = openerOf(dialog);
	closeLayer(() => closeNativeLayer(dialog), () => handBack(returnTo));
}
close.onclick = dismiss;
dialog.addEventListener("cancel", (event) => {
	event.preventDefault();
	dismiss();
});

//#endregion
export { openPageInspection };