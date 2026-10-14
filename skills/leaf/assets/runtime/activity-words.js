/* What each seat says about a page's served activity: the banner's status sentence and
   its disclosure, and the leaves drawer's row. Both are worded here from the one
   `activity` reading the server sends, and from the page's queues, so a fact the seats
   share changes in one place. Nothing here reads or writes the document; banner.js and
   live-leaves.js paint what these return, and `tests/runtime/activity-words.test.mjs`
   holds each sentence. */
import { JUST_NOW, ago } from "./presence.js";
import { itemNoun } from "./queues.js";

const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  closed: "",
};
const WORK_WORDS = {
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
  handling: "owed on picked-up updates",
  queued: "owed on queued updates",
  picked_up: "owed on picked-up updates; no current turn observed",
  pending: "owed on updates awaiting delivery",
};
const phrased = (counts, kinds) =>
  kinds
    .filter((kind) => counts[kind])
    .map((kind) => `${countResponses(counts[kind])} ${COUNT_PHRASES[kind]}`);
// What the banner and the leaves drawer both read off one page's server-owned `activity`
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
    work: WORK_WORDS[activity.observed_kind] || "working",
    left: Boolean(activity.dropped),
    silentSince: ago(activity.ts),
    listening: Boolean(counts.pending || counts.queued),
    waiting: Object.freeze(phrased(counts, ["queued", "pending"])),
    owed: Object.freeze(phrased(counts, ["active", "handling", "picked_up"])),
  });
}

// ---------- the banner ----------

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
// A published page states who replies and where to install Leaf.
const publicationWords = (published) => [
  `${
    published.kind === "example"
      ? "This is an example on the Leaf website."
      : "This website is a Leaf page."
  } ${published.agent} replies and revises this private copy. `,
  "Install Leaf",
];

// The updates an open turn picked up, by kind: a comment in a thread, or an answer to an
// ask. A lone update is the user's own; several are counted.
function pickedUpWords({ comments, answers }) {
  if (comments + answers === 1) return comments ? "the comment" : "the answer";
  const counted = (count, noun) => `${count} ${noun}${count === 1 ? "" : "s"}`;
  return [
    comments && counted(comments, "comment"),
    answers && counted(answers, "answer"),
  ]
    .filter(Boolean)
    .join(" and ");
}

