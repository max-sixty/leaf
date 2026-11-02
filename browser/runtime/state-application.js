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
} from "./semantic-state.js";
import { reportCarried, sameLayer } from "./layer-client.js";
import { observeServerNow, observeWorkingGrace } from "./presence.js";
import { settleAcceptedDrafts } from "./drafts.js";
import { announce, notice } from "./notifications.js";
import { markStateApplied, settlePageInterface } from "./presentation.js";
import {
  loadMessageMarkdown,
  prepareAuthoredMessage,
  messageText,
} from "./thread/messages.js";
import { commitWidgetDescriptors } from "./widget-descriptors.js";
import {
  combineSemanticNews,
  currentSemanticNews,
  observeSemanticNews,
  semanticNewsNotice,
  semanticNewsReading,
} from "./semantic-news.js";

/** @param {{
 * prepareActivation: ReturnType<typeof import("./version.js").createVersionController>["prepareActivation"],
 * acceptData: typeof import("./data.js").acceptData,
 * notifyDataSubscribers: typeof import("./data.js").notifyDataSubscribers,
 * accountPending: (receipts: readonly import("../types/domain.js").Event[]) => void
 * }} dependencies */
export function createStateApplication({
  prepareActivation,
  acceptData,
  notifyDataSubscribers,
  accountPending,
}) {
  /** @type {{reading: import("./semantic-news.js").NewsReading, observed: import("./semantic-news.js").ObservedNews} | null} */
  let presentedNews = null;
  let stateApplying = false;
  let admission = Promise.resolve();

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

  /** @param {import("./layer-client.js").CompletedState} state */
  async function receiveState(state) {
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
    const messages = threads.flatMap((thread) =>
      thread.msgs.map((message) => ({
        message,
        preparation:
          "markup" in message && message.markup
            ? prepareAuthoredMessage(message, thread.id)
            : null,
      })),
    );
    const [activation, , frozenDocuments] = await Promise.all([
      prepareActivation(state),
      threads.length ? loadMessageMarkdown() : null,
      Promise.all(
        messages.map(async ({ message, preparation }) => ({
          message,
          frozen: await preparation,
        })),
      ),
    ]);
    const bodies = new Map(
      frozenDocuments.map(({ message, frozen }) => [
        message.id,
        frozen
          ? {
              ...frozen.body,
              text: [messageText(message), frozen.body.text].filter(Boolean).join("\n"),
            }
          : { text: messageText(message) },
      ]),
    );

    return runSerialized(async () => {
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
      let authored = prior.authored;
      let descriptors = prior.descriptors;
      for (const { frozen } of frozenDocuments) {
        if (!frozen) continue;
        for (const [id, baseline] of frozen.authored) {
          if (authored.has(id)) continue;
          if (authored === prior.authored) authored = new Map(authored);
          authored.set(id, baseline);
        }
        for (const [id, descriptor] of frozen.descriptors.descriptors) {
          if (descriptors.has(id)) continue;
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
      for (const { frozen } of frozenDocuments)
        if (frozen) commitWidgetDescriptors(frozen.descriptors);
      if (!applicationState.adopt(state, documentCapture)) {
        await notifyChangedData();
        return;
      }
      observeServerNow(state.now);
      observeWorkingGrace(state.working_grace_ms);
      stateApplying = true;
      try {
        settleAcceptedDrafts();
        // Optional interface preparation joins imports and installation, without
        // pretending to be a semantic renderer. Adoption already claimed every document
        // region for this epoch, and frozen
        // thread widgets joining the document reopen the ones they change. Waiting for
        // that proof is what replaces naming the renderers and the order they run in.
        if (installed) await settlePageInterface();
        await whenDocumentPresented();
        // Version-owned mechanical landing follows proof and reports its own failures;
        // it cannot turn accepted truth into a refusal or strand proved receipts.
        if (installed) await installed.land();
        await notifyDataSubscribers();
        markStateApplied(state);
        accountPending(state.browser.receipts);
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
        // The agent's new words are heard, not shown: the On me mark's dot and each
        // margin marker's already show unread news, so the seat keeps the agent's status.
        // The user chose this on 25 October over a line counting the messages.
        if (reading.news.length) announce(semanticNewsNotice(reading.news));
        const shown = reading.news.filter((item) => item.kind !== "agent_content");
        if (shown.length) {
          const current = presentedNews;
          /** @param {readonly import("./semantic-news.js").SemanticNews[]} value */
          const format = (value) => {
            return semanticNewsNotice(
              currentSemanticNews(value, current.reading, current.observed),
            );
          };
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

  return { isApplying: () => stateApplying, receiveState, runSerialized };
}
