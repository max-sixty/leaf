// Every timestamp the page renders was written by its server. Keep the browser's one
// measured offset here, beside the two public readings that depend on it, so no seat can
// accidentally render against a second clock.
let clockSkew = 0;
let clockReads = null;
const clockPaints = new Set();
const serverNow = () => Date.now() + clockSkew;

// A clock reading is a displayed value or a temporal predicate, not raw wall time.
// Remember the readings made by each synchronous paint so the shared tick can wake
// only the paints whose answers changed. The callback receives the calibrated server-now
// milliseconds used by the comparison. Nested paints own their own dependencies.
export function clockValue(read) {
  const value = read(serverNow());
  clockReads?.push({ read, value });
  return value;
}

export function clocked(owner, paint) {
  let args;
  let reads = [];
  const entry = {
    owner,
    changed: () => reads.some(({ read, value }) => read(serverNow()) !== value),
    refresh: () => render(...args),
  };
  function render(...next) {
    args = next;
    const outer = clockReads;
    clockReads = [];
    try {
      return paint(...args);
    } finally {
      reads = clockReads;
      clockReads = outer;
      if (reads.length) clockPaints.add(entry);
      else clockPaints.delete(entry);
    }
  }
  render.stop = () => clockPaints.delete(entry);
  return render;
}

export async function tickClock(reportError) {
  // Package paints are independent subscribers. A bad clock read or repaint must
  // not starve later subscribers or turn a healthy state feed back into polling.
  const settled = await Promise.allSettled(
    [...clockPaints].map(async (entry) => {
      if (!entry.owner.isConnected) clockPaints.delete(entry);
      else if (entry.changed()) return entry.refresh();
    }),
  );
  for (const result of settled)
    if (result.status === "rejected")
      reportError(`clock paint failed: ${result.reason?.message ?? result.reason}`);
}

export const observeServerNow = (now) => {
  if (now) clockSkew = Date.parse(now) - Date.now();
};
export const ago = (ts) =>
  clockValue((now) => {
    if (!ts) return "";
    const secs = Math.max(0, (now - new Date(ts).getTime()) / 1000);
    if (secs < 45) return "just now";
    if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
    return `${Math.round(secs / 86400)}d ago`;
  });

const WORKING_GRACE_MS = 15 * 60 * 1000;
const PICKUP_RECEIPT_GRACE_MS = 2 * 60 * 1000;
const TURN_RENEWAL_GRACE_MS = 2 * 60 * 1000;
export const quietSince = (ts, grace = WORKING_GRACE_MS) =>
  clockValue((now) => Boolean(ts) && now - new Date(ts).getTime() > grace);
export const waitingForPickupSince = (ts) => quietSince(ts, PICKUP_RECEIPT_GRACE_MS);

