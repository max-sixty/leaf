/* Package-owned mirrors of complete Thread conversations.

   A mirror is an optional view of the shared Thread reading, never a placement of
   the original Thread. Each owner reconciles its own outlets and async preparation;
   neither can hold the core panel, margin, or read presentation. A later reading or
   unregister aborts its predecessor before any DOM from that predecessor commits. */
import { reportPageError } from "../layer-client.js";
import { under } from "../shadow.js";
import { clearThreadMirrors, renderThreadMirrors } from "./inline.js";
import { readThreads } from "./state.js";
import { watchThreads } from "./watch.js";

const registrations = new WeakMap();

export function registerMirrorConsumer(owner, render, { commands }) {
  if (!(owner instanceof Element))
    throw new TypeError("mountThreadViews needs an Element owner");
  if (typeof render !== "function")
    throw new TypeError("mountThreadViews needs a render callback");
  if (registrations.has(owner))
    throw new Error(`mountThreadViews(${owner.localName}) registered twice`);

  let active = true;
  let generation = 0;
  let pending = null;
  let queued = false;
  let outlets = new Set();

  const clear = () => {
    for (const outlet of outlets) {
      clearThreadMirrors(outlet);
      delete outlet.dataset.lfThreadSurface;
    }
    outlets = new Set();
  };
  const report = (error) =>
    reportPageError(
      `Thread mirrors in ${owner.localName}#${owner.id} failed: ${error?.message ?? error}`,
    );

  async function reconcile() {
    const current = ++generation;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    const cancelled = new Promise((resolve) =>
      abort.signal.addEventListener("abort", resolve, { once: true }),
    );
    const collection = readThreads();
    const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
    const selected = new Map();
    let accepting = true;
    const mirrors = {
      signal: abort.signal,
      render(key, outlet) {
        if (!accepting || abort.signal.aborted)
          throw new Error("Thread mirrors belong to their current render callback");
        if (!(outlet instanceof Element))
          throw new TypeError("A Thread mirror outlet must be an Element");
        const thread = byKey.get(key);
        if (!thread) throw new Error(`No Thread has key ${key}`);
        if ([...selected.values()].some((threads) => threads.includes(thread)))
          throw new Error("A consumer may render a Thread only once");
        const threads = selected.get(outlet) ?? [];
        threads.push(thread);
        selected.set(outlet, threads);
      },
    };
    try {
      const rendering = render(collection, mirrors);
      if (rendering?.then) await Promise.race([rendering, cancelled]);
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return;
      if (!owner.isConnected) return;
      for (const outlet of selected.keys()) {
        if (!outlet.isConnected) selected.delete(outlet);
        else if (!under(outlet, owner))
          throw new Error(
            `mountThreadViews(${owner.localName}) returned an outlet outside its widget`,
          );
      }
      for (const outlet of outlets)
        if (!selected.has(outlet)) {
          clearThreadMirrors(outlet);
          delete outlet.dataset.lfThreadSurface;
        }
      outlets = new Set(selected.keys());
      for (const [outlet, threads] of selected) {
        outlet.toggleAttribute("data-lf-thread-surface", true);
        renderThreadMirrors(outlet, threads, commands);
      }
    } catch (error) {
      if (!active || current !== generation || abort.signal.aborted) return;
      clear();
      report(error);
    } finally {
      accepting = false;
    }
  }

  const update = () => {
    if (!active || queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (active && owner.isConnected) void reconcile();
    });
  };
  const stop = watchThreads(owner, update);
  const handle = Object.freeze({
    read: readThreads,
    update,
    unregister() {
      if (!active) return;
      active = false;
      ++generation;
      pending?.abort();
      stop();
      registrations.delete(owner);
      clear();
    },
  });
  registrations.set(owner, handle);
  return handle;
}
