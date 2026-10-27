/* The page's primary reader of Thread conversations: the one presentation, a
   package's or the floating panel's, that draws each thread in outlets it names
   (application.js, `attachPresentation`). */
import { aborted } from "../abort.js";
import { randomId } from "../ids.js";
import { under, renderedUnder, shadowHost } from "../shadow.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { MessageView, messageReading } from "./messages.js";
import { Transcript } from "./transcript.js";
import { createReplyView, replyAvailable } from "./replies.js";
import { keeps, keepsHidden } from "../keeps.js";
import { generatedElement } from "../widget-elements.js";
import { focusDestination } from "../focus.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { elementById } from "../passages.js";
import { THREAD } from "./selectors.js";
import { threadPart, wholeThread } from "./selectors.js";
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
   panel's does. A message part offers the user's rewrite of it, and
   a reply part ↑ to the latest, as a thread card does, through the thread's one
   rewrite owner over the parts this reader draws (`threadRewrites`). Layout and
   disclosure belong to the caller, a transcript's folds aside. The thread's reply destination is its reply box as
   the parts stand: a reply part's, or the one the presentation drawing them declares
   (selectors.js, `threadPart`), as the floating panel declares its field. A reply part takes
   the presentation's words for its box and its own landing of a send (replies.js,
   `createReplyView`). The thread itself, where a walk or a notice lands the keyboard, is
   the drawing the presentation declares around the parts, as the panel's view is.
   The notice of what the reader holds back (held-news.js) stands where the
   presentation nominates it (`parts.news`), as the floating panel stands it among its
   view's controls, after the way back. Where it nominates none, the notice
   stands at the end of the first part's head, in room every such head keeps for it,
   so news arriving moves none of the head's words. */
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
        node: drawingOf(parts) ?? parts.at(-1).node,
        progressOpen: parts.some((part) => part.transcript?.progressOpen),
        // A presentation that makes room for the agent's answer to the user's last turn
        // itself (`answersAtOnce`) is handed it whatever it moves. A transcript moves
        // what a card's would (transcript.js, `newsMoves`).
        newsMoves: (held) =>
          !(answersAtOnce && held.answers) &&
          parts.some((part) =>
            part.transcript
              ? part.transcript.newsMoves(held)
              : (held.news.appended ||
                  held.news.settled ||
                  held.changed.has(part.messageKey) ||
                  held.folds.messages.includes(part.messageKey) ||
                  held.folds.summaries.length) &&
                growthIsSeen(part.node),
          ),
      };
    },
    () => void update().catch(() => {}),
  );
  let shown = new Map();
  // The thread as a whole where the presentation draws one around its parts, as the
  // floating panel's view is a drawing of the thread its messages are drawn in
  // (selectors.js, `wholeThread`): what a keyboard landing on the thread stands on.
  const drawingOf = (parts) => {
    const whole = wholeThread(parts[0].node);
    return whole === parts[0].node ? null : whole;
  };
  // Each thread's rewrites over the parts of it this reader draws (`threadRewrites`):
  // its messages in the thread's order, and its reply box.
  const rewrites = new Map();
  const partsOf = (key, kind) =>
    selected
      .filter((item) => item.key === key && item.kind === kind)
      .flatMap((item) => views.get(item.identity) ?? []);
  // The thread's reply box as the parts drawn stand, in a reply part or where the
  // presentation around them declares it.
  const replyOf = (key) => {
    for (const view of destinations.get(key) ?? []) {
      const input = !view.node.hidden && threadPart(view.node, "reply");
      if (input) return input;
    }
    return null;
  };
  const rewritesOf = (key) => {
    if (!rewrites.has(key))
      rewrites.set(
        key,
        threadRewrites({
          thread: () => key,
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
          send: (id, text, options) =>
            commands.reply.actions.edit(key, id, text, options),
          paint: (node) =>
            [...partsOf(key, "transcript"), ...partsOf(key, "message")]
              .find((view) => view.transcript || view.message.node === node)
              ?.draw(),
          box: () => replyOf(key),
          home: (node) => node.closest(THREAD),
          opening: (id) => {
            shown.get(key)?.news?.open();
            partsOf(key, "transcript")[0]?.transcript.expandAround(id);
          },
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
    const nominations = [];
    let accepting = true;
    const nominate = (kind, key, message, outlet, options = {}) => {
      if (!accepting || abort.signal.aborted)
        throw new Error("Thread nominations belong to their current render callback");
      const thread = byKey.get(key);
      if (!thread) throw new Error(`No Thread has key ${key}`);
      if (message !== null && !turns(thread).some((item) => item.key === message))
        throw new Error(`Thread ${key} has no turn ${message}`);
      const identity = JSON.stringify([kind, key, message]);
      // A whole thread draws every part of it, and a transcript every message.
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
      nominations.push({ identity, kind, key, message, outlet, thread, options });
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
            await paint(current);
          } catch (error) {
            failing ||= current === generation;
            throw error;
          }
          if (active && current === generation && !abort.signal.aborted) {
            candidate.commit();
            failed = false;
          }
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
          transcript: (key, outlet) => nominate("transcript", key, null, outlet),
          message: (key, id, outlet) => nominate("message", key, id, outlet),
          reply: (key, outlet, options) =>
            nominate("reply", key, null, outlet, options),
          news: (key, outlet) => nominate("news", key, null, outlet),
        }),
      );
      if (rendering?.then)
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
          view = new ThreadView({ ...commands, authoredRank: 3 });
        else if (item.kind === "news") {
          const notice = newsNotice();
          view = { node: notice.node, notice, dispose() {} };
        } else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          generatedElement(node, { says: false });
          node.dataset.lfOffer = "";
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
              repaint: () => view.draw(),
              home: () => node,
            });
            node.append(transcript.node);
            node.dataset.lfAppendTail = "";
            view = {
              node,
              transcript,
              reading: null,
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
                transcript.commit();
                this.drawn = true;
                if (handedOn) focusDestination(handedOn, "return");
              },
              dispose: () => transcript.retire(),
            };
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
            view = {
              node,
              message,
              messageKey: item.message,
              reading: null,
              // Whether the thread's notice stands in this message's head.
              headNotice: true,
              // Draws the message again at once, as its rewrite opens or closes.
              draw() {
                message.present(this.reading, {
                  headerControls: this.headNotice ? this.notice.node : undefined,
                });
                message.commit();
              },
              dispose: () => message.retire(),
            };
          } else {
            let joined = false;
            // What the box reads, when it holds its sends and how a send lands are the
            // presentation's (replies.js, `createReplyView`), given with its nomination.
            const { hint, hintLead, accessibleName, busy, sending, sent } =
              item.options;
            // The part draws whichever row the view holds: its own, or the session's
            // row it takes from a view that can draw the thread no more, the user
            // still in it (replies.js, `carry`).
            const redraw = () => {
              for (const row of node.querySelectorAll(":scope > .lf-thread-reply"))
                if (row !== reply.node) row.remove();
              move(node, reply.node, node.firstChild);
            };
            const reply = createReplyView(item.key, commands.reply, redraw, {
              onChange: () => {
                if (joined) void update().catch(() => {});
              },
              editLast: rewritesOf(item.key).editLast,
              hint,
              hintLead,
              accessibleName,
              busy,
              sending,
              sent,
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
      } else if (item.kind === "news") {
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
        if (notice) view.notice.set(news);
        keepsHidden(view.notice.node, !notice);
        if (item.kind === "transcript") {
          view.headNotice = !nominated;
          view.reading = shown.get(item.key);
          view.draw();
        } else if (item.kind === "message") {
          const message = item.thread.msgs.find((entry) => entry.key === item.message);
          view.headNotice = !nominated;
          view.reading = messageReading(message, {
            authoredRank: 3,
            reactions: message.reactions,
            workflows: message.workflows,
          });
          view.draw();
          // A reply still streaming at the thread's end grows at its foot as its words
          // come, as in a thread card (thread-card.js, shift_watch.js).
          keeps(
            view.node,
            "data-lf-append-tail",
            message.provisional && message === item.thread.msgs.at(-1) ? "" : null,
          );
        } else {
          keepsHidden(view.node, !replyAvailable(item.thread));
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
      if (item.kind === "news") continue;
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
    // A reply part standing in the document takes the row being written in its thread
    // that no view holds (replies.js, `claim`).
    for (const view of views.values())
      view.reply?.claim(() => view.node.isConnected && !view.node.hidden);
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
    ownsMessage: (message) => owner.isConnected && nativeMessages.has(message.id),
    ownsDestination: (node) =>
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
