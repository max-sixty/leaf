import { PENDING_TASK, afterScript, bindQueuedWork, byRenderedOrder, composedParentNode, failSoft, failSoftUnreported, frameVisibility, holdRendering, isNativeLayer, nextRender, onFrameVisibility, once, placesFailure, readSampleVisibility, renderedOrder, renderedParent, renderedUnder, reportFailure, shadowHost, sizeObserver, under, upFrom, watchOwner, whileConnected } from "./bundle-portable.js";
import { TEXT_FIELD, Z, canPlaceFocus, closeLayer, d, deepFocus, drawn, focusDestination, focused, handBack, holdFocus, inputCount, keeps, keepsHidden, keepsText, move, onCurrentLocation, onUserInput, openLayer, openerOf, q, takesLetters, whenLeft, x } from "./bundle-dom-move.js";
import { DRAFT_FORMAT, LitElement, PENDING, PRESENTATION_DOM, actionForWidget, agentName, anchorKey, annotationMode, applicationPresenter, applicationState, attachApplicationPresentation, attachWidgetPresentation, closeNativeLayer, discussed, documentChanged, drawingSchema, editable, html, isMessageEvent, isThreadEvent, matchesWhen, moved, offlineInteractive, offlineState, pageUrl, presentDocument, projectionOrigins, queueWidgetUpdate, reactionsAt, readApplication, readPart, registry, render, runtime, setPresentationFailureReporter, shadowRootsIn, showNativeLayer, stateCoordinate, tagsDeclaring, threadKey, tokenChoices, turns, watchPresentation, whenApplicationRegionsPresented, whenDocumentPresented, whenWidgetsPresented } from "./bundle-layer-stack.js";
import { PRESS, TEXT_ENTRY, actionIcon, admitResponse, announce, claimsEsc, commandAvailable, commandBinding, commandRoutes, completeData, controlAvailabilityOutput, countTraffic, cycledRow, dataHeaders, el, elementDirective, generatedElement, holdingError, iconTemplate, isCommandScope, keys, layerHeaders, notice, offer, offerAction, paintKeys, paintKeysWithin, postEvent, pressIsKeyboardActivation, projectCommandScope, raiseError, randomId, recordInteraction, removeRuntimeRootStyle, repaint, reportCarried, reportPageError, responseAction, reveal, rowArrows, sameLayer, savedReadingSettled, saying, sessionIsActive, setRuntimeRootStyle, watchCommandAvailability, watchPendingTraffic } from "./bundle-layer-client.js";
import { activityTransitionDue, addressableLabel, addressableWord, afterPresentation, ago, anchorForRange, anchoringIsReady, commitPoint, declaredName, livePoint, markStateApplied, moveScrollerBy, observeServerNow, observeWorkingGrace, reachScrollers, readingRegionFor, saidNow, scheduleMarginContentLayout, sectionOf, settlePageInterface, syncLayoutRegion, targetSegments, tickClock, visualPartLabel, widgetWord } from "./bundle-content-layout.js";
import { HOLDS_WORD, HeldNews, MessageView, SAYS_IN, THREAD, ThreadView, Transcript, aborted, allButCommandReference, allThreads, anchorLabel, answeredInWords, authoredHolder, authoredStates, awaitsData, beginThreadSeats, beginWalk, bindsInput, bringBackSurfaceOf, claimed, clearDraft, commitThreadSeats, commitWidgetDescriptors, comparisonBase, comparisonChanges, completeReadingReturn, createProjectionPresentation, createReplyView, dataReader, declareSide, descriptorStillMatches, dismissReplyAt, draftContexts, drawnThreadId, focusThread, focusedThreadTarget, heldOut, heldThread, holdReplyCompositions, holdThreadPlace, inlineComparison, isPageWidgetWorkflow, isWorkflowProgress, joinDataDelivery, keepRefusedWords, listWalkPosition, loadDraft, loadDraftPayload, loadMarkdown, loadMessageMarkdown, markdownReady, messageHolding, messageReading, messageText, mountFirstMessage, newsNotice, obligationHolding, obligationPlace, openMessageEditIn, orderChildren, pageCommand, pageScope, pageSelection, placeOf as placeOf$1, placePageThreads as placePageThreads$1, placedMarkdownTokens, prepareAuthoredMessage, progressFace, quoted as quoted$1, readObligations, readThreads, readingReturn, registerWritingDestination, rememberWriting, renderMarginThread, renderSeats, renderSurfaces, replyAvailable, replyDraftContext, replyThreadKey, retainThreadSeats, revealHeld, saveDraft, sendLanding, sendMessage, setChildren, settleAcceptedDrafts, showHeld, showHeldThread, strongestWorkflow, suppliedSnapshot, surfaceFocusTarget, threadAttention, threadDraft, threadIdNamed, threadIn, threadList, threadName, threadNamed, threadPart, threadReading as threadReading$1, threadReplyInput, threadRewrites, threadState, todoLabel, toggleInlineComparison, transferDraft, watchDraft, watchDrafts, watchThreadSurfaces, wholeThread, widgetDescriptor, workflowLabel, workflowVoice } from "./bundle-data.js";
import { clamp, clippedContents, clipsPastSurfaces, growthIsSeen, hasArea, intersect, layoutWindow, placeBox, placeHolder, presented as presented$1, seenRect, shownWindow, union, watchRoom, whenNone } from "./bundle-geometry.js";
import { closestAcross, elementById, excerptWords, inChrome, labelWords, leafSurface, pageParts, pageReadingVersion, quoteFrom, textNodesUnder } from "./bundle-passages.js";
import { alreadyShown, fitsWhole, restrictUserIntent, retainUserIntent, scrollIntoReadingBand, scrollIntoView } from "./bundle-copy-control.js";
import { agentArrivalDuration, isCanonicalMediaUrl, reducedMotion, scopedMediaUrl, scrollBehavior } from "./bundle-media.js";
import { visibleTargetParts } from "./bundle-visible-target-parts.js";

//#region runtime/pending/state.js
function createPendingLedger({ newAttempt, enqueue }) {
	const handles = /* @__PURE__ */ new Map();
	const snapshot = () => readApplication().unresolved;
	const sending = () => readApplication().effective.sending;
	return {
		enqueue(event) {
			const attempted = {
				...event,
				attempt: event.attempt || newAttempt()
			};
			if (applicationState.entry(attempted.attempt)) return null;
			const { promise: answer, resolve } = Promise.withResolvers();
			const { promise: read, resolve: resolveRead } = Promise.withResolvers();
			const current = () => applicationState.entry(attempted.attempt);
			const handle = {
				get event() {
					return current()?.event ?? attempted;
				},
				get admitted() {
					return current()?.admitted ?? null;
				},
				answer,
				read,
				resolve(value) {
					resolve(value);
					handles.delete(attempted.attempt);
				},
				resolveRead
			};
			handles.set(attempted.attempt, handle);
			enqueue(attempted);
			return handle;
		},
		snapshot,
		nextSending: () => {
			const [attempt] = sending();
			return attempt ? handles.get(attempt) : null;
		},
		releasable: () => applicationState.releasable(),
		release: (entries) => applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
		refuse(entry) {
			return applicationState.refuse(entry.event.attempt).flatMap((attempt) => {
				const handle = handles.get(attempt);
				handle?.resolve(null);
				return handle ? [{
					attempt,
					answer: handle.answer
				}] : [];
			});
		},
		accept(entry, event) {
			applicationState.accept(entry.event.attempt, event);
		},
		present(receipts) {
			applicationState.present(receipts);
			for (const receipt of receipts) if (receipt.attempt) handles.get(receipt.attempt)?.resolveRead(receipt);
		},
		nameEvents(entry) {
			return applicationState.nameEvents(entry.event.attempt);
		}
	};
}

//#endregion
//#region runtime/pending/dispatch.js
function createCommandDispatch() {
	const submitted = /* @__PURE__ */ new Set();
	const ledger = createPendingLedger({
		newAttempt: randomId,
		enqueue: (event) => {
			if (!submitted.has(event.attempt)) {
				submitted.add(event.attempt);
				recordInteraction("event_submit", {
					kind: event.kind,
					attempt: event.attempt
				});
			}
			return applicationState.enqueue(event, saidNow(), isThreadEvent(event) ? messageText(event) : void 0);
		}
	});
	let dependencies = null;
	const current = () => {
		if (!dependencies) throw new Error("Leaf application has not been mounted");
		return dependencies;
	};
	const startPost = (event) => {
		const { onCollision, afterEnqueue } = current();
		const entry = ledger.enqueue(event);
		if (!entry) {
			onCollision(event.attempt);
			return null;
		}
		afterEnqueue(entry);
		return entry;
	};
	const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);
	const dispatchWidget = (descriptor, command) => {
		const { withdraw } = current();
		const reading = applicationState.selectWidget(descriptor).read();
		if (command.kind === "undo") {
			const candidate = Object.values(reading.actions).flatMap(({ undo }) => undo).find((event) => "attempt" in event && event.attempt === command.target || event.id === command.target);
			return candidate ? withdraw(candidate) : null;
		}
		const revision = readApplication().document.revision;
		if (revision === null) return null;
		const action = reading.actions[command.verb];
		if (!action) throw new Error(`<${descriptor.tag} id="${descriptor.id}"> cannot dispatch ${JSON.stringify(command.verb)}; its user verbs are: ${Object.keys(reading.actions).join(", ") || "none"}`);
		if (!action.available) return null;
		const entry = startPost(actionForWidget(descriptor, command, revision));
		if (!entry) return null;
		if (command.says) current().named(entry, command.says);
		return entry.answer;
	};
	return Object.freeze({
		ledger,
		mount(installed) {
			dependencies = installed;
		},
		post,
		dispatchWidget
	});
}

//#endregion
//#region runtime/delivery.js
const RETRY_MS = 2e3;
const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));
const acceptedAnswer = (response, answer) => response.ok && !!answer && "state" in answer && !("final" in answer);
const refusedAnswer = (answer) => !!answer && "final" in answer;
const applyAnswerState = (apply, state) => apply(state).catch((error) => reportCarried(error, "state in event response"));
function createDelivery({ ledger, applyAcceptedState, settleRejected, settlementChanged, refusedWords }) {
	let draining = false;
	async function deliver(entry) {
		const retrying = holdingError();
		const retry = async (message) => {
			retrying(message);
			await retryPause();
		};
		try {
			return await tries(entry, retry);
		} finally {
			retrying(null);
		}
	}
	async function tries(entry, retry) {
		for (;;) {
			if (!ledger.nameEvents(entry)) return { accepted: null };
			const { event } = entry;
			if (entry.admitted) return { accepted: entry.admitted };
			const held = runtime.data;
			const sent = await Promise.race([postEvent(event, held).then((response) => ({ response }), (error) => ({ error })), entry.read.then((accepted) => ({ accepted }))]);
			if (sent.accepted) return { accepted: sent.accepted };
			if (sent.error) {
				await retry(runtime.keyRefused ? "This tab lost access — open the link again in a new tab and this goes through" : "Lost the connection — keep this page open and this goes through");
				continue;
			}
			if (!sent.response) return { accepted: null };
			if (sent.response.status === 503) {
				await retry("Not through yet — trying again…");
				continue;
			}
			const decoded = await Promise.race([sent.response.json().then((answer) => ({ answer }), (error) => ({ error })), entry.read.then((accepted) => ({ accepted }))]);
			if (decoded.accepted) return { accepted: decoded.accepted };
			if (decoded.error) {
				await retry("Not through yet — trying again…");
				continue;
			}
			const answer = decoded.answer;
			if (acceptedAnswer(sent.response, answer)) {
				const accepted = answer.state.browser?.receipts?.find((candidate) => candidate.attempt === event.attempt);
				if (accepted) return {
					accepted,
					application: applyAnswerState(applyAcceptedState, completeData(answer.state, held))
				};
			}
			if (refusedAnswer(answer) && (!("attempt" in answer) || answer.attempt === event.attempt)) return {
				accepted: null,
				state: completeData(answer.state, held),
				refusal: `Couldn't ${event.kind === "edit" ? "save the edit" : "take this"} — ${answer.error || "it was refused"}`
			};
			await retry("Not through yet — trying again…");
		}
	}
	async function drain() {
		if (draining) return;
		draining = true;
		try {
			for (;;) {
				const entry = ledger.nextSending();
				if (!entry) break;
				const { accepted, application, refusal, state } = await deliver(entry);
				if (accepted) ledger.accept(entry, accepted);
				let dependents = [];
				try {
					if (!accepted) dependents = await settleRejected(entry, state);
					settlementChanged(entry, accepted);
				} catch (error) {
					reportCarried(error, "event settlement");
				} finally {
					if (application) application.finally(() => entry.resolve(accepted));
					else {
						entry.resolve(accepted);
						if (refusal) {
							const refused = [{
								attempt: entry.event.attempt,
								answer: entry.answer
							}, ...dependents];
							Promise.all(refused.map(({ answer }) => answer)).then(() => afterScript(() => {
								const { said, field } = refusedWords(refused.map(({ attempt }) => attempt));
								raiseError(said ? `${refusal}. ${said}` : refusal, { subject: field });
							}));
						}
					}
				}
			}
		} finally {
			draining = false;
		}
	}
	return { drain };
}
async function deliverBookkeeping(event, applyState) {
	const held = runtime.data;
	let response;
	try {
		response = await postEvent(event, held);
	} catch {
		return "unreached";
	}
	if (!response || response.status === 503) return "unreached";
	let answer;
	try {
		answer = await response.json();
	} catch {
		return "unreached";
	}
	if (answer && "state" in answer) await applyAnswerState(applyState, completeData(answer.state, held));
	return acceptedAnswer(response, answer) ? "accepted" : refusedAnswer(answer) ? "refused" : "unreached";
}

//#endregion
//#region runtime/contribution-model.js
const entryRecords = /* @__PURE__ */ new WeakSet();
const isContributionEntry = (entry) => entryRecords.has(entry);
const CONTRIBUTION_ENTRY_SCHEMA = Object.freeze({
	tones: Object.freeze([
		"neutral",
		"positive",
		"negative"
	]),
	behaviors: Object.freeze([
		"action",
		"disclosure",
		"status"
	]),
	states: Object.freeze([
		"idle",
		"engaged",
		"busy",
		"failed"
	]),
	ranks: Object.freeze([
		"complete",
		"escape",
		"primary",
		"secondary",
		"reading",
		"overflow"
	])
});
const TONES = new Set(CONTRIBUTION_ENTRY_SCHEMA.tones);
const BEHAVIORS = new Set(CONTRIBUTION_ENTRY_SCHEMA.behaviors);
const STATES = new Set(CONTRIBUTION_ENTRY_SCHEMA.states);
const RANKS = new Set(CONTRIBUTION_ENTRY_SCHEMA.ranks);
const STATE_PRIORITY = /* @__PURE__ */ new Map([
	["failed", 0],
	["busy", 1],
	["engaged", 2],
	["idle", 3]
]);
const RANK_PRIORITY = /* @__PURE__ */ new Map([
	["complete", 0],
	["escape", 1],
	["primary", 2],
	["secondary", 3],
	["reading", 4],
	["overflow", 5]
]);
const ENTRY_OPTIONS = /* @__PURE__ */ new Set([
	"key",
	"glyph",
	"action",
	"icon",
	"label",
	"voice",
	"accessibleLabel",
	"context",
	"description",
	"behavior",
	"tone",
	"rank",
	"state",
	"visible",
	"disabled",
	"count",
	"pressed",
	"workflowReceipt",
	"relation",
	"activation",
	"title",
	"className",
	"scope"
]);
const KINDS = Object.freeze(Object.fromEntries(Object.entries({
	action: {
		label: "Action",
		icon: "dot",
		priority: -1
	},
	change: {
		label: "Change",
		icon: "change",
		priority: 0
	},
	restated: {
		label: "Rewritten",
		icon: "change",
		priority: 0,
		indication: true
	},
	comment: {
		label: "Thread",
		icon: "comment",
		priority: 1
	},
	"on-me": {
		label: "On me",
		icon: "question",
		priority: 2
	},
	sent: {
		label: "Queued",
		icon: "sent",
		priority: 3,
		indication: true
	},
	queued: {
		label: "Up next",
		icon: "pickup",
		priority: 3,
		indication: true
	},
	pickup: {
		label: "Got it",
		icon: "pickup",
		priority: 3,
		indication: true
	},
	waiting: {
		label: "Stalled update",
		icon: "waiting",
		priority: 3,
		indication: true
	},
	user: {
		label: "My change",
		icon: "change",
		priority: 4,
		indication: true
	},
	reported: {
		label: "Reported state",
		icon: "activity",
		priority: 4,
		indication: true
	},
	activity: {
		label: "Working",
		icon: "activity",
		priority: 4
	}
}).map(([kind, face]) => [kind, Object.freeze(face)])));
const READING_OPTIONS = /* @__PURE__ */ new Set([
	"kind",
	"subject",
	"state",
	"side",
	"notice",
	"entries",
	"readings"
]);
const text$1 = (value) => String(value ?? "").trim();
const unknownOptions = (offered, allowed, kind) => {
	const unknown = Object.keys(offered).filter((key) => !allowed.has(key));
	if (unknown.length) throw new TypeError(`Unknown contribution ${kind} option: ${unknown.sort().join(", ")}`);
};
const freezeRelation = (relation) => {
	if (relation == null) return null;
	if (relation.kind === "entries") {
		const keys = relation.keys?.map(text$1).filter(Boolean) ?? [];
		if (!keys.length) throw new TypeError("A contribution entry relation needs at least one entry key");
		return Object.freeze({
			kind: "entries",
			keys: Object.freeze(keys),
			expanded: Boolean(relation.expanded)
		});
	}
	if (relation.kind === "element") {
		const id = text$1(relation.id);
		if (!id) throw new TypeError("A margin element relation needs an id");
		return Object.freeze({
			kind: "element",
			id,
			expanded: Boolean(relation.expanded),
			popup: relation.popup == null ? null : text$1(relation.popup)
		});
	}
	throw new TypeError(`Unknown contribution entry relation: ${String(relation.kind)}`);
};
function contributionEntry$1(offered) {
	unknownOptions(offered, ENTRY_OPTIONS, "entry");
	const { key, glyph = null, action = null, icon: mark = null, label, voice = "agent", accessibleLabel = null, context = null, description = null, behavior = "action", tone = "neutral", rank = "primary", state = "idle", visible = true, disabled = false, count = 1, pressed = null, workflowReceipt = void 0, relation = null, activation = key, title = null, className = null, scope = null } = offered;
	if (!text$1(key)) throw new TypeError("A contribution entry needs a key");
	if ([
		text$1(glyph),
		action,
		mark
	].filter(Boolean).length !== 1) throw new TypeError("A contribution entry needs exactly one glyph, action or icon");
	const icon = action ? actionIcon(action) : mark;
	if (!text$1(label)) throw new TypeError("A contribution entry needs a label");
	if (!TONES.has(tone)) throw new TypeError(`Unknown contribution entry tone: ${tone}`);
	if (!BEHAVIORS.has(behavior)) throw new TypeError(`Unknown contribution entry behavior: ${behavior}`);
	if (!RANKS.has(rank)) throw new TypeError(`Unknown contribution entry rank: ${rank}`);
	if (!STATES.has(state)) throw new TypeError(`Unknown contribution entry state: ${state}`);
	if (!Number.isSafeInteger(count) || count < 0) throw new TypeError("A contribution entry count must be a non-negative integer");
	if (behavior !== "status" && !text$1(activation)) throw new TypeError("An actionable contribution entry needs an activation");
	if (behavior === "status" && scope != null) throw new TypeError("A status contribution entry cannot have a command scope");
	const record = Object.freeze({
		key: text$1(key),
		glyph: glyph == null ? null : String(glyph),
		icon,
		label: text$1(label),
		voice,
		accessibleLabel: text$1(accessibleLabel) || text$1(label),
		context: text$1(context) || null,
		description: text$1(description) || null,
		behavior,
		tone,
		rank,
		state,
		visible: Boolean(visible),
		disabled: Boolean(disabled),
		count,
		pressed: pressed == null ? null : Boolean(pressed),
		workflowReceipt,
		relation: freezeRelation(relation),
		activation: behavior === "status" ? null : text$1(activation),
		title: text$1(title) || null,
		className: text$1(className) || null
	});
	entryRecords.add(record);
	return record;
}
function normalizeContributionReading(reading, owner) {
	unknownOptions(reading, READING_OPTIONS, "contribution");
	const { kind = null, subject = null, state = "idle", side = "before", notice = null, entries = [], readings = [] } = reading;
	if (!STATES.has(state)) throw new TypeError(`Unknown contribution state: ${state}`);
	if (kind != null && !Object.hasOwn(KINDS, kind)) throw new TypeError(`Unknown contribution kind "${kind}" in contribution "${owner}"`);
	if (side !== "before" && side !== "after") throw new TypeError(`Unknown contribution side: ${side}`);
	const keys = /* @__PURE__ */ new Set();
	const normalizedEntries = entries.map((entry) => {
		const normalized = entryRecords.has(entry) ? entry : contributionEntry$1(entry);
		if (keys.has(normalized.key)) throw new TypeError(`Duplicate contribution entry key "${normalized.key}" in contribution "${owner}"`);
		keys.add(normalized.key);
		const owned = Object.freeze({
			...normalized,
			owner
		});
		entryRecords.add(owned);
		return owned;
	});
	const ids = /* @__PURE__ */ new Set();
	for (const item of readings) {
		if (typeof item.id !== "string" || !item.id.trim() || ids.has(item.id)) throw new TypeError(`Contribution reading IDs must be nonempty and unique in contribution "${owner}"`);
		ids.add(item.id);
	}
	const normalizedNotice = notice == null ? null : Object.freeze({
		text: text$1(notice.text),
		tone: text$1(notice.tone) || "negative"
	});
	return Object.freeze({
		kind: text$1(kind) || null,
		subject: text$1(subject) || null,
		state,
		side,
		notice: normalizedNotice,
		entries: Object.freeze(normalizedEntries),
		readings: Object.freeze(readings.map(({ activate, ...item }) => Object.freeze(item)))
	});
}
const contributionEntryStateRank = (state) => STATE_PRIORITY.get(state);
const contributionState = (offered) => offered.reading.state;
function compareContributions(left, right) {
	return STATE_PRIORITY.get(left.reading.state) - STATE_PRIORITY.get(right.reading.state) || left.key.localeCompare(right.key);
}
function compareContributionEntryRecords(left, right) {
	const state = STATE_PRIORITY.get(left.offered.reading.state) - STATE_PRIORITY.get(right.offered.reading.state);
	if (state) return state;
	const rank = RANK_PRIORITY.get(left.record.rank) - RANK_PRIORITY.get(right.record.rank);
	if (rank) return rank;
	return left.offered.key.localeCompare(right.offered.key) || left.record.key.localeCompare(right.record.key);
}
const visibleContributionEntryLabel = ({ behavior, label }) => behavior !== "disclosure" || /[…?]$/.test(label) ? label : `${label}…`;
const contributionItemKey = (item) => JSON.stringify([item.owner ?? null, item.id]);
const SPOKEN_SUBJECT_CAP = 120;
const spokenSubject = (value) => excerptWords(value, SPOKEN_SUBJECT_CAP);

//#endregion
//#region runtime/contribution-controls.js
const commandScopes = /* @__PURE__ */ new WeakMap();
const commandEntries = /* @__PURE__ */ new WeakSet();
const contributionOwnsCommand = (record) => commandEntries.has(record);
const CONTRIBUTION_ENTRY = Symbol("contribution entry");
function bindScope(record, declared) {
	const scope = commandScopes.get(declared) ?? declared.scope;
	if (scope != null) commandScopes.set(record, scope);
	if (contributionOwnsCommand(declared)) commandEntries.add(record);
	return record;
}
function contributionEntry(offered) {
	const scope = commandScopes.get(offered) ?? offered.scope;
	if (scope != null && !isCommandScope(scope)) throw new TypeError("A margin entry scope needs a commandScope capability");
	const command = entryCommand(scope, offered.activation);
	if (command) commandEntries.add(offered);
	return bindScope(contributionEntry$1(contributionOwnsCommand(offered) ? {
		...offered,
		disabled: commandDisabled(scope, command)
	} : offered), offered);
}
function contributionCommand(record) {
	if (!contributionOwnsCommand(record)) return null;
	return entryCommand(commandScopes.get(record), record.activation);
}
function contributionCommandDisabled(record) {
	const scope = commandScopes.get(record);
	const command = contributionCommand(record);
	return contributionOwnsCommand(record) && commandDisabled(scope, command);
}
const commandDisabled = (scope, command) => Boolean(!command || scope.scope.when && !scope.scope.when() || !commandAvailable(command.row, command.route));
function entryCommand(scope, id) {
	for (const row of scope?.scope.rows ?? []) {
		if (!row.run) continue;
		const routes = commandRoutes(row);
		if (!routes.length && row.id === id) return {
			row,
			route: null,
			binding: commandBinding(row)
		};
		const route = routes.find((route) => route.id === id);
		if (route) return {
			row,
			route,
			binding: commandBinding(row, route)
		};
	}
	return null;
}
function normalizeReading(reading, owner, previous = null) {
	const priorEntries = new Map((previous?.entries ?? []).map((entry) => [entry.key, entry]));
	const entries = (reading.entries ?? []).map((entry) => {
		const prior = priorEntries.get(entry.key);
		if (contributionOwnsCommand(prior) && entry.activation === prior.activation && (commandScopes.get(entry) ?? entry.scope) === commandScopes.get(prior)) commandEntries.add(entry);
		if (!isContributionEntry(entry)) return contributionEntry(entry);
		if (!contributionOwnsCommand(entry)) return entry;
		const { owner: _owner, ...fields } = entry;
		const declaration = {
			...fields,
			scope: commandScopes.get(entry)
		};
		commandEntries.add(declaration);
		return contributionEntry(declaration);
	});
	const normalized = normalizeContributionReading({
		...reading,
		entries
	}, owner);
	normalized.entries.forEach((entry, index) => bindScope(entry, entries[index]));
	return normalized;
}
const contributionControls = /* @__PURE__ */ new WeakMap();
let relationOrdinal = 0;
const presented = /* @__PURE__ */ new WeakMap();
const records = /* @__PURE__ */ new WeakMap();
const controlContributions = /* @__PURE__ */ new WeakMap();
const contributorClasses = /* @__PURE__ */ new WeakMap();
function createContributionControl(record, className = "") {
	return offer(record.behavior === "status" ? "span" : "button", className);
}
const contributionControlMatches = (control, record) => record.behavior === "status" ? control instanceof HTMLSpanElement : control instanceof HTMLButtonElement;
function contributionEntryRecord(control) {
	const record = records.get(control);
	if (!record) throw new TypeError("A presented margin control needs a margin entry record");
	return record;
}
function contributionControlKey(control) {
	const { owner, key } = contributionEntryRecord(control);
	return JSON.stringify([owner, key]);
}
function contributionEntrySource(control) {
	const offered = controlContributions.get(control);
	if (!offered) return null;
	return offered.source();
}
const agentWorkflowDescriptions = /* @__PURE__ */ new WeakMap();
const claimArrivals = /* @__PURE__ */ new Map();
const controlArrivals = /* @__PURE__ */ new WeakMap();
function agentWorkflowDescription(control) {
	let reading = agentWorkflowDescriptions.get(control);
	if (!reading) {
		reading = {
			description: control.getAttribute("aria-description"),
			title: control.getAttribute("title"),
			stage: null,
			word: null,
			detail: null
		};
		agentWorkflowDescriptions.set(control, reading);
	}
	return reading;
}
function syncAgentArrival(control, claim, stage) {
	if (stage !== "working") {
		control.removeAttribute("data-lf-agent-arrival");
		return;
	}
	if (!claimArrivals.has(claim)) claimArrivals.set(claim, performance.now());
	const elapsed = performance.now() - claimArrivals.get(claim);
	if (controlArrivals.get(control) === claim) return;
	controlArrivals.set(control, claim);
	if (elapsed >= agentArrivalDuration() || reducedMotion()) return;
	control.style.setProperty("--lf-agent-arrival-delay", `${-elapsed}ms`);
	keeps(control, "data-lf-agent-arrival", "1");
	control.addEventListener("animationend", () => control.removeAttribute("data-lf-agent-arrival"), { once: true });
}
function paintAgentDescription(control) {
	const reading = agentWorkflowDescriptions.get(control);
	if (!reading) {
		control.removeAttribute("aria-description");
		control.removeAttribute("title");
		paintLabelMore(control, null);
		return;
	}
	const record = records.get(control);
	paintLabelMore(control, [
		reading.title !== record?.label && reading.title,
		reading.stage && reading.word,
		reading.stage && reading.detail
	].filter(Boolean).join(" · "));
	if (!reading.stage) {
		for (const [attribute, value] of [["aria-description", reading.description], ["title", reading.title]]) keeps(control, attribute, value);
		return;
	}
	const work = [reading.word, reading.detail].filter(Boolean).join(" · ");
	keeps(control, "aria-description", [reading.description, work].filter(Boolean).join(" · "));
	keeps(control, "title", [
		record?.title ?? record?.label,
		reading.title !== (record?.title ?? record?.label) && reading.title,
		work
	].filter(Boolean).join(" · "));
}
function paintLabelMore(control, more) {
	const line = control.querySelector(":scope > .lf-margin-entry-label > .lf-margin-entry-more");
	if (line) keepsText(line, more ?? "");
}
function syncAgentDescriptionBase(control, description, title) {
	Object.assign(agentWorkflowDescription(control), {
		description,
		title
	});
	paintAgentDescription(control);
}
function syncContributionAgentWorkflow(control, receipt) {
	const paintedStage = progressFace(receipt);
	syncAgentArrival(control, receipt && JSON.stringify([
		receipt.subject.kind,
		receipt.subject.id,
		receipt.id
	]), paintedStage);
	const reading = agentWorkflowDescription(control);
	keeps(control, "data-lf-agent-workflow", paintedStage || null);
	Object.assign(reading, paintedStage ? {
		stage: paintedStage,
		word: workflowLabel(receipt, agentName()),
		detail: receipt.detail
	} : {
		stage: null,
		word: null,
		detail: null
	});
	paintAgentDescription(control);
}
function syncContributionSelection(control, selected) {
	control.toggleAttribute("data-lf-target-selected", Boolean(selected));
}
function syncContributionTurn(control, awaitsUser) {
	keeps(control, "data-lf-turn", awaitsUser ? "user" : null);
}
function syncContributionUnread(control, count) {
	control.toggleAttribute("data-lf-unread", Boolean(count));
}
function presentContributionHost(control, offered, { accessibleLabel = null, relatedControlIds = [], writesRelation = true, writesSeat = true } = {}) {
	const record = isContributionEntry(offered) ? offered : contributionEntry(offered);
	if (control instanceof HTMLButtonElement && record.behavior === "status") throw new TypeError("A status margin entry needs a stable span host");
	controlAvailabilityOutput(control, CONTRIBUTION_ENTRY, contributionOwnsCommand(record) ? {
		disabled: control instanceof HTMLButtonElement,
		ariaDisabled: true
	} : null);
	records.set(control, record);
	keeps(control, "data-lf-margin-entry-key", record.key);
	keeps(control, "data-lf-margin-entry-owner", record.owner || null);
	keeps(control, "data-lf-margin-entry-identity", JSON.stringify([record.owner, record.key]));
	keeps(control, "data-lf-behavior", record.behavior);
	keeps(control, "data-lf-tone", record.tone);
	keeps(control, "data-lf-rank", record.rank);
	keeps(control, "data-lf-state", record.state);
	keeps(control, "data-lf-offer", record.behavior === "status" ? "" : "button");
	keeps(control, "aria-pressed", record.pressed);
	keeps(control, "aria-busy", record.state === "busy" ? "true" : null);
	const relation = record.relation;
	if (writesRelation) {
		keeps(control, "aria-expanded", record.behavior === "disclosure" ? relation?.expanded ?? false : null);
		keeps(control, "aria-controls", relation?.kind === "element" ? relation.id : relation?.kind === "entries" && relatedControlIds.length ? relatedControlIds.join(" ") : null);
		keeps(control, "aria-haspopup", relation?.popup || null);
	}
	if (control instanceof HTMLButtonElement) {
		const wasStatus = control.getAttribute("role") === "status";
		control.removeAttribute("role");
		if (writesSeat && wasStatus) control.removeAttribute("tabindex");
		if (control.type !== "button") control.type = "button";
		if (control.disabled) control.disabled = false;
		keeps(control, "aria-disabled", record.disabled);
	} else if (record.behavior === "status") {
		keeps(control, "role", "status");
		control.removeAttribute("aria-disabled");
		if (writesSeat) keeps(control, "tabindex", -1);
	} else {
		keeps(control, "role", "button");
		keeps(control, "aria-disabled", record.disabled);
		if (writesSeat && control.tabIndex < 0) control.tabIndex = 0;
	}
	keeps(control, "aria-label", accessibleLabel ?? record.accessibleLabel);
	syncAgentDescriptionBase(control, record.description || null, record.title || null);
	projectCommandScope(control, CONTRIBUTION_ENTRY, commandScopes.get(record));
	return record;
}
const contributionHost = elementDirective("contributionHost", (control, source, surface, record, options) => {
	presentContributionHost(control, record, options);
	trackContributionControl(source, surface, record.key, control);
});
function presentContributionReceipts(control, receipt, awaitsUser) {
	syncContributionAgentWorkflow(control, receipt);
	syncContributionTurn(control, awaitsUser);
}
const contributionReceipts = elementDirective("contributionReceipts", presentContributionReceipts);
function presentContributionEntry(control, offered, options = {}) {
	const record = presentContributionHost(control, offered, options);
	if (Object.hasOwn(options, "selected")) syncContributionSelection(control, options.selected);
	control.classList.toggle("lf-margin-entry", true);
	control.classList.toggle(HOLDS_WORD, true);
	const priorClasses = contributorClasses.get(control) ?? [];
	const nextClasses = record.className?.split(/\s+/).filter(Boolean) ?? [];
	for (const name of priorClasses) if (!nextClasses.includes(name)) control.classList.toggle(name, false);
	for (const name of nextClasses) control.classList.toggle(name, true);
	contributorClasses.set(control, nextClasses);
	const visibleLabel = visibleContributionEntryLabel(record);
	const glyph = record.icon ? iconTemplate(record.icon) : html`<span class="lf-margin-entry-glyph" aria-hidden="true"
        >${record.glyph}</span
      >`;
	render(html`${glyph}<span class="lf-margin-entry-space" aria-hidden="true"> </span
      ><span class="lf-margin-entry-label" aria-hidden="true"
        ><span class="lf-margin-entry-label-word" data-voice=${record.voice}
          >${visibleLabel}</span
        >${record.context ? html`<span class="lf-margin-entry-context">${record.context}</span>` : null}<span class="lf-margin-entry-more"></span></span
      >${record.count > 1 ? html`<span class="lf-margin-count" aria-hidden="true"
              >${record.count}</span
            >` : null}`, control);
	paintAgentDescription(control);
	return control;
}
function trackContributionControl(offered, surface, key, control) {
	controlContributions.set(control, offered);
	let surfaces = presented.get(offered);
	if (!surfaces) {
		surfaces = /* @__PURE__ */ new Map();
		presented.set(offered, surfaces);
	}
	let controls = surfaces.get(surface);
	if (!controls) {
		controls = /* @__PURE__ */ new Map();
		surfaces.set(surface, controls);
	}
	controls.set(key, control);
}
function clearContributionControls(offered, surface, liveKeys) {
	const controls = presented.get(offered)?.get(surface);
	if (!controls) return;
	for (const [key, control] of controls) {
		if (liveKeys.has(key)) continue;
		controls.delete(key);
		if (![...presented.get(offered).values()].some((seats) => [...seats.values()].includes(control))) releaseContributionControl(control);
	}
}
function contributionControl(offered, entryKey, surface = null, visible = false) {
	const surfaces = presented.get(offered);
	for (const name of surface ? [surface] : [
		"margin",
		"page",
		"map",
		"inline"
	]) {
		const control = surfaces?.get(name)?.get(entryKey);
		if (control?.isConnected && (!visible || control.checkVisibility())) return control;
	}
	return null;
}
function contributionContains(offered, node) {
	if (!(node instanceof Node)) return false;
	return [...presented.get(offered)?.values() ?? []].some((controls) => [...controls.values()].some((control) => control === node || control.contains(node)));
}
function releaseContributionControl(control) {
	controlAvailabilityOutput(control, CONTRIBUTION_ENTRY);
	projectCommandScope(control, CONTRIBUTION_ENTRY, null);
	controlContributions.delete(control);
}
function forgetContributionControls(offered) {
	for (const controls of presented.get(offered)?.values() ?? []) for (const control of controls.values()) releaseContributionControl(control);
	presented.delete(offered);
}
function activateContributionControl({ offered, entry, control, surface, event }, reveal = null) {
	return offered.registration.activate(entry.key, {
		origin: control,
		surface,
		input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
		focus: (key) => {
			const destination = offered.registration.control(key, surface, true);
			if (!destination) return false;
			reveal?.(destination);
			focusDestination(destination, "return");
			return true;
		}
	});
}
function materializeContributionControls(source, surface, activate) {
	let controls = contributionControls.get(source);
	if (!controls) {
		controls = /* @__PURE__ */ new Map();
		contributionControls.set(source, controls);
	}
	const entries = source.reading.entries.filter((entry) => entry.visible);
	const liveKeys = new Set(entries.map((entry) => entry.key));
	const changed = /* @__PURE__ */ new Set();
	for (const key of controls.keys()) if (!liveKeys.has(key)) controls.delete(key);
	for (const entry of entries) {
		let control = controls.get(entry.key);
		if (!control || !contributionControlMatches(control, entry)) {
			control = createContributionControl(entry);
			controls.set(entry.key, control);
			changed.add(control);
		} else if (contributionEntryRecord(control) !== entry) changed.add(control);
		control.onclick = (event) => activate({
			offered: source,
			entry,
			control,
			surface,
			event
		});
		trackContributionControl(source, surface, entry.key, control);
	}
	clearContributionControls(source, surface, liveKeys);
	for (const entry of entries) {
		const control = controls.get(entry.key);
		const related = entry.relation?.kind === "entries" ? entry.relation.keys.map((key) => controls.get(key)).filter(Boolean) : [];
		related.forEach((node, index) => {
			if (!node.id) node.id = `lf-margin-related-${++relationOrdinal}-${index + 1}`;
		});
		if (changed.has(control)) presentContributionEntry(control, entry, { relatedControlIds: related.map((node) => node.id) });
	}
	return controls;
}

