/* Canonical Thread placement into exact widget seats and one page presentation.

   A widget whose element has a `threadOutlets` method is a seat for as long as it
   stands upgraded: `watchThreadSurfaces` registers it once its module has defined it and
   retires it when it leaves, over the same arrival lifetime every element owner holds
   (`watchArrivals`, dom/arrivals.js), so a move within one batch keeps it. The runtime asks
   the widget itself for outlets with
   `owner.threadOutlets(targets, {signal, collection, onCommit})` on every thread pass.
   The widget says its seats changed as it says any change in what it holds, with
   `lf-layout`, which asks for a pass (annotations/anchor-controls.js), and reaches its
   registration through `threadSurface(owner)` to open a comment on itself or one of
   its datums (`open(node)`) or to take the composer out of a node it is about to
   remove (`release(node)`). The selected page presentation registers explicitly
   (`placePageThreads`).

   A widget is offered two kinds of target, and no other thread on it: a datum it
   projects, and the widget itself, which is a thread anchored to its element and
   nothing inside it (state/thread/model.js, `seatOf`). A quote or a visual part of the widget stays
   the margin's, since it points into the widget's words rather than standing in the
   place the widget offers. The comment box seated in an outlet whose `lfHold` names a
   label offers a second send under that label, whose comment holds the widget
   (annotations/composing/selection.js).

   A placement claims one Thread's page position, so reconciliation joins the core
   Thread presentation. Both callbacks return outlets for an admitted batch;
   widget seats that survive final validation claim first, then the selected page presentation.
   Source coverage and outlet containment are separate: an authored page rail can
   show a target elsewhere in the document.

   Which threads a widget has claimed is a reading other paints follow (`claimed`):
   the margin lists a thread no widget seats, so a commit that changes the answer
   repaints it through its own presenter, and the thread pass itself paints no other
   owner's region. */
import { aborted } from "../../base/abort.js";
import { reportPageError } from "../../transport/layer-client.js";
import { reportFailure as reportWidgetFailure } from "../../lib/failure.js";
import { offlineInteractive } from "../../state/context.js";
import { aimTargetAt, datumAimTarget } from "../../readings/anchor-resolution.js";
import { sameAnchor } from "../../base/anchor-coordinate.js";
import { drawnThreadId, drawnThreadsWithId } from "./selectors.js";
import { registry } from "../../state/registry.js";
import { watchArrivals } from "../../dom/arrivals.js";
import { renderThreadSurface, clearThreadSurface } from "./inline.js";
import { readThreads, threadIdNamed, threadNamed } from "./state.js";
import { seatOf, seatRoot } from "../../state/thread/model.js";
import { threadFocusDestination } from "./focus.js";
import { under, closestAcross } from "../../lib/shadow-tree.js";
import { declareSide } from "../current-target.js";
import { signal } from "/vendor/signals-core.js";
import { tick } from "../../state/version-signal.js";

import { registrations, setRegistration, updateSurface } from "./surface-handles.js";
import type { ThreadCommands, ThreadRecord } from "./thread-card.js";
import type { ResolvedTarget, ThreadPlacements } from "./placement.js";
import type { Anchor } from "../../../types/domain.js";
import type { ThreadPart, createThreadDestinations } from "./destination.js";

type ThreadPlacement = ResolvedTarget;
type SurfacePlacements = Pick<ThreadPlacements, "placedAt" | "pendingAt">;
/** A widget receives only itself and the exact datums in it: `anchor.datum` and
 * `placement.datumElement` name a datum, and are absent where the target is the widget.
 * A null thread identifies composition. */
export type OutletTarget = {
  anchor: NonNullable<Anchor>;
  placement: ThreadPlacement & { status: "exact" };
  thread: ThreadRecord | null;
};
export type OutletContext = {
  signal: AbortSignal;
  collection: ReturnType<typeof readThreads>;
  onCommit: (run: () => void) => void;
};
export type ThreadOutletSelector = (
  targets: readonly OutletTarget[],
  context: OutletContext,
) => readonly (Element | null)[] | PromiseLike<readonly (Element | null)[]>;

