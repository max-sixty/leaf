/* The page's primary reader of Thread conversations: the one presentation, a
   package's or the floating panel's, that draws each thread in outlets it names
   (application.js, `attachPresentation`). */
import { aborted } from "../abort.js";
import { randomId } from "../ids.js";
import { under, renderedUnder, shadowHost } from "../shadow.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { MessageView, messageReading } from "./messages.js";
import { Transcript } from "./transcript.js";
import { createReplyView } from "./replies.js";
import { keeps, keepsHidden } from "../keeps.js";
import { generatedElement } from "../widget-elements.js";
import { focusDestination } from "../focus.js";
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
   `authoredHolders`). A message part is one of its thread's turns
   (model.js, `turns`), the messages a card draws: its root, even a reaction, and its
   spoken messages. A later reaction stands as the pressed chip on the message it
   answers, so naming one as a part of its own is refused, as naming a message the
   thread lacks is. A transcript part is all of them, drawn as a card draws them, folds
   and working message included (transcript.js), for a presentation that draws the
   thread's head and reply box itself, as the floating panel's view does; it stands
   instead of message parts of its thread, and grows at its foot, the growing tail
   (`data-lf-append-tail`) of an outlet that declares itself an append region, as the
   panel's does. Its optional `drawn(answer)` runs after its DOM is placed, before
   asynchronous widget preparation completes: null unless this draw answers the
   user's last turn, otherwise its `{turn, reply}` keys, reply null for work alone.
   A message part offers the user's rewrite of it, and
   a reply part ↑ to the latest, as a thread card does, through the thread's one
   rewrite owner over the parts this reader draws (`threadRewrites`). Layout and
   disclosure belong to the caller, a transcript's folds aside. The thread's reply destination is its reply box as
   the parts stand: a reply part's, or the one the presentation drawing them declares
   (selectors.js, `threadPart`), as the floating panel declares its field. A reply part takes
   the presentation's words for its box and its own landing of a send (replies.js,
   `createReplyView`). It stands in a resolved thread too, where a reply reopens the
   thread, as a card's reply row does. The thread itself, where a walk or a notice lands the keyboard, is
   the drawing the presentation declares around the parts, as the panel's view is.
   The notice of what the reader holds back (held-news.js) stands where the
   presentation nominates it (`parts.news`), as the floating panel stands it on its
   view's head line, before the thread's presses. Where it nominates none, the notice
   stands at the end of the first part's head, in room every such head keeps for it,
   so news arriving moves none of the head's words. */
/** @typedef {Pick<ReturnType<typeof import("./state.js").readThreads>, "phase" | "threads">} PrimaryCollection */
/** @typedef {{drawn?: (answer: import("./held-news.js").ThreadChange["answers"] | null) => unknown}} TranscriptOptions */
/** @typedef {{signal: AbortSignal,
 * thread: (key: string, outlet: Element) => void,
 * transcript: (key: string, outlet: Element, options?: TranscriptOptions) => void,
 * message: (key: string, message: string, outlet: Element) => void,
 * reply: (key: string, outlet: Element, options?: import("./replies.js").ReplyOptions) => void,
 * news: (key: string, outlet: Element) => void}} NominationParts */
/** @typedef {(collection: PrimaryCollection, parts: NominationParts) => unknown} PrimaryRender */
/** @typedef {ReturnType<typeof newsNotice>} PartNotice */
/** @typedef {{node: HTMLDivElement, notice: PartNotice, slots?: HTMLSlotElement[], dispose: () => void}} PartBase */
/** @typedef {PartBase & {kind: "transcript", transcript: Transcript, reading: import("./held-news.js").HeldThread, drawn: boolean, headNotice: boolean, draw: () => void}} TranscriptPart */
/** @typedef {PartBase & {kind: "message", message: MessageView, messageKey: string, reading: ReturnType<typeof messageReading>, headNotice: boolean, draw: () => void}} MessagePart */
/** @typedef {PartBase & {kind: "reply", reply: ReturnType<typeof createReplyView>}} ReplyPart */
/** @typedef {{kind: "news", node: HTMLElement, notice: PartNotice, slots?: HTMLSlotElement[], dispose: () => void}} NewsPart */
/** @typedef {ThreadView & {kind: "thread", slots?: HTMLSlotElement[]}} WholePart */
/** @typedef {WholePart | TranscriptPart | MessagePart | ReplyPart | NewsPart} RetainedPart */
/** @typedef {Exclude<RetainedPart, NewsPart>} DestinationPart */
/** @typedef {{key: string, outlet: Element} & ({kind: "thread", message: null, options: {}} | {kind: "news", message: null, options: {}} | {kind: "transcript", message: null, options: TranscriptOptions} | {kind: "reply", message: null, options: import("./replies.js").ReplyOptions} | {kind: "message", message: string, options: {}})} PartRequest */
/** @typedef {PartRequest & {identity: string, thread: import("./thread-card.js").ThreadRecord}} Nomination */
/** @param {Element} owner @param {PrimaryRender} render
 * @param {import("./thread-card.js").ThreadCommands} commands @param {() => Promise<unknown>} update
 * @param {{answersAtOnce?: boolean, onFailure?: () => void}} [options] */
