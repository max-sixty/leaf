// Compiled from widget-facts.ts by build/typescript.mjs; edit that file.
/* What each widget works out of its state and markup for the page to keep (`facts`),
   said again where that state or markup moved without a gesture of this tab's: a
   version arriving, a version's `restated` mark, or another tab's act reaching the
   server's reading. A gesture carries its widget's facts itself
   (records/pending/dispatch.js); this module speaks for every other move.

   Each time this tab adopts a server reading or a document, or a gesture of its own
   leaves the ledger, it compares each value
   a widget works out (`widgetFacts`) with the one the page keeps (the shown view's
   `facts`), an unsaid `answered` reading as false, as the server reads it (`awaits`).
   It works a widget's facts out again only where the widget's folded state, its
   descriptor or the version moved since it last did, and compares them again only
   where those or the value the page keeps for it moved. The page's reading shares
   every part a reading leaves alone (base/snapshot.js, `share`), so a reading costs
   each widget that declares facts one identity check, as each widget's selection does
   (`selectWidget`), and the work beyond it follows what moved. Where any value differs, it sends a `facts` event holding those that
   differ through the bookkeeping door (delivery.js), which never wakes the agent, and
   the page's next reading shows them. Every open tab does this after the same reading,
   and the server admits only an event that changes a value it keeps, so tabs that
   agree leave one event in the log. The press's own task never waits on this: a
   change it covers comes from outside the tab, and its result shows with the reading
   that keeps it.

   Only a tab showing the newest version speaks, since a widget's state on an older
   version is that version's, and the newest is the one the page keeps. A widget with
   a gesture of this tab's still on its way is left to that gesture, which carries its
   facts, and a widget whose class isn't defined yet, or whose markup the tab doesn't
   hold, waits for it, since only its class can say, and from that markup. A tab sends
   one word on each set of facts it works out on a version, with the reading it worked
   them out from (`through`), and says them again only once it works out others, on a
   newer version, once a gesture of its own has spoken for the widget, where the
   word never reached the page, or where the page refused it and the widget has since
   moved. The page refuses one worked out from a reading a gesture or another word on
   the widget has since moved past (`stale-facts`), so the tab works the facts out
   again from the reading the refusal brings and says them where they still differ;
   a word refused for good, as one naming an undeclared fact, isn't said again on the
   same state. So two tabs that work out different values each say theirs once,
   rather than overtaking each other without end. */
import { effect, untracked } from "/vendor/signals-core.js";
import { readApplication, readPart } from "../state/semantic-state.js";
import { gestureWidget } from "../state/pending/model.js";
import { registry } from "../state/registry.js";
import { widgetFacts } from "./widget-state.js";
import { addressableAt } from "../records/thread/messages.js";

// What the facts rest on is compared by identity only.

// A fact's value as the page keeps it, for comparing: an unsaid `answered` is the
// question still asked (`awaits`), and any other unsaid fact is none.
const keptValue = (kept, name) =>
  JSON.stringify(
    kept && name in kept ? kept[name] : name === "answered" ? false : null,
  );

export function reportFacts(send) {
  const reading = readPart((root) => root.authoritative);
  const shown = readPart((root) => root.document);
  // A widget left to a gesture of this tab's is looked at again as the gesture leaves
  // the ledger, which may follow the reading that logged it.
  const gestures = readPart((root) => root.unresolved);
  // Each widget's facts as this tab last worked them out, with what they rest on and
  // the value the page kept when it last compared them.
  const workedOut = new Map();
  // The word this tab last sent on each widget: the version and facts it worked out,
  // the record of what the widget then rested on, and whether the page refused it.
  const sent = new Map();
  const undefinedTags = new Set();
  const reconcile = () => {
    const root = readApplication();
    const state = root.authoritative;
    const { document } = root;
    const revision = document.revision;
    if (!state || root.phase !== "ready" || revision !== state.active.revision) return;
    const kept = state.browser.views[String(revision)]?.facts ?? {};
    const busy = new Set(
      root.unresolved.flatMap((entry) =>
        entry.state === "refused" ? [] : [gestureWidget(entry)],
      ),
    );
    for (const [id, folded] of root.effective.widgets) {
      const descriptor = document.descriptors.get(id);
      const tag = descriptor?.tag;
      if (!tag || !registry[tag]?.facts) continue;
      // The gesture carries the widget's word, which the next one this tab works out
      // answers afresh.
      if (busy.has(id)) {
        sent.delete(id);
        continue;
      }
      let worked = workedOut.get(id);
      const last = sent.get(id);
      const moved =
        worked?.folded !== folded ||
        worked.descriptor !== descriptor ||
        worked.revision !== revision;
      // A word the page refused is said again once the widget has moved past what it
      // rested on, as it has where the page refused it as stale (`stale-facts`); one
      // the page refused for good, on a widget that hasn't moved, isn't.
      const retry = Boolean(last?.refused && last.basis !== worked);
      if (!moved && worked?.kept === kept[id] && !retry) continue;
      // A widget with no markup to work from, as one whose message no reading holds,
      // waits until its markup arrives.
      if (!addressableAt(id)) continue;
      if (!customElements.get(tag)) {
        if (!undefinedTags.has(tag)) {
          undefinedTags.add(tag);
          void customElements.whenDefined(tag).then(() => {
            undefinedTags.delete(tag);
            reconcile();
          });
        }
        continue;
      }
      if (moved || !worked || worked.kept !== kept[id]) {
        const facts = moved || !worked ? (widgetFacts(id, tag) ?? {}) : worked.facts;
        worked = { folded, descriptor, revision, kept: kept[id], facts };
        workedOut.set(id, worked);
      }
      const changed = {};
      for (const [name, value] of Object.entries(worked.facts))
        if (JSON.stringify(value) !== keptValue(kept[id], name)) changed[name] = value;
      const said = JSON.stringify([revision, worked.facts]);
      if (!Object.keys(changed).length) continue;
      if (last?.said === said && (!last.refused || last.basis === worked)) continue;
      const entry = { said, basis: worked, refused: false };
      sent.set(id, entry);
      const through = state.browser.basis.through_seq;
      void send({ kind: "facts", widget: id, revision, through, facts: changed }).then(
        (result) => {
          if (result === "accepted" || sent.get(id) !== entry) return;
          if (result === "unreached") {
            // A word that never reached the page is compared and said again at the
            // next reading, though nothing in the widget moved.
            sent.delete(id);
            workedOut.delete(id);
            return;
          }
          // The refusal's own reading may already have moved the widget.
          entry.refused = true;
          reconcile();
        },
      );
    }
  };
  effect(() => {
    reading();
    shown();
    gestures();
    untracked(reconcile);
  });
}
