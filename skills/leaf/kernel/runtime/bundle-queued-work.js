// runtime/queued-work.js
var jobObservers = /* @__PURE__ */ new Set();
var jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
  jobObservers.add(observer);
  return () => jobObservers.delete(observer);
}
var announce = (phase, job) => {
  for (const observer of jobCohorts.get(job)) observer(phase, job);
};
function enqueueWork(callback) {
  const job = Object.freeze({ callback });
  jobCohorts.set(job, [...jobObservers]);
  announce("enqueue", job);
  return job;
}
function runWork(job, ...args) {
  const callback = job.callback;
  try {
    announce("run", job);
    return callback(...args);
  } finally {
    announce("finish", job);
  }
}
function bindQueuedWork(callback) {
  const job = enqueueWork(callback);
  return (...args) => runWork(job, ...args);
}
var cancelWork = (job) => announce("cancel", job);

// vendor/browser-runtime/signals-core.js
var j = /* @__PURE__ */ Symbol.for("preact-signals");
function S() {
  if (v > 1) v--;
  else {
    var t, i = false;
    for ((function() {
      var f = p;
      for (p = void 0; f !== void 0; ) {
        var w = f.S;
        if (w.v === f.v) for (var a = w.t; a !== void 0; a = a.x) a.i === f.i && (a.i = w.i);
        f = f.o;
      }
    })(); c !== void 0; ) {
      var o = c;
      for (c = void 0, l++; o !== void 0; ) {
        var r = o.u;
        if (o.u = void 0, o.f &= -3, !(8 & o.f) && g(o)) try {
          o.c();
        } catch (f) {
          i || (t = f, i = true);
        }
        o = r;
      }
    }
    if (l = 0, v--, i) throw t;
  }
}
var e;
var n = void 0;
function d(t) {
  var i = n, o = e;
  n = void 0, e = void 0;
  try {
    return t();
  } finally {
    n = i, e = o;
  }
}
var c = void 0;
var v = 0;
var l = 0;
var m = 0;
var p = void 0;
var y = 0;
function x(t) {
  if (n !== void 0) {
    var i = t.n;
    if (i === void 0 || i.t !== n) return i = { i: 0, S: t, p: n.s, n: void 0, t: n, e: void 0, x: void 0, r: i }, n.s !== void 0 && (n.s.n = i), n.s = i, t.n = i, 32 & n.f && t.S(i), i;
    if (i.i === -1) return i.i = 0, i.n !== void 0 && (i.n.p = i.p, i.p !== void 0 && (i.p.n = i.n), i.p = n.s, i.n = void 0, n.s.n = i, n.s = i), i;
  }
}
function s(t, i) {
  this.v = t, this.i = 0, this.n = void 0, this.t = void 0, this.l = 0, this.W = i?.watched, this.Z = i?.unwatched, this.name = i?.name;
}
s.prototype.brand = j;
s.prototype.h = function() {
  return true;
};
s.prototype.S = function(t) {
  var i = this, o = this.t;
  o !== t && t.e === void 0 && (t.x = o, this.t = t, o !== void 0 ? o.e = t : d(function() {
    var r;
    (r = i.W) == null || r.call(i);
  }));
};
s.prototype.U = function(t) {
  var i = this;
  if (this.t !== void 0) {
    var o = t.e, r = t.x;
    o !== void 0 && (o.x = r, t.e = void 0), r !== void 0 && (r.e = o, t.x = void 0), t === this.t && (this.t = r, r === void 0 && d(function() {
      var f;
      (f = i.Z) == null || f.call(i);
    }));
  }
};
s.prototype.subscribe = function(t) {
  var i = this;
  return Z(function() {
    var o = i.value;
    d(function() {
      return t(o);
    });
  }, { name: "sub" });
};
s.prototype.valueOf = function() {
  return this.value;
};
s.prototype.toString = function() {
  return this.value + "";
};
s.prototype.toJSON = function() {
  return this.value;
};
s.prototype.peek = function() {
  var t = this;
  return d(function() {
    return t.value;
  });
};
Object.defineProperty(s.prototype, "value", { get: function() {
  var t = x(this);
  return t !== void 0 && (t.i = this.i), this.v;
}, set: function(t) {
  if (t !== this.v) {
    if (l > 100) throw new Error("Cycle detected");
    (function(o) {
      v !== 0 && l === 0 && o.l !== m && (o.l = m, p = { S: o, v: o.v, i: o.i, o: p });
    })(this), this.v = t, this.i++, y++, v++;
    try {
      for (var i = this.t; i !== void 0; i = i.x) i.t.N();
    } finally {
      S();
    }
  }
} });
function M(t, i) {
  return new s(t, i);
}
function g(t) {
  for (var i = t.s; i !== void 0; i = i.n) if (i.S.i !== i.i || !i.S.h() || i.S.i !== i.i) return true;
  return false;
}
function E(t) {
  for (var i = t.s; i !== void 0; i = i.n) {
    var o = i.S.n;
    if (o !== void 0 && (i.r = o), i.S.n = i, i.i = -1, i.n === void 0) {
      t.s = i;
      break;
    }
  }
}
function O(t) {
  for (var i = t.s, o = void 0; i !== void 0; ) {
    var r = i.p;
    i.i === -1 ? (i.S.U(i), r !== void 0 && (r.n = i.n), i.n !== void 0 && (i.n.p = r)) : o = i, i.S.n = i.r, i.r !== void 0 && (i.r = void 0), i = r;
  }
  t.s = o;
}
function h(t, i) {
  s.call(this, void 0, i), this.x = t, this.s = void 0, this.g = y - 1, this.f = 4;
}
h.prototype = new s();
h.prototype.h = function() {
  if (this.f &= -3, 1 & this.f) return false;
  if ((36 & this.f) == 32 || (this.f &= -5, this.g === y)) return true;
  if (this.g = y, this.f |= 1, this.i > 0 && !g(this)) return this.f &= -2, true;
  var t = n;
  try {
    E(this), n = this;
    var i = this.x();
    (16 & this.f || this.v !== i || this.i === 0) && (this.v = i, this.f &= -17, this.i++);
  } catch (o) {
    this.v = o, this.f |= 16, this.i++;
  }
  return n = t, O(this), this.f &= -2, true;
};
h.prototype.S = function(t) {
  if (this.t === void 0) {
    this.f |= 36;
    for (var i = this.s; i !== void 0; i = i.n) i.S.S(i);
  }
  s.prototype.S.call(this, t);
};
h.prototype.U = function(t) {
  if (this.t !== void 0 && (s.prototype.U.call(this, t), this.t === void 0)) {
    this.f &= -33;
    for (var i = this.s; i !== void 0; i = i.n) i.S.U(i);
  }
};
h.prototype.N = function() {
  if (!(2 & this.f)) {
    this.f |= 6;
    for (var t = this.t; t !== void 0; t = t.x) t.t.N();
  }
};
Object.defineProperty(h.prototype, "value", { get: function() {
  if (1 & this.f) throw new Error("Cycle detected");
  var t = x(this);
  if (this.h(), t !== void 0 && (t.i = this.i), 16 & this.f) throw this.v;
  return this.v;
} });
function T(t, i) {
  return new h(t, i);
}
function U(t) {
  var i = t.m;
  if (t.m = void 0, typeof i == "function") {
    v++;
    var o = n;
    n = void 0;
    try {
      i();
    } catch (r) {
      throw t.f &= -2, t.f |= 8, b(t), r;
    } finally {
      n = o, S();
    }
  }
}
function b(t) {
  for (var i = t.s; i !== void 0; i = i.n) i.S.U(i);
  t.x = void 0, t.s = void 0, U(t);
}
function W(t) {
  if (n !== this) throw new Error("Out-of-order effect");
  O(this), n = t, this.f &= -2, 8 & this.f && b(this), S();
}
function u(t, i) {
  this.x = t, this.m = void 0, this.s = void 0, this.u = void 0, this.f = 32, this.name = i?.name, e && e.push(this);
}
u.prototype.c = function() {
  var t = this.S();
  try {
    if (8 & this.f || this.x === void 0) return;
    var i = this.x();
    typeof i == "function" && (this.m = i);
  } finally {
    t();
  }
};
u.prototype.S = function() {
  if (1 & this.f) throw new Error("Cycle detected");
  this.f |= 1, this.f &= -9, U(this), E(this), v++;
  var t = n;
  return n = this, W.bind(this, t);
};
u.prototype.N = function() {
  2 & this.f || (this.f |= 2, this.u = c, c = this);
};
u.prototype.d = function() {
  this.f |= 8, 1 & this.f || b(this);
};
u.prototype.dispose = function() {
  this.d();
};
function Z(t, i) {
  var o = new u(t, i);
  try {
    o.c();
  } catch (f) {
    throw o.d(), f;
  }
  var r = o.d.bind(o);
  return r[Symbol.dispose] = r, r;
}

