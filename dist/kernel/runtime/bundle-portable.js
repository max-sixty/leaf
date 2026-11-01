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
const readings = /* @__PURE__ */ new Map();
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
if (!child) for (; containingView.frameElement; containingView = containingView.parent) owners$1.push(watchFrame(containingView.frameElement, publish));
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
		readings.set(id, {
			resolve,
			reject
		});
		bridge.send({
			type: "visibility-read",
			detail: { id }
		});
	});
}
function publish() {
	const visibility = frameVisibility();
	for (const callback of observers) callback(visibility);
}
if (child) child.receive(({ type, detail }) => {
	if (type === "visibility-reading") {
		const reading = readings.get(detail.id);
		readings.delete(detail.id);
		if ("error" in detail) reading?.reject(Object.assign(new Error(detail.error.message), { stack: void 0 }, detail.error));
		else reading?.resolve(detail);
		return;
	}
	if (type !== "visibility") return;
	admitted = detail.visible;
	publish();
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
const watches = /* @__PURE__ */ new Set();
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
	watches.add(watch);
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
	for (const watch of watches) enroll(watch, stage);
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
const namedAction = (action) => {
	const named = ACTIONS[action];
	if (!named) throw new TypeError(`Unknown Leaf action: ${action}`);
	return named;
};
const actionIcon = (action) => namedAction(action).icon;
const actionName = (action) => namedAction(action).name;
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
	integration$1?.(root);
	return root;
}
function shadowStage(host, nodes) {
	const root = host.shadowRoot ?? stageFor(host);
	watchArrivalsIn(root);
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
	open: (node) => registrations.get(owner)?.handle.open(node) ?? false
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
export { ANNOUNCE, COMMANDS, J, LAYOUT, LeafElement, OUTPUT, PAGE_PAINT_ATTRIBUTE, PENDING_TASK, PendingTaskEvent, ROLE_BUTTON_OFFER, RUNTIME_PAINT_ATTRIBUTE, SourcePairs, W, Z, actionClass, actionElement, actionIcon, actionName, actionTemplate, afterScript, afterSettling, agentArrivalDuration, announce, assignRows, atLayoutPrecision, attachDeferredLoader, axisTicks, backgroundFlash, bindQueuedWork, bodyText, byRenderedOrder, cancelAnimation, cancelRender, canvas2D, commandsChanged, commandsChangedOn, composedParentNode, d, dataBody, describeFailure, elementBox, elementDirective, ensureSyntaxLanguage, exceptionRecord, exceptionText, excludedByInert, failSoft, failSoftUnreported, failureContext, failureOf, flashDuration, foldBlock, foldDuration, frameFor, frameVisibility, generated, generatedElement, holdRendering, iconElement, iconTemplate, inBaseLayer, inlineStyle, installElementIntegration, installMoveFocus, installStageIntegration, isElement, isHTML, isNativeLayer, isNode, isStage, isText, keeps, keepsHidden, keepsText, layoutChanged, layoutPx, liveStages, loadDeferred, measure, motion, motionEasing, motionPlays, motionTime, move, nativeLayerHolding, nativeLayerKind, nextAnimation, nextFrame, nextRender, observePreparations, observeQueuedWork, offer, offerAction, offerElement, offered, offeredAction, offeredActionElement, onFrameVisibility, onMotionPreferenceChange, once, orderChildren, outputProducer, pagePresented, pageUpgraded, patchRetains, patchTree, placesFailure, playMotion, publishOutput, q, readSampleVisibility, reducedMotion, refuseCommands, refuseOutput, registerVisualParts, registeredVisualPart, registeredVisualPartAt, registeredVisualPartLabel, registeredVisualParts, registrations, releaseOutlets, renderedOrder, renderedParent, renderedUnder, renderingState, reportFailure, returnDuration, revealRegisteredVisualPart, revealsVisualParts, roomPx, scrollBehavior, scrollGlides, scrolling, selectableOffer, selectableOffered, setChildLists, setChildren, setRenderedChildren, setScroll, shadowHost, shadowStage, showAction, sizeObserver, skipped, synNodes, syntax, syntaxLanguageNames, tabStore, textWidth, threadSurface, tokenLines, under, upFrom, updateSurface, visualPartAdmission, visualPartProblems, watchArrivals, watchFrame, watchOwner, watchScrollEnds, watchScrolls, whileConnected, x };