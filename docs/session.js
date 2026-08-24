/* The session a leaf page has when nothing is serving it.
 *
 * A page directory is files plus a process. The files a static host serves perfectly —
 * the vendored layer sits at this site's root, and every example under /examples is the
 * file in the tree — and the process answers two paths: GET /api/state, which hands the
 * page the log and who is behind it, and POST /api/event, which appends. So that is what
 * this is: those two paths, answered in the tab.
 *
 * Which makes the pages on this site live rather than pictures of live ones. Every
 * control is the shipped runtime's own — the banner and its counts, the comment panel,
 * the quote marks in the margin, a board that takes a drag and holds it across a reload —
 * because the runtime is loaded unmodified beside this file and cannot tell the
 * difference. What it can't have is the other half of the loop: no agent reads this log,
 * so a comment is recorded and answered by nobody.
 *
 * Three seats say so, because a reader meets the page at three moments and only one of
 * them is reading a line at the top. The banner says it in the runtime's own words, which
 * is what `unattended` below is for: this page reports that nobody is behind it and the
 * chrome states the consequence, where a page that wrote itself a claim could only then
 * talk the reader out of it. The label above the document says what the whole thing is,
 * on arrival, with room for it (`docs/sitenote.js`). And the demo replies once, in the
 * panel, because a reader who has just typed into a box deserves the answer where they
 * typed rather than where they stopped reading ten minutes ago.
 *
 * Nothing here validates what the runtime posts. The server's door is strict because it
 * guards a record an agent will act on and a machine anything on the network can reach;
 * this log is one reader's own, in one tab, written by the one script on the page, and a
 * second copy of that door would be a second thing to keep in step with the first.
 */

// The page these events belong to, which is the document's path with the version file
// taken off — so a page published with two versions keeps one log across both, as a
// served page does. Per tab, and per page: a reader who opens three examples is three
// readers, and closing the tab is how a demo is put back.
const KEY = `leaf-demo:${location.pathname.replace(/\/versions\/v[1-9]\d*\.html$/, "")}`;
// Which version this document is, read the way the runtime reads it.
const VERSION = Number(location.pathname.match(/\/versions\/v([1-9]\d*)\.html$/)?.[1]);
const LAYER = await fetch("/registry.json")
  .then((response) => response.json())
  .then((registry) => registry.$layer.generation);

// The name a reply in the panel wears, and nothing else. It is not the name of anyone
// behind the page — nobody is — so the banner never speaks it: `unattended` below is what
// the page reports, and the runtime's word for that names no agent.
//
// It said "The demo awaits" once, which the banner drew with the green dot it draws for a
// live watcher. Every word of the detail after it was spent denying the frame the seat had
// already set, and a reader who had not been told anyone might be listening was being
// argued out of a claim only the dot had made.
const AGENT = "The demo";
// Said once, to the first comment this reader writes, and not again — every comment
// after it is the same person who has now been told, and the same sentence under each of
// them reads as a machine talking rather than as an answer. Held here rather than read
// off the log, which on an example that ships a thread already holds replies that are
// none of this file's.
let answered = false;

const ANSWER = `This is the demo answering, not an agent. The page stands on a static host and the session behind it is your own browser tab, so nobody will read what you just wrote.

It went into the log all the same, with your quote attached — which is exactly what an agent picks up and answers. [Run one from a checkout](/examples.html#run) and a real reply lands right here.`;

// The log is this array. Web storage is where it is mirrored so a reload finds it, and
// a browser with storage switched off costs the reader their reload rather than the
// comment they just wrote — which is what reading the store back on every poll would
// have cost them, silently, at the one moment the page is proving it heard them.
const kept = (() => {
  try {
    return JSON.parse(sessionStorage.getItem(KEY));
  } catch {
    return null;
  }
})();

// What the page opens on, for an example that ships a thread beside it: the log the
// build laid in the page directory, which a served page would hand over on the first
// poll. Awaited at the top of the module, so it is in hand before the runtime beside
// this one evaluates and asks — fetched after the first answer, the page would paint an
// empty panel and then a full one, over a reader already reading it. A page with no
// thread to open on has no file here, and the 404 is that answer.
//
// Only where the tab is holding nothing. A reader who came back to this tab has a log
// that already grew from this seed, and re-reading it would put the thread back under
// whatever they did to it.
const events =
  kept ??
  (await fetch("../comments.jsonl")
    .then((res) => (res.ok ? res.text() : ""))
    .catch(() => "")
    .then((text) =>
      text
        .split("\n")
        .filter((line) => line.trim())
        // seq is the line number, as `read_events` numbers a log it reads: the file
        // holds none, and an event without one is invisible to the runtime's check for
        // what a poll has brought that the last one hadn't.
        .map((line, i) => ({ ...JSON.parse(line), seq: i + 1 })),
    ));

