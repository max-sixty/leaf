/** Mechanical presentation proof for immutable semantic publications.
 *
 * The semantic owner supplies an opaque document token and monotonically increasing
 * epoch. This coordinator opens the epoch before publication, lets synchronous
 * renderers replace inherited work, and seals membership after that publication
 * checkpoint. Replacing a required renderer reopens mechanical completion for the same
 * epoch. It retains renderer instances, promises, and commit proof; none of those
 * mechanical values enter the semantic snapshot. Independent proof observers run
 * outside a notifier's snapshot collection; their reads belong to their own owner.
 */

import { signal } from "@preact/signals-core";
import { untracked } from "./snapshot.ts";

type PresentationOutcome = "presented" | "superseded";
type PresentationStatus = "committed" | "failed";

interface PresentationPublication<DocumentToken extends object> {
  readonly document: DocumentToken;
  readonly semanticEpoch: number;
}

interface PresentationCommit<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
> {
  readonly document: DocumentToken;
  readonly semanticEpoch: number;
  readonly region: Region;
  readonly renderer: Renderer;
  readonly rendererGeneration: number;
  readonly ticketGeneration: number;
  readonly value: Value;
  readonly status: PresentationStatus;
  readonly proof: Proof | undefined;
}

interface PresentationReading<DocumentToken extends object, Region> {
  readonly document: DocumentToken | null;
  readonly semanticEpoch: number;
  readonly presentedEpoch: number;
  readonly sealed: boolean;
  readonly pending: readonly Region[];
}

/** One presentation of a value, which the renderer settles with its proof once the
 * value is on screen, or rejects when painting it failed. `resolve` adopts a promise of
 * proof, so a renderer already holding its paint's promise hands that over; resolving
 * with nothing commits without proof. `ready` is the coordinator's verdict: it settles
 * once the region committed this presentation, fail-soft proof included, and rejects
 * when the failure stands with the region still pending.
 *
 * A renderer may leave a ticket open while it withholds a reading, as a widget does
 * through a drag. The handle settles that hold itself, with nothing, once a newer
 * presentation or `disconnect` supersedes it, so no renderer tracks its own holds. A
 * ticket the renderer already resolved, with a paint still running included, is left
 * to that paint: it is what reports the paint's failure, and the document keeps
 * whatever state that failure reached. The release waits a microtask, so a paint whose
 * synchronous part supersedes its own ticket, by claiming the region again, still
 * hands its promise over first. */
interface PresentationTicket<Proof> {
  readonly resolve: (proof?: Proof | PromiseLike<Proof | undefined>) => void;
  readonly reject: (reason: unknown) => void;
  readonly ready: Promise<void>;
}

interface PresentationHandle<Value, Proof> {
  present(value: Value, failSoft?: (reason: unknown) => Proof): PresentationTicket<Proof>;
  disconnect(): void;
}

interface Ticket<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
> {
  readonly documentGeneration: number;
  readonly record: RegionRecord<DocumentToken, Region, Renderer, Value, Proof>;
  readonly ticketGeneration: number;
  readonly value: Value;
}

interface RegionRecord<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
> {
  readonly region: Region;
  readonly renderer: Renderer;
  readonly rendererGeneration: number;
  ticketGeneration: number;
  ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof> | null;
  commit: PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null;
}

interface BarrierMember<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
> {
  readonly record: RegionRecord<DocumentToken, Region, Renderer, Value, Proof>;
  ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof> | null;
  commit: PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null;
  retired: boolean;
}

interface Barrier<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
> {
  readonly publication: PresentationPublication<DocumentToken>;
  readonly members: Map<
    Region,
    BarrierMember<DocumentToken, Region, Renderer, Value, Proof>
  >;
  sealed: boolean;
  completed: boolean;
}

interface Waiter<DocumentToken extends object> {
  readonly document: DocumentToken;
  readonly semanticEpoch: number;
  readonly resolve: (outcome: PresentationOutcome) => void;
}

