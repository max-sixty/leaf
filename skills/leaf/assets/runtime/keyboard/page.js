/* The page's own keys: the scopes core declares — the reference, the key line's shelf, the
   page map, the composer, a text box, the thread panel, a focused thread, a link, a
   disclosure, design mode, and the page itself — and what a press from each of them
   does. A row's fields are stated once, in bindings.js; a scope's `at`/`when` pair in
   scopes.js. Widgets never see this list: they declare their own scopes through the
   register, and the dispatcher walks both. */

import { containsAcross, elementById, inChrome, pageQueryAll } from "../passages.js";
import { openThreads, threadList } from "../conversation/reconcile.js";
import { documentFocused, focused, keys } from "./scopes.js";
import { actionRow, ASK_CONTROL, askPlace, standingIn, stepAsk } from "../asks/view.js";
import { anchoringIsReady, itemAt, itemWord } from "../anchors.js";
import { currentTray, asksPanel, othersPanel, showTray } from "../trays.js";
import {
  findInput,
  generalHint,
  generalInput,
  generalRow,
  needsBtn,
  panel,
  threadsBox,
} from "../conversation/panel.js";
import { inPanel, panelIsOpen, setPanel } from "../chrome-layout.js";
import { composerOpen, fabInput } from "../composing/selection.js";
import { draftOf } from "../composing/input.js";
import {
  dismissFab,
  fabAnchorAt,
  fabOptionsAvailable,
  focusFabComment,
  showFabOptions,
  updateFab,
} from "../composing/surface.js";
import { activeInlineThread, keyboardRung } from "../living-margin.js";
import {
  backFromConversation,
  conversationInput,
  heldConversation,
  landIn,
  SAY_BOX,
  standingConversation,
} from "../conversation/landing.js";
import { commentOnItem, stepReading, stepThread } from "../navigation.js";
import { pageSelection } from "../composing/capture.js";
import {
  hasReactionTarget,
  REACT,
  reactionTokens,
  setReact,
  undoSentence,
} from "../reactions.js";
import { current, RETURN } from "./return-stack.js";
import {
  ariaShortcuts,
  bindings,
  checked,
  labelOf,
  live,
  parsed,
  word,
} from "./bindings.js";
import {
  helpClose,
  moveReference,
  moveCommand,
  onCommandRail,
  referenceOpen,
  runSelected,
} from "./reference.js";
import {
  keylineExpanded,
  keylineMore,
  keylineMoreKey,
  keylineMoreText,
  less,
} from "./keyline.js";
import { pagePresented } from "../presentation.js";
import { runtime } from "../context.js";
import { DISCLOSE } from "./disclosure.js";
import { designOn, setDesign } from "../design.js";
import {
  isSelecting,
  PAGE_SEARCH,
  SELECT,
  startSelecting,
} from "../composing/targets.js";
import { openAsks } from "../asks/model.js";
import { undoable, undoLast } from "../projection.js";
import { GO, GOTO } from "./address.js";
import { AIM } from "../composing/aim.js";
import { CHOOSER, latestChip, NEWEST, VERSIONS } from "../version.js";
import { outbox } from "../outbox.js";
import { narrowed, needsYou, widen } from "../conversation/narrowing.js";
import { awaitsReader } from "../conversation/model.js";
import { replyBoxHasDraft } from "../conversation/replies.js";

export function pageParts(sel) {
  return [...document.querySelectorAll(sel)].filter((el) => !inChrome(el));
}

// ---------- what the page's keys are live over ----------
function hasThreads() {
  return openThreads().length > 0;
}

// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own. Open and resolved threads both qualify:
// each has a primary Enter action and x changes the same resolution state in either direction.
export function focusedThread() {
  const active = documentFocused();
  return active?.classList?.contains("lf-thread") ? active : null;
}

