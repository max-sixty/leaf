/* Review one immutable Playwright recording. Playwright owns capture and native
 * clocks; Leaf owns comments. Browsing remains local mechanical state.
 * Phases, images and saved-tree nodes have archive-scoped comment coordinates.
 * A phase prefers its PNG, otherwise the latest same-page frame. Earlier empty
 * points preview the first real capture, labeled with its actual later time.
 * Recording-wide operations preserve the chosen image's real page and time.
 * Pixel comments identify that image; semantic comments identify a saved-tree
 * path. Sequential image and tree captures do not imply pixel alignment.
 *
 * One chronology includes every original operation, checkpoint and frame. The
 * timeline (timeline.js) draws it on one time scale: a mark's left edge is its
 * recorded time, intervals are bars from start to end, and labels only annotate.
 * Viewer.js owns image inspection.
 *
 * Words at rest are the recording's facts, not how to read them. Times count from
 * the recording's start, which a reader assumes, so nothing says so; a basis that
 * departs from it, the first captured event or a clock per stream, stands under the
 * point's heading. The zoom readout is the scale alone, since the image's grab
 * cursor says it drags and its accessible name says how keys pan it. Rejected
 * (2026-10-19): a muted line saying each of these at rest, and the default basis as
 * the heading's hover title, which neither a key nor a finger reaches.
 *
 * Each fact about where the playhead stands has one label at rest: its time in the
 * toolbar, the moment it stands on as the selected Moments row, and the call and its
 * checkpoint in the selected point's details. The toolbar adds the shown image's own
 * time only where it differs from the playhead's; the image's badge names the input
 * and its relation alone, and its caption only what nothing else says, the page where
 * the recording has several, a frame, and a preview. Rejected (2026-10-25): the same
 * time on five labels around one image, and the moment's name in the toolbar beside
 * its selected row.
 *
 * The playhead is a time. The shown evidence is the latest capture at or before
 * it. A checkpoint with an image stands at that image's capture time, which ends
 * the snapshot its DOM time begins; one without stands at its DOM time. Stepping,
 * a moment or a mark sets the time to that stop's own time, while
 * scrubbing and playback leave the playhead between captures and say which
 * capture is shown. Native input events carry no timestamp. A call's bar spans the
 * recorded call, its Action checkpoint is the capture taken just before input is
 * dispatched, and the image names and points at an input only once it is sent:
 * from that checkpoint until the call ends and INPUT_HOLD has passed, so a click
 * stays visible at recorded pace, or until a later input is sent, and only on a
 * capture taken from that checkpoint on. An input still to come shows only in the Input
 * lane: marking its target through the call's wait for actionability read as a
 * click that had already happened (2026-10-13, replacing a mark across the whole
 * call). It never implies a held key. At rest the badge also says whether the
 * shown capture comes just before, during or after the input's call; during
 * playback it names the input alone, since that relation changes faster than it
 * can be read at recorded pace. During
 * playback a plain image shows each capture in time over the Viewer, which takes
 * over again when playback stops; the clock waits only when the image on screen
 * would trail it by more than MAX_LAG.
 * The stage preserves a useful image minimum and grows in document flow when
 * its transport, evidence and tools cannot fit the viewport. Scope and saved
 * moments follow the evidence in normal flow, so their number cannot shrink the image.
 * Later metadata never
 * overlaps it. Empty and captured states reserve the same image allocation.
 *
 * Recorded pace preserves native timing. Review pace integrates important
 * input/result intervals without skipping boundaries or changing coordinates.
 * Explicit navigation and inspection pause playback; ordinary page scrolling
 * does not. Authored bookmark keys pair semantic results in a comparison group;
 * equal labels or clocks never establish correspondence between recordings.
 *
 * Scope-specific image views and time windows outlive their renderers. Same-page
 * captures retain inspected scale and origin; fitted images continue to fit. A
 * pending Viewer prepares offscreen, then atomically commits decoded pixels, caption
 * and comment identity before retiring the old surface. Inspection can settle on the
 * still-visible capture during that wait. Filmstrip frames retain the latest
 * same-page saved checkpoint and its exact comment identity. Saved elements has one
 * stable disclosure, a reading region whose subject is the checkpoint whose tree it
 * shows: the runtime keeps the reader's place in each checkpoint's tree, and returns
 * them to it as the tree opens or the checkpoint returns
 * (reading-regions.js, `showReadingSubject`). Explicit destination navigation opens
 * the disclosure and lands on its destination instead.
 */
import {
  generatedElement,
  dragging,
  cancelAnimation,
  nextAnimation,
  compoundReadingRegionId,
  registerReadingRegion,
  keepsHidden,
  el,
  focusDestination,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  holdFocus,
  html,
  actionTemplate,
  iconTemplate,
  inBaseLayer,
  live,
  nothing,
  classMap,
  styleMap,
  offered,
  offeredAction,
  pressIsKeyboardActivation,
  createRef,
  ref,
  render,
  repeat,
  keeps,
  keepsText,
  layoutPx,
  LeafElement,
  onUserInput,
  signal,
  quoted,
  registerVisualParts,
  scopedMediaUrl,
  retainUserIntent,
  scrollBehavior,
  scrollIntoReadingBand,
  setChildren,
  showReadingSubject,
  sizeObserver,
  whileConnected,
  currentLocationIn,
  commandsChanged,
} from "/runtime/widget-api.js";

import { advancePlayback, mergeIntervals } from "./playback.js";
import { RecordingTimeline } from "./timeline.js";

// Reuse the default package’s selected WebAwesome controls, already shipped with Leaf.
import "/vendor/webawesome.esm.js";
import { Viewer, css as imageCss } from "/vendor/images.esm.js";
// Dependency styles apply only inside recording widgets. Keeping them in their
// module makes the same presentation available in an offline export.
if (!document.querySelector("#lf-trace-library-styles")) {
  const styles = document.createElement("style");
  styles.id = "lf-trace-library-styles";
  styles.textContent = inBaseLayer(`@scope (lf-trace) { ${imageCss} }`);
  document.head.append(styles);
}

/** @typedef {import("../../../browser/types/contract.js").DataPlaywrightTrace} Recording */
/** @typedef {Recording["actions"][number]} TraceAction */
/** @typedef {Recording["images"][number]} TraceImage */
/** @typedef {NonNullable<TraceAction["phases"]["before"]>} Checkpoint */
/** @typedef {NonNullable<Checkpoint["tree"]>} SavedTree */
/** @typedef {SavedTree["nodes"][number]} SavedNode */
/** @typedef {keyof typeof PHASES} Phase */
/** @typedef {{id: string, action: TraceAction, phase: Phase, timestamp: number, image?: never}} ActionPoint */
/** @typedef {ActionPoint | {id: string, image: TraceImage, timestamp: number, action?: never, phase?: never}} TracePoint */
/** @typedef {{image: TraceImage | null} & ({tree: SavedTree, treePoint: ActionPoint} | {tree: null, treePoint: null})} Evidence */
/** @typedef {{id: string, node: SavedNode}} TreeRow */
/** @typedef {{index: number, target: string, label: string | null, key: string | null}} Bookmark */
/** @typedef {Bookmark & {scope: string, stream: string, time: number, number: number}} AvailableMoment */
/** @typedef {AvailableMoment | (Bookmark & {scope: undefined, stream: undefined, time: null, number: number})} Moment */
/** @typedef {TraceAction & {input: NonNullable<TraceAction["input"]>}} InputAction */
/** @typedef {{figure: HTMLElement, canvas: HTMLDivElement, img: HTMLImageElement, status: HTMLSpanElement}} ImageSurface */
/** @typedef {Viewer & {image: HTMLImageElement, viewer: HTMLDivElement, imageData: {width: number, x: number, y: number, ratio: number}, onResize: () => void}} CompletedViewer */
/** @param {Viewer | null} viewer @returns {viewer is CompletedViewer} */
function completedViewer(viewer) {
  return (
    !!viewer &&
    viewer.viewed &&
    viewer.image instanceof HTMLImageElement &&
    viewer.viewer instanceof HTMLDivElement &&
    typeof viewer.onResize === "function" &&
    typeof viewer.imageData.width === "number" &&
    typeof viewer.imageData.x === "number" &&
    typeof viewer.imageData.y === "number" &&
    typeof viewer.imageData.ratio === "number"
  );
}
/** @typedef {{image: TraceImage, figure: HTMLElement, viewer: Viewer | null, scope: string | null, resolve: () => void, ready: Promise<void>}} PendingPicture */
/** @typedef {{width: number, x: number, y: number}} InspectionView */
/** @typedef {{selected?: string | null, cursorTime?: number | null, image?: InspectionView | null, timeline?: import("./timeline.js").TimelineView | null}} ScopeView */
/** @typedef {{label: string, scope: string, pageId: string | null} & ({action: TraceAction, phase: Phase, node?: SavedNode, image?: never} | {image: TraceImage, action?: never, phase?: never, node?: never})} TraceTarget */
/** @param {TraceAction | null | undefined} action @param {Phase | null | undefined} phase */
function checkpointOf(action, phase) {
  return phase === "before" || phase === "action" || phase === "after"
    ? action?.phases[phase]
    : undefined;
}

/** @template {Element} T @param {import("lit/directives/ref.js").Ref<T>} target @returns {T} */
function completedRef(target) {
  if (!target.value)
    throw new Error("The recording view has not completed its native controls");
  return target.value;
}

const PHASES = {
  before: "Before",
  action: "Action",
  after: "After",
  start: "Start",
  end: "Completion",
};
// How a capture of an input call relates to its dispatch. The Action checkpoint
// is captured just before the input is sent.
const INPUT_PHASES = {
  before: "before",
  action: "next",
  after: "after",
};
// Native input methods by the gesture a reader recognizes.
/** @type {Readonly<Record<string, string>>} */
const INPUT_NAMES = {
  click: "Click",
  dblclick: "Double-click",
  tap: "Tap",
  hover: "Hover",
  fill: "Fill",
  check: "Check",
  uncheck: "Uncheck",
  selectOption: "Select",
  setInputFiles: "Choose files",
  keyboardType: "Type",
  keyboardInsertText: "Insert text",
  type: "Type",
  mouseWheel: "Wheel",
  mouseMove: "Mouse move",
  mouseDown: "Mouse down",
  mouseUp: "Mouse up",
  mouseClick: "Click",
  dragTo: "Drag",
};
// The marks that make a drawn part a datum on a Leaf page, taken off a part kept after
// it stops showing one.
const MARKS = [
  "data-lf-datum",
  "data-lf-identity",
  "data-lf-datum-label",
  "data-lf-origin-path",
];
// The longest an image on screen may trail the playing clock, in milliseconds.
const MAX_LAG = 150;
// How long after an input is sent the image keeps marking it, in milliseconds of
// recording: a click's call often ends a few milliseconds after it is sent, which
// playback at recorded pace would show for no frame at all.
const INPUT_HOLD = 500;
// When an input call is known to have sent its input: its Action checkpoint, or,
// without one, the call's end.
/** @param {TraceAction} action */
const inputSent = (action) =>
  action.phases.action?.timestamp ?? action.endTime ?? action.startTime;
/** @param {string} text */
const hex = (text) =>
  [...new globalThis.TextEncoder().encode(text)]
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
// Derived display origins are computed once per source delivery. Navigation and
// label formatting only read this map; the archive keeps its native timestamps.
/** @param {import("../../../browser/types/contract.js").DataPlaywrightTrace} trace */
function streamOrigins(trace) {
  const origins = new Map(
    trace.streams.map((stream) => [
      stream.id,
      {
        start: stream.monotonicTime ?? Infinity,
        recordedStart: stream.monotonicTime,
      },
    ]),
  );
  for (const action of trace.actions) {
    const origin = origins.get(action.stream);
    if (!origin)
      throw new Error(`Action names unknown recording stream ${action.stream}`);
    origin.start = Math.min(origin.start, action.startTime);
  }
  for (const image of trace.images) {
    const origin = origins.get(image.stream);
    if (!origin)
      throw new Error(`Image names unknown recording stream ${image.stream}`);
    origin.start = Math.min(origin.start, image.timestamp);
  }
  return new Map([...origins].filter(([, origin]) => Number.isFinite(origin.start)));
}
/** @param {SavedNode} node */
const nodeName = (node) =>
  [node.role, node.name || node.text].filter(Boolean).join(" · ") ||
  "Unnamed saved element";
