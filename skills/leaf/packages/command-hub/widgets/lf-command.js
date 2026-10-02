/* The Command Hub's projection boundary. The authored goal tree and event log are
 * canonical; the orchestration model gives the header, goal rows, stopped reading, and fleet
 * one answer about progress and workers.
 *
 * The three readings are panels that stand open, each titled by what it counts. They
 * fill a seat: the lf-command-readings the command's `readings` names, so a wide page
 * lays the tree in its body and the readings in the rail beside it, or else one the
 * command draws at its own head (`band`). The command owns the panels it drew wherever
 * they stand: each paint puts them at the head of the current seat, so a seat that
 * arrives or leaves moves them rather than stranding one copy and drawing another, and
 * a seat tells its command when it connects or disconnects. A command that disconnects
 * takes its panels with it, so a seat never holds a departed command's readings beside
 * its replacement's. The seat is looked up in the command's own authored document, so
 * a command quoted in a message does not take the page's seat. */
import {
  PRESS,
  threadBox,
  declarationFor,
  addressableWord,
  holdFocus,
  authoredScope,
  commands,
  keeps,
  keepsText,
  matchesWhen,
  offer,
  once,
  projectData,
  relabel,
  selectableOffer,
  shortAgo,
  TEXT_BOX,
  watchUpdates,
} from "/runtime/widget-api.js";
import {
  closestCommandRole,
  commandRole,
  commandSnapshot,
  directCommandRole,
  elementsWithCommandRole,
} from "/widgets/command-model.js";

const goalSignatures = new WeakMap();
const headerSignatures = new WeakMap();
const stoppedSignatures = new WeakMap();
const fleetSignatures = new WeakMap();
const fleetModes = new WeakMap();
const configured = new WeakSet();

function descendants(plan, source) {
  const seen = new Set();
  const queue = [source];
  while (queue.length) {
    const current = queue.shift();
    for (const task of elementsWithCommandRole(plan, "goal")) {
      const attr = commandRole(task, "goal").depends;
      if (!attr) continue;
      if (!(task.getAttribute(attr) || "").split(/\s+/).includes(current)) continue;
      if (seen.has(task.id)) continue;
      seen.add(task.id);
      queue.push(task.id);
    }
  }
  return [...seen];
}

const VIEWS = ["lf-command-head", "lf-stopped-view", "lf-fleet-view"];

// The panels each command drew, by reading, wherever they currently stand.
const drawn = new WeakMap();

const view = (plan, cls) => drawn.get(plan)?.get(cls) ?? null;

function draw(plan, cls, box) {
  if (!drawn.has(plan)) drawn.set(plan, new Map());
  const old = view(plan, cls);
  if (old && old !== box) old.replaceWith(box);
  drawn.get(plan).set(cls, box);
}

// The seat a command draws at its own head when the page places none. Which goals are
// stopped and which workers live or have gone quiet is the log's and the clock's to say,
// so no first paint knows the readings' size: the theme holds every seat at one fixed
// height from the first paint, scrolling inside it, so readings arriving move nothing
// (assets/AGENTS.md, "Stability"). The scrolling is the layer's bound, which the tag
// declares (x-bound): delivery paints it on a seat the page places, and the command
// paints it here on the one it makes.
const bands = new WeakMap();

function band(plan) {
  if (!bands.has(plan)) {
    const box = document.createElement("lf-command-readings");
    box.dataset.lfGen = "1";
    keeps(box, "data-lf-bound", declarationFor(box, "x-bound"));
    bands.set(plan, box);
  }
  return bands.get(plan);
}

// Where the readings stand: the lf-command-readings this command's `readings` names in
// its own document, or else the band at its head.
function home(plan) {
  const id = plan.getAttribute("readings");
  const named =
    id && authoredScope(plan).querySelector(`lf-command-readings[id="${id}"]`);
  return named || band(plan);
}

