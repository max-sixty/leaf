/* The floating panel: Leaf's chrome as one box hovering over the foot of the page, in
 * place of the banner and the bottom bar, for a user who chose it (prepaint.js,
 * `lfChrome`). It is another presentation of what the banner, the bottom bar, Threads
 * and Questions already own, so it reads their readings and calls their commands:
 * the status (`watchStatus`), the toolbar's rows (`bannerRows`), the threads
 * (`readThreads`), the queues (`readQueues`), the versions (`versionPicker`) and the
 * drafts (drafts.js). It decides only how they are shown.
 *
 * At rest the panel is one row: the leaf, whose colour is the agent's state; the
 * comment field, whose empty face says what the agent is doing; the Questions count;
 * the count of threads with news; and, on a desk, Annotate. Minimizing folds it to the
 * leaf, and it stays folded, across pages, until the user unfolds it: its resting form
 * is one setting (`rest`), so another resting form is another value of it.
 *
 * Everything else opens above that row, inside the same box, as views on a trail: the
 * page menu (the leaf), Threads and a thread, Questions, Versions, and the menu's
 * groups. The row just above the field names where the user is and the way back. The
 * field the user clicks in is the field they write in: a page comment where no thread
 * is open, a reply where one is, the destination named above it. Each destination keeps
 * its own native editor (its draft, caret and send), and the panel stands the current
 * one in the field's place, so words never move between editors.
 *
 * Nothing moves under the pointer: a filtered inventory keeps its height, and a control
 * the user pressed stays where it was. The box changes size only from its foot, the
 * row staying put, by one tween of its height; a view arriving fades in over the one
 * leaving. These are mechanics borrowed from the Codex app's floating panel
 * (`notes/floating-panel/GOAL.md`). */
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { move } from "./dom-move.js";
import { iconTemplate } from "./icons.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
import { approvalReading, approve, toggleBtn, watchStatus } from "./banner.js";
import { queueBtn } from "./drawers.js";
import { keys } from "./keyboard/scopes.js";
import { bannerRows, watchBannerRows } from "./banner-toolbar.js";
import { readPlace } from "./history.js";
import { readThreads } from "./thread/state.js";
import { watchThreads } from "./thread/watch.js";
import { threadAttention, workflowLabel } from "./thread/workflow.js";
import { threadSummary } from "./thread/model.js";
import { messageReading } from "./thread/messages.js";
import {
  draftHasContent,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "./drafts.js";
import { textField } from "./composing/text-field.js";
import { queueItemKey, readQueues, watchQueues } from "./queue-api.js";
import { queueTitle } from "./queue-title.js";
import { questionEnding } from "./questions/answer.js";
import { versionMenu, versionPicker } from "./version-picker.js";
import { reducedMotion } from "./motion.js";
import { pagePresented } from "./page-paint.js";
import {
  focusDestination,
  focused,
  onStanding,
  onUserInput,
  releaseFocus,
} from "./focus.js";
import { sizeObserver } from "./rendering.js";
import { agentName, readApplication, watchSemantic } from "./semantic-state.js";

const prefs = () => document.documentElement.lfChrome;
// The Codex panel's tween: one strong ease-out for every change of size and fade.
const EASE = "cubic-bezier(.23, 1, .32, 1)";
const RESIZE_MS = 300;
const FADE_MS = 180;
// The view leaving is gone before the one arriving shows, so the two never read
// through each other.
const OUT_MS = 80;

// The menu's groups, each a view of the toolbar rows declaring it.
const GROUPS = Object.freeze({
  navigate: "Navigate",
  annotate: "Annotations",
  about: "About this page",
});
// Rows the panel draws as views of its own rather than pressing the native control.
const OWN_VIEWS = Object.freeze({
  threads: "threads",
  queue: "questions",
  versions: "versions",
});
const FILTERS = Object.freeze(["all", "unread", "drafts", "resolved"]);
const capital = (word) => word[0].toUpperCase() + word.slice(1);
const coarse = () => matchMedia("(pointer: coarse)").matches;

export function createFloatingPanel({
  wireInput,
  threadActions,
  registerThreadPresentation,
  questions: questionView,
  queueActions,
  withdraw,
}) {
  const host = el("section", "lf-ui lf-floating-panel");
  host.setAttribute("aria-label", "Leaf");
  const card = el("div", "lf-fp-card");
  const inner = el("div", "lf-fp-inner");
  const stage = el("div", "lf-fp-stage");
  const head = el("div", "lf-fp-head");
  const to = el("div", "lf-fp-to");
  const toDest = el("span", "lf-fp-dest");
  const toActions = el("span", "lf-fp-actions");
  to.append(toDest, toActions);
  const row = el("div", "lf-fp-row");
  const foot = el("div", "lf-fp-foot");
  const peek = el("div", "lf-fp-peek");
  peek.id = "lf-fp-peek";
  peek.setAttribute("role", "tooltip");
  inner.append(stage, head, to, row, foot);
  card.append(inner);
  host.append(card, peek);

  const leaf = el("button", "lf-fp-leaf");
  leaf.type = "button";
  leaf.setAttribute("aria-haspopup", "dialog");
  leaf.setAttribute("aria-describedby", peek.id);
  const mark = el("span", "lf-dot");
  leaf.append(mark);
  const field = el("div", "lf-fp-field");
  const quick = el("div", "lf-fp-quick");
  row.append(leaf, field, quick);

  let status = { tone: "", summary: "Connecting…", explanation: "Connecting…" };
  // The trail of views open above the row, innermost last; empty at rest.
  let trail = [];
  let leaving = null;
  let filter = "all";
  let query = "";
  let writing = false;
  // The thread the reader lands at the end of, once Leaf has drawn it.
  let landAtEnd = null;

  // ---------- one native editor per destination ----------
  const editors = new Map();
  const destination = () => {
    const top = trail.at(-1);
    return top?.view === "thread" ? `reply:${top.thread}` : "general";
  };
  function editor(ctx) {
    let held = editors.get(ctx);
    if (held) return held;
    const input = textField();
    input.name = ctx === "general" ? "comment" : "reply";
    const send = el("button", "lf-btn lf-fp-send", "Send");
    const box = el("div", "lf-fp-box");
    box.append(input, send);
    const key = ctx === "general" ? null : ctx.slice("reply:".length);
    input.value = loadDraft(ctx) ?? "";
    const hint = () =>
      key
        ? threadByKey(key)?.resolved
          ? "Resolved · reopen to reply"
          : "Reply…"
        : status.summary;
    const sync = wireInput(input, {
      hint,
      accessibleName: () =>
        key ? `Reply to ${threadTitle(key)}` : "Comment on the page",
      sends: "send",
      sendBtn: send,
      save: (text) => {
        saveDraft(ctx, text);
        tellDraft(ctx, text);
        // Words arriving in an empty field, or the last of them going, re-seat the row.
        const worded = Boolean(text.trim());
        if (worded !== held.worded) {
          held.worded = worded;
          paint();
        }
      },
      send: (_text, raw, owns) => {
        const handle = sendMessage(ctx, owns, (attempt) =>
          key
            ? threadActions.reply(key, raw, { attempt })
            : threadActions.create({ attempt, text: raw })?.delivery,
        );
        if (!handle) return;
        // A page comment starts a thread, keyed by the attempt that sent it, which the
        // panel opens so its reply follows in the same field; a reply lands the reader
        // at the end of their own thread.
        if (key) landAtEnd = key;
        else open({ view: "thread", thread: handle.attempt }, { replace: true });
      },
    });
    sync();
    // Resume writing (`g i`) comes back to the page's words here, in the panel.
    const stop = mirrorDraft(input, sync, ctx, {
      retained: true,
      resume: key
        ? null
        : () => ({ where: input, input: () => input, open: writeOnPage }),
    });
    held = { ctx, box, input, sync, stop, worded: Boolean(input.value.trim()) };
    editors.set(ctx, held);
    return held;
  }

  // ---------- readings ----------
  const threads = () => {
    const reading = readThreads();
    return reading.phase === "ready" ? reading.threads : [];
  };
  const threadByKey = (key) =>
    threads().find((thread) => thread.key === key || thread.id === key) ?? null;
  const threadTitle = (key) => {
    const thread = threadByKey(key);
    return thread ? threadSummary(thread).topic : "this thread";
  };
  const unread = (thread) => thread.unread.length > 0;
  const newCount = () => threads().filter(unread).length;
  const questionCount = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.questions.length : 0;
  };
  const threadStatus = (thread) => {
    const words = [
      thread.resolved ? "Resolved" : (threadAttention(thread)?.label ?? "Open"),
    ];
    if (unread(thread)) words.push("New");
    if (draftHasContent(`reply:${thread.key}`)) words.push("Draft");
    return words.join(" · ");
  };
  const rows = () => bannerRows();

  // Who a reply goes to: the agent that has spoken in the thread, by its own name.
  const replyWords = (thread) => {
    const agent = thread.msgs.findLast((message) => message.author === "agent")?.agent;
    return agent ? `Reply in this thread · to ${agent}` : "Reply in this thread";
  };

  // ---------- navigation ----------
  const routeKey = (route) =>
    route.view === "thread"
      ? `thread:${route.thread}`
      : route.view === "group"
        ? `group:${route.group}`
        : route.view;
  const titleOf = (route) =>
    ({
      menu: "Page",
      threads: "Threads",
      questions: "Questions",
      versions: "Versions",
      layout: "Layout",
      thread: route.thread ? threadTitle(route.thread) : "",
      group: GROUPS[route.group],
    })[route.view];
  const PARENT = {
    threads: "menu",
    versions: "menu",
    layout: "menu",
    group: "menu",
    questions: null,
    thread: "threads",
  };
  const pathTo = (route) => {
    const parent = PARENT[route.view];
    return [...(parent ? pathTo({ view: parent }) : []), route];
  };
  function open(route, { replace = false, reopen = false, focus = true } = {}) {
    const before = trail.at(-1);
    if (before && routeKey(before) === routeKey(route) && !replace) {
      if (reopen) return;
      close();
      return;
    }
    trail = replace && before ? [...trail.slice(0, -1), route] : pathTo(route);
    if (replace && route.view === "thread" && trail.length === 1) trail = pathTo(route);
    if (route.view === "thread") arriveAt(route.thread);
    transition(before, { focus });
  }
  // Opening a thread shows it whole, at its end, where the latest turn is.
  function arriveAt(key) {
    landAtEnd = threadByKey(key)?.key ?? key;
  }
  // The field stands for the page again, with nothing open above it.
  // Asking to write is asking for the field, so a panel folded to the leaf unfolds.
  function writeOnPage() {
    const before = trail.at(-1);
    if (prefs().rest === "mark") prefs().set("rest", "row");
    trail = [];
    transition(before);
    focusDestination(editor("general").input, "move");
  }
  function back() {
    const before = trail.at(-1);
    trail = trail.slice(0, -1);
    transition(before);
    if (!trail.length) focusDestination(leaf, "return");
  }
  function close() {
    const before = trail.at(-1);
    trail = [];
    transition(before);
  }

  // ---------- motion: one box, resized from its foot ----------
  // The card follows its content's height by one tween, whatever changed it: a view
  // opening, the destination line arriving, a field growing a line. The content stands
  // at the card's foot, so the tween reveals or covers its top and the row stays put.
  // The first height, and any under reduced motion, is taken as it is.
  let shownHeight = null;
  let resize = null;
  const follow = sizeObserver(() => {
    const target = inner.getBoundingClientRect().height;
    if (shownHeight === null || reducedMotion() || !pagePresented()) {
      shownHeight = target;
      return;
    }
    if (Math.abs(target - shownHeight) < 0.5) return;
    const from = resize ? card.getBoundingClientRect().height : shownHeight;
    resize?.cancel();
    shownHeight = target;
    const played = card.animate([{ height: `${from}px` }, { height: `${target}px` }], {
      duration: RESIZE_MS,
      easing: EASE,
    });
    resize = played;
    played.finished.then(
      () => resize === played && (resize = null),
      () => {},
    );
  });
  function transition(before, { focus = true } = {}) {
    const after = trail.at(-1);
    const reading = [before, after].some((route) => route?.view === "thread");
    if (after?.view !== "questions") {
      seated = null;
      seatHeights.clear();
    }
    const changed =
      (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
    // The view going away fades where it stood, closing included, so the box shrinking
    // under it never shows an empty ground.
    leaving = changed && before ? before : null;
    paint();
    if (reading) void present({ release: true });
    if (!changed || reducedMotion() || !pagePresented()) {
      leaving = null;
      paint();
      if (focus) focusView(after);
      return;
    }
    const arriving = stage.querySelector(".lf-fp-view:not([data-leaving])");
    arriving?.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "none" },
      ],
      {
        duration: FADE_MS,
        delay: leaving ? OUT_MS : 0,
        easing: EASE,
        fill: "backwards",
      },
    );
    const gone = stage.querySelector(".lf-fp-view[data-leaving]");
    const fade = gone?.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: OUT_MS,
      easing: "linear",
      fill: "forwards",
    });
    const settle = () => {
      leaving = null;
      paint();
    };
    if (fade) fade.finished.then(settle, () => {});
    else leaving = null;
    if (focus) focusView(after);
  }
  function focusView(route) {
    if (!route) return;
    const view = stage.querySelector(".lf-fp-view:not([data-leaving])");
    if (!keyed && route.view !== "threads" && route.view !== "thread") {
      if (view) focusDestination(view, "move");
      return;
    }
    const target =
      route.view === "threads"
        ? stage.querySelector(".lf-fp-search")
        : route.view === "thread"
          ? editors.get(destination())?.input
          : stage.querySelector(".lf-fp-view:not([data-leaving]) button");
    if (target) focusDestination(target, "move");
  }

  // Whether the gesture now under way came from the keyboard: a key arriving in a view
  // stands on its first control, a pointer in the view itself, with no ring drawn.
  let keyed = false;
  onUserInput((event) => {
    if (
      ["keydown", "pointerdown"].includes(event.type) &&
      event.composedPath().includes(host)
    )
      keyed = event.type === "keydown";
  });

  // ---------- views ----------
  const menuRow = (label, value, press, { urgent = false, disabled = false } = {}) =>
    html`<button
      type="button"
      class="lf-fp-item"
      ?disabled=${disabled}
      ?data-lf-urgent=${urgent}
      @click=${press}
    >
      <span class="lf-fp-label">${label}</span>${
        value ? html`<span class="lf-fp-value">${value}</span>` : nothing
      }
    </button>`;

  function rowFor(entry) {
    const view = OWN_VIEWS[entry.key];
    const value =
      entry.key === "threads"
        ? `${threads().length}${newCount() ? ` · ${newCount()} new` : ""}`
        : entry.value;
    return menuRow(
      entry.label,
      value,
      () => (view ? open({ view }) : (close(), entry.press(heldStanding))),
      { urgent: Boolean(entry.urgent), disabled: entry.disabled },
    );
  }

  function menuView() {
    const all = rows();
    // The panel's own views lead, in the order the user reaches for them; the rest of
    // the page's rows follow in the toolbar's order.
    const lead = Object.keys(OWN_VIEWS);
    const page = all
      .filter(
        (entry) =>
          entry.group === "page" &&
          !entry.gesture &&
          !["page-comment", "approval", "keyboard"].includes(entry.key),
      )
      .sort(
        (a, b) =>
          (lead.includes(a.key) ? lead.indexOf(a.key) : lead.length) -
          (lead.includes(b.key) ? lead.indexOf(b.key) : lead.length),
      );
    const keyboard = all.find((entry) => entry.key === "keyboard");
    const groups = Object.keys(GROUPS).filter((group) =>
      all.some((entry) => entry.group === group && !entry.gesture),
    );
    const display = prefs().display;
    const asks = questionCount();
    return html`<p
        class="lf-fp-reading"
        data-tone=${status.tone}
        title=${status.explanation || status.summary}
      >
        ${status.summary}${asks ? ` · ${asks} ${asks === 1 ? "question" : "questions"} on you` : ""}
      </p>
      ${page.map(rowFor)}
      ${groups.map((group) =>
        menuRow(GROUPS[group], groupValue(group), () => open({ view: "group", group })),
      )}
      <hr />
      ${menuRow("Layout", capital(display), () => open({ view: "layout" }))}
      ${keyboard ? rowFor(keyboard) : nothing}`;
  }
  const groupValue = (group) =>
    group === "annotate"
      ? rows().find((entry) => entry.key === "command:annotations.toggle")?.label ===
        "Show annotations"
        ? "Hidden"
        : "Visible"
      : "";

  function groupView(group) {
    return rows()
      .filter((entry) => entry.group === group && !entry.gesture)
      .map(rowFor);
  }

  function layoutView() {
    const { display, rest } = prefs();
    const set = (value) => {
      if (value === "classic") {
        prefs().set("mode", "classic");
        location.reload();
        return;
      }
      prefs().set("display", value);
      paint();
    };
    return html`${["minimal", "moderate", "classic"].map((value) =>
        menuRow(capital(value), value === display ? "Current" : "", () => set(value)),
      )}
      <hr />
      ${menuRow(
        rest === "mark" ? "Unfold to the comment field" : "Fold to the leaf",
        "",
        () => setRest(rest === "mark" ? "row" : "mark"),
      )}`;
  }

  // The versions the picker lists, the one shown marked, each a press that travels
  // there, with Compare where the picker offers it; then the version's approval, where
  // the page asks for one, with why a press would not approve yet.
  function versionsView() {
    const { rows: versions, picker, selection } = versionPicker.model;
    const approval = approvalReading();
    const approved = approval?.text.startsWith("✓");
    return html`${repeat(
      versions,
      (entry) => `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
      (entry) =>
        html`<div class="lf-fp-version" ?data-current=${entry.current}>
          ${menuRow(entry.name, entry.current ? "Showing" : "", () => {
            close();
            versionPicker.activate(entry);
          })}${
            entry.comparable
              ? html`<button
                  type="button"
                  class="lf-fp-quiet lf-fp-compare"
                  aria-pressed=${String(selection.on && selection.base === entry.version)}
                  aria-label=${`Compare with ${entry.name}`}
                  @click=${() => {
                    close();
                    versionPicker.compare(entry.version);
                  }}
                >
                  Compare
                </button>`
              : nothing
          }
        </div>`,
    )}
    ${versions.length ? nothing : html`<p class="lf-fp-empty">${picker.token}</p>`}
    ${
      approval
        ? html`<hr />
            <div class="lf-fp-approval" title=${approval.reason ?? nothing}>
              ${menuRow(approval.text, approval.reason ?? "", () => approve(), {
                disabled: Boolean(approval.reason) && !approved,
              })}
            </div>`
        : nothing
    }`;
  }

  function threadsView() {
    const words = query.trim().toLowerCase();
    const shown = threads().filter((thread) => {
      if (filter === "unread" && !unread(thread)) return false;
      if (filter === "drafts" && !draftHasContent(`reply:${thread.key}`)) return false;
      if (filter === "resolved" && !thread.resolved) return false;
      if (!words) return true;
      const text = [
        threadSummary(thread).topic,
        ...thread.msgs.map((m) => m.text ?? ""),
      ]
        .join(" ")
        .toLowerCase();
      return text.includes(words);
    });
    const empty = words
      ? "No matching threads."
      : {
          all: "No threads yet. Comment below to start one.",
          unread: "All caught up.",
          drafts: "No drafts.",
          resolved: "No resolved threads.",
        }[filter];
    return html`<div class="lf-fp-tools">
        <input
          class="lf-fp-search"
          type="search"
          placeholder="Find a thread or message…"
          aria-label="Find a thread or message"
          .value=${query}
          @input=${(event) => {
            query = event.target.value;
            paint();
          }}
        />
        <div class="lf-fp-filters" role="group" aria-label="Show">
          ${FILTERS.map(
            (name) =>
              html`<button
                type="button"
                aria-pressed=${String(filter === name)}
                @click=${() => {
                  filter = name;
                  paint();
                }}
              >
                ${capital(name)}
              </button>`,
          )}
        </div>
      </div>
      <div class="lf-fp-list">
        ${
          shown.length
            ? repeat(
                shown,
                (thread) => thread.key,
                (thread) =>
                  html`<button
                    type="button"
                    class="lf-fp-thread"
                    ?data-unread=${unread(thread)}
                    ?data-resolved=${thread.resolved}
                    @click=${() => open({ view: "thread", thread: thread.key })}
                  >
                    <span class="lf-fp-label">${threadSummary(thread).topic}</span>
                    <span class="lf-fp-value">${threadStatus(thread)}</span>
                  </button>`,
              )
            : html`<p class="lf-fp-empty">${empty}</p>`
        }
      </div>`;
  }

  // A thread inside the panel is drawn by Leaf's own conversation reader: the panel
  // registers as the page's primary thread presentation (application.js,
  // `registerThreadPresentation`) and gives the open thread's messages an outlet
  // here. Leaf draws each message there, with its reactions, rewrites, read marks and
  // agent-authored widgets, and holds news that would move what the reader is reading
  // behind its own notice. The reply is the panel's field below, not a box in the
  // outlet. A thread anchored to a passage stays the page's: its card opens beside
  // the words it is about.
  let presentation = null;
  const outletOf = () =>
    stage.querySelector(
      '.lf-fp-view[data-view="thread"]:not([data-leaving]) .lf-fp-outlet',
    );
  function nominate(collection, parts) {
    const top = trail.at(-1);
    if (top?.view !== "thread") return;
    const outlet = outletOf();
    const thread = collection.threads.find(
      (candidate) => candidate.key === top.thread || candidate.id === top.thread,
    );
    if (!outlet || !thread) return;
    for (const message of thread.msgs) parts.message(thread.key, message.key, outlet);
  }
  // A deliberate view change shows the reader the whole current thread.
  function present({ release = false } = {}) {
    if (!presentation) return Promise.resolve();
    return presentation
      .update({ release })
      .then(() => landReader())
      .catch(() => {});
  }

  function threadView(key) {
    const thread = threadByKey(key);
    if (!thread)
      return html`<p class="lf-fp-empty">This thread is not on the page.</p>`;
    return html`<div class="lf-fp-messages lf-fp-outlet"></div>`;
  }

  // ---------- Questions: answered where they are read ----------
  // The three lists are the publisher's (`readQueues`): what waits on the user, on the
  // agent, and what is done. An item the user answers here stays where it stood, saying
  // its answer and offering Undo, until the view closes, so answering one question never
  // carries the next under the pointer.
  let queueTab = "you";
  let seated = null; // queue item keys standing in the open Questions view
  // The height each seated card first stood at, which it keeps while seated, so an
  // answer that shortens it moves nothing below.
  const seatHeights = new Map();
  const QUEUE_TABS = Object.freeze({
    you: "On you",
    agent: "On the agent",
    done: "Done",
  });
  const queueLists = () => {
    const reading = readQueues();
    return reading.phase === "ready"
      ? { you: reading.questions, agent: reading.tasks, done: reading.done }
      : { you: [], agent: [], done: [] };
  };

  // The undo list's entry for the gesture that answered an ask, where it can still be
  // taken back (undo.js).
  const answerGesture = (ask) => {
    const id = ask?.answer?.event?.id ?? ask?.answer?.event;
    if (!id) return null;
    const entry = readApplication().effective.view?.undo.find(
      ({ event }) => event.id === id || event.attempt === id,
    );
    return entry?.event ?? null;
  };
  const tabLabel = (tab, lists) =>
    `${tab === "agent" ? `On ${agentName()}` : QUEUE_TABS[tab]}${
      tab === "done" ? "" : ` ${lists[tab].length}`
    }`;

  function questionCard(item, list) {
    const ask = item.kind === "ask" ? item.ask : null;
    const thread = item.thread ? threadByKey(item.thread) : null;
    // A prose ask is a message in its thread: the thread names it, and the message's
    // words, as they read, are its prompt.
    const message =
      ask?.source.kind === "reply" && thread
        ? thread.msgs.find((candidate) => candidate.id === ask.message)
        : null;
    const title = message ? threadSummary(thread).topic : queueTitle(item);
    const said = message
      ? messageReading(message, { panel: false, reactions: [], workflows: [] }).body
          .plainText
      : ask?.prompt?.text;
    const prompt = said && said.trim() !== title.trim() ? said : "";
    const answered = ask && ask.status !== "open";
    const choices =
      ask && !answered && ask.source.kind === "widget"
        ? questionView.choicesOf(ask)
        : null;
    const gesture = answered ? answerGesture(ask) : null;
    const discuss = thread
      ? html`<button
          type="button"
          class="lf-fp-quiet"
          @click=${() => open({ view: "thread", thread: thread.key })}
        >
          Discuss
        </button>`
      : nothing;
    const arrive = html`<button
      type="button"
      class="lf-fp-quiet"
      @click=${() => {
        close();
        void (ask ? questionView.open(ask.id) : queueActions.open(queueItemKey(item)));
      }}
    >
      Show
    </button>`;
    let answers;
    if (list !== "you" && !answered)
      answers = html`<span class="lf-fp-said"
          >${item.running?.text ?? workflowLabel(item.workflow) ?? ""}</span
        >${thread ? discuss : nothing}`;
    else if (answered)
      answers = html`<span class="lf-fp-said">${questionEnding(ask)}</span>${
          gesture
            ? html`<button
                type="button"
                class="lf-fp-quiet"
                @click=${() => withdraw(gesture)}
              >
                Undo
              </button>`
            : nothing
        }`;
    else if (ask?.source.kind === "approval") {
      const approval = approvalReading();
      answers = html`<button
        type="button"
        class="lf-fp-answer"
        ?disabled=${Boolean(approval?.reason)}
        title=${approval?.reason ?? nothing}
        @click=${() => approve()}
      >
        ${approval?.text ?? "Approve version"}
      </button>`;
    } else if (choices?.length)
      answers = html`${choices.map(
        (choice) =>
          html`<button
            type="button"
            class="lf-fp-answer"
            aria-pressed=${String(choice.chosen)}
            @click=${() => {
              choice.press();
              paint();
            }}
          >
            ${capital(choice.label)}
          </button>`,
      )}${discuss}`;
    else if (item.offers?.done)
      answers = html`<button
          type="button"
          class="lf-fp-answer"
          @click=${() => queueActions.done(queueItemKey(item))}
        >
          Done</button
        >${discuss}${arrive}`;
    else if (ask?.source.kind === "reply" && thread)
      answers = html`<button
        type="button"
        class="lf-fp-answer"
        @click=${() => open({ view: "thread", thread: thread.key })}
      >
        Reply
      </button>`;
    else answers = html`${arrive}${discuss}`;
    const key = queueItemKey(item);
    return html`<section
      class="lf-fp-question"
      data-list=${list}
      data-key=${key}
      style=${seatHeights.has(key) ? `min-height: ${seatHeights.get(key)}px` : ""}
    >
      ${
        prompt
          ? html`<h3 class="lf-fp-qtitle">${title}</h3>
              <p class="lf-fp-prompt">${prompt}</p>`
          : html`<h3 class="lf-fp-qtitle lf-fp-whole">${title}</h3>`
      }
      <div class="lf-fp-answers">${answers}</div>
    </section>`;
  }

  function questionsView() {
    const lists = queueLists();
    const all = [...lists.you, ...lists.agent, ...lists.done];
    const byKey = new Map(all.map((item) => [queueItemKey(item), item]));
    const current = lists[queueTab].map(queueItemKey);
    // The seats this opening of the view holds: those it showed, still in the reading
    // wherever they now stand, then any that joined this list since.
    seated = [
      ...(seated ?? []).filter((key) => byKey.has(key)),
      ...current.filter((key) => !(seated ?? []).includes(key)),
    ];
    const items = seated.map((key) => byKey.get(key));
    return html`<div class="lf-fp-tools">
        <div class="lf-fp-filters" role="group" aria-label="Show">
          ${Object.keys(QUEUE_TABS).map(
            (tab) =>
              html`<button
                type="button"
                aria-pressed=${String(queueTab === tab)}
                @click=${() => {
                  queueTab = tab;
                  seated = null;
                  seatHeights.clear();
                  paint();
                }}
              >
                ${tabLabel(tab, lists)}
              </button>`,
          )}
        </div>
      </div>
      ${
        items.length
          ? repeat(items, queueItemKey, (item) =>
              questionCard(
                item,
                lists.you.includes(item)
                  ? "you"
                  : lists.agent.includes(item)
                    ? "agent"
                    : "done",
              ),
            )
          : html`<p class="lf-fp-empty">
              ${
                {
                  you: "Nothing waits on you.",
                  agent: `${agentName()} owes nothing here.`,
                  done: "Nothing is done yet.",
                }[queueTab]
              }
            </p>`
      }`;
  }

  function viewTemplate(route) {
    switch (route.view) {
      case "menu":
        return menuView();
      case "threads":
        return threadsView();
      case "thread":
        return threadView(route.thread);
      case "questions":
        return questionsView();
      case "versions":
        return versionsView();
      case "layout":
        return layoutView();
      case "group":
        return groupView(route.group);
    }
    return nothing;
  }

  // ---------- paint ----------
  // Folding to the leaf and unfolding again change the box's width in one step: a
  // width tween moves every centred control with it, and on a slow machine its last
  // frame lands after the press's input window, as motion nobody asked for.
  function setRest(rest) {
    prefs().set("rest", rest);
    trail = [];
    paint();
    if (rest === "mark") focusDestination(leaf, "move");
  }

  // A paint can blur what it removes, and the blur asks for a paint; that one runs
  // once this has finished rather than inside it.
  let painting = false;
  let again = false;
  function paint() {
    if (painting) {
      again = true;
      return;
    }
    painting = true;
    try {
      paintNow();
    } finally {
      painting = false;
    }
    if (again) {
      again = false;
      paint();
    }
    landReader();
    seatQuestions();
  }
  function seatQuestions() {
    if (trail.at(-1)?.view !== "questions") return;
    for (const card of stage.querySelectorAll(
      ".lf-fp-view:not([data-leaving]) .lf-fp-question[data-key]",
    ))
      if (!seatHeights.has(card.dataset.key))
        seatHeights.set(card.dataset.key, card.getBoundingClientRect().height);
  }
  // A thread the reader opens, or answers, or asks to see the news of, stands at its end.
  function landReader() {
    const top = trail.at(-1);
    if (!landAtEnd || top?.view !== "thread" || top.thread !== landAtEnd) return;
    const view = stage.querySelector(
      '.lf-fp-view[data-view="thread"]:not([data-leaving])',
    );
    if (!view || !outletOf()?.childElementCount) return;
    landAtEnd = null;
    view.scrollTop = view.scrollHeight;
  }
  function paintNow() {
    const top = trail.at(-1) ?? null;
    const prefsNow = prefs();
    keeps(host, "data-display", prefsNow.display);
    keeps(host, "data-rest", prefsNow.rest);
    keeps(host, "data-open", top ? top.view : null);
    keeps(mark, "class", `lf-dot${status.tone ? ` ${status.tone}` : ""}`);
    keeps(leaf, "aria-label", `Page controls · ${status.summary}`);
    keeps(leaf, "aria-expanded", String(top?.view === "menu"));
    keepsText(peek, status.explanation || status.summary);
    if (top) keeps(peek, "data-shown", null);

    const views = [leaving, top].filter(Boolean);
    render(
      repeat(
        views,
        routeKey,
        (route) =>
          html`<div
            class="lf-fp-view"
            tabindex="-1"
            data-view=${route.view}
            style=${route.view === "threads" ? `--lf-fp-rows: ${threads().length}` : nothing}
            ?data-leaving=${route === leaving}
          >
            ${viewTemplate(route)}
          </div>`,
      ),
      stage,
    );

    const parent = trail.at(-2);
    render(
      top
        ? html`<button
              type="button"
              class="lf-fp-back"
              ?hidden=${!parent}
              aria-label=${parent ? `Back to ${titleOf(parent)}` : nothing}
              @click=${back}
            >
              <span aria-hidden="true">‹</span> ${parent ? titleOf(parent) : ""}
            </button>
            <h2 class="lf-fp-title">
              ${titleOf(top)}${
                top.view === "threads"
                  ? html`<span class="lf-fp-count">${threads().length}</span>`
                  : nothing
              }
            </h2>
            <button type="button" class="lf-fp-close" @click=${close}>Close</button>`
        : nothing,
      head,
    );

    // The field: the destination's own editor stands in its place.
    const current = editor(destination());
    if (field.firstElementChild !== current.box) field.replaceChildren(current.box);
    current.sync();
    const thread = top?.view === "thread" ? threadByKey(top.thread) : null;
    const holds = Boolean(loadDraft(destination())?.trim());
    const showTo = Boolean(thread) || writing || holds;
    const toPage = () =>
      html`<button
        type="button"
        @click=${() => {
          close();
          void threadActions.open(thread.key, { part: null });
        }}
      >
        On the page
      </button>`;
    keepsText(
      toDest,
      showTo
        ? thread
          ? thread.resolved
            ? "Resolved · its history stays here"
            : replyWords(thread)
          : "Comment on this page"
        : "",
    );
    render(
      showTo
        ? html`${
            thread
              ? html`${thread.anchor ? toPage() : nothing}<button
                    type="button"
                    @click=${writeOnPage}
                  >
                    New comment</button
                  ><button
                    type="button"
                    class="lf-fp-settle"
                    ?disabled=${!(thread.resolved ? thread.offers.reopen : thread.offers.resolve)}
                    @click=${() =>
                      thread.resolved
                        ? threadActions.reopen(thread.key)
                        : threadActions.resolve(thread.key)}
                  >
                    ${thread.resolved ? "Reopen" : "Resolve"}
                  </button>`
              : nothing
          }`
        : nothing,
      toActions,
    );
    keepsHidden(to, !showTo);
    keeps(to, "data-thread", thread ? "" : null);
    // While the user writes, the field takes the row and what waits moves up beside
    // where the words go, as the prototype seats it: the field grows into the room the
    // counts leave, so the field the user pressed stays where it was.
    // The first word typed makes that room, not the press that put the caret there, so
    // a click into the field moves nothing.
    const up = Boolean(thread) || holds;
    const home = up ? to : row;
    if (quick.parentNode !== home) move(home, quick, up ? toActions : null);
    keeps(host, "data-writing", up ? "" : null);

    // Each count keeps its room whether or not anything waits, so a count arriving or
    // leaving moves nothing beside it (AGENTS.md, "Generated interface first appears in
    // its settled position").
    const questions = questionCount();
    const news = newCount();
    // The next step of what the user is doing now, such as leaving Draw mode or
    // commenting on the words a finger selected, stands in the counts' place while that
    // gesture holds it, as it stands on the banner's row (banner-toolbar.js, `gesture`).
    const steps = rows().filter((entry) => entry.gesture);
    keeps(quick, "data-steps", steps.length ? "" : null);
    if (steps.length) {
      render(
        html`${repeat(
          steps,
          (entry) => entry.key,
          (entry) =>
            html`<button
              type="button"
              class="lf-fp-chip lf-fp-step"
              ?disabled=${entry.disabled}
              @mousedown=${(event) => event.preventDefault()}
              @click=${() => entry.press()}
            >
              ${entry.label}
            </button>`,
        )}`,
        quick,
      );
    } else
      render(
        html`<button
            type="button"
            class="lf-fp-chip lf-fp-questions"
            ?data-none=${!questions}
            ?inert=${!questions}
            aria-hidden=${questions ? nothing : "true"}
            @click=${() => open({ view: "questions" })}
            aria-label=${questions ? `Questions: ${questions}` : nothing}
          >
            ${iconTemplate("question", "lf-action-icon lf-fp-icon")}<span
              class="lf-fp-word"
              >Questions</span
            >
            <span class="lf-fp-num">${questions || ""}</span></button
          ><button
            type="button"
            class="lf-fp-chip lf-fp-desk"
            @click=${() => open({ view: "group", group: "annotate" })}
          >
            Annotate</button
          ><button
            type="button"
            class="lf-fp-chip lf-fp-news"
            ?data-none=${!news}
            ?inert=${!news}
            aria-hidden=${news ? nothing : "true"}
            aria-label=${`${news} ${news === 1 ? "thread" : "threads"} with news`}
            @click=${() => {
              filter = "unread";
              query = "";
              open({ view: "threads" });
            }}
          >
            ${iconTemplate("comment", "lf-action-icon lf-fp-icon")}<span
              class="lf-fp-num"
              >${news || ""}</span
            ><span class="lf-fp-word"> new</span>
          </button>`,
        quick,
      );

    // Moderate adds where the reader stands and the keys that act there.
    const typing = host.contains(focused()) && focused()?.localName === "leaf-text";
    const keyWords = coarse()
      ? `${threads().length} threads`
      : thread
        ? html`<kbd>Esc</kbd> back`
        : typing
          ? html`<kbd>⌘/Ctrl ↵</kbd> send`
          : html`<kbd>c</kbd> comment · <kbd>?</kbd> keys`;
    const position = thread
      ? `Thread ${threads().indexOf(thread) + 1} of ${threads().length}${news ? ` · ${news} new` : ""}`
      : news
        ? `${news} new`
        : coarse()
          ? ""
          : `${threads().length} threads`;
    render(
      prefsNow.display === "moderate"
        ? html`<span class="lf-fp-keys">${keyWords}</span
            ><span class="lf-fp-where">${position}</span>`
        : nothing,
      foot,
    );
  }

  // ---------- gestures ----------
  leaf.addEventListener("click", () => {
    if (prefs().rest === "mark") prefs().set("rest", "row");
    open({ view: "menu" });
  });
  const showPeek = (on) => keeps(peek, "data-shown", on && !trail.length ? "" : null);
  leaf.addEventListener("pointerenter", () => showPeek(true));
  leaf.addEventListener("pointerleave", () => showPeek(false));
  leaf.addEventListener("focus", () => showPeek(leaf.matches(":focus-visible")));
  leaf.addEventListener("blur", () => showPeek(false));
  // Escape steps back along the trail, one view at a time, then out of the field.
  keys(host, "In the floating panel", [
    {
      id: "panel.floating.back",
      keys: ["Escape"],
      description: () =>
        trail.length ? `Back from ${titleOf(trail.at(-1))}` : "Leave the comment field",
      title: () => (trail.length ? "back" : "leave field"),
      when: () => trail.length > 0 || host.contains(focused()),
      run: () => {
        if (trail.length) back();
        else releaseFocus();
      },
    },
  ]);
  // Writing begins in the field and lasts while the user stays in the panel, so the
  // destination line stays put while they press Resolve or a filter.
  // Where the reader stood before stepping into the panel, which a row's command that
  // acts on that place gets back (history.js, `readPlace`).
  let heldStanding = null;
  host.addEventListener(
    "pointerdown",
    () => {
      if (!host.contains(focused())) heldStanding = readPlace();
    },
    true,
  );
  onStanding((node, _cause, left) => {
    const inside = host.contains(node);
    if (inside && left && !host.contains(left)) heldStanding = readPlace(left);
    const next = inside ? writing || node.localName === "leaf-text" : false;
    if (next === writing && !inside) return;
    writing = next;
    paint();
  });
  // A press on the page puts away what stands open above the row.
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (trail.length && !event.composedPath().includes(host)) close();
    },
    true,
  );

  // The Threads and Questions doors are the banner's controls, which every route to
  // those surfaces presses, Go-to's included. In this chrome the panel stands for
  // them, so their press opens its view instead.
  for (const [door, view] of [
    [toggleBtn, "threads"],
    [queueBtn, "questions"],
  ])
    door.addEventListener(
      "click",
      (event) => {
        event.stopImmediatePropagation();
        event.preventDefault();
        if (view === "threads") {
          filter = "all";
          query = "";
        }
        open({ view });
      },
      { capture: true },
    );

  // Version travel (Shift+V, `g V`, the picker's own press) opens the versions menu,
  // whichever route asks; in this chrome that opening is the panel's Versions view.
  versionMenu.addEventListener("beforetoggle", (event) => {
    if (event.newState !== "open") return;
    event.preventDefault();
    open({ view: "versions" }, { reopen: true });
  });

  // The page's comment box in this chrome, as `c` and Resume writing find it
  // (composing/surface.js, `commentDestination`).
  const pageComment = Object.freeze({
    get box() {
      return editor("general").input;
    },
    open: writeOnPage,
    close: () => {},
    sync: () => editor("general").sync(),
  });

  function mount(parent) {
    parent.append(host);
    follow.observe(inner);
    presentation = registerThreadPresentation(host, {
      render: nominate,
      // The thread's reply is the panel's field, standing for the thread open here.
      replyBox: (key) => {
        const top = trail.at(-1);
        return top?.view === "thread" && threadByKey(top.thread)?.key === key
          ? editor(`reply:${key}`).input
          : null;
      },
      // A thread about the whole page opens here; one about a passage opens beside it.
      reveal: (key, request) => {
        const thread = threadByKey(key);
        if (!thread || thread.anchor) return false;
        open(
          { view: "thread", thread: thread.key },
          { reopen: true, focus: request.focus !== false },
        );
        return present({ release: true });
      },
    });
    watchStatus((reading) => {
      status = reading;
      paint();
    });
    watchBannerRows(() => paint());
    watchThreads(host, () => paint());
    watchQueues(host, () => paint());
    watchSemantic(() => paint());
    versionPicker.watch(() => paint());
    document.addEventListener("lf-chrome-preference", () => paint());
    paint();
  }

  return { host, mount, open, close, pageComment };
}
