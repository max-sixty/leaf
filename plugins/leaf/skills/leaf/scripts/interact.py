#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8", "jsonschema>=4", "tinycss2>=1.4"]
# ///
"""Serve and mediate an interactive leaf page.

A `uv` script: the PEP 723 header above declares the dependencies, and
`interact.py.lock` beside it pins them, so every install runs the same versions;
editing the header re-resolves the lock on the next run. The lock's URLs are
pypi.org's, which a host serving its own mirror cannot fetch, so `bin/leaf` falls
back to resolving the header against that host's index. `uv` is the one
software prerequisite for the whole plugin — no venv to create, no build step.
The host must supply POSIX `fcntl` file locking: the event log's atomic attempt
identity and every other cross-process update use that one primitive, and a
platform without it is refused rather than silently running unlocked.
Run it with `uv run interact.py <group> <command> …`, or as
`leaf <group> <command> …` through the plugin's `bin/leaf` launcher.
Claude Code puts that launcher on PATH; Codex resolves it from the active skill.

A page directory holds:
    versions/v1.html…    immutable page versions (the agent writes them). The server
                         exposes a version only once `version publish` lands its
                         note, after `version check` passes, so a half-written or
                         broken file is never live to an open browser.
    leaf.js          the runtime (widget layer + comment layer), served at /leaf.js
    theme.css            tokens, element styles, class idioms, element-widget CSS
    registry.json        the widget vocabulary: JSON Schema per lf-* tag, plus the
                         layer-wide facts under $ — $idioms, $languages, $keys (what
                         each x- key means), and the page's vocabulary stamp ($events,
                         x-state): the one statement of what this page's vendored
                         runtime speaks
    guidance/            package-owned guidance grouped by audience. Files with the
                         same name concatenate in package order; `page catalog` adds
                         author.md to the vocabulary, while `page guidance` reads any
                         audience
    icon.svg             the mark the tab wears, whose lf-tone element the runtime
                         paints in whatever colour the banner's dot is wearing — so a
                         reader with six leaves open sees which one wants them
                         without opening any
    runtime/             private modules imported by the stable /leaf.js entry
    widgets/             one ES module per upgraded widget (lf-tabs.js, lf-diagram.js)
    vendor/              vendored third-party assets (mermaid.min.js, sortable.esm.js)
    media/               images the page shows, each named by the hash of its bytes
                         (`page media`). Not vendored — this is the page's content,
                         not the layer's — but served the same way.
                         Content-addressing is what lets content live here at all:
                         a name means one set of bytes forever, so a version the
                         user approved cannot show them different pixels later,
                         and two versions showing the same screenshot share one
                         file rather than carrying a copy each. It is also the
                         only door an image has into a page: the page's author is
                         a language model, and a screenshot is a megabyte of
                         base64 it cannot type — nor should each version carry a
                         copy that `version check` walks and a browser reloads.
                         So the transport was never an optimisation over
                         inlining; inlining was never available
    comments.jsonl       append-only event log; an event's seq is its line number (1-based)
    status.json          the agent's declared state: {"state": working|waiting|idle, "detail", "ts"};
                         detail is the finer grain the banner reads out after the
                         state — what the agent is doing while working, what it
                         needs from the reader while waiting;
                         "work" holds typed, sequence-bounded claims on comment
                         threads or page widgets. At the state boundary these
                         private records become canonical claim updates, which
                         their local seats show beside the page-wide line
                         (`leaf status … --on`);
                         when `leaf wait` prints for a non-working page, it
                         writes working with "handoff": true until the agent's
                         own `leaf status` lands
    waiter.lock          bare-shell `leaf wait` lease, held open and locked for
                         the command's life. A host session holds one lease at
                         sessions/<id>.wait instead, because one wait watches all
                         of that session's pages
    viewed.json          when a browser last polled the page, bumped (throttled)
                         by the server on /api/state; absent for a page nobody
                         has ever opened, which would otherwise be
                         indistinguishable from one the user studied and left
    cursor.json          seq of the last user event acknowledged after the complete
                         batch reached its next durable consumer — written by
                         `leaf ack`
    service.json         {"host", "bind", "port", "enabled", "lifetime"}: the
                         durable desired service. It preserves the exact URL an
                         open browser polls and whether a session may end it.
                         A crash leaves it enabled so `leaf wait` can revive it;
                         `server stop` disables it and leaves the address and
                         lifetime ready for a later start. The key in the URL is
                         the machine's, not the page's, and lives in the state home
    server.lock          a contentless live-server lease, locked for the process's
                         whole life. The kernel releases it on a crash. A stop
                         asks the server to exit through service.json and waits
                         for this lease, so no listening or accepted socket
                         remains when the command returns
    claims/              outside the page, one atomic record per resolved page:
                         its last claimant, release time, and the lifetime it
                         rests on.
                         Keeping provenance outside the disposable page lets
                         ownership discovery survive a page moving between sessions
status.json is a claim, and a claim never expires on its own: an agent that
stopped watching renders exactly like one that is watching and has nothing to
say, so a comment can sit unread with the page still reading "Claude is
working". The directory therefore also carries what it can prove — a lease only
a live `leaf wait` can hold, the acknowledgement cursor, and whether the owning
session's lifetime stands — and `/api/state` ships those beside the claim, so the
banner can say when
the claim has outlived its evidence. When a wait prints for a
non-working page, it marks the status it writes "handoff", which dates that
claim: after acknowledgement the agent writes its own `leaf status`, so a
handoff mark that survives means a dropped pickup rather than a long turn, and
the banner gives it a much shorter rope. Wait output that lands while the agent
is already working leaves the existing claim untouched; there is no pickup gap
to date.

So a claim of work has to be renewed, and the command that makes one renews it.
`--on` names the comment thread the work is about, so one check-in moves both
the page's line and the note the reader sees under their own words in the
comment panel, where it stands until the agent's next word in that thread. That
is how a claim crosses a turn boundary the session cannot write across: nothing
in a session touches status.json while its turn is over, so work handed to a
delegate is renewed from the delegate's own hands or not at all.

Where nothing answers for the claim at all, the banner drops the claim rather
than repeating it. A claimant whose lifetime has ended settles the question
outright; a page nothing ever claimed has only the claim's own age to go on, so
it falls to the same grace period. Either way the page is unheld, and the banner says
that instead — "no session holds this page" is a fact the banner computed, where
"Claude is working" would be a fortnight-old sentence someone else wrote. Unheld
is also not a fault: a page that stands for weeks (below) spends most of its
life unheld, and picks up again the moment a session takes it.

The `hook` command closes the same gap from the agent's side. Registered on
Stop, UserPromptSubmit and SessionEnd, it refuses to let a turn end with one of
this session's pages unwatched, surfaces unacknowledged user events at the next
prompt, and releases the session's page claims when it exits. Session death is
not completion or an explicit stop: work status and desired service stay as they
were, while a session server retires once no live successor has claimed it. It
finds the session's pages through the claim records under
~/.local/state/leaf/claims/. A record is keyed by its resolved page path and
retains the last claimant as provenance after release; `released: null` and a
live lifetime — the process its pid names, or the job directory a background
job records — are what make it active. Absent the host identity the environment
carries, nothing is claimed and the hooks stand down. What the environment
cannot carry is the session's own lifetime, and `session_lifetime` says where
each host's lifetime comes from. `hooks/scripts/loop-guard.py`, which the hosts
actually run, decides none of that: it runs this command under `uv` and stays
silent when it cannot get an answer, so every rule above has one reading and a
leaf bug costs a turn nothing. Unacknowledged events are the one
thing `leaf status <page> idle` can't close over: idling is how a leaf ends, and
one can't end on comments nobody read.

A session's leaves cost it one long-running command between them, and that
command is the watcher. The two jobs end in opposite ways: `leaf wait` has to
exit, because its exit is how what the user said reaches the agent; the server
has to not exit at all, because the browser polls it between turns and straight
across every wait. So no single process does both. Only the watcher belongs to
the session, and one watcher is enough: it watches every page the session
holds, re-reading the set on each pass, and delivers one page's batch under a
first line naming the page. `server start` spawns the service into a session of
its own and hands back the URL that process printed and the lifetime it
recorded — so a killed background task costs only the watcher and leaves every
page up, and recovery is one `leaf wait`.

Whether a session's end reaches a server is decided at launch and written in
service.json as its lifetime. A serve from an agent host records the page's
claim under the state home's claims directory. Claim replacement and release
cross the page transaction: a
successor arriving before the session server's final recheck keeps that process;
one arriving afterward finds the old process and lease already gone and revives
the still-enabled service. Neither path changes the page's authored work status.
A serve from a bare shell — a terminal, a launchd job — claims nothing, and that
is the standing serve: a long-lived dashboard someone leaves open for weeks.
`server start --standing` makes the
same statement from inside a host: the launch declines the claim, for a page
meant to outlive the session that starts it. No daemon is involved, and a server
that dies under a `leaf wait` watching an enabled page is revived with the
lifetime and exact URL in service.json. `leaf server stop` is a standing
server's one reaper, and that is the whole of what "standing" means. A session
that picks the page up later owes it a watcher while the session lives, exactly
as it would any page. Its claim comes and goes without changing the standing
service or the page's status.

`page init` vendors the runtime, theme, registry, widgets, and vendor assets into the
page directory. Leaf's kernel comes first, followed by the bundled default package,
any explicitly selected packages, the user's package (~/.config/leaf/), and the
project's package (./.leaf/). Theme stylesheets concatenate in that order, so a package
can override one token or rule without copying the defaults. Registry entries
merge by top-level name, with a later package replacing one complete entry rather
than deep-merging its schema; runtime, widget, and vendor files replace by path.
The page directory itself lives wherever the caller says —
conventionally ~/.local/state/leaf/pages/<slug>/ — and is self-contained,
so an approved version can't change under its user; re-running `page init`
is the explicit re-vendor, noted in the next version's changelog. A served page
is first stopped, which disables its desired service and waits for the process
and every accepted connection to retire. After re-vendoring, `server start`
restores its URL and lifetime; its status needs no maintenance copy. One
transition covers start, stop, init, contract-bearing CLI writes, and preview
reads. Stop retains it through the server's release, so no operation can cross
the old process's contract.

The registry is shared by the JS runtime, the POST and re-vendor action gates,
this file's `version check` and thread-markup validation, the passage reader
`leaf comment` anchors through, and the `page catalog` the agent reads. Each
successful init embeds a fresh `$layer.generation` in both leaf.js and the
registry. State reports it and event requests carry it; the server repeats it on
contract responses, so an old or half-loaded tab reloads before a replacement
server can interpret or append its event. Every widget entry is JSON Schema over the instance built
from the element's attributes
(values as strings, flag attributes as True). What JSON Schema has no
vocabulary for rides in the custom keywords below:
    x-parent    the tags this element may be a direct child of
    x-content   the content model: "prose" (flow content, widgets welcome),
                "items" (element children only, no loose text), "data" (one <pre>
                holding text in the notation the description names), "none"
                (empty). <pre> because a data body's whitespace is load-bearing
                and that tag is HTML's only way to say so — anywhere else,
                whitespace survival is a CSS fact, and a tool reading the markup
                alone collapses what it cannot see the rule for.
                Children that name this tag in x-parent are admissible under any
                model — that is what x-parent means. x-parent is a list because
                one element can belong to two holders: a chip is written in a
                lf-option and in a lf-variant, which are the same shape either
                side of the decision.
    x-inline    true when the element is set among the words around it rather
                than laid out as a region of its own. The render gate floors a
                widget's box to catch one that upgraded into nothing, and an
                inline element's box is just the words in it — so an inline
                widget keeps the height floor and takes no width floor at all; a
                chip reading `£9` is 31px wide and correct. Declared rather than
                read off the rendered display, because the rendered display also
                answers "inline" for a widget whose theme rule went missing.
    x-conversation  when selects the page instances whose exact-section threads render
                textually inside the widget as well as in the comments panel. The
                module places the conversationBox; both views share one reply draft,
                while interactive reply markup stays in the panel. An optional hold
                label adds the stronger send route: its unresolved comment thread is
                the hold, so resolving releases it and undoing resolution restores it
                without a second state event to reconcile.
    x-work      the local seat for a typed widget work claim: "content" admits a
                generated line in block prose, while "conversation" places it at
                the start of the matching x-conversation. An optional when narrows
                the instances that have that seat. x-content alone grants nothing.
    x-says      attributes whose values are words the reader sees, mapped to the
                edge they render at ("before" = first child, "after" = last).
                The runtime renders them as real text there, because a user can
                only quote what a text node holds — and the theme's matching
                `content: attr()` puts the same words on a page with no script.
    x-paints    attributes whose value the theme renders as paint and no words — a
                task's status marker, an event's kind, the ring on a recommended
                option. The runtime speaks each one as a word clipped to nothing
                (renderQuiet): the value itself, or, for a flag attribute that
                carries no value, the attribute's own name. Declared per
                attribute rather than assumed for every painted one, because
                paint that merely emphasises the words beside it — a chip's
                tone — would be the same fact said twice to whoever is
                listening.
                What the key cannot reach is a painted fact whose meaning is
                computed rather than stated: lf-metric's `direction` means
                better or worse only when crossed with the sign of `delta`, and
                "up-good" said aloud means nothing. Declaring that would put a
                rule in the registry rather than a name, and buying it with a
                module would cost lf-metric more than it bought: an upgraded
                element with no x-verbatim is opaque to quoting, so the caption
                would stop being something the reader can point at — to gain a
                word they can already infer from the number.
    x-refers    attributes whose values name another element on the page. The
                reader follows one, so `version check` holds each to an id the
                version actually carries; a reply's fragment is exempt, having no
                page to check against.
    x-tone      the attribute whose value names one of $tones.names, the semantic
                tints the theme paints. Declared rather than known by tag, so a
                second widget taking a tone costs a line and no new reader — and
                the list lives with the layer, since the palette is the page's
                rather than any one widget's.
    x-language  the attribute whose value names a code language. The layer colors
                what $languages.names holds, so a widget taking one declares which
                attribute carries it, and `version check` validates every such
                attribute against that list — the same list a plain <pre><code
                class="language-*"> is held to.
    x-lines     attributes holding 1-based line references into the nearest data
                body — the element's own <pre>, or its holder's (lf-note's `at`
                names a line of its lf-code). `version check` refuses a reference
                outside the body or a range running backwards (line_ref_errors);
                the modules render a miss silently, which is why the door owns
                the check.
    x-upgrade   true when the runtime imports /widgets/<tag>.js for it
    x-verbatim  true when an upgraded element's body reaches the reader as its own
                words. Otherwise a module may render anything in place of them, so
                `leaf comment` treats the element as opaque and won't quote
                through it.
    x-shadow    true when the module renders the page's words into a shadow root.
                The passage walk, the selection capture and the id lookups cross
                exactly the declared roots — an undeclared root's words are
                invisible to every one of them, so a widget that attaches one
                declares it, or its quotes anchor beside the reader's selection.
    x-exhibit   true when everything inside this element is quoted material — a
                specimen, not the page speaking. Interactive widgets inside take
                no input: modules consult `quoted()` before wiring affordances,
                and the action door refuses a send from one regardless.
    x-visual    true when the element renders as a picture: a click anchors on
                the element whole, there being no text in it to select — the
                same anchor a click on an <svg> or <img> makes.
    x-wide      the width model, for evidence whose size follows its content
                rather than the measure prose is read at. "box": the widget lays
                its content out into whatever width it is given — a board's
                columns — so it stands at the one width the whole vocabulary
                shares. "drawing": the widget renders one thing drawn at a size
                of its own — a diagram's graph — so its box is the clip around
                that drawing: the room the page has, with the drawing as near
                the column's axis as the claimed margins allow, and scrolling
                where even the room is short. The runtime marks what this key
                declares and theme.css spends the room the layout measured, so a
                page's shape follows what it holds and no page states a width.
    x-state     the widget's action verbs: each verb's detail schema, semantic
                facet, fold unit, optional current-state prerequisite, and the record
                form its state takes in markup. Every applyAction is absolute, so the
                user's standing state is a fold — the last surviving action per owner,
                unit, and facet — and one declaration drives the browser and POST
                eligibility doors, the re-vendor contract gate, check's state gate,
                the record-lag report, the runtime's pending mark, and the diff's state
                half (see $state in the registry).
    x-report    the widget's agent channel: report verbs a worker folds onto the
                page through `leaf report`, each with a detail schema, facet,
                fold unit, and *required* record form — declared state only, never
                body words, so a report never touches the passage reading. The
                precedence is opposite to x-state's: an action outranks every
                later version until `restated` retracts it, while a report is
                provisional and stands only until a version answers it by id —
                `reports` on the note, written by `version publish`; `overruled`
                on the element is how a version keeps its own state over one.
                See $report in the registry.
    x-retired-when  the outcome under which this element leaves the page — the
                slot a decision retires — with x-parent naming the widgets whose
                decision reaches it. That one holder/slot relation is the whole
                of what a decision settles: the anchor pass's skip list on both
                sides, and which ids a version honoring the decision may drop
                (retirable_ids). The browser's half of the skip keys on
                data-lf-state, which the layer itself paints onto the holder as
                replay applies the decision — with data-lf-retired painted onto
                the retired slots, which one theme rule hides — never a module
                obligation; the render gate compares both halves back against
                the log (RETIRED_SLOTS).
    x-withdrawn-as  the outcome an unanswered instance stands as when the author
                takes it back: a withdrawn suggestion leaves the page where a
                `reject` would. Without it a question, once asked, stays until
                the reader answers it — nothing else says which slots were the
                author's to take back and which hold the page's own words.
    x-awaits    an instance of this tag is a standing request to the reader.
                `when` says which instances ask (attribute values, a flag's
                being true and false); `answers` names the x-state verbs that
                close it; `rollup` derives nested requests from ordinary
                interventions and child roll-ups; `all` names the answer one
                blanket press takes. The banner, navigation, help, and
                conditional actions all read this projection. Recorded
                attribute and scalar values read from the replayed page; other
                answers read from their surviving fold entry (see $awaits).
    x-example   one authored example, printed by `page catalog`

Event kinds: comment (optional anchor {section, quote, and the neighbouring
text as prefix/suffix where there is any, which is what tells two identical
passages apart; a browser selection on projected data carries datum,
the stable key local to section, instead of treating neighbouring values as
identity), reply (parent=id),
resolve (parent=id), unresolve (the reader reopening a resolved thread by parent=id),
done (user sign-off; the banner offers it, and this door
takes it, only on a page declaring <meta name="lf-review" content="sign-off"> —
approval is the page's ask, and a page that asks nothing gets no terminal
control at all), action (user; a widget reporting the
user editing the document through it — widget=element id, action=verb, detail
per widget, version the edit was made against), report (agent; a worker's
provisional state change on a page widget — same widget/action/detail/version
shape as an action, validated by the widget's x-report declaration at the
`leaf report` door, and standing only until a version answers it), note
(agent; per-version changelog, carrying `restated`: the element ids whose
decisions the publishing version took back, and `reports`: the report event ids
the version absorbed or overruled), error (the page's own runtime reporting a
failure in front of the user — author=page, heard by the watcher like a report
and never counted against the reader).

undo (the reader taking a gesture back, `undoes` naming it — a resolve, an
unresolve, or an action, per UNDOABLE_KINDS) is the log's one word for that, and
it names the gesture and nothing else: every other field is the target's to
state. It withdraws rather than deletes. Nothing is removed from the log; the
folds and the thread reading simply drop the event, so the page is what the
version says plus what still stands — the same sentence a reload has always
read, and the same one `restated` already writes from the author's side. What
the reader sees follows from that rather than from a second statement: where the
log still leaves the unit a state that can be stated, the browser states it (a
prior action's detail, or the placement the version's markup arrived showing) so
the page moves rather than being rebuilt; where the verb records nothing, and so
no state can be stated, the browser rebuilds that widget from the version's own
markup and replays what survives onto it. The door refuses an `undoes` naming
anything but an unwithdrawn gesture of the reader's own.

The server stamps every other
browser-posted event author=user; agent-side `leaf comment`, `leaf reply`, `leaf report`,
and `version publish` stamp the wire
role author=claude plus the posting session's own voice: `agent`, its display name,
and `session`, its host session id. Several agent sessions can write to one page,
so the voice is read from the poster's environment rather than from the current
watcher's claim record — and identity is the session id, because a display name
is anyone's to choose and two workers may share one.
A message body is Markdown, stored as typed and rendered by the page's own
vendored runtime — the browser is where the page's other rendering already
lives, and vendoring the renderer beside the panel's styles keeps the two
versioning together. A fragment link in a body — `[the group](#d-channel)`,
written by either author — points at an element of the page, and the browser's
own navigation carries the reader there, opening whatever tab or settled group
hides it. Two parts of that are the runtime's: handling an arrival aimed by such
a link (a ⌘-click opens a tab the browser answers before any widget has
upgraded), and marking a link this version can't follow, since a message
outlives the version it was written on. Raw HTML in a body renders as its own
characters, so text cannot inject markup. A widget in a message rides the
event's `markup` field instead, whose one door is `leaf comment`/`leaf reply`,
where it is validated against the vendored registry — the discussion-side analog
of `version check`. The browser door refuses the field, so everything in the log
under that name has been through the gate.

Either side can open a thread and either side can close one, and `author` is the
whole difference between them. The user selects a passage and the browser writes
the anchor from the selection; `leaf comment` writes its file-confirmable form from
a quote, reading the version the way the anchor pass reads the DOM (see
"passages" below). Projected data has no file-side value to quote: its browser anchor
adds the projection's section and datum key, and a CLI comment can still name the
authored projection seat as an element. Everything downstream already turns on
`author`: `leaf wait`
prints user events and the banner counts them, so Claude's own comment neither
wakes its own watcher nor reads as unanswered. Closing runs the other way round,
because a note's purpose is discharged by being read, and only the reader knows
that happened. So `leaf resolve` is the agent's door onto closing, and the
reader is still the one who ordinarily closes a thread. A thread the reader did
not close is the one settlement they cannot watch happen, so the panel and the
transcript both name the agent that did it.

Commands:
    status, wait, ack, comment, reply, resolve, report, events, transcript
    page       init catalog media state
    package    init check
    version    check publish export
    server     run stop

`version check` is a deterministic pre-handover lint (no browser, near-free;
`version publish` re-runs it on every version): the HTML parses with balanced
tags; one direct `<body><main>` contains all authored content; the page carries
exactly one external script
(<script type="module" src="/leaf.js">) and one stylesheet link
(/theme.css), both directly in `<head>` so the presentation boundary exists before
body paint; every lf-* element validates against the vendored registry
(schema, nesting, no self-closing form); every lf-* meta is a known page
declaration with an allowed value; each lf-suggestion is well formed (at most
one of each slot, at least one of them, no nesting, `resolves` naming a real
comment); ids are unique and every id from the previous version survives
unless the log settled the widget holding it; no fixed-pixel-width element
is wider than the readable column. Near-free and deterministic is what makes
running it on every version affordable, so keep a new check that way; anything
needing a browser belongs in `--render`.

`version check --render` adds the browser half, run once before a page's URL is first
handed over: the version loads in the machine's installed Chrome (Playwright
`channel="chrome"` — the caller supplies playwright, which `bin/leaf` does
on seeing `--render`) and the render invariants the static lint cannot reach run
against it — no console or page errors, no fail-soft error box, every visible
widget occupies real space, code that reads against the block it is set on, no
sideways scroll, in both color schemes.
The invariants live in render_version, which the tests/test_render_*.py modules drive over
the shipped examples. The suite uses Chromium's headless shell, while its
end-to-end render-check tests cover the installed Chrome launch used here.

Passages: an anchor is resolved in the browser and written down here, so
`leaf comment` reads a version the way the anchor pass reads the DOM — text in
document order, minus the runtime's own words, plus the words a widget says
through an x-says attribute, with one space wherever the enclosing text block
changes and whitespace collapsed. What the file cannot know is what a widget's
module will write, so the reading stops where the registry stops telling it: an
upgraded element is opaque unless x-verbatim says its body reaches the reader as
its own words, and an opaque element and each of its children is fenced. A quote
never spans a fence, so "the page has words here that the file doesn't" becomes
a refusal when the comment is written, rather than an anchor that detaches later
in the user's browser. Anchor on an opaque widget's element instead
(`--section`), which is the same anchor a click on a diagram makes.

A version is written in more than one language, and each language is read by a
parser for that language: _StructParser for what the markup declares,
page_passages for what it says, tinycss2 for the CSS a <style> block holds. A
new question about a version becomes a field on one of those readings rather
than a pattern over the file's text, because a pattern answers something
adjacent to the question asked — the readable-column check below carries what
that cost.
"""

