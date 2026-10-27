/* The current annotation inventory, independent of its page presentation.

   This owner projects the application's published Threads, On lists, provenance and
   workflows together with producer-declared contributions. Frozen readings contain
   no browser capability. Current target/point nodes and generated action capabilities
   stay in this directory; contributed actions resolve through their registration.
   No renderer folds events or owns a second target inventory. The Thread coordinator
   refreshes after current widget claims and required conversation commits. Mechanical
   paints and immediate contribution updates refresh this same directory. */
import { replyAvailable } from "./thread/replies.js";
import { KINDS } from "./contribution-model.js";
import { excerptWords, labelWords } from "./words.js";
import { contributionEntries } from "./contributions.js";
import { marginInventory, threadMarks } from "./margin-model.js";
import { agentName } from "./semantic-state.js";
import { livePoint } from "./pointed-place.js";
import { ago } from "./presence.js";
import { runtime } from "./context.js";
import { elementById, inChrome, quoteFrom, textNodesUnder } from "./passages.js";
import { addressableLabel, addressableWord } from "./addressable-names.js";
import { threadList } from "./thread/state.js";
import { threadKey } from "./thread/model.js";
import { targetSegments } from "./resolved-target.js";
import { projectionOrigins, stateCoordinate } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { claimed, heldOut } from "./thread/surfaces.js";
import { threadName } from "./thread/messages.js";
import { outlineSubjectFor, pageOutline } from "./thread/placement.js";
import {
  isPageWidgetWorkflow,
  isWorkflowProgress,
  progressFace,
  strongestWorkflow,
  todoLabel,
  workflowLabel,
  workflowVoice,
} from "./thread/workflow.js";
import { renderedOrder, shadowHost, under } from "./shadow.js";
import { placeOf } from "./current-target.js";
import { obligationPlace } from "./obligations/place.js";
import { scrollBehavior } from "./motion.js";
import {
  comparisonBase,
  comparisonChanges,
  inlineComparison,
  toggleInlineComparison,
} from "./version.js";

// What the inventory reads from the semantic root: the Questions, the workflows its
// entries report, the shown revision and the agent's to-dos, and the projection whose
// reported and overridden marks it lists once the projection's chrome has painted them.
// What the thread pass decides about a thread reaches it as readings its paint follows:
// where the thread is placed (`placedAt`) and whether a widget seats or holds it
// (`claimed`, `heldOut`), so a pass that moves one repaints the margin, and one that
// moves none leaves it.
export const annotationSelection = (root) => ({
  projection: root.effective.projection,
  obligations: root.effective.obligations,
  workflows: root.effective.workflows,
  revision: root.document.revision,
  todos: root.authoritative?.browser.todos ?? null,
});

