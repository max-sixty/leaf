import { ANNOUNCE, COMMANDS, PAGE_PAINT_ATTRIBUTE, actionName, actionTemplate, commandsChangedOn, elementDirective, exceptionText, failureContext, failureOf, generatedElement, isNativeLayer, keeps, keepsText, nextRender, offer, offerAction, refuseCommands, renderedParent, renderedUnder, showAction, under } from "./bundle-portable.js";
import { AsyncDirective, CARET_KEYS, DELIVERY, PAGE_ROOT, PRESSES, PartType, TEXT_BOX, WORKS, Z, coarsePointer, controlNavigationKeys, directive, focusDestination, focusRevision, focused, html, move, nothing, offlineInteractive, onCurrentLocation, onFocusVisibility, pageShadowRoots, pageUrl, pressIsKeyboardActivation, render, runtime, showNativeLayer, tagsDeclaring, takesLetters, x } from "./bundle-layer-stack.js";

//#region runtime/root-state.js
const setRuntimeRootAttribute = (...args) => document.documentElement.lfRootState.setRuntimeRootAttribute(...args);
const setRuntimeRootStyle = (...args) => document.documentElement.lfRootState.setRuntimeRootStyle(...args);
const removeRuntimeRootStyle = (...args) => document.documentElement.lfRootState.removeRuntimeRootStyle(...args);
const runtimeRootState = (root) => ({
	attributes: document.documentElement.lfRootState.attributes(root),
	styles: document.documentElement.lfRootState.styles(root)
});

//#endregion
//#region runtime/traffic.js
const ledger = {
	sends: 0,
	acked: 0,
	asked: 0,
	heard: 0,
	pending: []
};
function paint() {
	setRuntimeRootAttribute(document.documentElement, PAGE_PAINT_ATTRIBUTE.traffic, JSON.stringify(ledger));
}
function countTraffic(key) {
	ledger[key] += 1;
	paint();
}
function watchPendingTraffic(sending) {
	let first = true;
	return sending.subscribe((attempts) => {
		const initial = first;
		first = false;
		if (initial && !attempts.length) return;
		ledger.pending = [...attempts];
		paint();
	});
}

