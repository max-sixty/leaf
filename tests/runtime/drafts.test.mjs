/* Words this document holds that the page's server never took, met by another tab's
   or device's generation of their draft there (`adopt`, runtime/records/drafts.js). The server
   below answers each draft write as `drafts.py` does: it takes the write only over a
   generation the write names or over none, and answers with what it holds. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);

/** @type {Map<string, {attempt: string, text: string, payload?: object, version: number}>} */
const server = new Map();
let version = 0;
// Answers the test holds back, released in the order the writes went out.
/** @type {(() => void)[] | null} */
let held = null;
// Whether draft writes fail as they do while the server is out of reach.
let unreachable = false;
// Each draft write's request, settled or not, for a test that reads what follows it.
/** @type {Promise<unknown>[]} */
const draftWrites = [];
// A canonical page also posts diagnostic interactions, which the server takes.
globalThis.fetch = (url, init) => {
  const answer = answerFetch(url, init);
  if (String(url).endsWith("/api/draft")) draftWrites.push(answer);
  return answer;
};
/** @param {RequestInfo | URL} url @param {RequestInit} [init] */
const answerFetch = async (url, init) => {
  if (!String(url).endsWith("/api/draft")) return new Response(null, { status: 204 });
  if (unreachable) throw new TypeError("Failed to fetch");
  const { context, expect, record } = JSON.parse(String(init?.body));
  const current = server.get(context) ?? null;
  const written = current === null || expect.includes(current.attempt);
  if (written) {
    version += 1;
    if (record.settled) server.delete(context);
    else server.set(context, { ...record, version });
  }
  const answer = {
    written,
    store: "store",
    version,
    record: server.get(context) ?? null,
  };
  if (held) await new Promise((resolve) => held?.push(() => resolve(undefined)));
  return Response.json(answer);
};
// The tab's memory, which a page going away leaves its drafts in.
/** @type {Map<string, string>} */
const tabMemory = new Map();
window.lfStorage.tabStore = {
  read: (key) => ({ available: true, value: tabMemory.get(key) ?? null }),
  get: (key) => tabMemory.get(key) ?? null,
  set: (key, value) => {
    if (value === null) tabMemory.delete(key);
    else tabMemory.set(key, value);
    return true;
  },
  where: (key) => ({ store: "session", key }),
  keys: () => [...tabMemory.keys()],
};
const { draftsWaiting, giveBackWords, loadDraft, saveDraft, sendDraft, watchDraft } =
  await import("/runtime/records/drafts.js");

/** Another tab's or device's generation of the draft at `ctx`, written to the server
 * behind this document. @param {string} ctx @param {string} text @param {object} [payload] */
const writtenElsewhere = (ctx, text, payload) => {
  version += 1;
  server.set(ctx, { attempt: `elsewhere-${ctx}`, text, payload, version });
};
/** Waits until every draft write has settled and the document has heard each answer
 * or failure: the handlers run in the request's own microtasks, so a timer turn after
 * the last request settles follows them, and a write an answer sends next joins the
 * wait. */
const writesSettled = async () => {
  for (let seen = -1; seen !== draftWrites.length;) {
    seen = draftWrites.length;
    await Promise.allSettled(draftWrites);
    await new Promise((resolve) => setTimeout(resolve));
  }
};
const leave = () =>
  window.dispatchEvent(new Event("beforeunload", { cancelable: true }));
/** The next words and payload every view of the draft at `ctx` is told of.
 * @param {string} ctx @returns {Promise<{value: string | null, payload: unknown}>} */
const told = (ctx) =>
  new Promise((resolve) => {
    const off = watchDraft(ctx, (value, payload) => {
      off();
      resolve({ value, payload });
    });
  });

test("words one copy already holds don't come twice", async () => {
  writtenElsewhere("reply:longer-here", "  Fit the bracket.\n");
  const longer = told("reply:longer-here");
  saveDraft("reply:longer-here", "Fit the bracket. Then the cable.");
  assert.equal((await longer).value, "Fit the bracket. Then the cable.");
  const kept = server.get("reply:longer-here");
  assert.equal(kept?.text, "Fit the bracket. Then the cable.");
  assert.notEqual(kept?.attempt, "elsewhere-reply:longer-here");

  writtenElsewhere("reply:longer-there", "Fit the bracket. Then the cable.");
  const shorter = told("reply:longer-there");
  saveDraft("reply:longer-there", "the bracket.");
  assert.equal((await shorter).value, "Fit the bracket. Then the cable.");
  assert.equal(
    loadDraft("reply:longer-there")?.attempt,
    "elsewhere-reply:longer-there",
  );
  assert.equal(
    server.get("reply:longer-there")?.attempt,
    "elsewhere-reply:longer-there",
  );
});

test("words joined from both copies keep this document's payload, else the other's", async () => {
  writtenElsewhere("composer:mine", "Theirs.", { drawing: "theirs" });
  const mine = told("composer:mine");
  saveDraft("composer:mine", "Mine.", { drawing: "mine" });
  assert.deepEqual(await mine, {
    value: "Theirs.\n\nMine.",
    payload: { drawing: "mine" },
  });

  writtenElsewhere("composer:theirs", "Theirs.", { drawing: "theirs" });
  const theirs = told("composer:theirs");
  saveDraft("composer:theirs", "Mine.");
  assert.deepEqual(await theirs, {
    value: "Theirs.\n\nMine.",
    payload: { drawing: "theirs" },
  });
});

