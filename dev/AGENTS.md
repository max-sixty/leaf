# The `leaf-dev` package

`leaf_dev` is Leaf's developer tooling: the mechanisms the suite and the eval
harnesses share, and the `leaf-dev` commands built on them. `uv run leaf-dev --help`
lists the commands, and each command's `--help` says what it does.

Only the root dev group depends on this uv workspace member, so the checkout's
environment installs it editable and `bin/leaf`, which runs `--no-dev`, never does.
Nothing in `skills/` may import it.

A command writes under `.tmp/` unless its reader finds the output at a committed
path, as with `examples/corpus.html` and its companions. Evidence, previews, and
probe results leave the tracked tree unchanged.

## Where tooling goes

When agents keep writing the same throwaway script, the job becomes a `leaf-dev`
command: a module here that owns its mechanism, registered in `cli.py`. Standing
tooling that CI, a hook or an alias runs is a command here too, so the repository
has no directory of loose scripts. A mechanism two tools need, such as building an
arm or serving a page, lives in one module here and the others import it. Code
reaches a module by importing it from this package, never through `sys.path`,
`PYTHONPATH` or a file path.

- `arms.py`: arms (the plugin payload at a ref, or as the working tree has it) and
  an A/B's pair of them, whose base defaults to the merge base with `main`
  (`base_ref`); pages served from an authored source on an arm; the machine's load
  average a timed command prints; the isolated `claude -p` children evals run; and
  the throwaway Claude Code, Codex and Pi homes a child of each runs under.
- `page_fixtures.py` builds a page directory from an authored source;
  `example_data.py` reads the catalog, names, and each page's companions.
- `browser.py` launches Chrome, and opens and settles a tab, the same way for every
  command that reads one.
- `leaf-dev probe SOURCE` opens a page built from this working tree, runs input
  steps, and prints what a JavaScript expression returns, the console errors, and
  optionally a screenshot; `--base` does the same on the merge base. Its startup
  evidence uses the same recorder as site verification: phases, resources, and
  native initial layout shifts with affected nodes and before/after rectangles.
  Those shifts are diagnostic, never a stability gate.
- `leaf-dev probe` also accepts an HTTP(S) URL. `--journey FILE` loads a Python
  file defining `run(page)`, after the `--do` steps; it can use the full Playwright
  API and return a JSON reading. `--record .tmp/recordings/NAME` saves `trace.zip`
  and `video.webm` per arm, even on a failed assertion. `--gif` adds a looping GIF
  for short journeys; `--actions` opts into visible click/key decorations.
  `--checkpoint-images` adds native PNG images at action phases for checkpoint review;
  taking them adds capture work and briefly hides the live caret.
  Recordings default to normal motion; `--motion reduce` reproduces that preference.
  Plain recording inserts no pauses. `--actions` is for demonstrations: Playwright
  waits 500 ms before each annotated input. Native video holds its final frame for
  at least one second. Read the timeline, filmstrip, DOM snapshots,
  console and network with `uv run leaf-dev trace-server DIR/worktree/trace.zip`.
  The server prints its viewer URL without opening a browser; link it for the user.
  `recording.py` owns capture and GIF encoding, including the demo's encoder;
  its `recording(page, directory)` context works in any Playwright script.
- `leaf-dev stills [BASE_REF]` screenshots a catalogue of UI states, at rest and
  reached by input, on a base runtime and HEAD's, and crops each state that changed
  into a before/after pair in its own run directory under `.tmp/stills/`.
  Repeat `--state NAME` to compare only the states a change touches.
- `leaf-dev thread-snapshots` owns reviewed message-delivery images in leaf-assets;
  `thread_snapshots.py` owns capture and acceptance. Its shared journey replaces
  the former panel/card sent stills. Acceptance alone advances
  `leaf-assets.json`'s `thread_snapshots_revision`; media publication advances
  `revision`, so new demo assets cannot replace a runtime's reviewed expectations.
- `suite.py` runs a selection of the suite in a checkout and reads each test's
  outcome from pytest's junit report, refusing a selection pytest would not run.
- `leaf-dev flake NODEID...` runs tests from the working tree as 18 copies, six at a
  time, and prints every failure's message, since a load flake never shows serially.
  The copies share every fixed path a test writes in the checkout, such as an export
  under `.tmp/`, so a failure naming one is the copies racing there, not load.
- `leaf-dev bugback NODEID...` runs the tests on HEAD and with the branch's non-test
  change reverted, in a scratch worktree, and reports which went red.
- `leaf-dev bench-latency [BASE_REF]` times an open page's answer to a gesture, an
  agent write, and a revision in Chrome, with the traffic each causes, for a base
  runtime and HEAD's.
- `leaf-dev profile SOURCE TRANSITION` says where one of those transitions spends its
  time in this working tree: main-thread tasks up to the painted frame, forced style
  recalculations and the writes that invalidated them, and JS by function. Traces and
  CPU profiles stay in its own run directory under `.tmp/profile/`.
- `leaf-dev bench-check [BASE_REF]` times `leaf page check --render` on a few
  examples, base plugin against HEAD's, with no model, and prints each arm's wall
  time. Its arms, pages and state stay in its own run directory under
  `.tmp/bench-check/`.
