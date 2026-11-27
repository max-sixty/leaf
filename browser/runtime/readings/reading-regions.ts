/* Reading regions are stable semantic places whose current scroll container may change.

   A region binds one stable id to a host and body. The host makes focus in a pane's
   header or footer select that pane; the body is the region's scroller whenever the
   stylesheet makes it scroll, which is the only reading of scroll behavior there is: a
   bounded region's body scrolls, and a flowing one's is carried by the region
   containing it or by the page. CSS decides that from the space a workspace has
   (layouts.css, the workspace Layout), so nothing here chooses a scroll behavior.

   Every box Leaf makes scroll vertically is a region, so every question that names the
   box scrolling a node (`scrollerFor`, and `scrollersOf` for the boxes around it) gets
   that box rather than the page: a pane's body, the Threads list, a compound widget's
   parts, and a block bounded with `bound` or data-bound, which `bounds.js` registers. A
   box page CSS makes scroll is none of these. It stays unsupported: `page check`
   advises bounding the block instead, and nothing here searches the DOM for scrollers.
   Containment follows the rendered tree, including assigned slots: a native message
   laid out by a package's shadow reader belongs to that reader's region.

   A module states a region on the box itself: reach's mark with a name,
   `data-lf-scroll="<name>"`, makes the box a region's body for as long as it stands in
   the page wearing it, and `data-lf-scroll-host="<name>"` on a box around it makes that
   box the host. One watch (dom/arrivals.js) keeps those regions registered. Every question
   asked of the registry first reads the mutations the watch has yet to deliver
   (`readMarks`), because a question can come in the task that wrote the mark: a widget
   draws a box and shows its first subject in it (`showReadingSubject`), lands
   something in it, or brackets its first change with `preserveReadingRegions`. A mark
   heard only at the watch's delivery would be a region none of those knew. A reading
   of the marks is one batch, which decides its departures first, so a box that replaces
   another takes the id the other held. The watch is this module's own: reach's watch
   of the same mark (dom/reach.js) starts once the page has presented and gives back a
   keyboard stop where a box leaves, which a reading in the middle of a task would do
   to a box a script is only moving. The runtime registers its own regions directly
   (`registerReadingRegion`).

   A region's id has to name it in the next document too, since that is where a revision
   restores its place, so it is composed from the id of an element that holds the region
   and the region's name (`regionId`).

   A region's scroller can change without any gesture: a window crossing the workspace
   threshold, a tab showing, a panel opening. A region whose width changes keeps its
   scroller but rewraps, which moves its words under the reader just the same. Each
   region's host is watched for size, and a region whose scroller is no longer the one
   last seen, or whose width is not, is announced to watchers as a `shift`, after the new
   geometry exists. A viewport height change shifts every shown region, including
   flowing bodies whose own size stays the same while their visible band shrinks. The
   page is watched the same way and shifts with no region: its width, and the top of its
   landing band, which the chrome moves when the window's width gives it another row.
   Continuity owners record the user's place continuously and restore it on a shift;
   this module stores no landmarks or scroll offsets. `preserveReadingRegions` brackets
   a composition change with the same
   watchers, as `before` and `after`, retaining only scrollers inside that composition
   when regions become hidden or visible. Hidden connected regions remain registered and
   return null bounds. A region whose body is a closed `<details>` is concealed though
   its summary shows: none of what it holds does, so there is no place in it to read.
   Cleanup removes live DOM bindings, so a replacement can reclaim an id.

   The reach pass paints continuation at the body's scroll edges. An owner can supply
   `onReach()` to read the body on the same scroll and size observations, as a thread
   card decides there whether its transcript shows its scrollbar (thread-preview.js).

   A region can show one subject of several in turn, as a trace's saved tree shows one
   checkpoint's elements at a time. Its owner replaces the body's contents through
   `showReadingSubject(body, subject, render)`, which tells watchers the subject is
   `leaving` and then `showing`, so a continuity owner keeps the reader's place in each
   subject and returns them to it.

   `onReadingInput` tells a reader where the user explicitly clicked. It includes
   unfocusable words, which update the reading region without a focus arrival, and a
   control already holding focus, where the browser announces none. A step by Tab is
   an arrival, which a reader hears from `onCurrentLocation` (dom/focus.js) as it hears
   every other. Mechanical returns, programmatic arrivals and scrolling are not
   choices of another passage. Each consumer interprets that target in its own
   domain. */
