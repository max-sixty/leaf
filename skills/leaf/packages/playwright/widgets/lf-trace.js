/* Review one immutable Playwright recording. Playwright owns capture and native
 * clocks; Leaf owns comments. Browsing remains local mechanical state.
 * Phases, images and saved-tree nodes have archive-scoped comment coordinates.
 * A phase prefers its PNG, otherwise the latest same-page frame. Earlier empty
 * points preview the first real capture, labeled with its actual later time.
 * Recording-wide operations preserve the chosen image's real page and time.
 * Pixel comments identify that image; semantic comments identify a saved-tree
 * path. Sequential image and tree captures do not imply pixel alignment.
 *
 * One chronology includes every original operation, checkpoint and frame.
 * Vis owns time geometry, collision stacking, pan and zoom;
 * Viewer.js owns image inspection. Native input and moment buttons retain their
 * identity and focus through resize. Every stacked row contributes its full
 * height in document flow; the timeline never scrolls vertically on its own.
 * A new rail measures its rows and recording window before exposing controls.
 * The ruler holds the scrub handle, clear of the visible input and moment rows.
 * Input boxes mark snapshot times, not key-down durations. The brief image
 * annotation names the last input and its approximate time, never a held key.
 * The stage preserves a useful image minimum and grows in document flow when
 * transport, evidence and tools cannot fit the viewport. Later metadata never
 * overlaps it. Empty and captured states reserve the same image allocation.
 *
 * Recorded pace preserves native timing. Review pace integrates important
 * input/result intervals without skipping boundaries or changing coordinates.
 * Explicit navigation and inspection pause playback; ordinary page scrolling
 * does not. Authored bookmark keys pair semantic results in a comparison group;
 * equal labels or clocks never establish correspondence between recordings.
 *
 * Scope-specific image views, time windows and saved-tree reading places outlive
 * their renderers. Same-page captures retain inspected scale and origin; fitted
 * images continue to fit. A pending Viewer prepares offscreen, then atomically
 * commits decoded pixels, caption and comment identity before retiring the old
 * surface. Inspection can settle on the still-visible capture during that wait.
 * Filmstrip frames retain the latest same-page saved checkpoint and its exact
 * comment identity. Saved elements has one stable disclosure; reading restoration
 * respects its current closure, while explicit destination navigation opens it.
 */
import {
  commands,
  authoredScope,
  capturePlace,
  declarationFor,
  dragging,
  cancelRender,
  cancelAnimation,
  nextAnimation,
  nextRender,
  compoundReadingRegionId,
  registerReadingRegion,
  registerMechanicalView,
  readingRegion,
  restorePlace,
  keepsHidden,
  el,
  focusDestination,
  focused,
  holdFocus,
  keeps,
  keepsText,
  layoutPx,
  once,
  onUserInput,
  offer,
  paintKeys,
  projectData,
  quoted,
  registerVisualParts,
  scopedMediaUrl,
  retainUserIntent,
  scrollBehavior,
  scrollIntoReadingBand,
  setChildren,
  sizeObserver,
  watchData,
  widgetController,
} from "/runtime/widget-api.js";

