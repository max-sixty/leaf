// Compiled from drafts.ts by build/typescript.mjs; edit that file.
/* The user's unsent words: one copy of each draft, which the page's server keeps for
   every tab and device, and each box's view of it.

   Every unsent composition persists:

   - the general comment box;
   - each thread reply;
   - the selection composer, including its anchor, mode and drawing;
   - a thread's first message and replies;
   - an `lf-draft` edit.

   The page's server keeps each draft (`src/leaf/serving/drafts.py`), because the words must
   survive reload, version navigation, closing the tab where they were typed, and the
   user moving to another tab or device. This document holds its copy of each
   (`draftCache`), which every box here reads and writes at once, and the copy goes on
   to the server behind the keystroke (`writeDraft`); a page going away sends what is
   still waiting, and a reload of its tab starts from its copy of it. Words typed while
   the server is out of reach stay in the tab until a look reaches it again, and
   leaving the page before then asks first (`beforeunload`), as it does over a
   comment's drawing. The server's store names itself, and within
   one store nothing this document heard goes back (`drafts.py`). A store that
   replaced the one this document heard from, as a new leaf.page release starts one,
   gets this document's words: alone where it holds nothing for their draft, and
   beside the words it holds there otherwise (`hearReading`).
   On leaf.page the first write starts the visitor's private page. An exported page
   has no server, so its drafts last as long as its tab. No failed write disables the
   live Send or Save action.

   Another tab or device hears a draft change through the look that tells it of the
   log: the look's `drafts` version moves, and the tab reads `/api/drafts`
   (`hearDrafts`). A served document arrives with the drafts it was served with
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
   another tab or device wrote in the meantime come back in its place. Nothing says
   the user no longer wants this document's words since then (SOUL.md, "Leaf drops
   words the user typed only when it knows they no longer want them"), so the draft
   becomes both, in one generation written over the other's (`adopt`). Words written
   apart are rare, and the maintainer asked for the simplest rule that loses none: a
   three-way merge would need every copy to keep the text it started from, and still
   leave conflicting edits for the user to sort. The joined draft is a new generation,
   which the log knows nothing of: where another tab sends or cancels its words while
   the answer carrying them is on its way here, they come back in the joined draft
   beside this document's, for the user to delete. Recognizing them would need each
   joined generation to record which generations it drew from. Words written over a generation another tab
   sent start the draft again, since they are newer than anything sent. The
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

   An editor's Discard and Escape throw its changed words away (`discardDraft`), as a
   message rewrite and an `lf-draft` edit do: the draft settles in every tab, as Cancel
   settles it, and the words go to the page's undo, which keeps them as a gesture ⌘Z
   takes back (records/undo.js, `keepDiscard`) and gives them back here (`giveBackWords`).

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

   An `lf-draft` editor is a live gesture. Its words are the editor's and this store's,
   never the widget's reading: remote edits and refusal correction draw the saved body
   under the open editor and leave its field alone.

   The comment over the store below says where it came from. */

import { offlineInteractive, pageUrl, runtime } from "../state/context.js";
import {
  admitResponse,
  layerHeaders,
  takeLeafUnload,
} from "../transport/layer-client.js";
import { PENDING } from "../state/thread/identity.js";
import { writingStore } from "../state/storage.js";
import { tabStore } from "../state/tab-store.js";
import { randomId } from "../base/ids.js";
import { anchorKey } from "../base/anchor-coordinate.js";
import { DRAFT_FORMAT } from "../state/kernel-facts.js";
import { focusDestination, readCaret, focused } from "../dom/focus.js";
import { readAttachedMedia, writeAttachedMedia } from "./media.js";
import { nameIn, namedIn } from "./carry.js";
import { renderedUnder } from "../lib/shadow-tree.js";
import { retainUserIntent } from "../dom/user-intent.js";
import { setScroll } from "../dom/arrivals.js";
import { CARET_KEYS, selectsAll } from "../dom/control-selectors.js";
import { passErrorsAt, raiseError } from "../transport/errors.js";
import { notice } from "../transport/notifications.js";
import { signal } from "/vendor/signals-core.js";

/** A draft's text field: a `leaf-text` (annotations/composing/text-field.js) or a textarea. */

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
class ListingMap extends Map {
  set(ctx, value) {
    super.set(ctx, value);
    listDraft(ctx);
    return this;
  }
  delete(ctx) {
    const had = super.delete(ctx);
    listDraft(ctx);
    return had;
  }
}
// This document's copy of each draft: the generation it shows (`record`); the one it
// last knew the server held (`stored`), or null where it holds none, as once a send or
// Cancel settled it; the server's store and its version when this document last heard
// of the draft (`store`, `version`), a version saying nothing of another store's;
// whether the server holds `record` itself (`durable`); and the attempts of this
// document's writes the server hasn't answered, whose arrival in a reading is this
// document's own words (`ours`).
const draftCache = new ListingMap();
// The generations the writes of the pages this tab reloaded carry or name, by context
// (`takeWaitingDrafts`). Any of those writes may still land, but only over a
// generation in its context's set, or where the server holds none, as any late write
// can (`drafts.py`). So once this document hears the server take a write of a
// generation outside the set, the set goes (`heardWrite`).
const inherited = new Map();
// Whether the words still waiting here go over a generation the server holds rather
// than join it. They go over this document's writes still unanswered, and over
// the generations the pages this tab reloaded wrote or wrote over, since the user went
// on from those pages to this one.
const superseded = (ctx, copy, attempt) =>
  copy.ours.has(attempt) || Boolean(inherited.get(ctx)?.has(attempt));
