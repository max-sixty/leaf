import { DISCLOSE, HOLDS_WORD, LAYOUT, LeafElement, PRESS, PendingTaskEvent, TEXT_BOX, TEXT_FIELD, Z, actionClass, actionName, actionTemplate, afterScript, announce, assignRows, atLayoutPrecision, atScrollEnd, axisTicks, backgroundFlash, beginWalk, bodyText, cancelAnimation, cancelRender, canvas2D, closeLayer, closeNativeLayer, closestAcross, commandsChanged, currentLocationIn, dataBody, describeFailure, ensureSyntaxLanguage, failSoft, fitsWhole, flashDuration, focusDestination, focused, foldBlock, foldDuration, frameFor, generated, generatedElement, growthIsSeen, handBack, holdFocus, iconElement, iconTemplate, inBaseLayer, inChrome, isNativeLayer, keeps, keepsHidden, keepsText, landingInsets, langForPath, layoutChanged, layoutPx, listWalkPosition, loadDeferred, measure, motion, move, nameAction, namedAction, nextAnimation, nextFrame, nextRender, offer, offerAction, offerElement, offered, offeredAction, offeredActionElement, onCurrentLocation, onMotionPreferenceChange, onPress, onPressAway, onUserInput, once, openLayer, openerOf, pageScroller, placesFailure, plainPress, pressIsKeyboardActivation, publishOutput, reducedMotion, registerVisualParts, relabel, releaseOutlets, reportFailure, retainUserIntent, returnDuration, rove, rowArrows, scrollBehavior, scrollIntoReadingBand, scrollIntoView, scrollLimit, searchField, selectableOffer, selectableOffered, setChildLists, setChildren, setRenderedChildren, setScroll, shadowStage, showNativeLayer, shownWindow, sizeObserver, synNodes, syntax, tabStore, textWidth, threadSurface, tokenLines, under, whenLeft, whileConnected } from "./bundle-portable.js";
import { PRESSABLE, agentName, applicationRegionsPresented, applicationState, commandScope, commandsOn, cycledRow, declarationFor, dragging, el, elementsDeclaring, hasObligationSource, holdAuthoredBody, labelOf, layerFact, matchesWhen, motionPreview, notice, offlineInteractive, pageUrl, projectionRegionsPresented, raiseError, rankAt, reachedForWords, readPart, registry, revisionLabel, saying, turns, worksInside } from "./bundle-errors.js";
import { LayerRefused, RequestError, requestJson } from "./bundle-layer-client.js";
import { PAGE_INTERFACE, PRESENTATION, addressableLabel, addressableName, addressableWord, afterPresentation, ago, clockValue, compoundReadingRegionId, deferredArrival, fragmentTarget, preserveReadingRegions, projectedDatum, quietSince, regionScrollBehavior, registerReadingRegion, scrollerFor, shortAgo, showReadingSubject, watchReadingRegionTransitions, whileInterfaceConnected } from "./bundle-content-layout.js";
import { alignText, authoredScope, elementById, excerptWords, says, wrote } from "./bundle-passages.js";
import { aborted, quoted, widgetDescriptor } from "./bundle-abort.js";
import { HeldReading, allButCommandReference, anchorLabel, answeredInWords, capturePlace, claimTraversals, clearDraft, comparisonChanges, copyBlock, copyControl, heldGrowth, highlightBlocks, inlineMarkdownFragment, keepView, loadDraft, loadMarkdown, markdownReady, markdownSourceOffset, markdownWords, obligationsIn, openingView, paintMarkdown, placeKeeper, placeOf, pushEntry, readObligations, readThreads, renderMarkdown, replaceEntry, restorePlace, rowWalk, saveDraft, sendDraft, threadSummary, viewMembers, watchDraft } from "./bundle-data.js";
import { CONTRIBUTION_ENTRY_SCHEMA, answerWords, consumeAnnotations, contributionEntry, contributionItemKey, currentProjection, landInThread, leafEditorView, navigateToDatum, obligationActions, placePageThreads, presentContributionEntry, presentContributionReceipts, queueActions, queueItemKey, queueTitle, readQueues, registerContribution, registerRootHeader, registerThreadPresentation, threadActions, threadBox, threadInput, widgetController, wireInput } from "./bundle-page-layout.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { classMap, createRef, guard, html, keyed, live, noChange, nothing, ref, render, repeat, styleMap, unsafeHTML } from "./portable-api.js";
import { wear } from "./bundle-dress.js";