import base64  # noqa: F401 - public facade re-export
import errno  # noqa: F401 - public facade re-export
import functools
import hashlib
import json
import os  # noqa: F401 - public facade re-export
import re  # noqa: F401 - public facade re-export
import secrets  # noqa: F401 - public facade re-export
import socket  # noqa: F401 - public facade re-export
import subprocess  # noqa: F401 - public facade re-export
import sys
import threading  # noqa: F401 - public facade re-export
import time  # noqa: F401 - public facade re-export
import zlib  # noqa: F401 - public facade re-export
from http.server import ThreadingHTTPServer  # noqa: F401 - public facade re-export
from pathlib import Path
from typing import NamedTuple  # noqa: F401 - public facade re-export
from urllib.parse import (  # noqa: F401 - public facade re-export
    parse_qs,
    urljoin,
    urlsplit,
)

import click  # noqa: F401 - public facade re-export
from jsonschema import Draft202012Validator  # noqa: F401 - public facade re-export
from leaf_interact.cli import create_cli
from leaf_interact.document import (
    COLLAPSE_CHARS,  # noqa: F401 - public facade re-export
    COLUMN_FALLBACK,  # noqa: F401 - public facade re-export
    EMPTY,  # noqa: F401 - public facade re-export
    LF_META,
    OPTIONAL_END,  # noqa: F401 - public facade re-export
    PAGE_CSP,
    SECTIONING_TAGS,  # noqa: F401 - public facade re-export
    _column_width,
    _overwide_elements,
    _StructParser,  # noqa: F401 - public facade re-export
    capture_anchor,
    collapse,  # noqa: F401 - public facade re-export
    css_syntax_errors,
    inline_presentation_override_errors,
    page_passages,  # noqa: F401 - public facade re-export
    parse_structure,
    parse_version,
    root_tokens,
    spoken,
    version_review_mode,  # noqa: F401 - public facade re-export
)
from leaf_interact.events import (
    AttemptConflict,  # noqa: F401 - public facade re-export
    AttemptExecution,  # noqa: F401 - public facade re-export
    _attempt_payload,  # noqa: F401 - public facade re-export
    append_event,
    build_threads,
    flocked,
    jsonl_line,
    now_iso,  # noqa: F401 - public facade re-export
    read_cursor,  # noqa: F401 - public facade re-export
    read_events,
    require_cross_process_locking,  # noqa: F401 - public facade re-export
    retractions,
    standing_work_claims,
    taken_back,
    thread_roots,  # noqa: F401 - public facade re-export
    thread_structure,
    undo_error,  # noqa: F401 - public facade re-export
    work_claim_version,
)
from leaf_interact.files import (
    _filesystem_case_sensitive,  # noqa: F401 - public facade re-export
    _path_location,  # noqa: F401 - public facade re-export
    json_bytes,  # noqa: F401 - public facade re-export
    latest_published,
    list_versions,
    located,  # noqa: F401 - public facade re-export
    location_is_within,  # noqa: F401 - public facade re-export
    locations_overlap,  # noqa: F401 - public facade re-export
    path_is_within,  # noqa: F401 - public facade re-export
    paths_same,  # noqa: F401 - public facade re-export
    published_versions,
    read_json,  # noqa: F401 - public facade re-export
    replace_files,  # noqa: F401 - public facade re-export
    version_name,
    version_num,  # noqa: F401 - public facade re-export
    version_path,
    write_json,  # noqa: F401 - public facade re-export
)
from leaf_interact.http import (
    Handler,  # noqa: F401 - public facade re-export
    full_state,  # noqa: F401 - public facade re-export
    handler_for,  # noqa: F401 - public facade re-export
    other_leaves,  # noqa: F401 - public facade re-export
    presence,  # noqa: F401 - public facade re-export
)
from leaf_interact.layer import (  # noqa: F401 - public facade re-exports
    LayerComposition,
    _init_page,
    _vendor_page,
    check_package,
    checked_inputs,
    checked_layer_inputs,
    cmd_init,
    cmd_package_check,
    cmd_package_init,
    compose_layer,
    composed_dir_files,
    composed_guidance,
    composed_theme,
    initialized_page_owning,
    input_paths,
    layer_inputs,
    overlapping_inputs,
    package_layer_inputs,
    package_page_overlap,
    package_roots,
    protected_package_paths,
    refuse_package_overlap,
    resolve_packages,
    validate_package_dir,
)
from leaf_interact.projection import (
    NO_RECORD,  # noqa: F401 - public facade re-export
    StateProjection,  # noqa: F401 - public facade re-export
    action_subjects,  # noqa: F401 - public facade re-export
    asking,  # noqa: F401 - public facade re-export
    canonical_updates,  # noqa: F401 - public facade re-export
    decisions,
    enclosing_widgets,  # noqa: F401 - public facade re-export
    folded_facet,
    markup_facet,
    page_ask_projection,  # noqa: F401 - public facade re-export
    page_asks,  # noqa: F401 - public facade re-export
    page_projection,
    projected_action_holders,  # noqa: F401 - public facade re-export
    quoted_in,  # noqa: F401 - public facade re-export
    record_lag,
    record_lag_entries,  # noqa: F401 - public facade re-export
    replayed_attrs,  # noqa: F401 - public facade re-export
    retirable_ids,
    retirement_holders,
    rewritten_bodies,
    state_projection,
    thread_ask_projection,  # noqa: F401 - public facade re-export
    thread_asks,  # noqa: F401 - public facade re-export
)
from leaf_interact.registry import (
    RegistryError,  # noqa: F401 - public facade re-export
    json_validator,  # noqa: F401 - public facade re-export
    layer_generation,  # noqa: F401 - public facade re-export
    load_registry,
    merge_layer_entries,  # noqa: F401 - public facade re-export
    read_registry_entries,  # noqa: F401 - public facade re-export
    require_registry,
    retirement_slots,  # noqa: F401 - public facade re-export
    validate_registry,  # noqa: F401 - public facade re-export
)
from leaf_interact.render_checks import (
    BAKE,  # noqa: F401 - public facade re-export
    CLIPPED_CONTROLS,  # noqa: F401 - public facade re-export
    COVERED_WORDS,  # noqa: F401 - public facade re-export
    MISPLACED_BOXES,  # noqa: F401 - public facade re-export
    OPEN_ROOTS,  # noqa: F401 - public facade re-export
    PAPER_WORDS,  # noqa: F401 - public facade re-export
    RELATIVE_REPLAYS,  # noqa: F401 - public facade re-export
    RENDER_VIEWPORT,  # noqa: F401 - public facade re-export
    REPLAY_OVERRIDES,  # noqa: F401 - public facade re-export
    RETIRED_SLOTS,  # noqa: F401 - public facade re-export
    SERVED_TIMEOUT_MS,  # noqa: F401 - public facade re-export
    SILENT_WORDS,  # noqa: F401 - public facade re-export
    TINY_BOXES,  # noqa: F401 - public facade re-export
    TRAPPED_MARGINS,  # noqa: F401 - public facade re-export
    UNDECLARED_ATTRS,  # noqa: F401 - public facade re-export
    UNMARKABLE_ITEMS,  # noqa: F401 - public facade re-export
    UNREACHABLE_WORDS,  # noqa: F401 - public facade re-export
    UNREAD_SYNTAX,  # noqa: F401 - public facade re-export
    WITHHELD_ROOM,  # noqa: F401 - public facade re-export
)
from leaf_interact.rendering import (
    MOVING,  # noqa: F401 - public facade re-export
    RESIZE_OBSERVER_ERROR,  # noqa: F401 - public facade re-export
    UPGRADED,  # noqa: F401 - public facade re-export
    WINDOW_ERRORS,  # noqa: F401 - public facade re-export
    _render_version_attempt,  # noqa: F401 - public facade re-export
    cmd_export,  # noqa: F401 - public facade re-export
    export_page,  # noqa: F401 - public facade re-export
    inline_assets,  # noqa: F401 - public facade re-export
    preview_server,  # noqa: F401 - public facade re-export
    previous_version,  # noqa: F401 - public facade re-export
    recurring_resize_observer_error,  # noqa: F401 - public facade re-export
    render_check,
    render_version,  # noqa: F401 - public facade re-export
    resize_observer_error,  # noqa: F401 - public facade re-export
    served,  # noqa: F401 - public facade re-export
)
from leaf_interact.schema import (
    _DIR_FILES,  # noqa: F401 - public facade re-export
    ACK_BATCH_INSTRUCTION,  # noqa: F401 - public facade re-export
    ANSWER_ASK_INSTRUCTION,  # noqa: F401 - public facade re-export
    ASSETS,  # noqa: F401 - public facade re-export
    BINARY_TYPES,  # noqa: F401 - public facade re-export
    BROWSER_DIRS,  # noqa: F401 - public facade re-export
    CONTENT_TYPES,  # noqa: F401 - public facade re-export
    DEFAULT_PACKAGE,  # noqa: F401 - public facade re-export
    EXTENSION_SCHEMA,  # noqa: F401 - public facade re-export
    GUIDANCE_DIR,  # noqa: F401 - public facade re-export
    GUIDANCE_FILE,  # noqa: F401 - public facade re-export
    KERNEL,  # noqa: F401 - public facade re-export
    KEY_COOKIE,  # noqa: F401 - public facade re-export
    LAYER_PLACEHOLDER,  # noqa: F401 - public facade re-export
    MEDIA_DIR,
    MEDIA_TYPES,
    NO_KEY,  # noqa: F401 - public facade re-export
    ORPHAN_GRACE_SECS,  # noqa: F401 - public facade re-export
    PACKAGE_DIRS,  # noqa: F401 - public facade re-export
    PACKAGE_FILES,  # noqa: F401 - public facade re-export
    PAGE_OWNED_DIRS,  # noqa: F401 - public facade re-export
    PAGE_OWNED_FILES,  # noqa: F401 - public facade re-export
    SERVED_PATH,  # noqa: F401 - public facade re-export
    VENDORED_FILES,
)
from leaf_interact.service import (
    PageTransaction,
    ancestry,  # noqa: F401 - public facade re-export
    claim_is_active,  # noqa: F401 - public facade re-export
    claim_page,  # noqa: F401 - public facade re-export
    claim_path,  # noqa: F401 - public facade re-export
    claim_records,  # noqa: F401 - public facade re-export
    claim_update_sources,  # noqa: F401 - public facade re-export
    config_home,  # noqa: F401 - public facade re-export
    host_identity,  # noqa: F401 - public facade re-export
    host_key,  # noqa: F401 - public facade re-export
    init_lock_path,  # noqa: F401 - public facade re-export
    lifetime_note,  # noqa: F401 - public facade re-export
    lock_is_held,  # noqa: F401 - public facade re-export
    message_identity,
    owned_pages,  # noqa: F401 - public facade re-export
    page_access,  # noqa: F401 - public facade re-export
    page_claim,  # noqa: F401 - public facade re-export
    page_url,  # noqa: F401 - public facade re-export
    restore_page_claim,  # noqa: F401 - CLI facade dependency and public re-export
    running_server,  # noqa: F401 - public facade re-export
    state_home,  # noqa: F401 - public facade re-export
    stop_when_service_ends,  # noqa: F401 - public facade re-export
    take_page_claim,  # noqa: F401 - CLI facade dependency and public re-export
    take_waiter_lease,  # noqa: F401 - public facade re-export
    transition_lock,
    unacknowledged,  # noqa: F401 - public facade re-export
    wait_is_live,  # noqa: F401 - public facade re-export
    waiter_lease_path,  # noqa: F401 - public facade re-export
)
from leaf_interact.validation import (
    DECLARED_WORDS,  # noqa: F401 - public facade re-export
    action_contract_error,  # noqa: F401 - public facade re-export
    addressable_instance_errors,
    ask_region_errors,
    check_markup,
    declared_action_error,  # noqa: F401 - public facade re-export
    declared_event_error,  # noqa: F401 - public facade re-export
    declared_word_errors,
    detail_error,  # noqa: F401 - public facade re-export
    event_record_error,  # noqa: F401 - public facade re-export
    fragment_errors,  # noqa: F401 - public facade re-export
    fragment_style_errors,  # noqa: F401 - public facade re-export
    held_comment_error,  # noqa: F401 - public facade re-export
    id_errors,
    incoming_registry,  # noqa: F401 - public facade re-export
    language_class_errors,
    line_ref_errors,
    media_errors,
    page_boundary_errors,
    read_text_arg,
    reference_errors,
    report_contract_error,
    report_errors,
    reserved_ids_error,  # noqa: F401 - public facade re-export
    reserved_marker_errors,  # noqa: F401 - public facade re-export
    restatement_errors,
    structure_errors,
    suggestion_errors,
    thread_markup_contract_errors,  # noqa: F401 - public facade re-export
    thread_state,  # noqa: F401 - public facade re-export
    thread_universe,  # noqa: F401 - public facade re-export
    unpointable_blocks,
    validate_registry_examples,  # noqa: F401 - public facade re-export
    version_ids,  # noqa: F401 - public facade re-export
    vocabulary_gaps,  # noqa: F401 - public facade re-export
    widget_errors,
)
from leaf_interact.validation import (
    at as _validation_at,
)
from leaf_interact.work import (
    widget_work_seat,  # noqa: F401 - public facade re-export
    widget_work_without_seats,
    work_subject,  # noqa: F401 - public facade re-export
)

