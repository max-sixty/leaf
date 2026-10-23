/** One owner's DOM writes followed by work that needs their committed DOM.
 *
 * Solid owns flushing the graph. A commit never recursively flushes it: view writes
 * publish props, then native onSettled runs error checks and the owner's next
 * measurement. A measurement may publish again, so each following callback waits
 * for another native settle. Independent owners keep independent lifetimes.
 *
 * `committed` covers these synchronous stretches. `ready` also adopts asynchronous
 * return values; a held preparation must not prevent another owner from reading DOM
 * this owner has already committed. Callers retain presentation tickets and decide
 * which owners depend on that DOM. This module orders no owners and schedules no
 * browser task. The host's run/bind hooks preserve reactive reads and input origin.
 * A current predicate cancels obsolete DOM work while retiring bound callbacks.
 * Work already started keeps its asynchronous result and failure reporting; a write
 * cancelled before it starts resolves ready with undefined.
 * Native scheduled owners start root commits: a caller flushing the graph cannot
 * lend its tracking, cancellation, or completion lifetime to an independent owner.
 */
import { flush, onSettled, runWithOwner } from "../solid.js";

























let active               = null;
const inline =    (callback         )    => callback();
const unchanged =    (callback         )            => callback;
const current = () => true;

function inside   (frame       , callback         )    {
  const previous = active;
  active = frame;
  try {
    return frame.run(callback);
  } finally {
    active = previous;
  }
}

/** Read or act on the DOM after this render's preceding writes have committed.
 * Outside a render commit, ordinary imperative code already owns current DOM.
 */
export function afterRender(callback               )       {
  if (!active) {
    callback();
    return;
  }
  const frame = active;
  frame.callbacks.push(
    frame.bind(() => {
      if (!frame.failed && frame.current()) return callback();
    }),
  );
}

/** Publish a retained view's props and check binding errors at the commit boundary.
 * The synchronous fallback is for imperative callers outside a rendering phase.
 * The write receives its publication's retirement before it can flush an eager mount.
 * An unconsumed binding failure can report once that owner commits or is cancelled.
 */
export function writeView(
  write                                  ,
  check            ,
)       {
  if (active) {
    active.checks.add(check);
    write(active.committed);
  } else {
    flush(() => write(Promise.resolve()));
    check();
  }
}

export function renderCommit   (
  write         ,
  options                = {},
)                  {
  const committed = Promise.withResolvers      ();
  const ready = Promise.withResolvers                        ();
  // A presenter can observe committed while its ticket observes ready. Neither
  // unobserved arm should create an additional browser-level rejection report.
  void committed.promise.catch(() => undefined);
  void ready.promise.catch(() => undefined);
  const parent = options.root ? null : active;
  const frame        = {
    failed: false,
    committed: committed.promise,
    callbacks: [],
    checks: new Set(),
    children: [],
    tails: [],
    run: options.run ?? parent?.run ?? inline,
    bind: options.bind ?? parent?.bind ?? unchanged,
    current: options.current ?? parent?.current ?? current,
  };
  if (parent) {
    parent.children.push(committed.promise);
    parent.tails.push(ready.promise);
  }
  let result                                 ;
  let ended = false;
  const fail = (error         ) => {
    if (ended) return;
    ended = true;
    frame.failed = true;
    // Bound invocations own a tracing lifecycle even when a prior callback failed.
    // Retire those jobs as no-ops rather than leaving their input scopes open.
    for (const callback of frame.callbacks.splice(0)) callback();
    frame.checks.clear();
    committed.reject(error);
    ready.reject(error);
  };
  const tail = (result         ) => {
    const pending = Promise.resolve(result);
    void pending.catch(() => undefined);
    frame.tails.push(pending);
  };
  const schedule = () => {
    // The owner of a native effect may disappear between publication and commit.
    // Leaf's explicit commit lifetime, rather than that incidental owner, owns this
    // callback. All exceptions are caught before they can interrupt Solid's queue.
    runWithOwner(null, () => onSettled(advance));
  };
  const advance = () => {
    if (ended) return;
    try {
      if (frame.current()) for (const check of frame.checks) check();
      frame.checks.clear();
      if (frame.children.length) {
        const children = frame.children.splice(0);
        void Promise.all(children).then(schedule, fail);
        return;
      }
      const callback = frame.callbacks.shift();
      if (callback) {
        // Finish this callback's descendants before a later sibling measures the
        // whole surface. A field's post-commit setup belongs before its panel's
        // focus handoff, even when the field registered that setup while drawing.
        const siblings = frame.callbacks.splice(0);
        try {
          tail(inside(frame, callback));
        } finally {
          frame.callbacks.push(...siblings);
        }
        schedule();
        return;
      }
      ended = true;
      committed.resolve();
      void Promise.all([result, ...frame.tails]).then(
        ([result]) => ready.resolve(result                          ),
        ready.reject,
      );
    } catch (error) {
      fail(error);
    }
  };
  try {
    result = Promise.resolve(frame.current() ? inside(frame, write) : undefined);
    // Observe an async rejection immediately, even while post-commit work remains.
    void result.catch(() => undefined);
    schedule();
  } catch (error) {
    fail(error);
  }
  return Object.freeze({ committed: committed.promise, ready: ready.promise });
}
// Generated from browser/framework/rendering.ts by build/browser/build.mjs.