// runtime/projection/model.js
var stateCoordinate = (owner, unit, verb) => JSON.stringify([owner, unit, verb]);
var coordinateOf = (key) => JSON.parse(key);
function foldedValue(event, record) {
  const value = event.detail.value;
  if (record.kind === "attribute" && Array.isArray(value)) return value.toSorted();
  return value ?? null;
}
var sameValue = (a, b2) => JSON.stringify(a) === JSON.stringify(b2);
var compareProjected = (a, b2) => {
  const aLogged = Number.isInteger(a.e.seq);
  const bLogged = Number.isInteger(b2.e.seq);
  if (aLogged && bLogged) return (a.e.seq ?? 0) - (b2.e.seq ?? 0);
  if (aLogged) return -1;
  if (bLogged) return 1;
  return (a.localOrder ?? 0) - (b2.localOrder ?? 0);
};
function foldProjection({
  entries = [],
  actionIds = [],
  reportIds = [],
  desiredIds = [],
  coverage = [],
  pendingEntries = []
} = {}) {
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
    const e2 = record.event;
    if (e2.kind === "undo" || classified.has(e2.id)) continue;
    classified.set(e2.id, { e: e2, terminal: record.coordinate === null });
  }
  const pendingActions = [];
  const withdrawn = /* @__PURE__ */ new Set();
  const recompute = (coordinate) => {
    const local = pendingActions.filter((entry) => entry.coordinate === coordinate && !withdrawn.has(entry.e.id)).at(-1);
    const durable = [...classified.values()].filter(
      /** @returns {entry is ProjectionEntry} */
      (entry) => Boolean(
        entry.stands && entry.coordinate === coordinate && !withdrawn.has(entry.e.id)
      )
    ).sort(compareProjected).at(-1);
    const action = local ?? durable;
    for (const view of [actions, desired])
      if (action) view.set(coordinate, action);
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
  return { actions, reports, classified, desired, pendingWithdrawals };
}
var authoredValue = (authoredSnapshots, { unit, e: { widget: owner, action: verb } }) => {
  const authored = authoredSnapshots.get(owner);
  if (!authored) return void 0;
  const spec = authored.specs.get(verb);
  const state = authored.state[verb];
  if (!spec || !state) throw new Error(`Missing authored state for ${owner}/${verb}`);
  const record = spec.record;
  const value = state.value;
  if (record?.kind === "position" && "units" in state)
    return Object.keys(state.value).find(
      (container) => state.value[container]?.includes(unit)
    ) ?? null;
  return value;
};
function projectionOrigins(authoredSnapshots, projection) {
  const origins = /* @__PURE__ */ new Map();
  const add = (origin, unit) => {
    const key = `${origin}:${unit}`;
    if (!origins.has(key)) origins.set(key, { origin, unit });
  };
  for (const entry of projection.classified.values())
    for (const unit of entry.restated ?? []) add("restated", unit);
  for (const entry of projection.desired.values()) {
    const { unit, e: e2, spec, value } = entry;
    const overridesSource = spec.record ? !sameValue(value, authoredValue(authoredSnapshots, entry)) : true;
    if (!overridesSource) continue;
    add(e2.kind === "action" ? "user" : "reported", unit);
  }
  return [...origins.values()];
}
var DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";
var authoredRank = (index) => "z".repeat(Math.floor(index / 35)) + DIGITS.charAt(index % 35 + 1);
var byRank = (ranks) => (
  /** @param {string} a @param {string} b */
  (a, b2) => {
    const left = ranks[a];
    const right = ranks[b2];
    if (left !== void 0 && right !== void 0 && left !== right)
      return left < right ? -1 : 1;
    return a < b2 ? -1 : a > b2 ? 1 : 0;
  }
);
function rankBetween(before, after) {
  if (after === null) return before ? rankAfter(before) : "i";
  if (!before) return rankBefore(after);
  if (before >= after) return before;
  return midpoint(before, after);
}
function rankAfter(key) {
  const digit = DIGITS.indexOf(key.charAt(0));
  if (digit < DIGITS.length - 1) return DIGITS.charAt(digit + 1);
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
    let n2 = 0;
    while ((before[n2] ?? "0") === after[n2]) n2 += 1;
    if (n2 > 0) return after.slice(0, n2) + midpoint(before.slice(n2), after.slice(n2));
  }
  const low = before ? DIGITS.indexOf(before.charAt(0)) : 0;
  const high = after !== null ? DIGITS.indexOf(after.charAt(0)) : DIGITS.length;
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
  return rankBetween(
    before ? ranks[before] ?? "" : "",
    after ? ranks[after] ?? null : null
  );
}
function foldWidgetStates(authoredSnapshots, projection) {
  const copyState = (state) => (
    /** @type {import("../../../../../build/browser/domain.ts").AuthoredWidget["state"]} */
    structuredClone(state)
  );
  const states = new Map(
    [...authoredSnapshots].map(([id, authored]) => [
      id,
      {
        state: copyState(authored.state),
        entries: [],
        specs: authored.specs
      }
    ])
  );
  const place = ({ value: containers, ranks }, unit, detail) => {
    if (typeof detail.value !== "string" || typeof detail.rank !== "string") return;
    const destination = containers[detail.value];
    if (!destination || !Object.values(containers).some((ids) => ids.includes(unit)))
      return;
    for (const ids of Object.values(containers)) {
      const index = ids.indexOf(unit);
      if (index >= 0) ids.splice(index, 1);
    }
    destination.push(unit);
    ranks[unit] = detail.rank;
  };
  for (const entry of [...projection.desired.values()].sort(compareProjected)) {
    const owner = states.get(entry.e.widget);
    if (!owner) continue;
    const { spec, e: e2, unit } = entry;
    const record = spec.record;
    const value = record ? structuredClone(e2.detail.value) : e2.action;
    const current = { action: e2.action, value, detail: structuredClone(e2.detail) };
    owner.entries.push(entry);
    const target = owner.state[e2.action];
    if (target && "units" in target) {
      target.units[unit] = current;
      if ("ranks" in target && !entry.absorbed) place(target, unit, e2.detail);
    } else {
      if (spec.unit !== "widget")
        throw new Error(`Missing authored units for ${e2.widget}/${e2.action}`);
      owner.state[e2.action] = current;
    }
  }
  for (const { state } of states.values())
    for (const position of Object.values(state))
      if ("ranks" in position)
        for (const ids of Object.values(position.value))
          ids.sort(byRank(position.ranks));
  return states;
}
function askValue(widget, verb, answered) {
  const state = widget.state[verb];
  const spec = widget.specs.get(verb);
  if (!state || !spec) throw new Error(`Missing ask value definition for ${verb}`);
  const recorded = (value2) => spec.record?.kind === "attribute" && Array.isArray(value2) ? value2.toSorted() : value2;
  const value = "units" in state ? spec.record?.kind === "position" ? state.value : Object.fromEntries(
    Object.entries(state.units).sort(([a], [b2]) => a < b2 ? -1 : a > b2 ? 1 : 0).map(([id, entry]) => [
      id,
      spec.record ? recorded(entry.value) : entry.detail
    ])
  ) : spec.record ? recorded(state.value) : state.action ? state.detail : null;
  const populated = value !== null && value !== "" && (typeof value !== "object" || Object.keys(value).length > 0);
  const hasInput = "units" in state ? Object.keys(state.units).length > 0 : Boolean(state.action);
  return { value, present: value !== null && (populated || answered || hasInput) };
}
var isProjectionEntry = (entry) => entry.coordinate !== void 0;

// runtime/anchor-coordinate.js
var RENDERING = /* @__PURE__ */ new Set(["source_revision", "datum"]);
var PRIMITIVE = /* @__PURE__ */ new Set(["string", "number", "boolean"]);
var anchorKey = (anchor) => {
  const identified = typeof anchor?.identity === "string";
  return JSON.stringify(
    Object.entries(anchor ?? {}).filter(
      ([key, value]) => PRIMITIVE.has(typeof value) && !(identified && RENDERING.has(key))
    ).sort(([left], [right]) => left.localeCompare(right))
  );
};
var sameAnchor = (a, b2) => a === b2 || Boolean(a) && Boolean(b2) && anchorKey(a) === anchorKey(b2);

// runtime/thread/identity.js
var PENDING = "pending:";

