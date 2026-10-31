import { LAYOUT, PendingTaskEvent, actionClass, actionName, actionTemplate, afterScript, announce, assignRows, atLayoutPrecision, axisTicks, backgroundFlash, bodyText, cancelAnimation, cancelRender, commandsChanged, dataBody, describeFailure, ensureSyntaxLanguage, failSoft, flashDuration, foldBlock, foldDuration, frameFor, generated, generatedElement, iconElement, iconTemplate, inBaseLayer, isNativeLayer, keeps, keepsHidden, keepsText, layoutChanged, layoutPx, measure, motion, nextAnimation, nextFrame, nextRender, offer, offerAction, offerElement, offered, offeredAction, offeredActionElement, onMotionPreferenceChange, once, placesFailure, reducedMotion, registerVisualParts, reportFailure, returnDuration, scrollBehavior, selectableOffer, selectableOffered, setScroll, sizeObserver, synNodes, syntax, tabStore, textWidth, tokenLines, under, whileConnected } from "./bundle-portable.js";
import { TEXT_BOX, TEXT_FIELD, Z, agentName, applicationRegionsPresented, applicationState, closeLayer, closeNativeLayer, currentLocationIn, declarationFor, elementsDeclaring, focusDestination, focused, handBack, holdFocus, layerFact, matchesWhen, move, offlineInteractive, onCurrentLocation, onPress, onPressAway, onUserInput, openLayer, openerOf, pageUrl, plainPress, pressIsKeyboardActivation, projectionRegionsPresented, rankAt, readPart, registry, revisionLabel, rove, showNativeLayer, turns, whenLeft } from "./bundle-layer-stack.js";
import { LayerRefused, PRESS, PRESSABLE, RequestError, commandScope, commandsOn, cycledRow, dragging, el, holdAuthoredBody, labelOf, motionPreview, nameAction, namedAction, notice, raiseError, reachedForWords, relabel, requestJson, rowArrows, saying, searchField, worksInside } from "./bundle-layer-client.js";
import { PAGE_INTERFACE, PRESENTATION, addressableLabel, addressableName, addressableWord, afterPresentation, ago, atScrollEnd, clockValue, compoundReadingRegionId, deferredArrival, fragmentTarget, pageScroller, preserveReadingRegions, projectedDatum, quietSince, regionScrollBehavior, registerReadingRegion, scrollLimit, scrollerFor, shortAgo, showReadingSubject, watchReadingRegionTransitions, whileInterfaceConnected } from "./bundle-content-layout.js";
import { HOLDS_WORD, HeldReading, aborted, allButCommandReference, anchorLabel, answeredInWords, beginWalk, capturePlace, claimTraversals, clearDraft, comparisonChanges, copyBlock, heldGrowth, highlightBlocks, inlineMarkdownFragment, keepView, langForPath, listWalkPosition, loadDeferred, loadDraft, loadMarkdown, markdownReady, markdownSourceOffset, markdownWords, obligationsIn, openingView, paintMarkdown, placeKeeper, placeOf, publishOutput, pushEntry, quoted, readObligations, readThreads, releaseOutlets, renderMarkdown, replaceEntry, restorePlace, rowWalk, saveDraft, sendDraft, setChildLists, setChildren, setRenderedChildren, threadSummary, threadSurface, viewMembers, watchDraft, widgetDescriptor } from "./bundle-data.js";
import { growthIsSeen, landingInsets, shownWindow } from "./bundle-geometry.js";
import { alignText, authoredScope, closestAcross, elementById, excerptWords, inChrome, says, wrote } from "./bundle-passages.js";
import { copyControl, fitsWhole, retainUserIntent, scrollIntoReadingBand, scrollIntoView } from "./bundle-copy-control.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { CONTRIBUTION_ENTRY_SCHEMA, DISCLOSE, LeafElement, answerWords, consumeAnnotations, contributionEntry, contributionItemKey, currentProjection, landInThread, leafEditorView, navigateToDatum, obligationActions, placePageThreads, presentContributionEntry, presentContributionReceipts, queueActions, queueItemKey, queueTitle, readQueues, registerContribution, registerRootHeader, registerThreadPresentation, shadowStage, threadActions, threadBox, threadInput, widgetController, wireInput } from "./bundle-page-layout.js";
import { classMap, createRef, guard, html, keyed, live, noChange, nothing, ref, render, repeat, styleMap, unsafeHTML } from "./portable-api.js";
import { wear } from "./bundle-dress.js";

