/* One diagnostic record of this tab's browser input. The page event log remains the
   authority for decisions; this stream explains the gestures that led to them.
   Every observation is bounded; oversized content records an omission. Rows carry
   the document's monotonic clock and visibility. A session names
   one document lifetime, so only rows in that session share a browser clock. */
import { TEXT_BOX } from "./control-selectors.js";
import { PAGE_ROOT } from "./context.js";
import { focused } from "./focus.js";
import { isNativeLayer } from "./shadow-tree.js";
import { randomId } from "./ids.js";

// A document with no declared root has no server to record to: an interactive export,
// or a file opened on its own.
const enabled = PAGE_ROOT !== null;
const url = enabled ? new URL("api/interaction", PAGE_ROOT).href : null;
const root = enabled ? new URL(PAGE_ROOT).pathname.replace(/\/$/, "") : "";
const session = randomId();
const queue = [];
// Bound the tab's diagnostic backlog during an outage. Repeated observations
// yield first; the remaining sequence gaps make any loss visible to a reader.
const MAX_PENDING_ENTRIES = 512;
const repetitive = new Set([
  // Timings of deferred imports and heartbeat requests are observations too;
  // their arrival must never evict the user's input from a congested backlog.
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
  "compositionupdate",
]);
const encoder = new window.TextEncoder();
const nodeIds = new WeakMap();
let nextSequence = 0;
let nextNodeId = 0;
let sending = false;
let inFlightCount = 0;
let scheduled = null;

const timestamp = () => new Date().toISOString();
const pagePath = (pathname) =>
  pathname === root || pathname === `${root}/`
    ? "/"
    : pathname.startsWith(`${root}/`)
      ? pathname.slice(root.length)
      : pathname;

function locator(node) {
  const id = node.id ? `#${node.id}` : "";
  const name = node.getAttribute("name");
  const named = name ? `[name=${JSON.stringify(name)}]` : "";
  return `${node.localName}${id}${named}`;
}

function nodeIdentity(node) {
  if (!nodeIds.has(node)) nodeIds.set(node, ++nextNodeId);
  return nodeIds.get(node);
}

function targetValue(target) {
  if (target instanceof window.HTMLInputElement) {
    if (target.type === "checkbox" || target.type === "radio")
      return { checked: target.checked, value: target.value };
    return { value: target.value };
  }
  if (target instanceof Element && target.matches(`${TEXT_BOX}, select`))
    return {
      value: /** @type {HTMLSelectElement | HTMLTextAreaElement} */ (target).value,
    };
  if (target instanceof HTMLElement && target.isContentEditable)
    return { value: target.textContent };
  return {};
}

function describe(event) {
  const path = event.composedPath();
  const elements = path.filter((node) => node instanceof Element).slice(0, 8);
  const entry = {
    type: event.type,
    target: elements.map(locator),
    nodes: elements.map(nodeIdentity),
    trusted: event.isTrusted,
  };
  const target = path[0];
  const control = path.find(
    (node) =>
      node instanceof Element &&
      node.matches(`button, a, summary, input, select, ${TEXT_BOX}, [role=button]`),
  );
  if (control) {
    entry.control = locator(control);
    entry.controlNode = nodeIdentity(control);
  }
  const labelTarget = control ?? target;
  if (labelTarget instanceof Element) {
    const label =
      labelTarget.getAttribute("aria-label") || labelTarget.getAttribute("title");
    if (label) entry.label = label;
    else if (control) entry.label = control.textContent?.trim().slice(0, 200);
  }
  if (event instanceof window.KeyboardEvent) {
    entry.key = event.key;
    entry.code = event.code;
    entry.repeat = event.repeat;
    entry.modifiers = ["Alt", "Control", "Meta", "Shift"].filter((name) =>
      event.getModifierState(name),
    );
  } else if (event instanceof window.PointerEvent) {
    entry.pointer = {
      id: event.pointerId,
      type: event.pointerType,
      button: event.button,
      buttons: event.buttons,
      x: event.clientX,
      y: event.clientY,
    };
  } else if (event instanceof window.WheelEvent) {
    entry.delta = [event.deltaX, event.deltaY, event.deltaMode];
  } else if (event instanceof window.MouseEvent) {
    entry.pointer = {
      button: event.button,
      x: event.clientX,
      y: event.clientY,
    };
  }
  if (event instanceof window.InputEvent) {
    entry.inputType = event.inputType;
    entry.data = event.data;
  }
  if (event instanceof window.CompositionEvent) entry.data = event.data;
  if (event instanceof window.ClipboardEvent)
    entry.clipboard = event.clipboardData?.getData("text/plain") ?? "";
  // Desktop Firefox without a touch screen, and Safari on a Mac, expose no
  // TouchEvent interface, so a touch event is recognized by what it carries.
  if (event.changedTouches)
    entry.touches = [...event.changedTouches].map((touch) => ({
      id: touch.identifier,
      x: touch.clientX,
      y: touch.clientY,
    }));
  if (event instanceof window.DragEvent && event.dataTransfer?.files.length)
    entry.files = [...event.dataTransfer.files].map((file) => ({
      name: file.name,
      size: file.size,
      type: file.type,
    }));
  if (["beforeinput", "input", "change"].includes(event.type))
    Object.assign(entry, targetValue(target));
  if (event.type === "scroll") {
    const scroller = target === document ? document.scrollingElement : target;
    if (scroller instanceof Element)
      entry.scroll = [scroller.scrollLeft, scroller.scrollTop];
  }
  if (event.type === "selectionchange") {
    const selection = document.getSelection();
    entry.selection = selection?.toString() ?? "";
  }
  if (["hashchange", "popstate", "pageshow", "pagehide"].includes(event.type))
    entry.location = `${pagePath(location.pathname)}${location.hash}`;
  if (event.type === "resize") entry.viewport = [window.innerWidth, window.innerHeight];
  if (event.type === "visibilitychange") entry.visibility = document.visibilityState;
  if (["beforetoggle", "toggle"].includes(event.type) && target instanceof Element)
    entry.open =
      /** @type {Partial<HTMLDetailsElement>} */ (target).open === true ||
      isNativeLayer(target);
  if (event.type === "fullscreenchange")
    entry.fullscreen = document.fullscreenElement
      ? {
          target: locator(document.fullscreenElement),
          node: nodeIdentity(document.fullscreenElement),
        }
      : null;
  return entry;
}

