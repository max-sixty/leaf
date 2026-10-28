# Validation contract

Each input is validated once, where it enters, and code past that point reads it
directly:

- an event, whether a browser posted it or a command wrote it, at the append door
  ([events.md, "Admission"](events.md#admission));
- a page's authored source at `check_source` (`validation/source.py`), which `page
check`, activation, `page stamp` and `page init` all run ("Static validation");
- message markup an agent hands in at `admission.check_markup`, which applies the same
  structure and vocabulary checks to an HTML fragment;
- a layer `page init` would vendor at `composition.incoming_registry`;
- what only a browser can see at `page check --render` ("Browser validation").

## Static validation

The static check reads the exact `index.html` with no browser. It is deterministic and
near-free, which is what makes running it on every save affordable, so keep a new
check that way and put anything needing a browser in the browser half. The rules live
in `validation/source.py` and `validation/markup.py`; these are the decisions behind
them:

- Page code may be any script, classic or module, inline or a file, with its literal
  local import graph under `/page/`. Delivery defers a classic script and drops
  `async` (`revision_delivery._deferred`), so every script runs after the runtime has
  read the page and while it listens for errors. Anything on another server is named
  by its http(s) URL and loaded as written.
- The runtime, theme, page identity and declarations about the whole document (a
  `<base>`, an http-equiv `<meta>`, an import map) belong to delivery, which inserts
  them at the start of `<head>`, so source may not author them. Message markup may not
  author the last three either, since it renders in every revision.
- The runtime's `lf-` and `data-lf-` namespaces are reserved, for names it uses now
  and later. No id takes the shape of a logged event id (`schema.EVENT_ID`), since a
  command's ID names a widget or a message in one address space.
- Historical references never veto a revision: wording, placement, subjects and
  vocabulary may all change. The check reports the threads that move (events.md,
  "Anchors"), and activation records them in the same page transaction as the
  revision.

The effective registry is validated only where it differs from the active revision's
captured copy. Vendored sheets are validated when `page init` composes them.

A reference to a thread, such as a widget's `resolves`, is checked against the thread
ids the log holds (`thread_context.thread_ids`), including a thread whose opening
comment the log lost. A live sample template's child is checked as a page against its
initial history wherever the template is declared, in the page or in a message's
frozen markup (`validation.source.sample_errors`; `sample_content.py` builds that
history). A `data-sample-threads` thread the parent's log does not hold yet leaves the
child without it, so a first version may name threads whose seed log is unwritten.
Corpus generation composes from the shipped log, so there a missing thread is a
mistake in the declaration and is refused.

Which writes check and publish the saved source is the writer's: progress and failure
replies use the active revision, a detach still checks the saved source, and a
successful reply publishes the source it checked (`thread._compose_and_append`, and
`revisioning.py`'s header for how a publication and its anchor moves land together).

### Page code

Plain `page check` runs one browser reading as well. A page that runs code of its own,
or places a data widget or a widget naming page media, is run once, and fails on each
`error` event its runtime posts, the same events `leaf wait` delivers
(`render_gate/page_code.py`). A thread command runs message markup placing one of those
widgets the same way before it posts, apart from the page lease, and refuses it on the
same reports (`render_gate/command.message_check`); markup without one waits on no
browser.

Leaf runs without a browser. Where the host has none, every browser gate (this run,
`--render` and `package check --render`) is skipped with a note and leaves the status
alone, since the page posts the same `error` events whenever a browser draws it
(`render_gate/command.run_in_browser`).

## Delivery policy

A page carries no content policy of its own: its code is its author's, and may load,
fetch and compile what it likes. Every served HTML response, historical versions and
sample children included, adds `frame-ancestors 'self'`
(`structure.FRAME_ANCESTORS_CSP`), so a different origin cannot frame a live page and
disguise its decisions under another interface, even where same-site cookies would
authorize the request. Same-origin parents may embed one, since they already share its
DOM and request authority. The published site's Worker reads the header from the site
manifest. A standalone file has no response header and so no framing guarantee. Every
response carries `X-Content-Type-Options: nosniff`, and the data and media routes serve
only JSON and admitted image types, so neither can become a script module.

## Browser validation

`page check --render` loads the exact current source in the host's browser once
before a page's URL is first handed over (`render_gate/browser.py` says which browser
and why). It refuses a version only for a fault its author can fix by editing the
page; a fault in Leaf's own chrome or theme belongs in the suite
(`render_gate/readings.py`, header). `render_gate/version.render_version` is the one
implementation the command and the `tests/*/test_render_*.py` modules call over the
shipped examples, and `_render_version_attempt`'s docstring lists what it reads. Its
desktop is the window of the browser that last reported viewing the page, or a fixed
laptop window (`render_gate.command.desktop_viewport`), and the sweep and screens use
that window's height.
The suite uses Chromium's headless shell; the end-to-end render-check tests cover the
launches the command uses.

Every widget output published during the check, including one subsequently withdrawn
or published by a disposed sample, is validated against its data contract. A failure
identifies the producer and the captured owners of its module, output declaration
and contract (`data_contracts.output_findings`).

A decision in force may paint over a changed authored baseline. That is the state
fold's behavior, not a reason to refuse the revision; `restated` retracts a decision
when the agent needs a fresh answer.

Every check behind `page check` reports a record (`findings.py` owns its fields and
words), and the browser probes return those records rather than sentences.

A version that passes gets screens for its author to read (`render_gate/screens.py`).
They are the command's, so the suite takes none.

The gate serves its probe modules and the runtime they import from the Leaf running
the command (`runtime_selection.py`), so the probes always meet the runtime they were
written for. The vendored layer is the page's to keep, so the gate does not re-vendor
it.

## Passages

The browser resolves an anchor and records it in the log, so `leaf thread create` reads
the active revision's file the way the anchor pass reads the DOM. `passages.py`'s
header comment owns that reading: what the registry's `x-says`, `x-verbatim` and
`x-retired-when` contribute, and where a fence stops a quote. Both runtimes take
whitespace collapse from the kernel's `$passages`.

A quote never spans a fence, so a passage the file cannot read is refused when the
comment is written rather than detaching later in the user's browser; anchor on the
widget's element (`--section`) instead. A file-side quote must also be unique in its
declared section, and widget source, retired text and repeated passages are refused.
Runtime anchors were resolved against rendered words, so admission does not recapture
them.

The render gate holds each `x-verbatim` owner to the file reading
(`readings._verbatim_findings`). It pairs each owner with its source by document-order
occurrence, so no authored id is needed, and compares the rendered words with the
passage a user can point at: user body rewrites in force replace authored words,
retired slots contribute none, and declared generated children join their owner. Page
markup is read at the rendered revision, and frozen thread markup over its thread's
whole action window.

## Parsed source

TurboHTML's WHATWG tree drives the one `SourceDocument` reading of what markup declares
and says, with exact source spans, and tinycss2 reads the CSS a `<style>` block holds.
A new question about a page becomes a field on one of those readings rather than a
pattern over the file's text, because a pattern answers something adjacent to the
question asked.

Immutable inputs are read once for as long as the process keeps the page's memory
(`page_memory`): a stored revision through `revision_artifact.read_revision`, a
candidate through the one `SourceReading` its check takes, which the revision it
activates adopts, and each logged markup fragment through
`thread_context.logged_fragment`. Markup a writer hands in is parsed afresh at its
gate.
