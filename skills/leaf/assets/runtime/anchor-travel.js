/* Travel to a place on the page.
 *
 * A place is what an anchor names (anchor-resolution.js): an addressed element, which
 * is what a fragment names too, a passage inside one, or a part of a widget, a projected
 * datum or a visual part. A thread travels to the place its anchor names, a fragment
 * link to its element, an Ask to its own arrival region, and a module's
 * `navigateToDatum` to the part its declared reference addresses. Whichever route names
 * it, a part is drawn through the one `revealAddressed`, what holds the place opens
 * through the one `reveal`, and the surface hiding it is cleared through the one
 * `clearFor`. Each route declares its fresh destination, focus target and scroll
 * placements. Each placement names its destination and may name a separate alignment
 * context: inner scrollports reveal the destination before its context is aligned.
 * `arrive` completes their reveal, presentation, focus and placement
 * under the original user intent; routes never perform the final handoff themselves.
 * Travel scrolls within the current view. When reveal replaces a visible view,
 * its destination lands immediately rather than scrolling from the old view's place.
 *
 * Travel owns effects above readonly resolution and paint. It receives the current
 * semantic threads and the synchronous thread refresh from the application root;
 * subordinate geometry never imports the presenter. A trip keeps its original user
 * intent through hydration, reveal and presentation. Newer input or another trip
 * cancels its landing without cancelling the data the page is loading. Every trip, to a
 * thread, an Ask or a datum, goes through `trip`, which clears whatever surface hides
 * the destination and then decides whether the user is already there or departs. A
 * departure leaves a history entry, so browser Back returns the user to where they
 * were reading; a journey, trips each leaving from the last one's landing, is one
 * entry. A fragment link's trip (`followFragment`) departs by the browser's own entry,
 * and Back or Forward to a place the page has hidden since (`returnToFragment`) is a
 * trip that departs by none.
 */

import {
  addressedElements,
  fragmentTarget,
  referencedProjection,
  requireReference,
  revealAddressed,
  sectionOf,
} from "./anchor-resolution.js";
import {
  clippedContents,
  clipsPast,
  landingBand,
  placeHolder,
  shownBox,
  shownRect,
} from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollersOf } from "./reading-regions.js";
import { pushEntry, replaceEntry } from "./history.js";
import { pageScroller } from "./scrolling.js";
import { scrollIntoReadingBand } from "./landing-scroll.js";
import { renderedParent } from "./shadow.js";
import { reveal } from "./widget-elements.js";
import { threadNames } from "./thread/model.js";
import { restrictUserIntent, retainUserIntent } from "./user-intent.js";
import { targetElement, targetPlace, targetSegments } from "./resolved-target.js";
import { rangeOf } from "./passages.js";
import { standingPoint } from "./pointed-place.js";

// The browser's rule for landing the element a fragment names: its start at its
// scroller's landing edge, which a sticky header's stated height keeps clear. Travel
// applies it where the browser's own landing does not reach the element: at an arrival
// the page reshapes after the browser landed it (version.js, `aimArrival`), and at a
// traversal, where the browser restores an offset instead (`returnToFragment`).
export function scrollToFragment(element) {
  element.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" });
}

