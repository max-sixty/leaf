/* The delivery gate, the event and media doors, the page's JSON requests, and the
   page's error channel to the agent.

   A document speaks the generation of the layer record it was served under, and runs
   the runtime of the Leaf that served it (`runtime_selection.py`), both of which its
   server names in the document (`DELIVERY`). `admitResponse` observes every response's
   session metadata and checks every successful payload against the document's layer,
   runtime and website release, including a freshness token whose body has not
   changed: a server restarted under another runtime serves state this code may not
   read, and refuses what it sends. A foreign answer is always refused;
   whether the page also reloads is the document source's to answer, through the same
   probe startup recovery uses, because only a source that has moved on has a different
   document to give and a page that reloads without one never stops. A page's record
   survives replacement of its serving process, including a website container, so
   process identity cannot invalidate the document. Do not let one delivery interpret
   another's state. A refused key is read here too, for every response: it is the page
   cut off from its log rather than an answer about any request, so the event door
   throws it as it throws a lost connection and the page status names the link that ends it.

   `reportPageError` is the common runtime error surface. A widget failure may `failSoft`
   its own element so the rest of the page and Threads remain usable, but a presentation
   failure neither rolls back accepted semantic state nor proves pending receipts were
   shown. The window error listener, module load failures, a widget's `failSoft`, the
   application's presentation and settlement of a gesture, and the render gate all
   report through the same page-level evidence. Do not catch an error merely to stamp
   readiness or continue accounting for pending attempts.

   A fault that leaves part of the page not working as authored, such as the tab icon,
   an interaction demo that fails to load or run a command, or a code block that fails
   to highlight, reports here so the agent hears of it, not only the console. On
   leaf.page a passive session reads the published page, so the Worker answers that
   report at the edge and logs it for the site's maintainers instead
   (`worker/src/index.ts`, `pageFault`). A failed
   user-view observer stays silent: that context is optional and must not become agent
   work. Code running inside a sample's child page reports to the child's own
   disposable log, not the page that embeds it. */

import { defineOwn } from "/runtime/framework.js";
import { exceptionText } from "./exception.js";
import { countTraffic } from "./traffic.js";
import { recordInteraction } from "./interaction-log.js";
import { DELIVERY, offlineInteractive, pageUrl, runtime } from "./context.js";
import { notice } from "./notifications.js";
import { holdingError } from "./errors.js";
import { failureContext, failureOf } from "./widget-upgrade.js";

const { layer: layerGeneration, release, probe, runtime: runtimeIdentity } = DELIVERY;

// Which delivery this page belongs to is settled by whatever serves its documents, not
// by whoever answered last. An answer naming another generation may come from a party a
// reload will never reach — a website container still starting the release the edge has
// already moved past — and reloading at each such answer lands on the same document and
// is told again, so the user spends the rollout watching the page restart. The probe
// is the document source's own reading, as it is for startup recovery: the page's
// release-scoped assets are gone once the edge has moved on, and the registry still
// answers with this document's `Leaf-Layer` while it has not.
// True when the source has a different document, false when it does not, and undefined
// when the probe could not be read or names no layer, which settles nothing and leaves
// the question open for the next foreign answer.
async function sourceMovedOn() {
  if (!probe) return true;
  let response;
  try {
    response = await fetch(probe, { cache: "no-store" });
  } catch {
    return undefined;
  }
  if (response.status === 404) return Boolean(release);
  if (!response.ok) return undefined;
  const servedRelease = response.headers.get("Leaf-Release");
  if (release && servedRelease) return servedRelease !== release;
  if (!sameRuntime(response)) return true;
  const generation = response.headers.get("Leaf-Layer");
  return generation ? generation !== layerGeneration : undefined;
}

let layerReloading = false;
/** @param {string} message */
function reloadNow(message) {
  if (layerReloading) return;
  layerReloading = true;
  notice(message);
  location.reload();
}

// Each foreign answer gets its own reading of the source, because the source may move
// while the page waits — this very page can be re-initialized during the hold — and an
// answer carried over from an earlier reading would leave the tab with no way back. One
// probe is in the air at a time, so a burst of refusals costs one. Waiting lasts as long
// as the disagreement does, so it is a held error (errors.js) rather than a passing
// notice: raised once, it stands until an answer from this delivery is admitted.
let asking = false;
const holdWaiting = holdingError();
/** @param {string} message */
function reloadDelivery(message) {
  if (layerReloading || asking) return;
  asking = true;
  void (async () => {
    try {
      const moved = await sourceMovedOn();
      if (moved === undefined) return;
      if (!moved) {
        // The answers stay refused, which is the offline reading this page already knows
        // how to hold: authored content stays readable and the feed keeps asking, so the
        // page rejoins the log by itself once the server is back on this delivery.
        holdWaiting("Waiting for Leaf to finish updating.");
        return;
      }
      reloadNow(message);
    } finally {
      asking = false;
    }
  })();
}