//#endregion
//#region runtime/contributions.js
const text = (value) => String(value ?? "").trim();
const contributionSources = /* @__PURE__ */ new WeakMap();
let publishing = 0;
const contributionSource = (model) => contributionSources.get(model);
function publishReading(offered) {
	publishing++;
	try {
		const declared = offered.read();
		const normalized = normalizeReading(declared, offered.key, offered.reading);
		if (!offered.activate && normalized.entries.some((entry) => entry.behavior !== "status" && !contributionOwnsCommand(entry))) throw new TypeError("An unscoped contribution action needs an activate function");
		offered.readingActions = new Map((declared.readings ?? []).map(({ id, activate }) => [id, activate]));
		offered.reading = normalized;
		const { readings, ...reading } = offered.reading;
		offered.model = Object.freeze({
			key: offered.key,
			reading: Object.freeze({
				...reading,
				hasReadings: readings.length > 0
			})
		});
		contributionSources.set(offered.model, offered);
	} finally {
		publishing--;
	}
}
const contributions = /* @__PURE__ */ new Set();
const listeners = /* @__PURE__ */ new Set();
let owed = false;
const changed = () => {
	owed = true;
	afterScript(settle);
};
function settle({ immediate = false } = {}) {
	if (!owed || publishing) return;
	owed = false;
	for (const listener of listeners) listener({ immediate });
}
const contributionEntries = () => contributions.values();
watchCommandAvailability(() => {
	for (const offered of contributions) if (offered.reading.entries.some((entry) => contributionOwnsCommand(entry) && entry.disabled !== contributionCommandDisabled(entry))) offered.registration.update({ immediate: true });
});
function presentingContributions() {
	owed = false;
}
function watchContributions(listener) {
	listeners.add(listener);
	return () => listeners.delete(listener);
}
function registerContribution({ key, target, source = target, read, activate }) {
	const owner = text(key);
	if (!owner) throw new TypeError("A contribution needs a key");
	const targetOf = typeof target === "function" ? target : () => target;
	const offered = {
		key: owner,
		target: targetOf,
		source: source === target ? targetOf : typeof source === "function" ? source : () => source,
		read,
		activate,
		reading: null
	};
	publishReading(offered);
	contributions.add(offered);
	changed();
	const entry = (entryKey) => offered.reading.entries.find((candidate) => candidate.key === entryKey) ?? null;
	const control = (entryKey, surface = null, visible = false) => {
		settle();
		return contributionControl(offered, entryKey, surface, visible);
	};
	let owedFocus = null;
	const landFocus = () => {
		const key = owedFocus;
		owedFocus = null;
		offered.focusRequest = null;
		if (key != null) registration.focus(key, "move");
	};
	const arrive = (entryKey, surface, move) => {
		const request = {
			key: text(entryKey),
			surface
		};
		const previous = offered.focusRequest;
		offered.focusRequest = request;
		try {
			changed();
			settle({ immediate: true });
			const destination = control(request.key, surface, true);
			if (!destination) return false;
			return move(destination);
		} finally {
			if (offered.focusRequest === request) offered.focusRequest = previous;
		}
	};
	const registration = Object.freeze({
		entry(entryKey) {
			return entry(text(entryKey));
		},
		control,
		contains(node) {
			return contributionContains(offered, node);
		},
		activate(entryKey, context = {}) {
			if (!contributions.has(offered)) return false;
			const current = entry(text(entryKey));
			if (!current || !current.visible || (contributionOwnsCommand(current) ? contributionCommandDisabled(current) : current.disabled) || current.behavior === "status") return false;
			const originOwnsFocus = context.origin == null || context.origin === focused();
			const focusCurrentSurface = (key) => arrive(key, context.surface ?? null, (destination) => {
				if (context.focus) return context.focus(key);
				focusDestination(destination, "return");
				return true;
			});
			const activationContext = {
				...context,
				entry: current,
				focus: originOwnsFocus ? focusCurrentSurface : () => false
			};
			const command = contributionCommand(current);
			if (command) command.row.run(command.binding, activationContext);
			else offered.activate(current.activation, activationContext);
			return true;
		},
		activateReading(id) {
			const activate = offered.readingActions.get(id);
			if (!activate) return false;
			activate();
			return true;
		},
		focus(entryKey, cause, surface = null) {
			return arrive(entryKey, surface, (destination) => {
				focusDestination(destination, cause);
				return true;
			});
		},
		update({ immediate = false, focus = null } = {}) {
			publishReading(offered);
			if (focus != null) {
				owedFocus = text(focus);
				offered.focusRequest = {
					key: owedFocus,
					surface: null
				};
				afterScript(landFocus);
			}
			changed();
			if (immediate) settle({ immediate: true });
		},
		unregister() {
			if (!contributions.delete(offered)) return;
			forgetContributionControls(offered);
			changed();
		}
	});
	offered.registration = registration;
	return registration;
}

//#endregion
//#region runtime/composing/drawing-record.js
const FIELDS = drawingSchema.properties;
const MAX_DRAWING_STROKES = FIELDS.strokes.maxItems;
const MAX_DRAWING_FRAME_DEPTH = FIELDS.frame.properties.path.maxItems;
const MAX_DRAWING_POINTS = FIELDS.strokes.items.maxItems;
const DRAWING_COORDINATE_LIMIT = FIELDS.strokes.items.items.prefixItems[0].maximum;
const MAX_DRAWING_SAYS_LENGTH = FIELDS.says.maxLength;
function sentDrawing(drawing) {
	const { at, ...sent } = drawing;
	return sent;
}

//#endregion
//#region runtime/editor-view.js
function travel(start, end, low, high, alignment, margin, side) {
	if (alignment === "nearest") {
		if (start < low + margin) {
			const movement = start - low - margin;
			return side > 0 && end > high + movement ? end - high + margin : movement;
		}
		if (end > high - margin) {
			const movement = end - high + margin;
			return side < 0 && start - movement < low ? start - low - margin : movement;
		}
		return 0;
	}
	if (alignment === "center" && end - start <= high - low) return (start + end - low - high) / 2;
	return alignment === "start" || alignment === "center" && side < 0 ? start - low - margin : end - high + margin;
}
const classes = /* @__PURE__ */ new WeakMap();
function leafEditorView(codemirror) {
	let made = classes.get(codemirror);
	if (!made) classes.set(codemirror, made = editorViewOver(codemirror));
	return made;
}
function editorViewOver({ Compartment, Direction, EditorState, EditorView, StateEffect }) {
	function caretAt(view, at) {
		const position = view.domAtPos(at);
		const caret = document.createRange();
		caret.setStart(position.node, position.offset);
		caret.collapse(true);
		if (caret.getClientRects().length) return {
			destination: caret,
			rectangle: caret.getBoundingClientRect()
		};
		const destination = position.node instanceof Element ? position.node : position.node.parentElement;
		const box = destination.getBoundingClientRect();
		const x = view.textDirection === Direction.LTR ? box.left : box.right;
		return {
			destination,
			rectangle: {
				left: x,
				right: x,
				top: box.top,
				bottom: box.bottom
			}
		};
	}
	function placeWithinEditor(view, selection, options, head) {
		const rectangle = union(selection.empty ? [head] : [head, caretAt(view, selection.anchor).rectangle]);
		const margins = {
			top: 0,
			bottom: 0,
			left: 0,
			right: 0
		};
		for (const provider of view.state.facet(EditorView.scrollMargins)) {
			const supplied = provider(view);
			if (supplied) for (const edge of Object.keys(margins)) margins[edge] = Math.max(margins[edge], supplied[edge] ?? 0);
		}
		const port = view.scrollDOM;
		const box = port.getBoundingClientRect();
		const { scaleX, scaleY } = view;
		const left = box.left + port.clientLeft * scaleX;
		const top = box.top + port.clientTop * scaleY;
		const right = left + port.clientWidth * scaleX;
		const bottom = top + port.clientHeight * scaleY;
		const side = selection.head < selection.anchor ? -1 : 1;
		const horizontal = view.textDirection === Direction.RTL ? options.x === "start" ? "end" : options.x === "end" ? "start" : options.x : options.x;
		const xMargin = clamp(options.xMargin, -port.offsetWidth, port.offsetWidth);
		const yMargin = clamp(options.yMargin, -port.offsetHeight, port.offsetHeight);
		const x = horizontal === "center" ? (rectangle.left - margins.left + rectangle.right + margins.right - left - right) / 2 : travel(rectangle.left - margins.left, rectangle.right + margins.right, left, right, horizontal, xMargin, side);
		const y = travel(rectangle.top - margins.top, rectangle.bottom + margins.bottom, top, bottom, options.y, yMargin, side);
		port.scrollBy({
			left: port.scrollWidth > port.clientWidth ? x / scaleX : 0,
			top: port.scrollHeight > port.clientHeight ? y / scaleY : 0,
			behavior: "instant"
		});
	}
	const navigation = new Compartment();
	const reveal = EditorView.scrollHandler.of((view, selection, options) => {
		const { destination, rectangle } = caretAt(view, selection.head);
		placeWithinEditor(view, selection, options, rectangle);
		scrollIntoView(destination, {
			block: "nearest",
			behavior: "instant"
		});
		return true;
	});
	const withNavigation = (state) => navigation.get(state) === void 0 ? state.update({ effects: StateEffect.appendConfig.of(navigation.of(reveal)) }).state : state;
	return class LeafEditorView extends EditorView {
		#focusing = false;
		constructor(config = {}) {
			super({
				...config,
				state: withNavigation(config.state ?? EditorState.create(config))
			});
			this.scrollDOM.classList.add("scroll");
			this.contentDOM.addEventListener("focus", () => {
				if (!this.#focusing) this.placeSelection();
			});
		}
		caretAt(at) {
			return caretAt(this, at);
		}
		setState(state) {
			super.setState(withNavigation(state));
		}
		focus() {
			if (!canPlaceFocus()) return;
			const selection = this.#selection();
			if (this.root.activeElement !== this.contentDOM && selection.getComposedRanges({ shadowRoots: this.root instanceof ShadowRoot ? [this.root] : [] }).some((range) => this.contentDOM.contains(range.startContainer) || this.contentDOM.contains(range.endContainer))) selection.removeAllRanges();
			this.#focusing = true;
			try {
				this.contentDOM.focus({ preventScroll: true });
			} finally {
				this.#focusing = false;
			}
			this.placeSelection();
		}
		placeSelection() {
			if (this.root.activeElement !== this.contentDOM) return;
			const { anchor, head } = this.state.selection.main;
			const from = this.domAtPos(anchor);
			const to = this.domAtPos(head);
			this.#selection().setBaseAndExtent(from.node, from.offset, to.node, to.offset);
		}
		#selection() {
			return this.root.getSelection?.() ?? this.dom.ownerDocument.getSelection();
		}
	};
}

