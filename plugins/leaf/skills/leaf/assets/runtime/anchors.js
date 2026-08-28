import { clippedRect, shownBox, shownParts, shownRect } from "./geometry.js";
import { moveScrollerBy } from "./scrolling.js";

/* Anchor resolution, painting, and anchor-specific travel. */
let publishedAnchors;
export const itemWord = (...args) => publishedAnchors.itemWord(...args);
// Anchors are shallow records of primitive coordinates. Compare the complete records:
// reading only the left operand's keys made a whole-visual anchor equal the part anchor
// that extended it, but not the other way around.
export const sameAnchor = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const left = Object.keys(a).sort();
  const right = Object.keys(b).sort();
  return (
    left.length === right.length &&
    left.every((key, index) => key === right[index] && a[key] === b[key])
  );
};

export function createAnchors(dependencies) {
  const {
    DATUM,
    scrollBehavior,
    actionAnchor,
    activateVisual,
    aimBox,
    aimIsOn,
    aimedItem,
    anchorLabel,
    anchorsReady,
    bareReaction,
    blockAt,
    buildThreads,
    closestAcross,
    composerAbout,
    composerAnchor,
    composerIsOpen,
    composerQuote,
    containsAcross,
    cut,
    designIsOn,
    designName,
    designTarget,
    el,
    elementById,
    elementFromPointAcross,
    elementOver,
    findQuote,
    focusedThreadOf,
    inChrome,
    inUi,
    inspectEl,
    offer,
    pageQueryAll,
    pageScroller,
    pageText,
    pageWords,
    paintThreadQuotes,
    panel,
    pointerAt,
    quoteFrom,
    queueLegend,
    rangeOf,
    refreshAction,
    registry,
    reveal,
    scrollerFor,
    setPanel,
    settledAway,
    tagsDeclaring,
    textNodesUnder,
    threadsBox,
    under,
    withdraw,
    worksSelector,
  } = dependencies;

  // ---------- anchors ----------
  // An anchor names a passage: a section id, a quote, or both. Resolving one is the only
  // place the page is searched, so the three things that read a passage back — a thread's
  // mark, the composer's own, and the reading position a version change rides on — cannot
  // disagree about where to look. A quoteless anchor has no text to paint and resolves to
  // its element instead.
  // The search always reads the whole document — the same text the capture wrote the
  // neighbours from — and the section the anchor names filters where a candidate may sit.
  // A section the page no longer has filters nothing, so the quote is still looked for
  // everywhere, which is all a stale section ever meant.
  // Which element an anchor names, asked in one place: the element it resolves to when it
  // carries no quote, the subtree a candidate has to sit inside when it does, and the holder
  // of the line saying a passage carries a comment are all this question.
  const sectionOf = (anchor) => (anchor.section ? elementById(anchor.section) : null);

  // A generated picture part keeps two identities. The authored widget is its semantic
  // seat; the module supplies only the current box that one stable authored token paints.
  // Core verifies the token against the declaration before trusting either module method,
  // so a renderer's generated id never escapes into the event log.
  const visualPartAttribute = (visual) => {
    const declaration = registry[visual?.localName]?.["x-visual"];
    return declaration && typeof declaration === "object" ? declaration.parts : null;
  };
  const declaredVisualParts = (visual) => {
    const attribute = visualPartAttribute(visual);
    const value = attribute ? visual?.getAttribute(attribute) : "";
    return new Set(value?.trim().split(/\s+/).filter(Boolean) ?? []);
  };
  function visualPart(visual, part) {
    if (!declaredVisualParts(visual).has(part)) return null;
    const answer = visual.lfVisualPart?.(part);
    const element = answer?.element;
    if (!(element instanceof Element) || !containsAcross(visual, element)) return null;
    return { part, element, label: answer.label || part };
  }
  function visualPartAt(visual, target) {
    const part = visual?.lfVisualPartAt?.(target);
    return typeof part === "string" ? visualPart(visual, part) : null;
  }
  const visualPartLabel = (visual, part) => visualPart(visual, part)?.label ?? null;
  const declaredVisualSelector = () =>
    [...tagsDeclaring((entry) => entry["x-visual"])].join(",");
  const genericVisualSelector = "svg, img, figure";
  const visualSelector = () =>
    [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");
  const interactiveSelector = `${worksSelector},[data-lf-offer]`;
  const parentAcross = (element) =>
    element?.parentElement ?? element?.getRootNode()?.host ?? null;
  const outermostAcross = (element, selector) => {
    for (let parent = parentAcross(element); parent;) {
      const outer = closestAcross(parent, selector);
      if (!outer) break;
      element = outer;
      parent = parentAcross(element);
    }
    return element;
  };
  const unclaimedVisualGesture = (target) =>
    !inChrome(target) && !inUi(target) && !closestAcross(target, interactiveSelector);
  // A declared provider owns every hit inside it, including an inner svg wrapped by a
  // generic figure. Without one, the outermost ordinary picture is the target. Generated
  // ids remain implementation details; the nearest authored id is the durable seat.
  function visualAt(target, { unclaimed = true } = {}) {
    if (unclaimed && !unclaimedVisualGesture(target)) return null;
    const declared = declaredVisualSelector();
    let element = declared ? closestAcross(target, declared) : null;
    if (element) element = outermostAcross(element, declared);
    else {
      element = closestAcross(target, genericVisualSelector);
      if (element) element = outermostAcross(element, genericVisualSelector);
      const providers =
        element && declared ? [...element.querySelectorAll(declared)] : [];
      // A figure holding one declared visual is its semantic caption/frame. Delegating
      // the wrapper to that provider gives its padding, caption, drawing, and keyboard
      // proxy one target. A figure holding several visuals remains a target of its own.
      if (providers.length === 1 && unclaimedVisualGesture(providers[0]))
        element = providers[0];
    }
    if (!element) return null;
    const seat = closestAcross(element, '[id]:not(.lf-ui):not([id^="lf-"])');
    return seat ? { element, id: seat.id, part: visualPartAt(element, target) } : null;
  }

  // Pointer activation may use the picture itself. Keyboard activation uses controls the
  // runtime owns beside it, so generated provider markup keeps its own roles and remains
  // clean when the live layer is removed from an exported copy. Each visual exposes its
  // whole target and, when declared, each stable part.
  const visualActionHolders = new WeakMap();
  const visualActionAnchor = (anchor) =>
    pageQueryAll(".lf-visual-action").find((control) =>
      sameAnchor(control.lfAnchor, anchor),
    ) ?? null;
  // A proxy stands after the thing whose visibility controls the picture. In particular,
  // putting it inside a closed details makes the control impossible to focus, so the
  // disclosure is the stable seat and focusing the proxy can reveal the target inside it.
  // Shadow renderers share their host as a seat; one holder there avoids moving several
  // sibling holders past one another on every paint.
  function visualActionSeat(candidate) {
    let seat =
      candidate.getRootNode() instanceof ShadowRoot
        ? candidate.getRootNode().host
        : candidate;
    for (let current = seat; current; current = parentAcross(current))
      if (current.matches?.("details")) seat = current;
    return seat;
  }
  function prepareVisualActions() {
    const groups = new Map();
    const claimed = [];
    const kept = new Set();
    for (const candidate of pageQueryAll(visualSelector())) {
      const found = visualAt(candidate);
      if (!found || found.element !== candidate) continue;
      const targets = [
        {
          anchor: { section: found.id },
          label: anchorLabel({ section: found.id }).replace(/^§\s*/, "") || found.id,
        },
        ...[...declaredVisualParts(candidate)].flatMap((token) => {
          const part = visualPart(candidate, token);
          return part && unclaimedVisualGesture(part.element)
            ? [
                {
                  anchor: { section: found.id, visual: token },
                  label: part.label,
                },
              ]
            : [];
        }),
      ];
      const seat = visualActionSeat(candidate);
      let group = groups.get(seat);
      if (!group) {
        group = [];
        groups.set(seat, group);
      }
      for (const target of targets)
        if (!claimed.some((anchor) => sameAnchor(anchor, target.anchor))) {
          claimed.push(target.anchor);
          group.push(target);
        }
    }
    for (const [seat, targets] of groups) {
      if (!targets.length) continue;
      let record = visualActionHolders.get(seat);
      if (!record?.holder.isConnected) {
        record = { holder: offer("span", "lf-visual-actions") };
        visualActionHolders.set(seat, record);
      }
      const { holder } = record;
      const unused = new Set(holder.children);
      const controls = targets.map(({ anchor, label }) => {
        let control = [...unused].find((child) => sameAnchor(child.lfAnchor, anchor));
        if (!control) {
          control = offer("button", "lf-visual-action lf-quiet");
          control.onfocus = () => {
            let current = resolveAnchor(control.lfAnchor, pageText());
            let element = current?.marks?.[0] ?? current?.element;
            if (!element) return;
            reveal(element);
            current = resolveAnchor(control.lfAnchor, pageText());
            element = current?.marks?.[0] ?? current?.element;
            element?.scrollIntoView({
              behavior: "instant",
              block: "nearest",
              inline: "nearest",
            });
          };
          control.onclick = () => activateVisual(control.lfAnchor, control);
        }
        unused.delete(control);
        control.lfAnchor = anchor;
        const name = `React or comment on ${label}`;
        if (control.textContent !== name) control.textContent = name;
        return control;
      });
      for (const control of unused) control.remove();
      controls.forEach((control, index) => {
        if (holder.children[index] !== control)
          holder.insertBefore(control, holder.children[index] ?? null);
      });
      if (seat.nextSibling !== holder) seat.after(holder);
      kept.add(holder);
    }
    for (const holder of pageQueryAll(".lf-visual-actions"))
      if (!kept.has(holder)) holder.remove();
  }

  // ---------- pointing at an item ----------
  // One gesture reaches any item: ⌥-click — direct aim, no selection, no chrome, and the
  // only route to an item whose words are all inside controls. A plain click reaches a
  // visual when it did not finish a passage selection. Two more routes were tried and
  // cut. A margin rule raised by hovering was too strong for what it offered and sat at
  // the item's own left edge, which is the page's margin only when that item happens to
  // be left-aligned. A row of chips beside the 💬 offered the selection's enclosing chain
  // ("⬚ paragraph", "⬚ section") — a correction nobody had asked for, paid in chrome
  // beside every selection a user made.
  //
  // A whole item writes {section: <id>} with no quote. A declared picture part adds its
  // authored `visual` token; the section remains the durable seat. Both coordinates come
  // from markup rather than from whatever ids a renderer generated for this load.
  //
  // An item is an element the author gave an id, outside the runtime's own layer and
  // outside the panel (a reply's frozen widget markup carries ids of its own). `version
  // check` holds every id across versions, which is exactly why an anchor naming one
  // survives a rewrite that takes a quote down with it. An id under the runtime's own
  // prefix is not the author's — a module coins one for what it draws (a diagram's svg
  // wears `lf-mermaid-N`, numbered by draw order) — so an anchor on it names nothing a
  // version holds and something the next load may number differently. The item is the
  // element around it unless its declaration maps the generated box to an authored token.
  const ITEM = '[id]:not(.lf-ui):not([id^="lf-"])';
  // Whether an element is an item: what the aim walks up to, and what the legend draws a
  // box for — one predicate, so the two cannot disagree about what is on the page. Never
  // one the user's decision settled off the page: the aim's paint already refused those,
  // and a press answered by a different predicate anchored a composer to a retired
  // element — a box about nothing, promised by nothing. And never one inside a widget
  // that renders as a picture (x-visual): a diagram's nodes carry the ids its renderer
  // coined — `root-1`, `actor0`, under no prefix of ours — and `itemAt` must never return
  // one. The visual-part provider is the only route that may turn that generated box
  // into an authored coordinate.
  function isItem(at) {
    if (!at.matches(ITEM) || inChrome(at) || inUi(at) || settledAway(at)) return false;
    const visual = tagsDeclaring((e) => e["x-visual"]).join(",");
    return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
  }
  // The innermost item: a card rather than its column, the column rather than the board —
  // the smallest thing under the pointer is the thing pointed at. The walk continues
  // upward past what is not one, because the enclosing item is what is on screen.
  function itemAt(node) {
    let at = node?.nodeType === 1 ? node : node?.parentElement;
    for (; at; at = at.parentElement) if (isItem(at)) return at;
    return null;
  }
  // What to call an item, in a word the user reads beside a thread's § label. A widget
  // names itself: its tag minus the prefix is already the word the vocabulary chose
  // ("card", "option", "column"), so the twelfth widget gets a name here without core
  // hearing about it.
  //
  // The page's own elements have no such word. A tag is markup rather than English, and a
  // label reading "§ p · …" over ordinary prose names the thing to a browser and to nobody
  // else. So HTML's tags get the nouns a reader would use, and an unlisted one falls back
  // to its tag, which is worse than a word and better than nothing.
  const HTML_WORDS = {
    // Every one of these is a control the platform gives keys to and no letters — a radio,
    // a checkbox, a slider, a colour or file button. The ones that take letters never reach
    // this reading, the typing scope having claimed the key before the page is asked, so
    // there is no field here for "control" to misname. Worth a word at all because `c` names
    // what it is about, and a reader standing on a toggle was told "the input".
    input: "control",
    select: "control",
    button: "control",
    p: "paragraph",
    li: "item",
    tr: "row",
    td: "cell",
    th: "cell",
    figure: "figure",
    blockquote: "quote",
    pre: "block",
    section: "section",
    article: "section",
    aside: "aside",
    ul: "list",
    ol: "list",
    dl: "list",
    table: "table",
    details: "note",
    h1: "heading",
    h2: "heading",
    h3: "heading",
    h4: "heading",
    h5: "heading",
    h6: "heading",
  };
  function itemWord(item) {
    if (!item) return "";
    const tag = item.tagName.toLowerCase();
    // A widget whose kind is not its tag says which it is. Three shapes of change are all
    // <lf-suggestion>, and naming each of them by the tag put a deletion on the asks tray
    // under the words it proposed to remove, reading exactly like the insertion above it.
    // Asked only where an entry says there is something to ask, and answered only by an
    // element that has upgraded — before that, and for every widget that declares nothing,
    // the tag is the word.
    if (registry[tag]?.["x-word"] === "module") {
      const own = item.lfWord?.();
      if (own) return own;
    }
    if (tag.startsWith("lf-")) return tag.slice(3);
    // A <pre> is a block of something and the something is in the markup: the documented
    // shape for source is <pre><code class="language-*">, and a <pre> without the <code> is
    // the shape for what isn't source — a transcript, a stack trace, command output. So the
    // word is read rather than assumed, and a user who calls it a code block is offered
    // one.
    if (tag === "pre") return item.querySelector(":scope > code") ? "code" : "block";
    return HTML_WORDS[tag] ?? tag;
  }
  // The item's own opening words, read the way anchoring reads everything else — so a label
  // a widget declared as the page speaking is in it and the runtime's own chrome (the hidden
  // "2 comments" line) is not. Cut back to a word boundary and marked as cut, because a label
  // ending mid-word reads as a quote that lost its tail rather than as a name for the thing.
  const ITEM_SAYS_CAP = 52;
  // The reading is the whole answer, and it is the answer wherever the item stands. An
  // ask carried by a message is still an ask, and it is read here exactly as an ask on
  // the page is: rooted at the item, so the panel around it is nobody's chrome (see the
  // note on `overIn`) while the item's own marks and offers still are. A veto on
  // `inChrome` stood in front of this, from the days only an anchor's section reached it:
  // it threw the reading away and left the asks tray naming the question by its raw id.
  function itemSays(item) {
    if (!item) return "";
    const whole = quoteFrom(textNodesUnder(item));
    if ([...whole].length <= ITEM_SAYS_CAP) return whole;
    const short = cut(whole, 0, ITEM_SAYS_CAP);
    const at = short.lastIndexOf(" ");
    return (at > ITEM_SAYS_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
  }
  function resolveAnchor(anchor, text) {
    // An element anchor asks a different question — whether the section is still on the
    // user's page — and the whole page is not an answer to it. Existence alone isn't
    // either: a decided element whose markup settles to nothing is present in the
    // document and absent from the screen, and an anchor held to it read as attached
    // while outlining nothing.
    if (anchor.datum) {
      const source = sectionOf(anchor);
      const datum = source
        ? [...source.children].filter(
            (el) =>
              el.matches(DATUM) &&
              el.dataset.lfProjection === anchor.section &&
              el.dataset.lfDatum === anchor.datum,
          )
        : [];
      // A projection/key pair identifies exactly one current fact. Disappearance detaches;
      // duplicates refuse to guess. Where its old display text still stands, mark those
      // exact words. Where the value changed, outline the same datum whole instead of
      // silently following the old string to some other fact.
      if (datum.length !== 1) return null;
      if (!anchor.quote) return { element: datum[0] };
      const segments = findQuote(text, anchor.quote, anchor, datum[0]);
      return segments.length ? { segments } : { element: datum[0] };
    }
    if (anchor.visual) {
      const section = sectionOf(anchor);
      // A semantic visual coordinate is deliberately distinct from `part`, the
      // free-form control label design mode records. Losing either the declaration or
      // its provider therefore detaches instead of silently widening to the widget.
      if (!section || !visualPartAttribute(section) || settledAway(section))
        return null;
      const found = visualPart(section, anchor.visual);
      return found ? { element: section, marks: [found.element] } : null;
    }
    if (!anchor.quote) {
      const section = sectionOf(anchor);
      return section && !settledAway(section) ? { element: section } : null;
    }
    const segments = findQuote(text, anchor.quote, anchor, sectionOf(anchor));
    return segments.length ? { segments } : null;
  }

  // Every mark the page wears, drawn by one pass, so ownership of an element both a thread
  // and the open composer point at is a branch inside a loop rather than an agreement
  // between functions ("One writer per thing" in CLAUDE.md, and why).
  //
  // One range per segment, never one spanning the passage: a single range would paint back
  // over everything the search stepped around on the way — a widget's Choose button, a drag
  // grip, a diagram's generated stylesheet.
  //
  // Keyed by thread, not by mark: a passage is several segments and two comments may land on
  // the same element, so mark → thread loses one of them — and losing it told the panel the
  // passage wasn't in this version while it sat outlined on screen. Every consumer but the
  // hit-test asks "where is thread X", and that is now the direction the map runs.
  const MARK = "lf-mark";
  const PENDING = "lf-pending";
  const NOTE = "lf-mark-note";
  // A standing reaction's paint: a wash fainter than a comment's on the passage (the
  // same highlight registry), a dashed hairline on an element, and a glyph in the margin
  // level with the block the passage starts in. Nothing enters the text flow, so no line
  // reflows when one lands; the glyph is the withdraw control, so the record and the
  // eraser are one surface. Recorded apart from `marked` because it answers a different
  // question — a reaction is not a thread, takes no press to a card, and has no hover.
  const REACT = "lf-react";
  const SEAT = "lf-reacts";
  const reacted = new Map(); // thread id -> the ranges or element parts painted for it
  const marked = new Map(); // thread id -> (Range | Element)[]: the pass's record of what it drew
  // thread id -> the element its passage lands in. A different question from `marked`, and
  // the one the panel's order asks: where a thread is, rather than what was drawn for it. A
  // resolved thread has a place and no paint, and an element anchor's paint is the boxes its
  // contents show through (shownParts) rather than the element the anchor named — so neither
  // record answers for the other. Written only by the pass that resolves the anchors, so the
  // two readings can never come from different resolutions.
  const placed = new Map();
  let pendingMarks = []; // the same record for the open composer's own passage
  let pendingOutline = []; // the elements the open draft outlines, owned by nobody else
  let actionOutline = []; // the visual target whose action bar is standing
  // What the pointer would take, in whichever arming stands — the ⌥ aim's item, or design
  // mode's target: the element, and the control's word where the pointer is on one — and
  // null when neither is armed. One answer for the box, the cursor and the name.
  function aimTarget() {
    if (aimIsOn()) {
      const item = aimedItem();
      return item ? { el: item, part: "" } : null;
    }
    const pointer = pointerAt();
    if (designIsOn() && pointer.x >= 0)
      return designTarget(document.elementFromPoint(pointer.x, pointer.y));
    return null;
  }
  // The aim's one writer, and the whole of its paint: the box in the chrome's layer
  // (aimBox), the cursor's half of the same promise, and in design mode the name of what
  // the box is on. Everything is derived fresh on every ask — the aimed item, lf-over-item,
  // the box's geometry — because a latch here was a second answer to the question the
  // press asks fresh, and a replay repainted it stale. Synchronous, not coalesced to a
  // frame the way refreshHover is: the keydown that arms the page is followed by the press
  // in the same gesture, and a promise a frame behind the arm is one the press can outrun.
  // What each ask costs is one hit-test and one rect walk, which is what the repaint gate
  // this replaced already spent per event on deciding whether to run a far dearer pass.
  function refreshAim() {
    const target = aimTarget();
    const aimed = target?.el ?? null;
    // The cursor's half, written where the box's half is decided, so the hand cannot
    // stand over a press the paint knows takes nothing. `aiming` alone says the page
    // is armed; this says the aim has landed on something.
    document.body.classList.toggle("lf-over-item", Boolean(aimed));
    const r = aimed && shownRect(aimed, new Map());
    if (!r) {
      aimBox.style.display = "none";
      aimBox.removeAttribute("data-for");
      paintInspect(null);
      return;
    }
    const { left, top, right, bottom } = r;
    aimBox.setAttribute("data-for", aimed.id);
    // The item's own corner radius, so the ring hugs the corner the item draws.
    Object.assign(aimBox.style, {
      display: "block",
      left: left + "px",
      top: top + pageScroller.scrollTop + "px",
      width: right - left + "px",
      height: bottom - top + "px",
      borderRadius: getComputedStyle(aimed).borderRadius,
    });
    paintInspect(designIsOn() ? target : null, { left, top });
  }
  // The name of what design mode is aimed at, at the box's top-left corner — above it
  // where there is room, inside it where there isn't (the banner sits at the top edge).
  // Document-anchored like the box, so a scroll moves the two together between the events
  // that re-derive them.
  function paintInspect(target, corner) {
    inspectEl.classList.toggle("lf-shown", Boolean(target));
    if (!target) return;
    const name = target.part
      ? `${target.part} · ${designName(target.el)}`
      : designName(target.el);
    if (inspectEl.textContent !== name) inspectEl.textContent = name;
    const above = corner.top - inspectEl.offsetHeight - 2;
    inspectEl.style.left = `${Math.max(2, corner.left)}px`;
    inspectEl.style.top = `${(above >= 0 ? above : corner.top + 2) + pageScroller.scrollTop}px`;
  }
  let hovering = null;
  let hoverQueued = false;
  const marksOf = (id) => marked.get(id) ?? [];
  const allMarks = () => [...marked.values()].flat();
  // What a reader who cannot see the paint is told. A highlight is glyphs, not an element, so
  // it builds no accessibility node — where a <mark> wrapper was a `mark` node, the paint is
  // nothing at all, and a passage carrying a comment reads exactly like one that doesn't.
  // Neither relation ARIA offers brings it back on something not focusable: NVDA ignores
  // aria-describedby there in browse mode and reports none of the labelling attributes on a
  // bare p or div at all, VoiceOver reads it only on an interactive, image or landmark role,
  // and aria-details is supported unevenly and says only that details exist. What every
  // screen reader announces in every mode is text, so the fact is carried as text — one
  // hidden, unselectable line inside whatever holds the mark, saying how many comments are
  // on it.
  //
  // Coarser than the mark, and deliberately: it names the block a passage sits in rather than
  // the passage, because naming the passage means wrapping it, and wrapping is what a redraw
  // between a mousedown and its mouseup turns into a swallowed click. The panel still carries
  // each thread's own quote. Written only where the text differs from what is already there,
  // because a screen reader rebuilds its buffer on every mutation and this pass runs on every
  // poll.
  function noteMarks(noted) {
    for (const [holder, threadIds] of noted) {
      const note =
        holder.querySelector(`:scope > .${NOTE}`) ??
        holder.appendChild(offer("button", NOTE));
      note.lfThreads = threadIds;
      note.onclick = () => {
        setPanel(true);
        const id = note.lfThreads.find((threadId) =>
          threadsBox.querySelector(`:scope > .lf-thread[data-id="${threadId}"]`),
        );
        const thread =
          id && threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`);
        if (!thread) return;
        thread.focus({ preventScroll: true });
        scrollToThread(id);
      };
      const n = threadIds.length;
      const said = `${n} comment${n === 1 ? "" : "s"}`;
      if (note.textContent !== said) note.textContent = said;
    }
    for (const note of pageQueryAll(`.${NOTE}`))
      if (!noted.has(note.parentElement)) note.remove();
  }

  function paintAnchors(threads = buildThreads()) {
    if (!anchorsReady()) return;
    prepareVisualActions();
    for (const where of allMarks())
      if (where instanceof Element) where.classList.remove("lf-mark-el");
    for (const where of [...reacted.values()].flat())
      if (where instanceof Element) where.classList.remove("lf-react-el");
    for (const el of pendingOutline) el.classList.remove("lf-mark-el", PENDING);
    for (const el of actionOutline) el.classList.remove("lf-action-target");
    marked.clear();
    reacted.clear();
    placed.clear();
    pendingOutline = [];
    actionOutline = [];

    const text = pageText(); // read once, for every anchor this pass places
    const posted = [];
    const reactions = [];
    const seats = new Map(); // block -> the reactions whose passage starts in it
    const noted = new Map(); // element -> ordered thread ids marking something inside it
    for (const t of threads) {
      if (!t.root.anchor) continue;
      const found = resolveAnchor(t.root.anchor, text);
      if (!found) continue;
      // Where the thread's passage lands in this version, recorded for every thread the
      // page still holds — the resolved ones too, which take no paint but do take a place
      // in the panel's order and keep the one they had while they fold out of it.
      placed.set(t.root.id, found.element ?? elementOver(found.segments[0].node));
      if (t.resolved) continue;
      // A reaction nobody has answered: its own paint, and no line for the note — the
      // glyph is a real control that says what it is. Answered, it is a thread and takes
      // a thread's mark below; resolved, nothing, resolve being its floor.
      if (bareReaction(t)) {
        // The seat: the block a passage starts in, entered at its start; or, for a
        // whole element, the element itself, stood before — an element may render into
        // a shadow tree or rebuild its own children, and a seat before it is level with
        // its top either way. A block inside a shadow tree is the host's, seated the
        // element's way: the document's rules do not reach in there to dress a seat.
        let at;
        let before;
        if (found.element) {
          const parts = found.marks ?? shownParts(found.element);
          for (const part of parts) part.classList.add("lf-react-el");
          reacted.set(t.root.id, parts);
          [at, before] = [found.element, true];
        } else {
          const ranges = found.segments.map((seg) => rangeOf([seg]));
          reacted.set(t.root.id, ranges);
          reactions.push(...ranges);
          const block = blockAt(found.segments[0].node) ?? sectionOf(t.root.anchor);
          const root = block?.getRootNode();
          [at, before] =
            root instanceof ShadowRoot ? [root.host, true] : [block, false];
        }
        // One entry per element, holding both placements: a reaction on a whole
        // paragraph and one on a passage inside it are two seats on one element.
        if (at && !inChrome(at)) {
          const held = seats.get(at) ?? { before: [], inside: [] };
          held[before ? "before" : "inside"].push(t.root);
          seats.set(at, held);
        }
        continue;
      }
      if (found.element) {
        // The boxes the element shows through, for the same reason the ask ring hangs on
        // those: an outline needs a box, and a wrapper that generates none took its ring
        // to the document's origin and drew nothing there. The record is what the pass
        // clears, what the pointer hit-tests, and what the composer stands off, so all
        // three follow the paint by holding the parts rather than the element.
        const parts = found.marks ?? shownParts(found.element);
        for (const part of parts) part.classList.add("lf-mark-el");
        marked.set(t.root.id, parts);
      } else {
        const ranges = found.segments.map((seg) => rangeOf([seg]));
        marked.set(t.root.id, ranges);
        posted.push(...ranges);
      }
      // Where the line goes: every block the passage crosses, so the reader of any of them
      // hears it — or, for a passage that sits in no block of its own, the element the
      // anchor names, which is where the runtime already puts chrome a widget has to live
      // with (a card's drag grip). Never the inline run or the body div in between, because
      // a widget reads those back as its own: lf-draft seeds the editor a user types
      // into from its body div, and a line inside it is chrome in the text they send back.
      const blocks = found.element
        ? [found.element]
        : [...new Set(found.segments.map((seg) => blockAt(seg.node)))].filter(Boolean);
      // Not inside the chrome: the line is the runtime's word inside the page's own
      // blocks, and a design comment on a runtime part is on chrome the panel already
      // reads out — an aria-hidden injected note button would be focusable content nobody
      // is told about.
      for (const holder of blocks.length ? blocks : [sectionOf(t.root.anchor)])
        if (holder && !inChrome(holder))
          noted.set(holder, [...(noted.get(holder) ?? []), t.root.id]);
    }

    // The composer's own passage, in the accent rather than the mark's own ink, so a draft
    // never reads as a posted comment. An element a thread already outlines keeps the posted
    // colour: there is one outline to give, and the thread's is the clickable one.
    //
    // The ⌥ aim does not wear this paint, though it is the same fact one step earlier:
    // a promise has to interrupt where an annotation may whisper, so the aim has a box
    // of its own in the chrome's layer (refreshAim, and the .lf-aim rule's account of
    // why). An open composer doesn't stand the aim down — a press while the box is up
    // re-anchors it to the aimed item (openOnItem) — so the two can show at once, which
    // is the true state: where the draft stands, and where a press would move it.
    const draft =
      composerIsOpen() && composerAnchor()
        ? resolveAnchor(composerAnchor(), text)
        : null;
    // Where the draft's passage is, recorded the way the threads' is, because placeComposer
    // has to keep the box off it. An element a thread already outlines belongs
    // in the record too — it is marked, just in the posted colour rather than the accent.
    pendingMarks = draft
      ? draft.element
        ? (draft.marks ?? shownParts(draft.element))
        : draft.segments.map((seg) => rangeOf([seg]))
      : [];
    const pending = [];
    if (draft?.element) {
      // Part by part, because a thread's outline is claimed the same way: the draft takes
      // whichever boxes are still free and leaves the rest in the posted colour. The record
      // above is the parts too, so placeComposer stands the box off the passage the reader
      // can see rather than off a wrapper whose rect sits at the top of the document.
      const taken = allMarks();
      for (const part of pendingMarks)
        if (!taken.includes(part)) {
          part.classList.add("lf-mark-el", PENDING);
          pendingOutline.push(part);
        }
    }
    if (draft?.segments) pending.push(...pendingMarks);

    const active = actionAnchor();
    const action = active && !active.quote ? resolveAnchor(active, text) : null;
    actionOutline = action?.element ? (action.marks ?? shownParts(action.element)) : [];
    for (const part of actionOutline) part.classList.add("lf-action-target");

    // The composer's echo of its own passage, decided here because here is where it is known
    // whether the page is showing that passage. Usually it is — the box opens beside the words
    // it just marked, and printing them inside it says the same sentence twice, side by side.
    // So the quote is the fallback rather than the statement: it shows where the mark can't,
    // which is where this version no longer holds the passage — a draft the user carried
    // onto a newer version, whose text survived the trip when its passage didn't. Dashed and
    // muted, the panel's detached treatment, for the same fact.
    //
    // Scrolled out of view looks like that case and is not: the passage is still there, one
    // scroll back, and the reader put it there seconds ago. A quote coming and going with the
    // scroll position would resize the box under the hands typing in it.
    //
    // Out of sight is not gone: a painted mark has no accessibility exposure at all, so the
    // quote stays in the tree as the box's description whichever way it renders. Written only
    // when it changes, because assigning textContent replaces the node even with the same
    // string, and this pass reruns whenever a comment arrives — a stranded quote is the only
    // copy of that passage left, so it is text a user may be selecting to keep.
    const label = composerIsOpen()
      ? anchorLabel(composerAnchor(), composerAbout())
      : "";
    if (composerQuote.textContent !== label) composerQuote.textContent = label;
    // A design comment's label stays: the outline says which element, and only the words
    // say the comment is about the layer and which control the press landed on.
    composerQuote.classList.toggle(
      "lf-unseen",
      !label || (Boolean(draft) && !composerAbout()),
    );

    // Ranked so each reading survives the ones under it: a posted mark, the hover over it,
    // the standing comment's own mark, and the draft above all three. A higher highlight
    // supplies only the properties it states, so the standing mark under the pointer takes
    // the hover's wash and keeps its own ink. The
    // passage under the pointer answers the pointer.
    CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(REACT, new Highlight(...reactions));
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...pending), { priority: 3 }),
    );
    seatReactions(seats);
    noteMarks(noted); // and the same fact for a reader who can't see any of it
    paintStanding(); // the ranges are new objects and the element classes were just cleared
    // The semantic thread may be unchanged while this pass replaced every Range or
    // element part that paints its hover. Rebind the projection before geometry decides
    // whether the parked pointer still indicates that thread at all.
    if (hovering || hoverThread || hoverParts.length) paintHover(hovering);
    pageShifted(); // the content moved: the hover, a held aim's promise, the legend ask again

    paintThreadQuotes();

    // A message pointing at the page — [the group](#d-channel) — travels by the
    // browser's own fragment navigation, which is already the whole feature within one
    // document: collapsed content wears hidden="until-found", so the jump fires
    // beforematch and the owning tab or settled group opens itself. Opened in a new tab
    // it is an arrival rather than a jump, and landArrival is what answers it there.
    // What the browser has no answer for is the id
    // this version hasn't got. A comment outlives the version it was written on, so
    // that happens without anyone doing anything wrong — and unmarked, the reference
    // reads live, moves nothing on the press, and leaves a fragment nobody holds in the
    // URL for the next load to honor. So it wears the same detached face a quote whose
    // passage left the page wears, asked of the same resolveAnchor, and its press is
    // taken rather than spent. aria-disabled because the title only reaches a pointer.
    for (const a of panel.querySelectorAll(MSG_REF)) {
      const id = fragmentId(a.getAttribute("href"));
      const alive = Boolean(resolveAnchor({ section: id }));
      a.classList.toggle("detached", !alive);
      if (alive) a.removeAttribute("aria-disabled");
      else a.setAttribute("aria-disabled", "true");
      a.title = alive
        ? `Jump to § ${id}`
        : `§ ${id} isn't in the version you're viewing`;
    }
  }

  // The margin glyphs: one seat per block, holding a pill per reaction whose passage
  // starts in it, in log order. The seat is the block's first child and positioned
  // absolutely with no `top`, so its static position — the block's first line — is where
  // it stands, in the column's right margin (`left: 100%`, as a suggestion's controls
  // hang there): no anchor name written onto the author's element, no measurement to
  // re-derive on a resize, and a copy at any width keeps it level with its block. Two
  // reactions on one block share the seat rather than stacking on one point. The pill is
  // the reaction's own eraser — its press is the ordinary undo naming the event — and
  // wears the token's glyph, the token being the runtime's word for what it means.
  //
  // Reconciled rather than rebuilt, so a pill whose press is in flight is the node the
  // reader pressed; stale seats are swept the way note lines are. The seat wears lf-ui
  // and data-lf-gen: an account of the passage, not words of the page, so selection,
  // quote capture and the diff readings skip it, and a frame's first-child trim does.
  // A seat says which placement it is (data-lf-seat), so the one standing before an
  // element and the one starting the same element's flow are told apart even where
  // the element is its parent's first child and the two nodes would otherwise be the
  // same node seen from two sides.
  const seatOf = (at, before) => {
    const node = before
      ? at.previousElementSibling
      : at.querySelector(`:scope > .${SEAT}`);
    return node?.classList.contains(SEAT) &&
      node.dataset.lfSeat === (before ? "before" : "inside")
      ? node
      : null;
  };
  // Whether the seat hangs in the column's margin or docks at the block's start. It
  // hangs off its containing block, and a positioned box the passage stands in — a
  // card, an option, a framed exhibit — is that block, so the glyph would land beside
  // the card rather than beside the column, over a neighbour or under a clip. Measured
  // rather than known, the way a suggestion's row decides whether it fits: hung, then
  // docked wherever it did not reach the column's own margin. Undocked first, so a
  // seat docked once is asked again when the room comes back.
  function dockSeat(seat) {
    seat.classList.remove("lf-docked");
    const column = document.querySelector("main")?.getBoundingClientRect();
    const box = seat.getBoundingClientRect();
    const hangs =
      getComputedStyle(seat).position === "absolute" &&
      column &&
      box.left >= column.right - 1 &&
      box.right <= document.documentElement.clientWidth;
    if (!hangs) seat.classList.add("lf-docked");
  }
  function seatReactions(seats) {
    const kept = new Set();
    const placements = [...seats].flatMap(([at, held]) =>
      ["before", "inside"]
        .filter((placement) => held[placement].length)
        .map((placement) => [at, placement === "before", held[placement]]),
    );
    for (const [at, before, roots] of placements) {
      let seat = seatOf(at, before);
      if (!seat) {
        seat = el("span", `lf-ui ${SEAT}`);
        seat.dataset.lfGen = "1";
        seat.dataset.lfSeat = before ? "before" : "inside";
        if (before) at.before(seat);
        else at.prepend(seat);
      }
      kept.add(seat);
      // What it stands for, for anyone reading the page: the element's id where it
      // has one, the way a suggestion's row names the change it decides.
      if (at.id) seat.dataset.lfFor = at.id;
      else seat.removeAttribute("data-lf-for");
      const wanted = roots.map((root) => {
        let mark = seat.querySelector(`:scope > [data-event="${root.id}"]`);
        if (!mark) {
          const entry = registry.$reactions.tokens[root.token];
          mark = offer("button", "lf-pill lf-react-mark", entry?.glyph ?? root.token);
          mark.dataset.event = root.id;
          mark.dataset.token = root.token;
          mark.title = `${root.token} — press to take it back`;
          mark.setAttribute("aria-label", `${root.token} — take it back`);
          mark.onclick = () => withdraw(root);
        }
        return mark;
      });
      for (const child of [...seat.children])
        if (!wanted.includes(child)) child.remove();
      wanted.forEach((mark, i) => {
        if (seat.children[i] !== mark)
          seat.insertBefore(mark, seat.children[i] ?? null);
      });
    }
    for (const seat of pageQueryAll(`.${SEAT}`)) if (!kept.has(seat)) seat.remove();
    dockSeats();
  }
  // Asked again whenever the room changes under the seats — the panel opening or
  // closing, the window resizing (syncLayout) — as well as at every paint.
  function dockSeats() {
    for (const seat of pageQueryAll(`.${SEAT}`)) dockSeat(seat);
  }

  // Re-resolve marks after a package replaces derived passage nodes during replay.
  let projectionAnchorPaintQueued = false;
  document.addEventListener("lf-projection", () => {
    if (projectionAnchorPaintQueued) return;
    projectionAnchorPaintQueued = true;
    queueMicrotask(() => {
      projectionAnchorPaintQueued = false;
      paintAnchors();
    });
  });

  // A reference a message makes into the page: its own Markdown link, or one a widget
  // in its frozen markup writes (a lf-option's `for`). One selector, so what the paint
  // above dresses and what the press below refuses are the same set.
  const MSG_REF = '.lf-msg-body a[href^="#"]';
  // The id a fragment names. An href holds it as the renderer percent-encoded it and
  // location.hash as the browser did; the document holds it as written. A malformed
  // escape ("#100%") keeps its own characters. One reading for both, because a reference
  // the panel paints and a URL the page arrived at name their element the same way.
  function fragmentId(fragment) {
    const raw = fragment.slice(1);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  // The only press this layer takes from the browser: a reference this version can't
  // follow. Everything else — the travel, the reveal, the back button — is the
  // platform's, and an exported copy keeps it by having a real href to jump through.
  panel.addEventListener("click", (ev) => {
    const a = ev.target.closest(MSG_REF);
    if (a && !resolveAnchor({ section: fragmentId(a.getAttribute("href")) }))
      ev.preventDefault();
  });

  // Which thread's mark is under a point. A painted range is not an element, so the pointer
  // finds it by the boxes the range occupies rather than by hit-testing the DOM — asking for
  // the caret position instead would claim the empty space past the end of a short line.
  function markAt(x, y) {
    const over = document.elementFromPoint(x, y);
    if (!pageWords(over)) return null;
    // The retargeted element answers the chrome question, whose subject is which layer the
    // pointer is in; an element mark needs the tree's own answer, because a host contains
    // every mark staged inside it and so tells none of them apart.
    const deep = elementFromPointAcross(x, y);
    for (const [id, marks] of marked)
      for (const where of marks) {
        const hit =
          where instanceof Range
            ? [...where.getClientRects()].some(
                (r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom,
              )
            : containsAcross(where, deep);
        if (hit) return id;
      }
    return null;
  }

  // Bring an element in the document to the position its caller names. A thread's element
  // anchor takes the middle; an Ask takes the readable start so its context comes before
  // its control. Which box does the travelling is scrollerFor's answer, asked here rather
  // than assumed: the document's scroller was written into this twice, so an element
  // standing in the panel's list was taken into view by the platform and then had this
  // travel spent on the page behind it, moving a reader who had asked for nothing there.
  // Reveal first, since opening a tab or settled group moves
  // everything below it. For a centred destination, "the middle" means the viewport's:
  // scrollIntoView measures against the scroller's own
  // scroll-padding-top — declared so a native fragment jump clears the banner — and every
  // "center" through it therefore landed 27px low. An element taller than the viewport has
  // no middle to show, and centring one puts its opening words above the top edge, so it
  // takes that same banner clearance instead and the reader starts at the start.
  //
  // The viewport is the scroller's own box rather than the window's, which is the same
  // number for the document — body is the page's scroller and is the window's height — and
  // is the panel's list where that is what scrolls.
  //
  // It glides, because a page the reader is already holding is one the motion keeps their
  // place in — the same reason a restore doesn't (moveScrollerBy). An arrival passes
  // "instant" for
  // exactly that reason: a document that appeared a moment ago holds no place to keep, so
  // the glide would be animating from nowhere.
  function centreBy(where, block = "center", box = pageScroller) {
    const rect =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    // The scroller's own box rather than the window's: the same number for the document,
    // whose scroller is body, and the list's own where the list is what scrolls.
    const view = shownBox(box);
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    const place =
      where instanceof Range
        ? (view.height - rect.height) / 2
        : block === "start"
          ? clear
          : Math.max((view.height - rect.height) / 2, clear);
    return rect.top - view.top - place;
  }
  function scrollToElement(el, behavior = scrollBehavior(), block = "center") {
    reveal(el);
    el.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: block === "nearest" ? behavior : "instant",
    });
    // `nearest` is a request to reveal only. Once the platform has done that, a
    // second centring move would turn a small correction into a page jump.
    if (block === "nearest") return;
    const box = scrollerFor(el);
    if (!under(el, box)) return;
    moveScrollerBy(box, centreBy(el, block, box), behavior);
  }

  // A comment destination already fully visible in its own scroller needs no travel.
  // Compare its unclipped geometry with what every clipping ancestor actually exposes;
  // an element can be in the viewport while still hidden behind a nested scroller edge.
  function readableThreadDestination(where) {
    const holder =
      where instanceof Range
        ? where.startContainer instanceof Element
          ? where.startContainer
          : where.startContainer.parentElement
        : where;
    if (!holder) return false;
    const destination =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const seen =
      where instanceof Range
        ? clippedRect(destination, holder, new Map())
        : shownRect(where, new Map());
    if (!seen) return false;
    const box = scrollerFor(holder);
    const view = shownBox(box);
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return (
      destination.top >= view.top + clear &&
      destination.bottom <= view.bottom &&
      close(seen.top, destination.top) &&
      close(seen.right, destination.right) &&
      close(seen.bottom, destination.bottom) &&
      close(seen.left, destination.left)
    );
  }

  // Move to where a thread is painted, if it still is — asked of the pass's own record, so the
  // panel and the page can't disagree about whether the passage survived. A painted range has
  // no element to scroll into view, so its own box does the work.
  //
  // Every "show me that comment's passage" route ends here. The focus its caller already
  // placed in the thread owns the standing paint; this function owns only the travel. It
  // makes the target's box visible in both axes, then glides the exact mark to the centre
  // of the region that holds it. No transient effect waits on that motion or survives it
  // as separate state.
  function scrollToThread(id) {
    let where = marksOf(id)[0] ?? placed.get(id);
    if (!where) return;
    const holder =
      where instanceof Range
        ? where.startContainer instanceof Element
          ? where.startContainer
          : where.startContainer.parentElement
        : where;
    if (!holder) return;
    reveal(holder);
    if (!(where instanceof Range) && !marksOf(id).length) {
      paintAnchors();
      where = marksOf(id)[0] ?? where;
    }
    if (readableThreadDestination(where)) return;
    if (!(where instanceof Range)) {
      scrollToElement(where);
      return;
    }
    // Sideways first, and only as far as it takes: a passage inside a wide `pre` or a
    // rendered diagram sits in a box with its own horizontal scroll, which the vertical
    // jump below cannot reach — scrolling to it in one axis leaves it off-screen in the other.
    holder.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
    moveScrollerBy(pageScroller, centreBy(where), scrollBehavior());
  }

  // Pointer feedback a wrapped <mark> got from :hover and cursor: pointer, neither of which
  // ::highlight() can carry — it styles glyphs, not boxes. Same hit-test as the click, so
  // what lights up is what would open. It is a function of where the pointer is and what the
  // page's geometry is, so everything that moves either asks again: the pointer moving, the
  // page scrolling under a still pointer, and the pass redrawing the ranges themselves.
  //
  // The pointer can indicate a thread from either surface, and the panel is the other one.
  // A card is the thread's view in the list the way a mark is its view in the prose, so
  // resting on the card lights the passage exactly as resting on the passage lights it —
  // the same wash, because it is the same fact, and a second strength would be a third
  // thing to learn on a page that already asks the reader to tell a mark from a standing
  // mark. It answers the question a reader scanning a full list keeps asking, which of
  // these is about what, without a press and without a travel they may not want; the
  // standing mark answers it for the one comment they chose, and this answers it for the
  // one under their hand.
  //
  // One answer rather than two, because the pointer is in one place: markAt refuses a point
  // that lands in the chrome, so the panel's reading and the page's cannot both name a
  // thread. That is also why the two are read here rather than painted by separate hands —
  // a second writer to this highlight would be overwritten by whichever frame ran last, and
  // the hit-test runs on every pointer move.
  //
  // The whole card and not the quote alone, though the quote is the part that presses. The
  // card is where the eye is while it reads the comment, and the question arrives there
  // rather than on the three clamped lines at the top; a reader who wanted the quote's
  // press would already be on it.
  const HOVER = "lf-mark-hover";
  const hoveredThreadOf = () => threadsBox.querySelector(".lf-thread:hover");
  let hoverParts = [];
  let hoverThread = null;
  const hoverCardOf = (id) =>
    id ? threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`) : null;
  function paintHover(id) {
    hovering = id;
    // The page and panel are reciprocal views of the thread. The highlight paints the
    // passage when the pointer is on its card; this class paints the card when the pointer
    // is on its passage. One writer keeps them on the same id, and keeping the node lets a
    // sweep touch only the two cards whose answer changed.
    const thread = hoverCardOf(id);
    if (hoverThread !== thread) {
      hoverThread?.classList.remove(HOVER);
      thread?.classList.add(HOVER);
      hoverThread = thread;
    }
    const where = marksOf(id);
    // Both kinds of anchor, for the reason paintStanding takes both: one question about one
    // thread, and a reading that answered only the passages with words left an element
    // anchor saying nothing back. Only what changed, and guarded on each side, for the
    // reason spelled out there — this runs on every frame of a pointer sweep.
    const parts = where.filter((mark) => mark instanceof Element);
    for (const part of hoverParts)
      if (!parts.includes(part)) part.classList.remove(HOVER);
    for (const part of parts)
      if (!part.classList.contains(HOVER)) part.classList.add(HOVER);
    hoverParts = parts;
    CSS.highlights.set(
      HOVER,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 1,
      }),
    );
  }
  // Which comment the reader is standing in, said out on the page. The panel has always
  // answered it on its own surface — the thread holds the focus, and a press on a mark
  // flashes the thread it opens — while the page answered nothing back: every posted mark
  // wears one wash, so a reader sent from a comment to its passage arrived among a dozen
  // identical marks with no way to tell which one they had asked to see. The t/T walk's
  // comment already called the panel and the page "two views of the same thread"; this is
  // the view that was missing.
  //
  // Derived from the focus rather than written where the travel put the reader, for the
  // reason markHere gives about the ask ring: a mark written at the arrival says where the
  // reader was *sent*, and goes on saying it after they have clicked away, read on down the
  // page and come back tomorrow. Every way into a thread then paints it — the quote's press,
  // t/T, a plain click on the card — because they all end in the same focus, and no
  // way in has to be taught to paint.
  //
  // Read through `closest` rather than off the thread itself, so a reader typing a reply is
  // still standing in the comment they are replying to; that is exactly when knowing which
  // passage it is on is worth most.
  //
  // Above the hover and below the draft. A pointer resting on the standing mark supplies
  // the middle wash, while this higher paint keeps the strongest wash and its accent ink:
  // the cursor promises the press, and the ink answers "which one".
  const HERE = "lf-mark-here";
  let hereParts = [];
  function paintStanding() {
    const where = marksOf(focusedThreadOf()?.dataset.id);
    const parts = where.filter((mark) => mark instanceof Element);
    // Only what changed, because the anchor pass calls this and the anchor pass runs on
    // every poll: an element that keeps the class would otherwise have it taken off and put
    // straight back, writing the page's own attribute twice a poll for as long as the
    // reader stands there, and a mutation on an authored element is something this page's
    // observers hear. Both sides are guarded, because Chrome records a mutation for a
    // classList.add of a token already in the list — the same reason noteMarks writes its
    // line only when the words differ.
    for (const part of hereParts)
      if (!parts.includes(part)) part.classList.remove(HERE);
    for (const part of parts)
      if (!part.classList.contains(HERE)) part.classList.add(HERE);
    hereParts = parts;
    CSS.highlights.set(
      HERE,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 2,
      }),
    );
  }
  // Coalesced to a frame: scroll outruns layout, the hit-test reads layout, and a repaint
  // asks from inside a pass that must stay cheap enough to run from a mousedown. The frame
  // is what settles the panel's half too — that reading is the browser's own :hover state,
  // and asking for it from inside the pointer event that is moving it asks mid-move.
  function refreshHover() {
    if (hoverQueued || (!marked.size && !hovering && !hoverThread)) return;
    hoverQueued = true;
    requestAnimationFrame(() => {
      hoverQueued = false;
      // The cursor stays with the page's own reading. It is the promise that a press here
      // opens something, and over a card the press on offer is the card's own — which the
      // panel already says for itself, on the quote that makes it. Unconditional because
      // toggle runs no update step when the answer has not changed, unlike the add that
      // noteMarks and the standing paint have to guard.
      const pointer = pointerAt();
      const onMark = markAt(pointer.x, pointer.y);
      document.body.classList.toggle("lf-over-mark", Boolean(onMark));
      const id = hoveredThreadOf()?.dataset.id ?? onMark;
      // A reconcile normally keeps a thread node, but settlement replaces it. If the
      // pointer stayed over the same semantic thread, repaint the reciprocal class onto
      // that new card even though the id did not change.
      if (id !== hovering || hoverCardOf(id) !== hoverThread) paintHover(id);
    });
  }
  // The shared pointer recorder is installed before this listener, so the hover reads the
  // same unrounded point the browser used for the event's hit test.
  document.addEventListener("pointermove", refreshHover);
  // The page moving under a parked pointer is the pointer moving over the page: what a
  // press would take, whether a mark is under the hand, and where every legend box
  // stands can all change with no mouse event to say so, and a box left over the old
  // item promises a press the click no longer makes. One repaint set for every door
  // that says so — a scroll, a window resize, a replay's marks landing (paintAnchors),
  // a widget's FLIP settling, and the reflows only the legend's observers hear, the
  // panel opening re-centring the column among them.
  let actionFrame = 0;
  function queueActionPlacement() {
    if (actionFrame) return;
    actionFrame = requestAnimationFrame(() => {
      actionFrame = 0;
      refreshAction();
    });
  }
  function pageShifted() {
    refreshHover();
    refreshAim();
    // A board scrolled sideways carries its cards out from under their boxes, and the
    // page scrolled brings items into view that had no box yet (shownRect).
    queueLegend();
    if (actionAnchor()) queueActionPlacement();
  }
  // At the document and at capture, because scroll does not bubble and body is not the
  // page's only scroller: a board scrolls its columns sideways, and a card carried under
  // a parked pointer that way is the same fact as the page scrolling under it. Capture is
  // the one place every scroller's event passes.
  document.addEventListener("scroll", pageShifted, { capture: true, passive: true });

  const anchors = {
    sectionOf,
    ITEM,
    isItem,
    itemAt,
    itemWord,
    itemSays,
    visualAt,
    visualActionAnchor,
    visualPartAt,
    visualPartLabel,
    resolveAnchor,
    NOTE,
    isMarked: (id) => marked.has(id),
    placedAt: (id) => placed.get(id),
    pendingMarkParts: () => [...pendingMarks],
    refreshAim,
    dockSeats,
    paintAnchors,
    fragmentId,
    markAt,
    scrollToElement,
    scrollToThread,
    paintStanding,
    refreshHover,
    pageShifted,
  };
  publishedAnchors = anchors;
  return anchors;
}
