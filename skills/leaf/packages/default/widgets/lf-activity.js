/* lf-activity: the page's history as a feed, newest first.
 *
 * The server's history reading is the only input and this list stores nothing: every
 * reading of `watchHistory` restates the whole feed. A row says who moved (You for the
 * user, the agent's own voice for an agent, Page for what the page did by itself), what
 * they did, the thing they did it to, and how long ago.
 *
 * What a move was is the server's: the thread it belongs to and that thread's title,
 * whether a later undo took it back, and for a widget gesture the words its ids had in
 * the document it was made in, under that document's declaration of the widget. A
 * version that rewords or removes an option therefore leaves the row as the user made
 * it. This module words those facts and names the places on the page it links to.
 *
 * A place is named on the page the user is reading, since that is where the row leads.
 * An element is named by `addressableName`, the name the authoring contract gives it;
 * where something happened is the nearest element from there up to the column that has
 * one. A quoted passage is named as Threads names its anchor (`anchorLabel`). An element
 * the contract names nowhere is named by its own words (`addressableSays`), cut short.
 *
 * The thing is the row's way there: a widget or section is an ordinary fragment link,
 * so the browser owns that travel as it does for lf-toc, and a thread is a button
 * onto `openThread`, which chooses the thread's inline destination or Threads the same
 * way a mark and t/T do. Links and buttons are the keyboard route: each is a Tab stop
 * and a go-to target.
 *
 * An excerpt is the words its Markdown renders, never the source.
 *
 * Rows are keyed by event id and only new rows are inserted, so a user tabbing down
 * the feed keeps their place when the log grows or the clock moves a timestamp. */
import {
  addressableName,
  addressableSays,
  agentName,
  ago,
  anchorLabel,
  layerFact,
  loadMarkdown,
  markdownReady,
  markdownWords,
  offer,
  once,
  openThread,
  relabel,
  watchHistory,
} from "/runtime/widget-api.js";

const NAME = 60;

const clip = (text, length) => {
  const flat = String(text ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > length ? `${flat.slice(0, length - 1).trimEnd()}…` : flat;
};

// Where something happened: the nearest named element from it up to the column, else
// the thing's own words, else its id.
function nameOf(id) {
  const element = id ? document.getElementById(id) : null;
  if (!element) return id || "the page";
  for (let at = element; at && at.localName !== "main"; at = at.parentElement) {
    const name = clip(addressableName(at), NAME);
    if (name) return name;
  }
  return clip(addressableSays(element), NAME) || id;
}

// A comment's place: a passage, a drawing's part, a datum, or a design subject as
// Threads names it; a whole element by where it is.
function placeName(anchor, about) {
  // A bare quote is cut inside its marks, so a long one still reads as a quote.
  if (anchor?.quote && !anchor.datum && about !== "design")
    return quoted(clip(anchor.quote, NAME));
  if (anchor?.visual || anchor?.datum || about === "design")
    return clip(anchorLabel(anchor, about), NAME);
  return nameOf(anchor?.section ?? null);
}

const reaction = (token) => layerFact("$reactions")?.tokens?.[token]?.glyph ?? token;

const actorOf = (row) =>
  row.author === "user"
    ? "You"
    : row.author === "page"
      ? "Page"
      : row.agent || (row.author === "agent" ? agentName() : row.author);

const quoted = (words) => `“${words}”`;
const named = (words) => quoted(clip(words, NAME));

// The thread's name as Threads states it: its latest title, else its opening words.
const topicOf = (thread) =>
  !thread
    ? "a thread"
    : (thread.title ?? (clip(markdownWords(thread.opening), 48) || "a drawing"));

function gesturePhrase(gesture) {
  switch (gesture.form) {
    case "choice":
      return `chose ${gesture.chosen.map(named).join(", ") || "nothing"} in`;
    case "move":
      return `moved ${named(gesture.unit)} to ${named(gesture.to)} in`;
    case "edit":
      return "edited";
    case "add":
      return `added ${named(gesture.words)} to`;
    default:
      return `recorded ${quoted(gesture.verb)} on`;
  }
}

// One served row as the words and the way there it is drawn with.
function describe(row) {
  const thread = (what, label) => ({
    what,
    thread: row.thread?.id,
    label: label ?? quoted(topicOf(row.thread)),
  });
  switch (row.kind) {
    case "comment":
      if (row.token)
        return {
          what: `reacted ${reaction(row.token)} on`,
          widget: row.anchor?.section ?? null,
          label: placeName(row.anchor, row.about),
        };
      if (row.holds) return thread("paused", nameOf(row.holds));
      return thread(
        row.drawing && !row.excerpt ? "drew on" : "commented on",
        placeName(row.anchor, row.about),
      );
    case "reply":
      return thread(row.token ? `reacted ${reaction(row.token)} in` : "replied in");
    case "edit":
      return thread("edited a message in");
    case "resolve":
      return thread("resolved");
    case "unresolve":
      return thread("reopened");
    case "action":
      return { what: gesturePhrase(row.gesture), widget: row.widget };
    case "report":
      return { what: `reported ${quoted(row.value)} on`, widget: row.widget };
    case "request":
      return { what: `requested ${quoted(row.operation)} in`, widget: row.widget };
    case "receipt":
      return {
        what: `${row.status === "succeeded" ? "completed" : "failed"} ${quoted(row.operation)} in`,
        widget: row.widget,
      };
    case "note":
      return { what: `published v${row.version}` };
    default:
      return { what: `approved v${row.version}` };
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
    #history = [];

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
      this.#stop ??= watchHistory(this, (history) => {
        this.#history = history;
        this.#render(history);
        // Excerpts painted from the source take the parser's words once it lands.
        if (!markdownReady())
          loadMarkdown().then((loaded) => {
            if (loaded && this.#stop) this.#render(this.#history);
          });
      });
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }

    #render(history) {
      const rows = history.map((served) => ({
        ...describe(served),
        excerpt: served.excerpt ? markdownWords(served.excerpt) : null,
        id: served.id,
        ts: served.ts,
        author: served.author,
        actor: actorOf(served),
        undone: served.undone,
      }));

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
