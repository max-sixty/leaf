/* Travel to a place on the page: open what hides it, scroll to it, focus it, and
 * record the departure in history.
 *
 * A place is what an anchor names (readings/anchor-resolution.js): an element with an id, a
 * passage inside one, or a part of a widget, such as a projected datum or a visual
 * part. A thread travels to its anchor's place, a fragment link to its element or to
 * the part a widget's key names, an obligation to its own arrival region, and a
 * module's `navigateToDatum` to the part its reference names. Every route shares three
 * steps: `revealAddressed` draws the part (`revealAnchor` each part an anchor names),
 * `reveal` opens what holds it and what takes focus, and `clearFor` puts away a surface that would stand
 * over it where it lands (panel/floating-panel.js). Each
 * route says where it lands, what takes focus and how to scroll; `arrive` then does
 * the reveal, clearing, painting, focus and scrolling, and no route does them itself.
 * When the reveal replaces a visible view, the destination lands at once instead of
 * scrolling from the old view's position. A destination inside a box the browser
 * skips while it is out of view (`content-visibility: auto`), such as a run of a long
 * text document's lines, also lands at once, since a glide across such a series draws
 * each box it passes, which took over two seconds on a long text. The box holding the
 * destination is drawn for the jump (`drawForLanding`), so the landing doesn't depend
 * on how well the box's estimated size matches its drawn one.
 *
 * Travel gets the current threads and the synchronous thread refresh from the
 * application root, so geometry code never imports the presenter. A navigation step keeps the
 * user's original intent while data loads, the target opens and the page paints;
 * newer input or another navigation step cancels its landing, but not the loading. Each navigation step
 * records where the user is before it moves anything. Every arrival that succeeds and
 * moves the page or lands the user on a stop they weren't on adds that departure to
 * history (`prepareNavigationStep`), so Back returns the user to the item they were on,
 * one step at a time, as Back does after a followed link, which the browser adds as an
 * entry though its target already shows. Leaf once let a run of steps share one entry while
 * the last landing still showed, so one Back undid a whole `t` or `m` walk. That skipped
 * the item a step left: after `t` then `m`, Back passed over the thread, and once the
 * user answered an obligation, which takes it out of On Me, neither Back nor Shift+m
 * returned to it. Limiting the sharing to one walk still missed the second case, so no
 * steps share an entry. Rejected: a step only where the arrival moves the page, under
 * which the first `t` to a thread on screen added none, so Back from its card left the
 * page, and a walk among stops the window shows left no way back along it. A fragment
 * link's navigation step (`followFragment`) uses the history entry the browser added for the link as
 * its departure, and Back or Forward to a place the page has since hidden
 * (`returnToFragment`) is a navigation step that adds no entry.
 */

/** @import { EditorDestination } from "../records/drafts.js" */

import { selectEnds } from "../dom/native-selection.js";
import { focusElement, focused } from "../dom/focus.js";
import { referencedProjection, requireReference } from "../readings/references.js";
import { fragmentUrl } from "../base/anchor-coordinate.js";
import {
  addressedElements,
  addressedFocus,
  fragmentAddress,
  fragmentTarget,
  resolveAnchor,
  revealAddressed,
  revealAnchor,
  sectionOf,
  awaitsDrawing,
} from "../readings/anchor-resolution.js";
import { placeHolder, showsContents } from "../dom/geometry.js";
import { scrollBehavior } from "../dom/motion.js";
import { renderedParent, under } from "../lib/shadow-tree.js";
import { nextFrame } from "../lib/frame-pass.js";
import { unconcealedReadingRegions } from "../readings/reading-regions.js";
import { prepareEntry, replaceEntry } from "../records/history.js";
import { pageScroller, stopBrowserScroll } from "../dom/scrolling.js";
import {
  alreadyShown,
  fitsWhole,
  landedBox,
  scrollIntoView,
} from "../readings/landing-scroll.js";
import { reveal } from "../dom/widget-elements.js";
import { threadNamed } from "../records/thread/state.js";
import { restrictUserIntent, retainUserIntent } from "../dom/user-intent.js";
import {
  targetElement,
  targetPlace,
  targetSegments,
} from "../readings/resolved-target.js";
import { passageStart, rangeOf } from "../readings/passages.js";
import { livePoint } from "../readings/pointed-place.js";
import { notice } from "../transport/notifications.js";

