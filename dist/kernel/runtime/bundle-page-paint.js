import {
  shownBox,
  tagsDeclaring
} from "./bundle-arrivals.js";
import {
  DELIVERY,
  PAGE_ROOT,
  offlineInteractive,
  pageUrl,
  runtime
} from "./bundle-semantic-state.js";
import {
  CARET_KEYS,
  TEXT_BOX,
  WORKS,
  controlNavigationKeys,
  focusRevision,
  focused,
  isNativeLayer,
  keeps,
  keepsText,
  nextRender,
  onStanding,
  renderedParent,
  sizeObserver,
  takesLetters,
  under
} from "./bundle-frame-visibility.js";
import {
  AsyncDirective,
  Directive,
  PartType,
  Z,
  describeFailure,
  directive,
  html,
  nothing,
  render,
  x
} from "./bundle-queued-work.js";

// runtime/page-paint.js
var PAGE_PAINT_ATTRIBUTE = Object.freeze({
  class: "class",
  obligation: "data-lf-obligation",
  done: "data-lf-done",
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  settlement: "data-lf-state",
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataVersion: "data-lf-data-version",
  source: "data-lf-source",
  sourceRevision: "data-lf-source-revision",
  userOverride: "data-lf-user-override",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  holds: "data-lf-holds",
  scrolls: "data-lf-scrolls",
  sticks: "data-lf-sticks",
  moreBefore: "data-lf-more-before",
  moreAfter: "data-lf-more-after",
  scrollDirection: "data-lf-scroll-direction",
  moreBelow: "data-lf-more-below",
  goto: "data-lf-go-to-active",
  traffic: "data-lf-traffic",
  indicated: "data-lf-indicated",
  // A recording playing through the runtime's controls (video-controls.js).
  player: "data-lf-player",
  // A breakout that keeps to its holder (prepaint.js, `breakouts`).
  kept: "data-lf-kept",
  // Delivery's, not a runtime writer's: the size of the page media an element names
  // (revision_delivery.py, `mark_declared`).
  mediaWidth: "data-lf-media-width",
  mediaHeight: "data-lf-media-height"
});
var pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
var pageUpgraded = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);

// runtime/root-state.js
var setRuntimeRootAttribute = (...args) => document.documentElement.lfInitial.setRuntimeRootAttribute(...args);
var setRuntimeRootStyle = (...args) => document.documentElement.lfInitial.setRuntimeRootStyle(...args);
var removeRuntimeRootStyle = (...args) => document.documentElement.lfInitial.removeRuntimeRootStyle(...args);
var runtimeRootState = (root2) => ({
  attributes: document.documentElement.lfInitial.runtimeRootAttributes(root2),
  styles: document.documentElement.lfInitial.runtimeRootStyles(root2)
});

// runtime/traffic.js
var ledger = { sends: 0, acked: 0, asked: 0, heard: 0, pending: [] };
function paint() {
  setRuntimeRootAttribute(
    document.documentElement,
    PAGE_PAINT_ATTRIBUTE.traffic,
    JSON.stringify(ledger)
  );
}
function countTraffic(key) {
  ledger[key] += 1;
  paint();
}
function watchPendingTraffic(sending2) {
  let first = true;
  return sending2.subscribe((attempts) => {
    const initial = first;
    first = false;
    if (initial && !attempts.length) return;
    ledger.pending = [...attempts];
    paint();
  });
}

// runtime/ids.js
var randomId = () => Array.from(
  crypto.getRandomValues(new Uint8Array(16)),
  (byte) => byte.toString(16).padStart(2, "0")
).join("");

// runtime/interaction-log.js
var enabled = PAGE_ROOT !== null;
var url = enabled ? new URL("api/interaction", PAGE_ROOT).href : null;
var root = enabled ? new URL(PAGE_ROOT).pathname.replace(/\/$/, "") : "";
var session = randomId();
var queue = [];
var MAX_PENDING_ENTRIES = 512;
var repetitive = /* @__PURE__ */ new Set([
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
  "compositionupdate"
]);
var encoder = new window.TextEncoder();
var nodeIds = /* @__PURE__ */ new WeakMap();
var nextSequence = 0;
var nextNodeId = 0;
var sending = false;
var inFlightCount = 0;
var scheduled = null;
var timestamp = () => (/* @__PURE__ */ new Date()).toISOString();
var pagePath = (pathname) => pathname === root || pathname === `${root}/` ? "/" : pathname.startsWith(`${root}/`) ? pathname.slice(root.length) : pathname;
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
      value: (
        /** @type {HTMLSelectElement | HTMLTextAreaElement} */
        target.value
      )
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
    trusted: event.isTrusted
  };
  const target = path[0];
  const control = path.find(
    (node) => node instanceof Element && node.matches(`button, a, summary, input, select, ${TEXT_BOX}, [role=button]`)
  );
  if (control) {
    entry.control = locator(control);
    entry.controlNode = nodeIdentity(control);
  }
  const labelTarget = control ?? target;
  if (labelTarget instanceof Element) {
    const label = labelTarget.getAttribute("aria-label") || labelTarget.getAttribute("title");
    if (label) entry.label = label;
    else if (control) entry.label = control.textContent?.trim().slice(0, 200);
  }
  if (event instanceof window.KeyboardEvent) {
    entry.key = event.key;
    entry.code = event.code;
    entry.repeat = event.repeat;
    entry.modifiers = ["Alt", "Control", "Meta", "Shift"].filter(
      (name) => event.getModifierState(name)
    );
  } else if (event instanceof window.PointerEvent) {
    entry.pointer = {
      id: event.pointerId,
      type: event.pointerType,
      button: event.button,
      buttons: event.buttons,
      x: event.clientX,
      y: event.clientY
    };
  } else if (event instanceof window.WheelEvent) {
    entry.delta = [event.deltaX, event.deltaY, event.deltaMode];
  } else if (event instanceof window.MouseEvent) {
    entry.pointer = {
      button: event.button,
      x: event.clientX,
      y: event.clientY
    };
  }
  if (event instanceof window.InputEvent) {
    entry.inputType = event.inputType;
    entry.data = event.data;
  }
  if (event instanceof window.CompositionEvent) entry.data = event.data;
  if (event instanceof window.ClipboardEvent)
    entry.clipboard = event.clipboardData?.getData("text/plain") ?? "";
  if (event.changedTouches)
    entry.touches = [...event.changedTouches].map((touch) => ({
      id: touch.identifier,
      x: touch.clientX,
      y: touch.clientY
    }));
  if (event instanceof window.DragEvent && event.dataTransfer?.files.length)
    entry.files = [...event.dataTransfer.files].map((file) => ({
      name: file.name,
      size: file.size,
      type: file.type
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
    entry.open = /** @type {Partial<HTMLDetailsElement>} */
    target.open === true || isNativeLayer(target);
  if (event.type === "fullscreenchange")
    entry.fullscreen = document.fullscreenElement ? {
      target: locator(document.fullscreenElement),
      node: nodeIdentity(document.fullscreenElement)
    } : null;
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
      (entry, index) => index >= inFlightCount && entry.repetitive
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
    sequence: ++nextSequence
  };
  let body = JSON.stringify({ ...entry, ...common });
  let bytes = encoder.encode(body).length;
  if (bytes > 4e4) {
    body = JSON.stringify({
      ...common,
      type: "interaction_omitted",
      originalType: entry.type,
      bytes,
      reason: "record_exceeds_limit"
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
    body: `${prefix}${queue.slice(start, start + count).map((row) => row.body).join(",")}]}`
  };
}
function post(body) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    credentials: "same-origin",
    keepalive: encoder.encode(body).length < 6e4
  });
}
async function flush() {
  if (sending || !queue.length) return;
  sending = true;
  const { count, body } = batch(0, 1e5);
  inFlightCount = count;
  let delay = 250;
  try {
    const response = await post(body);
    if (response.status >= 400 && response.status < 500) {
      console.error(
        `Leaf interaction log rejected ${count} records: ${response.status}`
      );
      queue.splice(0, count);
      return;
    }
    if (!response.ok) throw new Error(`interaction log returned ${response.status}`);
    queue.splice(0, count);
  } catch {
    delay = 2e3;
  } finally {
    inFlightCount = 0;
    sending = false;
    schedule(delay);
  }
}
function recordInteraction(type, detail = {}) {
  enqueue({ type, ...detail });
}
if (enabled) {
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
    "close"
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
    "fullscreenchange"
  ]) {
    window.addEventListener(type, (event) => enqueue(describe(event)), true);
  }
  document.addEventListener("lf-command-invoked", (event) => {
    const active = focused();
    enqueue({
      type: "command",
      ...event.detail,
      focus: active ? { target: locator(active), node: nodeIdentity(active) } : null,
      scroll: [window.scrollX, window.scrollY]
    });
  });
  const observer = new window.PerformanceObserver((list) => {
    for (
      const resource of
      /** @type {PerformanceResourceTiming[]} */
      list.getEntries()
    ) {
      if (resource.name.startsWith(url)) continue;
      const resourceUrl = new URL(resource.name);
      if (pagePath(resourceUrl.pathname) === "/api/news") continue;
      enqueue({
        type: "resource",
        path: pagePath(resourceUrl.pathname),
        initiator: resource.initiatorType,
        durationMs: resource.duration,
        // WebKit has no responseStatus.
        responseStatus: resource.responseStatus ?? null,
        transferSize: resource.transferSize
      });
    }
  });
  observer.observe({ type: "resource", buffered: true });
  enqueue({
    type: "session_start",
    location: `${pagePath(location.pathname)}${location.hash}`,
    viewport: [window.innerWidth, window.innerHeight],
    userAgent: navigator.userAgent
  });
  window.addEventListener(
    "pagehide",
    () => {
      for (let start = 0; start < queue.length; ) {
        const { count, body } = batch(start, 48e3);
        start += count;
        void post(body).catch(() => {
        });
      }
    },
    true
  );
}

