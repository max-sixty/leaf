/* Travel to a place on the page: open what hides it, scroll to it, focus it, and
 * record the departure in history.
 *
 * A place is what an anchor names (anchor-resolution.js): an element with an id, a
 * passage inside one, or a part of a widget, such as a projected datum or a visual
 * part. A thread travels to its anchor's place, a fragment link to its element, an obligation
 * to its own arrival region, and a module's `navigateToDatum` to the part its
 * reference names. Every route shares three steps: `revealAddressed` draws the part,
 * `reveal` opens what holds it, and `clearFor` puts away a surface that would stand
 * over it where it lands (floating-panel.js). Each
 * route says where it lands, what takes focus and how to scroll; `arrive` then does
 * the reveal, clearing, painting, focus and scrolling, and no route does them itself.
 * When the reveal replaces a visible view, the destination lands at once instead of
 * scrolling from the old view's position.
 *
 * Travel gets the current threads and the synchronous thread refresh from the
 * application root, so geometry code never imports the presenter. A navigation step keeps the
 * user's original intent while data loads, the target opens and the page paints;
 * newer input or another navigation step cancels its landing, but not the loading. Each navigation step
 * records where the user is before it moves anything, then checks whether the user is
 * already there. Every arrival that succeeds and moves the page adds that departure to
 * history, so Back returns the user to the item they were on, one step at a time, as
 * Back does after a followed link. Leaf once let a run of steps share one entry while
 * the last landing still showed, so one Back undid a whole `t` or `m` walk. That skipped
 * the item a step left: after `t` then `m`, Back passed over the thread, and once the
 * user answered an obligation, which takes it out of On me, neither Back nor Shift+m
 * returned to it. Limiting the sharing to one walk still missed the second case, so no
 * steps share an entry. A fragment link's
 * navigation step (`followFragment`) uses the history entry the browser added for the link as
 * its departure, and Back or Forward to a place the page has since hidden
 * (`returnToFragment`) is a navigation step that adds no entry.
 */

/** @typedef {{where: Element | Range, input: () => import('./drafts.js').DraftField | null,
 * open?: () => void | (() => void), present?: () => unknown, hasContent?: boolean}} EditorDestination */

import { selectEnds } from "./native-selection.js";
import { referencedProjection, requireReference } from "./references.js";
import {
  addressedElements,
  fragmentTarget,
  resolveAnchor,
  revealAddressed,
  sectionOf,
} from "./anchor-resolution.js";
import {
  clippedPlace,
  landingBand,
  placeBox,
  placeHolder,
  showsContents,
  shownBox,
} from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollersOf, unconcealedReadingRegions } from "./reading-regions.js";
import { prepareEntry } from "./history.js";
import { pageScroller, stopScroll } from "./scrolling.js";
import { landedBox, scrollIntoView } from "./landing-scroll.js";
import { reveal } from "./widget-elements.js";
import { threadNamed } from "./thread/state.js";
import { restrictUserIntent, retainUserIntent } from "./user-intent.js";
import { targetElement, targetPlace, targetSegments } from "./resolved-target.js";
import { rangeOf } from "./passages.js";
import { livePoint } from "./pointed-place.js";
import { notice } from "./notifications.js";

/** @param {Element} element */
const scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;

// The browser's rule for landing the element a fragment names: its start at its
// scroller's landing edge, which a sticky header's stated height keeps clear. Travel
// applies it where the browser's own landing does not reach the element: at an arrival
// the page reshapes after the browser landed it (version.js, `aimArrival`), and at a
// traversal, where the browser restores an offset instead (`returnToFragment`).
/** @param {Destination} element */
export function scrollToFragment(element) {
  scrollIntoView(element, { behavior: "auto", block: "start" });
}