//#endregion
//#region runtime/composing/field-editor.js
const touches = (state, from, to) => state.selection.ranges.some((range) => range.from <= to && range.to >= from);
const read = (state) => {
	return placedMarkdownTokens(state.doc.toString());
};
const FACE_PROBE = "<div></div><p></p><h1></h1><h2></h2><h3></h3><h4></h4><h5></h5><h6></h6><pre></pre><blockquote></blockquote><ul><li></li><li></li></ul><ol></ol><div></div>";
const collapsed = (a, b) => Math.max(a, b, 0) + Math.min(a, b, 0);
const GAP = "calc(max(var(--lf-gap-end), var(--lf-gap-start), 0px) + min(var(--lf-gap-end), var(--lf-gap-start), 0px))";
function readFaces(field, display) {
	const probe = display.cloneNode(false);
	probe.removeAttribute("id");
	probe.setAttribute("aria-hidden", "true");
	probe.style.cssText = "position: absolute; visibility: hidden; inline-size: 0; display: block";
	probe.innerHTML = FACE_PROBE;
	field.after(probe);
	const face = {};
	const own = getComputedStyle(field);
	const TYPE = [
		"font-size",
		"line-height",
		"font-weight",
		"letter-spacing"
	];
	for (const node of probe.querySelectorAll(":scope > :not(div), li + li")) {
		const s = getComputedStyle(node);
		const px = (value) => Number.parseFloat(value) || 0;
		face[node.localName] = {
			type: TYPE.filter((name) => s.getPropertyValue(name) !== own.getPropertyValue(name)).map((name) => `${name}: ${s.getPropertyValue(name)}`).join("; "),
			start: px(s.marginTop),
			end: px(s.marginBottom),
			padStart: px(s.paddingTop),
			padEnd: px(s.paddingBottom),
			inset: s.paddingInlineStart,
			indent: s.marginInlineStart
		};
	}
	probe.remove();
	const { li, pre, blockquote: quote } = face;
	const rules = [];
	for (const [tag, { type, start, end }] of Object.entries(face)) {
		const list = tag === "ul" || tag === "ol";
		rules.push(`.lf-face-${tag} { ${type} }`, `.lf-starts-${tag} { --lf-gap-start: ${list ? collapsed(start, li.start) : start}px }`, `.lf-ends-${tag} { --lf-gap-end: ${list ? collapsed(end, li.end) : end}px }`);
	}
	rules.push(`.lf-face-gap { line-height: ${GAP} }`, `.lf-face-gap.lf-face-share-2 { line-height: calc(${GAP} / 2) }`, `.lf-face-gap.lf-face-share-3 { line-height: calc(${GAP} / 3) }`, `.lf-face-rule { line-height: 0 }`, `.lf-face-gap-above { padding-block-start: ${GAP} }`, `.lf-face-fence-open { line-height: ${pre.padStart}px }`, `.lf-face-fence-close { line-height: ${pre.padEnd}px }`, `.lf-face-code { padding-inline: ${pre.inset} }`, `.lf-face-quote { margin-inline-start: ${quote.indent}; padding-inline-start: ${quote.inset}; --lf-marker-inset: ${quote.inset} }`, `.lf-face-quote-first { padding-block-start: ${quote.padStart}px }`, `.lf-face-gap-above.lf-face-quote-first { padding-block-start: calc(${GAP} + ${quote.padStart}px) }`, `.lf-face-quote-last { padding-block-end: ${quote.padEnd}px }`, `.lf-face-item { padding-block-start: ${collapsed(li.end, li.start)}px }`, `.lf-face-list-lead { padding-block-start: ${collapsed(0, li.start)}px }`, `.lf-face-list-tail { padding-block-end: ${collapsed(0, li.end)}px }`);
	return rules.join("\n");
}
const blockTag = (token) => token.type === "fence" || token.type === "code_block" ? "pre" : token.tag;
function standBlocks(state, placed, out, line) {
	const lines = (from, to, each) => {
		for (let at = from; at < to;) {
			const current = state.doc.lineAt(at);
			each(current);
			at = current.to + 1;
		}
	};
	const named = (from, cls) => out.push(line(cls).range(from));
	const gapLines = (from, to, gap) => {
		const runs = state.doc.lineAt(to).number - state.doc.lineAt(from).number;
		const share = runs > 1 ? ` lf-face-share-${Math.min(runs, 3)}` : "";
		lines(from, to, (each) => named(each.from, `lf-face-gap${share} ${gap}`));
	};
	const lineTouched = (at) => {
		const { from, to } = state.doc.lineAt(at);
		return touches(state, from, to);
	};
	const before = [];
	const open = [];
	let item = null;
	const blank = (at) => /^[\s>]*$/.test(state.doc.lineAt(at).text);
	for (const { token, from, to, markers, contentLines } of placed) {
		if (!token.block) continue;
		const tag = blockTag(token);
		if (token.type === "heading_open") {
			lines(...contentLines, (each) => named(each.from, `lf-face-${tag}`));
			if (!token.markup.startsWith("#")) {
				for (const [at] of markers) if (!lineTouched(at)) named(state.doc.lineAt(at).from, "lf-face-rule");
			}
		} else if (token.type === "fence" || token.type === "code_block") {
			lines(from, to, (each) => named(each.from, "lf-face-code"));
			const opener = state.doc.lineAt(from).number;
			for (const [at] of token.type === "fence" ? markers : []) {
				const fence = state.doc.lineAt(at);
				if (lineTouched(at)) continue;
				const side = fence.number === opener ? "open" : "close";
				named(fence.from, `lf-face-fence-${side}`);
			}
		}
		while (open.at(-1)?.to <= from) before.length = open.pop().level + 1;
		const within = open.at(-1)?.type;
		if (token.type === "list_item_open" && within !== "list_item_open") {
			if (item?.to === from) named(from, "lf-face-item");
			item = { to };
		}
		if (/^(blockquote|bullet_list|ordered_list|list_item)_open$/.test(token.type)) open.push({
			type: token.type,
			to,
			level: token.level
		});
		if (token.type === "list_item_open" || within === "list_item_open") continue;
		const level = token.level;
		if (!FACE_PROBE.includes(`<${tag}>`)) {
			before[level] = null;
			continue;
		}
		const list = tag === "ul" || tag === "ol";
		if (list && from === 0) named(0, "lf-face-list-lead");
		if (list && to >= state.doc.length) named(state.doc.lineAt(state.doc.length).from, "lf-face-list-tail");
		const prior = before[level];
		const gap = `lf-ends-${prior?.tag} lf-starts-${tag}`;
		if (prior && prior.to < from) gapLines(prior.to, from, gap);
		else if (prior) named(from, `lf-face-gap-above ${gap}`);
		let end = to;
		while (end > from && blank(end - 1)) end = state.doc.lineAt(end - 1).from;
		before[level] = {
			tag,
			to: end
		};
		before.length = level + 1;
		if (token.type === "paragraph_open" && level === 0) lines(from, to, (each) => named(each.from, "lf-face-p"));
		else if (token.type === "blockquote_open" && level === 0) {
			lines(from, end, (each) => named(each.from, "lf-face-quote"));
			named(from, "lf-face-quote-first");
			named(state.doc.lineAt(Math.max(from, end - 1)).from, "lf-face-quote-last");
		}
	}
	const last = state.doc.line(state.doc.lines);
	const final = before[0];
	if (final && final.to < last.from) gapLines(final.to, last.from, `lf-ends-${final.tag} lf-starts-p`);
}
let loaded = null;
const loadFieldEditor = () => loaded ??= import("/vendor/codemirror.esm.js").then((codemirror) => fieldEditor(codemirror, leafEditorView(codemirror)));
function fieldEditor({ EditorView, EditorState, StateEffect, Compartment, WidgetType, Decoration, LanguageSupport, ViewPlugin, keymap, history, standardKeymap, historyKeymap, isolateHistory, invertedEffects, markdownLanguage, insertNewlineContinueMarkup }, LeafEditorView) {
	const insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;
	const ownerStep = StateEffect.define();
	const hide = Decoration.replace({});
	const dim = Decoration.mark({ class: "lf-md-mark" });
	const link = Decoration.mark({ class: "lf-md-link" });
	const unseen = Decoration.mark({
		class: "lf-md-unseen",
		attributes: { "aria-hidden": "true" }
	});
	const marker = Decoration.mark({
		class: "lf-md-marker lf-md-unseen",
		attributes: { "aria-hidden": "true" }
	});
	const shownMarker = Decoration.mark({ class: "lf-md-marker lf-md-mark" });
	const line = (cls) => Decoration.line({ class: cls });
	const BULLETS = [
		"lf-md-disc",
		"lf-md-circle",
		"lf-md-square"
	];
	const itemLine = (depth, kind, number) => Decoration.line({
		class: kind ? `lf-md-item lf-md-listed ${kind}` : "lf-md-item",
		attributes: { style: `--lf-list-depth: ${depth}${kind === "lf-md-number" ? `; counter-set: list-item ${number}` : ""}` }
	});
	const INLINE = {
		code_inline: Decoration.mark({ tagName: "code" }),
		em_open: Decoration.mark({ tagName: "em" }),
		strong_open: Decoration.mark({ tagName: "strong" }),
		s_open: Decoration.mark({ tagName: "s" })
	};
	class Picture extends WidgetType {
		constructor(src, alt) {
			super();
			this.src = isCanonicalMediaUrl(src) ? scopedMediaUrl(src) : src;
			this.alt = alt;
		}
		eq(other) {
			return other.src === this.src && other.alt === this.alt;
		}
		toDOM(view) {
			const img = document.createElement("img");
			img.className = "lf-md-picture";
			img.alt = this.alt;
			img.src = this.src;
			img.addEventListener("load", () => view.requestMeasure(), { once: true });
			return img;
		}
		ignoreEvent() {
			return false;
		}
	}
	class ExternalMark extends WidgetType {
		eq() {
			return true;
		}
		toDOM() {
			return document.documentElement.lfExternalLink.mark();
		}
	}
	const externalMark = Decoration.widget({
		widget: new ExternalMark(),
		side: -1
	});
	const opensElsewhere = (href) => document.documentElement.lfExternalLink?.opensElsewhere(href) ?? false;
	function decorate(state, placed) {
		const out = [];
		const lists = [];
		const items = /* @__PURE__ */ new Map();
		const code = [];
		const add = (from, to, deco) => {
			if (from >= to) return;
			if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
			out.push(deco.range(from, to));
		};
		const lines = (from, to, each) => {
			for (let at = from; at < to;) {
				const current = state.doc.lineAt(at);
				each(current);
				at = current.to + 1;
			}
		};
		for (const { token, from, to, contentFrom, contentTo, escapes, markers, contentLines, words: said } of placed) {
			const syntax = touches(state, from, to) ? dim : hide;
			if (token.type === "code_inline" || contentFrom !== void 0) {
				const words = token.type === "code_inline" ? [from + token.markup.length, to - token.markup.length] : [contentFrom, contentTo];
				if (words[0] > words[1]) continue;
				if (INLINE[token.type]) add(from, to, INLINE[token.type]);
				else if (token.type === "link_open" && token.meta.linked) {
					add(words[0], words[1], link);
					if (opensElsewhere(token.attrGet("href"))) out.push(externalMark.range(words[1]));
				}
				add(from, words[0], syntax);
				add(words[1], to, syntax);
			} else if (token.type === "image") {
				if (said !== "" || state.doc.sliceString(from, to).includes("\n")) continue;
				const widget = new Picture(token.attrGet("src"), token.content);
				out.push(touches(state, from, to) ? Decoration.widget({
					widget,
					side: 1
				}).range(to) : Decoration.replace({ widget }).range(from, to));
			} else if (token.type === "text") for (const at of escapes ?? []) add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
			else if (token.type === "heading_open") {
				lines(...contentLines, (each) => {
					out.push(line("lf-md-heading").range(each.from));
				});
				for (const [a, b] of markers) {
					const rule = state.doc.lineAt(a);
					const shown = touches(state, rule.from, rule.to) ? dim : unseen;
					add(a, b, token.markup.startsWith("#") ? syntax : shown);
				}
			} else if (token.type === "fence" || token.type === "code_block") {
				code.push([from, to]);
				const body = token.content.split("\n");
				const opened = state.doc.lineAt(from).number + (token.type === "fence" ? 1 : 0);
				lines(from, to, (each) => {
					const ends = [
						each.from <= from ? " lf-md-code-first" : "",
						each.to + 1 >= to ? " lf-md-code-last" : "",
						token.type === "code_block" ? " lf-md-code-bare" : ""
					].join("");
					out.push(line(`lf-md-code-block${ends}`).range(each.from));
					const kept = body[each.number - opened];
					if (kept === void 0 || each.number - opened >= body.length - 1) return;
					const lead = each.text.match(/^[ \t]*/)[0].length;
					add(each.from, each.from + lead - kept.match(/^[ \t]*/)[0].length, hide);
				});
				for (const [a, b] of markers ?? []) {
					const fence = state.doc.lineAt(a);
					add(a, b, touches(state, fence.from, fence.to) ? dim : unseen);
				}
			} else if (token.type === "blockquote_open") {
				lines(from, to, (each) => {
					out.push(line("lf-md-quote").range(each.from));
				});
				for (const [a, b] of markers) add(a, b, touches(state, a, b) ? shownMarker : marker);
			} else if (token.type === "bullet_list_open" || token.type === "ordered_list_open") {
				while (lists.at(-1)?.to <= from) lists.pop();
				const ordered = token.type === "ordered_list_open";
				lists.push({
					to,
					next: ordered ? Number(token.attrGet("start") ?? 1) : null
				});
			} else if (token.type === "list_item_open") {
				while (lists.at(-1)?.to <= from) lists.pop();
				const list = lists.at(-1);
				const depth = lists.length;
				const head = state.doc.lineAt(from);
				const [at, end] = markers[0];
				const start = at - head.text.slice(0, at - head.from).match(/[ \t]*$/)[0].length;
				if (head.text.slice(0, start - head.from).trim()) {
					add(start, end, dim);
					continue;
				}
				lines(head.to + 1, Math.min(to, state.doc.length), (each) => {
					items.set(each.from, {
						depth,
						continued: true
					});
				});
				const kind = list.next === null ? BULLETS[Math.min(depth, BULLETS.length) - 1] : "lf-md-number";
				const shown = state.selection.ranges.some((range) => range.from < end && range.to >= start);
				items.set(head.from, {
					depth,
					kind: shown ? null : kind,
					number: list.next
				});
				if (list.next !== null) list.next++;
				add(start, end, shown ? shownMarker : marker);
			}
		}
		for (const [from, { depth, kind, number, continued }] of items) {
			out.push(itemLine(depth, kind, number).range(from));
			if (!continued || code.some(([a, b]) => from >= a && from < b)) continue;
			add(from, from + state.doc.lineAt(from).text.match(/^[ \t]*/)[0].length, hide);
		}
		standBlocks(state, placed, out, line);
		return Decoration.set(out, true);
	}
	const livePreview = ViewPlugin.fromClass(class {
		constructor(view) {
			this.live = true;
			this.placed = read(view.state);
			this.decorations = decorate(view.state, this.placed);
			this.judged = markdownReady();
			if (!this.judged) loadMarkdown().then(() => this.live && view.dispatch({}), () => {});
		}
		destroy() {
			this.live = false;
		}
		update(update) {
			const judged = markdownReady();
			if (update.docChanged || judged !== this.judged) {
				this.judged = judged;
				this.placed = read(update.state);
			} else if (!update.selectionSet) return;
			this.decorations = decorate(update.state, this.placed);
		}
	}, { decorations: (plugin) => plugin.decorations });
	const editable = new Compartment();
	const histories = new Compartment();
	const attributes = new Compartment();
	function fieldState(words, field) {
		const { base, text } = words;
		let from = 0;
		while (from < Math.min(base.length, text.length) && base[from] === text[from]) from++;
		let kept = 0;
		while (kept < Math.min(base.length, text.length) - from && base[base.length - 1 - kept] === text[text.length - 1 - kept]) kept++;
		let state = EditorState.create({
			doc: base,
			selection: { anchor: from },
			extensions: [
				EditorView.inputHandler.of((view, _from, _to, _text, insert) => {
					field.typed(!view.contentDOM.editContext, () => view.dispatch(insert()));
					return true;
				}),
				EditorView.scrollHandler.of((view, range) => {
					field.revealed(view, range.head);
					return false;
				}),
				histories.of(history()),
				EditorState.transactionFilter.of((tr) => {
					if (!tr.docChanged || !field.oneLine()) return tr;
					const breaks = [];
					tr.changes.iterChanges((_fromA, _toA, fromB, _toB, inserted) => {
						const text = inserted.toString();
						for (let at = text.indexOf("\n"); at !== -1; at = text.indexOf("\n", at + 1)) breaks.push({
							from: fromB + at,
							to: fromB + at + 1,
							insert: " "
						});
					});
					return breaks.length ? [tr, {
						changes: breaks,
						sequential: true
					}] : tr;
				}),
				invertedEffects.of((tr) => tr.effects.filter((effect) => effect.is(ownerStep)).map(({ value }) => ownerStep.of({
					run: value.back,
					back: value.run
				}))),
				keymap.of([
					{
						key: "Shift-Enter",
						run: () => field.oneLine()
					},
					{
						key: "Enter",
						run: (view) => field.returned() && insertNewline(view)
					},
					{
						key: "Shift-Enter",
						run: insertNewlineContinueMarkup
					},
					{
						key: "Shift-Enter",
						run: (view) => (view.dispatch(view.state.update(view.state.replaceSelection("\n"), {
							scrollIntoView: true,
							userEvent: "input"
						})), true)
					},
					...standardKeymap.filter(({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter"),
					...historyKeymap
				]),
				new LanguageSupport(markdownLanguage),
				livePreview,
				EditorView.lineWrapping,
				editable.of(EditorState.readOnly.of(field.readOnly)),
				attributes.of(EditorView.contentAttributes.of(field.attributes))
			]
		});
		state = state.update({
			...text !== base && {
				changes: {
					from,
					to: base.length - kept,
					insert: text.slice(from, text.length - kept)
				},
				annotations: isolateHistory.of("full"),
				userEvent: "input.type"
			},
			selection: {
				anchor: words.anchor,
				head: words.head
			}
		}).state;
		for (const [undo, redo] of words.steps) state = state.update(record(undo, redo)).state;
		return state;
	}
	const readOnly = (on) => ({ effects: editable.reconfigure(EditorState.readOnly.of(on)) });
	const contentAttributes = (wanted) => ({ effects: attributes.reconfigure(EditorView.contentAttributes.of(wanted)) });
	const record = (undo, redo) => ({
		effects: ownerStep.of({
			run: redo,
			back: undo
		}),
		annotations: isolateHistory.of("full")
	});
	const forgetHistory = { effects: histories.reconfigure([]) };
	const startHistory = () => ({ effects: histories.reconfigure(history()) });
	function runOwnerSteps(transactions) {
		for (const tr of transactions) if (tr.isUserEvent("undo") || tr.isUserEvent("redo")) {
			for (const effect of tr.effects) if (effect.is(ownerStep)) effect.value.run();
		}
	}
	return {
		LeafEditorView,
		fieldState,
		readOnly,
		contentAttributes,
		record,
		forgetHistory,
		startHistory,
		runOwnerSteps
	};
}

//#endregion
//#region runtime/composing/text-field.js
const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* CodeMirror's provider places its defaults in lf-base. This control owns the
     unlayered editor face: the host supplies type and colour, and these are the
     only internal padding declarations before Markdown's explicit insets below. */
  .cm-editor { font: inherit; color: inherit; background-color: transparent; }
  .cm-editor.cm-focused { outline: none; }
  .cm-scroller { font-family: inherit; line-height: inherit; overflow: visible; }
  .cm-content { padding: 0; caret-color: currentColor; min-height: 1lh; }
  /* An empty field draws no editor until the user arrives in it (#build). This box
     holds the empty line's place, as tall as the editor's line, and takes the focus
     that builds the editor; while the editor loads, it holds the words, wrapped as
     the editor wraps them. */
  .lf-field-rest { min-height: 1lh; outline: none; white-space: pre-wrap;
    overflow-wrap: break-word; }
  .cm-line { padding: 0; }
  /* A space after a line's last word hangs past its end, as in a textarea and in the
     sent message (reading.css, \`.lf-msg-text > p\`), rather than taking room on the
     line and carrying the word to the next one, as CodeMirror's \`break-spaces\`
     does. */
  .cm-editor .cm-content.cm-lineWrapping { white-space: pre-wrap; }
  /* CodeMirror's caret stops beside a widget hang from the text's top, which stands
     above a line set tighter than its type, as a heading's is, and would make that
     line taller than the heading it draws. The field's caret is the platform's. */
  .cm-widgetBuffer { vertical-align: top; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* An owner moving the field's edges can carry the words from where they were with
     them, by the host's --lf-field-carry, and cut them to the box it draws growing, by
     --lf-field-cut (theme.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. The clip
     reaches 2px past that box, the caret's width at a line's end: Firefox paints the
     caret from its offset onward and pulls it inside only a scroll container, so a
     caret after a line that fills the box, as a trailing space can, was
     cut away whole. Words an owner carries down from above the box, as a line removed
     carries them, need more: it sets --lf-field-reach as far as they travel, and
     stops the host scrolling meanwhile. Chrome refuses calc() here, so the reach
     replaces the caret's margin rather than adding to it, so the owner keeps at
     least 2px there and at the moving content's inline clip edges. */
  .lf-field { overflow: clip; overflow-clip-margin: var(--lf-field-reach, 2px); }
  .lf-field > * {
    translate: var(--lf-field-carry);
    clip-path: inset(var(--lf-field-cut));
  }
  /* The placeholder is one line that never widens the box — a response bar sizes to the
     words — and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; white-space: nowrap;
    contain: inline-size; overflow-x: clip; text-overflow: ellipsis;
    color: var(--muted); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* The trailing action's room, on every line. */
  .lf-field { padding-inline-end: var(--lf-field-end-room); }
  /* A draft wears the sent message's faces, or where it stands in place, those its
     display gives each block (\`standBlocks\`), written on its lines over these. Strong,
     emphasis and strikethrough are the elements themselves, which the platform dresses
     here as it does in the message; the rest read the theme's tokens, since its element
     rules stop at this root. A heading is bold, as the platform draws one, at the size
     of the words around it. A block is drawn line by line, so a code block's frame is
     each line's sides, closed above its first line and below its last. Syntax that holds
     its room while the caret is away, as a code fence's line does, is there unseen and
     unspoken. Its glyphs go unfilled while its colour stays the words', because the
     caret can stand at the end of unseen text, as just past a new item's marker, and the
     browser draws it in that text's colour. */
  .lf-md-mark { color: var(--muted); }
  .lf-md-unseen { -webkit-text-fill-color: transparent; }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset); color: var(--muted);
    --lf-marker-inset: var(--quote-inset); }
  /* A quote's and a list item's words stand where the message's do, and the source's
     marker stands in the inset before them, unseen while the caret is away, so
     revealing it moves no word. A list item's lines stand one list inset in per level,
     under the platform's own list marker, as in the message, so it is the same bullet
     or number at the same place. */
  .lf-md-item { margin-inline-start: calc(var(--lf-list-depth) * var(--list-inset));
    --lf-marker-inset: var(--list-inset); }
  .lf-md-marker { display: inline-flex; justify-content: flex-end; white-space: pre;
    inline-size: var(--lf-marker-inset);
    margin-inline-start: calc(-1 * var(--lf-marker-inset)); }
  .lf-md-listed { display: list-item; }
  .lf-md-disc { list-style-type: disc; }
  .lf-md-circle { list-style-type: circle; }
  .lf-md-square { list-style-type: square; }
  .lf-md-number { list-style-type: decimal; }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  /* A sent pre reserves 8px below its lines for a horizontal scrollbar. */
  .cm-line.lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r);
    padding-block-end: 8px; }
  /* A picture fits the field as media fits its container on the page, centred on its
     line (theme.css), and the mark after a link that leaves the page is the page's
     own (surfaces.css). */
  .lf-md-picture { max-width: 100%; height: auto; vertical-align: middle; }
  .lf-external-mark { display: inline-block; width: 0.75em; height: 0.75em;
    margin-inline-start: 0.24em; vertical-align: 0.03em; color: var(--accent);
    fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round;
    stroke-linejoin: round; overflow: visible; user-select: none;
    -webkit-user-select: none; }
  /* A fence's line, while the caret is away from it, stands for the sent pre's padding,
     and code with no fence lines takes that padding at its ends instead. A field that
     edits in place reads its display's padding over this (\`readFaces\`). */
  .lf-face-fence-open, .lf-face-fence-close { line-height: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-first { padding-block-start: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-last { padding-block-end: calc(var(--pre-pad-block) + 8px); }
`);
let editor = null;
const loadEditor = () => loadFieldEditor().then((loaded) => editor = loaded);
afterPresentation(loadEditor);
var Draft = class {
	steps = [];
	constructor(text) {
		this.text = this.base = text;
		this.anchor = this.head = text.length;
	}
};
const placeWords = (node) => node.nodeType === Node.TEXT_NODE ? node.data : node.nodeName === "BR" ? "\n" : [...node.childNodes].map(placeWords).join("");
var LeafText = class extends HTMLElement {
	#model = new Draft("");
	#view = null;
	#rest = document.createElement("div");
	#waiting = null;
	#composing = false;
	#nativeInput = false;
	#root;
	#internals = null;
	facesOf = null;
	#faces = new CSSStyleSheet();
	#facesRead = "";
	#readFaces() {
		if (!this.facesOf?.isConnected || !this.isConnected) return;
		const rules = readFaces(this, this.facesOf);
		if (rules === this.#facesRead) return;
		this.#facesRead = rules;
		this.#faces.replaceSync(rules);
	}
	#placeholderLayer = document.createElement("div");
	#placeholderText = document.createTextNode("");
	#frame = document.createElement("div");
	#readOnly = false;
	#sizes = sizeObserver(() => {
		this.#readFaces();
		const view = this.#view;
		if (view?.hasFocus) view.requestMeasure({
			key: this,
			read: () => this.#rowTravel(view, view.state.selection.main.head),
			write: (travel) => moveScrollerBy(this, travel)
		});
	});
	#rowTravel(view, pos) {
		const { destination, rectangle: caret } = view.caretAt(pos);
		const node = destination instanceof Range ? destination.startContainer : destination;
		const row = (node instanceof Element ? node : node.parentElement)?.closest(".cm-line") ?? this;
		const { scaleY } = view;
		const leading = Math.max(0, (parseFloat(getComputedStyle(row).lineHeight) * scaleY - (caret.bottom - caret.top)) / 2) || 0;
		const style = getComputedStyle(this);
		const box = this.getBoundingClientRect();
		const top = box.top + (this.clientTop + parseFloat(style.paddingTop)) * scaleY;
		const bottom = box.bottom - (this.offsetHeight - this.clientTop - this.clientHeight + parseFloat(style.paddingBottom)) * scaleY;
		const travel = (Math.min(0, caret.top - leading - top) + Math.max(0, caret.bottom + leading - bottom)) / scaleY;
		return travel < 0 ? Math.floor(travel) : Math.ceil(travel);
	}
	#overflow = sizeObserver(() => this.#measureOverflow());
	#measureOverflow() {
		this.#view?.requestMeasure({
			key: this.#overflow,
			read: () => {
				const style = getComputedStyle(this);
				return {
					scrolls: this.scrollHeight > this.clientHeight,
					above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
					below: this.scrollTop + this.clientHeight < this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1
				};
			},
			write: (reading) => {
				if (this.hasAttribute("data-scrolls") !== reading.scrolls) this.toggleAttribute("data-scrolls", reading.scrolls);
				for (const [state, on] of [["more-above", reading.scrolls && reading.above], ["more-below", reading.scrolls && reading.below]]) {
					if (this.#internals.states.has(state) === on) continue;
					if (on) this.#internals.states.add(state);
					else this.#internals.states.delete(state);
				}
			}
		});
	}
	static observedAttributes = [
		"aria-label",
		"aria-describedby",
		"placeholder"
	];
	constructor() {
		super();
		this.#root = this.attachShadow({
			mode: "closed",
			delegatesFocus: true
		});
		this.#frame.className = "lf-field";
		this.#placeholderLayer.className = "lf-field-placeholder";
		this.#placeholderLayer.setAttribute("aria-hidden", "true");
		this.#placeholderLayer.setAttribute("part", "placeholder");
		const hint = document.createElement("slot");
		hint.name = "placeholder";
		hint.append(this.#placeholderText);
		this.#placeholderLayer.append(hint);
		this.#rest.className = "lf-field-rest";
		this.#rest.append(document.createElement("br"));
		this.#rest.addEventListener("focusin", () => this.#build());
		for (const type of [
			"beforeinput",
			"input",
			"compositionstart",
			"compositionend"
		]) this.#rest.addEventListener(type, (event) => this.#typeAtRest(event));
		this.#frame.append(this.#placeholderLayer, this.#rest);
		this.#root.append(this.#frame);
		this.#dressRest();
		this.addEventListener("mousedown", (event) => this.#pressPadding(event));
		this.addEventListener("dragenter", () => {
			if (!this.#view) this.#build();
		});
		this.addEventListener("scroll", () => this.#measureOverflow(), { passive: true });
		this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), { capture: true });
		for (const type of ["input", "beforeinput"]) this.#root.addEventListener(type, (event) => event.stopPropagation());
	}
	#typeAtRest(event) {
		if (this.#view || !(this.#model instanceof Draft)) return;
		if (event.type === "compositionstart") {
			this.#composing = true;
			return;
		}
		if (event.type === "beforeinput") {
			if (this.#readOnly || event.inputType === "insertParagraph" && !this.#returned() || event.inputType === "insertLineBreak" && this.#oneLine) event.preventDefault();
			return;
		}
		if (event.type === "compositionend") this.#composing = false;
		else if (this.#composing || event.isComposing) return;
		this.#readRest();
		this.#paintEmpty();
		this.dispatchEvent(new Event("input", { bubbles: true }));
		if (event.type === "compositionend" && editor) this.#build();
	}
	#readRest() {
		const words = placeWords(this.#rest);
		const kept = this.#rest.lastChild?.nodeName === "BR" ? words.slice(0, -1) : words;
		const text = this.#oneLine ? kept.replaceAll("\n", " ") : kept;
		const selection = this.#selection();
		const [range] = selection.getComposedRanges({ shadowRoots: [this.#root] });
		const at = (node, offset) => {
			if (!this.#rest.contains(node)) return text.length;
			const before = document.createRange();
			before.setStart(this.#rest, 0);
			before.setEnd(node, offset);
			return Math.min(placeWords(before.cloneContents()).length, text.length);
		};
		const from = range ? at(range.startContainer, range.startOffset) : text.length;
		const to = range ? at(range.endContainer, range.endOffset) : text.length;
		const backward = selection.direction === "backward";
		Object.assign(this.#model, {
			text,
			anchor: backward ? to : from,
			head: backward ? from : to
		});
		if (text !== kept) this.#paintRest();
	}
	#selection() {
		return this.#root.getSelection?.() ?? document.getSelection();
	}
	#paintRest() {
		if (this.#composing) return;
		const text = this.#view ? "" : this.#text;
		const here = !this.#view && this.#root.activeElement === this.#rest;
		const last = this.#rest.lastChild?.nodeName === "BR";
		const shown = placeWords(this.#rest).slice(0, last ? -1 : void 0) === text;
		const plain = (node) => node?.nodeType === Node.TEXT_NODE;
		const one = this.#rest.childNodes.length === (text ? 1 : 0) + Number(last) && (!text || plain(this.#rest.firstChild));
		if (shown && (!here || one)) return this.#placeRestCaret(here);
		this.#rest.replaceChildren(...text ? [text] : [], ...!text || text.endsWith("\n") ? [document.createElement("br")] : []);
		this.#placeRestCaret(here);
	}
	#placeRestCaret(here) {
		if (!here) return;
		const { anchor, head } = this.#range;
		const words = this.#rest.firstChild;
		if (words.nodeType === Node.TEXT_NODE) this.#selection().setBaseAndExtent(words, anchor, words, head);
		else this.#selection().setBaseAndExtent(this.#rest, 0, this.#rest, 0);
	}
	#returned() {
		return this.dispatchEvent(new Event("lf-edit-return", { cancelable: true }));
	}
	#hooks() {
		return {
			readOnly: this.#readOnly,
			attributes: this.#contentAttributes(),
			returned: () => this.#returned(),
			oneLine: () => this.#oneLine,
			revealed: (view, pos) => moveScrollerBy(this, this.#rowTravel(view, pos)),
			typed: (native, insert) => {
				this.#nativeInput = native;
				try {
					insert();
				} finally {
					this.#nativeInput = false;
				}
			}
		};
	}
	get #state() {
		return this.#view?.state ?? this.#model;
	}
	get #text() {
		const state = this.#state;
		return state instanceof Draft ? state.text : state.doc.toString();
	}
	get #length() {
		const state = this.#state;
		return state instanceof Draft ? state.text.length : state.doc.length;
	}
	get #range() {
		const state = this.#state;
		return state instanceof Draft ? state : state.selection.main;
	}
	#change(spec, draft = () => {}) {
		if (this.#view) this.#view.dispatch(spec(editor));
		else if (this.#model instanceof Draft) draft(this.#model);
		else this.#model = this.#model.update(spec(editor)).state;
	}
	attributeChangedCallback(name) {
		if (name === "placeholder") this.#placeholderText.data = this.placeholder;
		if (name === "aria-describedby") return this.#describe();
		this.#dressRest();
		this.#change((module) => module.contentAttributes(this.#contentAttributes()));
	}
	connectedMoveCallback() {
		this.#view?.placeSelection();
	}
	connectedCallback() {
		this.classList.toggle("scroll", true);
		if (this.#view) return;
		if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
		if (!this.hasAttribute("aria-multiline")) this.setAttribute("aria-multiline", "true");
		if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
		this.#internals ??= this.attachInternals();
		this.#root.adoptedStyleSheets = [sheet, this.#faces];
		if (this.#length) this.#build();
		else this.#describe();
		this.#paintEmpty();
		this.#internals.states.add("ready");
	}
	#dressRest() {
		const wanted = {
			...this.#contentAttributes(),
			role: "textbox",
			contenteditable: "plaintext-only",
			...this.#readOnly && { "aria-readonly": "true" }
		};
		for (const name of [
			"aria-label",
			"aria-placeholder",
			"aria-readonly"
		]) if (!(name in wanted)) this.#rest.removeAttribute(name);
		for (const [name, value] of Object.entries(wanted)) if (this.#rest.getAttribute(name) !== value) this.#rest.setAttribute(name, value);
	}
	#build() {
		if (this.#view) return;
		if (!editor) {
			this.#paintRest();
			if (this.#waiting) return;
			this.#waiting = holdRendering();
			loadEditor().then(() => this.isConnected && this.#build()).finally(() => {
				this.#waiting();
				this.#waiting = null;
			});
			return;
		}
		if (this.#composing) return;
		if (this.#model instanceof Draft && this.#root.activeElement === this.#rest) this.#readRest();
		this.#readFaces();
		const module = editor;
		this.#view = new module.LeafEditorView({
			root: this.#root,
			parent: this.#frame,
			state: this.#model instanceof Draft ? module.fieldState(this.#model, this.#hooks()) : this.#model,
			dispatchTransactions: (transactions, view) => {
				const edited = transactions.some((tr) => tr.docChanged);
				if (edited && !this.#nativeInput) this.#beforeEdit();
				view.update(transactions);
				module.runOwnerSteps(transactions);
				this.#paintEmpty();
				this.#measureOverflow();
				if (edited) this.dispatchEvent(new Event("input", { bubbles: true }));
				else if (transactions.some((tr) => tr.isUserEvent("select"))) this.dispatchEvent(new Event("lf-caret-move", { bubbles: true }));
			}
		});
		this.#model = null;
		this.#sizes.observe(this);
		this.#overflow.observe(this);
		this.#overflow.observe(this.#view.contentDOM);
		this.#view.scrollDOM.removeAttribute("tabindex");
		this.#describe();
		if (this.#root.activeElement === this.#rest) {
			this.#view.contentDOM.focus({ preventScroll: true });
			this.#view.placeSelection();
		}
		this.#rest.hidden = true;
		this.#paintRest();
		this.#measureOverflow();
	}
	#beforeEdit() {
		this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
	}
	disconnectedCallback() {
		queueMicrotask(() => {
			if (this.isConnected) return;
			this.#internals.states.delete("ready");
			if (!this.#view) return;
			this.#model = this.#view.state;
			this.#sizes.disconnect();
			this.#overflow.disconnect();
			this.#view.destroy();
			this.#view = null;
			this.#rest.hidden = false;
		});
	}
	#describe() {
		if (!this.isConnected) return;
		const content = this.#view?.contentDOM ?? this.#rest;
		const root = this.getRootNode();
		const described = (this.getAttribute("aria-describedby") ?? "").split(/\s+/).filter(Boolean).map((id) => root.getElementById(id)).filter(Boolean);
		const current = content.ariaDescribedByElements ?? [];
		if (described.length !== current.length || described.some((element, at) => element !== current[at])) content.ariaDescribedByElements = described;
	}
	focus(options) {
		if (!this.isConnected) return;
		this.#build();
		if (this.#view) this.#view.focus();
		else this.#rest.focus({ preventScroll: true });
		if (this.#root.activeElement !== (this.#view?.contentDOM ?? this.#rest)) return;
		if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
	}
	blur() {
		(this.#view?.contentDOM ?? this.#rest).blur();
	}
	#pressPadding(event) {
		if (event.button !== 0) return;
		if (!this.#view) {
			event.preventDefault();
			this.focus({ preventScroll: true });
			return;
		}
		const area = this.#view.scrollDOM.getBoundingClientRect();
		const { clientX: x, clientY: y } = event;
		if (x >= area.left && x < area.right && y >= area.top && y < area.bottom) return;
		event.preventDefault();
		const clamp = (value, low, high) => Math.min(Math.max(value, low), high - 1);
		const at = this.#view.posAtCoords({
			x: clamp(x, area.left, area.right),
			y: clamp(y, area.top, area.bottom)
		}, false);
		this.#view.focus();
		this.#view.dispatch({ selection: { anchor: at } });
	}
	get #oneLine() {
		return this.getAttribute("aria-multiline") === "false";
	}
	#contentAttributes() {
		const attributes = {
			spellcheck: "true",
			autocorrect: "on",
			autocapitalize: "sentences",
			"aria-multiline": String(!this.#oneLine)
		};
		if (this.placeholder) attributes["aria-placeholder"] = this.placeholder;
		const label = this.getAttribute("aria-label");
		if (label !== null) attributes["aria-label"] = label;
		return attributes;
	}
	#paintEmpty() {
		if (this.#length) this.#internals.states.delete("placeholder-shown");
		else this.#internals.states.add("placeholder-shown");
	}
	get value() {
		return this.#text;
	}
	edit(text) {
		text = String(text).replace(/\r\n?/g, "\n");
		if (text === this.value) return;
		if (!this.#view && this.isConnected) this.#build();
		this.#change(() => ({
			changes: {
				from: 0,
				to: this.#length,
				insert: text
			},
			selection: { anchor: text.length },
			userEvent: "input.dictation"
		}), (draft) => {
			if (this.isConnected) this.#beforeEdit();
			draft.text = text;
			draft.anchor = draft.head = text.length;
			if (!this.isConnected) return;
			this.#paintRest();
			this.#paintEmpty();
			this.dispatchEvent(new Event("input", { bubbles: true }));
		});
	}
	record(undo, redo) {
		this.#change((module) => module.record(undo, redo), (draft) => draft.steps.push([undo, redo]));
	}
	restartHistory() {
		this.#change((module) => module.forgetHistory, (draft) => Object.assign(draft, {
			steps: [],
			base: draft.text
		}));
		this.#change((module) => module.startHistory());
	}
	get naturalBlockSize() {
		const host = getComputedStyle(this);
		return parseFloat(getComputedStyle(this.#frame).blockSize) + parseFloat(host.paddingBlockStart) + parseFloat(host.paddingBlockEnd) + parseFloat(host.borderBlockStartWidth) + parseFloat(host.borderBlockEndWidth);
	}
	set value(text) {
		text = String(text ?? "").replace(/\r\n?/g, "\n");
		if (text === this.value) return;
		if (!this.#view && this.isConnected) this.#build();
		if (!this.#view) {
			this.#model = new Draft(text);
			if (!this.isConnected) return;
			this.#paintRest();
			this.#paintEmpty();
			return;
		}
		const content = this.#view.contentDOM;
		const composing = this.#view.composing && content.editContext;
		if (composing) content.editContext = null;
		const reset = this.#view.state.update({
			changes: {
				from: 0,
				to: this.#view.state.doc.length,
				insert: text
			},
			selection: { anchor: text.length },
			...editor.forgetHistory
		});
		const fresh = reset.state.update(editor.startHistory());
		this.#view.update([reset, fresh]);
		if (composing) content.editContext = composing;
		this.#paintEmpty();
		this.#measureOverflow();
	}
	get selectionStart() {
		const { anchor, head } = this.#range;
		return Math.min(anchor, head);
	}
	get selectionEnd() {
		const { anchor, head } = this.#range;
		return Math.max(anchor, head);
	}
	get selectionDirection() {
		const { anchor, head } = this.#range;
		return anchor === head ? "none" : head < anchor ? "backward" : "forward";
	}
	setSelectionRange(start, end, direction = "none") {
		const length = this.#length;
		const to = Math.min(Math.max(Number(end) || 0, 0), length);
		const from = Math.min(Math.max(Number(start) || 0, 0), to);
		const [anchor, head] = direction === "backward" ? [to, from] : [from, to];
		this.#change(() => ({ selection: {
			anchor,
			head
		} }), (draft) => {
			Object.assign(draft, {
				anchor,
				head
			});
			this.#paintRest();
		});
	}
	select() {
		this.setSelectionRange(0, this.#length);
	}
	get placeholder() {
		return this.getAttribute("placeholder") ?? "";
	}
	set placeholder(text) {
		this.setAttribute("placeholder", text);
	}
	get readOnly() {
		return this.#readOnly;
	}
	set readOnly(on) {
		this.#readOnly = Boolean(on);
		this.#dressRest();
		this.#change((module) => module.readOnly(this.#readOnly));
	}
	get name() {
		return this.getAttribute("name") ?? "";
	}
	set name(value) {
		this.setAttribute("name", value);
	}
};
if (!customElements.get(TEXT_FIELD)) customElements.define(TEXT_FIELD, LeafText);
const textField = () => document.createElement(TEXT_FIELD);

//#endregion
//#region runtime/composing/selection.js
const fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.dataset.lfRuntime = "";
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
const fabInput = textField();
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.name = "comment";
fabInput.placeholder = "Comment…";
fabInput.setAttribute("aria-label", "Comment");
const fab = responseAction(el("button", "lf-ui lf-fab"), {
	action: "comment",
	label: "Comment",
	behavior: "disclosure"
});
fab.id = "lf-comment-button";
fab.title = "Comment";
const fabOptions = el("span", "lf-response-options");
fabOptions.id = "lf-response-options";
fabOptions.popover = "auto";
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
const fabSuggest = responseAction(el("button", "lf-ui lf-fab-suggest"), {
	action: "suggest",
	label: "Suggest",
	collapse: true
});
fabOptions.append(fabSuggest);
const fabOptionsTrigger = offerAction("symbol", "lf-response-trigger", "Other responses", { action: "more" });
fabOptionsTrigger.setAttribute("aria-controls", fabOptions.id);
fabOptionsTrigger.setAttribute("aria-expanded", "false");
fabOptionsTrigger.popoverTargetElement = fabOptions;
fabBar.append(fab, fabOptions);
const composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
const composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
composerQuote.hidden = true;
const composerInput = fabInput;
composerInput.setAttribute("aria-describedby", composerQuote.id);
const composerField = document.createDocumentFragment();
composerField.append(composerInput);
composer.append(composerQuote);
fabBar.prepend(composer);
let pendingAnchor = null;
let pendingAbout = null;
let pendingDrawing = null;
function wordsOf(element) {
	const range = document.createRange();
	range.selectNodeContents(element);
	const words = anchorForRange(range);
	return words.quote?.trim() ? words : null;
}
let composerOpen = false;
function createSelectionComposer({ setReact, reactionTokens, reactionAvailable, designModeActive, openPageThread, anchorTravelAt, bringForward, fabAnchorAt, fabPointAt, fabFrameAt, fabPositioned, beginFabFocus, endFabFocus, landFabFocus, showFab, letGoOfFab, createComment, landSent, refreshThread, wireInput, drawingEdits }) {
	const closeReactions = () => setReact(false);
	const COMPOSER_KEY = "composer:";
	const composerCtx = (anchor) => COMPOSER_KEY + anchorKey(anchor);
	let syncComposer;
	let pendingRevision = null;
	let suggestionMode = false;
	const composerDraftPayload = () => ({
		format: DRAFT_FORMAT,
		anchor: pendingAnchor,
		revision: pendingRevision,
		suggest: suggestionMode,
		about: pendingAbout,
		drawing: pendingDrawing,
		touched: Date.now()
	});
	const saveComposerDraft = (text = syncComposer.value()) => saveDraft(composerCtx(pendingAnchor), text, composerDraftPayload());
	const composerRecord = (ctx) => {
		const payload = loadDraftPayload(ctx);
		return payload?.format === "leaf-draft/17" ? {
			...payload,
			text: loadDraft(ctx)
		} : null;
	};
	const draftDrawing = (anchor) => {
		return composerRecord(composerCtx(anchor))?.drawing ?? null;
	};
	function heldDrawings() {
		const at = composerCtx(pendingAnchor);
		const held = [];
		for (const ctx of draftContexts()) {
			if (!ctx.startsWith(COMPOSER_KEY)) continue;
			const record = composerRecord(ctx);
			const drawing = ctx === at ? pendingDrawing : record?.drawing;
			if (!record || !drawing) continue;
			held.push({
				anchor: record.anchor,
				drawing,
				open: composerOpen && ctx === at
			});
		}
		return held;
	}
	function setDraftDrawing(anchor, drawing) {
		const ctx = composerCtx(anchor);
		if (ctx === composerCtx(pendingAnchor)) {
			pendingDrawing = drawing;
			saveComposerDraft();
			syncSuggestMode();
			return;
		}
		const record = composerRecord(ctx);
		if (!record) return;
		const { text, ...payload } = record;
		if (!text && !drawing) clearDraft(ctx);
		else saveDraft(ctx, text, {
			...payload,
			drawing
		});
	}
	const watchHeldDrawings = (callback) => watchDrafts(COMPOSER_KEY, callback);
	function pendingComposer() {
		let best = null;
		for (const ctx of draftContexts()) {
			if (!ctx.startsWith(COMPOSER_KEY)) continue;
			const record = composerRecord(ctx);
			if ((record?.text || record?.drawing) && (!best || record.touched > best.touched)) best = record;
		}
		return best;
	}
	let composerEpoch = 0;
	const holdsContent = (draft) => Boolean(draft || pendingDrawing);
	const composerHolds = () => holdsContent(syncComposer.value());
	function syncSuggestMode() {
		const suggest = !suggestionMode;
		responseAction(fabSuggest, {
			action: suggest ? "suggest" : "comment",
			label: suggest ? "Suggest" : "Comment",
			collapse: true
		});
		keeps(fabSuggest, "aria-label", suggest ? "Suggest" : "Comment");
		keeps(fabSuggest, "title", suggest ? "Suggest" : "Comment");
		syncComposer();
		syncResponseOptions();
		repaint();
	}
	function setSuggestionMode(suggest) {
		suggestionMode = Boolean(suggest);
		if (suggestionMode && syncComposer.hasMedia()) {
			suggestionMode = false;
			syncSuggestMode();
			raiseError("Remove attached images before suggesting replacement text");
			focusDestination(composerInput, "return");
			return;
		}
		if (suggestionMode && !syncComposer.value() && pendingAnchor?.quote) syncComposer.load(seededQuote = pendingAnchor.quote);
		syncSuggestMode();
		saveComposerDraft();
		focusDestination(composerInput, "return");
	}
	let responseOptionsOpen = false;
	const availableResponseOptions = () => [...fabOptions.querySelectorAll(".lf-response-action:not([hidden])")];
	const responseOptionsAreOpen = () => responseOptionsOpen;
	const responseOptionsAvailable = () => availableResponseOptions().length > 0;
	const responseOptionButtons = () => availableResponseOptions().filter((control) => control.checkVisibility());
	const focusedResponseOption = () => responseOptionButtons().includes(focused());
	const responseReactionButtons = () => responseOptionButtons().filter((control) => control.classList.contains("lf-react"));
	function stepResponseOptions(binding) {
		const choices = responseOptionButtons();
		if (!choices.length) return;
		const backward = [rowArrows(choices[0])[0], "ArrowUp"].includes(binding);
		focusDestination(cycledRow(choices, focused(), backward ? -1 : 1), "move");
		beginWalk("response-option", "Response", () => listWalkPosition(responseOptionButtons(), focused()));
	}
	const focusResponseOption = (focus) => {
		const mayFocus = retainUserIntent();
		fabPositioned().then((positioned) => {
			if (!positioned || !responseOptionsOpen) return;
			const options = responseOptionButtons();
			const destination = focus === "reaction" ? options.find((control) => control.classList.contains("lf-react")) : options[0];
			if (destination) mayFocus.handoff(() => focusDestination(destination, "move"));
			paintKeys();
		});
	};
	function setResponseOptions(open, { focus = null } = {}) {
		const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
		if (next === responseOptionsOpen) {
			if (next && focus) focusResponseOption(focus);
			return next;
		}
		if (next) setReact(false);
		responseOptionsOpen = next;
		keeps(fabOptionsTrigger, "aria-expanded", String(next));
		if (next) showNativeLayer(fabOptions, { source: fabOptionsTrigger });
		else closeNativeLayer(fabOptions);
		if (next && focus) focusResponseOption(focus);
		paintKeys();
		return next;
	}
	function syncResponseOptions(anchor = fabAnchorAt()) {
		keepsHidden(fabSuggest, !(anchor?.quote && !designModeActive() && (!composerOpen || !pendingAbout && !pendingDrawing)));
		keepsHidden(fabOptionsTrigger, !responseOptionsAvailable());
		if (responseOptionsOpen && !responseOptionsAvailable()) setResponseOptions(false);
	}
	function resetResponseOptions() {
		setResponseOptions(false);
	}
	function showComposer(open) {
		if (open && composerField.hasChildNodes()) composer.append(composerField);
		if (!open) syncComposer?.cancelDictation();
		if (composerOpen && !open && composerHolds()) notice("Draft kept — g i resumes writing");
		composerOpen = open;
		composer.toggleAttribute("data-lf-open", open);
		refreshThread();
		repaint();
	}
	let seededQuote = "";
	function adoptComposerDraft({ anchor, revision, text, suggest, about, drawing }) {
		const retargeted = JSON.stringify(pendingAnchor) !== JSON.stringify(anchor);
		if (syncComposer.value() !== text) {
			syncComposer.load(text);
			seededQuote = "";
		}
		pendingAnchor = anchor;
		pendingRevision = revision;
		pendingAbout = about ?? null;
		pendingDrawing = drawing ?? null;
		suggestionMode = Boolean(suggest);
		return retargeted;
	}
	function openComposer(anchor, text, { suggest = void 0, about = void 0, drawing = void 0, carry = false, focus = true, point = void 0, revision = applicationState.read().document.revision } = {}) {
		closeReactions();
		const ctx = composerCtx(anchor || null);
		const previousCtx = composerCtx(pendingAnchor);
		const drawingSupplied = drawing !== void 0;
		let carriedDraft = false;
		let storedDrawing = null;
		if (previousCtx !== ctx) {
			suggest = suggest === void 0 ? false : suggest;
			about = about === void 0 ? designModeActive() ? "design" : null : about;
			if (seededQuote && composerInput.value === seededQuote) syncComposer.load("");
			seededQuote = "";
			composerEpoch += 1;
			const previousText = syncComposer.value();
			const previousDrawing = pendingDrawing;
			syncComposer.load("");
			const record = text ? null : composerRecord(ctx);
			storedDrawing = composerRecord(ctx)?.drawing ?? null;
			if (carry && previousText && !previousDrawing && !(record?.text || record?.drawing)) {
				text ||= previousText;
				carriedDraft = true;
			} else if (record) ({text, suggest, about} = record);
		}
		adoptComposerDraft({
			anchor: anchor || null,
			revision,
			text: text || syncComposer.value(),
			suggest: suggest === void 0 ? suggestionMode : suggest,
			about: about === void 0 ? pendingAbout : about,
			drawing: previousCtx !== ctx ? storedDrawing : pendingDrawing
		});
		const target = pendingAnchor?.section ? elementById(pendingAnchor.section) : null;
		keeps(fabBar, "data-lf-paint-plane", target && inChrome(target) ? "chrome" : "page");
		if (previousCtx !== ctx) syncComposer.arrive();
		if (drawingSupplied) pendingDrawing = drawing ?? null;
		let handoff = 0;
		if (focus) handoff = beginFabFocus();
		else endFabFocus();
		showComposer(true);
		showFab(anchor, {
			point,
			reveal: true
		});
		syncSuggestMode();
		if (focus) {
			const focusEpoch = composerEpoch;
			landFabFocus(handoff, pendingAnchor, () => focusEpoch === composerEpoch);
		}
		watchComposer();
		if (carriedDraft) transferDraft(previousCtx, ctx, syncComposer.value(), composerDraftPayload());
		else if (drawingSupplied && JSON.stringify(composerRecord(ctx)?.drawing ?? null) !== JSON.stringify(pendingDrawing)) {
			saveComposerDraft();
			rememberWriting(composerInput);
		}
	}
	function openComposerWithMedia(anchor, images, options = {}) {
		openComposer(anchor, "", {
			carry: true,
			...options
		});
		return syncComposer.addMedia(images);
	}
	let composerWatch = null;
	function watchComposer() {
		composerWatch?.();
		composerWatch = watchDraft(composerCtx(pendingAnchor), (value) => {
			if (value === null) return settleComposer();
			const record = composerRecord(composerCtx(pendingAnchor));
			if (!record) return settleComposer();
			const outside = syncComposer.value() !== record.text || JSON.stringify(record.drawing ?? null) !== JSON.stringify(pendingDrawing);
			if (adoptComposerDraft(record) && composerOpen) showFab(pendingAnchor);
			if (outside) syncComposer.arrive();
			syncSuggestMode();
			refreshThread();
		}, { input: fabInput });
	}
	const hideComposer = () => showComposer(false);
	function leaveComposer(discard) {
		if (discard) clearDraft(composerCtx(pendingAnchor));
		composerWatch?.();
		composerWatch = null;
		syncComposer.load("");
		seededQuote = "";
		suggestionMode = false;
		pendingAnchor = null;
		pendingRevision = null;
		pendingAbout = null;
		pendingDrawing = null;
		syncComposer.arrive();
		syncSuggestMode();
		hideComposer();
	}
	function detachComposer() {
		composerEpoch += 1;
		leaveComposer(false);
	}
	function carryComposerToReply(ctx) {
		if (!pendingAnchor) return;
		const text = syncComposer.value();
		if (ctx && text && !loadDraft(ctx) && !suggestionMode && !pendingAbout && !pendingDrawing && !syncComposer.hasMedia()) transferDraft(composerCtx(pendingAnchor), ctx, text);
		detachComposer();
		showFab(null);
	}
	function settleComposer() {
		leaveComposer(false);
		letGoOfFab();
	}
	function openDraft(record = pendingComposer(), { focus = true } = {}) {
		if (!record) return false;
		openComposer(record.anchor, record.text, {
			...record,
			focus
		});
		return true;
	}
	registerWritingDestination(COMPOSER_KEY, (ctx) => {
		const record = composerRecord(ctx);
		if (!record) return null;
		return {
			hasContent: Boolean(record.text || record.drawing),
			where: anchorTravelAt(record.anchor) ?? composerInput,
			input: () => composerOpen && composerCtx(pendingAnchor) === ctx ? composerInput : null,
			open: () => {
				openDraft(composerRecord(ctx), { focus: false });
				const handoff = beginFabFocus();
				return () => endFabFocus(handoff);
			},
			present: fabPositioned
		};
	});
	function mount() {
		declareResponseOptionKeys();
		syncComposer = wireInput(composerInput, {
			hint: () => suggestionMode ? "Replacement text" : pendingAbout ? "About the layer" : "Comment…",
			sends: () => suggestionMode ? "suggest" : "comment",
			allowsMedia: () => suggestionMode ? "Images can be added to comments, not replacement text" : true,
			hasContent: holdsContent,
			save: saveComposerDraft,
			drawing: {
				read: () => pendingDrawing,
				target: () => drawingEdits.target(pendingAnchor),
				replace: (drawn) => drawingEdits.replace(pendingAnchor, drawn),
				undoStroke: () => drawingEdits.undoStroke(pendingAnchor),
				remove: () => drawingEdits.remove(pendingAnchor)
			},
			send: async (_text, raw, owns, visible) => {
				const anchor = structuredClone(pendingAnchor);
				const revision = pendingRevision;
				const ctx = composerCtx(anchor);
				const suggestion = suggestionMode;
				const about = pendingAbout;
				const drawing = pendingDrawing && sentDrawing(structuredClone(pendingDrawing));
				const origin = fabFrameAt();
				const point = fabPointAt();
				const epoch = composerEpoch;
				const currentIntent = retainUserIntent();
				const untouched = retainUserIntent({ source: document.documentElement });
				let flight = null;
				const sent = sendMessage(ctx, () => composerCtx(pendingAnchor) === ctx && owns(), (attempt) => {
					if (point) commitPoint(attempt, point, wordsOf(point));
					const event = {
						anchor,
						revision,
						attempt
					};
					if (raw) event.text = raw;
					if (suggestion) event.suggestion = true;
					if (about) event.about = about;
					if (drawing) event.drawing = drawing;
					return flight = createComment(event);
				});
				if (!sent) return;
				Promise.resolve(flight).then((accepted) => {
					if (accepted || composerEpoch !== epoch || composerOpen) return;
					const record = composerRecord(ctx);
					if (record && untouched()) untouched.handoff(() => openDraft(record));
				});
				const revealSent = bindQueuedWork((options) => openPageThread(sent.id, options));
				await refreshThread();
				const revealAvailable = () => composerEpoch === epoch && loadDraft(ctx) === null && !pageSelection();
				const mayReveal = () => revealAvailable() && currentIntent();
				if (mayReveal()) {
					const destination = await revealSent({
						part: "thread",
						focus: true,
						travel: false,
						intent: restrictUserIntent(currentIntent, revealAvailable),
						origin
					});
					const thread = destination && closestAcross(destination, ".lf-page-thread, [data-lf-thread-view]");
					if (mayReveal() && thread) currentIntent.handoff(() => landSent(thread));
				}
			}
		});
		composerInput.parentElement.append(fabOptionsTrigger);
		fabSuggest.onclick = () => {
			setResponseOptions(false);
			setSuggestionMode(!suggestionMode);
		};
		fabOptions.addEventListener("toggle", () => {
			if (!isNativeLayer(fabOptions)) setResponseOptions(false);
		});
		onCurrentLocation((node) => {
			if (node && responseOptionsOpen && !fabBar.contains(node)) setResponseOptions(false);
		});
		fab.onclick = () => {
			if (!fabAnchorAt()) return;
			openComposer(fabAnchorAt(), "");
		};
	}
	const RESPONSE_OPTIONS_TITLE = "With other responses open";
	const RESPONSE_REACTION = {
		id: "response.reaction.choose",
		touch: false,
		ready: savedReadingSettled,
		keys: () => reactionTokens().slice(0, 9).map((_, index) => String(index + 1)),
		label: () => {
			const count = Math.min(reactionTokens().length, 9);
			return count > 1 ? `1–${count}` : "1";
		},
		description: () => reactionTokens().slice(0, 9).map(([name, entry], index) => `${index + 1} ${entry.glyph} ${name}`).join(", "),
		title: "react",
		when: () => reactionAvailable() && !takesLetters(focused()) && responseReactionButtons().length > 0,
		run: (binding) => responseReactionButtons()[+binding - 1]?.click()
	};
	const RESPONSE_MOVE = {
		id: "response.move",
		touch: false,
		keys: [
			"ArrowLeft",
			"ArrowRight",
			"ArrowUp",
			"ArrowDown"
		],
		title: "move",
		repeat: true,
		when: () => focusedResponseOption(),
		run: stepResponseOptions
	};
	const RESPONSE_ACTIVATE = {
		id: "response.activate",
		touch: false,
		keys: PRESS,
		title: "choose",
		when: () => focusedResponseOption() && (!focused().classList.contains("lf-react") || reactionAvailable()),
		run: () => focused()?.click()
	};
	const RESPONSE_CLOSE = {
		id: "response.close",
		touch: false,
		keys: ["Escape"],
		title: "close",
		run: () => closeLayer(() => setResponseOptions(false), () => {
			const back = [fabInput, fab].find((control) => control.checkVisibility());
			if (back) focusDestination(back, "return");
		})
	};
	const responseOptionRows = () => [
		RESPONSE_REACTION,
		RESPONSE_MOVE,
		RESPONSE_ACTIVATE,
		RESPONSE_CLOSE
	];
	pageScope("response options", {
		title: RESPONSE_OPTIONS_TITLE,
		escape: "inner",
		at: () => responseOptionsAreOpen() && focused() === fabInput,
		rows: responseOptionRows()
	});
	function declareResponseOptionKeys() {
		keys(fabOptions, RESPONSE_OPTIONS_TITLE, responseOptionRows(), {
			when: responseOptionsAreOpen,
			escape: "inner"
		});
	}
	return {
		pendingComposer,
		draftDrawing,
		heldDrawings,
		watchHeldDrawings,
		setDraftDrawing,
		draftKey: composerCtx,
		composerHolds,
		responseOptionsAreOpen,
		responseOptionsAvailable,
		setResponseOptions,
		syncResponseOptions,
		resetResponseOptions,
		openComposer,
		openComposerWithMedia,
		hideComposer,
		detachComposer,
		carryComposerToReply,
		openDraft,
		mount
	};
}

//#endregion
//#region runtime/margin-model.js
const TOGGLE = Object.freeze({
	action: "more",
	label: "More options"
});
const FOLDED = Object.freeze(Object.fromEntries(Object.entries(KINDS).map(([kind, { icon, label }]) => [kind, Object.freeze({
	icon,
	label
})])));
const EXPANDED_MARGIN_ENTRY_BUDGET = 6;
function annotationItems(entry) {
	const represented = new Set(entry.offers.flatMap(({ reading }) => reading.entries.filter((record) => record.visible).map((record) => record.owner)));
	return entry.items.filter((item) => !item.owner || !represented.has(item.owner));
}
const noticeItems = (entry) => entry.offers.flatMap((offered) => {
	const notice = offered.reading.notice;
	if (!notice) return [];
	return [Object.freeze({
		kind: "notice",
		key: offered,
		notice,
		offered
	})];
});
const deriveEntryState = (entry) => {
	return [...entry.offers.map(contributionState), ...entry.items.map((item) => item.state ?? item.workflowFace?.state ?? "idle")].sort((left, right) => contributionEntryStateRank(left) - contributionEntryStateRank(right))[0] ?? "idle";
};
const entryState = (entry) => entry.state;
const entryEngaged = (entry) => entry.state !== "idle";
const controlReceipt = (carrier, record) => carrier?.key === record.key && carrier.owner === record.owner ? carrier.receipt : record.workflowReceipt;
const contributionItem = (offered, record, carrier, cluster = null) => Object.freeze({
	cluster,
	kind: "contribution",
	offered,
	record,
	receipt: controlReceipt(carrier, record)
});
const visibleRecords = (offers) => offers.flatMap((offered) => offered.reading.entries.filter((record) => record.visible).map((record) => ({
	offered,
	record
})));
const entryControls = (entry) => [...entry.controls, ...entry.afterControls].sort(compareContributionEntryRecords);
const choosePrimary = (entry) => entry.controls[0] ?? null;
const entryHasMarginHost = (entry) => entry.hasMarginHost;
const readingKey = (entry, choice) => JSON.stringify([entry.key, choice.key]);
const deriveReadingChoices = (items) => {
	const threadList = [];
	const choices = [];
	for (const item of items.filter((item) => item.marker !== false)) if (item.kind === "comment") threadList.push(item);
	else choices.push({
		key: contributionItemKey(item),
		kind: item.kind,
		items: [item],
		text: item.text
	});
	if (threadList.length) choices.push({
		key: "threadList",
		kind: "comment",
		items: threadList,
		text: threadList[0].text
	});
	return Object.freeze(choices.map((choice) => Object.freeze({
		...choice,
		items: Object.freeze(choice.items)
	})).sort((left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority || left.items[0].id.localeCompare(right.items[0].id) || left.key.localeCompare(right.key)));
};
const readingChoices = (entry) => entry.choices;
const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
const threadReading = (entry) => readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
const secondaryReadings = (entry, primaryControl) => readingChoices(entry).slice(primaryControl ? 0 : 1);
const secondaryCount = (entry, primary) => secondaryReadings(entry, primary).length + entry.controls.length - Number(Boolean(primary)) + entry.afterControls.length;
const optionsOffered = (entry, primary) => secondaryCount(entry, primary) > 1;
function readingLabel(choice) {
	const face = readingFace(choice);
	const items = choice?.items ?? [];
	if (items.length > 1) return `${face.label}s`;
	return items[0]?.label || face.label;
}
function markerFace(entry) {
	const kinds = kindsIn(entry, { markerOnly: true });
	const choice = primaryReading(entry);
	const face = readingFace(choice);
	const faceCount = choice?.items.length ?? 0;
	return {
		kinds,
		face,
		label: readingLabel(choice),
		count: faceCount
	};
}
function readingFace(choice) {
	return choice?.items.length === 1 && choice.items[0].workflowFace || KINDS[choice?.kind] || KINDS.action;
}
function readingState(choice) {
	return (choice?.items ?? []).map((item) => item.state ?? item.workflowFace?.state ?? "idle").sort((left, right) => contributionEntryStateRank(left) - contributionEntryStateRank(right))[0] ?? "idle";
}
const readingBehavior = (face) => face.indication ? "status" : "disclosure";
const userAttention = (items) => {
	let first = null;
	for (const item of items) {
		const attention = item.userAttention;
		if (!attention) continue;
		if (attention.reason === "obligation") return attention;
		first ??= attention;
	}
	return first;
};
const awaitingUser = (items) => Boolean(userAttention(items));
const unreadIn = (items) => items.reduce((sum, item) => sum + (item.unread ?? 0), 0);
function threadMarks(thread, agent) {
	const attention = threadAttention(thread, agent);
	const onUser = attention?.kind === "needs_user";
	const receipt = attention?.kind === "waiting" ? attention.workflow : null;
	const unread = thread.unread.length;
	const line = attention && (!receipt || receipt.condition) && attention.label || (unread ? `${unread} unread` : null);
	return {
		userAttention: onUser ? {
			label: attention.label,
			reason: thread.attention?.reason ?? "workflow"
		} : null,
		unread,
		context: line,
		mapContext: line,
		workflowReceipt: receipt
	};
}
function readingContext(choice) {
	const items = choice?.items ?? [];
	const attention = userAttention(items);
	if (attention) return attention.label;
	if (items.length === 1) return items[0].context ?? null;
	const unread = unreadIn(items);
	return unread ? `${unread} unread` : null;
}
const spokenContext = (choice) => {
	const items = choice?.items ?? [];
	return choice?.kind === "comment" || awaitingUser(items) || unreadIn(items) ? readingContext(choice) : null;
};
function kindsIn(entry, { markerOnly = false } = {}) {
	const counts = /* @__PURE__ */ new Map();
	for (const item of entry.items) if (!markerOnly || item.marker !== false) counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
	return [...counts].map(([kind, count]) => ({
		kind,
		count,
		...KINDS[kind]
	}));
}
const readingItem = (entry, choice) => Object.freeze({
	kind: "reading",
	key: `reading:${readingKey(entry, choice)}`,
	entry,
	choice
});
function optionItems(entry, primary, focusedOffer = null) {
	if (focusedOffer) return focusedOffer.reading.entries.filter((record) => record.visible).map((record) => contributionItem(focusedOffer, record, entry.workflowCarrier, entry));
	return [
		...entry.controls.slice(primary ? 1 : 0).map((item) => Object.freeze({
			...item,
			cluster: entry
		})),
		...secondaryReadings(entry, primary).map((choice) => readingItem(entry, choice)),
		...entry.afterControls.map((item) => Object.freeze({
			...item,
			cluster: entry
		}))
	];
}
function optionGroupProjection(entry, primary, optionsOpen, focusedOffer = null, forcedInlineKey = null, folded = false) {
	const items = optionItems(entry, primary, focusedOffer);
	const peerCapacity = Math.max(0, EXPANDED_MARGIN_ENTRY_BUDGET - (!focusedOffer && (primary || entry.choices.length) ? 1 : 0));
	const needsSpill = items.length > peerCapacity;
	const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
	const hidden = Math.max(0, items.length - visibleCapacity);
	const direct = items.slice(0, visibleCapacity);
	const forcedThread = forcedInlineKey === entry.key ? items.find((item) => item.choice?.kind === "comment") : null;
	if (forcedThread && direct.length && !direct.includes(forcedThread)) direct[direct.length - 1] = forcedThread;
	const firstSpilled = items.find((item) => !direct.includes(item));
	return Object.freeze({
		entry,
		entryKey: entry.key,
		label: `${entryEngaged(entry) || folded ? "Actions" : "More options"} for ${spokenSubject(entry.title)}`,
		hidden: !optionsOpen || direct.length === 0,
		items: Object.freeze(items),
		spill: needsSpill ? Object.freeze({
			count: hidden,
			first: firstSpilled,
			label: `Show ${hidden} more in Page Map`
		}) : null,
		visible: Object.freeze(direct)
	});
}
const focusedOfferOf = (entry, expandedKey, expandedOwner) => expandedKey === entry.key && expandedOwner ? entry.offers.find((offered) => offered.key === expandedOwner) ?? null : null;
function canFold(entry, { expandedKey = null, expandedOwner = null } = {}) {
	if (focusedOfferOf(entry, expandedKey, expandedOwner)) return false;
	const primary = choosePrimary(entry);
	return Boolean(primary) && secondaryCount(entry, primary) > 0 && entry.choices.length === 0 && noticeItems(entry).length === 0 && !entryEngaged(entry);
}
function clusterProjection(entry, { expandedKey = null, expandedOwner = null, forcedInlineKey = null, folded = false } = {}) {
	const focusedOffer = focusedOfferOf(entry, expandedKey, expandedOwner);
	const primary = focusedOffer ? null : choosePrimary(entry);
	const folds = folded && canFold(entry, {
		expandedKey,
		expandedOwner
	});
	const shown = folds ? null : primary;
	const subject = spokenSubject(entry.title);
	const secondaries = focusedOffer ? focusedOffer.reading.entries.filter((record) => record.visible).length : secondaryCount(entry, primary);
	const hasOptions = folds || secondaries > (focusedOffer ? 0 : 1);
	const optionsOpen = secondaries > 0 && (!hasOptions || expandedKey === entry.key || entryEngaged(entry));
	const kind = folds ? primary.offered.reading.kind ?? "action" : null;
	return Object.freeze({
		primary,
		hasOptions,
		optionsOpen,
		optionsExpanded: optionsOpen && expandedKey === entry.key,
		folded: folds,
		options: optionGroupProjection(entry, shown, optionsOpen, focusedOffer, forcedInlineKey, folds),
		direct: Object.freeze([...shown ? [shown] : [], ...noticeItems(entry)]),
		entry,
		kind: "page",
		label: `Page actions for ${subject}`,
		toggle: kind ? FOLDED[kind] : TOGGLE,
		moreLabel: kind ? `${KINDS[kind].label}, ${subject}` : `More options for ${subject}`,
		offers: entry.offers,
		hasPrimary: Boolean(shown),
		state: entryState(entry),
		target: entry.targetId || entry.key
	});
}
function marginInventory(groups) {
	return Object.freeze(groups.map((group) => {
		const represented = new Set(group.items.filter((item) => item.marker === false && item.represents).map((item) => item.kind));
		let items = group.items.filter((item) => item.marker === false || item.workflowFace || !represented.has(item.kind)).sort((left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority || (left.kind === "comment" ? 0 : left.id.localeCompare(right.id)));
		const direct = group.offers.filter((offered) => offered.reading.side === "before" || offered.reading.hasReadings);
		const after = group.offers.filter((offered) => offered.reading.side === "after" && !offered.reading.hasReadings).sort(compareContributions);
		const directRecords = visibleRecords(direct).sort(compareContributionEntryRecords);
		const primary = directRecords[0];
		const receipt = group.workflowReceipt;
		const workflowCarrier = primary && receipt ? Object.freeze({
			key: primary.record.key,
			owner: primary.record.owner,
			receipt
		}) : null;
		const controlsFrom = (records) => records.map(({ offered, record }) => contributionItem(offered, record, workflowCarrier));
		const controls = Object.freeze(controlsFrom(directRecords));
		const afterControls = Object.freeze(after.flatMap((offered) => controlsFrom(visibleRecords([offered]).sort(compareContributionEntryRecords))));
		if (workflowCarrier) items = items.filter((item) => !(item.workflowFace && item.carriesWorkflow));
		return Object.freeze({
			...group,
			items: Object.freeze(items),
			controls,
			afterControls,
			choices: deriveReadingChoices(items),
			state: deriveEntryState({
				offers: group.offers,
				items
			}),
			hasMarginHost: controls.length > 0 || afterControls.length > 0 || items.some((item) => item.marker !== false),
			workflowCarrier
		});
	}));
}

//#endregion
//#region runtime/projection/state.js
const currentProjection = readPart((root) => root.effective.projection);

//#endregion
//#region runtime/thread/placement.js
const threadPlace = (t, placedAt) => {
	const place = placedAt(t.id)?.place ?? (t.anchor ? sectionOf(t.anchor) : null);
	return place?.isConnected && !leafSurface(place) ? place : null;
};
const inPageOrder = (threads, placedAt) => byRenderedOrder(threads, (t) => threadPlace(t, placedAt));
let outlined = null;
function pageOutline() {
	const key = [pageReadingVersion(), documentChanged()];
	if (outlined?.key.every((part, index) => part === key[index])) return outlined.outline;
	const outline = Object.freeze(byRenderedOrder(pageParts("h1, h2, h3, h4, h5, h6"), (heading) => heading));
	outlined = {
		key,
		outline
	};
	return outline;
}
const HEADERS = "header, hgroup";
const headed = (heading) => {
	const at = upFrom(heading);
	return at?.matches(HEADERS) ? upFrom(at) : at;
};
function partOver(node, outline = pageOutline()) {
	const heads = /* @__PURE__ */ new Map();
	for (const heading of outline) if (renderedOrder(heading, node) < 0) heads.set(headed(heading), heading);
	for (let at = upFrom(node); at; at = upFrom(at)) {
		const heading = heads.get(at);
		if (heading) return heading;
		if (declaredName(at)) return at;
	}
	return null;
}
const subjectLabel = (target) => addressableLabel(target) || addressableWord(target);
function outlineSubjectFor(target, peers = [target], outline = pageOutline()) {
	const label = subjectLabel(target);
	return {
		label,
		context: outline.includes(target) && peers.some((candidate) => candidate !== target && outline.includes(candidate) && subjectLabel(candidate) === label) ? regionLabel(target) : ""
	};
}
function regionLabel(node) {
	for (let region = readingRegionFor(node); region; region = readingRegionFor(upFrom(region.host))) {
		const label = region.host.getAttribute("aria-label")?.trim();
		if (label) return label;
	}
	return "";
}

//#endregion
//#region runtime/annotation-inventory.js
const annotationSelection = (root) => ({
	projection: root.effective.projection,
	obligations: root.effective.obligations,
	workflows: root.effective.workflows,
	revision: root.document.revision,
	todos: root.authoritative?.browser.todos ?? null
});
function createAnnotationInventory({ readObligations, placedAt, openThread, goToObligation, scrollToElement }) {
	const humanized = (value) => String(value ?? "").replace(/[-_]+/g, " ").trim();
	function targetPath(target) {
		const host = shadowHost(target.getRootNode());
		const prefix = host ? `${targetPath(host)}/shadow/` : "";
		if (target.id) return `${prefix}id:${target.id}`;
		const steps = [];
		let from = "path:";
		for (let node = target; node;) {
			if (node.dataset?.lfProjection && node.hasAttribute("data-lf-datum")) {
				from = `datum:${node.dataset.lfProjection}/${node.dataset.lfDatum}:`;
				break;
			}
			const parent = node.parentElement ?? (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
			if (!parent) break;
			const siblings = [...parent.children].filter((candidate) => !candidate.classList.contains("lf-ui") && !candidate.hasAttribute("data-lf-gen"));
			steps.push(`${node.localName}:${siblings.indexOf(node)}`);
			if (node.localName === "main" || parent instanceof ShadowRoot) break;
			node = parent;
		}
		return `${prefix}${from}${steps.reverse().join("/")}`;
	}
	const standsBy = (group) => group.point ?? targetSegments(group.passage)[0]?.node ?? group.target;
	const startsAt = (group) => targetSegments(group.passage)[0]?.start ?? -1;
	function comesBefore(left, right) {
		if (left === right) return 0;
		if (!left) return 1;
		if (!right) return -1;
		return renderedOrder(left, right);
	}
	const targets = /* @__PURE__ */ new Map();
	const itemSources = /* @__PURE__ */ new WeakMap();
	const targetFor = (entry) => entry ? targets.get(entry.key) ?? null : null;
	const points = /* @__PURE__ */ new Map();
	const entryPoint = (entry) => entry ? livePoint(targetFor(entry), points.get(entry.key)) : null;
	const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
	const passages = /* @__PURE__ */ new Map();
	const entryPassage = (entry) => entry ? passages.get(entry.key) ?? null : null;
	const pointName = (words) => {
		const excerpt = words && excerptWords(words, 32);
		return excerpt ? `“${excerpt}”` : null;
	};
	const sourceItem = (item) => itemSources.get(item);
	function captureItem(item) {
		const { activate, discloses, thread, ...data } = item;
		const snapshot = Object.freeze({
			...data,
			carriesWorkflow: Boolean(workflowReceipt([item]))
		});
		itemSources.set(snapshot, {
			activate,
			discloses,
			thread
		});
		return snapshot;
	}
	const workflows = () => runtime.workflows;
	const workflowReceipt = (items) => {
		const receipts = new Set(items.map((item) => item.workflowReceipt?.id));
		return strongestWorkflow(workflows().filter((workflow) => receipts.has(workflow.id) && isWorkflowProgress(workflow)));
	};
	function groupFor(groups, target, pointed = null) {
		const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
		const slot = pointed ? `point:${key}` : target;
		let group = groups.get(slot);
		if (!group) {
			const word = addressableWord(target);
			group = {
				key,
				target,
				point: pointed?.element ?? null,
				passage: pointed?.passage ?? null,
				pointWords: pointed?.words ?? null,
				word,
				subject: null,
				title: null,
				items: [],
				offers: []
			};
			groups.set(slot, group);
		}
		return group;
	}
	function passageRow(target, passage) {
		const segments = targetSegments(passage);
		const page = textNodesUnder(target);
		const at = page.findIndex(({ node }) => node === segments[0].node);
		const before = at < 0 ? page : [...page.slice(0, at), {
			...page[at],
			end: segments[0].start
		}];
		const words = quoteFrom(segments);
		return JSON.stringify([words, quoteFrom(before).split(words).length - 1]);
	}
	function add(groups, target, item, pointed = null) {
		if (!target?.isConnected || inChrome(target)) return;
		groupFor(groups, target, pointed).items.push(item);
	}
	function visibleWidgetWorkflows() {
		return workflows().filter((workflow) => isPageWidgetWorkflow(workflow, runtime.currentRevision));
	}
	function agentWorkflowFace(receipt) {
		if (!receipt) return null;
		const label = workflowLabel(receipt, agentName());
		if (!label) return null;
		return {
			kind: receipt.condition ? "waiting" : receipt.at_work ? "activity" : receipt.stage === "picked_up" ? "pickup" : receipt.stage === "queued" ? "queued" : "sent",
			text: label,
			context: [receipt.ts ? ago(receipt.ts) : "", receipt.detail].filter(Boolean).join(" · ")
		};
	}
	const marginThreadItem = (thread) => thread ? `comment:${threadKey(thread)}` : null;
	let entries = Object.freeze([]);
	const watchers = /* @__PURE__ */ new Set();
	const threadHasDiscussion = (thread) => replyAvailable(thread) || heldOut(thread.id);
	function threadIdsAt(node) {
		const place = placeOf$1(node);
		let best = null;
		for (const thread of threadList()) {
			if (!threadHasDiscussion(thread)) continue;
			const placement = placedAt(thread.id);
			const target = placement?.place;
			if (!target || !under(place, target)) continue;
			const point = livePoint(target, placement.point);
			const rank = !point ? 1 : under(place, point) ? 2 : 0;
			if (best && target === best.target && point === best.point) {
				best.ids.push(thread.id);
				continue;
			}
			if (!best || (target === best.target ? rank >= best.rank : under(target, best.target))) best = {
				target,
				point,
				rank,
				ids: [thread.id]
			};
		}
		return best?.ids ?? [];
	}
	function collectEntries() {
		const groups = /* @__PURE__ */ new Map();
		const receiptByCoordinate = /* @__PURE__ */ new Map();
		for (const receipt of visibleWidgetWorkflows()) {
			const coordinate = receipt.coordinate;
			receiptByCoordinate.set(stateCoordinate(...coordinate), receipt);
		}
		for (const thread of threadList()) {
			if (!threadHasDiscussion(thread) || !thread.anchor || claimed(thread.id)) continue;
			const id = thread.id;
			const target = placedAt(id)?.place;
			const placement = placedAt(id);
			const point = livePoint(target, placement?.point);
			const pointed = point ? {
				key: placement.pointRow,
				element: point,
				words: placement.pointWords
			} : targetSegments(placement).length ? {
				key: passageRow(target, placement),
				passage: placement,
				words: thread.anchor.quote
			} : null;
			add(groups, target, {
				kind: "comment",
				id: marginThreadItem(thread),
				text: threadName(thread),
				thread,
				...threadMarks(thread, agentName()),
				activate: () => openThread(id)
			}, pointed);
		}
		const placed = () => readObligations().user.filter((item) => obligationPlace(item).node);
		for (const item of placed()) {
			const id = item.id;
			const target = obligationPlace(item).node;
			add(groups, target, {
				kind: "on-me",
				id: `on-me:${id}`,
				text: "Waiting on me",
				label: (item.source.kind === "todo" ? item.prompt.text : addressableLabel(target)) || null,
				activate: () => {
					const items = placed();
					const next = items.find((candidate) => candidate.id === id);
					if (next) goToObligation(next, items);
				}
			});
		}
		const projection = currentProjection();
		const activityAlreadyShown = /* @__PURE__ */ new Set();
		const acknowledged = /* @__PURE__ */ new Set();
		for (const [coordinate, entry] of projection.desired) {
			if (entry.e.kind !== "action") continue;
			const target = elementById(entry.unit) ?? elementById(entry.e.widget);
			if (!target) continue;
			const receipt = receiptByCoordinate.get(coordinate);
			if (!receipt) continue;
			const account = [
				addressableWord(target),
				humanized(entry.e.action),
				addressableLabel(target)
			].filter(Boolean).join(" · ");
			const face = agentWorkflowFace(receipt);
			if (!face) continue;
			if (face.kind === "activity") activityAlreadyShown.add(`widget:${receipt.subject.id}`);
			acknowledged.add(target);
			add(groups, target, {
				kind: face.kind,
				id: `acknowledgment:${receipt.id}`,
				text: labelWords(`${face.text} · ${account}`),
				workflowFace: Object.freeze({
					...KINDS[face.kind],
					label: face.text,
					voice: workflowVoice(receipt)
				}),
				workflowReceipt: receipt,
				...face.context ? { context: face.context } : {},
				activate: () => revealTarget(target, `${face.text}: ${account}`, scrollToElement)
			});
		}
		for (const origin of projectionOrigins(authoredStates(), projection)) {
			const target = elementById(origin.unit);
			if (!target) continue;
			if (origin.origin === "user" && acknowledged.has(target)) continue;
			const face = KINDS[origin.origin];
			add(groups, target, {
				kind: origin.origin,
				id: `state-origin:${origin.origin}:${origin.unit}`,
				marker: false,
				text: labelWords([
					face.label,
					addressableWord(target),
					addressableLabel(target)
				].filter(Boolean).join(" · ")),
				activate: () => revealTarget(target, `${face.label}: ${addressableLabel(target) || addressableWord(target)}`, scrollToElement)
			});
		}
		const base = comparisonBase();
		comparisonChanges().forEach((target, index) => {
			const account = `${addressableWord(target)} changed${base == null ? "" : ` since v${base}`}`;
			const inline = inlineComparison(target);
			const mapAccount = inline ? `${addressableWord(target)} changed` : account;
			add(groups, target, {
				kind: "change",
				id: `change:${targetPath(target)}:${index}`,
				text: labelWords([mapAccount, addressableLabel(target)].filter(Boolean).join(" · ")),
				...inline ? {
					context: inline.offer,
					mapContext: inline.offer
				} : {},
				discloses: () => inlineComparison(target),
				activate: () => {
					const said = toggleInlineComparison(target);
					revealTarget(target, said ? `${account} · ${said}` : account, scrollToElement);
				}
			});
		});
		for (const todo of runtime.todos) {
			if (todo.owner !== "agent" || todo.state !== "open" || todo.subject.kind !== "widget" && todo.subject.kind !== "element" || todo.revision > runtime.currentRevision) continue;
			if (activityAlreadyShown.has(`widget:${todo.subject.id}`)) continue;
			const target = elementById(todo.subject.id);
			const { running } = todo;
			const label = todoLabel(running);
			const account = [todo.agent, running?.text ?? todo.title].filter(Boolean).join(" · ");
			const age = running && ago(running.ts);
			add(groups, target, {
				kind: "activity",
				id: `todo:${todo.id}`,
				text: labelWords(account),
				workflowFace: Object.freeze({
					...KINDS.activity,
					label
				}),
				context: [age && `Checked in ${age}`, running && todo.title].filter(Boolean).join(" · "),
				activate: () => revealTarget(target, account, scrollToElement)
			});
		}
		for (const offered of contributionEntries()) {
			const target = offered.target();
			if (!target?.isConnected || inChrome(target)) continue;
			const group = groupFor(groups, target);
			if (group.offers.some((candidate) => candidate.key === offered.key)) throw new TypeError(`Duplicate margin contribution key for ${target.id || targetPath(target)}: ${offered.key}`);
			group.offers.push(offered);
			const subject = offered.reading.subject;
			if (String(subject ?? "").trim()) {
				if (group.subject && group.subject !== String(subject).trim()) throw new TypeError(`Conflicting margin contribution subjects for ${target.id || targetPath(target)}`);
				group.subject = String(subject).trim();
			}
			for (const item of offered.reading.readings) {
				const kind = item.kind ?? "action";
				if (!KINDS[kind]) throw new TypeError(`Unknown margin reading kind: ${kind}`);
				group.items.push({
					marker: false,
					...item,
					owner: offered.key,
					kind,
					activate: () => offered.registration.activateReading(item.id)
				});
			}
		}
		const outline = pageOutline();
		const collected = [...groups.values()];
		const subjects = collected.filter((group) => !group.subject).map((group) => group.target);
		targets.clear();
		points.clear();
		passages.clear();
		entries = marginInventory(collected.sort((left, right) => comesBefore(standsBy(left), standsBy(right)) || startsAt(left) - startsAt(right)).map((group) => {
			const subject = outlineSubjectFor(group.target, subjects, outline);
			targets.set(group.key, group.target);
			if (group.point) points.set(group.key, group.point);
			if (group.passage) passages.set(group.key, group.passage);
			return Object.freeze({
				key: group.key,
				targetId: group.target.id,
				title: labelWords([
					group.subject ? null : subject.context,
					group.word,
					group.subject ?? addressableLabel(group.target),
					pointName(group.pointWords)
				].filter(Boolean).join(" · ")),
				offers: Object.freeze(group.offers.map((offered) => offered.model)),
				items: Object.freeze(group.items.map(captureItem)),
				workflowReceipt: workflowReceipt(group.items)
			});
		}));
		for (const watcher of watchers) watcher(entries);
		return entries;
	}
	function revealTarget(target, account, scrollToElement) {
		if (!target?.isConnected) return;
		scrollToElement(target, scrollBehavior(), "nearest");
		notice(account);
	}
	return Object.freeze({
		collect: collectEntries,
		read: () => entries,
		watch(watcher) {
			watchers.add(watcher);
			try {
				watcher(entries);
			} catch (error) {
				watchers.delete(watcher);
				throw error;
			}
			return () => watchers.delete(watcher);
		},
		targetFor,
		entryPoint,
		entryPlace,
		entryPassage,
		sourceItem,
		workflowReceipt,
		targetPath,
		threadItem: marginThreadItem,
		threadIdsAt,
		activate: (item) => sourceItem(item)?.activate()
	});
}

//#endregion
//#region runtime/reactions.js
const reactionVocabulary = () => registry.$reactions?.tokens ?? {};
const reactionTokens = () => Object.entries(reactionVocabulary());
const reactionAvailable = () => readThreads().phase === "ready";
const anchorChoices = (anchor) => reactionAvailable() ? tokenChoices(reactionVocabulary(), anchor ? reactionsAt(allThreads(), anchor) : []) : [];
function reactionChip({ name, glyph, label }, pressed) {
	const chip = offer("button", `lf-react ${HOLDS_WORD}`);
	chip.dataset.token = name;
	chip.title = label;
	chip.setAttribute("aria-label", label);
	responseAction(chip, {
		glyph,
		label: name,
		collapse: true
	});
	keys(chip, "On a reaction", [{
		id: `reaction.${name}`,
		ready: savedReadingSettled,
		when: reactionAvailable,
		keys: [],
		control: chip,
		title: label,
		run: () => pressed(name)
	}]);
	return chip;
}
function paintBarReactions(anchor) {
	const by = new Map(anchorChoices(anchor).map((choice) => [choice.name, choice]));
	for (const chip of fabBar.querySelectorAll(".lf-react-palette > .lf-react")) {
		const inForce = by.get(chip.dataset.token)?.inForce;
		keeps(chip, "aria-pressed", String(Boolean(inForce)));
	}
}
function createReactionController({ marginEntryChoices, marginEntryContextContains, openMarginEntryOptions, designModeActive, hideComposer, syncResponseOptions, fabAnchorAt, fabReturnPlaces, fabTargetAt, hasPageSelectionTarget, showFab, showFabOptions, updateFab, currentLocationThread, currentTarget }) {
	const surfaces = /* @__PURE__ */ new WeakMap();
	const marginSurface = Symbol("margin reactions");
	let marginOffer = null;
	let marginTarget = null;
	let marginAnchor = null;
	let pageCommands = null;
	const marginReactionKey = (name, ordinal) => `reaction:${String(ordinal).padStart(4, "0")}:${name}`;
	function registerReactSurface(surface, { palette, trigger }) {
		surfaces.set(surface, {
			palette,
			trigger
		});
		return {
			toggle: () => setReact(!(reactArmed && reactSurface === surface), { surface }),
			close: () => {
				if (reactSurface === surface) setReact(false);
			}
		};
	}
	function buildReactBar(commands) {
		pageCommands = commands;
		const palette = el("span", "lf-react-palette");
		palette.setAttribute("role", "group");
		palette.setAttribute("aria-label", "Reactions for this selection or element");
		for (const choice of tokenChoices(reactionVocabulary(), [])) palette.append(reactionChip(choice, (token) => reactHere(token, commands)));
		fabOptions.append(palette);
		syncResponseOptions();
	}
	const anchorWord = (anchor) => {
		if (!anchor) return "the target";
		if (anchor.quote) return "the selection";
		const addressable = elementById(anchor.section);
		if (anchor.visual) return visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
		return addressableWord(addressable) || "the element";
	};
	async function reactHere(name, commands, anchor = fabAnchorAt()) {
		const choice = anchorChoices(anchor).find((choice) => choice.name === name);
		if (!choice) return;
		const { inForce } = choice;
		const returnTo = fabReturnPlaces();
		if (!anchor) return;
		let sent;
		if (inForce) sent = commands.withdrawReaction(inForce);
		else {
			const event = {
				kind: "comment",
				revision: runtime.currentRevision,
				token: name,
				anchor: structuredClone(anchor)
			};
			if (designModeActive()) event.about = "design";
			sent = sendReaction(event, anchorWord(anchor), commands.postReaction);
		}
		closeLayer(() => {
			hideComposer();
			showFab(null);
			setReact(false);
		}, () => handBack(...returnTo));
		getSelection()?.removeAllRanges();
		await sent;
	}
	let reactArmed = false;
	let reactRaised = false;
	let releaseMarginOptions = null;
	const reactLayer = {};
	const reactFrom = () => openerOf(reactLayer);
	let reactSurface = null;
	let reactDeparture = null;
	const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
	const pickerFor = (surface) => surfaces.get(surface);
	function reactionTarget() {
		const said = currentLocationThread();
		const strip = said && latestAgentStrip(said.held);
		if (strip) return {
			kind: "surface",
			surface: strip
		};
		if (fabAnchorAt()) return { kind: "anchor" };
		if (hasPageSelectionTarget()) return { kind: "selection" };
		const target = currentTarget();
		return target ? {
			kind: "target",
			target
		} : null;
	}
	const hasReactionTarget = () => Boolean(reactionTarget());
	function raiseMarginSurface() {
		const anchor = fabAnchorAt();
		const target = anchor && fabTargetAt();
		if (!pageCommands || !target || !openMarginEntryOptions) return false;
		fabBar.dataset.lfMarginRaised = "1";
		marginAnchor = structuredClone(anchor);
		marginOffer = registerContribution({
			key: "responses",
			target,
			read: () => ({
				side: "after",
				entries: anchorChoices(marginAnchor).map((choice, ordinal) => ({
					key: marginReactionKey(choice.name, ordinal),
					activation: choice.name,
					glyph: choice.glyph,
					label: choice.label,
					rank: "secondary",
					className: "lf-react",
					pressed: Boolean(choice.inForce)
				})),
				readings: []
			}),
			activate: (name) => reactHere(name, pageCommands, marginAnchor)
		});
		marginTarget = target;
		const release = openMarginEntryOptions(target, "responses");
		if (release) {
			releaseMarginOptions = release;
			return true;
		}
		marginOffer.unregister();
		marginOffer = null;
		marginTarget = null;
		marginAnchor = null;
		return false;
	}
	function lowerMarginSurface() {
		releaseMarginOptions?.();
		releaseMarginOptions = null;
		marginOffer?.unregister();
		marginOffer = null;
		marginTarget = null;
		marginAnchor = null;
		delete fabBar.dataset.lfMarginRaised;
	}
	function closeSurface(surface) {
		if (surface === marginSurface) return;
		reactDeparture?.();
		reactDeparture = null;
		const picker = pickerFor(surface);
		if (picker) closeNativeLayer(picker.palette);
		picker?.trigger.setAttribute("aria-expanded", "false");
	}
	function syncReactLayout() {
		return reactArmed && reactSurface === marginSurface;
	}
	function setReact(on, { surface = null } = {}) {
		if (on && !reactionAvailable()) return;
		if (!on && !reactArmed) {
			if (!(marginOffer || fabBar.hasAttribute("data-lf-margin-raised"))) return;
			closeSurface(reactSurface);
			lowerMarginSurface();
			repaint();
			return;
		}
		if (on === reactArmed && (surface === reactSurface || !surface)) return;
		if (on && claimsEsc(focused())) return;
		const closingActive = on ? null : focused();
		if (!on) {
			closeReact(closingActive);
			repaint();
			return;
		}
		closeSurface(reactSurface);
		if (on) {
			openLayer(reactLayer);
			if (surface) reactSurface = surface;
			else {
				const target = reactionTarget();
				if (target?.kind === "surface") reactSurface = target.surface;
				else if (target?.kind === "anchor" || target?.kind === "target") {
					if (target.kind === "target") {
						showFab(target.target.anchor, { place: false });
						reactRaised = true;
					}
					if (!raiseMarginSurface()) {
						if (reactRaised) showFab(null);
						reactRaised = false;
						reactSurface = null;
						openLayer(reactLayer, null);
						raiseError("That reaction target is no longer available");
						return;
					}
					reactSurface = marginSurface;
				} else {
					reactSurface = null;
					openLayer(reactLayer, null);
					return;
				}
			}
			if (reactSurface !== marginSurface && !pickerFor(reactSurface)) {
				reactSurface = null;
				openLayer(reactLayer, null);
				return;
			}
			reactArmed = true;
			if (reactSurface !== marginSurface) {
				const picker = pickerFor(reactSurface);
				scrollIntoReadingBand(picker.trigger, picker.trigger, "nearest", "instant");
				showNativeLayer(picker.palette, { source: picker.trigger });
				const opened = reactSurface;
				const seen = (trigger) => seenRect(trigger, clipsPastSurfaces());
				reactDeparture = whenNone([picker.trigger], seen, () => {
					if (reactSurface === opened) setReact(false);
				});
				picker.trigger.setAttribute("aria-expanded", "true");
				const first = surface && reactFrom() === picker.trigger && picker.palette.querySelector(".lf-react");
				if (first) focusDestination(first, "move");
			}
			announce(`React — ${saying(REACT.rows)}`);
		}
		repaint();
	}
	function closeReact(active) {
		const from = reactFrom();
		const trigger = pickerFor(reactSurface)?.trigger;
		const input = fabBar.querySelector(".lf-fab-input");
		const owed = fabBar.contains(from) || marginOffer?.contains(active) || active === document.body || active?.closest?.(".lf-react-palette");
		const candidates = from ? [
			input,
			from,
			trigger
		] : [input];
		closeLayer(() => {
			closeSurface(reactSurface);
			reactArmed = false;
			reactSurface = null;
			openLayer(reactLayer, null);
			if (reactRaised) showFab(null);
			reactRaised = false;
			lowerMarginSurface();
			if (fabAnchorAt()) showFab(fabAnchorAt());
		}, owed && (() => handBack(...candidates.filter(drawn))));
	}
	function responseChoices(surface) {
		if (!surface) return [];
		if (surface === marginSurface) return marginEntryChoices(fabTargetAt());
		return [...surface.querySelectorAll(".lf-react-palette > .lf-react")].filter((choice) => choice.checkVisibility());
	}
	function stepResponse(binding) {
		const choices = responseChoices(reactSurface);
		if (!choices.length) return;
		const backward = [
			rowArrows(choices[0])[0],
			"ArrowUp",
			"Shift+Tab"
		].includes(binding);
		focusDestination(cycledRow(choices, focused(), backward ? -1 : 1), "move");
		beginWalk("reaction", "Reaction", () => listWalkPosition(responseChoices(reactSurface), focused()));
	}
	const REACT = {
		title: "With reactions open",
		ready: savedReadingSettled,
		escape: "inner",
		liveInCommandReference: true,
		at: () => reactArmed,
		root: () => reactSurface instanceof Element ? reactSurface : document,
		claims: allButCommandReference,
		rows: [
			{
				id: "reaction.choose",
				touch: false,
				runFromCommandReference: false,
				keys: () => reactionTokens().slice(0, 9).map((_, i) => String(i + 1)),
				label: () => {
					const n = Math.min(reactionTokens().length, 9);
					return n > 1 ? `1–${n}` : "1";
				},
				description: () => reactionTokens().slice(0, 9).map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`).join(", "),
				title: "react",
				when: reactionAvailable,
				run: (binding) => {
					if (reactSurface === marginSurface) {
						const ordinal = +binding - 1;
						const token = reactionTokens()[ordinal]?.[0];
						if (token) marginOffer?.activate(marginReactionKey(token, ordinal), {
							origin: focused(),
							input: "keyboard",
							surface: "margin"
						});
						return;
					}
					pickerFor(reactSurface)?.palette.querySelectorAll(".lf-react")[+binding - 1]?.click();
				}
			},
			{
				id: "reaction.move",
				touch: false,
				runFromCommandReference: false,
				keys: [
					"Tab",
					"Shift+Tab",
					"ArrowLeft",
					"ArrowRight",
					"ArrowUp",
					"ArrowDown"
				],
				title: "move",
				repeat: true,
				run: stepResponse
			},
			{
				id: "response.activate",
				touch: false,
				runFromCommandReference: false,
				keys: PRESS,
				title: "choose",
				when: () => responseChoices(reactSurface).includes(focused()),
				run: () => focused()?.click()
			},
			{
				id: "reaction.cancel",
				touch: false,
				keys: ["Escape"],
				title: "cancel",
				run: () => setReact(false)
			}
		]
	};
	const isReactArmed = () => reactArmed;
	const reactionContextContains = (node) => reactArmed && reactSurface === marginSurface && marginEntryContextContains?.(fabTargetAt(), node);
	function mount() {
		document.addEventListener("lf-margin-entry-options-closed", () => {
			if (reactArmed && reactSurface === marginSurface) setReact(false);
		});
		const margin = readPart((root) => ({
			threads: root.effective.thread.all,
			annotations: annotationSelection(root)
		}));
		x(() => {
			margin();
			d(() => {
				if (reactArmed && reactSurface === marginSurface && (!marginTarget?.isConnected || fabTargetAt() !== marginTarget)) setReact(false);
				else if (reactArmed && reactSurface === marginSurface) marginOffer?.update();
			});
		});
	}
	pageScope("reactions", REACT);
	pageCommand({
		id: "reaction.open",
		ready: savedReadingSettled,
		touch: false,
		keys: ["e"],
		description: "On the selection, the focused item or the open reply",
		title: "reactions",
		when: () => reactionAvailable() && reactionTokens().length > 0 && hasReactionTarget() && (anchoringIsReady() || !pageSelection()),
		run: () => {
			if (pageSelection() && !fabAnchorAt()) updateFab();
			if (composerOpen && fabAnchorAt()) showFabOptions({ reaction: true });
			else setReact(true);
		}
	});
	return {
		registerReactSurface,
		buildReactBar,
		hasReactionTarget,
		syncReactLayout,
		setReact,
		isReactArmed,
		reactionContextContains,
		mount
	};
}
async function sendReaction(event, where, postReaction) {
	const sent = await postReaction(event);
	if (sent) announce(`${event.token} on ${where}`);
	return sent;
}
function reactionPlace(event) {
	if (event.kind === "reply") return "the reply";
	if (!event.anchor) return "the page";
	return anchorLabel(event.anchor, event.about);
}

