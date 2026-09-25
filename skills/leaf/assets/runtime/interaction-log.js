/* One diagnostic record of this tab's browser input. The page event log remains the
   authority for decisions; this stream explains the gestures that led to them. */

const canonical = document.querySelector('link[rel="canonical"][data-lf-runtime]');
const offline = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-offline]',
);
const enabled = Boolean(canonical && !offline);
const url = enabled ? new URL("api/interaction", canonical.href).href : null;
const root = enabled ? new URL(canonical.href).pathname.replace(/\/$/, "") : "";
const session = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
const queue = [];
// Bound the tab's diagnostic backlog during an outage. Repeated observations
// yield first; the remaining sequence gaps make any loss visible to a reader.
const MAX_PENDING_ENTRIES = 512;
const repetitive = new Set([
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
let retryTimer = null;

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
  if (
    target instanceof window.HTMLTextAreaElement ||
    target instanceof window.HTMLSelectElement
  )
    return { value: target.value };
  if (target instanceof Element && target.isContentEditable)
    return { value: target.textContent };
  return {};
}

function describe(event) {
  const path = event.composedPath?.() ?? [event.target];
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
      node.matches("button, a, summary, input, select, textarea, [role=button]"),
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
  if (event instanceof window.TouchEvent)
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
    entry.open = target.matches(":popover-open, dialog[open], details[open]");
  if (event.type === "fullscreenchange")
    entry.fullscreen = document.fullscreenElement
      ? {
          target: locator(document.fullscreenElement),
          node: nodeIdentity(document.fullscreenElement),
        }
      : null;
  return entry;
}

function schedule() {
  if (scheduled !== null || sending || retryTimer !== null || !queue.length) return;
  scheduled = setTimeout(() => {
    scheduled = null;
    void flush();
  }, 250);
}

function groupEnd(start) {
  const row = queue[start];
  if (row.type !== "interaction_part") return start + 1;
  let end = start + 1;
  while (end < queue.length && queue[end].partOf === row.partOf) end++;
  return end;
}

function evictableGroup(repetitiveOnly) {
  let start = 0;
  while (start < queue.length) {
    const end = groupEnd(start);
    if (
      start >= inFlightCount &&
      (!repetitiveOnly ||
        repetitive.has(queue[start].originalType ?? queue[start].type))
    )
      return [start, end];
    start = end;
  }
  return null;
}

function append(rows) {
  if (rows.length > MAX_PENDING_ENTRIES) return;
  while (queue.length + rows.length > MAX_PENDING_ENTRIES) {
    const group = evictableGroup(true) ?? evictableGroup(false);
    if (!group) return;
    queue.splice(group[0], group[1] - group[0]);
  }
  queue.push(...rows);
}

function enqueue(entry) {
  if (!enabled) return;
  const ts = timestamp();
  const row = { ...entry, ts, sequence: nextSequence + 1 };
  const serialized = JSON.stringify(row);
  if (encoder.encode(serialized).length <= 40_000) {
    nextSequence++;
    append([row]);
  } else {
    // Split large pastes and drafts into pieces that fit a pagehide Beacon and
    // the hosted Worker's record limit, subject to the tab's backlog bound.
    const partOf = nextSequence + 1;
    const parts = Math.ceil(serialized.length / 8_000);
    if (parts > MAX_PENDING_ENTRIES) {
      nextSequence += parts;
      append([
        {
          type: "interaction_omitted",
          originalType: entry.type,
          ts,
          sequence: ++nextSequence,
          reason: "record_exceeds_backlog",
          characters: serialized.length,
        },
      ]);
      schedule();
      return;
    }
    const rows = [];
    for (let part = 0; part < parts; part++)
      rows.push({
        type: "interaction_part",
        originalType: entry.type,
        ts,
        sequence: ++nextSequence,
        partOf,
        part,
        parts,
        json: serialized.slice(part * 8_000, (part + 1) * 8_000),
      });
    append(rows);
  }
  schedule();
}

function batch(start, maxBytes) {
  const entries = [];
  let body = "";
  while (start + entries.length < queue.length && entries.length < 100) {
    const candidate = JSON.stringify({
      session,
      entries: [...entries, queue[start + entries.length]],
    });
    if (entries.length && encoder.encode(candidate).length > maxBytes) break;
    entries.push(queue[start + entries.length]);
    body = candidate;
  }
  return { entries, body };
}

async function flush() {
  if (sending || !queue.length) return;
  sending = true;
  const { entries, body } = batch(0, 100_000);
  inFlightCount = entries.length;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      credentials: "same-origin",
      keepalive: encoder.encode(body).length < 60_000,
    });
    if (response.status >= 400 && response.status < 500) {
      // A rejected batch cannot become valid by retrying. Its sequence gap is
      // visible in later batches, and the console carries the immediate fault.
      console.error(
        `Leaf interaction log rejected ${entries.length} records: ${response.status}`,
      );
      queue.splice(0, entries.length);
      return;
    }
    if (!response.ok) throw new Error(`interaction log returned ${response.status}`);
    queue.splice(0, entries.length);
  } catch {
    retryTimer = setTimeout(() => {
      retryTimer = null;
      schedule();
    }, 2000);
  } finally {
    inFlightCount = 0;
    sending = false;
    schedule();
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
  document.addEventListener("lf-command-invoked", (event) =>
    enqueue({ type: "command", ...event.detail }),
  );
  if (typeof window.PerformanceObserver !== "undefined") {
    const observer = new window.PerformanceObserver((list) => {
      for (const resource of list.getEntries()) {
        if (resource.name.startsWith(url)) continue;
        const resourceUrl = new URL(resource.name);
        enqueue({
          type: "resource",
          path: pagePath(resourceUrl.pathname),
          initiator: resource.initiatorType,
          durationMs: resource.duration,
          responseStatus: resource.responseStatus ?? null,
          transferSize: resource.transferSize,
        });
      }
    });
    observer.observe({ type: "resource", buffered: true });
  }
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
        const { entries, body } = batch(start, 48_000);
        start += entries.length;
        if (
          !navigator.sendBeacon(
            url,
            new window.Blob([body], { type: "application/json" }),
          )
        )
          void fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body,
            credentials: "same-origin",
            keepalive: encoder.encode(body).length < 60_000,
          }).catch(() => {});
      }
    },
    true,
  );
}
