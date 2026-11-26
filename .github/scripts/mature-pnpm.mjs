/** Prints the newest pnpm release at least as many minutes old as its argument, which
 * the pnpm-update workflow reads from pnpm's `minimumReleaseAge`, for the workflow to
 * move `packageManager` to. `pnpm self-update` without a version would take the
 * `latest` tag whatever its age.
 */
import { pathToFileURL } from "node:url";

/** The newest pnpm release published at least `minutes` before `now`, from the
 * registry's map of each version to its publish time. */
export function maturePnpm(time, minutes, now = Date.now()) {
  const parts = (version) => version.split(".").map(Number);
  const newer = (a, b) => {
    const [x, y] = [parts(a), parts(b)];
    const at = x.findIndex((n, i) => n !== y[i]);
    return at >= 0 && x[at] > y[at];
  };
  let best;
  for (const [version, published] of Object.entries(time))
    if (
      /^\d+\.\d+\.\d+$/.test(version) &&
      Date.parse(published) <= now - minutes * 60_000 &&
      (!best || newer(version, best))
    )
      best = version;
  if (!best) throw new Error(`No pnpm release is ${minutes} minutes old`);
  return best;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const minutes = Number(process.argv[2]);
  if (!(minutes > 0))
    throw new Error(`Usage: mature-pnpm.mjs MINUTES (got ${process.argv[2]})`);
  const response = await fetch("https://registry.npmjs.org/pnpm");
  if (!response.ok) throw new Error(`Registry answered ${response.status}`);
  console.log(maturePnpm((await response.json()).time, minutes));
}
