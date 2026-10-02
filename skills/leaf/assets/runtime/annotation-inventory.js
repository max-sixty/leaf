/* The current annotation inventory, independent of its page presentation.

   This owner projects the application's published Threads, Asks, provenance and
   workflows together with producer-declared contributions. Frozen readings contain
   no browser capability. Current target/point nodes and generated action capabilities
   stay in this directory; contributed actions resolve through their registration.
   No renderer folds events or owns a second target inventory. The Thread coordinator
   refreshes after current widget claims and required conversation commits. Mechanical
   paints and immediate contribution updates refresh this same directory. */
import { replyHasWords } from "./thread/replies.js";
import { KINDS, excerptWords, labelWords } from "./contribution-model.js";
import { contributionEntries } from "./contributions.js";
import { marginInventory } from "./margin-model.js";
import { standingPoint } from "./pointed-place.js";
import { ago } from "./presence.js";
import { runtime } from "./context.js";
import { elementById, inChrome } from "./passages.js";
import { addressableLabel, addressableWord } from "./anchor-resolution.js";
import { updateSequence } from "./updates.js";
import { threadList } from "./thread/state.js";
import { threadKey } from "./thread/model.js";
import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { claimed, heldOut } from "./thread/surfaces.js";
import { anchorLabel } from "./thread/messages.js";
import { outlineSubjectFor, pageOutline } from "./thread/placement.js";
import {
  isLiveWorkflow,
  isPageWidgetWorkflow,
  isWorkflowProgress,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "./thread/workflow.js";
import { renderedParent, shadowHost } from "./shadow.js";
import { scrollBehavior } from "./motion.js";

export function createAnnotationInventory({
  openAsks,
  comparisonBase,
  comparisonChanges,
  inlineComparison,
  toggleInlineComparison,
  placedAt,
  showThread,
  goToAsk,
  scrollToElement,
}) {
  const humanized = (value) =>
    String(value ?? "")
      .replace(/[-_]+/g, " ")
      .trim();

  function targetPath(target) {
    const host = shadowHost(target.getRootNode());
    // IDs and sibling paths are scoped to a shadow root. Prefix them with the host's
    // own stable path so two instances of the same shadow template stay distinct,
    // while a live-version replacement at the same authored coordinate can still
    // retain its marker and preview focus.
    const prefix = host ? `${targetPath(host)}/shadow/` : "";
    if (target.id) return `${prefix}id:${target.id}`;
    const steps = [];
    let from = "path:";
    for (let node = target; node;) {
      // A projected datum's node is generated, so it stands at no authored position
      // among its siblings; it is named by its projection and key, which also survive a
      // renderer replacing it (projection/data.js).
      if (node.dataset?.lfProjection && node.hasAttribute("data-lf-datum")) {
        from = `datum:${node.dataset.lfProjection}/${node.dataset.lfDatum}:`;
        break;
      }
      const parent =
        node.parentElement ??
        (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
      if (!parent) break;
      const siblings = [...parent.children].filter(
        (candidate) =>
          !candidate.classList.contains("lf-ui") &&
          !candidate.hasAttribute("data-lf-gen"),
      );
      steps.push(`${node.localName}:${siblings.indexOf(node)}`);
      if (node.localName === "main" || parent instanceof ShadowRoot) break;
      node = parent;
    }
    return `${prefix}${from}${steps.reverse().join("/")}`;
  }

  function comesBefore(left, right) {
    if (left === right) return 0;
    if (!left) return 1;
    if (!right) return -1;
    // compareDocumentPosition calls nodes in separate shadow trees disconnected and
    // leaves their order implementation-specific. Build each composed ancestry instead:
    // the first divergent nodes share a document or shadow root and therefore have a
    // stable order. Keeping every inner step also distinguishes a target in an outer
    // tree from a later target inside one of its nested shadow hosts.
    const ancestry = (target) => {
      const chain = [];
      for (let node = target; node;) {
        chain.push(node);
        node = renderedParent(node);
      }
      return chain.reverse();
    };
    const leftChain = ancestry(left);
    const rightChain = ancestry(right);
    let index = 0;
    while (
      index < leftChain.length &&
      index < rightChain.length &&
      leftChain[index] === rightChain[index]
    )
      index += 1;
    if (index === leftChain.length || index === rightChain.length)
      return leftChain.length - rightChain.length;
    return leftChain[index].compareDocumentPosition(rightChain[index]) &
      Node.DOCUMENT_POSITION_FOLLOWING
      ? -1
      : 1;
  }

  // Targets and generated-reading callbacks stay outside the model. Registered
  // contributions already publish their own immutable model readings.
  const targets = new Map();
  const itemSources = new WeakMap();
  const targetFor = (entry) => (entry ? (targets.get(entry.key) ?? null) : null);
  // The row a pointed entry stands by (groupFor), as anchor paint last placed it, while
  // it still stands inside its target. Where the entry stands (`entryPlace`) is that
  // row, else the target: every reading of where an entry is on the page, as against
  // what it is about, asks this.
  const points = new Map();
  const entryPoint = (entry) =>
    entry ? standingPoint(targetFor(entry), points.get(entry.key)) : null;
  const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
  // A pointed row is named by its words as the page reads them, cells and blocks apart.
  const pointName = (words) => {
    const excerpt = words && excerptWords(words, 32);
    return excerpt ? `“${excerpt}”` : null;
  };
  const sourceItem = (item) => itemSources.get(item);
  function captureItem(item) {
    const { activate, discloses, thread, ...data } = item;
    const snapshot = Object.freeze({
      ...data,
      carriesWorkflow: Boolean(workflowReceipt([item])),
    });
    itemSources.set(snapshot, { activate, discloses, thread });
    return snapshot;
  }

  const workflows = () => runtime.workflows;
  // Selected from the published workflows rather than gathered from the items, whose
  // order is the margin's, so the strongest is the server's.
  const workflowReceipt = (items) => {
    const receipts = new Set(items.map((item) => item.workflowReceipt?.id));
    return strongestWorkflow(
      workflows().filter(
        (workflow) => receipts.has(workflow.id) && isWorkflowProgress(workflow),
      ),
    );
  };
  // One group per target, and one more for each row inside it that pointing gestures
  // stood threads at (pointed-place.js): those threads stand there together, and
  // everything else about the target (its other threads, an Ask's marker, a widget's
  // actions) keeps the target's own row. `pointed` is `{ key, element, words }`: the
  // row's key, which its first comment gave it and later ones share, the element it is,
  // and its words as the page reads them, which name it.
  function groupFor(groups, target, pointed = null) {
    const slot = pointed ? `point:${pointed.key}` : target;
    let group = groups.get(slot);
    if (!group) {
      const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
      const word = addressableWord(target);
      group = {
        key,
        target,
        point: pointed?.element ?? null,
        pointWords: pointed?.words ?? null,
        word,
        subject: null,
        title: null,
        items: [],
        offers: [],
      };
      groups.set(slot, group);
    }
    return group;
  }

  function add(groups, target, item, pointed = null) {
    if (!target?.isConnected || inChrome(target)) return;
    const group = groupFor(groups, target, pointed);
    group.items.push(item);
  }

  function visibleWidgetWorkflows() {
    return workflows().filter((workflow) =>
      isPageWidgetWorkflow(workflow, runtime.currentRevision),
    );
  }

  // A receipt's face is its category's icon and rank under the receipt's own label,
  // so one reading of a receipt never names a different stage than its text does.
  function agentWorkflowFace(receipt) {
    if (!receipt) return null;
    const label = workflowLabel(receipt);
    if (!label) return null;
    return {
      kind:
        receipt.next_actor === "user" || receipt.condition
          ? "waiting"
          : ["working", "replying"].includes(receipt.stage)
            ? "activity"
            : receipt.stage === "picked_up"
              ? "pickup"
              : receipt.stage === "queued"
                ? "queued"
                : "sent",
      text: label,
      context: [receipt.ts ? ago(receipt.ts) : "", receipt.detail]
        .filter(Boolean)
        .join(" · "),
    };
  }

  const marginThreadItem = (thread) => (thread ? `comment:${threadKey(thread)}` : null);

  let entries = Object.freeze([]);

  function collectEntries() {
    const groups = new Map();
    const receiptByCoordinate = new Map();
    for (const receipt of visibleWidgetWorkflows()) {
      receiptByCoordinate.set(JSON.stringify(receipt.coordinate), receipt);
    }
    const representedThreads = new Set();
    for (const thread of threadList()) {
      // A settled thread keeps its marker while the user has words for it, or while a
      // widget holds it out of its flow behind that marker (thread/held-news.js).
      const kept = replyHasWords(threadKey(thread)) || heldOut(thread.id);
      if ((thread.resolved && !kept) || !thread.anchor || claimed(thread.id)) continue;
      const id = thread.id;
      const target = placedAt(id)?.element;
      if (target?.isConnected && !inChrome(target)) representedThreads.add(id);
      const attention = threadAttention(thread);
      const onUser = attention?.kind === "needs_user";
      const unread = thread.unread.length;
      const placement = placedAt(id);
      const point = standingPoint(target, placement?.point);
      const pointed = point
        ? { key: placement.pointRow, element: point, words: placement.pointWords }
        : null;
      add(
        groups,
        target,
        {
          kind: "comment",
          // One row for one thread, across the log answering for it. A thread the
          // user just opened is known by its attempt until the log names it, and a row
          // whose identity changed there would be rebuilt — taking with it the reply box
          // the send had just put them in.
          id: marginThreadItem(thread),
          text: labelWords(
            thread.root.text || anchorLabel(thread.anchor, thread.root.about),
          ),
          thread,
          // The Thread record already combines server attention with the local workflow
          // overlay. Margin and Page Map carry that reading rather than deriving another
          // answer from raw turn or workflow fields.
          userAttention: onUser
            ? {
                label: attention.label,
                reason: thread.attention?.reason ?? "workflow",
              }
            : null,
          unread,
          // Page Map lists each thread on its own row, so the word goes on the row
          // rather than on an aggregate.
          ...(onUser
            ? { mapContext: attention.label }
            : unread
              ? { mapContext: `${unread} unread` }
              : {}),
          // Work decorates the thread control; it never replaces the control's
          // comment face or its disclosure action.
          workflowReceipt: onUser ? null : attention?.workflow,
          activate: () => showThread(id),
        },
        pointed,
      );
    }

    const asks = openAsks();
    for (const ask of asks) {
      const id = ask.id;
      const target = elementById(id);
      if (!target) continue;
      add(groups, target, {
        kind: "ask",
        id: `ask:${id}`,
        // The group this row stands in already names the Ask; the row says why it is
        // there, since these are the Asks the user owes.
        text: "Waiting on you",
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows.
        label: addressableLabel(target) || null,
        activate: () => {
          const standing = openAsks();
          const next = standing.find((candidate) => candidate.id === id);
          if (next) goToAsk(next, standing);
        },
      });
    }

    const projection = currentProjection();
    const claimActivity = new Map(
      workflows()
        .filter(isLiveWorkflow)
        .map((item) => [`${item.subject.kind}:${item.subject.id}`, item]),
    );
    const activityAlreadyShown = new Set();
    const acknowledged = new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const receipt = receiptByCoordinate.get(coordinate);
      if (!receipt) continue;
      const account = [
        addressableWord(target),
        humanized(entry.e.action),
        addressableLabel(target),
      ]
        .filter(Boolean)
        .join(" · ");
      const face = agentWorkflowFace(receipt);
      if (!face) continue;
      if (face.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.subject.id}`);
      acknowledged.add(target);
      add(groups, target, {
        kind: face.kind,
        id: `acknowledgment:${receipt.id}`,
        text: labelWords(`${face.text} · ${account}`),
        workflowFace: Object.freeze({ ...KINDS[face.kind], label: face.text }),
        workflowReceipt: receipt,
        ...(face.context ? { context: face.context } : {}),
        activate: () =>
          revealTarget(target, `${face.text}: ${account}`, scrollToElement),
      });
    }

    for (const origin of projectionOrigins(authoredStates(), projection)) {
      const target = elementById(origin.unit);
      if (!target) continue;
      // A gesture the agent still owes an answer to stands under its workflow row, which
      // says the change is the user's and where it has got to; its provenance row would
      // say the first half again.
      if (origin.origin === "user" && acknowledged.has(target)) continue;
      const face = KINDS[origin.origin];
      add(groups, target, {
        kind: origin.origin,
        id: `state-origin:${origin.origin}:${origin.unit}`,
        // Durable provenance belongs in Page Map rather than another target margin entry:
        // it remains explicit without changing the page's action density or geometry.
        marker: false,
        text: labelWords(
          [face.label, addressableWord(target), addressableLabel(target)]
            .filter(Boolean)
            .join(" · "),
        ),
        activate: () =>
          revealTarget(
            target,
            `${face.label}: ${addressableLabel(target) || addressableWord(target)}`,
            scrollToElement,
          ),
      });
    }

    const base = comparisonBase();
    comparisonChanges().forEach((target, index) => {
      const account = `${addressableWord(target)} changed${base == null ? "" : ` since v${base}`}`;
      const inline = inlineComparison(target);
      const mapAccount = inline ? `${addressableWord(target)} changed` : account;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: labelWords(
          [mapAccount, addressableLabel(target)].filter(Boolean).join(" · "),
        ),
        // A disclosure has to say what it holds, or its one word reports a fact and
        // promises nothing. The margin entry's quieter line carries it, and a block the
        // comparison holds nothing for has none, so no margin entry offers a press it has
        // not got.
        ...(inline ? { context: inline.offer, mapContext: inline.offer } : {}),
        // What a Change reading holds, where the comparison kept the base version's
        // words for this block: pressing it splices dropped text into the current
        // passage and paints additions there, so the user learns what changed without
        // travelling to the other version and back. Where it kept none, the press is the
        // travel it always was, and `discloses` answering null is what says so — to the
        // margin entry's relation, to the shortcut bar's word for the press, and to the
        // reference.
        discloses: () => inlineComparison(target),
        activate: () => {
          const said = toggleInlineComparison(target);
          revealTarget(
            target,
            said ? `${account} · ${said}` : account,
            scrollToElement,
          );
        },
      });
    });

    if (runtime.activity?.held)
      for (const update of updateSequence()) {
        if (update.source !== "claim" || update.disposition !== "effective") continue;
        if (update.revision > runtime.currentRevision) continue;
        if (update.target.kind === "thread" && representedThreads.has(update.target.id))
          continue;
        if (activityAlreadyShown.has(`${update.target.kind}:${update.target.id}`))
          continue;
        const target =
          update.target.kind === "thread"
            ? placedAt(update.target.id)?.element
            : elementById(update.target.id);
        const age = ago(update.ts);
        const account = [update.agent, update.text || humanized(update.action)]
          .filter(Boolean)
          .join(" · ");
        add(groups, target, {
          kind: "activity",
          id: `activity:${update.id}`,
          text: labelWords(account),
          workflowFace: KINDS.activity,
          workflowReceipt: claimActivity.get(
            `${update.target.kind}:${update.target.id}`,
          ),
          context: [age && `Checked in ${age}`, update.text]
            .filter(Boolean)
            .join(" · "),
          activate: () => revealTarget(target, account, scrollToElement),
        });
      }

    for (const offered of contributionEntries()) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
      if (!target?.isConnected || inChrome(target)) continue;
      const group = groupFor(groups, target);
      if (group.offers.some((candidate) => candidate.key === offered.key))
        throw new TypeError(
          `Duplicate margin contribution key for ${target.id || targetPath(target)}: ${offered.key}`,
        );
      group.offers.push(offered);
      const subject = offered.reading.subject;
      if (String(subject ?? "").trim()) {
        if (group.subject && group.subject !== String(subject).trim())
          throw new TypeError(
            `Conflicting margin contribution subjects for ${target.id || targetPath(target)}`,
          );
        group.subject = String(subject).trim();
      }
      for (const item of offered.reading.readings) {
        const kind = item.kind ?? "action";
        if (!KINDS[kind]) throw new TypeError(`Unknown margin reading kind: ${kind}`);
        group.items.push({
          marker: false,
          ...item,
          owner: offered.key,
          kind,
          activate: () => offered.registration.activateReading(item.id),
        });
      }
    }

    const outline = pageOutline();
    const collected = [...groups.values()];
    const subjects = collected
      .filter((group) => !group.subject)
      .map((group) => group.target);
    targets.clear();
    points.clear();
    entries = marginInventory(
      collected
        .sort((left, right) =>
          comesBefore(left.point ?? left.target, right.point ?? right.target),
        )
        .map((group) => {
          const subject = outlineSubjectFor(group.target, subjects, outline);
          targets.set(group.key, group.target);
          if (group.point) points.set(group.key, group.point);
          return Object.freeze({
            key: group.key,
            targetId: group.target.id,
            title: labelWords(
              [
                group.subject ? null : subject.context,
                group.word,
                group.subject ?? addressableLabel(group.target),
                // A pointed row is named by the words it stands by, so it and the
                // target's own row do not read alike.
                pointName(group.pointWords),
              ]
                .filter(Boolean)
                .join(" · "),
            ),
            offers: Object.freeze(group.offers.map((offered) => offered.model)),
            items: Object.freeze(group.items.map(captureItem)),
            workflowReceipt: workflowReceipt(group.items),
          });
        }),
    );
    return entries;
  }

  function revealTarget(target, account, scrollToElement) {
    if (!target?.isConnected) return;
    scrollToElement(target, scrollBehavior(), "nearest");
    // The account goes to the bottom notice rather than to the live region alone:
    // a Change margin entry's target is usually already on screen, so the scroll moves nothing
    // and a press that only announced was, to a sighted user, a press that did nothing.
    notice(account);
  }

  return Object.freeze({
    collect: collectEntries,
    read: () => entries,
    targetFor,
    entryPoint,
    entryPlace,
    sourceItem,
    workflowReceipt,
    targetPath,
    threadItem: marginThreadItem,
    activate: (item) => sourceItem(item)?.activate(),
  });
}
