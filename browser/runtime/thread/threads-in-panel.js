/* Whether the user has chosen the floating panel for threads about a passage.

   A thread about a passage opens beside its words, as a card, until the user chooses the
   panel, and then in the panel; thread/destination.js states the rule every route
   follows and why. Only the user's two presses choose: a card's Open in panel chooses
   the panel, and the panel's Show on page chooses cards. A press chooses only on a window
   wide enough for cards (content-layout.js, `windowHoldsRail`): a narrower one puts every
   thread in the panel whatever was chosen, and Show on page there goes to the passage and
   leaves the choice as it stood. Each choice says what now holds in a notice offering the
   press that takes it back, as `o` does (annotation-layer.js). The notice says "Threads
   open in the panel" rather than naming a mode: the glossary keeps "mode" for a state
   that changes what input means, as Design and Draw do, and this one changes only where
   a thread opens, so no chip or indicator stands for it either.

   The choice is this tab's view of the page, as Design mode and the annotation layer
   are, so it lives in the tab store and comes back with a reload, restored before the
   page is presented, and a new tab opens threads beside their passages. A choice isn't
   a place, so going Back or taking an update back leaves it as it stands.

   `chooseThreadsInPanel` is the one writer. Readers ask `threadsInPanel()`; a renderer
   that reads it repaints when it changes. */
import { signal } from "/runtime/framework.js";
import { tabStore } from "../tab-store.js";
import { notice } from "../notifications.js";
import { pressCommand } from "../keyboard/dispatch.js";
import { windowHoldsRail } from "../content-layout.js";
import { THREADS_IN_PANEL_KEY } from "../restore-state.js";

const inPanel = signal(false);

export const threadsInPanel = () => inPanel.value;
// Whether a press choosing `on` would change the choice now, as its preview says.
/** @param {boolean} on */
export const wouldChoose = (on) => on !== inPanel.value && windowHoldsRail();

// What each choice leaves holding, as its notice says it. The press that makes the
// choice previews the same words with "from now on".
export const IN_PANEL = "Threads open in the panel";
export const BESIDE_PASSAGES = "Threads open beside their passages";

/** @param {boolean} on */
function keep(on) {
  inPanel.value = on;
  tabStore.set(THREADS_IN_PANEL_KEY, on ? "panel" : null);
}

// Choose where threads about a passage open, as a press of the user's moves the thread
// they are in there. On a window too narrow for cards the press chooses nothing, and a
// press that repeats the choice in force says nothing. The notice offers `p`, which
// presses the move of the thread the user is at (`thread.move`, landing.js), the other
// way, while this choice stands; the field shows it only while `p` would press it, as
// it shows every press.
/** @param {boolean} on */
export function chooseThreadsInPanel(on) {
  if (!wouldChoose(on)) return;
  keep(on);
  const stands = () => inPanel.value === on;
  notice(on ? IN_PANEL : BESIDE_PASSAGES, {
    press: {
      action: on ? "show-on-page" : "open-in-panel",
      command: "thread.move",
      run: () => pressCommand("thread.move"),
      stands,
    },
    stands,
  });
}

// Read the choice the tab keeps: before presentation, so the page's first opening of
// a thread follows it.
export function restoreThreadsInPanel() {
  const on = tabStore.get(THREADS_IN_PANEL_KEY) === "panel";
  if (on !== inPanel.peek()) keep(on);
}