// runtime/pointer.js
var x2 = -1;
var y = -1;
var remember = (ev) => {
  x2 = ev.clientX;
  y = ev.clientY;
};
document.addEventListener("pointermove", remember, { capture: true });
document.addEventListener("pointerdown", remember, { capture: true });
var pointerAt = () => ({ x: x2, y });
var coarsePointer = matchMedia("(pointer: coarse)");
var hoveringPointer = matchMedia("(hover: hover)");
var pressIsKeyboardActivation = (event) => event.type === "click" && !event.detail;
var plainPress = (event) => event.button === 0 && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
function restorePointer(point) {
  if (x2 !== -1 || y !== -1 || !Number.isFinite(point?.x) || !Number.isFinite(point?.y))
    return;
  x2 = point.x;
  y = point.y;
}

// runtime/keyboard/bindings.js
var MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
var GLYPH = {
  Enter: "\u23CE",
  " ": "space",
  Escape: "esc",
  ArrowUp: "\u2191",
  ArrowDown: "\u2193",
  ArrowLeft: "\u2190",
  ArrowRight: "\u2192",
  Home: "home",
  End: "end",
  Tab: "\u21E5",
  // Mod is the platform's own modifier, and the matcher takes either it or Ctrl
  // (below): a chip says ⌘⏎ on a Mac and Ctrl+⏎ answers there too. A key that works
  // beyond what a surface promises is not a surface promising what does not work, which
  // is the rule this layer keeps.
  Mod: MAC ? "\u2318" : "Ctrl",
  Shift: MAC ? "\u21E7" : "Shift",
  Alt: MAC ? "\u2325" : "Alt"
};
var MODIFIERS = ["Mod", "Alt", "Shift"];
var parsed = (binding) => {
  const mods = binding.split("+");
  return { key: mods.pop(), mods };
};
var spell = (binding) => {
  const { key, mods } = parsed(binding);
  if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key))
    return key.toUpperCase();
  return mods.reduceRight((rest, mod) => {
    const glyph = GLYPH[mod] ?? mod;
    return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
  }, GLYPH[key] ?? key);
};
var softKeyboard = () => coarsePointer.matches;
var submitBindings = () => softKeyboard() ? ["Mod+Enter"] : ["Enter", "Mod+Enter"];
var submitLabel = () => spell(submitBindings()[0]);
var advertisesKeys = () => !coarsePointer.matches;
var spokenBinding = (binding) => {
  const { key, mods } = parsed(binding);
  const spokenModifier = (mod) => {
    if (mod === "Mod") return MAC ? "Command" : "Control";
    return mod;
  };
  const spokenKey = key === " " ? "Space" : key;
  return [...mods.map(spokenModifier), spokenKey].join("+");
};
var word = (cell) => typeof cell === "function" ? cell() : cell;
var declaredBindings = (row) => word(row.keys) ?? [];
var contextBindings = (row) => word(row.contextKeys) ?? [];
var titleOf = (row) => {
  const title = word(row.title);
  if (typeof title !== "string" || !title.trim())
    throw new TypeError(
      `leaf: ${row.id} has no command title; expected non-empty text`
    );
  return title;
};
var descriptionOf = (row) => word(row.description) ?? "";
var allBindings = (row) => [
  .../* @__PURE__ */ new Set([
    ...declaredBindings(row),
    ...contextBindings(row),
    ...commandRoutes(row).flatMap(contextBindings)
  ])
];
var commandRoutes = (row) => word(row.routes) ?? [];
var commandBinding = (row, route = null) => route ? route.binding ?? contextBindings(route)[0] : declaredBindings(row)[0] ?? contextBindings(row)[0];
var ROUTED_COMMAND = /* @__PURE__ */ Symbol("a routed command reference");
var contextualRoute = (route, command) => ({
  ...route,
  [ROUTED_COMMAND]: command
});
var routedCommand = (route) => route?.[ROUTED_COMMAND] ?? null;
var quickShortcuts = () => document.documentElement.lfKeyboard.quick;
var setQuickShortcuts = (on) => document.documentElement.lfKeyboard.setQuick(on);
var bindingEnabledFor = (binding, quick) => {
  const { key, mods } = parsed(binding);
  return quick || key.length !== 1 || key === " " || mods.some((mod) => mod !== "Shift");
};
var bindingEnabled = (binding) => bindingEnabledFor(binding, quickShortcuts());
var bindings = (row) => declaredBindings(row).filter(bindingEnabled);
var commandEntries = (row, active = bindings(row), { includeUnavailable = false } = {}) => {
  const routes = commandRoutes(row);
  if (!routes.length)
    return includeUnavailable || commandAvailable(row) ? [{ id: row.id, binding: active[0], route: null }] : [];
  return routes.filter(
    (route) => (includeUnavailable || commandAvailable(row, route)) && (active.includes(route.binding) || contextBindings(route).some((binding) => active.includes(binding)))
  ).map((route) => ({
    id: route.id,
    binding: route.binding ?? active.find((binding) => contextBindings(route).includes(binding)),
    route
  }));
};
var commandPresentations = (row, active = bindings(row), options = {}) => {
  if (row.runFromCommandReference === false) return [{ id: row.id, route: null }];
  return commandEntries(row, active, options);
};
var labelOf = (row) => {
  const label = word(row.label);
  if (label !== void 0 && label !== null) return label;
  return bindings(row).map(spell).join(" / ");
};
var controlOutputs = /* @__PURE__ */ new WeakMap();
function controlAvailabilityOutput(control, owner, fields = null) {
  let outputs = controlOutputs.get(control);
  if (!fields) {
    outputs?.delete(owner);
    return;
  }
  if (!outputs) controlOutputs.set(control, outputs = /* @__PURE__ */ new Map());
  outputs.set(owner, fields);
}
function disabledByFieldset(control) {
  for (let parent = control.parentElement; parent; parent = parent.parentElement) {
    if (parent.localName !== "fieldset" || !parent.disabled) continue;
    const legend = [...parent.children].find((child) => child.localName === "legend");
    if (!legend?.contains(control)) return true;
  }
  return false;
}
function controlAvailable(control) {
  if (!control?.isConnected) return false;
  const outputs = [...controlOutputs.get(control)?.values() ?? []];
  const disabled = outputs.some((fields) => fields.disabled) ? disabledByFieldset(control) : control.matches(":disabled");
  const ariaDisabled = !outputs.some((fields) => fields.ariaDisabled) && control.getAttribute("aria-disabled") === "true";
  return !disabled && !ariaDisabled;
}
var declaredCommandAvailable = (row, route = null) => commandReady(row, route) && (!row.when || row.when()) && (!route?.when || route.when());
var scopeReadiness = /* @__PURE__ */ new WeakMap();
var savedReadingSettled = () => runtime.statePhase !== "waiting";
function declareCommandReadiness(rows, ready) {
  if (ready !== void 0 && typeof ready !== "function")
    throw new TypeError("leaf: scope readiness must be a function");
  if (ready) for (const row of rows) scopeReadiness.set(row, ready);
}
var commandReady = (row, route = null) => {
  const saved = savedReadingSettled();
  if ((row.decision || route?.decision) && !saved) return false;
  const reference = routedCommand(route);
  if (reference) {
    const entry = referencedCommandEntry(reference, { includeUnavailable: true });
    if (entry && !commandReady(reference.row, entry.route)) return false;
  }
  const ready = route?.ready ?? row.ready ?? scopeReadiness.get(row);
  return ready ? ready() : true;
};
var scopeAvailable = (scope) => !commandReady(scope) || !scope.when || scope.when();
var commandAvailable = (row, route = null) => {
  const control = route?.control ?? row.control;
  const reference = routedCommand(route);
  return declaredCommandAvailable(row, route) && (control === void 0 || controlAvailable(word(control))) && (!reference || referencedCommandEntry(reference) !== null);
};
function referencedCommandEntry(reference, options) {
  if (!reference.source.isConnected || !reference.scope.rows.includes(reference.row) || !scopeAvailable(reference.scope))
    return null;
  return commandEntries(reference.row, allBindings(reference.row), options).find(
    ({ id, binding }) => id === reference.id && (binding ?? null) === reference.binding
  ) ?? null;
}
var live = (row) => {
  const routes = commandRoutes(row);
  return routes.length ? routes.some((route) => commandAvailable(row, route)) : commandAvailable(row);
};
var availableBindings = (row, declared) => declared.filter((binding) => commandEntries(row, [binding]).length > 0);
var touchPresses = (row) => row.touch ? [{ id: row.id, row, binding: void 0, words: row.touch }] : [];
var COMMAND_ID = /^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$/;
var canonicalBinding = (binding) => {
  const { key: declaredKey, mods } = parsed(binding);
  const key = declaredKey === "Space" ? " " : declaredKey;
  const letter = key.length === 1 && key.toLowerCase() !== key.toUpperCase();
  const named = key === " " || key.length > 1;
  const canonicalKey = letter ? key.toLowerCase() : key;
  const canonicalMods = MODIFIERS.filter(
    (mod) => mods.includes(mod) && (mod !== "Shift" || letter || named)
  );
  return [...canonicalMods, canonicalKey].join("+");
};
function validateActive(active, where, bindingOf) {
  const owners = /* @__PURE__ */ new Map();
  for (const row of active)
    for (const binding of bindingOf(row)) {
      const identity = canonicalBinding(binding);
      const prior = owners.get(identity);
      if (prior)
        throw new Error(
          `leaf: ${where} has two live meanings for ${binding}: ${titleOf(prior)}; ${titleOf(row)}`
        );
      owners.set(identity, row);
    }
  return active;
}
var validateRows = (rows, where = "a scope") => {
  const active = rows.filter(live);
  validateActive(active, where, (row) => availableBindings(row, declaredBindings(row)));
  return validateActive(
    active,
    where,
    (row) => availableBindings(row, [
      ...contextBindings(row),
      ...commandRoutes(row).flatMap(contextBindings)
    ])
  );
};
function activeRows(rows, where = "a scope") {
  const active = rows.filter((row) => live(row) && bindings(row).length > 0);
  return validateActive(active, where, (row) => availableBindings(row, bindings(row)));
}
function decisionControls(commands, where = "an obligation") {
  const controls = /* @__PURE__ */ new Map();
  for (const { source, scope, row } of commands) {
    const routes = commandRoutes(row);
    const candidates = [
      ...row.decision ? [{ row, route: null }] : [],
      ...routes.filter((route) => route.decision).map((route) => ({ row, route }))
    ];
    for (const { route } of candidates) {
      const contribution = route ?? row;
      const control = word(contribution.control ?? row.control);
      const label = titleOf(contribution);
      const bindingBadge = word(
        contribution.bindingBadge !== void 0 ? contribution.bindingBadge : row.bindingBadge
      ) ?? null;
      const active = route ? [route.binding, ...contextBindings(route)].filter(Boolean) : allBindings(row);
      if (control == null) continue;
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} in ${where} has no control`);
      if (bindingBadge !== null && !(bindingBadge instanceof Element))
        throw new TypeError(
          `leaf: ${contribution.id} in ${where} has no Element binding badge`
        );
      const binding = active[0] ?? null;
      const record = {
        id: contribution.id,
        source,
        control,
        label,
        bindingBadge,
        intrinsicBindings: active,
        command: Object.freeze({
          id: contribution.id,
          source,
          scope,
          row,
          binding,
          control
        })
      };
      const prior = controls.get(control);
      if (prior) {
        if (prior.id !== record.id || prior.label !== record.label || prior.bindingBadge !== record.bindingBadge || prior.command.source !== record.command.source || prior.command.scope !== record.command.scope || prior.command.row !== record.command.row)
          throw new TypeError(
            `leaf: one control has two Decision commands in ${where}: ${prior.id} and ${record.id}`
          );
        continue;
      }
      controls.set(control, record);
    }
  }
  return [...controls.values()];
}
var ariaBindings = (binding) => {
  const { key, mods } = parsed(binding);
  const variants = mods.includes("Mod") ? ["Meta", "Control"] : [null];
  return variants.map(
    (modKey) => [...mods.map((mod) => mod === "Mod" ? modKey : mod), key === " " ? "Space" : key].filter(Boolean).join("+")
  );
};
var ariaShortcuts = (rows, current = true, where, includes = () => true) => [
  ...new Set(
    (current ? activeRows(rows, where) : rows).flatMap(
      (row) => bindings(row).filter(
        (binding) => !current || commandEntries(row, [binding]).some(
          (entry) => includes(binding, entry, row)
        )
      ).flatMap(ariaBindings)
    )
  )
].join(" ");
function answers(binding, ev) {
  const { key, mods } = parsed(binding);
  if (mods.includes("Mod") !== (ev.metaKey || ev.ctrlKey)) return false;
  if (mods.includes("Alt") !== ev.altKey) return false;
  const shift = mods.includes("Shift");
  if (key.length === 1 && key.toLowerCase() !== key.toUpperCase())
    return ev.key.toLowerCase() === key.toLowerCase() && ev.shiftKey === shift;
  return key === " " || key.length > 1 ? ev.key === key && ev.shiftKey === shift : ev.key === key && (!shift || ev.shiftKey);
}
function checked(rows, where, ready) {
  declareCommandReadiness(rows, ready);
  const ids = /* @__PURE__ */ new Map();
  const named = (command) => {
    if (typeof command.id !== "string" || !COMMAND_ID.test(command.id))
      throw new Error(
        `leaf: ${where} names ${String(command.id)}, which is not a stable command id`
      );
    const prior = ids.get(command.id);
    if (prior && (!routedCommand(command) || routedCommand(prior) !== routedCommand(command)))
      throw new Error(`leaf: ${where} declares ${command.id} twice`);
    ids.set(command.id, command);
    if (!(typeof command.title === "function" || typeof command.title === "string" && command.title.trim()))
      throw new Error(`leaf: ${command.id} has no command title`);
    if (command.description !== void 0 && typeof command.description !== "string" && typeof command.description !== "function")
      throw new Error(`leaf: ${command.id} has invalid command description`);
    if (command.ready !== void 0 && typeof command.ready !== "function")
      throw new TypeError(`leaf: ${command.id} readiness must be a function`);
    if (command.decision !== void 0 && typeof command.decision !== "boolean")
      throw new Error(
        `leaf: ${command.id} has invalid Decision role; expected a boolean`
      );
  };
  rows.forEach((row, i) => {
    if (!row) throw new TypeError(`${where}: row ${i + 1} is missing`);
    named(row);
    if (row.decision && row.control == null)
      throw new Error(`leaf: ${row.id} is a Decision command with no control`);
    if (row.native && !row.run)
      throw new Error(
        `leaf: row ${i} of ${where} leaves the native press to the platform but runs no result`
      );
    if (row.exit && (!row.run || row.touch || row.routes))
      throw new Error(
        `leaf: ${row.id} is its stance's way out, which the panel's row offers in its own words, so it needs a run and no touch words or routes`
      );
    if (row.touch && (!row.run || row.routes))
      throw new Error(
        `leaf: ${row.id} stands in for its keys under a finger, so it needs a run and makes one press, with no routes`
      );
    const routes = commandRoutes(row);
    if (routes.length && contextBindings(row).length)
      throw new Error(
        `leaf: ${row.id} owns distinct routes; declare contextKeys on each route`
      );
    const declared = declaredBindings(row);
    const routed = /* @__PURE__ */ new Map();
    const contextual = /* @__PURE__ */ new Map();
    for (const route of routes) {
      named(route);
      if (route.decision && route.control == null && row.control == null)
        throw new Error(
          `leaf: route ${route.id} of ${row.id} is a Decision command with no control`
        );
      if (!declared.includes(route.binding) && !contextBindings(route).length)
        throw new Error(
          `leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`
        );
      for (const [bindings2, owners] of [
        [[route.binding].filter(Boolean), routed],
        [contextBindings(route), contextual]
      ]) {
        for (const binding of bindings2) {
          const prior = owners.get(binding);
          if (prior && prior !== route)
            throw new Error(`leaf: ${row.id} routes ${binding} twice`);
          owners.set(binding, route);
        }
      }
    }
    if (routes.length) {
      const missing = declared.filter((binding) => !routed.has(binding));
      if (missing.length)
        throw new Error(`leaf: ${row.id} has no route for ${missing.join(", ")}`);
    }
    for (const binding of allBindings(row)) {
      for (const mod of parsed(binding).mods)
        if (!MODIFIERS.includes(mod))
          throw new Error(
            `leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier this dispatcher answers (${MODIFIERS.join(", ")})`
          );
      const canonical = canonicalBinding(binding);
      if (binding !== canonical)
        throw new Error(
          `leaf: row ${i} of ${where} binds ${binding}; write the canonical ${canonical.endsWith(" ") ? JSON.stringify(canonical) : canonical}`
        );
    }
  });
  return rows;
}
var PRESS = ["Enter", " "];
var rowArrows = (node) => node.matches(":dir(rtl)") ? ["ArrowRight", "ArrowLeft"] : ["ArrowLeft", "ArrowRight"];
var clampedRow = (rows, current, dir, entry = dir > 0 ? 0 : rows.length - 1) => {
  if (!rows.length) return void 0;
  const at = rows.indexOf(current);
  const next = at < 0 ? entry : at + dir;
  return rows[Math.max(0, Math.min(rows.length - 1, next))];
};
var cycledRow = (rows, current, dir) => {
  if (!rows.length) return { row: void 0, wrapped: false };
  const at = rows.indexOf(current);
  const next = at < 0 ? dir > 0 ? 0 : rows.length - 1 : at + dir;
  const wrapped = next < 0 || next >= rows.length;
  return { row: rows[(next + rows.length) % rows.length], wrapped };
};

// runtime/keyboard/text-entry.js
function EVERYTHING() {
  return true;
}
function CHARACTER(binding) {
  return [...parsed(binding).key].length === 1;
}
var EDITING = /* @__PURE__ */ new Set(["Enter", "Backspace", "Delete", ...CARET_KEYS]);
function TEXT_ENTRY(binding) {
  return CHARACTER(binding) || EDITING.has(parsed(binding).key);
}
function nativeClaimAt(control) {
  if (takesLetters(control)) return TEXT_ENTRY;
  const navigation = controlNavigationKeys(control);
  return navigation.length ? (binding) => navigation.includes(parsed(binding).key) : null;
}
var LINK = "a[href], area[href]";
var ACTIVATION = [
  [LINK, ["Enter"]],
  [
    'button, details > summary, input:is([type="button"], [type="submit"], [type="reset"], [type="image"])',
    PRESS
  ],
  ['input:is([type="checkbox"], [type="radio"])', [" "]]
];
function nativeActivationAt(control) {
  const presses = ACTIVATION.find(([selector]) => control?.matches?.(selector))?.[1];
  return presses ? (binding) => presses.includes(binding) : null;
}

// runtime/repaint.js
var painters = null;
var frame = 0;
var movePage = false;
function mountRepaint(slots) {
  painters = slots;
  onStanding(requestFrame);
  requestFrame();
}
function requestFrame() {
  if (!painters || frame) return;
  frame = nextRender(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
    const p = painters;
    p.reflectFirstScopes?.();
    p.markHere?.();
    p.paintStanding?.();
    p.paintSelectedMarginEntries?.();
    p.paintTouchControls?.();
    p.paintStatusContext?.();
    p.syncLayout?.();
    if (shiftPage) p.pageShifted?.();
    p.paintInputs?.();
    p.paintGoToHints?.();
    p.paintTargetPickerHints?.();
    p.paintCommandHints?.();
    p.paintCoreControls?.();
    p.paintVersionShortcuts?.();
    p.reflectKeys?.();
  });
}
function repaint() {
  requestFrame();
}
function repaintPage() {
  movePage = true;
  requestFrame();
}

// runtime/keyboard/scopes.js
var unpainted = /* @__PURE__ */ new Set();
var buttonsDirty = true;
var wiredButtons = /* @__PURE__ */ new WeakSet();
var buttonReadings = /* @__PURE__ */ new WeakMap();
var buttonCommand = (control) => buttonReadings.get(control);
var buttonBaselines = /* @__PURE__ */ new WeakMap();
var BUTTON_AVAILABILITY = /* @__PURE__ */ Symbol("native command availability");
var commandAvailabilityReaders = /* @__PURE__ */ new Set();
function watchCommandAvailability(read) {
  commandAvailabilityReaders.add(read);
  buttonsDirty = true;
  return () => commandAvailabilityReaders.delete(read);
}
var reflectCommandAvailability = () => {
  for (const read of commandAvailabilityReaders) read();
};
var commandScopeReaders = /* @__PURE__ */ new Set();
function watchCommandScopes(read) {
  commandScopeReaders.add(read);
  buttonsDirty = true;
  return () => commandScopeReaders.delete(read);
}
function* nativeCommandScopes() {
  for (const ref of scopeRefs) {
    const source = ref.deref();
    if (source?.isConnected)
      for (const scope of scopesAt(source)) yield { source, scope };
  }
  for (const read of commandScopeReaders)
    for (const scope of read()) yield { source: document.documentElement, scope };
}
var projectedOnto = (control, scope) => [...projectedScopes.get(control)?.values() ?? []].some(
  (projected) => scopeIdentity(projected) === scopeIdentity(scope)
);
function buttonDeclarations() {
  const declarations = /* @__PURE__ */ new Map();
  for (const { source, scope } of nativeCommandScopes()) {
    if (scope.contextual || scope.sequence) continue;
    for (const row of scope.rows) {
      if (!row.run) continue;
      const routes = commandRoutes(row);
      for (const entry of routes.length ? routes : [row]) {
        const control = word(entry.control ?? row.control);
        if (!(control instanceof HTMLButtonElement) || !control.isConnected) continue;
        if (projectedOnto(control, scope)) continue;
        if (!declarations.has(control)) declarations.set(control, []);
        const candidates = declarations.get(control);
        if (!candidates.some(
          (candidate) => candidate.row === row && candidate.entry.id === entry.id
        ))
          candidates.push({ source, scope, row, entry });
      }
    }
  }
  return declarations;
}
function chosenCommand(candidates) {
  const available = candidates.filter(
    ({ scope, row, entry }) => (!scope.when || scope.when()) && declaredCommandAvailable(row, entry === row ? null : entry)
  );
  if (available.length > 1)
    throw new TypeError(
      `leaf: ${available[1].entry.id} shares a button with ${available[0].entry.id}`
    );
  return available[0] ?? candidates[0];
}
function buttonCommands() {
  return new Map(
    [...buttonDeclarations()].map(([control, candidates]) => [
      control,
      chosenCommand(candidates)
    ])
  );
}
function releaseButtons(declarations) {
  for (const ref of scopeRefs) {
    const control = ref.deref();
    if (!control || !buttonBaselines.has(control) || declarations.has(control))
      continue;
    buttonReadings.delete(control);
    buttonAvailability.get(control)?.();
    buttonAvailability.delete(control);
    const { disabled, ariaDisabled } = buttonBaselines.get(control);
    if (control.disabled !== disabled) control.disabled = disabled;
    keeps(control, "aria-disabled", ariaDisabled);
    buttonBaselines.delete(control);
    controlAvailabilityOutput(control, BUTTON_AVAILABILITY);
    reflectElementShortcuts(control);
    forgetScopedElement(control);
  }
}
var buttonAvailability = /* @__PURE__ */ new WeakMap();
var buttonCandidates = /* @__PURE__ */ new WeakMap();
var sameCandidates = (left, right) => left?.length === right.length && right.every(
  (candidate, index) => candidate.scope === left[index].scope && candidate.row === left[index].row && candidate.entry === left[index].entry
);
function reflectButton(control, candidates) {
  buttonAvailability.get(control)?.();
  buttonCandidates.set(control, candidates);
  const ref = new WeakRef(control);
  let reading = candidates;
  let failure = null;
  const dispose = x(() => {
    if (reading) {
      const read = reading;
      reading = null;
      try {
        focusRevision();
        const command = chosenCommand(read);
        const { scope, row, entry } = command;
        const disabled = Boolean(
          scope.when && !scope.when() || !commandAvailable(row, entry === row ? null : entry)
        );
        keeps(ref.deref(), "aria-disabled", disabled ? "true" : null);
        buttonReadings.set(ref.deref(), command);
      } catch (error) {
        failure = error;
      }
      return;
    }
    const moved = ref.deref();
    if (moved) {
      dirtyButtons.add(moved);
      repaint();
    } else dispose();
  });
  buttonAvailability.set(control, dispose);
  if (failure) throw failure;
}
function claimButton(control) {
  if (!buttonBaselines.has(control))
    buttonBaselines.set(control, {
      disabled: control.disabled,
      ariaDisabled: control.getAttribute("aria-disabled")
    });
  controlAvailabilityOutput(control, BUTTON_AVAILABILITY, {
    disabled: true,
    ariaDisabled: true
  });
  if (control.disabled) control.disabled = false;
  rememberScopedElement(control);
}
function wireButton(control) {
  claimButton(control);
  if (wiredButtons.has(control)) return;
  wiredButtons.add(control);
  control.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    const command = buttonCommands().get(control);
    if (!command) return;
    event.preventDefault();
    if (command.scope.when && !command.scope.when() || !commandAvailable(
      command.row,
      command.entry === command.row ? null : command.entry
    ))
      return;
    command.row.run(
      commandBinding(command.row, command.entry === command.row ? null : command.entry)
    );
  });
}
function wireDeclaredButtons(scope) {
  if (scope.contextual || scope.sequence) return;
  for (const row of scope.rows) {
    if (!row.run || typeof row.routes === "function") continue;
    for (const entry of row.routes?.length ? row.routes : [row]) {
      const control = entry.control ?? row.control;
      if (control instanceof HTMLButtonElement && !projectedOnto(control, scope))
        wireButton(control);
    }
  }
}
var either = (a, b) => a && b ? () => a() || b() : void 0;
var elementScopes = /* @__PURE__ */ new WeakMap();
var projectedScopes = /* @__PURE__ */ new WeakMap();
var commandScopeCapabilities = /* @__PURE__ */ new WeakSet();
var scopeIdentity = (scope) => scope.identity ?? scope;
var isCommandScope = (capability) => capability != null && commandScopeCapabilities.has(capability);
var localContexts = /* @__PURE__ */ new WeakMap();
function localContext(source, scope) {
  let contexts = localContexts.get(source);
  if (!contexts) localContexts.set(source, contexts = /* @__PURE__ */ new WeakMap());
  let contextual = contexts.get(scope);
  if (!contextual) {
    contextual = {
      identity: Object.freeze({}),
      title: scope.title,
      contextual: true,
      el: source,
      when: scope.when,
      ready: scope.ready,
      get rows() {
        return contextRows([{ source, scope }]);
      }
    };
    contexts.set(scope, contextual);
  }
  return contextual;
}
var scopesAt = (element) => {
  const original = [
    elementScopes.get(element),
    ...projectedScopes.get(element)?.values() ?? []
  ].filter(Boolean);
  return original.flatMap(
    (scope) => scope.contextual ? [scope] : [scope, localContext(element, scope)]
  );
};
var contextRowsBySource = /* @__PURE__ */ new WeakMap();
function contextRows(declarations) {
  return declarations.flatMap(({ source, scope, rows = scope.rows }) => {
    let scopes = contextRowsBySource.get(source);
    if (!scopes) contextRowsBySource.set(source, scopes = /* @__PURE__ */ new WeakMap());
    let rowsBySource = scopes.get(scope);
    if (!rowsBySource) scopes.set(scope, rowsBySource = /* @__PURE__ */ new WeakMap());
    return rows.flatMap((row) => {
      const contributions = () => commandRoutes(row).length ? commandRoutes(row) : [row];
      if (!contributions().some((contribution) => contextBindings(contribution).length))
        return [];
      let contextual = rowsBySource.get(row);
      if (!contextual) {
        contextual = {
          id: row.id,
          title: () => titleOf(row),
          description: () => descriptionOf(row),
          get keys() {
            return this.routes.map(({ binding }) => binding);
          },
          get routes() {
            return contributions().flatMap((contribution) => {
              const aliases = contextBindings(contribution);
              const reference = Object.freeze({
                id: contribution.id,
                source,
                scope,
                row,
                binding: commandBinding(
                  row,
                  contribution === row ? null : contribution
                ),
                get control() {
                  return word(contribution.control ?? row.control);
                }
              });
              return aliases.map(
                (binding) => contextualRoute(
                  {
                    id: contribution.id,
                    binding,
                    title: () => titleOf(contribution),
                    description: () => descriptionOf(contribution),
                    control: contribution.control ?? row.control,
                    bindingBadge: contribution.bindingBadge !== void 0 ? contribution.bindingBadge : row.bindingBadge,
                    intrinsicBindings: contribution === row ? declaredBindings(row) : contribution.binding ? [contribution.binding] : []
                  },
                  reference
                )
              );
            });
          },
          when: () => source.isConnected && scopesAt(source).includes(scope) && (!scope.when || scope.when()) && scope.rows.includes(row) && live(row)
        };
        rowsBySource.set(row, contextual);
      }
      return [contextual];
    });
  });
}
var contextScopeReaders = /* @__PURE__ */ new Set();
function contextScopes(title, resolve) {
  const identity = Object.freeze({});
  const read = (origin) => {
    const projection = resolve(origin);
    if (!projection) return null;
    return {
      identity,
      title,
      contextual: true,
      el: projection.root,
      get rows() {
        return contextRows(word(projection.declarations));
      }
    };
  };
  contextScopeReaders.add(read);
  return () => contextScopeReaders.delete(read);
}
var scopeRefs = /* @__PURE__ */ new Set();
var scopeRefFor = /* @__PURE__ */ new WeakMap();
var pruneScopedElements = () => {
  for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
function rememberScopedElement(el2) {
  if (scopeRefFor.has(el2)) return;
  const ref = new WeakRef(el2);
  scopeRefFor.set(el2, ref);
  scopeRefs.add(ref);
}
function forgetScopedElement(el2) {
  if (elementScopes.has(el2) || projectedScopes.has(el2) || buttonBaselines.has(el2))
    return;
  const ref = scopeRefFor.get(el2);
  if (ref) scopeRefs.delete(ref);
  scopeRefFor.delete(el2);
}
function merge(sections, { title, when, at, liveInCommandReference, rows }) {
  if (when && !when()) return;
  const seen = sections.get(title);
  if (!seen) {
    sections.set(title, {
      title,
      when,
      at,
      liveInCommandReference,
      rows: new Map(rows)
    });
    return;
  }
  for (const [key, row] of rows) seen.rows.set(key, row);
  seen.when = either(seen.when, when);
  seen.at = either(seen.at, at);
  seen.liveInCommandReference ||= liveInCommandReference;
}
function attachScope(where, declaration) {
  const scope = { ...declaration, el: where, validated: false };
  unpainted.delete(elementScopes.get(where));
  elementScopes.set(where, scope);
  unpainted.add(scope);
  wireDeclaredButtons(scope);
  rememberScopedElement(where);
  buttonsDirty = true;
  repaint();
  return scope;
}
function detachScope(element, scope) {
  if (elementScopes.get(element) !== scope) return false;
  unpainted.delete(scope);
  elementScopes.delete(element);
  forgetScopedElement(element);
  buttonsDirty = true;
  reflectElementShortcuts(element);
  return true;
}
function declaredScope(title, rows, options) {
  const { when, escape, ready, claims } = typeof options === "function" ? { when: options } : options ?? {};
  if (escape !== void 0 && escape !== "inner")
    throw new TypeError(
      `A command scope's Escape ownership must be "inner", got ${String(escape)}`
    );
  return {
    title,
    rows: checked(rows, title ?? "a scope", ready),
    when,
    escape,
    ready,
    claims
  };
}
function keys(where, title, rows, options) {
  if (rows === void 0 && isCommandScope(title))
    return attachScope(where, title.scope).rows;
  return attachScope(where, declaredScope(title, rows, options)).rows;
}
var commandsOn = directive(
  class extends AsyncDirective {
    #element;
    #declaration;
    #scope = null;
    constructor(part) {
      super(part);
      if (part.type !== PartType.ELEMENT)
        throw new TypeError("commandsOn belongs in a template's element part");
    }
    // The values the template passes, which `update` reads.
    render(title, rows, options) {
      return nothing;
    }
    update(part, [title, rows, options]) {
      this.#element = part.element;
      this.#declaration = rows === void 0 && isCommandScope(title) ? title.scope : declaredScope(
        title,
        typeof rows === "function" ? rows(part.element) : rows,
        options
      );
      if (this.isConnected) this.reconnected();
      return nothing;
    }
    reconnected() {
      this.#scope = attachScope(this.#element, this.#declaration);
    }
    disconnected() {
      if (detachScope(this.#element, this.#scope)) repaint();
    }
  }
);
function commandScope(title, rows, options) {
  const scope = {
    ...declaredScope(title, rows, options),
    identity: Object.freeze({})
  };
  validateRows(scope.rows, title ?? "a scope");
  const capability = Object.freeze({ scope });
  commandScopeCapabilities.add(capability);
  return capability;
}
function projectCommandScope(control, projector, capability = null) {
  dirtyButtons.add(control);
  const projections = projectedScopes.get(control) ?? /* @__PURE__ */ new Map();
  if (capability == null) {
    projections.delete(projector);
    if (!projections.size) {
      projectedScopes.delete(control);
      forgetScopedElement(control);
    }
    reflectElementShortcuts(control);
    return;
  }
  projections.set(projector, capability.scope);
  projectedScopes.set(control, projections);
  wireDeclaredButtons(capability.scope);
  rememberScopedElement(control);
  reflectTracked(control);
}
function scopesWithin(root2, activeOnly) {
  pruneScopedElements();
  const found = [];
  const seen = /* @__PURE__ */ new Set();
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (!scoped?.isConnected) continue;
    let inside = false;
    for (let node = scoped; node; node = renderedParent(node))
      if (node === root2) {
        inside = true;
        break;
      }
    if (!inside) continue;
    for (const scope of scopesAt(scoped)) {
      if (scope.contextual) continue;
      if (activeOnly && scope.when && !scope.when()) continue;
      const identity = scopeIdentity(scope);
      if (seen.has(identity)) continue;
      seen.add(identity);
      found.push({ source: scoped, scope });
    }
  }
  return found;
}
var commandDeclarationsWithin = (root2) => scopesWithin(root2, false);
function commandsWithin(root2) {
  return scopesWithin(root2, true).flatMap(
    ({ source, scope }) => scope.rows.filter(live).map((row) => ({ source, scope, row }))
  );
}
function reflectElementShortcuts(element) {
  const available = scopesAt(element).filter((scope) => !scope.when || scope.when());
  for (const scope of available) {
    try {
      validateRows(scope.rows, scope.title ?? "a scope");
    } catch (error) {
      if (scope.el === element && !scope.validated) detachScope(element, scope);
      throw error;
    }
    if (scope.el === element) scope.validated = true;
  }
  const nativeClaims = nativeClaimAt(element);
  const activation = nativeActivationAt(element);
  const ownsControl = available.some(
    (scope) => scope.rows.some(
      (row) => word(row.control) === element || commandRoutes(row).some(
        (route) => word(route.control ?? row.control) === element
      )
    )
  );
  const shortcuts = [
    ...new Set(
      available.flatMap(
        (scope) => ariaShortcuts(
          scope.rows,
          true,
          scope.title ?? "a scope",
          (binding, entry, row) => {
            if (scope.contextual && (nativeClaims?.(binding) || activation?.(binding)))
              return false;
            const control = word(entry.route?.control ?? row.control);
            return !ownsControl || control == null || control === element;
          }
        ).split(" ").filter(Boolean)
      )
    )
  ].join(" ");
  keeps(element, "aria-keyshortcuts", shortcuts || null);
}
function reflectFirstScopes() {
  reflectButtonsTracked();
  for (const scope of [...unpainted]) {
    unpainted.delete(scope);
    reflectTracked(scope.el);
  }
}
var keysDirty = true;
var dirtyElements = /* @__PURE__ */ new Set();
var tracked = /* @__PURE__ */ new WeakMap();
var dirtyButtons = /* @__PURE__ */ new Set();
var availabilityTracking = null;
var availabilityDirty = true;
function reflectAvailabilityReaders() {
  availabilityDirty = false;
  availabilityTracking?.();
  let first = true;
  let failure = null;
  availabilityTracking = x(() => {
    if (first) {
      first = false;
      try {
        focusRevision();
        reflectCommandAvailability();
      } catch (error) {
        failure = error;
      }
      return;
    }
    availabilityDirty = true;
    repaint();
  });
  if (failure) throw failure;
}
function reflectButtonsTracked() {
  if (!buttonsDirty && !dirtyButtons.size && !availabilityDirty) return;
  const every = buttonsDirty;
  buttonsDirty = false;
  for (const control of buttonDeclarations().keys()) claimButton(control);
  const failures = [];
  try {
    reflectAvailabilityReaders();
  } catch (error) {
    failures.push(error);
  }
  const dirty = new Set(dirtyButtons);
  dirtyButtons.clear();
  const declarations = buttonDeclarations();
  releaseButtons(declarations);
  for (const [control, candidates] of declarations) {
    claimButton(control);
    rememberScopedElement(control);
    wireButton(control);
    if (!every && !dirty.has(control) && buttonAvailability.has(control) && sameCandidates(buttonCandidates.get(control), candidates))
      continue;
    try {
      reflectButton(control, candidates);
    } catch (error) {
      failures.push(error);
    }
  }
  for (const failure of failures) reportError(failure);
}
function reflectTracked(element) {
  tracked.get(element)?.();
  const ref = new WeakRef(element);
  let first = true;
  let failure = null;
  const dispose = x(() => {
    if (first) {
      first = false;
      try {
        focusRevision();
        reflectElementShortcuts(ref.deref());
      } catch (error) {
        failure = error;
      }
      return;
    }
    const moved = ref.deref();
    if (moved) {
      dirtyElements.add(moved);
      repaint();
    } else dispose();
  });
  tracked.set(element, dispose);
  if (failure) throw failure;
}
function reflectKeys() {
  if (!keysDirty && !dirtyElements.size) return;
  const every = keysDirty;
  keysDirty = false;
  const dirty = [...dirtyElements];
  dirtyElements.clear();
  reflectButtonsTracked();
  pruneScopedElements();
  const elements = every ? [...scopeRefs].map((ref) => ref.deref()) : dirty;
  for (const scoped of elements) {
    if (!scoped?.isConnected) continue;
    try {
      reflectTracked(scoped);
    } catch (error) {
      reportError(error);
    }
  }
}
var paintKeys = () => {
  keysDirty = true;
  buttonsDirty = true;
  repaint();
};
var paintKeysWithin = (root2) => {
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (scoped && under(scoped, root2)) {
      dirtyElements.add(scoped);
      dirtyButtons.add(scoped);
    }
  }
  repaint();
};
var saying = (rows) => activeRows(rows, "an announced scope").map((row) => `${spoken(row)} ${titleOf(row)}`).join(", ");
var spoken = (row) => {
  const active = bindings(row);
  if (active.some((binding) => parsed(binding).mods.length))
    return active.map(spokenBinding).join(" or ");
  return word(row.label) ?? active.map(spokenBinding).join(" or ");
};
function scopesFor(node) {
  const contexts = [...contextScopeReaders].map((read) => read(node)).filter(Boolean);
  const found = [];
  const seen = /* @__PURE__ */ new Set();
  const collect = (start) => {
    for (let a = start; a; a = renderedParent(a)) {
      for (const scope of [...scopesAt(a), ...contexts.filter(({ el: el2 }) => el2 === a)]) {
        const identity = scopeIdentity(scope);
        if (seen.has(identity)) continue;
        found.push(scope.el ? scope : { ...scope, el: a });
        seen.add(identity);
      }
      if (a.hasAttribute?.("data-lf-thread-surface")) break;
    }
  };
  collect(node);
  return found;
}
var claimsEsc = (node) => scopesFor(node).some(
  (scope) => scope.rows.some((row) => live(row) && bindings(row).includes("Escape"))
);

