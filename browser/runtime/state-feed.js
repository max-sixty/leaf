/* The page's ear: the state reads, finite freshness reads that say when to ask, the heartbeat
   that re-applies what the page holds, and the phase the answers leave it in.

   `statePhase` distinguishes `waiting`, `ready`, and `offline`. An empty `events` array
   while waiting means the log has not been read; it does not mean there are no comments.
   A restored or newly opened panel shows a loading state until that distinction
   resolves, and the page's general box stays usable throughout.

   A failed fetch is an offline answer: the authored page and local comments remain
   useful, while Decisions await the complete reading their actions need. Fixed status
   chrome reports the loss; a request still in flight remains loading. A read in flight
   waits for its answer, however slow, until a news look fails, the page's sign that the
   server no longer stands behind its reads: every read still out then ends as a lost
   request (`abandonReads`). A hang bound covers what the looks don't
   (`STATE_READ_TIMEOUT_MS`). A successful response with malformed state is not an
   offline answer. A live server's error is no state either, but the status names it as
   the server's fault. Parsing or rendering errors pass to the recovery boundary and
   leave the candidate sequence unresolved; authored content stays readable while
   state-dependent controls remain unavailable. */

import { countTraffic } from "./traffic.js";
import { activityTransitionDue, tickClock } from "./presence.js";
import { offlineInteractive, offlineState, pageUrl, runtime } from "./context.js";
import { applicationState } from "./semantic-state.js";
import { completeReadingReturn, readingReturn } from "./reading-continuity.js";
import {
  completeState,
  heldHeaders,
  heldReading,
  layerHeaders,
  admitResponse,
  reportCarried,
  sessionIsActive,
} from "./layer-client.js";

// The answer, decoded, with nothing applied yet: `{state, fault}`, with `state` null
// where nothing answered, and `fault` the live server's words where it answered with
// an error of its own.
//
// Reading and applying are separate acts because the page must stay free to ask again
// while an application is still running. Applying can take arbitrarily long and can be
// held open deliberately — a version activation runs inside a view transition, which
// waits on a frame and on whatever a module does during one — and an ear that waited
// for that would stop hearing. The page would then go silent for a reason none of its
// news is about, which is a wedge rather than a delay: nothing else would ever ask.
/** @returns {Promise<{state: import("./layer-client.js").CompletedState | null, fault: string | null}>} */
async function readState() {
  countTraffic("asked");
  try {
    if (offlineInteractive) return { state: await offlineState(), fault: null };
    const signal = globalThis.AbortSignal.any([
      globalThis.AbortSignal.timeout(STATE_READ_TIMEOUT_MS),
      abandonment.signal,
    ]);
    const held = heldReading();
    let res;
    try {
      res = await fetch(pageUrl("api/state"), {
        headers: layerHeaders(heldHeaders(held)),
        // Coalescing bounds concurrency; this bounds its other dimension. A server
        // that stops answering cannot own the page's single read slot.
        signal,
      });
    } catch {
      // Network absence is a completed answer: there is no log to replay, so the
      // offline authored page is honest. A successful but malformed response is
      // different — let JSON or processing errors escape so the caller retains the
      // recovery boundary.
      return NOTHING;
    }
    if (!admitResponse(res)) return NOTHING;
    // A refusal is not state: the server answers a missing key with error-shaped JSON
    // at 401. A live server refusing the key and a dead one both leave the page
    // unreachable from here; the page status says which, since only the refused key has a
    // recourse the user takes (`runtime.keyRefused`). A gateway answering for a server
    // behind it that isn't there, such as the website's edge while a container starts,
    // is no answer either. Any other failure is the live server's own, which names
    // itself (http.py, `_answer`): the page says that fault rather than calling the
    // server offline, and asks again as it would of an absent one.
    if (!res.ok) {
      if (res.status === 401 || NO_SERVER_BEHIND.has(res.status)) return NOTHING;
      const answer = await res.json().catch(() => null);
      return { state: null, fault: answer?.error ?? `HTTP ${res.status}` };
    }
    // Receiving headers does not complete delivery: the body can still be lost.
    // Keep transport failure separate from parsing a fully delivered answer.
    let text;
    try {
      text = await res.text();
    } catch {
      return NOTHING;
    }
    /** @type {import("./layer-client.js").StateAnswer} */
    const state = JSON.parse(text);
    return { state: completeState(state, held), fault: null };
  } finally {
    // Heard once the read has ended whichever way: the body in hand, or nothing.
    countTraffic("heard");
  }
}

