/* Canonical Thread placement into exact widget seats and one page presentation.

   A widget whose tag declares `x-thread-surface` is a seat for as long as it stands
   upgraded: `watchThreadSurfaces` registers it once its module has defined it and
   retires it when it leaves, over the same arrival lifetime every element owner holds
   (`watchArrivals`, arrivals.js), so a move within one batch keeps it. The runtime asks
   the widget itself for outlets with
   `owner.threadOutlets(targets, {signal, collection, onCommit})`, and the widget
   reaches its registration through `threadSurface(owner)` to say its seats changed
   (`update()`) or to open a comment on one of its datums (`open(node)`). The selected page presentation registers explicitly
   (`placePageThreads`).

   A placement claims one Thread's page position, so reconciliation joins the core
   Thread presentation. Both callbacks return outlets for an admitted batch;
   widget seats that survive final validation claim first, then the selected page presentation.
   Source coverage and outlet containment are separate: an authored page rail can
   show a target elsewhere in the document.

   A thread the widget would draw in a seat it has not opened yet, while that would move
   what the reader reads, is held out of what the widget is handed (`HeldArrivals`,
   held-news.js): its target stays out of the batch, so the selected annotation
   presentation notices it, and `revealHeld` is how the margin's marker shows it.

   Which threads a widget has claimed or holds out is a reading other paints follow
   (`claimed`, `heldOut`): the margin lists a thread no widget seats, so a commit or a
   hold that changes the answer repaints it through its own presenter, and the thread
   pass itself paints no other owner's region. */
import { aborted } from "../abort.js";
import { reportPageError } from "../layer-client.js";
import { aimTargetAt, datumAimTarget } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { closestAcross } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { watchArrivals } from "../arrivals.js";
import { renderThreadSurface, clearThreadSurface } from "./inline.js";
import { readThreads, threadIdNamed } from "./state.js";
import { threadFocusDestination } from "./focus.js";
import { HeldArrivals } from "./held-news.js";
import { under } from "../shadow.js";
import { declareSide } from "../current-target.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { signal } from "/runtime/framework.js";
import { tick } from "../version-signal.js";

/** @typedef {import("./thread-card.js").ThreadRecord} ThreadRecord */
/** @typedef {import("../anchor-placement.js").ResolvedTarget} ThreadPlacement */
/** @typedef {{anchor: NonNullable<import("../../types/domain.js").Anchor> & {datum: string},
 * placement: ThreadPlacement & {status: "exact", datumElement: Element},
 * thread: ThreadRecord | null}} OutletTarget
 * A widget receives only exact datums in that widget; null thread identifies composition. */
/** @typedef {{signal: AbortSignal,
 * collection: ReturnType<typeof import("./state.js").readThreads>,
 * onCommit: (run: () => void) => void}} OutletContext */
/** @typedef {(targets: readonly OutletTarget[], context: OutletContext) =>
 * readonly (Element | null)[] | PromiseLike<readonly (Element | null)[]>} ThreadOutletSelector */

/** @typedef {{anchor: import("../../types/domain.js").Anchor | null | undefined,
 * placement: ThreadPlacement, thread: ThreadRecord | null}} PageOutletTarget */
/** @typedef {(targets: readonly PageOutletTarget[], context: OutletContext) => unknown} OutletRender */
/** @typedef {{active: () => {anchor: import("../../types/domain.js").Anchor} | null,
 * outlet: () => Element | null, node: () => HTMLElement,
 * open: ReturnType<typeof import("../composing/surface.js").createResponseSurface>["commentOnTarget"],
 * seat: ReturnType<typeof import("../composing/surface.js").createResponseSurface>["seatFab"],
 * restore: ReturnType<typeof import("../composing/surface.js").createResponseSurface>["restoreFab"]}} CompositionSurface */
/** @typedef {{invalidate: () => unknown, composition: CompositionSurface,
 * reveal: ReturnType<typeof import("./destination.js").createThreadDestinations>["openPageThread"]}} SurfaceServices */