// runtime/thread/model.js
var isReaction = (message) => Boolean(message.token);
var isAddressable = (message) => message.addressable !== false;
var threadOffers = (thread) => ({
  open: true,
  reply: !thread.settling,
  resolve: !thread.resolved && !thread.settling,
  reopen: Boolean(thread.resolved) && !thread.settling
});
function reactionChoices(thread, message, tokens) {
  if (thread.resolved || message.author !== "agent" || !isAddressable(message) || !Object.keys(tokens).length)
    return null;
  const latest = thread.msgs.findLast(
    (item) => item.author === "agent" && isAddressable(item)
  );
  const inForce = thread.msgs.filter(
    (item) => isReaction(item) && item.author === "user" && item.parent === message.id
  );
  return {
    thread: thread.key,
    message: message.key,
    latest: latest?.id === message.id,
    agent: message.agent,
    choices: tokenChoices(tokens, inForce)
  };
}
var tokenChoices = (tokens, inForce) => Object.entries(tokens).map(([name, entry]) => ({
  name,
  glyph: entry.glyph,
  label: name,
  inForce: inForce.find((item) => item.token === name) ?? null
}));
var spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
var turns = (thread) => thread.msgs.filter(
  (message) => message.id === thread.root.id || !isReaction(message)
);
var threadKey = (thread) => thread.root.attempt ?? thread.id;
var messageKey = (message) => message.key ?? message.attempt ?? message.id;
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
var editable = (message) => message.author === "user" && !message.pending && !message.token && Boolean(message.text);
var bareReaction = (thread) => thread.bare_reaction;
var discussed = (thread) => !bareReaction(thread);
var pendingSeat = (message) => message.about || !message.anchor || Object.keys(message.anchor).length !== 1 ? null : message.anchor.section ?? null;
var sending = (turn) => ({
  kind: "waiting",
  reason: "workflow",
  workflow: turn.id
});
function foldThreads(threads, gestures) {
  if (!gestures.length) return threads;
  const withdrawn = new Set(
    gestures.flatMap((gesture) => gesture.kind === "undo" ? [gesture.undoes] : [])
  );
  const copies = threads.filter((thread) => !withdrawn.has(thread.root.id)).map((thread) => ({
    ...thread,
    msgs: thread.msgs.filter((message) => !withdrawn.has(message.id))
  }));
  const byName = threadNames(copies);
  const opened = [];
  for (const gesture of gestures) {
    if (gesture.kind === "comment") {
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
        user_prompt: null,
        bare_reaction: reaction,
        seat: pendingSeat(gesture),
        summaries: [],
        unread: [],
        attention: reaction ? null : sending(gesture),
        todos: []
      };
      opened.push(thread);
      byName.set(gesture.id, thread);
    } else if (gesture.kind === "reply") {
      const thread = byName.get(gesture.parent);
      if (!thread) continue;
      const streaming = thread.msgs.at(-1)?.provisional ? 1 : 0;
      thread.msgs.splice(thread.msgs.length - streaming, 0, gesture);
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
      thread.resolved = gesture.kind === "resolve" ? { author: "user", pending: true } : null;
      thread.settling = gesture.kind;
    }
  }
  for (const thread of opened)
    thread.bare_reaction = isReaction(thread.root) && !spoken(thread).length;
  return [...copies, ...opened];
}
var reactionsAt = (threads, anchor) => threads.filter(
  (thread) => bareReaction(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor)
).map((thread) => thread.root);
var awaitsAgent = (thread) => !thread.resolved && thread.attention?.kind === "waiting";
var awaitsUser = (thread) => !thread.resolved && thread.attention?.kind === "needs_user";
var seatRoot = (thread) => thread.seat;
var moved = (message) => ({
  seq: message.edited?.seq ?? message.seq ?? null,
  ts: message.edited?.ts ?? message.ts ?? null
});
function lastMovedAt(thread) {
  let latest = null;
  for (const message of turns(thread)) {
    const { ts } = moved(message);
    if (ts !== null && (latest === null || Date.parse(ts) > Date.parse(latest)))
      latest = ts;
  }
  return latest;
}
var threadSummary = (thread) => ({
  topic: thread.title ?? thread.root.body.text.trim(),
  latest: lastMovedAt(thread)
});
var versionKey = ({ message, version }) => `${message}\0${version}`;
function readThreadRecords(threads, document, widgets, workflows, markingRead = [], ready = true) {
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
      const {
        markup,
        plainText,
        attention,
        session,
        publication,
        responds,
        start,
        title,
        ...record
      } = message;
      const units = unitsByMessage.get(message.id) ?? [];
      const authored = document.messageBodies?.get(message.id);
      if (markup && !authored)
        throw new Error(`Authored message ${message.id} has no captured body`);
      const body = markup && authored ? { kind: "authored", ...authored, units } : {
        kind: message.token ? "reaction" : message.suggestion ? "suggestion" : "prose",
        text: authored?.text ?? plainText ?? message.text ?? message.token ?? ""
      };
      const unitIds = new Set(units.map((unit) => unit.id));
      return {
        ...record,
        unread: unreadMessages.has(message.id),
        key: messageKey(message),
        body,
        // The message's own inputs, its first words and each rewrite of them, and the
        // actions on widgets frozen into it, in the published order `strongestWorkflow`
        // reads.
        workflows: workflows.filter(
          (workflow) => workflow.message === message.id || workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id)
        )
      };
    });
    const reactions = { key: threadKey(thread), resolved: thread.resolved, msgs };
    const messages = msgs.map((message) => ({
      ...message,
      reactions: ready ? reactionChoices(
        reactions,
        message,
        document.registry.$reactions?.tokens ?? {}
      ) : null
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
      user_prompt: thread.user_prompt,
      attention: thread.attention,
      todos: thread.todos,
      workflows: workflows.filter((workflow) => workflow.thread === thread.id),
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries,
      offers: threadOffers(thread)
    };
  });
}

// vendor/browser-runtime/presentation.js
function describeFailure(reason) {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
  return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}
