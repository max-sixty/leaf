/* The current annotation inventory, independent of its page presentation.

   This owner projects the application's published Threads, On lists, provenance and
   workflows together with producer-declared contributions. Frozen readings contain
   no browser capability. Current target/point nodes and generated action capabilities
   stay in this directory; contributed actions resolve through their registration.
   No renderer folds events or owns a second target inventory. The Thread coordinator
   refreshes after current widget claims and required conversation commits. Mechanical
   paints and immediate contribution updates refresh this same directory.

   Each collection reads the whole page's records, and the words of a target only where
   they changed (`passageRows`). An entry stays the same object from one collection to
   the next for as long as what it is made from holds still (`keptEntry`), so a reader
   learns whether an entry changed by comparing the two. */
import { share } from "/runtime/framework.js";
import { replyIsEditing } from "./thread/replies.js";
import { KINDS } from "./contribution-model.js";
import { excerptWords, labelWords } from "./words.js";
import { contributionEntries } from "./contributions.js";
import { marginEntry, threadMarks } from "./margin-model.js";
import { agentName, readPart } from "./semantic-state.js";
import { livePoint } from "./pointed-place.js";
import { ago } from "./presence.js";
import { runtime } from "./context.js";
import {
  elementById,
  findEach,
  GENERATED,
  inChrome,
  keptAnswer,
  quoteFrom,
  textNodesUnder,
} from "./passages.js";
import { addressableLabel, addressableWord } from "./addressable-names.js";
import { threadList } from "./thread/state.js";
import { threadKey } from "./thread/model.js";
import { readingOrder, readingPlace, targetSegments } from "./resolved-target.js";
import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { claimed } from "./thread/surfaces.js";
import { threadName } from "./thread/messages.js";
import { outlineContexts } from "./thread/placement.js";
import {
  isPageWidgetWorkflow,
  isWorkflowProgress,
  progressFace,
  strongestWorkflow,
  todoWord,
  workflowWord,
} from "./thread/workflow.js";
import { agentSays, leafSays } from "./voice.js";
import { renderedOrdering, shadowHost, under } from "./shadow.js";
import { placeOf } from "./current-target.js";
import { obligationPlace } from "./obligations/place.js";
import { scrollBehavior } from "./motion.js";
import {
  changeAccount,
  changeCard,
  changeSince,
  comparisonChanges,
  toggleChangeCard,
} from "./version.js";
import { versionProvenance } from "./change-provenance.js";

// The words of every obligation's row, one reading for all of them, so a collection
// finds each row's words unchanged by identity rather than by reading them
// (`captureItem`).
const WAITING_ON_ME = leafSays("Waiting on me");

// Where each published workflow still in progress stands in the published order, by
// its id.
const inProgress = readPart(
  (root) =>
    new Map(
      root.effective.workflows.flatMap((workflow, at) =>
        isWorkflowProgress(workflow) ? [[workflow.id, at]] : [],
      ),
    ),
);

/** @typedef {import("./margin-model.js").AnnotationItem} AnnotationItem
 * @typedef {import("./contributions.js").ContributionSource} ContributionSource
 * @typedef {import("./contributions.js").ContributionOffer} ContributionOffer
 * @typedef {import("./margin-model.js").MarginEntry<ContributionOffer>} InventoryEntry
 * @typedef {import("./margin-model.js").MarginGroup<ContributionOffer>} EntryGroup
 * @typedef {import("./framework/application.js").Workflow} Workflow
 * @typedef {import("./thread/workflow.js").ThreadRecord} ThreadRecord
 * @typedef {import("./anchor-placement.js").Placement} Placement
 * @typedef {import("./passages.js").Segment} Segment
 * @typedef {{activate: () => unknown, discloses?: () => ReturnType<typeof changeCard>, change?: import("./version.js").Change}} ItemSource
 * @typedef {AnnotationItem & ItemSource} LiveItem
 * @typedef {{key: string | null, element?: Element | null, passage?: Placement | null, words?: string | null | undefined}} Pointed
 * @typedef {{key: string, target: Element, point: Element | null, passage: Placement | null,
 * pointWords: string | null, word: string, subject: string | null, title: string | null,
 * items: LiveItem[], offers: ContributionSource[]}} Group
 * @typedef {Map<string | Element, Group>} Groups
 * @typedef {ReturnType<typeof import("./anchor-travel.js").createAnchorTravel>["scrollToElement"]} ScrollToElement
 */

