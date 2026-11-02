import "/runtime/document-inputs.js";
import { Directive, LitElement, PartType, directive, html, nothing, render, unsafeSVG } from "/vendor/lit.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

//#region runtime/queued-work.js
const jobObservers = /* @__PURE__ */ new Set();
const jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
	jobObservers.add(observer);
	return () => jobObservers.delete(observer);
}
const announce$1 = (phase, job, observers) => {
	for (const observer of observers) observer(phase, job);
};
function enqueueWork(callback) {
	const job = Object.freeze({ callback });
	const observers = [...jobObservers];
	jobCohorts.set(job, observers);
	announce$1("enqueue", job, observers);
	return job;
}
function claim(job) {
	const observers = jobCohorts.get(job);
	jobCohorts.delete(job);
	return observers;
}
function runWork(job, ...args) {
	const observers = claim(job);
	if (!observers) return;
	const callback = job.callback;
	try {
		announce$1("run", job, observers);
		return callback(...args);
	} finally {
		announce$1("finish", job, observers);
	}
}
function bindQueuedWork(callback) {
	const job = enqueueWork(callback);
	return (...args) => runWork(job, ...args);
}
function cancelWork(job) {
	const observers = claim(job);
	if (observers) announce$1("cancel", job, observers);
}

//#endregion
//#region runtime/frame-visibility.js
const child = document.documentElement.lfSample;
let admitted = false;
const observers = /* @__PURE__ */ new Set();
const readings$1 = /* @__PURE__ */ new Map();
let readingId = 0;
function watchFrame(frame, callback) {
	let intersecting = false;
	const seen = new IntersectionObserver((entries) => {
		for (const { intersectionRect: { width, height } } of entries) intersecting = width > 0 && height > 0;
		callback();
	}, { threshold: [
		0,
		Number.EPSILON,
		1
	] });
	seen.observe(frame);
	const styled = new MutationObserver((records) => {
		if (records.some(({ target }) => target === frame || target.contains(frame))) callback();
	});
	styled.observe(frame.ownerDocument, {
		subtree: true,
		attributes: true,
		attributeFilter: [
			"inert",
			"open",
			"hidden",
			"aria-hidden",
			"class",
			"style"
		]
	});
	return {
		shown: () => intersecting && frame.checkVisibility({ visibilityProperty: true }) && getComputedStyle(frame).contentVisibility !== "hidden",
		stop: () => {
			seen.disconnect();
			styled.disconnect();
		}
	};
}
const owners$1 = [];
let containingView = window;
if (!child) for (; containingView.frameElement; containingView = containingView.parent) owners$1.push(watchFrame(containingView.frameElement, publish$1));
function frameVisibility() {
	if (child) return { visible: admitted };
	if (owners$1.length) return { visible: owners$1.every((owner) => owner.shown()) };
	return null;
}
function onFrameVisibility(callback) {
	observers.add(callback);
	return () => observers.delete(callback);
}
function readSampleVisibility() {
	const bridge = child;
	if (!bridge) return null;
	return new Promise((resolve, reject) => {
		const id = ++readingId;
		readings$1.set(id, {
			resolve,
			reject
		});
		bridge.send({
			type: "visibility-read",
			detail: { id }
		});
	});
}
function publish$1() {
	const visibility = frameVisibility();
	for (const callback of observers) callback(visibility);
}
if (child) child.receive(({ type, detail }) => {
	if (type === "visibility-reading") {
		const reading = readings$1.get(detail.id);
		readings$1.delete(detail.id);
		if ("error" in detail) reading?.reject(Object.assign(new Error(detail.error.message), { stack: void 0 }, detail.error));
		else reading?.resolve(detail);
		return;
	}
	if (type !== "visibility") return;
	admitted = detail.visible;
	publish$1();
});
addEventListener("pagehide", (event) => {
	if (!event.persisted) for (const owner of owners$1) owner.stop();
});

//#endregion
//#region runtime/rendering.js
const ROUNDS = 8;
let queued = /* @__PURE__ */ new Map();
let running = null;
let afterPaint = /* @__PURE__ */ new Map();
let lastId = 0;
let frame = 0;
let heard = false;
let quiet = false;
let checking = false;
let preparations = 0;
const preparationObservers = /* @__PURE__ */ new Set();
function observePreparations(observer) {
	preparationObservers.add(observer);
	return () => preparationObservers.delete(observer);
}
function holdRendering() {
	preparations++;
	const serial = ++begun;
	pending.add(serial);
	unsettle();
	const identity = Object.freeze({});
	const observers = [...preparationObservers];
	for (const observer of observers) observer("begin", identity);
	let released = false;
	return (phase = "settle") => {
		if (released) return;
		released = true;
		preparations--;
		pending.delete(serial);
		if (updateChecking) heard = true;
		unsettle();
		for (const observer of observers) observer(phase, identity);
	};
}
function request(into, callback) {
	const id = ++lastId;
	into.set(id, enqueueWork(callback));
	if (!running && !frame) frame = requestAnimationFrame(pass);
	unsettle();
	return id;
}
const nextRender = (callback) => request(queued, callback);
const nextFrame = (callback) => request(running ? afterPaint : queued, callback);
const nextAnimation = (callback) => requestAnimationFrame(callback);
const cancelAnimation = (id) => cancelAnimationFrame(id);
function cancelRender(id) {
	if (id == null) return;
	for (const queue of [
		queued,
		afterPaint,
		running
	]) {
		const job = queue?.get(id);
		if (!job) continue;
		queue?.delete(id);
		cancelWork(job);
		return;
	}
}
async function pass(time) {
	frame = 0;
	for (let round = 0; queued.size && round < ROUNDS; round++) {
		running = queued;
		queued = /* @__PURE__ */ new Map();
		for (const [id, job] of running) {
			running.delete(id);
			try {
				runWork(job, time);
			} catch (error) {
				reportError(error);
			}
			await null;
		}
	}
	running = null;
	for (const entry of afterPaint) queued.set(...entry);
	afterPaint = /* @__PURE__ */ new Map();
	if (queued.size) frame = requestAnimationFrame(pass);
}
const owedThisScript = /* @__PURE__ */ new Map();
function settleScript() {
	for (const [callback, job] of owedThisScript) {
		owedThisScript.delete(callback);
		try {
			runWork(job);
		} catch (error) {
			reportError(error);
		}
	}
}
function afterScript(callback) {
	if (!owedThisScript.size) queueMicrotask(settleScript);
	if (!owedThisScript.has(callback)) owedThisScript.set(callback, enqueueWork(callback));
}
let deliveringSizes = 0;
function sizeObserver(callback, { counted = true } = {}) {
	const pending = /* @__PURE__ */ new Map();
	let installation = null;
	const observer = new ResizeObserver((entries, observer) => {
		if (counted) {
			heard = true;
			unsettle();
		}
		deliveringSizes++;
		try {
			callback(entries, observer);
		} finally {
			deliveringSizes--;
		}
	});
	const observe = observer.observe.bind(observer);
	const unobserve = observer.unobserve.bind(observer);
	const disconnect = observer.disconnect.bind(observer);
	const install = () => {
		installation = null;
		for (const [target, options] of pending) observe(target, options);
		pending.clear();
	};
	const retireInstallation = () => {
		if (pending.size || installation === null) return;
		(counted ? cancelRender : cancelAnimation)(installation);
		installation = null;
	};
	observer.observe = (target, options) => {
		if (!deliveringSizes) {
			pending.delete(target);
			retireInstallation();
			return observe(target, options);
		}
		pending.set(target, options);
		if (installation === null) installation = (counted ? nextRender : nextAnimation)(install);
	};
	observer.unobserve = (target) => {
		pending.delete(target);
		retireInstallation();
		unobserve(target);
	};
	observer.disconnect = () => {
		pending.clear();
		retireInstallation();
		disconnect();
	};
	return observer;
}
const renderingState = () => {
	const visible = rendered();
	return {
		updatesSettled: quiet || !visible,
		preparationsSettled: preparations === 0 || !visible
	};
};
const rendered = () => !document.hidden && frameVisibility()?.visible !== false;
function unsettle() {
	quiet = false;
	if (checking) return;
	checking = true;
	requestAnimationFrame(afterUpdate);
}
let updateChecking = false;
const afterUpdate = () => {
	updateChecking = true;
	setTimeout(check);
};
function check() {
	updateChecking = false;
	if (queued.size || heard) {
		heard = false;
		requestAnimationFrame(afterUpdate);
		return;
	}
	checking = false;
	quiet = true;
	const waiting = settling;
	settling = [];
	for (const waiter of waiting) if ([...pending].some((serial) => serial > waiter.since)) settling.push(waiter);
	else waiter.settled();
}
let settling = [];
let begun = 0;
const pending = /* @__PURE__ */ new Set();
const owed = () => {};
function afterSettling(settled) {
	settling.push({
		settled,
		since: begun
	});
	nextFrame(owed);
}
onFrameVisibility((visibility) => {
	if (visibility?.visible) unsettle();
});
unsettle();

//#endregion
//#region runtime/inputs.js
const inputs = Reflect.get(window, Symbol.for("leaf.inputs"));

