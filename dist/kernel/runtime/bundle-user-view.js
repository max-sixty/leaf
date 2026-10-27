import { coarsePointer, layerHeaders, randomId, sessionIsActive } from "./bundle-layer-client.js";
import { layoutWindow, offlineInteractive, pageUrl, runtime, seenRect, shownWindow, tagsDeclaring, watchRoom, watchSemantic } from "./bundle-geometry.js";
import { pageReadiness, unconcealedReadingRegions } from "./bundle-content-layout.js";
import { onMotionPreferenceChange, reducedMotion } from "./bundle-media.js";
import { darkPreference, pageIdentity, shownScheme } from "./bundle-page-identity.js";

//#region runtime/user-view.js
const REPORT_MS = 1e4;
const QUIET_MS = 300;
const rectangle = ({ x, y, width, height }) => ({
	x,
	y,
	width,
	height
});
const session = randomId();
let sequence = 0;
let reading = null;
let loading = null;
function loadReading() {
	return loading ??= import("/checks/view.js").then((module) => {
		reading = module.readViewChecks;
	}).catch((error) => {
		loading = null;
		throw error;
	});
}
function context() {
	const visual = window.visualViewport;
	const { right: width, bottom: height } = layoutWindow();
	const viewport = {
		width,
		height
	};
	if (viewport.width <= 0 || viewport.height <= 0 || visual.width <= 0 || visual.height <= 0) return null;
	const clips = /* @__PURE__ */ new Map();
	return {
		session,
		identity: pageIdentity(),
		sequence: ++sequence,
		visible: document.visibilityState !== "hidden",
		revision: runtime.currentRevision,
		through_seq: runtime.lastEventSeq,
		viewport,
		visual_viewport: {
			width: visual.width,
			height: visual.height,
			offset_left: visual.offsetLeft,
			offset_top: visual.offsetTop,
			scale: visual.scale
		},
		shown_window: rectangle(shownWindow()),
		color_scheme: shownScheme(),
		reduced_motion: reducedMotion(),
		pointer: coarsePointer.matches ? "coarse" : "fine",
		scroll: {
			x: window.scrollX,
			y: window.scrollY
		},
		visible_regions: unconcealedReadingRegions().filter(({ body }) => seenRect(body, clips) !== null).map(({ id }) => id)
	};
}
function readChecks(view) {
	const open = tagsDeclaring((entry) => ["markup", "members"].includes(entry["x-content"]));
	return {
		sequence: view.sequence,
		identity: view.identity,
		revision: view.revision,
		through_seq: view.through_seq,
		viewport: view.viewport,
		visual_viewport: view.visual_viewport,
		shown_window: view.shown_window,
		color_scheme: view.color_scheme,
		reading: reading(open)
	};
}
async function readCurrentUserView() {
	let unavailable = null;
	if (offlineInteractive) unavailable = "Layout probes are unavailable in an export.";
	else try {
		await loadReading();
	} catch (error) {
		unavailable = `Layout probes unavailable: ${error.message}`;
	}
	const view = context();
	if (!view) return {
		revision: null,
		unavailable: "The document has no allocated viewport."
	};
	return {
		...view,
		observed_at: (/* @__PURE__ */ new Date()).toISOString(),
		readiness: pageReadiness(),
		checks: unavailable ? null : readChecks(view),
		...unavailable ? { unavailable } : {}
	};
}
function observeUserView() {
	if (offlineInteractive) return;
	let pending = null;
	let checks = null;
	let checkedBasis = null;
	let lastSent = null;
	function send(view, keepalive = false) {
		fetch(pageUrl("api/user-view"), {
			method: "POST",
			headers: layerHeaders({ "Content-Type": "application/json" }),
			body: JSON.stringify({
				...view,
				checks
			}),
			keepalive,
			signal: keepalive ? void 0 : globalThis.AbortSignal.timeout(REPORT_MS)
		}).catch(() => {});
	}
	function report({ inspect = false, keepalive = false } = {}) {
		if (!sessionIsActive()) return;
		if (!Number.isInteger(runtime.currentRevision)) return;
		const view = context();
		if (!view) return;
		const basis = JSON.stringify([
			view.revision,
			view.through_seq,
			view.viewport,
			view.visual_viewport,
			view.shown_window,
			view.color_scheme
		]);
		if (view.visible && pageReadiness() === null && (inspect || basis !== checkedBasis)) {
			if (reading) {
				checks = readChecks(view);
				checkedBasis = basis;
			} else if (!loading) loadReading().then(schedule).catch(() => {
				loading = null;
			});
		}
		const said = JSON.stringify({
			...view,
			sequence: null,
			checks
		});
		if (!inspect && !keepalive && said === lastSent) return;
		lastSent = said;
		send(view, keepalive);
	}
	function schedule() {
		clearTimeout(pending);
		pending = setTimeout(() => {
			pending = null;
			report();
		}, QUIET_MS);
	}
	document.addEventListener("visibilitychange", () => {
		clearTimeout(pending);
		report({ keepalive: document.visibilityState === "hidden" });
	});
	window.addEventListener("pagehide", () => {
		if (!sessionIsActive()) return;
		const view = context();
		if (view) send({
			...view,
			visible: false
		}, true);
	});
	document.addEventListener("lf-session-active", schedule);
	watchSemantic(() => {
		if (document.visibilityState !== "hidden") schedule();
	});
	watchRoom(schedule);
	window.addEventListener("pageshow", schedule);
	onMotionPreferenceChange(schedule);
	for (const preference of [darkPreference, coarsePointer]) preference.addEventListener("change", schedule);
	setInterval(() => {
		if (document.visibilityState !== "hidden") report({ inspect: true });
	}, REPORT_MS);
	schedule();
}

//#endregion
export { observeUserView, readCurrentUserView };