// Whether an answer comes from a server running this document's runtime. A website
// release names its runtime, so neither side names one there.
/** @param {Response} response */
const sameRuntime = (response) => {
  const served = response.headers.get("Leaf-Runtime");
  return !runtimeIdentity || !served || served === runtimeIdentity;
};

/** @param {HeadersInit} [headers] */
export function layerHeaders(headers) {
  const result = new Headers({
    ...(layerGeneration && { "Leaf-Layer": layerGeneration }),
    ...(runtimeIdentity && { "Leaf-Runtime": runtimeIdentity }),
    ...(runtime.currentRevision && {
      "Leaf-View-Revision": String(runtime.currentRevision),
    }),
    ...(release && { "Leaf-Release": release }),
  });
  new Headers(headers).forEach((value, name) => result.set(name, value));
  return result;
}

/** @typedef {import("../types/contract.js").ServedState & {
 * active: NonNullable<import("../types/contract.js").ServedState["active"]>,
 * browser: NonNullable<import("../types/contract.js").ServedState["browser"]>
 * }} WholeAnswer
 * @typedef {WholeAnswer | import("../types/contract.js").ServedTail} StateAnswer
 * @typedef {Omit<WholeAnswer, "data"> & {
 * data: {version: string, sources: Record<string, import("./data.js").SourceReading>}
 * }} CompletedState
 * @typedef {{
 * data: {version: string | null, sources: Record<string, import("./data.js").SourceReading>},
 * state: CompletedState | null
 * }} Held */

// A state request names what the tab holds, and the answer leaves that out for its
// reader to restore from the same holding (http.py, `page_state` and `sent`). An answer
// at the data version the tab names leaves out its sources, since data moves only when
// an agent sets it. An answer to a request naming the reading the tab adopted, by its
// `browser.basis.key`, may instead carry only the changes since that reading and the
// events logged after it (`served_state/tail.py`). A newer reading can be adopted while
// a request is out, so its reader captures the holding before asking and completes the
// answer from that.
/** @returns {Held} */
export const heldReading = () => ({ data: runtime.data, state: runtime.state });
/** @param {Held} held */
export const heldHeaders = ({ data, state }) => ({
  ...(data.version !== null && { "Leaf-Data-Version": data.version }),
  ...(state?.browser.basis.key && { "Leaf-Held-Basis": state.browser.basis.key }),
});

/** @typedef {import("../types/contract.js").ServedChange} Change */
/** @typedef {Record<string, unknown> | unknown[]} Container */

// The list a change names, from the held one: the items it sent and those it changed in
// their places, those it moved or added after the item it pairs each with, in the
// list's order, and the rest where they were (`served_state/tail.py`). A changed item
// is the held one with its own changes applied, so what they leave alone in it, such
// as each message of a thread one reply joined, keeps its identity too.
/** @param {readonly unknown[]} held @param {Extract<Change, {by: unknown}>} change */
function changedList(held, { by, items = [], changed = [], dropped = [], after = [] }) {
  /** @param {unknown} item */
  const name = (item) =>
    /** @type {string} */ (
      by === "self"
        ? item
        : by === "id"
          ? /** @type {{id: string}} */ (item).id
          : /** @type {{event: {id: string}}} */ (item).event.id
    );
  const sent = new Map(items.map((item) => [name(item), item]));
  const kept = new Map(held.map((item) => [name(item), item]));
  for (const [key, patch] of changed) sent.set(key, patched(kept.get(key), patch));
  const placed = new Set([...dropped, ...after.map(([key]) => key)]);
  // Each item `after` places is the one item now right after the one it names, so the
  // list is the held items that stay, each followed by the run placed after it.
  const next = new Map(after.map(([key, before]) => [before, key]));
  /** @type {string[]} */
  const order = [];
  /** @param {string | null} key */
  const run = (key) => {
    for (let at = next.get(key); at !== undefined; at = next.get(at)) order.push(at);
  };
  run(null);
  for (const key of kept.keys())
    if (!placed.has(key)) {
      order.push(key);
      run(key);
    }
  return order.map((key) => (sent.has(key) ? sent.get(key) : kept.get(key)));
}

