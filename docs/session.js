/* The local session used only by the product site's static Leaf documents.
 *
 * These informational pages use Leaf's runtime and controls but have no durable record
 * or agent. This adapter answers Leaf's five request paths inside the tab so those
 * controls remain an ephemeral exhibit. It does not validate events or claim to be the
 * canonical server.
 *
 * Published examples deliberately do not enter this file. The website Worker routes
 * them to complete page directories behind Leaf's ordinary Python state, projection,
 * validation, event log, and news stream.
 */

// Product documents are live drafts, so the static session supplies their revision
// marker and leaves their version unset. The version-aware shape remains the runtime's
// contract even though these product pages do not stamp versions.
const VERSION_PATH = /\/versions\/v([1-9]\d*)\.html$/;
const PAGE_ROOT = new URL(
  VERSION_PATH.test(location.pathname) ? "../" : "./",
  location.href,
).pathname;
const DOCUMENT_URL = location.pathname;
const revisionMarker =
  document.querySelector('meta[name="lf-revision"][data-lf-runtime]') ??
  Object.assign(document.createElement("meta"), {
    name: "lf-revision",
    content: "1",
  });
if (!revisionMarker.isConnected) {
  revisionMarker.dataset.lfRuntime = "";
  document.head.append(revisionMarker);
}
const REVISION = Number(revisionMarker.content);
const versionMarker = document.querySelector(
  'meta[name="lf-version"][data-lf-runtime]',
);
const VERSION = versionMarker ? Number(versionMarker.content) : null;
const realFetch = window.fetch.bind(window);

async function requireFile(path) {
  const response = await realFetch(path);
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response;
}

// Begin every file read before installing the runtime. The local API below awaits this
// one readiness promise only when the runtime asks for state, leaving its module graph
// and the page's widget imports free to load alongside the static seed. These files are
// the complete static session; a missing one is a broken product-page deployment.
let REGISTRY;
let LAYER;
let DATA;
let events;
const sessionReady = Promise.all([
  requireFile("/registry.json").then((response) => response.json()),
  requireFile(`${PAGE_ROOT}data.json`).then((response) => response.json()),
  requireFile(`${PAGE_ROOT}events.jsonl`)
    .then((response) => response.text())
    .then((text) =>
      text
        .split("\n")
        .filter((line) => line.trim())
        // seq is the line number, as `read_events` numbers a log it reads: the file
        // holds none, and an event without one is invisible to the runtime's check for
        // what a poll has brought that the last one hadn't.
        .map((line, i) => ({ ...JSON.parse(line), seq: i + 1 })),
    ),
]).then(([registry, data, seededEvents]) => {
  REGISTRY = registry;
  LAYER = registry.$layer.generation;
  DATA = data;
  events = seededEvents;
});

// The name a reply in the panel wears, and nothing else. It is not the name of anyone
// behind the page — nobody is — so the banner never speaks it: `unattended` below is what
// the page reports, and the runtime's word for that names no agent.
//
// It said "The demo awaits" once, which the banner drew with the green dot it draws for a
// live watcher. Every word of the detail after it was spent denying the frame the seat had
// already set, and a reader who had not been told anyone might be listening was being
// argued out of a claim only the dot had made.
const AGENT = "The demo";
// Said once, to the first comment this reader writes, and not again — every comment
// after it is the same person who has now been told, and the same sentence under each of
// them reads as a machine talking rather than as an answer. Held here rather than read
// off the log, which is input state rather than this adapter's lifecycle.
let answered = false;

const ANSWER = `This demo has no agent, so nobody will read your comment.

[Install Leaf](/#install) to get replies from your agent.`;

// What the product document opens on: the log the build laid beside it, which a served
// page would hand over on the first poll. `sessionReady` puts it in the first answer
// while its file read overlaps runtime startup. Today's product logs are empty; keeping
// the file door makes that an input rather than a hard-coded special case.
//
// A reload deliberately starts again from this seed. Without the Python server there is
// no durable authority to replay; browser storage would turn this illustrative session
// into a second implementation of Leaf's persistence and version rules.
// The streams open on this tab's log, told directly when it moves. A served page's
// stream finds that out by looking at files; this log is in memory, and `append` is
// the one place it changes.
const ears = new Set();

