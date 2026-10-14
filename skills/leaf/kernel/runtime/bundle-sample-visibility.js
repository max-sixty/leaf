import {
  M,
  cancelWork,
  enqueueWork,
  runWork
} from "./bundle-queued-work.js";

// runtime/sample-visibility.js
var child = document.documentElement.lfSample;
var visibility = child ? { visible: false } : null;
var admitted = false;
var intersecting = false;
var observers = /* @__PURE__ */ new Set();
var readings = /* @__PURE__ */ new Map();
var readingId = 0;
var sampleVisibility = () => visibility;
function onSampleVisibility(callback) {
  observers.add(callback);
  return () => observers.delete(callback);
}
function readSampleVisibility() {
  if (!child) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const id = ++readingId;
    readings.set(id, { resolve, reject });
    child.send({ type: "visibility-read", detail: { id } });
  });
}
function publish() {
  visibility = { visible: admitted && intersecting };
  for (const callback of observers) callback(visibility);
}
if (child) {
  child.receive(({ type, detail }) => {
    if (type === "visibility-reading") {
      const reading = readings.get(detail.id);
      readings.delete(detail.id);
      if (detail.error)
        reading?.reject(
          Object.assign(
            new Error(detail.error.message),
            { stack: void 0 },
            detail.error
          )
        );
      else reading?.resolve(detail);
      return;
    }
    if (type !== "visibility") return;
    admitted = detail.visible;
    publish();
  });
  const seen = new IntersectionObserver(
    ([entry]) => {
      const { width, height } = entry.intersectionRect;
      intersecting = width > 0 && height > 0;
      publish();
    },
    // Edge adjacency is already "intersecting" at zero area. A positive threshold
    // makes the first painted pixel a delivery rather than leaving visibility stale.
    { threshold: [0, Number.EPSILON] }
  );
  seen.observe(document.documentElement);
  addEventListener("pagehide", () => seen.disconnect(), { once: true });
}

// runtime/rendering.js
var ROUNDS = 8;
var queued = /* @__PURE__ */ new Map();
var running = null;
var afterPaint = /* @__PURE__ */ new Map();
var lastId = 0;
var frame = 0;
var heard = false;
var quiet = false;
var checking = false;
var preparations = 0;
var preparationObservers = /* @__PURE__ */ new Set();
function observePreparations(observer) {
  preparationObservers.add(observer);
  return () => preparationObservers.delete(observer);
}
function holdRendering() {
  preparations++;
  const serial = ++begun;
  pending.add(serial);
  unsettle();
  const identity = Object.freeze({});
  const observers2 = [...preparationObservers];
  for (const observer of observers2) observer("begin", identity);
  let released2 = false;
  return (phase = "settle") => {
    if (released2) return;
    released2 = true;
    preparations--;
    pending.delete(serial);
    if (updateChecking) heard = true;
    unsettle();
    for (const observer of observers2) observer(phase, identity);
  };
}
function request(into, callback) {
  const id = ++lastId;
  into.set(id, enqueueWork(callback));
  if (!running && !frame) frame = requestAnimationFrame(pass);
  unsettle();
  return id;
}
var nextRender = (callback) => request(queued, callback);
var nextFrame = (callback) => request(running ? afterPaint : queued, callback);
var nextAnimation = (callback) => requestAnimationFrame(callback);
var cancelAnimation = (id) => cancelAnimationFrame(id);
function cancelRender(id) {
  for (const queue of [queued, afterPaint, running]) {
    const job = queue?.get(id);
    if (!job) continue;
    queue.delete(id);
    cancelWork(job);
    return;
  }
}
async function pass(time) {
  frame = 0;
  for (let round = 0; queued.size && round < ROUNDS; round++) {
    running = queued;
    queued = /* @__PURE__ */ new Map();
    for (const [id, job] of running) {
      running.delete(id);
      try {
        runWork(job, time);
      } catch (error) {
        reportError(error);
      }
      await null;
    }
  }
  running = null;
  for (const entry of afterPaint) queued.set(...entry);
  afterPaint = /* @__PURE__ */ new Map();
  if (queued.size) frame = requestAnimationFrame(pass);
}
var owedThisScript = /* @__PURE__ */ new Map();
function settleScript() {
  for (const [callback, job] of owedThisScript) {
    owedThisScript.delete(callback);
    try {
      runWork(job);
    } catch (error) {
      reportError(error);
    }
  }
}
function afterScript(callback) {
  if (!owedThisScript.size) queueMicrotask(settleScript);
  if (!owedThisScript.has(callback))
    owedThisScript.set(callback, enqueueWork(callback));
}
function sizeObserver(callback, { counted = true } = {}) {
  return new ResizeObserver((entries, observer) => {
    if (counted) {
      heard = true;
      unsettle();
    }
    callback(entries, observer);
  });
}
var renderingState = () => {
  const visible = rendered();
  return {
    updatesSettled: quiet || !visible,
    preparationsSettled: preparations === 0 || !visible
  };
};
function rendered() {
  if (document.hidden) return false;
  const sample = sampleVisibility();
  if (sample) return sample.visible;
  for (let view = (
    /** @type {Window} */
    window
  ); view.frameElement; view = view.parent)
    if (!view.frameElement.checkVisibility()) return false;
  return true;
}
function unsettle() {
  quiet = false;
  if (checking) return;
  checking = true;
  requestAnimationFrame(afterUpdate);
}
var updateChecking = false;
var afterUpdate = () => {
  updateChecking = true;
  setTimeout(check);
};
function check() {
  updateChecking = false;
  if (queued.size || heard) {
    heard = false;
    requestAnimationFrame(afterUpdate);
    return;
  }
  checking = false;
  quiet = true;
  const waiting = settling;
  settling = [];
  for (const waiter of waiting)
    if ([...pending].some((serial) => serial > waiter.since)) settling.push(waiter);
    else waiter.settled();
}
var settling = [];
var begun = 0;
var pending = /* @__PURE__ */ new Set();
var owed = () => {
};
function afterSettling(settled) {
  settling.push({ settled, since: begun });
  nextFrame(owed);
}
onSampleVisibility(() => {
  if (sampleVisibility()?.visible) unsettle();
});
unsettle();

