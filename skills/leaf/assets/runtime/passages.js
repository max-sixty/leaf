/* The page's one DOM reading and quote resolver. */
let publishedPassages;
export const closestAcross = (...args) => publishedPassages.closestAcross(...args);
export const inChrome = (...args) => publishedPassages.inChrome(...args);
export const inUi = (...args) => publishedPassages.inUi(...args);
export const renderRetired = (...args) => publishedPassages.renderRetired(...args);
export const says = (...args) => publishedPassages.says(...args);
export const textNodesUnder = (...args) => publishedPassages.textNodesUnder(...args);
export const uiInside = (...args) => publishedPassages.uiInside(...args);
export const wrote = (...args) => publishedPassages.wrote(...args);

export function createPassages(dependencies) {
  const {
    PAGE_PAINT_ATTRIBUTE,
    opaquePassageParts,
    opaquePassageRoots,
    pageShadowRoots,
    registry,
    widgetEntries,
  } = dependencies;

  // ---------- passages ----------
  // A passage is a list of {node, start, end} segments, and everything that reads the page's
  // text speaks in them: the search for a quote, the capture of one, the landmark a version
  // change rides on, the version diff's block keys. One shape means one answer to what the
  // page says. The bugs this layer kept having were all a second answer disagreeing with the
  // first — what a selection rendered as versus what the document holds — and a second
  // answer is what there is now no room for.
  //
  // Two skip lists, because two jobs genuinely differ, and the difference is the whole
  // reason .lf-ui and data-lf-gen are two markers rather than one. Anchoring skips the
  // runtime's own words, inline scripts, and the stylesheet a rendered diagram carries
  // inside its <svg>: a quote holding text the search skips is a quote nothing can find
  // again. The version diff additionally skips content an upgrade generated, because the
  // base document parses unupgraded and would never match it. So generated text the page
  // authored — a widget's label, an attribute renderSaid rendered — is diff-invisible and
  // quotable, which is the pair a user expects: they can point at it, and it doesn't
  // read as a change nobody wrote.
  //
  // A decided suggestion's retired slot goes with them. Its markup is still in the
  // document — the honoring version is what finally drops it — but the user has
  // removed it, and the live view is the version plus their decisions. Text nobody can
  // see is text nobody can mean: without this a comment made on a passage then accepted
  // away kept reading as attached in the panel and jumped nowhere, and a quote from
  // elsewhere could match inside the invisible half of a replacement.
  //
  // Which slots retire is the registry's to say, so this and passages.py's reading of the
  // same page follow one declaration: x-retired-when names the decision that removes the
  // element, x-parent the wrapper the decision is recorded on.
  // Computed once — but only once the registry has loaded: the aim listeners are
  // live from module evaluation, and a pointer move in the upgrade window would
  // otherwise seed the cache from the empty pre-fetch registry and disable the
  // retired-slot skip for the life of the page. It used to be rebuilt per
  // candidate ancestor per pointer move (itemAt's aim walk).
  let retiredSlotsMemo;
  function retiredSlots() {
    if (retiredSlotsMemo != null) return retiredSlotsMemo;
    // One selector per holder, never the array interpolated: `x-parent` is a list, and
    // `${list}` joins it with a comma, so a slot naming two holders wrote a selector
    // *list* whose first member was a bare tag — every instance of the first holder read
    // as a retired slot, decided or not, and the pair that was meant matched nothing.
    const value = widgetEntries()
      .filter(([, entry]) => entry["x-retired-when"])
      .flatMap(([tag, entry]) =>
        entry["x-parent"].map(
          (parent) => `${parent}[data-lf-state="${entry["x-retired-when"]}"] > ${tag}`,
        ),
      )
      .join(", ");
    if (Object.keys(registry).length) retiredSlotsMemo = value;
    return value;
  }
  // The same relation read the other way: holder tag → each settling outcome and the
  // slot tags that leave the page under it. Replay reads it to paint the settlement
  // (markSettled, renderRetired), so which verbs settle a holder is the registry's fact
  // here exactly as it is in the selector above. Same registry-loaded guard, for the
  // same aim-window reason.
  let settlementSlotsMemo;
  function settlementSlots() {
    if (settlementSlotsMemo != null) return settlementSlotsMemo;
    const value = {};
    for (const [tag, entry] of widgetEntries().filter(([, e]) => e["x-retired-when"]))
      for (const parent of entry["x-parent"])
        ((value[parent] ??= {})[entry["x-retired-when"]] ??= []).push(tag);
    if (Object.keys(registry).length) settlementSlotsMemo = value;
    return value;
  }

  // The rendering of a settlement, in one place for the two occasions that paint it —
  // replay (markSettled) and a module saying its own gesture (lf-suggestion's #settle):
  // reads the holder's mark and paints data-lf-retired onto the slots the standing
  // outcome retires, clearing it from the rest. One static theme rule hides the marked
  // slots, so a family a project declares hides what a settlement removes the day it
  // declares it — by-name rules in theme.css were the closed list wearing CSS's
  // clothes — and the same pair of marker and rule is what carries the disappearance
  // into an exported copy, which keeps markup and stylesheet and drops every module.
  function renderRetired(el) {
    const outcomes = settlementSlots()[el.localName];
    if (!outcomes) return;
    const mark = el.getAttribute("data-lf-state");
    for (const [outcome, tags] of Object.entries(outcomes))
      for (const tag of tags)
        for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
          for (const slot of root.querySelectorAll(`:scope > ${tag}`))
            slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, outcome === mark);
  }
  // What no label can speak through, however it is marked: an inline script, the
  // stylesheet a rendered diagram carries inside its <svg>, and a slot the user's
  // decision took off the page. Chrome is the rest of what the anchor pass skips and
  // the one part a label yields — it is a look, and a look cannot make a word the
  // runtime's.
  let silencedMemo;
  function silenced() {
    if (silencedMemo) return silencedMemo;
    const retired = retiredSlots();
    const value = ["script", "style", ...(retired ? [retired] : [])].join(", ");
    // Same registry-loaded guard as retiredSlots, for the same aim-window reason.
    if (Object.keys(registry).length) silencedMemo = value;
    return value;
  }

  // An element the user's decision took off the page, asked of an element rather
  // than of text: a retired slot (or anything inside one), or a decided element the
  // retirement emptied — a deletion accepted, an insertion refused — whose every child
  // is now a retired slot or the runtime's own chrome, with no text of its own. The
  // same declaration the anchor pass skips text by answers both (a declared label
  // counts as words still showing), and so an element anchor and a quote cannot
  // disagree about what left the page.
  //
  // The chrome question is bounded at the element, because the answer is about what this
  // element has left rather than about where it is standing. A suggestion an agent sent
  // in a reply stands inside the panel, which is chrome, so asked the unbounded way its
  // surviving half counted as apparatus too: one accepted slot emptied it, the anchor a
  // reader had put on it detached, and the mark went out from under a thread that was
  // still open. The same suggestion on the page kept both.
  function settledAway(el) {
    const retired = retiredSlots();
    if (!retired) return false;
    if (el.closest(retired)) return true;
    const nodes = [...el.childNodes];
    return (
      nodes.some((n) => n.nodeType === 1 && n.matches(retired)) &&
      nodes.every((n) =>
        n.nodeType === 1
          ? n.matches(retired) || uiInside(n, el)
          : n.nodeType !== 3 || !n.data.trim(),
      )
    );
  }
  const GENERATED = ".lf-ui, [data-lf-gen]";
  // A label a widget declared as the page speaking (relabel), which the anchor pass reads
  // over the chrome it sits in.
  const SAID = "[data-lf-said]";
  const DATUM = "[data-lf-projection][data-lf-datum]";
  // The same question one node at a time: is this the runtime's own chrome rather than the
  // document? Every affordance asks it before acting on where the pointer or the caret is.
  // The nearest element that answers wins: a declared label is the page's words inside the
  // control it labels, and a control nested inside one is chrome again. `.lf-ui` alone was
  // the answer once, and it is a look — which is how a user ended up reading a heading
  // they could not point at, twice.
  //
  // Bounded or not, by the second argument, and that is the whole difference between the
  // two ways this gets asked. Unbounded — `inUi` — the answer is about the page: a
  // control is the runtime's apparatus wherever it stands, which is what a pointer or a
  // caret needs to know. Bounded at an element, the answer is about that element's own
  // insides, which is what a reading of one widget needs: the panel holding a widget an
  // agent sent in a reply is itself `.lf-ui`, so asked the unbounded way every child of
  // such a widget answers yes, and the widget reads as having nothing of its own left.
  // The text readings took the same seam (quotable, authored); it is stated once here so
  // that what a mark may hang on, what a settlement has emptied, and what a quote may
  // name cannot come apart.
  const uiInside = (el, within) => {
    const near = el && overIn(el, `.lf-ui, ${SAID}`, within);
    return Boolean(near) && !near.matches(SAID);
  };
  const inUi = (node) =>
    uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);
  // A different question the class also used to answer, and not a question about looks at
  // all: which document is this element in? The runtime's layer is one container, so a
  // widget inside a reply — markup frozen in the log, carried by no version — is exactly
  // what that container holds, and the reading position is a place in the page rather than
  // in the panel over it. `.lf-ui` reached those elements and a widget's own controls out
  // on the page besides, which is the look standing in for the place.
  // Across the boundary for the same reason the climb below is: the marker lives out in
  // the document, so a node inside a widget's shadow tree can only reach it by leaving the
  // tree, and a widget staged inside a reply would otherwise read as page content.
  const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
  // The two together, which is what an affordance acting on where the pointer or the caret
  // is actually needs: the page's own words, as against the layer over them and as against
  // the apparatus inside them. Either half alone leaves a hole, and the hole `.lf-ui` left
  // was this one — a declared label is nearer than the panel and answers for itself, so a
  // drag across a question an agent asked in a reply read as a passage of the page. It
  // raised the page's 💬 and wrote an anchor onto a thread's own id, into an append-only
  // log, naming a section no version holds. `leaf comment --section` refuses exactly that
  // from the file side, and file capture is the reading that is supposed to promise less.
  const pageWords = (node) => Boolean(node) && !inChrome(node) && !inUi(node);
  // The runtime's own parts, as against everything else standing in its layer. Its parts
  // wear its id namespace — `lf-composer-quote`, which authored markup may not take — and
  // a widget an agent sent stands in the layer wearing an id of its own, no part of it.
  // `inChrome` answers which document an element is in, and it was standing in for this
  // question too: a design comment on a question asked in a reply was filed under the
  // runtime's own buttons and named "ps ask", where the same widget on the page reads
  // "lf-options · ps-decision".
  const layerPart = (el) => inChrome(el) && el.id.startsWith("lf-");
  const TEXT_BLOCK =
    "p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary";
  // The two readings, each one predicate over a text node and named for the question it
  // answers. Anchoring reads what the user can point at: not the runtime's own words —
  // `inUi`, which a declared label answers for itself — and nothing behind a wall no label
  // speaks through, so a pick mark inside a slot the user accepted away is gone with
  // the slot, its marker notwithstanding. The diff reads what the base version holds, and
  // the base parses unupgraded, so everything an upgrade generated goes, a declared label
  // included: the version being compared against has none.
  //
  // Built per walk rather than per node, because the retired half of the wall is read out
  // of the registry each time it is asked for.
  // A text node's parent is an element, and all four readings of these nodes say so:
  // the two below, pageText's cell walk and snapOut's seam. Written four ways it was four
  // answers to one question, three of them asserting the parent and one quietly admitting
  // a node without one — which is a claim about the page nothing backs: what a widget
  // stages into a shadow root is the only text these walks reach with no element over it,
  // and a module staging a bare text node would be handing the page words no cell, no
  // fence and no block. So the assertion is one function, and refusing is what it does.
  //
  // It refuses in the words of the mistake, which is the half that was missing. Throwing
  // out of the pass the render gate reads the console for is the loud direction, and the
  // throw was `Cannot read properties of null (reading 'closest')` on a page showing
  // nothing at all — naming neither the widget that staged the text nor what was wrong
  // with it. A refusal whose message is a property name reaches its author as the runtime
  // being broken, which is the one thing it isn't.
  const elementOver = (n) => {
    if (n.parentElement) return n.parentElement;
    const host = n.getRootNode()?.host;
    const at = host
      ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>`
      : "a module";
    throw new Error(
      `${at} staged bare text into a shadow root: ` +
        `${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, ` +
        `so the page holds no block, cell or fence for it. Give a module's rendered ` +
        `words an element to sit in.`,
    );
  };
  // Is `node` inside `root`? `Element.contains` stops at a shadow boundary and these
  // readings walk through one, so the climb is the same one `closestAcross` makes.
  const under = (node, root) => {
    for (let a = node; a; a = a.parentNode ?? a.host ?? null)
      if (a === root) return true;
    return false;
  };
  // The widget a reading belongs to. `.lf-ui` says the runtime built this rather than the
  // author, and a reading rooted at the document takes that straight: everything the layer
  // holds is the layer's, which is the whole of what the anchor pass and the version diff
  // need. Inside a widget it is a different sentence, and the widget is where it changes.
  //
  // A widget riding a message stands inside the thread panel, so the panel is `.lf-ui`
  // over every word it says — and read straight, a question an agent asked in a reply says
  // nothing whatever. That silence did not read as one: it read as an empty slot, so the
  // group named its options by their ids in the accessibility tree, the decisions tray named the
  // question by its id, and every widget reading its own words in a message got "" and fell
  // back to something else.
  //
  // So chrome between the words and their widget is that widget's own apparatus, and chrome
  // above the widget is somebody else's. Rooting the search at the element handed in says
  // almost the same thing and is wrong in one case that matters: a reading can start
  // *inside* generated chrome. A conversation box's messages are `<p>`s the runtime built,
  // on the page, inside the group they belong to — and `diffBlocks` reads every block on the
  // page, so bounded at the block each of them stopped being generated and the version diff
  // painted the reader's own comments as changes to the document.
  const frameOf = (node) => {
    for (let a = node?.nodeType === 1 ? node : upFrom(node); a; a = upFrom(a))
      if (a.localName?.startsWith("lf-")) return a;
    return null;
  };
  // The chrome over a node, read within one frame: above the frame it is nobody's, and with
  // no frame at all it is the document's own reading, unchanged.
  const overIn = (el, selector, frame) => {
    const near = el.closest(selector);
    return near && (!frame || under(near, frame)) ? near : null;
  };
  const quotable = (root) => {
    const gone = silenced();
    const frame = frameOf(root);
    return (n) => {
      const el = elementOver(n);
      return !uiInside(el, frame) && !el.closest(gone);
    };
  };
  const authored = (root) => {
    const frame = frameOf(root);
    return (n) => !overIn(elementOver(n), GENERATED, frame);
  };
  // The composed tree, not the light one: a widget that renders the page's words into an
  // open shadow root (x-shadow) shows the reader what its shadow tree holds, and a host's
  // own children stop rendering the moment it has one. A TreeWalker sees none of that — it
  // stops dead at the boundary — so the walk is written out, and it is the same walk in
  // both directions: a host's shadow root stands in for its children, a <slot> stands for
  // what was assigned to it, and everything else is the light DOM it always was. Nothing
  // here asks which widget it is looking at; a document with no shadow roots in it walks
  // exactly as it did before.
  //
  // The order is what earns the recursion. `pageText` builds one string in reading order
  // and indexes every position into it, so shadow text has to arrive at the host's own
  // place in that string — not appended from a second walk, which would put a diff's lines
  // after the page's last paragraph and every neighbour of theirs a lie.
  function textNodesUnder(rootEl, accepts = quotable(rootEl)) {
    const segments = [];
    const visit = (node) => {
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
          if (accepts(child))
            segments.push({ node: child, start: 0, end: child.data.length });
          continue;
        }
        if (child.nodeType !== Node.ELEMENT_NODE) continue;
        if (child.localName === "slot")
          for (const assigned of child.assignedNodes({ flatten: true }))
            assigned.nodeType === Node.TEXT_NODE
              ? accepts(assigned) &&
                segments.push({
                  node: assigned,
                  start: 0,
                  end: assigned.data.length,
                })
              : visit(assigned);
        else {
          // Only a root the registry declares (x-shadow): the capture asks
          // getComposedRanges for exactly the declared ones, and every climb
          // crosses exactly those — so a walk that entered any open root read
          // words the anchor side could never place, and a widget's undeclared
          // root anchored quotes astray instead of staying opaque. The render gate
          // names an undeclared root; this leaves its words alone.
          const declared = child.shadowRoot && registry[child.localName]?.["x-shadow"];
          visit(declared ? child.shadowRoot : child);
        }
      }
    };
    visit(rootEl);
    return segments;
  }

  // One step towards the document from any node, shadow boundary included: the ordinary
  // parent within a tree, and the host where a tree runs out. Every question the runtime
  // asks about where a node sits — which section, which block, which passage cell, whether
  // it is chrome — is asked of the page, and a climb that stops at a shadow root answers
  // about the widget's own markup instead.
  const upFrom = (node) => node.parentElement ?? node.getRootNode()?.host ?? null;

  // contains() stops at a boundary the same way, and this is the one that decides whether a
  // quote is found at all: a section holding an x-shadow widget does not contain the words
  // that widget renders, so narrowing a search to that section threw away every candidate
  // inside it and the passage resolved to nothing — the anchor captured, the mark never
  // painted. Asked of each tree on the way out, so the section contains what it renders.
  const containsAcross = (ancestor, node) => {
    for (let n = node; n; n = n.getRootNode()?.host ?? null)
      if (ancestor.contains(n)) return true;
    return false;
  };

  // closest() stops at a shadow boundary, so a node inside a widget's shadow tree can't
  // reach the section that holds it or the chrome marker above it — both out in the
  // document. Same climb as upFrom, asked with a selector at each tree it passes through.
  function closestAcross(node, selector) {
    let el = node?.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
    while (el) {
      const hit = el.closest(selector);
      if (hit) return hit;
      el = el.getRootNode()?.host ?? null;
    }
    return null;
  }

  // getElementById searches the document tree alone, which is the same boundary again and
  // the one every question the runtime asks by id runs into: which element an anchor names,
  // what an action rests on, which unit a fold paints, which ask a key steps to. A widget
  // that stages its authored children into a shadow tree takes their ids in there with it,
  // and each of those answers would come back null and quietly do nothing — the anchor
  // captured, the mark never painted, no error anywhere. The document first, because that
  // is where everything but a staged widget's own parts lives, and only the roots the
  // registry declares after it, so the walk sees what the capture saw.
  const elementById = (id) => {
    const found = document.getElementById(id);
    if (found) return found;
    for (const root of pageShadowRoots()) {
      const inside = root.getElementById(id);
      if (inside) return inside;
    }
    return null;
  };

  // elementFromPoint retargets to the host for a point over a shadow tree, so it names the
  // widget rather than the thing in it, and each root answers for its own. Mark hit testing
  // and item aim both use this exact reading, so a projected datum inside a declared shadow
  // tree can outrank its host.
  const elementFromPointAcross = (x, y) => {
    let el = document.elementFromPoint(x, y);
    while (el?.shadowRoot) {
      const inner = el.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === el) break;
      el = inner;
    }
    return el;
  };

  // A pass that clears its own marks before repainting has to sweep everywhere it can
  // write, and `elementById` above is what widened that: a mark placed on a staged element
  // sits in a tree `document.querySelectorAll` never enters, so the clear would miss it and
  // the mark outlive the reason for it. The runtime's own marks are read back this way, and
  // so is a control the reader can stand on, for the same reason: both are wherever the
  // markup ended up. Which widgets the page holds is a different question and still the
  // document's:
  // a widget staged inside another's tree is a nesting the registry's x-parent contract
  // does not model, and answering it here would be inventing that contract in a sweep.
  const pageQueryAll = (selector) =>
    [document, ...pageShadowRoots()].flatMap((root) => [
      ...root.querySelectorAll(selector),
    ]);

  // The range the reader actually drew. Chrome keeps the legacy Range in the light DOM: a
  // drag wholly inside a widget's shadow tree comes back with `commonAncestorContainer` at
  // BODY and its ends clamped to the host, so `sel.toString()` says the right words while
  // every node the capture would index says the wrong place. That is the one failure mode
  // worth naming twice — not a refusal, which the fence rule turns into a message to the
  // author, but a quote anchored somewhere the reader never pointed.
  //
  // `getComposedRanges` is the only thing that answers truthfully, and it answers only for
  // the roots it is handed, which is why the declaration (x-shadow) and not a sweep decides
  // what is passed. A selection that starts in one tree and ends in another is left to the
  // light-DOM range on purpose: a Range cannot hold ends in two roots, and a quote running
  // from the page's prose into a widget's shadow is exactly what the fences already refuse.
  function pageRange(sel) {
    const plain = sel.getRangeAt(0);
    if (typeof sel.getComposedRanges !== "function") return plain;
    const shadowRoots = pageShadowRoots();
    if (!shadowRoots.length) return plain;
    const [composed] = sel.getComposedRanges({ shadowRoots });
    if (!composed) return plain;
    const { startContainer, startOffset, endContainer, endOffset } = composed;
    if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
    const range = document.createRange();
    range.setStart(startContainer, startOffset);
    range.setEnd(endContainer, endOffset);
    return range;
  }

  // Whether a range covers a node, asked so a shadow tree answers the same as the light
  // DOM it renders in place of. `intersectsNode` compares within one tree, so every node
  // inside an x-shadow widget says no to a range drawn out in the document — and a drag
  // from the paragraph above a diff to the one below it would come back holding the two
  // paragraphs joined, with the lines the reader dragged straight over missing from the
  // quote and still sitting between them in the reading, so the search could never find
  // it. The tree renders where its host stands, so the host is what the question is really
  // about: climb to whichever ancestor shares the range's root, and ask there.
  function coveredBy(range, node) {
    const root = range.commonAncestorContainer.getRootNode();
    let n = node;
    while (n && n.getRootNode() !== root) n = n.getRootNode().host;
    return Boolean(n) && range.intersectsNode(n);
  }

  // The segments a selection covers, clipped to where it starts and ends.
  function segmentsIn(range) {
    const root = range.commonAncestorContainer;
    const whole = textNodesUnder(
      root.nodeType === Node.ELEMENT_NODE ? root : root.parentElement,
    );
    const segments = [];
    for (const { node, end: length } of whole) {
      if (!coveredBy(range, node)) continue;
      const start = node === range.startContainer ? range.startOffset : 0;
      const end = node === range.endContainer ? range.endOffset : length;
      if (end > start) segments.push({ node, start, end });
    }
    return segments;
  }

  // Segments as prose — what a comment stores as its quote, and what a reading position
  // remembers. A space goes in wherever a block boundary falls between two segments, so a
  // passage crossing two paragraphs doesn't read as one run-on word. Whitespace collapses,
  // since the same passage carries the author's line wraps in the source and the rendering's
  // on screen. Sliced by code point, because half a surrogate pair is a character no UTF-8
  // file can hold. Where the spaces landed is cosmetic to the search: a quote's own
  // whitespace is elastic to findQuote, so nothing downstream depends on this.
  // The block a node reads as part of, and null where it belongs to no block of its own —
  // which is a different answer from "its parent", and the two callers want different ones.
  const blockAt = (node) => closestAcross(node, TEXT_BLOCK);
  const blockOf = (node) => blockAt(node) ?? upFrom(node);
  // One collapse class, stated outright and spelled to the same set passages.py's
  // COLLAPSE_CHARS enumerates: JS's \s and Python's str.isspace() disagree at the
  // edges — U+FEFF is whitespace to JS alone, U+0085 and U+001C–001F to Python
  // alone — and a page carrying one of those in prose read differently on the two
  // sides, so a `leaf comment` quote could be written against text this runtime
  // never produces. (trim() removes exactly this class, so it needs no twin.)
  const COLLAPSE =
    /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
  function quoteFrom(segments) {
    let text = "";
    segments.forEach((seg, i) => {
      if (i && blockOf(seg.node) !== blockOf(segments[i - 1].node)) text += " ";
      text += seg.node.data.slice(seg.start, seg.end);
    });
    return [...text.replace(COLLAPSE, " ").trim()].join("");
  }
  // Cutting one to length is the caller's business and always by code point: half a surrogate
  // pair is a character no UTF-8 file can hold, and a quote is written to one.
  const cut = (text, from, to) => [...text].slice(from, to).join("");

  // What an element says, read the way this file reads the page everywhere else. A widget
  // wanting the words in one of its own slots asks for them here rather than through
  // `textContent`, because the two differ: the paint pass writes a hidden line into any text
  // block that carries a comment, including blocks inside a widget, and `textContent` returns
  // it. A suggestion labelled that way offered to accept “Retry three times. 1 comment”.
  const says = (el) => quoteFrom(textNodesUnder(el));
  // The other question, and a different answer: what the *author* wrote here, with
  // everything an upgrade generated left out. The version diff asks it because the base
  // version it compares against has no generated nodes at all; a widget asks it to name
  // one of its own parts, where `says` would hand back the widget's own declared labels
  // along with the words — a picked row's mark is the page speaking, so it is in the
  // reading a user points at and out of the row's name.
  const wrote = (el) => quoteFrom(textNodesUnder(el, authored(el)));

  // A passage as one Range: what paints it, and what measures it for a scroll.
  function rangeOf(segments) {
    const range = document.createRange();
    range.setStart(segments[0].node, segments[0].start);
    range.setEnd(segments.at(-1).node, segments.at(-1).end);
    return range;
  }

  // Find `quote` among `segments`; returns the segments it covers, or none. The quote's own
  // whitespace is treated as elastic and the page's is not, which is the asymmetry the
  // problem actually has. The same passage gets written down with a break where the source
  // wrapped it, with one where the rendering broke a block, and with none where two blocks
  // abut, so a gap in the quote has to match any gap in the page or none at all — otherwise
  // every producer has to agree on whitespace, and that agreement is the one this file kept
  // getting wrong. The converse is not true: where the quote runs two words together the
  // page may not, or a short quote starts matching inside longer words — "never" finding the
  // tail of "on every", in a different paragraph.
  // So a gap has to match *something* that separates words. Whitespace is one; an element
  // boundary is the other, and it leaves no character behind, which is why the raw text is
  // built with one standing in for it. Between the characters of a single word only a
  // boundary may fall — `<strong>bold</strong>text` reads as one word and is quoted as one —
  // and without that floor a gap could match nothing at all, so "set up" would find "setup"
  // in an earlier sentence and anchor there for good.
  const EDGE = "\u0000"; // no document holds one, so it can't collide with page text
  // A quote names text, not a place, and a page is free to say the same thing twice. Where it
  // does, the words on either side decide which occurrence was meant. A unified diff holds
  // the same line on both sides by construction, so without this, commenting on a fixed line
  // marked the broken one — the user's objection attached to the code they were objecting
  // to, and stored that way. Section scoping cannot reach it, because both sides of a diff
  // live under one id. Context rather than an offset: an offset goes stale silently when the
  // page is revised, while neighbours can be checked against the page as it now stands — see
  // `holds` for what checking them means, and what it deliberately refuses to do.
  // Anchors written before this carry none: their quote resolves only when it has a
  // single candidate, since there is no evidence that can identify one repeated copy.
  // The characters of raw[lo..hi) as segments, so a neighbourhood can be read back with the
  // same function that wrote it down. Edges hold no character and are simply absent.
  function spanOf(origin, lo, hi) {
    const out = [];
    for (let i = Math.max(0, lo); i < Math.min(origin.length, hi); i++) {
      const at = origin[i];
      if (!at) continue;
      const last = out.at(-1);
      if (last && last.node === at.node && last.end === at.offset)
        last.end = at.offset + 1;
      else out.push({ node: at.node, start: at.offset, end: at.offset + 1 });
    }
    return out;
  }
  // Context identifies a passage only when its neighbours are still exactly what they were.
  // A partial match is not weak evidence for the right copy — it is evidence the page moved
  // on, and acting on it is how a comment ends up somewhere it was never made: a version that
  // rewrote the sentence beside the anchored copy left an untouched copy elsewhere matching
  // better, and the comment followed it there. Demanding the whole stored context prevents
  // that: without one exact contextual match, only a quote with a sole candidate resolves;
  // repeated candidates detach rather than inheriting document order.
  //
  // Rare, not impossible. The bar is however much was stored, and the capture reads the
  // neighbours out of the whole document — a section is a filter on where a passage may sit,
  // not on what surrounds it — so both sides are full except against the document's own
  // ends. Anchors written before context reached past the section carry a side clipped at
  // that edge; they confirm at that shorter bar, which is the bar they were stored under.
  //
  // The bar is what the capture actually produces, not a number picked to fit: across every
  // selection in the shipped examples, an unmodified page confirms its stored context in full.
  //
  // An empty side is the case worth stating, because reading it as an absent constraint is
  // what sends a comment to a copy it was never made on. The capture reads the whole
  // document, so a side comes out empty only where the passage had nothing at all beside it:
  // the top or bottom of the page, the one place no capture can give two sides to. That is
  // not a missing constraint but the tightest one there is, and it is checkable — a candidate
  // confirms it by also having nothing there, which exactly one occurrence does. Refusing to
  // read it that way handed the last copy's mark to the first.
  const holds = ({ origin, fences }, at, want, before) => {
    // One character is all it takes to refute an empty side, and asking for none would answer
    // with none: doubling zero never grows.
    const there = neighbourhood(origin, fences, at, want.length || 1, before);
    if (!want) return there === "";
    return before ? there.endsWith(want) : there.startsWith(want);
  };
  // As much collapsed text as the caller asked for, however much raw text that takes.
  // A fixed raw budget reads less than the capture wrote wherever whitespace runs dense — an
  // indented line inside a <pre> — and the right occurrence then confirms none of its own
  // neighbours.
  //
  // Counted in code points, which is the unit both captures write in: `cut` slices the
  // window this returns by code point, and passages.py's reading of the same passage slices
  // a Python string, which has no other unit. Counting code units here stopped the growth
  // early on any neighbourhood holding an emoji — the window reached 24 of them while
  // holding 23 characters — so the browser stored a prefix a character short of the one the
  // file's reading stores for that same passage, and the two captures wrote different
  // anchors for one passage. `holds` asks in the other unit (`want.length`, the stored
  // string's own, which is what its endsWith compares in), and that is an over-decision this can
  // only over-satisfy: reaching N code points takes at least N code units, so its window is
  // never the one short of confirming that a repeated anchor would detach over.
  function neighbourhood(origin, fences, at, want, before) {
    const edge = before
      ? (fences.filter((f) => f <= at).at(-1) ?? 0)
      : (fences.find((f) => f >= at) ?? origin.length);
    for (let raw = want * 2; ; raw *= 2) {
      const lo = before ? Math.max(edge, at - raw) : at;
      const hi = before ? at : Math.min(edge, at + raw);
      const text = quoteFrom(spanOf(origin, lo, hi));
      if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
    }
  }
  // What the page says, once, as one string with a way back to the nodes it came from. Built
  // per pass rather than per anchor: every anchor a pass places is asking about the same
  // document, and the pass is what fixes which document that is — resolving each against its
  // own fresh reading would let two marks in one pass answer for two different pages, since a
  // widget can upgrade between them. Forty threads on a 13k-character page also spent it
  // forty times: 9.3ms of index building per pass, besides the forty tree walks feeding
  // it, against 1.5ms for the one read that replaces them.
  function pageText() {
    let raw = "";
    const origin = []; // origin[i] = {node, offset} for raw[i]; null for an edge
    const positions = new WeakMap(); // text node -> its offset-zero position in raw
    const fences = new Set();
    const segments = textNodesUnder(document.body);

    // Generated page-words that the registry does not model are their own passage
    // cells. Controls and the hidden comment count contain no accepted text and never
    // become fences; x-says spans are already present in the file-side reading.
    const dynamicWords = new WeakSet();
    for (const seg of segments) {
      const generated = elementOver(seg.node).closest("[data-lf-gen]");
      if (!generated) continue;
      const attr = generated.getAttribute("data-lf-said");
      const hostEntry = registry[generated.parentElement?.localName];
      const declared = attr && hostEntry?.["x-says"]?.[attr];
      if (!declared) dynamicWords.add(generated);
    }
    // Climbing crosses the shadow boundary (upFrom), and that is what keeps an x-shadow
    // widget fenced. The parts were remembered off the light DOM before any module ran,
    // so nothing inside a shadow tree is in either set; a climb that stopped at the root
    // would put a diff's lines in no cell at all, which reads as ordinary page prose and
    // lets a quote run from the paragraph above straight into the first changed line. One
    // move further up finds the host, which is the opaque root it always was.
    const cellOf = (node) => {
      for (let el = upFrom(node); el; el = upFrom(el)) {
        if (dynamicWords.has(el)) return el;
        if (opaquePassageParts.has(el) || opaquePassageRoots.has(el)) return el;
      }
      return null;
    };

    let previousCell = null;
    let started = false;
    for (const seg of segments) {
      const cell = cellOf(seg.node);
      if (!started) {
        if (cell) fences.add(0);
        started = true;
      } else {
        if (cell !== previousCell && (cell || previousCell)) fences.add(raw.length);
        origin.push(null);
        raw += EDGE;
      }
      positions.set(seg.node, raw.length - seg.start);
      for (let i = seg.start; i < seg.end; i++) {
        origin.push({ node: seg.node, offset: i });
        raw += seg.node.data[i];
      }
      previousCell = cell;
    }
    if (previousCell) fences.add(raw.length);
    return { raw, origin, positions, fences: [...fences].sort((a, b) => a - b) };
  }
  // Where a passage's segments start and stop in that reading, as [start, stop). A passage
  // is `{node, start, end}` segments and every question about the region it covers is asked
  // in the reading's own coordinates, so the join between the two is one function — the
  // capture writing an anchor's neighbours and the snap widening a drag both ask it. No
  // segments is the document's own start: a selection that covers no quotable character has
  // a position and no extent.
  function spanIn(reading, segments) {
    const first = segments[0];
    const last = segments.at(-1);
    const start = first ? reading.positions.get(first.node) + first.start : 0;
    return [start, last ? reading.positions.get(last.node) + last.end : start];
  }
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // How much of a quote the search compiles into its pattern. The bound is the pattern's,
  // never the passage's: one expression covering every word of a long passage is a term
  // per character, and V8 refuses to compile one that long at all — a ceiling a reader
  // reaches by selecting a page and pressing c. Measured on the corpus: 1.3ms at this
  // length, 11.6ms at five thousand characters, and a SyntaxError at twelve. So the lead
  // finds the candidates and the rest of the quote is walked against the text from each,
  // which is a comparison per character rather than a term, and the search stays flat in
  // the passage's length instead of ending at a wall.
  const LEAD_CAP = 400;
  // The rest of a quote, matched from `at` by the pattern's own rules: any run of
  // whitespace or edges between words, an edge free to fall between two characters of
  // one. Answers where the passage ends, or -1 where the text stops saying it.
  function confirmRest(raw, at, words) {
    let i = at;
    for (const w of words) {
      const gap = i;
      while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw[i]))) i++;
      if (i === gap) return -1; // two words the text runs together are not these two
      for (const ch of w) {
        while (raw[i] === EDGE) i++;
        if (!raw.startsWith(ch, i)) return -1;
        i += ch.length;
      }
    }
    return i;
  }
  function findQuote(text, quote, anchor, within) {
    const { raw, origin } = text;
    const words = quote.trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    // Whole words up to the cap, and never none: a single word longer than it is still
    // the only lead there is, and one that spent the cap exactly is not worth a term
    // the walk would take anyway.
    const lead = [];
    for (let spent = 0; words.length > lead.length;) {
      const next = words[lead.length];
      if (lead.length && spent + next.length > LEAD_CAP) break;
      lead.push(next);
      spent += next.length + 1;
    }
    const rest = words.slice(lead.length);
    const pattern = new RegExp(
      lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
      "g",
    );
    // A unique exact-context occurrence wins. If no context survives, a sole quote
    // occurrence is still identifiable; two are not. Document order is not identity:
    // guessing the first copy after the intended one's neighbours changed quietly moves
    // a comment to words it was never made on. matchAll steps past each lead, so two
    // occurrences overlapping within it are one candidate — which is the lead's own
    // repetition and not the passage's, since the walk still has to confirm the rest.
    const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
    const candidates = [];
    const exact = [];
    for (const at of raw.matchAll(pattern)) {
      const stop = confirmRest(raw, at.index + at[0].length, rest);
      if (stop === -1) continue;
      if (
        within &&
        !(
          containsAcross(within, origin[at.index].node) &&
          containsAcross(within, origin[stop - 1].node)
        )
      )
        continue;
      const hit = { from: at.index, to: stop };
      candidates.push(hit);
      if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false))
        exact.push(hit);
    }
    const found =
      exact.length === 1
        ? exact[0]
        : exact.length === 0 && candidates.length === 1
          ? candidates[0]
          : null;
    // The characters the match covers, cut out of the index the same way a neighbourhood is —
    // walking the segments a second time to rebuild the span would be a second answer to
    // "which text is this", and the two disagree wherever an edge falls inside the match.
    return found ? spanOf(origin, found.from, found.to) : [];
  }

  // Every occurrence of a reader's search, as passages in the page reading. This is not
  // anchor resolution: a search is allowed to find repeated words, while a stored anchor
  // must identify one occurrence or detach. It does keep the passage reader's other rules —
  // elastic whitespace and element edges, and no match crossing an opaque passage fence —
  // so choosing a result produces exactly the kind of segments capture and resolution use.
  function findText(text, query) {
    const words = query.trim().split(/\s+/u).filter(Boolean);
    if (!words.length) return [];
    const pattern = new RegExp(
      words.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
      "giu",
    );
    const out = [];
    for (const match of text.raw.matchAll(pattern)) {
      const from = match.index;
      const to = from + match[0].length;
      if (text.fences.some((fence) => from < fence && fence < to)) continue;
      out.push(spanOf(text.origin, from, to));
    }
    return out;
  }

  function contextAround(text, segments, length = 28) {
    const [start, end] = spanIn(text, segments);
    const before = neighbourhood(text.origin, text.fences, start, length, true);
    const after = neighbourhood(text.origin, text.fences, end, length, false);
    const beforeLength = [...before].length;
    return {
      before: cut(before, Math.max(0, beforeLength - length), beforeLength),
      after: cut(after, 0, length),
    };
  }

  const passages = {
    settlementSlots,
    renderRetired,
    settledAway,
    DATUM,
    uiInside,
    inUi,
    inChrome,
    pageWords,
    layerPart,
    TEXT_BLOCK,
    elementOver,
    under,
    authored,
    textNodesUnder,
    upFrom,
    containsAcross,
    closestAcross,
    elementById,
    elementFromPointAcross,
    elementOver,
    pageQueryAll,
    pageRange,
    segmentsIn,
    blockAt,
    blockOf,
    COLLAPSE,
    quoteFrom,
    cut,
    says,
    wrote,
    rangeOf,
    holds,
    neighbourhood,
    pageText,
    spanIn,
    findQuote,
    findText,
    contextAround,
  };
  publishedPassages = passages;
  return passages;
}
