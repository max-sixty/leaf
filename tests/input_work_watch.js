// Carries a trusted input through the asynchronous callbacks it schedules. The health
// watches read a callback's source when its work finishes, rather than guessing how
// recently the user pressed. A timer created before that input stays passive even if
// it runs while an input's other work is waiting. Native await continuations do not
// call Promise.prototype.then. Their owner captures the callback that commits an
// effect before awaiting, and invokes it afterwards. Leaf draft sends put words away
// synchronously before awaiting delivery (drafts.js).
// The watch's own scheduling uses the saved platform methods and is never counted.
(() => {
  "use strict";
  const { later: task, microtask } = window.lfWatchPlatform;
  const finishing = new Set();
  const finished = new Set();
  const subscribers = new Set();
  const sources = new WeakMap();
  let order = 0;
  const then = Promise.prototype.then;
  const parents = [];
  let callbackSource = null;
  let callbackDepth = 0;
  const current = () => (callbackDepth ? callbackSource : null);
  const checkpoint = (source, completedEdit = false) => {
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
  ];

  const handlerOriginals = new WeakMap();
  const handlerWrappers = new WeakMap();
  const handler = (callback) => {
    if (handlerOriginals.has(callback)) return callback;
    let wrapped = handlerWrappers.get(callback);
    if (!wrapped) {
      wrapped = function (event) {
        return wrap(callback, sources.get(event) ?? current()).call(this, event);
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

  const endDispatch = (source) => {
    finishing.add(source);
    task(() => {
      // The dispatch is over. A native await continuation since dispatch is not owned by
      // this event unless its committing callback was explicitly captured.
      checkpoint(null, true);
      finishing.delete(source);
      if (!finishing.size) {
        for (const resolve of finished) resolve();
        finished.clear();
      }
    });
  };
  for (let view = window; ; view = view.parent) {
    try {
      void view.document;
    } catch {
      break;
    }
    if (view !== window && view.lfInputWork) {
      parents.push(view.lfInputWork);
      view.lfInputWork.subscribe((source, completedEdit) => {
        if (!source) return checkpoint(source, completedEdit);
        let local = sources.get(source.event);
        if (!local) {
          local = { ...source, order: ++order };
          sources.set(source.event, local);
        }
        checkpoint(local, completedEdit);
      });
      if (view === view.parent) break;
      continue;
    }
    for (const type of inputTypes) {
      view.addEventListener(
        type,
        (event) => {
          if (!event.isTrusted) return;
          // An earlier passive loss cannot be answered by the input that follows it.
          checkpoint(null, event.type !== "input");
          const source = {
            event,
            node: event.composedPath()[0],
            order: ++order,
          };
          sources.set(event, source);
          // The browser compiles handler attributes without invoking our setter.
          // Adopt those callbacks before target dispatch, preserving getter identity.
          for (const node of event.composedPath()) {
            const name = `on${type}`;
            if (typeof node?.[name] === "function") node[name] = node[name];
          }
          microtask(() => checkpoint(source));
          endDispatch(source);
        },
        true,
      );
    }
    if (view === view.parent) break;
  }
  addEventListener("storage", (event) => {
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
        const source = sources.get(event) ?? current();
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
  };
})();
