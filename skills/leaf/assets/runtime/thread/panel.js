/* The keys the Threads list itself answers. Threads holds no box for starting a page
   thread; that is the banner's Comment on the page (thread/page-comment.js).

   Standing in the panel is where its focus is, not merely that it is open: the Threads
   button is the banner's, so opening by pointer leaves the user outside, and `g T`, `t`,
   Tab or a click on a thread is what puts them in. The thread scope draws one step further
   in, so its rows shadow these. Every page has this scope. */
import { focused, keys } from "../keyboard/scopes.js";
import { pageScope } from "../keyboard/register.js";
import { runtime } from "../context.js";
import { pagePresented } from "../presentation.js";
import { focusDestination } from "../focus.js";
import { rowWalk } from "../walk-position.js";

export function createThreadPanelKeys({
  elements: {
    closeBtn,
    findInput,
    narrowingView,
    threadsBox,
    inPanel: panelFocusIsInside,
  },
  openThreads,
  setPanel,
  panelIsOpen,
  narrowing,
  stepThread,
}) {
  async function mount() {
    closeBtn.onclick = () => setPanel(false);
    await findInput.updateComplete;
    declareFindBoxKeys();
  }

  const inPanel = () => panelFocusIsInside(panelIsOpen);
  const hasThreads = () => openThreads({ visibleOnly: panelIsOpen() }).length > 0;
  // The list's rows are its threads' titles, which the arrows walk as they walk the
  // Questions panel's rows; `t` and `T` still step and open. Only from a title, so the
  // arrows inside an open thread keep scrolling it.
  const titles = () =>
    [...threadsBox.querySelectorAll(".lf-thread-summary")].filter((title) =>
      title.checkVisibility(),
    );
  const onTitle = () => Boolean(focused()?.matches?.(".lf-thread-summary"));
  const titleWalk = rowWalk({
    id: "thread.list",
    noun: "Thread",
    plural: "threads",
    rows: titles,
  }).map((row) => ({ ...row, when: onTitle }));

  const stopPanelScope = pageScope("panel", {
    title: "In the thread panel",
    root: focused,
    at: inPanel,
    rows: [
      ...titleWalk,
      {
        // Search repeat keeps its canonical n/N meaning in the nearest active search.
        // Only a textual query makes this row live; the waiting filter does not claim them.
        id: "thread.find.repeat",
        keys: ["n", "Shift+n"],
        routes: [
          {
            id: "thread.find.next",
            binding: "n",
            title: "Go to the next thread found",
          },
          {
            id: "thread.find.previous",
            binding: "Shift+n",
            title: "Go to the previous thread found",
          },
        ],
        title: "search matches",
        repeat: true,
        when: () => narrowing.threadSearchActive() && hasThreads(),
        run: (binding) => stepThread(binding === "n" ? 1 : -1),
      },
      {
        id: "thread.waiting.toggle",
        // `w` for the words the control says. It is the phrase the page already uses for
        // the same question the queue walk (q/Q) asks of the page, asked here of
        // the thread — so the user learns one idea and reaches it two ways rather
        // than learning "needs you" beside it.
        //
        // The shortcut uses the visible control's toggle, including leaving Resolved
        // when requesting waiting threads and preserving every other restriction.
        keys: ["w"],
        description: () =>
          narrowing.needsYou()
            ? "Clear waiting filter"
            : "Show only the threads waiting on you",
        title: () => (narrowing.needsYou() ? "clear waiting filter" : "waiting on you"),
        control: () => narrowingView.userControl,
        when: () => runtime.statePhase === "ready" && narrowingView.canToggleUser,
        run: () => narrowingView.toggleUser(),
      },
      {
        id: "thread.find",
        // `/` is what every list with a search field takes it with, and the one letter a
        // text box does not shadow: the typing scope claims what types a character, so the
        // press only ever reaches here from the list rather than from a box in it.
        keys: ["/"],
        description: "Find in the threads",
        title: "find",
        control: () => findInput,
        run: () => {
          focusDestination(findInput, "move", { scroll: true });
          findInput.select();
        },
      },
    ],
  });

  // Search shares the text-entry scope's Escape: leave typing and keep the query.
  // Only Enter differs, walking into the first result of the narrowed list.
  function declareFindBoxKeys() {
    keys(
      findInput.input,
      "In the find box",
      [
        {
          id: "thread.find.first",
          keys: ["Enter"],
          description: "Go to the first thread found",
          title: "first found",
          when: hasThreads,
          run: () => stepThread(1),
        },
      ],
      pagePresented,
    );
  }

  return {
    mount,
    dispose: () => stopPanelScope(),
  };
}