// runtime/keeps.js
var keeps = (...args) => document.documentElement.lfInitial.keepsAttribute(...args);
function keepsHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}
function keepsText(node, text) {
  const said = String(text ?? "");
  if (node && node.textContent !== said) node.textContent = said;
}
var atLayoutPrecision = (length) => Math.round(length * 64) / 64;
var layoutPx = (length) => `${atLayoutPrecision(length)}px`;

// runtime/control-selectors.js
var TEXT_FIELD = "leaf-text";
var MODIFIER_KEYS = ["Shift", "Alt", "Control", "Meta"];
var CARET_KEYS = [
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown"
];
var selectsAll = (event) => event.key.toLowerCase() === "a" && (event.metaKey || event.ctrlKey);
var TEXT_BOX = `textarea, ${TEXT_FIELD}`;
var TAB_STOP = `a[href], button, input, select, ${TEXT_BOX}, summary, [contenteditable]:not([contenteditable="false"]), [tabindex]:not([tabindex="-1"])`;
var PRESS_SELECTORS = [
  "a[href]",
  "audio[controls]",
  "button",
  "img[usemap]",
  "input:not([type='hidden'])",
  "label",
  "select",
  "summary",
  TEXT_BOX,
  "video[controls]",
  "[role='button']",
  "[role='checkbox']",
  "[role='combobox']",
  "[role='link']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='option']",
  "[role='radio']",
  "[role='scrollbar']",
  "[role='searchbox']",
  "[role='separator'][tabindex]",
  "[role='slider']",
  "[role='spinbutton']",
  "[role='switch']",
  "[role='tab']",
  "[role='textbox']",
  "[role='treeitem']"
];
var LENT_REACH_STOP = "data-lf-lent-reach-stop";
var REGION_SELECTORS = [
  `[tabindex]:not([tabindex='-1']):not([${LENT_REACH_STOP}])`,
  "[contenteditable]:not([contenteditable='false'])",
  "[draggable='true']",
  "[role='application']",
  "[role='grid']",
  "[role='gridcell']",
  "[role='listbox']",
  "[role='menu']",
  "[role='menubar']",
  "[role='radiogroup']",
  "[role='tablist']",
  "[role='tree']",
  "[role='treegrid']"
];
var PRESSES = PRESS_SELECTORS.join(",");
var WORKS = [...PRESS_SELECTORS, ...REGION_SELECTORS].join(",");

