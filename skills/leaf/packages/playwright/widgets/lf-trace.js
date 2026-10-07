/* Review one immutable Playwright recording. Playwright owns capture and its clocks;
 * Leaf owns comments. Browsing is local mechanical state, not an event-log fold.
 * Action phases, native images, and saved-tree nodes have archive-scoped coordinates.
 * A phase prefers its checkpoint PNG, otherwise the latest same-page frame at or
 * before that time. Pixel comments name the actual image; semantic comments name a
 * saved tree path. Sequential image/tree captures never imply exact pixel alignment.
 * Once drawn, the recording takes its content's height and the page is its only
 * scroller; a stated height only holds the page's room until then (`x-height`). This
 * reverses the first version's decision to scroll the evidence inside a frame of the
 * authored height, which left a page scrolling inside the page. The stepper instead
 * sticks at the top of the page's band while the recording is on screen (theme.css),
 * and the page selector and frames row above it scroll away. Evidence comes first, in
 * a box shared at one zoom by the images of one viewport, and optional metadata
 * follows it.
 * Stepping keeps the evidence where the reader sees it, except that evidence the stuck
 * stepper covers starts again at the stepper's foot (`#navigate`). One cursor
 * walks native action checkpoints chronologically; captured frames can join that
 * same timeline. Initial selection prefers its first nonempty saved tree, then
 * its first image; empty earlier stops stay navigable. Following a visual part restores its exact
 * stop and page. */
import {
  cancelRender,
  commands,
  effectiveScroller,
  keepsHidden,
  el,
  holdFocus,
  keeps,
  keepsText,
  once,
  offer,
  paintKeys,
  projectData,
  quoted,
  registerVisualParts,
  scopedMediaUrl,
  nextRender,
  setChildren,
  sizeObserver,
  watchData,
} from "/runtime/widget-api.js";

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
  return origins;
}
// The box each image is drawn in, by image id, and each page's box for a stop with no
// image, by page id: that of its most frequent shape. A page's checkpoints are whole
// captures of its viewport, so they alone say which shapes it took: checkpoints within
// 2% of one aspect are one viewport. A filmstrip frame is Playwright's smaller, and not
// always same-shaped, encoding of whatever viewport the page had then, so it joins the
// shape of the checkpoint nearest it in time; a page with no checkpoints groups its
// frames by their own shape. The images of one shape share its widest member's width,
// so no frame's pixel width becomes a different zoom at a timeline stop, in a box as
// tall as the tallest of them at that width, so the caption and everything below stand
// still from one stop to the next. A viewport of another shape is a box of its own, so
// a portrait capture never makes a landscape one stand in blank room.
function imageBoxes(images) {
  const shapes = [];
  const shapeOf = (image) => {
    const ratio = image.width / image.height;
    let shape = shapes.find(
      (other) =>
        other.pageId === image.pageId && Math.abs(other.ratio / ratio - 1) < 0.02,
    );
    if (!shape) shapes.push((shape = { pageId: image.pageId, ratio, members: [] }));
    return shape;
  };
  const checkpoints = images.filter((image) => image.kind === "checkpoint");
  for (const image of checkpoints) shapeOf(image).members.push(image);
  for (const image of images) {
    if (image.kind === "checkpoint") continue;
    const distance = (other) => Math.abs(other.timestamp - image.timestamp);
    const nearest = checkpoints
      .filter((other) => other.pageId === image.pageId)
      .reduce(
        (best, other) => (!best || distance(other) < distance(best) ? other : best),
        null,
      );
    const shape = nearest
      ? shapes.find((candidate) => candidate.members.includes(nearest))
      : shapeOf(image);
    shape.members.push(image);
  }
  const boxes = new Map();
  const counts = new Map();
  for (const { pageId, members } of shapes) {
    const width = Math.max(...members.map((image) => image.width));
    const height = Math.max(
      ...members.map((image) => Math.ceil((image.height * width) / image.width)),
    );
    for (const image of members) boxes.set(image.id, { width, height });
    if (members.length > (counts.get(pageId) ?? 0)) {
      counts.set(pageId, members.length);
      boxes.set(pageId, { width, height });
    }
  }
  return boxes;
}
const nodeName = (node) =>
  [node.role, node.name || node.text].filter(Boolean).join(" · ") ||
  "Unnamed saved element";