// Both levels of wording follow server-owned activity. Short summaries retain the
// actionable distinction: working, listening, away, or nobody holding the page. How many
// updates are waiting or saved is the disclosure's; the row counts what waits on each
// side instead (`queueWords`). The third wording is what the sentence says that the
// summary does not, for a seat that shows both (`pageStatus`, `adds`).
function statusWords({
  age,
  agent,
  dated,
  shortDate,
  detail,
  handling,
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
  // updates its open turn picked up, so the row names them, in the words of their
  // Picked up stage, rather than standing on a bare "working", and the disclosure
  // says the agent's own words are still to come.
  if (kind === "working") {
    const picked = pickedUpWords(handling);
    const said = detail ? " — " + detail : picked ? " — picked up " + picked : "";
    return [
      `${agent} ${work}${age && age !== JUST_NOW ? " · " + age : ""}${said}`,
      detail || !picked
        ? `${agent} is ${work}${said}`
        : `${agent} picked up ${picked} and hasn't said what it's doing yet`,
      detail || !picked ? "" : "It hasn't said what it's doing yet.",
    ];
  }
  // A declared request tells the user what to do. Preserve it on the row when
  // no pending input supersedes it; a generic attendance label would lose that cue.
  if (kind === "listening") {
    const awaits = `${agent} awaits — ${detail || "select text to comment"}`;
    return listening
      ? [
          `${agent} listening`,
          `${agent} is listening${detail ? " — " + detail : ""}.`,
          detail ? `It asked: ${detail}.` : "",
        ]
      : [awaits, awaits, ""];
  }
  if (kind === "stalled")
    return [
      shortDate,
      `${dated}${detail ? ": " + detail : ""}. ${saved}`,
      `${detail ? `Last said: ${detail}. ` : ""}${saved}`,
    ];
  // Away is only worth a nudge once input has stalled (`counts.overdue`): the
  // session's next turn picks up whatever it finds, and Leaf messages a harness it
  // can reach once it has seen the turn end.
  return overdue
    ? [
        `Nudge ${agent} in terminal`,
        `${dated}. ${saved} Nothing is answering them, so nudge it in the terminal.`,
        `${dated}. ${saved} Nothing is answering them.`,
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
// this tab's key rather than going away), or with a reading the page could not apply
// (`broken`). The answer is the banner's reading before the queues join it
// (`statusModel`): its `kind`, the dot's `tone`, the row's `summary`, the disclosure's
// `explanation`, what that explanation `adds` to the summary for a seat that shows both
// (the floating panel's menu), and the `actionableWork` whose change is announced.
export function pageStatus(state, { reach = "reached" } = {}) {
  if (reach === "broken")
    return {
      kind: "broken",
      tone: "offline",
      summary: BROKEN_LINE,
      explanation: BROKEN_LINE,
      adds: "",
    };
  if (reach !== "reached")
    return {
      kind: "unreachable",
      tone: "offline",
      ...(reach === "refused"
        ? {
            summary: "Key refused — open Leaf's link in a new tab",
            explanation: KEY_REFUSED_LINE,
            adds: "Keep this tab open so pending changes can send.",
          }
        : {
            summary: "Server offline — reconnecting; keep page open",
            explanation: OFFLINE_LINE,
            adds: "",
          }),
    };
  const { publication } = state;
  if (publication) return { kind: "publication", tone: "", publication };
  const { activity, agent } = state;
  const { kind, detail } = activity;
  const facts = activityFacts(state);
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = "Updates are saved.";
  const checkedIn = facts.silentSince
    ? `${agent} last checked in ${facts.silentSince}`
    : `No check-in from ${agent} is recorded`;
  const ended = `${agent}’s turn ended${facts.silentSince ? " " + facts.silentSince : ""}`;
  const age = kind === "working" && activity.ts ? ago(activity.ts) : "";
  const [summary, text, beyond] = statusWords({
    age,
    agent,
    dated: facts.left ? ended : checkedIn,
    shortDate: facts.left ? ended : checkedIn,
    detail,
    handling: {
      comments: activity.counts.handling_comments,
      answers: activity.counts.handling - activity.counts.handling_comments,
    },
    kind,
    listening: facts.listening,
    overdue: activity.counts.overdue,
    saved,
    work: facts.work,
  });
  let explanation = age ? `${text} (${age})` : text;
  let adds = beyond;
  const append = (words, step = false) => {
    explanation = after(explanation, words, step);
    adds = after(adds, words, step);
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
  if (actionableWork && kind === "working")
    append("It waits in its own session, not on this page.");
  return { kind, tone: facts.tone, summary, explanation, adds, actionableWork };
}

// The page's two queues (`served_state.queues`) are told apart in the banner by where
// they stand. What waits on the user, which `m` walks, is the On me door beside
// Threads (queue-panel.js paints its count), and on a phone's one row it waits in More.
// What waits on the agent, On <agent>, stands beside the status, apart from the sentence,
// as the banner's whole account of the agent's side, with the disclosure naming both
// sides' kinds and each open to-do's title. The agent's count is a page fact, like the
// Threads count, and stands apart from the sentence so the agent's words changing never
// carries it. On one row it ends the status's room, which gives up its words to the
// ellipsis first; where the banner takes two rows, the sentence has the first to itself
// and the count leads the second, ahead of the controls, and a phone's one row leaves it
// to the disclosure (chrome.css). Its box is reserved for the count it usually reaches,
// as the Threads control is for "Threads: 999", and only grows, so a count changing
// moves none of its words.
const QUEUE_WORDS = Object.freeze({
  ask: ["ask", "asks"],
  approval: ["approval", "approvals"],
  resend: ["update to send again", "updates to send again"],
  answer: ["answer", "answers"],
  reply: ["reply", "replies"],
  work: ["update with work started", "updates with work started"],
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
      ? `${words} (${all.map((todo) => todo.title).join(" · ")})`
      : words;
  });
}
function queueWords({ on_user: onUser, on_agent: onAgent }, agent) {
  // The count stands in the banner's row, whose room theme.css states before the name is
  // known, so a long name is cut there; the explanation keeps it whole.
  const short = agent.length > 12 ? `${agent.slice(0, 11)}…` : agent;
  const named = (items, whom) =>
    items.length ? `Waiting on ${whom}: ${queueKinds(items).join(", ")}.` : "";
  return {
    summary: onAgent.length ? `On ${short}: ${onAgent.length}` : "",
    explanation: [named(onUser, "me"), named(onAgent, agent)].filter(Boolean).join(" "),
    // The widest the count usually reaches, under a hundred, which its box holds;
    // a count past it is cut (banner-status-view.js).
    widest: `On ${short}: 99`,
  };
}
const WITHOUT_QUEUES = new Set(["broken", "unreachable", "publication"]);

// What the banner shows for a status (`pageStatus`, or a reading of startup's own),
// beside the page's `queues` (`readQueues`) and the `agent` they wait on: the dot's
// `tone`, the row's `summary` and the agent's count, the disclosure's `explanation` and
// what it `adds` to the summary, and a publication's introduction and links, which
// remain an ordinary reading row rather than children of the status disclosure button.
export function statusModel(status, queues, agent) {
  const { kind, tone, summary, publication = null } = status;
  let { explanation, adds } = status;
  const counted = WITHOUT_QUEUES.has(kind)
    ? { summary: "", explanation: "", widest: "" }
    : queueWords(queues, agent);
  if (counted.explanation) {
    explanation = after(explanation, counted.explanation);
    adds = after(adds, counted.explanation);
  }
  let publicationModel = null;
  if (publication) {
    const [said, installs] = publicationWords(publication);
    const examples = publication.kind === "example" ? "Other examples" : null;
    explanation = said + (examples ? `${examples} ` : "") + installs;
    adds = explanation;
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
    queues: counted.summary,
    queuesWidest: counted.widest,
    explanation,
    adds,
    publication: publicationModel,
  });
}

// ---------- the leaves drawer ----------

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
  // The banner's two silences, dated the same way and worded for a row.
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