// runtime/icons.js
var SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';
var ICONS = {
  activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
  add: '<path d="M8 3v10M3 8h10"/>',
  change: '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
  check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
  comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
  cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
  dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  down: '<path d="m4 6.25 4 4 4-4"/>',
  edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
  expand: '<path d="M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75"/>',
  fit: '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
  fold: '<path d="M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5"/>',
  more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
  // What waits on the user, an inbox's tray: the On me mark. The question mark stays
  // with an obligation and with help (`?`).
  inbox: '<path d="M2.75 9.25h2.9l1 1.6h2.7l1-1.6h2.9M2.75 9.25 4.4 4h7.2l1.65 5.25v2.75H2.75z"/>',
  microphone: '<rect x="6" y="2" width="4" height="7" rx="2"/><path d="M4 7.5v.75a4 4 0 0 0 8 0V7.5M8 12.25V14M6 14h4"/><path class="lf-mic-slash" d="M2.5 2.5l11 11"/>',
  next: '<path d="m6 3.5 4.5 4.5L6 12.5"/>',
  pause: '<path d="M5 3v10M11 3v10"/>',
  play: '<path d="m5 3 7 5-7 5z"/>',
  previous: '<path d="m10 3.5-4.5 4.5 4.5 4.5"/>',
  all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
  pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
  question: '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
  reaction: '<circle cx="6.5" cy="8.25" r="4.25"/><circle cx="5" cy="7.25" r=".55" fill="currentColor" stroke="none"/><circle cx="8" cy="7.25" r=".55" fill="currentColor" stroke="none"/><path d="M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4"/>',
  retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
  search: '<circle cx="7" cy="7" r="3.75"/><path d="m10 10 3 3"/>',
  send: SEND,
  sent: SEND,
  start: '<path d="M3.5 3v10M12.5 3.5 6 8l6.5 4.5z"/>',
  subtract: '<path d="M3 8h10"/>',
  unfold: '<path d="M3 8h10M5.5 5.25 8 2.75l2.5 2.5M5.5 10.75 8 13.25l2.5-2.5"/>',
  undo: '<path d="M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1"/>',
  up: '<path d="m4 9.75 4-4 4 4"/>',
  waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>'
};
var iconMarkup = (icon) => {
  const markup = ICONS[icon];
  if (!markup) throw new TypeError(`Unknown Leaf icon: ${icon}`);
  return markup;
};
function iconTemplate(icon, className = "lf-margin-entry-icon") {
  return html`<svg
    viewBox="0 0 16 16"
    focusable="false"
    aria-hidden="true"
    class=${className}
    data-lf-icon=${icon}
    .innerHTML=${iconMarkup(icon)}
  ></svg>`;
}
function iconElement(icon, className = "lf-margin-entry-icon") {
  const holder = document.createDocumentFragment();
  render(iconTemplate(icon, className), holder);
  return holder.querySelector("svg");
}

