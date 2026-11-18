/* The user's unsent words: one copy of each draft, which the page's server keeps for
   every tab and device, and each box's view of it.

   Every unsent composition persists:

   - the general comment box;
   - each thread reply;
   - the selection composer, including its anchor, mode and drawing;
   - a thread's first message and replies;
   - an `lf-draft` edit.

   The page's server keeps each draft (`src/leaf/drafts.py`), because the words must
   survive reload, version navigation, closing the tab where they were typed, and the
   user moving to another tab or device. This document holds its copy of each
   (`draftCache`), which every box here reads and writes at once, and the copy goes on
   to the server behind the keystroke (`writeDraft`); a page going away sends what is
   still waiting, and a reload of its tab starts from its copy of it. Words typed while
   the server is out of reach stay in the tab until a look reaches it again; a tab
   closed before then takes them with it. A server that comes back holding less than
   this document heard from it gets its words back.
   On leaf.page the first write starts the visitor's private page. An exported page
   has no server, so its drafts last as long as its tab. No failed write disables the
   live Send or Save action.

   Another tab or device hears a draft change through the look that tells it of the
   log: the look's `drafts` version moves, and the tab reads `/api/drafts`
   (`lookForDrafts`). A served document arrives with the drafts it was served with
   (`lf-drafts`), so a box opens on its words before any look.

   One context has one shared generation. `watchDraft` mirrors every change into every
   live view. Ordinary disconnected inputs retire their subscription. Retained reply
   editors keep mirroring through candidate detachment; their presentation owner
   disposes the subscription when removal commits.

   An editor belongs to its existing draft subscription. A root editor has the context's
   one current connected destination; reply mirrors use the current Thread route
   instead. Revision continuity carries words, generation, caret and local scroll under
   that identity. It restores only the same active generation and only after the
   original input intent has landed the actual editor. A root editor the arriving
   document holds behind a disclosure, as the page comment card holds the page's box,
   is shown through the route its owner declares for Resume writing, since the user was
   writing in it when the revision came; no other hidden editor is opened by this
   mechanical handoff, and a newer edit is never overwritten by it.

   A draft generation is `{attempt, text, payload?, held?}` while active and
   `{attempt, settled: true}` after settlement. Its attempt is minted when an edit
   creates the generation, not on Send, and is reused by every tab that sends it.
   A refusal does not mint a new attempt. Pressing Send again re-evaluates the same
   attempt against current server state. A new edit, including replacing text with the
   same characters, creates a new attempt. A successful send settles only the exact
   active generation it sent, so text typed while the request is in flight survives its
   response.

   An active record and a settled one are different records. An empty active `text`
   means the user intentionally cleared the box. A settled record means Send or Cancel
   settled that generation.

   Each write names the generation it replaces: the one this document last knew the
   server held (`stored`), or none, and a page going away also names its own writes
   still unanswered, which its reload counts as its own. The server takes it only over
   one it names or over none, and answers with what it holds (`drafts.py`), so words
   another tab or device wrote in the meantime come back in its place, and they own the
   draft: this document's words since then retire. Words written over a generation
   another tab sent start the draft again, since they are newer than anything sent. The
   log answers which generations were sent, so the server settles one at its first
   reading after the event, which every tab hears at its next look, and turns a write
   of it that arrives later into its settlement (`drafts.py`).

   Every send draws its result in this document before the log answers. So the send
   masks its generation here at the gesture (`standGesture`) and the box the words were
   typed in reads empty, while the record stands unsettled until the answer accepts it
   or a refusal gives the words back. The mask is this document's; the record is every
   tab's. Words a refusal gives back to a box out of view become the Resume writing
   destination, and the refusal's notice names that address, for every gesture the
   refusal took down (`keepRefusedWords`).

   Settlement is generation-specific. `activeDraftRecord` filters settled records and
   the generation this document is sending. The server never hands this document a
   generation the log admitted (`drafts.py`), so nothing here asks the log whether
   words were sent. `sendDraft` snapshots the current record, checks ownership
   immediately before POST, and settles only that attempt. `mirrorDraft` updates
   visible text only when doing so will not erase a newer local generation.

   The selection composer keys drafts by anchor, not by one global composer slot. Its
   record carries the anchor, mode, and last-touch time; startup reopens the most
   recently touched draft. Different passages may therefore hold independent
   unfinished comments.

   An `lf-draft` editor is a live gesture. It defers the widget's drawing while the
   editor is open, so remote edits and refusal correction wait rather than overwriting
   the textarea. Closing the editor lets the authoritative projection apply in order.

   The comment over the store below says where it came from. */

import { offlineInteractive, pageUrl, runtime } from "./context.js";
import { admitResponse, layerHeaders } from "./layer-client.js";
import { PENDING } from "./thread/identity.js";
import { writingStore } from "./storage.js";
import { tabStore } from "./tab-store.js";
import { randomId } from "./ids.js";
import { focusDestination, readCaret, focused } from "./focus.js";
import { retainUserIntent } from "./user-intent.js";
import { setScroll } from "./arrivals.js";
import { CARET_KEYS, selectsAll } from "./control-selectors.js";
import { passErrorsAt, raiseError } from "./errors.js";
import { notice } from "./notifications.js";
import { signal } from "./framework.js";

/** @typedef {object} DraftPayload
 * @typedef {{attempt: string, text: string, payload?: DraftPayload, held?: string, settled?: never}} ActiveDraft
 * @typedef {{attempt: string, settled: true, text?: never, payload?: never, held?: never}} SettledDraft
 * @typedef {ActiveDraft | SettledDraft} DraftRecord
 * @typedef {import("../types/contract.js").ServedDraft} ServedDraft
 * @typedef {import("../types/contract.js").ServedDraftsAnswer} DraftsReading
 * @typedef {import("../types/contract.js").ServedDraftWriteAnswer} DraftWriteAnswer
 * @typedef {{record: DraftRecord, stored: string | null, version: number, durable: boolean, ours: ReadonlySet<string>}} DraftCopy
 * @typedef {{attempts: string[], copy: Pick<DraftCopy, "record" | "stored" | "version"> | null}} WaitingDraft
 * @typedef {{ctx: string, value: string | null, payload?: DraftPayload}} DraftNews
 * @typedef {import('./composing/text-field.js').LeafTextElement | HTMLTextAreaElement} DraftField
 * @typedef {import('./composing/input.js').InputSync} InputSync
 * @typedef {import('./anchor-travel.js').EditorDestination} EditorDestination
 * @typedef {import('./focus.js').Caret} Caret
 * @typedef {{context: string, selection: Caret | null, generation: string}} WritingPlace
 * @typedef {{ctx: string, input: DraftField | (() => DraftField | null), mirrored: boolean,
 * resume: (() => EditorDestination | null) | null}} DraftEditor */

// ---------- draft persistence ----------
// Text the user typed but hasn't sent must survive navigation, reload, version switches
// and the tab itself. That last one needs a store outside the tab: each
// round's reply hands the URL over again and the user opens the page from the turn in
// front of them, so a page's tabs accumulate and the one holding a half-written sentence
// is as likely to be closed as any other. Tab-local storage carries a draft through
// everything but the one gesture nobody thinks of as destructive. Browser storage
// carries it through that, but not to the user's other browser or device, which the
// page's server does, at the cost of words typed while the server
// can't be reached.
//
// So the draft is the user's, and one draft has one copy: every box showing it, in
// every tab, is a view of the server's record, and a keystroke reaches the rest through
// it. A copy per tab was the alternative and it fails in the direction that loses
// words — two tabs each holding a different half of one thought, and whichever is
// closed takes its half.
//
// A new attempt is minted even when its words equal an earlier message, and the
// attempt is what lets the log recognize the same gesture after the tab that sent it
// has died, and the server settles every generation whose attempt the log holds.

