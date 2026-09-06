/* Durable, cross-tab drafts and their accepted-log reconciliation.

   Every unsent composition persists:

   - the general comment box, including an attached page drawing;
   - each thread reply;
   - the selection composer, including its anchor and mode;
   - a conversation's first message and replies;
   - an `lf-draft` edit.

   The store is `localStorage` scoped by page and draft context, because the text must
   survive reload, version navigation, server restart, and closing the tab where it was
   typed. `draftCache` keeps a readable local branch when storage writes fail. Storage
   failure may reduce cross-tab durability; it never disables the live Send or Save
   action.

   One context has one shared generation. `watchDraft` mirrors storage changes into
   every connected view. The DOM's listener cleanup is the index: a watcher stops when
   its box is disconnected, so panel reconciliation does not maintain a parallel map of
   live inputs.

   A draft generation stores `{text, attempt, base, payload?}` while active and
   `{attempt, base, settled: true}` after settlement. Its attempt is minted when an edit
   creates the generation, not on Send, and is reused by every tab that sends it.
   A refusal does not mint a new attempt. Pressing Send again re-evaluates the same
   attempt against current server state. A new edit, including replacing text with the
   same characters, creates a new attempt. A successful send settles only the exact
   active generation it sent. `sendDraft` refreshes the shared record and compares both
   untrimmed text and attempt immediately before POST; `settleDraft` repeats the
   generation check before writing the tombstone. Text typed while the request is in
   flight therefore survives its response.

   An active record and a settled tombstone are different records. An empty active
   `text` means the reader intentionally cleared the box. A tombstone means Send or
   Cancel settled that generation. The implementation never depends on `removeItem` to
   distinguish them, because deletion can fail independently and could otherwise
   resurrect old words.

   `base` records the durable shared generation a local edit descends from. A chain of
   nondurable local writes keeps that base. Storage news from the base cannot erase the
   branch; an unrelated later shared generation owns the context and retires it. Before
   writing a settlement, Send, Cancel, and log reconciliation refresh the shared
   generation so a stale tab cannot tombstone a newer edit.

   Settlement is generation-specific. `activeDraftRecord` filters tombstones and
   accepted attempts (`attemptAccepted`: an attempt already in `events` is settled
   whatever stale storage hands back). `sendDraft` snapshots the current record, checks
   ownership immediately before POST, and settles only that attempt. `mirrorDraft`
   updates visible text only when doing so will not erase a newer local generation.

   The selection composer keys drafts by anchor, not by one global composer slot. Its
   stored record carries the anchor, mode, and last-touch time; startup reopens the
   most recently touched draft. Different passages may therefore hold independent
   unfinished comments.

   An `lf-draft` editor is a live gesture. Its `renderState` returns `false` while the
   editor is open, so remote edits and refusal correction wait rather than overwriting
   the textarea. Closing the editor lets the authoritative projection apply in order.

   The comment over the store below says where it came from and why one record carries
   an edit's provenance. */

import { runtime } from "./context.js";
import { PAGE_SCOPE, draftStore } from "./storage.js";