/** @typedef {Element | Range} Destination
 * @typedef {import("./user-intent.js").UserIntent} UserIntent
 * @typedef {import("./focus.js").Caret} Caret
 * @typedef {{at: Destination, align?: Destination, block?: ScrollLogicalPosition | "fragment", behavior?: ScrollBehavior, when?: () => boolean}} ScrollPlacement
 * @typedef {{where: Destination, focus?: Element | null | false, caret?: Caret | null,
 * selection?: {range: Range, backward: boolean}, reveal?: readonly Element[], scroll: readonly ScrollPlacement[]}} Arrival
 * @typedef {{plan: (where: Destination | null | undefined, options?: {there?: (readable: (where: Destination) => boolean) => boolean}) => boolean, commit: () => void}} NavigationStep
 * @typedef {{intent: UserIntent, present?: (() => unknown) | null, departure?: NavigationStep | null}} ArrivalOptions
 * @typedef {{anchors: Pick<ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>, "placedAt">,
 * refreshThread: () => unknown, focusForNavigation: typeof import("./focus.js").focusDestination,
 * threadFocusTarget: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["threadFocusTarget"],
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
    // Every new navigation step takes over the outgoing native placement, including when
    // the new destination still looks readable before the old navigation step's first frame.
    // Read geometry only after its last compositor update has passed; another
    // gesture during that wait retains the place it chose.
    if (initial.scroll.length)
      await stopScroll(
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
    const disclosures = [holder, ...(first.reveal ?? [])].map((target) =>
      reveal(target, intent),
    );
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
        if (current.selection) {
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
  /** @param {import("./anchor-resolution.js").CapturedAnchor | import("../types/domain.js").Anchor} anchor @param {{backward: boolean, intent: UserIntent}} options */
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
      const hydration = revealAddressed(source, datum);
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
  // passage together, taking over any native smooth travel still in progress.
  /** @param {() => EditorDestination | null | undefined} resolve
   * @param {{intent: ReturnType<typeof retainUserIntent>, caret: import("./focus.js").Caret | null}} options */
  async function arriveEditor(resolve, { intent, caret }) {
    const mayArrive = retainTravel(intent);
    const destination = resolve();
    if (!destination?.where) return null;
    const departure = prepareNavigationStep();
    departure.plan(destination.where);
    let release = () => {};
    await arrive(
      () => {
        const current = resolve();
        if (!current) return null;
        const input = current.input();
        return {
          where: current.where,
          focus: input,
          caret,
          // The place the words are about comes into view first and the editor
          // last, so a place taller than the window, as a reviewed case is on a
          // phone, never scrolls the caret back out of it.
          scroll: input
            ? [
                {
                  at: current.where,
                  behavior: "instant",
                  when: () =>
                    !readableDestination(current.where) || !readableDestination(input),
                },
                // The subject and editor can occupy different parts of a tall
                // page. Finish on the box the user asked to write in.
                { at: input, block: "nearest", behavior: "instant" },
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
    return mayArrive() ? (resolve()?.input() ?? null) : undefined;
  }

  // Travel's departure transaction. Capture where the user is before any reveal; plan
  // answers whether the caller moves the page, since a destination the user can already
  // read where they are is no departure, and arrive commits only its successful handoff.
  // Failure or newer intent leaves history untouched. A destination not yet placed (a
  // datum a widget has yet to hydrate) is somewhere else. `there` is the caller's reading
  // of already being there where it asks more than the destination's own (an obligation's
  // arrival region), built on the reading it is handed.
  /** @param {URL} [url] @returns {NavigationStep} */
  function prepareNavigationStep(url) {
    const write = prepareEntry();
    /** @type {boolean | undefined} */
    let moving;
    return {
      plan(where, { there } = {}) {
        moving = !(
          where && (there ? there(readableDestination) : readableDestination(where))
        );
        return moving;
      },
      commit() {
        if (moving) write(url ?? window.location.href);
      },
    };
  }

  // A fragment link naming an element of the page is a navigation step there whose departure is
  // the browser's: the navigation has already added the entry Back returns to, whoever
  // followed it — a press on a page link or a reply's reference, a Go-to hint. What the
  // platform lacks for a page place is travel's to add, the same as for any other
  // destination: clear the surface hiding it, and reveal what holds
  // it, which reaches a widget's own disclosure as well as `hidden="until-found"` (a
  // worker in a shut goal is `display: none`, and the browser landed on nothing). It
  // then lands by the browser's fragment placement rule and puts focus
  // at the destination. Scrolling alone can leave the source link's caret as the
  // user's current location, so subsequent commands would still act from the source.
  // Every activation route shares this arrival rather than supplying its own focus. A
  // fragment naming nothing here is not claimed, and the browser keeps it.
  /** @param {URL} url */
  function followFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && fragmentNavigationStep(url, true);
  }

  // Back or Forward restores the offset the entry was left at (history.js), which is
  // where the user was reading while the page still holds the place the entry's
  // fragment names. Once that place is no longer shown, closed since in a tab, a
  // disclosure or a widget's own shut state, the offset was read over a page that has
  // changed, and restoring it lands on whatever now sits at that pixel. The fragment is
  // then the one thing the entry still says, so the traversal is a navigation step to it that
  // departs by no new entry: the same clearing and reveal as a followed link. The
  // browser's own landing on a traversal is that offset, so travel lands the place by
  // the fragment rule itself (`scrollToFragment`).
  /** @param {URL} url */
  function returnToFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && !showsContents(where) ? fragmentNavigationStep(url, false) : null;
  }

  /** @param {URL} url @param {boolean} focus */
  function fragmentNavigationStep(url, focus) {
    const mayArrive = retainTravel();
    return () =>
      arrive(
        () => {
          const where = fragmentTarget(url.hash);
          return (
            where && {
              where,
              focus: focus ? where : null,
              scroll: [{ at: where, block: "fragment" }],
            }
          );
        },
        { intent: mayArrive },
      );
  }

  /** @param {Element} owner @param {string} attribute @param {string} key @param {{success?: string, missing?: string, focus?: boolean}} [options] */
  async function navigateToDatum(
    owner,
    attribute,
    key,
    { success = "", missing = "", focus = true } = {},
  ) {
    const mayArrive = retainTravel();
    requireReference("navigateToDatum", owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) notice(missing);
      return false;
    }

    const url = new URL(window.location.href);
    url.hash = source.id;
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
            focus: focus ? where : null,
            scroll: [
              { at: where, block: "start", when: () => !readableDestination(where) },
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

  /** @param {ScrollPlacement} place @param {boolean} replacedView */
  function placeScroll(
    { at, align = at, block = "center", behavior = scrollBehavior(), when },
    replacedView,
  ) {
    if (when && !when()) return;
    if (block === "fragment") scrollToFragment(at);
    else
      scrollIntoView(at, {
        alignment: align,
        behavior: replacedView ? "instant" : behavior,
        block,
      });
  }

  // Synchronous: the move is the caller's gesture, so its intent is the current one.
  /** @param {Element | null} element @param {ScrollBehavior} [behavior] @param {ScrollLogicalPosition} [block] */
  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    if (!element) return;
    const { replacedView } = reveal(element, retainUserIntent());
    placeScroll({ at: element, behavior, block }, replacedView);
  }

  // A destination's box and what of it the user can see, which is that box less the
  // window and whatever clips it, or null when none of it shows.
  /** @param {Destination} where */
  function seenOf(where) {
    const holder = placeHolder(where);
    if (!holder) return null;
    const destination = placeBox(where);
    const seen = clippedPlace(where, new Map(), destination);
    return seen && { holder, destination, seen };
  }

  // Whether travel to `where` would leave the page as it stands: the destination stands
  // whole inside the band a landing aims for (`landingBand`) and nothing cuts it. Being
  // in front of the user (`seenRect`) is not enough, since a destination half cut off or
  // pressed against the window's head is one a landing still moves.
  /** @param {Destination} where */
  function readableDestination(where) {
    const shown = seenOf(where);
    if (!shown) return false;
    const { holder, destination, seen } = shown;
    const box = scrollingBoxFor(holder);
    const band = box ? landingBand(box) : shownBox(pageScroller);
    if (!band) return false;
    /** @param {number} a @param {number} b */
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return (
      destination.top >= band.top - 0.5 &&
      destination.bottom <= band.bottom + 0.5 &&
      close(seen.top, destination.top) &&
      close(seen.right, destination.right) &&
      close(seen.bottom, destination.bottom) &&
      close(seen.left, destination.left)
    );
  }

  /** @param {Range} where @param {ScrollBehavior} [behavior] */
  function scrollToRange(where, behavior = scrollBehavior()) {
    const holder = placeHolder(where);
    if (!holder) return;
    const { replacedView } = reveal(holder, retainUserIntent());
    placeScroll({ at: where, behavior }, replacedView);
  }

  // Hydration may outlive its gesture. After it settles, validate the retained intent
  // and synchronously repaint before reading placement. The second refresh after reveal
  // handles outlets or fallback placement whose geometry appears only when opened.
  // Travel reads the first passage segment or semantic element from canonical placement,
  // independently of whether the selected presentation paints a mark.
  // A thread pointed into its target is travelled to at the row its own margin row
  // stands by (pointed-place.js), which a target taller than the window would otherwise
  // leave off screen.
  /** @param {string} id */
  const threadDestination = (id) => {
    const placement = anchors.placedAt(id);
    const segment = targetSegments(placement)[0];
    const where = segment
      ? rangeOf([segment])
      : (targetElement(placement) ?? targetPlace(placement));
    return (
      livePoint(targetElement(placement) ?? targetPlace(placement), placement?.point) ??
      where
    );
  };

  /** @param {string} id
   * @param {{part?: import("./thread/destination.js").ThreadPart, focus?: boolean, presented?: PromiseLike<unknown> | null, intent?: UserIntent | undefined, history?: boolean}} [options] */
  async function scrollToThread(
    id,
    { part = null, focus = true, presented = null, intent, history = true } = {},
  ) {
    const mayArrive = retainTravel(intent);
    const thread = threadNamed(id);
    const anchor = thread?.anchor;
    const status = anchors.placedAt(id)?.status;
    const hydrationTarget = anchor?.visual
      ? { anchor, key: anchor.visual }
      : anchor?.datum && status !== "outdated"
        ? { anchor, key: anchor.datum }
        : null;
    const destination = threadDestination(id);
    // Decided before the navigation step awaits anything: a destination that is not readable now,
    // or one a widget has yet to hydrate, is somewhere else.
    const departure = history ? prepareNavigationStep() : null;
    if (destination || hydrationTarget) departure?.plan(destination);
    if (hydrationTarget) {
      const source = sectionOf(hydrationTarget.anchor);
      // A visual settles on its part, including cancelling a pending replacement of
      // an already visible destination; a lazy datum may load.
      const hydration = source && revealAddressed(source, hydrationTarget.key);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(hydrationTarget.anchor) !== source) return false;
      await refreshThread();
      if (!mayArrive()) return false;
    }

    // The marks, the placement and the widget outlet this arrival lands in are all
    // written by the thread pass. Wait for it: a claim is synchronous but its
    // paint is not, so reading the destination in this turn would find the page as the
    // press left it.
    return arrive(
      () => {
        const where = threadDestination(id);
        if (!where) return null;
        const target = focus && part ? threadFocusTarget(id, { part }) : null;
        /** @type {ScrollPlacement[]} */
        const scroll = [];
        if (target) scroll.push({ at: target, block: "nearest" });
        scroll.push({ at: where, when: () => !readableDestination(where) });
        return { where, focus: target, scroll };
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
    readableDestination,
    scrollToRange,
    scrollToThread,
    threadDestination,
  };
}