# This program's one serialization primitive is POSIX flock. A platform without
# fcntl is explicitly unsupported: a no-op fallback used to look harmless while it
# allowed concurrent retries of one attempt to append more than one event.
try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


def cmd_media(page_dir: Path, files: list) -> list:
    """Copy images into the page's media directory, named by the hash of their
    bytes; returns (source, served path) per file, in the order given.

    Content-addressing is doing two jobs. It keeps the directory's promise —
    a name can only ever mean one set of bytes, so a version the user
    approved shows them the same picture forever, which is the same guarantee
    vendoring gives the layer. And it de-duplicates for free: a version that
    re-shows last version's screenshot re-uses the file rather than a second
    copy of it, which is what makes the version history cheap to keep."""
    out = []
    (page_dir / MEDIA_DIR).mkdir(exist_ok=True)
    for src in files:
        if src.suffix.lower() not in MEDIA_TYPES:
            sys.exit(
                f"{src}: not an image leaf serves — {', '.join(sorted(MEDIA_TYPES))}"
            )
        data = src.read_bytes()
        name = hashlib.sha256(data).hexdigest()[:16] + src.suffix.lower()
        (page_dir / MEDIA_DIR / name).write_bytes(data)
        out.append((str(src), f"/{MEDIA_DIR}/{name}"))
    return out