// The page's own draft: the floating panel's field, the one place a page thread
// starts.
export const PAGE_DRAFT = "general";
const DRAFT_NEWS = "lf-drafts";
// What a draft holds changes only where this document's copy of it or its sending
// mask (`sentAttempts`) changes, so each of those maps tells the drafts list of every
// change it records (`listDraft`).
/** @template V @extends {Map<string, V>} */
class ListingMap extends Map {
  /** @param {string} ctx @param {V} value */
  set(ctx, value) {
    super.set(ctx, value);
    listDraft(ctx);
    return this;
  }
  /** @param {string} ctx */
  delete(ctx) {
    const had = super.delete(ctx);
    listDraft(ctx);
    return had;
  }
}
// This document's copy of each draft: the generation it shows (`record`); the one it
// last knew the server held (`stored`), or null where it holds none, as once a send or
// Cancel settled it; the server's version when this document last heard of the draft
// (`version`); whether the server holds `record` itself (`durable`); and the attempts
// of this document's writes the server hasn't answered, whose arrival in a reading is
// this document's own words (`ours`).
/** @type {ListingMap<DraftCopy>} */
const draftCache = new ListingMap();
// The generations the writes of the pages this tab reloaded carry or name, by context
// (`takeWaitingDrafts`). Any of those writes may still land, but only over a
// generation in its context's set, or where the server holds none, as any late write
// can (`drafts.py`). So once this document hears the server take a write of a
// generation outside the set, the set goes (`heardWrite`).
/** @type {Map<string, ReadonlySet<string>>} */
const inherited = new Map();
// Whether the words still waiting here go over a generation the server holds rather
// than give way to it. They go over this document's writes still unanswered, and over
// the generations the pages this tab reloaded wrote or wrote over, since the user went
// on from those pages to this one.
/** @param {string} ctx @param {DraftCopy} copy @param {string} attempt */
const superseded = (ctx, copy, attempt) =>
  copy.ours.has(attempt) || Boolean(inherited.get(ctx)?.has(attempt));
/** @param {string} ctx @param {string | null} value @param {DraftPayload} [payload] */
export const tellDraft = (ctx, value, payload = undefined) =>
  document.dispatchEvent(
    new CustomEvent(DRAFT_NEWS, { detail: { ctx, value, payload } }),
  );
/** @param {string} ctx */
const rawDraftRecord = (ctx) => draftCache.get(ctx)?.record ?? null;
/** @param {DraftRecord | null} left @param {DraftRecord | null} right */
const sameDraftRecord = (left, right) =>
  left === right ||
  (left !== null &&
    right !== null &&
    left.attempt === right.attempt &&
    left.settled === right.settled &&
    left.text === right.text &&
    left.held === right.held &&
    JSON.stringify(left.payload) === JSON.stringify(right.payload));
// Publish a generation the server handed this document after the current call returns,
// so every mounted view follows the copy without making a composer's synchronous close
// clear itself recursively.
/** @param {string} ctx @param {DraftRecord | null} record */
const projectDraftRecord = (ctx, record) =>
  queueMicrotask(() => {
    const current = draftCache.get(ctx)?.record ?? null;
    if (!sameDraftRecord(current, record)) return;
    const active = current && !current.settled;
    tellDraft(ctx, active ? current.text : null, active ? current.payload : undefined);
  });

// The server's record as this document keeps it, less the version it carries apart.
/** @param {ServedDraft | DraftWriteAnswer["record"]} record @returns {DraftRecord | null} */
const recordOf = (record) => {
  if (record === null) return null;
  const { version: _, ...rest } = record;
  return /** @type {DraftRecord} */ (rest);
};
// Take the server's generation of a draft, which owns it: a record, or none where
// the reading holds none, as it holds none of a generation sent or put away.
/** @param {string} ctx @param {DraftRecord | null} record @param {number} version */
function adopt(ctx, record, version) {
  const shown = rawDraftRecord(ctx);
  const next =
    record ??
    (shown && !shown.settled ? { attempt: shown.attempt, settled: true } : shown);
  if (next === null) return;
  moving.delete(ctx);
  draftCache.set(ctx, {
    record: /** @type {DraftRecord} */ (next),
    stored: next.settled ? null : next.attempt,
    version,
    durable: true,
    ours: new Set(),
  });
  if (!sameDraftRecord(shown, next)) projectDraftRecord(ctx, next);
}

// The newest drafts version this document has taken, from a reading or from a write
// that was the only change since one; whether a look heard the store go back; and the
// reading out. A store holds no drafts until its first write moves it past 0, so a
// document served without them reads them only once the news names one.
let heardVersion = 0;
let restoring = false;
// Counts the times the store went back, so an answer to a write sent before one says
// nothing of the store the server holds now.
let restores = 0;
/** @type {Promise<void> | null} */
let reading = null;
// Take a reading of the server's drafts. A draft this document heard of at the
// reading's version or later keeps what it has, as the reading may have been taken
// before a write this document's answer already told it of. A draft whose words still
// wait to reach the server keeps them over the generation they replace, none, or one
// they supersede (`superseded`), and gives them up to anything else, which another
// tab or device wrote later.
/** @param {DraftsReading} drafts @param {boolean} restored */
function hearReading({ version, drafts }, restored) {
  if (restored) {
    // The server went back to an older store, as one restarting from a saved copy of
    // its page does (`lookForDrafts`): the words this document holds that it lost, and
    // the settlements it lost, go back to it over what it now holds.
    restores += 1;
    for (const [ctx, copy] of draftCache)
      draftCache.set(ctx, {
        ...copy,
        version: 0,
        ...(!copy.record.settled || drafts[ctx]
          ? { stored: drafts[ctx]?.attempt ?? null, durable: false }
          : {}),
      });
    heardVersion = version;
  }
  heardVersion = Math.max(heardVersion, version);
  for (const ctx of new Set([...draftCache.keys(), ...Object.keys(drafts)])) {
    const incoming = drafts[ctx] ?? null;
    const copy = draftCache.get(ctx);
    if (copy && (incoming ? incoming.version <= copy.version : version < copy.version))
      continue;
    if (copy && !copy.durable) {
      if (incoming === null || incoming.attempt === copy.stored) continue;
      if (superseded(ctx, copy, incoming.attempt)) {
        draftCache.set(ctx, { ...copy, stored: incoming.attempt });
        continue;
      }
    }
    adopt(ctx, recordOf(incoming), incoming?.version ?? version);
  }
  writeWaiting();
}
// A look at the server, taken from the version this document had heard as it set out,
// which the server had already reached: the drafts version the look answers with moves
// with every write, and is older only where the store went back. A look that reaches
// the server also sends on the words waiting for it.
export function lookForDrafts() {
  const floor = heardVersion;
  return (/** @type {number} */ version) => {
    if (version < floor) restoring = true;
    hearDrafts(version);
  };
}
/** @param {number} version */
function hearDrafts(version) {
  writeWaiting();
  if (reading || (version <= heardVersion && !restoring)) return;
  const restored = restoring;
  restoring = false;
  reading = fetch(pageUrl("api/drafts"), { headers: layerHeaders() })
    .then(async (response) => {
      if (!admitResponse(response))
        throw new Error("drafts belong to another delivery");
      if (!response.ok) throw new Error(`drafts returned HTTP ${response.status}`);
      hearReading(/** @type {DraftsReading} */ (await response.json()), restored);
    })
    .catch(() => {
      restoring ||= restored;
    })
    .finally(() => (reading = null));
}

