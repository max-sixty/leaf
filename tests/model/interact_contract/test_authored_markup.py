"""What `page check` refuses in authored markup, and how sample documents are read,
checked and seeded with their source thread's history."""

import json

import pytest
from interact_support import (
    PAGE,
    PAGE_GROUP,
    append_carried_log_record,
    bound_twice,
    check,
    check_findings,
    command_findings,
    command_notes,
    found,
    published,
    styled,
)

from leaf.base.findings import Finding
from leaf.source import passages as passages_model
from leaf.source import structure as structure_model


def test_check_refuses_the_runtimes_own_markers_in_authored_markup(page_dir):
    """The runtime writes data-lf-* attributes and lf- classes as its own record
    and reads them back: authored words inside .lf-chrome leave every reading,
    .lf-quiet clips them to a point nobody can see or select, and an authored
    data-lf-gen makes cells the file-side reading has no fence for.

    Both namespaces are reserved by prefix, so the fourth element here wears a
    class the runtime does not coin today and is refused all the same. A list of
    the names it happens to write is a list that admits the next one it coins:
    were .lf-quiet outside such a list, the chrome stylesheet would clip an
    authored copy of it to 1x1 with both render gates skipping the class
    unconditionally, so nothing anywhere would say the page's own words had
    gone. The <p class="note"> is the control: an ordinary class is the author's
    to write, and the count below is exact so a reservation that swallowed it
    would be caught here rather than in a page that stopped rendering. The box
    wears the name a kernel idiom gives a page's own scroller
    (`structure.AUTHORED_CLASSES`), which the reservation leaves to the author, and
    the button the names of Leaf's own controls, which a page's controls no longer
    write to take their faces (the theme gives them those)."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><div class="lf-chrome"><p id="w">words</p></div>'
            '<p id="q" class="lf-quiet">said out of sight</p>'
            '<p id="n" class="lf-not-coined-yet">a name the runtime has not taken</p>'
            '<p id="k" class="note">an ordinary class the author owns</p>'
            '<div id="s" class="lf-scroll">a box the page scrolls</div>'
            '<button id="b" class="lf-btn lf-commit">Send</button>'
            '<p id="g" data-lf-gen="1">generated-looking</p>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    # Exactly these markers: an ordinary class among them would mean the reservation
    # reaches past the lf- namespace.
    assert [
        (f.at, f.values["markers"]) for f in found(findings, "reserved-markers")
    ] == [
        ("<div>", ["lf-chrome"]),
        ("<p>", ["lf-quiet"]),
        ("<p>", ["lf-not-coined-yet"]),
        ("<button>", ["lf-btn", "lf-commit"]),
        ("<p>", ["data-lf-gen"]),
    ]


def test_check_requires_an_initialized_page(tmp_path):
    d = tmp_path / "bare"
    d.mkdir(parents=True)
    (d / "index.html").write_text(PAGE)
    result = check(d)
    assert result.exit_code == 1
    assert f"{d} is not an initialized page" in result.output


def test_check_rejects_an_invalid_bound_and_advises_on_loose_pane_text(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><pre data-bound="bottom">log</pre>'
            '<lf-pane id="queue" label="Queue">loose<p>Two</p></lf-pane>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings,
        "allocation-value",
        "<pre>",
        line=9,
        attr="data-bound",
        value="bottom",
        allowed=["start", "end"],
    )
    (pane,) = found(findings, "pane-body", "<lf-pane>", body=["#text", "p"])
    assert pane.severity == "advice"


@pytest.mark.parametrize(
    "items,advised",
    [
        ("<section id=open-items>{}</section>", True),
        ("<section id=open-items hidden=until-found>{}</section>", True),
        ("<section id=open-items hidden>{}</section>", False),
        ("<dialog id=open-items open>{}</dialog>", False),
    ],
)
def test_check_advises_a_workspace_to_keep_one_body(page_dir, items, advised):
    """A workspace's bodies share the window's height evenly, so a list written between
    its header and its regions halves them and leaves blank space under its own lines,
    with nothing out of reach for the render check to see. A body that takes no room
    takes no share, as a script, a dialog or one the page hides does, while one hidden
    until found keeps its box."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<main>",
            '<main class="layout-workspace"><header><h1>Plan</h1></header>'
            + items.format("<ul><li>Merge it</li></ul>")
            + "<script>void 0</script>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    tag = items[1 : items.index(" ")]
    assert [
        (f.at, f.values["line"], f.values["bodies"], f.severity)
        for f in found(findings, "workspace-bodies")
    ] == [
        (
            "<main>",
            7,
            [f"<{tag} id=open-items>", "<lf-group id=plan-questions>"],
            "advice",
        )
    ] * advised


