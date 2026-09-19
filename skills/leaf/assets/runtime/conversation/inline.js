/* Keyed synchronous Lit conversation seats outside the panel. Descriptors contain
   values; native first-message and response editors remain explicit capabilities. */
import { render, repeat } from "../../vendor/browser-runtime.js";
import { seatRoot } from "./model.js";
import { ThreadView, threadReading } from "./thread-card.js";
import { elementById } from "../passages.js";
import { focused } from "../keyboard/scopes.js";
import { focusDestination, readCaret } from "../focus.js";
import { registry } from "../registry.js";
import { loadDraft } from "../drafts.js";
import { runtime } from "../context.js";

const seats = new WeakMap();
const activeSeats = new Set();
const EMPTY = Object.freeze({ threads: Object.freeze([]), response: false });
let activeBatch = null;

class ConversationSeat {
  #views = new Map();
  #model = EMPTY;
  #committed = EMPTY;
  #commands = null;
  #response = () => null;
  #focus = null;
  #connected = false;

  constructor(node) {
    this.node = node;
  }
  configure(commands, response) {
    this.#commands ??= commands;
    this.#response = response;
  }

  present(model) {
    activeBatch?.seats.add(this);
    const standing = focused();
    const held = this.node.contains(standing);
    this.#focus ??= held ? { element: standing, caret: readCaret(standing) } : null;
    this.#model = model;
    const wanted = new Set(model.threads.map((thread) => thread.key));
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    const nodes = model.threads.map((descriptor) => {
      let view = this.#views.get(descriptor.key);
      if (!view)
        this.#views.set(
          descriptor.key,
          (view = new ThreadView(descriptor.surface, this.#commands)),
        );
      view.present(descriptor);
      return { key: descriptor.key, node: view.node };
    });
    const caret = held ? readCaret(standing) : null;
    render(
      [
        repeat(
          nodes,
          (item) => item.key,
          (item) => item.node,
        ),
        model.response ? this.#response() : null,
      ],
      this.node,
    );
    if (
      held &&
      standing.isConnected &&
      !this.node.contains(focused()) &&
      this.node.contains(standing)
    )
      focusDestination(standing, caret);
    if (!activeBatch) this.commit();
  }

  commit() {
    this.#committed = this.#model;
    const wanted = new Set(this.#model.threads.map((thread) => thread.key));
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#focus = null;
    this.#connected ||= this.node.isConnected;
  }
  retain() {
    this.present(this.#committed);
    if (this.#focus?.element.isConnected)
      focusDestination(this.#focus.element, this.#focus.caret);
    this.#focus = null;
  }
  prune() {
    if (!this.#connected || this.node.isConnected) return false;
    for (const view of this.#views.values()) view.dispose();
    this.#views.clear();
    return true;
  }
}

function seatFor(host, commands, response = () => null) {
  let seat = seats.get(host);
  if (!seat) {
    seat = new ConversationSeat(host);
    seats.set(host, seat);
    activeSeats.add(seat);
  }
  seat.configure(commands, response);
  return seat;
}
function seatReading(threads, surface, commands, response) {
  return Object.freeze({
    threads: Object.freeze(
      threads.map((thread) =>
        threadReading(thread, surface, commands, {
          interactions: runtime.activity?.interactions ?? [],
          revision: runtime.currentRevision,
        }),
      ),
    ),
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

export function mountFirstMessage(host, editor) {
  const seat = seatFor(host, null, () => editor);
  seat.present(Object.freeze({ threads: Object.freeze([]), response: true }));
  seat.commit();
}

export function renderConversations(threads, commands) {
  for (const host of document.querySelectorAll(
    ".lf-conversation[data-lf-conversation]",
  )) {
    const owner = elementById(host.dataset.lfConversation);
    const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
    const hold = registry[owner.localName]?.["x-conversation"]?.hold;
    const response = !owned.length || hold || loadDraft("say:" + owner.id) !== null;
    seatFor(host, commands, () => host.lfFirstMessage).present(
      seatReading(owned, "page", commands, response),
    );
  }
}

export function renderMarginThread(host, thread, commands) {
  seatFor(host, commands).present(seatReading([thread], "margin", commands, false));
  return host.querySelector(":scope > .lf-conversation-thread");
}

export function beginConversationSeats() {
  activeBatch = { seats: new Set() };
  return activeBatch;
}
export function commitConversationSeats(batch) {
  if (activeBatch !== batch) return;
  for (const seat of batch.seats) seat.commit();
  activeBatch = null;
  for (const seat of activeSeats)
    if (seat.prune()) {
      activeSeats.delete(seat);
      seats.delete(seat.node);
    }
}
export function retainConversationSeats(batch) {
  if (activeBatch !== batch) return;
  for (const seat of batch.seats) seat.retain();
  activeBatch = null;
}
