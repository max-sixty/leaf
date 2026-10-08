// build/browser/index.ts
import { LitElement, html, noChange, nothing, render } from "./lit.js";
import { repeat } from "./lit.js";

// node_modules/@preact/signals-core/dist/signals-core.module.js
var i = /* @__PURE__ */ Symbol.for("preact-signals");
function t() {
  if (!(v > 1)) {
    var i2, t2 = false;
    !(function() {
      var i3 = c;
      c = void 0;
      while (void 0 !== i3) {
        var t3 = i3.S;
        if (t3.v === i3.v) {
          for (var n2 = t3.t; void 0 !== n2; n2 = n2.x) if (n2.i === i3.i) n2.i = t3.i;
        }
        i3 = i3.o;
      }
    })();
    while (void 0 !== h) {
      var n = h;
      h = void 0;
      s++;
      while (void 0 !== n) {
        var r2 = n.u;
        n.u = void 0;
        n.f &= -3;
        if (!(8 & n.f) && w(n)) try {
          n.c();
        } catch (n2) {
          if (!t2) {
            i2 = n2;
            t2 = true;
          }
        }
        n = r2;
      }
    }
    s = 0;
    v--;
    if (t2) throw i2;
  } else v--;
}
var r;
var o = void 0;
function f(i2) {
  var t2 = o, n = r;
  o = void 0;
  r = void 0;
  try {
    return i2();
  } finally {
    o = t2;
    r = n;
  }
}
var h = void 0;
var v = 0;
var s = 0;
var e = 0;
var c = void 0;
var d = 0;
function a(i2) {
  if (void 0 !== o) {
    var t2 = i2.n;
    if (void 0 === t2 || t2.t !== o) {
      t2 = { i: 0, S: i2, p: o.s, n: void 0, t: o, e: void 0, x: void 0, r: t2 };
      if (void 0 !== o.s) o.s.n = t2;
      o.s = t2;
      i2.n = t2;
      if (32 & o.f) i2.S(t2);
      return t2;
    } else if (-1 === t2.i) {
      t2.i = 0;
      if (void 0 !== t2.n) {
        t2.n.p = t2.p;
        if (void 0 !== t2.p) t2.p.n = t2.n;
        t2.p = o.s;
        t2.n = void 0;
        o.s.n = t2;
        o.s = t2;
      }
      return t2;
    }
  }
}
function l(i2, t2) {
  this.v = i2;
  this.i = 0;
  this.n = void 0;
  this.t = void 0;
  this.l = 0;
  this.W = null == t2 ? void 0 : t2.watched;
  this.Z = null == t2 ? void 0 : t2.unwatched;
  this.name = null == t2 ? void 0 : t2.name;
}
l.prototype.brand = i;
l.prototype.h = function() {
  return true;
};
l.prototype.S = function(i2) {
  var t2 = this, n = this.t;
  if (n !== i2 && void 0 === i2.e) {
    i2.x = n;
    this.t = i2;
    if (void 0 !== n) n.e = i2;
    else f(function() {
      var i3;
      null == (i3 = t2.W) || i3.call(t2);
    });
  }
};
l.prototype.U = function(i2) {
  var t2 = this;
  if (void 0 !== this.t) {
    var n = i2.e, r2 = i2.x;
    if (void 0 !== n) {
      n.x = r2;
      i2.e = void 0;
    }
    if (void 0 !== r2) {
      r2.e = n;
      i2.x = void 0;
    }
    if (i2 === this.t) {
      this.t = r2;
      if (void 0 === r2) f(function() {
        var i3;
        null == (i3 = t2.Z) || i3.call(t2);
      });
    }
  }
};
l.prototype.subscribe = function(i2) {
  var t2 = this;
  return j(function() {
    var n = t2.value;
    f(function() {
      return i2(n);
    });
  }, { name: "sub" });
};
l.prototype.valueOf = function() {
  return this.value;
};
l.prototype.toString = function() {
  return this.value + "";
};
l.prototype.toJSON = function() {
  return this.value;
};
l.prototype.peek = function() {
  var i2 = this;
  return f(function() {
    return i2.value;
  });
};
Object.defineProperty(l.prototype, "value", { get: function() {
  var i2 = a(this);
  if (void 0 !== i2) i2.i = this.i;
  return this.v;
}, set: function(i2) {
  if (i2 !== this.v) {
    if (s > 100) throw new Error("Cycle detected");
    !(function(i3) {
      if (0 !== v && 0 === s) {
        if (i3.l !== e) {
          i3.l = e;
          c = { S: i3, v: i3.v, i: i3.i, o: c };
        }
      }
    })(this);
    this.v = i2;
    this.i++;
    d++;
    v++;
    try {
      for (var n = this.t; void 0 !== n; n = n.x) n.t.N();
    } finally {
      t();
    }
  }
} });
function y(i2, t2) {
  return new l(i2, t2);
}
function w(i2) {
  for (var t2 = i2.s; void 0 !== t2; t2 = t2.n) if (t2.S.i !== t2.i || !t2.S.h() || t2.S.i !== t2.i) return true;
  return false;
}
function _(i2) {
  for (var t2 = i2.s; void 0 !== t2; t2 = t2.n) {
    var n = t2.S.n;
    if (void 0 !== n) t2.r = n;
    t2.S.n = t2;
    t2.i = -1;
    if (void 0 === t2.n) {
      i2.s = t2;
      break;
    }
  }
}
function b(i2) {
  var t2 = i2.s, n = void 0;
  while (void 0 !== t2) {
    var r2 = t2.p;
    if (-1 === t2.i) {
      t2.S.U(t2);
      if (void 0 !== r2) r2.n = t2.n;
      if (void 0 !== t2.n) t2.n.p = r2;
    } else n = t2;
    t2.S.n = t2.r;
    if (void 0 !== t2.r) t2.r = void 0;
    t2 = r2;
  }
  i2.s = n;
}
function p(i2, t2) {
  l.call(this, void 0, t2);
  this.x = i2;
  this.s = void 0;
  this.g = d - 1;
  this.f = 4;
}
p.prototype = new l();
p.prototype.h = function() {
  this.f &= -3;
  if (1 & this.f) return false;
  if (32 == (36 & this.f)) return true;
  this.f &= -5;
  if (this.g === d) return true;
  this.g = d;
  this.f |= 1;
  if (this.i > 0 && !w(this)) {
    this.f &= -2;
    return true;
  }
  var i2 = o;
  try {
    _(this);
    o = this;
    var t2 = this.x();
    if (16 & this.f || this.v !== t2 || 0 === this.i) {
      this.v = t2;
      this.f &= -17;
      this.i++;
    }
  } catch (i3) {
    this.v = i3;
    this.f |= 16;
    this.i++;
  }
  o = i2;
  b(this);
  this.f &= -2;
  return true;
};
p.prototype.S = function(i2) {
  if (void 0 === this.t) {
    this.f |= 36;
    for (var t2 = this.s; void 0 !== t2; t2 = t2.n) t2.S.S(t2);
  }
  l.prototype.S.call(this, i2);
};
p.prototype.U = function(i2) {
  if (void 0 !== this.t) {
    l.prototype.U.call(this, i2);
    if (void 0 === this.t) {
      this.f &= -33;
      for (var t2 = this.s; void 0 !== t2; t2 = t2.n) t2.S.U(t2);
    }
  }
};
p.prototype.N = function() {
  if (!(2 & this.f)) {
    this.f |= 6;
    for (var i2 = this.t; void 0 !== i2; i2 = i2.x) i2.t.N();
  }
};
Object.defineProperty(p.prototype, "value", { get: function() {
  if (1 & this.f) throw new Error("Cycle detected");
  var i2 = a(this);
  this.h();
  if (void 0 !== i2) i2.i = this.i;
  if (16 & this.f) throw this.v;
  return this.v;
} });
function g(i2, t2) {
  return new p(i2, t2);
}
function S(i2) {
  var n = i2.m;
  i2.m = void 0;
  if ("function" == typeof n) {
    v++;
    var r2 = o;
    o = void 0;
    try {
      n();
    } catch (t2) {
      i2.f &= -2;
      i2.f |= 8;
      m(i2);
      throw t2;
    } finally {
      o = r2;
      t();
    }
  }
}
function m(i2) {
  for (var t2 = i2.s; void 0 !== t2; t2 = t2.n) t2.S.U(t2);
  i2.x = void 0;
  i2.s = void 0;
  S(i2);
}
function x(i2) {
  if (o !== this) throw new Error("Out-of-order effect");
  b(this);
  o = i2;
  this.f &= -2;
  if (8 & this.f) m(this);
  t();
}
function E(i2, t2) {
  this.x = i2;
  this.m = void 0;
  this.s = void 0;
  this.u = void 0;
  this.f = 32;
  this.name = null == t2 ? void 0 : t2.name;
  if (r) r.push(this);
}
E.prototype.c = function() {
  var i2 = this.S();
  try {
    if (8 & this.f) return;
    if (void 0 === this.x) return;
    var t2 = this.x();
    if ("function" == typeof t2) this.m = t2;
  } finally {
    i2();
  }
};
E.prototype.S = function() {
  if (1 & this.f) throw new Error("Cycle detected");
  this.f |= 1;
  this.f &= -9;
  S(this);
  _(this);
  v++;
  var i2 = o;
  o = this;
  return x.bind(this, i2);
};
E.prototype.N = function() {
  if (!(2 & this.f)) {
    this.f |= 2;
    this.u = h;
    h = this;
  }
};
E.prototype.d = function() {
  this.f |= 8;
  if (!(1 & this.f)) m(this);
};
E.prototype.dispose = function() {
  this.d();
};
function j(i2, t2) {
  var n = new E(i2, t2);
  try {
    n.c();
  } catch (i3) {
    n.d();
    throw i3;
  }
  var r2 = n.d.bind(n);
  r2[Symbol.dispose] = r2;
  return r2;
}