type PageOutletTarget = {
  anchor: Anchor | null | undefined;
  placement: ThreadPlacement;
  thread: ThreadRecord | null;
};
type OutletRender = (
  targets: readonly PageOutletTarget[],
  context: OutletContext,
) => unknown;
export type CompositionSurface = {
  active: () => { anchor: Anchor; about: string | null } | null;
  outlet: () => Element | null;
  node: () => HTMLElement;
  open: (target: {
    anchor: Anchor;
    element?: Element | null;
    point?: Element | null;
  }) => unknown;
  seat: (outlet: Element) => boolean;
  restore: () => unknown;
};
type SurfaceServices = {
  invalidate: () => unknown;
  composition: CompositionSurface;
  reveal: ReturnType<typeof createThreadDestinations>["openPageThread"];
};
export type Registration = Omit<SurfaceServices, "reveal"> & {
  owner: Element;
  render: OutletRender;
  kind: "widget" | "page";
  outlets: Set<Element>;
  placements: SurfacePlacements | null;
  reconcileQueued: boolean;
  cancelRender: () => void;
  stopSide: () => void;
  handle: {
    read: typeof readThreads;
    reveal: (key: string) => unknown;
    open: (node: Element) => boolean;
    update: () => void;
    unregister: () => void;
  };
};
let claimedIds = new Set<string>();
let renderGeneration = 0;
// Moves when the answer `claimed` gives changes, so a paint reading it follows it.
const ownership = signal(0);
const sameSet = <T>(a: ReadonlySet<T>, b: ReadonlySet<T>) =>
  a.size === b.size && [...a].every((item) => b.has(item));