from leaf_interact.hosting import (  # noqa: F401 - public facade re-exports
    DualStackHTTPServer,
    LeafHTTPServer,
    cmd_serve,
    cmd_stop,
    server_at,
    start_server,
)
from leaf_interact.session import (  # noqa: F401 - public facade re-exports
    PageTick,
    Watch,
    cmd_ack,
    cmd_status,
    cmd_wait,
)


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with flocked(transition_lock(page_dir)):
            return function(page_dir, *args, **kwargs)

    return locked


@contract_writer
def cmd_comment(page_dir: Path, quote: str, section: str, text, markup: str) -> None:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the version
    they are looking at — the newest published one, since a version no `note` has
    released is a passage nobody can be pointed at — and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there."""
    # Reading a body may wait on stdin; do that before taking the page lease.
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        version = latest_published(page_dir, events)
        anchor = None
        if quote or section:
            html = version_path(page_dir, version).read_text(encoding="utf-8")
            registry = require_registry(page_dir)
            projection, _, _ = page_projection(html, events, registry, version)
            decided = decisions(projection.actions, registry)
            edited = rewritten_bodies(projection.actions)
            try:
                anchor = capture_anchor(html, registry, quote, section, decided, edited)
            except ValueError as err:
                sys.exit(f"can't anchor in v{version}: {err}")
        if markup:
            check_markup(page_dir, "comment", markup, events)
        event = {
            "kind": "comment",
            "author": "claude",
            **message_identity(),
            "version": version,
            "text": body,
        }
        if anchor:
            event["anchor"] = anchor
        if markup:
            event["markup"] = markup
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_reply(page_dir: Path, to: str, text, markup: str) -> dict:
    """Post one complete threaded reply."""
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        known = {e["id"] for e in events if e["kind"] in {"comment", "reply"}}
        if to not in known:
            sys.exit(f"unknown comment id {to!r}; known: {sorted(known)}")
        if markup:
            check_markup(page_dir, "reply", markup, events)
        event = {
            "kind": "reply",
            "author": "claude",
            **message_identity(),
            "parent": to,
            "text": body,
        }
        if markup:
            event["markup"] = markup
        return append_event(page, event)


@contract_writer
def cmd_resolve(page_dir: Path, to: str) -> None:
    """Close a thread, as the reader's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        events = page.events
        known = {e["id"] for e in events if e["kind"] in {"comment", "reply"}}
        if to not in known:
            sys.exit(f"unknown comment id {to!r}; known: {sorted(known)}")
        event = {
            "kind": "resolve",
            "author": "claude",
            **message_identity(),
            "parent": to,
        }
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_report(page_dir: Path, widget: str, verb: str, fields: tuple) -> None:
    """A worker's provisional news: a declared state change folded onto a page
    widget, validated at this door the way the POST door validates an action,
    stamped with the posting session's voice, and made against the newest
    published version — the page the reader is looking at. The runtime paints it
    live; it stands until a version absorbs or overrules it by id (see
    `version publish`), and the page's watcher wakes to fold it in. Field values
    are strings — the declared detail schemas for reports speak in attribute
    values, which is all a report may move."""
    detail = {}
    for field in fields:
        name, eq, value = field.partition("=")
        if not eq or not name:
            sys.exit(f"detail fields are name=value, got {field!r}")
        detail[name] = value
    with PageTransaction(page_dir) as page:
        events = page.events
        version = latest_published(page_dir, events)
        registry = require_registry(page_dir)
        event = {
            "kind": "report",
            "author": "claude",
            **message_identity(),
            "widget": widget,
            "action": verb,
            "detail": detail,
            "version": version,
        }
        if error := report_contract_error(
            event, parse_version(page_dir, version).by_id, registry
        ):
            sys.exit(error)
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_publish(
    page_dir: Path, version: int, text, completes: tuple[str, ...] = ()
) -> None:
    name = version_name(version)
    path = version_path(page_dir, version)
    if not path.is_file():
        sys.exit(
            f"no v{version}.html in {page_dir / 'versions'}; write the version file first"
        )
    body = read_text_arg(text)
    # Validation, projection, and append share the contract transition held by
    # the decorator and this page transaction. A report therefore lands either
    # before the note and may be answered by it, or after it on the new version.
    with PageTransaction(page_dir) as page:
        events = page.events
        if (
            cmd_check(
                page_dir,
                version,
                transition_held=True,
                events_override=events,
            )
            != 0
        ):
            sys.exit(
                f"refusing to publish {name}: leaf version check failed (issues above)"
            )
        html = path.read_text(encoding="utf-8")
        registry = load_registry(page_dir)
        projection, parser, spk = page_projection(html, events, registry, version)
        retracts = sorted(parser.restated)
        byid = parser.by_id
        if len(set(completes)) != len(completes):
            sys.exit("--completes names each widget at most once")
        completed = set(completes)
        widget_work = {
            claim["subject"]["id"]: claim
            for claim in standing_work_claims(
                page.status, events, include_resolved=True
            )
            if claim["subject"]["kind"] == "widget"
        }
        unearned = sorted(completed - widget_work.keys())
        if unearned:
            sys.exit(
                "no active widget work claim for "
                + ", ".join(repr(widget) for widget in unearned)
            )
        not_later = sorted(
            widget
            for widget in completed
            if version <= work_claim_version(widget_work[widget], events)
        )
        if not_later:
            sys.exit(
                f"v{version} is not later than the active widget work claim for "
                + ", ".join(repr(widget) for widget in not_later)
            )
        unseated = widget_work_without_seats(
            html, parser, projection, events, page.status, registry, completed
        )
        if unseated:
            widgets = ", ".join(repr(widget) for widget in unseated)
            sys.exit(
                f"refusing to publish {name}: it would remove the local seat "
                f"for active work on {widgets}; pass --completes for each widget "
                "this version completes"
            )
        settled_reports = []
        for (_widget, unit, _facet), reports in projection.reports.items():
            last, spec = reports[-1]
            if unit in parser.overruled or markup_facet(
                unit, spec, byid, spk, registry
            ) == folded_facet(last, spec):
                settled_reports.extend(report["id"] for report, _ in reports)
        event = {
            "kind": "note",
            "author": "claude",
            **message_identity(),
            "version": version,
            "text": body,
        }
        if retracts:
            event["restated"] = retracts
        settlements = [
            *(
                {"kind": "report", "id": identity}
                for identity in sorted(settled_reports)
            ),
            *({"kind": "work", "id": identity} for identity in sorted(completed)),
        ]
        if settlements:
            event["settles"] = settlements
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