// The held reading with each change applied in turn. Only the objects and lists on a
// change's path are copied, so every record the changes leave alone is the very one the
// held reading had, which is what lets the publisher and the folds after it skip it.
/** @template T @param {T} reading @param {readonly Change[]} patch @returns {T} */
function patched(reading, patch) {
  /** @type {Set<unknown>} */
  const copies = new Set();
  /** @param {unknown} value @returns {Container} */
  const copy = (value) => {
    if (copies.has(value)) return /** @type {Container} */ (value);
    const owned = Array.isArray(value)
      ? [...value]
      : { .../** @type {Record<string, unknown>} */ (value) };
    copies.add(owned);
    return owned;
  };
  const root = /** @type {Record<string, unknown>} */ (copy(reading));
  for (const change of patch) {
    const key = /** @type {string} */ (change.at.at(-1));
    let parent = root;
    for (const step of change.at.slice(0, -1)) {
      const owned = /** @type {Record<string, unknown>} */ (copy(parent[step]));
      defineOwn(parent, step, owned);
      parent = owned;
    }
    if ("by" in change)
      defineOwn(
        parent,
        key,
        changedList(/** @type {unknown[]} */ (parent[key]), change),
      );
    else if ("value" in change) defineOwn(parent, key, change.value);
    else delete parent[key];
  }
  return /** @type {T} */ (root);
}

// The whole answer: its data sources, and for an answer carrying the changes since the
// reading its request named, the rest restored from that reading, which is exactly
// the answer the server would have sent whole.
/** @param {StateAnswer} answer @param {Held} held @returns {CompletedState} */
export function completeState(answer, held) {
  const sources = answer.data.sources ?? held.data.sources;
  if (!("since" in answer)) return { ...answer, data: { ...answer.data, sources } };
  const { since, patch, events, data } = answer;
  const prior = held.state;
  if (!prior || prior.browser.basis.key !== since.key)
    throw new Error("The state answer extends a reading this tab did not name");
  return {
    ...patched(prior, patch),
    data: { ...data, sources },
    events: events.length ? [...prior.events, ...events] : prior.events,
  };
}

// An answer `admitResponse` refused: it came from another delivery, and whether the page
// reloads is already settled there. Each caller says what that means for its request.
export class LayerRefused extends Error {}

/** The structured HTTP failure produced by requestJson. */
export class RequestError extends Error {
  /** @param {string} message
   * @param {{status: number; body: string; cause?: unknown;
   *   retryAfter?: number | undefined}} details */
  constructor(message, { status, body, cause, retryAfter }) {
    super(message, { cause });
    this.status = status;
    this.body = body;
    this.retryAfter = retryAfter;
  }
}

// A server that can't take a request yet answers 503 and names in `Retry-After` the
// seconds to wait before sending it again, as the website's edge does for the minutes
// a deploy takes to roll a visitor's container onto the new release
// (`worker/src/index.ts`, `rollingOut`). That wait in milliseconds, or undefined for
// any other answer.
/** @param {Response} response */
function retryWait(response) {
  const seconds = Number(response.headers.get("Retry-After") ?? NaN);
  return response.status === 503 && Number.isFinite(seconds)
    ? seconds * 1000
    : undefined;
}

// The page's JSON requests beside the event door and the state reads: the layer's
// headers out, the answer admitted, and the JSON read off the text so an error page a
// proxy wrote fails as its status rather than as a parse. A failure throws the server's
// `error`, or `<what>: HTTP <status>`, carrying the status, the raw body and the wait
// a server that can't take the request yet names (`retryAfter`). Whether to send it
// again is the caller's: the server may already have run the request, since the
// website's edge refuses a container's answer only after the container has handled it.
/** The server owns the response contract named by each endpoint caller.
 * @template T @param {string} url @param {RequestInit} init @param {string} what
 * @returns {Promise<T>} */
export async function requestJson(url, init, what) {
  const response = await fetch(url, { ...init, headers: layerHeaders(init.headers) });
  if (!admitResponse(response))
    throw new LayerRefused(`Leaf's layer changed while requesting ${what}`);
  const text = await response.text();
  /** @param {string} message @param {unknown} [cause] */
  const failed = (message, cause) =>
    new RequestError(message, {
      status: response.status,
      body: text,
      cause,
      retryAfter: retryWait(response),
    });
  let answer = null;
  if (
    response.ok ||
    response.headers.get("Content-Type")?.split(";").at(0)?.trim() ===
      "application/json"
  )
    try {
      answer = JSON.parse(text);
    } catch (error) {
      throw failed(`${what}: HTTP ${response.status}`, error);
    }
  if (!response.ok) {
    /** @type {import("../types/contract.js").ServedRefusal | null} */
    const refusal = answer;
    throw failed(refusal?.error ?? `${what}: HTTP ${response.status}`);
  }
  return answer;
}