function createPresentationCoordinator({ reportFailure }) {
  const changes = M(0);
  const changed = () => {
    changes.value += 1;
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
    if (!Number.isSafeInteger(epoch) || epoch < 0)
      throw new TypeError("presentation epoch must be a non-negative safe integer");
  };
  function resolveWaiters() {
    const remaining = [];
    for (const waiter of waiters) {
      if (document === null || !Object.is(waiter.document, document))
        waiter.resolve("superseded");
      else if (presentedEpoch >= waiter.semanticEpoch) waiter.resolve("presented");
      else remaining.push(waiter);
    }
    waiters = remaining;
  }
  function regionOutcome(waiter) {
    if (waiter.cancelled?.()) return "superseded";
    if (document === null || !Object.is(waiter.document, document)) return "superseded";
    if (semanticEpoch > waiter.semanticEpoch) return "superseded";
    if (semanticEpoch < waiter.semanticEpoch || !barrier?.sealed) return null;
    return [...waiter.regions].some(
      (region) => barrier?.members.get(region)?.commit === null
    ) ? null : "presented";
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
    if (!replacingDocument && nextSemanticEpoch < semanticEpoch)
      throw new RangeError("presentation epochs cannot decrease within one document");
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
        commit = Object.freeze({ ...commit, semanticEpoch: nextSemanticEpoch });
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
    if (document === null || barrier === null)
      throw new Error("begin a presentation publication before attaching a renderer");
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
          const proof = await completion;
          finish(ticket, "committed", proof);
        } catch (reason) {
          const superseded2 = !currentTicket(ticket);
          if (superseded2 && regions.get(record.region) !== record) return;
          let proof;
          let reported = reason;
          let recovered = false;
          if (failSoft) {
            try {
              proof = failSoft(reason);
              recovered = true;
            } catch (fallbackError) {
              if (fallbackError !== reason)
                reported = new AggregateError(
                  [reason, fallbackError],
                  "presentation and fail-soft failed"
                );
            }
          }
          reportFailure(reported);
          if (superseded2) return;
          if (recovered) finish(ticket, "failed", proof);
          else throw reported;
        }
      })();
      void ready.catch(() => void 0);
      superseded?.();
      return Object.freeze({ resolve, reject, ready });
    };
    const disconnect = () => {
      latest?.();
      latest = null;
      if (regions.get(region) !== record) return;
      regions.delete(region);
      const retiringBarrier = barrier;
      const member = retiringBarrier?.members.get(region);
      if (!retiringBarrier || member?.record !== record || retiringBarrier.completed)
        return;
      member.ticket = null;
      member.commit = null;
      member.retired = true;
      queueMicrotask(() => {
        if (barrier !== retiringBarrier || retiringBarrier.completed || retiringBarrier.members.get(region) !== member || !member.retired)
          return;
        retiringBarrier.members.delete(region);
        completeBarrier();
        resolveRegionWaiters();
        changed();
      });
    };
    return Object.freeze({ present, disconnect });
  }
  function committed(region, renderer, value) {
    const record = regions.get(region);
    return record && record.renderer === renderer && record.commit !== null && Object.is(record.commit.value, value) ? record.commit : null;
  }
  function whenPresented(targetDocument, targetSemanticEpoch) {
    validEpoch(targetSemanticEpoch);
    if (document === null || !Object.is(targetDocument, document))
      return Promise.resolve("superseded");
    const repairingCurrentEpoch = targetSemanticEpoch === semanticEpoch && barrier !== null && !barrier.completed;
    if (presentedEpoch >= targetSemanticEpoch && !repairingCurrentEpoch)
      return Promise.resolve("presented");
    return new Promise((resolve) => {
      waiters.push({
        document: targetDocument,
        semanticEpoch: targetSemanticEpoch,
        resolve
      });
    });
  }
  async function whenCurrentPresented(current) {
    for (; ; ) {
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
      resolve: () => {
      }
    }) === "presented";
  }
  async function whenCurrentRegionsPresented(current, regions2) {
    const wanted = [...new Set(regions2)];
    for (; ; ) {
      const target = current();
      if (target === null) return "superseded";
      await new Promise((resolve) => {
        const waiter = {
          ...target,
          regions: new Set(wanted),
          cancelled: () => current() === null,
          resolve
        };
        const outcome2 = regionOutcome(waiter);
        if (outcome2) resolve(outcome2);
        else regionWaiters.push(waiter);
      });
      const latest = current();
      if (latest === null) return "superseded";
      const outcome = regionOutcome({
        ...latest,
        regions: new Set(wanted),
        resolve: () => {
        }
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
      pending: Object.freeze(
        barrier ? [...barrier.members].filter(([, member]) => member.commit === null).map(([region]) => region) : []
      )
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
    subscribe: (callback) => changes.subscribe(() => {
      try {
        callback();
      } catch (reason) {
        reportFailure(reason);
      }
    }),
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
    void pass.promise.catch(() => void 0);
  }
  function collect(order, run) {
    open();
    queued.push({ order, run: bindJob(run) });
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      const round = queued;
      queued = [];
      round.sort((left, right) => left.order - right.order);
      for (const { run: run2 } of round) {
        const started = run2();
        void started.catch(() => void 0);
        running.push(started);
      }
      void drain();
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
      for (const outcome of await Promise.allSettled(started))
        if (outcome.status === "rejected" && !failed) {
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
  function presenter({
    attach,
    paint,
    failSoft,
    order = 0
  }) {
    let handle = null;
    let generation = 0;
    function claim(value) {
      const claimed = ++generation;
      handle ??= attach();
      return { claimed, value, presentation: handle.present(value, failSoft) };
    }
    async function run({ claimed, value, presentation }) {
      if (claimed !== generation) return;
      let painted;
      try {
        painted = paint(value, () => claimed === generation);
      } catch (error) {
        painted = Promise.reject(error);
      }
      presentation.resolve(painted);
      await presentation.ready;
    }
    function sync(value) {
      const ticket = claim(value);
      collect(order, () => run(ticket));
      return passed();
    }
    function disconnect() {
      generation += 1;
      handle?.disconnect();
      handle = null;
    }
    return Object.freeze({ sync, disconnect });
  }
  return Object.freeze({ presenter, passed });
}

// vendor/browser-runtime.js
import { LitElement, html, noChange, nothing, render } from "/vendor/lit.js";
import { Directive, PartType, directive } from "/vendor/lit.js";
import { AsyncDirective } from "/vendor/lit.js";
import { classMap } from "/vendor/lit.js";
import { guard } from "/vendor/lit.js";
import { keyed } from "/vendor/lit.js";
import { live } from "/vendor/lit.js";
import { createRef, ref } from "/vendor/lit.js";
import { repeat } from "/vendor/lit.js";
import { styleMap } from "/vendor/lit.js";
import { unsafeHTML } from "/vendor/lit.js";

// vendor/browser-runtime/snapshot.js
var collecting = null;
var collectingOutside = null;
function collected(reading, read) {
  const outer = collecting;
  const outerOutside = collectingOutside;
  collecting = null;
  collectingOutside = null;
  let value;
  try {
    value = read();
  } finally {
    collecting = outer;
    collectingOutside = outerOutside;
  }
  const into = reading.outside ? outerOutside : outer;
  if (into && !into.has(reading)) into.set(reading, value);
  return value;
}
function collectingInto(reads, outside, run) {
  const outer = collecting;
  const outerOutside = collectingOutside;
  collecting = reads;
  collectingOutside = outside;
  try {
    return run();
  } finally {
    collecting = outer;
    collectingOutside = outerOutside;
  }
}
function collectReads(run) {
  const reads = /* @__PURE__ */ new Map();
  try {
    return { reads, value: collectingInto(reads, reads, run) };
  } catch (error) {
    return { reads, error };
  }
}
function collectOutside(run) {
  const reads = /* @__PURE__ */ new Map();
  try {
    return { reads, value: collectingInto(collecting, reads, run) };
  } catch (error) {
    return { reads, error };
  }
}
function outsideReading(read, heard) {
  const reading = Object.freeze({
    outside: true,
    read: () => collected(reading, read),
    subscribe(listener) {
      let active = true;
      const stop = heard((round) => active ? listener(read(), round) : void 0);
      listener(read(), {});
      return () => {
        active = false;
        stop();
      };
    }
  });
  return reading;
}
function untracked(run) {
  return collectingInto(null, null, run);
}
var secured = /* @__PURE__ */ new WeakSet();
function immutable(value, normalized = /* @__PURE__ */ new WeakMap()) {
  if (value !== null && typeof value === "object" && !secured.has(value)) {
    const known = normalized.get(value);
    if (known) return known;
    let result = value;
    const refuse = () => {
      throw new TypeError("Application snapshots are read-only");
    };
    if (value instanceof Map) {
      const entries = [...value].map(([key, child]) => [
        immutable(key, normalized),
        immutable(child, normalized)
      ]);
      const map = Object.isExtensible(value) ? value : /* @__PURE__ */ new Map();
      map.clear();
      for (const [key, child] of entries) map.set(key, child);
      for (const name of ["set", "delete", "clear"])
        Object.defineProperty(map, name, { value: refuse });
      result = map;
    } else if (value instanceof Set) {
      const members = [...value].map((child) => immutable(child, normalized));
      const set = Object.isExtensible(value) ? value : /* @__PURE__ */ new Set();
      set.clear();
      for (const child of members) set.add(child);
      for (const name of ["add", "delete", "clear"])
        Object.defineProperty(set, name, { value: refuse });
      result = set;
    } else {
      const children = Object.entries(value).map(([key, child]) => [
        key,
        child,
        immutable(child, normalized)
      ]);
      if (children.some(([, child, next]) => child !== next)) {
        const target = Object.isFrozen(value) ? Array.isArray(value) ? [...value] : { ...value } : value;
        for (const [key, child, next] of children)
          if (child !== next) target[key] = next;
        result = target;
      }
    }
    Object.freeze(result);
    secured.add(result);
    normalized.set(value, result);
    return result;
  }
  return value;
}
var plain = (value) => {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};
function share(prior, next) {
  if (Object.is(prior, next)) return next;
  if (prior === null || next === null || typeof prior !== "object" || typeof next !== "object")
    return next;
  if (Array.isArray(next)) {
    if (!Array.isArray(prior)) return next;
    const children2 = next.map((child, index) => share(prior[index], child));
    if (prior.length === next.length && children2.every((child, index) => child === prior[index]))
      return prior;
    return children2.every((child, index) => child === next[index]) ? next : children2;
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(([key, child]) => [
      key,
      prior.has(key) ? share(prior.get(key), child) : child
    ]);
    if (priorKeys.length === entries.length && entries.every(([key, child], index) => key === priorKeys[index] && child === prior.get(key)))
      return prior;
    return entries.every(([key, child]) => child === next.get(key)) ? next : new Map(entries);
  }
  if (next instanceof Set) {
    if (!(prior instanceof Set)) return next;
    const priorMembers = [...prior];
    const members = [...next].map((child, index) => share(priorMembers[index], child));
    if (priorMembers.length === members.length && members.every((child, index) => child === priorMembers[index]))
      return prior;
    return members.every((child) => next.has(child)) ? next : new Set(members);
  }
  if (!plain(next) || !plain(prior) || Array.isArray(prior) || prior instanceof Map || prior instanceof Set)
    return next;
  const before = prior;
  const after = next;
  const keys = Object.keys(after);
  const children = keys.map((key) => Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key]);
  if (keys.length === Object.keys(before).length && keys.every((key, index) => Object.hasOwn(before, key) && children[index] === before[key]))
    return prior;
  if (keys.every((key, index) => children[index] === after[key])) return next;
  const copy = Object.getPrototypeOf(next) === null ? /* @__PURE__ */ Object.create(null) : {};
  keys.forEach(
    (key, index) => Object.defineProperty(copy, key, {
      value: children[index],
      writable: true,
      enumerable: true,
      configurable: true
    })
  );
  return copy;
}
function createApplicationPublisher(initial) {
  const root = M(immutable(initial));
  return Object.freeze({
    read: () => {
      if (collecting)
        throw new Error(
          "a collected read took the whole publication; select the part it needs"
        );
      return root.value;
    },
    // The root without subscribing or collecting, for the owner computing what it
    // publishes next.
    peek: () => root.peek(),
    publish(candidate) {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select(derive) {
      let prior;
      const selected = T(
        () => prior = immutable(share(prior, derive(root.value)))
      );
      const reading = Object.freeze({
        read: () => collected(reading, () => selected.value),
        subscribe: (listener) => selected.subscribe(listener)
      });
      return reading;
    }
  });
}

// runtime/registry-contract.js
function stampedState(registry, tag, event) {
  const state = registry.$states[tag]?.[event.action];
  const writer = { action: "user", report: "agent" }[event.kind];
  return state?.writer === writer ? state : null;
}
function sameStateDefinition(recorded, current) {
  if (recorded === current) return true;
  if (!recorded || !current || typeof recorded !== "object" || typeof current !== "object" || Array.isArray(recorded) !== Array.isArray(current))
    return false;
  const keys = Object.keys(recorded);
  return keys.length === Object.keys(current).length && keys.every(
    (key) => Object.hasOwn(current, key) && (typeof recorded[key] === "object" ? sameStateDefinition(recorded[key], current[key]) : recorded[key] === current[key])
  );
}
var isElementName = (name) => /^lf-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name);

// runtime/pending/model.js
var isThreadEvent = (event) => event.kind === "comment" || event.kind === "reply";
var isMessageEvent = (event) => isThreadEvent(event) && !event.token;
var isTurnEvent = (event) => isMessageEvent(event) || event.kind === "edit";
var turnMessage = (turn) => turn.kind === "edit" && turn.message ? turn.message : turn.id;
var threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  content_version: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: (
    /** @type {const} */
    true
  )
});
var editForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true
});
var NAMING_FIELDS = (
  /** @type {const} */
  ["parent", "message", "base", "undoes"]
);
var pendingId = (value) => typeof value === "string" && value.startsWith(PENDING);
var namesEvent = (event, id) => NAMING_FIELDS.some(
  (field) => (
    /** @type {Record<string, unknown>} */
    event[field] === id
  )
);
var namesPending = (event) => NAMING_FIELDS.some(
  (field) => pendingId(
    /** @type {Record<string, unknown>} */
    event[field]
  )
);
var nameAdmitted = (event, admitted) => {
  let named = event;
  for (const field of NAMING_FIELDS) {
    const value = (
      /** @type {Record<string, unknown>} */
      event[field]
    );
    const id = pendingId(value) ? admitted(value.slice(PENDING.length)) : null;
    if (id) named = { ...named, [field]: id };
  }
  return named;
};
var pendingForParent = (entries, id, kinds = null) => entries.find(
  (entry) => (entry.event.parent === id || entry.namedParent === id) && (!kinds || kinds.includes(entry.event.kind))
);
var actionForWidget = (descriptor, command, revision) => ({
  kind: "action",
  revision,
  widget: descriptor.id,
  action: command.verb,
  detail: structuredClone(command.detail ?? {}),
  ...command.attempt && { attempt: command.attempt }
});

