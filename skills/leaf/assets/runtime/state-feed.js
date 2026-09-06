/* The page's ear: the state reads, the news stream that says when to ask, the heartbeat
   that re-applies what the page holds, and the phase the answers leave it in.

   `statePhase` distinguishes `waiting`, `ready`, and `offline`. An empty `events` array
   while waiting means the log has not been read; it does not mean there are no comments.
   A restored or newly opened panel keeps its general composer usable and shows a loading
   state until that distinction resolves.

   A failed fetch is a complete offline answer for interaction: the authored page is the
   best state available when no log can be reached, so fixed status chrome reports the
   loss and its controls may activate. A successful response with malformed state is not
   an offline answer. Parsing or rendering errors pass to the recovery boundary and leave
   the candidate sequence unresolved; authored content stays readable while
   state-dependent controls remain unavailable. */

import { countTraffic } from "./traffic.js";
import { activityTransitionDue, tickClock } from "./presence.js";
import { runtime } from "./context.js";
import { reportPageError, sameLayer } from "./layer-client.js";
import {
  projectionDeferred,
  reconcileKnownState,
  releaseProjectedOutbox,
} from "./projection.js";
import { paintKeys } from "./keyboard/scopes.js";
import { notifyDataSubscribers } from "./data.js";
import { renderStatus } from "./banner.js";
import { panelIsOpen } from "./chrome-layout.js";
import { renderPanel } from "./conversation/reconcile.js";
import { receiveState } from "./state-application.js";
import { prepareActivation } from "./version.js";

// The answer, decoded, with nothing applied yet.
//
// Reading and applying are separate acts because the page must stay free to ask again
// while an application is still running. Applying can take arbitrarily long and can be
// held open deliberately — a version activation runs inside a view transition, which
// waits on a frame and on whatever a module does during one — and an ear that waited
// for that would stop hearing. The page would then go silent for a reason none of its
// news is about, which is a wedge rather than a delay: nothing else would ever ask.
async function readState() {
  countTraffic("asked");
  try {
    let res;
    try {
      const revision = runtime.currentRevision;
      res = await fetch("/api/state", {
        headers: Number.isInteger(revision)
          ? { "Leaf-View-Revision": String(revision) }
          : {},
      });
    } catch {
      // Network absence is a completed answer: there is no log to replay, so the
      // offline authored page is honest. A successful but malformed response is
      // different — let JSON or processing errors escape so the caller retains the
      // recovery boundary.
      return null;
    }
    const responseGeneration = res?.ok && res.headers.get("Leaf-Layer");
    if (responseGeneration && !sameLayer(responseGeneration)) return null;
    // A refusal is not state: the server answers a missing key with error-shaped JSON
    // at 403. A live server refusing the key and a dead one both leave the page
    // unreachable from here, and the terminal link is the recourse for both.
    if (!res?.ok) return null;
    return await res.json();
  } finally {
    // Heard once the read has ended whichever way: the body in hand, or nothing.
    countTraffic("heard");
  }
}

// Start a read without leaving a rejection unobserved while widget startup continues.
// The result is still applied through readAndApply, at the boundary that has captured
// the upgraded authored state. A malformed answer therefore remains a startup fault;
// buffering changes when the network work runs, not what its answer means.
export function beginRead() {
  return readState().then(
    (state) => ({ state }),
    (error) => ({ error }),
  );
}

// Failed reads retry on the clock: a news wake-up says that state changed, but
// cannot guarantee its read succeeded. Healthy pages ask only when news moves.
let readAnswered = false;

// The clock has no state to replay. Only an explicitly deferred projection needs
// another attempt; time-dependent paints remember their own displayed readings.
async function tick() {
  if (projectionDeferred() && reconcileKnownState()) {
    if (releaseProjectedOutbox()) paintKeys();
    document.dispatchEvent(new Event("lf-actions"));
    await notifyDataSubscribers();
  }
  await tickClock(reportPageError);
  document.dispatchEvent(new Event("lf-tick"));
}

// What the page does with an answer that brought no state.
async function readNothing() {
  readAnswered = false;
  if (runtime.statePhase === "waiting") runtime.statePhase = "offline";
  renderStatus(null);
  if (panelIsOpen()) renderPanel();
  await tick();
}

// A read and its application together, for the callers that want to be told when the
// page has taken the answer in: the first read, which presentation waits on, and a
// version activation, which asks for the state it is about to show.
export async function readAndApply(read = beginRead()) {
  const answer = await read;
  if ("error" in answer) throw answer.error;
  const { state } = answer;
  if (!state) {
    await readNothing();
    return;
  }
  await receiveState(state);
  readAnswered = true;
}

async function heartbeat() {
  try {
    if (
      runtime.statePhase === "ready" &&
      runtime.state &&
      runtime.state.active.revision > runtime.currentRevision
    ) {
      const activation = await prepareActivation(runtime.state);
      if (activation?.activates()) await receiveState(runtime.state);
    }
    await tick();
  } catch (error) {
    readAnswered = false;
    reportPageError(`tick failed: ${error?.message ?? error}`);
  }
}