// The item the reader is standing in, which is what a press means when they have pointed
// at nothing. The ⌥ aim reaches an item through the pointer and focus used to reach none
// at all: tabbing to a link in an option left `c` offering the page.
//
// The unanswered Ask where the reader is standing on a control that works it, and the innermost
// item everywhere else. The control the walk stands them on is one part of the question
// (standOn), so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* an Ask is not
// the same fact: a reader who tabbed to a hyperlink has said
// something more particular than the question containing it, and answering the question
// there both overrides what they named and made the same markup answer differently
// according to whether its question was still open — a link in a settled group gave the
// option, the identical link in an open one gave the whole group.
//
// So the ring `markHere` paints and this are two questions, and the earlier version had
// them confused. The ring says which Ask the reader is in, for the walk and the answering
// keys; this says what a remark made here is about. They agree wherever the reader is
// working the Ask, which is every arrival the Ask walk makes.
//
// Below that, the innermost item — the aim's own reading — through `askPlace`, so a
// control a widget hoisted into the margin speaks for the Ask it points back at rather
// than for the block it hangs beside.
//
// Focus in the chrome is not a place in the page. The banner, the panel and the trays are
// where a reader works on the page rather than where they stand in it, so a press made
// from one means the page whole. A box that takes letters never arrives here at all: the
// typing scope claims the letter before the page is asked.
//
// `documentFocused()` rather than `focused()`: a control
// staged in a shadow tree retargets to its host, and the host is the place in the document
// both the chrome guard and the item walk want. standingConversation below wants the inner
// reading, and says so.
export function standingItem() {
  const held = documentFocused();
  if (!held || held === document.body || inChrome(held)) return null;
  const working = held.matches?.(ASK_CONTROL) ? standingIn() : null;
  return working ?? itemAt(askPlace(held));
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
// `focused()` here where standingItem takes the host: this asks whether the reader is
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
// they are standing — the nearest conversation's box, then the nearest item, then the page,
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

function workspaceControlRoute(control) {
  if (!control || control === document.body) return () => null;
  const ask = control?.closest?.(".lf-asks-row[data-lf-at]");
  if (ask) {
    const target = ask.dataset.lfAt;
    return () =>
      [...asksPanel.querySelectorAll(".lf-asks-row[data-lf-at]")].find(
        (row) => row.dataset.lfAt === target,
      ) ?? null;
  }
  const thread = control?.closest?.(".lf-thread[data-id]");
  if (thread) {
    const id = thread.dataset.id;
    return () =>
      [...panel.querySelectorAll(".lf-thread[data-id]:not([hidden])")].find(
        (row) => row.dataset.id === id,
      ) ?? null;
  }
  const leaf = control?.closest?.(".lf-others-panel a[href]");
  if (leaf) {
    const href = leaf.href;
    return () =>
      [...othersPanel.querySelectorAll("a[href]")].find((link) => link.href === href) ??
      null;
  }
  return () => (control?.isConnected ? control : null);
}

export function workspaceState() {
  return {
    panel: panelIsOpen(),
    tray: currentTray(),
    control: workspaceControlRoute(documentFocused()),
  };
}

export function restoreWorkspace(state) {
  const { panel: hadPanel, tray } = state;
  if (tray) showTray(tray);
  else if (hadPanel) {
    showTray(null);
    setPanel(true);
  } else {
    showTray(null);
    setPanel(false);
  }
  return state.control();
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
        anchor.quote ? "selection" : itemWord(elementById(anchor.section)) || "item",
      ),
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
      go: () => landIn(said),
      returnFrame: () => boxReturnFrame(said.held, said.box),
    };
  const here = standingItem();
  if (here)
    return {
      ...commenting(itemWord(here)),
      go: () => commentOnItem(here),
      returnFrame: composerReturnFrame,
    };
  return {
    ...commenting("page"),
    go: () => {
      setPanel(true);
      generalInput.focus({ preventScroll: true });
    },
    returnFrame: () => {
      const workspace = workspaceState();
      return {
        active: () => panelIsOpen() && generalRow.contains(documentFocused()),
        close: () => restoreWorkspace(workspace),
        does: "Return to where you were",
        line: "back",
      };
    },
  };
}

export function hasCapturedTarget() {
  return Boolean(fabAnchorAt());
}

export const responseInstructions = () =>
  reactionTokens().length
    ? "Press c to comment, or r to react."
    : "Press c to comment.";

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
const TYPED_TYPES = new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);

export function takesLetters(node) {
  return (
    Boolean(node) &&
    (node.tagName === "TEXTAREA" ||
      node.tagName === "SELECT" ||
      node.isContentEditable ||
      (node.tagName === "INPUT" && TYPED_TYPES.has(node.type)))
  );
}