@pytest.mark.parametrize("target", ["Plan_Notes", "missing-notes"])
def test_a_reference_names_any_element_the_page_holds(page_dir, target):
    """A `refers` attribute takes the id of whatever element it names, a section
    whose id a widget couldn't carry included, and `page check` refuses only a value
    naming no element."""
    (page_dir / "index.html").write_text(
        PAGE.replace('<section id="plan"', '<section id="Plan_Notes"').replace(
            '<lf-option id="flag-first" label="Flag first">',
            f'<lf-option id="flag-first" label="Flag first" for="{target}">',
        )
    )
    _status, findings = check_findings(page_dir)
    assert not found(findings, "attribute-schema", "<lf-option>")
    assert bool(found(findings, "unknown-reference")) == (target == "missing-notes")


def test_check_rejects_an_unknown_authored_width(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><table data-width="full"><tr><td>A</td></tr></table>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings,
        "allocation-value",
        "<table>",
        line=9,
        attr="data-width",
        value="full",
        allowed=["wide", "available"],
    )


def test_check_advises_a_label_where_a_card_leads_with_a_strong(page_dir):
    """An option or card leading with a <strong>, past any chips, with no `label` draws
    as bold words rather than a titled card and is named by all its words, so `page
    check` advises its name in `label`. Bold words after words of the option's own, or
    an option with a label and its <strong> title, draw no advice."""
    (page_dir / "index.html").write_text(
        PAGE.replace(PAGE_GROUP, '<lf-options id="plan-choice">').replace(
            '<lf-option id="flag-first" label="Flag first">',
            '<lf-option id="old"><small class="lf-tag">x</small> <strong>Old</strong> w.'
            '</lf-option><lf-option id="bare">Keep <strong>it</strong></lf-option>'
            '<lf-option id="flag-first" label="Flag first">',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    assert [(f.at, f.severity) for f in found(findings, "unnamed-card")] == [
        ("<lf-option id=old>", "advice")
    ]


def test_check_takes_a_rail_only_by_name(page_dir):
    """`data-rail` says whether the page keeps a rail, naming one of the two answers."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<body>", '<body data-rail="none">')
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "index.html").write_text(
        PAGE.replace("<body>", '<body data-rail="left">')
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings,
        "allocation-value",
        "<body>",
        attr="data-rail",
        value="left",
        allowed=["right", "none"],
    )


def test_source_reading_preserves_foreign_graphics_as_exact_markup():
    graphic = (
        '<svg id="plot" viewBox="0 0 10 10">\r\n'
        '<circle cx="5" cy="5" r="4"/>\r\n'
        '<svg><text x="0">A &amp; B</text></svg>'
        "<foreignObject><p>HTML <strong>inside</strong></p></foreignObject>\r\n"
        "</svg >"
    )
    html = "<main>Préface\r\n" + graphic + '<p id="after">After</p></main>'
    parser = structure_model.SourceDocument(html)
    [main] = parser.authoring.content
    _, image, after = main["content"]
    assert image["markup"] == graphic
    assert image["content"] == []
    assert image["line"] == 2
    assert after["attrs"]["id"] == "after"
    assert after["content"] == ["After"]


def test_source_reading_keeps_a_sample_out_of_its_parent_identity_space():
    """Child documents keep their own ids, widgets, passages, and validation reading."""
    html = (
        '<main><p id="visible">Visible words.</p>'
        '<template id="practice" data-sample><lf-group id="nested-ask" label="Hidden question">'
        '<h2 id="nested-ask-h">Hidden question</h2><lf-options id="nested-options">'
        '<lf-option id="nested-choice">Hidden answer</lf-option>'
        "</lf-options></lf-group></template></main>"
    )
    parser = structure_model.SourceDocument(html)

    assert parser.authoring.errors == []
    assert parser.lf_elements == []
    assert "nested-options" not in parser.by_id
    assert passages_model.page_passages(parser).text == "Visible words."
    [sample] = parser.samples
    assert "nested-options" in sample["document"].by_id
    assert sample["document"].authoring.main_elements == [(1, True)]
    assert structure_model.page_layout(sample["document"], {}) == "column"


def test_a_sample_template_names_its_children_layout():
    """A sample is a column page unless its template's class names another Layout, so a
    workspace can be shown as one."""
    parser = structure_model.SourceDocument(
        '<main><template id="desk" data-sample class="layout-workspace density-working">'
        "<header><h1>Desk</h1></header><div>Body</div></template></main>"
    )
    [sample] = parser.samples
    assert structure_model.page_layout(sample["document"], {}) == "workspace"
    main = sample["document"].tree.select_one("body > main")
    assert main.attrs["class"] == ["layout-workspace", "density-working"]


def test_the_root_names_the_layout_of_a_child_of_a_main_without_one():
    """Delivery repeats the page's Layout on the root for the body rules that run before
    `main` is parsed, so a Layout on a child of a `main` that carries none goes across
    too, including under a `main` that carries only a block's Layout, while a child the
    page hides names none."""
    in_child = structure_model.SourceDocument(
        '<main><section class="layout-column"><p>Words.</p></section></main>'
    )
    under_tiles = structure_model.SourceDocument(
        '<main class="layout-tiles"><section class="layout-workspace">'
        "<p>Words.</p></section></main>"
    )
    assert structure_model.page_layout(in_child, {}) == "column"
    assert structure_model.page_layout(under_tiles, {}) == "tiles workspace"
    beside_hidden = structure_model.SourceDocument(
        '<main><section class="layout-column"><p>Words.</p></section>'
        '<section class="layout-workspace" hidden><p>Queue.</p></section></main>'
    )
    assert structure_model.page_layout(beside_hidden, {}) == "column"


def test_the_root_names_the_layouts_of_a_page_of_parts():
    """Which part opens is the browser's, so every part's Layout goes across, and a box
    at a part's depth under any other child names none."""
    registry = {
        "lf-parts": {
            "views": {"members": "lf-part", "parts": True},
        },
        "lf-tabs": {
            "views": {"members": "lf-tab"},
        },
    }
    parts = structure_model.SourceDocument(
        '<main><header><h1>Review</h1></header><lf-parts id="parts">'
        '<lf-part id="try" label="Try"><div class="layout-workspace"></div></lf-part>'
        '<lf-part id="read" label="Read"><article class="layout-column"></article>'
        "</lf-part></lf-parts></main>"
    )
    tabs = structure_model.SourceDocument(
        '<main><lf-tabs id="tabs"><lf-tab id="one" label="One">'
        '<div class="layout-workspace"></div></lf-tab></lf-tabs></main>'
    )
    assert structure_model.page_layout(parts, registry) == "workspace column"
    assert structure_model.page_layout(tabs, registry) is None


SAMPLE_DOCUMENT_CASES = [
    ('<lf-unknown id="bad">Unknown</lf-unknown>', "unknown-widget", ("practice",)),
    ('<lf-draft id="change" restated><pre>Text</pre></lf-draft>', None, ()),
    (
        "<template data-sample><h1>Child</h1></template>",
        "unnamed-sample",
        ("practice",),
    ),
    (
        '<p id="duplicate">One</p><p id="duplicate">Two</p>',
        "duplicate-ids",
        ("practice",),
    ),
    (
        '<template id="nested" data-sample><p id="twice">One</p><p id="twice">Two</p>'
        "</template>",
        "duplicate-ids",
        ("practice", "nested"),
    ),
]


# `documents.sample_errors` is the one gate either door reads a child through, so the
# message door takes the one case that also reaches a child's own samples, and a
# binding conflict, which a message's gate reads in its own markup alone.
@pytest.mark.parametrize(
    ("markup", "code", "samples", "holder"),
    [
        *((*case, "page") for case in SAMPLE_DOCUMENT_CASES),
        (*SAMPLE_DOCUMENT_CASES[-1], "message"),
        (bound_twice("shared"), "contract-conflict", ("practice",), "message"),
    ],
)
def test_check_validates_each_sample_document(page_dir, markup, code, samples, holder):
    findings = sample_holder_findings(
        page_dir, holder, f'<template id="practice" data-sample>{markup}</template>'
    )
    errors = [finding for finding in findings if finding.severity == "error"]
    if code is None:
        assert errors == []
        return
    [refused] = found(errors, code)
    assert refused.samples == samples


def test_a_binding_conflict_is_reported_once_by_the_gate_of_its_document(page_dir):
    """A source bound under two contracts is a conflict within one document, so the
    gate that reads that document reports it, and only that gate: the page's for its
    own markup, a sample child's for the template's, and the fixture's admission for
    a fixture message's, each naming the document where the author fixes it."""
    history = [
        {"kind": "comment", "id": "aabb0011", "author": "agent", "text": "Open"},
        {
            "kind": "reply",
            "parent": "aabb0011",
            "author": "agent",
            "revision": 1,
            "text": f"Both:\n\n{bound_twice('fixture-feed')}",
        },
    ]
    sample = (
        f'<script id="fixture" type="application/json">{json.dumps(history)}</script>'
        '<template id="practice" data-sample data-sample-events="fixture">'
        f"<h1>Child</h1>{bound_twice('sample-feed')}</template>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", bound_twice("page-feed") + sample + "</main>")
    )
    _status, findings = check_findings(page_dir)
    assert [
        (conflict.samples, conflict.values["source"])
        for conflict in found(findings, "contract-conflict")
    ] == [((), "page-feed"), (("practice",), "sample-feed")]
    [fixture] = found(findings, "fixture-markup", event=2)
    assert [
        (nested.code, nested.values["source"])
        for nested in map(Finding.loads, fixture.values["findings"])
    ] == [("contract-conflict", "fixture-feed")]


@pytest.mark.parametrize("holder", ["page", "message"])
def test_a_sample_child_naming_a_missing_picture_is_refused_once(page_dir, holder):
    """A page's capture reads its samples' children with it, and a message, which no
    capture reads, asks of the children it carries at its own gate: either way a
    picture the page directory lacks is refused, and by one of the two. The capture
    names a file once however many documents name it; the message's gate names it in
    each child that does."""
    picture = '<img src="/media/0000000000000009.png" alt="shot">'
    findings = sample_holder_findings(
        page_dir,
        holder,
        f'<template id="practice" data-sample><p>{picture}</p>'
        f'<template id="nested" data-sample><p>{picture}</p></template></template>',
    )
    missing = found(findings, "missing-media", ref="/media/0000000000000009.png")
    assert [refused.samples for refused in missing] == (
        [()] if holder == "page" else [("practice",), ("practice", "nested")]
    )


@pytest.mark.parametrize("poster", ["agent", "fixture"])
def test_a_message_sample_cannot_select_the_thread_holding_it(page_dir, poster):
    """Its child would hold the same message and sample, whose child would too,
    without end."""
    sample = (
        '<lf-sample id="loop"><template id="loop-page" data-sample'
        ' data-sample-threads="aabb0011"><h1>Loop</h1></template></lf-sample>'
    )
    if poster == "agent":
        published(page_dir)
        append_carried_log_record(
            page_dir,
            {"kind": "comment", "id": "aabb0011", "author": "agent", "text": "Open"},
        )
        findings = command_findings(
            "thread",
            "reply",
            str(page_dir),
            "aabb0011",
            "--text",
            f"Try:\n\n{sample}",
            "--title",
            "Thread title",
        )
    else:
        history = [
            {"kind": "comment", "id": "aabb0011", "author": "agent", "text": "Open"},
            {
                "kind": "reply",
                "parent": "aabb0011",
                "author": "agent",
                "revision": 1,
                "text": f"Try:\n\n{sample}",
            },
        ]
        findings = sample_holder_findings(
            page_dir,
            "page",
            f'<script id="fixture" type="application/json">{json.dumps(history)}'
            '</script><template id="practice" data-sample'
            ' data-sample-events="fixture"><h1 id="child">Child</h1></template>',
        )
        [markup] = found(findings, "fixture-markup", kind="reply")
        findings = [Finding.loads(nested) for nested in markup.values["findings"]]
    assert found(findings, "sample-loop", thread="aabb0011")


def sample_holder_findings(page_dir, holder, source) -> list[Finding]:
    """Declare `source`'s samples in the page and check it, or post them in a
    message: one gate checks a sample's child wherever its template is written."""
    if holder == "page":
        (page_dir / "index.html").write_text(
            PAGE.replace("</main>", source + "</main>")
        )
        _, findings = check_findings(page_dir)
        return findings
    published(page_dir)
    return command_findings(
        "thread",
        "create",
        str(page_dir),
        "--text",
        f"Try it:\n\n{source}",
        "--title",
        "Agent thread",
    )


@pytest.mark.parametrize("nested", [False, True])
def test_sample_diagnostics_report_authored_lines(page_dir, nested):
    markup = '<lf-unknown\n id="bad">Unknown</lf-unknown>\n<noscript>Hidden</noscript>'
    if nested:
        markup = f'<template\n id="nested"\n data-sample>\n{markup}</template>'
    source = PAGE.replace(
        "</main>",
        f'<template\n id="practice"\n data-sample>\n{markup}</template></main>',
    )
    (page_dir / "index.html").write_text(source)
    status, findings = check_findings(page_dir)
    assert status == 1
    samples = ("practice", "nested") if nested else ("practice",)
    line = source[: source.index("<noscript>")].count("\n") + 1
    unknown = source[: source.index("<lf-unknown")].count("\n") + 1
    assert [(f.code, f.samples, f.values["line"]) for f in findings] == [
        ("unknown-widget", samples, unknown),
        ("noscript", samples, line),
    ]


def test_sample_checks_available_history_beside_forward_thread_references(
    page_dir,
):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "aabb0011", "author": "user", "text": "A question"},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "parent": "aabb0011",
            "author": "agent",
            "text": 'An answer\n\n<lf-code id="duplicate">\n<pre><code class="language-python">1</code></pre></lf-code>',
        },
    )
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            '<template id="practice" data-sample data-sample-threads="aabb0011 aabb0022">'
            '<h1 id="duplicate">Child</h1></template></main>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [(f.code, f.samples, f.values) for f in findings] == [
        ("ids-taken-by-messages", ("practice",), {"ids": ["duplicate"]})
    ]