export function watchThreadSurfaces(commands: SurfaceServices) {
  // An export holds no thread and has nowhere to send a message (`exporting.py`), so a
  // widget there has nothing to seat and no comment box to open.
  if (offlineInteractive) return;
  // The method is the declaration: any tag a module upgrades may define it, so the
  // watch covers every such tag and asks each element.
  const tags = Object.keys(registry.$modules ?? {});
  if (!tags.length) return;
  watchArrivals(tags.join(","), [], {
    arrive(owner) {
      if (registrations.has(owner)) return;
      // Every door that brings a tag in imports its module before connecting its
      // markup (`records/widget-loader.js`), and this watch starts after startup's upgrade, so
      // an undefined owner failed to upgrade, which its module's failure reports.
      if (!owner.matches(":defined")) return;
      const outlets = owner.threadOutlets;
      if (typeof outlets !== "function") return;
      // A thread names its widget by id (`widgetTarget`), so an instance without one
      // can seat no thread and open no comment box. It registers nothing, which leaves
      // its opener null, and reports that as the widget's own failure, which the
      // page's error report and the render check carry without a press.
      if (!owner.id) {
        reportWidgetFailure(
          owner,
          new TypeError(
            "a widget that shows threads needs an id on each instance, and this one has none",
          ),
        );
        return;
      }
      register(
        owner,
        (targets, context) => {
          const result: unknown = Reflect.apply(outlets, owner, [targets, context]);
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

// The selected page presentation joins the same outlet and generation lifetime.
// This owner nominates fallback candidates. Only the final cohort move knows which
// widget nominations survived, and gives those seats priority over page nominations.
export function placePageThreads(
  owner: Element,
  render: OutletRender,
  options: SurfaceServices,
) {
  if ([...registrations.values()].some((item) => item.kind === "page"))
    throw new Error("The document already has a page Thread presentation");
  return register(owner, render, options, "page");
}

function register(
  owner: Element,
  render: OutletRender,
  { invalidate, composition, reveal }: SurfaceServices,
  kind: "widget" | "page",
) {
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
      return registration.placements?.placedAt(drawnThreadId(thread))?.place ?? null;
    return outlet === composition.outlet()
      ? (registration.placements?.pendingAt()?.place ?? null)
      : null;
  });
  const handle: Registration["handle"] = {
    read: readThreads,
    reveal(key) {
      if (registrations.get(owner) !== registration) return false;
      const thread = threadNamed(key);
      return thread ? reveal(thread.id) : false;
    },
    open(node) {
      if (registrations.get(owner) !== registration) return false;
      const target =
        kind === "page" || node === owner ? aimTargetAt(node) : datumAimTarget(node);
      if (
        !target ||
        (kind === "widget" &&
          (target.anchor.section !== owner.id || !under(target.element, owner)))
      )
        throw new TypeError(
          kind === "widget"
            ? `Thread surface ${owner.localName} can open only itself or its own projected datum`
            : "The page Thread presentation needs an addressable source target",
        );
      composition.open(target);
      return true;
    },
    update: () => updateSurface(registration),
    unregister() {
      if (registrations.get(owner) !== registration) return;
      setRegistration(owner, null);
      clearRegistration(registration);
      updateSurface(registration);
    },
  };
  const registration: Registration = {
    render,
    stopSide,
    handle,
    owner,
    kind,
    invalidate,
    composition,
    outlets: new Set(),
    placements: null,
    reconcileQueued: false,
    cancelRender: () => {},
  };
  setRegistration(owner, registration);
  updateSurface(registration);
  return registration.handle;
}

function clearOutlets(outlets: ReadonlySet<Element>) {
  for (const outlet of outlets) {
    clearThreadSurface(outlet);
    outlet.removeAttribute("data-lf-thread-surface");
  }
}

function reportFailure({ owner }: Pick<Registration, "owner">, error: unknown) {
  reportPageError(error, `thread surface ${owner.localName}#${owner.id} failed`);
}

function clearRegistration(registration: Registration) {
  registration.cancelRender();
  registration.stopSide();
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
function validateOutlets(
  { owner }: Pick<Registration, "owner">,
  byOutlet: Map<Element, ThreadRecord[]>,
) {
  for (const outlet of byOutlet.keys()) {
    if (!outlet.isConnected) byOutlet.delete(outlet);
    else if (!under(outlet, owner))
      throw new Error(
        `Thread surface ${owner.localName} returned an outlet outside its presentation owner`,
      );
  }
}

type TargetCandidate<T extends ThreadRecord | null> = {
  anchor: Anchor | null | undefined;
  placement: ThreadPlacement | null | undefined;
  thread: T;
  about?: string | null | undefined;
};

// Initial callback admission and the final move read the same current directory.
// A widget owns its exact datum and itself; the page can present any complete
// attachment place. The composer's `about` stands in for the root's where no thread
// exists yet, so a box and the thread it starts are admitted alike.
function widgetTarget<T extends ThreadRecord | null>(
  { owner }: Pick<Registration, "owner">,
  target: TargetCandidate<T>,
): target is TargetCandidate<T> & OutletTarget {
  const { anchor, placement, thread, about = null } = target;
  if (placement?.status !== "exact" || anchor?.section !== owner.id) return false;
  if (anchor.datum)
    return (
      placement.datumElement instanceof Element && under(placement.datumElement, owner)
    );
  return (
    (thread ? seatRoot(thread) : seatOf({ anchor, about })) === owner.id &&
    placement.kind === "element" &&
    placement.element === owner
  );
}
function pageTarget<T extends ThreadRecord | null>(
  target: TargetCandidate<T>,
): target is TargetCandidate<T> & PageOutletTarget {
  return (
    target.placement?.status === "exact" && target.placement.place instanceof Element
  );
}
function admitTarget<T extends ThreadRecord | null>(
  registration: Pick<Registration, "owner" | "kind">,
  target: TargetCandidate<T>,
):
  | { kind: "widget"; target: OutletTarget & { thread: T } }
  | { kind: "page"; target: PageOutletTarget & { thread: T } }
  | null {
  return registration.kind === "page"
    ? pageTarget(target)
      ? { kind: "page", target }
      : null
    : widgetTarget(registration, target)
      ? { kind: "widget", target }
      : null;
}

type SurfacePlan = {
  registration: Registration;
  byOutlet: Map<Element, ThreadRecord[]>;
  compositionOutlet: Element | null;
  committed: (() => void)[];
};
export function renderSurfaces(
  collection: ReturnType<typeof readThreads>,
  placements: SurfacePlacements,
  commands: ThreadCommands & { composition: CompositionSurface },
) {
  const generation = ++renderGeneration;
  const current = () => generation === renderGeneration;
  for (const registration of registrations.values()) registration.cancelRender();
  const cancel = () => {
    if (!current()) return;
    ++renderGeneration;
    for (const registration of registrations.values()) registration.cancelRender();
  };
  const activeComposition = commands.composition.active();
  let prepared: SurfacePlan[] | null = null;
  const completion = prepare().then((plans) => {
    prepared = plans;
  });
  return { completion, cancel, commit };

  // Callbacks nominate current contained outlets. They do not publish membership or
  // move the canonical editor before the required Thread cohort is ready to commit.
  async function prepare() {
    const plans: SurfacePlan[] = [];
    // Registration order cannot confer source ownership: the selected page owner
    // runs after the widgets in this pass.
    const ordered = [...registrations.values()].sort(
      (a, b) => Number(a.kind === "page") - Number(b.kind === "page"),
    );
    // Whether a registration still stands for its owner in the document, asked again
    // after a render's wait, during which either can change.
    const stands = (registration: Registration) =>
      registrations.get(registration.owner) === registration &&
      registration.owner.isConnected;
    for (const registration of ordered) {
      const { render, owner } = registration;
      if (registrations.get(owner) !== registration) continue;
      if (!owner.isConnected) {
        setRegistration(owner, null);
        clearRegistration(registration);
        continue;
      }
      registration.placements = placements;
      const byOutlet = new Map<Element, ThreadRecord[]>();
      const abort = new AbortController();
      const cancelled = aborted(abort.signal);
      registration.cancelRender = () => abort.abort();
      let compositionOutlet: Element | null = null;
      const committed: (() => void)[] = [];
      try {
        const targets: Map<
          string,
          NonNullable<ReturnType<typeof admitTarget<ThreadRecord>>>
        > = new Map();
        for (const thread of collection.threads) {
          if (registration.kind !== "page" && thread.anchor?.section !== owner.id)
            continue;
          const placement = placements.placedAt(thread.id);
          const admitted = admitTarget(registration, {
            anchor: thread.anchor,
            placement,
            thread,
          });
          if (admitted) targets.set(thread.key, admitted);
        }
        const anchor = activeComposition?.anchor;
        const placement =
          anchor && (registration.kind === "page" || anchor.section === owner.id)
            ? placements.pendingAt()
            : null;
        // The core supplies the complete admitted batch. Each position keeps its
        // canonical Thread or composer identity here; consumers only return seats.
        const batch: (PageOutletTarget | OutletTarget)[] = [...targets.values()].map(
          ({ target }) => Object.freeze(target),
        );
        const compositionTarget = admitTarget(registration, {
          anchor,
          placement,
          thread: null,
          about: activeComposition?.about,
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
        if (!stands(registration)) {
          clearRegistration(registration);
          continue;
        }
        if (abort.signal.aborted) continue;
        if (!Array.isArray(outlets) || outlets.length !== batch.length)
          throw new TypeError(
            "A Thread placement callback must return one outlet or null per target",
          );
        const nominated: readonly unknown[] = outlets;
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
                (plan.registration.kind === "widget" || !widgetClaims.has(thread.id)),
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
            about: activeComposition?.about,
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
      const nextClaimed = new Set<string>();
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
export const claimed = (id: string) => {
  ownership.value;
  return claimedIds.has(id);
};

// The node a widget's outlet draws for a thread's part.
// Resolve after reveal/presentation: a datum's outlet may have been replaced. Travel
// takes the node rather than a callback that privately focuses and scrolls it.
export function surfaceFocusTarget(
  name: string,
  { part = "reply" }: { part?: ThreadPart } = {},
) {
  const id = threadIdNamed(name);
  const thread = [...registrations.values()]
    .flatMap((registration) => [...registration.outlets])
    .map((outlet) => drawnThreadsWithId(outlet, id)[0])
    .find(Boolean);
  return thread ? threadFocusDestination(thread, { part, message: name }) : null;
}
