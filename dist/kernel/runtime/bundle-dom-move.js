import { afterScript, excludedByInert, isNativeLayer, nextRender, renderedParent, renderedUnder, shadowHost } from "./bundle-portable.js";

//#region vendor/signals-core.js
var j = Symbol.for("preact-signals");
function S() {
	if (h > 1) h--;
	else {
		var t, i = !1;
		for ((function() {
			var e = p;
			for (p = void 0; e !== void 0;) {
				var w = e.S;
				if (w.v === e.v) for (var u = w.t; u !== void 0; u = u.x) u.i === e.i && (u.i = w.i);
				e = e.o;
			}
		})(); c !== void 0;) {
			var o = c;
			for (c = void 0, l++; o !== void 0;) {
				var n = o.u;
				if (o.u = void 0, o.f &= -3, !(8 & o.f) && U(o)) try {
					o.c();
				} catch (e) {
					i || (t = e, i = !0);
				}
				o = n;
			}
		}
		if (l = 0, h--, i) throw t;
	}
}
function W(t) {
	if (h > 0) return t();
	m = ++_, h++;
	try {
		return t();
	} finally {
		S();
	}
}
var s;
var r = void 0;
function d(t) {
	var i = r, o = s;
	r = void 0, s = void 0;
	try {
		return t();
	} finally {
		r = i, s = o;
	}
}
var c = void 0;
var h = 0;
var l = 0;
var _ = 0;
var m = 0;
var p = void 0;
var y = 0;
function g(t) {
	if (r !== void 0) {
		var i = t.n;
		if (i === void 0 || i.t !== r) return i = {
			i: 0,
			S: t,
			p: r.s,
			n: void 0,
			t: r,
			e: void 0,
			x: void 0,
			r: i
		}, r.s !== void 0 && (r.s.n = i), r.s = i, t.n = i, 32 & r.f && t.S(i), i;
		if (i.i === -1) return i.i = 0, i.n !== void 0 && (i.n.p = i.p, i.p !== void 0 && (i.p.n = i.n), i.p = r.s, i.n = void 0, r.s.n = i, r.s = i), i;
	}
}
function f(t, i) {
	this.v = t, this.i = 0, this.n = void 0, this.t = void 0, this.l = 0, this.W = i?.watched, this.Z = i?.unwatched, this.name = i?.name;
}
f.prototype.brand = j;
f.prototype.h = function() {
	return !0;
};
f.prototype.S = function(t) {
	var i = this, o = this.t;
	o !== t && t.e === void 0 && (t.x = o, this.t = t, o !== void 0 ? o.e = t : d(function() {
		var n;
		(n = i.W) == null || n.call(i);
	}));
};
f.prototype.U = function(t) {
	var i = this;
	if (this.t !== void 0) {
		var o = t.e, n = t.x;
		o !== void 0 && (o.x = n, t.e = void 0), n !== void 0 && (n.e = o, t.x = void 0), t === this.t && (this.t = n, n === void 0 && d(function() {
			var e;
			(e = i.Z) == null || e.call(i);
		}));
	}
};
f.prototype.subscribe = function(t) {
	var i = this;
	return x(function() {
		var o = i.value;
		d(function() {
			return t(o);
		});
	}, { name: "sub" });
};
f.prototype.valueOf = function() {
	return this.value;
};
f.prototype.toString = function() {
	return this.value + "";
};
f.prototype.toJSON = function() {
	return this.value;
};
f.prototype.peek = function() {
	var t = this;
	return d(function() {
		return t.value;
	});
};
Object.defineProperty(f.prototype, "value", {
	get: function() {
		var t = g(this);
		return t !== void 0 && (t.i = this.i), this.v;
	},
	set: function(t) {
		if (t !== this.v) {
			if (l > 100) throw new Error("Cycle detected");
			(function(o) {
				h !== 0 && l === 0 && o.l !== m && (o.l = m, p = {
					S: o,
					v: o.v,
					i: o.i,
					o: p
				});
			})(this), this.v = t, this.i++, y++, h++;
			try {
				for (var i = this.t; i !== void 0; i = i.x) i.t.N();
			} finally {
				S();
			}
		}
	}
});
function Z(t, i) {
	return new f(t, i);
}
function U(t) {
	for (var i = t.s; i !== void 0; i = i.n) if (i.S.i !== i.i || !i.S.h() || i.S.i !== i.i) return !0;
	return !1;
}
function C(t) {
	for (var i = t.s; i !== void 0; i = i.n) {
		var o = i.S.n;
		if (o !== void 0 && (i.r = o), i.S.n = i, i.i = -1, i.n === void 0) {
			t.s = i;
			break;
		}
	}
}
function O(t) {
	for (var i = t.s, o = void 0; i !== void 0;) {
		var n = i.p;
		i.i === -1 ? (i.S.U(i), n !== void 0 && (n.n = i.n), i.n !== void 0 && (i.n.p = n)) : o = i, i.S.n = i.r, i.r !== void 0 && (i.r = void 0), i = n;
	}
	t.s = o;
}
function v(t, i) {
	f.call(this, void 0, i), this.x = t, this.s = void 0, this.g = y - 1, this.f = 4;
}
v.prototype = new f();
v.prototype.h = function() {
	if (this.f &= -3, 1 & this.f) return !1;
	if ((36 & this.f) == 32 || (this.f &= -5, this.g === y)) return !0;
	if (this.g = y, this.f |= 1, this.i > 0 && !U(this)) return this.f &= -2, !0;
	var t = r;
	try {
		C(this), r = this;
		var i = this.x();
		(16 & this.f || this.v !== i || this.i === 0) && (this.v = i, this.f &= -17, this.i++);
	} catch (o) {
		this.v = o, this.f |= 16, this.i++;
	}
	return r = t, O(this), this.f &= -2, !0;
};
v.prototype.S = function(t) {
	if (this.t === void 0) {
		this.f |= 36;
		for (var i = this.s; i !== void 0; i = i.n) i.S.S(i);
	}
	f.prototype.S.call(this, t);
};
v.prototype.U = function(t) {
	if (this.t !== void 0 && (f.prototype.U.call(this, t), this.t === void 0)) {
		this.f &= -33;
		for (var i = this.s; i !== void 0; i = i.n) i.S.U(i);
	}
};
v.prototype.N = function() {
	if (!(2 & this.f)) {
		this.f |= 6;
		for (var t = this.t; t !== void 0; t = t.x) t.t.N();
	}
};
Object.defineProperty(v.prototype, "value", { get: function() {
	if (1 & this.f) throw new Error("Cycle detected");
	var t = g(this);
	if (this.h(), t !== void 0 && (t.i = this.i), 16 & this.f) throw this.v;
	return this.v;
} });
function J(t, i) {
	return new v(t, i);
}
function k(t) {
	var i = t.m;
	if (t.m = void 0, typeof i == "function") {
		h++;
		var o = r;
		r = void 0;
		try {
			i();
		} catch (n) {
			throw t.f &= -2, t.f |= 8, b(t), n;
		} finally {
			r = o, S();
		}
	}
}
function b(t) {
	for (var i = t.s; i !== void 0; i = i.n) i.S.U(i);
	t.x = void 0, t.s = void 0, k(t);
}
function P(t) {
	if (r !== this) throw new Error("Out-of-order effect");
	O(this), r = t, this.f &= -2, 8 & this.f && b(this), S();
}
function a(t, i) {
	this.x = t, this.m = void 0, this.s = void 0, this.u = void 0, this.f = 32, this.name = i?.name, s && s.push(this);
}
a.prototype.c = function() {
	var t = this.S();
	try {
		if (8 & this.f || this.x === void 0) return;
		var i = this.x();
		typeof i == "function" && (this.m = i);
	} finally {
		t();
	}
};
a.prototype.S = function() {
	if (1 & this.f) throw new Error("Cycle detected");
	this.f |= 1, this.f &= -9, k(this), C(this), h++;
	var t = r;
	return r = this, P.bind(this, t);
};
a.prototype.N = function() {
	2 & this.f || (this.f |= 2, this.u = c, c = this);
};
a.prototype.d = function() {
	this.f |= 8, 1 & this.f || b(this);
};
a.prototype.dispose = function() {
	this.d();
};
function x(t, i) {
	var o = new a(t, i);
	try {
		o.c();
	} catch (e) {
		throw o.d(), e;
	}
	var n = o.d.bind(o);
	return n[Symbol.dispose] = n, n;
}
function q(t) {
	return class extends t {
		performUpdate() {
			var i;
			if (this.isUpdatePending === !1) return;
			(i = this._$Oo) === null || i === void 0 || i.call(this);
			let o = !0;
			this._$Oo = x((() => {
				o ? (o = !1, super.performUpdate()) : this.requestUpdate();
			}));
		}
		connectedCallback() {
			super.connectedCallback(), this.requestUpdate();
		}
		disconnectedCallback() {
			var i;
			super.disconnectedCallback(), (i = this._$Oo) === null || i === void 0 || i.call(this);
		}
	};
}