- `leaf-dev eval [CASE]... --harness claude-code|codex|both` runs the eval catalog
  through Promptfoo on the working tree, and with `--base` the merge base too.
  `evals/README.md` owns the format and how to read the results.

## Examples and previews

- `leaf-dev preview [EXAMPLE]` serves one example or developer fixture as a live
  page, or exports it with `--export`. `/developing-leaf` says when to pass `--user`.
- `leaf-dev corpus` generates `examples/corpus.html` and its companions.
- `leaf-dev keydocs` writes the `x-` key index in `docs/registry.html`.
- `leaf-dev catalog` refreshes `docs/examples.html` descriptions from example metadata;
  the site build derives them again before publication.

## Website and demo

`leaf-dev distribution --output NEW-DIRECTORY` builds the prepared Git payload.
`publish-distribution DIRECTORY` advances the `prepared` branch with a verified
payload from current main, retaining source ancestry and using a normal push.
The `prepared-install` workflow owns publication. Never merge that generated
branch into a development branch. Source checkouts remain directly runnable;
consumer installs and custom packages require no browser compiler.

CI, `worker/`'s npm scripts and `.config/wt.toml` run these. The images they
write live in `max-sixty/leaf-assets`, so outside `.tmp/` they write only the pin
in `leaf-assets.json` and the README's image URLs that name it.

- `leaf-dev site` builds <https://leaf.page/> into `.tmp/site`, its edge assets into
  `.tmp/site-assets`, and the prepared installation that vendors its pages and that
  the container image installs into `.tmp/site-install`; `--output` gives an
  independent build its own destination. Writes to one destination are serialized.
  `npm run dev --prefix worker` builds and serves it through `wrangler dev`, which
  chooses available HTTP and inspector ports.
- `leaf-dev verify-site` verifies a release at an origin, or with `website-worker`
  the site `leaf-dev site` built, through the local Worker and container, and prints
  the startup profile; CI runs `website-worker` on pull requests. Each local run
  has private listener ports, temporary site, container build context and state,
  and retained logs under `.tmp/verify-site/run-*/`. `worker/README.md` owns hosted-agent
  diagnostics and the failure contract.
- `leaf-dev journey TARGET` runs one user's journey against a real agent: it asks
  for a release that passed its checks to be recorded, and requires a revision and
  a reply; on a harness ("Harnesses" below) it takes further steps. For the website,
  TARGET is an origin, `website-adapter` for the website's adapter on this machine,
  or `website-worker` for the built site through the local Worker and container,
  and the user is in Chrome; `publish-site` runs it against each release. It prints
  one JSON sample: each comment's milestones timed on the page server's clock from
  its admission, and in Chrome what only the browser sees from the send. Each sample
  is also appended to `$XDG_STATE_HOME/leaf-dev/journey.jsonl` on the machine that
  ran it, and `leaf-dev journey-chart` prints an `lf-chart` of those samples, for
  the latest version each target ran at each user end, to put on a page.
- `worker/deploy-dev.sh` (`npm run deploy:dev --prefix worker`) deploys the checkout
  to the standing `leaf-website-dev` environment and verifies it. Production deploys
  only through `.github/workflows/publish-site.yaml`.
- `leaf-dev fetch-assets` fetches the `max-sixty/leaf-assets` revision pinned in
  `leaf-assets.json` (`leaf_assets.py`, which the site build also calls).
  `leaf-dev refresh-previews`, run as `wt refresh-previews`, recaptures the catalog
  previews under its `examples/`, republishes them, and moves the pin.
- `leaf-dev record-demo` regenerates the README's demo GIF and stills and the site's
  card under its `demo/`, and publishes them the same way.
- `leaf-dev publish-media FILE...` adds media the example pages show under its
  `examples/media/`, and moves the pin.

## Harnesses

`leaf-dev journey TARGET` also runs the user's journey on a real session of each
harness, with this working tree as its plugin under a throwaway home holding only
the host's login. TARGET is `claude-code` (interactive, in a tmux pane),
`codex-app-server` or `codex-queue` (a Codex task on that transport; the queue is
the desktop app's and IDE extension's), or `pi` (the version `dev/pi/package.json`
pins, in RPC mode, on a copy of the host's Codex login). `journey.py` owns what the
harnesses share: the isolation and its evidence under `.tmp/journey/`, the
`Terminal` every wait hears the session through, and the `User`, at one end for
every step: over HTTP by default, posting each comment as the page's tab does with no
browser, which is what agent and harness behaviour and timing need, or in Chrome with
`--browser`, typing each comment as a user does and timing what the page shows, the whole
user journey. Either way each comment is timed from the page's log on the server's
clock, with the agent's work on it split into delivery, model and tool phases.
Between steps the journey fails unless every comment so far has one reply and
entered the session's context, and the page's claim names the session with its turn closed; what else each
target checks is its harness's promise, which its module lists with its steps
(`journey_claude_code.py`, `journey_codex.py`, `journey_pi.py`). `--hooks-module`
turns Claude Code's hooks module on; `--preview` has Codex serve the page through
`leaf-dev preview --user` and checks it recovers its page server. These targets
spend the host's logins, so CI does not run them.