interface RegionWaiter<
  DocumentToken extends object,
  Region,
> extends Waiter<DocumentToken> {
  readonly regions: ReadonlySet<Region>;
  readonly cancelled?: () => boolean;
}

export function describeFailure(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
  return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}

export function createPresentationCoordinator<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
>({ reportFailure }: { reportFailure: (reason: unknown) => void }) {
  // Mechanical observers use the same Signals primitive as semantic selections.
  // Changes wake a blocked reading; they never publish a semantic epoch.
  const changes = signal(0);
  const changed = () => {
    changes.value += 1;
  };
  let document: DocumentToken | null = null;
  let documentGeneration = 0;
  let semanticEpoch = -1;
  let presentedEpoch = -1;
  let barrier: Barrier<DocumentToken, Region, Renderer, Value, Proof> | null = null;
  let waiters: Waiter<DocumentToken>[] = [];
  let regionWaiters: RegionWaiter<DocumentToken, Region>[] = [];
  const rendererGenerations = new Map<Region, number>();
  const regions = new Map<
    Region,
    RegionRecord<DocumentToken, Region, Renderer, Value, Proof>
  >();

  const validEpoch = (epoch: number) => {
    if (!Number.isSafeInteger(epoch) || epoch < 0)
      throw new TypeError("presentation epoch must be a non-negative safe integer");
  };

  function resolveWaiters() {
    const remaining = [];
    for (const waiter of waiters) {
      if (document === null || !Object.is(waiter.document, document))
        waiter.resolve("superseded");
      else if (presentedEpoch >= waiter.semanticEpoch) waiter.resolve("presented");
      else remaining.push(waiter);
    }
    waiters = remaining;
  }

  function regionOutcome(waiter: RegionWaiter<DocumentToken, Region>) {
    if (waiter.cancelled?.()) return "superseded";
    if (document === null || !Object.is(waiter.document, document)) return "superseded";
    if (semanticEpoch > waiter.semanticEpoch) return "superseded";
    if (semanticEpoch < waiter.semanticEpoch || !barrier?.sealed) return null;
    return [...waiter.regions].some(
      (region) => barrier?.members.get(region)?.commit === null,
    )
      ? null
      : "presented";
  }

  function resolveRegionWaiters() {
    const remaining = [];
    for (const waiter of regionWaiters) {
      const outcome = regionOutcome(waiter);
      if (outcome) waiter.resolve(outcome);
      else remaining.push(waiter);
    }
    regionWaiters = remaining;
  }

  function completeBarrier() {
    if (!barrier || barrier.completed || !barrier.sealed) return;
    if ([...barrier.members.values()].some((member) => member.commit === null)) return;
    barrier.completed = true;
    presentedEpoch = barrier.publication.semanticEpoch;
    resolveWaiters();
  }

  function begin(
    nextDocument: DocumentToken,
    nextSemanticEpoch: number,
  ): PresentationPublication<DocumentToken> {
    validEpoch(nextSemanticEpoch);
    const replacingDocument = document === null || !Object.is(document, nextDocument);
    if (!replacingDocument && nextSemanticEpoch < semanticEpoch)
      throw new RangeError("presentation epochs cannot decrease within one document");
    if (!replacingDocument && nextSemanticEpoch === semanticEpoch) {
      if (!barrier) throw new Error("the active document has no presentation barrier");
      return barrier.publication;
    }
    if (replacingDocument) {
      document = nextDocument;
      documentGeneration += 1;
      semanticEpoch = nextSemanticEpoch;
      presentedEpoch = -1;
      regions.clear();
      rendererGenerations.clear();
      resolveWaiters();
    } else semanticEpoch = nextSemanticEpoch;

    const publication = Object.freeze({
      document: nextDocument,
      semanticEpoch: nextSemanticEpoch,
    });
    const members = new Map<
      Region,
      BarrierMember<DocumentToken, Region, Renderer, Value, Proof>
    >();
    for (const [region, record] of regions) {
      let commit = record.commit;
      if (commit !== null) {
        commit = Object.freeze({ ...commit, semanticEpoch: nextSemanticEpoch });
        record.commit = commit;
      }
      members.set(region, {
        record,
        ticket: record.ticket,
        commit,
        retired: false,
      });
    }
    barrier = {
      publication,
      members,
      sealed: false,
      completed: false,
    };
    resolveRegionWaiters();
    changed();
    return publication;
  }

  function seal(publication: PresentationPublication<DocumentToken>): boolean {
    if (!barrier || barrier.publication !== publication) return false;
    barrier.sealed = true;
    completeBarrier();
    resolveRegionWaiters();
    changed();
    return true;
  }

  function currentTicket(
    ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof>,
  ) {
    const record = ticket.record;
    return (
      ticket.documentGeneration === documentGeneration &&
      regions.get(record.region) === record &&
      record.ticket === ticket
    );
  }

  function finish(
    ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof>,
    status: PresentationStatus,
    proof: Proof | undefined,
  ) {
    if (!currentTicket(ticket) || document === null) return;
    const record = ticket.record;
    const commit = Object.freeze({
      document,
      semanticEpoch,
      region: record.region,
      renderer: record.renderer,
      rendererGeneration: record.rendererGeneration,
      ticketGeneration: ticket.ticketGeneration,
      value: ticket.value,
      status,
      proof,
    });
    record.ticket = null;
    record.commit = commit;
    const member = barrier?.members.get(record.region);
    if (member?.record === record && member.ticket === ticket) {
      member.ticket = null;
      member.commit = commit;
      completeBarrier();
      resolveRegionWaiters();
    }
    changed();
  }

  function attach(
    region: Region,
    renderer: Renderer,
  ): PresentationHandle<Value, Proof> {
    if (document === null || barrier === null)
      throw new Error("begin a presentation publication before attaching a renderer");
    const record: RegionRecord<DocumentToken, Region, Renderer, Value, Proof> = {
      region,
      renderer,
      rendererGeneration: (rendererGenerations.get(region) ?? 0) + 1,
      ticketGeneration: 0,
      ticket: null,
      commit: null,
    };
    rendererGenerations.set(region, record.rendererGeneration);
    regions.set(region, record);
    // `attach` declares this renderer required. A renderer can appear after its
    // predecessor's retirement completed the same-epoch barrier, so membership cannot
    // depend on a surviving prior record or on the barrier still being open.
    barrier.completed = false;
    barrier.members.set(region, {
      record,
      ticket: null,
      commit: null,
      retired: false,
    });

    changed();

    // Releases the newest presentation. Resolving a ticket again does nothing, so this
    // settles only a hold its renderer left open.
    let latest: (() => void) | null = null;

    const present = (
      value: Value,
      failSoft?: (reason: unknown) => Proof,
    ): PresentationTicket<Proof> => {
      const { promise: completion, resolve, reject } = Promise.withResolvers<
        Proof | undefined
      >();
      const superseded = latest;
      latest = () => queueMicrotask(() => resolve(undefined));
      const ready = (async () => {
        if (regions.get(region) !== record) {
          await completion.catch(() => undefined);
          return;
        }
        const ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof> = {
          documentGeneration,
          record,
          ticketGeneration: ++record.ticketGeneration,
          value,
        };
        record.ticket = ticket;
        record.commit = null;
        const presentingBarrier = barrier;
        const member = presentingBarrier?.members.get(region);
        if (presentingBarrier && member?.record === record) {
          presentingBarrier.completed = false;
          member.ticket = ticket;
          member.commit = null;
          member.retired = false;
        }
        // Replacing a region can also invalidate a domain-scoped wait whose semantic
        // publication is unchanged, such as an older external-data revision.
        resolveRegionWaiters();
        changed();
        try {
          const proof = await completion;
          finish(ticket, "committed", proof);
        } catch (reason) {
          // A newer reading may already own this region. Its predecessor still left the
          // document in whatever state the failure reached, so the fault is reported
          // either way; only a renderer replaced outright has nothing to say about this
          // document. What a superseded ticket may not do is commit.
          const superseded = !currentTicket(ticket);
          if (superseded && regions.get(record.region) !== record) return;
          let proof: Proof | undefined;
          let reported = reason;
          let recovered = false;
          if (failSoft) {
            try {
              proof = failSoft(reason);
              recovered = true;
            } catch (fallbackError) {
              if (fallbackError !== reason)
                reported = new AggregateError(
                  [reason, fallbackError],
                  "presentation and fail-soft failed",
                );
            }
          }
          reportFailure(reported);
          if (superseded) return;
          // A renderer that supplies fallback proof has presented an explicit failure
          // state. Without that proof the region remains pending: declaring the page
          // presented would expose the partial rendering that just failed.
          if (recovered) finish(ticket, "failed", proof);
          else throw reported;
        }
      })();
      // The coordinator has already reported every rejection. Observe it here so a
      // background renderer can deliberately leave its region pending without also
      // creating a browser-level unhandled rejection. Callers that await `ready` still
      // receive the same rejection and can turn it into an owning startup failure.
      void ready.catch(() => undefined);
      // Released behind the ticket that replaces it, so an obsolete value cannot briefly
      // acknowledge this epoch between two presentations.
      superseded?.();
      return Object.freeze({ resolve, reject, ready });
    };

    const disconnect = () => {
      latest?.();
      latest = null;
      if (regions.get(region) !== record) return;
      regions.delete(region);
      const retiringBarrier = barrier;
      const member = retiringBarrier?.members.get(region);
      if (!retiringBarrier || member?.record !== record || retiringBarrier.completed)
        return;
      member.ticket = null;
      member.commit = null;
      member.retired = true;
      queueMicrotask(() => {
        if (
          barrier !== retiringBarrier ||
          retiringBarrier.completed ||
          retiringBarrier.members.get(region) !== member ||
          !member.retired
        )
          return;
        retiringBarrier.members.delete(region);
        completeBarrier();
        resolveRegionWaiters();
        changed();
      });
    };

    return Object.freeze({ present, disconnect });
  }

  function committed(
    region: Region,
    renderer: Renderer,
    value: Value,
  ): PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null {
    const record = regions.get(region);
    return record &&
      record.renderer === renderer &&
      record.commit !== null &&
      Object.is(record.commit.value, value)
      ? record.commit
      : null;
  }

  function whenPresented(
    targetDocument: DocumentToken,
    targetSemanticEpoch: number,
  ): Promise<PresentationOutcome> {
    validEpoch(targetSemanticEpoch);
    if (document === null || !Object.is(targetDocument, document))
      return Promise.resolve("superseded");
    const repairingCurrentEpoch =
      targetSemanticEpoch === semanticEpoch && barrier !== null && !barrier.completed;
    if (presentedEpoch >= targetSemanticEpoch && !repairingCurrentEpoch)
      return Promise.resolve("presented");
    return new Promise((resolve) => {
      waiters.push({
        document: targetDocument,
        semanticEpoch: targetSemanticEpoch,
        resolve,
      });
    });
  }

  async function whenCurrentPresented(
    current: () => PresentationPublication<DocumentToken>,
  ): Promise<PresentationOutcome> {
    for (;;) {
      const target = current();
      await whenPresented(target.document, target.semanticEpoch);
      // A waiter resumes in a microtask. An earlier waiter may have opened a newer
      // publication or replaced a renderer in the same epoch before this continuation
      // runs, so readiness is current only after re-reading both owners.
      if (currentPresented(current)) return "presented";
    }
  }

  function currentPresented(
    current: () => PresentationPublication<DocumentToken>,
  ): boolean {
    const latest = current();
    const reading = read();
    return (
      Object.is(reading.document, latest.document) &&
      reading.semanticEpoch === latest.semanticEpoch &&
      reading.presentedEpoch >= latest.semanticEpoch &&
      reading.sealed &&
      reading.pending.length === 0
    );
  }

  function currentRegionsPresented(
    current: () => PresentationPublication<DocumentToken> | null,
    wanted: readonly Region[],
  ): boolean {
    const target = current();
    return (
      target !== null &&
      regionOutcome({
        ...target,
        regions: new Set(wanted),
        resolve: () => {},
      }) === "presented"
    );
  }

  async function whenCurrentRegionsPresented(
    current: () => PresentationPublication<DocumentToken> | null,
    regions: readonly Region[],
  ): Promise<PresentationOutcome> {
    const wanted = [...new Set(regions)];
    for (;;) {
      const target = current();
      if (target === null) return "superseded";
      await new Promise<PresentationOutcome>((resolve) => {
        const waiter = {
          ...target,
          regions: new Set(wanted),
          cancelled: () => current() === null,
          resolve,
        };
        const outcome = regionOutcome(waiter);
        if (outcome) resolve(outcome);
        else regionWaiters.push(waiter);
      });
      const latest = current();
      if (latest === null) return "superseded";
      const outcome = regionOutcome({
        ...latest,
        regions: new Set(wanted),
        resolve: () => {},
      });
      if (outcome === "presented") return outcome;
    }
  }

  function read(): PresentationReading<DocumentToken, Region> {
    return Object.freeze({
      document,
      semanticEpoch,
      presentedEpoch,
      sealed: barrier?.sealed ?? false,
      pending: Object.freeze(
        barrier
          ? [...barrier.members]
              .filter(([, member]) => member.commit === null)
              .map(([region]) => region)
          : [],
      ),
    });
  }

  return Object.freeze({
    begin,
    seal,
    attach,
    committed,
    whenPresented,
    whenCurrentPresented,
    currentPresented,
    whenCurrentRegionsPresented,
    currentRegionsPresented,
    subscribe: (callback: () => void) =>
      changes.subscribe(() =>
        untracked(() => {
          try {
            callback();
          } catch (reason) {
            reportFailure(reason);
          }
        }),
      ),
    read,
  });
}

