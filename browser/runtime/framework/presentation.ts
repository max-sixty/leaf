/** Presentation completion has one record per connected region. A publication seals
 * the set of synchronous claims; later descendants and replacement renderers can
 * reopen it. Unchanged regions carry their completion into the next publication.
 * Scoped readers wait only for the regions they need. Renderer/ticket identity
 * rejects stale completions without storing a second copy of semantic state.
 *
 * A departure stays pending for its microtask so a synchronous replacement cannot
 * briefly acknowledge the old view. Resolved tickets adopt asynchronous rendering;
 * superseding an unresolved hold releases it, while a started paint still reports
 * failures. A successful fallback completes a region with its explicit failure view.
 */
type PresentationOutcome = "presented" | "superseded";
type PresentationPublication = object;
interface PresentationTicket {
  resolve: (completion?: unknown) => void;
  reject: (reason: unknown) => void;
  ready: Promise<void>;
}
interface PresentationHandle {
  present(failSoft?: (reason: unknown) => unknown): PresentationTicket;
  disconnect(): void;
}
interface RegionRecord {
  complete: boolean;
  active: boolean;
  latest: object | null;
  release: (() => void) | null;
}
import { signal } from "/vendor/signals-core.js";
import { untracked } from "./snapshot.js";
export function createPresentationCoordinator({
  reportFailure,
}: {
  reportFailure: (reason: unknown) => void;
}) {
  const changes = signal(0);
  let wake = Promise.withResolvers<void>();
  let publication: PresentationPublication | null = null;
  let sealed = false;
  const regions = new Map<string, RegionRecord>();
  const pending = (wanted: Iterable<string> = regions.keys()) =>
    [...wanted].filter((key) => {
      const record = regions.get(key);
      return record && !record.complete;
    });
  function changed() {
    const previous = wake;
    wake = Promise.withResolvers();
    previous.resolve();
    changes.value = changes.peek() + 1;
  }
  function begin() {
    for (const [region, record] of regions) if (!record.active) regions.delete(region);
    publication = Object.freeze({});
    sealed = false;
    changed();
    return publication;
  }
  function seal(value: PresentationPublication) {
    if (value !== publication) return false;
    sealed = true;
    changed();
    return true;
  }
  function attach(region: string): PresentationHandle {
    if (!publication)
      throw new Error("begin a presentation publication before attaching a renderer");
    const record: RegionRecord = {
      complete: false,
      active: true,
      latest: null,
      release: null,
    };
    regions.set(region, record);
    const active = () => record.active && regions.get(region) === record;
    changed();
    function present(failSoft?: (reason: unknown) => unknown) {
      const completion = Promise.withResolvers<unknown>();
      const previous = record.release;
      record.release = () => queueMicrotask(() => completion.resolve(undefined));
      const ticket = {};
      if (active()) {
        record.latest = ticket;
        record.complete = false;
        changed();
      }
      const current = () => active() && record.latest === ticket;
      const ready = (async () => {
        try {
          await completion.promise;
        } catch (reason) {
          if (!active()) return;
          let recovered = false;
          let failure = reason;
          if (failSoft) {
            try {
              failSoft(reason);
              recovered = true;
            } catch (fallbackError) {
              if (fallbackError !== reason)
                failure = new AggregateError(
                  [reason, fallbackError],
                  "presentation and fail-soft failed",
                );
            }
          }
          reportFailure(failure);
          if (!current()) return;
          if (!recovered) throw failure;
        }
        if (current()) {
          record.complete = true;
          changed();
        }
      })();
      void ready.catch(() => {});
      previous?.();
      return Object.freeze({
        resolve: completion.resolve,
        reject: completion.reject,
        ready,
      });
    }
    function disconnect() {
      record.release?.();
      record.release = null;
      if (!active()) return;
      if (!sealed || pending().length) record.complete = false;
      record.active = false;
      // Keep an unfinished departure outstanding until a synchronous replacement
      // can take its seat. Region identity, rather than another inventory, protects it.
      queueMicrotask(() => {
        if (regions.get(region) !== record) return;
        regions.delete(region);
        changed();
      });
    }
    return Object.freeze({ present, disconnect });
  }
  const currentRegionsPresented = (wanted?: readonly string[]) =>
    sealed && !pending(wanted).length;
  const currentPresented = () => currentRegionsPresented();
  const whenCurrentPresented = () => whenCurrentRegionsPresented();
  async function whenCurrentRegionsPresented(
    wanted?: readonly string[],
    current = () => true,
  ): Promise<PresentationOutcome> {
    // Connection observers must register already-inserted owners before readiness is read.
    await Promise.resolve();
    for (;;) {
      const next = wake.promise;
      if (!current()) return "superseded";
      if (currentRegionsPresented(wanted)) return "presented";
      await next;
    }
  }
  function read() {
    return Object.freeze({
      sealed,
      pending: Object.freeze(pending()),
    });
  }
  return Object.freeze({
    begin,
    seal,
    attach,
    whenCurrentPresented,
    currentPresented,
    whenCurrentRegionsPresented,
    currentRegionsPresented,
    read,
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
  });
}

