/* Canonical Thread placement into exact widget seats and one page presentation.

   A placement claims one Thread's page position, so reconciliation joins the core
   Thread presentation. Both callbacks nominate exact candidates; widget seats
   that survive final validation claim first, then the selected page presentation.
   Source coverage and outlet containment are separate: an authored page rail can
   show a target elsewhere in the document.
   Ordinary mirrors live
   in mirrors.js and cannot hold that presentation open.

   A thread the widget would draw in a seat it has not opened yet, while that would move
   what the reader reads, is held out of what the widget is handed (`HeldArrivals`,
   held-news.js): `target` answers null for it, so the margin draws it, and `showHeld`
   is how the margin's marker shows it. */
import { reportPageError } from "../layer-client.js";
import { aimTargetAt, datumAimTarget } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { closestAcross } from "../passages.js";
import { registry } from "../registry.js";
import { renderThreadSurface, clearThreadSurface } from "./inline.js";
import { allThreads, readThreads } from "./state.js";
import { threadNames } from "./model.js";
import { threadFocusDestination } from "./focus.js";
import { HeldArrivals } from "./held-news.js";
import { under } from "../shadow.js";
import { declareSide } from "../standing-target.js";
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

export function consumeThreads(owner, render, options) {
  return register(owner, render, options, "widget");
}

// The selected page presentation joins the same outlet and generation lifetime.
// This owner nominates fallback candidates. Only the final cohort move knows which
// widget nominations survived, and gives those seats priority over page nominations.
export function consumePageThreads(owner, render, options) {
  if ([...registrations.values()].some((item) => item.kind === "page"))
    throw new Error("The document already has a page Thread presentation");
  return register(owner, render, options, "page");
}