//#endregion
//#region runtime/ids.js
const randomId = () => Array.from(crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join("");

//#endregion
//#region runtime/interaction-log.js
const enabled = PAGE_ROOT !== null;
const url = enabled ? new URL("api/interaction", PAGE_ROOT).href : null;
const root = enabled ? new URL(PAGE_ROOT).pathname.replace(/\/$/, "") : "";
const session = randomId();
const queue = [];
const MAX_PENDING_ENTRIES = 512;
const repetitive = /* @__PURE__ */ new Set([
	"resource",
	"pointermove",
	"pointerover",
	"pointerout",
	"pointerenter",
	"pointerleave",
	"wheel",
	"scroll",
	"selectionchange",
	"drag",
	"dragover",
	"touchmove",
	"compositionupdate"
]);
const encoder = new window.TextEncoder();
const nodeIds = /* @__PURE__ */ new WeakMap();
let nextSequence = 0;
let nextNodeId = 0;
let sending = false;
let inFlightCount = 0;
let scheduled = null;
const timestamp = () => (/* @__PURE__ */ new Date()).toISOString();
const pagePath = (pathname) => pathname === root || pathname === `${root}/` ? "/" : pathname.startsWith(`${root}/`) ? pathname.slice(root.length) : pathname;
function locator(node) {
	const id = node.id ? `#${node.id}` : "";
	const name = node.getAttribute("name");
	const named = name ? `[name=${JSON.stringify(name)}]` : "";
	return `${node.localName}${id}${named}`;
}
function nodeIdentity(node) {
	if (!nodeIds.has(node)) nodeIds.set(node, ++nextNodeId);
	return nodeIds.get(node);
}
function targetValue(target) {
	if (target instanceof window.HTMLInputElement) {
		if (target.type === "checkbox" || target.type === "radio") return {
			checked: target.checked,
			value: target.value
		};
		return { value: target.value };
	}
	if (target instanceof Element && target.matches(`${TEXT_BOX}, select`)) return { value: target.value };
	if (target instanceof HTMLElement && target.isContentEditable) return { value: target.textContent };
	return {};
}
function describe(event) {
	const path = event.composedPath();
	const elements = path.filter((node) => node instanceof Element).slice(0, 8);
	const entry = {
		type: event.type,
		target: elements.map(locator),
		nodes: elements.map(nodeIdentity),
		trusted: event.isTrusted
	};
	const target = path[0];
	const control = path.find((node) => node instanceof Element && node.matches(`button, a, summary, input, select, ${TEXT_BOX}, [role=button]`));
	if (control) {
		entry.control = locator(control);
		entry.controlNode = nodeIdentity(control);
	}
	const labelTarget = control ?? target;
	if (labelTarget instanceof Element) {
		const label = labelTarget.getAttribute("aria-label") || labelTarget.getAttribute("title");
		if (label) entry.label = label;
		else if (control) entry.label = control.textContent?.trim().slice(0, 200);
	}
	if (event instanceof window.KeyboardEvent) {
		entry.key = event.key;
		entry.code = event.code;
		entry.repeat = event.repeat;
		entry.modifiers = [
			"Alt",
			"Control",
			"Meta",
			"Shift"
		].filter((name) => event.getModifierState(name));
	} else if (event instanceof window.PointerEvent) entry.pointer = {
		id: event.pointerId,
		type: event.pointerType,
		button: event.button,
		buttons: event.buttons,
		x: event.clientX,
		y: event.clientY
	};
	else if (event instanceof window.WheelEvent) entry.delta = [
		event.deltaX,
		event.deltaY,
		event.deltaMode
	];
	else if (event instanceof window.MouseEvent) entry.pointer = {
		button: event.button,
		x: event.clientX,
		y: event.clientY
	};
	if (event instanceof window.InputEvent) {
		entry.inputType = event.inputType;
		entry.data = event.data;
	}
	if (event instanceof window.CompositionEvent) entry.data = event.data;
	if (event instanceof window.ClipboardEvent) entry.clipboard = event.clipboardData?.getData("text/plain") ?? "";
	if (event.changedTouches) entry.touches = [...event.changedTouches].map((touch) => ({
		id: touch.identifier,
		x: touch.clientX,
		y: touch.clientY
	}));
	if (event instanceof window.DragEvent && event.dataTransfer?.files.length) entry.files = [...event.dataTransfer.files].map((file) => ({
		name: file.name,
		size: file.size,
		type: file.type
	}));
	if ([
		"beforeinput",
		"input",
		"change"
	].includes(event.type)) Object.assign(entry, targetValue(target));
	if (event.type === "scroll") {
		const scroller = target === document ? document.scrollingElement : target;
		if (scroller instanceof Element) entry.scroll = [scroller.scrollLeft, scroller.scrollTop];
	}
	if (event.type === "selectionchange") entry.selection = document.getSelection()?.toString() ?? "";
	if ([
		"hashchange",
		"popstate",
		"pageshow",
		"pagehide"
	].includes(event.type)) entry.location = `${pagePath(location.pathname)}${location.hash}`;
	if (event.type === "resize") entry.viewport = [window.innerWidth, window.innerHeight];
	if (event.type === "visibilitychange") entry.visibility = document.visibilityState;
	if (["beforetoggle", "toggle"].includes(event.type) && target instanceof Element) entry.open = target.open === true || isNativeLayer(target);
	if (event.type === "fullscreenchange") entry.fullscreen = document.fullscreenElement ? {
		target: locator(document.fullscreenElement),
		node: nodeIdentity(document.fullscreenElement)
	} : null;
	return entry;
}
function schedule(delay = 250) {
	if (scheduled !== null || sending || !queue.length) return;
	scheduled = setTimeout(() => {
		scheduled = null;
		flush();
	}, delay);
}
function append(row) {
	if (queue.length >= MAX_PENDING_ENTRIES) {
		let evict = queue.findIndex((entry, index) => index >= inFlightCount && entry.repetitive);
		if (evict < 0) {
			if (row.repetitive) return;
			evict = inFlightCount;
			if (evict >= queue.length) return;
		}
		queue.splice(evict, 1);
	}
	queue.push(row);
}
function enqueue(entry) {
	if (!enabled) return;
	const common = {
		observed_at: timestamp(),
		monotonic_ms: performance.now(),
		visibility: document.visibilityState,
		sequence: ++nextSequence
	};
	let body = JSON.stringify({
		...entry,
		...common
	});
	let bytes = encoder.encode(body).length;
	if (bytes > 4e4) {
		body = JSON.stringify({
			...common,
			type: "interaction_omitted",
			originalType: entry.type,
			bytes,
			reason: "record_exceeds_limit"
		});
		bytes = encoder.encode(body).length;
	}
	append({
		body,
		bytes,
		repetitive: repetitive.has(entry.type)
	});
	schedule();
}
function batch(start, maxBytes) {
	const prefix = `{"session":${JSON.stringify(session)},"entries":[`;
	let bytes = encoder.encode(prefix).length + 2;
	let count = 0;
	while (start + count < queue.length && count < 100) {
		const size = queue[start + count].bytes + (count ? 1 : 0);
		if (count && bytes + size > maxBytes) break;
		bytes += size;
		count++;
	}
	return {
		count,
		body: `${prefix}${queue.slice(start, start + count).map((row) => row.body).join(",")}]}`
	};
}
function post(body) {
	return fetch(url, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body,
		credentials: "same-origin",
		keepalive: encoder.encode(body).length < 6e4
	});
}
async function flush() {
	if (sending || !queue.length) return;
	sending = true;
	const { count, body } = batch(0, 1e5);
	inFlightCount = count;
	let delay = 250;
	try {
		const response = await post(body);
		if (response.status >= 400 && response.status < 500) {
			console.error(`Leaf interaction log rejected ${count} records: ${response.status}`);
			queue.splice(0, count);
			return;
		}
		if (!response.ok) throw new Error(`interaction log returned ${response.status}`);
		queue.splice(0, count);
	} catch {
		delay = 2e3;
	} finally {
		inFlightCount = 0;
		sending = false;
		schedule(delay);
	}
}
function recordInteraction(type, detail = {}) {
	enqueue({
		type,
		...detail
	});
}
if (enabled) {
	for (const type of [
		"pointerdown",
		"pointerup",
		"pointermove",
		"pointerover",
		"pointerout",
		"pointerenter",
		"pointerleave",
		"pointercancel",
		"click",
		"auxclick",
		"dblclick",
		"contextmenu",
		"wheel",
		"keydown",
		"keyup",
		"beforeinput",
		"input",
		"compositionstart",
		"compositionupdate",
		"compositionend",
		"change",
		"copy",
		"cut",
		"paste",
		"submit",
		"reset",
		"invalid",
		"focusin",
		"focusout",
		"scroll",
		"selectionchange",
		"visibilitychange",
		"dragstart",
		"drag",
		"dragend",
		"dragenter",
		"dragover",
		"dragleave",
		"drop",
		"touchstart",
		"touchmove",
		"touchend",
		"touchcancel",
		"beforetoggle",
		"toggle",
		"cancel",
		"close"
	]) document.addEventListener(type, (event) => enqueue(describe(event)), true);
	for (const type of [
		"pageshow",
		"pagehide",
		"hashchange",
		"popstate",
		"resize",
		"online",
		"offline",
		"fullscreenchange"
	]) window.addEventListener(type, (event) => enqueue(describe(event)), true);
	document.addEventListener("lf-command-invoked", (event) => {
		const active = focused();
		enqueue({
			type: "command",
			...event.detail,
			focus: active ? {
				target: locator(active),
				node: nodeIdentity(active)
			} : null,
			scroll: [window.scrollX, window.scrollY]
		});
	});
	new window.PerformanceObserver((list) => {
		for (const resource of list.getEntries()) {
			if (resource.name.startsWith(url)) continue;
			const resourceUrl = new URL(resource.name);
			if (pagePath(resourceUrl.pathname) === "/api/news") continue;
			enqueue({
				type: "resource",
				path: pagePath(resourceUrl.pathname),
				initiator: resource.initiatorType,
				durationMs: resource.duration,
				responseStatus: resource.responseStatus ?? null,
				transferSize: resource.transferSize
			});
		}
	}).observe({
		type: "resource",
		buffered: true
	});
	enqueue({
		type: "session_start",
		location: `${pagePath(location.pathname)}${location.hash}`,
		viewport: [window.innerWidth, window.innerHeight],
		userAgent: navigator.userAgent
	});
	window.addEventListener("pagehide", () => {
		for (let start = 0; start < queue.length;) {
			const { count, body } = batch(start, 48e3);
			start += count;
			post(body).catch(() => {});
		}
	}, true);
}

