// Planted faults for `leaf/evaluation-order`, the rule in `eslint.config.mjs` that
// refuses a runtime owner's module body reading or calling another member of the owner
// cycle. Nothing else exercises the rule: the runtime it lints is supposed to pass it,
// so a rule that stopped reporting would leave every hook green. This feeds eslint two
// modules over stdin and checks its verdict line by line.
//
// Both fixtures go in under `HOST`'s path, because the rule reads the import graph off
// disk to decide who is in the cycle, and an invented path is outside it. `OWNER`
// is another cycle member exporting both a `const` and a function declaration, the
// distinction between a refused read and an allowed reference. If either module leaves
// the cycle, or one of those two names changes kind, the fault cases stop reporting and
// this fails; point `HOST` and `OWNER` at another pair.
//
// eslint comes from `PATH`, so run this through the `eslint-evaluation-order` pre-commit
// hook, which shares the pinned eslint mirror's environment.

import { spawnSync } from "node:child_process";
import { join } from "node:path";

const ROOT = join(import.meta.dirname, "..");
const HOST = "skills/leaf/assets/runtime/chrome.js";
const OWNER = "anchors.js";
const RULE = "leaf/evaluation-order";

const readMessage = (name) =>
  `${OWNER} is in the owner cycle, so its ${name} may not be read as this module ` +
  `evaluates: ask for it at use.`;
const callMessage = (name) =>
  `${OWNER} is in the owner cycle, so its ${name} may not be called as this module ` +
  `evaluates: call it in a mount step or at use.`;

const faults = `import { ITEM, isItem } from "./${OWNER}";

const selector = ITEM;
isItem(document.body);
(() => {
  const inner = ITEM;
  return inner;
})();
const deferred = isItem;

export { selector, deferred };
`;

// Each fault, in the order eslint reports them. Matching this list exactly also covers
// the bare `isItem` reference in the fixture, which the rule must leave alone.
const refusals = [
  { at: "const selector = ITEM;", message: readMessage("ITEM") },
  { at: "isItem(document.body);", message: callMessage("isItem") },
  { at: "  const inner = ITEM;", message: readMessage("ITEM") },
];

const allowed = `import { isItem } from "./${OWNER}";

const deferred = isItem;
const ask = (node) => isItem(node);

export { deferred, ask };
`;

function fail(what) {
  process.stderr.write(`${what}\n`);
  process.exit(1);
}

function lineOf(source, snippet) {
  const hits = source
    .split("\n")
    .flatMap((line, index) => (line.includes(snippet) ? [index + 1] : []));
  if (hits.length !== 1)
    fail(`the fixture holds ${hits.length} lines matching ${JSON.stringify(snippet)}`);
  return hits[0];
}

function refusedBy(source) {
  const run = spawnSync(
    "eslint",
    ["--stdin", "--stdin-filename", HOST, "--format", "json"],
    { cwd: ROOT, input: source, encoding: "utf8" },
  );
  if (run.error?.code === "ENOENT")
    fail("eslint is not on PATH: run `pre-commit run eslint-evaluation-order`.");
  if (run.error) fail(`eslint did not run: ${run.error}`);
  let results;
  try {
    results = JSON.parse(run.stdout);
  } catch {
    fail(`eslint printed no report:\n${run.stdout}${run.stderr}`);
  }
  const [result] = results;
  if (!result || result.fatalErrorCount)
    fail(`eslint did not read the fixture as ${HOST}:\n${run.stdout}`);
  return result.messages
    .filter((message) => message.ruleId === RULE)
    .map(({ line, message }) => ({ line, message }));
}

const reported = refusedBy(faults);
const wanted = refusals.map(({ at, message }) => ({
  line: lineOf(faults, at),
  message,
}));
if (JSON.stringify(reported) !== JSON.stringify(wanted))
  fail(
    `${RULE} on the planted faults\n` +
      `  wanted: ${JSON.stringify(wanted, null, 2)}\n` +
      `  got:    ${JSON.stringify(reported, null, 2)}`,
  );

// A module that only references the cycle function, and calls it from a body that runs
// later, must lint clean on its own too.
const quiet = refusedBy(allowed);
if (quiet.length)
  fail(`${RULE} refused the deferring module: ${JSON.stringify(quiet, null, 2)}`);