// Letting go of what the reader is standing on. One act at both ends of the ladder, and
// one line of code, because standing on an Ask out on the page and standing on a banner
// button are the same state — the reader holding something — reached from either side of
// the chrome. What the two rungs do not share is the word, and neither word is the other's:
// leaving the chrome names where the reader lands, since that is the whole of what the
// rung is for, and letting go of an Ask names the act, since they were on the page all
// along.
//
// Focus rather than blur, because the two differ in what Space does next: a focused
// control owns the key, while body hands it back to the browser's root scrollport. A blur
// names no deliberate destination even when activeElement subsequently reads as body.
//
// Body therefore needs to be somewhere a reader can be put even on a short page. The
// explicit tab stop is programmatic only and gives every Escape handoff the same stable
// page destination without adding a visible stop to the Tab order.
document.body.tabIndex = -1;

export function letGo() {
  return document.body.focus({ preventScroll: true });
}

// Auto popovers and modal dialogs already put Escape in the platform contract. When one
// stands, let the browser dismiss the topmost layer and let that layer's toggle/close
// event update Leaf state. Product modes with a nearer Escape row (the composer, help's
// two-step shelf, a text box) still own their deliberate unwind step.
function browserDismissesTopLayer() {
  return Boolean(document.querySelector(":popover-open, dialog:modal"));
}

// The fallback Escape reading for state reached without a registered keyboard entry:
// pointer-opened workspaces, captured targets, and ordinary focus traversal. Commanded
// entries use the return stack and never infer their inverse from this resulting scene.
//
// So the first rung is theirs: out on the page, the innermost thing they are in is the Ask
// they are standing on, and a panel behind them is a layer they are not in. Nothing said
// this before — a reader the walk had brought to an Ask could press Escape all day and the
// ring stayed on it, the one place in the runtime a key put the reader somewhere with no
// key to take them out again.
//
// Inside the chrome it is the open workspace first. Trays and Threads replace one
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
      out: () => showTray(null),
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
  // Clearing a captured target is still available, but c and r are the two actions on the
  // thing the reader just chose. Keep both on the short line and leave this row in the full
  // reference until the target is gone.
  promoteEscape: () => !hasCapturedTarget() || reactionTokens().length === 0,
  when: () => !current() && !browserDismissesTopLayer() && Boolean(rung()),
  run: () => rung().out(),
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
export function EVERYTHING() {
  return true;
}

// A character key belongs to the box with any modifier: Shift changes its case, Alt may
// compose it, and Mod chords copy, select, or undo. The editing keys below stay the box's
// with modifiers too, so Shift+Arrow can extend a selection and Mod+Backspace can delete a
// word without an ancestor widget turning either into its own action. An exact element
// scope still stands nearer and can specialise a chord such as Mod+Enter for send.
function CHARACTER(binding) {
  return [...parsed(binding).key].length === 1;
}

const EDITING = new Set([
  "Enter",
  "Backspace",
  "Delete",
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
]);

function TEXT_ENTRY(binding) {
  return CHARACTER(binding) || EDITING.has(parsed(binding).key);
}

// What a mode standing over the page takes: the page's keys, and every scope between, minus
// the one key that says what this mode's own keys are. The reference is the exemption for the
// same reason the line draws its chip last whatever the room — a reader who has just opened
// something unfamiliar is exactly the reader who needs it, and a mode that swallowed it would
// leave the line naming a walk and no way to ask about anything else.
//
// A `function`, so the row it reads can be the one the page's own table declares: the modes
// are built beside the controls they belong to, further up than that table, and a claim is
// only ever called at a press. A blanket suits a mode that cannot outlive a keystroke — the
// chord disarms on any key and runs it again, so `?` still reaches the page behind it — and
// the versions menu is the other kind, standing until the reader closes it.
export function allButTheReference(binding) {
  return !bindings(REFERENCE).includes(binding);
}

function landInThreadReply(thread) {
  return landIn({ held: thread, box: thread.querySelector(SAY_BOX) });
}

