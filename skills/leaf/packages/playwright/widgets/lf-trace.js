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
 * on manual navigation, hiding or retirement. Captured frames can join that
 * same timeline. Initial selection prefers its first nonempty saved tree, then
 * its first image; empty earlier stops stay navigable. Following a visual part restores its exact
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
} from "/runtime/widget-api.js";

// Reuse the default package’s selected WebAwesome controls, already shipped with Leaf.
await import("../vendor/webawesome.esm.js");
const [{ Timeline, DataSet, css: timelineCss }, { Viewer, css: imageCss }] =
  await Promise.all([
    import("../vendor/timeline.esm.js"),
    import("../vendor/images.esm.js"),
  ]);
// Dependency styles apply only inside recording widgets. Keeping them in their
// module makes the same presentation available in an offline export.
if (!document.querySelector("#lf-trace-library-styles")) {
  const styles = document.createElement("style");
  styles.id = "lf-trace-library-styles";
  styles.textContent = `@layer lf-base { @scope (lf-trace) { ${timelineCss} ${imageCss} } }`;
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

// Transport faces share Leaf's 16px stroke vocabulary; fixed SVGs need no asset load.
function transportButton(label, path) {
  const button = offer("button", "lf-trace-transport-button");
  button.setAttribute("aria-label", label);
  button.title = label;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = path;
  button.append(svg);
  return button;
}

customElements.define(
  "lf-trace",
  class extends HTMLElement {
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
    #nodes = new Map();
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
      if (event.type === "keydown") {
        if (!path.includes(this)) return;
        if (["Shift", "Alt", "Control", "Meta"].includes(event.key)) return;
        this.#playIntent = null;
        if (path.includes(this.play) && ["Enter", " "].includes(event.key)) return;
        this.#pause();
        return;
      }
      if (!["pointerdown", "wheel"].includes(event.type)) return;
      if (!path.includes(this.body) || path.includes(this.play)) return;
      this.#pause();
      // A review gesture freezes the pixels actually on screen, including when
      // another capture is still preparing.
      if (path.includes(this.evidence) && this.#pendingPicture && this.#pictureId)
        this.#reveal(this.#id("image", this.#pictureId));
    };
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
      this.append(this.waiting);
      this.controls = offer("div", "lf-trace-controls");
      this.sources = offer("wa-radio-group", "lf-trace-sources");
      this.sources.name = `${this.id}-scope`;
      this.sources.label = "Recording scope";
      this.sources.size = "s";
      this.sources.orientation = "horizontal";
      this.framesToggle = offer("input", "lf-trace-frames", undefined, "checkbox");
      this.framesToggle.name = `${this.id}-frames`;
      const framesLabel = document.createElement("label");
      framesLabel.className = "lf-trace-frames-label";
      framesLabel.append(this.framesToggle, "Show intermediate frames");
      this.viewer = offer("a", "lf-trace-viewer", "Open in Playwright");
      this.viewer.target = "_blank";
      this.viewer.rel = "noopener noreferrer";
      this.previous = transportButton(
        "Previous",
        '<path d="m10 3.5-4.5 4.5 4.5 4.5"/>',
      );
      this.previous.classList.add("lf-trace-previous");
      this.next = transportButton("Next", '<path d="m6 3.5 4.5 4.5L6 12.5"/>');
      this.next.classList.add("lf-trace-next");
      this.previous.setAttribute("aria-label", "Previous");
      this.next.setAttribute("aria-label", "Next");
      this.previous.title = "Previous recorded point";
      this.next.title = "Next recorded point";
      this.play = transportButton("Play", '<path d="m5 3 7 5-7 5z"/>');
      this.play.classList.add("lf-trace-play");
      // Preserve the pressed meaning if playback ends before pointer release.
      this.play.addEventListener("pointerdown", () => {
        this.#playIntent = this.#playing;
      });
      this.play.addEventListener("pointercancel", () => {
        this.#playIntent = null;
      });
      const pauseIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      pauseIcon.setAttribute("viewBox", "0 0 16 16");
      pauseIcon.setAttribute("aria-hidden", "true");
      pauseIcon.innerHTML = '<path d="M5 3v10M11 3v10"/>';
      this.play.append(pauseIcon, el("span", "", "Play"));
      this.timeline = el("div", "lf-trace-timeline");
      this.timeline.tabIndex = quoted(this) ? -1 : 0;
      this.timeline.setAttribute("role", "group");
      this.timeline.setAttribute("aria-label", "Recording timeline");
      this.timeline.setAttribute(
        "aria-description",
        "Left and Right step through recorded points. Home and End reach the first and last point.",
      );
      this.markers = el("div", "lf-trace-markers");
      this.markers.setAttribute("role", "group");
      this.markers.setAttribute("aria-label", "Timeline moments");
      this.timeline.append(this.markers);
      this.momentHint = el(
        "p",
        "lf-trace-moment-hint",
        "Drag the blue handle to scrub. Drag empty space to pan; zoom to separate nearby moments.",
      );
      const stepper = offer("div", "lf-trace-stepper");
      stepper.append(this.timeline);
      const choices = offer("div", "lf-trace-choices");
      choices.append(this.sources);
      this.positionLabel = el("span", "lf-trace-position");
      this.selectionLabel = el("span", "lf-trace-selection");
      const position = el("div", "lf-trace-position-row");
      position.append(this.positionLabel, this.selectionLabel);
      this.bookmarks = document.createElement("section");
      this.bookmarks.className = "lf-trace-bookmarks";
      this.bookmarkSummary = el("p", "lf-trace-moments-heading");
      this.bookmarkList = el("div", "lf-trace-bookmark-list");
      this.noMoments = el(
        "p",
        "lf-trace-no-moments",
        "No saved moments in this stream.",
      );
      this.bookmarks.append(this.bookmarkSummary, this.bookmarkList);
      this.#bookmarks = [...this.querySelectorAll(":scope > lf-trace-bookmark")].map(
        (member) => {
          const target = member.getAttribute("target");
          const label = member.getAttribute("label");
          const button = offer("button", "lf-trace-bookmark");
          button.addEventListener("click", () => this.#reveal(target, button));
          this.bookmarkList.append(button);
          return { target, label, button };
        },
      );
      const options = el("div", "lf-trace-options");
      options.append(this.bookmarkSummary, this.viewer);
      this.bookmarks.prepend(options);
      this.zoomControls = el("div", "lf-trace-zoom-controls");
      this.zoomControls.setAttribute("role", "group");
      this.zoomControls.setAttribute("aria-label", "Timeline zoom");
      this.zoomIn = transportButton("Zoom in", '<path d="M8 3v10M3 8h10"/>');
      this.zoomOut = transportButton("Zoom out", '<path d="M3 8h10"/>');
      this.zoomReset = transportButton(
        "Whole recording",
        '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
      );
      this.zoomControls.append(this.zoomOut, this.zoomIn, this.zoomReset);
      const toolbar = el("div", "lf-trace-toolbar");
      const transport = el("div", "lf-trace-transport");
      transport.append(this.play, this.previous, this.next);
      toolbar.append(transport, position, this.zoomControls);
      const zoom = (direction) => {
        if (!this.#rail) return;
        this.#rail[direction](0.5, { animation: false });
        const point = this.#items().find((point) => point.id === this.#selected);
        if (point)
          this.#rail.moveTo(point.timestamp - this.#bounds().start, {
            animation: false,
          });
      };
      this.zoomIn.onclick = () => zoom("zoomIn");
      this.zoomOut.onclick = () => zoom("zoomOut");
      this.zoomReset.onclick = () => this.#resetRail();
      const help = el("div", "lf-trace-help");
      help.append(framesLabel, this.momentHint);
      this.controls.append(choices, this.bookmarks, help);
      this.clock = el("p", "lf-trace-clock");
      this.readout = el("p", "lf-trace-readout", "Waiting for a Playwright recording.");
      this.actionDetails = el("p", "lf-trace-action");
      this.phaseHeading = el("h3", "lf-trace-phase");
      this.error = el("p", "lf-trace-error");
      this.error.hidden = true;
      this.imageHost = el("div", "lf-trace-images");
      this.imageViewport = el("div", "lf-trace-image-viewport");
      this.missingImage = el("p", "lf-trace-missing-image");
      this.imageViewport.append(this.missingImage);
      this.captureCaption = el("p", "lf-trace-caption");
      this.fullSize = offer("a", "lf-trace-full-image", "Open full-size image");
      this.fullSize.target = "_blank";
      this.fullSize.rel = "noopener noreferrer";
      const captureFooter = el("div", "lf-trace-capture-footer");
      captureFooter.append(this.captureCaption, this.fullSize);
      this.imageHost.append(this.imageViewport, captureFooter);
      this.imageTools = el("div", "lf-trace-image-tools");
      const imageZoomIn = offer("button", "lf-btn", "+");
      const imageZoomOut = offer("button", "lf-btn", "−");
      const imageFit = offer("button", "lf-btn", "Fit image");
      const imageActual = offer("button", "lf-btn", "Actual size");
      imageZoomIn.setAttribute("aria-label", "Zoom image in");
      imageZoomOut.setAttribute("aria-label", "Zoom image out");
      imageZoomIn.onclick = () => this.#picture?.zoom(0.25);
      imageZoomOut.onclick = () => this.#picture?.zoom(-0.25);
      imageFit.onclick = () => this.#fitPicture();
      imageActual.onclick = () => this.#picture?.zoomTo(1);
      this.imageZoomLabel = el(
        "span",
        "lf-trace-image-zoom",
        "Drag to inspect · pinch to zoom",
      );
      this.imageTools.append(
        imageZoomOut,
        imageZoomIn,
        imageFit,
        imageActual,
        this.imageZoomLabel,
      );
      this.treeDetails = document.createElement("details");
      this.treeDetails.className = "lf-trace-tree";
      this.treeSummary = document.createElement("summary");
      this.treeSummary.textContent = "Saved elements";
      this.treeClock = el("p", "lf-trace-tree-clock");
      this.treeList = el("ul", "lf-trace-nodes");
      this.treeDetails.append(this.treeSummary, this.treeClock, this.treeList);
      this.body = el("div", "lf-trace-body");
      // Review gestures belong to evidence, independently of navigation layout.
      // A bounded point inspector keeps changing metadata and disclosure inside
      // the recording. Its retained disclosure precedes variable rows, so replay
      // cannot move that control as frames and checkpoints replace each other.
      this.evidence = el("div", "lf-trace-evidence");
      const metadata = el("div", "lf-trace-metadata");
      this.metadata = metadata;
      metadata.tabIndex = 0;
      metadata.setAttribute("role", "group");
      metadata.setAttribute("aria-label", "Selected point details");
      // A single-line position summary precedes checkpoint fields. Empty frames
      // retain those fields' extent below the summary, keeping their targets stable.
      metadata.append(
        this.treeDetails,
        this.clock,
        this.readout,
        this.actionDetails,
        this.phaseHeading,
        this.error,
      );
      this.evidence.append(this.imageHost, this.imageTools, metadata);
      this.body.append(toolbar, stepper, this.evidence);
      this.append(this.controls, this.body);
      this.#parts = registerVisualParts(this, () => this.#inventory, {
        label: (id) => this.#targets.get(id)?.label ?? null,
        reveal: (id) => this.#reveal(id),
      });
      this.treeDetails.addEventListener("scroll", () => {
        if (this.treeDetails.open && this.#treeScope)
          this.#treePlaces.set(
            this.#treeScope,
            capturePlace(
              readingRegion(compoundReadingRegionId(this, "saved-elements")),
            ),
          );
      });
      this.treeDetails.addEventListener("toggle", () => {
        this.#draw();
        if (this.treeDetails.open)
          restorePlace(
            this.#treePlaces.get(this.#treeScope),
            readingRegion(compoundReadingRegionId(this, "saved-elements")),
          );
      });
      if (quoted(this)) {
        this.previous.disabled = true;
        this.next.disabled = true;
        return;
      }
      // Vis owns time geometry. The native trace cursor owns discrete phase order,
      // including separately reachable phases sharing exactly one timestamp.
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
      this.sources.addEventListener("change", () => {
        if (this.#scope === this.sources.value) return;
        this.#selectScope(this.sources.value);
        this.#draw();
      });
      this.framesToggle.addEventListener("change", () => {
        this.#pause(false);
        const point = this.#items()[this.#position()];
        this.#intermediates = this.framesToggle.checked;
        const items = this.#items();
        if (point && !items.some((item) => item.id === point.id))
          this.#navigate(
            items.findLast((item) => item.timestamp <= point.timestamp)?.id ??
              items[0]?.id ??
              null,
          );
        else this.#draw();
      });
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
      const stream = this.#trace.streams.findIndex(
        (stream) => stream.id === page.stream,
      );
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
      return page
        ? stream === page.stream && pageId === page.id
        : stream === this.#scope;
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
      // Start with saved page content, otherwise an original image. A late
      // filmstrip frame gets its own stop, never attached to an earlier call.
      const items = this.#items(true);
      const firstTree = items.find((point) => this.#evidence(point).tree?.nodes.length);
      const point =
        firstTree ?? items.find((point) => this.#evidence(point).image) ?? items[0];
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
    #drawPlayback() {
      const label = this.#playing ? "Pause" : "Play";
      keeps(this.play, "aria-label", label);
      keeps(this.play, "title", label);
      keeps(this.play, "data-playing", this.#playing ? "" : null);
      keepsText(this.play.lastElementChild, label);
    }
    #pause(draw = true) {
      if (!this.#playing && this.#cursorTime === null && !this.#scrubbing) return;
      // A playing film is continuous mechanical motion, outside resting proof.
      if (this.#playFrame) cancelAnimation(this.#playFrame);
      this.#playFrame = 0;
      this.#playing = false;
      this.#cursorTime = null;
      if (this.#scrubbing) {
        this.#scrubbing = false;
        dragging(this, false);
      }
      if (draw) {
        this.#drawPlayback();
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
        this.#nodes.clear();
        this.#treePlaces.clear();
        this.#treeScope = null;
        this.#scope = null;
        this.#selected = null;
        this.#chosenBookmark = null;
        this.#intermediates = false;
        setChildren(this.imageViewport, [this.missingImage]);
        setChildren(this.treeList, []);
      }
      if (this.#trace) {
        const choices = this.#scopeChoices();
        this.#drawScopes(choices);
        if (!choices.some(([id]) => id === this.#scope))
          this.#scope = choices[0]?.[0] ?? null;
        keeps(this.viewer, "href", this.#trace.viewerUrl);
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
        setChildren(this.bookmarkList, [
          ...this.#moments.map((moment) => moment.button),
          this.noMoments,
        ]);
      } else {
        this.#targets.clear();
        this.#moments = [];
        this.#drawScopes([]);
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

    #drawScopes(choices) {
      keepsHidden(this.sources, choices.length < 2);
      keepsHidden(this.sources.parentElement, choices.length < 2);
      const prior = new Map(
        [...this.sources.children].map((choice) => [choice.value, choice]),
      );
      setChildren(
        this.sources,
        choices.map(([value, label]) => {
          const choice = prior.get(value) ?? offer("wa-radio", "lf-trace-source");
          choice.appearance = "button";
          keeps(choice, "value", value);
          keepsText(choice, label);
          return choice;
        }),
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
      const target = this.#targets.get(member.target);
      const capture = target?.image ?? target?.action?.phases[target.phase];
      return {
        ...member,
        scope: target?.scope,
        stream: target?.image?.stream ?? target?.action?.stream,
        time:
          capture?.timestamp ??
          (target?.phase === "end"
            ? target?.action?.endTime
            : target?.action?.startTime),
      };
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
      rail.on("timechange", (event) => scrub(event, false));
      rail.on("timechanged", (event) => scrub(event, true));
      rail.on("changed", () => this.#placeCursorHandle());
    }

    #drawMoments() {
      const moments = this.#moments;
      const available = moments.filter(
        (moment) => moment.scope === this.#scope || moment.stream === this.#scope,
      );
      const unavailable = moments.filter((moment) => !moment.scope);
      keepsHidden(this.bookmarkList, !moments.length);
      this.style.setProperty("--lf-trace-moment-rows", Math.min(3, moments.length));
      keepsHidden(this.markers, !this.#trace || !this.#items().length);
      this.markers.classList.toggle("lf-trace-readonly", quoted(this));
      keepsHidden(this.momentHint, !this.#trace || !this.#items().length);
      keepsHidden(this.noMoments, !!available.length || !!unavailable.length);
      keepsText(
        this.bookmarkSummary,
        `Moments (${available.length + unavailable.length})`,
      );
      keepsHidden(this.bookmarkSummary, !moments.length);
      for (const moment of moments) {
        const visible = available.includes(moment) || !moment.scope;
        keepsHidden(moment.button, !visible);
        keeps(moment.button, "disabled", !moment.scope || quoted(this) ? "" : null);
        if (!moment.button.firstElementChild) {
          moment.button.append(
            el("span", "lf-trace-moment-number"),
            el("span", "lf-trace-moment-label"),
            el("span", "lf-trace-moment-time"),
          );
        }
        const [number, label, time] = moment.button.children;
        keepsText(number, String(moment.number));
        keepsText(label, moment.label);
        const momentTime = moment.scope
          ? this.#time(moment.time, moment.stream)
          : "Unavailable";
        keepsText(time, momentTime);
        keeps(
          moment.button,
          "aria-label",
          `Moment ${moment.number} · ${moment.label} · ${momentTime}`,
        );
        const selected =
          !!moment.scope &&
          this.#destination(moment.target) === this.#selected &&
          (!this.#chosenBookmark || this.#chosenBookmark === moment.button);
        keeps(moment.button, "aria-current", selected ? "true" : null);
      }
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
        keeps(
          pin,
          "aria-current",
          moment.button.hasAttribute("aria-current") ? "true" : null,
        );
        pin.onclick = () => this.#reveal(moment.target, moment.button);
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
      cursor.style.setProperty("--lf-trace-cursor-axis", `${rail.top - line.top}px`);
      const middle = line.left + line.width / 2;
      const left = middle - rail.left;
      const right = rail.right - middle;
      const shift = (half) =>
        left < 0 || right < 0
          ? 0
          : Math.max(0, half - left) - Math.max(0, half - right);
      cursor.style.setProperty(
        "--lf-trace-cursor-hit-shift",
        `${shift(halfControl)}px`,
      );
      const halfCap = Number.parseFloat(getComputedStyle(cursor, "::before").width) / 2;
      cursor.style.setProperty("--lf-trace-cursor-cap-shift", `${shift(halfCap)}px`);
    }

    #draw() {
      keepsHidden(this.waiting, !!this.#trace);
      keepsHidden(this.controls, !this.#trace);
      keepsHidden(this.body, !this.#trace);
      this.#inventory = [];
      const projection = [];
      const add = (id, element, label, path, surface = element) => {
        this.#inventory.push({ id, element, label, surface });
        projection.push({ id, element, label, path });
      };
      if (!this.#items().some((point) => point.id === this.#selected))
        this.#selectDefault();
      const items = this.#items();
      const position = Math.max(0, Math.min(this.#position(), items.length - 1));
      const point = items[position];
      const treeScope = point?.action ? this.#phaseId(point.action, point.phase) : null;
      const treeChanged = treeScope !== this.#treeScope;
      const treeRegion = readingRegion(compoundReadingRegionId(this, "saved-elements"));
      // Saved trees replace each other under their archive phase identity. Keep
      // each reading through empty frames and returns using Leaf's place owner.
      if (treeChanged && this.#treeScope && this.treeDetails.open)
        this.#treePlaces.set(this.#treeScope, capturePlace(treeRegion));
      this.#selected = point?.id ?? null;
      if (this.sources.value !== (this.#scope ?? ""))
        this.sources.value = this.#scope ?? "";
      keeps(this.sources, "disabled", !this.#trace || quoted(this) ? "" : null);
      this.framesToggle.checked =
        this.#frames().length > 0 &&
        (this.#intermediates || !this.#checkpoints().length);
      keeps(
        this.framesToggle,
        "disabled",
        !this.#frames().length || !this.#checkpoints().length || quoted(this)
          ? ""
          : null,
      );
      const bounds = this.#bounds();
      keeps(
        this.play,
        "disabled",
        quoted(this) || this.#items(true).length < 2 ? "" : null,
      );
      this.#drawPlayback();
      keeps(
        this.zoomIn,
        "disabled",
        quoted(this) || bounds.end - bounds.start < 1 ? "" : null,
      );
      keeps(this.zoomOut, "disabled", quoted(this) ? "" : null);
      keeps(this.zoomReset, "disabled", quoted(this) ? "" : null);
      keepsText(
        this.positionLabel,
        point ? this.#time(point.timestamp, this.#stream()) : "No recorded points",
      );
      const selectedMoments = this.#moments.filter(
        (moment) =>
          this.#selected && this.#destination(moment.target) === this.#selected,
      );
      const selectedMoment =
        selectedMoments.find((moment) => moment.button === this.#chosenBookmark) ??
        selectedMoments[0];
      const selection =
        (selectedMoment
          ? `Moment ${selectedMoment.number} · ${selectedMoment.label}`
          : null) ??
        (point?.action
          ? `${PHASES[point.phase]} · ${point.action.title}`
          : point
            ? "Captured frame"
            : "");
      keepsText(this.selectionLabel, selection);
      keeps(this.selectionLabel, "title", selection);
      this.#drawMoments();
      keepsHidden(this.viewer, !this.#trace);
      keepsHidden(this.clock, !this.#origins.has(this.#stream()));
      const origin = this.#origins.get(this.#stream());
      const clockLabel =
        origin && origin.recordedStart !== null && origin.recordedStart === origin.start
          ? "Elapsed since recording started"
          : "Elapsed from first captured event";
      keepsText(
        this.clock,
        this.#trace?.streams.length > 1
          ? `${clockLabel} · each stream has its own clock`
          : clockLabel,
      );
      const hasAction = !!point?.action;
      // A filmstrip frame has no action target. Retain the previous rows' extent
      // while hiding them, so an inspected scroll position cannot be clamped.
      this.metadata.classList.toggle("lf-trace-no-action", !hasAction);
      const { image, tree } = this.#evidence(point);
      let action = null;
      let phase = null;
      if (point?.action) {
        action = point.action;
        phase = action.phases[point.phase];
        keepsText(this.actionDetails, action.title);
        keepsText(
          this.phaseHeading,
          `${PHASES[point.phase]} · ${this.#time(point.timestamp, action.stream)}`,
        );

        keepsText(this.error, action.error ?? "");
        keepsHidden(this.error, !action.error);
        const actionIndex = this.#trace.actions.indexOf(action);
        add(this.#id("action", action.id), this.actionDetails, action.title, [
          "actions",
          actionIndex,
        ]);
        add(
          this.#phaseId(action, point.phase),
          this.phaseHeading,
          `${action.title} · ${PHASES[point.phase]}`,
          phase
            ? ["actions", actionIndex, "phases", point.phase]
            : ["actions", actionIndex],
        );
      }

      const reading = !this.#trace
        ? "Waiting for a Playwright recording."
        : !items.length
          ? "No recorded checkpoints or frames in this recording scope."
          : `Timeline point ${position + 1} of ${items.length}`;
      keepsText(this.readout, reading);
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
                run: () => this.#picture?.move(-40, 0),
              },
              {
                id: "trace.image.right",
                keys: ["ArrowRight"],
                title: "pan image right",
                control: canvas,
                run: () => this.#picture?.move(40, 0),
              },
              {
                id: "trace.image.up",
                keys: ["ArrowUp"],
                title: "pan image up",
                control: canvas,
                run: () => this.#picture?.move(0, -40),
              },
              {
                id: "trace.image.down",
                keys: ["ArrowDown"],
                title: "pan image down",
                control: canvas,
                run: () => this.#picture?.move(0, 40),
              },
            ]);
          canvas.addEventListener("pointerdown", () =>
            focusDestination(canvas, "press"),
          );
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
      // The scope's viewport exists even before its first captured image.
      // Pixel surfaces can arrive or retire without changing review geometry.
      const extent = this.#imageSizes.get(this.#scope);
      this.imageViewport.style.aspectRatio = extent
        ? `${extent.width} / ${extent.height}`
        : "";
      this.imageViewport.style.maxWidth = extent ? `${extent.width}px` : "";
      keeps(this.imageViewport, "data-sized", extent ? "" : null);
      keepsHidden(this.imageTools, !extent);
      this.#drawPicture(image);
      const committedImage = this.#trace?.images.find(
        (item) => item.id === this.#pictureId,
      );
      keepsHidden(this.missingImage, !!this.#pictureId);
      keepsText(
        this.missingImage,
        !this.#trace
          ? "The recording has not arrived."
          : this.#pendingPicture
            ? "Loading captured image…"
            : "No captured image is available at or before this timeline point.",
      );
      const caption = committedImage
        ? this.#targets.get(this.#id("image", committedImage.id)).label
        : this.#pendingPicture
          ? "Loading captured image…"
          : "No captured image at this point.";
      keepsText(this.captureCaption, caption);
      keeps(this.captureCaption, "title", caption);
      keepsHidden(this.captureCaption, !extent);
      keepsHidden(this.fullSize, !extent);
      keeps(this.fullSize, "inert", committedImage ? null : "");
      keeps(this.fullSize, "aria-hidden", committedImage ? null : "true");
      keeps(
        this.fullSize,
        "href",
        committedImage ? scopedMediaUrl(committedImage.url) : null,
      );
      this.#imageZoom();
      if (this.#picture?.viewed) {
        const committed = this.#trace.images.find(
          (item) => item.id === this.#pictureId,
        );
        const displayed = this.#picture.image;
        const label = this.#targets.get(this.#id("image", committed.id)).label;
        keeps(displayed, "width", String(committed.width));
        keeps(displayed, "height", String(committed.height));
        add(this.#id("image", committed.id), displayed, label, [
          "images",
          this.#trace.images.indexOf(committed),
        ]);
      }
      for (const button of this.imageTools.querySelectorAll("button"))
        keeps(button, "disabled", !this.#picture?.viewed || quoted(this) ? "" : null);
      const rows = [];
      keepsText(
        this.treeSummary,
        tree ? `Saved elements (${tree.nodes.length})` : "Saved elements unavailable",
      );
      keepsText(
        this.treeClock,
        tree
          ? `Tree captured ${this.#time(tree.timestamp, action.stream)}. Element boxes describe this tree, not exact positions in the image.`
          : action
            ? "No accessibility tree was saved for this phase. Full DOM inspection is available in Playwright."
            : "No saved elements at this frame. Choose an action checkpoint to inspect its saved tree.",
      );
      if (action) {
        for (const [index, node] of (tree?.nodes ?? []).entries()) {
          const id = this.#nodeId(action, point.phase, node);
          let row = this.#nodes.get(id);
          if (!row) {
            row = el("li", "lf-trace-node");
            row.append(
              el("span", "lf-trace-node-name"),
              el("code", "lf-trace-node-path"),
            );
            this.#nodes.set(id, row);
          }
          keepsText(row.querySelector("span"), nodeName(node));
          keepsText(row.querySelector("code"), `path ${node.path}`);
          rows.push(row);
          if (this.treeDetails.open)
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
      }
      setChildren(this.treeList, rows);
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
  },
);
