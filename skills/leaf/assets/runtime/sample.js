/* A sample owns a disposable served page in an opaque browsing context. Its
 * unguessable page URL grants native requests to its own document, assets and log;
 * presentation commands and observations cross a private port as values.
 * Allocation captures the owning widget's immutable revision. Reset replaces the
 * allocation, admitting its initial document with a credentialless HEAD before
 * native navigation. A later authored navigation keeps the frame and disables its
 * private port; an ordinary reload reconnects.
 * An opaque parent cannot classify a later document which has no Leaf bootstrap.
 * Departed ports cannot settle the replacement's calls.
 * `ready` is the presentation of the sample's next document. When the child
 * document departs, through an authored navigation or a reload, `ready` becomes one
 * promise for the document a reload presents next, which announces itself with
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
 * nonce. Native load is distinct from Leaf presentation;
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
 * `_sample_headers`). A failed allocation or admission retires the allocation before
 * `ready` rejects. */
import { requestJson } from "./layer-client.js";
import { pageUrl, runtime } from "./context.js";
import { dressFor, registerSampleDress } from "./dress.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { containingView, frameView, presented, watchRoom } from "./geometry.js";
import {
  sampleVisibility,
  onSampleVisibility,
  readSampleVisibility,
} from "./sample-visibility.js";
import { keeps } from "./keeps.js";
import { move } from "./dom-move.js";
import { nextRender, sizeObserver } from "./rendering.js";
import { recordInteraction } from "./interaction-log.js";
import { focusDestination } from "./focus.js";
import { enterFrameBy, inLoop, movePast } from "./keyboard/layer-stack.js";
import { aborted } from "./abort.js";

// A page can carry many samples. Their child documents each import the runtime;
// presenting them together can exhaust the browser's request pool before any child
// finishes loading its module graph. Bound simultaneous loads across this page. A
// loaded child can keep reading slow state without holding up the next sample.
const MAX_LOADING_SAMPLES = 3;
let loadingSamples = 0;
const loadWaiters = [];
let nextHost = 0;
async function loadWithinLimit(work, signal) {
  signal.throwIfAborted();
  if (loadingSamples === MAX_LOADING_SAMPLES) {
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
    if (loadWaiters.length) loadWaiters.shift()();
    else loadingSamples--;
  };
  try {
    return await work(release);
  } finally {
    release();
  }
}

// The child document left before answering a call.
const departure = (message) => new DOMException(message, "SampleDepartedError");

const mounted = new Map();
export const isSampleFrame = (node) => mounted.has(node);
// A crop in the frame's viewport coordinates.
export const sampleFrameImage = (frame, crop) => mounted.get(frame).call("image", crop);

const request = (url, body, headers = {}) =>
  requestJson(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      keepalive: true,
    },
    "sample",
  );

