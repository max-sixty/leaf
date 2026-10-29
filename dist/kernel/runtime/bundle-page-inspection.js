import { scrollBehavior } from "./bundle-portable.js";
import { closeLayer, closeNativeLayer, currentLocationIn, focusDestination, guard, handBack, html, nothing, offlineInteractive, openLayer, openerOf, pageUrl, render, runtime, showNativeLayer } from "./bundle-layer-stack.js";
import { closeControl, el, offerAction, offeredAction, requestJson, reveal, sessionIsActive } from "./bundle-layer-client.js";
import { chromeForeground, pageControls } from "./bundle-content-layout.js";
import { copyControl, retainUserIntent, scrollIntoView } from "./bundle-copy-control.js";
import { readCurrentUserView } from "./bundle-user-view.js";

//#region runtime/copyable-text.js
function copyableText(label, value) {
	return html`<div class="lf-copyable-text">
    <div class="lf-copyable-head">
      <span>${label}</span>
      ${guard([label, value], () => {
		const copy = copyControl("", {
			label: `Copy ${label}`,
			success: `${label[0].toUpperCase()}${label.slice(1)} copied`,
			error: `${label[0].toUpperCase()}${label.slice(1)} not copied · select the text to copy`,
			role: "symbol"
		});
		copy.value = value;
		return copy;
	})}
    </div>
    <pre tabindex="0" aria-label=${label}>${value}</pre>
  </div>`;
}

//#endregion
//#region runtime/page-inspection.js
const dialog = el("dialog", "lf-ui lf-inspection-dialog");
dialog.setAttribute("aria-label", "About this page");
const head = el("div", "lf-inspection-head");
head.append(el("strong", "", "About this page"));
const copyLabel = offerAction("word", "", "Copy diagnostics");
const copy = copyControl("", {
	label: "Copy diagnostics",
	success: "Diagnostics copied",
	error: "Diagnostics not copied. Select the report text to copy it manually.",
	trigger: copyLabel
});
const close = closeControl({
	name: "Close about this page",
	title: "Close about this page (Esc)"
});
head.append(copy, close);
const copyResult = el("p");
copyResult.hidden = true;
const scroll = el("div", "lf-inspection-body");
const identity = el("section");
identity.setAttribute("aria-label", "Page details");
const body = el("div");
scroll.append(identity, body);
dialog.append(head, copyResult, scroll);
for (const type of ["wa-copy", "wa-error"]) copy.addEventListener(type, () => {
	if (!dialog.open) return;
	const failed = type === "wa-error";
	const fallback = failed ? html`<button ${offeredAction("word")} @click=${selectReport}>
          Select report text
        </button>` : nothing;
	render(html`<span>${failed ? copy.errorLabel : copy.successLabel}</span> ${fallback}`, copyResult);
	if (copyResult.hidden) copyResult.hidden = false;
});
function selectReport() {
	const text = body.querySelector("pre[aria-label=\"Structured diagnostics\"]");
	const intent = retainUserIntent();
	reveal(text, intent);
	focusDestination(text, "move");
	const range = document.createRange();
	range.selectNodeContents(text);
	const selection = getSelection();
	selection.removeAllRanges();
	selection.addRange(range);
	scrollIntoView(text, {
		block: "start",
		behavior: scrollBehavior()
	});
}
chromeForeground.append(dialog);
let request = null;
let report = null;
let sourceError = null;
let loading = false;
let destinations = /* @__PURE__ */ new WeakMap();
let navigationError = null;
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
              ${rows.map((row) => html` <li>
                    <code>${row.at}</code>: ${describe(row)}
                    ${destinations.has(row) ? html`<button
                            ${offeredAction("symbol", "", "Show on page", { action: "show" })}
                            @click=${() => showOnPage(row)}
                          ></button>` : nothing}
                  </li>`)}
            </ul>` : "None observed"}
    </dd>`;