export function createAnnotationInventory({
  readObligations,
  placedAt,
  openThread,
  goToObligation,
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

  // What a group stands by, for its place in the page's order: passages in one text
  // node by where in it they start.
  const standsBy = (group) =>
    group.point ?? targetSegments(group.passage)[0]?.node ?? group.target;
  const startsAt = (group) => targetSegments(group.passage)[0]?.start ?? -1;

  function comesBefore(left, right) {
    if (left === right) return 0;
    if (!left) return 1;
    if (!right) return -1;
    return renderedOrder(left, right);
  }

  // Targets and generated-reading callbacks stay outside the model. Registered
  // contributions already publish their own immutable model readings.
  const targets = new Map();
  const itemSources = new WeakMap();
  const targetFor = (entry) => (entry ? (targets.get(entry.key) ?? null) : null);
  // The row a pointed entry stands by (groupFor), as anchor-placement last placed it, while
  // it still stands inside its target. Where the entry stands (`entryPlace`) is that
  // row, else the target: every reading of where an entry is on the page, as against
  // what it is about, asks this.
  const points = new Map();
  const entryPoint = (entry) =>
    entry ? livePoint(targetFor(entry), points.get(entry.key)) : null;
  const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
  // The passage a quoting entry stands by (groupFor), as anchor-placement last resolved
  // it (resolved-target.js).
  const passages = new Map();
  const entryPassage = (entry) => (entry ? (passages.get(entry.key) ?? null) : null);
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
  // One group per target, one more for each row inside it that pointing gestures stood
  // threads at (pointed-place.js), and one more for each passage threads quote: those
  // threads stand there together, by what they are about, and everything else about the
  // target (its other threads, an obligation's marker, a widget's actions) keeps the target's
  // own row. `pointed` is `{ key, element, passage, words }`: the row's key (a pointed
  // row's its first comment gave it, a passage's from its words, `passageRow`), the
  // element it is or the passage it stands by (a resolved anchor), and its words, which
  // name it.
  function groupFor(groups, target, pointed = null) {
    const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
    const slot = pointed ? `point:${key}` : target;
    let group = groups.get(slot);
    if (!group) {
      const word = addressableWord(target);
      group = {
        key,
        target,
        point: pointed?.element ?? null,
        passage: pointed?.passage ?? null,
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

  // The row key for threads quoting `passage` of `target`: its words as the page reads
  // them, and which occurrence of those words in the target's reading it is. Threads
  // quoting the same words share it, and none settling or arriving changes it, so the
  // row and a card open on it outlive them. A re-render that removes an earlier
  // occurrence renumbers it and builds the row again, as a shifted path does an id-less
  // target's.
  function passageRow(target, passage) {
    const segments = targetSegments(passage);
    const page = textNodesUnder(target);
    const at = page.findIndex(({ node }) => node === segments[0].node);
    const before =
      at < 0 ? page : [...page.slice(0, at), { ...page[at], end: segments[0].start }];
    const words = quoteFrom(segments);
    return JSON.stringify([words, quoteFrom(before).split(words).length - 1]);
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
    const label = workflowLabel(receipt, agentName());
    if (!label) return null;
    return {
      kind:
        // A receipt handed back to the user always carries its failure.
        receipt.condition
          ? "waiting"
          : receipt.at_work
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
  const watchers = new Set();

  // Saved words and an editing session are distinct: only an active session keeps a
  // settled reply open. A widget-held conversation retains its existing notice.
  const threadHasDiscussion = (thread) => replyAvailable(thread) || heldOut(thread.id);

  // A command's subject does not depend on whether an overlay or exact widget seat
  // has realized its discussion. Attachment place and pointed row share the same
  // resolved record as collection, navigation and paint.
  function threadIdsAt(node) {
    const place = placeOf(node);
    let best = null;
    for (const thread of threadList()) {
      if (!threadHasDiscussion(thread)) continue;
      const placement = placedAt(thread.id);
      const target = placement?.place;
      if (!target || !under(place, target)) continue;
      const point = livePoint(target, placement.point);
      const rank = !point ? 1 : under(place, point) ? 2 : 0;
      if (best && target === best.target && point === best.point) {
        best.ids.push(thread.id);
        continue;
      }
      if (
        !best ||
        (target === best.target ? rank >= best.rank : under(target, best.target))
      )
        best = { target, point, rank, ids: [thread.id] };
    }
    return best?.ids ?? [];
  }

  function collectEntries() {
    const groups = new Map();
    const receiptByCoordinate = new Map();
    for (const receipt of visibleWidgetWorkflows()) {
      // A widget's workflow names its owner, unit and verb.
      const coordinate = /** @type {[string, string, string]} */ (receipt.coordinate);
      receiptByCoordinate.set(stateCoordinate(...coordinate), receipt);
    }
    for (const thread of threadList()) {
      if (!threadHasDiscussion(thread) || !thread.anchor || claimed(thread.id))
        continue;
      const id = thread.id;
      const target = placedAt(id)?.place;
      const placement = placedAt(id);
      const point = livePoint(target, placement?.point);
      const pointed = point
        ? { key: placement.pointRow, element: point, words: placement.pointWords }
        : targetSegments(placement).length
          ? {
              key: passageRow(target, placement),
              passage: placement,
              words: thread.anchor.quote,
            }
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
          text: threadName(thread),
          thread,
          // The Thread record already combines server attention with the local workflow
          // overlay. Margin and Page Map carry that reading rather than deriving another
          // answer from raw turn or workflow fields. Work decorates the thread control;
          // it never replaces the control's comment face or its disclosure action.
          ...threadMarks(thread, agentName()),
          activate: () => openThread(id),
        },
        pointed,
      );
    }

    // A widget's obligation and a to-do on the user have a place on the page
    // (obligations/place.js); the rest have no node.
    const placed = () =>
      readObligations().user.filter((item) => obligationPlace(item).node);
    for (const item of placed()) {
      const id = item.id;
      const target = obligationPlace(item).node;
      add(groups, target, {
        kind: "on-me",
        id: `on-me:${id}`,
        // The group this row stands in already names the obligation; the row says why it is
        // there, since these are the obligations the user owes.
        text: "Waiting on me",
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows: a widget's name, or a to-do's title, which the element
        // it is on does not say.
        label:
          (item.source.kind === "todo" ? item.prompt.text : addressableLabel(target)) ||
          null,
        activate: () => {
          const items = placed();
          const next = items.find((candidate) => candidate.id === id);
          if (next) goToObligation(next, items);
        },
      });
    }

    const projection = currentProjection();
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
        workflowFace: Object.freeze({
          ...KINDS[face.kind],
          label: face.text,
          voice: workflowVoice(receipt),
        }),
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
      const account = `${addressableWord(target)} changed${base == null ? "" : ` since ${base.name}`}`;
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
        // margin entry's relation, to the hint's word for the press, and to the
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

    // A to-do the agent opened on a page widget or element stands beside it, as Working
    // with the line of the start running on it, or as an open to-do under its title.
    // A thread's to-do is its thread's attention (above); the page's is the floating panel's. A
    // to-do on the user is on their list, On me, instead.
    for (const todo of runtime.todos) {
      if (
        todo.owner !== "agent" ||
        todo.state !== "open" ||
        (todo.subject.kind !== "widget" && todo.subject.kind !== "element") ||
        todo.revision > runtime.currentRevision
      )
        continue;
      if (activityAlreadyShown.has(`widget:${todo.subject.id}`)) continue;
      const target = elementById(todo.subject.id);
      const { running } = todo;
      const label = todoLabel(running);
      const account = [todo.agent, running?.text ?? todo.title]
        .filter(Boolean)
        .join(" · ");
      const age = running && ago(running.ts);
      add(groups, target, {
        kind: "activity",
        id: `todo:${todo.id}`,
        // A start running on it is the agent at work there (at-work.js).
        atWork: Boolean(running),
        text: labelWords(account),
        workflowFace: Object.freeze({ ...KINDS.activity, label }),
        context: [age && `Checked in ${age}`, running && todo.title]
          .filter(Boolean)
          .join(" · "),
        activate: () => revealTarget(target, account, scrollToElement),
      });
    }

    for (const offered of contributionEntries()) {
      const target = offered.target();
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
    passages.clear();
    entries = marginInventory(
      collected
        .sort(
          (left, right) =>
            comesBefore(standsBy(left), standsBy(right)) ||
            startsAt(left) - startsAt(right),
        )
        .map((group) => {
          const subject = outlineSubjectFor(group.target, subjects, outline);
          targets.set(group.key, group.target);
          if (group.point) points.set(group.key, group.point);
          if (group.passage) passages.set(group.key, group.passage);
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
            // Whether the agent is at work on this target, and not stalled: an update
            // here it is working on or replying to, or a to-do with a start running.
            atWork:
              progressFace(workflowReceipt(group.items)) === "working" ||
              group.items.some((item) => item.atWork),
          });
        }),
    );
    for (const watcher of watchers) watcher(entries);
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
    watch(watcher) {
      watchers.add(watcher);
      try {
        watcher(entries);
      } catch (error) {
        watchers.delete(watcher);
        throw error;
      }
      return () => watchers.delete(watcher);
    },
    targetFor,
    entryPoint,
    entryPlace,
    entryPassage,
    sourceItem,
    workflowReceipt,
    targetPath,
    threadItem: marginThreadItem,
    threadIdsAt,
    activate: (item) => sourceItem(item)?.activate(),
  });
}