// append_event's work, minus the durability: identity, authorship and time belong to
// whoever holds the log, and seq is the line number the reader would have had.
function append(event, author, agent) {
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  events.push({
    ...event,
    id: [...bytes].map((b) => b.toString(16).padStart(2, "0")).join(""),
    author,
    ...(agent && { agent }),
    ts: new Date().toISOString(),
    seq: events.length + 1,
  });
  try {
    sessionStorage.setItem(KEY, JSON.stringify(events));
  } catch {
    /* a demo that cannot remember still takes the next comment */
  }
  return events.at(-1);
}

// `full_state`'s answer, field for field. The shape is the runtime's contract with
// whatever is behind the page, so it is answered whole rather than pared down to what
// this version of the runtime happens to read — a field left out is a banner seat that
// goes blank the day it starts reading one.
const state = () => ({
  layer: LAYER,
  // The versions this page has, which here is the one being read: the site publishes a
  // single version of each example. A second would want the list handed to this file
  // rather than guessed from a path, since a reader on v1 has to be offered v2.
  versions: [VERSION],
  // Nobody is behind this page and nobody is coming, which the runtime has a word for
  // and reads before it weighs anything else. Everything below it is then the honest
  // nothing a page outside a session loop has to report: no claim was ever written, no
  // watcher is live, and no session ever claimed the directory. None of it is what the
  // banner reads — that is the point of declaring the state rather than staging the
  // evidence for it — but a state object that lied here would be a second answer to
  // the same question, waiting for whatever reads these next.
  unattended: true,
  status: { state: "idle", detail: "", ts: null },
  listening: false,
  session_alive: null,
  // The name a reply wears in the panel. The banner asks for none under `unattended`.
  agent: AGENT,
  host: null,
  // Read to the end, and so nothing waiting. The pair has to agree — the count is what
  // the cursor leaves over — and "read everything, do nothing with it" is what is
  // actually true here, where a cursor at nought would have the banner telling a reader
  // their comments are queued for someone.
  cursor: events.at(-1)?.seq ?? 0,
  pending: 0,
  viewed: null,
  // No session, so nowhere it is working: a page here is a file on a web host rather
  // than a leaf somebody's session holds, and the tray's hover names the work behind
  // a page. There is none behind this one, which `unattended` above already says.
  session_cwd: null,
  others: [],
  events,
});

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Leaf-Layer": LAYER },
  });

const realFetch = window.fetch;
window.fetch = (input, init) => {
  const url = new URL(
    input instanceof Request ? input.url : String(input),
    location.href,
  );
  // Only this page's two doors. Everything else — the theme, the registry, the widget
  // modules, another version's markup — is a file the host serves, and the runtime
  // reaches for it exactly as it would anywhere else.
  if (url.origin !== location.origin) return realFetch(input, init);
  if (url.pathname === "/api/state") return Promise.resolve(json(state()));
  if (url.pathname === "/api/event") {
    const event = JSON.parse(init.body);
    // The execution record the door keeps per attempt, which is the whole of what a
    // retry meets: a browser whose answer was lost re-posts the same attempt, and an
    // attempt already in the log is answered with the state holding it rather than
    // appended a second time. One line, because the log is this tab's own — what the
    // server spends a lock on here is the ordering two writers would need.
    if (event.attempt && events.some((e) => e.attempt === event.attempt)) {
      return Promise.resolve(json({ ok: true, state: state() }));
    }
    const minted = append(event, event.kind === "error" ? "page" : "user");
    // The reply is written after the send has been answered, and lands on a later poll,
    // because that is when an answer arrives: written into the same response, it would
    // appear in the panel in the same frame as the comment, over the reader's own words
    // still settling.
    if (event.kind === "comment" && !answered) {
      answered = true;
      setTimeout(
        () =>
          append(
            { kind: "reply", parent: minted.id, version: VERSION, text: ANSWER },
            "claude",
            AGENT,
          ),
        1200,
      );
    }
    // An accepted POST hands back the state holding the event it minted, so the sender
    // crosses one boundary rather than "the append succeeded" followed by a read that
    // could fail on its own. The minted event is in there: this file's log and the
    // state's are one list.
    return Promise.resolve(json({ ok: true, state: state() }));
  }
  return realFetch(input, init);
};
