import { shownBox, shownRect } from "../geometry.js";
import {
  createAddressPlacement,
  MAX_NUMBERED_ADDRESSES,
} from "../keyboard/address-placement.js";
import { bindings } from "../keyboard/bindings.js";
import { closestAcross, containsAcross, TEXT_BLOCK } from "../passages.js";
import { pageScroller } from "../scrolling.js";
import { decisionActions, decisionAnswer, watchDecisionActions } from "./actions.js";

export function createDecisionView({
  PAGE_PAINT_ATTRIBUTE,
  actionLayer,
  actionReachable,
  allDecisions,
  scrollBehavior,
  announce,
  decisionEntry,
  decisionSource,
  decisionsBtn,
  decisionsList,
  decisionsOffered,
  decisionsPanel,
  banner,
  readingBlock,
  closeTray,
  documentFocused,
  el,
  elementById,
  focusForNavigation,
  focused,
  inChrome,
  itemSays,
  itemWord,
  keylineEl,
  keys,
  openDecisions,
  openTray,
  paintAnchors,
  paintHere,
  paintKeys,
  PRESS,
  panelIsOpen,
  presentedActionControl,
  readableDestination,
  registry,
  reserve,
  reveal,
  scrollToElement,
  setPanel,
  showNews,
  shownParts,
  tagsDeclaring,
  trayCovers,
  unansweredDecisions,
  versionBtn,
}) {
  // One blanket answer per verb a widget declares one for (x-awaits.all), each deciding
  // its decisions one at a time so the log records what was consented to rather than one
  // blanket yes — accepting the rest after rejecting one stays honest. The widget
  // exposes a method named for the verb; the label is built from the same word.
  //
  // Built when the registry lands rather than written out above, so the second widget to
  // declare one gets its control by declaring it. Each takes its place in the row rather
  // than a box of its own: a control with no siblings is a control the press sweep walks
  // past, and one that only ever appears at upgrade spends the spacer's slack, not the
  // room of anything to its right.
  const bulkButtons = new Map();
  function buildBulkAnswers() {
    for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
      const verb = registry[tag]["x-awaits"].all;
      if (bulkButtons.has(verb)) continue;
      const label = verb[0].toUpperCase() + verb.slice(1);
      const btn = el("button", "lf-btn lf-answer-all", "");
      btn.title = `${label} every one still waiting on you`;
      let answering = false;
      btn.onclick = async () => {
        if (answering) return;
        answering = true;
        // Native disabling immediately drops keyboard focus on body, before the events
        // this press sends can settle and hide the control. Keep the busy button in the
        // focus model so showNews can hand its place to the next standing destination;
        // the guard above still makes a repeated activation inert.
        btn.setAttribute("aria-disabled", "true");
        try {
          for (const decision of openDecisions()) {
            const source = decisionSource(decision);
            if (decisionEntry(source)?.all === verb) await source[verb]?.();
          }
        } finally {
          answering = false;
          btn.removeAttribute("aria-disabled");
        }
      };
      showNews(btn, false);
      bulkButtons.set(verb, { btn, label });
      versionBtn.before(btn);
      // In the row now, so it holds the widest it reaches below a thousand — the same
      // words syncDecisions writes, measured in the face it will render in (see reserve).
      reserve(btn, [`${label} all (999)`]);
    }
  }

  // Each blanket answer with the decisions it would take, from the list above. The banner
  // writes its controls and counts from this one reading, without naming a verb in core;
  // which verbs exist is the registry's answer.
  function blanketAnswers(decisions) {
    return [...bulkButtons].map(([verb, { btn, label }]) => ({
      btn,
      label,
      n: decisions.filter(
        (decision) => decisionEntry(decisionSource(decision))?.all === verb,
      ).length,
    }));
  }
  // What the banner's button says about the page's Ask progress. The numerator is
  // durable completion rather than the reader's position in the open-Ask walk: moving
  // around the page changes neither number, while answering and revising do. The total
  // keeps answered Asks in reach instead of making completion erase its own route back.
  //
  // Written only on change: a poll repaints this, and an unchanged write feeds the
  // mutation stream a screen reader rebuilds its buffer on.
  function sayAsks(completed, total) {
    const said = `Asks ${completed}/${total}`;
    if (decisionsBtn.textContent !== said) decisionsBtn.textContent = said;
  }
  // The banner's reading of that one list. Refreshed from every signal that can change
  // it: a widget saying it has just taken an answer (lf-answered, which is also when the
  // page's own words change), and every poll, which is where the fold moves and where a
  // send that failed has its optimism taken back.
  let shortcutsOffered = false;
  let rowWalkOffered = false;
  function syncDecisions() {
    const decisions = openDecisions();
    const all = allDecisions();
    const unanswered = new Set(unansweredDecisions());
    const completed = all.filter((decision) => !unanswered.has(decision)).length;
    decisionsBtn.toggleAttribute(
      "data-lf-complete",
      all.length > 0 && completed === all.length,
    );
    // While the tray stands its button stands too, whatever the count just did — the
    // press that opened it has to be able to close it.
    showNews(decisionsBtn, decisionsOffered());
    sayAsks(completed, all.length);
    // Only while the tray is up: the count above is what a closed tray says, and these
    // rows are what an open one says. A closed tray reconciling a list on every poll is
    // work for a reader who cannot see it, and rows in a document nothing can press.
    if (openTray("decisions")) renderDecisions(all, unanswered);
    for (const { btn, label, n } of blanketAnswers(decisions)) {
      showNews(btn, Boolean(n));
      btn.textContent = `${label} all (${n})`;
    }
    // The a/A row stands on this list, so the surfaces reading it are repainted
    // where it changes — the rule showFab and showTray already keep for the words
    // they write. A capability change also moves the tray edge's machine-readable keys.
    const offered = decisionsOffered();
    const walkOffered = decisions.length > 0;
    if (offered !== shortcutsOffered || walkOffered !== rowWalkOffered) {
      shortcutsOffered = offered;
      rowWalkOffered = walkOffered;
      paintKeys();
    } else paintHere();
  }
  // An answer can also change what text the page has — a retired slot leaves it — so
  // marks are repainted from the same signal, and a comment on text the user just
  // removed says so at once rather than at the next poll.
  document.addEventListener("lf-answered", () => {
    syncDecisions();
    paintAnchors();
  });
  document.addEventListener("lf-actions", syncDecisions);
  // One row per active decision, reconciled on every signal that moves the list, the way the
  // leaves tray reconciles its own — rows kept in place rather than rebuilt, so a
  // repaint doesn't swap a row out from under a pressed pointer or drop focus inside it.
  //
  // Keyed by the decision's id and not by the element: a new version replaces every node on the
  // page, and the row for a question that survived the revision is the same row. That is
  // also what a press resolves through — the element this row stood for may be gone, and
  // the decision with that id is the one the reader means.
  //
  // A row says what kind of thing is asking and then the decision's own opening words, which is
  // itemSays — the same reading the thread panel labels an anchor with, so a row and a
  // comment on that decision say the same thing. Nothing here asks which widget it is: the kind
  // is the element's own word and the words are the element's own text, so the twelfth
  // widget gets a row that reads properly on the day it declares x-awaits.
  const decisionRowsById = new Map();
  // What the tray says when it is holding nothing, in the voice the thread panel's own
  // empty note uses: what is true, then what would fill it. A reader who opens Asks on a
  // page that is waiting on nobody was getting a blank panel, which says the same thing
  // as a tray that has failed to render — and the two are worth telling apart, since one
  // of them is the page being finished with them.
  //
  // The other half of the sentence is not a gesture, as it is next door: a reader makes
  // their own threads and does not make their own asks, so what it names is the agent.
  const emptyNote = el(
    "div",
    "lf-empty",
    "Nothing is waiting on you. A question the page needs an answer for appears " +
      "here when the agent asks one.",
  );
  function renderDecisions(
    decisions = allDecisions(),
    unanswered = new Set(unansweredDecisions()),
  ) {
    let anchor = null;
    if (!openTray("decisions")) {
      for (const [, row] of decisionRowsById) row.remove();
      decisionRowsById.clear();
      emptyNote.remove();
      return;
    }
    // Out of the way before the rows place themselves, so `firstElementChild` below is a
    // row or nothing and the note cannot become the thing a row is inserted after.
    emptyNote.remove();
    for (const decision of decisions) {
      let row = decisionRowsById.get(decision.id);
      if (!row) {
        row = el("button", "lf-decisions-row");
        row.type = "button";
        // The attribute that already means "this chrome belongs to that decision" (decisionPlace),
        // so focus landing on a row is the reader standing in the decision it names, and the
        // ring, the walk's own measuring point and the mark all follow with nothing added.
        row.setAttribute(DECISION_AT, decision.id);
        row.append(
          el("span", "lf-decisions-kind"),
          el("span", "lf-decisions-says"),
          el("span", "lf-decisions-answer"),
        );
        row.onclick = () => {
          const route = allDecisions();
          const to = route.find((candidate) => candidate.id === decision.id);
          if (to) goToDecision(to, route);
        };
        keys(row, "In the asks tray", [
          {
            id: "decision.open",
            keys: PRESS,
            does: "Go to this ask",
            line: "go to this ask",
          },
        ]);
        decisionRowsById.set(decision.id, row);
      }
      const [kind, says, answer] = row.querySelectorAll(
        ".lf-decisions-kind, .lf-decisions-says, .lf-decisions-answer",
      );
      const item = itemWord(decision);
      const word = item === "decision" ? "ask" : item;
      const said = itemSays(decision) || decision.id;
      const answered = !unanswered.has(decision);
      // Written only on change: an unchanged poll must not feed the mutation stream a
      // screen reader rebuilds its buffer on.
      if (kind.textContent !== word) kind.textContent = word;
      if (says.textContent !== said) says.textContent = said;
      const answerText = answered ? decisionAnswer(decisionSource(decision)) : "";
      if (answer.textContent !== answerText) answer.textContent = answerText;
      const answerState = answered ? "answered" : "open";
      if (row.dataset.lfAnswerState !== answerState)
        row.dataset.lfAnswerState = answerState;
      const account = `${word} · ${said}${answerText ? ` · ${answerText}` : ""}`;
      if (row.title !== account) row.title = account;
      const place = anchor
        ? anchor.nextElementSibling
        : decisionsList.firstElementChild;
      if (place !== row) decisionsList.insertBefore(row, place);
      anchor = row;
    }
    const live = new Set(decisions.map((a) => a.id));
    for (const [id, row] of decisionRowsById)
      if (!live.has(id)) {
        // A decision that leaves the active inventory takes its row with it, and may take
        // the focus too — for example, when a revision retires the source while the reader
        // is standing on its row. Hand focus to whatever now stands in its place rather
        // than letting it fall to the body, which is nowhere and takes the ring with it.
        const held = row.contains(document.activeElement);
        const next = row.nextElementSibling ?? row.previousElementSibling;
        row.remove();
        decisionRowsById.delete(id);
        if (held) (next ?? decisionsBtn).focus();
      }
    if (!decisions.length) decisionsList.append(emptyNote);
  }

  // The walk over what the page is waiting on the reader for. It wraps at both ends,
  // because decisions are a worklist rather than a document to read through: answering one takes
  // it out of the list, so forward is the direction that has somewhere to go, and a walk
  // that clamped there would strand them at the end of it.
  //
  // Somewhere inside the decision the reader can be stood: one within it, or one hoisted out of
  // it and pointing back (a suggestion's row is the column's child, so that it can hang in
  // the page margin). Landing on it rather than on the decision puts the reader on something
  // that works it, and Tab walks the rest of that decision's own controls from there.
  //
  // Focusable offered chrome: native buttons carry their tab stop implicitly, while the
  // selectable-control exception states one explicitly. Written as one `:is()` compound
  // rather than as two comma-separated alternatives, because standOn below prefixes it
  // with a descendant selector: a prefix binds to the first alternative of a selector
  // list only, so the bare list read as "a control inside this decision's row, or any
  // offered tab stop anywhere in the document" and the walk landed on the first control
  // on the page instead of the one it was sent to.
  const DECISION_CONTROL = ":is(button[data-lf-offer], [data-lf-offer][tabindex])";
  // Which decision such a control decides, where the widget hoisted it out of the element (the
  // attribute lf-suggestion writes on the row it hangs in the margin).
  const DECISION_ROW = "data-lf-for";
  // Chrome that stands *at* a decision without deciding it: the decisions tray's rows. Separate
  // from DECISION_ROW above, because the two say different things about the same element and
  // one of them has a consumer that must not confuse them — stepDecision looks through DECISION_ROW
  // for the control to put the reader on, and a row that merely points at the decision is not
  // that control. What they share is this: focus on either means the reader is standing at
  // that decision, which is the one question decisionPlace asks.
  const DECISION_AT = "data-lf-at";
  // The tab stop this walk lends a decision that holds nothing to work: such a decision has no box
  // in the tab order and the runtime writes it one — which is paint on the author's element,
  // and PAGE_PAINT_ATTRIBUTES is the whole of what the runtime may leave standing there (a
  // `tabindex` in it would blind the replay signature to an authored one). So the lend lasts
  // exactly as long as the ring it goes with: the walk hands the stop over as it moves, and
  // markHere takes it back when the reader leaves.
  //
  // One function for both ends of it, because written as statements at each end the walk's
  // half only ever wrote — it took the last lend's reference with it and left the stop
  // standing. Two control-less decisions in a row is all it took, and the walk in the shipped
  // examples goes through two: stepping off a task left it wearing a tab stop that nothing
  // afterwards was ever going to remove.
  let decisionLent = null;
  function lend(decision) {
    if (decisionLent === decision) return;
    decisionLent?.removeAttribute("tabindex");
    decisionLent = decision;
    if (decision) decision.tabIndex = -1;
  }
  // Where the walk last left off. Not the same question as where the reader is standing,
  // though one answer used to serve both: the ring said where they were and the walk read
  // its own last landing off it. A reader who has pressed the banner's Asks button is
  // standing in the banner, and the ring is rightly gone from the page — leaving the walk
  // with nothing to step from but whatever happens to be on screen, which would send the
  // next press back up the page.
  let landed = null;
  // An answered Ask normally keeps semantic focus on its own element after a tray-row
  // arrival. A boxless answered widget cannot: its visible revision control is the only
  // focus target. Remember that exact target for this arrival, and only while it still
  // owns focus, so returning to the same control ordinarily does not promote it from its
  // own local meaning to the whole Ask again.
  let reviewedThrough = null;
  function hasReviewedFocus() {
    if (reviewedThrough?.isConnected && focused() === reviewedThrough) return true;
    reviewedThrough = null;
    return false;
  }
  // A place in the document, stated as the decision it belongs to wherever it belongs to one: a
  // control hoisted out of its decision and pointing back at it stands for that decision and not for
  // the block it was hung beside, or stepping back from a suggestion's own ✓ Accept would
  // land on the suggestion the reader is already standing on.
  function decisionPlace(node) {
    const el = node.nodeType === 1 ? node : node.parentElement;
    const row = el?.closest(`[${DECISION_ROW}], [${DECISION_AT}]`);
    const at = row?.getAttribute(DECISION_ROW) ?? row?.getAttribute(DECISION_AT);
    return (at && elementById(at)) ?? node;
  }
  // The decision the reader is standing in: the one holding the focus, or the one a control
  // hoisted into the margin decides. The innermost of them, a decision being able to hold
  // another (a question inside a suggestion's lf-new) — the list answers in document order,
  // so the last container in the list is the nearest one.
  //
  // The unanswered decisions rather than the reader's list, because standing in a question is
  // about where the reader is working and not about what they owe. The two part on a widget
  // whose own seat is mid-conversation with the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the reader was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the reader did moved either. An
  // answered decision leaves both worklists but stays in the active inventory: the
  // Asks tray can return the reader to it, and standing there restores the same numeric
  // action route so they can revise the recorded answer.
  //
  // Document focus rather than the inner control, for the reason decisionPosition gives: a
  // control staged in a shadow tree retargets to its host, and the host is the place in the
  // document this wants.
  function standingIn() {
    const held = documentFocused();
    if (!held || held === document.body) return null;
    const place = decisionPlace(held);
    const unanswered = unansweredDecisions().findLast(
      (decision) => decision === place || decision.contains(place),
    );
    if (unanswered) return unanswered;
    // An answered Ask is standing only on the explicit review route: its tray row or
    // the decision element that row lands on. A widget host can be the document's
    // retargeted focus without being the decision itself; treating that as an arrival
    // would make an ordinary click on a chosen option steal the option's own semantics.
    const answered = allDecisions().findLast(
      (decision) => decision === place || decision.contains(place),
    );
    if (!answered) return null;
    return held === answered || held.closest(".lf-decisions-row") || hasReviewedFocus()
      ? answered
      : null;
  }

  // The Ask-local numeric map. The widget contributes the exact controls that work its
  // decision source; this view owns only their stable addresses while semantic focus is
  // on the Ask itself. Once Tab enters a control, the widget's nearer scope and native
  // keys take over. The deep focus reading matters for a shadow widget: document focus is
  // retargeted to its host, but a control inside it is still not the Ask itself.
  function actionDecision() {
    const decision = standingIn();
    return decision && (focused() === decision || hasReviewedFocus()) ? decision : null;
  }
  const availableActions = () => {
    const decision = actionDecision();
    if (!decision) return [];
    return decisionActions(decisionSource(decision))
      .filter(
        ({ control }) =>
          control.isConnected &&
          !control.matches(":disabled") &&
          control.getAttribute("aria-disabled") !== "true" &&
          control.getAttribute("aria-busy") !== "true",
      )
      .slice(0, MAX_NUMBERED_ADDRESSES);
  };
  const actionBindings = () => availableActions().map((_, index) => String(index + 1));
  const actionLabels = () => availableActions().map(({ label }) => label);
  const actionRow = {
    id: "decision.activate-nth",
    keys: actionBindings,
    label: () => {
      const count = actionBindings().length;
      return count > 1 ? `1–${count}` : "1";
    },
    does: () =>
      `Activate an action in this Ask: ${actionLabels()
        .map((label, index) => `${index + 1} ${label}`)
        .join("; ")}`,
    line: () => actionLabels().join(" / "),
    when: () => availableActions().length > 0,
    run: (binding) => availableActions()[Number(binding) - 1]?.control.click(),
  };

  // The chips are an eye's projection of the same row. A widget that already owns an
  // address face lends that face and its exact placement; other actions get chrome at
  // the visible Button's corner. Off-screen actions keep their working address and name
  // on the key line but wear no chip. A nearer keyboard layer suppresses both the row and
  // these chips through actionReachable, so a digit never stays painted after a chord,
  // text box, or modal has taken it.
  const wornAddresses = new Map();
  function restoreAddress(address, { display, priority }) {
    address.removeAttribute("data-lf-ask-address");
    if (display) address.style.setProperty("display", display, priority);
    else address.style.removeProperty("display");
  }
  function clearWornAddresses() {
    for (const [address, previous] of wornAddresses) restoreAddress(address, previous);
    wornAddresses.clear();
  }
  function paintActionAddresses() {
    clearWornAddresses();
    const actions = availableActions();
    if (!actionReachable() || !bindings(actionRow).length) {
      actionLayer.replaceChildren();
      return;
    }
    const placement = createAddressPlacement({
      banner,
      keylineEl,
      startsAt: shownRect,
    });

    // Reuse a widget's page-local address where it has one. Besides preserving the
    // widget's own card-versus-row alignment, leaving this face in the page's stack keeps
    // the fixed key line above it. Hide a face that has no clear visible box, just as the
    // general address pass drops a route chip where the screen cannot say it safely.
    for (const { address } of actions) {
      if (!address?.isConnected) continue;
      const previous = {
        display: address.style.getPropertyValue("display"),
        priority: address.style.getPropertyPriority("display"),
      };
      address.setAttribute("data-lf-ask-address", "");
      address.style.setProperty("display", "block", "important");
      const box = address.checkVisibility() && placement.visibleBox(address);
      if (!placement.reserve(box)) {
        restoreAddress(address, previous);
        continue;
      }
      wornAddresses.set(address, previous);
    }

    const chips = [];
    for (const [index, { control, address }] of actions.entries()) {
      if (address) continue;
      const presented = presentedActionControl(control);
      if (!presented.checkVisibility()) continue;
      const box = placement.visibleBox(presented);
      if (!box) continue;
      const chip = el("span", "lf-address lf-ask-address", String(index + 1));
      chip.setAttribute("aria-hidden", "true");
      chip.style.left = `${box.left}px`;
      chip.style.top = `${box.top}px`;
      chips.push(chip);
    }
    placement.paint(actionLayer, chips);
  }
  watchDecisionActions(() => {
    syncDecisions();
    paintKeys();
  });
  addEventListener("scroll", () => actionReachable() && paintHere(), {
    capture: true,
    passive: true,
  });
  addEventListener("resize", () => actionReachable() && paintHere());
  // The ring that says so, painted from the focus rather than written where the reader was
  // put. The walk used to write it, and it then said where the walk had left them rather
  // than where they were: click away, work in the panel, come back tomorrow, and a decision
  // nobody was standing in went on wearing "you are here". Every other way into a decision —
  // Tab, a click on one of its controls — left the ring somewhere else entirely, so the
  // same place was marked or not by how the reader had reached it.
  //
  // Keyed on focus and not on :focus-visible, which is a claim about the last input rather
  // than about where the reader is: a tray row's press lands the focus by script after a
  // click, and the decision it brought the reader to would wear nothing at all.
  //
  // The decision wears it, and so does every box it shows through (shownParts): the decision is
  // what carries the id captureView writes down and the place decisionStep measures from,
  // while an outline needs a box to hang on. Every widget in the vocabulary draws one
  // box now — the wrapper that declined to took a form instead, in its own stylesheet,
  // after the ring went out over its pieces and read as two boxes touching rather than
  // as the one decision the reader is standing in — so on shipped pages the parts are the
  // decision itself, and the fallback answers the wrapper any page can still style boxless
  // in a line, the same way the thread's mark does (paintAnchors).
  //
  // The tray's row for the decision is a second surface showing this one fact, so it is
  // painted from this one reading rather than from a mark the tray keeps for itself —
  // and the ring is the chrome's as much as the page's (the [data-lf-decision] rule in the
  // stylesheet is written against the attribute, not against the page), so wearing the
  // attribute is the whole of what the row needs.
  function markHere() {
    const here = standingIn();
    const row = here && decisionsPanel.querySelector(`[${DECISION_AT}="${here.id}"]`);
    const wearing = new Set(
      here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
    );
    // A walk that runs past the foot of an open tray leaves its mark off screen, which is
    // the tray saying nothing exactly while the reader is using it. `nearest` so a row
    // already in view moves nothing.
    if (row && openTray("decisions")) row.scrollIntoView({ block: "nearest" });
    for (const marked of document.querySelectorAll(
      `[${PAGE_PAINT_ATTRIBUTE.decision}]`,
    ))
      if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.decision);
    // A control-less request can borrow its own tab stop while the broader x-decision
    // region wears the ring. Keep that stop until the reader leaves the region.
    const holder = here && decisionSource(here);
    if (decisionLent && decisionLent !== here && decisionLent !== holder) lend(null);
    for (const marked of wearing)
      marked.setAttribute(PAGE_PAINT_ATTRIBUTE.decision, "1");
    paintActionAddresses();
  }
  // Where the walk measures from: where the reader is standing, rather than where the walk
  // last put them. It carried an id of its own, so every walk the reader had not made with
  // this key started at the top of the page — select a paragraph and press `d` and you were
  // taken back past everything you had read, and so was anyone scrolled halfway down
  // pressing it for the first time. Space page travel measures from the scroll position and t/T from the
  // focused thread; this measured from its own memory, which is the one place the reader
  // isn't.
  //
  // Read in the order of how directly each says where they are: what they have focused,
  // what they have selected, where this walk last left off (`landed`), and what they are
  // reading. Every one of them can be absent, and then the first decision is the only answer
  // there is.
  //
  // Document focus rather than the inner control: a control staged in a shadow tree
  // retargets to its host, which is exactly what this question wants — a place in the
  // document to measure the decisions against, not the control the register would dispatch to.
  function decisionPosition() {
    const held = documentFocused();
    // The banner stands over the page rather than in it, and its controls are addresses
    // the reader holds from wherever they are. A reader who pressed the Asks button is
    // standing on it, so measuring from it would send the next press back to the top.
    if (held && held !== document.body && !banner.contains(held))
      return decisionPlace(held);
    const sel = getSelection();
    // A caret counts here, where the composer's reading of the selection (pageSelection)
    // wants words to quote: a click that placed one is the reader saying where they are.
    if (sel?.focusNode && !inChrome(sel.focusNode)) return decisionPlace(sel.focusNode);
    // A landing whose element a later version dropped is no place at all, and
    // compareDocumentPosition against a detached node answers about no document.
    return (landed?.isConnected ? landed : null) ?? readingBlock();
  }
  // The decision `dir` steps to from there. Document position rather than an index into the
  // list, because the reader's place is a place and not a row: a decision holding it is the one
  // they are standing on, so it is what they step off rather than what they step to.
  function decisionStep(decisions, dir) {
    const here = decisionPosition();
    if (!here) return dir > 0 ? decisions[0] : decisions.at(-1);
    const side =
      dir > 0 ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING;
    const reach = decisions.filter((decision) => {
      const rel = here.compareDocumentPosition(decision);
      return !(rel & Node.DOCUMENT_POSITION_CONTAINS) && rel & side;
    });
    return dir > 0 ? (reach[0] ?? decisions[0]) : (reach.at(-1) ?? decisions.at(-1));
  }
  // Putting the reader back on the control they were working when a widget rebuilt itself
  // underneath them (rebuild): the control that works this decision — one inside it, or
  // one the widget hoisted into the margin and pointed back at it — or the decision
  // itself, lent a tab stop where it holds nothing to work.
  //
  // This is not where an arrival lands, and the two parted when the scroll and the focus
  // were measured against each other. Arrival puts the decision's opening at the top of
  // the window, and the first control that answers it is as far down the decision as its
  // context and evidence are long: measured on the shipped corpus at 1200x900, the heading
  // stood at 54px and the pick the walk focused ran from 847 to 1107 in a 900px window. So
  // the reader was told to look at one thing and stood on another, off the bottom of the
  // screen, and their next Enter would have worked a control they could not see.
  function standOn(el, review = false) {
    const source = decisionSource(el);
    const control =
      source.querySelector(DECISION_CONTROL) ??
      document.querySelector(`[${DECISION_ROW}="${source.id}"] ${DECISION_CONTROL}`);
    if (!control) lend(source);
    const target = control ?? source;
    if (review) reviewedThrough = target;
    focusForNavigation(target);
  }
  // Where an arrival lands: on the decision, which is what the scroll has just brought to
  // the top of the window and what the ring is about to name. Its controls are then the
  // next Tab stops, in the order they are written, because a tab stop at `tabindex: -1`
  // keeps its place in document order and everything inside a decision comes after it.
  //
  // The decision remains the semantic focus. Its widget-contributed actions are already
  // directly addressable there; Tab is the complementary path into the widget's own
  // local scope for walking or inspecting its controls.
  function arriveAt(decision, review = false) {
    reviewedThrough = review ? decision : null;
    decision.focus({ preventScroll: true });
    if (decision.matches(":focus")) return;
    lend(decision);
    decision.focus({ preventScroll: true });
    if (decision.matches(":focus")) return;
    // A decision the page styles boxless generates nothing to stand on, and a lent stop
    // does not change that. There the control that answers it is the only place the
    // reader can be, which is where every arrival used to land.
    lend(null);
    standOn(decision, review);
  }

  // The screen the reader can use, and the distance two boxes stand apart in it. The
  // clearance is the scroller's own declared scroll-padding, where it already says how
  // much of its top edge the banner stands over, rather than a second copy of that number
  // kept here.
  const clearanceOf = (box) => parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const HEADING = "h1,h2,h3,h4,h5,h6";

  // Where the reader arrives at a page decision: the region whose start has to be in front
  // of them for the question to make sense. A widget declaring x-decision states its own —
  // one heading, then the context and evidence, then the control — and this walk is handed
  // that region rather than the widget inside it, so its arrival is simply its start.
  //
  // The kind that most needs a region is the kind that cannot declare one. A suggestion is
  // an edit to a phrase, and what explains it is the sentence it stands in and the heading
  // over that — so it can never satisfy "an ask must name itself without context outside
  // the ask", and no x-decision can be written round it. Landing on the change alone put
  // its own top edge under the banner and took that sentence with it: the reader arrived
  // at ✓ Accept with nothing on screen saying what they were accepting. So where the
  // author has not declared a region, the document supplies one in the shape a declared
  // region has.
  //
  // Candidates widest first — the heading titling this part of the document, then the
  // block the change stands in, or, for a change that is its own block, the block before
  // it. The first whose start still leaves the decision's own foot on screen wins, so a
  // region never grows past what the reader takes in at once and a decision with nothing
  // that fits keeps the landing this walk always gave it. That bound is what lets the
  // widest candidate go first: a heading a long way up fails to fit, rather than needing a
  // rule about how far up is too far.
  function arrivalRegion(decision, box) {
    if (registry[decision.localName]?.["x-decision"]) return decision;
    const room = shownBox(box).height - clearanceOf(box);
    // A region has to be somewhere the reader can be taken. An element generating no box
    // measures (0,0) at the document's origin, which is not a degenerate answer but a
    // wrong one naming the top of the page (geometry.js says so at shownBox): a hidden
    // paragraph before the change fits every time, and the press then scrolls the page up
    // by the banner's clearance instead of travelling to the ask.
    // A region also has to begin at or above the change: it is the run-up to it, and one
    // starting below would be a region the change is not in. Document order alone does
    // not promise that — a preceding block can be painted lower — and the span such a
    // region measures is negative, which fits every screen there is.
    const fits = (region) => {
      if (!region) return false;
      const start = shownBox(region);
      const target = shownBox(decision);
      return (
        start.height > 0 && start.top <= target.top && target.bottom - start.top <= room
      );
    };
    // The blocks before this one that are about the same part of the document: the two
    // stand under one container, which is what "the heading over this" means and is the
    // whole of the bound the search needs. Without it the nearest preceding heading can
    // be the previous ask's own — two asks written one after another is the ordinary way
    // to write them — and the reader arrives reading the wrong question as the context
    // for this one. It also stops the walk at the section the decision is in rather than
    // running back through the whole document to find a heading.
    //
    // An ancestor both contains and precedes, so the block holding an inline change is
    // asked for by name and excluded here — or the walk backwards would stop at the
    // sentence the change is already inside and call it the one before.
    // The document's own blocks, in document order, which is what picking the last
    // heading and the nearest block both rest on. `pageQueryAll` would reach a widget's
    // declared shadow tree as well, and it concatenates each root's answer rather than
    // composing one order, so the last heading it reported could be from another tree
    // entirely — a worse answer than the one this misses. The crossing worth having is
    // on the two questions asked of each block: `containsAcross` for the container, and
    // the host climb below for the order, which together let a decision staged inside a
    // shadow tree take the heading standing over its host.
    //
    // `hidden` goes with `inChrome`: content-visibility leaves real rects behind, so a
    // block behind a shut disclosure otherwise measures like one the reader can see.
    //
    // Order is asked of the decision as the block's own tree sees it, which for a
    // decision staged in a shadow tree is its host and not the decision. Two nodes in
    // different roots are DISCONNECTED, and the direction bit that comes with it is
    // arbitrary-but-consistent rather than positional: Chrome answers PRECEDING for every
    // block in the document, whichever side of the host it stands. Asked straight, the
    // filter therefore kept the blocks after such a decision too, and the last heading in
    // the container won — the wrong-question arrival this bound exists to remove, in the
    // one shape the crossing above was written to serve.
    const seenBy = (block) => {
      const root = block.getRootNode();
      let node = decision;
      while (node && node.getRootNode() !== root)
        node = node.getRootNode().host ?? null;
      return node;
    };
    const before = [...document.querySelectorAll(TEXT_BLOCK)].filter((block) => {
      const from = seenBy(block);
      return (
        from &&
        !inChrome(block) &&
        !block.closest("[hidden]") &&
        !containsAcross(block, decision) &&
        block.parentElement &&
        containsAcross(block.parentElement, decision) &&
        from.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING
      );
    });
    const heading = before.findLast((block) => block.matches(HEADING));
    return (
      [heading, closestAcross(decision, TEXT_BLOCK) ?? before.at(-1)].find(fits) ??
      decision
    );
  }

  // The arrival the reader already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the ask and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the decision itself is readable is `readableDestination`'s question, asked of
  // every edge through whatever clips it — a decision half cut off by a board's own
  // scroller is not in front of the reader for having a box inside the window. This adds
  // the one thing that reading cannot know: the arrival is the region's start, so the
  // start has to be standing clear of the banner too.
  function framed(region, decision, box) {
    return (
      readableDestination(decision) &&
      shownBox(region).top >= shownBox(box).top + clearanceOf(box)
    );
  }

  // Standing on one decision: what d and D do once they have decided which, and what a press on
  // a tray row does having been told outright. One function because it is one act — a
  // second would be a second answer to "how do I put the reader on a decision", and the two
  // would drift the first time either the reveal or the focus rule changed.
  //
  // The list comes with the decision, because the announcement names a place in it and the caller
  // is the one that knows which list it walked: the walk's own or the tray's.
  function goToDecision(next, decisions) {
    // A thread's decision lives in the panel, which has no geometry while closed — the
    // same reason reveal() opens a settled group before the scroll.
    if (inChrome(next) && !panelIsOpen()) setPanel(true);
    // A tray beside the page stays standing as a working index. A covering tray has
    // become the whole visible surface, so selecting a page destination closes it
    // before the reveal and focus land; otherwise the correct navigation happens
    // invisibly behind the very sheet that offered it.
    if (!inChrome(next) && openTray("decisions") && trayCovers()) closeTray();
    reveal(next); // a settled group or an inactive tab has no geometry until it opens
    const source = decisionSource(next);
    if (source !== next) reveal(source); // let the answering widget settle its own chrome
    landed = next;
    // The ring follows: the focus move is what paints it, so the walk says where to stand
    // and markHere says where the reader is standing, rather than both saying the second.
    arriveAt(next, !unansweredDecisions().includes(next));
    // A page Decision starts below the banner so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the region an author declared,
    // or the one the document supplies for a change that cannot declare one. A thread
    // Decision is in the panel's own list, whose arrival stays centred in that region.
    // Which box either travel moves is the travel's own question (scrollerFor) rather than
    // a second one asked here.
    //
    // A page arrival the reader already has is left alone. The ring and the focus have
    // moved to the next ask, which is the whole of what this press had left to say.
    if (inChrome(next)) scrollToElement(next, scrollBehavior(), "center");
    else {
      const region = arrivalRegion(next, pageScroller);
      if (!framed(region, next, pageScroller)) {
        // The decision's own box first, which is the only pass that moves a scroller
        // other than the page's: the placement below moves whichever box scrolls the
        // region, and for a region out on the page that is never the board's own
        // scroller. Handing that placement the region alone left a decision inside a
        // card unscrolled in its card, with the ring and focus on a change the reader
        // could not see. `nearest` is a request to reveal only, which is exactly
        // what this needs and what the placement then builds on.
        scrollToElement(next, "instant", "nearest");
        scrollToElement(region, scrollBehavior(), "start");
      }
    }
    const state = unansweredDecisions().includes(next) ? "waiting on you" : "answered";
    announce(`${decisions.indexOf(next) + 1} of ${decisions.length} ${state}`);
  }
  function stepDecision(dir) {
    const decisions = openDecisions();
    if (!decisions.length) return; // never: the key and the control are live only with decisions
    goToDecision(decisionStep(decisions, dir), decisions);
  }

  const landedAt = () => landed;
  const setLanded = (value) => (landed = value);
  return {
    DECISION_CONTROL,
    DECISION_ROW,
    actionRow,
    decisionPlace,
    buildBulkAnswers,
    goToDecision,
    landedAt,
    markHere,
    renderDecisions,
    setLanded,
    standOn,
    standingIn,
    stepDecision,
    syncDecisions,
  };
}
