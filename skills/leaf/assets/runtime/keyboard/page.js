import { focusedThread } from "../conversation/focus.js";
import { takesLetters, letGo } from "../focus.js";
import { EVERYTHING, TEXT_ENTRY } from "./text-entry.js";
import { ELEMENTS } from "./register.js";
import { DISCLOSURE_SELECTOR, disclosed } from "./disclosure.js";
import { SHORTCUT_HELP, CLOSE_SHORTCUT_SHELF } from "./shortcut-bar.js";
import { containsAcross, elementById, inChrome, pageQueryAll } from "../passages.js";
import { threadList } from "../conversation/state.js";
import { openThreads } from "../conversation/thread-list.js";
import { documentFocused, focused, keys } from "./scopes.js";
import { anchoringIsReady, addressableWord } from "../anchor-resolution.js";
import { currentTray } from "../trays.js";
import {
  findInput,
  generalInput,
  generalRow,
  needsBtn,
  panel,
  threadsBox,
} from "../conversation/panel-elements.js";
import { inPanel as panelFocusIsInside } from "../conversation/panel-elements.js";
import { composerOpen, fabInput, fabOptions } from "../composing/selection.js";
import {
  backFromConversation,
  conversationInput,
  heldConversation,
  standingConversation,
} from "../conversation/landing.js";
import { pageSelection } from "../composing/capture.js";
import { current, RETURN } from "./return-stack.js";
import {
  ariaShortcuts,
  bindings,
  checked,
  labelOf,
  live,
  PRESS,
  word,
} from "./bindings.js";
import {
  commandReferenceDialog,
  commandReferenceClose,
  moveCommandReferenceFocus,
  moveCommandReferenceSelection,
  commandReferenceCommandActive,
  commandReferenceOpen,
  activateSelectedCommand,
} from "./command-reference.js";
import { shortcutShelfOpen } from "./shortcut-bar.js";
import { pagePresented } from "../presentation.js";
import { runtime } from "../context.js";
import { DISCLOSE } from "./disclosure.js";
import { latestChip } from "../version.js";
import { narrowed, needsYou, threadSearchActive } from "../conversation/narrowing.js";
import { awaitsReader } from "../conversation/model.js";
import { keeps } from "../widget-elements.js";