//#region runtime/shown-answer.js
const namedValue = (answer, keyOf) => {
	if (!keyOf) return typeof answer === "string" && answer ? answer : null;
	const [only, other] = new Set((Array.isArray(answer) ? answer : []).map((member) => {
		if (typeof member !== "string") throw new Error("A picked answer must name its members by id");
		return keyOf(member);
	}));
	return only !== void 0 && other === void 0 ? only : null;
};
function shownAnswer(view) {
	const shows = declarationFor(view, "x-shows");
	const id = shows && view.getAttribute(shows.attr);
	if (!id) return null;
	const owner = elementById(id, authoredScope(view));
	if (!owner) return null;
	const awaits = declarationFor(owner, "x-awaits");
	const verb = awaits?.value;
	if (!verb || !awaits) return null;
	const record = declarationFor(owner, "x-state")?.[verb]?.record;
	if (record?.kind !== "value" && !(record?.kind === "attribute" && awaits.key)) return null;
	if (!widgetDescriptor(owner)) return null;
	const controller = widgetController(owner);
	const reading = controller.read();
	const state = reading.state?.[verb];
	if (!state) return null;
	const scope = authoredScope(owner);
	const memberKey = record.kind === "attribute" ? awaits.key : null;
	const keyOf = memberKey ? (member) => elementById(member, scope)?.getAttribute(memberKey) ?? null : null;
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
	} else if (target !== null && typeof target === "object" && "kind" in target && "id" in target && (target.kind === "widget" || target.kind === "thread") && typeof target.id === "string" && target.id) return {
		kind: target.kind,
		id: target.id
	};
	throw new TypeError("report target must be a widget element or {kind: 'widget' | 'thread', id}");
}
const targetKey = (target) => target ? JSON.stringify([target.kind, target.id]) : null;
const reportsByTarget = /* @__PURE__ */ new Map();
const reportsFor = (key) => {
	let read = reportsByTarget.get(key);
	if (!read) {
		read = readPart((root) => (root.effective.view?.reports ?? []).filter((report) => key === null || targetKey(report.target) === key));
		reportsByTarget.set(key, read);
	}
	return read();
};
const reportSequence = (target = null) => reportsFor(targetKey(reportTarget(target))).map((report) => structuredClone(report));
const publishedAt = readPart((root) => root.effective.view?.published_at ?? null);
const saidAt = (el) => {
	return (closestAcross(el, ".lf-msg")?.querySelector(":scope > .lf-msg-head time"))?.dateTime || publishedAt();
};
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
function workRole(element, role = null) {
	const spec = element ? widgets()[element.localName] : void 0;
	return spec && (!role || spec.role === role) ? spec : null;
}
const hasRole = (entry, role) => entry[1].role === role;
function workEntries(root, role, { direct = false } = {}) {
	const roles = new Map(Object.entries(widgets()).filter((entry) => hasRole(entry, role)));
	const boundary = workAncestor(root, "scope");
	return [...root.querySelectorAll("*")].flatMap((element) => {
		const declared = roles.get(element.localName);
		return declared && workAncestor(element, "scope") === boundary && (!direct || workAncestor(element.parentElement) === root) ? [{
			element,
			role: declared
		}] : [];
	});
}
function workElements(root, role, options) {
	return workEntries(root, role, options).map(({ element }) => element);
}
const directWorkElements = (root, role) => workElements(root, role, { direct: true });
function workAncestor(element, role) {
	for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
	return null;
}
function stateVerb(element, role) {
	const stamped = registry.$states[element.localName];
	const matches = Object.entries(declarationFor(element, "x-state") ?? {}).flatMap(([verb, spec]) => {
		const state = stamped?.[verb];
		return spec.unit === "widget" && spec.record?.kind === "value" && spec.record.attr === role.state && state ? [{
			verb,
			state
		}] : [];
	});
	const match = matches[0];
	if (!match || matches.length !== 1) throw new Error(`leaf: $work ${role.role} <${element.localName}> state ${role.state} needs one recorded widget verb`);
	return match;
}
function stateReport(element, role) {
	const { verb, state } = stateVerb(element, role);
	return state.writer === "agent" ? verb : null;
}
const roleState = (element, role, read) => {
	const state = read(element).state[stateVerb(element, role).verb];
	return state && "value" in state ? state.value : null;
};
const actionReports = (element, action) => reportSequence(element).filter((report) => report.source === "report" && report.action === action);
function workerView({ element: worker, role }, read) {
	const state = roleState(worker, role, read);
	const focus = role.on && worker.getAttribute(role.on);
	const reportVerb = stateReport(worker, role);
	const heard = (reportVerb ? actionReports(worker, reportVerb) : []).at(-1)?.ts ?? saidAt(worker);
	const running = role.running.some((value) => value === state);
	const scope = workAncestor(worker, "scope");
	const goal = workAncestor(worker.parentElement, "goal");
	const remit = goal && workAncestor(goal, "scope") === scope ? goal : scope;
	const candidate = focus ? document.getElementById(focus) : null;
	const assignment = candidate && workRole(candidate, "goal") && workAncestor(candidate, "scope") === scope && (remit === scope || remit?.contains(candidate)) ? candidate : null;
	return {
		element: worker,
		role,
		state,
		retired: role.retired.some((value) => value === state),
		running,
		quiet: running && quietSince(heard),
		heard,
		remit,
		assignment
	};
}
const done = ({ element: goal, role }, read) => {
	return role.done.some((value) => value === roleState(goal, role, read));
};
function interventions(goal, open) {
	const scope = workAncestor(goal, "scope");
	return obligationsIn(goal, open).map((item) => item.source.kind === "widget" ? elementById(item.source.id) : null).filter((item) => item !== null).filter((item) => item !== goal && !workRole(item, "goal") && workAncestor(item, "scope") === scope && workAncestor(item.parentElement, "goal") === goal && !quoted(item));
}
function stopped(entry, open, nested, read) {
	const { element: goal, role } = entry;
	if (read(goal).thread.heldBy) return true;
	if (nested.length) return true;
	if (!role.stopped.some((value) => value === roleState(goal, role, read))) return false;
	if (open.some((item) => item.source.id === goal.id)) return true;
	const children = workEntries(goal, "goal", { direct: true });
	return children.length ? children.some((child) => stopped(child, open, interventions(child.element, open), read)) : true;
}
function goalView(entry, open, read) {
	const { element: goal, role } = entry;
	const leaves = workEntries(goal, "goal").filter((item) => !directWorkElements(item.element, "goal").length);
	const progressLeaves = leaves.length ? leaves : [entry];
	const liveWorkers = workEntries(goal, "worker", { direct: true }).map((worker) => workerView(worker, read)).filter((worker) => !worker.retired);
	const state = roleState(goal, role, read);
	const reportVerb = stateReport(goal, role);
	const latestReport = (reportVerb ? actionReports(goal, reportVerb) : []).at(-1);
	const reportedStoppedAt = latestReport?.disposition === "effective" && role.stopped.some((value) => value === latestReport.detail.value) ? latestReport.ts : null;
	const nested = interventions(goal, open);
	const held = Boolean(read(goal).thread.heldBy);
	return {
		element: goal,
		role,
		state,
		title: addressableName(goal) || goal.id,
		done: done(entry, read),
		stopped: stopped(entry, open, nested, read),
		held,
		leaves: progressLeaves.map(({ element }) => element),
		finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
		liveWorkers,
		stoppedAt: reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null)
	};
}
const openWidgetObligations = readPart((root) => root.effective.obligations.user.filter((item) => hasObligationSource(item, "widget")));
function readWork(scope) {
	const readings = /* @__PURE__ */ new Map();
	const read = (element) => {
		let reading = readings.get(element);
		if (!reading) {
			reading = widgetController(element).read();
			readings.set(element, reading);
		}
		return reading;
	};
	const open = openWidgetObligations();
	const goals = workEntries(scope, "goal").map((goal) => goalView(goal, open, read));
	const byElement = new Map(goals.map((goal) => [goal.element, goal]));
	const workers = workEntries(scope, "worker").map((worker) => workerView(worker, read));
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
	const writable = () => !offlineInteractive && Boolean(live$3());
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
export { CONTRIBUTION_ENTRY_SCHEMA, DISCLOSE, HOLDS_WORD, HeldReading, LAYOUT, LeafElement, PAGE_INTERFACE, PRESENTATION, PRESS, PRESSABLE, PendingTaskEvent, RequestError, TEXT_BOX, TEXT_FIELD, aborted, actionClass, actionName, actionTemplate, addressableLabel, addressableWord, afterPresentation, afterScript, agentName, ago, alignText, allButCommandReference, anchorLabel, announce, answerWords, answeredInWords, assignRows, atLayoutPrecision, atScrollEnd, authoredScope, axisTicks, backgroundFlash, beginWalk, bodyText, boundFile, cancelAnimation, cancelRender, canvas2D, capturePlace, claimTraversals, classMap, clearDraft, clockValue, closeLayer, closeNativeLayer, commandScope, commandsChanged, commandsOn, comparisonChanges, compoundReadingRegionId, connection, consumeAnnotations, contributionEntry, contributionItemKey, copyBlock, copyControl, createRef, currentLocationIn, cycledRow, dataBody, declarationFor, deferredArrival, describeFailure, directWorkElements, dragging, el, elementById, elementsDeclaring, ensureSyntaxLanguage, excerptWords, failSoft, fitsWhole, flashDuration, focusDestination, focused, foldBlock, foldDuration, fragmentTarget, frameFor, generate, generated, generatedElement, growthIsSeen, guard, handBack, heldGrowth, highlightBlocks, holdAuthoredBody, holdFocus, html, iconElement, iconTemplate, inBaseLayer, inChrome, inlineMarkdownFragment, isCanonicalMediaUrl, isNativeLayer, keepView, keeps, keepsHidden, keepsText, keyed, labelOf, landInThread, landingInsets, langForPath, layerFact, layoutChanged, layoutPx, leafEditorView, listWalkPosition, live, loadDeferred, loadDraft, loadMarkdown, markdownReady, markdownSourceOffset, markdownWords, matchesWhen, measure, motion, motionPreview, mountSample, move, nameAction, namedAction, navigateToDatum, nextAnimation, nextFrame, nextRender, noChange, nothing, notice, obligationActions, obligationsIn, offer, offerAction, offeredActionElement as offerActionElement, offerElement, offered, offeredAction, onCurrentLocation, onMotionPreferenceChange, onPress, onPressAway, onUserInput, once, openLayer, openerOf, openingView, pageScroller, paintMarkdown, placeKeeper, placeOf, placePageThreads, placesFailure, plainPress, presentContributionEntry, presentContributionReceipts, preserveReadingRegions, pressIsKeyboardActivation, projectedDatum, publishOutput, pushEntry, queueActions, queueItemKey, queueTitle, quietSince, quoted, raiseError, rankAt, reachedForWords, readHistory, readObligations, readQueues, readThreads, readWork, reducedMotion, ref, regionScrollBehavior, registerContribution, registerReadingRegion, registerRootHeader, registerThreadPresentation, registerVisualParts, relabel, releaseOutlets, render, renderMarkdown, repeat, replaceEntry, reportFailure, reportSequence, reportsPresented, reportsReady, restorePlace, retainUserIntent, returnDuration, revisionLabel, rove, rowArrows, rowWalk, saidAt, saveDraft, saying, says, scopedMediaUrl, scrollBehavior, scrollIntoReadingBand, scrollIntoView, scrollLimit, scrollerFor, searchField, selectableOffer, selectableOffered, sendDraft, setChildLists, setChildren, setRenderedChildren, setScroll, shadowStage, shortAgo, showNativeLayer, showReadingSubject, shownAnswer, shownWindow, Z as signal, sizeObserver, styleMap, synNodes, syntax, tabStore, tally, tallyWords, textWidth, threadActions, threadBox, threadInput, threadSummary, threadSurface, turns as threadTurns, tokenLines, under, unsafeHTML, viewMembers, watchDraft, watchReadingRegionTransitions, wear, whenLeft, whileConnected, whileInterfaceConnected, widgetController, wireInput, workAncestor, workElements, workRole, worksInside, wrote };