/** Presenters claim semantic completion synchronously and draw at the publication's
 * microtask checkpoint. Each owner names the DOM completion it reads in `after`;
 * native Lit `updateComplete` supplies an element's completion, while imperative
 * Lit renders commit synchronously. Registration and enqueue order confer nothing.
 *
 * DOM completion is independent of semantic completion. A paint's asynchronous tail
 * can prepare content or hold a reading without blocking dependent DOM readers.
 * Later materialization must invalidate its DOM consumers, as any mechanical
 * change does. The coordinator alone decides when each region has completed.
 *
 * The callback binder preserves each claim's input context around the synchronous
 * paint, after its DOM dependencies finish. Superseded and disconnected claims
 * release their DOM waiters; started asynchronous paints retain their tickets so
 * even late failures reach the coordinator. `passed` joins the whole pass's completion.
 */

/**
 * `sync` claims a value's ticket now and paints it on the pass that follows.
 * `committed` settles once the DOM its dependents need has committed, regardless of
 * held semantic completion. `disconnect` retires the renderer: it releases what it holds
 * and leaves the region to its successor.
 */
interface ScheduledPresenter<Value> {
  sync(value: Value): Promise<void>;
  committed(): Promise<void>;
  disconnect(): void;
}

/** One value a presenter claimed, awaiting its paint. */
interface Claim<Value> {
  readonly claimed: number;
  readonly dom: PromiseWithResolvers<void>;
  readonly value: Value;
  readonly presentation: PresentationTicket;
}

export function createPresentationSchedule(
  bindJob: <Result>(callback: () => Result) => () => Result | undefined,
) {
  let queued: Array<() => Promise<void>> = [];
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

  function collect(
    after: (() => readonly PromiseLike<unknown>[]) | undefined,
    run: () => Promise<void>,
    retired?: { ready: Promise<void>; current: () => boolean },
  ) {
    open();
    // Bind the actual synchronous paint, not the wait preceding it.
    const paint = bindJob(run);
    queued.push(async () => {
      let dependencies = after?.() ?? [];
      while (dependencies.length && (!retired || retired.current())) {
        // A failed owner leaves DOM too. Its coordinator reports the failure; other
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
    const finished = pass as PromiseWithResolvers<void>;
    pass = null;
    if (failed) finished.reject(failure);
    else finished.resolve();
  }

  /** The page has caught up with the root it is reading. */
  const passed = () => pass?.promise ?? Promise.resolve();

  /** Queue a native renderer, separating its scheduling return from committed DOM. */
  function enqueue(
    after: () => readonly PromiseLike<unknown>[],
    run: () => unknown,
    committed: () => PromiseLike<unknown>,
  ) {
    const completion = Promise.withResolvers<void>();
    const dom = Promise.withResolvers<void>();
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

  function presenter<Value>({
    attach,
    paint,
    failSoft,
    after,
  }: {
    attach: () => PresentationHandle;
    paint: (value: Value, current: () => boolean) => unknown;
    failSoft?: ((reason: unknown) => unknown) | undefined;
    after?: (() => readonly PromiseLike<unknown>[]) | undefined;
  }): ScheduledPresenter<Value> {
    let handle: PresentationHandle | null = null;
    let generation = 0;
    let dom = Promise.withResolvers<void>();
    dom.resolve();

    function claim(value: Value): Claim<Value> {
      const claimed = ++generation;
      handle ??= attach();
      const previous = dom;
      dom = Promise.withResolvers();
      previous.resolve();
      return { claimed, value, dom, presentation: handle.present(failSoft) };
    }

    async function run({ claimed, value, presentation, dom }: Claim<Value>) {
      // Superseded before it painted: the newer claim's ticket already released this one.
      if (claimed !== generation) return;
      let painted: unknown;
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
      // region has committed one, fallback included, and rejects when the failure
      // stands with the region still pending.
      await presentation.ready;
    }

    function sync(value: Value): Promise<void> {
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
