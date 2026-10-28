/* lf-activity: the page's history as a feed, newest first.
 *
 * The server's history reading is the only semantic input: every
 * reading of `readHistory` restates the whole feed. A row says who acted (You for the
 * user, Page for what the page did by itself, and otherwise the name the server serves
 * the row under), what they did, the thing they did it to, and how long ago.
 *
 * What a row's event was is the server's: the thread it belongs to,
 * whether a later undo took it back, and for a widget gesture the words its ids had in
 * the document it was made in, under that document's declaration of the widget. A
 * version that rewords or removes an option therefore leaves the row as the user made
 * it. This module words those facts and names the places on the page it links to; a
 * thread goes by its name in words (`threadSummary`).
 *
 * A place is named on the page the user is reading, since that is where the row leads,
 * and as the rest of the chrome names it (`addressableLabel`), else by its word. A
 * quoted passage is named as Threads names its anchor (`anchorLabel`).
 *
 * The thing is the row's way there: a widget or section is an ordinary fragment link,
 * so the browser owns that travel as it does for lf-toc, and a thread is a button
 * onto `threadActions.open`, which chooses the thread's inline destination or Threads the same
 * way a mark and t/T do. Links and buttons are the keyboard route: each is a Tab stop
 * and a go-to target.
 *
 * An excerpt is the words its Markdown renders, never the source.
 *
 * History has no authored size. Its fixed disclosure stands from first paint; rows
 * appear only when the reader opens it. Once open, HeldReading keeps visible history
 * behind that same disclosure until the reader asks to see the change or leaves it
 * off screen. Rows retain their event identity and focus while that reading stands.
 * Targets stay live: a held row keeps its historical words and geometry, but its
 * fragment link follows only a destination in the current document. A departed
 * destination leaves historical text in the same node, without an active link.
 * Tab memory retains the drawn presentation through a fresh document. Its initial
 * producer draws it before first paint, then the ready authoritative reading is
 * compared through HeldReading. This never folds events or records a decision. */
import {
  HeldReading,
  initialRender,
  tabStore,
  addressableLabel,
  addressableWord,
  ago,
  anchorLabel,
  elementById,
  fragmentTarget,
  layerFact,
  loadMarkdown,
  markdownReady,
  markdownWords,
  LeafElement,
  threadActions,
  readThreads,
  readHistory,
  threadSummary,
  whileConnected,
  excerptWords,
} from "/runtime/widget-api.js";

const NAME = 60;

// Where something happened, as the chrome names it, else its word.
function nameOf(id) {
  const element = id ? elementById(id) : null;
  if (!element) return id || "the page";
  return (
    excerptWords(addressableLabel(element), NAME) || `the ${addressableWord(element)}`
  );
}

// A comment's place: a passage, a drawing's part, a datum, or a design subject as
// Threads names it; a whole element by where it is.
function placeName(anchor, about) {
  // A bare quote is cut inside its marks, so a long one still reads as a quote.
  if (anchor?.quote && !anchor.datum && about !== "design")
    return quoted(excerptWords(anchor.quote, NAME));
  if (anchor?.visual || anchor?.datum || about === "design")
    return excerptWords(anchorLabel(anchor, about), NAME);
  return nameOf(anchor?.section ?? null);
}

const reaction = (token) => layerFact("$reactions")?.tokens?.[token]?.glyph ?? token;

const actorOf = (row) =>
  row.author === "user"
    ? "Me"
    : row.author === "page"
      ? "Page"
      : (row.agent ?? row.author);

const quoted = (words) => `“${words}”`;
const named = (words) => quoted(excerptWords(words, NAME));

// The thread's name in words (`threadSummary`), read from the thread as
// it stands now, as every way there is. A thread Threads does not list, a bare
// reaction, has no name there and no way to it, so it goes as a thread.
const topicOf = (served) => {
  const thread = served && readThreads().threads.find(({ id }) => id === served.id);
  return thread ? excerptWords(threadSummary(thread).topic, 48) : "a thread";
};

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
  class extends LeafElement {
    #list = null;
    #empty = null;
    #template = null;
    #storageKey = null;
    #notice = null;
    #opened = false;
    #reading = null;
    #printing = false;
    #closedReading = null;
    #restored = null;
    #ready = false;

    setup() {
      const drawing = initialRender(this);
      this.#storageKey = drawing.storageKey;
      this.#list = drawing.list;
      this.#empty = drawing.empty;
      this.#notice = drawing.notice;
      this.#template = (reading) =>
        drawing.render(reading, {
          printing: this.#printing,
          names: fragmentTarget,
          age: ago,
          openThread: (id) =>
            void threadActions.open(
              readThreads().threads.find((thread) => thread.id === id)?.key,
              { part: "thread" },
            ),
        });
      this.#opened = drawing.reading.open;
      this.#closedReading = drawing.restored ? drawing.reading.shown : null;
      this.#restored = drawing.restored ? drawing.reading.shown : null;
      this.#reading = new HeldReading(
        this,
        () => [this.#notice, this.#list, this.#empty],
        () => this.requestUpdate(),
      );
      this.#notice.addEventListener("click", () => {
        if (this.#notice.hasAttribute("data-lf-news")) this.#opened = true;
        else this.#opened = !this.#opened;
        this.#reading.release();
        this.requestUpdate();
        this.performUpdate();
      });
      const paper = matchMedia("print");
      const printing = () => {
        this.#printing = paper.matches;
        this.requestUpdate();
        this.performUpdate();
      };
      whileConnected(this, (signal) => {
        this.#printing = paper.matches;
        paper.addEventListener("change", printing, { signal });
      });
    }

    render() {
      const history = readHistory();
      this.#ready = history.phase === "ready";
      const view = this.#render(history.events);
      // A failed parser import can retry on the next reading, including a return.
      if (!markdownReady())
        loadMarkdown().then((loaded) => {
          if (loaded) this.requestUpdate();
        });
      return view;
    }

    #render(history) {
      if (!this.#ready && !this.#printing) return this.#template(undefined);
      if (this.#restored !== null) {
        if (this.#ready) {
          this.#reading.hold(this.#restored);
          this.#restored = null;
        }
      }
      const current = history.map((served) => ({
        ...describe(served),
        excerpt: served.excerpt
          ? excerptWords(markdownWords(served.excerpt), 140)
          : null,
        id: served.id,
        ts: served.ts,
        actor: actorOf(served),
        undone: served.undone,
      }));
      // Hold the complete drawn reading, including an undo or a changed title:
      // those may wrap too. The reactive reading supplies the authoritative history.
      for (const row of current) {
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
      const label = !this.#opened
        ? `Show activity${arrived ? ` · ${arrived} new` : ""}`
        : news
          ? arrived
            ? `Show ${arrived} new`
            : "Activity changed"
          : "Hide activity";
      if (this.#opened && !this.#printing) this.#closedReading = shown;
      const reading = { open: this.#opened, shown, label, news };
      if (!this.#printing) tabStore.set(this.#storageKey, JSON.stringify(reading));
      return this.#template(reading);
    }
  },
);