test("words already standing write nothing more, whatever their payload", async () => {
  writtenElsewhere("composer:touched", "Same words.", { touched: 1 });
  const same = told("composer:touched");
  saveDraft("composer:touched", "Same words.", { touched: 2 });
  assert.deepEqual(await same, {
    value: "Same words.",
    payload: { touched: 1 },
  });
  assert.equal(server.get("composer:touched")?.attempt, "elsewhere-composer:touched");
});

test("words this document is sending give way to another tab's", async () => {
  writtenElsewhere("reply:sending", "Words another tab wrote.");
  held = [];
  saveDraft("reply:sending", "Words sent before their write was answered.");
  /** @type {(sent: boolean) => void} */
  let accept = () => {};
  const sending = sendDraft(
    "reply:sending",
    () => true,
    () => new Promise((resolve) => (accept = resolve)),
  );
  const answered = told("reply:sending");
  const release = held;
  held = null;
  for (const answer of release) answer();
  assert.equal((await answered).value, "Words another tab wrote.");
  accept(true);
  await sending;
  assert.equal(loadDraft("reply:sending")?.text, "Words another tab wrote.");
  assert.equal(server.get("reply:sending")?.text, "Words another tab wrote.");
});

// Only the send's answer says whether the log took the words, so the reload mustn't
// start from them: a store that replaced this one would take them in as unsent.
test("a page going away leaves its tab no copy of saved words it is sending", async () => {
  saveDraft("reply:leaving", "Words sent as the page went away.");
  for (let turn = 0; draftsWaiting() && turn < 100; turn += 1)
    await new Promise((resolve) => setTimeout(resolve));
  assert.equal(draftsWaiting(), 0);
  void sendDraft(
    "reply:leaving",
    () => true,
    () => new Promise(() => {}),
  );
  window.dispatchEvent(new Event("pagehide"));
  const left = new Map(JSON.parse(tabMemory.get("lf-drafts-waiting") ?? "[]"));
  assert.equal(left.get("reply:leaving")?.copy, null);
});

// Words no write is carrying go with the document, so leaving asks first; words the
// server has taken leave quietly.
test("leaving asks first while words wait that no write carries", async () => {
  await writesSettled();
  const waiting = draftsWaiting();
  assert.equal(leave(), true);
  unreachable = true;
  saveDraft("reply:stranded", "Words typed while the server was away.");
  await writesSettled();
  assert.equal(draftsWaiting(), waiting + 1);
  assert.equal(leave(), false);
  unreachable = false;
  saveDraft("reply:stranded", "Words typed while the server was away, and after.");
  await writesSettled();
  assert.equal(
    server.get("reply:stranded")?.text,
    "Words typed while the server was away, and after.",
  );
  assert.equal(draftsWaiting(), waiting);
  assert.equal(leave(), true);
});

// A comment's drawing is the user's work as its words are, so a draft holding only a
// drawing that no write carries asks before leaving too.
test("leaving asks first while a drawing waits that no write carries", async () => {
  const drawing = {
    strokes: [
      [
        [0, 0],
        [10, 10],
      ],
    ],
    box: [100, 100],
    viewport: [800, 600],
    scheme: "light",
  };
  await writesSettled();
  const waiting = draftsWaiting();
  assert.equal(leave(), true);
  unreachable = true;
  saveDraft("composer:drawn", "", { drawing });
  await writesSettled();
  assert.equal(draftsWaiting(), waiting + 1);
  assert.equal(leave(), false);
  unreachable = false;
  saveDraft("composer:drawn", "", { drawing });
  await writesSettled();
  assert.deepEqual(server.get("composer:drawn")?.payload, { drawing });
  assert.equal(draftsWaiting(), waiting);
  assert.equal(leave(), true);
});

// Words an undo gives back to a box the user has begun keep what the box holds, even
// only whitespace, and the box's own payload rather than the sent message's.
test("words given back to a box holding only whitespace keep it and its payload", async () => {
  const own = { anchor: { says: "the bracket" }, mode: "comment" };
  saveDraft("composer:spaced", "  ", own);
  await writesSettled();
  const back = told("composer:spaced");
  giveBackWords("composer:spaced", "Fit the bracket.", {
    anchor: { says: "the cable" },
  });
  const { value, payload } = await back;
  assert.equal(value, "Fit the bracket.\n\n  ");
  assert.deepEqual(payload, own);
  assert.deepEqual(loadDraft("composer:spaced")?.payload, own);
});

// A reaction writes no words, so taking back one that opened a thread gives back only
// the reply begun under that thread, to the passage's box, and with none begun leaves
// the passage's box as it stands.
test("words given back with none of their own bring only the reply under them", async () => {
  saveDraft("reply:reacted", "Also check the cap.", {});
  await writesSettled();
  const passage = { anchor: { says: "the cap" } };
  giveBackWords("composer:reacted", "", passage, "reply:reacted");
  assert.equal(loadDraft("composer:reacted")?.text, "Also check the cap.");
  assert.deepEqual(loadDraft("composer:reacted")?.payload, passage);
  assert.equal(loadDraft("reply:reacted"), null);
  giveBackWords("composer:untouched", "", passage, "reply:none");
  assert.equal(loadDraft("composer:untouched"), null);
});