import { installScrollerLookup } from "./scroll-containers.js";
export { scrollersOf } from "./scroll-containers.js";
import { stageOf, watchArrivals } from "../dom/arrivals.js";
import { nextRender, sizeObserver } from "../lib/frame-pass.js";
import { landingBand, shownRect, userScrollport } from "../dom/geometry.js";
import {
  closestAcross,
  isElement,
  skipped,
  under,
  renderedUnder,
  renderedParent,
} from "../lib/shadow-tree.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { pageScroller } from "../dom/scrolling.js";
import { holdReach, reachReadingScroller } from "../dom/reach.js";
import {
  authoredScope,
  focusInPage,
  inPage,
  layoutBox,
  pageDocument,
} from "./passages.js";
import { deepFocus, onCurrentLocation, pressing } from "../dom/focus.js";

export type ReadingRegion = {
  id: string;
  host: Element & Partial<Pick<HTMLElement, "offsetWidth">>;
  body: Element;
  subject: string | null | undefined;
};
type RegionRegistration = ReadingRegion & {
  scroller: Element | null;
  width: number | null | undefined;
  away: boolean;
};
type RegionTarget = string | ReadingRegion | Element | null | undefined;
export type RegionShift =
  | { region: ReadingRegion; from: Element; to: Element; returned: boolean }
  | { region: null; band: number };
type CompositionTransition = { owner: Element; regions: ReadingRegion[] };
export type ReadingTransition =
  | { phase: "leaving" | "showing"; region: ReadingRegion }
  | { phase: "shift"; shifted: RegionShift[] }
  | (CompositionTransition &
      (
        | { phase: "before"; retained: boolean }
        | { phase: "after"; cancelled: boolean }
      ));
const regions = new Map<string, RegionRegistration>();
// Reads the marks written since the watch below last delivered (the header says why).
// Every question about the registry asks through `registered` or `regionsAround`,
// which read them first.
let readMarks = () => {};
const registered = () => {
  readMarks();
  return regions;
};
const transitionWatchers: Set<(transition: ReadingTransition) => void> = new Set();

const depthOf = (node: Node) => {
  let depth = 0;
  for (
    let current = node instanceof Element ? node : node.parentElement;
    current;
    current = renderedParent(current)
  )
    depth += 1;
  return depth;
};

const live = <T extends ReadingRegion>(region: T | undefined): region is T =>
  Boolean(region?.host.isConnected && region.body.isConnected);
// The regions each host holds and each body shows, in the order they registered, so a
// question about the regions around a node climbs from it rather than asking each one.
const byHost = new WeakMap<Element, RegionRegistration[]>();
const byBody = new WeakMap<Element, RegionRegistration[]>();
const current = (region: RegionRegistration) =>
  regions.get(region.id) === region && live(region);
function* regionsAround(
  node: Node | null | undefined,
  index: WeakMap<Element, RegionRegistration[]>,
) {
  readMarks();
  for (let at = node; at; at = renderedParent(at))
    if (isElement(at)) yield* (index.get(at) ?? []).filter(current);
}

// Three questions about a region's visibility, each asked where its cost and answer fit:
// `concealed` reads the page's own attributes alone, so the inventory decides what to
// sample without asking any geometry; `shown` (below) asks whether the browser draws
// the host at all, which a region scrolled out of the window still is; `hidden` asks
// whether the region has bounds to give now, concealed or clipped away entirely.
const concealed = (region: ReadingRegion) =>
  region.host.closest("[hidden], [aria-hidden='true']") !== null ||
  region.body.matches("details:not([open])");