// append_event's work, minus the durability: identity, authorship and time belong to
// whoever holds the log, and seq is the line number the reader would have had.
function append(event, author, agent) {
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  events.push({
    ...event,
    id: [...bytes].map((b) => b.toString(16).padStart(2, "0")).join(""),
    author,
    ...(agent && { agent }),
    ts: new Date().toISOString(),
    seq: events.length + 1,
  });
  for (const ear of ears) ear.speak();
  return events.at(-1);
}

// This static host cannot run the canonical Python projector. Its session is therefore
// deliberately a small, ephemeral exhibit: enough structure for the shipped runtime to
// render this tab's gestures, with no claim that the result is a durable Leaf reading.
// Real pages never enter this path; their `browser` object is produced under the page
// transaction in the server.
const coordinateOf = (event) => {
  const widget = document.getElementById(event.widget);
  const channel = event.kind === "action" ? "x-state" : "x-report";
  const spec = widget && REGISTRY[widget.localName]?.[channel]?.[event.action];
  if (!spec) return null;
  const unit = spec.unit === "widget" ? event.widget : event.detail[spec.unit];
  return typeof unit === "string" ? [event.widget, unit, spec.facet] : null;
};

const DEMO_COLLAPSE =
  /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
const valueOf = (event) => {
  const widget = document.getElementById(event.widget);
  const channel = event.kind === "action" ? "x-state" : "x-report";
  const record =
    widget && REGISTRY[widget.localName]?.[channel]?.[event.action]?.record;
  if (!record) return null;
  const value = event.detail[record.value];
  if (record.kind === "body") return String(value).replace(DEMO_COLLAPSE, " ").trim();
  if (record.kind === "attribute") return [...value].sort();
  return value ?? null;
};

function demoProjection() {
  const withdrawn = new Set(
    events.filter((event) => event.undoes).map((event) => event.undoes),
  );
  const entries = [];
  const actions = new Map();
  const reports = new Map();
  for (const event of events) {
    if (!["action", "report"].includes(event.kind)) continue;
    const coordinate = coordinateOf(event);
    if (!coordinate) continue;
    const key = JSON.stringify(coordinate);
    entries.push({
      event,
      coordinate,
      value: valueOf(event),
      scope: "document",
      restated: [],
    });
    if (event.kind === "action") {
      if (!withdrawn.has(event.id)) actions.set(key, event.id);
    } else {
      const standing = reports.get(key) ?? [];
      standing.push(event.id);
      reports.set(key, standing);
    }
  }
  const desired = new Map(
    [...reports].map(([key, standing]) => [key, standing.at(-1)]),
  );
  for (const [key, id] of actions) desired.set(key, id);
  return {
    entries,
    actions: [...actions.values()],
    reports: [...reports.values()].flat(),
    desired: [...desired.values()],
  };
}

function demoThreads() {
  const withdrawn = new Set(
    events.filter((event) => event.undoes).map((event) => event.undoes),
  );
  const threads = new Map();
  const threadFor = new Map();
  const messages = new Map();
  for (const event of events) {
    if (withdrawn.has(event.id)) continue;
    if (event.kind === "comment") {
      const message = { ...event };
      const thread = {
        root: message,
        anchor: message.anchor ?? null,
        msgs: [message],
        resolved: null,
      };
      messages.set(message.id, message);
      threads.set(message.id, thread);
      threadFor.set(message.id, thread);
    } else if (event.kind === "reply") {
      let thread = threadFor.get(event.parent);
      if (!thread) {
        thread = {
          root: { ...event },
          anchor: event.anchor ?? null,
          msgs: [],
          resolved: null,
        };
        threads.set(event.parent, thread);
        threadFor.set(event.parent, thread);
      }
      const message = { ...event };
      messages.set(message.id, message);
      thread.msgs.push(message);
      // A reply that carries an anchor moves the thread there, and the opening
      // comment keeps its own as history (build_threads, events.py).
      if ("anchor" in event) thread.anchor = event.anchor;
      threadFor.set(message.id, thread);
    } else if (event.kind === "edit") {
      const message = messages.get(event.message);
      if (message) {
        message.text = event.text;
        message.edited = { id: event.id, seq: event.seq, ts: event.ts };
      }
    } else if (event.kind === "resolve") {
      const thread = threadFor.get(event.parent);
      if (thread) thread.resolved = event;
    } else if (event.kind === "unresolve") {
      const thread = threadFor.get(event.parent);
      if (thread) thread.resolved = null;
    } else if (event.kind === "action" && event.detail?.resolves) {
      const thread = threads.get(event.detail.resolves);
      if (thread) thread.resolved = event;
    }
  }
  return [...threads.values()].map((thread) => {
    const spoken = thread.msgs.filter((message) => !message.token);
    const last = spoken.at(-1);
    return {
      ...thread,
      awaits_agent: Boolean(!thread.resolved && last && last.author !== "claude"),
      awaits_reader: Boolean(
        !thread.resolved &&
        last?.author === "claude" &&
        (last.kind !== "reply" || last.awaits),
      ),
      bare_reaction: Boolean(thread.root.token && spoken.length === 0),
      seat:
        !thread.root.about && thread.anchor && Object.keys(thread.anchor).length === 1
          ? (thread.anchor.section ?? null)
          : null,
    };
  });
}