const HELP = {
  title: "In this reference",
  at: () => referenceOpen(),
  claims: EVERYTHING,
  rows: [
    {
      id: "reference.focus.walk",
      keys: ["Tab", "Shift+Tab"],
      does: "Move through this reference",
      line: "move",
      repeat: true,
      runFromReference: false,
      run: (binding) => moveReference(binding === "Tab" ? 1 : -1),
    },
    {
      id: "reference.command.next",
      keys: ["ArrowDown"],
      does: "Choose the next command",
      line: "choose next",
      repeat: true,
      runFromReference: false,
      // The list is built before search receives focus, so physical liveness is false at
      // that instant even though this is one of the reference's standing instructions.
      referenceWhen: () => true,
      when: () => onCommandRail(),
      run: () => moveCommand(1),
    },
    {
      id: "reference.command.previous",
      keys: ["ArrowUp"],
      does: "Choose the previous command",
      line: "choose previous",
      repeat: true,
      runFromReference: false,
      referenceWhen: () => true,
      when: () => onCommandRail(),
      run: () => moveCommand(-1),
    },
    {
      id: "reference.command.run",
      keys: ["Enter"],
      does: "Run the chosen command",
      line: "run",
      runFromReference: false,
      referenceWhen: () => true,
      when: () => onCommandRail(),
      run: () => runSelected(),
    },
    {
      id: "reference.close",
      keys: ["Escape"],
      does: () =>
        keylineExpanded() ? "Back to more keyboard shortcuts" : "Close this reference",
      line: () => (keylineExpanded() ? "back to more shortcuts" : "close help"),
      control: () => helpClose,
      runFromReference: false,
      run: () => helpClose.click(),
    },
  ],
};

export const LESS_SHORTCUTS = {
  id: "keyline.less",
  keys: ["Escape"],
  does: "Show fewer keyboard shortcuts",
  line: "less",
  referenceWhen: () => false,
  runFromReference: false,
  run: () => less(),
};

const SHORTCUT_SHELF = {
  title: "With more keyboard shortcuts",
  at: () => Boolean(keylineExpanded()),
  rows: [LESS_SHORTCUTS],
};

// A Thread card and the unfolded Button cluster that owns it are one page-map stack,
// though the card itself is hoisted into the chrome. This registered rung precedes the
// reaction and navigation modes just as the surface's old local listener did: Escape
// closes the card first, then folds the cluster on a second press.
function pageMapRung(atFocus = true) {
  return keyboardRung({ atFocus }) ?? null;
}

const PAGE_MAP = {
  title: "In the page map",
  when: () => Boolean(pageMapRung(false)),
  at: () => Boolean(pageMapRung()),
  rows: [
    {
      id: "margin.back",
      keys: ["Escape"],
      does: () => pageMapRung(false)?.does,
      line: () => pageMapRung()?.says,
      referenceWhen: () => Boolean(pageMapRung(false)),
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
      when: () => fabOptionsAvailable(),
      run: () => showFabOptions(),
    },
    {
      id: "composer.close",
      keys: ["Escape"],
      does: () =>
        draftOf(fabInput).trim()
          ? "Close the composer, keeping the draft"
          : "Close the composer",
      line: () => (draftOf(fabInput).trim() ? "close — draft kept" : "close"),
      promoteEscape: false,
      run: () => dismissFab(),
    },
  ],
};

// The box a reply or a comment is typed into, which is the panel's; a page's own control
// is somewhere the reader is standing, not something they are writing in. Declared above
// the scope rather than below it, because a row naming a predicate directly reads the
// binding as the table is built — the deferring wrapper the branch here used to need was
// the only thing hiding that.
function inTheBox() {
  return panel.contains(documentFocused());
}

