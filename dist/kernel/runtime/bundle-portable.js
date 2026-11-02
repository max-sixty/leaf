import { __exportAll } from "./bundle-rolldown-runtime.js";
import "/runtime/document-inputs.js";
import { AsyncDirective, Directive, LitElement, LitElement as LitElement$1, PartType, PartType as PartType$1, directive, directive as directive$1, guard, html, html as html$1, keyed, live as live$1, noChange, nothing, nothing as nothing$1, ref, render, render as render$1, repeat, unsafeSVG } from "/vendor/lit.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

//#region runtime/queued-work.js
const jobObservers = /* @__PURE__ */ new Set();
const jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
	jobObservers.add(observer);
	return () => jobObservers.delete(observer);
}
const announce$2 = (phase, job, observers) => {
	for (const observer of observers) observer(phase, job);
};
function enqueueWork(callback) {
	const job = Object.freeze({ callback });
	const observers = [...jobObservers];
	jobCohorts.set(job, observers);
	announce$2("enqueue", job, observers);
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
		announce$2("run", job, observers);
		return callback(...args);
	} finally {
		announce$2("finish", job, observers);
	}
}
function bindQueuedWork(callback) {
	const job = enqueueWork(callback);
	return (...args) => runWork(job, ...args);
}
function cancelWork(job) {
	const observers = claim(job);
	if (observers) announce$2("cancel", job, observers);
}