// Whether a copy goes over the generation the server holds: the one it replaces, its
// own, or one it supersedes.
const replaces = (ctx, copy, attempt) =>
  attempt === copy.stored ||
  attempt === copy.record.attempt ||
  superseded(ctx, copy, attempt);
export const tellDraft = (ctx, value, payload = undefined) =>
  document.dispatchEvent(
    new CustomEvent(DRAFT_NEWS, { detail: { ctx, value, payload } }),
  );
const rawDraftRecord = (ctx) => draftCache.get(ctx)?.record ?? null;
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
const projectDraftRecord = (ctx, record) =>
  queueMicrotask(() => {
    const current = draftCache.get(ctx)?.record ?? null;
    if (!sameDraftRecord(current, record)) return;
    const active = current && !current.settled;
    tellDraft(ctx, active ? current.text : null, active ? current.payload : undefined);
  });

// The server's record as this document keeps it, less the version it carries apart.
const recordOf = (record) => {
  if (record === null) return null;
  const { version: _, ...rest } = record;
  return rest;
};
// Two copies of a draft's words as one: the longer, where one holds the other once
// both are trimmed, else the server's, a blank line, then this document's.
const bothWords = (theirs = "", mine = "") =>
  theirs.trim().includes(mine.trim())
    ? theirs
    : mine.trim().includes(theirs.trim())
      ? mine
      : `${theirs}\n\n${mine}`;
// Take the server's generation of a draft: a record, or none where the reading holds
// none, as it holds none of a generation sent or put away. Words this document holds
// that the store never took may still be wanted, unless this document is sending them,
// which the log may already hold. So where the server's words don't already hold
// them, the draft becomes both (`bothWords`), with this document's payload if it has
// one, else the server's: a new generation written over the server's, which every tab
// then hears, shown here with the caret at its end. Words alone decide whether to
// write one. A payload such as the selection composer's, which records when it was
// last touched, differs between tabs whatever they hold, so letting it decide would
// have two tabs write over each other without end.
function adopt(ctx, record, store, version) {
  const copy = draftCache.get(ctx);
  const mine =
    copy &&
    !(copy.durable && copy.store === store) &&
    !copy.record.settled &&
    sentAttempts.get(ctx) !== copy.record.attempt
      ? copy.record
      : null;
  if (copy && mine && record && !record.settled) {
    const text = bothWords(record.text, mine.text);
    const held = bothWords(record.held, mine.held);
    if (text !== record.text || held !== (record.held ?? "")) {
      draftCache.set(ctx, { ...copy, stored: record.attempt, store, version });
      saveDraft(ctx, text, mine.payload ?? record.payload, held || null);
      projectDraftRecord(ctx, rawDraftRecord(ctx));
      if (writingPlace?.context === ctx)
        keepWritingPlace({ ...writingPlace, selection: atEnd(ctx) });
      return;
    }
  }
  const shown = copy?.record ?? null;
  const next =
    record ??
    (shown && !shown.settled ? { attempt: shown.attempt, settled: true } : shown);
  if (next === null) return;
  moving.delete(ctx);
  draftCache.set(ctx, {
    record: next,
    stored: next.settled ? null : next.attempt,
    store,
    version,
    durable: true,
    ours: new Set(),
  });
  if (!sameDraftRecord(shown, next)) projectDraftRecord(ctx, next);
}

// The store this document last heard and its version then, from a reading or from a
// write that was the only change since one. A document served without its drafts has
// heard none until its first look.
let heard = { store: null, version: 0 };
let reading = null;
// Take a reading of the server's drafts. A draft this document heard of from the same
// store at the reading's version or later keeps what it has, as the reading may have
// been taken before a write this document's answer already told it of. A draft whose
// words still wait to reach the server keeps them over the generation they replace,
// none, or one they supersede (`superseded`), and anything else, which another tab or
// device wrote later, takes them in (`adopt`).
//
// A copy heard from another store, as a reload's from before a new leaf.page release
// started a store of its own, has a version that orders nothing here. Its words, or
// its settlement, go into this store where it holds nothing for their draft or a
// generation they replace (`replaces`), whether the earlier store held them or not.
// Any other generation it holds takes in those words, which this store never took,
// and stands over the settlement.
function hearReading({ store, version, drafts }) {
  if (store !== heard.store || version > heard.version) heard = { store, version };
  for (const ctx of new Set([...draftCache.keys(), ...Object.keys(drafts)])) {
    const incoming = drafts[ctx] ?? null;
    const copy = draftCache.get(ctx);
    if (copy && copy.store !== store) {
      if (incoming && !replaces(ctx, copy, incoming.attempt))
        adopt(ctx, recordOf(incoming), store, incoming.version);
      else
        draftCache.set(ctx, {
          ...copy,
          stored: incoming?.attempt ?? null,
          store,
          version: incoming?.version ?? version,
          durable: incoming
            ? sameDraftRecord(recordOf(incoming), copy.record)
            : Boolean(copy.record.settled),
        });
      continue;
    }
    if (copy && (incoming ? incoming.version <= copy.version : version < copy.version))
      continue;
    if (copy && !copy.durable) {
      if (incoming === null || incoming.attempt === copy.stored) continue;
      if (superseded(ctx, copy, incoming.attempt)) {
        draftCache.set(ctx, { ...copy, stored: incoming.attempt });
        continue;
      }
    }
    adopt(ctx, recordOf(incoming), store, incoming?.version ?? version);
  }
  takeHeldWords();
  writeWaiting();
}
// What a look at the server heard of the drafts: their store and its version, which
// moves with every write. Another store, or a later version of this one, is read
// again, though a store at version 0 holds no drafts to read. A look that reaches the
// server also sends on the words waiting for it.
export function hearDrafts({ store, version }) {
  writeWaiting();
  if (reading || (store === heard.store && version <= heard.version)) return;
  if (version === 0) return hearReading({ store, version, drafts: {} });
  reading = fetch(pageUrl("api/drafts"), { headers: layerHeaders() })
    .then(async (response) => {
      if (!admitResponse(response))
        throw new Error("drafts belong to another delivery");
      if (!response.ok) throw new Error(`drafts returned HTTP ${response.status}`);
      hearReading(await response.json());
    })
    .catch(() => {})
    .finally(() => (reading = null));
}