// The panel thread the reader is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
export function focusedThreadOf() {
  return documentFocused()?.closest?.(".lf-thread");
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
export function declareFindBoxKeys() {
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

export const TYPING = {
  title: "In a text box",
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

// A focused thread: the reply and the resolve are this scope's, not the page's. They said
// "On a focused thread" in their own sentences and were live over the whole page, so a
// reader who had focused nothing was offered a press that no-opped — the old page-step bug from the
// other side. The reopen button tells the two states apart; absent a focused thread, the
// reference describes the open state readers first meet rather than inventing a third one.
const THREAD = {
  title: "On a focused thread",
  when: () => threadList().length > 0,
  at: () => Boolean(focusedThread()),
  rows: [
    {
      id: "thread.primary",
      keys: ["Enter"],
      does: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "Reopen it"
          : "Write a reply",
      line: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "reopen"
          : "reply",
      when: () =>
        Boolean(focusedThread()?.querySelector(":scope > .lf-compose")) ||
        Boolean(
          focusedThread()?.querySelector(
            ':scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
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
        const reopen = thread.querySelector(":scope > .lf-thread-actions > .lf-reopen");
        if (reopen) reopen.click();
        else landInThreadReply(thread);
      },
    },
    {
      id: "thread.resolution.toggle",
      // `x` and not `r`, though resolve is the word it does: the press beside it in this
      // same scope is the reply, and a reader meeting `r` on the line reads "reply" before
      // they read "resolve". A key spelling its own word is the wrong key when the
      // neighbouring press owns the word it would be read as. `x` is the letter a thing
      // closes under, and no other scope had claimed it.
      keys: ["x"],
      does: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "Reopen it"
          : "Resolve it",
      line: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "reopen"
          : "resolve",
      // Through the thread's own button, so keyboard and mouse are one behaviour — the
      // focus landing included. Both states offer exactly one resolution button, and the
      // row's liveness names that reachable capability instead of hiding a no-op in run.
      when: () =>
        Boolean(
          focusedThread()?.querySelector(
            ':scope > .lf-compose > .lf-thread-actions > .lf-resolve:not(:disabled, [aria-disabled="true"]), :scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        ),
      run: () =>
        focusedThread()
          .querySelector(
            ':scope > .lf-compose > .lf-thread-actions > .lf-resolve:not(:disabled, [aria-disabled="true"]), :scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          )
          .click(),
    },
  ],
};

// Where the reader is standing, when what they are standing on is one of the page's own
// parts rather than a widget's own declaration. The control scope below cannot cover
// these: it works a span `offer` made pressable, where these arrive with platform keys
// already bound. Enter follows an <a> while Space scrolls the page out from under it;
// both work a disclosure. `g f` puts the reader on a disclosure, and Tab can put them on
// either. Until a scope existed the line went quiet at exactly the moment they arrived,
// with the press that finishes the motion unnamed.
//
// The page's parts and not every one, which is the reading the addresses take as well:
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
const DISCLOSURE_SELECTOR =
  'details > summary, :is(button, [role="button"])[aria-expanded]';

// Which way the disclosure at this element is standing: open, shut, or null where it is
// not a disclosure at all — which is a question asked from wherever the reader happens to
// be, the reference listing a scope the page has rather than the one they are in.
export function disclosed(el) {
  return !el?.matches?.(DISCLOSURE_SELECTOR)
    ? null
    : el.matches("details > summary")
      ? el.parentElement.open
      : el.getAttribute("aria-expanded") === "true";
}

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
const DESIGN = {
  title: "In design mode",
  at: () => designOn,
  rows: [
    {
      id: "design.comment",
      keys: [],
      label: "click",
      does: "Comment on what the click lands on — a widget, a control, the chrome; prose still selects",
    },
    {
      // Both keys, on one row: l is the toggle and Escape the mode's own rung, and two
      // chips reading "leave design" said one thing twice on the line.
      id: "design.leave",
      keys: ["Escape", "l"],
      does: "Leave design mode",
      line: "leave design",
      run: () => setDesign(false),
    },
  ],
};

// The page itself. Table order is the line's priority order — a total order every row has
// already, rather than a field one can forget — so the first live rows are the short hints.
// Escape is the default promotion over this order, because the way out of a current scene
// must survive beside its way in. A row can waive only that promotion when two local actions
// on the current state belong together; the binding remains live and stays in the reference.
// Named for the same kind of reason: a mode standing over the page suspends the page's keys
// and keeps this one (`allButTheReference`), and the claim reads the binding off the row
// rather than spelling "?" beside it — a fact about a binding written where the binding
// cannot correct it is the register's own oldest bug. Its place in the table is nominal:
// renderLine gives it the permanent More control instead of spending a hint slot on it.
export const REFERENCE = {
  id: "reference.open",
  runFromReference: false,
  keys: ["?"],
  does: () =>
    keylineExpanded() ? "All keyboard shortcuts" : "More keyboard shortcuts",
  line: () => (keylineExpanded() ? "all shortcuts" : "more"),
  control: () => keylineMore,
  run: () => keylineMore.click(),
};

// The stack, innermost first, and the whole of what the runtime says about the order. The
// Element scopes splice in where ELEMENTS stands. RETURN follows that placeholder in this
// canonical list; the dispatcher places it at the dynamic boundary after the exact control
// and before generic typing and ancestor rows, so an input can clear its own query before
// leaving while a plain composer returns in the one Escape its entry earned. Every reading
// starts from this stack: the dispatcher and line walk it inward, and the reference walks it
// backwards, so a mode this list leaves out is one the reference never names.
export const ELEMENTS = Symbol("the scopes of the focused element");
// The list is assembled on first use rather than as this module evaluates: several of its
// members — the g chord, reactions, the selection chooser, the return stack, the version
// chooser, the aim, an Ask's action row — are declared by the owners that answer their
// keys, and those owners import this module for what a page press means. Asking after
// every module has evaluated is what keeps the order of that cycle from mattering.
let scopes = null;
export function pageScopes() {
  if (scopes) return scopes;
  // What a press acts on is whose scope it belongs to: the page holds the presses whose
  // subject is the page — `t`/`T` and `a`/`A` walk its open sets, and `g` opens its
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
  const PANEL = {
    title: "In the thread panel",
    at: () => inPanel(),
    rows: [
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
      // Comment can act immediately because the page itself is its target. Selecting a
      // more particular target is the second step; only then does React become an action.
      {
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
      },
      {
        id: "selection.open",
        keys: ["s"],
        does: "Choose a visible item by hint",
        line: "select item",
        // Once a target is in hand, its actions own the two short-line slots. Escape clears
        // it, while this projection-only gate leaves s live to replace the target and keeps
        // that capability in the complete reference.
        lineWhen: () => !hasCapturedTarget(),
        when: anchoringIsReady,
        run: (...args) => startSelecting(...args),
      },
      {
        // `r` opens the list on the target the reader has already named: the current
        // selection, item, or agent reply. Digits are optional accelerators in the
        // registry's declared order.
        id: "reaction.open",
        keys: ["r"],
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
          // A fast `r` may arrive before that turn even though the native Selection is
          // already complete. Capture it now so the command cannot advertise reaction
          // digits while opening no corresponding choices.
          if (pageSelection() && !fabAnchorAt()) updateFab();
          setReact(true);
        },
      },
      // Search remains one press from the shelf and named in full by the reference.
      PAGE_SEARCH,
      {
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
        when: hasThreads,
        repeat: true,
        run: (binding) => stepThread(binding === "t" ? 1 : -1),
      },
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
      {
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
        // An ordinary row, ranked where it stands. It was the one persistent declaration in
        // the runtime, which spent a third of the resting line restating what every reader
        // already does with a wheel, a trackpad or the space bar — and spent it on every
        // page, in every scope, beside whatever the reader was actually doing. Scrolling is
        // the one capability no page has to advertise. The shelf and the reference still
        // name it, which is where a key the reader has not asked after belongs.
        repeat: true,
        run: (binding) => stepReading(binding === "d" ? 0.6 : -0.6, "page"),
      },
      {
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
      },
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
      // And the chord below it, having sat among the walks and pushed it off the end of a
      // 1280px line — the reader standing on an Ask, which is the one place the way out was
      // written for. What it costs to yield is small and what it buys is not: `g` opens a
      // door to three lists the walks above already reach one at a time, so a narrow window
      // hides a second way to somewhere; the press it was crowding out is the only way back
      // from where a press had just put the reader.
      GOTO,
      {
        // The way in; the mode's own scope takes the letter back out (DESIGN), nearer
        // than this row, so while it stands this one is shadowed off the line.
        id: "design.enter",
        keys: ["l"],
        does: "Design mode: comment on the layer — a widget, a control, the chrome — rather than the page",
        line: "design mode",
        run: () => setDesign(true),
      },
      REFERENCE,
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
  scopes = [
    HELP,
    SHORTCUT_SHELF,
    PAGE_MAP,
    GO,
    REACT,
    SELECT,
    ELEMENTS,
    RETURN,
    VERSIONS,
    COMPOSER,
    TYPING,
    THREAD,
    PANEL,
    LINK,
    DISCLOSURE,
    DESIGN,
    PAGE,
  ];
  // Core's scopes are checked as the list is built by the rule every widget's are checked
  // by at upgrade, so a row here that presses with nothing to say for itself takes down the layer on
  // the first page rather than going quiet on every one.
  for (const scope of coreScopes())
    checked(scope.rows, scope.title ?? "the page's own keys");
  return scopes;
}
function coreScopes() {
  return pageScopes().filter((scope) => scope !== ELEMENTS);
}

// A control the keyboard reaches names its shortcut from the row. `control` is where a
// row says which control it duplicates; its projection follows liveness too, so a disabled
// Ask does not advertise a shortcut the dispatcher has withdrawn. The latest-version
// chip's route spans two rows, so it is composed from both.
export function paintCoreControls() {
  const returningToMore = Boolean(keylineExpanded());
  helpClose.textContent = returningToMore ? "Back to more shortcuts" : "Close";
  helpClose.dataset.lfKeyTitle = returningToMore
    ? "Back to more shortcuts"
    : "Close the shortcuts";
  helpClose.setAttribute(
    "aria-label",
    returningToMore ? "Back to more shortcuts" : "Close the shortcuts",
  );
  const controlShortcut = (scope, row) =>
    [...(word(scope.chordPrefix ?? scope.chord) ?? []), labelOf(row)]
      .filter(Boolean)
      .join(" ");
  for (const scope of coreScopes())
    for (const row of scope.rows) {
      const control = word(row.control);
      if (control) {
        if (!("lfKeyTitle" in control.dataset))
          control.dataset.lfKeyTitle = control.title;
        const active = live(row) && bindings(row).length > 0;
        control.title =
          control.dataset.lfKeyTitle +
          (active ? ` (${controlShortcut(scope, row)})` : "");
        // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
        // alternatives. The complete chord remains in the visible hint and accessible
        // keyboard reference instead of claiming its final press works alone.
        if (active && !scope.chord)
          control.setAttribute("aria-keyshortcuts", ariaShortcuts([row], false));
        else control.removeAttribute("aria-keyshortcuts");
      }
    }
  const referenceBound = bindings(REFERENCE).length > 0;
  keylineMoreKey.hidden = !referenceBound;
  const shelf = referenceBound && Boolean(keylineExpanded()) && !referenceOpen();
  keylineMoreText.textContent = shelf ? "all shortcuts" : "more";
  keylineMore.title = shelf ? "All keyboard shortcuts" : "More keyboard shortcuts";
  keylineMore.setAttribute("aria-expanded", String(shelf));
  keylineMore.setAttribute(
    "aria-label",
    referenceBound ? (shelf ? "? all shortcuts" : "? more") : "More keyboard shortcuts",
  );
  const latestBound = bindings(CHOOSER).length && bindings(NEWEST).length;
  latestChip.title =
    latestChip.dataset.lfKeyTitle +
    (latestBound ? ` (${controlShortcut(GO, CHOOSER)} ${labelOf(NEWEST)})` : "");
}

// A gesture of the reader's that the page has not accounted for in a log read, asked of
// the layer's own signals rather than of any widget by name: a drag wears .lf-dragging
// (dragging, above), every unresolved browser event is in the outbox, and an undo
// in flight is its own — it is tracked separately because the walk itself cannot be
// offered again while its event is being answered.
// Two questions want the answer,
// which is why it has a name of its own: navigating away would destroy such a gesture,
// and the undo walk reads the log to find the last thing the reader did, so it cannot
// answer while the page is holding one. Its own press included — a second `z` landing
// inside the first one's trip would read the log from before it and withdraw the same
// gesture again, which the door refuses and the reader hears as a page that couldn't
// reach its server.
export function unaccountedGesture() {
  return (
    runtime.undoing ||
    outbox.length > 0 ||
    Boolean(document.querySelector(".lf-dragging"))
  );
}

// The user is mid-something navigation would destroy: the above, and the words they
// have typed — a composition surface is a focused textarea holding words or a draft, or
// a widget-built one (data-lf-offer) even empty, because deleting everything is still an
// edit. A reply the runtime merely opened and focused is the exception: that landing has
// no reader-authored draft to preserve and therefore does not stop a live page following.
export function midComposition() {
  const active = focused();
  const replyDraft = replyBoxHasDraft(active) ?? null;
  return (
    composerOpen ||
    isSelecting() ||
    Boolean(fabAnchorAt()) ||
    unaccountedGesture() ||
    (active?.tagName === "TEXTAREA" &&
      (draftOf(active) !== "" ||
        replyDraft === true ||
        (replyDraft === null && active.hasAttribute("data-lf-offer"))))
  );
}

// The row whose key opens that box, standing here beside the sentence they share rather
// than down among the panel's other rows. The box paints its placeholder as `wireInput`
// builds it, and the placeholder names this row's key — read off the row, so rebinding it
// corrects the box too. Built later, the row is still in its dead zone at that first
// paint and the whole layer stops on the reference. The comment above already calls the
// two a pair; this is the pair being one thing rather than two that agree by hand.
export const PANEL_SAY = {
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
  // page's own c answers, on the passage, saying so on the key line first.
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