/** @param {string} generation */
export function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  // Say what is about to happen before it happens. The user is looking at a page
  // that `page init` has moved out from under, and a tab that reloads itself with
  // nothing said is a page that appears to have lost their place for no reason.
  reloadDelivery("Leaf has been updated — reloading this page.");
  return false;
}

/** @param {Response} response */
export const admitResponse = (response) => admitted(response, true);

// An answer about another revision than the document's, such as the reading of an
// older version a comparison asks `/api/view` for, speaks that revision's layer. Only
// the runtime and release of the server answering are held to the document's.
/** @param {Response} response */
export const admitReading = (response) => admitted(response, false);

/** @param {Response} response @param {boolean} ofThisLayer */
function admitted(response, ofThisLayer) {
  observeSession(response);
  observeKey(response);
  // Failure responses still name session activation and its public reference. Their
  // status and error body belong to the caller, not to successful-payload admission.
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

// Activation belongs to one private page in one release. A pinned revision shares
// its canonical root; another page or deployment has a separate saved record.
let sessionMode = release ? "unknown" : "active";
const sessionChannel =
  release && !document.documentElement.lfSample
    ? new window.BroadcastChannel(`leaf-session:${release}:${pageUrl("")}`)
    : null;

/** @param {boolean} broadcast */
function activateSession(broadcast) {
  const activated = sessionMode !== "active";
  sessionMode = "active";
  if (activated) document.dispatchEvent(new Event("lf-session-active"));
  if (broadcast && activated) sessionChannel?.postMessage({ active: true });
}

sessionChannel?.addEventListener("message", (event) => {
  if (event.data?.active === true) activateSession(false);
});

// Whether the page's next write has to launch its agent's container first, by the last
// answer: leaf.page answers a page with no private copy yet at the edge
// (`Leaf-Session: passive`), and one whose container has stopped from its saved record
// (`Leaf-State-Source: durable`), and a write to either waits while the container
// starts (`worker/src/index.ts`). A server that names no session runs its agent beside
// it.
let agentStopped = false;

/** @param {Response} response */
function observeSession(response) {
  const reference = response.headers.get("Leaf-Session-Reference");
  if (reference !== null && /^\d{12}$/.test(reference))
    runtime.sessionReference = reference;
  const mode = response.headers.get("Leaf-Session");
  if (mode === "active") activateSession(true);
  else if (mode === "passive" && sessionMode !== "active") sessionMode = "passive";
  if (mode !== null)
    agentStopped =
      mode === "passive" || response.headers.get("Leaf-State-Source") === "durable";
}

export const sessionIsActive = () => sessionMode === "active";
export const writeLaunchesAgent = () => agentStopped;

// The server answers a request without this page's key with 401 and nothing else does,
// whichever route was asked (`http.py`, `_answer`). Any other answer passed the key
// gate, so each response settles the reading afresh: the tab regains the key the moment
// the printed link is opened in any tab of this browser, since that sets the cookie its
// next request carries.
const KEY_REFUSED = 401;
/** @param {Response} response */
function observeKey(response) {
  runtime.keyRefused = response.status === KEY_REFUSED;
}

/** @type {PromiseWithResolvers<void>} */
const { promise: layerReady, resolve: layerRevealed } = Promise.withResolvers();
// Once the layer is known, an event goes out in the task that sends it: awaiting the
// settled promise would put the request behind every microtask queued before it, such
// as the presentation the gesture's own publication claimed, and delay its answer by
// as long as they take.
let layerKnown = false;
export const revealLayer = () => {
  layerKnown = true;
  layerRevealed();
};

const encoder = new window.TextEncoder();
// Below the 64 KiB limit, so a message too long for it goes out as an ordinary
// request; a gesture's body is far smaller.
const KEEPALIVE_BYTES = 60_000;

// The page's one door to the log, spelled once. Its callers — delivery.js, which
// orders the user's own gestures through it and sends bookkeeping beside them, and the
// error report below, which deliberately doesn't — share the request rather than
// anything about the sending: same path, same method, same encoding, so a door that
// moved would move for all of them. Whether a send waits on the one before it belongs
// to the caller.
/** @param {import("../types/contract.js").BrowserCommand} event */
export const postEvent = async (event, held = heldReading()) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  if (!layerKnown) await layerReady;
  countTraffic("sends");
  recordInteraction("event_post", { kind: event.kind, attempt: event.attempt ?? null });
  const body = JSON.stringify(event);
  let response;
  try {
    response = await fetch(pageUrl("api/event"), {
      method: "POST",
      headers: layerHeaders({
        "Content-Type": "application/json",
        ...heldHeaders(held),
      }),
      body,
      // A gesture sent as the tab closes, such as the edit a playground records on
      // leaving, still reaches the log: a keepalive request outlives its document,
      // which Firefox otherwise drops before it leaves. A page may have 64 KiB of
      // keepalive bodies in flight and the browser refuses a request past that, so a
      // longer message goes out tied to its document.
      keepalive: encoder.encode(body).byteLength < KEEPALIVE_BYTES,
    });
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      status: response.status,
    });
  } catch (error) {
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      error: String(error),
    });
    throw error;
  } finally {
    countTraffic("acked");
  }
  if (!admitResponse(response)) return null;
  // A refused key is no answer to the event: the server read none of it, so the send
  // failed the way a lost connection fails and is retried as one. The page status names
  // the link that ends it.
  if (response.status === KEY_REFUSED)
    throw new Error("the server refused this page's key");
  return response;
};

