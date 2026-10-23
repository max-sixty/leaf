/* What each seat says about a page's served activity: the page's status sentence and
   what its explanation adds, and a row of All pages. Both are worded here from the one
   `activity` reading the server sends, and from the page's queues, so a fact the seats
   share changes in one place. Nothing here reads or writes the document; page-status.js
   and live-leaves.js read what these return, the floating panel draws it, and
   `tests/runtime/activity-words.test.mjs` holds each sentence. */
import { JUST_NOW, ago } from "./presence.js";
import { itemNoun } from "./queues.js";

/** @type {Record<import("../framework/contract.js").ServedActivity["kind"], string>} */
const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  closed: "",
};
// Every step the server may report (`ServedWorkKind`) has its words here.
/** @type {Record<import("../framework/contract.js").ServedWorkKind, string>} */
const WORK_WORDS = {
  working: "working",
  thinking: "thinking",
  tool: "using a tool",
  awaiting_approval: "waiting for approval",
  awaiting_input: "waiting for input",
  awaiting_user: "waiting for me",
  replying: "replying",
};
const countResponses = (count) => `${count} response${count === 1 ? "" : "s"}`;
// What each canonical count says the agent owes, in the order a reader is told.
const COUNT_PHRASES = {
  active: "being worked on",
  handling: "owed on delivered updates",
  queued: "owed on queued updates",
  picked_up: "owed on delivered updates; no current turn observed",
  pending: "owed on updates awaiting delivery",
};
const phrased = (counts, kinds) =>
  kinds
    .filter((kind) => counts[kind])
    .map((kind) => `${countResponses(counts[kind])} ${COUNT_PHRASES[kind]}`);
// What the status and an All pages row both read off one page's server-owned `activity`
// before either words it. Each seat keeps its own sentences; a fact they share changes
// here once:
//
// - `left` says the turn's ending retired the belief, and `silentSince` dates the
//   silence by the reading's own `ts`, which the server already sets to that ending
//   for a dropped claim.
// - `listening` is whether input is still on its way to the agent (pending or queued),
//   which turns a listening page's open request into "listening".
// - `waiting` phrases the queued and pending updates, in that order, and `owed` the
//   other counts, for a seat with room to say them beside `waiting`.
export function activityFacts({ activity }) {
  const { counts } = activity;
  return Object.freeze({
    tone: TONE[activity.kind],
    work: activity.observed_kind ? WORK_WORDS[activity.observed_kind] : "working",
    left: Boolean(activity.dropped),
    silentSince: ago(activity.ts),
    listening: Boolean(counts.pending || counts.queued),
    waiting: Object.freeze(phrased(counts, ["queued", "pending"])),
    owed: Object.freeze(phrased(counts, ["active", "handling", "picked_up"])),
  });
}

// ---------- the page's status ----------

// Words following a status sentence: a step the transport watched after a middle dot,
// anything else as a sentence of its own. With nothing before them they stand alone.
const after = (head, words, step = false) =>
  !head
    ? words
    : step
      ? `${head} · ${words}`
      : `${head}${head.endsWith(".") ? "" : "."} ${words}`;

// Status sentences for an unreachable server or a state the page cannot apply.
const OFFLINE_LINE =
  "Server offline — reconnecting. Keep this page open so pending changes can send.";
// A refused key leaves the page as cut off as a dead server, but the server is up and
// only the user can end it. Opening the link in another tab sets the key this tab's
// next request carries, so its pending changes send without a reload.
const KEY_REFUSED_LINE =
  "The server no longer accepts this tab's key. Open the link Leaf printed in a new tab, and keep this one open so pending changes can send.";
const BROKEN_LINE = "Page couldn't apply current state — reload";
// A published page states what it is, whose copy the visitor reads, and where to
// install Leaf; the status line beside it says who revises the copy.
const publicationWords = (published) => [
  `${
    published.kind === "example"
      ? "This is an example on the Leaf website"
      : "This website is a Leaf page"
  }, and this copy is private to this browser. `,
  "Install Leaf",
];

// The updates delivered into an open turn, by kind: a comment in a thread, or an answer to an
// obligation. A lone update is the user's own; several are counted.
function deliveredWords({ comments, answers }) {
  if (comments + answers === 1) return comments ? "the comment" : "the answer";
  const counted = (count, noun) => `${count} ${noun}${count === 1 ? "" : "s"}`;
  return [
    comments && counted(comments, "comment"),
    answers && counted(answers, "answer"),
  ]
    .filter(Boolean)
    .join(" and ");
}

// Rendered strings derive from structured parts, so an authored detail keeps its
// exact source without recovering its position from a combined status sentence.
const textParts = (words) =>
  (Array.isArray(words) ? words : [words])
    .filter(Boolean)
    .map((part) => (typeof part === "string" ? { text: part } : part));
