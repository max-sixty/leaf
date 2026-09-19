/* The thread panel's general composer and its one draft/drawing authority, and the keys
   the Threads list itself answers.

   Standing in the panel is where its focus is, not merely that it is open: the Threads
   button is the banner's, so opening by pointer leaves the reader outside, and `g T`, `t`,
   Tab or a click on a thread is what puts them in. The thread scope draws one step further
   in, so its rows shadow these. Every page has this scope: the general box stands and
   takes words from the first paint — the offline banner says a comment will not send, not
   that there is nowhere to write it. */
import { landTyping, mayLandTyping } from "../composing/capture.js";
import { validDrawing } from "../composing/drawing-record.js";
import {
  loadDraft,
  loadDraftPayload,
  mirrorDraft,
  saveDraft,
  sendMessage,
  watchDraft,
} from "../drafts.js";
import {
  closeBtn,
  findInput,
  generalInput,
  generalRow,
  generalSend,
  inPanel as panelFocusIsInside,
  narrowingView,
  threadsBox,
} from "./panel-elements.js";
import { documentFocused, focused, keys } from "../keyboard/scopes.js";
import { pageScope } from "../keyboard/register.js";
import { narrowed, needsYou, threadSearchActive } from "./narrowing.js";
import { awaitsReader } from "./model.js";
import { threadList } from "./state.js";
import { openThreads } from "./thread-list.js";
import { standingConversation } from "./landing.js";
import { runtime } from "../context.js";
import { pagePresented } from "../presentation.js";

const drawingIn = (payload) =>
  validDrawing(payload?.drawing) ? payload.drawing : null;