const hidden = (region: ReadingRegion) =>
  !live(region) || concealed(region) || shownRect(region.host, new Map()) === null;

const regionRecord = (region: ReadingRegion): ReadingRegion => ({
  id: region.id,
  host: region.host,
  body: region.body,
  subject: region.subject,
});

// The id of the region `name` that `owner` names, whose body is `box` (the header says
// what an id is for). An element with an id names its regions in the page's own
// document for good. A box no such element names, or one in a message's markup, whose
// ids repeat the page's, takes a fresh id that names its region in this document
// alone: the region answers every geometry question and keeps its place while it
// stands, and a replacement document starts it afresh rather than guess which region
// it was.
const THIS_DOCUMENT = `lf-region:${performance.timeOrigin}`;
let unnamed = 0;
export const regionId = (owner: Element | null, name: string, box: Element) =>
  owner?.id && authoredScope(box) === pageDocument()
    ? `lf-region:${owner.id}:${name}`
    : `${THIS_DOCUMENT}:${(unnamed += 1)}`;

export function registerReadingRegion({
  id,
  host,
  body,
  onReach = undefined,
}: {
  id: string;
  host: Element;
  body: Element;
  onReach?: () => void;
}) {
  if (typeof id !== "string" || !id)
    throw new Error("leaf: a reading region needs an id");
  if (live(regions.get(id)))
    throw new Error(`leaf: reading region ${id} is already live`);
  const region: RegionRegistration = {
    id,
    host,
    body,
    subject: undefined,
    scroller: null,
    width: null,
    away: false,
  };
  const stopReaching = reachReadingScroller(body, onReach);
  regions.set(id, region);
  byHost.set(host, [...(byHost.get(host) ?? []), region]);
  byBody.set(body, [...(byBody.get(body) ?? []), region]);
  sizes.observe(host);
  return () => {
    if (regions.get(id) === region) regions.delete(id);
    byHost.set(
      host,
      (byHost.get(host) ?? []).filter((other) => other !== region),
    );
    byBody.set(
      body,
      (byBody.get(body) ?? []).filter((other) => other !== region),
    );
    sizes.unobserve(host);
    stopReaching();
  };
}

// The boxes a page's Layout makes scroll, which no widget owns: the workspace's body,
// which scrolls as a whole where a pane in it does not bound itself, and a sidebar
// page's authored track, which scrolls while it stands beside the body
// (layouts.css). The stylesheet marks each one
// (`--lf-reading-region: layout`): a child of `main`, or the only child of one that is
// not itself marked. Each is registered like any other region, so what it holds is
// carried by it rather than by the page, and its scroll behavior is read from whether it
// scrolls. Its id is the authored id of the box or, for an only child, of the child of
// `main` holding it, as a sidebar page's `aside` names that box, so a neighbour's
// arrival or removal never renames it; an unnamed one takes its place among the unnamed
// ones, in a namespace of its own. Document composition asks on every pass, since a
// revision can replace `main`'s children and a resize can change which of them the stylesheet marks.
const layoutRegions: Map<Element, { id: string; stop: () => void }> = new Map();
const marked = (box: Element) =>
  box.checkVisibility() &&
  getComputedStyle(box).getPropertyValue("--lf-reading-region").trim() === "layout";
export function syncLayoutRegion() {
  const main = layoutBox();
  const bodies = main
    ? [...main.children].flatMap((child) => {
        if (marked(child)) return [{ body: child, name: child.id }];
        const only = child.childElementCount === 1 ? child.firstElementChild : null;
        return only && marked(only) ? [{ body: only, name: only.id || child.id }] : [];
      })
    : [];
  let unnamed = 0;
  const ids = new Map(
    bodies.map(({ body, name }) => [
      body,
      name ? `lf-region:layout#${name}` : `lf-region:layout@${unnamed++}`,
    ]),
  );
  for (const [body, region] of layoutRegions)
    if (ids.get(body) !== region.id) {
      region.stop();
      layoutRegions.delete(body);
    }
  for (const [body, id] of ids)
    if (!layoutRegions.has(body))
      layoutRegions.set(body, {
        id,
        stop: registerReadingRegion({ id, host: body, body }),
      });
}

