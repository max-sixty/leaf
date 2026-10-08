/* lf-activity: the page's history as a feed, newest first.
 *
 * The server's history reading is the only semantic input: every
 * reading of `watchHistory` restates the whole feed. A row says who moved (You for the
 * user, Page for what the page did by itself, and otherwise the name the server serves
 * the row under), what they did, the thing they did it to, and how long ago.
 *
 * What a move was is the server's: the thread it belongs to and that thread's title,
 * whether a later undo took it back, and for a widget gesture the words its ids had in
 * the document it was made in, under that document's declaration of the widget. A
 * version that rewords or removes an option therefore leaves the row as the user made
 * it. This module words those facts and names the places on the page it links to.
 *
 * A place is named on the page the user is reading, since that is where the row leads,
 * and as the rest of the chrome names it (`addressableLabel`), else by its word. A
 * quoted passage is named as Threads names its anchor (`anchorLabel`).
 *
 * The thing is the row's way there: a widget or section is an ordinary fragment link,
 * so the browser owns that travel as it does for lf-toc, and a thread is a button
 * onto `openThread`, which chooses the thread's inline destination or Threads the same
 * way a mark and t/T do. Links and buttons are the keyboard route: each is a Tab stop
 * and a go-to target.
 *
 * An excerpt is the words its Markdown renders, never the source.
 *
 * History has no authored size. Its fixed disclosure stands from first paint; rows
 * appear only when the reader opens it. Once open, HeldReading keeps visible history
 * behind that same disclosure until the reader asks to see the change or leaves it
 * off screen. Rows retain their event identity and focus while that reading stands.
 * Tab memory retains the drawn presentation through a fresh document. Its initial
 * producer draws it before first paint, then the ready authoritative reading is
 * compared through HeldReading. This never folds events or records a decision. */
import {
  HeldReading,
  holdFocus,
  initialRender,
  tabStore,
  addressableLabel,
  addressableWord,
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
  watchOwner,
  keeps,
  keepsHidden,
  keepsText,
} from "/runtime/widget-api.js";

import { ACTIVITY_VIEW, fillActivityRow } from "./activity-view.js";

const NAME = 60;

const clip = (text, length) => {
  const flat = String(text ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > length ? `${flat.slice(0, length - 1).trimEnd()}…` : flat;
};

// Where something happened, as the chrome names it, else its word.
function nameOf(id) {
  const element = id ? document.getElementById(id) : null;
  if (!element) return id || "the page";
  return clip(addressableLabel(element), NAME) || `the ${addressableWord(element)}`;
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
      : (row.agent ?? row.author);

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
    case "note":
      return { what: `published v${row.version}` };
    default:
      return { what: `approved v${row.version}` };
  }
}

