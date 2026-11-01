/* Synchronous thread seats outside the panel. Each seat owns its host's children: its
   retained open thread cards in order, its Resolved disclosure, then its response row.
   Descriptors contain values; native first-message and response editors remain
   explicit capabilities.

   A seat in the page's flow gathers its resolved threads under one Resolved
   disclosure after its open ones, closed until the reader opens it, so however many
   conversations a datum has settled they take one row. Inside it each thread draws as
   any page thread does, its Reopen where Resolve stands, and keeps its reply box, whose
   send reopens it. A thread that resolves while the user writes a reply in it stays
   among the open ones until they finish, and one they write in inside the disclosure
   stays there, so the box they type in never moves out from under them. The disclosure
   is where its threads' held news waits (held-news.js), and opening it shows that.
   Rejected: folding each resolved thread to a summary of its own, which repeated
   "Resolved" once per thread and named none of them.

   A newly resolved card gives its old room back through foldBlock before moving into
   the disclosure. Its semantic placement and focus change at once; its outgoing pixels
   are inert. Opening the disclosure, undo or refusal ends that fold immediately. HeldNews
   still decides when a passive settlement may move the reader. */
import { setChildren } from "../dom-children.js";
import { generatedElement } from "../widget-elements.js";
import { html, render } from "/runtime/framework.js";
import { seatRoot, threadKey } from "./model.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { holdFocus, focused, focusDestination, currentLocationIn } from "../focus.js";
import { registry } from "../registry.js";
import { loadDraft } from "../drafts.js";
import { holdBox } from "./reply-landing.js";
import { leafSays, voiced } from "../voice.js";
import { HeldNews, newsCount, seatNotice } from "./held-news.js";
import { releaseReplies, replyIsEditing } from "./replies.js";
import { passOn } from "../user-intent.js";
import { foldBlock } from "../motion.js";

/** @typedef {import("./thread-card.js").ThreadCommands} ThreadCommands */
/** @typedef {import("./thread-card.js").ThreadRecord} ThreadRecord */
/** @typedef {import("./thread-card.js").ThreadReading} ThreadReading */
/** @typedef {import("./thread-card.js").ThreadViewModel} ThreadViewModel */
/** @typedef {import("./thread-card.js").MarginControls} MarginControls */
/** @typedef {{threads: readonly ThreadReading[], response: boolean, surface?: string, news?: null}} SeatReading */
/** @typedef {{threads: readonly ThreadViewModel[], response: boolean, surface?: string,
 * news?: import("./held-news.js").NewsNotice | null}} SeatShowing */
/** @typedef {{seats: Map<ThreadSeat, ReturnType<typeof holdFocus>>}} SeatBatch */
/** @typedef {{node: HTMLDivElement, view: ThreadView, played: ReturnType<typeof foldBlock>}} SeatFold */
/** @type {WeakMap<Element, ThreadSeat>} */
const seats = new WeakMap();
/** @type {Set<ThreadSeat>} */
const activeSeats = new Set();
const EMPTY = Object.freeze({ threads: Object.freeze([]), response: false });
/** @type {SeatBatch | null} */
let activeBatch = null;

class ResolvedThreads {
  node = document.createElement("details");
  summary = document.createElement("summary");
  /** @type {readonly ThreadViewModel[]} */
  #threads = [];

