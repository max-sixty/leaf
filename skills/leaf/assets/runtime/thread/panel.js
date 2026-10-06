/* The thread panel's general composer, and the keys the Threads list itself answers.

   Standing in the panel is where its focus is, not merely that it is open: the Threads
   button is the banner's, so opening by pointer leaves the user outside, and `g T`, `t`,
   Tab or a click on a thread is what puts them in. The thread scope draws one step further
   in, so its rows shadow these. Every page has this scope: the general box stands and
   takes words from the first paint — the offline banner says a comment will not send, not
   that there is nowhere to write it. A drawing belongs to an element's comment, never to
   this box (composing/drawing.js). */
import { loadDraft, mirrorDraft, saveDraft, sendMessage } from "../drafts.js";
import { focused, keys } from "../keyboard/scopes.js";
import { pageScope } from "../keyboard/register.js";
import { runtime } from "../context.js";
import { pagePresented } from "../presentation.js";

export function createPanelComposer({
  elements: {
    closeBtn,
    findInput,
    generalInput,
    generalSend,
    narrowingView,
    inPanel: panelFocusIsInside,
  },
  openThreads,
  designModeActive,
  wireInput,
  createPageComment,
  showThread,
  setPanel,
  panelIsOpen,
  narrowing,
  stepThread,
  firstUnread,
  unreadCount,
}) {
  let sync = () => {};
  let stopMirroringDraft = () => {};
  const generalHint = () =>
    designModeActive() ? "Comment on the design" : "Comment on the page";
  const syncGeneral = () => sync();

  async function mount() {
    closeBtn.onclick = () => setPanel(false);
    generalInput.value = loadDraft("general") ?? "";
    sync = wireInput(generalInput, {
      hint: generalHint,
      accessibleName: generalHint,
      sends: "send",
      sendBtn: generalSend,
      save: (text) => saveDraft("general", text),
      send: async (_text, raw, owns) => {
        const sent = await sendMessage("general", owns, (attempt) => {
          const event = { attempt, text: raw };
          if (designModeActive()) event.about = "design";
          return createPageComment(event);
        });
        if (!sent) return;
        // The message renderer cues the send; revealing its thread only lands it.
        showThread(sent.id, { focus: false, flash: false });
      },
    });
    sync();
    stopMirroringDraft = mirrorDraft(generalInput, sync, "general", {
      resume: () => ({
        where: generalInput,
        input: () => generalInput,
        open: () => setPanel(true),
      }),
    });
    await findInput.updateComplete;
    declareFindBoxKeys();
  }

  const inPanel = () => panelFocusIsInside(panelIsOpen);
  const hasThreads = () => openThreads({ visibleOnly: panelIsOpen() }).length > 0;

  const stopPanelScope = pageScope("panel", {
    title: "In the thread panel",
    root: focused,
    at: inPanel,
    rows: [
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
        description: "Next / previous thread found",
        title: "search matches",
        repeat: true,
        when: () => narrowing.threadSearchActive() && hasThreads(),
        run: (binding) => stepThread(binding === "n" ? 1 : -1),
      },
      {
        id: "thread.waiting.toggle",
        // `w` for the words the control says. It is the phrase the page already uses for
        // the same question the queue walk (a/A) asks of the page, asked here of
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
        id: "thread.unread.first",
        keys: ["u"],
        description: "Go to the first unread message",
        title: "first unread",
        when: () => unreadCount() > 0,
        run: firstUnread,
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
          findInput.focus();
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
    syncGeneral,
    mount,
    dispose: () => {
      stopPanelScope();
      stopMirroringDraft();
    },
  };
}