def test_an_id_the_log_gives_an_event_is_refused_in_a_page_and_a_message(page_dir):
    """A command's ID names a widget or a message in one address space, so markup may
    not take an id the log already gives an event. An id that only looks like one, as
    a hash written as a section's id, names nothing else and passes."""
    shaped = '<section id="6d1d57ac"><h2>Shaped</h2></section>'
    (page_dir / "index.html").write_text(PAGE.replace("</main>", shaped + "</main>"))
    status, findings = check_findings(page_dir)
    assert status == 0, findings
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "6d1d57ac", "author": "user", "text": "A question"},
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [(f.code, f.values) for f in findings] == [
        ("ids-taken-by-events", {"ids": ["6d1d57ac"]})
    ]
    (page_dir / "index.html").write_text(PAGE)
    published(page_dir)
    message = command_findings(
        "thread",
        "create",
        page_dir,
        "--text",
        'See:\n\n<lf-code id="6d1d57ac">\n<pre><code>1</code></pre></lf-code>',
        "--title",
        "Agent thread",
    )
    assert [(f.code, f.values) for f in message] == [
        ("ids-taken-by-events", {"ids": ["6d1d57ac"]})
    ]


def test_check_reports_css_syntax_errors_in_every_source_the_page_writes(page_dir):
    """The page's own <style> and each inline style. Chrome drops a malformed
    declaration without a word, so the author hears of it here or not at all.
    An earlier style's EOF-terminated comment cannot hide a later style's errors.
    """
    (page_dir / "index.html").write_text(
        styled(
            '.page { color: "unterminated\n; }',
            '<p style="color red">Independent stylesheets are checked.</p>',
        ).replace("<style>", "<style>/*</style>\n<style>", 1)
    )

    status, findings = check_findings(page_dir)

    assert status == 1
    assert [f.values["sheet"] for f in found(findings, "css-syntax")] == [
        "page <style> (line 6)",
        "<p style> (line 11)",
    ]