// Put the drawn panels, in reading order, at the head of their home, and the band at
// the head of the command only while it is that home. Nothing already in place is
// moved, so a paint that changes nothing about the seat moves nothing.
function seat(plan, at = home(plan)) {
  const own = band(plan);
  if (at !== own) own.remove();
  else if (plan.firstChild !== own) plan.prepend(own);
  let cursor = at.firstChild;
  for (const cls of VIEWS) {
    const box = view(plan, cls);
    if (box === cursor) cursor = cursor.nextSibling;
    else at.insertBefore(box, cursor);
  }
}

// One reading's panel: the layer's titled region, its heading the reading's own count.
// The heading takes focus when a count in the head opens its view, so the move lands
// on the name of what the press opened.
function panel(cls, title) {
  const box = document.createElement("section");
  box.className = `panel ${cls}`;
  box.dataset.lfGen = "1";
  box.append(heading(title));
  return box;
}

function heading(title) {
  const node = document.createElement("h2");
  node.tabIndex = -1;
  relabel(node, title, { says: true });
  return node;
}

function retitle(box, title) {
  const node = box.querySelector(":scope > h2");
  relabel(node, title, { says: true });
}

// A route to a row, not a second place the page says its name. The label is copied off
// the target's own <strong>, and both copies stand fenced — the roster item is generated
// words, and the row's name sits between the state chip and the remit the widget builds —
// so two passages carried the same text and the same empty context, and neither could be
// told from the other: a drag across a worker's name detached instead of anchoring, on the
// name and on the row alike. Chrome, like the contents sidebar's links, which name every
// heading on the page and say none of them. The words stay quotable where the page says
// them, which is the row this points at.
//
// An echo rather than an unsaid label, because paper reads the same declaration: a
// stopped row is its goal's title and an age, a fleet row a worker's name and its state,
// and a sheet that drops the name prints "12d awaiting review" with no subject at
// all. The words are not this row's to be pointed at; they are still what it is about.
function button(label, target, cls = "") {
  const node = offer("a", cls);
  relabel(node, label, { says: "echo" });
  // Following it opens a shut goal around a worker as any trip does, through the goal's
  // `lf-reveal` below.
  node.href = `#${target.id}`;
  return node;
}

function viewButton(label, view, open, cls = "") {
  const node = selectableOffer("button", cls);
  relabel(node, label, { says: true });
  node.dataset.lfView = view;
  node.addEventListener("click", open);
  commands(node, "On a command view", [
    {
      id: "command.open-view",
      keys: PRESS,
      does: "Open this command view",
      line: "open the view",
      run: () => node.click(),
    },
  ]);
  return node;
}

function chip(text, cls = "") {
  return Object.assign(document.createElement("span"), {
    className: cls,
    textContent: text,
  });
}

// A count the head offers as a view: the number is what the eye compares across tiles,
// so it stands apart from its word, and the two still read as the one label they are.
function countTile(count, word, name, open, cls = "") {
  const node = viewButton(`${count} ${word}`, name, open, cls);
  node.replaceChildren(chip(String(count), "lf-command-count"), " ", chip(word));
  return node;
}

// The done fraction drawn as a length. The fraction under it says the number, so the
// bar is hidden from assistive technology rather than said twice.
function progressBar(done, total) {
  const bar = document.createElement("span");
  bar.className = "lf-command-progress";
  bar.setAttribute("aria-hidden", "true");
  bar.style.setProperty("--lf-done", total ? done / total : 0);
  return bar;
}

function projectionFocus(plan) {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement)) return null;
  const root = active.closest(`.${VIEWS.join(", .")}, .lf-task-meta`);
  if (!root) return null;
  const kind = VIEWS.find((cls) => root.classList.contains(cls));
  if (kind ? view(plan, kind) !== root : closestCommandRole(active, "command") !== plan)
    return null;
  const goal = !kind && closestCommandRole(root.parentElement, "goal");
  const href = active.getAttribute("href");
  const title = active.parentElement === root && active.localName === "h2";
  const viewName = active.dataset.lfView;
  const offerClass = [...active.classList].find((cls) => cls.startsWith("lf-task-"));
  const restoreFocus = holdFocus(root);
  // A panel moved to a new seat keeps its nodes, so the hold lands on the same one; a
  // repainted panel stands in the control keyed the same way.
  return () => {
    const replacementRoot = kind
      ? view(plan, kind)
      : goal?.querySelector(":scope > .lf-task-meta");
    const replacement = href
      ? [...(replacementRoot?.querySelectorAll("a[href]") ?? [])].find(
          (candidate) => candidate.getAttribute("href") === href,
        )
      : viewName
        ? replacementRoot?.querySelector(`[data-lf-view="${viewName}"]`)
        : offerClass
          ? replacementRoot?.querySelector(`.${offerClass}`)
          : title
            ? replacementRoot?.querySelector(":scope > h2")
            : null;
    restoreFocus(replacement);
  };
}