// build/browser/snapshot.ts
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
function createApplicationPublisher(initial) {
  const root = y(immutable(initial));
  return Object.freeze({
    read: () => root.value,
    publish(candidate) {
      root.value = immutable(candidate);
      return root.peek();
    },
    select(derive) {
      const selected = g(() => immutable(derive(root.value)));
      return Object.freeze({
        read: () => selected.value,
        subscribe: (listener) => selected.subscribe(listener)
      });
    }
  });
}

// skills/leaf/assets/runtime/collapse.js
var COLLAPSE = /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;

// skills/leaf/assets/runtime/projection/model.js
function foldedValue(event, record) {
  const value = event.detail.value;
  if (record.kind === "body")
    return String(value ?? "").replace(COLLAPSE, " ").trim();
  if (record.kind === "attribute") return [...value].sort().join(" ");
  return value ?? null;
}
var compareProjected = (a2, b2) => {
  const aLogged = Number.isInteger(a2.e.seq);
  const bLogged = Number.isInteger(b2.e.seq);
  if (aLogged && bLogged) return a2.e.seq - b2.e.seq;
  if (aLogged) return -1;
  if (bLogged) return 1;
  return a2.localOrder - b2.localOrder;
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
    const standing = reports.get(entry.coordinate) ?? [];
    standing.push(entry);
    reports.set(entry.coordinate, standing);
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
      (entry) => entry.stands && entry.coordinate === coordinate && !withdrawn.has(entry.e.id)
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
var byRank = (ranks) => (a2, b2) => ranks[a2] < ranks[b2] ? -1 : ranks[a2] > ranks[b2] ? 1 : a2 < b2 ? -1 : a2 > b2 ? 1 : 0;
function foldWidgetStates(authoredSnapshots, projection) {
  const states = new Map(
    [...authoredSnapshots].map(([id, authored]) => [
      id,
      {
        state: structuredClone(authored.state),
        entries: [],
        specs: authored.specs
      }
    ])
  );
  const place = ({ value: containers, ranks }, unit, detail) => {
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
    const standing = { action: e2.action, value, detail: structuredClone(e2.detail) };
    owner.entries.push(entry);
    if (spec.unit === "widget") owner.state[e2.action] = standing;
    else {
      const target = owner.state[e2.action];
      target.units[unit] = standing;
      if (record?.kind === "position" && !entry.absorbed) place(target, unit, e2.detail);
    }
  }
  for (const { state, specs } of states.values())
    for (const [verb, spec] of specs)
      if (spec.record?.kind === "position")
        for (const ids of Object.values(state[verb].value))
          ids.sort(byRank(state[verb].ranks));
  return states;
}

// skills/leaf/assets/runtime/thread/identity.js
var PENDING = "pending:";

// skills/leaf/assets/runtime/thread/model.js
var isReaction = (message) => Boolean(message.token);
var spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
var threadKey = (thread) => thread.root.attempt ?? thread.id;
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
var bareReaction = (thread) => thread.bare_reaction;
var discussed = (thread) => !bareReaction(thread);
var pendingSeat = (message) => message.about || !message.anchor || Object.keys(message.anchor).length !== 1 ? null : message.anchor.section ?? null;
var sending = (message) => ({
  kind: "waiting",
  reason: "workflow",
  workflow: message.id
});
function foldThreads(threads, messages, reactions, settlements, withdrawn) {
  if (!messages.length && !reactions.length && !settlements.length && !withdrawn.size)
    return threads;
  const copies = threads.filter((thread) => !withdrawn.has(thread.root.id)).map((thread) => ({
    ...thread,
    msgs: thread.msgs.filter((message) => !withdrawn.has(message.id))
  }));
  const byName = threadNames(copies);
  const opened = [];
  for (const root of [...messages, ...reactions]) {
    if (root.kind === "reply") continue;
    const reaction = isReaction(root);
    const thread = {
      id: root.id,
      root,
      title: null,
      anchor: root.anchor ?? null,
      detached_from: null,
      rewritten_from: null,
      msgs: [root],
      resolved: null,
      user_prompt: null,
      bare_reaction: reaction,
      seat: pendingSeat(root),
      summaries: [],
      unread: []
    };
    opened.push(thread);
    byName.set(root.id, thread);
  }
  for (const reply of [...messages, ...reactions]) {
    if (reply.kind !== "reply") continue;
    const thread = byName.get(reply.parent);
    if (!thread) continue;
    thread.msgs.push(reply);
    if (!isReaction(reply)) {
      thread.resolved = null;
      thread.attention = sending(reply);
    }
  }
  for (const thread of opened) {
    const said = spoken(thread);
    thread.bare_reaction = isReaction(thread.root) && !said.length;
    thread.attention = said.length ? sending(said.at(-1)) : null;
  }
  for (const settlement of settlements) {
    const thread = byName.get(settlement.parent) ?? byName.get(settlement.localParent);
    if (!thread) continue;
    thread.resolved = settlement.kind === "resolve" ? { author: "user", pending: true } : null;
    thread.settling = settlement.kind;
  }
  return [...copies, ...opened];
}
var awaitsUser = (thread) => !thread.resolved && thread.attention?.kind === "needs_user";
var versionKey = ({ message, version }) => `${message}\0${version}`;
function readThreadRecords(threads, document, widgets, workflows, markingRead = []) {
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
      const record = {};
      for (const field of [
        "id",
        "attempt",
        "kind",
        "author",
        "agent",
        "ts",
        "seq",
        "parent",
        "pending",
        "anchor",
        "about",
        "drawing",
        "holds",
        "token",
        "text",
        "edited",
        "failure",
        "addressable",
        "revision",
        "awaits",
        "ephemeral",
        "suggestion"
      ])
        if (message[field] !== void 0) record[field] = message[field];
      const units = unitsByMessage.get(message.id) ?? [];
      const authored = document.messageBodies?.get(message.id);
      const body = message.markup ? { kind: "authored", ...authored, units } : {
        kind: message.token ? "reaction" : message.suggestion ? "suggestion" : "prose",
        text: authored?.text ?? message.plainText ?? message.text ?? message.token ?? ""
      };
      if (message.markup && !authored)
        throw new Error(`Authored message ${message.id} has no captured body`);
      const unitIds = new Set(units.map((unit) => unit.id));
      return {
        ...record,
        unread: unreadMessages.has(message.id),
        key: message.attempt ?? message.id,
        body,
        // The message's own input and the moves on widgets frozen into it, in the
        // published order `strongestWorkflow` reads.
        workflows: workflows.filter(
          (workflow) => workflow.input === message.id || workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id)
        )
      };
    });
    return {
      id: thread.id,
      key: threadKey(thread),
      title: thread.title,
      root: msgs.find((message) => message.id === thread.root.id),
      msgs,
      unread: Object.freeze(unread),
      anchor: thread.anchor,
      detached_from: thread.detached_from,
      rewritten_from: thread.rewritten_from,
      resolved: thread.resolved,
      settling: thread.settling ?? null,
      user_prompt: thread.user_prompt,
      attention: thread.attention,
      workflows: workflows.filter((workflow) => workflow.thread === thread.id),
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries
    };
  });
}