def test_a_url_of_two_values_is_advice_beside_the_sheets_drops(page_dir):
    """A browser drops a declaration whose url() holds more than one value, as a URL
    modifier or a second string, so the check says so beside the sheet, and delivery
    carries the sheet as written."""
    (page_dir / "index.html").write_text(
        styled('.page { background-image: url("x.png" crossorigin(anonymous)); }')
    )

    status, findings = check_findings(page_dir)

    assert status == 0, findings
    [advice] = found(findings, "css-url")
    assert advice.severity == "advice"
    assert advice.values["sheet"].startswith("page <style>")


@pytest.mark.parametrize("style", ["color: red; } }", "& { color: red; }"])
@pytest.mark.parametrize(
    "holder",
    [
        "{}",
        "<template>{}</template>",
        '<div><template shadowrootmode="open">{}</template></div>',
    ],
    ids=["document", "template", "shadow-root"],
)
@pytest.mark.parametrize("door", ["page", "message"])
def test_what_delivery_cannot_read_is_refused_at_each_door(
    page_dir, style, holder, door
):
    """What a sheet must not hold is what delivery's reader can't read, so each door
    asks that reader of every sheet delivery rewrites, a template's and a shadow
    root's included, and refuses with its words. A nested rule in a style attribute
    parses as a block's contents but not as the declaration list delivery reads,
    and unasked would pass every check only for delivery to refuse it."""
    from leaf.serving.revision_delivery import DeliveryAddress, rebase_document
    from leaf.source.capture_refusals import ArtifactError

    markup = holder.format(f'<p style="{style}">Shown</p>')
    source = styled("", markup)
    if door == "page":
        (page_dir / "index.html").write_text(source)
        _, findings = check_findings(page_dir)
    else:
        published(page_dir)
        findings = command_findings(
            "thread",
            "create",
            page_dir,
            "--text",
            f"Look:\n\n{markup}",
            "--title",
            "Agent thread",
        )
    [refused] = findings if door == "message" else found(findings, "css-syntax")
    assert refused.code == "css-syntax"
    assert refused.values["sheet"].startswith("<p style>")
    with pytest.raises(ArtifactError) as delivered:
        rebase_document(source, DeliveryAddress("/root", "/revision"))
    assert [f.values["message"] for f in delivered.value.findings] == [
        refused.values["message"]
    ]