/** Epoch presenters and the one pass that paints them.
 *
 * Every renderer owes the same two moves — open a ticket inside the synchronous
 * publication that opened the epoch, and paint the newest value once that publication
 * has settled. A schedule starts the presenters it collected
 * in ascending `order` and repeats while painting has collected more.
 *
 * Starting is all the order buys, and the guarantee is worth stating exactly: when a
 * presenter begins, every lower-ranked presenter in that round has run as far as its
 * first `await`. So a renderer may rely on the markup a lower-ranked one writes
 * synchronously, and may not rely on anything that one finishes asynchronously — a
 * widget it upgrades, a box it measures after a frame. That dependency is stated once
 * here, beside the coordinator, rather than at every site that publishes, and `passed`
 * says the page has caught up with the root it is reading, which is what a caller waits
 * for instead of naming renderers.
 *
 * The host supplies a mandatory callback binder. Each claim binds its synchronous
 * paint turn before coalescing; the host can preserve the scheduling context without
 * changing the shared pass's ordering. A returned asynchronous tail is independent.
 *
 * The pass cannot await a presenter before starting the next, and a claim cannot wait
 * for the reading it supersedes, for the same reason: a renderer may be holding its
 * reading open — on a widget that has not prepared, on a gesture the user has not
 * finished — and anything queued behind that hold would never be drawn at all. The
 * handle releases a superseded hold; a superseded paint keeps its own ticket, so the
 * coordinator still reports its failure.
 */
