// Carries a trusted input through the asynchronous callbacks it schedules. The health
// watches read a callback's source when its work finishes, rather than guessing how
// recently the user pressed. A timer created before that input stays passive even if
// it runs while an input's other work is waiting. Native await continuations do not
// call Promise.prototype.then. Their owner captures the callback that commits an
// effect before awaiting, and invokes it afterwards. Leaf draft sends put words away
// synchronously before awaiting delivery (drafts.js). A reactive element's update is
// the exception the watch follows itself: Lit defers it behind a native await, and the
// request that starts it names its cause (`adoptReactive`).
// Native edit starts identify their field through DOM capture or EditContext's
// attachment; a watch confirms the value that field's input commits.
// Parent input bridges belong to the child document. Pagehide releases them before
// its realm goes away; a back-forward cache return reconnects the same bridges.
// The watch's own scheduling uses the saved platform methods and is never counted.
(() => {
  "use strict";
  const { later: task, microtask, listen } = window.lfWatchPlatform;
  const finishing = new Set();
  const nativeDefaults = new Map();
  const finished = new Set();
  const subscribers = new Set();
  const editSubscribers = new Set();
  const sources = new WeakMap();
  let order = 0;
  const then = Promise.prototype.then;
  const parents = [];
  const parentConnections = [];
  const stopParents = [];
  const connectParent = (connect) => {
    parentConnections.push(connect);
    stopParents.push(connect());
  };
  addEventListener("pagehide", () => {
    for (const stop of stopParents) stop();
    stopParents.length = 0;
  });
  addEventListener("pageshow", (event) => {
    if (event.persisted)
      for (const connect of parentConnections) stopParents.push(connect());
  });
  let callbackSource = null;
  let callbackDepth = 0;
  const localSource = (source) => {
    let local = sources.get(source.event);
    if (!local) {
      local = { event: source.event, node: source.node, order: ++order };
      sources.set(source.event, local);
    }
    return source.nativeDefault
      ? { ...local, nativeDefault: source.nativeDefault }
      : local;
  };
  const current = () => {
    if (callbackDepth) return callbackSource;
    // A parent's captured callback can synchronously call into its child. Work
    // that child schedules belongs to that same executing callback, not the last
    // input either document happened to receive.
    const source = parents[0]?.current();
    return source ? localSource(source) : null;
  };
  const closed = (owner) =>
    owner.localName === "details" ? !owner.open : !owner.matches(":popover-open");
  const checkpoint = (source, completedEdit = false) => {
    // The first reader after activation owns the native default, even when a
    // toggle listener runs before the dispatch-completion task.
    for (const [activation, owners] of nativeDefaults) {
      if (activation.event.defaultPrevented) continue;
      for (const owner of owners) {
        if (!closed(owner)) continue;
        owners.delete(owner);
        for (const subscriber of subscribers)
          subscriber({ ...activation, nativeDefault: owner }, true);
      }
      if (!owners.size) nativeDefaults.delete(activation);
    }
    for (const subscriber of subscribers) subscriber(source, completedEdit);
  };
  const enter = (source) => {
    // A nested focus or synthetic event can run after its caller changed the DOM.
    // Read those writes under that caller before the nested callback starts.
    checkpoint(current());
    const previous = callbackSource;
    callbackSource = source;
    callbackDepth++;
    return () => {
      try {
        checkpoint(source);
      } finally {
        callbackDepth--;
        callbackSource = previous;
      }
    };
  };
  const wrap = (callback, source) =>
    function (...args) {
      const leave = enter(source);
      try {
        return callback.apply(this, args);
      } finally {
        leave();
      }
    };

  // Browser edit commands can be handled by a closed editor without native
  // beforeinput or input. Their trusted dispatch remains the edit's source.
  const editorCommands = Object.freeze(["cut", "paste", "drop"]);
  const inputTypes = [
    "pointerdown",
    "mousedown",
    "touchstart",
    "pointerup",
    "mouseup",
    "touchend",
    "click",
    "contextmenu",
    "keydown",
    "beforeinput",
    "input",
    ...editorCommands,
  ];
  // Native summary activation belongs to the nearest interactive content, not an
  // enclosing summary around a button or link (HTML's interactive-content category).
  const nativeActivation =
    "summary,a[href],audio[controls],button,details,embed,iframe," +
    'img[usemap],img[controls],input:not([type="hidden" i]),label,select,textarea,video[controls]';

  const handlerOriginals = new WeakMap();
  const handlerWrappers = new WeakMap();
  const handler = (callback) => {
    if (handlerOriginals.has(callback)) return callback;
    let wrapped = handlerWrappers.get(callback);
    if (!wrapped) {
      wrapped = function (event) {
        return wrap(callback, eventSource(event)).call(this, event);
      };
      handlerWrappers.set(callback, wrapped);
      handlerOriginals.set(wrapped, callback);
    }
    return wrapped;
  };
  for (const prototype of [
    HTMLElement.prototype,
    SVGElement.prototype,
    Document.prototype,
    Window.prototype,
  ]) {
    for (const type of inputTypes) {
      const name = `on${type}`;
      const property = Object.getOwnPropertyDescriptor(prototype, name);
      if (!property?.set) continue;
      Object.defineProperty(prototype, name, {
        ...property,
        get() {
          const callback = property.get.call(this);
          return handlerOriginals.get(callback) ?? callback;
        },
        set(callback) {
          property.set.call(
            this,
            typeof callback === "function" ? handler(callback) : callback,
          );
        },
      });
    }
  }

  // A press is one gesture from pointerdown through its click; a key is its keydown.
  const PRESS = new Set(["pointerdown", "mousedown", "pointerup", "mouseup"]);
  const GESTURES = new Set(["pointerdown", "keydown"]);
  const endDispatch = (source) => {
    finishing.add(source);
    // A summary's native activation runs after the click listeners and their
    // microtasks, and so do the closes the browser makes of the popovers open when a
    // gesture starts: a press's light dismissal, a popovertarget invoker's toggle, and
    // Escape. Retain those browser-owned closes until the gesture's dispatch completes,
    // without assigning unrelated native-await work to the input. A press's light
    // dismissal falls between its own events, outside every dispatch, so the closes a
    // pointerdown retains stand until its click has dispatched.
    // A press inside a popover never light-dismisses it, so only those it lands outside
    // are retained for a press.
    const path = source.event.composedPath();
    const closes = new Set(
      GESTURES.has(source.event.type)
        ? [...document.querySelectorAll(":popover-open")].filter(
            (popover) => source.event.type === "keydown" || !path.includes(popover),
          )
        : [],
    );
    const summary =
      source.event.type === "click" ? source.node?.closest?.(nativeActivation) : null;
    const details = summary?.parentElement;
    const closesDetails =
      details?.localName === "details" &&
      summary.localName === "summary" &&
      details.querySelector(":scope > summary") === summary &&
      details.open;
    if (closesDetails) closes.add(details);
    if (closes.size) nativeDefaults.set(source, closes);
    task(() => {
      // The dispatch is over. A native await continuation since dispatch is not owned by
      // this event unless its committing callback was explicitly captured.
      checkpoint(null, true);
      for (const activation of nativeDefaults.keys())
        if (
          activation === source
            ? !PRESS.has(source.event.type)
            : source.event.type === "click" && PRESS.has(activation.event.type)
        )
          nativeDefaults.delete(activation);
      finishing.delete(source);
      if (!finishing.size) {
        for (const resolve of finished) resolve();
        finished.clear();
      }
    });
  };
  const beginSource = (event, node, edit = false) => {
    // An earlier passive loss cannot be answered by the input that follows it.
    checkpoint(null, event.type !== "input");
    // A new gesture ends what an earlier one retained.
    if (GESTURES.has(event.type)) nativeDefaults.clear();
    const source = { event, node, order: ++order };
    sources.set(event, source);
    if (edit) for (const subscriber of editSubscribers) subscriber(source);
    microtask(() => checkpoint(source));
    endDispatch(source);
    return source;
  };
  const eventSource = (event) => {
    if (sources.has(event)) return sources.get(event);
    // EditContext's trusted textupdate does not travel through a DOM capture path.
    // Its attached element owns rendering. Expose the field a composed DOM event
    // would expose outside its closed shadow roots, without consulting the runtime.
    if (
      event.isTrusted &&
      event.type === "textupdate" &&
      window.EditContext &&
      event.target instanceof window.EditContext
    ) {
      let node = event.target.attachedElements()[0];
      if (node?.editContext === event.target) {
        for (let inner = node; inner.getRootNode().host;) {
          const root = inner.getRootNode();
          inner = root.host;
          if (root.mode === "closed") node = inner;
        }
        return beginSource(event, node, true);
      }
    }
    return current();
  };
  for (let view = window; ; view = view.parent) {
    try {
      void view.document;
    } catch {
      break;
    }
    if (view !== window && view.lfInputWork) {
      const parent = view.lfInputWork;
      parents.push(parent);
      connectParent(() => {
        const stopEdits = parent.subscribeEdits((source) => {
          for (const subscriber of editSubscribers) subscriber(localSource(source));
        });
        const stop = parent.subscribe((source, completedEdit) => {
          if (!source) return checkpoint(source, completedEdit);
          checkpoint(localSource(source), completedEdit);
        });
        return () => {
          stopEdits();
          stop();
        };
      });
      if (view === view.parent) break;
      continue;
    }
    const callbacks = [];
    for (const type of inputTypes) {
      const callback = (event) => {
        if (!event.isTrusted) return;
        beginSource(
          event,
          event.composedPath()[0],
          event.type === "beforeinput" || editorCommands.includes(event.type),
        );
        // The browser compiles handler attributes without invoking our setter.
        // Adopt those callbacks before target dispatch, preserving getter identity.
        for (const node of event.composedPath()) {
          const name = `on${type}`;
          if (typeof node?.[name] === "function") node[name] = node[name];
        }
      };
      callbacks.push([type, callback]);
    }
    const listen = () => {
      for (const [type, callback] of callbacks)
        view.addEventListener(type, callback, true);
      return () => {
        for (const [type, callback] of callbacks)
          view.removeEventListener(type, callback, true);
      };
    };
    if (view === window) listen();
    else connectParent(listen);
    if (view === view.parent) break;
  }
  listen(window, "storage", (event) => {
    if (!event.isTrusted) return;
    checkpoint(null);
    const source = { event, node: null, order: ++order };
    sources.set(event, source);
    microtask(() => checkpoint(source));
    endDispatch(source);
  });

  // Event dispatch runs a microtask checkpoint between listeners. Capture alone
  // cannot read what a later listener writes, so page listeners checkpoint their own
  // work. Keep one wrapper per callback, preserving native duplicate/remove identity.
  const listeners = new WeakMap();
  const add = EventTarget.prototype.addEventListener;
  const remove = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, callback, options) {
    if (!callback) return add.call(this, type, callback, options);
    let listener = listeners.get(callback);
    if (!listener) {
      listener = function (event) {
        const source = eventSource(event);
        const call = typeof callback === "function" ? callback : callback.handleEvent;
        return wrap(call, source).call(
          typeof callback === "function" ? this : callback,
          event,
        );
      };
      listeners.set(callback, listener);
    }
    return add.call(this, type, listener, options);
  };
  EventTarget.prototype.removeEventListener = function (type, callback, options) {
    return remove.call(this, type, listeners.get(callback) ?? callback, options);
  };

  for (const name of [
    "setTimeout",
    "setInterval",
    "requestAnimationFrame",
    "queueMicrotask",
  ]) {
    const schedule = window[name];
    window[name] = function (callback, ...args) {
      return schedule.call(
        this,
        typeof callback === "function" ? wrap(callback, current()) : callback,
        ...args,
      );
    };
  }
  // A reactive element (Lit's lifecycle: `requestUpdate` starts an update, which a native
  // `await` defers to `scheduleUpdate`) commits its update for whatever requested it.
  // The request that starts the update names its source, as scheduling a timer does,
  // and connecting the element names the source of its first; the update runs under
  // that source, so a field it rewrites keeps its cause.
  const updateSources = new WeakMap();
  const reactive = new WeakSet();
  const adoptReactive = (constructor) => {
    for (
      let prototype = constructor?.prototype;
      prototype && prototype !== HTMLElement.prototype;
      prototype = Object.getPrototypeOf(prototype)
    ) {
      if (
        reactive.has(prototype) ||
        !Object.hasOwn(prototype, "requestUpdate") ||
        !Object.hasOwn(prototype, "scheduleUpdate")
      )
        continue;
      reactive.add(prototype);
      const request = prototype.requestUpdate;
      const schedule = prototype.scheduleUpdate;
      prototype.requestUpdate = function (...args) {
        const starts = !this.isUpdatePending;
        const result = request.apply(this, args);
        if (starts && this.isUpdatePending) updateSources.set(this, current());
        return result;
      };
      prototype.scheduleUpdate = function (...args) {
        const source = updateSources.get(this) ?? null;
        updateSources.delete(this);
        return wrap(schedule, source).apply(this, args);
      };
      // The first update, requested as the element is made, waits for it to be
      // connected, so connecting it is what that update answers to.
      if (Object.hasOwn(prototype, "connectedCallback")) {
        const connect = prototype.connectedCallback;
        prototype.connectedCallback = function (...args) {
          if (!this.hasUpdated && this.isUpdatePending)
            updateSources.set(this, current());
          return connect.apply(this, args);
        };
      }
    }
  };
  const define = CustomElementRegistry.prototype.define;
  CustomElementRegistry.prototype.define = function (name, constructor, options) {
    adoptReactive(constructor);
    return define.call(this, name, constructor, options);
  };

  Promise.prototype.then = function (fulfilled, rejected) {
    const source = current();
    return then.call(
      this,
      typeof fulfilled === "function" ? wrap(fulfilled, source) : fulfilled,
      typeof rejected === "function" ? wrap(rejected, source) : rejected,
    );
  };
  window.lfInputWork = {
    current,
    capture: (callback) => wrap(callback, current()),
    // A generic scheduler can observe enqueue/run/finish without replacing its
    // callbacks. Capture at enqueue, enter at run, and checkpoint before release.
    captureScope() {
      const source = current();
      return () => enter(source);
    },
    dispatching: () =>
      finishing.size > 0 || parents.some((parent) => parent.dispatching()),
    dispatched: () =>
      Promise.all([
        finishing.size
          ? new Promise((resolve) => finished.add(resolve))
          : Promise.resolve(),
        ...parents.map((parent) => parent.dispatched()),
      ]),
    subscribe(callback) {
      subscribers.add(callback);
      return () => subscribers.delete(callback);
    },
    subscribeEdits(callback) {
      editSubscribers.add(callback);
      return () => editSubscribers.delete(callback);
    },
  };
})();