//#endregion
//#region runtime/native-selection.js
function pageRange(sel) {
	const plain = sel.getRangeAt(0);
	const shadowRoots = pageShadowRoots();
	if (!shadowRoots.length) return plain;
	const [composed] = sel.getComposedRanges({ shadowRoots });
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
	if (!writtenSelection) return false;
	if (selectionEnds(selection).every((end, i) => end === writtenSelection[i])) return true;
	writtenSelection = null;
	return false;
}
function selectionBackward(selection, range = pageRange(selection)) {
	if (selection.anchorNode.getRootNode() !== range.commonAncestorContainer.getRootNode()) return programmaticSelection(selection) ? writtenBackward : selection.direction === "backward";
	const probe = document.createRange();
	probe.setStart(selection.anchorNode, selection.anchorOffset);
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
	const mods = binding.split("+");
	return {
		key: mods.pop(),
		mods
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
const quickShortcuts = () => document.documentElement.lfKeyboard.quick;
const setQuickShortcuts = (on) => document.documentElement.lfKeyboard.setQuick(on);
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
	return routes.filter((route) => (includeUnavailable || commandAvailable(row, route)) && (active.includes(route.binding) || contextBindings(route).some((binding) => active.includes(binding)))).map((route) => ({
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
		if (parent.localName !== "fieldset" || !parent.disabled) continue;
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
		if (row.decision && row.control == null) throw new Error(`leaf: ${row.id} is a Decision command with no control`);
		if (row.lands !== void 0 && typeof row.lands !== "function") throw new TypeError(`leaf: ${row.id} lands must be a function`);
		if (row.native && !row.run) throw new Error(`leaf: row ${i} of ${where} leaves the native press to the platform but runs no result`);
		if (row.exit && (!row.run || row.touch || row.routes)) throw new Error(`leaf: ${row.id} is its stance's way out, which the panel's row offers in its own words, so it needs a run and no touch words or routes`);
		if (row.touch && (!row.run || row.routes)) throw new Error(`leaf: ${row.id} stands in for its keys under a finger, so it needs a run and makes one press, with no routes`);
		const routes = commandRoutes(row);
		if (routes.length && contextBindings(row).length) throw new Error(`leaf: ${row.id} owns distinct routes; declare contextKeys on each route`);
		const declared = declaredBindings(row);
		const routed = /* @__PURE__ */ new Map();
		const contextual = /* @__PURE__ */ new Map();
		for (const route of routes) {
			named(route);
			if (route.decision && route.control == null && row.control == null) throw new Error(`leaf: route ${route.id} of ${row.id} is a Decision command with no control`);
			if (!declared.includes(route.binding) && !contextBindings(route).length) throw new Error(`leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`);
			for (const [bindings, owners] of [[[route.binding].filter(Boolean), routed], [contextBindings(route), contextual]]) for (const binding of bindings) {
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
const PRESS = ["Enter", " "];
const rowArrows = (node) => node.matches(":dir(rtl)") ? ["ArrowRight", "ArrowLeft"] : ["ArrowLeft", "ArrowRight"];
const clampedRow = (rows, current, dir, entry = dir > 0 ? 0 : rows.length - 1) => {
	if (!rows.length) return void 0;
	const at = rows.indexOf(current);
	const next = at < 0 ? entry : at + dir;
	return rows[Math.max(0, Math.min(rows.length - 1, next))];
};
const cycledRow = (rows, current, dir) => {
	if (!rows.length) return void 0;
	const at = rows.indexOf(current);
	return rows[((at < 0 ? dir > 0 ? 0 : rows.length - 1 : at + dir) + rows.length) % rows.length];
};

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
	["button, details > summary, input:is([type=\"button\"], [type=\"submit\"], [type=\"reset\"], [type=\"image\"])", PRESS],
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
	if (!painters || frame) return;
	frame = nextRender(() => {
		frame = 0;
		const shiftPage = movePage;
		movePage = false;
		const p = painters;
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
const unpainted = /* @__PURE__ */ new Set();
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
			if (!row.run) continue;
			const routes = commandRoutes(row);
			for (const entry of routes.length ? routes : [row]) {
				const control = word(entry.control ?? row.control);
				if (!(control instanceof HTMLButtonElement) || !control.isConnected) continue;
				if (projectedOnto(control, scope)) continue;
				if (!declarations.has(control)) declarations.set(control, []);
				const candidates = declarations.get(control);
				if (!candidates.some((candidate) => candidate.row === row && candidate.entry.id === entry.id)) candidates.push({
					source,
					scope,
					row,
					entry
				});
			}
		}
	}
	return declarations;
}
function chosenCommand(candidates) {
	const available = candidates.filter(({ scope, row, entry }) => (!scope.when || scope.when()) && declaredCommandAvailable(row, entry === row ? null : entry));
	if (available.length > 1) throw new TypeError(`leaf: ${available[1].entry.id} shares a button with ${available[0].entry.id}`);
	return available[0] ?? candidates[0];
}
function buttonCommands() {
	return new Map([...buttonDeclarations()].map(([control, candidates]) => [control, chosenCommand(candidates)]));
}
function releaseButtons(declarations) {
	for (const ref of scopeRefs) {
		const control = ref.deref();
		if (!control || !buttonBaselines.has(control) || declarations.has(control)) continue;
		buttonReadings.delete(control);
		buttonAvailability.get(control)?.();
		buttonAvailability.delete(control);
		const { disabled, ariaDisabled } = buttonBaselines.get(control);
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
const sameCandidates = (left, right) => left?.length === right.length && right.every((candidate, index) => candidate.scope === left[index].scope && candidate.row === left[index].row && candidate.entry === left[index].entry);
function reflectButton(control, candidates) {
	buttonAvailability.get(control)?.();
	buttonCandidates.set(control, candidates);
	const ref = new WeakRef(control);
	let reading = candidates;
	let failure = null;
	const dispose = x(() => {
		if (reading) {
			const read = reading;
			reading = null;
			try {
				focusRevision();
				const command = chosenCommand(read);
				const { scope, row, entry } = command;
				const disabled = Boolean(scope.when && !scope.when() || !commandAvailable(row, entry === row ? null : entry));
				keeps(ref.deref(), "aria-disabled", disabled ? "true" : null);
				buttonReadings.set(ref.deref(), command);
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
		runLanding(command.row, () => command.row.run(commandBinding(command.row, command.entry === command.row ? null : command.entry)), control);
	});
}
function wireDeclaredButtons(scope) {
	if (scope.contextual || scope.sequence) return;
	for (const row of scope.rows) {
		if (!row.run || typeof row.routes === "function") continue;
		for (const entry of row.routes?.length ? row.routes : [row]) {
			const control = entry.control ?? row.control;
			if (control instanceof HTMLButtonElement && !projectedOnto(control, scope)) wireButton(control);
		}
	}
}
const either = (a, b) => a && b ? () => a() || b() : void 0;
const elementScopes = /* @__PURE__ */ new WeakMap();
const projectedScopes = /* @__PURE__ */ new WeakMap();
const commandScopeCapabilities = /* @__PURE__ */ new WeakSet();
const scopeIdentity = (scope) => scope.identity ?? scope;
const isCommandScope = (capability) => capability != null && commandScopeCapabilities.has(capability);
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
	return [elementScopes.get(element), ...projectedScopes.get(element)?.values() ?? []].filter(Boolean).flatMap((scope) => scope.contextual ? [scope] : [scope, localContext(element, scope)]);
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
						return this.routes.map(({ binding }) => binding);
					},
					get routes() {
						return contributions().flatMap((contribution) => {
							const aliases = contextBindings(contribution);
							const reference = Object.freeze({
								id: contribution.id,
								source,
								scope,
								row,
								binding: commandBinding(row, contribution === row ? null : contribution),
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
function merge(sections, { title, when, at, liveInCommandReference, rows }) {
	if (when && !when()) return;
	const seen = sections.get(title);
	if (!seen) {
		sections.set(title, {
			title,
			when,
			at,
			liveInCommandReference,
			rows: new Map(rows)
		});
		return;
	}
	for (const [key, row] of rows) seen.rows.set(key, row);
	seen.when = either(seen.when, when);
	seen.at = either(seen.at, at);
	seen.liveInCommandReference ||= liveInCommandReference;
}
function attachScope(where, declaration) {
	const scope = {
		...declaration,
		el: where,
		validated: false
	};
	unpainted.delete(elementScopes.get(where));
	elementScopes.set(where, scope);
	unpainted.add(scope);
	wireDeclaredButtons(scope);
	rememberScopedElement(where);
	buttonsDirty = true;
	repaint();
	return scope;
}
function detachScope(element, scope) {
	if (elementScopes.get(element) !== scope) return false;
	unpainted.delete(scope);
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
function keys(where, title, rows, options) {
	if (rows === void 0 && isCommandScope(title)) return attachScope(where, title.scope).rows;
	return attachScope(where, declaredScope(title, rows, options)).rows;
}
const commandsOn = directive(class extends AsyncDirective {
	#element;
	#declaration;
	#scope = null;
	constructor(part) {
		super(part);
		if (part.type !== PartType.ELEMENT) throw new TypeError("commandsOn belongs in a template's element part");
	}
	render(title, rows, options) {
		return nothing;
	}
	update(part, [title, rows, options]) {
		this.#element = part.element;
		this.#declaration = rows === void 0 && isCommandScope(title) ? title.scope : declaredScope(title, typeof rows === "function" ? rows(part.element) : rows, options);
		if (this.isConnected) this.reconnected();
		return nothing;
	}
	reconnected() {
		this.#scope = attachScope(this.#element, this.#declaration);
	}
	disconnected() {
		if (detachScope(this.#element, this.#scope)) repaint();
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
		for (let node = scoped; node; node = renderedParent(node)) if (node === root) {
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
	for (const scope of [...unpainted]) {
		unpainted.delete(scope);
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
	let first = true;
	let failure = null;
	const dispose = x(() => {
		if (first) {
			first = false;
			try {
				focusRevision();
				reflectElementShortcuts(ref.deref());
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
	const contexts = [...contextScopeReaders].map((read) => read(node)).filter(Boolean);
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
		if (a.tagName === "DETAILS" && !a.open) a.open = true;
		if (a.hasAttribute?.("popover") && !isNativeLayer(a)) showNativeLayer(a, { modal: false });
		if (a.getAttribute?.("hidden") !== "until-found") continue;
		const shown = [...a.parentNode?.children ?? []].filter((s) => !s.hidden);
		a.dispatchEvent(new Event("beforematch", { bubbles: true }));
		a.removeAttribute("hidden");
		if (shown.some((sibling) => sibling.hidden)) replacedView = true;
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
function searchField(cls, { name, label, placeholder = label }) {
	const field = offer("wa-input", `lf-search-field lf-label-hidden ${cls}`);
	field.type = "search";
	field.value = "";
	field.size = "s";
	field.withClear = true;
	field.tabIndex = 0;
	field.name = name;
	field.label = label;
	field.placeholder = placeholder;
	field.autocomplete = "off";
	field.spellcheck = false;
	return field;
}
function nameAction(control, action, { label, title, className } = {}) {
	const name = label ?? actionName(action);
	keeps(control, "aria-label", name);
	keeps(control, "title", title ?? name);
	showAction(control, action, className);
}
const namedAction = elementDirective("namedAction", nameAction);
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
function relabel(node, label, { says } = {}) {
	generatedElement(node, { says });
	keepsText(node, label);
}
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
	render(html`${action ? actionTemplate(action) : html`<span class="lf-response-action-glyph" aria-hidden="true"
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
const noticeText = (message) => typeof message === "string" ? message : message.map((part) => part.text).join("");
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
		liveEl.append(noticeText(msg));
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
		const message = entry.format(entry.value);
		if (noticeText(message)) {
			showNotice(message, entry);
			return true;
		}
		entry = waitingBackground.shift();
	}
	return false;
}
const textBackground = (message) => ({
	key: "text",
	value: message,
	combine: (_older, newer) => newer,
	format: (value) => value
});
function queueBackground(entry, front = false) {
	const index = waitingBackground.findIndex((waiting) => waiting.key === entry.key);
	if (index >= 0) {
		const [waiting] = waitingBackground.splice(index, 1);
		entry = {
			...entry,
			value: front ? entry.combine(entry.value, waiting.value) : entry.combine(waiting.value, entry.value)
		};
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
//#region runtime/layer-client.js
const { layer: layerGeneration, release, probe, runtime: runtimeIdentity } = DELIVERY;
async function sourceMovedOn() {
	if (!probe) return true;
	let response;
	try {
		response = await fetch(probe, { cache: "no-store" });
	} catch {
		return;
	}
	if (response.status === 404) return Boolean(release);
	if (!response.ok) return void 0;
	const servedRelease = response.headers.get("Leaf-Release");
	if (release && servedRelease) return servedRelease !== release;
	if (!sameRuntime(response)) return true;
	const generation = response.headers.get("Leaf-Layer");
	return generation ? generation !== layerGeneration : void 0;
}
let layerReloading = false;
function reloadNow(message) {
	if (layerReloading) return;
	layerReloading = true;
	notice(message);
	location.reload();
}
let asking = false;
const holdWaiting = holdingError();
function reloadDelivery(message) {
	if (layerReloading || asking) return;
	asking = true;
	(async () => {
		try {
			const moved = await sourceMovedOn();
			if (moved === void 0) return;
			if (!moved) {
				holdWaiting("Waiting for Leaf to finish updating.");
				return;
			}
			reloadNow(message);
		} finally {
			asking = false;
		}
	})();
}
const sameRuntime = (response) => {
	const served = response.headers.get("Leaf-Runtime");
	return !runtimeIdentity || !served || served === runtimeIdentity;
};
function layerHeaders(headers = {}) {
	return {
		"Leaf-Layer": layerGeneration,
		...runtimeIdentity && { "Leaf-Runtime": runtimeIdentity },
		...runtime.currentRevision && { "Leaf-View-Revision": String(runtime.currentRevision) },
		...release && { "Leaf-Release": release },
		...headers
	};
}
const dataHeaders = (held) => held.version === null ? {} : { "Leaf-Data-Version": held.version };
const completeData = (state, held) => state && !state.data.sources ? {
	...state,
	data: held
} : state;
var LayerRefused = class extends Error {};
var RequestError = class extends Error {
	constructor(message, { status, body, cause, current, said }) {
		super(message, { cause });
		this.status = status;
		this.body = body;
		this.current = current;
		this.said = said;
	}
};
async function requestJson(url, init, what) {
	const response = await fetch(url, {
		...init,
		headers: layerHeaders(init.headers)
	});
	if (!admitResponse(response)) throw new LayerRefused(`Leaf's layer changed while requesting ${what}`);
	const text = await response.text();
	const failed = (message, cause, details = {}) => new RequestError(message, {
		status: response.status,
		body: text,
		cause,
		...details
	});
	let answer = null;
	if (response.ok || response.headers.get("Content-Type")?.split(";")[0].trim() === "application/json") try {
		answer = JSON.parse(text);
	} catch (error) {
		throw failed(`${what}: HTTP ${response.status}`, error);
	}
	if (!response.ok) {
		const refusal = answer;
		throw failed(refusal?.error ?? `${what}: HTTP ${response.status}`, void 0, {
			current: refusal && "current" in refusal ? refusal.current : void 0,
			said: refusal?.error
		});
	}
	return answer;
}
function sameLayer(generation) {
	if (generation === layerGeneration) return true;
	reloadDelivery("Leaf has been updated — reloading this page.");
	return false;
}
const admitResponse = (response) => admitted(response, true);
const admitReading = (response) => admitted(response, false);
function admitted(response, ofThisLayer) {
	observeSession(response);
	observeKey(response);
	if (!response.ok) return true;
	if (layerReloading) return false;
	const generation = response.headers.get("Leaf-Layer");
	const responseRelease = response.headers.get("Leaf-Release");
	if (ofThisLayer && generation && !sameLayer(generation)) return false;
	if (!sameRuntime(response)) {
		reloadDelivery("Leaf has been updated — reloading this page.");
		return false;
	}
	if (release && responseRelease && responseRelease !== release) {
		reloadDelivery("Leaf has been updated — reloading this page.");
		return false;
	}
	holdWaiting(null);
	return true;
}
let sessionMode = release ? "unknown" : "active";
const sessionChannel = release && !document.documentElement.lfSample ? new window.BroadcastChannel(`leaf-session:${release}:${pageUrl("")}`) : null;
function activateSession(broadcast) {
	const activated = sessionMode !== "active";
	sessionMode = "active";
	if (activated) document.dispatchEvent(new Event("lf-session-active"));
	if (broadcast && activated) sessionChannel?.postMessage({ active: true });
}
sessionChannel?.addEventListener("message", (event) => {
	if (event.data?.active === true) activateSession(false);
});
function observeSession(response) {
	const reference = response.headers.get("Leaf-Session-Reference");
	if (/^\d{12}$/.test(reference)) runtime.sessionReference = reference;
	const mode = response.headers.get("Leaf-Session");
	if (mode === "active") activateSession(true);
	else if (mode === "passive" && sessionMode !== "active") sessionMode = "passive";
}
const sessionIsActive = () => sessionMode === "active";
const KEY_REFUSED = 401;
function observeKey(response) {
	runtime.keyRefused = response.status === KEY_REFUSED;
}
const { promise: layerReady, resolve: layerRevealed } = Promise.withResolvers();
let layerKnown = false;
const revealLayer = () => {
	layerKnown = true;
	layerRevealed();
};
const postEvent = async (event, held = runtime.data) => {
	if (offlineInteractive) throw new Error("no agent or server is available in an interactive export");
	if (!layerKnown) await layerReady;
	countTraffic("sends");
	recordInteraction("event_post", {
		kind: event.kind,
		attempt: event.attempt ?? null
	});
	let response;
	try {
		response = await fetch(pageUrl("api/event"), {
			method: "POST",
			headers: layerHeaders({
				"Content-Type": "application/json",
				...dataHeaders(held)
			}),
			body: JSON.stringify(event)
		});
		recordInteraction("event_response", {
			kind: event.kind,
			attempt: event.attempt ?? null,
			status: response.status
		});
	} catch (error) {
		recordInteraction("event_response", {
			kind: event.kind,
			attempt: event.attempt ?? null,
			error: String(error)
		});
		throw error;
	} finally {
		countTraffic("acked");
	}
	if (!admitResponse(response)) return null;
	if (response.status === KEY_REFUSED) throw new Error("the server refused this page's key");
	return response;
};
const uploadMedia = async (file) => {
	if (offlineInteractive) throw new Error("no agent or server is available in an interactive export");
	await layerReady;
	countTraffic("sends");
	let answer;
	try {
		answer = await requestJson(pageUrl("api/media"), {
			method: "POST",
			headers: { "Content-Type": file.type },
			body: file
		}, "image upload");
	} catch (error) {
		if (error instanceof LayerRefused) return null;
		throw error;
	} finally {
		countTraffic("acked");
	}
	return answer.path;
};
const reportedReasons = /* @__PURE__ */ new WeakSet();
const reportedPrimitives = /* @__PURE__ */ new Set();
const reportedErrors = /* @__PURE__ */ new Set();
function reportPageError(reason, context = "") {
	if (typeof reason === "object" && reason !== null) reportedReasons.add(reason);
	else reportedPrimitives.add(String(reason));
	const text = exceptionText(reason, context);
	document.documentElement.lfDocumentLifetime.whenActive(`report ${text}`, () => {
		console.error(`leaf: ${text}`);
		if (offlineInteractive) return;
		if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
		reportedErrors.add(text);
		postEvent({
			kind: "error",
			text,
			...runtime.currentRevision != null && { revision: runtime.currentRevision }
		}).catch(() => {});
	});
}
function reportCarried(reason, context = "") {
	if (!(typeof reason === "object" && reason !== null ? reportedReasons.has(reason) : reportedPrimitives.has(String(reason)))) reportPageError(reason, context);
}
window.addEventListener("error", (e) => {
	const failure = failureOf(e);
	if (failure) {
		reportPageError(failure.reason, failureContext(failure.element));
		return;
	}
	if (e.message?.startsWith("ResizeObserver loop")) return;
	reportPageError(e.error ?? e.message, e.filename ? `${e.filename}:${e.lineno}:${e.colno}` : "");
});
window.addEventListener("unhandledrejection", (e) => {
	reportPageError(e.reason);
});

//#endregion
export { EVERYTHING, LINK, LayerRefused, PRESS, PRESSABLE, RequestError, TEXT_ENTRY, admitReading, admitResponse, advertisesKeys, allBindings, announce, answers, ariaShortcuts, authoredBody, bindingEnabled, bindingEnabledFor, bindings, buttonCommand, checked, claimsEsc, clampedRow, closeControl, commandAvailable, commandBinding, commandDeclarationsWithin, commandEntries, commandPresentations, commandReady, commandRoutes, commandScope, commandsOn, commandsWithin, completeData, contextBindings, contextScopes, controlAvailabilityOutput, countTraffic, cycledRow, dataHeaders, decisionControls, declareCommandReadiness, declaredBindings, descriptionOf, dismissError, dismissErrors, dragHeld, dragging, el, errorsReading, holdAuthoredBody, holdStatus, holdingError, isCommandScope, keys, labelOf, layerHeaders, live, liveEl, merge, motionPreview, mountRepaint, nameAction, namedAction, nativeActivationAt, nativeClaimAt, notice, noticeReading, noticeText, pageRange, paintKeys, paintKeysWithin, parsed, passErrors, passErrorsAt, postEvent, programmaticSelection, projectCommandScope, pruneScopedElements, quickShortcuts, raiseError, randomId, reachedForWords, recordInteraction, referencedCommandEntry, reflectFirstScopes, reflectKeys, relabel, removeRuntimeRootStyle, repaint, repaintPage, reportCarried, reportPageError, requestJson, responseAction, reveal, revealLayer, routedCommand, rowArrows, runLanding, runtimeRootState, sameLayer, savedReadingSettled, saying, scopeAvailable, scopeIdentity, scopeRefs, scopesAt, scopesFor, searchField, seeErrors, selectEnds, selectionBackward, sessionIsActive, setNoticeContext, setQuickShortcuts, setRuntimeRootAttribute, setRuntimeRootStyle, spell, spokenBinding, submitBindings, titleOf, touchPresses, uploadMedia, watchCommandAvailability, watchCommandScopes, watchPendingTraffic, word, worksInside };