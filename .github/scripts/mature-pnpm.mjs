/** Prints the newest pnpm release old enough for `minimumReleaseAge` in
 * `pnpm-workspace.yaml`, for the pnpm-update workflow to move `packageManager` to.
 * `pnpm self-update` without a version would take the `latest` tag whatever its age.
 */
import { readFileSync } from "node:fs";
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
  const minutes = Number(
    readFileSync("pnpm-workspace.yaml", "utf8").match(
      /^minimumReleaseAge: (\d+)$/m,
    )?.[1],
  );
  if (!minutes) throw new Error("pnpm-workspace.yaml sets no minimumReleaseAge");
  const response = await fetch("https://registry.npmjs.org/pnpm");
  if (!response.ok) throw new Error(`Registry answered ${response.status}`);
  console.log(maturePnpm((await response.json()).time, minutes));
}