//#endregion
//#region runtime/keeps.js
const keeps = (...args) => document.documentElement.lfInitial.keepsAttribute(...args);
function keepsHidden(node, hidden) {
	if (node && node.hidden !== hidden) node.hidden = hidden;
}
function keepsText(node, text) {
	const said = String(text ?? "");
	if (node && node.textContent !== said) node.textContent = said;
}
const atLayoutPrecision = (length) => Math.round(length * 64) / 64;
const layoutPx = (length) => `${atLayoutPrecision(length)}px`;
const roomPx = (length) => `${Math.floor(length * 64) / 64}px`;

//#endregion
//#region runtime/control-selectors.js
const TEXT_FIELD = document.documentElement.lfInputs.textField;
const MODIFIER_KEYS = [
	"Shift",
	"Alt",
	"Control",
	"Meta"
];
const CARET_KEYS = [
	"ArrowLeft",
	"ArrowRight",
	"ArrowUp",
	"ArrowDown",
	"Home",
	"End",
	"PageUp",
	"PageDown"
];
const selectsAll = (event) => event.key.toLowerCase() === "a" && (event.metaKey || event.ctrlKey);
const TEXT_BOX = document.documentElement.lfInputs.textBox;
const TAB_STOP = `a[href], button, input, select, ${TEXT_BOX}, summary, [contenteditable]:not([contenteditable="false"]), [tabindex]:not([tabindex="-1"])`;
const PRESS_SELECTORS = [
	"a[href]",
	"audio[controls]",
	"button",
	"img[usemap]",
	"input:not([type='hidden'])",
	"label",
	"select",
	"summary",
	TEXT_BOX,
	"video[controls]",
	"video[data-lf-player]",
	"[role='button']",
	"[role='checkbox']",
	"[role='combobox']",
	"[role='link']",
	"[role='menuitem']",
	"[role='menuitemcheckbox']",
	"[role='menuitemradio']",
	"[role='option']",
	"[role='radio']",
	"[role='scrollbar']",
	"[role='searchbox']",
	"[role='separator'][tabindex]",
	"[role='slider']",
	"[role='spinbutton']",
	"[role='switch']",
	"[role='tab']",
	"[role='textbox']",
	"[role='treeitem']"
];
const LENT_REACH_STOP = "data-lf-lent-reach-stop";
const REGION_SELECTORS = [
	`[tabindex]:not([tabindex='-1']):not([${LENT_REACH_STOP}]):not([role='tabpanel'])`,
	"[contenteditable]:not([contenteditable='false'])",
	"[draggable='true']",
	"[role='application']",
	"[role='grid']",
	"[role='gridcell']",
	"[role='listbox']",
	"[role='menu']",
	"[role='menubar']",
	"[role='radiogroup']",
	"[role='tablist']",
	"[role='tree']",
	"[role='treegrid']"
];
const PRESSES = PRESS_SELECTORS.join(",");
const WORKS = [...PRESS_SELECTORS, ...REGION_SELECTORS].join(",");