// What every state read in flight listens to besides its own bound.
let abandonment = new AbortController();

// End every state read in flight as a lost request, and give the reads after a fresh
// signal. A news look that heard nothing calls this. Only a read that completes with
// nothing tells the page status the server is unreachable, and a read still in flight
// holds the page's one read slot, so without this a failed look could only queue a
// read behind one that a gone server will never answer.
function abandonReads() {
  abandonment.abort();
  abandonment = new AbortController();
}

// A read whose rejection is observed here rather than wherever it is finally awaited.
function buffer() {
  return readState().catch((error) => ({ error }));
}

// Start the page's first read without leaving a rejection unobserved while widget
// startup continues. The result is still applied through readAndApply, at the boundary
// that has captured the upgraded authored state. A malformed answer therefore remains a
// startup fault; buffering changes when the network work runs, not what its answer
// means. Initial presentation waits for this answer, or its bounded offline result.
export function beginRead() {
  return buffer();
}

// Failed state reads and crossed freshness observations retry on the clock. Freshness names a changed reading, but
// cannot guarantee its state read succeeded. Healthy pages read state only on change.
/** @param {{
 * stateApplying: () => boolean,
 * stateInHand: () => import("../types/contract.js").ServedState | null,
 * invalidateDom: () => Promise<unknown>,
 * receiveState: (state: import("./layer-client.js").CompletedState) => Promise<unknown>,
 * prepareActivation: ReturnType<typeof import("./version.js").createVersionController>["prepareActivation"]
 * }} dependencies */