export function createPrimaryReader(
  owner,
  render,
  commands,
  update,
  { answersAtOnce = false, onFailure = () => {} } = {},
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
  /** @type {Map<string, DestinationPart[]>} */
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
      if (whole) return whole;
      return {
        node: drawingOf(parts) ?? last.node,
        progressOpen: parts.some(
          (part) => part.kind === "transcript" && part.transcript.progressOpen,
        ),
        // A presentation that makes room for the agent's answer to the user's last turn
        // itself (`answersAtOnce`) is handed it whatever it moves. A transcript moves
        // what a card's would (transcript.js, `newsMoves`).
        newsMoves: (held) =>
          !(answersAtOnce && held.answers) &&
          parts.some((part) =>
            part.kind === "transcript"
              ? part.transcript.newsMoves(held)
              : (held.news.appended ||
                  held.news.settled ||
                  (part.kind === "message" && held.changed.has(part.messageKey)) ||
                  (part.kind === "message" &&
                    held.folds.messages.includes(part.messageKey)) ||
                  Boolean(held.folds.summaries.length)) &&
                growthIsSeen(part.node),
          ),
      };
    },
    () => void update().catch(() => {}),
  );
  /** @type {Map<string, import("./held-news.js").HeldThread>} */
  let shown = new Map();
  // The thread as a whole where the presentation draws one around its parts, as the
  // floating panel's view is a drawing of the thread its messages are drawn in
  // (selectors.js, `wholeThread`): what a keyboard landing on the thread stands on.
  /** @param {readonly DestinationPart[]} parts */
  const drawingOf = (parts) => {
    const first = parts[0];
    if (!first) return null;
    const whole = wholeThread(first.node);
    return whole === first.node ? null : whole;
  };
  // Each thread's rewrites over the parts of it this reader draws (`threadRewrites`):
  // its messages in the thread's order, and its reply box.
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
          const transcript = partsOf(key, "transcript")[0];
          if (transcript) return transcript.transcript.views;
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
          [...partsOf(key, "transcript"), ...partsOf(key, "message")]
            .find((view) => view.kind === "transcript" || view.message.node === node)
            ?.draw(),
        box: () => replyOf(key),
        home: (node) => {
          const home = node?.closest(THREAD);
          if (!home)
            throw new Error("A primary message must stand in its drawn thread");
          return home;
        },
        opening: (id) => {
          shown.get(key)?.news?.open();
          partsOf(key, "transcript")[0]?.transcript.expandAround(id);
        },
        landInThread: commands.reply.landInThread,
        landSent: commands.reply.landSent,
      });
      rewrites.set(key, rewrite);
    }
    return rewrite;
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
  /** @param {PrimaryCollection} collection @param {Promise<unknown>} cancelled */
  function prepare(collection, cancelled) {
    const current = ++generation;
    failing = false;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const candidate = held.prepare(
      {
        threads: collection.threads.map((thread) =>
          threadReading(thread, "outlet", { ...commands, authoredRank: 3 }),
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
      // A whole thread draws every part of it, and a transcript every message.
      /** @param {PartRequest["kind"]} a @param {PartRequest["kind"]} b */
      const covers = (a, b) =>
        a === "thread" || (a === "transcript" && b === "message");
      if (
        nominations.some(
          (item) =>
            item.identity === identity ||
            (item.key === key && (covers(item.kind, kind) || covers(kind, item.kind))),
        )
      )
        throw new Error("A primary reader may nominate each Thread part only once");
      nominations.push({ ...request, identity, thread });
    };
    const finish = () => {
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return null;
      for (const item of nominations) {
        if (!item.outlet.isConnected || !under(item.outlet, owner))
          throw new Error(
            "A primary Thread outlet must remain inside its connected owner",
          );
      }
      selected = nominations;
      shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (
            item.kind === "thread" ||
            item.kind === "transcript" ||
            item.message === message.key
          )
            nativeMessages.add(message.id);
      return {
        paint: async () => {
          try {
            await paint(current, () => {
              if (!active || current !== generation || abort.signal.aborted) return;
              candidate.commit();
              for (const item of nominations)
                if (item.kind === "transcript")
                  item.options.drawn?.(shown.get(item.key)?.change?.answers ?? null);
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
          thread: (key, outlet) =>
            nominate({ kind: "thread", key, message: null, outlet, options: {} }),
          transcript: (key, outlet, options) =>
            nominate({
              kind: "transcript",
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
          news: (key, outlet) =>
            nominate({ kind: "news", key, message: null, outlet, options: {} }),
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
      reactions: message.reactions,
      workflows: message.workflows,
    });
  };
  /** @param {number} current @param {() => void} drawn */
  async function paint(current, drawn) {
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
    /** @type {Map<Element, Element[]>} */
    const children = new Map();
    /** @param {Element} parent @param {Element} node */
    const place = (parent, node) => {
      const nodes = children.get(parent) ?? [];
      nodes.push(node);
      children.set(parent, nodes);
    };
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
        } else if (item.kind === "news") {
          const notice = newsNotice();
          view = { kind: "news", node: notice.node, notice, dispose() {} };
        } else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          generatedElement(node, { says: false });
          node.dataset.lfOffer = "";
          const notice = newsNotice();
          notice.node.classList.add("lf-primary-news");
          if (item.kind === "transcript") {
            // A press on a reply's reactions is the user acting in this thread, so
            // what the reader holds of it shows with it, as in a card (thread-card.js).
            const transcript = new Transcript({
              commands,
              messageCommands: {
                ...commands,
                reaction: {
                  ...commands.reaction,
                  pressed: () => shown.get(item.key)?.news?.open(),
                },
                edit: rewritesOf(item.key).edit,
              },
              repaint: () => part.draw(),
              home: () => node,
            });
            node.append(transcript.node);
            node.dataset.lfAppendTail = "";
            /** @type {TranscriptPart} */
            const part = {
              kind: "transcript",
              node,
              notice,
              transcript,
              reading,
              drawn: false,
              // Whether the thread's notice stands in its first message's head.
              headNotice: true,
              // Draws the transcript again at once, as a fold or a rewrite opens or
              // closes; a disclosure the draw replaced hands focus to its successor.
              draw() {
                const handedOn = transcript.present(this.reading, {
                  arrived: this.drawn,
                  notice: this.headNotice ? this.notice.node : null,
                });
                transcript.commit(this.reading);
                this.drawn = true;
                if (handedOn) focusDestination(handedOn, "return");
              },
              dispose: () => transcript.retire(),
            };
            view = part;
          } else if (item.kind === "message") {
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
              // Whether the thread's notice stands in this message's head.
              headNotice: true,
              // Draws the message again at once, as its rewrite opens or closes.
              draw() {
                message.present(this.reading, {
                  ...(this.headNotice ? { headerControls: this.notice.node } : {}),
                });
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
      if (view.kind === "thread") {
        view.present(reading);
        view.commit();
      } else if (view.kind === "news") {
        const news = shown.get(item.key)?.news;
        if (news) view.notice.set(news);
        keepsHidden(view.node, !news);
      } else {
        keeps(view.node, "data-thread", item.thread.id);
        keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
        const news = shown.get(item.key)?.news;
        const nominated = selected.some(
          (part) => part.key === item.key && part.kind === "news",
        );
        const first =
          selected.find(
            (part) =>
              part.key === item.key &&
              (part.kind === "message" || part.kind === "transcript"),
          ) ?? selected.find((part) => part.key === item.key);
        const notice = Boolean(news) && !nominated && first === item;
        if (notice && news) view.notice.set(news);
        keepsHidden(view.notice.node, !notice);
        if (view.kind === "transcript") {
          view.headNotice = !nominated;
          view.reading = reading;
          view.draw();
        } else if (view.kind === "message") {
          const message = messageSource(item.thread, view.messageKey);
          view.headNotice = !nominated;
          view.reading = messageModel(item.thread, view.messageKey);
          view.draw();
          // A reply still streaming at the thread's end grows at its foot as its words
          // come, as in a thread card (thread-card.js, shift_watch.js).
          keeps(
            view.node,
            "data-lf-append-tail",
            message.provisional && message === item.thread.msgs.at(-1) ? "" : null,
          );
        } else {
          if (nominated) view.notice.node.remove();
          else if (view.notice.node.parentNode !== view.node)
            move(view.node, view.notice.node, null);
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
      // The notice is no part of the thread that a reading or a landing stands on.
      if (view.kind === "news") continue;
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
    // A reply part standing in the document takes the row being written in its thread
    // that no view holds (replies.js, `claim`).
    for (const view of views.values())
      if (view.kind === "reply")
        view.reply.claim(() => view.node.isConnected && !view.node.hidden);
    // The transcript is now on screen: it becomes the held-news baseline and its
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
        const node = view.node.querySelector(`.lf-msg[data-event="${CSS.escape(id)}"]`);
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
      [...views.values()].some((view) => under(node, view.node)) ||
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