//#endregion
//#region runtime/undo.js
const WAIT = "Wait for the current change to finish before undoing";
const quoted = (words, cap = 60) => `“${excerptWords(words, cap)}”`;
function widgetNamed(id) {
	const element = elementById(id);
	if (!element) return "a widget";
	const label = addressableLabel(element);
	return label ? quoted(label) : `the ${addressableWord(element)}`;
}
function actionWords(event, gesture) {
	const widget = widgetNamed(event.widget);
	switch (gesture?.form) {
		case "choice": return `chose ${gesture.chosen.map((words) => quoted(words)).join(", ") || "nothing"} in ${widget}`;
		case "move": return `moved ${quoted(gesture.unit)} to ${quoted(gesture.to)} in ${widget}`;
		case "edit": return `edited ${widget}`;
		case "add": return `added ${quoted(gesture.words)} to ${widget}`;
		case "verb": return `recorded “${gesture.verb}” on ${widget}`;
		default: return `updated ${widget}`;
	}
}
const TODO_ENDINGS = {
	done: (title) => `marked ${title} done`,
	failed: (title) => `marked ${title} failed`,
	dropped: (title) => `dropped ${title}`
};
function gestureWords(event, gesture) {
	if (event.token) return `${event.token} reaction on ${reactionPlace(event)}`;
	switch (event.kind) {
		case "resolve":
		case "unresolve": {
			const thread = threadNamed(event.parent);
			const name = thread ? quoted(threadName(thread), 48) : "a thread";
			return `${event.kind === "resolve" ? "resolved" : "reopened"} ${name}`;
		}
		case "todo_end": {
			const todo = runtime.todos.find(({ id }) => id === event.todo);
			return TODO_ENDINGS[event.outcome](todo ? quoted(todo.title) : "a to-do");
		}
		default: return actionWords(event, gesture);
	}
}
function placeOf(event) {
	if ([
		"resolve",
		"unresolve",
		"reply"
	].includes(event.kind)) return {
		thread: threadIdNamed(event.parent),
		nodes: []
	};
	const id = event.kind === "action" ? event.widget : event.anchor?.section;
	if (!id) return null;
	const held = messageHolding(id);
	if (held) return {
		thread: held.thread,
		message: held.message,
		nodes: [held.element]
	};
	return {
		fragment: id,
		nodes: [elementById(id)]
	};
}
const seen = (where) => Boolean(where && seenRect(placeHolder(where), /* @__PURE__ */ new Map(), placeBox(where)));
const KEYS_HELD = /* @__PURE__ */ new Set([
	"Shift",
	"Control",
	"Alt",
	"Meta",
	"CapsLock",
	"Fn"
]);
const UNDO_KEYS = ["z"];
function createUndo({ post, stateApplying, unaccountedGesture, openThread, threadPlace }) {
	const gestures = /* @__PURE__ */ new Map();
	function retainGesture(attempt, facts) {
		const { effective, unresolved } = readApplication();
		if (effective.view) {
			const liveAttempts = /* @__PURE__ */ new Set([...effective.view.undo.map(({ event }) => event.attempt), ...unresolved.map((entry) => entry.event.attempt)]);
			for (const kept of gestures.keys()) if (!liveAttempts.has(kept)) gestures.delete(kept);
		}
		gestures.set(attempt, {
			...gestures.get(attempt),
			...facts
		});
	}
	const said = (event) => {
		const gesture = runtime.undo.find((entry) => entry.event.id === event.id)?.gesture;
		return gestures.get(event.attempt)?.says ?? gestureWords(event, gesture);
	};
	const takes = (event) => [said(event), ago(event.ts)].filter(Boolean).join(" · ");
	const head = () => {
		const [first] = runtime.undo;
		return first?.newest ? first.event : null;
	};
	function undoable() {
		return stateApplying() ? null : head();
	}
	function withdrawable(event) {
		if (event.kind !== "action" && String(event.id).startsWith("pending:")) return false;
		return !applicationState.unpresented().some((entry) => entry.event.kind === "action" && (entry.admitted?.id ?? entry.localId) !== event.id);
	}
	function withdraw(event) {
		if (!withdrawable(event)) {
			raiseError(WAIT);
			return null;
		}
		const taken = takes(event);
		return post({
			kind: "undo",
			undoes: event.id
		}).then((accepted) => {
			if (accepted) {
				notice(`Undid: ${taken}`);
				gestures.delete(event.attempt);
			}
			return accepted;
		});
	}
	let armed = null;
	function disarm() {
		armed?.stop();
		armed = null;
	}
	onUserInput((event) => {
		if (!armed || event.type === "blur") return;
		if (event.type === "wheel" && !armed.returns) return;
		if (event.type === "keydown" && (event.repeat || KEYS_HELD.has(event.key) || UNDO_KEYS.includes(event.key))) return;
		if ((event.type === "pointerdown" || event.type === "touchstart") && inChrome(event.composedPath()[0])) return;
		armed.inputs.push(inputCount());
		if (armed.inputs.length > 1) disarm();
	});
	const armedFor = (event) => Boolean(armed?.is(event)) && armed.shown && armed.inputs.every((input) => input === inputCount());
	function landedAway(attempt) {
		disarm();
		armed = {
			is: (event) => event.attempt === attempt,
			stop: () => {},
			inputs: [],
			shown: true,
			returns: true
		};
	}
	const drawingsOf = (id) => [...[...document.querySelectorAll(THREAD)].filter((node) => drawnThreadId(node) === id), surfaceFocusTarget(id, { part: "thread" })];
	const inView = (place) => [...place.thread ? [threadPlace(place.thread), ...drawingsOf(place.thread)] : [], ...place.nodes].some(seen);
	function needsShowing(entry) {
		if (entry.picked_up) return true;
		const place = placeOf(entry.event);
		return Boolean(place) && !inView(place);
	}
	async function returnToThread(id, intent) {
		const seated = drawingsOf(id).find((node) => node && !inChrome(node) && seen(node));
		if (!seated) return openThread(id, {
			part: "thread",
			intent
		});
		intent.handoff(() => focusDestination(seated, "move"));
		return seated;
	}
	async function show(event, intent = retainUserIntent()) {
		const place = placeOf(event);
		if (!place) return [];
		if (place.message) return [await openThread(place.message, {
			part: "message",
			intent
		}), ...place.nodes].filter(Boolean);
		if (place.thread) return [await returnToThread(place.thread, intent)].filter(Boolean);
		const url = new URL(window.location.href);
		url.hash = place.fragment;
		if (window.navigation) await window.navigation.navigate(url.href).finished.catch(() => {});
		else window.location.assign(url);
		return place.nodes.filter(Boolean);
	}
	function arm(event) {
		disarm();
		let stop = () => {};
		const current = {
			is: (other) => other.id === event.id,
			stop: () => stop(),
			inputs: [],
			shown: false,
			returns: false
		};
		armed = current;
		notice(`Press again to undo: ${takes(event)}`);
		show(event).then((nodes) => {
			if (armed !== current) return;
			current.shown = true;
			if (!nodes.length) return;
			let landed = false;
			stop = whenNone(nodes, (node, clips) => {
				const shown = seenRect(node, clips);
				landed ||= Boolean(shown);
				return shown;
			}, () => {
				if (landed && armed === current) disarm();
			});
		});
	}
	function undoLast() {
		if (stateApplying() || unaccountedGesture()) {
			raiseError(WAIT);
			return null;
		}
		const event = undoable();
		if (!event) return null;
		const [entry] = runtime.undo;
		const taking = armedFor(event) && !(armed.returns && entry.picked_up);
		if (!taking && needsShowing(entry)) {
			arm(event);
			return null;
		}
		const returning = taking && armed.returns && retainUserIntent();
		const answer = withdraw(event);
		if (!answer) return null;
		disarm();
		if (returning) whenDocumentPresented().then(() => show(event, returning)).catch(() => {});
		return answer;
	}
	pageCommand({
		id: "history.undo",
		ready: savedReadingSettled,
		keys: UNDO_KEYS,
		description: () => head() ? `Undo: ${takes(head())}` : "Undo the latest update",
		title: "undo",
		touch: () => head() ? `Undo: ${said(head())}` : "Undo",
		touchValue: () => head() ? ago(head().ts) : "",
		menu: "page",
		when: () => !unaccountedGesture() && Boolean(undoable()),
		run: (...args) => undoLast(...args)
	});
	return {
		landedAway,
		returnToThread,
		retainGesture,
		undoable,
		undoLast,
		withdraw
	};
}

