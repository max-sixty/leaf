/* The pages served on this machine now, as the floating panel's All pages lists them
   (`leavesRows`), and its row among the page's controls (page-controls.js), offered
   while another page is served beside this one. */
import { runtime } from "./context.js";
import { pagePresented } from "./page-paint.js";
import { activityFacts, leafRow } from "./activity-words.js";
import { commandSteps } from "./keyboard/control-keys.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "./page-controls.js";

// Something to show: a list of one, the page the user is already on, is not worth a
// door. It reads the state itself, so a paint drawing it follows neighbours as they
// come and go; `others` holds live neighbours only, since a closed one leaves it
// (presence.py).
export const leavesOffered = () =>
  pagePresented() && (runtime.state?.others.length ?? 0) > 0;

// The whole of what the list knows about one page, for its hover. Everything drawn
// on a row is cut to the panel's fixed width — the title ellipsizes, the line
// ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
// session behind the leaf is working. A title is a sentence somebody wrote and two
// pages a week apart share one; the work each came out of is the thing the user
// already holds in their head, so it is worth the room a hover has and a row hasn't.
// Each serving page publishes the same compact account of its own canonical activity.
//
// One tooltip for the row rather than one per part. The innermost title wins where two
// overlap, so a title left on the line would answer the hover most likely to be asking
// this question — a user pointing at the words that ran out of room — with the one
// part of the account they can already read.
const rowAccount = (entry, title, line) =>
  [
    title,
    entry.session_cwd,
    line,
    // The rest of the canonical agent obligations the line summarizes, expanded for the
    // row's hover. A raw cursor count cannot say whether those words are queued,
    // opened in this turn, or still waiting for delivery; the line already says the
    // queued and pending ones.
    activityFacts(entry).owed.join("; "),
  ]
    .filter(Boolean)
    .join("\n");

// The pages the list holds for a state reading: this page's own, then each live
// neighbour. A neighbour's row is its page, keyed by `page_key`, and its link is wherever
// that page is served now. A server restarted on another port keeps the row, and the
// focus on it, where they were; only the destination changes.
const listedPages = (state) =>
  state === null
    ? []
    : [
        { key: "self", href: null, title: document.title, entry: state },
        ...state.others.map((entry) => ({
          key: entry.page_key,
          href: entry.url,
          title: entry.title,
          entry,
        })),
      ];

// Each page a state reading lists, as a row says it: its tone and line in the shape of
// the page's own status, and the whole account its hover gives.
export const leavesRows = (state) =>
  Object.freeze(
    listedPages(state).map(({ key, href, title, entry }) => {
      const { tone, line, parts } = leafRow(entry);
      return Object.freeze({
        key,
        self: key === "self",
        href,
        title,
        tone,
        line,
        parts,
        account: rowAccount(entry, title, line),
      });
    }),
  );

// The list's row among the page's controls counts the pages its press lists, this page
// included, so one neighbour says two.
registerPageControl({
  key: "leaves",
  rank: PAGE_CONTROL_RANK.leaves,
  label: "All pages",
  value: () => String(listedPages(runtime.state).length),
  shortcut: () => commandSteps("navigation.panel.leaves"),
  offered: leavesOffered,
  group: "navigate",
});