// The writes of each draft go to the server one at a time: words typed while one is
// out wait behind it, the latest in place of any that waited before them, so a
// keystroke costs this document a map write and the server a request for each answer
// it gives. An exported page has no server, so its drafts last as long as its tab.
/** @type {Map<string, DraftRecord>} */
const writing = new Map();
/** @param {string} context @param {(string | null)[]} expect the generations the write
 * may replace, null for none @param {DraftRecord} record @param {boolean} [keepalive] */
async function postDraft(context, expect, record, keepalive = false) {
  const response = await fetch(pageUrl("api/draft"), {
    method: "POST",
    // The runtime it names keeps a tab from before an update from writing a shape a
    // newer runtime reads (`_runtime_gate`).
    headers: layerHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      context,
      expect: expect.filter((attempt) => attempt !== null),
      record,
    }),
    keepalive,
  });
  if (!admitResponse(response))
    throw new Error("draft answer belongs to another delivery");
  if (!response.ok) throw new Error(`draft write returned HTTP ${response.status}`);
  return /** @type {DraftWriteAnswer} */ (await response.json());
}
/** @param {string} ctx */
function writeDraft(ctx) {
  const copy = draftCache.get(ctx);
  if (!copy || copy.durable || writing.has(ctx) || offlineInteractive) return;
  const sent = copy.record;
  const epoch = restores;
  writing.set(ctx, sent);
  draftCache.set(ctx, { ...copy, ours: new Set([...copy.ours, sent.attempt]) });
  void postDraft(ctx, [copy.stored], sent).then(
    (answer) => {
      writing.delete(ctx);
      if (epoch === restores) heardWrite(ctx, sent, answer);
      writeDraft(ctx);
    },
    () => writing.delete(ctx),
  );
}
const writeWaiting = () => {
  for (const ctx of draftCache.keys()) writeDraft(ctx);
};
// A page going away sends the words still waiting again, in requests the browser
// finishes after it (`keepalive`, which carries only a small body), since leaving may
// cancel a write already out, often before this listener runs. The server may have
// taken that write all the same, or another whose answer never came back, so each
// resend names every generation this document wrote since it last heard an answer
// (`ours`) beside the one it knew the server held: whichever the server holds, the
// newest words replace it.
//
// A reload can be served its drafts before those writes land, and the words typed on
// arrival would then go over an older generation than the resend's and lose to it. So
// the page also leaves in the tab, for each draft, the generations its writes that
// may still land carry or name (`inherited` included), and its copy of a draft still
// waiting (`WAITING_DRAFTS`), and its reload starts from them (`takeWaitingDrafts`).
// The reload shows the newest words at once, and the words it has yet to send go over
// any of those writes, whichever lands and when (`superseded`), so the words typed
// after the reload stand. A generation this document is sending leaves its
// generations but not its copy, since only the server's answer says whether the log
// took those words.
const WAITING_DRAFTS = "lf-drafts-waiting";
addEventListener("pagehide", () => {
  if (offlineInteractive) return;
  /** @type {[string, WaitingDraft][]} */
  const waiting = [];
  for (const ctx of new Set([...draftCache.keys(), ...inherited.keys()])) {
    const copy = draftCache.get(ctx);
    const earlier = [...(inherited.get(ctx) ?? [])];
    if (!copy || copy.durable) {
      if (earlier.length) waiting.push([ctx, { attempts: earlier, copy: null }]);
      continue;
    }
    const { record, stored, version } = copy;
    draftCache.set(ctx, { ...copy, ours: new Set([...copy.ours, record.attempt]) });
    const unanswered = [...copy.ours, ...earlier];
    void postDraft(ctx, [stored, ...unanswered], record, true).catch(() => {});
    const sending = sentAttempts.get(ctx) === record.attempt;
    waiting.push([
      ctx,
      {
        attempts: [...unanswered, record.attempt, ...(stored ? [stored] : [])],
        copy: sending ? null : { record, stored, version },
      },
    ]);
  }
  tabStore.set(WAITING_DRAFTS, waiting.length ? JSON.stringify(waiting) : null);
});
// What the page this tab reloaded left waiting, taken once. Any other arrival in the
// tab, such as a return through history, can come long after its writes landed, and
// the server keeps no record of words put away since, so a replay then would stand
// them up again.
function takeWaitingDrafts() {
  const left = tabStore.get(WAITING_DRAFTS);
  tabStore.set(WAITING_DRAFTS, null);
  const reloaded =
    /** @type {PerformanceNavigationTiming | undefined} */ (
      performance.getEntriesByType("navigation")[0]
    )?.type === "reload";
  if (!left || !reloaded) return;
  try {
    for (const [ctx, { attempts, copy }] of /** @type {[string, WaitingDraft][]} */ (
      JSON.parse(left)
    )) {
      inherited.set(ctx, new Set(attempts));
      if (copy) draftCache.set(ctx, { ...copy, durable: false, ours: new Set() });
    }
  } catch {
    // Unreadable copies leave the drafts the document was served with.
  }
}
// How many drafts hold words the server hasn't taken yet, for a check that reads what
// another tab or device would find.
export const draftsWaiting = () =>
  [...draftCache.values()].filter(({ durable }) => !durable).length;
// Words whose box is gone move into the page's draft (`transferDraft`), and leave the
// draft they came from once the server holds them there: once it takes the generation
// carrying them, or a later one this document wrote over it (`carrying`). Words
// another tab or device wrote there meanwhile turn them away, and they stay where they
// were.
/** @type {Map<string, {from: string, attempt: string, carrying: WeakSet<DraftRecord>}>} */
const moving = new Map();
// The server's answer to a write: the draft as it now holds it. A generation this
// document's words supersede (`superseded`) leaves them standing; any other is later
// words of another tab's or device's, which own the draft.
/** @param {string} ctx @param {DraftRecord} sent @param {DraftWriteAnswer} answer */
function heardWrite(ctx, sent, { written, version, record }) {
  if (written && !inherited.get(ctx)?.has(sent.attempt)) inherited.delete(ctx);
  const copy = draftCache.get(ctx);
  // A reading taken since may already have said more than this answer does.
  if (!copy || copy.version > version) return;
  const held = recordOf(record);
  const own = written || Boolean(held && superseded(ctx, copy, held.attempt));
  const move = moving.get(ctx);
  if (move && written && move.carrying.has(sent)) {
    moving.delete(ctx);
    const settled = settleDraft(move.from, move.attempt);
    if (settled) projectDraftRecord(move.from, settled);
  }
  if (!own) {
    adopt(ctx, held, record?.version ?? version);
    return;
  }
  // A write that was the only change since the reading this document took leaves it
  // holding the next one, which a look need not read again.
  if (written && version === heardVersion + 1) heardVersion = version;
  // Words the log already took, whose write reached the server after their event, are
  // settled there (`drafts.py`, `sent`), and here too unless typed over since.
  const spoken = written && !held && !sent.settled && copy.record === sent;
  draftCache.set(ctx, {
    ...copy,
    record: spoken ? { attempt: sent.attempt, settled: true } : copy.record,
    stored: held && !held.settled ? held.attempt : null,
    version: Math.max(copy.version, version),
    durable: copy.durable || (written && copy.record === sent),
    ours: new Set(),
  });
  if (spoken) projectDraftRecord(ctx, rawDraftRecord(ctx));
}