// Replace a region's contents with another subject's (see the header). A box that is no
// region's body has no place to keep, so the render runs alone.
export function showReadingSubject<T>(
  body: Element,
  subject: string | null,
  render: () => T,
): T {
  readMarks();
  const region = byBody.get(body)?.find(current);
  if (!region || region.subject === subject) {
    if (region) region.subject = subject;
    return render();
  }
  notify({ phase: "leaving", region: regionRecord(region) });
  region.subject = subject;
  const rendered = render();
  notify({ phase: "showing", region: regionRecord(region) });
  return rendered;
}

export const readingRegion = (id: string | null | undefined) => {
  const region = id == null ? undefined : registered().get(id);
  return live(region) ? regionRecord(region) : undefined;
};

export const readingRegions = () =>
  [...registered().values()].filter(live).map(regionRecord);

// Keep a region in the inventory while an authored disclosure or tab conceals it,
// but never ask its geometry merely to decide whether to sample it.
export const unconcealedReadingRegions = () =>
  [...registered().values()]
    .filter((region) => live(region) && !concealed(region) && !skipped(region.body))
    .map(regionRecord);

// The region whose host is nearest around `node`: the first its climb meets.
const regionAt = (node: Node | null | undefined) =>
  regionsAround(node, byHost).next().value ?? undefined;

export const readingRegionFor = (node: Node | null | undefined) => {
  const region = regionAt(node);
  return region && regionRecord(region);
};

// The region the user is reading in, which the reading keys scroll and continuity
// restores first. Focus answers where it stands on the page or in a region; otherwise
// the user's last press, wheel, touch or arrival does, which is the platform's own rule
// for Space and PageDown: with nothing focused, Chrome scrolls from the node last
// pressed. A click on a pane's words focuses nothing, so without this a pane the user had
// just clicked into was no answer at all, and `d` scrolled a page a full-height workspace keeps
// still. Anything on the page outside every region names the page, which is `undefined`
// here as it is for `readingRegionFor`, and so does the body, where a let-go
// (`releaseFocus`) or a press on nothing puts the user. Anything in the chrome names
// nothing new, so opening a menu leaves the pane the user was reading as the answer.
// A key press is not among them: its target is where focus already stands, which
// arrived as a change where the user is (dom/focus.js, `onCurrentLocation`), or the body,
// which is where a click on words leaves it.
//
// The page's own answer is kept apart from a surface's. A region in the chrome, such as
// the Threads list, answers while it shows; once it has closed, the user is back in the
// page region they acted in last (`pageReadingRegion`), which a surface opened on top of
// it never replaced. A landing in the document asks the page's answer alone, since a
// surface is no part of the document it lands in.
let recentRegionId: string | null = null;
let pageRegionId: string | null = null;
// Chrome can focus body between pointerdown on unfocusable words and pointerup.
// That focus belongs to the same press while it is down (dom/focus.js, `pressing`);
// pointerdown has already named its place.
const readingInputReaders: Set<(node: Node) => void> = new Set();
export const onReadingInput = (read: (node: Node) => void) =>
  readingInputReaders.add(read);
