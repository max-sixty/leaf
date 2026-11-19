/* Words this document holds that the page's server never took, met by another tab's
   or device's generation of their draft there (`adopt`, runtime/drafts.js). The server
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
// A canonical page also posts diagnostic interactions, which the server takes.
globalThis.fetch = async (url, init) => {
  if (!String(url).endsWith("/api/draft")) return new Response(null, { status: 204 });
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
const { loadDraft, saveDraft, sendDraft, watchDraft } =
  await import("/runtime/drafts.js");

/** Another tab's or device's generation of the draft at `ctx`, written to the server
 * behind this document. @param {string} ctx @param {string} text @param {object} [payload] */
const writtenElsewhere = (ctx, text, payload) => {
  version += 1;
  server.set(ctx, { attempt: `elsewhere-${ctx}`, text, payload, version });
};
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