// A message draft is kept under what it is written about, and it stays there until it
// is sent or put away. The contexts below, named only here, say which subject each
// draft is about. Threads lists the drafts under Drafts (`draftsReading`;
// floating-panel.js, `draftsListing`), and a press on a row or Resume writing brings the
// user back to one (`createWritingResume`). Opening another box opens that box's own
// draft and moves no words into it. Rejected: an explicit Comment on
// another target, or `c` into a thread, moving the unsent words there. Words move only
// when their box is gone, into the page's draft (`moveToPage`).
// - `page`: the page's own comment, the floating panel's field (`PAGE_DRAFT`);
// - `comment`: a comment on a passage or element, under its anchor's key
//   (composing/selection.js, `anchorKey`), its record holding the anchor;
// - `reply`: a thread's reply box, under the thread's key (`threadKey`, a first
//   message's attempt until the log names the thread);
// - `rewrite`: a rewrite of a message, under that message's id (thread/message-edit.js).
// Any other draft, such as a widget's edit, is a value rather than a message.
/** @typedef {"comment" | "reply" | "rewrite"} DraftPart */
/** @type {Record<DraftPart, string>} */
const PREFIX = {
  comment: "composer:",
  reply: "reply:",
  rewrite: "rewrite:",
};
/** @param {string} key */
export const commentContext = (key) => PREFIX.comment + key;
/** @param {string} key */
export const replyContext = (key) => PREFIX.reply + key;
/** @param {string} id */
export const rewriteContext = (id) => PREFIX.rewrite + id;

// Which message draft `ctx` is, with the key or id it is under; null for any other.
/** @param {string} ctx @returns {{part: DraftPart, name: string} | {part: "page", name: null} | null} */
function draftSubject(ctx) {
  if (ctx === PAGE_DRAFT) return { part: "page", name: null };
  for (const [part, prefix] of /** @type {[DraftPart, string][]} */ (
    Object.entries(PREFIX)
  ))
    if (ctx.startsWith(prefix)) return { part, name: ctx.slice(prefix.length) };
  return null;
}
// The drafts a thread holds: its reply box and a rewrite of one of its messages.
/** @param {string} ctx @returns {{part: "reply" | "rewrite", name: string} | null} */
export function threadDraft(ctx) {
  const subject = draftSubject(ctx);
  return subject?.part === "reply" || subject?.part === "rewrite"
    ? { part: subject.part, name: subject.name }
    : null;
}
/** @param {string} ctx */
const isReply = (ctx) => threadDraft(ctx)?.part === "reply";
// What a box that stops showing the user's words says, once, with the address that
// brings them back.
export const DRAFT_KEPT = "Draft kept — g i resumes writing";

// A generation this document has sent and not heard back on. Its words are shown
// wherever the gesture drew them, so the box they were written in reads empty, while
// the record itself stands, unsettled, until the log accepts it. The two are different
// facts: what a box shows is about this document, and settlement is a claim over every
// tab. That is what lets a second tab still show and send the same generation, and what
// brings the words back here on a refusal with nothing to restore them from.
/** @type {ListingMap<string>} */
const sentAttempts = new ListingMap(); // ctx -> attempt

/** @param {string} ctx */
const unsettledDraftRecord = (ctx) => {
  const record = rawDraftRecord(ctx);
  return record && !record.settled ? record : null;
};
/** @param {string} ctx */
const activeDraftRecord = (ctx) => {
  const record = unsettledDraftRecord(ctx);
  return sentAttempts.get(ctx) === record?.attempt ? null : record;
};
// Sending hides a generation's words while its result stands on screen, but does
// not end its editor's lifetime: refusal still owes those words that same editor.
/** @param {string} ctx */
export const draftHasContent = (ctx) => Boolean(unsettledDraftRecord(ctx)?.text);
/** @param {string} ctx @param {DraftRecord} record */
const keepDraft = (ctx, record) => {
  const copy = draftCache.get(ctx);
  const move = moving.get(ctx);
  if (move && copy && move.carrying.has(copy.record)) move.carrying.add(record);
  draftCache.set(ctx, {
    record,
    stored: copy?.stored ?? null,
    version: copy?.version ?? 0,
    durable: false,
    ours: copy?.ours ?? new Set(),
  });
  writeDraft(ctx);
};
// Every settlement is an ownership claim, whether it follows Send, Cancel or a widget
// action. It settles only the generation it names, and the server takes it only over
// the generation this document last knew it held, so a view that missed a newer edit
// elsewhere hears that edit back rather than settling it.
/** @param {string} ctx @param {string} attempt */
const settleDraft = (ctx, attempt) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled || current.attempt !== attempt) return null;
  /** @type {SettledDraft} */
  const record = { attempt, settled: true };
  keepDraft(ctx, record);
  return record;
};
/** @param {string} ctx @param {string} text @param {DraftPayload} [payload] @param {string | null} [held] */
export const saveDraft = (ctx, text, payload, held = carriedHeld(ctx)) =>
  keepDraft(ctx, {
    attempt: randomId(),
    text,
    ...(payload === undefined ? {} : { payload }),
    ...(held ? { held } : {}),
  });
// A reply a refusal handed back to the draft whose message opened its thread
// (`keepRefusedWords`) is part of that draft: every edit of it keeps the reply, and
// whatever moves the draft moves the reply with it (`transferDraft`). A generation in
// flight has already put its reply in the thread its send opened (`sendMessage`), so an
// edit made meanwhile starts without it.
/** @param {string} ctx */
const carriedHeld = (ctx) => {
  const previous = rawDraftRecord(ctx);
  return previous && !previous.settled && sentAttempts.get(ctx) !== previous.attempt
    ? previous.held
    : undefined;
};
// Set the held reply on the draft's current generation without minting another: the
// refused attempt stays the one a resend re-evaluates.
/** @param {string} ctx @param {string} held */
const holdReply = (ctx, held) => {
  const current = activeDraftRecord(ctx);
  if (!current) return false;
  const { held: _, ...rest } = current;
  keepDraft(ctx, held ? { ...rest, held } : rest);
  return true;
};
/** @param {string} ctx */
export const clearDraft = (ctx) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled) return false;
  return settleDraft(ctx, current.attempt);
};
// Words whose box is gone move into the page's draft (`moveToPage`), the one move a
// draft makes. The source settles once the server holds the words in the page's draft
// (`moving`), so a destination write it turns away never discards them. Every live
// destination view reads the same moved draft. The move also moves Resume writing,
// with the source's caret, and the reply the source holds (`held`).
/** @param {string} from @param {string} to @param {string} text */
function transferDraft(from, to, text) {
  const source = activeDraftRecord(from);
  if (!source || from === to) return false;
  const editor =
    [...draftEditors].find((view) => view.ctx === from) ??
    [...draftEditors].find((view) => view.ctx === to);
  const selection =
    writingPlace?.context === from
      ? writingPlace.selection
      : readCaret(editor ? editorInput(editor) : null);
  // A destination already holding a reply keeps it, with the source's after it.
  const held =
    [carriedHeld(to), carriedHeld(from)].filter(Boolean).join("\n\n") || null;
  saveDraft(to, text, undefined, held);
  /** @type {WritingPlace & {selection: Caret}} */
  const place = {
    context: to,
    selection: selection ?? [0, 0],
    generation: randomId(),
  };
  keepWritingPlace(place);
  const moved = rawDraftRecord(to);
  if (offlineInteractive || !moved) {
    const settled = settleDraft(from, source.attempt);
    if (settled) projectDraftRecord(from, settled);
  } else
    moving.set(to, { from, attempt: source.attempt, carrying: new WeakSet([moved]) });
  tellDraft(to, activeDraftRecord(to)?.text ?? text);
  return place;
}
// Put words the user put away back into `ctx`, as a new generation every view shows,
// unless it holds words of its own: those are newer than the words coming back.
/** @param {string} ctx @param {string} text @param {DraftPayload} [payload] */
export function restoreDraft(ctx, text, payload) {
  if (draftHasContent(ctx)) return false;
  saveDraft(ctx, text, payload);
  tellDraft(ctx, text, payload);
  return true;
}
/** @param {string} ctx */
export const loadDraft = (ctx) => activeDraftRecord(ctx);
export const draftContexts = () => [...draftCache.keys()];
// ---------- the drafts list ----------
// Every message draft holding words or a drawing, as this document shows it, in no
// order: a generation it is sending stands on screen as the message, not as a draft.
// The page's own draft isn't listed: the floating panel's field shows it and no view of
// drafts does, so listing it would repaint every view of drafts as the field's words
// start and end. It is the one list every view of drafts reads: Threads' Drafts band and the
// On Me mark's dot (floating-panel.js), and each draft's margin entry. It publishes when
// a draft starts or stops holding something or what it is about changes, so a
// keystroke in a draft already listed costs one comparison and repaints nothing; a
// view reads the draft's words where it draws them (`loadDraft`).
/** @typedef {{part: DraftPart, name: string, context: string, payload: DraftPayload | undefined}} ListedDraft */
/** @type {Map<string, ListedDraft>} */
const listing = new Map();
const listed = signal(/** @type {readonly ListedDraft[]} */ (Object.freeze([])));
export const draftsReading = () => listed.value;
// What a listing shows of a draft's payload: where it is, whether it suggests, what it
// is about and its drawing. Another tab's write arrives as new objects alike in content.
const LISTED = ["anchor", "suggest", "about", "drawing"];
/** @param {DraftPayload | undefined} payload @param {string} key */
const field = (payload, key) =>
  /** @type {Record<string, unknown> | undefined} */ (payload)?.[key];