//#endregion
//#region runtime/focus.js
function* renderedElements(node) {
	const children = node.localName === "slot" ? node.assignedElements({ flatten: true }) : (node.shadowRoot ?? node).children;
	for (const child of children) {
		yield child;
		if (child.shadowRoot && parseInt(child.getAttribute("tabindex")) < 0) continue;
		yield* renderedElements(child);
	}
}
const SEQUENTIAL = `${TAB_STOP}, iframe, audio[controls], video[controls]`;
const tabStops = (root) => [...renderedElements(root)].filter((node) => node.matches(SEQUENTIAL) && node.tabIndex >= 0 && !node.shadowRoot?.delegatesFocus && !node.matches(":disabled") && !node.inert && node.checkVisibility({ visibilityProperty: true }));
const canPlaceFocus = () => window === window.top || document.hasFocus();
const CAUSES = /* @__PURE__ */ new Set([
	"move",
	"step",
	"return",
	"press"
]);
function focusDestination(destination, cause, { caret = null, ...unknown } = {}) {
	if (!CAUSES.has(cause)) throw new TypeError(`focusDestination: no cause ${cause}`);
	const unexpected = Object.keys(unknown);
	if (unexpected.length) throw new TypeError(`focusDestination: unknown options ${unexpected.join(", ")}`);
	if (!canPlaceFocus()) return;
	const options = {
		preventScroll: true,
		focusVisible: pressLed() ? void 0 : true
	};
	placed(cause, () => {
		destination.focus(options);
		if (!landedOn(destination) && lendable(destination)) lendStop(destination, options);
	});
	if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}