function schedule(delay = 250) {
  if (scheduled !== null || sending || !queue.length) return;
  scheduled = setTimeout(() => {
    scheduled = null;
    void flush();
  }, delay);
}

function append(row) {
  if (queue.length >= MAX_PENDING_ENTRIES) {
    let evict = queue.findIndex(
      (entry, index) => index >= inFlightCount && entry.repetitive,
    );
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
  if (!enabled) return;
  const common = {
    observed_at: timestamp(),
    monotonic_ms: performance.now(),
    visibility: document.visibilityState,
    sequence: ++nextSequence,
  };
  let body = JSON.stringify({ ...entry, ...common });
  let bytes = encoder.encode(body).length;
  // Keep large drafts in their editor and semantic log. This diagnostic records
  // their omission, using the original observation's identity and clocks.
  if (bytes > 40_000) {
    body = JSON.stringify({
      ...common,
      type: "interaction_omitted",
      originalType: entry.type,
      bytes,
      reason: "record_exceeds_limit",
    });
    bytes = encoder.encode(body).length;
  }
  append({ body, bytes, repetitive: repetitive.has(entry.type) });
  schedule();
}

function batch(start, maxBytes) {
  const prefix = `{"session":${JSON.stringify(session)},"entries":[`;
  let bytes = encoder.encode(prefix).length + 2;
  let count = 0;
  while (start + count < queue.length && count < 100) {
    const size = queue[start + count].bytes + (count ? 1 : 0);
    if (count && bytes + size > maxBytes) break;
    bytes += size;
    count++;
  }
  return {
    count,
    body: `${prefix}${queue
      .slice(start, start + count)
      .map((row) => row.body)
      .join(",")}]}`,
  };
}

function post(body) {
  // Beacon always includes credentials; explicit fetch semantics also work from
  // an opaque sample, whose capability URL is its authority rather than cookies.
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    credentials: "same-origin",
    keepalive: encoder.encode(body).length < 60_000,
  });
}

async function flush() {
  if (sending || !queue.length) return;
  sending = true;
  const { count, body } = batch(0, 100_000);
  inFlightCount = count;
  let delay = 250;
  try {
    const response = await post(body);
    if (response.status >= 400 && response.status < 500) {
      // A rejected batch cannot become valid by retrying. Its sequence gap is
      // visible in later batches, and the console carries the immediate fault.
      console.error(
        `Leaf interaction log rejected ${count} records: ${response.status}`,
      );
      queue.splice(0, count);
      return;
    }
    if (!response.ok) throw new Error(`interaction log returned ${response.status}`);
    queue.splice(0, count);
  } catch {
    delay = 2000;
  } finally {
    inFlightCount = 0;
    sending = false;
    schedule(delay);
  }
}

export function recordInteraction(type, detail = {}) {
  enqueue({ type, ...detail });
}

if (enabled) {
  // TODO(privacy): Add retention and redaction controls before pages are shared with
  // other users. Input values, selected text, and keyboard input are recorded now.
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
    "close",
  ]) {
    document.addEventListener(type, (event) => enqueue(describe(event)), true);
  }
  for (const type of [
    "pageshow",
    "pagehide",
    "hashchange",
    "popstate",
    "resize",
    "online",
    "offline",
    "fullscreenchange",
  ]) {
    window.addEventListener(type, (event) => enqueue(describe(event)), true);
  }
  document.addEventListener("lf-command-invoked", (event) => {
    const active = focused();
    enqueue({
      type: "command",
      ...event.detail,
      focus: active ? { target: locator(active), node: nodeIdentity(active) } : null,
      scroll: [window.scrollX, window.scrollY],
    });
  });
  const observer = new window.PerformanceObserver((list) => {
    for (const resource of /** @type {PerformanceResourceTiming[]} */ (
      list.getEntries()
    )) {
      if (resource.name.startsWith(url)) continue;
      const resourceUrl = new URL(resource.name);
      // Freshness is transport housekeeping; failed reads are explained by the
      // server diagnostic and the state read they prompt. Logging each look
      // would turn its quiet clock into a second diagnostic request clock.
      if (pagePath(resourceUrl.pathname) === "/api/news") continue;
      enqueue({
        type: "resource",
        path: pagePath(resourceUrl.pathname),
        initiator: resource.initiatorType,
        durationMs: resource.duration,
        // WebKit has no responseStatus.
        responseStatus: resource.responseStatus ?? null,
        transferSize: resource.transferSize,
      });
    }
  });
  observer.observe({ type: "resource", buffered: true });
  enqueue({
    type: "session_start",
    location: `${pagePath(location.pathname)}${location.hash}`,
    viewport: [window.innerWidth, window.innerHeight],
    userAgent: navigator.userAgent,
  });
  window.addEventListener(
    "pagehide",
    () => {
      // Keep the in-flight entries in the queue until their fetch is acknowledged.
      // A closeout may duplicate a batch, identified by session and sequence.
      for (let start = 0; start < queue.length;) {
        const { count, body } = batch(start, 48_000);
        start += count;
        void post(body).catch(() => {});
      }
    },
    true,
  );
}
