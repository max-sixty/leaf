#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8", "jsonschema>=4", "tinycss2>=1.4"]
# ///
"""Serve and mediate an interactive leaf page.

A `uv` script: the PEP 723 header above declares the dependencies, and
`interact.py.lock` beside it pins them, so every install runs the same versions;
editing the header re-resolves the lock on the next run. `uv` is the one
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
    icon.svg             the mark the tab wears, whose lf-tone element the runtime
                         paints in whatever colour the banner's dot is wearing — so a
                         reader with six leaves open sees which one wants them
                         without opening any
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
                         its last claimant, release time, and process evidence.
                         Keeping provenance outside the disposable page lets
                         ownership discovery survive a page moving between sessions
status.json is a claim, and a claim never expires on its own: an agent that
stopped watching renders exactly like one that is watching and has nothing to
say, so a comment can sit unread with the page still reading "Claude is
working". The directory therefore also carries what it can prove — a lease only
a live `leaf wait` can hold, the acknowledgement cursor, and the owning session's
pid — and `/api/state` ships those beside the claim, so the banner can say when
the claim has outlived its evidence. When a wait prints for a
non-working page, it marks the status it writes "handoff", which dates that
claim: after acknowledgement the agent writes its own `leaf status`, so a
handoff mark that survives means a dropped pickup rather than a long turn, and
the banner gives it a much shorter rope. Wait output that lands while the agent
is already working leaves the existing claim untouched; there is no pickup gap
to date.

Where nothing answers for the claim at all, the banner drops the claim rather
than repeating it. A claimant pid that has exited settles the question outright;
a page nothing ever claimed has only the claim's own age to go on, so it falls
to the same grace period. Either way the page is unheld, and the banner says
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
live pid are what make it active. Absent the host identity the environment
carries, nothing is claimed and the hooks stand down. What the environment
cannot carry is the session's own lifetime, and `session_pid` says where each
host's lifetime comes from. Unacknowledged events are the one thing `leaf status
<page> idle` can't close over: idling is how a leaf ends, and one can't end on
comments nobody read.

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
is the standing serve: a page kept up across sessions, for a command hub or a
dashboard someone leaves open for weeks. `server start --standing` makes the
same statement from inside a host: the launch declines the claim, for a page
meant to outlive the session that starts it. No daemon is involved, and a server
that dies under a `leaf wait` watching an enabled page is revived with the
lifetime and exact URL in service.json. `leaf server stop` is a standing
server's one reaper, and that is the whole of what "standing" means. A session
that picks the page up later owes it a watcher while the session lives, exactly
as it would any page. Its claim comes and goes without changing the standing
service or the page's status.

`page init` vendors the runtime, theme, registry, widgets, and vendor assets into the
page directory, overlaying by precedence: leaf's integrated layer (the runtime,
the theme's own rules, the suggestion family and the $ keys), then its bundled
widgets (the content families, an overlay like any other so they reach a page
through the same door a project's widgets do), then the user layer
(~/.config/leaf/), then the project layer
(./.leaf/). Theme stylesheets concatenate in that order, so a layer
can override one token or rule without copying the defaults. Registry entries
merge by top-level name, with a later layer replacing one complete entry rather
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
                while interactive reply markup stays in the panel.
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
                facet, fold unit, and the record form its state takes in markup. Every
                applyAction is absolute, so the user's standing state is a
                fold — the last surviving action per owner, unit, and facet — and one declaration
                drives the POST and re-vendor contract gates, check's state gate,
                the record-lag report, the runtime's pending mark, and the diff's
                state half (see $state in the registry).
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
                being true and false); `all` names the verb one press answers
                every one
                with. What counts as answered needs no new bookkeeping: a verb
                that records as an attribute answers on the record the replayed
                page carries, and every other verb answers through its own
                surviving fold entry, whatever else it records — so the banner's
                count, the key that steps through open asks, and the `?` overlay
                all read one list (see $awaits).
    x-example   one authored example, printed by `page catalog`

Event kinds: comment (optional anchor {section, quote, and the neighbouring
text as prefix/suffix where there is any, which is what tells two identical
passages apart), reply (parent=id),
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
the anchor from the selection; `leaf comment` writes the same anchor from a
quote, reading the version the way the anchor pass reads the DOM (see
"passages" below). Everything downstream already turns on `author`: `leaf wait`
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
    customize  theme widget
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
The invariants live in render_version, which tests/test_render.py drives over
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

import base64
import contextlib
import ctypes
import errno
import functools
import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import zlib
from datetime import datetime
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple
from urllib.parse import parse_qs, urljoin, urlsplit

import click
import tinycss2
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

# A session-managed server gives a replacement session one short poll window to
# claim the page before it closes. The external claim record is the ownership
# source; a standing lifetime ignores it and remains enabled until `server stop`.
ORPHAN_GRACE_SECS = 1
# The kinds a reader can take back. A message is not among them: a comment is
# speech, and the agent may already have read it — what a reader regrets there
# they say, rather than unsay. Nor is an undo itself, which would be a redo.
UNDOABLE_KINDS = {"resolve", "unresolve", "action"}
ANSWER_ASK_INSTRUCTION = (
    "Answer each with `leaf reply <page> --to <id> --text ...`, or close one the "
    "work has since answered with `leaf resolve <page> --to <id>`."
)
ACK_BATCH_INSTRUCTION = (
    "If wait output is truncated, acknowledge nothing and rerun with enough output "
    "capacity for the whole batch. After the complete batch reaches its next durable "
    "consumer, the wait owner runs `leaf ack <page> <highest-seq>` for the page the "
    "batch's first line names."
)
HTML_NAME = r"[a-z][a-z0-9-]*"
WIDGET_NAME = r"lf-[a-z0-9]+(?:-[a-z0-9]+)*"
# The record forms one vocabulary of declared state draws on ($state in the
# registry): how a unit's state reads in markup, each dispatched on by the gate,
# the runtime, and the diff without any of them knowing a widget by name.
_RECORD_ATTRIBUTE = {
    "type": "object",
    "properties": {
        "kind": {"const": "attribute"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "attr", "value"],
    "additionalProperties": False,
}
_RECORD_POSITION = {
    "type": "object",
    "properties": {
        "kind": {"const": "position"},
        "within": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
        "value": {"type": "string", "minLength": 1},
        # Where the unit sits among its siblings. Comparison stays at the
        # container's granularity (see $state) — but a reader that has to *state*
        # a position needs both halves, and taking a move back is one: the runtime
        # reads the authored placement off the page before replay touches it, and
        # a record naming only the column would put a card back on the right list
        # in the wrong place.
        "order": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "within", "value", "order"],
    "additionalProperties": False,
}
_RECORD_BODY = {
    "type": "object",
    "properties": {
        "kind": {"const": "body"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "value"],
    "additionalProperties": False,
}
_RECORD_VALUE = {
    "type": "object",
    "properties": {
        "kind": {"const": "value"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "attr", "value"],
    "additionalProperties": False,
}


def _verbs_schema(records: list, required: list) -> dict:
    """The shape x-state and x-report share: verbs to
    {detail, facet, unit, record}, differing only in which record forms a
    channel admits and whether one is required at all."""
    return {
        "type": "object",
        "minProperties": 1,
        "propertyNames": {"pattern": f"^{HTML_NAME}$"},
        "additionalProperties": {
            "type": "object",
            "properties": {
                "detail": {"type": "object"},
                "facet": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                "unit": {"type": "string", "minLength": 1},
                "record": {"oneOf": records},
            },
            "required": required,
            "additionalProperties": False,
        },
    }


STATE_SCHEMA = _verbs_schema(
    [_RECORD_ATTRIBUTE, _RECORD_POSITION, _RECORD_BODY, _RECORD_VALUE],
    ["detail", "facet", "unit"],
)
# A report moves declared state only, never body words — no body record, so the
# passage reading never has to model one — and the record itself is required:
# the gate compares record forms, and a recordless report would be a claim
# nothing could check a version against.
REPORT_SCHEMA = _verbs_schema(
    [_RECORD_ATTRIBUTE, _RECORD_POSITION, _RECORD_VALUE],
    ["detail", "facet", "unit", "record"],
)
# A `when` predicate selects instances by attribute values (or by a flag's being
# present or absent). One condition shape serves every registry consumer because
# they ask the same question of the same attributes.
ASK_CONDITION = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "array",
        "items": {"type": ["string", "boolean"]},
        "minItems": 1,
    },
}
AWAITS_SCHEMA = {
    "type": "object",
    "properties": {
        "when": ASK_CONDITION,
        "all": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "until": {
            "type": "object",
            "properties": {
                "verb": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                "when": ASK_CONDITION,
            },
            "required": ["verb", "when"],
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
# A list of the widget's own attribute names. One shape for the three keys that hold
# one, since the shape is a consequence of what they name rather than three decisions.
_ATTRIBUTE_LIST = {
    "type": "array",
    "items": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    "minItems": 1,
}
_ATTRIBUTE_NAME = {"type": "string", "pattern": f"^{HTML_NAME}$"}
EXTENSION_SCHEMA = {
    "type": "object",
    "properties": {
        "x-awaits": AWAITS_SCHEMA,
        "x-conversation": {
            "type": "object",
            "properties": {"when": ASK_CONDITION},
            "required": ["when"],
            "additionalProperties": False,
        },
        "x-content": {"enum": ["prose", "items", "data", "none"]},
        "x-example": {"type": "string"},
        "x-exhibit": {"type": "boolean"},
        "x-inline": {"type": "boolean"},
        "x-language": _ATTRIBUTE_NAME,
        # Attributes holding 1-based line references into the nearest data body —
        # the element's own <pre>, or its holder's (lf-note's `at` names a line of
        # its lf-code). `version check` refuses one outside the body (line_ref_errors).
        "x-lines": _ATTRIBUTE_LIST,
        # Attributes the theme renders as paint alone — a status marker's tint, an
        # event's kind, the ring on the recommended option. The runtime speaks each as
        # a clipped word (renderQuiet), the value or, where a flag carries no value,
        # the attribute's own name.
        "x-paints": _ATTRIBUTE_LIST,
        "x-parent": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
            "minItems": 1,
        },
        "x-refers": _ATTRIBUTE_LIST,
        "x-report": REPORT_SCHEMA,
        "x-retired-when": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-says": {
            "type": "object",
            "propertyNames": {"pattern": f"^{HTML_NAME}$"},
            "additionalProperties": {"enum": ["before", "after"]},
        },
        "x-shadow": {"type": "boolean"},
        "x-state": STATE_SCHEMA,
        "x-tone": _ATTRIBUTE_NAME,
        "x-upgrade": {"type": "boolean"},
        "x-verbatim": {"type": "boolean"},
        "x-visual": {"type": "boolean"},
        "x-wide": {"enum": ["box", "drawing"]},
        "x-withdrawn-as": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-word": {"enum": ["module"]},
    },
    "required": ["x-content", "x-upgrade"],
    "dependentRequired": {"x-retired-when": ["x-parent"]},
    "additionalProperties": False,
}
# The keys whose value names attributes of the widget's own schema, in whichever shape
# each carries the names: a list, a mapping keyed by them, or one name. One rule for all
# of them, because the failure is one — the attribute is absent, so the pass reading the
# key finds nothing and does nothing, and the widget is simply missing from it with no
# error anywhere (validate_registry holds every key here to the entry's `properties`).
# The verb keys of the same shape (x-retired-when, x-withdrawn-as) are not in it: they
# name an outcome rather than an attribute, and sharing a spelling is no reason to share
# a check. x-awaits names attributes too and keeps its own loop, having more to say about
# each than that it exists.
ATTRIBUTE_KEYS = ("x-language", "x-lines", "x-paints", "x-refers", "x-says", "x-tone")

ASSETS = Path(__file__).resolve().parent.parent / "assets"
BUNDLED = Path(__file__).resolve().parent.parent / "bundled"
VENDORED_FILES = ("leaf.js", "theme.css", "registry.json", "icon.svg")
VENDORED_DIRS = ("widgets", "vendor")
LAYER_PLACEHOLDER = b'"__LEAF_LAYER_GENERATION__"'
# Images the page shows, named by the hash of their bytes (`page media`). Not vendored
# — they are the page's content, not the layer's — but served like it, and the
# naming is what keeps the directory's promise: same name, same bytes, so a
# version the user approved cannot show them something else later.
MEDIA_DIR = "media"
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
NO_KEY = "open the link leaf printed; it carries the key"
# One name, because there is one key (`host_key`). Cookies are scoped by host and
# blind to the port, so every page this machine serves shares a jar — on 127.0.0.1,
# with every other server the user has running, which is what the prefix is for.
KEY_COOKIE = "lf_key"
PAGE_STATE_FILES = (
    "comments.jsonl",
    "status.json",
    "waiter.lock",
    "cursor.json",
    "service.json",
    "server.lock",
)
PAGE_OWNED_FILES = (*VENDORED_FILES, *PAGE_STATE_FILES)
PAGE_OWNED_DIRS = ("versions", *VENDORED_DIRS, MEDIA_DIR)
# What the server exposes from a page directory: exactly what init vendors, plus
# the media and the versions — built from the vendoring constants, so growing
# them grows this. The dir patterns are keyed by the directories themselves:
# vendoring a new dir without saying what it may serve fails here, at import.
_DIR_FILES = {
    "widgets": r"[a-z0-9-]+\.js",
    "vendor": r"[A-Za-z0-9._-]+",
    MEDIA_DIR: r"[a-f0-9]{16}(?:" + "|".join(re.escape(e) for e in MEDIA_TYPES) + ")",
}
SERVED_PATH = re.compile(
    "/(?:"
    + "|".join(
        [re.escape(f) for f in VENDORED_FILES]
        + [f"{d}/{_DIR_FILES[d]}" for d in (*VENDORED_DIRS, MEDIA_DIR)]
        + [r"versions/v[1-9][0-9]*\.html"]
    )
    + ")"
)
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".html": "text/html",
    **MEDIA_TYPES,
}
BINARY_TYPES = frozenset(MEDIA_TYPES.values()) - {"image/svg+xml"}

# This program's one serialization primitive is POSIX flock. A platform without
# fcntl is explicitly unsupported: a no-op fallback used to look harmless while it
# allowed concurrent retries of one attempt to append more than one event.
try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


def require_cross_process_locking() -> None:
    """Refuse every writer/server path on a host without the log's lock."""
    if fcntl is None:
        raise RuntimeError(
            "leaf requires POSIX cross-process file locking; this platform has no fcntl"
        )


@contextlib.contextmanager
def flocked(path: Path):
    """An exclusive lock held while the block runs — the one serialization
    primitive here. The log serializes appends, cursor and status updates, and
    claim and delivery transitions. Stable purpose locks serialize contract or service
    transitions; a `.lock` beside a registry of JSON files serializes updates
    to them, since the files themselves are replaced by rename and a lock on a
    replaced inode holds nothing."""
    require_cross_process_locking()
    # comments.jsonl is the successful-init marker as well as a lease. A
    # transaction racing page deletion must not recreate it and turn a deleted
    # directory back into an initialized page. Purpose locks are disposable and
    # may be minted on first use.
    mode = "r+b" if path.name == "comments.jsonl" else "a+b"
    with open(path, mode) as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def file_stamp(path: Path):
    """What the filesystem says a file is: which file, when it was last written,
    and how big it is. A page directory holds files that are written once and read
    on every request, so what each one says is worked out once and kept under this
    stamp, and a file rewritten since wears a different one. A path with nothing
    there stamps as None, which keeps nothing and reads every time."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_ino, stat.st_mtime_ns, stat.st_size)


def read_cursor(page_dir: Path) -> int:
    """The seq the agent has acknowledged through (`leaf ack`); 0 before any."""
    return (read_json(page_dir / "cursor.json") or {"seq": 0})["seq"]


def replace_files(files: list) -> None:
    """Stage every (path, bytes, follow_symlink) write before replacing targets."""
    staged = []
    targets = [
        path.resolve() if follow_symlink and path.is_symlink() else path
        for path, _, follow_symlink in files
    ]
    located_targets = [_path_location(target) for target in targets]
    if any(
        left == right
        for index, left in enumerate(located_targets)
        for right in located_targets[index + 1 :]
    ):
        sys.exit("two customization files resolve to the same target")
    try:
        for (path, data, follow_symlink), target in zip(files, targets):
            for _ in range(100):
                tmp = target.with_name(f".{secrets.token_hex(8)}.tmp")
                try:
                    fd = os.open(
                        tmp,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0),
                        0o666,
                    )
                    break
                except FileExistsError:
                    continue
            else:  # pragma: no cover - 64 random bits collided 100 times
                raise FileExistsError(f"could not reserve a temp file beside {target}")
            staged.append((tmp, target))
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            if follow_symlink or not path.is_symlink():
                try:
                    tmp.chmod(target.stat().st_mode & 0o777)
                except FileNotFoundError:
                    pass  # no target to preserve a mode from
        for tmp, target in staged:
            os.replace(tmp, target)
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)


def json_bytes(obj, *, indent=None) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=indent) + "\n").encode()


def write_json(path: Path, obj) -> None:
    # Atomic: the serve process reads these files while the CLI commands write them;
    # a torn cursor or status would make the page report false state. Each writer
    # stages through an exclusively created name so simultaneous writers cannot
    # replace one another's temp file.
    replace_files([(path, json_bytes(obj), False)])


def jsonl_line(event: dict) -> str:
    """One event as one physical line. U+2028, U+2029 and U+0085 are legal raw in
    JSON strings and line breaks to any splitlines()-shaped reader, so they are
    written as escapes — a pasted comment carrying one must not decide where an
    event ends. The log's own reader splits on the "\\n" the writer puts between
    events either way; the escape is for what `wait` and `events` print, which
    stays one event per line for every consumer. json.dumps escapes every other
    line-breaking character on its own."""
    line = json.dumps(event, ensure_ascii=False)
    for ch in "\u2028\u2029\u0085":
        line = line.replace(ch, f"\\u{ord(ch):04x}")
    return line


class AttemptConflict(ValueError):
    """One browser attempt was reused for a different event payload."""


class AttemptExecution:
    """One execution shared by concurrent HTTP requests for the same attempt.

    Success is durable in the event log. The record coordinates requests while a
    handler is executing and is released once that handler finishes, so a concurrent
    retry receives the same outcome and a later one is free to be evaluated again.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.done = threading.Event()
        self.result = None


def _attempt_payload(event: dict) -> dict:
    # Kind is part of the gesture. Only fields the append boundary itself assigns
    # disappear from the equality check.
    return {
        key: value
        for key, value in event.items()
        if key not in {"id", "ts", "author", "seq"}
    }


def _matching_attempt(f, event: dict) -> dict | None:
    attempt = event.get("attempt")
    if not attempt:
        return None
    f.seek(0)
    for raw in f:
        try:
            existing = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if existing.get("attempt") != attempt:
            continue
        if _attempt_payload(existing) != _attempt_payload(event):
            raise AttemptConflict(
                f"attempt {attempt!r} already belongs to another event"
            )
        return existing
    return None


def _append_event_unlocked(f, event: dict) -> dict:
    """Append while the caller holds this log file's exclusive lease."""
    event.setdefault("id", secrets.token_hex(4))
    event.setdefault("ts", now_iso())
    # Attempt identity is checked under the log's append lock. Checking before
    # this point would leave two server threads free to observe absence together
    # and append together. Content and time deliberately play no part: an
    # intentional later identical message has a fresh attempt and is a second
    # event.
    if event.get("attempt") and (existing := _matching_attempt(f, event)):
        return existing
    # A crash can tear the previous append mid-line: SIGKILL under a buffered
    # flush, a full disk. The line discipline is the writer's, so the writer
    # restores it — without this, the next event glues onto the torn fragment
    # and one lost event becomes an unreadable line mid-file.
    f.seek(0, os.SEEK_END)
    if f.tell():
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
    f.write((jsonl_line(event) + "\n").encode())
    # To the platter before the caller is told it landed: an event is a
    # decision, the sender's 200 (or a CLI exit 0) is the claim it is kept,
    # and events are rare enough that a flush per append costs nothing.
    f.flush()
    os.fsync(f.fileno())
    return event


def append_event(page_dir: "Path | PageTransaction", event: dict) -> dict:
    if isinstance(page_dir, PageTransaction):
        return page_dir.append_event(event)
    # The path form is the low-level fixture/instrumentation seam and retains
    # its historic ability to start a log in an already-created directory.
    # Product writers pass PageTransaction, whose entry never mints the page's
    # successful-init marker.
    log = page_dir / "comments.jsonl"
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        return _append_event_unlocked(f, event)


def read_events(page_dir: Path) -> list:
    path = page_dir / "comments.jsonl"
    if not path.exists():
        return []
    events = []
    # The log's grammar is events joined by "\n" — the writer's own separator,
    # not splitlines()'s wider class, which once read a U+2028 inside a comment's
    # text as a break and left half an event leading a line no parse could take.
    # Bytes, decoded per line: a crash can tear mid-character as easily as
    # mid-line (ensure_ascii=False writes multi-byte UTF-8), and one strict
    # read_text of the file would raise on the tear before any line-level
    # tolerance could reach it.
    lines = path.read_bytes().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # The final line is a concurrent append mid-flush, complete on the
            # next read. An earlier one is the tear a crash left, standing alone
            # because append_event repairs the discipline before writing: that
            # event's sender already saw its send fail, the seqs around it hold,
            # and there is nothing anyone could do with a fragment — so it is
            # skipped, not raised over, and the page keeps reading.
            continue
        event["seq"] = i + 1
        events.append(event)
    return events


def taken_back(events: list) -> set:
    """Event ids some later gesture took back (`undoes`).

    An undo names the gesture it withdraws and carries no counter-state, so every
    projection drops those ids. The thread an action answered is open again once
    the answer is withdrawn, and the undo walk steps back past what it has
    already taken."""
    return {e["undoes"] for e in events if e.get("undoes")}


def undo_error(event: dict, events: list) -> str | None:
    """Why this undo may not take back the event it names, or None.

    Checked once here, at the door the browser writes through, so nothing
    downstream asks a second time whether an `undoes` points at something real.
    Two tabs racing to take back the same event are the one case this refuses
    that nothing is wrong with: the second is a no-op, and refusing it costs a
    toast where accepting it would leave two withdrawals of one gesture in a log
    whose every other line is something the reader did."""
    target = next((e for e in events if e["id"] == event["undoes"]), None)
    if target is None:
        return f"unknown undoes {event['undoes']!r}"
    if target["author"] != "user":
        return f"{target['kind']} {target['id']} is not the reader's own gesture"
    if target["kind"] not in UNDOABLE_KINDS:
        return (
            f"{target['kind']} events cannot be taken back (the kinds that can "
            f"are {', '.join(sorted(UNDOABLE_KINDS))})"
        )
    if target["id"] in taken_back(events):
        return f"{target['id']} has already been taken back"
    return None


def build_threads(events: list, spk: dict) -> dict:
    """Fold the chronological log into comment threads by root id.

    `resolved` is the event that settled the thread, or None. Either side can
    close one, so a bool beside a second field naming who would be two readings
    of one fact; the settling event answers both questions and carries its own
    `author`.

    A thread is settled by the widget's standing answer: the last action that
    widget sent and the log still lets stand, and then only while that answer
    names the thread. Three things unseat one, and every one of them is the log's
    own word rather than a case written out here. A version that rewrites what a
    decision rested on says `restated`, publishing records the floor, and replay
    drops the action — `action_retracted`, the same test the fold and the words
    gate ask. The reader can take the answer back where they stand, which is the
    `undo` naming it and `taken_back` reading it. And a later action on the same
    widget supersedes the one before it, exactly as the state fold reads a second
    `move` on one card. Without that last one, a reject after an accept left the
    reader's question filed away as answered by the fix they had just turned down,
    while the fold reported the suggestion rejected: the log held one thing, the
    panel showed another, and nothing on either side said so.

    An ask is a widget instance ($awaits), so what answers one is that widget's
    own last word — and the widget id is also the only key the log carries by
    itself. That is why the state fold cannot serve here: it drops an action whose
    widget the current page no longer holds, and the version that honors a
    decision retires the widget that made it, precisely when the thread it settled
    must stay settled. `x-state` holds a verb declaring `resolves` to a
    widget-absolute unit, so the two keys are one key.

    Standing says nothing about the page, and that silence cuts both ways: a stale
    tab's decision unseats an answer whose widget a published version has since
    retired, leaving the fold nothing to paint and the reader's press reaching the
    thread or nothing at all. Asking the page instead would fork the two runtimes,
    which read different pages — the browser's pinned version against this side's
    last published file.

    A `resolve` is a person saying the conversation is done, and the log does not
    fold that away. Nothing here has to take one back: a superseded answer never
    stood, so it has nothing to clear, and whatever was said after it still stands.

    What `resolves` cannot say is the difference between an answer that leaves the
    thread open and an action that is not an answer at all — a reject means the
    first, and both spell it by carrying nothing. The one widget that names a
    thread has two verbs, both of them its answers, so the readings coincide; a
    press that confirms rather than answers, Done over a set of picks, would want
    the third value spelled before its widget could settle a thread.

    `spk` is the page the containment half of the retraction test is read against,
    and it is the reading of the version the outcomes were folded over, so threads
    and state cannot be settled against two different pages. Required, not
    defaulted: a caller with no published page passes `{}` and says so, because a
    default that stood down quietly is exactly where a verb naming a part of its
    own widget would have gone unfloored."""
    floors = retractions(events)
    withdrawn = taken_back(events)
    # widget id -> its last action the log still lets stand: not one the reader
    # took back, and not one a version retracted under it.
    answers = {}
    for e in events:
        if (
            e["kind"] == "action"
            and e["id"] not in withdrawn
            and not action_retracted(e, floors, spk)
        ):
            answers[e["widget"]] = e
    threads = {}
    thread_for = {}
    for e in events:
        # A gesture the reader took back settles nothing, whichever way it settled:
        # the log holds it and no reading of the log stands on it.
        if e["id"] in withdrawn:
            continue
        if e["kind"] == "comment":
            thread = {"root": e, "msgs": [e], "resolved": None}
            threads[e["id"]] = thread
            thread_for[e["id"]] = thread
            continue
        # A standing answer settles the thread it names, and the detail carrying
        # `resolves` is the whole of that condition — a second widget that answers
        # a thread joins by declaring the field, not by being read here by name.
        # The sender snapshots the mapping into the action because the honoring
        # version retires the element that held it, so nothing later can look it up.
        #
        # Settled here, at the answer's own place in the log, rather than after the
        # walk: a resolve pressed between two decisions is the last word on the
        # thread, and applying settlements afterwards would paint over it.
        if e["kind"] == "action":
            answered = threads.get(e["detail"].get("resolves"))
            if answered and answers.get(e["widget"]) is e:
                answered["resolved"] = e
            continue
        if e["kind"] == "reply":
            thread = thread_for[e["parent"]]
            thread["msgs"].append(e)
            thread_for[e["id"]] = thread
        elif e["kind"] == "resolve":
            thread = thread_for[e["parent"]]
            thread["resolved"] = e
        elif e["kind"] == "unresolve":
            thread_for[e["parent"]]["resolved"] = None
    return threads


def anchored_ids(events: list, spk: dict) -> set:
    """Element ids an unresolved thread still points at."""
    return {
        (t["root"].get("anchor") or {}).get("section")
        for t in build_threads(events, spk).values()
        if not t["resolved"]
    } - {None}


VERSION_FILE = re.compile(r"v([1-9][0-9]*)\.html")


def version_num(name: str) -> int:
    """A version's number is its identity; its file name only renders it. So
    everything that orders or addresses versions parses the number out rather
    than working on the name, and the names carry no zero padding — padding is
    what you add to make a string comparison come out right, and nothing here
    compares names. `v10.html` precedes `v9.html` in every ordering a string
    has, and follows it in the only one that means anything."""
    return int(VERSION_FILE.fullmatch(name).group(1))


def version_name(version: int) -> str:
    return f"v{version}.html"


def version_path(page_dir: Path, version: int) -> Path:
    return page_dir / "versions" / version_name(version)


def list_versions(page_dir: Path) -> list:
    versions_dir = page_dir / "versions"
    if not versions_dir.exists():
        return []
    return sorted(
        version_num(p.name)
        for p in versions_dir.iterdir()
        if p.is_file() and VERSION_FILE.fullmatch(p.name)
    )


def published_versions(page_dir: Path, events: list) -> list:
    """Versions the server exposes: those whose `note` event has landed. `version
    publish` runs `version check` first, so a half-written or failing version is
    never live to an open browser — the file existing is not enough."""
    noted = {e["version"] for e in events if e["kind"] == "note"}
    return [version for version in list_versions(page_dir) if version in noted]


def latest_published(page_dir: Path, events: list) -> int:
    """The page the reader is looking at, for a message the agent makes against it — a
    comment, or a report. A version no `note` has released is a page nobody has seen, so
    there is nothing to speak about and the command says so rather than picking a file
    off disk."""
    published = published_versions(page_dir, events)
    if not published:
        sys.exit("no published version; run `leaf version publish` first")
    return published[-1]


def pid_alive(pid: int) -> bool:
    # PermissionError is another user's process, and every pid this module
    # records — servers, agent sessions — runs as this user. After a reboot the
    # low pids are mostly root's, so counting EPERM alive read a stale record
    # as a live server for as long as the machine stayed up.
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def process_info(pid: int) -> tuple[int, str] | None:
    """Two facts about a live process — the pid above it, and the name of the
    program it is itself running — or None once it is gone.

    The name is the executable's own, not the words the command was written
    with: a process launched through a symlink or a `#!` script reports what the
    kernel loaded. That is the point — it answers which program a process *is*,
    which is what `session_pid` asks of an ancestor.

    Two platform doors because there is no portable one. `ps` reads this on
    both, and macOS ships it setuid root, which the seatbelt sandbox Codex runs
    its shell tool under refuses to exec — so the one door that looks portable
    is the one that fails exactly where this is needed (measured inside
    `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
    permitted`)."""
    if sys.platform == "darwin":
        # proc_pidinfo's PROC_PIDT_SHORTBSDINFO, whose whole struct is the two
        # facts wanted; pbsi_comm is the executable's name, truncated to 16.
        class ProcBSDShortInfo(ctypes.Structure):
            _fields_ = [
                ("pbsi_pid", ctypes.c_uint32),
                ("pbsi_ppid", ctypes.c_uint32),
                ("pbsi_pgid", ctypes.c_uint32),
                ("pbsi_status", ctypes.c_uint32),
                ("pbsi_comm", ctypes.c_char * 16),
                ("pbsi_flags", ctypes.c_uint32),
                ("pbsi_uid", ctypes.c_uint32),
                ("pbsi_gid", ctypes.c_uint32),
                ("pbsi_ruid", ctypes.c_uint32),
                ("pbsi_rgid", ctypes.c_uint32),
                ("pbsi_svuid", ctypes.c_uint32),
                ("pbsi_svgid", ctypes.c_uint32),
                ("pbsi_rfu", ctypes.c_uint32),
            ]

        proc_pidt_shortbsdinfo = 13
        info = ProcBSDShortInfo()
        proc_pidinfo = ctypes.CDLL(None).proc_pidinfo
        if proc_pidinfo(
            ctypes.c_int(pid),
            ctypes.c_int(proc_pidt_shortbsdinfo),
            ctypes.c_uint64(0),
            ctypes.byref(info),
            ctypes.c_int(ctypes.sizeof(info)),
        ) != ctypes.sizeof(info):
            return None
        return info.pbsi_ppid, info.pbsi_comm.decode()

    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # The program's name is parenthesised and may hold spaces and parens of its
    # own, so the fields after it are read from past the last ')': state, ppid.
    program = stat[stat.index("(") + 1 : stat.rindex(")")]
    return int(stat[stat.rindex(")") + 1 :].split()[1]), program


def ancestry() -> list[tuple[int, str]]:
    """This process and every process above it, nearest first: (pid, program).

    The walk ends at init, or at whichever ancestor exited while it ran — a
    parent that goes takes the rest of the chain with it, since what is left
    above a reparented process is init's."""
    walked = []
    pid = os.getpid()
    while pid > 1:
        info = process_info(pid)
        if info is None:
            break
        parent, program = info
        walked.append((pid, program))
        pid = parent
    return walked


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.
    """
    require_cross_process_locking()
    try:
        with open(path, "r+b") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def page_lock(page_dir: Path, purpose: str) -> Path:
    """A stable lock for one page, outside the page it guards.

    `page init` must reject a customization source without writing into it, so
    locks that can meet init cannot live in the prospective page directory. The
    resolved path gives every process the same lock while the purpose keeps the
    contract transition independent from the page's current session claim.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def transition_lock(page_dir: Path) -> Path:
    """Serialize service changes, re-vendoring, and contract-bearing writes."""
    return page_lock(page_dir, "transition")


def running_server(page_dir: Path):
    """The desired service, while a process holds its live-server lease."""
    if not lock_is_held(page_dir / "server.lock"):
        return None
    service = read_json(page_dir / "service.json")
    if not service or not service["enabled"]:
        return None
    return {
        **service,
        "url": page_url(service["host"], service["port"], host_key()),
    }


def lifetime_note(page_dir: Path) -> str:
    """What ends this server, said at the moment it starts.

    The two lifetimes are indistinguishable from the terminal — same command,
    same URL — and the difference only shows up hours later, when one process is
    gone and the other isn't. So the serve states which it is rather than
    leaving it to be discovered, on the line after the URL, and names the command
    where that is the only way out.

    Read from service.json, the one place a lifetime is written down. The record
    lands before the URL is printed and survives an explicit stop, so a restart
    restores the same lifetime as well as the same URL."""
    if (read_json(page_dir / "service.json") or {}).get("lifetime") == "standing":
        return (
            "standing server: no agent session claimed this page, so it outlives "
            f"this shell. `leaf server stop {page_dir}` is what stops it."
        )
    return (
        "session server: it stops when the agent session that claimed this page ends."
    )


def stop_when_service_ends(page_dir: Path) -> None:
    """Apply desired state and session ownership from inside the server.

    The process exits as the shutdown operation. That closes the listening
    socket, every accepted keep-alive socket, and the live lease together; a
    graceful `shutdown()` can release the lease while a handler thread still
    owns an accepted connection.
    """
    orphaned_at = None
    while True:
        service = read_json(page_dir / "service.json")
        if not service or not service["enabled"]:
            os._exit(0)
        if service["lifetime"] == "standing":
            time.sleep(0.1)
            continue
        claim = page_claim(page_dir)
        if claim_is_active(claim):
            orphaned_at = None
        elif orphaned_at is None:
            orphaned_at = time.monotonic()
        elif time.monotonic() - orphaned_at >= ORPHAN_GRACE_SECS:
            # A transfer may land after the unlocked observation above. Recheck
            # beside process exit under the page transaction so a new live owner
            # cannot inherit a server already committed to retiring.
            try:
                with PageTransaction(page_dir) as page:
                    service = read_json(page_dir / "service.json")
                    if not service or not service["enabled"]:
                        os._exit(0)
                    if service["lifetime"] == "standing" or page.active_claim:
                        orphaned_at = None
                        continue
                    os._exit(0)
            except FileNotFoundError:
                # Deleting the page removes its successful-init identity. The
                # service has nothing left to preserve and must not recreate it.
                os._exit(0)
        time.sleep(0.1)


def page_access(page_dir: Path, host: str | None = None) -> dict:
    """Where a page is reached: the name its URL carries and the interface its
    server binds. The key that URL also carries is the machine's — `host_key`.

    Derived — no `host` — the address is read from SSH_CONNECTION, whose third
    field is this machine as the client just reached it: a route the session
    carrying the request has already demonstrated, rather than a guess about what
    resolves from where. No SSH_CONNECTION is the same answer for a reader on
    this machine: loopback. The server binds that address alone, so the open port
    faces only the network the session crossed.

    But a route the session demonstrated is not one the user's browser
    shares: a jump host or NAT between them and this machine leaves it
    unroutable from where they sit, and no derivation from this end can know the
    name they do route to. `--host` states it. A stated name goes in the URL and
    the bind widens to every interface of both families (`::`, V6ONLY off),
    because the name need not resolve to an address this machine could bind (a
    NAT'd public IP), let alone say which family the user reaches it by. An
    overlay network the machine has joined (a tailnet) is just one more
    interface. That widens exposure to the machine's other networks and no
    further — leaf never creates a route that didn't exist.

    Recorded once and kept. `start_server` restarts a dead server by re-running
    `server run` bare, and a fresh address there would leave the user's open page
    polling a URL that no longer answers — which is why a stated host is recorded
    here rather than passed per run."""
    access = read_json(page_dir / "service.json")
    if access and host is None:
        return access
    if host:
        # The record's one door checks what it keeps: a scheme, a port, or a
        # path pasted into --host would mint a URL no browser resolves, handed
        # to the one reader who can't report it.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?", host):
                sys.exit(
                    f"--host {host}: not a hostname or IP address "
                    "(no scheme, no port — leaf picks the port)"
                )
        # Over the record, not in place of it: a --host restates where the page
        # is reached, and the record's other facts — the exact port an open tab
        # polls, the standing lifetime — restate nothing and must survive, or
        # the recovery this flag exists for demotes the dashboard it recovers.
        access = {**(access or {}), "host": host, "bind": "::"}
    else:
        ssh = os.environ.get("SSH_CONNECTION", "").split()
        addr = ssh[2] if len(ssh) == 4 else "127.0.0.1"
        access = {"host": addr, "bind": addr}
    return access


def host_key() -> str:
    """The key every page this machine serves is read with, minted at the first
    `server run` and kept in the state home. It rides in the URL Claude hands
    over, and `authorized` puts it in a cookie on arrival.

    The key exists because serving anywhere but loopback puts an unauthenticated
    writer on whatever network reached us, and `POST /api/event` appends to a log
    that outranks the document and replays onto every version after.

    One key for the machine rather than one per page, because every page here
    goes to the same reader — the one person the agent is working with. A page
    has nothing to keep from another page's reader, which is what lets the
    `others` menu link them, and what lets the cookie jar, scoped by host and
    blind to the port, hold one key under one name.

    The cost is that handing out any page's URL hands out every page on the
    machine, present and future. Leaf has one reader; giving it a second
    means scoping the key back to the page first.

    The cookie is a second copy of that cost: a browser's jar is port-blind, so
    any server the reader visits on the same host string — a dev server on
    localhost:3000 — receives the key with their request. Considered and kept:
    every cookie-borne credential has this property (a port-scoped name or a
    derived value is still delivered to every port and replayable against this
    one), and dropping the cookie for a key-in-URL scheme breaks the thing the
    cookie exists for — the page's static asset references (/leaf.js, a module's
    ../leaf.js import) can carry no query, so every asset would need the auth
    the redirect-following request has. The boundary is the host string; a
    reader on a shared or hostile-local-service machine narrows it by serving
    on a name other servers don't share (--host).

    Linked into place rather than written over, so two first serves racing on a
    fresh machine agree on whichever won. Each keeping its own would have their
    servers overwrite the one shared cookie in turn, for as long as both ran."""
    path = state_home() / "access.json"
    if not path.exists():
        staged = path.with_name(f".{secrets.token_hex(8)}.tmp")
        staged.write_bytes(json_bytes({"token": secrets.token_urlsafe(16)}))
        staged.chmod(0o600)
        try:
            os.link(staged, path)
        except FileExistsError:
            pass  # someone minted first; theirs is the key, read below
        staged.unlink()
    return read_json(path)["token"]


def page_url(host: str, port: int, token: str) -> str:
    """The handover URL. A bare IPv6 address is bracketed, since the authority
    already separates its port with a colon."""
    host = f"[{host}]" if ":" in host else host
    return f"http://{host}:{port}/?t={token}"


def config_home() -> Path:
    """$XDG_CONFIG_HOME/leaf (~/.config/leaf/) — the user's overlay layer."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "leaf"


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, init/ the stable per-path creation
    leases, and access.json the one key every page here is served with
    (`host_key`). State, not config:
    claim records carry pids and absolute paths, while page service records
    carry ports, so this state is bound to this machine, as is the key that
    reaches it.

    Created here, owner-only: the key is what stands between another local user
    and a log that outranks the document, and a 0644 file under a traversable
    path hands it to anyone on a shared machine. One writer for the mode, since
    every path into the state home resolves through this call."""
    home = (
        Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        / "leaf"
    )
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def host_identity() -> dict | None:
    """The identity the host session supplies through the environment, or None
    outside an agent host: `id`, the session's own stable id; `host`, which
    program is running it; `agent`, the display name the page shows for it.

    The name is LEAF_AGENT where the launch set one — naming a worker in its
    environment needs no cooperation from the agent, so every command it runs
    speaks as that voice — and the host's own name otherwise. `host` stays a
    separate fact because behavior keys on it (unattended_pages prescribes
    unified exec or background tasks by host) and a display name is anyone's to
    choose. The LEAF_* door is the launcher's mapping of Codex today; a
    third host earns its own value when one arrives — the id and the name, which
    are the whole of what a launcher can state. What outlives the command is
    `session_pid`'s to find."""
    if sid := os.environ.get("CLAUDE_CODE_SESSION_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Claude"
        return {"id": sid, "host": "claude-code", "agent": agent}
    if sid := os.environ.get("LEAF_SESSION_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Codex"
        return {"id": sid, "host": "codex", "agent": agent}
    return None


def message_identity() -> dict:
    """The voice an agent-authored event carries: the posting session's display
    name and session id, read from its own environment rather than the page's
    claim record — the claimant is whoever watches the page, and on a page
    several sessions report to, that is usually not the poster. Empty outside a
    host session: the readers' generic label covers an event with no voice, and
    a stored placeholder would only impersonate a name."""
    identity = host_identity()
    if identity is None:
        return {}
    return {"agent": identity["agent"], "session": identity["id"]}


def session_pid(identity: dict) -> int:
    """The process whose lifetime is the agent session's, which is what the
    claim records and its readers act on: a dead pid makes ownership inactive,
    and a session-managed server retires ORPHAN_GRACE_SECS after it
    (`stop_when_service_ends`).

    Claude Code states it outright and Codex states nothing, so the Codex half
    is discovered: the nearest ancestor running the `codex` program. The
    launcher cannot hand it over, because a shell tool's $PPID is a fact about
    the *shape* of the command rather than about the session. Measured through
    `codex exec` at 0.147.0: a bare command, an `&&` chain and a `bash -lc` all
    reported the codex process, because the shell it wraps them in can exec a
    last simple command in place; `leaf … | cat` reported the wrapping shell
    itself, which exits with the pipeline. Recording that one would have taken
    the page's server down a second after the command that started it, and the
    page would have told its reader no session holds it while the session sat
    there working."""
    if identity["host"] == "claude-code":
        return int(os.environ["CLAUDE_PID"])
    walked = ancestry()
    for pid, program in walked:
        if program == "codex":
            return pid
    # Nothing to fall back to: any pid guessed here is a claim that expires on
    # its own, and the states that follow from one are silent. LEAF_SESSION_ID
    # with no codex above it is a hand-built environment, so say what was walked.
    chain = " → ".join(program for _, program in walked)
    sys.exit(
        "LEAF_SESSION_ID names a Codex session but no codex process runs above "
        f"this one ({chain}); leaf takes the session's lifetime from it"
    )


def claim_path(page_dir: Path) -> Path:
    """The one ownership record for a resolved page path."""
    return state_home() / "claims" / f"{page_key(page_dir)}.json"


def page_key(page_dir: Path) -> str:
    """A filesystem-safe identity for state held outside one page directory."""
    return hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()


def init_lock_path(page_dir: Path) -> Path:
    """The lease serializing creation before a page has its own transaction."""
    return state_home() / "init" / f"{page_key(page_dir)}.lock"


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one that is released or whose pid died."""
    return read_json(claim_path(page_dir))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner."""
    return bool(claim and claim["released"] is None and pid_alive(claim["pid"]))


def claim_records() -> list:
    """Every atomic page claim record currently on this machine."""
    directory = state_home() / "claims"
    if not directory.is_dir():
        return []
    return [claim for path in directory.glob("*.json") if (claim := read_json(path))]


class PageTransaction:
    """One page transition serialized by its append-only log."""

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir.resolve()
        self._lock = None
        self._log = None

    def __enter__(self):
        self._lock = flocked(self.page_dir / "comments.jsonl")
        self._log = self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def take_claim(self, identity: dict, pid: int) -> tuple[dict | None, dict]:
        previous = self.claim
        path = claim_path(self.page_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        claim = {
            "page": str(self.page_dir),
            "id": identity["id"],
            "host": identity["host"],
            "pid": pid,
            "agent": identity["agent"],
            "cwd": os.getcwd(),
            "ts": now_iso(),
            "released": None,
        }
        write_json(path, claim)
        return previous, claim

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if self.claim != expected:
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            write_json(path, previous)

    def owned_by(self, identity: dict | None) -> bool:
        """Whether this transaction may act for the given waiter."""
        if identity is None:
            return self.active_claim is None
        claim = self.active_claim
        return bool(
            claim and (claim["host"], claim["id"]) == (identity["host"], identity["id"])
        )

    def release_claim(self) -> None:
        claim = self.claim
        if claim and claim["released"] is None:
            write_json(claim_path(self.page_dir), {**claim, "released": now_iso()})

    @property
    def status(self) -> dict:
        return read_json(self.page_dir / "status.json") or {"state": "idle"}

    def set_status(self, state: str, detail: str, *, handoff: bool = False) -> None:
        status = {"state": state, "detail": detail, "ts": now_iso()}
        if handoff:
            status["handoff"] = True
        write_json(self.page_dir / "status.json", status)

    @property
    def events(self) -> list:
        return read_events(self.page_dir)

    def matching_attempt(self, event: dict) -> dict | None:
        """An accepted retry, read under this transaction's log lease."""
        return _matching_attempt(self._log, event)

    def append_event(self, event: dict) -> dict:
        """Append under this transaction without re-entering its log lease."""
        return _append_event_unlocked(self._log, event)

    @property
    def cursor(self) -> int:
        return read_cursor(self.page_dir)

    def watch_state(self, identity: dict | None) -> str:
        if not self.owned_by(identity):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the host session the page's watcher, if a host supplied one.

    `server start` and named `leaf wait` claim; authoring commands do not. A
    bare-shell serve makes no claim and therefore starts as standing.
    """
    identity = host_identity()
    if not identity:
        return None
    pid = session_pid(identity)
    with PageTransaction(page_dir) as page:
        return page.take_claim(identity, pid)


def claim_page(page_dir: Path) -> bool:
    return take_page_claim(page_dir) is not None


def restore_page_claim(
    page_dir: Path, transition: tuple[dict | None, dict] | None
) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    previous, expected = transition
    with PageTransaction(page_dir) as page:
        page.restore_claim(expected, previous)


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records()
        if claim_is_active(claim)
        and (session_id is None or claim["id"] == session_id)
        and (Path(claim["page"]) / "comments.jsonl").is_file()
    }
    return sorted(pages, key=str)


def other_leaves(page_dir: Path) -> list:
    """The machine's other live leaves, for the banner's panel: each page
    whose server is up, as a title, its handover URL, and the same presence
    facts the page ships about itself — so a row there and the banner above it
    are the one judgment reading the one shape.

    Candidates are the conventional pages/ home and every claim record, which
    is what finds a page served from a session's scratch directory. Released
    and dead claims stay useful here as provenance. Liveness is the held
    server.lock lease, the same answer `running_server` gives everything else,
    and the URL is the one in durable service state, key included. The title is the
    newest published version's — the version that page's own root URL answers
    with — read the way `transcript` reads it.

    The whole scan runs on every /api/state; what it reads of each neighbour is
    kept per file, so a poll costs the scan and the presence reads rather than a
    parse of every live neighbour's page (`parse_version`)."""
    candidates = []
    pages = state_home() / "pages"
    if pages.is_dir():
        candidates += (d for d in pages.iterdir() if d.is_dir())
    candidates += (Path(claim["page"]) for claim in claim_records())
    others = []
    seen = {page_dir.resolve()}
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a log a disk fault corrupted would otherwise 500
        # every open page's poll on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if not info:
                continue
            events = read_events(candidate)
            published = published_versions(candidate, events)
            # A server up before its page's first publish serves nothing to link.
            if not published:
                continue
            parser = parse_version(candidate, published[-1])
        except Exception:  # noqa: BLE001, S112 - whatever shape its fault takes
            continue
        others.append(
            {
                "title": parser.title.strip() or candidate.name,
                "url": info["url"],
                **presence(candidate, events),
            }
        )
    return sorted(others, key=lambda entry: entry["title"].lower())


def unacknowledged(events: list, cursor: int) -> list:
    """The events past the acknowledgement cursor that the page's watcher owes a
    reading: the user's own, and workers' reports — a report moves the page the
    way a user's action does, and the watcher is the one who can absorb it into
    a version. One cursor and one predicate for the whole batch, so `leaf
    wait`'s output, the Stop hook's count, and the idle gate cannot disagree
    about what is still owed. The reader's banner counts only the user half
    (full_state's `pending`): a report is news the agent owes the page, not
    something the reader owes an answer. A session that reports to a page it
    also watches reads its own report back once — rare enough (workers report,
    the watcher publishes) that a session-keyed carve-out would cost a second,
    parameterized predicate for no failure anyone has hit."""
    return [
        e
        for e in events
        if e["seq"] > cursor
        # The user's own, a worker's report, and the page reporting itself
        # broken — the last is the agent's debt exactly as a report is.
        and (e["author"] == "user" or e["kind"] in ("report", "error"))
    ]


def waiter_lease_path(page_dir: Path | None, session: dict | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A host wait covers every page its session owns, so its lease belongs to the
    session. Outside a host, a named page is the entire watch set and holds a
    page-local lease. An unnamed bare-shell wait has no watch set and no lease.
    """
    if session:
        return state_home() / "sessions" / f"{session['id']}.wait"
    return page_dir / "waiter.lock" if page_dir is not None else None


def take_waiter_lease(path: Path):
    """Take and return a wait lease, or None when another wait already holds it."""
    require_cross_process_locking()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = open(path, "a+b")  # noqa: SIM115 - returned and held for the wait's life
    try:
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        record.close()
        return None
    return record


def wait_is_live(page_dir: Path, session: dict | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session)
    return bool(lease_path and lock_is_held(lease_path))


def presence(page_dir: Path, events: list) -> dict:
    """What a seat showing this page says about it: the agent's claim, everything
    the directory holds that can answer for it, and where that agent is working.
    One gatherer for every such seat — `full_state` spreads it into the page's own
    poll answer, and `other_leaves` attaches it to each entry — so the runtime's one
    claim-against-proof judgment reads the same fields whichever page it judges,
    and the board's account of a neighbour is the account this page gives of
    itself."""
    # A file that isn't there stands in as its whole record, so every read below
    # indexes rather than asking twice whether the field arrived.
    status = read_json(page_dir / "status.json") or {
        "state": "idle",
        "detail": "",
        "ts": None,
    }
    claim = page_claim(page_dir)
    active = claim if claim_is_active(claim) else None
    # What the wait owner has acknowledged after the complete batch reached its
    # next durable consumer. An action past this seq has not reached that point,
    # which lets the runtime carry it forward onto versions written without it.
    cursor = read_cursor(page_dir)
    return {
        "status": status,
        "listening": wait_is_live(page_dir, active),
        "cursor": cursor,
        # The reader's number, not the watcher's: their own messages the agent
        # hasn't taken in. Reports ride the same cursor but are the agent's debt,
        # so the banner never tells a reader that a worker's news is waiting on them.
        "pending": sum(
            1 for e in unacknowledged(events, cursor) if e["author"] == "user"
        ),
        "agent": claim.get("agent", "Claude") if claim else "Claude",
        # The claimant's host program, for behavior that keys on it — the display
        # name above is anyone's to choose, so nothing may dispatch on it.
        "host": claim.get("host") if claim else None,
        # None when nothing claimed the page — interact.py run outside an agent host.
        "session_alive": active is not None if claim else None,
        # When a browser last polled the page (the server bumps viewed.json,
        # throttled), or None for a page nobody has ever opened — which used to
        # be indistinguishable from one the user studied and left.
        "viewed": (read_json(page_dir / "viewed.json") or {"t": None})["t"],
        # Where the claimant is working (claim_page), for the board's hover: what
        # tells one leaf from another is the work behind it, and neither the title
        # nor the page directory says which that is. It outlives the session that
        # wrote it, as every other fact in this record does — a page the board
        # calls unheld came out of somewhere, and that is still where it came from.
        # None for a page nothing ever claimed, which is the honest nothing.
        "session_cwd": claim.get("cwd") if claim else None,
    }


def full_state(
    page_dir: Path, events: list, versions: list, layer: str | None = None
) -> dict:
    return {
        "layer": layer or layer_generation(page_dir),
        "versions": versions,
        **presence(page_dir, events),
        # As logged: a message's text is Markdown the page's vendored runtime renders,
        # and its markup is the fragment the CLI gate validated. The wire adds nothing,
        # so the only vocabulary a page's frozen layer has to keep speaking is the
        # log's own, which $events already stamps.
        "events": events,
    }


class Handler(BaseHTTPRequestHandler):
    page_dir = None
    token = None
    event_attempts = None
    event_attempts_lock = None
    # Set by `authorized` when the key arrived in the query, cleared by the one
    # writer that spends it.
    set_cookie = False
    # The render gate previews a version before its `note` publishes it —
    # refusing the note is the gate's whole job. Set to that version's number,
    # the handler exposes on-disk versions up to it, previewed one included as
    # latest, so the runtime neither 404s the preview nor follows the published
    # latest away from it mid-check. None — every server a user reaches —
    # exposes noted versions only.
    preview_upto = None

    def versions_live(self, events):
        if self.preview_upto is None:
            return published_versions(self.page_dir, events)
        return [
            version
            for version in list_versions(self.page_dir)
            if version <= self.preview_upto
        ]

    def page_state(self) -> dict:
        """The current log reading used by GET and accepted POST responses."""
        events = read_events(self.page_dir)
        state = full_state(
            self.page_dir,
            events,
            self.versions_live(events),
            layer=self.layer,
        )
        # Every URL in `others` carries the machine key (`host_key`), so the list
        # reaches neighbouring pages without creating another authorization path.
        state["others"] = other_leaves(self.page_dir)
        return state

    def log_message(self, *args):
        pass

    def handle(self):
        """The exchange, ending quietly when the reader is no longer there.

        A reader who closes the tab mid-response leaves the handler writing into a
        socket the kernel answers with a reset, and `socketserver` prints the
        `BrokenPipeError` as a twenty-five-line traceback naming this file — a
        server fault, by every appearance, for the one thing a page is most
        certain to do. Closing a tab is not an error and there is nothing to
        answer with, the peer being gone; every read and write on the connection
        passes through here, so this is where it ends. `ConnectionError` is the
        whole of that case: its other subclass, a refused connection, cannot
        reach a socket the server already accepted."""
        try:
            super().handle()
        except ConnectionError:
            pass

    def authorized(self) -> bool:
        """The key, from the handover URL or from the cookie an earlier request
        set out of it. One arrival is enough: the runtime's own fetches are
        relative and carry no query, and a reader who reloads or bookmarks the bare
        address is the same reader. So nothing has to thread the key through the
        page, and `leaf.js` never learns there is one."""
        if secrets.compare_digest(
            parse_qs(urlsplit(self.path).query).get("t", [""])[0], self.token
        ):
            self.set_cookie = True
        else:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            if KEY_COOKIE not in jar or not secrets.compare_digest(
                jar[KEY_COOKIE].value, self.token
            ):
                return False
        return True

    def end_headers(self):
        # Every response ends here — answered, redirected, or refused — so the
        # cookie has one writer rather than one per path that sends a header.
        path = urlsplit(self.path).path
        if path.startswith("/api/") or path == "/registry.json":
            self.send_header("Leaf-Layer", self.layer)
        if self.set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{KEY_COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.set_cookie = False
        super().end_headers()

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(
            status, "application/json", json.dumps(obj, ensure_ascii=False).encode()
        )

    def do_GET(self):
        self._answer(self._get)

    def do_POST(self):
        # The body is route preparation: inside the answer boundary, but after the one
        # shared key gate. An unauthenticated peer therefore cannot choose an allocation
        # or park a handler in a body read. Its refusal names no attempt because no body
        # was trusted enough to read one from; the browser accepts that attempt-less
        # final answer because the refusal happened before any append could have begun.
        self._answer(self._post, prepare=self._read_posted)

    def _read_posted(self) -> tuple:
        """The POSTed body as a dict, or the refusal it has already earned.

        Reading and parsing can fail in different ways, all before an append is
        possible. Naming those failures as final lets the outbox put the gesture back;
        an unexpected exception remains inside `_answer` and is therefore retryable.
        """
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        except (TypeError, ValueError, MemoryError):
            return {}, "invalid Content-Length"
        try:
            posted = json.loads(body)
        except (ValueError, RecursionError):
            return {}, "invalid JSON"
        if not isinstance(posted, dict):
            return {}, "event must be a JSON object"
        return posted, None

    def _refuse(self, error: str, status: int = 400) -> None:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self.command == "POST" and urlsplit(self.path).path == "/api/event":
            status, body = self.event_rejection(self.posted, error, status)
            self._json(body, status)
        else:
            self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> None:
        """One boundary for authorization, route preparation, and route faults.

        Unanswered, a fault
        drops the socket, socketserver buries the traceback in stderr nothing reads, and
        the banner says "Server offline" about a server that is up — so every
        fault becomes a 500 naming itself, which the banner can show to the one
        person still looking. The key is checked here for `end_headers`'s reason: every
        request passes through, so there is one gate rather than one per method, and a
        route added later cannot be the one that forgot to ask. POST preparation is
        deliberately after that gate, so an unknown peer cannot choose a body-read cost.
        """
        try:
            if prepare:
                self.posted, self.posted_error = {}, None
            if not self.authorized():
                # HTTP/1.1 cannot reuse a connection whose declared request body was
                # never consumed: those bytes would be parsed as the next request.
                if prepare:
                    self.close_connection = True
                self._refuse(NO_KEY, 403)
                return
            if prepare:
                self.posted, self.posted_error = prepare()
            route()
        except Exception as error:  # noqa: BLE001 - the boundary answers, never buries
            # Not a refusal: a fault may have landed either side of the append, so the
            # browser must retry the same attempt instead of putting its gesture back.
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass  # the peer left mid-answer; nobody to tell

    def _get(self):
        path = urlsplit(self.path).path
        if path == "/":
            versions = self.versions_live(read_events(self.page_dir))
            if not versions:
                self._json({"error": "no published versions yet"}, 404)
                return
            self.send_response(302)
            self.send_header("Location", f"/versions/{version_name(versions[-1])}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/state":
            # A poll is the one proof a browser holds the page open, and before
            # this nothing recorded it: a page nobody ever opened and one the
            # user studied and left looked identical from the agent's side.
            # Throttled — presence needs a recency, not a request log. Never
            # from a preview: the render gate's own browser is not the reader,
            # and its polls would leave no page "never opened" again.
            cls = type(self)
            if (
                self.preview_upto is None
                and time.time() - getattr(cls, "viewed_at", 0) > 30
            ):
                cls.viewed_at = time.time()
                write_json(self.page_dir / "viewed.json", {"t": cls.viewed_at})
            # Versions pass through the handler's own view, so a preview state
            # agrees with the version it serves.
            self._json(self.page_state())
            return
        # Browsers ask for this unprompted, and go on asking where nothing in the
        # markup names an icon — the runtime's link is written as the chrome is built,
        # which is after the parse. Answering "no content" rather than letting it fall
        # through to 404 keeps the console clean, which is what makes an empty console
        # worth asserting on (tests/test_render.py).
        if path == "/favicon.ico":
            self._send(204, "image/x-icon", b"")
            return
        if SERVED_PATH.fullmatch(path):
            if path.startswith("/versions/"):
                version = version_num(Path(path).name)
                if version not in self.versions_live(read_events(self.page_dir)):
                    self._json(
                        {
                            "error": "not published yet; run `leaf version publish` first"
                        },
                        404,
                    )
                    return
            file = self.page_dir / path.lstrip("/")
            # is_file, not exists: the vendor pattern admits "." and "..", which
            # resolve to directories.
            if file.is_file():
                ctype = CONTENT_TYPES.get(Path(path).suffix, "application/octet-stream")
                # charset describes an encoding, so it rides on the types that
                # have one. On a PNG it is noise.
                if ctype not in BINARY_TYPES:
                    ctype += "; charset=utf-8"
                self._send(200, ctype, file.read_bytes())
                return
        self._json({"error": "not found"}, 404)

    @staticmethod
    def event_rejection(event: dict, error: str, status: int = 400) -> tuple:
        """A final answer proving that this execution appended no event."""
        body = {"ok": False, "error": error, "final": True}
        if event.get("attempt"):
            body["attempt"] = event["attempt"]
        return status, body

    def accepted_state(self) -> tuple:
        return 200, {"ok": True, "state": self.page_state()}

    def coordinate_event(self, event: dict) -> tuple:
        """Run one copy of an attempt and share its outcome with concurrent copies."""
        attempt = event.get("attempt")
        if not attempt:
            return self.execute_event(event)
        payload = _attempt_payload(event)
        with self.event_attempts_lock:
            execution = self.event_attempts.get(attempt)
            if execution is None:
                execution = AttemptExecution(payload)
                self.event_attempts[attempt] = execution
                owner = True
            else:
                owner = False
                if execution.payload != payload:
                    return self.event_rejection(
                        event,
                        f"attempt {attempt!r} already belongs to another event",
                        409,
                    )
        if not owner:
            execution.done.wait()
            return execution.result
        try:
            result = self.execute_event(event)
        except Exception as error:  # noqa: BLE001 - every waiter needs an outcome
            # A fault may occur after append. Withholding `final` makes the next
            # identical request find the accepted event or execute the attempt again.
            result = (
                500,
                {
                    "ok": False,
                    "attempt": attempt,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
        finally:
            execution.result = result
            execution.done.set()
            # Waiters retain the execution object. Acceptance is durable in the log;
            # every other outcome must be evaluated again if it is posted later.
            with self.event_attempts_lock:
                if self.event_attempts.get(attempt) is execution:
                    del self.event_attempts[attempt]
        return result

    def execute_event(self, event: dict) -> tuple:
        """Validate mutable page state and append as one log transaction.

        `_post` checks the payload's declared shape before attempt coordination. A
        re-vendor can replace that declaration before this transaction is acquired,
        so an action's contract is deliberately read again inside the lease: this
        reading, not the admission reading, is the one allowed to append beside the
        page's current vocabulary.
        """
        kind = event["kind"]
        # Every decision whose validity depends on the log stays under the append
        # lock through the write. In particular, two tabs cannot both validate an
        # undo against the same standing target and append after either lock is gone.
        with PageTransaction(self.page_dir) as page:
            # Acceptance outranks mutable state validation. A retry for an accepted
            # attempt asks for its state; it does not repeat the gesture.
            if "attempt" in event:
                event["author"] = "user"
                try:
                    existing = page.matching_attempt(event)
                except AttemptConflict as error:
                    return self.event_rejection(event, str(error), 409)
                if existing:
                    return self.accepted_state()
            events = page.events
            if "version" in event:
                live_versions = self.versions_live(events)
                if event["version"] not in live_versions:
                    return self.event_rejection(
                        event, f"{kind} version must be one of {live_versions}"
                    )
            if kind == "done":
                mode = version_review_mode(self.page_dir, event["version"])
                if mode != "sign-off":
                    return self.event_rejection(
                        event,
                        f"version {event['version']} does not declare "
                        '<meta name="lf-review" content="sign-off">, so it has no '
                        "approval to record",
                    )
            if kind == "action":
                # This is not the static admission read in `_post`: re-vendoring and
                # this transaction have now chosen an order, so only this registry
                # can authorize an action that will be appended under the same lease.
                try:
                    registry = load_registry(self.page_dir)
                except RegistryError as error:
                    return self.event_rejection(event, str(error))
                if registry is None:
                    return self.event_rejection(event, "the page has no registry.json")
                if error := action_contract_error(
                    event,
                    parse_version(self.page_dir, event["version"]).by_id,
                    thread_structure(events),
                    registry,
                ):
                    return self.event_rejection(event, error)
            if "parent" in event and event["parent"] not in {
                e["id"] for e in events if e["kind"] in {"comment", "reply"}
            }:
                return self.event_rejection(
                    event, f"unknown parent {event['parent']!r}"
                )
            if kind == "undo" and (error := undo_error(event, events)):
                return self.event_rejection(event, error)
            event["author"] = "page" if kind == "error" else "user"
            append_event(page, event)
        return self.accepted_state()

    def _post(self):
        if urlsplit(self.path).path != "/api/event":
            self._json({"error": "not found"}, 404)
            return
        # Preview requests have passed authentication and body preparation, so
        # their refusal can name the attempt without writing to the real log.
        if self.preview_upto is not None:
            self._refuse("the preview server is read-only", 403)
            return
        current_layer = self.layer
        if self.headers.get("Leaf-Layer") != current_layer:
            # Preparation already consumed the body. A stale runtime needs the
            # current generation, not a verdict in a vocabulary it no longer speaks.
            self._json({"layer": current_layer})
            return
        if self.posted_error:
            self._refuse(self.posted_error)
            return
        event = self.posted
        try:
            registry = load_registry(self.page_dir)
        except RegistryError as error:
            self._refuse(str(error))
            return
        if registry is None:
            self._refuse("the page has no registry.json")
            return
        contracts = registry["$events"]["kinds"]
        browser_kinds = sorted(
            name for name, contract in contracts.items() if "browser" in contract
        )
        kind = event.get("kind")
        if not isinstance(kind, str) or kind not in browser_kinds:
            self._refuse(f"kind must be one of {browser_kinds}")
            return
        # The server owns the record envelope and agent identity. Removing client
        # copies before validation prevents them from entering attempt identity too.
        for field in ("id", "author", "agent", "session", "ts", "seq"):
            event.pop(field, None)
        if error := event_record_error(contracts[kind], event, browser=True):
            self._refuse(f"{kind} event is invalid: {error}")
            return
        status, answer = self.coordinate_event(event)
        self._json(answer, status)


def handler_for(
    page_dir: Path, token: str, preview_upto=None, protocol_version="HTTP/1.0"
):
    """A request handler bound to one page, publication view, and key. The key has no
    default: every server over a page directory is reachable by whatever reached the
    machine, so there is no construction that should quietly go without one."""
    return type(
        "PageHandler",
        (Handler,),
        {
            "page_dir": page_dir,
            "token": token,
            "preview_upto": preview_upto,
            "protocol_version": protocol_version,
            "event_attempts": {},
            "event_attempts_lock": threading.Lock(),
            "layer": layer_generation(page_dir),
        },
    )


def layer_dirs() -> list:
    """Widget-layer sources, lowest precedence first: leaf's integrated layer
    (the runtime and the machine's own vocabulary), its bundled widgets (the
    content families, shipped as an overlay so they reach a page through the door
    any layer's widgets use), the user layer, the project layer (resolved against
    the working directory). Each mirrors the assets layout:
    theme.css/registry.json/leaf.js at the top, modules in widgets/,
    third-party files in vendor/. Theme files form one cascade, registry files
    are additive by top-level entry, and every other file replaces by path."""
    return [ASSETS, BUNDLED, config_home(), Path.cwd() / ".leaf"]


def checked_layers(sources: list) -> list:
    """Existing, structurally complete layer roots.

    An overlay path of the wrong kind is authored input, not an absent
    customization. Refuse it here once so every merger can assume the layer
    shape the public guide describes.
    """
    layers = []
    for layer in sources:
        if not (layer.exists() or layer.is_symlink()):
            continue
        if not layer.is_dir():
            sys.exit(f"{layer} must be a directory")
        for name in VENDORED_FILES:
            path = layer / name
            if (path.exists() or path.is_symlink()) and not path.is_file():
                sys.exit(f"{path} must be a file")
        for sub in VENDORED_DIRS:
            directory = layer / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            if not directory.is_dir():
                sys.exit(f"{directory} must be a directory")
            for path in directory.iterdir():
                if not path.is_file():
                    sys.exit(f"{path} must be a file")
        layers.append(layer)
    return layers


def layer_source_paths(layers: list) -> list:
    """Every path a layer reads, including the targets of nested symlinks."""
    paths = []
    for layer in layers:
        paths.append(layer.resolve())
        paths.extend(
            path.resolve()
            for name in VENDORED_FILES
            if ((path := layer / name).exists() or path.is_symlink())
        )
        for sub in VENDORED_DIRS:
            directory = layer / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            paths.append(directory.resolve())
            if directory.is_dir():
                paths.extend(path.resolve() for path in directory.iterdir())
    return paths


class _Location(NamedTuple):
    """A path in the one form containment can be read off without touching disk.

    `lineage` is the filesystem identity — `samefile`'s own pair — of the deepest
    existing ancestor and of every ancestor above it, deepest first; `tail` is
    the components below that ancestor which don't exist yet, case-folded where
    the volume ignores case. Two of these answer every question below by
    comparison alone.

    That is the whole point of the form. The callers are set intersections: every
    layer source against every other, every source against every vendored
    destination — 786 containment tests over the shipped layer's thirty-six
    distinct paths. Asked path-by-path, each test re-resolved both paths and
    stat'd its way up both ancestor chains, so `page init` spent two thirds of
    itself on some 37,000 `stat` calls. Canonicalising each path once leaves the
    syscalls proportional to the paths rather than to the tests, which halves
    `page init` and takes two thirds off its system time."""

    lineage: tuple
    tail: tuple


def _path_location(path: Path) -> _Location:
    """Read a path into the form above."""
    ancestor = path.resolve()
    tail = []
    while True:
        try:
            identity = ancestor.stat()
        except (FileNotFoundError, NotADirectoryError):
            tail.append(ancestor.name)
            ancestor = ancestor.parent
            continue
        break
    lineage = [(identity.st_dev, identity.st_ino)]
    # The ancestors of a path that resolved all exist, so a failure here is the
    # filesystem moving under the command and belongs to whoever called it.
    for parent in ancestor.parents:
        above = parent.stat()
        lineage.append((above.st_dev, above.st_ino))
    # Only a tail can be case-folded, so a path that exists never pays for the
    # volume probe — which is every path the set intersections compare.
    if tail and not _filesystem_case_sensitive(ancestor):
        tail = [part.casefold() for part in tail]
    return _Location(tuple(lineage), tuple(reversed(tail)))


def _filesystem_case_sensitive(path: Path) -> bool:
    """Whether new names on path's filesystem distinguish letter case."""
    if sys.platform != "darwin":
        return os.path.normcase("A") != os.path.normcase("a")

    # Darwin exposes this per volume rather than through normcase: APFS can be
    # mounted either way, and normcase leaves names unchanged in both cases.
    class AttrList(ctypes.Structure):
        _fields_ = [
            ("bitmapcount", ctypes.c_uint16),
            ("reserved", ctypes.c_uint16),
            ("commonattr", ctypes.c_uint32),
            ("volattr", ctypes.c_uint32),
            ("dirattr", ctypes.c_uint32),
            ("fileattr", ctypes.c_uint32),
            ("forkattr", ctypes.c_uint32),
        ]

    class VolumeCapabilities(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_uint32),
            ("capabilities", ctypes.c_uint32 * 4),
            ("valid", ctypes.c_uint32 * 4),
        ]

    attr_vol_info = 0x80000000
    attr_vol_capabilities = 0x00020000
    case_sensitive = 0x00000100
    attributes = AttrList(5, 0, 0, attr_vol_info | attr_vol_capabilities, 0, 0, 0)
    result = VolumeCapabilities()
    getattrlist = ctypes.CDLL(None, use_errno=True).getattrlist
    getattrlist.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(AttrList),
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_ulong,
    ]
    getattrlist.restype = ctypes.c_int
    if getattrlist(
        os.fsencode(path),
        ctypes.byref(attributes),
        ctypes.byref(result),
        ctypes.sizeof(result),
        0,
    ):
        return True
    if not result.valid[0] & case_sensitive:
        return True
    return bool(result.capabilities[0] & case_sensitive)


def location_is_within(here: _Location, there: _Location) -> bool:
    """The one implementation of containment; everything below reads it.

    An existing `there` is reached by finding its identity among `here`'s
    ancestors. One that doesn't exist yet is reached only from the same deepest
    existing ancestor, with its tail as a prefix — which is also why folding each
    tail by its own volume above is safe: tails are compared only when the two
    ancestors are one inode, and so one volume."""
    if not there.tail:
        return there.lineage[0] in here.lineage
    return (
        here.lineage[0] == there.lineage[0]
        and here.tail[: len(there.tail)] == there.tail
    )


def locations_overlap(left: _Location, right: _Location) -> bool:
    return location_is_within(left, right) or location_is_within(right, left)


def located(paths) -> list:
    """Each path beside its location, for a caller about to compare it many times."""
    return [(path, _path_location(path)) for path in paths]


def path_is_within(path: Path, root: Path) -> bool:
    """Filesystem-aware containment, including not-yet-created descendants."""
    return location_is_within(_path_location(path), _path_location(root))


def paths_same(left: Path, right: Path) -> bool:
    # Containment both ways is equality of the canonical form: neither path can
    # be a strict ancestor of the other and still contain it.
    return _path_location(left) == _path_location(right)


def overlapping_layer_sources(layers: list):
    """The first resolved path shared by two precedence scopes."""
    sources = [(layer, located(layer_source_paths([layer]))) for layer in layers]
    return next(
        (
            (left_layer, left, right_layer, right)
            for index, (left_layer, left_paths) in enumerate(sources)
            for right_layer, right_paths in sources[index + 1 :]
            for left, left_at in left_paths
            for right, right_at in right_paths
            if locations_overlap(left_at, right_at)
        ),
        None,
    )


def layered_dir_files(layers: list, sub: str) -> dict:
    """The winning source for every file in one overlaid directory."""
    sources = {}
    for layer in layers:
        source_dir = layer / sub
        if not source_dir.is_dir():
            continue
        for source in sorted(source_dir.iterdir()):
            if source.is_file():
                sources[source.name] = source
    return sources


def layered_theme(layers: list) -> str:
    """One stylesheet whose source order is the layer precedence."""
    sources = [
        layer / "theme.css" for layer in layers if (layer / "theme.css").is_file()
    ]
    if not sources:
        sys.exit("the incoming layer has no theme.css")
    parts = []
    for source in sources:
        try:
            css = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            sys.exit(f"{source} must be UTF-8")
        if errors := css_syntax_errors(css, str(source)):
            sys.exit(errors[0])
        parts.append(css if css.endswith("\n") else css + "\n")
    return "".join(parts)


def cmd_init(page_dir: Path) -> None:
    # Before the directory exists there is no comments log for PageTransaction
    # to lock. This one external lease covers that missing first instant through
    # the complete vendoring, so two public inits cannot both observe freshness
    # and the earlier one cannot later erase the page the other created.
    path = init_lock_path(page_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(path), flocked(transition_lock(page_dir)):
        _init_page(page_dir)


def _init_page(page_dir: Path) -> None:
    service = read_json(page_dir / "service.json")
    server_live = lock_is_held(page_dir / "server.lock")
    if server_live or (service and service["enabled"]):
        sys.exit(
            f"cannot re-vendor {page_dir} while its service is enabled. "
            f"Run `leaf server stop {page_dir}` first."
        )
    # Successful init creates the append-only log's stable inode. A directory
    # the caller prepared is still a fresh page until that marker exists: it
    # keeps the caller's chosen mode, takes no PageTransaction yet, and a failed
    # validation leaves it untouched.
    fresh = not (page_dir / "comments.jsonl").is_file()
    sources = layer_dirs()
    page_target = page_dir.resolve()
    # Refuse a customization source before PageTransaction opens the page log:
    # this directory is not a page, and a rejected init must not put page state
    # inside the layer it was trying to protect.
    if source := next(
        (layer for layer in sources if path_is_within(page_target, layer)),
        None,
    ):
        sys.exit(
            f"{page_dir} is inside the widget-layer customization source "
            f"{source}, not a page directory"
        )
    if fresh:
        _vendor_page(page_dir, fresh=True, sources=sources, page_target=page_target)
        return
    # The init lease serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the vocabulary check
    # and contract commit one order against every browser append. No path takes
    # the page transaction and then the init lease, so this order cannot invert.
    with PageTransaction(page_dir):
        _vendor_page(page_dir, fresh=False, sources=sources, page_target=page_target)


def _vendor_page(
    page_dir: Path, *, fresh: bool, sources: list, page_target: Path
) -> None:
    # Re-vendoring is the one moment a page's vocabulary changes hands, so it is
    # where drift has to be caught: a tag or verb the new layer omits, or a
    # detail schema that no longer accepts an old payload, makes a recorded
    # action foreign on the first reload — the lost-decision bug reintroduced
    # through vocabulary drift instead of version-scoping.
    layers = checked_layers(sources)
    if overlap := overlapping_layer_sources(layers):
        left_layer, left, right_layer, right = overlap
        sys.exit(
            f"widget-layer sources {left_layer} and {right_layer} overlap "
            f"at {left} and {right}; layer scopes must be separate"
        )
    destinations = [
        *(page_target / name for name in VENDORED_FILES),
        *(page_target / sub for sub in ("versions", *VENDORED_DIRS)),
    ]
    located_destinations = located(destinations)
    if overlap := next(
        (
            (source, destination)
            for source, source_at in located(layer_source_paths(layers))
            for destination, destination_at in located_destinations
            if locations_overlap(source_at, destination_at)
        ),
        None,
    ):
        source, destination = overlap
        sys.exit(
            f"widget-layer source {source} overlaps page destination "
            f"{destination}; source and vendored page paths must be separate"
        )
    incoming = incoming_registry(layers)
    directory_sources = {sub: layered_dir_files(layers, sub) for sub in VENDORED_DIRS}
    missing_modules = sorted(
        tag
        for tag, entry in incoming.items()
        if tag.startswith("lf-")
        and entry["x-upgrade"]
        and f"{tag}.js" not in directory_sources["widgets"]
    )
    if missing_modules:
        sys.exit(
            "the incoming registry marks widgets as upgraded but their modules "
            "are missing:\n"
            + "\n".join(f"  - widgets/{tag}.js" for tag in missing_modules)
        )
    events = read_events(page_dir)
    gaps = vocabulary_gaps(page_dir, events, incoming)
    if gaps:
        sys.exit(
            "this page's log holds vocabulary the incoming layer no longer speaks:\n"
            + "\n".join(f"  - {g}" for g in gaps)
            + "\nre-vendoring would silently stop these replaying — the user's"
            " recorded decisions among them."
        )

    # Resolve and read the complete incoming layer before the first page write.
    # A bad late source must not leave the registry newer than the theme or its
    # modules.
    top_files = {"theme.css": layered_theme(layers).encode()}
    for name in VENDORED_FILES:
        if name == "registry.json" or name in top_files:
            continue
        source = next(
            (layer / name for layer in reversed(layers) if (layer / name).is_file()),
            None,
        )
        if source is None:
            sys.exit(f"the incoming layer has no {name}")
        top_files[name] = source.read_bytes()
    # `page init` is the contract transition, even when its input bytes happen to
    # match the last run. The browser carries this epoch on every write so an open
    # tab cannot post through a runtime whose server contract was re-vendored under it.
    generation = secrets.token_hex(16)
    incoming["$layer"] = {"generation": generation}
    runtime = top_files["leaf.js"]
    if runtime.count(LAYER_PLACEHOLDER) != 1:
        sys.exit(
            "the incoming leaf.js must contain exactly one layer-generation placeholder"
        )
    top_files["leaf.js"] = runtime.replace(
        LAYER_PLACEHOLDER, json.dumps(generation).encode()
    )
    # The registry makes the theme and modules live, so it commits last.
    top_files["registry.json"] = json_bytes(incoming)
    directory_files = {
        sub: {
            name: source.read_bytes() for name, source in directory_sources[sub].items()
        }
        for sub in VENDORED_DIRS
    }

    # Resolve every destination conflict before touching the page. A directory
    # where one vendored file belongs must not leave the top-level layer newer
    # than its modules.
    if (page_dir.exists() or page_dir.is_symlink()) and not page_dir.is_dir():
        sys.exit(f"{page_dir} must be a directory")
    directories = [page_dir / "versions"] + [page_dir / sub for sub in VENDORED_DIRS]
    for destination in directories:
        if destination.is_symlink():
            sys.exit(f"{destination} must be a real directory, not a symlink")
        if (
            destination.exists() or destination.is_symlink()
        ) and not destination.is_dir():
            sys.exit(f"{destination} must be a directory")
    file_targets = [
        *(page_dir / name for name in top_files),
        *(
            page_dir / sub / name
            for sub in VENDORED_DIRS
            for name in directory_files[sub]
        ),
    ]
    for target in file_targets:
        if (target.exists() or target.is_symlink()) and not target.is_file():
            sys.exit(f"{target} must be a file")

    # Owner-only when this call creates it: the directory holds the discussion
    # and service state whose URL carries the machine key. A directory the
    # caller already made keeps the mode they chose.
    if fresh:
        # A page's claim lives outside its directory. Recreating a deleted path
        # creates a new page, so it must not inherit the deleted page's owner.
        # Re-vendoring an existing page preserves that page and its claim.
        claim_path(page_dir).unlink(missing_ok=True)
    page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    (page_dir / "versions").mkdir(exist_ok=True)
    for sub in VENDORED_DIRS:
        (page_dir / sub).mkdir(exist_ok=True)
    # Stage the whole layer together. The registry is the declaration that
    # makes every other file live, so it is the final replacement.
    writes = [
        (page_dir / name, data, False)
        for name, data in top_files.items()
        if name != "registry.json"
    ]
    writes.extend(
        (page_dir / sub / name, data, False)
        for sub in VENDORED_DIRS
        for name, data in directory_files[sub].items()
    )
    writes.append((page_dir / "registry.json", top_files["registry.json"], False))
    replace_files(writes)

    for sub in VENDORED_DIRS:
        destination = page_dir / sub
        for stale in destination.iterdir():
            if stale.name not in directory_files[sub] and (
                stale.is_symlink() or stale.is_file()
            ):
                stale.unlink()
    if not (page_dir / "status.json").exists():
        # Fresh creation holds the init lease; re-vendoring holds both it and
        # the page transaction. Calling cmd_status would try to re-enter the
        # latter's comments-log flock for an existing directory missing status.
        write_json(
            page_dir / "status.json",
            {"state": "working", "detail": "Writing the page", "ts": now_iso()},
        )
    # The append-only log's stable inode is also the successful-init marker and
    # the page transaction lease. Publish it only after the layer and initial
    # status commit, so a failed first write still takes the fresh-init path.
    with open(page_dir / "comments.jsonl", "a", encoding="utf-8"):
        pass
    print(f"initialized {page_dir}")


CUSTOM_THEME = """\
/* Appended after Leaf's defaults by `page init`.
 * Override tokens for broad changes and selectors for specific elements. */
:root {
  /* --accent: #7c3aed; */
}
"""


def customization_dir(user: bool) -> Path:
    return config_home() if user else Path.cwd() / ".leaf"


def custom_theme_content(layer: Path) -> tuple:
    path = layer / "theme.css"
    if path.exists() or path.is_symlink():
        if not path.is_file():
            sys.exit(f"{path} must be a file")
        try:
            return path, path.read_text(encoding="utf-8"), True
        except UnicodeDecodeError:
            sys.exit(f"{path} must be UTF-8")
    return path, CUSTOM_THEME, False


def customization_protected_paths(layer: Path) -> list:
    """Resolved paths owned by every layer other than the selected write scope."""
    paths = []
    for source in layer_dirs():
        if source == layer:
            continue
        paths.append(source.resolve())
        if source.is_dir():
            paths.extend(layer_source_paths([source]))
    return paths


def refuse_customization_overlap(targets: list, protected: list) -> None:
    """Refuse a customization this scaffold would write over another layer's own source.

    Three callers ask, each about a different set of targets — the layer directory
    itself, the theme file, every file a widget scaffold stages — and the refusal is one,
    so it is stated here with the question rather than three times beside it."""
    located_protected = located(protected)
    overlap = next(
        (
            (target.resolve(), source)
            for target, target_at in located(targets)
            for source, source_at in located_protected
            if locations_overlap(target_at, source_at)
        ),
        None,
    )
    if overlap:
        target, source = overlap
        sys.exit(
            f"customization target {target} overlaps another layer source "
            f"{source}; customization scopes must be separate"
        )


def initialized_page_owning(path: Path):
    """The initialized page that owns path, if there is one."""
    resolved = path.resolve()
    at = _path_location(resolved)
    for root in (resolved, *resolved.parents):
        # Runtime state is disposable and regenerated; it cannot identify the
        # page whose owned paths this gate protects.
        if not (
            (root / "versions").is_dir()
            and all((root / name).is_file() for name in VENDORED_FILES)
            and all((root / name).is_dir() for name in VENDORED_DIRS)
        ):
            continue
        if (
            at == _path_location(root)
            or any(at == _path_location(root / name) for name in PAGE_OWNED_FILES)
            or any(
                location_is_within(at, _path_location(root / name))
                for name in PAGE_OWNED_DIRS
            )
        ):
            return root
    return None


def customization_page_overlap(paths: list):
    for path in paths:
        resolved = path.resolve()
        if page := initialized_page_owning(resolved):
            return resolved, page
    return None


def validate_customization_dir(layer: Path) -> list:
    if (layer.exists() or layer.is_symlink()) and not layer.is_dir():
        sys.exit(f"{layer} must be a directory")
    if layer.is_dir():
        checked_layers([layer])
    protected = customization_protected_paths(layer)
    selected = layer_source_paths([layer]) if layer.is_dir() else [layer]
    if overlap := customization_page_overlap(selected):
        target, page = overlap
        sys.exit(
            f"customization path {target} is owned by initialized page {page}; "
            "customization sources must stay separate from page-owned paths, "
            "then run `page init` to re-vendor the page"
        )
    refuse_customization_overlap(selected, protected)
    return protected


def cmd_customize_theme(user: bool) -> Path:
    layer = customization_dir(user)
    protected = validate_customization_dir(layer)
    path, css, exists = custom_theme_content(layer)
    refuse_customization_overlap([path], protected)
    if exists:
        print(f"using {path}")
        return path
    layer.mkdir(parents=True, exist_ok=True)
    replace_files([(path, css.encode(), True)])
    print(f"created {path}")
    return path


def custom_widget_entry(tag: str, upgrade: bool) -> dict:
    stem = tag.removeprefix("lf-")
    entry = {
        "description": f"A custom <{tag}> block.",
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "pattern": "^[a-z0-9][a-z0-9-]*$",
            }
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "prose",
        "x-upgrade": upgrade,
        "x-example": (
            f'<{tag} id="{stem}-example"><strong>Example</strong> '
            f"Replace this content.</{tag}>"
        ),
    }
    if upgrade:
        entry["x-verbatim"] = True
    return entry


def custom_widget_css(tag: str) -> str:
    return f"""\
/* <{tag}> */
{tag} {{
  display: block;
  margin: var(--sp-3) 0;
  padding: var(--sp-3);
  border: 1px solid var(--rule);
  border-radius: var(--r);
  background: var(--card);
  /* This box frames what it holds, so the room its outermost blocks reserve against
     neighbours they haven't got stops here rather than being painted as padding. Say
     it wherever a box draws an inset; theme.css states the trim once for every layer,
     and `version check --render` reports a box that shows more than it declared. */
  --lf-frame: 1;
}}
"""


def custom_widget_module(tag: str) -> str:
    return f"""\
// A widget module takes the helper surface /leaf.js exports, and no more.
// The contracts a module must honor (each is a norm in the shipped layer's
// skills/leaf/CLAUDE.md, learned by getting it wrong):
// - applyAction states an absolute placement, never a relative mutation —
//   replay applies it on every later version, and the sender's own action
//   must be a no-op. `version check --render` re-applies the standing state and
//   reports a widget that moves under it.
// - A slot that declares x-retired-when leaves the page when its holder settles,
//   and the layer renders the whole settlement: replay paints data-lf-state on the
//   holder and data-lf-retired on the retired slots, and one theme rule hides
//   them. This module owes only its own choreography — a fold, a control saying
//   what was decided (renderRetired paints the same state sooner on the sender's
//   own gesture). `version check --render` reads the result, and reports a settled
//   slot that shows words anyway, or a mark the log never decided.
// - Read your own slot with says(el), never textContent: the runtime's hidden
//   comment line lands inside widgets legitimately.
// - Anything you inject is chrome only if marked: offer() for a control,
//   relabel() for a label that is the page speaking. Unmarked injected words
//   read as the page's and break the file-side anchor reading.
// - The registry entry declares x-verbatim because this stub leaves the body
//   in place. Drop it the moment the module renders anything in the body's
//   stead, or quotes anchor on words the screen no longer shows.
// - Keys go through keys(el, title, rows) at upgrade, never at module load: one
//   declaration is the dispatch, the key line and the "?" reference, so a row
//   cannot say one key and answer another. Rows carry their own liveness (when),
//   so a control whose keys change with its state declares every state once and
//   calls paintKeys(); a row that presses must say a word for the line.
// - Before wiring any input that would carry an edit back, consult quoted():
//   an exhibited copy of this widget takes no input.
import {{ once }} from "/leaf.js";

customElements.define(
  "{tag}",
  class extends HTMLElement {{
    connectedCallback() {{
      if (!once(this)) return;
    }}
  }},
);
"""


def cmd_customize_widget(tag: str, user: bool, upgrade: bool) -> None:
    if re.fullmatch(WIDGET_NAME, tag) is None:
        sys.exit("widget tag must start with `lf-` and use lowercase kebab-case")

    layer = customization_dir(user)
    protected = validate_customization_dir(layer)
    registry_path = layer / "registry.json"
    # Every layer up to and including the write scope: a collision is checked
    # against what this scope's merge can see, and a project tag may shadow
    # nothing while a user tag may not collide with the shipped layers.
    all_layers = layer_dirs()
    registry_layers = all_layers[: all_layers.index(layer) + 1]
    checked_layers(registry_layers[:-1])
    for source_layer in registry_layers:
        source_path = source_layer / "registry.json"
        source_entries = read_registry_entries(source_path) or {}
        if tag in source_entries:
            sys.exit(f"<{tag}> already exists in {source_path}")

    widgets_dir = layer / "widgets"
    if (widgets_dir.exists() or widgets_dir.is_symlink()) and not widgets_dir.is_dir():
        sys.exit(f"{widgets_dir} must be a directory")
    module_path = layer / "widgets" / f"{tag}.js"
    if module_path.exists() or module_path.is_symlink():
        sys.exit(f"{module_path} already exists")

    entries = read_registry_entries(registry_path) or {}
    entries[tag] = custom_widget_entry(tag, upgrade)
    merged = {}
    for source_layer in registry_layers:
        source_entries = (
            entries
            if source_layer.resolve() == layer.resolve()
            else read_registry_entries(source_layer / "registry.json") or {}
        )
        merge_layer_entries(merged, source_entries)
    source = f"custom widget <{tag}>"
    validate_registry_examples(validate_registry(merged, source), source)

    theme_path, css, _ = custom_theme_content(layer)
    if css and not css.endswith("\n"):
        css += "\n"
    css += "\n" + custom_widget_css(tag)
    if errors := css_syntax_errors(css, str(theme_path)):
        sys.exit(errors[0])

    layer.mkdir(parents=True, exist_ok=True)
    writes = [(theme_path, css.encode(), True)]
    created = [registry_path, theme_path]
    if upgrade:
        writes.append((module_path, custom_widget_module(tag).encode(), False))
        created.append(module_path)
    # The registry is the declaration that makes the other files live, so it
    # commits last after every target has been staged.
    writes.append((registry_path, json_bytes(entries, indent=2), True))
    refuse_customization_overlap([path for path, _, _ in writes], protected)
    if upgrade:
        widgets_dir.mkdir(parents=True, exist_ok=True)
    replace_files(writes)
    print("custom widget scaffold:")
    for path in created:
        print(f"  {path}")


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


class LeafHTTPServer(ThreadingHTTPServer):
    """Every page leaf serves — a session server, a preview, a test's fixture —
    is served from here, so the suite drives the server the product answers on.

    The one thing it states is how deep the kernel may queue connections the
    accept loop has not reached yet. `socketserver` says five, and a queue that
    overflows does not hold the sixth caller back. Linux drops the handshake's
    last packet, the client posts into a connection this side has already
    forgotten, and the reset that comes back reaches the reader as a send that
    went nowhere. Five is reachable: test_concurrent_posts_never_tear_the_log
    sends twenty at once to ask about the append itself, and on an emulated
    Linux box a quarter of them were reset before the log was ever the
    question. Nothing here wants a shallower queue than the kernel will hold,
    so the number is the kernel's own."""

    request_queue_size = socket.SOMAXCONN


class DualStackHTTPServer(LeafHTTPServer):
    """For a bind with ":" in it. The stated-host wildcard is "::" with V6ONLY
    off, which answers IPv4 too (as ::ffff:...), so the URL is reachable
    whichever family the stated name resolves to; a derived IPv6 address just
    needs the family at all."""

    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def server_at(bind: str, port: int, handler) -> LeafHTTPServer:
    """A recorded bind, opened in a family this kernel actually has.

    A kernel with IPv6 switched off refuses AF_INET6 at the socket constructor,
    and the bind that asks for it is the stated-host wildcard — so `--host`, the
    one remedy the skill offers a reader who cannot reach the derived address,
    failed exactly where it is wanted: a headless box is where that address is
    loopback and no browser is local. `0.0.0.0` says what `::` says, every
    interface, in the family that is left, so the wildcard is restated rather
    than refused. Only the wildcard is: a literal v6 address has no reading in
    the other family, and answering it with every interface would widen the
    exposure the recorded address chose.

    The record keeps `::` either way. What a restart has to reproduce is the URL
    an open tab is polling, and that states the host and the port; which family
    carried it is this kernel's answer, asked again on the next serve."""
    if ":" not in bind:
        return LeafHTTPServer((bind, port), handler)
    try:
        return DualStackHTTPServer((bind, port), handler)
    except OSError as e:
        if e.errno != errno.EAFNOSUPPORT or bind != "::":
            raise
        return LeafHTTPServer(("0.0.0.0", port), handler)


def cmd_serve(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
) -> None:
    """Serve one initialized page under its durable service contract.

    Claiming is deliberately outside this process: server start claims before
    spawning it, server run claims at the CLI boundary, and a wait already owns
    the page it revives. This child only verifies that the matching claim still
    stands, then owns service.json and the server.lock process lease.
    """
    require_cross_process_locking()
    lease = None
    httpd = None
    with flocked(transition_lock(page_dir)), PageTransaction(page_dir) as page:
        service = read_json(page_dir / "service.json")
        if revive and (not service or not service["enabled"]):
            sys.exit("service was stopped; not reviving")

        identity = host_identity()
        claim = page.claim
        claimed = bool(
            not standing
            and identity is not None
            and claim is not None
            and claim["released"] is None
            and (claim["host"], claim["id"]) == (identity["host"], identity["id"])
        )
        if not standing and identity is not None and not claimed:
            sys.exit(
                f"this host session no longer owns {page_dir}; "
                "the server was not started"
            )
        if revive and service and service["lifetime"] == "session" and not claimed:
            sys.exit("this session no longer owns the service; not reviving")

        existing = running_server(page_dir)
        if existing:
            if host and urlsplit(existing["url"]).hostname != host.lower():
                sys.exit(
                    f"already serving at {existing['url']}; "
                    "leaf server stop first, then re-run with --host"
                )
            if standing and existing["lifetime"] != "standing":
                sys.exit(
                    f"already serving as a session server at {existing['url']}; "
                    "leaf server stop first, then re-run with --standing"
                )
            print(existing["url"], flush=True)
            print(lifetime_note(page_dir), file=sys.stderr, flush=True)
            return

        access = page_access(page_dir, host)
        token = host_key()
        base = 41000 + zlib.crc32(str(page_dir.resolve()).encode()) % 4000
        ports = [access["port"]] if "port" in access else [*range(base, base + 10), 0]
        lease = open(  # noqa: SIM115 - held until the server process exits
            page_dir / "server.lock", "a+b"
        )
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lease.close()
            winner = running_server(page_dir)
            if winner:
                print(winner["url"], flush=True)
                print(lifetime_note(page_dir), file=sys.stderr, flush=True)
                return
            sys.exit(f"another server run is serving {page_dir}; re-run")

        for port in ports:
            try:
                httpd = server_at(
                    access["bind"],
                    port,
                    handler_for(page_dir, token, protocol_version="HTTP/1.1"),
                )
                break
            except OSError as error:
                if error.errno == errno.EADDRINUSE and "port" not in access:
                    continue
                lease.close()
                sys.exit(
                    f"can't serve {page_dir} on {access['bind']}"
                    f"{':' + str(access['port']) if 'port' in access else ''}: "
                    f"{error}\nthat address is kept in "
                    f"{page_dir / 'service.json'}; delete that file to derive "
                    "the address again from this session, or re-run with "
                    "--host NAME."
                )

        lifetime = (
            "standing"
            if standing or access.get("lifetime") == "standing" or not claimed
            else "session"
        )
        service = {
            "host": access["host"],
            "bind": access["bind"],
            "port": httpd.server_address[1],
            "enabled": True,
            "lifetime": lifetime,
        }
        write_json(page_dir / "service.json", service)
        url = page_url(service["host"], service["port"], token)

    print(url, flush=True)
    print(lifetime_note(page_dir), file=sys.stderr, flush=True)
    threading.Thread(
        target=stop_when_service_ends,
        args=(page_dir,),
        daemon=True,
    ).start()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        lease.close()


def cmd_status(page_dir: Path, state: str, detail: str, handoff: bool = False) -> None:
    with PageTransaction(page_dir) as page:
        page.set_status(state, detail, handoff=handoff)


def start_server(
    page_dir: Path,
    host: str | None = None,
    standing: bool = False,
    revive: bool = False,
) -> tuple[str, str] | None:
    """Put the page's server up in a session of its own, and report where.

    The serve has to outlive this command — the browser polls it between turns
    and across every `leaf wait`, which exits to deliver — so it is spawned
    rather than held, and the one long-running command a leaf costs its session
    is the watcher. The module docstring carries the rest of that.

    `server run` in a session of its own is the whole mechanism. An explicit
    start may enable a stopped service; a revival carries the narrower intent
    "only if still enabled," which the child checks inside the transition.
    sys.executable is the resolved uv environment, so this skips uv.

    Returns where the page is and what ends it — the URL the child minted and
    the note for the lifetime it recorded — or None, having put the child's
    reason on stderr.
    """
    require_cross_process_locking()
    child = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "server",
            "_serve",
            str(page_dir),
            *(["--host", host] if host else []),
            *(["--standing"] if standing else []),
            *(["--revive"] if revive else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    # The child's own handshake, rather than a deadline over a file that may or
    # may not appear inside it: the service prints the URL once it holds the
    # record and the port, and otherwise exits having named its own reason — a
    # stale bind, a taken port, a flag the running server contradicts.
    url = child.stdout.readline().strip()
    if not url:
        print(
            child.stderr.read().strip() or f"the server for {page_dir} did not start",
            file=sys.stderr,
        )
        return None
    # Nothing drains the child's streams from here on, which is safe because the
    # URL and the note printed beside it are everything a server ever says — the
    # handler logs nothing (`log_message`) — so there is nothing left to write
    # into pipes this process closes on its way out.
    return url, lifetime_note(page_dir)


class PageTick(NamedTuple):
    """Where one page stands at one pass of the watch."""

    page_dir: Path
    status: dict
    batch: list
    live: bool
    watch_state: str
    lost: bool
    restarted: str | None
    transaction: PageTransaction


class Watch:
    """A session's watch, one locked page reading at a time.

    A tick yields while the page's log lock remains held. The caller decides how
    to deliver the batch before asking for the next tick, so claim transfer,
    SessionEnd, event arrival, delivery, and the handoff status have one order.
    A revival releases that transaction before waiting for the service
    transition, then rereads under a new transaction; no delivery snapshot
    crosses that unlocked interval.
    `watch_state` is ownership/lifetime; `lost` separately says the server is
    down with no restart left to make.
    """

    def __init__(self, identity: dict | None, named: Path | None = None):
        self.identity = identity
        self.session_id = identity["id"] if identity else None
        self.named = named
        self.lease_path = waiter_lease_path(named, identity)
        self.lease = None
        self._revived: set = set()
        self._lost: set = set()
        self._check_at: dict = {}

    def acquire(self) -> bool:
        """Take this carrier's exact liveness lease, idempotently."""
        if self.lease is not None or self.lease_path is None:
            return True
        self.lease = take_waiter_lease(self.lease_path)
        return self.lease is not None

    def pages(self) -> list:
        """Every page this session holds, re-read each pass, so a page served
        mid-watch joins it and a page another session picked up drops out.
        Naming one holds it in the set whatever the registry says — how a
        session picks up a leaf it didn't serve. A bare shell has no implicit
        ownership set, so it watches only a page explicitly named."""
        watched = owned_pages(self.session_id) if self.identity is not None else []
        named_at = None if self.named is None else _path_location(self.named)
        if named_at is not None and not any(
            _path_location(d) == named_at for d in watched
        ):
            watched.append(self.named)
        return watched

    def tick(self):
        """Yield each page while its ownership and delivery lock is held."""
        if self.lease_path is not None and self.lease is None:
            return
        for page_dir in self.pages():
            # This is only the account returned if ownership is already gone.
            # Every act uses the current reading under the lock below. Keeping
            # the harmless observation outside makes the lock boundary itself
            # testable: a claim or SessionEnd can win after page selection,
            # and _read must then decline every stale act.
            observed = read_json(page_dir / "status.json") or {"state": "idle"}
            try:
                with PageTransaction(page_dir) as page:
                    reading, revive = self._read(page, observed)
                    if not revive:
                        yield reading
                        continue
            except FileNotFoundError:
                # Discovery can race deletion; a missing marker is no page.
                continue

            started = start_server(page_dir, revive=True)
            key = str(page_dir)
            if started:
                self._revived.add(key)
                self._lost.discard(key)
            else:
                self._lost.add(key)

            # Ownership or status may have changed while the service transition
            # ran. Only this second transactional reading may be delivered.
            try:
                with PageTransaction(page_dir) as page:
                    reading, _ = self._read(page, observed)
                    if (
                        started
                        and reading.watch_state == "watching"
                        and reading.live
                        and not reading.lost
                    ):
                        reading = reading._replace(restarted=started[0])
                    yield reading
            except FileNotFoundError:
                continue

    def _read(self, page: PageTransaction, observed: dict) -> tuple[PageTick, bool]:
        """Read one page transaction and say whether revival is due."""
        page_dir = page.page_dir
        watch_state = page.watch_state(self.identity)
        status = observed if watch_state == "lost" else page.status
        live = status["state"] != "idle"
        batch = (
            unacknowledged(page.events, page.cursor) if watch_state != "lost" else []
        )
        service = read_json(page_dir / "service.json")
        enabled = bool(service and service["enabled"])
        key, now, revive = str(page_dir), time.time(), False
        # Desired service state owns revival. Status says what the page is doing;
        # it does not turn a deliberately disabled service back on.
        if watch_state == "watching" and live and not enabled:
            self._lost.add(key)
        elif watch_state == "watching" and live and now > self._check_at.get(key, 0):
            self._check_at[key] = now + 5
            if running_server(page_dir):
                # A server seen running earns the next death its own revival —
                # one attempt per death, so a server dying on arrival still
                # can't respawn every five seconds.
                self._revived.discard(key)
                self._lost.discard(key)
            elif key in self._revived:
                self._lost.add(key)
            else:
                revive = True
        elif watch_state != "watching" or not live:
            self._lost.discard(key)
            self._revived.discard(key)
        return (
            PageTick(
                page_dir,
                status,
                batch,
                live,
                watch_state,
                key in self._lost,
                None,
                page,
            ),
            revive,
        )

    def release(self) -> None:
        """Release this carrier's liveness proof, however it ended."""
        if self.lease is not None:
            self.lease.close()
            self.lease = None


def cmd_wait(page_dir: Path | None = None) -> int:
    """Hold until a user speaks or a worker reports, and deliver what was said.

    One watcher covers the session. The watch set is every page the session
    holds, re-read each pass, so a page served mid-wait joins the running watch
    without a second command, and a page another session has since picked up
    drops out on its own. Naming PAGE claims it first — how a session picks up
    a leaf it didn't serve — and holds it in the set, which is also the whole
    set outside a host session (a bare shell, the tests). A batch is one page's
    events, so its first line names the page, and `leaf ack` goes back to that
    page. The JSON envelope says nothing about what consumes it. The wait owner
    advances the cursor only after the complete batch reaches that next durable
    consumer.

    A wait ends on someone speaking, on the last watched leaf ending, or on a
    server being down with no restart to make. It puts no clock on how long a
    user takes, because there is no such measurement to take from this side of
    the wire: a page whose address their browser can't route to and one they
    simply haven't opened yet look identical at every length, so a deadline over
    it announces the first while describing the second — and the second is the
    ordinary case. Only their browser can tell them apart, and the user holds
    the URL from the turn that handed it over, so the report comes from them;
    references/serving-pages.md's "Unreachable URLs and `--host`" carries the
    recourse."""
    if page_dir is not None:
        claim_page(page_dir)
    identity = host_identity()
    watch = Watch(identity, named=page_dir)
    if not watch.acquire():
        target = "this session" if identity else str(page_dir)
        print(f"another `leaf wait` is already active for {target}", file=sys.stderr)
        return 2
    try:
        while True:
            readings = []
            live = []
            for reading in watch.tick():
                readings.append(reading)
                if reading.watch_state == "lost":
                    if page_dir is not None and paths_same(reading.page_dir, page_dir):
                        print(
                            f"stopped watching {page_dir}: this session no longer owns it",
                            file=sys.stderr,
                        )
                        return 2
                    continue
                if reading.live:
                    live.append(reading)
                if reading.restarted:
                    print(
                        f"{reading.page_dir}: server had died; "
                        f"restarted at {reading.restarted}",
                        file=sys.stderr,
                        flush=True,
                    )
                # The batch outranks the page's state: a wait already holding
                # events owes them to the agent whatever became of the leaf, so
                # an idled page still delivers here — it just no longer holds
                # the wait open below.
                if reading.batch:
                    # Whose events follow, said in-band: no event line names its
                    # page, and the ack has to go back to the right one.
                    print(jsonl_line({"page": str(reading.page_dir)}), flush=True)
                    for event in reading.batch:
                        print(jsonl_line(event), flush=True)
                    if reading.status["state"] != "working":
                        # Flip before the agent handles the batch: the handoff
                        # gap between this exit and pickup must not show
                        # "waiting". The tick still holds the page lock, so a
                        # transfer cannot land between delivery and this claim.
                        n = len(reading.batch)
                        reading.transaction.set_status(
                            "working",
                            f"picking up {n} update{'s' if n != 1 else ''}",
                            handoff=True,
                        )
                    return 0
                if reading.lost:
                    print(
                        f"{reading.page_dir}: server is not running; restart it with "
                        f"`leaf server start {reading.page_dir}`",
                        file=sys.stderr,
                    )
                    return 2
            # A leaf the agent idled has nobody left to carry a comment to, so it
            # leaves the watch, and the last one gone ends the wait too.
            if not live:
                if not readings:
                    print(
                        "nothing to watch: no page named and none claimed by "
                        "this session",
                        file=sys.stderr,
                    )
                    return 2
                one = len(readings) == 1
                names = ", ".join(str(r.page_dir) for r in readings)
                print(
                    f"the {'leaf' if one else 'leaves'} ended; {names} "
                    f"{'is' if one else 'are'} idle",
                    file=sys.stderr,
                )
                return 2
            time.sleep(1)
    finally:
        watch.release()


def cmd_ack(page_dir: Path, seq: int) -> None:
    """Acknowledge through one event of a complete wait batch that reached delivery.

    The target must be something `leaf wait` prints — a user event or a
    worker's report. This catches a mistyped sequence and prevents an agent from
    advancing the cursor to a trailing log entry it never saw. Writing only when
    the cursor advances makes retries harmless.
    """
    with PageTransaction(page_dir) as page:
        events = page.events
        # By the seq the event carries, never by its position in the list. A seq
        # is a line number and read_events skips what it can't read, so the two
        # coincide only on a log nothing tore.
        target = next((e for e in events if e["seq"] == seq), None)
        if target is None:
            end = events[-1]["seq"] if events else 0
            sys.exit(f"event {seq} does not exist; the log ends at {end}")
        if target["author"] != "user" and target["kind"] not in ("report", "error"):
            sys.exit(f"event {seq} is not a user event, a report, or a page error")
        if seq > page.cursor:
            write_json(page_dir / "cursor.json", {"seq": seq})


def read_text_arg(text) -> str:
    body = text if text is not None else sys.stdin.read()
    if not body.strip():
        sys.exit("empty text (pass --text or pipe via stdin)")
    return body.strip()


class ThreadStructure(NamedTuple):
    ids: set
    by_id: dict
    fragments: dict


def thread_structure(events: list) -> ThreadStructure:
    """Parse each logged markup fragment once into the panel's id universe."""
    ids, by_id, fragments = set(), {}, {}
    for e in events:
        if markup := e.get("markup"):
            fragment = parse_structure(markup)
            fragments[e["id"]] = fragment
            ids.update(fragment.ids)
            by_id.update(fragment.by_id)
    return ThreadStructure(ids, by_id, fragments)


def detail_error(schema: dict, detail: dict):
    """The first schema complaint about an event's detail payload, or None —
    ordered so which one speaks doesn't depend on validator iteration order."""
    error = min(Draft202012Validator(schema).iter_errors(detail), key=str, default=None)
    return error.message if error else None


def event_record_error(contract: dict, event: dict, browser: bool = False):
    """The first complaint from one event kind's stored-record contract."""
    schema = contract["record"]
    instance = event
    if browser:
        # Supply the fields the server and reader add so the full record schema
        # can validate the unstamped request beside its browser assertions.
        schema = {"allOf": [schema, contract["browser"]]}
        instance = {
            **event,
            "id": "browser",
            "ts": "browser",
            "author": "page" if event.get("kind") == "error" else "user",
            "seq": 1,
        }
    return detail_error(schema, instance)


def declared_event_error(
    event: dict, tag: str, registry: dict, kind: str, channel: str
):
    """Why a known widget's verb or detail violates one declared channel."""
    entry = registry.get(tag)
    if entry is None:
        return (
            f"registry no longer declares <{tag}> for {kind} widget {event['widget']!r}"
        )
    declared = entry.get(channel, {})
    spec = declared.get(event["action"])
    if spec is None:
        return f"<{tag}> does not declare {kind} verb {event['action']!r}" + (
            f"; it declares {sorted(declared)}" if kind == "report" and declared else ""
        )
    if message := detail_error(spec["detail"], event["detail"]):
        return f"<{tag}> {kind} {event['action']!r} detail is invalid: {message}"
    return None


def action_contract_error(
    event: dict, page_by_id: dict, thread: ThreadStructure, registry: dict
):
    """Why a structurally complete action violates its sending widget's contract."""
    # Page widgets come from the action's own published version. Thread widgets
    # inhabit the panel's other live document. Either record answers both which
    # tag sent the action and whether it stands inside an exhibit.
    rec = page_by_id.get(event["widget"]) or thread.by_id.get(event["widget"])
    if rec is None:
        return (
            f"unknown action widget {event['widget']!r} in v{event['version']} "
            "or agent-authored thread markup"
        )
    tag = rec["tag"]
    if error := declared_event_error(event, tag, registry, "action", "x-state"):
        return error
    # The exhibit rule at the door, not only in the shipped runtime's
    # sendAction: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the reader
    # made on quoted material. Any sender the key admits reaches this door.
    if quoted_in(rec, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
    return None


def report_contract_error(event: dict, page_by_id: dict, registry: dict):
    """Why a structurally complete report violates its widget's declaration —
    the CLI door's mirror of the POST door's action_contract_error. Page markup
    only, never a reply's: a report has to be answerable, and thread markup is
    frozen in the log, so no version could ever absorb or overrule one made
    there."""
    rec = page_by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return (
            f"unknown report widget {event['widget']!r} in v{event['version']} — "
            "reports name page widgets only; thread markup is frozen, so no "
            "version could ever answer a report made there"
        )
    return declared_event_error(event, tag, registry, "report", "x-report")


def version_ids(page_dir: Path) -> set:
    ids = set()
    for version in list_versions(page_dir):
        ids |= parse_version(page_dir, version).ids
    return ids


def reserved_ids_error(ids: list) -> str:
    """The one sentence for an authored id in the runtime's own namespace, shared by the
    version lint and the thread-markup one — page ids and a reply's are one universe, so
    what keeps both clear of the runtime's is one rule. leaf.js coins document ids
    under `lf-` (`lf-composer-quote`) and points ARIA at them, so an authored id there
    redirects the reference to the page."""
    return (
        "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, "
        f"and points ARIA at them): {ids}"
    )


def reserved_marker_errors(parser) -> list:
    """The same trespass as a reserved id, for the runtime's other markers: it
    writes data-lf-* and the .lf-chrome/.lf-live/.lf-copy classes as its own
    record and reads them back, so an authored copy makes it misread the page —
    words inside .lf-chrome leave every reading, data-lf-gen words become cells
    the file-side reading has no fence for."""
    return [
        f"<{tag}> at line {line} wears the runtime's own markers "
        f"({', '.join(markers)}); the page may not author what the runtime "
        "reads back as its own record"
        for tag, line, markers in parser.reserved_markers
    ]


def id_errors(parser) -> list:
    """What a parsed page's own names must not do: repeat, or trespass on the runtime's
    own namespace — its ids, and its markers. One reader, because the two gates that ask
    are asking the same thing of the same parser: a version, and a catalog example, which
    is markup an author writes from. Written twice, the second gate is the one that goes
    on not asking whatever the first one learns to."""
    errors = []
    if parser.duplicate_ids:
        errors.append(
            f"duplicate ids (anchors need unique targets): {parser.duplicate_ids}"
        )
    if parser.reserved_ids:
        errors.append(reserved_ids_error(parser.reserved_ids))
    return errors + reserved_marker_errors(parser)


def thread_markup_contract_errors(parser, registry: dict) -> list:
    """Registry-derived errors shared by admission and re-vendoring."""
    errors = fragment_errors(parser, registry)
    settled = retirement_slots(registry)
    errors.extend(
        f"<{rec['tag']}> is a settlement holder, but thread markup is frozen in "
        "the log and no version could ever settle it; put the change in the next "
        "version instead"
        for rec in parser.lf_elements
        if rec["tag"] in settled
    )
    return errors


def check_markup(page_dir: Path, kind: str, markup: str, events: list) -> None:
    """A message's widget markup, validated against the vendored registry at post
    time — the discussion-side `version check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no gate at all — the runtime renders it with every tag
    escaped, so it cannot claim a widget. Exits with what's wrong."""
    registry = require_registry(page_dir)
    frag = parse_structure(markup)
    errs = thread_markup_contract_errors(frag, registry)
    if errs:
        sys.exit(
            f"{kind} markup doesn't validate:\n" + "\n".join(f"  - {e}" for e in errs)
        )
    if not frag.lf_elements:
        sys.exit("--markup carries no widget; put prose in --text")
    if frag.duplicate_ids:
        sys.exit(
            f"{kind} widget markup reuses an id within itself: {frag.duplicate_ids}"
        )
    if frag.reserved_ids:
        sys.exit(f"{kind} widget markup takes " + reserved_ids_error(frag.reserved_ids))
    if marker_errors := reserved_marker_errors(frag):
        sys.exit(f"{kind} widget markup: " + "; ".join(marker_errors))
    clash = sorted(frag.ids & (version_ids(page_dir) | thread_structure(events).ids))
    if clash:
        sys.exit(
            f"{kind} widget ids already taken by the page or an earlier message: {clash}"
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
def cmd_publish(page_dir: Path, version: int, text) -> None:
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
        if cmd_check(page_dir, version, transition_held=True) != 0:
            sys.exit(
                f"refusing to publish {name}: leaf version check failed (issues above)"
            )
        html = path.read_text(encoding="utf-8")
        registry = load_registry(page_dir)
        events = page.events
        projection, parser, spk = page_projection(html, events, registry, version)
        retracts = sorted(parser.restated)
        byid = parser.by_id
        answered = []
        for (_widget, unit, _facet), reports in projection.reports.items():
            last, spec = reports[-1]
            if unit in parser.overruled or markup_facet(
                unit, spec, byid, spk, registry
            ) == folded_facet(last, spec):
                answered.extend(report["id"] for report, _ in reports)
        event = {
            "kind": "note",
            "author": "claude",
            **message_identity(),
            "version": version,
            "text": body,
        }
        if retracts:
            event["restated"] = retracts
        if answered:
            event["reports"] = sorted(answered)
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


CATALOG_PREAMBLE = """\
# Widget vocabulary, vendored for this page — `version check` validates against it.
#
# Widgets are lf-* elements in the authored HTML; attributes carry scalars
# (enums, flags), children carry prose, and an item's title is a leading
# <strong> child. Every lf-* element takes an explicit end tag — never
# <lf-foo/>. Ids are authored (lowercase kebab), unique, stable across
# versions. Each entry is JSON Schema over the attributes, plus the x- keys
# that say how the layer treats the tag — what each of those means is printed
# after the entries ($keys).
"""


# The layer-wide facts printed after the widget entries, each with the sentence saying
# what an author reads it for. A table because the catalog is the agent's own
# documentation of a vocabulary that grows: a `$` key a layer adds is a row here, not a
# block of its own beside six that already say the same thing differently. $events is
# absent because it is the vocabulary stamp — what this page's runtime speaks, for
# `page init` to hold a re-vendor against — and nothing an author writes markup from.
CATALOG_FACTS = (
    ("$keys", "The x- keys an entry may declare, and what each one means."),
    (
        "$restated",
        "`restated` — the one attribute that spans widgets; read it before revising one.",
    ),
    ("$state", "x-state's fields — the facet, fold unit, and record forms."),
    ("$report", "x-report's fields — how a version answers a standing report."),
    ("$awaits", "x-awaits' fields — when an instance asks, and what answers it."),
    (
        "$languages",
        "The languages this page colors, in a code block's class or an x-language attribute.",
    ),
    ("$tones", "The tones this page's layer paints, on any x-tone attribute."),
    (
        "$idioms",
        "Theme idioms — shapes the theme styles directly; no registry entry, no JS.",
    ),
)


def cmd_catalog(page_dir: Path) -> None:
    reg = require_registry(page_dir)
    print(CATALOG_PREAMBLE)
    print(
        json.dumps(
            {k: v for k, v in reg.items() if not k.startswith("$")},
            indent=2,
            ensure_ascii=False,
        )
    )
    for key, heading in CATALOG_FACTS:
        if fact := reg.get(key):
            print(f"\n# {heading}\n")
            print(json.dumps(fact, indent=2, ensure_ascii=False))


def cmd_page_state(page_dir: Path) -> None:
    """Where the page stands, as one JSON object — the agent-side twin of the
    browser's /api/state, folded rather than raw. /api/state ships the log and
    lets the runtime replay it; a session picking a page up owes the same
    reading, and doing it in-head over `leaf events` is how a standing decision
    gets missed. So this prints the readings the runtime derives, from the same
    constructions it derives them with: the published markup's elements, the
    projection of the user's standing state and the reports standing on the agent
    channel, where the record lags either (`record_lag_entries`), the open asks
    on the page and in threads (the banner's own count), the comment threads,
    and presence beside what answers for it. Computed on demand from the log,
    the version, and the registry — nothing here is stored, so there is no
    second copy of the truth to reconcile.

    Every markup-derived reading is of the latest *published* version, because
    that is the page the user sees and acts on; a written draft shows up in
    `versions.written` and nowhere else."""
    events = read_events(page_dir)
    registry = require_registry(page_dir)
    published = published_versions(page_dir, events)
    written = list_versions(page_dir)
    pres = presence(page_dir, events)
    # The published page's readings, up front and through the one construction
    # (page_projection) every consumer of declared state reads, so the threads
    # settle against the same page the projection was built over rather than no page.
    parser, projection, spk = None, None, {}
    if published:
        html = version_path(page_dir, published[-1]).read_text(encoding="utf-8")
        projection, parser, spk = page_projection(html, events, registry, published[-1])
    threads = build_threads(events, spk)
    state = {
        "page": str(page_dir),
        "title": "",
        "versions": {"published": published, "written": written},
        **pres,
        # The watcher's number where `pending` is the reader's: everything a
        # wait would still print, workers' reports included.
        "unacked": len(unacknowledged(events, pres["cursor"])),
        "server": running_server(page_dir),
        "elements": [],
        "state": [],
        "reports": [],
        "asks": [],
        "threads": [
            {
                "id": t["root"]["id"],
                "anchor": t["root"].get("anchor"),
                "text": t["root"]["text"],
                # Who closed it, or null for a thread still open — the reading a
                # session picking the page up acts on, since a thread an agent
                # closed is one the reader may never have answered.
                "resolved": t["resolved"] and t["resolved"]["author"],
                "messages": len(t["msgs"]),
            }
            for t in threads.values()
        ],
        "lag": [],
    }
    if published:
        byid = parser.by_id
        state["title"] = parser.title.strip()
        state["elements"] = [
            {"tag": r["tag"], "id": r["attrs"].get("id"), "line": r["line"]}
            for r in parser.lf_elements
        ]
        state["state"] = [
            {
                "widget": widget,
                "unit": unit,
                "facet": facet,
                "action": e["action"],
                "detail": e["detail"],
                "version": e["version"],
                "seq": e["seq"],
            }
            for (widget, unit, facet), (e, _) in sorted(projection.actions.items())
        ]
        state["reports"] = [
            {
                "widget": widget,
                "unit": unit,
                "facet": facet,
                "action": e["action"],
                "detail": e["detail"],
                "version": e["version"],
                "seq": e["seq"],
                "agent": e.get("agent"),
                "standing": len(standing),
            }
            for (widget, unit, facet), standing in sorted(projection.reports.items())
            for e, _ in [standing[-1]]
        ]
        # An ask standing in a slot the log has retired — a group inside the lf-new
        # of a rejected suggestion — left the page with the slot, so it is nobody's
        # to answer; the passage reading already knows which ids a decision dropped.
        passages = page_passages(
            html, registry, decisions(projection.actions, registry)
        )
        state["asks"] = page_asks(
            parser,
            projection,
            byid,
            spk,
            registry,
            set(passages.retired) | set(passages.gone),
        )
        state["lag"] = record_lag_entries(projection, byid, spk, registry)
    elif written:
        state["title"] = parse_version(page_dir, written[-1]).title.strip()
    state["asks"] += thread_asks(
        events, registry, {rid for rid, t in threads.items() if t["resolved"]}
    )
    print(json.dumps(state, indent=2, ensure_ascii=False))


def cmd_stop(page_dir: Path) -> str:
    """Disable the desired service and wait until its process lease is released."""
    require_cross_process_locking()
    with flocked(transition_lock(page_dir)):
        service = read_json(page_dir / "service.json")
        live = lock_is_held(page_dir / "server.lock")
        if service and service["enabled"]:
            write_json(page_dir / "service.json", {**service, "enabled": False})
        if live:
            # The serving process observes disabled desired state and exits.
            # Taking its lease is the barrier proving every socket is closed.
            with open(page_dir / "server.lock", "a+b") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX)
            return "stopped server"
    return "no server running"


# ---------- hook: the loop, enforced rather than remembered ----------


def unanswered_asks(events: list, cursor: int) -> list:
    """The comments this session took delivery of and left with no answer under
    them.

    Acknowledging is what takes a comment off the batch, so an acknowledged one
    nobody answered has passed the last gate that could have caught it: the
    watcher keeps no memory of it, and re-delivery reads the same cursor. The
    reader is left looking at a question with nothing under it, and the agent
    believes the batch is dealt with.

    What it looks for is a thread whose last word is the reader's. Not a thread
    nobody but the reader has ever spoken in: the browser posts the reader's
    follow-ups as `reply` events of their own, so under that reading one agent
    message anywhere in a thread answers it forever, and a follow-up — "but why
    not C?" — acknowledged and answered in the terminal is this very bug played
    again one level down, with the gate reading green. The agent's own ask needs
    no case of its own either way round: the last word there is the agent's
    until the reader answers, and once they answer in-thread it is theirs.

    Reading the last speaker rather than the whole cast means a thread that
    needs no answer — "great, ship it" — holds a turn until the agent replies or
    runs `leaf resolve`. That is the direction to err in. Both failures are
    invisible from the browser, so the question is who can see each: a thread
    left standing over a reader's last word is visible to nobody, while "does
    this one need an answer" is a question the agent is holding the context to
    settle, and settling it costs one command.

    The log alone, with no reading of the page: `build_threads` is told there is
    no published page to settle against, which is the one thing this reader may
    not ask for. Reading the page means loading the page's vendored registry,
    and that load is a gate — a page vendored before the layer last changed
    fails it by design. Every other caller may raise on that; this one is
    reached from the Stop hook, which fails open, so a raise here would stand
    the whole guard down on any page a little older than the code, watch clause
    included, and say nothing. What the log alone costs is that a pick retracted
    by a floor on one of its parts, rather than on the widget it named, still
    reads as settling its thread — an ask that goes unmentioned, never a turn
    blocked over an answer the reader already gave.
    """
    return [
        t["root"]
        for t in build_threads(events, {}).values()
        # The cursor is read against the last word, not the root: a follow-up
        # past it is a delivery the agent has yet to take, which is the
        # unacknowledged clause's to report and not this one's.
        if t["msgs"][-1]["author"] == "user"
        and t["msgs"][-1]["seq"] <= cursor
        and not t["resolved"]
    ]


def unattended_pages(session_id: str) -> list:
    """The pages this session owes something, each with what to do about it.
    Two invariants hold between turns. A page is watched or idle, so anything
    else has quietly stopped listening. And every comment the session has taken
    delivery of has an answer under it, since acknowledging is what takes one
    off the batch and nothing delivers it again."""
    reasons = []
    for page_dir in owned_pages(session_id):
        page_reasons = []
        try:
            events = read_events(page_dir)
            state = full_state(page_dir, events, published_versions(page_dir, events))
        except FileNotFoundError:
            continue
        codex = state["host"] == "codex"
        # Asked of every page, watched or not, and ahead of the watch question
        # below: a watcher cannot deliver a comment the cursor has already
        # passed, so a live wait is no answer to this one.
        stale = unanswered_asks(events, state["cursor"])
        if stale:
            ids = ", ".join(t["id"] for t in stale)
            page_reasons.append(
                f"{page_dir}: {len(stale)} acknowledged "
                f"comment{'s' if len(stale) != 1 else ''} with no answer "
                f"({ids}). " + ANSWER_ASK_INSTRUCTION
            )
        # A live Claude `leaf wait` is the watch, and it prints what's pending on
        # its own. Reporting the page here would start a second waiter and print
        # the same unacknowledged events twice.
        if not (state["listening"] and not codex):
            # The watcher's whole batch — user events and workers' reports — not the
            # reader-facing count, which deliberately leaves reports out.
            n = len(unacknowledged(events, state["cursor"]))
            if n:
                if codex and state["listening"]:
                    remedy = (
                        "Poll the existing `leaf wait` unified-exec session with "
                        "`write_stdin`."
                    )
                elif codex:
                    remedy = (
                        "Start `leaf wait` in unified exec, retain its session id, "
                        "and poll it with `write_stdin`."
                    )
                else:
                    remedy = "`leaf wait` prints them."
                remedy += (
                    f" {ACK_BATCH_INSTRUCTION} If this task is the consumer, then address "
                    "every event."
                )
                page_reasons.append(
                    f"{page_dir}: {n} update{'s' if n != 1 else ''} you haven't picked up. "
                    + remedy
                )
            elif state["status"]["state"] != "idle":
                if codex and state["listening"]:
                    page_reasons.append(
                        f"{page_dir}: the Codex page is still live. Keep this turn "
                        "active and poll the existing `leaf wait` unified-exec "
                        "session with `write_stdin`."
                    )
                elif codex:
                    page_reasons.append(
                        f"{page_dir}: no watcher. Start `leaf wait` in unified exec, "
                        "retain its session id, and keep this turn active while polling it with "
                        "`write_stdin`; or run `leaf status <page> idle` if the page "
                        "is done."
                    )
                else:
                    page_reasons.append(
                        f"{page_dir}: no watcher. Start `leaf wait` as a background "
                        "task — one wait covers every page this session holds — or "
                        "run `leaf status <page> idle` if the page is done."
                    )
        # Discovery is only a candidate read. Transfer can happen while the
        # hook reads status, so decide against current ownership at the end.
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim and claim["id"] == session_id:
                    reasons.extend(page_reasons)
        except FileNotFoundError:
            continue
    return reasons


def cmd_hook(payload: dict) -> None:
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if event == "SessionEnd":
        for page_dir in owned_pages(sid):
            try:
                with PageTransaction(page_dir) as page:
                    claim = page.claim
                    # A successor that arrived after discovery remains current.
                    # SessionEnd releases only ownership provenance: status is
                    # authored work state, while service.json and the service
                    # reaper own process lifetime.
                    if claim and claim["released"] is None and claim["id"] == sid:
                        page.release_claim()
            except FileNotFoundError:
                continue
        return
    # stop_hook_active means this hook already blocked once and Claude is running
    # again on the strength of it; blocking a second time is how a hook loops.
    # A block naming two debts and answered on one therefore ends the turn with
    # the other standing — the guard is a nudge per stop, not a barrier. What
    # carries the rest is UserPromptSubmit, which reads the same reasons, so the
    # debt opens the next turn rather than waiting for its end.
    if event == "Stop" and payload.get("stop_hook_active"):
        return
    reasons = unattended_pages(sid)
    if not reasons:
        return
    # The message avoids "unattended": a page can be watched and still be owed
    # an answer, and the runtime spends that word on a different fact — a page
    # served to nobody at all.
    message = (
        "leaf — a page of this session's has something outstanding:\n"
        + "\n".join(f"- {r}" for r in reasons)
    )
    if event == "Stop":
        print(json.dumps({"decision": "block", "reason": message}))
    else:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": message,
                    }
                }
            )
        )


# ---------- check: deterministic pre-handover lint ----------

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
# Elements whose end tag HTML lets you omit — leaving one "unclosed" is valid,
# so the balance check must not flag them (only genuinely-open structural
# elements like <div>/<section> point at a real layout bug).
OPTIONAL_END = {
    "p",
    "li",
    "dd",
    "dt",
    "td",
    "th",
    "tr",
    "thead",
    "tbody",
    "tfoot",
    "option",
    "optgroup",
    "caption",
    "colgroup",
    "rp",
    "rt",
    "html",
    "head",
    "body",
}
# A start tag on the left implicitly closes matching open elements on the right.
P_CLOSERS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "details",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hgroup",
    "hr",
    "main",
    "menu",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}
# …and closes its own kind: a start tag ends the open siblings it can't nest inside.
SIBLING_CLOSERS = {
    "li": ("li",),
    "dt": ("dt", "dd"),
    "dd": ("dt", "dd"),
    "td": ("td", "th"),
    "th": ("td", "th"),
    "tr": ("td", "th", "tr"),
    "thead": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "tbody": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "tfoot": ("td", "th", "tr", "thead", "tbody", "tfoot"),
    "option": ("option",),
    "optgroup": ("option", "optgroup"),
}


# How a plain code block names its language, matching leaf.js's own pattern. The
# class is the universal one every Markdown renderer emits, so a block Claude wrote
# elsewhere lands here unchanged.
LANGUAGE_CLASS = re.compile(r"(?:^|\s)language-([\w+.#-]+)(?=\s|$)")

# Container selectors whose max-width defines the readable column.
COLUMN_SELECTORS = (
    "main",
    "body",
    "article",
    ".container",
    ".wrap",
    ".content",
    ".page",
)


def _names_column(selector: str) -> bool:
    """Whether a rule's selector names one of the column containers — as a selector
    component, not a substring. Matched as text, `.domain-list` contained "main" and
    one unrelated rule redefined the column every element was measured against; a
    component is the word standing as the compound's type selector or as a whole
    class, with nothing of an identifier continuing it."""
    for part in re.split(r"[,\s>+~]+", selector):
        for sel in COLUMN_SELECTORS:
            if sel.startswith("."):
                if re.search(rf"{re.escape(sel)}(?![\w-])", part):
                    return True
            elif re.match(rf"{sel}(?![\w-])", part):
                return True
    return False


COLUMN_FALLBACK = 780
# Attribute widths only count as pixels on these elements.
PIXEL_WIDTH_TAGS = {"img", "svg", "table", "canvas", "iframe", "video", "object"}

# Blocks a user predictably points at whole rather than quoting: a run of code,
# a table, a figure, an aside set off from the prose — and the sections
# references/page-authoring.md holds to "Stable anchors". Widgets aren't listed
# because the
# registry's schemas already demand ids wherever pointing at one matters.
POINTABLE_TAGS = {"section", "article", "aside", "pre", "table", "figure"}
# Where an aim that found no tighter id has escaped to: naming one of these is
# naming most of the page.
SECTIONING_TAGS = {"section", "article", "main", "body"}
# The properties that overflow a column when pinned in pixels. max-width defines the
# column instead, so it is read there and never counted here.
OVERFLOW_PROPS = ("width", "min-width")
# Page-level declarations the runtime reads from <meta name="lf-*"> in the head,
# name → allowed content values (None = free-form). A misspelled name or value
# would silently declare nothing in the browser, so `version check` owns this
# vocabulary the way the registry owns lf-* elements.
LF_META = {"lf-review": frozenset({"sign-off"})}
# The one CSP every page declares, required by `version check` the way the one
# script tag is. The vendoring promise — an approved page can't change under its
# user, and can't phone home — held by convention until the browser enforced it:
# a vendored module or an inline handler could fetch any origin. 'self' is the
# page directory whole; data: admits the images `version export` inlines; the
# theme arrives inline in a <style> on export, hence 'unsafe-inline' for styles
# (scripts stay 'self'-only, which is what matters). Verified over the gallery —
# every widget, mermaid and the tokenizer included — before it was required.
PAGE_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
# Non-painting document structure that may stand outside the authored main. Head
# metadata is allowed only while the parser is actually inside head; the canonical
# module is also allowed beside main because shipped pages use both placements.
DOCUMENT_WRAPPERS = {"html", "head", "body", "main"}
HEAD_METADATA_TAGS = {"base", "link", "meta", "script", "style", "title"}


def implicit_closes(open_tags: list, tag: str) -> int:
    """How many elements at the top of an open-element stack this start tag closes,
    under HTML's optional-end-tag rules. Two parsers walk the same documents — the
    structure lint and the passage reader — and `version check` accepts an omitted
    </p>, so a tree they disagreed about would be a passage one of them puts in the
    wrong section."""
    closed = 0
    if tag in P_CLOSERS:
        while closed < len(open_tags) and open_tags[-1 - closed] == "p":
            closed += 1
    siblings = SIBLING_CLOSERS.get(tag, ())
    while closed < len(open_tags) and open_tags[-1 - closed] in siblings:
        closed += 1
    return closed


class _StructParser(HTMLParser):
    """Tracks a tag stack to catch unclosed and mismatched tags, and collects what the
    rest of `version check` reads off a version: element ids and the widget each
    stands in, every <script src> tag, stylesheet links, each lf-* element
    (attributes, direct parent, direct children, direct text) for registry
    validation, the page's title, and everything it says about width. Structure
    only — no tag here is known by name, so every question about what a widget
    *means* is asked of the registry by whoever holds one. Foreign markup inside
    <svg> is skipped (SVG has its own self-closing rules that don't matter here)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, lineno, lf_record | None, id | None)
        self.errors = []
        self.all_ids = []
        # {attrs, parent, early_head} per external asset. Applicability and placement
        # belong to the asset record: parallel lists made one fact several
        # representations and let a later parser edit silently misalign them.
        self.external_scripts = []
        self.stylesheets = []
        self.lf_metas = []  # {"name", "content", "line"} for <meta name="lf-*">
        self.http_equivs = []  # {"equiv", "content", "line"} per http-equiv meta
        # The authored page lives under one direct body > main because that is the
        # element the first-replay presentation boundary withholds. Both assets that
        # establish that boundary belong in head; anything paintable outside main would
        # stand outside it.
        self.body_lines = []
        self.head_elements = []  # (line, direct child of html)
        self.main_elements = []  # (line, direct child of body)
        self.outside_main = []  # paintable content with no main ancestor
        # /media/ paths any attribute points at, so the check that the file is
        # there reads references and not mentions: a page documenting leaf
        # writes one of these paths in prose, and a raw scan of the markup
        # would send its author hunting for a screenshot nothing asks for.
        self.media_refs = set()
        # What the version says about width, each where a document says it: CSS is
        # what a <style> block holds, and a fixed width is what a rule, a style="" or
        # a width="" states. The column check reads these three and nothing else.
        self.css = ""
        self.inline_styles = []  # each style="" declaration list
        self.attr_widths = []  # (tag, value) per width="" that counts as pixels
        self.title = ""  # what <title> says, for the transcript's heading
        # {"tag", "line", "attrs", "parent", "children", "text"}
        self.lf_elements = []
        # id → the innermost lf-* element standing around it, an element's own id
        # standing in itself. Where an id lives is structure; which of those
        # elements is a slot a decision retires and which the widget holding it is
        # the registry's word, read by whoever has one (`retirement_holders`), so
        # what a version's outcome licenses is worked out without this parse
        # knowing a widget by name.
        self.within = {}
        # {"tag", "parent", "lang", "line"} per element claiming a language — the
        # coloring the runtime honors on a plain <pre><code>, checked here because a
        # class it doesn't honor is a request that silently isn't answered.
        self.language_blocks = []
        # {"tag", "line", "under"} per id-less occurrence of a pointable block,
        # with the nearest open ancestor carrying an id — (tag, id) or None — so
        # unpointable_blocks can judge where a user's aim would land.
        self.bare_blocks = []
        # (tag, line, markers) per element wearing the runtime's own record:
        # a data-lf-* attribute, or one of the classes that answer "which
        # document is this" (.lf-chrome), "this is the live region" (.lf-live),
        # "this is a copy" (.lf-copy). The runtime writes these and reads them
        # back, so an authored copy makes it misread the page it stands on —
        # authored words inside .lf-chrome leave the reading position and every
        # quote, and data-lf-gen words become fenced cells the file's reading
        # has no fence for.
        self.reserved_markers = []
        self._svg_depth = 0

    @property
    def ids(self) -> set:
        return set(self.all_ids)

    @property
    def by_id(self) -> dict:
        """id → its element record, for every id-bearing lf-* element."""
        return {r["attrs"]["id"]: r for r in self.lf_elements if r["attrs"].get("id")}

    @property
    def restated(self) -> set:
        """Ids this version declares it has rewritten, retracting whatever the
        user had recorded on them."""
        return {
            rec["attrs"]["id"]
            for rec in self.lf_elements
            if rec["attrs"].get("id") and "restated" in rec["attrs"]
        }

    @property
    def overruled(self) -> set:
        """Ids this version declares it keeps its own state on, over a worker's
        standing report — the agent channel's mirror of `restated`."""
        return {
            rec["attrs"]["id"]
            for rec in self.lf_elements
            if rec["attrs"].get("id") and "overruled" in rec["attrs"]
        }

    @property
    def duplicate_ids(self) -> list:
        seen, dupes = set(), set()
        for i in self.all_ids:
            (dupes if i in seen else seen).add(i)
        return sorted(dupes)

    @property
    def reserved_ids(self) -> list:
        """Ids that trespass on the runtime's own namespace (see reserved_ids_error)."""
        return sorted({i for i in self.all_ids if i.startswith("lf-")})

    def _implicit_close(self, tag):
        for _ in range(implicit_closes([t for t, *_ in self.stack], tag)):
            self.stack.pop()

    def _open_widget(self):
        """The innermost lf-* element still open, or None outside every one."""
        return next(
            (record for _, _, record, _ in reversed(self.stack) if record), None
        )

    def _harvest(self, tag, attrs_d):
        if attrs_d.get("id"):
            self.all_ids.append(attrs_d["id"])
            # An lf-* element's own id stands in the element itself, which
            # handle_starttag writes over this the moment the record exists.
            self.within[attrs_d["id"]] = self._open_widget()
        if tag == "script" and attrs_d.get("src"):
            self.external_scripts.append(
                {
                    "attrs": attrs_d,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "early_head": bool(self.head_elements)
                    and self.head_elements[-1][1]
                    and not self.body_lines,
                }
            )
        if tag == "link" and "stylesheet" in (attrs_d.get("rel") or ""):
            self.stylesheets.append(
                {
                    "attrs": attrs_d,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "early_head": bool(self.head_elements)
                    and self.head_elements[-1][1]
                    and not self.body_lines,
                }
            )
        if tag == "meta" and (attrs_d.get("name") or "").startswith("lf-"):
            self.lf_metas.append(
                {
                    "name": attrs_d["name"],
                    "content": attrs_d.get("content"),
                    "line": self.getpos()[0],
                }
            )
        if tag == "meta" and attrs_d.get("http-equiv"):
            self.http_equivs.append(
                {
                    "equiv": attrs_d["http-equiv"],
                    "content": attrs_d.get("content"),
                    "line": self.getpos()[0],
                }
            )
        if attrs_d.get("style"):
            self.inline_styles.append(attrs_d["style"])
        if tag in PIXEL_WIDTH_TAGS and attrs_d.get("width"):
            self.attr_widths.append((tag, attrs_d["width"]))
        markers = sorted(name for name in attrs_d if name.startswith("data-lf-"))
        markers += sorted(
            {"lf-chrome", "lf-live", "lf-copy", "lf-ui"}
            & set((attrs_d.get("class") or "").split())
        )
        if markers:
            self.reserved_markers.append((tag, self.getpos()[0], markers))
        self.media_refs.update(
            v for v in attrs_d.values() if v and v.startswith(f"/{MEDIA_DIR}/")
        )

    def _attributes(self, tag, attrs):
        """The browser's attribute reading: first value wins, duplicates are invalid."""
        values = {}
        duplicates = set()
        for name, value in attrs:
            if name in values:
                duplicates.add(name)
            else:
                values[name] = value
        if duplicates:
            self.errors.append(
                f"<{tag}> at line {self.getpos()[0]} has duplicate attribute "
                f"names {sorted(duplicates)}; HTML keeps the first value"
            )
        return values

    def _record_outside_main(self, tag):
        """Record markup Chrome can paint without crossing the authored main."""
        ancestors = {open_tag for open_tag, *_ in self.stack}
        if "main" in ancestors or tag in DOCUMENT_WRAPPERS:
            return
        if "head" in ancestors and tag in HEAD_METADATA_TAGS:
            return
        self.outside_main.append(f"<{tag}> at line {self.getpos()[0]}")

    def handle_starttag(self, tag, attrs):
        attrs_d = self._attributes(tag, attrs)
        # The browser renders neither: template content parses into an inert
        # fragment and noscript stays text in any scripting browser, while the
        # file's reading would take both for the page's words — so a comment
        # could anchor on words no reader ever sees. Nothing in the vocabulary
        # has a use for markup the page won't render; refuse it at the door
        # instead of teaching every reading to look away.
        if tag in ("template", "noscript"):
            self.errors.append(
                f"<{tag}> at line {self.getpos()[0]}: the browser renders none of "
                "its content; write it plainly or leave it out"
            )
        self._harvest(tag, attrs_d)
        if tag == "svg":
            self._record_outside_main(tag)
            self._svg_depth += 1
            self.stack.append((tag, self.getpos()[0], None, attrs_d.get("id")))
            return
        if self._svg_depth:  # don't tag-balance inside SVG
            return
        # Before the void check: <hr> is void and closes an open <p>, and a void tag
        # left inside a paragraph it ended puts the rest of the section in it.
        self._implicit_close(tag)
        parent = self.stack[-1][0] if self.stack else None
        if tag == "head":
            self.head_elements.append((self.getpos()[0], parent == "html"))
        if tag == "body":
            self.body_lines.append(self.getpos()[0])
        if tag == "main":
            self.main_elements.append((self.getpos()[0], parent == "body"))
        self._record_outside_main(tag)
        # After it, so the parent recorded here is the one the browser will see.
        lang = LANGUAGE_CLASS.search(attrs_d.get("class") or "")
        if lang:
            self.language_blocks.append(
                {
                    "tag": tag,
                    "parent": self.stack[-1][0] if self.stack else None,
                    "lang": lang.group(1),
                    "line": self.getpos()[0],
                }
            )
        if tag in POINTABLE_TAGS and not attrs_d.get("id"):
            self.bare_blocks.append(
                {
                    "tag": tag,
                    "line": self.getpos()[0],
                    "under": next(
                        ((t, i) for t, _, _, i in reversed(self.stack) if i), None
                    ),
                }
            )
        if tag in VOID_TAGS:
            if self.stack and self.stack[-1][2] is not None:
                self.stack[-1][2]["children"].append(tag)
            return
        if self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)
        record = None
        if tag.startswith("lf-"):
            record = {
                "tag": tag,
                "line": self.getpos()[0],
                "attrs": attrs_d,
                "parent": self.stack[-1][0] if self.stack else None,
                "children": [],
                "text": False,
                "body": "",  # a <pre> data body's text, for the x-lines gate
                # The nearest enclosing lf element's record, so a child's line
                # reference (x-lines) can find the data body it points into, and
                # so a reading with the registry to hand can walk out of a slot
                # to the widget whose decision retires it.
                "holder": self._open_widget(),
            }
            self.lf_elements.append(record)
            if attrs_d.get("id"):
                self.within[attrs_d["id"]] = record
        self.stack.append((tag, self.getpos()[0], record, attrs_d.get("id")))

    def handle_startendtag(self, tag, attrs):
        # <foo/> — self-closing; still harvest but never pushed. Outside SVG the
        # slash is a trap on any non-void tag: HTML ignores it, the element stays
        # open in a browser and swallows the rest of its parent, so from here on
        # this parser's tree and the browser's would diverge. Reject the form
        # outright rather than model a tree the user's page won't have.
        attrs_d = self._attributes(tag, attrs)
        self._harvest(tag, attrs_d)
        if self._svg_depth:  # SVG has real self-closing syntax
            return
        self._record_outside_main(tag)
        if tag not in VOID_TAGS:
            self.errors.append(
                f"<{tag}/> at line {self.getpos()[0]} is self-closing: HTML ignores "
                f"the slash and the element would swallow what follows — write "
                f"<{tag} …></{tag}>"
            )
        elif self.stack and self.stack[-1][2] is not None:
            self.stack[-1][2]["children"].append(tag)

    def handle_data(self, data):
        ancestors = {open_tag for open_tag, *_ in self.stack}
        holder = self.stack[-1][0] if self.stack else None
        if (
            data.strip()
            and "main" not in ancestors
            and holder not in {"script", "style", "title"}
        ):
            self.outside_main.append(f"text at line {self.getpos()[0]}")
        if self.stack and self.stack[-1][2] is not None and data.strip():
            self.stack[-1][2]["text"] = True
        if holder == "style":
            self.css += data
        elif holder == "title":
            self.title += data
        elif holder == "pre" and len(self.stack) > 1 and self.stack[-2][2] is not None:
            # A data body: the <pre> directly under an lf element, collected for
            # the x-lines gate to count lines against.
            self.stack[-2][2]["body"] += data

    def handle_endtag(self, tag):
        if tag == "svg":
            while self.stack and self.stack[-1][0] != "svg":
                self.stack.pop()
            if self.stack:
                self.stack.pop()
            self._svg_depth = max(0, self._svg_depth - 1)
            return
        if self._svg_depth or tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                orphaned = [
                    (t, ln)
                    for t, ln, *_ in self.stack[i + 1 :]
                    if t not in OPTIONAL_END
                ]
                if orphaned:
                    unclosed = ", ".join(f"<{t}> (line {ln})" for t, ln in orphaned)
                    self.errors.append(
                        f"</{tag}> at line {self.getpos()[0]} closes over unclosed: {unclosed}"
                    )
                del self.stack[i:]
                return
        if tag not in OPTIONAL_END:
            self.errors.append(
                f"stray </{tag}> at line {self.getpos()[0]} with no matching open tag"
            )


def parse_structure(markup: str) -> _StructParser:
    """One structural reading of a document or fragment — fed and closed, so
    every reader gets the flushed parse rather than each restating the ritual."""
    parser = _StructParser()
    parser.feed(markup)
    parser.close()
    return parser


_versions = {}  # version file -> (its stamp, the structural reading of it)


def parse_version(page_dir: Path, version: int) -> _StructParser:
    """One structural reading per published version file.

    `version publish` writes a version and nothing writes it again, while the
    readings that cost most are the ones a reader waits through: the action door
    checks a press against the version it was made on, and every poll reads each
    live neighbour's newest version for the one string the board shows of it. That
    last one made a title cost a parse of the whole page, once a second, per
    neighbour — seven neighbours put more time between a press and its paint than
    everything else the server did for it put together."""
    path = version_path(page_dir, version)
    stamp = file_stamp(path)
    if stamp and (held := _versions.get(path)) and held[0] == stamp:
        return held[1]
    parser = parse_structure(path.read_text(encoding="utf-8"))
    if stamp:
        _versions[path] = (stamp, parser)
    return parser


def version_review_mode(page_dir: Path, version: int):
    """The review ask declared by a published version, or None for comments only."""
    parser = parse_version(page_dir, version)
    return next(
        (meta["content"] for meta in parser.lf_metas if meta["name"] == "lf-review"),
        None,
    )


# ---------- passages: the text an anchor points at ----------
# The runtime resolves an anchor against the DOM; `leaf comment` writes one down
# against the file. The two have to read the same page or the anchor lands somewhere it
# was never made, so this mirrors leaf.js's capture rather than approximating it:
# the same skip list, the same block-boundary space, the same collapse, the same caps.
#
# What the file cannot know is what a widget's module will write, and the registry is
# where that is declared rather than guessed at per widget. Three keywords carry what
# can be declared, and a fence carries the rest:
#
#   x-says      attribute values the reader sees. renderSaid puts them in the DOM, so
#               they go in here too, at the edge the registry names.
#   x-verbatim  an upgraded element whose body reaches the reader as its own words
#               (lf-draft renders the authored text into a plain div, deliberately
#               unmarked so anchoring can see it). Without it, an upgraded element is
#               opaque: a mermaid body is a picture by the time it is read.
#   x-retired-when  the outcome under which this element leaves the page: a decided
#               suggestion's losing slot. The browser builds its anchor pass's skip
#               list from this key too (`quotable` in leaf.js), so a reading given
#               the log's outcomes drops here exactly what drops there — and a widget
#               whose decision leaves nothing showing goes with its slots (settledAway
#               there, `gone` here). Its values are also the vocabulary's decision
#               verbs, which is where `decisions` reads them from.
#   x-state, record kind "body"  the verb whose detail text becomes this element's
#               body once the user sends one (lf-draft's `edit`): replay writes
#               the newest surviving one into the DOM verbatim (applyAction is
#               absolute), so a reading given the fold's word (rewritten_bodies)
#               holds their words in the authored body's place. It asks nothing of
#               the browser, whose page already shows the text this substitutes.
#
# A module writes between the children of the element it upgrades — a column's heading, a
# milestone's chips, a diff's gutters — so an opaque element and each of its children is
# fenced. A quote never spans a fence, which turns "the page has words here that the file
# doesn't" from an anchor that silently detaches in the user's browser into a refusal
# at the moment it is written, addressed to the one party who can still fix it.
#
# Retirement drops and rewriting substitutes rather than fencing, because that is what
# each leaves on the screen. A fence says the reading doesn't know what stands there, and
# in both of these it knows exactly.
#
# x-paints is the key that writes into an upgraded element and belongs in none of this.
# Its word is clipped to nothing and marked as the runtime's (.lf-quiet, .lf-ui), so the
# browser's own reading of the page skips it exactly as this one never sees it: the two
# readings agree by both being silent, and a fence would be room reserved for words no
# reader on either side can reach.

# The collapse class, stated outright: the characters a whitespace run is made of, one
# spelling the set and the regex both derive from, matching leaf.js's COLLAPSE exactly.
# JS's \s and Python's str.isspace() disagree at the edges — U+FEFF is whitespace to JS
# alone, U+0085 and U+001C–001F to Python alone — and a page carrying one of those in
# prose read differently on the two sides, so a `leaf comment` quote could be written
# against text the browser never produces. The browser is the producer of every captured
# quote, so its set is the one both sides speak.
COLLAPSE_CHARS = frozenset(
    "\t\n\x0b\x0c\r \u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
COLLAPSE = re.compile("[" + re.escape("".join(sorted(COLLAPSE_CHARS))) + "]+")


def collapse(text: str) -> str:
    """One space per whitespace run, none at the edges — the reading every quote and
    facet comparison uses, the browser's quoteFrom in Python."""
    return COLLAPSE.sub(" ", text).strip(" ")


# What a text node's "block" resolves to, matching the runtime's TEXT_BLOCK: one space
# goes wherever two runs of text sit in different blocks, and none where they share one,
# so `<p>a</p><p>b</p>` reads "a b" and `set<em>up</em>` reads "setup".
TEXT_BLOCK_TAGS = {
    "p",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "td",
    "th",
    "pre",
    "blockquote",
    "dd",
    "dt",
    "figcaption",
    "summary",
}
# Text no anchor can reach. script/style are the anchor pass's own skip list; head is
# outside the tree it searches at all, the runtime rooting a section-less anchor at
# document.body — without it a page's <title> would be quotable and land nowhere.
UNQUOTABLE_TAGS = {"script", "style", "head"}
# How much of the surrounding text an anchor stores to tell two identical passages
# apart, as leaf.js captures it. The quote itself is stored whole, however long the
# passage: it is the extent the page marks, and a cap on it was a comment quietly made
# on less than was quoted (leaf.js, above selectionAnchor).
CONTEXT = 24


class _PassageParser(HTMLParser):
    """A version's prose as the anchor pass reads it. `text` is the whole page collapsed
    the way a captured quote is; `owner[i]` is the ids enclosing text[i], outermost
    first, so a match can name the section it fell in and be re-read within it.

    `decided` is the accept/reject each suggestion stands under (`decisions`).
    A decision retires a slot — the registry's `x-retired-when` names which outcome —
    and the browser's anchor pass reads the same key (`quotable` in leaf.js), so
    this reading drops it the same way. A decision that leaves its
    widget with nothing — a deletion accepted, an insertion refused — empties the
    wrapper too (`gone`), because an element showing nothing is one nobody can point
    at, however present its markup. `rewrites` is the user's
    standing text per element whose registry entry records a verb as the body
    (`rewritten_bodies`): their words stand in the authored body's place, because
    replay writes exactly that into the DOM. Without either, the reading is the
    version as authored — every slot pending, every body Claude's.

    close() deliberately does not unwind the stack. An element still open at EOF
    would lose its `_close` work — the x-says tail, a `gone` verdict — but those
    attach only to lf-* elements, and every path into this reading is gated on
    `structure_errors`, which refuses any lf-* left open (versions at check and
    publish, thread fragments at their own door, prev_html by the published-note
    filter). The tags legitimately open at EOF (p, li, body, html) lose nothing
    in `_close`. A guard here would defend a state no gated input reaches."""

    def __init__(self, registry=None, decided=None, rewrites=None):
        super().__init__(convert_charrefs=True)
        self.registry = registry or {}
        self.decided = decided or {}
        self.rewrites = rewrites or {}
        self.text = ""
        self.owner = []  # per character: the tuple of enclosing ids
        self.fences = set()  # indices a quote may not span
        self.retired = {}  # id under a retired slot → the suggestion whose decision did it
        self.rewritten = {}  # id whose body the user rewrote → the verb that did it
        self.gone = {}  # decided id whose decision left it empty → the outcome that did it
        self.shown = {}  # id whose data body this reading withheld → the words in it
        # id → the ids enclosing it, outermost first, itself last. Structure, not
        # words: an element is somewhere on the page whether or not it says
        # anything, which is what the containment questions downstream ask (see
        # `spoken`). Written for every id the markup carries, since a widget's
        # detail may name one the page holds outside the vocabulary.
        self.enclosing = {}
        self.bearing = (
            set()
        )  # ids still showing something: text under them, or a surviving child
        self.stack = []  # [{"tag", "id", "ids", "skip", "shows", "sub", "opaque", "fenced", "retired_by", "tb", "block", "tail"}]
        self._uid = 0
        self._block = None  # the block the last character came from
        self._space = False  # a separator waiting for a character to follow it

    def _fresh(self) -> int:
        self._uid += 1
        return self._uid

    def _write(self, data: str, block: int, ids: tuple) -> None:
        """Text into the collapsed run, one space per whitespace run and none leading."""
        if data.strip():
            self.bearing.update(ids)
        if self.text and block != self._block:
            self._space = True
        self._block = block
        for ch in data:
            if ch in COLLAPSE_CHARS:
                self._space = bool(self.text)
                continue
            if self._space:
                self.text += " "
                self.owner.append(ids)
                self._space = False
            self.text += ch
            self.owner.append(ids)

    def _fence(self) -> None:
        """Words may stand here that this reading knows nothing about. Recorded as a
        position rather than written into the text, so `text` stays the page's own words
        and no quote can be built out of one."""
        self.fences.add(len(self.text))

    def _said(self, frame: dict, values: list) -> None:
        # renderSaid puts each value in its own <span>, so each is its own block wherever
        # the widget sits outside a text block — the same rule, applied to the span.
        for value in values:
            self._write(
                value, frame["tb"] if frame["tb"] else self._fresh(), frame["ids"]
            )

    def _close(self, frame: dict) -> None:
        """Everything an element's end does, whether it was written or inferred — an
        omitted </p> inside a widget still ends what the element was saying."""
        if not frame["skip"]:
            self._said(frame, frame["tail"])
        if frame["fenced"]:
            self._fence()
        # A decided element closing with nothing shown left the page with its decision:
        # a deletion accepted, an insertion refused. Everything it held is either a
        # retired slot or silent, so there is nothing on screen for an anchor to reach.
        if (
            frame["id"] in self.decided
            and not frame["skip"]
            and frame["id"] not in self.bearing
        ):
            self.gone[frame["id"]] = self.decided[frame["id"]]

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        # Before the void check, unlike the structure lint's: <hr> is both void and a
        # paragraph closer, and text after it is in a different block.
        for _ in range(implicit_closes([f["tag"] for f in self.stack], tag)):
            self._close(self.stack.pop())
        parent = self.stack[-1] if self.stack else None
        # Recorded before the void check, and before anything asks what this element
        # shows: where an element sits is a fact about the markup, so an image, an
        # opaque widget and a slot a decision retired each answer it like any other.
        ids = (parent["ids"] if parent else ()) + (
            (attrs_d["id"],) if attrs_d.get("id") else ()
        )
        if attrs_d.get("id"):
            self.enclosing[attrs_d["id"]] = ids
        if tag in VOID_TAGS:
            return
        entry = self.registry.get(tag) or {}
        # The innermost open text block, if any: the runtime's `closest(TEXT_BLOCK)`.
        tb = (
            self._fresh()
            if tag in TEXT_BLOCK_TAGS
            else (parent["tb"] if parent else None)
        )
        # A module may write anywhere inside the element it upgrades, unless the registry
        # says the body reaches the reader as its own words.
        opaque = bool(entry.get("x-upgrade") and not entry.get("x-verbatim"))
        # A slot a decision retired: its words left the page with the outcome the
        # registry names, and everything under it goes too. Looked up by the parent's
        # own id — the same child-of-suggestion shape as the browser's selector.
        retired_by = (parent["retired_by"] if parent else None) or (
            parent["id"]
            if parent
            and entry.get("x-retired-when")
            and self.decided.get(parent["id"]) == entry["x-retired-when"]
            else None
        )
        # A wall this element raises itself: its words are off the reader's page, whatever
        # holds it. Named apart from the inherited half below because the two answer
        # different questions — an element under a withheld data body is still showing
        # its words, and one under a retired slot is not.
        own_wall = bool(
            retired_by
            or tag in UNQUOTABLE_TAGS
            or "lf-ui" in (attrs_d.get("class") or "").split()
        )
        # Silenced from above: the element shows nothing of its own, so a rewrite of
        # its body has nothing to stand in for — an edited draft inside a slot the
        # user accepted away left the page with the slot.
        silenced = bool((parent and parent["skip"]) or own_wall)
        # A surviving child keeps its parent on the page even where it holds no text —
        # a kept slot whose only content is an image. The text case marks every
        # enclosing id in _write.
        if parent and not silenced:
            self.bearing.add(parent["id"])
        # A body the user rewrote. `rewritten_bodies` already resolved the verb
        # through this element's x-state, so an id in the dict is the whole test:
        # the fold decides, this pass only applies.
        sub = self.rewrites.get(attrs_d.get("id")) if not silenced else None
        # The element whose data body this reading is withholding, carried down to
        # everything under it. The page shows whatever its module made of that body, so a
        # quote landing inside one is told where it landed rather than told the page never
        # said it — a claim wider than this reading can make. Only where the body still
        # stands: a retired or rewritten one is `retired`/`rewritten`'s to answer for, and
        # each of those names the act that did it.
        shows = (
            None
            if own_wall or sub is not None
            else (parent["shows"] if parent else None)
            or (
                attrs_d.get("id")
                if opaque and entry.get("x-content") == "data"
                else None
            )
        )
        frame = {
            "tag": tag,
            "id": attrs_d.get("id"),
            "ids": ids,
            "skip": silenced
            or sub is not None
            or (opaque and entry.get("x-content") == "data"),
            "shows": shows,
            "sub": sub,
            "retired_by": retired_by,
            "opaque": opaque,
            "fenced": opaque or bool(parent and parent["opaque"]),
            "tb": tb,
            # …and where there is none, the element is its own text node's parent, which
            # is what the runtime falls back to. Fresh per element, so `a<em>b</em>c`
            # under a <div> reads as three blocks and under a <p> as one.
            "block": tb if tb else self._fresh(),
            "tail": [],
        }
        # Each x-says value at the edge of the element's own words, in registry order,
        # which is where renderSaid puts it and where a pseudo-element stood before it.
        head = []
        for attr, edge in (entry.get("x-says") or {}).items():
            value = attrs_d.get(attr)
            if value is None:
                continue
            (head if edge == "before" else frame["tail"]).append(value)
        if frame["fenced"]:
            self._fence()
        if retired_by and frame["id"]:
            self.retired[frame["id"]] = retired_by
        self.stack.append(frame)
        if not frame["skip"]:
            self._said(frame, head)
        elif sub is not None:
            # The body's own write path, so a quote across the element's edge sees
            # the same adjacency the screen shows — no fence, nothing withheld.
            verb, their_text = sub
            self._write(their_text, frame["block"], frame["ids"])
            self.rewritten[frame["id"]] = verb

    def handle_data(self, data):
        frame = self.stack[-1] if self.stack else None
        if not frame:
            return
        if not frame["skip"]:
            self._write(data, frame["block"], frame["ids"])
        elif frame["shows"]:
            self.shown[frame["shows"]] = self.shown.get(frame["shows"], "") + data

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                # Innermost first, so an element closing over unclosed children ends them
                # in the order they were opened in.
                while len(self.stack) > i:
                    self._close(self.stack.pop())
                return

    def close(self):
        super().close()
        # An element still open at EOF owes its close all the same: a frame never
        # closed loses its `gone` verdict and its trailing x-says values. `version
        # check` refuses unbalanced markup, but this parser also reads `prev_html`
        # and fragments that never passed that gate.
        while self.stack:
            self._close(self.stack.pop())


class Passages(NamedTuple):
    """A version's words, and what a search over them needs to know."""

    text: str  # collapsed the way a captured quote is
    owner: list  # per character: the tuple of enclosing ids, outermost first
    fences: set  # indices a quote may not span: where a module may write
    retired: dict  # id under a retired slot → the suggestion whose decision did it
    rewritten: dict  # id whose body the user rewrote → the verb that did it
    gone: dict  # decided id whose decision left it empty → the outcome that did it
    shown: dict  # id whose data body this withheld → the words a module shows there
    enclosing: dict  # id → the ids enclosing it, outermost first, itself last


def page_passages(html: str, registry=None, decided=None, rewrites=None) -> Passages:
    parser = _PassageParser(registry, decided, rewrites)
    parser.feed(html)
    parser.close()
    return Passages(
        parser.text,
        parser.owner,
        parser.fences,
        parser.retired,
        parser.rewritten,
        parser.gone,
        # Collapsed the way `text` is, so one comparison answers for both.
        {id: collapse(words) for id, words in parser.shown.items()},
        parser.enclosing,
    )


def section_span(owner: list, section: str):
    """The half-open range of characters inside `section`, or None when the version has
    no such element with text in it. An element is contiguous in document order, so its
    characters are too — which is what lets a search be scoped by slicing."""
    inside = [i for i, ids in enumerate(owner) if section in ids]
    return (inside[0], inside[-1] + 1) if inside else None


class Spoken(NamedTuple):
    """What one element says, and where it sits."""

    words: str  # the words under it, as the anchor pass reads them
    within: tuple  # the ids enclosing it, outermost first, itself last


# An id this version doesn't carry — nothing said, and nowhere it sits. An element
# that is here and silent is not this: it has a chain, which is what lets a fold
# reach a card holding one diagram.
EMPTY = Spoken("", ())


def spoken(html: str, registry: dict) -> dict:
    """id → Spoken, for every element the version carries.

    This is the version's own reading of itself, so it is `page_passages` sliced by
    id rather than a second walk: chrome skipped, x-says attributes counted (a
    picked option's `effort` is a word on the page now, so changing it changes what
    the user decided about), whitespace collapsed the way a captured quote is.
    Asking whether two versions still say the same thing has to mean the same text a
    user could have selected, or the question is about something else.

    `section_span` answers this for one id by scanning the page; every id at once is
    that same scan, done once.

    The two halves come from different readings because they are different facts,
    and taking both off the character scan cost the second one. Words are what the
    scan holds. Where an element *sits* is structure, so it comes from the parser's
    record of what was open — and an element that says nothing is somewhere all the
    same. Keyed on words, an image-only option and a card holding one diagram were
    in no chain at all, so `action_rests_on` dropped them from what an action rests
    on where the browser's `restsOn` keeps them (a floor stopped replaying on one
    side only), and `markup_facet` read a version that honoured a pick on such an
    option as showing no pick, which is the state gate refusing the very version
    that agreed with the user."""
    p = page_passages(html, registry)
    first, last = {}, {}
    for i, ids in enumerate(p.owner):
        for wid in ids:
            first.setdefault(wid, i)
            last[wid] = i
    # Stripped: the separator `_write` puts between blocks lands inside whichever
    # element the next block opens, so a slice can start or end on one. It marks a
    # boundary rather than saying anything.
    said = {wid: p.text[lo : last[wid] + 1].strip() for wid, lo in first.items()}
    return {wid: Spoken(said.get(wid, ""), chain) for wid, chain in p.enclosing.items()}


def enclosing_section(owner: list, lo: int, hi: int):
    """The innermost id enclosing every character of [lo, hi) — the runtime's
    `closest("[id]")` on the passage's common ancestor."""
    first, last = owner[lo], owner[hi - 1]
    shared = 0
    while shared < min(len(first), len(last)) and first[shared] == last[shared]:
        shared += 1
    return first[shared - 1] if shared else None


def occurrences(text: str, quote: str, lo: int, hi: int, fences=frozenset()) -> list:
    """Where `quote` sits in text[lo:hi], as absolute indices. A match that runs across a
    fence is not one: the page has words there that this text doesn't."""
    found = []
    at = text.find(quote, lo, hi)
    while at != -1:
        if not any(at < f < at + len(quote) for f in fences):
            found.append(at)
        at = text.find(quote, at + len(quote), hi)
    return found


def capture_anchor(
    html: str, registry, quote: str, section: str, decided=None, rewrites=None
) -> dict:
    """The anchor a quote makes, written the way a selection's is. Raises ValueError with
    what to do about it — a quote the file doesn't hold, or holds twice, is a question
    with an answer, and asking now beats posting a comment that lands nowhere.

    `decided` and `rewrites` make this the reading the user is looking at rather
    than the version as authored: a slot their decision retired is off the page, and a
    body their edit rewrote holds their words — so an anchor is met here the way it
    would land there, instead of detaching in front of them."""
    text, owner, fences, retired, rewritten, gone, shown, enclosing = page_passages(
        html, registry, decided, rewrites
    )
    if section:
        # Against the structure, not the text: an element anchor is the one a click makes
        # on a diagram or an image, and those hold no text to look for.
        if section not in enclosing:
            raise ValueError(f"no element id {section!r} in this version")
        if section in retired:
            sid = retired[section]
            raise ValueError(
                f"§ {section} left the page when the user chose to {decided[sid]} "
                f"§ {sid} — a decision retires the slot its outcome names, and an anchor "
                "on it would reach nobody. Anchor on the settled text instead."
            )
        if section in gone:
            raise ValueError(
                f"§ {section} settled to nothing when the user chose to {gone[section]} "
                "it — the decision removed everything it held from the page, and an anchor "
                "on it would reach nobody. Anchor on the surrounding text instead."
            )
    if not quote:
        return {"section": section}

    wanted = collapse(quote)
    lo_bound, hi_bound = 0, len(text)
    if section:
        span = section_span(owner, section)
        if span is None:
            raise ValueError(
                f"§ {section} holds no quotable text — a widget's data body is its source, "
                "not its words. Drop --quote to anchor on the element itself."
            )
        lo_bound, hi_bound = span
    where = "the page" if not section else f"§ {section}"
    hits = occurrences(text, wanted, lo_bound, hi_bound, fences)
    if not hits:
        if occurrences(text, wanted, lo_bound, hi_bound):
            raise ValueError(
                f"{wanted!r} runs across a widget's parts, and a widget writes words of "
                "its own between them — a column's heading, a milestone's chips, a "
                "diagram in place of its source. Quote within one part, or --section the "
                "widget to point at the whole of it."
            )
        was = _removed_by(html, registry, wanted, section, decided or {}, rewritten)
        if was:
            raise ValueError(f"{where} said {wanted!r} until {was}")
        holder = next((el for el, words in shown.items() if wanted in words), None)
        if holder:
            raise ValueError(
                f"{wanted!r} is in § {holder}'s data body, which is the widget's source "
                "and not its words — the page shows whatever its module made of that, "
                "and this reading holds nothing there to anchor on. Point at the element "
                f"instead: --section {holder}."
            )
        raise ValueError(
            f"{where} doesn't say {wanted!r} — quote it as the version file holds it. A "
            "widget's data body is the widget's source, not its words (a diagram's body "
            "is a picture by the time it is read), so --section the element instead."
        )
    if len(hits) > 1:
        around = [
            f"  - …{text[max(lo_bound, at - 30) : at + len(wanted) + 30]}…"
            for at in hits[:4]
        ]
        if len(hits) > len(around):
            around.append(f"  - …and {len(hits) - len(around)} more")
        raise ValueError(
            f"{where} says {wanted!r} {len(hits)} times, so this quote names no one "
            "passage. Extend it, or scope it with --section:\n" + "\n".join(around)
        )

    lo = hits[0]
    hi = lo + len(wanted)
    section = section or enclosing_section(owner, lo, hi)
    # The neighbours come from the whole reading, as the browser's do — the section
    # filters where the search may land, never what surrounds a passage — so a passage
    # closing its section still stores a full suffix. Each side reaches only to the
    # nearest fence, because past one the page holds words this doesn't: context the
    # runtime can never confirm leaves every copy equally unconfirmed, which is where
    # an anchor carrying none starts anyway.
    # Both are trimmed before they are cut, since the runtime reads its side back through
    # the same collapse, which trims — a stored space no occurrence produces fails at the
    # first comparison.
    prefix = text[max([0] + [f for f in fences if f <= lo]) : lo].strip()[-CONTEXT:]
    suffix = text[hi : min([len(text)] + [f for f in fences if f >= hi])].strip()[
        :CONTEXT
    ]
    return {
        "section": section,
        "quote": wanted,
        **({"prefix": prefix} if prefix else {}),
        **({"suffix": suffix} if suffix else {}),
    }


def _removed_by(html, registry, wanted: str, section: str, decided, rewritten):
    """What took `wanted` off the user's page, when the version as authored still
    holds it: the decision that retired the slot it sat in, or the edit that rewrote
    the element saying it. Naming that act beats telling the writer the page never
    said it."""
    if not (decided or rewritten):
        return None
    p = page_passages(html, registry)
    lo, hi = 0, len(p.text)
    if section:
        span = section_span(p.owner, section)
        if span is None:
            return None
        lo, hi = span
    for at in occurrences(p.text, wanted, lo, hi, p.fences):
        for ids in p.owner[at : at + len(wanted)]:
            sid = next((wid for wid in ids if wid in decided), None)
            if sid:
                return (
                    f"the user chose to {decided[sid]} § {sid} — that decision "
                    "retired these words from the page. Quote it as it now stands."
                )
            wid = next((wid for wid in ids if wid in rewritten), None)
            if wid:
                return (
                    f"the user rewrote § {wid} — their {rewritten[wid]} replaced "
                    "these words. Quote the text as they left it."
                )
    return None


# ---------- the readable column ----------
# A rule, a style="" and a width="" are the three places a document states a width.
# The first two are CSS, so tinycss2 reads them; the third is an attribute, so the
# markup parser does.
#
# Three patterns over the file's text came first, and each answered something adjacent
# to the question asked: the document read as a stylesheet handed a screenshot's base64
# to the rule walker, `width` needed a lookbehind to exclude `max-width` because it
# matched a name instead of reading a property, and the scan for `style=""` never saw
# one written with the other quote. Hand-rolling the parser is the same mistake a level
# down, and harder to see, because a hand-rolled parser is right about the grammar it
# was written against: the brace walk those patterns became knew that a comment's braces
# are not braces, and still read a `}` inside `content: "}"` as the end of the block,
# dropping every declaration after it in that rule; still read a rule holding both
# declarations and a nested rule as declaring nothing of its own; and still told a fixed
# `900px` from a `calc(100% - 900px)` by asking whether the string ended in `px`, which
# `900px !important` does not. CSS has no parser in the stdlib, so the dependency is a
# real cost — one more wheel behind every `version check`, ~6ms to read the theme — and
# it buys the grammar whole rather than one bug's worth at a time.


def css_block(css):
    """What a block holds: the declarations it states, and the rules nested inside it. A
    style="" attribute is a block written without the braces around it."""
    return tinycss2.parse_blocks_contents(css, skip_comments=True, skip_whitespace=True)


def css_rules(css: str):
    """(selector, block, conditional) per qualified rule, at every depth — a rule that
    holds both declarations and a nested rule states one of its own. `conditional` is
    true for a rule inside an at-rule, which applies only when a condition this check
    never evaluates holds: `@media print`, a viewport query. Nesting alone is not a
    condition, so a rule nested in a conditional one is conditional and no more."""
    yield from _rules(
        tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    )


def _css_unclosed_blocks(css: str) -> int:
    """How many blocks a stylesheet leaves open at end of file.

    The CSS parser auto-closes these (so tinycss2 reports no error), which is
    exactly what makes one dangerous here: stylesheets are layer sources that
    concatenate, so a block left open swallows every rule after it — the rest
    of the file's and every later layer's — into its own scope. Counted
    outside comments and strings; an over-closed sheet floors at zero, since
    the stray brace is a parse error tinycss2 already names."""
    depth = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end == -1 else end + 2
        elif ch in "\"'":
            quote = ch
            i += 1
            while i < len(css) and css[i] not in (quote, "\n"):
                i += 2 if css[i] == "\\" else 1
            i += 1
        else:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            i += 1
    return depth


def css_syntax_errors(css: str, source: str, *, block=False) -> list:
    """Every parse error in a stylesheet or declaration block, including nested rules."""
    parse = (
        css_block
        if block
        else lambda value: tinycss2.parse_stylesheet(
            value, skip_comments=True, skip_whitespace=True
        )
    )
    errors = []
    seen = set()
    if not block and (depth := _css_unclosed_blocks(css)):
        errors.append(
            f"{source}: {depth} block(s) left open at end of file — every rule "
            "after the unclosed brace, this stylesheet's or a later layer's, "
            "lands inside its scope"
        )

    def record(node):
        key = (node.source_line, node.source_column, node.message)
        if key in seen:
            return
        seen.add(key)
        errors.append(
            f"{source} syntax error at "
            f"{node.source_line}:{node.source_column}: {node.message}"
        )

    def walk_tokens(tokens):
        for token in tokens:
            if token.type == "error":
                record(token)
            for attr in ("arguments", "content"):
                nested = getattr(token, attr, None)
                if isinstance(nested, list):
                    walk_tokens(nested)

    def walk_rules(nodes):
        for node in nodes:
            if node.type == "error":
                record(node)
            for attr in ("prelude", "value"):
                tokens = getattr(node, attr, None)
                if isinstance(tokens, list):
                    walk_tokens(tokens)
            if node.type in {"qualified-rule", "at-rule"} and node.content is not None:
                walk_tokens(node.content)
                walk_rules(css_block(node.content))

    walk_rules(parse(css))
    return errors


def _rules(nodes, conditional=False):
    """`nodes` and every rule nested inside them, as (selector, block, conditional)."""
    for node in nodes:
        if node.type == "qualified-rule":
            block = css_block(node.content)
            yield tinycss2.serialize(node.prelude).strip(), block, conditional
            yield from _rules(block, conditional)
        elif node.type == "at-rule" and node.content:
            yield from _rules(css_block(node.content), True)


def _number(text: str):
    """`text` as a number, or None when it is not one. A width="" attribute states a
    bare count of pixels, so it has no unit for the CSS parser to read."""
    try:
        return float(text)
    except ValueError:
        return None


def _px(declaration):
    """The pixel length a declaration states, or None where it states something else: a
    percentage, a vw, a calc() with a px term inside it. Only a fixed pixel length is a
    hard overflow, and only a lone length is fixed. A value keeps the whitespace around
    it, which is a token like any other and not part of what the value says."""
    value = [t for t in declaration.value if t.type != "whitespace"]
    if len(value) == 1 and value[0].type == "dimension" and value[0].lower_unit == "px":
        return value[0].value
    return None


def _px_widths(declarations, props: tuple):
    """(property, pixels) per declaration in `props` pinned to a fixed pixel length."""
    for declaration in declarations:
        if declaration.type == "declaration" and declaration.lower_name in props:
            px = _px(declaration)
            if px is not None:
                yield declaration.lower_name, px


def _column_width(page_css: str, theme_css: str) -> int:
    """Best-effort readable-column width from the max-width of a container rule.
    A page's own <style> wins over the vendored theme, which wins over the fallback.

    Only what a stylesheet states outright counts: a column is the baseline everything
    else is measured against, so it has to be certain, and a conditional rule states a
    column for some condition rather than for the page. Reading them too let a page
    disable this check with one line of print CSS — `@media print { main { max-width:
    2000px } }` measured every screen element against 2000px."""
    for css in (page_css, theme_css):
        widths = [
            px
            for selector, block, conditional in css_rules(css)
            if not conditional and _names_column(selector)
            for _, px in _px_widths(block, ("max-width",))
        ]
        if widths:
            return int(max(widths))
    return COLUMN_FALLBACK


def _overwide_elements(parser: _StructParser, column: int) -> list:
    """Everything a version pins wider than the column: its own rules, its inline
    styles, and the width="" attributes that count as pixels.

    A conditional rule counts here, where it cannot define the column: a pin is a risk
    rather than a baseline, and it overflows whenever its condition holds."""
    hits = []
    for selector, block, _ in css_rules(parser.css):
        for prop, px in _px_widths(block, OVERFLOW_PROPS):
            if px > column:
                hits.append(
                    f"rule `{selector}` sets {prop}: {px:g}px (column is {column}px)"
                )
    for style in parser.inline_styles:
        for prop, px in _px_widths(css_block(style), OVERFLOW_PROPS):
            if px > column:
                hits.append(f"inline style {prop}: {px:g}px (column is {column}px)")
    for tag, value in parser.attr_widths:
        px = _number(value)
        if px is not None and px > column:
            hits.append(f'<{tag} width="{value}"> exceeds column ({column}px)')
    return hits


PRESENTATION_PROPERTIES = {
    "all",
    "display",
    "interactivity",
    "opacity",
    "pointer-events",
    "visibility",
}


def inline_presentation_override_errors(parser: _StructParser) -> list:
    """Inline importance outranks even the theme's first important cascade layer."""
    errors = []
    for number, style in enumerate(parser.inline_styles, 1):
        for declaration in css_block(style):
            if (
                declaration.type == "declaration"
                and declaration.important
                and declaration.lower_name in PRESENTATION_PROPERTIES
            ):
                errors.append(
                    f"inline style #{number} makes protected presentation property "
                    f"{declaration.lower_name} important"
                )
    return errors


class RegistryError(click.ClickException):
    """A registry that is not a vocabulary, raised rather than exited because two doors
    read one. The CLI prints the message and stops; the page server owes the browser an
    answer, and `sys.exit` inside its request handler killed the connection mid-POST
    while every other rejection beside it returned a 400 — so a page whose vendored
    stamp had fallen behind the running layer met the reader's click with a dead socket
    and no words. Click renders an escaped one bare, at whichever command reached it, so
    a refusal from here reads like every other refusal this CLI writes."""

    def show(self, file=None) -> None:
        click.echo(self.message, file=file or click.get_text_stream("stderr"))


def read_registry_entries(path: Path):
    """Read the top-level entries one registry layer contributes."""
    if (path.exists() or path.is_symlink()) and not path.is_file():
        raise RegistryError(f"{path}: registry.json must be a file")
    try:
        registry = read_json(path)
    except json.JSONDecodeError as error:
        raise RegistryError(f"{path}: invalid JSON ({error.msg}, line {error.lineno})")
    except UnicodeDecodeError:
        raise RegistryError(f"{path} must be UTF-8")
    if registry is None:
        if not path.is_file():
            return None
        raise RegistryError(f"{path}: registry must be a JSON object")
    if not isinstance(registry, dict):
        raise RegistryError(f"{path}: registry must be a JSON object")
    non_objects = [
        name for name, entry in registry.items() if not isinstance(entry, dict)
    ]
    if non_objects:
        raise RegistryError(f"{path}: registry entries must be objects: {non_objects}")
    return registry


def declares_string(field_schema) -> bool:
    """Whether a detail field allows a string and nothing else, however it says so."""
    declared = field_schema.get("type") if isinstance(field_schema, dict) else None
    allowed = {declared} if isinstance(declared, str) else set(declared or [])
    return allowed == {"string"}


def state_specs(entry: dict):
    """The state and report verb declarations on one widget entry."""
    for channel in ("x-state", "x-report"):
        for verb, spec in entry.get(channel, {}).items():
            yield channel, verb, spec


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary after its top-level overlays are merged."""
    path = source
    try:
        kinds = registry["$events"]["kinds"]
        names = registry["$languages"]["names"]
        paths = registry["$languages"]["paths"]
        tones = registry["$tones"]["names"]
    except (KeyError, TypeError):
        raise RegistryError(
            f"{path}: registry must declare $events.kinds, $languages.names/paths "
            "and $tones.names"
        )
    if not isinstance(kinds, dict):
        raise RegistryError(f"{path}: $events.kinds must map names to event contracts")
    envelope = {"id", "ts", "author", "kind", "seq"}
    for kind, contract in kinds.items():
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(contract, dict)
            or set(contract) - {"record", "browser"}
            or not isinstance(contract.get("record"), dict)
            or ("browser" in contract and not isinstance(contract["browser"], dict))
        ):
            raise RegistryError(
                f"{path}: $events.kinds must map names to atomic record/browser "
                "contracts"
            )
        for writer, schema in contract.items():
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: $events kind `{kind}` {writer} is not a valid JSON "
                    f"Schema: {error.message}"
                )
        record = contract["record"]
        properties = record.get("properties", {})
        required = record.get("required", [])
        if (
            set(record) != {"type", "properties", "required", "additionalProperties"}
            or record.get("type") != "object"
            or not envelope <= set(properties)
            or not envelope <= set(required)
            or properties.get("kind") != {"const": kind}
            or record.get("additionalProperties") is not False
        ):
            raise RegistryError(
                f"{path}: $events kind `{kind}` record must use only type, "
                "properties, required, and additionalProperties to declare a closed "
                "full event schema with required id/ts/author/kind/seq fields and "
                "its kind const"
            )

    # Compare a vendored or overlaid contract with the installed producers' own.
    # Optional fields may grow; installed fields, requirements, and browser doors
    # may not change.
    current = read_registry_entries(ASSETS / "registry.json")["$events"]["kinds"]
    incompatible = []
    for kind, expected in current.items():
        actual = kinds.get(kind)
        if actual is None:
            incompatible.append(f"kind `{kind}`")
            continue
        expected_record = expected["record"]
        actual_record = actual["record"]
        expected_properties = expected_record["properties"]
        actual_properties = actual_record["properties"]
        changed = sorted(
            name
            for name, schema in expected_properties.items()
            if actual_properties.get(name) != schema
        )
        if changed:
            incompatible.append(f"`{kind}` fields {changed}")
        elif set(actual_record["required"]) != set(expected_record["required"]):
            incompatible.append(f"`{kind}` required fields")
        elif actual.get("browser") != expected.get("browser"):
            incompatible.append(f"`{kind}` browser writer")
    if incompatible:
        raise RegistryError(
            f"{path}: $events.kinds omits or changes contracts the current layer "
            "writes: " + ", ".join(incompatible)
        )
    # $keys documents exactly the x- keys the lint admits, one string per key: the
    # keys are closed here (EXTENSION_SCHEMA), so a member for a key that cannot be
    # declared is documentation of nothing, and a key with no member is one an author
    # reads the catalog for and finds unsaid. `page catalog` prints it and the site's
    # table is generated from it, which is what makes the pin worth keeping.
    keys = registry.get("$keys")
    admitted = set(EXTENSION_SCHEMA["properties"])
    documented = set(keys or {}) - {"description"}
    if (
        not isinstance(keys, dict)
        or not isinstance(keys.get("description"), str)
        or not all(isinstance(text, str) and text for text in keys.values())
        or documented != admitted
    ):
        raise RegistryError(
            f"{path}: $keys must carry a description and one paragraph per x- key the "
            f"lint admits — missing {sorted(admitted - documented)}, "
            f"unadmitted {sorted(documented - admitted)}"
        )
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or len(names) != len(set(names))
    ):
        raise RegistryError(
            f"{path}: $languages.names must be a unique list of strings"
        )
    if not isinstance(paths, dict) or not all(
        isinstance(extension, str) and language in names
        for extension, language in paths.items()
    ):
        raise RegistryError(
            f"{path}: $languages.paths must map extensions to declared languages"
        )
    # Shape, not just presence, because `declared_word_errors` asks a list for membership
    # and a string answers the same question by substring: a layer declaring
    # `"names": "ok"` would pass every one-letter tone and paint none of them, which is
    # exactly the invisible failure the check exists to catch.
    if (
        not isinstance(tones, list)
        or not all(isinstance(tone, str) for tone in tones)
        or len(tones) != len(set(tones))
    ):
        raise RegistryError(f"{path}: $tones.names must be a unique list of strings")
    invalid_names = [
        tag
        for tag in registry
        if not tag.startswith("$") and re.fullmatch(WIDGET_NAME, tag) is None
    ]
    if invalid_names:
        raise RegistryError(f"{path}: invalid registry entry names: {invalid_names}")
    widgets = {tag: entry for tag, entry in registry.items() if tag.startswith("lf-")}
    # First validate every entry in isolation. Cross-entry checks run only after this
    # pass, so their result cannot depend on which widget happened to be written first.
    for tag, entry in widgets.items():
        try:
            Draft202012Validator.check_schema(entry)
        except SchemaError as error:
            raise RegistryError(
                f"{path}: <{tag}> is not a valid JSON Schema: {error.message}"
            )
        extensions = {
            key: value for key, value in entry.items() if key.startswith("x-")
        }
        errors = sorted(
            Draft202012Validator(EXTENSION_SCHEMA).iter_errors(extensions), key=str
        )
        if errors:
            raise RegistryError(
                f"{path}: <{tag}> registry extensions are invalid: {errors[0].message}"
            )
        for channel, verb, spec in state_specs(entry):
            try:
                Draft202012Validator.check_schema(spec["detail"])
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` has an invalid "
                    f"detail schema: {error.message}"
                )
            if spec["detail"].get("type") != "object":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    "must declare an object"
                )
            # A verb carries only the detail keys its entry declares — the
            # premise the layer's own field meanings rest on: both runtimes
            # dispatch thread settlement on `resolves` being present, which
            # is safe exactly because a closed schema makes carrying it a
            # declaration.
            if spec["detail"].get("additionalProperties") is not False:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    "must state additionalProperties: false — a verb carries "
                    "only the detail keys it declares"
                )

    slots = retirement_slots(registry)
    for tag, entry in widgets.items():
        if unknown := sorted(set(entry.get("x-parent", [])) - set(widgets)):
            raise RegistryError(
                f"{path}: <{tag}> x-parent names unknown widgets {unknown}"
            )
        properties = entry.get("properties", {})
        said = set(entry.get("x-says", {}))
        for key in ATTRIBUTE_KEYS:
            declared = entry.get(key) or ()
            named = {declared} if isinstance(declared, str) else set(declared)
            if unknown := sorted(named - set(properties)):
                raise RegistryError(
                    f"{path}: <{tag}> {key} names undeclared attributes {unknown}"
                )
        # A drawing's box is the clip around something drawn at a size of its own, and
        # the theme lays it out as a row so the drawing keeps the column's axis and
        # scrolls only past the room. Every child of that element is an item in the row,
        # so a word the layer writes into it stands beside the drawing rather than over
        # it and takes it off the axis by half the word's width — a picture placed
        # slightly wrong, which nothing else on the page has any way to notice. The
        # widget that has words as well as a drawing is a box, which lays out both.
        # (x-paints is the other kind of word and is not this: it renders into the
        # shared clip, which is positioned out of the flow.)
        if entry.get("x-wide") == "drawing" and said:
            raise RegistryError(
                f"{path}: <{tag}> is x-wide: drawing and says {sorted(said)} — a "
                "drawing's box holds what was drawn and lays out nothing beside it, "
                "so a widget that says an attribute as well declares x-wide: box"
            )
        # A predicate names attributes and values the page can actually carry, or its
        # widget silently disappears from every consumer. The value's kind follows the
        # attribute's own schema — a flag is there or it isn't, an enum admits what it
        # lists — and a subschema that states neither contradicts nothing.
        awaits = entry.get("x-awaits", {})
        conditions = [
            ("x-awaits", awaits.get("when", {})),
            ("x-awaits", awaits.get("until", {}).get("when", {})),
            ("x-conversation", entry.get("x-conversation", {}).get("when", {})),
        ]
        for declaration, condition in conditions:
            for attr, values in condition.items():
                if attr not in properties:
                    raise RegistryError(
                        f"{path}: <{tag}> {declaration} names undeclared attribute "
                        f"`{attr}`"
                    )
                schema = properties[attr]
                declared = schema if isinstance(schema, dict) else {}
                for value in values:
                    if isinstance(value, bool):
                        # A subschema saying neither a type nor an enum contradicts
                        # nothing; one that says either has told us this attribute
                        # carries a value.
                        if declared.get("type") not in (
                            None,
                            "boolean",
                        ) or declared.get("enum"):
                            raise RegistryError(
                                f"{path}: <{tag}> {declaration} tests `{attr}` as "
                                f"{str(value).lower()}, but that attribute is not a flag"
                            )
                    elif declared.get("type") == "boolean":
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests flag `{attr}` as "
                            f"{value!r}; a flag is there or it isn't"
                        )
                    if (
                        allowed := declared.get("enum")
                    ) is not None and value not in allowed:
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests `{attr}` at "
                            f"{value!r}, which its own enum does not admit"
                        )
                    if errors := sorted(
                        Draft202012Validator(schema).iter_errors(value), key=str
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests `{attr}` at "
                            f"{value!r}, which its own schema does not admit: "
                            f"{errors[0].message}"
                        )
        # A blanket answer is one of this widget's own verbs, so the log records it
        # the way every other decision is recorded.
        if (blanket := awaits.get("all")) and blanket not in entry.get("x-state", {}):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits answers every one at once with "
                f"`{blanket}`, which it does not declare as an x-state verb"
            )
        # The until verb closes a thread ask, so it too is one of the widget's own
        # verbs — same rule as `all`, same reason.
        if (until := awaits.get("until")) and until["verb"] not in entry.get(
            "x-state", {}
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits holds asks open until `{until['verb']}`, "
                "which it does not declare as an x-state verb"
            )
        needs_upgrade = [
            key
            for key in (
                "x-state",
                "x-report",
                "x-language",
                "x-verbatim",
                "x-shadow",
                "x-conversation",
            )
            if entry.get(key) and not entry["x-upgrade"]
        ]
        if needs_upgrade:
            raise RegistryError(
                f"{path}: <{tag}> declares {', '.join(needs_upgrade)} "
                "but has no upgraded handler"
            )
        # A version overrules a standing report with `overruled` on the element,
        # so a widget with an agent channel that doesn't declare the attribute is
        # one whose every report contradiction is unpublishable.
        if entry.get("x-report") and not (
            isinstance(properties.get("overruled"), dict)
            and properties["overruled"].get("type") == "boolean"
        ):
            raise RegistryError(
                f"{path}: <{tag}> declares x-report but not the boolean `overruled` "
                "attribute a version overrules a standing report with"
            )
        # The same rule for the other channel: a version that rewrites what a
        # decision rested on must say `restated` on the element ($restated),
        # and a closed schema without the attribute is a widget whose every
        # rewrite is unpublishable — the words gate demands an attribute the
        # widget's own schema refuses. Held only where a verb folds on the
        # widget itself: a verb folding per child (move's "card") rests its
        # decisions on elements this entry doesn't name.
        folds_whole = any(
            spec["unit"] == "widget" for spec in entry.get("x-state", {}).values()
        )
        if folds_whole and not (
            isinstance(properties.get("restated"), dict)
            and properties["restated"].get("type") == "boolean"
        ):
            raise RegistryError(
                f"{path}: <{tag}> declares x-state verbs that fold on the widget "
                "but not the boolean `restated` attribute a version retracts a "
                "decision with"
            )
        # A facet is one independently standing fact. Every way of stating that
        # fact therefore agrees on what it folds over and how authored markup can
        # record it. The name itself remains local to the tag: two widget families
        # may both call a facet `status` without sharing a contract.
        facet_specs: dict[str, tuple[str, str, dict | None]] = {}
        for channel, verb, spec in state_specs(entry):
            facet = spec["facet"]
            previous = facet_specs.get(facet)
            if previous is None:
                facet_specs[facet] = (channel, verb, spec.get("record"))
                continue
            previous_channel, previous_verb, previous_record = previous
            previous_spec = entry[previous_channel][previous_verb]
            if spec["unit"] != previous_spec["unit"]:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` and "
                    f"{previous_channel} verb `{previous_verb}` share facet "
                    f"`{facet}` but declare different fold units "
                    f"(`{spec['unit']}` and `{previous_spec['unit']}`)"
                )
            if spec.get("record") != previous_record:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` and "
                    f"{previous_channel} verb `{previous_verb}` share facet "
                    f"`{facet}` but do not declare identical record forms "
                    "(or both remain recordless)"
                )

        # A facet is semantic, but its record writes a physical slot. Body and
        # position have one per unit; value and attribute-set are keyed by attr.
        physical_slots: dict[tuple[str, str, str | None], tuple[str, str, str]] = {}
        for channel, verb, spec in state_specs(entry):
            record = spec.get("record")
            if record is None:
                continue
            kind = record["kind"]
            attr = record.get("attr")
            key = spec["unit"], kind, attr
            previous = physical_slots.setdefault(key, (channel, verb, spec["facet"]))
            previous_channel, previous_verb, previous_facet = previous
            if previous_facet == spec["facet"]:
                continue
            slot = kind + (f" `{attr}`" if attr else "")
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` (facet "
                f"`{spec['facet']}`) and {previous_channel} verb "
                f"`{previous_verb}` (facet `{previous_facet}`) claim the "
                f"same physical record slot (unit `{spec['unit']}`, "
                f"{slot}); distinct facets must record independently"
            )

        # A resolves-bearing widget has one answer fact. Thread history can outlive
        # the markup that declared its verbs, so both thread builders deliberately
        # fold answers by widget id alone; requiring every action verb on that tag
        # to share the answer facet makes that historical key exact rather than a
        # compatibility approximation.
        state = entry.get("x-state", {})
        resolving = [
            (verb, spec)
            for verb, spec in state.items()
            if "resolves" in spec["detail"].get("properties", {})
        ]
        if resolving:
            answer_verb, answer_spec = resolving[0]
            answer_facet = answer_spec["facet"]
            for verb, spec in state.items():
                if spec["facet"] != answer_facet:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` uses facet "
                        f"`{spec['facet']}`, but `{answer_verb}` declares "
                        "`resolves`; every x-state verb on a resolves-bearing "
                        f"widget must share its answer facet `{answer_facet}`"
                    )

        # One rule set for both channels: x-state and x-report differ in
        # precedence, not in how a verb, its facet, unit, and record hang together.
        for channel, verb, spec in state_specs(entry):
            detail_properties = spec["detail"].get("properties", {})
            required = set(spec["detail"].get("required", []))
            unit = spec["unit"]
            fields = [] if unit == "widget" else [unit]
            record = spec.get("record")
            if record:
                fields.append(record["value"])
                if record["kind"] == "position":
                    fields.append(record["order"])
                    if record["within"] not in widgets:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records a "
                            f"position within unknown widget <{record['within']}>"
                        )
                if record["kind"] == "body":
                    if entry.get("x-content") != "data":
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            "its body, so x-content must be data; projection "
                            "states text rather than a prose subtree"
                        )
                    nested = sorted(
                        child
                        for child, child_entry in widgets.items()
                        if tag in child_entry.get("x-parent", [])
                    )
                    if nested:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"its body but admits nested widgets {nested}; a "
                            "text statement cannot reconstruct their state"
                        )
                if record["kind"] == "value":
                    attr = record["attr"]
                    if attr not in properties:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"undeclared attribute `{attr}`"
                        )
                    # Projection rebuilds a refused gesture from authored state.
                    # A required string value gives every baseline an absolute
                    # action detail; absence is represented by an admitted value.
                    if attr not in entry.get("required", []):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"optional attribute `{attr}`; recorded state must be "
                            "required so its authored value can be replayed"
                        )
                    # An x-says value is words the reader sees, and the file's
                    # reading takes them from the markup — replay writing one
                    # would change what the page says while that reading held
                    # still, the desync the fence rules exist to prevent.
                    if attr in said:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"x-says attribute `{attr}`, whose value is words "
                            "the reader sees — declared state may not move the "
                            "page's words"
                        )
            # `resolves` is a reserved detail field: thread settlement reads it
            # off every action as "the comment thread this action answers"
            # (build_threads, in both runtimes), so a verb spelling the name
            # means that or is refused here — a widget using it otherwise
            # would settle a thread silently.
            if "resolves" in detail_properties:
                # The reader's channel only. Both thread builders read `resolves`
                # off actions, so the name on a report verb declares an answer
                # nothing gives: the report would fold like any other and settle
                # no thread ever — the feature nobody wired up, which this door
                # exists to turn into an error. A thread is the reader's to close,
                # or an action of theirs; the agent's own way is `leaf resolve`.
                if channel != "x-state":
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                        "field `resolves`, a reserved name (the comment thread "
                        "this action answers) — only an x-state verb settles a "
                        "thread, so rename the field"
                    )
                if detail_properties["resolves"] != {"type": "string"}:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                        "field `resolves`, a reserved name (the comment thread "
                        'this action answers) — declare it {"type": "string"} or '
                        "rename the field"
                    )
                # A thread is answered by the ask, and an ask is a widget
                # instance (x-awaits) — so the answer is absolute across the
                # widget, and both thread builders key the standing answer on
                # the widget id, the one key a log outlives its markup with.
                # A per-part verb answering a thread would fold per part and
                # settle per widget, and the disagreement is invisible: the
                # thread reads right until a second part is acted on. Whoever
                # writes that widget needs an ask per part first, and this is
                # where they find that out.
                if unit != "widget":
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` answers a "
                        f"comment thread (`resolves`) but folds per `{unit}` — "
                        "a thread is answered by the ask, and an ask is the "
                        "whole widget"
                    )
            undeclared = [field for field in fields if field not in detail_properties]
            optional = [field for field in fields if field not in required]
            if undeclared or optional:
                problem = (
                    f"does not declare {undeclared}"
                    if undeclared
                    else f"does not require {optional}"
                )
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` reads detail fields "
                    f"its schema {problem}"
                )
            # Undo restores a recorded action from authored markup. That markup
            # can reconstruct exactly the fold unit and the record's value/order;
            # any other required field would make a valid declaration impossible
            # to restore without a widget-specific default hidden in core.
            unrestorable = sorted(required.difference(fields))
            if channel == "x-state" and record and unrestorable:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` requires detail "
                    f"fields {unrestorable} that authored markup cannot restore"
                )
            if unit != "widget" and record and record["kind"] != "position":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` records per-part "
                    "state; only position records support that"
                )

            if unit != "widget" and not declares_string(detail_properties[unit]):
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` fold unit `{unit}` "
                    "must be a string"
                )
            if record:
                value = record["value"]
                schema = detail_properties[value]
                # An attribute record names the set of elements wearing it, so its
                # detail field is a list of ids however many the group allows —
                # nothing downstream has to ask which kind of group it came from.
                if record["kind"] == "attribute":
                    items = schema.get("items") if isinstance(schema, dict) else None
                    if not (
                        isinstance(schema, dict)
                        and schema.get("type") == "array"
                        and isinstance(items, dict)
                        and items.get("type") == "string"
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must be an array of strings"
                        )
                elif record["kind"] == "value":
                    # The record reads and writes the attribute, so its detail
                    # field speaks the attribute's own schema — one vocabulary,
                    # or the log's contract and the markup's drift apart.
                    if schema != properties[record["attr"]]:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must carry attribute "
                            f"`{record['attr']}`'s own schema"
                        )
                    string_enum = (
                        isinstance(schema, dict)
                        and isinstance(schema.get("enum"), list)
                        and bool(schema["enum"])
                        and all(isinstance(value, str) for value in schema["enum"])
                    )
                    if not (declares_string(schema) or string_enum):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must be a string or string enum; "
                            "HTML attributes cannot restore another JSON type"
                        )
                elif not declares_string(schema):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
                        f"value `{value}` must be a string"
                    )
                if record["kind"] == "position":
                    order = detail_properties[record["order"]]
                    if not (isinstance(order, dict) and order.get("type") == "integer"):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"order `{record['order']}` counts the unit's "
                            "siblings, so its detail field must be an integer"
                        )
        # Withdrawal is the author taking an unanswered question back, and the
        # entry says which of its own outcomes that leaves the page in
        # (retirable_ids). A verb no slot of this widget retires under would
        # license nothing but the wrapper, so the withdrawal it promises would
        # fail as "ids dropped" on the version that tried it — the misdeclaration
        # is invisible until then, and this is where its author is standing.
        withdrawn = entry.get("x-withdrawn-as")
        if withdrawn is not None and withdrawn not in slots.get(tag, {}):
            raise RegistryError(
                f"{path}: <{tag}> x-withdrawn-as `{withdrawn}` retires none of its "
                "slots; withdrawing it would leave their ids on the page"
            )
        retired = entry.get("x-retired-when")
        if retired is None:
            continue
        # Every holder, not the first: a slot that retires on its parent's verb has
        # to retire whichever parent it was written in, or it would be settled under
        # one and undecidable under another.
        for parent in entry["x-parent"]:
            parent_state = widgets[parent].get("x-state", {})
            if retired not in parent_state:
                raise RegistryError(
                    f"{path}: <{tag}> x-retired-when `{retired}` is invalid: "
                    f"<{parent}> does not declare that x-state verb"
                )
            if parent_state[retired]["unit"] != "widget":
                raise RegistryError(
                    f"{path}: <{tag}> x-retired-when `{retired}` must fold by widget"
                )
    # A holder's retired slots are halves of one decision; outcomes on different
    # facets could stand at once, leaving no single settlement to render.
    for holder, outcomes in slots.items():
        state = widgets[holder]["x-state"]
        facets = {state[outcome]["facet"] for outcome in outcomes}
        if len(facets) > 1:
            mapping = ", ".join(
                f"`{outcome}` → `{state[outcome]['facet']}`" for outcome in outcomes
            )
            raise RegistryError(
                f"{path}: <{holder}> x-retired-when outcomes span facets "
                f"({mapping}); every retirement outcome for one holder must "
                "share one facet"
            )
    return registry


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or (example := entry.get("x-example")) is None:
            continue
        parser = parse_structure(example)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise RegistryError(f"{source}: <{tag}> x-example is invalid: {errors[0]}")
    return registry


_registries = {}  # registry.json -> (its stamp, the vocabulary it holds)


def read_registry(path: Path):
    """Read and validate one complete registry vocabulary, once per vendored file.

    `page init` writes a page's registry.json and nothing writes it again, while an
    action POST asks for the whole vocabulary before it can check a single press —
    so every press re-linted forty frozen entries, an order of magnitude more work
    than the contract check it was preparing for."""
    stamp = file_stamp(path)
    if stamp and (held := _registries.get(path)) and held[0] == stamp:
        return held[1]
    entries = read_registry_entries(path)
    registry = None if entries is None else validate_registry(entries, path)
    if stamp:
        _registries[path] = (stamp, registry)
    return registry


def load_registry(page_dir: Path):
    """The page's complete vendored vocabulary, or None before `page init`."""
    return read_registry(page_dir / "registry.json")


def layer_generation(page_dir: Path) -> str:
    """The epoch shared by this page's vendored runtime and server contract."""
    registry = read_registry_entries(page_dir / "registry.json")
    generation = (registry or {}).get("$layer", {}).get("generation")
    if not isinstance(generation, str) or not generation:
        raise RegistryError(
            f"{page_dir / 'registry.json'}: vendored registry lacks $layer.generation; "
            "run `leaf page init`"
        )
    return generation


def require_registry(page_dir: Path) -> dict:
    """The vendored vocabulary, for a command that has nothing to do without one."""
    registry = load_registry(page_dir)
    if registry is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    return registry


def merge_layer_entries(merged: dict, entries: dict) -> None:
    """Fold one layer's top-level registry entries into the merge.

    A tag entry replaces the earlier one whole; schemas never deep-merge,
    because a half-old, half-new contract is no layer's vocabulary. A $ entry
    merges by member: it is not a contract but the layer's namespace of shared
    facts. Under replace-whole, a project declaring its one idiom vendored a
    $idioms holding exactly that idiom — its theme rules kept styling,
    theme.css concatenating where the registry did not, while `page catalog`
    silently dropped the shipped ten. A member that is itself a map merges by
    its own keys for the same reason one level down: $languages.paths is
    indexed by extension, and a layer adding `.svelte` must not silently drop
    every shipped extension with it. Scalar and list members replace whole —
    a names list is one statement — and the grain here decides nothing the
    gates don't re-check: validation and the vocabulary stamp read the merged
    result, whichever layer each piece came from.
    """
    for name, entry in entries.items():
        earlier = merged.get(name)
        if not (name.startswith("$") and earlier is not None):
            merged[name] = entry
            continue
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {**earlier[key], **value}
        merged[name] = combined


def incoming_registry(layers: list) -> dict:
    """The merged registry `page init` will vendor.

    Layers are additive at the top level; merge_layer_entries holds the grain.
    """
    merged = {}
    paths = []
    for layer in layers:
        path = layer / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_entries(merged, read_registry_entries(path))
    if not paths:
        raise RegistryError("the incoming layer has no registry.json")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    return validate_registry_examples(validate_registry(merged, source), source)


# ---------- the vocabulary stamp ----------
# The registry vendored into a page is also that page's statement of what its
# runtime speaks: $events names the event kinds and the fields each carries,
# x-state (per widget) each tag's verbs and detail schemas. Nothing else on disk
# says so. `page init` refuses a re-vendor that would retire or reshape a contract
# still present in the log.
#
# That refusal is the third door a decision can be lost through, after version-scoping
# and hand-copying: the log is append-only and its verbs are a forever-contract, so
# fifteen of one page's own `decide` events fell silent when the verb was retired under
# them. Only the stamp makes that a refusal rather than a quiet no-op.


def vocabulary_gaps(page_dir: Path, events: list, incoming: dict) -> list:
    """What the page's log says that the *incoming* layer no longer speaks:
    events its $events record schemas reject, or actions and reports whose
    sending tag, verb, or detail the incoming x-state or x-report contract
    rejects. Empty for a fresh page.
    Counted, because the number is the cost — each is a recorded event that
    would never replay again."""
    if not events:
        return []
    contracts = incoming["$events"]["kinds"]
    thread = thread_structure(events)
    versions = {}

    def page_by_id(version):
        if version not in versions:
            versions[version] = parse_version(page_dir, version).by_id
        return versions[version]

    missing = {}
    for e in events:
        kind = e["kind"]
        if kind not in contracts:
            key = f"kind `{kind}`"
        elif error := event_record_error(contracts[kind], e):
            key = f"kind `{kind}` record: {error}"
        elif kind == "action" and (
            error := action_contract_error(
                e, page_by_id(e["version"]), thread, incoming
            )
        ):
            key = f"action contract: {error}"
        elif kind == "report" and (
            error := report_contract_error(e, page_by_id(e["version"]), incoming)
        ):
            key = f"report contract: {error}"
        elif e.get("markup") and (
            errors := thread_markup_contract_errors(thread.fragments[e["id"]], incoming)
        ):
            key = "thread markup contract: " + "; ".join(errors)
        else:
            continue
        missing[key] = missing.get(key, 0) + 1
    return [
        f"{n} event{'s' if n != 1 else ''} of {key}"
        for key, n in sorted(missing.items())
    ]


def at(rec: dict, named: str = "") -> str:
    """Where a lint finding is, in the terms the author reads their own file in: the
    tag, whatever identifies the one meant — an id, or the attribute the rule is
    about — and the line the markup opens on. Every gate below opens its findings this
    way, so the shape is stated here rather than re-spelled at each of them; a reader
    scanning a page of them reads one shape, and a change to it is one edit."""
    return f"<{rec['tag']}{' ' + named if named else ''}> (line {rec['line']})"


def widget_errors(lf_elements: list, registry: dict) -> list:
    """Validate parsed lf-* elements against the registry: schema over the
    attribute instance, x-parent nesting, and the x-content model."""
    errors = []
    # Containers ("items") admit exactly the tags that declare them as x-parent.
    children_of = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-"):
            continue
        for parent in entry.get("x-parent", []):
            children_of.setdefault(parent, set()).add(tag)

    for rec in lf_elements:
        tag, where = rec["tag"], at(rec)
        entry = registry.get(tag)
        if entry is None:
            errors.append(
                f"{where}: unknown widget — not in the vendored registry.json"
            )
            continue
        # The element validates as the instance built from its attributes:
        # values as strings, flag attributes as True. HTML's two flag spellings
        # (bare and ="") both mean true; a literal value on a flag stays a string
        # so it fails loudly rather than silently meaning true.
        props = entry.get("properties", {})
        instance = {}
        for name, value in rec["attrs"].items():
            prop = props.get(name)
            is_flag = isinstance(prop, dict) and prop.get("type") == "boolean"
            instance[name] = True if value in (None, "") and is_flag else (value or "")
        for err in sorted(Draft202012Validator(entry).iter_errors(instance), key=str):
            errors.append(f"{where}: {err.message}")

        want_parents = entry.get("x-parent", [])
        if want_parents and rec["parent"] not in want_parents:
            actual = f", found <{rec['parent']}>" if rec["parent"] else ""
            wanted = " or ".join(f"<{p}>" for p in want_parents)
            errors.append(f"{where}: must be a direct child of {wanted}{actual}")
        # Tags declaring this one as x-parent are admissible children under any
        # content model — that is what x-parent means. "data" takes one <pre> and
        # those, "items" element children only, "none" nothing at all.
        content = entry["x-content"]
        allowed = children_of.get(tag, set())
        stray = sorted({c for c in rec["children"] if c not in allowed})
        if content == "none" and (rec["children"] or rec["text"]):
            errors.append(f"{where}: takes no content — write <{tag} …></{tag}>")
        elif content == "data":
            others = [c for c in stray if c != "pre"]
            if rec["children"].count("pre") != 1 or others:
                found = ", ".join(f"<{c}>" for c in rec["children"]) or "nothing"
                errors.append(
                    f"{where}: its body is one <pre> holding the text "
                    f"(escape < and >), found {found}"
                )
            if rec["text"]:
                errors.append(
                    f"{where}: text outside its <pre> — the whole body goes inside it"
                )
        elif content == "items":
            if stray:
                errors.append(
                    f"{where}: admits only {sorted(allowed)} children, found {stray}"
                )
            if rec["text"]:
                errors.append(f"{where}: loose text between its items isn't allowed")
    return errors


def reference_errors(lf_elements: list, registry: dict, ids: set) -> list:
    """An attribute the registry marks as naming another element (x-refers) that names
    nothing this version holds. The reader follows it, so a typo is a reference to
    nowhere and the markup around it is perfectly well-formed — visible to them and to
    nobody else. Asked of the version rather than of a fragment: a reply's markup
    carries no page to check against, and one of its widgets pointing at the version
    beside it is exactly right."""
    return [
        f'{at(rec)}: {attr}="{target}" names no element in this version'
        for rec in lf_elements
        for attr in registry.get(rec["tag"], {}).get("x-refers", [])
        if (target := rec["attrs"].get(attr)) and target not in ids
    ]


def language_class_errors(blocks: list, known: list) -> list:
    """A `class="language-…"` the runtime won't honor: the class somewhere other than
    <pre><code>, or a word the layer doesn't speak. Neither is visible to the user — a
    class in the wrong place and a misspelt language both render as an ordinary
    uncolored block — so the failure is routed to the one party who can still fix it,
    which is whoever wrote the word. A widget declaring a language is held to the same
    list one attribute over (declared_word_errors); this half is the plain HTML block,
    which belongs to no widget at all.

    The list is indexed rather than tested: a layer naming none colors none, so a word
    declared to it is still one it can't honor, and the placement rule never depended on
    the list at all. A check whose two failures are both invisible on the page is the
    last one that should be able to pass by finding nothing to check against."""
    errors = []
    for block in blocks:
        where = f'class="language-{block["lang"]}" (line {block["line"]})'
        if (block["tag"], block["parent"]) != ("code", "pre"):
            errors.append(
                f"{where}: only <pre><code> is colored, found <{block['tag']}> in "
                f"<{block['parent'] or 'nothing'}> — move it, or use <lf-code language=…> "
                f"for a walkthrough"
            )
        elif block["lang"] not in known:
            errors.append(
                f"{where}: not a language this page's layer speaks — known: {known}"
            )
    return errors


# A word a widget declares that its layer has to know, as three things: the x- key
# naming the attribute that carries it, the layer-wide fact listing the words the layer
# has, and what the layer does with one that is on the list.
#
# One reader for both, because they are one failure — a misspelt language colors nothing
# and a misspelt tone paints nothing, and each renders as a page that otherwise looks
# perfectly well, so nobody downstream can see it: not the user, who never knew the chip
# was meant to be red. The one party who can still fix it is whoever wrote the word, and
# this is where they are told. A class would have been the same words with nobody
# checking them.
#
# The list is the layer's ($languages, $tones) rather than any widget's, and which
# attribute carries the word is the entry's to say — so nothing here knows which widget
# takes a language or a tone, and the thirteenth that colors something is covered the day
# it declares one. A third such word is a row in this table.
DECLARED_WORDS = (
    ("x-language", "$languages", "a language this page's layer speaks"),
    ("x-tone", "$tones", "a tone this page's layer paints"),
)


def declared_word_errors(lf_elements: list, registry: dict) -> list:
    """Every word the page declares that its layer has no entry for (DECLARED_WORDS)."""
    errors = []
    for key, fact, honored in DECLARED_WORDS:
        known = registry[fact]["names"]
        for rec in lf_elements:
            attr = (registry.get(rec["tag"]) or {}).get(key)
            word = rec["attrs"].get(attr) if attr else None
            if word is not None and word not in known:
                named = f'{attr}="{word}"'
                errors.append(f"{at(rec, named)}: not {honored} — known: {known}")
    return errors


def line_ref_errors(lf_elements: list, registry: dict) -> list:
    """A declared line reference outside the body it points into. x-lines names the
    attributes holding 1-based line numbers or ranges of the nearest data body — the
    element's own, or its holder's (lf-note's `at` anchors in its lf-code). The
    modules miss silently in both directions — a reversed range paints nothing, a
    note past the end docks at the block's foot — and version-to-version drift is
    exactly how one goes stale, so the door refuses what no reader would ever see."""
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"]) or {}
        for attr in entry.get("x-lines", ()):
            value = rec["attrs"].get(attr)
            if value is None:
                continue
            # Shape is the schema's question and already answered (widget_errors
            # reports a malformed value); this gate owns only the bounds, so a
            # value it cannot read is one it stands aside from rather than a
            # traceback that eats every other error.
            if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*", value):
                continue
            holder = rec if rec["body"].strip() else rec.get("holder") or {}
            # The modules' own trim: leading blank lines and trailing whitespace
            # are the source's furniture, not lines.
            body = re.sub(r"\s+$", "", re.sub(r"^\n+", "", holder.get("body", "")))
            count = len(body.split("\n"))
            where = at(rec, f'{attr}="{value}"')
            for part in value.split(","):
                lo, _, hi = part.partition("-")
                lo, hi = int(lo), int(hi) if hi else int(lo)
                if hi < lo:
                    errors.append(f"{where}: range {part} runs backwards")
                elif not 1 <= lo <= count or hi > count:
                    errors.append(
                        f"{where}: line {part} is outside the {count}-line body"
                    )
    return errors


def enclosing_widgets(rec: dict):
    """The lf-* elements standing around one, innermost first."""
    rec = rec["holder"]
    while rec is not None:
        yield rec
        rec = rec["holder"]


def retirement_slots(registry: dict) -> dict:
    """holder tag → {outcome verb → the tags that leave the page under it}: every
    holder/slot pair `x-retired-when` relates, the slot naming the outcome and
    `x-parent` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or not entry.get("x-retired-when"):
            continue
        outcome = entry["x-retired-when"]
        for holder in entry["x-parent"]:
            slots.setdefault(holder, {}).setdefault(outcome, []).append(tag)
    return slots


def enclosing_slot(rec: dict, registry: dict):
    """The innermost slot an element stands in and the widget whose decision
    retires it, or None where it stands in neither. The element itself counts:
    a slot's own id is the slot's, not the widget's around it."""
    for node in (rec, *enclosing_widgets(rec)):
        entry = registry.get(node["tag"]) or {}
        holder = node["holder"]
        if (
            entry.get("x-retired-when")
            and holder
            and holder["tag"] in entry["x-parent"]
        ):
            return node, holder
    return None


def retirement_holders(parser: _StructParser, registry: dict) -> list:
    """Every widget the page carries that a decision can settle, and what each
    outcome would retire: {"id", "tag", "retires": {outcome → ids},
    "withdrawn_as"}. An id belongs to a slot when the slot stands anywhere
    around it, found by walking out of the id rather than down from the widget,
    so a paragraph three elements deep in a slot is read like the slot's own.

    Every outcome the registry declares gets a set, carried in the markup or
    not: a suggestion that only inserts still retires its wrapper when accepted,
    and a structure built from the slots the page happens to hold would have
    nothing to license that with."""
    declared = retirement_slots(registry)
    holders = {}
    for rec in parser.lf_elements:
        wid = rec["attrs"].get("id")
        if wid and rec["tag"] in declared:
            holders[wid] = {
                "id": wid,
                "tag": rec["tag"],
                "retires": {outcome: set() for outcome in declared[rec["tag"]]},
                "withdrawn_as": registry[rec["tag"]].get("x-withdrawn-as"),
            }
    for wid, rec in parser.within.items():
        pair = enclosing_slot(rec, registry) if rec else None
        if pair is None:
            continue
        slot, holder = pair
        held = holders.get(holder["attrs"].get("id"))
        if held is not None:
            held["retires"][registry[slot["tag"]]["x-retired-when"]].add(wid)
    return list(holders.values())


def suggestion_errors(lf_elements: list, registry: dict, comment_ids: set) -> list:
    """What the registry's schema can't say about a suggestion: it holds at most
    one of each slot and at least one of them, it doesn't nest, and `resolves`
    names a comment that exists. A family lint, named for its family — and it
    reads even its own slots out of the merged registry, so a layer that adds
    one to the family is linted for it rather than around it."""
    tags = {
        tag
        for slot_tags in retirement_slots(registry).get("lf-suggestion", {}).values()
        for tag in slot_tags
    }
    errors = []
    for rec in lf_elements:
        if rec["tag"] != "lf-suggestion":
            continue
        where = at(rec, f"id={rec['attrs'].get('id')!r}")
        if any(w["tag"] == "lf-suggestion" for w in enclosing_widgets(rec)):
            errors.append(f"{where}: suggestions don't nest")
        carried = [tag for tag in rec["children"] if tag in tags]
        if not carried:
            errors.append(
                f"{where}: needs a <lf-old> (what it replaces), a <lf-new> "
                f"(what it proposes), or both"
            )
        for tag in sorted(tags):
            if carried.count(tag) > 1:
                errors.append(
                    f"{where}: carries {carried.count(tag)} <{tag}> children, one at most"
                )
        resolves = rec["attrs"].get("resolves")
        if resolves and resolves not in comment_ids:
            errors.append(f"{where}: resolves={resolves!r} names no comment in the log")
    return errors


def retirable_ids(
    holders: list, events: list, dropped: set, outcomes: dict, spk: dict
) -> set:
    """Ids the previous version's settled widgets let the next one drop, given
    what it actually dropped. A logged outcome settles a widget: the slots
    declaring that outcome leave the page, and the widget holding them goes with
    them, its question answered — a suggestion accepted retires the markup it
    replaced, rejected retires the proposal, and either retires the wrapper.
    Which widgets those are is the registry's relation rather than a list here
    (`retirement_holders`), so a family a layer adds is licensed the day it is
    declared instead of failing three versions in with "ids dropped".

    A widget no one has answered can still be withdrawn — no decision rested on
    it — where the entry says what withdrawing it means (`x-withdrawn-as`:
    taking a suggestion back leaves the page as a `reject` would). That is the
    author asserting a state the user never gave, so it is hedged where a
    decision is not: only whole, every id under the slots it retires going with
    the widget, so a version can't quietly keep an unanswered proposal as
    settled content — and not while an unresolved thread is anchored in any of
    it. What the withdrawal doesn't name stays: the markup a pending deletion
    wraps is the page's own, and only the user's own `accept` consents to losing
    it.

    The outcomes are replay's own (`decisions`, folded over the version these
    widgets are on), so a decision a later version restated away settles
    nothing here either — replay hands the widget back as pending, and the
    slots stay needed. `spk` is that same version's reading, so the thread half of
    this answer stands on the page the outcomes were folded against."""
    anchored = anchored_ids(events, spk)
    licensed = set()
    for holder in holders:
        answered = holder["id"] in outcomes
        outcome = outcomes[holder["id"]] if answered else holder["withdrawn_as"]
        retires = holder["retires"].get(outcome)
        if retires is None:
            continue
        whole = {holder["id"]} | retires
        if not answered and (whole & anchored or not retires <= dropped):
            continue
        licensed |= whole
    return licensed


def action_subjects(event: dict, byid: dict, now: dict, registry: dict) -> list:
    """What an action was *about*, at the finest grain the vocabulary allows.

    An action names the widget that sent it, but on a container that is rarely
    the thing decided: a `move` names the board and carries {card, to, index}, a
    `choose` names the group and carries {option}. So the subjects are the parts
    of the widget its detail points at, minus containers (x-content "items") —
    the column a card landed in is where the decision *put* it, not what it was
    about, and holding a version to a column's contents would refuse it for
    adding an unrelated card. Where a detail names no part of the widget (an
    `edit` carries text, an `accept` carries nothing) the widget is its own
    subject.

    No verb is interpreted here. A detail value counts when it names an element
    *inside the widget that sent the action* — not merely an id the page has
    somewhere, which would let a literal like "approved" collide with an element
    that happens to be called that."""
    widget = event["widget"]
    parts = action_rests_on(event, now)[1:]
    subjects = [
        v
        for v in parts
        if registry.get(byid.get(v, {}).get("tag"), {}).get("x-content") != "items"
    ]
    return subjects or [widget]


def note_floors(events: list, field: str, upto=None) -> dict:
    """id named by a note field → the last version that named it in the window.

    `restated` and `reports` are the reviewer and agent channels' two readings
    of the same durable relation: one version's note answers ids, and that
    answer lasts without being repeated. Keeping their filter-and-max fold here
    prevents the channels from disagreeing about how a window is applied.
    """
    at = {}
    for event in events:
        if event["kind"] == "note" and (upto is None or event["version"] <= upto):
            for named in event.get(field, []):
                at[named] = max(at.get(named, 0), event["version"])
    return at


def retractions(events: list, upto=None) -> dict:
    """id → the version whose `restated` note last took back its decision."""
    return note_floors(events, "restated", upto)


def report_absorptions(events: list, upto=None) -> dict:
    """report event id → the version whose `reports` note last answered it."""
    return note_floors(events, "reports", upto)


def action_rests_on(event: dict, spk: dict) -> list:
    """The runtime's restsOn, read the same way here: the sending widget plus
    every detail id it contains. This is the one key space for liveness — fold
    survival, retraction floors, and the earning of `restated` all go through
    it, in both runtimes — while `action_subjects` stays the words gate's finer,
    subject-keyed view of the same containment. Two views, one containment test;
    a third keying would fork the JS/Python twin a third way."""
    widget = event["widget"]
    parts = [
        v
        for field in event["detail"].values()
        for v in (field if isinstance(field, list) else [field])
        if isinstance(v, str) and widget in spk.get(v, EMPTY).within
    ]
    return [widget, *parts]


def action_retracted(event: dict, floors: dict, spk: dict) -> bool:
    """Whether a retraction has taken this action back: true when any id it rests
    on carries a floor from a version later than the one the action was made on.

    One predicate for every reader of liveness — the fold's survival test, the
    words gate's, and the thread a decision settles — because a decision the log
    has taken back has to be absent everywhere at once. It was written out twice
    and a third reader went without: `build_threads` settled a thread on an accept
    and never asked, so a suggestion the next version rewrote came back pending
    with the thread it had answered still filed away, and the user was never asked
    the question again."""
    return any(floors.get(i, 0) > event["version"] for i in action_rests_on(event, spk))


# A verb with no declared record form (accept/reject — the honoring version
# retires the wrapper, so there is no markup value to compare) has no record.
NO_RECORD = object()


class StateProjection(NamedTuple):
    """The durable widget state declared by one page and log window."""

    actions: dict
    reports: dict
    desired: dict
    report_answers: dict


def state_coordinate(widget: str, unit: str, spec: dict) -> tuple[str, str, str]:
    """The one identity of a durable fact: its owner, fold unit, and local facet."""
    return widget, unit, spec["facet"]


def state_projection(
    events: list,
    byid: dict,
    spk: dict,
    registry: dict,
    upto,
    floors: dict | None = None,
) -> StateProjection:
    """Project both durable channels onto owner-unit-facet coordinates.

    `actions` holds the last surviving reader action per coordinate. `reports`
    keeps every live report there because publishing retires all of them.
    `desired` gives a reader action precedence over provisional agent news on
    the same coordinate.

    Both channels share one classification pass over the window. They end by
    different facts: undo or a retraction floor ends an action, while a note
    naming a report ends that report. `report_answers` retains the answer
    version for gate diagnostics after an absorbed report leaves the live maps.
    A report or action whose widget the markup lacks resolves no declaration
    and stands nowhere."""
    if floors is None:
        floors = retractions(events, upto)
    withdrawn = taken_back(events)
    absorbed = report_absorptions(events, upto)
    actions = {}
    reports = {}
    report_answers = {}
    for event in events:
        if event["kind"] == "action":
            channel = "x-state"
        elif event["kind"] == "report":
            channel = "x-report"
        else:
            continue
        if upto is not None and event["version"] > upto:
            continue
        rec = byid.get(event["widget"])
        if rec is None:
            continue
        spec = (registry.get(rec["tag"], {}).get(channel) or {}).get(event["action"])
        if not spec:
            continue
        unit = (
            event["widget"]
            if spec["unit"] == "widget"
            else event["detail"].get(spec["unit"])
        )
        if not isinstance(unit, str):
            continue
        coordinate = state_coordinate(event["widget"], unit, spec)
        entry = (event, spec)
        if event["kind"] == "action":
            if event["id"] in withdrawn or action_retracted(event, floors, spk):
                continue
            actions[coordinate] = entry
        elif answered_at := absorbed.get(event["id"]):
            report_answers[coordinate] = max(
                report_answers.get(coordinate, 0), answered_at
            )
        else:
            reports.setdefault(coordinate, []).append(entry)

    desired = {coordinate: entries[-1] for coordinate, entries in reports.items()}
    desired.update(actions)
    return StateProjection(
        actions,
        reports,
        desired,
        report_answers,
    )


def recorded_owner(unit: str, byid: dict, spk: dict, registry: dict):
    """The nearest enclosing widget whose registry entry records state."""
    for candidate in reversed(spk.get(unit, EMPTY).within):
        rec = byid.get(candidate)
        entry = registry.get(rec["tag"], {}) if rec else {}
        if any(spec.get("record") for _, _, spec in state_specs(entry)):
            return candidate
    return None


def markup_facet(unit: str, spec: dict, byid: dict, spk: dict, registry: dict):
    """What one version's markup shows for a unit's declared record form: every
    element inside it carrying the attribute, the unit's own attribute's value,
    the declared container enclosing it, or its body's words — the empty list
    where the markup shows no pick.

    An attribute record is a set, never one element: a group taking several
    picks marks several options, and one shape for both is what lets the fold
    compare like with like whatever the group allows."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    if record["kind"] == "attribute":
        return sorted(
            oid
            for oid, orec in byid.items()
            if record["attr"] in orec["attrs"]
            and unit in spk.get(oid, EMPTY).within[:-1]
            and recorded_owner(oid, byid, spk, registry) == unit
        )
    if record["kind"] == "value":
        rec = byid.get(unit)
        return rec["attrs"].get(record["attr"]) if rec else None
    if record["kind"] == "position":
        enclosing = [
            i
            for i in spk.get(unit, EMPTY).within[:-1]
            if byid.get(i, {}).get("tag") == record["within"]
        ]
        return enclosing[-1] if enclosing else None
    return collapse(spk.get(unit, EMPTY).words)  # "body"


def folded_facet(e: dict, spec: dict):
    """The state the folded action left: the detail field the record declares,
    collapsed the way `spoken` collapses where it compares against words, and
    sorted where it compares against a set of marked elements."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    value = e["detail"].get(record["value"])
    if record["kind"] == "body":
        return collapse(str(value))
    if record["kind"] == "attribute":
        return sorted(value)
    return value


def page_projection(html: str, events: list, registry: dict, upto):
    """Project one page's markup and log window through one construction.

    `record_lag`, `page state`, and the passage readings used by `leaf comment`
    and `version check` therefore cannot drift on declarations, floors, or the
    window. The parser and spoken reading travel with the projection for callers
    that compare it with authored markup."""
    parser = parse_structure(html)
    spk = spoken(html, registry)
    return (
        state_projection(events, parser.by_id, spk, registry, upto),
        parser,
        spk,
    )


def rewritten_bodies(actions: dict) -> dict:
    """id → (verb, text): the user's standing rewrite of each element whose
    registry entry records a verb as the body (x-state record kind "body"), as
    replay leaves it. The action projection is read here for the one record kind
    whose state is words rather than markup, so the passage reading can hold
    those words where the authored body was."""
    return {
        unit: (e["action"], e["detail"][spec["record"]["value"]])
        for (_widget, unit, _facet), (e, spec) in actions.items()
        if (spec.get("record") or {}).get("kind") == "body"
    }


def decisions(actions: dict, registry: dict) -> dict:
    """widget id → the accept/reject its action projection leaves standing.

    Which verbs decide is the registry's word too: `x-retired-when` names the
    outcome under which an element leaves the page, so nothing here knows a
    widget or verb by name."""
    # Widgets only: $keys spells its members in the x- keys' own names, so a sweep
    # over every entry would take its paragraph on x-retired-when for a verb.
    deciding = {
        e["x-retired-when"]
        for tag, e in registry.items()
        if tag.startswith("lf-") and "x-retired-when" in e
    }
    return {
        unit: e["action"]
        for (_widget, unit, _facet), (e, _) in actions.items()
        if e["action"] in deciding
    }


def record_lag_entries(projection: StateProjection, byid, spk, registry: dict) -> list:
    """Coordinates whose markup lags the user's standing state — the record debt a
    log-less reader would miss. Advice, never errors: a version is free to stay
    silent (replay resolves it), but references/page-authoring.md's "Honoring
    reader state" obligation needs a feedback loop, and a finished page's final
    version is the page that has
    to read right without the log. One comparison, rendered twice: `record_lag`
    speaks it, `page state` ships it — the same entries, so the advice a check
    prints and the debt an agent queries cannot disagree."""
    entries = []
    for coordinate in sorted(projection.desired):
        widget, unit, facet = coordinate
        e, spec = projection.desired[coordinate]
        if unit not in byid:
            continue
        f_cur = markup_facet(unit, spec, byid, spk, registry)
        f_log = folded_facet(e, spec)
        if f_cur is NO_RECORD or f_cur == f_log:
            continue
        entries.append(
            {
                "widget": widget,
                "unit": unit,
                "facet": facet,
                "channel": e["kind"],
                "action": e["action"],
                "log": f_log,
                "markup": f_cur,
            }
        )
    return entries


def record_lag(
    projection: StateProjection, byid: dict, spk: dict, registry: dict
) -> list:
    """`record_lag_entries` as advice lines, for check and the transcript."""
    lag = []
    for n in record_lag_entries(projection, byid, spk, registry):
        who = "the log records" if n["channel"] == "action" else "a report records"
        lag.append(
            f"`{n['unit']}` ({n['facet']} facet): {who} {n['action']} → "
            f"{n['log']!r}; "
            f"the markup still shows {n['markup']!r}"
        )
    return lag


def asking(attrs: dict, when: dict) -> bool:
    """The runtime's `asking`: every attribute `when` names holds one of the
    values that ask, a flag's two values being its presence and its absence."""
    return all(
        any(
            (attr in attrs) == value
            if isinstance(value, bool)
            else attrs.get(attr) == value
            for value in values
        )
        for attr, values in (when or {}).items()
    )


def replayed_attrs(rec: dict, projection: StateProjection) -> dict:
    """An element's attributes under the declared standing projection: authored
    markup overlaid with every surviving value record. The user's action holds
    one coordinate over a standing report, and independent facets coexist."""
    attrs = rec["attrs"]
    unit = attrs.get("id")
    if not unit:
        return attrs
    held = [
        winner
        for coordinate, winner in projection.desired.items()
        if coordinate[1] == unit
    ]
    for e, spec in sorted(held, key=lambda item: item[0]["seq"]):
        if (spec.get("record") or {}).get("kind") == "value":
            attrs = {**attrs, spec["record"]["attr"]: folded_facet(e, spec)}
    return attrs


def answered_ask(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
) -> bool:
    """The runtime's `answeredAsk`: a verb that records as an attribute answers
    on the record the replayed page carries — the fold's where an action
    survives on the unit, the authored markup's otherwise, so a version that
    honors a pick reads as answered with no log at all and a pick the reader
    cleared reads as open again. Any other verb answers only through its own
    fold entry."""
    unit = rec["attrs"].get("id")
    for verb, spec in (entry.get("x-state") or {}).items():
        held = projection.actions.get(state_coordinate(unit, unit, spec))
        record = spec.get("record")
        if record and record["kind"] == "attribute":
            if held and (held[1].get("record") or {}).get("kind") == "attribute":
                facet = folded_facet(*held)
            else:
                facet = markup_facet(unit, spec, byid, spk, registry) if unit else []
            if facet:
                return True
        elif held and held[0]["action"] == verb:
            return True
    return False


def quoted_in(rec: dict, registry: dict) -> bool:
    """The runtime's `quoted`: inside an element the registry marks x-exhibit,
    a widget is a mention rather than a use, and asks nothing.

    The holder chain answers it, which is the walk `enclosing_slot` makes and the
    one the runtime makes over the DOM. Asked of `spoken` instead, containment
    became a question about the page's words: the reading that says what stands
    around one widget walks every character of the version to do it, so an action
    POST on a 90KB page spent forty milliseconds finding out what a single id sat
    in. It reads a record rather than an id for the same reason the runtime takes
    an element — an element the author left unnamed stands where it stands."""
    return any(
        (registry.get(node["tag"]) or {}).get("x-exhibit")
        for node in enclosing_widgets(rec)
    )


def page_asks(parser, projection, byid, spk, registry: dict, dropped: set) -> list:
    """The published page's standing asks — the list the banner counts and the
    `n`/`p` walk steps, read from the file and the log instead of the DOM. An
    instance asks when its replayed attributes match its entry's `when`;
    quoted material asks nothing; an instance a decision dropped from the page
    (`dropped`: ids under retired slots, and decided-empty ids, from the passage
    reading) asks nothing either, the way the runtime's own list skips what
    `settledAway` hides; answered is what x-state already declares
    (`answered_ask`)."""
    asks = []
    for rec in parser.lf_elements:
        entry = registry.get(rec["tag"]) or {}
        awaits = entry.get("x-awaits")
        if not awaits:
            continue
        unit = rec["attrs"].get("id")
        if unit and unit in dropped:
            continue
        if quoted_in(rec, registry):
            continue
        if not asking(replayed_attrs(rec, projection), awaits.get("when")):
            continue
        if answered_ask(rec, entry, projection, byid, spk, registry):
            continue
        asks.append({"id": unit, "tag": rec["tag"], "thread": None})
    return asks


def thread_asks(events: list, registry: dict, settled: set) -> list:
    """Asks standing in thread markup — the runtime's `answeredThreadAsk` read
    from the log. A fragment is frozen: no version answers it and no `restated`
    retracts it, so every action on its widgets stands (no floors, no window).
    Only a widget with an action channel asks in a thread at all, and `until`
    holds a matching ask open until the reader has posted the verb it names.

    `settled` is the root ids of the closed threads, whose asks went with them —
    the question was the thread's, and the panel's own reading takes a closed
    thread's mark off the page for the same reason. Without it, a question the
    agent asked and then withdrew by resolving stays on the banner's count for
    the life of the page, and the walk that steps to it lands in a shut
    disclosure."""
    structure = thread_structure(events)
    asks, records, byid, spk = [], [], {}, {}
    thread_of = {}
    for e in events:
        if e["kind"] == "comment":
            thread_of[e["id"]] = e["id"]
        elif e["kind"] == "reply":
            thread_of[e["id"]] = thread_of[e["parent"]]
        else:
            continue
        markup = e.get("markup")
        if not markup or thread_of[e["id"]] in settled:
            continue
        frag = structure.fragments[e["id"]]
        byid.update(frag.by_id)
        spk.update(spoken(markup, registry))
        records.extend((thread_of[e["id"]], rec) for rec in frag.lf_elements)
    projection = state_projection(events, byid, spk, registry, None, {})
    for thread, rec in records:
        entry = registry.get(rec["tag"]) or {}
        awaits = entry.get("x-awaits")
        if not awaits or not entry.get("x-state"):
            continue
        unit = rec["attrs"].get("id")
        if quoted_in(rec, registry):
            continue
        attrs = replayed_attrs(rec, projection)
        if not asking(attrs, awaits.get("when")):
            continue
        until = awaits.get("until")
        if until and asking(attrs, until["when"]):
            answered = any(
                action["widget"] == unit and action["action"] == until["verb"]
                for action, _spec in projection.actions.values()
            )
        else:
            answered = answered_ask(rec, entry, projection, byid, spk, registry)
        if not answered:
            asks.append({"id": unit, "tag": rec["tag"], "thread": thread})
    return asks


def unpointable_blocks(parser: _StructParser) -> list:
    """Blocks a user will aim at whole that no anchor can name. Advice, never a
    gate, in the same register as record_lag:
    references/page-authoring.md's "Stable anchors" states the id rule, and this
    is its feedback loop. The page that introduced item anchoring hit this
    failure itself — its code blocks carried no ids, so a comment aimed at one fell
    through to the enclosing section and read as the gesture being broken rather
    than the page being bare, and nothing anywhere said so.

    A section or article is named outright; a block below one only where its aim
    escapes to a sectioning element. The ancestor's tag stands in for tightness —
    a figure around a table, a card around a pre — which no static read can
    measure, so a page-wide <div id> also passes for aim enough and the advice
    stays quiet. Undercounting is the right error for advice: a miss costs one
    aim landing wide, noise costs the register its authority."""
    lines = []
    for block in parser.bare_blocks:
        where = at(block)
        under = block["under"]
        if block["tag"] in ("section", "article"):
            lines.append(
                f"unpointable — {where} has no id, so no comment or reading "
                f"position can hold to it"
            )
        elif under is None:
            lines.append(
                f"unpointable — {where} has no id, nor anything enclosing it, "
                f"so no comment can name it"
            )
        elif under[0] in SECTIONING_TAGS:
            lines.append(
                f"unpointable — {where} has no id, so a comment aimed at it "
                f"lands on the whole of #{under[1]}"
            )
    return lines


def restatement_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    prev_num: int,
    registry: dict,
    projection: StateProjection,
    floors: dict,
) -> list:
    """The other half of the id-survival rule. That one keeps a republish from
    dropping the anchors a user hung on the page; this one keeps it from
    dropping the decisions they recorded on it. CLAUDE.md carries why the log
    outranks the markup and what that cost.

    The runtime reconciles every standing action onto every later version, so a
    version cannot revise what a user acted on: reconciliation would paint their
    recorded state back over the revision and the new words would reach nobody. A
    version that means to revise says so — `restated` on what it rewrote — and one that
    changes those words in silence is refused here. An unearned `restated` is an
    error too: a decision thrown away for nothing, and, left unchecked, the
    one-word ritual that would make this gate meaningless.

    The comparison is the words each version says (`spoken`), because words are
    what a decision is about. Re-indenting a draft, marking the picked option
    `chosen`, or relocating a card the user already moved is not a revision,
    and neither is writing their own edit back — a version that says what they
    said is agreeing with them.

    Words are one divergence kind; declared state is the other. For each verb
    the registry declares (x-state), the fold gives the user's standing
    state per owner, unit, and facet, and a version whose markup actively changes that unit's
    record away from both the previous version's and the fold is refused the
    same way a silent rewrite of words is. Writing the folded state is the
    state-level echo (honoring); re-emitting the previous version's state is
    blessed silence, which reconciliation resolves; a unit with no surviving folded
    action is exempt — never decided, or retracted back to the author. And
    `restated` is earned by either divergence kind: a words-unchanged
    relocation earns it at the unit even though no subject's words moved."""
    errors = []
    declared = cur.restated
    # Retractions up to prev — never this version's own, which is what it is
    # here to declare, so re-checking a published version reaches the same
    # verdict as checking it did.
    byid = cur.by_id

    decided = {}  # subject id → the actions resting on it
    for e, _spec in projection.actions.values():
        for subject in action_subjects(e, byid, now, registry):
            if subject in was:
                decided.setdefault(subject, []).append(e)

    # The state gate, beside the words gate: one gate, two divergence kinds.
    prev_byid = prev.by_id
    facet_earned = set()
    for coordinate in sorted(projection.actions):
        _widget, unit, _facet = coordinate
        e, spec = projection.actions[coordinate]
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_prev = markup_facet(unit, spec, prev_byid, was, registry)
        if f_cur is NO_RECORD or f_cur == f_prev:
            continue  # no record form, or no active change — replay resolves silence
        f_fold = folded_facet(e, spec)
        if f_cur == f_fold:
            continue  # writing the folded state is honoring: the state-level echo
        if unit in declared:
            facet_earned.add(unit)
            continue
        where = at(rec, f"id={unit!r}")
        errors.append(
            f"{where}: its state changed under the user's decision — the markup "
            f"shows {f_cur!r} where their {e['action']} (on v{e.get('version', 0)}) "
            f"left {f_fold!r}. Their decision is what the page shows, so this state "
            f"would never reach them — add `restated` to retract it and ask again, "
            f"or leave it as v{prev_num} had it."
        )

    for sid, rec in sorted(byid.items()):
        live, restated = decided.get(sid, []), sid in declared
        # A version that writes back what the user themselves recorded is
        # agreeing with them, not overruling them — an honored `edit` is the
        # commonest and most correct thing an author does with a draft, and the
        # gate has to stay quiet for it or it fires on nearly every version and
        # teaches authors to reach for `restated` by reflex. No verb is special-
        # cased: it is enough that the words on the page are words the user
        # sent.
        echoed = {
            collapse(str(v))
            for e in live
            for v in e["detail"].values()
            if isinstance(v, str)
        }
        said = now.get(sid, EMPTY).words
        changed = sid in was and said != was[sid].words and said not in echoed
        where = at(rec, f"id={sid!r}")
        # `restated` is earned by either divergence kind — words on the leaf, or
        # declared state at the unit — else a words-unchanged relocation would
        # be refused both with the attribute and without it.
        if restated and not ((live and changed) or sid in facet_earned):
            # An already-retracted widget is the case an author lands on by being
            # careful — carrying the attribute forward the way state used to have
            # to be carried — so it gets its own answer rather than the
            # never-decided one, which would read as if the user had done
            # nothing.
            if sid in floors:
                errors.append(
                    f"{where}: restated, but v{floors[sid]} already took that "
                    f"back — a retraction is recorded when it is published and holds "
                    f"without being repeated. Drop the attribute."
                )
            else:
                why = (
                    f"its words are unchanged since v{prev_num}"
                    if live
                    else "the user has recorded nothing on it"
                )
                errors.append(
                    f"{where}: restated, but there is nothing to retract — {why}. "
                    f"Drop the attribute; `restated` discards their decision."
                )
        elif changed and live and not restated:
            did = ", ".join(f"{e['action']} on v{e.get('version')}" for e in live[-3:])
            errors.append(
                f"{where}: its words changed, and the user has already acted "
                f"on it ({did}). Their decision is what the page shows, so these "
                f"words would never reach them — add `restated` to retract it and "
                f"ask again, or leave the text as v{prev_num} had it."
            )
    return errors


def report_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    registry: dict,
    projection: StateProjection,
) -> list:
    """The report gate, beside the reviewer one — the same shape with the
    precedence reversed. A report is a worker's provisional news: the runtime
    paints it onto every version published before it, and it stands only until
    a version answers it by id (`reports` on the note, the mirror of
    `restated`). Three outcomes are legal. Writing the reported state is
    honoring — publishing records it as absorption. Leaving the markup as the
    previous version had it is blessed silence — the report keeps painting.
    Marking the element `overruled` keeps this version's own state and retires
    the report, with the why in the note's text. What is refused is the fourth
    thing, markup that contradicts a standing report it never names: the drop
    must be the publisher's to adjudicate, never silent. And an unearned
    `overruled` is refused like an unearned `restated` — spent where nothing
    stands or where the markup agrees with the report, it is the reflex that
    would make the gate meaningless.

    Standing is read up to prev — never this version's own note, which is what
    publishing is about to record — so re-checking a published version reaches
    the same verdict as checking it did."""
    errors = []
    declared = cur.overruled
    byid = cur.by_id
    prev_byid = prev.by_id
    effective_standing = {
        coordinate: reports
        for coordinate, reports in projection.reports.items()
        if coordinate not in projection.actions
    }
    earned = set()
    for coordinate in sorted(effective_standing):
        _widget, unit, _facet = coordinate
        e, spec = effective_standing[coordinate][-1]
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_rep = folded_facet(e, spec)
        # Whether an `overruled` is earned is this version's markup against the
        # report, so it is settled ahead of the skip below: a unit the gate declines
        # to adjudicate would otherwise land in `unearned` and be told it writes the
        # reported state it in fact contradicts.
        if unit in declared and f_cur != f_rep:
            earned.add(unit)  # a named disagreement, whatever state it keeps
            continue
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        if f_cur == f_rep:
            continue  # honoring: publishing absorbs the report by id
        if f_cur == markup_facet(unit, spec, prev_byid, was, registry):
            continue  # blessed silence: the report keeps painting
        where = at(rec, f"id={unit!r}")
        who = e.get("agent", "a worker")
        errors.append(
            f"{where}: its markup contradicts a standing report — it shows "
            f"{f_cur!r} where {who}'s {e['action']} (report {e['id']}, on "
            f"v{e['version']}) left {f_rep!r}. Adjudicate it: write the reported "
            f"state to absorb the report, or add `overruled` to keep this state "
            f"and retire it (say why in the note)."
        )
    unearned = declared - earned
    # Where an attribute is spent past its version: which version already
    # answered the unit's reports, for the message that says to drop it.
    answered_at = {}
    if unearned:
        for (_widget, unit, _facet), version in projection.report_answers.items():
            answered_at[unit] = max(answered_at.get(unit, 0), version)
    for sid in sorted(unearned):
        rec = byid.get(sid)
        if rec is None:
            continue
        where = at(rec, f"id={sid!r}")
        if any(unit == sid for _widget, unit, _facet in effective_standing):
            errors.append(
                f"{where}: overruled, but this version writes the reported state — "
                f"that is absorption, which publishing records on its own. "
                f"Drop the attribute."
            )
        elif sid in answered_at:
            errors.append(
                f"{where}: overruled, but v{answered_at[sid]} already answered the "
                f"reports on it — an answer is recorded when it is published and "
                f"holds without being repeated. Drop the attribute."
            )
        else:
            errors.append(
                f"{where}: overruled, but no report is standing on it — there is "
                f"nothing to overrule. Drop the attribute."
            )
    return errors


def structure_errors(parser: _StructParser) -> list:
    """A fed parser's structural complaints, plus the tags it was left holding
    open at the end of its input."""
    errors = list(parser.errors)
    leftover = [(t, ln) for t, ln, *_ in parser.stack if t not in OPTIONAL_END]
    if leftover:
        errors.append(
            "unclosed tags: " + ", ".join(f"<{t}> (line {ln})" for t, ln in leftover)
        )
    return errors


def page_boundary_errors(parser: _StructParser) -> list:
    """Authored content lies under the same element the presentation gate owns."""
    errors = []
    direct = [line for line, is_direct in parser.main_elements if is_direct]
    if (
        len(parser.body_lines) != 1
        or len(parser.main_elements) != 1
        or len(direct) != 1
    ):
        errors.append(
            "the page must have one <main> directly under <body>; "
            f"found {len(parser.body_lines)} bodies, {len(parser.main_elements)} mains, "
            f"and {len(direct)} direct body mains"
        )
    if parser.outside_main:
        errors.append(
            "paintable authored content must stay inside the one <main> directly "
            "under <body>; found " + str(parser.outside_main)
        )
    return errors


def fragment_errors(parser: _StructParser, registry: dict) -> list:
    """Structural + registry validation of a markup fragment (an agent reply
    carrying widgets): the discussion-side analog of `version check`. The declared-word
    checks come along because the schema stopped carrying the lists: a reply's
    <lf-code language=…> is colored by the same tokenizer a version's is, and its chips
    are tinted by the same theme, and nothing else would now refuse either a word its
    layer doesn't know."""
    return (
        structure_errors(parser)
        + widget_errors(parser.lf_elements, registry)
        + language_class_errors(parser.language_blocks, registry["$languages"]["names"])
        + declared_word_errors(parser.lf_elements, registry)
        + line_ref_errors(parser.lf_elements, registry)
    )


def cmd_check(
    page_dir: Path,
    version,
    render: bool = False,
    transition_held: bool = False,
) -> int:
    if not transition_held:
        with flocked(transition_lock(page_dir)):
            return cmd_check(page_dir, version, render, transition_held=True)
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

    events = read_events(page_dir)
    registry = load_registry(page_dir)
    if registry is not None:
        errors.extend(widget_errors(parser.lf_elements, registry))
        errors.extend(reference_errors(parser.lf_elements, registry, parser.ids))
        errors.extend(
            language_class_errors(
                parser.language_blocks, registry["$languages"]["names"]
            )
        )
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

    # A /media/ reference the directory can't answer renders as a broken image.
    # The render gate would catch it as a 404, but that runs once a page; this
    # runs on every version, and a missing file is as deterministic as a missing
    # id.
    for ref in sorted(parser.media_refs):
        if not (page_dir / ref.lstrip("/")).is_file():
            errors.append(
                f"{ref} isn't in the page directory; `leaf page media` puts it there"
            )

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
    errors.extend(_overwide_elements(parser, column))

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


# ---------- check --render: the browser half of the gate ----------

# A probe here sweeps the document, and an x-shadow widget's words are not in it:
# querySelectorAll stops at the root boundary, and a climb by parentElement ends at the
# top of one. A reading written that way goes on working perfectly for every other widget
# and says nothing about that one, reporting nothing — so a probe whose subject can be in
# there follows the boundary both ways, as UNREAD_SYNTAX does for the diff's coloured
# code: 24 of the 41 coloured spans on pr-walkthrough. The rest sweep the document because
# the one root on the page holds none of what they ask about — no .lf-ui, no declared
# label, nothing past the column — which is a fact about today's widget, not about them.

RENDER_VIEWPORT = {"width": 1200, "height": 900}


# A widget that upgraded into no room to be read in. The floor is two numbers, and
# which of them a widget is held to is the widget's to declare (x-inline), because
# the two kinds are laid out by different rules: one reserves a region and the other
# is set among the words around it, where the box is the words and there is no width
# it was supposed to reach. Held to the region's floor, an inline widget fails for
# being short — a chip reading a price is 31px wide and correct, and the gate reported
# the author's own words as a collapse. The height floor is both kinds': a line of
# words is a line tall wherever it is laid out, which leaves a flattened chip caught.
#
# Declared, not read off the computed display, because a custom element with no rule
# left standing computes as inline: a theme that lost the chip block would silence the
# check that exists to catch it.
#
# [hidden] needs its own exclusion: hidden="until-found" (what a closed tab wears)
# resolves to content-visibility, which checkVisibility reports as visible while the
# box measures zero. That collapse is the point of a closed tab; the collapse being
# hunted here is the one nothing asked for.
# A control drawn where no reader can reach it. `TINY_BOXES` asks whether a widget got a
# box at all; this asks the question one level down, of the chrome inside it, and the
# difference is which failure each catches: a widget with no box is a widget that didn't
# render, and a control with a box its own container clips away is a widget that rendered
# and then hid its offer behind the frame it drew.
#
# It is the failure with no witness. Nothing overflows the page, so the sideways-scroll
# check is quiet; nothing is past the column, so that gate is quiet; the words are in a
# text node and technically selectable, so the unreachable-words gate is quiet. What the
# reader gets is a question with no visible way to answer it — which is exactly what
# shipped: a `choose` group in its row form states `width: 100%` on options that a
# live-page rule gives a 30px keyboard-address rail, and under the default box-sizing
# those are the row's width *plus* its padding, so every row ran 28px wider than the
# group whose `overflow: hidden` keeps its cells' hairlines square. The last cell is the
# pick mark, so all of it went over the edge: every row-form decision on every live page
# drew no dot, no "chosen", nothing. Paper and an exported copy were right throughout,
# the rail being live-pages-only, so no medium outside a browser could see it.
#
# Only where the clip cannot be scrolled away. A board's columns run past the board and
# are reached by scrolling, which is the arrangement rather than a fault, so an ancestor
# with something to scroll answers for what it holds. And only for controls the page
# offers (data-lf-offer), which keeps it clear of everything deliberately clipped to
# nothing — the paint pass's quiet words, the line counting a block's comments — whose
# whole point is to be read and not seen.
CLIPPED_CONTROLS = """() => {
    const out = [];
    for (const el of document.querySelectorAll('[data-lf-offer]')) {
        // checkOpacity too: a control faded to nothing is as unreachable as one clipped
        // away, and reporting it against a box it is inside would name the wrong fault.
        if (!el.checkVisibility({ checkOpacity: true }) || el.closest('[hidden]'))
            continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1 && b.height < 1) continue;
        // Where the clip is escaped rather than suffered. An absolutely-positioned
        // control whose containing block is above the clipping ancestor is painted
        // outside it on purpose, exactly as MISPLACED_BOXES' own resident is.
        if (getComputedStyle(el).position === 'absolute') continue;
        // Up to the body and no further: the document's own scrolling arrangement is
        // the page's, not a widget's. The runtime scrolls body rather than the
        // viewport so the panel has room beside it, which leaves <html> clipping and
        // with nothing of its own to scroll — so a walk that ran to the root reported
        // every control below the fold as hidden by the page it is on.
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
            const s = getComputedStyle(a);
            // Asked of the overflow value, per axis, and not of the scroll extent. A
            // box that clips always has something to scroll — that is what clipping
            // means — so `scrollWidth > clientWidth` is true of exactly the boxes this
            // is about and would wave every one of them through. What separates a
            // board, whose columns run past it and are reached by dragging, from a
            // group that swallowed its own pick marks is whether the box offers the
            // reader a way in: auto and scroll do, hidden and clip do not. Paint
            // containment clips both axes while `overflow` computes `visible`
            // (MISPLACED_BOXES reads the same fact for its ancestors), and it denies
            // the way in exactly where the axis has no scroller of its own.
            const contained = /paint|strict|content/.test(s.contain);
            const scrollX = s.overflowX === 'auto' || s.overflowX === 'scroll';
            const scrollY = s.overflowY === 'auto' || s.overflowY === 'scroll';
            const across = s.overflowX === 'hidden' || s.overflowX === 'clip'
                || (contained && !scrollX);
            const down = s.overflowY === 'hidden' || s.overflowY === 'clip'
                || (contained && !scrollY);
            if (across || down) {
                const f = a.getBoundingClientRect();
                const lost = Math.round(Math.max(
                    across ? Math.max(b.right - f.right, f.left - b.left) : 0,
                    down ? Math.max(b.bottom - f.bottom, f.top - b.top) : 0));
                if (lost > 1) {
                    out.push({ ctrl: el.className, id: el.id,
                               by: `<${a.tagName.toLowerCase()}${a.id ? ' id=' + a.id : ''}>`,
                               lost });
                    break;
                }
            }
            // And the walk stops at the first box the reader can move. Above a
            // scroller, a control outside an ancestor's rect is a control that ancestor
            // will show once the scroller is dragged, so measuring it there would
            // report a press that is one gesture away as one drawn nowhere.
            if ((s.overflowX !== 'visible' && !across)
                || (s.overflowY !== 'visible' && !down)) break;
        }
    }
    return out;
}"""


TINY_BOXES = """(widgets) => {
    const inline = new Set(Object.entries(widgets)
        .filter(([tag, entry]) => entry['x-inline'])
        .map(([tag]) => tag));
    return [...document.querySelectorAll('*')]
        .filter(el => el.tagName.toLowerCase().startsWith('lf-')
                   && el.textContent.trim()
                   && el.checkVisibility()
                   && !el.closest('[hidden]'))
        .map(el => ({ tag: el.tagName.toLowerCase(), id: el.id,
                      w: Math.round(el.getBoundingClientRect().width),
                      h: Math.round(el.getBoundingClientRect().height) }))
        .filter(box => box.h < 10 || (!inline.has(box.tag) && box.w < 40));
}"""


# An element the reader can see and no mark can be shown on. The gate presses no keys, so
# it never watches the ask walk paint a ring or a comment paint an outline. It can still
# read whether either would have had anywhere to land, which is the same fault one step
# earlier, before it turns into a mark nobody can see.
#
# The fault is a box that isn't there. An element with `display: contents` lays its
# children out in its parent's flow and generates no box of its own, so its rect is the
# empty one every rect starts as — zero-sized, at the document's origin, a real-looking
# answer naming a place it is not. An outline drawn on it draws nothing, and a scroll
# aimed at it lands at the top of the page: a page whose open asks were all suggestions
# answered `n` by appearing to do nothing at all, and that reached its reader rather than
# this gate. The runtime answers it by hanging a mark on the boxes an element shows
# through (shownParts) — which leaves one case that answer cannot reach, an element whose
# words are in no child element at all, where there is nothing to hang anything on.
#
# TINY_BOXES is next door and cannot see this: `checkVisibility()` is false for an element
# with no box, so the very elements at issue are the ones it filters out. Both readings are
# imported rather than restated, so what the gate refuses a handover for and what the page
# actually paints cannot come apart — the whole point of the pair being that there is one
# answer to where an element is.
UNMARKABLE_ITEMS = """async () => {
    const { shownBox, shownParts } = await import('/leaf.js');
    const HTML = 'http://www.w3.org/1999/xhtml';
    const found = [];
    for (const el of document.querySelectorAll('[id]')) {
        // The document's own elements, which is what an anchor can name and a walk can
        // step to. A rendered diagram's insides are none of those — they are one
        // picture, whose <lf-diagram> is the thing to point at and has a box of its
        // own — and they are full of shapes with ids and no layout box: every <marker>
        // in a mermaid flowchart's <defs> read as an item showing 11x11px of words.
        if (el.namespaceURI !== HTML) continue;
        if (el.closest('.lf-chrome')) continue;
        const box = shownBox(el);
        // Nothing on screen is nothing to mark, and nothing the reader can point at
        // either: a collapsed tab's contents, a slot a decision retired.
        if (!(box.width && box.height)) continue;
        if (shownParts(el).length) continue;
        found.push({ tag: el.tagName.toLowerCase(), id: el.id,
                     w: Math.round(box.width), h: Math.round(box.height) });
    }
    return found;
}"""


# Words the page shows that no user can select, and so no comment can be
# anchored on. A widget has two ways to leave them there, neither of which a
# static lint can see, and a page-local widget is where both keep happening.
#
# It can paint them: `content: attr(label)` puts a heading on screen and in no
# text node, so a selection can't cover it. The runtime says the attributes the
# registry marks x-says, and a widget's module says the rest (a chip row, a
# heading that doubles as a list's accessible name); either way, none of an
# element's own attribute values should still be reaching the reader as
# generated content.
#
# Or it can leave them under .lf-ui with nothing said about whose words they are.
# That class is the chrome face, a look — reaching for it as a general "this is
# chrome" marker is how a user ends up unable to comment on a heading they can
# see. The declaration is made where the label is written: data-lf-said for the page
# speaking, which the anchor pass reads over the box around it, data-lf-offer for a
# thing to work. So inside a widget, every word under .lf-ui has to be declared the
# page's, be a control's own label, or be the line the paint pass writes to say how
# many comments a block carries: that one is about the document rather than of it,
# which is the same reason it wears .lf-ui at all, and it lands inside a widget
# whenever a comment does. The comment panel is out of scope: a widget in a reply is
# markup frozen in the event log, not the document.
#
# And a declared label inside a form control is out of reach whatever it is marked:
# Chrome starts no pointer selection inside one, which is why `offer` builds a press
# as a span wearing role="button". A widget reaching for <button> anyway is the one
# mistake the marker cannot fix, so it is reported separately and says why.
UNREACHABLE_WORDS = """() => {
    const found = [];
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
    for (const el of document.querySelectorAll('*')) {
        if (!el.tagName.startsWith('LF-')) continue;
        const shown = ['::before', '::after']
            .map(w => getComputedStyle(el, w).content)
            .filter(c => c && c.startsWith('"'));
        for (const { name, value } of el.attributes)
            if (value.length > 1 && shown.some(c => c.includes(value)))
                found.push(`${at(el)} paints ${name}="${value}" rather than saying it`);
    }
    // A widget's chrome is the .lf-ui inside a lf-* element; the runtime's own
    // layer is appended to body and sits inside none of them.
    const widget = el => { for (let a = el; a; a = a.parentElement)
                               if (a.tagName.startsWith('LF-')) return a; };
    // The anchor pass's own rule: the nearest element that answers wins.
    const speaks = el => Boolean(el.closest('.lf-ui, [data-lf-said]')?.matches('[data-lf-said]'));
    const FORM = 'button, textarea, input, select';
    // Where a control's own words may sit: the control a widget declared (data-lf-offer,
    // asked instead of the role it wears, because lf-tabs overwrites `offer`'s
    // role="button" with "tab" and a Δ badge in a tab then read as a heading somebody
    // hid while the identical badge in a settled row read as chrome), or a native
    // control. `label` is among those because a radio and a checkbox have nowhere else
    // to put their words: a button holds its own, an input cannot, and HTML's answer is
    // an element beside it. lf-shot's flip is a checkbox, so that it keeps working in a page
    // whose script is gone. The line counting a passage's comments is one of these too —
    // the runtime builds it through `offer`, as a widget builds its own.
    const CONTROL = `${FORM}, label, [data-lf-offer]`;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim() || !el.closest('.lf-ui') || !widget(el)) continue;
        if (speaks(el) || el.closest(CONTROL)) continue;
        // .lf-quiet is words for a reader listening, clipped to nothing: not on
        // screen, so there is nothing here the eye can see and the pointer can't
        // reach — the failure this check exists for.
        if (el.closest('.lf-quiet')) continue;
        found.push(`${at(widget(el))} puts ${JSON.stringify(n.data.trim().slice(0, 40))} `
                   + `under .lf-ui, where no comment can reach it`);
    }
    // FORM rather than CONTROL: a <label>'s words select like any others, and a widget
    // that declared a box a control has said nothing about what element it is.
    for (const el of document.querySelectorAll('[data-lf-said]')) {
        if (!el.closest(FORM) || !widget(el)) continue;
        found.push(`${at(widget(el))} says ${JSON.stringify(el.textContent.trim().slice(0, 40))} `
                   + `inside a form control, where no selection can reach it`);
    }
    return [...new Set(found)];
}"""


# Every box is drawn somewhere, and something has to answer for where. Three
# readings ask it — of the column, of the room the page keeps for a wide widget,
# and of the container that was handed a box's overflow — and the last two are
# written beside the loops that make them.
#
# The column first: content set outside the one it belongs to. The
# sideways-scroll reading is the same question asked of the window, and the
# window is the wider of the two: the gate renders at 1200px against a 720px
# column, so 200px of margin on each side absorbs a spill that scrolls nothing.
# What is out there is the margin, where a suggestion's controls hang, and the
# user's own window is free to be narrower than this one — so a page that passed
# here scrolls sideways on the machine it was written for.
#
# The static lint asks about the column too (_column_width), and asks it of the
# stylesheet, because that is all a linter has: a width the author pinned in
# pixels, against a number parsed out of a max-width. This is the same column
# with a layout engine behind it, so it is measured rather than parsed, and it
# catches what no declaration states — a vw width, an unbreakable table, a
# widget that came out wider than its content.
#
# Two kinds of element answer for their own width and not to this, and both say
# so in their computed style. The margin has legitimate residents — a
# suggestion's controls, a sidenote, the hidden line the paint pass writes — and
# each is out there by its own declaration: placed absolutely, or floated clear
# of the column. Where the box sits is what separates a resident from a spill,
# which crosses the column's edge rather than clearing it, having started inside
# and run out. So a float that merely overflows is still reported, and a widget's
# own float inside the column (an option's .facts rail) is never in question.
#
# A resident answers for what it holds, which is why both readings are made up the
# ancestors and not of the element alone. A sidenote is prose, so it carries the
# <code>, links and emphasis any other prose does, and each of those inherits a box
# its parent put in the margin on purpose — named, one by one, as spilling out of a
# column none of them was ever in.
#
# And a scroll container answers for what it holds: a box inside one runs on
# past the clip and is drawn only as far as its container reaches, so a wide
# table's own rows would otherwise be reported as spilling out of the table that
# is containing them. What is left is the flow, which the column is the whole
# width of. A spill is reported once, at the outermost element that has it,
# because everything inside one inherits its box and would name the same fault a
# dozen times over.
MISPLACED_BOXES = """async () => {
    // shownBand is the runtime's own: what a container lets the reader see of what it
    // holds, or nothing where it shows all of it. Imported rather than restated, so the
    // band a handover is refused against and the band the page paints to cannot come
    // apart — and because `overflow` is one of three ways to draw nothing past an edge.
    // (TRAPPED_MARGINS reads `contain` for the neighbouring question: which margins a
    // formatting context keeps in.)
    const { shownBand } = await import('/leaf.js');
    const main = document.querySelector('main');
    if (!main) return [];
    const style = getComputedStyle(main), box = main.getBoundingClientRect();
    const left = box.left + parseFloat(style.paddingLeft);
    const right = box.right - parseFloat(style.paddingRight);
    // A widget the registry declares wide is answered for out here, the way an
    // absolutely-positioned resident is: standing past the column is what it was
    // declared for. What still has to hold is the page's own box — the room the layout
    // measured is the column's leftover, the rail a suggestion hangs in and the strip
    // the comment panel takes, and an exhibit over that edge is in the margin whether or
    // not the window happened to scroll for it. So the question is the same one, asked
    // against the wider bound: this gate renders at one viewport with no panel open, and
    // the reader's window is free to be narrower than this one.
    const bodyStyle = getComputedStyle(document.body);
    const bodyBox = document.body.getBoundingClientRect();
    const roomLeft = bodyBox.left + parseFloat(bodyStyle.paddingLeft);
    const roomRight = bodyBox.right - parseFloat(bodyStyle.paddingRight);
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
    // `float` computes to whichever of the four values was written, so the two
    // logical ones are resolved against the element's own direction rather than
    // compared as strings: `inline-start` is the left edge in a LTR page and the
    // right edge in a RTL one, and a side read wrong reports a note that is exactly
    // where it belongs.
    const floatSide = (s) =>
        s.float === 'left' || s.float === 'right' ? s.float
        : (s.float === 'inline-start') === (s.direction !== 'rtl') ? 'left' : 'right';
    const inTheMargin = (el, s) => {
        if (s.float === 'none') return false;
        const b = el.getBoundingClientRect();
        return floatSide(s) === 'left' ? b.right <= left + 1 : b.left >= right - 1;
    };
    // Both readings that hand a box to an ancestor ask shownBand, or a box inside a
    // container that clips without saying so in `overflow` is named for a spill it is
    // drawn nowhere near and left unnamed for the loss it did take, the walk at the foot
    // of this pass having gone straight past the container that cut it.
    const answeredFor = (el) => {
        const own = getComputedStyle(el);
        if (own.position === 'absolute' || inTheMargin(el, own)) return true;
        for (let a = el.parentElement; a && a !== main; a = a.parentElement) {
            const s = getComputedStyle(a);
            if (s.position === 'absolute' || inTheMargin(a, s)) return true;
            if (shownBand(a)) return true;
        }
        return false;
    };
    // The bound a descendant of a wide widget is held to. The column is the wrong one —
    // the room is exactly what the declaration granted, and a roster of prose rows had
    // all five reported as standing out in the margin — but "answered for" is wrong too,
    // and wrong in the direction that costs: a child that paints past its own widget's
    // box does not grow that box, so exempting the subtree makes the widget's rect prove
    // something about itself alone. This read as answered while both wide widgets also
    // scrolled, `overflow-x: auto` having caught every descendant a line above.
    const insideWide = (el) => {
        for (let a = el.parentElement; a && a !== main; a = a.parentElement)
            if (a.hasAttribute('data-lf-wide')) return a;
        return null;
    };
    // What a wide widget may not escape, whatever the page has room for: the nearest
    // thing between it and the column that draws a box of its own. Asked of the drawing
    // rather than of a list of tags, because the fault is visual and so is the property
    // — a widget that stands outside a frame, a tint or a fill reads as a broken page,
    // and one that grows through a transparent wrapper (a section, a tab's panel) reads
    // as the exhibit it is. A box that draws one says so where it draws it (--lf-frame,
    // theme.css) and the theme reads that declaration to withhold the room; this is what
    // says so when a box that draws hasn't made it. (Nothing to do with x-paints, which is
    // about words rather than boxes: an attribute rendered as paint instead of text, and
    // spoken for whoever is listening.)
    const draws = (el) => {
        const s = getComputedStyle(el);
        return s.backgroundImage !== 'none'
            || !/^(transparent|rgba\\(0, 0, 0, 0\\))$/.test(s.backgroundColor)
            || ['Top', 'Right', 'Bottom', 'Left'].some(side =>
                   parseFloat(s[`border${side}Width`]) > 0
                   && s[`border${side}Style`] !== 'none');
    };
    const framing = (el) => {
        for (let a = el.parentElement; a && a !== main; a = a.parentElement)
            if (draws(a)) return a;
        return null;
    };
    const over = new Map();
    for (const el of main.querySelectorAll('*')) {
        const wide = el.hasAttribute('data-lf-wide');
        // A wide widget is asked whatever it stands in, where everything else is excused
        // by a scroll container above it. The excuse is about the column — a box inside a
        // scroller is drawn only as far as the scroller reaches, so it cannot spill onto
        // the page — and a wide widget's question is a different one: it is measured
        // against the box that frames it, and a board scrolls, so every card on every
        // board was excused from the only reading that applies to it. A diagram in a card
        // was drawn across the neighbouring column and this said the page was clean.
        if (!el.checkVisibility() || (!wide && answeredFor(el))) continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1) continue;
        const frame = wide ? framing(el) : null;
        const host = wide ? null : insideWide(el);
        const bound = (frame || host)?.getBoundingClientRect() ?? null;
        const past = wide || host
            ? Math.round(Math.max(b.right - (bound ? bound.right : roomRight),
                                  (bound ? bound.left : roomLeft) - b.left))
            : Math.round(Math.max(b.right - right, left - b.left));
        if (past > 1) over.set(el, [past, wide, frame, host]);
    }
    const found = [];
    for (const [el, [past, wide, frame, host]] of over) {
        if ([...over.keys()].some(other => other !== el && other.contains(el))) continue;
        found.push(host
            ? `${at(el)} stands ${past}px outside the ${at(host)} it is part of`
            : !wide
            ? `${at(el)} is set ${past}px past the column, out in the margin`
            : frame
            ? `${at(el)} stands ${past}px outside the ${at(frame)} that frames it — `
              + `declare --lf-frame: 1 in the rule that draws the frame, so the box `
              + `holds the room in as well as the margins`
            : `${at(el)} stands ${past}px past the room the page has for a wide widget`);
    }
    // The room being the page's own box is not the whole of what a wide widget owes,
    // because the page hangs things in that box. A suggestion's controls stand 22px off
    // the column and a sidenote a gutter off it on the other side, while the strip each
    // is reserved out of comes off the far edge of the page — and those are the same
    // place only when the column is flush against the strip, which it never is, since it
    // centres in what the strip leaves. So the reservation says where the room ends and
    // the occupancy says where the furniture is, and between them is a band that is
    // inside the page's box and already spoken for. A board grown to the box was drawn
    // 134px over the controls that decide the change above it, which is the change made
    // undecidable by the page's own exhibit.
    //
    // The theme is where a margin's claimant gives up that side (--lf-grow-l, --lf-grow-r),
    // and this is what says so when one of them doesn't — the same bargain the framing
    // rule above has, and the reason neither has to be a list anybody maintains. A
    // resident is whatever answered for itself in the margin above, so a project hanging
    // its own furniture out there is covered without declaring anything to this pass.
    const residents = [];
    for (const el of main.querySelectorAll('*')) {
        if (!el.checkVisibility() || el.hasAttribute('data-lf-wide')) continue;
        const s = getComputedStyle(el), b = el.getBoundingClientRect();
        // Clipped to nothing is not standing in the margin: the words a page paints for
        // whoever is listening are a pixel wide and under a reader's notice, so a widget
        // drawn across one has taken nothing from anybody.
        if (b.width < 2) continue;
        const clear = b.right <= left + 1 || b.left >= right - 1;
        if (clear && (s.position === 'absolute' || inTheMargin(el, s))) residents.push(el);
    }
    for (const el of main.querySelectorAll('[data-lf-wide]')) {
        if (!el.checkVisibility()) continue;
        const b = el.getBoundingClientRect();
        const hit = residents.find((r) => {
            if (el.contains(r) || r.contains(el)) return false;
            const c = r.getBoundingClientRect();
            return b.left < c.right - 1 && b.right > c.left + 1
                && b.top < c.bottom - 1 && b.bottom > c.top + 1;
        });
        if (hit) found.push(`${at(el)} is drawn over ${at(hit)}, which stands in the `
                            + `margin it grew into — the side that holds it gives no room`);
    }
    // The other half of excusing a resident: an excuse is only good if the reader can
    // see the thing. Both readings above hand a box to something else to answer for —
    // the margin it was placed in, the container that took its overflow — and the
    // second is worth exactly what the reader can tell from that container. A scroller
    // answers for what ran out of it on the side it scrolls toward, scrollLeft running
    // from zero to the overflow and never the other way. A box that marks where it cut
    // answers for the rest, the mark being what says there is a rest. And a box that
    // only clips answers for nothing at all: what leaves a choose group, a board or a
    // table is drawn nowhere and said nowhere either, and every other reading here
    // calls such a page well — checkVisibility() is true of a clipped box, so screen
    // and print agree, and the copy withholds the clip and shows the words the live
    // page dropped. The reader is the only party who loses them, which is why the
    // question is asked here, where the excuse was granted.
    //
    // Every box and not floats alone. A float is how a resident reaches the margin, so
    // it was the shape the failure first arrived in; the rule is about the excuse, and
    // a container grants that to whatever stands inside it. Held to floats it watched
    // one sidenote and let a question through: a row-form option 30px wider than the
    // group holding it carried every mark on it past the clip, and four of the examples
    // shipped a decision with no box to tick.
    //
    // Across the page and not down it, which is the axis every reading here takes: a
    // box cut off below its container is usually cut on purpose — a collapsed
    // disclosure, a shot's frame, a draft's box are all a height with the rest hidden —
    // where one cut off at the side never is.
    //
    // The nearest container and no further, because past it what an outer box sees is
    // that container's own edges, and the container answers the same question on its
    // own turn of the loop. Body is the page's scroller, so this is also where a float
    // carried off the leading edge of the window is named — the sideways reading, which
    // reads how far the page scrolls, cannot see one. Wholly inside, because a box half
    // in the clip is half unreadable: the group above leaves 7px of a 192px note
    // showing, which is nothing an "overlaps at all" reading would have objected to.
    const scrolls = (s) => /^(auto|scroll)$/.test(s.overflowX);
    const lost = new Map();
    // Up the containing blocks rather than the markup, since those are the boxes that
    // hold this one: an absolutely-placed box hangs off the nearest ancestor that
    // establishes one, and a static box it happens to be written inside clips it not at
    // all. offsetParent names that ancestor. Its own definition says positioned
    // ancestors, which reads as a gap — transform, filter, will-change, contain and
    // content-visibility each establish a containing block too — but Chrome returns
    // those as well, agreeing with where the box lands, so the property list a reader
    // reaches for here is already in the one call. A fixed box hangs off none of them.
    const holder = (el) => {
        const s = getComputedStyle(el);
        return s.position === 'absolute' ? el.offsetParent
             : s.position === 'fixed' ? null
             : el.parentElement;
    };
    for (const el of main.querySelectorAll('*')) {
        if (!el.checkVisibility()) continue;
        // Nothing inside an <svg> is the page's flow: a foreignObject clips by its
        // nature, and mermaid's label boxes run an even 8px outside theirs on an
        // ordinary graph — the drawing's own accounting, not the page losing words.
        if (el.closest('svg')) continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1) continue;
        let a = holder(el), band = null;
        for (; a; a = holder(a)) { band = shownBand(a); if (band) break; }
        if (!a) continue;
        const s = getComputedStyle(a);
        // text-overflow is the mark, declared in the rule that does the cutting, the
        // way --lf-frame is declared where the frame is drawn. The box itself still
        // answers here on its own turn.
        if (s.textOverflow !== 'clip') continue;
        const overL = band.left - b.left, overR = b.right - band.right;
        // A scroller reaches its whole content on the side it scrolls toward, so only
        // its leading edge is asked — and asked from scroll position zero, since where
        // the container happens to be scrolled while the gate reads it says nothing
        // about where its content ends.
        const past = Math.round(
            !scrolls(s) ? Math.max(overL, overR)
            : s.direction === 'rtl' ? overR + a.scrollLeft
            : overL - a.scrollLeft);
        if (past > 1) lost.set(el, [past, a]);
    }
    for (const [el, [past, a]] of lost) {
        // Out of the same container, because that is what makes the outer box's report
        // the inner one's too. Suppressing on containment alone let a box lost 3px out
        // of one container hide the one hung off it and lost 400px out of another.
        if ([...lost].some(([o, [, its]]) => o !== el && its === a && o.contains(el)))
            continue;
        found.push(`${at(el)} is drawn ${past}px outside ${at(a)}, which does not show it`);
    }
    return [...new Set(found)];
}"""


# A version whose markup asserts a state the log replays over — `chosen` moved
# to another option, a card re-authored into a column the user dragged it
# out of. Replay resolves it in the user's favor, so what needs reporting is
# the author's intent going down silently. The static half can't say which
# attribute is a verb's state — that lives in each widget's applyAction, and a
# table here would be the second copy the registry exists to prevent — so the
# browser compares: projection reconciliation records the ids it wrote on the body
# (data-lf-replay-wrote), and this pass asks which of them the author also
# changed since the previous version, reading both files with the runtime's own
# shallowSigs. An authored change replay then overrode is a conflict; an
# unchanged id is the initial condition the log is supposed to outrank. For the
# message, each conflicting id is laid at the door of the widget whose replay
# wrote it — its nearest ancestor with an applyAction.
#
# The two files are handed in rather than fetched: which pair to compare is a
# question about the log and the URL, both of which the caller holds, and a read
# it makes is a read it can put a deadline on (see `served` in render_version).
REPLAY_OVERRIDES = """async ({ curHtml, prevHtml }) => {
    const ids = (document.body.dataset.lfReplayWrote ?? '').split(' ').filter(Boolean);
    if (!ids.length) return [];
    const { shallowSigs } = await import('/leaf.js');
    const sigs = (html) => shallowSigs(
        new DOMParser().parseFromString(html, 'text/html').body);
    const cur = sigs(curHtml), prev = sigs(prevHtml);
    const groups = new Map();
    for (const id of ids) {
        if ((cur.get(id) ?? '') === (prev.get(id) ?? '')) continue;
        let widget = null;
        for (let a = document.getElementById(id); a; a = a.parentElement)
            if (a.applyAction) { widget = a; break; }
        const key = widget ? `<${widget.tagName.toLowerCase()} id=${widget.id}>` : `id=${id}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(id);
    }
    return [...groups].map(([who, asserted]) =>
        `${who} authors state the log replays over (${asserted.join(', ')}): `
        + `the user's decision stands — either carry it in the markup, or `
        + `rewrite the passage and declare restated`);
}"""


# Whether an applyAction is absolute, which is the premise both folds and every view
# built on them rest on and the one thing about a widget module no gate could see. A
# relative implementation — a card shifted one column along, a pick toggled rather than
# set — is invisible to every other reading here: it renders perfectly, and what it
# costs arrives later, in the poll that replays the sender's own action over the state
# that gesture already painted. The user drags a card once and watches it walk.
#
# So the page is asked rather than the code. Each standing action is applied a second
# time onto the state the page's own replay produced, and an absolute one has nothing
# to do. Re-running reconciliation would prove nothing — an already committed
# projection is clean whatever the widgets do — which is why this reaches past the
# runtime's checkpoint and calls the method.
#
# The standing state rather than the whole log, because that is the set the contract is
# for: the fold's own claim is that the last surviving action per coordinate *is* the state,
# so the page is already showing exactly these. It is also the set replay applied and
# did not skip — a retracted decision, a version's future action and a widget the
# markup dropped are all out of it — so nothing here re-applies what the page declined.
#
# The whole set at once and in the log's order, never one action measured on its own.
# An absolute applyAction states its own unit and says nothing about any other, so where
# two units share an ordered container the page is the sequence's result rather than any
# one action's: two cards dragged to the head of one column leave it holding the second
# above the first, and lifting the first back over the second is what replaying it alone
# is *supposed* to do. Read per action, that named lf-board relative and refused a page
# with nothing wrong with it — at the gate a handover cannot get past. Read across the
# batch, an absolute set lands exactly where it already was and a relative one walks.
#
# Two readings, because one is blind where the other sees. shallowSigs is the id-bearing
# markup state, which covers a moved card, a flipped attribute and a re-pointed pick;
# it looks away from text on purpose, and a `body` record is nothing but text, so the
# unit's declared facet is read beside it. A throw is a finding of its own rather than
# an exception out of the gate: whatever a second application was expected to do, it was
# not that. Each moved id is then laid at the door of the widget whose applyAction writes
# it — its nearest ancestor with the method, as a replayed override already is — since
# across a batch no single verb owns the difference.
RELATIVE_REPLAYS = """async () => {
    const { standingState, shallowSigs } = await import('/leaf.js');
    const at = (el) => `<${el.localName}${el.id ? ' id=' + el.id : ''}>`;
    // A fold reads the registry, so a decided widget whose module never loaded is in it
    // and has no method to converge. That failure is reported on its own — the console,
    // the fail-soft box, the undefined element — and asking it this question would only
    // lay the same fault at a second door.
    const standing = standingState().filter((s) => s.widget?.applyAction);
    if (!standing.length) return [];
    const found = [];
    const before = shallowSigs(document.body);
    const stood = standing.map((s) => s.read());
    for (const s of standing) {
        const widget = s.widget;
        if (!widget?.applyAction) continue; // an earlier application replaced it
        try {
            widget.applyAction(s.action, s.detail);
        } catch (error) {
            found.push(`${at(widget)} applyAction(${s.action}) threw when the recorded `
                + `action was applied a second time: ${error?.message ?? error} — the `
                + `poll replays the sender's own action, so it has to arrive twice`);
        }
    }
    const now = shallowSigs(document.body);
    const verbs = new Map();
    for (const s of standing) {
        if (!s.widget) continue;
        const key = at(s.widget);
        if (!verbs.has(key)) verbs.set(key, new Set());
        verbs.get(key).add(s.action);
    }
    const groups = new Map();
    const note = (key, what) => {
        if (!groups.has(key)) groups.set(key, new Set());
        groups.get(key).add(what);
    };
    for (const id of new Set([...before.keys(), ...now.keys()])) {
        if (before.get(id) === now.get(id)) continue;
        let widget = null;
        for (let a = document.getElementById(id); a; a = a.parentElement)
            if (a.applyAction) { widget = a; break; }
        note(widget ? at(widget) : `id=${id}`, id);
    }
    // Only body records need the second reading: shallowSigs deliberately excludes
    // text. Key its wording by facet as well as unit, because a markup facet and a
    // body facet may both stand on the same unit and both move in this batch.
    standing.forEach((s, i) => {
        if (s.record !== 'body' || s.read() === stood[i] || !s.widget) return;
        note(at(s.widget), `the ${s.facet} state recorded on ${s.unit}`);
    });
    return [...found, ...[...groups].map(([who, moved]) => {
        const said = verbs.get(who);
        const named = said?.size ? `applyAction(${[...said].join(', ')})` : 'applyAction';
        return `${who} ${named} is relative — re-applying the standing log moved `
            + `${[...moved].join(', ')}. The poll replays every standing action over the `
            + `state they already produced, so state the whole value from the detail `
            + `rather than stepping from what the page shows`;
    })];
}"""


# What the page says, and whether each run of it is showing. Read once in each medium
# and compared by walk order: media change what is displayed, never the DOM, so the nth
# run on screen is the nth run on paper. What a page says has to survive being printed,
# and the ways it can fail to are all silent — a widget's control that is a statement as
# well as a thing to press (the pick mark, which took the only words naming the option a
# group carried), a rule of the page's own that hides its content in print. The whole
# page rather than the widgets in it, because a user's printout losing a paragraph is
# no better than losing a widget's word. Declared offers are excluded because paper has
# nothing to press; the runtime's own layer is excluded because it was never the
# document, and a widget rendered inside it (a reply's markup) is the panel's, not the
# page's.
PAPER_WORDS = """() => {
    const out = [];
    const at = el => { const named = el.closest('[id]');
                       return named ? `<${named.tagName.toLowerCase()} id=${named.id}>`
                                    : `<${el.tagName.toLowerCase()}>`; };
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim() || el.closest('.lf-chrome, [data-lf-offer]')) continue;
        out.push({ at: at(el), text: n.data.trim().slice(0, 40),
                   shown: el.checkVisibility() });
    }
    return out;
}"""


# Words the page draws in the same place as other words. A copy went out with a settled
# group's cards laid across the heading above them — the cards kept the collapsed
# padding, which is the room the group is laid out in — and the user saw it in the
# first second while every assertion passed: the words were all present, all shown, and
# all of a usable size. They were in the same place, and nothing was asking about place.
#
# Boxes rather than a hit test, which is the other way to ask: a press landing on the
# wrong element is a different fault with its own test, and the medium this has to hold
# up in is the copy, where there is nothing left to press. Text against text, because
# text over a background, a border, or a picture is how a page is built.
#
# A pair where one element contains the other is skipped: a paragraph and the <em>
# inside it are one run of words that the flow lays out together, and their boxes
# overlap by construction. Two pixels of slack, since a line box carries its leading and
# adjacent blocks can round into each other by a hair. The runtime's layer is skipped
# too: it floats over the document on purpose, and where that costs the user a press
# it is the hit test that says so.
#
# The layer is in two places, so the skip names both. The line counting a passage's
# comments lives inside the page's own elements by design — it is what a screen reader
# hears where a painted mark says nothing — and it is clipped to nothing on screen.
# checkVisibility answers for display, visibility and opacity and knows nothing of
# clip-path, so that line read as drawn, and its text lays out past the 1px box holding
# it: an anchor on a container put "1 comment" across the paragraph below the widget and
# failed the gate on a page with nothing wrong with it. Asking for `.lf-chrome` alone was
# the class standing in for the question, the same substitution the anchor pass made with
# `.lf-ui`. The question is whose words these are, and the runtime marks its own in both
# of the places it writes them.
#
# checkVisibility knows nothing of content-visibility either, which is what a collapse
# wears: an inactive tab's panel and a settled group's cards are hidden="until-found" so
# that find-in-page still reaches inside, and the text in one reports the boxes it last
# laid out in — every sibling's at the same place. So a page with a collapsed group on it
# failed about half the runs and passed the rest, which is the worst way for a gate to be
# wrong: the page that goes out is whichever one the coin was kind to. A collapse is asked
# for, and words nobody can see are not drawn over anything, so [hidden] is held out here
# the way the size check holds it out. The coin comes down the same side every time on a
# group that has been opened and closed, which is where the test pins it.
COVERED_WORDS = """() => {
    const runs = [];
    const at = el => { const named = el.closest('[id]');
                       return named ? `<${named.tagName.toLowerCase()} id=${named.id}>`
                                    : `<${el.tagName.toLowerCase()}>`; };
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim() || el.closest('.lf-chrome, .lf-mark-note, .lf-quiet, [hidden]')) continue;
        if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
        const range = document.createRange();
        range.selectNodeContents(n);
        for (const box of range.getClientRects())
            if (box.width > 1 && box.height > 1)
                runs.push({ el, box, text: n.data.trim().slice(0, 40) });
    }
    const found = [];
    for (let i = 0; i < runs.length; i++) for (let j = i + 1; j < runs.length; j++) {
        const a = runs[i], b = runs[j];
        if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
        const across = Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
        const down = Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
        if (across <= 2 || down <= 2) continue;
        found.push(`${at(a.el)} draws ${JSON.stringify(a.text)} in the same place as `
                   + `${at(b.el)}'s ${JSON.stringify(b.text)}`);
    }
    return [...new Set(found)];
}"""


# Which trees are the page, for the two readings below that answer for what a widget
# renders rather than for what it declares. Every open root, found by walking rather than
# read off the registry's x-shadow list: a root a module attached without declaring one
# still holds words and code the reader has to read, and a reading that asked the
# registry would look away from exactly the tree nobody vouched for. Written once,
# because it is one claim about the page and two copies of it are two things to keep
# level.
OPEN_ROOTS = """
    const roots = (root) => [root, ...[...root.querySelectorAll('*')]
        .filter(el => el.shadowRoot).flatMap(el => roots(el.shadowRoot))];"""


# Code that came out the colour of the code around it. Colouring takes two halves that
# meet nowhere a static lint can reach: the runtime writes data-lf-syn in the browser,
# and the theme answers it with a var() the browser resolves. Either half can stop
# working with nothing said — the tokenizer failing throws, and the console error is
# already a finding here, but a stylesheet that no longer answers a role, or answers it
# with an ink too near the paper, is silent. What reaches the user is a page of code in
# one flat colour, which is what they report as the highlighting being gone; it was
# reported that way, on a comment that was 3.3:1 against the block it sat on.
#
# So both halves are asked of the drawn result rather than of the declarations behind it.
# A palette can be read out of the stylesheet; what a role came out as cannot, because a
# project overlays its own theme over this one and the browser is the only thing that
# knows which declaration won.
#
# Once per role and surface rather than once per span: the fault belongs to the role, not
# to the hundredth span wearing it, and a role reads differently on a diff's del tint than
# on the plain block, so the pair is what a reading answers for. A page of code costs a
# couple of dozen of them rather than one per token — measured at under 10ms across the
# examples. The line is per role, since the palette is where the fix goes and a role
# failing on two tints is one thing to change.
#
# What a colour is comes back from the browser painting it, not from a parse of how it
# wrote it down — getComputedStyle serializes a hex as rgb() in 0–255 and a color-mix as
# color(srgb …) in 0–1, and a probe reading one as the other reports a ratio against a
# colour nothing on the page is. Painting the backgrounds in order composites the
# translucent ones the way the page does, over the white the browser paints under
# everything, so a tint over a tint is the colour the reader actually has behind the
# glyphs. A marked passage is not among them: the highlight registry styles glyphs and
# not boxes, so a mark is no element's background, and it is the user's own paint over a
# page that had to be legible before they put it there.
#
# 4.5:1 is WCAG AA for body text, and body text is the threshold that applies — code is
# 13px. Axe runs over this corpus too and passes it, which is not the same guarantee:
# asked for colour-contrast alone on the example carrying the beige comment, it returned
# 44 passing elements, no violation, and not one of the spans among them.
#
# Which shadow roots it crosses into is OPEN_ROOTS' answer (the section note above says
# why it crosses at all), which is the choice everything else here makes — colour is
# asked of what the browser painted, so where it painted is too, and a root a widget
# attached without declaring one still holds code the reader has to read.
UNREAD_SYNTAX = (
    """() => {"""
    + OPEN_ROOTS
    + """
    const cx = document.createElement('canvas').getContext('2d');
    const paint = (...layers) => {
        cx.clearRect(0, 0, 1, 1);
        for (const c of ['white', ...layers]) { cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); }
        return [...cx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
    };
    const chan = (v) => (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    const lum = ([r, g, b]) => 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
    const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p);
                              return (hi + 0.05) / (lo + 0.05); };
    const up = (el) => el.parentElement ?? el.getRootNode().host ?? null;
    const under = (el) => { const layers = [];
                            for (let a = el; a; a = up(a))
                                layers.unshift(getComputedStyle(a).backgroundColor);
                            return layers; };
    const seen = new Set(), found = new Map();
    for (const span of roots(document)
                       .flatMap(r => [...r.querySelectorAll('[data-lf-syn]')])) {
        const role = span.dataset.lfSyn;
        if (found.has(role) || !span.textContent.trim()) continue;
        if (!span.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
            continue;
        const layers = under(span);
        const on = paint(...layers);
        if (seen.has(`${role} on ${on}`)) continue;
        seen.add(`${role} on ${on}`);
        const ink = paint(...layers, getComputedStyle(span).color);
        const plain = paint(...layers, getComputedStyle(up(span)).color);
        const read = ratio(ink, on);
        if (String(ink) === String(plain))
            found.set(role, `code marked ${role} is the ink of the code around it — `
                          + `nothing answered [data-lf-syn="${role}"]`);
        else if (read < 4.5)
            found.set(role, `code marked ${role} reads at ${read.toFixed(1)}:1 `
                          + `against the block it is set on`);
    }
    return [...found.values()];
}"""
)


# Words a declaration promised and the page never got. Every other reading here works
# from what the browser drew, and that is exactly what cannot see this one: a word that
# never arrived looks the same as an attribute with nothing to say, and a fact the page
# paints in colour alone is a fact no measurement of a drawn page has ever read. The
# registry is what knows the difference — x-says names the attributes whose values are
# words at the element's edge, x-paints the ones drawn as paint and spoken to a reader
# listening (renderQuiet) — so the declaration is what this asks against.
#
# Both passes run once at the upgrade, before an async widget's own render lands, so a
# module that rebuilds its body from a settle() promise takes the words out with it and
# nothing on the page says so. renderQuiet re-runs on each replay and renderSaid never
# does, which decides how long each stays gone rather than whether it goes.
#
# It reads every open root (OPEN_ROOTS) where both word passes stop at the boundary on
# purpose: which widgets the page holds is the document's question, and settling a
# staged widget's nesting in a sweep would be writing that contract where nobody would
# look for it (the layer's CLAUDE.md). So a staged element keeps its declarations and
# gets neither pass, which is exactly where a promised word reaches nobody in silence —
# reported here, to the module's author, at handover.
#
# Both halves ask the *rendered* page rather than the markup, and a shadow host is why:
# an element that stages a tree keeps its light DOM in the document and out of every box,
# so both passes find the host, write there, and leave `textContent` and `querySelector`
# reporting words the reader will never get. Each half gets to the rendered page its own
# way, because they read different things. Words are `says()`, the layer's one answer to
# what an element says rather than a second reading spelled here — asked of the host's
# root where there is one, since the walk behind it substitutes a declared root for a
# *child* and never for the element it was handed. The quiet word is in no such reading,
# wearing the .lf-ui that `says` skips on purpose, so what is asked of it is its box: a
# span clipped to a pixel still has one wherever it renders, and none at all where it
# doesn't. A collapsed card lays out nothing either and is asked for, so [hidden] is held
# out here the way COVERED_WORDS holds it out.
SILENT_WORDS = (
    """(widgets) => import('/leaf.js').then(leaf => {"""
    + OPEN_ROOTS
    + """
    const found = [];
    const all = roots(document);
    const at = el => `<${el.localName}${el.id ? ' id=' + el.id : ''}>`;
    const every = tag => all.flatMap(r => [...r.querySelectorAll(tag)]);
    for (const [tag, entry] of Object.entries(widgets)) {
        for (const attr of Object.keys(entry['x-says'] ?? {}))
            for (const el of every(tag)) {
                const value = el.getAttribute(attr);
                if (value !== null && !leaf.says(el.shadowRoot ?? el).includes(value))
                    found.push(`${at(el)} declares ${attr} as x-says and never says `
                               + `"${value}"`);
            }
        // The word itself is renderQuiet's to derive, and this asks only that the
        // element carries one: a widget painting a fact and saying nothing is the
        // whole of the failure, and all a second copy of the derivation would add is
        // a second place to change it.
        for (const attr of entry['x-paints'] ?? [])
            for (const el of every(tag)) {
                if (!el.hasAttribute(attr)) continue;
                const quiet = el.querySelector(':scope > .lf-quiet');
                if (quiet && (quiet.getClientRects().length || el.closest('[hidden]')))
                    continue;
                found.push(`${at(el)} paints ${attr}="${el.getAttribute(attr)}" `
                           + `and says nothing a reader listening can hear`);
            }
    }
    return found;
})"""
)


# Attributes standing on a widget that its entry never declared. The schema is the
# whole of the author's namespace — `additionalProperties: false` on every tag — and
# the static lint holds a version file to it. What no reading of a file can see is the
# other writer: a module, which upgrades the element and may leave anything it likes on
# it. So a module writes in that namespace only where the registry declares the
# attribute as a verb's record form (`chosen`, `status`), which is what makes the write
# a statement the log's fold, the state gate and the record-lag report can all read.
# Everything else it needs to mark goes where the module's own words go — the chrome it
# built, in the platform's vocabulary (aria-*, role, hidden, tabindex) or under data-*,
# which is the layer's and a widget's alike.
#
# lf-options had two of the other kind, and both were quiet. `answered` recorded a verb
# only a thread can post, and a thread's markup is frozen in the log, so no version
# could ever have honored a record of it; `open` recorded which way this tab last left
# a disclosure, which no version carries at all. Neither reached a consumer, and the
# one reader that did see them read them wrong: shallowSigs excludes exactly the
# attributes no version can assert, and its exclusion list is the runtime's own paint —
# so a widget writing beside it is counted as state the author wrote, in the reading
# `version check --render` uses to decide whether a version overrules the user.
#
# Deduped and reported per tag and attribute, because one mistake is on every instance.
UNDECLARED_ATTRS = (
    """(widgets) => {"""
    + OPEN_ROOTS
    + """
    // What a module may write without declaring: the platform's own vocabulary for
    // what a control is and how it behaves, and the data-* namespace the runtime and
    // the widgets both paint in. `class` and `style` are the same kind of fact — a
    // look, not a state a version could carry.
    const painted = /^(?:data-|aria-)/;
    const platform = new Set(['role', 'class', 'style', 'hidden', 'tabindex']);
    const all = roots(document);
    const found = [];
    for (const [tag, entry] of Object.entries(widgets)) {
        if (!entry.properties) continue;
        for (const root of all)
            for (const el of root.querySelectorAll(tag))
                for (const a of el.attributes)
                    if (!painted.test(a.name) && !platform.has(a.name)
                        && !(a.name in entry.properties))
                        found.push({tag, id: el.id, attr: a.name});
    }
    return found;
}"""
)


# The two sides of the settlement contract, compared on the rendered page. The mark —
# data-lf-state on a holder — is the layer's paint of a logged decision (projection
# reconciliation in leaf.js), and the anchor pass retires slots by it, so whatever it
# says, the page's
# reading obeys. What can still go wrong is a family's, and both failures render
# perfectly: a module that writes the mark where the log decided nothing silences words
# the reader can still see and select, and a settled slot can show its words anyway — a
# later layer's rule outranking the default hide, a module re-showing what it folded —
# leaving the reader selecting words no comment can anchor to, with the refusal
# arriving later, at `leaf comment`, nowhere near the mistake. So the expected outcome
# comes from the file's reading (`decisions`, folded over this version's log), never
# from the page, and the page answers only for what it shows.
#
# The words walk is textNodesUnder with an accepts of its own, on purpose: the anchor
# pass's default accepts already skips a marked holder's slots, so asking it whether
# the retired words are gone would let the mark answer for the screen. What it keeps
# of that reading is the boundary — declared shadow roots, the same trees replay's
# elementById marks across, which is why the holders are found through OPEN_ROOTS
# too — and the chrome test (inUi): a declared label is the page's words, so a
# settled slot still showing one is still showing words. The visibility guards are
# COVERED_WORDS', for its reasons: [hidden] holds until-found content whose boxes
# report as last laid out, and visibility and opacity hide with layout intact. One
# scheme, on the trapped-margin reading's premise — the palettes carry no geometry
# between them — with the fold a replayed decision plays awaited first, finite
# animations only, because a slot mid-fold still paints words it has already retired.
RETIRED_SLOTS = (
    """async (holders) => {"""
    + OPEN_ROOTS
    + """
    const leaf = await import('/leaf.js');
    const all = roots(document);
    const find = (id) => {
        for (const r of all) {
            const el = r.getElementById(id);
            if (el) return el;
        }
        return null;
    };
    const found = [];
    const showing = (slot) => {
        for (const seg of leaf.textNodesUnder(slot, (n) => !leaf.inUi(n))) {
            const n = seg.node, el = n.parentElement;
            if (!n.data.trim()) continue;
            if (el.closest('.lf-chrome, .lf-mark-note, .lf-quiet, [hidden]')) continue;
            if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
                continue;
            const range = document.createRange();
            range.selectNodeContents(n);
            for (const box of range.getClientRects())
                if (box.width > 1 && box.height > 1) return n.data.trim().slice(0, 40);
        }
        return null;
    };
    for (const h of holders) {
        const el = find(h.id);
        if (!el || leaf.inChrome(el) || leaf.quoted(el)) continue;
        await Promise.allSettled(
            el.getAnimations({subtree: true})
                .filter((a) => a.effect?.getTiming().iterations !== Infinity)
                .map((a) => a.finished));
        const mark = el.getAttribute('data-lf-state');
        const at = `<${h.tag} id='${h.id}'>`;
        if (mark !== (h.outcome ?? null)) {
            const log = h.outcome ? '`' + h.outcome + '`' : 'no decision';
            found.push(`${at} wears data-lf-state=${JSON.stringify(mark)} where the `
                + `log records ${log} — the mark is the layer's paint of a logged `
                + `decision, and the anchor pass retires slots by it, so a module may `
                + `say only what the log decided`);
            continue;
        }
        for (const tag of h.slots)
            for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
                for (const slot of root.querySelectorAll(`:scope > ${tag}`)) {
                    const words = showing(slot);
                    if (words === null) continue;
                    found.push(`${at} settled \\`${h.outcome}\\` and its <${tag}> still `
                        + `shows ${JSON.stringify(words)} — those words have left the `
                        + `page's reading, so the reader can select what no comment can `
                        + `anchor to; the layer hides a retired slot by default, so `
                        + `something in this family is showing it anyway`);
                }
    }
    return found;
}"""
)


# A box that draws an inset and shows a different one. A child's outer margin normally
# collapses through its parent and is spent between blocks; where the parent draws
# something at that edge, or holds a formatting context of its own, it cannot get out and
# is painted as the parent's inset instead. So the number a stylesheet states is not the
# number a reader sees, and which of the two they get depends on what the author wrote
# inside: a card ending in a sentence showed its 16px, the same card ending in a paragraph
# showed 29. theme.css states the trim and a box opts in where it draws the frame
# (`--lf-frame`); this is what says when one hasn't.
#
# It is a reading of the rendered page because nothing else can be. The trim is a style
# query, the frame is a declaration in whichever layer drew the box, and a project overlays
# its own theme over leaf's — so which rule won, and whether the child that ended up at the
# edge is the one the stylesheet's author had in mind, are facts only the browser holds. A
# lint over the CSS would be reading the declarations and not the result, which is the same
# mistake the reserved-width lint made before the press sweep replaced it.
#
# Two exclusions, both about what a margin means where it stands. A flex or grid container
# collapses no margin anywhere, so a margin on an item at its edge is a placement rather
# than room that could not get out — the switch under a screenshot pair carries 3px of
# exactly that, the UA's own on a checkbox. And an edge whose box is a generated one (a
# pseudo-element, an `x-says` word, an injected control) is the layer's own paint, stated
# in the same rule as the frame: what the trim looks for is the first and last block the
# page itself put there, so this looks for the same, and a card's absolutely-positioned
# pick mark is not the thing under its last paragraph.
#
# Deduped per tag and edge, because one mistake is on every instance of that widget.
TRAPPED_MARGINS = (
    """() => {"""
    + OPEN_ROOTS
    + """
    const px = (v) => parseFloat(v) || 0;
    // The platform's own answer to "does a child's margin reach my edge, and can it get
    // past it": a box that establishes a formatting context keeps every margin inside.
    const holds = (s) =>
        s.display === 'flow-root' || s.display === 'inline-block'
        || s.display.startsWith('table') || s.overflow !== 'visible'
        || s.float !== 'none' || s.position === 'absolute' || s.position === 'fixed'
        || s.contain.includes('layout') || s.contain.includes('paint');
    // The page's own boxes in this box's flow, in order. Out-of-flow children are not in
    // it, a floated one spends its margins rather than reserving them, a generated one is
    // the layer's paint, and a boxless child hands its own children to the flow.
    const flow = (el) => {
        const out = [];
        for (const node of el.childNodes) {
            if (node.nodeType === 3) { if (node.data.trim()) out.push({}); continue; }
            if (node.nodeType !== 1) continue;
            const s = getComputedStyle(node);
            if (s.display === 'none') continue;
            if (s.position === 'absolute' || s.position === 'fixed') continue;
            if (s.float !== 'none') continue;
            if (s.display === 'contents') { out.push(...flow(node)); continue; }
            if (node.matches('.lf-ui, [data-lf-gen]')) { out.push({}); continue; }
            out.push({node, s});
        }
        return out;
    };
    const found = [];
    for (const root of roots(document))
        for (const el of root.querySelectorAll('*')) {
            const s = getComputedStyle(el);
            if (s.display === 'none' || s.display === 'contents') continue;
            // An inline box lays no vertical margin out, so it traps nothing.
            if (s.display.startsWith('inline') && s.display !== 'inline-block') continue;
            if (s.display.includes('flex') || s.display.includes('grid')) continue;
            const kids = flow(el);
            if (!kids.length) continue;
            for (const [edge, side, end, kid, pseudo] of [
                ['above', 'Top', 'Start', kids[0], '::before'],
                ['below', 'Bottom', 'End', kids[kids.length - 1], '::after'],
            ]) {
                if (!kid.node) continue;
                if (getComputedStyle(el, pseudo).content !== 'none') continue;
                const drawn = px(s['padding' + side]) + px(s['border' + side + 'Width']);
                if (!drawn && !holds(s)) continue;
                const margin = px(kid.s['marginBlock' + end]);
                if (margin > 0.5)
                    found.push({
                        tag: el.tagName.toLowerCase(), id: el.id || null,
                        cls: el.classList[0] || null, edge, drawn, margin,
                        child: kid.node.tagName.toLowerCase(),
                    });
            }
        }
    return found;
}"""
)


# How long the render gate waits on the server for one of the documents it reads.
# The same patience playwright gives `wait_for_function` above it, and stated here
# because it is the number that turns a wedged server into a sentence.
SERVED_TIMEOUT_MS = 30_000


def served(page, url: str, path: str):
    """A document this page's own server holds, read from out here.

    The one reader in the render gate that can be given a deadline. `page.evaluate`
    sends the driver no timeout at all — measured on playwright 1.62, an evaluate
    awaiting a fetch that never answers is still running at 200s — so a reading
    taken inside the page is a hang with nothing printed and no way to bound it
    from Python. `page.request` takes one, and shares the browser context's cookie
    jar, so it reads as the same authorized client the page is: the handover key
    rides in the URL and becomes a cookie on the first navigation."""
    return page.request.get(urljoin(url, path), timeout=SERVED_TIMEOUT_MS)


def previous_version(here: int, versions: list) -> int | None:
    """The newest version this server lists before this one, or None where there is
    none — a first version, or one the server does not list at all, which is the
    same answer for the same reason: the conflict reading compares this file against
    what a reader could have seen before it."""
    earlier = [version for version in versions if version < here]
    return max(earlier) if earlier else None


# The window's third error channel, which neither of the two below carries: an `error`
# event with no exception behind it reaches `pageerror` on nobody's account and was never
# written to the console either. Chrome reports a ResizeObserver loop that way — a page
# saying on every load that a piece of its own layout is going undelivered, and every
# reader of it calling the page clean. Routed into the console, which both callers already
# collect, and only for the events with no exception, since the rest arrive as exceptions
# already and one fault should not be two strings.
WINDOW_ERRORS = (
    "addEventListener('error', (e) => {\n"
    "  if (!e.error) console.error('window error: ' + e.message);\n"
    "});"
)
RESIZE_OBSERVER_ERROR = "window error: ResizeObserver loop"

# The page's own word for "I have finished becoming myself", which every pass here
# waits on before reading anything (the stamp's reasons are at the foot of leaf.js).
UPGRADED = "() => document.body.dataset.lfUpgraded === '1'"


def resize_observer_error(text: str) -> bool:
    return text.startswith(RESIZE_OBSERVER_ERROR)


def recurring_resize_observer_error(unit: str) -> str:
    return f"{RESIZE_OBSERVER_ERROR} notice recurred on the confirming {unit}"


# What the page is still doing, named by what it moves. A finite end is what separates a
# page settling from a page living: the banner's dot pulses for as long as the tab is
# open, and a wait that asked for no animation at all would never be answered.
#
# Every open root, because a document answers for its own tree alone. `getAnimations`
# on the document returns nothing for an element inside a widget's shadow root, and
# `{subtree: true}` on the root element returns nothing either (measured on Chrome
# 151) — so a widget drawing itself into place inside its own tree would leave the
# wait satisfied while the host box it grows is still moving, which is the one thing
# this reading exists to prevent.
MOVING = (
    """() => {"""
    + OPEN_ROOTS
    + """
    // Named by the nearest thing the reader can point at, climbing out of a tree the
    // way the runtime's own walks do: an element a widget staged in its root has no
    // id in there, and `<div>` names nothing a fix could start from.
    const at = (el) => {
        for (let n = el; n; n = n.getRootNode?.()?.host) {
            const named = n.closest?.('[id]');
            if (named) return `<${named.tagName.toLowerCase()} id=${named.id}>`;
        }
        return `<${el?.tagName?.toLowerCase() ?? '?'}>`;
    };
    return roots(document)
        .flatMap(root => root.getAnimations())
        .filter(a => a.playState === 'running'
                     && Number.isFinite(a.effect?.getComputedTiming().endTime))
        .map(a => a.animationName ? `${at(a.effect?.target)} ${a.animationName}`
                                  : at(a.effect?.target));
}"""
)


def _render_version_attempt(browser, url: str) -> tuple[list, list, bool]:
    """Everything wrong with a served version that only a browser can see: a
    console or page error, a request that 404s, a fail-soft error box, an upgrade
    module that never defines its declared element, an x-conversation whose module
    placed no matching page host, a widget upgraded into a box of no usable size,
    an element showing words with no box for a mark to hang on, so a comment anchored
    there would outline nothing and the ask walk would travel to the top of the page,
    the page scrolling sideways, content set past the column and out into the margin,
    words the user can read and can't select, words drawn on top of other words, code
    coloured in an ink the reader cannot tell from the code around it — each
    in both color schemes, because the dark theme is real CSS nobody otherwise
    renders — plus, in one scheme, a word the registry promised that never reached
    the page (a declaration is scheme-blind), an attribute a module left standing on a
    widget that its entry never declared (a file's reading sees one writer, and this is
    the other), a version that authors widget state the log replays over, a widget whose
    applyAction is relative, so the poll's replay of the sender's own gesture moves the
    page again (none of the three is CSS), a settled holder whose mark or still-showing
    slot words disagree with the log's decision (read once, on the premise the
    trapped-margin reading shares: the palettes carry no geometry between them), a box
    drawing one inset and showing another,
    and, on paper, words the page drops that it says on screen, or draws over each other
    (print is scheme-blind). Returns human-readable failures; [] is a pass.

    One implementation with two callers — `version check --render` on the page an agent
    just wrote, and the render suite on the shipped examples
    (tests/test_render.py) — so the gate and the suite hold one set of
    invariants. Returns ordinary failures, ResizeObserver notices, and whether every
    reading completed. `browser` is a live Playwright browser; nothing here imports
    playwright at module level, so the module stays importable without it."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    def in_scheme(scheme):
        page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme=scheme)
        errors = []
        resize_notices = []

        def console_message(message):
            if message.type != "error":
                return
            (resize_notices if resize_observer_error(message.text) else errors).append(
                message.text
            )

        page.on("console", console_message)
        page.on("pageerror", lambda e: errors.append(str(e)))
        # The console's own word for a bad response is "Failed to load resource",
        # which names nothing; carry the status and URL so a failure says what
        # went missing.
        page.on(
            "response",
            lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
        )
        page.add_init_script(WINDOW_ERRORS)
        try:
            page.goto(url, wait_until="networkidle")
            page.wait_for_function(
                "() => document.querySelector('.lf-banner') !== null"
            )
        except PlaywrightTimeout:
            page.close()
            explanations = [*errors, *resize_notices]
            return (
                [
                    f"[{scheme}] the runtime never injected its banner — "
                    + ("; ".join(explanations) or "and no console error explains why")
                ],
                [],
                False,
            )
        # Every reading below is of a settled page. The widget layer writes half the
        # document, so a box measured while it is still drawing belongs to no version of
        # the page — which is the stamp `version export` waits on for the same reason.
        try:
            page.wait_for_function(UPGRADED)
        except PlaywrightTimeout:
            page.close()
            explanations = [*errors, *resize_notices]
            return (
                [
                    f"[{scheme}] the widget layer never finished upgrading — "
                    + ("; ".join(explanations) or "and no console error explains why")
                ],
                [],
                False,
            )
        # The served documents every reading below is asked against, read once each
        # (`served` says why they are read from out here rather than fetched inside
        # the page). The registry alone used to be fetched seven times a scheme, to
        # answer seven questions about one document. What the readings get now is
        # data, so most of them are plain synchronous DOM walks with nothing left in
        # them to await, let alone hang in.
        try:
            registry = served(page, url, "/registry.json").json()
            # The readings in the page mean widgets, so they are handed only those:
            # $keys spells its members in the x- keys' own names, and a sweep over
            # every entry took it for a widget called $keys.
            widgets = {tag: e for tag, e in registry.items() if tag.startswith("lf-")}
            state = served(page, url, "/api/state").json()
            markup = served(page, url, urlsplit(url).path).text()
            # Which version this is, parsed once for every reading that needs it:
            # the gate is always pointed at a version file, so the path stating
            # which one is a fact to read rather than something to test for.
            here = version_num(Path(urlsplit(url).path).name)
            # The version before this one, for the conflict reading below: which
            # pair it compares is a question about the log and the URL, both of
            # which are held out here. A first version has no predecessor to have
            # authored anything against.
            before = previous_version(here, state["versions"])
            earlier = (
                served(page, url, f"/versions/v{before}.html").text()
                if before
                else None
            )
        except PlaywrightTimeout as e:
            page.close()
            # The first line only: the rest is playwright's call log, which says
            # nothing about the page that a reader of this failure needs.
            return (
                [
                    *[f"[{scheme}] console: {error}" for error in errors],
                    *[f"[{scheme}] console: {notice}" for notice in resize_notices],
                    (
                        f"[{scheme}] the server stopped answering: "
                        f"{str(e).splitlines()[0]}"
                    ),
                ],
                [],
                False,
            )
        # The widgets the log has moved, in the log's order. Both replayed kinds,
        # once: the caught-up stamp counts reports beside actions, so the wait below
        # counts what this holds, and the verbatim reading excuses exactly these.
        touched = [
            e["widget"] for e in state["events"] if e["kind"] in ("action", "report")
        ]
        # Every reading below is of a page at rest, and the upgrade stamp above is
        # one third of that. The stamp is written without awaiting the first poll, so
        # a gate reading there reads the authored board, the unanswered question and
        # the body the reader has since rewritten — a page nobody is shown. The
        # caught-up stamp is the log's answer to that, and the frame it lands in is
        # the first frame of whatever the replay set moving, a replay past the
        # presentation boundary moving rather than teleporting. Both waits are taken
        # in both schemes, because every reading below has boxes or words in it. The
        # windows open under load alone, which is how one page passed at a desk and
        # reported words drawn over words under a full suite ("The page finishes
        # twice", in the layer's own CLAUDE.md).
        unsettled = []
        replayed = True
        if touched:
            applied = len(touched)
            try:
                page.wait_for_function(
                    "(applied) => Number(document.body.dataset.lfApplied ?? -1)"
                    " >= applied",
                    arg=applied,
                )
            except PlaywrightTimeout:
                replayed = False
                stalled = (
                    "the runtime never finished replaying the log "
                    f"({applied} action(s))"
                )
                unsettled = [stalled]
        if replayed:
            try:
                page.wait_for_function(f"() => ({MOVING})().length === 0")
            except PlaywrightTimeout:
                unsettled = [
                    "the page never stopped moving: " + ", ".join(page.evaluate(MOVING))
                ]
        failsoft = page.evaluate(
            "[...document.querySelectorAll('.lf-error')].map(e => e.textContent.trim())"
        )
        missing_upgrades = page.evaluate(
            """(widgets) => Object.entries(widgets)
                .filter(([tag, entry]) => entry['x-upgrade'] && !customElements.get(tag))
                .map(([tag]) => tag)""",
            widgets,
        )
        tiny = page.evaluate(TINY_BOXES, widgets)
        unmarkable = page.evaluate(UNMARKABLE_ITEMS)
        overflow = page.evaluate(
            "document.body.scrollWidth - document.body.clientWidth"
        )
        misplaced = page.evaluate(MISPLACED_BOXES)
        clipped = page.evaluate(CLIPPED_CONTROLS)
        unreachable = page.evaluate(UNREACHABLE_WORDS)
        covered = page.evaluate(COVERED_WORDS)
        unread = page.evaluate(UNREAD_SYNTAX)
        # Shadow roots the registry doesn't declare: the passage walk, the
        # capture and the id lookups cross exactly the declared ones, so an
        # undeclared root's words silently anchor quotes astray. UA shadow roots
        # are closed and invisible here; anything open was attached by a module.
        undeclared_shadow = page.evaluate(
            """(registry) => [...new Set([...document.querySelectorAll('*')]
                .filter(el => el.shadowRoot && !registry[el.localName]?.['x-shadow'])
                .map(el => `<${el.localName}>`))]""",
            registry,
        )
        # Replay is scheme-blind, so one scheme's reading covers both.
        conflicts = []
        dishonest_verbatim = []
        silent = []
        missing_conversations = []
        undeclared_attrs = []
        retired = []
        if scheme == "light":
            # x-conversation promises one page view per matching instance. A widget in
            # thread chrome already has the thread's reply surface and conversationBox
            # deliberately returns none there. Everywhere else, ask the merged registry
            # for the instances and the module's own marker for the host it placed.
            missing_conversations = page.evaluate(
                """(widgets) => import('/leaf.js').then(leaf =>
                    Object.entries(widgets)
                        .filter(([, entry]) => entry['x-conversation'])
                        .flatMap(([tag, entry]) => [...document.querySelectorAll(tag)]
                            .filter(el => !leaf.inChrome(el) && !leaf.quoted(el)
                                && leaf.matchesWhen(
                                    el, entry['x-conversation'].when))
                            .map(el => ({
                                tag,
                                id: el.id,
                                hosts: [...el.querySelectorAll('.lf-conversation')]
                                    .filter(host =>
                                        host.dataset.lfConversation === el.id).length,
                            })))
                        .filter(instance => instance.hosts !== 1))""",
                widgets,
            )
            # x-verbatim honesty: the entry claims the body reaches the reader
            # as its own words, and the two readings built on that claim — the
            # browser's says() and the file's spoken() — are compared here on
            # every instance the log hasn't moved (a decided or rewritten
            # widget legitimately shows other words). A module that renders
            # something in the body's stead while the entry still says
            # verbatim strands quotes on words the screen no longer shows.
            shown = page.evaluate(
                """({widgets, touched}) => import('/leaf.js').then(leaf =>
                    Object.entries(widgets)
                        .filter(([tag, entry]) => entry['x-verbatim'])
                        .flatMap(([tag]) => [...document.querySelectorAll(tag)]
                            .filter(el => el.id && !touched.includes(el.id))
                            .map(el => ({tag, id: el.id, says: leaf.says(el)}))))""",
                {"widgets": widgets, "touched": touched},
            )
            if shown:
                spk = spoken(markup, registry)
                dishonest_verbatim = [
                    f"<{s['tag']} id={s['id']!r}> declares x-verbatim but shows "
                    f"{s['says'][:80]!r} where the file reads "
                    f"{spk.get(s['id'], EMPTY).words[:80]!r}"
                    for s in shown
                    if s["says"] != spk.get(s["id"], EMPTY).words
                ]
            if touched and replayed and earlier is not None:
                conflicts = page.evaluate(
                    REPLAY_OVERRIDES,
                    {"curHtml": markup, "prevHtml": earlier},
                )
            # Behind the caught-up wait above: a report moves a painted attribute and
            # the pass that speaks it runs before the stamp, so a reading taken any
            # earlier asks after a word the page has not been asked to say yet. A page
            # that never caught up is already reported there and read no further.
            if replayed:
                silent = page.evaluate(SILENT_WORDS, widgets)
                # Behind the same wait, because reconciliation is one of the two
                # writers: an applyAction states one declared fact whole, and a
                # record form is exactly the attribute it may state that fact in.
                undeclared_attrs = page.evaluate(UNDECLARED_ATTRS, widgets)
                # Behind it too: the settlement mark is replay's own write, so a
                # reading taken earlier asks after paint the page has not been
                # asked to make yet. The expected outcomes are the file's, scoped
                # to each holder's own relation: `decisions` folds any verb that
                # retires somewhere in the vocabulary, so a verb of that name on
                # a family it settles nothing of decides nothing here — the
                # browser's write reads the per-holder relation, and a comparison
                # against anything wider would fail a page both sides are right
                # about.
                if slots := retirement_slots(registry):
                    projection, vparser, _ = page_projection(
                        markup, state["events"], registry, here
                    )
                    outcomes = decisions(projection.actions, registry)
                    holders = []
                    for h in retirement_holders(vparser, registry):
                        declared = slots[h["tag"]]
                        outcome = outcomes.get(h["id"])
                        if outcome not in declared:
                            outcome = None
                        holders.append(
                            {
                                "tag": h["tag"],
                                "id": h["id"],
                                "outcome": outcome,
                                "slots": sorted(declared.get(outcome, ())),
                            }
                        )
                    if holders:
                        retired = page.evaluate(RETIRED_SLOTS, holders)
        # One scheme, the palettes carrying no geometry between them, and before the
        # medium moves: a box's inset is what it declared in either.
        trapped = page.evaluate(TRAPPED_MARGINS) if scheme == "light" else []
        # Last, and in one scheme: paper has no color scheme, and the medium has to be
        # put back before anything else reads a box.
        on_paper = []
        if scheme == "light":
            screen = page.evaluate(PAPER_WORDS)
            page.emulate_media(media="print")
            paper = page.evaluate(PAPER_WORDS)
            # Paper is laid out by rules no other medium runs, and it is the medium
            # nobody looks at, so the overlap reading is taken here too while it holds.
            on_paper = [f"[print] {c}" for c in page.evaluate(COVERED_WORDS)]
            page.emulate_media(media="screen")
            # Paired on the words as well as the position: the page is live, and a poll
            # landing between the two readings would otherwise shift one against the
            # other and report whatever happened to line up. A pair that disagrees says
            # nothing, which is the right way round — the next run reads it again.
            on_paper += [
                f"[print] {s['at']} drops {json.dumps(s['text'])}, which it says on screen"
                for s, p in zip(screen, paper)
                if s["text"] == p["text"] and s["shown"] and not p["shown"]
            ]
        # Last of all, because it is the only reading here that writes: it applies each
        # standing action again, which is a no-op exactly when the contract holds and a
        # page nobody should read any further when it doesn't. Behind the same caught-up
        # wait as the conflicts above, for the same reason — a page mid-replay has not
        # finished producing the state the second application is measured against.
        relative = []
        if scheme == "light" and replayed:
            relative = page.evaluate(RELATIVE_REPLAYS)
        # The print reset and replay above can resize what an observer watches. Chrome
        # delivers that notice in the next rendering turn, so closing on the write
        # would call an attempt complete before its last error channel had spoken.
        page.evaluate("() => new Promise(requestAnimationFrame)")
        page.close()
        found = [f"[{scheme}] console: {e}" for e in errors]
        found += [f"[{scheme}] a widget failed soft: {t}" for t in failsoft]
        if missing_upgrades:
            found.append(
                f"[{scheme}] upgraded widgets did not define their elements: "
                + ", ".join(f"<{tag}>" for tag in missing_upgrades)
            )
        if tiny:
            found.append(
                f"[{scheme}] widgets rendered with no usable size: {json.dumps(tiny)}"
            )
        found += [
            f"[{scheme}] <{u['tag']} id={u['id']!r}> shows {u['w']}x{u['h']}px of words"
            " and offers no box to mark: it draws none of its own and no element inside"
            " it draws one either, so a comment anchored here would outline nothing and"
            " the ask walk would travel to the top of the page. Put the words in an"
            " element that takes a box"
            for u in unmarkable
        ]
        if overflow > 0:
            found.append(f"[{scheme}] the page scrolls sideways by {overflow}px")
        found += [f"[{scheme}] {s}" for s in misplaced]
        found += [
            f"[{scheme}] the control .{c['ctrl'].split()[0]}"
            + (f" (#{c['id']})" if c["id"] else "")
            + f" is drawn {c['lost']}px outside the {c['by']} that clips it, where"
            " nothing can scroll to reach it — the page offers a press it does not show"
            for c in clipped
        ]
        found += [f"[{scheme}] {w}" for w in unreachable]
        found += [f"[{scheme}] {c}" for c in covered]
        found += [f"[{scheme}] {u}" for u in unread]
        if undeclared_shadow:
            found.append(
                f"[{scheme}] shadow roots the registry doesn't declare "
                f"(an undeclared root's words anchor quotes astray; declare "
                f"x-shadow): {', '.join(undeclared_shadow)}"
            )
        found += [f"[{scheme}] {d}" for d in dishonest_verbatim]
        found += [f"[{scheme}] {s}" for s in silent]
        for c in missing_conversations:
            found.append(
                f"[{scheme}] <{c['tag']} id={c['id']!r}> declares x-conversation but "
                f"rendered {c['hosts']} matching hosts; its module must place exactly "
                "one conversationBox"
            )
        for u in {(x["tag"], x["attr"]): x for x in undeclared_attrs}.values():
            found.append(
                f"[{scheme}] <{u['tag']} id={u['id']!r}> carries {u['attr']!r}, which "
                "its registry entry does not declare — declare it as a verb's record "
                "form (x-state) if a version is meant to carry it, or write the state "
                "on the chrome the module built"
            )
        for t in {(x["tag"], x["edge"]): x for x in trapped}.values():
            box = f"<{t['tag']}" + (f" class={t['cls']!r}" if t["cls"] else "") + ">"
            found.append(
                f"[{scheme}] {box} draws {t['drawn']:g}px of inset and shows "
                f"{t['drawn'] + t['margin']:g}px {t['edge']} what it holds "
                f"(id={t['id']!r}): its {t['edge'] == 'above' and 'first' or 'last'} "
                f"block is a <{t['child']}> reserving {t['margin']:g}px against a "
                f"neighbour it hasn't got, and the box is where that margin stops. "
                f"Declare --lf-frame: 1 in the rule that draws the frame, so the trim "
                f"in theme.css reaches it"
            )
        found += [f"[{scheme}] {r}" for r in retired]
        found += [f"[{scheme}] {u}" for u in unsettled]
        found += [f"[{scheme}] {c}" for c in conflicts]
        found += [f"[{scheme}] {r}" for r in relative]
        found += on_paper
        notices = [f"[{scheme}] console: {e}" for e in resize_notices]
        return found, notices, True

    light, light_notices, light_complete = in_scheme("light")
    dark, dark_notices, dark_complete = in_scheme("dark")
    return (
        [*light, *dark],
        [*light_notices, *dark_notices],
        light_complete and dark_complete,
    )


def render_version(browser, url: str) -> list:
    """Read a version, confirming a complete attempt that reports a ResizeObserver
    loop notice.

    Chrome can emit the notice once under load, while a layout feedback loop emits it
    on every rendering. The unit here is the whole light-and-dark gate, including its
    print and replay probes: a notice is ignored only when a later complete attempt is
    clean. Ordinary failures from both attempts are retained, and an incomplete
    confirmation cannot pardon the notice that prompted it.
    """
    failures = []

    def retain(found):
        failures.extend(failure for failure in found if failure not in failures)

    found, notices, complete = _render_version_attempt(browser, url)
    retain(found)
    if not complete:
        retain(notices)
        return failures
    if not notices:
        return failures

    found, confirming_notices, complete = _render_version_attempt(browser, url)
    retain(found)
    if not complete:
        for notice in [*notices, *confirming_notices]:
            retain([f"{notice} (the confirming render attempt did not complete)"])
        return failures
    if confirming_notices:
        failures.append(recurring_resize_observer_error("render attempt"))
    return failures


@contextlib.contextmanager
def preview_server(page_dir: Path, version: int, transition_held: bool = False):
    """The page directory on a loopback port, exposing versions up to this one, for
    the length of a `with`. Two callers need a browser to see a version the user
    may not have (`version check --render` before its note lands, `version export`
    on any published one), and the preview window is what lets them: the server's
    own liveness rule is the user's, and this widens it for exactly one process."""
    # Its own key, not the machine's: this server is loopback-only and lives for
    # the length of a `with`, so it neither needs nor should mint the access every
    # page here is read with. It sets that key under the one cookie name, which
    # would sign a reader out of every page on 127.0.0.1 — except that both
    # callers below drive Playwright, whose browser brings its own jar.
    transition = (
        contextlib.nullcontext()
        if transition_held
        else flocked(transition_lock(page_dir))
    )
    with transition:
        token = secrets.token_urlsafe(16)
        httpd = LeafHTTPServer(
            ("127.0.0.1", 0), handler_for(page_dir, token, preview_upto=version)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/versions/{version_name(version)}?t={token}"
        finally:
            httpd.shutdown()


def render_check(page_dir: Path, version: int, transition_held: bool = False) -> int:
    """Serve the page directory to the machine's installed Chrome and run the
    render invariants on this version.

    Playwright is the gate's own extra, not the script's: declaring it in the
    PEP 723 header would put its wheel in every `server run`, `leaf wait`, and
    `version publish`, so the import happens here and its absence names the
    invocation that supplies it. Chrome is part of this gate: if it cannot
    launch, the gate fails."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "version check --render needs Playwright; run it as\n"
            "  leaf version check <page> --render\n"
            "or, from a checkout,\n"
            "  plugins/leaf/bin/leaf version check <page> --render",
            file=sys.stderr,
        )
        return 1
    name = version_name(version)
    with (
        preview_server(page_dir, version, transition_held=transition_held) as url,
        sync_playwright() as p,
    ):
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as error:
            print(
                "✗ render check failed — Chrome did not launch: "
                + str(error).strip().splitlines()[0],
                file=sys.stderr,
            )
            return 1
        try:
            failures = render_version(browser, url)
        finally:
            browser.close()
    if failures:
        print(f"✗ {name}: renders broken — {len(failures)} issue(s)", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        f"✓ {name}: renders clean in Chrome, light and dark — no console errors, "
        "every widget takes space, no words on top of other words, code that reads "
        "against the block it is on, nothing past the column, no sideways scroll"
    )
    return 0


# ---------- export: the page as one file ----------

# What a standalone copy drops. Scripts go because there is no server behind a file
# and nothing left for them to reach; the runtime's own layer goes with them, since a
# comment box that swallows what you type and a banner claiming someone is listening
# are worse than no chrome at all — a copy that lies about being a live page. What stays
# is everything the widgets built, and the controls they injected where the browser is
# what works them: a `lf-shot` flips on a checkbox with no script running. A press a handler
# answered leaves the words it stated and takes the rest of itself with it, below.
#
# `lf-copy` is the medium, declared the way `@media print` is and read the same way —
# by the theme, per widget. A widget whose control needed a handler puts the affordance
# behind a guard this class fails, so a copy gets the page its markup describes; one
# whose control the browser owns has no guard and keeps working. That is why no widget
# is named here: this marks the medium, and the widgets answer for themselves.
BAKE = """() => {
    document.documentElement.classList.add('lf-copy');
    document.querySelectorAll('script, .lf-chrome').forEach(el => el.remove());
    // A measurement of this window is not a fact about the reader's. The room a wide
    // widget may take is measured on the live page (syncLayout) and stated inline on the
    // root, and an inline value outranks every rule a stylesheet could write — so a copy
    // carrying it would hold whatever width the exporter's headless window happened to
    // have, on a file whose whole point is being opened somewhere else. The theme states
    // the copy's own room from its viewport, which is honest there: no panel takes a
    // strip from a file, and no session grows one. Taken off the way the chrome above is,
    // rather than guarded against in the theme, because the stale number is the thing
    // that is wrong here and a rule written around it would leave it there to be read by
    // the next thing that asks.
    //
    // The width the panel stands at is the second such number and goes for the same
    // reason rather than because anything in a copy reads it: it is stated on the root
    // by the same hand, and it is a fact about a panel this file hasn't got and about a
    // reader who is not the one opening it.
    for (const stale of ['--lf-room', '--lf-panel-w'])
        document.documentElement.style.removeProperty(stale);
    // The tab icon is the third seat of the banner's status (paintTab), and a file has
    // no session behind it — a copy keeping the tone it was exported under would claim
    // one, which is the same lie the chrome above is dropped for. So it drops back to
    // the mark as authored, which the runtime left here for exactly this.
    const icon = document.querySelector('link[rel="icon"][data-lf-rest]');
    if (icon) {
        icon.href = icon.dataset.lfRest;
        icon.removeAttribute('data-lf-rest');
    }
    // hidden="until-found" is the page saying "collapsed, but the reader can still
    // get here" — a tab's inactive panel, a settled group's cards. In a copy the
    // control that would get them there is inert, so the attribute is a promise
    // nothing can keep, and it takes the collapsed element's layout down with it:
    // the theme zeroes a hidden card's padding, which is the room its chips are
    // positioned into. Dropping it opens the element on the terms it was authored
    // with, which is the layout the theme's live-page guard was withholding anyway.
    document.querySelectorAll('[hidden="until-found"]')
        .forEach(el => el.removeAttribute('hidden'));
    // A press a widget injected is a tab stop wearing an interactive role (offer), and
    // both are promises a handler kept. The handlers left with the scripts above, so a
    // copy that carried them offered a press nothing can take — and the first Tab into an
    // exported decision page landed on one. It was a `choose` group's pick mark, which
    // drew the keyboard address for a key that answers nothing, into a row holding no
    // column for it: the 30px an option reserves is live-page-only, so the digit came
    // down 8px over the option's own first word.
    //
    // So the control goes and its word stays, which is the bargain paper struck first
    // (the runtime's @media print rule, on these same two markers). A mark reading
    // "chosen" is the page stating which option won, and it stays with the role and the
    // tab stop taken off it; "choose one" is an invitation, and it leaves with the grips,
    // the pills and the pencils. Where the words a removal takes with it are the page's —
    // a settled group's disclosure names its chosen card, a tab's button names its panel —
    // the copy has those open underneath saying it themselves, which is why paper drops
    // the same two.
    //
    // A copy parts from paper on one thing: it is still a document the browser runs, so a
    // control the browser drives keeps working, and lf-shot flips its frames on a checkbox in
    // a file with no script behind it. The tab stop is what tells the two apart, being the
    // runtime's own reading of a press it made (ASK_CONTROL): a checkbox, a label and a §
    // link never had one, and lf-shot's checkbox keeps the role that says what it is.
    //
    // Asked of the marker rather than of the role, because `offer`'s role="button" is not
    // what a press ends up wearing: a widget with an ARIA pattern to keep writes its own
    // over it, so every press in lf-tabs' strip says role="tab", and naming that second
    // role would have left the next widget's. The author's roles are untouched, being on
    // the author's elements: a board's columns stay a list of cards to a screen reader.
    //
    // The box a press hung in goes with it. A suggestion's control row is nothing but its
    // two controls, and left standing it still claims the rail the page reserves for it
    // (--rail) — a margin held open for controls that are no longer there. Asked of what
    // each removal empties rather than of an empty box, since a widget's own empty box is
    // a real thing: that row hangs off an anchor span which takes no space and says
    // nothing, and `anchor(top)` is measured from it.
    for (const control of
            document.querySelectorAll('[data-lf-offer][tabindex]:not([data-lf-said])')) {
        let dead = control, box = dead.parentElement?.closest('[data-lf-offer]');
        dead.remove();
        while (box && !box.firstChild) {
            dead = box;
            box = dead.parentElement?.closest('[data-lf-offer]');
            dead.remove();
        }
    }
    document.querySelectorAll('[data-lf-offer][tabindex]').forEach(el => {
        el.removeAttribute('role');
        el.removeAttribute('tabindex');
        // The states and relations rode the role: pressed="true" on a plain span is
        // ARIA nothing may interpret (axe calls it critical), where the label is the
        // word's accessible copy and stands on its own.
        for (const attr of [...el.attributes])
            if (attr.name.startsWith('aria-') &&
                !['aria-label', 'aria-hidden'].includes(attr.name))
                el.removeAttribute(attr.name);
    });
    // What the runtime painted, as against what a widget built, goes the same way. An
    // element-anchored comment's mark is a class the kept stylesheet answers with a
    // ring and a pointer hand, and the panel that hand promised left with the chrome —
    // while a text-anchored mark, painted through the highlight registry by script, is
    // already gone. One fact — a comment is anchored here — leaves the copy whole.
    document.querySelectorAll('.lf-mark-el')
        .forEach(el => el.classList.remove('lf-mark-el'));
    // A tab stop still standing on a widget element is module paint — the registry's
    // schemas admit no authored tabindex on one — promising focus to chrome whose
    // handler left with the scripts: a tabs panel's roving stop, an ask-lend. Asked
    // of the tag's dash, the platform's own mark of a custom element, so no widget
    // is named and the author's own elements are untouched. Scroll stops go with
    // the rest and come back below, where every scrollable box is answered at once.
    document.querySelectorAll('[tabindex]').forEach(el => {
        if (el.tagName.includes('-')) el.removeAttribute('tabindex');
    });
    // Then what the removals uncovered: a box that scrolls whose way in was the
    // chrome just taken out — a board whose grips were its only focusable content,
    // a diagram whose stop the sweep above stripped — has no keyboard into it, and
    // scrolling needs no handler (the lf-shot bargain). The live page's one grantor
    // is reachScrollers; its predicate is restated here because the runtime's
    // module scope left with the scripts, and this pass runs where the removals
    // have already settled what remains.
    for (const el of document.querySelectorAll('*')) {
        if (el.tabIndex >= 0) continue;
        const style = getComputedStyle(el);
        if (!/^(auto|scroll)$/.test(style.overflowX) &&
            !/^(auto|scroll)$/.test(style.overflowY))
            continue;
        if (!el.querySelector('a[href], button, input, select, textarea, ' +
                              '[tabindex]:not([tabindex="-1"])'))
            el.tabIndex = 0;
    }
    // getHTML and not outerHTML: a widget that renders the page's words into a shadow
    // root (x-shadow) has them in no element's outerHTML, so a copy taken that way
    // arrives with an empty element where a diff's lines were — silently, since the
    // element and its ids are all still there. Asking for serializable roots writes each
    // one as a declarative <template shadowrootmode>, which the browser rebuilds on open
    // with no script, the same bargain every other widget's chrome makes here.
    //
    // It is innerHTML's counterpart, though, so the root's own tag is not in what it
    // returns and has to be written back: <html> carries the lang the document is read
    // in and the lf-copy class the theme reads its medium from, and a copy missing them
    // opens as a live page whose affordances press nothing. Rebuilt from the attributes
    // rather than sliced off outerHTML's opening tag, because an attribute value may
    // hold the very > that slicing would stop at.
    const root = document.documentElement;
    const attrs = [...root.attributes]
        .map(a => ` ${a.name}="${a.value.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}"`)
        .join('');
    return `<html${attrs}>${root.getHTML({serializableShadowRoots: true})}</html>`;
}"""


def inline_assets(html: str, page_dir: Path) -> str:
    """Fold the served assets into the markup. The theme's link becomes the stylesheet
    itself and each image becomes its own bytes, which is everything the document still
    reaches the server for: the runtime's stylesheet arrived as a `<style>` in the DOM,
    the widget modules were imports rather than elements, and a `lf-ref`'s link was
    always somewhere else."""
    theme = (page_dir / "theme.css").read_text(encoding="utf-8")
    html, n = re.subn(
        r'<link[^>]+href="/theme\.css"[^>]*>',
        lambda _: f"<style>{theme}</style>",
        html,
        count=1,
    )
    if not n:
        sys.exit(
            "the rendered page carried no /theme.css link — it would open unstyled"
        )
    # References from the parsed reading, never a scan of the text: a path standing
    # in prose is the reader's words — the lesson `media_refs` itself carries — and
    # a text scan crashed the export on a documented path no file answers. The
    # attribute harvest is media_refs; a page <style>'s url(/media/…) is the one
    # reference an attribute harvest can't see, so it is read from the parsed css.
    # The substitution then rewrites only the two serialized forms a reference
    # takes (`="…"`, `url(…)`); prose quoting the exact string of a path the page
    # also really uses is the residual, and it is the author quoting live markup.
    parsed = parse_structure(html)
    css_refs = set(
        re.findall(rf"url\((/{MEDIA_DIR}/{_DIR_FILES[MEDIA_DIR]})\)", parsed.css)
    )
    for src in sorted(set(parsed.media_refs) | css_refs):
        file = page_dir / src.lstrip("/")
        data = base64.b64encode(file.read_bytes()).decode()
        uri = f"data:{MEDIA_TYPES[file.suffix]};base64,{data}"
        html = html.replace(f'="{src}"', f'="{uri}"').replace(
            f"url({src})", f"url({uri})"
        )
    return html


def export_page(browser, url: str, page_dir: Path) -> str:
    """The served version at `url`, copied as one self-contained document.

    One implementation has two callers, as `render_version` does: `version export`
    supplies installed Chrome, while the suite drives this over the shipped
    examples with its Chromium headless shell. That keeps the export behavior in
    one function without claiming that the two browser launch paths are identical.

    The user's decisions come with it. Replay is what puts them on the page, so
    this waits for the runtime's caught-up stamp exactly as the gate does, and a page
    whose board was rearranged copies rearranged."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=RENDER_VIEWPORT)
    try:
        page.goto(url, wait_until="networkidle")
        try:
            page.wait_for_function(UPGRADED)
            # Both replayed kinds, as the render gate counts them: the caught-up
            # stamp counts reports beside actions, and a page whose only recorded
            # state is a worker's report would otherwise copy before it painted.
            n_replayed = len(
                [e for e in read_events(page_dir) if e["kind"] in ("action", "report")]
            )
            if n_replayed:
                page.wait_for_function(
                    f"() => Number(document.body.dataset.lfApplied ?? -1) >= {n_replayed}"
                )
        except PlaywrightTimeout:
            sys.exit(
                f"{url.rsplit('/', 1)[-1]} never finished upgrading in the browser, so a copy "
                "would be half-drawn. `leaf version check <page> --render` says what "
                "is wrong with it."
            )
        return inline_assets(page.evaluate(BAKE), page_dir)
    finally:
        page.close()


def cmd_export(page_dir: Path, out: Path, version) -> int:
    """One published version as a standalone HTML file.

    The copy is the page as the browser finished drawing it, which is the only way to
    get one: half the document is written by the widget layer at runtime, a mermaid
    diagram becomes an SVG only once mermaid has drawn it, and a code block is colored
    by the vendored tokenizer in the page rather than by anything that can read the
    file. So Chrome is not an optimisation here and no `x-` key exempts a widget from
    it; without a browser there is nothing to copy at all."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "export needs Playwright; run it as\n"
            "  leaf version export <page> -o <file>\n"
            "or, from a checkout,\n"
            "  plugins/leaf/bin/leaf version export <page> -o <file>"
        )
    published = published_versions(page_dir, read_events(page_dir))
    if not published:
        sys.exit(
            f"{page_dir} has no published version to export; "
            "run `leaf version publish` first"
        )
    version = version if version else published[-1]
    if version not in published:
        sys.exit(
            f"v{version} is not published — published: "
            + ", ".join(f"v{v}" for v in published)
        )
    name = version_name(version)

    with preview_server(page_dir, version) as url, sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as e:
            sys.exit(
                f"export needs Chrome, and it didn't launch ({str(e).strip().splitlines()[0]}). "
                "A copy is the drawn page, so there is nothing to write without one."
            )
        try:
            html = export_page(browser, url, page_dir)
        finally:
            browser.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✓ {name} → {out} ({out.stat().st_size // 1024} KB, opens with no server)")
    return 0


def resolve_dir(dir_arg: str, must_exist: bool = True) -> Path:
    page_dir = Path(dir_arg).expanduser().resolve()
    if must_exist and not (page_dir / "comments.jsonl").is_file():
        sys.exit(
            f"{page_dir} is not an initialized page; run `leaf page init` "
            "to vendor the layer"
        )
    return page_dir


@click.group()
def cli() -> None:
    """Build and run interactive pages a session shares with its user."""


@cli.group(short_help="Create pages and add media.")
def page() -> None:
    """Create pages and add media."""


@page.command(short_help="Create or re-vendor a page directory.")
@click.argument("dir", metavar="PAGE")
def init(dir: str) -> None:
    """Create or re-vendor a page directory.

    Creates PAGE/versions/ for authored vN.html files and vendors the widget
    layer. Re-running replaces that layer, unless the page log uses vocabulary
    the incoming layer cannot read.
    """
    cmd_init(resolve_dir(dir, must_exist=False))


@cli.group(short_help="Create theme and widget customizations.")
def customize() -> None:
    """Create theme and widget customizations."""


@customize.command("theme", short_help="Create the theme override file.")
@click.option(
    "--user", is_flag=True, help="Use the user layer instead of this project."
)
def customize_theme(user: bool) -> None:
    """Create the CSS override file without replacing one that exists."""
    cmd_customize_theme(user)


@customize.command("widget", short_help="Add a widget scaffold.")
@click.argument("tag")
@click.option(
    "--user", is_flag=True, help="Use the user layer instead of this project."
)
@click.option("--upgrade", is_flag=True, help="Also create an ES-module upgrade.")
def customize_widget(tag: str, user: bool, upgrade: bool) -> None:
    """Add a registry entry and CSS scaffold for a lf-* widget."""
    cmd_customize_widget(tag, user, upgrade)


@page.command(short_help="Add images and print their page paths.")
@click.argument("dir", metavar="PAGE")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    metavar="IMAGE...",
)
def media(dir: str, files) -> None:
    """Add images and print their page paths.

    Copies each image into the page under a content-addressed name and prints
    its page path followed by its source file.
    """
    for src, url in cmd_media(resolve_dir(dir), [Path(f) for f in files]):
        print(f"{url}\t{src}")


@page.command(short_help="Print the widget and theme vocabulary.")
@click.argument("dir", metavar="PAGE")
def catalog(dir: str) -> None:
    """Print the page's widget and theme vocabulary."""
    cmd_catalog(resolve_dir(dir))


@page.command(short_help="Print where the page stands, as JSON.")
@click.argument("dir", metavar="PAGE")
def state(dir: str) -> None:
    """Fold the log onto the published page and print the result as one JSON
    object: elements, standing state and reports, record lag, open asks,
    threads, versions, presence."""
    cmd_page_state(resolve_dir(dir))


@cli.group(short_help="Check, publish, and export versions.")
def version() -> None:
    """Check, publish, and export versions."""


@version.command(short_help="Check a page version.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--version",
    type=int,
    default=None,
    metavar="N",
    help="version to check (default: latest)",
)
@click.option("--render", is_flag=True, help="also check the rendered page in Chrome")
def check(dir: str, version: int, render: bool) -> None:
    """Check a page version.

    Runs deterministic markup checks. --render also checks the drawn page in
    the installed Chrome.
    """
    sys.exit(cmd_check(resolve_dir(dir), version, render))


@version.command(short_help="Publish a checked version with a changelog.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--version", type=int, required=True, metavar="N", help="version to publish"
)
@click.option("--text", help="changelog text (default: stdin)")
def publish(dir: str, version: int, text: str) -> None:
    """Publish a checked version with a changelog.

    Checks the version first, then makes it visible to the page server.
    """
    cmd_publish(resolve_dir(dir), version, text)


@version.command(short_help="Export a published version to one HTML file.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "-o",
    "--out",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="output HTML file",
)
@click.option(
    "--version",
    type=int,
    metavar="N",
    help="published version to export (default: latest)",
)
def export(dir: str, out: Path, version: int) -> None:
    """Export a published version to one HTML file.

    Renders the version in Chrome, then writes a standalone copy.
    """
    sys.exit(cmd_export(resolve_dir(dir), out, version))


@cli.group(short_help="Start, run, or stop the local server.")
def server() -> None:
    """Start, run, or stop the local server."""


def serve_flags(command):
    """The two statements a serve takes, worn by the launcher and by the process
    it launches alike: `server start` forwards them verbatim to the `server run`
    it spawns, so one spelling is what keeps the pair from drifting."""
    for option in (
        click.option(
            "--standing",
            is_flag=True,
            help="decline the session claim, so the server outlives this session "
            "and only `leaf server stop` ends it — for a page kept up across "
            "sessions",
        ),
        click.option(
            "--host",
            metavar="NAME",
            help="bind every interface and put NAME in the URL, for a user the "
            "derived address can't reach; recorded in service.json",
        ),
    ):
        command = option(command)
    return command


@server.command(short_help="Start a page's server and print its URL.")
@click.argument("dir", metavar="PAGE")
@serve_flags
def start(dir: str, host: str | None, standing: bool) -> None:
    """Start a page's server and print its URL.

    Returns as soon as the server is up; the server itself keeps running in a
    session of its own. `leaf server stop` takes one down, and a session server
    goes down with the session that claimed it besides. A page already served
    prints that server's URL and is left alone.
    """
    page_dir = resolve_dir(dir)
    claim_transition = None if standing else take_page_claim(page_dir)
    if claim_transition:
        # Check the claim after taking it. The child checks it again under its
        # own transaction, so SessionEnd winning the spawn gap makes startup
        # fail instead of reviving a released page.
        with PageTransaction(page_dir) as page:
            if not page.owned_by(host_identity()):
                raise SystemExit(
                    f"this session no longer owns {page_dir}; the server was not started"
                )
    started = start_server(page_dir, host, standing)
    if not started:
        # A refusal or failed bind never transfers the page. Restore the prior
        # provenance only if nobody replaced this startup's exact claim.
        restore_page_claim(page_dir, claim_transition)
        raise SystemExit(1)
    url, note = started
    print(url)
    print(note, file=sys.stderr)


@server.command(short_help="Serve a page in the foreground until stopped.")
@click.argument("dir", metavar="PAGE")
@serve_flags
def run(dir: str, host: str | None, standing: bool) -> None:
    """Serve a page in the foreground, printing its URL and running until stopped.

    Run this in a terminal of your own to hold a page up where you can watch it.
    From an agent session use `server start`. A page already served prints that
    server's URL and exits.
    """
    page_dir = resolve_dir(dir)
    claim_transition = None if standing else take_page_claim(page_dir)
    try:
        cmd_serve(page_dir, host, standing)
    except BaseException:
        restore_page_claim(page_dir, claim_transition)
        raise


@server.command("_serve", hidden=True)
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option("--revive", is_flag=True, hidden=True)
def _serve(dir: str, host: str | None, standing: bool, revive: bool) -> None:
    """Private child process spawned by server start and Watch revival."""
    cmd_serve(resolve_dir(dir), host, standing, revive)


@server.command(short_help="Stop a page's server.")
@click.argument("dir", metavar="PAGE")
def stop(dir: str) -> None:
    """Stop a page's server."""
    print(cmd_stop(resolve_dir(dir)))


@cli.command(short_help="Set the agent's banner state.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["working", "waiting", "idle"]))
@click.argument("detail", required=False, default="")
def status(dir: str, state: str, detail: str) -> None:
    """Set the agent's banner state.

    DETAIL is what the banner says after the state: what you are doing while
    `working`, and what you want back from the reader while `waiting` ("pick a
    storage engine"). A waiting page that declares none falls back to the
    standing "select text to comment".
    """
    page_dir = resolve_dir(dir)
    # Idling over an event nobody has answered ends the leaf on a user still
    # owed one — unread, or read and left. The watcher's whole batch, not the
    # reader-facing count, so a worker's report cannot be left standing as
    # provisional state forever either. Here rather than in cmd_status because
    # the log lock gives the check and the transition one order with an event
    # arriving or an acknowledgement advancing the cursor.
    if state != "idle":
        cmd_status(page_dir, state, detail)
        return
    with PageTransaction(page_dir) as page:
        events = page.events
        cursor = page.cursor
        pending = len(unacknowledged(events, cursor))
        unanswered = unanswered_asks(events, cursor)
        if pending:
            prefix = (
                f"{pending} update{'s' if pending != 1 else ''} nobody has picked up; "
                "idling ends the leaf over them; "
            )
            sys.exit(
                prefix + "`leaf wait` prints them and returns at once when events are "
                "already waiting. The wait owner must finish the delivery contract "
                "before idling. " + ACK_BATCH_INSTRUCTION
            )
        if unanswered:
            ids = ", ".join(t["id"] for t in unanswered)
            sys.exit(
                f"{len(unanswered)} acknowledged "
                f"comment{'s' if len(unanswered) != 1 else ''} with no answer "
                f"({ids}); idling ends the leaf over them. " + ANSWER_ASK_INSTRUCTION
            )
        page.set_status(state, detail)


@cli.command(
    short_help="Print one page's unacknowledged events and reports, then exit.",
    help=(
        "Watch every page this session holds — plus PAGE, claimed first, when "
        "given — and print one page's unacknowledged user events and worker "
        "reports as JSON lines under a first line naming the page.\n\n"
        + ACK_BATCH_INSTRUCTION
    ),
)
@click.argument("dir", metavar="PAGE", required=False)
def wait(dir: str | None) -> None:
    """Print one page's unacknowledged events and reports, then exit."""
    sys.exit(cmd_wait(resolve_dir(dir) if dir else None))


@cli.command(
    short_help="Acknowledge one complete, untruncated wait batch.",
    help=ACK_BATCH_INSTRUCTION,
)
@click.argument("dir", metavar="PAGE")
@click.argument("seq", type=click.IntRange(min=1), metavar="SEQ")
def ack(dir: str, seq: int) -> None:
    """Acknowledge one complete, untruncated wait batch."""
    cmd_ack(resolve_dir(dir), seq)


@cli.command(short_help="Open an agent thread — on a passage, or on the page whole.")
@click.argument("dir", metavar="PAGE")
@click.option("--quote", help="passage text from the published version")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--text", help="comment text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
def comment(dir: str, quote: str, section: str, text: str, markup: str) -> None:
    """Open a thread as the agent (--text or stdin): anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    The user answers it in the browser and resolves it there. Refuses a quote the
    published version does not hold, or holds more than once.
    """
    cmd_comment(resolve_dir(dir), quote, section, text, markup)


@cli.command(short_help="Reply to a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option("--to", required=True, metavar="ID", help="comment or reply ID to answer")
@click.option("--text", help="reply text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
def reply(dir: str, to: str, text: str, markup: str) -> None:
    """Post a threaded reply as the agent (--text or stdin)."""
    print(json.dumps(cmd_reply(resolve_dir(dir), to, text, markup), ensure_ascii=False))


@cli.command(short_help="Close a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--to", required=True, metavar="ID", help="a message in the thread to close"
)
def resolve(dir: str, to: str) -> None:
    """Close a thread as the agent.

    The reader's own ✓ Resolve is the ordinary way a thread closes, so this is for
    the cases where waiting on them says nothing: they asked for it closed, or the
    thread is plainly moot — what it was about has left the page, or the work has
    since answered the question it put. Reply first where the thread asked something —
    closing is not an answer, and the panel names the agent that did it.
    """
    cmd_resolve(resolve_dir(dir), to)


@cli.command(short_help="Report a state change onto a page widget, as a worker.")
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(dir: str, widget: str, verb: str, fields: tuple) -> None:
    """Report a state change onto a page widget, as a worker.

    The verb and its fields are the widget's own x-report declaration —
    `leaf report <page> t-parser status status=review` moves a task. The
    page paints the report live as provisional news; it stands until a version
    absorbs or overrules it, and the page's watcher wakes to fold it in.
    """
    cmd_report(resolve_dir(dir), widget, verb, fields)


@cli.command(short_help="Print the event log as JSON lines.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--after",
    type=int,
    default=0,
    metavar="SEQ",
    help="print events after this sequence",
)
def events(dir: str, after: int) -> None:
    """Print the event log as JSON lines.

    This is read-only and does not acknowledge user events.
    """
    cmd_events(resolve_dir(dir), after)


@cli.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> None:
    """Print the page's exchange as Markdown."""
    cmd_transcript(resolve_dir(dir))


@cli.command(hidden=True)
def hook() -> None:
    """Answer an agent-host hook on stdin."""
    cmd_hook(json.load(sys.stdin))


if __name__ == "__main__":
    # `leaf` is the name the skill hands an agent and the name on PATH, so it is
    # the name the usage lines have to say back, whichever way the script was reached.
    cli(prog_name="leaf")