export function createStateFeed({
  stateApplying,
  stateInHand,
  invalidateDom,
  receiveState,
  prepareActivation,
}) {
  let readAnswered = false;
  // What the page has adopted or has in hand, and so needs no read for.
  const readingInHand = () => stateInHand()?.reading ?? null;

  // A read that did not land: the page asks again on the next tick and says why. A fault
  // its producer already reported (a paint, a state application) is reported once.
  /** @param {unknown} error */
  function failed(error) {
    readAnswered = false;
    reportCarried(error, `read failed`);
    applicationState.setReach({ reach: "broken" });
  }

  // The clock has no state to replay; time-dependent paints remember their own
  // displayed readings.
  async function tick() {
    if (stateApplying()) return;
    // A repaint through a reading paint has already reported its own failure.
    await tickClock(reportCarried);
    if (stateApplying()) return;
    document.dispatchEvent(new Event("lf-tick"));
  }

  // What the page does with an answer that brought no state, and the server's `fault`
  // where it said why.
  /** @param {string | null} fault */
  async function readNothing(fault = null) {
    readAnswered = false;
    if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
    if (fault !== null) applicationState.setReach({ reach: "faulted", fault });
    else
      applicationState.setReach({
        reach: runtime.keyRefused ? "refused" : "unreachable",
      });
    await invalidateDom();
    await tick();
  }

  // A read and its application together, for the callers that want to be told when the
  // page has taken the answer in: the buffered first read, and a version activation,
  // which asks for the state it is about to show.
  async function readAndApply(read = buffer()) {
    const answer = await read;
    if ("error" in answer) throw answer.error;
    const { state, fault } = answer;
    if (!state) {
      await readNothing(fault);
      return;
    }
    await receiveState(state);
    readAnswered = true;
  }

  async function heartbeat() {
    if (stateApplying()) return;
    try {
      if (runtime.statePhase === "ready" && runtime.state && !runtime.showsActive) {
        const activation = await prepareActivation(runtime.state);
        if (activation?.activates()) await receiveState(runtime.state);
      }
      await tick();
    } catch (error) {
      readAnswered = false;
      reportCarried(error, `tick failed`);
    }
  }

  /** @param {() => void | Promise<unknown>} present */
  function startFeed(present, initialRead = beginRead()) {
    // Upgrade has already opened reading and commenting. Authoritative presentation
    // waits for an actual answer; elapsed time cannot turn an unanswered read offline.
    const readAndPresent = async () => {
      try {
        await readAndApply(initialRead);
      } catch (error) {
        failed(error);
        return;
      } finally {
        releaseSlot();
      }
      try {
        await present();
      } catch (error) {
        failed(error);
      }
    };
    // What the page does when a freshness look says it has moved. State application remains
    // independent — see readState — but the network side admits only one read at a time.
    // stream.json can move several times while a container is still answering the first
    // read; those wake-ups mean "read again afterwards", not "open another socket". One
    // trailing read therefore absorbs the whole burst and keeps reads from queueing behind
    // the page transaction they are trying to observe.
    //
    // Presentation is chained onto application because it is a fact about applied state:
    // a page whose first answer did not present must still present on a later one. An
    // answer with nothing in it — an unreachable server, a refused key, a layer that has
    // moved on and is reloading — still presents, since the authored page under an
    // unreachable server is a page, and saying so is the page status's job.
    // The buffered first read is already out, so the slot starts held: a tick or a freshness
    // answer arriving while it is still unanswered queues a trailing read behind it instead
    // of opening a second one alongside.
    let reading = true;
    // What the trailing read is for: the news a look heard while the slot was held,
    // null when a tick or a failed look asked for no reading in particular, and
    // undefined while nothing waits.
    /** @type {string | null | undefined} */
    let queued;
    let applyingReads = 0;
    // Give the read slot back, and start the trailing read a tick or freshness answer
    // queued behind the read that held it, unless the answer that read just handed in
    // is the reading the look heard of. A read that began before a save can wait out
    // the save's activation and answer with its revision.
    const releaseSlot = () => {
      reading = false;
      const asked = queued;
      queued = undefined;
      if (asked === undefined || (asked !== null && asked === readingInHand())) return;
      item();
    };
    // Nothing is being read or applied: what the page shows is the latest it holds.
    // The reading's own completions below ask less, since a newer read still in flight
    // would otherwise hold a return open for as long as that read takes.
    const feedQuiet = () => !reading && !applyingReads && !stateApplying();
    const askOnce = async () => {
      const returned = readingReturn();
      try {
        const { state, fault } = await readState();
        if (state) {
          applyingReads += 1;
          void receiveState(state)
            .then(
              async () => {
                readAnswered = true;
                // receiveState waits for document proof and any invalidation
                // queued behind it. present alone only stamps first startup.
                await present();
                // An overtaken candidate may fulfill before the newer candidate
                // finishes preparing or painting. Only the last applying read
                // can restore protection; otherwise the freshness look closes it.
                if (applyingReads === 1 && !stateApplying())
                  completeReadingReturn(returned);
              },
              async (error) => {
                failed(error);
                await present();
              },
            )
            // Presentation's own fault is reported as its own: the read behind it
            // stands, and the tick retries the presentation rather than the read.
            .catch((error) => {
              reportCarried(error, `presentation failed`);
            })
            .finally(() => {
              applyingReads -= 1;
            });
        } else {
          void readNothing(fault)
            .then(async () => {
              await present();
              if (!applyingReads && !stateApplying()) completeReadingReturn(returned);
            })
            .catch(failed);
        }
      } catch (error) {
        failed(error);
      }
    };
    /** @param {string | null} [observed] the news that asks, if a look heard it */
    const item = (observed = null) => {
      if (reading) {
        queued = queued === null || observed === null ? null : observed;
        return;
      }
      reading = true;
      void askOnce().finally(releaseSlot);
    };
    // Each visible document asks for a cheap reading, never holding a connection
    // between looks. State still travels through the coalesced read above, and an
    // unchanged token does not replay or repaint the page. The news request is also
    // this document's visible-page lease; hidden documents cancel it and stop asking.
    const pageIsVisible = () => document.visibilityState !== "hidden";
    let feedStarted = false;
    /** @type {AbortController | null} */
    let listening = null;
    /** @type {string | null} */
    let freshness = null;
    // What the page had in hand when the last look heard the news name another
    // reading, or null when the two agreed. The page may hold no reading yet.
    /** @type {{held: string | null} | null} */
    let crossed = null;
    /** @type {ReturnType<typeof setTimeout> | undefined} */
    let nextLook;
    const stopListening = () => {
      clearTimeout(nextLook);
      nextLook = undefined;
      listening?.abort();
      listening = null;
      freshness = null;
      crossed = null;
    };
    const listen = () => {
      if (!feedStarted || !pageIsVisible() || !sessionIsActive() || listening) return;
      const interval = new AbortController();
      listening = interval;
      const look = async () => {
        let delay = LOOK_MS;
        const returned = readingReturn();
        try {
          const response = await fetch(pageUrl("api/news"), {
            headers: layerHeaders(),
            signal: globalThis.AbortSignal.any([
              interval.signal,
              globalThis.AbortSignal.timeout(NEWS_TIMEOUT_MS),
            ]),
          });
          if (listening !== interval) return;
          if (!admitResponse(response))
            throw new Error("news belongs to another delivery");
          if (!response.ok) throw new Error(`news returned HTTP ${response.status}`);
          const observed = await response.text();
          if (listening === interval) {
            const held = readingInHand();
            crossed = observed === held ? null : { held };
            if (observed !== freshness && observed !== held) item(observed);
            else if (returned !== null && observed === runtime.reading && feedQuiet()) {
              // There is no newer state to ask for. Still present what this tab
              // held before the absence, then protect its new baseline again.
              await invalidateDom();
              await present();
              if (feedQuiet()) completeReadingReturn(returned);
            }
            freshness = observed;
          }
        } catch {
          if (listening !== interval) return;
          abandonReads();
          item();
          delay = TICK_MS;
        }
        if (listening === interval) nextLook = setTimeout(look, delay);
      };
      void look();
    };
    document.addEventListener("visibilitychange", () => {
      if (!pageIsVisible()) {
        stopListening();
        return;
      }
      const returned = readingReturn();
      // Revealing cached news needs no network round trip. A live page keeps
      // continuity interrupted until its freshness/state answer is presented;
      // offline pages already have their complete reading.
      void invalidateDom()
        .then(present)
        .then(() => {
          if (offlineInteractive || !sessionIsActive()) completeReadingReturn(returned);
        })
        .catch((error) => reportCarried(error, `return presentation failed`));
      listen();
    });
    document.addEventListener("lf-session-active", listen);
    // The ear opens after the first answer or startup fault. A successful read holds
    // a freshness token, so an unchanged page is not asked for twice; a failed read
    // releases its slot for recovery on the shared clock.
    const initialPresentation = readAndPresent();
    if (offlineInteractive) return;
    initialPresentation.finally(() => {
      feedStarted = true;
      // One shared clock serves temporal paint, deferred work, and failed reads.
      setInterval(() => {
        if (!pageIsVisible()) return;
        // Ask again after a read that failed, when the state in hand says its
        // activity has come due, or when the last look heard the news name a
        // reading other than the one the page still has in hand: a state read
        // crossed a short-lived process lease the news never named, or the page
        // dropped an answer it could not adopt. Repair each on this clock rather
        // than repeating state at every look. A read in flight, or an answer handed
        // in since that look, settles it instead, and if it fails the next tick asks.
        const asks =
          !readAnswered ||
          (sessionIsActive() &&
            (activityTransitionDue(stateInHand()) ||
              (crossed !== null && crossed.held === readingInHand())));
        if (asks && !reading) void item();
        else if (readAnswered) void heartbeat();
        // A presentation that failed is retried here as the poll retried it, since
        // a quiet page may see no read to chain it onto.
        void present();
      }, TICK_MS);
      listen();
    });
  }

  return { readAndApply, startFeed };
}