//#endregion
//#region runtime/projection/data.js
const projectedDescendants = (root) => [root, ...shadowRootsIn(root)].flatMap((scope) => [...scope.querySelectorAll("[data-lf-projection]")]).filter((element) => element.dataset.lfProjection === root.id);
const markOwner = (node) => {
	for (let at = composedParentNode(node); at; at = composedParentNode(at)) if (at.nodeType === Node.ELEMENT_NODE && registry[at.localName]?.["x-data"]) return at;
	return null;
};
const markedDatums = (root) => [root, ...shadowRootsIn(root)].flatMap((scope) => [...scope.querySelectorAll("[data-lf-datum]")]).filter((node) => markOwner(node) === root).map((node) => ({
	node,
	key: node.dataset.lfDatum,
	label: node.dataset.lfDatumLabel,
	identity: node.dataset.lfIdentity,
	path: node.dataset.lfOriginPath
}));
const originPath = (who, key, text) => {
	let path;
	try {
		path = JSON.parse(text);
	} catch {
		path = null;
	}
	if (!Array.isArray(path) || !path.every((step) => typeof step === "string" || Number.isInteger(step) && step >= 0)) throw new TypeError(`${who} datum ${key} data-lf-origin-path must be a JSON array of field names and indices`);
	return path;
};
let constructed = null;
function projectMarked(root, snapshot) {
	if (!constructed) throw new Error("Leaf's data projection has not been constructed");
	constructed.projectMarked(root, snapshot);
}
function createDataProjection({ invalidateDom }) {
	let dataPaintQueued = false;
	const changedRoots = /* @__PURE__ */ new Set();
	const mirrored = /* @__PURE__ */ new WeakMap();
	function applyProjection(root) {
		changedRoots.add(root);
		if (dataPaintQueued) return;
		dataPaintQueued = true;
		queueMicrotask(() => {
			dataPaintQueued = false;
			for (const changed of changedRoots) if (changed.isConnected) reachScrollers(changed);
			changedRoots.clear();
			invalidateDom();
		});
	}
	function projectMarked(root, snapshot) {
		if (!root.id) throw new TypeError(`<${root.localName}> needs an id to name its drawn data`);
		const who = `<${root.localName} id=${root.id}>`;
		const stampBasis = (node) => {
			keeps(node, "data-lf-source", snapshot?.source ?? null);
			keeps(node, "data-lf-source-revision", snapshot?.revision ?? null);
		};
		stampBasis(root);
		const projected = projectedDescendants(root);
		const keys = /* @__PURE__ */ new Set();
		const identities = /* @__PURE__ */ new Set();
		const nodes = /* @__PURE__ */ new Set();
		for (const { node, key, label, identity, path } of markedDatums(root)) {
			if (!key) throw new TypeError(`${who} keys must be non-empty strings`);
			if (keys.has(key)) throw new Error(`${who} received duplicate key ${key}`);
			keys.add(key);
			if (identity !== void 0) {
				if (!identity) throw new TypeError(`${who} identity for ${key} must be a non-empty string`);
				if (identities.has(identity)) throw new Error(`${who} received duplicate identity ${identity}`);
				identities.add(identity);
			}
			nodes.add(node);
			if (label !== void 0) {
				const prior = mirrored.get(node);
				if (!node.hasAttribute("aria-label") && (!node.hasAttribute("aria-description") || node.getAttribute("aria-description") === prior)) {
					keeps(node, "aria-description", label);
					mirrored.set(node, label);
				}
			} else unmirror(node);
			keeps(node, "data-lf-gen", "1");
			keeps(node, "data-lf-projection", root.id);
			stampBasis(node);
			const origin = snapshot?.origin ? {
				...snapshot.origin,
				...path === void 0 ? {} : { path: originPath(who, key, path) }
			} : null;
			keeps(node, "data-lf-origin", origin === null ? null : JSON.stringify(origin));
		}
		for (const node of projected) if (!nodes.has(node)) {
			delete node.dataset.lfGen;
			delete node.dataset.lfProjection;
			delete node.dataset.lfSource;
			delete node.dataset.lfSourceRevision;
			delete node.dataset.lfOrigin;
			unmirror(node);
		}
		applyProjection(root);
	}
	function unmirror(node) {
		const label = mirrored.get(node);
		if (label === void 0) return;
		if (node.getAttribute("aria-description") === label) node.removeAttribute("aria-description");
		mirrored.delete(node);
	}
	constructed = { projectMarked };
	return constructed;
}

//#endregion
//#region runtime/thread/presentation.js
function renderHolds(threads) {
	const held = /* @__PURE__ */ new Map();
	for (const thread of threads) {
		if (thread.resolved || !thread.root.holds || thread.root.pending) continue;
		const target = elementById(thread.root.holds);
		if (target && !inChrome(target)) held.set(target, thread.id);
	}
	for (const node of document.querySelectorAll("[data-lf-held]")) if (!held.has(node)) node.removeAttribute("data-lf-held");
	for (const [target, id] of held) keeps(target, "data-lf-held", id);
}
function createThreadPresentation({ available = true, inlineView, surfaceView, anchorPlacement, anchorPaint, anchorControls, drawingPaint, pageGeometry, readDraft, activeActionAnchor, renderSurfaces, openThread, continueThread, returnToPage, threadAt, marginCommitted, read }) {
	let primary = null;
	const presenter = applicationPresenter({
		region: "thread",
		after: PRESENTATION_DOM.projection,
		reading: () => !available ? null : runtime.statePhase === "waiting" && !threadState().all.length ? "waiting" : true,
		paint: async (value, current, resume) => {
			await startRender(current, resume);
			return value;
		}
	});
	const present = () => presenter.present();
	let surfaceGeneration = 0;
	let cancelCurrentRender = () => {};
	const startRender = (presenting, resume = (run) => run) => {
		cancelCurrentRender();
		const { promise: cancelled, resolve } = Promise.withResolvers();
		cancelCurrentRender = resolve;
		return renderReading(cancelled, presenting, resume);
	};
	async function renderReading(cancelled, presenting, resume) {
		const generation = ++surfaceGeneration;
		read.begin();
		const current = () => generation === surfaceGeneration && presenting();
		const batch = beginThreadSeats();
		const restorePlace = holdThreadPlace(openThread, {
			threadAt,
			seated: (id) => Boolean(surfaceFocusTarget(id, { part: "thread" }))
		});
		let surfaces = null;
		try {
			const { all: threads } = threadState();
			const collection = readThreads();
			const listed = collection.threads;
			const continueReplies = holdReplyCompositions(threads, continueThread);
			renderHolds(threads);
			const readTargets = () => {
				const anchors = anchorPlacement.read({
					threads,
					draft: readDraft(),
					actionAnchor: activeActionAnchor()
				});
				if (anchors) {
					anchorPaint?.paint(anchors);
					anchorControls.render(anchors);
				}
				drawingPaint.paint();
			};
			readTargets();
			surfaces = renderSurfaces(collection, anchorPlacement, surfaceView);
			surfaces.completion.catch(() => {});
			const primaryPreparation = primary?.owner.isConnected ? primary.prepare(collection, cancelled) : null;
			const paintPrepared = (primaryCandidate) => {
				if (!current()) return;
				renderSeats(listed, inlineView);
				return Promise.race([Promise.all([surfaces.completion, Promise.resolve().then(() => current() && primaryCandidate?.current() ? primaryCandidate.paint() : null)]).then(() => true), cancelled.then(() => false)]).then(resume((completed) => {
					if (!completed || !current()) return;
					readTargets();
					surfaces.commit();
					commitThreadSeats(batch);
					surfaceView.composition.finishPlacement();
					pageGeometry.pageShifted();
					read.present();
					Promise.resolve().then(marginCommitted).then(() => continueReplies(restorePlace)).then(returnToPage).catch((error) => reportPageError(error, `Reply continuation failed`));
				}));
			};
			await (primaryPreparation?.then ? primaryPreparation.then(resume(paintPrepared)) : paintPrepared(primaryPreparation));
		} catch (error) {
			surfaces?.cancel();
			if (!current()) throw error;
			anchorControls.withholdVisualActions();
			read.abort();
			primary?.cancel();
			if (!current()) return;
			retainThreadSeats(batch);
			throw error;
		}
	}
	function registerPrimary(reader) {
		if (primary) throw new Error("The page already has a primary Thread presentation");
		primary = reader;
		present();
		return () => {
			if (primary !== reader) return;
			primary = null;
			reader.unregister();
			present();
		};
	}
	return {
		present,
		registerPrimary
	};
}

