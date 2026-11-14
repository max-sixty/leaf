/* The page's primary reader of Thread conversations: the one presentation, a
   package's or the floating panel's, that draws each thread in outlets it names
   (application.js, `attachPresentation`). */
import { aborted } from "../abort.js";
import { randomId } from "../ids.js";
import { under, renderedUnder, shadowHost } from "../shadow.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { MessageView, messageReading } from "./messages.js";
import { createReplyView } from "./replies.js";
import { keeps, keepsHidden } from "../keeps.js";
import { generatedElement } from "../widget-elements.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { elementById } from "../passages.js";
import { THREAD, threadPart, wholeThread } from "./selectors.js";
import { threadRewrites } from "./message-edit.js";
import { orderChildren } from "../dom-children.js";
import { move } from "../dom-move.js";
import { growthIsSeen } from "../geometry.js";
import { HeldNews, newsNotice } from "./held-news.js";
import { turns } from "./model.js";

/* A selected primary reader joins the required thread presentation. Packages nominate
   complete conversations or retained fragments; core owns their generated roots,
   editors, exact-version read observation and the single authored widget instances,
   which stand here before any other drawing of their message (messages.js,
   `authoredHolders`). A thread part is the whole thread, drawn as every surface draws
   one (thread-card.js, `ThreadView`); its nomination may say where the thread stands
   the parts it draws apart (`ThreadOutlets`), as the floating panel's view stands its
   notice and settlement on its head line and its reply box in the row's field, and
   whether it draws the words it is about. Its optional `drawn()` runs after its DOM is
   placed, before asynchronous widget preparation completes, and the thread then reads
   the box its nomination says scrolls it (`ThreadView.settled`). A message part is one
   of its thread's turns
   (model.js, `turns`), the messages a card draws: its root, even a reaction, and its
   spoken messages. A later reaction stands as the pressed chip on the message it
   answers, so naming one as a part of its own is refused, as naming a message the
   thread lacks is. A message part offers the user's rewrite of it, and
   a reply part ↑ to the latest, as a thread card does, through the thread's one
   rewrite owner over the parts this reader draws (`threadRewrites`). Layout and
   disclosure belong to the caller. The thread's reply destination is its reply box as
   the parts stand: a thread's or a reply part's, or the one the presentation drawing
   them declares (selectors.js, `threadPart`), as the floating panel declares its
   field. A reply part takes the presentation's words for its box and its own landing
   of a send (replies.js, `createReplyView`), as a thread part's reply outlet does. It
   stands in a resolved thread too, where a reply reopens the thread, as a card's reply
   row does. The thread itself, where a walk or a notice lands the keyboard, is the
   drawing the presentation declares around the parts, as the panel's view is. The
   notice of what the reader holds back (held-news.js) stands in a thread part as a
   card's does, or where its nomination stands it; among message parts it stands at
   the end of the first part's head, in room every such head keeps for it, so news
   arriving moves none of the head's words. */
/** @typedef {Pick<ReturnType<typeof import("./state.js").readThreads>, "phase" | "threads">} PrimaryCollection */
/** @typedef {import("./thread-card.js").ThreadOutlets & {drawn?: () => unknown}} ThreadOptions */
/** @typedef {{signal: AbortSignal,
 * thread: (key: string, outlet: Element, options?: ThreadOptions) => void,
 * message: (key: string, message: string, outlet: Element) => void,
 * reply: (key: string, outlet: Element, options?: import("./replies.js").ReplyOptions) => void}} NominationParts */