// runtime/shadow-tree.js
var shadowHost = (root) => root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? root.host ?? null : null;
var upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
var renderedParent = (node) => node?.assignedSlot ?? upFrom(node);
var composedParentNode = (node) => node.parentNode ?? shadowHost(node);
var renderedParentNode = (node) => node.assignedSlot ?? composedParentNode(node);
var under = (node, root) => {
  for (let at = node; at; at = composedParentNode(at)) if (at === root) return true;
  return false;
};
var renderedUnder = (node, root) => {
  for (let at = node; at; at = renderedParentNode(at)) if (at === root) return true;
  return false;
};
var renderedChain = (node) => {
  const chain = [];
  for (let at = node; at; at = renderedParent(at)) chain.push(at);
  return chain.reverse();
};
function renderedOrder(a, b) {
  if (a === b) return 0;
  const left = renderedChain(a);
  const right = renderedChain(b);
  let index = 0;
  while (index < left.length && index < right.length && left[index] === right[index])
    index += 1;
  if (index === left.length || index === right.length)
    return left.length - right.length;
  return left[index].compareDocumentPosition(right[index]) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}
var byRenderedOrder = (items, placeOfItem) => {
  const placed2 = items.map((item) => ({ item, place: placeOfItem(item) }));
  return [
    ...placed2.filter(({ place }) => place).sort((a, b) => renderedOrder(a.place, b.place)),
    ...placed2.filter(({ place }) => !place)
  ].map(({ item }) => item);
};
var nativeLayerKind = (node) => {
  if (node?.nodeType !== Node.ELEMENT_NODE || !node.isConnected) return null;
  if (node.matches("dialog:modal")) return "modal";
  return node.matches(":popover-open") ? "popover" : null;
};
var isNativeLayer = (node) => nativeLayerKind(node) !== null;
function nativeLayerHolding(node) {
  for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
  return null;
}

// runtime/focus.js
function* renderedElements(node) {
  const children = node.localName === "slot" ? node.assignedElements({ flatten: true }) : (node.shadowRoot ?? node).children;
  for (const child2 of children) {
    yield child2;
    if (child2.shadowRoot && parseInt(child2.getAttribute("tabindex")) < 0) continue;
    yield* renderedElements(child2);
  }
}
var SEQUENTIAL = `${TAB_STOP}, iframe, audio[controls], video[controls]`;
var tabStops = (root) => [...renderedElements(root)].filter(
  (node) => node.matches(SEQUENTIAL) && node.tabIndex >= 0 && !node.shadowRoot?.delegatesFocus && !node.matches(":disabled") && !node.inert && node.checkVisibility({ visibilityProperty: true })
);
var canPlaceFocus = () => !document.documentElement.lfSample || document.hasFocus();
var CAUSES = /* @__PURE__ */ new Set(["move", "step", "return", "press"]);
function focusDestination(destination, cause2, { caret = null, ...unknown } = {}) {
  if (!CAUSES.has(cause2)) throw new TypeError(`focusDestination: no cause ${cause2}`);
  const unexpected = Object.keys(unknown);
  if (unexpected.length)
    throw new TypeError(`focusDestination: unknown options ${unexpected.join(", ")}`);
  if (!canPlaceFocus()) return;
  placed(cause2, () => {
    destination.focus({ preventScroll: true });
    if (!landedOn(destination) && lendable(destination)) lendStop(destination);
  });
  if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}
