/* Package-owned mirrors of complete Thread conversations.

   A mirror is an optional view of the shared Thread reading, never a placement of
   the original Thread. Each owner reconciles its own outlets and async preparation;
   neither can hold the core panel, margin, or read presentation. A later reading or
   unregister aborts its predecessor before any DOM from that predecessor commits. */
import { reportPageError } from "../layer-client.js";
import { under, renderedUnder, shadowHost } from "../shadow.js";
import { clearThreadMirrors, renderThreadMirrors } from "./inline.js";
import { readThreads } from "./state.js";
import { watchThreads } from "./watch.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { MessageView, messageReading } from "./messages.js";
import { createReplyView, replyAvailable } from "./replies.js";
import { reactionReading } from "./reaction-model.js";
import { keeps, keepsHidden } from "../keeps.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { elementById } from "../passages.js";
import { SAY_BOX } from "./selectors.js";

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

/* A selected primary reader joins the required thread presentation. Packages nominate
   complete conversations or retained fragments; core owns their generated roots,
   editors, exact-version read observation and the single authored widget instances.
   Nominations settle before the fallback panel paints, so native authored nodes have
   one physical destination on every pass. Layout and disclosure belong to the caller. */
export function createPrimaryReader(owner, render, commands, update) {
  if (!(owner instanceof Element) || typeof render !== "function")
    throw new TypeError(
      "A Thread presentation needs an Element owner and render callback",
    );
  let active = true;
  let generation = 0;
  let pending = null;
  let selected = [];
  const views = new Map();
  const destinations = new Map();
  const nativeMessages = new Set();
  const clear = () => {
    for (const view of views.values()) {
      view.dispose();
      view.node.remove();
      for (const slot of view.slots ?? []) slot.remove();
    }
    views.clear();
    destinations.clear();
    nativeMessages.clear();
  };
  function prepare(collection, cancelled) {
    const current = ++generation;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
    const nominations = [];
    let accepting = true;
    const nominate = (kind, key, message, outlet) => {
      if (!accepting || abort.signal.aborted)
        throw new Error("Thread nominations belong to their current render callback");
      if (!(outlet instanceof Element))
        throw new TypeError("A Thread outlet must be an Element");
      const thread = byKey.get(key);
      if (!thread) throw new Error(`No Thread has key ${key}`);
      if (message !== null && !thread.msgs.some((item) => item.id === message))
        throw new Error(`Thread ${key} has no message ${message}`);
      const identity = JSON.stringify([kind, key, message]);
      if (
        nominations.some(
          (item) =>
            item.identity === identity ||
            (item.key === key && (item.kind === "thread" || kind === "thread")),
        )
      )
        throw new Error("A primary reader may nominate each Thread part only once");
      nominations.push({ identity, kind, key, message, outlet, thread });
    };
    const finish = () => {
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return null;
      for (const item of nominations)
        if (!item.outlet.isConnected || !under(item.outlet, owner))
          throw new Error(
            "A primary Thread outlet must remain inside its connected owner",
          );
      selected = nominations;
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (item.kind === "thread" || item.message === message.id)
            nativeMessages.add(message.id);
      return {
        paint: () => paint(current),
        current: () => active && current === generation && !abort.signal.aborted,
      };
    };
    try {
      const rendering = render(
        collection,
        Object.freeze({
          signal: abort.signal,
          render: (key, outlet) => nominate("thread", key, null, outlet),
          message: (key, id, outlet) => nominate("message", key, id, outlet),
          reply: (key, outlet) => nominate("reply", key, null, outlet),
        }),
      );
      if (rendering?.then)
        return Promise.race([
          rendering,
          new Promise((resolve) =>
            abort.signal.addEventListener("abort", resolve, { once: true }),
          ),
        ])
          .then(finish)
          .finally(() => {
            accepting = false;
          });
      return finish();
    } catch (error) {
      accepting = false;
      throw error;
    }
  }
  async function paint(current) {
    if (!active || generation !== current) return;
    for (const item of selected)
      if (!owner.isConnected || !item.outlet.isConnected || !under(item.outlet, owner))
        throw new Error(
          "A primary Thread outlet must remain inside its connected owner",
        );
    const wanted = new Set(selected.map((item) => item.identity));
    for (const [key, view] of views)
      if (!wanted.has(key)) {
        view.dispose();
        view.node.remove();
        for (const slot of view.slots ?? []) slot.remove();
        views.delete(key);
      }
    destinations.clear();
    for (const item of selected) {
      let view = views.get(item.identity);
      if (!view) {
        if (item.kind === "thread")
          view = new ThreadView("outlet", { ...commands, nativeAuthored: true });
        else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui";
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          node.dataset.lfGen = "1";
          node.dataset.lfOffer = "";
          if (item.kind === "message") {
            const message = new MessageView(commands);
            node.append(message.node);
            view = { node, message, dispose: () => message.retire() };
          } else {
            let joined = false;
            const reply = createReplyView(item.key, commands.reply, {
              onChange: () => {
                if (joined) update();
              },
            });
            joined = true;
            node.append(reply.node);
            view = { node, reply, dispose: reply.dispose };
          }
        }
        views.set(item.identity, view);
      }
      if (item.kind === "thread") {
        view.present(
          threadReading(
            item.thread,
            "outlet",
            { ...commands, nativeAuthored: true },
            {},
          ),
        );
        view.commit();
      } else {
        keeps(view.node, "data-thread", item.thread.id);
        keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
        if (item.kind === "message") {
          const message = item.thread.msgs.find((entry) => entry.id === item.message);
          view.message.present(
            messageReading(message, {
              panel: false,
              nativeAuthored: true,
              reactions: reactionReading(item.thread, message, true),
              workflows: message.workflows,
            }),
          );
          view.message.commit();
        } else keepsHidden(view.node, !replyAvailable(item.thread));
      }
      // A native slot keeps the canonical conversation and its authored widgets in
      // the document's stylesheet scope, including html/body state conditions.
      // The package's shadow tree owns only their physical layout. No copied style
      // sheet or second renderer is needed for arbitrary nested package widgets.
      const slots = (view.slots ??= []);
      let destination = item.outlet;
      let previous = null;
      let depth = 0;
      for (let host; (host = shadowHost(destination.getRootNode()));) {
        let slot = slots[depth];
        if (!slot) {
          slot = document.createElement("slot");
          slot.name = "lf-thread-part-" + crypto.randomUUID();
          slots.push(slot);
        }
        keeps(slot, "slot", previous?.name ?? null);
        if (slot.parentNode !== destination) destination.append(slot);
        previous = slot;
        destination = host;
        depth++;
      }
      for (const slot of slots.splice(depth)) slot.remove();
      keeps(view.node, "slot", previous?.name ?? null);
      if (view.node.parentNode !== destination) destination.append(view.node);
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    const widgets = [...readApplication().document.descriptors.values()]
      .filter(
        (descriptor) =>
          descriptor.document.kind === "thread" &&
          renderedUnder(elementById(descriptor.id), owner),
      )
      .map((descriptor) => descriptor.id);
    await whenWidgetsPresented(widgets);
  }
  const destination = (key, { message = null, focus = null } = {}) => {
    const parts = destinations.get(key) ?? [];
    if (message) {
      for (const view of parts) {
        const node = view.node.querySelector(
          `.lf-msg[data-event="${CSS.escape(message)}"]`,
        );
        if (node) return node;
      }
      return null;
    }
    if (focus !== "thread")
      for (const view of parts) {
        const input = view.node.querySelector(SAY_BOX);
        if (input && !view.node.hidden) return input;
      }
    return parts[0]?.node ?? null;
  };
  return Object.freeze({
    owner,
    prepare,
    destination,
    ownsMessage: (message) => owner.isConnected && nativeMessages.has(message.id),
    ownsDestination: (node) =>
      [...views.values()].some((view) => under(node, view.node)),
    cancel() {
      ++generation;
      pending?.abort();
      clear();
    },
    unregister() {
      active = false;
      ++generation;
      pending?.abort();
      clear();
    },
  });
}
