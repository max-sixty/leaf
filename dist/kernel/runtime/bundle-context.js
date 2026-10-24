import { J, W, Z, bindQueuedWork, createPresentationCoordinator, createPresentationSchedule, createSemanticApplication, d, x } from "./bundle-browser-runtime.js";

//#region runtime/semantic-state.js
const documentToken = Object.freeze({});
let reportPresentationFailure = (reason) => console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({ reportFailure: (reason) => reportPresentationFailure(reason) });
const schedule = createPresentationSchedule(bindQueuedWork);
const applicationState = createSemanticApplication({ presentation: {
	begin: (semanticEpoch) => presentation.begin(documentToken, semanticEpoch),
	seal: (publication) => presentation.seal(publication)
} });
const readApplication = applicationState.read;
const readPart = (derive) => applicationState.select(derive).read;
const agent = readPart((root) => root.authoritative?.agent ?? null);
const agentName = () => agent() || "the agent";
const agentLabel = () => agentName().replace(/^./, (first) => first.toUpperCase());
const pageClaimed = readPart((root) => root.authoritative?.claim_session != null);
const projectView = applicationState.projectView;
const selectWidgets = applicationState.selectWidgets;
const attachApplicationPresentation = (region, renderer) => presentation.attach(region, renderer);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) => ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
const attachWidgetPresentation = (widget, kind, renderer, seat = null) => presentation.attach(seat ? `${widgetRegion(widget, kind)}@${seat}` : widgetRegion(widget, kind), renderer);
const widgetCommits = /* @__PURE__ */ new Map();
const documentCommits = /* @__PURE__ */ new Map();
const currentWidgetParents = readPart((root) => root.effective.widgetParents);
const queueWidgetUpdate = (widget, update, committed) => {
	const { ready, committed: dom } = schedule.enqueue(() => {
		const parents = d(currentWidgetParents);
		const pending = [];
		const seen = /* @__PURE__ */ new Set([widget]);
		for (let parent = parents.get(widget); parent; parent = parents.get(parent)) {
			if (seen.has(parent)) return [];
			seen.add(parent);
			const dom = widgetCommits.get(parent);
			if (dom) pending.push(dom);
		}
		return pending;
	}, update, committed);
	widgetCommits.set(widget, dom);
	const retire = () => {
		if (widgetCommits.get(widget) === dom) widgetCommits.delete(widget);
	};
	dom.then(retire, retire);
	return ready;
};
const PRESENTATION_DOM = Object.freeze({
	widgets: () => [...widgetCommits.values()],
	projection: () => documentCommits.get("projection:chrome")?.() ?? [],
	thread: () => documentCommits.get("thread")?.() ?? [],
	obligations: () => documentCommits.get("obligations")?.() ?? []
});
const documentPresenters = [];
const applicationPresenter = ({ region, renderer = document, after, reading, paint, failSoft }) => {
	const revision = Z(0);
	const selected = J(() => {
		revision.value;
		const epoch = d(() => readApplication().semanticEpoch);
		const value = reading();
		if (epoch !== d(() => readApplication().semanticEpoch)) throw new Error(`the ${region} region's reading moved a part it read`);
		return value;
	});
	let claimed;
	let owed = false;
	let following = [];
	const forget = () => {
		for (const stop of following) stop();
		following = [];
	};
	const presenter = schedule.presenter({
		attach: () => presentation.attach(region, renderer),
		after,
		paint: (value, current) => {
			owed = false;
			forget();
			const generation = following;
			const stretch = (run) => {
				let first = true;
				let outcome;
				const stop = x(() => {
					if (!first) {
						if (!owed && current()) d(() => {
							const next = selected.value;
							if (next !== null) claim(next);
						});
						return;
					}
					first = false;
					try {
						outcome = { value: run() };
					} catch (error) {
						outcome = { error };
					}
				});
				if (current() && following === generation) generation.push(stop);
				else stop();
				if ("error" in outcome) throw outcome.error;
				return outcome.value;
			};
			const resume = (run) => (...args) => stretch(() => run(...args));
			return stretch(() => paint(value, current, resume));
		},
		failSoft
	});
	documentCommits.set(region, () => [...after?.() ?? [], presenter.committed()]);
	const claim = (value) => {
		claimed = value;
		if (value === null) return schedule.passed();
		owed = true;
		return presenter.sync(value);
	};
	const present = () => d(() => W(() => {
		revision.value += 1;
		return claim(selected.value);
	}));
	documentPresenters.push(present);
	let first = true;
	x(() => {
		const value = selected.value;
		if (first || value === null) {
			first = false;
			claimed = value;
		} else if (value !== claimed) d(() => claim(value));
	});
	const disconnect = () => {
		forget();
		presenter.disconnect();
	};
	return Object.freeze({
		present,
		disconnect
	});
};
const documentChanges = Z(0);
const documentChanged = () => documentChanges.value;
const presentDocument = () => W(() => {
	documentChanges.value += 1;
	for (const present of documentPresenters) present();
	return schedule.passed();
});
const whenDocumentPresented = () => schedule.passed();
const currentEpoch = () => d(() => readApplication().semanticEpoch);
const currentApplicationPresentation = () => ({
	document: documentToken,
	semanticEpoch: currentEpoch()
});
const whenApplicationPresented = () => presentation.whenCurrentPresented(currentApplicationPresentation);
const applicationPresented = () => presentation.currentPresented(currentApplicationPresentation);
const whenWidgetsPresented = (widgets) => presentation.whenCurrentRegionsPresented(() => ({
	document: documentToken,
	semanticEpoch: currentEpoch()
}), widgets.flatMap(widgetRegions));
const whenApplicationRegionsPresented = (regions, current) => presentation.whenCurrentRegionsPresented(() => current() ? {
	document: documentToken,
	semanticEpoch: currentEpoch()
} : null, regions);
const applicationRegionsPresented = (regions) => presentation.currentRegionsPresented(currentApplicationPresentation, regions);
const projectionRegionsPresented = (widgets) => applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
const watchPresentation = presentation.subscribe;
const readApplicationPresentation = presentation.read;
function setPresentationFailureReporter(report) {
	reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
const watchSemantic = (callback) => applicationState.select((root) => root.semanticEpoch).subscribe(() => callback(readApplication()));

//#endregion
//#region runtime/context.js
const PAGE_PATH = location.pathname;
const LIVE_ROOT = PAGE_PATH.endsWith("/");
const PAGE_ROOT = document.querySelector("link[rel=\"canonical\"][data-lf-runtime]")?.href ?? null;
const served = document.querySelector("script[data-lf-runtime][data-lf-server]");
const offlineMarker = document.querySelector("script[type=\"application/json\"][data-lf-runtime][data-lf-offline]");
const DELIVERY = Object.freeze({
	layer: (served ?? offlineMarker)?.dataset.lfLayer,
	release: served?.dataset.lfRelease,
	runtime: served?.dataset.lfRuntimeIdentity,
	probe: served?.dataset.lfProbe
});
const WEBSITE_DELIVERY = DELIVERY.release !== void 0;
const layerRoot = (doc) => doc.querySelector("script[data-lf-runtime][data-lf-entry]")?.dataset.lfEntry.replace(/leaf\.js$/, "") ?? "";
const SHARE_ROOT = served?.dataset.lfShareUrl;
function shareUrl() {
	const url = new URL(SHARE_ROOT);
	url.pathname = location.pathname;
	const access = [...url.searchParams];
	url.search = location.search;
	for (const [key, value] of access) url.searchParams.set(key, value);
	url.hash = location.hash;
	return url.href;
}
const pageUrl = (path) => new URL(path, PAGE_ROOT).href;
const offlinePayload = offlineMarker ? JSON.parse(offlineMarker.textContent || "null") : null;
const allocation = (name) => document.body.getAttribute(name);
const annotationMode = allocation("data-annotations") ?? "overlay";
const offlineInteractive = offlinePayload !== null;
const offlineState = () => offlineInteractive ? structuredClone(offlinePayload.state) : null;
const offlineData = () => offlineInteractive ? offlinePayload.data : null;
const runtimeModule = (path) => offlineInteractive ? `leaf:${path.startsWith("/") ? path : `/${path}`}` : path;
const servedLayerRoot = layerRoot(document);
const runtimeResource = (path) => {
	if (!offlineInteractive) return servedLayerRoot ? new URL(`.${path}`, new URL(servedLayerRoot, document.baseURI)).href : path;
	const located = new URL(path, document.baseURI);
	const resource = offlinePayload.resources[located.pathname];
	if (typeof resource !== "string") throw new Error(`Leaf's interactive export is missing ${path}`);
	return resource + located.hash;
};
const part = {
	active: readPart((root) => root.authoritative?.active ?? null),
	browser: readPart((root) => root.authoritative?.browser ?? null),
	revision: readPart((root) => root.document.revision),
	live: readPart((root) => root.document.live),
	stamp: readPart((root) => root.document.stamp ?? null),
	data: readPart((root) => root.data),
	seq: readPart((root) => root.authoritative?.browser.basis.through_seq ?? null),
	reading: readPart((root) => root.authoritative?.reading ?? null),
	state: readPart((root) => root.authoritative),
	phase: readPart((root) => root.phase),
	versions: readPart((root) => root.authoritative?.versions ?? []),
	workflows: readPart((root) => root.effective.workflows),
	view: readPart((root) => root.effective.view),
	undo: readPart((root) => root.effective.view?.undo ?? []),
	todos: readPart((root) => root.authoritative?.browser.todos ?? []),
	receipts: readPart((root) => root.authoritative?.browser.receipts ?? []),
	revisionLabels: readPart((root) => root.authoritative?.revision_labels)
};
const runtime = {
	get active() {
		return part.active();
	},
	get browser() {
		return part.browser();
	},
	get showsActive() {
		return runtime.active !== null && runtime.currentRevision === runtime.active.revision;
	},
	get currentLabel() {
		return part.live() && runtime.showsActive ? runtime.active.label : runtime.currentStamp === null ? null : `v${runtime.currentStamp}`;
	},
	get currentRevision() {
		return part.revision();
	},
	get currentStamp() {
		return part.live() && runtime.showsActive ? runtime.active.version : part.stamp();
	},
	get data() {
		return part.data();
	},
	get lastEventSeq() {
		return part.seq();
	},
	get reading() {
		return part.reading();
	},
	sessionReference: null,
	keyRefused: false,
	get state() {
		return part.state();
	},
	registry: {},
	get statePhase() {
		return part.phase();
	},
	get versions() {
		return part.versions();
	},
	get workflows() {
		return part.workflows();
	},
	get view() {
		return part.view();
	},
	get undo() {
		return part.undo();
	},
	get todos() {
		return part.todos();
	},
	get receipts() {
		return part.receipts();
	}
};
const revisionLabel = (revision) => part.revisionLabels()[revision];

//#endregion
export { DELIVERY, LIVE_ROOT, PAGE_ROOT, PRESENTATION_DOM, SHARE_ROOT, WEBSITE_DELIVERY, agentLabel, agentName, annotationMode, applicationPresented, applicationPresenter, applicationRegionsPresented, applicationState, attachApplicationPresentation, attachWidgetPresentation, documentChanged, layerRoot, offlineData, offlineInteractive, offlineState, pageClaimed, pageUrl, presentDocument, projectView, projectionRegionsPresented, queueWidgetUpdate, readApplication, readApplicationPresentation, readPart, revisionLabel, runtime, runtimeModule, runtimeResource, selectWidgets, setPresentationFailureReporter, shareUrl, watchPresentation, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whenWidgetsPresented };