/** @param {DraftPayload | undefined} was @param {DraftPayload | undefined} now */
const listsAlike = (was, now) =>
  LISTED.every((key) => {
    const [a, b] = [field(was, key), field(now, key)];
    return a === b || JSON.stringify(a) === JSON.stringify(b);
  });
/** @param {string} ctx */
function listDraft(ctx) {
  const subject = draftSubject(ctx);
  if (!subject || subject.part === "page") return;
  const record = activeDraftRecord(ctx);
  const holds = Boolean(record?.text.trim() || field(record?.payload, "drawing"));
  const was = listing.get(ctx);
  if (!holds && !was) return;
  if (holds && was && listsAlike(was.payload, record?.payload)) return;
  if (holds) listing.set(ctx, { ...subject, context: ctx, payload: record?.payload });
  else listing.delete(ctx);
  listed.value = Object.freeze([...listing.values()]);
}
// Where on the page a listed draft is about, as an anchor: a comment's. A reply or
// rewrite has none of its own; it stands where its thread does.
/** @param {ListedDraft} draft @returns {import('../types/domain.js').Anchor | null} */
export const draftAnchor = (draft) => {
  if (draft.part !== "comment") return null;
  const anchor = /** @type {import('../types/domain.js').Anchor | undefined} */ (
    field(draft.payload, "anchor")
  );
  return anchor ?? null;
};
// What Send makes of a listed draft, the word every view of it ends on.
/** @param {ListedDraft} draft */
export const draftSends = (draft) =>
  ({
    comment: field(draft.payload, "suggest") ? "Suggestion" : "Comment",
    reply: "Reply",
    rewrite: "Edit",
  })[draft.part];

// One draft generation has one attempt across every tab showing this page. Two tabs may
// POST it together; the append-locked log returns the same event to both. The attempt is
// also what lets a replacement tab recover after the first sender dies.
//
// A successful older send settles only that generation; any later edit has a fresh
// attempt and remains open. This is the claim both senders below make, and the only
// thing they share: a send that no longer owns its generation appends nothing, whichever
// lifecycle it is in.
/** @param {string} ctx @param {() => boolean} owns */
function claimDraft(ctx, owns) {
  const current = activeDraftRecord(ctx);
  return current && owns() ? current : null;
}

// Both senders below stage the same way, because both draw their result in the document
// before the log has answered: `post` paints the message in its thread, and a dispatched
// action paints its projected outcome. So the box stops showing words the user can now
// see painted, while the record keeps them — one copy of the words on screen, and a
// generation still owed an answer. Acceptance settles exactly that generation. A refusal
// withdraws the result and lifts the mask, so the box the user typed in has the words
// again; the record stood in the store throughout, which is what a tab that went down
// with the send recovers from.
/** @param {string} ctx @param {ActiveDraft} current */
const standGesture = (ctx, current) => {
  sentAttempts.set(ctx, current.attempt);
  tellDraft(ctx, null);
  return (/** @type {unknown} */ sent) => {
    // Lift this generation's mask, not whatever is current for the context: a second
    // send into the box this one emptied has masked its own words by the time this
    // answer arrives, and they are on screen as a gesture of their own.
    if (sentAttempts.get(ctx) === current.attempt) sentAttempts.delete(ctx);
    if (sent) {
      if (settleDraft(ctx, current.attempt)) tellDraft(ctx, null);
      return;
    }
    // A later edit of their own has a fresh attempt and is not this generation, and
    // keeps the box.
    if (activeDraftRecord(ctx)?.attempt !== current.attempt) return;
    tellDraft(ctx, current.text);
  };
};

// An action the sender waits on: a widget edit, an added option. Its dispatch paints the
// projected outcome before the delivery it returns resolves, so the words are already
// shown in the document by the time this awaits them. The caller's own control shows
// the wait.
/** @template T @param {string} ctx @param {() => boolean} owns
 * @param {(attempt: string, payload: DraftPayload | undefined) => T | PromiseLike<T>} send @returns {Promise<T | null>} */
export async function sendDraft(ctx, owns, send) {
  const current = claimDraft(ctx, owns);
  if (!current) return null;
  const flight = send(current.attempt, current.payload);
  const answer = standGesture(ctx, current);
  const sent = await flight;
  answer(sent);
  return sent;
}

// A message, whose result is the words themselves. `post` stages and paints it before it
// returns, so the caller continues against a thread the user can already see and the
// round trip happens behind them.
//
// The returned handle names the message the send drew. It is what a caller opens or
// focuses, and the log's answer renames that same node rather than replacing it. A send
// the page refuses before posting, such as a reply to a thread being settled, drew
// nothing: the words stay in the box and the caller hears null, as for a draft it could
// not claim.
/** @param {string} ctx @param {() => boolean} owns @param {(attempt: string, payload: DraftPayload | undefined) => unknown} send */
export function sendMessage(ctx, owns, send) {
  const current = claimDraft(ctx, owns);
  if (!current) return null;
  const flight = send(current.attempt, current.payload);
  const answer = standGesture(ctx, current);
  if (!flight) {
    answer(null);
    return null;
  }
  // A first message opens a thread keyed by its attempt. Until the log takes it, the
  // draft it was sent from owns what is written under it, and a reply a refusal handed
  // back to that draft (`held`) stands in the box of the thread this send opens.
  if (!isReply(ctx)) {
    openedFrom.set(current.attempt, ctx);
    const under = replyContext(current.attempt);
    if (current.held && !activeDraftRecord(under)) {
      saveDraft(under, current.held);
      tellDraft(under, current.held);
    }
  }
  // A sent first message now has a durable conversation identity: its attempt is
  // the thread key before and after admission. Continue there, with an empty reply.
  // Refusal returns to the same original editor unless a later edit chose another.
  const previousPlace = writingPlace;
  /** @type {WritingPlace | null} */
  const sentPlace =
    previousPlace?.context === ctx
      ? {
          context: isReply(ctx) ? ctx : replyContext(current.attempt),
          selection: [0, 0],
          generation: previousPlace.generation,
        }
      : null;
  if (sentPlace) keepWritingPlace(sentPlace);
  void Promise.resolve(flight).then((sent) => {
    answer(sent);
    if (sent) openedFrom.delete(current.attempt);
    if (
      !sent &&
      sentPlace &&
      writingPlace?.generation === sentPlace.generation &&
      writingPlace.context === sentPlace.context
    )
      keepWritingPlace(previousPlace);
  });
  return { attempt: current.attempt, id: `${PENDING}${current.attempt}` };
}