export function startFeed(present, initialRead = beginRead()) {
  // A package-owned surface may hold replay while it is open. Its completion is a
  // projection invalidation, so retry the already applied reading immediately instead
  // of waiting for the clock's deferred-work heartbeat. The event is intentionally
  // generic: the state feed does not know which widget held the projection.
  let projectionQueued = false;
  const retryProjection = () => {
    if (projectionQueued) return;
    projectionQueued = true;
    // A close can precede the gesture's outbox entry in the same call stack.
    // Let that producer finish before replaying the resulting composition.
    queueMicrotask(() => {
      projectionQueued = false;
      if (!projectionDeferred()) return;
      void tick().catch((error) =>
        reportPageError(`tick failed: ${error?.message ?? error}`),
      );
    });
  };
  document.addEventListener("lf-projection", retryProjection);
  const readAndPresent = async () => {
    try {
      await readAndApply(initialRead);
      await present();
    } catch (error) {
      readAnswered = false;
      reportPageError(`read failed: ${error?.message ?? error}`);
      renderStatus(error);
    }
  };
  // What the page does when the stream says it has moved. Every wake-up is a read of
  // its own, and reads may overlap: one held by a slow proxy while the next answers
  // is the case receiveState orders by sequence, revision and stamp, and a gate that let
  // one read out at a time would have made a held read a held page. Application is
  // deliberately not awaited — see readState — and a fault applying one answer is
  // reported and does not stop the next from arriving. Presentation is chained onto
  // the application rather than onto the read, because it is a fact about applied
  // state: a page whose first answer did not present must still present on a later
  // one. An answer with nothing in it — an unreachable server, a refused key, a layer
  // that has moved on and is reloading — still presents, since the authored page under
  // an unreachable server is a page, and saying so is the banner's job.
  const ask = async () => {
    try {
      const state = await readState();
      if (state)
        void receiveState(state)
          .then(
            () => {
              readAnswered = true;
            },
            (error) => {
              readAnswered = false;
              reportPageError(`read failed: ${error?.message ?? error}`);
              renderStatus(error);
            },
          )
          // Presentation's own fault is reported as its own: the read behind it
          // stands, and the tick retries the presentation rather than the read.
          .then(present)
          .catch((error) => {
            reportPageError(`presentation failed: ${error?.message ?? error}`);
          });
      else {
        await readNothing();
        await present();
      }
    } catch (error) {
      readAnswered = false;
      reportPageError(`read failed: ${error?.message ?? error}`);
      renderStatus(error);
    }
  };
  // The page's ear: one stream, open for the page's life, on which the server names the
  // page's reading each time it changes, and again every five seconds whether or
  // not it did — nothing else rides it. State still comes by asking, so every reader
  // of a state request — in the page, or a test standing outside it with a route on
  // the request — keeps its meaning; the stream only says when asking is worth it.
  // The reading compared is the one the page has applied: a wake-up naming what the
  // page already shows, which a page's own POST response leaves it holding, is no
  // reason to ask. The repeated word is what makes the comparison safe to rest on: a
  // reading that reached the page some other way, or that the server's own memory of
  // this stream missed, differs from the next word here and is asked for then.
  //
  // The browser reopens a stream that drops. One the server refused — a key it no
  // longer honours, a server too old to have the door — is closed for good, and is
  // reopened from here at the spacing a failed read always had. Either way, whether
  // the server is there is put to a read, which is what the banner answers from: a
  // dropped stream is a prompt to ask, not a verdict. Coming back after a silence, the
  // page asks if its last read failed, since whatever it is showing about the server
  // is from before the silence.
  const listen = () => {
    const news = new EventSource("/api/news");
    let quiet;
    const alive = () => {
      clearTimeout(quiet);
      quiet = setTimeout(() => {
        news.close();
        listen();
      }, SILENCE_MS);
    };
    news.addEventListener("open", () => {
      alive();
      if (!readAnswered) void ask();
    });
    news.addEventListener("message", (event) => {
      alive();
      if (event.data !== runtime.reading) void ask();
    });
    news.addEventListener("error", () => {
      clearTimeout(quiet);
      if (news.readyState === EventSource.CLOSED) setTimeout(listen, RETRY_MS);
      void ask();
    });
  };
  // Presentation waits on the first read, and the ear opens after it: the page then
  // holds a reading for the stream's first word to be compared with, so an unchanged
  // page is not asked for twice.
  readAndPresent().finally(() => {
    // One shared clock serves temporal paint, deferred work, and failed reads.
    setInterval(() => {
      if (readAnswered && activityTransitionDue(runtime.state)) void ask();
      else if (readAnswered) void heartbeat();
      else void ask();
      // A presentation that failed is retried here as the poll retried it, since
      // a quiet page may see no read to chain it onto.
      void present();
    }, TICK_MS);
    listen();
  });
}

// How often the page refreshes display ages and checks the server-projected activity's
// next transition. The browser decides only when to ask; the returned projection decides
// what the agent is doing.
const TICK_MS = 2000;

// How long the outbox waits before re-sending, and how long the page waits before
// reopening a news stream the server refused. Both are the same "try again shortly",
// and neither is a cadence: a page with news gets it without waiting for either.
export const RETRY_MS = 2000;

// How long the news stream may say nothing before the page takes it for dead. The
// server speaks at least every five seconds, so half a minute of silence is a
// connection something between them has quietly lost — a proxy, a laptop that slept —
// which is the one failure the browser cannot see for itself and would otherwise wait
// on forever.
const SILENCE_MS = 30_000;
