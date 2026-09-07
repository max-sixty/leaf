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
export const quietSince = (ts, grace = WORKING_GRACE_MS) =>
  clockValue((now) => Boolean(ts) && now - new Date(ts).getTime() > grace);

// Temporal policy belongs to the server's canonical activity fold. The browser uses
// its calibrated copy of server time only to ask for the next projection when that
// fold says an answer can change; it never decides what the new answer is.
export const activityTransitionDue = (state) =>
  [state?.activity, ...(state?.others ?? []).map((entry) => entry.activity)].some(
    (activity) =>
      activity?.next_transition_at &&
      serverNow() >= Date.parse(activity.next_transition_at),
  );
