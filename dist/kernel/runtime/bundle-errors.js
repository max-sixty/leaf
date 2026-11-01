import { __exportAll } from "./bundle-rolldown-runtime.js";
import { ANNOUNCE, CARET_KEYS, COMMANDS, J, PRESS, PRESSES, ROLE_BUTTON_OFFER, W, WORKS, Z, actionTemplate, bindQueuedWork, coarsePointer, commandsChangedOn, controlNavigationKeys, d, focusDestination, focusRevision, holdFocus, installLanguagePaths, installMoveFocus, isElement, isHTML, isNativeLayer, isStage, keeps, liveStages, move, nextRender, offer, offerAction, onCurrentLocation, onFocusVisibility, pressIsKeyboardActivation, refuseCommands, renderedParent, renderedUnder, shadowHost, showNativeLayer, takesLetters, under, watchCurrentLocationIn, x } from "./bundle-portable.js";
import { AsyncDirective, LitElement as LitElement$1, PartType as PartType$1, directive as directive$1, guard, html as html$1, keyed, live as live$1, noChange, nothing as nothing$1, ref, render as render$1, repeat } from "/vendor/lit.js";

//#region runtime/move-focus.js
installMoveFocus({
	hold: holdFocus,
	watch: watchCurrentLocationIn
});

//#endregion
//#region runtime/obligations/source.js
const hasObligationSource = (item, kind) => item?.source.kind === kind;

//#endregion
//#region runtime/framework/snapshot.js
const secured = /* @__PURE__ */ new WeakSet();
function immutable(value) {
	if (value !== null && typeof value === "object" && !secured.has(value)) {
		if (value instanceof Map) for (const [key, child] of value) {
			immutable(key);
			immutable(child);
		}
		else if (value instanceof Set) for (const child of value) immutable(child);
		else for (const child of Object.values(value)) immutable(child);
		if (value instanceof Map || value instanceof Set) {
			const refuse = () => {
				throw new TypeError("Application snapshots are read-only");
			};
			for (const name of value instanceof Map ? [
				"set",
				"delete",
				"clear"
			] : [
				"add",
				"delete",
				"clear"
			]) Object.defineProperty(value, name, { value: refuse });
		}
		Object.freeze(value);
		secured.add(value);
	}
	return value;
}
const plain = (value) => {
	const proto = Object.getPrototypeOf(value);
	return proto === Object.prototype || proto === null;
};
function share(prior, next) {
	if (Object.is(prior, next)) return next;
	if (prior === null || next === null || typeof prior !== "object" || typeof next !== "object") return next;
	if (Array.isArray(next)) {
		if (!Array.isArray(prior)) return next;
		const children = next.map((child, index) => share(prior[index], child));
		if (prior.length === next.length && children.every((child, index) => child === prior[index])) return prior;
		return children.every((child, index) => child === next[index]) ? next : children;
	}
	if (next instanceof Map) {
		if (!(prior instanceof Map)) return next;
		const priorKeys = [...prior.keys()];
		const entries = [...next].map(([key, child]) => [key, prior.has(key) ? share(prior.get(key), child) : child]);
		if (priorKeys.length === entries.length && entries.every(([key, child], index) => key === priorKeys[index] && child === prior.get(key))) return prior;
		return entries.every(([key, child]) => child === next.get(key)) ? next : new Map(entries);
	}
	if (next instanceof Set) {
		if (!(prior instanceof Set)) return next;
		const priorMembers = [...prior];
		const members = [...next].map((child, index) => share(priorMembers[index], child));
		if (priorMembers.length === members.length && members.every((child, index) => child === priorMembers[index])) return prior;
		return members.every((child) => next.has(child)) ? next : new Set(members);
	}
	if (!plain(next) || !plain(prior) || Array.isArray(prior) || prior instanceof Map || prior instanceof Set) return next;
	const before = prior;
	const after = next;
	const keys = Object.keys(after);
	const children = keys.map((key) => Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key]);
	if (keys.length === Object.keys(before).length && keys.every((key, index) => Object.hasOwn(before, key) && children[index] === before[key])) return prior;
	if (keys.every((key, index) => children[index] === after[key])) return next;
	const copy = Object.getPrototypeOf(next) === null ? /* @__PURE__ */ Object.create(null) : {};
	keys.forEach((key, index) => Object.defineProperty(copy, key, {
		value: children[index],
		writable: true,
		enumerable: true,
		configurable: true
	}));
	return copy;
}
function createApplicationPublisher(initial) {
	const root = Z(immutable(initial));
	return Object.freeze({
		read: () => root.value,
		peek: () => root.peek(),
		publish(candidate) {
			root.value = immutable(share(root.peek(), candidate));
			return root.peek();
		},
		select(derive) {
			let prior;
			const selected = J(() => {
				const value = root.value;
				return d(() => prior = immutable(share(prior, derive(value))));
			});
			return Object.freeze({
				read: () => selected.value,
				subscribe: (listener) => selected.subscribe((value) => d(() => listener(value)))
			});
		}
	});
}

//#endregion
//#region runtime/projection/model.js
const stateCoordinate = (owner, unit, verb) => JSON.stringify([
	owner,
	unit,
	verb
]);
const coordinateOf = (key) => JSON.parse(key);
function foldedValue(event, record) {
	const value = event.detail.value;
	if (record.kind === "attribute" && Array.isArray(value)) return value.toSorted();
	return value ?? null;
}
const sameValue = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const compareProjected = (a, b) => {
	const aLogged = Number.isInteger(a.e.seq);
	const bLogged = Number.isInteger(b.e.seq);
	if (aLogged && bLogged) return (a.e.seq ?? 0) - (b.e.seq ?? 0);
	if (aLogged) return -1;
	if (bLogged) return 1;
	return (a.localOrder ?? 0) - (b.localOrder ?? 0);
};
function foldProjection({ entries = [], actionIds = [], reportIds = [], desiredIds = [], coverage = [], pendingEntries = [] } = {}) {
	const actions = /* @__PURE__ */ new Map();
	const reports = /* @__PURE__ */ new Map();
	const classified = /* @__PURE__ */ new Map();
	const desired = /* @__PURE__ */ new Map();
	const byId = /* @__PURE__ */ new Map();
	const pendingWithdrawals = /* @__PURE__ */ new Map();
	for (const entry of entries) {
		classified.set(entry.e.id, entry);
		byId.set(entry.e.id, entry);
	}
	for (const id of actionIds) {
		const entry = byId.get(id);
		if (entry && !entry.terminal) actions.set(entry.coordinate, entry);
	}
	for (const id of reportIds) {
		const entry = byId.get(id);
		if (!entry || entry.terminal) continue;
		const reported = reports.get(entry.coordinate) ?? [];
		reported.push(entry);
		reports.set(entry.coordinate, reported);
	}
	for (const id of desiredIds) {
		const entry = byId.get(id);
		if (entry && !entry.terminal) desired.set(entry.coordinate, entry);
	}
	for (const record of coverage) {
		const e = record.event;
		if (e.kind === "undo" || classified.has(e.id)) continue;
		classified.set(e.id, {
			e,
			terminal: record.coordinate === null
		});
	}
	const pendingActions = [];
	const withdrawn = /* @__PURE__ */ new Set();
	const recompute = (coordinate) => {
		const local = pendingActions.filter((entry) => entry.coordinate === coordinate && !withdrawn.has(entry.e.id)).at(-1);
		const durable = [...classified.values()].filter((entry) => Boolean(entry.stands && entry.coordinate === coordinate && !withdrawn.has(entry.e.id))).sort(compareProjected).at(-1);
		const action = local ?? durable;
		for (const view of [actions, desired]) if (action) view.set(coordinate, action);
		else view.delete(coordinate);
	};
	for (const entry of pendingEntries) {
		if (entry.kind === "undo") {
			const targetId = entry.targetId ?? entry.target.e.id;
			const target = classified.get(targetId) ?? entry.target;
			withdrawn.add(targetId);
			pendingWithdrawals.set(targetId, target);
			recompute(entry.coordinate);
			continue;
		}
		pendingActions.push(entry);
		recompute(entry.coordinate);
	}
	return {
		actions,
		reports,
		classified,
		desired,
		pendingWithdrawals
	};
}
const authoredValue = (authoredSnapshots, { unit, e: { widget: owner, action: verb } }) => {
	const authored = authoredSnapshots.get(owner);
	if (!authored) return void 0;
	const spec = authored.specs.get(verb);
	const state = authored.state[verb];
	if (!spec || !state) throw new Error(`Missing authored state for ${owner}/${verb}`);
	const record = spec.record;
	const value = state.value;
	if (record?.kind === "position" && "units" in state) return Object.keys(state.value).find((container) => state.value[container]?.includes(unit)) ?? null;
	return value;
};
function projectionOrigins(authoredSnapshots, projection) {
	const origins = /* @__PURE__ */ new Map();
	const add = (origin, unit) => {
		const key = `${origin}:${unit}`;
		if (!origins.has(key)) origins.set(key, {
			origin,
			unit
		});
	};
	for (const entry of projection.classified.values()) for (const unit of entry.restated ?? []) add("restated", unit);
	for (const entry of projection.desired.values()) {
		const { unit, e, spec, value } = entry;
		if (!(spec.record ? !sameValue(value, authoredValue(authoredSnapshots, entry)) : true)) continue;
		add(e.kind === "action" ? "user" : "reported", unit);
	}
	return [...origins.values()];
}
const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";
const authoredRank = (index) => "z".repeat(Math.floor(index / 35)) + DIGITS.charAt(index % 35 + 1);
const byRank = (ranks) => (a, b) => {
	const left = ranks[a];
	const right = ranks[b];
	if (left !== void 0 && right !== void 0 && left !== right) return left < right ? -1 : 1;
	return a < b ? -1 : a > b ? 1 : 0;
};
function rankBetween(before, after) {
	if (after === null) return before ? rankAfter(before) : "i";
	if (!before) return rankBefore(after);
	if (before >= after) return before;
	return midpoint(before, after);
}
function rankAfter(key) {
	const digit = DIGITS.indexOf(key.charAt(0));
	if (digit < 35) return DIGITS.charAt(digit + 1);
	return "z" + (key.length > 1 ? rankAfter(key.slice(1)) : "1");
}
function rankBefore(key) {
	if (key.length > 1 && key.charAt(0) !== "0") return key.charAt(0);
	const digit = DIGITS.indexOf(key.charAt(0));
	if (digit > 1) return DIGITS.charAt(digit - 1);
	return "0" + (key.length > 1 ? rankBefore(key.slice(1)) : "z");
}
function midpoint(before, after) {
	if (after !== null) {
		let n = 0;
		while ((before[n] ?? "0") === after[n]) n += 1;
		if (n > 0) return after.slice(0, n) + midpoint(before.slice(n), after.slice(n));
	}
	const low = before ? DIGITS.indexOf(before.charAt(0)) : 0;
	const high = after !== null ? DIGITS.indexOf(after.charAt(0)) : 36;
	if (high - low > 1) return DIGITS.charAt(Math.round((low + high) / 2));
	if (after !== null && after.length > 1) return after.charAt(0);
	return DIGITS.charAt(low) + midpoint(before.slice(1), null);
}
function rankAt({ value, ranks }, container, index, unit) {
	const members = value[container];
	if (!members) throw new Error(`Unknown position container ${container}`);
	const others = members.filter((id) => id !== unit);
	const before = others[index - 1];
	const after = others[index];
	return rankBetween(before ? ranks[before] ?? "" : "", after ? ranks[after] ?? null : null);
}
function foldWidgetStates(authoredSnapshots, projection) {
	const copyState = (state) => structuredClone(state);
	const states = new Map([...authoredSnapshots].map(([id, authored]) => [id, {
		state: copyState(authored.state),
		entries: [],
		specs: authored.specs
	}]));
	const place = ({ value: containers, ranks }, unit, detail) => {
		const { value, rank } = detail;
		const destination = containers[value];
		if (!destination || !Object.values(containers).some((ids) => ids.includes(unit))) return;
		for (const ids of Object.values(containers)) {
			const index = ids.indexOf(unit);
			if (index >= 0) ids.splice(index, 1);
		}
		destination.push(unit);
		ranks[unit] = rank;
	};
	for (const entry of [...projection.desired.values()].sort(compareProjected)) {
		const owner = states.get(entry.e.widget);
		if (!owner) continue;
		const { spec, e, unit } = entry;
		const value = spec.record ? structuredClone(e.detail.value) : e.action;
		const current = {
			action: e.action,
			value,
			detail: structuredClone(e.detail)
		};
		owner.entries.push(entry);
		const target = owner.state[e.action];
		if (target && "units" in target) {
			target.units[unit] = current;
			if ("ranks" in target && !entry.absorbed) place(target, unit, e.detail);
		} else {
			if (spec.unit !== "widget") throw new Error(`Missing authored units for ${e.widget}/${e.action}`);
			owner.state[e.action] = current;
		}
	}
	for (const { state } of states.values()) for (const position of Object.values(state)) if ("ranks" in position) for (const ids of Object.values(position.value)) ids.sort(byRank(position.ranks));
	return states;
}
function obligationValue(widget, verb, answered, unit) {
	const complete = widget.state[verb];
	const state = unit !== void 0 && complete && "units" in complete ? complete.units[unit] : complete;
	if (unit !== void 0 && !state) return {
		value: null,
		present: false
	};
	const spec = widget.specs.get(verb);
	if (!state || !spec) throw new Error(`Missing obligation value definition for ${verb}`);
	const recorded = (value) => spec.record?.kind === "attribute" && Array.isArray(value) ? value.toSorted() : value;
	const value = "units" in state ? spec.record?.kind === "position" ? state.value : Object.fromEntries(Object.entries(state.units).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([id, entry]) => [id, spec.record ? recorded(entry.value) : entry.detail])) : spec.record ? recorded(state.value) : state.action ? state.detail : null;
	const populated = value !== null && value !== "" && (typeof value !== "object" || Object.keys(value).length > 0);
	const hasInput = "units" in state ? Object.keys(state.units).length > 0 : Boolean(state.action);
	return {
		value,
		present: value !== null && (populated || answered || hasInput)
	};
}
const isProjectionEntry = (entry) => entry.coordinate !== void 0;