//#endregion
//#region runtime/annotation-view.js
function createAnnotationView(owner, render, inventory, invalidate, retire) {
	if (!(owner instanceof Element)) throw new TypeError("consumeAnnotations needs an Element owner");
	if (!owner.isConnected) throw new TypeError("An annotation view needs a connected owner");
	if (typeof render !== "function") throw new TypeError("consumeAnnotations needs a synchronous render callback");
	let active = true;
	let places = /* @__PURE__ */ new Map();
	let offers = /* @__PURE__ */ new Set();
	const stopSide = declareSide((node) => {
		for (const [row, entry] of places) if (under(node, row)) return inventory.entryPlace(entry);
		return null;
	});
	function paint(entries) {
		if (!active) return;
		if (!owner.isConnected) return unregister();
		const nextPlaces = /* @__PURE__ */ new Map();
		const nextOffers = /* @__PURE__ */ new Set();
		const allowed = new Set(entries);
		let painting = true;
		const admit = (entry) => {
			if (!painting || !allowed.has(entry)) throw new TypeError("Annotation capabilities belong to their current reading");
		};
		try {
			if (render(entries, {
				target: inventory.targetFor,
				activate: inventory.activate,
				items: annotationItems,
				controlKey: contributionControlKey,
				controlRecord: contributionEntryRecord,
				arriving: entries.some((entry) => entry.offers.some((model) => {
					const offered = contributionSource(model);
					const request = offered.focusRequest;
					return request && (request.surface == null || request.surface === "page") && offered.reading.entries.some((item) => item.key === request.key && item.visible);
				})),
				place(entry, row) {
					admit(entry);
					if (!(row instanceof Element) || !under(row, owner)) throw new TypeError("An annotation row must stay inside its owner");
					nextPlaces.set(row, entry);
				},
				controls(entry) {
					admit(entry);
					const retained = new Map(entry.offers.map((model) => {
						const offered = contributionSource(model);
						nextOffers.add(offered);
						return [model, materializeContributionControls(offered, "page", activateContributionControl)];
					}));
					return entryControls(entry).map(({ offered, record, receipt }) => {
						const control = retained.get(offered).get(record.key);
						presentContributionReceipts(control, receipt, false);
						return control;
					});
				}
			})?.then) throw new TypeError("Annotation paint must finish inside its inventory reading");
			for (const offered of offers) if (!nextOffers.has(offered)) clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
			offers = nextOffers;
			places = nextPlaces;
		} catch (error) {
			for (const offered of nextOffers) if (!offers.has(offered)) clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
			throw error;
		} finally {
			painting = false;
		}
	}
	let stopReading = () => {};
	function unregister() {
		if (!active) return;
		active = false;
		stopReading();
		stopSide();
		for (const offered of offers) clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
		offers.clear();
		places.clear();
		retire();
	}
	try {
		stopReading = inventory.watch(paint);
	} catch (error) {
		unregister();
		throw error;
	}
	return Object.freeze({
		read: inventory.read,
		update: invalidate,
		unregister
	});
}

//#endregion
//#region runtime/inline-contributions.js
function createInlineContributions({ targetPath }) {
	const hosts = /* @__PURE__ */ new Map();
	function present() {
		const grouped = /* @__PURE__ */ new Map();
		for (const offered of contributionEntries()) {
			const target = offered.target();
			if (!target?.isConnected || !inChrome(target) || !offered.reading.entries.some((entry) => entry.visible)) continue;
			const offers = grouped.get(target) ?? [];
			offers.push(offered);
			grouped.set(target, offers);
		}
		for (const [target, { host, offers }] of hosts) if (!grouped.has(target)) {
			for (const offered of offers) clearContributionControls(offered, "inline", /* @__PURE__ */ new Set());
			host.replaceChildren();
			host.remove();
			hosts.delete(target);
		}
		for (const [target, offers] of grouped) {
			let seat = hosts.get(target);
			if (!seat) {
				const host = el("div", "lf-ui lf-margin-inline");
				generatedElement(host, { says: false });
				host.setAttribute("role", "group");
				seat = {
					host,
					offers: []
				};
				hosts.set(target, seat);
			}
			const { host } = seat;
			for (const offered of seat.offers) if (!offers.includes(offered)) clearContributionControls(offered, "inline", /* @__PURE__ */ new Set());
			seat.offers = offers;
			host.lfTarget = target;
			keeps(host, "data-lf-margin-for", target.id || targetPath(target));
			keeps(host, "aria-label", `Actions for ${spokenSubject(addressableWord(target))}`);
			const controls = (side) => offers.filter((offered) => offered.reading.side === side).sort(compareContributions).flatMap((offered) => {
				const materialized = materializeContributionControls(offered, "inline", activateContributionControl);
				return offered.reading.entries.filter((entry) => entry.visible).map((entry) => {
					const control = materialized.get(entry.key);
					presentContributionReceipts(control, entry.workflowReceipt, false);
					return control;
				});
			});
			const nodes = [...controls("before"), ...controls("after")];
			for (const node of nodes) node.removeAttribute("data-lf-margin-entry-primary");
			const restoreFocus = holdFocus(host);
			setChildren(host, nodes);
			restoreFocus?.();
			if (target.nextSibling !== host) move(target.parentNode, host, target.nextSibling);
		}
	}
	return Object.freeze({ present });
}

//#endregion
//#region runtime/thread/destination.js
function createThreadDestinations({ placedAt, threadIdsAt, scrollToThread, arrive, prepareNavigationStep, preview = null }) {
	let presentation = null;
	let opening = null;
	const lastResort = /* @__PURE__ */ new Set();
	function register(owner, open, reader) {
		if (presentation) throw new Error("The page already has a Thread presentation");
		const registration = {
			owner,
			open,
			reader
		};
		presentation = registration;
		return () => {
			if (presentation === registration) {
				presentation = null;
				opening?.abort();
			}
		};
	}
	const threadTarget = (id) => placedAt(id)?.place ?? null;
	const threadPlace$1 = (id) => {
		const thread = allThreads().find((candidate) => candidate.id === id);
		return thread ? threadPlace(thread, placedAt) : null;
	};
	const threadHere = (active = focused()) => {
		const held = threadIn(active);
		if (held) return held;
		const shown = preview?.accompanied() ?? null;
		if (!active || active === document.body) return shown;
		const ids = threadIdsAt(active);
		const drawn = [shown, ...ids.map((id) => surfaceFocusTarget(id, { part: "thread" }))].filter((thread) => thread && ids.includes(drawnThreadId(thread)));
		return drawn.length === 1 ? drawn[0] : null;
	};
	let lastIn = null;
	onCurrentLocation((node) => {
		lastIn = drawnThreadId(threadIn(node)) ?? lastIn;
	});
	const threadAtCurrentLocation = (active = focused()) => {
		const here = drawnThreadId(threadHere(active));
		if (here) return here;
		const ids = active ? threadIdsAt(active) : [];
		return (ids.includes(lastIn) ? lastIn : ids[0]) ?? null;
	};
	const replyThreadAtCurrentLocation = () => {
		const id = threadAtCurrentLocation();
		const thread = allThreads().find((candidate) => candidate.id === id);
		return thread && replyAvailable(thread) ? id : null;
	};
	const addressedPart = (thread, id, part) => ({
		part,
		message: part === "message" ? thread.msgs.find((message) => message.id === id)?.key ?? null : null
	});
	const threadFocusTarget = (id, { part = null } = {}) => {
		const thread = threadNamed(id);
		const candidates = [
			thread && presentation?.owner.isConnected ? presentation.reader.destination(thread.key, addressedPart(thread, id, part)) : null,
			surfaceFocusTarget(id, { part }),
			preview?.focusTarget(id, { part })
		].filter(Boolean);
		return candidates.find(presented$1) ?? candidates[0] ?? null;
	};
	const DECLINED = Symbol("declined");
	const UNDRAWN = Symbol("undrawn");
	async function openPageThread(id, { part = null, focus = true, travel = true, history = true, scroll = true, intent = retainUserIntent(), origin = null, returning = false } = {}) {
		if (!intent()) return null;
		const navigationStep = travel && scroll;
		const selected = presentation?.owner.isConnected ? presentation : null;
		const thread = threadNamed(id);
		if (selected && (!thread || !discussed(thread))) return null;
		const holder = part === "message" ? authoredHolder(id) : null;
		const drawn = Boolean(selected && holder && renderedUnder(holder, selected.owner));
		function inPrimary(last) {
			opening?.abort();
			const abort = new AbortController();
			opening = abort;
			const cancelled = aborted(abort.signal);
			const whileCurrent = (work) => Promise.race([work, cancelled]);
			const request = {
				...addressedPart(thread, id, part),
				focus,
				last,
				signal: abort.signal,
				current: () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent())
			};
			const mayPresent = () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent());
			const arriving = restrictUserIntent(intent, mayPresent);
			const departure = focus !== false && navigationStep && history ? prepareNavigationStep({
				landing: () => selected.reader.destination(thread.key, request),
				intent: arriving
			}) : null;
			if (last) lastResort.add(thread.key);
			else lastResort.delete(thread.key);
			const result = selected.open(thread.key, request);
			if (result === false) lastResort.delete(thread.key);
			if (result === false && !drawn) return mayPresent() ? DECLINED : null;
			if (result !== false && preview) intent.handoff(preview.close);
			return taken(result);
			async function taken(result) {
				const selectedLayout = result?.then ? await whileCurrent(result) : result;
				if (!mayPresent()) return null;
				if (selectedLayout === false && !drawn) return DECLINED;
				await whileCurrent(selected.reader.update());
				if (!mayPresent()) return null;
				const destination = selected.reader.destination(thread.key, request);
				if (destination === null) return UNDRAWN;
				if (!(destination instanceof Element) || !destination.isConnected || !renderedUnder(destination, selected.owner) || !selected.reader.ownsDestination(destination)) throw new TypeError("A Thread destination must be a retained part of its registered presentation");
				if (focus === false) {
					await whileCurrent(reveal(destination, intent).ready);
					return mayPresent() ? destination : null;
				}
				departure?.plan(destination);
				return await whileCurrent(arrive(() => {
					const current = selected.reader.destination(thread.key, request);
					return current && {
						where: current,
						focus: current,
						scroll: navigationStep ? [{
							at: current,
							block: "nearest"
						}] : []
					};
				}, {
					intent: arriving,
					departure
				})) ? selected.reader.destination(thread.key, request) : null;
			}
		}
		async function onPage() {
			const mayPresent = () => focus === false ? intent.available() : intent();
			const localPart = part ?? "reply";
			if (part === "message") showHeld(id);
			const openSurface = async () => {
				if (preview) intent.handoff(preview.close);
				if (navigationStep) {
					if (!await scrollToThread(id, {
						part: localPart,
						focus,
						intent,
						history
					})) return null;
				} else if (focus === false) {
					await reveal(surfaceFocusTarget(id, { part: localPart }), intent).ready;
					if (!mayPresent()) return null;
				} else if (!await arrive(() => {
					const current = surfaceFocusTarget(id, { part: localPart });
					return current && {
						where: current,
						focus: current,
						scroll: scroll ? [{
							at: current,
							block: "nearest",
							behavior: "auto"
						}] : []
					};
				}, { intent })) return null;
				return surfaceFocusTarget(id, { part: localPart });
			};
			if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
			if (showHeldThread(id) && surfaceFocusTarget(id, { part: localPart })) return openSurface();
			const place = preview && !navigationStep ? threadTarget(id) : null;
			const placeDrawn = () => visibleTargetParts(place).length > 0;
			if (place && scroll && !placeDrawn()) {
				await reveal(place, intent).ready;
				if (!mayPresent()) return null;
			}
			let opened = null;
			if (preview && (!place || placeDrawn())) intent.handoff(() => {
				opened = preview.open(id, { origin });
			});
			if (opened) {
				if (navigationStep) {
					if (!await scrollToThread(id, {
						part: part ?? "thread",
						focus,
						presented: opened.presented,
						intent,
						history
					})) return null;
				} else {
					if (!await opened.presented || !mayPresent()) return null;
					if (focus !== false && !await arrive(() => {
						const current = threadFocusTarget(id, { part });
						return current && {
							where: current,
							focus: current,
							scroll: scroll ? [{
								at: current,
								block: "nearest"
							}] : []
						};
					}, { intent })) return null;
				}
				return threadFocusTarget(id, { part });
			}
			const held = revealHeld([threadIdNamed(id)]);
			if (held) {
				await held.presented;
				if (!mayPresent()) return null;
			}
			if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
			return DECLINED;
		}
		const asked = selected && !returning ? inPrimary(false) : DECLINED;
		const first = asked instanceof Promise ? await asked : asked;
		if (first !== DECLINED && first !== UNDRAWN) return first;
		const shown = await onPage();
		if (returning) {
			if (!shown || shown === DECLINED) return null;
			if (selected) await inPrimary(false);
			return shown;
		}
		if (shown !== DECLINED) return shown;
		if (!selected || first !== DECLINED) return null;
		const last = await inPrimary(true);
		return last === DECLINED || last === UNDRAWN ? null : last;
	}
	async function returnToPage() {
		const selected = presentation?.owner.isConnected ? presentation : null;
		if (!selected) return;
		for (const key of [...lastResort]) {
			const thread = allThreads().find((each) => threadKey(each) === key);
			const drawing = selected.reader.destination(key, { part: "thread" });
			if (!thread || !drawing?.checkVisibility()) {
				lastResort.delete(key);
				continue;
			}
			await openPageThread(thread.id, {
				part: "thread",
				focus: replyThreadKey(focused()) !== key && drawnThreadId(heldThread()) === thread.id,
				travel: false,
				scroll: false,
				returning: true
			});
		}
	}
	async function openThreadSubject(id, { intent = retainUserIntent() } = {}) {
		const message = placedAt(id)?.message;
		if (!message) return null;
		const { element } = messageHolding(threadNamed(id).anchor.section);
		if (!await openPageThread(message, {
			part: "message",
			focus: false,
			travel: false,
			intent
		}) || !element.isConnected) return null;
		return await arrive(() => element.isConnected && {
			where: element,
			focus: element,
			scroll: [{
				at: element,
				block: "nearest"
			}]
		}, { intent }) ? element : null;
	}
	async function openThreadDraft(context, intent) {
		const thread = threadHolding(context);
		if (!thread) return null;
		const { part, name } = threadDraft(context);
		if (part === "reply") return openPageThread(thread.id, {
			part: "reply",
			intent
		});
		const landed = await openPageThread(name, {
			part: "message",
			intent
		});
		const card = landed && closestAcross(landed, ".lf-page-thread, [data-lf-thread-view]");
		return card ? openMessageEditIn(card, name) : null;
	}
	function threadHolding(context) {
		const { part, name } = threadDraft(context);
		return part === "reply" ? allThreads().find((each) => threadKey(each) === name) : allThreads().find((each) => each.msgs.some(({ id }) => id === name));
	}
	return {
		register,
		openPageThread,
		openThreadSubject,
		openThreadDraft,
		returnToPage,
		atLastResort: (key) => lastResort.has(key),
		holdsThreadDraft: (context) => Boolean(threadHolding(context)),
		threadFocusTarget,
		threadHere,
		threadAtCurrentLocation,
		replyThreadAtCurrentLocation,
		threadTarget,
		threadPlace: threadPlace$1
	};
}

//#endregion
//#region runtime/thread/actions.js
function createThreadActions({ post, withdraw, sendReaction, currentRevision, open }) {
	const create = (command) => {
		const { text, anchor, revision = currentRevision(), attempt = randomId(), holds, about, drawing, suggestion } = command;
		if (!text && !drawing) return null;
		const delivery = post({
			kind: "comment",
			revision,
			...text !== void 0 && { text },
			...anchor !== void 0 && { anchor: structuredClone(anchor) },
			...attempt !== void 0 && { attempt },
			...holds !== void 0 && { holds },
			...about !== void 0 && { about },
			...drawing !== void 0 && { drawing: structuredClone(drawing) },
			...suggestion !== void 0 && { suggestion }
		});
		return delivery ? Object.freeze({
			key: attempt,
			delivery
		}) : null;
	};
	const find = (key) => readThreads().threads.find((thread) => thread.key === key);
	const reply = (key, text, { attempt } = {}) => {
		if (!text) return null;
		const thread = find(key);
		if (!thread) return null;
		return post({
			kind: "reply",
			revision: currentRevision(),
			parent: thread.root.id,
			text,
			...attempt && { attempt }
		});
	};
	const edit = (key, messageId, text, { attempt, base } = {}) => {
		const thread = find(key);
		if (!thread) return null;
		const message = thread.msgs.find((item) => item.id === messageId);
		if (!message || !editable(message) || !text || text === message.text) return null;
		return post({
			kind: "edit",
			message: messageId,
			text,
			base,
			...attempt && { attempt }
		});
	};
	const settle = (key, resolved, { attempt } = {}) => {
		const thread = find(key);
		if (!thread || Boolean(thread.resolved) === resolved) return null;
		return post({
			kind: resolved ? "resolve" : "unresolve",
			parent: thread.root.id,
			...attempt && { attempt }
		});
	};
	const setReaction = (key, messageKey, token, active) => {
		if (typeof active !== "boolean") throw new TypeError("A reaction needs its desired state");
		const message = find(key)?.msgs.find((item) => item.key === messageKey);
		const choice = message && message.reactions?.choices.find((item) => item.name === token);
		if (!choice || active === Boolean(choice.inForce)) return null;
		if (choice.inForce) return withdraw(choice.inForce);
		return sendReaction({
			kind: "reply",
			parent: message.id,
			revision: currentRevision(),
			token
		}, `${message.agent}'s reply`, post);
	};
	return Object.freeze({
		async open(key, { message = null, ...options } = {}) {
			const thread = find(key);
			if (!thread) return null;
			const target = message === null ? thread : thread.msgs.find((item) => item.key === message);
			if (!target) return null;
			return open(target.id, message === null ? options : {
				...options,
				part: "message"
			});
		},
		create,
		reply,
		edit,
		resolve: (key, options) => settle(key, true, options),
		reopen: (key, options) => settle(key, false, options),
		setReaction
	});
}

//#endregion
//#region runtime/queue-api.js
const queueItemKey = (item) => JSON.stringify([item.kind, item.id]);
const readQueues = readPart((root) => root.effective.queues);
const readPlan = readPart((root) => root.effective.plan);
function createQueueActions({ post, arrive }) {
	return Object.freeze({
		open(key) {
			const reading = readQueues();
			const item = [
				...reading.on_user,
				...reading.on_agent,
				...reading.done
			].find((candidate) => queueItemKey(candidate) === key);
			return item?.offers.open ? arrive(item) : Promise.resolve(false);
		},
		done(key) {
			const item = readQueues().on_user.find((candidate) => queueItemKey(candidate) === key);
			if (!item?.offers.done) return null;
			const delivery = post({
				kind: "todo_end",
				todo: item.id,
				outcome: "done"
			});
			announce("Done");
			return delivery;
		}
	});
}

//#endregion
//#region runtime/thread/primary-reader.js
function createPrimaryReader(owner, render, commands, update, { answersAtOnce = false, onFailure = () => {} } = {}) {
	let active = true;
	let failing = false;
	let failed = false;
	let generation = 0;
	let pending = null;
	let selected = [];
	const views = /* @__PURE__ */ new Map();
	const destinations = /* @__PURE__ */ new Map();
	const nativeMessages = /* @__PURE__ */ new Set();
	const held = new HeldNews(owner, (key) => {
		const parts = destinations.get(key);
		if (!parts?.length) return null;
		const whole = parts.find((part) => part instanceof ThreadView);
		if (whole) return whole;
		return {
			node: drawingOf(parts) ?? parts.at(-1).node,
			progressOpen: parts.some((part) => part.transcript?.progressOpen),
			newsMoves: (held) => !(answersAtOnce && held.answers) && parts.some((part) => part.transcript ? part.transcript.newsMoves(held) : (held.news.appended || held.news.settled || held.changed.has(part.messageKey) || held.folds.messages.includes(part.messageKey) || held.folds.summaries.length) && growthIsSeen(part.node))
		};
	}, () => void update().catch(() => {}));
	let shown = /* @__PURE__ */ new Map();
	const drawingOf = (parts) => {
		const whole = wholeThread(parts[0].node);
		return whole === parts[0].node ? null : whole;
	};
	const rewrites = /* @__PURE__ */ new Map();
	const partsOf = (key, kind) => selected.filter((item) => item.key === key && item.kind === kind).flatMap((item) => views.get(item.identity) ?? []);
	const replyOf = (key) => {
		for (const view of destinations.get(key) ?? []) {
			const input = !view.node.hidden && threadPart(view.node, "reply");
			if (input) return input;
		}
		return null;
	};
	const rewritesOf = (key) => {
		if (!rewrites.has(key)) rewrites.set(key, threadRewrites({
			thread: () => key,
			views: () => {
				const transcript = partsOf(key, "transcript")[0];
				if (transcript) return transcript.transcript.views;
				const order = shown.get(key)?.source.msgs.map((message) => message.key);
				return partsOf(key, "message").toSorted((a, b) => (order?.indexOf(a.messageKey) ?? 0) - (order?.indexOf(b.messageKey) ?? 0)).map((view) => view.message);
			},
			send: (id, text, options) => commands.reply.actions.edit(key, id, text, options),
			paint: (node) => [...partsOf(key, "transcript"), ...partsOf(key, "message")].find((view) => view.transcript || view.message.node === node)?.draw(),
			box: () => replyOf(key),
			home: (node) => node.closest(THREAD),
			opening: (id) => {
				shown.get(key)?.news?.open();
				partsOf(key, "transcript")[0]?.transcript.expandAround(id);
			},
			landInThread: commands.reply.landInThread,
			landSent: commands.reply.landSent
		}));
		return rewrites.get(key);
	};
	const clear = () => {
		for (const view of views.values()) {
			view.dispose();
			view.node.remove();
			for (const slot of view.slots ?? []) slot.remove();
		}
		views.clear();
		destinations.clear();
		nativeMessages.clear();
		rewrites.clear();
	};
	function prepare(collection, cancelled) {
		const current = ++generation;
		failing = false;
		pending?.abort();
		const abort = new AbortController();
		pending = abort;
		cancelled.then(() => abort.abort());
		const candidate = held.prepare({ threads: collection.threads.map((thread) => threadReading$1(thread, "outlet", {
			...commands,
			authoredRank: 3
		})) }, { row: false });
		const byKey = new Map(candidate.reading.threads.map((thread) => [thread.key, thread.source]));
		const shownCollection = Object.freeze({
			phase: collection.phase,
			threads: Object.freeze([...byKey.values()])
		});
		const nominations = [];
		let accepting = true;
		const nominate = (kind, key, message, outlet, options = {}) => {
			if (!accepting || abort.signal.aborted) throw new Error("Thread nominations belong to their current render callback");
			const thread = byKey.get(key);
			if (!thread) throw new Error(`No Thread has key ${key}`);
			if (message !== null && !turns(thread).some((item) => item.key === message)) throw new Error(`Thread ${key} has no turn ${message}`);
			const identity = JSON.stringify([
				kind,
				key,
				message
			]);
			const covers = (a, b) => a === "thread" || a === "transcript" && b === "message";
			if (nominations.some((item) => item.identity === identity || item.key === key && (covers(item.kind, kind) || covers(kind, item.kind)))) throw new Error("A primary reader may nominate each Thread part only once");
			nominations.push({
				identity,
				kind,
				key,
				message,
				outlet,
				thread,
				options
			});
		};
		const finish = () => {
			accepting = false;
			if (!active || current !== generation || abort.signal.aborted) return null;
			for (const item of nominations) if (!item.outlet.isConnected || !under(item.outlet, owner)) throw new Error("A primary Thread outlet must remain inside its connected owner");
			selected = nominations;
			shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
			nativeMessages.clear();
			for (const item of nominations) for (const message of item.thread.msgs) if (item.kind === "thread" || item.kind === "transcript" || item.message === message.key) nativeMessages.add(message.id);
			return {
				paint: async () => {
					try {
						await paint(current);
					} catch (error) {
						failing ||= current === generation;
						throw error;
					}
					if (active && current === generation && !abort.signal.aborted) {
						candidate.commit();
						failed = false;
					}
				},
				current: () => active && current === generation && !abort.signal.aborted
			};
		};
		try {
			const rendering = render(shownCollection, Object.freeze({
				signal: abort.signal,
				thread: (key, outlet) => nominate("thread", key, null, outlet),
				transcript: (key, outlet) => nominate("transcript", key, null, outlet),
				message: (key, id, outlet) => nominate("message", key, id, outlet),
				reply: (key, outlet, options) => nominate("reply", key, null, outlet, options),
				news: (key, outlet) => nominate("news", key, null, outlet)
			}));
			if (rendering?.then) return Promise.race([rendering, aborted(abort.signal)]).then(finish).catch((error) => {
				failing ||= !abort.signal.aborted;
				throw error;
			}).finally(() => {
				accepting = false;
			});
			return finish();
		} catch (error) {
			accepting = false;
			failing = true;
			throw error;
		}
	}
	async function paint(current) {
		if (!active || generation !== current) return;
		for (const item of selected) if (!owner.isConnected || !item.outlet.isConnected || !under(item.outlet, owner)) throw new Error("A primary Thread outlet must remain inside its connected owner");
		const wanted = new Set(selected.map((item) => item.identity));
		const keys = new Set(selected.map((item) => item.key));
		for (const key of rewrites.keys()) if (!keys.has(key)) rewrites.delete(key);
		for (const [key, view] of views) if (!wanted.has(key)) {
			view.dispose();
			view.node.remove();
			for (const slot of view.slots ?? []) slot.remove();
			views.delete(key);
		}
		destinations.clear();
		const children = /* @__PURE__ */ new Map();
		const place = (parent, node) => {
			const nodes = children.get(parent) ?? [];
			nodes.push(node);
			children.set(parent, nodes);
		};
		for (const item of selected) {
			let view = views.get(item.identity);
			if (!view) {
				if (item.kind === "thread") view = new ThreadView({
					...commands,
					authoredRank: 3
				});
				else if (item.kind === "news") {
					const notice = newsNotice();
					view = {
						node: notice.node,
						notice,
						dispose() {}
					};
				} else {
					const node = document.createElement("div");
					node.className = "lf-page-thread lf-ui lf-primary-part";
					node.dataset.lfPart = item.kind;
					node.tabIndex = -1;
					node.dataset.lfRuntime = "";
					generatedElement(node, { says: false });
					node.dataset.lfOffer = "";
					if (item.kind === "transcript") {
						const transcript = new Transcript({
							commands,
							messageCommands: {
								...commands,
								reaction: {
									...commands.reaction,
									pressed: () => shown.get(item.key)?.news?.open()
								},
								edit: rewritesOf(item.key).edit
							},
							repaint: () => view.draw(),
							home: () => node
						});
						node.append(transcript.node);
						node.dataset.lfAppendTail = "";
						view = {
							node,
							transcript,
							reading: null,
							drawn: false,
							headNotice: true,
							draw() {
								const handedOn = transcript.present(this.reading, {
									arrived: this.drawn,
									notice: this.headNotice ? this.notice.node : null
								});
								transcript.commit();
								this.drawn = true;
								if (handedOn) focusDestination(handedOn, "return");
							},
							dispose: () => transcript.retire()
						};
					} else if (item.kind === "message") {
						const message = new MessageView({
							...commands,
							reaction: {
								...commands.reaction,
								pressed: () => shown.get(item.key)?.news?.open()
							},
							edit: rewritesOf(item.key).edit
						});
						node.append(message.node);
						view = {
							node,
							message,
							messageKey: item.message,
							reading: null,
							headNotice: true,
							draw() {
								message.present(this.reading, { headerControls: this.headNotice ? this.notice.node : void 0 });
								message.commit();
							},
							dispose: () => message.retire()
						};
					} else {
						let joined = false;
						const { hint, hintLead, accessibleName, busy, sending, sent } = item.options;
						const redraw = () => {
							for (const row of node.querySelectorAll(":scope > .lf-thread-reply")) if (row !== reply.node) row.remove();
							move(node, reply.node, node.firstChild);
						};
						const reply = createReplyView(item.key, commands.reply, redraw, {
							onChange: () => {
								if (joined) update().catch(() => {});
							},
							editLast: rewritesOf(item.key).editLast,
							hint,
							hintLead,
							accessibleName,
							busy,
							sending,
							sent
						});
						joined = true;
						node.append(reply.node);
						view = {
							node,
							reply,
							dispose: reply.dispose
						};
					}
					view.notice = newsNotice();
					view.notice.node.classList.add("lf-primary-news");
				}
				views.set(item.identity, view);
			}
			if (item.kind === "thread") {
				view.present(shown.get(item.key));
				view.commit();
			} else if (item.kind === "news") {
				const news = shown.get(item.key)?.news;
				if (news) view.notice.set(news);
				keepsHidden(view.node, !news);
			} else {
				keeps(view.node, "data-thread", item.thread.id);
				keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
				const news = shown.get(item.key)?.news;
				const nominated = selected.some((part) => part.key === item.key && part.kind === "news");
				const first = selected.find((part) => part.key === item.key && (part.kind === "message" || part.kind === "transcript")) ?? selected.find((part) => part.key === item.key);
				const notice = Boolean(news) && !nominated && first === item;
				if (notice) view.notice.set(news);
				keepsHidden(view.notice.node, !notice);
				if (item.kind === "transcript") {
					view.headNotice = !nominated;
					view.reading = shown.get(item.key);
					view.draw();
				} else if (item.kind === "message") {
					const message = item.thread.msgs.find((entry) => entry.key === item.message);
					view.headNotice = !nominated;
					view.reading = messageReading(message, {
						authoredRank: 3,
						reactions: message.reactions,
						workflows: message.workflows
					});
					view.draw();
					keeps(view.node, "data-lf-append-tail", message.provisional && message === item.thread.msgs.at(-1) ? "" : null);
				} else if (nominated) view.notice.node.remove();
				else if (view.notice.node.parentNode !== view.node) move(view.node, view.notice.node, null);
			}
			const slots = view.slots ??= [];
			let destination = item.outlet;
			let previous = null;
			let depth = 0;
			for (let host; host = shadowHost(destination.getRootNode());) {
				let slot = slots[depth];
				if (!slot) {
					slot = document.createElement("slot");
					slot.name = "lf-thread-part-" + randomId();
					slots.push(slot);
				}
				keeps(slot, "slot", previous?.name ?? null);
				place(destination, slot);
				previous = slot;
				destination = host;
				depth++;
			}
			for (const slot of slots.splice(depth)) slot.remove();
			keeps(view.node, "slot", previous?.name ?? null);
			place(destination, view.node);
			if (item.kind === "news") continue;
			const parts = destinations.get(item.key) ?? [];
			parts.push(view);
			destinations.set(item.key, parts);
		}
		for (const [parent, nodes] of children) orderChildren(parent, nodes);
		for (const view of views.values()) view.reply?.claim(() => view.node.isConnected && !view.node.hidden);
		const widgets = [...readApplication().document.descriptors.values()].filter((descriptor) => descriptor.document.kind === "thread" && renderedUnder(elementById(descriptor.id), owner)).map((descriptor) => descriptor.id);
		await whenWidgetsPresented(widgets);
	}
	const destination = (key, { message = null, part = null } = {}) => {
		const parts = destinations.get(key) ?? [];
		if (message) {
			const id = shown.get(key)?.source.msgs.find((item) => item.key === message)?.id;
			if (!id) return null;
			for (const view of parts) {
				const node = view.node.querySelector(`.lf-msg[data-event="${CSS.escape(id)}"]`);
				if (node) return node;
			}
			return null;
		}
		const first = parts[0]?.node ?? null;
		if (part === "thread") return parts.length && drawingOf(parts) || first;
		return replyOf(key) || first;
	};
	return Object.freeze({
		owner,
		update,
		release: () => held.release(),
		prepare,
		destination,
		ownsMessage: (message) => owner.isConnected && nativeMessages.has(message.id),
		ownsDestination: (node) => [...views.values()].some((view) => under(node, view.node)) || [...destinations.keys()].some((key) => replyOf(key) === node) || [...destinations.values()].some((parts) => drawingOf(parts) === node),
		cancel() {
			++generation;
			pending?.abort();
			clear();
			held.release();
			if (failing) {
				failing = false;
				failed = true;
				onFailure();
			}
		},
		get failed() {
			return failed;
		},
		unregister() {
			active = false;
			++generation;
			pending?.abort();
			clear();
			held.dispose();
		}
	});
}

