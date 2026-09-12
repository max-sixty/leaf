/** Mechanical presentation proof for immutable semantic publications.
 *
 * The semantic owner supplies an opaque document token and monotonically increasing
 * epoch. This coordinator opens the epoch before publication, lets synchronous
 * renderers replace inherited work, and seals membership after that publication
 * checkpoint. Replacing a required renderer reopens mechanical completion for the same
 * epoch. It retains renderer instances, promises, and commit proof; none of those
 * mechanical values enter the semantic snapshot.
 */

export type PresentationOutcome = "presented" | "superseded";
export type PresentationStatus = "committed" | "failed";

export interface PresentationPublication<DocumentToken extends object> {
  readonly document: DocumentToken;
  readonly semanticEpoch: number;
}

export interface PresentationCommit<
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

export interface PresentationReading<DocumentToken extends object, Region> {
  readonly document: DocumentToken | null;
  readonly semanticEpoch: number;
  readonly presentedEpoch: number;
  readonly sealed: boolean;
  readonly pending: readonly Region[];
}

export interface PresentationHandle<Value, Proof> {
  present(
    value: Value,
    completion: PromiseLike<Proof> | Proof,
    failSoft?: (reason: unknown) => Proof,
  ): Promise<void>;
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

interface RegionWaiter<DocumentToken extends object, Region> extends Waiter<DocumentToken> {
  readonly regions: ReadonlySet<Region>;
  readonly cancelled?: () => boolean;
}

export function createPresentationCoordinator<
  DocumentToken extends object,
  Region,
  Renderer extends object,
  Value,
  Proof,
>({ reportFailure }: { reportFailure: (reason: unknown) => void }) {
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
    if (document === null || !Object.is(waiter.document, document))
      return "superseded";
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
    return publication;
  }

  function seal(publication: PresentationPublication<DocumentToken>): boolean {
    if (!barrier || barrier.publication !== publication) return false;
    barrier.sealed = true;
    completeBarrier();
    resolveRegionWaiters();
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

    const present = async (
      value: Value,
      completion: PromiseLike<Proof> | Proof,
      failSoft?: (reason: unknown) => Proof,
    ) => {
      if (regions.get(region) !== record) {
        await Promise.resolve(completion).catch(() => undefined);
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
      try {
        const proof = await completion;
        finish(ticket, "committed", proof);
      } catch (reason) {
        if (!currentTicket(ticket)) return;
        let proof: Proof | undefined;
        let reported = reason;
        try {
          proof = failSoft?.(reason);
        } catch (fallbackError) {
          reported = new AggregateError(
            [reason, fallbackError],
            "presentation and fail-soft failed",
          );
        }
        try {
          reportFailure(reported);
        } finally {
          finish(ticket, "failed", proof);
        }
      }
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

  function whenRegionsPresented(
    targetDocument: DocumentToken,
    targetSemanticEpoch: number,
    regions: readonly Region[],
  ): Promise<PresentationOutcome> {
    validEpoch(targetSemanticEpoch);
    const wanted = new Set(regions);
    return new Promise((resolve) => {
      const waiter = {
        document: targetDocument,
        semanticEpoch: targetSemanticEpoch,
        regions: wanted,
        resolve,
      };
      const outcome = regionOutcome(waiter);
      if (outcome) resolve(outcome);
      else regionWaiters.push(waiter);
    });
  }

  async function whenCurrentPresented(
    current: () => PresentationPublication<DocumentToken>,
  ): Promise<PresentationOutcome> {
    for (;;) {
      const target = current();
      await whenPresented(target.document, target.semanticEpoch);
      const latest = current();
      const reading = read();
      // A waiter resumes in a microtask. An earlier waiter may have opened a newer
      // publication or replaced a renderer in the same epoch before this continuation
      // runs, so readiness is current only after re-reading both owners.
      if (
        Object.is(reading.document, latest.document) &&
        reading.semanticEpoch === latest.semanticEpoch &&
        reading.presentedEpoch >= latest.semanticEpoch &&
        reading.sealed &&
        reading.pending.length === 0
      )
        return "presented";
    }
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
    whenCurrentRegionsPresented,
    read,
  });
}
