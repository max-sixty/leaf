/* Prepare asynchronously, adopt one semantic root synchronously, then present it.

   Complete readings are ordered by transaction time, event sequence, and active
   revision. Preparation may overlap; the adoption boundary judges the candidate
   again and folds it with the latest local attempts. Accepted truth never rolls back
   when a view fails. Failed presentation reports visibly and leaves pending receipt
   accounting untouched, so another reading can retry from that same semantic root. */
import { LIVE_ROOT } from "./storage.js";
import { runtime } from "./context.js";
import { applicationState, readApplication } from "./semantic-state.js";
import { reportPageError, sameLayer } from "./layer-client.js";
import { importWidgets } from "./widget-loader.js";
import { observeServerNow } from "./presence.js";
import { settleAcceptedDrafts } from "./drafts.js";
import { notice } from "./notifications.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { loadMarked, prepareAuthoredMessage } from "./conversation/messages.js";
import { commitWidgetDescriptors } from "./widget-descriptors.js";

export function createStateApplication({
  prepareActivation,
  acceptData,
  notifyDataSubscribers,
  isSignoffDeclared,
  paintApproval,
  renderStatus,
  renderVersions,
  stateSignoff,
  renderOthers,
  applyConversation,
  renderAsks,
  prepareProjection,
  presentProjection,
  accountPending,
  panelIsOpen,
  paintKeys,
}) {
  let agentMsgCount = -1;
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
    if (activation?.stale) {
      await notifyChangedData();
      return;
    }

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
      let documentCapture = following !== null ? await activation.install() : null;
      if (frozenDocuments.length) {
        const prior = documentCapture ?? readApplication().document;
        const authored = new Map(prior.authored);
        const descriptors = new Map(prior.descriptors);
        for (const frozen of frozenDocuments) {
          for (const [id, baseline] of frozen.authored) authored.set(id, baseline);
          for (const [id, descriptor] of frozen.descriptors.descriptors)
            descriptors.set(id, descriptor);
        }
        documentCapture = { ...prior, authored, descriptors };
      }
      for (const frozen of frozenDocuments) commitWidgetDescriptors(frozen.descriptors);
      if (!applicationState.adopt(state, documentCapture)) {
        await notifyChangedData();
        return;
      }
      observeServerNow(state.now);
      stateApplying = true;
      // Hold chrome presentation while every renderer consumes the newly adopted
      // document and server reading as one semantic epoch.
      const preparedProjection = prepareProjection();
      try {
        settleAcceptedDrafts();
        renderStatus(state);
        renderVersions(state);
        stateSignoff(isSignoffDeclared());
        paintApproval();
        renderOthers(state);
        // Frozen thread widgets join the already-adopted document here; connection is
        // presentation only because their authored semantics were captured above.
        await applyConversation();
        presentProjection(preparedProjection);
        await applyConversation();
        // Present the already-derived Ask inventory before recording this accepted
        // reading on the document.
        await renderAsks();
        await notifyDataSubscribers();
        if (runtime.reading !== null)
          document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.reading, runtime.reading);
        accountPending(state.browser.receipts ?? []);
        const replies = runtime.browser.conversation.threads.flatMap((thread) =>
          thread.msgs.filter(
            (message) => message.author === "claude" && message.kind === "reply",
          ),
        );
        if (agentMsgCount >= 0 && replies.length > agentMsgCount && !panelIsOpen())
          notice(`${replies.at(-1).agent || "Agent"} replied — open Threads`, {
            background: true,
          });
        agentMsgCount = replies.length;
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
