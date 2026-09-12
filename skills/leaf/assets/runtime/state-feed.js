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
import { containedPage, offlineInteractive, offlineState, runtime } from "./context.js";
import { applicationState } from "./semantic-state.js";
import {
  layerHeaders,
  observeSession,
  reportPageError,
  sameDelivery,
  sessionIsActive,
} from "./layer-client.js";
import { paintKeys } from "./keyboard/scopes.js";

// The answer, decoded, with nothing applied yet.
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
    if (offlineInteractive) return offlineState();
    const signal = globalThis.AbortSignal.timeout(bound);
    let res;
    try {
      const revision = runtime.currentRevision;
      res = await fetch("/api/state", {
        headers: layerHeaders({
          ...(Number.isInteger(revision) && {
            "Leaf-View-Revision": String(revision),
          }),
        }),
        // Coalescing bounds concurrency; this bounds its other dimension. A proxy that
        // never answers cannot own the page's single read slot forever.
        signal,
      });
    } catch {
      // Network absence is a completed answer: there is no log to replay, so the
      // offline authored page is honest. A successful but malformed response is
      // different — let JSON or processing errors escape so the caller retains the
      // recovery boundary.
      return null;
    }
    if (res) observeSession(res);
    if (res?.ok && !sameDelivery(res)) return null;
    // A refusal is not state: the server answers a missing key with error-shaped JSON
    // at 403. A live server refusing the key and a dead one both leave the page
    // unreachable from here, and the terminal link is the recourse for both.
    if (!res?.ok) return null;
    try {
      return await res.json();
    } catch (error) {
      if (signal.aborted) return null;
      throw error;
    }
  } finally {
    // Heard once the read has ended whichever way: the body in hand, or nothing.
    countTraffic("heard");
  }
}

// A read whose rejection is observed here rather than wherever it is finally awaited.
function buffer(bound) {
  return readState(bound).then(
    (state) => ({ state }),
    (error) => ({ error }),
  );
}

// Start the page's first read without leaving a rejection unobserved while widget
// startup continues. The result is still applied through readAndApply, at the boundary
// that has captured the upgraded authored state. A malformed answer therefore remains a
// startup fault; buffering changes when the network work runs, not what its answer
// means. This is the one read nothing is waiting on — presentation ends at its own wait
// — so it is the one that takes the long bound.
export function beginRead() {
  return buffer(FIRST_READ_TIMEOUT_MS);
}

