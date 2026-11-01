/* Meaningful news from complete, accepted page readings.

   The server owns thread content, user obligations and response conditions. This
   module compares those readings after presentation. It remembers which source
   versions were observed, not a second account of what the page currently means.

   The agent's activity is no news here: the page's status says it in the same seat a
   notice would take, and page-status.js announces a change of its kind. Removed on 26
   October 2026: "Claude active on this page", which stood for four seconds in front of
   the status line that named the agent's work.

   New agent content is the server's `unread` reading, the same one the floating panel
   paints: a version is news the first time this tab sees it unread, and
   never once the user has taken it in, here or in another tab. What the user has
   not read is news on the first reading too, since it arrived while they were away.
   Every other kind of news is a change between readings, so the first reading
   establishes it without announcing it. */
import { moved } from "./thread/model.js";
import { NOT_ANSWERED } from "./thread/workflow.js";
import { agentSays, leafSays } from "./voice.js";
import { excerptWords } from "./words.js";

/** @typedef {ReturnType<typeof semanticNewsReading>} NewsReading
 * @typedef {import("../types/domain.js").Message} Message
 * @typedef {{kind: "agent_content", key: string, thread: string, message: Message, version: string}} ContentNews
 * @typedef {{kind: "response_failure", key: string, condition: "failed" | "interrupted",
 * input: string, thread: string | null, seq: number}} FailureNews
 * @typedef {{kind: "user_obligation", key: string, sourceKey: string, episode: number,
 * source: string, thread: string | null, message: string | null}} ObligationNews
 * @typedef {ContentNews | FailureNews | ObligationNews} SemanticNews
 * @typedef {{content: Set<string>, failures: Set<string>, obligations: Set<string>, obligationEpisodes: Map<string, number>}} ObservedNews
 */

/** @param {{attempt?: string | null, id?: string | null}} record */
const identity = (record) => record.attempt ?? record.id;

// News reads the shown revision's view: the one the page just presented, whose On me list
// the floating panel counts. While an activation waits (a gesture defers it, or
// the document is a pinned version), an obligation the active revision adds is not on this
// page yet; it becomes news when a revision holding it is presented.
/** @param {ReturnType<typeof import("./semantic-state.js").readApplication>} root */
export function semanticNewsReading(root) {
  const view = root.effective.view;
  if (!view) throw new Error("The shown page has no browser reading");
  const state = root.authoritative;
  if (!state) throw new Error("The shown page has no accepted reading");
  return {
    obligations: view.obligations,
    thread: view.thread,
    workflows: state.workflows,
  };
}

// Unread agent content, oldest first. A failure reply is unread content too, but
// its news is the failed response's, announced from its workflow.
/** @param {NewsReading["thread"]} threadView */
function unreadContent(threadView) {
  return threadView.threads
    .flatMap((thread) =>
      thread.unread.map(({ message: id, version }) => {
        const message = thread.msgs.find((message) => message.id === id);
        if (!message)
          throw new Error(`Unread version ${version} names missing message ${id}`);
        return { thread: thread.id, message, version };
      }),
    )
    .filter(({ message }) => !("failure" in message && message.failure))
    .sort((a, b) => Number(moved(a.message).seq) - Number(moved(b.message).seq));
}

// What the page asks of the user, with the agent message that holds each, if any. An
// update handed back to them is news through its failed response (`responseFailures`),
// not a second time as an obligation.
/** @param {NewsReading["obligations"]} items */
function userObligations(items) {
  /** @type {Map<string, Pick<ObligationNews, "source" | "thread" | "message">>} */
  const held = new Map();
  for (const item of items) {
    if (item.next_actor !== "user" || item.source.kind === "update") continue;
    const key =
      item.thread === null ? ["page", item.id] : ["thread", item.thread, item.id];
    held.set(JSON.stringify(key), {
      source: item.id,
      thread: item.thread,
      message: item.message,
    });
  }
  return held;
}

/** @param {NewsReading["workflows"]} workflows */
function responseFailures(workflows) {
  /** @type {Map<string, {key: string, kind: "failed" | "interrupted", input: string, thread: string | null, seq: number}>} */
  const failures = new Map();
  for (const workflow of workflows) {
    if (
      workflow.condition?.operation !== "response" ||
      (workflow.condition.kind !== "failed" &&
        workflow.condition.kind !== "interrupted")
    )
      continue;
    const source = workflow.response;
    if (!source) continue;
    const key = identity(source);
    if (!key) continue;
    failures.set(key, {
      key,
      kind: workflow.condition.kind,
      input: workflow.input,
      thread: workflow.thread,
      seq: workflow.seq,
    });
  }
  return failures;
}