// runtime/widget-elements.js
function reveal(el2, mayReveal) {
  const chain = [];
  const pending = [];
  let replacedView = false;
  for (let a = el2; a; a = renderedParent(a)) chain.push(a);
  for (const a of chain.reverse()) {
    if (!mayReveal()) break;
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    a.dispatchEvent(
      new CustomEvent("lf-reveal", {
        detail: {
          target: el2,
          mayReveal,
          replacedView: () => {
            replacedView = true;
          },
          present: (ready2) => ready2?.then && pending.push(ready2)
        }
      })
    );
  }
  const ready = Promise.all(pending);
  void ready.catch(() => {
  });
  return { ready, replacedView };
}
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== void 0) node.textContent = text;
  return node;
}
var hands = Z(/* @__PURE__ */ new Set());
var dragHeld = () => hands.value.size > 0;
var dragging = (el2, on) => {
  const held = new Set(hands.peek());
  if (on) held.add(el2);
  else held.delete(el2);
  hands.value = held;
  paintKeysWithin(el2);
};
var LAYOUT = "lf-layout";
var layoutChanged = (el2) => {
  const pending = [];
  el2.dispatchEvent(
    new CustomEvent(LAYOUT, {
      bubbles: true,
      composed: true,
      detail: {
        present: (ready2) => ready2?.then && pending.push(ready2)
      }
    })
  );
  const ready = Promise.all(pending);
  void ready.catch(() => {
  });
  return ready;
};
var measurements = /* @__PURE__ */ new WeakMap();
var drawn = (el2) => {
  const box = shownBox(el2);
  return Boolean(box.width || box.height);
};
var unmeasured = sizeObserver((entries) => {
  const taking = [];
  for (const { target } of entries) {
    if (!drawn(target)) continue;
    unmeasured.unobserve(target);
    taking.push(measurements.get(target));
    measurements.delete(target);
  }
  for (const take of taking) take();
});
function measure(el2, take) {
  if (drawn(el2)) {
    if (measurements.delete(el2)) unmeasured.unobserve(el2);
    return take();
  }
  measurements.set(el2, take);
  unmeasured.observe(el2);
}
function worksInside(node, container) {
  const parts = /* @__PURE__ */ new Set([container.localName]);
  for (let grew = true; grew; ) {
    grew = false;
    for (const tag of tagsDeclaring(
      (entry) => (entry["x-owners"] ?? []).some((owner) => parts.has(owner))
    ))
      if (!parts.has(tag)) {
        parts.add(tag);
        grew = true;
      }
  }
  const held = tagsDeclaring(() => true).filter((tag) => !parts.has(tag));
  const inner = node.closest(
    [...held, WORKS, "[data-lf-offer]", ".lf-msg-sending"].join(",")
  );
  return inner && inner !== container && container.contains(inner) ? inner : null;
}
var offer = (...args) => document.documentElement.lfInitial.offer(...args);
var offerElement = (...args) => document.documentElement.lfInitial.offerElement(...args);
function searchField(cls, { name, label, placeholder = label }) {
  const field = offer("wa-input", `lf-search-field lf-label-hidden ${cls}`);
  field.type = "search";
  field.value = "";
  field.size = "s";
  field.withClear = true;
  field.tabIndex = 0;
  field.name = name;
  field.label = label;
  field.placeholder = placeholder;
  field.autocomplete = "off";
  field.spellcheck = false;
  return field;
}
function elementDirective(name, write) {
  return directive(
    class extends Directive {
      constructor(part) {
        super(part);
        if (part.type !== PartType.ELEMENT)
          throw new TypeError(`${name} belongs in a template's element part`);
      }
      // The values the template passes, which `update` writes.
      render(...args) {
        return nothing;
      }
      update(part, args) {
        write(part.element, ...args);
        return nothing;
      }
    }
  );
}
var offered = elementDirective("offered", offerElement);
function selectableOfferElement(node, role, cls) {
  keeps(node, "role", role);
  keeps(node, "class", cls ? `${cls} lf-ui lf-ui-face` : "lf-ui lf-ui-face");
  keeps(node, "data-lf-gen", "1");
  keeps(node, "data-lf-offer", role);
  keeps(node, "data-lf-selectable-offer", "");
}
function selectableOffer(role, cls, label) {
  const node = document.createElement("span");
  selectableOfferElement(node, role, cls);
  node.tabIndex = 0;
  if (label !== void 0) node.textContent = label;
  return node;
}
var selectableOffered = elementDirective(
  "selectableOffered",
  selectableOfferElement
);
var PRESSABLE = '[data-lf-offer]:not([data-lf-offer=""])';
function reachedForWords(el2) {
  const sel = getSelection();
  return !!sel && !sel.isCollapsed && el2.contains(sel.focusNode);
}
document.addEventListener(
  "click",
  (ev) => {
    if (pressIsKeyboardActivation(ev)) return;
    const control = (
      /** @type {Partial<Element>} */
      ev.target.closest?.(
        "[data-lf-offer]"
      )
    );
    if (control && reachedForWords(control)) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  },
  true
);
function relabel(node, label, { says } = {}) {
  if (typeof says !== "boolean" && says !== "echo")
    throw new TypeError(
      `Say whether this label is the page speaking: true, false, or "echo" for a copy of words it says elsewhere`
    );
  keeps(node, "data-lf-gen", "1");
  node.toggleAttribute("data-lf-said", says === true);
  node.toggleAttribute("data-lf-echo", says === "echo");
  keepsText(node, label);
}
function closeControl({ name, title = name, className = "" }) {
  const control = el(
    "button",
    `lf-btn lf-icon-action lf-quiet-action ${className}`.trim()
  );
  control.type = "button";
  control.append(iconElement("cross", "lf-action-icon"));
  control.setAttribute("aria-label", name);
  control.title = title;
  return control;
}
function responseAction(control, { glyph = null, icon = null, label, behavior = "action", collapse = false }) {
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A response action needs exactly one glyph or icon");
  control.classList.toggle("lf-response-control", true);
  control.classList.toggle("lf-response-action", true);
  keeps(control, "data-lf-behavior", behavior);
  control.toggleAttribute("data-lf-collapse", collapse);
  if (behavior !== "action" && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (behavior === "action") control.removeAttribute("aria-expanded");
  if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
  render(
    html`${icon ? iconTemplate(icon) : html`<span class="lf-response-action-glyph" aria-hidden="true"
              >${glyph}</span
            >`}<span class="lf-response-action-space" aria-hidden="true"> </span
      ><span class="lf-response-action-label">${label}</span>`,
    control
  );
  return control;
}
function motionPreview(label) {
  const preview = offer("div", "lf-motion-preview", label);
  preview.inert = true;
  preview.setAttribute("aria-hidden", "true");
  return preview;
}

// runtime/notifications.js
var liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");
var NOTICE_MS = 4e3;
var noticeTimer = 0;
var showingBackground = null;
var waitingBackground = [];
var userContext = false;
var userHoldTimer = 0;
var noticePresentation = Z(Object.freeze({ message: "", visible: false }));
var noticeReading = () => noticePresentation.value;
var noticeVisible = () => noticePresentation.peek().visible;
var presentNotice = (message, visible) => {
  noticePresentation.value = Object.freeze({ message, visible });
};
function announce(msg) {
  if (liveEl.firstChild) liveEl.replaceChildren();
  setTimeout(() => {
    if (liveEl.firstChild) liveEl.replaceChildren();
    liveEl.append(msg);
  }, 30);
}
function showNotice(msg, background = null) {
  presentNotice(msg, true);
  showingBackground = background;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift()))
      return;
    presentNotice(noticePresentation.peek().message, false);
    showingBackground = null;
  }, NOTICE_MS);
}
function showBackground(entry) {
  while (entry) {
    const message = entry.format(entry.value);
    if (message) {
      showNotice(message, entry);
      return true;
    }
    entry = waitingBackground.shift();
  }
  return false;
}
var textBackground = (message) => ({
  key: "text",
  value: message,
  combine: (_older, newer) => newer,
  format: (value) => value
});
function queueBackground(entry, front = false) {
  const index = waitingBackground.findIndex((waiting) => waiting.key === entry.key);
  if (index >= 0) {
    const [waiting] = waitingBackground.splice(index, 1);
    entry = {
      ...entry,
      value: front ? entry.combine(entry.value, waiting.value) : entry.combine(waiting.value, entry.value)
    };
  }
  if (front) waitingBackground.unshift(entry);
  else waitingBackground.push(entry);
}
function notice(msg, { background = false, announce: speak = true, group = null } = {}) {
  if (speak) announce(msg);
  if (background) {
    const entry = group ?? textBackground(msg);
    if (userContext || userHoldTimer || noticeVisible()) return queueBackground(entry);
    return showBackground(entry);
  }
  if (showingBackground) queueBackground(showingBackground, true);
  showNotice(msg);
}
function yieldNotice() {
  if (showingBackground) queueBackground(showingBackground, true);
  clearTimeout(noticeTimer);
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}
function holdStatus(ms) {
  if (noticeVisible()) yieldNotice();
  clearTimeout(userHoldTimer);
  userHoldTimer = setTimeout(() => {
    userHoldTimer = 0;
    if (userContext || noticeVisible() || !waitingBackground.length) return;
    showBackground(waitingBackground.shift());
  }, ms);
}
function setNoticeContext(active) {
  userContext = active;
  if (active && showingBackground) yieldNotice();
  else if (!active && !userHoldTimer && waitingBackground.length && !noticeVisible()) {
    showBackground(waitingBackground.shift());
  }
}

