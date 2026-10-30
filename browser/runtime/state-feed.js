/* The page's ear: the state reads, finite freshness reads that say when to ask, the heartbeat
   that re-applies what the page holds, and the phase the answers leave it in.

   `statePhase` distinguishes `waiting`, `ready`, and `offline`. An empty `events` array
   while waiting means the log has not been read; it does not mean there are no comments.
   A restored or newly opened panel shows a loading state until that distinction
   resolves, and the page's general box stays usable throughout.

   A failed fetch is an offline answer: the authored page and local comments remain
   useful, while Decisions await the complete reading their actions need. Fixed status
   chrome reports the loss; a request still in flight remains loading. A successful
   response with malformed state is not an offline answer. A live server's error is no
   state either, but the status names it as the server's fault. Parsing or rendering
   errors pass to the recovery boundary and leave the candidate sequence unresolved;
   authored content stays readable while state-dependent controls remain unavailable. */

import { countTraffic } from "./traffic.js";
import { activityTransitionDue, tickClock } from "./presence.js";
import { offlineInteractive, offlineState, pageUrl, runtime } from "./context.js";
import { applicationState } from "./semantic-state.js";
import { completeReadingReturn, readingReturn } from "./reading-continuity.js";
import {
  completeData,
  dataHeaders,
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
async function readState(bound) {
  countTraffic("asked");
  try {
    // Before the first admission, the request can name the exact data reading
    // delivered with the document. Keep it in this request closure until its
    // answer is completed, even if another answer transfers ownership first.
    const held =
      runtime.data.version === null
        ? (document.documentElement.lfInitial.initialData() ?? runtime.data)
        : runtime.data;
    if (offlineInteractive)
      return { state: completeData(offlineState(), held), fault: null };
    const signal = globalThis.AbortSignal.timeout(bound);
    let res;
    try {
      res = await fetch(pageUrl("api/state"), {
        headers: layerHeaders(dataHeaders(held)),
        // Coalescing bounds concurrency; this bounds its other dimension. A proxy that
        // never answers cannot own the page's single read slot forever.
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
    return { state: completeData(JSON.parse(text), held), fault: null };
  } finally {
    // Heard once the read has ended whichever way: the body in hand, or nothing.
    countTraffic("heard");
  }
}

// A read whose rejection is observed here rather than wherever it is finally awaited.
function buffer(bound) {
  return readState(bound).catch((error) => ({ error }));
}

// Start the page's first read without leaving a rejection unobserved while widget
// startup continues. The result is still applied through readAndApply, at the boundary
// that has captured the upgraded authored state. A malformed answer therefore remains a
// startup fault; buffering changes when the network work runs, not what its answer
// means. The interface opens independently at upgrade, so the first read takes the long
// bound while authoritative presentation waits for its actual answer.
export function beginRead() {
  return buffer(FIRST_READ_TIMEOUT_MS);
}

// Failed state reads and crossed freshness observations retry on the clock. Freshness names a changed reading, but
// cannot guarantee its state read succeeded. Healthy pages read state only on change.
export function createStateFeed({
  stateApplying,
  invalidateDom,
  receiveState,
  prepareActivation,
}) {
  let readAnswered = false;

  // A read that did not land: the page asks again on the next tick and says why. A fault
  // its producer already reported (a paint, a state application) is reported once.
  function failed(error) {
    readAnswered = false;
    reportCarried(error, `read failed`);
    applicationState.setReach("broken");
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
  async function readNothing(fault = null) {
    readAnswered = false;
    if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
    if (fault !== null) applicationState.setReach("faulted", fault);
    else applicationState.setReach(runtime.keyRefused ? "refused" : "unreachable");
    await invalidateDom();
    await tick();
  }

  // A read and its application together, for the callers that want to be told when the
  // page has taken the answer in: the buffered first read, and a version activation,
  // which asks for the state it is
  // about to show. The activation opens its own read from a page a user is already
  // using, so it takes an ordinary read's bound rather than the first read's.
  async function readAndApply(read = buffer(STATE_READ_TIMEOUT_MS)) {
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
    let readQueued = false;
    let applyingReads = 0;
    // Give the read slot back, and start the trailing read a tick or freshness answer
    // queued behind the read that held it.
    const releaseSlot = () => {
      reading = false;
      if (!readQueued) return;
      readQueued = false;
      item();
    };
    // Nothing is being read or applied: what the page shows is the latest it holds.
    // The reading's own completions below ask less, since a newer read still in flight
    // would otherwise hold a return open for as long as that read takes.
    const feedQuiet = () => !reading && !applyingReads && !stateApplying();
    const askOnce = async () => {
      const returned = readingReturn();
      try {
        const { state, fault } = await readState(STATE_READ_TIMEOUT_MS);
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
    const item = () => {
      if (reading) {
        readQueued = true;
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
    let listening = null;
    let freshness = null;
    let nextLook = null;
    const stopListening = () => {
      clearTimeout(nextLook);
      nextLook = null;
      listening?.abort();
      listening = null;
      freshness = null;
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
              globalThis.AbortSignal.timeout(STATE_READ_TIMEOUT_MS),
            ]),
          });
          if (listening !== interval) return;
          if (!admitResponse(response))
            throw new Error("news belongs to another delivery");
          if (!response.ok) throw new Error(`news returned HTTP ${response.status}`);
          const observed = await response.text();
          if (listening === interval) {
            if (observed !== freshness && observed !== runtime.reading) item();
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
        // A state read can cross a short-lived process lease and name a different
        // observation than the unchanged freshness token. Repair that crossing on
        // the same clock as failed reads, rather than repeating state at every look.
        if (
          readAnswered &&
          sessionIsActive() &&
          (activityTransitionDue(runtime.state) ||
            (freshness !== null && freshness !== runtime.reading))
        )
          void item();
        else if (readAnswered) void heartbeat();
        else void item();
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

// The interface is usable at upgrade while the first reading finishes. Bound its
// network slot outside the hosted deploy gate's 120-second revision wait, rather than
// aborting a live container's answer while the gate is still waiting for it. An expired
// read is a completed offline answer and releases the slot for a retry.
const FIRST_READ_TIMEOUT_MS = 120_000;

// How long every read after that may take. These have no wait beside them, and the
// page status's one honesty mechanism about the server runs through a read that *completed*
// with nothing: its `unreachable` reach is the only path to OFFLINE_LINE, and a read still
// in flight holds the slot, so freshness or a clock tick only queues a trailing read
// behind it. This bound is therefore the whole time a user watching a live page can be
// shown a reading the server has stopped standing behind, which is a user's timescale
// rather than the gate's. On expiry readState produces the same offline answer as any
// lost request, and the shared retry clock asks again.
const STATE_READ_TIMEOUT_MS = 10_000;

// A read nothing answered.
const NOTHING = Object.freeze({ state: null, fault: null });

// Statuses a gateway sends when no server stands behind it.
const NO_SERVER_BEHIND = new Set([502, 503, 504]);