export const PRESENTATION_HELD = Symbol("presentation held");

interface EpochPresenter<Value> {
  /** Claim this value's ticket now and paint it on the pass that follows. */
  sync(value: Value): Promise<void>;
  /** Retire this renderer: release what it holds and leave the region to its successor. */
  disconnect(): void;
}

export function createPresentationSchedule(
  bindJob: <Result>(callback: () => Result) => () => Result,
) {
  let queued: { order: number; run: () => Promise<void> }[] = [];
  let running: Promise<void>[] = [];
  let scheduled = false;
  let settling = false;
  let pass: PromiseWithResolvers<void> | null = null;

  function open() {
    if (pass) return;
    pass = Promise.withResolvers<void>();
    // A caller that ignores this promise reads the failure from the coordinator's
    // report instead, so it must not raise a browser-level unhandled rejection.
    void pass.promise.catch(() => undefined);
  }

  function collect(order: number, run: () => Promise<void>) {
    open();
    // Each claim belongs to its own scheduling context. The host binds it here,
    // before several producers share the one microtask that starts this pass.
    queued.push({ order, run: bindJob(run) });
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      const round = queued;
      queued = [];
      round.sort((left, right) => left.order - right.order);
      // Start them in rank order, so a renderer that reads DOM another materializes runs
      // after those writes are in the document. Nothing here waits for them: a renderer
      // may hold its reading open on a widget that has not prepared, and a later turn's
      // paint queued behind that hold would never reach the page at all.
      for (const { run } of round) {
        const started = run();
        void started.catch(() => undefined);
        running.push(started);
      }
      void drain();
    });
  }

  async function drain() {
    if (settling) return;
    settling = true;
    let failure: unknown = null;
    let failed = false;
    while (running.length || queued.length || scheduled) {
      const started = running;
      running = [];
      for (const outcome of await Promise.allSettled(started))
        if (outcome.status === "rejected" && !failed) {
          failed = true;
          failure = outcome.reason;
        }
    }
    settling = false;
    const finished = pass!;
    pass = null;
    if (failed) finished.reject(failure);
    else finished.resolve();
  }

  /** The page has caught up with the root it is reading. */
  const passed = () => pass?.promise ?? Promise.resolve();

  function presenter<Value, Proof>({
    attach,
    paint,
    failSoft,
    order = 0,
  }: {
    attach: () => PresentationHandle<Value, Proof>;
    paint: (
      value: Value,
      current: () => boolean,
    ) => Proof | PromiseLike<Proof> | typeof PRESENTATION_HELD;
    failSoft?: (reason: unknown) => Proof;
    order?: number;
  }): EpochPresenter<Value> {
    interface Claim {
      readonly claimed: number;
      readonly value: Value;
      readonly presentation: PresentationTicket<Proof>;
    }
    let handle: PresentationHandle<Value, Proof> | null = null;
    let generation = 0;

    function claim(value: Value): Claim {
      const claimed = ++generation;
      handle ??= attach();
      return { claimed, value, presentation: handle.present(value, failSoft) };
    }

    async function run({ claimed, value, presentation }: Claim) {
      // Superseded before it painted: the newer claim's ticket already released this one.
      if (claimed !== generation) return;
      let painted: Proof | PromiseLike<Proof> | typeof PRESENTATION_HELD;
      try {
        painted = paint(value, () => claimed === generation);
      } catch (error) {
        painted = Promise.reject(error);
      }
      // A withheld reading keeps its ticket open until a newer claim or `disconnect`
      // releases it, so there is no answer to wait for.
      if (painted === PRESENTATION_HELD) return;
      presentation.resolve(painted);
      // The coordinator's answer is the verdict on this reading. It resolves once the
      // region has committed one, fail-soft proof included, and rejects when the failure
      // stands with the region still pending.
      await presentation.ready;
    }

    function sync(value: Value): Promise<void> {
      // The claim is synchronous, inside the publication that opened the epoch. Only
      // the paint waits for the pass.
      const ticket = claim(value);
      collect(order, () => run(ticket));
      return passed();
    }

    function disconnect() {
      generation += 1;
      handle?.disconnect();
      handle = null;
    }

    return Object.freeze({ sync, disconnect });
  }

  return Object.freeze({ presenter, passed });
}