async function showOnPage(row) {
	const target = destinations.get(row)?.deref();
	const view = report.current_view;
	if (runtime.currentRevision !== view.revision || !target?.isConnected) {
		navigationError = "This location changed. Close and reopen diagnostics to inspect the current page.";
		present();
		return;
	}
	const intent = retainUserIntent();
	if (!intent.handoff(() => dismiss(false))) return;
	await reveal(target, intent).ready;
	if (!intent() || !target.isConnected || runtime.currentRevision !== view.revision) return;
	focusDestination(target, "move");
	scrollIntoView(target, {
		block: "center",
		behavior: scrollBehavior()
	});
}
function browserReading(view) {
	if (!view.viewport) return html`<p>${view.unavailable}</p>`;
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
      ${copyableText("browser observations and locations", JSON.stringify(view, null, 2))}
    </details>`;
}
function present() {
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
	render(html`
      <p>
        Source inventory and passive browser observations. Counts describe the page;
        they do not rate its design.
      </p>
      ${navigationError ? html`<p role="status">${navigationError}</p>` : nothing}
      <section aria-label="Authored CSS">
        <h2>Authored CSS</h2>
        ${loading ? html`<p role="status">Reading source…</p>` : nothing}
        ${sourceError ? html`<p role="status">${sourceError}</p>
                ${report.basis ? html`<button
                        ${offeredAction("symbol", "", "Retry source inspection", { action: "retry" })}
                        @click=${loadSource}
                      ></button>` : nothing}` : nothing}
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
      ${report.javascript ? html`<section aria-label="Authored JavaScript">
              <h2>Authored JavaScript</h2>
              <p>
                ${number(report.javascript.page.bytes)} page-owned bytes ·
                ${number(report.javascript.page.inline_scripts)} inline scripts ·
                ${number(report.javascript.page.files)} files
              </p>
              <details>
                <summary>JavaScript sources</summary>
                <dl>
                  ${report.javascript.sources.map((source) => html`<dt><code>${source.path}:${source.line}</code></dt>
                        <dd>
                          ${source.owner} · ${source.kind} · ${number(source.bytes)}
                          bytes
                        </dd>`)}
                </dl>
              </details>
            </section>` : nothing}
      ${report.page_widgets?.length ? html`<section aria-label="Page-owned widgets">
              <h2>Page-owned widgets</h2>
              <dl>
                ${report.page_widgets.map((widget) => html`<dt><code>${widget.tag}</code></dt>
                      <dd><code>${widget.path}</code></dd>`)}
              </dl>
            </section>` : nothing}
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
        ${copyableText("Structured diagnostics", serialized)}
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
	const resolver = offlineInteractive ? null : await import("/checks/locate.js").catch(() => null);
	const current_view = await readCurrentUserView();
	if (!intent()) return;
	destinations = /* @__PURE__ */ new WeakMap();
	navigationError = null;
	if (!copyResult.hidden) copyResult.hidden = true;
	const retain = (value) => {
		if (!value || typeof value !== "object") return;
		if (resolver && value.place && !Array.isArray(value.place)) {
			const target = resolver.resolvePlace(value.place);
			if (target) destinations.set(value, new WeakRef(target));
		}
		for (const child of Object.values(value)) retain(child);
	};
	if ("checks" in current_view) retain(current_view.checks);
	const available = !offlineInteractive && sessionIsActive() && Number.isInteger(current_view.revision);
	report = {
		basis: available ? { revision: current_view.revision } : null,
		css: null,
		current_view
	};
	sourceError = available ? null : "Source inspection is unavailable in this export or public preview. Browser context is shown below.";
	loading = available;
	render(html`<h2>Page details</h2>
      ${pageControls().filter((entry) => entry.copies).map((entry) => html`${copyableText(entry.label[0].toUpperCase() + entry.label.slice(1), entry.copies)}${entry.value ? html`<p>${entry.value}</p>` : nothing}`)}`, identity);
	openLayer(dialog);
	if (available) loadSource();
	else present();
	showNativeLayer(dialog);
	focusDestination(close, "move");
}
function dismiss(returnFocus = true) {
	request?.abort();
	request = null;
	const returnTo = openerOf(dialog);
	closeLayer(() => closeNativeLayer(dialog), () => {
		if (returnFocus) handBack(returnTo);
	});
}
close.onclick = () => dismiss();
dialog.addEventListener("cancel", (event) => {
	event.preventDefault();
	dismiss();
});

//#endregion
export { openPageInspection };