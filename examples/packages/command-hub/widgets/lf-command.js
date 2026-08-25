/* The Command Hub's projection boundary. The authored goal tree and event log are
 * canonical; the orchestration model gives the header, goal rows, stopped reading, and fleet
 * one answer about progress and workers. */
import {
  conversationBox,
  declarationFor,
  itemWord,
  matchesWhen,
  offer,
  once,
  projectData,
  relabel,
} from "/leaf.js";
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

function speakingOffer(tag, label, cls = "") {
  const node = offer(tag, cls);
  relabel(node, label, { says: true });
  return node;
}

function button(label, target, cls = "") {
  const node = speakingOffer("a", label, cls);
  node.href = `#${target.id}`;
  node.addEventListener("click", () => {
    if (commandRole(target, "worker")) {
      const command = closestCommandRole(target, "command");
      const goal = closestCommandRole(target.parentElement, "goal");
      if (goal && closestCommandRole(goal, "command") === command)
        goal.setAttribute("data-lf-open", "");
    }
  });
  return node;
}

function chip(text, cls = "") {
  return Object.assign(document.createElement("span"), {
    className: cls,
    textContent: text,
  });
}

function projectionFocus(plan) {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement) || !plan.contains(active)) return null;
  if (closestCommandRole(active, "command") !== plan) return null;
  const root = active.closest(
    ".lf-command-head, .lf-stopped-view, .lf-fleet-view, .lf-task-meta",
  );
  if (!root) return null;
  const kind = ["lf-command-head", "lf-stopped-view", "lf-fleet-view"].find((cls) =>
    root.classList.contains(cls),
  );
  const goal = !kind && closestCommandRole(root.parentElement, "goal");
  const href = active.getAttribute("href");
  const summary = active.localName === "summary";
  const offerClass = [...active.classList].find((cls) => cls.startsWith("lf-task-"));
  return () => {
    if (active.isConnected) return;
    const replacementRoot = kind
      ? plan.querySelector(`:scope > .${kind}`)
      : goal?.querySelector(":scope > .lf-task-meta");
    const replacement = href
      ? [...(replacementRoot?.querySelectorAll("a[href]") ?? [])].find(
          (candidate) => candidate.getAttribute("href") === href,
        )
      : offerClass
        ? replacementRoot?.querySelector(`.${offerClass}`)
        : summary
          ? replacementRoot?.querySelector(":scope > summary")
          : null;
    replacement?.focus({ preventScroll: true });
  };
}

function toggleWorkers(goal) {
  goal.toggleAttribute("data-lf-open");
  const crew = goal.querySelector(":scope > .lf-task-meta .lf-task-crew");
  crew?.setAttribute("aria-expanded", String(goal.hasAttribute("data-lf-open")));
}