import { advancePlayback, mergeIntervals } from "./playback.js";

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
    #inputPins = new Map();
    #pendingPicture = null;
    #scopeViews = new Map();
    #applyingPictureView = false;
    #picture = null;
    #pictureId = null;
    #picturePreview = false;
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
          this.#closeRail();
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
            if (overview) this.#resetRail();
            done();
          });
          rail.redraw();
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
      if (firstConnection) {
        this.#build();
        registerMechanicalView(this, () => {
          const rail = this.#rail;
          const window = rail?.getWindow();
          return () => {
            if (rail && rail === this.#rail)
              rail.setWindow(window.start, window.end, { animation: false });
          };
        });
      }
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
            when: () => this.#items().length > 1,
            run: () => {
              const pause = this.#playIntent ?? this.#playing;
              this.#playIntent = null;
              if (pause) this.#pause();
              else this.#startPlayback();
            },
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
      this.viewer = offer("a", "lf-trace-viewer", "Open in Playwright");
      this.viewer.target = "_blank";
      this.viewer.rel = "noopener noreferrer";
      this.first = transportButton("Start", '<path d="M3 3v10M12 3 5 8l7 5z"/>');
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
      let pressedPlay = null;
      this.play.addEventListener("pointerdown", (event) => {
        pressedPlay = { pointerId: event.pointerId, pause: this.#playing };
      });
      this.play.addEventListener("pointercancel", () => {
        pressedPlay = null;
      });
      this.play.addEventListener(
        "click",
        (event) => {
          // Only the matching pointer click carries its press across a clock change.
          // A canceled mouse press cannot decide a later keyboard or command action.
          this.#playIntent =
            pressedPlay && event.detail > 0 && event.pointerId === pressedPlay.pointerId
              ? pressedPlay.pause
              : null;
          pressedPlay = null;
        },
        { capture: true },
      );
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
          button.addEventListener("click", () => this.#visitMoment(target, button));
          this.bookmarkList.append(button);
          return { target, label, key: member.getAttribute("key"), button };
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
      transport.append(this.first, this.play, this.previous, this.next);
      toolbar.append(transport, position, this.zoomControls);
      const paceLabel = el("label", "lf-trace-pace", "Pace ");
      this.pace = offer("select");
      this.pace.name = `${this.id}-pace`;
      this.pace.setAttribute("aria-label", "Playback pace");
      this.pace.title =
        "Review pace slows near recorded input and marked results, and speeds quiet intervals.";
      this.pace.setAttribute("aria-description", this.pace.title);
      for (const [value, label] of [
        ["recorded", "Recorded (1×)"],
        ["review", "Review (0.35–3×)"],
      ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        this.pace.append(option);
      }
      paceLabel.append(this.pace);
      toolbar.append(paceLabel);
      const zoom = (direction) => {
        this.#pause();
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
      this.zoomReset.onclick = () => {
        this.#pause();
        this.#resetRail();
      };
      this.controls.append(choices, this.bookmarks);
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
      this.inputBadge = el("span", "lf-trace-input-badge");
      this.inputPoint = el("span", "lf-trace-input-point");
      this.inputBadge.hidden = this.inputPoint.hidden = true;
      this.imageViewport.append(this.inputBadge, this.inputPoint);
      this.captureCaption = el("p", "lf-trace-caption");
      this.fullSize = offer("a", "lf-trace-full-image", "Open full-size image");
      this.fullSize.target = "_blank";
      this.fullSize.rel = "noopener noreferrer";
      const captureFooter = el("div", "lf-trace-capture-footer");
      captureFooter.append(this.captureCaption, this.fullSize);
      this.imageHost.append(this.imageViewport);
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
      const inspect = (event) => {
        const path = event.composedPath();
        if (path.includes(this.metadata)) this.#pause();
        else if (
          event.type === "lf-inspect" ||
          path.includes(this.imageViewport) ||
          path.includes(this.imageTools)
        )
          this.#inspectEvidence();
      };
      this.evidence.addEventListener("click", inspect, { capture: true });
      this.addEventListener("lf-inspect", inspect);
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
      // One stage owns the available viewport. The flexible canvas gives room
      // to the actual rail and tools, keeping result and inspection together.
      this.stage = el("div", "lf-trace-stage");
      this.stage.append(toolbar, stepper, this.imageHost, this.imageTools);
      this.evidence.append(this.stage, captureFooter, metadata);
      this.body.append(this.evidence);
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
          control: this.first,
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
    #items() {
      const points = this.#checkpoints();
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
      if (!image && point) {
        // A recording may begin before its first screencast. Preview the first
        // real image, retaining its later timestamp and exact comment identity.
        image =
          this.#trace.images
            .filter(
              (image) =>
                image.stream === (action?.stream ?? point.image?.stream) &&
                (!pageId || image.pageId === pageId),
            )
            .sort((a, b) => a.timestamp - b.timestamp)[0] ?? null;
      }
      const treePoint = phase?.tree
        ? point
        : this.#checkpoints()
            .sort((a, b) => a.timestamp - b.timestamp)
            .filter(
              (candidate) =>
                candidate.timestamp <= point?.timestamp &&
                candidate.action.stream === (action?.stream ?? point?.image?.stream) &&
                candidate.action.phases[candidate.phase]?.pageId ===
                  (pageId ?? point?.image?.pageId) &&
                candidate.action.phases[candidate.phase]?.tree,
            )
            .at(-1);
      return {
        image,
        tree: treePoint?.action.phases[treePoint.phase]?.tree ?? null,
        treePoint,
      };
    }
    #selectDefault() {
      // Start with saved page content, otherwise an original image. A late
      // filmstrip frame gets its own stop, never attached to an earlier call.
      const items = this.#items();
      const firstTree = items.find((point) => this.#evidence(point).tree?.nodes.length);
      const point =
        firstTree ??
        items.find((point) => {
          const image = this.#evidence(point).image;
          return image && image.timestamp <= point.timestamp;
        }) ??
        items[0];
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
      this.#rail?.setOptions({ moveable: true });
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
      const points = this.#items();
      if (points.length < 2) return;
      // Playback includes every original filmstrip capture.
      const selected = points.find((point) => point.id === this.#selected);
      const from = selected === points.at(-1) ? points[0] : (selected ?? points[0]);
      let time = from.timestamp;
      const origin = this.#bounds().start;
      const end = points.at(-1).timestamp;
      this.#playing = true;
      this.#rail?.setOptions({ moveable: false });
      this.#chosenBookmark = null;
      this.#selected = from.id;
      this.#cursorTime = from.timestamp - origin;
      this.#draw();
      let previousTick = performance.now();
      const intervals = mergeIntervals([
        ...this.#inputActions().map((action) => [
          action.startTime - 200,
          Math.max(this.#inputTime(action), action.endTime ?? action.startTime) + 450,
        ]),
        ...this.#moments
          .filter(
            (moment) => moment.scope === this.#scope || moment.stream === this.#scope,
          )
          .map((moment) => {
            const target = this.#targets.get(moment.target);
            return [target?.action?.startTime ?? moment.time - 400, moment.time + 300];
          }),
      ]);
      const tick = () => {
        this.#playFrame = 0;
        if (!this.#playing) return;
        const now = performance.now();
        time = Math.min(
          end,
          advancePlayback(
            time,
            now - previousTick,
            this.pace.value === "review" ? intervals : null,
          ),
        );
        previousTick = now;
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
        setChildren(this.imageViewport, [
          this.missingImage,
          this.inputBadge,
          this.inputPoint,
        ]);
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
      // A peer may have chosen a shared result while this source was arriving.
      // The peer's authored bookmark is the mechanical selection authority.
      const comparison = this.#comparison();
      if (this.#trace && comparison && !this.#chosenBookmark && !quoted(this)) {
        const peer = [...authoredScope(this).querySelectorAll("lf-trace")].find(
          (peer) =>
            peer !== this && peer.#comparison() === comparison && peer.#chosenBookmark,
        );
        const key = peer?.#bookmarks.find(
          (moment) => moment.button === peer.#chosenBookmark,
        )?.key;
        const match = key && this.#bookmarks.find((moment) => moment.key === key);
        if (match && this.#targets.has(match.target))
          this.#reveal(match.target, match.button);
      }
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
      });
      this.#cancelPicture();
      this.#scope = scope;
      const saved = this.#scopeView();
      this.#selected = saved.selected ?? null;
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
      if (target.node) keeps(this.treeDetails, "open", "");
      this.#draw();
      this.#drawCursor(true);
    }

    async #visitMoment(id, bookmark) {
      const mayArrive = retainUserIntent();
      this.#reveal(id, bookmark);
      const comparison = this.#comparison();
      const key = this.#bookmarks.find((moment) => moment.button === bookmark)?.key;
      // A semantic pairing is authored explicitly; equal times and matching
      // labels do not establish it. Set each peer's own captured coordinate,
      // without taking focus or scrolling a hidden recording into the page.
      if (comparison && key && !quoted(this)) {
        for (const peer of authoredScope(this).querySelectorAll("lf-trace")) {
          if (peer === this || peer.#comparison() !== comparison) continue;
          const match = peer.#bookmarks.find((moment) => moment.key === key);
          if (match && peer.#targets.has(match.target))
            peer.#reveal(match.target, match.button);
        }
      }
      await this.#pendingPicture?.ready;
      if (!mayArrive() || this.#chosenBookmark !== bookmark) return;
      const target = this.#targets.get(id);
      const destination = target?.node
        ? this.querySelector(`[data-lf-datum="${CSS.escape(id)}"]`)
        : this.#pictureId
          ? this.stage
          : null;
      if (destination)
        scrollIntoReadingBand(destination, destination, "center", scrollBehavior());
    }

    #stream() {
      return (
        this.#trace?.pages.find((page) => page.id === this.#scope)?.stream ??
        this.#trace?.streams.find((stream) => stream.id === this.#scope)?.id
      );
    }
    #comparison() {
      return this.getAttribute("compare") ?? this.closest("lf-trace-compare")?.id;
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
      this.#drawInput();
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
        setChildren(this.imageViewport, [
          this.missingImage,
          this.inputBadge,
          this.inputPoint,
        ]);
        return;
      }
      if (this.#pendingPicture?.image.id !== image.id) this.#cancelPicture();
      const point = this.#items().find((point) => point.id === this.#selected);
      const preview =
        image.timestamp > point.timestamp &&
        !point.action?.phases[point.phase]?.imageId;
      if (this.#pictureId === image.id) {
        this.#picturePreview = preview;
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
          this.#picturePreview = preview;
          this.#pictureScope = pending.scope;
          this.#pendingPicture = null;
          keeps(this.imageHost, "aria-busy", null);
          figure.classList.remove("lf-trace-image-pending");
          figure.inert = false;
          keeps(figure, "aria-hidden", null);
          keeps(source, "hidden", "");
          setChildren(this.imageViewport, [
            this.missingImage,
            figure,
            this.inputBadge,
            this.inputPoint,
          ]);
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
                event.detail.originalEvent?.pointerType === "touch" &&
                this.#playing
              ) {
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
              this.#drawInput();
              this.#parts.update();
            },
            zoomed: () => {
              this.#rememberPictureView(pending.viewer);
              this.#imageZoom();
              this.#drawInput();
              this.#parts.update();
            },
          });
        }, failed);
      });
      pending.ready = ready;
      widgetController(this).present(ready);
    }

    #resetRail() {
      if (!this.#rail) return;
      const { min, max } = this.#limitRail(this.#rail);
      this.#rail.setWindow(min, max, { animation: false });
    }

    #limitRail(rail) {
      // Vis's initial-draw callback can arrive after its instance is retired.
      if (rail !== this.#rail) return;
      // Time belongs to Vis, including the space occupied by a centered handle.
      // Reserve that space in the time window, never by shifting the visible
      // thumb away from the line representing its time.
      const duration = Math.max(1, this.#bounds().end - this.#bounds().start);
      const gutter = this.#controlSize() / 2 + 2;
      const padding =
        (duration * gutter) / Math.max(1, this.timeline.clientWidth - 2 * gutter);
      // All rail controls have this declared width. Library item fitting also
      // measures whichever rows happen to be drawn; that is presentation state,
      // and recomputing bounds from it clamps a restored pan to a new window.
      const min = -padding;
      const max = duration + padding;
      const { start, end } = rail.getWindow();
      rail.setOptions({ min, max, zoomMax: max - min });
      rail.setWindow(start, end, { animation: false });
      return { min, max };
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
      keeps(this.markers, "aria-busy", null);
      this.#railData = null;
      this.#railReady = false;
      this.#railFollow = false;
    }

    #inputTime(action) {
      // Native input events have no timestamp. This is an action checkpoint,
      // with call times used only when the archive has no captured checkpoint.
      return (
        action.phases.action?.timestamp ??
        action.phases.after?.timestamp ??
        action.endTime ??
        action.startTime
      );
    }

    #inputLabel(action) {
      return action.input.key
        ? `Press ${action.input.key}`
        : action.method[0].toUpperCase() + action.method.slice(1);
    }

    #inputActions() {
      return (this.#trace?.actions ?? []).filter(
        (action) =>
          action.input &&
          action.stream === this.#stream() &&
          (this.#scope === action.stream || action.pageId === this.#scope),
      );
    }

    #drawInput() {
      // A restored view adjusts zoom and pan together. Viewer emits each
      // intermediate pose synchronously; draw only after that view is complete.
      if (this.#applyingPictureView) return;
      const point = this.#items().find((point) => point.id === this.#selected);
      const action = this.#inputActions()
        .sort((a, b) => this.#inputTime(a) - this.#inputTime(b))
        .filter((action) => {
          const time = this.#inputTime(action);
          const pageId = point?.image?.pageId ?? point?.action?.pageId;
          return (
            point &&
            action.pageId === pageId &&
            time <= point.timestamp &&
            point.timestamp - time <= 500
          );
        })
        .at(-1);
      const image = this.#trace?.images.find((image) => image.id === this.#pictureId);
      const imageReady = point && image && this.#evidence(point).image?.id === image.id;
      keepsHidden(this.inputBadge, !action || !imageReady);
      keepsText(
        this.inputBadge,
        action
          ? `Last input: ${action.input.key ?? this.#inputLabel(action)} · ~${this.#time(this.#inputTime(action), action.stream)}`
          : "",
      );
      keeps(
        this.inputBadge,
        "title",
        action
          ? `${this.#inputLabel(action)}${action.input.selector ? ` · ${action.input.selector}` : ""} · input checkpoint ${this.#time(this.#inputTime(action), action.stream)}; exact input time and held-key duration are not recorded`
          : null,
      );
      const coordinate = action?.input.point;
      const viewport = action?.input.viewport;
      const visible =
        coordinate &&
        viewport &&
        imageReady &&
        image.pageId === action.pageId &&
        this.#picture?.viewed;
      keepsHidden(this.inputPoint, !visible);
      if (visible) {
        const raster = this.#picture.image.getBoundingClientRect();
        const host = this.imageViewport.getBoundingClientRect();
        this.inputPoint.style.left = layoutPx(
          raster.left - host.left + (coordinate.x / viewport.width) * raster.width,
        );
        this.inputPoint.style.top = layoutPx(
          raster.top - host.top + (coordinate.y / viewport.height) * raster.height,
        );
        keeps(this.inputPoint, "title", this.#inputLabel(action));
      }
    }

    #railItems(available) {
      const bounds = this.#bounds();
      const duration = Math.max(1, bounds.end - bounds.start);
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
        ...this.#inputActions().map((action) => ({
          id: `input:${action.id}`,
          start: this.#inputTime(action) - bounds.start,
          type: "box",
          className: "lf-trace-input-event",
          inputAction: action,
          content: "",
        })),
        ...available.map((moment) => ({
          id: moment.number,
          start: moment.time - bounds.start,
          content: String(moment.number),
          type: "box",
          align: "center",
        })),
      ];
    }

    #focusRailControl(control, id) {
      if (!this.#rail || !control.matches(":focus-visible")) return;
      const viewport = this.markers.querySelector(".vis-panel.vis-center");
      const box = control.getBoundingClientRect();
      const frame = viewport.getBoundingClientRect();
      if (box.left < frame.left || box.right > frame.right) {
        this.#rail.focus(id, { zoom: false, animation: false });
        return;
      }
    }

    #buildRail(available) {
      this.#railViewScope = this.#scope;
      const window = this.#scopeView().window;
      this.#railData = new DataSet(this.#railItems(available));
      let rail;
      keeps(this.markers, "aria-busy", "true");
      const ready = this.#waitRail((resolve) => {
        this.#rail = rail = new Timeline(this.markers, this.#railData, {
          rtl: getComputedStyle(this).direction === "rtl",
          autoResize: false,
          showCurrentTime: false,
          onInitialDrawComplete: () => {
            if (rail !== this.#rail) return resolve();
            this.#limitRail(rail);
            // Let Vis complete its initial fit before restoring a mechanical view.
            // Constructor start/end uses a separate deferred range-change latch.
            if (window) rail.setWindow(window.start, window.end, { animation: false });
            else this.#resetRail();
            // Vis's intrinsic height exposes every collision row. The stage
            // grows in document flow when the rows and image need more room.
            this.#railReady = true;
            this.#drawMoments();
            this.#drawCursor(this.#railFollow);
            this.#railFollow = false;
            // Initial item fitting and our recording window are separate Vis
            // commits. Publish controls only after the canonical window redraw,
            // preserving measurement while no preliminary hit target is exposed.
            const committed = () => {
              rail.off("changed", committed);
              if (rail === this.#rail) keeps(this.markers, "aria-busy", null);
              resolve();
            };
            rail.on("changed", committed);
            rail.redraw();
          },
          showMajorLabels: false,
          stack: true,
          cluster: false,
          selectable: false,
          orientation: "top",
          zoomKey: "ctrlKey",
          zoomMin: 1,
          snap: null,
          // The ruler already holds the full cursor hit target. Collision rows
          // start directly below it, without another empty control lane.
          margin: {
            item: Number.parseFloat(getComputedStyle(this).getPropertyValue("--sp-2")),
            axis: 2,
          },
          format: {
            minorLabels: (date) =>
              `${(+date / 1000).toFixed(+date % 10 ? 3 : +date % 1000 ? 2 : 0)} s`,
          },
          template: (item) => {
            if (item.inputAction) {
              const label = this.#inputLabel(item.inputAction);
              let tick = this.#inputPins.get(item.id);
              if (!tick) {
                tick = offer("button", "lf-trace-input-tick");
                tick.textContent = item.inputAction.input.key ?? label;
                tick.title = `${label} · ${this.#time(this.#inputTime(item.inputAction), item.inputAction.stream)}`;
                tick.setAttribute("aria-label", tick.title);
                tick.disabled = quoted(this);
                tick.addEventListener("pointerdown", () =>
                  focusDestination(tick, "press"),
                );
                tick.addEventListener("focus", () => {
                  this.#focusRailControl(tick, item.id);
                });
                tick.addEventListener("click", () => {
                  const phase =
                    this.#phases(item.inputAction).find(
                      (phase) =>
                        this.#inputTime(item.inputAction) ===
                        (item.inputAction.phases[phase]?.timestamp ??
                          item.inputAction.endTime),
                    ) ?? "start";
                  this.#navigate(this.#phaseId(item.inputAction, phase));
                });
                this.#inputPins.set(item.id, tick);
              }
              return tick;
            }
            return item.type === "background"
              ? ""
              : this.#pins.get(item.id).parentElement;
          },
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
      const available = moments.filter(
        (moment) => moment.scope === this.#scope || moment.stream === this.#scope,
      );
      const unavailable = moments.filter((moment) => !moment.scope);
      keepsHidden(this.bookmarkList, !moments.length);
      this.style.setProperty("--lf-trace-moment-rows", Math.min(3, moments.length));
      keepsHidden(this.markers, !this.#trace || !this.#items().length);
      this.markers.classList.toggle("lf-trace-readonly", quoted(this));
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
        this.#inputPins.clear();
      }
      for (const moment of available) {
        let pin = this.#pins.get(moment.number);
        if (!pin) {
          pin = offer("button", "lf-trace-marker");
          // Vis claims pointer defaults for its gestures. The embedded native
          // control still owns focus, including tooltip blur/re-arm behavior.
          pin.addEventListener("pointerdown", () => focusDestination(pin, "press"));
          pin.addEventListener("focus", () => {
            this.#focusRailControl(pin, moment.number);
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
        pin.onclick = () => this.#visitMoment(moment.target, moment.button);
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
      // Initial preparation refreshes this signature after Vis draws its rows.
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
      const ruler = this.markers.querySelector(".vis-panel.vis-top");
      if (!cursor || !ruler) return;
      // The native time coordinate owns both paint and hit region. The range
      // reserves edge room; no part of the playhead has a second x coordinate.
      const line = cursor.getBoundingClientRect();
      const axis = ruler.getBoundingClientRect();
      cursor.style.setProperty("--lf-trace-cursor-axis", `${axis.top - line.top}px`);
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
      const { image, tree, treePoint } = this.#evidence(point);
      const treeScope = treePoint
        ? this.#phaseId(treePoint.action, treePoint.phase)
        : null;
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
      const bounds = this.#bounds();
      keeps(this.first, "disabled", quoted(this) || !items.length ? "" : null);
      keeps(
        this.play,
        "disabled",
        quoted(this) || this.#items().length < 2 ? "" : null,
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
          ? `${PHASES[point.phase]}${["before", "action", "after"].includes(point.phase) ? " checkpoint" : ""} · ${point.action.title}`
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
      let action = null;
      let phase = null;
      if (point?.action) {
        action = point.action;
        phase = action.phases[point.phase];
        keepsText(this.actionDetails, action.title);
        keepsText(
          this.phaseHeading,
          `${PHASES[point.phase]}${phase ? " checkpoint" : ""} · ${this.#time(point.timestamp, action.stream)}`,
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
        ? `${this.#targets.get(this.#id("image", committedImage.id)).label}${this.#picturePreview ? " · First capture after this point" : ""}`
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
      keepsText(this.treeSummary, "Saved elements");
      keepsText(
        this.treeClock,
        tree
          ? `${tree.nodes.length} elements · ${PHASES[treePoint.phase]} checkpoint at ${this.#time(tree.timestamp, treePoint.action.stream)}. Saved element boxes may differ from the image.`
          : action
            ? "No accessibility tree was saved for this phase. Full DOM inspection is available in Playwright."
            : "No saved elements at this frame. Choose an action checkpoint to inspect its saved tree.",
      );
      if (treePoint) {
        const treeAction = treePoint.action;
        for (const [index, node] of (tree?.nodes ?? []).entries()) {
          const id = this.#nodeId(treeAction, treePoint.phase, node);
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
              this.#trace.actions.indexOf(treeAction),
              "phases",
              treePoint.phase,
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
