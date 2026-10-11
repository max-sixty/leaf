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
 * The playhead is a time. The shown evidence is the latest capture at or before
 * it: stepping, a moment or a mark sets the time to that capture's own time, while
 * scrubbing and playback leave the playhead between captures and say which
 * capture is shown. Native input events carry no timestamp. A call's bar spans the
 * recorded call, its Action checkpoint is the capture taken just before input is
 * dispatched, and the image names the input only at that call's checkpoints or
 * while the playhead lies inside the call. It never implies a held key.
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
  cancelAnimation,
  nextAnimation,
  nextRender,
  cancelRender,
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
  inBaseLayer,
  live,
  nothing,
  classMap,
  styleMap,
  offered,
  render,
  repeat,
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
import { RecordingTimeline } from "./timeline.js";

// Reuse the default package’s selected WebAwesome controls, already shipped with Leaf.
await import("/vendor/webawesome.esm.js");
const { Viewer, css: imageCss } = await import("/vendor/images.esm.js");
// Dependency styles apply only inside recording widgets. Keeping them in their
// module makes the same presentation available in an offline export.
if (!document.querySelector("#lf-trace-library-styles")) {
  const styles = document.createElement("style");
  styles.id = "lf-trace-library-styles";
  styles.textContent = inBaseLayer(`@scope (lf-trace) { ${imageCss} }`);
  document.head.append(styles);
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
  before: "Before",
  action: "Next",
  after: "After",
};
// Native input methods by the gesture a reader recognizes.
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
// A call's short name: its method, or the title past a class prefix.
const callName = (action) => action.title.replace(/^[A-Z][A-Za-z]*\./, "");
const seconds = (ms) => `${(ms / 1000).toFixed(3)} s`;

