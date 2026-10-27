import { afterScript, focusDestination, focused, keeps, keepsText } from "./bundle-dom-move.js";
import { html, render } from "./bundle-context.js";
import { commandAvailable, commandBinding, commandRoutes, controlAvailabilityOutput, elementDirective, iconTemplate, isCommandScope, offer, pressIsKeyboardActivation, projectCommandScope, watchCommandAvailability } from "./bundle-errors.js";
import { excerptWords } from "./bundle-passages.js";
import { HOLDS_WORD, progressFace, threadAttention, workflowLabel } from "./bundle-surfaces.js";
import { agentArrivalDuration, reducedMotion } from "./bundle-motion.js";

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
	"icon",
	"label",
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
		label: "Saved",
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
	const { key, glyph = null, icon = null, label, accessibleLabel = null, context = null, description = null, behavior = "action", tone = "neutral", rank = "primary", state = "idle", visible = true, disabled = false, count = 1, pressed = null, workflowReceipt = void 0, relation = null, activation = key, title = null, className = null, scope = null } = offered;
	if (!text$1(key)) throw new TypeError("A contribution entry needs a key");
	if (Boolean(text$1(glyph)) === Boolean(icon)) throw new TypeError("A contribution entry needs exactly one glyph or icon");
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
		word: workflowLabel(receipt),
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
        ><span class="lf-margin-entry-label-word">${visibleLabel}</span>${record.context ? html`<span class="lf-margin-entry-context">${record.context}</span>` : null}<span class="lf-margin-entry-more"></span></span
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
//#region runtime/margin-model.js
const TOGGLE = Object.freeze({
	icon: "more",
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
function threadMarks(thread) {
	const attention = threadAttention(thread);
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
export { CONTRIBUTION_ENTRY_SCHEMA, KINDS, activateContributionControl, annotationItems, awaitingUser, canFold, choosePrimary, clearContributionControls, clusterProjection, compareContributions, contributionControlKey, contributionEntries, contributionEntry, contributionEntryRecord, contributionEntrySource, contributionHost, contributionItemKey, contributionReceipts, contributionSource, entryControls, entryEngaged, entryHasMarginHost, focusedOfferOf, marginInventory, markerFace, materializeContributionControls, optionsOffered, presentContributionEntry, presentContributionReceipts, presentingContributions, primaryReading, readingBehavior, readingChoices, readingContext, readingFace, readingKey, readingLabel, readingState, registerContribution, spokenContext, spokenSubject, syncContributionSelection, syncContributionUnread, threadMarks, threadReading, unreadIn, visibleContributionEntryLabel, watchContributions };