function forwardFocus(destination) {
  if (!canPlaceFocus()) return;
  placed(
    placing ?? cause(destination),
    () => destination.focus({ preventScroll: true })
  );
}
var placing = null;
var placed = (cause2, move) => {
  const was = placing;
  placing ??= cause2;
  try {
    return move();
  } finally {
    placing = was;
  }
};
var landedOn = (node) => node === document.body ? node.matches(":focus") : node.getRootNode().activeElement === node || Boolean(node.shadowRoot?.activeElement);
var lendable = (node) => drawn(node) && !node.matches(TAB_STOP);
var lent = /* @__PURE__ */ new WeakSet();
var wearsLentStop = (element) => lent.has(element);
function whenLeft(element, leave) {
  const blur = () => {
    if (element.getRootNode().activeElement === element) return;
    element.removeEventListener("blur", blur);
    leave();
  };
  element.addEventListener("blur", blur);
}
function lendStop(destination) {
  if (destination.hasAttribute("tabindex")) return;
  const giveBack = () => {
    lent.delete(destination);
    if (destination.getAttribute("tabindex") === "-1")
      destination.removeAttribute("tabindex");
  };
  lent.add(destination);
  destination.tabIndex = -1;
  destination.focus({ preventScroll: true });
  if (!landedOn(destination)) {
    giveBack();
    return;
  }
  whenLeft(destination, giveBack);
}
var CARETED = /* @__PURE__ */ new Set(["text", "search", "url", "tel", "password"]);
var holdsCaret = (node) => node.matches(TEXT_BOX) || node.tagName === "INPUT" && CARETED.has(node.type);
function readCaret(node) {
  if (!node || !holdsCaret(node) || node.selectionStart === null) return null;
  return [node.selectionStart, node.selectionEnd, node.selectionDirection];
}
var deepFocus = (at = document.activeElement) => {
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};
var labelPress = null;
var heldByLabel = () => labelPress?.held.isConnected ? labelPress.held : null;
function finishLabelPress() {
  const press2 = labelPress;
  if (!press2) return null;
  labelPress = null;
  return press2;
}
function landLabelPress() {
  if (!finishLabelPress()) return;
  setTimeout(() => {
    if (labelPress) return;
    const at = deepFocus();
    if (at && at !== document.body) return reconcile(null, pressedPath);
    if (!drawn(published?.deref())) return;
    placements += 1;
    stood = null;
    publish2(null, cause(null));
  });
}
var standing = M(0);
var focused = (tree = null) => {
  void standing.value;
  let at = heldByLabel() ?? deepFocus();
  if (tree) while (at && at.getRootNode() !== tree) at = shadowHost(at.getRootNode());
  return at;
};
var selectionOf = (node) => {
  const root = node.getRootNode();
  const own = (
    /** @type {{getSelection?: () => Selection}} */
    root
  );
  return root instanceof ShadowRoot && own.getSelection?.() || getSelection();
};
function standingNodes() {
  const at = focused();
  const selection = getSelection();
  return [
    at && at !== document.body ? at : null,
    selection?.focusNode ?? null,
    selection?.anchorNode ?? null
  ].filter(Boolean);
}
function standsOn(node) {
  if (!node) return false;
  if (standingNodes().some((at) => at === node || node.contains(at))) return true;
  const selection = selectionOf(node);
  return Boolean(selection?.rangeCount && selection.getRangeAt(0).intersectsNode(node));
}
var restoring = false;
var placements = 0;
var stood = null;
var readers = /* @__PURE__ */ new Set();
var onStanding = (read2) => readers.add(read2);
var published = null;
var departed = false;
var readings2 = 0;
var paintDestination = null;
var paintedFocus = null;
var paintedWithin = /* @__PURE__ */ new Set();
function markFocus(node, name, present) {
  keeps(node, `data-lf-${name}`, present ? "" : null);
  if (!present) node.part?.remove(`lf-${name}`);
  else if (node.getRootNode().nodeType === Node.DOCUMENT_FRAGMENT_NODE && node.hasAttribute("part"))
    node.part.add(`lf-${name}`);
}
function paintFocus(node) {
  const next = node === document.body || node === document.documentElement ? null : node;
  if (next !== paintedFocus) {
    if (paintedFocus) markFocus(paintedFocus, "focus", false);
    if (next) markFocus(next, "focus", true);
    paintedFocus = next;
  }
  const within = /* @__PURE__ */ new Set();
  for (let owner = next; owner; owner = renderedParent(owner)) within.add(owner);
  for (const owner of paintedWithin) {
    if (!within.has(owner)) markFocus(owner, "focus-within", false);
  }
  for (const owner of within) {
    if (!paintedWithin.has(owner)) markFocus(owner, "focus-within", true);
  }
  paintedWithin = within;
}
var refreshFocusPaint = () => {
  const node = paintDestination?.deref();
  if (node?.isConnected) watchStandingAround(node);
  paintFocus(node?.isConnected ? node : null);
};
var returnPaintPending = false;
var paintAfterScript = () => {
  if (!returnPaintPending) refreshFocusPaint();
};
var queueFocusPaint = () => afterScript(paintAfterScript);
var queueReturnFocusPaint = () => {
  if (returnPaintPending) return;
  returnPaintPending = true;
  nextRender(() => {
    if (!returnPaintPending) return;
    returnPaintPending = false;
    refreshFocusPaint();
  });
};
var paintRoots = /* @__PURE__ */ new WeakSet();
function watchFocusPaintIn(root) {
  if (paintRoots.has(root)) return;
  paintRoots.add(root);
  new MutationObserver(queueFocusPaint).observe(root, {
    childList: true,
    subtree: true
  });
  root.addEventListener("slotchange", queueFocusPaint);
}
function publish2(node, cause2) {
  watchStandingAround(node);
  paintDestination = node && new WeakRef(node);
  if (cause2 === "return") queueReturnFocusPaint();
  else {
    returnPaintPending = false;
    queueFocusPaint();
  }
  if (node === (published?.deref() ?? null) && !departed) return;
  departed = false;
  const left = published?.deref() ?? null;
  const reading = ++readings2;
  standing.value = reading;
  if (cause2 === "drop") departed = true;
  else published = node && new WeakRef(node);
  if (node) placeInput = "focus";
  const was = [placing, restoring];
  [placing, restoring] = [null, false];
  try {
    for (const read2 of readers) {
      try {
        read2(node, cause2, left);
      } catch (error) {
        reportError(error);
      }
      if (readings2 !== reading) return;
    }
  } finally {
    [placing, restoring] = was;
  }
}
var pressedPath = null;
var pressedOn = (node) => Boolean(pressedPath) && pressedPath.some((ref) => {
  const at = ref.deref();
  return at === node || at?.localName === "label" && at.control === node;
});
var pressLed = () => pressedPath !== null;
var stepping = null;
var leftClosedLayer = (left) => {
  const layer = left?.closest?.("dialog, [popover]");
  return Boolean(layer) && !(layer.open === true || isNativeLayer(layer));
};
var cause = (node, left = null) => placing ?? (leftClosedLayer(left) ? "return" : pressedOn(node) ? "press" : stepping ? "step" : "move");
var read = /* @__PURE__ */ new WeakSet();
function stand(event) {
  if (read.has(event)) return;
  read.add(event);
  if (closing) return;
  if (heldByLabel()) {
    if (placing === null) return;
    finishLabelPress();
  }
  if (!restoring && !(placing === null && leftClosedLayer(event.relatedTarget)))
    placements += 1;
  const at = deepFocus();
  stood = at && new WeakRef(at);
  publish2(at, cause(at, event.relatedTarget));
}
function watchStandingAround(node) {
  for (let at = node; at; at = renderedParent(at)) watchStandingIn(at.getRootNode());
}
function enter(event) {
  if (read.has(event)) return;
  read.add(event);
  watchStandingAround(deepFocus());
}
function watchStandingIn(root) {
  root.addEventListener("focus", enter, true);
  root.addEventListener("focusin", stand, true);
  watchFocusPaintIn(root);
}
watchStandingIn(document);
watchStandingAround(deepFocus());
document.addEventListener(
  "focusout",
  (event) => {
    if (event.relatedTarget !== null) {
      departed = true;
      return;
    }
    const left = event.composedPath()[0];
    stood = new WeakRef(left);
    if (restoring) return;
    queueMicrotask(() => {
      const at = document.activeElement;
      if (at !== null && at !== document.body) return;
      if (heldByLabel()) return;
      if (!drawn(left)) return publish2(null, "drop");
      if (left !== document.body) placements += 1;
      if (stood?.deref() === left) stood = null;
      publish2(null, cause(null));
    });
  },
  true
);
var sequential = (event) => event.key === "Tab" && !event.altKey && !event.ctrlKey && !event.metaKey;
function reconcile(step, pressed) {
  if (heldByLabel()) return;
  const at = deepFocus();
  if (!at || at === document.body || at === published?.deref()) return;
  placements += 1;
  stood = new WeakRef(at);
  const was = [stepping, pressedPath];
  [stepping, pressedPath] = [step, pressed];
  try {
    publish2(at, cause(at));
  } finally {
    [stepping, pressedPath] = was;
  }
}
addEventListener(
  "click",
  () => {
    const pressed = pressedPath;
    setTimeout(() => reconcile(null, pressed));
  },
  { capture: true, passive: true }
);
var inputs = document.documentElement.lfInputs;
var inputCount = () => inputs.count;
var onUserInput = (read2) => inputs.observe(read2);
var keyCarets = null;
onUserInput((event) => {
  if (event.type !== "keydown") return;
  const carets = /* @__PURE__ */ new Map();
  for (const node of event.composedPath()) {
    const caret = node instanceof Element && readCaret(node);
    if (caret) carets.set(node, caret);
  }
  keyCarets = carets;
  setTimeout(() => {
    if (keyCarets === carets) keyCarets = null;
  });
});
var caretAtKey = (node) => keyCarets?.get(node) ?? null;
onUserInput((event) => {
  if (event.type !== "blur") return;
  landLabelPress();
  endPress(event, false);
});
var placeInput = "focus";
for (const type of ["pointermove", "pointerdown", "wheel"])
  addEventListener(type, () => placeInput = "pointer", {
    capture: true,
    passive: true
  });