// A command row owns each transport button's activation and availability.
const transport = (cls, label, icon, disabled, title = label) =>
  html`<button
    ${offered(`lf-trace-transport-button ${cls}`)}
    aria-label=${label}
    title=${title}
    ?disabled=${disabled}
  >
    ${iconTemplate(icon, "lf-action-icon")}
  </button>`;

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
    #view = null;
    #metadataPoint = null;
    #pace = "recorded";
    #pressedPlay = null;
    #bookmarks = [];
    #moments = [];
    #chosenBookmark = null;
    #boundsByScope = new Map();
    #timeline = null;
    #timelineScope = null;
    #pendingPicture = null;
    #scopeViews = new Map();
    #applyingPictureView = false;
    #picture = null;
    #pictureId = null;
    #picturePreview = false;
    #pictureScope = null;
    #resizer = null;
    #resizeFrame = 0;
    #playFrame = 0;
    #playing = false;
    #playIntent = null;
    #stopInput = null;
    // The playhead's time from the scope origin when it stands between captures,
    // after scrubbing or playback. Null when it stands on the selected capture.
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
      else if (
        event.type === "pointerdown" &&
        event.pointerType !== "touch" &&
        path.includes(this.imageViewport)
      )
        this.#inspectEvidence();
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

    // Viewer owns its container sizing; reapply the page's inspection view after
    // a resize refits the image, including a hidden tab becoming visible.
    #resize = () => {
      this.#resizeFrame ||= nextRender(() => {
        this.#resizeFrame = 0;
        if (!this.imageViewport.clientWidth) {
          this.#pause();
          if (this.#pendingPicture) this.#closePicture();
          return;
        }
        if (!this.#picture && this.#trace) this.#draw();
        if (!this.#picture?.viewed) return;
        const canvas = this.#picture.element.parentElement;
        const viewer = this.#picture.viewer;
        if (
          viewer.clientWidth === canvas.offsetWidth &&
          viewer.clientHeight === canvas.offsetHeight
        )
          return;
        this.#picture.resize();
        const image = this.#trace.images.find((image) => image.id === this.#pictureId);
        this.#applyPictureView(this.#picture, image);
        this.#imageZoom();
        this.#parts.update();
      });
    };

    connectedCallback() {
      document.addEventListener("visibilitychange", this.#visibility);
      // The shared input owner observes synchronously before drawing claims input.
      this.#stopInput ??= onUserInput(this.#reviewGesture);
      const firstConnection = once(this);
      if (firstConnection) this.#build();
      this.#resizer ??= sizeObserver(this.#resize);
      this.#resizer.observe(this.imageViewport);
      this.#timeline.connect();
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
            when: () => this.#position() > 0 || this.#cursorTime !== null,
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
            id: "trace.zoom-in",
            keys: () => (this.timeline.contains(focused()) ? ["="] : []),
            title: "zoom the timeline in",
            control: this.zoomIn,
            when: () => this.#timeline.canZoomIn,
            run: () => this.#zoom(() => this.#timeline.zoomBy(2)),
          },
          {
            id: "trace.zoom-out",
            keys: () => (this.timeline.contains(focused()) ? ["-"] : []),
            title: "zoom the timeline out",
            control: this.zoomOut,
            when: () => this.#timeline.canZoomOut,
            run: () => this.#zoom(() => this.#timeline.zoomBy(0.5)),
          },
          {
            id: "trace.zoom-fit",
            keys: () => (this.timeline.contains(focused()) ? ["0"] : []),
            title: "show the whole recording",
            control: this.zoomReset,
            when: () => this.#timeline.canZoomOut,
            run: () => this.#zoom(() => this.#timeline.fit()),
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
      this.#stopReading?.();
      this.#stopReading = null;
      this.#resizer?.disconnect();
      if (this.#resizeFrame) cancelRender(this.#resizeFrame);
      this.#resizeFrame = 0;
      this.#timeline.disconnect();
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
          key: member.getAttribute("key"),
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
        body: ".lf-trace-body",
        stage: ".lf-trace-stage",
        metadata: ".lf-trace-metadata",
        imageViewport: ".lf-trace-image-viewport",
        imageHost: ".lf-trace-images",
        imageTools: ".lf-trace-image-tools",
        imageZoomLabel: ".lf-trace-image-zoom",
        treeDetails: ".lf-trace-tree",
        treeList: ".lf-trace-nodes",
        sources: ".lf-trace-sources",
        first: ".lf-trace-first",
        play: ".lf-trace-play",
        previous: ".lf-trace-previous",
        next: ".lf-trace-next",
        zoomIn: ".lf-trace-zoom-in",
        zoomOut: ".lf-trace-zoom-out",
        zoomReset: ".lf-trace-zoom-fit",
        positionLabel: ".lf-trace-position",
        selectionLabel: ".lf-trace-selection",
        actionDetails: ".lf-trace-action",
        phaseHeading: ".lf-trace-phase",
      }))
        this[name] = this.#view.querySelector(selector);
      // Viewer owns the viewport children and the timeline module its own. The
      // position readout and zoom status change during playback and pinching, so
      // they are written directly. None of these regions holds a Lit child part.
      this.missingImage = el("p", "lf-trace-missing-image");
      this.inputBadge = el("span", "lf-trace-input-badge");
      this.inputPoint = el("span", "lf-trace-input-point");
      this.inputBadge.hidden = this.inputPoint.hidden = true;
      this.imageViewport.append(this.missingImage, this.inputBadge, this.inputPoint);
      this.#timeline = new RecordingTimeline(this.timeline, {
        quoted: quoted(this),
        onSeek: (time, final) => this.#seek(time, final),
        onPick: (lane, id, time) => this.#pick(lane, id, time),
        onUserPan: () => {
          if (this.#playing) this.#pause();
        },
      });
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
            title: "first capture",
            control: this.first,
            run: () => this.#navigate(this.#items().at(0)?.id ?? null),
          },
          {
            id: "trace.last",
            keys: ["End"],
            title: "last capture",
            run: () => this.#navigate(this.#items().at(-1)?.id ?? null),
          },
        ]);
    }

    // Review gestures belong to evidence, independently of navigation layout.
    #inspect(event) {
      const path = event.composedPath();
      if (path.includes(this.metadata)) this.#pause();
      else if (
        event.type === "lf-inspect" ||
        path.includes(this.imageViewport) ||
        path.includes(this.imageTools)
      )
        this.#inspectEvidence();
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
      return seconds(value - this.#origins.get(stream).start);
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
    #itemsCache = null;
    #items() {
      const key = `${this.#trace?.archive.sha256}:${this.#scope}`;
      if (this.#itemsCache?.key === key) return this.#itemsCache.points;
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
      this.#chosenBookmark = destination === point?.id ? moment.index : null;
      this.#selected = point?.id ?? null;
      this.#cursorTime = null;
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
      this.#cursorTime = null;
      this.#draw();
      this.#revealTime("center");
    }
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
    #pointAt(elapsed) {
      const items = this.#items();
      const time = this.#bounds().start + elapsed;
      return items.findLast((point) => point.timestamp <= time) ?? items[0];
    }
    #seek(elapsed, final) {
      if (this.#playing) this.#pause(false);
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
    #pick(lane, id, time) {
      if (lane === "moments") {
        const moment = this.#moments.find((moment) => String(moment.number) === id);
        if (moment?.scope) this.#visitMoment(moment.target, moment.index);
        return;
      }
      const action = this.#trace.actions.find((action) => action.id === id);
      if (!action) return;
      const phases = this.#phases(action);
      const at = (phase) =>
        (action.phases[phase]?.timestamp ??
          (phase === "end" ? action.endTime : action.startTime)) - this.#bounds().start;
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
    #pause(draw = true) {
      if (!this.#playing && !this.#scrubbing) return;
      // A playing film is continuous mechanical motion, outside resting proof.
      // Pausing keeps the playhead where it stands.
      if (this.#playFrame) cancelAnimation(this.#playFrame);
      this.#playFrame = 0;
      this.#playing = false;
      if (this.#scrubbing) {
        this.#scrubbing = false;
        dragging(this, false);
      }
      if (draw) this.#draw();
    }
    #startPlayback() {
      const points = this.#items();
      if (points.length < 2) return;
      const origin = this.#bounds().start;
      const end = points.at(-1).timestamp;
      const selected = this.#point() ?? points[0];
      // Playback starts at the playhead and includes every original capture.
      let time =
        this.#cursorTime !== null ? origin + this.#cursorTime : selected.timestamp;
      if (time >= end) time = points[0].timestamp;
      this.#playing = true;
      this.#chosenBookmark = null;
      this.#cursorTime = time - origin;
      this.#selected = this.#pointAt(this.#cursorTime).id;
      this.#draw();
      let previousTick = performance.now();
      const intervals = mergeIntervals([
        ...this.#inputActions().map((action) => [
          action.startTime - 200,
          (action.endTime ?? action.startTime) + 450,
        ]),
        ...this.#scopeMoments().map((moment) => {
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
            this.#pace === "review" ? intervals : null,
          ),
        );
        previousTick = now;
        this.#cursorTime = time - origin;
        const point = this.#pointAt(this.#cursorTime);
        if (point.id !== this.#selected) {
          this.#selected = point.id;
          this.#draw();
        } else this.#drawTime();
        this.#revealTime("page");
        if (time === end) this.#pause();
        else this.#playFrame = nextAnimation(tick);
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
      this.#itemsCache = null;
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
        this.#timelineScope = null;
        this.#closePicture();
        this.#images.clear();
        this.#scopeViews.clear();
        this.#metadataPoint = null;
        this.#treePlaces.clear();
        this.#treeScope = null;
        this.#scope = null;
        this.#selected = null;
        this.#cursorTime = null;
        this.#chosenBookmark = null;
        setChildren(this.imageViewport, [
          this.missingImage,
          this.inputBadge,
          this.inputPoint,
        ]);
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
      // A peer may have chosen a shared result while this source was arriving.
      // The peer's authored bookmark is the mechanical selection authority.
      const comparison = this.#comparison();
      if (this.#trace && comparison && !quoted(this)) {
        const peer = [...authoredScope(this).querySelectorAll("lf-trace")].find(
          (peer) =>
            peer !== this &&
            peer.#comparison() === comparison &&
            peer.#chosenBookmark !== null,
        );
        const key = peer?.#bookmarks[peer.#chosenBookmark]?.key;
        const match = key && this.#bookmarks.find((moment) => moment.key === key);
        if (match && this.#targets.has(match.target))
          this.#reveal(match.target, match.index);
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
        cursorTime: this.#cursorTime,
      });
      this.#cancelPicture();
      this.#scope = scope;
      const saved = this.#scopeView();
      this.#selected = saved.selected ?? null;
      this.#cursorTime = saved.cursorTime ?? null;
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
      this.#cursorTime = null;
      if (target.node) keeps(this.treeDetails, "open", "");
      this.#draw();
      this.#revealTime("center");
    }

    async #visitMoment(id, bookmark) {
      const mayArrive = retainUserIntent();
      this.#reveal(id, bookmark);
      const comparison = this.#comparison();
      const key = this.#bookmarks[bookmark]?.key;
      // A semantic pairing is authored explicitly; equal times and matching
      // labels do not establish it. Set each peer's own captured coordinate,
      // without taking focus or scrolling a hidden recording into the page.
      if (comparison && key && !quoted(this)) {
        for (const peer of authoredScope(this).querySelectorAll("lf-trace")) {
          if (peer === this || peer.#comparison() !== comparison) continue;
          const match = peer.#bookmarks.find((moment) => moment.key === key);
          if (match && peer.#targets.has(match.target))
            peer.#reveal(match.target, match.index);
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
          (target?.phase === "end"
            ? target?.action?.endTime
            : target?.action?.startTime),
      };
    }
    #scopeMoments() {
      return this.#moments.filter(
        (moment) => moment.scope === this.#scope || moment.stream === this.#scope,
      );
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
      const point = this.#point();
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
        this.inputBadge,
        this.inputPoint,
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

    #inputLabel(action) {
      if (action.input.key) return `Press ${action.input.key}`;
      return (
        INPUT_NAMES[action.method] ??
        action.method[0].toUpperCase() + action.method.slice(1)
      );
    }

    #inputActions() {
      return this.#actions().filter((action) => action.input);
    }

    // The input the shown evidence belongs to: the selected checkpoint's own
    // input call, or an input call the playhead stands inside. Nothing else.
    #currentInput() {
      const point = this.#point();
      if (point?.action?.input && INPUT_PHASES[point.phase])
        return { action: point.action, phase: point.phase };
      const time = this.#playheadTime();
      if (time === null) return null;
      const action = this.#inputActions().find(
        (action) =>
          action.startTime <= time && time <= (action.endTime ?? action.startTime),
      );
      return action ? { action, phase: null } : null;
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
      const point = this.#point();
      const current = this.#currentInput();
      const action = current?.action;
      const image = this.#trace?.images.find((image) => image.id === this.#pictureId);
      const imageReady = point && image && this.#evidence(point).image?.id === image.id;
      keepsHidden(this.inputBadge, !action || !imageReady);
      const span = action
        ? `${this.#time(action.startTime, action.stream)}–${this.#time(action.endTime ?? action.startTime, action.stream)}`
        : "";
      keepsText(
        this.inputBadge,
        action
          ? current.phase
            ? `${INPUT_PHASES[current.phase]}: ${this.#inputLabel(action)}`
            : `During: ${this.#inputLabel(action)}`
          : "",
      );
      keeps(
        this.inputBadge,
        "title",
        action
          ? `${this.#inputLabel(action)}${action.input.selector ? ` · ${action.input.selector}` : ""} · call ${span}. The Input checkpoint is captured just before dispatch; the exact input time is not recorded.`
          : null,
      );
      // A pointer target belongs to the checkpoints taken before dispatch.
      const coordinate = action?.input.point;
      const viewport = action?.input.viewport;
      const visible =
        coordinate &&
        viewport &&
        (current.phase === "before" || current.phase === "action") &&
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

    // The timeline model: every mark of the scope at its own recorded time.
    #timelineModel() {
      const bounds = this.#bounds();
      const origin = bounds.start;
      const point = this.#point();
      const playhead = this.#playheadTime();
      const inside = (action) =>
        playhead !== null &&
        action.startTime <= playhead &&
        playhead <= (action.endTime ?? action.startTime);
      const span = (action) =>
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
          const input = action.phases.action;
          inputs.push({
            ...mark,
            label: action.input.key ?? this.#inputLabel(action),
            title: `${this.#inputLabel(action)} · call ${span(action)}${input ? ` · Input checkpoint ${this.#time(input.timestamp, action.stream)}` : ""}`,
          });
        } else
          calls.push({
            ...mark,
            label: callName(action),
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
        kind: item.image ? "frame" : "checkpoint",
        current: item.id === this.#selected,
      }));
      return {
        signature: `${this.#trace.archive.sha256}:${this.#scope}:${moments.map((moment) => `${moment.number}@${moment.time}`).join(",")}`,
        duration: Math.max(1, bounds.end - origin),
        time: playhead === null ? 0 : playhead - origin,
        moments,
        inputs,
        calls,
        captures,
      };
    }

    #revealTime(mode) {
      const time = this.#playheadTime();
      if (time !== null) this.#timeline.reveal(time - this.#bounds().start, mode);
    }

    #zoom(change) {
      this.#pause();
      change();
      paintKeys();
    }

    // The playhead and its readout, without redrawing evidence.
    #drawTime() {
      const point = this.#point();
      const playhead = this.#playheadTime();
      if (this.#trace && playhead !== null)
        this.#timeline.setTime(playhead - this.#bounds().start);
      keepsText(
        this.positionLabel,
        playhead === null ? "No recorded points" : this.#time(playhead, this.#stream()),
      );
      const selectedMoments = this.#moments.filter(
        (moment) =>
          this.#selected && this.#destination(moment.target) === this.#selected,
      );
      const selectedMoment =
        selectedMoments.find((moment) => moment.index === this.#chosenBookmark) ??
        selectedMoments[0];
      const description = selectedMoment
        ? `Moment ${selectedMoment.number} · ${selectedMoment.label}`
        : point?.action
          ? `${PHASES[point.phase]}${["before", "action", "after"].includes(point.phase) ? " checkpoint" : ""} · ${point.action.title}`
          : point
            ? "Captured frame"
            : "";
      // Between captures, say which capture is shown and when it was taken.
      const between =
        point && playhead !== null && Math.abs(playhead - point.timestamp) >= 0.5;
      const selection = between
        ? `Showing ${point.image ? "frame" : "checkpoint"} from ${this.#time(point.timestamp, this.#stream())} · ${description}`
        : description;
      keepsText(this.selectionLabel, selection);
      keeps(this.selectionLabel, "title", selection);
      this.#drawInput();
    }

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

    #viewState() {
      const items = this.#items();
      const position = Math.max(
        0,
        items.findIndex((point) => point.id === this.#selected),
      );
      const point = items[position];
      const { image, tree, treePoint } = this.#evidence(point);
      return {
        items,
        position,
        point,
        image,
        tree,
        treePoint,
        extent: this.#imageSizes.get(this.#scope),
        choices: this.#trace ? this.#scopeChoices() : [],
        origin: this.#origins.get(this.#stream()),
        available: this.#scopeMoments(),
        unavailable: this.#moments.filter((moment) => !moment.scope),
        rows: treePoint
          ? (tree?.nodes ?? []).map((node) => ({
              node,
              id: this.#nodeId(treePoint.action, treePoint.phase, node),
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
      treePoint,
      extent,
      choices,
      origin,
      available,
      unavailable,
      rows,
    }) {
      const trace = this.#trace;
      const q = quoted(this);
      const action = point?.action ?? null;
      // A filmstrip frame has no action. The previous action's fields stay in
      // place, hidden, so an inspected metadata scroll position is not clamped.
      const metadataPoint = this.#metadataPoint;
      const metadataAction = metadataPoint?.action;
      const committed = trace?.images.find((item) => item.id === this.#pictureId);
      const caption = committed
        ? `${this.#targets.get(this.#id("image", committed.id)).label}${this.#picturePreview ? " · First capture after this point" : ""}`
        : this.#pendingPicture
          ? "Loading captured image…"
          : "No captured image at this point.";
      const playLabel = this.#playing ? "Pause" : "Play";
      const moments = this.#moments;
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
                      @click=${() => this.#visitMoment(moment.target, moment.index)}
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
          </div>
          <div class="lf-trace-body" ?hidden=${!trace}>
            <div
              class="lf-trace-evidence"
              @click=${{ handleEvent: (event) => this.#inspect(event), capture: true }}
            >
              <div class="lf-trace-stage">
                <div class="lf-trace-toolbar">
                  <div class="lf-trace-transport">
                    ${transport("lf-trace-first", "Start", "start", q || !items.length)}
                    <button
                      ${offered("lf-trace-transport-button lf-trace-play")}
                      aria-label=${playLabel}
                      title=${playLabel}
                      data-playing=${this.#playing ? "" : nothing}
                      ?disabled=${q || items.length < 2}
                      @pointerdown=${(event) => {
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
                        handleEvent: (event) => {
                          const pressed = this.#pressedPlay;
                          this.#playIntent =
                            pressed &&
                            event.detail > 0 &&
                            event.pointerId === pressed.pointerId
                              ? pressed.pause
                              : null;
                          this.#pressedPlay = null;
                        },
                        capture: true,
                      }}
                    >
                      ${iconTemplate("play", "lf-action-icon")}${iconTemplate(
                        "pause",
                        "lf-action-icon",
                      )}<span>${playLabel}</span>
                    </button>
                    ${transport("lf-trace-previous", "Previous", "previous", q, "Previous capture")}
                    ${transport("lf-trace-next", "Next", "next", q, "Next capture")}
                  </div>
                  <div class="lf-trace-position-row">
                    <span class="lf-trace-position"></span
                    ><span class="lf-trace-selection"></span>
                  </div>
                  <div
                    class="lf-trace-zoom-controls"
                    role="group"
                    aria-label="Timeline zoom"
                  >
                    ${transport("lf-trace-zoom-out", "Zoom out", "subtract", q)}
                    ${transport("lf-trace-zoom-in", "Zoom in", "add", q)}
                    ${transport("lf-trace-zoom-fit", "Whole recording", "fit", q)}
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
                      @change=${(event) => (this.#pace = event.currentTarget.value)}
                    >
                      <option value="recorded">Recorded (1×)</option>
                      <option value="review">Review (0.35–3×)</option>
                    </select></label
                  >
                </div>
                <div
                  class="lf-trace-timeline"
                  tabindex=${q ? -1 : 0}
                  role="group"
                  aria-label="Recording timeline"
                  aria-description="Left and Right step through captures. Home and End reach the first and last capture."
                  ?hidden=${!trace || !items.length}
                ></div>
                <div class="lf-trace-images">
                  <div
                    class="lf-trace-image-viewport"
                    style=${styleMap({
                      aspectRatio: extent ? `${extent.width} / ${extent.height}` : undefined,
                      maxWidth: extent ? `${extent.width}px` : undefined,
                    })}
                    ?data-sized=${!!extent}
                  ></div>
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
              </div>
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
                  <summary>Saved elements</summary>
                  <p class="lf-trace-tree-clock">
                    ${tree
                      ? `${tree.nodes.length} elements · ${PHASES[treePoint.phase]} checkpoint at ${this.#time(tree.timestamp, treePoint.action.stream)}. Saved element boxes may differ from the image.`
                      : action
                        ? "No accessibility tree was saved for this phase. Full DOM inspection is available in Playwright."
                        : "No saved elements at this frame. Choose an action checkpoint to inspect its saved tree."}
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
                  ${trace?.streams.length > 1
                    ? `${clockLabel} · each stream has its own clock`
                    : clockLabel}
                </p>
                <p class="lf-trace-readout">
                  ${!trace
                    ? "Waiting for a Playwright recording."
                    : !items.length
                      ? "No recorded checkpoints or frames in this recording scope."
                      : `Capture ${position + 1} of ${items.length}`}
                </p>
                <p class="lf-trace-action">${metadataAction?.title ?? ""}</p>
                <h3 class="lf-trace-phase">
                  ${metadataAction
                    ? `${PHASES[metadataPoint.phase]}${metadataAction.phases[metadataPoint.phase] ? " checkpoint" : ""} · ${this.#time(metadataPoint.timestamp, metadataAction.stream)}`
                    : ""}
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

    #draw() {
      if (!this.#items().some((point) => point.id === this.#selected))
        this.#selectDefault();
      const view = this.#viewState();
      const { point, image, treePoint, rows } = view;
      this.#selected = point?.id ?? null;
      if (point?.action) this.#metadataPoint = point;
      const treeScope = treePoint
        ? this.#phaseId(treePoint.action, treePoint.phase)
        : null;
      const treeChanged = treeScope !== this.#treeScope;
      const treeRegion = readingRegion(compoundReadingRegionId(this, "saved-elements"));
      // Saved trees replace each other under their archive phase identity. Keep
      // each reading through empty frames and returns using Leaf's place owner,
      // independent of the recreated rows.
      if (treeChanged && this.#treeScope && this.treeDetails.open)
        this.#treePlaces.set(this.#treeScope, capturePlace(treeRegion));
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
      this.#drawTimeline();
      this.#imageZoom();
      this.#drawTime();
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
      if (treePoint && this.treeDetails.open)
        for (const [index, { id }] of rows.entries())
          add(id, this.treeList.children[index], this.#targets.get(id).label, [
            "actions",
            this.#trace.actions.indexOf(treePoint.action),
            "phases",
            treePoint.phase,
            "tree",
            "nodes",
            index,
          ]);
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