function showView(box) {
  const title = box?.querySelector(":scope > h2");
  if (!title) return;
  title.focus({ preventScroll: true });
  box.scrollIntoView({ block: "nearest" });
}

function openStopped(plan) {
  showView(view(plan, "lf-stopped-view"));
}

function openFleet(plan, mode) {
  fleetModes.set(plan, mode);
  render(plan);
  showView(view(plan, "lf-fleet-view"));
}

function setWorkers(goal, open) {
  goal.toggleAttribute("data-lf-open", open);
  const crew = goal.querySelector(":scope > .lf-task-meta .lf-task-crew");
  keeps(crew, "aria-expanded", open);
}

function toggleWorkers(goal) {
  setWorkers(goal, !goal.hasAttribute("data-lf-open"));
}

function configureGoal(goal) {
  if (configured.has(goal)) return;
  configured.add(goal);
  const threadRole = declarationFor(goal, "x-thread-seat");
  if (threadRole && matchesWhen(goal, threadRole.when)) {
    const thread = threadBox(goal, "Say something here");
    if (thread) goal.append(thread);
  }
  goal.addEventListener("lf-reveal", (event) => {
    const target = event.detail?.target;
    if (
      target instanceof Node &&
      directCommandRole(goal, "worker").some((worker) => worker.contains(target))
    )
      setWorkers(goal, true);
  });
  goal.addEventListener("click", (event) => {
    if (!directCommandRole(goal, "worker").length) return;
    if (event.target.closest(`button, a, ${TEXT_BOX}, input, summary, [data-lf-offer]`))
      return;
    if (
      closestCommandRole(event.target, "command") !==
      closestCommandRole(goal, "command")
    )
      return;
    if (closestCommandRole(event.target, "goal") !== goal) return;
    if (closestCommandRole(event.target, "worker")) return;
    const selection = getSelection();
    if (selection && !selection.isCollapsed) return;
    toggleWorkers(goal);
  });
}

function renderGoal(goal) {
  configureGoal(goal.element);
  const signature = JSON.stringify([
    goal.state,
    goal.held,
    goal.stopped,
    goal.finished,
    goal.leaves.length,
    goal.element.getAttribute("when"),
    goal.element.getAttribute("tags"),
    goal.liveWorkers.map((worker) => [worker.element.id, worker.state, worker.quiet]),
    goal.openInterventions.map((item) => item.id),
  ]);
  if (goalSignatures.get(goal.element) === signature) return false;
  goalSignatures.set(goal.element, signature);
  goal.element.querySelector(":scope > .lf-task-meta[data-lf-gen]")?.remove();
  const meta = document.createElement("span");
  meta.className = "lf-task-meta";
  meta.dataset.lfGen = "1";
  if (goal.leaves.length > 1)
    meta.append(chip(`${goal.finished}/${goal.leaves.length}`, "lf-task-progress"));
  const signals = [];
  if (goal.stopped && goal.role.stalled?.includes(goal.state))
    signals.push("stalled work");
  else if (goal.stopped && goal.role.review?.includes(goal.state))
    signals.push("review");
  for (const intervention of goal.openInterventions) {
    const word = addressableWord(intervention);
    if (word && !signals.includes(word)) signals.push(word);
  }
  for (const signal of signals) meta.append(chip(signal, "lf-task-signal"));
  for (const label of [
    goal.element.getAttribute("when"),
    ...(goal.element.getAttribute("tags")?.split(",") ?? []),
  ].filter(Boolean))
    meta.append(chip(label));
  if (goal.liveWorkers.length) {
    const crew = offer(
      "button",
      "lf-task-crew",
      `${goal.liveWorkers.length} worker${goal.liveWorkers.length === 1 ? "" : "s"}`,
    );
    crew.setAttribute(
      "aria-expanded",
      String(goal.element.hasAttribute("data-lf-open")),
    );
    crew.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleWorkers(goal.element);
    });
    meta.append(crew);
  }
  if (goal.held) meta.append(chip("paused by you", "lf-task-held"));
  // First, so the chips float level with the title (theme.css).
  goal.element.prepend(meta);
  return true;
}