const matchesWhen = (element, when = {}) =>
  Object.entries(when).every(([attribute, values]) => {
    const present = element.hasAttribute(attribute);
    const value = element.getAttribute(attribute);
    return values.some((candidate) =>
      typeof candidate === "boolean" ? candidate === present : candidate === value,
    );
  });

const quoted = (element) => {
  for (let parent = element.parentElement; parent; parent = parent.parentElement)
    if (REGISTRY[parent.localName]?.["x-exhibit"]) return true;
  return false;
};

function demoAsks(projection, threads) {
  const standing = new Set(projection.actions);
  const withAgent = new Set(
    threads
      .filter((thread) => thread.awaits_agent)
      .map((thread) => thread.seat)
      .filter(Boolean),
  );
  const asks = { all: [], reader: [], unanswered: [] };
  const awaiting = {};
  const unansweredAwaiting = {};
  for (const [tag, entry] of Object.entries(REGISTRY)) {
    const ask = entry?.["x-awaits"];
    const request = entry?.["x-request"]?.ask;
    if (tag.startsWith("$") || (!request && (!ask || ask.rollup))) continue;
    for (const element of document.querySelectorAll(tag)) {
      if (
        !element.id ||
        (!request && !matchesWhen(element, ask.when)) ||
        quoted(element)
      )
        continue;
      const answered = request
        ? events.some(
            (event) => event.kind === "request" && event.widget === element.id,
          )
        : (ask.answers ?? []).some((verb) =>
            projection.entries.some(
              (candidate) =>
                candidate.event.widget === element.id &&
                candidate.event.action === verb &&
                standing.has(candidate.event.id),
            ),
          );
      const stillUnanswered = !answered;
      const waitsOnReader = stillUnanswered && !withAgent.has(element.id);
      awaiting[element.id] = waitsOnReader;
      unansweredAwaiting[element.id] = stillUnanswered;
      let surface = element;
      for (let parent = element.parentElement; parent; parent = parent.parentElement) {
        if (REGISTRY[parent.localName]?.["x-ask-surface"]) {
          surface = parent;
          break;
        }
      }
      const description = { id: surface.id, tag: surface.localName, thread: null };
      asks.all.push(description);
      if (waitsOnReader) asks.reader.push(description);
      if (stillUnanswered) asks.unanswered.push(description);
    }
  }
  return { ...asks, awaiting, unansweredAwaiting };
}

