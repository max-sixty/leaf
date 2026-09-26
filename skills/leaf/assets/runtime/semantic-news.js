/* Meaningful news from complete, accepted page readings.

   The server owns thread content, user obligations, request lifecycles,
   response conditions, and page activity. This module compares those readings after
   presentation. It remembers which source versions were observed, not a second
   account of what the page currently means.

   New agent content is the server's `unread` reading, the same one the Threads panel
   and banner paint: a version is news the first time this tab sees it unread, and
   never once the user has taken it in, here or in another tab. What the user has
   not read is news on the first reading too, since it arrived while they were away.
   Every other kind of news is a change between readings, so the first reading
   establishes it without announcing it. */
import { moved } from "./thread/model.js";

const identity = (record) => record.attempt ?? record.id;

// News reads the shown revision's view: the one the page just presented, whose Asks
// the tray and banner count paint. While an activation waits (a gesture defers it, or
// the document is a pinned version), an Ask the active revision adds is not on this
// page yet; it becomes news when a revision holding it is presented.
export function semanticNewsReading(root) {
  const page = root.effective.view?.document;
  if (!page) throw new Error("The shown page has no browser reading");
  const state = root.authoritative;
  return {
    page,
    thread: state.browser.thread,
    workflows: state.workflows,
    activity: state.activity,
    requestOutcomes: state.browser.request_outcomes,
  };
}

// Unread agent content, oldest move first. A failure reply is unread content too, but
// its news is the failed response's, announced from its workflow.
function unreadContent(threadView) {
  return threadView.threads
    .flatMap((thread) =>
      thread.unread.map(({ message: id, version }) => ({
        thread: thread.root.id,
        message: thread.msgs.find((message) => message.id === id),
        version,
      })),
    )
    .filter(({ message }) => !message.failure)
    .sort((a, b) => moved(a.message).seq - moved(b.message).seq);
}

function userObligations(page, threadView) {
  const held = new Map();
  for (const ask of page.asks.user)
    held.set(JSON.stringify(["page", ask.id]), { source: ask.id, thread: null });
  const askedThreads = new Set();
  for (const ask of threadView.asks.user) {
    held.set(JSON.stringify(["thread", ask.thread, ask.id]), {
      source: ask.id,
      thread: ask.thread,
    });
    askedThreads.add(ask.thread);
  }
  for (const thread of threadView.threads) {
    if (
      thread.attention?.kind === "needs_user" &&
      thread.attention.reason === "ask" &&
      !askedThreads.has(thread.root.id) &&
      thread.user_prompt
    )
      held.set(
        JSON.stringify(["thread-turn", thread.root.id, thread.user_prompt.version]),
        {
          source: thread.user_prompt.message,
          thread: thread.root.id,
        },
      );
  }
  return held;
}

function responseFailures(workflows) {
  const failures = new Map();
  for (const workflow of workflows) {
    if (
      workflow.condition?.operation !== "response" ||
      !["failed", "interrupted"].includes(workflow.condition.kind)
    )
      continue;
    const source = workflow.response;
    if (!source?.attempt && !source?.id) continue;
    const key = identity(source);
    const failure = {
      key,
      kind: workflow.condition.kind,
      input: workflow.input,
      thread: workflow.subject.kind === "thread" ? workflow.subject.id : null,
      seq: workflow.seq ?? 0,
    };
    failures.set(key, failure);
  }
  return failures;
}

const agentAvailable = (activity) =>
  activity.held && ["listening", "working"].includes(activity.kind);