// skills/leaf/assets/runtime/pending/model.js
var isThreadEvent = (event) => event.kind === "comment" || event.kind === "reply";
var isMessageEvent = (event) => isThreadEvent(event) && !event.token;
var threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true
});

// skills/leaf/assets/runtime/thread/workflow.js
var STAGE_LABELS = Object.freeze({
  sending: "Sending",
  sent: "Sent",
  queued: "Queued",
  picked_up: "Picked up",
  working: "Working",
  replying: "Replying",
  answered: "Answered"
});
var CONDITION_LABELS = Object.freeze({
  ended: "Turn ended",
  interrupted: "Interrupted",
  stale: "Update stale",
  failed: "Failed"
});
var atWork = (workflow) => ["working", "replying"].includes(workflow.stage);

// skills/leaf/assets/runtime/queues.js
var NOUNS = Object.freeze({ widget: "ask", reply: "question" });
var taskItem = (task) => ({
  kind: "task",
  id: task.id,
  owner: task.owner,
  subject: task.subject,
  thread: task.thread,
  title: task.title,
  running: task.running,
  agent: task.agent,
  session: task.session,
  ends: task.ends,
  ask: task.ask
});
function selectQueues({ threads, workflows, tasks }) {
  const attention = new Map(threads.map((thread) => [thread.id, thread.attention]));
  const onUser = (task) => {
    if (task.ends === "widget") return !task.ask.held_by_seat;
    if (task.ends === "reply")
      return attention.get(task.subject.id)?.kind !== "waiting";
    return true;
  };
  const onYou = tasks.filter((task) => task.owner === "user" && onUser(task)).map(taskItem);
  for (const thread of threads)
    if (awaitsUser(thread) && thread.attention.reason === "recovery")
      onYou.push({
        kind: "recovery",
        id: thread.id,
        subject: { kind: "thread", id: thread.id },
        thread: thread.id
      });
  const onAgent = [];
  const sending2 = (workflow) => workflow.stage === "sending" && workflow.subject.kind === "thread";
  const resent = new Set(workflows.filter(sending2).map(({ thread }) => thread));
  for (const workflow of workflows) {
    const item = {
      id: workflow.id,
      subject: workflow.subject,
      thread: workflow.thread
    };
    if (workflow.next_actor === "user") {
      if (workflow.thread === null) onYou.push({ kind: "recovery", ...item });
    } else if (sending2(workflow) || workflow.answer !== null && !resent.has(workflow.thread))
      onAgent.push({
        kind: "answer",
        ...item,
        answer: workflow.answer,
        stage: workflow.stage
      });
    else if (atWork(workflow))
      onAgent.push({ kind: "work", ...item, detail: workflow.detail });
  }
  onAgent.push(...tasks.filter((task) => task.owner === "agent").map(taskItem));
  return { onYou, onAgent };
}
function selectDone({ tasks }) {
  return tasks.map((task) => ({
    kind: "task",
    id: task.id,
    owner: task.owner,
    subject: task.subject,
    thread: task.thread,
    title: task.title,
    state: task.state,
    ended: task.outcome?.ts ?? null,
    detail: task.outcome?.detail ?? null,
    ends: task.ends,
    ask: task.ask
  }));
}

