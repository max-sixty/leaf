/* A sample owns a disposable served page in an opaque browsing context. Its
 * unguessable page URL grants native requests to its own document, assets and log;
 * presentation commands and observations cross a private port as values.
 * Allocation captures the owning widget's immutable revision and builds either its
 * named template or a supplied full HTML source. Both become ordinary validated
 * child pages; supplied source starts with an empty history. Reset replaces the
 * allocation, admitting its initial document with a credentialless HEAD before
 * native navigation. A later authored navigation keeps the frame and disables its
 * private port; an ordinary reload reconnects.
 * An opaque parent cannot classify a later document which has no Leaf bootstrap.
 * Departed ports cannot settle the replacement's calls.
 * `ready` is the usable, upgraded interface of the sample's next document,
 * independent of its authoritative saved-state reading. When the child
 * document departs, through an authored navigation or a reload, `ready` becomes one
 * promise for the document a reload upgrades next, which announces itself with
 * `loading`. A call made meanwhile waits on it, and whatever the owner applied to the
 * departed document it applies again once it resolves. Nothing follows an external
 * destination, so that wait lasts until the owner resets or destroys the host.
 * `ready` and calls reject with `AbortError` only when the owner cancels them that
 * way, and with the next document's failure when it fails to start. A call the
 * departed document had not answered rejects with `SampleDepartedError`, since
 * commands belong to one document.
 * A block follows the child's reported height; a window keeps its own viewport.
 * A reading step the child's scroll chain spent goes on from the frame here, as the
 * wheel's scroll chains out of a frame (navigation.js, `stepAlong`).
 * Removing a frame retires its realm before releasing the allocation, including on
 * reset and parent departure. Destruction cancels pending admission and queue
 * waits; an allocation already in flight is allowed to finish so its returned
 * capability can be released. Lifecycle records enter the interaction stream at
 * these decisions, with a host/allocation identity and the connected document
 * nonce. Native load is distinct from Leaf upgrade;
 * an opaque destination cannot be classified from its load event. Retirement
 * records the local realm's destruction, before the allocation release answers.
 * A mounted frame answers for its image: the child draws the requested part of its
 * viewport, which an image of the containing page puts in the frame's place.
 * The frame's sandbox admits scripts, forms, popups that escape it, modals, downloads
 * and pointer lock, but not the same origin: the child's origin is opaque, so neither
 * document reaches the other's DOM, storage or runtime, and the child's requests to
 * other servers follow opaque-origin CORS. Native focus and reveal calls an authored
 * script makes keep their browser behavior; Leaf's own placements are skipped unless
 * the child holds focus (focus.js, `canPlaceFocus`), and its reveals stay within its
 * document. Child-capability responses carry `Referrer-Policy: no-referrer` (http.py,
 * `_sample_headers`). The frame delegates no permission policy, so the browser refuses
 * the child's clipboard writes and its copy controls fall back as on any page whose
 * clipboard refuses. The user chose this on 21 October 2026 over delegating
 * `clipboard-write`, which would let any script an author puts in a sample write the
 * user's clipboard on a press. A failed allocation or admission retires the
 * allocation before `ready` rejects. */
import { RequestError, requestJson } from "./layer-client.js";
import { pageUrl, runtime } from "./context.js";
import { dressFor, registerSampleDress } from "./dress.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { frameView, layoutWindow, presented, watchRoom } from "./geometry.js";
import {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
  watchFrame,
} from "./frame-visibility.js";
import { keeps } from "./keeps.js";
import { inputInFrame } from "./focus.js";
import { move } from "./dom-move.js";
import { nextRender, sizeObserver } from "./rendering.js";
import { recordInteraction } from "./interaction-log.js";
import { exceptionRecord } from "./exception.js";
import { aborted } from "./abort.js";

/** @typedef {import("./sample-protocol.js").SampleReady} SampleReady
 * @typedef {import("./sample-protocol.js").SampleCommands} SampleCommands
 * @typedef {import("./sample-protocol.js").SampleMethod} SampleMethod
 * @typedef {import("./sample-protocol.js").SampleResult} SampleResult
 * @typedef {import("./sample-protocol.js").SampleCall} SampleCall
 * @typedef {import("./sample-protocol.js").SampleNotices} SampleNotices
 * @typedef {{ready: Promise<SampleReady>, reset: () => Promise<SampleReady>,
 * setWindow: (value: boolean) => Promise<SampleCommands["window"]["result"]>,
 * on: <K extends keyof SampleNotices>(type: K, callback: (detail: SampleNotices[K]) => unknown) => () => void,
 * restoreCurrentLocation: () => Promise<boolean>,
 * showThread: (id: string, options: {signal: AbortSignal, surface?: "page" | "panel"}) => Promise<boolean>,
 * destroy: () => Promise<unknown>}} SampleHost
 * @typedef {{reloading?: boolean, operation?: "release", status?: number, leafDocument?: string | null,
 * reason?: string, document?: string | null, sample?: string | null,
 * error?: ReturnType<typeof exceptionRecord> & {status?: number, body?: unknown}}} SampleRecordDetail
 */