//#endregion
//#region runtime/kernel-facts.js
const COLLAPSE = /[\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
const DRAFT_FORMAT = "leaf-draft/17";
const MESSAGE_KINDS = /* @__PURE__ */ new Set(["comment", "reply"]);
const TEXT_BLOCK = "p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary";
const VERB_WRITERS = {
	"action": "user",
	"report": "agent"
};
const WIDGET_NAME = /^lf-[a-z0-9]+(?:-[a-z0-9]+)*$/;
const drawingSchema = {
	"type": "object",
	"properties": {
		"strokes": {
			"type": "array",
			"minItems": 1,
			"maxItems": 32,
			"items": {
				"type": "array",
				"minItems": 2,
				"maxItems": 256,
				"items": {
					"type": "array",
					"minItems": 2,
					"maxItems": 2,
					"prefixItems": [{
						"type": "number",
						"minimum": -33554432,
						"maximum": 33554432
					}, {
						"type": "number",
						"minimum": -33554432,
						"maximum": 33554432
					}],
					"items": false
				}
			}
		},
		"box": {
			"type": "array",
			"minItems": 2,
			"maxItems": 2,
			"prefixItems": [{
				"type": "number",
				"exclusiveMinimum": 0,
				"maximum": 33554432
			}, {
				"type": "number",
				"exclusiveMinimum": 0,
				"maximum": 33554432
			}],
			"items": false
		},
		"frame": {
			"type": "object",
			"properties": {
				"root": {
					"type": "string",
					"maxLength": 128,
					"pattern": "^[A-Za-z][A-Za-z0-9_.:-]*$"
				},
				"path": {
					"type": "array",
					"maxItems": 32,
					"items": {
						"type": "object",
						"properties": {
							"tag": {
								"type": "string",
								"maxLength": 128,
								"pattern": "^[A-Za-z][A-Za-z0-9_.:-]*$"
							},
							"index": {
								"type": "integer",
								"minimum": 0,
								"maximum": 65535
							},
							"siblings": {
								"type": "integer",
								"minimum": 1,
								"maximum": 65536
							},
							"shadow": { "type": "boolean" }
						},
						"required": [
							"tag",
							"index",
							"siblings"
						],
						"additionalProperties": false
					}
				}
			},
			"required": ["root", "path"],
			"additionalProperties": false
		},
		"says": {
			"type": "string",
			"minLength": 1,
			"maxLength": 500
		},
		"viewport": {
			"type": "array",
			"minItems": 2,
			"maxItems": 2,
			"prefixItems": [{
				"type": "number",
				"exclusiveMinimum": 0,
				"maximum": 33554432
			}, {
				"type": "number",
				"exclusiveMinimum": 0,
				"maximum": 33554432
			}],
			"items": false
		},
		"scheme": { "enum": ["light", "dark"] }
	},
	"required": [
		"strokes",
		"box",
		"viewport",
		"scheme"
	],
	"additionalProperties": false
};
const marks = {
	"x-content": {
		"paint": "data-lf-content",
		"message": true
	},
	"x-verbatim": {
		"paint": "data-lf-verbatim",
		"message": true
	},
	"x-space": {
		"paint": "data-lf-space",
		"authored": "data-width",
		"authored_on": "content",
		"message": false
	},
	"x-inline": {
		"paint": "data-lf-inline",
		"message": true
	},
	"x-exhibit": {
		"paint": "data-lf-exhibit",
		"message": true
	},
	"x-bound": {
		"paint": "data-lf-bound",
		"authored": "data-bound",
		"authored_on": "content",
		"message": true
	},
	"x-height": {
		"paint": "data-lf-height",
		"authored": "data-height",
		"authored_on": "declared",
		"message": true
	},
	"x-reading-role": {
		"paint": "data-lf-reading-role",
		"message": true
	},
	"x-views": {
		"paint": "data-lf-views",
		"message": true
	},
	"x-visual": {
		"paint": "data-lf-visual",
		"presence": true,
		"message": true
	},
	"x-awaits": {
		"paint": "data-lf-awaits",
		"presence": true,
		"message": true
	}
};

//#endregion
//#region runtime/registry-contract.js
function stampedState(registry, tag, event) {
	const state = registry.$states[tag]?.[event.action];
	return state?.writer === VERB_WRITERS[event.kind] ? state : null;
}
function sameStateDefinition(recorded, current) {
	if (recorded === current) return true;
	if (!recorded || !current || typeof recorded !== "object" || typeof current !== "object" || Array.isArray(recorded) !== Array.isArray(current)) return false;
	const fields = new Map(Object.entries(recorded));
	const other = new Map(Object.entries(current));
	return fields.size === other.size && [...fields].every(([key, value]) => other.has(key) && sameStateDefinition(value, other.get(key)));
}
const isElementName = (name) => WIDGET_NAME.test(name);

//#endregion
//#region runtime/anchor-coordinate.js
const RENDERING = /* @__PURE__ */ new Set(["source_revision", "datum"]);
const PRIMITIVE = /* @__PURE__ */ new Set([
	"string",
	"number",
	"boolean"
]);
const anchorKey = (anchor) => {
	const identified = typeof anchor?.identity === "string";
	return JSON.stringify(Object.entries(anchor ?? {}).filter(([key, value]) => PRIMITIVE.has(typeof value) && !(identified && RENDERING.has(key))).sort(([left], [right]) => left.localeCompare(right)));
};
const sameAnchor = (a, b) => a === b || Boolean(a) && Boolean(b) && anchorKey(a) === anchorKey(b);
const fragmentId = (fragment) => {
	const raw = fragment.slice(1);
	try {
		return decodeURIComponent(raw);
	} catch {
		return raw;
	}
};

//#endregion
//#region runtime/thread/identity.js
const PENDING = "pending:";

//#endregion
//#region runtime/thread/model.js
const isReaction = (message) => Boolean(message.token);
const isAddressable = (message) => message.addressable !== false;
function reactionChoices(thread, message, tokens) {
	if (thread.resolved || message.author !== "agent" || !isAddressable(message) || !Object.keys(tokens).length) return null;
	const latest = thread.msgs.findLast((item) => item.author === "agent" && isAddressable(item));
	const inForce = thread.msgs.filter((item) => isReaction(item) && item.author === "user" && item.parent === message.id);
	return {
		thread: thread.key,
		message: message.key,
		latest: latest?.id === message.id,
		agent: message.agent,
		choices: tokenChoices(tokens, inForce)
	};
}
const tokenChoices = (tokens, inForce) => Object.entries(tokens).map(([name, entry]) => ({
	name,
	glyph: entry.glyph,
	label: name,
	inForce: inForce.find((item) => item.token === name) ?? null
}));
const spoken$1 = (thread) => thread.msgs.filter((message) => !isReaction(message));
const turns = (thread) => thread.msgs.filter((message) => message.id === thread.root.id || !isReaction(message));
const threadKey = (thread) => thread.root.attempt ?? thread.id;
const messageKey = (message) => message.key ?? message.attempt ?? message.id;
function threadNames(threads) {
	const byName = /* @__PURE__ */ new Map();
	for (const thread of threads) {
		byName.set(thread.id, thread);
		for (const message of thread.msgs) {
			byName.set(message.id, thread);
			if (message.attempt) byName.set(PENDING + message.attempt, thread);
		}
	}
	return byName;
}
const editable = (message) => message.author === "user" && !message.pending && !message.token && Boolean(message.text);
const bareReaction = (thread) => thread.bare_reaction;
const discussed = (thread) => !thread.bare_reaction;
const hasUnread = (thread) => thread.unread.length > 0;
const isNews = (thread) => !thread.resolved && hasUnread(thread);
function threadCounts(threads) {
	const listed = threads.filter(discussed);
	return {
		open: listed.filter((thread) => !thread.resolved).length,
		unread: listed.filter(isNews).length
	};
}
const pendingSeat = (message) => message.about || !message.anchor || Object.keys(message.anchor).length !== 1 ? null : message.anchor.section ?? null;
const sending = (turn) => ({
	kind: "waiting",
	reason: "workflow",
	workflow: turn.id
});
function foldThreads(threads, gestures) {
	if (!gestures.length) return [...threads];
	const withdrawn = new Set(gestures.flatMap((gesture) => gesture.kind === "undo" ? [gesture.undoes] : []));
	const copies = threads.filter((thread) => !withdrawn.has(thread.root.id)).map((thread) => ({
		...thread,
		msgs: thread.msgs.filter((message) => !withdrawn.has(message.id)),
		...thread.resolved && "id" in thread.resolved && withdrawn.has(thread.resolved.id) ? { resolved: null } : {}
	}));
	const byName = threadNames(copies);
	const opened = [];
	for (const gesture of gestures) if (gesture.kind === "comment") {
		const reaction = isReaction(gesture);
		const thread = {
			id: gesture.id,
			root: gesture,
			title: null,
			anchor: gesture.anchor ?? null,
			detached_from: null,
			rewritten_from: null,
			msgs: [gesture],
			revisions: [],
			resolved: null,
			bare_reaction: reaction,
			seat: pendingSeat(gesture),
			summaries: [],
			unread: [],
			attention: reaction ? null : sending(gesture)
		};
		opened.push(thread);
		byName.set(gesture.id, thread);
	} else if (gesture.kind === "reply") {
		const thread = byName.get(gesture.parent);
		if (!thread) continue;
		const streaming = thread.msgs.at(-1)?.provisional ? 1 : 0;
		thread.msgs = thread.msgs.toSpliced(thread.msgs.length - streaming, 0, gesture);
		if (!isReaction(gesture)) thread.resolved = null;
	} else if (gesture.kind === "edit") {
		const thread = byName.get(gesture.message);
		const at = thread?.msgs.findIndex(({ id }) => id === gesture.message) ?? -1;
		const message = thread?.msgs[at];
		if (!thread || !message) continue;
		thread.msgs = thread.msgs.with(at, {
			...message,
			text: gesture.text,
			content_version: gesture.id,
			edited: {
				id: gesture.id,
				ts: gesture.ts,
				was: message.text ?? "",
				pending: true
			}
		});
		if (thread.root.id === gesture.message) thread.root = thread.msgs[at] ?? message;
		thread.resolved = null;
	} else if (gesture.kind === "resolve" || gesture.kind === "unresolve") {
		const thread = byName.get(gesture.parent) ?? (gesture.localParent ? byName.get(gesture.localParent) : void 0);
		if (!thread) continue;
		thread.resolved = gesture.kind === "resolve" ? {
			author: "user",
			pending: true
		} : null;
	}
	for (const thread of opened) thread.bare_reaction = isReaction(thread.root) && !spoken$1(thread).length;
	return [...copies, ...opened];
}
const reactionsAt = (threads, anchor) => threads.filter((thread) => !discussed(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor)).map((thread) => thread.root);
const seatRoot = (thread) => thread.seat;
const moved = (message) => ({
	seq: message.edited?.seq ?? message.seq ?? null,
	ts: message.edited?.ts ?? message.ts ?? null
});
function lastMovedAt(thread) {
	let latest = null;
	for (const message of turns(thread)) {
		const { ts } = moved(message);
		if (ts !== null && (latest === null || Date.parse(ts) > Date.parse(latest))) latest = ts;
	}
	return latest;
}
const versionKey = ({ message, version }) => `${message}\u0000${version}`;
function readThreadRecords(threads, document, widgets, workflows, todos = [], obligations = [], markingRead = [], ready = true) {
	const locallyRead = new Set(markingRead.map(versionKey));
	const unitsByMessage = /* @__PURE__ */ new Map();
	for (const descriptor of document.descriptors.values()) {
		if (descriptor.document.kind !== "thread") continue;
		const units = unitsByMessage.get(descriptor.document.message) ?? [];
		units.push({
			id: descriptor.id,
			tag: descriptor.tag,
			state: widgets.get(descriptor.id)?.state ?? {}
		});
		unitsByMessage.set(descriptor.document.message, units);
	}
	const readMessage = (message, unreadMessages, thread) => {
		const { markup, plainText, attention, session, publication, responds, start, title, ...record } = message;
		const units = unitsByMessage.get(message.id) ?? [];
		const authored = document.messageBodies?.get(message.id);
		if (markup && !authored) throw new Error(`Authored message ${message.id} has no captured body`);
		const body = markup && authored ? {
			kind: "authored",
			...authored,
			units
		} : {
			kind: message.token ? "reaction" : message.suggestion ? "suggestion" : "prose",
			text: authored?.text ?? plainText ?? message.text ?? message.token ?? ""
		};
		const unitIds = new Set(units.map((unit) => unit.id));
		return {
			...record,
			thread,
			unread: unreadMessages.has(message.id),
			key: messageKey(message),
			body,
			workflows: workflows.filter((workflow) => workflow.message === message.id || workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id))
		};
	};
	return threads.map((thread) => {
		const unread = thread.unread.filter((item) => !locallyRead.has(versionKey(item)));
		const unreadMessages = new Set(unread.map((item) => item.message));
		const msgs = thread.msgs.map((message) => readMessage(message, unreadMessages, threadKey(thread)));
		const reactions = {
			key: threadKey(thread),
			resolved: thread.resolved,
			msgs
		};
		const messages = msgs.map((message) => ({
			...message,
			reactions: ready ? reactionChoices(reactions, message, document.registry.$reactions?.tokens ?? {}) : null
		}));
		const root = messages.find((message) => message.id === thread.root.id);
		if (!root) throw new Error(`Thread ${thread.id} has no root message`);
		return {
			id: thread.id,
			key: threadKey(thread),
			title: thread.title,
			root,
			msgs: messages,
			unread: Object.freeze(unread),
			anchor: thread.anchor,
			detached_from: thread.detached_from,
			rewritten_from: thread.rewritten_from,
			resolved: thread.resolved,
			attention: thread.attention,
			obligations: obligations.filter((obligation) => obligation.thread === thread.id),
			todos: todos.filter((todo) => todo.owner === "agent" && todo.thread === thread.id),
			userTodos: todos.filter((todo) => todo.owner === "user" && todo.thread === thread.id),
			workflows: workflows.filter((workflow) => workflow.thread === thread.id),
			bare_reaction: thread.bare_reaction,
			seat: thread.seat,
			summaries: thread.summaries
		};
	});
}

//#endregion
//#region runtime/pending/model.js
const isThreadEvent = (event) => MESSAGE_KINDS.has(event.kind);
const isMessageEvent = (event) => isThreadEvent(event) && !event.token;
const isTurnEvent = (event) => isMessageEvent(event) || event.kind === "edit";
const turnMessage = (turn) => turn.kind === "edit" && turn.message ? turn.message : turn.id;
const threadForAttempt = (event, timestamp) => ({
	...event,
	id: `${PENDING}${event.attempt}`,
	content_version: `${PENDING}${event.attempt}`,
	author: "user",
	ts: timestamp,
	pending: true
});
const editForAttempt = (event, timestamp) => ({
	...event,
	id: `${PENDING}${event.attempt}`,
	author: "user",
	ts: timestamp,
	pending: true
});
const NAMING_FIELDS = [
	"parent",
	"message",
	"base",
	"undoes"
];
const pendingId = (value) => typeof value === "string" && value.startsWith("pending:");
const namesEvent = (event, id) => NAMING_FIELDS.some((field) => event[field] === id);
const namesPending = (event) => NAMING_FIELDS.some((field) => pendingId(event[field]));
const nameAdmitted = (event, admitted) => {
	let named = event;
	for (const field of NAMING_FIELDS) {
		const value = event[field];
		const id = pendingId(value) ? admitted(value.slice(PENDING.length)) : null;
		if (id) named = {
			...named,
			[field]: id
		};
	}
	return named;
};
const actionForWidget = (descriptor, command, revision) => ({
	kind: "action",
	revision,
	widget: descriptor.id,
	action: command.verb,
	detail: structuredClone(command.detail ?? {}),
	...command.attempt && { attempt: command.attempt }
});

//#endregion
//#region runtime/voice.js
const saidBy = (voice, text) => Object.freeze({
	text,
	voice
});
const agentSays = (text) => saidBy("agent", text);
const leafSays = (text) => saidBy("leaf", text);
const runOf = (words) => typeof words === "string" || "voice" in words ? [words] : words;
const wordsText = (words) => runOf(words).map((part) => typeof part === "string" ? part : part.text).join("");
function voiceOf(words) {
	const voices = new Set(runOf(words).filter((part) => typeof part === "string" ? part : part.text).map((part) => typeof part === "string" ? null : part.voice));
	const [voice = null] = voices;
	return voices.size === 1 ? voice : null;
}
const voiced = (words) => runOf(words).map((part) => typeof part === "string" ? part : html$1`<span data-voice=${part.voice}>${part.text}</span>`);

//#endregion
//#region runtime/queues.js
const queueOffers = (item, ready, onUser) => ({
	open: ready,
	done: ready && onUser && item.kind === "todo"
});
const carriesObligation = (item) => item.kind === "widget" || item.kind === "message" || item.kind === "todo" && item.owner === "user";
const itemNoun = (item) => item.kind !== "update" ? item.kind : item.owner === "user" ? "resend" : item.thread !== null ? "reply" : "answer";
const OUTCOMES = Object.freeze({
	done: "Done",
	failed: "Failed",
	dropped: "Dropped"
});
const itemOutcome = (item) => item.kind === "update" ? agentSays("Answered") : saidBy(item.owner === "agent" ? "agent" : "leaf", OUTCOMES[item.state] ?? item.state);