@pytest.mark.parametrize("door", ["page", "page-sample", "message-sample"])
def test_a_sheet_delivery_refuses_reports_nothing_dropped(page_dir, door):
    """A sheet delivery's reader refuses has its syntax error and nothing more: a
    reparse past that error would report the rules it misreads as dropped."""
    sheet = "<style>p { ] }</style>"
    sample = f'<template id="practice" data-sample>{sheet}<h1>Child</h1></template>'
    if door == "message-sample":
        published(page_dir)
        findings = command_findings(
            "thread",
            "create",
            page_dir,
            "--text",
            f"Try:\n\n{sample}",
            "--title",
            "Agent thread",
        )
    else:
        (page_dir / "index.html").write_text(
            styled("", sample) if door == "page-sample" else styled("p { ] }")
        )
        _, findings = check_findings(page_dir)
    assert [
        (f.code, f.values["message"]) for f in findings if f.severity == "error"
    ] == [("css-syntax", "Unmatched ]")]


def test_a_message_takes_the_advice_its_markup_draws_on_a_page(page_dir):
    """The advice that reads only markup reaches a message's HTML as it reaches a
    page's source: a code block naming a language Leaf doesn't colour posts, and its
    command says so beside it."""
    published(page_dir)
    noted = command_notes(
        "thread",
        "create",
        page_dir,
        "--text",
        'Run:\n\n<pre><code class="language-nope">go</code></pre>',
        "--title",
        "Agent thread",
    )
    assert [(f.code, f.values["language"]) for f in noted] == [
        ("uncoloured-language", "nope")
    ]