customElements.define(
  "lf-activity",
  class extends HTMLElement {
    #list = null;
    #empty = null;
    // Event id to its row and the description it was last filled from.
    #rows = new Map();
    #history = [];
    #notice = null;
    #opened = false;
    #reading = null;
    #printing = false;
    #closedReading = null;
    #restored = null;
    #ready = false;

    connectedCallback() {
      if (!once(this)) return;
      const drawing = initialRender(this);
      this.#list = drawing.list;
      this.#empty = drawing.empty;
      this.#notice = drawing.notice;
      this.#rows = drawing.rows;
      this.#opened = drawing.reading.open;
      this.#closedReading = drawing.restored ? drawing.reading.shown : null;
      this.#restored = drawing.restored ? drawing.reading.shown : null;
      for (const row of JSON.parse(drawing.reading.shown))
        this.#bind(this.#rows.get(row.id).item, row);
      this.#reading = new HeldReading(
        () => [this.#notice, this.#list, this.#empty],
        () => this.#render(this.#history),
      );
      this.#notice.addEventListener("click", () => {
        if (this.#notice.hasAttribute("data-lf-news")) this.#opened = true;
        else this.#opened = !this.#opened;
        this.#reading.release();
        this.#render(this.#history);
      });
      const paper = matchMedia("print");
      const printing = () => {
        this.#printing = paper.matches;
        this.#render(this.#history);
      };
      watchOwner(this, {
        connect: () => paper.addEventListener("change", printing),
        disconnect: () => paper.removeEventListener("change", printing),
      });
      watchHistory(this, (history, { ready }) => {
        this.#ready = ready;
        this.#history = history;
        this.#render(history);
        // Excerpts painted from the source take the parser's words once it lands.
        if (!markdownReady())
          loadMarkdown().then((loaded) => {
            if (loaded && this.isConnected) this.#render(this.#history);
          });
      });
    }

    disconnectedCallback() {
      this.#reading?.dispose();
    }

    #bind(item, row) {
      const button = item.querySelector("button.lf-activity-target");
      if (!button) return;
      relabel(button, row.label, { says: "echo" });
      button.addEventListener(
        "click",
        () => void openThread(row.thread, { focus: "thread" }),
      );
    }

    #render(history) {
      if (!this.#ready && !this.#printing) return;
      if (this.#restored !== null) {
        if (this.#ready) {
          this.#reading.hold(this.#restored);
          this.#restored = null;
        }
      }
      const current = history.map((served) => ({
        ...describe(served),
        excerpt: served.excerpt ? clip(markdownWords(served.excerpt), 140) : null,
        id: served.id,
        ts: served.ts,
        author: served.author,
        actor: actorOf(served),
        undone: served.undone,
      }));
      // Hold the complete drawn reading, including an undo or a changed title:
      // those may wrap too. The authoritative history always remains #history.
      for (const row of current) {
        row.available = Boolean(row.widget && document.getElementById(row.widget));
        if (row.widget || row.label) row.label ??= nameOf(row.widget);
      }
      const wanted = JSON.stringify(current);
      if (this.#closedReading === null) this.#closedReading = wanted;
      const shown = this.#printing
        ? wanted
        : this.#opened
          ? this.#reading.hold(wanted)
          : this.#closedReading;
      const rows = JSON.parse(shown);
      const news = shown !== wanted;
      const known = new Set(rows.map(({ id }) => id));
      const arrived = current.filter(({ id }) => !known.has(id)).length;
      keeps(this.#notice, "data-lf-news", news ? "" : null);
      keeps(this.#notice, "aria-expanded", String(this.#opened));
      keepsText(
        this.#notice,
        !this.#opened
          ? `Show activity${arrived ? ` · ${arrived} new` : ""}`
          : news
            ? arrived
              ? `${arrived} new ${arrived === 1 ? "update" : "updates"}`
              : "Activity changed"
            : "Hide activity",
      );
      if (this.#opened && !this.#printing) this.#closedReading = shown;
      keepsHidden(this.#list, !this.#opened && !this.#printing);

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
        keeps(item, "data-lf-activity-author", row.author);
        if (seat.key !== key) {
          const restoreFocus = holdFocus(item);
          fillActivityRow(item, row, offer);
          this.#bind(item, row);
          restoreFocus?.(item.querySelector(".lf-activity-target"));
          seat.key = key;
        }
        // Read synchronously, so the shared clock repaints this reading when it turns.
        const time = item.querySelector(".lf-activity-time");
        keepsText(time, ago(row.ts));
        if (item !== next) this.#list.insertBefore(item, next);
        else next = next.nextElementSibling;
      }
      for (const [id, { item }] of this.#rows)
        if (!kept.has(id)) {
          item.remove();
          this.#rows.delete(id);
        }
      keepsHidden(this.#empty, (!this.#opened && !this.#printing) || rows.length > 0);
      if (!this.#printing)
        tabStore.set(
          ACTIVITY_VIEW + this.id,
          JSON.stringify({
            open: this.#opened,
            shown,
            label: this.#notice.textContent,
            news,
          }),
        );
    }
  },
);