//#region runtime/shown-answer.js
const namedValue = (answer, keyOf) => {
	if (!keyOf) return typeof answer === "string" && answer ? answer : null;
	const values = new Set((Array.isArray(answer) ? answer : []).map(keyOf));
	return values.size === 1 && !values.has(null) ? [...values][0] : null;
};
function shownAnswer(view) {
	const shows = declarationFor(view, "x-shows");
	const id = shows && view.getAttribute(shows.attr);
	if (!id) return null;
	const owner = elementById(id, authoredScope(view));
	const awaits = owner && declarationFor(owner, "x-awaits");
	const verb = awaits?.value;
	const record = verb && declarationFor(owner, "x-state")?.[verb]?.record;
	if (record?.kind !== "value" && !(record?.kind === "attribute" && awaits.key)) return null;
	if (!widgetDescriptor(owner)) return null;
	const controller = widgetController(owner);
	const reading = controller.read();
	const state = reading.state?.[verb];
	if (!state) return null;
	const scope = authoredScope(owner);
	const keyOf = record.kind === "attribute" ? (member) => elementById(member, scope)?.getAttribute(awaits.key) ?? null : null;
	const detailFor = (value) => {
		if (!keyOf) return value === null ? null : { value };
		if (value === null) return { value: [] };
		const members = (reading.memberships?.[record.attr] ?? []).filter((member) => keyOf(member) === value);
		return members.length ? { value: members } : null;
	};
	return Object.freeze({
		owner,
		value: namedValue(state.value, keyOf),
		available: Boolean(reading.actions[verb]?.available),
		takes: (value) => detailFor(value) !== null,
		answer(value, says) {
			const detail = detailFor(value);
			return detail ? controller.dispatch({
				kind: "action",
				verb,
				detail,
				...says && { says }
			}) : null;
		}
	});
}

//#endregion
//#region runtime/reports.js
function reportTarget(target) {
	if (target === null) return null;
	if (target instanceof Element) {
		if (target.id) return {
			kind: "widget",
			id: target.id
		};
	} else if (["widget", "thread"].includes(target?.kind) && typeof target.id === "string" && target.id) return {
		kind: target.kind,
		id: target.id
	};
	throw new TypeError("report target must be a widget element or {kind: 'widget' | 'thread', id}");
}
const targetKey = (target) => target ? JSON.stringify([target.kind, target.id]) : null;
const reportsByTarget = /* @__PURE__ */ new Map();
const reportsFor = (key) => {
	if (!reportsByTarget.has(key)) reportsByTarget.set(key, readPart((root) => (root.effective.view?.reports ?? []).filter((report) => key === null || targetKey(report.target) === key)));
	return reportsByTarget.get(key)();
};
const reportSequence = (target = null) => reportsFor(targetKey(reportTarget(target))).map((report) => structuredClone(report));
const publishedAt = readPart((root) => root.effective.view?.published_at ?? null);
const saidAt = (el) => closestAcross(el, ".lf-msg")?.querySelector(":scope > .lf-msg-head time")?.dateTime || publishedAt();
const readHistory = readPart((root) => ({
	phase: root.phase,
	events: root.authoritative?.browser.history ?? []
}));
const reportsPresented = (target = null) => projectionRegionsPresented([...reportWidgets(target)]);
const reportWidgets = (target) => {
	const key = targetKey(reportTarget(target));
	const widgets = new Set(target instanceof Element ? [target.id] : []);
	for (const entry of currentProjection().classified.values()) {
		if (entry.terminal || entry.e.kind !== "report") continue;
		if (key === null || key === targetKey({
			kind: "widget",
			id: entry.e.widget
		})) widgets.add(entry.e.widget);
	}
	return widgets;
};
const reportsReady = (target) => target.whenReady(() => applicationRegionsPresented([
	"projection:chrome",
	`widget:${target.id}:preparation`,
	...[...reportWidgets(target)].filter((widget) => widget !== target.id).flatMap((widget) => [`widget:${widget}:render`, `widget:${widget}:preparation`])
]));

