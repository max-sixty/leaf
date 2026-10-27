import { Z, x as x$1 } from "./bundle-signals-core.js";
import { CARET_KEYS, PRESSES, WORKS, controlNavigationKeys, focusRevision, keeps, keepsText, nextRender, onCurrentLocation, onFocusVisibility, renderedParent, sizeObserver, takesLetters, under } from "./bundle-dom-move.js";
import { shownBox, tagsDeclaring } from "./bundle-geometry.js";
import { AsyncDirective, Directive, PartType, directive, html, nothing, render, runtime } from "./bundle-context.js";

//#region runtime/pointer.js
let x = -1;
let y = -1;
const remember = (ev) => {
	x = ev.clientX;
	y = ev.clientY;
};
document.addEventListener("pointermove", remember, { capture: true });
document.addEventListener("pointerdown", remember, { capture: true });
const pointerAt = () => ({
	x,
	y
});
const coarsePointer = matchMedia("(pointer: coarse)");
const hoveringPointer = matchMedia("(hover: hover)");
const pressIsKeyboardActivation = (event) => event.type === "click" && !event.detail;
const plainPress = (event) => event.button === 0 && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
let releaseClaimed = false;
const claimReleaseClick = () => {
	releaseClaimed = true;
};
document.addEventListener("pointerdown", () => {
	releaseClaimed = false;
}, { capture: true });
document.addEventListener("click", (event) => {
	if (!releaseClaimed || !event.isTrusted || pressIsKeyboardActivation(event)) return;
	releaseClaimed = false;
	event.preventDefault();
	event.stopImmediatePropagation();
}, { capture: true });
function restorePointer(point) {
	if (x !== -1 || y !== -1 || !Number.isFinite(point?.x) || !Number.isFinite(point?.y)) return;
	x = point.x;
	y = point.y;
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
	const dispose = x$1(() => {
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
		command.row.run(commandBinding(command.row, command.entry === command.row ? null : command.entry));
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
	if (escape !== void 0 && escape !== "inner") throw new TypeError(`A command scope's Escape ownership must be \"inner\", got ${String(escape)}`);
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
	availabilityTracking = x$1(() => {
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
	const dispose = x$1(() => {
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
//#region runtime/icon-paths.js
const SEND = "<path d=\"M8 13V3M4 7l4-4 4 4\"/>";
const ICONS = {
	activity: "<circle cx=\"8\" cy=\"8\" r=\"3\" fill=\"currentColor\" stroke=\"none\"/>",
	add: "<path d=\"M8 3v10M3 8h10\"/>",
	change: "<path d=\"M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13\"/>",
	check: "<path d=\"m3 8.25 3.15 3.15L13 4.75\"/>",
	comment: "<path d=\"M3 3.25h10v7H7.25L4 12.75v-2H3z\"/>",
	copy: "<rect x=\"6\" y=\"6\" width=\"7\" height=\"7\" rx=\"1.25\"/><path d=\"M10 6V4.25C10 3.56 9.44 3 8.75 3h-4.5C3.56 3 3 3.56 3 4.25v4.5C3 9.44 3.56 10 4.25 10H6\"/>",
	cross: "<path d=\"m4 4 8 8M12 4l-8 8\"/>",
	dot: "<circle cx=\"8\" cy=\"8\" r=\"1.5\" fill=\"currentColor\" stroke=\"none\"/>",
	down: "<path d=\"m4 6.25 4 4 4-4\"/>",
	edit: "<path d=\"m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2\"/>",
	expand: "<path d=\"M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75\"/>",
	collapse: "<path d=\"M13 3 9.25 6.75M9.25 3.25v3.5h3.5M3 13l3.75-3.75M3.25 9.25h3.5v3.5\"/>",
	fit: "<path d=\"M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3\"/>",
	fold: "<path d=\"M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5\"/>",
	more: "<circle cx=\"3.5\" cy=\"8\" r=\"1\" fill=\"currentColor\" stroke=\"none\"/><circle cx=\"8\" cy=\"8\" r=\"1\" fill=\"currentColor\" stroke=\"none\"/><circle cx=\"12.5\" cy=\"8\" r=\"1\" fill=\"currentColor\" stroke=\"none\"/>",
	inbox: "<path d=\"M2.75 9.25h2.9l1 1.6h2.7l1-1.6h2.9M2.75 9.25 4.4 4h7.2l1.65 5.25v2.75H2.75z\"/>",
	link: "<path d=\"M6.67 8.67a3.33 3.33 0 0 0 5.03.36l2-2a3.33 3.33 0 0 0-4.71-4.71l-1.15 1.14M9.33 7.33a3.33 3.33 0 0 0-5.03-.36l-2 2a3.33 3.33 0 0 0 4.71 4.71l1.14-1.14\"/>",
	microphone: "<rect x=\"6\" y=\"2\" width=\"4\" height=\"7\" rx=\"2\"/><path d=\"M4 7.5v.75a4 4 0 0 0 8 0V7.5M8 12.25V14M6 14h4\"/><path class=\"lf-mic-slash\" d=\"M2.5 2.5l11 11\"/>",
	next: "<path d=\"m6 3.5 4.5 4.5L6 12.5\"/>",
	pause: "<path d=\"M5 3v10M11 3v10\"/>",
	play: "<path d=\"m5 3 7 5-7 5z\"/>",
	previous: "<path d=\"m10 3.5-4.5 4.5 4.5 4.5\"/>",
	arrange: "<path d=\"M3 4.5h10M3 8h7M3 11.5h4\"/>",
	all: "<path d=\"M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4\"/>",
	pickup: "<path d=\"M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2\"/>",
	question: "<path d=\"M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2\"/><circle cx=\"8\" cy=\"12.35\" r=\".7\" fill=\"currentColor\" stroke=\"none\"/>",
	reaction: "<circle cx=\"6.5\" cy=\"8.25\" r=\"4.25\"/><circle cx=\"5\" cy=\"7.25\" r=\".55\" fill=\"currentColor\" stroke=\"none\"/><circle cx=\"8\" cy=\"7.25\" r=\".55\" fill=\"currentColor\" stroke=\"none\"/><path d=\"M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4\"/>",
	retry: "<path d=\"M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9\"/>",
	save: "<path d=\"M3 4.25A1.25 1.25 0 0 1 4.25 3h6.5L13 5.25v6.5A1.25 1.25 0 0 1 11.75 13h-7.5A1.25 1.25 0 0 1 3 11.75zM5.5 3v2.5h4V3\"/>",
	search: "<circle cx=\"7\" cy=\"7\" r=\"3.75\"/><path d=\"m10 10 3 3\"/>",
	send: SEND,
	sent: SEND,
	start: "<path d=\"M3.5 3v10M12.5 3.5 6 8l6.5 4.5z\"/>",
	subtract: "<path d=\"M3 8h10\"/>",
	unfold: "<path d=\"M3 8h10M5.5 5.25 8 2.75l2.5 2.5M5.5 10.75 8 13.25l2.5-2.5\"/>",
	undo: "<path d=\"M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1\"/>",
	up: "<path d=\"m4 9.75 4-4 4 4\"/>",
	waiting: "<circle cx=\"8\" cy=\"8\" r=\"5\"/><path d=\"M8 5v3.25l2 1.25\"/>"
};
const SVG = "http://www.w3.org/2000/svg";
const iconMarkup = (icon) => {
	const markup = ICONS[icon];
	if (!markup) throw new TypeError(`Unknown Leaf icon: ${icon}`);
	return markup;
};
function iconElement(icon, className = "lf-margin-entry-icon") {
	const svg = document.createElementNS(SVG, "svg");
	svg.setAttribute("viewBox", "0 0 16 16");
	svg.setAttribute("focusable", "false");
	svg.setAttribute("aria-hidden", "true");
	svg.setAttribute("class", className);
	svg.dataset.lfIcon = icon;
	svg.innerHTML = iconMarkup(icon);
	return svg;
}

//#endregion
//#region runtime/icons.js
function iconTemplate(icon, className = "lf-margin-entry-icon") {
	return html`<svg
    viewBox="0 0 16 16"
    focusable="false"
    aria-hidden="true"
    class=${className}
    data-lf-icon=${icon}
    .innerHTML=${iconMarkup(icon)}
  ></svg>`;
}

//#endregion
//#region runtime/widget-elements.js
function reveal(el, mayReveal) {
	const chain = [];
	const pending = [];
	let replacedView = false;
	for (let a = el; a; a = renderedParent(a)) chain.push(a);
	for (const a of chain.reverse()) {
		if (!mayReveal()) break;
		if (a.tagName === "DETAILS" && !a.open) a.open = true;
		a.dispatchEvent(new CustomEvent("lf-reveal", { detail: {
			target: el,
			mayReveal,
			replacedView: () => {
				replacedView = true;
			},
			present: (ready) => ready?.then && pending.push(ready)
		} }));
	}
	const ready = Promise.all(pending);
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
const LAYOUT = "lf-layout";
const layoutChanged = (el) => {
	const pending = [];
	el.dispatchEvent(new CustomEvent(LAYOUT, {
		bubbles: true,
		composed: true,
		detail: { present: (ready) => ready?.then && pending.push(ready) }
	}));
	const ready = Promise.all(pending);
	ready.catch(() => {});
	return ready;
};
const measurements = /* @__PURE__ */ new WeakMap();
const drawn = (el) => {
	const box = shownBox(el);
	return Boolean(box.width || box.height);
};
const unmeasured = sizeObserver((entries) => {
	const taking = [];
	for (const { target } of entries) {
		if (!drawn(target)) continue;
		unmeasured.unobserve(target);
		taking.push(measurements.get(target));
		measurements.delete(target);
	}
	for (const take of taking) take();
});
function measure(el, take) {
	if (drawn(el)) {
		if (measurements.delete(el)) unmeasured.unobserve(el);
		return take();
	}
	measurements.set(el, take);
	unmeasured.observe(el);
}
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
const offer = (...args) => document.documentElement.lfInitial.offer(...args);
const offerElement = (...args) => document.documentElement.lfInitial.offerElement(...args);
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
function elementDirective(name, write) {
	return directive(class extends Directive {
		constructor(part) {
			super(part);
			if (part.type !== PartType.ELEMENT) throw new TypeError(`${name} belongs in a template's element part`);
		}
		render(...args) {
			return nothing;
		}
		update(part, args) {
			write(part.element, ...args);
			return nothing;
		}
	});
}
const offered = elementDirective("offered", offerElement);
const offerActionElement = (...args) => document.documentElement.lfInitial.offerActionElement(...args);
function offerAction(role, className, label, { title, icon } = {}) {
	const control = document.documentElement.lfInitial.offerAction(role, className, label, title === void 0 ? void 0 : { title });
	if (icon) control.append(iconElement(icon, role === "mark" ? "lf-mark-icon" : "lf-action-icon"));
	return control;
}
const offeredAction = elementDirective("offeredAction", offerActionElement);
const selectableOfferElement = (node, role, cls) => document.documentElement.lfInitial.selectableOfferElement(node, role, cls);
const selectableOffer = (role, cls, label) => document.documentElement.lfInitial.selectableOffer(role, cls, label);
const selectableOffered = elementDirective("selectableOffered", selectableOfferElement);
const PRESSABLE = "[data-lf-offer]:not([data-lf-offer=\"\"])";
function reachedForWords(el) {
	const sel = getSelection();
	return !!sel && !sel.isCollapsed && el.contains(sel.focusNode);
}
document.addEventListener("click", (ev) => {
	if (pressIsKeyboardActivation(ev)) return;
	const control = ev.target.closest?.(`${PRESSES},[data-lf-offer]`);
	if (control && reachedForWords(control)) {
		ev.stopPropagation();
		ev.preventDefault();
	}
}, true);
const generatedElement = (...args) => document.documentElement.lfInitial.generatedElement(...args);
const generated = elementDirective("generated", generatedElement);
function relabel(node, label, { says } = {}) {
	generatedElement(node, { says });
	keepsText(node, label);
}
const closeControl = ({ name, title = name, className = "" }) => offerAction("symbol", className, name, {
	title,
	icon: "cross"
});
function responseAction(control, { glyph = null, icon = null, label, behavior = "action", collapse = false }) {
	if (Boolean(String(glyph ?? "").trim()) === Boolean(icon)) throw new TypeError("A response action needs exactly one glyph or icon");
	control.classList.toggle("lf-response-control", true);
	control.classList.toggle("lf-response-action", true);
	keeps(control, "data-lf-behavior", behavior);
	control.toggleAttribute("data-lf-collapse", collapse);
	if (behavior !== "action" && !control.hasAttribute("aria-expanded")) control.setAttribute("aria-expanded", "false");
	if (behavior === "action") control.removeAttribute("aria-expanded");
	if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
	render(html`${icon ? iconTemplate(icon) : html`<span class="lf-response-action-glyph" aria-hidden="true"
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
		liveEl.append(msg);
	}, 30);
}
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
		if (message) {
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
export { EVERYTHING, LAYOUT, LINK, PRESS, PRESSABLE, TEXT_ENTRY, advertisesKeys, allBindings, announce, answers, ariaShortcuts, bindingEnabled, bindingEnabledFor, bindings, buttonCommand, checked, claimReleaseClick, claimsEsc, clampedRow, closeControl, coarsePointer, commandAvailable, commandBinding, commandDeclarationsWithin, commandEntries, commandPresentations, commandReady, commandRoutes, commandScope, commandsOn, commandsWithin, contextBindings, contextScopes, controlAvailabilityOutput, cycledRow, decisionControls, declareCommandReadiness, declaredBindings, descriptionOf, dismissError, dismissErrors, dragHeld, dragging, el, elementDirective, errorsReading, generated, generatedElement, holdStatus, holdingError, hoveringPointer, iconElement, iconTemplate, isCommandScope, keys, labelOf, layoutChanged, live, liveEl, measure, merge, motionPreview, mountRepaint, nativeActivationAt, nativeClaimAt, notice, noticeReading, offer, offerAction, offerActionElement, offered, offeredAction, paintKeys, paintKeysWithin, parsed, passErrors, passErrorsAt, plainPress, pointerAt, pressIsKeyboardActivation, projectCommandScope, pruneScopedElements, quickShortcuts, raiseError, reachedForWords, referencedCommandEntry, reflectFirstScopes, reflectKeys, relabel, repaint, repaintPage, responseAction, restorePointer, reveal, routedCommand, rowArrows, savedReadingSettled, saying, scopeAvailable, scopeIdentity, scopeRefs, scopesAt, scopesFor, searchField, seeErrors, selectableOffer, selectableOffered, setNoticeContext, setQuickShortcuts, spell, spokenBinding, submitBindings, titleOf, touchPresses, watchCommandAvailability, watchCommandScopes, word, worksInside };