export function createPresence() {
  // ---------- presence ----------
  // "Claude is working" is a claim in status.json, and nothing revises a claim once the
  // session behind it walks away — so a page nobody is watching reads exactly like a page
  // whose user has said nothing yet. The banner asks whether anyone is attending, and
  // only two things answer yes: Claude is credibly busy, or a `leaf wait` is live.
  // Everything else is absence, where the reason and the remedy are all that vary.
  //
  // One of those absences is not a fault, and reading it as one was the bug. A page served
  // across sessions — a command hub, a dashboard left open for a fortnight — is unheld for
  // most of its life, and a night of it is Tuesday. So the banner separates "somebody is
  // behind this page and isn't keeping up", which is worth an amber dot and a nudge, from
  // "nobody is behind it", which is the standing page at rest: grey, and the plain fact
  // that it picks up again when a session does.
  //
  // Every one of those answers is about a session that exists or existed, and a page can be
  // served with none — the whole of leaf.page is, each example a working page on a static
  // host where the log is the reader's own browser and no agent will ever read it. The
  // banner had no way to say that, so the page said the nearest thing it could and claimed
  // to be listening: green dot, "awaits", over a page waiting for nobody. Whoever answers
  // the poll declares it instead (`unattended`), and it is judged ahead of the rest because
  // it is not a state the evidence below could reach — there is no claim to weigh, no
  // lifetime to look for, and nothing coming that would change the answer.
  // How long a claim of work may go unrefreshed before the page stops taking its word for
  // it. Exported, because the banner is not the only thing that judges one: a page running
  // a fleet says the same sentence per row, and a second threshold spelled in a widget
  // would be a second answer to "how long is too long" — free to disagree with the banner
  // directly above it about the very same silence. The caller supplies the rope where its
  // claim has a shorter one; the constant is the default because that is the case there is
  // only one of.
  // How long after a turn closes a claim it left behind is still believed. The grace
  // above asks how long a claim has gone unrenewed; this one exists because the answer
  // to "is anything still behind it" arrives before the answer to "has it gone stale",
  // and it needs a margin: the agent claims the work, hands it to a delegate and ends
  // the turn in the same second, and the delegate's first note is a minute or so behind
  // that. Shorter than the grace by an order of magnitude, because it is measured from
  // an observed event rather than from the absence of one.
  // The second question the page asks of a claim, beside how long it has gone
  // unrenewed: did the turn behind it end with nothing picking it up. This one has an
  // answer the moment it becomes true, because the Stop hook watches the ending rather
  // than inferring it from silence. Written no later than the ending counts as written
  // by the turn that ended — both stamps carry seconds, and an agent's last word about
  // its work and the end of the turn that wrote it land in the same one all the time.
  // Shared, because a page claim and a note on a thread are written by one command and
  // a seat answering this differently for one of them is the two of them arguing about
  // a single silence.
  const droppedAt = (ts, turnClosed) =>
    Boolean(turnClosed) &&
    Date.parse(ts) <= Date.parse(turnClosed) &&
    quietSince(turnClosed, TURN_RENEWAL_GRACE_MS);
  // Which claim each kind reads out, and so whose detail it may speak. The question
  // sits here rather than at each seat, for the reason `kind` does: two seats answering
  // it separately is two answers to what the page may say it is waiting for. A kind
  // absent here is a judgment against the claim — nobody is behind the page, or the page
  // is closed — and the claim's words about the work are not the news there.
  //
  // `stalled` reads a `working` claim's detail like `working` does, and that is the whole
  // difference between the two: same words, a sentence that dates them. They were one
  // judgment once, folded into `listening` because a watcher was live, and the detail was
  // dropped on the way — so a page whose agent had said "revising the plan" and then
  // spent twenty minutes in a delegate's hands read "Claude awaits — select text to
  // comment", inviting the reader to start something over a page already mid-answer. The
  // dropping was right for the sentence it was under: what the agent was doing is the
  // wrong half of the loop to read out after "awaits". The sentence was the mistake.
  const DETAIL_FROM = { working: "working", listening: "waiting", stalled: "working" };
  // The claim-against-proof judgment, one function for every surface that shows a
  // status: the banner's sentence about this page and a panel row about a neighbour
  // read the same fields the server gathers in one place (`presence`), so the two can
  // never disagree about what "working" means. `kind` is the judged state and `detail`
  // the claim's own words where that state licenses them; the caller words it for its
  // seat.
  function presented(state) {
    const { status, listening, session_alive, unattended, turn_closed } = state;
    // How long the agent's own work claim has gone unrefreshed. Delivery pickup is
    // projected per interaction and never changes this page-wide status.
    const aged = quietSince(status.ts);
    // The same silence reached by evidence instead of by a clock. A claim is written by
    // a model's turn, and when that turn ends nothing runs — so the page could only ever
    // find an abandoned claim by waiting out the grace, saying "Claude is working" over
    // nobody for most of a quarter of an hour. The Stop hook records the ending, and a
    // claim older than it is one that neither a next turn nor a delegate renewed across
    // the boundary. A delegate that does check in writes a `ts` past the stamp and
    // carries the claim on its own from then on, which is the same one command that
    // writes its note — so this costs the delegate case nothing and closes the window
    // on the case it was hiding.
    const dropped = droppedAt(status.ts, turn_closed);
    const quiet = aged || dropped;
    // Nothing is behind the claim. The claimant's lifetime settles it where there is
    // one: over is over, whatever the claim says and whether a stray `leaf wait` still
    // holds a lease for a session that can no longer read it. Where nothing claimed the
    // page — a server started outside an agent host — there is no lifetime to read, so a
    // live watcher or a claim still inside its grace is the whole of the evidence, and
    // once both are spent the page is unheld too.
    const unheld =
      session_alive === false || (session_alive === null && !listening && quiet);
    const kind = unattended
      ? "unattended"
      : status.state === "idle"
        ? "closed"
        : unheld
          ? "unheld"
          : status.state === "working"
            ? // A claim of work outranks the watcher under it, fresh or stale: what the
              // agent said it was doing is the news either way, and going quiet on it is
              // the news the reader is least able to work out for themselves. The rope is
              // the same one a roster row holds a worker to, so "gone quiet" means one
              // thing on the page whoever is being judged — and a note on a thread
              // (`leaf status … --on`) renews the claim, which is how work handed to a
              // delegate stays true across a turn boundary the session cannot write over.
              !quiet
              ? "working"
              : listening
                ? "stalled"
                : "away"
            : listening
              ? "listening"
              : "away";
    return {
      kind,
      quiet,
      // Which of the two silences this is, for the seat that has to date it. Not a kind
      // of its own: whether the reader's next word still reaches anyone is the question
      // `stalled` and `away` already split on, and this is orthogonal to it.
      dropped,
      // Whether anything at all answers for the claim. The banner drops a claim
      // nothing is behind rather than repeating it, and every other seat reading
      // the same claim has to drop it on the same evidence: a note left on a
      // thread by a session that has since died would sit under a line saying no
      // session holds the page, each half arguing with the other about the same
      // fact. Not the same question as `quiet`, which is about a claim going
      // unrenewed by somebody who is still there.
      held: kind !== "unheld" && kind !== "unattended",
      detail: status.state === DETAIL_FROM[kind] ? status.detail : "",
    };
  }

  return { droppedAt, presented };
}