  /** @param {() => void} opened */
  constructor(opened) {
    this.node.className = "lf-resolved-threads lf-ui";
    this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
    generatedElement(this.node, { says: false });
    this.node.dataset.lfOffer = "";
    this.summary.className = "lf-resolved-summary lf-disclosure-marker";
    // Native disclosure opens at the attribute checkpoint, before paint, so the first
    // opened body already holds what its threads held back.
    new MutationObserver(() => {
      if (this.node.open) {
        opened();
        for (const thread of this.#threads) thread.news?.open();
      }
    }).observe(this.node, { attributeFilter: ["open"] });
  }

  // The summary says what its threads hold back as one count, as every notice of held
  // news does (held-news.js, `newsCount`), its title each fact. The news is Leaf's, as
  // a held-news notice's is, so it wears Leaf's voice.
  /** @param {readonly ThreadViewModel[]} threads @param {readonly Node[]} nodes */
  present(threads, nodes) {
    this.#threads = threads;
    const held = threads.flatMap(({ news }) => (news ? [news] : []));
    const total = held.reduce((sum, news) => sum + news.total, 0);
    const notice = total ? newsCount(total) : null;
    render(
      html`Resolved ·
      ${threads.length}${
        notice
          ? html` ·
              <span data-lf-news title=${held.map(({ label }) => label).join(" · ")}
                >${voiced(leafSays(notice))}</span
              >`
          : ""
      }`,
      this.summary,
    );
    setChildren(this.node, [this.summary, ...nodes]);
  }
}

class ThreadSeat {
  /** @type {Map<string, ThreadView>} */
  #views = new Map();
  /** @type {ResolvedThreads | null} */
  #resolved = null;
  /** @type {Map<string, SeatFold>} */
  #folding = new Map();
  #settled = new Set();
  #place = () => {};
  /** @type {SeatReading} */
  #model = EMPTY;
  /** @type {SeatShowing} */
  #shown = EMPTY;
  /** @type {SeatReading} */
  #committed = EMPTY;
  // A seat holds back news that would move what the reader reads, and says so in place
  // of its first-message row while it draws no thread (held-news.js). The margin's
  // floating card is a seat too, so it holds news as a seat in the page's flow does.
  /** @type {HeldNews | null} */
  #held = null;
  /** @type {ReturnType<typeof seatNotice> | null} */
  #notice = null;
  #commands;
  /** @type {() => HTMLElement | null} */
  #response = () => null;
  #connected = false;
  /** @type {MarginControls | null} */
  #marginControls = null;

  /** @param {Element} node @param {ThreadCommands} commands */
  constructor(node, commands) {
    this.node = node;
    this.#commands = commands;
  }
  /** @param {() => HTMLElement | null} response @param {MarginControls | null} marginControls */
  configure(response, marginControls = null) {
    this.#response = response;
    this.#marginControls = marginControls;
  }

