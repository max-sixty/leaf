/* Keyed synchronous Lit thread seats outside the panel. Descriptors contain
   values; native first-message and response editors remain explicit capabilities. */
import { render, repeat } from "../../vendor/browser-runtime.js";
import { seatRoot } from "./model.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { elementById } from "../passages.js";
import { focused } from "../keyboard/scopes.js";
import { holdFocus } from "../focus.js";
import { registry } from "../registry.js";
import { loadDraft } from "../drafts.js";
import { holdBox } from "./reply-landing.js";
import { HeldNews, seatNotice } from "./held-news.js";

const seats = new WeakMap();
const activeSeats = new Set();
const EMPTY = Object.freeze({ threads: Object.freeze([]), response: false });
let activeBatch = null;

class ThreadSeat {
  #views = new Map();
  #model = EMPTY;
  #shown = EMPTY;
  #committed = EMPTY;
  // A seat in the page's flow holds back news that would move what the reader reads, and
  // says so in place of its first-message row while it draws no thread (held-news.js).
  #held = null;
  #notice = null;
  #commands = null;
  #response = () => null;
  #connected = false;
  #marginControls = null;

  constructor(node) {
    this.node = node;
  }
  configure(commands, response, marginControls = null) {
    this.#commands ??= commands;
    this.#response = response;
    this.#marginControls = marginControls;
  }

  present(model, batch = activeBatch) {
    // A refused batch hands the user back the place they stood in when the seat joined
    // it (`retainThreadSeats`); this render hands them their place across itself.
    if (batch && !batch.seats.has(this)) batch.seats.set(this, holdFocus(this.node));
    const restoreFocus = holdFocus(this.node);
    const standing = focused();
    const restoreBox = this.node.contains(standing) ? holdBox(standing) : () => {};
    this.#model = model;
    if (model.surface === "page" || model.surface === "outlet")
      this.#held ??= new HeldNews(
        this.node,
        (key) => this.#views.get(key),
        () => this.present(this.#model),
      );
    const prior = this.#shown;
    // The first-message row the seat drew, which a thread arriving in a seat that gives
    // its box up takes out of the reading even while the seat holds that thread.
    const box = model.surface === "page" ? this.#response() : null;
    const row = Boolean(box) && prior.response && !box.contains(standing);
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
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    const nodes = shown.threads.map((descriptor) => {
      let view = this.#views.get(descriptor.key);
      if (!view)
        this.#views.set(
          descriptor.key,
          (view = new ThreadView(descriptor.surface, this.#commands)),
        );
      view.setMarginControls(this.#marginControls);
      view.present(descriptor);
      return { key: descriptor.key, node: view.node };
    });
    render(
      [
        repeat(
          nodes,
          (item) => item.key,
          (item) => item.node,
        ),
        foot,
      ],
      this.node,
    );
    // The seat's own box gives way to the thread its message started, and the user stands
    // on that thread, where any send leaves them (`landSent`). Threads the seat held back
    // show with the user's, which is the one they stand on.
    const own = added.filter(({ messages }) => messages[0]?.author === "user");
    const start = own.length === 1 ? own[0] : added.length === 1 ? added[0] : null;
    const started = start && this.#views.get(start.key).node;
    restoreFocus?.(started && (() => this.#commands?.reply.landSent(started)));
    restoreBox();
    if (!batch) this.commit();
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
  retain(restoreFocus) {
    this.present(this.#committed);
    restoreFocus?.();
  }
  prune() {
    if (!this.#connected || this.node.isConnected) return false;
    this.#held?.dispose();
    for (const view of this.#views.values()) view.dispose();
    this.#views.clear();
    return true;
  }
}

function seatFor(host, commands, response = () => null, marginControls = null) {
  let seat = seats.get(host);
  if (!seat) {
    seat = new ThreadSeat(host);
    seats.set(host, seat);
    activeSeats.add(seat);
  }
  seat.configure(commands, response, marginControls);
  return seat;
}
function seatReading(threads, surface, commands, response) {
  return Object.freeze({
    threads: Object.freeze(
      threads.map((thread) => threadReading(thread, surface, commands, {})),
    ),
    surface,
    response: Boolean(response),
  });
}

export function renderThreadSurface(host, threads, commands, response = null) {
  const editor = () =>
    commands.composition.outlet() === host ? commands.composition.node() : null;
  seatFor(host, commands, editor).present(
    seatReading(threads, "outlet", commands, response),
  );
}

export function clearThreadSurface(host) {
  seats.get(host)?.present(EMPTY);
}

// Package mirrors are independent of the core Thread batch. A slow package callback
// may hold its own view, but cannot hold the panel, margin, or read presentation.
export function renderThreadMirrors(host, threads, commands) {
  seatFor(host, commands).present(seatReading(threads, "outlet", commands, null), null);
}

export function clearThreadMirrors(host) {
  seats.get(host)?.present(EMPTY, null);
}

export function mountFirstMessage(host, editor) {
  const seat = seatFor(host, null, () => editor);
  seat.present(Object.freeze({ threads: Object.freeze([]), response: true }));
  seat.commit();
}

export function renderSeats(threads, commands) {
  for (const host of document.querySelectorAll(
    ".lf-thread-seat[data-lf-thread-seat]",
  )) {
    const owner = elementById(host.dataset.lfThreadSeat);
    const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
    const hold = registry[owner.localName]?.["x-thread-seat"]?.hold;
    const response = !owned.length || hold || loadDraft("say:" + owner.id) !== null;
    seatFor(host, commands, () => host.lfFirstMessage).present(
      seatReading(owned, "page", commands, response),
    );
  }
}

export function renderMarginThread(host, thread, commands, marginControls = null) {
  seatFor(host, commands, () => null, marginControls).present(
    seatReading([thread], "margin", commands, false),
  );
  return host.querySelector(":scope > .lf-page-thread");
}

export function beginThreadSeats() {
  activeBatch = { seats: new Map() };
  return activeBatch;
}
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
export function retainThreadSeats(batch) {
  if (activeBatch !== batch) return;
  for (const [seat, restoreFocus] of batch.seats) seat.retain(restoreFocus);
  activeBatch = null;
}