// How often the page refreshes display ages and checks the server-projected activity's
// next transition. The browser decides only when to ask; the returned projection decides
// what the agent is doing.
const TICK_MS = 2000;

// Visible pages check a cheap reading four times per second. Each finite response
// leaves the origin's HTTP slots free. Each completed check waits 250 ms before
// the next; request duration adds to the interval. Quiet checks do not rebuild.
const LOOK_MS = 250;

// How long a state read may go unanswered before it ends on time alone, as a completed
// offline answer that releases the slot for a retry. While the page looks for news, a
// failed look ends a read first, so this bound decides only for a read that hangs while
// the looks are answered, and for reads no look stands beside: the first, since the
// looks begin once it presents, and a read out while the page isn't looking, because it
// is hidden or a passive leaf.page session. The first read sets the value: the interface
// is usable at upgrade while it finishes, so its network slot is bounded outside the
// hosted deploy gate's 120-second revision wait, rather than aborting a live
// container's answer while the gate is still waiting for it.
const STATE_READ_TIMEOUT_MS = 120_000;

// How long a news look may go unanswered. A dead server fails the next look at once and
// a hung one fails it here; either failure abandons every state read in flight, so the
// page says it is offline on a user's timescale while a slow, live server's read goes on.
const NEWS_TIMEOUT_MS = 10_000;

// A read nothing answered.
const NOTHING = Object.freeze({ state: null, fault: null });

// Statuses a gateway sends when no server stands behind it.
const NO_SERVER_BEHIND = new Set([502, 503, 504]);