//#endregion
//#region runtime/work.js
const widgets = () => layerFact("$work")?.widgets ?? {};
function specs(role) {
	return Object.entries(widgets()).filter(([, spec]) => spec?.role === role);
}
function workRole(element, role = null) {
	const spec = widgets()[element?.localName];
	return spec && (!role || spec.role === role) ? spec : null;
}
function workElements(root, role, { direct = false } = {}) {
	const tags = new Set(specs(role).map(([tag]) => tag));
	const candidates = [...root.querySelectorAll("*")];
	const boundary = workAncestor(root, "scope");
	return candidates.filter((element) => tags.has(element.localName) && workAncestor(element, "scope") === boundary && (!direct || workAncestor(element.parentElement) === root));
}
const directWorkElements = (root, role) => workElements(root, role, { direct: true });
function workAncestor(element, role) {
	for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
	return null;
}
function stateReport(element, role) {
	const verb = stateVerb(element, role);
	const spec = declarationFor(element, "x-state")[verb];
	return registry.$states[element.localName][verb].writer === "agent" ? [verb, spec] : [null, null];
}
function stateVerb(element, role) {
	const attribute = workRole(element, role)?.state;
	const matches = Object.entries(declarationFor(element, "x-state") ?? {}).filter(([, spec]) => spec.unit === "widget" && spec.record?.kind === "value" && spec.record.attr === attribute).map(([verb]) => verb);
	if (matches.length !== 1) throw new Error(`leaf: $work ${role} <${element.localName}> state ${attribute} needs one recorded widget verb`);
	return matches[0];
}
const roleState = (element, role, read) => read(element).state[stateVerb(element, role)]?.value ?? null;
const actionReports = (element, action) => reportSequence(element).filter((report) => report.source === "report" && report.action === action);
function workerView(worker, read) {
	const role = workRole(worker, "worker");
	const state = roleState(worker, "worker", read);
	const focus = role.on && worker.getAttribute(role.on);
	const [reportVerb] = stateReport(worker, "worker");
	const heard = (reportVerb ? actionReports(worker, reportVerb) : []).at(-1)?.ts ?? saidAt(worker);
	const running = role.running.includes(state);
	const scope = workAncestor(worker, "scope");
	const goal = workAncestor(worker.parentElement, "goal");
	const remit = goal && workAncestor(goal, "scope") === scope ? goal : scope;
	const candidate = focus ? document.getElementById(focus) : null;
	const assignment = candidate && workRole(candidate, "goal") && workAncestor(candidate, "scope") === scope && (remit === scope || remit.contains(candidate)) ? candidate : null;
	return {
		element: worker,
		role,
		state,
		retired: role.retired.includes(state),
		running,
		quiet: running && quietSince(heard),
		heard,
		remit,
		assignment
	};
}
const done = (goal, read) => {
	return workRole(goal, "goal").done.includes(roleState(goal, "goal", read));
};
function interventions(goal, open) {
	const scope = workAncestor(goal, "scope");
	return obligationsIn(goal, open).map((item) => elementById(item.source.id)).filter((item) => item !== goal && !workRole(item, "goal") && workAncestor(item, "scope") === scope && workAncestor(item.parentElement, "goal") === goal && !quoted(item));
}
function stopped(goal, open, nested, read) {
	const role = workRole(goal, "goal");
	if (read(goal).thread.heldBy) return true;
	if (nested.length) return true;
	if (!role.stopped.includes(roleState(goal, "goal", read))) return false;
	if (open.some((item) => item.source.id === goal.id)) return true;
	const children = directWorkElements(goal, "goal");
	return children.length ? children.some((child) => stopped(child, open, interventions(child, open), read)) : true;
}
function goalView(goal, open, read) {
	const leaves = workElements(goal, "goal").filter((item) => !directWorkElements(item, "goal").length);
	const progressLeaves = leaves.length ? leaves : [goal];
	const liveWorkers = directWorkElements(goal, "worker").map((worker) => workerView(worker, read)).filter((worker) => !worker.retired);
	const role = workRole(goal, "goal");
	const state = roleState(goal, "goal", read);
	const [reportVerb] = stateReport(goal, "goal");
	const latestReport = (reportVerb ? actionReports(goal, reportVerb) : []).at(-1);
	const reportedStoppedAt = latestReport?.disposition === "effective" && role.stopped.includes(latestReport.detail.value) ? latestReport.ts : null;
	const nested = interventions(goal, open);
	const held = Boolean(read(goal).thread.heldBy);
	return {
		element: goal,
		role,
		state,
		title: addressableName(goal) || goal.id,
		done: done(goal, read),
		stopped: stopped(goal, open, nested, read),
		held,
		leaves: progressLeaves,
		finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
		liveWorkers,
		stoppedAt: reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null)
	};
}
const openWidgetObligations = readPart((root) => root.effective.obligations.user.filter((item) => item.source.kind === "widget"));
function readWork(scope) {
	const readings = /* @__PURE__ */ new Map();
	const read = (element) => {
		if (!readings.has(element)) readings.set(element, widgetController(element).read());
		return readings.get(element);
	};
	const open = openWidgetObligations();
	const goals = workElements(scope, "goal").map((goal) => goalView(goal, open, read));
	const byElement = new Map(goals.map((goal) => [goal.element, goal]));
	const workers = workElements(scope, "worker").map((worker) => workerView(worker, read));
	const liveWorkers = workers.filter((worker) => !worker.retired);
	const leaves = goals.filter((goal) => !directWorkElements(goal.element, "goal").length);
	const stoppedGoals = goals.filter((goal) => goal.stopped).sort((a, b) => {
		const at = a.stoppedAt ? new Date(a.stoppedAt).getTime() : NaN;
		const bt = b.stoppedAt ? new Date(b.stoppedAt).getTime() : NaN;
		return (Number.isFinite(at) ? at : Infinity) - (Number.isFinite(bt) ? bt : Infinity);
	});
	return {
		scope,
		goals,
		byElement,
		leaves,
		done: leaves.filter((goal) => goal.done).length,
		workers,
		liveWorkers,
		running: liveWorkers.filter((worker) => worker.running && !worker.quiet),
		quiet: liveWorkers.filter((worker) => worker.quiet),
		stopped: stoppedGoals
	};
}