  /** @param {SeatReading} model @param {SeatBatch | null} [batch] */
  present(model, batch = activeBatch) {
    // A refused batch hands the user back their previous location when the seat joined
    // it (`retainThreadSeats`); this render hands them their place across itself.
    if (batch && !batch.seats.has(this)) batch.seats.set(this, holdFocus(this.node));
    const restoreFocus = holdFocus(this.node);
    const currentLocation = focused();
    const restoreBox = this.node.contains(currentLocation)
      ? holdBox(currentLocation)
      : () => {};
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
    // A reading with no surface, a first-message box drawn before its seat's threads,
    // is no baseline for news.
    if (model.surface)
      this.#held ??= new HeldNews(
        this.node,
        (key) => this.#views.get(key) ?? null,
        () => this.present(this.#model),
      );
    const prior = this.#shown;
    // The first-message row the seat drew, which a thread arriving in a seat that gives
    // its box up takes out of the reading even while the seat holds that thread.
    const box = model.surface === "page" ? this.#response() : null;
    const row = !!box && prior.response && !box.contains(currentLocation);
    const shown = this.#held ? this.#held.hold(model, { row }) : model;
    let foot = shown.response ? this.#response() : null;
    if (shown.news) {
      this.#notice ??= seatNotice();
      this.#notice.set(shown.news, box);
      foot = this.#notice.node;
    }
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
      view.setMarginControls(this.#marginControls);
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
      /** @type {Node[]} */
      const nodes = drawn.flatMap(({ descriptor: thread, view }) =>
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
    // Where settling would draw each card: a resolved thread that reopens takes its place
    // among the open ones, before the next of them or the disclosure; an open one that
    // resolves joins the disclosure.
    const fold = this.#resolved;
    const joins = () => (fold?.node.open ? fold.node : null);
    /** @type {Element | null} */
    let next = fold?.node ?? null;
    for (const { descriptor, view } of drawn.toReversed()) {
      if (!settled.includes(descriptor)) {
        view.setSettlesAt(joins);
        next = view.node;
      } else {
        const before = next;
        view.setSettlesAt(() => before);
      }
    }
    this.claim();
    // The seat's own box gives way to the thread its message started, and the user is
    // on that thread, where any send leaves them (`landSent`). Threads the seat held back
    // show with the user's, which is their current location. A disclosure the user was
    // on that went, as its last thread reopened, hands them to that thread.
    const own = added.filter(({ messages }) => messages[0]?.author === "user");
    const start = own.length === 1 ? own[0] : added.length === 1 ? added[0] : null;
    const started = drawn.find(({ descriptor }) => descriptor === start)?.view.node;
    restoreFocus?.(
      started && (() => this.#commands?.reply.landSent(started)),
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
    restoreBox();
    if (!batch) this.commit();
    return drawn;
  }

  /** @param {string} key @param {SeatFold} fold */
  #stopFold(key, { node, played }) {
    this.#folding.delete(key);
    node.inert = false;
    played?.cancel();
  }

  // Each thread the seat shows takes the reply being written in it where no view holds
  // it (replies.js, `claim`), once the seat stands in the document, so the move keeps the
  // user in the editor. A seat drawn before it is placed, as the margin card's is, claims
  // once its owner places it (`claimSeatReplies`).
  claim() {
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
  /** @param {ReturnType<typeof holdFocus>} restoreFocus */
  retain(restoreFocus) {
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

/** @param {Element} host @param {ThreadCommands} commands
 * @param {() => HTMLElement | null} response @param {MarginControls | null} marginControls */
function seatFor(host, commands, response = () => null, marginControls = null) {
  let seat = seats.get(host);
  if (!seat) {
    seat = new ThreadSeat(host, commands);
    seats.set(host, seat);
    activeSeats.add(seat);
  }
  seat.configure(response, marginControls);
  return seat;
}
/** @param {readonly ThreadRecord[]} threads @param {string} surface
 * @param {ThreadCommands} commands @param {unknown} response @returns {SeatReading} */
function seatReading(threads, surface, commands, response) {
  return Object.freeze({
    threads: Object.freeze(
      threads.map((thread) => threadReading(thread, surface, commands)),
    ),
    surface,
    response: Boolean(response),
  });
}

/** @param {Element} host @param {readonly ThreadRecord[]} threads
 * @param {ThreadCommands & {composition: {outlet: () => Element | null, node: () => HTMLElement}}} commands
 * @param {unknown} response */
export function renderThreadSurface(host, threads, commands, response = null) {
  const editor = () =>
    commands.composition.outlet() === host ? commands.composition.node() : null;
  seatFor(host, commands, editor).present(
    seatReading(threads, "outlet", commands, response),
  );
}

/** @param {Element} host */
export const claimSeatReplies = (host) => seats.get(host)?.claim();

/** @param {Element} host */
export function clearThreadSurface(host) {
  seats.get(host)?.present(EMPTY);
}

/** @param {HTMLElement} host @param {HTMLElement} editor */
export function mountFirstMessage(host, editor) {
  setChildren(host, [editor]);
}

/** @param {readonly ThreadRecord[]} threads @param {ThreadCommands} commands */
export function renderSeats(threads, commands) {
  /** @type {NodeListOf<HTMLElement & {lfThreadSeatOwner: Element}>} */
  const hosts = document.querySelectorAll(".lf-thread-seat[data-lf-thread-seat]");
  for (const host of hosts) {
    const owner = host.lfThreadSeatOwner;
    const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
    const hold = registry[owner.localName]?.["x-thread-seat"]?.hold;
    const response = !owned.length || hold || loadDraft("say:" + owner.id) !== null;
    seatFor(host, commands, () => host.lfFirstMessage ?? null).present(
      seatReading(owned, "page", commands, response),
    );
  }
}

/** @param {HTMLElement} host @param {ThreadRecord} thread @param {ThreadCommands} commands
 * @param {MarginControls | null} marginControls */
export function renderMarginThread(host, thread, commands, marginControls = null) {
  return seatFor(host, commands, () => null, marginControls)
    .present(seatReading([thread], "margin", commands, false))
    .filter(({ descriptor }) => descriptor.key === threadKey(thread))
    .map(({ view }) => ({ thread: view.node, transcript: view.transcript }));
}

export function beginThreadSeats() {
  activeBatch = { seats: new Map() };
  return activeBatch;
}
/** @param {SeatBatch} batch */
export function commitThreadSeats(batch) {
  if (activeBatch !== batch) return;
  for (const seat of batch.seats.keys()) seat.commit();
  activeBatch = null;
  for (const seat of activeSeats)
    if (seat.prune()) {
      activeSeats.delete(seat);
      seats.delete(seat.node);
    }
}
/** @param {SeatBatch} batch */
export function retainThreadSeats(batch) {
  if (activeBatch !== batch) return;
  for (const [seat, restoreFocus] of batch.seats) seat.retain(restoreFocus);
  activeBatch = null;
}