//#endregion
//#region runtime/thread/read.js
const keyOf = (item) => `${item.message}\u0000${item.version}`;
const EPSILON = 1;
function mergeIntervals(intervals) {
	const ordered = intervals.sort((a, b) => a[0] - b[0]);
	const merged = [];
	for (const [start, end] of ordered) {
		const prior = merged.at(-1);
		if (prior && start <= prior[1] + EPSILON) prior[1] = Math.max(prior[1], end);
		else merged.push([start, end]);
	}
	return merged;
}
function visibleInterval(body, clips, band) {
	if (!presented$1(body)) return null;
	const box = body.getBoundingClientRect();
	const clipped = seenRect(body, clips);
	if (!clipped || box.width <= 0 || box.height <= 0) return null;
	const shown = intersect(clipped, band);
	if (shown.bottom <= shown.top) return null;
	if (shown.left > box.left + EPSILON || shown.right < box.right - EPSILON) return null;
	return {
		interval: [Math.max(0, shown.top - box.top), Math.min(box.height, shown.bottom - box.top)],
		height: box.height,
		width: box.width,
		contentHeight: body.scrollHeight
	};
}
function wordsAreVisible(body, clips, band) {
	if (!presented$1(body) || !body.checkVisibility({ opacityProperty: true })) return false;
	const text = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
	const range = document.createRange();
	for (let node = text.nextNode(); node; node = text.nextNode()) {
		if (!node.textContent.trim()) continue;
		const holder = node.parentElement;
		if (!holder || !presented$1(holder) || !holder.checkVisibility({ opacityProperty: true })) continue;
		range.selectNodeContents(node);
		for (const box of range.getClientRects()) {
			const clipped = clippedContents(box, holder, clips);
			if (!clipped) continue;
			const room = shownWindow({
				within: clipped,
				item: holder
			});
			if (hasArea(intersect(intersect(clipped, room), band))) return true;
		}
	}
	return false;
}
function createReadTracking({ markRead, openThread }) {
	let coverage = /* @__PURE__ */ new WeakMap();
	const renderedBodies = /* @__PURE__ */ new Map();
	const visibleReplies = /* @__PURE__ */ new Set();
	const refusedThisVisit = /* @__PURE__ */ new Set();
	const sizes = sizeObserver(() => scheduleScan());
	const frameWatches = [];
	const committedThreads = Z([]);
	let threadsPresented = false;
	let presentationGeneration = 0;
	let visitGeneration = 0;
	let scheduled = false;
	let passWaiters = [];
	function resetExposure() {
		visitGeneration++;
		exposureGeneration++;
		coverage = /* @__PURE__ */ new WeakMap();
		refusedThisVisit.clear();
	}
	const unreadIn = (threads) => threads.flatMap((thread) => thread.unread.map((item) => ({
		thread,
		item,
		message: thread.msgs.find((message) => message.id === item.message)
	})));
	const actionableUnread = () => {
		const live = new Set(unreadIn(readThreads().threads).map(({ item }) => keyOf(item)));
		return unreadIn(committedThreads.value).filter(({ item }) => live.has(keyOf(item)));
	};
	function firstUnread(thread = null) {
		const target = actionableUnread().filter((each) => thread === null || each.thread.key === thread).sort((a, b) => moved(a.message).seq - moved(b.message).seq)[0];
		return target ? openThread(target.item.message, { part: "message" }) : Promise.resolve();
	}
	const firstUnreadCommand = {
		id: "thread.unread.first",
		ready: savedReadingSettled,
		keys: ["u"],
		title: "first unread",
		touch: false,
		travels: true,
		when: () => actionableUnread().length > 0,
		run: () => void firstUnread()
	};
	function scan(sampleBand) {
		if (document.visibilityState !== "visible") return;
		const band = sampleBand ?? layoutWindow();
		if (!band || sampleBand?.visible === false) return;
		const candidates = new Map((threadsPresented ? actionableUnread() : []).map(({ item }) => [item.message, item]));
		const mayRead = threadsPresented && document.hasFocus() && sessionIsActive();
		const clips = /* @__PURE__ */ new Map();
		const completed = /* @__PURE__ */ new Map();
		const unseenWords = [];
		for (const [node, rendered] of renderedBodies) {
			const { body, id, version, feedback } = rendered;
			if (!node.isConnected || !body.isConnected) {
				sizes.unobserve(body);
				renderedBodies.delete(node);
				continue;
			}
			if (feedback) {
				const key = `${feedback.reply_id ?? `input:${feedback.input_id}`}:${feedback.presentation_kind}:${feedback.surface}`;
				if (!visibleReplies.has(key)) {
					if (wordsAreVisible(body, clips, band)) {
						visibleReplies.add(key);
						recordInteraction("reply_visible", feedback);
					} else unseenWords.push(body);
				}
			}
			const item = mayRead && candidates.get(id);
			const key = item && keyOf(item);
			if (!item || item.version !== version || completed.has(key) || refusedThisVisit.has(key)) continue;
			const visible = visibleInterval(body, clips, band);
			if (!visible) continue;
			let tracked = coverage.get(body);
			if (!tracked || tracked.key !== key || tracked.width !== visible.width || tracked.height !== visible.height || tracked.contentHeight !== visible.contentHeight) {
				tracked = {
					key,
					width: visible.width,
					height: visible.height,
					contentHeight: visible.contentHeight,
					intervals: []
				};
				coverage.set(body, tracked);
			}
			tracked.intervals = mergeIntervals([...tracked.intervals, visible.interval]);
			if (tracked.intervals.length === 1 && tracked.intervals[0][0] <= EPSILON && tracked.intervals[0][1] >= visible.height - EPSILON) completed.set(key, item);
		}
		if (unseenWords.length) passAfterFades(unseenWords);
		if (completed.size) {
			const items = [...completed.values()];
			const visit = visitGeneration;
			markRead(items).then((outcome) => {
				if (outcome === "refused" && visit === visitGeneration) for (const item of items) refusedThisVisit.add(keyOf(item));
			});
		}
		if (!threadsPresented) return;
		const waiting = passWaiters;
		passWaiters = [];
		for (const then of waiting) then();
	}
	const awaitedRuns = /* @__PURE__ */ new WeakSet();
	function passAfterFades(bodies) {
		for (const body of bodies) {
			const animations = body.getAnimations({ subtree: true });
			for (let at = renderedParent(body); at; at = renderedParent(at)) animations.push(...at.getAnimations());
			for (const { finished } of animations) {
				if (awaitedRuns.has(finished)) continue;
				awaitedRuns.add(finished);
				finished.then(scheduleScan, scheduleScan);
			}
		}
	}
	function afterPass(then) {
		passWaiters.push(then);
		scheduleScan();
	}
	let exposureGeneration = 0;
	function scheduleScan() {
		exposureGeneration++;
		if (scheduled) return;
		scheduled = true;
		nextRender(() => {
			scheduled = false;
			const asked = readSampleVisibility();
			if (!asked) {
				if (frameVisibility()?.visible !== false) scan();
				return;
			}
			const generation = exposureGeneration;
			asked.then((reading) => {
				if (generation === exposureGeneration) scan(reading);
			}, reportError);
		});
	}
	function mount() {
		frameWatches.push(watchRoom(scheduleScan));
		addEventListener("focus", scheduleScan);
		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState !== "visible") resetExposure();
			else scheduleScan();
		});
		addEventListener("blur", resetExposure);
		addEventListener("load", scheduleScan, true);
		document.addEventListener("lf-session-active", scheduleScan);
		frameWatches.push(onFrameVisibility((visibility) => {
			if (visibility.visible) scheduleScan();
			else resetExposure();
		}));
		addEventListener("pagehide", (event) => {
			exposureGeneration++;
			if (event.persisted) return;
			sizes.disconnect();
			for (const unwatch of frameWatches) unwatch();
			frameWatches.length = 0;
		});
	}
	function observeBody(body, reading) {
		if (!(body instanceof Element)) throw new TypeError("A message body must be an Element");
		if (!renderedBodies.has(body)) sizes.observe(body);
		const registration = {
			body,
			...reading
		};
		renderedBodies.set(body, registration);
		scheduleScan();
		return () => {
			if (renderedBodies.get(body) !== registration) return;
			sizes.unobserve(body);
			renderedBodies.delete(body);
		};
	}
	function observeMessage(body, message) {
		return observeBody(body, {
			id: message.id,
			version: message.version,
			feedback: message.author === "agent" ? {
				reply_id: message.id,
				attempt: message.attempt,
				presentation_kind: "message_words",
				reply_kind: message.provisional ? "stream" : message.progress ? "progress" : message.failure ? "failure" : "answer",
				surface: "margin"
			} : null
		});
	}
	function observeFeedback(body, feedback) {
		return observeBody(body, {
			id: null,
			version: null,
			feedback
		});
	}
	function present() {
		const generation = presentationGeneration;
		const threads = readThreads().threads;
		whenDocumentPresented().then(() => {
			if (generation !== presentationGeneration) return;
			committedThreads.value = threads;
			threadsPresented = true;
			const unread = unreadIn(threads);
			const current = new Set(unread.map(({ item }) => keyOf(item)));
			for (const key of refusedThisVisit) if (!current.has(key)) refusedThisVisit.delete(key);
			scheduleScan();
		}).catch(() => {
			if (generation === presentationGeneration) coverage = /* @__PURE__ */ new WeakMap();
		});
	}
	function begin() {
		presentationGeneration++;
		exposureGeneration++;
		threadsPresented = false;
	}
	function abort() {
		presentationGeneration++;
		threadsPresented = false;
		resetExposure();
	}
	return {
		mount,
		begin,
		abort,
		present,
		observeMessage,
		observeFeedback,
		firstUnread,
		afterPass,
		firstUnreadCommand
	};
}

//#endregion
//#region runtime/thread/box.js
const threadBox$1 = (el, hint, { createComment, onDraftChanged, wireInput }) => {
	if (inChrome(el) || quoted$1(el)) return null;
	const declaration = registry[el.localName]?.["x-thread-seat"];
	if (!declaration || !matchesWhen(el, declaration.when)) throw new TypeError(`<${el.localName}> placed a thread outside its x-thread-seat predicate`);
	const box = offer("div", "lf-thread-seat");
	box.dataset.lfRuntime = "";
	box.dataset.lfThreadSeat = el.id;
	const row = offer("div", "lf-say lf-comment-box");
	const ta = offer(TEXT_FIELD);
	ta.name = "comment";
	const ctx = "say:" + el.id;
	ta.value = loadDraft(ctx) ?? "";
	ta.setAttribute("aria-label", hint);
	row.append(ta);
	const sendComment = (text, owns, holds = false) => {
		const land = sendLanding(ta);
		const sent = sendMessage(ctx, owns, (attempt) => createComment({
			anchor: { section: el.id },
			text,
			attempt,
			...holds && { holds: el.id }
		}));
		if (sent) land();
		return sent;
	};
	const sync = wireInput(ta, {
		hint,
		sends: "send",
		altLabel: declaration.hold ?? null,
		save: (value) => saveDraft(ctx, value),
		send: (_text, raw, owns) => {
			sendComment(raw, owns);
		},
		altSend: declaration.hold ? (_text, raw, owns) => {
			if (sendComment(raw, owns, true)) notice("Replied — goal paused");
		} : null
	});
	sync();
	box.lfFirstMessage = row;
	whileConnected(box, () => watchDraft(ctx, (value) => {
		sync.load(value ?? "");
		onDraftChanged();
	}, {
		input: ta,
		resume: () => ({
			where: el,
			input: () => ta
		})
	}));
	mountFirstMessage(box, row);
	return box;
};

//#endregion
//#region runtime/semantic-news.js
const identity = (record) => record.attempt ?? record.id;
function semanticNewsReading(root) {
	const view = root.effective.view;
	if (!view) throw new Error("The shown page has no browser reading");
	const state = root.authoritative;
	return {
		obligations: view.obligations,
		thread: view.thread,
		workflows: state.workflows
	};
}
function unreadContent(threadView) {
	return threadView.threads.flatMap((thread) => thread.unread.map(({ message: id, version }) => ({
		thread: thread.id,
		message: thread.msgs.find((message) => message.id === id),
		version
	}))).filter(({ message }) => !message.failure).sort((a, b) => moved(a.message).seq - moved(b.message).seq);
}
function userObligations(items) {
	const held = /* @__PURE__ */ new Map();
	for (const item of items) {
		if (item.next_actor !== "user" || item.source.kind === "update") continue;
		const key = item.thread === null ? ["page", item.id] : [
			"thread",
			item.thread,
			item.id
		];
		held.set(JSON.stringify(key), {
			source: item.id,
			thread: item.thread,
			message: item.message
		});
	}
	return held;
}
function responseFailures(workflows) {
	const failures = /* @__PURE__ */ new Map();
	for (const workflow of workflows) {
		if (workflow.condition?.operation !== "response" || !["failed", "interrupted"].includes(workflow.condition.kind)) continue;
		const source = workflow.response;
		if (!source?.attempt && !source?.id) continue;
		const key = identity(source);
		const failure = {
			key,
			kind: workflow.condition.kind,
			input: workflow.input,
			thread: workflow.thread,
			seq: workflow.seq
		};
		failures.set(key, failure);
	}
	return failures;
}
function observeSemanticNews(prior, reading) {
	const content = unreadContent(reading.thread);
	const obligations = userObligations(reading.obligations);
	const failures = responseFailures(reading.workflows);
	const first = prior === null;
	const observed = {
		content: new Set(prior?.content),
		failures: new Set(prior?.failures),
		obligations: new Set(obligations.keys()),
		obligationEpisodes: new Map(prior?.obligationEpisodes)
	};
	const news = [];
	for (const { thread, message, version } of content) {
		if (!observed.content.has(version)) news.push({
			kind: "agent_content",
			key: `content:${version}`,
			thread,
			message,
			version
		});
		observed.content.add(version);
	}
	for (const failure of failures.values()) {
		if (!first && !observed.failures.has(failure.key)) news.push({
			...failure,
			condition: failure.kind,
			kind: "response_failure",
			key: `response:${failure.key}`
		});
		observed.failures.add(failure.key);
	}
	for (const [key, obligation] of obligations) {
		if (prior?.obligations.has(key)) continue;
		const episode = (observed.obligationEpisodes.get(key) ?? 0) + 1;
		observed.obligationEpisodes.set(key, episode);
		if (!first) news.push({
			kind: "user_obligation",
			key: `obligation:${key}:${episode}`,
			sourceKey: key,
			episode,
			...obligation
		});
	}
	return {
		observed,
		news
	};
}
function currentSemanticNews(news, reading, observed) {
	const versions = new Set(unreadContent(reading.thread).map(({ version }) => version));
	const obligations = userObligations(reading.obligations);
	const failures = responseFailures(reading.workflows);
	return news.flatMap((item) => {
		switch (item.kind) {
			case "agent_content": return versions.has(item.version) ? [item] : [];
			case "response_failure": {
				const current = failures.get(item.key.slice(9));
				return current ? [{
					...item,
					condition: current.kind
				}] : [];
			}
			case "user_obligation": return obligations.has(item.sourceKey) && item.episode === observed.obligationEpisodes.get(item.sourceKey) ? [item] : [];
			default: throw new Error(`Unknown semantic news kind ${item.kind}`);
		}
	});
}
function combineSemanticNews(older, newer) {
	return [...new Map([...older, ...newer].map((item) => [item.key, item])).values()];
}
const plural = (count, singular, pluralForm = `${singular}s`) => `${count} ${count === 1 ? singular : pluralForm}`;
const MESSAGE_WORDS = 60;
function semanticNewsNotice(news) {
	if (!news.length) return "";
	const byKind = (kind) => news.filter((item) => item.kind === kind);
	const content = byKind("agent_content");
	const failures = byKind("response_failure");
	let obligations = byKind("user_obligation");
	const clauses = [];
	if (content.length === 1) {
		const { message } = content[0];
		obligations = obligations.filter((item) => item.message !== message.id);
		const words = excerptWords(message.text, MESSAGE_WORDS);
		clauses.push(words ? message.edited ? `Edited: ${words}` : words : message.kind === "reply" ? "Replied" : "Commented");
	} else if (content.length) {
		const replies = content.filter(({ message }) => message.kind === "reply");
		const threads = new Set(content.map((item) => item.thread)).size;
		clauses.push(replies.length === content.length ? `${plural(content.length, "reply", "replies")} in ${plural(threads, "thread")}` : `${plural(content.length, "agent message")} in ${plural(threads, "thread")}`);
	}
	const failed = failures.filter((item) => item.condition === "failed").length;
	const interrupted = failures.filter((item) => item.condition === "interrupted").length;
	if (failed) clauses.push(failed === 1 ? "Couldn't answer" : `Couldn't answer ${failed}`);
	if (interrupted) clauses.push(interrupted === 1 ? "Interrupted mid-answer" : `Interrupted on ${interrupted}`);
	if (obligations.length) clauses.push(obligations.length === 1 ? "New on me" : `${obligations.length} new on me`);
	return clauses.join(" · ");
}

//#endregion
//#region runtime/state-application.js
function createStateApplication({ prepareActivation, acceptData, notifyDataSubscribers, accountPending }) {
	let observedSemanticNews = null;
	let presentedNewsReading = null;
	let stateApplying = false;
	let admission = Promise.resolve();
	async function runSerialized(operation) {
		const prior = admission;
		const { promise, resolve: release } = Promise.withResolvers();
		admission = promise;
		await prior;
		try {
			return await operation();
		} finally {
			release();
		}
	}
	async function receiveState(state) {
		if (!sameLayer(state.layer.generation)) return;
		const dataChanged = acceptData(state.data, state.taken);
		const notifyChangedData = () => dataChanged ? notifyDataSubscribers() : void 0;
		if (applicationState.overtaken(state)) {
			await notifyChangedData();
			return;
		}
		const threads = state.browser.views[state.active.revision].thread.threads;
		const preparations = [prepareActivation(state), threads.length ? loadMessageMarkdown() : null];
		for (const thread of threads) for (const message of thread.msgs) if (message.markup) preparations.push(prepareAuthoredMessage(message, thread.id));
		const [activation, , ...frozenDocuments] = await Promise.all(preparations);
		const bodies = new Map(threads.flatMap((thread) => thread.msgs.map((message) => [message.id, { text: messageText(message) }])));
		for (const frozen of frozenDocuments) bodies.set(frozen.message, {
			...frozen.body,
			text: [bodies.get(frozen.message).text, frozen.body.text].filter(Boolean).join("\n")
		});
		return runSerialized(async () => {
			const following = activation?.activates() ? activation.revision : null;
			if (!applicationState.canAdopt(state, following)) {
				await notifyChangedData();
				return;
			}
			const installed = following !== null ? await activation.install() : null;
			const prior = installed?.document ?? readApplication().document;
			let authored = prior.authored;
			let descriptors = prior.descriptors;
			for (const frozen of frozenDocuments) {
				for (const [id, baseline] of frozen.authored) {
					if (authored.has(id)) continue;
					if (authored === prior.authored) authored = new Map(authored);
					authored.set(id, baseline);
				}
				for (const [id, descriptor] of frozen.descriptors.descriptors) {
					if (descriptors.has(id)) continue;
					if (descriptors === prior.descriptors) descriptors = new Map(descriptors);
					descriptors.set(id, descriptor);
				}
			}
			const documentCapture = {
				...prior,
				authored,
				descriptors,
				messageBodies: bodies
			};
			for (const frozen of frozenDocuments) commitWidgetDescriptors(frozen.descriptors);
			if (!applicationState.adopt(state, documentCapture)) {
				await notifyChangedData();
				return;
			}
			observeServerNow(state.now);
			observeWorkingGrace(state.working_grace_ms);
			stateApplying = true;
			try {
				settleAcceptedDrafts();
				if (installed) await settlePageInterface();
				await whenDocumentPresented();
				if (installed) await installed.land();
				await notifyDataSubscribers();
				markStateApplied(state);
				accountPending(state.browser.receipts);
				presentedNewsReading = semanticNewsReading(readApplication());
				const reading = observeSemanticNews(observedSemanticNews, presentedNewsReading);
				observedSemanticNews = reading.observed;
				if (reading.news.length) announce(semanticNewsNotice(reading.news));
				const shown = reading.news.filter((item) => item.kind !== "agent_content");
				if (shown.length) {
					const format = (value) => semanticNewsNotice(currentSemanticNews(value, presentedNewsReading, observedSemanticNews));
					notice(format(shown), {
						background: true,
						announce: false,
						group: {
							key: "semantic-news",
							value: shown,
							combine: combineSemanticNews,
							format
						}
					});
				}
			} catch (error) {
				reportCarried(error, `State presentation failed`);
				throw error;
			} finally {
				stateApplying = false;
			}
		});
	}
	return {
		isApplying: () => stateApplying,
		receiveState,
		runSerialized
	};
}

//#endregion
//#region runtime/state-feed.js
async function readState(bound) {
	countTraffic("asked");
	try {
		if (offlineInteractive) return {
			state: offlineState(),
			fault: null
		};
		const signal = globalThis.AbortSignal.timeout(bound);
		const held = runtime.data;
		let res;
		try {
			res = await fetch(pageUrl("api/state"), {
				headers: layerHeaders(dataHeaders(held)),
				signal
			});
		} catch {
			return NOTHING;
		}
		if (!admitResponse(res)) return NOTHING;
		if (!res.ok) {
			if (res.status === 401 || NO_SERVER_BEHIND.has(res.status)) return NOTHING;
			return {
				state: null,
				fault: (await res.json().catch(() => null))?.error ?? `HTTP ${res.status}`
			};
		}
		let text;
		try {
			text = await res.text();
		} catch {
			return NOTHING;
		}
		return {
			state: completeData(JSON.parse(text), held),
			fault: null
		};
	} finally {
		countTraffic("heard");
	}
}
function buffer(bound) {
	return readState(bound).catch((error) => ({ error }));
}
function beginRead() {
	return buffer(FIRST_READ_TIMEOUT_MS);
}
function createStateFeed({ stateApplying, invalidateDom, receiveState, prepareActivation }) {
	let readAnswered = false;
	function failed(error) {
		readAnswered = false;
		reportCarried(error, `read failed`);
		applicationState.setReach("broken");
	}
	async function tick() {
		if (stateApplying()) return;
		await tickClock(reportCarried);
		if (stateApplying()) return;
		document.dispatchEvent(new Event("lf-tick"));
	}
	async function readNothing(fault = null) {
		readAnswered = false;
		if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
		if (fault !== null) applicationState.setReach("faulted", fault);
		else applicationState.setReach(runtime.keyRefused ? "refused" : "unreachable");
		await invalidateDom();
		await tick();
	}
	async function readAndApply(read = buffer(STATE_READ_TIMEOUT_MS)) {
		const answer = await read;
		if ("error" in answer) throw answer.error;
		const { state, fault } = answer;
		if (!state) {
			await readNothing(fault);
			return;
		}
		await receiveState(state);
		readAnswered = true;
	}
	async function heartbeat() {
		if (stateApplying()) return;
		try {
			if (runtime.statePhase === "ready" && runtime.state && !runtime.showsActive) {
				if ((await prepareActivation(runtime.state))?.activates()) await receiveState(runtime.state);
			}
			await tick();
		} catch (error) {
			readAnswered = false;
			reportCarried(error, `tick failed`);
		}
	}
	function startFeed(present, initialRead = beginRead()) {
		const readAndPresent = async () => {
			try {
				await readAndApply(initialRead);
			} catch (error) {
				failed(error);
				return;
			} finally {
				releaseSlot();
			}
			try {
				await present();
			} catch (error) {
				failed(error);
			}
		};
		let reading = true;
		let readQueued = false;
		let applyingReads = 0;
		const releaseSlot = () => {
			reading = false;
			if (!readQueued) return;
			readQueued = false;
			item();
		};
		const feedQuiet = () => !reading && !applyingReads && !stateApplying();
		const askOnce = async () => {
			const returned = readingReturn();
			try {
				const { state, fault } = await readState(STATE_READ_TIMEOUT_MS);
				if (state) {
					applyingReads += 1;
					receiveState(state).then(async () => {
						readAnswered = true;
						await present();
						if (applyingReads === 1 && !stateApplying()) completeReadingReturn(returned);
					}, async (error) => {
						failed(error);
						await present();
					}).catch((error) => {
						reportCarried(error, `presentation failed`);
					}).finally(() => {
						applyingReads -= 1;
					});
				} else readNothing(fault).then(async () => {
					await present();
					if (!applyingReads && !stateApplying()) completeReadingReturn(returned);
				}).catch(failed);
			} catch (error) {
				failed(error);
			}
		};
		const item = () => {
			if (reading) {
				readQueued = true;
				return;
			}
			reading = true;
			askOnce().finally(releaseSlot);
		};
		const pageIsVisible = () => document.visibilityState !== "hidden";
		let feedStarted = false;
		let listening = null;
		let freshness = null;
		let nextLook = null;
		const stopListening = () => {
			clearTimeout(nextLook);
			nextLook = null;
			listening?.abort();
			listening = null;
			freshness = null;
		};
		const listen = () => {
			if (!feedStarted || !pageIsVisible() || !sessionIsActive() || listening) return;
			const interval = new AbortController();
			listening = interval;
			const look = async () => {
				let delay = LOOK_MS;
				const returned = readingReturn();
				try {
					const response = await fetch(pageUrl("api/news"), {
						headers: layerHeaders(),
						signal: globalThis.AbortSignal.any([interval.signal, globalThis.AbortSignal.timeout(STATE_READ_TIMEOUT_MS)])
					});
					if (listening !== interval) return;
					if (!admitResponse(response)) throw new Error("news belongs to another delivery");
					if (!response.ok) throw new Error(`news returned HTTP ${response.status}`);
					const observed = await response.text();
					if (listening === interval) {
						if (observed !== freshness && observed !== runtime.reading) item();
						else if (returned !== null && observed === runtime.reading && feedQuiet()) {
							await invalidateDom();
							await present();
							if (feedQuiet()) completeReadingReturn(returned);
						}
						freshness = observed;
					}
				} catch {
					if (listening !== interval) return;
					item();
					delay = TICK_MS;
				}
				if (listening === interval) nextLook = setTimeout(look, delay);
			};
			look();
		};
		document.addEventListener("visibilitychange", () => {
			if (!pageIsVisible()) {
				stopListening();
				return;
			}
			const returned = readingReturn();
			invalidateDom().then(present).then(() => {
				if (offlineInteractive || !sessionIsActive()) completeReadingReturn(returned);
			}).catch((error) => reportCarried(error, `return presentation failed`));
			listen();
		});
		document.addEventListener("lf-session-active", listen);
		const initialPresentation = readAndPresent();
		if (offlineInteractive) return;
		initialPresentation.finally(() => {
			feedStarted = true;
			setInterval(() => {
				if (!pageIsVisible()) return;
				if (readAnswered && sessionIsActive() && (activityTransitionDue(runtime.state) || freshness !== null && freshness !== runtime.reading)) item();
				else if (readAnswered) heartbeat();
				else item();
				present();
			}, TICK_MS);
			listen();
		});
	}
	return {
		readAndApply,
		startFeed
	};
}
const TICK_MS = 2e3;
const LOOK_MS = 250;
const FIRST_READ_TIMEOUT_MS = 12e4;
const STATE_READ_TIMEOUT_MS = 1e4;
const NOTHING = Object.freeze({
	state: null,
	fault: null
});
const NO_SERVER_BEHIND = /* @__PURE__ */ new Set([
	502,
	503,
	504
]);