// runtime/errors.js
var KEPT = 20;
var raised = 0;
var unsaid = [];
var errors = Z(
  /** @type {readonly RaisedError[]} */
  Object.freeze([])
);
var publish = (next) => {
  errors.value = Object.freeze(next.slice(0, KEPT));
};
var errorsReading = () => errors.value;
function raiseError(message, { subject = null, announce: speak = true } = {}) {
  return raise(message, subject, speak, null);
}
function raise(message, subject, speak, replaced) {
  const id = ++raised;
  if (speak && !unsaid.length)
    queueMicrotask(() => {
      announce(unsaid.map((said) => said.replace(/\.$/, "")).join(". "));
      unsaid = [];
    });
  if (speak) unsaid.push(message);
  publish([
    Object.freeze({ id, message, subject, at: Date.now(), passed: false, seen: false }),
    ...errors.peek().filter((entry) => entry.id !== replaced)
  ]);
  return Object.freeze({ id, clear: () => dismissError(id) });
}
function passErrors(ids) {
  if (errors.peek().some((entry) => ids.includes(entry.id) && !entry.passed))
    publish(
      errors.peek().map(
        (entry) => ids.includes(entry.id) && !entry.passed ? Object.freeze({ ...entry, passed: true }) : entry
      )
    );
}
function passErrorsAt(subject) {
  passErrors(
    errors.peek().filter((entry) => entry.subject === subject).map((entry) => entry.id)
  );
}
function seeErrors() {
  if (errors.peek().some((entry) => !entry.seen))
    publish(
      errors.peek().map((entry) => entry.seen ? entry : Object.freeze({ ...entry, seen: true }))
    );
}
function dismissError(id) {
  if (errors.peek().some((entry) => entry.id === id))
    publish(errors.peek().filter((entry) => entry.id !== id));
}
function holdingError({ announce: speak = true } = {}) {
  let held = null;
  let said = null;
  return (message) => {
    if (message === said) return;
    if (message) held = raise(message, null, speak, held?.id ?? null);
    else {
      held?.clear();
      held = null;
    }
    said = message;
  };
}
function dismissErrors() {
  if (errors.peek().length) publish([]);
}