/** @typedef {(collection: PrimaryCollection, parts: NominationParts) => unknown} PrimaryRender */
/** @typedef {ReturnType<typeof newsNotice>} PartNotice */
/** @typedef {{node: HTMLDivElement, notice: PartNotice, dispose: () => void}} PartBase */
/** @typedef {PartBase & {kind: "message", message: MessageView, messageKey: string, reading: ReturnType<typeof messageReading>, draw: () => void}} MessagePart */
/** @typedef {PartBase & {kind: "reply", reply: ReturnType<typeof createReplyView>}} ReplyPart */
/** @typedef {ThreadView & {kind: "thread"}} WholePart */
/** @typedef {WholePart | MessagePart | ReplyPart} RetainedPart */
/** @typedef {{key: string, outlet: Element} & ({kind: "thread", message: null, options: ThreadOptions} | {kind: "reply", message: null, options: import("./replies.js").ReplyOptions} | {kind: "message", message: string, options: {}})} PartRequest */
/** @typedef {PartRequest & {identity: string, thread: import("./thread-card.js").ThreadRecord}} Nomination */
// The places a nomination names, with what stands in each: the part in its outlet, and
// a whole thread's parts it draws apart in the places its options name
// (thread-card.js, `ThreadOutlets`). Every place is held to what an outlet is: inside the
// owner, connected, and reached through slots where it stands in a shadow tree.
/** @param {PartRequest} item @returns {[Element, (view: RetainedPart) => Element][]} */
const placesOf = (item) => {
  /** @type {[Element, (view: RetainedPart) => Element][]} */
  const places = [[item.outlet, (view) => view.node]];
  if (item.kind !== "thread") return places;
  /** @param {keyof ThreadView["apart"]} part @returns {(view: RetainedPart) => Element} */
  const apart = (part) => (view) =>
    view.kind === "thread" ? view.apart[part] : view.node;
  const { head, reply } = item.options;
  if (head) places.push([head.news, apart("news")], [head.controls, apart("controls")]);
  if (head?.unread) places.push([head.unread, apart("unread")]);
  if (reply?.outlet) places.push([reply.outlet, apart("reply")]);
  return places;
};
// What a part stands in its places: its own box, and a whole thread's boxes apart.
/** @param {RetainedPart} view @returns {Element[]} */
const boxesOf = (view) =>
  view.kind === "thread" ? [view.node, ...Object.values(view.apart)] : [view.node];
/** @param {Element} owner @param {PrimaryRender} render
 * @param {import("./thread-card.js").ThreadCommands} commands @param {() => Promise<unknown>} update
 * @param {{answersAtOnce?: () => boolean, onFailure?: () => void}} [options] */
