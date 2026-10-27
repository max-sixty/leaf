// @ts-check
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

import { signal } from "/vendor/signals-core.js";
import { untracked } from "./snapshot.js";

/** @typedef {"presented" | "superseded"} PresentationOutcome */
/** @typedef {"committed" | "failed"} PresentationStatus */

/**
 * @template {object} DocumentToken
 * @typedef {{
 *   readonly document: DocumentToken;
 *   readonly semanticEpoch: number;
 * }} PresentationPublication
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly document: DocumentToken;
 *   readonly semanticEpoch: number;
 *   readonly region: Region;
 *   readonly renderer: Renderer;
 *   readonly rendererGeneration: number;
 *   readonly ticketGeneration: number;
 *   readonly value: Value;
 *   readonly status: PresentationStatus;
 *   readonly proof: Proof | undefined;
 * }} PresentationCommit
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @typedef {{
 *   readonly document: DocumentToken | null;
 *   readonly semanticEpoch: number;
 *   readonly presentedEpoch: number;
 *   readonly sealed: boolean;
 *   readonly pending: readonly Region[];
 * }} PresentationReading
 */

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
 * hands its promise over first.
 *
 * @template Proof
 * @typedef {{
 *   readonly resolve: (proof?: Proof | PromiseLike<Proof | undefined>) => void;
 *   readonly reject: (reason: unknown) => void;
 *   readonly ready: Promise<void>;
 * }} PresentationTicket
 */

/**
 * @template Value
 * @template Proof
 * @typedef {{
 *   present(
 *     value: Value,
 *     failSoft?: (reason: unknown) => Proof,
 *   ): PresentationTicket<Proof>;
 *   disconnect(): void;
 * }} PresentationHandle
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly documentGeneration: number;
 *   readonly record: RegionRecord<DocumentToken, Region, Renderer, Value, Proof>;
 *   readonly ticketGeneration: number;
 *   readonly value: Value;
 * }} Ticket
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly region: Region;
 *   readonly renderer: Renderer;
 *   readonly rendererGeneration: number;
 *   ticketGeneration: number;
 *   ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof> | null;
 *   commit: PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null;
 * }} RegionRecord
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly record: RegionRecord<DocumentToken, Region, Renderer, Value, Proof>;
 *   ticket: Ticket<DocumentToken, Region, Renderer, Value, Proof> | null;
 *   commit: PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null;
 *   retired: boolean;
 * }} BarrierMember
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly publication: PresentationPublication<DocumentToken>;
 *   readonly members: Map<
 *     Region,
 *     BarrierMember<DocumentToken, Region, Renderer, Value, Proof>
 *   >;
 *   sealed: boolean;
 *   completed: boolean;
 * }} Barrier
 */

/**
 * @template {object} DocumentToken
 * @typedef {{
 *   readonly document: DocumentToken;
 *   readonly semanticEpoch: number;
 *   readonly resolve: (outcome: PresentationOutcome) => void;
 * }} Waiter
 */

/**
 * @template {object} DocumentToken
 * @template Region
 * @typedef {Waiter<DocumentToken> & {
 *   readonly regions: ReadonlySet<Region>;
 *   readonly cancelled?: () => boolean;
 * }} RegionWaiter
 */

/** @param {unknown} reason @returns {string} */
export function describeFailure(reason) {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
  return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}

/**
 * @template {object} DocumentToken
 * @template Region
 * @template {object} Renderer
 * @template Value
 * @template Proof
 * @param {{ reportFailure: (reason: unknown) => void }} options
 */