export function mountSample(
  frame,
  { template, window: asWindow = false, chrome = undefined },
) {
  if (!template) throw new Error("a sample needs an authored template id");
  // A template is declared in its revision's document or in a message's frozen
  // markup, which the server reads from the log beside the current revision.
  let revision = runtime.currentRevision;
  let message;
  for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
    const descriptor = widgetDescriptor(owner);
    if (!descriptor) continue;
    if (descriptor.document.kind === "page") revision = descriptor.document.revision;
    else message = descriptor.document.message;
    break;
  }
  let current = null;
  let samplePage = null;
  let destroyed = false;
  let operation = null;
  let closing = null;
  let channel = null;
  // Why the last channel closed: what a call aimed at its document rejects with.
  let lost;
  let nextId = 0;
  let readyResolve;
  let readyReject;
  let presenting = false;
  let hasConnected = false;
  let connectedNonce = null;
  const hostId = ++nextHost;
  const started = performance.now();
  let allocation = 0;
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
  const recordFailure = (error, detail = {}) =>
    record("failed", {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
        status: error.status,
        body: error.body,
      },
      ...detail,
    });
  const lifetimeController = new AbortController();
  const candidates = new Set();
  const pending = new Map();
  const listeners = new Map();
  const notify = (type, detail) => {
    for (const callback of listeners.get(type) ?? []) callback(detail);
  };
  keeps(
    frame,
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock",
  );
  frame.toggleAttribute("data-lf-contained", true);

  function admitted() {
    return (
      document.visibilityState === "visible" &&
      presented(frame) &&
      sampleVisibility()?.visible !== false
    );
  }
  // What the containing page admits changes with what stands over the frame, and so
  // does whether the frame stands in a Tab loop (keyboard/layer-stack.js). The child
  // hears the loop first, so its own samples tell theirs on the admission it publishes.
  let looped = null;
  function visibility() {
    const standing = inLoop(frame);
    if (channel && standing !== looped) {
      channel.postMessage({ type: "tab-loop", detail: { standing } });
      looped = standing;
    }
    channel?.postMessage({ type: "visibility", detail: { visible: admitted() } });
  }
  async function readVisibility(port, id) {
    try {
      const outer = await readSampleVisibility();
      if (channel !== port) return;
      const within = outer ? outer.visible && outer : containingView();
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
          error: { name: error.name, message: error.message, stack: error.stack },
        },
      });
      reportError(error);
    }
  }
  function disconnect(reason) {
    channel?.close();
    channel = null;
    looped = null;
    lost = reason;
    connectedNonce = null;
    for (const { reject } of pending.values()) reject(reason);
    pending.clear();
  }
  // Public readiness includes failure retirement. Reset coalesces with an
  // allocation's own operation, so a reported failure already permits a fresh one.
  // A reload's presentation, or a departure's wait, is not an operation: Reset then
  // allocates afresh.
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
  async function settle(work) {
    try {
      return await work;
    } catch (error) {
      // Reset and destroy retire allocations themselves.
      if (error.name !== "AbortError") {
        recordFailure(error);
        await retire("failure", error);
      }
      throw error;
    }
  }
  function presentation() {
    presenting = true;
    return new Promise((resolve, reject) => {
      readyResolve = (value) => {
        presenting = false;
        resolve(value);
      };
      readyReject = (error) => {
        presenting = false;
        reject(error);
      };
    });
  }
  // A departed or replaced document's successor presents into the presentation
  // already pending, so a departure and the reload after it share one `ready`.
  function awaitNext() {
    if (presenting) return;
    host.ready = settle(presentation());
    // Owners read its outcome from `ready`; a host nobody awaits drops it, as an
    // operation's does.
    host.ready.catch(() => {});
  }
  function failure(error) {
    if (presenting) readyReject(error);
    else {
      begin(settle(Promise.reject(error)));
      notify("loading");
    }
  }
  function connect(event) {
    if (
      !current ||
      event.source !== frame.contentWindow ||
      event.data?.sample !== new URL(current).pathname
    )
      return;
    if (
      event.data.type !== "leaf-sample-connect" ||
      typeof event.data.nonce !== "string" ||
      event.data.nonce === connectedNonce
    )
      return;
    const nonce = event.data.nonce;
    const owned = current;
    const pair = new MessageChannel();
    const port = pair.port1;
    // Publish this private document endpoint at the existing diagnostic seam.
    document.querySelector("script[data-lf-entry]").lfDocumentPort = port;
    candidates.add(port);
    port.onmessage = ({ data }) => {
      if (data.type === "connected") {
        if (!candidates.has(port) || current !== owned || data.nonce !== nonce) return;
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
          notify("loading");
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
        notify("departed");
        return;
      }
      if (data.type === "visibility-read") {
        void readVisibility(port, data.detail.id);
        return;
      }
      if (pending.has(data.id)) {
        const { resolve, reject } = pending.get(data.id);
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
        record("presented");
        readyResolve(data.detail);
        // A loop told before the child's runtime listened never reached it.
        looped = null;
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
      else if (data.type === "tab") movePast(frame, data.detail.backward);
      else if (data.type === "step")
        frame.dispatchEvent(
          new CustomEvent("lf-sample-step", {
            bubbles: true,
            composed: true,
            detail: data.detail,
          }),
        );
      else notify(data.type, data.detail);
    };
    event.source.postMessage(
      {
        sample: event.data.sample,
        nonce,
        settings: { window: asWindow, dress: dressFor(frame) ?? undefined, chrome },
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
  const seen = new IntersectionObserver(visibility, { threshold: [0, 1] });
  seen.observe(frame);
  const size = sizeObserver(visibility);
  size.observe(frame);
  const admission = new MutationObserver((records) => {
    if (records.some(({ target }) => target === frame || target.contains(frame)))
      visibility();
  });
  admission.observe(document, {
    subtree: true,
    attributes: true,
    attributeFilter: ["inert", "open", "hidden", "aria-hidden", "class", "style"],
  });
  const nativeTransition = () => nextRender(visibility);
  for (const type of ["beforetoggle"])
    document.addEventListener(type, nativeTransition, true);
  const unwatch = onSampleVisibility(visibility);
  const unenter = enterFrameBy(frame, (backward) => {
    focusDestination(frame, "step");
    channel?.postMessage({ type: "tab-enter", detail: { backward } });
  });
  const undress = registerSampleDress(frame, (dress) =>
    channel?.postMessage({ type: "dress", detail: dress }),
  );
  const lifetime = new MutationObserver(() => {
    if (!frame.isConnected) void host.destroy();
  });
  lifetime.observe(document, { childList: true, subtree: true });

  // What a pending call rejects with: the failure that retires the allocation, or
  // else the owner's cancellation.
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
    readyReject?.(cause);
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
        const { url, page } = await request(
          pageUrl("api/samples"),
          { template, message },
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
          const presented = presentation();
          // A loaded module graph frees its slot even while presentation waits on
          // slow state. Native load needs no access to the opaque child document.
          frame.addEventListener("load", release, { once: true });
          record("loading");
          frame.src = current;
          return await presented;
        } finally {
          frame.removeEventListener("load", release);
        }
      }, lifetimeController.signal),
    );
  }
  function reset() {
    if (destroyed)
      return Promise.reject(new Error("the sample host has been destroyed"));
    if (!operation) begin(replace());
    return operation;
  }
  const host = {
    ready: null,
    reset,
    // Full view keeps the realm, log and native editor; only its allocation changes.
    setWindow(value) {
      asWindow = value;
      return host.call("window", { window: value });
    },
    call(method, detail = {}) {
      const ready = host.ready;
      return ready.then(() => {
        if (ready !== host.ready || !channel) throw lost;
        const id = ++nextId;
        return new Promise((resolve, reject) => {
          pending.set(id, { resolve, reject });
          channel.postMessage({ id, method, detail });
        });
      });
    },
    on(type, callback) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(callback);
      return () => listeners.get(type).delete(callback);
    },
    dress: (dress) => channel?.postMessage({ type: "dress", detail: dress }),
    showThread(id, { signal, ...options }) {
      if (signal.aborted) return Promise.resolve(false);
      const cancel = () => channel?.postMessage({ type: "cancel-view" });
      signal.addEventListener("abort", cancel, { once: true });
      return host
        .call("thread", { id, ...options })
        .finally(() => signal.removeEventListener("abort", cancel));
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
      seen.disconnect();
      size.disconnect();
      admission.disconnect();
      for (const type of ["beforetoggle"])
        document.removeEventListener(type, nativeTransition, true);
      lifetime.disconnect();
      unwatch();
      unenter();
      undress();
      closing = Promise.all([retire("destroyed"), operation?.catch(() => {})]);
      return closing;
    },
  };
  const departing = (event) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  mounted.set(frame, host);
  reset();
  return host;
}
