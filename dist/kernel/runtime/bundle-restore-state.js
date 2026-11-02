import { canPlaceFocus, composedParentNode, exceptionRecord, excludedByInert, focusDestination, focused, nativeLayers, onCurrentLocation, onUserInput, pagePresented, pageUpgraded, recoveredLabelFocus, renderedUnder, sizeObserver, tabStore, takesLetters } from "./bundle-portable.js";
import { EVERYTHING, allBindings, answers, bindingEnabledFor, bindings, commandEntries, commandReady, commandRoutes, commandRun, declaredBindings, descriptionOf, live, nativeActivationAt, nativeClaimAt, quickShortcuts, referencedCommandEntry, routedCommand, runLanding, scopeAvailable, scopeIdentity, scopesAt, scopesFor, spell, titleOf, word } from "./bundle-errors.js";
import { whenArrived } from "./bundle-content-layout.js";
import { DESIGN_MODE_KEY, ELEMENTS, pageScopes, stances, textEntryScopes, universalCommandReference } from "./bundle-data.js";

//#region runtime/sample-child.js
const child = document.documentElement.lfSample;
const commands = {};
const observers = /* @__PURE__ */ new Set();
function onSampleNotice(_type, callback) {
	observers.add(callback);
	return () => observers.delete(callback);
}
function registerSampleCommand(name, callback) {
	commands[name] = callback;
	return () => {
		delete commands[name];
	};
}
function sampleNotice(notice) {
	child?.send(notice);
}
async function execute({ method, detail }) {
	const command = commands[method];
	if (!command) throw new Error(`Unknown sample command: ${method}`);
	return await command(detail);
}
if (child) child.receive(async (message) => {
	if (message.type) {
		if (message.type === "cancel-view") for (const callback of observers) callback();
		return;
	}
	try {
		const result = await execute(message);
		child.send({
			id: message.id,
			result
		});
	} catch (error) {
		child.send({
			id: message.id,
			error: exceptionRecord(error)
		});
	}
});
if (child) {
	let upgraded = false;
	let arriving = false;
	let currentLocation = null;
	onCurrentLocation((node) => {
		if (node && node !== document.body) currentLocation = node;
		sampleNotice({
			type: "current-location",
			detail: { focused: Boolean(node && node !== document.body) }
		});
	});
	const input = (event) => {
		if (!event.isTrusted || event.type === "blur") return;
		sampleNotice({
			type: "input",
			detail: { type: event.type }
		});
	};
	onUserInput(input);
	window.addEventListener("click", input, {
		capture: true,
		passive: true
	});
	registerSampleCommand("restore-current-location", () => {
		if (!currentLocation?.isConnected || !canPlaceFocus()) return false;
		focusDestination(currentLocation, "return");
		return document.hasFocus();
	});
	registerSampleCommand("image", async ({ x, y, width, height }) => {
		const { pageImage } = await import("./bundle-page-image.js").then((n) => n.page_image_exports);
		return pageImage({
			x: scrollX + x,
			y: scrollY + y,
			width,
			height
		});
	});
	const inspect = () => {
		const error = document.documentElement.dataset.lfStartupError;
		if (error) sampleNotice({
			type: "error",
			detail: document.documentElement.lfStartupException ?? { message: error }
		});
		if (upgraded && !arriving && pagePresented()) {
			arriving = true;
			whenArrived().then(() => sampleNotice({ type: "arrived" }));
		}
		if (upgraded || !(document.body && pageUpgraded())) return;
		upgraded = true;
		child.present();
		let height = Math.ceil(document.body.getBoundingClientRect().height);
		sampleNotice({
			type: "height",
			detail: { height }
		});
		const measure = () => {
			if (!document.body) return;
			const next = Math.ceil(document.body.getBoundingClientRect().height);
			if (next !== height) {
				height = next;
				sampleNotice({
					type: "height",
					detail: { height }
				});
			}
		};
		registerSampleCommand("window", ({ window: asWindow }) => {
			child.settings.window = asWindow;
			window.lfRootState.setRuntimeRootAttribute(document.documentElement, "data-lf-sample-block", asWindow ? null : "");
			measure();
			return { height };
		});
		sizeObserver(measure, { counted: false }).observe(document.body);
		sampleNotice({
			type: "ready",
			detail: {
				height,
				block: document.documentElement.hasAttribute("data-lf-sample-block")
			}
		});
		inspect();
	};
	new MutationObserver(inspect).observe(document, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: [
			"data-lf-upgraded",
			"data-lf-presented",
			"data-lf-startup-error"
		]
	});
	inspect();
}