addEventListener(
  "click",
  (event) => {
    if (event.isTrusted && event.button === 0)
      placeInput = focused()?.contains(event.composedPath()[0]) ? "focus" : "pointer";
  },
  { capture: true, passive: true }
);
var recentPlaceInput = () => placeInput;
var press = null;
var pressing = () => press;
var pressReaders = /* @__PURE__ */ new Set();
var onPress = (read2) => pressReaders.add(read2);
addEventListener(
  "pointerdown",
  (event) => {
    if (!event.isPrimary) return;
    const path = event.composedPath();
    const ends = [];
    press = { pointerId: event.pointerId, path, ends };
    for (const read2 of pressReaders) {
      const end = read2(event, path);
      if (end) ends.push(end);
    }
    if (event.button !== 0 || labelPress) return;
    const label = (
      /** @type {(EventTarget & Partial<HTMLLabelElement>)[]} */
      path.find((node) => node?.localName === "label" && node.control)
    );
    const held = label && deepFocus();
    if (!held || held === document.body) return;
    labelPress = { held, pointerId: event.pointerId, label };
  },
  { capture: true, passive: true }
);
function endPress(event, completed) {
  if (!press) return;
  const { ends } = press;
  press = null;
  for (const end of ends) end(event, completed);
}
for (
  const type of
  /** @type {const} */
  ["pointerup", "pointercancel"]
)
  addEventListener(
    type,
    (event) => {
      if (event.pointerId === labelPress?.pointerId && (type === "pointercancel" || !event.composedPath().includes(labelPress.label)))
        landLabelPress();
      if (event.pointerId === press?.pointerId) endPress(event, type === "pointerup");
    },
    { capture: true, passive: true }
  );