// ---------- draft persistence ----------
// Text the user typed but hasn't sent must survive navigation, reload, version switches,
// server death — and the tab itself. That last one is where this store came from: each
// round's reply hands the URL over again and the user opens the page from the turn in
// front of them, so a page's tabs accumulate and the one holding a half-written sentence
// is as likely to be closed as any other. Tab-local storage carried a draft through
// everything but the one gesture nobody thinks of as destructive.
//
// So the store is the reader's, and one draft has one copy: every box showing it, in
// every tab, is a view of the store, and the store's own `storage` event carries a
// keystroke from the tab that made it to the rest (watchDraft). A copy per tab was the
// alternative and it fails in the direction that loses words — two tabs each holding a
// different half of one thought, and whichever is closed takes its half.
//
// The stored value is one record, not raw words plus lock markers:
// {text, attempt, base, payload?} while active and {attempt, base, settled:true}
// afterward. `payload` lets a draft whose submission depends on more than its visible
// words bind that exact submission state to the attempt; two tabs must not derive two
// action bodies from one shared generation. `base` is the shared attempt this edit
// descended from, or null when the store was absent. A new edit always mints a new
// attempt but a chain of failed local writes keeps the same base. That provenance is
// what lets the branch survive news settling its predecessor without letting it overwrite
// an unrelated generation another tab durably wrote later.
//
// A new attempt is minted even when its words equal an earlier message. The tombstone
// rather than key removal is
// what makes asymmetric removeItem behavior irrelevant, and the attempt is what lets the
// log recognize the same gesture after the tab holding the browser lock has died.
//
// Storage failures never break typing (`stored`). Every local save updates the document
// cache first and then tries the one record write, so a successful set followed by a
// failed get remains sendable, and a failed newer set cannot be erased by news settling
// the older shared attempt. The log still outranks both: an attempt already present in
// `events` is settled whatever stale active record storage hands back on reload.
const DRAFT = "lf-draft:";
const DRAFT_NEWS = "lf-drafts";
const draftCache = new Map(); // context -> {record, durable}
export const tellDraft = (ctx, value, payload = undefined) =>
  document.dispatchEvent(
    new CustomEvent(DRAFT_NEWS, { detail: { ctx, value, payload } }),
  );
const parseDraftRecord = (value) => {
  if (typeof value !== "string") return null;
  try {
    const record = JSON.parse(value);
    if (
      !record ||
      typeof record !== "object" ||
      typeof record.attempt !== "string" ||
      !(record.base === null || typeof record.base === "string") ||
      (record.settled === true
        ? Object.keys(record).some(
            (key) => !["attempt", "base", "settled"].includes(key),
          )
        : typeof record.text !== "string" ||
          (record.payload !== undefined &&
            (!record.payload ||
              typeof record.payload !== "object" ||
              Array.isArray(record.payload))) ||
          Object.keys(record).some(
            (key) => !["attempt", "text", "base", "payload"].includes(key),
          ))
    )
      return null;
    return record;
  } catch {
    return null;
  }
};
const attemptAccepted = (attempt) =>
  (runtime.browser?.receipts ?? []).some((event) => event.attempt === attempt);
const writeDraftRecord = (ctx, record) =>
  draftStore.set(DRAFT + ctx, JSON.stringify(record));
const rawDraftRecord = (ctx) => {
  if (draftCache.has(ctx)) return draftCache.get(ctx).record;
  const read = draftStore.read(DRAFT + ctx);
  const record = read.available ? parseDraftRecord(read.value) : null;
  if (record) draftCache.set(ctx, { record, durable: true });
  return record;
};
const sameDraftRecord = (left, right) =>
  (left === null && right === null) ||
  (left !== null && right !== null && JSON.stringify(left) === JSON.stringify(right));
// Refresh is a reconciliation as real as a storage event. Publish an adopted shared
// generation after the current call returns, so every mounted view follows the cache
// without making a composer's synchronous close clear itself recursively.
const projectDraftRecord = (ctx, record) =>
  queueMicrotask(() => {
    const current = draftCache.get(ctx)?.record ?? null;
    if (!sameDraftRecord(current, record)) return;
    const active = current && !current.settled && !attemptAccepted(current.attempt);
    tellDraft(ctx, active ? current.text : null, active ? current.payload : undefined);
  });
// A nondurable branch may replace exactly the shared generation it was editing, not
// merely whatever record happens to be there when a failed writer becomes writable
// again. A tombstone for that base is the older branch settling; it still cannot erase
// the newer local words. An unrelated attempt is later shared ownership and wins.
const sharedIsBaseOf = (branch, shared) =>
  branch.base === null ? shared === null : shared?.attempt === branch.base;