/** @param {number} ms */
const seconds = (ms) => `${(ms / 1000).toFixed(3)} s`;
// During playback a plain image shows each capture in time; the inspectable
// Viewer surface takes over again when playback stops. The canvas is the part;
// the Viewer image names it to assistive tech.
const playbackLayer = () =>
  Object.assign(el("img", "lf-trace-playback-image"), {
    alt: "",
    ariaHidden: "true",
    hidden: true,
  });

// A command row owns each transport button's activation and availability.
/** @param {import("lit/directives/ref.js").Ref<HTMLButtonElement>} target @param {string} label @param {string} action @param {boolean} disabled @param {string} [title] */
const transport = (target, label, action, disabled, title = label) =>
  html`<button
    ${offeredAction("symbol", "lf-trace-transport-button", label, { title, action })}
    ${ref(target)}
    ?disabled=${disabled}
  ></button>`;

/** @typedef {{
 * timelineHost: HTMLElement,
 * body: HTMLElement,
 * stage: HTMLElement,
 * metadata: HTMLElement,
 * viewport: HTMLElement,
 * imageHost: HTMLElement,
 * imageTools: HTMLElement,
 * zoomLabel: HTMLElement,
 * imageScale: HTMLButtonElement,
 * imageScaleOptions: HTMLElement,
 * tree: HTMLDetailsElement,
 * treeList: HTMLElement,
 * sources: import("@awesome.me/webawesome/dist/components/radio-group/radio-group.js").default,
 * first: HTMLButtonElement,
 * play: HTMLButtonElement,
 * previous: HTMLButtonElement,
 * next: HTMLButtonElement,
 * zoomIn: HTMLButtonElement,
 * zoomOut: HTMLButtonElement,
 * zoomFit: HTMLButtonElement,
 * positionLabel: HTMLElement,
 * selectionLabel: HTMLElement,
 * actionDetails: HTMLElement,
 * phaseHeading: HTMLElement,
 * }} TraceNodes */