// The browser's rule for landing the element a fragment names: its start at its
// scroller's landing edge, which a sticky header's stated height keeps clear. Travel
// applies it where the browser's own landing does not reach the element: at an arrival
// the page reshapes after the browser landed it (version.js, `aimArrival`), and at a
// traversal, where the browser restores an offset instead (`returnToFragment`).
/** @param {Destination} element */
export function scrollToFragment(element) {
  scrollIntoView(element, { behavior: "auto", block: "start" });
}

// Whether the page shows the place a fragment names (readings/anchor-resolution.js,
// `fragmentAddress`). A widget's key names no shown place until the widget draws its
// part and shows it: a file view keeps an unselected file's node hidden until found,
// so a node existing is not the widget having drawn it. A traversal and a load ask the
// widget for the part only where this is false.
/** @param {ReturnType<typeof fragmentAddress>} address */
export const fragmentShown = (address) =>
  Boolean(address?.place && showsContents(address.place));

/** @import { Destination, ScrollPlacement, Arrival, NavigationStep, ArrivalOptions } from "../dom/arrival-plan.js" */
/** @import { UserIntent } from "../dom/user-intent.js" */
/** @typedef {import("../base/held-place.js").Caret} Caret
 * @typedef {{anchors: Pick<import("../records/thread/placement.js").ThreadPlacements, "placedAt">,
 * refreshThread: () => unknown, focusForNavigation: typeof import("../dom/focus.js").focusDestination,
 * threadFocusTarget: ReturnType<typeof import("../records/thread/destination.js").createThreadDestinations>["threadFocusTarget"],
 * clearFor: (destination: Arrival, landed: DOMRect | null) => unknown, announce: (message: string) => unknown}} TravelOptions
 */