// A page can carry many samples. Their child documents each import the runtime;
// upgrading them together can exhaust the browser's request pool before any child
// finishes loading its module graph. Bound simultaneous loads across this page. A
// loaded child can keep reading slow state without holding up the next sample.
const MAX_LOADING_SAMPLES = 3;
let loadingSamples = 0;
/** @type {(() => void)[]} */
const loadWaiters = [];
let nextHost = 0;
/** @template T @param {(release: () => void) => T | PromiseLike<T>} work @param {AbortSignal} signal */
async function loadWithinLimit(work, signal) {
  signal.throwIfAborted();
  if (loadingSamples === MAX_LOADING_SAMPLES) {
    /** @type {PromiseWithResolvers<void>} */
    const { promise: turn, resolve: proceed } = Promise.withResolvers();
    loadWaiters.push(proceed);
    await Promise.race([turn, aborted(signal)]);
    // A slot handed over before the abort is this load's to run and release.
    const waiting = loadWaiters.indexOf(proceed);
    if (waiting !== -1) {
      loadWaiters.splice(waiting, 1);
      throw signal.reason;
    }
  } else loadingSamples++;
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    const next = loadWaiters.shift();
    if (next) next();
    else loadingSamples--;
  };
  try {
    return await work(release);
  } finally {
    release();
  }
}

// The child document left before answering a call.
/** @param {string} message */
const departure = (message) => new DOMException(message, "SampleDepartedError");

/** @type {Map<Node, SampleCall>} */
const mounted = new Map();
/** @param {Node} node @returns {node is HTMLIFrameElement} */
export const isSampleFrame = (node) => mounted.has(node);
// A crop in the frame's viewport coordinates.
/** @param {HTMLIFrameElement} frame @param {import("./sample-protocol.js").SampleCrop} crop */
export function sampleFrameImage(frame, crop) {
  const call = mounted.get(frame);
  if (!call) throw departure("Sample frame has departed");
  return call("image", crop);
}

/** @param {string | URL} url @param {object} body @param {Record<string, string>} [headers] */
const request = (url, body, headers = {}) =>
  requestJson(
    String(url),
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      keepalive: true,
    },
    "sample",
  );

/** @param {unknown} value @returns {value is {type: "leaf-sample-connect", sample: string, nonce: string}} */
function connectionMessage(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    "type" in value &&
    value.type === "leaf-sample-connect" &&
    "sample" in value &&
    typeof value.sample === "string" &&
    "nonce" in value &&
    typeof value.nonce === "string"
  );
}