export class Trace extends LeafElement {
  /** @type {TraceNodes | null} */
  #nativeNodes = null;
  get #nodes() {
    return (this.#nativeNodes ??= {
      timelineHost: completedRef(this.#timelineHost),
      body: completedRef(this.#body),
      stage: completedRef(this.#stage),
      metadata: completedRef(this.#metadata),
      viewport: completedRef(this.#viewport),
      imageHost: completedRef(this.#imageHost),
      imageTools: completedRef(this.#imageTools),
      zoomLabel: completedRef(this.#zoomLabel),
      imageScale: completedRef(this.#imageScale),
      imageScaleOptions: completedRef(this.#imageScaleOptions),
      tree: completedRef(this.#tree),
      treeList: completedRef(this.#treeList),
      sources: completedRef(this.#sources),
      first: completedRef(this.#first),
      play: completedRef(this.#play),
      previous: completedRef(this.#previous),
      next: completedRef(this.#next),
      zoomIn: completedRef(this.#zoomIn),
      zoomOut: completedRef(this.#zoomOut),
      zoomFit: completedRef(this.#zoomFit),
      positionLabel: completedRef(this.#positionLabel),
      selectionLabel: completedRef(this.#selectionLabel),
      actionDetails: completedRef(this.#actionDetails),
      phaseHeading: completedRef(this.#phaseHeading),
    });
  }
  // The recording, set by whoever hosts the widget: Leaf from the bound source (the
  // registry's `x-data.trace.property`), or null while that source has none.
  static properties = { value: { attribute: false } };

  constructor() {
    super();
    /** @type {import("../../../browser/types/contract.js").DataPlaywrightTrace | null} */
    this.value = null;
  }

  // The recording the last render read, and the one shown.
  /** @type {import("../../../browser/types/contract.js").DataPlaywrightTrace | null | undefined} */
  #delivered;
  /** @type {import("../../../browser/types/contract.js").DataPlaywrightTrace | null | undefined} */
  #shown;
  // The elements the last paint marked as drawn data.
  /** @type {Set<Element>} */
  #marked = new Set();
  /** @type {ReturnType<typeof streamOrigins>} */
  #origins = new Map();
  /** @type {Map<string | null, {width: number, height: number}>} */
  #imageSizes = new Map();
  /** @type {import("../../../browser/types/contract.js").DataPlaywrightTrace | null} */
  #trace = null;
  /** @type {string | null} */
  #scope = null;
  /** @type {string | null} */
  #selected = null;
  /** @type {ReturnType<typeof registerVisualParts> | null} */
  #visualParts = null;
  get #parts() {
    if (!this.#visualParts)
      throw new Error("The recording has not registered its visual parts");
    return this.#visualParts;
  }
  /** @type {import("../../../browser/runtime/visual-parts.js").VisualPart[]} */
  #inventory = [];
  /** @type {Map<string, TraceTarget>} */
  #targets = new Map();
  /** @type {Map<string, ImageSurface>} */
  #images = new Map();
  /** @type {HTMLDivElement | null} */
  #renderedView = null;
  get #view() {
    if (!this.#renderedView) throw new Error("The recording has not built its view");
    return this.#renderedView;
  }
  /** @type {[TracePoint | null, Evidence, TreeRow[]]} */
  #drawing = [null, { image: null, tree: null, treePoint: null }, []];

  get #recording() {
    if (!this.#trace) throw new Error("The recording has not arrived");
    return this.#trace;
  }

  createRenderRoot() {
    return this.#view;
  }
  /** @type {ActionPoint | null} */
  #metadataPoint = null;
  #pace = "recorded";
  /** @type {{pointerId: number, pause: boolean} | null} */
  #pressedPlay = null;
  /** @type {Bookmark[]} */
  #bookmarks = [];
  /** @type {Moment[]} */
  #moments = [];
  /** @type {number | null} */
  #chosenBookmark = null;
  /** @type {Map<string | null, {start: number, end: number}>} */
  #boundsByScope = new Map();
  /** @type {RecordingTimeline | null} */
  #drawnTimeline = null;
  get #timeline() {
    if (!this.#drawnTimeline)
      throw new Error("The recording has not built its timeline");
    return this.#drawnTimeline;
  }
  /** @type {string | null} */
  #timelineScope = null;
  /** @type {PendingPicture | null} */
  #pendingPicture = null;
  /** @type {Map<string | null, ScopeView>} */
  #scopeViews = new Map();
  /** @type {InspectionView | null} */
  #pendingInspection = null;
  #applyingPictureView = false;
  /** @type {{viewer: CompletedViewer | null, image: TraceImage, scope: string | null} | null} */
  #shownPicture = null;
  get #committedPicture() {
    if (!this.#shownPicture) throw new Error("The recording has no committed capture");
    return this.#shownPicture;
  }
  get #picture() {
    return this.#shownPicture?.viewer ?? null;
  }
  get #pictureId() {
    return this.#shownPicture?.image.id ?? null;
  }
  get #pictureScope() {
    return this.#shownPicture?.scope ?? null;
  }
  #picturePreview = false;
  #playFrame = 0;
  #playing = false;
  /** @type {boolean | null} */
  #playIntent = null;
  // The playhead's time from the scope origin when it stands between captures,
  // after scrubbing or playback. Null when it stands on the selected capture. A
  // signal, because the step and event commands' liveness reads it.
  /** @type {import("@preact/signals-core").Signal<number | null>} */
  #cursor = signal(null);
  get #cursorTime() {
    return this.#cursor.value;
  }
  set #cursorTime(time) {
    this.#cursor.value = time;
  }
  #scrubbing = false;
  // Nodes of the Lit view that their imperative owners below read and write.
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #timelineHost = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #body = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #stage = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #metadata = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #viewport = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #imageHost = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #imageTools = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #zoomLabel = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #imageScale = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #imageScaleOptions = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLDetailsElement>} */
  #tree = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #treeList = createRef();
  /** @type {import("lit/directives/ref.js").Ref<import("@awesome.me/webawesome/dist/components/radio-group/radio-group.js").default>} */
  #sources = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #first = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #play = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #previous = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #next = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #zoomIn = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #zoomOut = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLButtonElement>} */
  #zoomFit = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #positionLabel = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #selectionLabel = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #actionDetails = createRef();
  /** @type {import("lit/directives/ref.js").Ref<HTMLElement>} */
  #phaseHeading = createRef();
  // Viewer owns the viewport's figures; these overlays stand beside them.
  #missingImage = el("p", "lf-trace-missing-image");
  #inputBadge = Object.assign(el("span", "lf-trace-input-badge"), { hidden: true });
  #inputPoint = Object.assign(el("span", "lf-trace-input-point"), { hidden: true });
  #playbackImage = playbackLayer();
  #reviewGesture = (/** @type {Event} */ event) => {
    const path = event.composedPath();
    // Native scroller input belongs to the inspector; widget commands own
    // their own inspection. Page navigation never changes the recording.
    if (
      path.includes(this.#nodes.metadata) &&
      (event.type === "wheel" ||
        event.type === "pointerdown" ||
        (event instanceof KeyboardEvent &&
          ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(
            event.key,
          )))
    )
      this.pause();
    // Freeze a mouse press before drawing or image dragging claims it. A
    // touch press may start page scrolling; its tap or drawing claim decides.
    else if (
      event instanceof PointerEvent &&
      event.pointerType !== "touch" &&
      path.includes(this.#nodes.viewport)
    )
      this.#inspectEvidence();
  };
  #inspectEvidence() {
    this.pause();
    // A review gesture freezes the pixels actually on screen, including when
    // another capture is still preparing.
    const shown = this.#playbackId ?? this.#pictureId;
    if ((this.#pendingPicture || this.#playbackId) && shown)
      this.#reveal(this.#id("image", shown));
  }
  #visibility = () => {
    if (document.hidden) this.pause();
  };

  // Viewer owns its container sizing; reapply the page's inspection view after
  // a resize refits the image, including a hidden tab becoming visible.
  #resize = () => {
    if (!this.#nodes.viewport.clientWidth) {
      this.pause();
      if (this.#pendingPicture) this.#closePicture();
      return;
    }
    if (!this.#picture && this.#trace) this.#draw();
    if (!this.#picture?.viewed) return;
    const canvas = this.#imageSurface(this.#pictureId).canvas;
    const viewer = this.#picture.viewer;
    if (
      viewer.clientWidth === canvas.offsetWidth &&
      viewer.clientHeight === canvas.offsetHeight
    )
      return;
    this.#picture.resize();
    const image = this.#committedPicture.image;
    this.#applyPictureView(this.#picture, image);
    this.#placePlayback();
    this.#imageZoom();
    this.#parts.update();
  };

  setup() {
    this.#build();
    const timeline = this.#nodes.timelineHost;
    // Element command scopes leave with their element; a return keeps the declaration.
    if (!quoted(this)) {
      this.lfCommands = {
        title: "In a Playwright recording",
        rows: [
          // Back along the time scale is the arrow toward its start. The scale
          // runs left to right in every text direction (base.css), so its arrows
          // are fixed rather than read from the computed direction, which would
          // force a style recalculation each time the page's keys are reflected.
          {
            id: "trace.previous",
            keys: ["ArrowLeft"],
            title: "previous timeline point",
            control: this.#nodes.previous,
            when: () => this.#position() > 0 || this.#cursorTime !== null,
            run: () => this.#step(-1),
          },
          {
            id: "trace.next",
            keys: ["ArrowRight"],
            title: "next timeline point",
            control: this.#nodes.next,
            when: () => this.#position() < this.#items().length - 1,
            run: () => this.#step(1),
          },
          {
            id: "trace.zoom-in",
            keys: () => (currentLocationIn(timeline) ? ["="] : []),
            title: "zoom the timeline in",
            control: this.#nodes.zoomIn,
            when: () => this.#timeline.canZoomIn,
            run: () => this.#zoom(() => this.#timeline.zoomBy(2)),
          },
          {
            id: "trace.zoom-out",
            keys: () => (currentLocationIn(timeline) ? ["-"] : []),
            title: "zoom the timeline out",
            control: this.#nodes.zoomOut,
            when: () => this.#timeline.canZoomOut,
            run: () => this.#zoom(() => this.#timeline.zoomBy(0.5)),
          },
          {
            id: "trace.zoom-fit",
            keys: () => (currentLocationIn(timeline) ? ["0"] : []),
            title: "show the whole recording",
            control: this.#nodes.zoomFit,
            when: () => this.#timeline.canZoomOut,
            run: () => this.#zoom(() => this.#timeline.fit()),
          },
          {
            id: "trace.previous-event",
            keys: () => (currentLocationIn(timeline) ? ["Shift+ArrowLeft"] : []),
            title: "previous input or moment",
            when: () => this.#eventStop(-1) !== null,
            run: () => this.#navigate(this.#eventStop(-1)),
          },
          {
            id: "trace.next-event",
            keys: () => (currentLocationIn(timeline) ? ["Shift+ArrowRight"] : []),
            title: "next input or moment",
            when: () => this.#eventStop(1) !== null,
            run: () => this.#navigate(this.#eventStop(1)),
          },
          {
            id: "trace.play",
            keys: () => (currentLocationIn(timeline) ? [" "] : []),
            title: () => (this.#playing ? "pause recording" : "play recording"),
            control: this.#nodes.play,
            when: () => this.#items().length > 1,
            run: () => {
              const pause = this.#playIntent ?? this.#playing;
              this.#playIntent = null;
              if (pause) this.pause();
              else this.#startPlayback();
            },
          },
        ],
      };
      commandsChanged(this);
    }
    whileConnected(this, (signal) => {
      document.addEventListener("visibilitychange", this.#visibility, { signal });
      const stopInput = onUserInput(this.#reviewGesture);
      const resizer = sizeObserver(this.#resize);
      resizer.observe(this.#nodes.viewport);
      const stopReading = [
        { name: "recording", host: this, body: this.#nodes.body },
        {
          name: "point-details",
          host: this.#nodes.metadata,
          body: this.#nodes.metadata,
        },
        { name: "saved-elements", host: this.#nodes.tree, body: this.#nodes.tree },
      ].map(({ name, host, body }) =>
        registerReadingRegion({
          id: compoundReadingRegionId(this, name),
          host,
          body,
        }),
      );
      // A returning recording draws the picture its departure closed.
      if (this.#trace) this.#draw();
      return () => {
        this.pause(false);
        dragging(this, false);
        stopInput();
        for (const stop of stopReading.toReversed()) stop();
        resizer.disconnect();
        this.#closePicture();
      };
    });
  }

  render() {
    this.#delivered = this.value;
    return this.#template(...this.#drawing);
  }

  // A recording draws each delivery once, after Lit's update, since showing it moves
  // focus, playback and the picture.
  /** @param {import("lit").PropertyValues} changed */
  updated(changed) {
    super.updated(changed);
    if (this.#delivered === this.#shown) return;
    this.#shown = this.#delivered;
    this.#show(this.#shown ?? null);
  }

  #build() {
    this.#bookmarks = [...this.querySelectorAll(":scope > lf-trace-bookmark")].map(
      (member, index) => {
        const target = member.getAttribute("target");
        if (!target) throw new Error("A recording bookmark needs its target");
        return {
          index,
          target,
          label: member.getAttribute("label"),
          key: member.getAttribute("key"),
        };
      },
    );
    // Authored bookmarks remain outside the live view's one Lit root.
    this.#renderedView = generatedElement(el("div", "lf-trace-view"), { says: false });
    this.append(this.#view);
    render(this.#template(...this.#drawing), this.#view, this.renderOptions);
    // Viewer owns the viewport's figures and the timeline module its own
    // drawing; neither region holds a Lit child part.
    this.#nodes.viewport.append(this.#missingImage, ...this.#overlays());
    this.#drawnTimeline = new RecordingTimeline(this.#nodes.timelineHost, {
      quoted: quoted(this),
      onSeek: (time, final) => this.#seek(time, final),
      onPick: (lane, id, time) => this.#pick(lane, id, time),
      onUserPan: () => {
        if (this.#playing) this.pause();
      },
      // Zoom availability follows the window a gesture left.
      onZoom: () => commandsChanged(this),
    });
    this.addEventListener("lf-inspect", (event) => this.#inspect(event));
    this.#visualParts = registerVisualParts(this, () => this.#inventory, {
      label: (id) => this.#targets.get(id)?.label ?? null,
      reveal: (id) => this.#reveal(id),
    });
    if (!quoted(this)) {
      this.#nodes.timelineHost.lfCommands = {
        title: "On a recording timeline",
        rows: [
          {
            id: "trace.first",
            travels: true,
            keys: ["Home"],
            title: "first capture",
            control: this.#nodes.first,
            when: () => this.#items().length > 0,
            run: () => this.#navigate(this.#items().at(0)?.id ?? null),
          },
          {
            id: "trace.last",
            travels: true,
            keys: ["End"],
            title: "last capture",
            run: () => this.#navigate(this.#items().at(-1)?.id ?? null),
          },
        ],
      };
      commandsChanged(this.#nodes.timelineHost);
    }
  }

  // Review gestures belong to evidence, independently of navigation layout.
  /** @param {Event} event */
  #inspect(event) {
    const path = event.composedPath();
    if (path.includes(this.#nodes.metadata)) this.pause();
    else if (
      event.type === "lf-inspect" ||
      path.includes(this.#nodes.viewport) ||
      path.includes(this.#nodes.imageTools)
    )
      this.#inspectEvidence();
  }

  /** @param {string} kind @param {string} value */
  #id(kind, value) {
    return `trace-${this.#recording.archive.sha256}-${kind}-${value}`;
  }
  /** @param {string | null | undefined} stream */
  #origin(stream) {
    return stream == null ? undefined : this.#origins.get(stream);
  }
  /** @param {string | null | undefined} id */
  #capturedImage(id) {
    return id == null ? null : (this.#imageById.get(id) ?? null);
  }
  /** @param {string} id */
  #indexedTarget(id) {
    const target = this.#targets.get(id);
    if (!target) throw new Error(`The recording has no indexed target ${id}`);
    return target;
  }
  /** @param {string | null | undefined} id */
  #imageSurface(id) {
    const surface = id == null ? null : this.#images.get(id);
    if (!surface) throw new Error(`The recording has no mounted image surface ${id}`);
    return surface;
  }

  /** @param {number} value @param {string | undefined} stream */
  #time(value, stream) {
    const origin = this.#origin(stream);
    if (!origin) throw new Error(`The recording has no origin for stream ${stream}`);
    return seconds(value - origin.start);
  }
  /** @param {string} id */
  #pageLabel(id) {
    const index = this.#recording.pages.findIndex((page) => page.id === id);
    const page = this.#recording.pages[index];
    if (!page) throw new Error(`The recording has no page ${id}`);
    const stream = this.#recording.streams.findIndex(
      (stream) => stream.id === page.stream,
    );
    return `Page ${index + 1}${this.#recording.streams.length > 1 ? ` · Stream ${stream + 1}` : ""}`;
  }
  /** @param {TraceAction} action @param {Phase} phase */
  #phaseId(action, phase) {
    return this.#id("phase", `${action.id}-${phase}`);
  }
  /** @param {TraceAction} action @param {Phase} phase @param {SavedNode} node */
  #nodeId(action, phase, node) {
    return `${this.#phaseId(action, phase)}-node-${hex(node.path)}`;
  }
  /** @param {string} stream @param {string | null} pageId */
  #includes(stream, pageId) {
    const page = this.#trace?.pages.find((page) => page.id === this.#scope);
    return page ? stream === page.stream && pageId === page.id : stream === this.#scope;
  }
  #actions() {
    return (
      this.#trace?.actions.filter(
        (action) =>
          this.#includes(action.stream, action.pageId) ||
          Object.values(action.phases).some((phase) =>
            this.#includes(action.stream, phase.pageId),
          ),
      ) ?? []
    );
  }
  #frames() {
    return (
      this.#trace?.images
        .filter(
          (image) =>
            this.#includes(image.stream, image.pageId) && image.kind === "frame",
        )
        .sort((a, b) => a.timestamp - b.timestamp) ?? []
    );
  }
  /** @returns {ActionPoint[]} */
  #checkpoints() {
    /** @type {ActionPoint[]} */
    const points = [];
    for (const action of this.#actions())
      for (const phase of this.#phases(action)) {
        const checkpoint = checkpointOf(action, phase);
        if (!this.#includes(action.stream, checkpoint?.pageId ?? action.pageId))
          continue;
        points.push({
          id: this.#phaseId(action, phase),
          action,
          phase,
          timestamp: this.#phaseTime(action, phase),
        });
      }
    return points;
  }
  // A checkpoint stands where what it shows was captured: at its image, whose
  // capture finishes after the DOM snapshot that starts it, or else at that
  // snapshot. A call without checkpoints stands at its start and end.
  /** @param {TraceAction} action @param {Phase} phase @returns {number} */
  #phaseTime(action, phase) {
    const checkpoint = checkpointOf(action, phase);
    if (checkpoint?.imageId) {
      const image = this.#capturedImage(checkpoint.imageId);
      if (!image)
        throw new Error(`Checkpoint names unknown image ${checkpoint.imageId}`);
      return image.timestamp;
    }
    if (checkpoint) return checkpoint.timestamp;
    if (phase === "end") {
      if (action.endTime === null)
        throw new Error("An unfinished call has no completion checkpoint");
      return action.endTime;
    }
    return action.startTime;
  }
  /** @type {Map<string, TraceImage>} */
  #imageById = new Map();
  /** @type {{key: string, points: TracePoint[]} | null} */
  #itemsCache = null;
  #items() {
    const key = `${this.#trace?.archive.sha256}:${this.#scope}`;
    if (this.#itemsCache?.key === key) return this.#itemsCache.points;
    /** @type {TracePoint[]} */
    const points = this.#checkpoints();
    for (const image of this.#frames())
      points.push({
        id: this.#id("image", image.id),
        image,
        timestamp: image.timestamp,
      });
    // Stable ties retain native phase order, then archive image order. There is
    // one stop per native checkpoint, never synthetic start/end duplicates.
    points.sort((a, b) => a.timestamp - b.timestamp);
    this.#itemsCache = { key, points };
    return points;
  }
  #point() {
    return this.#items().find((point) => point.id === this.#selected) ?? null;
  }
  /** @param {TracePoint | null} point @returns {Evidence} */
  #evidence(point) {
    const action = point?.action;
    const phase = checkpointOf(action, point?.phase);
    const pageId = phase?.pageId ?? action?.pageId;
    let image = point?.image ?? this.#capturedImage(phase?.imageId) ?? null;
    // Otherwise the latest image of the page captured at or before the stop.
    if (!image && action)
      image =
        this.#recording.images
          .filter(
            (image) =>
              image.stream === action.stream &&
              (!pageId || image.pageId === pageId) &&
              image.timestamp <= point.timestamp,
          )
          .sort((a, b) => a.timestamp - b.timestamp)
          .at(-1) ?? null;
    if (!image && point) {
      // A recording may begin before its first screencast. Preview the first
      // real image, retaining its later timestamp and exact comment identity.
      image =
        this.#recording.images
          .filter(
            (image) =>
              image.stream === (action?.stream ?? point.image?.stream) &&
              (!pageId || image.pageId === pageId),
          )
          .sort((a, b) => a.timestamp - b.timestamp)[0] ?? null;
    }
    const treePoint =
      phase?.tree && point?.action
        ? point
        : this.#checkpoints()
            .sort((a, b) => a.timestamp - b.timestamp)
            .filter(
              (candidate) =>
                point !== null &&
                candidate.timestamp <= point.timestamp &&
                candidate.action.stream === (action?.stream ?? point?.image?.stream) &&
                checkpointOf(candidate.action, candidate.phase)?.pageId ===
                  (pageId ?? point?.image?.pageId) &&
                checkpointOf(candidate.action, candidate.phase)?.tree,
            )
            .at(-1);
    const tree = checkpointOf(treePoint?.action, treePoint?.phase)?.tree;
    return tree && treePoint
      ? { image, tree, treePoint }
      : { image, tree: null, treePoint: null };
  }
  #selectDefault() {
    // Authored moments name the review's entry point. Otherwise start with
    // saved page content, then an original image. A late filmstrip frame gets
    // its own stop, never attached to an earlier call.
    const items = this.#items();
    const moment = this.#scopeMoments()[0];
    const destination = moment ? this.#destination(moment.target) : null;
    const point =
      items.find((point) => point.id === destination) ??
      items.find((point) => this.#evidence(point).tree?.nodes.length) ??
      items.find((point) => {
        const image = this.#evidence(point).image;
        return image && image.timestamp <= point.timestamp;
      }) ??
      items[0];
    this.#chosenBookmark = moment && destination === point?.id ? moment.index : null;
    this.#selected = point?.id ?? null;
    this.#cursorTime = null;
  }
  #position() {
    return Math.max(
      0,
      this.#items().findIndex((point) => point.id === this.#selected),
    );
  }
  /** @param {string | null} id */
  #navigate(id) {
    this.pause(false);
    this.#chosenBookmark = null;
    this.#selected = id;
    this.#cursorTime = null;
    this.#draw();
    this.#revealTime("center");
  }
  /** @param {number} delta */
  #step(delta) {
    const items = this.#items();
    // From a playhead between captures, Previous returns to the shown capture.
    if (delta < 0 && this.#cursorTime !== null) {
      const point = this.#point();
      if (point && point.timestamp - this.#bounds().start < this.#cursorTime)
        return this.#navigate(point.id);
    }
    const next = Math.max(0, Math.min(items.length - 1, this.#position() + delta));
    this.#navigate(items[next]?.id ?? null);
  }
  // The capture shown at a playhead time: the latest at or before it, or the
  // first capture when the time precedes every capture.
  /** @param {number} elapsed */
  #pointAt(elapsed) {
    const items = this.#items();
    const first = items[0];
    if (!first) throw new Error("A recording with no captures has no playhead");
    const time = this.#bounds().start + elapsed;
    return items.findLast((point) => point.timestamp <= time) ?? first;
  }
  /** @param {number} elapsed @param {boolean} final */
  #seek(elapsed, final) {
    if (this.#playing) this.pause(false);
    if (this.#scrubbing !== !final) {
      this.#scrubbing = !final;
      dragging(this, !final);
    }
    this.#chosenBookmark = null;
    const point = this.#pointAt(elapsed);
    this.#cursorTime = elapsed;
    if (point && point.id !== this.#selected) {
      this.#selected = point.id;
      this.#draw();
    } else this.#drawTime();
  }
  /** @param {string} lane @param {string} id @param {number} time */
  #pick(lane, id, time) {
    if (lane === "moments") {
      const moment = this.#moments.find((moment) => String(moment.number) === id);
      if (moment?.scope) this.#visitMoment(moment.target, moment.index, false);
      return;
    }
    const action = this.#recording.actions.find((action) => action.id === id);
    if (!action) return;
    const phases = this.#phases(action);
    const at = (/** @type {Phase} */ phase) =>
      this.#phaseTime(action, phase) - this.#bounds().start;
    // An input's Action checkpoint shows its target just before dispatch.
    // A call's mark picks the checkpoint nearest the press.
    const phase =
      lane === "input" && phases.includes("action")
        ? "action"
        : phases.reduce((best, phase) =>
            Math.abs(at(phase) - time) < Math.abs(at(best) - time) ? phase : best,
          );
    const destination = this.#phaseId(action, phase);
    if (this.#items().some((point) => point.id === destination))
      this.#navigate(destination);
  }
  pause(draw = true) {
    if (!this.#playing && !this.#scrubbing) return;
    // A playing film is continuous mechanical motion, outside resting proof.
    // Pausing keeps the playhead where it stands.
    if (this.#playFrame) cancelAnimation(this.#playFrame);
    this.#playFrame = 0;
    this.#playing = false;
    this.#playbackWanted = null;
    if (this.#scrubbing) {
      this.#scrubbing = false;
      dragging(this, false);
    }
    if (draw) this.#draw();
  }
  #startPlayback() {
    const points = this.#items();
    const [first, second, ...remaining] = points;
    if (!first || !second) return;
    const last = remaining.at(-1) ?? second;
    const origin = this.#bounds().start;
    const end = last.timestamp;
    const selected = this.#point() ?? first;
    // Playback starts at the playhead and includes every original capture.
    let time =
      this.#cursorTime !== null ? origin + this.#cursorTime : selected.timestamp;
    if (time >= end) time = first.timestamp;
    this.#playing = true;
    this.#chosenBookmark = null;
    this.#cursorTime = time - origin;
    this.#selected = this.#pointAt(this.#cursorTime).id;
    this.#draw();
    let previousTick = performance.now();
    const intervals = mergeIntervals([
      ...this.#inputActions().map(
        /** @returns {import("./playback.js").Interval} */ (action) => [
          action.startTime - 200,
          (action.endTime ?? action.startTime) + 450,
        ],
      ),
      ...this.#scopeMoments().map(
        /** @returns {import("./playback.js").Interval} */ (moment) => {
          const target = this.#targets.get(moment.target);
          return [target?.action?.startTime ?? moment.time - 400, moment.time + 300];
        },
      ),
    ]);
    const tick = () => {
      this.#playFrame = 0;
      if (!this.#playing) return;
      const now = performance.now();
      // Like a video player, playback keeps time and skips images that cannot
      // be shown in time, but the clock waits once the image on screen falls
      // more than MAX_LAG behind it. The readout names that image's own time.
      const shown = this.#shownImage();
      const waiting = this.#pendingPicture || this.#playbackWanted;
      if (waiting && (!shown || time - shown.timestamp > MAX_LAG)) {
        previousTick = now;
        this.#playFrame = nextAnimation(tick);
        return;
      }
      time = Math.min(
        end,
        advancePlayback(
          time,
          now - previousTick,
          this.#pace === "review" ? intervals : null,
        ),
      );
      previousTick = now;
      this.#cursorTime = time - origin;
      const point = this.#pointAt(this.#cursorTime);
      if (point.id !== this.#selected) {
        this.#selected = point.id;
        this.#draw();
        this.#warm(points.indexOf(point));
      } else this.#drawTime();
      this.#revealTime("page");
      if (time === end) this.pause();
      else this.#playFrame = nextAnimation(tick);
    };
    this.#playFrame = nextAnimation(tick);
  }
  // Fetch and decode the next captures playback will show.
  #warmed = new Set();
  /** @param {number} index */
  #warm(index) {
    for (const point of this.#items().slice(index + 1, index + 9)) {
      const image = this.#evidence(point).image;
      if (!image || this.#warmed.has(image.url)) continue;
      this.#warmed.add(image.url);
      const loader = new globalThis.Image();
      loader.src = scopedMediaUrl(image.url);
      loader.decode().catch(() => this.#warmed.delete(image.url));
    }
  }

  // The nearest input call or moment beyond the playhead, as a capture stop.
  /** @param {number} delta */
  #eventStop(delta) {
    const time = this.#playheadTime();
    if (time === null) return null;
    const stops = new Set(
      [
        ...this.#inputActions().map((action) => {
          const phase = this.#phases(action).includes("action")
            ? "action"
            : this.#phases(action)[0];
          return this.#phaseId(action, phase);
        }),
        ...this.#scopeMoments().map((moment) => this.#destination(moment.target)),
      ].filter(Boolean),
    );
    const items = this.#items().filter((point) => stops.has(point.id));
    return (
      (delta > 0
        ? items.find((point) => point.timestamp > time)
        : items.findLast((point) => point.timestamp < time)
      )?.id ?? null
    );
  }

  /** @param {TraceAction} action @returns {[Phase, ...Phase[]]} */
  #phases(action) {
    /** @type {("before" | "action" | "after")[]} */
    const candidates = ["before", "action", "after"];
    const [first, ...rest] = candidates.filter((phase) => action.phases[phase]);
    if (first) return [first, ...rest];
    return action.endTime === null ? ["start"] : ["start", "end"];
  }

  /** @param {import("../../../browser/types/contract.js").DataPlaywrightTrace | null} trace */
  #show(trace) {
    this.pause(false);
    const restore = holdFocus(this);
    const oldArchive = this.#trace?.archive.sha256;
    this.#trace = trace;
    this.#boundsByScope.clear();
    this.#itemsCache = null;
    this.#origins = this.#trace ? streamOrigins(this.#trace) : new Map();
    this.#imageById = new Map(this.#trace?.images.map((image) => [image.id, image]));
    // Every recording/page scope reserves its complete captured extent, including
    // earlier empty stops. Viewer fits each original inside this stable canvas.
    this.#imageSizes = new Map();
    for (const image of this.#trace?.images ?? []) {
      for (const scope of [image.pageId, image.stream]) {
        const extent = this.#imageSizes.get(scope);
        this.#imageSizes.set(scope, {
          width: Math.max(extent?.width ?? 0, image.width),
          height: Math.max(extent?.height ?? 0, image.height),
        });
      }
    }
    this.classList.toggle("lf-rendered", this.#trace !== null);
    if (oldArchive !== this.#trace?.archive.sha256) {
      this.#timelineScope = null;
      this.#closePicture();
      this.#images.clear();
      this.#scopeViews.clear();
      this.#metadataPoint = null;
      this.#scope = null;
      this.#selected = null;
      this.#cursorTime = null;
      this.#chosenBookmark = null;
      setChildren(this.#nodes.viewport, [this.#missingImage, ...this.#overlays()]);
    }
    if (this.#trace) {
      const choices = this.#scopeChoices();
      const chooseScope = !choices.some(([id]) => id === this.#scope);
      this.#indexTargets();
      const scopeOrder = new Map(
        this.#recording.streams.map((stream, index) => [stream.id, index]),
      );
      this.#moments = this.#bookmarks
        .map((member) => this.#moment(member))
        .toSorted(
          (a, b) =>
            (a.stream === undefined
              ? Infinity
              : (scopeOrder.get(a.stream) ?? Infinity)) -
              (b.stream === undefined
                ? Infinity
                : (scopeOrder.get(b.stream) ?? Infinity)) ||
            Number(a.time) - Number(b.time),
        )
        .map((moment, index) => ({ ...moment, number: index + 1 }));
      // Authored moments choose the opening stream; otherwise the first.
      if (chooseScope)
        this.#scope =
          this.#moments.find((moment) => moment.scope)?.stream ??
          choices[0]?.[0] ??
          null;
    } else {
      this.#targets.clear();
      this.#moments = [];
    }
    this.#draw();
    restore?.(this.#nodes.sources);
    this.dispatchEvent(new Event("lf-trace-ready"));
    // Readiness may select a paired moment in another stream. Apply an incoming
    // inspection once that destination exists, outside the archive reset above.
    if (this.#trace && this.#pendingInspection) {
      this.inspectionView = this.#pendingInspection;
      this.#pendingInspection = null;
    }
  }

  /** @returns {[string, string][]} */
  #scopeChoices() {
    return this.#recording.streams.flatMap(
      /** @returns {[string, string][]} */ (stream, index) => {
        const pages = this.#recording.pages.filter((page) => page.stream === stream.id);
        return [
          [
            stream.id,
            this.#recording.streams.length > 1
              ? `Stream ${index + 1}`
              : pages.length > 1
                ? "All pages"
                : "Recording",
          ],
          ...(pages.length > 1
            ? pages.map(
                /** @returns {[string, string]} */ (page) => [
                  page.id,
                  this.#pageLabel(page.id),
                ],
              )
            : []),
        ];
      },
    );
  }

  #scopeView(scope = this.#scope) {
    let view = this.#scopeViews.get(scope);
    if (!view) {
      view = {};
      this.#scopeViews.set(scope, view);
    }
    return view;
  }

  /** @param {string} scope */
  #selectScope(scope) {
    if (scope === this.#scope) return;
    this.pause(false);
    Object.assign(this.#scopeView(), {
      selected: this.#selected,
      cursorTime: this.#cursorTime,
    });
    this.#cancelPicture();
    this.#scope = scope;
    const saved = this.#scopeView();
    this.#selected = saved.selected ?? null;
    this.#cursorTime = saved.cursorTime ?? null;
  }

  /** @param {string} stream @param {string | null} pageId */
  #targetScope(stream, pageId) {
    return pageId &&
      this.#recording.pages.filter((page) => page.stream === stream).length > 1
      ? pageId
      : stream;
  }

  #indexTargets() {
    this.#targets.clear();
    for (const action of this.#recording.actions) {
      const firstPhase = this.#phases(action)[0];
      const pageId = action.pageId;
      const firstPageId = checkpointOf(action, firstPhase)?.pageId ?? pageId;
      const scope = this.#targetScope(action.stream, firstPageId);
      this.#targets.set(this.#id("action", action.id), {
        action,
        scope,
        pageId: firstPageId,
        phase: firstPhase,
        label: action.title,
      });
      for (const phase of this.#phases(action)) {
        this.#targets.set(this.#phaseId(action, phase), {
          action,
          pageId: checkpointOf(action, phase)?.pageId ?? pageId,
          scope: this.#targetScope(
            action.stream,
            checkpointOf(action, phase)?.pageId ?? pageId,
          ),
          phase,
          label: `${action.title} · ${PHASES[phase]}`,
        });
        for (const node of checkpointOf(action, phase)?.tree?.nodes ?? [])
          this.#targets.set(this.#nodeId(action, phase, node), {
            action,
            pageId: checkpointOf(action, phase)?.pageId ?? pageId,
            scope: this.#targetScope(
              action.stream,
              checkpointOf(action, phase)?.pageId ?? pageId,
            ),
            phase,
            node,
            label: `${action.title} · ${PHASES[phase]} · ${nodeName(node)} · path ${node.path}`,
          });
      }
    }
    for (const image of this.#recording.images)
      this.#targets.set(this.#id("image", image.id), {
        image,
        pageId: image.pageId,
        scope: this.#targetScope(image.stream, image.pageId),
        label: `${this.#pageLabel(image.pageId)} · ${image.kind === "frame" ? "Captured frame" : `${PHASES[image.phase]} checkpoint`} · ${this.#time(image.timestamp, image.stream)}`,
      });
  }

  /** @param {string | null | undefined} id */
  #destination(id) {
    if (id == null) return null;
    const target = this.#targets.get(id);
    if (!target) return null;
    if (target.image?.kind === "frame") return id;
    const action =
      target.action ??
      this.#recording.actions.find(
        (action) =>
          action.stream === target.image.stream &&
          action.callId === target.image.callId &&
          checkpointOf(action, target.image.phase)?.imageId === target.image.id,
      );
    return action ? this.#phaseId(action, target.phase ?? target.image.phase) : null;
  }
  // The comparison chooses one declared result; the trace resolves its own
  // archive coordinate, including when its data arrives after the chooser.
  /** @param {string} key */
  selectMoment(key) {
    const match = this.#bookmarks.find((moment) => moment.key === key);
    if (match && this.#targets.has(match.target))
      this.#reveal(match.target, match.index);
  }

  get inspectionView() {
    return this.#trace ? (this.#scopeView().image ?? null) : this.#pendingInspection;
  }
  set inspectionView(view) {
    if (!this.#trace) {
      this.#pendingInspection = view;
      return;
    }
    this.#scopeView().image = view;
    if (this.#picture?.viewed) {
      this.#picture.resize();
      this.#applyPictureView(this.#picture, this.#committedPicture.image);
      this.#imageZoom();
    }
  }

  /** @param {string} id @param {number | null} [bookmark] */
  #reveal(id, bookmark = null) {
    this.pause(false);
    const selected = this.#destination(id);
    if (!selected) return;
    const target = this.#targets.get(id);
    if (!target) return;
    this.#chosenBookmark = bookmark;
    // Following a point already present in the overview keeps that overview.
    // A page filter changes only when it cannot display the exact destination.
    if (
      !this.#includes(
        target.action ? target.action.stream : target.image.stream,
        target.pageId,
      )
    )
      this.#selectScope(target.scope);
    this.#selected = selected;
    this.#cursorTime = null;
    if (target.node) keeps(this.#nodes.tree, "open", "");
    this.#draw();
    this.#revealTime("center");
  }

  // From the Moments list a moment brings its evidence into view if it is not;
  // from the timeline, which stands beside the evidence, it moves nothing.
  /** @param {string} id @param {number} bookmark @param {boolean} [travel] */
  async #visitMoment(id, bookmark, travel = true) {
    const mayArrive = retainUserIntent();
    this.#reveal(id, bookmark);
    const key = this.#bookmarks[bookmark]?.key;
    if (key)
      this.dispatchEvent(new CustomEvent("lf-trace-moment", { detail: { key } }));
    if (!travel) return;
    await this.#pendingPicture?.ready;
    if (!mayArrive() || this.#chosenBookmark !== bookmark) return;
    // A saved element's row stands in the tree's own scroll box, which can hide it
    // inside the window. A nearest landing reveals it there and the tree in the page,
    // and moves nothing that already shows it.
    if (this.#targets.get(id)?.node) {
      const row = this.#inventory.find((part) => part.id === id)?.element;
      if (row) scrollIntoReadingBand(row, row, "nearest", scrollBehavior());
      return;
    }
    const view = this.#nodes.viewport.getBoundingClientRect();
    if (this.#pictureId && !(view.top >= 0 && view.bottom <= innerHeight))
      scrollIntoReadingBand(
        this.#nodes.stage,
        this.#nodes.stage,
        "center",
        scrollBehavior(),
      );
  }

  #stream() {
    return (
      this.#trace?.pages.find((page) => page.id === this.#scope)?.stream ??
      this.#trace?.streams.find((stream) => stream.id === this.#scope)?.id
    );
  }
  #bounds() {
    const saved = this.#boundsByScope.get(this.#scope);
    if (saved) return saved;
    const start = this.#origin(this.#stream())?.start ?? 0;
    let end = start;
    for (const action of this.#actions())
      end = Math.max(end, action.endTime ?? action.startTime);
    for (const point of this.#checkpoints()) end = Math.max(end, point.timestamp);
    for (const image of this.#trace?.images ?? []) {
      if (!this.#includes(image.stream, image.pageId)) continue;
      end = Math.max(end, image.timestamp);
    }
    const bounds = { start, end };
    this.#boundsByScope.set(this.#scope, bounds);
    return bounds;
  }
  /** @param {Bookmark} member @returns {Omit<AvailableMoment, "number"> | Omit<Extract<Moment, {time: null}>, "number">} */
  #moment(member) {
    const target = this.#destination(member.target)
      ? this.#targets.get(member.target)
      : null;
    if (!target) return { ...member, scope: undefined, stream: undefined, time: null };
    return {
      ...member,
      scope: target.scope,
      stream: target.action ? target.action.stream : target.image.stream,
      time: target.action
        ? this.#phaseTime(target.action, target.phase)
        : target.image.timestamp,
    };
  }
  #scopeMoments() {
    return this.#moments.filter(
      /** @returns {moment is AvailableMoment} */ (moment) =>
        moment.scope !== undefined &&
        (moment.scope === this.#scope || moment.stream === this.#scope),
    );
  }
  #imageZoom() {
    this.#drawInput();
    const percent = `${Math.round((this.#picture?.imageData.ratio ?? 1) * 100)}%`;
    const fitted = !this.#scopeView().image;
    keepsText(this.#nodes.zoomLabel, fitted ? "Fit" : percent);
    keeps(this.#nodes.imageScale, "title", fitted ? `Fit · ${percent}` : percent);
    for (const button of this.#nodes.imageScaleOptions.querySelectorAll("button"))
      keeps(
        button,
        "aria-pressed",
        button.dataset.scale === "fit"
          ? fitted
          : !fitted && this.#picture?.imageData.ratio === 1,
      );
    keepsText(
      this.#nodes.imageTools.querySelector(".lf-trace-tools-status"),
      this.#picture?.viewed
        ? ""
        : this.#pendingPicture
          ? "Loading capture…"
          : this.#pictureId
            ? "Image unavailable"
            : "No captured image",
    );
  }

  /** @param {number} x @param {number} y */
  #panPicture(x, y) {
    this.#inspectEvidence();
    this.#picture?.move(x, y);
  }

  #fitPicture() {
    if (!this.#picture?.viewed) return;
    const image = this.#committedPicture.image;
    this.#scopeView().image = null;
    this.#applyPictureView(this.#picture, image);
    this.#imageZoom();
    this.#parts.update();
  }

  /** @param {Viewer | null} viewer */
  #rememberPictureView(viewer) {
    if (
      !completedViewer(viewer) ||
      viewer !== this.#picture ||
      this.#applyingPictureView
    )
      return;
    const width = this.#imageSurface(this.#pictureId).canvas.clientWidth;
    const { width: pixels, x, y } = viewer.imageData;
    this.#scopeView(this.#pictureScope).image = {
      width: pixels / width,
      x: x / width,
      y: y / width,
    };
  }

  /** @param {CompletedViewer} viewer @param {TraceImage} image */
  #applyPictureView(viewer, image) {
    const canvas = this.#imageSurface(image.id).canvas;
    const view = this.#scopeView().image;
    this.#applyingPictureView = true;
    try {
      // Capture encodings differ in native size. Scope-relative extent and origin
      // preserve the inspection across them, empty points, and container resizing.
      const ratio = view
        ? (view.width * canvas.clientWidth) / image.width
        : Math.min(
            canvas.clientWidth / image.width,
            canvas.clientHeight / image.height,
          );
      viewer.zoomTo(ratio);
      viewer.moveTo(
        view
          ? view.x * canvas.clientWidth
          : (canvas.clientWidth - image.width * ratio) / 2,
        view
          ? view.y * canvas.clientWidth
          : (canvas.clientHeight - image.height * ratio) / 2,
      );
    } finally {
      this.#applyingPictureView = false;
    }
  }

  #cancelPicture() {
    this.#pendingPicture?.resolve?.();
    this.#pendingPicture?.viewer?.destroy();
    this.#pendingPicture?.figure.remove();
    this.#pendingPicture = null;
  }

  #overlays() {
    return [this.#inputBadge, this.#inputPoint];
  }

  // The image on screen: the playback image while it shows, else the Viewer's.
  #shownImage() {
    return this.#playbackId
      ? this.#capturedImage(this.#playbackId)
      : (this.#shownPicture?.image ?? null);
  }

  // Show a capture at once during playback by drawing it over the committed
  // Viewer image, in the same place and scale. Captures of another size or page
  // wait for the Viewer, as do all of them once playback stops.
  /** @type {string | null} */
  #playbackId = null;
  /** @type {string | null} */
  #playbackWanted = null;
  /** @param {TraceImage} image */
  #playFast(image) {
    const committed = this.#shownPicture?.image ?? null;
    if (
      !this.#playing ||
      !this.#picture?.viewed ||
      this.#pendingPicture ||
      !committed ||
      committed.pageId !== image.pageId ||
      committed.width !== image.width ||
      committed.height !== image.height
    )
      return false;
    if (image.id === this.#pictureId) {
      this.#hidePlayback();
      return true;
    }
    if ((this.#playbackWanted ?? this.#playbackId) === image.id) return true;
    this.#playbackWanted = image.id;
    const loader = new globalThis.Image();
    loader.src = scopedMediaUrl(image.url);
    loader.decode().then(
      () => {
        if (
          this.#playbackWanted !== image.id ||
          !this.#playing ||
          !this.#picture?.viewed
        )
          return;
        this.#playbackWanted = null;
        const layer = this.#playbackImage;
        keeps(layer, "src", loader.src);
        this.#playbackId = image.id;
        this.#placePlayback();
        keepsHidden(this.#playbackImage, false);
        this.#draw();
      },
      () => {
        if (this.#playbackWanted === image.id) this.#playbackWanted = null;
      },
    );
    return true;
  }
  // The playback image stands inside the committed Viewer's canvas, over its
  // image at the same place and scale, so a hit on it reaches the canvas part.
  #placePlayback() {
    if (this.#playbackId === null || !this.#picture?.viewed) return;
    const canvas = this.#imageSurface(this.#pictureId).canvas;
    const raster = this.#picture.image.getBoundingClientRect();
    const host = canvas.getBoundingClientRect();
    /** @type {(["left" | "top" | "width" | "height", number])[]} */
    const dimensions = [
      ["left", raster.left - host.left - canvas.clientLeft],
      ["top", raster.top - host.top - canvas.clientTop],
      ["width", raster.width],
      ["height", raster.height],
    ];
    const place = dimensions.map(([name, value]) => ({ name, value: layoutPx(value) }));
    let layer = this.#playbackImage;
    // A new canvas, or a hidden image returning elsewhere, gets a new element:
    // it appears where it stands rather than travelling there.
    if (
      layer.parentElement !== canvas ||
      (layer.hidden && place.some(({ name, value }) => layer.style[name] !== value))
    ) {
      const fresh = Object.assign(playbackLayer(), {
        hidden: layer.hidden,
        src: layer.src,
      });
      layer.remove();
      canvas.append(fresh);
      this.#playbackImage = layer = fresh;
    }
    for (const { name, value } of place)
      if (layer.style[name] !== value) layer.style[name] = value;
  }
  #hidePlayback() {
    this.#playbackWanted = null;
    if (this.#playbackId === null) return;
    this.#playbackId = null;
    keepsHidden(this.#playbackImage, true);
  }

  #closePicture() {
    this.#hidePlayback();
    this.#cancelPicture();
    keeps(this.#nodes.imageHost, "aria-busy", null);
    this.#picture?.destroy();
    this.#shownPicture = null;
  }

  /** @param {TraceImage | null} image */
  #drawPicture(image) {
    if (!image) {
      this.#closePicture();
      setChildren(this.#nodes.viewport, [this.#missingImage, ...this.#overlays()]);
      return;
    }
    if (this.#playFast(image)) return;
    if (this.#pendingPicture?.image.id !== image.id) this.#cancelPicture();
    const point = this.#point();
    const preview =
      point !== null &&
      image.timestamp > point.timestamp &&
      !checkpointOf(point?.action, point?.phase)?.imageId;
    if (this.#pictureId === image.id) {
      // A refreshed index keeps the Viewer, but its image belongs to the new
      // delivery, including the origin path drawn from that delivery's array.
      this.#committedPicture.image = image;
      this.#hidePlayback();
      this.#picturePreview = preview;
      if (this.#pictureScope !== this.#scope && this.#picture?.viewed) {
        this.#applyPictureView(this.#picture, image);
        this.#committedPicture.scope = this.#scope;
      }
      keeps(this.#nodes.imageHost, "aria-busy", null);
      this.#imageZoom();
      return;
    }
    if (this.#pendingPicture) return;
    const { figure, canvas, img: source, status } = this.#imageSurface(image.id);
    if (!figure.classList.contains("lf-trace-image-pending"))
      figure.classList.add("lf-trace-image-pending");
    if (!figure.classList.contains("lf-trace-image-loading"))
      figure.classList.add("lf-trace-image-loading");
    keeps(figure, "inert", "");
    keeps(figure, "aria-hidden", "true");
    keepsText(status, "Loading captured image…");
    setChildren(this.#nodes.viewport, [
      this.#missingImage,
      ...(this.#pictureId ? [this.#imageSurface(this.#pictureId).figure] : []),
      figure,
      ...this.#overlays(),
    ]);
    if (!canvas.clientWidth) {
      keeps(this.#nodes.imageHost, "aria-busy", null);
      return;
    }
    const { promise: ready, resolve } = Promise.withResolvers();
    /** @type {PendingPicture} */
    const pending = {
      image,
      figure,
      viewer: null,
      scope: this.#scope,
      ready,
      resolve: () => resolve(undefined),
    };
    this.#pendingPicture = pending;
    keeps(this.#nodes.imageHost, "aria-busy", "true");
    const current = () => this.#pendingPicture === pending;
    {
      const commit = (/** @type {CompletedViewer | null} */ viewer) => {
        if (!current()) return;
        const retired = this.#picture;
        const hadFocus = currentLocationIn(this.#nodes.viewport);
        this.#shownPicture = { viewer, image, scope: pending.scope };
        // Leaf owns container resize so unchanged window signals leave the
        // inspected image alone. Viewer otherwise refits it on every signal.
        if (viewer) window.removeEventListener("resize", viewer.onResize);
        this.#picturePreview = preview;
        this.#pendingPicture = null;
        this.#hidePlayback();
        keeps(this.#nodes.imageHost, "aria-busy", null);
        figure.classList.remove("lf-trace-image-pending");
        figure.inert = false;
        keeps(figure, "aria-hidden", null);
        keeps(source, "hidden", "");
        setChildren(this.#nodes.viewport, [
          this.#missingImage,
          figure,
          ...this.#overlays(),
        ]);
        if (hadFocus) focusDestination(canvas, "return");
        retired?.destroy();
        this.#imageZoom();
        this.#draw();
        pending.resolve();
      };
      const failed = () => {
        if (!current()) return;
        pending.viewer?.destroy();
        keepsText(status, "Captured image could not load.");
        commit(null);
      };
      // Viewer clears its canvas before decoding a replacement. Prepare its
      // complete surface separately; only public viewed + decoded pixels can
      // replace the committed capture and its exact comment identity.
      source.decode().then(() => {
        if (!current()) return;
        pending.viewer = new Viewer(source, {
          inline: true,
          // The page owns this inline surface. Viewer backdrop dismissal
          // emulates a click after touch scrolling, even without a tap.
          backdrop: false,
          title: false,
          navbar: false,
          toolbar: false,
          button: false,
          tooltip: false,
          transition: false,
          keyboard: false,
          focus: false,
          initialCoverage: 1,
          minWidth: 1,
          minHeight: 1,
          rotatable: false,
          scalable: false,
          rotateOnGesture: false,
          zoomOnWheel: false,
          slideOnWheel: false,
          toggleOnDblclick: false,
          move: (event) => {
            // Before the browser claims pan-y, even a page swipe can produce
            // horizontal movement. Playback leaves touch movement to the page;
            // a tap pauses for inspection and enables image dragging.
            if (
              event.detail.originalEvent instanceof PointerEvent &&
              event.detail.originalEvent.pointerType === "touch" &&
              this.#playing
            ) {
              event.preventDefault();
              return;
            }
            if (event.detail.originalEvent) {
              this.#inspectEvidence();
              this.#hidePlayback();
            }
          },
          zoom: (event) => {
            if (event.detail.originalEvent) {
              this.#inspectEvidence();
              this.#hidePlayback();
            }
          },
          view: (event) =>
            event.detail.image.addEventListener("error", failed, { once: true }),
          viewed: (event) => {
            event.detail.image.decode().then(() => {
              if (!current()) return;
              const viewer = pending.viewer;
              if (!completedViewer(viewer)) {
                failed();
                return;
              }
              this.#applyPictureView(viewer, image);
              figure.classList.remove("lf-trace-image-loading");
              commit(viewer);
            }, failed);
          },
          moved: () => {
            this.#rememberPictureView(pending.viewer);
            this.#placePlayback();
            this.#drawInput();
            this.#parts.update();
          },
          zoomed: () => {
            this.#rememberPictureView(pending.viewer);
            this.#placePlayback();
            this.#imageZoom();
            this.#drawInput();
            this.#parts.update();
          },
        });
      }, failed);
    }
    this.controller.present(ready);
  }

  /** @param {TraceAction} action */
  #inputLabel(action) {
    const key = action.input?.key;
    if (key && action.method === "keyboardDown") return `Key down ${key}`;
    if (key && action.method === "keyboardUp") return `Key up ${key}`;
    if (key) return `Press ${key}`;
    return (
      INPUT_NAMES[action.method] ??
      action.method.charAt(0).toUpperCase() + action.method.slice(1)
    );
  }

  #inputActions() {
    return this.#actions().filter(
      /** @returns {action is InputAction} */ (action) => action.input !== null,
    );
  }

  // The input the shown evidence concerns, which the image marks only once it is
  // sent: the input call of the Action or After checkpoint the playhead stands
  // on, or the latest input sent before the playhead, until its call has ended
  // and INPUT_HOLD has passed. What is still to come stands in the timeline's
  // Input lane, not on the image.
  /** @returns {TraceAction | null} */
  #currentInput() {
    const point = this.#point();
    const time = this.#playheadTime();
    if (time === null) return null;
    if (
      point?.action?.input &&
      (point.phase === "action" || point.phase === "after") &&
      Math.abs(time - point.timestamp) < 0.5
    )
      return point.action;
    // A later input sent supersedes an earlier one, however long its call runs.
    let latest = null;
    for (const action of this.#inputActions()) {
      const sent = inputSent(action);
      if (sent <= time && (!latest || sent > inputSent(latest))) latest = action;
    }
    if (!latest) return null;
    const sent = inputSent(latest);
    return time <= Math.max(latest.endTime ?? sent, sent + INPUT_HOLD) ? latest : null;
  }

  // How an image relates to an input call, from the image's own capture: its
  // checkpoint phase when it is one of the call's, otherwise its time.
  /** @param {TraceImage} image @param {TraceAction} action */
  #inputRelation(image, action) {
    if (image.kind === "checkpoint" && image.callId === action.callId)
      return INPUT_PHASES[image.phase];
    // Before the Action checkpoint the input has not been sent; after it, and
    // until the call ends, it may have been.
    const send = action.phases.action?.timestamp ?? null;
    if (image.timestamp < (send ?? action.startTime)) return "before";
    if (send !== null && Math.abs(image.timestamp - send) < 0.5) return "next";
    if (image.timestamp > (action.endTime ?? action.startTime)) return "after";
    return "during";
  }

  #playheadTime() {
    const point = this.#point();
    if (!point) return null;
    return this.#cursorTime !== null
      ? this.#bounds().start + this.#cursorTime
      : point.timestamp;
  }

  #drawInput() {
    // A restored view adjusts zoom and pan together. Viewer emits each
    // intermediate pose synchronously; draw only after that view is complete.
    if (this.#applyingPictureView) return;
    const input = this.#currentInput();
    const image = this.#shownImage();
    const imageReady = image && this.#picture?.viewed;
    // The image on screen can trail the playhead. One captured before the input
    // was sent shows nothing of it, so it names none.
    const read = input && image ? this.#inputRelation(image, input) : null;
    const relation = read === "before" ? null : read;
    const action = relation ? input : null;
    keepsHidden(this.#inputBadge, !action || !imageReady);
    const span = action
      ? `${this.#time(action.startTime, action.stream)}–${this.#time(action.endTime ?? action.startTime, action.stream)}`
      : "";
    // At rest the badge says whether the input was next, under way or done; the
    // toolbar says when (the header's labels at rest). Playing, those words would
    // change within a few hundred milliseconds of each input, so the badge names
    // the input alone.
    keepsText(
      this.#inputBadge,
      !action || !relation
        ? ""
        : this.#playing
          ? this.#inputLabel(action)
          : `${relation === "next" ? "next:" : relation} ${this.#inputLabel(action)}`,
    );
    keeps(
      this.#inputBadge,
      "title",
      action && relation
        ? `This image was captured ${relation === "next" ? "at the Action checkpoint, just before the input is sent" : `${relation} the input call`}. ${this.#inputLabel(action)}${action.input?.selector ? ` · ${action.input?.selector}` : ""} · call ${span}. Key-down and hold times are not recorded.`
        : null,
    );
    // The point marks where the input lands in the shown capture's viewport.
    const coordinate = action?.input?.point;
    const viewport = action?.input?.viewport;
    const visible =
      coordinate &&
      viewport &&
      imageReady &&
      image.pageId === action.pageId &&
      this.#picture?.viewed;
    keepsHidden(this.#inputPoint, !visible);
    if (visible) {
      const raster = this.#picture.image.getBoundingClientRect();
      const host = this.#nodes.viewport.getBoundingClientRect();
      // A capture scales the viewport by its width; a screencast frame may also
      // crop the viewport's foot, so its height says nothing of the scale.
      const scale = raster.width / viewport.width;
      const left = layoutPx(raster.left - host.left + coordinate.x * scale);
      const top = layoutPx(raster.top - host.top + coordinate.y * scale);
      if (this.#inputPoint.style.left !== left) this.#inputPoint.style.left = left;
      if (this.#inputPoint.style.top !== top) this.#inputPoint.style.top = top;
      keeps(this.#inputPoint, "title", this.#inputLabel(action));
    }
  }

  // The timeline model: every mark of the scope at its own recorded time.
  #timelineModel() {
    const bounds = this.#bounds();
    const origin = bounds.start;
    const point = this.#point();
    const playhead = this.#playheadTime();
    const inside = (/** @type {TraceAction} */ action) =>
      playhead !== null &&
      action.startTime <= playhead &&
      playhead <= (action.endTime ?? action.startTime);
    const span = (/** @type {TraceAction} */ action) =>
      action.endTime === null
        ? `${this.#time(action.startTime, action.stream)}, unfinished`
        : `${this.#time(action.startTime, action.stream)}–${this.#time(action.endTime, action.stream)}`;
    const inputs = [];
    const calls = [];
    for (const action of this.#actions().toSorted(
      (a, b) => a.startTime - b.startTime,
    )) {
      const mark = {
        id: action.id,
        start: action.startTime - origin,
        end: (action.endTime ?? action.startTime) - origin,
        current: point?.action === action,
        active: inside(action),
      };
      if (action.input) {
        // The notch is the Action snapshot's own time: the archive orders it,
        // not its image, before the input is sent.
        const send = action.phases.action?.timestamp ?? null;
        inputs.push({
          ...mark,
          send: send === null ? null : send - origin,
          label: !action.input.key
            ? this.#inputLabel(action)
            : action.method === "keyboardDown"
              ? `${action.input.key}↓`
              : action.method === "keyboardUp"
                ? `${action.input.key}↑`
                : action.input.key,
          title: `${this.#inputLabel(action)} · call ${span(action)}${send === null ? "" : ` · Action checkpoint ${this.#time(send, action.stream)}, just before it is sent`}`,
        });
      } else
        calls.push({
          ...mark,
          label: action.method,
          error: !!action.error,
          title: `${action.title} · ${span(action)}${action.error ? ` · ${action.error}` : ""}`,
        });
    }
    const moments = this.#scopeMoments().map((moment) => ({
      id: String(moment.number),
      number: moment.number,
      time: moment.time - origin,
      title: `${moment.number} · ${moment.label} · ${this.#time(moment.time, moment.stream)}`,
      current: this.#momentSelected(moment),
    }));
    const captures = this.#items().map((item) => ({
      id: item.id,
      time: item.timestamp - origin,
      image: !!(item.image ?? checkpointOf(item.action, item.phase)?.imageId),
      current: item.id === this.#selected,
    }));
    return {
      signature: `${this.#recording.archive.sha256}:${this.#scope}:${origin}:${bounds.end}:${moments.map((moment) => `${moment.number}@${moment.time}`).join(",")}`,
      duration: Math.max(1, bounds.end - origin),
      time: playhead === null ? 0 : playhead - origin,
      moments,
      inputs,
      calls,
      captures,
    };
  }

  /** @param {"page" | "center"} mode */
  #revealTime(mode) {
    const time = this.#playheadTime();
    if (time !== null) this.#timeline.reveal(time - this.#bounds().start, mode);
  }

  /** @param {() => void} change */
  #zoom(change) {
    this.pause();
    change();
    commandsChanged(this);
  }

  // The playhead and its readout, without redrawing evidence. Playback changes
  // these on every frame, and `#draw`, which renders the view and projects its
  // parts, is too heavy to run per frame, so they are written directly; so is
  // the image zoom status, which changes on each pinch step.
  #drawTime() {
    const playhead = this.#playheadTime();
    if (this.#trace && playhead !== null)
      this.#timeline.setTime(playhead - this.#bounds().start);
    keepsText(
      this.#nodes.positionLabel,
      playhead === null ? "No recorded points" : this.#time(playhead, this.#stream()),
    );
    // The readout reserves the recording's longest time, so the selection beside
    // it holds still while playback changes its digits.
    const longest = this.#trace
      ? String(this.#time(this.#bounds().end, this.#stream()).length)
      : "";
    if (
      this.#nodes.positionLabel.style.getPropertyValue("--lf-trace-position-chars") !==
      longest
    )
      this.#nodes.positionLabel.style.setProperty("--lf-trace-position-chars", longest);
    // When the image on screen was taken at another time than the playhead,
    // say so: between captures, at a checkpoint without its own image, or
    // while the next image prepares. What the playhead stands on is said by the
    // selected moment's row and the point's details (the header's labels at rest).
    const shown = this.#shownImage();
    const selection =
      shown && playhead !== null && Math.abs(playhead - shown.timestamp) >= 0.5
        ? `Image from ${this.#time(shown.timestamp, shown.stream)}`
        : "";
    keepsText(this.#nodes.selectionLabel, selection);
    keeps(this.#nodes.selectionLabel, "title", selection || null);
    this.#drawInput();
  }

  /** @param {Moment} moment */
  #momentSelected(moment) {
    return (
      !!moment.scope &&
      this.#destination(moment.target) === this.#selected &&
      (this.#chosenBookmark === null || this.#chosenBookmark === moment.index)
    );
  }

  #drawTimeline() {
    if (!this.#trace || !this.#items().length) return;
    const scope = this.#scope;
    if (scope !== this.#timelineScope && this.#timelineScope !== null)
      this.#scopeView(this.#timelineScope).timeline = this.#timeline.view;
    this.#timeline.update(this.#timelineModel());
    if (scope !== this.#timelineScope) {
      this.#timelineScope = scope;
      this.#timeline.view = this.#scopeView().timeline ?? null;
    }
  }

  // Lit owns the native controls and metadata. Library surfaces and the
  // per-frame labels (`#drawTime`) keep their imperative owners. `#draw`
  // passes the selected point and the saved tree it resolved.
  /** @param {TracePoint | null} [point] @param {Evidence} [saved] @param {TreeRow[]} [rows] */
  #template(
    point = null,
    { tree, treePoint } = { image: null, tree: null, treePoint: null },
    rows = [],
  ) {
    const trace = this.#trace;
    const q = quoted(this);
    const items = this.#items();
    const extent = this.#imageSizes.get(this.#scope);
    const choices = trace ? this.#scopeChoices() : [];
    const origin = this.#origin(this.#stream());
    const available = this.#scopeMoments();
    const unavailable = this.#moments.filter((moment) => !moment.scope);
    // A filmstrip frame has no action. The previous action's fields stay in
    // place, hidden, so an inspected metadata scroll position is not clamped.
    const metadataPoint = this.#metadataPoint;
    const metadataAction = metadataPoint?.action;
    const committed = this.#shownImage();
    // What the image is, where nothing else says it (the header's labels at rest).
    const caption = committed
      ? [
          (trace?.pages.length ?? 0) > 1 || (trace?.streams.length ?? 0) > 1
            ? this.#pageLabel(committed.pageId)
            : "",
          committed.kind === "frame" ? "Captured frame" : "",
          this.#picturePreview ? "First capture after this point" : "",
        ]
          .filter(Boolean)
          .join(" · ")
      : this.#pendingPicture
        ? "Loading captured image…"
        : "No captured image at this point.";
    const playLabel = this.#playing ? "Pause" : "Play";
    // What the times count from, said only where it departs from the recording's
    // start (the header's "Words at rest").
    const fromStart =
      origin && origin.recordedStart !== null && origin.recordedStart === origin.start;
    const ownClocks = trace !== null && trace.streams.length > 1;
    const clockLabel = `${
      fromStart
        ? "Times are elapsed since the recording started"
        : "Times are elapsed from the first captured event"
    }${ownClocks ? " · each stream has its own clock" : ""}`;
    const controls = html`<div ${offered("lf-trace-controls")} ?hidden=${!trace}>
      <div ${offered("lf-trace-choices")} ?hidden=${choices.length < 2}>
        <wa-radio-group
          ${offered("lf-trace-sources lf-label-hidden")}
          ${ref(this.#sources)}
          name=${`${this.id}-scope`}
          label="Recording scope"
          size="s"
          orientation="horizontal"
          ?hidden=${choices.length < 2}
          ?disabled=${!trace || q}
          .value=${live(this.#scope ?? "")}
          @change=${() => {
            const selected = choices.find(([id]) => id === this.#nodes.sources.value);
            if (!selected)
              throw new Error(
                "The recording scope chooser needs one of its declared scopes",
              );
            const [value] = selected;
            if (this.#scope === value) return;
            this.#selectScope(value);
            this.#draw();
          }}
        >
          ${repeat(
            choices,
            ([value]) => value,
            ([value, label]) =>
              html`<wa-radio
                ${offered("lf-trace-source")}
                appearance="button"
                value=${value}
                >${label}</wa-radio
              >`,
          )}
        </wa-radio-group>
      </div>
      <section class="lf-trace-bookmarks">
        <div class="lf-trace-options">
          <p class="lf-rows-head" ?hidden=${!this.#moments.length}>Moments</p>
          <a
            ${offered("lf-trace-viewer")}
            target="_blank"
            rel="noopener noreferrer"
            href=${trace?.viewerUrl ?? nothing}
            ?hidden=${!trace}
            >Open in Playwright</a
          >
        </div>
        <div class="lf-trace-bookmark-list lf-rows" ?hidden=${!this.#moments.length}>
          ${repeat(
            this.#moments,
            (moment) => moment.index,
            (moment) => {
              const time = moment.scope
                ? this.#time(moment.time, moment.stream)
                : "Unavailable";
              return html`<button
                ${offeredAction("row", "lf-trace-bookmark")}
                ?hidden=${!(available.some((available) => available === moment) || !moment.scope)}
                ?disabled=${!moment.scope || q}
                aria-label=${`Moment ${moment.number} · ${moment.label} · ${time}`}
                aria-current=${this.#momentSelected(moment) ? "true" : nothing}
                @click=${() => this.#visitMoment(moment.target, moment.index)}
              >
                <span class="lf-row-lead"
                  ><span class="lf-trace-moment-number">${moment.number}</span></span
                ><span class="lf-trace-moment-label lf-row-main">${moment.label}</span
                ><span class="lf-trace-moment-time lf-row-end">${time}</span>
              </button>`;
            },
          )}
          <p
            class="lf-rows-empty"
            ?hidden=${!!available.length || !!unavailable.length}
          >
            No saved moments in this stream.
          </p>
        </div>
      </section>
    </div>`;
    return html`<div class="lf-trace-body" ${ref(this.#body)}>
      <div
        class="lf-trace-evidence"
        @click=${{ handleEvent: (/** @type {Event} */ event) => this.#inspect(event), capture: true }}
      >
        <div class="lf-trace-stage" ?data-ready=${!!trace} ${ref(this.#stage)}>
          <div class="lf-trace-heading" ?hidden=${!trace}>
            <div class="lf-trace-toolbar" ?hidden=${!trace}>
              <div class="lf-trace-transport">
                ${transport(this.#first, "Start", "start", q)}
                <button
                  ${offeredAction(
                    "symbol",
                    "lf-trace-transport-button lf-trace-play",
                    playLabel,
                    { action: "play" },
                  )}
                  ${ref(this.#play)}
                  data-playing=${this.#playing ? "" : nothing}
                  ?disabled=${q}
                  @pointerdown=${(/** @type {PointerEvent} */ event) => {
                    this.#pressedPlay = {
                      pointerId: event.pointerId,
                      pause: this.#playing,
                    };
                  }}
                  @pointercancel=${() => (this.#pressedPlay = null)}
                  @click=${{
                    // Only the matching pointer click carries its press across
                    // a clock change; a canceled mouse press cannot decide a
                    // later keyboard or command action.
                    handleEvent: (/** @type {PointerEvent} */ event) => {
                      const pressed = this.#pressedPlay;
                      this.#playIntent =
                        pressed &&
                        !pressIsKeyboardActivation(event) &&
                        event.pointerId === pressed.pointerId
                          ? pressed.pause
                          : null;
                      this.#pressedPlay = null;
                    },
                    capture: true,
                  }}
                >
                  <!-- Pause stands drawn beside Play, so the clock turning shows
                      it at once (defaults.css, .lf-trace-play[data-playing]). -->
                  ${actionTemplate("pause", "lf-action-icon")}
                </button>
                ${transport(
                  this.#previous,
                  "Previous",
                  "previous",
                  q,
                  "Previous capture",
                )}
                ${transport(this.#next, "Next", "next", q, "Next capture")}
              </div>
              <div class="lf-trace-position-row">
                <span class="lf-trace-position" ${ref(this.#positionLabel)}></span
                ><span class="lf-trace-selection" ${ref(this.#selectionLabel)}></span>
              </div>
              <div
                class="lf-trace-zoom-controls"
                role="group"
                aria-label="Timeline zoom"
              >
                ${transport(this.#zoomOut, "Zoom out", "zoom-out", q)}
                ${transport(this.#zoomIn, "Zoom in", "zoom-in", q)}
                ${transport(this.#zoomFit, "Whole recording", "fit", q)}
              </div>
              <label class="lf-trace-pace"
                >Pace
                <select
                  ${offered("")}
                  name=${`${this.id}-pace`}
                  aria-label="Playback pace"
                  title="Review pace slows near recorded input and marked results, and speeds quiet intervals."
                  ?disabled=${q}
                  .value=${live(this.#pace)}
                  @change=${(/** @type {Event} */ event) => {
                    if (event.currentTarget instanceof HTMLSelectElement)
                      this.#pace = event.currentTarget.value;
                  }}
                >
                  <option value="recorded">Recorded (1×)</option>
                  <option value="review">Review (0.35–3×)</option>
                </select></label
              >
            </div>
          </div>
          <p class="lf-trace-waiting" ?hidden=${!!trace}>
            Waiting for a Playwright recording.
          </p>
          <div
            class="lf-trace-timeline"
            ${ref(this.#timelineHost)}
            tabindex=${q ? -1 : 0}
            role="group"
            aria-label="Recording timeline"
            aria-description="Left and Right step through captures, Shift with Left and Right through inputs and moments, Home and End to the first and last capture. Space plays and pauses."
            ?hidden=${!trace || !items.length}
          ></div>
          <div class="lf-trace-images" ?hidden=${!trace} ${ref(this.#imageHost)}>
            <div
              class="lf-trace-image-viewport"
              ${ref(this.#viewport)}
              style=${styleMap({
                aspectRatio: extent ? `${extent.width} / ${extent.height}` : undefined,
                maxWidth: extent ? `${extent.width}px` : undefined,
              })}
              ?data-sized=${!!extent}
            ></div>
          </div>
          <div class="lf-trace-image-tools" ?hidden=${!extent} ${ref(this.#imageTools)}>
            ${[
              {
                action: "zoom-out",
                label: "Zoom image out",
                run: () => this.#picture?.zoom(-0.25),
              },
              {
                action: "zoom-in",
                label: "Zoom image in",
                run: () => this.#picture?.zoom(0.25),
              },
            ].map(
              ({ action, label, run }) =>
                html`<button
                  ${offeredAction("symbol", "", label, { action })}
                  ?disabled=${!this.#picture?.viewed || q}
                  @click=${run}
                ></button>`,
            )}
            <button
              ${offeredAction("word", "lf-trace-image-scale")}
              ${ref(this.#imageScale)}
              aria-label="Image scale"
              aria-controls=${`${this.id}-image-scale-options`}
              popovertarget=${`${this.id}-image-scale-options`}
              aria-expanded="false"
              ?disabled=${!this.#picture?.viewed || q}
              @click=${(/** @type {Event} */ event) => {
                event.preventDefault();
                const options = this.#nodes.imageScaleOptions;
                if (isNativeLayer(options)) closeNativeLayer(options);
                else {
                  focusDestination(this.#nodes.imageScale, "press");
                  showNativeLayer(options, { source: this.#nodes.imageScale });
                  const selected =
                    options.querySelector('[aria-pressed="true"]') ??
                    options.querySelector("button");
                  if (!selected)
                    throw new Error("The image scale menu needs its controls");
                  focusDestination(selected, "move");
                }
              }}
            >
              <span ${ref(this.#zoomLabel)}></span>${iconTemplate(
                "down",
                "lf-action-icon",
              )}
            </button>
            <div
              id=${`${this.id}-image-scale-options`}
              class="lf-trace-scale-options"
              popover="auto"
              role="group"
              aria-label="Image scale"
              ${ref(this.#imageScaleOptions)}
              @toggle=${() => {
                keeps(
                  this.#nodes.imageScale,
                  "aria-expanded",
                  isNativeLayer(this.#nodes.imageScaleOptions),
                );
                commandsChanged(this);
              }}
            >
              ${[
                {
                  scale: "fit",
                  text: "Fit",
                  label: "Fit image",
                  run: () => this.#fitPicture(),
                },
                {
                  scale: "actual",
                  text: "100%",
                  label: "Actual size",
                  run: () => this.#picture?.zoomTo(1),
                },
              ].map(
                ({ scale, text, label, run }) =>
                  html`<button
                    ${offeredAction("word", "")}
                    data-scale=${scale}
                    aria-label=${label}
                    @click=${() => {
                      run();
                      closeNativeLayer(this.#nodes.imageScaleOptions);
                      focusDestination(this.#nodes.imageScale, "move");
                    }}
                  >
                    ${text}
                  </button>`,
              )}
            </div>
            <span class="lf-trace-tools-status"></span>
          </div>
        </div>
        <div class="lf-trace-capture-footer" ?hidden=${!trace}>
          <p class="lf-trace-caption" title=${caption || nothing} ?hidden=${!extent}>
            ${caption}
          </p>
          <a
            ${offered("lf-trace-full-image")}
            target="_blank"
            rel="noopener noreferrer"
            ?hidden=${!extent}
            ?inert=${!committed}
            aria-hidden=${committed ? nothing : "true"}
            href=${committed ? scopedMediaUrl(committed.url) : nothing}
            >Open full-size image</a
          >
        </div>
        ${controls}
        <div
          class=${classMap({
            "lf-trace-metadata": true,
            "lf-trace-no-action": !point?.action,
          })}
          ?hidden=${!trace}
          ${ref(this.#metadata)}
          tabindex="0"
          role="group"
          aria-label="Selected point details"
        >
          <details
            class="lf-trace-tree"
            ${ref(this.#tree)}
            @toggle=${() => this.#draw()}
          >
            <summary>Saved elements</summary>
            <p class="lf-trace-tree-clock">
              ${
                tree
                  ? `${tree.nodes.length} elements · ${PHASES[treePoint.phase]} checkpoint at ${this.#time(tree.timestamp, treePoint.action.stream)}. Saved element boxes may differ from the image.`
                  : "No accessibility tree was saved at this point."
              }
            </p>
            <ul class="lf-trace-nodes" ${ref(this.#treeList)}>
              ${repeat(
                rows,
                ({ node }) => node.path,
                ({ node }) =>
                  html`<li class="lf-trace-node">
                    <span class="lf-trace-node-name">${nodeName(node)}</span
                    ><code class="lf-trace-node-path">path ${node.path}</code>
                  </li>`,
              )}
            </ul>
          </details>
          <p class="lf-trace-readout">
            ${
              !trace
                ? "Waiting for a Playwright recording."
                : !items.length
                  ? "No recorded checkpoints or frames in this recording scope."
                  : `Step ${this.#position() + 1} of ${items.length}`
            }
          </p>
          <p
            class="lf-trace-action"
            ${ref(this.#actionDetails)}
            .textContent=${metadataAction?.title ?? ""}
          ></p>
          <h3 class="lf-trace-phase" ${ref(this.#phaseHeading)}>
            ${
              metadataAction
                ? `${PHASES[metadataPoint.phase]}${checkpointOf(metadataAction, metadataPoint.phase) ? " checkpoint" : ""}`
                : ""
            }
          </h3>
          <p class="lf-trace-error" ?hidden=${!metadataAction?.error}>
            ${metadataAction?.error ?? ""}
          </p>
          <p class="lf-trace-clock" ?hidden=${!origin || (fromStart && !ownClocks)}>
            ${clockLabel}
          </p>
        </div>
      </div>
    </div>`;
  }

  #draw() {
    if (!this.#items().some((point) => point.id === this.#selected))
      this.#selectDefault();
    const point = this.#point();
    const evidence = this.#evidence(point);
    const { image, tree, treePoint } = evidence;
    const rows = treePoint
      ? tree.nodes.map((node) => ({
          node,
          id: this.#nodeId(treePoint.action, treePoint.phase, node),
        }))
      : [];
    if (point?.action) this.#metadataPoint = point;
    const treeScope = treePoint
      ? this.#phaseId(treePoint.action, treePoint.phase)
      : null;
    if (image) {
      if (!this.#images.has(image.id)) {
        const figure = el("figure", "lf-trace-image");
        const img = document.createElement("img");
        const status = el("span", "lf-trace-image-status", "Loading captured image…");
        figure.classList.add("lf-trace-image-loading");

        const canvas = el("div", "lf-trace-canvas");
        canvas.tabIndex = 0;
        canvas.setAttribute("role", "group");
        canvas.setAttribute(
          "aria-label",
          "Captured image. Arrow keys pan the image; use image controls to zoom or fit.",
        );
        if (!quoted(this)) {
          canvas.lfCommands = {
            title: "In a captured image",
            rows: [
              {
                id: "trace.image.left",
                keys: ["ArrowLeft"],
                title: "pan image left",
                control: canvas,
                run: () => this.#panPicture(-40, 0),
              },
              {
                id: "trace.image.right",
                keys: ["ArrowRight"],
                title: "pan image right",
                control: canvas,
                run: () => this.#panPicture(40, 0),
              },
              {
                id: "trace.image.up",
                keys: ["ArrowUp"],
                title: "pan image up",
                control: canvas,
                run: () => this.#panPicture(0, -40),
              },
              {
                id: "trace.image.down",
                keys: ["ArrowDown"],
                title: "pan image down",
                control: canvas,
                run: () => this.#panPicture(0, 40),
              },
            ],
          };
          commandsChanged(canvas);
        }
        canvas.addEventListener("pointerdown", () => focusDestination(canvas, "press"));
        canvas.append(img, status);
        figure.append(canvas);
        this.#images.set(image.id, { figure, canvas, img, status });
      }
      const { img } = this.#imageSurface(image.id);
      const label = this.#indexedTarget(this.#id("image", image.id)).label;
      keeps(img, "src", scopedMediaUrl(image.url));
      keeps(img, "alt", label);
      keeps(img, "width", String(image.width));
      keeps(img, "height", String(image.height));
    }
    this.#drawPicture(image);
    // Saved trees replace each other under their archive phase identity, and the
    // reader's place in each is kept through empty frames and returns.
    showReadingSubject(
      compoundReadingRegionId(this, "saved-elements"),
      treeScope,
      () => {
        this.#drawing = [point, evidence, rows];
        render(this.#template(...this.#drawing), this.#view, this.renderOptions);
      },
    );
    keepsHidden(this.#missingImage, !!this.#pictureId);
    keepsText(
      this.#missingImage,
      !this.#trace
        ? "The recording has not arrived."
        : this.#pendingPicture
          ? "Loading captured image…"
          : "No captured image is available at or before this timeline point.",
    );
    this.#drawTimeline();
    this.#imageZoom();
    this.#drawTime();
    this.#inventory = [];
    /** @type {{id: string, element: Element, label: string, path: (string | number)[]}[]} */
    const projection = [];
    /** @param {string} id @param {Element} element @param {string} label @param {(string | number)[]} path @param {Element} [surface] */
    const add = (id, element, label, path, surface = element) => {
      this.#inventory.push({ id, element, label, surface });
      projection.push({ id, element, label, path });
    };
    const action = point?.action;
    if (action) {
      const actionIndex = this.#recording.actions.indexOf(action);
      add(this.#id("action", action.id), this.#nodes.actionDetails, action.title, [
        "actions",
        actionIndex,
      ]);
      add(
        this.#phaseId(action, point.phase),
        this.#nodes.phaseHeading,
        `${action.title} · ${PHASES[point.phase]}`,
        checkpointOf(action, point.phase)
          ? ["actions", actionIndex, "phases", point.phase]
          : ["actions", actionIndex],
      );
    }
    // Comments name the image on screen, during playback too.
    if (this.#picture?.viewed) {
      const committed = this.#shownImage() ?? this.#committedPicture.image;
      const displayed = this.#playbackId ? this.#playbackImage : this.#picture.image;
      const label = this.#indexedTarget(this.#id("image", committed.id)).label;
      keeps(displayed, "width", String(committed.width));
      keeps(displayed, "height", String(committed.height));
      add(
        this.#id("image", committed.id),
        this.#playbackId ? this.#imageSurface(this.#pictureId).canvas : displayed,
        label,
        ["images", this.#recording.images.indexOf(committed)],
        displayed,
      );
    }
    if (treePoint && this.#nodes.tree.open) {
      const elements = this.#nodes.treeList.children[Symbol.iterator]();
      for (const [index, { id }] of rows.entries()) {
        const element = elements.next().value;
        if (!element)
          throw new Error("Saved tree rows must match their rendered elements");
        add(id, element, this.#indexedTarget(id).label, [
          "actions",
          this.#recording.actions.indexOf(treePoint.action),
          "phases",
          treePoint.phase,
          "tree",
          "nodes",
          index,
        ]);
      }
    }
    // Only drawn evidence is marked as data (`module-state.md`, "Marking drawn
    // data"). Hidden parts keep their archive coordinate in the inventory reader's
    // label/reveal routes, not in a second semantic fold.
    const marked = new Set();
    for (const { id, element, label, path } of projection) {
      keeps(element, "data-lf-datum", id);
      keeps(element, "data-lf-identity", id);
      keeps(element, "data-lf-datum-label", label);
      keeps(element, "data-lf-origin-path", JSON.stringify(path));
      marked.add(element);
    }
    for (const element of this.#marked)
      if (!marked.has(element)) for (const name of MARKS) element.removeAttribute(name);
    this.#marked = marked;
    this.dispatchEvent(new CustomEvent("drawn", { detail: { value: this.#trace } }));
    this.#parts.update();
    commandsChanged(this);
  }
}
customElements.define("lf-trace", Trace);
