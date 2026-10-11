/* Review one immutable Playwright recording. Playwright owns capture and its clocks;
 * Leaf owns comments. Browsing is local mechanical state, not an event-log fold.
 * Action phases, native images, and saved-tree nodes have archive-scoped coordinates.
 * A phase prefers its checkpoint PNG, otherwise the latest same-page frame at or
 * before that time. Recording-wide operations use the latest capture in their
 * stream, preserving its real page and timestamp in the caption and comments.
 * Each stream has one chronological overview containing all its operations and
 * captures; only recordings with multiple pages expose page filters. Browser and
 * context operations remain in the overview, never become a fabricated page.
 * Pixel comments name the actual image; semantic comments name a
 * saved tree path. Sequential image/tree captures never imply exact pixel alignment.
 * Evidence grows in document flow; a bounded point inspector follows it. Authored bookmarks
 * use the same archive coordinates as comments and derive their capture times.
 * Vis Timeline owns collision stacking, pan and time zoom; Viewer.js owns image
 * inspection. Native buttons keep every moment independently keyboard reachable;
 * blank timeline space only pans, so a released drag never selects a capture.
 * Incremental Vis item updates retain native controls and keyboard focus through resize.
 * One chronological collection gives the timeline, list and selected readout their
 * shared numbers. Pixel projection follows the displayed image under pan and zoom.
 * The ruler starts at the stream origin; Vis measures room for the final controls
 * without inventing captured stops. That overview bounds pan and zoom; playback
 * retains the chosen time window, while explicit point navigation reveals its destination. One cursor
 * scrubs native captures; playback includes frames at their recorded timing and pauses
 * on manual navigation, inspection, hiding or retirement. Page scrolling keeps
 * playback running, including wheel input and vertical touch swipes over captures. Captured frames can join that
 * same timeline. Initial selection opens the first stream in recording order holding
 * a resolvable authored moment, at its earliest one. Otherwise it opens the first
 * stream's first nonempty saved tree, then its first image;
 * empty earlier stops stay navigable. Updates within one archive keep the chosen scope.
 * Following a visual part restores its exact
 * stop and its recording or page scope. Visible choices use the shared Web Awesome radio group;
 * source switching and timeline stepping have separate keyboard focus. Scope choices
 * and the bounded, always-visible Moments list keep evidence at a stable origin. The timeline sits directly above the capture; image
 * inspection controls follow it. One page-sized viewport reserves empty and captured
 * states alike; pixel surfaces never own surrounding geometry. Same-page capture changes retain an inspected
 * image scale and origin, even across empty points and replay; fitted captures continue to fit.
 * Point metadata and saved-element disclosure scroll inside their own region, so
 * playback cannot move surrounding page controls. Registered nested reading regions
 * and phase-keyed reading places retain saved-tree inspection through empty frames.
 * Scope-specific inspection state
 * outlives the image and timeline renderers. Image replacement is atomic: one pending Viewer
 * prepares offscreen while the committed pixels, caption and comment identity stay
 * together; viewed and decoded pixels commit before the retired surface leaves. */
import {
  inBaseLayer,
  commands,
  capturePlace,
  declarationFor,
  dragging,
  cancelRender,
  cancelAnimation,
  nextAnimation,
  nextRender,
  compoundReadingRegionId,
  registerReadingRegion,
  readingRegion,
  restorePlace,
  keepsHidden,
  el,
  focusDestination,
  focused,
  holdFocus,
  html,
  iconTemplate,
  live,
  nothing,
  classMap,
  styleMap,
  offered,
  render,
  repeat,
  keeps,
  keepsText,
  once,
  onUserInput,
  offer,
  paintKeys,
  projectData,
  quoted,
  registerVisualParts,
  scopedMediaUrl,
  setChildren,
  sizeObserver,
  watchData,
  widgetController,
  layoutPx,
} from "/runtime/widget-api.js";

// Reuse the default package’s selected WebAwesome controls, already shipped with Leaf.
await import("/vendor/webawesome.esm.js");
const [{ Timeline, DataSet, css: timelineCss }, { Viewer, css: imageCss }] =
  await Promise.all([
    import("/vendor/timeline.esm.js"),
    import("/vendor/images.esm.js"),
  ]);
// Dependency styles apply only inside recording widgets. Keeping them in their
// module makes the same presentation available in an offline export.
if (!document.querySelector("#lf-trace-library-styles")) {
  const styles = document.createElement("style");
  styles.id = "lf-trace-library-styles";
  styles.textContent = inBaseLayer(`@scope (lf-trace) { ${timelineCss} ${imageCss} }`);
  document.head.append(styles);
}

const PHASES = {
  before: "Before",
  action: "Action",
  after: "After",
  start: "Start",
  end: "Completion",
};
const hex = (text) =>
  [...new globalThis.TextEncoder().encode(text)]
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
// Derived display origins are computed once per source delivery. Navigation and
// label formatting only read this map; the archive keeps its native timestamps.
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
    origin.start = Math.min(origin.start, action.startTime);
  }
  for (const image of trace.images) {
    const origin = origins.get(image.stream);
    origin.start = Math.min(origin.start, image.timestamp);
  }
  return new Map([...origins].filter(([, origin]) => Number.isFinite(origin.start)));
}
const nodeName = (node) =>
  [node.role, node.name || node.text].filter(Boolean).join(" · ") ||
  "Unnamed saved element";

const transport = (cls, label, icon, disabled, onClick, title = label) =>
  html`<button
    ${offered(`lf-trace-transport-button ${cls}`)}
    aria-label=${label}
    title=${title}
    ?disabled=${disabled}
    @click=${onClick}
  >
    ${iconTemplate(icon, "lf-action-icon")}
  </button>`;