//#endregion
//#region runtime/stylesheets.js
const delivery = document.querySelector("script[type=\"application/json\"][data-lf-runtime][data-lf-sheets]");
if (!delivery) throw new Error("The document has no runtime stylesheets");
const sheets = JSON.parse(delivery.textContent);
function constructSheet(text) {
	const sheet = new CSSStyleSheet();
	sheet.replaceSync(text);
	return sheet;
}
const chromeSheet = constructSheet(sheets.chrome);
const chromeSharedClasses = Object.freeze([
	"lf-aiming",
	"lf-over-item",
	"lf-react-mark",
	"lf-mark-note",
	"lf-ui",
	"lf-version-inline-deletion",
	"lf-visual-action"
]);
const marksSheet = constructSheet(sheets.marks);
const annotationMarkSheets = sheets.annotations ? [constructSheet(sheets.annotations.marks)] : [];
const annotationSheets = sheets.annotations ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets] : [];

//#endregion
//#region runtime/keyboard/dispatch.js
const pageHas = scopeAvailable;
const userIn = (scope) => {
	if (excludedByInert(scopeRoot(scope))) return false;
	return !scope.at || scope.at();
};
const currentLocation = (scope) => userIn(scope) && pageHas(scope);
const innermostStance = () => stances().find(({ scope }) => currentLocation(scope)) ?? null;
const nativeBoundary = (claims) => ({
	get rows() {
		const reference = universalCommandReference();
		return reference ? [reference] : [];
	},
	claims,
	escapeBoundary: true
});
const MODAL_BOUNDARY = nativeBoundary(EVERYTHING);
const POPOVER_BOUNDARY = nativeBoundary((binding) => binding === "Escape");
const scopeRoot = (scope) => {
	const declared = scope.root ?? scope.el ?? document;
	return typeof declared === "function" ? declared() : declared;
};
const innerEscape = (scope, active) => scope.escape === "inner" || scope.el === active;
const above = (node, active) => {
	let depth = 0;
	let up = active;
	for (; up; up = composedParentNode(up)) {
		if (up === node) return depth;
		depth += 1;
	}
	return -1;
};
const escapeOrder = (scopes, active) => {
	const boundaryAt = scopes.findIndex((scope) => scope.escapeBoundary);
	const end = boundaryAt < 0 ? scopes.length : boundaryAt;
	const layer = scopes.slice(0, end);
	const inner = layer.filter((scope) => innerEscape(scope, active));
	const outer = layer.filter((scope) => !inner.includes(scope)).map((scope) => {
		const root = scopeRoot(scope);
		return {
			scope,
			root,
			depth: above(root, active)
		};
	});
	let surface = null;
	for (const { root, depth } of outer) {
		if (depth < 1 || root === document) continue;
		if (!surface || renderedUnder(root, surface)) surface = root;
	}
	const within = surface ? outer.filter(({ root }) => renderedUnder(root, surface)) : [];
	within.sort((a, b) => a.depth - b.depth);
	const rest = outer.filter((scope) => !within.includes(scope));
	return [
		...inner,
		...within.map(({ scope }) => scope),
		...rest.map(({ scope }) => scope),
		...scopes.slice(end)
	];
};
function stack(binding = null) {
	const active = focused();
	const elementStack = scopesFor(active);
	const typing = takesLetters(active);
	const TYPING = textEntryScopes();
	const nativeClaims = nativeClaimAt(active);
	const activation = nativeActivationAt(active);
	const controlScope = (nativeClaims || activation) && !typing ? {
		root: active,
		rows: [],
		claims: nativeClaims,
		activation
	} : null;
	const expanded = pageScopes().flatMap((scope) => {
		if (scope === ELEMENTS) {
			if (!typing && !controlScope) return elementStack;
			const own = elementStack.filter(({ el, contextual }) => el === active && !contextual);
			const ancestors = elementStack.filter(({ el, contextual }) => el !== active || contextual);
			return [
				...own,
				...typing ? TYPING : controlScope ? [controlScope] : [],
				...ancestors
			];
		}
		if (typing && TYPING.includes(scope)) return [];
		return scope;
	});
	const ordered = (scopes) => {
		const activeScopes = scopes.filter(currentLocation);
		return binding === "Escape" ? escapeOrder(activeScopes, active) : activeScopes;
	};
	const layers = nativeLayers();
	const modal = layers.findLast((layer) => layer.kind === "modal");
	const visible = modal ? layers.slice(layers.indexOf(modal)) : layers;
	const floor = modal?.root ?? null;
	const aboveFloor = (scope) => !floor || renderedUnder(scopeRoot(scope), floor);
	const top = visible.at(-1) ?? null;
	const foreground = (scope) => elementStack.includes(scope) || scopeRoot(scope) === active || innerEscape(scope, active);
	const parts = [];
	let pool = expanded;
	const take = (keep) => {
		const rest = [];
		for (const scope of pool) (keep(scope) ? parts : rest).push(scope);
		pool = rest;
	};
	for (const layer of visible.toReversed()) {
		take((scope) => renderedUnder(scopeRoot(scope), layer.root) || layer === top && foreground(scope) && aboveFloor(scope));
		parts.push(layer.kind === "modal" ? MODAL_BOUNDARY : POPOVER_BOUNDARY);
	}
	if (!modal) parts.push(...pool);
	return ordered(parts);
}
const ownsLeafInvocation = (row) => Boolean(row.run || row.runKey) || [row, ...commandRoutes(row)].some((part) => part.control != null) || commandRoutes(row).some((route) => routedCommand(route));
const runsElsewhere = (row, scope, control) => {
	if (!scope.contextual && scopeRoot(scope) === control) return false;
	const controls = [row, ...commandRoutes(row)].map((part) => word(part.control));
	if (controls.some((each) => each === control)) return false;
	return ownsLeafInvocation(row) || controls.some((each) => each != null);
};
const shadow = (quick = quickShortcuts()) => {
	const claims = [];
	let activation = null;
	return {
		takes: (...request) => {
			const binding = request[0];
			return claims.some((claim) => claim(binding)) || request.length === 3 && activation !== null && activation.claims(binding) && runsElsewhere(request[1], request[2], activation.control);
		},
		past: (scope) => {
			if (scope.claims) claims.push(scope.claims);
			if (scope.activation) activation = {
				claims: scope.activation,
				control: scopeRoot(scope)
			};
			const owned = scope.el ? scope.rows.filter(ownsLeafInvocation).flatMap((row) => declaredBindings(row).filter((binding) => bindingEnabledFor(binding, quick))).filter((binding) => binding !== "Escape" && !activation?.claims(binding)) : [];
			if (owned.length) claims.push((binding) => owned.includes(binding));
		}
	};
};
const landing = (row, run) => () => runLanding(row, run, focused());
function referencedInvocation(reference) {
	if (!reference) return null;
	const current = referencedCommandEntry(reference);
	if (!current || !scopesAt(reference.source).includes(reference.scope)) return null;
	const control = word(current.route?.control ?? reference.row.control);
	const run = commandRun(reference.row, reference.binding, control);
	return run ? {
		id: reference.id,
		row: reference.row,
		entry: current,
		binding: reference.binding ?? void 0,
		run: landing(reference.row, run),
		native: false
	} : null;
}
function invocationFor(row, binding, command, recovered = null) {
	if (!command || !live(row)) return null;
	const current = commandEntries(row, binding === void 0 ? [] : [binding]).find(({ id }) => id === command.id);
	if (!current) return null;
	const reference = routedCommand(current.route);
	if (reference) return referencedInvocation(reference);
	const nativeControl = recovered ?? word(current.route?.control ?? row.control);
	const run = commandRun(row, current.route?.binding ?? binding, nativeControl);
	return run ? {
		id: command?.id ?? row.id,
		row,
		entry: current,
		binding,
		run: landing(row, run),
		native: Boolean(row.native)
	} : null;
}
function announceInvocation(invocation, title = null) {
	const { row, entry } = invocation;
	const route = entry.route;
	document.dispatchEvent(new window.CustomEvent("lf-command-invoked", { detail: {
		id: invocation.id,
		binding: invocation.binding,
		title: title ?? titleOf(route?.title === void 0 ? row : route),
		description: descriptionOf(route?.description === void 0 ? row : route),
		travels: Boolean(row.travels)
	} }));
}
function invokeCommand(command) {
	const invocation = invocationFor(command.row, command.binding, command.entry);
	if (!invocation) return false;
	announceInvocation(invocation);
	invocation.run();
	return true;
}
function unclaimedScopes(binding) {
	const unclaimed = /* @__PURE__ */ new Set();
	const nearer = shadow();
	for (const scope of stack(binding)) {
		if (!nearer.takes(binding)) unclaimed.add(scopeIdentity(scope));
		nearer.past(scope);
	}
	return unclaimed;
}
const INPUT_PENDING = Symbol("command input pending");
function resolveKey(ev) {
	const recovered = recoveredLabelFocus(ev);
	const nearer = shadow();
	for (const scope of stack(answers("Escape", ev) ? "Escape" : null)) {
		let matched = null;
		let pending = false;
		for (const row of scope.rows) {
			const binding = bindings(row).find((b) => answers(b, ev));
			if (!binding || nearer.takes(binding, row, scope)) continue;
			const entries = commandEntries(row, [binding], { includeUnavailable: true });
			pending ||= entries.some(({ route }) => !commandReady(row, route));
			const entry = commandEntries(row, [binding])[0];
			const invocation = invocationFor(row, binding, entry, recovered);
			if (!invocation) continue;
			if (matched) throw new Error(`leaf: ${scope.title ?? "a scope"} has two live meanings for ${binding}: ${titleOf(matched.row)}; ${titleOf(row)}`);
			matched = invocation;
		}
		if (matched) return matched;
		if (pending) return INPUT_PENDING;
		nearer.past(scope);
	}
	return null;
}
const keyReady = (ev) => resolveKey(ev) !== INPUT_PENDING;
const escapePress = () => new window.KeyboardEvent("keydown", { key: "Escape" });
const escapeTakesAStep = () => {
	const matched = resolveKey(escapePress());
	return Boolean(matched) && matched !== INPUT_PENDING;
};
function answerCloseRequest() {
	const matched = resolveKey(escapePress());
	if (!matched || matched === INPUT_PENDING) return;
	const keep = matched.row.keep;
	announceInvocation(matched, keep ? "keep" : null);
	if (keep) keep();
	else matched.run();
}
function dispatchKey(ev) {
	const matched = resolveKey(ev);
	if (!matched || matched === INPUT_PENDING) return false;
	if (!matched.native) ev.preventDefault();
	if (ev.repeat && !matched.row.repeat) return true;
	announceInvocation(matched);
	matched.run();
	return true;
}
const reachableBindings = (row, scope, nearer, unclaimedEscape, commands, quick = quickShortcuts()) => (commands ? declaredBindings(row) : bindings(row)).filter((binding) => commands && !bindingEnabledFor(binding, quick) ? true : binding === "Escape" ? unclaimedEscape.has(scopeIdentity(scope)) : !nearer.takes(binding, row, scope));
function commandMatching(matches, commands = false) {
	const unclaimedEscape = unclaimedScopes("Escape");
	const nearer = shadow();
	for (const scope of stack()) {
		for (const row of scope.rows) {
			if (!live(row)) continue;
			const reachable = reachableBindings(row, scope, nearer, unclaimedEscape, commands);
			const entry = commandEntries(row, reachable).find((command) => matches(command, row) && invocationFor(row, command.binding, command));
			if (entry && (entry.binding != null || allBindings(row).length === 0)) return {
				row,
				binding: entry.binding,
				entry
			};
		}
		nearer.past(scope);
	}
	return null;
}
const commandFor = (id) => commandMatching((command) => command.id === id, true);
function activeCommandLabel(ids) {
	const wanted = new Set(ids);
	const command = commandMatching((entry) => wanted.has(entry.id));
	return command?.binding != null ? spell(command.binding) : "";
}
function availableCommandRoutes({ commands = false, quick = quickShortcuts() } = {}) {
	const routes = /* @__PURE__ */ new Map();
	const unclaimedEscape = unclaimedScopes("Escape");
	const nearer = shadow(quick);
	for (const scope of stack()) {
		for (const row of scope.rows) {
			if (!live(row)) continue;
			const reachable = reachableBindings(row, scope, nearer, unclaimedEscape, commands, quick);
			for (const binding of allBindings(row).length ? reachable : [void 0]) for (const command of commandEntries(row, binding === void 0 ? [] : [binding])) {
				if (!invocationFor(row, binding, command)) continue;
				const reachable = routes.get(row) ?? /* @__PURE__ */ new Set();
				reachable.add(binding);
				routes.set(row, reachable);
			}
		}
		nearer.past(scope);
	}
	return routes;
}
function invokePress({ id, row, binding }) {
	const invocation = invocationFor(row, binding, { id });
	if (!invocation) return false;
	announceInvocation(invocation);
	invocation.run();
	return true;
}
function executeCommand(id) {
	const command = commandFor(id);
	if (!command) return false;
	return invokeCommand(command);
}

//#endregion
//#region runtime/restore-state.js
const ANNOTATIONS_KEY = "lf-annotations";
const USER_VIEW_RESTORE_CASES = [{
	name: "design mode on",
	...tabStore.where(DESIGN_MODE_KEY),
	value: "1"
}, {
	name: "annotations hidden",
	...tabStore.where(ANNOTATIONS_KEY),
	value: "hidden"
}];
function restoreUserView({ setDesignMode }) {
	if (tabStore.get("lf-design-mode") === "1") setDesignMode(true, { spoken: false });
}

//#endregion
export { ANNOTATIONS_KEY, USER_VIEW_RESTORE_CASES, activeCommandLabel, annotationMarkSheets, annotationSheets, answerCloseRequest, availableCommandRoutes, chromeSharedClasses, chromeSheet, dispatchKey, escapeTakesAStep, executeCommand, innermostStance, invokePress, keyReady, marksSheet, onSampleNotice, registerSampleCommand, restoreUserView, sampleNotice, stack, userIn };