//#endregion
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
var y$1 = 0;
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
	return x$1(function() {
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
			})(this), this.v = t, this.i++, y$1++, h++;
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
	f.call(this, void 0, i), this.x = t, this.s = void 0, this.g = y$1 - 1, this.f = 4;
}
v.prototype = new f();
v.prototype.h = function() {
	if (this.f &= -3, 1 & this.f) return !1;
	if ((36 & this.f) == 32 || (this.f &= -5, this.g === y$1)) return !0;
	if (this.g = y$1, this.f |= 1, this.i > 0 && !U(this)) return this.f &= -2, !0;
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
function x$1(t, i) {
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
			this._$Oo = x$1((() => {
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
//#region runtime/shadow-tree.js
const isShadowRoot = (node) => node != null && node.nodeType === node.DOCUMENT_FRAGMENT_NODE && "host" in node;
const isNode = (node) => typeof node === "object" && node !== null && "nodeType" in node && typeof node.nodeType === "number";
const isElement = (node) => isNode(node) && node.nodeType === node.ELEMENT_NODE;
const isText = (node) => node != null && node.nodeType === node.TEXT_NODE;
function isHTML(node, tag) {
	return isElement(node) && node.namespaceURI === "http://www.w3.org/1999/xhtml" && (tag === void 0 || node.localName === tag);
}
const isSlottable = (node) => isElement(node) || isText(node);
const shadowHost = (root) => isShadowRoot(root) ? root.host : null;
const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
const isStyledElement = (node) => node.namespaceURI === "http://www.w3.org/1999/xhtml" || node.namespaceURI === "http://www.w3.org/2000/svg" || node.namespaceURI === "http://www.w3.org/1998/Math/MathML";
function closestAcross(node, selector) {
	let el = isElement(node) ? node : upFrom(node);
	while (el) {
		const hit = el.closest(selector);
		if (hit) return hit;
		el = shadowHost(el.getRootNode());
	}
	return null;
}
const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
const renderedParent = (node) => (isSlottable(node) ? node.assignedSlot : null) ?? upFrom(node);
const composedParentNode = (node) => node.parentNode ?? shadowHost(node);
const renderedParentNode = (node) => (isSlottable(node) ? node.assignedSlot : null) ?? composedParentNode(node);
const under = (node, root) => {
	for (let at = node; at; at = composedParentNode(at)) if (at === root) return true;
	return false;
};
const renderedUnder = (node, root) => {
	for (let at = node; at; at = renderedParentNode(at)) if (at === root) return true;
	return false;
};
const overIn = (el, selector, frame) => {
	const near = el.closest(selector);
	return near && (!frame || under(near, frame)) ? near : null;
};
const SAID = "[data-lf-said]";
const UI_MARKS = `.lf-ui, ${SAID}`;
const uiInside = (el, within) => {
	const near = el && overIn(el, ".lf-ui, [data-lf-said]", within);
	return !!near && !near.matches("[data-lf-said]");
};
const inUi = (node) => uiInside(isElement(node) ? node : node?.parentElement, null);
const renderedChain = (node) => {
	const chain = [];
	for (let at = node; at; at = renderedParent(at)) chain.push(at);
	return chain.reverse();
};
function renderedOrder(a, b) {
	if (a === b) return 0;
	const left = renderedChain(a);
	const right = renderedChain(b);
	let index = 0;
	while (index < left.length && index < right.length && left[index] === right[index]) index += 1;
	const first = left[index];
	const second = right[index];
	if (!first || !second) return left.length - right.length;
	return first.compareDocumentPosition(second) & first.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}
const byRenderedOrder = (items, placeOfItem) => {
	const placed = [];
	const unplaced = [];
	for (const item of items) {
		const place = placeOfItem(item);
		if (place) placed.push({
			item,
			place
		});
		else unplaced.push(item);
	}
	return [...placed.sort((a, b) => renderedOrder(a.place, b.place)).map(({ item }) => item), ...unplaced];
};
const nativeLayerKind = (node) => {
	if (!isElement(node) || !node.isConnected) return null;
	if (node.matches("dialog:modal")) return "modal";
	return node.matches(":popover-open") ? "popover" : null;
};
const isNativeLayer = (node) => nativeLayerKind(node) !== null;
function nativeLayerHolding(node) {
	for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
	return null;
}
function excludedByInert(node) {
	for (let owner = node; owner; owner = renderedParent(owner)) {
		if (!isElement(owner)) continue;
		if (isHTML(owner) && owner.inert) return true;
		if (nativeLayerKind(owner) === "modal") break;
	}
	return false;
}

//#endregion
//#region runtime/keeps.js
const keeps = (node, name, value) => {
	const next = value == null ? null : String(value);
	if (!node || node.getAttribute(name) === next) return;
	if (next === null) node.removeAttribute(name);
	else node.setAttribute(name, next);
};
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
function inlineStyle(element) {
	if (isStyledElement(element)) return element.style;
	throw new TypeError("This element has no native inline style");
}

//#endregion
//#region runtime/control-selectors.js
const TEXT_FIELD = inputs.textField;
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
const TEXT_BOX = inputs.textBox;
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
function restorePointer(point) {
	if (x !== -1 || y !== -1 || !Number.isFinite(point?.x) || !Number.isFinite(point?.y)) return;
	x = point.x;
	y = point.y;
}
const eventSource = (event) => event.composedPath().find((node) => isNode(node)) ?? null;

//#endregion
//#region runtime/focus.js
function* renderedElements(node) {
	const children = isHTML(node, "slot") ? node.assignedElements({ flatten: true }) : (isElement(node) && node.shadowRoot || node).children;
	for (const child of children) {
		yield child;
		const tabIndex = child.getAttribute("tabindex");
		if (child.shadowRoot && tabIndex !== null && parseInt(tabIndex) < 0) continue;
		yield* renderedElements(child);
	}
}
const SEQUENTIAL = `${TAB_STOP}, iframe, audio[controls], video[controls]`;
const tabStops = (root) => [...renderedElements(root)].filter((node) => node.matches(SEQUENTIAL) && "tabIndex" in node && typeof node.tabIndex === "number" && node.tabIndex >= 0 && !node.shadowRoot?.delegatesFocus && !node.matches(":disabled") && !(isHTML(node) && node.inert) && node.checkVisibility({ visibilityProperty: true }));
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
		...!pressLed() && { focusVisible: true }
	};
	placed(cause, () => {
		nativeFocusTarget(destination).focus(options);
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
const landedOn = (node) => node === document.body ? node.matches(":focus") : activeIn(node.getRootNode()) === node || Boolean(node.shadowRoot?.activeElement);
const lendable = (node) => drawn$1(node) && !node.matches(TAB_STOP);
const lent = /* @__PURE__ */ new WeakSet();
const wearsLentStop = (element) => lent.has(element);
function whenLeft(element, leave) {
	const blur = () => {
		if (activeIn(element.getRootNode()) === element) return;
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
	destination.setAttribute("tabindex", "-1");
	nativeFocusTarget(destination).focus(options);
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
const holdsCaret = (node) => isHTML(node) && (node.matches(TEXT_BOX) || isHTML(node, "input") && CARETED.has(node.type));
function readCaret(node) {
	if (!node || !holdsCaret(node)) return null;
	const { selectionStart, selectionEnd, selectionDirection } = node;
	if (selectionStart === null || selectionEnd === null || selectionDirection === null) return null;
	return [
		selectionStart,
		selectionEnd,
		selectionDirection
	];
}
const deepFocus = (at = document.activeElement) => {
	while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
	return at;
};
const focusRoot = (root) => root.nodeType === Node.DOCUMENT_NODE || root.nodeType === Node.DOCUMENT_FRAGMENT_NODE && "host" in root;
const activeIn = (root) => focusRoot(root) ? root.activeElement : null;
function hasNativeFocus(element) {
	return "focus" in element && typeof element.focus === "function" && "blur" in element && typeof element.blur === "function" && "tabIndex" in element && typeof element.tabIndex === "number";
}
function nativeFocusTarget(element) {
	if (!hasNativeFocus(element)) throw new TypeError(`Element ${element.localName} has no native focus capability`);
	return element;
}
function blurFocused() {
	const active = deepFocus();
	if (active) nativeFocusTarget(active).blur();
}
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
		if (!drawn$1(published?.deref())) return;
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
	return focusRoot(root) && root.nodeType === Node.DOCUMENT_FRAGMENT_NODE && root.getSelection?.() || getSelection();
};
function currentLocationNodes() {
	const at = focused();
	const selection = getSelection();
	return [
		at && at !== document.body ? at : null,
		selection?.focusNode ?? null,
		selection?.anchorNode ?? null
	].filter((node) => node !== null);
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
	const was = {
		placing,
		restoring
	};
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
		placing = was.placing;
		restoring = was.restoring;
	}
}
let pressedPath = null;
const pressedOn = (node) => pressedPath !== null && pressedPath.some((ref) => {
	const at = ref.deref();
	return at === node || isHTML(at, "label") && at.control === node;
});
const pressLed = () => pressedPath !== null;
let stepping = null;
const leftClosedLayer = (left) => {
	const layer = isElement(left) ? left.closest("dialog, [popover]") : null;
	return layer !== null && !(isHTML(layer, "dialog") && layer.open || isNativeLayer(layer));
};
const cause = (node, left = null) => placing ?? (leftClosedLayer(left) ? "return" : pressedOn(node) ? "press" : stepping ? "step" : "move");
const read = /* @__PURE__ */ new WeakSet();
function readFocusEvent(event) {
	if (!("relatedTarget" in event)) return;
	if (read.has(event)) return;
	read.add(event);
	if (closing$1) return;
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
	for (let at = node; at; at = renderedParent(at)) {
		const root = at.getRootNode();
		if (focusRoot(root)) watchCurrentLocationIn(root);
	}
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
	const left = eventSource(event);
	if (!isElement(left)) return;
	lastLocation = new WeakRef(left);
	if (restoring) return;
	const departure = readings;
	setTimeout(() => {
		if (readings !== departure) return;
		const at = document.activeElement;
		if (at !== null && at !== document.body) return;
		if (heldByLabel()) return;
		if (!drawn$1(left)) return publish(null, "drop");
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
	const input = {
		stepping,
		pressedPath
	};
	[stepping, pressedPath] = [step, pressed];
	try {
		publish(at, cause(at));
	} finally {
		stepping = input.stepping;
		pressedPath = input.pressedPath;
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
const inputCount = () => inputs.count;
const onUserInput = (read) => inputs.observe(read);
let keyCarets = null;
onUserInput((event) => {
	if (event.type !== "keydown") return;
	const carets = /* @__PURE__ */ new Map();
	for (const node of event.composedPath()) {
		const caret = isElement(node) && readCaret(node);
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
	if (event.isTrusted && event.button === 0) placeInput = focused()?.contains(eventSource(event)) ? "focus" : "pointer";
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
function pressRecords() {
	const records = /* @__PURE__ */ new WeakMap();
	return {
		keep(event, value) {
			if (press?.pointerId === event.pointerId && !press.released) records.set(press, value);
			return value;
		},
		kept: () => (press && records.get(press)) ?? null
	};
}
const pressHolds = (event) => press !== null && press.pointerId === event.pointerId && (event.type !== "pointermove" || !press.released);
function overPress(ended) {
	if (press !== ended) return;
	press = null;
	for (const over of ended.overs) over();
}
const overSoon = (ended) => setTimeout(() => overPress(ended));
const claimReleaseClick = () => {
	if (press) press.clickClaimed = true;
};
document.addEventListener("click", (event) => {
	if (!press?.clickClaimed || !event.isTrusted || pressIsKeyboardActivation(event)) return;
	press.clickClaimed = false;
	event.preventDefault();
	event.stopImmediatePropagation();
}, { capture: true });
for (const type of ["click", "auxclick"]) addEventListener(type, (event) => {
	if (press?.released && event.isTrusted && !pressIsKeyboardActivation(event)) overSoon(press);
}, {
	capture: true,
	passive: true
});
onUserInput((event) => {
	if (press?.released && event.type !== "pointerdown") overSoon(press);
});
const onPressAway = (away, dismiss) => onPress((start, from) => start.button === 0 && away(from) ? (end, completed) => {
	const path = end.composedPath();
	if (completed && away(path)) dismiss(path, from);
} : null);
addEventListener("pointerdown", (event) => {
	if (!event.isPrimary) return;
	if (press) {
		const before = press;
		endPress(event, false);
		overPress(before);
	}
	const path = event.composedPath();
	const begun = {
		pointerId: event.pointerId,
		path,
		ends: [],
		overs: [],
		released: false,
		clickClaimed: false
	};
	press = begun;
	for (const read of pressReaders) {
		const end = read(event, path);
		if (end) begun.ends.push(end);
	}
	if (event.button !== 0 || labelPress) return;
	const label = path.find((node) => isHTML(node, "label") && node.control !== null);
	const held = label && deepFocus();
	if (!label || !held || held === document.body) return;
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
	const ended = press;
	if (!ended.released) {
		ended.released = true;
		for (const end of ended.ends) {
			const over = end(event, completed);
			if (over) ended.overs.push(over);
		}
	}
	if (!completed) overSoon(ended);
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
const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event) ?? null;
addEventListener("keydown", (event) => {
	placeInput = "focus";
	const recovering = labelPress;
	if (!recovering || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
	const active = deepFocus();
	finishLabelPress();
	const { held } = recovering;
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
		const step = event instanceof KeyboardEvent && sequential(event) ? event : null;
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
	if (!isElement(node) || !node.matches(":focus, [data-lf-focus]")) return node;
	for (let box = renderedParent(node); isElement(box); box = renderedParent(box)) if (getComputedStyle(box).getPropertyValue("--lf-wears-ring") === "1") return box;
	return node;
}
const drawn$1 = (node) => node?.isConnected && !excludedByInert(node) && node.checkVisibility({ visibilityProperty: true });
const dropped = () => {
	const at = deepFocus();
	if (at && at !== document.body) return null;
	const node = lastLocation?.deref();
	return node && !drawn$1(node) ? node : null;
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
					let group = byKey.get(at);
					if (!group) {
						group = [];
						byKey.set(at, group);
					}
					group.push(each);
				}
			}
			return byKey.get(value) ?? [];
		};
		const matching = (root) => {
			if (root.matches(like) && drawn$1(root)) return root;
			const assigned = isHTML(root, "slot") ? root.assignedElements({ flatten: true }) : [];
			for (const child of assigned.length ? assigned : root.children) {
				const found = matching(child);
				if (found) return found;
			}
			return null;
		};
		const find = (value) => {
			const found = keyed(value).filter(drawn$1);
			return found.find((each) => each.matches(like)) ?? found.map(matching).find(Boolean) ?? found[0] ?? null;
		};
		const neighbour = (value) => () => {
			const place = find(value);
			if (!place || !drawn$1(place)) return null;
			focusDestination(place, "return");
			return landedOn(place);
		};
		return restore(() => find(same), ...rest.map(neighbour), ...standIns);
	};
}
const heldIn = (scope) => {
	const held = heldByLabel();
	if (held) return renderedUnder(held, scope) ? held : null;
	const currentLocation = deepFocus(activeIn(scope.getRootNode()) ?? scope.ownerDocument.activeElement);
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
let closing$1 = 0;
let deferredLanding = null;
let landingLayer = false;
function layerLanding(land) {
	return (...args) => {
		if (!landingLayer) throw new Error("A layer's landing runs only as the layer closes");
		return land(...args);
	};
}
function closeLayer(close, land = null) {
	closing$1 += 1;
	let deferred = null;
	const landingAround = landingLayer;
	landingLayer = false;
	try {
		close();
	} finally {
		landingLayer = landingAround;
		closing$1 -= 1;
		if (!closing$1) [deferred, deferredLanding] = [deferredLanding, null];
	}
	if (closing$1) {
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
const isCompletion = (value) => value !== null && typeof value === "object" && "then" in value && typeof value.then === "function";
function holdOn(held) {
	const caret = readCaret(held);
	const began = placements;
	return (...standIns) => {
		if (placements !== began) return false;
		for (const standIn of [held, ...standIns]) {
			if (placements !== began) return false;
			const place = typeof standIn === "function" ? standIn() : standIn;
			if (isCompletion(place)) return place.then((destination) => {
				if (!isElement(destination) || !drawn$1(destination) || deepFocus() !== destination) return false;
				return land$1(() => {
					focusDestination(destination, "return", { caret });
					return landedOn(destination);
				});
			});
			if (place === true) return true;
			if (!isElement(place) || !drawn$1(place)) continue;
			if (place === held && deepFocus() === held) return true;
			if (land$1(() => {
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
const land$1 = (landing) => {
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
function letGo(from = focused()) {
	letGoes++;
	const block = readingBlock(from);
	if (!block?.isConnected) releaseFocus();
	else {
		focusDestination(block, "move");
		block.blur();
	}
	if (from && from !== document.body) for (const read of letGoReaders) read(from);
}
function handBack(...destinations) {
	const places = destinations.flatMap((node) => node && node !== document.body ? [node] : []);
	const landed = () => {
		const at = placements;
		return places.some((node) => {
			if (placements !== at) return true;
			if (!drawn$1(node)) return false;
			focusDestination(node, "return");
			return landedOn(node);
		});
	};
	if (landed()) return;
	if (!places.some((node) => node.isConnected)) {
		letGo();
		return;
	}
	const yielded = !drawn$1(deepFocus());
	if (yielded) releaseFocus();
	const began = placements;
	const pendingInput = inputCount();
	nextRender(() => {
		if (inputCount() !== pendingInput || placements !== began || yielded && deepFocus() !== document.body || landed()) return;
		letGo();
	});
}

//#endregion
//#region runtime/exception.js
const UNREADABLE = "Could not read the error";
function readException(read, unreadable) {
	try {
		return read();
	} catch {
		return unreadable;
	}
}
function exceptionFields(reason) {
	if (reason === null || typeof reason !== "object" && typeof reason !== "function") return {
		name: void 0,
		message: String(reason),
		stack: void 0,
		cause: void 0,
		hasMessage: false
	};
	const name = "name" in reason ? reason.name : void 0;
	const message = "message" in reason ? reason.message : void 0;
	const stack = "stack" in reason ? reason.stack : void 0;
	const cause = "cause" in reason ? reason.cause : void 0;
	return {
		name: typeof name === "string" ? name : void 0,
		message: typeof message === "string" ? message : String(reason),
		stack: typeof stack === "string" ? stack : void 0,
		cause,
		hasMessage: typeof message === "string"
	};
}
function describeFailure(reason) {
	return readException(() => {
		const fields = exceptionFields(reason);
		const message = fields.message || fields.name || "Error";
		return reason instanceof AggregateError && reason.errors.length ? `${message}: ${reason.errors.map(describeFailure).join("; ")}` : message;
	}, UNREADABLE);
}
function exceptionRecord(reason) {
	return readException(() => {
		const fields = exceptionFields(reason);
		return {
			name: fields.name ?? "Error",
			message: fields.message,
			stack: fields.stack
		};
	}, {
		name: "Error",
		message: UNREADABLE,
		stack: void 0
	});
}
function exceptionError(reason) {
	return readException(() => reason instanceof Error ? reason : Object.assign(Object.create(Error.prototype), exceptionRecord(reason)), Object.assign(Object.create(Error.prototype), { message: UNREADABLE }));
}
function exceptionText(reason, context = "") {
	return readException(() => {
		const fields = exceptionFields(reason);
		const message = fields.message;
		const text = !fields.hasMessage ? message : `${fields.name || "Error"}: ${message}`;
		const stack = fields.stack;
		let evidence = !stack ? text : stack.includes(text) ? stack : `${text}
${stack}`;
		if (reason instanceof AggregateError) evidence += reason.errors.map((error) => `
${exceptionText(error)}`).join("");
		if (fields.cause !== void 0) evidence += `
Caused by: ${exceptionText(fields.cause)}`;
		if (!context) return evidence;
		return `${context}: ${reason instanceof Error ? describeFailure(reason) : message}${!fields.hasMessage ? "" : `
${evidence}`}`;
	}, context ? `${context}: ${UNREADABLE}` : UNREADABLE);
}

//#endregion
//#region runtime/page-paint.js
const RUNTIME_PAINT_ATTRIBUTE = Object.freeze({
	external: "data-lf-external",
	viewMember: "data-lf-view",
	obligation: "data-lf-obligation",
	done: "data-lf-done",
	restated: "data-lf-restated",
	retired: "data-lf-retired",
	settlement: "data-lf-state",
	applied: "data-lf-applied",
	reading: "data-lf-reading",
	dataVersion: "data-lf-data-version",
	source: "data-lf-source",
	sourceRevision: "data-lf-source-revision",
	userOverride: "data-lf-user-override",
	presented: "data-lf-presented",
	reported: "data-lf-reported",
	upgraded: "data-lf-upgraded",
	scrolls: "data-lf-scrolls",
	moreBefore: "data-lf-more-before",
	moreAfter: "data-lf-more-after",
	scrollDirection: "data-lf-scroll-direction",
	moreBelow: "data-lf-more-below",
	goto: "data-lf-go-to-active",
	traffic: "data-lf-traffic",
	player: "data-lf-player"
});
const PAGE_PAINT_ATTRIBUTE = Object.freeze({
	class: "class",
	viewMembers: "data-lf-view-members",
	...RUNTIME_PAINT_ATTRIBUTE,
	mediaWidth: "data-lf-media-width",
	mediaHeight: "data-lf-media-height",
	quiet: "data-lf-quiet"
});
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const pageUpgraded = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);

//#endregion
//#region runtime/arrivals.js
const watches$1 = /* @__PURE__ */ new Set();
const stages$1 = /* @__PURE__ */ new WeakSet();
const stageRefs = /* @__PURE__ */ new Set();
const owners = /* @__PURE__ */ new WeakMap();
let offerOwner;
function watchOwner(owner, lifecycle) {
	let connected = false;
	const subscriptions = owners.get(owner) ?? /* @__PURE__ */ new Set();
	owners.set(owner, subscriptions);
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
	let disconnect = () => {};
	return watchOwner(owner, {
		connect() {
			const controller = new AbortController();
			let cleanup;
			disconnect = () => {
				controller.abort();
				cleanup?.();
			};
			cleanup = start(controller.signal);
		},
		disconnect() {
			disconnect();
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
const isStage = (root) => stages$1.has(root);
const stands = (el) => {
	const root = el.getRootNode();
	return root === document ? document.body.contains(el) : isStage(root) && root.host.isConnected;
};
function* matching(node, selector) {
	if (!isElement(node)) return;
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
	const beside = (node) => isElement(node) && (arrived.has(node) || node.matches(selector)) ? [node] : [];
	const read = (records) => {
		const offered = /* @__PURE__ */ new Set();
		for (const record of records) {
			if (record.type === "attributes") {
				if (isElement(record.target)) offered.add(record.target);
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
	if (stages$1.has(stage)) return;
	stages$1.add(stage);
	stageRefs.add(new WeakRef(stage));
	for (const watch of watches$1) enroll(watch, stage);
	stage.addEventListener("scroll", heardIn(stage), SCROLL);
}
const scrollListeners = /* @__PURE__ */ new Set();
const SCROLL = {
	capture: true,
	passive: true
};
function announceScroll(box) {
	for (const listener of scrollListeners) listener(box);
}
function setScroll(box, options) {
	const { scrollTop, scrollLeft } = box;
	const { behavior = "instant" } = options;
	box.scrollTo({
		...options,
		behavior
	});
	if (behavior === "instant" && (box.scrollTop !== scrollTop || box.scrollLeft !== scrollLeft)) announceScroll(box);
}
const heardIn = (stage) => (event) => {
	const target = event.target;
	if (target === document) {
		if (stage === document) announceScroll(document.scrollingElement);
	} else if (isElement(target) && target.getRootNode() === stage) announceScroll(target);
};
document.addEventListener("scroll", heardIn(document), SCROLL);
function watchScrolls(listener) {
	scrollListeners.add(listener);
	return () => scrollListeners.delete(listener);
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
//#region runtime/dom-move.js
let focusOwner = null;
const installMoveFocus = (owner) => {
	focusOwner = owner;
};
function move(parent, node, before = null) {
	if (node.parentNode === parent && (before === node || node.nextSibling === before)) return node;
	if (parent.isConnected) focusOwner?.watch(parent.getRootNode());
	if (parent.moveBefore && node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })) parent.moveBefore(node, before);
	else {
		const restore = isElement(node) ? focusOwner?.hold(node) : null;
		parent.insertBefore(node, before);
		restore?.();
	}
	return node;
}
window.lfMove = move;

//#endregion
//#region runtime/version-signal.js
const tick = (version) => {
	version.value = version.peek() + 1;
};

//#endregion
//#region runtime/control-faces.js
const ACTION_FACES = {
	symbol: "lf-icon-action",
	word: "lf-btn",
	commit: "lf-btn primary",
	mark: "lf-mark-action",
	inline: "lf-inline-action",
	row: "lf-row"
};
function actionClass(role, className = "") {
	const face = ACTION_FACES[role];
	if (!face) throw new TypeError(`A control's role is one of ${Object.keys(ACTION_FACES).join(", ")}, not ${role}`);
	return className ? `${face} ${className}` : face;
}

//#endregion
//#region runtime/icon-paths.js
const SEND = "<path d=\"M8 13V3M4 7l4-4 4 4\"/>";
const ICONS = {
	activity: "<circle cx=\"8\" cy=\"8\" r=\"3\" fill=\"currentColor\" stroke=\"none\"/>",
	add: "<path d=\"M8 3v10M3 8h10\"/>",
	change: "<path d=\"M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13\"/>",
	check: "<path d=\"m3 8.25 3.15 3.15L13 4.75\"/>",
	checked: "<circle cx=\"8\" cy=\"8\" r=\"5.5\"/><path d=\"m5.6 8.15 1.7 1.7 3.1-3.3\"/>",
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
	locate: "<circle cx=\"8\" cy=\"8\" r=\"4\"/><path d=\"M8 1.75v2.5M8 11.75v2.5M1.75 8h2.5M11.75 8h2.5\"/><circle cx=\"8\" cy=\"8\" r=\"1\" fill=\"currentColor\" stroke=\"none\"/>",
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
	undo: "<path d=\"M5.5 2.75 2.75 5.5l2.75 2.75M3 5.5h6.25a3.5 3.5 0 0 1 0 7H6.5\"/>",
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
const ACTIONS = {
	accept: {
		name: "Accept",
		icon: "check"
	},
	add: {
		name: "Add",
		icon: "add"
	},
	arrange: {
		name: "Arrange",
		icon: "arrange"
	},
	back: {
		name: "Back",
		icon: "previous"
	},
	cancel: {
		name: "Cancel",
		icon: "cross"
	},
	close: {
		name: "Close",
		icon: "cross"
	},
	collapse: {
		name: "Collapse",
		icon: "collapse"
	},
	comment: {
		name: "Comment",
		icon: "comment"
	},
	copy: {
		name: "Copy",
		icon: "copy"
	},
	"copy-link": {
		name: "Copy link",
		icon: "link"
	},
	dictate: {
		name: "Dictate",
		icon: "microphone"
	},
	discard: {
		name: "Discard",
		icon: "undo"
	},
	done: {
		name: "Done",
		icon: "checked"
	},
	edit: {
		name: "Edit",
		icon: "edit"
	},
	expand: {
		name: "Expand",
		icon: "expand"
	},
	find: {
		name: "Find",
		icon: "search"
	},
	"collapse-all": {
		name: "Collapse all",
		icon: "fold"
	},
	"expand-all": {
		name: "Expand all",
		icon: "unfold"
	},
	fit: {
		name: "Fit",
		icon: "fit"
	},
	minimize: {
		name: "Minimize",
		icon: "subtract"
	},
	more: {
		name: "More options",
		icon: "more"
	},
	next: {
		name: "Next",
		icon: "next"
	},
	"next-match": {
		name: "Next match",
		icon: "down"
	},
	"on-me": {
		name: "On me",
		icon: "inbox"
	},
	pause: {
		name: "Pause",
		icon: "pause"
	},
	play: {
		name: "Play",
		icon: "play"
	},
	previous: {
		name: "Previous",
		icon: "previous"
	},
	"previous-match": {
		name: "Previous match",
		icon: "up"
	},
	react: {
		name: "Add reaction",
		icon: "reaction"
	},
	remove: {
		name: "Remove",
		icon: "cross"
	},
	reject: {
		name: "Reject",
		icon: "cross"
	},
	reopen: {
		name: "Reopen",
		icon: "check"
	},
	reset: {
		name: "Reset",
		icon: "retry"
	},
	resolve: {
		name: "Resolve",
		icon: "check"
	},
	retry: {
		name: "Retry",
		icon: "retry"
	},
	save: {
		name: "Save",
		icon: "save"
	},
	send: {
		name: "Send",
		icon: "send"
	},
	show: {
		name: "Show",
		icon: "locate"
	},
	start: {
		name: "Start",
		icon: "start"
	},
	suggest: {
		name: "Suggest",
		icon: "edit"
	},
	undo: {
		name: "Undo",
		icon: "undo"
	},
	"zoom-in": {
		name: "Zoom in",
		icon: "add"
	},
	"zoom-out": {
		name: "Zoom out",
		icon: "subtract"
	}
};
const namedAction$1 = (action) => {
	const named = ACTIONS[action];
	if (!named) throw new TypeError(`Unknown Leaf action: ${action}`);
	return named;
};
const actionIcon = (action) => namedAction$1(action).icon;
const actionName = (action) => namedAction$1(action).name;
const actionElement = (action, className) => iconElement(actionIcon(action), className);
const SYMBOLIC = /* @__PURE__ */ new Set(["symbol", "mark"]);
function actionFace(role, label, action) {
	if (!SYMBOLIC.has(role)) {
		if (action !== void 0) throw new TypeError(`A ${role} says its label and shows no action's symbol`);
		return {
			label,
			action: void 0
		};
	}
	if (action === void 0) throw new TypeError(`A ${role} names the action it shows`);
	const name = actionName(action);
	return {
		label: label ?? name,
		action
	};
}
function showAction(control, action, className = "lf-action-icon") {
	const icon = actionIcon(action);
	const drawn = control.querySelector(":scope > svg[data-lf-icon]");
	if (drawn?.getAttribute("data-lf-icon") === icon) return;
	const symbol = iconElement(icon, className);
	if (drawn) drawn.replaceWith(symbol);
	else control.prepend(symbol);
}
const drawAction = (node, role, action) => showAction(node, action, role === "mark" ? "lf-mark-icon" : "lf-action-icon");
function actionOffers(base) {
	const titled = (title) => title === void 0 ? void 0 : { title };
	return {
		offerAction(role, className, label, { title, action } = {}) {
			const face = actionFace(role, label, action);
			const node = base.offerAction(role, className, face.label, titled(title));
			if (face.action !== void 0) drawAction(node, role, face.action);
			return node;
		},
		offerActionElement(node, role, className, label, { title, action } = {}) {
			const face = actionFace(role, label, action);
			base.offerActionElement(node, role, className, face.label, titled(title));
			if (face.action !== void 0) drawAction(node, role, face.action);
			return node;
		}
	};
}

//#endregion
//#region runtime/role-button-press.js
const ROLE_BUTTON_OFFER = "[role=\"button\"][data-lf-offer=\"button\"]:not(button)";
const offerPressed = (ev) => {
	const target = ev.composedPath()[0];
	return target instanceof HTMLElement && target.matches("[role=\"button\"][data-lf-offer=\"button\"]:not(button)") && target.getAttribute("aria-disabled") !== "true" && !(ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) ? target : null;
};
let spaceOn = null;
addEventListener("keydown", (ev) => {
	const offer = offerPressed(ev);
	if (!offer || ev.defaultPrevented || ev.isComposing) return;
	if (ev.key === "Enter") {
		if (!ev.repeat) offer.click();
	} else if (ev.key === " ") {
		ev.preventDefault();
		spaceOn = offer;
	}
});
addEventListener("keyup", (ev) => {
	if (ev.key !== " ") return;
	const offer = spaceOn;
	spaceOn = null;
	if (offer && offer === offerPressed(ev) && !ev.defaultPrevented) offer.click();
});

//#endregion
//#region runtime/element-markers.js
const offerElement = (node, cls, pressable = false) => {
	if (node instanceof HTMLButtonElement && !node.hasAttribute("type")) keeps(node, "type", "button");
	const face = node.localName.includes("-") ? "" : " lf-ui-face";
	keeps(node, "class", `${cls ? `${cls} ` : ""}lf-ui${face}`);
	keeps(node, "data-lf-gen", "1");
	keeps(node, "data-lf-offer", pressable ? node.localName : node instanceof HTMLButtonElement || node.localName === "summary" || node instanceof HTMLInputElement && ["checkbox", "radio"].includes(node.type) ? node instanceof HTMLInputElement || node instanceof HTMLButtonElement ? node.type : node.localName : "");
	return node;
};
const generatedElement = (node, { says } = {}) => {
	if (typeof says !== "boolean" && says !== "echo") throw new TypeError("Say whether these words are the page speaking: true, false, or \"echo\" for a copy of words it says elsewhere");
	keeps(node, "data-lf-gen", "1");
	node.toggleAttribute("data-lf-said", says === true);
	node.toggleAttribute("data-lf-echo", says === "echo");
	return node;
};
function offer(tag, cls, label, inputType, pressable = false) {
	const node = document.createElement(tag);
	if (inputType !== void 0) {
		if (tag !== "input") throw new TypeError("only an input offer can declare an input type");
		node.setAttribute("type", inputType);
	}
	offerElement(node, cls, pressable);
	if (label !== void 0) node.textContent = label;
	return node;
}
const roleElement = (node, role, cls, label, { title = label } = {}) => {
	offerElement(node, actionClass(role, cls));
	if (label !== void 0 && (role === "symbol" || role === "mark")) {
		keeps(node, "aria-label", label);
		keeps(node, "title", title);
	}
	return node;
};
const buildAction = (role, cls, label, options) => {
	const node = roleElement(document.createElement("button"), role, cls, label, options);
	if (label !== void 0 && role !== "symbol" && role !== "mark") node.textContent = label;
	return node;
};
const selectableOfferElement = (node, role, cls, face) => {
	keeps(node, "role", role);
	keeps(node, "class", [
		face && actionClass(face),
		cls,
		"lf-ui lf-ui-face"
	].filter(Boolean).join(" "));
	keeps(node, "data-lf-gen", "1");
	keeps(node, "data-lf-offer", role);
};
const selectableOffer = (role, cls, label, face) => {
	const node = document.createElement("span");
	selectableOfferElement(node, role, cls, face);
	node.tabIndex = 0;
	if (label !== void 0) node.textContent = label;
	return node;
};
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
const { offerAction, offerActionElement: offeredActionElement } = actionOffers({
	offerAction: buildAction,
	offerActionElement: roleElement
});
const offeredAction = elementDirective("offeredAction", offeredActionElement);
const selectableOffered = elementDirective("selectableOffered", selectableOfferElement);
const generated = elementDirective("generated", generatedElement);

//#endregion
//#region runtime/control-labels.js
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
function relabel(node, label, options = {}) {
	generatedElement(node, options);
	keepsText(node, label);
}

//#endregion
//#region runtime/syntax-languages.js
const syntaxLanguages = {
	"bash": () => import("/vendor/syntax/bash.js"),
	"css": () => import("/vendor/syntax/css.js"),
	"diff": () => import("/vendor/syntax/diff.js"),
	"go": () => import("/vendor/syntax/go.js"),
	"html": () => import("/vendor/syntax/html.js"),
	"java": () => import("/vendor/syntax/java.js"),
	"javascript": () => import("/vendor/syntax/javascript.js"),
	"json": () => import("/vendor/syntax/json.js"),
	"markdown": () => import("/vendor/syntax/markdown.js"),
	"python": () => import("/vendor/syntax/python.js"),
	"rust": () => import("/vendor/syntax/rust.js"),
	"sql": () => import("/vendor/syntax/sql.js"),
	"toml": () => import("/vendor/syntax/toml.js"),
	"typescript": () => import("/vendor/syntax/typescript.js"),
	"yaml": () => import("/vendor/syntax/yaml.js")
};
const syntaxLanguageNames = {
	"shellscript": "bash",
	"bash": "bash",
	"sh": "bash",
	"shell": "bash",
	"zsh": "bash",
	"css": "css",
	"diff": "diff",
	"go": "go",
	"html": "html",
	"java": "java",
	"javascript": "javascript",
	"js": "javascript",
	"cjs": "javascript",
	"mjs": "javascript",
	"json": "json",
	"markdown": "markdown",
	"md": "markdown",
	"python": "python",
	"py": "python",
	"rust": "rust",
	"rs": "rust",
	"sql": "sql",
	"toml": "toml",
	"typescript": "typescript",
	"ts": "typescript",
	"cts": "typescript",
	"mts": "typescript",
	"yaml": "yaml",
	"yml": "yaml"
};
const syntaxLanguagePaths = {
	"bash": "bash",
	"cjs": "javascript",
	"css": "css",
	"go": "go",
	"htm": "html",
	"html": "html",
	"java": "java",
	"js": "javascript",
	"json": "json",
	"jsx": "javascript",
	"markdown": "markdown",
	"md": "markdown",
	"mjs": "javascript",
	"py": "python",
	"rs": "rust",
	"sh": "bash",
	"sql": "sql",
	"toml": "toml",
	"ts": "typescript",
	"tsx": "typescript",
	"yaml": "yaml",
	"yml": "yaml"
};

//#endregion
//#region runtime/language-paths.js
let paths = syntaxLanguagePaths;
const installLanguagePaths = (declarations) => {
	paths = declarations;
};
const langForPath = (path) => {
	const filename = path.slice(path.lastIndexOf("/") + 1);
	const dot = filename.lastIndexOf(".");
	return dot < 0 ? void 0 : paths[filename.slice(dot + 1).toLowerCase()];
};

//#endregion
//#region runtime/control-keys.js
const PRESS = ["Enter", " "];
const rowArrows = (node) => node.matches(":dir(rtl)") ? ["ArrowRight", "ArrowLeft"] : ["ArrowLeft", "ArrowRight"];
const DISCLOSE = (el) => {
	const disclosure = disclosureAt(el);
	if (!disclosure) return [
		...PRESS,
		"ArrowLeft",
		"ArrowRight"
	];
	const { element, open } = disclosure;
	const [back, ahead] = rowArrows(element);
	return inChrome(element) ? PRESS : [...PRESS, open ? back : ahead];
};
const DISCLOSURE_SELECTOR = "details > summary, :is(button, [role=\"button\"])[aria-expanded]";
function disclosureAt(el) {
	if (!el?.matches("details > summary, :is(button, [role=\"button\"])[aria-expanded]")) return null;
	return {
		element: el,
		open: el.matches("details > summary") ? el.matches("details[open] > summary") : el.getAttribute("aria-expanded") === "true"
	};
}

//#endregion
//#region runtime/widget-upgrade.js
const initialized = /* @__PURE__ */ new WeakSet();
function once(el) {
	if (initialized.has(el)) return false;
	initialized.add(el);
	if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
	return true;
}
const dataBody = (el) => {
	const body = el.querySelector(":scope > pre");
	if (!body) throw new Error(`<${el.localName}> has no data body`);
	return body.textContent;
};
const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();
const PENDING_TASK = "pending-task";
var PendingTaskEvent = class extends Event {
	constructor(complete) {
		super(PENDING_TASK, {
			bubbles: true,
			composed: true
		});
		this.complete = complete;
	}
};
const LAYOUT = "lf-layout";
const layoutChanged = (el) => {
	el.dispatchEvent(new CustomEvent(LAYOUT, {
		bubbles: true,
		composed: true
	}));
};
const COMMANDS = "lf-commands";
const CHANGED = Symbol("element whose commands changed");
const REFUSED$1 = Symbol("why Leaf refused the declaration");
function commandsChanged(el) {
	const event = Object.assign(new Event(COMMANDS, {
		bubbles: true,
		composed: true
	}), { [CHANGED]: el });
	(el.isConnected ? el : window).dispatchEvent(event);
	if (event[REFUSED$1]) throw event[REFUSED$1];
}
const ANNOUNCE = "lf-announce";
const announce = (words) => window.dispatchEvent(new CustomEvent(ANNOUNCE, { detail: words }));
const commandsChangedOn = (event) => event[CHANGED];
const refuseCommands = (event, error) => {
	event[REFUSED$1] = error;
};
function failSoft(el, err, source) {
	reportFailure(el, err);
	showFailure(el, `<${widgetOf(el).localName}> failed: ${describeFailure(err)}`, source);
}
function reportFailure(el, err) {
	const event = Object.assign(new ErrorEvent("error", {
		error: exceptionError(err),
		message: describeFailure(err),
		bubbles: true,
		composed: true
	}), { [FAILURE]: {
		element: el,
		reason: err
	} });
	(el.isConnected ? el : window).dispatchEvent(event);
}
const FAILURE = Symbol("failure");
function failureOf(event) {
	if (event[FAILURE]) return event[FAILURE];
	const [origin] = event.composedPath();
	return origin instanceof Element ? {
		element: origin,
		reason: event.error
	} : null;
}
function failureContext(el) {
	const owner = widgetOf(el);
	return `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`;
}
function failSoftUnreported(el, err) {
	showFailure(el, `<${widgetOf(el).localName}> failed: ${describeFailure(err)}`);
}
const widgetOf = (el) => {
	let owner = el;
	while (owner.parentElement && !owner.localName.includes("-")) owner = owner.parentElement;
	return owner.localName.includes("-") ? owner : el;
};
const placers = /* @__PURE__ */ new WeakMap();
const placesFailure = (el, place) => placers.set(el, place);
const stages = /* @__PURE__ */ new WeakMap();
const stagesFailure = (host, place) => stages.set(host, place);
function showFailure(el, text, source) {
	const box = document.createElement("div");
	box.className = "lf-error";
	box.textContent = text;
	if (source) {
		const pre = document.createElement("pre");
		pre.textContent = source;
		box.append(pre);
	}
	if (placers.get(el)?.(box) || stages.get(el)?.(box)) return;
	const part = el._$litPart$;
	if (!part) {
		el.replaceChildren(box);
		return;
	}
	el.replaceChildren(part.startNode);
	(part._$AI ?? part._$setValue).call(part, box);
}

//#endregion
//#region runtime/keyboard/layer-stack.js
let styleChrome = null;
function installLayerStyleIntegration(style) {
	styleChrome = style;
}
let entries = [];
const watchedRoots = /* @__PURE__ */ new WeakSet();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;
function prune() {
	entries = entries.filter((entry) => entry.active());
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
		for (const layer of nativeLayers().toReversed()) if (layer.kind === "modal" && renderedUnder(layer.root, entry.root)) closeNativeLayer(layer.root);
	}
	if (entry?.kind === "popover" && entry.fromNowhere && !document.documentElement.inert && canPlaceFocus() && renderedUnder(focused(), entry.root)) releaseFocus();
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
		} else {
			if (source && !isHTML(source)) throw new TypeError("A popover source must be an HTML element");
			layer.showPopover(source ? { source } : void 0);
		}
	} finally {
		if (withholdFocus) layer.inert = false;
	}
}
const modalHomes = /* @__PURE__ */ new WeakMap();
function seatModal(dialog, source) {
	let place = modalHomes.get(dialog);
	if (!place) {
		const parent = dialog.parentNode;
		if (!parent) throw new Error("A modal dialog needs a connected home");
		place = {
			home: parent,
			chrome: Boolean(dialog.closest(".lf-chrome")),
			scope: null
		};
		modalHomes.set(dialog, place);
		const home = place;
		const restore = () => {
			if (dialog.parentNode !== home.home) move(home.home, dialog);
			home.scope?.remove();
		};
		dialog.addEventListener("close", () => {
			if (!dialog.open) restore();
		});
		watchOwner(dialog, { disconnect() {
			if (dialog.parentNode === home.home) return;
			closeNativeLayer(dialog);
			restore();
		} });
	}
	const holder = nativeLayerHolding(source);
	let seat = place.home;
	if (holder && nativeLayerKind(holder) === "popover") {
		if (renderedUnder(holder, place.home)) seat = holder;
		else if (place.chrome) {
			if (!place.scope) {
				place.scope = document.createElement("div");
				place.scope.className = "lf-chrome";
			}
			const root = holder.getRootNode();
			if (root instanceof ShadowRoot) styleChrome?.(root);
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
	if (!(event.target instanceof HTMLElement) || !event.target.matches("[popover], dialog")) return;
	for (const listener of changeListeners) listener(event);
};
function watchLayers(root) {
	if (watchedRoots.has(root)) return;
	watchedRoots.add(root);
	const opened = (event) => {
		if (event.newState === "open" && event.target instanceof HTMLElement && event.target.matches("[popover], dialog")) pushNativeLayer(event.target, event.source);
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
//#region runtime/icons.js
function iconTemplate(icon, className = "lf-margin-entry-icon") {
	return html`<svg
    viewBox="0 0 16 16"
    focusable="false"
    aria-hidden="true"
    class=${className}
    data-lf-icon=${icon}
  >
    ${unsafeSVG(iconMarkup(icon))}
  </svg>`;
}
const actionTemplate = (action, className) => iconTemplate(actionIcon(action), className);

//#endregion
//#region runtime/dom-children.js
var SourcePairs = class extends WeakMap {
	constructor() {
		super();
	}
	get(source) {
		return super.get(source);
	}
	set(source, live) {
		return super.set(source, live);
	}
	require(source) {
		const live = this.get(source);
		if (!live) throw new Error("The authored source has no paired native node");
		return live;
	}
	pair(source, live) {
		if (source instanceof Element && live instanceof Element) return this.set(source, live);
		if (source instanceof CharacterData && live instanceof CharacterData && source.nodeType === live.nodeType) return this.set(source, live);
		throw new Error("An authored source and its live node must have the same native kind");
	}
};
function setChildren(parent, nodes) {
	setChildLists([[parent, nodes]]);
}
function setChildLists(lists) {
	for (const [parent, nodes] of lists) orderChildren(parent, nodes);
	for (const [parent, nodes] of lists) {
		const keep = new Set(nodes);
		for (const child of [...parent.childNodes]) if (!keep.has(child)) child.remove();
	}
}
function orderChildren(parent, nodes) {
	const owned = new Set(nodes);
	order(parent, nodes, (node) => !owned.has(node));
}
function setRenderedChildren(parent, nodes) {
	const after = document.createDocumentFragment();
	after.append(...nodes);
	patchChildren(parent, parent, after, {
		pairs: selfPairs(parent),
		arrive: (node) => node,
		sameValue: (held, wanted) => held === wanted,
		touched: () => {},
		declared: () => false,
		body: () => null,
		same: (held, wanted) => held.isEqualNode(wanted),
		generated: () => false,
		contains: (target, owner) => Boolean(owner?.contains(target)),
		reaches: () => false
	});
}
function selfPairs(parent) {
	const pairs = new SourcePairs();
	for (const node of sourceNodes(parent)) pairs.pair(node, node);
	return pairs;
}
function order(parent, nodes, passed = () => false) {
	const list = [...nodes];
	const stay = staying(parent, list);
	let cursor = parent.firstChild;
	for (const node of list) {
		while (cursor && passed(cursor)) cursor = cursor.nextSibling;
		if (node === cursor) cursor = cursor.nextSibling;
		else if (stay.has(node)) cursor = node.nextSibling;
		else move(parent, node, cursor);
	}
}
function staying(parent, nodes) {
	const places = new Map([...parent.childNodes].map((node, at) => [node, at + 1]));
	const size = places.size;
	const best = new Array(size + 1);
	let last = null;
	for (const node of nodes) {
		const place = places.get(node);
		if (!place) continue;
		let before = null;
		for (let i = place - 1; i > 0; i -= i & -i) {
			const candidate = best[i];
			if (candidate && (!before || candidate.weight >= before.weight)) before = candidate;
		}
		const weight = (node.nodeType === Node.ELEMENT_NODE ? nodes.length + 1 : 1) + (before?.weight ?? 0);
		const chain = {
			node,
			weight,
			previous: before
		};
		for (let i = place; i <= size; i += i & -i) {
			const held = best[i];
			if (!held || weight >= held.weight) best[i] = chain;
		}
		if (!last || weight >= last.weight) last = chain;
	}
	const stay = /* @__PURE__ */ new Set();
	for (let chain = last; chain; chain = chain.previous) stay.add(chain.node);
	return stay;
}
function patchTree(before, after, rules) {
	const live = rules.pairs.require(before);
	patchAttributes(live, before, after, rules);
	patchChildren(holder(live, rules), tree(before), tree(after), rules);
}
function patchRetains(before, after, target, rules) {
	if (!target?.isConnected) return false;
	if (!sourceOwns(before, target, rules)) return true;
	return retainedWithin(before, after, target, rules);
}
function sourceOwns(source, target, rules) {
	const owns = (node) => rules.contains(target, rules.pairs.get(node));
	if (owns(source)) return true;
	for (const node of sourceNodes(source)) if (owns(node)) return true;
	return false;
}
function retainedWithin(before, after, target, rules) {
	const live = rules.pairs.get(before);
	if (!live || !sourceOwns(before, target, rules)) return false;
	if (rules.same(before, after)) return true;
	if (live === target) return false;
	if (before.attributes.length !== after.attributes.length || [...before.attributes].some(({ name, value }) => {
		const attribute = after.getAttributeNode(name);
		return !attribute || !rules.sameValue(value, attribute.value);
	})) return false;
	const children = [...tree(before).childNodes];
	const arriving = [...tree(after).childNodes];
	const forward = matchNodes(children, arriving);
	const matches = new SourcePairs();
	for (const wanted of arriving) {
		const held = forward.get(wanted);
		if (held) matches.pair(held, wanted);
	}
	for (const held of children) {
		if (!(held instanceof Element)) continue;
		const node = rules.pairs.get(held);
		if (!node || !sourceOwns(held, target, rules)) continue;
		const wanted = matches.get(held);
		if (!wanted) return false;
		if (!(atomic(held, wanted, node, rules) ? rules.same(held, wanted) : retainedWithin(held, wanted, target, rules))) return false;
	}
	return true;
}
const tree = (node) => node instanceof HTMLTemplateElement ? node.content : node;
const holder = (live, rules) => rules.body(live) ?? tree(live);
function patchAttributes(live, before, after, rules) {
	let changed = false;
	for (const { name, value } of [...before.attributes]) {
		if (after.hasAttribute(name)) continue;
		if (name === "class") live.classList.remove(...tokens(value));
		else live.removeAttribute(name);
		changed = true;
	}
	for (const { name, value } of after.attributes) {
		const held = before.getAttribute(name);
		if (held !== null && rules.sameValue(held, value)) continue;
		if (name === "class") {
			live.classList.remove(...tokens(held ?? ""));
			live.classList.add(...tokens(value));
		} else live.setAttribute(name, value);
		changed = true;
	}
	if (changed) rules.touched(live);
}
const tokens = (value) => value.split(/\s+/).filter(Boolean);
function writeText(node, next) {
	const held = node.data;
	if (held === next) return;
	let prefix = 0;
	while (prefix < held.length && prefix < next.length && held[prefix] === next[prefix]) prefix += 1;
	let suffix = 0;
	while (suffix < held.length - prefix && suffix < next.length - prefix && held[held.length - suffix - 1] === next[next.length - suffix - 1]) suffix += 1;
	node.replaceData(prefix, held.length - prefix - suffix, next.slice(prefix, next.length - suffix));
}
function evict(before, live, rules) {
	live.parentNode?.removeChild(live);
	for (const inner of sourceNodes(before)) {
		const stray = rules.pairs.get(inner);
		if (!stray?.parentNode || live.contains(stray)) continue;
		stray.parentNode.removeChild(stray);
	}
}
function* sourceNodes(node) {
	for (const child of tree(node).childNodes) {
		yield child;
		yield* sourceNodes(child);
	}
}
function patchChildren(liveParent, beforeParent, afterParent, rules) {
	const held = [...beforeParent.childNodes];
	const wanted = [...afterParent.childNodes];
	const matches = matchNodes(held, wanted);
	const matched = new Set(wanted.map((node) => matches.get(node)));
	for (const node of held) if (!matched.has(node)) evict(node, rules.pairs.require(node), rules);
	const placed = [];
	for (const node of wanted) {
		const pair = patchPair(node, matches, rules.pairs);
		if (!pair || !pair.live.parentNode) {
			placed.push(rules.arrive(node, liveParent));
			continue;
		}
		const { live } = pair;
		if (pair.kind === "data") {
			writeText(pair.live, pair.after.data);
			rules.pairs.set(pair.after, pair.live);
		} else {
			const { before, after } = pair;
			if (!atomic(before, after, pair.live, rules)) patchTree(before, after, rules);
			else if (!rules.same(before, after)) {
				evict(before, pair.live, rules);
				placed.push(rules.arrive(after, liveParent));
				continue;
			} else pairInterior(before, after, rules);
			rules.pairs.set(after, pair.live);
		}
		if (live.parentNode === liveParent) placed.push(live);
	}
	order(liveParent, placed, rules.generated);
}
function patchPair(after, matches, pairs) {
	if (after instanceof Element) {
		const before = matches.get(after);
		const live = before && pairs.get(before);
		return before && live ? {
			kind: "element",
			before,
			after,
			live
		} : null;
	}
	if (after instanceof CharacterData) {
		const before = matches.get(after);
		const live = before && pairs.get(before);
		return before && live ? {
			kind: "data",
			before,
			after,
			live
		} : null;
	}
	throw new Error("Authored child nodes must be elements or character data");
}
function pairInterior(before, after, rules) {
	const held = [...sourceNodes(before)];
	const wanted = [...sourceNodes(after)];
	if (held.length !== wanted.length) return;
	const originals = held[Symbol.iterator]();
	for (const node of wanted) {
		const original = originals.next().value;
		if (!original) throw new Error("An unchanged source must retain its complete node sequence");
		const live = rules.pairs.get(original);
		if (live) rules.pairs.pair(node, live);
	}
}
const atomic = (before, after, live, rules) => before.matches("style, link[rel~=\"stylesheet\" i]") || rules.declared(before) && !rules.reaches(before, after) || [...tree(before).childNodes].some((node) => rules.pairs.get(node)?.parentNode !== holder(live, rules));
function matchNodes(held, wanted) {
	const matches = new SourcePairs();
	const matched = /* @__PURE__ */ new Set();
	const byId = /* @__PURE__ */ new Map();
	for (const node of held) if (node instanceof Element && node.id && !byId.has(node.id)) byId.set(node.id, node);
	for (const node of wanted) {
		if (!(node instanceof Element) || !node.id) continue;
		const match = byId.get(node.id);
		if (!match || match.localName !== node.localName || matched.has(match)) continue;
		matches.set(node, match);
		matched.add(match);
	}
	alignRest(held.filter((node) => !matched.has(node)), wanted.filter((node) => !matches.has(node)), matches);
	return matches;
}
function diffNode(nodes, index) {
	const node = nodes[index];
	if (!node) throw new Error("A child diff named a source position outside its input");
	return node;
}
const COLLAPSE = /\s+/g;
const signature = (node) => {
	if (node instanceof CharacterData) return `${node.nodeType}:${node.data}`;
	if (!(node instanceof Element)) throw new Error("Authored child nodes must be elements or character data");
	const words = tree(node).textContent ?? "";
	return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};
function alignRest(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	let gapHeld = [];
	let gapWanted = [];
	const closeGap = () => {
		pairInGap(gapHeld, gapWanted, matches);
		gapHeld = [];
		gapWanted = [];
	};
	for (const run of diffArrays(held.map(signature), wanted.map(signature))) {
		const count = run.value.length;
		if (run.added) gapWanted.push(...wanted.slice(wantedAt, wantedAt += count));
		else if (run.removed) gapHeld.push(...held.slice(heldAt, heldAt += count));
		else {
			closeGap();
			for (let at = 0; at < count; at++) matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
			heldAt += count;
			wantedAt += count;
		}
	}
	closeGap();
}
function pairInGap(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
		const count = run.value.length;
		if (run.added) wantedAt += count;
		else if (run.removed) heldAt += count;
		else {
			for (let at = 0; at < count; at++) matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
			heldAt += count;
			wantedAt += count;
		}
	}
}
const interchangeable = (held, wanted) => held.nodeType === wanted.nodeType && (!(held instanceof Element) || wanted instanceof Element && held.localName === wanted.localName && !(held.id && wanted.id));

//#endregion
//#region runtime/shadow-stage.js
let integration$1 = null;
const installStageIntegration = (adopt) => {
	integration$1 = adopt;
};
function adoptShadowStage(root) {
	watchArrivalsIn(root);
	watchLayers(root);
	integration$1?.(root);
	return root;
}
function shadowStage(host, nodes) {
	const root = host.shadowRoot ?? stageFor(host);
	watchArrivalsIn(root);
	watchLayers(root);
	const styles = integration$1?.(root) ?? [];
	setChildren(root, [...styles, ...nodes]);
	for (const child of [...host.childNodes]) child.remove();
	return root;
}
function stageFor(host) {
	stagesFailure(host, (box) => {
		shadowStage(host, [box]);
		return true;
	});
	return host.attachShadow({ mode: "open" });
}

//#endregion
//#region runtime/leaf-element.js
let integration = null;
function installElementIntegration(host) {
	integration = host;
}
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
	#signalError = {};
	#stopReadiness = null;
	signalUpdateFailed(error) {
		this.#signalError.error = error;
	}
	requestUpdate(...args) {
		const wasPending = this.isUpdatePending;
		const result = super.requestUpdate(...args);
		if (this.hasUpdated && this.isUpdatePending && (!wasPending || !this.#updating)) d(() => {
			if (this.#connected && this.#region && !this.#ticket) this.#ticket = this.#claim(this.#region);
		});
		return result;
	}
	whenReady(read) {
		if (!integration || d(read)) return true;
		if (!this.#stopReadiness) this.#stopReadiness = integration.watchPresentation(() => {
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
	#data = null;
	createRenderRoot() {
		if (!integration?.shadows(this)) return this;
		const root = super.createRenderRoot();
		if (!(root instanceof ShadowRoot)) throw new Error("A shadow widget needs a shadow render root");
		return adoptShadowStage(root);
	}
	scheduleUpdate() {
		return this.#scheduled ?? this.#queueUpdate();
	}
	#committed() {
		return super.getUpdateComplete();
	}
	#queueUpdate() {
		if (!this.#descriptor) return super.scheduleUpdate();
		const scheduled = integration?.queueWidgetUpdate(this.#descriptor.id, () => {
			if (this.#scheduled !== scheduled) return;
			this.#scheduled = null;
			return super.scheduleUpdate();
		}, () => this.#committed());
		this.#scheduled = scheduled ?? null;
		return scheduled;
	}
	connectedCallback() {
		if (once(this)) this.#setup();
		super.connectedCallback();
	}
	#setup() {
		this.#descriptor = integration?.widgetDescriptor(this) ?? null;
		if (this.#descriptor) {
			this.#controller = integration?.widgetController(this) ?? null;
			integration?.drawsItself(this, {
				hold: () => this.#hold(),
				refresh: () => this.#refresh()
			});
			this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
		}
		this.#regionName = this.#descriptor ? null : `element:${this.localName}#${this.id}:${++regions}`;
		this.#data = integration?.data(this, () => this.#stage()) ?? null;
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
			this.#data?.initialize();
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
		return this.controller.read().state;
	}
	get controller() {
		if (!this.#controller) throw new Error(`${this.localName} has no authored widget controller`);
		return this.#controller;
	}
	defer() {
		return this.#controller ? this.#controller.defer() : this.#hold();
	}
	#hold() {
		if (this.#held) throw new Error("Widget presentation is already deferred");
		this.#held = true;
		let released = false;
		return () => {
			if (released) return;
			released = true;
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
		this.#drawing = this.#ticket ?? this.#claim(this.#region);
		this.#ticket = null;
		if (!this.#draws()) return false;
		this.#data?.deliver();
		return super.shouldUpdate(changed);
	}
	#draws() {
		return !this.#broken && this.#complete() && !this.#data?.awaitsDelivery();
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
			const boundary = this.#signalError = {};
			super.performUpdate();
			if ("error" in boundary) throw boundary.error;
			this.#settleDrawing();
		} catch (error) {
			if (outer && !this.#drawing) throw error;
			this.#failed(error, this.#drawing);
		} finally {
			this.#drawing = outer;
			this.#updating = updating;
		}
	}
	#settleDrawing() {
		this.#drawing?.resolve(this.updateComplete.then(() => void 0, (error) => {
			reportFailure(this, error);
			throw error;
		}));
	}
	redraw() {
		if (this.#draws()) render(this.render(), this.renderRoot, this.renderOptions);
	}
	updated(changed) {
		super.updated(changed);
		d(() => integration?.paintKeysWithin(this));
	}
	#failed(error, ticket) {
		if (!ticket) return failSoft(this, error);
		reportFailure(this, error);
		ticket.reject(error);
	}
	#claim(region = this.#region) {
		return region?.present((reason) => failSoftUnreported(this, reason)) ?? null;
	}
	#stage() {
		if (this.#ticket || !this.#region) return;
		this.#ticket = this.#claim(this.#region);
	}
	#present({ now = false } = {}) {
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
		const name = this.#descriptor ? `widget:${this.#descriptor.id}:render` : this.#regionName ??= `element:${this.localName}#${this.id}:${++regions}`;
		this.#region = this.#descriptor ? integration?.attachWidgetPresentation(this.#descriptor.id, "render") ?? null : integration?.attachApplicationPresentation(name) ?? null;
		const parentChanged = this.#connectedParent !== this.parentElement;
		this.#connectedParent = this.parentElement;
		this.#leaveData = this.#data?.connect(name) ?? null;
		this.#present();
		if (this.#descriptor) integration?.widgetMounted(this, this.#descriptor, parentChanged);
	}
	#disconnect() {
		this.#connected = false;
		const region = this.#region;
		this.#region = null;
		this.#stopReadiness?.();
		this.#stopReadiness = null;
		this.#leaveData?.();
		this.#leaveData = null;
		this.#ticket = null;
		region?.disconnect();
	}
};

//#endregion
//#region runtime/base-layer.js
const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;

//#endregion
//#region runtime/motion.js
const preference = matchMedia("(prefers-reduced-motion: reduce)");
const active = /* @__PURE__ */ new Set();
const reducedMotion = () => preference.matches;
const scrollBehavior = () => preference.matches ? "instant" : "smooth";
function onMotionPreferenceChange(listener) {
	const changed = (event) => listener(event.matches);
	preference.addEventListener("change", changed);
	return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
	if (event.matches) for (const played of [...active]) played.finish();
});
const motionPlays = () => !reducedMotion() && pagePresented();
const motion = (el, keyframes, ms, pseudoElement = null) => playMotion(el, keyframes, {
	duration: ms,
	pseudoElement
});
function playMotion(el, keyframes, { duration, easing = "ease", delay = 0, pseudoElement = null }) {
	if (!motionPlays()) return null;
	const played = el.animate(keyframes, {
		duration,
		delay,
		pseudoElement,
		easing,
		fill: "both"
	});
	active.add(played);
	played.finished.then(() => queueMicrotask(() => {
		active.delete(played);
		played.cancel();
	}), () => active.delete(played));
	return played;
}
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
const motionTime = (property, on = document.documentElement) => {
	const value = token(property, on);
	return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
const motionEasing = (property, on = document.documentElement) => token(property, on);
const flashDuration = () => motionTime("--lf-motion-flash");
const agentArrivalDuration = () => motionTime("--lf-motion-agent-arrival");
function backgroundFlash(el, ms) {
	return motion(el, [{
		backgroundColor: "var(--hi-tint)",
		offset: 0
	}], ms);
}
const foldDuration = () => motionTime("--lf-motion-fold");
const returnDuration = () => motionTime("--lf-motion-return");
function foldBlock(el, allocation = null) {
	const adjustment = allocation ? allocation.priorSize - allocation.container.getBoundingClientRect().height : 0;
	const native = CSS.supports("block-size", "calc-size(auto, size)");
	const frames = (blockSize) => [{
		blockSize,
		display: "block",
		overflow: "clip",
		opacity: 1
	}, {
		blockSize: "0px",
		minBlockSize: "0px",
		marginBlockStart: "0px",
		marginBlockEnd: "0px",
		paddingBlockStart: "0px",
		paddingBlockEnd: "0px",
		borderBlockStartWidth: "0px",
		borderBlockEndWidth: "0px",
		display: "block",
		overflow: "clip",
		opacity: 0
	}];
	const played = motion(el, frames(native ? `calc-size(auto, size + ${adjustment}px)` : "auto"), foldDuration());
	if (!played || native) return played;
	if (getComputedStyle(el).display === "none") {
		el.style.display = "block";
		const release = () => el.style.removeProperty("display");
		played.finished.then(release, release);
	}
	const size = parseFloat(getComputedStyle(el).blockSize) + adjustment;
	const effect = played.effect;
	if (effect instanceof KeyframeEffect) effect.setKeyframes(frames(`${size}px`));
	return played;
}

//#endregion
//#region runtime/user-intent.js
const passed = /* @__PURE__ */ new WeakMap();
const passOn = (container, target) => passed.set(target, {
	container,
	intent: inputCount()
});
const displaced = (source, at) => {
	if (!(source instanceof Node) || !at) return false;
	const via = passed.get(at);
	const carry = carriedFrom(at);
	return at.contains(source) || via?.intent === inputCount() && via.container.contains(source) || carry?.inputs === inputCount() && (carry.from === source || source.contains(carry.from));
};
function retainUserIntent({ source = focused(), available = () => true, fallback = null, since = inputCount() } = {}) {
	const retained = since;
	let held = source instanceof Node ? new WeakRef(source) : null;
	const current = () => {
		const at = focused();
		const from = held?.deref();
		const withinSource = from === document.body ? at === document.body : from?.contains(at);
		return Boolean(available() && retained === inputCount() && (at === document.body || at === fallback || withinSource || displaced(from, at)));
	};
	current.available = available;
	current.handoff = (move) => {
		if (!available() || retained !== inputCount()) return false;
		const moved = current();
		if (moved) move();
		const at = focused();
		held = at ? new WeakRef(at) : null;
		return moved && current();
	};
	return current;
}
function restrictUserIntent(retained, available) {
	const current = () => available() && retained();
	current.available = () => available() && retained.available();
	current.handoff = (move) => available() && retained.handoff(move);
	return current;
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
//#region runtime/shown-box.js
const skipped = (element) => {
	if (element.checkVisibility({ contentVisibilityAuto: true })) return false;
	if (element.checkVisibility()) return true;
	let child = element;
	let box = renderedParent(element);
	while (box && !box.checkVisibility()) {
		child = box;
		box = renderedParent(box);
	}
	if (!box) return false;
	if (box.localName === "details") return !box.hasAttribute("open") && child.localName !== "summary";
	return getComputedStyle(box).contentVisibility === "hidden";
};
function elementBox(el) {
	const r = el.getBoundingClientRect();
	if (r.width || r.height || skipped(el) || getComputedStyle(el).display !== "contents") return r;
	const contents = document.createRange();
	contents.selectNodeContents(el);
	return contents.getBoundingClientRect();
}
const measurements = /* @__PURE__ */ new WeakMap();
const drawn = (el) => {
	if (skipped(el)) return false;
	const box = elementBox(el);
	return Boolean(box.width || box.height);
};
const unmeasured = sizeObserver((entries) => {
	const taking = [];
	for (const { target } of entries) {
		if (!drawn(target)) continue;
		unmeasured.unobserve(target);
		const take = measurements.get(target);
		if (take) taking.push(take);
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

//#endregion
//#region runtime/geometry.js
const nativeViewport = window.visualViewport;
if (!nativeViewport) throw new Error("Leaf requires an active visual viewport");
const visualViewport = nativeViewport;
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
function shownWindow({ within = null, gap = 0, viewport = "visual", item = null, across = null } = {}) {
	const layout = layoutWindow();
	const { offsetLeft, offsetTop, width, height } = viewport === "visual" ? visualViewport : {
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
		if (!overlapsAcross(box, across ?? {
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
	const s = getComputedStyle(el);
	const axes = clippingAxes(s);
	if (!axes.x && !axes.y) return null;
	const b = el.getBoundingClientRect();
	const scaleX = isHTML(el) && el.offsetWidth ? b.width / el.offsetWidth : 1;
	const scaleY = isHTML(el) && el.offsetHeight ? b.height / el.offsetHeight : 1;
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
	if (!isElement(box) || box.namespaceURI === "http://www.w3.org/2000/svg") return false;
	const style = getComputedStyle(box);
	return scrollport(style.overflowX) && box.scrollWidth > box.clientWidth || scrollport(style.overflowY) && box.scrollHeight > box.clientHeight;
}
const slotHolder = (el, scroller) => {
	let at = el;
	let box = el;
	for (; box && box !== scroller; box = renderedParent(box)) if (box.nodeType === 1 && scrolls(box)) at = renderedParent(box);
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
	let el = node;
	for (; el?.nodeType === 1 && el !== within; el = renderedParent(el)) {
		const style = getComputedStyle(el);
		if (style.position === "sticky" ? sticks(el) : inWindow(el, style)) return el;
	}
	return null;
}
const inWindow = (el, style) => style.position === "fixed" && isHTML(el) && el.offsetParent === null && !style.positionAnchor.startsWith("--");
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
	while (parent && parent !== scroller && getComputedStyle(parent).display === "contents") parent = renderedParent(parent);
	const content = band.top - scroller.scrollTop;
	const holder = parent === scroller ? {
		top: content + padTop,
		bottom: content + scroller.scrollHeight - padBottom
	} : parent && shownBox(parent);
	if (!holder) return false;
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
function shownBox(el) {
	if (el === document.scrollingElement) {
		const { left, top, right, bottom } = layoutWindow(el.ownerDocument);
		return new DOMRect(left, top, right - left, bottom - top);
	}
	return elementBox(el);
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
function seenRect(item, clips, box = placeBox(item)) {
	const shown = clippedPlace(item, clips, box);
	if (!shown) return null;
	const room = shownWindow({
		within: shown,
		item: placeHolder(item)
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
	let at = node;
	for (; at; at = renderedParent(at)) if (at.getAttribute?.("aria-hidden") === "true") return false;
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
	const viewport = visualViewport;
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
	const anchorBand = !scroller ? cut : scroller.scrollTop > 0 ? landingBand(scroller) : shownBand(scroller);
	return anchorBand && anchorBand.top < room.bottom ? {
		top: anchorBand.top,
		bottom: room.bottom
	} : null;
}
function growthIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { top, bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return band !== null && bottom > band.top && top < band.bottom;
}
function growthAfterIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return band !== null && bottom > band.top && bottom < band.bottom;
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
		unlisten?.();
		unlisten = null;
		if (watchPass !== null) cancelRender(watchPass);
		watchPass = null;
	};
}
const startsAt = (item, clips) => {
	const fragments = item.getClientRects();
	return (fragments.length ? [...fragments] : [shownBox(item)]).map((box) => clippedRect(box, item, clips)).find(Boolean);
};
const clippedRect = (box, item, clips, stop) => clipped(box, item, clips, false, true, stop);
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
	const bands = [];
	for (const cut of walk.cuts) {
		const band = cut.band;
		if (!band) return hidden;
		if (cut.box !== root) bands.unshift({
			...cut,
			band
		});
	}
	let shown = cutBy(box, walk.cuts, root, false);
	if (!shown) return {
		plane,
		window: window ?? null,
		bands
	};
	for (const { surface, box: over, level } of aboveSurfaces ? openOccluders(clips) : []) {
		if (!overlaps(shown, over) || under(item, surface) || stackLevel(item) >= level) continue;
		const left = uncovered(shown, over);
		if (!left) return hidden;
		window ??= layoutWindow(item.ownerDocument);
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
	return box !== null && box.bottom >= -height && box.top <= 2 * height && box.right >= -width && box.left <= 2 * width;
}
const clippedContents = (box, holder, clips, stop) => clipped(box, holder, clips, true, true, stop);
function clipped(box, item, clips, held, inWindow = true, stop) {
	const root = item.ownerDocument.scrollingElement;
	const shown = cutBy(box, clipWalk(item, clips, held, stop).cuts, root, inWindow && !stop);
	return stop ? shown : shown && occluded(shown, item, clips);
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
function clipWalk(item, clips, held, stop) {
	let holder = item;
	let escaped = false;
	let containing = null;
	const cuts = [];
	let a = item;
	for (; a && a !== stop; a = renderedParent(a)) {
		let c = clips.get(a);
		if (c === void 0) clips.set(a, c = {
			band: shownBand(a),
			axes: a === a.ownerDocument.scrollingElement ? {
				x: true,
				y: true
			} : clippingAxes(getComputedStyle(a)),
			positioned: isHTML(a) && ["fixed", "absolute"].includes(getComputedStyle(a).position),
			block: isHTML(a) ? a.offsetParent : void 0,
			scrolls: scrollContainer(a)
		});
		if (escaped && a === containing) escaped = false;
		if (!escaped && (held || a !== item) && c.band) {
			const covered = c.band.top + (!stop && c.scrolls ? insetAt(holder, a, ...TOP) : 0);
			const footed = c.band.bottom - (!stop && c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
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
		if (c.scrolls) holder = renderedParent(a);
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
	let at = surface;
	for (; at && isHTML(at); at = at.offsetParent) {
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
const clipsPast = (surfaces) => {
	const clips = /* @__PURE__ */ new Map();
	clips.set(PAST, new Set(surfaces));
	return clips;
};
const clipsPastSurfaces = () => clipsPast(occluders);
function coveredShare(surface, where, landed = null) {
	const holder = placeHolder(where);
	if (!holder || !occluders.has(surface) || !standsNow(surface)) return 0;
	if (under(holder, surface) || under(surface, holder)) return 0;
	if (stackLevel(holder) >= stackLevel(surface)) return 0;
	const box = landed ?? placeBox(where);
	const { left, top, right, bottom } = landed ?? clippedPlace(where, clipsPast([surface]), box) ?? box;
	const over = restingBox(surface);
	const across = Math.max(0, Math.min(right, over.right) - Math.max(left, over.left));
	const room = shownWindow({ viewport: "layout" });
	if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1) return across / (right - left || 1);
	return across * Math.max(0, Math.min(bottom, over.bottom) - Math.max(top, over.top)) / ((right - left) * (bottom - top) || 1);
}
const hides = (surface, where) => coveredShare(surface, where) > .5;
const underOccluder = (where) => [...occluders].some((surface) => hides(surface, where));
const placeHolder = (where) => where instanceof Range ? isElement(where.startContainer) ? where.startContainer : where.startContainer.parentElement : where;
const placeBox = (where) => where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
const clippedPlace = (where, clips, box = placeBox(where)) => {
	if (!(where instanceof Range)) return clippedRect(box, where, clips);
	const holder = placeHolder(where);
	return holder && clippedContents(box, holder, clips);
};
function stackLevel(node) {
	let level = 0;
	let a = node;
	for (; a; a = renderedParent(a)) {
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
		const remaining = uncovered(rect, box);
		if (!remaining) return null;
		rect = remaining;
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
//#region runtime/scrolling.js
const nativeScroller = document.scrollingElement;
if (!(nativeScroller instanceof HTMLElement)) throw new Error("Leaf requires an active HTML document scrollport");
const pageScroller = nativeScroller;
const moving = /* @__PURE__ */ new WeakMap();
const ended = /* @__PURE__ */ new WeakMap();
const scrollSteps = /* @__PURE__ */ new WeakMap();
const layoutMoved = /* @__PURE__ */ new WeakSet();
const watchedLayout = /* @__PURE__ */ new WeakSet();
const extents = /* @__PURE__ */ new WeakMap();
const extentOf = (box) => [
	box.scrollHeight,
	box.clientWidth,
	box.clientHeight
];
const changedExtent = (before, after) => before?.some((value, index) => value !== after[index]);
function watchLayout(box) {
	if (watchedLayout.has(box)) return;
	watchedLayout.add(box);
	extents.set(box, extentOf(box));
	const root = box === pageScroller ? document.documentElement : box;
	const sizes = /* @__PURE__ */ new WeakMap();
	const measure = (node) => skipped(node) ? null : [
		node.clientWidth,
		node.clientHeight,
		node.scrollHeight
	];
	const observer = sizeObserver((entries) => {
		let changed = false;
		for (const { target } of entries) {
			const next = measure(target);
			const before = sizes.get(target);
			sizes.set(target, next);
			if (next && (!before || before.some((value, index) => value !== next[index]))) changed = true;
		}
		if (changed) {
			if (ended.has(box) && box.scrollTop !== ended.get(box)) layoutMoved.add(box);
			else extents.set(box, extentOf(box));
		}
	}, { counted: false });
	const observe = (node) => {
		sizes.set(node, measure(node));
		observer.observe(node);
	};
	observe(root);
	if (box !== pageScroller) {
		for (const child of box.children) observe(child);
		const mutation = new MutationObserver((entries) => {
			for (const entry of entries) {
				for (const node of entry.addedNodes) if (node instanceof Element) observe(node);
				for (const node of entry.removedNodes) if (node instanceof Element) observer.unobserve(node);
			}
		});
		mutation.observe(box, { childList: true });
		watchOwner(box, { disconnect() {
			observer.disconnect();
			mutation.disconnect();
			watchedLayout.delete(box);
		} });
	}
}
watchLayout(pageScroller);
ended.set(pageScroller, pageScroller.scrollTop);
function stopScroll(boxes) {
	const stopped = [...boxes].flatMap((box) => {
		const sequence = moving.get(box);
		return sequence ? [{
			box,
			sequence
		}] : [];
	});
	if (!stopped.length) return null;
	for (const { box } of stopped) setScroll(box, {
		left: box.scrollLeft,
		top: box.scrollTop,
		behavior: "instant"
	});
	return new Promise((resolve) => nextFrame(() => nextFrame(() => {
		for (const { box, sequence } of stopped) if (moving.get(box) === sequence) moving.delete(box);
		resolve(void 0);
	})));
}
let choices = 0;
const chosen = /* @__PURE__ */ new WeakMap();
const kept = /* @__PURE__ */ new WeakMap();
const scrollChoices = () => choices;
const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
const chooseScroll = (box) => chosen.set(box, ++choices);
function startScroll(box) {
	moving.set(box, { glide: true });
	chooseScroll(box);
}
let travel = null;
document.addEventListener("beforematch", () => {
	const mark = travel = {};
	nextFrame(() => nextFrame(() => {
		if (travel === mark) travel = null;
	}));
}, { capture: true });
const eventScroller = (target) => target === document ? pageScroller : target instanceof Element ? target : null;
document.addEventListener("scroll", ({ target }) => {
	const box = eventScroller(target);
	if (!box) return;
	if (skipped(box)) return;
	watchLayout(box);
	scrollSteps.set(box, (scrollSteps.get(box) ?? 0) + 1);
	if (moving.get(box)?.glide) return;
	const sequence = { glide: false };
	moving.set(box, sequence);
	nextFrame(() => nextFrame(() => {
		if (moving.get(box) === sequence) moving.delete(box);
	}));
}, {
	capture: true,
	passive: true
});
function placeKept(...boxes) {
	for (const box of boxes) kept.set(box, box.scrollTop);
}
document.addEventListener("scrollend", ({ target }) => {
	const box = eventScroller(target);
	if (!box) return;
	if (skipped(box)) {
		moving.delete(box);
		scrollSteps.delete(box);
		layoutMoved.delete(box);
		return;
	}
	watchLayout(box);
	const wasMoving = moving.get(box);
	moving.delete(box);
	const extent = extentOf(box);
	const repeated = (scrollSteps.get(box) ?? 0) > 1;
	scrollSteps.delete(box);
	if ((wasMoving?.glide || repeated || travel !== null || ended.get(box) !== box.scrollTop && !layoutMoved.has(box) && !changedExtent(extents.get(box), extent)) && kept.get(box) !== box.scrollTop) chooseScroll(box);
	ended.set(box, box.scrollTop);
	layoutMoved.delete(box);
	extents.set(box, extent);
	kept.delete(box);
}, {
	capture: true,
	passive: true
});
const riding = /* @__PURE__ */ new WeakSet();
const contentRides = (box, rides) => rides ? riding.add(box) : riding.delete(box);
function laidOutHeight(box) {
	let end = 0;
	for (const child of box.children) {
		if (!child.checkVisibility()) continue;
		if (!(child instanceof HTMLElement) || child.offsetParent !== box) return box.scrollHeight;
		end = Math.max(end, child.offsetTop + child.offsetHeight + Number.parseFloat(getComputedStyle(child).marginBottom));
	}
	const padding = Number.parseFloat(getComputedStyle(box).paddingBottom);
	return Math.min(box.scrollHeight, end + padding);
}
const scrollLimit = (box) => Math.max(0, (riding.has(box) ? laidOutHeight(box) : box.scrollHeight) - box.clientHeight);
const SCROLL_SLACK = 2;
const atScrollEnd = (box) => scrollLimit(box) - box.scrollTop <= 2;
const scrollToEnd = (box, behavior = "instant") => {
	if (behavior !== "instant" && !atScrollEnd(box)) startScroll(box);
	setScroll(box, {
		top: scrollLimit(box),
		behavior
	});
};
const aims = /* @__PURE__ */ new WeakMap();
const moveScrollerBy = (box, top, behavior = "instant") => {
	const aim = box.scrollTop + top;
	if (Math.abs(top) >= .5) {
		if (behavior !== "instant" && reachable(box, top)) startScroll(box);
		setScroll(box, {
			top: aim,
			behavior
		});
	}
	if (behavior === "instant" && Math.abs(aim - box.scrollTop) < 1) aims.set(box, {
		aim,
		at: box.scrollTop
	});
	else aims.delete(box);
};
const aimedTop = (box) => {
	const kept = aims.get(box);
	return kept?.at === box.scrollTop ? kept.aim : box.scrollTop;
};
const reachable = (box, top) => Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));

//#endregion
//#region runtime/scroll-containers.js
let lookup = (node) => {
	for (let at = node instanceof Element ? node : node?.parentElement; at; at = renderedParent(at)) if (at === pageScroller || /^(auto|scroll)$/.test(getComputedStyle(at).overflowY)) return at;
	return pageScroller;
};
function installScrollerLookup(read) {
	lookup = read;
}
function* scrollersOf(node) {
	for (let box = lookup(node);; box = lookup(renderedParent(box))) {
		for (let at = node; at !== box; at = renderedParent(at)) if (!at || getComputedStyle(at).position === "fixed") return;
		yield box;
		if (box === pageScroller) return;
		node = box;
	}
}

//#endregion
//#region runtime/element-axes.js
function elementAxes(source) {
	let matrix = new window.DOMMatrix();
	let node = source;
	for (; isElement(node); node = renderedParent(node)) {
		const style = getComputedStyle(node);
		let local = new window.DOMMatrix();
		if (style.rotate !== "none") {
			const split = style.rotate.lastIndexOf(" ");
			const angle = style.rotate.slice(split + 1);
			const parts = style.rotate.slice(0, split + 1).trim().split(" ");
			const degrees = parseFloat(angle) * (angle.endsWith("turn") ? 360 : angle.endsWith("grad") ? .9 : angle.endsWith("rad") ? 180 / Math.PI : 1);
			const axis = parts.length === 3 ? [
				Number(parts[0]),
				Number(parts[1]),
				Number(parts[2])
			] : parts[0] === "x" ? [
				1,
				0,
				0
			] : parts[0] === "y" ? [
				0,
				1,
				0
			] : [
				0,
				0,
				1
			];
			local = local.rotateAxisAngle(...axis, degrees);
		}
		if (style.scale !== "none") {
			const scale = style.scale.split(" ").map(Number);
			local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
		}
		if (style.transform !== "none") local = local.multiply(new window.DOMMatrix(style.transform));
		const zoom = Number(style.zoom);
		local = local.scale(zoom, zoom);
		matrix = local.multiply(matrix);
	}
	return {
		x: {
			x: matrix.a,
			y: matrix.b
		},
		y: {
			x: matrix.c,
			y: matrix.d
		}
	};
}
function scrollAxes(source) {
	return source === source.ownerDocument.scrollingElement ? {
		x: {
			x: 1,
			y: 0
		},
		y: {
			x: 0,
			y: 1
		}
	} : elementAxes(source);
}

//#endregion
//#region runtime/element-frame.js
const nativePositions = /* @__PURE__ */ new WeakMap();
let positionProbe;
function nativePosition(source, position, horizontal, vertical) {
	const key = JSON.stringify([
		position,
		horizontal,
		vertical
	]);
	const prior = nativePositions.get(source);
	if (prior?.key === key) return prior.offset;
	let depth = 0;
	let split = -1;
	for (let at = 0; at < position.length; at++) {
		const character = position[at];
		if (character === "(") depth++;
		if (character === ")") depth--;
		if (character === " " && !depth) {
			split = at;
			break;
		}
	}
	if (split < 0) throw new TypeError(`Computed object-position has no second component: ${position}`);
	const pixels = (value, space) => value.replace(/([-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?)%/gi, (_unit, percent) => `${Number(percent) * space / 100}px`);
	if (!positionProbe) {
		const measure = document.createElement("div");
		measure.className = "lf-ui";
		measure.dataset.lfRuntime = "";
		measure.inert = true;
		measure.style.cssText = "all:initial;position:fixed;visibility:hidden;contain:strict;width:0;height:0;left:0;top:0;pointer-events:none";
		const point = document.createElement("div");
		point.style.cssText = "all:initial;position:absolute;width:0;height:0";
		measure.append(point);
		positionProbe = {
			measure,
			point
		};
	}
	const { measure, point } = positionProbe;
	point.style.left = pixels(position.slice(0, split), horizontal);
	point.style.top = pixels(position.slice(split + 1), vertical);
	document.body.append(measure);
	const resolved = getComputedStyle(point);
	const offset = {
		x: Number.parseFloat(resolved.left),
		y: Number.parseFloat(resolved.top)
	};
	measure.remove();
	nativePositions.set(source, {
		key,
		offset
	});
	return offset;
}
function elementFrame(source) {
	const box = shownBox(source);
	if (!box?.width || !box?.height) return null;
	if (source instanceof window.SVGGraphicsElement) {
		const local = source instanceof window.SVGSVGElement ? source.viewBox.baseVal.width && source.viewBox.baseVal.height ? source.viewBox.baseVal : {
			x: 0,
			y: 0,
			width: Number.parseFloat(getComputedStyle(source).width),
			height: Number.parseFloat(getComputedStyle(source).height)
		} : source.getBBox();
		const screen = source.getScreenCTM();
		if (!screen) return null;
		return {
			box,
			width: local.width,
			height: local.height,
			matrix: new window.DOMMatrix([
				screen.a,
				screen.b,
				screen.c,
				screen.d,
				screen.e,
				screen.f
			])
		};
	}
	const layout = elementBorderFrame(source);
	if (!layout) return null;
	const { width, height, matrix } = layout;
	const style = getComputedStyle(source);
	const native = source instanceof window.HTMLImageElement ? {
		width: source.naturalWidth,
		height: source.naturalHeight
	} : source instanceof window.HTMLCanvasElement ? {
		width: source.width,
		height: source.height
	} : source instanceof window.HTMLVideoElement ? {
		width: source.videoWidth,
		height: source.videoHeight
	} : null;
	if (native) {
		if (!native.width || !native.height) return null;
		const edge = (side) => Number.parseFloat(style[`border${side}Width`]) + Number.parseFloat(style[`padding${side}`]);
		const contentWidth = width - edge("Left") - edge("Right");
		const contentHeight = height - edge("Top") - edge("Bottom");
		let sx = contentWidth / native.width;
		let sy = contentHeight / native.height;
		if (style.objectFit !== "fill") sx = sy = style.objectFit === "cover" ? Math.max(sx, sy) : style.objectFit === "none" ? 1 : Math.min(sx, sy, style.objectFit === "scale-down" ? 1 : Infinity);
		const { x: dx, y: dy } = nativePosition(source, style.objectPosition, contentWidth - native.width * sx, contentHeight - native.height * sy);
		if (![
			sx,
			sy,
			dx,
			dy
		].every(Number.isFinite) || !sx || !sy) return null;
		return {
			box,
			width: native.width,
			height: native.height,
			matrix: matrix.translate(edge("Left") + dx, edge("Top") + dy).scale(sx, sy)
		};
	}
	return {
		box,
		width,
		height,
		matrix
	};
}
function elementBorderFrame(source) {
	const box = shownBox(source);
	if (!box?.width || !box?.height) return null;
	const style = getComputedStyle(source);
	if (style.display === "contents") return {
		box,
		width: box.width,
		height: box.height,
		matrix: new window.DOMMatrix().translate(box.left, box.top)
	};
	const borderSize = (side, edges, fallback) => {
		const size = Number.parseFloat(style[side]);
		if (!Number.isFinite(size)) return fallback;
		return style.boxSizing === "border-box" ? size : size + edges.reduce((sum, edge) => sum + Number.parseFloat(style[`padding${edge}`]) + Number.parseFloat(style[`border${edge}Width`]), 0);
	};
	const width = borderSize("width", ["Left", "Right"], isHTML(source) ? source.offsetWidth : void 0);
	const height = borderSize("height", ["Top", "Bottom"], isHTML(source) ? source.offsetHeight : void 0);
	if (width === void 0 || height === void 0) return null;
	const { x, y } = elementAxes(source);
	const left = box.left - Math.min(0, width * x.x, height * y.x, width * x.x + height * y.x);
	const top = box.top - Math.min(0, width * x.y, height * y.y, width * x.y + height * y.y);
	return {
		box,
		width,
		height,
		matrix: new window.DOMMatrix([
			x.x,
			x.y,
			y.x,
			y.y,
			left,
			top
		])
	};
}
function localScrollBy(source, { x, y }) {
	const axes = scrollAxes(source);
	const horizontal = source.scrollWidth > source.clientWidth;
	const vertical = source.scrollHeight > source.clientHeight;
	const along = (axis) => {
		return [...x && axis.x ? [x / axis.x] : [], ...y && axis.y ? [y / axis.y] : []].reduce((move, amount) => Math.abs(amount) > Math.abs(move) ? amount : move, 0);
	};
	const reach = (offset, current, minimum, maximum) => Math.max(minimum - current, Math.min(maximum - current, offset));
	const horizontalLimit = source.scrollWidth - source.clientWidth;
	const rtl = getComputedStyle(source).direction === "rtl";
	const reachLeft = (offset) => reach(offset, source.scrollLeft, rtl ? -horizontalLimit : 0, rtl ? 0 : horizontalLimit);
	const reachTop = (offset) => reach(offset, source.scrollTop, 0, source.scrollHeight - source.clientHeight);
	if (!horizontal) return {
		left: 0,
		top: vertical ? reachTop(along(axes.y)) : 0
	};
	if (!vertical) return {
		left: reachLeft(along(axes.x)),
		top: 0
	};
	const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
	const left = (x * axes.y.y - y * axes.y.x) / determinant;
	const top = (y * axes.x.x - x * axes.x.y) / determinant;
	const reachableLeft = reachLeft(left);
	const reachableTop = reachTop(top);
	if (reachableLeft !== left && axes.y.y) return {
		left: reachableLeft,
		top: reachTop((y - reachableLeft * axes.x.y) / axes.y.y)
	};
	if (reachableTop !== top && axes.x.x) return {
		left: reachLeft((x - reachableTop * axes.y.x) / axes.x.x),
		top: reachableTop
	};
	return {
		left,
		top
	};
}

//#endregion
//#region runtime/landing-scroll.js
const land = (box, by, behavior) => {
	startScroll(box);
	setScroll(box, {
		top: box.scrollTop + (by.top ?? 0),
		left: box.scrollLeft + (by.left ?? 0),
		behavior
	});
};
function scrollMargin(where, side = "Top") {
	if (!(where instanceof Range)) return Number.parseFloat(getComputedStyle(where).getPropertyValue(`scroll-margin-${side.toLowerCase()}`)) || 0;
	const edges = [where.startContainer.childNodes[where.startOffset], where.endContainer.childNodes[where.endOffset - 1]].filter((edge) => edge instanceof Element);
	return edges.length ? Math.max(...edges.map((edge) => scrollMargin(edge, side))) : 0;
}
function shownFor(where) {
	const ring = ringBox(where);
	if (ring === where) return where;
	const box = placeBox(ring);
	const room = roomAround(ring, where);
	return box.height <= room.height && box.width <= room.width ? ring : where;
}
const destinationBox = (where) => placeBox(shownFor(where));
const holderOf = (where) => placeHolder(shownFor(where));
const readingTop = (holder, box, band) => visibleBand(box, holder)?.top ?? band.top;
function topMargin(where, box, band, holder = holderOf(where)) {
	return Math.max(scrollMargin(where), readingTop(holder, box, band) - band.top);
}
const landingRoom = (where, until) => roomAround(shownFor(where), where, until);
function roomAround(shown, where, until) {
	const holder = placeHolder(shown);
	const regions = /* @__PURE__ */ new Map();
	let previous = null;
	for (const box of scrollersOf(holder)) {
		regions.set(box, previous);
		previous = box;
	}
	let { width, height } = shownWindow();
	for (let box = shown instanceof Range ? holder : renderedParent(shown); box instanceof Element; box = renderedParent(box)) {
		const band = (!until || until === where || renderedUnder(until, box)) && landingBand(box);
		if (band) {
			const axes = box === pageScroller ? {
				x: true,
				y: true
			} : clippingAxes(getComputedStyle(box));
			const inner = regions.get(box);
			const clearance = inner === null ? topMargin(where, box, band, holder) + scrollMargin(until ?? where, "Bottom") : inner ? Math.max(0, readingTop(inner, box, band) - band.top) : 0;
			if (axes.x) width = Math.min(width, band.right - band.left);
			if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
		}
		if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
	}
	return {
		width,
		height
	};
}
function fitsWhole(where) {
	const box = destinationBox(where);
	const room = landingRoom(where);
	return box.height <= room.height && box.width <= room.width;
}
function seesWhole(where, box, out) {
	const seen = seenRect(shownFor(where), /* @__PURE__ */ new Map(), out);
	if (!seen) return false;
	const room = landingRoom(where);
	return (box.height > room.height || seen.top <= out.top && seen.bottom >= out.bottom) && (box.width > room.width || seen.left <= out.left && seen.right >= out.right);
}
function alreadyShown(where) {
	const box = destinationBox(where);
	return seesWhole(where, box, box);
}
function ringShown(where) {
	const box = destinationBox(where);
	const top = scrollMargin(where, "Top");
	const right = scrollMargin(where, "Right");
	const bottom = scrollMargin(where, "Bottom");
	const left = scrollMargin(where, "Left");
	return seesWhole(where, box, new DOMRect(box.left - left, box.top - top, box.width + left + right, box.height + top + bottom));
}
function placementBy(where, block, band, margin) {
	const rect = destinationBox(where);
	const room = band.bottom - band.top;
	const place = block === "start" ? margin : block === "end" ? room - rect.height - scrollMargin(where, "Bottom") : Math.max((room - rect.height) / 2, margin);
	return block === "nearest" ? nearestScrollBy(rect.top - margin, rect.bottom + scrollMargin(where, "Bottom"), band.top, band.bottom) : rect.top - band.top - place;
}
function verticalTravel(box, movement) {
	const scale = scrollAxes(box).y.y;
	const local = scale === 0 ? 0 : reachable(box, movement / scale);
	return {
		local,
		moved: local * scale
	};
}
function readingBandMoves(where, holder, block) {
	const [box, ...around] = scrollersOf(holder);
	if (!box) return {
		moves: [],
		moved: 0
	};
	const band = landingBand(box);
	if (!band) return {
		moves: [],
		moved: 0
	};
	const rect = destinationBox(where);
	const margin = topMargin(where, box, band);
	let { top, bottom } = rect;
	if (block === "start") top -= margin;
	else if (block === "end") {
		top = bottom - 1;
		bottom += scrollMargin(where, "Bottom");
	}
	let { local, moved } = verticalTravel(box, placementBy(where, block, band, margin));
	const moves = [{
		box,
		local,
		moved
	}];
	let inner = box;
	for (const outer of around) {
		top -= moved;
		bottom -= moved;
		const band = landingBand(outer);
		if (!band) break;
		band.top = Math.max(band.top, readingTop(inner, outer, band));
		if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
		({local, moved} = verticalTravel(outer, nearestScrollBy(top, bottom, band.top, band.bottom)));
		moves.push({
			box: outer,
			local,
			moved
		});
		inner = outer;
	}
	return {
		moves,
		moved: moves.reduce((sum, move) => sum + move.moved, 0)
	};
}
function landedBox(where) {
	const rect = destinationBox(where);
	const { moved } = readingBandMoves(where, holderOf(where), "center");
	return new DOMRect(rect.x, rect.y - moved, rect.width, rect.height);
}
function scrollIntoReadingBand(where, holder, block, behavior) {
	for (const { box, local, moved } of readingBandMoves(where, holder, block).moves) if (Math.abs(moved) >= 1) land(box, { top: local }, behavior);
}
function scrollIntoView(where, { alignment, behavior = "auto", block = "start", within = null } = {}) {
	if (!where) return;
	const aligned = alignment ?? where;
	const holder = holderOf(aligned);
	if (!holder) return;
	const targetScroller = within ? null : scrollersOf(holder).next().value;
	let inside = true;
	const start = holderOf(where);
	for (let box = start; box instanceof Element; box = renderedParent(box)) {
		if (box === targetScroller) inside = false;
		const band = landingBand(box);
		if (band) {
			const { left, right } = band;
			const destination = destinationBox(where);
			const byX = nearestScrollBy(destination.left - scrollMargin(where, "Left"), destination.right + scrollMargin(where, "Right"), left, right);
			const byY = inside ? placementBy(where, "nearest", band, topMargin(where, box, band, start)) : 0;
			const by = localScrollBy(box, {
				x: byX,
				y: byY
			});
			if (by.left || by.top) land(box, by, "instant");
		}
		if (box === within || box === pageScroller || getComputedStyle(box).position === "fixed") break;
	}
	if (targetScroller) scrollIntoReadingBand(aligned, holder, block, behavior);
}
onCurrentLocation((node, cause) => {
	if (cause !== "step" || !node) return;
	nextRender(() => {
		if (deepFocus() !== node) return;
		if (!ringShown(node)) scrollIntoView(node, { block: "nearest" });
		let box = node;
		for (; box; box = renderedParent(box)) {
			if (!box.matches("[data-lf-obligation]")) continue;
			if (getComputedStyle(box).outlineStyle === "none") continue;
			if (!ringShown(box)) scrollIntoView(box, { block: "nearest" });
			break;
		}
	});
});

//#endregion
//#region runtime/syntax-tokens.js
let tokenizerReady;
const tokenizer = () => tokenizerReady ??= import("/vendor/syntax.esm.js");
const languagesReady = /* @__PURE__ */ new Map();
function ensureSyntaxLanguage(lang) {
	if (!lang) return tokenizer();
	let ready = languagesReady.get(lang);
	if (!ready) {
		const load = syntaxLanguages[lang];
		if (!load) throw new Error(`no ${lang} grammar — rebuild syntax from registry.json`);
		ready = Promise.all([tokenizer(), load()]).then(async ([shared, grammar]) => {
			await shared.registerLanguage(lang, grammar.default);
			return shared;
		});
		languagesReady.set(lang, ready);
	}
	return ready;
}
async function syntax(source, lang) {
	const tokens = await (await ensureSyntaxLanguage(lang)).tokenize(source, lang);
	if (tokens.map((t) => t.text).join("") !== source) throw new Error(`the ${lang} tokenizer did not return the source unchanged`);
	return tokens;
}
const synNodes = (tokens) => tokens.map(({ text, style }) => {
	if (!Object.keys(style).length) return document.createTextNode(text);
	const span = document.createElement("span");
	span.dataset.lfSyn = "";
	for (const [property, value] of Object.entries(style)) span.style.setProperty(property, value);
	span.textContent = text;
	return span;
});
function tokenLines(tokens) {
	let line = [];
	const lines = [line];
	for (const { text, style } of tokens) text.split("\n").forEach((part, i) => {
		if (i) {
			line = [];
			lines.push(line);
		}
		if (part) line.push({
			text: part,
			style
		});
	});
	return lines;
}

//#endregion
//#region runtime/visual-parts.js
const registrations$1 = /* @__PURE__ */ new WeakMap();
const words = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
function registerVisualParts(source, read, { reveal = null, label = null } = {}) {
	if (registrations$1.has(source)) throw new TypeError("A visual source may register its parts only once");
	registrations$1.set(source, {
		read,
		reveal,
		label
	});
	return { update: () => layoutChanged(source) };
}
function visualPartAdmission(visual, declaration) {
	if (!declaration || typeof declaration !== "object") return null;
	if ("prefixes" in declaration) return (id) => declaration.prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
	return visual.hasAttribute(declaration.parts) ? () => true : null;
}
const revealsVisualParts = (source) => Boolean(registrations$1.get(source)?.reveal);
function revealRegisteredVisualPart(source, id) {
	const reveal = registrations$1.get(source)?.reveal;
	if (reveal) reveal(id);
	return registeredVisualPart(source, id);
}
function visualPartProblems(source, declaration) {
	if (!declaration || typeof declaration !== "object") return [];
	if (!registrations$1.has(source)) return [{ kind: "unregistered" }];
	const parts = registeredVisualParts(source);
	const admission = visualPartAdmission(source, declaration);
	const outside = "prefixes" in declaration && admission ? parts.filter((part) => !admission(part.id)).map((part) => part.id) : [];
	return outside.length ? [{
		kind: "unadmitted-parts",
		parts: outside
	}] : [];
}
function registeredVisualParts(source) {
	const read = registrations$1.get(source)?.read;
	if (!read) return [];
	const seenIds = /* @__PURE__ */ new Set();
	const seenElements = /* @__PURE__ */ new Set();
	const seenSurfaces = /* @__PURE__ */ new Set();
	return [...read()].map((part, index) => {
		const number = index + 1;
		const id = part.id;
		const element = part.element;
		const label = words(part.label);
		const surface = part.surface ?? element;
		if (typeof id !== "string" || !id || /\s/.test(id)) throw new TypeError(`Visual part ${number} has no single-token id`);
		if (!(element instanceof Element) || element === source || !under(element, source)) throw new TypeError(`Visual part ${id} has no descendant Element`);
		if (!label) throw new TypeError(`Visual part ${id} has no label`);
		if (!(surface instanceof Element) || !under(surface, element)) throw new TypeError(`Visual part ${id} has no descendant Element surface`);
		if (seenIds.has(id)) throw new TypeError(`A visual source registered part ${id} twice`);
		if (seenElements.has(element)) throw new TypeError("A visual source registered one element as two parts");
		if (seenSurfaces.has(surface)) throw new TypeError("A visual source registered one surface for two parts");
		seenIds.add(id);
		seenElements.add(element);
		seenSurfaces.add(surface);
		return {
			id,
			element,
			label,
			surface
		};
	});
}
const registeredVisualPart = (source, id) => registeredVisualParts(source).find((part) => part.id === id) ?? null;
const registeredVisualPartLabel = (source, id) => {
	const current = registeredVisualPart(source, id)?.label;
	if (current) return current;
	const label = registrations$1.get(source)?.label?.(id);
	return words(label) || null;
};
function registeredVisualPartAt(source, target, admits = () => true) {
	const byElement = new Map(registeredVisualParts(source).filter(admits).map((part) => [part.element, part]));
	for (let current = target; current && current !== source; current = upFrom(current)) {
		const part = byElement.get(current);
		if (part) return part;
	}
	return null;
}

//#endregion
//#region runtime/held-word.js
const HOLDS_WORD = "lf-holds-word";
const HOLDER = `.${HOLDS_WORD}`;
function holdToRead() {
	let hold = null;
	const holderIn = (event) => {
		for (const node of event.composedPath()) if (isElement(node) && node.matches(HOLDER)) return node;
		return null;
	};
	const read = (held, holder) => {
		if (held.reading === holder) return;
		held.reading?.removeAttribute("data-lf-held-word");
		held.reading = holder;
		holder?.setAttribute("data-lf-held-word", "");
	};
	const under = (held, event) => {
		const holder = holderIn(event);
		return holder?.parentElement === held.parent ? holder : null;
	};
	const end = (event, commit) => {
		if (!hold || hold.pointerId !== event.pointerId) return;
		const holder = commit && plainPress(event) ? under(hold, event) : null;
		read(hold, null);
		hold = null;
		if (!holder) return;
		claimReleaseClick();
		nativeFocusTarget(holder).focus({
			preventScroll: true,
			focusVisible: false
		});
		holder.dispatchEvent(new MouseEvent("click", {
			bubbles: true,
			cancelable: true,
			composed: true,
			detail: 1,
			clientX: event.clientX,
			clientY: event.clientY
		}));
	};
	document.addEventListener("pointerdown", (event) => {
		if (hold) read(hold, null);
		hold = null;
		if (!event.isPrimary || !plainPress(event)) return;
		const holder = holderIn(event);
		if (!holder || holder.matches(":disabled, [aria-disabled='true']")) return;
		const origin = event.composedPath()[0];
		if (isElement(origin) && origin.hasPointerCapture(event.pointerId)) origin.releasePointerCapture(event.pointerId);
		hold = {
			pointerId: event.pointerId,
			parent: holder.parentElement,
			reading: null
		};
		read(hold, holder);
	}, { capture: true });
	document.addEventListener("pointermove", (event) => {
		if (hold?.pointerId === event.pointerId) read(hold, under(hold, event));
	}, { capture: true });
	document.addEventListener("pointerup", (event) => end(event, true), { capture: true });
	document.addEventListener("pointercancel", (event) => end(event, false), { capture: true });
	document.addEventListener("contextmenu", (event) => {
		if (hold) event.preventDefault();
	}, { capture: true });
}

//#endregion
//#region runtime/walk-declaration.js
const WALK = "lf-walk";
let walking = null;
function walkPositionLabel(noun, position, total, qualifier = "") {
	if (!noun && !qualifier) throw new Error("leaf: a walk position needs a noun");
	return [
		noun,
		`${position} of ${total}`,
		qualifier
	].filter(Boolean).join(" ");
}
function listWalkPosition(items, current, { identity = (item) => item, qualifier = "" } = {}) {
	if (!current) return null;
	const target = identity(current);
	const index = items.findIndex((item) => identity(item) === target);
	if (index < 0) return null;
	return {
		target,
		position: index + 1,
		total: items.length,
		qualifier
	};
}
function walkPosition() {
	if (!walking) return null;
	const position = walking.read();
	if (!position || position.target !== walking.target) {
		walking = null;
		return null;
	}
	return {
		kind: walking.key,
		target: position.target,
		position: position.position,
		total: position.total,
		text: walkPositionLabel(walking.noun, position.position, position.total, position.qualifier)
	};
}
function beginWalk(key, noun, read) {
	const position = read();
	if (!position) {
		walking = null;
		return null;
	}
	walkPositionLabel(noun, position.position, position.total, position.qualifier);
	walking = {
		key,
		noun,
		read,
		target: position.target
	};
	const shown = walkPosition();
	window.dispatchEvent(new Event(WALK));
	return shown?.text ?? null;
}

//#endregion
//#region runtime/thread/surface-handles.js
const registrations = /* @__PURE__ */ new Map();
const registrationVersion = Z(0);
function setRegistration(owner, registration) {
	if (registration) registrations.set(owner, registration);
	else registrations.delete(owner);
	tick(registrationVersion);
}
function updateSurface(registration) {
	if (registration.reconcileQueued) return;
	registration.reconcileQueued = true;
	queueMicrotask(() => {
		registration.reconcileQueued = false;
		registration.invalidate();
	});
}
const threadSurface = (owner) => Object.freeze({
	update() {
		const registration = registrations.get(owner);
		if (registration) updateSurface(registration);
	},
	get open() {
		registrationVersion.value;
		return registrations.get(owner)?.handle.open ?? null;
	}
});
function releaseOutlets(node) {
	for (const { outlets, composition } of registrations.values()) {
		const outlet = composition.outlet();
		if (outlet && outlets.has(outlet) && under(outlet, node)) composition.restore();
	}
}

//#endregion
//#region runtime/tab-store.js
const tabStore = window.lfStorage?.tabStore ?? {
	read: () => ({
		available: false,
		value: null
	}),
	get: () => null,
	set: () => false,
	where: (key) => ({
		store: "session",
		key
	}),
	keys: () => []
};

//#endregion
//#region runtime/widget-output.js
const OUTPUT = "lf-output";
const PRODUCER = Symbol("output producer");
const REFUSED = Symbol("output refusal");
function publishOutput(element, output, value) {
	const event = Object.assign(new CustomEvent(OUTPUT, {
		bubbles: true,
		composed: true,
		detail: {
			output,
			value
		}
	}), {
		[PRODUCER]: element,
		[REFUSED]: void 0
	});
	(element.isConnected ? element : window).dispatchEvent(event);
	if (event[REFUSED]) throw event[REFUSED];
}
const outputProducer = (event) => event[PRODUCER];
const refuseOutput = (event, error) => {
	event[REFUSED] = error;
};

//#endregion
//#region runtime/deferred-value.js
const loaders = /* @__PURE__ */ new WeakMap();
function attachDeferredLoader(value, load) {
	loaders.set(value, load);
}
async function loadDeferred(value, key) {
	const load = loaders.get(value);
	if (!load) throw new Error(`loadDeferred(${key}) needs a source value Leaf delivered`);
	return load(key);
}

//#endregion
//#region runtime/canvas.js
function canvas2D(canvas, options) {
	const context = canvas.getContext("2d", options);
	if (!context) throw new Error("The browser could not create a 2D canvas context");
	return context;
}

//#endregion
//#region runtime/time-axis.js
const TICK_SPACING = 84;
const STEPS = [
	1,
	2,
	5
];
function tickStep(pxPerMs) {
	for (let power = 1; power < 1e9; power *= 10) for (const step of STEPS) if (step * power * pxPerMs >= TICK_SPACING) return step * power;
	return 1e9;
}
function tickLabel(time, step) {
	if (time === 0) return "0 s";
	const digits = step >= 1e3 ? 0 : step >= 100 ? 1 : step >= 10 ? 2 : 3;
	return `${(time / 1e3).toFixed(digits)} s`;
}
function axisTicks(from, to, duration, pxPerMs) {
	const step = tickStep(pxPerMs);
	const minor = step / (String(step)[0] === "2" ? 4 : 5);
	const ticks = [];
	for (let time = Math.floor(from / minor) * minor; time <= to; time += minor) {
		const rounded = Math.round(time * 1e3) / 1e3;
		if (rounded < 0 || rounded > duration) continue;
		const major = Math.abs(rounded / step - Math.round(rounded / step)) < 1e-6;
		ticks.push({
			time: rounded,
			major,
			label: major ? tickLabel(rounded, step) : null,
			step
		});
	}
	return ticks;
}
function assignRows(items, start, end) {
	const rows = [];
	const rowOf = /* @__PURE__ */ new Map();
	for (const item of items.toSorted((a, b) => start(a) - start(b))) {
		let row = rows.findIndex((last) => last <= start(item));
		if (row < 0) row = rows.push(-Infinity) - 1;
		rows[row] = end(item);
		rowOf.set(item.id, row);
	}
	return rowOf;
}
let measuring = null;
function textWidth(text, font) {
	measuring ??= canvas2D(document.createElement("canvas"));
	measuring.font = font;
	return measuring.measureText(text).width;
}

//#endregion
export { ANNOUNCE, CARET_KEYS, COMMANDS, DISCLOSE, DISCLOSURE_SELECTOR, HOLDS_WORD, J, LAYOUT, LENT_REACH_STOP, LeafElement, MODIFIER_KEYS, OUTPUT, PAGE_PAINT_ATTRIBUTE, PENDING_TASK, PRESS, PRESSES, PendingTaskEvent, ROLE_BUTTON_OFFER, RUNTIME_PAINT_ATTRIBUTE, SAID, SourcePairs, TAB_STOP, TEXT_BOX, TEXT_FIELD, UI_MARKS, W, WALK, WORKS, Z, actionClass, actionElement, actionIcon, actionName, actionTemplate, afterScript, afterSettling, agentArrivalDuration, aimedTop, alreadyShown, announce, assignRows, atLayoutPrecision, atScrollEnd, attachDeferredLoader, axisTicks, backgroundFlash, beginWalk, bindQueuedWork, blurFocused, bodyText, byRenderedOrder, canPlaceFocus, cancelAnimation, cancelRender, canvas2D, caretAtKey, chosenSince, claimReleaseClick, clamp, clippedContents, clippedPlace, clippedRect, clippingAxes, clipsPastSurfaces, closeLayer, closeNativeLayer, closestAcross, coarsePointer, commandsChanged, commandsChangedOn, composedParentNode, contentRides, controlNavigationKeys, coveredShare, currentLocationIn, currentLocationNodes, currentLocationTouches, d, dataBody, declareOccluder, declareReading, declareRelease, declareWindowChrome, deepFocus, describeFailure, disclosureAt, dismissPopoversOutside, drawn$1 as drawn, elementDirective, elementFrame, ensureSyntaxLanguage, eventSource, exceptionRecord, exceptionText, excludedByInert, failSoft, failSoftUnreported, failureContext, failureOf, fitsWhole, flashDuration, focusDestination, focusRevision, focused, foldBlock, foldDuration, frameFor, frameView, frameVisibility, generated, generatedElement, growthAfterIsSeen, growthIsSeen, handBack, hasArea, headerCuts, headerInset, holdCurrentLocation, holdFocus, holdRendering, holdToRead, hoveringPointer, iconElement, iconTemplate, inBaseLayer, inChrome, inUi, inWindowChrome, inlineStyle, inputCount, inputInFrame, installElementIntegration, installLanguagePaths, installLayerStyleIntegration, installMoveFocus, installScrollerLookup, installStageIntegration, intersect, isElement, isHTML, isNativeLayer, isNode, isStage, isText, keeps, keepsHidden, keepsText, landedBox, landingBand, landingInsets, landingRoom, langForPath, layerLanding, layoutChanged, layoutPx, layoutWindow, letGo, listWalkPosition, liveStages, loadDeferred, measure, motion, motionEasing, motionPlays, motionTime, move, moveScrollerBy, nameAction, namedAction, nativeFocusTarget, nativeLayerHolding, nativeLayers, nativeModalAdmits, nearObserver, nearWindow, nextAnimation, nextFrame, nextRender, observePreparations, observeQueuedWork, offer, offerAction, offerElement, offered, offeredAction, offeredActionElement, onCurrentLocation, onFocusVisibility, onFrameVisibility, onLetGo, onMotionPreferenceChange, onPress, onPressAway, onUserInput, once, openLayer, openerOf, orderChildren, outputProducer, overIn, overlaps, overlapsAcross, pagePresented, pageScroller, pageUpgraded, paintClips, passOn, patchRetains, patchTree, placeBox, placeHolder, placeKept, placesFailure, plainPress, playMotion, pointerAt, presented, pressHolds, pressIsKeyboardActivation, pressLed, pressRecords, pressing, publishOutput, q, readCaret, readSampleVisibility, recentPlaceInput, recoveredLabelFocus, reducedMotion, refuseCommands, refuseOutput, registerVisualParts, registeredVisualPart, registeredVisualPartAt, registeredVisualPartLabel, registeredVisualParts, registrations, relabel, release, releaseFocus, releaseOutlets, renderedOrder, renderedParent, renderedUnder, renderingState, reportFailure, restorePointer, restrictUserIntent, retainUserIntent, returnDuration, revealRegisteredVisualPart, revealsVisualParts, rightCover, ringBox, roomPx, rove, rowArrows, scrollAxes, scrollBehavior, scrollChoices, scrollContainer, scrollGlides, scrollIntoReadingBand, scrollIntoView, scrollLimit, scrollToEnd, scrollersOf, scrolling, scrollsBy, scrollsContent, searchField, seenRect, selectableOffer, selectableOffered, selectsAll, setChildLists, setChildren, setRegistration, setRenderedChildren, setScroll, shadowHost, shadowStage, shellRight, showNativeLayer, shownBand, shownBox, shownExtent, shownParts, shownRect, shownWindow, showsContents, sizeObserver, skipped, slotTop, stackLevel, startsAt, stopScroll, stuckBox, synNodes, syntax, syntaxLanguageNames, tabStops, tabStore, takesLetters, textWidth, threadSurface, tick, tokenLines, typesText, uiInside, under, underOccluder, union, upFrom, updateSurface, userScrollport, visibleBand, visibleFocus, visualPartAdmission, visualPartProblems, visualViewport, walkPosition, walkPositionLabel, watchArrivals, watchCurrentLocationIn, watchFrame, watchLayerChanges, watchOwner, watchRoom, watchScrollEnds, watchScrolls, wearsLentStop, whenLeft, whenNone, whileConnected, windowChromeBoxes, x$1 as x };