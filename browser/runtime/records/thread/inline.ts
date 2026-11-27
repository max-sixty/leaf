/* Synchronous thread seats outside the panel. Each seat owns its host's children: its
   retained open thread cards in order, its Resolved disclosure, then its response row.
   Descriptors contain values; the native editor of a seat's response row remains an
   explicit capability.

   A seat in the page's flow gathers its resolved threads under one Resolved
   disclosure after its open ones, closed until the reader opens it, so however many
   conversations a datum has settled they take one row. The row names them, by count
   where there are several and each by its name (messages.js, `threadName`), so a reader
   can tell a datum's settled conversations apart without opening it, as a code review
   tool's folded conversation shows its opening. Inside it each thread draws as
   any page thread does, its Reopen where Resolve stands, and keeps its reply box, whose
   send reopens it. A thread that resolves while the user writes a reply in it stays
   among the open ones until they finish, and one they write in inside the disclosure
   stays there, so the box they type in never moves out from under them.
   Rejected: folding each resolved thread to a summary of its own, which repeated
   "Resolved" once per thread and named none of them.

   A newly resolved card gives its old room back through foldBlock before moving into
   the disclosure. Its semantic placement and focus change at once; its outgoing pixels
   are inert. Opening the disclosure, undo or refusal ends that fold immediately. HeldNews
   still decides when a passive settlement may move the reader. */
import { setChildren } from "../../dom/dom-children.js";
import { generatedElement } from "../../dom/widget-elements.js";
import { html, render } from "/vendor/lit.js";
import { threadKey } from "../../state/thread/model.js";
import { ThreadView, threadReading } from "./thread-card.js";
import {
  holdFocus,
  focused,
  focusDestination,
  currentLocationIn,
} from "../../dom/focus.js";
import { HeldNews } from "./held-news.js";
import { releaseReplies, replyIsEditing } from "./replies.js";
import { passOn } from "../../dom/user-intent.js";
import { foldBlock } from "../../dom/motion.js";
import type {
  ThreadCommands,
  ThreadReading,
  ThreadRecord,
  ThreadViewModel,
  ViewOutlets,
} from "./thread-card.js";
import type { ThreadChange } from "./held-news.js";
import type { BoxExtent } from "../../dom/scrolling.js";

type SeatReading = {
  threads: readonly ThreadReading[];
  response: boolean;
  surface?: string;
};
type SeatShowing = {
  threads: readonly ThreadViewModel[];
  response: boolean;
  surface?: string;
};
type SeatBatch = { seats: Map<ThreadSeat, ReturnType<typeof holdFocus>> };
type SeatFold = {
  node: HTMLDivElement;
  view: ThreadView;
  played: ReturnType<typeof foldBlock>;
};
const seats = new WeakMap<Element, ThreadSeat>();
const activeSeats = new Set<ThreadSeat>();
const EMPTY = Object.freeze({ threads: Object.freeze([]), response: false });
let activeBatch: SeatBatch | null = null;

class ResolvedThreads {
  node = document.createElement("details");
  summary = document.createElement("summary");

  constructor(opened: () => void) {
    this.node.className = "lf-resolved-threads lf-ui";
    this.node.dataset.lfRuntime = ""; // readings/passages.js, leafSurface
    generatedElement(this.node);
    this.node.dataset.lfOffer = "";
    this.summary.className = "lf-resolved-summary lf-disclosure-marker";
    // Native disclosure opens at the attribute checkpoint, before paint.
    new MutationObserver(() => {
      if (this.node.open) opened();
    }).observe(this.node, { attributeFilter: ["open"] });
  }

  present(threads: readonly ThreadViewModel[], nodes: readonly Node[]) {
    // A name that is a sentence keeps its words but not its full stop, which a list
    // of names would read as two marks in a row.
    const names = threads.map((thread) => thread.name.replace(/\.$/, "")).join(", ");
    const count = threads.length > 1 ? `${threads.length} · ` : "";
    render(html`Resolved · ${count}${names}`, this.summary);
    setChildren(this.node, [this.summary, ...nodes]);
  }
}

class ThreadSeat {
  declare node: Element;