// A durable cache is a rendering convenience, never a claim that storage still holds
// that generation. Refresh it immediately before sending or settling. If the
// read itself is refused, the cache is the only copy available. A nondurable branch wins
// only over its own base; unrelated shared news wins even when its storage event was
// delayed or suppressed.
const refreshDraftRecord = (ctx) => {
  const cached = draftCache.get(ctx);
  const read = draftStore.read(DRAFT + ctx);
  if (!read.available) return cached?.record ?? null;
  const shared = parseDraftRecord(read.value);
  if (cached && !cached.durable) {
    if (sameDraftRecord(cached.record, shared)) {
      cached.durable = true;
      return cached.record;
    }
    if (sharedIsBaseOf(cached.record, shared)) {
      if (cached.record.settled) cached.durable = writeDraftRecord(ctx, cached.record);
      return cached.record;
    }
  }
  const changed = Boolean(cached && !sameDraftRecord(cached.record, shared));
  if (shared) draftCache.set(ctx, { record: shared, durable: true });
  else draftCache.delete(ctx);
  if (changed) projectDraftRecord(ctx, shared);
  return shared;
};
const activeDraftRecord = (ctx) => {
  const record = rawDraftRecord(ctx);
  return record && !record.settled && !attemptAccepted(record.attempt) ? record : null;
};
// Every tombstone is an ownership claim, whether it follows Send, Cancel, a widget
// action, or a poll that observed the attempt in the log. Re-read shared storage before
// making that claim so a stale view cannot settle a newer durable generation. A refused
// read and a nondurable local edit still use the document cache, their only copy.
const settleDraft = (ctx, attempt) => {
  const current = refreshDraftRecord(ctx);
  if (!current || current.settled || current.attempt !== attempt) return false;
  const currentDurable = draftCache.get(ctx)?.durable;
  // If this write fails, the cache tombstone still descends from whatever the active
  // branch could replace. If it succeeds, the tombstone itself is the new shared
  // generation and later edits descend from its attempt.
  const storedRecord = { attempt, base: attempt, settled: true };
  const durable = writeDraftRecord(ctx, storedRecord);
  const record = durable
    ? storedRecord
    : {
        attempt,
        base: currentDurable ? current.attempt : current.base,
        settled: true,
      };
  draftCache.set(ctx, { record, durable });
  return true;
};
export const newAttempt = () => {
  const bytes = new Uint8Array(16);
  // Unlike randomUUID(), getRandomValues is available when leaf is served over plain
  // HTTP to a stated/LAN host as well as in a secure localhost context.
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
};
export const saveDraft = (ctx, text, payload) => {
  const cached = draftCache.get(ctx);
  const previous = rawDraftRecord(ctx);
  // A series of local edits whose writes all fail is one branch from the last shared
  // generation, not a chain that progressively forgets what it may replace.
  const base =
    cached && !cached.durable && previous ? previous.base : (previous?.attempt ?? null);
  const record = {
    text,
    attempt: newAttempt(),
    base,
    ...(payload === undefined ? {} : { payload }),
  };
  const durable = writeDraftRecord(ctx, record);
  draftCache.set(ctx, { record, durable });
  return durable;
};
export const clearDraft = (ctx) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled) {
    draftCache.delete(ctx);
    return false;
  }
  return settleDraft(ctx, current.attempt);
};
export const loadDraft = (ctx) => activeDraftRecord(ctx)?.text ?? null;
export const loadDraftPayload = (ctx) => activeDraftRecord(ctx)?.payload;
export const draftContexts = () =>
  new Set([
    ...draftCache.keys(),
    ...draftStore
      .keys()
      .filter((key) => key.startsWith(DRAFT))
      .map((key) => key.slice(DRAFT.length)),
  ]);

// The log is authoritative over a stale active storage record. Run after each poll so a
// remove-resistant record from an accepted send becomes a tombstone in every live tab;
// activeDraftRecord already masks it during the write attempt itself.
export function settleAcceptedDrafts() {
  for (const ctx of draftContexts()) {
    const record = refreshDraftRecord(ctx);
    if (
      record &&
      !record.settled &&
      attemptAccepted(record.attempt) &&
      settleDraft(ctx, record.attempt)
    )
      tellDraft(ctx, null);
  }
}