//#endregion
//#region runtime/framework/application.js
const LIFECYCLE = {
	sending: {
		accept: "accepted",
		refuse: "refused",
		log: "sending:logged",
		present: "sending:presented"
	},
	"sending:logged": {
		accept: "accepted:logged",
		refuse: "refused",
		present: "sending:presented"
	},
	"sending:presented": {
		accept: "accepted:presented",
		refuse: "refused"
	},
	accepted: {
		log: "accepted:logged",
		present: "accepted:presented"
	},
	"accepted:logged": { present: "accepted:presented" },
	"accepted:presented": {},
	refused: {}
};
const SENDING = /* @__PURE__ */ new Set([
	"sending",
	"sending:logged",
	"sending:presented"
]);
const DRAWN_LOCALLY = /* @__PURE__ */ new Set(["sending", "accepted"]);
const RELEASABLE = /* @__PURE__ */ new Set(["accepted:presented", "refused"]);
const UNPRESENTED = /* @__PURE__ */ new Set([
	"sending",
	"accepted",
	"sending:logged",
	"accepted:logged"
]);
function admittedId(attempt, unresolved, receipts) {
	if (!attempt) return null;
	return unresolved.find((entry) => entry.event.attempt === attempt)?.admitted?.id ?? receipts.find((receipt) => receipt.attempt === attempt)?.id ?? null;
}
function advance(entry, signal, admitted = null) {
	const action = entry.event.kind === "action";
	if (signal === "present" && !action) return entry;
	const state = LIFECYCLE[entry.state][signal];
	if (!state) return entry;
	if (state === "accepted:logged" && !action) return null;
	return {
		...entry,
		state,
		admitted: entry.admitted ?? admitted
	};
}
function normalizedProjection(view) {
	const entries = [];
	const actionIds = [];
	const reportIds = [];
	const desiredIds = [];
	for (const projection of [view?.document.projection, view?.thread.projection]) {
		if (!projection) continue;
		for (const wire of projection.entries) {
			const e = wire.event;
			const coordinate = stateCoordinate(...wire.coordinate);
			entries.push({
				coordinate,
				e,
				restated: wire.restated,
				absorbed: wire.absorbed,
				stands: wire.stands,
				scope: wire.scope,
				spec: wire.spec,
				unit: wire.coordinate[1],
				value: wire.value
			});
		}
		actionIds.push(...projection.actions);
		reportIds.push(...projection.reports);
		desiredIds.push(...projection.desired);
	}
	return {
		entries,
		actionIds,
		reportIds,
		desiredIds,
		coverage: view?.coverage ?? []
	};
}
const NO_OBLIGATIONS = {
	all: [],
	user: [],
	unanswered: []
};
function normalizedObligations(view, widgets, document, projection, todos) {
	const todoRecords = new Map([...todos.open, ...todos.ended].map((todo) => [todo.id, todo]));
	const all = (view?.obligations ?? []).map((item) => {
		if (hasObligationSource(item, "todo")) {
			const todo = todoRecords.get(item.source.id);
			if (todo.state === "open" && item.status !== "open") return {
				...item,
				answer: null,
				status: "open",
				next_actor: "user",
				end: null
			};
			if ((todo.state === "done" || todo.state === "failed") && item.status === "open") return {
				...item,
				answer: {
					value: todo.state,
					event: null
				},
				status: "answered",
				next_actor: null,
				end: null
			};
			return item;
		}
		if (!hasObligationSource(item, "widget")) return item;
		const sourceId = item.source.id;
		const sourceUnit = item.source.unit;
		const widget = widgets.get(sourceId);
		const verb = (document.descriptors.get(item.source.id)?.declaration["x-awaits"])?.value;
		if (!verb || !widget) return item;
		const completed = item.status === "answered" && !(item.answer?.event && projection.pendingWithdrawals.has(item.answer.event.id));
		const { value, present } = obligationValue(widget, verb, completed, sourceUnit);
		const pendingValue = widget.entries.some(({ e, unit }) => e.action === verb && (sourceUnit === void 0 || unit === sourceUnit) && !Number.isInteger(e.seq)) || [...projection.pendingWithdrawals.values()].some(({ e, unit }) => e.widget === sourceId && (sourceUnit === void 0 || unit === sourceUnit) && (e.action === verb || e.id === item.answer?.event?.id));
		const answer = present ? {
			value,
			event: pendingValue ? null : item.answer?.event ?? null
		} : null;
		return {
			...item,
			answer
		};
	});
	return {
		all,
		user: all.filter((item) => item.next_actor === "user"),
		unanswered: all.filter((item) => item.status === "open")
	};
}
function localTodos(state, local) {
	const ending = new Set(local.flatMap(({ event }) => event.kind === "todo_end" ? [event.todo] : []));
	const undoing = new Set(local.flatMap(({ event }) => event.kind === "undo" ? [event.undoes] : []));
	const all = state?.browser.todos ?? [];
	const served = all.filter((todo) => todo.state === "open");
	const ended = all.filter((todo) => todo.state !== "open");
	const reopened = (todo) => todo.outcome !== null && undoing.has(todo.outcome.id);
	const open = [...served, ...ended.filter(reopened).map((todo) => ({
		...todo,
		state: "open",
		outcome: null
	}))];
	const locallyEnded = (todo) => ending.has(todo.id);
	return {
		open: open.filter((todo) => !locallyEnded(todo)),
		ended: [...ended.filter((todo) => !reopened(todo)), ...open.filter(locallyEnded).map((todo) => ({
			...todo,
			state: "done",
			running: null,
			outcome: {
				ts: null,
				detail: null
			}
		}))]
	};
}
const NO_QUEUES = {
	on_user: [],
	on_agent: [],
	done: []
};
function currentWidgetRelations(document, widgets, projection) {
	const parents = new Map([...document.descriptors].map(([id, descriptor]) => [id, descriptor.parent?.id]));
	const owners = /* @__PURE__ */ new Map();
	const memberships = /* @__PURE__ */ new Map();
	const members = (owner, attr) => memberships.get(owner)[attr];
	for (const [id, widget] of widgets) for (const [verb, spec] of widget.specs) {
		const record = spec.record;
		if (record?.kind === "attribute") {
			const named = owners.get(record.attr) ?? /* @__PURE__ */ new Set();
			named.add(id);
			owners.set(record.attr, named);
			const slots = memberships.get(id) ?? {};
			slots[record.attr] = [];
			memberships.set(id, slots);
		} else if (record?.kind === "position") {
			const state = widget.state[verb];
			if (state && "ranks" in state) for (const [container, units] of Object.entries(state.value)) for (const unit of units) parents.set(unit, container);
		}
	}
	for (const [attr, named] of owners) {
		for (const id of document.descriptors.keys()) {
			const seen = /* @__PURE__ */ new Set([id]);
			for (let parent = parents.get(id); parent; parent = parents.get(parent)) {
				if (seen.has(parent)) break;
				seen.add(parent);
				if (!named.has(parent)) continue;
				members(parent, attr).push(id);
				break;
			}
		}
		for (const { e, unit, spec } of projection.desired.values()) if (spec.creates && named.has(e.widget) && !document.descriptors.has(unit)) members(e.widget, attr).push(unit);
		for (const owner of named) members(owner, attr).sort();
	}
	return {
		parents,
		memberships
	};
}
function localQueues(served, workflows, todos, items, local) {
	const record = new Map(items.all.map((item) => [item.id, item]));
	const inventoryAt = new Map(items.all.map((item, at) => [item.id, at]));
	const open = new Set(todos.open.map((todo) => todo.id));
	const ended = new Set(todos.ended.map((todo) => todo.id));
	const todoRecord = new Map([...todos.open, ...todos.ended].map((todo) => [todo.id, todo]));
	const sentIn = new Set(workflows.flatMap((workflow) => workflow.stage === "sending" && workflow.condition === null && workflow.subject.kind === "thread" ? [workflow.thread] : []));
	const obligationOf = (item) => {
		const current = record.get(item.id);
		if (!current) throw new Error(`Queue item ${item.id} names no obligation`);
		return current;
	};
	const standsOpen = (item) => {
		if (!namesRecord(item)) return open.has(item.id);
		const current = obligationOf(item);
		return current.next_actor === item.owner && !(current.source.kind === "update" && current.thread !== null && sentIn.has(current.thread));
	};
	const reopened = (item) => namesRecord(item) ? obligationOf(item).status === "open" && obligationOf(item).next_actor === item.owner : open.has(item.id);
	const endedHere = (item) => namesRecord(item) ? obligationOf(item).status !== "open" : ended.has(item.id);
	const todoOf = (item) => {
		const local = todoRecord.get(item.id);
		if (!local) throw new Error(`Queue item ${item.id} names no to-do`);
		return local;
	};
	const current = (item) => namesRecord(item) ? {
		...item,
		obligation: obligationOf(item)
	} : {
		...item,
		kind: "todo",
		owner: "agent",
		todo: todoOf(item)
	};
	const asOpen = ({ state: _state, ended: _ended, detail: _detail, ...item }) => current(item);
	const asDone = (item) => ({
		...current(item),
		live: false,
		state: namesRecord(item) && obligationOf(item).status === "withdrawn" ? "dropped" : "done",
		ended: null,
		detail: null
	});
	const reopenedFor = (owner) => served.done.filter((item) => item.owner === owner && reopened(item));
	const localRow = (item) => {
		const source = item.source;
		return current({
			kind: "update",
			id: item.id,
			owner: item.next_actor,
			subject: source.subject,
			thread: item.thread,
			also: [],
			live: false
		});
	};
	return {
		on_user: [
			...served.on_user.filter(standsOpen).map(current),
			...reopenedFor("user").map(asOpen),
			...local.filter((item) => item.next_actor === "user").map(localRow)
		].toSorted((a, b) => onUserRank(a) - onUserRank(b) || (namesRecord(a) && namesRecord(b) ? inventoryAt.get(a.id) - inventoryAt.get(b.id) : 0)),
		on_agent: [
			...served.on_agent.filter((item) => item.kind !== "todo" && standsOpen(item)).map(current),
			...local.filter((item) => item.next_actor === "agent").map(localRow),
			...served.on_agent.filter((item) => item.kind === "todo" && standsOpen(item)).map(current),
			...reopenedFor("agent").map(asOpen)
		],
		done: [...[...served.on_user, ...served.on_agent].filter(endedHere).map(asDone), ...served.done.filter((item) => !reopened(item)).map(current)]
	};
}
function localUpdates(workflows) {
	const newest = /* @__PURE__ */ new Map();
	for (const workflow of workflows) if (workflow.stage === "sending" && workflow.condition === null) newest.set(workflow.thread, workflow);
	const records = [];
	return {
		workflows: workflows.map((workflow) => {
			if (workflow.stage !== "sending") return workflow;
			const refused = workflow.condition !== null;
			const owner = refused ? workflow : newest.get(workflow.thread);
			const id = `update:${owner.id}`;
			if (owner === workflow) records.push({
				id,
				source: {
					kind: "update",
					id: workflow.input,
					subject: workflow.subject
				},
				thread: workflow.thread,
				message: workflow.message,
				prompt: {
					text: null,
					target: "id" in workflow.subject ? workflow.subject.id : workflow.input
				},
				answer: null,
				status: "open",
				end: null,
				next_actor: refused ? "user" : "agent"
			});
			return {
				...workflow,
				obligation: id
			};
		}),
		records
	};
}
const onUserRank = (item) => item.kind === "todo" ? 1 : item.kind === "update" ? 2 : 0;
const namesRecord = (item) => item.kind !== "todo" || item.owner === "user";
function widgetIndex(root) {
	const projection = root.effective.projection;
	const byWidget = /* @__PURE__ */ new Map();
	const group = (widget) => {
		let entries = byWidget.get(widget);
		if (!entries) byWidget.set(widget, entries = {
			classified: [],
			desired: [],
			undo: []
		});
		return entries;
	};
	for (const entry of projection.classified.values()) if (!entry.terminal && entry.e.kind === "action") group(entry.e.widget).classified.push(entry);
	for (const entry of projection.actions.values()) group(entry.e.widget).desired.push(entry);
	for (const { event } of root.effective.view?.undo ?? []) if (event.kind === "action" && !projection.pendingWithdrawals.has(event.id)) group(event.widget).undo.push(event);
	const heldBy = /* @__PURE__ */ new Map();
	for (const thread of root.effective.thread.all) if (!thread.resolved && !thread.root.pending && thread.root.holds && !heldBy.has(thread.root.holds)) heldBy.set(thread.root.holds, thread.id);
	return {
		byWidget,
		heldBy
	};
}
const NO_ENTRIES = {
	classified: [],
	desired: [],
	undo: []
};
function widgetInputs(root, index, { id, tag }) {
	return {
		registered: root.document.descriptors.get(id),
		states: root.document.registry.$states[tag],
		current: root.effective.widgets.get(id),
		memberships: root.effective.memberships.get(id),
		authored: root.document.authored.get(id),
		hostAvailable: root.effective.hostAvailable,
		ready: root.phase === "ready",
		entries: index.byWidget.get(id) ?? NO_ENTRIES,
		heldBy: index.heldBy.get(id) ?? null
	};
}
function widgetReading(inputs, descriptor) {
	const currentDescriptor = JSON.stringify(inputs.registered) === JSON.stringify(descriptor);
	const current = currentDescriptor ? inputs.current : void 0;
	const authored = currentDescriptor ? inputs.authored?.state : void 0;
	const classified = inputs.entries.classified.toSorted((left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0));
	const actionSpecs = descriptor.declaration["x-state"] ?? {};
	const states = inputs.states ?? {};
	const desired = inputs.entries.desired;
	const durableUndo = inputs.entries.undo;
	const localUndo = desired.map(({ e }) => e).filter((event) => String(event.id).startsWith(PENDING));
	const actions = Object.fromEntries(Object.entries(actionSpecs).filter(([verb]) => states[verb]?.writer === "user").map(([verb]) => [verb, {
		available: currentDescriptor && inputs.hostAvailable && inputs.ready && !descriptor.quoted,
		unavailable: inputs.hostAvailable ? null : "no agent or server is available",
		history: classified.filter(({ e }) => e.action === verb).map(({ e }) => e),
		inForce: desired.filter(({ e }) => e.action === verb).map(({ e, unit, value }) => ({
			event: e,
			unit,
			value
		})),
		undo: inputs.hostAvailable ? [...localUndo, ...durableUndo].filter((event) => event.action === verb) : []
	}]));
	const provenanceEntries = current?.entries ?? [];
	const provenance = Object.fromEntries(provenanceEntries.map(({ e, unit, value }) => [`${e.action}:${unit}`, {
		event: e,
		unit,
		value
	}]));
	return {
		authored: authored ?? {},
		state: current?.state ?? {},
		memberships: currentDescriptor ? inputs.memberships ?? {} : {},
		thread: { heldBy: inputs.heldBy },
		provenance,
		actions
	};
}
function createSemanticApplication({ presentation } = {}) {
	const initial = {
		document: {
			revision: null,
			registry: { $states: {} },
			authored: /* @__PURE__ */ new Map(),
			descriptors: /* @__PURE__ */ new Map()
		},
		authoritative: null,
		unresolved: [],
		settled: [],
		markingRead: [],
		phase: "waiting",
		reach: { reach: "waiting" },
		hostAvailable: true,
		data: {
			version: null,
			sources: {}
		},
		outputs: {},
		effective: derive({
			revision: null,
			registry: { $states: {} },
			authored: /* @__PURE__ */ new Map(),
			descriptors: /* @__PURE__ */ new Map()
		}, null, [], [], [], "waiting", true),
		semanticEpoch: 0
	};
	const publisher = createApplicationPublisher(initial);
	const widgets = publisher.select(widgetIndex);
	let dataTaken = -Infinity;
	let order = 0;
	const drawn = /* @__PURE__ */ new Set();
	let publicationDepth = 0;
	let activePresentation = null;
	if (presentation) presentation.seal(presentation.begin());
	function derive(document, state, unresolved, settled, markingRead, phase, hostAvailable) {
		const receipts = state?.browser.receipts ?? [];
		const local = unresolved.filter((entry) => DRAWN_LOCALLY.has(entry.state));
		const refused = unresolved.filter((entry) => entry.state === "refused");
		const served = state?.browser.views[String(document.revision)];
		const view = served ? (({ basis: _basis, ...rest }) => rest)(served) : null;
		const admitted = normalizedProjection(view);
		const classifiedIds = new Set(admitted.entries.map(({ e }) => e.id));
		const drawsAction = (e) => {
			const descriptor = document.descriptors.get(e.widget);
			const state = descriptor && stampedState(document.registry, descriptor.tag, e);
			return Boolean(state && sameStateDefinition(e.meaning?.state, state.definition));
		};
		const localProjections = local.flatMap((entry) => {
			const projection = entry.projection;
			if (!projection) return [];
			if (projection.kind !== "undo") return drawsAction(projection.e) ? [projection] : [];
			const { target } = projection;
			const targetId = admittedId(entry.undoTarget, unresolved, receipts);
			const pending = !Number.isInteger(target.e.seq);
			return classifiedIds.has(targetId ?? target.e.id) || pending && drawsAction(target.e) ? [{
				...projection,
				targetId
			}] : [];
		});
		const projection = foldProjection({
			...admitted,
			pendingEntries: localProjections
		});
		const ready = phase === "ready";
		const gestures = local.flatMap(({ event, thread, namedParent }) => thread ? [thread] : event.kind === "resolve" || event.kind === "unresolve" ? [{
			...event,
			...namedParent ? { localParent: namedParent } : {}
		}] : event.kind === "undo" ? [event] : []);
		const folded = foldThreads(view?.thread.threads ?? [], gestures);
		const widgets = foldWidgetStates(document.authored, projection);
		const { parents: widgetParents, memberships } = currentWidgetRelations(document, widgets, projection);
		const todos = ready ? localTodos(state, local) : {
			open: [],
			ended: []
		};
		const servedItems = ready ? normalizedObligations(view, widgets, document, projection, todos) : NO_OBLIGATIONS;
		const named = threadNames(folded);
		const threadOfEntry = ({ event, thread: drawn, namedParent }) => {
			const drawnIn = drawn && named.get(drawn.id)?.id;
			if (drawnIn) return drawnIn;
			switch (event.kind) {
				case "comment": return drawn?.id ?? null;
				case "reply": return named.get(event.parent)?.id ?? event.parent;
				case "edit": return named.get(event.message)?.id ?? null;
				case "resolve":
				case "unresolve": return named.get(event.parent)?.id ?? (namedParent ? named.get(namedParent)?.id : null) ?? null;
				case "action": {
					const held = document.descriptors.get(event.widget)?.document;
					return held?.kind === "thread" ? held.thread ?? null : null;
				}
				default: return null;
			}
		};
		const logged = state?.browser.thread_memberships ?? {};
		const threadsOfEntry = (entry) => {
			const filed = entry.admitted ? logged[entry.admitted.id] : void 0;
			if (filed) return filed;
			const { event } = entry;
			if (event.kind === "undo") {
				const target = unresolved.find((each) => each.localId === event.undoes || each.admitted?.id === event.undoes);
				return target ? threadsOfEntry(target) : logged[event.undoes] ?? [];
			}
			const thread = threadOfEntry(entry);
			return thread ? [thread] : [];
		};
		const recovery = /* @__PURE__ */ new Map();
		for (const entry of refused) {
			if (!isTurnEvent(entry.event) && entry.event.kind !== "action") continue;
			const thread = threadOfEntry(entry);
			if (thread) recovery.set(thread, `rejected:${entry.event.attempt}`);
		}
		const obligated = folded.map((thread) => {
			const retry = recovery.get(thread.id);
			return retry && thread.attention?.kind !== "needs_user" ? {
				...thread,
				attention: {
					kind: "needs_user",
					reason: "resend",
					workflow: retry
				}
			} : thread;
		});
		const localWorkflow = (entry, rejected) => {
			const turn = isTurnEvent(entry.event) ? entry.thread : null;
			const thread = threadOfEntry(entry);
			const subject = turn && thread !== null ? {
				kind: "thread",
				id: thread
			} : entry.event.kind === "action" ? {
				kind: "widget",
				id: entry.event.widget
			} : null;
			if (!subject) return null;
			const common = {
				id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
				seq: entry.order,
				input: turn?.id ?? entry.localId,
				message: turn ? turnMessage(turn) : null,
				thread,
				at_work: false,
				coordinate: turn ? ["thread", thread] : entry.projection ? coordinateOf(entry.projection.coordinate) : null,
				obligation: null,
				stage: "sending",
				ts: turn?.ts ?? null,
				detail: null,
				detail_seq: null,
				agent: null,
				session: null,
				delivery_seq: null,
				delivery_session: null,
				delivery_turn: null,
				response: null,
				activity: [],
				condition: rejected ? {
					kind: "failed",
					operation: "delivery"
				} : null,
				started_by: []
			};
			if (entry.event.kind === "action") return {
				...common,
				subject: {
					kind: "widget",
					id: entry.event.widget
				},
				revision: entry.event.revision
			};
			return {
				...common,
				subject: {
					kind: "thread",
					id: subject.id
				},
				revision: entry.event.revision ?? document.revision
			};
		};
		const sends = localUpdates([
			...state ? state.workflows : [],
			...local.flatMap((entry) => isTurnEvent(entry.event) ? localWorkflow(entry, false) ?? [] : []),
			...refused.flatMap((entry) => localWorkflow(entry, true) ?? [])
		]);
		const workflows = sends.workflows;
		const localRecords = ready ? sends.records : [];
		const items = {
			all: [...servedItems.all, ...localRecords],
			user: [...servedItems.user, ...localRecords.filter((item) => item.next_actor === "user")],
			unanswered: [...servedItems.unanswered, ...localRecords]
		};
		const threads = readThreadRecords(obligated, document, widgets, workflows, todos.open, items.all, markingRead, ready);
		const selectedQueues = localQueues(ready ? view?.queues ?? NO_QUEUES : NO_QUEUES, workflows, todos, items, localRecords);
		const serving = /* @__PURE__ */ new Map();
		for (const workflow of workflows) if (workflow.obligation !== null && !serving.has(workflow.obligation)) serving.set(workflow.obligation, workflow);
		const contextual = (items, onUser = false) => items.map((item) => ({
			...item,
			workflow: serving.get(item.id) ?? null,
			offers: queueOffers(item, ready, onUser)
		}));
		return {
			hostAvailable,
			projection,
			widgets,
			thread: {
				all: threads,
				collection: {
					phase,
					threads: threads.filter(discussed)
				},
				gestured: [...new Set([...unresolved, ...settled].flatMap(threadsOfEntry))]
			},
			obligations: {
				phase,
				...items
			},
			plan: ready ? state?.browser.plan ?? null : null,
			queues: {
				phase,
				on_user: contextual(selectedQueues.on_user, true),
				on_agent: contextual(selectedQueues.on_agent),
				done: contextual(selectedQueues.done)
			},
			view,
			memberships,
			widgetParents,
			sending: unresolved.filter((entry) => SENDING.has(entry.state)).map((entry) => entry.event.attempt),
			workflows,
			activity: state?.activity ?? null
		};
	}
	function publish(changes) {
		const prior = publisher.peek();
		const next = {
			...prior,
			...changes
		};
		next.effective = share(prior.effective, derive(next.document, next.authoritative, next.unresolved, next.settled, next.markingRead, next.phase, next.hostAvailable));
		next.data = share(prior.data, next.data);
		next.outputs = share(prior.outputs, next.outputs);
		next.semanticEpoch = prior.semanticEpoch + Number(next.effective !== prior.effective || next.data !== prior.data || next.outputs !== prior.outputs || next.phase !== prior.phase || next.document.revision !== prior.document.revision);
		if (presentation) activePresentation = presentation.begin();
		publicationDepth += 1;
		try {
			return publisher.publish(next);
		} finally {
			publicationDepth -= 1;
			if (presentation && publicationDepth === 0 && activePresentation) {
				const current = activePresentation;
				activePresentation = null;
				presentation.seal(current);
			}
		}
	}
	const overtaken = (state) => {
		const prior = publisher.peek().authoritative;
		return Boolean(prior && (state.taken < prior.taken || state.browser.basis.through_seq < prior.browser.basis.through_seq || state.active.revision < prior.active.revision));
	};
	const adoptable = (state, candidate) => {
		const prior = publisher.peek();
		if (overtaken(state)) return false;
		const revision = typeof candidate === "number" ? candidate : candidate?.revision ?? prior.document.revision;
		const view = state.browser.views[String(revision)];
		return Boolean(view && view.basis.revision === revision && view.basis.through_seq === state.browser.basis.through_seq);
	};
	const unresolvedPart = publisher.select((root) => root.unresolved);
	const receiptsPart = publisher.select((root) => root.authoritative?.browser.receipts ?? []);
	const widgetsPart = publisher.select((root) => root.effective.widgets);
	const entry = (attempt) => unresolvedPart.read().find((item) => item.event.attempt === attempt);
	const ledgerAndReceipts = () => [unresolvedPart.read(), receiptsPart.read()];
	const update = (attempt, change) => publish({ unresolved: publisher.peek().unresolved.map((item) => item.event.attempt === attempt ? change(item) : item) });
	const transition = (signal, admitted) => {
		const left = [];
		let moved = false;
		return {
			unresolved: publisher.peek().unresolved.flatMap((item) => {
				if (!admitted.has(item.event.attempt)) return [item];
				const event = admitted.get(item.event.attempt) ?? null;
				const next = advance(item, signal, event);
				if (next !== item) moved = true;
				if (!next) left.push({
					...item,
					admitted: item.admitted ?? event
				});
				return next ? [next] : [];
			}),
			left,
			moved
		};
	};
	const byAttempt = (receipts) => new Map(receipts.flatMap((receipt) => receipt.attempt ? [[receipt.attempt, receipt]] : []));
	return Object.freeze({
		read: publisher.read,
		select: publisher.select,
		publishing: () => publicationDepth > 0,
		projectView(view) {
			return foldProjection({
				...normalizedProjection(view),
				pendingEntries: []
			});
		},
		selectWidgets(eventIds = null) {
			if (eventIds === null) return widgetsPart.read();
			const wanted = new Set(eventIds);
			return publisher.select((root) => foldWidgetStates(root.document.authored, {
				...root.effective.projection,
				desired: new Map([...root.effective.projection.desired].filter(([, entry]) => wanted.has(entry.e.id)))
			})).read();
		},
		selectWidget(descriptor) {
			let inputs = null;
			let reading;
			return publisher.select((root) => {
				const next = widgetInputs(root, widgets.read(), descriptor);
				const keys = Object.keys(next);
				const prior = inputs;
				if (prior && keys.every((key) => next[key] === prior[key])) return reading;
				inputs = next;
				return reading = widgetReading(next, descriptor);
			});
		},
		entry,
		identify(revision, stamp = null, live = false) {
			return publish({ document: {
				...publisher.peek().document,
				revision,
				stamp,
				live
			} });
		},
		setHostAvailable(hostAvailable) {
			return publish({ hostAvailable });
		},
		markRead(items) {
			return publish({ markingRead: [...publisher.peek().markingRead, ...items] });
		},
		settleMarkRead(items) {
			return publish({ markingRead: publisher.peek().markingRead.filter((item) => !items.some((done) => done.message === item.message && done.version === item.version)) });
		},
		captureDocument(document) {
			if (publisher.peek().authoritative) throw new Error("an admitted document changes only through adopt");
			return publish({ document });
		},
		setPhase(phase) {
			return publish({ phase });
		},
		setReach(reach) {
			const now = publisher.peek();
			if (now.reach.reach === reach.reach && now.reach.fault === reach.fault) return now;
			return publish({ reach });
		},
		publishOutput(widget, output, reading) {
			const prior = publisher.peek();
			const values = { ...prior.outputs[widget] };
			if (reading === null) delete values[output];
			else values[output] = reading;
			const outputs = { ...prior.outputs };
			if (Object.keys(values).length) outputs[widget] = values;
			else delete outputs[widget];
			if (share(prior.outputs, outputs) === prior.outputs) return prior;
			return publish({ outputs });
		},
		acceptData(data, taken) {
			if (taken < dataTaken) return false;
			dataTaken = taken;
			if (data.version === publisher.peek().data.version) return false;
			publish({ data });
			return true;
		},
		canAdopt(state, document = null) {
			return adoptable(state, document);
		},
		overtaken,
		adopt(state, document = null) {
			const prior = publisher.peek();
			if (!adoptable(state, document)) return false;
			const authoritative = state;
			const { unresolved, left } = transition("log", byAttempt(authoritative.browser.receipts));
			const settled = [...prior.settled.filter((item) => !drawn.has(item.event.attempt)), ...left];
			for (const attempt of drawn) if (!unresolved.some((item) => item.event.attempt === attempt)) drawn.delete(attempt);
			publish({
				document: document ?? prior.document,
				authoritative,
				unresolved,
				settled,
				phase: "ready",
				reach: { reach: "reached" }
			});
			return true;
		},
		enqueue(event, timestamp, plainText = event.text ?? event.token ?? "") {
			if (entry(event.attempt)) return null;
			const before = publisher.peek();
			const localId = PENDING + event.attempt;
			const thread = isThreadEvent(event) ? {
				...threadForAttempt(event, timestamp),
				plainText
			} : event.kind === "edit" ? editForAttempt(event, timestamp) : null;
			const undoTarget = event.kind === "undo" ? before.unresolved.find((item) => item.localId === event.undoes) : null;
			const localTarget = undoTarget?.projection;
			const target = event.kind === "undo" ? (localTarget?.kind !== "undo" ? localTarget : null) ?? before.effective.projection.classified.get(event.undoes) : null;
			const widget = event.kind === "action" ? before.document.authored.get(event.widget) : null;
			const declaration = event.kind === "action" ? before.document.descriptors.get(event.widget)?.declaration : null;
			const spec = event.kind === "action" && widget ? declaration?.["x-state"]?.[event.action] : null;
			const unit = event.kind === "action" && spec ? spec.unit === "widget" ? event.widget : event.detail[spec.unit] : null;
			const localOrder = ++order;
			const projection = event.kind === "undo" && target && isProjectionEntry(target) && target.e.kind === "action" ? {
				kind: "undo",
				target,
				coordinate: target.coordinate,
				localOrder
			} : event.kind === "action" && widget && spec && typeof unit === "string" ? {
				unit,
				spec,
				coordinate: stateCoordinate(event.widget, unit, event.action),
				localOrder,
				e: {
					...event,
					id: localId,
					meaning: { state: before.document.registry.$states[widget.tag]?.[event.action]?.definition }
				},
				value: spec.record ? foldedValue(event, spec.record) : event.action
			} : null;
			publish({ unresolved: [...before.unresolved, {
				event: structuredClone(event),
				localId,
				timestamp,
				order: localOrder,
				projection,
				thread,
				undoTarget: undoTarget?.event.attempt ?? null,
				state: "sending",
				admitted: null
			}] });
			return entry(event.attempt);
		},
		accept(attempt, accepted) {
			if (!entry(attempt)) return;
			const { unresolved, left } = transition("accept", /* @__PURE__ */ new Map([[attempt, accepted]]));
			const settled = left.filter((item) => !drawn.delete(item.event.attempt));
			publish({
				unresolved,
				...settled.length && { settled: [...publisher.peek().settled, ...settled] }
			});
		},
		refuse(attempt) {
			const refused = entry(attempt);
			if (!refused) return [];
			const ledger = publisher.peek().unresolved;
			const gone = [refused.localId];
			const dependents = [];
			for (let grew = true; grew;) {
				grew = false;
				for (const item of ledger) if (item.event.attempt !== attempt && !dependents.includes(item.event.attempt) && gone.some((id) => namesEvent(item.event, id))) {
					dependents.push(item.event.attempt);
					gone.push(item.localId);
					grew = true;
				}
			}
			const { unresolved } = transition("refuse", /* @__PURE__ */ new Map([[attempt, null]]));
			publish({ unresolved: unresolved.filter((item) => !dependents.includes(item.event.attempt)) });
			return dependents;
		},
		present(receipts) {
			const { unresolved, settled } = publisher.peek();
			const attempts = byAttempt(receipts);
			for (const item of [...settled, ...unresolved]) if (attempts.has(item.event.attempt)) drawn.add(item.event.attempt);
			const { unresolved: next, moved } = transition("present", attempts);
			if (moved) publish({ unresolved: next });
		},
		unpresented: () => unresolvedPart.read().filter((item) => UNPRESENTED.has(item.state)),
		releasable: () => unresolvedPart.read().filter((item) => RELEASABLE.has(item.state)),
		release(attempts) {
			return publish({ unresolved: publisher.peek().unresolved.filter((item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state))) });
		},
		nameEvents(attempt) {
			const item = entry(attempt);
			if (!item) return true;
			const event = nameAdmitted(item.event, (pending) => admittedId(pending, ...ledgerAndReceipts()));
			if (event !== item.event) update(attempt, (item) => ({
				...item,
				...event.parent !== item.event.parent && typeof item.event.parent === "string" ? { namedParent: item.event.parent } : {},
				event
			}));
			return !(event.kind === "undo" && namesPending(event));
		}
	});
}