def cmd_events(page_dir: Path, after: int) -> None:
    for event in read_events(page_dir):
        if event["seq"] > after:
            print(jsonl_line(event))


# A quote as a transcript names it. The anchor stores the passage whole, because that
# is the extent the page marks; a transcript is prose someone pastes into an MR, where
# a paragraph of quoted page inside every thread head buries the exchange it is there
# to carry. Both ends rather than the opening alone: a passage is identified by where
# it starts and where it stops, and an elision that keeps only the head reads as a
# short quote rather than as a long one shown briefly.
QUOTE_SHOWN = 240


def shown(quote: str) -> str:
    if len(quote) <= QUOTE_SHOWN:
        return quote
    half = QUOTE_SHOWN // 2
    return f"{quote[:half].rstrip()} … {quote[-half:].lstrip()}"


def cmd_transcript(page_dir: Path) -> None:
    """The page's exchange as Markdown, for reuse in a PR description."""
    events = read_events(page_dir)
    published = published_versions(page_dir, events)
    registry = load_registry(page_dir) or {}
    title = ""
    if published:
        title = parse_version(page_dir, published[-1]).title.strip()
    print(f"## Leaf: {title or page_dir.name}")

    notes = [e for e in events if e["kind"] == "note"]
    if notes:
        print("\n### Versions\n")
        for e in notes:
            print(f"- v{e['version']}: {e['text']}")

    # The user's direct edits are outcomes of the exchange; without them the transcript
    # understates it whenever a changelog note doesn't restate them. So
    # is a version taking one back, which is the same understatement the other
    # way round — an edit shown as final that a later version overruled.
    # Widget-agnostic rendering: verb + detail pairs, against the version edited.
    withdrawn = taken_back(events)
    edits = [
        e
        for e in events
        if e["kind"] in {"action", "report"}
        or (e["kind"] == "note" and e.get("restated"))
    ]
    if edits:
        print("\n### Edits\n")
        for e in edits:
            if e["kind"] == "note":
                for wid in e["restated"]:
                    print(
                        f"- `{wid}`: rewritten by v{e['version']}, retracting what was decided on it"
                    )
                continue
            detail = " ".join(f"{k}={v}" for k, v in e["detail"].items())
            verb = f"{e['action']} {detail}".strip()  # a bare reject carries no detail
            if e["kind"] == "report":
                # A worker's provisional news is an outcome too, under its own name.
                print(
                    f"- `{e['widget']}`: {e.get('agent', 'a worker')} reported "
                    f"{verb} (on v{e['version']})"
                )
            else:
                # An edit the reader took back is an outcome too, and the same
                # understatement the other way round: shown as it stands it reads
                # as final, and left out it reads as never made.
                took = " — taken back" if e["id"] in withdrawn else ""
                print(f"- `{e['widget']}`: {verb} (on v{e['version']}){took}")

    # Against the newest published version — the page as it now stands, which is
    # what a transcript is an account of. A page with nothing published yet has no
    # reading to give, and no action can have been made against one either.
    latest = (
        version_path(page_dir, published[-1]).read_text(encoding="utf-8")
        if published
        else ""
    )
    projection = parser = None
    spk = {}
    if published:
        projection, parser, spk = page_projection(
            latest, events, registry, published[-1]
        )
    threads = build_threads(events, spk)
    if threads:
        print("\n### Threads\n")
    for t in threads.values():
        anchor = t["root"].get("anchor") or {}
        if anchor.get("quote"):
            head = f"> “{shown(anchor['quote'])}”"
        elif anchor.get("section"):
            head = f"> § {anchor['section']}"
            if anchor.get("part"):
                head += f" · {anchor['part']}"
        else:
            head = "> (page-level)"
        if t["root"].get("about") == "layer":
            head += "  — about the layer"
        closed = t["resolved"]
        if closed and closed["author"] == "claude":
            # Named where the reader was not the one who closed it. A transcript is
            # read away from the page, so the panel's own line saying so is not in it.
            head += "  — resolved by " + closed.get("agent", "Agent")
        elif closed:
            head += "  — resolved"
        print(head)
        for m in t["msgs"]:
            who = m.get("agent", "Agent") if m["author"] == "claude" else "User"
            body = m["text"] + (f"\n{m['markup']}" if m.get("markup") else "")
            print(f"- **{who}**: " + body.replace("\n", "\n  "))
        print()
    for e in events:
        if e["kind"] == "done":
            print(f"Approved at {e['ts']}.")
            break

    # To stderr — stdout is the artifact. A transcript is a page's closing act,
    # and the record debt it reports here is about to stop being fixable.
    if projection and registry:
        for line in record_lag(projection, parser.by_id, spk, registry):
            print(f"record behind the log — {line}", file=sys.stderr)