function renderHeader(snapshot) {
  const { plan } = snapshot;
  const old = view(plan, "lf-command-head");
  const signature = JSON.stringify([
    snapshot.done,
    snapshot.leaves.length,
    snapshot.running.map((worker) => worker.element.id),
    snapshot.liveWorkers.length,
    snapshot.quiet.map((worker) => worker.element.id),
    snapshot.stopped.map((goal) => goal.element.id),
    plan.getAttribute("label"),
    plan.getAttribute("phase"),
  ]);
  if (old && headerSignatures.get(plan) === signature) return false;
  headerSignatures.set(plan, signature);
  const head = panel("lf-command-head", "Outcome");
  const outcome = document.createElement("div");
  outcome.className = "lf-command-outcome";
  outcome.append(
    Object.assign(document.createElement("strong"), {
      textContent: plan.getAttribute("label") || "Work",
    }),
    progressBar(snapshot.done, snapshot.leaves.length),
    Object.assign(document.createElement("span"), {
      textContent: `${snapshot.done}/${snapshot.leaves.length} leaves · ${plan.getAttribute("phase") || "in progress"}`,
    }),
  );
  const facts = document.createElement("div");
  facts.className = "lf-command-facts";
  facts.append(
    countTile(snapshot.running.length, "running", "running", () =>
      openFleet(plan, "running"),
    ),
    countTile(snapshot.liveWorkers.length, "workers", "workers", () =>
      openFleet(plan, "all"),
    ),
  );
  if (snapshot.quiet.length)
    facts.append(
      countTile(
        snapshot.quiet.length,
        "quiet",
        "quiet",
        () => openFleet(plan, "quiet"),
        "warn",
      ),
    );
  facts.append(
    countTile(
      snapshot.stopped.length,
      "stopped",
      "stopped",
      () => openStopped(plan),
      snapshot.stopped.length ? "danger" : "",
    ),
  );
  head.append(outcome, facts);
  draw(plan, "lf-command-head", head);
  return true;
}

// `stoppedAt` is a server stamp or a `stopped-at` the registry admitted as a date-time,
// so the one reading left to make is its absence.
const age = (goal) => (goal.stoppedAt ? shortAgo(goal.stoppedAt) : "age unknown");

function renderStopped(snapshot) {
  const { plan } = snapshot;
  let box = view(plan, "lf-stopped-view");
  const signature = JSON.stringify(
    snapshot.stopped.map((goal) => [
      goal.element.id,
      goal.stoppedAt,
      goal.held,
      goal.state,
      descendants(plan, goal.element.id).length,
    ]),
  );
  if (box && stoppedSignatures.get(plan) === signature) {
    for (const goal of snapshot.stopped) {
      const shown = box?.querySelector(
        `li[data-lf-goal="${goal.element.id}"] .lf-stopped-age`,
      );
      keepsText(shown, age(goal));
    }
    return false;
  }
  stoppedSignatures.set(plan, signature);
  if (!box) {
    box = panel("lf-stopped-view", "Nothing is stopped");
    draw(plan, "lf-stopped-view", box);
  }
  const label = snapshot.stopped.length
    ? `Stopped work · ${snapshot.stopped.length}, oldest first`
    : "Nothing is stopped";
  retitle(box, label);
  if (snapshot.stopped.length) {
    let list = box.querySelector(":scope > ol");
    if (!list) {
      list = document.createElement("ol");
      list.id = `lf-${plan.id}-stopped`;
      box.append(list);
    }
    projectData(
      list,
      snapshot.stopped,
      (goal) => goal.element.id,
      (goal) => {
        const downstream = descendants(plan, goal.element.id);
        const reason = goal.held
          ? "paused by you"
          : goal.role.review?.includes(goal.state)
            ? "awaiting review"
            : goal.role.stalled?.includes(goal.state)
              ? "stalled"
              : "blocked";
        const item = document.createElement("li");
        item.dataset.lfGoal = goal.element.id;
        item.dataset.lfReason = reason;
        const why = chip("", "lf-stopped-why");
        why.append(chip(age(goal), "lf-stopped-age"), ` ${reason}`);
        if (downstream.length)
          why.append(
            ` · holds ${downstream.length} downstream goal${downstream.length === 1 ? "" : "s"}`,
          );
        item.append(button(goal.title, goal.element), why);
        return item;
      },
      {
        originOf: (goal) => ({
          derived: [goal.element.id, ...descendants(plan, goal.element.id)].map(
            (widget) => ({ widget }),
          ),
        }),
      },
    );
  } else box.querySelector(":scope > ol")?.remove();
  return true;
}