const readingInput = (node: Node) => {
  for (const read of readingInputReaders) read(node);
};
// The region the reading keys chose, until the user next acts anywhere
// (`chooseReadingRegion`).
let chosenRegionId: string | null = null;
const actedAt = (at: Node, arriving: boolean) => {
  chosenRegionId = null;
  const region = readingRegionFor(at);
  if (region) {
    recentRegionId = region.id;
    if (inPage(region.host)) pageRegionId = region.id;
  } else if (
    inPage(at) &&
    !(arriving && at === document.body && pressing()?.released === false)
  )
    recentRegionId = pageRegionId = null;
};
for (const type of ["pointerdown", "wheel", "touchstart", "click"])
  addEventListener(
    type,
    (event) => {
      const at = event.composedPath()[0];
      if (!(at instanceof Node)) return;
      if (type !== "click") actedAt(at, false);
      else if (event.isTrusted && event instanceof MouseEvent && event.button === 0)
        readingInput(at);
    },
    { capture: true, passive: true },
  );
// An arrival, by whatever route, a move inside a widget's shadow tree included.
onCurrentLocation((node) => {
  if (node) actedAt(node, true);
});
export const recentReadingRegion = () => readingRegion(recentRegionId);
// A region hidden from layout — a closed panel's list, a pane in a tab not shown — is not
// where the user reads. One scrolled out of the window still is.
const shown = (region: ReadingRegion | undefined) =>
  region?.host.checkVisibility() ? region : undefined;
// A region the reading keys chose for the user (panel/navigation.js, `regionForStep`) is the
// one they acted in, as a wheel there makes it, so a walk goes on from it. It stays the
// keys' choice rather than the user's until the user next acts, which the keys read to
// keep the page ahead of it.
export const chooseReadingRegion = (region: ReadingRegion) => {
  actedAt(region.host, false);
  chosenRegionId = region.id;
};
export const chosenReadingRegion = () => shown(readingRegion(chosenRegionId));
export const pageReadingRegion = () => {
  const at = deepFocus();
  if (focusInPage(at)) return readingRegionFor(at);
  return shown(readingRegion(pageRegionId));
};
export const userReadingRegion = () => {
  const at = deepFocus();
  const region = readingRegionFor(at);
  if (region || focusInPage(at)) return region;
  return shown(recentReadingRegion()) ?? pageReadingRegion();
};

// The deepest region whose body actually contains this node. A region's host includes
// its frame furniture so focus there can still select the region for reading commands;
// geometry that must contain the node itself instead walks outward to the body it lives
// in. Keep that containment walk shared with scrollerFor so placement and travel cannot
// disagree about which reading box holds a control.
export const containingReadingRegionFor = (node: Node | null | undefined) => {
  let region = regionAt(node);
  while (region) {
    if (renderedUnder(node, region.body)) return regionRecord(region);
    region = regionAt(renderedParent(region.host));
  }
  return undefined;
};

const asRegion = (regionOrNode: RegionTarget) => {
  if (typeof regionOrNode === "string") return registered().get(regionOrNode);
  if (!regionOrNode) return undefined;
  const named = registered().get(regionOrNode.id);
  if (named || !(regionOrNode instanceof Element)) return named;
  const containing = readingRegionFor(regionOrNode);
  return containing ? regions.get(containing.id) : undefined;
};

const scrolls = (box: Element) => userScrollport(getComputedStyle(box).overflowY);

// "bounded" when the region's own body scrolls, "flow" when something outside it does.
export const regionScrollBehavior = (regionOrNode: RegionTarget) => {
  const region = asRegion(regionOrNode);
  return region &&
    live(region) &&
    !concealed(region) &&
    !skipped(region.body) &&
    scrolls(region.body)
    ? "bounded"
    : "flow";
};

export function effectiveScroller(regionOrNode: RegionTarget): Element {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (regionScrollBehavior(region) === "bounded") return region.body;
  const containing = [...regionsAround(region.host, byBody)]
    .filter((candidate) => candidate !== region)
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return containing ? effectiveScroller(containing) : pageScroller;
}

// Which box scrolls a given element, for anything that has to name its scroller rather
// than search for one. The document's for everything the document holds — and the
// panel's own list for a widget an agent put in a reply, which is scrolled by that and
// by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
// that never comes. The list answers here as any region does: the panel registers it as
// its bounded reading region (`registerReadingRegion`).
export const scrollerFor = (el: Node | null | undefined) => {
  const region = containingReadingRegionFor(el);
  return region ? effectiveScroller(region) : pageScroller;
};

