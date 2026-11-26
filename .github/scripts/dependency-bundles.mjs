/** Dependency builds run without secrets. The trusted publisher accepts only
 * generated browser bundles and the pnpm pin for the exact, still-open Dependabot
 * head it built. It never executes PR code, and a non-forced ref update rejects
 * concurrent edits.
 *
 * Dependabot never moves the pnpm that `packageManager` pins, so the build moves it
 * to the newest release `minimumReleaseAge` admits (`maturePnpm`) with
 * `pnpm self-update <version>`, which rewrites `packageManager` and the lockfile's
 * first document, where pnpm locks itself. Without a version, `self-update` takes the
 * `latest` tag whatever its age. The publisher takes those two files only where
 * nothing else in them changed.
 */
import { execFileSync } from "node:child_process";
import { lstatSync, readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { styleEntries } from "../../build/styles.mjs";

// The publisher loads this declaration from its trusted default-branch checkout,
// never from the PR or its artifact. A sheet counts only when the build writes it, so
// authored CSS remains outside this boundary.
const styles = new Set(styleEntries.map(([, output]) => output));

const pin = new Set(["package.json", "pnpm-lock.yaml"]);

function generated(path) {
  return (
    (styles.has(path) ||
      /^(?:browser\/vendor|packages\/[^/.]+\/vendor)\/(?:[^/.][^/]*\/)*[^/.][^/]*\.(?:js|css|LICENSES\.txt)$/.test(
        path,
      )) &&
    !path.split("/").some((part) => part === ".." || part === ".")
  );
}

export function capture() {
  const git = (...args) => execFileSync("git", args, { encoding: "utf8" }).trim();
  const paths = git("diff", "--name-only", "--no-renames", "HEAD")
    .split("\n")
    .filter(Boolean);
  const files = paths.map((path) => {
    if (!generated(path) && !pin.has(path))
      throw new Error(`Build changed non-bundle path: ${path}`);
    const mode = git("ls-files", "--stage", "--", path).split(" ")[0];
    const file = lstatSync(path, { throwIfNoEntry: false });
    if (mode !== "100644" || (file && !file.isFile()))
      throw new Error(`Bundle is not a regular file: ${path}`);
    return { path, content: file ? readFileSync(path, "utf8") : null };
  });
  // New chunk files belong to the build too; tracked-only diff would lose them.
  for (const path of git("ls-files", "--others", "--exclude-standard")
    .split("\n")
    .filter(Boolean)) {
    if (!generated(path)) throw new Error(`Build created non-bundle path: ${path}`);
    if (!lstatSync(path).isFile())
      throw new Error(`Bundle is not a regular file: ${path}`);
    files.push({ path, content: readFileSync(path, "utf8") });
  }
  return { head: git("rev-parse", "HEAD"), files };
}

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

// The lockfile's first document locks pnpm itself; the second locks the dependencies.
function lockDocuments(text) {
  const at = text.indexOf("\n---\n", 4);
  if (!text.startsWith("---\n") || at < 0)
    throw new Error("Invalid pnpm pin: lockfile");
  return [text.slice(0, at), text.slice(at)];
}

// The first document's lines from `packages:` on, as pnpm writes them for pnpm
// `version` and its platform binaries, each fetched from the registry by integrity
// alone. A line of any other shape, such as a tarball URL, another package or YAML's
// block or explicit-key syntax, fails the check.
function pinLines(version) {
  const v = version.replaceAll(".", "\\.");
  const exe = "@pnpm/exe\\.[a-z0-9]+(?:-[a-z0-9]+)*";
  return [
    /^$/,
    /^(?:packages|snapshots):$/,
    new RegExp(`^ {2}(?:pnpm@${v}|'${exe}@${v}'):$`),
    /^ {4}resolution: \{integrity: sha512-[A-Za-z0-9+/]+={0,2}\}$/,
    /^ {4}(?:cpu|os|libc): \[[a-z0-9]+(?:, [a-z0-9]+)*\]$/,
    /^ {4}engines: \{node: '[^']*'\}$/,
    /^ {4}(?:hasBin|optional): true$/,
    /^ {4}optionalDependencies:$/,
    new RegExp(`^ {6}'${exe}': ${v}$`),
  ];
}

// The build's package.json and lockfile may differ from the head's only in the pnpm
// they pin: `packageManager`, the importer that names it, and `pinLines`.
async function checkPin(api, repo, head, files) {
  const read = (path) =>
    api("GET", `/repos/${repo}/contents/${path}?ref=${head}`, {
      mediaType: { format: "raw" },
    });
  const [manifest, lock] = await Promise.all([
    read("package.json"),
    read("pnpm-lock.yaml"),
  ]);
  const field = /"packageManager": "pnpm@(\d+\.\d+\.\d+)"/;
  const version = files["package.json"]?.match(field)?.[1];
  const previous = manifest.match(field)?.[1];
  if (
    !version ||
    !previous ||
    files["package.json"] !==
      manifest.replace(field, `"packageManager": "pnpm@${version}"`)
  )
    throw new Error("Invalid pnpm pin: package.json");
  const [first, rest] = lockDocuments(files["pnpm-lock.yaml"] ?? "");
  const [headFirst, headRest] = lockDocuments(lock);
  const at = first.indexOf("\npackages:\n");
  const headAt = headFirst.indexOf("\npackages:\n");
  const shapes = pinLines(version);
  if (
    rest !== headRest ||
    at < 0 ||
    headAt < 0 ||
    first.slice(0, at) !== headFirst.slice(0, headAt).replaceAll(previous, version) ||
    !first
      .slice(at + 1)
      .split("\n")
      .every((line) => shapes.some((shape) => shape.test(line)))
  )
    throw new Error("Invalid pnpm pin: lockfile");
  return version;
}

export async function publish(api, repo, run, artifact) {
  if (run.event !== "pull_request" || run.head_repository.full_name !== repo)
    throw new Error("Build must originate in this repository's pull request");
  if (artifact.head !== run.head_sha)
    throw new Error("Artifact is for a different head");
  if (!artifact.files.length) return "unchanged";
  const seen = new Set();
  for (const file of artifact.files) {
    if (
      !(generated(file.path) || pin.has(file.path)) ||
      seen.has(file.path) ||
      (file.content !== null && typeof file.content !== "string")
    )
      throw new Error(`Invalid generated bundle: ${file.path}`);
    seen.add(file.path);
  }
  const pulls = await api("GET", `/repos/${repo}/commits/${artifact.head}/pulls`);
  const pr = pulls.find(
    (p) =>
      p.state === "open" &&
      p.user.login === "dependabot[bot]" &&
      p.head.repo.full_name === repo &&
      p.head.sha === artifact.head,
  );
  if (!pr) return "superseded";
  const changes = await api(
    "GET",
    `/repos/${repo}/pulls/${pr.number}/files?per_page=100`,
  );
  if (
    changes.length >= 100 ||
    !changes.some((f) => f.filename === "pnpm-lock.yaml") ||
    changes.some(
      (f) =>
        !["package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"].includes(
          f.filename,
        ) && !generated(f.filename),
    )
  )
    throw new Error("Dependency PR also changes non-bundle source");
  const pinned = artifact.files.filter((file) => pin.has(file.path));
  const version = pinned.length
    ? await checkPin(
        api,
        repo,
        artifact.head,
        Object.fromEntries(pinned.map(({ path, content }) => [path, content])),
      )
    : null;
  const bundles = artifact.files.length > pinned.length;
  const parent = await api("GET", `/repos/${repo}/git/commits/${artifact.head}`);
  const tree = await api("POST", `/repos/${repo}/git/trees`, {
    base_tree: parent.tree.sha,
    tree: artifact.files.map(({ path, content }) => ({
      path,
      mode: "100644",
      type: "blob",
      ...(content === null ? { sha: null } : { content }),
    })),
  });
  if (tree.sha === parent.tree.sha) return "unchanged";
  const commit = await api("POST", `/repos/${repo}/git/commits`, {
    message: `${
      version
        ? `Move pnpm to ${version}${bundles ? " and rebuild browser bundles" : ""}`
        : "Rebuild browser bundles for dependency updates"
    }\n\n> _This was written by Leaf dependency automation on behalf of max-sixty_`,
    tree: tree.sha,
    parents: [artifact.head],
  });
  await api(
    "PATCH",
    `/repos/${repo}/git/refs/heads/${encodeURIComponent(pr.head.ref)}`,
    { sha: commit.sha, force: false },
  );
  return commit.sha;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv[2] === "capture")
    writeFileSync(process.argv[3], JSON.stringify(capture()));
  else if (process.argv[2] === "pnpm") {
    const minutes = Number(
      readFileSync("pnpm-workspace.yaml", "utf8").match(
        /^minimumReleaseAge: (\d+)$/m,
      )?.[1],
    );
    if (!minutes) throw new Error("pnpm-workspace.yaml sets no minimumReleaseAge");
    const response = await fetch("https://registry.npmjs.org/pnpm");
    if (!response.ok) throw new Error(`Registry answered ${response.status}`);
    console.log(maturePnpm((await response.json()).time, minutes));
  } else throw new Error("Usage: dependency-bundles.mjs capture FILE | pnpm");
}
