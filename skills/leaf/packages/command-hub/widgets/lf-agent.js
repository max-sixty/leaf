/* lf-agent: upgraded because a roster row has two facts a version cannot write.
 * `doing` is the effective report's live clause, and the line saying how old what the
 * row says is computed at runtime from the worker's last report, or from when the row
 * itself was said when no report exists. The version carries the durable
 * state; answering its report therefore removes the clause rather than restoring an
 * authored copy of something that was true only between versions.
 *
 * The upgrade only adds — a state pill before whatever the author wrote and a live
 * line after it — and never moves or rewrites an authored node, so an error here
 * surfaces on the console and leaves the prose untouched and there is no failSoft
 * (which replaces content). The gutter the pill hangs in and every tint are theme CSS.
 *
 * Neither position is lf-task's, which inserts its chips after the <strong>, and the
 * difference is what each row is for. A task's chips qualify its title, so they belong
 * against it. A roster row is read across five near-identical siblings, so the state
 * leads — first in the reading and first in the gutter — and the minute-by-minute line
 * sits under the name and the author's sentence, one shape per agent to run an eye down.
 *
 * The line's words are the page's, not the runtime's: plain spans carrying
 * data-lf-gen, exactly as lf-task's done-fraction chip is, so the reader can select
 * and quote what the row says. Generated, so the version diff looks away; unmarked as
 * chrome, so the anchor pass does not. A quote on the elapsed line detaches when the
 * minute turns, which is the same bargain a quote on a computed fraction already
 * makes, and the alternative — marking it chrome — would put a word on screen that
 * the reader can read and not point at.
 *
 * Rebuilding is idempotent: renderState states the absolute attribute, and the common
 * update projection hands the declared activity clause to this row, so a reload, a
 * second tab, and a re-applied report all converge. watchUpdates re-renders on every
 * poll whether or not the log grew, which is what keeps the elapsed line true without
 * a timer of this module's own. */
import {
  ago,
  measure,
  offer,
  once,
  quietSince,
  saidAt,
  watchUpdates,
} from "/runtime/widget-api.js";
import { directCommandRole } from "/widgets/command-model.js";

const LINE = "lf-agent-line";

const word = (cls, text) =>
  Object.assign(document.createElement("span"), { className: cls, textContent: text });

/* When the log last heard this worker, and whether that is a problem. A claim of work
 * nobody has refreshed is the fleet's version of the banner's quiet agent, judged on
 * the same rope by the same predicate — one page must not hold two answers to how
 * long is too long. Silence is only news against a claim of work: an idle worker that
 * has said nothing all day is idle, which is what it said. Said in words and not in
 * the tint alone, because a colour is silence to whoever is listening — and said by
 * adding a word rather than by rewording the elapsed line, so `ago` is rendered whole
 * wherever it appears instead of being taken apart to fit a second sentence.
 *
 * Every report and not only the standing ones. The canonical feed retains settled
 * history explicitly: this line is about the log rather than about the fold,
 * and a version that absorbs a report answers what the row *says* without hearing a
 * word more from the worker who said it.
 *
 * And where a worker has never said anything, the version that published its row, which
 * is the longest we can honestly claim to have heard nothing. Saying nothing there was
 * the first build's answer, and it fails in the one direction this line cannot afford:
 * five rows claiming work, published at six in the evening, read at eight the next
 * morning with every worker dead — no elapsed line, no call-out, a dead fleet drawn
 * exactly like a fresh one. */
function heard(el, updates) {
  const row = el.querySelector(`:scope > .${LINE}`);
  if (!row) return;
  const reports = updates.filter((update) => update.source === "report");
  const effective = reports.findLast((update) => update.disposition === "effective");
  sayDoing(row, effective?.text ?? null);
  // What this worker last said, or — where it has never said anything — when the row
  // claiming it exists was put in front of the reader, which is the longest we can
  // honestly say we have heard nothing. `saidAt` for that: the version's publish for a
  // row on the page, and the message's own clock for a roster an agent sent in a reply,
  // where the page's publish would have the row certifying workers against a moment
  // before its own message existed.
  //
  // A fallback and pointedly not the later of the two: the question is how long the
  // *worker* has been silent, and a page revision is the orchestrator speaking, not them.
  // Taking the newer would let a revision activated this minute certify a worker three
  // hours dead, which is the failure this line exists to catch wearing the fix for its
  // twin.
  // The feed itself is chronological across sources. A report's durable log sequence
  // is the authority for which report this worker made last, including a repaired or
  // imported log whose timestamp is older than the entry before it. Do not smuggle a
  // second ordering rule in through array position.
  const newest = reports.reduce(
    (found, report) => (found === null || report.seq > found.seq ? report : found),
    null,
  );
  const ts = newest?.ts ?? saidAt(el);
  const stale = ts && el.getAttribute("state") === "working" && quietSince(ts);
  // In place, and only where the words actually differ. This runs on every poll for
  // every row on the page, and the row is a thing the reader is invited to select and
  // point at: a span removed and rebuilt every two seconds takes the selection whose
  // endpoint was in it, drops focus off the reference beside it, and swallows a click
  // that straddles the swap — the failure "Paint; don't wrap" is about, arrived at by
  // rebuilding rather than by wrapping. So structure is rebuilt only when a report
  // moves the row (render, from renderState), and the clock touches one text node when
  // the minute turns.
  say(row, "lf-cold", stale ? "quiet" : null, "lf-heard");
  say(row, "lf-heard", ts ? `last heard ${ago(ts)}` : null);
}