function configureGoal(goal) {
  if (configured.has(goal)) return;
  configured.add(goal);
  goal.dataset.lfCommandGoal = "1";
  const conversationRole = declarationFor(goal, "x-conversation");
  if (conversationRole && matchesWhen(goal, conversationRole.when)) {
    const conversation = conversationBox(goal, "Say something here");
    if (conversation) goal.append(conversation);
  }
  goal.addEventListener("lf-reveal", () => goal.setAttribute("data-lf-open", ""));
  goal.addEventListener("click", (event) => {
    if (!directCommandRole(goal, "worker").length) return;
    if (event.target.closest("button, a, textarea, input, summary, [data-lf-offer]"))
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
  const asks = [];
  if (goal.stopped && goal.role.stalled?.includes(goal.state))
    asks.push("stalled work");
  else if (goal.stopped && goal.role.review?.includes(goal.state)) asks.push("review");
  for (const ask of goal.openInterventions) {
    const word = itemWord(ask);
    if (word && !asks.includes(word)) asks.push(word);
  }
  for (const ask of asks) meta.append(chip(ask, "lf-task-ask"));
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
  const strong = goal.element.querySelector(":scope > strong");
  const quiet = goal.element.querySelector(":scope > .lf-quiet");
  if (quiet) quiet.after(meta);
  else if (strong) strong.after(meta);
  else goal.element.prepend(meta);
  return true;
}

function renderHeader(snapshot) {
  const { plan } = snapshot;
  const old = plan.querySelector(":scope > .lf-command-head[data-lf-gen]");
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
  if (headerSignatures.get(plan) === signature) return false;
  headerSignatures.set(plan, signature);
  const head = document.createElement("header");
  head.className = "lf-command-head";
  head.dataset.lfGen = "1";
  const outcome = document.createElement("div");
  outcome.className = "lf-command-outcome";
  outcome.append(
    Object.assign(document.createElement("strong"), {
      textContent: plan.getAttribute("label") || "Work",
    }),
    Object.assign(document.createElement("span"), {
      textContent: `${snapshot.done}/${snapshot.leaves.length} leaves · ${plan.getAttribute("phase") || "in progress"}`,
    }),
  );
  const facts = document.createElement("div");
  facts.className = "lf-command-facts";
  facts.append(
    button(`${snapshot.running.length} running`, snapshot.running[0]?.element || plan),
    button(
      `${snapshot.liveWorkers.length} workers`,
      snapshot.liveWorkers[0]?.element || plan,
    ),
  );
  if (snapshot.quiet.length)
    facts.append(
      button(`${snapshot.quiet.length} quiet`, snapshot.quiet[0].element, "warn"),
    );
  facts.append(
    button(
      `${snapshot.stopped.length} stopped`,
      snapshot.stopped[0]?.element || plan,
      snapshot.stopped.length ? "danger" : "",
    ),
  );
  head.append(outcome, facts);
  if (old) old.replaceWith(head);
  else plan.prepend(head);
  return true;
}

function age(goal) {
  if (!goal.stoppedAt) return "age unknown";
  const at = new Date(goal.stoppedAt).getTime();
  if (!Number.isFinite(at)) return "age unknown";
  const minutes = Math.max(0, Math.floor((Date.now() - at) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h` : `${Math.floor(hours / 24)}d`;
}

function renderStopped(snapshot) {
  const { plan } = snapshot;
  let box = plan.querySelector(":scope > .lf-stopped-view[data-lf-gen]");
  const signature = JSON.stringify(
    snapshot.stopped.map((goal) => [
      goal.element.id,
      goal.stoppedAt,
      goal.held,
      goal.state,
      descendants(plan, goal.element.id).length,
    ]),
  );
  if (stoppedSignatures.get(plan) === signature) {
    for (const goal of snapshot.stopped) {
      const shown = box?.querySelector(
        `li[data-lf-goal="${goal.element.id}"] .lf-stopped-age`,
      );
      if (shown) shown.textContent = age(goal);
    }
    return false;
  }
  stoppedSignatures.set(plan, signature);
  if (!box) {
    box = document.createElement("details");
    box.className = "lf-stopped-view";
    box.dataset.lfGen = "1";
    box.append(speakingOffer("summary", "Nothing is stopped"));
    plan.querySelector(":scope > .lf-command-head")?.after(box);
  }
  const label = snapshot.stopped.length
    ? `Stopped work · ${snapshot.stopped.length}, oldest first`
    : "Nothing is stopped";
  const summary = box.querySelector(":scope > summary");
  if (summary.textContent !== label) relabel(summary, label, { says: true });
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
        item.append(
          button(goal.title, goal.element),
          " · ",
          chip(age(goal), "lf-stopped-age"),
          ` — ${reason}; ${downstream.length} downstream goal${downstream.length === 1 ? "" : "s"} unreachable`,
        );
        return item;
      },
    );
  } else box.querySelector(":scope > ol")?.remove();
  return true;
}

function renderFleet(snapshot) {
  const { plan } = snapshot;
  const old = plan.querySelector(":scope > .lf-fleet-view[data-lf-gen]");
  const signature = JSON.stringify(
    snapshot.liveWorkers.map((worker) => [
      worker.element.id,
      worker.state,
      worker.remit.id,
      worker.assignment?.id,
      worker.assignment && snapshot.byElement.get(worker.assignment).title,
    ]),
  );
  if (fleetSignatures.get(plan) === signature) return false;
  fleetSignatures.set(plan, signature);
  const box = document.createElement("details");
  box.className = "lf-fleet-view";
  box.dataset.lfGen = "1";
  box.open = old?.open || false;
  box.append(
    speakingOffer(
      "summary",
      `Fleet · ${snapshot.liveWorkers.length} live worker${snapshot.liveWorkers.length === 1 ? "" : "s"}`,
    ),
  );
  const list = document.createElement("ul");
  for (const worker of snapshot.liveWorkers) {
    const focus = worker.assignment && snapshot.byElement.get(worker.assignment);
    const remit =
      worker.remit === plan
        ? "project-wide remit"
        : `${snapshot.byElement.get(worker.remit).title} remit`;
    const item = document.createElement("li");
    item.append(
      button(
        worker.element.querySelector(":scope > strong")?.textContent.trim() ||
          worker.element.id,
        worker.element,
      ),
    );
    item.append(` · ${worker.state} · ${remit}`);
    if (focus && worker.assignment !== worker.remit)
      item.append(` · focused on ${focus.title}`);
    list.append(item);
  }
  box.append(list);
  if (old) old.replaceWith(box);
  else plan.append(box);
  return true;
}

function render(plan) {
  const restoreFocus = projectionFocus(plan);
  const snapshot = commandSnapshot(plan);
  // This marker is the renderer's generic relation hook. It covers workers at every
  // remit depth, including a project-wide worker directly under the command.
  for (const worker of snapshot.workers)
    if (!worker.element.hasAttribute("data-lf-command-worker"))
      worker.element.dataset.lfCommandWorker = "1";
  const changed = [
    ...snapshot.goals.map((goal) => renderGoal(goal)),
    renderHeader(snapshot),
    renderStopped(snapshot),
    renderFleet(snapshot),
  ].some(Boolean);
  if (changed)
    document.dispatchEvent(new CustomEvent("lf-command-update", { detail: snapshot }));
  restoreFocus?.();
}

customElements.define(
  "lf-command",
  class extends HTMLElement {
    #events;
    #observer;

    connectedCallback() {
      once(this);
      this.#events = new AbortController();
      document.addEventListener("lf-actions", () => render(this), {
        signal: this.#events.signal,
      });
      this.#observer = new MutationObserver((changes) => {
        if (
          changes.some((change) => {
            if (["data-lf-held", "data-lf-pending"].includes(change.attributeName))
              return true;
            return Boolean(commandRole(change.target));
          })
        )
          render(this);
      });
      this.#observer.observe(this, { attributes: true, subtree: true });
      render(this);
    }

    disconnectedCallback() {
      this.#events?.abort();
      this.#events = null;
      this.#observer?.disconnect();
      this.#observer = null;
    }
  },
);