/** @param {HTMLIFrameElement} frame @param {({template: string, source?: never} | {source: string, template?: never}) & {window?: boolean}} options @returns {SampleHost} */
export function mountSample(frame, { template, source, window: asWindow = false }) {
  if ((template == null) === (source == null))
    throw new Error("a sample needs either an authored template id or source document");
  // A template is declared in its revision's document or in a message's frozen
  // markup, which the server reads from the log beside the current revision.
  let revision = runtime.currentRevision;
  /** @type {string | undefined} */
  let message;
  for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
    const descriptor = widgetDescriptor(owner);
    if (!descriptor) continue;
    if (descriptor.document.kind === "page") revision = descriptor.document.revision;
    else if (source == null) message = descriptor.document.message;
    break;
  }
  /** @type {string | null} */
  let current = null;
  /** @type {string | null} */
  let samplePage = null;
  let destroyed = false;
  /** @type {Promise<SampleReady> | null} */
  let operation = null;
  /** @type {Promise<unknown> | null} */
  let closing = null;
  /** @type {MessagePort | null} */
  let channel = null;
  // Why the last channel closed: what a call aimed at its document rejects with.
  /** @type {unknown} */
  let lost;
  let nextId = 0;
  /** @type {PromiseWithResolvers<SampleReady> | null} */
  let pendingInterface = null;
  let hasConnected = false;
  /** @type {string | null} */
  let connectedNonce = null;
  const hostId = ++nextHost;
  const started = performance.now();
  let allocation = 0;
  /** @param {string} phase @param {SampleRecordDetail} [detail] */
  const record = (phase, detail = {}) =>
    recordInteraction("sample", {
      host: hostId,
      template,
      revision,
      allocation,
      sample: samplePage,
      document: connectedNonce,
      elapsed: performance.now() - started,
      phase,
      ...detail,
    });
  /** @param {unknown} error @param {SampleRecordDetail} [detail] */
  const recordFailure = (error, detail = {}) =>
    record("failed", {
      error: {
        ...exceptionRecord(error),
        ...(error instanceof RequestError && {
          status: error.status,
          body: error.body,
        }),
      },
      ...detail,
    });
  const lifetimeController = new AbortController();
  /** @type {Set<MessagePort>} */
  const candidates = new Set();
  /** @type {Map<import("./sample-protocol.js").SampleId, Pick<PromiseWithResolvers<SampleResult>, "resolve" | "reject">>} */
  const pending = new Map();
  /** @type {import("./sample-protocol.js").SampleListeners} */
  const listeners = {
    height: new Set(),
    input: new Set(),
    "current-location": new Set(),
    arrived: new Set(),
    loading: new Set(),
    departed: new Set(),
  };
  /** @template {keyof SampleNotices} K @param {K} type @param {SampleNotices[K]} detail */
  const notify = (type, detail) => {
    for (const callback of listeners[type] ?? []) callback(detail);
  };
  keeps(
    frame,
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock",
  );
  frame.toggleAttribute("data-lf-contained", true);

  // Whether the user can see the frame and read what it shows: the frame on screen
  // (frame-visibility.js) and admitted by this page, which itself shows.
  function admitted() {
    return (
      document.visibilityState === "visible" &&
      presented(frame) &&
      seen.shown() &&
      frameVisibility()?.visible !== false
    );
  }
  function visibility() {
    channel?.postMessage({ type: "visibility", detail: { visible: admitted() } });
  }
  /** @param {MessagePort} port @param {number} id */
  async function readVisibility(port, id) {
    try {
      const outer = await readSampleVisibility();
      if (channel !== port) return;
      const within = outer ? outer.visible && outer : layoutWindow();
      const view = admitted() && within && frameView(frame, within);
      port.postMessage({
        type: "visibility-reading",
        detail: { id, visible: Boolean(view), ...view },
      });
    } catch (error) {
      if (channel !== port) return;
      port.postMessage({
        type: "visibility-reading",
        detail: {
          id,
          error: exceptionRecord(error),
        },
      });
      reportError(error);
    }
  }
  /** @param {unknown} reason */
  function disconnect(reason) {
    channel?.close();
    channel = null;
    lost = reason;
    connectedNonce = null;
    for (const { reject } of pending.values()) reject(reason);
    pending.clear();
  }
  // Public readiness includes failure retirement. Reset coalesces with an
  // allocation's own operation, so a reported failure already permits a fresh one.
  // A reload's upgrade, or a departure's wait, is not an operation: Reset then
  // allocates afresh.
  /** @param {Promise<SampleReady>} work */
  function begin(work) {
    const active = work;
    operation = active;
    host.ready = active;
    const settled = () => {
      if (operation === active) operation = null;
    };
    active.then(settled, settled);
    return active;
  }
  /** @template T @param {PromiseLike<T>} work */
  async function settle(work) {
    try {
      return await work;
    } catch (error) {
      // Reset and destroy retire allocations themselves.
      if (exceptionRecord(error).name !== "AbortError") {
        recordFailure(error);
        await retire("failure", error);
      }
      throw error;
    }
  }
  function interfaceReady() {
    /** @type {PromiseWithResolvers<SampleReady>} */
    const completion = Promise.withResolvers();
    pendingInterface = completion;
    return completion.promise;
  }
  // A departed or replaced document's successor upgrades into the readiness
  // already pending, so a departure and the reload after it share one `ready`.
  function awaitNext() {
    if (pendingInterface) return;
    host.ready = settle(interfaceReady());
    // Owners read its outcome from `ready`; a host nobody awaits drops it, as an
    // operation's does.
    host.ready.catch(() => {});
  }
  /** @param {unknown} error */
  function failure(error) {
    if (pendingInterface) {
      const completion = pendingInterface;
      pendingInterface = null;
      completion.reject(error);
    } else {
      begin(settle(Promise.reject(error)));
      notify("loading", undefined);
    }
  }
  /** @param {MessageEvent<unknown>} event */
  function connect(event) {
    const data = event.data;
    if (
      !current ||
      event.source !== frame.contentWindow ||
      !connectionMessage(data) ||
      data.sample !== new URL(current).pathname ||
      data.nonce === connectedNonce
    )
      return;
    const nonce = data.nonce;
    const owned = current;
    const pair = new MessageChannel();
    const port = pair.port1;
    // Publish this private document endpoint at the existing diagnostic seam.
    /** @type {HTMLScriptElement | null} */
    const entry = document.querySelector("script[data-lf-entry]");
    if (!entry) throw new Error("A sample host needs the Leaf bootstrap entry");
    entry.lfDocumentPort = port;
    candidates.add(port);
    port.onmessage =
      /** @param {MessageEvent<import("./sample-protocol.js").ChildMessage>} event */ ({
        data,
      }) => {
        if (data.type === "connected") {
          if (!candidates.has(port) || current !== owned || data.nonce !== nonce)
            return;
          candidates.delete(port);
          for (const candidate of candidates) candidate.close();
          candidates.clear();
          const reloading = hasConnected;
          disconnect(departure("sample document replaced"));
          channel = port;
          connectedNonce = nonce;
          hasConnected = true;
          record("connected", { reloading });
          if (reloading) {
            awaitNext();
            notify("loading", undefined);
          }
          visibility();
          return;
        }
        // Messages from the departed realm cannot settle the next realm's calls.
        if (channel !== port) return;
        if (data.type === "departed") {
          record("departed");
          disconnect(departure("sample document navigated"));
          // Reset need not wait for a document that may never come.
          operation = null;
          awaitNext();
          notify("departed", undefined);
          return;
        }
        if (data.type === "visibility-read") {
          void readVisibility(port, data.detail.id);
          return;
        }
        if (data.type === undefined) {
          const completion = pending.get(data.id);
          if (!completion) return;
          const { resolve, reject } = completion;
          pending.delete(data.id);
          if (data.error)
            reject(
              Object.assign(
                new Error(data.error.message),
                { stack: undefined },
                data.error,
              ),
            );
          else resolve(data.result);
        } else if (data.type === "ready") {
          record("upgraded");
          const completion = pendingInterface;
          pendingInterface = null;
          completion?.resolve(data.detail);
          visibility();
        } else if (data.type === "error") {
          failure(
            Object.assign(
              new Error(data.detail.message),
              { stack: undefined },
              data.detail,
            ),
          );
        } else if (data.type === "return")
          frame.dispatchEvent(new Event("lf-sample-return"));
        else if (data.type === "step")
          frame.dispatchEvent(
            new CustomEvent("lf-sample-step", {
              bubbles: true,
              composed: true,
              detail: data.detail,
            }),
          );
        else if (data.type === "input") {
          inputInFrame(frame, data.detail.type);
          notify("input", data.detail);
        } else if (data.type === "height") notify("height", data.detail);
        else if (data.type === "current-location")
          notify("current-location", data.detail);
        else if (data.type === "arrived") notify("arrived", undefined);
      };
    frame.contentWindow?.postMessage(
      {
        sample: data.sample,
        nonce,
        settings: { window: asWindow, dress: dressFor(frame) ?? undefined },
      },
      "*",
      [pair.port2],
    );
  }
  window.addEventListener("message", connect);
  const loaded = () => {
    if (current && frame.hasAttribute("src")) record("loaded");
  };
  frame.addEventListener("load", loaded);
  const room = watchRoom(visibility);
  document.addEventListener("visibilitychange", visibility);
  const seen = watchFrame(frame, visibility);
  const size = sizeObserver(visibility);
  size.observe(frame);
  const nativeTransition = () => nextRender(visibility);
  for (const type of ["beforetoggle"])
    document.addEventListener(type, nativeTransition, true);
  const unwatch = onFrameVisibility(visibility);
  const undress = registerSampleDress(frame, (dress) =>
    channel?.postMessage({ type: "dress", detail: dress }),
  );
  const lifetime = new MutationObserver(() => {
    if (!frame.isConnected) void host.destroy();
  });
  lifetime.observe(document, { childList: true, subtree: true });

  // What a pending call rejects with: the failure that retires the allocation, or
  // else the owner's cancellation.
  /** @param {string} reason @param {unknown} [cause] */
  function retire(reason, cause = new DOMException("sample replaced", "AbortError")) {
    if (!current) return;
    const retiringDocument = connectedNonce;
    const previous = current;
    const sample = samplePage;
    current = null;
    samplePage = null;
    hasConnected = false;
    disconnect(cause);
    for (const port of candidates) port.close();
    candidates.clear();
    const completion = pendingInterface;
    pendingInterface = null;
    completion?.reject(cause);
    const parent = frame.parentNode;
    const next = frame.nextSibling;
    frame.remove();
    frame.removeAttribute("src");
    if (parent) move(parent, frame, next);
    record("retired", { reason, document: retiringDocument, sample });
    return request(new URL("api/release", previous), {}).catch((error) => {
      recordFailure(error, {
        operation: "release",
        document: retiringDocument,
        sample,
      });
      throw error;
    });
  }
  async function replace() {
    await retire("reset");
    allocation++;
    record("queued");
    return settle(
      loadWithinLimit(async (release) => {
        if (destroyed) throw new DOMException("sample destroyed", "AbortError");
        record("allocating");
        /** @type {import("../types/contract.js").ServedSampleAnswer} */
        const { url, page } = await request(
          pageUrl("api/samples"),
          { template, source, message },
          revision ? { "Leaf-View-Revision": String(revision) } : {},
        );
        current = new URL(url, location.href).href;
        samplePage = page;
        record("allocated");
        try {
          if (destroyed) {
            await retire("destroyed");
            throw new DOMException("sample destroyed", "AbortError");
          }
          // The opaque frame cannot expose its document or order cross-process
          // bootstrap messages against load. Admit the server's document contract
          // before native navigation; later authored destinations remain native.
          const admission = await fetch(current, {
            method: "HEAD",
            credentials: "omit",
            signal: lifetimeController.signal,
          });
          record("admission", {
            status: admission.status,
            leafDocument: admission.headers.get("Leaf-Document"),
          });
          if (!admission.ok || !admission.headers.has("Leaf-Document"))
            throw new Error("The sample document did not start Leaf");
          if (destroyed) {
            await retire("destroyed");
            throw new DOMException("sample destroyed", "AbortError");
          }
          const upgraded = interfaceReady();
          // A loaded module graph frees its slot even while Leaf upgrade waits on
          // widget preparation. Native load needs no access to the opaque child document.
          frame.addEventListener("load", release, { once: true });
          record("loading");
          frame.src = current;
          return await upgraded;
        } finally {
          frame.removeEventListener("load", release);
        }
      }, lifetimeController.signal),
    );
  }
  function reset() {
    if (destroyed)
      return Promise.reject(new Error("the sample host has been destroyed"));
    return operation ?? begin(replace());
  }
  /** @template {SampleMethod} K @overload @param {K} method @param {SampleCommands[K]["detail"]} detail @returns {Promise<SampleCommands[K]["result"]>} */
  /** @param {SampleMethod} method @param {SampleCommands[SampleMethod]["detail"]} detail @returns {Promise<SampleResult>} */
  function call(method, detail) {
    const ready = host.ready;
    return ready.then(() => {
      if (ready !== host.ready || !channel) throw lost;
      const port = channel;
      const id = ++nextId;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        port.postMessage({ id, method, detail });
      });
    });
  }
  /** @type {SampleHost} */
  const host = {
    ready: replace(),
    reset,
    // Full view keeps the realm, log and native editor; only its allocation changes.
    setWindow(value) {
      asWindow = value;
      return call("window", { window: value });
    },
    on(type, callback) {
      const callbacks = listeners[type];
      callbacks.add(callback);
      return () => {
        callbacks.delete(callback);
      };
    },
    restoreCurrentLocation: () => call("restore-current-location", {}),
    showThread(id, { signal, ...options }) {
      if (signal.aborted) return Promise.resolve(false);
      const cancel = () => channel?.postMessage({ type: "cancel-view" });
      signal.addEventListener("abort", cancel, { once: true });
      return call("thread", { id, ...options }).finally(() =>
        signal.removeEventListener("abort", cancel),
      );
    },
    destroy() {
      if (closing) return closing;
      destroyed = true;
      record("destroyed");
      lifetimeController.abort(new DOMException("sample destroyed", "AbortError"));
      mounted.delete(frame);
      window.removeEventListener("message", connect);
      frame.removeEventListener("load", loaded);
      window.removeEventListener("pagehide", departing);
      room();
      document.removeEventListener("visibilitychange", visibility);
      seen.stop();
      size.disconnect();
      for (const type of ["beforetoggle"])
        document.removeEventListener(type, nativeTransition, true);
      lifetime.disconnect();
      unwatch();
      undress();
      closing = Promise.all([retire("destroyed"), operation?.catch(() => {})]);
      return closing;
    },
  };
  /** @param {PageTransitionEvent} event */
  const departing = (event) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  mounted.set(frame, call);
  begin(host.ready);
  return host;
}