def test_a_dropped_declaration_is_advice(page_dir):
    """A declaration a browser drops is one delivery's reader reads whole, so it
    refuses nothing of Leaf's: the check reports it beside a passing result, and a
    message carrying it is admitted with the same advice beside the command's result
    (`styles.dropped_css`)."""
    (page_dir / "index.html").write_text(styled("p { color: red; broken; }"))
    status, findings = check_findings(page_dir)
    [dropped] = found(findings, "css-dropped")
    assert (status, dropped.severity) == (0, "advice")
    published_markup = (
        '<template id="practice" data-sample><style>p { broken; }</style>'
        "<h1>Child</h1></template>"
    )
    (page_dir / "index.html").write_text(PAGE)
    published(page_dir)
    noted = command_notes(
        "thread",
        "create",
        page_dir,
        "--text",
        f"Try:\n\n{published_markup}",
        "--title",
        "Agent thread",
    )
    assert [(f.code, f.severity) for f in noted] == [("css-dropped", "advice")]


def test_a_sampled_thread_starts_as_its_source_log_leaves_it():
    """A child page sampling a thread holds one revision, its parent's document, so
    what a later version of the parent retracted stays behind rather than staying in force
    again on that one revision: an answer the parent no longer counts leaves the
    child's copy of its thread open too, and the action it had superseded, which the
    version took back with it, stays behind as well."""
    from leaf.log.events import build_threads
    from leaf.log.thread_context import sample_events
    from leaf.source.passages import enclosing_ids

    document = structure_model.SourceDocument(
        '<main><lf-suggestion id="sug-a" resolves="c1">'
        '<p id="sug-note">Refill when half-empty.</p></lf-suggestion></main>'
    )
    within = enclosing_ids(document)
    events = [
        {
            "kind": "comment",
            "id": "c1",
            "seq": 1,
            "revision": 1,
            "author": "user",
            "ts": "t",
            "text": "Refill less often?",
            "anchor": {"section": "sug-a"},
        },
        {
            "kind": "action",
            "id": "first",
            "seq": 2,
            "revision": 1,
            "author": "user",
            "ts": "t",
            "widget": "sug-a",
            "action": "decide",
            "detail": {"outcome": "defer"},
            "meaning": {"unit": "sug-a", "depends": [], "answer": None},
        },
        {
            "kind": "action",
            "id": "accept",
            "seq": 3,
            "revision": 1,
            "author": "user",
            "ts": "t",
            "widget": "sug-a",
            "action": "decide",
            "detail": {"outcome": "accept"},
            "meaning": {"unit": "sug-a", "depends": ["sug-note"], "answer": "c1"},
        },
        {
            "kind": "note",
            "id": "v2",
            "seq": 4,
            "revision": 2,
            "author": "agent",
            "ts": "t",
            "text": "Reworded the rule.",
            "restated": ["sug-note"],
        },
    ]
    assert build_threads(events, within)["c1"]["resolved"] is None
    # The version took back the accept and the deferral it replaced, so the child
    # starts with neither.
    copied = sample_events(document, events, {"c1"})
    assert [event["id"] for event in copied] == ["c1"]
    assert build_threads(copied, within)["c1"]["resolved"] is None