  #views: Map<string, ThreadView> = new Map();
  #resolved: ResolvedThreads | null = null;
  #folding: Map<string, SeatFold> = new Map();
  #settled = new Set();
  #place = () => {};
  #model: SeatReading = EMPTY;
  #shown: SeatShowing = EMPTY;
  #committed: SeatReading = EMPTY;
  // A seat holds back news that would move what the reader reads (held-news.js). The
  // margin's floating card is a seat too, so it holds news as a seat in the page's flow
  // does. A thread in the flow that the user is in draws what its news adds at once,
  // as a chat does, since the reading that brings it keeps the control they are on
  // still by scrolling what stands above it up (readings/user-place.js, `holdUserPlace`). Its
  // settlement still waits behind its notice, since resolving or reopening moves the
  // thread between the seat's open threads and its Resolved disclosure, out from under
  // the user. The margin's card keeps its own rule for a user in it (thread-card.js,
  // `newsMoves`).
  #held: HeldNews | null = null;
  #commands;
  #response: () => HTMLElement | null = () => null;
  // Whether the seat has stood in the document, read at a commit or when its owner
  // places it (`claim`). A seat that stood there and left is pruned at the next commit;
  // one drawn but not yet placed is kept for its owner.
  #connected = false;
  // Where the margin's floating card stands its thread's parts (thread-card.js,
  // `ViewOutlets`); a seat in the page's flow gives none.
  #outlets: ViewOutlets = {};

  constructor(node: Element, commands: ThreadCommands) {
    this.node = node;
    this.#commands = commands;
  }
  configure(response: () => HTMLElement | null, outlets: ViewOutlets = {}) {
    this.#response = response;
    this.#outlets = outlets;
  }