// build/browser/application.ts
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
var UNPRESENTED = /* @__PURE__ */ new Set(["sending:logged", "accepted:logged"]);
function advance(entry, signal, admitted = null) {
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:presented" && entry.event.kind !== "action") return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}
function normalizedProjection(view, thread) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, thread?.projection]) {
    if (!projection) continue;
    for (const wire of projection.entries ?? []) {
      const e2 = wire.event;
      const coordinate = JSON.stringify(wire.coordinate);
      entries.push({
        coordinate,
        e: e2,
        restated: wire.restated,
        absorbed: wire.absorbed,
        stands: wire.stands,
        scope: wire.scope,
        spec: wire.spec,
        unit: wire.coordinate[1],
        value: wire.spec.record?.kind === "attribute" ? wire.value.join(" ") : wire.value
      });
    }
    actionIds.push(...projection.actions ?? []);
    reportIds.push(...projection.reports ?? []);
    desiredIds.push(...projection.desired ?? []);
  }
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}
var appliesTo = (descriptor, event) => event.widget === descriptor.id;
var NO_ASKS = {
  all: [],
  user: [],
  unanswered: []
};
var askRecord = (ask) => ({
  id: ask.id,
  tag: ask.tag,
  sourceId: ask.source,
  sourceTag: ask.source_tag,
  thread: ask.thread
});
function normalizedAsks(view, threadView) {
  const page = view?.document.asks;
  const thread = threadView?.asks;
  const records = (kind) => [
    ...(page?.[kind] ?? []).map(askRecord),
    ...(thread?.[kind] ?? []).map(askRecord)
  ];
  return {
    all: records("all"),
    user: records("user"),
    unanswered: records("unanswered")
  };
}
function localTasks(view, state, local) {
  const ending = new Set(
    local.filter(({ event }) => event.kind === "task_end").map(({ event }) => event.task)
  );
  const undoing = new Set(
    local.filter(({ event }) => event.kind === "undo").map(({ event }) => event.undoes)
  );
  const served = [...view?.document.tasks ?? [], ...state?.browser.tasks ?? []];
  const ended = [
    ...view?.document.ended_tasks ?? [],
    ...state?.browser.ended_tasks ?? []
  ];
  const reopened = (task) => task.outcome !== null && undoing.has(task.outcome.id ?? "");
  const open = [
    ...served,
    ...ended.filter(reopened).map((task) => ({ ...task, state: "open", outcome: null }))
  ];
  return {
    open: open.filter((task) => !ending.has(task.id)),
    ended: [
      ...ended.filter((task) => !reopened(task)),
      ...open.filter((task) => ending.has(task.id)).map((task) => ({
        ...task,
        state: "done",
        running: null,
        outcome: { ts: null, detail: null }
      }))
    ]
  };
}
function widgetReading(root, descriptor) {
  const registered = root.document.descriptors.get(descriptor.id);
  const currentDescriptor = JSON.stringify(registered) === JSON.stringify(descriptor);
  const current = currentDescriptor ? root.effective.widgets.get(descriptor.id) : void 0;
  const authored = currentDescriptor ? root.document.authored.get(descriptor.id)?.state : void 0;
  const declaration = descriptor.declaration;
  const actionSpecs = declaration["x-state"] ?? {};
  const projection = root.effective.projection;
  const classified = [...projection.classified.values()].filter(
    ({ e: e2, terminal }) => !terminal && e2.kind === "action" && appliesTo(descriptor, e2)
  ).sort((left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0));
  const desired = [...projection.actions.values()].filter(
    ({ e: e2 }) => appliesTo(descriptor, e2)
  );
  const durableUndo = (root.effective.view?.undo ?? []).map((candidate) => candidate.event).filter(
    (event) => event.kind === "action" && appliesTo(descriptor, event) && !projection.pendingWithdrawals.has(event.id)
  );
  const localUndo = desired.map(({ e: e2 }) => e2).filter((event) => String(event.id).startsWith(PENDING));
  const actions = Object.fromEntries(
    Object.entries(actionSpecs).filter(([, spec]) => spec.writer === "user").map(([verb]) => [
      verb,
      {
        available: currentDescriptor && root.effective.hostAvailable && root.phase !== "waiting" && !descriptor.quoted,
        unavailable: root.effective.hostAvailable ? null : "no agent or server is available",
        history: classified.filter(({ e: e2 }) => e2.action === verb).map(({ e: e2 }) => e2),
        standing: desired.filter(({ e: e2 }) => e2.action === verb).map(({ e: e2, unit, value }) => ({ event: e2, unit, value })),
        undo: root.effective.hostAvailable ? [...localUndo, ...durableUndo].filter((event) => event.action === verb) : []
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
  const holdingThread = root.effective.thread.all.find(
    (thread) => !thread.resolved && !thread.root.pending && thread.root.holds === descriptor.id
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    thread: { heldBy: holdingThread?.id ?? null },
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
      registry: {},
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
    hostAvailable: true,
    data: { version: null, sources: {} },
    effective: derive(
      {
        revision: null,
        registry: {},
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
  let dataTaken = -Infinity;
  let order = 0;
  let signature = semanticSignature([initial.effective, initial.data, initial.phase]);
  let publicationDepth = 0;
  let activePresentation = null;
  if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));
  function derive(document, state, unresolved, markingRead, phase, hostAvailable) {
    const receipts = state?.browser.receipts ?? [];
    const local = unresolved.filter((entry2) => DRAWN_LOCALLY.has(entry2.state));
    const refused = unresolved.filter((entry2) => entry2.state === "refused");
    const namedTarget = (attempt) => {
      const target = unresolved.find((entry2) => entry2.event.attempt === attempt);
      return target ? target.admitted?.id ?? null : receipts.find((receipt) => receipt.attempt === attempt)?.id ?? null;
    };
    const localProjections = local.filter((entry2) => entry2.projection).map(
      (entry2) => entry2.projection.kind === "undo" ? { ...entry2.projection, targetId: namedTarget(entry2.undoTarget) } : entry2.projection
    );
    const served = state?.browser.views[String(document.revision)];
    const view = served ? (({ basis: _basis, ...rest }) => rest)(served) : null;
    const admitted = normalizedProjection(view, state?.browser.thread);
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections
    });
    const ready = phase === "ready";
    const messages = local.filter((entry2) => entry2.message);
    const folded = ready ? foldThreads(
      state?.browser.thread.threads ?? [],
      messages.map((entry2) => entry2.message),
      local.filter((entry2) => entry2.thread?.token).map((entry2) => entry2.thread),
      local.filter(
        ({ event }) => event.kind === "resolve" || event.kind === "unresolve"
      ).map((entry2) => ({ ...entry2.event, localParent: entry2.namedParent })),
      new Set(
        local.filter(({ event }) => event.kind === "undo").map(({ event }) => event.undoes)
      )
    ) : [];
    const widgets = foldWidgetStates(document.authored, projection);
    const asks = ready ? normalizedAsks(view, state?.browser.thread) : NO_ASKS;
    const tasks = ready ? localTasks(view, state, local) : { open: [], ended: [] };
    const owed = new Set(asks.user.map((ask) => ask.thread));
    const named = threadNames(folded);
    const threadOf = (message) => message.kind === "reply" ? named.get(message.parent)?.id ?? message.parent : message.id;
    const threadOfEntry = (entry2) => {
      if (entry2.message) return threadOf(entry2.message);
      const held = document.descriptors.get(entry2.event.widget)?.document;
      return held?.kind === "thread" ? held.thread ?? null : null;
    };
    const recovery = /* @__PURE__ */ new Map();
    for (const entry2 of refused) {
      const thread = threadOfEntry(entry2);
      if (thread) recovery.set(thread, `rejected:${entry2.event.attempt}`);
    }
    const obligated = folded.map((thread) => {
      if (owed.has(thread.id))
        return thread.attention?.reason === "ask" ? thread : {
          ...thread,
          attention: { kind: "needs_user", reason: "ask", workflow: null }
        };
      const retry = recovery.get(thread.id);
      return retry && thread.attention?.kind !== "needs_user" ? {
        ...thread,
        attention: { kind: "needs_user", reason: "recovery", workflow: retry }
      } : thread;
    });
    const localWorkflow = (entry2, rejected) => {
      const message = entry2.message;
      const thread = threadOfEntry(entry2);
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry2.event.attempt}`,
        revision: entry2.event.revision ?? document.revision,
        seq: entry2.order,
        input: message?.id ?? entry2.localId,
        subject: message ? { kind: "thread", id: thread } : { kind: "widget", id: entry2.event.widget },
        thread,
        holds_thread: Boolean(message),
        // The server's list, where the local fold keys a coordinate by its JSON.
        coordinate: message ? ["thread", thread] : entry2.projection ? JSON.parse(entry2.projection.coordinate) : null,
        answer: null,
        stage: "sending",
        ts: message?.ts ?? null,
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
      ...messages.map((entry2) => localWorkflow(entry2, false)),
      ...refused.map((entry2) => localWorkflow(entry2, true))
    ];
    const threads = readThreadRecords(
      obligated,
      document,
      widgets,
      workflows,
      markingRead
    );
    return {
      hostAvailable,
      projection,
      widgets,
      thread: {
        all: threads,
        collection: {
          phase,
          threads: threads.filter(discussed)
        }
      },
      asks,
      // What is on the user and what is on the agent, selected from the readings
      // above once this tab's sends are folded into them (`runtime/queues.js`).
      queues: selectQueues({ threads, workflows, tasks: tasks.open }),
      // What is finished, selected beside them from the ended tasks.
      done: selectDone({ tasks: tasks.ended }),
      // Inside the publication signature, so a read that changes only the view's
      // updates, publication time, or undo list still reaches its watchers.
      view,
      acceptedApprovals: state?.browser.thread.done ?? [],
      pendingApprovals: local.filter((entry2) => entry2.event.kind === "done").map((entry2) => entry2.event),
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved.filter((entry2) => SENDING.has(entry2.state)).map((entry2) => entry2.event.attempt),
      workflows,
      activity: state?.activity ?? null
    };
  }
  function semanticSignature(value) {
    return JSON.stringify(
      value,
      (_key, child) => child instanceof Map ? [...child] : child
    );
  }
  function publish(changes) {
    const prior = publisher.read();
    const next = { ...prior, ...changes };
    next.effective = derive(
      next.document,
      next.authoritative,
      next.unresolved,
      next.markingRead,
      next.phase,
      next.hostAvailable
    );
    const nextSignature = semanticSignature([next.effective, next.data, next.phase]);
    next.semanticEpoch = prior.semanticEpoch + Number(
      nextSignature !== signature || next.document.revision !== prior.document.revision
    );
    signature = nextSignature;
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
    const prior = publisher.read().authoritative;
    return Boolean(
      prior && (state.taken < prior.taken || state.browser.basis.through_seq < prior.browser.basis.through_seq || state.active.revision < prior.active.revision)
    );
  };
  const adoptable = (state, candidate) => {
    const prior = publisher.read();
    if (overtaken(state)) return false;
    const revision = typeof candidate === "number" ? candidate : candidate?.revision ?? prior.document.revision;
    const view = state.browser.views[String(revision)];
    return Boolean(
      view && view.basis.revision === revision && view.basis.through_seq === state.browser.basis.through_seq
    );
  };
  const entry = (attempt) => publisher.read().unresolved.find((item) => item.event.attempt === attempt);
  const update = (attempt, change) => publish({
    unresolved: publisher.read().unresolved.map(
      (item) => item.event.attempt === attempt ? change(item) : item
    )
  });
  const transition = (signal, admitted) => {
    const left = [];
    const unresolved = publisher.read().unresolved.flatMap((item) => {
      if (!admitted.has(item.event.attempt)) return [item];
      const next = advance(item, signal, admitted.get(item.event.attempt) ?? null);
      if (!next) left.push(item.event.attempt);
      return next ? [next] : [];
    });
    return { unresolved, left };
  };
  const byAttempt = (receipts) => new Map(
    receipts.map((receipt) => [receipt.attempt, receipt])
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
    projectView(view, thread) {
      return foldProjection({
        ...normalizedProjection(view, thread),
        pendingEntries: []
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds = null) {
      if (eventIds === null) return publisher.read().effective.widgets;
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
    selectWidget(descriptor) {
      let prior;
      let priorSignature;
      return publisher.select((root) => {
        const reading = widgetReading(root, descriptor);
        const readingSignature = semanticSignature(reading);
        if (readingSignature === priorSignature && prior) return prior;
        prior = reading;
        priorSignature = readingSignature;
        return reading;
      });
    },
    entry,
    identify(revision, stamp = null, live = false) {
      return publish({
        document: { ...publisher.read().document, revision, stamp, live }
      });
    },
    setHostAvailable(hostAvailable) {
      return publish({ hostAvailable });
    },
    markRead(items) {
      return publish({
        markingRead: [...publisher.read().markingRead, ...structuredClone(items)]
      });
    },
    settleMarkRead(items) {
      const remaining = publisher.read().markingRead.filter(
        (item) => !items.some(
          (done) => done.message === item.message && done.version === item.version
        )
      );
      return publish({ markingRead: remaining });
    },
    captureDocument(document) {
      if (publisher.read().authoritative)
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
    // Source revisions are digests with no order, so a reading's data is ordered by
    // the moment the server took it: an answer taken before the one already accepted
    // is older, whichever order the two arrive in.
    acceptData(data, taken) {
      if (taken < dataTaken) return false;
      dataTaken = taken;
      if (data.version === publisher.read().data.version) return false;
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
      const prior = publisher.read();
      if (!adoptable(state, document)) return false;
      const authoritative = structuredClone(state);
      const { unresolved } = transition(
        "log",
        byAttempt(authoritative.browser.receipts)
      );
      const capture = (value, standing) => value === standing ? value : structuredClone(value);
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
        phase: "ready"
      });
      return true;
    },
    enqueue(event, timestamp, plainText = event.text ?? event.token ?? "") {
      if (entry(event.attempt)) return null;
      const before = publisher.read();
      const localId = PENDING + event.attempt;
      const thread = isThreadEvent(event) ? { ...threadForAttempt(event, timestamp), plainText } : null;
      const undoTarget = event.kind === "undo" ? before.unresolved.find((item) => item.localId === event.undoes) : null;
      const target = undoTarget?.projection ?? before.effective.projection.classified.get(event.undoes);
      const widget = before.document.authored.get(event.widget);
      const spec = widget && before.document.registry[widget.tag]?.["x-state"]?.[event.action];
      const unit = spec && (spec.unit === "widget" ? event.widget : event.detail[spec.unit]);
      const localOrder = ++order;
      const projection = event.kind === "undo" && target?.e.kind === "action" ? {
        kind: "undo",
        target,
        coordinate: target.coordinate,
        localOrder
      } : event.kind === "action" && spec && typeof unit === "string" ? {
        unit,
        spec,
        coordinate: JSON.stringify([event.widget, unit, event.action]),
        localOrder,
        e: { ...event, id: localId },
        value: spec.record ? foldedValue(event, spec.record) : event.action
      } : null;
      publish({
        unresolved: [
          ...before.unresolved,
          {
            event: structuredClone(event),
            localId,
            order: localOrder,
            projection,
            thread,
            message: isMessageEvent(event) ? thread : null,
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
    // with it: an undo of it, and a reply to its message. Returns those attempts.
    refuse(attempt) {
      const refused = entry(attempt);
      if (!refused) return [];
      const dependents = publisher.read().unresolved.filter(
        (item) => item.undoTarget === attempt || refused.message?.id && item.event.parent === refused.message.id
      ).map((item) => item.event.attempt);
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
    // The entries an adopted reading logs that the page has not yet presented.
    unpresented: () => publisher.read().unresolved.filter((item) => UNPRESENTED.has(item.state)),
    // The entries `release` would retire now, in ledger order.
    releasable: () => publisher.read().unresolved.filter((item) => RELEASABLE.has(item.state)),
    // Retire those of `attempts` still in a releasable state.
    release(attempts) {
      return publish({
        unresolved: publisher.read().unresolved.filter(
          (item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state))
        )
      });
    },
    nameParent(attempt, receipts) {
      const item = entry(attempt);
      const parent = item?.event.parent;
      if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
      const parentAttempt = parent.slice(PENDING.length);
      const named = entry(parentAttempt)?.admitted?.id ?? receipts.find((receipt) => receipt.attempt === parentAttempt)?.id;
      if (named)
        update(attempt, (item2) => ({
          ...item2,
          namedParent: parent,
          event: { ...item2.event, parent: named }
        }));
    },
    nameUndo(attempt, receipts) {
      const item = entry(attempt);
      if (item?.event.kind !== "undo" || !item.undoTarget) return true;
      const named = entry(item.undoTarget)?.admitted?.id ?? receipts.find((receipt) => receipt.attempt === item.undoTarget)?.id;
      if (!named) return false;
      update(attempt, (item2) => ({ ...item2, event: { ...item2.event, undoes: named } }));
      return true;
    }
  });
}

// build/browser/presentation.ts
function describeFailure(reason) {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
  return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}
function createPresentationCoordinator({ reportFailure }) {
  const changes = y(0);
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
    const present = (value, completion, failSoft) => {
      const ready = (async () => {
        if (regions.get(region) !== record) {
          await Promise.resolve(completion).catch(() => void 0);
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
          const superseded = !currentTicket(ticket);
          if (superseded && regions.get(record.region) !== record) return;
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
          if (superseded) return;
          if (recovered) finish(ticket, "failed", proof);
          else throw reported;
        }
      })();
      void ready.catch(() => void 0);
      return ready;
    };
    const disconnect = () => {
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
var PRESENTATION_HELD = /* @__PURE__ */ Symbol("presentation held");
function createPresentationSchedule(bindJob) {
  let queued = [];
  let running = [];
  let scheduled = false;
  let settling = false;
  let pass = null;
  function open() {
    pass ??= (() => {
      let settle;
      let refuse;
      const promise = new Promise((resolve, reject) => {
        settle = resolve;
        refuse = reject;
      });
      void promise.catch(() => void 0);
      return { promise, settle, refuse };
    })();
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
    if (failed) finished.refuse(failure);
    else finished.settle();
  }
  const passed = () => pass?.promise ?? Promise.resolve();
  function presenter({
    attach,
    paint,
    failSoft,
    order = 0
  }) {
    let handle = null;
    let held = null;
    let generation = 0;
    function claim(value) {
      const claimed = ++generation;
      let resolve;
      let reject;
      const completion = new Promise((done, fail) => {
        resolve = done;
        reject = fail;
      });
      const inherited = held;
      held = null;
      handle ??= attach();
      const ready = handle?.present(value, completion, failSoft) ?? Promise.resolve();
      void ready.catch(() => void 0);
      inherited?.(void 0);
      return { claimed, value, resolve, reject, ready };
    }
    async function run(ticket) {
      if (ticket.claimed !== generation) {
        ticket.resolve(void 0);
        return;
      }
      let withheld = false;
      try {
        const painted = paint(ticket.value, () => ticket.claimed === generation);
        if (painted === PRESENTATION_HELD) {
          withheld = true;
          if (ticket.claimed === generation) held = ticket.resolve;
        } else ticket.resolve(await painted);
      } catch (error) {
        ticket.reject(error);
      }
      if (!withheld) await ticket.ready;
    }
    function sync(value) {
      const ticket = claim(value);
      collect(order, () => run(ticket));
      return passed();
    }
    function disconnect() {
      generation += 1;
      const inherited = held;
      held = null;
      inherited?.(void 0);
      handle?.disconnect();
      handle = null;
    }
    return Object.freeze({ sync, disconnect });
  }
  return Object.freeze({ presenter, passed });
}
export {
  LitElement,
  PRESENTATION_HELD,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
  describeFailure,
  html,
  noChange,
  nothing,
  render,
  repeat
};