export function createPrimaryReader(
  owner,
  render,
  commands,
  update,
  { answersAtOnce = () => false, onFailure = () => {} } = {},
) {
  let active = true;
  // Whether the presentation's own part of the current pass failed: its render, the
  // outlets it named, or their paint. The pass that fails cancels the reader, which
  // then says so (`onFailure`), and reads as `failed` until a later pass paints.
  let failing = false;
  let failed = false;
  let generation = 0;
  /** @type {AbortController | null} */
  let pending = null;
  /** @type {Nomination[]} */
  let selected = [];
  /** @type {Map<string, RetainedPart>} */
  const views = new Map();
  /** @type {Map<string, RetainedPart[]>} */
  const destinations = new Map();
  /** @type {Set<string>} */
  const nativeMessages = new Set();
  const held = new HeldNews(
    owner,
    (key) => {
      const parts = destinations.get(key);
      const last = parts?.at(-1);
      if (!parts || !last) return null;
      const whole = parts.find((part) => part instanceof ThreadView);
      return {
        node: drawingOf(parts) ?? last.node,
        progressOpen: whole?.progressOpen ?? false,
        // A presentation that makes room for the agent's answer to the user's last turn
        // itself is handed it whatever it moves, while it says it has that room as the
        // news comes (`answersAtOnce`). A whole thread moves what a card's would
        // (thread-card.js, `newsMoves`).
        newsMoves: (held) =>
          !(held.answers && answersAtOnce()) &&
          (whole
            ? whole.newsMoves(held)
            : parts.some(
                (part) =>
                  (held.news.appended ||
                    held.news.settled ||
                    (part.kind === "message" && held.changed.has(part.messageKey)) ||
                    (part.kind === "message" &&
                      held.folds.messages.includes(part.messageKey)) ||
                    Boolean(held.folds.summaries.length)) &&
                  growthIsSeen(part.node),
              )),
      };
    },
    () => void update().catch(() => {}),
  );
  /** @type {Map<string, import("./held-news.js").HeldThread>} */
  let shown = new Map();
  // The thread as a whole where the presentation draws one around its parts, as the
  // floating panel's view is a drawing of the thread its messages are drawn in
  // (selectors.js, `wholeThread`): what a keyboard landing on the thread stands on.
  /** @param {readonly RetainedPart[]} parts */
  const drawingOf = (parts) => {
    const first = parts[0];
    if (!first) return null;
    const whole = wholeThread(first.node);
    return whole === first.node ? null : whole;
  };
  // Each thread's rewrites over the message parts of it this reader draws
  // (`threadRewrites`): its messages in the thread's order, and its reply box. A whole
  // thread keeps its own.
  /** @type {Map<string, ReturnType<typeof threadRewrites>>} */
  const rewrites = new Map();
  /** @template {RetainedPart["kind"]} K @param {string} key @param {K} kind
   * @returns {Extract<RetainedPart, {kind: K}>[]} */
  const partsOf = (key, kind) => {
    /** @type {Extract<RetainedPart, {kind: K}>[]} */
    const parts = [];
    for (const item of selected) {
      const view = views.get(item.identity);
      if (item.key === key && view && isKind(view, kind)) parts.push(view);
    }
    return parts;
  };
  /** @template {RetainedPart["kind"]} K @param {RetainedPart} view @param {K} kind
   * @returns {view is Extract<RetainedPart, {kind: K}>} */
  const isKind = (view, kind) => view.kind === kind;
  // The thread's reply box as the parts drawn stand, in a reply part or where the
  // presentation around them declares it.
  /** @param {string} key */
  const replyOf = (key) => {
    for (const view of destinations.get(key) ?? []) {
      const input = !view.node.hidden && threadPart(view.node, "reply");
      if (input) return input;
    }
    return null;
  };
  /** @param {string} key */
  const rewritesOf = (key) => {
    let rewrite = rewrites.get(key);
    if (!rewrite) {
      rewrite = threadRewrites({
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
        paint: (node) =>
          partsOf(key, "message")
            .find((view) => view.message.node === node)
            ?.draw(),
        box: () => replyOf(key),
        home: (node) => {
          const home = node?.closest(THREAD);
          if (!home)
            throw new Error("A primary message must stand in its drawn thread");
          return home;
        },
        opening: () => {
          shown.get(key)?.news?.open();
        },
        landInThread: commands.reply.landInThread,
        landSent: commands.reply.landSent,
      });
      rewrites.set(key, rewrite);
    }
    return rewrite;
  };
  // The slots each box a part stands reaches its place through, by the box.
  /** @type {Map<Element, HTMLSlotElement[]>} */
  const slotsOf = new Map();
  // Takes a box out of its place, with the slots it stood in.
  /** @param {Element} box */
  const unplace = (box) => {
    box.remove();
    for (const slot of slotsOf.get(box) ?? []) slot.remove();
    slotsOf.delete(box);
  };
  // Every place the nominations name stands inside the connected owner.
  /** @param {readonly PartRequest[]} items */
  const checkPlaces = (items) => {
    for (const item of items)
      for (const [place] of placesOf(item))
        if (!owner.isConnected || !place.isConnected || !under(place, owner))
          throw new Error(
            "A primary Thread outlet must remain inside its connected owner",
          );
  };
  const clear = () => {
    for (const view of views.values()) {
      view.dispose();
      for (const box of boxesOf(view)) unplace(box);
    }
    views.clear();
    destinations.clear();
    nativeMessages.clear();
    rewrites.clear();
  };
  /** @param {PrimaryCollection} collection @param {Promise<unknown>} cancelled */
  function prepare(collection, cancelled) {
    const current = ++generation;
    failing = false;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const candidate = held.prepare({
      threads: collection.threads.map((thread) =>
        threadReading(thread, "outlet", { ...commands, authoredRank: 3 }),
      ),
    });
    const byKey = new Map(
      candidate.reading.threads.map((thread) => [thread.key, thread.source]),
    );
    const shownCollection = Object.freeze({
      phase: collection.phase,
      threads: Object.freeze([...byKey.values()]),
    });
    /** @type {Nomination[]} */
    const nominations = [];
    let accepting = true;
    /** @param {PartRequest} request */
    const nominate = (request) => {
      const { kind, key, message } = request;
      if (!accepting || abort.signal.aborted)
        throw new Error("Thread nominations belong to their current render callback");
      const thread = byKey.get(key);
      if (!thread) throw new Error(`No Thread has key ${key}`);
      if (message !== null && !turns(thread).some((item) => item.key === message))
        throw new Error(`Thread ${key} has no turn ${message}`);
      const identity = JSON.stringify([kind, key, message]);
      // A whole thread draws every part of it.
      /** @param {PartRequest["kind"]} a */
      const covers = (a) => a === "thread";
      if (
        nominations.some(
          (item) =>
            item.identity === identity ||
            (item.key === key && (covers(item.kind) || covers(kind))),
        )
      )
        throw new Error("A primary reader may nominate each Thread part only once");
      nominations.push({ ...request, identity, thread });
    };
    const finish = () => {
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return null;
      checkPlaces(nominations);
      selected = nominations;
      shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (item.kind === "thread" || item.message === message.key)
            nativeMessages.add(message.id);
      return {
        paint: async () => {
          try {
            await paint(current, () => {
              if (!active || current !== generation || abort.signal.aborted) return;
              candidate.commit();
              for (const item of nominations) {
                if (item.kind !== "thread") continue;
                item.options.drawn?.();
                const view = views.get(item.identity);
                if (view?.kind === "thread") view.settled();
              }
            });
          } catch (error) {
            failing ||= current === generation;
            throw error;
          }
          if (active && current === generation && !abort.signal.aborted) failed = false;
        },
        current: () => active && current === generation && !abort.signal.aborted,
      };
    };
    try {
      const rendering = render(
        shownCollection,
        Object.freeze({
          signal: abort.signal,
          thread: (key, outlet, options) =>
            nominate({
              kind: "thread",
              key,
              message: null,
              outlet,
              options: options ?? {},
            }),
          message: (key, id, outlet) =>
            nominate({ kind: "message", key, message: id, outlet, options: {} }),
          reply: (key, outlet, options) =>
            nominate({
              kind: "reply",
              key,
              message: null,
              outlet,
              options: options ?? {},
            }),
        }),
      );
      if (
        rendering != null &&
        (typeof rendering === "object" || typeof rendering === "function") &&
        "then" in rendering &&
        typeof rendering.then === "function"
      )
        return Promise.race([rendering, aborted(abort.signal)])
          .then(finish)
          .catch((error) => {
            failing ||= !abort.signal.aborted;
            throw error;
          })
          .finally(() => {
            accepting = false;
          });
      return finish();
    } catch (error) {
      accepting = false;
      failing = true;
      throw error;
    }
  }
  /** @param {import("./thread-card.js").ThreadRecord} thread @param {string} key */
  const messageSource = (thread, key) => {
    const message = thread.msgs.find((entry) => entry.key === key);
    if (!message) throw new Error(`Thread ${thread.key} has no message ${key}`);
    return message;
  };
  /** @param {import("./thread-card.js").ThreadRecord} thread @param {string} key */
  const messageModel = (thread, key) => {
    const message = messageSource(thread, key);
    return messageReading(message, {
      authoredRank: 3,
      workflows: message.workflows,
    });
  };
  /** @param {number} current @param {() => void} drawn */
  async function paint(current, drawn) {
    if (!active || generation !== current) return;
    checkPlaces(selected);
    const wanted = new Set(selected.map((item) => item.identity));
    const keys = new Set(selected.map((item) => item.key));
    for (const key of rewrites.keys()) if (!keys.has(key)) rewrites.delete(key);
    for (const [key, view] of views)
      if (!wanted.has(key)) {
        view.dispose();
        for (const box of boxesOf(view)) unplace(box);
        views.delete(key);
      }
    destinations.clear();
    /** @type {Map<Element, Element[]>} */
    const children = new Map();
    /** @param {Element} parent @param {Element} node */
    const place = (parent, node) => {
      const nodes = children.get(parent) ?? [];
      nodes.push(node);
      children.set(parent, nodes);
    };
    /** @type {{item: Nomination, view: RetainedPart, reading: import("./held-news.js").HeldThread}[]} */
    const drawing = [];
    // The boxes this pass places.
    /** @type {Set<Element>} */
    const placed = new Set();
    for (const item of selected) {
      const reading = shown.get(item.key);
      if (!reading) throw new Error(`No prepared Thread has key ${item.key}`);
      let view = views.get(item.identity);
      if (!view) {
        if (item.kind === "thread") {
          /** @type {WholePart} */
          const whole = Object.assign(
            new ThreadView(commands, reading),
            /** @satisfies {{kind: "thread"}} */ ({ kind: "thread" }),
          );
          view = whole;
        } else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ring-overlay lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          generatedElement(node, { says: false });
          node.dataset.lfOffer = "";
          const notice = newsNotice();
          notice.node.classList.add("lf-primary-news");
          if (item.kind === "message") {
            // A press on a reply's reactions is the user acting in this thread, so
            // what the reader holds of it shows with it, as in a card (thread-card.js).
            const message = new MessageView({
              ...commands,
              reaction: {
                ...commands.reaction,
                pressed: () => shown.get(item.key)?.news?.open(),
              },
              edit: rewritesOf(item.key).edit,
            });
            node.append(message.node);
            /** @type {MessagePart} */
            const part = {
              kind: "message",
              node,
              notice,
              message,
              messageKey: item.message,
              reading: messageModel(item.thread, item.message),
              // Draws the message again at once, as its rewrite opens or closes, the
              // thread's notice in its head.
              draw() {
                message.present(this.reading, { headerControls: this.notice.node });
                message.commit();
              },
              dispose: () => message.retire(),
            };
            view = part;
          } else {
            let joined = false;
            // What the box reads, when it holds its sends and how a send lands are the
            // presentation's (replies.js, `createReplyView`), given with its nomination.
            // The part draws whichever row the view holds: its own, or the session's
            // row it takes from a view that can draw the thread no more, the user
            // still in it (replies.js, `carry`).
            const redraw = () => {
              for (const row of node.querySelectorAll(":scope > .lf-thread-reply"))
                if (row !== reply.node) row.remove();
              move(node, reply.node, node.firstChild);
            };
            const reply = createReplyView(item.key, commands.reply, redraw, {
              ...item.options,
              onChange: () => {
                if (joined) void update().catch(() => {});
              },
              editLast: rewritesOf(item.key).editLast,
            });
            joined = true;
            node.append(reply.node);
            view = { kind: "reply", node, notice, reply, dispose: reply.dispose };
          }
        }
        views.set(item.identity, view);
      }
      // A native slot keeps the canonical conversation and its authored widgets in
      // the document's stylesheet scope, including html/body state conditions.
      // The package's shadow tree owns only their physical layout. No copied style
      // sheet or second renderer is needed for arbitrary nested package widgets.
      for (const [outlet, boxOf] of placesOf(item)) {
        const box = boxOf(view);
        placed.add(box);
        const slots = slotsOf.get(box) ?? [];
        slotsOf.set(box, slots);
        let destination = outlet;
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
        keeps(box, "slot", previous?.name ?? null);
        place(destination, box);
      }
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
      drawing.push({ item, view, reading });
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
    // A box its part stands in no place now, as a thread's notice where its reader no
    // longer names a head, leaves.
    for (const view of views.values())
      for (const box of boxesOf(view)) if (!placed.has(box)) unplace(box);
    // Each part draws where it now stands, so what it reads of its own layout is read
    // in place: a package may hand a new outlet on each render, and a thread drawn out
    // of the document read no room for its held news beside its first head, its notice
    // standing at the head's start until a later frame moved it to its place
    // (thread-card.js, `#retainHeaderSlot`).
    for (const { item, view, reading } of drawing) {
      if (view.kind === "thread") {
        if (item.kind === "thread") {
          // Only what a nomination may ask of its thread (module-annotations.md), so
          // nothing else it passed reaches the view, as a margin card's own head line
          // would move the package's element into the thread (thread-card.js,
          // `CardOutlets`). A nomination that lands the user elsewhere is where taking
          // back the settlement opens the thread again (`ViewOutlets`, `reader`).
          const { head, reply, quote, scroller, landing } = item.options;
          view.setOutlets({
            ...(head && {
              head: {
                news: head.news,
                controls: head.controls,
                ...(head.unread && { unread: head.unread }),
              },
            }),
            ...(reply && { reply }),
            ...(quote && { quote }),
            ...(scroller && { scroller }),
            ...(landing && { landing, reader: /** @type {const} */ ("primary") }),
          });
        }
        view.present(reading);
        view.commit();
      } else {
        keeps(view.node, "data-lf-thread", item.thread.id);
        keeps(view.node, "data-lf-attempt", item.thread.root.attempt ?? null);
        const news = shown.get(item.key)?.news;
        const first =
          selected.find((part) => part.key === item.key && part.kind === "message") ??
          selected.find((part) => part.key === item.key);
        const notice = Boolean(news) && first === item;
        if (notice && news) view.notice.set(news);
        keepsHidden(view.notice.node, !notice);
        if (view.kind === "message") {
          const message = messageSource(item.thread, view.messageKey);
          view.reading = messageModel(item.thread, view.messageKey);
          view.draw();
          // A reply still streaming at the thread's end grows at its foot as its words
          // come, as in a thread card (thread-card.js, shift_watch.js).
          keeps(
            view.node,
            "data-lf-append-tail",
            message.provisional && message === item.thread.msgs.at(-1) ? "" : null,
          );
        } else if (view.notice.node.parentNode !== view.node)
          move(view.node, view.notice.node, null);
      }
    }
    // A thread or a reply part standing in the document takes the row being written in
    // its thread that no view holds (replies.js, `claim`).
    for (const view of views.values())
      if (view.kind === "reply")
        view.reply.claim(() => view.node.isConnected && !view.node.hidden);
      else if (view.kind === "thread") view.claimReply(() => view.node.isConnected);
    // What the reader drew is now on screen: it becomes the held-news baseline and its
    // presentation can land it before the next frame. Widget preparation is separate
    // readiness; waiting for it cannot postpone what these words already drew.
    drawn();
    const widgets = [...readApplication().document.descriptors.values()]
      .filter(
        (descriptor) =>
          descriptor.document.kind === "thread" &&
          renderedUnder(elementById(descriptor.id), owner),
      )
      .map((descriptor) => descriptor.id);
    await whenWidgetsPresented(widgets);
  }
  /** @param {string} key
   * @param {{message?: string | null, part?: import("./destination.js").ThreadPart}} [options] */
  const destination = (key, { message = null, part = null } = {}) => {
    const parts = destinations.get(key) ?? [];
    if (message) {
      const id = shown.get(key)?.source.msgs.find((item) => item.key === message)?.id;
      if (!id) return null;
      for (const view of parts) {
        const node = view.node.querySelector(
          `.lf-msg[data-lf-event="${CSS.escape(id)}"]`,
        );
        if (node) return node;
      }
      return null;
    }
    const first = parts[0]?.node ?? null;
    if (part === "thread") return (parts.length && drawingOf(parts)) || first;
    return replyOf(key) || first;
  };
  return Object.freeze({
    owner,
    update,
    release: () => held.release(),
    prepare,
    destination,
    ownsMessage: /** @param {{id: string}} message */ (message) =>
      owner.isConnected && nativeMessages.has(message.id),
    ownsDestination: /** @param {Element} node */ (node) =>
      [...views.values()].some((view) =>
        boxesOf(view).some((box) => under(node, box)),
      ) ||
      [...destinations.keys()].some((key) => replyOf(key) === node) ||
      [...destinations.values()].some((parts) => drawingOf(parts) === node),
    cancel() {
      ++generation;
      pending?.abort();
      clear();
      held.release();
      if (failing) {
        failing = false;
        failed = true;
        onFailure();
      }
    },
    get failed() {
      return failed;
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