/* The report field x-report declared as its human-readable update, first in the tail.
 * Replay states semantic attributes; the update feed says which source is effective and
 * when it was heard. A version answering the report therefore removes this clause
 * without pretending the report vanished from history. */
function sayDoing(row, text) {
  let cell = row.querySelector(":scope > .lf-doing");
  if (text === null) {
    cell?.remove();
    return;
  }
  if (!cell) {
    cell = word("lf-doing", text);
    row.prepend(cell);
  }
  if (cell.textContent !== text) cell.textContent = text;
}

/* One cell of the row's tail: written where the words changed, created before `before`
 * where it was absent, removed where there is nothing to say. */
function say(row, cls, text, before) {
  let cell = row.querySelector(`:scope > .${cls}`);
  if (text === null) {
    cell?.remove();
    return;
  }
  if (!cell) {
    cell = word(cls, text);
    row.insertBefore(cell, before ? row.querySelector(`:scope > .${before}`) : null);
  }
  if (cell.textContent !== text) cell.textContent = text;
}

/* The state, in the gutter every row shares. A word rather than a dot: a tree's marker
 * sits beside a title that already says what the work is, so paint alone carries there
 * (lf-task, x-paints), and a roster is a set of rows alike in everything but this — a
 * colour with no word on it is a legend the reader has to hold in their head across
 * five of them, and silence to whoever is listening rather than looking.
 *
 * In a gutter, because the question a roster answers is which of these five, and an
 * answer that starts at a different column on every row is one the eye has to read
 * rather than scan. It is the one part of the row whose words are enumerable, which is
 * what makes a gutter possible at all: the names are not, and the clause after them
 * certainly is not, so the state is the only thing that can hold a column. */
function stateWord(el) {
  el.querySelector(":scope > .lf-state[data-lf-gen]")?.remove();
  const state = el.getAttribute("state");
  const pill = word(`lf-state lf-state-${state}`, state);
  pill.dataset.lfGen = "1";
  // First in the reading, wherever the gutter puts it on screen: "working, wren, …" is
  // the row in the order a listener needs it, and appending would have read the state
  // out after the elapsed line, as an afterthought to a row it is the subject of.
  el.prepend(pill);
}

/* The gutter's width, measured from the words rather than stated. Five states, so the
 * widest is knowable — and knowable only at load, in the face this page is actually
 * set in: the same 68px that covered "your pick" on macOS came 2px short of the
 * DejaVu a Linux runner has, and a number written here would go stale that quietly
 * again. Measured across the whole roster rather than per row, because a column that
 * each row sizes for itself is not a column. */
function gutter(el) {
  // The column belongs to the roster, so the roster is what is asked for — by the
  // question rather than by counting one step up, which would be a claim about where
  // this element happens to sit rather than about what shares its column.
  const roster = el.closest("lf-roster");
  if (!roster) return;
  const wide = Math.max(
    0,
    ...[...roster.querySelectorAll(":scope > lf-agent > .lf-state")].map(
      (pill) => pill.getBoundingClientRect().width,
    ),
  );
  if (wide) roster.style.setProperty("--lf-state-room", `${Math.ceil(wide)}px`);
}

/* The durable row fields. Run at upgrade and whenever replay moves this row; the
 * canonical update watcher paints transient activity afterward. */
function render(el) {
  stateWord(el);
  el.querySelector(`:scope > .${LINE}[data-lf-gen]`)?.remove();
  const row = document.createElement("div");
  row.className = LINE;
  row.dataset.lfGen = "1"; // generated, not authored — the version diff skips it
  const on = el.getAttribute("on");
  if (on) {
    // The task this worker holds, written the way every other reference on a page is
    // (lf-option's `for`): a pointer whose text is the id it names, chrome throughout,
    // so paper drops it rather than printing an address nobody can follow.
    const ref = offer("a", "lf-ref", `§ ${on}`);
    ref.href = `#${on}`;
    row.append(ref);
  }
  el.insertBefore(row, directCommandRole(el, "evidence")[0] ?? null);
  // The pill this row just drew may be the widest in the roster, and on the first pass
  // it is the last one to know: every row measures after its own render, so the column
  // is right once the last row has rendered and right again whenever a report changes
  // one of the words in it.
  // Off the pills' own boxes, so it waits for one (`measure`): a roster quoted
  // into a reply is built into the thread panel, which may not be open yet.
  measure(el, () => gutter(el));
}

customElements.define(
  "lf-agent",
  class extends HTMLElement {
    #stop = null;

    connectedCallback() {
      if (once(this)) render(this);
      // The clock, and nothing else. It runs immediately and again on every poll, so
      // the elapsed line stays true with no timer of this module's own — and touches
      // one text node when it does, rather than rebuilding a row the reader may have
      // their pointer in.
      this.#stop ??= watchUpdates(this, (updates) => heard(this, updates));
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
    }

    renderState(state) {
      const value = state.activity.value;
      if (value === this.getAttribute("state")) return;
      if (value === null) this.removeAttribute("state");
      else this.setAttribute("state", value);
      render(this);
    }
  },
);