addEventListener(
  "contextmenu",
  (event) => {
    landLabelPress();
    endPress(event, false);
  },
  { capture: true, passive: true }
);
addEventListener("click", landLabelPress, { capture: true, passive: true });
var recoveredLabelKeys = /* @__PURE__ */ new WeakMap();
var recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);
addEventListener(
  "keydown",
  (event) => {
    placeInput = "focus";
    if (!labelPress || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
    const active = deepFocus();
    const { held } = finishLabelPress();
    if (active === held || !held.isConnected) return;
    focusDestination(held, "return");
    if (deepFocus() === held) recoveredLabelKeys.set(event, held);
  },
  true
);
for (const type of ["keydown", "pointerdown", "wheel", "touchstart"])
  addEventListener(
    type,
    (event) => {
      if (type === "pointerdown")
        pressedPath = event.composedPath().map((node) => new WeakRef(node));
      else if (type === "keydown") pressedPath = null;
      stepping = null;
      if (type === "keydown" || type === "pointerdown") {
        const step = type === "keydown" && sequential(event) ? event : null;
        const pressed = pressedPath;
        stepping = step;
        setTimeout(() => {
          if (step && stepping === step) stepping = null;
          reconcile(step, pressed);
        });
      }
      const at = deepFocus();
      if (at && at !== document.body || heldByLabel()) return;
      stood = null;
      publish2(null, cause(null));
    },
    { capture: true, passive: true }
  );
var drawn = (node) => node?.isConnected && node.checkVisibility({ visibilityProperty: true });
var dropped = () => {
  const at = deepFocus();
  if (at && at !== document.body) return null;
  const node = stood?.deref();
  return node && !drawn(node) ? node : null;
};
function holdFocus(scope, { key = null } = {}) {
  const node = heldIn(scope);
  if (!node) return null;
  const restore = holdOn(node);
  if (!key) return restore;
  let item = node;
  while (item && !item.matches?.(`[${key}]`)) item = renderedParent(item);
  if (!item || item === scope || !renderedUnder(item, scope)) return restore;
  const tree = item.getRootNode() === scope.getRootNode() ? scope : item.getRootNode();
  const items = () => [...tree.querySelectorAll(`[${key}]`)].filter((item2) => renderedUnder(item2, scope));
  const keys = [...new Set(items().map((each) => each.getAttribute(key)))];
  const at = keys.indexOf(item.getAttribute(key));
  const order = [keys[at], ...keys.slice(at + 1), ...keys.slice(0, at).reverse()];
  let control = node;
  while (control.getRootNode() !== item.getRootNode()) {
    const host = shadowHost(control.getRootNode());
    if (!host) break;
    control = host;
  }
  const like = control.localName + [...control.classList].map((name) => `.${CSS.escape(name)}`).join("");
  const [same, ...rest] = order;
  return (...standIns) => {
    let byKey = null;
    const keyed = (value) => {
      if (!byKey) {
        byKey = /* @__PURE__ */ new Map();
        for (const each of items()) {
          const at2 = each.getAttribute(key);
          if (!byKey.has(at2)) byKey.set(at2, []);
          byKey.get(at2).push(each);
        }
      }
      return byKey.get(value) ?? [];
    };
    const matching = (root) => {
      if (root.matches(like) && drawn(root)) return root;
      const assigned = root.localName === "slot" ? root.assignedElements({ flatten: true }) : [];
      for (const child2 of assigned.length ? assigned : root.children) {
        const found = matching(child2);
        if (found) return found;
      }
      return null;
    };
    const find = (value) => {
      const found = keyed(value).filter(drawn);
      return (like && found.find((each) => each.matches(like))) ?? (like && found.map(matching).find(Boolean)) ?? found[0] ?? null;
    };
    const neighbour = (value) => () => {
      const place = find(value);
      if (!place || !drawn(place)) return null;
      focusDestination(place, "return");
      return landedOn(place);
    };
    return restore(() => find(same), ...rest.map(neighbour), ...standIns);
  };
}
var heldIn = (scope) => {
  const held = heldByLabel();
  if (held) return renderedUnder(held, scope) ? held : null;
  const standing2 = deepFocus(
    scope.getRootNode().activeElement ?? scope.ownerDocument.activeElement
  );
  if (standing2 && standing2 !== document.body && renderedUnder(standing2, scope))
    return standing2;
  const node = stood?.deref();
  return node && renderedUnder(node, scope) ? dropped() : null;
};
var standingIn = (scope) => {
  const at = focused();
  return Boolean(at) && at !== document.body && renderedUnder(at, scope);
};
function rove(items, stop) {
  for (const item of items) keeps(item, "tabindex", item === stop ? 0 : -1);
}
var openers = /* @__PURE__ */ new WeakMap();
function openLayer(layer, opener = focused()) {
  openers.set(layer, opener && opener !== document.body ? opener : null);
}
var openerOf = (layer) => openers.get(layer) ?? null;
var closing = 0;
var deferredLanding = null;
var landingLayer = false;
function layerLanding(land2) {
  return (...args) => {
    if (!landingLayer)
      throw new Error("A layer's landing runs only as the layer closes");
    return land2(...args);
  };
}
function closeLayer(close, land2 = null) {
  closing += 1;
  let deferred = null;
  const landingAround = landingLayer;
  landingLayer = false;
  try {
    close();
  } finally {
    landingLayer = landingAround;
    closing -= 1;
    if (!closing) [deferred, deferredLanding] = [deferredLanding, null];
  }
  if (closing) {
    if (land2) deferredLanding ??= land2;
    return;
  }
  const landing = land2 || deferred;
  if (landing) {
    const outer = landingLayer;
    landingLayer = true;
    try {
      landing();
    } finally {
      landingLayer = outer;
    }
  }
  const at = deepFocus();
  if (!at || at === document.body || at === published?.deref()) return;
  stood = new WeakRef(at);
  publish2(at, "return");
}
function holdStanding() {
  const at = focused();
  const node = at && at !== document.body ? at : dropped();
  return node ? { node, restore: holdOn(node) } : null;
}
var carried = /* @__PURE__ */ new WeakMap();
var carriedFrom = (node) => carried.get(node) ?? null;
function holdOn(held) {
  const caret = readCaret(held);
  const began = placements;
  return (...standIns) => {
    if (placements !== began) return false;
    for (const standIn of [held, ...standIns]) {
      if (placements !== began) return false;
      const place = typeof standIn === "function" ? standIn() : standIn;
      if (place?.then)
        return place.then((destination) => {
          if (!(destination instanceof Element) || !drawn(destination) || deepFocus() !== destination)
            return false;
          return land(() => {
            focusDestination(destination, "return", { caret });
            return landedOn(destination);
          });
        });
      if (place === true) return true;
      if (!(place instanceof Element) || !drawn(place)) continue;
      if (place === held && deepFocus() === held) return true;
      const landed = land(() => {
        focusDestination(place, "return", { caret });
        return landedOn(place);
      });
      if (landed) {
        const before = carriedFrom(held);
        if (place !== held)
          carried.set(
            place,
            before?.inputs === inputCount() ? before : { from: held, inputs: inputCount() }
          );
        return true;
      }
    }
    return false;
  };
}
var land = (landing) => {
  const was = restoring;
  restoring = true;
  try {
    return landing();
  } finally {
    restoring = was;
  }
};
var TYPED_TYPES = /* @__PURE__ */ new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week"
]);
function typesText(node) {
  return Boolean(node) && (node.matches(TEXT_BOX) || node.isContentEditable || node.tagName === "INPUT" && TYPED_TYPES.has(node.type));
}
function takesLetters(node) {
  return typesText(node) || Boolean(node) && (node.tagName === "SELECT" || node.getAttribute("role") === "option");
}
function controlNavigationKeys(node) {
  if (node?.matches('input[type="radio"], [role="radio"]'))
    return ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (node?.matches('input[type="range"], [role="slider"]'))
    return [
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "Home",
      "End",
      "PageUp",
      "PageDown"
    ];
  return [];
}
var readingBlock = () => null;
function declareReading(read2) {
  readingBlock = read2;
}
var coveringSurface = () => null;
var coveringLanding = () => null;
function declareCovering({ surface, landing }) {
  coveringSurface = surface;
  coveringLanding = landing;
}
var coveringFocus = () => coveringLanding();
function releaseFocus() {
  focusDestination(document.body, "move");
  document.body.blur();
}
var released = () => {
};
function declareRelease(release2) {
  released = release2;
}
var letGoes = 0;
function release() {
  const before = letGoes;
  released();
  if (letGoes === before) letGo();
}
function letGo() {
  letGoes++;
  const covering = coveringSurface();
  if (covering) {
    if (!covering.contains(document.activeElement))
      focusDestination(coveringFocus(), "move");
    return;
  }
  const block = readingBlock();
  if (!block?.isConnected) {
    releaseFocus();
    return;
  }
  focusDestination(block, "move");
  block.blur();
}
function handBack(...destinations) {
  const places = destinations.filter((node) => node && node !== document.body);
  const landed = () => {
    const at = placements;
    return places.some((node) => {
      if (placements !== at) return true;
      if (!drawn(node)) return false;
      focusDestination(node, "return");
      return landedOn(node);
    });
  };
  if (landed()) return;
  if (!places.some((node) => node.isConnected)) {
    letGo();
    return;
  }
  const yielded = !drawn(deepFocus());
  if (yielded) releaseFocus();
  const began = placements;
  const pendingInput = inputCount();
  nextRender(() => {
    if (inputCount() !== pendingInput || placements !== began || yielded && deepFocus() !== document.body || landed())
      return;
    letGo();
  });
}

