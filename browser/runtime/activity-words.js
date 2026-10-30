/* What each seat says about a page's served activity: the page's status sentence and
   what its explanation adds, and a row of All pages. Both are worded here from the one
   `activity` reading the server sends, and from the page's queues, so a fact the seats
   share changes in one place. Nothing here reads or writes the document; page-status.js
   and live-leaves.js read what these return, the floating panel draws it, and
   `tests/runtime/activity-words.test.mjs` holds each sentence. */
import { ago } from "./presence.js";
import { itemNoun } from "./queues.js";

/** @type {Record<import("../types/contract.js").ServedActivity["kind"], string>} */
const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  closed: "",
};
// Every step the server may report (`ServedWorkKind`) has its words here, in Leaf's
// voice, since the harness observed the step and the agent said none of them
// (glossary.md, "Reader-facing words").
/** @type {Record<import("../types/contract.js").ServedWorkKind, string>} */
const WORK_WORDS = {
  working: "Working",
  thinking: "Thinking",
  tool: "Using a tool",
  awaiting_approval: "Approval needed",
  awaiting_input: "Input needed",
  awaiting_user: "Question waiting",
  replying: "Writing a reply",
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
// - `work` names the step, and where a dialog in the agent's own window holds it
//   (`awaiting`), that the user answers it in the terminal, since nothing on the page
//   does.
// - `waiting` phrases the queued and pending updates, in that order, and `owed` the
//   other counts, for a seat with room to say them beside `waiting`.
export function activityFacts({ activity }) {
  const { counts } = activity;
  return Object.freeze({
    tone: TONE[activity.kind],
    work:
      WORK_WORDS[activity.observed_kind ?? "working"] +
      (activity.awaiting ? " in the terminal" : ""),
    left: Boolean(activity.dropped),
    silentSince: ago(activity.ts),
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

// Status sentences for an unreachable server or a state the page cannot apply, in
// Leaf's voice like every sentence the agent didn't write (glossary.md,
// "Reader-facing words").
const OFFLINE_LINE =
  "Lost the connection — reconnecting. Keep this page open so changes made here go through.";
// A refused key leaves the page as cut off as a dead server, but the server is up and
// only the user can end it. Opening the link in another tab sets the key this tab's
// next request carries, so its pending changes send without a reload.
const KEY_REFUSED_LINE =
  "This tab lost access. Open the page's link again in a new tab, and keep this one open so changes made here go through.";
const BROKEN_LINE = "Couldn't show the latest — reload";
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

// Rendered strings derive from structured parts, so an authored detail keeps its
// exact source without recovering its position from a combined status sentence. A
// part with a `source`, or in the agent's `voice`, such as a to-do's title, is the
// agent's own words; every other part is Leaf's, which the seats set apart in italic
// (glossary.md, "Reader-facing words").
const textParts = (words) =>
  (Array.isArray(words) ? words : [words])
    .filter(Boolean)
    .map((part) => (typeof part === "string" ? { text: part } : part));
const textOf = (parts) => parts.map((part) => part.text).join("");
const appendWords = (parts, words, step = false) => {
  const head = textOf(parts);
  parts.push({ text: after(head, words, step).slice(head.length) });
};
// Parts following a status sentence as `after` joins words, each keeping its voice.
const appendParts = (parts, more) => {
  const head = textOf(parts);
  const joined = textOf(more);
  const lead = after(head, joined).slice(head.length, -joined.length);
  parts.push(...(lead ? [{ text: lead }] : []), ...more);
};

// Both levels of wording follow server-owned activity. Short summaries retain the
// actionable distinction: working, listening, away, or nobody holding the page. How many
// updates are waiting or saved is the disclosure's; the row counts what waits on each
// side instead (`queueWords`). The third wording is what the sentence says that the
// summary does not, for a seat that shows both (`pageStatus`, `adds`), and the fourth
// whether the words ask the user to act (`pageStatus`, `asks`), which only a wording
// that asks sets. Only the agent's `detail` is in its voice; the rest is Leaf's.
function statusWords({
  dated,
  detail,
  detailSource,
  invite,
  kind,
  overdue,
  saved,
  waits,
  work,
}) {
  if (kind === "closed") return ["Done with this page", "Done with this page.", ""];
  if (kind === "unheld") {
    const meanwhile = `${saved} They're picked up next time.`;
    return [
      "Not on this page right now",
      `Not on this page right now. ${meanwhile}`,
      meanwhile,
    ];
  }
  // While it works, its own sentence is the reason to look at the row, so the row keeps
  // it and the ellipsis fits it to the room the controls leave. The row carries no date:
  // the agent keeps the sentence current, reminded by its hooks when it goes unrenewed
  // (`hook_transport.status_reminders`), and a sentence the server stops believing
  // becomes a stall, which dates itself. The disclosure says how long ago it was
  // written. A row dated by the sentence's age, rejected on 27 October 2026, read
  // "3m ago" for most of every turn, while the session was visibly moving.
  //
  // Until the agent writes that sentence the row says nothing, and the leaf's tone says
  // it works: the words beside the leaf are the agent's to choose (the user's choice,
  // 28 October 2026). Rejected: Leaf's guess at them ("Got your comment", "Working on
  // it"), which put Leaf's words in the agent's mouth; the update's own Got it label
  // already says it arrived. The step the harness observed stays in the disclosure.
  if (kind === "working") {
    const sentence = detail ? [{ text: detail, source: detailSource }] : [];
    // A wait the user answers in the terminal leads, ahead of the sentence it
    // interrupts, since it is the one thing on the line the user must act on.
    if (waits) {
      const said = [work, ...(detail ? [" — ", ...sentence] : [])];
      return [said, said, ""];
    }
    return detail ? [sentence, sentence, ""] : ["", work, work];
  }
  // The stock words say where a comment starts; they report and ask nothing. An
  // update still on its way says so on its own label and in the explanation's count,
  // so the line keeps the invitation (the user's choice, 26 October 2026, over a
  // separate "listening" while one was).
  if (kind === "listening") return [invite, invite, ""];
  if (kind === "stalled")
    return [
      dated,
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
        "Not answering — nudge the terminal",
        `${dated}. ${saved} Nothing is answering them, so nudge the terminal.`,
        `${dated}. ${saved} Nothing is answering them.`,
        true,
      ]
    : [
        "Away",
        `Away right now. ${saved} They're picked up next turn.`,
        `${saved} They're picked up next turn.`,
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
// can draw louder than a status that only reports, its `voice`, `agent` where the
// row holds the agent's own words and `leaf` where all of it is Leaf's, and the
// `actionableWork` whose
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
      voice: "leaf",
      explanation: BROKEN_LINE,
      adds: "",
      asks: true,
    };
  if (reach === "refused")
    return {
      kind: "refused",
      tone: "blocked",
      summary: "This tab lost access — open the link again",
      voice: "leaf",
      explanation: KEY_REFUSED_LINE,
      adds: "Keep this tab open so changes made here go through.",
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
      summary: "Hit a problem — trying again",
      voice: "leaf",
      explanation: `Hit a problem: ${said}. Trying again.`,
      adds: `${said}. Trying again.`,
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
      summary: "Lost the connection — reconnecting",
      voice: "leaf",
      explanation: OFFLINE_LINE,
      adds: "",
    };
  const { activity, publication = null } = state;
  // On Leaf's website any comment starts the agent (`leaf_website`), so whenever it
  // isn't working it listens: no session holds a copy until its first comment, and one
  // that has gone quiet since starts again at the next. Its work reads as on any page,
  // and the introduction and its links join the explanation (`statusModel`).
  const onCall = Boolean(publication) && activity.kind !== "working";
  const kind = onCall ? "listening" : activity.kind;
  // The line of work a quiet copy's last session left no longer stands.
  const detail = onCall ? "" : activity.detail;
  const facts = activityFacts(state);
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = "Updates are saved.";
  const checkedIn = facts.silentSince
    ? `Last checked in ${facts.silentSince}`
    : "Haven't checked in yet";
  const ended = `Stopped${facts.silentSince ? " " + facts.silentSince : ""}`;
  const age = kind === "working" && activity.ts ? ago(activity.ts) : "";
  const [summaryWords, explanationWords, beyond, asked = false] = statusWords({
    dated: facts.left ? ended : checkedIn,
    detail,
    detailSource: activity.detail_source,
    invite: publication
      ? "Ready — comment to revise this copy"
      : "Ready — select text to comment",
    kind,
    overdue: activity.counts.overdue,
    saved,
    waits: Boolean(activity.awaiting),
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
  // An approval or a question the agent's own window holds is answered there, which
  // the work's words say (`activityFacts`), and the page is the one place the user may
  // be looking instead, so the status asks.
  const waitsThere = Boolean(actionableWork) && kind === "working";
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
    voice: summaryParts.some((part) => part.source) ? "agent" : "leaf",
    actionableWork,
    publication,
  };
}

// The page's two queues (`served_state.queues`), as the status's explanation names
// them: each side's kinds and each open to-do's title. The floating panel counts what
// waits on the user on its On me mark. What a widget registered is counted as what is
// left to answer, since only a row or the walk names it by its widget (`obligationWord`).
// A question asked in a message is counted with them, so kinds that share words share
// one count.
const TO_ANSWER = Object.freeze(["to answer", "to answer"]);
const TODO = Object.freeze(["to-do", "to-dos"]);
const QUEUE_WORDS = Object.freeze({
  widget: TO_ANSWER,
  message: TO_ANSWER,
  resend: ["update to send again", "updates to send again"],
  answer: ["answer", "answers"],
  reply: ["reply", "replies"],
  todo: TODO,
});
function queueKinds(items) {
  const byWords = new Map();
  for (const item of items) {
    const nouns = QUEUE_WORDS[itemNoun(item)];
    byWords.set(nouns, [...(byWords.get(nouns) ?? []), item]);
  }
  return [...byWords].map(([nouns, all]) => {
    const words = { text: `${all.length} ${nouns[all.length === 1 ? 0 : 1]}` };
    if (nouns !== TODO) return [words];
    // A to-do outlasts the turns and the thread that opened it (`todos.py`), so each
    // open one is named, including one on a thread the user has resolved, in the
    // words the agent gave it.
    const titles = all.flatMap((row, index) => [
      ...(index ? [{ text: " · " }] : []),
      { text: row.obligation?.prompt.text ?? row.todo.title, voice: "agent" },
    ]);
    return [{ ...words, text: `${words.text} (` }, ...titles, { text: ")" }];
  });
}
function queueWords({ on_user: onUser, on_agent: onAgent }, agent) {
  const named = (items, whom) =>
    items.length
      ? [
          { text: `Waiting on ${whom}: ` },
          ...queueKinds(items).flatMap((kind, index) => [
            ...(index ? [{ text: ", " }] : []),
            ...kind,
          ]),
          { text: "." },
        ]
      : [];
  const onMe = named(onUser, "me");
  const onAgentParts = named(onAgent, agent);
  return [
    ...onMe,
    ...(onMe.length && onAgentParts.length ? [{ text: " " }] : []),
    ...onAgentParts,
  ];
}
const WITHOUT_QUEUES = new Set(["broken", "refused", "faulted", "unreachable"]);

// What the chrome shows for a status (`pageStatus`, or a reading of startup's own),
// beside the page's `queues` (`readQueues`) and the `agent` they wait on: the leaf's
// `tone`, the row's `summary`, the `explanation` and
// what it `adds` to the summary, whether the status `asks` the user to act, and a
// publication's introduction and links, with which the explanation ends.
export function statusModel(status, queues, agent) {
  const {
    kind,
    tone,
    summary,
    asks = false,
    voice = "agent",
    publication = null,
  } = status;
  let { explanation, adds } = status;
  const explanationParts = [...(status.explanationParts ?? textParts(explanation))];
  const addsParts = [...(status.addsParts ?? textParts(adds))];
  const counted = WITHOUT_QUEUES.has(kind) ? [] : queueWords(queues, agent);
  if (counted.length) {
    appendParts(explanationParts, counted);
    appendParts(addsParts, counted);
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
    voice,
    explanation,
    adds,
    publication: publicationModel,
  });
}

// ---------- a row of All pages ----------

// A row's whole account of a page: the dot's tone and one line of words, from an
// canonical activity computed by each serving page, as its `line` and as `parts`,
// each in the `voice` of whoever said it. The wording is the seat's.
export function leafRow(entry) {
  const { kind, counts, detail } = entry.activity;
  const facts = activityFacts(entry);
  // The user opens this panel to find which page needs them, so a row says what the
  // agent last said, in its own words (`recording the demo`): three pages waiting
  // rendered as three identical rows said least about the one row they are here to
  // act on. A working page whose agent has said nothing yet shows its tone alone, as
  // the status does.
  const own = detail ? [{ text: detail, voice: "agent" }] : [];
  const leaf = (text) => ({ text, voice: "leaf" });
  const stated = (word) => [leaf(word), ...(detail ? [leaf(" — "), ...own] : [])];
  // The status's two silences in the status's own words.
  const since = facts.silentSince ? ` ${facts.silentSince}` : "";
  const silence = facts.left
    ? `Stopped${since}`
    : since
      ? `Last checked in${since}`
      : "Haven't checked in yet";
  // A wait the user answers in the terminal leads, as the status's does, so a blocked
  // page doesn't read as a busy one.
  const primary =
    kind === "working"
      ? entry.activity.awaiting
        ? stated(facts.work)
        : own
      : kind === "listening"
        ? [leaf("Ready")]
        : kind === "stalled"
          ? stated(silence)
          : kind === "away"
            ? [leaf(counts.overdue ? silence : "Away")]
            : [
                leaf(
                  kind === "unheld"
                    ? "Not on this page right now"
                    : "Done with this page",
                ),
              ];
  const waiting = facts.waiting.join(" · ");
  const parts = waiting
    ? [...primary, leaf(primary.length ? ` · ${waiting}` : waiting)]
    : primary;
  return {
    tone: facts.tone,
    line: parts.map((part) => part.text).join(""),
    parts: Object.freeze(parts),
  };
}