# ---------- hook: the loop, enforced rather than remembered ----------
from leaf_interact.hooks import (  # noqa: F401 - public facade re-exports
    cmd_hook,
    unanswered_asks,
    unattended_pages,
)
from leaf_interact.page import (  # noqa: F401 - public facade re-exports
    CATALOG_FACTS,
    CATALOG_INTERNAL_FACTS,
    CATALOG_PREAMBLE,
    _write_page_state,
    cmd_catalog,
    cmd_guidance,
    cmd_page_state,
    page_guidance,
    standing_entry,
)


def cmd_check(
    page_dir: Path,
    version,
    render: bool = False,
    transition_held: bool = False,
    events_override: list | None = None,
) -> int:
    if not transition_held:
        with flocked(transition_lock(page_dir)):
            return cmd_check(
                page_dir,
                version,
                render,
                transition_held=True,
                events_override=events_override,
            )
    versions = list_versions(page_dir)
    if not versions:
        sys.exit(
            f"no versions in {page_dir / 'versions'}; write versions/v1.html first"
        )
    selected = version if version is not None else versions[-1]
    if selected not in versions:
        sys.exit(f"no v{version}.html in {page_dir / 'versions'}")
    name = version_name(selected)
    html = version_path(page_dir, selected).read_text(encoding="utf-8")

    errors = []

    for missing in [f for f in VENDORED_FILES if not (page_dir / f).exists()]:
        errors.append(
            f"{missing} missing from the page directory; run `leaf page init` "
            "to vendor the layer"
        )

    parser = parse_structure(html)
    errors.extend(structure_errors(parser))
    errors.extend(page_boundary_errors(parser))

    scripts = parser.external_scripts
    if len(scripts) != 1:
        errors.append(
            f"expected exactly one external <script src> tag, found {len(scripts)}"
            + (f": {[s['attrs']['src'] for s in scripts]}" if scripts else "")
        )
    elif scripts[0]["attrs"] != {"src": "/leaf.js", "type": "module"}:
        attrs = scripts[0]["attrs"]
        errors.append(
            'the only external script must be exactly <script type="module" '
            f'src="/leaf.js">, found attributes {attrs}'
        )
    elif scripts[0]["parent"] != "head" or not scripts[0]["early_head"]:
        errors.append(
            "the /leaf.js module must be in <head> before <body> can paint; "
            "its <head> must be the document's direct, initial head"
        )
    stylesheets = parser.stylesheets
    if len(stylesheets) != 1 or stylesheets[0]["attrs"] != {
        "rel": "stylesheet",
        "href": "/theme.css",
    }:
        errors.append(
            "the page must link exactly one stylesheet, always-applicable and exactly "
            '<link rel="stylesheet" href="/theme.css">, found '
            f"{[asset['attrs'] for asset in stylesheets]}"
        )
    elif stylesheets[0]["parent"] != "head" or not stylesheets[0]["early_head"]:
        errors.append(
            "the /theme.css stylesheet must be in <head> before <body> can paint; "
            "its <head> must be the document's direct, initial head"
        )
    declared_csp = [
        m["content"]
        for m in parser.http_equivs
        if m["equiv"].lower() == "content-security-policy"
    ]
    if declared_csp != [PAGE_CSP]:
        errors.append(
            "the page must declare the layer's one CSP, "
            f'<meta http-equiv="Content-Security-Policy" content="{PAGE_CSP}">'
            + (f" — found {declared_csp}" if declared_csp else "")
        )

    for meta in parser.lf_metas:
        where = f'<meta name="{meta["name"]}"> (line {meta["line"]})'
        if meta["name"] not in LF_META:
            errors.append(f"{where}: unknown lf- meta — known: {sorted(LF_META)}")
            continue
        allowed = LF_META[meta["name"]]
        if allowed is not None and meta["content"] not in allowed:
            errors.append(
                f"{where}: content must be one of {sorted(allowed)}, found {meta['content']!r}"
            )

    errors.extend(id_errors(parser))

    events = read_events(page_dir) if events_override is None else events_override
    registry = load_registry(page_dir)
    if registry is not None:
        errors.extend(widget_errors(parser.lf_elements, registry))
        errors.extend(addressable_instance_errors(parser.lf_elements, registry))
        errors.extend(ask_region_errors(parser.lf_elements, registry))
        errors.extend(reference_errors(parser.lf_elements, registry, parser.ids))
        errors.extend(language_class_errors(parser.language_blocks, registry))
        errors.extend(declared_word_errors(parser.lf_elements, registry))
        errors.extend(line_ref_errors(parser.lf_elements, registry))
        # A family lint reads its own slots off the registry, so it stands with
        # the checks that need one — a page missing registry.json has already
        # been told to vendor the layer, and there is nothing to lint against.
        errors.extend(
            suggestion_errors(
                parser.lf_elements,
                registry,
                {e["id"] for e in events if e["kind"] == "comment"},
            )
        )
        for tag, entry in registry.items():
            if not tag.startswith("lf-"):
                continue
            if (
                entry["x-upgrade"]
                and not (page_dir / "widgets" / f"{tag}.js").is_file()
            ):
                errors.append(
                    f"registry marks <{tag}> as upgraded but widgets/{tag}.js "
                    f"isn't vendored; run `leaf page init`"
                )

    # "Previous" is the last *published* version before this one — the page the
    # user was actually looking at, which is what `leaf comment` anchors
    # against and what the browser diffs against. The file before it on disk may be an
    # abandoned draft no note ever released: ids nobody saw, words nobody could
    # have decided on. The first published version has no predecessor, so it
    # stands against an empty one: nothing of its can have been dropped and
    # nothing decided, which is exactly what makes a `restated` on it an error
    # like any other unearned one.
    noted = {e["version"] for e in events if e["kind"] == "note"}
    earlier = [
        candidate
        for candidate in versions
        if candidate < selected and candidate in noted
    ]
    prev, prev_num, was = parse_structure(""), 0, {}
    if earlier:
        prev_num = earlier[-1]
        prev_name = version_name(prev_num)
        prev_html = version_path(page_dir, prev_num).read_text(encoding="utf-8")
        prev = parse_structure(prev_html)
        was = spoken(prev_html, registry or {})
        # An id may retire when the log has settled what holds it; everything
        # else must survive, or the anchors on it break.
        gone = prev.ids - parser.ids
        # With the family lints above, and for their reason: which ids a settled
        # widget licenses is the holder/slot declaration's answer, so with no
        # registry there is nothing to ask it — and every id a decision legitimately
        # retired would read as dropped, stacked on the "vendor the layer" error the
        # page already has.
        if registry is not None:
            previous_projection = state_projection(
                events, prev.by_id, was, registry, prev_num
            )
            dropped = sorted(
                gone
                - retirable_ids(
                    retirement_holders(prev, registry),
                    events,
                    gone,
                    decisions(previous_projection.actions, registry),
                    was,
                )
            )
            if dropped:
                errors.append(
                    f"ids present in {prev_name} but dropped in {name} "
                    f"(anchors on them will break): {dropped}"
                )
    # And the decisions recorded on the ids that stayed — the reviewer channel's
    # gate, then its mirror for the agent channel's standing reports.
    now = spoken(html, registry or {})
    floors = retractions(events, prev_num)
    projection = state_projection(
        events, parser.by_id, now, registry or {}, prev_num, floors
    )
    errors.extend(
        restatement_errors(
            parser,
            prev,
            was,
            now,
            prev_num,
            registry or {},
            projection,
            floors,
        )
    )
    errors.extend(report_errors(parser, prev, was, now, registry or {}, projection))

    # Thread markup is frozen in the log and rendered into the panel; a page id
    # colliding with one would steal its action replays.
    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(f"ids already taken by widget markup in a reply: {taken}")

    errors.extend(media_errors(parser, page_dir))

    theme_css = (
        (page_dir / "theme.css").read_text(encoding="utf-8")
        if (page_dir / "theme.css").exists()
        else ""
    )
    errors.extend(css_syntax_errors(parser.css, "page <style>"))
    for number, style in enumerate(parser.inline_styles, 1):
        errors.extend(css_syntax_errors(style, f"inline style #{number}", block=True))
    errors.extend(css_syntax_errors(theme_css, "theme.css"))
    errors.extend(inline_presentation_override_errors(parser))
    column = _column_width(parser.css, theme_css)
    errors.extend(_overwide_elements(parser, column, root_tokens(theme_css)))

    if errors:
        print(f"✗ {name}: {len(errors)} issue(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(
        f"✓ {name}: parses, widgets validate, one module script + theme link, "
        f"ids and decisions carried over, nothing overflows the {column}px column"
    )
    # Advice, never a gate: silence is blessed and replay resolves it, but a
    # log-less reader (a printout, a transcript's audience) sees only the markup,
    # so say where it lags the log. Loudest at the end of the exchange — the final
    # version is the page that must read right without the log.
    current_projection = state_projection(
        events, parser.by_id, now, registry or {}, selected
    )
    for line in record_lag(current_projection, parser.by_id, now, registry or {}):
        print(f"  · record behind the log — {line}")
    # Same register, different debt: a block the id rule missed, named while the
    # author can still cheaply mint one.
    for line in unpointable_blocks(parser):
        print(f"  · {line}")
    # Render only what passed the static half: an unparsable page would drown
    # the browser's report in consequences of what the lint already named.
    return render_check(page_dir, selected, transition_held=True) if render else 0


at = _validation_at
_cli_surface = create_cli(globals())
globals().update(_cli_surface)
cli = _cli_surface["cli"]


if __name__ == "__main__":
    # `leaf` is the name the skill hands an agent and the name on PATH, so it is
    # the name the usage lines have to say back, whichever way the script was reached.
    cli(prog_name="leaf")
