/* What each widget works out of its state and markup for the page to keep (`facts`),
   said again where that state or markup moved without a gesture of this tab's: a
   version arriving, a version's `restated` mark, or another tab's act reaching the
   server's reading. A gesture carries its widget's facts itself
   (records/pending/dispatch.js); this module speaks for every other move.

   Each time this tab adopts a server reading or a document, it compares each value
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
   one word on each set of facts it works out on a version, and says them again only
   once it works out others, on a newer version, once a gesture of its own has spoken
   for the widget, or where the send never reached the server. So two tabs that work
   out different values each say theirs once, rather than overtaking each other without
   end, and a word refused because a newer version landed first is said again on that
   version. */
import { effect, untracked } from "/vendor/signals-core.js";
import { readApplication, readPart } from "../state/semantic-state.js";
import { gestureWidget } from "../state/pending/model.js";
import { registry } from "../state/registry.js";
import { widgetFacts } from "./widget-state.js";
import { addressableAt } from "../records/thread/messages.js";

/** @typedef {{kind: "facts", widget: string, revision: number, through: number, facts: Record<string, unknown>}} FactsEvent */

// A fact's value as the page keeps it, for comparing: an unsaid `answered` is the
// question still asked (`awaits`), and any other unsaid fact is none.
/** @param {Record<string, unknown> | undefined} kept @param {string} name */
const keptValue = (kept, name) =>
  JSON.stringify(
    kept && name in kept ? kept[name] : name === "answered" ? false : null,
  );

/** @param {(event: FactsEvent) => Promise<"accepted" | "refused" | "unreached">} send */
export function reportFacts(send) {
  const reading = readPart((root) => root.authoritative);
  const shown = readPart((root) => root.document);
  // Each widget's facts as this tab last worked them out, with what they rest on and
  // the value the page kept when it last compared them.
  /** @type {Map<string, {folded: unknown, descriptor: unknown, revision: number | null, kept: unknown, facts: Record<string, unknown>}>} */
  const workedOut = new Map();
  // The version and facts this tab worked out of each widget when it last sent a word
  // on it.
  /** @type {Map<string, string>} */
  const sent = new Map();
  /** @type {Set<string>} */
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
      const moved =
        worked?.folded !== folded ||
        worked.descriptor !== descriptor ||
        worked.revision !== revision;
      if (!moved && worked?.kept === kept[id]) continue;
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
      const facts = moved || !worked ? (widgetFacts(id, tag) ?? {}) : worked.facts;
      worked = { folded, descriptor, revision, kept: kept[id], facts };
      workedOut.set(id, worked);
      /** @type {Record<string, unknown>} */
      const changed = {};
      for (const [name, value] of Object.entries(worked.facts))
        if (JSON.stringify(value) !== keptValue(kept[id], name)) changed[name] = value;
      const said = JSON.stringify([revision, worked.facts]);
      if (!Object.keys(changed).length || sent.get(id) === said) continue;
      sent.set(id, said);
      const through = state.browser.basis.through_seq;
      void send({ kind: "facts", widget: id, revision, through, facts: changed }).then(
        (result) => {
          // A word that never reached the page is compared and said again at the
          // next reading, though nothing in it moved.
          if (result !== "unreached" || sent.get(id) !== said) return;
          sent.delete(id);
          workedOut.delete(id);
        },
      );
    }
  };
  effect(() => {
    reading();
    shown();
    untracked(reconcile);
  });
}
