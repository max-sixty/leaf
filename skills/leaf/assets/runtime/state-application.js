/* Prepare asynchronously, adopt one semantic root synchronously, then wait for the page
   to show it.

   Complete readings are ordered by transaction time, event sequence, and active
   revision. Preparation may overlap; the adoption boundary judges the candidate
   again and folds it with the latest local attempts. Adoption is also where every
   document region claims this epoch, so what remains here is to wait for their proof
   rather than to name renderers or order them. Accepted truth never rolls back when a
   view fails. Failed presentation reports visibly and leaves pending receipt accounting
   untouched, so another reading can retry from that same semantic root. */
import { LIVE_ROOT } from "./storage.js";
import { runtime } from "./context.js";
import {
  applicationState,
  whenDocumentPresented,
  readApplication,
} from "./semantic-state.js";
import { reportPageError, sameLayer } from "./layer-client.js";
import { importWidgets } from "./widget-loader.js";
import { observeServerNow } from "./presence.js";
import { settleAcceptedDrafts } from "./drafts.js";
import { notice } from "./notifications.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import {
  loadMarked,
  prepareAuthoredMessage,
  messageText,
} from "./conversation/messages.js";
import { commitWidgetDescriptors } from "./widget-descriptors.js";
import {
  combineSemanticNews,
  currentSemanticNews,
  observeSemanticNews,
  semanticNewsNotice,
  semanticNewsReading,
} from "./semantic-news.js";

export function createStateApplication({
  prepareActivation,
  acceptData,
  notifyDataSubscribers,
  isSignoffDeclared,
  renderStatus,
  renderVersions,
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
    let release;
    admission = new Promise((resolve) => {
      release = resolve;
    });
    await prior;
    try {
      return await operation();
    } finally {
      release();
    }
  }

  const stale = (state) =>
    runtime.state !== null &&
    (state.taken < runtime.state.taken ||
      state.browser.basis.through_seq < runtime.lastEventSeq ||
      state.active.revision < runtime.active.revision);

  async function receiveState(state) {
    if (!sameLayer(state.layer.generation)) return;
    if (typeof state.taken !== "number")
      throw new TypeError("state must say when it was taken");
    // Source revisions are independently monotone, even in a crossed older log read.
    const dataChanged = acceptData(state.data);
    const notifyChangedData = () => (dataChanged ? notifyDataSubscribers() : undefined);
    const eventSeq = state.browser?.basis?.through_seq;
    if (!Number.isInteger(eventSeq) || eventSeq < 0)
      throw new TypeError("state browser must name its log sequence");
    const targetRevision = state.active?.revision;
    if (!Number.isInteger(targetRevision) || targetRevision < 1)
      throw new TypeError("state active must name a positive revision");
    if (LIVE_ROOT && runtime.currentRevision === null)
      throw new TypeError("the live document has no lf-revision marker");
    if (stale(state)) {
      await notifyChangedData();
      return;
    }

    const frozenDocuments = [];
    const threadRoots = new Map(
      (state.browser.conversation.threads ?? []).flatMap((thread) =>
        thread.msgs.map((message) => [message.id, thread.root.id]),
      ),
    );
    const preparations = [
      prepareActivation(state),
      state.events.some((event) => event.kind === "comment" || event.kind === "reply")
        ? loadMarked()
        : null,
    ];
    for (const event of state.events) {
      if (!event.markup) continue;
      const authored = prepareAuthoredMessage(event, threadRoots.get(event.id));
      frozenDocuments.push(authored);
      if (markupRead.has(event.id)) continue;
      preparations.push(
        importWidgets(authored.root).then(() => markupRead.add(event.id)),
      );
    }
    const [activation] = await Promise.all(preparations);
    const bodies = new Map(
      state.browser.conversation.threads.flatMap((thread) =>
        thread.msgs.map((message) => {
          const authored = message.markup
            ? prepareAuthoredMessage(message, thread.root.id).body
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
      if (stale(state)) {
        await notifyChangedData();
        return;
      }
      // Pending deferral is rechecked by activates. An installation edits the reader's
      // document and there is no putting it back, so the answer that would follow it is
      // judged first, against the revision the install would leave showing. A candidate
      // that could not be adopted is dropped here, with the page still whole.
      const following = activation?.activates() ? activation.revision : null;
      if (!applicationState.canAdopt(state, following)) {
        await notifyChangedData();
        return;
      }
      // A reload never returns to install this candidate in the old realm. A patch
      // does, and adoption is where the revision it installed becomes current, so the
      // document and the state that speaks for it reach the page in one reading.
      const installed = following !== null ? await activation.install() : null;
      const prior = installed ?? readApplication().document;
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
      stateApplying = true;
      try {
        settleAcceptedDrafts();
        renderStatus(state);
        renderVersions(state);
        stateSignoff(isSignoffDeclared());
        renderOthers(state);
        // Adoption already claimed every document region for this epoch, and frozen
        // thread widgets joining the document reopen the ones they change. Waiting for
        // that proof is what replaces naming the renderers and the order they run in.
        await whenDocumentPresented();
        await notifyDataSubscribers();
        if (runtime.reading !== null)
          document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.reading, runtime.reading);
        accountPending(state.browser.receipts ?? []);
        // Only the accepted candidate that this full document just presented can
        // establish news. A queued notice formats against the latest such reading,
        // so a later answer does not repeat a superseded failure or edit.
        presentedNewsReading = semanticNewsReading(state);
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
        reportPageError(`State presentation failed: ${error?.message ?? error}`);
        throw error;
      } finally {
        stateApplying = false;
        paintKeys();
      }
    });
  }

  return { isApplying: () => stateApplying, receiveState, runSerialized };
}