// The writes of each draft go to the server one at a time: words typed while one is
// out wait behind it, the latest in place of any that waited before them, so a
// keystroke costs this document a map write and the server a request for each answer
// it gives. An exported page has no server, so its drafts last as long as its tab.
const writing = new Map();
/** @param expect the generations the write may replace, null for none */
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
  return await response.json();
}
function writeDraft(ctx) {
  const copy = draftCache.get(ctx);
  if (!copy || copy.durable || writing.has(ctx) || offlineInteractive) return;
  const sent = copy.record;
  writing.set(ctx, sent);
  draftCache.set(ctx, { ...copy, ours: new Set([...copy.ours, sent.attempt]) });
  void postDraft(ctx, [copy.stored], sent).then(
    (answer) => {
      writing.delete(ctx);
      heardWrite(ctx, sent, answer);
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
// arrival would then go over an older generation than the resend's and lose to it. It
// can also be served them before a write this page then heard the server take, since
// the reload asks for its document before this page goes away. So the page also
// leaves in the tab, for each draft, the generations its writes that may still land
// carry or name (`inherited` included), and its copy of the draft, taken or still
// waiting (`WAITING_DRAFTS`), and its reload starts from them (`takeWaitingDrafts`).
// The reload shows the newest words at once, a served generation older than the copy
// gives way to it by version, a store that replaced the copy's takes its words
// (`hearReading`), and the words it has yet to send go over any of those writes,
// whichever lands and when (`superseded`), so the words typed after the reload stand. A generation this document is sending leaves its
// generations but not its copy, since only the server's answer says whether the log
// took those words.
//
// Words or a drawing no write is carrying (`holdsWork`), as after one failed while the
// server was out of reach, or on an exported page, which has no server, go with the
// document. So leaving asks first, through the browser's own prompt, and the user says
// whether they still want them (SOUL.md, "Leaf drops words the user typed only when it
// knows they no longer want them"). Keeping them in the browser past the tab instead
// would need the store to know every write it ever took, or a late replay brings back
// words sent, cancelled or written over elsewhere. Work a write is carrying needs no
// prompt, since the resend above takes it on. A reload the user asks for asks too,
// though its tab keeps the work for it, since the prompt can't tell a reload from a
// close. The prompt a reload Leaf asks for raises asks nothing (transport/layer-client.js,
// `takeLeafUnload`): it is no close, and after a server restarted under another Leaf,
// which refuses this document's writes, every word typed since would otherwise put the
// prompt in front of a reload the user never asked for.
addEventListener("beforeunload", (event) => {
  if (takeLeafUnload()) return;
  const stranded = [...draftCache].some(
    ([ctx, { durable }]) =>
      !durable && !writing.has(ctx) && holdsWork(activeDraftRecord(ctx)),
  );
  if (stranded) event.preventDefault();
});
const WAITING_DRAFTS = "lf-drafts-waiting";
addEventListener("pagehide", () => {
  if (offlineInteractive) return;
  const waiting = [];
  for (const ctx of new Set([...draftCache.keys(), ...inherited.keys()])) {
    const copy = draftCache.get(ctx);
    const earlier = [...(inherited.get(ctx) ?? [])];
    if (!copy) {
      if (earlier.length) waiting.push([ctx, { attempts: earlier, copy: null }]);
      continue;
    }
    const { record, stored, store, version, durable } = copy;
    const left =
      sentAttempts.get(ctx) === record.attempt
        ? null
        : { record, stored, store, version, durable };
    if (durable) {
      waiting.push([ctx, { attempts: earlier, copy: left }]);
      continue;
    }
    draftCache.set(ctx, { ...copy, ours: new Set([...copy.ours, record.attempt]) });
    const unanswered = [...copy.ours, ...earlier];
    void postDraft(ctx, [stored, ...unanswered], record, true).catch(() => {});
    waiting.push([
      ctx,
      {
        attempts: [...unanswered, record.attempt, ...(stored ? [stored] : [])],
        copy: left,
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
  const reloaded = performance.getEntriesByType("navigation")[0]?.type === "reload";
  if (!left || !reloaded) return;
  try {
    for (const [ctx, { attempts, copy }] of JSON.parse(left)) {
      inherited.set(ctx, new Set(attempts));
      if (copy) draftCache.set(ctx, { ...copy, ours: new Set() });
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
// another tab or device wrote there meanwhile take them in (`adopt`), and the
// generation holding both carries them; where those words already hold them, the move
// ends and they stay where they were too.
const moving = new Map();
// The server's answer to a write: the draft as it now holds it. A generation this
// document's words go over (`replaces`) leaves them standing; any other is another
// tab's or device's, which takes in the words this document has yet to send
// (`adopt`).
function heardWrite(ctx, sent, { written, store, version, record }) {
  if (written && !inherited.get(ctx)?.has(sent.attempt)) inherited.delete(ctx);
  const copy = draftCache.get(ctx);
  // A reading of this store taken since may already have said more than this answer
  // does; a copy heard from another store orders nothing against it.
  if (!copy || (copy.store === store && copy.version > version)) return;
  const held = recordOf(record);
  const own = written || Boolean(held && replaces(ctx, copy, held.attempt));
  const move = moving.get(ctx);
  if (move && written && move.carrying.has(sent)) {
    moving.delete(ctx);
    const settled = settleDraft(move.from, move.attempt);
    if (settled) projectDraftRecord(move.from, settled);
  }
  if (!own) {
    adopt(ctx, held, store, record?.version ?? version);
    return;
  }
  // A write that was the only change since the reading this document took leaves it
  // holding the next one, which a look need not read again.
  if (written && store === heard.store && version === heard.version + 1)
    heard = { store, version };
  // Words the log already took, whose write reached the server after their event, are
  // settled there (`drafts.py`, `sent`), and here too unless typed over since.
  const spoken = written && !held && !sent.settled && copy.record === sent;
  draftCache.set(ctx, {
    ...copy,
    record: spoken ? { attempt: sent.attempt, settled: true } : copy.record,
    stored: held && !held.settled ? held.attempt : null,
    store,
    version: copy.store === store ? Math.max(copy.version, version) : version,
    durable: copy.durable || (written && copy.record === sent),
    ours: new Set(),
  });
  if (spoken) projectDraftRecord(ctx, rawDraftRecord(ctx));
}

// A message draft is kept under what it is written about, and it stays there until it
// is sent or put away. The contexts below, named only here, say which subject each
// draft is about. Threads lists the drafts under Drafts (`draftsReading`;
// panel/floating-panel.js, `draftsListing`), and a press on a row or Resume writing brings the
// user back to one (`createWritingResume`). Opening another box opens that box's own
// draft and moves no words into it. Rejected: an explicit Comment on
// another target, or `c` into a thread, moving the unsent words there. Words move only
// when their box is gone, into the page's draft (`moveToPage`).
// - `page`: the page's own comment, the floating panel's field (`PAGE_DRAFT`);
// - `comment`: a comment on a passage or element, under its anchor's key
//   (`composerCtx`), its record holding the anchor (`ComposerDraft`);
// - `reply`: a thread's reply box, under the thread's key (`threadKey`, a first
//   message's attempt until the log names the thread);
// - `rewrite`: a rewrite of a message, under that message's id (thread/message-edit.js).
// Any other draft, such as a widget's edit, is a value rather than a message.
const PREFIX = {
  comment: "composer:",
  reply: "reply:",
  rewrite: "rewrite:",
};
export const commentContext = (key) => PREFIX.comment + key;
export const replyContext = (key) => PREFIX.reply + key;
export const rewriteContext = (id) => PREFIX.rewrite + id;

// A passage comment's draft, as the selection composer (annotations/composing/selection.js)
// keeps it. `composerCtx` is the key the draft is kept under, which
// `createSelectionComposer` explains, and `composerPayload` is the record kept beside the
// words, touched now. DRAFT_FORMAT identifies the record's complete current shape, which
// Threads' Drafts also reads for what a passage's draft is about.
export const composerCtx = (anchor) => commentContext(anchorKey(anchor));
export const composerPayload = (fields) => ({
  format: DRAFT_FORMAT,
  ...fields,
  touched: Date.now(),
});
export function isComposerDraft(payload) {
  return payload != null && "format" in payload && payload.format === DRAFT_FORMAT;
}
// The draft a comment the log holds on a passage was written in, as the composer keeps
// it, which taking the comment back puts its words back in (records/undo.js).
export const commentDraft = (comment) => ({
  ctx: composerCtx(comment.anchor),
  payload: composerPayload({
    anchor: comment.anchor,
    revision: comment.revision ?? null,
    suggest: Boolean(comment.suggestion),
    about: comment.about ?? null,
    drawing: comment.drawing ?? null,
  }),
});

// Which message draft `ctx` is, with the key or id it is under; null for any other.
function draftSubject(ctx) {
  if (ctx === PAGE_DRAFT) return { part: "page", name: null };
  for (const [part, prefix] of Object.entries(PREFIX))
    if (ctx.startsWith(prefix)) return { part, name: ctx.slice(prefix.length) };
  return null;
}
// The drafts a thread holds: its reply box and a rewrite of one of its messages.
export function threadDraft(ctx) {
  const subject = draftSubject(ctx);
  return subject?.part === "reply" || subject?.part === "rewrite"
    ? { part: subject.part, name: subject.name }
    : null;
}
const isReply = (ctx) => threadDraft(ctx)?.part === "reply";
// What a box that stops showing the user's words says, once: that they are kept, with
// Resume writing, the press that brings them back, at the panel field's end, where the
// user looks for a moment's next press and its key (transport/notifications.js, `press`). A
// refusal's error offers the same press (`keepRefusedWords`).
export function noticeDraftKept() {
  notice("Draft kept", { press: writingPlace && RESUME_WRITING });
}
const RESUME_WRITING = {
  action: "resume-writing",
  command: "writing.resume",
  stands: () => writingPlace !== null,
};

// A generation this document has sent and not heard back on. Its words are shown
// wherever the gesture drew them, so the box they were written in reads empty, while
// the record itself stands, unsettled, until the log accepts it. The two are different
// facts: what a box shows is about this document, and settlement is a claim over every
// tab. That is what lets a second tab still show and send the same generation, and what
// brings the words back here on a refusal with nothing to restore them from.
const sentAttempts = new ListingMap(); // ctx -> attempt

const unsettledDraftRecord = (ctx) => {
  const record = rawDraftRecord(ctx);
  return record && !record.settled ? record : null;
};
const activeDraftRecord = (ctx) => {
  const record = unsettledDraftRecord(ctx);
  return sentAttempts.get(ctx) === record?.attempt ? null : record;
};
// Sending hides a generation's words while its result stands on screen, but does
// not end its editor's lifetime: refusal still owes those words that same editor.
export const draftHasContent = (ctx) => Boolean(unsettledDraftRecord(ctx)?.text);
const keepDraft = (ctx, record) => {
  const copy = draftCache.get(ctx);
  const move = moving.get(ctx);
  if (move && copy && move.carrying.has(copy.record)) move.carrying.add(record);
  draftCache.set(ctx, {
    record,
    stored: copy?.stored ?? null,
    store: copy?.store ?? heard.store,
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
const settleDraft = (ctx, attempt) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled || current.attempt !== attempt) return null;
  const record = { attempt, settled: true };
  keepDraft(ctx, record);
  return record;
};
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
const carriedHeld = (ctx) => {
  const previous = rawDraftRecord(ctx);
  return previous && !previous.settled && sentAttempts.get(ctx) !== previous.attempt
    ? previous.held
    : undefined;
};
// Set the held reply on the draft's current generation without minting another: the
// refused attempt stays the one a resend re-evaluates.
const holdReply = (ctx, held) => {
  const current = activeDraftRecord(ctx);
  if (!current) return false;
  const { held: _, ...rest } = current;
  keepDraft(ctx, held ? { ...rest, held } : rest);
  return true;
};
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

// Who keeps the words a box's Discard or Escape throws away: the page's undo (records/undo.js,
// `keepDiscard`), set as the application mounts.
let keepDiscarded = null;
export const keepDiscardsWith = (keep) => {
  keepDiscarded = keep;
};
// Throw away the words `ctx`'s draft holds, as an editor's Discard and Escape do,
// with the box they stand in (`at`) while it still stands, which says what they were
// an edit of. A draft holding no words leaves nothing to take back. The editor calls it
// only where its words differ from what its subject already says.
export function discardDraft(ctx) {
  const record = activeDraftRecord(ctx);
  clearDraft(ctx);
  if (!record?.text) return;
  const editor = [...draftEditors].find((view) => view.ctx === ctx);
  const at = (editor && editorInput(editor)) ?? null;
  keepDiscarded?.({ ctx, text: record.text, payload: record.payload, at });
}
export const loadDraft = (ctx) => activeDraftRecord(ctx);
export const draftContexts = () => [...draftCache.keys()];

// ---------- the drafts list ----------
// Every message draft holding words or a drawing, as this document shows it, in no
// order: a generation it is sending stands on screen as the message, not as a draft.
// The page's own draft isn't listed: the floating panel's field shows it and no view of
// drafts does, so listing it would repaint every view of drafts as the field's words
// start and end. It is the one list every view of drafts reads: Threads' Drafts band and the
// leaf's dot (panel/floating-panel.js), and each draft's margin entry. It publishes when
// a draft starts or stops holding something or what it is about changes, so a
// keystroke in a draft already listed costs one comparison and repaints nothing; a
// view reads the draft's words where it draws them (`loadDraft`).
const listing = new Map();
const listed = signal(Object.freeze([]));
export const draftsReading = () => listed.value;
// What a listing shows of a draft's payload: where it is, whether it suggests, what it
// is about and its drawing. Another tab's write arrives as new objects alike in content.
const LISTED = ["anchor", "suggest", "about", "drawing"];
const field = (payload, key) => payload?.[key];
// Whether a draft holds the user's work: words, or a comment's drawing, which a
// selection composer can hold with no words. Leaving asks over it and the drafts list
// shows it. Words given back test more widely (`giveBackWords`).
const holdsWork = (record) =>
  Boolean(record?.text.trim() || field(record?.payload, "drawing"));
const listsAlike = (was, now) =>
  LISTED.every((key) => {
    const [a, b] = [field(was, key), field(now, key)];
    return a === b || JSON.stringify(a) === JSON.stringify(b);
  });
function listDraft(ctx) {
  const subject = draftSubject(ctx);
  if (!subject || subject.part === "page") return;
  const record = activeDraftRecord(ctx);
  const holds = holdsWork(record);
  const was = listing.get(ctx);
  if (!holds && !was) return;
  if (holds && was && listsAlike(was.payload, record?.payload)) return;
  if (holds) listing.set(ctx, { ...subject, context: ctx, payload: record?.payload });
  else listing.delete(ctx);
  listed.value = Object.freeze([...listing.values()]);
}
// Where on the page a listed draft is about, as an anchor: a comment's. A reply or
// rewrite has none of its own; it stands where its thread does.
export const draftAnchor = (draft) => {
  if (draft.part !== "comment") return null;
  const anchor = field(draft.payload, "anchor");
  return anchor ?? null;
};
// What Send makes of a listed draft, the word every view of it ends on.
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
const standGesture = (ctx, current) => {
  sentAttempts.set(ctx, current.attempt);
  tellDraft(ctx, null);
  return (sent) => {
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
//
// A refusal gives back what the send took (browser/AGENTS.md, "A refused or undone
// gesture gives back what it took"): the words to their draft (`standGesture`), and,
// while the user has done nothing since Send, the user to the box they come back in:
// `back`, the caller's way into that box, which says itself where a box no longer
// stands for those words. Only whether they have acted since counts, not where focus
// stands, since withdrawing the thread the send landed them on hands their focus on.
// After a later key or press the words wait for Resume writing.
export function sendMessage(ctx, owns, send, back) {
  const current = claimDraft(ctx, owns);
  if (!current) return null;
  const untouched = retainUserIntent({ source: document.documentElement });
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
    if (!sent) untouched.handoff(back);
  });
  return { attempt: current.attempt, id: `${PENDING}${current.attempt}` };
}

// The draft each first message still in flight was sent from, by its attempt. The
// draft, not the attempt, is what lasts: a refusal keeps the attempt only until the
// user edits the words, and the thread comes back under whichever one is sent.
const openedFrom = new Map();

// Existing draft subscriptions own current editor identity and lifetime. The store
// supplies active words and an optional submission payload, or null and no payload
// for settlement. Editor membership is mechanical: connected root editors recover
// by context, and retained reply mirrors land through their current thread owner.
// Unsubscribing retires that membership alongside the listener. A subscription also
// says whether its box takes words now (`closed`) and which box its words are written
// in (`box`), which a wired box's wiring answers (`mirrorDraft`), so Resume writing and
// history ask the editor they reach.
//
// It does not run on subscribe, which is where this parts company with controller state. The
// draft a box opens with and the news that another tab changed one are different facts,
// and the boxes answer them differently: a draft editor opens on recovery at load and
// stays shut for a keystroke made elsewhere, because news arriving has no gesture behind
// it and so may move nothing.
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
const writingRoutes = new Map();
const writingRoute = (ctx) =>
  [...writingRoutes].find(([prefix]) => ctx.startsWith(prefix))?.[1];
const editorInput = (editor) =>
  typeof editor.input === "function" ? editor.input() : editor.input;
const storeWritingPlace = () =>
  writingStore.set(
    WRITING_PLACE,
    writingPlace && JSON.stringify({ ...writingPlace, earlier: earlierPlaces }),
  );
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
const atEnd = (ctx) => {
  const end = (activeDraftRecord(ctx)?.text ?? "").length;
  return [end, end];
};
// Words an undo took back from the log, given back to the draft they were written in
// (records/undo.js, `withdraw`), so taking a message back puts it to draft rather than
// discarding it. They come first, then the words of the box `under` them, the reply box
// of a thread that went with them, then any words the draft holds now, which the user
// wrote after them. A draft holding something of its own keeps its own `payload`, such
// as the passage and mode of a comment begun since, taking only a drawing it lacks; one
// holding nothing takes the words'. A new generation, so the log's record of the send
// settles nothing here (`drafts.py`). They are the user's newest unsent words, so
// Resume writing goes to their end, wherever the box stands.
export function giveBackWords(ctx, text, payload, under = null) {
  const current = activeDraftRecord(ctx);
  // Any text counts here, whitespace included, so a box the user has begun keeps
  // what they typed and its own payload, such as the passage of a comment begun since.
  const own =
    current && (current.text || field(current.payload, "drawing")) ? current : null;
  const reply = under === null ? null : activeDraftRecord(under);
  const drawing = field(payload, "drawing");
  // Giving back nothing, as a reaction with no reply begun under it does, leaves the
  // draft and Resume writing as they stand.
  if (!text && !reply?.text && !drawing) return;
  const words = [text, reply?.text, own?.text].filter(Boolean).join("\n\n");
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
// The box on screen that shows `ctx`'s words, or null where none does.
const shownIn = (ctx) =>
  [...draftEditors]
    .filter((view) => view.ctx === ctx)
    .map((view) => editorInput(view))
    .find((input) => input?.isConnected && input.checkVisibility()) ?? null;
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
// says they are kept (host/delivery.js). The error is about the box on screen the sending
// gesture's words came back to, where there is one (`field`); otherwise it is about no
// box and offers Resume writing as its press (`press`), since a box's cover draws no
// press (transport/errors.js).
//
// Resume writing comes back to words a refusal handed back at their end (`atEnd`), as a
// press on the error over them does (annotations/composing/input.js), so Enter sends them.
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
  const hidden = returned.filter((ctx) => !shownIn(ctx));
  // Words back where Resume writing already goes are resumed at their end too, not at
  // the start of the box the send emptied.
  const resumes = returned.find((ctx) => ctx === writingPlace?.context);
  if (resumes !== undefined && writingPlace)
    keepWritingPlace({ ...writingPlace, selection: atEnd(resumes) });
  // The gesture delivery was sending comes first, so it is the place Resume writing
  // reaches first, and the others stand behind it.
  for (const ctx of hidden.toReversed())
    if (writingPlace?.context !== ctx)
      keepWritingPlace({ context: ctx, selection: atEnd(ctx), generation: randomId() });
  const sentences = [
    hidden.length && "Draft kept",
    held && "Reply kept — it comes back once its comment is saved",
  ].filter(Boolean);
  const field = returned.map(shownIn).find(Boolean) ?? null;
  return {
    said: sentences.length ? sentences.join(". ") : null,
    field,
    press: hidden.length && writingPlace && !field ? RESUME_WRITING : null,
  };
}
const writingEditor = () =>
  [...draftEditors].find((editor) => editorInput(editor) === focused());
const keepWritingCaret = () => {
  const editor = writingEditor();
  if (editor && editor.ctx === writingPlace?.context)
    keepWritingPlace({ ...writingPlace, selection: readCaret(editorInput(editor)) });
};
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
// In capture, since a key typed in the editor stops at it (base/field-keys.js).
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

export function registerWritingDestination(prefix, reveal) {
  // Availability can include an empty current editor. hasContent tells fallback
  // selection whether its owner holds work beyond the shared draft's words.
  writingRoutes.set(prefix, reveal);
  return () => writingRoutes.delete(prefix);
}

// Whether the user stands on the box `ctx` is written in, as the thread walk leaves them
// (`showDraft`), rather than in its editor: only a draft whose owner declares a writing
// route has such a box (`frame`). The walk puts the box away once it has taken the
// user on to another stop (`closeDraft`), keeping its words, as `c` into a thread does.
export function standsOnDraft(ctx) {
  const frame = writingRoute(ctx)?.(ctx)?.frame?.();
  return Boolean(frame) && focused() === frame;
}
export const closeDraft = (ctx) => writingRoute(ctx)?.(ctx)?.close?.();

// Words nothing on the active document holds a box for, as when a version removes the
// content an edit was for, join the page's own draft after the words it already holds,
// and Resume writing moves with them (`transferDraft`): one copy, sent or put away like
// any page comment. Whatever took the box away, the words now stand where a comment
// about no particular place is written.
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
// words' end, or on a control inside its box the route names (`control`), as history
// returns the user to one (`draftFocus`). Opening a draft is no content edit, so it
// leaves the writing place where it was. Each travels to the draft, a Back step, except where the caller opens it
// where the user stands (`travel: false`), as a press on its passage's margin marker
// does (thread/destination.js).
export function createWritingResume({
  revealInThread,
  arriveEditor,
  holdsThreadDraft,
}) {
  const holdsBox = (ctx) =>
    threadDraft(ctx)
      ? holdsThreadDraft(ctx)
      : Boolean(writingRoute(ctx)) ||
        [...draftEditors].some((view) => view.ctx === ctx);
  const resume = () => (writingPlace ? resumeAt(writingPlace) : Promise.resolve());
  // A route that names the caret, as a return to an entry the user left writing does
  // (history.js), puts it there rather than where the words were last written.
  const resumeDraft = (ctx, route = {}) => {
    const place = [writingPlace, ...earlierPlaces].find(
      (place) => place?.context === ctx,
    ) ?? { context: ctx, selection: atEnd(ctx), generation: randomId() };
    return resumeAt(route.caret ? { ...place, selection: route.caret } : place, route);
  };
  const resumeAt = async (place, route = {}) => {
    // A route a restoration starts runs under its intent (history.js).
    const intent = route.intent ?? retainUserIntent();
    let input;
    // A thread view holds its own drafts, which the thread's destination reveals.
    if (threadDraft(place.context))
      input = await revealInThread(place.context, intent, route);
    else {
      const resolve = () => {
        const route = writingRoute(place.context);
        const editor = [...draftEditors].find(
          (view) => view.ctx === place.context && view.resume,
        );
        return route ? route(place.context) : editor?.resume?.();
      };
      input = await arriveEditor(resolve, {
        intent,
        caret: place.selection,
        travel: route.travel ?? true,
      });
    }
    if (input === undefined || !intent()) return;
    const editor = [...draftEditors].find(
      (view) => view.ctx === place.context && editorInput(view) === input,
    );
    const field = editor && editorInput(editor);
    // Whether the box takes words now, as its subscription says (`closed`), not its
    // painted `readOnly`, which still reads shut until the next paint after the same
    // task ends a stance, as `g i` ends Go-to's.
    if (
      field?.isConnected &&
      field.checkVisibility() &&
      !editor?.closed() &&
      !("disabled" in field && field.disabled)
    ) {
      const box = route.control ? (editor?.box() ?? null) : null;
      const within = box && route.control ? namedIn(box, route.control) : null;
      // Coming back to the words is the user dealing with any error over them, as a
      // press on it is (transport/errors.js, `passErrorsAt`).
      intent.handoff(() => {
        passErrorsAt(field);
        if (within && within !== box) focusDestination(within, "return");
        else focusDestination(field, "move", { caret: place.selection });
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
  // The thread walk's way onto a draft it names by context (panel/navigation.js): the draft's
  // box opens on its own record, as Resume writing opens it, and the user stands on the
  // box rather than in it (`standsOnDraft`), so a walk key goes on walking and `c` puts
  // the caret in the words. It answers whether the user arrived. Opening a draft is no
  // content edit, so it leaves the writing place where it was. Back to such a stop opens
  // the box where the user stands (`travel: false`, history.js).
  const showDraft = async (ctx, { travel = true, intent: asked } = {}) => {
    const route = writingRoute(ctx);
    if (!route) return false;
    const intent = asked ?? retainUserIntent();
    const frame = await arriveEditor(() => route(ctx), {
      intent,
      caret: null,
      onFrame: true,
      travel,
    });
    return Boolean(frame) && intent();
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
    showDraft,
  };
}

// A subscription owns its editor's context and lifetime. A context's root editor is
// the box it is written in directly, which takes the caret back after a revision.
// Replies explicitly declare mirrors and land through their thread owner.
// A revision carries mechanical editing, never another copy of the draft's words.
export function captureDraftEditing(at = focused()) {
  for (const editor of draftEditors) {
    const input = editorInput(editor);
    if (!input || input !== at) continue;
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

// The draft focus is on, as history keeps it for an entry the user left writing
// (history.js): its context, and the caret where focus is in its editor, or `box` where
// the user stands on the box it is written in, as a walk leaves them
// (`standsOnDraft`), or on a control inside it, as a drawing's Undo, which `control`
// names within the box (carry.js, `nameIn`). A reply's mirror is its thread's, which
// history names by the thread. The words stay in the drafts store, which brings them
// back with the box.
export function draftFocus(at = focused()) {
  const editing = captureDraftEditing(at);
  if (editing && !editing.mirrored)
    return {
      draft: editing.context,
      ...(editing.selection && { caret: editing.selection }),
    };
  if (!at) return null;
  for (const view of draftEditors) {
    if (view.mirrored) continue;
    const box = view.box();
    if (!box || !renderedUnder(at, box)) continue;
    const frame = writingRoute(view.ctx)?.(view.ctx)?.frame?.();
    return {
      draft: view.ctx,
      box: true,
      ...(at !== frame && { control: nameIn(box, at) }),
    };
  }
  return null;
}

export const draftEditingStands = (editing) =>
  editing !== null && activeDraftRecord(editing.context)?.attempt === editing.attempt;

// The root editor a revision hands the caret back to, shown first through its owner's
// Resume writing route when a disclosure holds it shut; `handoff` gates that showing on
// the user's intent. A root off the page counts when its owner's route places it there,
// as the page comment card places its box at its first open, and so does one whose
// owner has no box until that route builds it, as a closed document edit has none.
export function draftEditingDestination(editing, handoff) {
  const shown = (view) =>
    Boolean(editorInput(view)?.checkVisibility({ visibilityProperty: true }));
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

export function watchDraft(
  ctx,
  callback,
  {
    input = null,
    mirrored = false,
    resume = null,
    closed = () => false,
    box = () => null,
  } = {},
) {
  const editor = input && { ctx, input, mirrored, resume, closed, box };
  if (editor) draftEditors.add(editor);
  const update = (ev) =>
    ev.detail.ctx === ctx && callback(ev.detail.value, ev.detail.payload);
  document.addEventListener(DRAFT_NEWS, update);
  return () => {
    document.removeEventListener(DRAFT_NEWS, update);
    if (editor) draftEditors.delete(editor);
  };
}
// A package's draft: the functions above bound to one context, which the package API
// exports in their place (widget-api.js). Its types offer none of what only Leaf's own
// boxes pass: a reply the draft holds (`held`), and a mirror's options.
export const draft = (ctx) => ({
  read: () => loadDraft(ctx),
  save: (text, payload) => saveDraft(ctx, text, payload),
  clear: () => clearDraft(ctx),
  discard: () => discardDraft(ctx),
  watch: (callback, options) => watchDraft(ctx, callback, options),
  send: (owns, deliver) => sendDraft(ctx, owns, deliver),
});
// News of every draft whose context starts with `prefix`, for a reader of a whole kind
// of draft rather than one box's.
export function watchDrafts(prefix, callback) {
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
    {
      input: ta,
      mirrored,
      resume,
      closed: sync.closed,
      box: () => sync.composition().frame,
    },
  );
  return off;
}
// Reply drafts are never pruned. A thread resolving is not a discard, so another
// tab's Resolve, or this tab accepting a suggestion whose action `resolves`,
// sweeps no unsent reply out of storage, which would lose words where the
// norm is that Cancel is the only discard. A thread a retraction reopens finds
// the draft where it was left.

// Words the user typed through a reload Leaf asked for, which the early key hold
// keeps for their box (bootstrap.js, `typeBack`), each batch with the context of the
// draft they were typed for. They go into that draft, among its words
// and before any pictures it holds (media.js, `readAttachedMedia`): at the caret the
// reload's record of the box being written holds (`captureDraftEditing`), while the
// draft is still the generation that record was read at (`draftEditingStands`), and
// after its words otherwise. That record moves with them, so a reload that still puts
// the user back in the box puts the caret after them (features/version.js,
// `restoreEditingContinuity`). The words leave the panel's field, where the keys stood,
// as the hand-back ends; where they aren't then on screen in their box (`shownIn`),
// the panel says the draft is kept, with Resume writing, which goes to their end, as
// it does for words from a document that doesn't put the user back here. A document
// served without the drafts takes them once its first reading has told it what the
// draft holds (`hearReading`).
const HELD_WORDS = "lf-held-words";
function takeHeldWords(event) {
  const ended = event instanceof CustomEvent ? event.detail : null;
  if (typeof ended === "string" && !shownIn(ended)) noticeDraftKept();
  if (heard.store === null && !offlineInteractive) return;
  const left = tabStore.get(HELD_WORDS);
  if (!left) return;
  tabStore.set(HELD_WORDS, null);
  let kept;
  try {
    kept = JSON.parse(left);
  } catch {
    return;
  }
  const handed = window.lfStorage.handoff?.draftEditing;
  for (const { context, words: typed } of kept) {
    const box = handed?.context === context ? handed : null;
    const current = activeDraftRecord(context);
    const { text, paths } = readAttachedMedia(current?.text ?? "");
    const [start, end] =
      box && draftEditingStands(box) && box.selection
        ? box.selection
        : [text.length, text.length];
    const words = text.slice(0, start) + typed + text.slice(end);
    const value = writeAttachedMedia(words, paths);
    saveDraft(context, value, current?.payload);
    tellDraft(context, value, current?.payload);
    const selection = [start + typed.length, start + typed.length];
    keepWritingPlace({ context, selection, generation: randomId() });
    if (box)
      Object.assign(box, {
        words,
        selection,
        attempt: activeDraftRecord(context)?.attempt,
      });
  }
  if (!window.lfStorage.placesUser()) noticeDraftKept();
}

// The drafts start from the copies the page this tab reloaded left waiting
// (`takeWaitingDrafts`), then those the document was served with (`lf-drafts`), heard
// as any reading is (`hearReading`), then the words the key hold let go
// (`takeHeldWords`); every later change reaches the list through the maps. A document
// served without them, as a release's or an export's, hears them at its first look, or
// has none.
takeWaitingDrafts();
const served = document.getElementById("lf-drafts")?.textContent;
if (served) hearReading(JSON.parse(served));
takeHeldWords();
document.addEventListener(HELD_WORDS, takeHeldWords);