  present(model: SeatReading, batch: SeatBatch | null = activeBatch) {
    // A refused batch hands the user back their previous location when the seat joined
    // it (`retainThreadSeats`); this render hands them their place across itself.
    if (batch && !batch.seats.has(this)) batch.seats.set(this, holdFocus(this.node));
    const restoreFocus = holdFocus(this.node);
    const stoodIn = [...this.#views.values()].find(({ node }) =>
      currentLocationIn(node),
    );
    const gathered =
      this.#resolved && currentLocationIn(this.#resolved.summary)
        ? [
            ...[...this.#resolved.node.children].slice(1),
            ...[...this.#folding.values()].map(({ node }) => node),
          ]
        : [];
    this.#model = model;
    // The reading that empties a seat names no surface, and is no baseline for news.
    if (model.surface)
      this.#held ??= new HeldNews(
        this.node,
        (key) => {
          const view = this.#views.get(key);
          if (!view || this.#model.surface === "margin") return view ?? null;
          return {
            node: view.node,
            newsMoves: (change: ThreadChange) =>
              (!currentLocationIn(view.node) || Boolean(change.news.settled)) &&
              view.newsMoves(change),
          };
        },
        () => this.present(this.#model),
      );
    const prior = this.#shown;
    const shown = this.#held ? this.#held.hold(model) : model;
    const foot = shown.response ? this.#response() : null;
    this.#shown = shown;
    const added = shown.threads.filter(
      (thread) => !prior.threads.some(({ key }) => key === thread.key),
    );
    const wanted = new Set(shown.threads.map((thread) => thread.key));
    // A thread leaving the seat releases the reply being written in it before its card
    // goes, so the editor goes on where the thread now stands (replies.js), still
    // listening if the user was dictating; the card retires only what stays with it.
    for (const [key, view] of this.#views)
      if (!wanted.has(key)) {
        releaseReplies(view.node);
        view.retire();
      }
    const settled = shown.threads.filter(
      (thread) =>
        thread.surface !== "margin" &&
        thread.resolved &&
        (!replyIsEditing(thread.key) || this.#settled.has(thread.key)),
    );
    this.#settled = new Set(settled.map(({ key }) => key));
    // The disclosure owns semantic placement immediately. Only the old room stays
    // outside it while folding, inert so no outgoing control remains actionable.
    if (!settled.length) this.#resolved = null;
    else
      this.#resolved ??= new ResolvedThreads(() => {
        if (!this.#folding.size) return;
        for (const [key, fold] of this.#folding) this.#stopFold(key, fold);
        this.present(this.#model);
      });
    for (const [key, fold] of this.#folding)
      if (!settled.some((thread) => thread.key === key) || this.#resolved?.node.open)
        this.#stopFold(key, fold);
    const resolved = this.#resolved;
    const departing = settled.filter((thread) => {
      const was = prior.threads.find(({ key }) => key === thread.key);
      return (
        was &&
        !was.resolved &&
        !resolved?.node.open &&
        this.#views.get(thread.key)?.node.parentElement === this.node
      );
    });
    const priorSize = departing.length ? this.node.getBoundingClientRect().height : 0;
    const drawn = shown.threads.map((descriptor) => {
      let view = this.#views.get(descriptor.key);
      if (!view)
        this.#views.set(
          descriptor.key,
          (view = new ThreadView(this.#commands, descriptor)),
        );
      const resolved = settled.includes(descriptor);
      view.setOutlets(this.#outlets);
      view.present(descriptor);
      view.setFoldedInto(
        resolved ? (this.#resolved?.node ?? null) : null,
        this.#folding.get(descriptor.key)?.played?.finished ?? null,
      );
      if (departing.includes(descriptor)) {
        view.node.inert = true;
        this.#folding.set(descriptor.key, { node: view.node, view, played: null });
      }
      return { descriptor, view };
    });
    const place = () => {
      const nodes: Node[] = drawn.flatMap(({ descriptor: thread, view }) =>
        !settled.includes(thread) || this.#folding.has(thread.key) ? [view.node] : [],
      );
      if (resolved) {
        resolved.present(
          settled,
          drawn
            .filter(
              ({ descriptor }) =>
                settled.includes(descriptor) && !this.#folding.has(descriptor.key),
            )
            .map(({ view }) => view.node),
        );
        nodes.push(resolved.node);
      }
      setChildren(this.node, foot ? [...nodes, foot] : nodes);
    };
    this.#place = place;
    place();
    let immediate = false;
    for (const [key, retirement] of this.#folding) {
      if (retirement.played) continue;
      const played = foldBlock(retirement.node, { container: this.node, priorSize });
      if (!played) {
        this.#folding.delete(key);
        retirement.node.inert = false;
        immediate = true;
        continue;
      }
      retirement.played = played;
      retirement.view.setFoldedInto(resolved?.node ?? null, played.finished);
      played.finished.then(
        () => {
          if (this.#folding.get(key) !== retirement) return;
          this.#folding.delete(key);
          // Only pixels finish here; the model and focus already reached their final
          // state. Place the retained nodes without repainting or taking a new reading
          // position from the outgoing card's temporarily restored intrinsic size.
          played.cancel();
          retirement.node.inert = false;
          this.#place();
        },
        () => {},
      );
    }
    if (immediate) place();
    const fold = this.#resolved;
    this.claim();
    // The seat's own box gives way to the thread its message started, and the user is
    // on that thread, where any send leaves them (`landSent`). A disclosure the user was
    // on that went, as its last thread reopened, hands them to that thread.
    const own = added.filter(({ messages }) => messages[0]?.author === "user");
    const start = own.length === 1 ? own[0] : added.length === 1 ? added[0] : null;
    const started = drawn.find(({ descriptor }) => descriptor === start)?.view.node;
    restoreFocus?.(
      started && (() => this.#commands.reply.landSent(started)),
      ...gathered,
    );
    // A thread the user was in that settling folded into the closed disclosure leaves
    // them on its summary, whether the move kept them on the hidden thread or dropped
    // them to the body, and the gesture's landing follows them there (`passOn`). One
    // reopened out of it keeps them, as its card hands their place across its own
    // render.
    const now = focused();
    const foldedThread =
      fold &&
      stoodIn &&
      (fold.node.contains(stoodIn.node) ||
        [...this.#folding.values()].some(({ node }) => node === stoodIn.node))
        ? stoodIn
        : null;
    if (
      fold &&
      foldedThread &&
      !fold.node.open &&
      (!now ||
        now === document.body ||
        currentLocationIn(foldedThread.node) ||
        (currentLocationIn(fold.node) && now !== fold.summary))
    ) {
      focusDestination(fold.summary, "return");
      passOn(foldedThread.node, fold.summary);
    }
    if (!batch) this.commit();
    return drawn;
  }

  #stopFold(key: string, { node, played }: SeatFold) {
    this.#folding.delete(key);
    node.inert = false;
    played?.cancel();
  }

  // Each thread the seat shows takes the reply being written in it where no view holds
  // it (replies.js, `claim`), once the seat stands in the document, so the move keeps the
  // user in the editor. A seat drawn before it is placed, as the margin card's is, claims
  // once its owner places it (`claimSeatReplies`).
  claim() {
    this.#connected ||= this.node.isConnected;
    const shown = () => this.node.isConnected;
    for (const [key, view] of this.#views)
      if (this.#shown.threads.some((thread) => thread.key === key))
        view.claimReply(shown);
  }

  commit() {
    this.#committed = this.#model;
    const wanted = new Set(this.#shown.threads.map((thread) => thread.key));
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#connected ||= this.node.isConnected;
  }
  retain(restoreFocus: ReturnType<typeof holdFocus>) {
    this.present(this.#committed);
    restoreFocus?.();
  }
  prune() {
    if (!this.#connected || this.node.isConnected) return false;
    this.#held?.dispose();
    for (const [key, fold] of this.#folding) this.#stopFold(key, fold);
    for (const view of this.#views.values()) view.dispose();
    this.#views.clear();
    return true;
  }
}

function seatFor(
  host: Element,
  commands: ThreadCommands,
  response: () => HTMLElement | null,
  outlets: ViewOutlets = {},
) {
  let seat = seats.get(host);
  if (!seat) {
    seat = new ThreadSeat(host, commands);
    seats.set(host, seat);
    activeSeats.add(seat);
  }
  seat.configure(response, outlets);
  return seat;
}
function seatReading(
  threads: readonly ThreadRecord[],
  surface: string,
  commands: ThreadCommands,
  response: unknown,
): SeatReading {
  return Object.freeze({
    threads: Object.freeze(
      threads.map((thread) => threadReading(thread, surface, commands)),
    ),
    surface,
    response: Boolean(response),
  });
}

export function renderThreadSurface(
  host: Element,
  threads: readonly ThreadRecord[],
  commands: ThreadCommands & {
    composition: { outlet: () => Element | null; node: () => HTMLElement };
  },
  response: unknown = null,
) {
  const editor = () =>
    commands.composition.outlet() === host ? commands.composition.node() : null;
  seatFor(host, commands, editor).present(
    seatReading(threads, "outlet", commands, response),
  );
}

export const claimSeatReplies = (host: Element) => seats.get(host)?.claim();

export function clearThreadSurface(host: Element) {
  seats.get(host)?.present(EMPTY);
}

export function renderMarginThread(
  host: HTMLElement,
  thread: ThreadRecord,
  commands: ThreadCommands,
  outlets: ViewOutlets,
) {
  return seatFor(host, commands, () => null, outlets)
    .present(seatReading([thread], "margin", commands, false))
    .filter(({ descriptor }) => descriptor.key === threadKey(thread))
    .map(({ view }) => ({
      transcript: view.transcript,
      settled: () => view.settled(),
      answering: () => view.answering,
      placesEnd: (before: BoxExtent) => view.placesEnd(before),
    }));
}

export function beginThreadSeats() {
  activeBatch = { seats: new Map() };
  return activeBatch;
}
export function commitThreadSeats(batch: SeatBatch) {
  if (activeBatch !== batch) return;
  for (const seat of batch.seats.keys()) seat.commit();
  activeBatch = null;
  for (const seat of activeSeats)
    if (seat.prune()) {
      activeSeats.delete(seat);
      seats.delete(seat.node);
    }
}
// A seat whose host has left the document, as a margin card's thread does once the
// card draws another, goes at once rather than at the next draw's prune
// (`commitThreadSeats`), so its drawings let go of what they held, a message's widgets
// among them, which the drawing standing in its place takes (messages.js,
// `authoredHolders`).
export function pruneThreadSeat(host: Element) {
  const seat = seats.get(host);
  if (!seat?.prune()) return;
  activeSeats.delete(seat);
  seats.delete(seat.node);
}
export function retainThreadSeats(batch: SeatBatch) {
  if (activeBatch !== batch) return;
  for (const [seat, restoreFocus] of batch.seats) seat.retain(restoreFocus);
  activeBatch = null;
}