installScrollerLookup(scrollerFor);

export function shownRegionBounds(regionOrNode: RegionTarget) {
  const region = asRegion(regionOrNode);
  if (!region || hidden(region)) return null;
  return shownRect(region.body, new Map());
}

export function watchReadingRegionTransitions(
  listener: (transition: ReadingTransition) => void,
) {
  transitionWatchers.add(listener);
  return () => transitionWatchers.delete(listener);
}

const notify = (detail: ReadingTransition) => {
  for (const listener of transitionWatchers) listener(detail);
};

const compositionTransitions = new Map<Element, CompositionTransition>();

export async function preserveReadingRegions(owner: Element, change: () => unknown) {
  const transition = {
    owner,
    regions: readingRegions().filter((region) => under(region.host, owner)),
  };
  // A second choice can supersede an unfinished layout. Its intermediate geometry
  // must not overwrite the reading captured before the first choice.
  notify({
    ...transition,
    phase: "before",
    retained: compositionTransitions.has(owner),
  });
  compositionTransitions.set(owner, transition);
  const releaseReach = holdReach(owner);
  let completed = false;
  try {
    await change();
    completed = true;
  } finally {
    if (compositionTransitions.get(owner) === transition) {
      compositionTransitions.delete(owner);
      notify({
        ...transition,
        phase: "after",
        cancelled: !completed || !owner.isConnected,
      });
      releaseReach();
    }
  }
}

// Whether a region is scrolled by the box last seen for it, at the width last seen.
const asSeen = (
  region: RegionRegistration,
  scroller: Element,
  width: number | undefined,
) => region.scroller === scroller && region.width === width;
let viewportHeight = innerHeight;

// The page's width and the top of its landing band as last seen, or null before the
// first delivery. The page needs no registration: the root is always there, and its
// size changes only with the window's.
let pageSeen: ReturnType<typeof pageGeometry> | null = null;
const pageGeometry = () => ({
  width: pageScroller.clientWidth,
  band: landingBand(pageScroller)?.top ?? 0,
});
// A band that moves with the window's width shifts the page. One that moves without
// it, as a page tab strip arriving does (`--lf-root-headers`, dom/root-headers.js), comes with
// the content that moved it, whose owner keeps the reader's place across it, so it is
// taken as seen wherever it is read: no size need change with it, and left unseen it
// would read as unsettled, recording nothing, until the window next changed.
const pageMoved = (now = pageGeometry()) => {
  if (pageSeen === null) return false;
  if (now.width !== pageSeen.width) return true;
  pageSeen = now;
  return false;
};

// Whether the page and every region stand as last seen. A layout that has handed a
// region to another scroller or rewrapped it or the page, before the observer below has
// announced it, is not a place to record the user's position in: the words have already
// moved under the reader (a flow page clamps as its content leaves), and the restore the
// announcement brings would return them to that moved place. A region hidden from layout
// shows no words to move, and measuring one in skipped content would lay out what it
// skips.
export const regionsSettled = () =>
  viewportHeight === innerHeight &&
  !pageMoved() &&
  [...registered().values()].every(
    (region) =>
      !live(region) ||
      !region.scroller ||
      !shown(region) ||
      asSeen(region, effectiveScroller(region), region.host.offsetWidth),
  );