// What the inventory reads from the semantic root: the Questions, the workflows its
// entries report, the shown revision and the agent's to-dos, and the projection whose
// reported and overridden marks it lists once the projection's chrome has painted them.
// What the thread pass decides about a thread reaches it as readings its paint follows:
// where the thread is placed (`placedAt`) and whether a widget seats it (`claimed`), so
// a pass that moves one repaints the margin, and one that moves none leaves it.
/** @param {import("./framework/application.js").SemanticRoot} root */
export const annotationSelection = (root) => ({
  projection: root.effective.projection,
  obligations: root.effective.obligations,
  workflows: root.effective.workflows,
  revision: root.document.revision,
});

/** @param {{readObligations: typeof import("./obligations/model.js").readObligations, placedAt: ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>["placedAt"], openThread: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openPageThread"], goToObligation: ReturnType<typeof import("./obligations/view.js").createObligationView>["goToObligation"], scrollToElement: ScrollToElement}} dependencies */
export function createAnnotationInventory({
  readObligations,
  placedAt,
  openThread,
  goToObligation,
  scrollToElement,
}) {
  /** @param {string | null | undefined} value */
  const humanized = (value) =>
    String(value ?? "")
      .replace(/[-_]+/g, " ")
      .trim();

  /** @param {Element} target @returns {string} */
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
      const projection = node.getAttribute("data-lf-projection");
      if (projection && node.hasAttribute("data-lf-datum")) {
        from = `datum:${projection}/${node.getAttribute("data-lf-datum")}:`;
        break;
      }
      const parent =
        node.parentElement ??
        (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
      if (!parent) break;
      const siblings = [...parent.children].filter(
        (candidate) => !candidate.matches(GENERATED),
      );
      steps.push(`${node.localName}:${siblings.indexOf(node)}`);
      if (node.localName === "body" || parent instanceof ShadowRoot) break;
      node = parent;
    }
    return `${prefix}${from}${steps.reverse().join("/")}`;
  }

  // Where a group stands in the page's reading order (resolved-target.js,
  // `readingOrder`): the row it points into, else its passage, else its target.
  /** @param {Group} group */
  const placeIn = (group) => {
    const place = readingPlace(group.passage, group.point);
    return place.node ? place : { ...place, node: group.target };
  };

  // Targets and generated-reading callbacks stay outside the model. Registered
  // contributions already publish their own immutable model readings.
  /** @type {Map<string, Element>} */
  const targets = new Map();
  /** @type {WeakMap<AnnotationItem, ItemSource>} */
  const itemSources = new WeakMap();
  /** @param {Pick<InventoryEntry, "key"> | null | undefined} entry */
  const targetFor = (entry) => (entry ? (targets.get(entry.key) ?? null) : null);
  // The row a pointed entry stands by (groupFor), as anchor-placement last placed it, while
  // it still stands inside its target. Where the entry stands (`entryPlace`) is that
  // row, else the target: every reading of where an entry is on the page, as against
  // what it is about, asks this.
  /** @type {Map<string, Element>} */
  const points = new Map();
  /** @param {Pick<InventoryEntry, "key"> | null | undefined} entry */
  const entryPoint = (entry) =>
    entry ? livePoint(targetFor(entry), points.get(entry.key)) : null;
  /** @param {Pick<InventoryEntry, "key"> | null | undefined} entry */
  const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
  // The passage a quoting entry stands by (groupFor), as anchor-placement last resolved
  // it (resolved-target.js).
  /** @type {Map<string, Placement>} */
  const passages = new Map();
  /** @param {Pick<InventoryEntry, "key"> | null | undefined} entry */
  const entryPassage = (entry) => (entry ? (passages.get(entry.key) ?? null) : null);
  // A pointed row is named by its words as the page reads them, cells and blocks apart.
  /** @param {string | null | undefined} words */
  const pointName = (words) => {
    const excerpt = words && excerptWords(words, 32);
    return excerpt ? `“${excerpt}”` : null;
  };
  /** @param {AnnotationItem} item */
  const sourceItem = (item) => itemSources.get(item);
  // An item equal to the one last at its place comes back as that object (`share`), and
  // takes this reading's capabilities, which close over the live target.
  /** @param {LiveItem} item @param {AnnotationItem | undefined} last */
  function captureItem(item, last) {
    const { activate, discloses, change, ...data } = item;
    const snapshot = Object.freeze(
      share(last, {
        ...data,
        carriesWorkflow: Boolean(workflowReceipt([item])),
      }),
    );
    itemSources.set(snapshot, {
      activate,
      ...(discloses ? { discloses } : {}),
      ...(change ? { change } : {}),
    });
    return snapshot;
  }

  const workflows = () => runtime.workflows;
  // Selected from the published workflows rather than gathered from the items, whose
  // order is the margin's, so the strongest is the server's. A receipt is looked up by
  // its id among those still in progress, so each item costs what it holds rather than
  // every workflow on the page.
  /** @param {readonly AnnotationItem[]} items */
  const workflowReceipt = (items) => {
    const at = inProgress();
    const published = workflows();
    /** @type {Set<number>} */
    const receipts = new Set();
    for (const { workflowReceipt } of items) {
      const index = workflowReceipt ? at.get(workflowReceipt.id) : undefined;
      if (index !== undefined) receipts.add(index);
    }
    return strongestWorkflow(
      [...receipts].sort((a, b) => a - b).flatMap((index) => published[index] ?? []),
    );
  };
  // One group per target, one more for each row inside it that pointing gestures stood
  // threads at (pointed-place.js), and one more for each passage threads quote: those
  // threads stand there together, by what they are about, and everything else about the
  // target (its other threads, an obligation's marker, a widget's actions) keeps the target's
  // own row. `pointed` is `{ key, element, passage, words }`: the row's key (a pointed
  // row's its first comment gave it, a passage's from its words, `passageRows`), the
  // element it is or the passage it stands by (a resolved anchor), and its words, which
  // name it.
  /** @param {Groups} groups @param {Element} target @param {Pointed | null} [pointed] */
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

  // The row key for threads quoting a passage of `target`: its words as the page reads
  // them, and which occurrence of those words in the target's reading it is, counting
  // the copies that stand wholly before it, one after another. Threads quoting the same
  // words share it, and none settling or arriving changes it, so the row and a card
  // open on it outlive them. A re-render that removes an earlier occurrence renumbers it
  // and builds the row again, as a shifted path does an id-less target's.
  //
  // Every passage threads quote in a target is keyed from one reading of it: where each
  // passage starts among the target's words, heard as they are read, and every place each
  // passage's words stand in them, found by one pass for all of them. So a paragraph
  // holding many quoted passages costs its words and its passages, not their product.
  //
  // A passage's key is kept, under where it starts and what it says, for as long as the
  // target's words are unchanged (passages.js, `keptAnswer`). So a collection reads a
  // target again only where its words changed or a passage in it is new. Every change to
  // the page starts a collection, a closed tab's document drawing included, and a change
  // to one part of the page leaves a datum in another unchanged. Keyed afresh on every
  // collection, one comment on a 4 MB text document read that document again each time
  // another of 30 drew, 200 ms each in Chromium.
  /** @param {Element} target @param {readonly (readonly [Segment, ...Segment[]])[]} quoted
   * @returns {string[]} */
  function passageRows(target, quoted) {
    // Each key by the passage's first text node, then by where it starts there and what
    // it says.
    /** @type {Map<Text, Map<string, string>>} */
    const kept = keptAnswer(target, "passage rows", () => new Map());
    const asked = quoted.map((passage) => ({
      passage,
      node: passage[0].node,
      key: `${passage[0].start} ${quoteFrom(passage)}`,
    }));
    const unkeyed = asked.filter(({ node, key }) => !kept.get(node)?.has(key));
    if (unkeyed.length) {
      const read = readPassageRows(
        target,
        unkeyed.map(({ passage }) => passage),
      );
      unkeyed.forEach(({ node, key }, at) =>
        kept.set(
          node,
          (kept.get(node) ?? new Map()).set(key, /** @type {string} */ (read[at])),
        ),
      );
    }
    return asked.map(
      ({ node, key }) => /** @type {string} */ (kept.get(node)?.get(key)),
    );
  }
  /** @param {Element} target @param {readonly (readonly [Segment, ...Segment[]])[]} quoted
   * @returns {string[]} */
  function readPassageRows(target, quoted) {
    // How many of the target's words stand before each passage's first character, as
    // reading the target only up to there would say: all of them where the passage
    // starts in none of its text nodes.
    /** @type {Map<Text, Map<number, number | undefined>>} */
    const starts = new Map();
    for (const [{ node, start }] of quoted)
      starts.set(node, (starts.get(node) ?? new Map()).set(start, undefined));
    const text = quoteFrom(textNodesUnder(target), (node, offset, length) => {
      const at = starts.get(node);
      if (at?.has(offset)) at.set(offset, length);
    });
    /** @param {Segment} first */
    const before = ({ node, start }) => starts.get(node)?.get(start) ?? text.length;
    const words = quoted.map((segments) => quoteFrom(segments));
    const places = findEach(text, words);
    return quoted.map(([first], at) => {
      const said = /** @type {string} */ (words[at]);
      const ahead = before(first);
      // No words split a reading between every character.
      let count = said ? 0 : ahead - 1;
      let end = 0;
      for (const place of said ? (places.get(said) ?? []) : []) {
        if (place < end) continue;
        if (place + said.length > ahead) break;
        count += 1;
        end = place + said.length;
      }
      return JSON.stringify([said, count]);
    });
  }
  // A reading of each target made once a pass, however many of its groups ask.
  /** @template T @param {(target: Element) => T} read */
  const perTarget = (read) => {
    /** @type {Map<Element, T>} */
    const kept = new Map();
    return (/** @type {Element} */ target) => {
      if (!kept.has(target)) kept.set(target, read(target));
      return /** @type {T} */ (kept.get(target));
    };
  };

  /** @param {Groups} groups @param {Element | null | undefined} target @param {LiveItem} item @param {Pointed | null} [pointed] */
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

  // A receipt's face is its category's icon and rank under the receipt's own word,
  // so one reading of a receipt never names a different stage than its text does. Its
  // line says when, in the interface's words, and what the agent said of it.
  /** @param {Workflow | null | undefined} receipt
   * @returns {{kind: "waiting" | "activity" | "pickup" | "sent", word: import("./voice.js").Said, context: import("./voice.js").Words | null} | null} */
  function agentWorkflowFace(receipt) {
    if (!receipt) return null;
    const word = workflowWord(receipt, agentName());
    if (!word) return null;
    const when = receipt.ts ? ago(receipt.ts) : "";
    const said = receipt.detail ? [agentSays(receipt.detail)] : [];
    return {
      kind:
        // A receipt handed back to the user is blocked by its failure.
        receipt.state === "blocked"
          ? "waiting"
          : receipt.state === "running"
            ? "activity"
            : receipt.seen
              ? "pickup"
              : "sent",
      word,
      context:
        when || said.length
          ? [...(when ? [when] : []), ...(when && said.length ? [" · "] : []), ...said]
          : null,
    };
  }

  /** @overload @param {ThreadRecord} thread @returns {string} */
  /** @overload @param {ThreadRecord | null | undefined} thread @returns {string | null} */
  /** @param {ThreadRecord | null | undefined} thread */
  function marginThreadItem(thread) {
    return thread ? `comment:${threadKey(thread)}` : null;
  }

  /** @type {readonly InventoryEntry[]} */
  let entries = Object.freeze([]);
  // Each entry by its key, with the group it was made from.
  /** @type {Map<string, {group: EntryGroup, entry: InventoryEntry}>} */
  let lastEntries = new Map();
  // An entry is a function of its group (`marginEntry`), and each thing a group holds is
  // the same object while it holds still: a published record is shared across
  // publications, an item through `captureItem`, and a contribution's model is new only
  // when its producer publishes. So a group holding what the last under its key held
  // keeps that entry.
  /** @param {EntryGroup} group @returns {InventoryEntry} */
  function keptEntry(group) {
    const last = lastEntries.get(group.key);
    if (!last) return marginEntry(group);
    const held = (/** @type {keyof EntryGroup} */ field) => {
      const [was, now] = [last.group[field], group[field]];
      return Array.isArray(now) && Array.isArray(was)
        ? was.length === now.length && now.every((thing, at) => thing === was[at])
        : was === now;
    };
    return /** @type {(keyof EntryGroup)[]} */ (Object.keys(group)).every(held)
      ? last.entry
      : marginEntry(group);
  }
  /** @type {Set<(entries: readonly InventoryEntry[]) => void>} */
  const watchers = new Set();

  // A resolved thread leaves the margin, unless a reply is being written in it: saved
  // words and an editing session are distinct, and only an active session keeps it.
  /** @param {ThreadRecord} thread */
  const threadHasDiscussion = (thread) =>
    !thread.resolved || replyIsEditing(threadKey(thread));

  // A command's subject does not depend on whether an overlay or exact widget seat
  // has realized its discussion. Attachment place and pointed row share the same
  // resolved record as collection, navigation and paint.
  /** @param {Node | null} node */
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
    /** @type {Groups} */
    const groups = new Map();
    const labelOf = perTarget(addressableLabel);
    /** @type {Map<string, Workflow>} */
    const receiptByCoordinate = new Map();
    for (const receipt of visibleWidgetWorkflows()) {
      // A widget's workflow names its owner, unit and verb.
      const coordinate = receipt.coordinate;
      receiptByCoordinate.set(JSON.stringify(coordinate), receipt);
    }
    const standing = [];
    /** @type {Map<Element, (readonly [Segment, ...Segment[]])[]>} */
    const quotedIn = new Map();
    for (const thread of threadList()) {
      if (!threadHasDiscussion(thread) || !thread.anchor || claimed(thread.id))
        continue;
      const placement = placedAt(thread.id);
      const target = placement?.place;
      if (!target) continue;
      const [first, ...rest] = targetSegments(placement);
      const point = livePoint(target, placement.point);
      /** @type {readonly [Segment, ...Segment[]] | null} */
      const passage = !point && first ? [first, ...rest] : null;
      if (passage) quotedIn.set(target, [...(quotedIn.get(target) ?? []), passage]);
      standing.push({ thread, placement, target, point, passage });
    }
    /** @type {Map<Element, string[]>} */
    const rows = new Map(
      [...quotedIn].map(([target, quoted]) => [target, passageRows(target, quoted)]),
    );
    for (const { thread, placement, target, point, passage } of standing) {
      const id = thread.id;
      const pointed = point
        ? { key: placement.pointRow, element: point, words: placement.pointWords }
        : passage
          ? {
              key: /** @type {string} */ (rows.get(target)?.shift()),
              passage: placement,
              words: thread.anchor?.quote,
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

    // A widget's obligation has a place on the page (obligations/place.js); the rest
    // have no node.
    /** @param {import("./framework/application.js").ObligationRecord} item
     * @returns {item is import("./obligations/answer.js").AnswerableObligation} */
    const hasPlace = (item) => Boolean(obligationPlace(item).node);
    const placed = () => readObligations().user.filter(hasPlace);
    for (const item of readObligations().user) {
      const id = item.id;
      const target = obligationPlace(item).node;
      if (!target) continue;
      add(groups, target, {
        kind: "on-me",
        id: `on-me:${id}`,
        // The group this row stands in already names the obligation; the row says why it is
        // there, since these are the obligations the user owes.
        text: "Waiting on me",
        words: WAITING_ON_ME,
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows: the widget's name.
        label: labelOf(target) || null,
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
        text: labelWords(`${face.word.text} · ${account}`),
        // The same name as its rows show it, the receipt's word in its speaker's face.
        words: [face.word, ` · ${labelWords(account)}`],
        workflowFace: Object.freeze({
          ...KINDS[face.kind],
          label: face.word.text,
          voice: face.word.voice,
        }),
        workflowReceipt: receipt,
        ...(face.context ? { context: face.context } : {}),
        activate: () =>
          revealTarget(target, `${face.word.text}: ${account}`, scrollToElement),
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

    // One entry per change (version.js, `changeRuns`), beside the block the change starts
    // with, or the block beside its gap where it only took blocks out, so a section
    // rewritten whole gets one entry rather than one per paragraph. It says what the
    // change did in blocks (`changeAccount`): "2 paragraphs replaced by 3". Under it
    // stands what the version the comparison shows was saved after, the same for
    // every change, a line each (change-provenance.js).
    const savedAfter = versionProvenance()?.lines ?? [];
    comparisonChanges().forEach((change, index) => {
      const target = change.at;
      const did = changeAccount(change);
      const account = changeSince(change);
      const card = changeCard(change);
      const mapAccount = card ? did : account;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: labelWords(
          [mapAccount, addressableLabel(target)].filter(Boolean).join(" · "),
        ),
        words: [
          leafSays(mapAccount),
          ...(addressableLabel(target) ? [` · ${addressableLabel(target)}`] : []),
        ],
        // A disclosure has to say what it holds, or its one word reports a fact and
        // promises nothing. The margin entry's quieter line carries what the change did,
        // and the Page Map row the versions its card compares; a change the comparison
        // holds nothing for has neither, so no margin entry offers a press it has not
        // got. What the version was saved after is the comparison's reading, not the
        // card's, so it stands under every change, a line each.
        // The entry's relation says whether the card stands open, so opening it changes
        // the entry (`keptEntry`).
        ...(card || savedAfter.length
          ? {
              context: [...(card ? [[account]] : []), ...savedAfter].flatMap(
                (line, at) => (at ? ["\n", ...line] : line),
              ),
            }
          : {}),
        ...(card ? { mapContext: card.offer, cardOpen: card.open } : {}),
        // What a Change reading holds, where the comparison kept the words the change
        // replaced or edited: pressing it opens the change's card over the change, so
        // the user learns what changed without travelling to the other version and back
        // and without the page moving. Where it kept none, the press is the travel it
        // always was, and `discloses` answering null is what says so — to the margin
        // entry's relation, to the hint's word for the press, and to the reference.
        discloses: () => changeCard(change),
        // Hovering or focusing the entry outlines the whole change
        // (margin-projection.js, `refreshHighlight`).
        change,
        activate: () => {
          const said = toggleChangeCard(change);
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
    // A thread's to-do is its thread's attention (above); the page's is the floating
    // panel's.
    for (const todo of readObligations().all) {
      if (todo.source.kind !== "todo" || todo.state === "done") continue;
      const { subject } = todo.source;
      if (
        (subject.kind !== "widget" && subject.kind !== "element") ||
        Number(todo.revision) > Number(runtime.currentRevision)
      )
        continue;
      if (activityAlreadyShown.has(`widget:${subject.id}`)) continue;
      const target = elementById(subject.id);
      // The line of the start on it, standing or stopped.
      const line = todo.line ?? null;
      const title = todo.prompt.text ?? "";
      const word = todoWord(todo);
      const account = [todo.agent, line?.text ?? title].filter(Boolean).join(" · ");
      add(groups, target, {
        kind: "activity",
        id: `todo:${todo.id}`,
        // A start running on it is the agent at work there (margin-bars.js).
        atWork: todo.state === "running",
        text: labelWords(account),
        words: [
          ...(todo.agent ? [`${todo.agent} · `] : []),
          agentSays(labelWords(line?.text ?? title)),
        ],
        workflowFace: Object.freeze({
          ...KINDS.activity,
          label: word.text,
          voice: word.voice,
        }),
        context: line
          ? [leafSays(`Checked in ${ago(line.ts)} · `), agentSays(title)]
          : null,
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

    const collected = [...groups.values()];
    const subjects = collected
      .filter((group) => !group.subject)
      .map((group) => group.target);
    targets.clear();
    points.clear();
    passages.clear();
    /** @type {typeof lastEntries} */
    const nextEntries = new Map();
    const contextOf = perTarget(outlineContexts(subjects));
    // Each group's place read once for the sort, and each node's climb once in it.
    const places = new Map(collected.map((group) => [group, placeIn(group)]));
    const order = renderedOrdering();
    /** @param {Group} group */
    const placeOfGroup = (group) =>
      /** @type {ReturnType<typeof placeIn>} */ (places.get(group));
    entries = Object.freeze(
      collected
        .sort((left, right) =>
          readingOrder(placeOfGroup(left), placeOfGroup(right), order),
        )
        .map((group) => {
          targets.set(group.key, group.target);
          if (group.point) points.set(group.key, group.point);
          if (group.passage) passages.set(group.key, group.passage);
          const lastItems = lastEntries.get(group.key)?.group.items;
          /** @type {EntryGroup} */
          const made = Object.freeze({
            key: group.key,
            targetId: group.target.id,
            title: labelWords(
              [
                group.subject ? null : contextOf(group.target),
                group.word,
                group.subject ?? labelOf(group.target),
                // A pointed row is named by the words it stands by, so it and the
                // target's own row do not read alike.
                pointName(group.pointWords),
              ]
                .filter(Boolean)
                .join(" · "),
            ),
            offers: Object.freeze(group.offers.map((offered) => offered.model)),
            items: Object.freeze(
              group.items.map((item, at) => captureItem(item, lastItems?.[at])),
            ),
            workflowReceipt: workflowReceipt(group.items),
            // Whether the agent is at work on this target, and not stalled: an update
            // here it is working on or replying to, or a to-do with a start running.
            atWork:
              progressFace(workflowReceipt(group.items)) === "working" ||
              group.items.some((item) => item.atWork),
          });
          const entry = keptEntry(made);
          nextEntries.set(group.key, { group: made, entry });
          return entry;
        }),
    );
    lastEntries = nextEntries;
    for (const watcher of watchers) watcher(entries);
    return entries;
  }

  /** @param {Element | null} target @param {string} account @param {ScrollToElement} scrollToElement */
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
    /** @param {(entries: readonly InventoryEntry[]) => void} watcher */
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
    /** @param {AnnotationItem} item */
    activate: (item) => sourceItem(item)?.activate(),
  });
}