function selector(name, label, entries) {
  const select = offer("select", "lf-trace-select");
  select.name = name;
  select.setAttribute("aria-label", label);
  for (const [value, title] of entries) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = title;
    select.append(option);
  }
  return select;
}

customElements.define(
  "lf-trace",
  class extends HTMLElement {
    #snapshot = null;
    #origins = new Map();
    #imageBoxes = new Map();
    #trace = null;
    #page = null;
    #selected = null;
    #intermediates = false;
    #resized = null;
    #releaseFrame = 0;
    #scrolled = null;
    #keys = null;
    #parts = null;
    #inventory = [];
    #targets = new Map();
    #images = new Map();
    #nodes = new Map();

    connectedCallback() {
      const firstConnection = once(this);
      if (firstConnection) this.#build();
      if (!quoted(this))
        this.#keys ??= commands(this, "In a Playwright recording", [
          {
            id: "trace.previous",
            keys: ["ArrowLeft"],
            title: "previous timeline point",
            control: this.previous,
            when: () => this.#position() > 0,
            run: () => this.#step(-1),
          },
          {
            id: "trace.next",
            keys: ["ArrowRight"],
            title: "next timeline point",
            control: this.next,
            when: () => this.#position() < this.#items().length - 1,
            run: () => this.#step(1),
          },
          {
            id: "trace.frames",
            title: () => `${this.#intermediates ? "hide" : "show"} intermediate frames`,
            control: this.framesToggle,
            run: () => this.framesToggle.click(),
            when: () => this.#checkpoints().length > 0 && this.#frames().length > 0,
          },
        ]);
      // A new width redraws every height, so the room held for an earlier one is
      // released to what the reader's place still needs. After the delivery, since
      // the release resizes the element observed.
      if (!this.#resized) {
        this.#resized = sizeObserver(() => {
          this.#releaseFrame ||= nextRender(() => {
            this.#releaseFrame = 0;
            this.#release();
          });
        });
        this.#resized.observe(this);
      }
      // Held room serves the place the reader stood in when a change shortened the
      // page; once they scroll away from it, what lies below them is given back too.
      // Capture hears a box that scrolls as well as the root, whose scrollend never
      // bubbles.
      if (!this.#scrolled) {
        this.#scrolled = new AbortController();
        document.addEventListener("scrollend", () => this.#release(), {
          capture: true,
          passive: true,
          signal: this.#scrolled.signal,
        });
      }
      if (firstConnection) watchData(this, "trace", (snapshot) => this.#show(snapshot));
    }

    disconnectedCallback() {
      this.#resized?.disconnect();
      this.#resized = null;
      cancelRender(this.#releaseFrame);
      this.#releaseFrame = 0;
      this.#scrolled?.abort();
      this.#scrolled = null;
      // Element command scopes leave with their element; reconnect keeps the declaration.
    }

    #build() {
      this.pageSelect = selector(`${this.id}-page`, "Recorded page or API stream", []);
      this.framesToggle = offer("input", "lf-trace-frames", undefined, "checkbox");
      this.framesToggle.name = `${this.id}-frames`;
      const framesLabel = document.createElement("label");
      framesLabel.className = "lf-trace-frames-label";
      framesLabel.append(this.framesToggle, "Show intermediate frames");
      this.viewer = offer("a", "lf-trace-viewer", "Open in Playwright");
      this.viewer.target = "_blank";
      this.viewer.rel = "noopener noreferrer";
      this.previous = offer("button", "lf-btn lf-trace-previous", "Previous");
      this.next = offer("button", "lf-btn lf-trace-next", "Next");
      this.slider = offer("input", "lf-trace-slider", undefined, "range");
      this.slider.name = `${this.id}-position`;
      this.slider.step = "1";
      this.slider.min = "0";
      this.slider.setAttribute("aria-label", "Timeline position");
      // The stepper sticks over the evidence (theme.css); the choices above it
      // scroll away with the page.
      this.stepper = offer("div", "lf-trace-stepper");
      this.stepper.append(this.previous, this.slider, this.next);
      const choices = offer("div", "lf-trace-choices");
      choices.append(this.pageSelect, framesLabel, this.viewer);
      this.clock = el("p", "lf-trace-clock");
      this.readout = el("p", "lf-trace-readout", "Waiting for a Playwright recording.");
      this.actionDetails = el("p", "lf-trace-action");
      this.phaseHeading = el("h3", "lf-trace-phase");
      this.error = el("p", "lf-trace-error");
      this.imageHost = el("div", "lf-trace-images");
      // Where no image is captured, the box an image would fill stands empty and the
      // message takes the caption's row, so what follows stays where it was.
      this.missingImage = el("figure", "lf-trace-image lf-trace-missing-image");
      this.missingBox = el("div", "lf-trace-frame");
      this.missingNote = el("figcaption", "lf-trace-caption");
      this.missingImage.append(this.missingBox, this.missingNote);
      this.imageHost.append(this.missingImage);
      this.treeDetails = document.createElement("details");
      this.treeDetails.className = "lf-trace-tree";
      this.treeSummary = document.createElement("summary");
      this.treeSummary.textContent = "Saved elements";
      this.treeClock = el("p", "lf-trace-tree-clock");
      this.treeList = el("ul", "lf-trace-nodes");
      this.treeDetails.append(this.treeSummary, this.treeClock, this.treeList);
      this.body = el("div", "lf-trace-body");
      // Evidence owns the reading origin. Optional metadata follows it, so a
      // frame/checkpoint transition cannot move the pixels being compared.
      this.body.append(
        this.imageHost,
        this.clock,
        this.readout,
        this.actionDetails,
        this.phaseHeading,
        this.error,
        this.treeDetails,
      );
      // Room held below the metadata across a step near the page's end (`#navigate`).
      this.held = el("div", "lf-trace-held");
      this.body.append(this.held);
      this.append(choices, this.stepper, this.body);
      this.#parts = registerVisualParts(this, () => this.#inventory, {
        label: (id) => this.#targets.get(id)?.label ?? null,
        reveal: (id) => this.#reveal(id),
      });
      this.treeDetails.addEventListener("toggle", () => this.#draw());
      // Folding the saved elements keeps their summary under the press, which the
      // browser's own toggle would let the page's end pull down.
      this.treeSummary.addEventListener("click", (event) => {
        if (event.defaultPrevented) return;
        event.preventDefault();
        const top = this.treeSummary.getBoundingClientRect().top;
        this.treeDetails.open = !this.treeDetails.open;
        this.#keep(this.treeSummary, top);
      });
      if (quoted(this)) {
        this.previous.disabled = true;
        this.next.disabled = true;
        return;
      }
      this.slider.addEventListener("input", () => {
        this.#navigate(this.#items()[Number(this.slider.value)]?.id ?? null);
      });
      this.pageSelect.addEventListener("change", () => {
        this.#page = this.pageSelect.value;
        this.#navigate(null);
      });
      this.framesToggle.addEventListener("change", () => {
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
    #actions() {
      if (!this.#trace || !this.#page) return [];
      const page = this.#trace.pages.find((page) => page.id === this.#page);
      if (page)
        return this.#trace.actions.filter(
          (action) =>
            action.stream === page.stream &&
            (action.pageId === page.id ||
              Object.values(action.phases).some((phase) => phase.pageId === page.id)),
        );
      return this.#trace.actions.filter(
        (action) =>
          `${action.stream}-calls` === this.#page &&
          action.pageId === null &&
          !Object.keys(action.phases).length,
      );
    }
    #frames() {
      return (
        this.#trace?.images
          .filter((image) => image.pageId === this.#page && image.kind === "frame")
          .sort((a, b) => a.timestamp - b.timestamp) ?? []
      );
    }
    #checkpoints() {
      const points = [];
      for (const action of this.#actions())
        for (const phase of this.#phases(action)) {
          const checkpoint = action.phases[phase];
          const page = checkpoint?.pageId ?? action.pageId ?? `${action.stream}-calls`;
          if (page !== this.#page) continue;
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
      if (!image && pageId)
        image =
          this.#trace.images
            .filter(
              (image) =>
                image.pageId === pageId &&
                image.stream === action.stream &&
                image.kind === "frame" &&
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
    // Stepping replaces the evidence where the reader sees it. Where the stuck
    // stepper covers the evidence's top, or all of it while the reader is down in
    // the saved elements, the new point's evidence starts at the stepper's foot: the
    // one scroll at which the stuck stepper also meets its place in flow, so it stays
    // under the gesture, and after which later steps move nothing. Otherwise the new
    // evidence starts where the old one did. A stepper parked at the recording's
    // foot, the whole recording scrolled past, covers nothing.
    #navigate(id) {
      const before = this.imageHost.getBoundingClientRect().top;
      const stepper = this.stepper.getBoundingClientRect();
      const stuck = this.body.getBoundingClientRect().bottom > stepper.bottom + 1;
      const target = stuck && before < stepper.bottom - 1 ? stepper.bottom : before;
      this.#selected = id;
      this.#draw();
      this.#keep(this.imageHost, target);
    }
    // Scrolls `element`, after a change the reader made, back to `top` on screen. A
    // change that shortens what follows (a captured frame has no action or saved
    // elements; folded saved elements have no rows) would, near the page's end, pull
    // everything down; the body then holds the room that place needs (`held`),
    // released as soon as a later draw or width no longer needs it.
    #keep(element, top) {
      const move = element.getBoundingClientRect().top - top;
      if (Math.abs(move) < 1) return;
      const scroller = effectiveScroller(this);
      const room = this.#room(scroller);
      if (move > room) this.#hold(this.#heldRoom() + move - room);
      scroller.scrollBy({ top: move, behavior: "instant" });
      this.#release();
    }
    #keepStyle(element, name, value) {
      if (element.style.getPropertyValue(name) === (value ?? "")) return;
      if (value) element.style.setProperty(name, value);
      else element.style.removeProperty(name);
    }
    #room(scroller = effectiveScroller(this)) {
      return scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop;
    }
    #heldRoom() {
      return Number.parseFloat(this.held.style.blockSize) || 0;
    }
    #hold(px) {
      const size = px >= 1 ? `${Math.ceil(px)}px` : "";
      if (this.held.style.blockSize !== size) this.held.style.blockSize = size;
    }
    // The held room shrinks by whatever the page has below the reader, which never
    // shortens it under the scroll position it holds.
    #release() {
      const held = this.#heldRoom();
      if (!held) return;
      const room = this.#room();
      if (room >= 1) this.#hold(held - room);
    }
    #step(delta) {
      const items = this.#items();
      const next = Math.max(0, Math.min(items.length - 1, this.#position() + delta));
      this.#navigate(items[next]?.id ?? null);
    }
    #phases(action) {
      return Object.keys(action.phases).length
        ? Object.keys(PHASES).filter((phase) => action.phases[phase])
        : action.endTime === null
          ? ["start"]
          : ["start", "end"];
    }

    #show(snapshot) {
      const restore = holdFocus(this);
      const oldArchive = this.#trace?.archive.sha256;
      this.#snapshot = snapshot;
      this.#trace = snapshot?.value ?? null;
      this.#origins = this.#trace ? streamOrigins(this.#trace) : new Map();
      this.#imageBoxes = imageBoxes(this.#trace?.images ?? []);
      this.classList.toggle("lf-rendered", this.#trace !== null);
      if (oldArchive !== this.#trace?.archive.sha256) {
        this.#images.clear();
        this.#nodes.clear();
        this.#page = null;
        this.#selected = null;
        this.#intermediates = false;
        setChildren(this.imageHost, [this.missingImage]);
        setChildren(this.treeList, []);
      }
      if (this.#trace) {
        const choices = this.#trace.pages.map((page) => [
          page.id,
          this.#pageLabel(page.id),
        ]);
        for (const [index, stream] of this.#trace.streams.entries()) {
          if (
            this.#trace.actions.some(
              (action) =>
                action.stream === stream.id &&
                action.pageId === null &&
                !Object.keys(action.phases).length,
            )
          )
            choices.push([
              `${stream.id}-calls`,
              `Stream ${index + 1} · API calls without a page`,
            ]);
        }
        this.#selectOptions(this.pageSelect, choices);
        if (!choices.some(([id]) => id === this.#page))
          this.#page = choices[0]?.[0] ?? null;
        keeps(this.viewer, "href", this.#trace.viewerUrl);
        this.#indexTargets();
      } else {
        this.#targets.clear();
        this.#selectOptions(this.pageSelect, []);
      }
      this.#draw();
      restore?.(this.pageSelect);
    }

    #selectOptions(select, choices) {
      const prior = new Map(
        [...select.options].map((option) => [option.value, option]),
      );
      setChildren(
        select,
        choices.map(([value, label]) => {
          const option = prior.get(value) ?? document.createElement("option");
          keeps(option, "value", value);
          keepsText(option, label);
          return option;
        }),
      );
    }

    #indexTargets() {
      this.#targets.clear();
      for (const action of this.#trace.actions) {
        const page =
          action.pageId ??
          Object.values(action.phases)[0]?.pageId ??
          `${action.stream}-calls`;
        this.#targets.set(this.#id("action", action.id), {
          action,
          page,
          phase: this.#phases(action)[0],
          label: action.title,
        });
        for (const phase of this.#phases(action)) {
          this.#targets.set(this.#phaseId(action, phase), {
            action,
            page: action.phases[phase]?.pageId ?? page,
            phase,
            label: `${action.title} · ${PHASES[phase]}`,
          });
          for (const node of action.phases[phase]?.tree?.nodes ?? [])
            this.#targets.set(this.#nodeId(action, phase, node), {
              action,
              page: action.phases[phase]?.pageId ?? page,
              phase,
              node,
              label: `${action.title} · ${PHASES[phase]} · ${nodeName(node)} · path ${node.path}`,
            });
        }
      }
      for (const image of this.#trace.images)
        this.#targets.set(this.#id("image", image.id), {
          image,
          page: image.pageId,
          label: `${this.#pageLabel(image.pageId)} · ${image.kind === "frame" ? "Captured frame" : `${PHASES[image.phase]} checkpoint`} · ${this.#time(image.timestamp, image.stream)}`,
        });
    }

    #reveal(id) {
      const target = this.#targets.get(id);
      if (!target) return;
      this.#page = target.page;
      if (target.image?.kind === "frame") {
        this.#intermediates = true;
        this.#selected = id;
      } else {
        const action =
          target.action ??
          this.#trace.actions.find(
            (action) =>
              action.stream === target.image.stream &&
              action.callId === target.image.callId &&
              action.phases[target.image.phase]?.imageId === target.image.id,
          );
        if (!action) return;
        this.#selected = this.#phaseId(action, target.phase ?? target.image.phase);
      }
      if (target.node) keeps(this.treeDetails, "open", "");
      this.#draw();
    }

    #draw() {
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
      this.#selected = point?.id ?? null;
      this.pageSelect.value = this.#page ?? "";
      this.framesToggle.checked =
        this.#frames().length > 0 &&
        (this.#intermediates || !this.#checkpoints().length);
      keeps(this.pageSelect, "disabled", !this.#trace || quoted(this) ? "" : null);
      keeps(
        this.framesToggle,
        "disabled",
        !this.#frames().length || !this.#checkpoints().length || quoted(this)
          ? ""
          : null,
      );
      keeps(this.slider, "max", String(Math.max(0, items.length - 1)));
      this.slider.value = String(position);
      keeps(this.slider, "disabled", items.length < 2 || quoted(this) ? "" : null);
      keeps(
        this.slider,
        "aria-valuetext",
        `Timeline point ${items.length ? position + 1 : 0} of ${items.length}`,
      );
      keepsHidden(this.viewer, !this.#trace);
      keepsHidden(this.clock, !this.#trace);
      const selectedStream =
        this.#trace?.pages.find((page) => page.id === this.#page)?.stream ??
        this.#trace?.streams.find((stream) => `${stream.id}-calls` === this.#page)?.id;
      const origin = this.#origins.get(selectedStream);
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
      keepsHidden(this.actionDetails, !hasAction);
      keepsHidden(this.phaseHeading, !hasAction);
      const { image, tree } = this.#evidence(point);
      let action = null;
      let phase = null;
      let wanted = null;
      if (point?.action) {
        action = point.action;
        phase = action.phases[point.phase];
        wanted = point.timestamp;
        keepsText(this.actionDetails, action.title);
        keepsText(
          this.phaseHeading,
          `${PHASES[point.phase]} · ${this.#time(wanted, action.stream)}`,
        );

        keepsText(this.error, action.error ?? "");
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
      keepsHidden(this.error, !action?.error);
      keepsHidden(this.treeDetails, !action);
      let reading = !this.#trace
        ? "Waiting for a Playwright recording."
        : !items.length
          ? "No recorded checkpoints or frames in this page or stream."
          : `Timeline point ${position + 1} of ${items.length}${action ? ` · Action ${this.#trace.actions.indexOf(action) + 1} · ${PHASES[point.phase]}` : " · Captured frame"}`;
      if (image)
        reading += ` · ${image.kind === "checkpoint" ? "checkpoint" : "captured image"} ${this.#time(image.timestamp, image.stream)}${wanted === null || image.kind === "checkpoint" ? "" : ` (${Math.round(wanted - image.timestamp)} ms earlier)`}`;
      keepsText(this.readout, reading);
      const imageNodes = [this.missingImage];
      if (image) {
        let figure = this.#images.get(image.id);
        if (!figure) {
          figure = el("figure", "lf-trace-image");
          const frame = el("div", "lf-trace-frame");
          frame.append(document.createElement("img"));
          figure.append(frame, el("figcaption", "lf-trace-caption"));
          this.#images.set(image.id, figure);
        }
        const img = figure.querySelector("img");
        const label = this.#targets.get(this.#id("image", image.id)).label;
        keeps(img, "src", scopedMediaUrl(image.url));
        keeps(img, "alt", label);
        keeps(img, "width", String(image.width));
        keeps(img, "height", String(image.height));
        keepsText(figure.querySelector("figcaption"), label);
        imageNodes.push(figure);
        add(this.#id("image", image.id), img, label, [
          "images",
          this.#trace.images.indexOf(image),
        ]);
      }
      keepsHidden(this.missingImage, !!image);
      keepsText(
        this.missingNote,
        !this.#trace
          ? "The recording has not arrived."
          : "No captured image is available at or before this timeline point.",
      );
      setChildren(this.imageHost, imageNodes);
      const box = this.#imageBoxes.get(image?.id ?? this.#page);
      keepsHidden(this.missingBox, !box);
      this.#keepStyle(this.imageHost, "--lf-trace-image-w", box && `${box.width}px`);
      this.#keepStyle(
        this.imageHost,
        "--lf-trace-image-ratio",
        box && `${box.width} / ${box.height}`,
      );
      const rows = [];
      if (action) {
        keepsText(
          this.treeSummary,
          tree ? `Saved elements (${tree.nodes.length})` : "Saved elements unavailable",
        );
        keepsText(
          this.treeClock,
          tree
            ? `Tree captured ${this.#time(tree.timestamp, action.stream)}. Element boxes describe this tree, not exact positions in the image.`
            : "No accessibility tree was saved for this phase. Full DOM inspection is available in Playwright.",
        );
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
      this.#parts.update();
      paintKeys();
      // Every draw, a same-sized one included, gives back held room it no longer needs.
      this.#release();
    }
  },
);