// runtime/layer-client.js
var { layer: layerGeneration, release, probe, runtime: runtimeIdentity } = DELIVERY;
async function sourceMovedOn() {
  if (!probe) return true;
  let response;
  try {
    response = await fetch(probe, { cache: "no-store" });
  } catch {
    return void 0;
  }
  if (response.status === 404) return Boolean(release);
  if (!response.ok) return void 0;
  const servedRelease = response.headers.get("Leaf-Release");
  if (release && servedRelease) return servedRelease !== release;
  if (!sameRuntime(response)) return true;
  const generation = response.headers.get("Leaf-Layer");
  return generation ? generation !== layerGeneration : void 0;
}
var layerReloading = false;
function reloadNow(message) {
  if (layerReloading) return;
  layerReloading = true;
  notice(message);
  location.reload();
}
var asking = false;
var holdWaiting = holdingError();
function reloadDelivery(message) {
  if (layerReloading || asking) return;
  asking = true;
  void (async () => {
    try {
      const moved = await sourceMovedOn();
      if (moved === void 0) return;
      if (!moved) {
        holdWaiting("Waiting for the server to finish updating.");
        return;
      }
      reloadNow(message);
    } finally {
      asking = false;
    }
  })();
}
var sameRuntime = (response) => {
  const served = response.headers.get("Leaf-Runtime");
  return !runtimeIdentity || !served || served === runtimeIdentity;
};
function layerHeaders(headers = {}) {
  return {
    "Leaf-Layer": layerGeneration,
    ...runtimeIdentity && { "Leaf-Runtime": runtimeIdentity },
    ...runtime.currentRevision && {
      "Leaf-View-Revision": String(runtime.currentRevision)
    },
    ...release && { "Leaf-Release": release },
    ...headers
  };
}
var dataHeaders = (held) => held.version === null ? {} : { "Leaf-Data-Version": held.version };
var completeData = (state, held) => state && !state.data.sources ? { ...state, data: held } : state;
var LayerRefused = class extends Error {
};
async function requestJson(url2, init, what) {
  const response = await fetch(url2, { ...init, headers: layerHeaders(init.headers) });
  if (!admitResponse(response))
    throw new LayerRefused(`Leaf's layer changed while requesting ${what}`);
  const text = await response.text();
  const failed = (message, cause) => Object.assign(new Error(message, { cause }), {
    status: response.status,
    body: text
  });
  let answer = null;
  if (response.ok || response.headers.get("Content-Type")?.split(";")[0].trim() === "application/json")
    try {
      answer = JSON.parse(text);
    } catch (error) {
      throw failed(`${what}: HTTP ${response.status}`, error);
    }
  if (!response.ok) {
    const refusal = answer;
    throw Object.assign(failed(refusal?.error ?? `${what}: HTTP ${response.status}`), {
      current: refusal && "current" in refusal ? refusal.current : void 0,
      said: refusal?.error
    });
  }
  return answer;
}
function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  reloadDelivery("Leaf has been updated \u2014 reloading this page.");
  return false;
}
var admitResponse = (response) => admitted(response, true);
var admitReading = (response) => admitted(response, false);
function admitted(response, ofThisLayer) {
  observeSession(response);
  observeKey(response);
  if (!response.ok) return true;
  if (layerReloading) return false;
  const generation = response.headers.get("Leaf-Layer");
  const responseRelease = response.headers.get("Leaf-Release");
  if (ofThisLayer && generation && !sameLayer(generation)) return false;
  if (!sameRuntime(response)) {
    reloadDelivery("Leaf has been updated \u2014 reloading this page.");
    return false;
  }
  if (release && responseRelease && responseRelease !== release) {
    reloadDelivery("Leaf has been updated \u2014 reloading this page.");
    return false;
  }
  holdWaiting(null);
  return true;
}
var sessionMode = release ? "unknown" : "active";
var sessionChannel = release && !document.documentElement.lfSample ? new window.BroadcastChannel(`leaf-session:${release}:${pageUrl("")}`) : null;
function activateSession(broadcast) {
  const activated = sessionMode !== "active";
  sessionMode = "active";
  if (activated) document.dispatchEvent(new Event("lf-session-active"));
  if (broadcast && activated) sessionChannel?.postMessage({ active: true });
}
sessionChannel?.addEventListener("message", (event) => {
  if (event.data?.active === true) activateSession(false);
});
function observeSession(response) {
  const reference = response.headers.get("Leaf-Session-Reference");
  if (/^\d{12}$/.test(reference)) runtime.sessionReference = reference;
  const mode = response.headers.get("Leaf-Session");
  if (mode === "active") activateSession(true);
  else if (mode === "passive" && sessionMode !== "active") sessionMode = "passive";
}
var sessionIsActive = () => sessionMode === "active";
var KEY_REFUSED = 401;
function observeKey(response) {
  runtime.keyRefused = response.status === KEY_REFUSED;
}
var { promise: layerReady, resolve: layerRevealed } = Promise.withResolvers();
var layerKnown = false;
var revealLayer = () => {
  layerKnown = true;
  layerRevealed();
};
var postEvent = async (event, held = runtime.data) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  if (!layerKnown) await layerReady;
  countTraffic("sends");
  recordInteraction("event_post", { kind: event.kind, attempt: event.attempt ?? null });
  let response;
  try {
    response = await fetch(pageUrl("api/event"), {
      method: "POST",
      headers: layerHeaders({
        "Content-Type": "application/json",
        ...dataHeaders(held)
      }),
      body: JSON.stringify(event)
    });
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      status: response.status
    });
  } catch (error) {
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      error: String(error)
    });
    throw error;
  } finally {
    countTraffic("acked");
  }
  if (!admitResponse(response)) return null;
  if (response.status === KEY_REFUSED)
    throw new Error("the server refused this page's key");
  return response;
};
var uploadMedia = async (file) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  await layerReady;
  countTraffic("sends");
  let answer;
  try {
    answer = await requestJson(
      pageUrl("api/media"),
      { method: "POST", headers: { "Content-Type": file.type }, body: file },
      "image upload"
    );
  } catch (error) {
    if (error instanceof LayerRefused) return null;
    throw error;
  } finally {
    countTraffic("acked");
  }
  return answer.path;
};
var reportedReasons = /* @__PURE__ */ new WeakSet();
var reportedPrimitives = /* @__PURE__ */ new Set();
var reportedErrors = /* @__PURE__ */ new Set();
function reportPageError(reason, context = "") {
  if (typeof reason === "object" && reason !== null) reportedReasons.add(reason);
  else reportedPrimitives.add(String(reason));
  const text = exceptionText(reason, context);
  document.documentElement.lfDocumentLifetime.whenActive(`report ${text}`, () => {
    console.error(`leaf: ${text}`);
    if (offlineInteractive) return;
    if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
    reportedErrors.add(text);
    postEvent({
      kind: "error",
      text,
      ...runtime.currentRevision != null && { revision: runtime.currentRevision }
    }).catch(() => {
    });
  });
}
function reportCarried(reason, context = "") {
  const reported = typeof reason === "object" && reason !== null ? reportedReasons.has(reason) : reportedPrimitives.has(String(reason));
  if (!reported) reportPageError(reason, context);
}
function exceptionText(reason, context = "") {
  const message = reason?.message;
  const text = message === void 0 ? String(reason) : `${reason.name || "Error"}: ${message}`;
  const stack = reason?.stack;
  let evidence = !stack ? text : stack.includes(text) ? stack : `${text}
${stack}`;
  if (reason instanceof AggregateError)
    evidence += reason.errors.map((error) => `
${exceptionText(error)}`).join("");
  if (reason?.cause !== void 0)
    evidence += `
Caused by: ${exceptionText(reason.cause)}`;
  if (!context) return evidence;
  const summary = reason instanceof Error ? describeFailure(reason) : message ?? String(reason);
  return `${context}: ${summary}${message === void 0 ? "" : `
${evidence}`}`;
}
window.addEventListener("error", (e) => {
  if (e.message?.startsWith("ResizeObserver loop")) return;
  reportPageError(
    e.error?.stack ? e.error : `${e.message} (${e.filename}:${e.lineno})`
  );
});
window.addEventListener("unhandledrejection", (e) => {
  reportPageError(e.reason);
});

