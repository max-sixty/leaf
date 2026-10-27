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
export { J, W, Z, bindQueuedWork, cancelWork, d, enqueueWork, observeQueuedWork, q, runWork, x };