// The draft each first message still in flight was sent from, by its attempt. The
// draft, not the attempt, is what lasts: a refusal keeps the attempt only until the
// user edits the words, and the thread comes back under whichever one is sent.
/** @type {Map<string, string>} */
const openedFrom = new Map();

// Existing draft subscriptions own current editor identity and lifetime. The store
// supplies active words and an optional submission payload, or null and no payload
// for settlement. Editor membership is mechanical: connected root editors recover
// by context, and retained reply mirrors land through their current thread owner.
// Unsubscribing retires that membership alongside the listener.
//
// It does not run on subscribe, which is where this parts company with controller state. The
// draft a box opens with and the news that another tab changed one are different facts,
// and the boxes answer them differently: a draft editor opens on recovery at load and
// stays shut for a keystroke made elsewhere, because news arriving has no gesture behind
// it and so may move nothing.
/** @type {Set<DraftEditor>} */
const draftEditors = new Set();

// Resume writing is mechanical page state, owned alongside editor identity. Only a
// content edit changes its destination; focus, draft mirroring and automatic recovery do
// not. The one context and caret survive reload with the words. Reveal capabilities
// belong to the editor's existing owner, and reply mirrors use the canonical thread
// destination supplied by the composition root. No editor node is stored as identity.
// The places written in before the current one stand behind it, newest last, one for
// each context, so a place whose words are put away hands Resume writing back to the
// latest earlier one still holding words; they survive reload with it. Where the user
// was writing is this browser's (`writingStore`), though the words are every device's.
const WRITING_PLACE = "lf-writing-place";
/** @param {unknown} place @returns {place is WritingPlace} */
const isPlace = (place) => {
  if (
    place === null ||
    typeof place !== "object" ||
    !("context" in place) ||
    typeof place.context !== "string" ||
    !("generation" in place) ||
    typeof place.generation !== "string" ||
    !("selection" in place) ||
    !Array.isArray(place.selection)
  )
    return false;
  const [start, end, direction] = place.selection;
  return (
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    (direction === undefined ||
      direction === "forward" ||
      direction === "backward" ||
      direction === "none")
  );
};
/** @returns {[WritingPlace | null, WritingPlace[]]} */
const savedWritingPlaces = () => {
  try {
    const value = writingStore.get(WRITING_PLACE);
    if (value === null) return [null, []];
    const stored = JSON.parse(value);
    if (!isPlace(stored)) return [null, []];
    const earlier =
      "earlier" in stored && Array.isArray(stored.earlier)
        ? stored.earlier.filter(isPlace)
        : [];
    const { context, selection, generation } = stored;
    return [{ context, selection, generation }, earlier];
  } catch {
    return [null, []];
  }
};
let [writingPlace, earlierPlaces] = savedWritingPlaces();
/** @type {Map<string, (ctx: string) => EditorDestination | null>} */
const writingRoutes = new Map();
/** @param {string} ctx */
const writingRoute = (ctx) =>
  [...writingRoutes].find(([prefix]) => ctx.startsWith(prefix))?.[1];
/** @param {DraftEditor} editor */
const editorInput = (editor) =>
  typeof editor.input === "function" ? editor.input() : editor.input;
const storeWritingPlace = () =>
  writingStore.set(
    WRITING_PLACE,
    writingPlace && JSON.stringify({ ...writingPlace, earlier: earlierPlaces }),
  );
/** @param {WritingPlace | null} place */
const keepWritingPlace = (place) => {
  const previous = writingPlace;
  if (previous && place && previous.context !== place.context)
    earlierPlaces = [
      ...earlierPlaces.filter(
        ({ context }) => context !== previous.context && context !== place.context,
      ),
      previous,
    ].slice(-8);
  writingPlace = place;
  storeWritingPlace();
};
// Words put away, discarded or sent, leave nowhere to resume there: Resume writing goes
// back to the latest place still holding words, or a destination its owner can resume
// without words, as a drawing's composer.
/** @param {string} ctx */
export function forgetWritingPlace(ctx) {
  earlierPlaces = earlierPlaces.filter(({ context }) => context !== ctx);
  if (writingPlace?.context !== ctx) return storeWritingPlace();
  writingPlace = null;
  let place;
  while (!writingPlace && (place = earlierPlaces.pop())) {
    if (
      draftHasContent(place.context) ||
      writingRoute(place.context)?.(place.context)?.hasContent
    )
      writingPlace = place;
  }
  storeWritingPlace();
}
// The end of a draft's words: its length, which the editor clamps to the end of its
// words, since any attached images follow them.
/** @param {string} ctx @returns {Caret} */
const atEnd = (ctx) => {
  const end = (activeDraftRecord(ctx)?.text ?? "").length;
  return [end, end];
};
// Words an undo took back from the log, given back to the draft they were written in
// (undo.js, `withdraw`), so taking a message back puts it to draft rather than
// discarding it. They come first, then the words of the box `under` them, the reply box
// of a thread that went with them, then any words the draft holds now, which the user
// wrote after them. A draft holding something of its own keeps its own `payload`, such
// as the passage and mode of a comment begun since, taking only a drawing it lacks; one
// holding nothing takes the words'. A new generation, so the log's record of the send
// settles nothing here (`drafts.py`). They are the user's newest unsent words, so
// Resume writing goes to their end, wherever the box stands.
/** @param {string} ctx @param {string} text @param {DraftPayload} [payload] @param {string | null} [under] */
export function giveBackWords(ctx, text, payload, under = null) {
  const current = activeDraftRecord(ctx);
  const own =
    current && (current.text || field(current.payload, "drawing")) ? current : null;
  const reply = under === null ? null : activeDraftRecord(under);
  const words = [text, reply?.text, own?.text].filter(Boolean).join("\n\n");
  const drawing = field(payload, "drawing");
  const kept = !own
    ? payload
    : drawing && !field(own.payload, "drawing")
      ? { ...own.payload, drawing }
      : own.payload;
  saveDraft(ctx, words, kept);
  tellDraft(ctx, words, kept);
  if (reply && under !== null) clearDraft(under);
  keepWritingPlace({ context: ctx, selection: atEnd(ctx), generation: randomId() });
}
// What a refusal left the user, given every attempt it refused, read once each sender's
// own answer has returned its words (`standGesture`) and any owner has reopened its box
// for them.
//
// A thread this tab opened goes with its first message, and with it the box under it,
// whose draft keys by that message's attempt (`reply:<attempt>`), whether its words were
// sent behind the message or still unsent. That box began with any reply the draft held,
// so its words now are the draft's held reply (`held`), part of the draft the message
// was sent from (`openedFrom`), which brings them to the thread its next send opens,
// edited, carried elsewhere or not (`sendMessage`). Resume writing, shown in the
// withdrawn box, moves to that draft, the one place the user acts to get them back.
//
// Words back in a box on screen need no sentence. Words back only in a box out of view
// are the ones a refusal otherwise appears to lose, so they become the Resume writing
// destination, a content change to that draft like any other, and the refusal's error
// carries the sentence naming that address (delivery.js). The error is about the box on
// screen the sending gesture's words came back to, where there is one (`field`).
//
// Resume writing comes back to words a refusal handed back at their end (`atEnd`), as a
// press on the error over them does (composing/input.js), so Enter sends them.
/** @param {readonly string[]} attempts */
export function keepRefusedWords(attempts) {
  let held = 0;
  for (const attempt of attempts) {
    const from = openedFrom.get(attempt);
    openedFrom.delete(attempt);
    const under = replyContext(attempt);
    const box = activeDraftRecord(under);
    if (from === undefined || !box || !holdReply(from, box.text)) continue;
    const resumed = writingPlace?.context === under;
    clearDraft(under);
    if (resumed)
      keepWritingPlace({
        context: from,
        selection: atEnd(from),
        generation: randomId(),
      });
    if (box.text) held += 1;
  }
  const returned = attempts.flatMap((attempt) => {
    const ctx = [...draftContexts()].find(
      (context) => activeDraftRecord(context)?.attempt === attempt,
    );
    return ctx === undefined ? [] : [ctx];
  });
  /** @param {string} ctx */
  const shownIn = (ctx) =>
    [...draftEditors]
      .filter((view) => view.ctx === ctx)
      .map((view) => editorInput(view))
      .find((input) => input?.isConnected && input.checkVisibility()) ?? null;
  const hidden = returned.filter((ctx) => !shownIn(ctx));
  // Words back where Resume writing already goes are resumed at their end too, not at
  // the caret the send left.
  const resumes = returned.find((ctx) => ctx === writingPlace?.context);
  if (resumes !== undefined && writingPlace)
    keepWritingPlace({ ...writingPlace, selection: atEnd(resumes) });
  // The gesture delivery was sending comes first, so it is the place Resume writing
  // reaches first, and the others stand behind it.
  for (const ctx of hidden.toReversed())
    if (writingPlace?.context !== ctx)
      keepWritingPlace({ context: ctx, selection: atEnd(ctx), generation: randomId() });
  const sentences = [
    hidden.length && DRAFT_KEPT,
    held && "Reply kept — it comes back once its comment is saved",
  ].filter(Boolean);
  return {
    said: sentences.length ? sentences.join(". ") : null,
    field: returned.map(shownIn).find(Boolean) ?? null,
  };
}
const writingEditor = () =>
  [...draftEditors].find((editor) => editorInput(editor) === focused());