export function createPageKeys({
  panelIsOpen,
  coveringAuxiliarySurface,
  stepReading,
  openAsks,
  GO_TO_SCOPE,
  OPEN_GO_TO,
  undoable,
  undoLast,
  unaccountedGesture,
  setPanel,
  setOpenTray,
  captureAuxiliaryChromeState,
  restoreAuxiliaryChromeState,
  widen,
  landIn,
  stepAsk,
  stepThread,
  composerHolds,
  focusedResponseOption,
  responseOptionsAreOpen,
  responseReactionButtons,
  setResponseOptions,
  stepResponseOptions,
  dismissFab,
  fabAnchorAt,
  fabOptionsAvailable,
  commentOnAddressable,
  focusFabComment,
  showFabOptions,
  updateFab,
  hasReactionTarget,
  REACT,
  reactionTokens,
  setReact,
  undoSentence,
  designModeActive,
  setDesignMode,
  PAGE_SEARCH,
  REPEAT_PAGE_SEARCH,
  TARGET_CHOOSER_SCOPE,
  PAGE_SEARCH_SCOPE,
  openTargetChooser,
  AIM,
  drawModeActive,
  setDrawMode,
  generalHint,
  CHOOSER,
  NEWEST,
  VERSIONS,
  activeInlineThread,
  keyboardRung,
  standingElement,
  actionRow,
}) {
  const inPanel = () => panelFocusIsInside(panelIsOpen);
  /* The page's own keys: the scopes core declares — the reference, the shortcut bar's shelf, the
   Page Map, the composer, a text box, the thread panel, a focused thread, a link, a
   disclosure, design mode, and the page itself — and what a press from each of them
   does. A row's fields are stated once, in bindings.js; a scope's `at`/`when` pair in
   scopes.js. Widgets never see this list: they declare their own scopes through the
   register, and the dispatcher walks both. */

  // ---------- what the page's keys are live over ----------
  function hasThreads() {
    return openThreads({ visibleOnly: panelIsOpen() }).length > 0;
  }

  // The conversation the reader is standing in, and the box it is written in. Three
  // containers hold one and the reader can stand in any of them: the panel's thread, a
  // conversation seated on the page (x-conversation), and each thread inside that seat. They
  // are one question — a press meaning "say something about this" belongs to the box of the
  // conversation the reader is already in — so they get one reading rather than a rule for
  // the panel and a different one for the page. `conversationBox` states the same rule from
  // the other side when it declines to seat a widget standing inside a thread.
  //
  // One of the three is in the chrome, which is not the exception it looks like: page scope
  // already crosses there. A page key that takes the reader somewhere owes them an answer
  // once they are standing there.
  //
  // The box decides membership, rather than the container's class deciding it. A resolved
  // thread is built by the same function, wears the same class, and keeps a tab stop and a
  // Reopen button — reading the class alone put the reader in a thread whose box is not
  // there and the press died on the null. Asking for the box answers both shapes at once,
  // and answers a container that is merely collapsed the same honest way: no box, so this is
  // not where the press goes.
  //
  // `focused()` here where standingElement takes the host: this asks whether the reader is
  // inside a conversation, and a widget an agent sent stages its controls in a shadow tree
  // of its own, so the innermost focus is where they actually are. The climb out is
  // closestAcross's.
  // What `c` acts on, decided once and read twice: the row's words are `word` and the press
  // is `go`, so the line, the reference and the box that opens cannot come to name different
  // things. Spelled out at each of them the ladder was two hand-written copies in the same
  // order kept in step by hand, which is the mistake `focusedThread` already names — the row
  // the line paints and the press the dispatcher takes have to ask one question.
  //
  // One aim and then one climb, rather than four cases. The pointer's aim outranks position,
  // being the more recent thing the reader said; below it the answer walks outward from where
  // they are standing — the nearest conversation's box, then the nearest addressable element,
  // then the page,
  // which is what is left when they are standing nowhere in it. An element anchor answers in
  // its own word (a figure, a card), the way the panel names one.
  //
  // Every destination is a box to write in and says so in the same sentence; the word is
  // what varies.
  function commenting(word) {
    return {
      does: `Comment on the ${word}`,
      line: `comment on the ${word}`,
    };
  }

  function composerReturnFrame() {
    return {
      active: () => composerOpen,
      close: dismissFab,
      does: "Return to where you were",
      line: "back",
    };
  }

  function boxReturnFrame(held, box, does = "Return to the thread") {
    return {
      active: () =>
        held?.isConnected && (containsAcross(held, focused()) || box === focused()),
      close: () => box.blur(),
      does,
      line: "back to thread",
    };
  }

  function commentDestination() {
    const anchor = fabAnchorAt();
    if (anchor)
      return {
        ...commenting(
          anchor.quote
            ? "selection"
            : addressableWord(elementById(anchor.section)) || "element",
        ),
        box: fabInput,
        go: focusFabComment,
        returnFrame: composerReturnFrame,
      };
    const inline = activeInlineThread();
    const inlineBox = inline && conversationInput(inline);
    const said =
      standingConversation() ?? (inlineBox ? { held: inline, box: inlineBox } : null);
    if (said)
      return {
        ...commenting("thread"),
        box: said.box,
        go: () => landIn(said),
        returnFrame: () => boxReturnFrame(said.held, said.box),
      };
    const here = standingElement();
    if (here)
      return {
        ...commenting(addressableWord(here)),
        box: fabInput,
        go: () => commentOnAddressable(here),
        returnFrame: composerReturnFrame,
      };
    return {
      ...commenting("page"),
      box: generalInput,
      go: () => {
        setPanel(true);
        generalInput.focus({ preventScroll: true });
      },
      returnFrame: () => {
        const previousAuxiliaryChrome = captureAuxiliaryChromeState();
        return {
          active: () => panelIsOpen() && generalRow.contains(documentFocused()),
          close: () => restoreAuxiliaryChromeState(previousAuxiliaryChrome),
          does: "Return to where you were",
          line: "back",
        };
      },
    };
  }

  // c goes where commenting happens: a live selection gets the composer (what the floating
  // button does), an element click's pending 💬 gets that, an open thread the reader is
  // standing in gets its own reply box, the item they are standing in gets the box belonging
  // to it, and otherwise the page's general box. That box lives in Threads, but c names and
  // focuses the box directly; g T independently names the list. Never the panel's collapse:
  // c doubled as the toggle once, so with the panel standing open the key that promised
  // “comment” answered “close”. Backing out is the entry's return frame.
  //
  // Standing outranks the page and not the pointer: a reader who has just selected words or
  // raised the 💬 on something has said what they mean more recently than the focus they left
  // behind, which is the order the target reading below uses.
  function commentKey() {
    updateFab(); // the selection may be newer than the mouseup that last placed the bar
    commentDestination().go();
  }

  // The destination's box is the identity chrome uses to place a contextual binding badge.
  // Dispatch still decides whether either Comment row can be reached from the current scope.
  const commentBox = () => commentDestination().box;

  const COMMENT_CREATE = {
    id: "comment.create",
    keys: ["c"],
    // One key, four destinations, and the surfaces name the one in front of the reader:
    // a live selection, the item a click raised the 💬 on, the box belonging to whatever
    // the reader is standing in, or — when none of those is in hand — the page itself.
    // "Comment" covered them all and so promised none of them. All four enter their
    // actual box; the panel's contextual c reaches the same general box from its list.
    does: () => commentDestination().does,
    line: () => commentDestination().line,
    // A selection made before the anchor pass has run can't be quoted yet, and
    // commenting on the page instead is not what the reader asked for — so the press
    // waits, and the row's own liveness is where that is said rather than a refusal
    // inside run that no surface can see.
    when: () => anchoringIsReady() || !pageSelection(),
    returnFrame: () => {
      updateFab();
      return commentDestination().returnFrame?.() ?? null;
    },
    run: commentKey,
  };

  // Pages are authored documents where typing can start at any moment, so a scope whose keys
  // are bare letters stands down wherever a letter is a keystroke. That is the whole of the
  // question, and asking a wider one cost the page its keyboard: every `<input>` counted,
  // so a reader standing on a screenshot's before/after radio — which consumes no letter the
  // platform ever gave it — lost c, page travel, Ask travel and the rest, with nothing on screen saying why.
  // A select is in, its letters jumping its options; a radio, a checkbox, a slider, a colour
  // or file button are out. The platform's set of text-entry types, stated whole: a denylist
  // named the two controls to hand and left a slider swallowing the Escape rung the same way
  // the version chooser had. A bare or unknown type resolves to "text", so the default lands
  // on the typed side.
  // The fallback Escape reading for state reached without a registered keyboard entry:
  // pointer-opened auxiliary surfaces, captured targets, and ordinary focus traversal. Commanded
  // entries use the return stack and never infer their inverse from this resulting scene.
  //
  // So the first rung is theirs: out on the page, the innermost thing they are in is the Ask
  // they are standing on, and a panel behind them is a layer they are not in. Nothing said
  // this before — a reader the walk had brought to an Ask could press Escape all day and the
  // ring stayed on it, the one place in the runtime a key put the reader somewhere with no
  // key to take them out again.
  //
  // Inside the chrome it is the open auxiliary surface first. Trays and Threads replace one
  // another, so a standing tray is the one auxiliary layer Escape can unwind.
  //
  // Then the last rung leaves the chrome, because closing the panel does not put the reader
  // back on the page: it lands them on the control that closes it, deliberately (setPanel
  // says why), and the closing keypress rings a button a pointer-borne reader never chose.
  // Their next Space is then that button rather than the page's scroll. CLAUDE.md's "The
  // reader has to be standing somewhere" holds the rest.
  function rung() {
    const active = documentFocused();
    const holding = Boolean(active) && active !== document.body;
    if (pageSelection() || fabAnchorAt())
      return {
        says: "unselect",
        does: "Clear the selection",
        out: dismissFab,
      };
    if (holding && !inChrome(active))
      return { says: "let go", does: "Let go of what you are standing on", out: letGo };
    // Whichever tray holds the edge, named by the rung so the reader is told what the
    // press will take rather than being told "close the tray" over two of them.
    const tray = currentTray();
    if (tray) {
      // The tray's key is the runtime's; the reader knows the strip by the banner's word.
      return {
        says: `close ${tray}`,
        does: `Close the ${tray} tray`,
        out: () => setOpenTray(null),
      };
    }
    // A narrowing is a layer of the panel the way a tray is a layer of the page: the
    // reader put it on, and the list in front of them is not the whole of the conversation
    // until it comes off. So it unwinds before the panel does, and from wherever they are
    // standing — the find box binds the same step for itself, being the one place the
    // reader can see what they are backing out of.
    if (panelIsOpen() && narrowed())
      return {
        says: "show all",
        does: "Show every thread again",
        out: (...args) => widen(...args),
      };
    if (panelIsOpen())
      return {
        says: "close threads",
        does: "Close the thread panel",
        out: () => setPanel(false),
      };
    if (holding)
      return { says: "back to the page", does: "Back out onto the page", out: letGo };
    return null;
  }

  // The page's own Escape, said and run off one object: each rung states the act, the word
  // the line paints over it and the sentence the reference lists. A row rather than a rung,
  // so the reference names it beside every other key and cannot list a stale half of the
  // ladder.
  //
  // The sentence is the rung's for the reason `c`'s is the anchor's: the reader can see
  // which branch they are in, so a word covering all of them tells them nothing. "Back out
  // one layer" was true while every rung took a layer of chrome off the page, and stopped
  // being true the day the first rung became letting go of an Ask, which is no layer at
  // all — the line saying "let go" while the reference said "layer" about the same press.
  const BACK_OUT = {
    id: "navigation.back",
    keys: ["Escape"],
    does: () => rung()?.does,
    line: () => rung()?.says,
    // Search repeat is the useful contextual hint after Enter accepts the first result.
    // Escape remains live and stays in the complete reference without occupying that slot.
    lineWhen: () => !threadSearchActive() || !inPanel(),
    // Clearing a captured target is still available, but c and r are the two actions on the
    // thing the reader just chose. Keep both on the short line and leave this row in the full
    // reference until the target is gone.
    promoteEscape: () => !Boolean(fabAnchorAt()) || reactionTokens().length === 0,
    when: () => !current() && Boolean(rung()),
    run: () => rung().out(),
  };

  const PAGE_MOVE = {
    id: "page.move",
    keys: ["d", "u"],
    routes: [
      {
        id: "page.down",
        binding: "d",
        does: "Move 60% of a page down",
        line: "page down",
      },
      {
        id: "page.up",
        binding: "u",
        does: "Move 60% of a page up",
        line: "page up",
      },
    ],
    does: "Move 60% of a page down or up",
    line: "page down / up",
    repeat: true,
    run: (binding) => stepReading(binding === "d" ? 0.6 : -0.6, "page"),
  };

  const SCROLL_MOVE = {
    id: "scroll.move",
    keys: ["j", "k"],
    routes: [
      {
        id: "scroll.down",
        binding: "j",
        does: "Scroll down a little",
        line: "scroll down",
      },
      {
        id: "scroll.up",
        binding: "k",
        does: "Scroll up a little",
        line: "scroll up",
      },
    ],
    does: "Scroll down or up a little",
    line: "scroll down / up",
    repeat: true,
    run: (binding) => stepReading(binding === "j" ? 60 : -60, "pixel"),
  };

  // ---------- what a scope takes ----------
  // A scope shadows what stands behind it two ways, and they are one rule: a row of its own
  // that names the key, and a claim on keys it has no row for. The second is the platform's
  // share — where the reader stands, the browser already answers these and the register has
  // nothing to run and nothing to say, so an outer row that named one would be promising a
  // press it will not get. Everything not claimed stacks: a scope's rows are reached
  // wherever no nearer scope has taken the binding.
  //
  // This was a blanket (`only: true`), and the blanket is what put a working keyboard out of
  // a reader's reach. A text box does claim every key that types a character, so the blanket
  // was right about the case it was written for and wrong about the class: the box also took
  // the Escape it has no use for, which one branch inside its own row then hand-rescued for
  // the controls that type nothing. One key rescued and every other one left swallowed is the
  // shape of a menu being extended. Named as a claim instead, the rescue is deleted rather than
  // widened: a select's typeahead takes the letters and leaves the page's Escape standing,
  // and a radio, which types nothing, claims nothing and keeps the whole keyboard.
  function landInThreadReply(thread) {
    return landIn({ held: thread, box: conversationInput(thread) });
  }

  const resolutionControl = (thread) =>
    thread?.querySelector(
      ":scope > .lf-thread-head > .lf-resolve, " +
        ":scope > .lf-thread-actions > .lf-reopen, " +
        ":scope > .lf-conversation-resolved .lf-reopen",
    ) ?? null;

  const COMMAND_REFERENCE_SCOPE = {
    title: "In the command reference",
    escape: "inner",
    root: () => commandReferenceDialog,
    at: () => commandReferenceOpen(),
    claims: EVERYTHING,
    rows: [
      {
        id: "command.reference.focus.walk",
        keys: ["Tab", "Shift+Tab"],
        does: "Move through the command reference",
        line: "move",
        repeat: true,
        runFromCommandReference: false,
        run: (binding) => moveCommandReferenceFocus(binding === "Tab" ? 1 : -1),
      },
      {
        id: "command.reference.command.next",
        keys: ["ArrowDown"],
        does: "Choose the next command",
        line: "choose next",
        repeat: true,
        runFromCommandReference: false,
        // The list is built before search receives focus, so physical liveness is false at
        // that instant even though this is one of the reference's standing instructions.
        commandReferenceWhen: () => true,
        when: () => commandReferenceCommandActive(),
        run: () => moveCommandReferenceSelection(1),
      },
      {
        id: "command.reference.command.previous",
        keys: ["ArrowUp"],
        does: "Choose the previous command",
        line: "choose previous",
        repeat: true,
        runFromCommandReference: false,
        commandReferenceWhen: () => true,
        when: () => commandReferenceCommandActive(),
        run: () => moveCommandReferenceSelection(-1),
      },
      {
        id: "command.reference.command.activate",
        keys: ["Enter"],
        does: "Activate the chosen command",
        line: "activate",
        runFromCommandReference: false,
        commandReferenceWhen: () => true,
        when: () => commandReferenceCommandActive(),
        run: () => activateSelectedCommand(),
      },
      {
        id: "command.reference.close",
        keys: ["Escape"],
        does: () =>
          shortcutShelfOpen()
            ? "Back to more keyboard shortcuts"
            : "Close the command reference",
        line: () =>
          shortcutShelfOpen() ? "back to more shortcuts" : "close command reference",
        control: () => commandReferenceClose,
        runFromCommandReference: false,
        run: () => commandReferenceClose.click(),
      },
    ],
  };

  const SHORTCUT_SHELF_SCOPE = {
    title: "In the shortcut shelf",
    escape: "inner",
    root: () => commandReferenceDialog,
    at: () => Boolean(shortcutShelfOpen()),
    rows: [CLOSE_SHORTCUT_SHELF],
  };

  // A thread card and the unfolded margin entry cluster that owns it are one page-map stack,
  // though the card itself is hoisted into the chrome. This is a scene-derived fallback:
  // a later keyboard entry returns through its captured frame before this rung. Without
  // one, the registered rung precedes the reaction and navigation fallbacks just as the
  // surface's old local listener did: Escape closes the card first, then folds the cluster
  // on a second press.
  function pageMapRung(atFocus = true) {
    return keyboardRung({ atFocus }) ?? null;
  }

  const PAGE_MAP = {
    title: "In the Page Map",
    root: () => pageMapRung()?.root ?? document,
    when: () => Boolean(pageMapRung(false)),
    at: () => Boolean(pageMapRung()),
    rows: [
      {
        id: "margin.back",
        keys: ["Escape"],
        does: () => pageMapRung(false)?.does,
        line: () => pageMapRung()?.says,
        commandReferenceWhen: () => Boolean(pageMapRung(false)),
        when: () => Boolean(pageMapRung()),
        run: () => pageMapRung()?.out(),
      },
    ],
  };

  // Below the element scopes: the page's own modes, then the page. The composer's rung is
  // its own scope rather than the box's, because the box may not have focus — the reader
  // clicked away and the composer still stands, holding their draft.
  const COMPOSER = {
    title: "In the composer",
    at: () => composerOpen,
    rows: [
      {
        id: "comment.options",
        keys: ["Tab"],
        does: "Show other responses",
        line: "other responses",
        when: () => fabOptionsAvailable() && !responseOptionsAreOpen(),
        run: () => showFabOptions(),
      },
      {
        id: "composer.close",
        keys: ["Escape"],
        does: () =>
          composerHolds()
            ? "Close the composer, keeping the draft"
            : "Close the composer",
        line: () => (composerHolds() ? "close — draft kept" : "close"),
        promoteEscape: false,
        when: () => !responseOptionsAreOpen(),
        run: () => dismissFab(),
      },
    ],
  };

  const RESPONSE_REACTION = {
    id: "response.reaction.choose",
    keys: () =>
      responseReactionButtons()
        .slice(0, 9)
        .map((_, index) => String(index + 1)),
    label: () => {
      const count = Math.min(responseReactionButtons().length, 9);
      return count > 1 ? `1–${count}` : "1";
    },
    does: () =>
      `Put a reaction on the response target: ${reactionTokens()
        .slice(0, 9)
        .map(([name, entry], index) => `${index + 1} ${entry.glyph} ${name}`)
        .join(", ")}`,
    line: "react",
    when: () => !takesLetters(focused()) && responseReactionButtons().length > 0,
    run: (binding) => responseReactionButtons()[+binding - 1]?.click(),
  };
  const RESPONSE_TAB = {
    id: "response.tab",
    keys: ["Tab", "Shift+Tab"],
    does: "Move between the comment and other responses",
    line: "move",
    repeat: true,
    run: stepResponseOptions,
  };
  const RESPONSE_MOVE = {
    id: "response.move",
    keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
    does: "Move through other responses",
    line: "move",
    repeat: true,
    when: () => focusedResponseOption(),
    run: stepResponseOptions,
  };
  const RESPONSE_ACTIVATE = {
    id: "response.activate",
    keys: PRESS,
    does: "Use the focused response",
    line: "choose",
    when: () => focusedResponseOption(),
    run: () => focused()?.click(),
  };
  const RESPONSE_CLOSE = {
    id: "response.close",
    keys: ["Escape"],
    does: "Close other responses",
    line: "close",
    run: () => setResponseOptions(false, { returnFocus: true }),
  };
  const RESPONSE_OPTIONS_TITLE = "With other responses open";
  const RESPONSE_OPTIONS = {
    title: RESPONSE_OPTIONS_TITLE,
    escape: "inner",
    at: () => responseOptionsAreOpen() && focused() === fabInput,
    // These two keys move into and out of the disclosure itself, including while the
    // field's return frame stands nearer than ordinary containing surfaces.
    rows: [
      RESPONSE_REACTION,
      RESPONSE_TAB,
      RESPONSE_MOVE,
      RESPONSE_ACTIVATE,
      RESPONSE_CLOSE,
    ],
  };
  function declareResponseOptionKeys() {
    // Choice commands apply only while focus is inside the choices. They no longer stand
    // ahead of the field's exact send command or native text-entry claims.
    keys(
      fabOptions,
      RESPONSE_OPTIONS_TITLE,
      [
        RESPONSE_REACTION,
        RESPONSE_TAB,
        RESPONSE_MOVE,
        RESPONSE_ACTIVATE,
        RESPONSE_CLOSE,
      ],
      { when: responseOptionsAreOpen, escape: "inner" },
    );
  }

  // The box a reply or a comment is typed into, which is the panel's; a page's own control
  // is somewhere the reader is standing, not something they are writing in. Declared above
  // the scope rather than below it, because a row naming a predicate directly reads the
  // binding as the table is built — the deferring wrapper the branch here used to need was
  // the only thing hiding that.
  function inTheBox() {
    return panel.contains(documentFocused());
  }

  // Where a box reached by Tab or pointer hands the reader back. Keyboard entry carries its
  // own captured return frame before this fallback is reached. This once asked only for
  // `.lf-thread` and the panel, so the two boxes outside the chrome — a conversation seated
  // on the page, and each thread on that seat — had no relation to return through. The climb
  // is `heldConversation`'s, the same relation contextual `c` uses when it names a thread.
  //
  // A seat holding no thread yet has no standing place of its own. A widget control that
  // explicitly sends the reader into that box can supply its own return through
  // `landInConversation`; a visit reached by Tab still falls through to the page's "let go".
  // Otherwise the question is "can the reader be put here", rather than a list of which two
  // containers happen to be focusable — which is also why a seat that `reachScrollers` makes
  // focusable, having grown a scrollbar and no focusable child, becomes a rung without anyone
  // editing this: the question is the same one, and the answer moved.
  function backFromBox() {
    const held = heldConversation();
    if (held?.hasAttribute("tabindex")) return { target: held, line: "back to thread" };
    const route = backFromConversation(focused());
    return route?.target?.isConnected ? route : null;
  }

  // A box words are typed into takes character keys and the keys that edit it: Enter,
  // deletion, caret movement, Home/End, and page movement, including their modified forms.
  // Escape remains the box's to declare or pass on. What it declares is the way back out —
  // to the thread a reply
  // belongs to, so Esc then Enter round-trips, or to the list, so t/T walk on from where the
  // backing-out started. Drafts are kept at every rung.
  //
  // A control the reader is standing on rather than writing in keeps that rung without this
  // scope carrying a second branch for it: the scope claims the keys a box takes and leaves
  // every other press — c, the walks, the versions, the reference — to the scopes behind it.
  // The find box is a text box and takes the letters like any other, so it stands inside the
  // typing scope and states only what it does differently: Escape lets the narrowing go
  // rather than merely leaving the box, and Enter walks into the list the words just found.
  // Nearer than TYPING in the stack, which is the whole of how it shadows that scope's own
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
          // One press, one step, like every other Escape in the register: the narrowing goes
          // first and the box is left on the next press, rather than both at once.
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

  // A focused thread's primary route is its reply or reopen, not the page's. It said "On a
  // focused thread" and was live over the whole page, so a reader who had focused nothing
  // was offered a press that no-opped — the old page-step bug from the other side. The
  // reopen button tells the two states apart; absent a focused thread, the reference
  // describes the open state readers first meet rather than inventing a third one.
  const THREAD = {
    title: "On a focused thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(focusedThread()),
    rows: [
      {
        id: "thread.primary",
        keys: ["Enter"],
        does: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Write a reply",
        line: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "reopen"
            : "reply",
        when: () =>
          Boolean(conversationInput(focusedThread())) ||
          resolutionControl(focusedThread())?.matches(
            '.lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        returnFrame: () => {
          const thread = focusedThread();
          const box = thread && conversationInput(thread);
          return box ? boxReturnFrame(thread, box) : null;
        },
        // Find the thread's own compose row rather than the first textarea: a message may
        // contain a widget with an editor of its own before the reply box in DOM order.
        run: () => {
          const thread = focusedThread();
          const reopen = resolutionControl(thread)?.matches(".lf-reopen")
            ? resolutionControl(thread)
            : null;
          if (reopen) reopen.click();
          else landInThreadReply(thread);
        },
      },
      {
        id: "thread.resolution.toggle",
        keys: ["r"],
        does: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "Reopen it"
            : "Resolve it",
        line: () =>
          resolutionControl(focusedThread())?.matches(".lf-reopen")
            ? "reopen"
            : "resolve",
        // Search keeps its next/previous hints; resolution remains in the reference.
        lineWhen: () => !threadSearchActive(),
        when: () =>
          resolutionControl(focusedThread())?.matches(
            ':not(:disabled, [aria-disabled="true"])',
          ),
        run: () => resolutionControl(focusedThread()).click(),
      },
    ],
  };

  // Where the reader is standing, when what they are standing on is one of the page's own
  // parts rather than a widget's own declaration. The control scope below cannot cover
  // these: it works a span `offer` made pressable, where these arrive with platform keys
  // already bound. Enter follows an <a> while Space scrolls the page out from under it;
  // both work a disclosure. A generated `g` hint puts the reader on a disclosure, and Tab
  // can put them on either. Until a scope existed the line went quiet at exactly the moment
  // they arrived,
  // with the press that finishes the motion unnamed.
  //
  // The page's parts and not every one, which is the reading the target map takes as well:
  // the chrome's own links are the leaves tray's and its resolved comments are the panel's,
  // and both of those declare what they answer themselves. Asked of the document at large,
  // "On a link" was had by every page — a machine with one neighbour has a tray full of
  // links — so the reference named it wherever the reader went, on pages holding none to
  // stand on. One derivation and not a copy apiece: what a scope here asks is the same pair
  // of questions of a different selector, and the day the chrome rule changes is the day a
  // second copy of it is wrong.
  function standingOn(title, sel, rows) {
    return {
      title,
      root: focused,
      at: () => {
        const el = focused();
        return Boolean(el?.matches?.(sel)) && !inChrome(el);
      },
      // Across the declared shadow roots, where the addresses stop at the document: a row on
      // a staged disclosure names a key the browser does not answer, so a scope that could not
      // see one would leave the line promising a press nothing makes.
      when: () => pageQueryAll(sel).some((el) => !inChrome(el)),
      rows,
    };
  }

  // A link's press is the browser's whole answer, so this row binds no `run`: it promises
  // nothing the browser does not already do, and what it adds is the promise being on
  // screen. Enter alone, Space under a link being the page's own scroll.
  const LINK = standingOn("On a link", "a[href]", [
    { id: "link.follow", keys: ["Enter"], does: "Follow it", line: "follow" },
  ]);

  // A disclosure, in either spelling the page has for one. The platform's <details> keeps
  // the state on itself; a control a widget built out of a span says the same thing through
  // ARIA's own attribute, which it already writes for the theme and the screen reader. Two
  // vocabularies, one capability — and a reader standing on a settled group cannot see
  // which of the two they are standing on, so a scope apiece would be the same press
  // answered on one of them and not the other.
  //
  // ARIA's disclosure pattern and not the attribute at large. A combobox wears
  // aria-expanded over a box words are typed into and a treeitem wears it in a walk of its
  // own, and ← / → belong to the caret and the walk there. The pattern is the pair, so the
  // selector asks for the button half too — which is what `offer` writes, and what a real
  // <button> brings with it.
  const DISCLOSURE = standingOn("On a disclosure", DISCLOSURE_SELECTOR, [
    {
      id: "disclosure.toggle",
      keys: () => DISCLOSE(focused()),
      does: "Open or close it",
      // Read where it is painted rather than named once for both branches, the way a diff's
      // own file rows read theirs: what the press does is whichever way the disclosure is
      // standing, and a word fixed at declaration could only ever say one of them.
      line: () => (disclosed(focused()) ? "close" : "open"),
      // Through the element's own click, so keyboard and pointer are one behaviour: a
      // <summary>'s click is the toggle the browser was already making, and a widget's
      // control runs the handler its own pointer press runs. Enter and Space are the
      // runtime's here rather than the platform's, because a row owns its whole binding set
      // and the dispatcher takes the key before the platform sees it. One toggle answers all
      // three: the arrow bound is the one that changes this disclosure, so a press cannot
      // mean anything else.
      run: () => focused().click(),
    },
  ]);

  // Design mode: a page mode the reader stands in for a batch of remarks about the layer.
  // Its Escape is the innermost rung while it stands — a composer opened in it closes
  // first (COMPOSER is nearer), then the mode, then the panels — and the press it is made
  // of is not a key at all, so that row binds nothing and says nothing on the line, the
  // way the ⌥ aim's row does.
  const DESIGN_MODE_SCOPE = {
    title: "In Design mode",
    at: designModeActive,
    rows: [
      {
        id: "design.mode.comment",
        keys: [],
        label: "click",
        does: "Comment on what the click lands on — a widget, a control, the chrome; prose still selects",
      },
      {
        // Both keys, on one row: l is the toggle and Escape the mode's own rung, and two
        // chips reading "leave design" said one thing twice on the line.
        id: "design.mode.exit",
        keys: ["Escape", "l"],
        does: "Exit Design mode",
        line: "exit Design mode",
        run: () => setDesignMode(false),
      },
    ],
  };

  // Draw mode claims one pointer stroke before handing its mark to an ordinary comment.
  // Its own scope keeps the toggle and Escape as the two ways out while the page underneath
  // remains the drawing surface rather than receiving the drag.
  const DRAW_MODE_SCOPE = {
    title: "In Draw mode",
    at: drawModeActive,
    rows: [
      {
        id: "draw.mode.stroke",
        keys: [],
        label: "drag",
        does: "Draw anywhere on the page, then send or add words",
      },
      {
        id: "draw.mode.exit",
        keys: ["Escape", "w"],
        does: "Exit Draw mode",
        line: "exit Draw mode",
        run: () => setDrawMode(false),
      },
    ],
  };

  // The page itself. Table order is the line's priority order — a total order every row has
  // already, rather than a field one can forget — so the first live rows are the short hints.
  // Escape is the default promotion over this order, because the way out of a current scene
  // must survive beside its way in. A row can waive only that promotion when two local actions
  // on the current state belong together; the binding remains live and stays in the reference.
  // Named for the same kind of reason: a mode standing over the page suspends the page's keys
  // and keeps this one (`allButCommandReference`), and the claim reads the binding off the row
  // rather than spelling "?" beside it — a fact about a binding written where the binding
  // cannot correct it is the register's own oldest bug. Its place in the table is nominal:
  // renderShortcutBar gives it the permanent More control instead of spending a hint slot on it.

  // The stack, innermost first, and the whole of what the runtime says about ordinary-key
  // order. Element scopes splice in where ELEMENTS stands. For Escape, the dispatcher reads
  // an explicit `escape: "inner"` on active modes and the exact focused element, then RETURN,
  // then every unmarked fallback; placement in this list grants no causal priority. Every
  // reading starts from these scopes, and the reference walks them backwards, so a mode this
  // list leaves out is one the reference never names.

  function buildPageScopes() {
    // What a press acts on is whose scope it belongs to: the page holds the presses whose
    // subject is the page — `a`/`A` walks its open asks, and `g` opens its
    // destinations — while a surface holds presses for its own contents. `w` narrows this
    // list and `/` searches it, and a list the reader is not looking at is neither a thing
    // to narrow nor a thing to search. `c` is the one row here whose subject is not this
    // list: it carries the page's contextual comment intent into the general box, and its
    // own guard says where it stands down, so the page's nearer selection, item, or
    // conversation answer wins there.
    //
    // Standing in the panel is where its focus is, not merely that it is open: the Threads
    // button is the banner's, so opening by pointer leaves the reader outside, and `g T`,
    // `t`, Tab or a click on a thread is what puts them in. THREAD draws one step further
    // in, which is why that scope sits before this one and its rows shadow these. Every
    // page has this scope: its general box stands and takes words from the first paint —
    // the offline banner says a comment will not send, not that there is nowhere to write
    // it. Whether the waiting filter is useful is `w`'s own condition, said on that row.
    // The thread walk follows the surface presenting the threads. Sharing its row with
    // covering workspace keeps t/T available inside the panel's modal scope boundary.
    const THREAD_WALK = {
      id: "thread.walk",
      // A walk's letter names its category; Shift reverses it. The two existing
      // page categories therefore use the same compact, repeatable grammar.
      keys: ["t", "Shift+t"],
      routes: [
        { id: "thread.next", binding: "t", does: "Next open thread" },
        { id: "thread.previous", binding: "Shift+t", does: "Previous open thread" },
      ],
      does: "Next / previous open thread",
      line: "threads",
      // Once textual search owns the panel, n/N are the canonical walk there. Keep
      // t/T as the page's open-thread walk without leaving two spellings for the same
      // panel action.
      when: () =>
        hasThreads() &&
        (!coveringAuxiliarySurface() || inPanel()) &&
        !(threadSearchActive() && inPanel()),
      repeat: true,
      run: (binding) => stepThread(binding === "t" ? 1 : -1),
    };
    const PANEL = {
      title: "In the thread panel",
      root: focused,
      at: () => inPanel(),
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
              does: "Go to the next thread found",
            },
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
          // frame. The scene rung remains only for pointer activation. Dead while there is nothing waiting
          // and nothing hidden, which is the same fact that greys the control — and dead
          // before the log arrives, which is the one part of that the standing narrowing
          // cannot say for itself: `needsYou` is a flag the reader set, and it outlives a
          // list that has gone back to empty. `/` needs no such clause, `renderPanel`
          // emptying `threadList` at every phase but ready.
          keys: ["w"],
          does: () =>
            needsYou()
              ? "Show every thread again"
              : "Show only the threads waiting on you",
          line: () => (needsYou() ? "all threads" : "waiting on you"),
          control: () => needsBtn,
          when: () =>
            runtime.statePhase === "ready" &&
            (needsYou() || threadList().some((...args) => awaitsReader(...args))),
          returnFrame: () => ({
            active: () => panelIsOpen() && needsYou(),
            close: () => needsBtn.click(),
            does: "Show every thread again",
            line: "show all",
          }),
          run: () => needsBtn.click(),
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
    };
    const PAGE = {
      rows: [
        actionRow,
        // The page itself is already a Comment target. `s` plus a hint names a more
        // particular one; either route opens Comment, while reactions wait for a target.
        COMMENT_CREATE,
        {
          id: "target.chooser.open",
          keys: ["s"],
          does: "Comment on a visible target by hint",
          line: "comment on target",
          // Once the field is open, its typing scope owns character keys. This gate also
          // keeps the route off the short line while a target is in hand.
          lineWhen: () => !Boolean(fabAnchorAt()),
          when: anchoringIsReady,
          run: (...args) => openTargetChooser(...args),
        },
        {
          // `e` opens the list on the target the reader has already named: the current
          // selection, item, or agent reply. Digits are optional accelerators in the
          // registry's declared order.
          id: "reaction.open",
          keys: ["e"],
          does: () =>
            `Open reactions — ${reactionTokens()
              .slice(0, 9)
              .map(([name, entry]) => `${entry.glyph} ${name}`)
              .join(
                ", ",
              )} — for the selection, the item you are standing on, or the reply you are reading`,
          line: "react",
          when: () =>
            reactionTokens().length > 0 &&
            hasReactionTarget() &&
            (anchoringIsReady() || !pageSelection()),
          run: () => {
            // Selection capture normally follows the pointer gesture in its queued turn.
            // A fast `e` may arrive before that turn even though the native Selection is
            // already complete. Capture it now so the command cannot advertise reaction
            // digits while opening no corresponding choices.
            if (pageSelection() && !fabAnchorAt()) updateFab();
            if (composerOpen && fabAnchorAt()) showFabOptions({ reaction: true });
            else setReact(true);
          },
        },
        // Search remains one press from the shelf and named in full by the reference.
        PAGE_SEARCH,
        REPEAT_PAGE_SEARCH,
        THREAD_WALK,
        {
          id: "ask.walk",
          keys: ["a", "Shift+a"],
          routes: [
            {
              id: "ask.next",
              binding: "a",
              does: "Next ask this page is waiting on you for",
            },
            {
              id: "ask.previous",
              binding: "Shift+a",
              does: "Previous ask this page is waiting on you for",
            },
          ],
          does: "Next / previous ask this page is waiting on you for",
          line: "asks",
          when: () => openAsks().length > 0,
          repeat: true,
          run: (binding) => stepAsk(binding === "a" ? 1 : -1),
        },
        // Scrolling is available in the page and in a covering auxiliary surface. The latter
        // reuses these rows while the modal floor suspends the rest of page scope.
        PAGE_MOVE,
        SCROLL_MOVE,
        {
          // The last thing the reader did to this page, put back. Its own key rather
          // than the platform's ⌘Z, which belongs to the box a reader is typing in and
          // is taken by the browser everywhere else: this is a page-level press like
          // every other letter here, and the typing scope keeps it off a composer's
          // words by claiming its letters. The word is "undo" and never the verb it is
          // about to state — `move` is one widget's word, and a line that said it would
          // be naming a member where the mechanism is what holds.
          id: "history.undo",
          keys: ["z"],
          does: () => undoSentence(),
          line: "undo",
          // Dead while the page holds a gesture no log read accounts for, this one's
          // own send included: the walk would name the gesture *before* the one they
          // just made and take that back instead. The line drops the chip for as long
          // as that is true rather than promising a press that would undo the wrong thing.
          when: () => !unaccountedGesture() && Boolean(undoable()),
          run: (...args) => undoLast(...args),
        },
        // Above the page's furniture, because it is the way out of wherever the reader is
        // standing and they are standing somewhere far more often than a panel is open: it
        // ranks with the presses that act on where they are, not with the versions and the
        // modes. Below it, the line drops chips a window at a time, and this is the one that
        // says how to undo the press that put them there.
        BACK_OUT,
        // And the sequence below it, having sat among the walks and pushed it off the end of a
        // 1280px line — the reader standing on an Ask, which is the one place the way out was
        // written for. What it costs to yield is small and what it buys is not: `g` opens a
        // door to three lists the walks above already reach one at a time, so a narrow window
        // hides a second way to somewhere; the press it was crowding out is the only way back
        // from where a press had just put the reader.
        OPEN_GO_TO,
        {
          id: "draw.mode.enter",
          keys: ["w"],
          does: "Draw on the page and attach the mark to a comment",
          line: "draw",
          when: () => anchoringIsReady(),
          run: () => setDrawMode(true),
        },
        {
          // The way in; the mode's own scope takes the letter back out (DESIGN_MODE_SCOPE), nearer
          // than this row, so while it stands this one is shadowed off the line.
          id: "design.mode.enter",
          keys: ["l"],
          does: "Enter Design mode: comment on the layer — a widget, a control, the chrome — rather than the page",
          line: "design mode",
          run: () => setDesignMode(true),
        },
        SHORTCUT_HELP,
        // Reference: a real key the browser owns, and one gesture that is not a key at all.
        // Neither says a word for the line, so neither is ever promised as the next press —
        // one rule where the three exemptions this replaced were three.
        {
          id: "browser.caret",
          keys: ["F7"],
          does: "Caret browsing (the browser's): select text by keyboard, then c",
        },
        AIM,
      ],
    };
    const COVERING_WORKSPACE = {
      title: "In the covering auxiliary surface",
      root: coveringAuxiliarySurface,
      when: () => Boolean(coveringAuxiliarySurface()),
      at: () => Boolean(coveringAuxiliarySurface()),
      // The global Go-to vocabulary is still a route out of this auxiliary surface. Reuse its
      // one entry row here; GO_TO_SCOPE moves its own root to the same modal surface while armed.
      rows: [
        PAGE_MOVE,
        SCROLL_MOVE,
        OPEN_GO_TO,
        THREAD_WALK,
        { ...BACK_OUT, when: () => Boolean(rung()) },
      ],
    };
    const scopes = [
      COMMAND_REFERENCE_SCOPE,
      SHORTCUT_SHELF_SCOPE,
      PAGE_MAP,
      GO_TO_SCOPE,
      RESPONSE_OPTIONS,
      REACT,
      PAGE_SEARCH_SCOPE,
      TARGET_CHOOSER_SCOPE,
      ELEMENTS,
      RETURN,
      VERSIONS,
      COMPOSER,
      TYPING,
      THREAD,
      PANEL,
      COVERING_WORKSPACE,
      LINK,
      DISCLOSURE,
      DRAW_MODE_SCOPE,
      DESIGN_MODE_SCOPE,
      PAGE,
    ];
    // Core's scopes are checked as the list is built by the rule every widget's are checked
    // by at upgrade, so a row here that presses with nothing to say for itself takes down the layer on
    // the first page rather than going quiet on every one.
    for (const scope of scopes.filter((scope) => scope !== ELEMENTS))
      checked(scope.rows, scope.title ?? "the page's own keys");
    return scopes;
  }
  function coreScopes() {
    return scopes.filter((scope) => scope !== ELEMENTS);
  }

  // A control the keyboard reaches names its shortcut from the row. `control` is where a
  // row says which control it duplicates; its projection follows liveness too, so a disabled
  // Ask does not advertise a shortcut the dispatcher has withdrawn. The latest-version
  // chip's route spans two rows, so it is composed from both. The Go-to owner paints
  // sequential steps while its interaction stands; this projection keeps the complete
  // route in the tooltip at rest.
  //
  // The pass runs in the standing chrome's frame, so every name it writes goes through
  // `keeps` and says nothing where the control already says it. Restated title or shortcut
  // metadata is news to whatever is reading the page — the mutation stream a screen reader
  // rebuilds its buffer from — and these controls stand on the banner the margin projection
  // watches.
  function paintCoreControls() {
    const returningToMore = Boolean(shortcutShelfOpen());
    const closeSays = returningToMore ? "Back to more shortcuts" : "Close";
    const closeTitle = returningToMore
      ? "Back to more shortcuts"
      : "Close the command reference";
    if (commandReferenceClose.textContent !== closeSays)
      commandReferenceClose.textContent = closeSays;
    if (commandReferenceClose.dataset.lfKeyTitle !== closeTitle)
      commandReferenceClose.dataset.lfKeyTitle = closeTitle;
    keeps(commandReferenceClose, "aria-label", closeTitle);
    const controlShortcut = (scope, row) =>
      [...(word(scope.sequencePrefix ?? scope.sequence) ?? []), labelOf(row)]
        .filter(Boolean)
        .join(" ");
    for (const scope of coreScopes())
      for (const row of scope.rows) {
        // The shortcut bar owns the permanent More control because its binding must first pass
        // through the same contextual shadowing as the line's ordinary rows.
        if (row === SHORTCUT_HELP) continue;
        const control = word(row.control);
        if (control) {
          if (!("lfKeyTitle" in control.dataset))
            control.dataset.lfKeyTitle = control.title;
          const active = live(row) && bindings(row).length > 0;
          const shortcut = controlShortcut(scope, row);
          keeps(
            control,
            "title",
            control.dataset.lfKeyTitle + (active ? ` (${shortcut})` : ""),
          );
          // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
          // alternatives. The complete sequence remains in the overlay, tooltip, and
          // accessible command reference instead of claiming its final press works alone.
          if (active && !scope.sequence)
            keeps(control, "aria-keyshortcuts", ariaShortcuts([row], false));
          else control.removeAttribute("aria-keyshortcuts");
        }
      }
    const latestBound = bindings(CHOOSER).length && bindings(NEWEST).length;
    keeps(
      latestChip,
      "title",
      latestChip.dataset.lfKeyTitle +
        (latestBound
          ? ` (${controlShortcut(GO_TO_SCOPE, CHOOSER)} ${labelOf(NEWEST)})`
          : ""),
    );
  }

  // The panel's local route to the contextual Comment capability. Both scoped rows are
  // exposed together below so the placeholder can project whichever one dispatch reaches.
  const PANEL_SAY = {
    // From the Threads list this puts the reader in the page-comment box. Page c reaches
    // the same box directly; this is the same contextual intent from a surface whose local
    // w and / commands remain useful until the reader asks to write.
    id: "comment.write",
    keys: ["c"],
    does: () => generalHint(),
    line: "comment",
    // Dead while the reader has a passage or an item in hand. `t` is a page key that
    // lands focus in the panel, so a reader who selected a paragraph and then walked
    // the threads is standing in this scope with their selection still live — and this
    // row, being the innermost, would have taken the press and spent it on the general
    // box, collapsing the selection as the box took focus. A gesture the reader made
    // outranks the room they happen to be standing in, so the row stands down and the
    // page's own c answers, on the passage, saying so on the shortcut bar first.
    //
    // Dead inside a conversation for the same reason read the other way. This scope is
    // live wherever focus is in the panel, a card the reader has walked to included, and
    // that card's own reply box is a nearer answer to "comment" than the general box is
    // — the one `Enter` reaches from here. Standing in a
    // conversation is the page's second destination, so the row stands down and lets it
    // answer, and the two ways into a thread's box stay one landing. A resolved card has
    // no box to be the nearer answer, and standingConversation reads the box rather than
    // the class, so the press there is the general box's after all.
    when: () => !fabAnchorAt() && !standingConversation(),
    returnFrame: () => ({
      active: () => generalRow.contains(documentFocused()),
      close: () => generalInput.blur(),
      does: "Return to the thread panel",
      line: "back to threads",
    }),
    run: () => generalInput.focus({ preventScroll: true }),
  };

  const commentRows = () => [COMMENT_CREATE, PANEL_SAY];

  const TYPING = {
    title: "In a text box",
    root: focused,
    at: () => takesLetters(focused()),
    claims: TEXT_ENTRY,
    rows: [
      {
        id: "text.leave",
        keys: ["Escape"],
        does: "Leave the box, keeping what is typed",
        line: () => backFromBox()?.line ?? "back to list",
        // The conversation the box belongs to, or the panel's list where it is the
        // chrome's own box. A page textarea that is neither leaves the row dead and the
        // page's rung standing, which is the honest answer: nothing there to go back to.
        when: () => Boolean(backFromBox()) || inTheBox(),
        run: () => {
          const back = backFromBox();
          document.activeElement.blur();
          (back?.target ?? threadsBox).focus();
        },
      },
    ],
  };

  const scopes = buildPageScopes();
  return {
    scopes,
    typing: TYPING,
    commentBox,
    commentRows,
    declareFindBoxKeys,
    declareResponseOptionKeys,
    paintCoreControls,
  };
}
