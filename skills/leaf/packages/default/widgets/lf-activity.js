/* lf-activity: the page's history as a feed, newest first.
 *
 * The event log is the only input and this list stores nothing: every reading of
 * `watchHistory` restates the whole feed. A row says who moved (You for the reader, the
 * agent's own voice for an agent, Page for what the page did by itself), what they did,
 * the thing they did it to, and how long ago. The thing is the row's way there: a
 * widget or section is an ordinary fragment link, so the browser owns that travel as it
 * does for lf-toc, and a conversation is a button onto `openThread`, which chooses the
 * thread's inline destination or Threads the same way a mark and t/T do. Links and
 * buttons are the keyboard route: each is a Tab stop and a go-to target.
 *
 * Bookkeeping stays out: `read`, `pickup` (a delivery fact the banner already reports as
 * activity), `summary`, `conversation_title`, and `error`. An `undo` is not its own row;
 * it marks the gesture it took back, which is what a reader scanning the feed needs to
 * know about that gesture.
 *
 * Rows are keyed by event id and only new rows are inserted, so a reader tabbing down
 * the feed keeps their place when the log grows or the clock moves a timestamp. */
import {
  agentName,
  ago,
  declarationFor,
  layerFact,
  offer,
  once,
  openThread,
  relabel,
  watchHistory,
  wrote,
} from "/runtime/widget-api.js";

const LIMIT = 50;
const NAMING = ":scope > :is(strong, h1, h2, h3, h4, h5, h6, header)";