//#endregion
//#region runtime/application.js
const commandDispatch = createCommandDispatch();
let application = null;
const app = () => {
	if (!application) throw new Error("Leaf application has not been mounted");
	return application;
};
function mountApplication(dependencies) {
	if (application) throw new Error("Leaf application mounted twice");
	setPresentationFailureReporter(reportCarried);
	const { ledger } = commandDispatch;
	watchPendingTraffic(applicationState.select((root) => root.effective.sending));
	const hasPending = () => ledger.snapshot().length > 0;
	const engagement = dependencies.createEngagement({
		hasPending,
		fabAnchorAt: dependencies.activeActionAnchor,
		targetPickerOpen: dependencies.targetPickerOpen
	});
	let threadPresenter;
	let stateApplication;
	let queuedInvalidation = false;
	const stateApplying = () => stateApplication?.isApplying() ?? false;
	const openPageThread = (...args) => threadDestinations.openPageThread(...args);
	const releasePending = async () => {
		const candidates = ledger.releasable();
		if (!candidates.length) return false;
		const attempts = new Set(candidates.map((entry) => entry.event.attempt));
		const stillCurrent = () => ledger.releasable().some((entry) => attempts.has(entry.event.attempt));
		await Promise.all([whenWidgetsPresented([...new Set(candidates.filter((entry) => entry.event.kind === "action").map((entry) => entry.event.widget))]), whenApplicationRegionsPresented([
			"projection:chrome",
			"thread",
			"obligations"
		], stillCurrent)]);
		const released = ledger.releasable().filter((entry) => attempts.has(entry.event.attempt));
		if (!released.length) return false;
		ledger.release(released);
		return true;
	};
	const releasePendingSafely = (context) => {
		releasePending().catch((error) => reportCarried(error, context));
	};
	const invalidateDom = () => {
		if (stateApplying()) {
			queuedInvalidation = true;
			return Promise.resolve();
		}
		return presentDocument();
	};
	createProjectionPresentation();
	createDataProjection({ invalidateDom });
	let delivery;
	const presentThread = () => threadPresenter.present();
	const refreshThread = () => presentThread().catch(() => void 0);
	function afterEnqueue(entry) {
		try {
			if (isMessageEvent(entry.event)) announce("Message added");
			if (entry.event.kind === "edit") announce("Message edited");
		} catch (error) {
			reportPageError(error, "optimistic presentation");
		} finally {
			delivery.drain();
		}
	}
	commandDispatch.mount({
		afterEnqueue,
		named: (entry, says) => {
			undo.retainGesture(entry.event.attempt, { says });
			entry.answer.then((admitted) => {
				if (admitted) announce(says);
			});
		},
		withdraw: (candidate) => undo.withdraw(candidate),
		onCollision: (attempt) => raiseError(`Couldn't send — attempt ${attempt} is already in use`)
	});
	const { post } = commandDispatch;
	const undo = createUndo({
		post,
		stateApplying,
		unaccountedGesture: engagement.unaccountedGesture,
		openThread: openPageThread,
		threadPlace: (id) => dependencies.anchorTravel.threadDestination(id)
	});
	const markRead = async (messages) => {
		applicationState.markRead(messages);
		try {
			return await deliverBookkeeping({
				kind: "read",
				messages
			}, receiveState);
		} finally {
			applicationState.settleMarkRead(messages);
		}
	};
	const read = createReadTracking({
		markRead,
		openThread: openPageThread
	});
	const threadActions = createThreadActions({
		post,
		withdraw: undo.withdraw,
		sendReaction: dependencies.sendReaction,
		currentRevision: () => runtime.currentRevision,
		open: openPageThread
	});
	const queueActions = createQueueActions({
		post,
		arrive: (item) => dependencies.arriveAtQueueItem(item)
	});
	const replyView = {
		actions: threadActions,
		wireInput: dependencies.wireInput,
		landSent: dependencies.landSent,
		landInThread: dependencies.landInThread
	};
	const settlementView = {
		pendingEntries: ledger.snapshot,
		actions: threadActions,
		landedAway: undo.landedAway,
		returnToThread: undo.returnToThread
	};
	const inlineView = {
		reply: replyView,
		settlement: settlementView,
		reaction: {
			registerSurface: dependencies.registerReactSurface,
			actions: threadActions
		},
		todos: { done: (id) => queueActions.done(queueItemKey({
			kind: "todo",
			id
		})) },
		read,
		openThread: openPageThread,
		landInThread: dependencies.landInThread
	};
	const surfaceView = {
		...inlineView,
		composition: dependencies.compositionSurface
	};
	const annotations = createAnnotationInventory({
		readObligations,
		placedAt: dependencies.anchorPlacement.placedAt,
		openThread: openPageThread,
		goToObligation: dependencies.annotationCommands.goToObligation,
		scrollToElement: dependencies.anchorTravel.scrollToElement
	});
	const inlineContributions = createInlineContributions(annotations);
	const onPaper = matchMedia("print");
	function refreshAnnotationInventory() {
		if (onPaper.matches) return annotations.read();
		presentingContributions();
		inlineContributions.present();
		const entries = annotations.collect();
		dependencies.annotationCommands.renderPageMapDialog(entries);
		return entries;
	}
	let annotationsDrawn = false;
	const renderAnnotations = () => {
		annotationsDrawn = true;
		if (!onPaper.matches) {
			const entries = refreshAnnotationInventory();
			overlay?.paint(entries);
		}
	};
	renderAnnotations.refresh = () => {
		if (annotationsDrawn) renderAnnotations();
	};
	const annotationInputs = readPart(annotationSelection);
	let marginPresentation = null;
	const mountAnnotations = () => {
		const presentation = applicationPresenter({
			region: "annotations",
			after: PRESENTATION_DOM.obligations,
			reading: () => annotationInputs(),
			paint: renderAnnotations
		});
		marginPresentation = presentation;
		presentation.present();
		onPaper.addEventListener("change", () => {
			if (!onPaper.matches) presentation.present();
		});
		watchContributions(({ immediate }) => {
			renderAnnotations();
			if (immediate) overlay?.flushLayout();
		});
	};
	const overlay = dependencies.createMarginProjection?.({
		inventory: annotations,
		refreshInventory: refreshAnnotationInventory,
		renderAnnotations,
		openPageThread,
		designModeActive: dependencies.annotationCommands.designModeActive,
		pointerModeActive: dependencies.annotationCommands.pointerModeActive,
		leavePageMap: dependencies.annotationCommands.leavePageMap,
		openPageMap: dependencies.annotationCommands.openPageMap,
		pageMapDialogContains: dependencies.annotationCommands.pageMapDialogContains,
		scrollThreadIntoView: dependencies.annotationCommands.scrollThreadIntoView,
		renderMarginThread: (host, thread, controls) => renderMarginThread(host, thread, inlineView, controls),
		placedAt: dependencies.anchorPlacement.placedAt,
		marksFor: (id) => dependencies.anchorPaint?.marksFor(id) ?? [],
		scrollToElement: dependencies.anchorTravel.scrollToElement,
		openInPanel: dependencies.annotationCommands.openInPanel
	});
	const threadDestinations = createThreadDestinations({
		threadIdsAt: annotations.threadIdsAt,
		placedAt: dependencies.anchorPlacement.placedAt,
		scrollToThread: dependencies.anchorTravel.scrollToThread,
		arrive: dependencies.anchorTravel.arrive,
		prepareNavigationStep: dependencies.anchorTravel.prepareNavigationStep,
		preview: overlay?.threadPreview
	});
	threadPresenter = createThreadPresentation({
		available: dependencies.threadAvailable ?? true,
		inlineView,
		surfaceView,
		anchorPlacement: dependencies.anchorPlacement,
		anchorPaint: dependencies.anchorPaint,
		anchorControls: dependencies.anchorControls,
		drawingPaint: dependencies.drawingPaint,
		pageGeometry: dependencies.pageGeometry,
		readDraft: dependencies.readThreadDraft,
		activeActionAnchor: dependencies.activeActionAnchor,
		renderSurfaces,
		openThread: (id, options) => threadDestinations.openPageThread(id, {
			...options,
			travel: false
		}),
		continueThread: (id, intent) => threadDestinations.openPageThread(id, {
			part: "reply",
			focus: false,
			travel: false,
			intent
		}),
		returnToPage: threadDestinations.returnToPage,
		threadAt: (node) => overlay?.entryThread(node) ?? null,
		marginCommitted: () => marginPresentation?.committed() ?? Promise.resolve(),
		read
	});
	const accountPending = (receipts) => {
		ledger.present(receipts);
		releasePendingSafely("receipt presentation");
	};
	stateApplication = createStateApplication({
		prepareActivation: dependencies.state.prepareActivation,
		acceptData: dependencies.state.acceptData,
		notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
		accountPending
	});
	const flushQueuedInvalidation = () => {
		if (!queuedInvalidation || stateApplying()) return Promise.resolve();
		queuedInvalidation = false;
		return invalidateDom();
	};
	const receiveState = (state) => stateApplication.receiveState(state).finally(() => flushQueuedInvalidation().catch(() => void 0));
	delivery = createDelivery({
		ledger,
		applyAcceptedState: receiveState,
		refusedWords: keepRefusedWords,
		settleRejected: async (entry, state) => {
			if (state) await receiveState(state).catch((error) => reportCarried(error, "state in refused event response"));
			let dependents = [];
			await stateApplication.runSerialized(async () => {
				dependents = ledger.refuse(entry);
				const prepared = invalidateDom();
				releasePendingSafely("rejected event presentation");
				await prepared;
			});
			return dependents;
		},
		settlementChanged: (entry, accepted) => {
			if (accepted) {
				releasePendingSafely("accepted event reconciliation");
				if (!applicationState.entry(entry.event.attempt)) invalidateDom();
			}
		}
	});
	const feed = createStateFeed({
		prepareActivation: dependencies.state.prepareActivation,
		stateApplying,
		invalidateDom,
		receiveState
	});
	const threadBox = (owner, hint) => threadBox$1(owner, hint, {
		createComment: (command) => threadActions.create(command)?.delivery ?? null,
		onDraftChanged: invalidateDom,
		wireInput: dependencies.wireInput
	});
	const threadSurfaceCommands = {
		invalidate: invalidateDom,
		composition: dependencies.compositionSurface,
		reveal: openPageThread
	};
	const requirePageAnnotations = () => {
		if (annotationMode !== "page") throw new Error("Page annotation presentation requires data-annotations=page");
	};
	let annotationRegistration = null;
	const consumeAnnotations = (owner, render) => {
		requirePageAnnotations();
		if (annotationRegistration) throw new Error("The document already has a page annotation view");
		const registration = Symbol("page annotation view");
		annotationRegistration = registration;
		const retire = () => {
			if (annotationRegistration === registration) annotationRegistration = null;
		};
		try {
			return createAnnotationView(owner, render, annotations, invalidateDom, retire);
		} catch (error) {
			retire();
			throw error;
		}
	};
	const watchThreadSurfaces$1 = () => watchThreadSurfaces(threadSurfaceCommands);
	const placePageThreads = (owner, render) => {
		requirePageAnnotations();
		return placePageThreads$1(owner, render, threadSurfaceCommands);
	};
	const attachPresentation = (owner, { render, reveal, answersAtOnce = false }, onFailure = void 0) => {
		const reader = createPrimaryReader(owner, render, inlineView, () => threadPresenter.present(), {
			answersAtOnce,
			onFailure
		});
		const detachDestination = threadDestinations.register(owner, reveal, reader);
		let detachPresentation;
		try {
			detachPresentation = threadPresenter.registerPrimary(reader);
		} catch (error) {
			detachDestination();
			reader.unregister();
			throw error;
		}
		return {
			reader,
			detach() {
				detachDestination();
				detachPresentation();
			}
		};
	};
	let yielding = null;
	let authored = null;
	const restoreYielding = () => {
		if (yielding && !yielding.attached) yielding.attached = attachPresentation(yielding.owner, yielding.spec);
	};
	const takePlace = (entry) => {
		const displaced = yielding?.attached;
		const handOff = displaced ? yielding.spec.yielded() : null;
		if (displaced) {
			displaced.detach();
			yielding.attached = null;
		}
		try {
			entry.attached = attachPresentation(entry.owner, entry.spec, () => nextRender(() => fallBack(entry)));
		} catch (error) {
			if (displaced) restoreYielding();
			throw error;
		}
		authored = entry;
		if (handOff) queueMicrotask(() => {
			if (authored === entry) handOff();
		});
	};
	const fallBack = (entry) => {
		if (authored !== entry || !entry.attached?.reader.failed) return;
		entry.attached.detach();
		entry.attached = null;
		restoreYielding();
	};
	const presentThreads = (owner, spec, yields) => {
		const entry = {
			owner,
			spec,
			attached: null
		};
		if (yields) {
			if (yielding) throw new Error("The page already has a yielding Thread presentation");
			yielding = entry;
			if (!authored) entry.attached = attachPresentation(owner, spec);
		} else takePlace(entry);
		let active = true;
		return Object.freeze({
			get primary() {
				return Boolean(entry.attached);
			},
			update: ({ release = false } = {}) => {
				if (active && authored === entry && !entry.attached) takePlace(entry);
				if (release) entry.attached?.reader.release();
				return threadPresenter.present();
			},
			unregister() {
				if (!active) return;
				active = false;
				entry.attached?.detach();
				entry.attached = null;
				if (yielding === entry) yielding = null;
				if (authored === entry) {
					authored = null;
					restoreYielding();
				}
			}
		});
	};
	application = {
		withdraw: undo.withdraw,
		midComposition: engagement.midComposition,
		threadBox,
		hasPending,
		invalidateDom,
		landInThread: dependencies.landInThread,
		annotations,
		renderAnnotations,
		mountAnnotations,
		overlay,
		threadDestinations,
		read,
		mountRead: read.mount,
		registerThreadPresentation: (owner, spec) => presentThreads(owner, spec, false),
		registerChromeThreadPresentation: (owner, spec) => presentThreads(owner, spec, true),
		navigateToDatum: dependencies.anchorTravel.navigateToDatum,
		post,
		readAndApply: feed.readAndApply,
		refreshThread,
		presentThread,
		watchThreadSurfaces: watchThreadSurfaces$1,
		placePageThreads,
		consumeAnnotations,
		threadActions,
		queueActions,
		settlement: settlementView,
		openObligation(id) {
			const item = readObligations().all.find((item) => item.id === id);
			if (!item) return Promise.resolve(false);
			if (item.source.kind === "update" || item.source.kind === "todo") return queueActions.open(JSON.stringify([item.source.kind, item.id]));
			if (item.thread !== null && answeredInWords(item)) {
				showHeld(item.thread);
				return threadDestinations.openPageThread(item.message, { part: "message" });
			}
			return dependencies.annotationCommands.goToObligation(item, readObligations().all);
		},
		nextObligation: (options) => dependencies.nextObligationWithin(options),
		startFeed: feed.startFeed,
		wireInput: dependencies.wireInput
	};
	return application;
}
const threadBox = (...args) => app().threadBox(...args);
const dispatchWidget = commandDispatch.dispatchWidget;
const invalidateDom = (...args) => app().invalidateDom(...args);
const landInThread = (...args) => app().landInThread(...args);
const navigateToDatum = (...args) => app().navigateToDatum(...args);
const post = commandDispatch.post;
const placePageThreads = (...args) => app().placePageThreads(...args);
const consumeAnnotations = (...args) => app().consumeAnnotations(...args);
const registerThreadPresentation = (...args) => app().registerThreadPresentation(...args);
const threadActions = Object.freeze({
	open: (...args) => app().threadActions.open(...args),
	create: (...args) => app().threadActions.create(...args),
	reply: (...args) => app().threadActions.reply(...args),
	resolve: (...args) => app().threadActions.resolve(...args),
	reopen: (...args) => app().threadActions.reopen(...args),
	setReaction: (...args) => app().threadActions.setReaction(...args)
});
const obligationActions = Object.freeze({
	open: (...args) => app().openObligation(...args),
	next: (...args) => app().nextObligation(...args)
});
const queueActions = Object.freeze({
	open: (...args) => app().queueActions.open(...args),
	done: (...args) => app().queueActions.done(...args)
});
const wireInput = (...args) => app().wireInput(...args);

//#endregion
//#region runtime/thread/landing.js
const threadReturns = /* @__PURE__ */ new WeakMap();
function threadInput(node) {
	const held = node && closestAcross(node, ".lf-page-thread, [data-lf-thread-view], .lf-thread-seat");
	return threadReplyInput(held);
}
const heldThreadOrSeat = () => focused() && closestAcross(focused(), ".lf-page-thread, [data-lf-thread-view], .lf-thread-seat");
const currentLocationThread = () => {
	const held = heldThreadOrSeat();
	const box = threadReplyInput(held);
	return box ? {
		held: wholeThread(held),
		box
	} : null;
};
const backFromThread = (box) => threadReturns.get(box) ?? null;
function backFromBox() {
	const held = heldThreadOrSeat();
	if (held?.matches(".lf-page-thread, [data-lf-thread-view]")) return {
		target: wholeThread(held),
		line: "back to thread"
	};
	const route = backFromThread(focused());
	return route?.target?.isConnected ? route : null;
}
const boxHandsBack = () => Boolean(backFromBox());
const inBox = () => takesLetters(focused()) || replyDraftContext(focused()) !== null;
const leavesBox = () => inBox() && boxHandsBack();
pageScope("text entry", {
	title: "In a text box",
	root: focused,
	at: inBox,
	claims: (binding) => takesLetters(focused()) && TEXT_ENTRY(binding),
	rows: [{
		id: "text.leave",
		touch: false,
		keys: ["Escape"],
		description: "Keeps what is typed",
		title: () => backFromBox()?.line ?? "back",
		when: leavesBox,
		run: () => {
			const back = backFromBox();
			dismissReplyAt(focused());
			deepFocus()?.blur();
			const target = back?.target;
			if (!target) return;
			if (!target.matches?.(".lf-page-thread, [data-lf-thread-view]")) {
				focusDestination(target, "return");
				scrollIntoView(target, { block: "nearest" });
				return;
			}
			returnToThread(target);
		}
	}]
});
function returnToThread(thread) {
	const shown = alreadyShown(thread);
	if (!fitsWhole(thread) && shown) {
		focusThread(thread, "return");
		return;
	}
	focusThread(thread, "move");
	const box = threadReplyInput(thread);
	if (!shown && !(box && seenRect(box, /* @__PURE__ */ new Map()))) scrollIntoView(thread, { block: "nearest" });
}
const cardThread = () => focusedThreadTarget();
const resolutionControl = (thread) => thread ? threadPart(thread, "settlement") : null;
const messageAt = (node) => (node instanceof Element ? node : node?.parentElement)?.closest(".lf-msg") ?? null;
function messageCopy(thread) {
	if (!thread) return null;
	const caret = getSelection().anchorNode;
	return (messageAt(focused()) ?? (thread.contains(caret) ? messageAt(caret) : null) ?? [...thread.querySelectorAll(".lf-msg")].at(-1))?.querySelector(":scope > .lf-msg-head > .lf-msg-controls > .lf-msg-copy") ?? null;
}
function prepareLanding({ held = null, box, route = null }) {
	if (!box) return false;
	held ??= closestAcross(box, SAYS_IN);
	if (route && held && !held.hasAttribute("tabindex")) {
		threadReturns.set(box, route);
		whenLeft(box, () => threadReturns.delete(box));
	}
	return {
		held,
		box
	};
}
function createThreadLanding() {
	const landIn = (destination) => {
		const prepared = prepareLanding(destination);
		if (!prepared) return false;
		const { box } = prepared;
		bringBackSurfaceOf(box);
		focusDestination(box, "move");
		if (!alreadyShown(box)) scrollIntoView(box, {
			block: "nearest",
			behavior: "instant"
		});
		return true;
	};
	const landInThread = (box, route = null) => landIn({
		box,
		route
	});
	return {
		landIn,
		landInThread,
		landSent: returnToThread
	};
}
function declareThreadKeys(landIn, threadHere) {
	pageScope("thread", {
		title: "In a thread",
		root: focused,
		when: () => threadList().length > 0,
		at: () => Boolean(threadHere()),
		rows: [
			{
				id: "thread.primary",
				touch: false,
				keys: ["Enter"],
				title: () => !threadInput(cardThread()) && resolutionControl(cardThread())?.matches(".lf-reopen") ? "reopen" : "reply",
				when: () => Boolean(threadInput(cardThread())) || resolutionControl(cardThread())?.matches(".lf-reopen:not(:disabled, [aria-disabled=\"true\"])"),
				run: () => {
					const thread = cardThread();
					const box = threadInput(thread);
					if (box) landIn({
						held: thread,
						box
					});
					else resolutionControl(thread).click();
				}
			},
			{
				id: "thread.resolution.toggle",
				touch: false,
				keys: ["r"],
				title: () => resolutionControl(threadHere())?.matches(".lf-reopen") ? "reopen" : "resolve",
				when: () => resolutionControl(threadHere())?.matches(":not(:disabled, [aria-disabled=\"true\"])"),
				run: () => resolutionControl(threadHere()).click()
			},
			{
				id: "message.copy",
				touch: false,
				keys: ["Mod+c"],
				title: "copy message as Markdown",
				when: () => Boolean(messageCopy(threadHere())) && getSelection().isCollapsed,
				run: () => messageCopy(threadHere()).shadowRoot.querySelector("button").click()
			}
		]
	});
}

//#endregion
//#region runtime/widget-controller.js
const controllers = /* @__PURE__ */ new WeakMap();
const ancestorRefreshes = /* @__PURE__ */ new Set();
let ancestorRefreshQueued = false;
const selfDrawn = /* @__PURE__ */ new WeakMap();
const drawsItself = (owner, drawing) => selfDrawn.set(owner, drawing);
function widgetMounted(owner, descriptor, parentChanged) {
	if (parentChanged && applicationState.read().document.authored.has(descriptor.id)) refreshAncestors(owner);
	invalidateDom();
}
function refreshAncestors(owner) {
	for (let ancestor = owner.parentElement; ancestor; ancestor = ancestor.parentElement) {
		const drawing = selfDrawn.get(ancestor);
		if (drawing) ancestorRefreshes.add(drawing);
	}
	if (!ancestorRefreshes.size || ancestorRefreshQueued) return;
	ancestorRefreshQueued = true;
	queueMicrotask(() => {
		ancestorRefreshQueued = false;
		const pending = [...ancestorRefreshes];
		ancestorRefreshes.clear();
		for (const drawing of pending) drawing.refresh();
	});
}
const immutable = (value) => {
	if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
		for (const child of Object.values(value)) immutable(child);
		Object.freeze(value);
	}
	return value;
};
const unavailable = (reading) => immutable({
	...structuredClone(reading),
	actions: Object.fromEntries(Object.entries(reading.actions).map(([verb, entry]) => [verb, {
		...entry,
		available: false,
		undo: []
	}]))
});
function createWidgetController(owner) {
	const descriptor = widgetDescriptor(owner);
	if (!descriptor) throw new Error(`leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`);
	const selected = applicationState.selectWidget(descriptor);
	let deferred = false;
	let preparationHandle = null;
	const pendingPreparations = /* @__PURE__ */ new Map();
	let preparation = null;
	let preparationBatch = null;
	const read = () => descriptorStillMatches(owner, descriptor) ? selected.read() : unavailable(selected.read());
	const prepared = () => {
		if (!preparationHandle && owner.isConnected) preparationHandle = attachWidgetPresentation(descriptor.id, "preparation");
		return preparationHandle;
	};
	const holdPreparation = (promise) => {
		if (pendingPreparations.has(promise)) {
			if (owner.isConnected && !pendingPreparations.get(promise)) pendingPreparations.set(promise, holdRendering());
			return;
		}
		pendingPreparations.set(promise, owner.isConnected ? holdRendering() : null);
		const settled = () => {
			pendingPreparations.get(promise)?.(owner.isConnected ? "settle" : "cancel");
			pendingPreparations.delete(promise);
		};
		Promise.resolve(promise).then(settled, settled);
	};
	const presentPreparation = (handle, { completion }) => handle.present((reason) => failSoftUnreported(owner, reason)).resolve(completion);
	const connect = () => d(() => {
		if (!owner.isConnected) return;
		for (const promise of pendingPreparations.keys()) holdPreparation(promise);
		if (preparation && !preparationHandle) {
			const handle = prepared();
			if (handle) presentPreparation(handle, preparation);
		}
	});
	const disconnect = () => {
		preparationHandle?.disconnect();
		preparationHandle = null;
		for (const [promise, release] of pendingPreparations) {
			release?.("cancel");
			pendingPreparations.set(promise, null);
		}
	};
	watchOwner(owner, {
		connect,
		disconnect
	});
	return Object.freeze({
		read,
		dispatch(command) {
			if (!descriptorStillMatches(owner, descriptor)) return null;
			const delivery = dispatchWidget(descriptor, command);
			if (!delivery) return null;
			return immutable({
				reading: read(),
				delivery
			});
		},
		defer() {
			const drawing = selfDrawn.get(owner);
			if (!drawing) throw new Error(`<${owner.localName}> defers only a LeafElement's drawing`);
			if (deferred) throw new Error("Widget presentation is already deferred");
			deferred = true;
			const release = drawing.hold();
			let released = false;
			return () => {
				if (released) return read();
				released = true;
				deferred = false;
				release();
				invalidateDom();
				return read();
			};
		},
		present(promise) {
			const value = read();
			if (!preparationBatch || preparationBatch.value !== value) preparationBatch = {
				value,
				promises: []
			};
			preparationBatch.promises.push(promise);
			const batch = preparationBatch;
			const completion = Promise.all(batch.promises);
			batch.completion = completion;
			preparation = { completion };
			holdPreparation(promise);
			const handle = prepared();
			if (handle) presentPreparation(handle, preparation);
			const clear = () => {
				if (preparationBatch?.completion === completion) preparationBatch = null;
			};
			completion.then(clear, clear);
			return promise;
		}
	});
}
function widgetController(owner) {
	let controller = controllers.get(owner);
	if (!controller) {
		let implementation = null;
		const resolve = () => implementation ??= createWidgetController(owner);
		controller = Object.freeze(Object.fromEntries([
			"read",
			"dispatch",
			"defer",
			"present"
		].map((method) => [method, (...args) => resolve()[method](...args)])));
		controllers.set(owner, controller);
	}
	return controller;
}
document.addEventListener(PENDING_TASK, (event) => {
	const owner = event.composedPath().find((node) => node instanceof Element && widgetDescriptor(node));
	if (owner) widgetController(owner).present(event.complete);
});

//#endregion
//#region runtime/leaf-element.js
let regions = 0;
var UpdateBoundary = class extends LitElement {
	signalUpdateFailed(error) {
		throw error;
	}
	performUpdate() {
		try {
			super.performUpdate();
		} catch (error) {
			this.signalUpdateFailed(error);
		}
	}
};
var LeafElement = class extends q(UpdateBoundary) {
	#signalError = null;
	#stopReadiness = null;
	signalUpdateFailed(error) {
		this.#signalError = { error };
	}
	requestUpdate(...args) {
		const wasPending = this.isUpdatePending;
		const result = super.requestUpdate(...args);
		if (this.hasUpdated && this.isUpdatePending && (!wasPending || !this.#updating)) d(() => {
			if (this.#connected && this.#region && !this.#ticket) this.#ticket = this.#claim();
		});
		return result;
	}
	whenReady(read) {
		if (d(read)) return true;
		if (!this.#stopReadiness) this.#stopReadiness = watchPresentation(() => {
			if (!d(read)) return;
			this.#stopReadiness?.();
			this.#stopReadiness = null;
			super.requestUpdate();
		});
		return false;
	}
	#descriptor = null;
	#controller = null;
	#verbs = [];
	#region = null;
	#regionName = null;
	#connected = false;
	#connectedParent = null;
	#ticket = null;
	#held = false;
	#box = null;
	#broken = false;
	#drawing = null;
	#updating = false;
	#leaveData = null;
	#scheduled = null;
	#inputs = [];
	#sent = /* @__PURE__ */ new Map();
	createRenderRoot() {
		return this;
	}
	scheduleUpdate() {
		return this.#scheduled ?? this.#queueUpdate();
	}
	#committed() {
		return super.getUpdateComplete();
	}
	#queueUpdate() {
		if (!this.#descriptor) return super.scheduleUpdate();
		const scheduled = queueWidgetUpdate(this.#descriptor.id, () => {
			if (this.#scheduled !== scheduled) return;
			this.#scheduled = null;
			return super.scheduleUpdate();
		}, () => this.#committed());
		this.#scheduled = scheduled;
		return scheduled;
	}
	connectedCallback() {
		if (once(this)) this.#setup();
		super.connectedCallback();
	}
	#setup() {
		this.#descriptor = widgetDescriptor(this);
		if (this.#descriptor) {
			this.#controller = widgetController(this);
			drawsItself(this, {
				hold: () => this.#hold(),
				refresh: () => this.#refresh()
			});
			this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
		}
		this.#regionName = this.#descriptor ? null : `element:${this.localName}#${this.id}:${++regions}`;
		this.#inputs = Object.entries(registry[this.localName]?.["x-data"] ?? {}).flatMap(([input, declaration]) => declaration.property ? [{
			input,
			property: declaration.property,
			bound: bindsInput(this, declaration),
			read: null
		}] : []);
		if (this.#inputs.length) this.addEventListener("drawn", (event) => {
			if (event.target === this) this.#drawn(event.detail);
		});
		placesFailure(this, (box) => {
			const root = this.renderRoot ?? this;
			if (root === this && this.shadowRoot) return false;
			if (this.#box?.parentNode === root && this.#box.textContent === box.textContent) return true;
			this.#box?.remove();
			this.#box = box;
			root.append(box);
			return true;
		});
		try {
			this.setup();
		} catch (error) {
			this.#broken = true;
			failSoft(this, error);
		}
		watchOwner(this, {
			connect: () => d(() => this.#connect()),
			disconnect: () => this.#disconnect()
		});
	}
	setup() {}
	get reading() {
		return this.#controller?.read() ?? null;
	}
	get state() {
		return this.reading.state;
	}
	get controller() {
		return this.#controller;
	}
	#deliverInputs() {
		for (const entry of this.#inputs) {
			if (!entry.bound) continue;
			entry.read ??= dataReader(this, entry.input, () => this.#stage());
			const snapshot = entry.read();
			const sent = this.#sent.get(entry.property);
			if (sent && sent.snapshot === snapshot) continue;
			const value = snapshot ? snapshot.value : null;
			const primitives = sent?.primitives ?? /* @__PURE__ */ new Map();
			if (value !== null && typeof value !== "object") {
				primitives.delete(value);
				primitives.set(value, snapshot);
			}
			this.#sent.set(entry.property, {
				snapshot,
				primitives
			});
			this[entry.property] = value;
		}
	}
	#drawn(detail) {
		try {
			const named = this.#inputs.filter(({ property }) => detail && Object.hasOwn(detail, property));
			if (named.length !== 1 || Object.keys(detail).length !== 1) throw new Error(`<${this.localName}> drawn must name one bound property (${this.#inputs.map(({ property }) => property).join(", ")}) with the value it drew`);
			const [{ property, bound }] = named;
			const value = detail[property];
			const snapshot = !bound || value === null ? null : typeof value === "object" ? suppliedSnapshot(value) : this.#retire(property, value);
			if (snapshot === void 0) throw new Error(`<${this.localName} id=${this.id}> drew a ${property} Leaf did not set`);
			projectMarked(this, snapshot);
		} catch (error) {
			failSoft(this, error);
		}
	}
	#retire(property, value) {
		const primitives = this.#sent.get(property)?.primitives;
		if (!primitives?.has(value)) return void 0;
		for (const earlier of primitives.keys()) {
			if (earlier === value) break;
			primitives.delete(earlier);
		}
		return primitives.get(value);
	}
	#hold() {
		this.#held = true;
		return () => {
			this.#held = false;
			this.#refresh();
		};
	}
	#complete() {
		if (!this.#controller) return true;
		const { state } = this.#controller.read();
		return this.#verbs.every((verb) => verb in state);
	}
	shouldUpdate(changed) {
		if (!this.#connected || !this.isConnected) return false;
		if (this.#held) return false;
		this.#drawing = this.#ticket ?? this.#claim();
		this.#ticket = null;
		if (!this.#draws()) return false;
		this.#deliverInputs();
		return super.shouldUpdate(changed);
	}
	#draws() {
		return !this.#broken && this.#complete() && !awaitsData(this);
	}
	update(changed) {
		super.update(changed);
		this.#box?.remove();
		this.#box = null;
	}
	performUpdate() {
		const outer = this.#drawing;
		const updating = this.#updating;
		this.#drawing = null;
		this.#updating = true;
		try {
			this.#signalError = null;
			super.performUpdate();
			if (this.#signalError) throw this.#signalError.error;
			if (this.#drawing) this.#drawing.resolve(this.updateComplete.then(() => void 0, (error) => {
				reportFailure(this, error);
				throw error;
			}));
		} catch (error) {
			if (outer && !this.#drawing) throw error;
			this.#failed(error, this.#drawing);
		} finally {
			this.#drawing = outer;
			this.#updating = updating;
		}
	}
	redraw() {
		if (this.#draws()) render(this.render(), this.renderRoot, this.renderOptions);
	}
	updated(changed) {
		super.updated(changed);
		d(() => paintKeysWithin(this));
	}
	#failed(error, ticket) {
		if (!ticket) return failSoft(this, error);
		reportFailure(this, error);
		ticket.reject(error);
	}
	#claim() {
		return this.#region.present((reason) => failSoftUnreported(this, reason));
	}
	#stage() {
		if (!this.#connected || this.#ticket || !this.#region) return;
		this.#ticket = this.#claim();
	}
	#present({ now = false } = {}) {
		if (!this.#region) return;
		this.#ticket = this.#claim();
		if (this.#held) return;
		this.requestUpdate();
		if (now) {
			this.#scheduled = null;
			this.performUpdate();
		} else if (this.#descriptor) this.#queueUpdate();
	}
	#refresh() {
		if (this.#connected) this.#present({ now: true });
	}
	#connect() {
		this.#connected = true;
		this.#region = this.#descriptor ? attachWidgetPresentation(this.#descriptor.id, "render") : attachApplicationPresentation(this.#regionName);
		const parentChanged = this.#connectedParent !== this.parentElement;
		this.#connectedParent = this.parentElement;
		if (registry[this.localName]?.["x-data"]) this.#leaveData = joinDataDelivery(this.#descriptor ? `widget:${this.#descriptor.id}:render` : this.#regionName);
		this.#present();
		if (this.#descriptor) widgetMounted(this, this.#descriptor, parentChanged);
	}
	#disconnect() {
		this.#connected = false;
		this.#stopReadiness?.();
		this.#stopReadiness = null;
		this.#leaveData?.();
		this.#leaveData = null;
		this.#ticket = null;
		this.#region?.disconnect();
		this.#region = null;
	}
};

//#endregion
//#region runtime/queue-title.js
function queueTitle(item) {
	const thread = readThreads().threads.find((thread) => thread.id === item.thread);
	const own = elementById(item.subject.id);
	const topic = thread ? threadName(thread) : "";
	const title = item.todo?.title ?? item.obligation?.prompt.text;
	if (title) return title;
	const reply = item.kind === "update" ? item.obligation?.answer?.event?.id : null;
	const sent = reply && thread?.msgs.find((message) => message.id === reply);
	if (sent) return sent.body.text.trim() || topic;
	if (item.subject.kind === "widget") {
		const record = own && obligationHolding(readObligations().all, own);
		return record && addressableLabel(obligationPlace(record).context) || addressableLabel(own) || topic || item.id;
	}
	return topic || item.id;
}

//#endregion
//#region runtime/obligations/answer.js
function ownedObligationControl(source, commandSource) {
	const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
	return !selector || closestAcross(commandSource, selector) === source;
}
function obligationWord(item) {
	if (item.source.kind === "message") return "Reply";
	if (item.source.kind === "todo") return "To-do";
	const word = widgetWord(item.source.tag, elementById(item.source.id));
	return word.charAt(0).toUpperCase() + word.slice(1);
}
function answerWords(item) {
	if (item.answer === null) return "";
	if (answeredInWords(item)) return item.answer.value.text ?? item.answer.value.token ?? "";
	const source = elementById(item.source.id);
	const formatter = customElements.get(item.source.tag)?.answerWords;
	return String(source && formatter ? formatter(item.answer.value, source) : "").replace(/\s+/g, " ").trim();
}
function obligationEnding(item) {
	if (item.source.kind === "todo") return item.status === "withdrawn" ? "Dropped" : item.answer?.value === "failed" ? "Failed" : "Done";
	if (item.status === "withdrawn") return "Withdrawn";
	if (item.status === "answered_elsewhere") return "Answered elsewhere";
	const words = answerWords(item);
	return words ? `Answered: ${words}` : "Answered";
}

//#endregion
//#region runtime/page-layout.js
const rootHeaders = /* @__PURE__ */ new Set();
const paintRootHeaders = () => {
	const height = [...rootHeaders].filter((header) => header.isConnected).reduce((total, header) => total + header.getBoundingClientRect().height, 0);
	const root = document.documentElement;
	if (height) setRuntimeRootStyle(root, "--lf-root-headers", `${height}px`);
	else removeRuntimeRootStyle(root, "--lf-root-headers");
};
const syncRootHeaders = () => afterScript(paintRootHeaders);
function registerRootHeader(header) {
	return whileConnected(header, () => {
		rootHeaders.add(header);
		const size = sizeObserver(syncRootHeaders);
		size.observe(header, { box: "border-box" });
		syncRootHeaders();
		return () => {
			size.disconnect();
			rootHeaders.delete(header);
			syncRootHeaders();
		};
	});
}
function createPageLayout({ scheduleThreadPreviewPosition, syncReactLayout, refreshFab, pageShifted, repaintPage }) {
	function syncLayout() {
		syncLayoutRegion();
		scheduleMarginContentLayout();
		scheduleThreadPreviewPosition?.();
		if (syncReactLayout()) return;
		refreshFab();
	}
	let bodyContentWidth = 0;
	let bodyContentHeight = 0;
	const layoutSizes = sizeObserver(([{ contentRect }]) => {
		const widthChanged = contentRect.width !== bodyContentWidth;
		const moved = widthChanged || contentRect.height !== bodyContentHeight;
		bodyContentWidth = contentRect.width;
		bodyContentHeight = contentRect.height;
		if (widthChanged) repaintPage();
		else if (moved) pageShifted();
	});
	function mountLayoutObservers() {
		addEventListener("resize", syncLayout);
		layoutSizes.observe(document.body);
	}
	return {
		syncLayout,
		mountLayoutObservers
	};
}

//#endregion
//#region runtime/keyboard/disclosure.js
const disclosureWatch = new MutationObserver((records) => {
	for (const r of records) if (r.target.getAttribute(r.attributeName) !== r.oldValue) paintKeysWithin(r.target);
});
const watchDisclosures = (root) => disclosureWatch.observe(root, {
	subtree: true,
	attributeFilter: ["open", "aria-expanded"],
	attributeOldValue: true
});
const DISCLOSE = (el) => {
	const open = disclosed(el);
	if (open === null) return [
		...PRESS,
		"ArrowLeft",
		"ArrowRight"
	];
	const [back, ahead] = rowArrows(el);
	return inChrome(el) ? PRESS : [...PRESS, open ? back : ahead];
};
const DISCLOSURE_SELECTOR = "details > summary, :is(button, [role=\"button\"])[aria-expanded]";
function disclosed(el) {
	return !el?.matches?.("details > summary, :is(button, [role=\"button\"])[aria-expanded]") ? null : el.matches("details > summary") ? el.parentElement.open : el.getAttribute("aria-expanded") === "true";
}

//#endregion
export { CONTRIBUTION_ENTRY_SCHEMA, DISCLOSE, DISCLOSURE_SELECTOR, DRAWING_COORDINATE_LIMIT, KINDS, LeafElement, MAX_DRAWING_FRAME_DEPTH, MAX_DRAWING_POINTS, MAX_DRAWING_SAYS_LENGTH, MAX_DRAWING_STROKES, activateContributionControl, annotationItems, answerWords, awaitingUser, beginRead, canFold, choosePrimary, clearContributionControls, clusterProjection, composerOpen, composerQuote, consumeAnnotations, contributionEntry, contributionEntryRecord, contributionEntrySource, contributionHost, contributionItemKey, contributionReceipts, contributionSource, createPageLayout, createReactionController, createSelectionComposer, createThreadLanding, currentLocationThread, currentProjection, declareThreadKeys, disclosed, entryControls, entryEngaged, entryHasMarginHost, fabBar, fabInput, fabOptionsTrigger, focusedOfferOf, inPageOrder, landInThread, leafEditorView, leavesBox, markerFace, materializeContributionControls, mountApplication, navigateToDatum, obligationActions, obligationEnding, obligationWord, optionsOffered, ownedObligationControl, paintBarReactions, partOver, pendingAbout, pendingAnchor, pendingDrawing, placePageThreads, presentContributionEntry, presentContributionReceipts, primaryReading, queueActions, queueItemKey, queueTitle, reactionAvailable, reactionTokens, readPlan, readQueues, readingBehavior, readingChoices, readingContext, readingFace, readingKey, readingLabel, readingState, registerContribution, registerRootHeader, registerThreadPresentation, sendReaction, spokenContext, spokenSubject, syncContributionSelection, syncContributionUnread, textField, threadActions, threadBox, threadInput, threadReading, unreadIn, visibleContributionEntryLabel, watchDisclosures, widgetController, wireInput };