export function createPanelComposer({
  designModeActive,
  wireInput,
  createPageComment,
  showThread,
  setPanel,
  panelIsOpen,
  stepThread,
  widen,
  fabAnchorAt,
  paintDrawings,
}) {
  let sync = () => {};
  let generalDrawing = drawingIn(loadDraftPayload("general"));
  const generalHint = () =>
    designModeActive() && !generalDrawing
      ? "Comment on the design"
      : "Comment on the page";
  const syncGeneral = () => sync();
  const pageComposerDrawing = () => generalDrawing;

  function saveGeneralDraft(text = sync.value()) {
    return saveDraft(
      "general",
      text,
      generalDrawing ? { drawing: generalDrawing } : undefined,
    );
  }

  function openPageDrawing(drawing) {
    generalDrawing = drawing;
    saveGeneralDraft();
    setPanel(true);
    generalInput.focus({ preventScroll: true });
    sync();
    paintDrawings();
  }

  function mount() {
    closeBtn.onclick = () => setPanel(false);
    generalInput.value = loadDraft("general") ?? "";
    sync = wireInput(generalInput, {
      hint: generalHint,
      accessibleName: generalHint,
      sends: "send",
      sendBtn: generalSend,
      hasContent: (raw) => Boolean(raw || generalDrawing),
      save: saveGeneralDraft,
      send: async (_text, raw, owns) => {
        const sent = await sendMessage("general", owns, (attempt, payload) => {
          const event = { attempt };
          if (raw) event.text = raw;
          const drawing = drawingIn(payload);
          if (designModeActive() && !drawing) event.about = "design";
          if (drawing) event.drawing = drawing;
          return createPageComment(event);
        });
        if (!sent) return;
        const shouldLand = mayLandTyping(generalInput);
        showThread(sent.id, { focus: false });
        if (shouldLand) landTyping(generalInput);
      },
    });
    sync();
    mirrorDraft(generalInput, sync, "general");
    watchDraft("general", (_value, payload) => {
      generalDrawing = drawingIn(payload);
      sync();
      paintDrawings();
    });
    declareFindBoxKeys();
  }

  const inPanel = () => panelFocusIsInside(panelIsOpen);
  const hasThreads = () => openThreads({ visibleOnly: panelIsOpen() }).length > 0;

  // The panel's local route to the contextual Comment capability. From the Threads list
  // this puts the reader in the page-comment box; page `c` reaches the same box directly,
  // and this is the same contextual intent from a surface whose local `w` and `/` commands
  // remain useful until the reader asks to write.
  const PANEL_SAY = {
    id: "comment.write",
    keys: ["c"],
    does: () => generalHint(),
    line: "comment",
    // Dead while the reader has a passage or an item in hand. `t` is a page key that lands
    // focus in the panel, so a reader who selected a paragraph and then walked the threads
    // is standing in this scope with their selection still live — and this row, being the
    // innermost, would have taken the press and spent it on the general box, collapsing
    // the selection as the box took focus. A gesture the reader made outranks the room
    // they happen to be standing in, so the row stands down and the page's own c answers,
    // on the passage, saying so on the shortcut bar first.
    //
    // Dead inside a conversation for the same reason read the other way. This scope is
    // live wherever focus is in the panel, a card the reader has walked to included, and
    // that card's own reply box is a nearer answer to "comment" than the general box is —
    // the one `Enter` reaches from here. A resolved card has no box to be the nearer
    // answer, and standingConversation reads the box rather than the class, so the press
    // there is the general box's after all.
    when: () => !fabAnchorAt() && !standingConversation(),
    returnFrame: () => ({
      active: () => generalRow.contains(documentFocused()),
      close: () => generalInput.blur(),
      does: "Return to the thread panel",
      line: "back to threads",
    }),
    run: () => generalInput.focus({ preventScroll: true }),
  };

  pageScope("panel", {
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
          { id: "thread.find.next", binding: "n", does: "Go to the next thread found" },
          {
            id: "thread.find.previous",
            binding: "Shift+n",
            does: "Go to the previous thread found",
          },
        ],
        does: "Next / previous thread found",
        line: "search matches",
        repeat: true,
        when: () => threadSearchActive() && hasThreads(),
        run: (binding) => stepThread(binding === "n" ? 1 : -1),
      },
      {
        id: "thread.waiting.toggle",
        // `w` for the words the control says. It is the phrase the page already uses for
        // the same question asked of its widgets (a/A), asked here of the conversation —
        // so the reader learns one idea and reaches it two ways rather than learning
        // "needs you" beside it.
        //
        // A narrowing is a mode, so the row states it as one: the sentence and line turn
        // on whether it stands, and a successful keyboard activation pushes its return
        // frame. Dead while there is nothing waiting and nothing hidden, which is the same
        // fact that greys the control — and dead before the log arrives, which is the one
        // part of that the standing narrowing cannot say for itself: `needsYou` is a flag
        // the reader set, and it outlives a list that has gone back to empty. `/` needs no
        // such clause, `renderPanel` emptying `threadList` at every phase but ready.
        keys: ["w"],
        does: () =>
          needsYou()
            ? "Show every thread again"
            : "Show only the threads waiting on you",
        line: () => (needsYou() ? "all threads" : "waiting on you"),
        control: () => narrowingView.readerControl,
        when: () =>
          runtime.statePhase === "ready" &&
          (needsYou() || threadList().some((...args) => awaitsReader(...args))),
        returnFrame: () => ({
          active: () => panelIsOpen() && needsYou(),
          close: () => narrowingView.readerControl.click(),
          does: "Show every thread again",
          line: "show all",
        }),
        run: () => narrowingView.readerControl.click(),
      },
      {
        id: "thread.find",
        // `/` is what every list with a search field takes it with, and the one letter a
        // text box does not shadow: the typing scope claims what types a character, so the
        // press only ever reaches here from the list rather than from a box in it.
        keys: ["/"],
        does: "Find in the threads",
        line: "find",
        control: () => findInput,
        returnFrame: () => ({
          active: () =>
            panelIsOpen() && (findInput === documentFocused() || narrowed()),
          lineWhen: () => !threadSearchActive() || !inPanel(),
          close: () => {
            if (widen()) return false;
            findInput.blur();
          },
          does: () =>
            narrowed() ? "Show every thread again" : "Leave the thread search",
          line: () => (narrowed() ? "show all" : "back to threads"),
        }),
        run: () => {
          findInput.focus();
          findInput.select();
        },
      },
      // Last, because `w` and `/` are the list's own operations while this is a contextual
      // route through it. The latest return frame already owns the first key-line slot; the
      // remaining one should say what the list can do. The page-comment box advertises `c`
      // in its own placeholder, and the complete reference retains this row.
      PANEL_SAY,
    ],
  });

  // The find box is a text box and takes the letters like any other, so it stands inside
  // the typing scope and states only what it does differently: Escape lets the narrowing go
  // rather than merely leaving the box, and Enter walks into the list the words just found.
  // Registered on the exact input, which is the whole of how it shadows that scope's own
  // Escape — no listener of its own, no preventDefault written by hand.
  function declareFindBoxKeys() {
    keys(
      findInput,
      "In the find box",
      [
        {
          id: "thread.find.close",
          keys: ["Escape"],
          does: () =>
            narrowed()
              ? "Show every thread again"
              : "Leave the box, keeping what is typed",
          line: () => (narrowed() ? "show all" : "back to list"),
          // One press, one step, like every other Escape in the register: the narrowing
          // goes first and the box is left on the next press, rather than both at once.
          run: () => {
            if (widen()) return;
            findInput.blur();
            threadsBox.focus();
          },
        },
        {
          id: "thread.find.first",
          keys: ["Enter"],
          does: "Go to the first thread found",
          line: "first found",
          when: hasThreads,
          run: () => stepThread(1),
        },
      ],
      pagePresented,
    );
  }

  return {
    syncGeneral,
    pageComposerDrawing,
    openPageDrawing,
    mount,
  };
}