function register(owner, render, { invalidate, composition, reveal }, kind) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeThreads needs an Element owner");
  if (kind === "widget") requireSurface(owner);
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
    kind,
    invalidate,
    composition,
    outlets: new Set(),
    placements: null,
    // The datums where the widget drew a thread last, and the threads it holds out of
    // the seats it has not opened.
    drawn: new Set(),
    held: kind === "widget" ? new HeldArrivals(() => update(registration)) : null,
    reconcileQueued: false,
    cancelRender: () => {},
  };
  // The outlet lifetime also owns its source standing. A page rail's card stands
  // at the source it shows, while its unrelated controls keep their authored place.
  // The standing reader gives an innermost reply Ask priority over this relation.
  registration.stopSide = declareSide((node) => {
    const outlet = [...registration.outlets].find((outlet) => under(node, outlet));
    if (!outlet) return null;
    const thread = closestAcross(node, ".lf-page-thread");
    if (thread && under(thread, outlet))
      return registration.placements?.placedAt(thread.dataset.thread)?.place ?? null;
    return outlet === composition.outlet()
      ? (registration.placements?.pendingAt()?.place ?? null)
      : null;
  });
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
    open(node, { origin = null } = {}) {
      if (!active) return false;
      if (kind === "widget") requireSurface(owner);
      const target = kind === "widget" ? datumAimTarget(node) : aimTargetAt(node);
      if (
        !target ||
        (kind === "widget" &&
          (target.anchor.section !== owner.id || !under(target.element, owner)))
      )
        throw new TypeError(
          kind === "widget"
            ? `consumeThreads(${owner.localName}) can open only its own projected datum`
            : "The page Thread presentation needs an addressable source target",
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
  registration.stopSide();
  registration.held?.dispose();
  registration.drawn = new Set();
  if (registration.outlets.has(registration.composition.outlet()))
    registration.composition.restore();
  clearOutlets(registration.outlets);
  registration.outlets.clear();
}

// A nomination remains a capability only while its output is connected inside its
// presentation owner. Preparation and final cohort admission share this one reading.
function validateOutlets({ owner }, byOutlet) {
  for (const outlet of byOutlet.keys()) {
    if (!outlet.isConnected) byOutlet.delete(outlet);
    else if (!under(outlet, owner))
      throw new Error(
        `consumeThreads(${owner.localName}) returned an outlet outside its presentation owner`,
      );
  }
}

// Initial callback admission and the final move read the same current directory.
// A widget owns its exact datum; the page can present any complete attachment place.
function exactTarget({ owner, kind }, anchor, placement) {
  return (
    placement?.status === "exact" &&
    (kind === "page"
      ? placement.place instanceof Element
      : anchor?.datum &&
        anchor.section === owner.id &&
        placement.datumElement instanceof Element &&
        under(placement.datumElement, owner))
  );
}

export function renderSurfaces(collection, placements, commands) {
  const generation = ++renderGeneration;
  const current = () => generation === renderGeneration;
  for (const registration of registrations.values()) registration.cancelRender();
  const cancel = () => {
    if (!current()) return;
    ++renderGeneration;
    for (const registration of registrations.values()) registration.cancelRender();
  };
  const activeComposition = commands.composition.active();
  let prepared = null;
  const completion = prepare().then((plans) => {
    prepared = plans;
  });
  return { completion, cancel, commit };

  // Callbacks nominate current contained outlets. They do not publish membership or
  // move the canonical editor before the required Thread cohort is ready to commit.
  async function prepare() {
    const plans = [];
    // Registration order cannot confer source ownership: the selected page owner
    // runs after the widgets establish their held-arrival admission in this pass.
    const ordered = [...registrations.values()].sort(
      (a, b) => (a.kind === "page") - (b.kind === "page"),
    );
    for (const registration of ordered) {
      const { render, owner } = registration;
      if (registrations.get(owner) !== registration) continue;
      if (!owner.isConnected) {
        registrations.delete(owner);
        clearRegistration(registration);
        continue;
      }
      registration.placements = placements;
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
      try {
        const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
        const targets = new Map();
        for (const thread of collection.threads) {
          if (
            registration.kind === "page"
              ? heldOut(thread.id)
              : thread.anchor?.section !== owner.id
          )
            continue;
          const placement = placements.placedAt(thread.id);
          if (exactTarget(registration, thread.anchor, placement))
            targets.set(thread.key, { anchor: thread.anchor, placement });
        }
        const held = registration.held?.hold(
          [...targets].map(([key, { anchor, placement }]) => ({
            thread: byKey.get(key),
            datum: anchor.datum,
            node: placement.datumElement,
          })),
          { drawn: registration.drawn, all: collection.threads },
        );
        const target = (key) => (held?.has(key) ? null : (targets.get(key) ?? null));
        const anchor = activeComposition?.anchor;
        const placement =
          anchor &&
          (registration.kind === "page" ||
            (anchor.datum && anchor.section === owner.id))
            ? placements.pendingAt()
            : null;
        const compositionTarget = exactTarget(registration, anchor, placement)
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
                  "A Thread outlet requires an exact target admitted to this presentation",
                );
              placeThread(key, outlet);
            },
            placeComposition(outlet) {
              acceptOutlet(outlet);
              if (!compositionTarget)
                throw new Error(
                  "The composer has no exact target in this presentation",
                );
              compositionOutlet = outlet;
              if (!byOutlet.has(outlet)) byOutlet.set(outlet, []);
            },
          });
          if (rendering?.then) await Promise.race([rendering, cancelled]);
        } finally {
          placing = false;
        }
        if (!current()) return null;
        if (registrations.get(owner) !== registration || !owner.isConnected) {
          clearRegistration(registration);
          continue;
        }
        validateOutlets(registration, byOutlet);
        if (
          compositionOutlet &&
          (!byOutlet.has(compositionOutlet) ||
            !sameAnchor(commands.composition.active()?.anchor, anchor))
        )
          compositionOutlet = null;
      } catch (error) {
        if (!current()) return null;
        if (abort.signal.aborted) continue;
        if (registration.kind === "page") throw error;
        // A failed widget can yield to the selected page phase. Clearing its prior
        // seats belongs to the same eventual commit as that fallback.
        plans.push({ registration, byOutlet: new Map(), compositionOutlet: null });
        reportFailure(registration, error);
        continue;
      }
      plans.push({ registration, byOutlet, compositionOutlet });
    }
    return current() ? plans : null;
  }

  function commit() {
    if (!current() || !prepared) return;
    const plans = prepared.filter(
      ({ registration }) =>
        registrations.get(registration.owner) === registration &&
        registration.owner.isConnected,
    );
    // Required preparation can yield after callback admission. The coordinator has
    // refreshed the target directory; read it and the outlets at the actual move.
    // Page candidates cover every exact target. Only surviving widget nominations
    // reserve a Thread or composer here; a failed page cannot certify the cohort.
    const widgetClaims = new Set();
    for (const plan of plans) {
      try {
        validateOutlets(plan.registration, plan.byOutlet);
        for (const [outlet, threads] of plan.byOutlet)
          plan.byOutlet.set(
            outlet,
            threads.filter(
              (thread) =>
                exactTarget(
                  plan.registration,
                  thread.anchor,
                  placements.placedAt(thread.id),
                ) &&
                (plan.registration.kind === "widget" ||
                  (!widgetClaims.has(thread.id) && !heldOut(thread.id))),
            ),
          );
        if (
          !plan.byOutlet.has(plan.compositionOutlet) ||
          !exactTarget(
            plan.registration,
            activeComposition?.anchor,
            placements.pendingAt(),
          )
        )
          plan.compositionOutlet = null;
      } catch (error) {
        if (plan.registration.kind === "page") throw error;
        reportFailure(plan.registration, error);
        plan.byOutlet.clear();
        plan.compositionOutlet = null;
      }
      if (plan.registration.kind === "widget") {
        for (const threads of plan.byOutlet.values())
          for (const thread of threads) widgetClaims.add(thread.id);
      }
    }
    const previousComposition = commands.composition.outlet();
    let movedComposition = false;
    try {
      // Preparation may have awaited a package while the user chose another target.
      // Only the still-current composition can move to the nominated outlet.
      if (
        sameAnchor(activeComposition?.anchor, commands.composition.active()?.anchor)
      ) {
        movedComposition = true;
        // Only an admitted native editor seat reserves composition. Folded Thread
        // outlets remain valid materialization, while an unavailable typing place
        // yields to the surviving page nomination or the actual composition home.
        const seated = plans.some(
          ({ compositionOutlet }) =>
            compositionOutlet && commands.composition.seat(compositionOutlet),
        );
        if (!seated) commands.composition.restore();
      }
      const nextClaimed = new Set();
      for (const { registration, byOutlet } of plans) {
        for (const outlet of registration.outlets)
          if (!byOutlet.has(outlet)) clearThreadSurface(outlet);
        for (const [outlet, threads] of byOutlet) {
          const response =
            outlet === commands.composition.outlet()
              ? commands.composition.node()
              : null;
          renderThreadSurface(outlet, threads, commands, response);
          for (const thread of threads) nextClaimed.add(thread.id);
        }
      }
      // Commit mechanical ownership after all fallible seat preparation. If a required
      // sibling failed, this function was never called and ThreadSeat retention still
      // agrees with the old outlet membership and native surface flags.
      for (const { registration, byOutlet } of plans) {
        for (const outlet of registration.outlets)
          if (!byOutlet.has(outlet)) delete outlet.dataset.lfThreadSurface;
        for (const outlet of byOutlet.keys())
          outlet.toggleAttribute("data-lf-thread-surface", true);
        registration.outlets = new Set(byOutlet.keys());
        registration.drawn = new Set(
          [...byOutlet.values()].flat().map((thread) => thread.anchor.datum),
        );
      }
      claimedIds = nextClaimed;
      prepared = null;
    } catch (error) {
      // ThreadSeat retention restores the conversations. Composition owns its own
      // native editor, so return it through the same seat/restore producer first.
      if (movedComposition) {
        if (
          !previousComposition?.isConnected ||
          !commands.composition.seat(previousComposition)
        )
          commands.composition.restore();
      }
      throw error;
    }
  }
}