function demoBrowser() {
  const projection = demoProjection();
  const threads = demoThreads();
  const asks = demoAsks(projection, threads);
  const throughSeq = events.at(-1)?.seq ?? 0;
  const coverage = events
    .filter((event) => ["action", "report", "undo"].includes(event.kind))
    .map((event) => {
      const target =
        event.kind === "undo"
          ? events.find((candidate) => candidate.id === event.undoes)
          : event;
      return { event, coordinate: target ? coordinateOf(target) : null };
    });
  const undo = [...events]
    .reverse()
    .filter(
      (event) =>
        event.author === "user" &&
        ["action", "resolve", "unresolve"].includes(event.kind) &&
        !events.some((candidate) => candidate.undoes === event.id),
    )
    .map((event) => ({
      event,
      ...(coordinateOf(event) && { coordinate: coordinateOf(event) }),
    }));
  return {
    basis: { through_seq: throughSeq },
    views: {
      [REVISION]: {
        basis: { revision: REVISION, through_seq: throughSeq },
        document: {
          revision: REVISION,
          projection,
          asks: {
            all: asks.all,
            reader: asks.reader,
            unanswered: asks.unanswered,
            awaiting: asks.awaiting,
            unanswered_awaiting: asks.unansweredAwaiting,
          },
        },
        updates: [],
        undo,
        coverage,
        published_at: null,
      },
    },
    conversation: {
      projection: { entries: [], actions: [], reports: [], desired: [] },
      asks: { all: [], reader: [], unanswered: [], awaiting: {} },
      threads,
      done: events.filter((event) => event.kind === "done"),
    },
    receipts: events.filter((event) => event.attempt),
    version_notes: Object.fromEntries(
      events
        .filter((event) => event.kind === "note")
        .map((event) => [event.version, event.text]),
    ),
  };
}

// `full_state`'s answer, field for field. The shape is the runtime's contract with
// whatever is behind the page, so it is answered whole rather than pared down to what
// this version of the runtime happens to read — a field left out is a banner seat that
// goes blank the day it starts reading one.
const state = () => ({
  layer: REGISTRY.$layer,
  // A product route is a live draft; the current document stands at the page root.
  active: {
    revision: REVISION,
    version: VERSION,
    url: DOCUMENT_URL,
    label: VERSION === null ? "Draft" : `v${VERSION}`,
    activated_at: null,
  },
  versions:
    VERSION === null
      ? []
      : [{ version: VERSION, revision: REVISION, url: DOCUMENT_URL }],
  source_error: null,
  // Nobody is behind this page and nobody is coming, which the runtime has a word for
  // and reads before it weighs anything else. Everything below it is then the honest
  // nothing a page outside a session loop has to report: no claim was ever written, no
  // watcher is live, and no session ever claimed the directory. None of it is what the
  // banner reads — that is the point of declaring the state rather than staging the
  // evidence for it — but a state object that lied here would be a second answer to
  // the same question, waiting for whatever reads these next.
  unattended: true,
  status: { state: "idle", detail: "", ts: null },
  claims: [],
  listening: false,
  session_alive: null,
  claim_session: null,
  // The name a reply wears in the panel. The banner asks for none under `unattended`.
  agent: AGENT,
  host: null,
  // Read to the end, and so nothing waiting. The pair has to agree — the count is what
  // the cursor leaves over — and "read everything, do nothing with it" is what is
  // actually true here, where a cursor at nought would have the banner telling a reader
  // their comments are queued for someone.
  cursor: events.at(-1)?.seq ?? 0,
  pending: 0,
  viewed: null,
  // No session, so nowhere it is working: a page here is a file on a web host rather
  // than a leaf somebody's session holds, and the tray's hover names the work behind
  // a page. There is none behind this one, which `unattended` above already says.
  session_cwd: null,
  others: [],
  // Package-declared source state is served beside the event log. Unlike local reader
  // gestures it does not change in this static session, but it enters through the same
  // full-state field as a live host and therefore exercises the same package modules.
  data: (() => {
    const delivered = structuredClone(DATA);
    for (const source of Object.values(delivered.sources)) {
      const fragments = REGISTRY.$data?.contracts?.[source.contract]?.fragments;
      if (!fragments) continue;
      for (const snapshot of [source, ...Object.values(source.snapshots ?? {})]) {
        const items = snapshot.value?.[fragments.items];
        if (!Array.isArray(items)) continue;
        for (const item of items) delete item[fragments.value];
      }
    }
    return delivered;
  })(),
  events,
  browser: demoBrowser(),
  // The reading a served page stamps on its state and names on its stream, so a tab
  // can tell whether the stream is telling it something it already holds. The log is
  // the whole of what moves here, so its length is the reading.
  reading: String(events.length),
  // When this answer was taken, which orders answers that cross. None cross here —
  // the store answers in the tab, in turn — so the clock is only the honest value.
  taken: Date.now() / 1000,
});

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Leaf-Layer": LAYER },
  });

