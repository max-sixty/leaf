/* Exact widget-local placement for canonical Thread conversations.

   A placement claims one Thread's page position, so reconciliation joins the core
   Thread presentation before the margin chooses its fallback. Ordinary mirrors live
   in mirrors.js and cannot hold that presentation open.

   A thread the widget would draw in a seat it has not opened yet, while that would move
   what the reader reads, is held out of what the widget is handed (`HeldArrivals`,
   held-news.js): `target` answers null for it, so the margin draws it, and `showHeld`
   is how the margin's marker shows it. */
import { reportPageError } from "../layer-client.js";
import { datumAimTarget, resolveAnchor } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { pageText } from "../passages.js";
import { registry } from "../registry.js";
import { renderThreadSurface, clearThreadSurface } from "./inline.js";
import { readThreads } from "./state.js";
import { focusThread } from "./focus.js";
import { HeldArrivals } from "./held-news.js";
import { SAY_BOX } from "./selectors.js";
import { under } from "../shadow.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { retainUserIntent } from "../user-intent.js";

const registrations = new Map();
let claimedIds = new Set();
let renderGeneration = 0;

function update(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}

export function consumeThreads(owner, render, { invalidate, composition, reveal }) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeThreads needs an Element owner");
  requireSurface(owner);
  if (typeof render !== "function")
    throw new TypeError("consumeThreads needs a render callback");
  if (typeof invalidate !== "function")
    throw new TypeError("consumeThreads needs an invalidation function");
  if (
    !composition ||
    typeof composition.open !== "function" ||
    typeof composition.active !== "function" ||
    typeof composition.node !== "function" ||
    typeof composition.seat !== "function" ||
    typeof composition.restore !== "function" ||
    typeof composition.outlet !== "function"
  )
    throw new TypeError("consumeThreads needs composition presentation");
  if (registrations.has(owner))
    throw new Error(`consumeThreads(${owner.localName}) registered twice`);
  const registration = {
    render,
    owner,
    invalidate,
    composition,
    outlets: new Set(),
    // The datums where the widget drew a thread last, and the threads it holds out of
    // the seats it has not opened.
    drawn: new Set(),
    held: new HeldArrivals(() => update(registration)),
    reconcileQueued: false,
    cancelRender: () => {},
  };
  registrations.set(owner, registration);
  update(registration);
  let active = true;
  return {
    read: readThreads,
    reveal(key) {
      if (!active) return false;
      const thread = readThreads().threads.find((item) => item.key === key);
      return thread ? reveal(thread.id) : false;
    },
    open(datum, { origin = null } = {}) {
      if (!active) return false;
      requireSurface(owner);
      const target = datumAimTarget(datum);
      if (
        !target ||
        target.anchor.section !== owner.id ||
        !under(target.element, owner)
      )
        throw new TypeError(
          `consumeThreads(${owner.localName}) can open only its own projected datum`,
        );
      composition.open(target, { origin });
      return true;
    },
    update: () => update(registration),
    unregister() {
      if (!active) return;
      active = false;
      registrations.delete(owner);
      clearRegistration(registration);
      update(registration);
    },
  };
}

function requireSurface(owner) {
  if (registry[owner.localName]?.["x-thread-surface"] !== true)
    throw new Error(
      `consumeThreads(${owner.localName}) requires x-thread-surface: true to place Threads`,
    );
}

function clearOutlets(outlets) {
  for (const outlet of outlets) {
    clearThreadSurface(outlet);
    delete outlet.dataset.lfThreadSurface;
  }
}

function reportFailure({ owner }, error) {
  reportPageError(
    `thread surface ${owner.localName}#${owner.id} failed: ${error?.message ?? error}`,
  );
}

function clearRegistration(registration) {
  registration.cancelRender();
  registration.held.dispose();
  registration.drawn = new Set();
  if (registration.outlets.has(registration.composition.outlet()))
    registration.composition.restore();
  clearOutlets(registration.outlets);
  registration.outlets.clear();
}

