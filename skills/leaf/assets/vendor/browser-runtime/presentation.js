/** Mechanical presentation proof for immutable semantic publications.
 *
 * The semantic owner supplies an opaque document token and monotonically increasing
 * epoch. This coordinator opens the epoch before publication, lets synchronous
 * renderers replace inherited work, and seals membership after that publication
 * checkpoint. Replacing a required renderer reopens mechanical completion for the same
 * epoch. It retains renderer instances, promises, and commit proof; none of those
 * mechanical values enter the semantic snapshot.
 */

import { signal } from "./signals-core.js";



















































































































export function describeFailure(reason         )         {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (!(reason instanceof AggregateError) || reason.errors.length === 0) return message;
  return `${message}: ${reason.errors.map(describeFailure).join("; ")}`;
}

export function createPresentationCoordinator





 ({ reportFailure }                                              ) {
  // Mechanical observers use the same Signals primitive as semantic selections.
  // Changes wake a blocked reading; they never publish a semantic epoch.
  const changes = signal(0);
  const changed = () => {
    changes.value += 1;
  };
  let document                       = null;
  let documentGeneration = 0;
  let semanticEpoch = -1;
  let presentedEpoch = -1;
  let barrier                                                                = null;
  let waiters                          = [];
  let regionWaiters                                        = [];
  const rendererGenerations = new Map                ();
  const regions = new Map


   ();

  const validEpoch = (epoch        ) => {
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

  function regionOutcome(waiter                                     ) {
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
    nextDocument               ,
    nextSemanticEpoch        ,
  )                                         {
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
    const members = new Map


     ();
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

  function seal(publication                                        )          {
    if (!barrier || barrier.publication !== publication) return false;
    barrier.sealed = true;
    completeBarrier();
    resolveRegionWaiters();
    changed();
    return true;
  }

  function currentTicket(
    ticket                                                       ,
  ) {
    const record = ticket.record;
    return (
      ticket.documentGeneration === documentGeneration &&
      regions.get(record.region) === record &&
      record.ticket === ticket
    );
  }

  function finish(
    ticket                                                       ,
    status                    ,
    proof                   ,
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
    region        ,
    renderer          ,
  )                                   {
    if (document === null || barrier === null)
      throw new Error("begin a presentation publication before attaching a renderer");
    const record                                                              = {
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

    const present = (
      value       ,
      completion                            ,
      failSoft                             ,
    ) => {
      const ready = (async () => {
        if (regions.get(region) !== record) {
          await Promise.resolve(completion).catch(() => undefined);
          return;
        }
        const ticket                                                        = {
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
          let proof                   ;
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
      return ready;
    };

    const disconnect = () => {
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
    region        ,
    renderer          ,
    value       ,
  )                                                                           {
    const record = regions.get(region);
    return record &&
      record.renderer === renderer &&
      record.commit !== null &&
      Object.is(record.commit.value, value)
      ? record.commit
      : null;
  }

  function whenPresented(
    targetDocument               ,
    targetSemanticEpoch        ,
  )                               {
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
    current                                              ,
  )                               {
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
    current                                              ,
  )          {
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
    current                                                     ,
    wanted                   ,
  )          {
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
    current                                                     ,
    regions                   ,
  )                               {
    const wanted = [...new Set(regions)];
    for (;;) {
      const target = current();
      if (target === null) return "superseded";
      await new Promise                     ((resolve) => {
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

  function read()                                             {
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
    subscribe: (callback            ) =>
      changes.subscribe(() => {
        try {
          callback();
        } catch (reason) {
          reportFailure(reason);
        }
      }),
    read,
  });
}

/** Epoch presenters and the one pass that paints them.
 *
 * Every renderer owes the same three moves — open a ticket inside the synchronous
 * publication that opened the epoch, release the hold it inherited, and paint the newest
 * value once that publication has settled. A schedule starts the presenters it collected
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
 * finished — and anything queued behind that hold would never be drawn at all. What a
 * superseded paint keeps is its own ticket, so the coordinator still reports its
 * failure, because the DOM keeps whatever state that failure reached.
 */
export const PRESENTATION_HELD = Symbol("presentation held");








export function createPresentationSchedule(
  bindJob                                                  ,
) {
  let queued                                                = [];
  let running                  = [];
  let scheduled = false;
  let settling = false;
  let pass



           = null;

  function open() {
    pass ??= (() => {
      let settle             ;
      let refuse                            ;
      const promise = new Promise      ((resolve, reject) => {
        settle = resolve;
        refuse = reject;
      });
      // A caller that ignores this promise reads the failure from the coordinator's
      // report instead, so it must not raise a browser-level unhandled rejection.
      void promise.catch(() => undefined);
      return { promise, settle, refuse };
    })();
  }

  function collect(order        , run                     ) {
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
    let failure          = null;
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
    const finished = pass ;
    pass = null;
    if (failed) finished.refuse(failure);
    else finished.settle();
  }

  /** The page has caught up with the root it is reading. */
  const passed = () => pass?.promise ?? Promise.resolve();

  function presenter              ({
    attach,
    paint,
    failSoft,
    order = 0,
  }







   )                        {







    let handle                                          = null;
    let held                                              = null;
    let generation = 0;

    function claim(value       )         {
      const claimed = ++generation;
      let resolve                                     ;
      let reject                            ;
      const completion = new Promise                   ((done, fail) => {
        resolve = done;
        reject = fail;
      });
      // The only reading this claim has to answer for is a withheld one, which by
      // definition will never answer for itself. A paint still running keeps its own
      // ticket: it is what reports its own failure, and the document keeps whatever
      // state that failure reached. Answering for it here would fulfil the ticket its
      // rejection was going to travel on, and the fault would go unreported.
      const inherited = held;
      held = null;
      handle ??= attach();
      const ready =
        handle?.present(value, completion                      , failSoft) ??
        Promise.resolve();
      // The coordinator reports every rejection. Observe it here so a renderer can
      // deliberately leave its region pending without also raising a browser-level
      // unhandled rejection.
      void ready.catch(() => undefined);
      // Release the superseded hold behind the replacement, so an obsolete value cannot
      // briefly acknowledge this epoch between two claims.
      inherited?.(undefined);
      return { claimed, value, resolve, reject, ready };
    }

    async function run(ticket        ) {
      // Superseded before it painted. The claim that superseded it already installed
      // its own ticket, so the region is not waiting on this one for anything; settling
      // it releases the coordinator's continuation, which would otherwise hold this
      // reading's value for as long as the document lives.
      if (ticket.claimed !== generation) {
        ticket.resolve(undefined);
        return;
      }
      let withheld = false;
      try {
        const painted = paint(ticket.value, () => ticket.claimed === generation);
        if (painted === PRESENTATION_HELD) {
          withheld = true;
          // `held` is the current withheld reading, and a reading superseded while it
          // was deciding to withhold is not that. Nothing observable turns on it — the
          // stale hold would release a ticket no longer standing for the region — but
          // one name meaning one thing is worth a line.
          if (ticket.claimed === generation) held = ticket.resolve;
        } else ticket.resolve(await painted);
      } catch (error) {
        ticket.reject(error);
      }
      // The coordinator's answer is the verdict on this reading. It resolves once the
      // region has committed one, fail-soft proof included, and rejects when the failure
      // stands with the region still pending. A withheld reading keeps its ticket open
      // instead, so there is no answer to wait for.
      if (!withheld) await ticket.ready;
    }

    function sync(value       )                {
      // The claim is synchronous, inside the publication that opened the epoch. Only
      // the paint waits for the pass.
      const ticket = claim(value);
      collect(order, () => run(ticket));
      return passed();
    }

    function disconnect() {
      generation += 1;
      const inherited = held;
      held = null;
      inherited?.(undefined);
      handle?.disconnect();
      handle = null;
    }

    return Object.freeze({ sync, disconnect });
  }

  return Object.freeze({ presenter, passed });
}
// Generated from build/browser/presentation.ts by npm run build:browser.
