/* Prepare asynchronously, adopt one semantic root synchronously, then wait for the page
   to show it.

   Complete readings are ordered by transaction time, event sequence, and active
   revision. Preparation may overlap; the adoption boundary judges the candidate
   again and folds it with the latest local attempts. Adoption is also where every
   document region claims this epoch, so what remains here is to wait for their proof
   rather than to name renderers or order them. Accepted truth never rolls back when a
   view fails. Failed presentation reports visibly and leaves pending receipt accounting
   untouched, so another reading can retry from that same semantic root. A revision's
   install returns only its immutable document capture and a mechanical landing. After
   adoption, optional interface installation and the canonical document proof both
   finish before that landing; declining stale focus never retracts accepted truth. */
import {
  applicationState,
  whenDocumentPresented,
  readApplication,
} from "../state/semantic-state.js";
import { runtime } from "../state/context.js";
import { reportCarried, sameLayer } from "../transport/layer-client.js";
import { afterOwedFrame } from "../base/rendering.js";
import { countTraffic } from "../transport/traffic.js";
import { holdUserPlace } from "../readings/user-place.js";
import { observeServerNow, observeWorkingGrace } from "../state/presence.js";
import { announce, gesture, notice } from "../transport/notifications.js";
import { markStateApplied, settlePageInterface } from "../readings/presentation.js";
import {
  loadMessageMarkdown,
  islandChange,
  prepareAuthoredMessage,
  messageText,
} from "../records/thread/messages.js";
import { keptEach } from "../state/kept.js";
import {
  combineSemanticNews,
  currentSemanticNews,
  newsMoment,
  observeSemanticNews,
  semanticNewsNotice,
  semanticNewsReading,
} from "./semantic-news.js";

/** @typedef {import("../state/thread/model.js").CapturedBody} CapturedBody */
// Each message's captured words, kept while they read the same (state/kept.js): an authored
// message's are its island's, and any other's its words as a label reads them. A
// thread's are kept together while its messages' are, so its record stands while its
// messages do (state/thread/model.js, `readThreadRecords`).
const plainBody = keptEach(
  /** @param {object} _message @param {string} text @returns {CapturedBody} */
  (_message, text) => ({ text }),
);
const threadBodies = keptEach(
  /** @param {{msgs: readonly {id: string}[]}} thread @param {CapturedBody[]} bodies */
  (thread, ...bodies) =>
    new Map(thread.msgs.map((message, at) => [message.id, bodies[at]])),
);

/** @param {{
 * prepareActivation: ReturnType<typeof import("../features/version.js").createVersionController>["prepareActivation"],
 * acceptData: typeof import("./data.js").acceptData,
 * notifyDataSubscribers: typeof import("./data.js").notifyDataSubscribers,
 * accountPending: (events: readonly import("../../types/domain.js").Event[]) => void
 * }} dependencies */
