Subject: a simplification review of the `harbor` service, for its maintainer. Present it as a Leaf page. Three reviewers read the code and measured where they could.

Findings:

1. Accidental complexity has five causes. A table: (cause, where, size, fix) — parallel paths (~2,100 lines; one path per job), a private copy of the asset bundle in every deploy (180 MB on disk, 30 MB distinct; shared store), hand-wired factories in `app.js` (900 of 2,800 lines; one context object), arrangement-heavy tests (30k of 55k lines; parametrize), prose restating code (~800 lines; docstrings).

2. Six jobs have two implementations. A list:
   - The mobile web view is a second page renderer: `mobile/view.html` paints the document with its own sanitizer and selection capture that skips the uniqueness check the main renderer applies.
   - The website re-derives the projection in JavaScript (`docs/session.js` reimplements folds that `projection.py` owns; nothing checks they agree; the site build can bake Python output as static JSON).
   - Three state assemblers call the same six primitives and emit different shapes (`agent_state.py`, `served_state/`, `transcript.py`); one view per transaction with three serializers.
   - Work claims are a second state store beside the log (`status.json` replace-in-place; predicate written three times); append a `claim` event instead.
   - Two config loaders: `config/env.py` and `config/file.py` each parse the same twelve keys with different defaults for three of them.
   - Three constants are spelled in both languages, with three tests checking the pairs match; generate from one JSON file.
   Evidence for the six (file references and line counts) exists and should be available but need not be read to follow the findings.

3. The test suite spends three lines arranging for each line asserting: of 55k test lines, 10k assert and 30k arrange; the render files use `parametrize` 20 times at 25 lines per test; 4,000 lines of JavaScript sit inside Python string literals and are not linted, though an `evaluate_probe` helper over lintable `.js` files already exists and is used 30 times. No decision here; the fix follows from the repository's rules.

4. Order of work: parallel paths first, then the bundle store, then tests.

Decisions the maintainer must make (the code cannot supply the answer):

- On the mobile renderer (finding 2, first item): (a) delete the mobile renderer and serve the main page's URL to mobile hosts (effort low, removes ~1,100 lines, reviewers' recommendation), (b) delete the whole mobile surface including its build and the `mobile-sdk` dependency (effort medium, removes ~2,300 lines, loses the embedded-in-app route), (c) keep both and bring the mobile capture up to the shared rules.
- On the config loaders (finding 2, fifth item): (a) keep the file loader, have env override its keys (effort low, recommendation), (b) keep the env loader and drop file config (effort low, breaks two deployments that use files), (c) keep both and generate both from one schema (effort medium).