//#endregion
//#region runtime/file-api.js
const live$3 = readPart((root) => root.document.live);
function boundFile(binding) {
	const writable = () => !offlineInteractive && live$3();
	async function request(options = {}) {
		if (!writable()) throw new Error("File editing is available in live pages.");
		try {
			return await requestJson(pageUrl(`api/files/${encodeURIComponent(binding)}`), {
				cache: "no-store",
				...options
			}, "file");
		} catch (error) {
			if (error instanceof LayerRefused) throw new Error("Leaf changed while accessing the file.", { cause: error });
			if (!(error instanceof RequestError)) throw new Error("The page's server did not answer.", { cause: error });
			if (error.said === void 0) throw new Error(error.status < 400 ? "The page's server answered in a form the page cannot read." : `The page's server answered HTTP ${error.status}.`, { cause: error });
			throw error;
		}
	}
	return {
		get writable() {
			return writable();
		},
		read: async () => {
			const file = await request();
			if (file === null) throw new Error(`No file is bound as '${binding}'.`);
			return file;
		},
		save: (snapshot) => request({
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(snapshot)
		}),
		watch(callback) {
			let subscribing = true;
			const stop = applicationState.select((root) => root.authoritative?.files[binding]).subscribe(() => {
				if (!subscribing) callback();
			});
			subscribing = false;
			return stop;
		}
	};
}

//#endregion
//#region runtime/llm-api.js
const live$2 = readPart((root) => root.document.live);
async function generate(request) {
	if (offlineInteractive || !live$2()) throw new Error("LLM generation is available in live pages.");
	return requestJson(pageUrl("api/llm"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(request)
	}, "LLM generation");
}

//#endregion
//#region runtime/http-api.js
const live$1 = readPart((root) => root.document.live);
function connection(name) {
	return { async fetch(path) {
		if (offlineInteractive || !live$1()) throw new Error("HTTP connections are available in live pages.");
		return requestJson(pageUrl(`api/connections/${encodeURIComponent(name)}`), {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ path })
		}, "HTTP connection");
	} };
}

//#endregion
//#region runtime/obligations/tally.js
function tally(held) {
	const open = held.filter((item) => item.status === "open");
	return {
		onUser: open.filter((item) => item.next_actor === "user").length,
		onAgent: open.filter((item) => item.next_actor === "agent").length,
		open: open.length,
		total: held.length
	};
}
function tallyWords({ onUser, onAgent, open, total }, agent) {
	if (!total) return "Nothing to answer";
	if (onUser && onAgent) return `${onUser} left to answer · ${onAgent} on ${agent}`;
	if (onUser) return `${onUser} left to answer`;
	if (onAgent) return `${onAgent} on ${agent}`;
	if (open) return `${open} open`;
	return total === 1 ? "Answered" : `All ${total} answered`;
}