export function renderSurfaces(collection, placedAt, commands) {
  const generation = ++renderGeneration;
  const current = () => generation === renderGeneration;
  for (const registration of registrations.values()) registration.cancelRender();
  const cancel = () => {
    if (!current()) return;
    ++renderGeneration;
    for (const registration of registrations.values()) registration.cancelRender();
  };
  const completion = render();
  return { completion, cancel };

  async function render() {
    const nextClaimed = new Set();
    const activeComposition = commands.composition.active();
    let compositionSeated = false;
    for (const registration of [...registrations.values()]) {
      const { render, owner } = registration;
      if (registrations.get(owner) !== registration) continue;
      if (!owner.isConnected) {
        registrations.delete(owner);
        clearRegistration(registration);
        continue;
      }
      const byOutlet = new Map();
      const abort = new AbortController();
      let cancel;
      const cancelled = new Promise((resolve) => {
        cancel = resolve;
      });
      registration.cancelRender = () => {
        abort.abort();
        cancel();
      };
      let compositionOutlet = null;
      let compositionPrepared = false;
      try {
        const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
        const exact = (anchor, placement) =>
          anchor?.datum &&
          anchor.section === owner.id &&
          placement?.status === "exact" &&
          placement.datumElement instanceof Element &&
          under(placement.datumElement, owner);
        const targets = new Map();
        for (const thread of collection.threads) {
          if (thread.anchor?.section !== owner.id) continue;
          const placement = placedAt(thread.id);
          if (exact(thread.anchor, placement))
            targets.set(thread.key, { anchor: thread.anchor, placement });
        }
        const held = registration.held.hold(
          [...targets].map(([key, { anchor, placement }]) => ({
            thread: byKey.get(key),
            datum: anchor.datum,
            node: placement.datumElement,
          })),
          { drawn: registration.drawn, all: collection.threads },
        );
        const target = (key) => (held.has(key) ? null : (targets.get(key) ?? null));
        const anchor = activeComposition?.anchor;
        const placement =
          anchor?.datum && anchor.section === owner.id
            ? resolveAnchor(anchor, pageText())
            : null;
        const compositionTarget = exact(anchor, placement)
          ? { anchor, placement }
          : null;
        let placing = true;
        const acceptOutlet = (outlet) => {
          if (!placing || abort.signal.aborted)
            throw new Error("Thread outlets belong to their current render callback");
          if (!(outlet instanceof Element))
            throw new TypeError("A Thread outlet must be an Element");
        };
        const placeThread = (key, outlet) => {
          acceptOutlet(outlet);
          const thread = byKey.get(key);
          if (!thread) throw new Error(`No Thread has key ${key}`);
          const held = byOutlet.get(outlet) ?? [];
          if ([...byOutlet.values()].some((threads) => threads.includes(thread)))
            throw new Error("A consumer may place a Thread only once");
          held.push(thread);
          byOutlet.set(outlet, held);
        };
        try {
          const rendering = render(collection, {
            signal: abort.signal,
            target,
            composition: compositionTarget,
            place(key, outlet) {
              if (!target(key))
                throw new Error(
                  "A Thread outlet requires an exact target owned by its widget",
                );
              placeThread(key, outlet);
            },
            placeComposition(outlet) {
              acceptOutlet(outlet);
              if (!compositionTarget)
                throw new Error("The composer has no exact target in this widget");
              compositionOutlet = outlet;
              if (!byOutlet.has(outlet)) byOutlet.set(outlet, []);
            },
          });
          if (rendering?.then) await Promise.race([rendering, cancelled]);
        } finally {
          placing = false;
        }
        if (!current()) return claimedIds;
        if (registrations.get(owner) !== registration || !owner.isConnected) {
          clearRegistration(registration);
          continue;
        }
        for (const outlet of byOutlet.keys()) {
          if (!outlet.isConnected) {
            byOutlet.delete(outlet);
          } else if (!under(outlet, owner))
            throw new Error(
              `consumeThreads(${owner.localName}) returned an outlet outside its widget`,
            );
        }
        const text = byOutlet.size ? pageText() : null;
        for (const [outlet, threads] of byOutlet) {
          byOutlet.set(
            outlet,
            threads.filter((thread) =>
              exact(thread.anchor, resolveAnchor(thread.anchor, text)),
            ),
          );
        }
        if (
          compositionOutlet &&
          (!byOutlet.has(compositionOutlet) ||
            !exact(anchor, resolveAnchor(anchor, text)) ||
            !sameAnchor(commands.composition.active()?.anchor, anchor))
        )
          compositionOutlet = null;
        const currentCompositionOutlet = commands.composition.outlet();
        if (compositionOutlet)
          compositionPrepared = commands.composition.seat(compositionOutlet);
        else if (registration.outlets.has(currentCompositionOutlet))
          commands.composition.restore();
        if (compositionPrepared) compositionSeated = true;
      } catch (error) {
        if (!current()) return claimedIds;
        if (abort.signal.aborted) continue;
        if (
          registration.outlets.has(commands.composition.outlet()) ||
          compositionOutlet === commands.composition.outlet()
        )
          commands.composition.restore();
        clearOutlets(registration.outlets);
        registration.outlets.clear();
        reportFailure(registration, error);
        continue;
      }
      clearOutlets([...registration.outlets].filter((outlet) => !byOutlet.has(outlet)));
      registration.outlets = new Set(byOutlet.keys());
      registration.drawn = new Set(
        [...byOutlet.values()].flat().map((thread) => thread.anchor.datum),
      );
      for (const [outlet, threads] of byOutlet) {
        outlet.toggleAttribute("data-lf-thread-surface", true);
        const response =
          compositionPrepared && outlet === compositionOutlet
            ? commands.composition.node()
            : null;
        renderThreadSurface(outlet, threads, commands, response);
        for (const thread of threads) nextClaimed.add(thread.id);
      }
    }
    if (!compositionSeated) commands.composition.restore();
    claimedIds = nextClaimed;
    return claimedIds;
  }
}

export const claimed = (id) => claimedIds.has(id);

// Whether a widget holds the thread `id` out of its flow, so that its margin marker is
// the notice it waits behind.
export const heldOut = (id) =>
  [...registrations.values()].some(({ held }) => held.holds(id));

// Shows the threads `ids` names that a widget holds out of its flow, and lands on the
// first where its widget then draws it, since the marker the user pressed goes with
// what it held, unless a newer gesture has taken them elsewhere. Returns whether a
// widget held any.
export function showHeld(ids) {
  for (const registration of registrations.values()) {
    const [id] = registration.held.show(ids);
    if (id) {
      void presentHeld(registration, id, retainUserIntent());
      return true;
    }
  }
  return false;
}

async function presentHeld(registration, id, mayLand) {
  await registration.invalidate();
  await whenDocumentPresented();
  if (mayLand()) focusSurface(id, { focus: "thread" });
}

export function focusSurface(id, { focus = "reply" } = {}) {
  for (const registration of registrations.values()) {
    const thread = [...registration.outlets]
      .map((outlet) =>
        outlet.querySelector(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
      )
      .find(Boolean);
    if (!thread) continue;
    const summary = thread.querySelector(":scope > summary");
    const target =
      (focus === "thread" ? thread : null) ??
      (summary && !thread.hasAttribute("open") ? summary : null) ??
      thread.querySelector(SAY_BOX) ??
      summary ??
      thread;
    if (target === thread) focusThread(thread, { preventScroll: true });
    else target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest" });
    return target;
  }
  return null;
}