const keepWritingCaret = () => {
  const editor = writingEditor();
  if (editor && editor.ctx === writingPlace?.context)
    keepWritingPlace({ ...writingPlace, selection: readCaret(editorInput(editor)) });
};
/** @param {DraftField | null} input */
export function rememberWriting(input) {
  const editor = [...draftEditors].find((view) => editorInput(view) === input);
  if (editor)
    keepWritingPlace({
      context: editor.ctx,
      selection: readCaret(input),
      generation: randomId(),
    });
}
document.addEventListener("input", (event) => {
  const path = event.composedPath();
  const editor = [...draftEditors].find((view) => {
    const input = editorInput(view);
    return input !== null && path.includes(input);
  });
  if (editor) rememberWriting(editorInput(editor));
});
// In capture, since a key typed in the editor stops at it (field-keys.js).
document.addEventListener(
  "keyup",
  (event) => {
    // The gesture's end, not `selectionchange`, which fires on every typed character and
    // every step of a drag: the place is stored once per gesture.
    if (CARET_KEYS.includes(event.key) || selectsAll(event)) keepWritingCaret();
  },
  true,
);
document.addEventListener("pointerup", keepWritingCaret);

/** @param {string} prefix @param {(ctx: string) => EditorDestination | null} reveal */
export function registerWritingDestination(prefix, reveal) {
  // Availability can include an empty current editor. hasContent tells fallback
  // selection whether its owner holds work beyond the shared draft's words.
  writingRoutes.set(prefix, reveal);
  return () => writingRoutes.delete(prefix);
}

// Words nothing on the active document holds a box for, as when a version removes the
// content an edit was for, join the page's own draft after the words it already holds,
// and Resume writing moves with them (`transferDraft`): one copy, sent or put away like
// any page comment. Whatever took the box away, the words now stand where a comment
// about no particular place is written.
/** @param {string} ctx */
function moveToPage(ctx) {
  const words = loadDraft(ctx)?.text ?? "";
  const text = [loadDraft(PAGE_DRAFT)?.text, words].filter(Boolean).join("\n\n");
  const place = transferDraft(ctx, PAGE_DRAFT, text);
  if (!place) return false;
  const shift = text.length - words.length;
  const [start, end, ...direction] = place.selection;
  keepWritingPlace({
    ...place,
    selection: [start + shift, end + shift, ...direction],
  });
  return true;
}

// `holdsThreadDraft` answers whether the thread or message a thread-held draft is
// written under still stands; any other draft is held by a route declared for its kind
// or an editor registered for it, each for its owner's lifetime.
//
// The command resumes the writing place; `resumeDraft` resumes the draft a press names,
// as a row of Threads' Drafts does, at the caret the place last kept for it, else at its
// words' end. Opening a draft is no content edit, so it leaves the writing place where
// it was.
/** @param {{revealInThread: (ctx: string, intent: ReturnType<typeof retainUserIntent>) => Promise<Element | null | undefined>,
 * arriveEditor: ReturnType<typeof import("./anchor-travel.js").createAnchorTravel>["arriveEditor"], holdsThreadDraft: (ctx: string) => boolean}} options
 * @returns {{command: import("./keyboard/bindings.js").Command, resumeDraft: (ctx: string) => Promise<void>}} */
export function createWritingResume({
  revealInThread,
  arriveEditor,
  holdsThreadDraft,
}) {
  /** @param {string} ctx */
  const holdsBox = (ctx) =>
    threadDraft(ctx)
      ? holdsThreadDraft(ctx)
      : Boolean(writingRoute(ctx)) ||
        [...draftEditors].some((view) => view.ctx === ctx);
  const resume = () => (writingPlace ? resumeAt(writingPlace) : Promise.resolve());
  /** @param {string} ctx */
  const resumeDraft = (ctx) =>
    resumeAt(
      [writingPlace, ...earlierPlaces].find((place) => place?.context === ctx) ?? {
        context: ctx,
        selection: atEnd(ctx),
        generation: randomId(),
      },
    );
  /** @param {WritingPlace} place @returns {Promise<void>} */
  const resumeAt = async (place) => {
    const intent = retainUserIntent();
    let input;
    // A thread view holds its own drafts, which the thread's destination reveals.
    if (threadDraft(place.context)) input = await revealInThread(place.context, intent);
    else {
      const resolve = () => {
        const route = writingRoute(place.context);
        const editor = [...draftEditors].find(
          (view) => view.ctx === place.context && view.resume,
        );
        return route ? route(place.context) : editor?.resume?.();
      };
      input = await arriveEditor(resolve, { intent, caret: place.selection });
    }
    if (input === undefined || !intent()) return;
    const editor = [...draftEditors].find(
      (view) => view.ctx === place.context && editorInput(view) === input,
    );
    const field = editor && editorInput(editor);
    if (
      field?.isConnected &&
      field.checkVisibility() &&
      !field.readOnly &&
      !("disabled" in field && field.disabled)
    ) {
      // Coming back to the words is the user dealing with any error over them, as a
      // press on it is (errors.js, `passErrorsAt`).
      intent.handoff(() => {
        passErrorsAt(field);
        focusDestination(field, "move", { caret: place.selection });
      });
      return;
    }
    // A document behind the active one may lack a box the active one holds, so only
    // the active document moves the words to the page.
    if (runtime.showsActive && !holdsBox(place.context) && moveToPage(place.context)) {
      notice("Its box is gone, so its words moved to a comment on the page");
      return resume();
    }
    // A box that stands but takes no words now, as a resolved thread's in the floating
    // panel, is no fault of the version shown.
    raiseError(
      `That writing place is unavailable${runtime.showsActive ? "" : " on this version"}`,
    );
  };
  return {
    command: {
      id: "writing.resume",
      keys: ["i"],
      title: "Resume writing",
      touch: "Resume writing",
      menu: "keys",
      travels: true,
      when: () => writingPlace !== null,
      run: resume,
    },
    resumeDraft,
  };
}