/** @typedef {Omit<SurfaceServices, "reveal"> & {owner: Element, render: OutletRender, kind: "widget" | "page",
 * outlets: Set<Element>, placements: ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement> | null,
 * drawn: Set<string>, held: HeldArrivals | null, heldKeys: Set<string>,
 * reconcileQueued: boolean, cancelRender: () => void, stopSide: () => void,
 * handle: {read: typeof readThreads, reveal: (key: string) => unknown,
 * open: (node: Element) => boolean, update: () => void, unregister: () => void}}} Registration */
/** @type {Map<Element, Registration>} */
const registrations = new Map();
/** @type {Set<string>} */
let claimedIds = new Set();
let renderGeneration = 0;
// Moves when the answer `claimed` or `heldOut` gives changes, so a paint reading either
// follows it. This module's own reads take the plain answer (`holdsOut`): a pass that
// followed what it moves itself would claim another.
const ownership = signal(0);
/** @template T @param {ReadonlySet<T>} a @param {ReadonlySet<T>} b */
const sameSet = (a, b) => a.size === b.size && [...a].every((item) => b.has(item));
/** @param {string} id */
const holdsOut = (id) =>
  [...registrations.values()].some(({ held }) => held?.holds(id));

/** @param {Registration} registration */
function update(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}

/** @param {SurfaceServices} commands */
export function watchThreadSurfaces(commands) {
  const tags = tagsDeclaring((entry) => entry["x-thread-surface"] === true);
  if (!tags.length) return;
  watchArrivals(tags.join(","), [], {
    arrive(owner) {
      if (registrations.has(owner)) return;
      // Every door that brings a tag in imports its module before connecting its
      // markup (`widget-loader.js`), and this watch starts after startup's upgrade, so
      // an undefined owner failed to upgrade, which its module's failure reports.
      if (!owner.matches(":defined")) return;
      const outlets = owner.threadOutlets;
      if (typeof outlets !== "function")
        throw new TypeError(
          `<${owner.localName}> declares x-thread-surface without threadOutlets`,
        );
      register(
        owner,
        (targets, context) => {
          /** @type {unknown} */
          const result = Reflect.apply(outlets, owner, [targets, context]);
          return result;
        },
        commands,
        "widget",
      );
    },
    leave(owner) {
      registrations.get(owner)?.handle.unregister();
    },
  });
}

// The registered surface of a widget declaring `x-thread-surface`, as the widget reads
// it: before the runtime has registered it, or after it left, there is nothing to update
// and nothing it can open.
/** @param {Element} owner */
export const threadSurface = (owner) =>
  Object.freeze({
    update() {
      const registration = registrations.get(owner);
      if (registration) update(registration);
    },
    open: (/** @type {Element} */ node) =>
      registrations.get(owner)?.handle.open(node) ?? false,
  });

// The selected page presentation joins the same outlet and generation lifetime.
// This owner nominates fallback candidates. Only the final cohort move knows which
// widget nominations survived, and gives those seats priority over page nominations.
/** @param {Element} owner @param {OutletRender} render @param {SurfaceServices} options */
export function placePageThreads(owner, render, options) {
  if ([...registrations.values()].some((item) => item.kind === "page"))
    throw new Error("The document already has a page Thread presentation");
  return register(owner, render, options, "page");
}

/** @param {Element} owner @param {OutletRender} render @param {SurfaceServices} services
 * @param {"widget" | "page"} kind */