export function createStateApplication({
  prepareActivation,
  acceptData,
  notifyDataSubscribers,
  accountPending,
}) {
  /** @typedef {{reading: import("./semantic-news.js").NewsReading, observed: import("./semantic-news.js").ObservedNews}} PresentedNews */
  /** @type {PresentedNews | null} */
  let presentedNews = null;
  // What a queued news notice says when it shows, against the latest presented reading.
  // Made here, not in `receiveState`, whose scope holds the activation and the document
  // it replaced: a notice waiting its turn would keep both alive.
  /** @param {PresentedNews} current */
  const newsFormat =
    (current) =>
    /** @param {readonly import("../../types/domain.js").SemanticNews[]} value */
    (value) =>
      semanticNewsNotice(currentSemanticNews(value, current.reading, current.observed));
  let stateApplying = false;
  let admission = Promise.resolve();
  // Every answer handed in through any door, a state read or a gesture's POST, while
  // it is still being prepared or applied. Until one is adopted or dropped,
  // `runtime.state` is the state before it, so whoever asks what the page already
  // has asks `stateInHand`.
  /** @type {Set<import("../transport/layer-client.js").CompletedState>} */
  const inHand = new Set();

  /** @template T @param {() => T | Promise<T>} operation */
  async function runSerialized(operation) {
    const prior = admission;
    /** @type {PromiseWithResolvers<void>} */
    const { promise, resolve: release } = Promise.withResolvers();
    admission = promise;
    await prior;
    try {
      return await operation();
    } finally {
      release();
    }
  }

  /** @param {import("../transport/layer-client.js").CompletedState} state */
  async function receiveState(state) {
    inHand.add(state);
    countTraffic("received");
    try {
      return await applyState(state);
    } finally {
      inHand.delete(state);
      countTraffic("applied");
    }
  }

  // The newest state, by when the server took it, of those the page has adopted or
  // has in hand.
  function stateInHand() {
    let newest = runtime.state;
    for (const state of inHand)
      if (!newest || state.taken > newest.taken) newest = state;
    return newest;
  }

  /** @param {import("../transport/layer-client.js").CompletedState} state */
  async function applyState(state) {
    if (!sameLayer(state.layer.generation)) return;
    // Data is ordered by when the server took the reading, even in a crossed older log read.
    const dataChanged = acceptData(state.data, state.taken);
    const notifyChangedData = () => (dataChanged ? notifyDataSubscribers() : undefined);
    if (applicationState.overtaken(state)) {
      await notifyChangedData();
      return;
    }

    // Every view holds the same messages, read under its own registry; the active
    // one is always served.
    const activeView = state.browser.views[state.active.revision];
    if (!activeView)
      throw new Error(`State has no view for active revision ${state.active.revision}`);
    const threads = activeView.thread.threads;
    // An agent's message holding HTML renders once, from the loaded renderer.
    const markdown = threads.length ? loadMessageMarkdown() : null;
    const messages = threads.flatMap((thread) =>
      thread.msgs.map((message) => ({
        message,
        preparation:
          "html" in message && message.html
            ? markdown?.then(() => prepareAuthoredMessage(message, thread.id))
            : null,
      })),
    );
    const [activation, , preparedMessages] = await Promise.all([
      prepareActivation(state),
      markdown,
      Promise.all(
        messages.map(async ({ message, preparation }) => ({
          message,
          prepared: await preparation,
        })),
      ),
    ]);
    const preparedFor = new Map(
      preparedMessages.map(({ message, prepared }) => [message, prepared]),
    );
    const bodies = new Map(
      threads.map((thread) => [
        thread.id,
        threadBodies(
          thread,
          ...thread.msgs.map((message) => {
            const prepared = preparedFor.get(message);
            return prepared ? prepared.body : plainBody(message, messageText(message));
          }),
        ),
      ]),
    );

    return runSerialized(async () => {
      // A reading that arrives while a gesture of the user's is unresolved, before the
      // frame painting what the gesture drew, waits for that frame, so the gesture's own
      // result paints before the reading's work (base/rendering.js, `afterOwedFrame`). With no
      // gesture in flight, as while the page loads, nothing on screen is owed first.
      if (readApplication().unresolved.length) await afterOwedFrame();
      // Pending deferral is rechecked by activates. An installation edits the user's
      // document and there is no putting it back, so the answer that would follow it is
      // judged first, against the revision the install would leave showing. A candidate
      // that could not be adopted, overtaken by a newer reading included, is dropped
      // here, with the page still whole.
      const following = activation?.activates() ? activation.revision : null;
      if (!applicationState.canAdopt(state, following)) {
        await notifyChangedData();
        return;
      }
      // A reload never returns to install this candidate in the old realm. A patch
      // does, and adoption is where the revision it installed becomes current, so the
      // document and the state that speaks for it reach the page in one reading.
      const installed =
        following !== null && activation ? await activation.install() : null;
      const prior = installed?.document ?? readApplication().document;
      // Each message's widgets as this reading's wording authors them: an edit's
      // island replaces what the wording before it captured, and the ids that wording
      // held and this one doesn't leave (messages.js, `islandChange`).
      const islands = islandChange(preparedMessages);
      let authored = prior.authored;
      let descriptors = prior.descriptors;
      for (const id of islands.retired) {
        if (!authored.has(id) && !descriptors.has(id)) continue;
        if (authored === prior.authored) authored = new Map(authored);
        if (descriptors === prior.descriptors) descriptors = new Map(descriptors);
        authored.delete(id);
        descriptors.delete(id);
      }
      for (const { prepared } of preparedMessages) {
        if (!prepared) continue;
        for (const [id, baseline] of prepared.authored) {
          if (authored.get(id) === baseline) continue;
          if (authored === prior.authored) authored = new Map(authored);
          authored.set(id, baseline);
        }
        for (const [id, descriptor] of prepared.descriptors.descriptors) {
          if (descriptors.get(id) === descriptor) continue;
          if (descriptors === prior.descriptors) descriptors = new Map(descriptors);
          descriptors.set(id, descriptor);
        }
      }
      const documentCapture = {
        ...prior,
        authored,
        descriptors,
        messageBodies: bodies,
      };
      // The user's place across the change this reading brings, kept once the page
      // shows it (readings/user-place.js, `holdUserPlace`). A revision places the reader with its
      // own landing instead (features/version.js).
      const keepPlace = installed ? null : holdUserPlace();
      if (!applicationState.adopt(state, documentCapture)) {
        await notifyChangedData();
        return;
      }
      islands.commit();
      observeServerNow(state.now);
      observeWorkingGrace(state.working_grace_ms);
      stateApplying = true;
      try {
        // Optional interface preparation joins imports and installation, without
        // pretending to be a semantic renderer. Adoption already claimed every document
        // region for this epoch, and thread widgets joining the document reopen the
        // ones they change. Waiting for that proof is what replaces naming the renderers
        // and the order they run in.
        if (installed) await settlePageInterface();
        await whenDocumentPresented();
        // Version-owned mechanical landing follows proof and reports its own failures;
        // it cannot turn accepted truth into a refusal or strand proved receipts.
        if (installed) await installed.land();
        await notifyDataSubscribers();
        // A widget's paint from its new data can claim other regions, as a diff that
        // drops a commented line sends its thread to a margin card, and the place is
        // kept only once those have drawn too.
        await whenDocumentPresented();
        keepPlace?.();
        markStateApplied(state);
        accountPending(state.events);
        // Only the accepted candidate that this full document just presented can
        // establish news. A queued notice formats against the latest such reading,
        // so a later answer does not repeat a superseded failure or edit.
        const newsReading = semanticNewsReading(readApplication());
        const reading = observeSemanticNews(
          presentedNews?.observed ?? null,
          newsReading,
        );
        if (presentedNews) {
          presentedNews.reading = newsReading;
          presentedNews.observed = reading.observed;
        } else presentedNews = { reading: newsReading, observed: reading.observed };
        // The agent's new words are heard, not shown: the leaf's dot and each
        // margin marker's already show unread news, so the seat keeps the agent's status.
        // The user chose this over a line counting the messages.
        if (reading.news.length) announce(semanticNewsNotice(reading.news));
        // The leaf answers news as it arrives, with the badge and dots, rather than when
        // a notice held behind the user's own command shows it.
        const moment = newsMoment(reading.news);
        if (moment) gesture(moment);
        const shown = reading.news.filter((item) => item.kind !== "agent_content");
        if (shown.length) {
          const format = newsFormat(presentedNews);
          notice(format(shown), {
            background: true,
            announce: false,
            group: {
              key: "semantic-news",
              value: shown,
              combine: combineSemanticNews,
              format,
            },
          });
        }
      } catch (error) {
        reportCarried(error, `State presentation failed`);
        throw error;
      } finally {
        stateApplying = false;
      }
    });
  }

  return {
    isApplying: () => stateApplying,
    stateInHand,
    receiveState,
    runSerialized,
  };
}