// Failed reads retry on the clock: a news wake-up says that state changed, but
// cannot guarantee its read succeeded. Healthy pages ask only when news moves.
export function createStateFeed({
  projectionDeferred,
  retryProjection,
  stateApplying,
  releasePending,
  renderConversation,
  presentProjection,
  receiveState,
  prepareActivation,
  notifyDataSubscribers,
  renderStatus,
}) {
  let readAnswered = false;

  // The clock has no state to replay. Only an explicitly deferred projection needs
  // another attempt; time-dependent paints remember their own displayed readings.
  async function tick() {
    const retried = projectionDeferred() && retryProjection();
    if (stateApplying()) return;
    if (retried) {
      await releasePending();
      await notifyDataSubscribers();
    }
    if (stateApplying()) return;
    await tickClock(reportPageError);
    if (stateApplying()) return;
    document.dispatchEvent(new Event("lf-tick"));
  }

  // What the page does with an answer that brought no state.
  async function readNothing() {
    readAnswered = false;
    if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
    renderStatus(null);
    presentProjection();
    await renderConversation();
    await tick();
  }

  // A read and its application together, for the callers that want to be told when the
  // page has taken the answer in: the buffered first read, which presentation waits on
  // until its own deadline, and a version activation, which asks for the state it is
  // about to show. The activation opens its own read from a page a reader is already
  // using, so it takes an ordinary read's bound rather than the first read's.
  async function readAndApply(read = buffer(STATE_READ_TIMEOUT_MS)) {
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
    if (stateApplying()) return;
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

  function startFeed(present, initialRead = beginRead()) {
    // A package-owned surface may hold replay while it is open. Its completion is a
    // projection invalidation, so retry the already applied reading immediately instead
    // of waiting for the clock's deferred-work heartbeat. The event is intentionally
    // generic: the state feed does not know which widget held the projection.
    let projectionQueued = false;
    const retryProjection = () => {
      if (projectionQueued) return;
      projectionQueued = true;
      // A close can precede the gesture's pending ledger entry in the same call stack.
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
    // Presentation waits on the first read, but not on the container: the wait ends at
    // `PRESENTATION_WAIT_MS` whether or not an answer has come, and nothing is aborted
    // when it does. The request keeps its own, far longer bound and stays in flight, so a
    // container that is merely slow is never abandoned mid-answer, while one that accepts
    // the connection and says nothing cannot decide when the reader gets a page at all.
    // Past the wait the buffered read is an ordinary one: its answer applies and repaints
    // through the same path any later read's does, and a malformed one is reported the
    // same way rather than withholding a page the reader is already using.
    const readAndPresent = async () => {
      let outcome = "waiting";
      let waited = null;
      const wait = new Promise((resolve) => {
        waited = setTimeout(resolve, PRESENTATION_WAIT_MS);
      });
      // The buffered read holds the page's one read slot until it settles — see `reading`
      // below — so the clock this feed installs asks again after it rather than beside it.
      const settled = (async () => {
        try {
          await readAndApply(initialRead);
          outcome = "applied";
        } catch (error) {
          outcome = "failed";
          readAnswered = false;
          reportPageError(`read failed: ${error?.message ?? error}`);
          renderStatus(error);
        }
      })().finally(() => {
        clearTimeout(waited);
        reading = false;
        if (!readQueued) return;
        readQueued = false;
        ask();
      });
      await Promise.race([settled, wait]);
      // An answer that arrived and could not be applied is a startup fault: the authored
      // document stays readable under the named error and the presented stamp is withheld.
      if (outcome === "failed") return;
      try {
        // The wait ran out first, so the page has no state to show and says so, exactly as
        // it does for an answer that brought none.
        if (outcome === "waiting") await readNothing();
        await present();
      } catch (error) {
        readAnswered = false;
        reportPageError(`read failed: ${error?.message ?? error}`);
        renderStatus(error);
      }
    };
    // What the page does when the stream says it has moved. State application remains
    // independent — see readState — but the network side admits only one read at a time.
    // status.json can move several times while a container is still answering the first
    // read; those wake-ups mean "read again afterwards", not "open another socket". One
    // trailing read therefore absorbs the whole burst and keeps reads from queueing behind
    // the page transaction they are trying to observe.
    //
    // Presentation is chained onto application because it is a fact about applied state:
    // a page whose first answer did not present must still present on a later one. An
    // answer with nothing in it — an unreachable server, a refused key, a layer that has
    // moved on and is reloading — still presents, since the authored page under an
    // unreachable server is a page, and saying so is the banner's job.
    // The buffered first read is already out, so the slot starts held: a tick or a stream
    // word arriving while it is still unanswered queues a trailing read behind it instead
    // of opening a second one alongside.
    let reading = true;
    let readQueued = false;
    const askOnce = async () => {
      try {
        const state = await readState(STATE_READ_TIMEOUT_MS);
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
          void readNothing()
            .then(present)
            .catch((error) => {
              readAnswered = false;
              reportPageError(`read failed: ${error?.message ?? error}`);
              renderStatus(error);
            });
        }
      } catch (error) {
        readAnswered = false;
        reportPageError(`read failed: ${error?.message ?? error}`);
        renderStatus(error);
      }
    };
    const ask = () => {
      if (reading) {
        readQueued = true;
        return;
      }
      reading = true;
      void askOnce().finally(() => {
        reading = false;
        if (!readQueued) return;
        readQueued = false;
        ask();
      });
    };
    // The page's ear: one stream per visible interval, on which the server names the
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
    // A visible tab is the reader lease for its server-side page. The stream itself is
    // that lease: while any tab for a browser session is visible, at least one incoming
    // request keeps its shared container active. Hidden tabs close their streams, so the
    // container's ordinary idle timeout begins after the last visible tab leaves without
    // trusting an unload signal the browser may never deliver.
    //
    // Visibility, rather than `window.focus`, is the boundary. A page remains useful in
    // split-screen or while its developer tools have focus, and the platform aggregates
    // multiple tabs naturally: each tab owns only its own stream.
    const pageIsVisible = () => document.visibilityState !== "hidden";
    let feedStarted = false;
    let news = null;
    let quiet = null;
    let reopen = null;
    const stopListening = () => {
      clearTimeout(quiet);
      clearTimeout(reopen);
      quiet = null;
      reopen = null;
      const openNews = news;
      news = null;
      openNews?.close();
    };
    const listen = () => {
      if (!feedStarted || !pageIsVisible() || !sessionIsActive() || news) return;
      const opened = new EventSource("/api/news");
      news = opened;
      const alive = () => {
        if (news !== opened || !pageIsVisible()) return;
        clearTimeout(quiet);
        quiet = setTimeout(() => {
          if (news !== opened || !pageIsVisible()) return;
          stopListening();
          listen();
        }, SILENCE_MS);
      };
      opened.addEventListener("open", () => {
        alive();
        if (!readAnswered) void ask();
      });
      opened.addEventListener("message", (event) => {
        alive();
        if (event.data !== runtime.reading) void ask();
      });
      opened.addEventListener("error", () => {
        if (news !== opened) return;
        clearTimeout(quiet);
        quiet = null;
        if (!pageIsVisible()) {
          stopListening();
          return;
        }
        if (opened.readyState === EventSource.CLOSED) {
          news = null;
          reopen = setTimeout(() => {
            reopen = null;
            listen();
          }, RETRY_MS);
        }
        void ask();
      });
    };
    document.addEventListener("visibilitychange", () => {
      if (pageIsVisible()) listen();
      else stopListening();
    });
    document.addEventListener("lf-session-active", listen);
    // The ear opens once the page has presented, not once the container has answered: a
    // page whose first read is still out has nothing for the stream's first word to be
    // compared with, so that word asks — which is what the slot the read still holds is
    // for. A page that did get its answer holds a reading, and an unchanged page is not
    // asked for twice.
    const initialPresentation = readAndPresent();
    if (offlineInteractive) return;
    initialPresentation.finally(() => {
      // A contained page is a fixed specimen controlled by its parent gallery. It needs
      // the first reading to render production chrome, but another news stream and
      // heartbeat would duplicate the outer page's connection for a picture that cannot
      // accept reader input or durable updates.
      if (containedPage) {
        const retry = () => {
          if (document.body.hasAttribute("data-lf-presented")) return;
          if (!readAnswered) void ask();
          else void present();
          setTimeout(retry, TICK_MS);
        };
        retry();
        return;
      }
      feedStarted = true;
      // One shared clock serves temporal paint, deferred work, and failed reads.
      setInterval(() => {
        if (!pageIsVisible()) return;
        if (readAnswered && sessionIsActive() && activityTransitionDue(runtime.state))
          void ask();
        else if (readAnswered) void heartbeat();
        else void ask();
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

// How long the page waits before reopening a news stream the server refused.
// This is a retry delay, not a polling cadence; an open stream delivers news immediately.
export const RETRY_MS = 2000;

// How long the news stream may say nothing before the page takes it for dead. The
// server speaks at least every five seconds, so half a minute of silence is a
// connection something between them has quietly lost — a proxy, a laptop that slept —
// which is the one failure the browser cannot see for itself and would otherwise wait
// on forever.
const SILENCE_MS = 30_000;

// How long the page waits on its first read before presenting without one. Presentation
// is the reader's page arriving, so this is the only bound a reader feels, and it is set
// where waiting longer stops being worth an unflashed banner: outside the readings a
// working container takes — a container that has just run a hosted agent turn was
// measured answering in 2.3-3.9 s — and inside the patience anyone has for a page. What
// running out costs is a banner that corrects itself, because the read it stopped
// waiting on is still coming.
const PRESENTATION_WAIT_MS = 10_000;

// How long the first read may take before the page gives up on it. Nothing waits on this
// one — the wait above presents without it — so the bound frees the page's one read slot
// rather than deciding when the page arrives, and is set outside what any live container
// takes rather than inside it: the deploy gate gives every read of a container running a
// hosted turn a 120-second revision wait after presentation. This read starts before
// that wait, so abandoning it sooner would abort an answer while the gate is still
// waiting; at this bound the gate observes the resulting offline state. A proxy that
// accepts the connection and never answers is therefore still bounded here.
const FIRST_READ_TIMEOUT_MS = 120_000;

// How long every read after that may take. These have no wait beside them, and the
// banner's one honesty mechanism about the server runs through a read that *completed*
// with nothing: `renderStatus(null)` is the only path to OFFLINE_LINE, and a read still
// in flight holds the slot, so a stream word or a clock tick only queues a trailing read
// behind it. This bound is therefore the whole time a reader watching a live page can be
// shown a reading the server has stopped standing behind, which is a reader's timescale
// rather than the gate's. On expiry readState produces the same offline answer as any
// lost request, and the shared retry clock asks again.
const STATE_READ_TIMEOUT_MS = 10_000;
