/* Registry-declared widget-local placements for canonical Thread views.

   Registrations are the domain's durable extension points. Each public registration is
   supplied the application invalidation that owns its next semantic render; the module
   stores no application service or generic event channel. */
import { reportPageError } from "../layer-client.js";
import { datumAimTarget, resolveAnchor } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { containsAcross, pageText } from "../passages.js";
import { registry } from "../registry.js";
import { renderThreadSurface, clearThreadSurface } from "./inline.js";
import { readThreads } from "./state.js";
import { focusThread } from "./focus.js";

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
      return thread ? reveal(thread.root.id) : false;
    },
    open(datum, { origin = null } = {}) {
      if (!active) return false;
      requireSurface(owner);
      const target = datumAimTarget(datum);
      if (
        !target ||
        target.anchor.section !== owner.id ||
        !containsAcross(owner, target.element)
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
          containsAcross(owner, placement.datumElement);
        const target = (key) => {
          const thread = byKey.get(key);
          if (!thread) return null;
          const placement = placedAt(thread.root.id);
          return exact(thread.anchor, placement)
            ? { anchor: thread.anchor, placement }
            : null;
        };
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
            throw new Error(
              "Thread placements belong to their current render callback",
            );
          requireSurface(owner);
          if (!(outlet instanceof Element))
            throw new TypeError("A Thread outlet must be an Element");
        };
        try {
          const rendering = render(collection, {
            signal: abort.signal,
            target,
            composition: compositionTarget,
            place(key, outlet) {
              acceptOutlet(outlet);
              if (!target(key))
                throw new Error(
                  "A Thread outlet requires an exact target owned by its widget",
                );
              const held = byOutlet.get(outlet) ?? [];
              const thread = byKey.get(key);
              if ([...byOutlet.values()].some((items) => items.includes(thread)))
                throw new Error("A consumer may place a Thread only once");
              held.push(thread);
              byOutlet.set(outlet, held);
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
          if (!outlet.isConnected) byOutlet.delete(outlet);
          else if (!containsAcross(owner, outlet))
            throw new Error(
              `consumeThreads(${owner.localName}) returned an outlet outside its widget`,
            );
        }
        for (const [outlet, threads] of byOutlet) {
          byOutlet.set(
            outlet,
            threads.filter((thread) =>
              exact(thread.anchor, resolveAnchor(thread.anchor, pageText())),
            ),
          );
        }
        if (
          compositionOutlet &&
          (!byOutlet.has(compositionOutlet) ||
            !exact(anchor, resolveAnchor(anchor, pageText())) ||
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
      for (const [outlet, localThreads] of byOutlet) {
        outlet.dataset.lfThreadSurface = "";
        const response =
          compositionPrepared && outlet === compositionOutlet
            ? commands.composition.node()
            : null;
        renderThreadSurface(outlet, localThreads, commands, response);
        for (const thread of localThreads) nextClaimed.add(thread.root.id);
      }
    }
    if (!compositionSeated) commands.composition.restore();
    claimedIds = nextClaimed;
    return claimedIds;
  }
}

export const claimed = (id) => claimedIds.has(id);

export function focusSurface(id, { focus = "reply" } = {}) {
  for (const registration of registrations.values()) {
    const root = registration.owner.shadowRoot ?? registration.owner;
    const thread = root.querySelector(
      `.lf-conversation-thread[data-thread="${CSS.escape(id)}"]`,
    );
    if (!thread) continue;
    const summary = thread.querySelector(":scope > summary");
    const target =
      (focus === "thread" ? thread : null) ??
      (summary && !thread.hasAttribute("open") ? summary : null) ??
      thread.querySelector("textarea:not([disabled])") ??
      summary ??
      thread;
    if (target === thread) focusThread(thread, { preventScroll: true });
    else target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest" });
    return target;
  }
  return null;
}