//#endregion
//#region runtime/framework/presentation.js
function createPresentationCoordinator({ reportFailure }) {
	const changes = Z(0);
	let wake = Promise.withResolvers();
	let publication = null;
	let sealed = false;
	const regions = /* @__PURE__ */ new Map();
	const pending = (wanted = regions.keys()) => [...wanted].filter((key) => {
		const record = regions.get(key);
		return record && !record.complete;
	});
	function changed() {
		const previous = wake;
		wake = Promise.withResolvers();
		previous.resolve();
		changes.value = changes.peek() + 1;
	}
	function begin() {
		for (const [region, record] of regions) if (!record.active) regions.delete(region);
		publication = Object.freeze({});
		sealed = false;
		changed();
		return publication;
	}
	function seal(value) {
		if (value !== publication) return false;
		sealed = true;
		changed();
		return true;
	}
	function attach(region) {
		if (!publication) throw new Error("begin a presentation publication before attaching a renderer");
		const record = {
			complete: false,
			active: true,
			latest: null,
			release: null
		};
		regions.set(region, record);
		const active = () => record.active && regions.get(region) === record;
		changed();
		function present(failSoft) {
			const completion = Promise.withResolvers();
			const previous = record.release;
			record.release = () => queueMicrotask(() => completion.resolve(void 0));
			const ticket = {};
			if (active()) {
				record.latest = ticket;
				record.complete = false;
				changed();
			}
			const current = () => active() && record.latest === ticket;
			const ready = (async () => {
				try {
					await completion.promise;
				} catch (reason) {
					if (!active()) return;
					let recovered = false;
					let failure = reason;
					if (failSoft) try {
						failSoft(reason);
						recovered = true;
					} catch (fallbackError) {
						if (fallbackError !== reason) failure = new AggregateError([reason, fallbackError], "presentation and fail-soft failed");
					}
					reportFailure(failure);
					if (!current()) return;
					if (!recovered) throw failure;
				}
				if (current()) {
					record.complete = true;
					changed();
				}
			})();
			ready.catch(() => {});
			previous?.();
			return Object.freeze({
				resolve: completion.resolve,
				reject: completion.reject,
				ready
			});
		}
		function disconnect() {
			record.release?.();
			record.release = null;
			if (!active()) return;
			if (!sealed || pending().length) record.complete = false;
			record.active = false;
			queueMicrotask(() => {
				if (regions.get(region) !== record) return;
				regions.delete(region);
				changed();
			});
		}
		return Object.freeze({
			present,
			disconnect
		});
	}
	const currentRegionsPresented = (wanted) => sealed && !pending(wanted).length;
	const currentPresented = () => currentRegionsPresented();
	const whenCurrentPresented = () => whenCurrentRegionsPresented();
	async function whenCurrentRegionsPresented(wanted, current = () => true) {
		await Promise.resolve();
		for (;;) {
			const next = wake.promise;
			if (!current()) return "superseded";
			if (currentRegionsPresented(wanted)) return "presented";
			await next;
		}
	}
	function read() {
		return Object.freeze({
			sealed,
			pending: Object.freeze(pending())
		});
	}
	return Object.freeze({
		begin,
		seal,
		attach,
		whenCurrentPresented,
		currentPresented,
		whenCurrentRegionsPresented,
		currentRegionsPresented,
		read,
		subscribe: (callback) => changes.subscribe(() => d(() => {
			try {
				callback();
			} catch (reason) {
				reportFailure(reason);
			}
		}))
	});
}
function createPresentationSchedule(bindJob) {
	let queued = [];
	let running = [];
	let scheduled = false;
	let settling = false;
	let pass = null;
	function open() {
		if (pass) return;
		pass = Promise.withResolvers();
		pass.promise.catch(() => void 0);
	}
	function collect(after, run, retired) {
		open();
		const paint = bindJob(run);
		queued.push(async () => {
			let dependencies = after?.() ?? [];
			while (dependencies.length && (!retired || retired.current())) {
				const settled = Promise.allSettled(dependencies);
				await (retired ? Promise.race([settled, retired.ready]) : settled);
				const latest = after?.() ?? [];
				if (latest.every((dependency) => dependencies.includes(dependency))) break;
				dependencies = latest;
			}
			return paint();
		});
		if (scheduled) return;
		scheduled = true;
		queueMicrotask(() => {
			scheduled = false;
			const round = queued;
			queued = [];
			for (const run of round) {
				const started = run();
				started.catch(() => void 0);
				running.push(started);
			}
			drain();
		});
	}
	async function drain() {
		if (settling) return;
		settling = true;
		let failure = null;
		let failed = false;
		while (running.length || queued.length || scheduled) {
			const started = running;
			running = [];
			for (const outcome of await Promise.allSettled(started)) if (outcome.status === "rejected" && !failed) {
				failed = true;
				failure = outcome.reason;
			}
		}
		settling = false;
		const finished = pass;
		pass = null;
		if (failed) finished.reject(failure);
		else finished.resolve();
	}
	const passed = () => pass?.promise ?? Promise.resolve();
	function enqueue(after, run, committed) {
		const completion = Promise.withResolvers();
		const dom = Promise.withResolvers();
		collect(after, async () => {
			try {
				await run();
				completion.resolve();
				await committed();
				dom.resolve();
			} catch (error) {
				completion.reject(error);
				dom.reject(error);
				throw error;
			}
		});
		return Object.freeze({
			ready: completion.promise,
			committed: dom.promise
		});
	}
	function presenter({ attach, paint, failSoft, after }) {
		let handle = null;
		let generation = 0;
		let dom = Promise.withResolvers();
		dom.resolve();
		function claim(value) {
			const claimed = ++generation;
			handle ??= attach();
			const previous = dom;
			dom = Promise.withResolvers();
			previous.resolve();
			return {
				claimed,
				value,
				dom,
				presentation: handle.present(failSoft)
			};
		}
		async function run({ claimed, value, presentation, dom }) {
			if (claimed !== generation) return;
			let painted;
			try {
				painted = paint(value, () => claimed === generation);
			} catch (error) {
				painted = Promise.reject(error);
			}
			dom.resolve();
			presentation.resolve(painted);
			await presentation.ready;
		}
		function sync(value) {
			const ticket = claim(value);
			collect(after, () => run(ticket), {
				ready: ticket.dom.promise,
				current: () => ticket.claimed === generation
			});
			return passed();
		}
		function disconnect() {
			generation += 1;
			dom.resolve();
			handle?.disconnect();
			handle = null;
		}
		return Object.freeze({
			sync,
			committed: () => dom.promise,
			disconnect
		});
	}
	return Object.freeze({
		presenter,
		enqueue,
		passed
	});
}