export const claimed = (id) => claimedIds.has(id);

// Whether a widget holds the thread `id` out of its flow, so that its margin marker is
// the notice it waits behind.
export const heldOut = (id) =>
  [...registrations.values()].some(({ held }) => held?.holds(id));

// Shows the threads `ids` names that a widget holds out of its flow, and lands on the
// first where its widget then draws it, since the marker the user pressed goes with
// what it held, unless a newer gesture has taken them elsewhere. Returns whether a
// widget held any.
export function showHeld(ids) {
  for (const registration of registrations.values()) {
    const [id] = registration.held?.show(ids) ?? [];
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

// Resolve after reveal/presentation: a datum's outlet may have been replaced. Travel
// takes the node rather than a callback that privately focuses and scrolls it.
export function surfaceFocusTarget(id, { focus = "reply" } = {}) {
  // Exact message navigation is the panel's; a local surface lands on its thread.
  if (focus === "message") return null;
  id = threadNames(allThreads()).get(id)?.id ?? id;
  for (const registration of registrations.values()) {
    const thread = [...registration.outlets]
      .map((outlet) =>
        outlet.querySelector(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
      )
      .find(Boolean);
    if (!thread) continue;
    return threadFocusDestination(thread, { focus });
  }
  return null;
}

// A surface can also be entered in place, without a page trip (a press on its words).
// That mechanical focus move shares the same target reading as travel.
export function focusSurface(id, options) {
  const target = surfaceFocusTarget(id, options);
  if (!target) return null;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "nearest" });
  return target;
}