const textOf = (parts) => parts.map((part) => part.text).join("");
const appendWords = (parts, words, step = false) => {
  const head = textOf(parts);
  parts.push({ text: after(head, words, step).slice(head.length) });
};

// Both levels of wording follow server-owned activity. Short summaries retain the
// actionable distinction: working, listening, away, or nobody holding the page. How many
// updates are waiting or saved is the disclosure's; the row counts what waits on each
// side instead (`queueWords`). The third wording is what the sentence says that the
// summary does not, for a seat that shows both (`pageStatus`, `adds`), and the fourth
// whether the words ask the user to act (`pageStatus`, `asks`), which only a wording
// that asks sets.
function statusWords({
  age,
  agent,
  dated,
  shortDate,
  detail,
  detailSource,
  handling,
  invite,
  kind,
  listening,
  overdue,
  saved,
  work,
}) {
  if (kind === "closed") return ["Page closed", "Page closed", ""];
  if (kind === "unheld") {
    const meanwhile = `${saved} It picks up again when a session does.`;
    return ["No session", `No session holds this page. ${meanwhile}`, meanwhile];
  }
  // The agent's own sentence is the reason to look at the row while it works, so the
  // row keeps it and the ellipsis fits it to the room the controls leave. A sentence just
  // renewed needs no date; an older one is dated ahead of the detail, because the detail
  // is what the ellipsis eats first and a stale sentence with its date cut off is the one
  // reading this row must not give.
  //
  // Until the agent writes that sentence, what Leaf knows is which of the user's
  // updates were delivered into its open turn, so the row names them, in the words of
  // their Delivered stage, rather than standing on a bare "working", and the
  // disclosure says the agent's own words are still to come.
  if (kind === "working") {
    const delivered = deliveredWords(handling);
    const said = detail
      ? [" — ", { text: detail, source: detailSource }]
      : delivered
        ? [" — has " + delivered]
        : [];
    return [
      [`${agent} ${work}${age && age !== JUST_NOW ? " · " + age : ""}`, ...said],
      detail || !delivered
        ? [`${agent} is ${work}`, ...said]
        : `${agent} has ${delivered} and hasn't said what it's doing yet`,
      detail || !delivered ? "" : "It hasn't said what it's doing yet.",
    ];
  }
  // A declared request tells the user what to do. Preserve it on the row when
  // no pending input supersedes it; a generic attendance label would lose that cue.
  if (kind === "listening") {
    const awaits = detail ? `${agent} awaits — ${detail}` : invite;
    return listening
      ? [
          `${agent} listening`,
          `${agent} is listening${detail ? " — " + detail : ""}.`,
          detail ? `It asked: ${detail}.` : "",
        ]
      : // A request the agent declared asks the user for it; the stock words say only
        // where a comment starts.
        [awaits, awaits, "", Boolean(detail)];
  }
  if (kind === "stalled")
    return [
      shortDate,
      [
        dated,
        ...(detail ? [": ", { text: detail, source: detailSource }] : []),
        `. ${saved}`,
      ],
      [
        ...(detail
          ? ["Last said: ", { text: detail, source: detailSource }, ". "]
          : []),
        saved,
      ],
    ];
  // Away is only worth a nudge once input has stalled (`counts.overdue`): the
  // session's next turn picks up whatever it finds, and Leaf messages a harness it
  // can reach once it has seen the turn end.
  return overdue
    ? [
        `Nudge ${agent} in terminal`,
        `${dated}. ${saved} Nothing is answering them, so nudge it in the terminal.`,
        `${dated}. ${saved} Nothing is answering them.`,
        true,
      ]
    : [
        `${agent} away`,
        `${agent} isn't watching right now. ${saved} It picks them up next turn.`,
        `${saved} It picks them up next turn.`,
      ];
}

