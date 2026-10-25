import { AsyncDirective, Directive, LitElement, PartType, classMap, createRef, directive, guard, html, keyed, live, noChange, nothing, ref, render, repeat, styleMap, unsafeHTML } from "/vendor/lit.js";

//#region runtime/queued-work.js
const jobObservers = /* @__PURE__ */ new Set();
const jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
	jobObservers.add(observer);
	return () => jobObservers.delete(observer);
}
const announce = (phase, job, observers) => {
	for (const observer of observers) observer(phase, job);
};
function enqueueWork(callback) {
	const job = Object.freeze({ callback });
	const observers = [...jobObservers];
	jobCohorts.set(job, observers);
	announce("enqueue", job, observers);
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
		announce("run", job, observers);
		return callback(...args);
	} finally {
		announce("finish", job, observers);
	}
}
function bindQueuedWork(callback) {
	const job = enqueueWork(callback);
	return (...args) => runWork(job, ...args);
}
function cancelWork(job) {
	const observers = claim(job);
	if (observers) announce("cancel", job, observers);
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
		const { width, height } = entries.at(-1).intersectionRect;
		intersecting = width > 0 && height > 0;
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
const owners = [];
if (!child) for (let view = window; view.frameElement; view = view.parent) owners.push(watchFrame(view.frameElement, publish$1));
function frameVisibility() {
	if (child) return { visible: admitted };
	if (owners.length) return { visible: owners.every((owner) => owner.shown()) };
	return null;
}
function onFrameVisibility(callback) {
	observers.add(callback);
	return () => observers.delete(callback);
}
function readSampleVisibility() {
	if (!child) return null;
	return new Promise((resolve, reject) => {
		const id = ++readingId;
		readings$1.set(id, {
			resolve,
			reject
		});
		child.send({
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
		if (detail.error) reading?.reject(Object.assign(new Error(detail.error.message), { stack: void 0 }, detail.error));
		else reading?.resolve(detail);
		return;
	}
	if (type !== "visibility") return;
	admitted = detail.visible;
	publish$1();
});
addEventListener("pagehide", (event) => {
	if (!event.persisted) for (const owner of owners) owner.stop();
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
	for (const queue of [
		queued,
		afterPaint,
		running
	]) {
		const job = queue?.get(id);
		if (!job) continue;
		queue.delete(id);
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
function sizeObserver(callback, { counted = true } = {}) {
	return new ResizeObserver((entries, observer) => {
		if (counted) {
			heard = true;
			unsettle();
		}
		callback(entries, observer);
	});
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
	if (visibility.visible) unsettle();
});
unsettle();

//#endregion
//#region vendor/browser-runtime/signals-core.js
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
//#region vendor/browser-runtime/snapshot.js
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
//#region runtime/event-kinds.js
const MESSAGE_KINDS = /* @__PURE__ */ new Set(["comment", "reply"]);
const VERB_WRITERS = {
	"action": "user",
	"report": "agent"
};

//#endregion
//#region runtime/names.js
const WIDGET_NAME = /* @__PURE__ */ new RegExp("^lf-[a-z0-9]+(?:-[a-z0-9]+)*$");

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
function threadCounts(threads) {
	const listed = threads.filter(discussed);
	return {
		open: listed.filter((thread) => !thread.resolved).length,
		unread: listed.filter(hasUnread).length
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
		msgs: thread.msgs.filter((message) => !withdrawn.has(message.id))
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
const itemOutcome = (item) => item.kind === "update" ? "Sent" : OUTCOMES[item.state] ?? item.state;

//#endregion
//#region vendor/browser-runtime/application.js
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
				memberships.get(parent)[attr].push(id);
				break;
			}
		}
		for (const { e, unit, spec } of projection.desired.values()) if (spec.creates && named.has(e.widget) && !document.descriptors.has(unit)) memberships.get(e.widget)[attr].push(unit);
		for (const owner of named) memberships.get(owner)[attr].sort();
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
				if (inputs && keys.every((key) => next[key] === inputs[key])) return reading;
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
//#region vendor/browser-runtime/presentation.js
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
//#region runtime/shadow-tree.js
const shadowHost = (root) => root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? root.host ?? null : null;
const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
const renderedParent = (node) => node?.assignedSlot ?? upFrom(node);
const composedParentNode = (node) => node.parentNode ?? shadowHost(node);
const renderedParentNode = (node) => node.assignedSlot ?? composedParentNode(node);
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
	if (index === left.length || index === right.length) return left.length - right.length;
	return left[index].compareDocumentPosition(right[index]) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}
const byRenderedOrder = (items, placeOfItem) => {
	const placed = items.map((item) => ({
		item,
		place: placeOfItem(item)
	}));
	return [...placed.filter(({ place }) => place).sort((a, b) => renderedOrder(a.place, b.place)), ...placed.filter(({ place }) => !place)].map(({ item }) => item);
};
const nativeLayerKind = (node) => {
	if (node?.nodeType !== Node.ELEMENT_NODE || !node.isConnected) return null;
	if (node.matches("dialog:modal")) return "modal";
	return node.matches(":popover-open") ? "popover" : null;
};
const isNativeLayer = (node) => nativeLayerKind(node) !== null;
function nativeLayerHolding(node) {
	for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
	return null;
}

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
const canPlaceFocus = () => !document.documentElement.lfSample || document.hasFocus();
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
function markFocus(node, name, present) {
	keeps(node, `data-lf-${name}`, present ? "" : null);
	if (!present) {
		if (node.part?.contains(`lf-${name}`)) node.part.remove(`lf-${name}`);
	} else if (node.getRootNode().nodeType === Node.DOCUMENT_FRAGMENT_NODE && node.hasAttribute("part")) node.part.add(`lf-${name}`);
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
	const visible = next && (next.matches(":focus-visible") || next.matches(TEXT_BOX)) ? next : null;
	if (visible !== paintedVisible) {
		if (paintedVisible) markFocus(paintedVisible, "focus-visible", false);
		if (visible) markFocus(visible, "focus-visible", true);
		paintedVisible = visible;
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
	if (event.relatedTarget !== null) {
		departed = true;
		return;
	}
	const left = event.composedPath()[0];
	lastLocation = new WeakRef(left);
	if (restoring) return;
	queueMicrotask(() => {
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
	const at = deepFocus();
	if (!at || at === document.body || at === published?.deref()) return;
	placements += 1;
	lastLocation = new WeakRef(at);
	const was = [stepping, pressedPath];
	[stepping, pressedPath] = [step, pressed];
	try {
		publish(at, cause(at));
	} finally {
		[stepping, pressedPath] = was;
	}
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
const drawn = (node) => node?.isConnected && node.checkVisibility({ visibilityProperty: true });
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
function letGo() {
	letGoes++;
	const block = readingBlock();
	if (!block?.isConnected) {
		releaseFocus();
		return;
	}
	focusDestination(block, "move");
	block.blur();
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
export { AsyncDirective, CARET_KEYS, Directive, J, LENT_REACH_STOP, LitElement, MODIFIER_KEYS, PENDING, PRESSES, PartType, TAB_STOP, TEXT_BOX, TEXT_FIELD, W, WORKS, Z, actionForWidget, afterScript, afterSettling, anchorKey, atLayoutPrecision, authoredRank, bareReaction, bindQueuedWork, byRenderedOrder, canPlaceFocus, cancelAnimation, cancelRender, caretAtKey, carriedFrom, carriesObligation, classMap, closeLayer, composedParentNode, controlNavigationKeys, createPresentationCoordinator, createPresentationSchedule, createRef, createSemanticApplication, currentLocationIn, currentLocationNodes, currentLocationTouches, d, declareReading, declareRelease, deepFocus, describeFailure, directive, discussed, drawn, editable, focusDestination, focusRevision, focused, foldWidgetStates, frameVisibility, guard, handBack, hasUnread, holdCurrentLocation, holdFocus, holdRendering, html, inputCount, isElementName, isMessageEvent, isNativeLayer, isReaction, isThreadEvent, itemNoun, itemOutcome, keeps, keepsHidden, keepsText, keyed, lastMovedAt, layerLanding, layoutPx, letGo, live, messageKey, move, moved, nativeLayerHolding, nativeLayerKind, nextAnimation, nextFrame, nextRender, noChange, nothing, obligationValue, observePreparations, observeQueuedWork, onCurrentLocation, onFrameVisibility, onPress, onPressAway, onUserInput, openLayer, openerOf, pendingForParent, pressLed, pressing, projectionOrigins, q, rankAt, reactionsAt, readCaret, readSampleVisibility, recentPlaceInput, recoveredLabelFocus, ref, release, releaseFocus, render, renderedOrder, renderedParent, renderedUnder, renderingState, repeat, ringBox, roomPx, rove, sameAnchor, seatRoot, selectsAll, shadowHost, share, sizeObserver, stateCoordinate, styleMap, tabStops, takesLetters, threadCounts, threadKey, threadNames, tokenChoices, turns, typesText, under, unsafeHTML, upFrom, watchCurrentLocationIn, watchFrame, wearsLentStop, whenLeft, x };