export default class extends HTMLElement {
  #snapshot = null;
  #origins = new Map();
  #imageSizes = new Map();
  #trace = null;
  #scope = null;
  #selected = null;
  #intermediates = false;
  #stopReading = null;
  #treeScope = null;
  #treePlaces = new Map();
  #keys = null;
  #parts = null;
  #inventory = [];
  #targets = new Map();
  #images = new Map();
  #view = null;
  // Frame gaps hide the previous action fields without shrinking their extent,
  // so the inspected metadata scroll position cannot be clamped.
  #metadataPoint = null;
  #bookmarks = [];
  #moments = [];
  #chosenBookmark = null;
  #boundsByScope = new Map();
  #rail = null;
  #railData = null;
  #railScope = null;
  #railViewScope = null;
  #railReady = false;
  #railFollow = false;
  #railSignature = null;
  #pins = new Map();
  #pendingPicture = null;
  #scopeViews = new Map();
  #applyingPictureView = false;
  #picture = null;
  #pictureId = null;
  #pictureScope = null;
  #railResize = null;
  #railFrame = 0;
  #railWidth = null;
  #railWaiters = new Set();
  #playFrame = 0;
  #playing = false;
  #playIntent = null;
  #stopInput = null;
  #cursorTime = null;
  #scrubbing = false;
  #reviewGesture = (event) => {
    const path = event.composedPath();
    // Native scroller input belongs to the inspector; widget commands own
    // their own inspection. Page navigation never changes the recording.
    if (
      path.includes(this.metadata) &&
      (event.type === "wheel" ||
        event.type === "pointerdown" ||
        (event.type === "keydown" &&
          ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(
            event.key,
          )))
    )
      this.#pause();
    // Freeze a mouse press before drawing or image dragging claims it. A
    // touch press may start page scrolling; its tap or drawing claim decides.
    else if (event.type === "pointerdown" && event.pointerType !== "touch") {
      if (path.includes(this.imageViewport)) this.#inspectEvidence();
      else if (path.includes(this.timeline)) this.#pause();
    }
  };
  #inspectEvidence() {
    this.#pause();
    // A review gesture freezes the pixels actually on screen, including when
    // another capture is still preparing.
    if (this.#pendingPicture && this.#pictureId)
      this.#reveal(this.#id("image", this.#pictureId));
  }
  #visibility = () => {
    if (document.hidden) this.#pause();
  };

  #resize = () => {
    this.#railFrame ||= nextRender(() => {
      this.#railFrame = 0;
      const width = this.timeline.clientWidth;
      const widthChanged = width !== this.#railWidth;
      this.#railWidth = width;
      // A hidden library region has no geometry to prove. Vis emits no
      // completion at zero width; showing the region starts its real draw.
      if (!width) {
        this.#pause();
        for (const done of this.#railWaiters) done();
        if (this.#pendingPicture) this.#closePicture();
        return;
      }
      const rail = this.#rail;
      const range = widthChanged && rail?.getWindow();
      const overview =
        range &&
        +range.start <= 0 &&
        +range.end >= this.#bounds().end - this.#bounds().start;
      if (widthChanged) this.#draw();
      // Viewer owns container sizing. Reapply the page's inspection view after
      // its resize refits the image, including a hidden tab becoming visible.
      if (this.#picture?.viewed) {
        const canvas = this.#picture.element.parentElement;
        const viewer = this.#picture.viewer;
        const resized =
          viewer.clientWidth !== canvas.offsetWidth ||
          viewer.clientHeight !== canvas.offsetHeight;
        if (resized) {
          this.#picture.resize();
          const image = this.#trace.images.find(
            (image) => image.id === this.#pictureId,
          );
          this.#applyPictureView(this.#picture, image);
          this.#imageZoom();
          this.#parts.update();
        }
      }
      if (!widthChanged || !rail || rail !== this.#rail) return;
      const redraw = this.#waitRail((done) => {
        this.#rail.once("changed", () => {
          this.#limitRail(rail);
          // A fitted overview follows the available width. A narrower window
          // belongs to the reader's zoom or pan and keeps its time coordinates.
          if (overview) rail.fit({ animation: false });
          done();
        });
        this.#rail.redraw();
      });
      widgetController(this).present(redraw);
    });
  };

  connectedCallback() {
    document.addEventListener("visibilitychange", this.#visibility);
    // The shared input owner observes synchronously before drawing claims input.
    this.#stopInput ??= onUserInput(this.#reviewGesture);
    window.addEventListener("resize", this.#resize);
    const firstConnection = once(this);
    if (firstConnection) this.#build();
    this.#railResize ??= sizeObserver(this.#resize);
    this.#railResize.observe(this.timeline);
    if (!quoted(this))
      this.#keys ??= commands(this, "In a Playwright recording", [
        {
          id: "trace.previous",
          keys: () =>
            this.timeline.contains(focused())
              ? ["ArrowLeft", "ArrowDown", "PageDown"]
              : ["ArrowLeft"],
          title: "previous timeline point",
          control: this.previous,
          when: () => this.#position() > 0,
          run: () => this.#step(-1),
        },
        {
          id: "trace.next",
          keys: () =>
            this.timeline.contains(focused())
              ? ["ArrowRight", "ArrowUp", "PageUp"]
              : ["ArrowRight"],
          title: "next timeline point",
          control: this.next,
          when: () => this.#position() < this.#items().length - 1,
          run: () => this.#step(1),
        },
        {
          id: "trace.play",
          title: () => (this.#playing ? "pause recording" : "play recording"),
          control: this.play,
          when: () => this.#items(true).length > 1,
          run: () => {
            const pause = this.#playIntent ?? this.#playing;
            this.#playIntent = null;
            if (pause) this.#pause();
            else this.#startPlayback();
          },
        },
        {
          id: "trace.frames",
          title: () => `${this.#intermediates ? "hide" : "show"} intermediate frames`,
          control: this.framesToggle,
          run: () => this.framesToggle.click(),
          when: () => this.#checkpoints().length > 0 && this.#frames().length > 0,
        },
      ]);
    if (!this.#stopReading) {
      const stops = [
        ["recording", this, this.body],
        ["point-details", this.metadata, this.metadata],
        ["saved-elements", this.treeDetails, this.treeDetails],
      ].map(([name, host, body]) =>
        registerReadingRegion({
          id: compoundReadingRegionId(this, name),
          host,
          body,
        }),
      );
      this.#stopReading = () => stops.toReversed().forEach((stop) => stop());
    }
    if (firstConnection) watchData(this, "trace", (snapshot) => this.#show(snapshot));
    else this.#draw();
  }

  disconnectedCallback() {
    this.#pause(false);
    dragging(this, false);
    document.removeEventListener("visibilitychange", this.#visibility);
    this.#stopInput?.();
    this.#stopInput = null;
    window.removeEventListener("resize", this.#resize);
    this.#stopReading?.();
    this.#stopReading = null;
    this.#railResize?.disconnect();
    if (this.#railFrame) cancelRender(this.#railFrame);
    this.#railFrame = 0;
    this.#railWidth = null;
    this.#closeRail();
    this.#railScope = null;
    this.#railSignature = null;
    this.#closePicture();
    // Element command scopes leave with their element; reconnect keeps the declaration.
  }

  #build() {
    const waiting = document.createElement("template");
    waiting.innerHTML = declarationFor(this, "x-prepaint");
    this.waiting = waiting.content.firstElementChild;
    this.waiting.dataset.lfGen = "1";
    this.querySelector(":scope > [data-lf-prepaint]")?.remove();
    this.#bookmarks = [...this.querySelectorAll(":scope > lf-trace-bookmark")].map(
      (member, index) => ({
        index,
        target: member.getAttribute("target"),
        label: member.getAttribute("label"),
      }),
    );
    // Lit owns only this generated container; authored bookmarks and the
    // prepaint face remain outside its child-part markers.
    this.#view = el("div");
    this.#view.dataset.lfGen = "1";
    this.#view.style.display = "contents";
    this.append(this.waiting, this.#view);
    this.#paint(this.#viewState());
    for (const [name, selector] of Object.entries({
      timeline: ".lf-trace-timeline",
      markers: ".lf-trace-markers",
      body: ".lf-trace-body",
      metadata: ".lf-trace-metadata",
      imageViewport: ".lf-trace-image-viewport",
      imageHost: ".lf-trace-images",
      imageZoomLabel: ".lf-trace-image-zoom",
      treeDetails: ".lf-trace-tree",
      sources: ".lf-trace-sources",
      framesToggle: ".lf-trace-frames",
      play: ".lf-trace-play",
      previous: ".lf-trace-previous",
      next: ".lf-trace-next",
      actionDetails: ".lf-trace-action",
      phaseHeading: ".lf-trace-phase",
      treeList: ".lf-trace-nodes",
    }))
      this[name] = this.#view.querySelector(selector);
    // Viewer owns the viewport children, Vis the marker children. Neither
    // region contains a Lit child expression that could retire their nodes.
    this.missingImage = el("p", "lf-trace-missing-image");
    this.imageViewport.append(this.missingImage);
    this.addEventListener("lf-inspect", (event) => this.#inspect(event));
    this.#parts = registerVisualParts(this, () => this.#inventory, {
      label: (id) => this.#targets.get(id)?.label ?? null,
      reveal: (id) => this.#reveal(id),
    });
    if (!quoted(this))
      commands(this.timeline, "On a recording timeline", [
        {
          id: "trace.first",
          keys: ["Home"],
          title: "first timeline point",
          run: () => this.#navigate(this.#items().at(0)?.id ?? null),
        },
        {
          id: "trace.last",
          keys: ["End"],
          title: "last timeline point",
          run: () => this.#navigate(this.#items().at(-1)?.id ?? null),
        },
      ]);
  }

  #inspect(event) {
    if (event.composedPath().includes(this.metadata)) this.#pause();
    else this.#inspectEvidence();
  }

  #showFrames(checked) {
    this.#pause(false);
    const point = this.#items()[this.#position()];
    this.#intermediates = checked;
    const items = this.#items();
    if (point && !items.some((item) => item.id === point.id))
      this.#navigate(
        items.findLast((item) => item.timestamp <= point.timestamp)?.id ??
          items[0]?.id ??
          null,
      );
    else this.#draw();
  }

  #zoomRail(direction) {
    this.#pause();
    if (!this.#rail) return;
    this.#rail[direction](0.5, { animation: false });
    const point = this.#items().find((point) => point.id === this.#selected);
    if (point)
      this.#rail.moveTo(point.timestamp - this.#bounds().start, { animation: false });
  }

  #rememberTreePlace() {
    if (this.treeDetails.open && this.#treeScope)
      this.#treePlaces.set(
        this.#treeScope,
        capturePlace(readingRegion(compoundReadingRegionId(this, "saved-elements"))),
      );
  }

  #treeToggled() {
    this.#draw();
    if (this.treeDetails.open)
      restorePlace(
        this.#treePlaces.get(this.#treeScope),
        readingRegion(compoundReadingRegionId(this, "saved-elements")),
      );
  }

  #id(kind, value) {
    return `trace-${this.#trace.archive.sha256}-${kind}-${value}`;
  }
  #time(value, stream) {
    return `${((value - this.#origins.get(stream).start) / 1000).toFixed(3)} s`;
  }
  #pageLabel(id) {
    const index = this.#trace.pages.findIndex((page) => page.id === id);
    const page = this.#trace.pages[index];
    const stream = this.#trace.streams.findIndex((stream) => stream.id === page.stream);
    return `Page ${index + 1}${this.#trace.streams.length > 1 ? ` · Stream ${stream + 1}` : ""}`;
  }
  #phaseId(action, phase) {
    return this.#id("phase", `${action.id}-${phase}`);
  }
  #nodeId(action, phase, node) {
    return `${this.#phaseId(action, phase)}-node-${hex(node.path)}`;
  }
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
  #checkpoints() {
    const points = [];
    for (const action of this.#actions())
      for (const phase of this.#phases(action)) {
        const checkpoint = action.phases[phase];
        if (!this.#includes(action.stream, checkpoint?.pageId ?? action.pageId))
          continue;
        points.push({
          id: this.#phaseId(action, phase),
          action,
          phase,
          timestamp:
            checkpoint?.timestamp ??
            (phase === "end" ? action.endTime : action.startTime),
        });
      }
    return points;
  }
  #items(includeFrames = this.#intermediates) {
    const points = this.#checkpoints();
    if (includeFrames || !points.length)
      for (const image of this.#frames())
        points.push({
          id: this.#id("image", image.id),
          image,
          timestamp: image.timestamp,
        });
    // Stable ties retain native phase order, then archive image order. There is
    // one stop per native checkpoint, never synthetic start/end duplicates.
    return points.sort((a, b) => a.timestamp - b.timestamp);
  }
  #evidence(point) {
    const action = point?.action;
    const phase = action?.phases[point.phase];
    const pageId = phase?.pageId ?? action?.pageId;
    let image =
      point?.image ??
      (phase?.imageId
        ? this.#trace.images.find((image) => image.id === phase.imageId)
        : null);
    if (!image && action)
      image =
        this.#trace.images
          .filter(
            (image) =>
              image.stream === action.stream &&
              (!pageId || (image.pageId === pageId && image.kind === "frame")) &&
              image.timestamp <= point.timestamp,
          )
          .sort((a, b) => a.timestamp - b.timestamp)
          .at(-1) ?? null;
    return { image, tree: phase?.tree ?? null };
  }
  #selectDefault() {
    // Authored moments name the review's entry point.
    // A late filmstrip frame keeps its own stop, never an earlier call's time.
    const items = this.#items(true);
    const moment = this.#scopeMoments()[0];
    const destination = moment ? this.#destination(moment.target) : null;
    const firstTree = items.find((point) => this.#evidence(point).tree?.nodes.length);
    const point =
      items.find((point) => point.id === destination) ??
      firstTree ??
      items.find((point) => this.#evidence(point).image) ??
      items[0];
    this.#chosenBookmark = moment?.index ?? null;
    if (point?.image) this.#intermediates = true;
    this.#selected = point?.id ?? null;
  }
  #position() {
    return Math.max(
      0,
      this.#items().findIndex((point) => point.id === this.#selected),
    );
  }
  #navigate(id) {
    this.#pause(false);
    this.#chosenBookmark = null;
    this.#selected = id;
    this.#draw();
    this.#drawCursor(true);
  }
  #step(delta) {
    const items = this.#items();
    const next = Math.max(0, Math.min(items.length - 1, this.#position() + delta));
    this.#navigate(items[next]?.id ?? null);
  }
  #pause(draw = true) {
    if (!this.#playing && this.#cursorTime === null && !this.#scrubbing) return;
    // A playing film is continuous mechanical motion, outside resting proof.
    if (this.#playFrame) cancelAnimation(this.#playFrame);
    this.#playFrame = 0;
    this.#playing = false;
    this.#rail?.setOptions({ moveable: true });
    this.#cursorTime = null;
    if (this.#scrubbing) {
      this.#scrubbing = false;
      dragging(this, false);
    }
    if (draw) {
      this.#paint(this.#viewState());
      if (this.#rail) this.#drawMoments();
    }
  }
  #startPlayback() {
    const points = this.#items(true);
    if (points.length < 2) return;
    // Playback includes filmstrip captures; manual filter changes pause it.
    this.#intermediates = true;
    const selected = points.find((point) => point.id === this.#selected);
    const from = selected === points.at(-1) ? points[0] : (selected ?? points[0]);
    const started = performance.now();
    const origin = this.#bounds().start;
    const end = points.at(-1).timestamp;
    this.#playing = true;
    this.#rail?.setOptions({ moveable: false });
    this.#chosenBookmark = null;
    this.#selected = from.id;
    this.#cursorTime = from.timestamp - origin;
    this.#draw();
    const tick = () => {
      this.#playFrame = 0;
      if (!this.#playing) return;
      const time = Math.min(end, from.timestamp + performance.now() - started);
      const point = points.findLast((point) => point.timestamp <= time) ?? from;
      this.#cursorTime = time - origin;
      if (point.id !== this.#selected) {
        this.#selected = point.id;
        this.#draw();
      } else this.#drawCursor();
      if (time === end) this.#pause();
      else {
        this.#playFrame = nextAnimation(tick);
      }
    };
    this.#playFrame = nextAnimation(tick);
  }
  #phases(action) {
    return Object.keys(action.phases).length
      ? Object.keys(PHASES).filter((phase) => action.phases[phase])
      : action.endTime === null
        ? ["start"]
        : ["start", "end"];
  }

  #show(snapshot) {
    this.#pause(false);
    const restore = holdFocus(this);
    const oldArchive = this.#trace?.archive.sha256;
    this.#snapshot = snapshot;
    this.#trace = snapshot?.value ?? null;
    this.#boundsByScope.clear();
    this.#origins = this.#trace ? streamOrigins(this.#trace) : new Map();
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
      this.#closeRail();
      this.#railScope = null;
      this.#closePicture();
      this.#images.clear();
      this.#scopeViews.clear();
      this.#metadataPoint = null;
      this.#treePlaces.clear();
      this.#treeScope = null;
      this.#scope = null;
      this.#selected = null;
      this.#chosenBookmark = null;
      this.#intermediates = false;
      setChildren(this.imageViewport, [this.missingImage]);
    }
    if (this.#trace) {
      const choices = this.#scopeChoices();
      const chooseScope = !choices.some(([id]) => id === this.#scope);
      this.#indexTargets();
      const scopeOrder = new Map(
        this.#trace.streams.map((stream, index) => [stream.id, index]),
      );
      this.#moments = this.#bookmarks
        .map((member) => this.#moment(member))
        .toSorted(
          (a, b) =>
            (scopeOrder.get(a.stream) ?? Infinity) -
              (scopeOrder.get(b.stream) ?? Infinity) || a.time - b.time,
        )
        .map((moment, index) => ({ ...moment, number: index + 1 }));
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
    restore?.(this.sources);
  }

  #scopeChoices() {
    return this.#trace.streams.flatMap((stream, index) => {
      const pages = this.#trace.pages.filter((page) => page.stream === stream.id);
      return [
        [
          stream.id,
          this.#trace.streams.length > 1
            ? `Stream ${index + 1}`
            : pages.length > 1
              ? "All pages"
              : "Recording",
        ],
        ...(pages.length > 1
          ? pages.map((page) => [page.id, this.#pageLabel(page.id)])
          : []),
      ];
    });
  }

  #scopeView(scope = this.#scope) {
    let view = this.#scopeViews.get(scope);
    if (!view) {
      view = {};
      this.#scopeViews.set(scope, view);
    }
    return view;
  }

  #selectScope(scope) {
    if (scope === this.#scope) return;
    this.#pause(false);
    Object.assign(this.#scopeView(), {
      selected: this.#selected,
      intermediates: this.#intermediates,
    });
    this.#cancelPicture();
    this.#scope = scope;
    const saved = this.#scopeView();
    this.#selected = saved.selected ?? null;
    this.#intermediates = saved.intermediates ?? false;
  }

  #targetScope(stream, pageId) {
    return pageId &&
      this.#trace.pages.filter((page) => page.stream === stream).length > 1
      ? pageId
      : stream;
  }

  #indexTargets() {
    this.#targets.clear();
    for (const action of this.#trace.actions) {
      const firstPhase = this.#phases(action)[0];
      const pageId = action.pageId;
      const firstPageId = action.phases[firstPhase]?.pageId ?? pageId;
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
          pageId: action.phases[phase]?.pageId ?? pageId,
          scope: this.#targetScope(
            action.stream,
            action.phases[phase]?.pageId ?? pageId,
          ),
          phase,
          label: `${action.title} · ${PHASES[phase]}`,
        });
        for (const node of action.phases[phase]?.tree?.nodes ?? [])
          this.#targets.set(this.#nodeId(action, phase, node), {
            action,
            pageId: action.phases[phase]?.pageId ?? pageId,
            scope: this.#targetScope(
              action.stream,
              action.phases[phase]?.pageId ?? pageId,
            ),
            phase,
            node,
            label: `${action.title} · ${PHASES[phase]} · ${nodeName(node)} · path ${node.path}`,
          });
      }
    }
    for (const image of this.#trace.images)
      this.#targets.set(this.#id("image", image.id), {
        image,
        pageId: image.pageId,
        scope: this.#targetScope(image.stream, image.pageId),
        label: `${this.#pageLabel(image.pageId)} · ${image.kind === "frame" ? "Captured frame" : `${PHASES[image.phase]} checkpoint`} · ${this.#time(image.timestamp, image.stream)}`,
      });
  }

  #destination(id) {
    const target = this.#targets.get(id);
    if (!target) return null;
    if (target.image?.kind === "frame") return id;
    const action =
      target.action ??
      this.#trace.actions.find(
        (action) =>
          action.stream === target.image.stream &&
          action.callId === target.image.callId &&
          action.phases[target.image.phase]?.imageId === target.image.id,
      );
    return action ? this.#phaseId(action, target.phase ?? target.image.phase) : null;
  }
  #reveal(id, bookmark = null) {
    this.#pause(false);
    const selected = this.#destination(id);
    if (!selected) return;
    const target = this.#targets.get(id);
    this.#chosenBookmark = bookmark;
    // Following a point already present in the overview keeps that overview.
    // A page filter changes only when it cannot display the exact destination.
    if (!this.#includes(target.image?.stream ?? target.action.stream, target.pageId))
      this.#selectScope(target.scope);
    this.#selected = selected;
    if (target.image?.kind === "frame") this.#intermediates = true;
    if (target.node) keeps(this.treeDetails, "open", "");
    this.#draw();
    this.#drawCursor(true);
  }

  #stream() {
    return (
      this.#trace?.pages.find((page) => page.id === this.#scope)?.stream ??
      this.#trace?.streams.find((stream) => stream.id === this.#scope)?.id
    );
  }
  #bounds() {
    if (this.#boundsByScope.has(this.#scope))
      return this.#boundsByScope.get(this.#scope);
    const start = this.#origins.get(this.#stream())?.start ?? 0;
    let end = start;
    for (const point of this.#checkpoints()) {
      end = Math.max(end, point.timestamp);
    }
    for (const image of this.#trace?.images ?? []) {
      if (!this.#includes(image.stream, image.pageId)) continue;
      end = Math.max(end, image.timestamp);
    }
    const bounds = {
      start,
      end,
    };
    this.#boundsByScope.set(this.#scope, bounds);
    return bounds;
  }
  #moment(member) {
    const target = this.#destination(member.target)
      ? this.#targets.get(member.target)
      : null;
    const capture = target?.image ?? target?.action?.phases[target.phase];
    return {
      ...member,
      scope: target?.scope,
      stream: target?.image?.stream ?? target?.action?.stream,
      time:
        capture?.timestamp ??
        (target?.phase === "end" ? target?.action?.endTime : target?.action?.startTime),
    };
  }
  #scopeMoments() {
    return this.#moments.filter(
      (moment) => moment.scope === this.#scope || moment.stream === this.#scope,
    );
  }
  #imageZoom() {
    keepsText(
      this.imageZoomLabel,
      this.#picture?.viewed
        ? `${Math.round(this.#picture.imageData.ratio * 100)}% · drag to inspect`
        : this.#pendingPicture
          ? "Loading capture…"
          : this.#pictureId
            ? "Image unavailable"
            : "No captured image",
    );
  }

  #panPicture(x, y) {
    this.#inspectEvidence();
    this.#picture?.move(x, y);
  }

  #fitPicture() {
    if (!this.#picture?.viewed) return;
    const image = this.#trace.images.find((image) => image.id === this.#pictureId);
    this.#scopeView().image = null;
    this.#applyPictureView(this.#picture, image);
    this.#imageZoom();
    this.#parts.update();
  }

  #rememberPictureView(viewer) {
    if (viewer !== this.#picture || this.#applyingPictureView) return;
    const width = viewer.element.parentElement.clientWidth;
    const { width: pixels, x, y } = viewer.imageData;
    this.#scopeView(this.#pictureScope).image = {
      width: pixels / width,
      x: x / width,
      y: y / width,
    };
  }

  #applyPictureView(viewer, image) {
    const canvas = viewer.element.parentElement;
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

  #closePicture() {
    this.#cancelPicture();
    keeps(this.imageHost, "aria-busy", null);
    this.#picture?.destroy();
    this.#picture = null;
    this.#pictureId = null;
    this.#pictureScope = null;
  }

  #drawPicture(image) {
    if (!image) {
      this.#closePicture();
      setChildren(this.imageViewport, [this.missingImage]);
      return;
    }
    if (this.#pendingPicture?.image.id !== image.id) this.#cancelPicture();
    if (this.#pictureId === image.id) {
      if (this.#pictureScope !== this.#scope && this.#picture?.viewed) {
        this.#applyPictureView(this.#picture, image);
        this.#pictureScope = this.#scope;
      }
      keeps(this.imageHost, "aria-busy", null);
      this.#imageZoom();
      return;
    }
    if (this.#pendingPicture) return;
    const figure = this.#images.get(image.id);
    const source = figure.querySelector(".lf-trace-canvas > img");
    const canvas = source.parentElement;
    if (!figure.classList.contains("lf-trace-image-pending"))
      figure.classList.add("lf-trace-image-pending");
    if (!figure.classList.contains("lf-trace-image-loading"))
      figure.classList.add("lf-trace-image-loading");
    keeps(figure, "inert", "");
    keeps(figure, "aria-hidden", "true");
    keepsText(
      figure.querySelector(".lf-trace-image-status"),
      "Loading captured image…",
    );
    setChildren(this.imageViewport, [
      this.missingImage,
      ...(this.#pictureId ? [this.#images.get(this.#pictureId)] : []),
      figure,
    ]);
    if (!canvas.clientWidth) {
      keeps(this.imageHost, "aria-busy", null);
      return;
    }
    const pending = { image, figure, viewer: null, scope: this.#scope };
    this.#pendingPicture = pending;
    keeps(this.imageHost, "aria-busy", "true");
    const current = () => this.#pendingPicture === pending;
    const ready = new Promise((resolve) => {
      pending.resolve = resolve;
      const commit = (viewer) => {
        if (!current()) return;
        const retired = this.#picture;
        const hadFocus = this.imageViewport.contains(document.activeElement);
        this.#picture = viewer;
        // Leaf owns container resize so unchanged window signals leave the
        // inspected image alone. Viewer otherwise refits it on every signal.
        if (viewer) window.removeEventListener("resize", viewer.onResize);
        this.#pictureId = image.id;
        this.#pictureScope = pending.scope;
        this.#pendingPicture = null;
        keeps(this.imageHost, "aria-busy", null);
        figure.classList.remove("lf-trace-image-pending");
        figure.inert = false;
        keeps(figure, "aria-hidden", null);
        keeps(source, "hidden", "");
        setChildren(this.imageViewport, [this.missingImage, figure]);
        if (hadFocus) focusDestination(canvas, "return");
        retired?.destroy();
        this.#imageZoom();
        this.#draw();
        resolve();
      };
      const failed = () => {
        if (!current()) return;
        pending.viewer?.destroy();
        keepsText(
          figure.querySelector(".lf-trace-image-status"),
          "Captured image could not load.",
        );
        commit(null);
      };
      // Viewer clears its canvas before decoding a replacement. Prepare its
      // complete surface separately; only public viewed + decoded pixels can
      // replace the committed capture and its exact comment identity.
      source.decode().then(() => {
        if (!current()) return;
        pending.viewer = new Viewer(source, {
          inline: true,
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
            if (event.detail.originalEvent?.pointerType === "touch" && this.#playing) {
              event.preventDefault();
              return;
            }
            if (event.detail.originalEvent) this.#inspectEvidence();
          },
          zoom: (event) => {
            if (event.detail.originalEvent) this.#inspectEvidence();
          },
          view: (event) =>
            event.detail.image.addEventListener("error", failed, { once: true }),
          viewed: (event) => {
            event.detail.image.decode().then(() => {
              if (!current()) return;
              this.#applyPictureView(pending.viewer, image);
              figure.classList.remove("lf-trace-image-loading");
              commit(pending.viewer);
            }, failed);
          },
          moved: () => {
            this.#rememberPictureView(pending.viewer);
            this.#parts.update();
          },
          zoomed: () => {
            this.#rememberPictureView(pending.viewer);
            this.#imageZoom();
            this.#parts.update();
          },
        });
      }, failed);
    });
    widgetController(this).present(ready);
  }

  #resetRail() {
    if (!this.#rail) return;
    this.#limitRail(this.#rail);
    this.#rail.fit({ animation: false });
  }

  #limitRail(rail) {
    // Vis's initial-draw callback can arrive after its instance is retired.
    if (rail !== this.#rail) return;
    // Vis measures room for the final button. The stream's zero is the hard
    // left boundary, including when fitting, panning, zooming or resizing.
    const { max } = rail.getItemRange();
    const { start, end } = rail.getWindow();
    rail.setOptions({ min: 0, max, zoomMax: +max });
    rail.setWindow(start, end, { animation: false });
  }

  #waitRail(start) {
    return new Promise((resolve) => {
      const done = () => {
        this.#railWaiters.delete(done);
        resolve();
      };
      this.#railWaiters.add(done);
      start(done);
    });
  }

  #closeRail() {
    this.#pause(false);
    // Destroy cancels library redraws; superseded preparation must settle too.
    for (const done of this.#railWaiters) done();
    if (this.#rail) {
      this.#scopeView(this.#railViewScope).window = this.#rail.getWindow();
      this.#rail.destroy();
    }
    this.#rail = null;
    this.#railData = null;
    this.#railReady = false;
    this.#railFollow = false;
  }

  #railItems(available) {
    const bounds = this.#bounds();
    const duration = Math.max(1, bounds.end - bounds.start);
    const extent = this.#rail ? +this.#rail.getItemRange().max : duration;
    const halfControl = this.#controlSize() / 2;
    // The passive interval supplies the actual recording extent, not another
    // stop. Vis fits both that extent and the measured moment-button widths.
    return [
      {
        id: "recording-extent",
        start: 0,
        end: duration,
        type: "background",
        content: "",
      },
      ...available.map((moment) => ({
        id: moment.number,
        start: moment.time - bounds.start,
        content: String(moment.number),
        type: "box",
        // Near zero, Vis anchors the box after its native time instead of
        // centering half its control outside the recording. Interior boxes
        // retain their centered alignment; resizing recomputes this choice.
        align:
          (moment.time - bounds.start) * this.timeline.clientWidth <
          halfControl * extent
            ? "left"
            : "center",
      })),
    ];
  }

  #buildRail(available) {
    this.#railViewScope = this.#scope;
    const window = this.#scopeView().window;
    this.#railData = new DataSet(this.#railItems(available));
    let rail;
    const ready = this.#waitRail((resolve) => {
      this.#rail = rail = new Timeline(this.markers, this.#railData, {
        rtl: getComputedStyle(this).direction === "rtl",
        autoResize: false,
        height: "100%",
        verticalScroll: true,
        showCurrentTime: false,
        onInitialDrawComplete: () => {
          if (rail !== this.#rail) return resolve();
          this.#limitRail(rail);
          // Let Vis complete its initial fit before restoring a mechanical view.
          // Constructor start/end uses a separate deferred range-change latch.
          if (window) rail.setWindow(window.start, window.end, { animation: false });
          this.#railReady = true;
          this.#drawMoments();
          this.#drawCursor(this.#railFollow);
          this.#railFollow = false;
          resolve();
        },
        showMajorLabels: false,
        stack: true,
        cluster: false,
        selectable: false,
        orientation: "top",
        zoomKey: "ctrlKey",
        min: 0,
        zoomMin: 1,
        snap: null,
        // The cursor owns a full control row below the ruler; stacked moments
        // begin after it, so scrubbing never covers a tick or another target.
        margin: {
          item: Number.parseFloat(getComputedStyle(this).getPropertyValue("--sp-2")),
          axis: this.#controlSize(),
        },
        format: {
          minorLabels: (date) =>
            `${(+date / 1000).toFixed(+date % 10 ? 3 : +date % 1000 ? 2 : 0)} s`,
        },
        template: (item) =>
          item.type === "background" ? "" : this.#pins.get(item.id).parentElement,
      });
    });
    widgetController(this).present(ready);
    this.#rail.addCustomTime(0, "selection");
    // Vis seats moving time cursors on a stationary background plane, separate
    // from moment buttons. Only that plane permits its live control to travel.
    const cursorPlane = this.markers.querySelector(
      ".vis-panel.vis-background.vis-vertical",
    );
    cursorPlane.setAttribute("data-lf-runtime", "");
    cursorPlane.setAttribute("data-lf-reflow", "controls");
    this.#rail.setCustomTimeTitle(
      quoted(this) ? "Selected recorded point" : "Drag to scrub recording",
      "selection",
    );
    const scrub = ({ id, time }, finished) => {
      if (rail !== this.#rail || id !== "selection" || quoted(this)) return;
      if (this.#playing) this.#pause(false);
      this.#scrubbing = !finished;
      dragging(this, !finished);
      const origin = this.#bounds().start;
      const elapsed = Math.max(0, Math.min(this.#bounds().end - origin, +time));
      const items = this.#items();
      // Vis stores integer milliseconds, while native captures can share that
      // bucket. Keep an exact selected identity there; stepping reaches every tie.
      const bucket = (point) => Math.trunc(point.timestamp - origin);
      const nearest = items.reduce(
        (best, point) =>
          Math.abs(bucket(point) - elapsed) < Math.abs(bucket(best) - elapsed)
            ? point
            : best,
        items[0],
      );
      const selected = items.find((point) => point.id === this.#selected);
      this.#selected =
        selected && bucket(selected) === bucket(nearest) ? selected.id : nearest.id;
      this.#chosenBookmark = null;
      this.#cursorTime = finished ? null : elapsed;
      this.#draw();
    };
    rail.on("rangechange", (event) => {
      if (event.byUser) this.#pause();
    });
    rail.on("click", () => this.#pause());
    rail.on("timechange", (event) => scrub(event, false));
    rail.on("timechanged", (event) => scrub(event, true));
    rail.on("changed", () => this.#placeCursorHandle());
  }

  #drawMoments() {
    const moments = this.#moments;
    const available = this.#scopeMoments();
    this.style.setProperty("--lf-trace-moment-rows", Math.min(3, moments.length));
    if (!this.#trace) return;
    const scope = `${this.#trace.archive.sha256}:${this.#scope}`;
    if (scope !== this.#railScope) {
      this.#closeRail();
      this.#railScope = scope;
      this.#railSignature = null;
      this.#pins.clear();
    }
    for (const moment of available) {
      let pin = this.#pins.get(moment.number);
      if (!pin) {
        pin = offer("button", "lf-trace-marker");
        // Vis claims pointer defaults for its gestures. The embedded native
        // control still owns focus, including tooltip blur/re-arm behavior.
        pin.addEventListener("pointerdown", () => focusDestination(pin, "press"));
        pin.addEventListener("focus", () => {
          if (pin.matches(":focus-visible"))
            this.#rail?.focus(moment.number, { zoom: false, animation: false });
        });
        pin.append(el("span"));
        const anchor = el("span", "lf-trace-moment-anchor");
        anchor.append(pin);
        this.#pins.set(moment.number, pin);
      }
      keepsText(pin.firstElementChild, String(moment.number));
      const anchor = pin.parentElement;
      keeps(anchor, "id", `${this.id}-moment-${moment.number}`);
      keeps(pin, "id", `${this.id}-moment-${moment.number}-control`);
      keeps(
        pin,
        "aria-label",
        `Moment ${moment.number} · ${moment.label} · ${this.#time(moment.time, moment.stream)}`,
      );
      keeps(pin, "disabled", quoted(this) ? "" : null);
      keeps(pin, "aria-current", this.#momentSelected(moment) ? "true" : null);
      pin.onclick = () => this.#reveal(moment.target, moment.index);
      let tip = this.timeline.querySelector(`wa-tooltip[for="${anchor.id}"]`);
      if (!tip) {
        tip = offer("wa-tooltip", "lf-trace-tooltip");
        tip.setAttribute("for", anchor.id);
        this.timeline.append(tip);
      }
      keepsText(
        tip,
        `${moment.number} · ${moment.label} · ${this.#time(moment.time, moment.stream)}`,
      );
    }
    if (!this.timeline.clientWidth) return;
    const created = !this.#rail;
    if (created) this.#buildRail(available);
    const signature = `${this.timeline.clientWidth}|${available
      .map((moment) => `${moment.number}:${moment.time}`)
      .join("|")}`;
    if (!created && signature !== this.#railSignature) {
      const items = this.#railItems(available);
      const ids = new Set(items.map((item) => item.id));
      this.#railData.remove(this.#railData.getIds().filter((id) => !ids.has(id)));
      // Replacing the dataset detaches every native button and drops focus.
      // Updating existing items lets Vis restack and align their intact nodes.
      this.#railData.update(items);
      this.#limitRail(this.#rail);
    }
    // Initial fit measures the library's final extent. Its completion pass
    // refines edge alignment once, then playback reads this unchanged input.
    this.#railSignature = created ? null : signature;
    this.#drawCursor();
  }
  #drawCursor(follow = false) {
    if (!this.#rail) return;
    if (follow && !this.#railReady) this.#railFollow = true;
    const origin = this.#bounds().start;
    const time =
      this.#cursorTime ??
      (this.#items().find((point) => point.id === this.#selected)?.timestamp ??
        origin) - origin;
    if (+this.#rail.getCustomTime("selection") !== Math.trunc(time))
      this.#rail.setCustomTime(time, "selection");
    const window = this.#rail.getWindow();
    // Rendering and playback update the cursor, never the user's time window.
    // Explicit point navigation reveals an off-window destination at this zoom.
    if (
      follow &&
      this.#railReady &&
      !this.#scrubbing &&
      (time < +window.start || time > +window.end)
    )
      this.#rail.moveTo(time, { animation: false });
    this.#placeCursorHandle();
  }

  #controlSize() {
    return Number.parseFloat(
      getComputedStyle(this).getPropertyValue("--lf-trace-control-size"),
    );
  }

  #placeCursorHandle() {
    const cursor = this.markers.querySelector(".vis-custom-time");
    const center = this.markers.querySelector(".vis-panel.vis-center");
    if (!cursor || !center) return;
    // Read Vis's actual cursor position, keeping its time coordinate intact.
    // Only the handle moves inward at an edge; its full hit region stays usable.
    const line = cursor.getBoundingClientRect();
    const rail = center.getBoundingClientRect();
    const halfControl = this.#controlSize() / 2;
    cursor.style.setProperty("--lf-trace-cursor-axis", layoutPx(rail.top - line.top));
    const middle = line.left + line.width / 2;
    const left = middle - rail.left;
    const right = rail.right - middle;
    const shift = (half) =>
      left < 0 || right < 0 ? 0 : Math.max(0, half - left) - Math.max(0, half - right);
    cursor.style.setProperty(
      "--lf-trace-cursor-hit-shift",
      layoutPx(shift(halfControl)),
    );
    const halfCap = Number.parseFloat(getComputedStyle(cursor, "::before").width) / 2;
    cursor.style.setProperty("--lf-trace-cursor-cap-shift", layoutPx(shift(halfCap)));
  }

  #viewState() {
    const items = this.#items();
    const position = Math.max(
      0,
      items.findIndex((point) => point.id === this.#selected),
    );
    const point = items[position];
    const { image, tree } = this.#evidence(point);
    const extent = this.#imageSizes.get(this.#scope);
    const trace = this.#trace;
    const q = quoted(this);
    const stream = this.#stream();
    const origin = this.#origins.get(stream);
    const action = point?.action ?? null;
    const choices = trace ? this.#scopeChoices() : [];
    const selection = (() => {
      const selected = this.#moments.filter(
        (moment) =>
          this.#selected && this.#destination(moment.target) === this.#selected,
      );
      const moment =
        selected.find((moment) => moment.index === this.#chosenBookmark) ?? selected[0];
      return moment
        ? `Moment ${moment.number} · ${moment.label}`
        : action
          ? `${PHASES[point.phase]} · ${action.title}`
          : point
            ? "Captured frame"
            : "";
    })();
    const available = this.#scopeMoments();
    const unavailable = this.#moments.filter((moment) => !moment.scope);
    return {
      items,
      position,
      point,
      image,
      tree,
      extent,
      bounds: this.#bounds(),
      choices,
      selection,
      stream,
      origin,
      available,
      unavailable,
      frameCount: this.#frames().length,
      checkpointCount: this.#checkpoints().length,
      playDisabled: q || this.#items(true).length < 2,
      rows: action
        ? (tree?.nodes ?? []).map((node) => ({
            node,
            id: this.#nodeId(action, point.phase, node),
          }))
        : [],
    };
  }

  // Lit owns the native controls and metadata. Library surfaces keep their
  // imperative owners, including zoom updates on each pinch step.
  #paint({
    items,
    position,
    point,
    tree,
    extent,
    bounds,
    choices,
    selection,
    stream,
    origin,
    available,
    unavailable,
    frameCount,
    checkpointCount,
    playDisabled,
    rows,
  }) {
    const trace = this.#trace;
    const q = quoted(this);
    const action = point?.action ?? null;
    const metadataPoint = this.#metadataPoint;
    const metadataAction = metadataPoint?.action;
    const committed = trace?.images.find((item) => item.id === this.#pictureId);
    const caption = committed
      ? this.#targets.get(this.#id("image", committed.id)).label
      : this.#pendingPicture
        ? "Loading captured image…"
        : "No captured image at this point.";
    const playLabel = this.#playing ? "Pause" : "Play";
    const moments = this.#moments;
    const noPoints = !trace || !items.length;
    const clockLabel =
      origin && origin.recordedStart !== null && origin.recordedStart === origin.start
        ? "Elapsed since recording started"
        : "Elapsed from first captured event";
    render(
      html`<div ${offered("lf-trace-controls")} ?hidden=${!trace}>
          <div ${offered("lf-trace-choices")} ?hidden=${choices.length < 2}>
            <wa-radio-group
              ${offered("lf-trace-sources lf-label-hidden")}
              name=${`${this.id}-scope`}
              label="Recording scope"
              size="s"
              orientation="horizontal"
              ?hidden=${choices.length < 2}
              ?disabled=${!trace || q}
              .value=${live(this.#scope ?? "")}
              @change=${(event) => {
                const value = event.currentTarget.value;
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
              <p class="lf-trace-moments-heading" ?hidden=${!moments.length}>
                Moments (${available.length + unavailable.length})
              </p>
              <a
                ${offered("lf-trace-viewer")}
                target="_blank"
                rel="noopener noreferrer"
                href=${trace?.viewerUrl ?? nothing}
                ?hidden=${!trace}
                >Open in Playwright</a
              >
            </div>
            <div class="lf-trace-bookmark-list" ?hidden=${!moments.length}>
              ${repeat(
                moments,
                (moment) => moment.index,
                (moment) => {
                  const time = moment.scope
                    ? this.#time(moment.time, moment.stream)
                    : "Unavailable";
                  return html`<button
                    ${offered("lf-trace-bookmark")}
                    ?hidden=${!(available.includes(moment) || !moment.scope)}
                    ?disabled=${!moment.scope || q}
                    aria-label=${`Moment ${moment.number} · ${moment.label} · ${time}`}
                    aria-current=${this.#momentSelected(moment) ? "true" : nothing}
                    @click=${() => this.#reveal(moment.target, moment.index)}
                  >
                    <span class="lf-trace-moment-number">${moment.number}</span
                    ><span class="lf-trace-moment-label">${moment.label}</span
                    ><span class="lf-trace-moment-time">${time}</span>
                  </button>`;
                },
              )}
              <p
                class="lf-trace-no-moments"
                ?hidden=${!!available.length || !!unavailable.length}
              >
                No saved moments in this stream.
              </p>
            </div>
          </section>
          <div class="lf-trace-help">
            <label class="lf-trace-frames-label"
              ><input
                type="checkbox"
                ${offered("lf-trace-frames")}
                name=${`${this.id}-frames`}
                .checked=${live(
                  frameCount > 0 && (this.#intermediates || !checkpointCount),
                )}
                ?disabled=${!frameCount || !checkpointCount || q}
                @change=${(event) => this.#showFrames(event.currentTarget.checked)}
              />Show intermediate frames</label
            >
            <p class="lf-trace-moment-hint" ?hidden=${noPoints}>
              Drag the blue handle to scrub. Drag empty space to pan; zoom to separate
              nearby moments.
            </p>
          </div>
        </div>
        <div class="lf-trace-body" ?hidden=${!trace}>
          <div class="lf-trace-toolbar">
            <div class="lf-trace-transport">
              <button
                ${offered("lf-trace-transport-button lf-trace-play")}
                aria-label=${playLabel}
                title=${playLabel}
                data-playing=${this.#playing ? "" : nothing}
                ?disabled=${playDisabled}
                @pointerdown=${() => (this.#playIntent = this.#playing)}
                @pointercancel=${() => (this.#playIntent = null)}
              >
                ${iconTemplate("play", "lf-action-icon")}${iconTemplate("pause", "lf-action-icon")}<span
                  >${playLabel}</span
                >
              </button>
              ${transport("lf-trace-previous", "Previous", "previous", q, undefined, "Previous recorded point")}
              ${transport("lf-trace-next", "Next", "next", q, undefined, "Next recorded point")}
            </div>
            <div class="lf-trace-position-row">
              <span class="lf-trace-position"
                >${point ? this.#time(point.timestamp, stream) : "No recorded points"}</span
              ><span class="lf-trace-selection" title=${selection}>${selection}</span>
            </div>
            <div class="lf-trace-zoom-controls" role="group" aria-label="Timeline zoom">
              ${transport("", "Zoom out", "subtract", q, () => this.#zoomRail("zoomOut"))}
              ${transport(
                "",
                "Zoom in",
                "add",
                q || bounds.end - bounds.start < 1,
                () => this.#zoomRail("zoomIn"),
              )}
              ${transport("", "Whole recording", "fit", q, () => {
                this.#pause();
                this.#resetRail();
              })}
            </div>
          </div>
          <div ${offered("lf-trace-stepper")}>
            <div
              class="lf-trace-timeline"
              tabindex=${q ? -1 : 0}
              role="group"
              aria-label="Recording timeline"
              aria-description="Left and Right step through recorded points. Home and End reach the first and last point."
            >
              <div
                class=${classMap({ "lf-trace-markers": true, "lf-trace-readonly": q })}
                role="group"
                aria-label="Timeline moments"
                ?hidden=${noPoints}
              ></div>
            </div>
          </div>
          <div
            class="lf-trace-evidence"
            @click=${{ handleEvent: (event) => this.#inspect(event), capture: true }}
          >
            <div class="lf-trace-images">
              <div
                class="lf-trace-image-viewport"
                style=${styleMap({ aspectRatio: extent ? `${extent.width} / ${extent.height}` : undefined, maxWidth: extent ? `${extent.width}px` : undefined })}
                ?data-sized=${!!extent}
              ></div>
              <div class="lf-trace-capture-footer">
                <p class="lf-trace-caption" title=${caption} ?hidden=${!extent}>
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
            </div>
            <div class="lf-trace-image-tools" ?hidden=${!extent}>
              ${[
                ["−", "Zoom image out", () => this.#picture?.zoom(-0.25)],
                ["+", "Zoom image in", () => this.#picture?.zoom(0.25)],
                ["Fit image", null, () => this.#fitPicture()],
                ["Actual size", null, () => this.#picture?.zoomTo(1)],
              ].map(
                ([text, label, run]) =>
                  html`<button
                    ${offered("lf-btn")}
                    aria-label=${label ?? nothing}
                    ?disabled=${!this.#picture?.viewed || q}
                    @click=${run}
                  >
                    ${text}
                  </button>`,
              )}
              <span class="lf-trace-image-zoom"></span>
            </div>
            <div
              class=${classMap({ "lf-trace-metadata": true, "lf-trace-no-action": !action })}
              tabindex="0"
              role="group"
              aria-label="Selected point details"
            >
              <details
                class="lf-trace-tree"
                @scroll=${() => this.#rememberTreePlace()}
                @toggle=${() => this.#treeToggled()}
              >
                <summary>
                  ${tree ? `Saved elements (${tree.nodes.length})` : "Saved elements unavailable"}
                </summary>
                <p class="lf-trace-tree-clock">
                  ${tree ? `Tree captured ${this.#time(tree.timestamp, action.stream)}. Element boxes describe this tree, not exact positions in the image.` : "No accessibility tree was saved at this point."}
                </p>
                <ul class="lf-trace-nodes">
                  ${repeat(
                    rows,
                    ({ id }) => id,
                    ({ node }) =>
                      html`<li class="lf-trace-node">
                        <span class="lf-trace-node-name">${nodeName(node)}</span
                        ><code class="lf-trace-node-path">path ${node.path}</code>
                      </li>`,
                  )}
                </ul>
              </details>
              <p class="lf-trace-clock" ?hidden=${!origin}>
                ${trace?.streams.length > 1 ? `${clockLabel} · each stream has its own clock` : clockLabel}
              </p>
              <p class="lf-trace-readout">
                ${
                  !trace
                    ? "Waiting for a Playwright recording."
                    : !items.length
                      ? "No recorded checkpoints or frames in this recording scope."
                      : `Timeline point ${position + 1} of ${items.length}`
                }
              </p>
              <p class="lf-trace-action">${metadataAction?.title ?? ""}</p>
              <h3 class="lf-trace-phase">
                ${metadataAction ? `${PHASES[metadataPoint.phase]} · ${this.#time(metadataPoint.timestamp, metadataAction.stream)}` : ""}
              </h3>
              <p class="lf-trace-error" ?hidden=${!metadataAction?.error}>
                ${metadataAction?.error ?? ""}
              </p>
            </div>
          </div>
        </div>`,
      this.#view,
    );
  }

  #momentSelected(moment) {
    return (
      !!moment.scope &&
      this.#destination(moment.target) === this.#selected &&
      (this.#chosenBookmark === null || this.#chosenBookmark === moment.index)
    );
  }

  #draw() {
    if (!this.#items().some((point) => point.id === this.#selected))
      this.#selectDefault();
    const view = this.#viewState();
    const { point, image, rows } = view;
    this.#selected = point?.id ?? null;
    if (point?.action) this.#metadataPoint = point;
    const treeScope = point?.action ? this.#phaseId(point.action, point.phase) : null;
    const treeChanged = treeScope !== this.#treeScope;
    const treeRegion = readingRegion(compoundReadingRegionId(this, "saved-elements"));
    // Saved-tree rows may be recreated on return. The reading owner restores
    // their passage or offset in this retained scrollport, independent of nodes.
    if (treeChanged && this.#treeScope && this.treeDetails.open)
      this.#treePlaces.set(this.#treeScope, capturePlace(treeRegion));
    this.#paint(view);
    this.#drawMoments();
    this.#inventory = [];
    const projection = [];
    const add = (id, element, label, path, surface = element) => {
      this.#inventory.push({ id, element, label, surface });
      projection.push({ id, element, label, path });
    };
    const action = point?.action;
    if (action) {
      const actionIndex = this.#trace.actions.indexOf(action);
      add(this.#id("action", action.id), this.actionDetails, action.title, [
        "actions",
        actionIndex,
      ]);
      add(
        this.#phaseId(action, point.phase),
        this.phaseHeading,
        `${action.title} · ${PHASES[point.phase]}`,
        action.phases[point.phase]
          ? ["actions", actionIndex, "phases", point.phase]
          : ["actions", actionIndex],
      );
    }
    if (image) {
      let figure = this.#images.get(image.id);
      if (!figure) {
        figure = el("figure", "lf-trace-image");
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
        if (!quoted(this))
          commands(canvas, "In a captured image", [
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
          ]);
        canvas.addEventListener("pointerdown", () => focusDestination(canvas, "press"));
        canvas.append(img, status);
        figure.append(canvas);
        this.#images.set(image.id, figure);
      }
      const img = figure.querySelector(".lf-trace-canvas > img");
      const label = this.#targets.get(this.#id("image", image.id)).label;
      keeps(img, "src", scopedMediaUrl(image.url));
      keeps(img, "alt", label);
      keeps(img, "width", String(image.width));
      keeps(img, "height", String(image.height));
      keeps(
        img,
        "data-lf-image-width",
        String(this.#imageSizes.get(image.pageId).width),
      );
    }
    this.#drawPicture(image);
    this.#paint(view);
    keepsHidden(this.waiting, !!this.#trace);
    keepsHidden(this.missingImage, !!this.#pictureId);
    keepsText(
      this.missingImage,
      !this.#trace
        ? "The recording has not arrived."
        : this.#pendingPicture
          ? "Loading captured image…"
          : "No captured image is available at or before this timeline point.",
    );
    this.#imageZoom();
    if (this.#picture?.viewed) {
      const committed = this.#trace.images.find((item) => item.id === this.#pictureId);
      const displayed = this.#picture.image;
      const label = this.#targets.get(this.#id("image", committed.id)).label;
      keeps(displayed, "width", String(committed.width));
      keeps(displayed, "height", String(committed.height));
      add(this.#id("image", committed.id), displayed, label, [
        "images",
        this.#trace.images.indexOf(committed),
      ]);
    }
    if (action && this.treeDetails.open)
      for (const [index, { id }] of rows.entries()) {
        const row = this.treeList.children[index];
        add(id, row, this.#targets.get(id).label, [
          "actions",
          this.#trace.actions.indexOf(action),
          "phases",
          point.phase,
          "tree",
          "nodes",
          index,
        ]);
      }
    // Only drawn evidence is projected. Hidden parts keep their archive coordinate
    // in the inventory reader's label/reveal routes, not in a second semantic fold.
    projectData(
      this,
      projection.map((record) => ({
        node: record.element,
        key: record.id,
        identity: record.id,
        label: record.label,
        origin: { ...this.#snapshot.origin, path: record.path },
      })),
      { snapshot: this.#snapshot },
    );
    if (treeChanged) {
      this.#treeScope = treeScope;
      if (this.treeDetails.open)
        restorePlace(this.#treePlaces.get(treeScope), treeRegion);
    }
    this.#parts.update();
    paintKeys();
  }
}