//#endregion
//#region runtime/frame-visibility.js
const child = document.documentElement.lfSample;
let admitted$1 = false;
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
if (!child) for (; containingView.frameElement; containingView = containingView.parent) owners$1.push(watchFrame(containingView.frameElement, publish$2));
function frameVisibility() {
	if (child) return { visible: admitted$1 };
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
function publish$2() {
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
	admitted$1 = detail.visible;
	publish$2();
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
let frame$1 = 0;
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
	if (!running && !frame$1) frame$1 = requestAnimationFrame(pass);
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
	frame$1 = 0;
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
	if (queued.size) frame$1 = requestAnimationFrame(pass);
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
		publish$1(null, cause(null));
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
function publish$1(node, cause) {
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
	publish$1(at, cause(at, event.relatedTarget));
}
function watchCurrentLocationAround(node) {
	for (let at = node; at; at = renderedParent(at)) {
		const root = at.getRootNode();
		if (focusRoot(root)) watchCurrentLocationIn(root);
	}
}
function enter$1(event) {
	if (read.has(event)) return;
	read.add(event);
	watchCurrentLocationAround(deepFocus());
}
function watchCurrentLocationIn(root) {
	root.addEventListener("focus", enter$1, true);
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
		if (!drawn$1(left)) return publish$1(null, "drop");
		if (left !== document.body) placements += 1;
		if (lastLocation?.deref() === left) lastLocation = null;
		publish$1(null, cause(null));
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
		publish$1(at, cause(at));
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
	publish$1(null, cause(null));
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
	publish$1(at, "return");
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
function release$1() {
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
const COLLAPSE$1 = /[\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
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
const sending$1 = (turn) => ({
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
			attention: reaction ? null : sending$1(gesture)
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
const schedule$1 = createPresentationSchedule(bindQueuedWork);
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
	const { ready, committed: dom } = schedule$1.enqueue(() => {
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
	const presenter = schedule$1.presenter({
		attach: () => presentation.attach(region),
		after,
		paint: (value, current) => {
			owed = false;
			forget();
			const generation = following;
			const stretch = (run) => {
				let first = true;
				let outcome;
				const stop = x$1(() => {
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
		if (value === null) return schedule$1.passed();
		owed = true;
		return presenter.sync(value);
	};
	const present = () => d(() => W(() => {
		tick(revision);
		return claim(selected.value);
	}));
	documentPresenters.push(present);
	let first = true;
	x$1(() => {
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
	return schedule$1.passed();
});
const whenDocumentPresented = () => schedule$1.passed();
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
//#region runtime/root-state.js
const setRuntimeRootAttribute = (...args) => window.lfRootState.setRuntimeRootAttribute(...args);
const setRuntimeRootStyle = (...args) => window.lfRootState.setRuntimeRootStyle(...args);
const removeRuntimeRootStyle = (...args) => window.lfRootState.removeRuntimeRootStyle(...args);
const runtimeRootState = (root) => ({
	attributes: window.lfRootState.attributes(root),
	styles: window.lfRootState.styles(root)
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
	revisionLabels: readPart((root) => root.authoritative?.revision_labels)
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
//#region runtime/ids.js
const randomId = () => Array.from(crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join("");

//#endregion
//#region runtime/interaction-log.js
const url = PAGE_ROOT !== null ? new URL("api/interaction", PAGE_ROOT).href : null;
const root = PAGE_ROOT !== null ? new URL(PAGE_ROOT).pathname.replace(/\/$/, "") : "";
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
	const previous = nodeIds.get(node);
	if (previous !== void 0) return previous;
	const id = ++nextNodeId;
	nodeIds.set(node, id);
	return id;
}
function targetValue(target) {
	if (target instanceof window.HTMLInputElement) {
		if (target.type === "checkbox" || target.type === "radio") return {
			checked: target.checked,
			value: target.value
		};
		return { value: target.value };
	}
	if (target instanceof Element && "value" in target && target.matches(`${TEXT_BOX}, select`)) return { value: target.value };
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
	if (["beforetoggle", "toggle"].includes(event.type) && target instanceof Element) entry.open = "open" in target && target.open === true || isNativeLayer(target);
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
	if (url === null) return;
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
	for (const row of queue.slice(start, start + 100)) {
		const size = row.bytes + (count ? 1 : 0);
		if (count && bytes + size > maxBytes) break;
		bytes += size;
		count++;
	}
	return {
		count,
		body: `${prefix}${queue.slice(start, start + count).map((row) => row.body).join(",")}]}`
	};
}
function post(body, destination) {
	return fetch(destination, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body,
		credentials: "same-origin",
		keepalive: encoder.encode(body).length < 6e4
	});
}
async function flush() {
	if (url === null || sending || !queue.length) return;
	sending = true;
	const { count, body } = batch(0, 1e5);
	inFlightCount = count;
	let delay = 250;
	try {
		const response = await post(body, url);
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
if (url !== null) {
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
			if (!(resource instanceof PerformanceResourceTiming)) continue;
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
			post(body, url).catch(() => {});
		}
	}, true);
}

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
const announce$1 = (words) => window.dispatchEvent(new CustomEvent(ANNOUNCE, { detail: words }));
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
	const dispose = x$1(() => {
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
const declared$1 = /* @__PURE__ */ new WeakMap();
addEventListener(COMMANDS, (event) => {
	const element = commandsChangedOn(event);
	const declaration = element.lfCommands ?? null;
	const standing = declared$1.get(element);
	if (declaration === (standing?.declaration ?? null)) {
		paintKeys();
		return;
	}
	if (!declaration) {
		declared$1.delete(element);
		if (detachScope(element, standing.scope)) repaint();
		return;
	}
	try {
		const scope = attachScope(element, isCommandScope(declaration) ? declaration.scope : declaredScope(declaration.title, declaration.rows, declaration));
		declared$1.set(element, {
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
	let initial = element;
	let failure = null;
	const dispose = x$1(() => {
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
function layerHeaders(headers) {
	const result = new Headers({
		...layerGeneration && { "Leaf-Layer": layerGeneration },
		...runtimeIdentity && { "Leaf-Runtime": runtimeIdentity },
		...runtime.currentRevision && { "Leaf-View-Revision": String(runtime.currentRevision) },
		...release && { "Leaf-Release": release }
	});
	new Headers(headers).forEach((value, name) => result.set(name, value));
	return result;
}
const dataHeaders = (held) => held.version === null ? {} : { "Leaf-Data-Version": held.version };
const completeData = (state, held) => ({
	...state,
	data: {
		...state.data,
		sources: state.data.sources ?? held.sources
	}
});
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
	if (response.ok || response.headers.get("Content-Type")?.split(";").at(0)?.trim() === "application/json") try {
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
	if (reference !== null && /^\d{12}$/.test(reference)) runtime.sessionReference = reference;
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
	window.lfDocumentLifetime.whenActive(`report ${text}`, () => {
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
//#region runtime/text-alignment.js
const textUnits = new Intl.Segmenter(void 0, { granularity: "word" });
const sentenceUnits = new Intl.Segmenter(void 0, { granularity: "sentence" });
const MAX_EDIT_LENGTH = 1e3;
function alignText(before, after, units = textUnits, maxEditLength = MAX_EDIT_LENGTH) {
	const left = [...units.segment(before)].map((part) => part.segment);
	const right = [...units.segment(after)].map((part) => part.segment);
	const changes = diffArrays(left, right, { maxEditLength });
	if (!changes) return [{
		kind: "delete",
		text: before
	}, {
		kind: "insert",
		text: after
	}].filter((run) => run.text);
	return changes.map((change) => ({
		kind: change.added ? "insert" : change.removed ? "delete" : "same",
		text: change.value.join("")
	})).filter((run) => run.text);
}
function alignInlineText(before, after) {
	const coarse = alignText(before, after, sentenceUnits)[Symbol.iterator]();
	const runs = [];
	const push = (run) => {
		const last = runs.at(-1);
		if (last?.kind === run.kind) last.text += run.text;
		else runs.push({ ...run });
	};
	let current = coarse.next();
	while (!current.done) {
		const run = current.value;
		const next = coarse.next();
		if (run.kind !== "delete" || next.done || next.value.kind !== "insert") {
			push(run);
			current = next;
			continue;
		}
		const replacement = next.value;
		const fine = alignText(run.text, replacement.text);
		if (fine.filter((part) => part.kind === "same").reduce((length, part) => length + part.text.length, 0) >= Math.min(run.text.length, replacement.text.length) * .6) fine.forEach(push);
		else {
			push(run);
			push(replacement);
		}
		current = coarse.next();
	}
	return runs;
}

//#endregion
//#region runtime/words.js
const labelWords = (value) => String(value ?? "").replace(COLLAPSE$1, " ").trim();
function excerptWords(value, cap) {
	const words = labelWords(value);
	const points = [...words];
	if (points.length <= cap) return words;
	const excerpt = points.slice(0, cap - 1);
	const boundary = excerpt.lastIndexOf(" ");
	const end = boundary >= cap / 2 ? boundary : excerpt.length;
	return `${excerpt.slice(0, end).join("")}…`;
}

//#endregion
//#region runtime/passages.js
const passageFences = /* @__PURE__ */ new WeakSet();
const verbatimOwnerIdentity = /* @__PURE__ */ new WeakMap();
const verbatimBoundaryIdentity = /* @__PURE__ */ new WeakMap();
let settledReading = null;
let settledDecisions;
let settled = null;
let settledKey = "[]";
function settlements() {
	if (settledDecisions !== registry.$decisions || !settledReading) {
		const decisions = settledDecisions = registry.$decisions;
		settledReading = readPart((root) => {
			const holders = /* @__PURE__ */ new Map();
			for (const [id, { state }] of root.effective.widgets) {
				const tag = root.document.authored.get(id)?.tag;
				const decision = tag === void 0 ? void 0 : decisions?.[tag];
				const outcome = decision && state[decision.verb]?.detail?.outcome;
				const retires = outcome ? decision.retires[outcome] : null;
				if (tag !== void 0 && retires?.length) holders.set(id, {
					tag,
					retires: [...retires]
				});
			}
			return holders;
		});
	}
	const next = settledReading();
	if (next !== settled) {
		settled = next;
		settledKey = JSON.stringify([...settled]);
	}
	return settled;
}
function retiredSlot(el) {
	const holder = upFrom(el);
	if (!holder?.id || el.ownerDocument !== document) return false;
	const settlement = settlements().get(holder.id);
	return settlement?.tag === holder.localName && settlement.retires.includes(el.localName);
}
function renderRetired(el, outcome) {
	const outcomes = decisionFor(el.localName)?.retires;
	if (!outcomes) return;
	for (const [candidate, tags] of Object.entries(outcomes)) for (const tag of tags) for (const root of [el, ...el.shadowRoot ? [el.shadowRoot] : []]) for (const slot of root.children) if (slot.localName === tag) slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, candidate === outcome);
}
function settledAway(el) {
	let at = el;
	for (; at; at = at.parentElement) if (retiredSlot(at)) return true;
	const nodes = [...el.childNodes];
	return nodes.some((n) => isElement(n) && retiredSlot(n)) && nodes.every((n) => isElement(n) ? retiredSlot(n) || uiInside(n, el) : !isText(n) || !n.data.trim());
}
const GENERATED = ".lf-ui, [data-lf-gen]";
const DATUM = "[data-lf-projection][data-lf-datum]";
const showsWords = (block) => block.checkVisibility({ visibilityProperty: true });
const LEAF_SURFACE = ".lf-chrome, [data-lf-runtime]";
const leafSurface = (node) => isNode(node) ? closestAcross(node, LEAF_SURFACE) : null;
const pageWords = (node) => Boolean(node) && !inChrome(node) && !inUi(node);
const bareTextRefusal = (n) => {
	const host = shadowHost(n.getRootNode());
	const at = host ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>` : "a module";
	return /* @__PURE__ */ new Error(`${at} staged bare text into a shadow root: ${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, so the page holds no block, cell or fence for it. Give a module's rendered words an element to sit in.`);
};
const elementOver = (n) => {
	if (n.parentElement) return n.parentElement;
	if (isText(n)) throw bareTextRefusal(n);
	throw new Error("A passage node has no element over it");
};
function refusesBareText(root) {
	const bare = [...root.childNodes].filter(isText).find((node) => node.data.trim());
	if (!bare) return false;
	refuseShadowRoot(root);
	const refusal = bareTextRefusal(bare);
	reportPageError(refusal);
	if (!pageUpgraded()) window.dispatchEvent(new CustomEvent("lf-startup-failed", { detail: {
		reason: refusal.message,
		error: refusal,
		page: true
	} }));
	return true;
}
const frameOf = (node) => {
	for (let a = isElement(node) ? node : upFrom(node); a; a = upFrom(a)) if (a.localName?.startsWith("lf-")) return a;
	return null;
};
const NO_CONTEXT = Object.freeze({
	chrome: false,
	silenced: false,
	generated: false,
	gen: null,
	block: null,
	textBlock: null,
	island: null,
	cells: null
});
const GEN = "[data-lf-gen]";
const ISLAND = "[data-lf-markdown-words]";
const MARKS = [
	UI_MARKS,
	GENERATED,
	ISLAND
].join(", ");
const BLOCK_TAGS = new Set(TEXT_BLOCK.split(","));
const BLOCKS = `${TEXT_BLOCK}, ${DATUM}`;
const chromeMark = (el) => el.matches(".lf-ui, [data-lf-said]") ? !el.matches(SAID) : null;
const SILENT_TAGS = /* @__PURE__ */ new Set([
	"script",
	"style",
	"textarea"
]);
const silences = (el) => SILENT_TAGS.has(el.localName) || retiredSlot(el);
const unmodelled = (el) => {
	const attr = el.getAttribute("data-lf-said");
	const parent = el.parentElement;
	return !(attr && parent && registry[parent.localName]?.["x-says"]?.[attr]);
};
const fileModelsPassage = (segments) => segments.every(({ node, gen }) => !isEditing(elementOver(node)) && (!gen || !unmodelled(gen)));
const opaque = (el) => passageFences.has(el);
const editingBoundary = (el) => isEditing(el) !== isEditing(el.parentElement);
const isEditing = (el) => el !== null && isHTML(el) && el.isContentEditable;
function enter(ctx, el, inFrame = true) {
	const marked = el.hasAttributes() && el.matches(MARKS);
	const textBlock = BLOCK_TAGS.has(el.localName);
	const block = textBlock || el.matches("[data-lf-projection][data-lf-datum]");
	const editing = editingBoundary(el);
	const cell = opaque(el) || editing || marked && el.matches(GEN) && unmodelled(el);
	const silent = !ctx.silenced && silences(el);
	if (!marked && !block && !cell && !silent) return ctx;
	const chrome = (marked && inFrame ? chromeMark(el) : null) ?? ctx.chrome;
	const generated = ctx.generated || marked && inFrame && el.matches(GENERATED);
	return {
		chrome,
		silenced: ctx.silenced || silent,
		generated,
		gen: marked && el.matches(GEN) ? el : ctx.gen,
		block: block ? el : ctx.block,
		textBlock: textBlock ? el : ctx.textBlock,
		island: marked && el.matches(ISLAND) ? el : ctx.island,
		cells: cell ? {
			el,
			editing,
			up: ctx.cells
		} : ctx.cells
	};
}
const crossed = (ctx) => ({
	...ctx,
	chrome: false,
	silenced: false,
	generated: false,
	gen: null
});
function contextAt(el, frame) {
	const over = [];
	for (let a = el; a; a = upFrom(a)) over.push(a);
	let ctx = NO_CONTEXT;
	let inFrame = !frame;
	for (const a of over.reverse()) {
		if (a === frame) inFrame = true;
		if (a.parentNode?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) ctx = crossed(ctx);
		ctx = enter(ctx, a, inFrame);
	}
	return ctx;
}
const segmentIn = (node, ctx) => ({
	node,
	start: 0,
	end: node.data.length,
	block: ctx.block ?? (ctx.island ? upFrom(ctx.island) : null),
	textBlock: ctx.textBlock ?? (ctx.island ? upFrom(ctx.island) : null),
	gen: ctx.gen
});
const READINGS = {
	says: (ctx) => !ctx.chrome && !ctx.silenced,
	wrote: (ctx) => !ctx.generated,
	unsilenced: (ctx) => !ctx.chrome
};
const authored = (root) => {
	const frame = frameOf(root);
	return (n) => !overIn(isElement(n) ? n : elementOver(n), GENERATED, frame);
};
function walk(root, onText, skip = null, onBreak = null, onElement = null) {
	const frame = frameOf(root);
	const passed = /* @__PURE__ */ new Map();
	const contextOver = (node) => {
		const over = elementOver(node);
		return passed.get(over) ?? contextAt(over, frame);
	};
	const visitElement = (child, ctx) => {
		if (skip?.(child)) return;
		const inner = enter(ctx, child);
		if (child.localName === "br") onBreak?.(inner);
		else if (isHTML(child, "slot")) {
			passed.set(child, inner);
			onElement?.(child, inner, true);
			for (const assigned of child.assignedNodes({ flatten: true })) isText(assigned) ? onText(assigned, contextOver(assigned)) : isElement(assigned) && visitElement(assigned, contextOver(assigned));
			onElement?.(child, inner, false);
		} else {
			const declared = declaredRoot(child);
			if (declared && !refusesBareText(declared)) {
				passed.set(child, inner);
				visit(declared, crossed(inner), child);
			} else visit(child, inner);
		}
	};
	const visit = (node, ctx, host = null) => {
		const element = host ?? (isElement(node) ? node : null);
		if (element) onElement?.(element, ctx, true);
		for (let child = node.firstChild; child; child = child.nextSibling) if (isText(child)) {
			if (node.nodeType !== Node.ELEMENT_NODE && !child.data.trim()) continue;
			if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
			onText(child, ctx);
		} else if (isElement(child)) visitElement(child, ctx);
		if (element) onElement?.(element, ctx, false);
	};
	const host = shadowHost(root);
	visit(root, isElement(root) ? contextAt(root, frame) : host ? crossed(contextAt(host, frame)) : NO_CONTEXT);
}
function textNodesUnder(root, reading = "says", boundary = null, format = "prose") {
	const keeps = READINGS[reading];
	const segments = [];
	let breakBefore = false;
	let lineBefore = "";
	const styles = /* @__PURE__ */ new Map();
	const style = (element) => {
		let value = styles.get(element);
		if (!value) styles.set(element, value = getComputedStyle(element));
		return value;
	};
	walk(root, (node, ctx) => {
		if (keeps(ctx)) {
			segments.push({
				...segmentIn(node, ctx),
				breakBefore,
				...format === "lines" && {
					lineBefore,
					whiteSpace: style(node.assignedSlot ?? elementOver(node)).whiteSpaceCollapse
				}
			});
			breakBefore = false;
			lineBefore = "";
		}
	}, boundary && ((child) => boundary(child, segments.length)), (ctx) => {
		if (keeps(ctx)) {
			breakBefore = true;
			lineBefore = "\n";
		}
	}, format === "lines" ? (element, ctx, entering) => {
		if (!keeps(ctx)) return;
		const display = style(element).display;
		if (display === "table-cell") {
			if (!entering && lineBefore !== "\n") lineBefore = "	";
		} else if (/^(block|flow-root|list-item|flex|grid|table|-webkit-box)/.test(display)) lineBefore = "\n";
	} : null);
	return segments;
}
const elementById = (id, root = document) => {
	if (id == null || root === null) return null;
	const found = root === document ? document.getElementById(id) : root.querySelector(`[id="${CSS.escape(id)}"]`);
	if (found) return found;
	for (const shadow of shadowRootsIn(root)) {
		const inside = shadow.getElementById(id);
		if (inside) return inside;
	}
	return null;
};
const pageDocument = (doc = document) => doc.querySelector("body > main");
const isLayoutBox = (box) => getComputedStyle(box).getPropertyValue("--lf-layout-box").trim() === "1";
const layoutBox = () => {
	const main = document.querySelector("body > main");
	if (!main || isLayoutBox(main)) return main;
	const parts = main.querySelector(":scope > [data-lf-views=\"parts\"]");
	return [...main.children, ...[...parts?.children ?? []].flatMap((part) => [...part.children])].find((box) => box.checkVisibility() && isLayoutBox(box)) ?? main;
};
const authoredScope = (node) => closestAcross(node, ".lf-msg-body") ?? pageDocument();
const elementFromPointAcross = (x, y) => {
	let el = document.elementFromPoint(x, y);
	for (let root; el && (root = declaredRoot(el));) {
		const inner = root.elementFromPoint(x, y);
		if (!inner || inner === el) break;
		el = inner;
	}
	return el;
};
const pageQueryAll = (selector) => [document, ...pageShadowRoots()].flatMap((root) => {
	return [...root.querySelectorAll(selector)];
});
const beforePoint = (node, container, offset) => {
	if (node === container) return false;
	if (container.nodeType === Node.TEXT_NODE || offset === 0) return renderedOrder(node, container) < 0;
	const next = container.childNodes[offset];
	return next ? renderedOrder(node, next) < 0 : renderedUnder(node, container) || renderedOrder(node, container) < 0;
};
const coveredBy = (range, node) => !beforePoint(node, range.startContainer, range.startOffset) && (node === range.endContainer || beforePoint(node, range.endContainer, range.endOffset));
function segmentsIn(range) {
	const segments = [];
	for (const segment of pageText().segments) {
		const { node } = segment;
		if (!coveredBy(range, node)) continue;
		const start = node === range.startContainer ? range.startOffset : 0;
		const end = node === range.endContainer ? range.endOffset : segment.end;
		if (end > start) segments.push({
			...segment,
			start,
			end
		});
	}
	return segments;
}
const blockAt = (node) => {
	const block = closestAcross(node, BLOCKS);
	if (block) return block;
	const island = closestAcross(node, ISLAND);
	return island ? upFrom(island) : null;
};
const segmentBlock = (segment) => segment.block ?? segment.node.parentElement;
const segmentTextBlock = (segment) => segment.textBlock ?? segment.node.parentElement;
const COLLAPSIBLE = new RegExp(`^(?:${COLLAPSE$1.source})$`, "u");
function readSegments(segments, mapCharacters) {
	let text = "";
	const units = [];
	let pendingSpace = null;
	const push = (character, start, end) => {
		if (COLLAPSIBLE.test(character)) {
			if (text) pendingSpace = pendingSpace ? {
				start: pendingSpace.start,
				end
			} : {
				start,
				end
			};
			return;
		}
		if (pendingSpace) {
			text += " ";
			if (mapCharacters) units.push({
				text: " ",
				...pendingSpace
			});
			pendingSpace = null;
		}
		text += character;
		if (mapCharacters) units.push({
			text: character,
			start,
			end
		});
	};
	let previous;
	for (const seg of segments) {
		if (previous && (seg.breakBefore || segmentTextBlock(seg) !== segmentTextBlock(previous))) {
			const point = {
				node: seg.node,
				offset: seg.start
			};
			push(" ", point, point);
		}
		let offset = seg.start;
		for (const character of seg.node.data.slice(seg.start, seg.end)) {
			const end = offset + character.length;
			push(character, {
				node: seg.node,
				offset
			}, {
				node: seg.node,
				offset: end
			});
			offset = end;
		}
		previous = seg;
	}
	return mapCharacters ? {
		text,
		units
	} : text;
}
const quoteFrom = (segments) => readSegments(segments, false);
const readingFrom = (segments) => readSegments(segments, true);
const cut = (text, from, to) => [...text].slice(from, to).join("");
function linesFrom(segments) {
	let text = "";
	let separator = "";
	for (const segment of segments) {
		if (segment.lineBefore && text) separator = segment.lineBefore === "\n" || separator === "\n" ? "\n" : "	";
		const { whiteSpace } = segment;
		const collapses = whiteSpace === "preserve" || whiteSpace === "break-spaces" ? null : whiteSpace === "preserve-breaks" ? /[\t\r\f ]/ : /[\t\n\r\f ]/;
		for (const character of segment.node.data.slice(segment.start, segment.end)) {
			if (collapses?.test(character)) {
				if (text && !text.endsWith("\n")) separator ||= " ";
				continue;
			}
			if (whiteSpace === "preserve-breaks" && character === "\n" && separator === " ") separator = "";
			text += separator + character;
			separator = "";
		}
	}
	return text;
}
const says = (el, options = {}) => {
	const segments = textNodesUnder(el, "says", null, options.format);
	return options.format === "lines" ? linesFrom(segments) : quoteFrom(segments);
};
const wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));
function rangeOf(segments) {
	const first = segments[0];
	const last = segments.at(-1);
	if (!first || !last) throw new RangeError("A passage range needs at least one segment");
	const range = document.createRange();
	range.setStart(first.node, first.start);
	range.setEnd(last.node, last.end);
	return range;
}
const EDGE = "\0";
function segmentAt({ segments }, i) {
	let lo = 0;
	let hi = segments.length;
	while (lo < hi) {
		const mid = lo + hi >> 1;
		const segment = segments[mid];
		if (segment && segment.rawStart <= i) lo = mid + 1;
		else hi = mid;
	}
	return lo - 1;
}
function pointAt(reading, i) {
	const segment = reading.segments[segmentAt(reading, i)];
	if (!segment) return null;
	const offset = i - segment.rawStart;
	return offset < segment.end - segment.start ? {
		node: segment.node,
		offset: segment.start + offset,
		segment
	} : null;
}
function spanOf(reading, lo, hi) {
	const { segments } = reading;
	const out = [];
	let seg;
	for (let k = Math.max(0, segmentAt(reading, lo)); seg = segments[k]; k++) {
		const from = seg.rawStart;
		if (from >= hi) break;
		const a = Math.max(lo, from);
		const b = Math.min(hi, from + seg.end - seg.start);
		if (b > a) out.push({
			...seg,
			start: seg.start + a - from,
			end: seg.start + b - from,
			breakBefore: Boolean(seg.breakBefore && a === from)
		});
	}
	return out;
}
const holds = (reading, at, want, before) => {
	const there = neighbourhood(reading, at, want.length || 1, before);
	if (!want) return there === "";
	return before ? there.endsWith(want) : there.startsWith(want);
};
function neighbourhood(reading, at, want, before) {
	const { fences } = reading;
	const edge = before ? fences.filter((f) => f <= at).at(-1) ?? 0 : fences.find((f) => f >= at) ?? reading.raw.length;
	for (let raw = want * 2;; raw *= 2) {
		const lo = before ? Math.max(edge, at - raw) : at;
		const hi = before ? at : Math.min(edge, at + raw);
		const text = quoteFrom(spanOf(reading, lo, hi));
		if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
	}
}
const WATCH_READING = {
	subtree: true,
	childList: true,
	characterData: true,
	attributes: true,
	attributeOldValue: true,
	attributeFilter: [
		"class",
		"data-lf-said",
		"data-lf-gen",
		"data-lf-projection",
		"data-lf-datum",
		"slot",
		"name",
		"contenteditable"
	]
};
let reading = null;
let elementReadings = /* @__PURE__ */ new WeakMap();
let readingVocabulary;
let readingSettled;
let watcher = null;
const pageReads = (over) => !isElement(over) || READINGS.says(contextAt(over, null));
const holdsSaid = (node) => isElement(node) && (node.matches("[data-lf-said]") || node.querySelector("[data-lf-said]") !== null);
const speaks = (node, read) => read && !(isElement(node) && chromeMark(node) === true) || holdsSaid(node);
const changesTheReading = (record) => {
	const { target } = record;
	if (record.type === "childList") {
		const read = pageReads(target);
		return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
	}
	if (record.type === "characterData") return pageReads(target.parentNode);
	if (!isElement(target)) return false;
	if (record.attributeName === "class") {
		if (/(^|\s)lf-ui(\s|$)/.test(record.oldValue ?? "") === target.classList.contains("lf-ui")) return false;
	}
	if (record.attributeName === "name" && target.localName !== "slot") return false;
	return record.attributeName === "data-lf-said" && record.oldValue !== null || holdsSaid(target) || pageReads(target.parentNode);
};
let readingVersion = 0;
const forgetReading = () => {
	reading = null;
	elementReadings = /* @__PURE__ */ new WeakMap();
	readingVersion += 1;
};
function pageReadingVersion() {
	catchUpReading();
	return readingVersion;
}
function watchReading() {
	if (watcher) return watcher;
	watcher = new MutationObserver((records) => {
		if (records.some(changesTheReading)) forgetReading();
	});
	watcher.observe(document, WATCH_READING);
	return watcher;
}
function watchPassageRoot(root) {
	watchReading().observe(root, WATCH_READING);
	forgetReading();
}
function fencePassageParts(root, children = root.children) {
	passageFences.add(root);
	for (const child of children) passageFences.add(child);
	forgetReading();
}
function pageText() {
	catchUpReading();
	return reading ??= readPage();
}
function catchUpReading() {
	const moved = watchReading().takeRecords().some(changesTheReading);
	const vocabulary = registry.$layer?.generation;
	settlements();
	if (moved || vocabulary !== readingVocabulary || settledKey !== readingSettled) forgetReading();
	readingVocabulary = vocabulary;
	readingSettled = settledKey;
}
function elementReading(element, reading = "says") {
	catchUpReading();
	let kept = elementReadings.get(element);
	if (kept?.[reading] !== void 0) return kept[reading];
	const value = quoteFrom(textNodesUnder(element, reading));
	if (element.isConnected && element.ownerDocument === document && pageReads(element)) {
		if (!kept) elementReadings.set(element, kept = {});
		kept[reading] = value;
	}
	return value;
}
function readPage() {
	const segments = [];
	const cellChains = [];
	const keeps = READINGS.says;
	let breakBefore = false;
	walk(document.body, (node, ctx) => {
		if (!keeps(ctx)) return;
		segments.push({
			...segmentIn(node, ctx),
			breakBefore
		});
		breakBefore = false;
		cellChains.push(ctx.cells);
	}, null, (ctx) => {
		if (keeps(ctx)) breakBefore = true;
	});
	const dynamicWords = /* @__PURE__ */ new Set();
	for (const { gen } of segments) if (gen && unmodelled(gen)) dynamicWords.add(gen);
	const cellOf = (chain) => {
		for (let at = chain; at; at = at.up) if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
		return null;
	};
	const parts = [];
	const indexed = [];
	const positions = /* @__PURE__ */ new WeakMap();
	const fences = /* @__PURE__ */ new Set();
	let length = 0;
	let previousCell = null;
	segments.forEach((seg, k) => {
		const cell = cellOf(cellChains[k]);
		if (k === 0) {
			if (cell) fences.add(0);
		} else {
			if (cell !== previousCell && (cell || previousCell)) fences.add(length);
			parts.push(seg.breakBefore ? " " : EDGE);
			length += 1;
		}
		indexed.push({
			...seg,
			rawStart: length
		});
		positions.set(seg.node, length - seg.start);
		parts.push(seg.node.data);
		length += seg.end - seg.start;
		previousCell = cell;
	});
	if (previousCell) fences.add(length);
	return {
		raw: parts.join(""),
		positions,
		fences: [...fences].sort((a, b) => a - b),
		segments: indexed
	};
}
function pageBlocks() {
	const text = pageText();
	if (!text.blocks) {
		const seen = /* @__PURE__ */ new Set();
		text.blocks = text.segments.map(({ block }) => block).filter((block) => block !== null).filter((block) => !seen.has(block) && seen.add(block));
	}
	return text.blocks;
}
function spanIn(reading, segments) {
	const first = segments[0];
	const last = segments.at(-1);
	const position = (node) => {
		const offset = reading.positions.get(node);
		if (offset === void 0) throw new RangeError("A passage must belong to the page reading it is placed in");
		return offset;
	};
	const start = first ? position(first.node) + first.start : 0;
	return [start, last ? position(last.node) + last.end : start];
}
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const LEAD_CAP = 400;
function confirmRest(raw, at, words) {
	let i = at;
	for (const w of words) {
		const gap = i;
		while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw.charAt(i)))) i++;
		if (i === gap) return -1;
		for (const ch of w) {
			while (raw[i] === EDGE) i++;
			if (!raw.startsWith(ch, i)) return -1;
			i += ch.length;
		}
	}
	return i;
}
const withinCell = (text, from, to) => !text.fences.some((fence) => from < fence && fence < to);
function findQuote(text, quote, anchor, within) {
	const { raw } = text;
	const words = quote.trim().split(/\s+/).filter(Boolean);
	if (!words.length) return [];
	const lead = [];
	let spent = 0;
	for (const next of words) {
		if (lead.length && spent + next.length > LEAD_CAP) break;
		lead.push(next);
		spent += next.length + 1;
	}
	const rest = words.slice(lead.length);
	const pattern = new RegExp(lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`), "g");
	const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
	const candidates = [];
	const exact = [];
	for (const at of raw.matchAll(pattern)) {
		const stop = confirmRest(raw, at.index + at[0].length, rest);
		if (stop === -1 || !withinCell(text, at.index, stop)) continue;
		if (within && !(under(pointAt(text, at.index)?.node, within) && under(pointAt(text, stop - 1)?.node, within))) continue;
		const hit = {
			from: at.index,
			to: stop
		};
		candidates.push(hit);
		if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false)) exact.push(hit);
	}
	const found = exact.length === 1 ? exact[0] : exact.length === 0 && candidates.length === 1 ? candidates[0] : null;
	return found ? spanOf(text, found.from, found.to) : [];
}
function searchableWords() {
	const styles = /* @__PURE__ */ new Map();
	const reachable = /* @__PURE__ */ new Map();
	const style = (el) => {
		let value = styles.get(el);
		if (!value) styles.set(el, value = getComputedStyle(el));
		return value;
	};
	const canReveal = (el) => {
		if (!el) return true;
		const kept = reachable.get(el);
		if (kept !== void 0) return kept;
		const css = style(el);
		const result = css.display !== "none" && (css.contentVisibility !== "hidden" || el.getAttribute("hidden") === "until-found") && canReveal(renderedParent(el));
		reachable.set(el, result);
		return result;
	};
	return ({ node }) => {
		const parent = renderedParent(node);
		return parent && style(parent).visibility === "visible" && canReveal(parent);
	};
}
function findText(text, query) {
	const words = query.trim().split(/\s+/u).filter(Boolean);
	if (!words.length) return [];
	const pattern = new RegExp(words.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`), "giu");
	const out = [];
	const searchable = searchableWords();
	for (let match; match = pattern.exec(text.raw);) {
		const from = match.index;
		const to = from + match[0].length;
		const segments = spanOf(text, from, to);
		if (withinCell(text, from, to) && segments.every(searchable)) out.push(segments);
		else {
			const point = text.raw.slice(from, from + 2)[Symbol.iterator]().next();
			if (!point.done) pattern.lastIndex = from + point.value.length;
		}
	}
	return out;
}
function contextAround(text, segments, { before = 28, after = 28 } = {}) {
	const [start, end] = spanIn(text, segments);
	function side(at, length, backwards) {
		if (!length) return "";
		const budget = length * 2 + 1;
		const neighbourhoodPoints = [...neighbourhood(text, at, budget, backwards)];
		const points = backwards ? neighbourhoodPoints.slice(-budget) : neighbourhoodPoints.slice(0, budget);
		const context = points.join("");
		const boundary = backwards ? points.slice(0, Math.max(0, points.length - length)).join("").length : points.slice(0, length).join("").length;
		const word = textUnits.segment(context).containing(backwards ? boundary : boundary - 1);
		const outer = word?.isWordLike ? backwards ? word.index : word.index + word.segment.length : boundary;
		if ((backwards ? outer === 0 : outer === context.length) && points.length >= budget) {
			const excerpt = excerptWords(backwards ? points.toReversed().join("") : context, length).slice(0, -1);
			return backwards ? [...excerpt].toReversed().join("") : excerpt;
		}
		return (backwards ? context.slice(outer) : context.slice(0, outer)).trim();
	}
	return {
		before: side(start, before, true),
		after: side(end, after, false)
	};
}
function pageParts(sel) {
	return pageQueryAll(sel).filter((el) => !inChrome(el));
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
const token$1 = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
const motionTime = (property, on = document.documentElement) => {
	const value = token$1(property, on);
	return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
const motionEasing = (property, on = document.documentElement) => token$1(property, on);
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
//#region runtime/chrome.js
const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
const chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");

//#endregion
//#region runtime/css-anchors.js
const anchorNames = /* @__PURE__ */ new WeakMap();
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
const partOf = (name) => name.slice(2);
const partNamed = (el) => {
	const name = anchorNames.get(el);
	return name !== void 0 && el.part.contains(partOf(name));
};
let partRules = null;
const declared = /* @__PURE__ */ new Set();
const given = /* @__PURE__ */ new WeakMap();
const watchedTrees = /* @__PURE__ */ new WeakSet();
const restoreParts = (el) => {
	if (!isElement(el)) return;
	for (const part of given.get(el) ?? []) if (!el.part.contains(part)) el.part.add(part);
};
function keepParts(root) {
	if (watchedTrees.has(root)) return;
	watchedTrees.add(root);
	new MutationObserver((records) => {
		for (const { target } of records) restoreParts(target);
	}).observe(root, {
		subtree: true,
		attributes: true,
		attributeFilter: ["part"]
	});
}
function namePart(el, name, pseudo = "") {
	if (!partRules) {
		partRules = new CSSStyleSheet();
		document.adoptedStyleSheets = [...document.adoptedStyleSheets, partRules];
	}
	if (!declared.has(name)) {
		const content = pseudo ? "content: \"\";" : "";
		partRules.insertRule(`::part(${partOf(name)})${pseudo} { ${content} anchor-name: ${name}; }`, partRules.cssRules.length);
		declared.add(name);
	}
	given.set(el, /* @__PURE__ */ new Set([...given.get(el) ?? [], partOf(name)]));
	keepParts(el.getRootNode());
	restoreParts(el);
}
function anchorReading(el, name) {
	if (!isElement(el)) return { name: el.name };
	name ??= anchorNames.get(el) ?? nextName();
	anchorNames.set(el, name);
	if (el.getRootNode() !== document) return partNamed(el) ? {
		el,
		name
	} : {
		el,
		name,
		write: name,
		part: true
	};
	const written = inlineStyle(el).anchorName;
	if (written.split(",").some((part) => part.trim() === name)) return {
		el,
		name
	};
	const authored = written || getComputedStyle(el).anchorName;
	return {
		el,
		name,
		write: !authored || authored === "none" ? name : `${authored}, ${name}`
	};
}
function nameAnchor({ el, name, write, part }) {
	if (write && part) {
		if (!partNamed(el)) namePart(el, name);
	} else if (write) inlineStyle(el).anchorName = write;
	return name;
}
function nameable(el) {
	const root = el.getRootNode();
	if (root === document) return true;
	if (shadowHost(root)?.getRootNode() !== document) return false;
	if (anchorNames.has(el) && partNamed(el)) return true;
	const authored = getComputedStyle(el).anchorName;
	return !authored || authored === "none";
}
function outsideScopes(target) {
	let el = target;
	let at = target;
	for (; isElement(at); at = renderedParent(at)) if (at.getRootNode() === document && !at.contains(chromeRoot) && getComputedStyle(at).anchorScope === "all") el = renderedParent(at) ?? at;
	return el;
}
function anchorElement(target) {
	let el = outsideScopes(target);
	for (let host; !nameable(el) && (host = shadowHost(el.getRootNode()));) el = host;
	while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
	if (el !== target) return el;
	const [part] = shownParts(target);
	return part && part !== target ? part : target;
}
function anchorReaches(anchor, box) {
	const holder = anchorHolder(anchor);
	const host = hostIn(holder, document);
	if (!host) return false;
	const layer = nativeLayerHolding(holder);
	if (layer !== nativeLayerHolding(box)) return !layer;
	const order = host.compareDocumentPosition(box);
	return Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) && !(order & Node.DOCUMENT_POSITION_CONTAINED_BY);
}
function scrollsWith(node, box) {
	let at = node;
	for (; at !== box; at = renderedParent(at)) {
		if (!at) return false;
		if (isElement(at) && (!/^(static|relative)$/.test(getComputedStyle(at).position) || at !== node && scrollsContent(at))) return false;
	}
	return true;
}
function carriedAnchor(scroller, near = null) {
	if (anchorElement(scroller) !== scroller || nativeLayerHolding(scroller)) return null;
	const carried = (node) => isElement(node) && !/^(br|wbr)$/.test(node.localName) && anchorElement(node) === node && node.getClientRects().length > 0 && /^(static|relative)$/.test(getComputedStyle(node).position);
	if (!near) {
		for (const child of scroller.children) if (carried(child)) return child;
		return contentStart(scroller);
	}
	for (let before = near.previousSibling, after = near.nextSibling; before || after; before = before?.previousSibling ?? null, after = after?.nextSibling ?? null) for (const node of [before, after]) if (carried(node)) return node;
	return contentStart(scroller);
}
function anchorFor(context) {
	const physical = isElement(context) ? context : context?.parentElement;
	if (!physical) return null;
	const anchor = anchorElement(physical);
	if (context === physical || anchor !== physical || !scrollContainer(physical)) return anchor;
	return carriedAnchor(physical, context) ?? anchor;
}
const starts = /* @__PURE__ */ new WeakMap();
const START = "data-lf-content-start";
function contentStart(scroller) {
	if (!scroller.firstChild || [...scroller.childNodes].some((node) => node.nodeType !== Node.TEXT_NODE && !(isElement(node) && /^(br|wbr)$/.test(node.localName)))) return null;
	let handle = starts.get(scroller);
	if (!handle) {
		if (!CSS.supports("anchor-name", "attr(data-lf-content-start type(<custom-ident>))") || !/^(block|inline-block|flow-root|list-item)$/.test(getComputedStyle(scroller).display) || !/^(none|normal)$/.test(getComputedStyle(scroller, "::before").content) || getComputedStyle(scroller, "::first-letter").float !== "none") return null;
		handle = {
			scroller,
			name: nextName(),
			getBoundingClientRect() {
				const range = document.createRange();
				for (const lead of scroller.childNodes) {
					if (isText(lead)) {
						range.setStart(lead, 0);
						range.setEnd(lead, Math.min(1, lead.length));
					} else range.selectNode(lead);
					const [rect] = range.getClientRects();
					if (rect) return rect;
				}
				return range.getBoundingClientRect();
			}
		};
		starts.set(scroller, handle);
	}
	const { name } = handle;
	if (scroller.getRootNode() === document) keeps(scroller, START, name);
	else namePart(scroller, name, "::before");
	return handle;
}
const anchorHolder = (anchor) => isElement(anchor) ? anchor : anchor.scroller;
const anchorName = (el) => nameAnchor(anchorReading(el));
let dropsTransforms;
function anchorDropsTransforms() {
	if (dropsTransforms !== void 0) return dropsTransforms;
	const moved = document.createElement("div");
	const anchored = document.createElement("div");
	moved.style.cssText = "position: fixed; left: 0; top: 0; translate: 8px 0; anchor-name: --lf-moved";
	anchored.style.cssText = "position: fixed; top: 0; position-anchor: --lf-moved; left: anchor(left, 8px)";
	chromeRoot.append(moved, anchored);
	dropsTransforms = anchored.getBoundingClientRect().left < 4;
	moved.remove();
	anchored.remove();
	return dropsTransforms;
}
function laidOut(el) {
	const parent = el.offsetParent;
	let left = el.offsetLeft;
	let top = el.offsetTop;
	if (!parent) {
		if (getComputedStyle(el).position !== "fixed") return null;
		return {
			left,
			top
		};
	}
	if (parent === document.body && getComputedStyle(parent).position === "static") {
		left -= scrollX;
		top -= scrollY;
	} else {
		const from = parent.getBoundingClientRect();
		left += from.left + parent.clientLeft - parent.scrollLeft;
		top += from.top + parent.clientTop - parent.scrollTop;
	}
	for (let box = renderedParent(el); box !== parent; box = renderedParent(box)) {
		if (!isElement(box)) return null;
		left -= box.scrollLeft;
		top -= box.scrollTop;
	}
	return {
		left,
		top
	};
}
function movement(style) {
	const matrix = style.transform === "none" ? null : new window.DOMMatrixReadOnly(style.transform);
	return {
		moves: Boolean(matrix) || style.translate !== "none" || style.rotate !== "none" || style.scale !== "none" || style.offsetPath !== "none",
		slides: style.rotate === "none" && style.scale === "none" && (style.offsetPath === "none" || style.offsetRotate === "0deg") && (!matrix || matrix.is2D && matrix.a === 1 && matrix.b === 0 && matrix.c === 0 && matrix.d === 1)
	};
}
function translationOf(el) {
	let x = 0;
	let y = 0;
	let at = el;
	for (; isElement(at); at = renderedParent(at)) {
		const { moves, slides } = movement(getComputedStyle(at));
		if (!moves) continue;
		if (!slides || !isHTML(at) || at.currentCSSZoom !== 1) return null;
		const layout = laidOut(at);
		if (!layout) return null;
		const shown = at.getBoundingClientRect();
		x += shown.left - layout.left;
		y += shown.top - layout.top;
	}
	return {
		x,
		y
	};
}
function anchorBox(anchor) {
	const box = anchor.getBoundingClientRect();
	if (!anchorDropsTransforms()) return box;
	const shift = translationOf(anchorHolder(anchor));
	return shift && (shift.x || shift.y) ? new DOMRect(box.left - shift.x, box.top - shift.y, box.width, box.height) : box;
}
function anchorAt(node, anchor, box, at = anchor && anchorBox(anchor), visibility = "always") {
	const from = (side, length) => anchor ? `calc(anchor(${side}, -9999px) + ${layoutPx(length)})` : layoutPx(length);
	Object.assign(node.style, {
		position: "fixed",
		positionAnchor: anchor ? anchorName(anchor) : "",
		positionVisibility: anchor ? visibility : "",
		left: from("left", box.left - (at?.left ?? 0)),
		top: from("top", box.top - (at?.top ?? 0)),
		...box.right === void 0 ? {} : {
			width: layoutPx(box.right - box.left),
			height: layoutPx(box.bottom - box.top)
		}
	});
}
const cutPath = ({ x, y }, band) => {
	const open = 1e5;
	const width = band.right - band.left;
	const height = band.bottom - band.top;
	const edge = (value, side) => `calc(${layoutPx(value)} - var(--lf-paint-outset-${side}, 0px))`;
	return `inset(${edge(y ? 0 : -1e5, "top")} ${edge(-width - (x ? 0 : open), "right")} ${edge(-height - (y ? 0 : open), "bottom")} ${edge(x ? 0 : -1e5, "left")})`;
};
const nowhere = {
	left: 0,
	top: 0,
	right: 0,
	bottom: 0
};
function headerLevels(item, clips = /* @__PURE__ */ new Map()) {
	return headerCuts(item, clips).map(({ box, band }) => {
		const anchor = box === box.ownerDocument.scrollingElement ? null : anchorElement(box);
		const cut = {
			band: band ?? nowhere,
			axes: {
				x: false,
				y: true
			}
		};
		return anchor ? {
			...cut,
			anchor,
			reading: anchorReading(anchor),
			at: anchorBox(anchor)
		} : {
			...cut,
			anchor: null,
			reading: null,
			at: null
		};
	});
}
function cutFrames(levels, frames, make) {
	const remaining = [...frames];
	const placed = levels.toReversed().map((level) => ({
		level,
		frame: remaining.pop() ?? make()
	})).reverse();
	const chain = placed.map(({ frame }) => frame);
	const first = chain[0];
	const was = frames[0];
	if (first && was && first !== was && was.parentNode) move(was.parentNode, first, was);
	let parent = null;
	for (const frame of chain) {
		if (parent && frame.parentNode !== parent) move(parent, frame, null);
		parent = frame;
	}
	for (const dropped of remaining) dropped.remove();
	for (const { level: { anchor, band, axes, at, reading }, frame } of placed) {
		if (reading) nameAnchor(reading);
		anchorAt(frame, anchor, {
			left: band.left,
			top: band.top,
			right: band.left,
			bottom: band.top
		}, at);
		frame.style.clipPath = cutPath(axes, band);
	}
	return placed;
}
const views = /* @__PURE__ */ new Map();
const viewedNodes = /* @__PURE__ */ new WeakMap();
let viewObserver;
function refreshAnchorView(node) {
	const binding = viewedNodes.get(node);
	if (!binding) return;
	if (!binding.view) {
		resumeAnchorView(node);
		return;
	}
	const view = binding.view;
	const near = nearWindow(view.target);
	if (view.near === near) return;
	view.near = near;
	for (const notify of view.nodes.values()) notify();
}
function releaseAnchorView(node) {
	const binding = viewedNodes.get(node);
	const view = binding?.view;
	if (!view) return;
	binding.view = null;
	view.nodes.delete(node);
	if (!view.nodes.size) {
		view.observer.unobserve(view.target);
		views.delete(view.target);
	}
}
function resumeAnchorView(node) {
	const binding = viewedNodes.get(node);
	if (!binding || binding.view || !node.isConnected || !binding.target.isConnected) return;
	anchorView(node, binding.target, binding.changed);
	binding.changed();
}
function anchorView(node, target, changed) {
	let view = viewedNodes.get(node)?.view;
	if (view?.target === target) return view.near;
	releaseAnchorView(node);
	if (!target) return false;
	if (!viewObserver) {
		watchArrivals(".lf-anchor-view", ["class"], {
			arrive: resumeAnchorView,
			leave: releaseAnchorView
		});
		viewObserver = nearObserver((entries) => {
			for (const entry of entries) {
				const view = views.get(entry.target);
				if (!view) continue;
				const near = entry.isIntersecting && entry.target.checkVisibility();
				const changed = view.near !== near;
				view.near = near;
				for (const [node, notify] of view.nodes) {
					if (!node.isConnected || !entry.target.isConnected) {
						releaseAnchorView(node);
						continue;
					}
					if (changed) notify();
				}
			}
		});
	}
	view = views.get(target);
	if (!view) {
		view = {
			target,
			near: nearWindow(target),
			nodes: /* @__PURE__ */ new Map(),
			observer: viewObserver
		};
		views.set(target, view);
		viewObserver.observe(target);
	}
	view.nodes.set(node, changed);
	viewedNodes.set(node, {
		target,
		changed,
		view
	});
	if (!node.classList.contains("lf-anchor-view")) node.classList.add("lf-anchor-view");
	return view.near;
}

//#endregion
//#region runtime/target-paint-geometry.js
const SVG_NS = "http://www.w3.org/2000/svg";
const SHAPE_STROKE_ROOM = 2;
const paints = (shape, property) => {
	const style = getComputedStyle(shape);
	return shape.checkVisibility({
		opacityProperty: true,
		visibilityProperty: true
	}) && style[property] !== "none" && Number.parseFloat(style[`${property}Opacity`]) !== 0 && (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0);
};
function paintGeometry(surface) {
	if (!(surface instanceof SVGElement) || !surface.ownerSVGElement) return null;
	const geometry = [surface, ...surface.querySelectorAll("*")].filter((child) => child instanceof SVGGeometryElement);
	const fill = geometry.filter((shape) => paints(shape, "fill"));
	const paintedStroke = geometry.filter((shape) => paints(shape, "stroke"));
	const outlined = /* @__PURE__ */ new Set([...fill, ...paintedStroke]);
	const stroke = geometry.filter((shape) => outlined.has(shape));
	return fill.length || stroke.length ? {
		fill,
		stroke
	} : null;
}
function geometryClone(source, left, top, property) {
	const matrix = source.getScreenCTM();
	if (!matrix) return null;
	const clone = source.cloneNode(false);
	clone.removeAttribute("id");
	clone.removeAttribute("class");
	clone.removeAttribute("opacity");
	clone.removeAttribute("fill-opacity");
	clone.removeAttribute("stroke-opacity");
	clone.style.removeProperty("transform");
	clone.style.removeProperty("opacity");
	clone.style.removeProperty("fill-opacity");
	clone.style.removeProperty("stroke-opacity");
	for (const attribute of [...clone.attributes]) {
		const length = Reflect.get(source, attribute.localName);
		if (attribute.value.includes("%") && length instanceof SVGAnimatedLength) clone.setAttribute(attribute.name, String(length.animVal.value));
	}
	clone.setAttribute("transform", `matrix(${matrix.a} ${matrix.b} ${matrix.c} ${matrix.d} ${atLayoutPrecision(matrix.e - left)} ${atLayoutPrecision(matrix.f - top)})`);
	clone.style.setProperty("fill", property === "fill" ? "white" : "none", "important");
	clone.style.setProperty("stroke", property === "stroke" ? "var(--lf-shape-ink)" : "none", "important");
	clone.style.setProperty("stroke-width", "var(--lf-shape-stroke)", "important");
	clone.style.setProperty("stroke-dasharray", "var(--lf-shape-dash, none)", "important");
	clone.style.setProperty("stroke-linejoin", "round", "important");
	clone.style.setProperty("stroke-linecap", "round", "important");
	clone.style.setProperty("vector-effect", "non-scaling-stroke", "important");
	return clone;
}
function paintShape(host, geometry, { left, top, right, bottom }, options = {}) {
	if (!geometry) return false;
	const { maskId = "", veil = false } = options;
	const width = atLayoutPrecision(right - left);
	const height = atLayoutPrecision(bottom - top);
	const fill = [];
	const stroke = [];
	if (veil) for (const shape of geometry.fill) {
		const clone = geometryClone(shape, left, top, "fill");
		if (!clone) return false;
		fill.push(clone);
	}
	for (const shape of geometry.stroke) {
		const clone = geometryClone(shape, left, top, "stroke");
		if (!clone) return false;
		stroke.push(clone);
	}
	const paint = [];
	if (veil && fill.length) {
		const defs = document.createElementNS(SVG_NS, "defs");
		const mask = document.createElementNS(SVG_NS, "mask");
		mask.id = maskId;
		mask.setAttribute("maskUnits", "userSpaceOnUse");
		mask.setAttribute("x", "0");
		mask.setAttribute("y", "0");
		mask.setAttribute("width", String(width));
		mask.setAttribute("height", String(height));
		mask.style.maskType = "alpha";
		mask.append(...fill);
		defs.append(mask);
		const wash = document.createElementNS(SVG_NS, "rect");
		wash.setAttribute("width", String(width));
		wash.setAttribute("height", String(height));
		wash.setAttribute("fill", "var(--lf-shape-ink)");
		wash.setAttribute("fill-opacity", "0.08");
		wash.setAttribute("mask", `url(#${maskId})`);
		paint.push(defs, wash);
	}
	const outline = document.createElementNS(SVG_NS, "g");
	outline.append(...stroke);
	paint.push(outline);
	keeps(host, "viewBox", `0 0 ${width} ${height}`);
	keeps(host, "width", width);
	keeps(host, "height", height);
	const held = host.children;
	if (paint.length !== held.length || paint.some((node, index) => !node.isEqualNode(held.item(index)))) host.replaceChildren(...paint);
	return true;
}
function paintStand(box = null) {
	const root = document.createElement("div");
	root.className = "lf-ui lf-target-paint lf-paint-stand";
	root.setAttribute("aria-hidden", "true");
	root.style.position = "fixed";
	const carrier = document.createElement("div");
	carrier.className = "lf-paint-carrier";
	if (box) carrier.append(box);
	root.append(carrier);
	return {
		root,
		carrier,
		box,
		anchored: false,
		frames: []
	};
}
function anchoredBy(el, root) {
	const anchor = anchorElement(el);
	if (!anchorReaches(anchor, root)) return null;
	return anchor === el || scrollsWith(el, anchor) && !scrollsContent(anchor) || scrollsWith(anchor, el) ? anchor : null;
}
const makeFrame = () => {
	const frame = document.createElement("div");
	frame.className = "lf-paint-frame";
	return frame;
};
function standIn(stand, placed, anchored) {
	const { levels } = placed;
	const readings = levels.map((level) => ({
		...level,
		anchor: level.holder ? anchoredBy(level.holder, stand.root) : null
	}));
	anchored &&= readings.every(({ holder, anchor }) => !holder || anchor !== null);
	stand.anchored = anchored;
	stand.frames = cutFrames(readings.map(({ anchor, band, axes }) => ({
		anchor: anchored ? anchor : null,
		band,
		axes
	})), stand.frames.map(({ frame }) => frame), makeFrame);
	const outer = stand.frames[0]?.frame;
	if (outer && outer.parentNode !== stand.root) move(stand.root, outer, null);
	const inner = stand.frames.at(-1)?.frame ?? stand.root;
	if (stand.carrier.parentNode !== inner) move(inner, stand.carrier, null);
	const band = levels.at(-1)?.band;
	return anchored ? {
		anchored: true,
		origin: null
	} : {
		anchored: false,
		origin: {
			x: band?.left ?? 0,
			y: band?.top ?? 0
		}
	};
}
function standBox(box, rect, stood, anchor = null, at = anchor && anchorBox(anchor)) {
	if (stood.anchored) {
		anchorAt(box, anchor, rect, at, stood.visibility ?? "always");
		return;
	}
	Object.assign(box.style, {
		position: "",
		positionAnchor: "",
		positionVisibility: "",
		left: layoutPx(rect.left - stood.origin.x),
		top: layoutPx(rect.top - stood.origin.y),
		...rect.right === void 0 ? {} : {
			width: layoutPx(rect.right - rect.left),
			height: layoutPx(rect.bottom - rect.top)
		}
	});
}
function standOver(stand, placed, borderRadius) {
	const anchor = anchoredBy(placed.surface, stand.root);
	const at = anchor && anchorBox(anchor);
	const stood = standIn(stand, placed, Boolean(anchor));
	const style = stand.box.style;
	standBox(stand.box, placed.rect, stood, anchor, at);
	Object.assign(style, {
		display: "block",
		borderRadius
	});
	const band = token("--focus-ring-w");
	const outside = markGap(placed.surface);
	const gap = cramped(placed, band + outside) ? -band : outside;
	style.setProperty("--lf-mark-offset", layoutPx(gap));
	const room = Math.max(0, band + gap);
	for (const side of [
		"top",
		"right",
		"bottom",
		"left"
	]) stand.root.style.setProperty(`--lf-paint-outset-${side}`, layoutPx(cutsAt(placed, side) ? 0 : room));
	return {
		...stood,
		anchor,
		at,
		room
	};
}
const token = (name) => Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
function markGap(surface) {
	const style = getComputedStyle(surface);
	if (style.getPropertyValue("--lf-ring-at")) return Number.parseFloat(style.outlineOffset);
	return token(surface.matches(PRESSES) ? "--focus-ring-gap" : "--focus-region-gap");
}
function cutsAt({ rect, levels }, side) {
	const axis = side === "top" || side === "bottom" ? "y" : "x";
	const low = side === "top" || side === "left";
	return levels.some(({ band, axes }) => axes[axis] && (low ? rect[side] < band[side] : rect[side] > band[side]));
}
function cramped({ rect, levels, plane }, room) {
	const short = (band, low, high) => rect[low] >= band[low] && rect[low] - room < band[low] || rect[high] <= band[high] && rect[high] + room > band[high];
	const page = pageExtent(plane);
	return short(page, "left", "right") || short(page, "top", "bottom") || levels.some(({ holder, band, axes }) => holder && (axes.x && short(band, "left", "right") || axes.y && short(band, "top", "bottom")));
}
function pageExtent(plane) {
	const shown = layoutWindow();
	const root = document.scrollingElement;
	if (plane === "window" || !root) return shown;
	const style = getComputedStyle(root);
	const fixed = (overflow) => overflow === "hidden" || overflow === "clip";
	const [x, y] = [!fixed(style.overflowX), !fixed(style.overflowY)];
	return {
		left: x ? -root.scrollLeft : shown.left,
		top: y ? -root.scrollTop : shown.top,
		right: x ? root.scrollWidth - root.scrollLeft : shown.right,
		bottom: y ? root.scrollHeight - root.scrollTop : shown.bottom
	};
}
function paintSet(root, { onNear = () => {} } = {}) {
	const stands = /* @__PURE__ */ new Map();
	const entries = /* @__PURE__ */ new Map();
	const near = /* @__PURE__ */ new Set();
	const watched = /* @__PURE__ */ new Map();
	const watching = /* @__PURE__ */ new Map();
	const nearBy = (target) => !target || near.has(target);
	const view = nearObserver((records) => {
		const moved = /* @__PURE__ */ new Set();
		for (const { target: box, isIntersecting } of records) for (const target of watching.get(box) ?? []) {
			if (isIntersecting) near.add(target);
			else near.delete(target);
			moved.add(target);
		}
		for (const stand of stands.values()) if (stand.members.some(({ target }) => moved.has(target))) seat(stand);
		onNear();
	});
	const ids = /* @__PURE__ */ new WeakMap();
	let idCount = 0;
	const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
	const keyOf = ({ surface, levels }, anchor, plane, framed) => !surface ? `${plane}|window` : [
		plane,
		framed ? "cut" : "open",
		anchor ? "anchored" : "window",
		...levels.map(({ holder, band, from, axes }) => {
			const edges = [
				from.left,
				from.top,
				from.left + band.right - band.left
			];
			return `${holder ? idOf(holder) : "window"}:${[...edges, from.top + band.bottom - band.top]}:${axes.x}${axes.y}`;
		})
	].join("|");
	function seat(stand, all = false) {
		const { carrier, members } = stand;
		const seating = new Set(members.filter(({ node, target }) => nearBy(target) && (all || node.parentElement !== carrier)));
		const readings = [...seating].flatMap(({ entry }) => entry.anchor ? [anchorReading(entry.anchor)] : []);
		for (const reading of readings) nameAnchor(reading);
		let cursor = carrier.firstElementChild;
		for (const member of members) {
			const { node, target, entry } = member;
			if (!nearBy(target)) {
				if (node.parentElement !== carrier) continue;
				if (cursor === node) cursor = node.nextElementSibling;
				node.remove();
				continue;
			}
			if (cursor === node) cursor = node.nextElementSibling;
			else move(carrier, node, cursor);
			if (seating.has(member)) standBox(node, entry.rect, entry.stood, entry.anchor, entry.at);
		}
	}
	function place(items, clips = /* @__PURE__ */ new Map()) {
		const holders = /* @__PURE__ */ new Map();
		const targets = /* @__PURE__ */ new Set();
		const read = items.map((item) => {
			const { node, held = false, anchor, plane = "page" } = item;
			const { cut: framed = true } = item;
			if (!item.target) {
				const placed = {
					surface: null,
					levels: []
				};
				return {
					node,
					target: null,
					placed,
					rect: item.rect,
					plane,
					framed,
					anchor: null,
					at: null,
					key: keyOf(placed, null, plane, framed)
				};
			}
			const target = item.target;
			const rect = item.rect;
			targets.add(target);
			let placed = placement(target, false, false, clips, held);
			const { left, top, right, bottom } = placed.rect;
			if (!(right > left && bottom > top)) return {
				node,
				target,
				placed: null
			};
			const box = typeof rect === "function" ? rect(placed) : rect ?? placed.rect;
			if (!watched.has(target)) {
				const box = anchorElement(target);
				watched.set(target, box);
				let observed = watching.get(box);
				if (!observed) {
					observed = /* @__PURE__ */ new Set();
					watching.set(box, observed);
					view.observe(box);
				}
				observed.add(target);
				if (nearWindow(target, clips)) near.add(target);
			}
			const carriedBy = anchor === void 0 ? anchoredBy(target, root) : anchor && anchorReaches(anchor, root) ? anchor : null;
			if (!framed) placed = {
				...placed,
				levels: headerCuts(target, clips).map(({ box, band }) => ({
					holder: box === box.ownerDocument.scrollingElement ? null : box,
					band: band ?? {
						left: 0,
						top: 0,
						right: 0,
						bottom: 0
					},
					axes: {
						x: false,
						y: true
					}
				}))
			};
			const levels = placed.levels.map((level) => {
				let at;
				if (level.holder) {
					at = holders.get(level.holder);
					if (!at) {
						at = level.holder.getBoundingClientRect();
						holders.set(level.holder, at);
					}
				} else at = {
					left: 0,
					top: 0
				};
				return {
					...level,
					from: {
						left: level.band.left - at.left,
						top: level.band.top - at.top
					}
				};
			});
			const placedLevels = {
				...placed,
				levels
			};
			return {
				node,
				target,
				placed: placedLevels,
				rect: box,
				plane,
				framed,
				anchor: carriedBy,
				at: carriedBy && anchorBox(carriedBy),
				key: keyOf(placedLevels, carriedBy, plane, framed)
			};
		});
		for (const [target, box] of watched) if (!targets.has(target)) {
			watched.delete(target);
			near.delete(target);
			const observed = watching.get(box);
			observed?.delete(target);
			if (observed?.size) continue;
			watching.delete(box);
			view.unobserve(box);
		}
		const stood = /* @__PURE__ */ new Map();
		let previous = null;
		for (const item of read) {
			if (!item.placed) continue;
			const { placed, key, anchor, plane, framed } = item;
			if (stood.has(key)) continue;
			const stand = stands.get(key) ?? {
				...paintStand(),
				members: []
			};
			stands.set(key, stand);
			keeps(stand.root, "data-lf-paint-plane", plane);
			const next = previous ? previous.root.nextElementSibling : root.firstElementChild;
			if (next !== stand.root) move(root, stand.root, next);
			const how = standIn(stand, placed, Boolean(anchor));
			stood.set(key, {
				stand,
				how: {
					...how,
					visibility: framed ? "always" : "anchors-visible"
				}
			});
			previous = stand;
		}
		for (const [key, stand] of stands) if (!stood.has(key)) {
			dropStand(stand);
			stands.delete(key);
		}
		for (const stand of stands.values()) stand.members = [];
		const placing = /* @__PURE__ */ new Set();
		for (const item of read) {
			const { node, target } = item;
			placing.add(node);
			const standing = item.placed ? stood.get(item.key) : null;
			if (!item.placed || !standing) {
				node.remove();
				entries.set(node, null);
				continue;
			}
			const { stand, how } = standing;
			const { rect, anchor, at } = item;
			if (entries.get(node)?.stand !== stand) node.remove();
			const entry = {
				stand,
				stood: how,
				rect,
				anchor,
				at
			};
			entries.set(node, entry);
			stand.members.push({
				node,
				target,
				entry
			});
		}
		for (const node of entries.keys()) if (!placing.has(node)) {
			node.remove();
			entries.delete(node);
		}
		for (const stand of stands.values()) seat(stand, true);
		return read.map(({ placed }) => placed);
	}
	function clear() {
		for (const stand of stands.values()) dropStand(stand);
		for (const node of entries.keys()) node.remove();
		stands.clear();
		entries.clear();
		near.clear();
		watched.clear();
		watching.clear();
		view.disconnect();
	}
	return {
		place,
		clear,
		near: nearBy,
		stands: (node) => Boolean(entries.get(node)?.stand)
	};
}
function vacate(stand) {
	if (!stand.frames.length && stand.carrier.parentElement === stand.root) return;
	stand.frames = cutFrames([], stand.frames.map(({ frame }) => frame), makeFrame);
	move(stand.root, stand.carrier, null);
}
function dropStand(stand) {
	vacate(stand);
	stand.root.remove();
}
function placement(surface, shaped, aboveSurfaces, clips = /* @__PURE__ */ new Map(), held = false) {
	const box = shownBox(surface);
	const pad = shaped ? SHAPE_STROKE_ROOM : 0;
	const rect = {
		left: box.left - pad,
		top: box.top - pad,
		right: box.right + pad,
		bottom: box.bottom + pad
	};
	const cuts = paintClips(surface, rect, clips, aboveSurfaces, held);
	const levels = [];
	if (cuts.window) levels.push({
		band: cuts.window,
		axes: {
			x: true,
			y: true
		},
		holder: null
	});
	for (const { box: holder, band, axes } of cuts.bands) levels.push({
		band,
		axes,
		holder
	});
	let shown = rect;
	for (const { band, axes } of levels) shown = intersect(shown, band, axes);
	return {
		rect,
		shown: hasArea(shown) ? shown : null,
		shapeKey: `${rect.right - rect.left}:${rect.bottom - rect.top}`,
		levels,
		surface,
		plane: cuts.plane
	};
}

//#endregion
//#region runtime/target-paint.js
var target_paint_exports = /* @__PURE__ */ __exportAll({
	aimLayer: () => aimLayer,
	clearAim: () => clearAim,
	geometryChanged: () => geometryChanged,
	labelAim: () => labelAim,
	locationLayer: () => locationLayer,
	locationStandsDown: () => locationStandsDown,
	mountTargetPaint: () => mountTargetPaint,
	paintAim: () => paintAim,
	paintLocation: () => paintLocation,
	paintTrace: () => paintTrace,
	shifted: () => shifted,
	targetTraceLayer: () => targetTraceLayer
});
const targetTraceBox = el("div", "lf-ui lf-target-trace");
const aimBox = el("div", "lf-ui lf-aim");
const locationBox = el("div", "lf-ui lf-location");
const traceStand = paintStand(targetTraceBox);
const aimStand = paintStand(aimBox);
const locationStand = paintStand(locationBox);
const targetTraceLayer = traceStand.root;
const aimLayer = aimStand.root;
const locationLayer = locationStand.root;
const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
const targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
let aimed = null;
let traceElement = null;
let traceSurface = null;
let traceGeometry = null;
let traceShapeKey = "";
let placementFrame = 0;
let geometryFrame = 0;
let geometryDirty = false;
let locationElement = null;
let locationFrame = 0;
let locationProjected = [];
const PROJECTED_LOCATION = "lf-projected-location";
function clearAim() {
	aimed = null;
	vacate(aimStand);
	aimBox.style.display = "none";
	aimBox.classList.toggle("lf-shaped", false);
	aimShape.replaceChildren();
	aimBox.removeAttribute("data-for");
	delete aimStand.root.dataset.lfPaintPlane;
}
function paintAim(element, surface) {
	if (!element) {
		clearAim();
		return null;
	}
	surface ??= element;
	const geometry = surface && paintGeometry(surface);
	const placed = element && placement(surface, Boolean(geometry), inChrome(element));
	if (!placed?.shown) {
		clearAim();
		return null;
	}
	const shaped = paintShape(aimShape, geometry, placed.rect, {
		maskId: aimMaskId,
		veil: true
	});
	aimBox.classList.toggle("lf-shaped", shaped);
	if (!shaped) aimShape.replaceChildren();
	keeps(aimBox, "data-for", element.id);
	keeps(aimStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	const stood = standOver(aimStand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
	aimed = {
		placed: {
			...placed,
			shown: placed.shown
		},
		stood
	};
	return placed.shown;
}
function labelAim(node) {
	if (!aimed) return;
	const { placed: { rect, shown, levels }, stood } = aimed;
	const above = shown.top - node.offsetHeight - stood.room;
	const room = Math.max(0, ...levels.filter(({ axes }) => axes.y).map(({ band }) => band.top));
	const cutTop = shown.top > rect.top;
	const at = {
		left: Math.max(2, shown.left),
		top: !cutTop && above >= room ? above : shown.top + 2
	};
	const cut = cutTop ? aimStand.frames.findLast(({ level: { axes, band } }) => axes.y && band.top === shown.top) : shown.left > rect.left ? aimStand.frames.findLast(({ level: { axes, band } }) => axes.x && band.left === shown.left) : void 0;
	if (cut) {
		const { frame, level: { band } } = cut;
		if (node.parentElement !== frame) move(frame, node, null);
		standBox(node, at, {
			anchored: false,
			origin: {
				x: band.left,
				y: band.top
			}
		});
		return;
	}
	if (node.parentElement !== aimStand.carrier) move(aimStand.carrier, node, null);
	standBox(node, at, stood, stood.anchor, stood.at);
}
function clearTrace() {
	traceElement = null;
	traceSurface = null;
	traceGeometry = null;
	traceShapeKey = "";
	vacate(traceStand);
	targetTraceBox.style.display = "none";
	targetTraceBox.classList.toggle("lf-shaped", false);
	targetTraceShape.replaceChildren();
	targetTraceBox.removeAttribute("data-for");
	delete traceStand.root.dataset.lfPaintPlane;
}
function drawTrace(element = traceElement, surface = traceSurface, rebuildGeometry = true) {
	if (!(element instanceof Element) || !(surface instanceof Element) || !element.isConnected || !surface.isConnected) {
		clearTrace();
		return;
	}
	const changed = element !== traceElement || surface !== traceSurface;
	const geometry = changed || rebuildGeometry ? paintGeometry(surface) : traceGeometry;
	const placed = placement(surface, Boolean(geometry), inChrome(element));
	traceElement = element;
	traceSurface = surface;
	traceGeometry = geometry;
	if (!placed.shown) {
		targetTraceBox.style.display = "none";
		return;
	}
	const { rect, shapeKey } = placed;
	let shaped = Boolean(geometry);
	if (shaped && (changed || rebuildGeometry || shapeKey !== traceShapeKey)) shaped = paintShape(targetTraceShape, geometry, rect);
	if (!shaped) targetTraceShape.replaceChildren();
	traceShapeKey = shaped ? shapeKey : "";
	targetTraceBox.classList.toggle("lf-shaped", shaped);
	keeps(targetTraceBox, "data-for", element.id || null);
	keeps(traceStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	standOver(traceStand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
}
function paintTrace(element, surface = element) {
	if (!element) {
		clearTrace();
		return;
	}
	const rebuild = geometryDirty || element !== traceElement || surface !== traceSurface;
	if (geometryDirty) {
		if (geometryFrame) cancelRender(geometryFrame);
		if (placementFrame) cancelRender(placementFrame);
		geometryFrame = placementFrame = 0;
		geometryDirty = false;
	}
	drawTrace(element, surface, rebuild);
}
function shifted() {
	relocate();
	if (placementFrame || geometryFrame || !traceElement) return;
	placementFrame = nextRender(() => {
		placementFrame = 0;
		if (traceElement) drawTrace(traceElement, traceSurface, false);
	});
}
function geometryChanged() {
	relocate();
	geometryDirty = true;
	if (placementFrame) cancelRender(placementFrame);
	placementFrame = 0;
	if (geometryFrame || !traceElement) return;
	geometryFrame = nextRender(() => {
		geometryFrame = 0;
		if (!geometryDirty) return;
		geometryDirty = false;
		if (traceElement) drawTrace(traceElement, traceSurface, true);
	});
}
function paintLocation(element) {
	locationElement = element;
	drawLocation();
}
const locationStandsDown = (element) => getComputedStyle(element).getPropertyValue("--lf-obligation-ring").trim() === "none";
const paintsOver = (element) => {
	const layer = nativeLayerHolding(element);
	return !layer || layer === nativeLayerHolding(locationStand.root);
};
function drawLocation() {
	const element = locationElement;
	const placed = element?.isConnected && !locationStandsDown(element) && paintsOver(element) ? placement(element, false, inChrome(element)) : null;
	if (!element || !placed?.shown) {
		projectLocation([]);
		vacate(locationStand);
		locationBox.style.display = "none";
		locationBox.removeAttribute("data-for");
		delete locationStand.root.dataset.lfPaintPlane;
		return;
	}
	projectLocation([element, ...shownParts(element)]);
	keeps(locationBox, "data-for", element.id || null);
	keeps(locationStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	standOver(locationStand, placed, getComputedStyle(element).borderRadius);
}
function projectLocation(boxes) {
	for (const box of locationProjected) if (!boxes.includes(box)) box.classList.toggle(PROJECTED_LOCATION, false);
	for (const box of boxes) box.classList.toggle(PROJECTED_LOCATION, true);
	locationProjected = boxes;
}
function relocate() {
	if (locationFrame || !locationElement) return;
	locationFrame = nextRender(() => {
		locationFrame = 0;
		drawLocation();
	});
}
function mountTargetPaint() {
	aimBox.append(aimShape);
	targetTraceBox.append(targetTraceShape);
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
			if (locationStandsDown(box)) continue;
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
export { CARET_KEYS, COLLAPSE$1 as COLLAPSE, DATUM, DELIVERY, DISCLOSE, DISCLOSURE_SELECTOR, DRAFT_FORMAT, EVERYTHING, HOLDS_WORD, J, LAYOUT, LEAF_SURFACE, LENT_REACH_STOP, LINK, LIVE_ROOT, LayerRefused, LeafElement, LitElement$1 as LitElement, MODIFIER_KEYS, OUTPUT, PAGE_PAINT_ATTRIBUTE, PENDING, PENDING_TASK, PRESENTATION_DOM, PRESS, PRESSABLE, PRESSES, PendingTaskEvent, RUNTIME_PAINT_ATTRIBUTE, RequestError, SHARE_ROOT, SVG_NS, SourcePairs, TAB_STOP, TEXT_BLOCK, TEXT_BOX, TEXT_ENTRY, TEXT_FIELD, W, WALK, WEBSITE_DELIVERY, WORKS, Z, actionClass, actionElement, actionForWidget, actionIcon, actionName, actionTemplate, admitReading, admitResponse, adoptRegistry, advertisesKeys, afterScript, afterSettling, agentArrivalDuration, agentName, agentSays, aimLayer, aimedTop, alignInlineText, alignText, allBindings, alreadyShown, anchorBox, anchorElement, anchorFor, anchorKey, anchorName, anchorReading, anchorView, annotationMode, announce, announce$1, answers, applicationPresented, applicationPresenter, applicationRegionsPresented, applicationState, ariaShortcuts, assignRows, atLayoutPrecision, atScrollEnd, attachApplicationPresentation, attachDeferredLoader, attachWidgetPresentation, authored, authoredBody, authoredRank, authoredScope, axisTicks, backgroundFlash, bareReaction, beginWalk, bindQueuedWork, bindingEnabled, bindingEnabledFor, bindings, blockAt, blurFocused, bodyText, buttonCommand, byRenderedOrder, canPlaceFocus, cancelAnimation, cancelRender, canvas2D, caretAtKey, carriedAnchor, carriesObligation, checked, chosenSince, chromeForeground, chromeRoot, claimReleaseClick, claimsEsc, clamp, clampedRow, clippedContents, clippedPlace, clippedRect, clippingAxes, clipsPastSurfaces, closeControl, closeLayer, closeNativeLayer, closestAcross, coarsePointer, commandAvailable, commandBinding, commandDeclarationsWithin, commandEntries, commandPresentations, commandReady, commandRoutes, commandRun, commandScope, commandsChanged, commandsOn, commandsWithin, completeData, composedParentNode, contentRides, contextAround, contextBindings, contextScopes, controlAvailabilityOutput, countTraffic, coveredShare, createPresentationSchedule, currentLocationIn, currentLocationNodes, currentLocationTouches, cut, cutFrames, cycledRow, d, dataBody, dataHeaders, decisionControls, decisionFor, declarationFor, declareCommandReadiness, declareOccluder, declareReading, declareRelease, declareWindowChrome, declaredBindings, declaresCommandHandler, deepFocus, describeFailure, descriptionOf, disclosureAt, discussed, dismissError, dismissErrors, dismissPopoversOutside, documentChanged, dragHeld, dragging, drawingSchema, drawn$1 as drawn, dropStand, editable, el, elementById, elementDeclarations, elementDirective, elementFrame, elementFromPointAcross, elementOver, elementReading, elementsDeclaring, ensureSyntaxLanguage, errorsReading, eventSource, exceptionRecord, exceptionText, excerptWords, excludedByInert, exhibits, failSoft, failSoftUnreported, fencePassageParts, fileModelsPassage, findQuote, findText, fitsWhole, flashDuration, focusDestination, focusRevision, focused, foldBlock, foldDuration, foldWidgetStates, fragmentId, frameFor, frameView, frameVisibility, generated, generatedElement, growthAfterIsSeen, growthIsSeen, guard, handBack, hasArea, hasObligationSource, hasRows, headerCuts, headerInset, headerLevels, holdAuthoredBody, holdCurrentLocation, holdFocus, holdRendering, holdStatus, holdToRead, holdingError, hostIn, hoveringPointer, html$1 as html, iconElement, iconTemplate, inBaseLayer, inChrome, inUi, inWindowChrome, inlineStyle, inputCount, inputInFrame, installElementIntegration, installLayerStyleIntegration, installScrollerLookup, installStageIntegration, intersect, isCommandScope, isElement, isElementName, isHTML, isMessageEvent, isNativeLayer, isNews, isReaction, isText, isThreadEvent, itemNoun, itemOutcome, keeps, keepsHidden, keepsText, keyed, keys, labelOf, labelWords, landedBox, landingBand, landingInsets, landingRoom, langForPath, lastMovedAt, layerFact, layerHeaders, layerLanding, layerRoot, layoutBox, layoutChanged, layoutPx, layoutWindow, leafSays, leafSurface, letGo, listWalkPosition, live, live$1, liveEl, loadDeferred, loadShadowRules, locationLayer, marks, matchesWhen, measure, messageKey, motion, motionEasing, motionPlays, motionPreview, motionTime, mountRepaint, mountTargetPaint, move, moveScrollerBy, moved, nameAction, nameAnchor, nameable, namedAction, nativeActivationAt, nativeClaimAt, nativeFocusTarget, nativeLayerHolding, nativeLayers, nativeModalAdmits, nativePress, nearObserver, nearWindow, neighbourhood, nextAnimation, nextFrame, nextRender, noChange, nothing$1 as nothing, notice, noticeReading, noticeWords, obligationValue, observePreparations, observeQueuedWork, offer, offerAction, offerElement, offered, offeredAction, offeredActionElement, offlineData, offlineInteractive, offlineState, onCurrentLocation, onFrameVisibility, onLetGo, onMotionPreferenceChange, onPress, onPressAway, onUserInput, once, openLayer, openerOf, orderChildren, outputProducer, overlaps, overlapsAcross, pageBlocks, pageClaimed, pageDocument, pageParts, pagePresented, pageQueryAll, pageRange, pageReadingVersion, pageScroller, pageText, pageUpgraded, pageUrl, pageWords, paintClips, paintGeometry, paintKeys, paintKeysWithin, paintLocation, paintSet, paintShape, paintStand, paintTrace, parsed, passErrors, passErrorsAt, passOn, patchRetains, patchTree, placeBox, placeHolder, placeKept, placement, placesFailure, plainPress, playMotion, pointAt, pointerAt, postEvent, presentDocument, presented, pressHolds, pressIsKeyboardActivation, pressLed, pressRecords, pressing, programmaticSelection, projectCommandScope, projectView, projectionOrigins, projectionRegionsPresented, pruneScopedElements, publishOutput, q, queueWidgetUpdate, quickShortcuts, quoteFrom, raiseError, randomId, rangeOf, rankAt, reachedForWords, reactionsAt, readApplication, readApplicationPresentation, readCaret, readPart, readSampleVisibility, readingFrom, recentPlaceInput, recordInteraction, recordedWidgetSelector, recoveredLabelFocus, reducedMotion, ref, referencedCommandEntry, reflectFirstScopes, reflectKeys, refreshAnchorView, refuseOutput, registerVisualParts, registeredVisualPart, registeredVisualPartAt, registeredVisualPartLabel, registeredVisualParts, registrations, registry, relabel, release$1 as release, releaseFocus, releaseOutlets, removeRuntimeRootStyle, render$1 as render, renderRetired, renderedChildren, renderedOrder, renderedParent, renderedUnder, renderingState, repaint, repaintPage, repeat, reportCarried, reportFailure, reportPageError, requestJson, responseAction, restorePointer, restrictUserIntent, retainUserIntent, returnDuration, reveal, revealLayer, revealRegisteredVisualPart, revealsVisualParts, revisionLabel, rightCover, ringBox, roomPx, routedCommand, rove, rowArrows, runLanding, runtime, runtimeModule, runtimeResource, runtimeRootState, saidBy, sameAnchor, sameLayer, savedReadingSettled, saying, says, scopeAvailable, scopeIdentity, scopeRefs, scopesAt, scopesFor, scrollAxes, scrollBehavior, scrollChoices, scrollContainer, scrollGlides, scrollIntoReadingBand, scrollIntoView, scrollLimit, scrollToEnd, scrollersOf, scrolling, scrollsBy, scrollsContent, scrollsWith, searchField, seatRoot, seeErrors, seenRect, segmentBlock, segmentsIn, selectEnds, selectWidgets, selectableOffer, selectableOffered, selectionBackward, selectsAll, sentenceUnits, sessionIsActive, setChildLists, setChildren, setNoticeContext, setPresentationFailureReporter, setQuickShortcuts, setRegistration, setRenderedChildren, setRuntimeRootAttribute, setRuntimeRootStyle, setScroll, settledAway, shadowHost, shadowRootsIn, shadowRules, shadowStage, share, shareUrl, shellRight, showNativeLayer, shownBand, shownBox, shownExtent, shownParts, shownRect, shownWindow, showsContents, showsWords, sizeObserver, skipped, slotTop, spanIn, spell, spokenBinding, stackLevel, standOver, startsAt, stateSpecs, stopScroll, stuckBox, submitBindings, synNodes, syntax, syntaxLanguageNames, tabStops, tabStore, tagsDeclaring, takesLetters, targetTraceLayer, target_paint_exports, textNodesUnder, textUnits, textWidth, threadCounts, threadKey, threadNames, threadSurface, tick, titleOf, tokenChoices, tokenEntry, tokenLines, touchPresses, turns, typesText, uiInside, under, underOccluder, union, upFrom, updateSurface, uploadMedia, userScrollport, verbatimBoundaryIdentity, verbatimOwnerIdentity, visibleBand, visibleFocus, visualPartAdmission, visualPartProblems, visualViewport, voiceOf, voiced, walkPosition, walkPositionLabel, watchArrivals, watchCommandAvailability, watchCommandScopes, watchCurrentLocationIn, watchFrame, watchLayerChanges, watchOwner, watchPassageRoot, watchPendingTraffic, watchPresentation, watchRoom, watchScrollEnds, watchScrolls, watchSemantic, wearsLentStop, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whenLeft, whenNone, whenWidgetsPresented, whileConnected, windowChromeBoxes, word, wordsText, worksInside, wrote, x$1 as x };