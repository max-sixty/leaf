/* @noformat Generated TypeScript; edit the .ts owner. */
import { signal } from "/vendor/signals-core.js";
import { untracked } from "./snapshot.js";
function createPresentationCoordinator({
  reportFailure
}) {
  const changes = signal(0);
  let wake = Promise.withResolvers();
  let publication = null;
  let sealed = false;
  const regions = /* @__PURE__ */ new Map();
  const pending = (wanted = regions.keys()) => [...wanted].filter((key) => {
    const record = regions.get(key);
    return record && !record.complete;
  });
  function changed() {
    const previous = wake;
    wake = Promise.withResolvers();
    previous.resolve();
    changes.value = changes.peek() + 1;
  }
  function begin() {
    for (const [region, record] of regions) if (!record.active) regions.delete(region);
    publication = Object.freeze({});
    sealed = false;
    changed();
    return publication;
  }
  function seal(value) {
    if (value !== publication) return false;
    sealed = true;
    changed();
    return true;
  }
  function attach(region) {
    if (!publication)
      throw new Error("begin a presentation publication before attaching a renderer");
    const record = {
      complete: false,
      active: true,
      latest: null,
      release: null
    };
    regions.set(region, record);
    const active = () => record.active && regions.get(region) === record;
    changed();
    function present(failSoft) {
      const completion = Promise.withResolvers();
      const previous = record.release;
      record.release = () => queueMicrotask(() => completion.resolve(void 0));
      const ticket = {};
      if (active()) {
        record.latest = ticket;
        record.complete = false;
        changed();
      }
      const current = () => active() && record.latest === ticket;
      const ready = (async () => {
        try {
          await completion.promise;
        } catch (reason) {
          if (!active()) return;
          let recovered = false;
          let failure = reason;
          if (failSoft) {
            try {
              failSoft(reason);
              recovered = true;
            } catch (fallbackError) {
              if (fallbackError !== reason)
                failure = new AggregateError(
                  [reason, fallbackError],
                  "presentation and fail-soft failed"
                );
            }
          }
          reportFailure(failure);
          if (!current()) return;
          if (!recovered) throw failure;
        }
        if (current()) {
          record.complete = true;
          changed();
        }
      })();
      void ready.catch(() => {
      });
      previous?.();
      return Object.freeze({
        resolve: completion.resolve,
        reject: completion.reject,
        ready
      });
    }
    function disconnect() {
      record.release?.();
      record.release = null;
      if (!active()) return;
      if (!sealed || pending().length) record.complete = false;
      record.active = false;
      queueMicrotask(() => {
        if (regions.get(region) !== record) return;
        regions.delete(region);
        changed();
      });
    }
    return Object.freeze({ present, disconnect });
  }
  const currentRegionsPresented = (wanted) => sealed && !pending(wanted).length;
  const currentPresented = () => currentRegionsPresented();
  const whenCurrentPresented = () => whenCurrentRegionsPresented();
  async function whenCurrentRegionsPresented(wanted, current = () => true) {
    await Promise.resolve();
    for (; ; ) {
      const next = wake.promise;
      if (!current()) return "superseded";
      if (currentRegionsPresented(wanted)) return "presented";
      await next;
    }
  }
  function read() {
    return Object.freeze({
      sealed,
      pending: Object.freeze(pending())
    });
  }
  return Object.freeze({
    begin,
    seal,
    attach,
    whenCurrentPresented,
    currentPresented,
    whenCurrentRegionsPresented,
    currentRegionsPresented,
    read,
    subscribe: (callback) => changes.subscribe(
      () => untracked(() => {
        try {
          callback();
        } catch (reason) {
          reportFailure(reason);
        }
      })
    )
  });
}
function createPresentationSchedule(bindJob) {
  let queued = [];
  let running = [];
  let scheduled = false;
  let settling = false;
  let pass = null;
  function open() {
    if (pass) return;
    pass = Promise.withResolvers();
    void pass.promise.catch(() => void 0);
  }
  function collect(after, run, retired) {
    open();
    const paint = bindJob(run);
    queued.push(async () => {
      let dependencies = after?.() ?? [];
      while (dependencies.length && (!retired || retired.current())) {
        const settled = Promise.allSettled(dependencies);
        await (retired ? Promise.race([settled, retired.ready]) : settled);
        const latest = after?.() ?? [];
        if (latest.every((dependency) => dependencies.includes(dependency))) break;
        dependencies = latest;
      }
      return paint();
    });
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      const round = queued;
      queued = [];
      for (const run2 of round) {
        const started = run2();
        void started.catch(() => void 0);
        running.push(started);
      }
      void drain();
    });
  }
  async function drain() {
    if (settling) return;
    settling = true;
    let failure = null;
    let failed = false;
    while (running.length || queued.length || scheduled) {
      const started = running;
      running = [];
      for (const outcome of await Promise.allSettled(started))
        if (outcome.status === "rejected" && !failed) {
          failed = true;
          failure = outcome.reason;
        }
    }
    settling = false;
    const finished = pass;
    pass = null;
    if (failed) finished.reject(failure);
    else finished.resolve();
  }
  const passed = () => pass?.promise ?? Promise.resolve();
  function enqueue(after, run, committed) {
    const completion = Promise.withResolvers();
    const dom = Promise.withResolvers();
    collect(after, async () => {
      try {
        await run();
        completion.resolve();
        await committed();
        dom.resolve();
      } catch (error) {
        completion.reject(error);
        dom.reject(error);
        throw error;
      }
    });
    return Object.freeze({ ready: completion.promise, committed: dom.promise });
  }
  function presenter({
    attach,
    paint,
    failSoft,
    after
  }) {
    let handle = null;
    let generation = 0;
    let dom = Promise.withResolvers();
    dom.resolve();
    function claim(value) {
      const claimed = ++generation;
      handle ??= attach();
      const previous = dom;
      dom = Promise.withResolvers();
      previous.resolve();
      return { claimed, value, dom, presentation: handle.present(failSoft) };
    }
    async function run({ claimed, value, presentation, dom: dom2 }) {
      if (claimed !== generation) return;
      let painted;
      try {
        painted = paint(value, () => claimed === generation);
      } catch (error) {
        painted = Promise.reject(error);
      }
      dom2.resolve();
      presentation.resolve(painted);
      await presentation.ready;
    }
    function sync(value) {
      const ticket = claim(value);
      collect(after, () => run(ticket), {
        ready: ticket.dom.promise,
        current: () => ticket.claimed === generation
      });
      return passed();
    }
    function disconnect() {
      generation += 1;
      dom.resolve();
      handle?.disconnect();
      handle = null;
    }
    return Object.freeze({ sync, committed: () => dom.promise, disconnect });
  }
  return Object.freeze({ presenter, enqueue, passed });
}
export {
  createPresentationCoordinator,
  createPresentationSchedule
};