//#endregion
//#region runtime/version-signal.js
const tick = (version) => {
	version.value = version.peek() + 1;
};

//#endregion
//#region runtime/semantic-state.js
let reportPresentationFailure = (reason) => console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({ reportFailure: (reason) => reportPresentationFailure(reason) });
const schedule = createPresentationSchedule(bindQueuedWork);
const applicationState = createSemanticApplication({ presentation });
const readApplication = applicationState.read;
const readPart = (derive) => applicationState.select(derive).read;
const agent = readPart((root) => root.authoritative?.agent ?? null);
const agentName = () => agent() || "the agent";
const pageClaimed = readPart((root) => root.authoritative?.claim_session != null);
const projectView = applicationState.projectView;
const selectWidgets = applicationState.selectWidgets;
const attachApplicationPresentation = (region) => presentation.attach(region);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) => ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
const attachWidgetPresentation = (widget, kind) => presentation.attach(widgetRegion(widget, kind));
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
const applicationPresenter = ({ region, after, reading, paint, failSoft }) => {
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
		attach: () => presentation.attach(region),
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
		tick(revision);
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
		disconnect,
		committed: presenter.committed
	});
};
const documentChanges = Z(0);
const documentChanged = () => documentChanges.value;
const presentDocument = () => W(() => {
	tick(documentChanges);
	for (const present of documentPresenters) present();
	return schedule.passed();
});
const whenDocumentPresented = () => schedule.passed();
const whenApplicationPresented = () => presentation.whenCurrentPresented();
const applicationPresented = () => presentation.currentPresented();
const whenWidgetsPresented = (widgets) => presentation.whenCurrentRegionsPresented(widgets.flatMap(widgetRegions));
const whenApplicationRegionsPresented = (regions, current) => presentation.whenCurrentRegionsPresented(regions, current);
const applicationRegionsPresented = (regions) => presentation.currentRegionsPresented(regions);
const projectionRegionsPresented = (widgets) => applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
const watchPresentation = presentation.subscribe;
const readApplicationPresentation = presentation.read;
function setPresentationFailureReporter(report) {
	reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
const watchSemantic = (callback) => applicationState.select((root) => root.semanticEpoch).subscribe(() => callback(readApplication()));

//#endregion
//#region runtime/context.js
var context_exports = /* @__PURE__ */ __exportAll({
	DELIVERY: () => DELIVERY,
	LIVE_ROOT: () => LIVE_ROOT,
	PAGE_ROOT: () => PAGE_ROOT,
	SHARE_ROOT: () => SHARE_ROOT,
	WEBSITE_DELIVERY: () => WEBSITE_DELIVERY,
	annotationMode: () => annotationMode,
	layerRoot: () => layerRoot,
	offlineData: () => offlineData,
	offlineInteractive: () => offlineInteractive,
	offlineState: () => offlineState,
	pageUrl: () => pageUrl,
	revisionLabel: () => revisionLabel,
	runtime: () => runtime,
	runtimeModule: () => runtimeModule,
	runtimeResource: () => runtimeResource,
	shareUrl: () => shareUrl
});
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
const layerRoot = (doc) => {
	return doc.querySelector("script[data-lf-runtime][data-lf-entry]")?.dataset.lfEntry?.replace(/leaf\.js$/, "") ?? "";
};
const SHARE_ROOT = served?.dataset.lfShareUrl;
function shareUrl(root) {
	const url = new URL(root);
	url.pathname = location.pathname;
	const access = [...url.searchParams];
	url.search = location.search;
	for (const [key, value] of access) url.searchParams.set(key, value);
	url.hash = location.hash;
	return url.href;
}
const pageUrl = (path) => new URL(path, PAGE_ROOT ?? void 0).href;
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
	revisionLabels: readPart((root) => root.authoritative?.revision_labels),
	seen: readPart((root) => root.authoritative?.seen ?? null)
};
const shownActive = () => {
	const active = part.active();
	return active && part.revision() === active.revision ? active : null;
};
const runtime = {
	get active() {
		return part.active();
	},
	get browser() {
		return part.browser();
	},
	get showsActive() {
		return shownActive() !== null;
	},
	get currentLabel() {
		const active = part.live() ? shownActive() : null;
		return active ? active.label : runtime.currentStamp === null ? null : `v${runtime.currentStamp}`;
	},
	get currentRevision() {
		return part.revision();
	},
	get currentStamp() {
		const active = part.live() ? shownActive() : null;
		return active ? active.version : part.stamp();
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
	get seen() {
		return part.seen();
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
const revisionLabel = (revision) => part.revisionLabels()?.[revision];

//#endregion
//#region runtime/registry.js
const registry = runtime.registry;
const tokenEntry = (name) => registry.$reactions?.tokens[name];
const elementDeclarations = () => Object.entries(registry).filter(([tag]) => isElementName(tag));
function adoptRegistry(declarations) {
	for (const [name, value] of Object.entries(declarations)) if (name.startsWith("$")) freeze(value);
	Object.assign(registry, declarations);
	if (declarations.$languages) installLanguagePaths(declarations.$languages.paths);
}
function freeze(value) {
	if (value === null || typeof value !== "object" || Object.isFrozen(value)) return;
	for (const child of Object.values(value)) freeze(child);
	Object.freeze(value);
}
let stateIndex;
const recordSlot = (record) => JSON.stringify([record.kind, "attr" in record ? record.attr : null]);
function indexedState() {
	const generation = registry.$layer?.generation;
	if (typeof generation !== "string" || !generation) throw new Error("leaf: state vocabulary requested before registry loaded");
	if (stateIndex?.generation === generation) return stateIndex;
	const specs = [];
	for (const [tag, entry] of elementDeclarations()) for (const [verb, spec] of Object.entries(entry["x-state"] ?? {})) specs.push({
		tag,
		verb,
		spec
	});
	const recordTags = /* @__PURE__ */ new Map();
	for (const { tag, spec } of specs) {
		if (!spec.record) continue;
		const slot = recordSlot(spec.record);
		const tags = recordTags.get(slot) ?? /* @__PURE__ */ new Set();
		tags.add(tag);
		recordTags.set(slot, tags);
	}
	stateIndex = {
		generation,
		recordSelectors: new Map([...recordTags].map(([slot, tags]) => [slot, [...tags].join(",")])),
		specs
	};
	return stateIndex;
}
const stateSpecs = () => indexedState().specs;
const recordedWidgetSelector = (record) => indexedState().recordSelectors.get(recordSlot(record)) ?? "";
const layerFact = (name) => registry[name];
const declarationFor = (el, key) => el ? registry[el.localName]?.[key] : void 0;
const decisionFor = (tag) => registry.$decisions[tag] ?? null;
const elementsDeclaring = (root, key, { direct = false } = {}) => {
	return (direct ? [...root.children] : [...root.querySelectorAll("*")]).filter((el) => declarationFor(el, key) !== void 0);
};
const tagsDeclaring = (holds) => elementDeclarations().filter(([, entry]) => holds(entry)).map(([tag]) => tag);
const matchesWhen = (el, when) => Object.entries(when ?? {}).every(([attr, values]) => values.some((value) => typeof value === "boolean" ? el.hasAttribute(attr) === value : el.getAttribute(attr) === value));
const exhibits = (el, entry) => {
	const rule = entry?.["x-exhibit"];
	return typeof rule === "object" && rule !== null ? matchesWhen(el, rule.when) : !!rule;
};

//#endregion
//#region runtime/shadow.js
const refusedRoots = /* @__PURE__ */ new WeakSet();
const refuseShadowRoot = (root) => refusedRoots.add(root);
const declaredRoot = (host) => host.shadowRoot && registry[host.localName]?.["x-shadow"] && isStage(host.shadowRoot) && !refusedRoots.has(host.shadowRoot) ? host.shadowRoot : null;
const shadowRootsIn = (root) => liveStages().filter((stage) => root.contains(stage.host) && declaredRoot(stage.host) === stage);
const pageShadowRoots = () => shadowRootsIn(document);
const renderedChildren = (node) => isHTML(node, "slot") ? node.assignedNodes({ flatten: true }) : (isElement(node) ? node.shadowRoot ?? node : node).childNodes;
const hostIn = (node, root) => {
	let at = node;
	while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
	return at;
};
let shadowRules = "";
let loading = null;
function loadShadowRules() {
	loading ??= readShadowRules();
	return loading;
}
async function readShadowRules() {
	const { runtimeResource } = await Promise.resolve().then(() => context_exports);
	const response = await fetch(runtimeResource("/shadow.css"));
	if (!response.ok) throw new Error(`leaf: shadow.css failed to load (${response.status})`);
	shadowRules = await response.text();
}

//#endregion
//#region runtime/native-selection.js
function pageRange(sel) {
	const plain = sel.getRangeAt(0);
	const shadowRoots = pageShadowRoots();
	if (!shadowRoots.length) return plain;
	const [composed] = sel.getComposedRanges({ shadowRoots });
	if (!composed) return plain;
	const { startContainer, startOffset, endContainer, endOffset } = composed;
	if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
	const range = document.createRange();
	range.setStart(startContainer, startOffset);
	range.setEnd(endContainer, endOffset);
	return range;
}
let writtenSelection = null;
let writtenBackward = false;
function selectEnds(anchor, focus) {
	const selection = getSelection();
	if (!selection) return;
	const from = document.createRange(), to = document.createRange();
	from.setStart(...anchor);
	to.setStart(...focus);
	writtenBackward = from.compareBoundaryPoints(Range.START_TO_START, to) > 0;
	selection.setBaseAndExtent(...anchor, ...focus);
	writtenSelection = selectionEnds(selection);
}
const selectionEnds = (selection) => {
	const range = selection.rangeCount ? pageRange(selection) : null;
	return [
		selection.anchorNode,
		selection.anchorOffset,
		selection.focusNode,
		selection.focusOffset,
		range?.startContainer,
		range?.startOffset,
		range?.endContainer,
		range?.endOffset
	];
};
function programmaticSelection(selection) {
	if (!selection) {
		writtenSelection = null;
		return false;
	}
	const written = writtenSelection;
	if (!written) return false;
	if (selectionEnds(selection).every((end, i) => end === written[i])) return true;
	writtenSelection = null;
	return false;
}
function selectionBackward(selection, range = pageRange(selection)) {
	const anchor = selection.anchorNode;
	if (!anchor) return false;
	if (anchor.getRootNode() !== range.commonAncestorContainer.getRootNode()) return programmaticSelection(selection) ? writtenBackward : selection.direction === "backward";
	const probe = document.createRange();
	probe.setStart(anchor, selection.anchorOffset);
	return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}

//#endregion
//#region runtime/keyboard/bindings.js
const MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const GLYPH = {
	Enter: "⏎",
	" ": "space",
	Escape: "esc",
	ArrowUp: "↑",
	ArrowDown: "↓",
	ArrowLeft: "←",
	ArrowRight: "→",
	Home: "home",
	End: "end",
	Tab: "⇥",
	Mod: MAC ? "⌘" : "Ctrl",
	Shift: MAC ? "⇧" : "Shift",
	Alt: MAC ? "⌥" : "Alt"
};
const MODIFIERS = [
	"Mod",
	"Alt",
	"Shift"
];
const parsed = (binding) => {
	const separator = binding.lastIndexOf("+");
	return {
		key: binding.slice(separator + 1),
		mods: separator < 0 ? [] : binding.slice(0, separator).split("+")
	};
};
const spell = (binding) => {
	const { key, mods } = parsed(binding);
	if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key)) return key.toUpperCase();
	return mods.reduceRight((rest, mod) => {
		const glyph = GLYPH[mod] ?? mod;
		return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
	}, GLYPH[key] ?? key);
};
const softKeyboard = () => coarsePointer.matches;
const submitBindings = () => softKeyboard() ? ["Mod+Enter"] : ["Enter", "Mod+Enter"];
const advertisesKeys = () => !coarsePointer.matches;
const spokenBinding = (binding) => {
	const { key, mods } = parsed(binding);
	const spokenModifier = (mod) => {
		if (mod === "Mod") return MAC ? "Command" : "Control";
		return mod;
	};
	const spokenKey = key === " " ? "Space" : key;
	return [...mods.map(spokenModifier), spokenKey].join("+");
};
const word = (cell) => typeof cell === "function" ? cell() : cell;
const declaredBindings = (row) => word(row.keys) ?? [];
const contextBindings = (row) => word(row.contextKeys) ?? [];
const titleOf = (row) => {
	const title = word(row.title);
	if (typeof title !== "string" || !title.trim()) throw new TypeError(`leaf: ${row.id} has no command title; expected non-empty text`);
	return title;
};
const descriptionOf = (row) => word(row.description) ?? "";
const allBindings = (row) => [.../* @__PURE__ */ new Set([
	...declaredBindings(row),
	...contextBindings(row),
	...commandRoutes(row).flatMap(contextBindings)
])];
const commandRoutes = (row) => word(row.routes) ?? [];
const commandBinding = (row, route = null) => route ? route.binding ?? contextBindings(route)[0] : declaredBindings(row)[0] ?? contextBindings(row)[0];
const ROUTED_COMMAND = Symbol("a routed command reference");
const contextualRoute = (route, command) => ({
	...route,
	[ROUTED_COMMAND]: command
});
const routedCommand = (route) => route?.[ROUTED_COMMAND] ?? null;
const quickShortcuts = () => window.lfKeyboard.quick;
const setQuickShortcuts = (on) => window.lfKeyboard.setQuick(on);
const bindingEnabledFor = (binding, quick) => {
	const { key, mods } = parsed(binding);
	return quick || key.length !== 1 || key === " " || mods.some((mod) => mod !== "Shift");
};
const bindingEnabled = (binding) => bindingEnabledFor(binding, quickShortcuts());
const bindings = (row) => declaredBindings(row).filter(bindingEnabled);
const commandEntries = (row, active = bindings(row), { includeUnavailable = false } = {}) => {
	const routes = commandRoutes(row);
	if (!routes.length) return includeUnavailable || commandAvailable(row) ? [{
		id: row.id,
		binding: active[0],
		route: null
	}] : [];
	return routes.filter((route) => (includeUnavailable || commandAvailable(row, route)) && (route.binding !== void 0 && active.includes(route.binding) || contextBindings(route).some((binding) => active.includes(binding)))).map((route) => ({
		id: route.id,
		binding: route.binding ?? active.find((binding) => contextBindings(route).includes(binding)),
		route
	}));
};
const commandPresentations = (row, active = bindings(row), options = {}) => {
	if (row.runFromCommandReference === false) return [{
		id: row.id,
		route: null
	}];
	return commandEntries(row, active, options);
};
const labelOf = (row) => {
	const label = word(row.label);
	if (label !== void 0 && label !== null) return label;
	return bindings(row).map(spell).join(" / ");
};
const controlOutputs = /* @__PURE__ */ new WeakMap();
function controlAvailabilityOutput(control, owner, fields = null) {
	let outputs = controlOutputs.get(control);
	if (!fields) {
		outputs?.delete(owner);
		return;
	}
	if (!outputs) controlOutputs.set(control, outputs = /* @__PURE__ */ new Map());
	outputs.set(owner, fields);
}
function disabledByFieldset(control) {
	for (let parent = control.parentElement; parent; parent = parent.parentElement) {
		if (!(parent instanceof HTMLFieldSetElement) || !parent.disabled) continue;
		if (![...parent.children].find((child) => child.localName === "legend")?.contains(control)) return true;
	}
	return false;
}
function controlAvailable(control) {
	if (!control?.isConnected) return false;
	const outputs = [...controlOutputs.get(control)?.values() ?? []];
	const disabled = outputs.some((fields) => fields.disabled) ? disabledByFieldset(control) : control.matches(":disabled");
	const ariaDisabled = !outputs.some((fields) => fields.ariaDisabled) && control.getAttribute("aria-disabled") === "true";
	return !disabled && !ariaDisabled;
}
const declaredCommandAvailable = (row, route = null) => commandReady(row, route) && (!row.when || row.when()) && (!route?.when || route.when());
const scopeReadiness = /* @__PURE__ */ new WeakMap();
const savedReadingSettled = () => runtime.statePhase !== "waiting";
function declareCommandReadiness(rows, ready) {
	if (ready !== void 0 && typeof ready !== "function") throw new TypeError("leaf: scope readiness must be a function");
	if (ready) for (const row of rows) scopeReadiness.set(row, ready);
}
const commandReady = (row, route = null) => {
	const saved = savedReadingSettled();
	if ((row.decision || route?.decision) && !saved) return false;
	const reference = routedCommand(route);
	if (reference) {
		const entry = referencedCommandEntry(reference, { includeUnavailable: true });
		if (entry && !commandReady(reference.row, entry.route)) return false;
	}
	const ready = route?.ready ?? row.ready ?? scopeReadiness.get(row);
	return ready ? ready() : true;
};
const scopeAvailable = (scope) => !commandReady(scope) || !scope.when || scope.when();
const commandAvailable = (row, route = null) => {
	const control = route?.control ?? row.control;
	const reference = routedCommand(route);
	return declaredCommandAvailable(row, route) && (control === void 0 || controlAvailable(word(control))) && (!reference || referencedCommandEntry(reference) !== null);
};
function referencedCommandEntry(reference, options) {
	if (!reference.source.isConnected || !reference.scope.rows.includes(reference.row) || !scopeAvailable(reference.scope)) return null;
	return commandEntries(reference.row, allBindings(reference.row), options).find(({ id, binding }) => id === reference.id && (binding ?? null) === reference.binding) ?? null;
}
const live = (row) => {
	const routes = commandRoutes(row);
	return routes.length ? routes.some((route) => commandAvailable(row, route)) : commandAvailable(row);
};
const availableBindings = (row, declared) => declared.filter((binding) => commandEntries(row, [binding]).length > 0);
const touchPresses = (row) => row.touch ? [{
	id: row.id,
	row,
	binding: void 0,
	words: row.touch
}] : [];
const COMMAND_ID = /^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$/;
const canonicalBinding = (binding) => {
	const { key: declaredKey, mods } = parsed(binding);
	const key = declaredKey === "Space" ? " " : declaredKey;
	const letter = key.length === 1 && key.toLowerCase() !== key.toUpperCase();
	const named = key === " " || key.length > 1;
	const canonicalKey = letter ? key.toLowerCase() : key;
	return [...MODIFIERS.filter((mod) => mods.includes(mod) && (mod !== "Shift" || letter || named)), canonicalKey].join("+");
};
function validateActive(active, where, bindingOf) {
	const owners = /* @__PURE__ */ new Map();
	for (const row of active) for (const binding of bindingOf(row)) {
		const identity = canonicalBinding(binding);
		const prior = owners.get(identity);
		if (prior) throw new Error(`leaf: ${where} has two live meanings for ${binding}: ${titleOf(prior)}; ${titleOf(row)}`);
		owners.set(identity, row);
	}
	return active;
}
const validateRows = (rows, where = "a scope") => {
	const active = rows.filter(live);
	validateActive(active, where, (row) => availableBindings(row, declaredBindings(row)));
	return validateActive(active, where, (row) => availableBindings(row, [...contextBindings(row), ...commandRoutes(row).flatMap(contextBindings)]));
};
function activeRows(rows, where = "a scope") {
	return validateActive(rows.filter((row) => live(row) && bindings(row).length > 0), where, (row) => availableBindings(row, bindings(row)));
}
function decisionControls(commands, where = "an obligation") {
	const controls = /* @__PURE__ */ new Map();
	for (const { source, scope, row } of commands) {
		const routes = commandRoutes(row);
		const candidates = [...row.decision ? [{
			row,
			route: null
		}] : [], ...routes.filter((route) => route.decision).map((route) => ({
			row,
			route
		}))];
		for (const { route } of candidates) {
			const contribution = route ?? row;
			const control = word(contribution.control ?? row.control);
			const label = titleOf(contribution);
			const description = descriptionOf(route?.description !== void 0 ? route : row);
			const bindingBadge = word(contribution.bindingBadge !== void 0 ? contribution.bindingBadge : row.bindingBadge) ?? null;
			const active = route ? [route.binding, ...contextBindings(route)].filter(Boolean) : allBindings(row);
			if (control == null) continue;
			if (!(control instanceof Element)) throw new TypeError(`leaf: ${contribution.id} in ${where} has no control`);
			if (bindingBadge !== null && !(bindingBadge instanceof Element)) throw new TypeError(`leaf: ${contribution.id} in ${where} has no Element binding badge`);
			const binding = active[0] ?? null;
			const record = {
				id: contribution.id,
				source,
				control,
				label,
				description,
				recommended: Boolean(contribution.recommended ?? row.recommended),
				commits: Boolean(contribution.commits ?? row.commits),
				bindingBadge,
				intrinsicBindings: active,
				command: Object.freeze({
					id: contribution.id,
					source,
					scope,
					row,
					binding,
					control
				})
			};
			const prior = controls.get(control);
			if (prior) {
				if (prior.id !== record.id || prior.label !== record.label || prior.bindingBadge !== record.bindingBadge || prior.command.source !== record.command.source || prior.command.scope !== record.command.scope || prior.command.row !== record.command.row) throw new TypeError(`leaf: one control has two Decision commands in ${where}: ${prior.id} and ${record.id}`);
				continue;
			}
			controls.set(control, record);
		}
	}
	return [...controls.values()];
}
const ariaBindings = (binding) => {
	const { key, mods } = parsed(binding);
	return (mods.includes("Mod") ? ["Meta", "Control"] : [null]).map((modKey) => [...mods.map((mod) => mod === "Mod" ? modKey : mod), key === " " ? "Space" : key].filter(Boolean).join("+"));
};
const ariaShortcuts = (rows, current = true, where, includes = () => true) => [...new Set((current ? activeRows(rows, where) : rows).flatMap((row) => bindings(row).filter((binding) => !current || commandEntries(row, [binding]).some((entry) => includes(binding, entry, row))).flatMap(ariaBindings)))].join(" ");
function answers(binding, ev) {
	const { key, mods } = parsed(binding);
	if (mods.includes("Mod") !== (ev.metaKey || ev.ctrlKey)) return false;
	if (mods.includes("Alt") !== ev.altKey) return false;
	const shift = mods.includes("Shift");
	if (key.length === 1 && key.toLowerCase() !== key.toUpperCase()) return ev.key.toLowerCase() === key.toLowerCase() && ev.shiftKey === shift;
	return key === " " || key.length > 1 ? ev.key === key && ev.shiftKey === shift : ev.key === key && (!shift || ev.shiftKey);
}
const declaresCommandHandler = (row, handler) => Boolean(Object.getOwnPropertyDescriptor(row, handler)?.get) || typeof row[handler] === "function";
function checked(rows, where, ready) {
	declareCommandReadiness(rows, ready);
	const ids = /* @__PURE__ */ new Map();
	const named = (command) => {
		if (typeof command.id !== "string" || !COMMAND_ID.test(command.id)) throw new Error(`leaf: ${where} names ${String(command.id)}, which is not a stable command id`);
		const prior = ids.get(command.id);
		if (prior && (!routedCommand(command) || routedCommand(prior) !== routedCommand(command))) throw new Error(`leaf: ${where} declares ${command.id} twice`);
		ids.set(command.id, command);
		if (!(typeof command.title === "function" || typeof command.title === "string" && command.title.trim())) throw new Error(`leaf: ${command.id} has no command title`);
		if (command.description !== void 0 && typeof command.description !== "string" && typeof command.description !== "function") throw new Error(`leaf: ${command.id} has invalid command description`);
		if (command.ready !== void 0 && typeof command.ready !== "function") throw new TypeError(`leaf: ${command.id} readiness must be a function`);
		if (command.decision !== void 0 && typeof command.decision !== "boolean") throw new Error(`leaf: ${command.id} has invalid Decision role; expected a boolean`);
	};
	rows.forEach((row, i) => {
		if (!row) throw new TypeError(`${where}: row ${i + 1} is missing`);
		named(row);
		const declaresRun = declaresCommandHandler(row, "run");
		const declaresRunKey = declaresCommandHandler(row, "runKey");
		if (row.decision && row.control == null) throw new Error(`leaf: ${row.id} is a Decision command with no control`);
		if (row.lands !== void 0 && typeof row.lands !== "function") throw new TypeError(`leaf: ${row.id} lands must be a function`);
		if (row.native && !declaresRun && !declaresRunKey) throw new Error(`leaf: row ${i} of ${where} leaves the native press to the platform but runs no result`);
		if (row.exit && (!declaresRun || row.touch || row.routes)) throw new Error(`leaf: ${row.id} is its stance's way out, which the panel's row offers in its own words, so it needs a run and no touch words or routes`);
		if (row.touch && (!declaresRun || row.routes)) throw new Error(`leaf: ${row.id} stands in for its keys under a finger, so it needs a run and makes one press, with no routes`);
		const routes = commandRoutes(row);
		if (routes.length && contextBindings(row).length) throw new Error(`leaf: ${row.id} owns distinct routes; declare contextKeys on each route`);
		const declared = declaredBindings(row);
		const routed = /* @__PURE__ */ new Map();
		const contextual = /* @__PURE__ */ new Map();
		for (const route of routes) {
			named(route);
			if (route.decision && route.control == null && row.control == null) throw new Error(`leaf: route ${route.id} of ${row.id} is a Decision command with no control`);
			if ((route.binding === void 0 || !declared.includes(route.binding)) && !contextBindings(route).length) throw new Error(`leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`);
			const routeBindings = [[route.binding === void 0 ? [] : [route.binding], routed], [contextBindings(route), contextual]];
			for (const [bindings, owners] of routeBindings) for (const binding of bindings) {
				const prior = owners.get(binding);
				if (prior && prior !== route) throw new Error(`leaf: ${row.id} routes ${binding} twice`);
				owners.set(binding, route);
			}
		}
		if (routes.length) {
			const missing = declared.filter((binding) => !routed.has(binding));
			if (missing.length) throw new Error(`leaf: ${row.id} has no route for ${missing.join(", ")}`);
		}
		for (const binding of allBindings(row)) {
			for (const mod of parsed(binding).mods) if (!MODIFIERS.includes(mod)) throw new Error(`leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier this dispatcher answers (${MODIFIERS.join(", ")})`);
			const canonical = canonicalBinding(binding);
			if (binding !== canonical) throw new Error(`leaf: row ${i} of ${where} binds ${binding}; write the canonical ${canonical.endsWith(" ") ? JSON.stringify(canonical) : canonical}`);
		}
	});
	return rows;
}
function clampedRow(rows, current, dir, entry = dir > 0 ? 0 : rows.length - 1) {
	if (!rows.length) return void 0;
	const at = rows.findIndex((row) => row === current);
	const next = at < 0 ? entry : at + dir;
	return rows[Math.max(0, Math.min(rows.length - 1, next))];
}
const hasRows = (rows) => rows.length > 0;
function cycledRow(rows, current, dir) {
	if (!rows.length) return void 0;
	const at = rows.findIndex((row) => row === current);
	return rows[((at < 0 ? dir > 0 ? 0 : rows.length - 1 : at + dir) + rows.length) % rows.length];
}
function nativePress(control) {
	return control instanceof HTMLElement && control.isConnected ? () => control.click() : null;
}
function commandRun(row, binding, control = word(row.control)) {
	const keyed = row.runKey;
	const action = row.run;
	if (keyed && binding != null) return () => keyed(binding);
	return action ?? nativePress(control);
}

//#endregion
//#region runtime/keyboard/text-entry.js
function EVERYTHING() {
	return true;
}
function CHARACTER(binding) {
	return [...parsed(binding).key].length === 1;
}
const EDITING = /* @__PURE__ */ new Set([
	"Enter",
	"Backspace",
	"Delete",
	...CARET_KEYS
]);
function TEXT_ENTRY(binding) {
	return CHARACTER(binding) || EDITING.has(parsed(binding).key);
}
function nativeClaimAt(control) {
	if (takesLetters(control)) return TEXT_ENTRY;
	const navigation = controlNavigationKeys(control);
	return navigation.length ? (binding) => navigation.includes(parsed(binding).key) : null;
}
const LINK = "a[href], area[href]";
const ACTIVATION = [
	[LINK, ["Enter"]],
	[`button, ${ROLE_BUTTON_OFFER}, details > summary, input:is([type="button"], [type="submit"], [type="reset"], [type="image"])`, PRESS],
	["input:is([type=\"checkbox\"], [type=\"radio\"])", [" "]]
];
function nativeActivationAt(control) {
	const presses = ACTIVATION.find(([selector]) => control?.matches?.(selector))?.[1];
	return presses ? (binding) => presses.includes(binding) : null;
}

//#endregion
//#region runtime/repaint.js
let painters = null;
let frame = 0;
let movePage = false;
function mountRepaint(slots) {
	painters = slots;
	onCurrentLocation(requestFrame);
	onFocusVisibility(requestFrame);
	requestFrame();
}
function requestFrame() {
	const p = painters;
	if (!p || frame) return;
	frame = nextRender(() => {
		frame = 0;
		const shiftPage = movePage;
		movePage = false;
		p.reflectFirstScopes?.();
		p.markHere?.();
		p.paintCurrentLocation?.();
		p.paintSelectedMarginEntries?.();
		p.paintTouchControls?.();
		p.paintCloseRequests?.();
		p.paintStatusContext?.();
		p.syncLayout?.();
		if (shiftPage) p.pageShifted?.();
		p.publishInputHint?.();
		p.paintGoToHints?.();
		p.paintTargetPickerHints?.();
		p.paintCommandHints?.();
		p.paintCoreControls?.();
		p.paintVersionShortcuts?.();
		p.reflectKeys?.();
	});
}
function repaint() {
	requestFrame();
}
function repaintPage() {
	movePage = true;
	requestFrame();
}

//#endregion
//#region runtime/keyboard/scopes.js
const unpainted = /* @__PURE__ */ new Map();
let buttonsDirty = true;
const wiredButtons = /* @__PURE__ */ new WeakSet();
const buttonReadings = /* @__PURE__ */ new WeakMap();
const buttonCommand = (control) => buttonReadings.get(control);
const buttonBaselines = /* @__PURE__ */ new WeakMap();
const BUTTON_AVAILABILITY = Symbol("native command availability");
const commandAvailabilityReaders = /* @__PURE__ */ new Set();
function watchCommandAvailability(read) {
	commandAvailabilityReaders.add(read);
	buttonsDirty = true;
	return () => commandAvailabilityReaders.delete(read);
}
const reflectCommandAvailability = () => {
	for (const read of commandAvailabilityReaders) read();
};
const commandScopeReaders = /* @__PURE__ */ new Set();
function watchCommandScopes(read) {
	commandScopeReaders.add(read);
	buttonsDirty = true;
	return () => commandScopeReaders.delete(read);
}
function* nativeCommandScopes() {
	for (const ref of scopeRefs) {
		const source = ref.deref();
		if (source?.isConnected) for (const scope of scopesAt(source)) yield {
			source,
			scope
		};
	}
	for (const read of commandScopeReaders) for (const scope of read()) yield {
		source: document.documentElement,
		scope
	};
}
const projectedOnto = (control, scope) => [...projectedScopes.get(control)?.values() ?? []].some((projected) => scopeIdentity(projected) === scopeIdentity(scope));
function buttonDeclarations() {
	const declarations = /* @__PURE__ */ new Map();
	for (const { source, scope } of nativeCommandScopes()) {
		if (scope.contextual || scope.sequence) continue;
		for (const row of scope.rows) {
			if (!row.run && !row.runKey) continue;
			const routes = commandRoutes(row);
			for (const entry of routes.length ? routes : [row]) {
				const control = word(entry.control ?? row.control);
				if (!(control instanceof HTMLButtonElement) || !control.isConnected) continue;
				if (projectedOnto(control, scope)) continue;
				const run = commandRun(row, commandBinding(row, entry === row ? null : entry), null);
				if (!run) continue;
				const candidate = {
					source,
					scope,
					row,
					run,
					entry
				};
				const candidates = declarations.get(control);
				if (!candidates) declarations.set(control, [candidate]);
				else if (!candidates.some((candidate) => candidate.row === row && candidate.entry.id === entry.id)) candidates.push(candidate);
			}
		}
	}
	return declarations;
}
function chosenCommand(candidates) {
	const [first, second] = candidates.filter(({ scope, row, entry }) => (!scope.when || scope.when()) && declaredCommandAvailable(row, entry === row ? null : entry));
	if (first && second) throw new TypeError(`leaf: ${second.entry.id} shares a button with ${first.entry.id}`);
	return first ?? candidates[0];
}
function buttonCommands() {
	return new Map([...buttonDeclarations()].map(([control, candidates]) => [control, chosenCommand(candidates)]));
}
function releaseButtons(declarations) {
	for (const ref of scopeRefs) {
		const control = ref.deref();
		if (!(control instanceof HTMLButtonElement) || declarations.has(control)) continue;
		const baseline = buttonBaselines.get(control);
		if (!baseline) continue;
		buttonReadings.delete(control);
		buttonAvailability.get(control)?.();
		buttonAvailability.delete(control);
		const { disabled, ariaDisabled } = baseline;
		if (control.disabled !== disabled) control.disabled = disabled;
		keeps(control, "aria-disabled", ariaDisabled);
		buttonBaselines.delete(control);
		controlAvailabilityOutput(control, BUTTON_AVAILABILITY);
		reflectElementShortcuts(control);
		forgetScopedElement(control);
	}
}
const buttonAvailability = /* @__PURE__ */ new WeakMap();
const buttonCandidates = /* @__PURE__ */ new WeakMap();
const sameCandidates = (left, right) => left?.length === right.length && right.every((candidate, index) => candidate.scope === left?.[index]?.scope && candidate.row === left?.[index]?.row && candidate.entry === left?.[index]?.entry);
function reflectButton(control, candidates) {
	buttonAvailability.get(control)?.();
	buttonCandidates.set(control, candidates);
	const ref = new WeakRef(control);
	let reading = {
		control,
		candidates
	};
	let failure = null;
	const dispose = x(() => {
		if (reading) {
			const read = reading;
			reading = null;
			try {
				focusRevision();
				const command = chosenCommand(read.candidates);
				const { scope, row, entry } = command;
				const disabled = Boolean(scope.when && !scope.when() || !commandAvailable(row, entry === row ? null : entry));
				keeps(read.control, "aria-disabled", disabled ? "true" : null);
				buttonReadings.set(read.control, command);
			} catch (error) {
				failure = error;
			}
			return;
		}
		const moved = ref.deref();
		if (moved) {
			dirtyButtons.add(moved);
			repaint();
		} else dispose();
	});
	buttonAvailability.set(control, dispose);
	if (failure) throw failure;
}
function claimButton(control) {
	if (!buttonBaselines.has(control)) buttonBaselines.set(control, {
		disabled: control.disabled,
		ariaDisabled: control.getAttribute("aria-disabled")
	});
	controlAvailabilityOutput(control, BUTTON_AVAILABILITY, {
		disabled: true,
		ariaDisabled: true
	});
	if (control.disabled) control.disabled = false;
	rememberScopedElement(control);
}
function runLanding(row, run, from) {
	run();
	const to = row.lands?.(from);
	if (to) focusDestination(to, "move");
}
function wireButton(control) {
	claimButton(control);
	if (wiredButtons.has(control)) return;
	wiredButtons.add(control);
	control.addEventListener("click", (event) => {
		if (event.defaultPrevented || event.button !== 0) return;
		const command = buttonCommands().get(control);
		if (!command) return;
		event.preventDefault();
		if (command.scope.when && !command.scope.when() || !commandAvailable(command.row, command.entry === command.row ? null : command.entry)) return;
		runLanding(command.row, command.run, control);
	});
}
function wireDeclaredButtons(scope) {
	if (scope.contextual || scope.sequence) return;
	for (const row of scope.rows) {
		if (!declaresCommandHandler(row, "run") && !declaresCommandHandler(row, "runKey") || typeof row.routes === "function") continue;
		for (const entry of row.routes?.length ? row.routes : [row]) {
			const control = entry.control ?? row.control;
			if (control instanceof HTMLButtonElement && !projectedOnto(control, scope)) wireButton(control);
		}
	}
}
const elementScopes = /* @__PURE__ */ new WeakMap();
const projectedScopes = /* @__PURE__ */ new WeakMap();
const commandScopeCapabilities = /* @__PURE__ */ new WeakSet();
const scopeIdentity = (scope) => scope.identity ?? scope;
const isCommandScope = (capability) => capability != null && (typeof capability === "object" || typeof capability === "function") && commandScopeCapabilities.has(capability);
const localContexts = /* @__PURE__ */ new WeakMap();
function localContext(source, scope) {
	let contexts = localContexts.get(source);
	if (!contexts) localContexts.set(source, contexts = /* @__PURE__ */ new WeakMap());
	let contextual = contexts.get(scope);
	if (!contextual) {
		contextual = {
			identity: Object.freeze({}),
			title: scope.title,
			contextual: true,
			el: source,
			when: scope.when,
			ready: scope.ready,
			get rows() {
				return contextRows([{
					source,
					scope
				}]);
			}
		};
		contexts.set(scope, contextual);
	}
	return contextual;
}
const scopesAt = (element) => {
	return [elementScopes.get(element), ...projectedScopes.get(element)?.values() ?? []].filter((scope) => scope !== void 0).flatMap((scope) => scope.contextual ? [scope] : [scope, localContext(element, scope)]);
};
const contextRowsBySource = /* @__PURE__ */ new WeakMap();
function contextRows(declarations) {
	return declarations.flatMap(({ source, scope, rows = scope.rows }) => {
		let scopes = contextRowsBySource.get(source);
		if (!scopes) contextRowsBySource.set(source, scopes = /* @__PURE__ */ new WeakMap());
		let rowsBySource = scopes.get(scope);
		if (!rowsBySource) scopes.set(scope, rowsBySource = /* @__PURE__ */ new WeakMap());
		return rows.flatMap((row) => {
			const contributions = () => commandRoutes(row).length ? commandRoutes(row) : [row];
			if (!contributions().some((contribution) => contextBindings(contribution).length)) return [];
			let contextual = rowsBySource.get(row);
			if (!contextual) {
				contextual = {
					id: row.id,
					title: () => titleOf(row),
					description: () => descriptionOf(row),
					get keys() {
						return commandRoutes(this).flatMap(({ binding }) => binding === void 0 ? [] : [binding]);
					},
					get routes() {
						return contributions().flatMap((contribution) => {
							const aliases = contextBindings(contribution);
							const reference = Object.freeze({
								id: contribution.id,
								source,
								scope,
								row,
								binding: commandBinding(row, contribution === row ? null : contribution) ?? null,
								get control() {
									return word(contribution.control ?? row.control);
								}
							});
							return aliases.map((binding) => contextualRoute({
								id: contribution.id,
								binding,
								title: () => titleOf(contribution),
								description: () => descriptionOf(contribution),
								control: contribution.control ?? row.control,
								bindingBadge: contribution.bindingBadge !== void 0 ? contribution.bindingBadge : row.bindingBadge,
								intrinsicBindings: contribution === row ? declaredBindings(row) : contribution.binding ? [contribution.binding] : []
							}, reference));
						});
					},
					when: () => source.isConnected && scopesAt(source).includes(scope) && (!scope.when || scope.when()) && scope.rows.includes(row) && live(row)
				};
				rowsBySource.set(row, contextual);
			}
			return [contextual];
		});
	});
}
const contextScopeReaders = /* @__PURE__ */ new Set();
function contextScopes(title, resolve) {
	const identity = Object.freeze({});
	const read = (origin) => {
		const projection = resolve(origin);
		if (!projection) return null;
		return {
			identity,
			title,
			contextual: true,
			el: projection.root,
			get rows() {
				return contextRows(word(projection.declarations));
			}
		};
	};
	contextScopeReaders.add(read);
	return () => contextScopeReaders.delete(read);
}
const scopeRefs = /* @__PURE__ */ new Set();
const scopeRefFor = /* @__PURE__ */ new WeakMap();
const pruneScopedElements = () => {
	for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
function rememberScopedElement(el) {
	if (scopeRefFor.has(el)) return;
	const ref = new WeakRef(el);
	scopeRefFor.set(el, ref);
	scopeRefs.add(ref);
}
function forgetScopedElement(el) {
	if (elementScopes.has(el) || projectedScopes.has(el) || buttonBaselines.has(el)) return;
	const ref = scopeRefFor.get(el);
	if (ref) scopeRefs.delete(ref);
	scopeRefFor.delete(el);
}
function attachScope(where, declaration) {
	const scope = {
		...declaration,
		el: where,
		validated: false
	};
	unpainted.delete(where);
	elementScopes.set(where, scope);
	unpainted.set(where, scope);
	wireDeclaredButtons(scope);
	rememberScopedElement(where);
	buttonsDirty = true;
	repaint();
	return scope;
}
function detachScope(element, scope) {
	if (elementScopes.get(element) !== scope) return false;
	unpainted.delete(element);
	elementScopes.delete(element);
	forgetScopedElement(element);
	buttonsDirty = true;
	reflectElementShortcuts(element);
	return true;
}
function declaredScope(title, rows, options) {
	const { when, escape, ready, claims } = typeof options === "function" ? { when: options } : options ?? {};
	if (escape !== void 0 && escape !== "inner") throw new TypeError(`A command scope's Escape ownership must be "inner", got ${String(escape)}`);
	return {
		title,
		rows: checked(rows, title ?? "a scope", ready),
		when,
		escape,
		ready,
		claims
	};
}
function keys(where, ...declaration) {
	if (declaration[1] === void 0) return attachScope(where, declaration[0].scope).rows;
	const [title, rows, options] = declaration;
	return attachScope(where, declaredScope(title, rows, options)).rows;
}
const commandsOn = directive$1(class extends AsyncDirective {
	#reconnect = () => {};
	#disconnect = () => {};
	constructor(part) {
		super(part);
		if (part.type !== PartType$1.ELEMENT) throw new TypeError("commandsOn belongs in a template's element part");
	}
	render(_title, _rows, _options) {
		return nothing$1;
	}
	update(part, values) {
		const element = part.element;
		const declaration = values[1] === void 0 ? values[0].scope : declaredScope(values[0], typeof values[1] === "function" ? values[1](element) : values[1], values[2]);
		let scope = null;
		this.#reconnect = () => {
			scope = attachScope(element, declaration);
		};
		this.#disconnect = () => {
			if (detachScope(element, scope)) repaint();
		};
		if (this.isConnected) this.reconnected();
		return nothing$1;
	}
	reconnected() {
		this.#reconnect();
	}
	disconnected() {
		this.#disconnect();
	}
});
const declared = /* @__PURE__ */ new WeakMap();
addEventListener(COMMANDS, (event) => {
	const element = commandsChangedOn(event);
	const declaration = element.lfCommands ?? null;
	const standing = declared.get(element);
	if (declaration === (standing?.declaration ?? null)) {
		paintKeys();
		return;
	}
	if (!declaration) {
		declared.delete(element);
		if (detachScope(element, standing.scope)) repaint();
		return;
	}
	try {
		const scope = attachScope(element, isCommandScope(declaration) ? declaration.scope : declaredScope(declaration.title, declaration.rows, declaration));
		declared.set(element, {
			declaration,
			scope
		});
	} catch (error) {
		refuseCommands(event, error);
	}
});
function commandScope(title, rows, options) {
	const scope = {
		...declaredScope(title, rows, options),
		identity: Object.freeze({})
	};
	validateRows(scope.rows, title ?? "a scope");
	const capability = Object.freeze({ scope });
	commandScopeCapabilities.add(capability);
	return capability;
}
function projectCommandScope(control, projector, capability = null) {
	dirtyButtons.add(control);
	const projections = projectedScopes.get(control) ?? /* @__PURE__ */ new Map();
	if (capability == null) {
		projections.delete(projector);
		if (!projections.size) {
			projectedScopes.delete(control);
			forgetScopedElement(control);
		}
		reflectElementShortcuts(control);
		return;
	}
	projections.set(projector, capability.scope);
	projectedScopes.set(control, projections);
	wireDeclaredButtons(capability.scope);
	rememberScopedElement(control);
	reflectTracked(control);
}
function scopesWithin(root, activeOnly) {
	pruneScopedElements();
	const found = [];
	const seen = /* @__PURE__ */ new Set();
	for (const ref of scopeRefs) {
		const scoped = ref.deref();
		if (!scoped?.isConnected) continue;
		let inside = false;
		let node = scoped;
		for (; node; node = renderedParent(node)) if (node === root) {
			inside = true;
			break;
		}
		if (!inside) continue;
		for (const scope of scopesAt(scoped)) {
			if (scope.contextual) continue;
			if (activeOnly && scope.when && !scope.when()) continue;
			const identity = scopeIdentity(scope);
			if (seen.has(identity)) continue;
			seen.add(identity);
			found.push({
				source: scoped,
				scope
			});
		}
	}
	return found;
}
const commandDeclarationsWithin = (root) => scopesWithin(root, false);
function commandsWithin(root) {
	return scopesWithin(root, true).flatMap(({ source, scope }) => scope.rows.filter(live).map((row) => ({
		source,
		scope,
		row
	})));
}
function reflectElementShortcuts(element) {
	const available = scopesAt(element).filter((scope) => !scope.when || scope.when());
	for (const scope of available) {
		try {
			validateRows(scope.rows, scope.title ?? "a scope");
		} catch (error) {
			if (scope.el === element && !scope.validated) detachScope(element, scope);
			throw error;
		}
		if (scope.el === element) scope.validated = true;
	}
	const nativeClaims = nativeClaimAt(element);
	const activation = nativeActivationAt(element);
	const ownsControl = available.some((scope) => scope.rows.some((row) => word(row.control) === element || commandRoutes(row).some((route) => word(route.control ?? row.control) === element)));
	const shortcuts = [...new Set(available.flatMap((scope) => ariaShortcuts(scope.rows, true, scope.title ?? "a scope", (binding, entry, row) => {
		if (scope.contextual && (nativeClaims?.(binding) || activation?.(binding))) return false;
		const control = word(entry.route?.control ?? row.control);
		return !ownsControl || control == null || control === element;
	}).split(" ").filter(Boolean)))].join(" ");
	keeps(element, "aria-keyshortcuts", shortcuts || null);
}
function reflectFirstScopes() {
	reflectButtonsTracked();
	for (const [element, scope] of unpainted) {
		unpainted.delete(element);
		reflectTracked(scope.el);
	}
}
let keysDirty = true;
const dirtyElements = /* @__PURE__ */ new Set();
const tracked = /* @__PURE__ */ new WeakMap();
const dirtyButtons = /* @__PURE__ */ new Set();
let availabilityTracking = null;
let availabilityDirty = true;
function reflectAvailabilityReaders() {
	availabilityDirty = false;
	availabilityTracking?.();
	let first = true;
	let failure = null;
	availabilityTracking = x(() => {
		if (first) {
			first = false;
			try {
				focusRevision();
				reflectCommandAvailability();
			} catch (error) {
				failure = error;
			}
			return;
		}
		availabilityDirty = true;
		repaint();
	});
	if (failure) throw failure;
}
function reflectButtonsTracked() {
	if (!buttonsDirty && !dirtyButtons.size && !availabilityDirty) return;
	const every = buttonsDirty;
	buttonsDirty = false;
	for (const control of buttonDeclarations().keys()) claimButton(control);
	const failures = [];
	try {
		reflectAvailabilityReaders();
	} catch (error) {
		failures.push(error);
	}
	const dirty = new Set(dirtyButtons);
	dirtyButtons.clear();
	const declarations = buttonDeclarations();
	releaseButtons(declarations);
	for (const [control, candidates] of declarations) {
		claimButton(control);
		rememberScopedElement(control);
		wireButton(control);
		if (!every && !dirty.has(control) && buttonAvailability.has(control) && sameCandidates(buttonCandidates.get(control), candidates)) continue;
		try {
			reflectButton(control, candidates);
		} catch (error) {
			failures.push(error);
		}
	}
	for (const failure of failures) reportError(failure);
}
function reflectTracked(element) {
	tracked.get(element)?.();
	const ref = new WeakRef(element);
	let initial = element;
	let failure = null;
	const dispose = x(() => {
		if (initial) {
			const current = initial;
			initial = null;
			try {
				focusRevision();
				reflectElementShortcuts(current);
			} catch (error) {
				failure = error;
			}
			return;
		}
		const moved = ref.deref();
		if (moved) {
			dirtyElements.add(moved);
			repaint();
		} else dispose();
	});
	tracked.set(element, dispose);
	if (failure) throw failure;
}
function reflectKeys() {
	if (!keysDirty && !dirtyElements.size) return;
	const every = keysDirty;
	keysDirty = false;
	const dirty = [...dirtyElements];
	dirtyElements.clear();
	reflectButtonsTracked();
	pruneScopedElements();
	const elements = every ? [...scopeRefs].map((ref) => ref.deref()) : dirty;
	for (const scoped of elements) {
		if (!scoped?.isConnected) continue;
		try {
			reflectTracked(scoped);
		} catch (error) {
			reportError(error);
		}
	}
}
const paintKeys = () => {
	keysDirty = true;
	buttonsDirty = true;
	repaint();
};
const paintKeysWithin = (root) => {
	for (const ref of scopeRefs) {
		const scoped = ref.deref();
		if (scoped && under(scoped, root)) {
			dirtyElements.add(scoped);
			dirtyButtons.add(scoped);
		}
	}
	repaint();
};
const saying = (rows) => activeRows(rows, "an announced scope").map((row) => `${spoken(row)} ${titleOf(row)}`).join(", ");
const spoken = (row) => {
	const active = bindings(row);
	if (active.some((binding) => parsed(binding).mods.length)) return active.map(spokenBinding).join(" or ");
	return word(row.label) ?? active.map(spokenBinding).join(" or ");
};
function scopesFor(node) {
	const contexts = [...contextScopeReaders].map((read) => read(node)).filter((scope) => scope !== null);
	const found = [];
	const seen = /* @__PURE__ */ new Set();
	const collect = (start) => {
		for (let a = start; a; a = renderedParent(a)) {
			for (const scope of [...scopesAt(a), ...contexts.filter(({ el }) => el === a)]) {
				const identity = scopeIdentity(scope);
				if (seen.has(identity)) continue;
				found.push(scope.el ? scope : {
					...scope,
					el: a
				});
				seen.add(identity);
			}
			if (a.hasAttribute?.("data-lf-thread-surface")) break;
		}
	};
	collect(node);
	return found;
}
const claimsEsc = (node) => scopesFor(node).some((scope) => scope.rows.some((row) => live(row) && bindings(row).includes("Escape")));