export {
  sampleVisibility,
  onSampleVisibility,
  readSampleVisibility,
  observePreparations,
  holdRendering,
  nextRender,
  nextFrame,
  nextAnimation,
  cancelAnimation,
  cancelRender,
  afterScript,
  sizeObserver,
  renderingState,
  afterSettling,
  keeps,
  keepsHidden,
  keepsText,
  atLayoutPrecision,
  layoutPx,
  TEXT_FIELD,
  MODIFIER_KEYS,
  CARET_KEYS,
  selectsAll,
  TEXT_BOX,
  TAB_STOP,
  LENT_REACH_STOP,
  PRESSES,
  WORKS,
  shadowHost,
  upFrom,
  renderedParent,
  composedParentNode,
  under,
  renderedUnder,
  renderedOrder,
  byRenderedOrder,
  nativeLayerKind,
  isNativeLayer,
  nativeLayerHolding,
  tabStops,
  canPlaceFocus,
  focusDestination,
  forwardFocus,
  wearsLentStop,
  whenLeft,
  readCaret,
  deepFocus,
  focused,
  standingNodes,
  standsOn,
  onStanding,
  pressLed,
  watchStandingIn,
  inputCount,
  onUserInput,
  caretAtKey,
  recentPlaceInput,
  pressing,
  onPress,
  recoveredLabelFocus,
  drawn,
  holdFocus,
  standingIn,
  rove,
  openLayer,
  openerOf,
  layerLanding,
  closeLayer,
  holdStanding,
  carriedFrom,
  typesText,
  takesLetters,
  controlNavigationKeys,
  declareReading,
  declareCovering,
  coveringFocus,
  releaseFocus,
  declareRelease,
  release,
  letGo,
  handBack
};