// The page's status from the server's latest answer: `state` is the reading the page
// adopted, and `reach` how the latest read was answered (the publication's `reach`):
// with that reading, with nothing (`unreachable`, or `refused` where the server refused
// this tab's key rather than going away), with an error of its own (`faulted`, whose
// words are `fault`), or with a reading the page could not apply (`broken`). The
// answer is the status's reading before the queues join it (`statusModel`): its
// `kind`, the dot's `tone`, the row's `summary`, the disclosure's `explanation`, what
// that explanation `adds` to the summary for a seat that shows both (the floating
// panel's menu), whether it `asks` the user to act, such as to nudge the agent, answer
// what it declared it waits for, approve in its own session, or reload, which a seat
// can draw louder than a status that only reports, and the `actionableWork` whose
// change is announced. Each reading the user acts on differently
// has its own `kind`, since a change of kind is what the status announces
// (page-status.js): a server that went away and then starts refusing this tab's key
// asks something new of the user.
export function pageStatus(state, { reach = "reached", fault = null } = {}) {
  if (reach === "broken")
    return {
      kind: "broken",
      tone: "blocked",
      summary: BROKEN_LINE,
      explanation: BROKEN_LINE,
      adds: "",
      asks: true,
    };
  if (reach === "refused")
    return {
      kind: "refused",
      tone: "blocked",
      summary: "Key refused — open Leaf's link in a new tab",
      explanation: KEY_REFUSED_LINE,
      adds: "Keep this tab open so pending changes can send.",
      asks: true,
    };
  // A server answering with an error of its own is up and failing, which nothing the
  // user does here repairs: the page asks again on its clock, and the server's words say
  // what failed.
  if (reach === "faulted") {
    const said = fault.replace(/\.$/, "");
    return {
      kind: "faulted",
      tone: "blocked",
      summary: "Server error — retrying",
      explanation: `The server answered with an error: ${said}. Retrying.`,
      adds: `It answered: ${said}. Retrying.`,
    };
  }
  // An unreachable server is reported, not asked about: the page retries on its own, the
  // words being written are kept as drafts, and a change the user sends meanwhile says
  // itself that it is waiting (delivery.js). The leaf still turns red, since the page
  // has lost its link to the agent, and the words stay a report (floating-panel.css).
  if (reach !== "reached")
    return {
      kind: "unreachable",
      tone: "blocked",
      summary: "Server offline — reconnecting",
      explanation: OFFLINE_LINE,
      adds: "",
    };
  const { activity, agent, publication = null } = state;
  // On Leaf's website any comment starts the agent (`leaf_website`), so whenever it
  // isn't working it listens: no session holds a copy until its first comment, and one
  // that has gone quiet since starts again at the next. Its work reads as on any page,
  // and the introduction and its links join the explanation (`statusModel`).
  const onCall = Boolean(publication) && activity.kind !== "working";
  const kind = onCall ? "listening" : activity.kind;
  // A request the agent declared still stands; the line of work it left does not.
  const detail = !onCall || activity.kind === "listening" ? activity.detail : "";
  const facts = activityFacts(state);
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = "Updates are saved.";
  const checkedIn = facts.silentSince
    ? `${agent} last checked in ${facts.silentSince}`
    : `No check-in from ${agent} is recorded`;
  const ended = `${agent}’s turn ended${facts.silentSince ? " " + facts.silentSince : ""}`;
  const age = kind === "working" && activity.ts ? ago(activity.ts) : "";
  const [summaryWords, explanationWords, beyond, asked = false] = statusWords({
    age,
    agent,
    dated: facts.left ? ended : checkedIn,
    shortDate: facts.left ? ended : checkedIn,
    detail,
    detailSource: activity.detail_source,
    handling: {
      comments: activity.counts.handling_comments,
      answers: activity.counts.handling - activity.counts.handling_comments,
    },
    invite: publication
      ? `${agent} awaits — comment to revise this copy`
      : `${agent} awaits — select text to comment`,
    kind,
    listening: facts.listening,
    overdue: activity.counts.overdue,
    saved,
    work: facts.work,
  });
  const summaryParts = textParts(summaryWords);
  const explanationParts = textParts(explanationWords);
  if (age) explanationParts.push({ text: ` (${age})` });
  const addsParts = textParts(beyond);
  const append = (words, step = false) => {
    appendWords(explanationParts, words, step);
    appendWords(addsParts, words, step);
  };
  // What a transport can watch for itself, when the sentence beside it was written by
  // the agent: two facts about one turn, so the row keeps the one meant for the user
  // and the disclosure holds the step proving the session is still moving.
  if (activity.observed && activity.observed !== detail)
    append(activity.observed, true);
  if (facts.waiting.length && ["working", "listening"].includes(kind))
    append(`${facts.waiting.join(" · ")}.`);
  const actionableWork = activity.awaiting ? activity.observed_kind : null;
  // An approval or a question the agent's own window holds is answered there, and
  // the page is the one place the user may be looking instead.
  const waitsThere = Boolean(actionableWork) && kind === "working";
  if (waitsThere) append("It waits in its own session, not on this page.");
  return {
    kind,
    tone: TONE[kind],
    summary: textOf(summaryParts),
    summaryParts,
    explanation: textOf(explanationParts),
    explanationParts,
    adds: textOf(addsParts),
    addsParts,
    asks: asked || waitsThere,
    actionableWork,
    publication,
  };
}