export function observeSemanticNews(prior, reading) {
  const content = unreadContent(reading.thread);
  const obligations = userObligations(reading.page, reading.thread);
  const failures = responseFailures(reading.workflows);
  const available = agentAvailable(reading.activity);
  const first = prior === null;
  const observed = {
    content: new Set(prior?.content),
    receipts: new Set(prior?.receipts),
    failures: new Set(prior?.failures),
    obligations: new Set(obligations.keys()),
    obligationEpisodes: new Map(prior?.obligationEpisodes),
    available,
    availabilityEpisode: prior?.availabilityEpisode ?? 0,
  };
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
  for (const { request, widget, receipt } of reading.requestOutcomes) {
    if (!first && !observed.receipts.has(receipt.id))
      news.push({
        kind: "request_outcome",
        key: `request:${receipt.id}`,
        request,
        widget,
        receipt,
      });
    observed.receipts.add(receipt.id);
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
        ...obligation,
      });
  }
  if (available && !prior?.available) {
    observed.availabilityEpisode += 1;
    if (!first)
      news.push({
        kind: "agent_available",
        key: `agent-available:${observed.availabilityEpisode}`,
      });
  }
  return { observed, news };
}

// A waiting status-line notice keeps the historical receipts but drops assertions
// that the latest successfully presented reading has since superseded. In particular,
// an answer can replace a failure while the user's own command holds the line.
export function currentSemanticNews(news, reading, observed) {
  const versions = new Set(unreadContent(reading.thread).map(({ version }) => version));
  const obligations = userObligations(reading.page, reading.thread);
  const failures = responseFailures(reading.workflows);
  return news.flatMap((item) => {
    switch (item.kind) {
      case "agent_content":
        return versions.has(item.version) ? [item] : [];
      case "request_outcome":
        return [item];
      case "response_failure": {
        const current = failures.get(item.key.slice("response:".length));
        return current ? [{ ...item, condition: current.kind }] : [];
      }
      case "user_obligation":
        return obligations.has(item.sourceKey) ? [item] : [];
      case "agent_available":
        return agentAvailable(reading.activity) &&
          item.key === `agent-available:${observed.availabilityEpisode}`
          ? [item]
          : [];
      default:
        throw new Error(`Unknown semantic news kind ${item.kind}`);
    }
  });
}

export function combineSemanticNews(older, newer) {
  return [...new Map([...older, ...newer].map((item) => [item.key, item])).values()];
}

const plural = (count, singular, pluralForm = `${singular}s`) =>
  `${count} ${count === 1 ? singular : pluralForm}`;

export function semanticNewsNotice(news) {
  if (!news.length) return "";
  const byKind = (kind) => news.filter((item) => item.kind === kind);
  const content = byKind("agent_content");
  const failures = byKind("response_failure");
  const requests = byKind("request_outcome");
  const obligations = byKind("user_obligation");
  const availability = byKind("agent_available");
  const clauses = [];

  if (content.length === 1) {
    const { message } = content[0];
    const agent = message.agent || "Agent";
    const verb = message.kind === "reply" ? "reply" : "comment";
    clauses.push(
      message.edited
        ? `${agent} updated a ${verb}`
        : `${agent} ${verb === "reply" ? "replied" : "commented"}`,
    );
  } else if (content.length) {
    const replies = content.filter(({ message }) => message.kind === "reply");
    const threads = new Set(content.map((item) => item.thread)).size;
    clauses.push(
      replies.length === content.length
        ? `${plural(content.length, "reply", "replies")} in ${plural(threads, "thread")}`
        : `${plural(content.length, "agent message")} in ${plural(threads, "thread")}`,
    );
  }
  for (const condition of ["failed", "interrupted"]) {
    const count = failures.filter((item) => item.condition === condition).length;
    if (count)
      clauses.push(
        count === 1
          ? `Response ${condition}`
          : `${plural(count, "response")} ${condition}`,
      );
  }
  for (const status of ["failed", "succeeded"]) {
    const count = requests.filter((item) => item.receipt.status === status).length;
    if (count)
      clauses.push(
        count === 1 ? `Request ${status}` : `${plural(count, "request")} ${status}`,
      );
  }
  if (obligations.length)
    clauses.push(
      obligations.length === 1
        ? "Input needed"
        : `${plural(obligations.length, "item")} need your input`,
    );
  if (availability.length) clauses.push("Agent active on this page");
  return clauses.join("; ");
}
