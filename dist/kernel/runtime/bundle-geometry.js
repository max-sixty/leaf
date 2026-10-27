import { __exportAll } from "./bundle-rolldown-runtime.js";
import { J, W, Z, bindQueuedWork, canPlaceFocus, cancelRender, closeLayer, d, excludedByInert, focused, handBack, isNativeLayer, move, nativeLayerHolding, nativeLayerKind, nextRender, releaseFocus, renderedParent, renderedUnder, shadowHost, sizeObserver, under, upFrom, x } from "./bundle-dom-move.js";
import { AsyncDirective, Directive, LitElement, PartType, classMap, createRef, directive, guard, html, keyed, live, noChange, nothing, ref, render, repeat, styleMap, unsafeHTML } from "/vendor/lit.js";

//#region runtime/arrivals.js
const watches$1 = /* @__PURE__ */ new Set();
const stages = /* @__PURE__ */ new WeakSet();
const stageRefs = /* @__PURE__ */ new Set();
const owners = /* @__PURE__ */ new WeakMap();
let offerOwner;
function watchOwner(owner, lifecycle) {
	let connected = false;
	const subscription = {
		connect() {
			if (connected || !owner.isConnected) return;
			connected = true;
			try {
				lifecycle.connect?.();
			} catch (error) {
				subscriptions.delete(subscription);
				subscription.disconnect();
				throw error;
			}
		},
		disconnect() {
			if (!connected) return;
			connected = false;
			lifecycle.disconnect?.();
		}
	};
	let subscriptions = owners.get(owner);
	if (!subscriptions) owners.set(owner, subscriptions = /* @__PURE__ */ new Set());
	if (!offerOwner) {
		const notify = (element, method) => {
			for (const subscription of owners.get(element) ?? []) try {
				subscription[method]();
			} catch (error) {
				queueMicrotask(() => {
					throw error;
				});
			}
		};
		offerOwner = watchArrivals("*", [], {
			arrive: (element) => notify(element, "connect"),
			leave: (element) => notify(element, "disconnect")
		});
	}
	if (owner.isConnected) offerOwner(owner);
	subscriptions.add(subscription);
	const stop = () => {
		subscriptions.delete(subscription);
		subscription.disconnect();
	};
	subscription.connect();
	return stop;
}
function whileConnected(owner, start) {
	let held;
	return watchOwner(owner, {
		connect() {
			const controller = new AbortController();
			held = {
				controller,
				cleanup: null
			};
			held.cleanup = start(controller.signal);
		},
		disconnect() {
			const current = held;
			held = null;
			current.controller.abort();
			current.cleanup?.();
		}
	});
}
function frameFor(owner, run) {
	let frame = 0;
	watchOwner(owner, { disconnect() {
		cancelRender(frame);
		frame = 0;
	} });
	return () => {
		if (frame || !owner.isConnected) return;
		frame = nextRender(() => {
			frame = 0;
			if (owner.isConnected) run();
		});
	};
}
function liveStages() {
	const live = [];
	for (const ref of stageRefs) {
		const root = ref.deref();
		if (root) live.push(root);
		else stageRefs.delete(ref);
	}
	return live;
}
const isStage = (root) => stages.has(root);
const stands = (el) => {
	const root = el.getRootNode();
	return root === document ? document.body.contains(el) : stages.has(root) && root.host.isConnected;
};
function* matching(node, selector) {
	if (node?.nodeType !== Node.ELEMENT_NODE) return;
	if (node.matches(selector)) yield node;
	yield* node.querySelectorAll(selector);
	for (const stage of liveStages()) if (under(stage.host, node)) yield* stage.querySelectorAll(selector);
}
function watchArrivals(selector, attributes, { arrive, arriveBatch, leave }) {
	const arrived = /* @__PURE__ */ new WeakSet();
	const offerMany = (elements) => {
		const present = [];
		for (const el of elements) if (stands(el) && el.matches(selector)) present.push(el);
		else if (arrived.delete(el)) leave(el);
		if (!arriveBatch) for (const el of present) offer(el);
		else if (present.length) {
			for (const el of present) arrived.add(el);
			arriveBatch(present);
		}
	};
	const offer = (el) => {
		if (stands(el) && el.matches(selector)) {
			arrived.add(el);
			if (arriveBatch) arriveBatch([el]);
			else arrive(el);
		} else if (arrived.delete(el)) leave(el);
	};
	const beside = (node) => node?.nodeType === Node.ELEMENT_NODE && (arrived.has(node) || node.matches(selector)) ? [node] : [];
	const read = (records) => {
		const offered = /* @__PURE__ */ new Set();
		for (const record of records) {
			if (record.type === "attributes") {
				offered.add(record.target);
				continue;
			}
			for (const el of [
				...beside(record.target),
				...beside(record.previousSibling),
				...beside(record.nextSibling)
			]) offered.add(el);
			for (const node of record.addedNodes) for (const el of matching(node, selector)) offered.add(el);
			for (const node of record.removedNodes) for (const el of matching(node, selector)) if (arrived.has(el)) offered.add(el);
		}
		offerMany(offered);
	};
	const observer = new MutationObserver(read);
	const watch = {
		selector,
		attributes,
		observer,
		offerMany
	};
	watches$1.add(watch);
	for (const root of [document.body, ...liveStages()]) enroll(watch, root);
	return (el) => {
		read(observer.takeRecords());
		offer(el);
	};
}
function enroll({ selector, attributes, observer, offerMany }, root) {
	observer.observe(root, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: attributes
	});
	offerMany(root.querySelectorAll(selector));
}
function watchArrivalsIn(stage) {
	if (stages.has(stage)) return;
	stages.add(stage);
	stageRefs.add(new WeakRef(stage));
	for (const watch of watches$1) enroll(watch, stage);
	stage.addEventListener("scroll", heardIn(stage), SCROLL);
}
const scrollListeners = /* @__PURE__ */ new Set();
const SCROLL = {
	capture: true,
	passive: true
};
const heardIn = (stage) => (event) => {
	if (event.target.getRootNode() !== stage) return;
	for (const listener of scrollListeners) listener(event);
};
function watchScrolls(listener) {
	scrollListeners.add(listener);
	document.addEventListener("scroll", listener, SCROLL);
	return () => {
		scrollListeners.delete(listener);
		document.removeEventListener("scroll", listener, SCROLL);
	};
}
const SETTLE_MS = 80;
const settleListeners = /* @__PURE__ */ new Set();
let inFlight = false;
let gliding = false;
let settleTimer = 0;
let trackingScrolls = false;
function settle() {
	if (!inFlight || gliding) return;
	inFlight = false;
	clearTimeout(settleTimer);
	for (const listener of settleListeners) listener();
}
function trackScrolls() {
	if (trackingScrolls) return;
	trackingScrolls = true;
	watchScrolls(() => {
		inFlight = true;
		clearTimeout(settleTimer);
		settleTimer = setTimeout(settle, SETTLE_MS);
	});
	document.addEventListener("scrollend", settle, SCROLL);
}
function scrollGlides(on) {
	trackScrolls();
	gliding = on;
	if (on) inFlight = true;
	else if (inFlight) {
		clearTimeout(settleTimer);
		settleTimer = setTimeout(settle, SETTLE_MS);
	}
}
function scrolling() {
	trackScrolls();
	return inFlight;
}
function watchScrollEnds(listener) {
	trackScrolls();
	settleListeners.add(listener);
	return () => settleListeners.delete(listener);
}

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
	const copy = Object.getPrototypeOf(next) === null ? Object.create(null) : {};
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
	"x-margin-content": {
		"paint": "data-lf-margin-content",
		"message": false
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
	const keys = Object.keys(recorded);
	return keys.length === Object.keys(current).length && keys.every((key) => Object.hasOwn(current, key) && (typeof recorded[key] === "object" ? sameStateDefinition(recorded[key], current[key]) : recorded[key] === current[key]));
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

//#endregion
//#region runtime/thread/identity.js
const PENDING = "pending:";

//#endregion
//#region runtime/thread/model.js
const isReaction = (message) => Boolean(message.token);
const isAddressable = (message) => message.addressable !== false;
const threadOffers = (thread) => ({
	open: true,
	reply: !thread.settling,
	resolve: !thread.resolved && !thread.settling,
	reopen: Boolean(thread.resolved) && !thread.settling
});
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
const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
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
const discussed = (thread) => !bareReaction(thread);
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
		thread.settling = gesture.kind;
	}
	for (const thread of opened) thread.bare_reaction = isReaction(thread.root) && !spoken(thread).length;
	return [...copies, ...opened];
}
const reactionsAt = (threads, anchor) => threads.filter((thread) => bareReaction(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor)).map((thread) => thread.root);
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
	return threads.map((thread) => {
		const unread = thread.unread.filter((item) => !locallyRead.has(versionKey(item)));
		const unreadMessages = new Set(unread.map((item) => item.message));
		const msgs = thread.msgs.map((message) => {
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
				unread: unreadMessages.has(message.id),
				key: messageKey(message),
				body,
				workflows: workflows.filter((workflow) => workflow.message === message.id || workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id))
			};
		});
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
			settling: thread.settling ?? null,
			attention: thread.attention,
			obligations: obligations.filter((obligation) => obligation.thread === thread.id),
			todos: todos.filter((todo) => todo.owner === "agent" && todo.thread === thread.id),
			userTodos: todos.filter((todo) => todo.owner === "user" && todo.thread === thread.id),
			workflows: workflows.filter((workflow) => workflow.thread === thread.id),
			bare_reaction: thread.bare_reaction,
			seat: thread.seat,
			summaries: thread.summaries,
			offers: threadOffers(thread)
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
const pendingForParent = (entries, id, kinds = null) => entries.find((entry) => (entry.event.parent === id || entry.namedParent === id) && (!kinds || kinds.includes(entry.event.kind)));
const actionForWidget = (descriptor, command, revision) => ({
	kind: "action",
	revision,
	widget: descriptor.id,
	action: command.verb,
	detail: structuredClone(command.detail ?? {}),
	...command.attempt && { attempt: command.attempt }
});

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
const itemOutcome = (item) => item.kind === "update" ? "Answered" : OUTCOMES[item.state] ?? item.state;

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
		if (item.source.kind === "todo") {
			const todo = todoRecords.get(item.source.id);
			if (todo.state === "open" && item.status !== "open") return {
				...item,
				answer: null,
				status: "open",
				next_actor: "user",
				end: null
			};
			if (todo.state !== "open" && item.status === "open") return {
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
		if (item.source.kind !== "widget") return item;
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
		reach: "waiting",
		fault: null,
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
	if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));
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
			const subject = turn ? thread === null ? null : {
				kind: "thread",
				id: thread
			} : entry.event.kind === "action" ? {
				kind: "widget",
				id: entry.event.widget
			} : null;
			if (!subject) return null;
			return {
				id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
				revision: entry.event.revision ?? document.revision,
				seq: entry.order,
				input: turn?.id ?? entry.localId,
				message: turn ? turnMessage(turn) : null,
				subject,
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
		if (presentation) activePresentation = presentation.begin(next.semanticEpoch);
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
		setReach(reach, fault = null) {
			const now = publisher.peek();
			if (now.reach === reach && now.fault === fault) return now;
			return publish({
				reach,
				fault
			});
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
				reach: "reached",
				fault: null
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
function describeFailure(reason) {
	const message = reason instanceof Error ? reason.message : String(reason);
	if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
	return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}
function createPresentationCoordinator({ reportFailure }) {
	const changes = Z(0);
	const changed = () => {
		changes.value = changes.peek() + 1;
	};
	let document = null;
	let documentGeneration = 0;
	let semanticEpoch = -1;
	let presentedEpoch = -1;
	let barrier = null;
	let waiters = [];
	let regionWaiters = [];
	const rendererGenerations = /* @__PURE__ */ new Map();
	const regions = /* @__PURE__ */ new Map();
	const validEpoch = (epoch) => {
		if (!Number.isSafeInteger(epoch) || epoch < 0) throw new TypeError("presentation epoch must be a non-negative safe integer");
	};
	function resolveWaiters() {
		const remaining = [];
		for (const waiter of waiters) if (document === null || !Object.is(waiter.document, document)) waiter.resolve("superseded");
		else if (presentedEpoch >= waiter.semanticEpoch) waiter.resolve("presented");
		else remaining.push(waiter);
		waiters = remaining;
	}
	function regionOutcome(waiter) {
		if (waiter.cancelled?.()) return "superseded";
		if (document === null || !Object.is(waiter.document, document)) return "superseded";
		if (semanticEpoch > waiter.semanticEpoch) return "superseded";
		if (semanticEpoch < waiter.semanticEpoch || !barrier?.sealed) return null;
		return [...waiter.regions].some((region) => barrier?.members.get(region)?.commit === null) ? null : "presented";
	}
	function resolveRegionWaiters() {
		const remaining = [];
		for (const waiter of regionWaiters) {
			const outcome = regionOutcome(waiter);
			if (outcome) waiter.resolve(outcome);
			else remaining.push(waiter);
		}
		regionWaiters = remaining;
	}
	function completeBarrier() {
		if (!barrier || barrier.completed || !barrier.sealed) return;
		if ([...barrier.members.values()].some((member) => member.commit === null)) return;
		barrier.completed = true;
		presentedEpoch = barrier.publication.semanticEpoch;
		resolveWaiters();
	}
	function begin(nextDocument, nextSemanticEpoch) {
		validEpoch(nextSemanticEpoch);
		const replacingDocument = document === null || !Object.is(document, nextDocument);
		if (!replacingDocument && nextSemanticEpoch < semanticEpoch) throw new RangeError("presentation epochs cannot decrease within one document");
		if (!replacingDocument && nextSemanticEpoch === semanticEpoch) {
			if (!barrier) throw new Error("the active document has no presentation barrier");
			return barrier.publication;
		}
		if (replacingDocument) {
			document = nextDocument;
			documentGeneration += 1;
			semanticEpoch = nextSemanticEpoch;
			presentedEpoch = -1;
			regions.clear();
			rendererGenerations.clear();
			resolveWaiters();
		} else semanticEpoch = nextSemanticEpoch;
		const publication = Object.freeze({
			document: nextDocument,
			semanticEpoch: nextSemanticEpoch
		});
		const members = /* @__PURE__ */ new Map();
		for (const [region, record] of regions) {
			let commit = record.commit;
			if (commit !== null) {
				commit = Object.freeze({
					...commit,
					semanticEpoch: nextSemanticEpoch
				});
				record.commit = commit;
			}
			members.set(region, {
				record,
				ticket: record.ticket,
				commit,
				retired: false
			});
		}
		barrier = {
			publication,
			members,
			sealed: false,
			completed: false
		};
		resolveRegionWaiters();
		changed();
		return publication;
	}
	function seal(publication) {
		if (!barrier || barrier.publication !== publication) return false;
		barrier.sealed = true;
		completeBarrier();
		resolveRegionWaiters();
		changed();
		return true;
	}
	function currentTicket(ticket) {
		const record = ticket.record;
		return ticket.documentGeneration === documentGeneration && regions.get(record.region) === record && record.ticket === ticket;
	}
	function finish(ticket, status, proof) {
		if (!currentTicket(ticket) || document === null) return;
		const record = ticket.record;
		const commit = Object.freeze({
			document,
			semanticEpoch,
			region: record.region,
			renderer: record.renderer,
			rendererGeneration: record.rendererGeneration,
			ticketGeneration: ticket.ticketGeneration,
			value: ticket.value,
			status,
			proof
		});
		record.ticket = null;
		record.commit = commit;
		const member = barrier?.members.get(record.region);
		if (member?.record === record && member.ticket === ticket) {
			member.ticket = null;
			member.commit = commit;
			completeBarrier();
			resolveRegionWaiters();
		}
		changed();
	}
	function attach(region, renderer) {
		if (document === null || barrier === null) throw new Error("begin a presentation publication before attaching a renderer");
		const record = {
			region,
			renderer,
			rendererGeneration: (rendererGenerations.get(region) ?? 0) + 1,
			ticketGeneration: 0,
			ticket: null,
			commit: null
		};
		rendererGenerations.set(region, record.rendererGeneration);
		regions.set(region, record);
		barrier.completed = false;
		barrier.members.set(region, {
			record,
			ticket: null,
			commit: null,
			retired: false
		});
		changed();
		let latest = null;
		const present = (value, failSoft) => {
			const { promise: completion, resolve, reject } = Promise.withResolvers();
			const superseded = latest;
			latest = () => queueMicrotask(() => resolve(void 0));
			const ready = (async () => {
				if (regions.get(region) !== record) {
					await completion.catch(() => void 0);
					return;
				}
				const ticket = {
					documentGeneration,
					record,
					ticketGeneration: ++record.ticketGeneration,
					value
				};
				record.ticket = ticket;
				record.commit = null;
				const presentingBarrier = barrier;
				const member = presentingBarrier?.members.get(region);
				if (presentingBarrier && member?.record === record) {
					presentingBarrier.completed = false;
					member.ticket = ticket;
					member.commit = null;
					member.retired = false;
				}
				resolveRegionWaiters();
				changed();
				try {
					finish(ticket, "committed", await completion);
				} catch (reason) {
					const superseded = !currentTicket(ticket);
					if (superseded && regions.get(record.region) !== record) return;
					let proof;
					let reported = reason;
					let recovered = false;
					if (failSoft) try {
						proof = failSoft(reason);
						recovered = true;
					} catch (fallbackError) {
						if (fallbackError !== reason) reported = new AggregateError([reason, fallbackError], "presentation and fail-soft failed");
					}
					reportFailure(reported);
					if (superseded) return;
					if (recovered) finish(ticket, "failed", proof);
					else throw reported;
				}
			})();
			ready.catch(() => void 0);
			superseded?.();
			return Object.freeze({
				resolve,
				reject,
				ready
			});
		};
		const disconnect = () => {
			latest?.();
			latest = null;
			if (regions.get(region) !== record) return;
			regions.delete(region);
			const retiringBarrier = barrier;
			const member = retiringBarrier?.members.get(region);
			if (!retiringBarrier || member?.record !== record || retiringBarrier.completed) return;
			member.ticket = null;
			member.commit = null;
			member.retired = true;
			queueMicrotask(() => {
				if (barrier !== retiringBarrier || retiringBarrier.completed || retiringBarrier.members.get(region) !== member || !member.retired) return;
				retiringBarrier.members.delete(region);
				completeBarrier();
				resolveRegionWaiters();
				changed();
			});
		};
		return Object.freeze({
			present,
			disconnect
		});
	}
	function committed(region, renderer, value) {
		const record = regions.get(region);
		return record && record.renderer === renderer && record.commit !== null && Object.is(record.commit.value, value) ? record.commit : null;
	}
	function whenPresented(targetDocument, targetSemanticEpoch) {
		validEpoch(targetSemanticEpoch);
		if (document === null || !Object.is(targetDocument, document)) return Promise.resolve("superseded");
		const repairingCurrentEpoch = targetSemanticEpoch === semanticEpoch && barrier !== null && !barrier.completed;
		if (presentedEpoch >= targetSemanticEpoch && !repairingCurrentEpoch) return Promise.resolve("presented");
		return new Promise((resolve) => {
			waiters.push({
				document: targetDocument,
				semanticEpoch: targetSemanticEpoch,
				resolve
			});
		});
	}
	async function whenCurrentPresented(current) {
		for (;;) {
			const target = current();
			await whenPresented(target.document, target.semanticEpoch);
			if (currentPresented(current)) return "presented";
		}
	}
	function currentPresented(current) {
		const latest = current();
		const reading = read();
		return Object.is(reading.document, latest.document) && reading.semanticEpoch === latest.semanticEpoch && reading.presentedEpoch >= latest.semanticEpoch && reading.sealed && reading.pending.length === 0;
	}
	function currentRegionsPresented(current, wanted) {
		const target = current();
		return target !== null && regionOutcome({
			...target,
			regions: new Set(wanted),
			resolve: () => {}
		}) === "presented";
	}
	async function whenCurrentRegionsPresented(current, regions) {
		const wanted = [...new Set(regions)];
		for (;;) {
			const target = current();
			if (target === null) return "superseded";
			await new Promise((resolve) => {
				const waiter = {
					...target,
					regions: new Set(wanted),
					cancelled: () => current() === null,
					resolve
				};
				const outcome = regionOutcome(waiter);
				if (outcome) resolve(outcome);
				else regionWaiters.push(waiter);
			});
			const latest = current();
			if (latest === null) return "superseded";
			const outcome = regionOutcome({
				...latest,
				regions: new Set(wanted),
				resolve: () => {}
			});
			if (outcome === "presented") return outcome;
		}
	}
	function read() {
		return Object.freeze({
			document,
			semanticEpoch,
			presentedEpoch,
			sealed: barrier?.sealed ?? false,
			pending: Object.freeze(barrier ? [...barrier.members].filter(([, member]) => member.commit === null).map(([region]) => region) : [])
		});
	}
	return Object.freeze({
		begin,
		seal,
		attach,
		committed,
		whenPresented,
		whenCurrentPresented,
		currentPresented,
		whenCurrentRegionsPresented,
		currentRegionsPresented,
		subscribe: (callback) => changes.subscribe(() => d(() => {
			try {
				callback();
			} catch (reason) {
				reportFailure(reason);
			}
		})),
		read
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
				presentation: handle.present(value, failSoft)
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
const pageClaimed = readPart((root) => root.authoritative?.claim_session != null);
const projectView = applicationState.projectView;
const selectWidgets = applicationState.selectWidgets;
const attachApplicationPresentation = (region, renderer) => presentation.attach(region, renderer);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) => ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
const attachWidgetPresentation = (widget, kind, renderer) => presentation.attach(widgetRegion(widget, kind), renderer);
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
//#region runtime/registry.js
const registry = runtime.registry;
const tokenEntry = (name) => registry.$reactions.tokens[name];
const elementDeclarations = () => Object.entries(registry).filter(([tag]) => isElementName(tag));
function adoptRegistry(declarations) {
	for (const [name, value] of Object.entries(declarations)) if (name.startsWith("$")) freeze(value);
	Object.assign(registry, declarations);
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
const declarationFor = (el, key) => registry[el?.localName]?.[key];
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
const renderedChildren = (node) => node.localName === "slot" ? node.assignedNodes({ flatten: true }) : (node.shadowRoot ?? node).childNodes;
const hostIn = (node, root) => {
	let at = node;
	while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
	return at;
};
const overIn = (el, selector, frame) => {
	const near = el.closest(selector);
	return near && (!frame || under(near, frame)) ? near : null;
};
const SAID = "[data-lf-said]";
const UI_MARKS = `.lf-ui, ${SAID}`;
const uiInside = (el, within) => {
	const near = el && overIn(el, ".lf-ui, [data-lf-said]", within);
	return Boolean(near) && !near.matches("[data-lf-said]");
};
const inUi = (node) => uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);
let shadowRules = "";
const SHADOW_LEADING_CSS = `
@layer {
  [hidden]:not([hidden="until-found"]),
  :host([hidden]:not([hidden="until-found"])) {
    display: none !important;
  }
  @media screen {
    @container style(--lf-before-presentation: 1) {
      *,
      *::before,
      *::after {
        transition: none !important;
      }
    }
    @container style(--lf-before-upgrade: 1) {
      .lf-ui {
        visibility: hidden !important;
      }
    }
  }
}`;
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
//#region runtime/stylesheets.js
const sheets = JSON.parse(document.querySelector("script[type=\"application/json\"][data-lf-runtime][data-lf-sheets]").textContent);
const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;
function constructSheet(text) {
	const sheet = new CSSStyleSheet();
	sheet.replaceSync(text);
	return sheet;
}
const chromeSheet = constructSheet(sheets.chrome);
const chromeSharedClasses = Object.freeze([
	"lf-aiming",
	"lf-ins-block",
	"lf-over-item",
	"lf-react-mark",
	"lf-mark-note",
	"lf-ui",
	"lf-version-inline",
	"lf-version-inline-deletion",
	"lf-visual-action"
]);
const marksSheet = constructSheet(sheets.marks);
const annotationMarkSheets = sheets.annotations ? [constructSheet(sheets.annotations.marks)] : [];
const annotationSheets = sheets.annotations ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets] : [];

//#endregion
//#region runtime/keyboard/layer-stack.js
const entries = [];
const watchedRoots = /* @__PURE__ */ new WeakSet();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;
function prune() {
	for (let index = entries.length - 1; index >= 0; index -= 1) if (!entries[index].active()) entries.splice(index, 1);
}
function pushNativeLayer(node, source = null) {
	const at = entries.findIndex((entry) => entry.root === node);
	const existing = at < 0 ? null : entries[at];
	if (existing?.active()) return existing;
	prune();
	const holding = focused();
	const entry = {
		root: node,
		opening: !isNativeLayer(node),
		get kind() {
			return nativeLayerKind(node);
		},
		active() {
			return this.opening || isNativeLayer(node);
		},
		fromNowhere: !holding || holding === document.body,
		opener: holding && holding !== document.body ? holding : null,
		source
	};
	if (entry.opening) queueMicrotask(() => {
		entry.opening = false;
	});
	entries.push(entry);
	return entry;
}
function closing(event) {
	if (event.newState !== "closed") return;
	const entry = entries.find((candidate) => candidate.root === event.target);
	if (entry) entry.opening = false;
	if (entry?.kind === "popover") {
		for (const layer of nativeLayers().toReversed()) if (layer.kind === "modal" && renderedUnder(layer.root, event.target)) closeNativeLayer(layer.root);
	}
	if (entry?.kind === "popover" && entry.fromNowhere && !document.documentElement.inert && canPlaceFocus() && renderedUnder(focused(), event.target)) releaseFocus();
}
HTMLDialogElement.prototype.showModal = function() {
	const entry = nativeLayerKind(this) !== "modal" ? pushNativeLayer(this) : null;
	try {
		return nativeDialogShowModal.call(this);
	} finally {
		if (entry) entry.opening = false;
	}
};
HTMLElement.prototype.showPopover = function(options) {
	const entry = nativeLayerKind(this) !== "popover" ? pushNativeLayer(this) : null;
	try {
		nativePopoverShow.call(this, options);
	} finally {
		if (entry) entry.opening = false;
	}
	if (entry && options?.source) entry.source = options.source;
};
function showNativeLayer(layer, { source, modal = true } = {}) {
	const withholdFocus = Boolean(document.documentElement.lfSample) && !layer.inert;
	if (withholdFocus) layer.inert = true;
	try {
		if (layer instanceof HTMLDialogElement) {
			if (modal) {
				if (source) seatModal(layer, source);
				layer.showModal();
			} else layer.show();
		} else layer.showPopover(source ? { source } : void 0);
	} finally {
		if (withholdFocus) layer.inert = false;
	}
}
const modalHomes = /* @__PURE__ */ new WeakMap();
function seatModal(dialog, source) {
	let place = modalHomes.get(dialog);
	if (!place) {
		place = {
			home: dialog.parentNode,
			chrome: Boolean(dialog.closest(".lf-chrome")),
			scope: null
		};
		modalHomes.set(dialog, place);
		const restore = () => {
			if (dialog.parentNode !== place.home) move(place.home, dialog);
			place.scope?.remove();
		};
		dialog.addEventListener("close", () => {
			if (!dialog.open) restore();
		});
		watchOwner(dialog, { disconnect() {
			if (dialog.parentNode === place.home) return;
			closeNativeLayer(dialog);
			restore();
		} });
	}
	const holder = nativeLayerHolding(source);
	let seat = place.home;
	if (nativeLayerKind(holder) === "popover") {
		if (renderedUnder(holder, place.home)) seat = holder;
		else if (place.chrome) {
			if (!place.scope) {
				place.scope = document.createElement("div");
				place.scope.className = "lf-chrome";
			}
			const root = holder.getRootNode();
			if (root instanceof ShadowRoot && !root.adoptedStyleSheets.includes(chromeSheet)) root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
			if (place.scope.parentNode !== holder) move(holder, place.scope);
			seat = place.scope;
		}
	}
	if (dialog.parentNode !== seat) move(seat, dialog);
}
function closeNativeLayer(layer) {
	const dialog = layer instanceof HTMLDialogElement;
	if (dialog ? !layer.open : !isNativeLayer(layer)) return;
	const currentLocation = focused();
	const returnTo = entries.find((entry) => entry.root === layer)?.opener;
	const returnLocally = document.documentElement.lfSample && currentLocation && renderedUnder(currentLocation, layer);
	const inhibited = document.documentElement.lfSample ? [document.documentElement, ...nativeLayers().filter((entry) => entry.kind === "modal").map((entry) => entry.root)].filter((node) => !node.inert) : [];
	closeLayer(() => {
		for (const node of inhibited) node.inert = true;
		try {
			if (dialog) layer.close();
			else layer.hidePopover();
		} finally {
			for (const node of inhibited) node.inert = false;
		}
	}, returnLocally && (() => {
		if (!canPlaceFocus()) return;
		if (returnTo) handBack(returnTo);
		else releaseFocus();
	}));
}
const changeListeners = /* @__PURE__ */ new Set();
function watchLayerChanges(listener) {
	changeListeners.add(listener);
	return () => changeListeners.delete(listener);
}
const changed = (event) => {
	if (!event.target?.matches?.("[popover], dialog")) return;
	for (const listener of changeListeners) listener(event);
};
function watchLayers(root) {
	if (watchedRoots.has(root)) return;
	watchedRoots.add(root);
	const opened = (event) => {
		if (event.newState === "open" && event.target?.matches?.("[popover], dialog")) pushNativeLayer(event.target, event.source);
	};
	root.addEventListener("beforetoggle", opened, true);
	root.addEventListener("beforetoggle", closing, true);
	root.addEventListener("toggle", opened, true);
	root.addEventListener("toggle", changed, true);
}
watchLayers(document);
function nativeLayers() {
	prune();
	return entries.filter((entry) => entry.active());
}
const NATIVE_LAYERS = Symbol.for("leaf.nativeLayers");
Object.defineProperty(document, NATIVE_LAYERS, { value: nativeLayers });
function nativeModalAdmits(node) {
	const owner = node.ownerDocument;
	const reading = owner[NATIVE_LAYERS];
	if (reading) {
		const modal = reading().findLast((layer) => layer.kind === "modal")?.root;
		return !modal || renderedUnder(node, modal);
	}
	return [...owner.querySelectorAll("dialog")].filter((dialog) => nativeLayerKind(dialog) === "modal").every((modal) => renderedUnder(node, modal));
}
function dismissPopoversOutside(root) {
	for (const entry of nativeLayers().toReversed()) if (entry.kind === "popover" && entry.root.popover !== "manual" && !renderedUnder(entry.root, root)) closeNativeLayer(entry.root);
}

//#endregion
//#region runtime/rect.js
const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;
const BOTH = {
	x: true,
	y: true
};
const intersect = (a, b, axes = BOTH) => ({
	left: axes.x ? Math.max(a.left, b.left) : a.left,
	top: axes.y ? Math.max(a.top, b.top) : a.top,
	right: axes.x ? Math.min(a.right, b.right) : a.right,
	bottom: axes.y ? Math.min(a.bottom, b.bottom) : a.bottom
});
const hasArea = (box) => box.right > box.left && box.bottom > box.top;
function union(boxes) {
	if (!boxes.length) return null;
	const left = Math.min(...boxes.map((box) => box.left));
	const top = Math.min(...boxes.map((box) => box.top));
	const right = Math.max(...boxes.map((box) => box.right));
	const bottom = Math.max(...boxes.map((box) => box.bottom));
	return {
		left,
		top,
		right,
		bottom,
		width: right - left,
		height: bottom - top
	};
}
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
function nearestScrollBy(start, end, low, high) {
	if (start < low && end > high) return 0;
	const oversized = end - start > high - low;
	if (start < low) return oversized ? end - high : start - low;
	if (end > high) return oversized ? start - low : end - high;
	return 0;
}
const clippingAxes = (style) => {
	const clips = /^(hidden|clip|scroll|auto)$/;
	const both = /paint|strict|content/.test(style.contain) || /^(auto|hidden)$/.test(style.contentVisibility);
	return {
		x: both || clips.test(style.overflowX),
		y: both || clips.test(style.overflowY)
	};
};

//#endregion
//#region runtime/geometry.js
const shellRight = () => document.body.getBoundingClientRect().right;
const windowChrome = /* @__PURE__ */ new Map();
const chromeSizes = sizeObserver(() => announceRoom(document));
const watchChrome = (element) => chromeSizes.observe(element, { box: "border-box" });
const declareWindowChrome = (boxes, elements) => {
	windowChrome.set(boxes, elements);
	elements.forEach(watchChrome);
};
const standsIn = (node, elements) => Boolean(node) && elements.some((element) => under(node, element));
const inWindowChrome = (node) => [...windowChrome.values()].some((elements) => standsIn(node, elements));
const windowChromeBoxes = (item = null) => [...windowChrome].filter(([, elements]) => !standsIn(item, elements)).flatMap(([boxes]) => boxes());
const layoutWindow = (doc = document) => ({
	left: 0,
	top: 0,
	right: doc.documentElement.clientWidth,
	bottom: doc.documentElement.clientHeight
});
function shownWindow({ within = null, gap = 0, viewport = "visual", item = null } = {}) {
	const layout = layoutWindow();
	const { offsetLeft, offsetTop, width, height } = viewport === "visual" ? window.visualViewport : {
		offsetLeft: 0,
		offsetTop: 0,
		width: layout.right,
		height: layout.bottom
	};
	const left = Math.max(offsetLeft, within?.left ?? -Infinity) + gap;
	const right = Math.min(offsetLeft + width, within?.right ?? Infinity) - gap;
	let top = Math.max(offsetTop, within?.top ?? -Infinity);
	let bottom = Math.min(offsetTop + height, within?.bottom ?? Infinity);
	const middle = offsetTop + height / 2;
	for (const box of windowChromeBoxes(item)) {
		if (!overlapsAcross(box, {
			left,
			right
		})) continue;
		if (box.top + box.bottom < 2 * middle) top = Math.max(top, box.bottom);
		else bottom = Math.min(bottom, box.top);
	}
	top += gap;
	bottom -= gap;
	return new DOMRect(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
}
function shownBand(el) {
	const doc = el.ownerDocument;
	if (el === doc.scrollingElement) return layoutWindow(doc);
	const s = doc.defaultView.getComputedStyle(el);
	const axes = clippingAxes(s);
	if (!axes.x && !axes.y) return null;
	const b = el.getBoundingClientRect();
	const scaleX = el.offsetWidth ? b.width / el.offsetWidth : 1;
	const scaleY = el.offsetHeight ? b.height / el.offsetHeight : 1;
	const left = b.left + el.clientLeft * scaleX, top = b.top + el.clientTop * scaleY;
	return {
		left,
		top,
		right: left + el.clientWidth * scaleX,
		bottom: top + el.clientHeight * scaleY
	};
}
const scrollport = (overflow) => /^(auto|scroll|hidden)$/.test(overflow);
const userScrollport = (overflow) => /^(auto|scroll)$/.test(overflow);
const scrollsBy = ({ overflowX, overflowY }) => scrollport(overflowX) || scrollport(overflowY);
const scrolls = (el) => scrollsBy(getComputedStyle(el));
const scrollContainer = (box) => box === box.ownerDocument.scrollingElement || scrolls(box);
function scrollsContent(box) {
	if (!(box instanceof Element) || box instanceof SVGElement) return false;
	const style = getComputedStyle(box);
	return scrollport(style.overflowX) && box.scrollWidth > box.clientWidth || scrollport(style.overflowY) && box.scrollHeight > box.clientHeight;
}
const slotHolder = (el, scroller) => {
	let at = el;
	for (let box = el; box && box !== scroller; box = upFrom(box)) if (box.nodeType === 1 && scrolls(box)) at = upFrom(box);
	return at;
};
const insetAt = (at, scroller, slot, padding) => {
	const read = (box) => Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
	const inset = at?.nodeType === 1 ? read(at) : 0;
	if (inset <= read(scroller)) return 0;
	return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
const TOP = ["--lf-top", "paddingTop"];
function slotTop(scroller) {
	const style = getComputedStyle(scroller);
	return (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.getPropertyValue("--lf-top")) || 0);
}
const FOOT = ["--lf-bottom", "paddingBottom"];
const edgeInset = (el, scroller, edge) => !scrollContainer(scroller) || el === scroller ? 0 : insetAt(slotHolder(el, scroller), scroller, ...edge);
const headerInset = (el, scroller) => edgeInset(el, scroller, TOP);
const footerInset = (el, scroller) => edgeInset(el, scroller, FOOT);
function visibleBand(scroller, item = null) {
	const band = shownBand(scroller);
	if (!band || !item) return band;
	const top = band.top + headerInset(item, scroller);
	const bottom = band.bottom - footerInset(item, scroller);
	return bottom > top ? {
		...band,
		top,
		bottom
	} : null;
}
const OPEN = 1e5;
function headerCuts(item, clips = /* @__PURE__ */ new Map()) {
	return clipWalk(item, clips, false).cuts.filter(({ covered, footed }) => covered || footed).reverse().map(({ box, band, covered, footed }) => ({
		box,
		band: band && {
			left: band.left - OPEN,
			right: band.right + OPEN,
			top: covered ? band.top : band.top - OPEN,
			bottom: footed ? band.bottom : band.bottom + OPEN
		}
	}));
}
function stuckBox(node, within = null) {
	for (let el = node; el?.nodeType === 1 && el !== within; el = renderedParent(el)) {
		const style = getComputedStyle(el);
		if (style.position === "sticky" ? sticks(el) : inWindow(el, style)) return el;
	}
	return null;
}
const inWindow = (el, style) => style.position === "fixed" && el.offsetParent === null && !style.positionAnchor.startsWith("--");
function sticks(sticky) {
	let scroller = renderedParent(sticky);
	while (scroller?.nodeType === 1 && !scrollContainer(scroller)) scroller = renderedParent(scroller);
	if (scroller?.nodeType !== 1) return false;
	const band = shownBand(scroller);
	if (!band) return false;
	const style = getComputedStyle(sticky);
	const room = getComputedStyle(scroller);
	const padTop = Number.parseFloat(room.paddingTop) || 0;
	const padBottom = Number.parseFloat(room.paddingBottom) || 0;
	const box = sticky.getBoundingClientRect();
	let parent = renderedParent(sticky);
	while (parent !== scroller && getComputedStyle(parent).display === "contents") parent = renderedParent(parent);
	const content = band.top - scroller.scrollTop;
	const holder = parent === scroller ? {
		top: content + padTop,
		bottom: content + scroller.scrollHeight - padBottom
	} : shownBox(parent);
	const topLine = band.top + padTop + Number.parseFloat(style.top);
	const footLine = band.bottom - padBottom - Number.parseFloat(style.bottom);
	if (box.top <= topLine + 1 && holder.top < box.top - 1) return true;
	if (Math.abs(box.bottom - footLine) <= 1) return true;
	return box.bottom > footLine && holder.bottom > box.bottom + 1;
}
function landingBand(scroller) {
	const band = shownBand(scroller);
	if (!band) return null;
	const inset = landingInsets(scroller);
	return {
		left: band.left + inset.left,
		top: band.top + inset.top,
		right: band.right - inset.right,
		bottom: band.bottom - inset.bottom
	};
}
function landingInsets(scroller) {
	const style = getComputedStyle(scroller);
	const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
	return {
		top: inset("Top"),
		right: inset("Right"),
		bottom: inset("Bottom"),
		left: inset("Left")
	};
}
const skipped = (el) => document.documentElement.lfInitial.skipped(el, renderedParent);
function shownBox(el) {
	if (el === document.scrollingElement) {
		const { left, top, right, bottom } = shownBand(el);
		return new DOMRect(left, top, right - left, bottom - top);
	}
	const r = el.getBoundingClientRect();
	if (r.width || r.height || skipped(el) || getComputedStyle(el).display !== "contents") return r;
	const contents = document.createRange();
	contents.selectNodeContents(el);
	return contents.getBoundingClientRect();
}
function shownParts(el) {
	const r = el.getBoundingClientRect();
	if (r.width && r.height) return [el];
	return [...el.children].filter((child) => !uiInside(child, el)).flatMap((child) => shownParts(child));
}
const shownExtent = (el) => union(shownParts(el).map((part) => part.getBoundingClientRect()));
function shownRect(item, clips) {
	return clippedRect(shownBox(item), item, clips);
}
function seenRect(item, clips, box = shownBox(item)) {
	const shown = clippedRect(box, item, clips);
	if (!shown) return null;
	const room = shownWindow({
		within: shown,
		item
	});
	return room.width > 0 && room.height > 0 ? {
		left: shown.left,
		top: room.top,
		right: shown.right,
		bottom: room.bottom
	} : null;
}
const showsContents = (node, options) => node.getAttribute("hidden") !== "until-found" && node.checkVisibility(options);
function presented(node) {
	if (!showsContents(node, { visibilityProperty: true }) || excludedByInert(node) || !nativeModalAdmits(node)) return false;
	for (let at = node; at; at = renderedParent(at)) if (at.getAttribute?.("aria-hidden") === "true") return false;
	return true;
}
function frameView(frame, within) {
	const seen = seenRect(frame, /* @__PURE__ */ new Map());
	const shown = seen && intersect(seen, within);
	if (!shown || !hasArea(shown)) return null;
	const rect = frame.getBoundingClientRect();
	const scaleX = rect.width / frame.offsetWidth || 1;
	const scaleY = rect.height / frame.offsetHeight || 1;
	const x = (at) => (at - rect.left) / scaleX - frame.clientLeft;
	const y = (at) => (at - rect.top) / scaleY - frame.clientTop;
	return {
		left: x(shown.left),
		top: y(shown.top),
		right: x(shown.right),
		bottom: y(shown.bottom)
	};
}
const ROOM_MOVED = "lf-room-moved";
const announceRoom = (target) => target.dispatchEvent(new Event(ROOM_MOVED, {
	bubbles: true,
	composed: true
}));
function watchRoom(callback) {
	const viewport = window.visualViewport;
	const listening = [
		[window, "resize"],
		[viewport, "scroll"],
		[viewport, "resize"],
		[
			document,
			ROOM_MOVED,
			true
		]
	];
	for (const [target, type, capture] of listening) target.addEventListener(type, callback, capture);
	const stops = [
		watchScrolls(callback),
		watchLayerChanges(callback),
		() => {
			for (const [target, type, capture] of listening) target.removeEventListener(type, callback, capture);
		}
	];
	return () => {
		for (const stop of stops) stop();
	};
}
function motionBand(item, clips) {
	const walk = clipWalk(item, clips, false);
	const cut = cutBy({
		left: -Infinity,
		top: -Infinity,
		right: Infinity,
		bottom: Infinity
	}, walk.cuts.map((each) => ({
		...each,
		axes: {
			...each.axes,
			x: false
		}
	})), item.ownerDocument.scrollingElement, true);
	if (!cut) return null;
	const room = shownWindow({ within: cut });
	if (room.height <= 0) return null;
	const scroller = walk.cuts.find(({ box, scrolls }) => scrolls && box.scrollHeight > box.clientHeight)?.box;
	const anchors = !scroller ? cut.top : scroller.scrollTop > 0 ? landingBand(scroller).top : shownBand(scroller).top;
	return anchors < room.bottom ? {
		top: anchors,
		bottom: room.bottom
	} : null;
}
function growthIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { top, bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return Boolean(band) && bottom > band.top && top < band.bottom;
}
function growthAfterIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return Boolean(band) && bottom > band.top && bottom < band.bottom;
}
const watches = /* @__PURE__ */ new Set();
let watchPass = null;
let unlisten = null;
const readWatches = () => {
	watchPass = null;
	const clips = /* @__PURE__ */ new Map();
	const left = [...watches].filter((watch) => watch.read(clips));
	for (const watch of left) if (watches.has(watch)) watch.leave();
};
const rereadWatches = () => {
	watchPass ??= nextRender(readWatches);
};
function whenNone(nodes, holds, leave) {
	let held = null;
	const watch = {
		leave,
		read(clips) {
			const now = nodes.some((node) => node.isConnected && Boolean(holds(node, clips)));
			const stopped = !now && held !== false;
			held = now;
			return stopped;
		}
	};
	watches.add(watch);
	unlisten ??= watchRoom(rereadWatches);
	const observer = new IntersectionObserver(rereadWatches);
	for (const node of nodes) observer.observe(node);
	return () => {
		observer.disconnect();
		watches.delete(watch);
		if (watches.size) return;
		unlisten();
		unlisten = null;
		if (watchPass !== null) cancelRender(watchPass);
		watchPass = null;
	};
}
const startsAt = (item, clips) => {
	const fragments = item.getClientRects();
	return (fragments.length ? [...fragments] : [shownBox(item)]).map((box) => clippedRect(box, item, clips)).find(Boolean);
};
const clippedRect = (box, item, clips) => clipped(box, item, clips, false);
function paintClips(item, box, clips, aboveSurfaces, held = false) {
	const walk = clipWalk(item, clips, held);
	const plane = walk.fixed ? "window" : "page";
	const root = item.ownerDocument.scrollingElement;
	const hidden = {
		plane,
		window: {
			left: 0,
			top: 0,
			right: 0,
			bottom: 0
		},
		bands: []
	};
	let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
	const bands = walk.cuts.filter(({ box: cut }) => cut !== root).reverse();
	let shown = cutBy(box, walk.cuts, root, false);
	if (!shown) return walk.cuts.some(({ band }) => !band) ? hidden : {
		plane,
		window: window ?? null,
		bands
	};
	for (const { surface, box: over, level } of aboveSurfaces ? openOccluders(clips) : []) {
		if (!overlaps(shown, over) || under(item, surface) || stackLevel(item) >= level) continue;
		const left = uncovered(shown, over);
		if (!left) return hidden;
		window ??= shownBand(root);
		window = {
			left: left.left > shown.left ? Math.max(window.left, over.right) : window.left,
			top: left.top > shown.top ? Math.max(window.top, over.bottom) : window.top,
			right: left.right < shown.right ? Math.min(window.right, over.left) : window.right,
			bottom: left.bottom < shown.bottom ? Math.min(window.bottom, over.top) : window.bottom
		};
		shown = left;
	}
	return {
		plane,
		window: window ?? null,
		bands
	};
}
const pagePlaneRect = (box, item, clips) => clipped(box, item, clips, false, false);
const nearObserver = (callback) => new IntersectionObserver(callback, {
	rootMargin: "100%",
	scrollMargin: "600px"
});
function nearWindow(target, clips = /* @__PURE__ */ new Map()) {
	if (!target.checkVisibility()) return false;
	const box = pagePlaneRect(shownBox(target), target, clips);
	const { right: width, bottom: height } = layoutWindow();
	return Boolean(box) && box.bottom >= -height && box.top <= 2 * height && box.right >= -width && box.left <= 2 * width;
}
const clippedContents = (box, holder, clips) => clipped(box, holder, clips, true);
function clipped(box, item, clips, held, inWindow = true) {
	const root = item.ownerDocument.scrollingElement;
	const shown = cutBy(box, clipWalk(item, clips, held).cuts, root, inWindow);
	return shown && occluded(shown, item, clips);
}
function cutBy(box, cuts, root, inWindow) {
	let shown = inWindow ? intersect(box, layoutWindow()) : box;
	for (const { box: cut, band, axes, covered } of cuts) {
		if (!band) return null;
		const edges = !inWindow && cut === root ? {
			left: -Infinity,
			top: covered ? band.top : -Infinity,
			right: Infinity,
			bottom: Infinity
		} : band;
		shown = intersect(shown, edges, axes);
	}
	const { left, top, right, bottom } = shown;
	return hasArea(shown) ? {
		left,
		top,
		right,
		bottom
	} : null;
}
function clipWalk(item, clips, held) {
	let holder = item;
	let escaped = false, containing = null;
	const cuts = [];
	for (let a = item; a; a = upFrom(a)) {
		let c = clips.get(a);
		if (c === void 0) clips.set(a, c = {
			band: shownBand(a),
			axes: a === a.ownerDocument.scrollingElement ? {
				x: true,
				y: true
			} : clippingAxes(getComputedStyle(a)),
			positioned: a.offsetParent !== void 0 && ["fixed", "absolute"].includes(getComputedStyle(a).position),
			block: a.offsetParent,
			scrolls: scrollContainer(a)
		});
		if (escaped && a === containing) escaped = false;
		if (!escaped && (held || a !== item) && c.band) {
			const covered = c.band.top + (c.scrolls ? insetAt(holder, a, ...TOP) : 0);
			const footed = c.band.bottom - (c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
			cuts.push({
				box: a,
				axes: c.axes,
				scrolls: c.scrolls,
				covered: c.axes.y && covered > c.band.top,
				footed: c.axes.y && footed < c.band.bottom,
				band: c.axes.y && covered >= footed ? null : c.axes.y ? {
					...c.band,
					top: covered,
					bottom: footed
				} : c.band
			});
		}
		if (c.scrolls) holder = upFrom(a);
		if (!escaped && c.positioned) {
			escaped = true;
			containing = c.block;
		}
	}
	return {
		cuts,
		fixed: escaped && !containing
	};
}
const occluders = /* @__PURE__ */ new Set();
const standsNow = (surface) => surface.checkVisibility();
function restingBox(surface) {
	let left = 0, top = 0;
	for (let at = surface; at; at = at.offsetParent) {
		left += at.offsetLeft + (at === surface ? 0 : at.clientLeft);
		top += at.offsetTop + (at === surface ? 0 : at.clientTop);
	}
	return {
		left,
		top,
		right: left + surface.offsetWidth,
		bottom: top + surface.offsetHeight
	};
}
const declareOccluder = (surface) => {
	occluders.add(surface);
	watchChrome(surface);
	return () => {
		occluders.delete(surface);
		chromeSizes.unobserve(surface);
		announceRoom(document);
	};
};
function rightCover() {
	const edge = layoutWindow().right;
	let left = Infinity;
	for (const surface of occluders) {
		if (!standsNow(surface)) continue;
		const box = restingBox(surface);
		if (box.left > 0 && box.right >= edge - 1) left = Math.min(left, box.left);
	}
	return left;
}
const PAST = Symbol("past");
const clipsPast = (surfaces) => /* @__PURE__ */ new Map([[PAST, new Set(surfaces)]]);
const clipsPastSurfaces = () => clipsPast(occluders);
function hides(surface, where) {
	const holder = placeHolder(where);
	if (!holder || !occluders.has(surface) || !standsNow(surface)) return false;
	if (under(holder, surface) || stackLevel(holder) >= stackLevel(surface)) return false;
	const box = placeBox(where);
	const { left, top, right, bottom } = clippedPlace(where, clipsPast([surface]), box) ?? box;
	const over = restingBox(surface);
	const across = Math.min(right, over.right) - Math.max(left, over.left);
	const room = shownWindow({ viewport: "layout" });
	if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1) return across > (right - left) / 2;
	const down = Math.min(bottom, over.bottom) - Math.max(top, over.top);
	return across > 0 && down > 0 && across * down > (right - left) * (bottom - top) / 2;
}
const underOccluder = (where) => [...occluders].some((surface) => hides(surface, where));
const placeHolder = (where) => where instanceof Range ? where.startContainer instanceof Element ? where.startContainer : where.startContainer.parentElement : where;
const placeBox = (where) => where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
const clippedPlace = (where, clips, box = placeBox(where)) => where instanceof Range ? clippedContents(box, placeHolder(where), clips) : clippedRect(box, where, clips);
function stackLevel(node) {
	let level = 0;
	for (let a = node; a; a = renderedParent(a)) {
		if (isNativeLayer(a)) return Infinity;
		const { position, zIndex } = getComputedStyle(a);
		if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
	}
	return level;
}
const OCCLUDERS = Symbol("occluders");
function openOccluders(clips) {
	let open = clips.get(OCCLUDERS);
	if (open) return open;
	const past = clips.get(PAST);
	open = [...occluders].filter(standsNow).filter((surface) => !past?.has(surface)).map((surface) => ({
		surface,
		box: restingBox(surface),
		level: stackLevel(surface)
	}));
	clips.set(OCCLUDERS, open);
	return open;
}
const area = (box) => (box.right - box.left) * (box.bottom - box.top);
function occluded(rect, item, clips) {
	for (const { surface, box, level } of openOccluders(clips)) {
		if (!overlaps(rect, box) || under(item, surface) || stackLevel(item) >= level) continue;
		rect = uncovered(rect, box);
		if (!rect) return null;
	}
	return rect;
}
function uncovered(rect, box) {
	if (!overlaps(rect, box)) return rect;
	const sides = [
		{
			...rect,
			right: Math.min(rect.right, box.left)
		},
		{
			...rect,
			left: Math.max(rect.left, box.right)
		},
		{
			...rect,
			bottom: Math.min(rect.bottom, box.top)
		},
		{
			...rect,
			top: Math.max(rect.top, box.bottom)
		}
	].filter((side) => side.right > side.left && side.bottom > side.top);
	return sides.length ? sides.reduce((most, side) => area(side) > area(most) ? side : most) : null;
}

//#endregion
export { AsyncDirective, COLLAPSE, DELIVERY, DRAFT_FORMAT, Directive, LIVE_ROOT, LitElement, PAGE_ROOT, PENDING, PRESENTATION_DOM, PartType, SAID, SHADOW_LEADING_CSS, SHARE_ROOT, TEXT_BLOCK, UI_MARKS, WEBSITE_DELIVERY, actionForWidget, adoptRegistry, agentName, anchorKey, annotationMarkSheets, annotationMode, annotationSheets, applicationPresented, applicationPresenter, applicationRegionsPresented, applicationState, attachApplicationPresentation, attachWidgetPresentation, authoredRank, bareReaction, carriesObligation, chromeSharedClasses, chromeSheet, clamp, classMap, clippedContents, clippedPlace, clippingAxes, clipsPastSurfaces, closeNativeLayer, createPresentationSchedule, createRef, decisionFor, declarationFor, declareOccluder, declareWindowChrome, declaredRoot, describeFailure, directive, discussed, dismissPopoversOutside, documentChanged, drawingSchema, editable, elementDeclarations, elementsDeclaring, exhibits, foldWidgetStates, frameFor, frameView, growthAfterIsSeen, growthIsSeen, guard, hasArea, headerCuts, headerInset, hostIn, html, inBaseLayer, inUi, inWindowChrome, intersect, isElementName, isMessageEvent, isNews, isReaction, isThreadEvent, itemNoun, itemOutcome, keyed, landingBand, landingInsets, lastMovedAt, layerFact, layerRoot, layoutWindow, live, loadShadowRules, marks, marksSheet, matchesWhen, messageKey, moved, nativeLayers, nativeModalAdmits, nearObserver, nearWindow, nearestScrollBy, noChange, nothing, obligationValue, offlineData, offlineInteractive, offlineState, overIn, overlaps, overlapsAcross, pageClaimed, pageShadowRoots, pageUrl, paintClips, pendingForParent, placeBox, placeHolder, presentDocument, presented, projectView, projectionOrigins, projectionRegionsPresented, queueWidgetUpdate, rankAt, reactionsAt, readApplication, readApplicationPresentation, readPart, recordedWidgetSelector, ref, refuseShadowRoot, registry, render, renderedChildren, repeat, revisionLabel, rightCover, runtime, runtimeModule, runtimeResource, sameAnchor, scrollContainer, scrollGlides, scrolling, scrollsBy, scrollsContent, seatRoot, seenRect, selectWidgets, setPresentationFailureReporter, shadowRootsIn, shadowRules, share, shareUrl, shellRight, showNativeLayer, shownBand, shownBox, shownExtent, shownParts, shownRect, shownWindow, showsContents, skipped, slotTop, stackLevel, startsAt, stateCoordinate, stateSpecs, stuckBox, styleMap, tagsDeclaring, threadCounts, threadKey, threadNames, tick, tokenChoices, tokenEntry, turns, uiInside, underOccluder, union, unsafeHTML, userScrollport, visibleBand, watchArrivals, watchArrivalsIn, watchLayerChanges, watchLayers, watchOwner, watchPresentation, watchRoom, watchScrollEnds, watchScrolls, watchSemantic, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whenNone, whenWidgetsPresented, whileConnected, windowChromeBoxes };