/** @param {ObservedNews | null} prior @param {NewsReading} reading */
export function observeSemanticNews(prior, reading) {
  const content = unreadContent(reading.thread);
  const obligations = userObligations(reading.obligations);
  const failures = responseFailures(reading.workflows);
  const first = prior === null;
  const observed = {
    content: new Set(prior?.content),
    failures: new Set(prior?.failures),
    obligations: new Set(obligations.keys()),
    obligationEpisodes: new Map(prior?.obligationEpisodes),
  };
  /** @type {SemanticNews[]} */
  const news = [];

  for (const { thread, message, version } of content) {
    if (!observed.content.has(version))
      news.push({
        kind: "agent_content",
        key: `content:${version}`,
        thread,
        message,
        version,
      });
    observed.content.add(version);
  }
  for (const failure of failures.values()) {
    if (!first && !observed.failures.has(failure.key))
      news.push({
        ...failure,
        condition: failure.kind,
        kind: "response_failure",
        key: `response:${failure.key}`,
      });
    observed.failures.add(failure.key);
  }
  for (const [key, obligation] of obligations) {
    if (prior?.obligations.has(key)) continue;
    const episode = (observed.obligationEpisodes.get(key) ?? 0) + 1;
    observed.obligationEpisodes.set(key, episode);
    if (!first)
      news.push({
        kind: "user_obligation",
        key: `obligation:${key}:${episode}`,
        sourceKey: key,
        episode,
        ...obligation,
      });
  }
  return { observed, news };
}

// A waiting status-line notice drops assertions that the latest successfully
// presented reading has since superseded. In particular,
// an answer can replace a failure while the user's own command holds the line.
/** @param {readonly SemanticNews[]} news @param {NewsReading} reading @param {ObservedNews} observed @returns {SemanticNews[]} */
export function currentSemanticNews(news, reading, observed) {
  const versions = new Set(unreadContent(reading.thread).map(({ version }) => version));
  const obligations = userObligations(reading.obligations);
  const failures = responseFailures(reading.workflows);
  return news.flatMap(
    /** @returns {SemanticNews[]} */ (item) => {
      if (item.kind === "agent_content")
        return versions.has(item.version) ? [item] : [];
      if (item.kind === "response_failure") {
        const current = failures.get(item.key.slice("response:".length));
        return current ? [{ ...item, condition: current.kind }] : [];
      }
      return obligations.has(item.sourceKey) &&
        item.episode === observed.obligationEpisodes.get(item.sourceKey)
        ? [item]
        : [];
    },
  );
}

/** @param {readonly SemanticNews[]} older @param {readonly SemanticNews[]} newer */
export function combineSemanticNews(older, newer) {
  return [...new Map([...older, ...newer].map((item) => [item.key, item])).values()];
}

/** @param {number} count @param {string} singular @param {string} pluralForm */
const plural = (count, singular, pluralForm = `${singular}s`) =>
  `${count} ${count === 1 ? singular : pluralForm}`;

// One clause per fact, joined by the middle dot the panel's line joins every fact with,
// as parts each said by the agent or by Leaf (voice.js; notifications.js, `notice`). A
// single new message speaks for itself, its opening words in the agent's voice ("I
// changed the route."), with whatever it asks of the user, since the question and the
// message are one piece of news; that it replied, commented or edited its words is its
// own act, which Leaf relays in its voice. Everything else is Leaf's news, set apart in
// italic (glossary.md, "Reader-facing words"): what became of an answer, the counts, and
// what else is new on the user's list by the list's name.
const MESSAGE_WORDS = 60;
/** @param {readonly SemanticNews[]} news */
export function semanticNewsNotice(news) {
  const content = news.filter((item) => item.kind === "agent_content");
  const failures = news.filter((item) => item.kind === "response_failure");
  let obligations = news.filter((item) => item.kind === "user_obligation");
  /** @type {import("./voice.js").Said[][]} */
  const clauses = [];

  const single = content.length === 1 ? content[0] : null;
  if (single) {
    const { message } = single;
    obligations = obligations.filter((item) => item.message !== message.id);
    const words = excerptWords(message.text, MESSAGE_WORDS);
    clauses.push(
      words
        ? message.edited
          ? [agentSays(`Edited: ${words}`)]
          : [agentSays(words)]
        : [agentSays(message.kind === "reply" ? "Replied" : "Commented")],
    );
  } else if (content.length) {
    const replies = content.filter(({ message }) => message.kind === "reply");
    const threads = new Set(content.map((item) => item.thread)).size;
    clauses.push([
      leafSays(
        replies.length === content.length
          ? `${plural(content.length, "reply", "replies")} in ${plural(threads, "thread")}`
          : `${plural(content.length, "agent message")} in ${plural(threads, "thread")}`,
      ),
    ]);
  }
  const failed = failures.filter((item) => item.condition === "failed").length;
  const interrupted = failures.filter(
    (item) => item.condition === "interrupted",
  ).length;
  if (failed)
    clauses.push([failed === 1 ? NOT_ANSWERED : leafSays(`${failed} not answered`)]);
  if (interrupted)
    clauses.push([
      leafSays(
        interrupted === 1 ? "Interrupted mid-answer" : `Interrupted on ${interrupted}`,
      ),
    ]);
  if (obligations.length)
    clauses.push([
      leafSays(
        obligations.length === 1 ? "New on me" : `${obligations.length} new on me`,
      ),
    ]);
  return clauses.flatMap((clause, index) =>
    index ? [leafSays(" · "), ...clause] : clause,
  );
}