// A subscription owns its editor's context and lifetime. A context's root editor is
// the box it is written in directly, which takes the caret back after a revision.
// Replies explicitly declare mirrors and land through their thread owner.
// A revision carries mechanical editing, never another copy of the draft's words.
/** @param {Element | null} [at] */
export function captureDraftEditing(at = focused()) {
  for (const editor of draftEditors) {
    const input = editorInput(editor);
    if (!input || input !== at) continue;
    /** @type {[number, number]} */
    const scroll = [input.scrollLeft, input.scrollTop];
    return {
      context: editor.ctx,
      mirrored: editor.mirrored,
      attempt: activeDraftRecord(editor.ctx)?.attempt,
      words: input.value,
      selection: readCaret(input),
      scroll,
    };
  }
  return null;
}

/** @typedef {NonNullable<ReturnType<typeof captureDraftEditing>>} DraftEditing */
/** @param {DraftEditing | null} editing */
export const draftEditingStands = (editing) =>
  editing !== null && activeDraftRecord(editing.context)?.attempt === editing.attempt;

// The root editor a revision hands the caret back to, shown first through its owner's
// Resume writing route when a disclosure holds it shut; `handoff` gates that showing on
// the user's intent. A root off the page counts when its owner's route places it there,
// as the page comment card places its box at its first open, and so does one whose
// owner has no box until that route builds it, as a closed document edit has none.
/** @param {DraftEditing} editing @param {(move: () => unknown) => unknown} handoff */
export function draftEditingDestination(editing, handoff) {
  /** @param {DraftEditor} view */
  const shown = (view) =>
    Boolean(editorInput(view)?.checkVisibility({ visibilityProperty: true }));
  /** @param {DraftEditor} view */
  const placed = (view) => editorInput(view)?.isConnected;
  const roots = [...draftEditors].filter(
    (view) =>
      view.ctx === editing.context && !view.mirrored && (placed(view) || view.resume),
  );
  const editor = roots.find(shown) ?? roots.find(placed) ?? roots[0];
  if (!editor) return null;
  // A route may have no place to offer now, or no disclosure of its own to open.
  const open = shown(editor) ? null : editor.resume?.()?.open;
  if (open) handoff(open);
  return shown(editor) ? editorInput(editor) : null;
}

/** @param {DraftEditing} editing @param {Element | null} input */
export function restoreDraftEditing(editing, input) {
  if (!draftEditingStands(editing)) return false;
  for (const editor of draftEditors) {
    const field = editorInput(editor);
    if (!field || field !== input) continue;
    if (
      editor.ctx !== editing.context ||
      !field.isConnected ||
      !field.checkVisibility() ||
      field.value !== editing.words ||
      focused() !== field
    )
      return false;
    focusDestination(field, "return", { caret: editing.selection });
    const [left, top] = editing.scroll;
    setScroll(field, { left, top });
    return true;
  }
  return false;
}

/** @param {string} ctx @param {(value: string | null, payload?: DraftPayload) => void} callback
 * @param {{input?: DraftField | (() => DraftField | null) | null, mirrored?: boolean, resume?: (() => EditorDestination | null) | null}} [options] */
export function watchDraft(
  ctx,
  callback,
  { input = null, mirrored = false, resume = null } = {},
) {
  const editor = input && { ctx, input, mirrored, resume };
  if (editor) draftEditors.add(editor);
  /** @param {CustomEvent<DraftNews>} ev */
  const update = (ev) =>
    ev.detail.ctx === ctx && callback(ev.detail.value, ev.detail.payload);
  document.addEventListener(DRAFT_NEWS, update);
  return () => {
    document.removeEventListener(DRAFT_NEWS, update);
    if (editor) draftEditors.delete(editor);
  };
}
// News of every draft whose context starts with `prefix`, for a reader of a whole kind
// of draft rather than one box's.
/** @param {string} prefix @param {(ctx: string) => void} callback */
export function watchDrafts(prefix, callback) {
  /** @param {CustomEvent<DraftNews>} ev */
  const update = (ev) => ev.detail.ctx.startsWith(prefix) && callback(ev.detail.ctx);
  document.addEventListener(DRAFT_NEWS, update);
  return () => document.removeEventListener(DRAFT_NEWS, update);
}
// One box's view of one draft: sync.load() takes the complete durable value, splits the
// attached-media projection that is not exposed in the field back out of it, and makes
// the visible words, the media shelf, and the Send button agree. It leaves a value the
// box already holds alone, because writing .value on a focused box moves the caret to
// the end. The box grows to fit either way, sizing being the stylesheet's (wireInput).
//
// A retained editor remains a draft view during candidate detachment and receives
// concurrent draft changes before rollback reconnects it. Its owner explicitly disposes
// that lifetime on committed removal. Ordinary inputs retire on disconnection. The
// owner receives the original notification after hydration: null can mask a provisional
// send or report settlement, so its lifecycle reads canonical draft availability.
// `blank` answers what the box holds with no draft: nothing for a new message, and the
// message's own words for a rewrite of it.
/** @param {DraftField} ta @param {InputSync} sync @param {string} ctx
 * @param {{
 *   retained?: boolean,
 *   mirrored?: boolean,
 *   resume?: (() => EditorDestination | null) | null,
 *   onChange?: (value: string | null) => void,
 *   blank?: () => string,
 * }} [options] */
export function mirrorDraft(
  ta,
  sync,
  ctx,
  {
    retained = false,
    mirrored = false,
    resume = null,
    onChange = () => {},
    blank = () => "",
  } = {},
) {
  const off = watchDraft(
    ctx,
    (value) => {
      if (!retained && !ta.isConnected) return off();
      sync.load(value ?? blank());
      onChange(value);
    },
    { input: ta, mirrored, resume },
  );
  return off;
}
// Reply drafts are never pruned. A thread resolving is not a discard, so another
// tab's Resolve, or this tab accepting a suggestion whose action `resolves`,
// sweeps no unsent reply out of storage, which would lose words where the
// norm is that Cancel is the only discard. A thread a retraction reopens finds
// the draft where it was left.

// The drafts start from the copies the page this tab reloaded left waiting
// (`takeWaitingDrafts`), then those the document was served with (`lf-drafts`), heard
// as any reading is (`hearReading`); every later change reaches the list through the
// maps. A document served without them, as a release's or an export's, hears them at
// its first look, or has none.
takeWaitingDrafts();
const served = document.getElementById("lf-drafts")?.textContent;
if (served) hearReading(/** @type {DraftsReading} */ (JSON.parse(served)), false);
