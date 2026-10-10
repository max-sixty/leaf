/** Dependency builds run without secrets. The trusted publisher accepts only
 * generated browser bundles for the exact, still-open Dependabot head it built.
 * It never executes PR code, and a non-forced ref update rejects concurrent edits.
 */
import { execFileSync } from "node:child_process";
import { lstatSync, readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export function generated(path) {
  return (
    /^(?:skills\/leaf\/assets\/vendor|skills\/leaf\/packages\/[^/.]+\/vendor)\/(?:[^/.][^/]*\/)*[^/.][^/]*\.(?:js|css|LICENSES\.txt)$/.test(
      path,
    ) && !path.split("/").some((part) => part === ".." || part === ".")
  );
}

export function capture() {
  const git = (...args) => execFileSync("git", args, { encoding: "utf8" }).trim();
  const paths = git("diff", "--name-only", "--no-renames", "HEAD")
    .split("\n")
    .filter(Boolean);
  const files = paths.map((path) => {
    if (!generated(path)) throw new Error(`Build changed non-bundle path: ${path}`);
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

export async function publish(api, repo, run, artifact) {
  if (run.event !== "pull_request" || run.head_repository.full_name !== repo)
    throw new Error("Build must originate in this repository's pull request");
  if (artifact.head !== run.head_sha)
    throw new Error("Artifact is for a different head");
  if (!artifact.files.length) return "unchanged";
  const seen = new Set();
  for (const file of artifact.files) {
    if (
      !generated(file.path) ||
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
    !changes.some((f) => f.filename === "package-lock.json") ||
    changes.some(
      (f) =>
        !["package.json", "package-lock.json"].includes(f.filename) &&
        !generated(f.filename),
    )
  )
    throw new Error("Dependency PR also changes non-bundle source");
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
    message:
      "Rebuild browser bundles for dependency updates\n\n> _This was written by Leaf dependency automation on behalf of max-sixty_",
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
  if (process.argv[2] !== "capture")
    throw new Error("Usage: dependency-bundles.mjs capture FILE");
  writeFileSync(process.argv[3], JSON.stringify(capture()));
}