window.fetch = async (input, init) => {
  const url = new URL(
    input instanceof Request ? input.url : String(input),
    location.href,
  );
  // Only this page's request doors. Everything else — the theme, the registry, the
  // widget modules, another version's markup — is a file the host serves, and the
  // runtime reaches for it exactly as it would anywhere else.
  if (url.origin !== location.origin) return realFetch(input, init);
  if (!["/api/state", "/api/view", "/api/data", "/api/event"].includes(url.pathname))
    return realFetch(input, init);

  await sessionReady;
  if (url.pathname === "/api/state") return json(state());
  if (url.pathname === "/api/data") {
    const revision = Number(url.searchParams.get("data_revision"));
    const sourceName = url.searchParams.get("source");
    const key = url.searchParams.get("key");
    const snapshotId = url.searchParams.get("snapshot");
    const source = DATA.sources[sourceName];
    const fragments = source && REGISTRY.$data?.contracts?.[source.contract]?.fragments;
    const selected = snapshotId ? source?.snapshots?.[snapshotId] : source;
    const matches = selected?.value?.[fragments?.items]?.filter(
      (item) => item[fragments.key] === key,
    );
    if (
      revision !== DATA.revision ||
      !fragments ||
      !Array.isArray(matches) ||
      matches.length !== 1
    )
      return json({ error: "the static exhibit holds no such data fragment" }, 400);
    return json({
      revision,
      source: sourceName,
      contract: source.contract,
      ...(snapshotId && { snapshot: snapshotId }),
      key,
      value: matches[0][fragments.value],
    });
  }
  if (url.pathname === "/api/view") {
    const browser = demoBrowser();
    const revision = Number(url.searchParams.get("revision"));
    const throughSeq = Number(url.searchParams.get("through_seq"));
    if (revision !== REVISION || throughSeq !== browser.basis.through_seq)
      return json({ error: "the static exhibit holds no such projection" }, 400);
    return json({ browser });
  }
  if (url.pathname === "/api/event") {
    const event = JSON.parse(init.body);
    // The execution record the door keeps per attempt, which is the whole of what a
    // retry meets: a browser whose answer was lost re-posts the same attempt, and an
    // attempt already in the log is answered with the state holding it rather than
    // appended a second time. One line, because the log is this tab's own — what the
    // server spends a lock on here is the ordering two writers would need.
    if (event.attempt && events.some((e) => e.attempt === event.attempt)) {
      return json({ ok: true, state: state() });
    }
    const minted = append(event, event.kind === "error" ? "page" : "user");
    // The reply is written after the send has been answered, and lands on the read its
    // own append prompts, because that is when an answer arrives: written into the same
    // response, it would appear in the panel in the same frame as the comment, over the
    // reader's own words still settling.
    if (event.kind === "comment" && !answered) {
      answered = true;
      setTimeout(
        () =>
          append(
            { kind: "reply", parent: minted.id, revision: REVISION, text: ANSWER },
            "claude",
            AGENT,
          ),
        1200,
      );
    }
    // An accepted POST hands back the state holding the event it minted, so the sender
    // crosses one boundary rather than "the append succeeded" followed by a read that
    // could fail on its own. The minted event is in there: this file's log and the
    // state's are one list.
    return json({ ok: true, state: state() });
  }
};

// The fourth door. A served page holds GET /api/news open and hears the page's reading
// named each time it moves, then asks for state. Nothing here looks at a file: `append`
// speaks to every open stream, and what it says is the reading `state` carries. No
// connection can fail after startup, there being no server to lose; failed startup does
// dispatch `error`. There is no `alive`: the runtime's watchdog reopens a silent stream
// after half a minute, which lands here again.
window.EventSource = class EventSource extends EventTarget {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  constructor() {
    super();
    this.readyState = EventSource.CONNECTING;
    ears.add(this);
    void sessionReady.then(
      () =>
        queueMicrotask(() => {
          if (this.readyState === EventSource.CLOSED) return;
          this.readyState = EventSource.OPEN;
          this.dispatchEvent(new Event("open"));
          this.speak();
        }),
      () => {
        this.close();
        this.dispatchEvent(new Event("error"));
      },
    );
  }
  speak() {
    if (this.readyState !== EventSource.OPEN) return;
    this.dispatchEvent(new MessageEvent("message", { data: String(events.length) }));
  }
  close() {
    this.readyState = EventSource.CLOSED;
    ears.delete(this);
  }
};
