/* The pages served on this machine now, as the floating panel's All pages lists them
   (`leavesRows`), and its row among the page's controls (base/page-controls.js), offered
   while another page is served beside this one.

   The list is the machine's, not the page's, so it travels apart from the page's
   state: `/api/pages` answers it, and nothing this page reads waits for it or agrees
   with it. Each news look names the list's reading beside the page's own
   (state-feed.js), and the list is asked for again only when that names another
   reading than the one it was last asked for (`hearPages`). So another page's
   change re-reads this list alone, and never this page's state. */
import { signal } from "/vendor/signals-core.js";
import { pageUrl, runtime } from "../state/context.js";
import { authoredTitle } from "../base/tab-title.js";
import { pagePresented } from "../base/page-paint.js";
import { activityFacts, leafRow } from "../state/activity-words.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "../base/page-controls.js";
import type {
  ServedLivePage,
  ServedPagesAnswer,
  ServedState,
} from "../../types/contract.js";

type LivePage = ServedLivePage;

const NONE: readonly LivePage[] = Object.freeze([]);
// The live neighbours, in title order; a closed one is not among them (presence.py).
const neighbours = signal(NONE);
// The list's reading it was last asked for, null for none live, or undefined before
// the first look, after a look that heard nothing and after a read that failed, so the
// next look asks again.
let asked: string | null | undefined;
// The read of `/api/pages` still out, if one is.
let reading: AbortController | null = null;

/** Take in what a news look heard of the list: the reading it names, null for none
 *     live, or undefined for a look that heard nothing. Another reading than the one last
 *     asked for ends the read still out, whose answer could only be older, and none live
 *     empties the list without a read; a new reading is read at once. A look that heard
 *     nothing ends the read too, as the feed ends its state reads then (state-feed.js,
 *     `abandonReads`), and leaves the list as it stands for the next look to name. */
export function hearPages(heard: string | null | undefined) {
  if (heard === asked) return;
  asked = heard;
  reading?.abort();
  reading = null;
  if (heard === null) neighbours.value = NONE;
  else if (heard !== undefined) void readPages();
}

async function readPages() {
  const read = new AbortController();
  reading = read;
  try {
    const response = await fetch(pageUrl("api/pages"), { signal: read.signal });
    if (!response.ok) throw new Error(`pages returned HTTP ${response.status}`);
    const pages: ServedPagesAnswer = await response.json();
    if (reading === read) neighbours.value = Object.freeze(pages);
  } catch {
    // A read ended for a newer reading leaves `asked` naming that one.
    if (reading === read) asked = undefined;
  } finally {
    if (reading === read) reading = null;
  }
}

// Something to show: a list of one, the page the user is already on, is not worth a
// door. It reads the list itself, so a paint drawing it follows neighbours as they come
// and go.
export const leavesOffered = () => pagePresented() && neighbours.value.length > 0;

// The whole of what the list knows about one page, for its hover. Everything drawn
// on a row is cut to the panel's fixed width — the title ellipsizes, the line
// ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
// session behind the leaf is working. A title is a sentence somebody wrote and two
// pages a week apart share one; the work each came out of is the thing the user
// already holds in their head, so it is worth the room a hover has and a row hasn't.
// Each serving page publishes the same compact account of its own canonical activity.
// A pointer that can't hover has no hover to give that room, so a row there draws its
// words whole and `rest` under them, what the account holds that the row leaves out
// (floating-panel.css).
//
// One tooltip for the row rather than one per part. The innermost title wins where two
// overlap, so a title left on the line would answer the hover most likely to be asking
// this question — a user pointing at the words that ran out of room — with the one
// part of the account they can already read.
const onLines = (facts: readonly (string | null)[]) => facts.filter(Boolean).join("\n");

// The pages the list holds: this page's own, by its own state reading, then each live
// neighbour. A neighbour's row is its page, keyed by `page_key`, and its link is wherever
// that page is served now. A server restarted on another port keeps the row, and the
// focus on it, where they were; only the destination changes.
const listedPages = (state: ServedState | null) =>
  state === null
    ? []
    : [
        { key: "self", href: null, title: authoredTitle(), entry: state },
        ...neighbours.value.map((entry) => ({
          key: entry.page_key,
          href: entry.url,
          title: entry.title,
          entry,
        })),
      ];

// Each page the list holds, as a row says it: its tone and line in the shape of the
// page's own status, and the whole account its hover gives.
export const leavesRows = (state: ServedState | null) =>
  Object.freeze(
    listedPages(state).map(({ key, href, title, entry }) => {
      const { tone, line, parts } = leafRow(entry);
      // The rest of the canonical agent obligations the line summarizes, expanded for
      // the row's hover. A raw cursor count cannot say whether those words are queued,
      // opened in this turn, or still waiting for delivery; the line already says the
      // queued and pending ones.
      const owed = activityFacts(entry).owed.join("; ");
      return Object.freeze({
        key,
        self: key === "self",
        href,
        title,
        tone,
        line,
        parts,
        account: onLines([title, entry.session_cwd, line, owed]),
        rest: onLines([entry.session_cwd, owed]),
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
  command: "navigation.panel.leaves",
  offered: leavesOffered,
  group: "navigate",
});