// Every shown region's scroller and width as last seen, and the page's geometry, so a
// size change that hands a region to a different scroller, or rewraps it or the page, is
// announced once, after layout has produced it. A hidden region keeps what was last seen
// of it and is compared again once it shows. Read on the observer's delivery, which
// follows layout; nothing here writes a box it observes.
function measureRegions() {
  const viewportChanged = viewportHeight !== innerHeight;
  viewportHeight = innerHeight;
  const shifted: RegionShift[] = [];
  for (const region of registered().values()) {
    if (!live(region) || !shown(region)) continue;
    const scroller = effectiveScroller(region);
    const width = region.host.offsetWidth;
    // A region concealed when last measured, as a closed disclosure's, returns: its
    // words stood in no scroller meanwhile, though one carried its box.
    const away = concealed(region);
    if (region.scroller && (viewportChanged || !asSeen(region, scroller, width)))
      shifted.push({
        region: regionRecord(region),
        from: region.scroller,
        to: scroller,
        returned: Boolean(region.away) && !away,
      });
    region.scroller = scroller;
    region.width = width;
    region.away = away;
  }
  const now = pageGeometry();
  const previousPage = pageSeen;
  if (pageMoved(now) && previousPage)
    shifted.push({ region: null, band: now.band - previousPage.band });
  pageSeen = now;
  if (shifted.length) notify({ phase: "shift", shifted });
}
const sizes = sizeObserver(measureRegions);
sizes.observe(pageScroller);
// A flowing region need not resize when only the window's height changes.
// Share the observer's comparison so one reflow produces one shift reading.
addEventListener("resize", () => nextRender(measureRegions), { passive: true });

// The regions the page's marks state (the header): each marked body with the name and
// host it is registered under, so a body offered again as it stood costs one climb.
//
// - The host is the nearest box around the body that names the region, or the body
//   where none does. The climb stops at a box that is another region's body: a region's
//   host stands inside the region that holds it, so a host further out names some other
//   widget's region of the same name.
// - The region is named after the nearest element with an id, the host itself or one
//   around it, so a pane's region keeps its id whichever body the pane holds, and a
//   widget's regions are named after the widget wherever it stands, a shadow tree
//   included.
// - A name a standing box already holds under that element is no refusal: the later
//   box is a region under an id of this document alone, and keeps that id while it
//   stands. Each answers for what it scrolls, and only the earlier one's place is found
//   again in a replacement document.
const BODY = PAGE_PAINT_ATTRIBUTE.scrollSurface;
const HOST = PAGE_PAINT_ATTRIBUTE.scrollHost;
const stated: Map<Element, { name: string; host: Element; stop: () => void }> =
  new Map();
const hosts = new WeakMap<Element, string>();
function readBody(body: Element) {
  const name = body.isConnected ? body.getAttribute(BODY) : null;
  let host = body;
  for (let at = renderedParent(body); name && at; at = renderedParent(at)) {
    if (at.getAttribute(HOST) === name) host = at;
    if (host === at || at.getAttribute(BODY)) break;
  }
  const held = stated.get(body);
  if (held?.name === name && held.host === host) return;
  held?.stop();
  stated.delete(body);
  if (!name) return;
  const named = regionId(closestAcross(host, "[id]"), name, body);
  const id = live(regions.get(named)) ? regionId(null, name, body) : named;
  stated.set(body, { name, host, stop: registerReadingRegion({ id, host, body }) });
}
// A host's mark can be written after its body's region is registered, or taken off
// while the body stands, so each change to what a box hosts offers again the bodies it
// hosted and those it may host now: the marked ones in its own tree, and in its shadow
// stage where the box is a widget hosting a body it drew there.
function readHost(box: Element) {
  const name = box.isConnected ? box.getAttribute(HOST) : null;
  if (name === (hosts.get(box) ?? null)) return;
  if (name === null) hosts.delete(box);
  else hosts.set(box, name);
  for (const region of [...(byHost.get(box) ?? [])]) readBody(region.body);
  if (name === null) return;
  const named = `[${BODY}="${CSS.escape(name)}"]`;
  for (const tree of [box, stageOf(box)])
    for (const body of tree?.querySelectorAll(named) ?? []) readBody(body);
}
const readBox = (box: Element) => {
  readHost(box);
  readBody(box);
};
readMarks = watchArrivals(`[${BODY}]:not([${BODY}=""]), [${HOST}]`, [BODY, HOST], {
  arrive: readBox,
  leave: readBox,
});