function register(owner, render, { invalidate, composition, reveal }, kind) {
  if (!(owner instanceof Element))
    throw new TypeError("A Thread presentation needs an Element owner");
  if (registrations.has(owner))
    throw new Error(`Thread surface ${owner.localName} registered twice`);
  // The outlet lifetime also owns its source location. A page rail's card stands
  // at the source it shows, while its unrelated controls keep their authored place.
  // The current location reader gives an innermost reply obligation priority over this relation.
  const stopSide = declareSide((node) => {
    const outlet = [...registration.outlets].find((outlet) => under(node, outlet));
    if (!outlet) return null;
    const thread = closestAcross(node, ".lf-page-thread");
    if (thread && under(thread, outlet))
      return (
        registration.placements?.placedAt(thread.getAttribute("data-thread"))?.place ??
        null
      );
    return outlet === composition.outlet()
      ? (registration.placements?.pendingAt()?.place ?? null)
      : null;
  });
  let active = true;
  /** @type {Registration["handle"]} */
  const handle = {
    read: readThreads,
    reveal(key) {
      if (!active) return false;
      const thread = readThreads().threads.find((item) => item.key === key);
      return thread ? reveal(thread.id) : false;
    },
    open(node) {
      if (!active) return false;
      const target = kind === "widget" ? datumAimTarget(node) : aimTargetAt(node);
      if (
        !target ||
        (kind === "widget" &&
          (target.anchor.section !== owner.id || !under(target.element, owner)))
      )
        throw new TypeError(
          kind === "widget"
            ? `Thread surface ${owner.localName} can open only its own projected datum`
            : "The page Thread presentation needs an addressable source target",
        );
      composition.open(target);
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
  /** @type {Registration} */
  const registration = {
    render,
    stopSide,
    handle,
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
    // The keys the last hold kept out, to tell a hold that changed from one that didn't.
    heldKeys: new Set(),
    reconcileQueued: false,
    cancelRender: () => {},
  };
  registrations.set(owner, registration);
  update(registration);
  return registration.handle;
}

/** @param {ReadonlySet<Element>} outlets */
function clearOutlets(outlets) {
  for (const outlet of outlets) {
    clearThreadSurface(outlet);
    outlet.removeAttribute("data-lf-thread-surface");
  }
}

/** @param {Pick<Registration, "owner">} registration @param {unknown} error */
function reportFailure({ owner }, error) {
  reportPageError(error, `thread surface ${owner.localName}#${owner.id} failed`);
}

// A widget removes a node that may hold an outlet only through its placement's
// `onCommit`, or after this: core's composer, the one node it carries from outlet to
// outlet, leaves every outlet under `node` now, for where the next commit would put
// it once `node` is gone, so the removal cannot take the user's editor with it.
/** @param {Node} node */
export function releaseOutlets(node) {
  for (const { outlets, composition } of registrations.values()) {
    const outlet = composition.outlet();
    for (const candidate of outlets)
      if (candidate === outlet && under(candidate, node)) {
        composition.restore();
        break;
      }
  }
}

/** @param {Registration} registration */
function clearRegistration(registration) {
  registration.cancelRender();
  registration.stopSide();
  registration.held?.dispose();
  registration.drawn = new Set();
  if (
    [...registration.outlets].some(
      (outlet) => outlet === registration.composition.outlet(),
    )
  )
    registration.composition.restore();
  clearOutlets(registration.outlets);
  registration.outlets.clear();
}

// A nomination remains a capability only while its output is connected inside its
// presentation owner. Preparation and final cohort admission share this one reading.
/** @param {Pick<Registration, "owner">} registration @param {Map<Element, ThreadRecord[]>} byOutlet */
function validateOutlets({ owner }, byOutlet) {
  for (const outlet of byOutlet.keys()) {
    if (!outlet.isConnected) byOutlet.delete(outlet);
    else if (!under(outlet, owner))
      throw new Error(
        `Thread surface ${owner.localName} returned an outlet outside its presentation owner`,
      );
  }
}

// Initial callback admission and the final move read the same current directory.
// A widget owns its exact datum; the page can present any complete attachment place.
/** @template {ThreadRecord | null} T
 * @typedef {{anchor: import("../../types/domain.js").Anchor | null | undefined,
 * placement: ThreadPlacement | null | undefined, thread: T}} TargetCandidate */
/** @template {ThreadRecord | null} T
 * @param {Pick<Registration, "owner">} registration @param {TargetCandidate<T>} target
 * @returns {target is TargetCandidate<T> & OutletTarget} */
function widgetTarget({ owner }, target) {
  const { anchor, placement } = target;
  return (
    placement?.status === "exact" &&
    !!anchor?.datum &&
    anchor.section === owner.id &&
    placement.datumElement instanceof Element &&
    under(placement.datumElement, owner)
  );
}
/** @template {ThreadRecord | null} T
 * @param {TargetCandidate<T>} target @returns {target is TargetCandidate<T> & PageOutletTarget} */
function pageTarget(target) {
  return (
    target.placement?.status === "exact" && target.placement.place instanceof Element
  );
}
/** @template {ThreadRecord | null} T
 * @param {Pick<Registration, "owner" | "kind">} registration @param {TargetCandidate<T>} target
 * @returns {{kind: "widget", target: OutletTarget & {thread: T}} | {kind: "page", target: PageOutletTarget & {thread: T}} | null} */
function admitTarget(registration, target) {
  return registration.kind === "page"
    ? pageTarget(target)
      ? { kind: "page", target }
      : null
    : widgetTarget(registration, target)
      ? { kind: "widget", target }
      : null;
}

/** @typedef {{registration: Registration, byOutlet: Map<Element, ThreadRecord[]>,
 * compositionOutlet: Element | null, committed: (() => void)[]}} SurfacePlan */
/** @param {ReturnType<typeof readThreads>} collection
 * @param {ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>} placements
 * @param {import("./thread-card.js").ThreadCommands & {composition: CompositionSurface}} commands */
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
  /** @type {SurfacePlan[] | null} */
  let prepared = null;
  const completion = prepare().then((plans) => {
    prepared = plans;
  });
  return { completion, cancel, commit };

  // Callbacks nominate current contained outlets. They do not publish membership or
  // move the canonical editor before the required Thread cohort is ready to commit.
  async function prepare() {
    /** @type {SurfacePlan[]} */
    const plans = [];
    // Registration order cannot confer source ownership: the selected page owner
    // runs after the widgets establish their held-arrival admission in this pass.
    const ordered = [...registrations.values()].sort(
      (a, b) => Number(a.kind === "page") - Number(b.kind === "page"),
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
      /** @type {Map<Element, ThreadRecord[]>} */
      const byOutlet = new Map();
      const abort = new AbortController();
      const cancelled = aborted(abort.signal);
      registration.cancelRender = () => abort.abort();
      /** @type {Element | null} */
      let compositionOutlet = null;
      /** @type {(() => void)[]} */
      const committed = [];
      try {
        /** @type {Map<string, NonNullable<ReturnType<typeof admitTarget<ThreadRecord>>>>} */
        const targets = new Map();
        for (const thread of collection.threads) {
          if (
            registration.kind === "page"
              ? holdsOut(thread.id)
              : thread.anchor?.section !== owner.id
          )
            continue;
          const placement = placements.placedAt(thread.id);
          const admitted = admitTarget(registration, {
            anchor: thread.anchor,
            placement,
            thread,
          });
          if (admitted) targets.set(thread.key, admitted);
        }
        const held = registration.held?.hold(
          [...targets.values()].flatMap(({ kind, target }) =>
            kind === "widget"
              ? [
                  {
                    thread: target.thread,
                    datum: target.anchor.datum,
                    node: target.placement.datumElement,
                  },
                ]
              : [],
          ),
          { drawn: registration.drawn, all: collection.threads },
        );
        if (held && !sameSet(held, registration.heldKeys)) {
          registration.heldKeys = held;
          tick(ownership);
        }
        const anchor = activeComposition?.anchor;
        const placement =
          anchor &&
          (registration.kind === "page" ||
            (anchor.datum && anchor.section === owner.id))
            ? placements.pendingAt()
            : null;
        // The core supplies the complete admitted batch. Each position keeps its
        // canonical Thread or composer identity here; consumers only return seats.
        /** @type {(PageOutletTarget | OutletTarget)[]} */
        const batch = [...targets]
          .filter(([key]) => !held?.has(key))
          .map(([_key, { target }]) => Object.freeze(target));
        const compositionTarget = admitTarget(registration, {
          anchor,
          placement,
          thread: null,
        });
        if (compositionTarget) batch.push(Object.freeze(compositionTarget.target));
        const rendering = render(Object.freeze(batch), {
          signal: abort.signal,
          collection,
          onCommit: (run) => committed.push(run),
        });
        const asynchronous =
          rendering != null &&
          (typeof rendering === "object" || typeof rendering === "function") &&
          "then" in rendering &&
          typeof rendering.then === "function";
        const outlets = asynchronous
          ? await Promise.race([rendering, cancelled])
          : rendering;
        if (!current()) return null;
        if (registrations.get(owner) !== registration || !owner.isConnected) {
          clearRegistration(registration);
          continue;
        }
        if (abort.signal.aborted) continue;
        if (!Array.isArray(outlets) || outlets.length !== batch.length)
          throw new TypeError(
            "A Thread placement callback must return one outlet or null per target",
          );
        /** @type {readonly unknown[]} */
        const nominated = outlets;
        for (const [index, { thread }] of batch.entries()) {
          const outlet = nominated[index];
          if (outlet === null) continue;
          if (!(outlet instanceof Element))
            throw new TypeError("A Thread outlet must be an Element or null");
          const threads = byOutlet.get(outlet) ?? [];
          if (thread) threads.push(thread);
          else compositionOutlet = outlet;
          byOutlet.set(outlet, threads);
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
        plans.push({
          registration,
          byOutlet: new Map(),
          compositionOutlet: null,
          committed: [],
        });
        reportFailure(registration, error);
        continue;
      }
      plans.push({ registration, byOutlet, compositionOutlet, committed });
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
                admitTarget(plan.registration, {
                  anchor: thread.anchor,
                  placement: placements.placedAt(thread.id),
                  thread,
                }) &&
                (plan.registration.kind === "widget" ||
                  (!widgetClaims.has(thread.id) && !holdsOut(thread.id))),
            ),
          );
        if (
          ![...plan.byOutlet.keys()].some(
            (outlet) => outlet === plan.compositionOutlet,
          ) ||
          !admitTarget(plan.registration, {
            anchor: activeComposition?.anchor,
            placement: placements.pendingAt(),
            thread: null,
          })
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
          if (!byOutlet.has(outlet)) outlet.removeAttribute("data-lf-thread-surface");
        for (const outlet of byOutlet.keys())
          outlet.toggleAttribute("data-lf-thread-surface", true);
        registration.outlets = new Set(byOutlet.keys());
        registration.drawn = new Set(
          [...byOutlet.values()]
            .flat()
            .flatMap((thread) => (thread.anchor?.datum ? [thread.anchor.datum] : [])),
        );
      }
      if (!sameSet(claimedIds, nextClaimed)) {
        claimedIds = nextClaimed;
        tick(ownership);
      }
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
    // Only now has the composer left every outlet a widget stopped returning, so the
    // widget can take those outlets down without taking the user's editor with them.
    for (const { registration, committed } of plans)
      for (const run of committed) {
        try {
          run();
        } catch (error) {
          reportFailure(registration, error);
        }
      }
  }
}

// Whether a widget seat drew the thread `id` at the last commit. A paint reading it is
// repainted when a commit changes the answer.
/** @param {string} id */
export const claimed = (id) => {
  ownership.value;
  return claimedIds.has(id);
};

// Whether a widget holds the thread `id` out of its flow, so that its margin marker is
// the notice it waits behind. Followed like `claimed`.
/** @param {string} id */
export const heldOut = (id) => {
  ownership.value;
  return holdsOut(id);
};

// Release the named held arrivals through their widget's existing render proof.
// This owner decides admission and returns readiness; the core destination owns the
// gesture's original intent and its focus after the current outlet has committed.
/** @param {readonly string[]} ids */
export function revealHeld(ids) {
  for (const registration of registrations.values()) {
    const [id] = registration.held?.show(ids) ?? [];
    if (id) {
      const presented = (async () => {
        await registration.invalidate();
        await whenDocumentPresented();
      })();
      return { id, presented };
    }
  }
  return null;
}

// Resolve after reveal/presentation: a datum's outlet may have been replaced. Travel
// takes the node rather than a callback that privately focuses and scrolls it.
/** @param {string} name @param {{part?: import("./destination.js").ThreadPart}} [options] */
export function surfaceFocusTarget(name, { part = "reply" } = {}) {
  const id = threadIdNamed(name);
  for (const registration of registrations.values()) {
    const thread = [...registration.outlets]
      .map((outlet) =>
        outlet.querySelector(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
      )
      .find(Boolean);
    if (!thread) continue;
    return threadFocusDestination(thread, { part, message: name });
  }
  return null;
}