//#endregion
//#region runtime/widget-api.js
async function mountSample(frame, options) {
	return (await import("./bundle-sample.js")).mountSample(frame, options);
}

//#endregion
export { CONTRIBUTION_ENTRY_SCHEMA, DISCLOSE, HOLDS_WORD, HeldReading, LAYOUT, LeafElement, PAGE_INTERFACE, PRESENTATION, PRESS, PRESSABLE, PendingTaskEvent, RequestError, TEXT_BOX, TEXT_FIELD, aborted, actionClass, actionName, actionTemplate, addressableLabel, addressableWord, afterPresentation, afterScript, agentName, ago, alignText, allButCommandReference, anchorLabel, announce, answerWords, answeredInWords, assignRows, atLayoutPrecision, atScrollEnd, authoredScope, axisTicks, backgroundFlash, beginWalk, bodyText, boundFile, cancelAnimation, cancelRender, capturePlace, claimTraversals, classMap, clearDraft, clockValue, closeLayer, closeNativeLayer, commandScope, commandsChanged, commandsOn, comparisonChanges, compoundReadingRegionId, connection, consumeAnnotations, contributionEntry, contributionItemKey, copyBlock, copyControl, createRef, currentLocationIn, cycledRow, dataBody, declarationFor, deferredArrival, describeFailure, directWorkElements, dragging, el, elementById, elementsDeclaring, ensureSyntaxLanguage, excerptWords, failSoft, fitsWhole, flashDuration, focusDestination, focused, foldBlock, foldDuration, fragmentTarget, frameFor, generate, generated, generatedElement, growthIsSeen, guard, handBack, heldGrowth, highlightBlocks, holdAuthoredBody, holdFocus, html, iconElement, iconTemplate, inBaseLayer, inChrome, inlineMarkdownFragment, isCanonicalMediaUrl, isNativeLayer, keepView, keeps, keepsHidden, keepsText, keyed, labelOf, landInThread, landingInsets, langForPath, layerFact, layoutChanged, layoutPx, leafEditorView, listWalkPosition, live, loadDeferred, loadDraft, loadMarkdown, markdownReady, markdownSourceOffset, markdownWords, matchesWhen, measure, motion, motionPreview, mountSample, move, nameAction, namedAction, navigateToDatum, nextAnimation, nextFrame, nextRender, noChange, nothing, notice, obligationActions, obligationsIn, offer, offerAction, offeredActionElement as offerActionElement, offerElement, offered, offeredAction, onCurrentLocation, onMotionPreferenceChange, onPress, onPressAway, onUserInput, once, openLayer, openerOf, openingView, pageScroller, paintMarkdown, placeKeeper, placeOf, placePageThreads, placesFailure, plainPress, presentContributionEntry, presentContributionReceipts, preserveReadingRegions, pressIsKeyboardActivation, projectedDatum, publishOutput, pushEntry, queueActions, queueItemKey, queueTitle, quietSince, quoted, raiseError, rankAt, reachedForWords, readHistory, readObligations, readQueues, readThreads, readWork, reducedMotion, ref, regionScrollBehavior, registerContribution, registerReadingRegion, registerRootHeader, registerThreadPresentation, registerVisualParts, relabel, releaseOutlets, render, renderMarkdown, repeat, replaceEntry, reportFailure, reportSequence, reportsPresented, reportsReady, restorePlace, retainUserIntent, returnDuration, revisionLabel, rove, rowArrows, rowWalk, saidAt, saveDraft, saying, says, scopedMediaUrl, scrollBehavior, scrollIntoReadingBand, scrollIntoView, scrollLimit, scrollerFor, searchField, selectableOffer, selectableOffered, sendDraft, setChildLists, setChildren, setRenderedChildren, setScroll, shadowStage, shortAgo, showNativeLayer, showReadingSubject, shownAnswer, shownWindow, Z as signal, sizeObserver, styleMap, synNodes, syntax, tabStore, tally, tallyWords, textWidth, threadActions, threadBox, threadInput, threadSummary, threadSurface, turns as threadTurns, tokenLines, under, unsafeHTML, viewMembers, watchDraft, watchReadingRegionTransitions, wear, whenLeft, whileConnected, whileInterfaceConnected, widgetController, wireInput, workAncestor, workElements, workRole, worksInside, wrote };