SAMPLE_FIXTURE_REFUSALS = [
    (
        "[]",
        'type="application/json"',
        'data-sample-events="missing"',
        "sample-script",
        {"reference": "missing"},
    ),
    (
        "[]",
        'type="text/plain"',
        'data-sample-events="fixture"',
        "sample-script-type",
        {},
    ),
    (
        "[]",
        'type="application/json" src="/page/history.json"',
        'data-sample-events="fixture"',
        "sample-script-type",
        {},
    ),
    (
        '[{"kind":"comment","text":NaN}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "sample-json",
        {"error": "NaN is not a JSON number"},
    ),
    (
        "{",
        'type="application/json"',
        'data-sample-events="fixture"',
        "sample-json",
        {},
    ),
    (
        "{}",
        'type="application/json"',
        'data-sample-events="fixture"',
        "sample-array",
        {},
    ),
    (
        "[1]",
        'type="application/json"',
        'data-sample-events="fixture"',
        "sample-array",
        {},
    ),
    (
        '[{"kind": []}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-event",
        {"event": 1},
    ),
    (
        '[{"kind":"reply","parent":"absent","text":"Reply"}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-event",
        {"event": 1},
    ),
    (
        '[{"kind":"comment","id":"aabb0011","text":"One"},{"kind":"comment","id":"aabb0011","text":"Two"}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-id-repeated",
        {"event": 2, "id": "aabb0011"},
    ),
    (
        '[{"kind":"comment","id":"child","text":"Collision"}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-id-taken",
        {"event": 1, "id": "child"},
    ),
    (
        '[{"kind":"action","widget":"absent","action":"choose","detail":{"value":[]}}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-event",
        {"event": 1},
    ),
    (
        '[{"kind":"action"}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-event",
        {"event": 1},
    ),
    (
        '[{"kind":"comment","text":"Bad clock","ts":"yesterday"}]',
        'type="application/json"',
        'data-sample-events="fixture"',
        "fixture-ts",
        {"event": 1},
    ),
    (
        "[]",
        'type="application/json"',
        'data-sample-events="fixture" data-sample-threads="aabb0011"',
        "sample-source-both",
        {},
    ),
]


