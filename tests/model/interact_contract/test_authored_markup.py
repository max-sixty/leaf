"""What `page check` refuses in authored markup, and how sample documents are read,
checked and seeded with their source thread's history."""

import json

import pytest
from interact_support import (
    PAGE,
    append_carried_log_record,
    check,
    check_findings,
    command_findings,
    found,
    published,
    styled,
)

from leaf import passages as passages_model
from leaf import structure as structure_model
from leaf.findings import Finding


def test_check_refuses_the_runtimes_own_markers_in_authored_markup(page_dir):
    """The runtime writes data-lf-* attributes and lf- classes as its own record
    and reads them back: authored words inside .lf-chrome leave every reading,
    .lf-quiet clips them to a point nobody can see or select, and an authored
    data-lf-gen makes cells the file-side reading has no fence for.

    Both namespaces are reserved by prefix, so the fourth element here wears a
    class the runtime does not coin today and is refused all the same. A list of
    the names it happens to write is a list that admits the next one it coins:
    .lf-quiet was outside the list this once held, and the chrome stylesheet
    clipped an authored copy of it to 1x1 with both render gates skipping the
    class unconditionally, so nothing anywhere said the page's own words had
    gone. The <p class="note"> is the control: an ordinary class is the author's
    to write, and the count below is exact so a reservation that swallowed it
    would be caught here rather than in a page that stopped rendering."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><div class="lf-chrome"><p id="w">words</p></div>'
            '<p id="q" class="lf-quiet">said out of sight</p>'
            '<p id="n" class="lf-not-coined-yet">a name the runtime has not taken</p>'
            '<p id="k" class="note">an ordinary class the author owns</p>'
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
        ("<p>", ["data-lf-gen"]),
    ]


def test_check_requires_the_vendored_layer(tmp_path):
    d = tmp_path / "bare"
    d.mkdir(parents=True)
    (d / "index.html").write_text(PAGE)
    result = check(d)
    assert result.exit_code == 1
    assert f"run `leaf page init {d}`" in result.output


def test_check_rejects_an_invalid_bound_and_loose_pane_text(page_dir):
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
    assert found(findings, "pane-body", "<lf-pane>", body=["#text", "p"])


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


def test_check_takes_a_stated_height_in_whole_css_pixels(page_dir):
    """`data-height` states the box of a widget that draws into one, in whole CSS
    pixels."""
    chart = '<lf-chart id="c" data-height="{}"><pre>{{ariaLabel: "x", marks: []}}</pre></lf-chart>'
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + chart.format(240))
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + chart.format("240px"))
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings, "allocation-value", attr="data-height", value="240px", allowed=None
    )


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
        '<template id="practice" data-sample><lf-ask id="nested-ask">'
        '<h2>Hidden question</h2><lf-options id="nested-options" choose>'
        '<lf-option id="nested-choice">Hidden answer</lf-option>'
        "</lf-options></lf-ask></template></main>"
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
    registry = {"lf-parts": {"x-views": "parts"}, "lf-tabs": {"x-views": True}}
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


@pytest.mark.parametrize(
    ("markup", "code", "samples"),
    [
        ("<noscript>invisible</noscript>", "noscript", ("practice",)),
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
            '<template id="nested" data-sample><noscript>hidden</noscript></template>',
            "noscript",
            ("practice", "nested"),
        ),
    ],
)
@pytest.mark.parametrize("holder", ["page", "message"])
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
            "Try:",
            "--markup",
            sample,
        )
    else:
        history = [
            {"kind": "comment", "id": "aabb0011", "author": "agent", "text": "Open"},
            {"kind": "reply", "parent": "aabb0011", "text": "Try:", "markup": sample},
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
        "thread", "create", str(page_dir), "--text", "Try it:", "--markup", source
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
        ("noscript", samples, line),
        ("unknown-widget", samples, unknown),
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
            "text": "An answer",
            "markup": '<lf-code id="duplicate" language="python"><pre>1</pre></lf-code>',
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
    and once passed every check only for delivery to refuse it with no reason."""
    from leaf.revision_artifact import ArtifactError
    from leaf.revision_delivery import DeliveryAddress, rebase_document

    markup = holder.format(f'<p style="{style}">Shown</p>')
    source = styled("", markup)
    if door == "page":
        (page_dir / "index.html").write_text(source)
        _, findings = check_findings(page_dir)
    else:
        published(page_dir)
        findings = command_findings(
            "thread", "create", page_dir, "--text", "Look:", "--markup", markup
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
            "thread", "create", page_dir, "--text", "Try:", "--markup", sample
        )
    else:
        (page_dir / "index.html").write_text(
            styled("", sample) if door == "page-sample" else styled("p { ] }")
        )
        _, findings = check_findings(page_dir)
    assert [
        (f.code, f.values["message"]) for f in findings if f.severity == "error"
    ] == [("css-syntax", "Unmatched ]")]


@pytest.mark.parametrize("severity", ["error", "advice"])
def test_a_dropped_declaration_takes_its_severity_from_one_place(
    page_dir, monkeypatch, severity
):
    """A declaration a browser drops is one the reader delivers, so whether it
    refuses the page is a choice, made in `styles.DROPPED_SEVERITY` alone: at
    advice it is reported beside a passing check and a message carrying it is
    admitted."""
    from leaf import styles

    monkeypatch.setattr(styles, "DROPPED_SEVERITY", severity)
    (page_dir / "index.html").write_text(styled("p { color: red; broken; }"))
    status, findings = check_findings(page_dir)
    [dropped] = found(findings, "css-dropped")
    assert (status, dropped.severity) == (int(severity == "error"), severity)
    published_markup = (
        '<template id="practice" data-sample><style>p { broken; }</style>'
        "<h1>Child</h1></template>"
    )
    (page_dir / "index.html").write_text(PAGE)
    published(page_dir)
    refused = command_findings(
        "thread", "create", page_dir, "--text", "Try:", "--markup", published_markup
    )
    assert [f.code for f in refused] == (["css-dropped"] if severity == "error" else [])


def test_a_sampled_thread_starts_as_its_source_log_leaves_it():
    """A child page sampling a thread holds one revision, its parent's document, so
    what a later version of the parent retracted stays behind rather than staying in force
    again on that one revision: an answer the parent no longer counts leaves the
    child's copy of its thread open too, and the action it had superseded, which
    answered nothing, decides the widget there as it does in the parent."""
    from leaf.events import build_threads
    from leaf.passages import enclosing_ids
    from leaf.thread_context import sample_events

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
    copied = sample_events(document, events, {"c1"})
    assert [event["id"] for event in copied] == ["c1", "first"]
    assert build_threads(copied, within)["c1"]["resolved"] is None


@pytest.mark.parametrize(
    ("history", "script_attrs", "template_attrs", "code", "values"),
    [
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
            "fixture-kind",
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
    ],
)
@pytest.mark.parametrize("holder", ["page", "message"])
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
            '<lf-code id="child" language="python"><pre>1</pre></lf-code>',
            "ids-taken",
        ),
        (
            '<lf-code id="code" language="python"><pre>1</pre></lf-code><style>p {color:red}</style>',
            "message-style",
        ),
    ],
)
def test_sample_fixture_message_markup_uses_the_message_gate(page_dir, markup, code):
    history = json.dumps(
        [{"kind": "comment", "author": "agent", "text": "Example", "markup": markup}]
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