// One draft generation has one attempt across every tab showing this page. Two tabs may
// POST it together; the append-locked log returns the same event to both. The attempt is
// also what lets a replacement tab recover after the first sender dies.
//
// Attempt and exact untrimmed text are rechecked immediately before POST. A successful
// older send settles only that generation; any later edit has a fresh attempt and remains
// standing.
export async function sendDraft(ctx, owns, send) {
  const before = activeDraftRecord(ctx);
  const refreshed = refreshDraftRecord(ctx);
  const current =
    refreshed && !refreshed.settled && !attemptAccepted(refreshed.attempt)
      ? refreshed
      : null;
  if (
    !before ||
    !current ||
    current.attempt !== before.attempt ||
    current.text !== before.text ||
    !owns()
  )
    return null;
  const sent = await send(current.attempt, current.payload);
  if (sent && settleDraft(ctx, current.attempt)) tellDraft(ctx, null);
  return sent;
}

// A draft written in another view, routed to whatever is showing it here. The document is
// the bus, as it is for replayed actions (watchActions), and that is what supplies the
// index this needs — from a draft's context to the box on screen — without a map of our
// own to hold in step with the panel: a box that has left the document takes its view off
// with it (mirrorDraft). The callback takes the store's vocabulary: active words and
// their optional submission payload, or null and no payload for settlement.
//
// It does not run on subscribe, which is where this parts company with watchActions. The
// draft a box opens with and the news that another tab changed one are different facts,
// and the boxes answer them differently: a draft editor opens on recovery at load and
// stays shut for a keystroke made elsewhere, because news arriving has no gesture behind
// it and so may move nothing.
export function watchDraft(ctx, callback) {
  const update = (ev) =>
    ev.detail.ctx === ctx && callback(ev.detail.value, ev.detail.payload);
  document.addEventListener(DRAFT_NEWS, update);
  return () => document.removeEventListener(DRAFT_NEWS, update);
}
addEventListener("storage", (ev) => {
  const prefix = PAGE_SCOPE + DRAFT;
  // Null where the whole store was cleared, and every key of another page on this origin
  // besides — a published site serves each example from one root.
  if (!ev.key?.startsWith(prefix)) return;
  const ctx = ev.key.slice(prefix.length);
  const incoming = parseDraftRecord(ev.newValue);
  const cached = draftCache.get(ctx);
  const current = cached?.record;
  // Reconcile the same way the lock callback does. A nondurable branch can reassert
  // itself over its base (including that base's tombstone), but unrelated active news
  // is a later shared generation and retires the local branch.
  if (current && !cached.durable) {
    if (sameDraftRecord(current, incoming)) cached.durable = true;
    else if (sharedIsBaseOf(current, incoming)) {
      cached.durable = writeDraftRecord(ctx, current);
      return;
    }
  }
  if (incoming) draftCache.set(ctx, { record: incoming, durable: true });
  else draftCache.delete(ctx);
  const active = incoming && !incoming.settled && !attemptAccepted(incoming.attempt);
  tellDraft(ctx, active ? incoming.text : null, active ? incoming.payload : undefined);
});

// One box's view of one draft: sync.value() reads the complete durable value, including
// a pasted-media projection that is not exposed in the textarea. Write .value only when
// that complete value differs, because writing it on a focused box moves the caret to
// the end. The box grows to fit either way, sizing being the stylesheet's (wireInput),
// and sync() makes its visible words, media shelf, and Send button agree.
//
// A box out of the document drops its view at the next word it would have shown, rather
// than at the moment it leaves — the one box that ever leaves is a reply box going with
// its resolved thread, and asking the panel to say so would be the index this design is
// for not keeping. What the check has to hold is that such a box never renders and never
// doubles the live one: a thread a retraction reopens is a second box on the same
// context, and the one that is still in the document is the one that paints.
export function mirrorDraft(ta, sync, ctx) {
  const off = watchDraft(ctx, (value) => {
    if (!ta.isConnected) return off();
    const text = value ?? "";
    if (sync.value() === text) return;
    ta.value = text;
    sync();
  });
}
// Reply drafts are never pruned. A thread resolving is not a discard: another
// tab's Resolve, or this tab accepting a suggestion whose action `resolves`,
// used to sweep an unsent reply out of storage — words going missing, where the
// norm is that Cancel is the only discard. A thread a retraction reopens finds
// the draft where it was left.