//#endregion
//#region runtime/widget-elements.js
function reveal(el, mayReveal) {
	const chain = [];
	const settling = /* @__PURE__ */ new Set();
	let replacedView = false;
	for (let a = el; a; a = renderedParent(a)) chain.push(a);
	chain.reverse();
	for (const [at, a] of chain.entries()) {
		if (!mayReveal()) break;
		if (a instanceof HTMLDetailsElement && !a.open) a.open = true;
		if (a instanceof HTMLElement && a.hasAttribute("popover") && !isNativeLayer(a)) showNativeLayer(a, { modal: false });
		if (a.getAttribute?.("hidden") !== "until-found") continue;
		const shown = [...a.parentNode?.children ?? []].filter((s) => !("hidden" in s && s.hidden));
		a.dispatchEvent(new Event("beforematch", { bubbles: true }));
		a.removeAttribute("hidden");
		if (shown.some((sibling) => "hidden" in sibling && sibling.hidden)) replacedView = true;
		for (const owner of chain.slice(0, at + 1)) if (owner.updateComplete?.then) settling.add(owner.updateComplete);
	}
	const ready = Promise.all(settling);
	ready.catch(() => {});
	return {
		ready,
		replacedView
	};
}
function el(tag, cls, text) {
	const node = document.createElement(tag);
	if (cls) node.className = cls;
	if (text !== void 0) node.textContent = text;
	return node;
}
const hands = Z(/* @__PURE__ */ new Set());
const dragHeld = () => hands.value.size > 0;
const dragging = (el, on) => {
	const held = new Set(hands.peek());
	if (on) held.add(el);
	else held.delete(el);
	hands.value = held;
	paintKeysWithin(el);
};
function worksInside(node, container) {
	const parts = /* @__PURE__ */ new Set([container.localName]);
	for (let grew = true; grew;) {
		grew = false;
		for (const tag of tagsDeclaring((entry) => (entry["x-owners"] ?? []).some((owner) => parts.has(owner)))) if (!parts.has(tag)) {
			parts.add(tag);
			grew = true;
		}
	}
	const held = tagsDeclaring(() => true).filter((tag) => !parts.has(tag));
	const inner = node.closest([
		...held,
		WORKS,
		"[data-lf-offer]",
		".lf-msg-sending"
	].join(","));
	return inner && inner !== container && container.contains(inner) ? inner : null;
}
const PRESSABLE = "[data-lf-offer]:not([data-lf-offer=\"\"])";
function reachedForWords(el) {
	const sel = getSelection();
	if (!sel?.rangeCount) return false;
	const range = pageRange(sel);
	const focus = selectionBackward(sel, range) ? range.startContainer : range.endContainer;
	return !range.collapsed && renderedUnder(focus, el);
}
document.addEventListener("click", (ev) => {
	if (pressIsKeyboardActivation(ev)) return;
	const control = ev.composedPath().find((node) => node instanceof Element && node.matches(`${PRESSES},[data-lf-offer]`));
	if (control && reachedForWords(control)) {
		ev.stopPropagation();
		ev.preventDefault();
	}
}, true);
const closeControl = ({ name, title = name, className = "" }) => offerAction("symbol", className, name, {
	title,
	action: "close"
});
function responseAction(control, { glyph = null, action = null, label, behavior = "action", collapse = false }) {
	if (Boolean(String(glyph ?? "").trim()) === Boolean(action)) throw new TypeError("A response action needs exactly one glyph or action");
	control.classList.toggle("lf-response-control", true);
	control.classList.toggle("lf-response-action", true);
	keeps(control, "data-lf-behavior", behavior);
	control.toggleAttribute("data-lf-collapse", collapse);
	if (behavior !== "action" && !control.hasAttribute("aria-expanded")) control.setAttribute("aria-expanded", "false");
	if (behavior === "action") control.removeAttribute("aria-expanded");
	if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
	render$1(html$1`${action ? actionTemplate(action) : html$1`<span class="lf-response-action-glyph" aria-hidden="true"
              >${glyph}</span
            >`}<span class="lf-response-action-space" aria-hidden="true"> </span
      ><span class="lf-response-action-label">${label}</span>`, control);
	return control;
}
function motionPreview(label) {
	const preview = offer("div", "lf-motion-preview", label);
	preview.inert = true;
	preview.setAttribute("aria-hidden", "true");
	return preview;
}
const authoredBodies = /* @__PURE__ */ new WeakMap();
const authoredBody = (host) => authoredBodies.get(host) ?? null;
function holdAuthoredBody(host, body) {
	for (const node of [...host.childNodes]) move(body, node, null);
	authoredBodies.set(host, body);
	return body;
}