// Pasted pixels become page content before their Markdown reference enters a draft.
// The raw body keeps binary data out of JSON and the append-only log; the server
// derives the served extension and returns the canonical page-relative path. Like an
// event POST, this request waits for a known layer and accounts for its whole trip.
/** @param {Blob} file */
export const uploadMedia = async (file) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  await layerReady;
  countTraffic("sends");
  /** @type {import("../types/contract.js").ServedMediaAnswer} */
  let answer;
  try {
    answer = await requestJson(
      pageUrl("api/media"),
      { method: "POST", headers: { "Content-Type": file.type }, body: file },
      "image upload",
    );
  } catch (error) {
    if (error instanceof LayerRefused) return null;
    throw error;
  } finally {
    countTraffic("acked");
  }
  return answer.path;
};

// The page reporting itself broken, to the party who can fix it: the agent
// authored the page and its widgets, and before this the only route for a
// live-session fault was the user pasting a console nobody told them to
// open. The event lands in the log as kind "error", author "page" — the
// watcher hears it beside comments and reports; the user's pending count
// never claims it. Logged once per message text per load (a reload may repeat
// one — bounded noise over silence), capped so a fault in a loop cannot flood
// the log, and sent bare rather than through post(): a poll fault reporting
// itself through the poll would recurse, and nothing here needs the answer.
// Not part of the helper surface a module gets: an upgrade that throws is already on
// this path through window.error, and a widget that wants to say so itself has
// failSoft, which puts the message where the user is looking and dispatches the
// `error` event that window.error reports here.
const reportedReasons = new WeakSet();
const reportedPrimitives = new Set();
const reportedErrors = new Set();
/** @param {unknown} reason @param {string} [context] */
export function reportPageError(reason, context = "") {
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
      ...(runtime.currentRevision != null && { revision: runtime.currentRevision }),
    }).catch(() => {});
  });
}

// What a consumer reports of a fault it carries: a rejection that travelled up to it
// from the presentation coordinator or state application, say. Where the producer
// already reported that fault, a second report would add only the consumer's context
// and make one fault read as several, so it is dropped; for a fault no producer saw,
// such as a malformed state body, the consumer is the only reporter. A producer that
// shares one exception among owners, as a cached rejected load does among its widgets,
// reports through reportPageError, once per owner. A primitive reason has no identity,
// so its text stands for it.
/** @param {unknown} reason @param {string} [context] */
export function reportCarried(reason, context = "") {
  const reported =
    typeof reason === "object" && reason !== null
      ? reportedReasons.has(reason)
      : reportedPrimitives.has(String(reason));
  if (!reported) reportPageError(reason, context);
}

window.addEventListener("error", (e) => {
  // A widget's own failure, which it shows where it stands and dispatches
  // (`reportFailure`, widget-upgrade.js), named for the widget it happened in.
  const failure = failureOf(e);
  if (failure) {
    reportPageError(failure.reason, failureContext(failure.element));
    return;
  }
  // Chrome also puts ResizeObserver loop notices on window.error without an
  // exception. This one live page cannot tell an occasional scheduling notice
  // from a layout feedback loop, so it persists neither in the user's log. The
  // render gate and test navigation take one complete confirming reading and
  // report a notice that recurs there.
  if (e.message?.startsWith("ResizeObserver loop")) return;
  // A parse error can have a stack containing only its name and message. The
  // browser's event still names its source, independently of those stack frames.
  reportPageError(
    e.error ?? e.message,
    e.filename ? `${e.filename}:${e.lineno}:${e.colno}` : "",
  );
});
window.addEventListener("unhandledrejection", (e) => {
  reportPageError(e.reason);
});