// The page's two queues (`served_state.queues`), as the status's explanation names
// them: each side's kinds and each open to-do's title. The floating panel counts what
// waits on the user on its On me mark. What a widget registered is counted as what is
// left to answer, since only a row or the walk names it by its widget (`obligationWord`).
const QUEUE_WORDS = Object.freeze({
  widget: ["to answer", "to answer"],
  message: ["to answer", "to answer"],
  resend: ["update to send again", "updates to send again"],
  answer: ["answer", "answers"],
  reply: ["reply", "replies"],
  todo: ["to-do", "to-dos"],
});
function queueKinds(items) {
  const byKind = new Map();
  for (const item of items)
    byKind.set(itemNoun(item), [...(byKind.get(itemNoun(item)) ?? []), item]);
  return [...byKind].map(([kind, all]) => {
    const words = `${all.length} ${QUEUE_WORDS[kind][all.length === 1 ? 0 : 1]}`;
    // A to-do outlasts the turns and the thread that opened it (`todos.py`), so each
    // open one is named, including one on a thread the user has resolved.
    return kind === "todo"
      ? `${words} (${all.map((row) => row.obligation?.prompt.text ?? row.todo.title).join(" · ")})`
      : words;
  });
}
function queueWords({ on_user: onUser, on_agent: onAgent }, agent) {
  const named = (items, whom) =>
    items.length ? `Waiting on ${whom}: ${queueKinds(items).join(", ")}.` : "";
  return [named(onUser, "me"), named(onAgent, agent)].filter(Boolean).join(" ");
}
const WITHOUT_QUEUES = new Set(["broken", "refused", "faulted", "unreachable"]);

// What the chrome shows for a status (`pageStatus`, or a reading of startup's own),
// beside the page's `queues` (`readQueues`) and the `agent` they wait on: the leaf's
// `tone`, the row's `summary`, the `explanation` and
// what it `adds` to the summary, whether the status `asks` the user to act, and a
// publication's introduction and links, with which the explanation ends.
export function statusModel(status, queues, agent) {
  const { kind, tone, summary, asks = false, publication = null } = status;
  let { explanation, adds } = status;
  const explanationParts = [...(status.explanationParts ?? textParts(explanation))];
  const addsParts = [...(status.addsParts ?? textParts(adds))];
  const counted = WITHOUT_QUEUES.has(kind) ? "" : queueWords(queues, agent);
  if (counted) {
    appendWords(explanationParts, counted);
    appendWords(addsParts, counted);
    explanation = textOf(explanationParts);
    adds = textOf(addsParts);
  }
  let publicationModel = null;
  if (publication) {
    const [said, installs] = publicationWords(publication);
    const examples = publication.kind === "example" ? "Other examples" : null;
    appendWords(explanationParts, said + (examples ? `${examples} ` : "") + installs);
    explanation = textOf(explanationParts);
    publicationModel = Object.freeze({
      copy: said,
      examples,
      install: installs,
      installUrl: publication.install_url,
      examplesUrl: examples ? "/examples/" : null,
    });
  }
  return Object.freeze({
    tone,
    summary,
    summaryParts: status.summaryParts ?? textParts(summary),
    explanationParts,
    addsParts,
    asks,
    explanation,
    adds,
    publication: publicationModel,
  });
}

// ---------- a row of All pages ----------

// A row's whole account of a page: the dot's tone and one line of words, from an
// canonical activity computed by each serving page. The wording is the seat's.
export function leafRow(entry) {
  const { kind, counts, detail } = entry.activity;
  const facts = activityFacts(entry);
  // The same join for both kinds that have words of their own. The user opens this
  // panel to find which page needs them, so a bare `Awaits` beside a neighbour's
  // `Working — recording the demo` said least about the one row they are here to act
  // on: three pages waiting rendered as three identical rows, and which to go to
  // first is the whole question the panel was opened to answer.
  const stated = (word) => word + (detail ? " — " + detail : "");
  // The status's two silences, dated the same way and worded for a row.
  const silence = `${facts.left ? "Left" : "Quiet"}${facts.silentSince ? ` (${facts.silentSince})` : ""}`;
  const work = facts.work.replace(/^./, (letter) => letter.toUpperCase());
  const primary =
    kind === "working"
      ? stated(work)
      : kind === "listening"
        ? facts.listening
          ? stated("Listening")
          : stated("Awaits")
        : kind === "stalled"
          ? stated(silence)
          : kind === "away"
            ? counts.overdue
              ? silence
              : "Away"
            : kind === "unheld"
              ? "No session"
              : "Closed";
  const line = facts.waiting.length
    ? `${primary} · ${facts.waiting.join(" · ")}`
    : primary;
  return { tone: facts.tone, line };
}