let placing = null;
const placed = (cause, move) => {
	const was = placing;
	placing ??= cause;
	try {
		return move();
	} finally {
		placing = was;
	}
};
const landedOn = (node) => node === document.body ? node.matches(":focus") : node.getRootNode().activeElement === node || Boolean(node.shadowRoot?.activeElement);
const lendable = (node) => drawn(node) && !node.matches(TAB_STOP);
const lent = /* @__PURE__ */ new WeakSet();
const wearsLentStop = (element) => lent.has(element);
function whenLeft(element, leave) {
	const blur = () => {
		if (element.getRootNode().activeElement === element) return;
		element.removeEventListener("blur", blur);
		leave();
	};
	element.addEventListener("blur", blur);
}
function lendStop(destination, options) {
	if (destination.hasAttribute("tabindex")) return;
	const giveBack = () => {
		lent.delete(destination);
		if (destination.getAttribute("tabindex") === "-1") destination.removeAttribute("tabindex");
	};
	lent.add(destination);
	destination.tabIndex = -1;
	destination.focus(options);
	if (!landedOn(destination)) {
		giveBack();
		return;
	}
	whenLeft(destination, giveBack);
}
const CARETED = /* @__PURE__ */ new Set([
	"text",
	"search",
	"url",
	"tel",
	"password"
]);
const holdsCaret = (node) => node.matches(TEXT_BOX) || node.tagName === "INPUT" && CARETED.has(node.type);
function readCaret(node) {
	if (!node || !holdsCaret(node) || node.selectionStart === null) return null;
	return [
		node.selectionStart,
		node.selectionEnd,
		node.selectionDirection
	];
}
const deepFocus = (at = document.activeElement) => {
	while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
	return at;
};
let labelPress = null;
const heldByLabel = () => labelPress?.held.isConnected ? labelPress.held : null;
function finishLabelPress() {
	const press = labelPress;
	if (!press) return null;
	labelPress = null;
	return press;
}
function landLabelPress() {
	if (!finishLabelPress()) return;
	setTimeout(() => {
		if (labelPress) return;
		const at = deepFocus();
		if (at && at !== document.body) return reconcile(null, pressedPath);
		if (!drawn(published?.deref())) return;
		placements += 1;
		lastLocation = null;
		publish(null, cause(null));
	});
}
const currentLocation = Z(0);
const focusRevision = () => currentLocation.value;
const focused = (tree = null) => {
	let at = heldByLabel() ?? deepFocus();
	if (tree) while (at && at.getRootNode() !== tree) at = shadowHost(at.getRootNode());
	return at;
};
const selectionOf = (node) => {
	const root = node.getRootNode();
	const own = root;
	return root instanceof ShadowRoot && own.getSelection?.() || getSelection();
};
function currentLocationNodes() {
	const at = focused();
	const selection = getSelection();
	return [
		at && at !== document.body ? at : null,
		selection?.focusNode ?? null,
		selection?.anchorNode ?? null
	].filter(Boolean);
}
function currentLocationTouches(node) {
	if (!node) return false;
	if (currentLocationNodes().some((at) => at === node || node.contains(at))) return true;
	const selection = selectionOf(node);
	return Boolean(selection?.rangeCount && selection.getRangeAt(0).intersectsNode(node));
}
let restoring = false;
let placements = 0;
let lastLocation = null;
const readers = /* @__PURE__ */ new Set();
const onCurrentLocation = (read) => {
	readers.add(read);
	return () => readers.delete(read);
};
let published = null;
let departed = false;
let readings = 0;
let paintDestination = null;
let paintedFocus = null;
let paintedWithin = /* @__PURE__ */ new Set();
let paintedVisible = null;
let paintedVisibleWithin = /* @__PURE__ */ new Set();
const visibilityReaders = /* @__PURE__ */ new Set();
const onFocusVisibility = (read) => {
	visibilityReaders.add(read);
	return () => visibilityReaders.delete(read);
};
function markFocus(node, name, present) {
	keeps(node, `data-lf-${name}`, present ? "" : null);
	if (!present) {
		if (node.part?.contains(`lf-${name}`)) node.part.remove(`lf-${name}`);
	} else if (node.getRootNode().nodeType === Node.DOCUMENT_FRAGMENT_NODE && node.hasAttribute("part")) node.part.add(`lf-${name}`);
}
function visibleFocus(node = focused()) {
	return node && node !== document.body && node !== document.documentElement && (node.matches(":focus-visible") || node.matches(TEXT_BOX) || node.localName === "iframe" && !pressLed()) ? node : null;
}
function paintFocus(node) {
	const next = node === document.body || node === document.documentElement ? null : node;
	if (next !== paintedFocus) {
		if (paintedFocus) markFocus(paintedFocus, "focus", false);
		if (next) markFocus(next, "focus", true);
		paintedFocus = next;
	}
	const within = /* @__PURE__ */ new Set();
	for (let owner = next; owner && owner !== document.body && owner !== document.documentElement; owner = renderedParent(owner)) within.add(owner);
	for (const owner of paintedWithin) if (!within.has(owner)) markFocus(owner, "focus-within", false);
	for (const owner of within) if (!paintedWithin.has(owner)) markFocus(owner, "focus-within", true);
	paintedWithin = within;
	const visible = visibleFocus(next);
	if (visible !== paintedVisible) {
		if (paintedVisible) markFocus(paintedVisible, "focus-visible", false);
		if (visible) markFocus(visible, "focus-visible", true);
		paintedVisible = visible;
		for (const read of visibilityReaders) read();
	}
	const visibleWithin = visible ? within : /* @__PURE__ */ new Set();
	for (const owner of paintedVisibleWithin) if (!visibleWithin.has(owner)) markFocus(owner, "focus-visible-within", false);
	for (const owner of visibleWithin) if (!paintedVisibleWithin.has(owner)) markFocus(owner, "focus-visible-within", true);
	paintedVisibleWithin = visibleWithin;
}
const refreshFocusPaint = () => {
	const node = paintDestination?.deref();
	if (node?.isConnected && node !== deepFocus() && node !== heldByLabel()) return;
	if (node?.isConnected) watchCurrentLocationAround(node);
	paintFocus(node?.isConnected ? node : null);
};
let returnPaintPending = false;
const paintAfterScript = () => {
	if (!returnPaintPending) refreshFocusPaint();
};
const queueFocusPaint = () => afterScript(paintAfterScript);
const queueReturnFocusPaint = () => {
	if (returnPaintPending) return;
	returnPaintPending = true;
	nextRender(() => {
		if (!returnPaintPending) return;
		returnPaintPending = false;
		refreshFocusPaint();
	});
};
const paintRoots = /* @__PURE__ */ new WeakSet();
function watchFocusPaintIn(root) {
	if (paintRoots.has(root)) return;
	paintRoots.add(root);
	new MutationObserver(queueFocusPaint).observe(root, {
		childList: true,
		subtree: true
	});
	root.addEventListener("slotchange", queueFocusPaint);
}
function publish(node, cause) {
	watchCurrentLocationAround(node);
	paintDestination = node && new WeakRef(node);
	if (cause === "return") queueReturnFocusPaint();
	else {
		returnPaintPending = false;
		queueFocusPaint();
	}
	if (node === (published?.deref() ?? null) && !departed) return;
	departed = false;
	const left = published?.deref() ?? null;
	const reading = ++readings;
	currentLocation.value = reading;
	if (cause === "drop") departed = true;
	else published = node && new WeakRef(node);
	if (node) placeInput = "focus";
	const was = [placing, restoring];
	[placing, restoring] = [null, false];
	try {
		for (const read of readers) {
			try {
				read(node, cause, left);
			} catch (error) {
				reportError(error);
			}
			if (readings !== reading) return;
		}
	} finally {
		[placing, restoring] = was;
	}
}
let pressedPath = null;
const pressedOn = (node) => Boolean(pressedPath) && pressedPath.some((ref) => {
	const at = ref.deref();
	return at === node || at?.localName === "label" && at.control === node;
});
const pressLed = () => pressedPath !== null;
let stepping = null;
const leftClosedLayer = (left) => {
	const layer = left?.closest?.("dialog, [popover]");
	return Boolean(layer) && !(layer.open === true || isNativeLayer(layer));
};
const cause = (node, left = null) => placing ?? (leftClosedLayer(left) ? "return" : pressedOn(node) ? "press" : stepping ? "step" : "move");
const read = /* @__PURE__ */ new WeakSet();
function readFocusEvent(event) {
	if (read.has(event)) return;
	read.add(event);
	if (closing) return;
	if (heldByLabel()) {
		if (placing === null) return;
		finishLabelPress();
	}
	if (!restoring && !(placing === null && leftClosedLayer(event.relatedTarget))) placements += 1;
	const at = deepFocus();
	lastLocation = at && new WeakRef(at);
	publish(at, cause(at, event.relatedTarget));
}
function watchCurrentLocationAround(node) {
	for (let at = node; at; at = renderedParent(at)) watchCurrentLocationIn(at.getRootNode());
}
function enter(event) {
	if (read.has(event)) return;
	read.add(event);
	watchCurrentLocationAround(deepFocus());
}
function watchCurrentLocationIn(root) {
	root.addEventListener("focus", enter, true);
	root.addEventListener("focusin", readFocusEvent, true);
	watchFocusPaintIn(root);
}
watchCurrentLocationIn(document);
watchCurrentLocationAround(deepFocus());
document.addEventListener("focusout", (event) => {
	if (event.relatedTarget !== null) departed = true;
	const left = event.composedPath()[0];
	lastLocation = new WeakRef(left);
	if (restoring) return;
	const departure = readings;
	setTimeout(() => {
		if (readings !== departure) return;
		const at = document.activeElement;
		if (at !== null && at !== document.body) return;
		if (heldByLabel()) return;
		if (!drawn(left)) return publish(null, "drop");
		if (left !== document.body) placements += 1;
		if (lastLocation?.deref() === left) lastLocation = null;
		publish(null, cause(null));
	});
}, true);
const sequential = (event) => event.key === "Tab" && !event.altKey && !event.ctrlKey && !event.metaKey;
function reconcile(step, pressed) {
	if (heldByLabel()) return;
	const deep = deepFocus();
	const at = deep === document.body ? null : deep;
	const was = published?.deref() ?? null;
	if (at === was || !at && was?.localName !== "iframe") return;
	placements += 1;
	lastLocation = at && new WeakRef(at);
	const input = [stepping, pressedPath];
	[stepping, pressedPath] = [step, pressed];
	try {
		publish(at, cause(at));
	} finally {
		[stepping, pressedPath] = input;
	}
}
function inputInFrame(frame, type) {
	if (deepFocus() !== frame) return;
	if (type === "keydown") pressedPath = null;
	else if (type === "pointerdown" || type === "touchstart") pressedPath = [new WeakRef(frame)];
	if (published?.deref() === frame) queueFocusPaint();
	else reconcile(null, pressedPath);
}
addEventListener("click", () => {
	const pressed = pressedPath;
	setTimeout(() => {
		reconcile(null, pressed);
		queueFocusPaint();
	});
}, {
	capture: true,
	passive: true
});
const inputs = document.documentElement.lfInputs;
const inputCount = () => inputs.count;
const onUserInput = (read) => inputs.observe(read);
let keyCarets = null;
onUserInput((event) => {
	if (event.type !== "keydown") return;
	const carets = /* @__PURE__ */ new Map();
	for (const node of event.composedPath()) {
		const caret = node instanceof Element && readCaret(node);
		if (caret) carets.set(node, caret);
	}
	keyCarets = carets;
	setTimeout(() => {
		if (keyCarets === carets) keyCarets = null;
	});
});
const caretAtKey = (node) => keyCarets?.get(node) ?? null;
onUserInput((event) => {
	if (event.type !== "blur") return;
	landLabelPress();
	endPress(event, false);
});
let placeInput = "focus";
for (const type of [
	"pointermove",
	"pointerdown",
	"wheel"
]) addEventListener(type, () => placeInput = "pointer", {
	capture: true,
	passive: true
});
addEventListener("click", (event) => {
	if (event.isTrusted && event.button === 0) placeInput = focused()?.contains(event.composedPath()[0]) ? "focus" : "pointer";
}, {
	capture: true,
	passive: true
});
const recentPlaceInput = () => placeInput;
let press = null;
const pressing = () => press;
const pressReaders = /* @__PURE__ */ new Set();
const onPress = (read) => {
	pressReaders.add(read);
	return () => pressReaders.delete(read);
};
const onPressAway = (away, dismiss) => onPress((start, from) => start.button === 0 && away(from) ? (end, completed) => {
	const path = end.composedPath();
	if (completed && away(path)) dismiss(path, from);
} : null);
addEventListener("pointerdown", (event) => {
	if (!event.isPrimary) return;
	const path = event.composedPath();
	const ends = [];
	press = {
		pointerId: event.pointerId,
		path,
		ends
	};
	for (const read of pressReaders) {
		const end = read(event, path);
		if (end) ends.push(end);
	}
	if (event.button !== 0 || labelPress) return;
	const label = path.find((node) => node?.localName === "label" && node.control);
	const held = label && deepFocus();
	if (!held || held === document.body) return;
	labelPress = {
		held,
		pointerId: event.pointerId,
		label
	};
}, {
	capture: true,
	passive: true
});
function endPress(event, completed) {
	if (!press) return;
	const { ends } = press;
	press = null;
	for (const end of ends) end(event, completed);
}
for (const type of ["pointerup", "pointercancel"]) addEventListener(type, (event) => {
	if (event.pointerId === labelPress?.pointerId && (type === "pointercancel" || !event.composedPath().includes(labelPress.label))) landLabelPress();
	if (event.pointerId === press?.pointerId) endPress(event, type === "pointerup");
}, {
	capture: true,
	passive: true
});
addEventListener("contextmenu", (event) => {
	landLabelPress();
	endPress(event, false);
}, {
	capture: true,
	passive: true
});
addEventListener("click", landLabelPress, {
	capture: true,
	passive: true
});
const recoveredLabelKeys = /* @__PURE__ */ new WeakMap();
const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);
addEventListener("keydown", (event) => {
	placeInput = "focus";
	if (!labelPress || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
	const active = deepFocus();
	const { held } = finishLabelPress();
	if (active === held || !held.isConnected) return;
	focusDestination(held, "return");
	if (deepFocus() === held) recoveredLabelKeys.set(event, held);
}, true);
for (const type of [
	"keydown",
	"pointerdown",
	"wheel",
	"touchstart"
]) addEventListener(type, (event) => {
	if (type === "pointerdown") pressedPath = event.composedPath().map((node) => new WeakRef(node));
	else if (type === "keydown") pressedPath = null;
	stepping = null;
	if (type === "keydown" || type === "pointerdown") {
		const step = type === "keydown" && sequential(event) ? event : null;
		const pressed = pressedPath;
		stepping = step;
		setTimeout(() => {
			if (step && stepping === step) stepping = null;
			reconcile(step, pressed);
			queueFocusPaint();
		});
	}
	const at = deepFocus();
	if (at && at !== document.body || heldByLabel()) return;
	lastLocation = null;
	publish(null, cause(null));
}, {
	capture: true,
	passive: true
});
function ringBox(node) {
	if (!node?.matches?.(":focus, [data-lf-focus]")) return node;
	for (let box = renderedParent(node); box instanceof Element; box = renderedParent(box)) if (getComputedStyle(box).getPropertyValue("--lf-wears-ring") === "1") return box;
	return node;
}
const drawn = (node) => node?.isConnected && !excludedByInert(node) && node.checkVisibility({ visibilityProperty: true });
const dropped = () => {
	const at = deepFocus();
	if (at && at !== document.body) return null;
	const node = lastLocation?.deref();
	return node && !drawn(node) ? node : null;
};
function holdFocus(scope, { key = null } = {}) {
	const node = heldIn(scope);
	if (!node) return null;
	const restore = holdOn(node);
	if (!key) return restore;
	let item = node;
	while (item && !item.matches?.(`[${key}]`)) item = renderedParent(item);
	if (!item || item === scope || !renderedUnder(item, scope)) return restore;
	const tree = item.getRootNode() === scope.getRootNode() ? scope : item.getRootNode();
	const items = () => [...tree.querySelectorAll(`[${key}]`)].filter((item) => renderedUnder(item, scope));
	const keys = [...new Set(items().map((each) => each.getAttribute(key)))];
	const at = keys.indexOf(item.getAttribute(key));
	const order = [
		keys[at],
		...keys.slice(at + 1),
		...keys.slice(0, at).reverse()
	];
	let control = node;
	while (control.getRootNode() !== item.getRootNode()) {
		const host = shadowHost(control.getRootNode());
		if (!host) break;
		control = host;
	}
	const like = control.localName + [...control.classList].map((name) => `.${CSS.escape(name)}`).join("");
	const [same, ...rest] = order;
	return (...standIns) => {
		let byKey = null;
		const keyed = (value) => {
			if (!byKey) {
				byKey = /* @__PURE__ */ new Map();
				for (const each of items()) {
					const at = each.getAttribute(key);
					if (!byKey.has(at)) byKey.set(at, []);
					byKey.get(at).push(each);
				}
			}
			return byKey.get(value) ?? [];
		};
		const matching = (root) => {
			if (root.matches(like) && drawn(root)) return root;
			const assigned = root.localName === "slot" ? root.assignedElements({ flatten: true }) : [];
			for (const child of assigned.length ? assigned : root.children) {
				const found = matching(child);
				if (found) return found;
			}
			return null;
		};
		const find = (value) => {
			const found = keyed(value).filter(drawn);
			return (like && found.find((each) => each.matches(like))) ?? (like && found.map(matching).find(Boolean)) ?? found[0] ?? null;
		};
		const neighbour = (value) => () => {
			const place = find(value);
			if (!place || !drawn(place)) return null;
			focusDestination(place, "return");
			return landedOn(place);
		};
		return restore(() => find(same), ...rest.map(neighbour), ...standIns);
	};
}
const heldIn = (scope) => {
	const held = heldByLabel();
	if (held) return renderedUnder(held, scope) ? held : null;
	const currentLocation = deepFocus(scope.getRootNode().activeElement ?? scope.ownerDocument.activeElement);
	if (currentLocation && currentLocation !== document.body && renderedUnder(currentLocation, scope)) return currentLocation;
	const node = lastLocation?.deref();
	return node && renderedUnder(node, scope) ? dropped() : null;
};
const currentLocationIn = (scope) => {
	const at = focused();
	return Boolean(at) && at !== document.body && renderedUnder(at, scope);
};
function rove(items, stop) {
	for (const item of items) keeps(item, "tabindex", item === stop ? 0 : -1);
}
const openers = /* @__PURE__ */ new WeakMap();
function openLayer(layer, opener = focused()) {
	openers.set(layer, opener && opener !== document.body ? opener : null);
}
const openerOf = (layer) => openers.get(layer) ?? null;
let closing = 0;
let deferredLanding = null;
let landingLayer = false;
function layerLanding(land) {
	return (...args) => {
		if (!landingLayer) throw new Error("A layer's landing runs only as the layer closes");
		return land(...args);
	};
}
function closeLayer(close, land = null) {
	closing += 1;
	let deferred = null;
	const landingAround = landingLayer;
	landingLayer = false;
	try {
		close();
	} finally {
		landingLayer = landingAround;
		closing -= 1;
		if (!closing) [deferred, deferredLanding] = [deferredLanding, null];
	}
	if (closing) {
		if (land) deferredLanding ??= land;
		return;
	}
	const landing = land || deferred;
	if (landing) {
		const outer = landingLayer;
		landingLayer = true;
		try {
			landing();
		} finally {
			landingLayer = outer;
		}
	}
	const at = deepFocus();
	if (!at || at === document.body || at === published?.deref()) return;
	lastLocation = new WeakRef(at);
	publish(at, "return");
}
function holdCurrentLocation() {
	const at = focused();
	const node = at && at !== document.body ? at : dropped();
	return node ? {
		node,
		restore: holdOn(node)
	} : null;
}
const carried = /* @__PURE__ */ new WeakMap();
const carriedFrom = (node) => carried.get(node) ?? null;
function holdOn(held) {
	const caret = readCaret(held);
	const began = placements;
	return (...standIns) => {
		if (placements !== began) return false;
		for (const standIn of [held, ...standIns]) {
			if (placements !== began) return false;
			const place = typeof standIn === "function" ? standIn() : standIn;
			if (place?.then) return place.then((destination) => {
				if (!(destination instanceof Element) || !drawn(destination) || deepFocus() !== destination) return false;
				return land(() => {
					focusDestination(destination, "return", { caret });
					return landedOn(destination);
				});
			});
			if (place === true) return true;
			if (!(place instanceof Element) || !drawn(place)) continue;
			if (place === held && deepFocus() === held) return true;
			if (land(() => {
				focusDestination(place, "return", { caret });
				return landedOn(place);
			})) {
				const before = carriedFrom(held);
				if (place !== held) carried.set(place, before?.inputs === inputCount() ? before : {
					from: held,
					inputs: inputCount()
				});
				return true;
			}
		}
		return false;
	};
}
const land = (landing) => {
	const was = restoring;
	restoring = true;
	try {
		return landing();
	} finally {
		restoring = was;
	}
};
const typesText = inputs.typesText;
const takesLetters = inputs.takesLetters;
function controlNavigationKeys(node) {
	if (node?.matches("input[type=\"radio\"], [role=\"radio\"]")) return [
		"ArrowLeft",
		"ArrowRight",
		"ArrowUp",
		"ArrowDown"
	];
	if (node?.matches("input[type=\"range\"], [role=\"slider\"]")) return [
		"ArrowLeft",
		"ArrowRight",
		"ArrowUp",
		"ArrowDown",
		"Home",
		"End",
		"PageUp",
		"PageDown"
	];
	return [];
}
let readingBlock = () => null;
function declareReading(read) {
	readingBlock = read;
}
function releaseFocus() {
	focusDestination(document.body, "move");
	document.body.blur();
}
let released = () => {};
function declareRelease(release) {
	released = release;
}
let letGoes = 0;
function release() {
	const before = letGoes;
	released();
	if (letGoes === before) letGo();
}
const letGoReaders = /* @__PURE__ */ new Set();
const onLetGo = (read) => {
	letGoReaders.add(read);
	return () => letGoReaders.delete(read);
};
function letGo() {
	letGoes++;
	const from = focused();
	const block = readingBlock(from);
	if (!block?.isConnected) releaseFocus();
	else {
		focusDestination(block, "move");
		block.blur();
	}
	if (from && from !== document.body) for (const read of letGoReaders) read(from);
}
function handBack(...destinations) {
	const places = destinations.filter((node) => node && node !== document.body);
	const landed = () => {
		const at = placements;
		return places.some((node) => {
			if (placements !== at) return true;
			if (!drawn(node)) return false;
			focusDestination(node, "return");
			return landedOn(node);
		});
	};
	if (landed()) return;
	if (!places.some((node) => node.isConnected)) {
		letGo();
		return;
	}
	const yielded = !drawn(deepFocus());
	if (yielded) releaseFocus();
	const began = placements;
	const pendingInput = inputCount();
	nextRender(() => {
		if (inputCount() !== pendingInput || placements !== began || yielded && deepFocus() !== document.body || landed()) return;
		letGo();
	});
}

//#endregion
//#region runtime/dom-move.js
function move(parent, node, before) {
	if (node.parentNode === parent && (before === node || node.nextSibling === before)) return node;
	if (parent.isConnected) watchCurrentLocationIn(parent.getRootNode());
	if (parent.moveBefore && node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })) parent.moveBefore(node, before);
	else {
		const restore = node.nodeType === Node.ELEMENT_NODE ? holdFocus(node) : null;
		parent.insertBefore(node, before);
		restore?.();
	}
	return node;
}
document.documentElement.lfInitial.move = move;

//#endregion
export { CARET_KEYS, J, LENT_REACH_STOP, MODIFIER_KEYS, PRESSES, TAB_STOP, TEXT_BOX, TEXT_FIELD, W, WORKS, Z, atLayoutPrecision, canPlaceFocus, caretAtKey, carriedFrom, closeLayer, controlNavigationKeys, currentLocationIn, currentLocationNodes, currentLocationTouches, d, declareReading, declareRelease, deepFocus, drawn, focusDestination, focusRevision, focused, handBack, holdCurrentLocation, holdFocus, inputCount, inputInFrame, keeps, keepsHidden, keepsText, layerLanding, layoutPx, letGo, move, onCurrentLocation, onFocusVisibility, onLetGo, onPress, onPressAway, onUserInput, openLayer, openerOf, pressLed, pressing, q, readCaret, recentPlaceInput, recoveredLabelFocus, release, releaseFocus, ringBox, roomPx, rove, selectsAll, tabStops, takesLetters, typesText, visibleFocus, watchCurrentLocationIn, wearsLentStop, whenLeft, x };