const clip = (text, length) => {
  const flat = String(text ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > length ? `${flat.slice(0, length - 1).trimEnd()}…` : flat;
};

// An element's own name: its label, else the heading or lead words it opens with.
function ownName(element) {
  const lead = element.querySelector(NAMING);
  return clip(element.getAttribute("label"), 60) || (lead ? clip(wrote(lead), 60) : "");
}

// Where something happened: the nearest named element from it up to the column, else
// its id.
function nameOf(id) {
  const element = id ? document.getElementById(id) : null;
  if (!element) return id || "the page";
  for (let at = element; at && at.localName !== "main"; at = at.parentElement) {
    const name = ownName(at);
    if (name) return name;
  }
  return id;
}

// A choice or a moved item is named by its own words, since it is the thing itself.
function itemName(id) {
  const element = id ? document.getElementById(id) : null;
  if (!element) return id;
  return ownName(element) || clip(wrote(element), 60) || id;
}

const reaction = (token) => layerFact("$reactions")?.tokens?.[token]?.glyph ?? token;

const actorOf = (event) =>
  event.author === "user"
    ? "You"
    : event.author === "page"
      ? "Page"
      : event.agent || (event.author === "agent" ? agentName() : event.author);

function threadRoot(event, byId) {
  let current = event;
  const seen = new Set();
  while (current?.parent && !seen.has(current.id)) {
    seen.add(current.id);
    current = byId.get(current.parent);
  }
  return current?.kind === "comment" ? current : null;
}

const quoted = (words) => `“${words}”`;

// The conversation's name as Threads states it: its latest title, else its opening words.
function topicOf(root, titles) {
  if (!root) return "a thread";
  return titles.get(root.id) ?? clip(root.text || root.token || "a drawing", 48);
}

function actionPhrase(event) {
  const element = document.getElementById(event.widget);
  const state = declarationFor(element, "x-state")?.[event.action];
  const record = state?.record;
  const detail = event.detail ?? {};
  if (record?.kind === "attribute") {
    const ids = [detail[record.value]].flat().filter(Boolean);
    const chosen = ids.map((id) => quoted(itemName(id))).join(", ") || "nothing";
    return { what: `chose ${chosen} in`, widget: event.widget };
  }
  if (record?.kind === "position")
    return {
      what: `moved ${quoted(itemName(detail[state.unit]))} to ${quoted(itemName(detail[record.value]))} in`,
      widget: event.widget,
    };
  if (record?.kind === "body") return { what: "edited", widget: event.widget };
  return { what: `recorded ${quoted(event.action)} on`, widget: event.widget };
}

function reportPhrase(event) {
  const element = document.getElementById(event.widget);
  const report = declarationFor(element, "x-report")?.[event.action];
  const detail = event.detail ?? {};
  const value = report?.record?.value ? detail[report.record.value] : null;
  return {
    what: `reported ${quoted(value ?? event.action)} on`,
    widget: event.widget,
    excerpt: report?.update ? detail[report.update] : null,
  };
}

// A request names its operation the way the holder offers it: the offered child's words.
function operationName(request) {
  const holder = document.getElementById(request?.widget);
  const offers = declarationFor(holder, "x-request")?.offers ?? {};
  for (const [tag, attribute] of Object.entries(offers)) {
    const child = [...(holder?.children ?? [])].find(
      (candidate) =>
        candidate.localName === tag &&
        candidate.getAttribute(attribute) === request.action,
    );
    const words = child && clip(wrote(child.querySelector(NAMING) ?? child), 60);
    if (words) return words;
  }
  return request?.action?.replaceAll("-", " ") ?? "request";
}

// One event as a row description, or null for an event the feed leaves out: `read`,
// `pickup`, `summary`, `conversation_title`, `error`, and `undo` reach the default.
function describe(event, context) {
  const { byId, titles } = context;
  const root = threadRoot(
    event.kind === "edit" ? byId.get(event.message) : event,
    byId,
  );
  const thread = (what, label, excerpt) => ({
    what,
    thread: root?.id,
    label: label ?? quoted(topicOf(root, titles)),
    excerpt,
  });
  switch (event.kind) {
    case "comment": {
      const where = event.holds ?? event.anchor?.section ?? null;
      if (event.token)
        return {
          what: `reacted ${reaction(event.token)} on`,
          widget: where,
          label: nameOf(where),
        };
      if (event.holds) return thread("paused", nameOf(where), event.text);
      return thread(
        event.drawing && !event.text ? "drew on" : "commented on",
        nameOf(where),
        event.text,
      );
    }
    case "reply":
      return event.token
        ? thread(`reacted ${reaction(event.token)} in`)
        : thread("replied in", undefined, event.text);
    case "edit":
      return thread("edited a message in");
    case "resolve":
      return thread("resolved");
    case "unresolve":
      return thread("reopened");
    case "action":
      return actionPhrase(event);
    case "report":
      return reportPhrase(event);
    case "request":
      return {
        what: `requested ${quoted(operationName(event))} in`,
        widget: event.widget,
      };
    case "receipt": {
      const request = byId.get(event.request);
      return {
        what: `${event.status === "succeeded" ? "completed" : "failed"} ${quoted(operationName(request))} in`,
        widget: request?.widget,
        excerpt: event.text,
      };
    }
    case "note":
      return { what: `published v${event.version}`, excerpt: event.text };
    case "done":
      return { what: `approved v${event.version}` };
    default:
      return null;
  }
}

function target(row) {
  if (row.thread) {
    const button = offer("button", "lf-activity-target");
    relabel(button, row.label, { says: "echo" });
    button.addEventListener("click", () => openThread(row.thread, { focus: "thread" }));
    return button;
  }
  if (!row.widget && !row.label) return null;
  const label = row.label ?? nameOf(row.widget);
  if (!row.widget || !document.getElementById(row.widget)) {
    const span = document.createElement("span");
    span.className = "lf-activity-target";
    span.textContent = label;
    return span;
  }
  const link = document.createElement("a");
  link.className = "lf-activity-target";
  link.href = `#${encodeURIComponent(row.widget)}`;
  link.textContent = label;
  return link;
}

function fill(item, row) {
  const avatar = document.createElement("span");
  avatar.className = "lf-activity-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = row.actor.slice(0, 1).toUpperCase();
  const line = document.createElement("p");
  line.className = "lf-activity-line";
  const actor = document.createElement("strong");
  actor.className = "lf-activity-actor";
  actor.textContent = row.actor;
  const what = document.createElement("span");
  what.className = "lf-activity-what";
  what.textContent = row.what;
  line.append(actor, " ", what);
  const place = target(row);
  if (place) line.append(" ", place);
  const time = document.createElement("time");
  time.className = "lf-activity-time";
  time.dateTime = row.ts;
  time.title = new Date(row.ts).toLocaleString();
  line.append(" ", time);
  if (row.undone) {
    const undone = document.createElement("span");
    undone.className = "lf-activity-undone";
    undone.textContent = "undone";
    line.append(" ", undone);
  }
  item.replaceChildren(avatar, line);
  const excerpt = clip(row.excerpt, 140);
  if (excerpt) {
    const said = document.createElement("p");
    said.className = "lf-activity-excerpt";
    said.textContent = excerpt;
    item.append(said);
  }
  item.dataset.lfActivityAuthor = row.author;
  item.toggleAttribute("data-lf-undone", row.undone);
}

customElements.define(
  "lf-activity",
  class extends HTMLElement {
    #stop = null;
    #list = null;
    #empty = null;
    // Event id to its row and the description it was last filled from.
    #rows = new Map();

    connectedCallback() {
      if (once(this)) {
        this.#list = document.createElement("ol");
        this.#list.className = "lf-activity-list";
        this.#list.dataset.lfGen = "1";
        this.#empty = document.createElement("p");
        this.#empty.className = "lf-activity-empty";
        this.#empty.dataset.lfGen = "1";
        this.#empty.textContent = "Nothing has happened on this page yet.";
        this.replaceChildren(this.#list, this.#empty);
      }
      this.#stop ??= watchHistory(this, (events) => this.#render(events));
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }

    #render(events) {
      const byId = new Map(events.map((event) => [event.id, event]));
      const titles = new Map();
      const undone = new Set();
      for (const event of events) {
        if (event.kind === "conversation_title")
          titles.set(event.conversation, event.title);
        if (event.kind === "undo") undone.add(event.undoes);
      }
      const context = { byId, titles };
      const rows = [];
      for (let at = events.length - 1; at >= 0 && rows.length < LIMIT; at -= 1) {
        const event = events[at];
        const described = describe(event, context);
        if (!described) continue;
        rows.push({
          ...described,
          id: event.id,
          ts: event.ts,
          author: event.author,
          actor: actorOf(event),
          undone: undone.has(event.id),
        });
      }

      const kept = new Set();
      let next = this.#list.firstElementChild;
      for (const row of rows) {
        kept.add(row.id);
        const key = JSON.stringify(row);
        let seat = this.#rows.get(row.id);
        if (!seat) {
          const item = document.createElement("li");
          item.className = "lf-activity-row";
          seat = { item, key: null };
          this.#rows.set(row.id, seat);
        }
        const { item } = seat;
        if (seat.key !== key) {
          fill(item, row);
          seat.key = key;
        }
        // Read synchronously, so the shared clock repaints this reading when it turns.
        const time = item.querySelector(".lf-activity-time");
        const when = ago(row.ts);
        if (time.textContent !== when) time.textContent = when;
        if (item !== next) this.#list.insertBefore(item, next);
        else next = next.nextElementSibling;
      }
      for (const [id, { item }] of this.#rows)
        if (!kept.has(id)) {
          item.remove();
          this.#rows.delete(id);
        }
      this.#empty.hidden = rows.length > 0;
    }
  },
);