//#endregion
//#region runtime/notifications.js
const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");
const NOTICE_MS = 4e3;
let noticeTimer = 0;
let showingBackground = null;
const waitingBackground = [];
let userContext = false;
let userHoldTimer = 0;
const noticePresentation = Z(Object.freeze({
	message: "",
	visible: false
}));
const noticeReading = () => noticePresentation.value;
const noticeVisible = () => noticePresentation.peek().visible;
const noticeWords = (message) => typeof message === "string" ? [leafSays(message)] : message;
const presentNotice = (message, visible) => {
	noticePresentation.value = Object.freeze({
		message,
		visible
	});
};
function announce(msg) {
	if (liveEl.firstChild) liveEl.replaceChildren();
	setTimeout(() => {
		if (liveEl.firstChild) liveEl.replaceChildren();
		liveEl.append(wordsText(msg));
	}, 30);
}
addEventListener(ANNOUNCE, (event) => announce(event.detail));
function showNotice(msg, background = null) {
	presentNotice(msg, true);
	showingBackground = background;
	clearTimeout(noticeTimer);
	noticeTimer = setTimeout(() => {
		if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift())) return;
		presentNotice(noticePresentation.peek().message, false);
		showingBackground = null;
	}, NOTICE_MS);
}
function showBackground(entry) {
	while (entry) {
		const message = entry.key === "text" ? entry.value : entry.format(entry.value);
		if (wordsText(message)) {
			showNotice(message, entry);
			return true;
		}
		entry = waitingBackground.shift();
	}
	return false;
}
const textBackground = (message) => ({
	key: "text",
	value: message
});
function queueBackground(entry, front = false) {
	const waiting = waitingBackground.find((waiting) => waiting.key === entry.key);
	if (waiting) {
		waitingBackground.splice(waitingBackground.indexOf(waiting), 1);
		if (entry.key === "semantic-news" && waiting.key === "semantic-news") entry = {
			...entry,
			value: front ? entry.combine(entry.value, waiting.value) : entry.combine(waiting.value, entry.value)
		};
		else if (front) entry = waiting;
	}
	if (front) waitingBackground.unshift(entry);
	else waitingBackground.push(entry);
}
function notice(msg, { background = false, announce: speak = true, group = null } = {}) {
	if (speak) announce(msg);
	if (background) {
		const entry = group ?? textBackground(msg);
		if (userContext || userHoldTimer || noticeVisible()) return queueBackground(entry);
		return showBackground(entry);
	}
	if (showingBackground) queueBackground(showingBackground, true);
	showNotice(msg);
}
function yieldNotice() {
	if (showingBackground) queueBackground(showingBackground, true);
	clearTimeout(noticeTimer);
	presentNotice(noticePresentation.peek().message, false);
	showingBackground = null;
}
function holdStatus(ms) {
	if (noticeVisible()) yieldNotice();
	clearTimeout(userHoldTimer);
	userHoldTimer = setTimeout(() => {
		userHoldTimer = 0;
		if (userContext || noticeVisible() || !waitingBackground.length) return;
		showBackground(waitingBackground.shift());
	}, ms);
}
function setNoticeContext(active) {
	userContext = active;
	if (active && showingBackground) yieldNotice();
	else if (!active && !userHoldTimer && waitingBackground.length && !noticeVisible()) showBackground(waitingBackground.shift());
}