export function createPresentationCoordinator({ reportFailure }) {
  // Mechanical observers use the same Signals primitive as semantic selections.
  // Changes wake a blocked reading; they never publish a semantic epoch.
  const changes = signal(0);
  const changed = () => {
    // A renderer can attach or present a child while it paints. Publishing that proof
    // must not make the containing paint a subscriber to its own completion.
    changes.value = changes.peek() + 1;
  };
  /** @type {DocumentToken | null} */
  let document = null;
  let documentGeneration = 0;
  let semanticEpoch = -1;
  let presentedEpoch = -1;
  /** @type {Barrier<DocumentToken, Region, Renderer, Value, Proof> | null} */
  let barrier = null;
  /** @type {Waiter<DocumentToken>[]} */
  let waiters = [];
  /** @type {RegionWaiter<DocumentToken, Region>[]} */
  let regionWaiters = [];
  /** @type {Map<Region, number>} */
  const rendererGenerations = new Map();
  /** @type {Map<Region, RegionRecord<DocumentToken, Region, Renderer, Value, Proof>>} */
  const regions = new Map();

  /** @param {number} epoch */
  const validEpoch = (epoch) => {
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

  /** @param {RegionWaiter<DocumentToken, Region>} waiter */
  function regionOutcome(waiter) {
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

  /**
   * @param {DocumentToken} nextDocument
   * @param {number} nextSemanticEpoch
   * @returns {PresentationPublication<DocumentToken>}
   */
  function begin(nextDocument, nextSemanticEpoch) {
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
    /** @type {Map<Region, BarrierMember<DocumentToken, Region, Renderer, Value, Proof>>} */
    const members = new Map();
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

  /** @param {PresentationPublication<DocumentToken>} publication @returns {boolean} */
  function seal(publication) {
    if (!barrier || barrier.publication !== publication) return false;
    barrier.sealed = true;
    completeBarrier();
    resolveRegionWaiters();
    changed();
    return true;
  }

  /** @param {Ticket<DocumentToken, Region, Renderer, Value, Proof>} ticket */
  function currentTicket(ticket) {
    const record = ticket.record;
    return (
      ticket.documentGeneration === documentGeneration &&
      regions.get(record.region) === record &&
      record.ticket === ticket
    );
  }

  /**
   * @param {Ticket<DocumentToken, Region, Renderer, Value, Proof>} ticket
   * @param {PresentationStatus} status
   * @param {Proof | undefined} proof
   */
  function finish(ticket, status, proof) {
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

  /**
   * @param {Region} region
   * @param {Renderer} renderer
   * @returns {PresentationHandle<Value, Proof>}
   */
  function attach(region, renderer) {
    if (document === null || barrier === null)
      throw new Error("begin a presentation publication before attaching a renderer");
    /** @type {RegionRecord<DocumentToken, Region, Renderer, Value, Proof>} */
    const record = {
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
    /** @type {(() => void) | null} */
    let latest = null;

    /**
     * @param {Value} value
     * @param {(reason: unknown) => Proof} [failSoft]
     * @returns {PresentationTicket<Proof>}
     */
    const present = (value, failSoft) => {
      /** @type {PromiseWithResolvers<Proof | undefined>} */
      const { promise: completion, resolve, reject } = Promise.withResolvers();
      const superseded = latest;
      latest = () => queueMicrotask(() => resolve(undefined));
      const ready = (async () => {
        if (regions.get(region) !== record) {
          await completion.catch(() => undefined);
          return;
        }
        /** @type {Ticket<DocumentToken, Region, Renderer, Value, Proof>} */
        const ticket = {
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
          /** @type {Proof | undefined} */
          let proof;
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

  /**
   * @param {Region} region
   * @param {Renderer} renderer
   * @param {Value} value
   * @returns {PresentationCommit<DocumentToken, Region, Renderer, Value, Proof> | null}
   */
  function committed(region, renderer, value) {
    const record = regions.get(region);
    return record &&
      record.renderer === renderer &&
      record.commit !== null &&
      Object.is(record.commit.value, value)
      ? record.commit
      : null;
  }

  /**
   * @param {DocumentToken} targetDocument
   * @param {number} targetSemanticEpoch
   * @returns {Promise<PresentationOutcome>}
   */
  function whenPresented(targetDocument, targetSemanticEpoch) {
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

  /**
   * @param {() => PresentationPublication<DocumentToken>} current
   * @returns {Promise<PresentationOutcome>}
   */
  async function whenCurrentPresented(current) {
    for (;;) {
      const target = current();
      await whenPresented(target.document, target.semanticEpoch);
      // A waiter resumes in a microtask. An earlier waiter may have opened a newer
      // publication or replaced a renderer in the same epoch before this continuation
      // runs, so readiness is current only after re-reading both owners.
      if (currentPresented(current)) return "presented";
    }
  }

  /** @param {() => PresentationPublication<DocumentToken>} current @returns {boolean} */
  function currentPresented(current) {
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

  /**
   * @param {() => PresentationPublication<DocumentToken> | null} current
   * @param {readonly Region[]} wanted
   * @returns {boolean}
   */
  function currentRegionsPresented(current, wanted) {
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

  /**
   * @param {() => PresentationPublication<DocumentToken> | null} current
   * @param {readonly Region[]} regions
   * @returns {Promise<PresentationOutcome>}
   */
  async function whenCurrentRegionsPresented(current, regions) {
    const wanted = [...new Set(regions)];
    for (;;) {
      const target = current();
      if (target === null) return "superseded";
      await /** @type {Promise<PresentationOutcome>} */ (
        new Promise((resolve) => {
          const waiter = {
            ...target,
            regions: new Set(wanted),
            cancelled: () => current() === null,
            resolve,
          };
          const outcome = regionOutcome(waiter);
          if (outcome) resolve(outcome);
          else regionWaiters.push(waiter);
        })
      );
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

  /** @returns {PresentationReading<DocumentToken, Region>} */
  function read() {
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
    /** @param {() => void} callback */
    subscribe: (callback) =>
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

/** Presenters claim semantic proof synchronously and draw at the publication's
 * microtask checkpoint. Each owner names the DOM completion it reads in `after`;
 * native Lit `updateComplete` supplies an element's completion, while imperative
 * Lit renders commit synchronously. Registration and enqueue order confer nothing.
 *
 * DOM completion is independent of semantic proof. A paint's asynchronous tail
 * can prepare content or hold a reading without blocking dependent DOM readers.
 * Later materialization must invalidate its DOM consumers, as any mechanical
 * change does. The ledger alone decides which semantic revision is visible.
 *
 * The callback binder preserves each claim's input context around the synchronous
 * paint, after its DOM dependencies finish. Superseded and disconnected claims
 * release their DOM waiters; started asynchronous paints retain their tickets so
 * even late failures reach the coordinator. `passed` joins the whole pass's proof.
 */

/**
 * `sync` claims a value's ticket now and paints it on the pass that follows.
 * `committed` settles once the DOM its dependents need has committed, regardless of
 * held semantic proof. `disconnect` retires the renderer: it releases what it holds
 * and leaves the region to its successor.
 *
 * @template Value
 * @typedef {{
 *   sync(value: Value): Promise<void>;
 *   committed(): Promise<void>;
 *   disconnect(): void;
 * }} EpochPresenter
 */

/**
 * One value a presenter claimed, awaiting its paint.
 *
 * @template Value
 * @template Proof
 * @typedef {{
 *   readonly claimed: number;
 *   readonly dom: PromiseWithResolvers<void>;
 *   readonly value: Value;
 *   readonly presentation: PresentationTicket<Proof>;
 * }} Claim
 */

/** @param {<Result>(callback: () => Result) => () => Result} bindJob */
export function createPresentationSchedule(bindJob) {
  /** @type {(() => Promise<void>)[]} */
  let queued = [];
  /** @type {Promise<void>[]} */
  let running = [];
  let scheduled = false;
  let settling = false;
  /** @type {PromiseWithResolvers<void> | null} */
  let pass = null;

  function open() {
    if (pass) return;
    pass = /** @type {PromiseWithResolvers<void>} */ (Promise.withResolvers());
    // A caller that ignores this promise reads the failure from the coordinator's
    // report instead, so it must not raise a browser-level unhandled rejection.
    void pass.promise.catch(() => undefined);
  }

  /**
   * @param {(() => readonly PromiseLike<unknown>[]) | undefined} after
   * @param {() => Promise<void>} run
   * @param {{ ready: Promise<void>; current: () => boolean }} [retired]
   */
  function collect(after, run, retired) {
    open();
    // Bind the actual synchronous paint, not the wait preceding it.
    const paint = bindJob(run);
    queued.push(async () => {
      let dependencies = after?.() ?? [];
      while (dependencies.length && (!retired || retired.current())) {
        // A failed owner leaves DOM too. Its ledger reports the failure; other
        // owners must still draw. Retirement releases obsolete waiters immediately.
        const settled = Promise.allSettled(dependencies);
        await (retired ? Promise.race([settled, retired.ready]) : settled);
        const latest = after?.() ?? [];
        // A predecessor may have been replaced while this owner waited. Its retired
        // promise is no evidence that the replacement DOM has committed.
        if (latest.every((dependency) => dependencies.includes(dependency))) break;
        dependencies = latest;
      }
      return paint();
    });
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      const round = queued;
      queued = [];
      for (const run of round) {
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
    /** @type {unknown} */
    let failure = null;
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
    const finished = /** @type {PromiseWithResolvers<void>} */ (pass);
    pass = null;
    if (failed) finished.reject(failure);
    else finished.resolve();
  }

  /** The page has caught up with the root it is reading. */
  const passed = () => pass?.promise ?? Promise.resolve();

  /** Queue a native renderer, separating its scheduling return from committed DOM.
   * @param {() => readonly PromiseLike<unknown>[]} after
   * @param {() => void | PromiseLike<void>} run
   * @param {() => PromiseLike<unknown>} committed
   */
  function enqueue(after, run, committed) {
    /** @type {PromiseWithResolvers<void>} */
    const completion = Promise.withResolvers();
    /** @type {PromiseWithResolvers<void>} */
    const dom = Promise.withResolvers();
    collect(after, async () => {
      try {
        await run();
        // Release Lit's scheduleUpdate before awaiting its updateComplete: Lit
        // completes the native update only once this callback has returned.
        completion.resolve();
        await committed();
        dom.resolve();
      } catch (error) {
        completion.reject(error);
        dom.reject(error);
        throw error;
      }
    });
    return Object.freeze({ ready: completion.promise, committed: dom.promise });
  }

  /**
   * @template Value
   * @template Proof
   * @param {{
   *   attach: () => PresentationHandle<Value, Proof>;
   *   paint: (value: Value, current: () => boolean) => Proof | PromiseLike<Proof>;
   *   failSoft?: (reason: unknown) => Proof;
   *   after?: () => readonly PromiseLike<unknown>[];
   * }} options
   * @returns {EpochPresenter<Value>}
   */
  function presenter({ attach, paint, failSoft, after }) {
    /** @type {PresentationHandle<Value, Proof> | null} */
    let handle = null;
    let generation = 0;
    /** @type {PromiseWithResolvers<void>} */
    let dom = Promise.withResolvers();
    dom.resolve();

    /** @param {Value} value @returns {Claim<Value, Proof>} */
    function claim(value) {
      const claimed = ++generation;
      handle ??= attach();
      const previous = dom;
      dom = Promise.withResolvers();
      previous.resolve();
      return { claimed, value, dom, presentation: handle.present(value, failSoft) };
    }

    /** @param {Claim<Value, Proof>} claim */
    async function run({ claimed, value, presentation, dom }) {
      // Superseded before it painted: the newer claim's ticket already released this one.
      if (claimed !== generation) return;
      /** @type {Proof | PromiseLike<Proof>} */
      let painted;
      try {
        painted = paint(value, () => claimed === generation);
      } catch (error) {
        painted = Promise.reject(error);
      }
      // Imperative Lit rendering commits in this call. Its asynchronous tail is
      // semantic preparation and never stands in for native DOM completion.
      dom.resolve();
      presentation.resolve(painted);
      // The coordinator's answer is the verdict on this reading. It resolves once the
      // region has committed one, fail-soft proof included, and rejects when the failure
      // stands with the region still pending.
      await presentation.ready;
    }

    /** @param {Value} value @returns {Promise<void>} */
    function sync(value) {
      // The claim is synchronous, inside the publication that opened the epoch. Only
      // the paint waits for the pass.
      const ticket = claim(value);
      collect(after, () => run(ticket), {
        ready: ticket.dom.promise,
        current: () => ticket.claimed === generation,
      });
      return passed();
    }

    function disconnect() {
      generation += 1;
      dom.resolve();
      handle?.disconnect();
      handle = null;
    }

    return Object.freeze({ sync, committed: () => dom.promise, disconnect });
  }

  return Object.freeze({ presenter, enqueue, passed });
}
