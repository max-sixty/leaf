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
import { html, nothing, render, repeat, unsafeHTML } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { approvalReading, approve, watchStatus } from "./banner.js";
import { bannerRows, watchBannerRows } from "./banner-toolbar.js";
import { readThreads } from "./thread/state.js";
import { watchThreads } from "./thread/watch.js";
import { threadAttention } from "./thread/workflow.js";
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
import { readQueues, watchQueues } from "./queue-api.js";
import { versionPicker } from "./version-picker.js";
import { reducedMotion } from "./motion.js";
import { pagePresented } from "./page-paint.js";
import { focusDestination } from "./focus.js";
import { sizeObserver } from "./rendering.js";
import { watchSemantic } from "./semantic-state.js";

const prefs = () => document.documentElement.lfChrome;
// The Codex panel's tween: one strong ease-out for every change of size and fade.
const EASE = "cubic-bezier(.23, 1, .32, 1)";
const RESIZE_MS = 300;
const FADE_MS = 180;

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

export function createFloatingPanel({ wireInput, threadActions }) {
  const host = el("section", "lf-ui lf-floating-panel");
  host.setAttribute("aria-label", "Leaf");
  const card = el("div", "lf-fp-card");
  const inner = el("div", "lf-fp-inner");
  const stage = el("div", "lf-fp-stage");
  const head = el("div", "lf-fp-head");
  const to = el("div", "lf-fp-to");
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
    const hint = () => (key ? `Reply to ${threadTitle(key)}` : status.summary);
    const sync = wireInput(input, {
      hint,
      accessibleName: () => (key ? `Reply to ${threadTitle(key)}` : "Comment on the page"),
      sends: "send",
      sendBtn: send,
      save: (text) => {
        saveDraft(ctx, text);
        tellDraft(ctx, text);
      },
      send: (_text, raw, owns) => {
        const handle = sendMessage(ctx, owns, (attempt) =>
          key
            ? threadActions.reply(key, raw, { attempt })
            : threadActions.create({ attempt, text: raw }),
        );
        if (!handle) return;
        // A page comment starts a thread, which the panel opens so its reply can follow
        // in the same field.
        if (!key) open({ view: "thread", thread: handle.id }, { replace: true });
      },
    });
    sync();
    const stop = mirrorDraft(input, sync, ctx, { retained: true });
    input.addEventListener("focus", () => {
      writing = true;
      paint();
    });
    held = { ctx, box, input, sync, stop };
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
  const openCount = () => threads().filter((thread) => !thread.resolved).length;
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
  function open(route, { replace = false } = {}) {
    const before = trail.at(-1);
    if (before && routeKey(before) === routeKey(route) && !replace) {
      close();
      return;
    }
    trail = replace && before ? [...trail.slice(0, -1), route] : pathTo(route);
    if (replace && route.view === "thread" && trail.length === 1)
      trail = pathTo(route);
    transition(before);
  }
  function back() {
    const before = trail.at(-1);
    trail = trail.slice(0, -1);
    transition(before);
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
  function transition(before) {
    const after = trail.at(-1);
    const changed =
      (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
    leaving = changed && before && after ? before : null;
    paint();
    if (!changed || reducedMotion() || !pagePresented()) {
      leaving = null;
      paint();
      focusView(after);
      return;
    }
    const arriving = stage.querySelector(".lf-fp-view:not([data-leaving])");
    arriving?.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "none" },
      ],
      { duration: FADE_MS, easing: EASE },
    );
    const gone = stage.querySelector(".lf-fp-view[data-leaving]");
    const fade = gone?.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: FADE_MS * 0.7,
      easing: "linear",
      fill: "forwards",
    });
    const settle = () => {
      leaving = null;
      paint();
    };
    if (fade) fade.finished.then(settle, () => {});
    else leaving = null;
    focusView(after);
  }
  function focusView(route) {
    if (!route) return;
    const target =
      route.view === "threads"
        ? stage.querySelector(".lf-fp-search")
        : route.view === "thread"
          ? editors.get(destination())?.input
          : stage.querySelector(".lf-fp-view:not([data-leaving]) button");
    if (target) focusDestination(target, "move");
  }

  // ---------- views ----------
  const menuRow = (label, value, press, { urgent = false, disabled = false } = {}) =>
    html`<button
      type="button"
      class="lf-fp-item"
      ?disabled=${disabled}
      ?data-lf-urgent=${urgent}
      @click=${press}
    >
      <span class="lf-fp-label">${label}</span>${value
        ? html`<span class="lf-fp-value">${value}</span>`
        : nothing}
    </button>`;

  function rowFor(entry) {
    const view = OWN_VIEWS[entry.key];
    const value =
      entry.key === "threads"
        ? `${openCount()}${newCount() ? ` · ${newCount()} new` : ""}`
        : entry.value;
    return menuRow(
      entry.label,
      value,
      () => (view ? open({ view }) : (close(), entry.press())),
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
    return html`<p class="lf-fp-reading" data-tone=${status.tone}>
        ${status.explanation || status.summary}
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
      ${menuRow(rest === "mark" ? "Unfold to the comment field" : "Fold to the leaf", "", () =>
        setRest(rest === "mark" ? "row" : "mark"),
      )}`;
  }

  function versionsView() {
    const { rows: versions, picker } = versionPicker.model;
    const approval = approvalReading();
    return html`${versions.map((entry) =>
        menuRow(
          entry.name,
          entry.current ? "Current" : (entry.note ?? ""),
          () => versionPicker.activate(entry),
        ),
      )}
      ${versions.length ? nothing : html`<p class="lf-fp-empty">${picker.token}</p>`}
      ${approval
        ? html`<hr />
            ${menuRow(approval.text, approval.reason ?? "", () => approve(), {
              disabled: Boolean(approval.reason) && !approval.text.startsWith("✓"),
            })}`
        : nothing}`;
  }

  function threadsView() {
    const words = query.trim().toLowerCase();
    const shown = threads().filter((thread) => {
      if (filter === "unread" && !unread(thread)) return false;
      if (filter === "drafts" && !draftHasContent(`reply:${thread.key}`)) return false;
      if (filter === "resolved" && !thread.resolved) return false;
      if (!words) return true;
      const text = [threadSummary(thread).topic, thread.root.text, ...thread.msgs.map((m) => m.text)]
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
        ${shown.length
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
          : html`<p class="lf-fp-empty">${empty}</p>`}
      </div>`;
  }

  function threadView(key) {
    const thread = threadByKey(key);
    if (!thread) return html`<p class="lf-fp-empty">This thread is not on the page.</p>`;
    const messages = [thread.root, ...thread.msgs];
    return html`<div class="lf-fp-messages">
      ${repeat(
        messages,
        (message) => message.attempt ?? message.id,
        (message) => {
          const reading = messageReading(message, {
            panel: false,
            reactions: [],
            workflows: message.workflows ?? [],
          });
          return html`<article class="lf-fp-message" data-author=${message.author}>
            <header>${reading.by}${reading.workflowLabel ? html` · ${reading.workflowLabel}` : nothing}</header>
            <div class="lf-fp-body">
              ${reading.body.html ? unsafeHTML(reading.body.html) : reading.body.plainText}
            </div>
          </article>`;
        },
      )}
    </div>`;
  }

  function questionsView() {
    const { questions } = readQueues();
    return html`${questions.length
      ? questions.map((item) =>
          menuRow(item.subject ?? item.kind, "", () => {
            close();
            item.open?.();
          }),
        )
      : html`<p class="lf-fp-empty">Nothing waits on you.</p>`}`;
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
    peek.textContent = status.explanation || status.summary;
    if (top) keeps(peek, "data-shown", null);

    const views = [leaving, top].filter(Boolean);
    render(
      repeat(
        views,
        routeKey,
        (route) =>
          html`<div
            class="lf-fp-view"
            data-view=${route.view}
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
              ${titleOf(top)}${top.view === "threads"
                ? html`<span class="lf-fp-count">${threads().length}</span>`
                : nothing}
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
    render(
      showTo
        ? html`<span class="lf-fp-dest"
              >${thread ? `Reply to ${threadSummary(thread).topic}` : "Comment on this page"}</span
            >${thread
              ? html`${thread.resolved
                    ? nothing
                    : html`<button
                        type="button"
                        @click=${() => open({ view: "threads" })}
                      >
                        New comment
                      </button>`}<button
                    type="button"
                    @click=${() =>
                      thread.resolved
                        ? threadActions.reopen(thread.key)
                        : threadActions.resolve(thread.key)}
                  >
                    ${thread.resolved ? "Reopen" : "Resolve"}
                  </button>`
              : nothing}`
        : nothing,
      to,
    );
    to.hidden = !showTo;

    const questions = questionCount();
    const news = newCount();
    render(
      html`${questions
          ? html`<button
              type="button"
              class="lf-fp-chip"
              @click=${() => open({ view: "questions" })}
            >
              Questions <span class="lf-fp-num">${questions}</span>
            </button>`
          : nothing}<button
          type="button"
          class="lf-fp-chip lf-fp-desk"
          @click=${() => open({ view: "group", group: "annotate" })}
        >
          Annotate</button
        >${news
          ? html`<button
              type="button"
              class="lf-fp-chip lf-fp-news"
              aria-label=${`${news} ${news === 1 ? "thread" : "threads"} with news`}
              @click=${() => {
                filter = "unread";
                query = "";
                open({ view: "threads" });
              }}
            >
              ${news} new
            </button>`
          : nothing}`,
      quick,
    );

    render(
      prefsNow.display === "moderate"
        ? html`<span class="lf-fp-keys"><kbd>c</kbd> comment · <kbd>?</kbd> keys</span
            ><span class="lf-fp-where"
              >${thread
                ? `Thread ${threads().indexOf(thread) + 1} of ${threads().length}`
                : `${openCount()} open threads`}</span
            >`
        : nothing,
      foot,
    );
  }

  // ---------- gestures ----------
  leaf.addEventListener("click", () => {
    if (prefs().rest === "mark") {
      prefs().set("rest", "row");
      paint();
    }
    open({ view: "menu" });
  });
  const showPeek = (on) => keeps(peek, "data-shown", on && !trail.length ? "" : null);
  leaf.addEventListener("pointerenter", () => showPeek(true));
  leaf.addEventListener("pointerleave", () => showPeek(false));
  leaf.addEventListener("focus", () => showPeek(true));
  leaf.addEventListener("blur", () => showPeek(false));
  host.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (trail.length) {
      event.preventDefault();
      event.stopPropagation();
      back();
    }
  });
  host.addEventListener("focusout", (event) => {
    if (host.contains(event.relatedTarget)) return;
    writing = false;
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

  function mount(parent) {
    parent.append(host);
    follow.observe(inner);
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

  return { host, mount, open, close };
}
