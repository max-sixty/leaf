/* Package-owned primary readers and optional mirrors of Thread conversations.

   An optional mirror is a view of the shared Thread reading, never a placement of
   the original Thread. Optional consumers reconcile their outlets and async
   preparation independently of the core panel, margin, and read presentation. A later reading or
   unregister aborts its predecessor before any DOM from that predecessor commits. */
import { randomId } from "../ids.js";
import { reportPageError } from "../layer-client.js";
import { under, renderedUnder, shadowHost } from "../shadow.js";
import { clearThreadMirrors, renderThreadMirrors } from "./inline.js";
import { readThreads } from "./state.js";
import { watchThreads } from "./watch.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { MessageView, messageReading } from "./messages.js";
import { createReplyView, replyAvailable } from "./replies.js";
import { keeps, keepsHidden } from "../keeps.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { elementById } from "../passages.js";
import { SAY_BOX, THREAD } from "./selectors.js";
import { threadRewrites } from "./message-edit.js";
import { orderChildren } from "../dom-children.js";
import { growthIsSeen } from "../geometry.js";
import { HeldNews, newsNotice } from "./held-news.js";

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
    reportPageError(error, `Thread mirrors in ${owner.localName}#${owner.id} failed`);

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
      thread(key, outlet) {
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
   one physical destination on every pass. A message part offers the user's rewrite of
   it, and a reply part ↑ to the latest, as a thread card does, through the thread's one
   rewrite owner over the parts this reader draws (`threadRewrites`). Layout and
   disclosure belong to the caller. */
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
  const held = new HeldNews(
    owner,
    (key) => {
      const parts = destinations.get(key);
      if (!parts?.length) return null;
      const whole = parts.find((part) => part instanceof ThreadView);
      if (whole) return whole;
      return {
        node: parts.at(-1).node,
        newsMoves: ({ news, changed, folds }) =>
          parts.some(
            (part) =>
              (news.appended ||
                news.settled ||
                changed.has(part.messageKey) ||
                folds.messages.includes(part.messageKey) ||
                folds.summaries.length) &&
              growthIsSeen(part.node),
          ),
      };
    },
    () => void update().catch(() => {}),
  );
  let shown = new Map();
  // Each thread's rewrites over the parts of it this reader draws (`threadRewrites`):
  // its messages in the thread's order, and its reply box.
  const rewrites = new Map();
  const partsOf = (key, kind) =>
    selected
      .filter((item) => item.key === key && item.kind === kind)
      .flatMap((item) => views.get(item.identity) ?? []);
  const rewritesOf = (key) => {
    if (!rewrites.has(key))
      rewrites.set(
        key,
        threadRewrites({
          views: () => {
            const order = shown.get(key)?.source.msgs.map((message) => message.key);
            return partsOf(key, "message")
              .toSorted(
                (a, b) =>
                  (order?.indexOf(a.messageKey) ?? 0) -
                  (order?.indexOf(b.messageKey) ?? 0),
              )
              .map((view) => view.message);
          },
          send: (id, text, options) =>
            commands.reply.actions.edit(key, id, text, options),
          paint: (node) =>
            partsOf(key, "message")
              .find((view) => view.message.node === node)
              ?.draw(),
          box: () => {
            const reply = partsOf(key, "reply")[0];
            return reply && !reply.node.hidden
              ? reply.node.querySelector(SAY_BOX)
              : null;
          },
          home: (node) => node.closest(THREAD),
          opening: () => shown.get(key)?.news?.open(),
          landInThread: commands.reply.landInThread,
          landSent: commands.reply.landSent,
        }),
      );
    return rewrites.get(key);
  };
  const clear = () => {
    for (const view of views.values()) {
      view.dispose();
      view.node.remove();
      for (const slot of view.slots ?? []) slot.remove();
    }
    views.clear();
    destinations.clear();
    nativeMessages.clear();
    rewrites.clear();
  };
  function prepare(collection, cancelled) {
    const current = ++generation;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const candidate = held.prepare(
      {
        threads: collection.threads.map((thread) =>
          threadReading(thread, "outlet", { ...commands, nativeAuthored: true }, {}),
        ),
      },
      { row: false },
    );
    const byKey = new Map(
      candidate.reading.threads.map((thread) => [thread.key, thread.source]),
    );
    const shownCollection = Object.freeze({
      phase: collection.phase,
      threads: Object.freeze([...byKey.values()]),
    });
    const nominations = [];
    let accepting = true;
    const nominate = (kind, key, message, outlet) => {
      if (!accepting || abort.signal.aborted)
        throw new Error("Thread nominations belong to their current render callback");
      if (!(outlet instanceof Element))
        throw new TypeError("A Thread outlet must be an Element");
      const thread = byKey.get(key);
      if (!thread) throw new Error(`No Thread has key ${key}`);
      if (message !== null && !thread.msgs.some((item) => item.key === message))
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
      shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (item.kind === "thread" || item.message === message.key)
            nativeMessages.add(message.id);
      return {
        paint: async () => {
          await paint(current);
          if (active && current === generation && !abort.signal.aborted)
            candidate.commit();
        },
        current: () => active && current === generation && !abort.signal.aborted,
      };
    };
    try {
      const rendering = render(
        shownCollection,
        Object.freeze({
          signal: abort.signal,
          thread: (key, outlet) => nominate("thread", key, null, outlet),
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
    const keys = new Set(selected.map((item) => item.key));
    for (const key of rewrites.keys()) if (!keys.has(key)) rewrites.delete(key);
    for (const [key, view] of views)
      if (!wanted.has(key)) {
        view.dispose();
        view.node.remove();
        for (const slot of view.slots ?? []) slot.remove();
        views.delete(key);
      }
    destinations.clear();
    const children = new Map();
    const place = (parent, node) => {
      const nodes = children.get(parent) ?? [];
      nodes.push(node);
      children.set(parent, nodes);
    };
    for (const item of selected) {
      let view = views.get(item.identity);
      if (!view) {
        if (item.kind === "thread")
          view = new ThreadView("outlet", { ...commands, nativeAuthored: true });
        else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          node.dataset.lfGen = "1";
          node.dataset.lfOffer = "";
          if (item.kind === "message") {
            const message = new MessageView({
              ...commands,
              edit: rewritesOf(item.key).edit,
            });
            message.node.classList.add("lf-primary-message");
            node.append(message.node);
            view = {
              node,
              message,
              messageKey: item.message,
              reading: null,
              // Draws the message again at once, as its rewrite opens or closes.
              draw() {
                message.present(this.reading, { headerControls: this.notice.node });
                message.commit();
              },
              dispose: () => message.retire(),
            };
          } else {
            let joined = false;
            const reply = createReplyView(item.key, commands.reply, {
              onChange: () => {
                if (joined) void update().catch(() => {});
              },
              editLast: rewritesOf(item.key).editLast,
            });
            joined = true;
            node.append(reply.node);
            view = { node, reply, dispose: reply.dispose };
          }
          view.notice = newsNotice();
          view.notice.node.classList.add("lf-primary-news");
        }
        views.set(item.identity, view);
      }
      if (item.kind === "thread") {
        view.present(shown.get(item.key));
        view.commit();
      } else {
        keeps(view.node, "data-thread", item.thread.id);
        keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
        const news = shown.get(item.key)?.news;
        const first =
          selected.find((part) => part.key === item.key && part.kind === "message") ??
          selected.find((part) => part.key === item.key);
        const notice = Boolean(news) && first === item;
        if (notice) view.notice.set(news);
        keepsHidden(view.notice.node, !notice);
        if (item.kind === "message") {
          const message = item.thread.msgs.find((entry) => entry.key === item.message);
          view.reading = messageReading(message, {
            panel: false,
            nativeAuthored: true,
            reactions: message.reactions,
            workflows: message.workflows,
          });
          view.draw();
        } else {
          keepsHidden(view.node, !replyAvailable(item.thread));
          if (view.notice.node.parentNode !== view.node)
            view.node.append(view.notice.node);
        }
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
          slot.name = "lf-thread-part-" + randomId();
          slots.push(slot);
        }
        keeps(slot, "slot", previous?.name ?? null);
        place(destination, slot);
        previous = slot;
        destination = host;
        depth++;
      }
      for (const slot of slots.splice(depth)) slot.remove();
      keeps(view.node, "slot", previous?.name ?? null);
      place(destination, view.node);
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
    const widgets = [...readApplication().document.descriptors.values()]
      .filter(
        (descriptor) =>
          descriptor.document.kind === "thread" &&
          renderedUnder(elementById(descriptor.id), owner),
      )
      .map((descriptor) => descriptor.id);
    await whenWidgetsPresented(widgets);
  }
  const destination = (key, { message = null, part = null } = {}) => {
    const parts = destinations.get(key) ?? [];
    if (message) {
      const id = shown.get(key)?.source.msgs.find((item) => item.key === message)?.id;
      if (!id) return null;
      for (const view of parts) {
        const node = view.node.querySelector(`.lf-msg[data-event="${CSS.escape(id)}"]`);
        if (node) return node;
      }
      return null;
    }
    if (part !== "thread")
      for (const view of parts) {
        const input = view.node.querySelector(SAY_BOX);
        if (input && !view.node.hidden) return input;
      }
    return parts[0]?.node ?? null;
  };
  return Object.freeze({
    owner,
    update,
    release: () => held.release(),
    prepare,
    destination,
    ownsMessage: (message) => owner.isConnected && nativeMessages.has(message.id),
    ownsDestination: (node) =>
      [...views.values()].some((view) => under(node, view.node)),
    cancel() {
      ++generation;
      pending?.abort();
      clear();
      held.release();
    },
    unregister() {
      active = false;
      ++generation;
      pending?.abort();
      clear();
      held.dispose();
    },
  });
}