// runtime/queues.js
var queueOffers = (item, ready, onUser) => ({
  open: ready,
  done: ready && onUser && item.kind === "todo"
});
var itemNoun = (item) => item.kind === "answer" && item.answer?.kind === "reply" ? "reply" : item.kind;
var OUTCOMES = Object.freeze({ done: "Done", failed: "Failed", dropped: "Dropped" });
var itemOutcome = (item) => item.kind === "answer" ? "Sent" : OUTCOMES[item.state] ?? item.state;

// vendor/browser-runtime/application.js
var LIFECYCLE = {
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
  "sending:presented": { accept: "accepted:presented", refuse: "refused" },
  accepted: { log: "accepted:logged", present: "accepted:presented" },
  "accepted:logged": { present: "accepted:presented" },
  "accepted:presented": {},
  refused: {}
};
var SENDING = /* @__PURE__ */ new Set([
  "sending",
  "sending:logged",
  "sending:presented"
]);
var DRAWN_LOCALLY = /* @__PURE__ */ new Set(["sending", "accepted"]);
var RELEASABLE = /* @__PURE__ */ new Set(["accepted:presented", "refused"]);
var UNPRESENTED = /* @__PURE__ */ new Set([
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
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:presented" && entry.event.kind !== "action") return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}
function normalizedProjection(view) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, view?.thread.projection]) {
    if (!projection) continue;
    for (const wire of projection.entries) {
      const e2 = wire.event;
      const coordinate = stateCoordinate(...wire.coordinate);
      entries.push({
        coordinate,
        e: e2,
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
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}
var NO_ASKS = {
  all: [],
  user: [],
  unanswered: []
};
function normalizedAsks(view, widgets, document, projection, local) {
  const page = view?.document.asks;
  const thread = view?.thread.asks;
  const all = [...page?.all ?? [], ...thread?.all ?? []].map(
    (ask) => {
      if (ask.source.kind === "approval") {
        const version = ask.source.version;
        const undone = new Set(local.flatMap(({ event }) => event.kind === "undo" ? [event.undoes] : []));
        const approving = local.some(({ event }) => event.kind === "done" && event.version === version);
        if (approving) return {
          ...ask,
          answer: { value: true, event: null },
          status: "answered",
          next_actor: null
        };
        if (ask.answer?.event && undone.has(ask.answer.event.id))
          return { ...ask, answer: null, status: "open", next_actor: "user" };
        return ask;
      }
      if (ask.source.kind !== "widget") return ask;
      const sourceId = ask.source.id;
      const widget = widgets.get(sourceId);
      const declaration = document.descriptors.get(ask.source.id)?.declaration["x-awaits"];
      const verb = declaration?.value;
      if (!verb || !widget) return ask;
      const completed = ask.status === "answered" && !(ask.answer?.event && projection.pendingWithdrawals.has(ask.answer.event.id));
      const { value, present } = askValue(widget, verb, completed);
      const pendingValue = widget.entries.some(({ e: e2 }) => e2.action === verb && !Number.isInteger(e2.seq)) || [...projection.pendingWithdrawals.values()].some(({ e: e2 }) => e2.widget === sourceId && (e2.action === verb || e2.id === ask.answer?.event?.id));
      const answer = present ? { value, event: pendingValue ? null : ask.answer?.event ?? null } : null;
      return { ...ask, answer };
    }
  );
  const selection = (kind) => {
    const admitted = new Set([...page?.[kind] ?? [], ...thread?.[kind] ?? []].map((ask) => ask.id));
    return all.filter((ask) => ask.source.kind === "approval" ? kind === "user" ? ask.next_actor === "user" : ask.status === "open" : admitted.has(ask.id));
  };
  return { all, user: selection("user"), unanswered: selection("unanswered") };
}
function localTodos(state, local) {
  const ending = new Set(
    local.flatMap(({ event }) => event.kind === "todo_end" ? [event.todo] : [])
  );
  const undoing = new Set(
    local.flatMap(({ event }) => event.kind === "undo" ? [event.undoes] : [])
  );
  const served = state?.browser.todos ?? [];
  const ended = state?.browser.ended_todos ?? [];
  const reopened = (todo) => todo.outcome !== null && undoing.has(todo.outcome.id ?? "");
  const open = [
    ...served,
    ...ended.filter(reopened).map((todo) => ({ ...todo, state: "open", outcome: null }))
  ];
  const locallyEnded = (todo) => ending.has(todo.id);
  return {
    open: open.filter((todo) => !locallyEnded(todo)),
    ended: [
      ...ended.filter((todo) => !reopened(todo)),
      ...open.filter(locallyEnded).map((todo) => ({
        ...todo,
        state: "done",
        running: null,
        outcome: { ts: null, detail: null }
      }))
    ]
  };
}
var NO_QUEUES = { on_user: [], on_agent: [], done: [] };
function localQueues(served, threads, workflows, todos, asks) {
  const record = new Map(asks.all.map((ask) => [ask.id, ask]));
  const asked = new Map(asks.all.map((ask, at) => [ask.id, at]));
  const open = new Set(todos.open.map((todo) => todo.id));
  const ended = new Set(todos.ended.map((todo) => todo.id));
  const byThread = new Map(threads.map((thread) => [thread.id, thread]));
  const sending2 = workflows.filter(
    (workflow) => workflow.stage === "sending" && workflow.next_actor === "agent" && workflow.subject.kind === "thread"
  );
  const resent = new Set(sending2.map((workflow) => workflow.thread));
  const retrying = (thread) => {
    const reading = byThread.get(thread);
    return Boolean(
      reading && !reading.resolved && reading.attention?.kind === "needs_user" && reading.attention.reason === "resend"
    );
  };
  const askOf = (item) => {
    const local = record.get(item.id);
    if (!local) throw new Error(`Queue item ${item.id} names no ask`);
    return local;
  };
  const standsOpen = (item) => {
    switch (item.kind) {
      case "ask":
        return askOf(item).next_actor === "user";
      case "todo":
        return open.has(item.id);
      case "resend":
        return item.thread === null || retrying(item.thread);
      case "answer":
        return !resent.has(item.thread);
      default:
        return true;
    }
  };
  const reopened = (item) => item.kind === "ask" ? askOf(item).status === "open" && askOf(item).next_actor === "user" : item.kind === "todo" && open.has(item.id);
  const endedHere = (item) => item.kind === "ask" ? askOf(item).status !== "open" : item.kind === "todo" && ended.has(item.id);
  const current = (item) => item.kind === "ask" ? { ...item, ask: askOf(item) } : item;
  const asOpen = ({ state: _state, ended: _ended, detail: _detail, ...item }) => current(item);
  const asDone = (item) => ({
    ...current(item),
    live: false,
    state: item.kind === "ask" && askOf(item).status === "withdrawn" ? "dropped" : "done",
    ended: null,
    detail: null
  });
  const listed = new Set(
    [...served.on_user, ...served.on_agent].map((item) => `${item.kind}:${item.id}`)
  );
  const resend = (id, subject, thread) => listed.has(`resend:${id}`) ? [] : [{ kind: "resend", id, owner: "user", subject, thread, live: false }];
  const reopenedFor = (owner) => served.done.filter((item) => item.owner === owner && reopened(item));
  return {
    on_user: [
      ...served.on_user.filter(standsOpen).map(current),
      ...reopenedFor("user").map(asOpen),
      ...threads.flatMap(
        (thread) => retrying(thread.id) ? resend(thread.id, { kind: "thread", id: thread.id }, thread.id) : []
      ),
      ...workflows.flatMap(
        (workflow) => workflow.next_actor === "user" && workflow.thread === null ? resend(workflow.id, workflow.subject, null) : []
      )
    ].toSorted(
      (a, b2) => onUserRank(a) - onUserRank(b2) || (a.kind === "ask" && b2.kind === "ask" ? asked.get(a.id) - asked.get(b2.id) : 0)
    ),
    on_agent: [
      ...served.on_agent.filter((item) => item.kind !== "todo" && standsOpen(item)),
      // One answer per thread, as the server lists one for the newest turn owed.
      ...sending2.filter(
        (workflow, at) => sending2.slice(at + 1).every((later) => later.thread !== workflow.thread)
      ).map((workflow) => ({
        kind: "answer",
        id: workflow.id,
        owner: "agent",
        subject: workflow.subject,
        thread: workflow.thread,
        live: false,
        answer: workflow.answer,
        stage: workflow.stage
      })),
      ...served.on_agent.filter((item) => item.kind === "todo" && standsOpen(item)),
      ...reopenedFor("agent").map(asOpen)
    ],
    // Newest first, as the server serves it: what ended in this tab has just ended.
    done: [
      ...[...served.on_user, ...served.on_agent].filter(endedHere).map(asDone),
      ...served.done.filter((item) => !reopened(item)).map(current)
    ]
  };
}
var onUserRank = (item) => item.kind === "ask" ? 0 : item.kind === "todo" ? 1 : 2;
function widgetIndex(root) {
  const projection = root.effective.projection;
  const byWidget = /* @__PURE__ */ new Map();
  const group = (widget) => {
    let entries = byWidget.get(widget);
    if (!entries) byWidget.set(widget, entries = { classified: [], desired: [], undo: [] });
    return entries;
  };
  for (const entry of projection.classified.values())
    if (!entry.terminal && entry.e.kind === "action") group(entry.e.widget).classified.push(entry);
  for (const entry of projection.actions.values()) group(entry.e.widget).desired.push(entry);
  for (const { event } of root.effective.view?.undo ?? [])
    if (event.kind === "action" && !projection.pendingWithdrawals.has(event.id))
      group(event.widget).undo.push(event);
  const heldBy = /* @__PURE__ */ new Map();
  for (const thread of root.effective.thread.all)
    if (!thread.resolved && !thread.root.pending && thread.root.holds && !heldBy.has(thread.root.holds))
      heldBy.set(thread.root.holds, thread.id);
  return { byWidget, heldBy };
}
var NO_ENTRIES = { classified: [], desired: [], undo: [] };
function widgetInputs(root, index, { id, tag }) {
  return {
    registered: root.document.descriptors.get(id),
    states: root.document.registry.$states[tag],
    current: root.effective.widgets.get(id),
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
  const classified = inputs.entries.classified.toSorted(
    (left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0)
  );
  const actionSpecs = descriptor.declaration["x-state"] ?? {};
  const states = inputs.states ?? {};
  const desired = inputs.entries.desired;
  const durableUndo = inputs.entries.undo;
  const localUndo = desired.map(({ e: e2 }) => e2).filter((event) => String(event.id).startsWith(PENDING));
  const actions = Object.fromEntries(
    Object.entries(actionSpecs).filter(([verb]) => states[verb]?.writer === "user").map(([verb]) => [
      verb,
      {
        available: currentDescriptor && inputs.hostAvailable && inputs.ready && !descriptor.quoted,
        unavailable: inputs.hostAvailable ? null : "no agent or server is available",
        history: classified.filter(({ e: e2 }) => e2.action === verb).map(({ e: e2 }) => e2),
        inForce: desired.filter(({ e: e2 }) => e2.action === verb).map(({ e: e2, unit, value }) => ({ event: e2, unit, value })),
        undo: inputs.hostAvailable ? [...localUndo, ...durableUndo].filter((event) => event.action === verb) : []
      }
    ])
  );
  const provenanceEntries = current?.entries ?? [];
  const provenance = Object.fromEntries(
    provenanceEntries.map(({ e: e2, unit, value }) => [
      `${e2.action}:${unit}`,
      { event: e2, unit, value }
    ])
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    thread: { heldBy: inputs.heldBy },
    provenance,
    actions
  };
}
function createSemanticApplication({
  presentation
} = {}) {
  const initial = {
    document: {
      revision: null,
      registry: { $states: {} },
      authored: /* @__PURE__ */ new Map(),
      descriptors: /* @__PURE__ */ new Map()
    },
    authoritative: null,
    unresolved: [],
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: [],
    phase: "waiting",
    // How the server answered the page's latest read: not yet (`waiting`), with a
    // reading the page adopted (`reached`), with nothing (`unreachable`, or `refused`
    // where it refused this tab's key), or with one the page could not apply
    // (`broken`). It is what the banner says about the server, and no semantic epoch.
    reach: "waiting",
    hostAvailable: true,
    data: { version: null, sources: {} },
    effective: derive(
      {
        revision: null,
        registry: { $states: {} },
        authored: /* @__PURE__ */ new Map(),
        descriptors: /* @__PURE__ */ new Map()
      },
      null,
      [],
      [],
      "waiting",
      true
    ),
    semanticEpoch: 0
  };
  const publisher = createApplicationPublisher(initial);
  const widgets = publisher.select(widgetIndex);
  let dataTaken = -Infinity;
  let order = 0;
  let publicationDepth = 0;
  let activePresentation = null;
  if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));
  function derive(document, state, unresolved, markingRead, phase, hostAvailable) {
    const receipts = state?.browser.receipts ?? [];
    const local = unresolved.filter((entry2) => DRAWN_LOCALLY.has(entry2.state));
    const refused = unresolved.filter((entry2) => entry2.state === "refused");
    const served = state?.browser.views[String(document.revision)];
    const view = served ? (({ basis: _basis, ...rest }) => rest)(served) : null;
    const admitted = normalizedProjection(view);
    const classifiedIds = new Set(admitted.entries.map(({ e: e2 }) => e2.id));
    const drawsAction = (e2) => {
      const descriptor = document.descriptors.get(e2.widget);
      const state2 = descriptor && stampedState(document.registry, descriptor.tag, e2);
      return Boolean(state2 && sameStateDefinition(e2.meaning?.state, state2.definition));
    };
    const localProjections = local.flatMap((entry2) => {
      const projection2 = entry2.projection;
      if (!projection2) return [];
      if (projection2.kind !== "undo") return drawsAction(projection2.e) ? [projection2] : [];
      const { target } = projection2;
      const targetId = admittedId(entry2.undoTarget, unresolved, receipts);
      const pending = !Number.isInteger(target.e.seq);
      const draws = classifiedIds.has(targetId ?? target.e.id) || pending && drawsAction(target.e);
      return draws ? [{ ...projection2, targetId }] : [];
    });
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections
    });
    const ready = phase === "ready";
    const gestures = local.flatMap(
      ({ event, thread, namedParent }) => thread ? [thread] : event.kind === "resolve" || event.kind === "unresolve" ? [{ ...event, ...namedParent ? { localParent: namedParent } : {} }] : event.kind === "undo" ? [event] : []
    );
    const folded = foldThreads(view?.thread.threads ?? [], gestures);
    const widgets2 = foldWidgetStates(document.authored, projection);
    const asks = ready ? normalizedAsks(view, widgets2, document, projection, local) : NO_ASKS;
    const todos = ready ? localTodos(state, local) : { open: [], ended: [] };
    const named = threadNames(folded);
    const threadOfEntry = ({ event, thread: drawn, namedParent }) => {
      const drawnIn = drawn && named.get(drawn.id)?.id;
      if (drawnIn) return drawnIn;
      switch (event.kind) {
        case "comment":
          return drawn?.id ?? null;
        case "reply":
          return named.get(event.parent)?.id ?? event.parent;
        case "edit":
          return named.get(event.message)?.id ?? null;
        case "resolve":
        case "unresolve":
          return named.get(event.parent)?.id ?? (namedParent ? named.get(namedParent)?.id : null) ?? null;
        case "action": {
          const held = document.descriptors.get(event.widget)?.document;
          return held?.kind === "thread" ? held.thread ?? null : null;
        }
        default:
          return null;
      }
    };
    const logged = state?.browser.thread_memberships ?? {};
    const threadsOfEntry = (entry2) => {
      const filed = entry2.admitted ? logged[entry2.admitted.id] : void 0;
      if (filed) return filed;
      const { event } = entry2;
      if (event.kind === "undo") {
        const target = unresolved.find(
          (each) => each.localId === event.undoes || each.admitted?.id === event.undoes
        );
        return target ? threadsOfEntry(target) : logged[event.undoes] ?? [];
      }
      const thread = threadOfEntry(entry2);
      return thread ? [thread] : [];
    };
    const recovery = /* @__PURE__ */ new Map();
    for (const entry2 of refused) {
      if (!isTurnEvent(entry2.event) && entry2.event.kind !== "action") continue;
      const thread = threadOfEntry(entry2);
      if (thread) recovery.set(thread, `rejected:${entry2.event.attempt}`);
    }
    const obligated = folded.map((thread) => {
      const retry = recovery.get(thread.id);
      return retry && thread.attention?.kind !== "needs_user" ? {
        ...thread,
        attention: { kind: "needs_user", reason: "resend", workflow: retry }
      } : thread;
    });
    const localWorkflow = (entry2, rejected) => {
      const turn = isTurnEvent(entry2.event) ? entry2.thread : null;
      const thread = threadOfEntry(entry2);
      const subject = turn ? thread === null ? null : { kind: "thread", id: thread } : entry2.event.kind === "action" ? { kind: "widget", id: entry2.event.widget } : null;
      if (!subject) return null;
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry2.event.attempt}`,
        revision: entry2.event.revision ?? document.revision,
        seq: entry2.order,
        input: turn?.id ?? entry2.localId,
        message: turn ? turnMessage(turn) : null,
        subject,
        thread,
        at_work: false,
        holds_thread: Boolean(turn),
        // The server's tuple, where the local fold keys a coordinate.
        coordinate: turn ? ["thread", thread] : entry2.projection ? coordinateOf(entry2.projection.coordinate) : null,
        answer: null,
        stage: "sending",
        ts: turn?.ts ?? null,
        detail: null,
        agent: null,
        session: null,
        delivery_seq: null,
        delivery_session: null,
        delivery_turn: null,
        response: null,
        activity: [],
        condition: rejected ? { kind: "failed", operation: "delivery" } : null,
        next_actor: rejected ? "user" : "agent",
        started_by: []
      };
    };
    const workflows = [
      ...state ? state.workflows : [],
      ...local.flatMap(
        (entry2) => isTurnEvent(entry2.event) ? localWorkflow(entry2, false) ?? [] : []
      ),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control or to-do when speculation ends.
      ...refused.flatMap((entry2) => localWorkflow(entry2, true) ?? [])
    ];
    const threads = readThreadRecords(
      obligated,
      document,
      widgets2,
      workflows,
      markingRead,
      ready
    );
    const selectedQueues = localQueues(
      ready ? view?.queues ?? NO_QUEUES : NO_QUEUES,
      threads,
      workflows,
      todos,
      asks
    );
    const workflowById = new Map(workflows.map((workflow) => [workflow.id, workflow]));
    const contextual = (items, onUser = false) => items.map((item) => ({
      ...item,
      workflow: workflowById.get(item.id) ?? null,
      offers: queueOffers(item, ready, onUser)
    }));
    return {
      hostAvailable,
      projection,
      widgets: widgets2,
      thread: {
        all: threads,
        // Historical system rows are event narration, never current approval state.
        approvalHistory: [
          ...state?.browser.approval_history ?? [],
          ...local.flatMap(({ event, localId, timestamp }) => event.kind === "done" ? [{ ...event, id: localId, ts: timestamp }] : [])
        ].filter((event) => !local.some(({ event: gesture }) => gesture.kind === "undo" && gesture.undoes === event.id)),
        collection: {
          phase,
          threads: threads.filter(discussed)
        },
        // The threads the gestures this tab's ledger still holds concern, refused ones
        // included until the reading they restore is drawn (held-news.js, `gesturedOn`).
        gestured: [...new Set(unresolved.flatMap(threadsOfEntry))]
      },
      asks: { phase, ...asks },
      // On me (on the user), On <agent> (on the agent), and done: the served lists
      // with this tab's sends placed against them (`localQueues`).
      queues: {
        phase,
        on_user: contextual(selectedQueues.on_user, true),
        on_agent: contextual(selectedQueues.on_agent),
        done: contextual(selectedQueues.done)
      },
      // Part of the effective reading, so a read that changes only the view's
      // reports, publication time, or undo list opens an epoch and reaches its readers.
      view,
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved.filter((entry2) => SENDING.has(entry2.state)).map((entry2) => entry2.event.attempt),
      workflows,
      activity: state?.activity ?? null
    };
  }
  function publish(changes) {
    const prior = publisher.peek();
    const next = { ...prior, ...changes };
    next.effective = share(
      prior.effective,
      derive(
        next.document,
        next.authoritative,
        next.unresolved,
        next.markingRead,
        next.phase,
        next.hostAvailable
      )
    );
    next.data = share(prior.data, next.data);
    next.semanticEpoch = prior.semanticEpoch + Number(
      next.effective !== prior.effective || next.data !== prior.data || next.phase !== prior.phase || next.document.revision !== prior.document.revision
    );
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
    return Boolean(
      prior && (state.taken < prior.taken || state.browser.basis.through_seq < prior.browser.basis.through_seq || state.active.revision < prior.active.revision)
    );
  };
  const adoptable = (state, candidate) => {
    const prior = publisher.peek();
    if (overtaken(state)) return false;
    const revision = typeof candidate === "number" ? candidate : candidate?.revision ?? prior.document.revision;
    const view = state.browser.views[String(revision)];
    return Boolean(
      view && view.basis.revision === revision && view.basis.through_seq === state.browser.basis.through_seq
    );
  };
  const unresolvedPart = publisher.select((root) => root.unresolved);
  const receiptsPart = publisher.select(
    (root) => root.authoritative?.browser.receipts ?? []
  );
  const widgetsPart = publisher.select((root) => root.effective.widgets);
  const entry = (attempt) => unresolvedPart.read().find((item) => item.event.attempt === attempt);
  const ledgerAndReceipts = () => [unresolvedPart.read(), receiptsPart.read()];
  const update = (attempt, change) => publish({
    unresolved: publisher.peek().unresolved.map(
      (item) => item.event.attempt === attempt ? change(item) : item
    )
  });
  const transition = (signal, admitted) => {
    const left = [];
    const unresolved = publisher.peek().unresolved.flatMap((item) => {
      if (!admitted.has(item.event.attempt)) return [item];
      const next = advance(item, signal, admitted.get(item.event.attempt) ?? null);
      if (!next) left.push(item.event.attempt);
      return next ? [next] : [];
    });
    return { unresolved, left };
  };
  const byAttempt = (receipts) => new Map(
    receipts.flatMap(
      (receipt) => receipt.attempt ? [[receipt.attempt, receipt]] : []
    )
  );
  return Object.freeze({
    read: publisher.read,
    select: publisher.select,
    // Whether a publication is still running its synchronous subscribers. A renderer
    // driven by one paints after it, so every region has claimed this epoch before any
    // of them touches the document.
    publishing: () => publicationDepth > 0,
    // Version comparison receives a server projection already interpreted through the
    // requested revision's registry. Keep that admitted spec on the wire; the current
    // document contract must not reinterpret historical events.
    projectView(view) {
      return foldProjection({
        ...normalizedProjection(view),
        pendingEntries: []
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds = null) {
      if (eventIds === null) return widgetsPart.read();
      const wanted = new Set(eventIds);
      return publisher.select(
        (root) => foldWidgetStates(root.document.authored, {
          ...root.effective.projection,
          desired: new Map(
            [...root.effective.projection.desired].filter(
              ([, entry2]) => wanted.has(entry2.e.id)
            )
          )
        })
      ).read();
    },
    // A widget's reading, recomputed only when one of the parts it draws moves, so a
    // publication about another widget or a thread costs each widget a comparison.
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
    identify(revision, stamp = null, live2 = false) {
      return publish({
        document: { ...publisher.peek().document, revision, stamp, live: live2 }
      });
    },
    setHostAvailable(hostAvailable) {
      return publish({ hostAvailable });
    },
    markRead(items) {
      return publish({
        markingRead: [...publisher.peek().markingRead, ...structuredClone(items)]
      });
    },
    settleMarkRead(items) {
      const remaining = publisher.peek().markingRead.filter(
        (item) => !items.some(
          (done) => done.message === item.message && done.version === item.version
        )
      );
      return publish({ markingRead: remaining });
    },
    captureDocument(document) {
      if (publisher.peek().authoritative)
        throw new Error("an admitted document changes only through adopt");
      return publish({
        document: {
          ...structuredClone(document),
          authored: new Map(structuredClone(document.authored)),
          descriptors: new Map(structuredClone(document.descriptors))
        }
      });
    },
    setPhase(phase) {
      return publish({ phase });
    },
    setReach(reach) {
      if (publisher.peek().reach === reach) return publisher.peek();
      return publish({ reach });
    },
    // Source revisions are digests with no order, so a reading's data is ordered by
    // the moment the server took it: an answer taken before the one already accepted
    // is older, whichever order the two arrive in.
    acceptData(data, taken) {
      if (taken < dataTaken) return false;
      dataTaken = taken;
      if (data.version === publisher.peek().data.version) return false;
      publish({ data: structuredClone(data) });
      return true;
    },
    // Whether this answer could be adopted with `revision` showing, asked without
    // adopting it. A live activation patches the document before it adopts, and a patch
    // is not something to undo, so the candidate is judged before the user's page is
    // touched. One definition read from two places, because two would be one edit away
    // from a document patched to a revision the answer it was patched for declines to
    // speak for.
    canAdopt(state, document = null) {
      return adoptable(state, document);
    },
    // Whether an answer is older than the one adopted, whichever revision it would
    // show. Transport drops such an answer before preparing anything for it.
    overtaken,
    // `revision` is the revision a live activation has just installed into this
    // document, and adopting the answer that named it is where its revision and stamp
    // become current.
    // The two are one reading: published apart, every widget renders once against a
    // state holding no view of the revision the document now shows — an empty
    // projection, indistinguishable for many widgets from their authored condition,
    // so the second publication changes nothing and never reaches them.
    adopt(state, document = null) {
      const prior = publisher.peek();
      if (!adoptable(state, document)) return false;
      const authoritative = structuredClone(state);
      const { unresolved } = transition(
        "log",
        byAttempt(authoritative.browser.receipts)
      );
      const capture = (value, previous) => value === previous ? value : structuredClone(value);
      publish({
        document: document ? {
          ...document,
          registry: capture(document.registry, prior.document.registry),
          authored: capture(document.authored, prior.document.authored),
          descriptors: capture(document.descriptors, prior.document.descriptors),
          ...document.messageBodies ? {
            messageBodies: capture(
              document.messageBodies,
              prior.document.messageBodies
            )
          } : {}
        } : prior.document,
        authoritative,
        unresolved,
        phase: "ready",
        reach: "reached"
      });
      return true;
    },
    enqueue(event, timestamp, plainText = event.text ?? event.token ?? "") {
      if (entry(event.attempt)) return null;
      const before = publisher.peek();
      const localId = PENDING + event.attempt;
      const thread = isThreadEvent(event) ? { ...threadForAttempt(event, timestamp), plainText } : event.kind === "edit" ? editForAttempt(event, timestamp) : null;
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
          meaning: {
            state: structuredClone(
              before.document.registry.$states[widget.tag]?.[event.action]?.definition
            )
          }
        },
        value: spec.record ? foldedValue(event, spec.record) : event.action
      } : null;
      publish({
        unresolved: [
          ...before.unresolved,
          {
            event: structuredClone(event),
            localId,
            timestamp,
            order: localOrder,
            projection,
            thread,
            undoTarget: undoTarget?.event.attempt ?? null,
            state: "sending",
            admitted: null
          }
        ]
      });
      return entry(event.attempt);
    },
    // The POST accepted `attempt` as the log's `accepted`.
    accept(attempt, accepted) {
      if (!entry(attempt)) return;
      const { unresolved } = transition("accept", /* @__PURE__ */ new Map([[attempt, accepted]]));
      publish({ unresolved });
    },
    // The POST refused `attempt`, or it can no longer be sent. What depends on it goes
    // with it: every gesture naming it by its pending id (`namesEvent`), such as an undo
    // of it, a reply to its message or a rewrite written over it, and so on down, since
    // a rewrite over that rewrite names only the one between. Returns those attempts.
    refuse(attempt) {
      const refused = entry(attempt);
      if (!refused) return [];
      const ledger = publisher.peek().unresolved;
      const gone = [refused.localId];
      const dependents = [];
      for (let grew = true; grew; ) {
        grew = false;
        for (const item of ledger)
          if (item.event.attempt !== attempt && !dependents.includes(item.event.attempt) && gone.some((id) => namesEvent(item.event, id))) {
            dependents.push(item.event.attempt);
            gone.push(item.localId);
            grew = true;
          }
      }
      const { unresolved } = transition("refuse", /* @__PURE__ */ new Map([[attempt, null]]));
      publish({
        unresolved: unresolved.filter(
          (item) => !dependents.includes(item.event.attempt)
        )
      });
      return dependents;
    },
    // A document pass carrying these receipts has run. Returns the attempts that left.
    present(receipts) {
      const { unresolved, left } = transition("present", byAttempt(receipts));
      publish({ unresolved });
      return left;
    },
    // The entries no document pass has presented yet.
    unpresented: () => unresolvedPart.read().filter((item) => UNPRESENTED.has(item.state)),
    // The entries `release` would retire now, in ledger order.
    releasable: () => unresolvedPart.read().filter((item) => RELEASABLE.has(item.state)),
    // Retire those of `attempts` still in a releasable state.
    release(attempts) {
      return publish({
        unresolved: publisher.peek().unresolved.filter(
          (item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state))
        )
      });
    },
    // Just before a send, a gesture naming one this tab sent, by its pending id, names
    // it by the id the log gave it once the log has answered, in every field that names
    // an event (`nameAdmitted`): a reply's `parent`, the revision an edit is written over
    // (`base`), as a second rewrite over a first still sending is, an undo's target. A
    // renamed `parent` is kept as `namedParent`, which still finds the thread the reply
    // was drawn in. Returns false for a gesture that cannot be sent: an undo still naming
    // a gesture the log never took, since it would take back nothing the log knows.
    nameEvents(attempt) {
      const item = entry(attempt);
      if (!item) return true;
      const event = nameAdmitted(
        item.event,
        (pending) => admittedId(pending, ...ledgerAndReceipts())
      );
      if (event !== item.event)
        update(attempt, (item2) => ({
          ...item2,
          ...event.parent !== item2.event.parent && typeof item2.event.parent === "string" ? { namedParent: item2.event.parent } : {},
          event
        }));
      return !(event.kind === "undo" && namesPending(event));
    }
  });
}

export {
  observeQueuedWork,
  enqueueWork,
  runWork,
  bindQueuedWork,
  cancelWork,
  M,
  Z,
  collectReads,
  collectOutside,
  outsideReading,
  untracked,
  share,
  stateCoordinate,
  projectionOrigins,
  authoredRank,
  rankAt,
  foldWidgetStates,
  askValue,
  isElementName,
  anchorKey,
  sameAnchor,
  PENDING,
  isReaction,
  tokenChoices,
  turns,
  threadKey,
  messageKey,
  threadNames,
  editable,
  bareReaction,
  discussed,
  reactionsAt,
  awaitsAgent,
  awaitsUser,
  seatRoot,
  moved,
  threadSummary,
  isThreadEvent,
  isMessageEvent,
  pendingForParent,
  actionForWidget,
  itemNoun,
  itemOutcome,
  createSemanticApplication,
  describeFailure,
  createPresentationCoordinator,
  createPresentationSchedule,
  LitElement,
  html,
  noChange,
  nothing,
  render,
  Directive,
  PartType,
  directive,
  AsyncDirective,
  classMap,
  guard,
  keyed,
  live,
  createRef,
  ref,
  repeat,
  styleMap,
  unsafeHTML
};