export {
  PAGE_PAINT_ATTRIBUTE,
  pagePresented,
  pageUpgraded,
  setRuntimeRootAttribute,
  setRuntimeRootStyle,
  removeRuntimeRootStyle,
  runtimeRootState,
  countTraffic,
  watchPendingTraffic,
  randomId,
  recordInteraction,
  pointerAt,
  coarsePointer,
  hoveringPointer,
  pressIsKeyboardActivation,
  plainPress,
  restorePointer,
  parsed,
  spell,
  submitBindings,
  submitLabel,
  advertisesKeys,
  spokenBinding,
  word,
  declaredBindings,
  contextBindings,
  titleOf,
  descriptionOf,
  allBindings,
  commandRoutes,
  commandBinding,
  routedCommand,
  quickShortcuts,
  setQuickShortcuts,
  bindingEnabledFor,
  bindingEnabled,
  bindings,
  commandEntries,
  commandPresentations,
  labelOf,
  controlAvailabilityOutput,
  savedReadingSettled,
  declareCommandReadiness,
  commandReady,
  scopeAvailable,
  commandAvailable,
  referencedCommandEntry,
  live,
  touchPresses,
  decisionControls,
  ariaShortcuts,
  answers,
  checked,
  PRESS,
  rowArrows,
  clampedRow,
  cycledRow,
  EVERYTHING,
  TEXT_ENTRY,
  nativeClaimAt,
  LINK,
  nativeActivationAt,
  mountRepaint,
  repaint,
  repaintPage,
  buttonCommand,
  watchCommandAvailability,
  watchCommandScopes,
  scopeIdentity,
  isCommandScope,
  scopesAt,
  contextScopes,
  scopeRefs,
  pruneScopedElements,
  merge,
  keys,
  commandsOn,
  commandScope,
  projectCommandScope,
  commandDeclarationsWithin,
  commandsWithin,
  reflectFirstScopes,
  reflectKeys,
  paintKeys,
  paintKeysWithin,
  saying,
  scopesFor,
  claimsEsc,
  iconTemplate,
  iconElement,
  reveal,
  el,
  dragHeld,
  dragging,
  LAYOUT,
  layoutChanged,
  measure,
  worksInside,
  offer,
  searchField,
  elementDirective,
  offered,
  selectableOffer,
  selectableOffered,
  PRESSABLE,
  reachedForWords,
  relabel,
  closeControl,
  responseAction,
  motionPreview,
  liveEl,
  noticeReading,
  announce,
  notice,
  holdStatus,
  setNoticeContext,
  errorsReading,
  raiseError,
  passErrors,
  passErrorsAt,
  seeErrors,
  dismissError,
  holdingError,
  dismissErrors,
  layerHeaders,
  dataHeaders,
  completeData,
  LayerRefused,
  requestJson,
  sameLayer,
  admitResponse,
  admitReading,
  sessionIsActive,
  revealLayer,
  postEvent,
  uploadMedia,
  reportPageError,
  reportCarried,
  exceptionText
};