# `documents.initial_sample_events` reads a fixture for either door, so the
# message door takes the one case a holder's own script and a child's ids both reach.
@pytest.mark.parametrize(
    ("history", "script_attrs", "template_attrs", "code", "values", "holder"),
    [
        *((*case, "page") for case in SAMPLE_FIXTURE_REFUSALS),
        (
            *next(
                case
                for case in SAMPLE_FIXTURE_REFUSALS
                if case[3] == "fixture-id-taken"
            ),
            "message",
        ),
    ],
)
def test_sample_fixture_refusals_reach_page_check(
    page_dir, history, script_attrs, template_attrs, code, values, holder
):
    source = (
        f'<script id="fixture" {script_attrs}>{history}</script>'
        f'<template id="practice" data-sample {template_attrs}>'
        '<h1 id="child">Child</h1></template>'
    )
    findings = sample_holder_findings(page_dir, holder, source)
    [refused] = found(findings, code, **values)
    assert refused.samples == ("practice",)


@pytest.mark.parametrize(
    ("markup", "code"),
    [
        ('<lf-unknown id="widget">Unknown</lf-unknown>', "unknown-widget"),
        (
            '<lf-code id="child">\n<pre><code class="language-python">1</code></pre></lf-code>',
            "ids-taken",
        ),
        (
            '<lf-code id="code">\n<pre><code class="language-python">1</code></pre></lf-code>\n<style>p {color:red}</style>',
            "message-style",
        ),
    ],
)
def test_sample_fixture_message_markup_uses_the_message_gate(page_dir, markup, code):
    history = json.dumps(
        [
            {
                "kind": "comment",
                "author": "agent",
                "text": f"Example\n\n{markup}",
            }
        ]
    )
    source = (
        f'<script id="fixture" type="application/json">{history}</script>'
        '<template id="practice" data-sample data-sample-events="fixture">'
        '<h1 id="child">Child</h1></template>'
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", source + "</main>"))
    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(findings, "fixture-markup", kind="comment", event=1)
    assert refused.samples == ("practice",)
    assert found(
        [Finding.loads(nested) for nested in refused.values["findings"]], code
    ), refused


def test_a_fixture_anchor_keeps_the_context_it_gives(page_dir):
    """A side a fixture gives picks its own copy of the words, here the first, which
    the files read with a space inside it, so the anchor keeps only the sides the
    fixture gave, with no note, rather than borrowing the other side from the one copy
    the files hold."""
    from leaf.records.authored_checks.documents import initial_sample_events
    from leaf.source.vocabulary import read_page_registry

    anchor = {"section": "child-p", "quote": "preflight", "prefix": "First"}
    history = json.dumps(
        [{"kind": "comment", "author": "user", "text": "x", "anchor": anchor}]
    )
    source = (
        f'<script id="fixture" type="application/json">{history}</script>'
        '<template id="practice" data-sample data-sample-events="fixture">'
        '<div id="child-p">First <b>pre</b><em>flight</em> alpha. Later preflight beta.'
        "</div></template>"
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", source + "</main>"))
    published(page_dir)
    holder = structure_model.SourceDocument((page_dir / "index.html").read_text())
    [template] = holder.samples
    events, notes = initial_sample_events(
        page_dir,
        holder,
        [],
        holder,
        template,
        read_page_registry(page_dir).registry,
        {},
    )
    [comment] = [event for event in events if event["kind"] == "comment"]
    assert (comment["anchor"], notes) == (anchor, [])