function renderFleet(snapshot) {
  const { plan } = snapshot;
  const mode = fleetModes.get(plan) ?? "all";
  const workers =
    mode === "running"
      ? snapshot.running
      : mode === "quiet"
        ? snapshot.quiet
        : snapshot.liveWorkers;
  const old = view(plan, "lf-fleet-view");
  const signature = JSON.stringify([
    mode,
    workers.map((worker) => [
      worker.element.id,
      worker.state,
      worker.remit.id,
      worker.assignment?.id,
      worker.assignment && snapshot.byElement.get(worker.assignment).title,
    ]),
  ]);
  if (old && fleetSignatures.get(plan) === signature) return false;
  fleetSignatures.set(plan, signature);
  const box = panel(
    "lf-fleet-view",
    mode === "all"
      ? `Fleet · ${workers.length} live worker${workers.length === 1 ? "" : "s"}`
      : `${mode === "running" ? "Running" : "Quiet"} · ${workers.length} worker${workers.length === 1 ? "" : "s"}`,
  );
  const list = document.createElement("ul");
  for (const worker of workers) {
    const focus = worker.assignment && snapshot.byElement.get(worker.assignment);
    const remit =
      worker.remit === plan
        ? "project-wide remit"
        : `${snapshot.byElement.get(worker.remit).title} remit`;
    const item = document.createElement("li");
    item.append(
      button(
        `§ ${
          worker.element.querySelector(":scope > strong")?.textContent.trim() ||
          worker.element.id
        }`,
        worker.element,
      ),
    );
    item.append(
      " ",
      chip(worker.state, `lf-state lf-state-${worker.state}`),
      chip(
        focus && worker.assignment !== worker.remit
          ? `${remit} · focused on ${focus.title}`
          : remit,
        "lf-fleet-remit",
      ),
    );
    list.append(item);
  }
  box.append(list);
  draw(plan, "lf-fleet-view", box);
  return true;
}

const render = (plan) => paint(plan);

function paint(plan) {
  const restoreFocus = projectionFocus(plan);
  const snapshot = commandSnapshot(plan);
  for (const goal of snapshot.goals) renderGoal(goal);
  renderHeader(snapshot);
  renderStopped(snapshot);
  renderFleet(snapshot);
  seat(plan);
  restoreFocus?.();
}

customElements.define(
  "lf-command",
  class extends HTMLElement {
    #stop;

    connectedCallback() {
      once(this);
      this.#stop ??= watchUpdates(this, () => render(this));
    }

    // The panels leave with the command: standing in a seat, they would outlive it
    // there, and a command that connects again repaints them into its current seat.
    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
      if (drawn.has(this)) seat(this, band(this));
    }

    // The seat this command's `readings` names connected or disconnected.
    reseat() {
      if (!this.isConnected || !drawn.has(this)) return;
      const restoreFocus = projectionFocus(this);
      seat(this);
      restoreFocus?.();
    }
  },
);
