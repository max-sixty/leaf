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
import { importWidgets } from "./widget-loader.js";
import { observeServerNow, observeWorkingGrace } from "./presence.js";
import { settleAcceptedDrafts } from "./drafts.js";
import { notice } from "./notifications.js";
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
import { renderVersions } from "./version.js";

export function createStateApplication({
  prepareActivation,
  acceptData,
  notifyDataSubscribers,
  isSignoffDeclared,
  renderStatus,
  stateSignoff,
  renderOthers,
  accountPending,
  paintKeys,
}) {
  let observedSemanticNews = null;
  let presentedNewsReading = null;
  const markupRead = new Set();
  let stateApplying = false;
  let admission = Promise.resolve();

  async function runSerialized(operation) {
    const prior = admission;
    const { promise, resolve: release } = Promise.withResolvers();
    admission = promise;
    await prior;
    try {
      return await operation();
    } finally {
      release();
    }
  }

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
    const threads = state.browser.views[state.active.revision].thread.threads;
    const frozenDocuments = [];
    const preparations = [
      prepareActivation(state),
      threads.length ? loadMessageMarkdown() : null,
    ];
    // The log retains withdrawn messages; only the current thread inventory owns
    // authored islands that this reading can prepare and publish.
    for (const thread of threads)
      for (const message of thread.msgs) {
        if (!message.markup) continue;
        const authored = prepareAuthoredMessage(message, thread.id);
        frozenDocuments.push(authored);
        if (markupRead.has(message.id)) continue;
        preparations.push(
          importWidgets(authored.root).then(() => markupRead.add(message.id)),
        );
      }
    const [activation] = await Promise.all(preparations);
    const bodies = new Map(
      threads.flatMap((thread) =>
        thread.msgs.map((message) => {
          const authored = message.markup
            ? prepareAuthoredMessage(message, thread.id).body
            : null;
          return [
            message.id,
            {
              ...(authored ?? {}),
              text: [messageText(message), authored?.text].filter(Boolean).join("\n"),
            },
          ];
        }),
      ),
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
      const installed = following !== null ? await activation.install() : null;
      const prior = installed?.document ?? readApplication().document;
      let authored = prior.authored;
      let descriptors = prior.descriptors;
      for (const frozen of frozenDocuments) {
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
      for (const frozen of frozenDocuments) commitWidgetDescriptors(frozen.descriptors);
      if (!applicationState.adopt(state, documentCapture)) {
        await notifyChangedData();
        return;
      }
      observeServerNow(state.now);
      observeWorkingGrace(state.working_grace_ms);
      stateApplying = true;
      try {
        settleAcceptedDrafts();
        renderStatus(state);
        renderVersions(state);
        stateSignoff(isSignoffDeclared());
        renderOthers(state);
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
        presentedNewsReading = semanticNewsReading(readApplication());
        const reading = observeSemanticNews(observedSemanticNews, presentedNewsReading);
        observedSemanticNews = reading.observed;
        if (reading.news.length) {
          const format = (value) =>
            semanticNewsNotice(
              currentSemanticNews(value, presentedNewsReading, observedSemanticNews),
            );
          notice(format(reading.news), {
            background: true,
            group: {
              key: "semantic-news",
              value: reading.news,
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
        paintKeys();
      }
    });
  }

  return { isApplying: () => stateApplying, receiveState, runSerialized };
}
