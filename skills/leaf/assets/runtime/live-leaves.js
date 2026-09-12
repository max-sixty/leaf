/* This module derives the machine's immutable Leaves presentation and owns its walk. */
import { ago, clocked } from "./presence.js";
import { pagePresented } from "./presentation.js";
import { liveLeavesList, trayIsOpen, othersPanel } from "./trays.js";
import { keys, paintKeys } from "./keyboard/scopes.js";
import { walkRows } from "./keyboard/bindings.js";
import { toneFor } from "./banner.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";

let others = [];
let rows = Object.freeze([]);

// The tray's one offer: something to show, or the tray already standing — the key that
// opened it must still close it, and its button must still be pressable. The button's
// visibility and the key both ask the tray's own predicate, so the two surfaces cannot
// disagree about whether there is a tray to open. A leaves tray of one — the page the
// reader is already on — is not worth a control.
export const leavesOffered = () =>
  pagePresented() && (others.length > 0 || trayIsOpen("leaves"));
// The control counts the rows its press opens, including this page's own marked row.
// One neighbour therefore says two, rather than naming a different collection from
// the tray. The list and its control receive this same frozen value.
const presentationModel = () =>
  Object.freeze({
    offered: leavesOffered(),
    label: `All leaves (${rows.length})`,
    rows,
  });
export const presentLeaves = () => liveLeavesList.present(presentationModel());

// The tray's own scope. The walk is the tray's rather than the page's, because ArrowUp
// and ArrowDown anywhere else are the page's own scroll and stay so; Enter is the
// browser's, a row being a link, and the row says so with no `run` to give. The reader
// arrives here by key — `g L` lands focus on the first neighbour — so the scope names
// what activating does rather than leaving it to the platform's own contract.
export const othersLinks = () => [...othersPanel.querySelectorAll("a.lf-others-row")];
// Declared once the tray is in the document (leaf.js): the tray is trays.js's, an
// owner that imports this module back.
export function declareLeavesKeys() {
  keys(
    othersPanel,
    "In the leaves tray",
    [
      {
        id: "leaf.walk",
        keys: ["ArrowUp", "ArrowDown"],
        routes: [
          { id: "leaf.previous", binding: "ArrowUp", does: "Previous leaf" },
          { id: "leaf.next", binding: "ArrowDown", does: "Next leaf" },
        ],
        does: "Walk the leaves",
        line: "walk the leaves",
        repeat: true,
        run: (binding) => {
          walkRows(othersLinks(), binding === "ArrowDown" ? 1 : -1);
          beginWalk("leaf", "Leaf", () =>
            listWalkPosition(othersLinks(), document.activeElement),
          );
        },
      },
    ],
    () => othersLinks().length > 0,
  );
}

// A row's whole account of a page: the dot's tone and one line of words, from the
// same judgment the banner's sentences come from — the judgment is shared, the
// wording is the seat's.
function rowPresence(entry) {
  const { kind, quiet, dropped, detail, ts, counts } = entry.activity;
  // The same join for both kinds that have words of their own. The reader opens this
  // panel to find which page needs them, so a bare `Awaits` beside a neighbour's
  // `Working — recording the demo` said least about the one row they are here to act
  // on: three pages waiting rendered as three identical rows, and which to go to
  // first is the whole question the panel was opened to answer.
  const stated = (word) => word + (detail ? " — " + detail : "");
  // The banner's two silences, dated the same way and worded for a row.
  const silence = dropped ? `Left (${ago(entry.turn_closed)})` : `Quiet (${ago(ts)})`;
  const primary =
    kind === "working"
      ? stated("Working")
      : kind === "handling"
        ? "Handling updates"
        : kind === "queued"
          ? "Queued"
          : kind === "picked_up"
            ? "Picked up; turn ended"
            : kind === "listening"
              ? counts.pending
                ? stated("Listening")
                : stated("Awaits")
              : kind === "stalled"
                ? stated(silence)
                : kind === "away"
                  ? quiet
                    ? silence
                    : "Away"
                  : kind === "unheld"
                    ? "Unheld"
                    : kind === "unattended"
                      ? "Unattended"
                      : "Closed";
  const pending = counts.pending
    ? `${counts.pending} update${counts.pending === 1 ? "" : "s"} waiting`
    : null;
  const line = pending ? `${primary} · ${pending}` : primary;
  return { tone: toneFor(kind), line };
}

// The whole of what the tray knows about one page, for its hover. Everything drawn
// on a row is cut to the panel's fixed width — the title ellipsizes, the line
// ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
// session behind the leaf is working. A title is a sentence somebody wrote and two
// pages a week apart share one; the work each came out of is the thing the reader
// already holds in their head, so it is worth the room a hover has and a row hasn't.
//
// One tooltip for the row rather than one per part. The innermost title wins where two
// overlap, so a title left on the line would answer the hover most likely to be asking
// this question — a reader pointing at the words that ran out of room — with the one
// part of the account they can already read.
const activityAccount = ({ counts }) => {
  const noun = (count) => `${count} update${count === 1 ? "" : "s"}`;
  const parts = [];
  if (counts.active) parts.push(`${noun(counts.active)} active`);
  if (counts.handling) parts.push(`${noun(counts.handling)} being handled`);
  if (counts.queued) parts.push(`${noun(counts.queued)} queued`);
  if (counts.picked_up) parts.push(`${noun(counts.picked_up)} picked up; turn ended`);
  if (counts.pending) parts.push(`${noun(counts.pending)} waiting`);
  return parts.length ? parts.join("; ") : null;
};

const rowAccount = (entry, title, line) =>
  [
    title,
    entry.session_cwd,
    line,
    // The same canonical agent obligations the line summarizes, expanded for the
    // row's hover. A raw cursor count cannot say whether those words are queued,
    // opened in this turn, or still waiting for delivery.
    activityAccount(entry.activity),
  ]
    .filter(Boolean)
    .join("\n");

function renderOthersNow(state) {
  const offeredBefore = leavesOffered();
  // Null is the explicit pre-read state. It has no self presence to draw, and recovery
  // from a refused first reading must remove every row that candidate introduced.
  // A closed leaf is not one of the machine's live pages and drops out of the tray on
  // the poll that says
  // so: its server stays up so the page stays readable — a standing one for good —
  // so nothing else would ever take the row off, and a count the reader glances at
  // to find who needs them would silently become a tally of everything that has run
  // here. Judged by the same canonical `activity` the rows read, never by a second
  // reading of the status the server ships. This page's own row is not in the list and so is
  // never dropped: a reader looking at a closed page is still looking at it.
  others =
    state === null
      ? []
      : state.others.filter((entry) => entry.activity.kind !== "closed");
  const wanted = state
    ? [
        { key: "self", title: document.title, entry: state },
        ...others.map((entry) => ({ key: entry.url, title: entry.title, entry })),
      ]
    : [];
  rows = Object.freeze(
    wanted.map(({ key, title, entry }) => {
      const { tone, line } = rowPresence(entry);
      return Object.freeze({
        key,
        self: key === "self",
        href: key === "self" ? null : key,
        title,
        tone,
        line,
        account: rowAccount(entry, title, line),
      });
    }),
  );
  if (offeredBefore !== leavesOffered()) paintKeys();
  return presentLeaves();
}

export const renderOthers = clocked(document.body, renderOthersNow);