export function createAnchorTravel({
  anchors,
  surfaces,
  currentThreads,
  refreshThread,
  focusForNavigation,
  threadFocusTarget,
  announce,
}) {
  let travelIntent = 0;
  const retainTravel = (retained = retainUserIntent()) => {
    const intent = ++travelIntent;
    return restrictUserIntent(retained, () => intent === travelIntent);
  };

  // A push leaves the current scroll position on the entry it leaves, and Back
  // restores it there (history.js), so the push comes before the trip moves anything.
  // A destination already readable where the user stands is no departure. A trip that
  // names its `landing` while any of the last trip's landing still shows continues that
  // journey, whether it goes to threads or Asks: it replaces the journey's entry, which
  // already holds where the journey began. Once the user has moved off that landing, the
  // next trip pushes again. A journey is not a walk (the glossary's ordered movement
  // among one kind of destination): steps of a thread walk and of an Ask walk, or a
  // press on a margin marker, can all be trips of one journey. The landing is a lookup
  // rather than a node because the thread pass repaints marks, and the entry
  // carries a token for this document's journey because only this load holds the
  // lookup.
  const journeyPrefix = `${performance.timeOrigin}:`;
  let trips = 0;
  let journey = null;

  function depart({ url = window.location.href, landing = null } = {}) {
    const continuing = landing && stillLanded();
    journey = landing && { token: journeyPrefix + ++trips, landing };
    const state = journey && { lfJourney: journey.token };
    if (continuing) replaceEntry(url, state);
    else pushEntry(url, state);
  }

  // A trip whose destination is already in front of the user moves nothing and records
  // nothing, but it is still a trip of the journey: the journey now stands on its
  // landing, so the next trip continues from there rather than from the one before it.
  function stay(landing) {
    if (stillLanded()) journey.landing = landing;
  }

  function stillLanded() {
    const where =
      journey && history.state?.lfJourney === journey.token && journey.landing();
    return Boolean(where && seenOf(where));
  }

  // A route resolves a declaration, not a retained DOM destination. Reveal and its
  // presentation may replace nodes; focus may itself change the geometry. Read the
  // declaration after each of those boundaries, then apply its scroll placements in
  // the same synchronous handoff as focus. Exposure places a replaced view immediately;
  // `present` lets the owning renderer settle before the final geometry is read.
  // History departure remains before the work that would move the outgoing place.
  async function arrive(resolve, { intent, present = null, keep = false }) {
    const first = resolve();
    const holder = first && placeHolder(first.where);
    if (!holder || !intent()) return false;
    if (!keep) intent.handoff(() => surfaces.clearFor(holder));
    const disclosures = [holder, ...(first.reveal ?? [])].map((target) =>
      reveal(target, intent),
    );
    const replacedView = disclosures.some((disclosure) => disclosure.replacedView);
    const place = () => {
      let completed = false;
      intent.handoff(() => {
        const destination = resolve();
        if (!destination?.where) return;
        if (destination.focus) focusForNavigation(destination.focus, destination.caret);
        const current = resolve();
        if (!current?.where) return;
        for (const placement of current.scroll) placeScroll(placement, replacedView);
        completed = true;
      });
      return completed;
    };
    // A new view may paint while its layout is still presenting. Place its destination
    // now; after presentation, resolve fresh geometry through the same placement.
    if (replacedView) place();
    await Promise.all(disclosures.map((disclosure) => disclosure.ready));
    if (!intent()) return false;
    if (present) await present();
    if (!intent()) return false;
    return place();
  }

  // A remembered editor starts from its authored place, before a hidden editor is
  // materialized. Its owner opens without focus; the ordinary arrival owns surface
  // clearance, disclosure, presentation, caret and reading placement. A materializer
  // may return its keyed focus-handoff release, retired after this landing.
  async function arriveEditor(resolve, { intent, caret }) {
    const mayArrive = retainTravel(intent);
    const destination = resolve();
    if (!destination?.where) return null;
    trip(destination.where, { intent: mayArrive, landing: () => resolve()?.where });
    let release = null;
    await arrive(
      () => {
        const current = resolve();
        const input = current?.input();
        return (
          current && {
            where: current.where,
            focus: input,
            caret,
            scroll: input
              ? [
                  { at: input, block: "nearest" },
                  {
                    at: current.where,
                    when: () => !readableDestination(input),
                  },
                ]
              : [],
          }
        );
      },
      {
        intent: mayArrive,
        present: async () => {
          const current = resolve();
          if (!current) return;
          if (current.open)
            mayArrive.handoff(() => {
              release = current.open();
            });
          await current.present?.();
        },
      },
    );
    if (typeof release === "function") release();
    return mayArrive() ? (resolve()?.input() ?? null) : undefined;
  }

  // Travel's one entry. It stays when the user already has the destination and departs
  // otherwise, and answers whether the caller moves the page. A destination not yet
  // placed (a datum a widget has yet to hydrate) is somewhere else. `there` is the
  // caller's reading of already being there where it asks more than the destination's
  // own (an Ask's arrival region), built on the reading it is handed. Clearing a surface
  // can take the focus out of it, so the caller's retained `intent` hands the gesture
  // over to where that leaves the user rather than reading the move as a newer one.
  function trip(
    where,
    {
      landing = null,
      url,
      keep = false,
      intent,
      there = (readable) => readable(where),
    } = {},
  ) {
    if (where && !keep) intent.handoff(() => surfaces.clearFor(where));
    if (where && there(readableDestination)) {
      stay(landing);
      return false;
    }
    depart({ url, landing });
    return true;
  }

  // A fragment link naming an element of the page is a trip there whose departure is
  // the browser's: the navigation has already added the entry Back returns to, whoever
  // followed it — a press on a page link or a reply's reference, a Go-to hint. What the
  // platform lacks for a page place is travel's to add, the same as for any other
  // destination: clear the surface hiding it (a covering Threads panel left the page
  // scrolling behind it, the link's own thread still in front), and reveal what holds
  // it, which reaches a widget's own disclosure as well as `hidden="until-found"` (a
  // worker in a shut goal is `display: none`, and the browser landed on nothing). It
  // then lands by the browser's fragment placement rule and puts focus
  // at the destination. Scrolling alone can leave the source link's caret as the
  // user's standing place, so subsequent commands would still act from the source.
  // Every activation route shares this arrival rather than supplying its own focus. A
  // fragment naming nothing here is not claimed, and the browser keeps it.
  function followFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && fragmentTrip(url, true);
  }

  // Back or Forward restores the offset the entry was left at (history.js), which is
  // where the user was reading while the page still holds the place the entry's
  // fragment names. Once that place is no longer shown, closed since in a tab, a
  // disclosure or a widget's own shut state, the offset was read over a page that has
  // changed, and restoring it lands on whatever now sits at that pixel. The fragment is
  // then the one thing the entry still says, so the traversal is a trip to it that
  // departs by no new entry: the same clearing and reveal as a followed link. The
  // browser's own landing on a traversal is that offset, so travel lands the place by
  // the fragment rule itself (`scrollToFragment`).
  function returnToFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && !where.checkVisibility() ? fragmentTrip(url, false) : null;
  }

  function fragmentTrip(url, focus) {
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

  async function navigateToDatum(
    owner,
    attribute,
    key,
    { success = "", missing = "" } = {},
  ) {
    const mayArrive = retainTravel();
    requireReference("navigateToDatum", owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }

    // The widget owns filters, lazy projection, and the state a visual draws. Ask it to
    // make the key reachable before interpreting DOM presence.
    const hydration = revealAddressed(source, key);
    if (hydration?.then) await hydration;
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }
    const destination = addressedElements(source, key)[0] ?? null;

    const url = new URL(window.location.href);
    url.hash = source.id;
    const moving = trip(destination, { url, intent: mayArrive });
    if (!destination) {
      await arrive(
        () => {
          const where = referencedProjection(owner, attribute);
          return (
            where && { where, focus: null, scroll: [{ at: where, block: "start" }] }
          );
        },
        { intent: mayArrive },
      );
      if (mayArrive() && missing) announce(missing);
      return false;
    }
    const arrived = await arrive(
      () => {
        const source = referencedProjection(owner, attribute);
        const where = source && addressedElements(source, key)[0];
        return where && { where, focus: where, scroll: moving ? [{ at: where }] : [] };
      },
      { intent: mayArrive },
    );
    if (mayArrive() && (arrived ? success : missing))
      announce(arrived ? success : missing);
    return arrived;
  }

  // Reading-region membership also covers fixed chrome, but its viewport position does
  // not move with that region, so a fixed boundary ends the scrollers that move it
  // (`scrollersOf`); a scroller inside that boundary still owns its ordinary descendants.
  const scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;

  function placeScroll(
    { at, align = at, block = "center", behavior = scrollBehavior(), when },
    replacedView,
  ) {
    if (when && !when()) return;
    if (block === "fragment") scrollToFragment(at);
    else scrollRevealedPlace(at, align, replacedView ? "instant" : behavior, block);
  }

  // Synchronous: the move is the caller's gesture, so its intent is the one standing now.
  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    const { replacedView } = reveal(element, retainUserIntent());
    placeScroll({ at: element, behavior, block }, replacedView);
  }

  // A destination's box and what of it the user can see, which is that box less the
  // window and whatever clips it, or null when none of it shows. The selected surface is
  // read past: it can be cleared for travel; any other occluder is not.
  function seenOf(where) {
    const holder = placeHolder(where);
    if (!holder) return null;
    const destination =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const standing = surfaces.selectedSurface();
    const clips = standing ? clipsPast([standing]) : new Map();
    const seen =
      where instanceof Range
        ? clippedContents(destination, holder, clips)
        : shownRect(where, clips);
    return seen && { holder, destination, seen };
  }

  function readableDestination(where) {
    const shown = seenOf(where);
    if (!shown) return false;
    const { holder, destination, seen } = shown;
    const box = scrollingBoxFor(holder);
    const band = box ? landingBand(box) : shownBox(pageScroller);
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

  // Native nearest alignment: a destination spanning both edges stays; one larger
  // than the viewport lands its nearer edge rather than hiding its opening words.
  function nearestBy(start, end, low, high) {
    if (start < low && end > high) return 0;
    const oversized = end - start > high - low;
    if (start < low) return oversized ? end - high : start - low;
    if (end > high) return oversized ? start - low : end - high;
    return 0;
  }

  // Prepare only scrollports inside the owning reading region. Snapping the owning
  // region (or the document) into view first consumes the distance the glide should
  // travel, so a far destination appears to teleport before a tiny alignment move.
  // Elements and passages share this placement, including horizontal inspection.
  function scrollRevealedPlace(where, alignment, behavior, block) {
    if (block === "nearest" && where instanceof Element) {
      where.scrollIntoView({ block, inline: "nearest", behavior });
      return;
    }
    const holder = placeHolder(alignment);
    if (!holder) return;
    const targetScroller = scrollingBoxFor(holder);
    if (!targetScroller) return;
    // Horizontal inspection can belong to any ancestor, the owning region included.
    // Only inner scrollports prepare Y; the region and its outers glide below.
    let inside = true;
    for (
      let box = placeHolder(where);
      box instanceof Element;
      box = renderedParent(box)
    ) {
      if (box === targetScroller) inside = false;
      const band = landingBand(box);
      if (!band) continue;
      const { left, right, top, bottom } = band;
      const destination = where.getBoundingClientRect();
      const byX = nearestBy(destination.left, destination.right, left, right);
      const byY = inside
        ? nearestBy(destination.top, destination.bottom, top, bottom)
        : 0;
      if (byX || byY) box.scrollBy({ left: byX, top: byY, behavior: "instant" });
      if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
    }
    scrollIntoReadingBand(alignment, holder, block, behavior);
  }

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
  const threadDestination = (id) => {
    const placement = anchors.placedAt(id);
    const segment = targetSegments(placement)[0];
    const where = segment
      ? rangeOf([segment])
      : (targetElement(placement) ?? targetPlace(placement));
    return (
      standingPoint(
        targetElement(placement) ?? targetPlace(placement),
        placement?.point,
      ) ?? where
    );
  };

  async function scrollToThread(
    id,
    { focus = null, keep = false, presented = null, intent } = {},
  ) {
    const mayArrive = retainTravel(intent);
    const thread = threadNames(currentThreads()).get(id);
    const anchor = thread?.anchor;
    const status = anchors.placedAt(id)?.status;
    const hydrating =
      (anchor?.datum && status !== "outdated") ||
      (anchor?.visual && status === "fallback");
    const standing = threadDestination(id);
    // Decided before the trip awaits anything: a destination that is not readable now,
    // or one a widget has yet to hydrate, is somewhere else.
    const landing = () => threadDestination(id);
    if (standing || hydrating) trip(standing, { landing, keep, intent: mayArrive });
    if (hydrating) {
      const source = sectionOf(anchor);
      // A visual draws the state holding its part synchronously; a lazy datum may load.
      const hydration =
        source && revealAddressed(source, anchor.visual ?? anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
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
        const target = focus && threadFocusTarget(id, { focus });
        return {
          where,
          focus: target,
          scroll: [
            ...(target ? [{ at: target, block: "nearest" }] : []),
            { at: where, when: () => !readableDestination(where) },
          ],
        };
      },
      {
        intent: mayArrive,
        present: async () => {
          if (presented) await presented;
          if (mayArrive()) await refreshThread();
        },
        keep,
      },
    );
  }

  return {
    trip,
    arrive,
    arriveEditor,
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