/** @param {TravelOptions} travel */
export function createAnchorTravel({
  anchors,
  refreshThread,
  focusForNavigation,
  threadFocusTarget,
  clearFor,
  announce,
}) {
  let travelIntent = 0;
  const retainTravel = (retained = retainUserIntent()) => {
    const intent = ++travelIntent;
    return restrictUserIntent(retained, () => intent === travelIntent);
  };

  // Resolve fresh after exposure, presentation and focus. A replaced view lands
  // immediately so it never paints at the old view's offset; final placement alone
  // commits the prepared departure, after the destination still stands through focus.
  // The destination is laid out by then, so where it will land can be read
  // (`landedBox`), or where it stands for an arrival that scrolls nothing, and a
  // surface that would stand over it there goes before focus moves to it (`clearFor`):
  // closing a view the user stood in hands focus on, which the retained intent carries.
  // An empty scroll list preserves the reader's existing scroll, as a continuation
  // can request. Visibility conditions on a placement are read after cancellation.
  /** @param {() => Arrival | null | undefined} resolve @param {ArrivalOptions} options */
  async function arrive(resolve, { intent, present = null, departure = null }) {
    if (!intent()) return false;
    const initial = resolve();
    if (!initial) return false;
    // Every new navigation step takes over the outgoing native placement, and lands from
    // where a glide of Leaf's is headed (dom/scrolling.js, `stopBrowserScroll`). Read
    // geometry only after the stopped scroll's last compositor update has passed;
    // another gesture during that wait retains the place it chose.
    if (initial.scroll.length)
      await stopBrowserScroll(
        new Set([
          pageScroller,
          ...unconcealedReadingRegions().map((region) => region.body),
        ]),
      );
    if (!intent()) return false;
    const first = resolve();
    if (!first || !intent()) return false;
    const holder = placeHolder(first.where);
    if (!holder) return false;
    // What takes focus is shown too, as a message a closed fold holds in a thread
    // whose place the arrival lands on.
    const disclosures = [
      holder,
      ...(first.focus ? [focusElement(first.focus)] : []),
      ...(first.reveal ?? []),
    ].map((target) => reveal(target, intent));
    const replacedView = disclosures.some((disclosure) => disclosure.replacedView);
    const place = (complete = false) => {
      let completed = false;
      intent.handoff(() => {
        const destination = resolve();
        if (!destination?.where) return;
        clearFor(
          destination,
          destination.scroll.length ? landedBox(destination.where) : null,
        );
        if (destination.focus)
          focusForNavigation(
            destination.focus,
            "move",
            destination.caret === undefined ? {} : { caret: destination.caret },
          );
        const current = resolve();
        if (!current?.where) return;
        if (complete) departure?.commit();
        // A selection the arrival names becomes the page's; `null` clears the page's.
        if (current.selection === null) getSelection()?.removeAllRanges();
        else if (current.selection) {
          const { range, backward } = current.selection;
          /** @type {[Node, number]} */
          const head = [range.startContainer, range.startOffset];
          /** @type {[Node, number]} */
          const tail = [range.endContainer, range.endOffset];
          selectEnds(backward ? tail : head, backward ? head : tail);
        }
        for (const placement of current.scroll) placeScroll(placement, replacedView);
        completed = true;
      });
      return completed;
    };
    if (replacedView) place();
    await Promise.all(disclosures.map((disclosure) => disclosure.ready));
    if (!intent()) return false;
    if (present) await present();
    if (!intent()) return false;
    return place(true);
  }

  // A remembered passage carries semantic words, never retained DOM endpoints.
  // Resolve on each side of reveal/focus so a revision cannot leave stale nodes in
  // the native selection. Ordinary arrival owns clearance, history and reading band.
  /** @param {import("../readings/anchor-resolution.js").CapturedAnchor | import("../../types/domain.js").Anchor} anchor @param {{backward: boolean, intent: UserIntent}} options */
  async function restoreSelection(anchor, { backward, intent }) {
    const mayArrive = retainTravel(intent);
    /** @returns {Arrival | null} */
    const resolve = () => {
      const target = resolveAnchor(anchor);
      const segments = targetSegments(target);
      if (!segments.length) return null;
      const range = rangeOf(segments);
      return {
        where: range,
        focus: targetPlace(target),
        selection: { range, backward },
        scroll: [{ at: range }],
      };
    };
    const destination = resolve();
    const datum = anchor.datum;
    const source = datum ? sectionOf(anchor) : null;
    if (!destination && !source) return false;
    const departure = prepareNavigationStep();
    departure.plan(destination?.where ?? source, {
      there: (readable) => Boolean(destination && readable(destination.where)),
    });
    if (source && datum) {
      const hydration = revealAnchor(source, anchor);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
    }
    return arrive(resolve, { intent: mayArrive, departure });
  }

  // A remembered editor starts from its authored place, before a hidden editor is
  // materialized. Its owner opens without focus; the ordinary arrival owns surface
  // clearance, disclosure, presentation, caret and reading placement. A materializer
  // may return its keyed focus-handoff release, retired after this landing. Opening
  // supplies geometry without moving the viewport: the final arrival places editor and
  // passage together, taking over any native smooth travel still in progress. With
  // `onFrame`, the arrival puts the user on the box the editor stands in rather than in
  // it (`frame`), and answers with that box. Words selected elsewhere go, as focusing
  // the editor drops them (annotations/composing/surface.js, `commentOnTarget`), so the box is
  // where the user is and where `c` writes.
  /** @param {() => EditorDestination | null | undefined} resolve
   * @param {{intent: ReturnType<typeof retainUserIntent>, caret: import("../base/held-place.js").Caret | null, onFrame?: boolean, travel?: boolean}} options */
  async function arriveEditor(
    resolve,
    { intent, caret, onFrame = false, travel = true },
  ) {
    const mayArrive = retainTravel(intent);
    const destination = resolve();
    if (!destination?.where) return null;
    // An editor opened where the user stands (`travel: false`) is no departure.
    const departure = travel ? prepareNavigationStep() : null;
    departure?.plan(destination.where);
    let release = () => {};
    await arrive(
      () => {
        const current = resolve();
        if (!current) return null;
        const box = onFrame ? (current.frame?.() ?? null) : current.input();
        return {
          where: current.where,
          focus: box,
          caret: onFrame ? null : caret,
          ...(onFrame && { selection: null }),
          // The place the words are about comes into view first and the editor
          // last, so a place taller than the window, as a reviewed case is on a
          // phone, never scrolls the caret back out of it.
          scroll: box
            ? [
                {
                  at: current.where,
                  behavior: "instant",
                  when: () =>
                    !alreadyShown(current.where, { block: "center" }) ||
                    !alreadyShown(box),
                },
                // The subject and editor can occupy different parts of a tall
                // page. Finish on the box the user asked to write in.
                { at: box, block: "nearest", behavior: "instant" },
              ]
            : [{ at: current.where, behavior: "instant" }],
        };
      },
      {
        intent: mayArrive,
        departure,
        present: async () => {
          const current = resolve();
          if (!current) return;
          if (current.open)
            mayArrive.handoff(() => {
              const opened = current.open?.();
              if (opened) release = opened;
            });
          await current.present?.();
        },
      },
    );
    release();
    if (!mayArrive()) return undefined;
    const arrived = resolve();
    return (onFrame ? arrived?.frame?.() : arrived?.input()) ?? null;
  }

  // Travel's departure transaction, the one rule for whether a route that travels is a
  // Back step: it is where it moves the page, or lands the user on a stop they weren't
  // on, which is where its arrival puts focus on something the user's focus wasn't in
  // (records/current-target.js, "on a stop"). So every stop of a walk is a step, as each
  // followed link is, though the stop already shows: the first `t` to a thread on
  // screen, which once left Back leaving the page from the card it opened, and `m` or
  // `t` between stops the window already shows. An arrival that puts focus nowhere new,
  // as on the stop the user is on, is a step only where it moves the page. A route that
  // opens or puts away a view where the user stands doesn't travel (`travel: false`,
  // records/thread/destination.js) and takes no departure. Capture where the user is before any
  // reveal; plan answers whether the arrival moves the page, which a caller may use to
  // decide its scroll, and arrive commits only its successful handoff, after it has
  // placed focus. A step commits once, by the last plan made before it, so a route that
  // lands in two places in turn, as a thread's view and then its passage, commits after
  // the last landing it reached. Failure or newer intent leaves history untouched. A destination not
  // yet placed (a datum a widget has yet to hydrate) is somewhere else. `there` is the
  // caller's reading of already being there where it asks more than the destination's
  // own (an obligation's arrival region), built on the reading it is handed.
  /** @param {URL} [url] @returns {NavigationStep} */
  function prepareNavigationStep(url) {
    // Travel lands a destination at its start or centre, alike for one taller than its
    // room, so it is already there where that landing would move nothing.
    /** @param {Destination} where */
    const travelShown = (where) => alreadyShown(where, { block: "start" });
    const write = prepareEntry();
    const left = focused();
    /** @type {boolean | undefined} */
    let moving;
    return {
      plan(where, { there } = {}) {
        moving = !(where && (there ? there(travelShown) : travelShown(where)));
        return moving;
      },
      commit() {
        if (moving === undefined) return;
        const on = focused();
        const stayed = on === left || (left !== document.body && under(left, on));
        if (moving || !stayed) write(url ?? window.location.href);
        // No departure, but the entry the user stays on now names where they are.
        else if (url) replaceEntry(url);
        moving = undefined;
      },
    };
  }

  // A fragment link naming a place of the page, an element or a widget's key, is a
  // navigation step there whose departure is the browser's: the navigation has already
  // added the entry Back returns to, whoever
  // followed it — a press on a page link or a reply's reference, a Go-to hint. What the
  // platform lacks for a page place is travel's to add, the same as for any other
  // destination: draw a key's part, clear the surface hiding it, and reveal what holds
  // it, which reaches a widget's own disclosure as well as `hidden="until-found"` (a
  // worker in a shut goal is `display: none`, and the browser landed on nothing). It
  // then lands by the browser's fragment placement rule and puts focus
  // at the destination. Scrolling alone can leave the source link's caret as the
  // user's current location, so subsequent commands would still act from the source.
  // Every activation route shares this arrival rather than supplying its own focus. A
  // fragment naming nothing here is not claimed, and the browser keeps it.
  /** @param {URL} url */
  function followFragment(url) {
    return fragmentTarget(url.hash) && fragmentNavigationStep(url, true);
  }

  // Back or Forward restores the offset the entry was left at (records/history.js), which is
  // where the user was reading while the page still holds the place the entry's
  // fragment names. Once that place is no longer shown, closed since in a tab, a
  // disclosure or a widget's own shut state, the offset was read over a page that has
  // changed, and restoring it lands on whatever now sits at that pixel. The fragment is
  // then the one thing the entry still says, so the traversal is a navigation step to it that
  // departs by no new entry: the same clearing and reveal as a followed link. A widget's
  // key whose part the widget no longer draws, since the user has picked another of its
  // items, names such a place too. The browser's own landing on a traversal is that
  // offset, so travel lands the place by the fragment rule itself (`scrollToFragment`).
  // It runs under the intent of the traversal's restoration (records/history.js), which a
  // later navigation ends.
  /** @param {URL} url @param {ReturnType<typeof retainUserIntent>} intent */
  function returnToFragment(url, intent) {
    const address = fragmentAddress(url.hash);
    if (!address) return null;
    return fragmentShown(address) ? null : fragmentNavigationStep(url, false, intent);
  }

  // A key's part is asked for first, as `navigateToDatum` asks for it, and a key the
  // widget draws nothing for lands on the widget.
  /** @param {URL} url @param {boolean} focus @param {ReturnType<typeof retainUserIntent>} [intent] */
  function fragmentNavigationStep(url, focus, intent) {
    const mayArrive = retainTravel(intent);
    return async () => {
      const address = fragmentAddress(url.hash);
      const drawing =
        address?.key == null ? null : revealAddressed(address.element, address.key);
      if (drawing?.then) await drawing;
      if (!mayArrive()) return false;
      return arrive(
        () => {
          const where = fragmentTarget(url.hash);
          const keyed = fragmentAddress(url.hash);
          const focusing =
            keyed?.key != null && keyed.place
              ? addressedFocus(keyed.element, keyed.key)
              : where;
          return (
            where && {
              where,
              focus: focus ? focusing : null,
              scroll: [{ at: where, block: "fragment" }],
            }
          );
        },
        { intent: mayArrive },
      );
    };
  }

  /** @param {Element} owner @param {string} attribute @param {string} key @param {{success?: string, missing?: string, focus?: boolean}} [options] */
  async function navigateToDatum(
    owner,
    attribute,
    key,
    { success = "", missing = "", focus = true } = {},
  ) {
    const mayArrive = retainTravel();
    requireReference(owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) notice(missing);
      return false;
    }

    // The entry names the key, so a reload or a copied URL reaches the same part.
    const url = new URL(fragmentUrl(source, key));
    const departure = prepareNavigationStep(url);

    // The widget owns filters, lazy projection, and the state a visual draws. Ask it to
    // make the key reachable before interpreting DOM presence.
    const hydration = revealAddressed(source, key);
    if (hydration?.then) await hydration;
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) notice(missing);
      return false;
    }
    const destination = addressedElements(source, key)[0] ?? null;

    if (!destination) {
      // An absent address is no destination: keep the departure and its history,
      // rather than landing on the containing widget as if the request succeeded.
      if (missing) notice(missing);
      return false;
    }
    departure.plan(destination);
    const arrived = await arrive(
      () => {
        const source = referencedProjection(owner, attribute);
        const where = source && addressedElements(source, key)[0];
        return (
          where && {
            where,
            focus: focus ? addressedFocus(source, key) : null,
            scroll: [
              {
                at: where,
                block: "start",
                when: () => !alreadyShown(where, { block: "start" }),
              },
            ],
          }
        );
      },
      { intent: mayArrive, departure },
    );
    if (mayArrive()) {
      if (arrived && success) announce(success);
      else if (!arrived && missing) notice(missing);
    }
    return arrived;
  }

  // Reading-region membership also covers fixed chrome, but its viewport position does
  // not move with that region, so a fixed boundary ends the scrollers that move it
  // (`scrollersOf`); a scroller inside that boundary still owns its ordinary descendants.

  // The box `at` stands in that the browser skips while it is out of view, or null,
  // read from the box's style rather than from whether it is skipped now: the boxes
  // between it and the view can be skipped while its own is drawn, as naming the
  // destination's anchor for its thread's card draws it. A box an earlier landing still
  // holds drawn (`drawForLanding`) counts though its style reads `visible`: read from
  // the style alone, a second `t` within those frames, as a held key repeats, glided
  // and left the line 1,220 px out of view.
  /** @param {Element | Range} at */
  const skippableBox = (at) => {
    for (let box = placeHolder(at); box; box = renderedParent(box))
      if (
        drawnForLanding.has(box) ||
        getComputedStyle(box).contentVisibility === "auto"
      )
        return box;
    return null;
  };

  // A skipped box takes its estimated size, so geometry read inside it, which the
  // browser lays out to answer, can disagree with the stretch drawn where the jump
  // lands; Firefox also keeps the box skipped until it meets the view at an update. On
  // text that breaks other than as its estimate assumes, such as base64 in Firefox,
  // that drew lines 26 past the destination. Drawn for the jump, the box lands where
  // it is read; two frames later the browser has found it in view, and it is released.
  /** @type {Map<Element, string>} */
  const drawnForLanding = new Map();
  /** @param {Element} box */
  function drawForLanding(box) {
    if (!(box instanceof HTMLElement) || drawnForLanding.has(box)) return;
    drawnForLanding.set(box, box.style.getPropertyValue("content-visibility"));
    box.style.setProperty("content-visibility", "visible");
    nextFrame(() =>
      nextFrame(() => {
        const before = drawnForLanding.get(box);
        drawnForLanding.delete(box);
        if (before) box.style.setProperty("content-visibility", before);
        else box.style.removeProperty("content-visibility");
      }),
    );
  }

  /** @param {ScrollPlacement} place @param {boolean} replacedView */
  function placeScroll(
    { at, align = at, block = "center", behavior = scrollBehavior(), when },
    replacedView,
  ) {
    if (when && !when()) return;
    if (block === "fragment") scrollToFragment(at);
    else {
      const skippable = skippableBox(at);
      if (skippable) drawForLanding(skippable);
      scrollIntoView(at, {
        alignment: align,
        behavior: replacedView || skippable ? "instant" : behavior,
        block,
      });
    }
  }

  // Synchronous: the move is the caller's gesture, so its intent is the current one.
  /** @param {Element | null} element @param {ScrollBehavior} [behavior] @param {ScrollLogicalPosition} [block] */
  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    if (!element) return;
    const { replacedView } = reveal(element, retainUserIntent());
    placeScroll({ at: element, behavior, block }, replacedView);
  }

  /** @param {Range} where @param {ScrollBehavior} [behavior] */
  function scrollToRange(where, behavior = scrollBehavior()) {
    const holder = placeHolder(where);
    if (!holder) return;
    const { replacedView } = reveal(holder, retainUserIntent());
    placeScroll({ at: where, behavior }, replacedView);
  }
  // A passage is scrolled to where its words start (readings/passages.js, `passageStart`), as a
  // thread is travelled to (`threadDestination`): a search's match, the comment box
  // brought back to its passage.
  /** @param {readonly import("../readings/passages.js").Segment[]} segments @param {ScrollBehavior} [behavior] */
  function scrollToPassage(segments, behavior = scrollBehavior()) {
    const start = passageStart(segments);
    if (start.length) scrollToRange(rangeOf(start), behavior);
  }

  // Hydration may outlive its gesture. After it settles, validate the retained intent
  // and synchronously repaint before reading placement. The second refresh after reveal
  // handles outlets or fallback placement whose geometry appears only when opened.
  // Travel reads the first passage segment or semantic element from canonical placement,
  // independently of whether the selected presentation paints a mark.
  // A thread pointed into its target is travelled to at the row its own margin row
  // stands by (readings/pointed-place.js), which a target taller than the window would otherwise
  // leave off screen.
  /** @param {string} id */
  const threadDestination = (id) => {
    const placement = anchors.placedAt(id);
    const start = passageStart(targetSegments(placement));
    const where = start.length
      ? rangeOf(start)
      : (targetElement(placement) ?? targetPlace(placement));
    return (
      livePoint(targetElement(placement) ?? targetPlace(placement), placement?.point) ??
      where
    );
  };

  // Where an arrival at a thread lands: on `target`, a node of the thread's or in its
  // card, at the nearest edge, then at the thread's place unless that already shows,
  // centred, or by `block`, as `nearest` for a reader beside the page that moves the
  // page only as far as the place needs (records/thread/destination.js).
  // A part inside a place taller than its room, as a seat's thread can be inside its
  // element, skips the second landing, since landing the place would scroll the part
  // back out of view. A card stands fixed over the page by its thread's place, so an
  // arrival in it, as `m` reaching a question in an agent's answer, lands here too.
  /** @param {string} id @param {import("../dom/focus.js").FocusDestination | null} target
   * @param {"center" | "nearest"} [block] */
  const threadLanding = (id, target, block = "center") => {
    const where = threadDestination(id);
    if (!where) return null;
    const at = target && focusElement(target);
    /** @type {ScrollPlacement[]} */
    const scroll = [];
    if (at) scroll.push({ at, block: "nearest" });
    const inside =
      at !== null && at !== where && where instanceof Element && under(at, where);
    scroll.push({
      at: where,
      block,
      when: () => !alreadyShown(where, { block }) && !(inside && !fitsWhole(where)),
    });
    return { where, focus: target, scroll };
  };

  // The threads a travel is taking the user to, each with the intents that may still
  // land it. Drawing a thread's part can take it off the margin entry or card the user
  // stands on, and the thread pass then carries them to where it stands (records/thread/focus.js,
  // `holdThreadPlace`); a travel that may still land takes them there instead, as its
  // departure says.
  /** @type {Map<string, Set<UserIntent>>} */
  const travelling = new Map();
  /** @param {string} id */
  const travellingTo = (id) =>
    [...(travelling.get(threadNamed(id)?.id ?? id) ?? [])].some((intent) => intent());
  /** @template T @param {string} id @param {UserIntent} intent @param {() => Promise<T>} work */
  async function travelTo(id, intent, work) {
    const key = threadNamed(id)?.id ?? id;
    const intents = travelling.get(key) ?? new Set();
    travelling.set(key, intents.add(intent));
    try {
      return await work();
    } finally {
      intents.delete(intent);
      if (!intents.size && travelling.get(key) === intents) travelling.delete(key);
    }
  }

  // Has the widget holding a thread's target draw the part its anchor names, and
  // resolves whether the travel may still land once the thread pass has placed the
  // thread again. A visual settles on its part, including cancelling a pending
  // replacement of an already visible destination; a lazy datum may load. A thread on
  // earlier data asks its widget too. The thread stays on the place the widget now
  // gives that datum (`lfDataDatum`'s `outdated`), and the widget opens what holds it,
  // as a diff opens the file an earlier line was in.
  /** @param {string} id @param {UserIntent} mayArrive */
  async function drawThread(id, mayArrive) {
    const anchor = threadNamed(id)?.anchor;
    if (!anchor?.visual && !anchor?.datum) return mayArrive();
    const source = sectionOf(anchor);
    const hydration = source && revealAnchor(source, anchor);
    if (hydration?.then) await hydration;
    if (!mayArrive() || sectionOf(anchor) !== source) return false;
    await refreshThread();
    return mayArrive();
  }

  // The same, for a route that has yet to choose where the thread shows, since drawing
  // its part can give it a seat on the page (records/thread/destination.js).
  /** @param {string} id @param {UserIntent | undefined} intent */
  const revealThread = (id, intent) => {
    const mayArrive = retainTravel(intent);
    return travelTo(id, mayArrive, () => drawThread(id, mayArrive));
  };

  // `departure` is the route's, read where the user stood before the route changed
  // anything (records/thread/destination.js), or null for an arrival that adds no entry.
  /** @param {string} id
   * @param {{part?: import("../records/thread/destination.js").ThreadPart, focus?: boolean, presented?: PromiseLike<unknown> | null, intent?: UserIntent | undefined, departure: NavigationStep | null, block?: "center" | "nearest", drawn?: boolean}} options */
  const scrollToThread = (id, options) => {
    const mayArrive = retainTravel(options.intent);
    return travelTo(id, mayArrive, () => travelToThread(id, mayArrive, options));
  };

  /** @param {string} id @param {UserIntent} mayArrive
   * @param {{part?: import("../records/thread/destination.js").ThreadPart, focus?: boolean, presented?: PromiseLike<unknown> | null, departure: NavigationStep | null, block?: "center" | "nearest", drawn?: boolean}} options */
  async function travelToThread(
    id,
    mayArrive,
    {
      part = null,
      focus = true,
      presented = null,
      departure,
      block = "center",
      drawn = false,
    },
  ) {
    const anchor = threadNamed(id)?.anchor;
    const placement = anchors.placedAt(id);
    const destination = threadDestination(id);
    // `drawn` lands the place only where the page shows it now, for an arrival that
    // doesn't travel: it asks no widget to draw a part, opens nothing that hides one,
    // and moves only the scrollers the landing needs.
    if (drawn) {
      if ((anchor?.visual || anchor?.datum) && !targetElement(placement)) return false;
      if (!(destination && placeHolder(destination)?.checkVisibility())) return false;
      const landing = threadLanding(id, null, block);
      if (!landing || !mayArrive()) return false;
      for (const place of landing.scroll) placeScroll(place, false);
      return true;
    }
    // Decided before the navigation step awaits anything: a destination that is not
    // readable now is somewhere else, and so is one a widget has yet to draw, though
    // what stands in for it shows, as a closed file's row shows while the line it
    // stands in for opens thousands of pixels below it. One readable now is already
    // there where the landing below, at its `block`, would move nothing, so history
    // judges the placement the scroll makes (`threadLanding`).
    if (destination || anchor?.visual || anchor?.datum)
      departure?.plan(awaitsDrawing(anchor, placement) ? null : destination, {
        there: () => destination !== null && alreadyShown(destination, { block }),
      });
    if (!(await drawThread(id, mayArrive))) return false;

    // The marks, the placement and the widget outlet this arrival lands in are all
    // written by the thread pass. Wait for it: a claim is synchronous but its
    // paint is not, so reading the destination in this turn would find the page as the
    // press left it.
    // A route naming no part of the thread lands on the place it is about, where the
    // page shows that place but no view of the thread (records/thread/destination.js,
    // `reader: "page"`), and on a part of a drawing where the drawing names for it
    // (`addressedFocus`). A part lands on the page's drawing of it, since this is travel
    // on the page (records/thread/destination.js, `threadFocusTarget`'s `page`).
    return arrive(
      () => {
        const placement = anchors.placedAt(id);
        const source = anchor?.visual ? sectionOf(anchor) : null;
        const target = !focus
          ? null
          : part
            ? threadFocusTarget(id, { part, page: true })
            : (anchor?.visual && source && addressedFocus(source, anchor.visual)) ||
              (targetElement(placement) ?? targetPlace(placement));
        return threadLanding(id, target, block);
      },
      {
        intent: mayArrive,
        departure,
        present: async () => {
          if (presented) await presented;
          if (mayArrive()) await refreshThread();
        },
      },
    );
  }

  return {
    prepareNavigationStep,
    arrive,
    arriveEditor,
    restoreSelection,
    followFragment,
    returnToFragment,
    navigateToDatum,
    scrollToElement,
    scrollToPassage,
    scrollToRange,
    revealThread,
    scrollToThread,
    travellingTo,
    threadDestination,
    threadLanding,
  };
}