//#endregion
//#region runtime/errors.js
const KEPT = 20;
let raised = 0;
let unsaid = [];
const errors = Z(Object.freeze([]));
const publish = (next) => {
	errors.value = Object.freeze(next.slice(0, KEPT));
};
const errorsReading = () => errors.value;
function raiseError(message, { subject = null, announce: speak = true } = {}) {
	return raise(message, subject, speak, null);
}
function raise(message, subject, speak, replaced) {
	const id = ++raised;
	if (speak && !unsaid.length) queueMicrotask(() => {
		announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
		unsaid = [];
	});
	if (speak) unsaid.push(message);
	publish([Object.freeze({
		id,
		message,
		subject,
		at: Date.now(),
		passed: false,
		seen: false
	}), ...errors.peek().filter((entry) => entry.id !== replaced)]);
	return Object.freeze({
		id,
		clear: () => dismissError(id)
	});
}
function passErrors(ids) {
	if (errors.peek().some((entry) => ids.includes(entry.id) && !entry.passed)) publish(errors.peek().map((entry) => ids.includes(entry.id) && !entry.passed ? Object.freeze({
		...entry,
		passed: true
	}) : entry));
}
function passErrorsAt(subject) {
	passErrors(errors.peek().filter((entry) => entry.subject === subject).map((entry) => entry.id));
}
function seeErrors() {
	if (errors.peek().some((entry) => !entry.seen)) publish(errors.peek().map((entry) => entry.seen ? entry : Object.freeze({
		...entry,
		seen: true
	})));
}
function dismissError(id) {
	if (errors.peek().some((entry) => entry.id === id)) publish(errors.peek().filter((entry) => entry.id !== id));
}
function holdingError({ announce: speak = true } = {}) {
	let held = null;
	let said = null;
	return (message) => {
		if (message === said) return;
		if (message) held = raise(message, null, speak, held?.id ?? null);
		else {
			held?.clear();
			held = null;
		}
		said = message;
	};
}
function dismissErrors() {
	if (errors.peek().length) publish([]);
}

//#endregion
export { COLLAPSE, DELIVERY, DRAFT_FORMAT, EVERYTHING, LINK, LIVE_ROOT, LitElement$1 as LitElement, PAGE_ROOT, PENDING, PRESENTATION_DOM, PRESSABLE, SHARE_ROOT, TEXT_BLOCK, TEXT_ENTRY, WEBSITE_DELIVERY, actionForWidget, adoptRegistry, advertisesKeys, agentName, agentSays, allBindings, anchorKey, annotationMode, announce, answers, applicationPresented, applicationPresenter, applicationRegionsPresented, applicationState, ariaShortcuts, attachApplicationPresentation, attachWidgetPresentation, authoredBody, authoredRank, bareReaction, bindingEnabled, bindingEnabledFor, bindings, buttonCommand, carriesObligation, checked, claimsEsc, clampedRow, closeControl, commandAvailable, commandBinding, commandDeclarationsWithin, commandEntries, commandPresentations, commandReady, commandRoutes, commandRun, commandScope, commandsOn, commandsWithin, contextBindings, contextScopes, controlAvailabilityOutput, createPresentationSchedule, cycledRow, decisionControls, decisionFor, declarationFor, declareCommandReadiness, declaredBindings, declaredRoot, declaresCommandHandler, descriptionOf, discussed, dismissError, dismissErrors, documentChanged, dragHeld, dragging, drawingSchema, editable, el, elementDeclarations, elementsDeclaring, errorsReading, exhibits, foldWidgetStates, fragmentId, guard, hasObligationSource, hasRows, holdAuthoredBody, holdStatus, holdingError, hostIn, html$1 as html, isCommandScope, isElementName, isMessageEvent, isNews, isReaction, isThreadEvent, itemNoun, itemOutcome, keyed, keys, labelOf, lastMovedAt, layerFact, layerRoot, leafSays, live, live$1, liveEl, loadShadowRules, marks, matchesWhen, messageKey, motionPreview, mountRepaint, moved, nativeActivationAt, nativeClaimAt, nativePress, noChange, nothing$1 as nothing, notice, noticeReading, noticeWords, obligationValue, offlineData, offlineInteractive, offlineState, pageClaimed, pageRange, pageShadowRoots, pageUrl, paintKeys, paintKeysWithin, parsed, passErrors, passErrorsAt, presentDocument, programmaticSelection, projectCommandScope, projectView, projectionOrigins, projectionRegionsPresented, pruneScopedElements, queueWidgetUpdate, quickShortcuts, raiseError, rankAt, reachedForWords, reactionsAt, readApplication, readApplicationPresentation, readPart, recordedWidgetSelector, ref, referencedCommandEntry, reflectFirstScopes, reflectKeys, refuseShadowRoot, registry, render$1 as render, renderedChildren, repaint, repaintPage, repeat, responseAction, reveal, revisionLabel, routedCommand, runLanding, runtime, runtimeModule, runtimeResource, saidBy, sameAnchor, savedReadingSettled, saying, scopeAvailable, scopeIdentity, scopeRefs, scopesAt, scopesFor, seatRoot, seeErrors, selectEnds, selectWidgets, selectionBackward, setNoticeContext, setPresentationFailureReporter, setQuickShortcuts, shadowRootsIn, shadowRules, share, shareUrl, spell, spokenBinding, stateSpecs, submitBindings, tagsDeclaring, threadCounts, threadKey, threadNames, tick, titleOf, tokenChoices, tokenEntry, touchPresses, turns, voiceOf, voiced, watchCommandAvailability, watchCommandScopes, watchPresentation, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whenWidgetsPresented, word, wordsText, worksInside };