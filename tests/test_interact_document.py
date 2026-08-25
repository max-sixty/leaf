"""Static document, version, and page-state tests."""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    OPTIONS,
    PAGE,
    PHRASING_CONTENT,
    SUGGESTION,
    X,
    Y,
    _balanced,
    _board,
    _decided,
    _marker_for,
    _report,
    _status,
    _tasks_version,
    check,
    decide,
    interact,
    publish,
    state_json,
    suggest,
)


def test_check_accepts_a_valid_page(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_check_requires_the_layers_one_csp(page_dir):
    """The vendoring promise — an approved page can't change under its user and
    can't phone home — is enforced by the browser only if the page declares the
    layer's CSP, so the gate requires it the way it requires the one script."""
    version = page_dir / "versions" / "v1.html"
    stripped = re.sub(
        r'<meta http-equiv="Content-Security-Policy"[^>]*>\n', "", version.read_text()
    )
    version.write_text(stripped)
    result = check(page_dir)
    assert result.exit_code == 1
    assert "the layer's one CSP" in result.output


def test_check_refuses_markup_the_browser_never_renders(page_dir):
    """<template> parses into an inert fragment and <noscript> stays unrendered
    in any scripting browser, while the file's reading would take both for the
    page's words — a comment could anchor on text no reader ever sees."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><template><p id="tp">Ghost words.</p></template>'
            "<noscript>Fallback words.</noscript>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert result.output.count("the browser renders none of its content") == 2


def test_check_rejects_widget_violations(page_dir):
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            '<a href="https://example.test/jobs/backfill.py#L88"><code>jobs/backfill.py:88</code></a>',
            '<lf-metric id="bad-metric" value="1"/>'
            "<figure/>"
            "<lf-bogus></lf-bogus>"
            '<lf-timeline id="bad-timeline">'
            '<lf-event id="stray-event" kind="medium">S</lf-event></lf-timeline>'
            '<lf-option id="stray"><strong>S</strong></lf-option>'
            '<lf-diagram id="Bad_ID"><pre>graph LR</pre><em>x</em></lf-diagram>'
            '<lf-diagram id="bare-body">graph LR</lf-diagram>',
        ).replace('<lf-option id="flag-first"', "<lf-option")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    out = result.output
    # Both the widget and the plain <figure/>: the slash misleads a browser on
    # any non-void tag, not only on the vocabulary's.
    assert out.count("self-closing") == 2
    assert "unknown widget" in out
    assert "'medium' is not one of" in out
    assert "must be a direct child of <lf-options>" in out
    assert "'id' is a required property" in out
    assert "does not match" in out  # id pattern
    # A stray element beside the <pre>, and a body that never opened one: both are
    # the same rule, since the <pre> is what carries the whitespace the notation needs.
    assert out.count("its body is one <pre> holding the text") == 2
    assert "text outside its <pre>" in out


def test_check_rejects_duplicate_attributes_the_browser_reads_differently(page_dir):
    """A file reading cannot silently choose another id than the live DOM.

    HTML keeps the first duplicate attribute, while HTMLParser reports both and
    ``dict(attrs)`` keeps the last. Accepting this would let the action gate map
    a stateful widget under an id its browser can never send.
    """
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"].replace(
        'id="feeder-board"', 'id="browser-board" id="file-board"'
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "duplicate attribute" in result.output


def test_check_rejects_a_language_nothing_will_color(page_dir):
    """A declared language the runtime won't honor renders as a plain block, which is
    exactly what a block with no language renders as — so the user sees nothing
    wrong and the author never finds out. Every way of getting it wrong is the lint's,
    because the author is the only one who can still fix any of them: the class somewhere
    other than <pre><code>, an unknown word on the class, and an unknown word on a
    widget attribute that declares itself a language (x-language). The last is checked
    against the same list as the first two rather than by that widget's own schema,
    which is what keeps a second tag taking a language from needing a second reader."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>\n"
            '<pre><code class="language-pythn">x = 1</code></pre>\n'
            '<div class="note language-python">not a code block</div>\n'
            '<lf-code id="walk-bad" language="pythn"><pre>z = 3\n</pre></lf-code>\n'
            '<pre><code class="language-python">y = 2</code></pre>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    out = result.output
    assert (
        'class="language-pythn"' in out
        and "not a language this page's layer speaks" in out
    )
    assert 'class="language-python"' in out and "only <pre><code> is colored" in out
    assert '<lf-code language="pythn">' in out, out
    # The well-formed block is not among the complaints.
    assert out.count('class="language-python"') == 1


def test_a_widget_that_declares_a_language_is_checked_by_that_alone(page_dir):
    """The list is the layer's fact, not one widget's, so nothing in the lint knows
    which widget takes a language: a tag whose entry declares x-language is held to
    $languages on the strength of the declaration. A thirteenth widget that colors
    something — a terminal transcript, a diff — is covered without the lint moving."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-tree"]["properties"]["dialect"] = {"type": "string"}
    registry["lf-tree"]["x-language"] = "dialect"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<lf-tree id="t" dialect="lisp"><pre>\nfeeders/\n</pre></lf-tree>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<lf-tree dialect="lisp">' in result.output
    assert "not a language this page's layer speaks" in result.output


def test_a_misplaced_class_is_offered_whatever_tag_takes_a_language(page_dir):
    """The other way to color a block is read from the layer, not written into the
    lint: the tags whose entries declare an attribute for a language (x-language) are
    the ones the misplaced class is offered, under the attribute each declares. The
    widget that colors a walkthrough is the layer's rather than core's, so a lint that
    named it would be core knowing a content widget — and would keep offering it to a
    layer that dropped it, spelt its attribute differently, or added a second."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<div class="note language-python">not a code block</div>',
        )
    )
    registry_file = page_dir / "registry.json"
    registry = json.loads(registry_file.read_text())
    declaring = {
        tag: entry["x-language"]
        for tag, entry in registry.items()
        if tag.startswith("lf-") and "x-language" in entry
    }
    assert declaring, "the shipped layer declares one; the offer below is its reading"
    out = check(page_dir).output
    for tag, attr in declaring.items():
        assert f"<{tag} {attr}=…>" in out, out

    # A second tag taking one joins the offer under the attribute it declares.
    registry["lf-tree"]["properties"]["dialect"] = {"type": "string"}
    registry["lf-tree"]["x-language"] = "dialect"
    registry_file.write_text(json.dumps(registry))
    out = check(page_dir).output
    assert "<lf-tree dialect=…>" in out, out

    # A layer whose tags declare none has nothing to offer, and the placement rule —
    # which never rested on any widget — is stated on its own.
    for tag in [*declaring, "lf-tree"]:
        registry[tag].pop("x-language")
    registry_file.write_text(json.dumps(registry))
    out = check(page_dir).output
    assert "only <pre><code> is colored" in out and "— move it" in out, out
    assert "or use" not in out, out


def test_the_block_content_lists_are_the_platform_set_and_the_inline_marker():
    """Two selectors in the theme decide what counts as block content — the
    suggestion slots' blockization and lf-compare's stacked-variant trigger
    (lf-options stacks on the title alone, so it asks no block question) — by the
    platform's closed set inverted: any child that is not phrasing content is block.
    The enumeration this replaced named every bundled widget, which is the closed
    list the norms forbid: the first project-layer widget staged in a slot rendered
    inline and the fold dropped it in the frame of the press.

    So each list is held to what it claims to be, in both of its halves. The platform
    half is HTML's phrasing content entire, stated above, which is the half the two
    copies could never check: agreeing with each other says nothing about a name
    dropped from both, and a missing one blockizes a slot holding the element it
    names. The widget half is the inversion's one wrong answer — an inline widget is
    a custom element like any other — and it is a marker rather than tag names,
    because which widgets those are is the registry's to say (x-inline) and a
    stylesheet cannot read it. Four names stood here, one of them a bundled chip's
    inside the integrated theme, and no layer could join them; the runtime paints the
    declaration instead and an inline widget joins by declaring it.

    The marker is held to what markDeclared paints for x-inline, because a selector
    naming an attribute nothing writes matches nothing and says so nowhere — it reads
    as the ordinary case of a page with no inline widget in a slot. Being a name the
    runtime is allowed to paint is not that: the wiring is a declaration's entry in
    one of markDeclared's tables, and _marker_for is what follows it. And it is held
    to :where(), which is what keeps an answer about content
    from becoming a claim on the cascade: :not() takes the specificity of the most
    specific thing in it, so a bare attribute selector lifts the whole rule a column
    above the type names beside it, over the marks the layer paints on top of the
    result. Bare, it beat [data-lf-retired] and a decided suggestion kept the slot
    it had just retired."""
    theme = interact.layered_theme([interact.ASSETS, interact.BUNDLED])
    lists = [_balanced(theme, found.end()) for found in re.finditer(r":not\(", theme)]
    lists = [found for found in lists if found.startswith("a, abbr")]
    assert len(lists) == 2, (
        "expected the suggestion-slot list and lf-compare's stacked-variant trigger"
    )
    registry = interact.incoming_registry([interact.ASSETS, interact.BUNDLED])
    assert [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and entry.get("x-inline")
    ], "no widget declares x-inline, so the marker in these lists stands for nothing"
    for found in lists:
        tags = {t.strip() for t in found.split(",")}
        markers = {t for t in tags if not t.isalpha()}
        assert tags - markers == PHRASING_CONTENT, (
            "the platform half of a block-content list is not HTML's phrasing "
            "content: a name dropped from it stacks a slot holding that element, "
            "one added to it leaves a block child laid out inline, and a widget "
            "named in either half re-closes the inversion"
        )
        assert markers == {":where([data-lf-inline])"}, (
            "the widget half of a block-content list is the inline marker the "
            "runtime paints from x-inline, in :where() so the question does not "
            "outrank the marks painted over its answer"
        )
        for marker in markers:
            attribute = marker[len(":where([") : -len("])")]
            assert _marker_for("x-inline") == attribute, (
                f"{marker} is not what the runtime paints for x-inline, so the "
                "list's widget half matches nothing on any page"
            )


def test_the_collapse_class_is_one_set_on_both_sides():
    """COLLAPSE_CHARS (the file side) and leaf.js's COLLAPSE regex (the browser
    side) are two spellings of one set, and everything quote-shaped rests on their
    agreement: a character one side collapses and the other keeps is a quote
    captured in the browser that the file's reading can never confirm. The next
    edit to either spelling meets this test, not a detached comment."""
    js = (interact.ASSETS / "leaf.js").read_text()
    found = re.search(r"const COLLAPSE =\n\s*/\[(.*?)\]\+/g;", js)
    assert found, "leaf.js lost its COLLAPSE regex"
    js_class = re.compile(f"[{found.group(1)}]")
    js_set = {chr(c) for c in range(0x10000) if js_class.match(chr(c))}
    assert js_set == interact.COLLAPSE_CHARS


def test_the_exhibit_exclusions_ask_for_the_marker_and_not_a_tag():
    """A choose group's affordance rules stand down inside an exhibit in their own
    selectors, because a stylesheet cannot read the registry the runtime's quoted()
    dispatches on. What they exclude is the paint that declaration leaves on the
    page (data-lf-exhibit, markDeclared) rather than the widgets declaring it, so
    the layer that ships an exhibit and the layer whose rules withhold the hand need
    not be the same one — the shape a tag list cannot have.

    Every ancestor exclusion in the rules of the composed theme is read, not the
    exhibit ones alone: a tag name in one is a closed vocabulary wherever it appears,
    and the failure it causes is a project's own widget silently outside the answer.
    Comments come off first, because two of them quote this very selector — left in,
    the set could be satisfied with every rule that carries the exclusion deleted.

    The marker is then held to what `markDeclared` actually paints for x-exhibit and
    to a widget declaring it: either missing leaves every one of those rules excluding
    nothing on any page, which renders as a quoted group offering the pick it exists
    to withhold. Not the pick itself, which quoted() refuses at the layer's own door:
    what is lost is that a mention stops looking like a mention. Which of
    markDeclared's two tables the declaration sits in is a different question — where
    the fact holds — and the browser answers it, in a reply as well as in the
    document.

    What this cannot see is one rule of ten dropping its exclusion while the others
    keep theirs: a set does not count. That reading is the browser's."""
    theme = re.sub(
        r"/\*.*?\*/",
        "",
        interact.layered_theme([interact.ASSETS, interact.BUNDLED]),
        flags=re.DOTALL,
    )
    excluded = {
        inside.removesuffix(" *")
        for found in re.finditer(r":not\(", theme)
        if (inside := _balanced(theme, found.end())).endswith(" *")
    }
    assert excluded == {":where([data-lf-exhibit])"}, (
        f"the theme's ancestor exclusions are {excluded}, and the one thing a rule "
        "may ask to stand down inside is the painted exhibit marker. A tag spelled "
        "here answers for the layer that ships it and for no other; a second marker "
        "is a second question, and belongs to whichever test owns that one; an empty "
        "set is rules that stopped standing down inside an exhibit at all"
    )
    assert _marker_for("x-exhibit") == "data-lf-exhibit", (
        "the theme excludes data-lf-exhibit and markDeclared paints "
        f"{_marker_for('x-exhibit')!r} for x-exhibit, so nothing puts that mark on a "
        "page and an exhibit keeps every affordance these rules meant to withhold"
    )
    registry = interact.incoming_registry([interact.ASSETS, interact.BUNDLED])
    assert [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and entry.get("x-exhibit")
    ], "no widget declares x-exhibit, so the marker in these rules stands for nothing"


def test_every_declared_attribute_and_enum_stands_in_an_example():
    """The corpus floor one level down from tags (examples/CLAUDE.md): where an
    attribute or an enum value changes what a reader sees, a page shows it. The
    batch that raised the corpus to this line surfaced five real defects on the
    day it landed, so the floor ratchets: the next declared attribute joins the
    corpus by being declared. The exemptions are the log-only names the doc
    enumerates — restated, overruled and resolves each name something the log
    holds, which a one-version corpus cannot earn."""
    registry = interact.incoming_registry([interact.ASSETS, interact.BUNDLED])
    used = {}
    for path in (Path(__file__).parent.parent / "examples").glob("*.html"):
        for rec in interact.parse_structure(path.read_text()).lf_elements:
            for attr, value in rec["attrs"].items():
                used.setdefault(rec["tag"], {}).setdefault(attr, set()).add(value)
    missing = []
    for tag, entry in sorted(registry.items()):
        if not tag.startswith("lf-"):
            continue
        for attr, spec in entry.get("properties", {}).items():
            if attr in {"restated", "overruled", "resolves"}:
                continue
            seen = used.get(tag, {}).get(attr)
            if seen is None:
                missing.append(f"{tag}[{attr}]")
            else:
                missing.extend(
                    f'{tag}[{attr}="{value}"]'
                    for value in spec.get("enum", [])
                    if value not in seen
                )
    assert missing == [], missing


def test_a_tone_the_layer_cannot_paint_is_refused_where_the_author_can_still_fix_it(
    page_dir,
):
    """The same failure a misspelt language has, and caught for the same reason: a
    tone nothing matches paints nothing, so the chip renders neutral on a page that
    otherwise looks perfectly well. The user cannot see it — they never knew it
    was meant to be red — so the only party who can still fix it is whoever wrote
    the word, and the lint is where they are told. This is the whole difference
    between the attribute and a class, which nothing checks."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            '<lf-option id="flag-first">',
            '<lf-option id="flag-first"><lf-chip tone="dangre">risk: high</lf-chip>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "not a tone this page's layer paints" in result.output
    assert "'ok', 'warn', 'danger'" in result.output.replace('"', "'")

    # The list is the layer's, so a layer that adds one accepts it with no widget
    # touched — which is the point of $tones over an enum on lf-chip.
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$tones"]["names"].append("dangre")
    (page_dir / "registry.json").write_text(json.dumps(registry))
    assert check(page_dir).exit_code == 0


def test_a_chip_is_admissible_in_both_its_holders(page_dir):
    """x-parent is a list because one element can belong to two holders, and a chip
    is written in a lf-option and in a lf-variant — the same shape either side of the
    decision. Neither is special-cased anywhere: the nesting check reads the list."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<lf-compare id="cmp"><lf-variant id="v-a"><lf-chip tone="ok">cheap</lf-chip>'
            "<strong>A</strong> One.</lf-variant></lf-compare>\n  <lf-options>",
        )
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output

    # And refused where neither holder is its parent, naming both.
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2><lf-chip>stray</lf-chip>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "must be a direct child of <lf-option> or <lf-variant>" in result.output


def test_a_layer_naming_no_languages_refuses_every_word_rather_than_none(page_dir):
    """A layer that names none colors none, so a page declaring one is asking for
    something it cannot get. The list is therefore read and indexed, never tested for
    emptiness: an empty list that stood the check down would be a check retiring itself
    the moment its list moved — and this is the check whose failures the user can't
    see either way, so silence is the one outcome it must not have."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$languages"]["names"] = []
    registry["$languages"]["paths"] = {}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<pre><code class="language-python">x = 1</code></pre>\n'
            '<div class="note language-python">not a code block</div>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "not a language this page's layer speaks" in result.output
    # The placement rule never rested on the list, so it reports here too.
    assert "only <pre><code> is colored" in result.output


def test_check_rejects_loose_content_in_items_container(page_dir):
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", "<lf-options>\nloose text\n<p>stray</p>\n<br/>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "admits only ['lf-option'] children" in result.output
    assert "'br'" in result.output  # self-closed strays count as children too
    assert "loose text" in result.output


def test_flag_attribute_accepts_both_html_spellings(page_dir):
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(" recommended>", ' recommended="">')
    )
    assert check(page_dir).exit_code == 0
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(" recommended>", ' recommended="yes">')
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "is not of type 'boolean'" in result.output


def test_milestones_compose(page_dir):
    nested = """<lf-milestones>
    <lf-milestone id="m-one" status="done" when="week 1"><strong>Survey</strong> Sites.</lf-milestone>
    <lf-milestone id="m-two" status="active" tags="wood,solar"><strong>Build</strong></lf-milestone>
  </lf-milestones>
<lf-options>"""
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<lf-options>", nested))
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<lf-milestone id="m-stray" status="done"><strong>X</strong></lf-milestone><lf-options>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "must be a direct child of <lf-milestones>" in result.output


def test_tabs_validate_and_compose(page_dir):
    tabs = """<lf-tabs id="ws">
  <lf-tab id="ws-ingest" label="Ingest"><p>Pipeline notes.</p></lf-tab>
  <lf-tab id="ws-search" label="Search">
    <lf-metrics><lf-metric id="k-lat" value="118 ms"></lf-metric></lf-metrics>
  </lf-tab>
</lf-tabs>
<lf-options>"""
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<lf-options>", tabs))
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_tabs_reject_structural_violations(page_dir):
    # A label-less panel, a stray panel outside lf-tabs, and loose text between
    # panels are each refused.
    bad = """<lf-tabs id="ws">
  loose text
  <lf-tab id="ws-a"><p>x</p></lf-tab>
</lf-tabs>
<lf-tab id="ws-stray" label="Stray"><p>y</p></lf-tab>
<lf-options>"""
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<lf-options>", bad))
    result = check(page_dir)
    assert result.exit_code == 1
    assert "'label' is a required property" in result.output
    assert "must be a direct child of <lf-tabs>" in result.output
    assert "loose text" in result.output


def test_suggestion_validates(page_dir):
    suggest(page_dir)
    assert check(page_dir, version=1).exit_code == 0, check(page_dir, version=1).output


def test_suggestion_rejects_malformed_shapes(page_dir):
    for markup, expected in [
        ('<lf-suggestion id="sug-a"></lf-suggestion><lf-options>', "needs a <lf-old>"),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new><p>x</p></lf-new>'
                "<lf-new><p>y</p></lf-new></lf-suggestion><lf-options>"
            ),
            "one at most",
        ),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new>'
                '<lf-suggestion id="sug-b"><lf-new>x</lf-new></lf-suggestion>'
                "</lf-new></lf-suggestion><lf-options>"
            ),
            "don't nest",
        ),
        (
            "<lf-old><p>orphan</p></lf-old><lf-options>",
            "must be a direct child of <lf-suggestion>",
        ),
        (
            (
                '<lf-suggestion id="sug-a" resolves="nosuch"><lf-new><p>x</p></lf-new>'
                "</lf-suggestion><lf-options>"
            ),
            "names no comment in the log",
        ),
    ]:
        (page_dir / "versions" / "v1.html").write_text(
            PAGE.replace("<lf-options>", markup)
        )
        result = check(page_dir, version=1)
        assert result.exit_code == 1, markup
        assert expected in result.output, f"{markup}\n{result.output}"


def test_suggestion_resolves_accepts_a_real_comment(page_dir):
    interact.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    markup = '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p>x</p></lf-new></lf-suggestion><lf-options>'
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<lf-options>", markup))
    assert check(page_dir, version=1).exit_code == 0


def test_accepting_licenses_retiring_the_replaced_markup(page_dir):
    # v2 honors the accept: the old paragraph and the wrapper are gone, the
    # proposal inlined. Nothing but a logged accept makes that legal.
    suggest(page_dir)
    honored = PAGE.replace(
        "<lf-options>",
        '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
    )
    (page_dir / "versions" / "v2.html").write_text(honored)
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "refill-rule" in result.output

    decide(page_dir, "accept")
    assert check(page_dir, version=2).exit_code == 0, check(page_dir, version=2).output


def test_a_later_decision_does_not_license_an_earlier_version(page_dir):
    """An old file is checked against what the reader could have decided then."""
    suggest(page_dir)
    publish(page_dir, 2)
    (page_dir / "versions" / "v3.html").write_text(
        PAGE.replace("<lf-options>", SUGGESTION)
    )
    publish(page_dir, 3)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 3,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )

    # Re-checking the older published file cannot borrow the future action to
    # justify dropping what its own predecessor contained.
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
        )
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "refill-rule" in result.output


def test_an_unanswered_proposal_cant_be_kept_as_settled_content(page_dir):
    # Self-accepting: the wrapper goes but its proposal stays, presented as
    # ordinary prose the user never agreed to. Withdrawal is whole or not.
    insert = """<lf-suggestion id="sug-thistle">
  <lf-new><p id="thistle-plan">Switch the north feeder to thistle in autumn.</p></lf-new>
</lf-suggestion>
<lf-options>"""
    suggest(page_dir, markup=insert)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="thistle-plan">Switch the north feeder to thistle in autumn.</p><lf-options>',
        )
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "sug-thistle" in result.output
    # A refused version never published, so it is nobody's baseline: v3 stands
    # against v1 — the page the user was actually looking at — and there a
    # whole withdrawal is fine. So is honoring a logged accept.
    (page_dir / "versions" / "v3.html").write_text(PAGE)
    assert check(page_dir, version=3).exit_code == 0
    decide(page_dir, "accept", widget="sug-thistle")
    assert check(page_dir, version=2).exit_code == 0


def test_rejecting_licenses_retiring_the_proposal(page_dir):
    # A reject is consent to drop the proposal, so it retires even while a
    # thread about it is open — the user has already answered.
    suggest(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    interact.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "cameras aren't reliable yet",
        },
    )
    assert check(page_dir, version=2).exit_code == 1
    decide(page_dir, "reject")
    assert check(page_dir, version=2).exit_code == 0
    # The other slot is not licensed: dropping the markup a reject kept is refused.
    (page_dir / "versions" / "v3.html").write_text(PAGE)
    result = check(page_dir, version=3)
    assert result.exit_code == 1
    assert "refill-rule" in result.output


def test_an_unanswered_deletion_cant_delete(page_dir):
    # The mirror of self-accepting an insertion: dropping the markup a pending
    # deletion wraps, without the accept that consents to losing it.
    delete = """<lf-suggestion id="sug-drop">
  <lf-old><p id="hand-log">The manual sightings log.</p></lf-old>
</lf-suggestion>
<lf-options>"""
    suggest(page_dir, markup=delete)
    (page_dir / "versions" / "v2.html").write_text(PAGE)
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "hand-log" in result.output
    decide(page_dir, "accept", widget="sug-drop")
    assert check(page_dir, version=2).exit_code == 0


def test_withdrawing_an_unanswered_suggestion_needs_no_consent(page_dir):
    # Nothing was decided, so Claude may take the proposal back — but not while
    # an unresolved thread is anchored in it.
    suggest(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    assert check(page_dir, version=2).exit_code == 0
    interact.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "why the camera?",
        },
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "refill-camera" in result.output
    interact.append_event(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c1"}
    )
    assert check(page_dir, version=2).exit_code == 0


def test_reply_refuses_a_suggestion(page_dir):
    interact.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    result = CliRunner().invoke(
        interact.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "Fixed:",
            "--markup",
            '<lf-suggestion id="sug-x"><lf-new><p>fixed</p></lf-new></lf-suggestion>',
        ],
    )
    assert result.exit_code != 0
    assert "frozen in the log" in result.output


def test_check_rejects_wrong_scaffold(page_dir):
    html = PAGE.replace('<script type="module" src="/leaf.js"></script>', "").replace(
        '<link rel="stylesheet" href="/theme.css">', ""
    )
    (page_dir / "versions" / "v1.html").write_text(html)
    result = check(page_dir)
    assert result.exit_code == 1
    assert "exactly one external <script src>" in result.output
    assert "exactly one stylesheet" in result.output


@pytest.mark.parametrize(
    "html",
    [
        PAGE.replace('<script type="module" src="/leaf.js"></script>', "").replace(
            "</main>",
            '</main>\n<script type="module" src="/leaf.js"></script>',
        ),
        PAGE.replace('<link rel="stylesheet" href="/theme.css">', "").replace(
            "<main>", '<main>\n<link rel="stylesheet" href="/theme.css">'
        ),
        PAGE.replace('<link rel="stylesheet" href="/theme.css">', "")
        .replace('<script type="module" src="/leaf.js"></script>', "")
        .replace(
            "</main>",
            """</main>
<head>
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>""",
        ),
    ],
    ids=["module-after-main", "stylesheet-inside-main", "assets-in-late-head"],
)
def test_check_requires_presentation_assets_in_head(page_dir, html):
    """The gate must exist before the browser can paint the body it withholds."""
    (page_dir / "versions" / "v1.html").write_text(html)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "must be in <head> before <body>" in result.output


@pytest.mark.parametrize(
    "asset, changed",
    [
        (
            '<link rel="stylesheet" href="/theme.css">',
            '<link rel="stylesheet" href="/theme.css" media="print">',
        ),
        (
            '<script type="module" src="/leaf.js"></script>',
            '<script type="module" src="/leaf.js" async></script>',
        ),
    ],
    ids=["print-only-theme", "noncanonical-module"],
)
def test_check_requires_always_applicable_canonical_assets(page_dir, asset, changed):
    """An asset whose URL is right but applicability differs is not the boundary."""
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace(asset, changed))

    result = check(page_dir)

    assert result.exit_code == 1
    assert "exactly" in result.output


def test_check_rejects_inline_importance_over_the_presentation_boundary(page_dir):
    """Inline importance outranks stylesheet layers, so the authoring door owns it."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<main>", '<main style="opacity: 1 !important">')
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "protected presentation property opacity important" in result.output


@pytest.mark.parametrize(
    "outside",
    [
        "Authored tail",
        '<p id="tail">Authored tail</p>',
        '<lf-options><lf-option id="tail">Authored tail</lf-option></lf-options>',
        '<main><p id="tail">Second main</p></main>',
    ],
)
def test_check_confines_authored_content_to_one_direct_main(page_dir, outside):
    """The element the presentation boundary withholds contains the whole page.

    Prose, ordinary elements, widgets, and another main beside the first are all
    visible outside the CSS gate and must be refused at the authoring door.
    """
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("</main>", f"</main>\n{outside}")
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_requires_main_to_be_a_direct_body_child(page_dir):
    """A main nested in an authored wrapper is not selected by `body > main`."""
    wrapped = PAGE.replace("<main>", "<div>\n<main>").replace(
        "</main>", "</main>\n</div>"
    )
    (page_dir / "versions" / "v1.html").write_text(wrapped)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


@pytest.mark.parametrize(
    "html",
    [
        PAGE.replace("</body>", '</body>\n<p id="tail">Authored tail</p>'),
        PAGE.replace("</head>", '<img src="/media/tail.png" alt="tail">\n</head>'),
    ],
)
def test_check_rejects_paintable_markup_the_browser_reparents(page_dir, html):
    """HTML recovery cannot move authored pixels around the main boundary."""
    (page_dir / "versions" / "v1.html").write_text(html)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_owns_the_lf_meta_vocabulary(page_dir):
    # The sign-off declaration: valid on its one value, rejected on a misspelled
    # value or name — either would silently declare nothing in the browser.
    signoff = PAGE.replace(
        "<title>t</title>",
        '<title>t</title>\n<meta name="lf-review" content="sign-off">',
    )
    (page_dir / "versions" / "v1.html").write_text(signoff)
    assert check(page_dir).exit_code == 0

    (page_dir / "versions" / "v1.html").write_text(
        signoff.replace("sign-off", "approve")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "content must be one of ['sign-off'], found 'approve'" in result.output

    (page_dir / "versions" / "v1.html").write_text(
        signoff.replace("lf-review", "lf-signoff")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "unknown lf- meta" in result.output
    assert "lf-review" in result.output  # the error names the known vocabulary


def test_check_rejects_duplicate_ids_and_dropped_ids(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="flag-first"')
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "duplicate ids" in result.output
    assert "dropped in v2.html" in result.output
    assert "backfill-first" in result.output


def test_a_version_may_not_quietly_rewrite_what_the_user_decided(page_dir):
    """The runtime replays a recorded action onto every later version, so the
    user's edit stands over whatever v2's markup says about that widget.
    Which makes a rewritten widget a version talking to nobody — its new words
    could never reach the reader. `restated` is how a version says it means to
    take the decision back, and this is the gate that makes it say so."""
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    assert check(page_dir).exit_code == 0

    # Re-emitting what v1 said is the ordinary republish, and costs nothing:
    # the user's edit is already on screen over it.
    v2("Ship the flag dark, then backfill.")
    assert check(page_dir, version=2).exit_code == 0, (
        "a republish that changes nothing must pass"
    )

    # Writing their own words back is the other quiet case, and the commoner
    # one: the version agrees with the edit rather than overruling it. A gate
    # that fired here would fire on almost every version an author writes, and
    # a gate that fires on correct work is one they learn to silence.
    v2("Cut the flag; backfill first.")
    assert check(page_dir, version=2).exit_code == 0, "honoring an edit must pass"

    # Rewriting the words under the edit is the case that needs a decision.
    v2("Ship the flag dark, then backfill. Roll back with one flag.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "its words changed" in result.output
    assert "edit on v1" in result.output
    assert "restated" in result.output

    # Said out loud, the same version publishes.
    v2("Ship the flag dark, then backfill. Roll back with one flag.", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0, "a restated rewrite is allowed"


def test_restating_on_the_first_version_is_refused(page_dir):
    """There is nothing before v1 to take back, so `restated` there can only be
    a misreading of what the word does — and one that would record a retraction
    of nothing into the log."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1" restated><pre>Words.</pre></lf-draft>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "nothing to retract" in result.output
    assert "recorded nothing on it" in result.output


def test_restating_a_widget_that_kept_its_words_is_refused(page_dir):
    """`restated` discards what the user recorded, so a version may only
    spend it where there is a rewrite to justify it. Unpoliced, it is the one
    word that turns the gate back into the silence it replaced."""
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    v2("Ship the flag dark, then backfill.", attrs=" restated")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "nothing to retract" in result.output
    assert "unchanged since v1" in result.output


def test_report_validates_at_the_door_and_stamps_identity(page_dir, monkeypatch):
    """`leaf report` is the report event's one door, so the widget, verb, and
    detail are held to the x-report declaration there — the CLI mirror of the
    POST door's action gate — and the event leaves stamped with the posting
    session's voice and the version the reader is looking at."""
    _tasks_version(page_dir, 1, "active")
    unpublished = _report(page_dir, "t-parser", "status", "status=review")
    assert unpublished.exit_code == 1
    assert "no published version" in unpublished.output

    publish(page_dir)
    for args, message in [
        (("nope", "status", "status=review"), "unknown report widget"),
        (("tree", "status", "status=review"), "does not declare report verb"),
        (("t-parser", "finish", "status=done"), "does not declare report verb"),
        (("t-parser", "status", "status=shipping"), "detail is invalid"),
        (("t-parser", "status", "status"), "name=value"),
        (("t-parser", "status"), "'status' is a required property"),
    ]:
        refused = _report(page_dir, *args)
        assert refused.exit_code == 1, args
        assert message in refused.output, args
    assert all(e["kind"] != "report" for e in interact.read_events(page_dir))

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0, sent.output
    event = interact.read_events(page_dir)[-1]
    assert event["kind"] == "report" and event["author"] == "claude"
    assert (event["agent"], event["session"]) == ("Indexer", "worker-1")
    assert event["widget"] == "t-parser" and event["action"] == "status"
    assert event["detail"] == {"status": "review"} and event["version"] == 1


def test_a_version_may_not_quietly_contradict_a_standing_report(page_dir):
    """A report is provisional news with the reviewer precedence reversed:
    silence leaves it painting, writing the reported state absorbs it, and a
    version that writes something else must say so with `overruled` — the gate
    refuses the silent contradiction, which would otherwise drop a worker's
    news without anyone adjudicating it."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0

    # Blessed silence: markup unchanged, the report keeps painting — and the
    # passing run says so in the record-debt register.
    _tasks_version(page_dir, 2, "active")
    silent = check(page_dir, version=2)
    assert silent.exit_code == 0
    assert "a report records status → 'review'" in silent.output

    # Honoring: writing the reported state.
    _tasks_version(page_dir, 2, "review")
    assert check(page_dir, version=2).exit_code == 0, "honoring a report must pass"

    # Contradiction, unnamed: refused, naming the report and both states.
    _tasks_version(page_dir, 2, "done")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "contradicts a standing report" in result.output
    assert "'done'" in result.output and "'review'" in result.output
    assert "overruled" in result.output

    # Said out loud, the same version publishes — including back to the state
    # the report tried to move (rejecting the news without changing the page).
    _tasks_version(page_dir, 2, "done", " overruled")
    assert check(page_dir, version=2).exit_code == 0
    _tasks_version(page_dir, 2, "active", " overruled")
    assert check(page_dir, version=2).exit_code == 0


def test_publishing_records_typed_settlements_for_provisional_agent_facts(page_dir):
    """One durable relation ends both kinds of provisional agent information.
    Its typed targets keep report-event ids and widget-work ids distinct without
    growing one note field for each channel."""

    def add_board(version: int) -> None:
        path = page_dir / "versions" / f"v{version}.html"
        path.write_text(
            path.read_text().replace(
                '<lf-diagram id="flow">',
                '<lf-board id="rollout"><lf-column id="now" label="Now">'
                '<lf-card id="rollout-card"><strong>Ship</strong></lf-card>'
                '</lf-column></lf-board><lf-diagram id="flow">',
            )
        )

    _tasks_version(page_dir, 1, "active")
    add_board(1)
    runner = CliRunner()
    assert (
        runner.invoke(
            interact.cli,
            ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
        ).exit_code
        == 0
    )
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0
    report_id = json.loads(sent.output)["id"]
    claimed = _status(
        page_dir, "working", "checking the rollout", "--on", "rollout-card"
    )
    assert claimed.exit_code == 0, claimed.output

    _tasks_version(page_dir, 2, "review")
    add_board(2)
    published = runner.invoke(
        interact.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "2",
            "--text",
            "absorb",
            "--completes",
            "rollout-card",
        ],
    )
    assert published.exit_code == 0, published.output
    note = [e for e in interact.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["settles"] == [
        {"kind": "report", "id": report_id},
        {"kind": "work", "id": "rollout-card"},
    ]

    # The report ended at v2, so v3 owes it nothing.
    _tasks_version(page_dir, 3, "done")
    add_board(3)
    assert check(page_dir, version=3).exit_code == 0

    # And a repeated `overruled` after the answer is the carried-forward
    # attribute, refused the way a repeated `restated` is.
    _tasks_version(page_dir, 3, "done", " overruled")
    stale = check(page_dir, version=3)
    assert stale.exit_code == 1
    assert "v2 already answered" in stale.output

    # Reissuing an older version cannot absorb a report made on a later one,
    # even when the old file happens to state the reported value.
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0, sent.output
    future_report = json.loads(sent.output)["id"]
    _tasks_version(page_dir, 1, "review")
    republished = CliRunner().invoke(
        interact.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "1",
            "--text",
            "reissued old cut",
        ],
    )
    assert republished.exit_code == 0, republished.output
    note = [e for e in interact.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["version"] == 1
    assert {"kind": "report", "id": future_report} not in note.get("settles", [])


def test_publish_and_report_choose_one_log_order(page_dir, monkeypatch):
    """Report versioning and note calculation are one transaction each."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    _tasks_version(page_dir, 2, "review")

    at_commit = threading.Event()
    resume = threading.Event()
    original_append_event = interact.append_event

    def held_append_event(directory, event):
        if event.get("kind") == "note" and event.get("version") == 2:
            at_commit.set()
            assert resume.wait(timeout=10), "the report did not enter the publish gap"
        return original_append_event(directory, event)

    monkeypatch.setattr(interact, "append_event", held_append_event)
    with ThreadPoolExecutor(max_workers=2) as executor:
        publishing = executor.submit(interact.cmd_publish, page_dir, 2, "absorb")
        assert at_commit.wait(timeout=10), "publish never reached its note commit"
        serialized = interact.lock_is_held(page_dir / "comments.jsonl")
        reporting = executor.submit(
            interact.cmd_report,
            page_dir,
            "t-parser",
            "status",
            ("status=review",),
        )
        # This branch only prevents the test harness from deadlocking in the
        # correct implementation: a transaction-holding publish must finish
        # before the report can derive its version; the current unlocked publish
        # lets the report finish first and exposes the inconsistent order.
        if serialized:
            resume.set()
            publishing.result(timeout=10)
            reporting.result(timeout=10)
        else:
            reporting.result(timeout=10)
            resume.set()
            publishing.result(timeout=10)

    events = interact.read_events(page_dir)
    report = [event for event in events if event["kind"] == "report"][-1]
    note = [event for event in events if event["kind"] == "note"][-1]
    assert serialized, "publish calculated mutable log state outside its transaction"
    assert note["version"] == 2 and "settles" not in note
    assert report["version"] == 2


def test_absorption_is_by_id_never_inferred_from_markup(page_dir):
    """The bug put back: a v2 that writes the reported state but whose note
    names no report ids (the shape a hand-built note has) leaves the report
    standing, so a v3 that moves the state again is refused. Without the
    id-explicit record the gate would infer absorption from v2's markup and let
    the report die silently."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0
    _tasks_version(page_dir, 2, "review")
    publish(page_dir, version=2)  # a bare note: honoring markup, nothing named

    _tasks_version(page_dir, 3, "done")
    result = check(page_dir, version=3)
    assert result.exit_code == 1
    assert "contradicts a standing report" in result.output


def test_an_unearned_overruled_is_refused(page_dir):
    """`overruled` discards a worker's news, so a version may only spend it
    where a disagreement justifies it — agreeing with the report, or wearing it
    with no report standing, is the reflex that would hollow the gate out."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)

    # Nothing standing at all.
    _tasks_version(page_dir, 2, "active", " overruled")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "nothing to overrule" in result.output

    # Standing, but the markup writes the reported state: that is absorption.
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0
    _tasks_version(page_dir, 2, "review", " overruled")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "writes the reported state" in result.output


def test_overruled_is_earned_even_when_prev_dropped_the_unit(page_dir):
    """Whether `overruled` is earned is this version's markup against the
    report, not whether the *previous* version's markup still carried the id.
    A unit that vanished from prev and comes back writing a disagreeing state
    is a named disagreement like any other — id-survival is a separate
    question, and letting it decide earning told an honestly overruling
    version it was writing the reported state (absorption) instead."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0

    # v2 drops the task's id outright. `publish` registers it as the baseline
    # directly, the way test_absorption_is_by_id_never_inferred_from_markup
    # does — id-survival is its own gate, not what this test is about.
    (page_dir / "versions" / "v2.html").write_text(PAGE)
    publish(page_dir, version=2)

    # v3 brings the id back, honoring its own state and overruling the report
    # still standing from v1 — this must pass, not be told it's absorbing.
    _tasks_version(page_dir, 3, "done", " overruled")
    result = check(page_dir, version=3)
    assert result.exit_code == 0, result.output


def test_the_gate_asks_about_the_card_that_was_moved_and_not_the_board(page_dir):
    """A `move` names the board, but what the user decided about is the card:
    where it belongs. Holding the version to the board's whole contents would
    refuse it for editing an untouched card or adding a new one — a rule that
    fires on innocent versions is one authors learn to silence.

    So the subject is the card, and `restated` on it retracts that card's moves
    alone. The rest of the board stays where the user put it, which is what
    keeps a typo fix from costing them an afternoon's arrangement."""

    def write(version, todo, done):
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _board(todo, done))
        )

    write(1, [X, Y], [])
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "b1",
            "action": "move",
            "detail": {"card": "card-x", "to": "c-done", "index": 0},
        },
    )
    assert check(page_dir).exit_code == 0

    # An untouched card rewritten, the moved card's own words left alone.
    write(2, [X, ("card-y", "", "Wire the importer and its backfill")], [])
    assert check(page_dir, version=2).exit_code == 0, (
        "an untouched card is not the gate's business"
    )

    # The card written where the user put it. Redundant now that replay
    # carries the move, but a version that does it anyway is not wrong.
    write(2, [Y], [X])
    assert check(page_dir, version=2).exit_code == 0, (
        "relocating the moved card must pass"
    )

    # The moved card's own words rewritten: now the decision is in question.
    write(2, [("card-x", "", "Guard the delete behind the flag"), Y], [])
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "card-x" in result.output and "move on v1" in result.output
    assert "card-y" not in result.output, (
        "the gate named a card nobody had decided about"
    )

    write(2, [("card-x", " restated", "Guard the delete behind the flag"), Y], [])
    assert check(page_dir, version=2).exit_code == 0

    # And the board itself never takes the attribute: every move names a card, so
    # a board is never what a decision rests on, and offering `restated` there
    # would be a door onto an error message about retracting nothing.
    (page_dir / "versions" / "v2.html").write_text(
        (page_dir / "versions" / "v2.html")
        .read_text()
        .replace('<lf-board id="b1">', '<lf-board id="b1" restated>')
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "restated" in result.output and "lf-board" in result.output


def test_the_gate_reads_a_pick_the_same_way_it_reads_an_edit(page_dir):
    """The rule was built on drafts and boards; a pick is the case it was not
    built on. It lands the same way because nothing in it is per-widget: the
    subject is what the detail names, so a pick rests on the option picked. What
    the other options say is then free to change, and marking the pick `chosen`
    — the one thing every version does after a pick — says nothing, so it is
    invisible to the comparison.

    A chip is content rather than a mark, so writing one onto a picked option is
    changing what they picked and lands in the same comparison its prose does.
    The gate reads the version the way the anchor pass does, which is what keeps
    that true without anything here knowing a chip from a paragraph."""

    def write(version, **kw):
        opts = OPTIONS.format(
            **{
                "a": "",
                "b": "",
                "chip": "",
                "shim": "Fastest to ship.",
                "stage": "Table by table.",
                **kw,
            }
        )
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write(1)
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )
    assert check(page_dir).exit_code == 0

    # The record the next version owes: the picked card marked, nothing else.
    write(2, a=" chosen")
    assert check(page_dir, version=2).exit_code == 0, (
        "marking the pick is not a rewrite"
    )

    # An option nobody picked, rewritten freely.
    write(2, a=" chosen", stage="One table at a time, behind a flag.")
    assert check(page_dir, version=2).exit_code == 0, (
        "an unpicked option is free to change"
    )

    # The picked one, rewritten — the user chose those words.
    write(2, a=" chosen", shim="Fastest to ship, and we own the shim forever.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "o-shim" in result.output and "choose on v1" in result.output

    write(2, a=" chosen restated", shim="Fastest to ship, and we own the shim forever.")
    assert check(page_dir, version=2).exit_code == 0

    # A chip is a word on the page: one appearing on the option they picked reads
    # to them as the option changing, and is caught the same way its prose is.
    write(2, a=" chosen", chip="<lf-chip>effort: high</lf-chip>")
    result = check(page_dir, version=2)
    assert result.exit_code == 1, "a chip is words the user read"
    assert "o-shim" in result.output

    write(2, a=" chosen restated", chip="<lf-chip>effort: high</lf-chip>")
    assert check(page_dir, version=2).exit_code == 0

    # A later pick on the same coordinate releases the old option's words.
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-stage"]},
        },
    )
    write(2, b=" chosen", shim="The shim now has a bounded removal date.")
    assert check(page_dir, version=2).exit_code == 0


def test_a_cleared_pick_rests_on_the_group_that_holds_it(page_dir):
    """Clearing a pick names no option (`{"options": []}`), so there is no part
    of the widget for the decision to rest on and it rests on the group. That
    falls out of the subject rule rather than being written for this case — which
    is why the group takes `restated` and a board, whose every move names a card,
    does not."""

    def write(version, shim="Fastest to ship.", attrs=""):
        opts = OPTIONS.format(a="", b="", chip="", shim=shim, stage="Table by table.")
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace(
                "<h2>Plan</h2>",
                "<h2>Plan</h2>"
                + opts.replace(
                    '<lf-options id="g1" choose>', f'<lf-options id="g1" choose{attrs}>'
                ),
            )
        )

    write(1)
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": []},
        },
    )
    write(2, shim="Fastest to ship, and we own the shim forever.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "lf-options id='g1'" in result.output

    write(2, shim="Fastest to ship, and we own the shim forever.", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0


def test_a_version_may_not_quietly_move_the_pick(page_dir):
    """The words gate can't see `chosen` — the attribute says nothing — so this
    is the state gate's own case: a version marking a different option than the
    user picked is overruling them as surely as a rewrite is, and says so
    with the group's `restated` or not at all. After the retraction the state is
    the author's again: the next version moves the pick freely, because a unit
    with no surviving folded action is exempt — that exemption is what keeps
    the retract-and-ask-again flow from deadlocking one version later."""

    def write(version, a="", b="", attrs="", shim="Fastest to ship."):
        opts = OPTIONS.format(a=a, b=b, chip="", shim=shim, stage="Table by table.")
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace(
                "<h2>Plan</h2>",
                "<h2>Plan</h2>"
                + opts.replace(
                    '<lf-options id="g1" choose>', f'<lf-options id="g1" choose{attrs}>'
                ),
            )
        )

    write(1)
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )

    # The author's markup contradicting the recorded pick, words untouched.
    write(2, b=" chosen")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "its state changed" in result.output
    assert "'o-stage'" in result.output and "'o-shim'" in result.output

    # Said out loud — on the group, the unit the fold keys the pick by.
    write(2, b=" chosen", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0, check(page_dir, version=2).output
    result = CliRunner().invoke(
        interact.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "2",
            "--text",
            "moved the default",
        ],
    )
    assert result.exit_code == 0, result.output

    # The retraction handed the state back: v3 owns it, no ritual to repeat.
    write(3, a=" chosen")
    assert check(page_dir, version=3).exit_code == 0, check(page_dir, version=3).output

    # And the words gate agrees the pick is dead: the group's retraction floors
    # everything resting inside it, so rewriting the once-picked option's words
    # is free — one key space for liveness, or the gate would demand a second
    # `restated` for a decision the browser already dropped.
    publish(page_dir, 3)
    write(4, a=" chosen", shim="Fastest to ship, and the shim is ours to keep.")
    assert check(page_dir, version=4).exit_code == 0, check(page_dir, version=4).output


def test_check_reports_record_lag_without_erroring(page_dir):
    """Silence is blessed — replay resolves it — but a log-less reader sees only
    the markup, so `version check` says where it lags the log, as advice on a passing
    run. `leaf transcript` says the same to stderr, where the debt stops being
    fixable."""

    def write(version, a=""):
        opts = OPTIONS.format(
            a=a, b="", chip="", shim="Fastest to ship.", stage="Table by table."
        )
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write(1)
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )
    write(2)
    result = check(page_dir, version=2)
    assert result.exit_code == 0
    assert "record behind the log" in result.output
    assert "g1" in result.output and "o-shim" in result.output

    # Honored, the debt is gone and so is the advice.
    write(2, a=" chosen")
    result = check(page_dir, version=2)
    assert result.exit_code == 0
    assert "record behind the log" not in result.output

    result = CliRunner().invoke(interact.cli, ["transcript", str(page_dir)])
    assert "record behind the log" in result.output  # CliRunner folds stderr in


def test_record_lag_uses_the_version_being_checked(page_dir):
    """A pinned version does not owe state from an action made on a later one."""
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    for version in (1, 2):
        (page_dir / "versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )
        publish(page_dir, version)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 2,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-stage"]},
        },
    )

    result = check(page_dir, version=1)
    assert result.exit_code == 0, result.output
    assert "record behind the log" not in result.output


def test_file_state_scopes_a_nested_pick_to_its_nearest_recorded_owner(page_dir):
    """The file-side facet is the runtime's same ownership reading. An inner chosen
    option is not part of the outer group's record, so an outer log choice that matches
    its own authored option carries no phantom lag."""
    nested = """<lf-options id="outer" choose multiple>
  <lf-option id="outer-a" chosen><strong>Outer A</strong>
    <lf-options id="inner" choose>
      <lf-option id="inner-a" chosen>Inner A</lf-option>
      <lf-option id="inner-b">Inner B</lf-option>
    </lf-options>
  </lf-option>
  <lf-option id="outer-b"><strong>Outer B</strong></lf-option>
</lf-options>"""
    html = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + nested)
    (page_dir / "versions" / "v1.html").write_text(html)
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "outer",
            "action": "choose",
            "detail": {"options": ["outer-a"]},
        },
    )

    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "record behind the log" not in result.output


def test_page_state_folds_the_log_onto_the_published_page(page_dir):
    """`page state` is /api/state folded for the agent: the banner's ask list,
    the standing state replay paints, and record_lag's advice, as one queryable
    object — the position a session picking up a standing page would otherwise
    re-derive from the raw log."""
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    state = state_json(page_dir)
    assert state["versions"] == {"published": [1], "written": [1]}
    # The one asking group: PAGE's own bare <lf-options> takes no `choose`.
    assert state["asks"] == [{"id": "g1", "tag": "lf-options", "thread": None}]
    assert {"g1", "o-shim", "o-stage"} <= {el["id"] for el in state["elements"]}
    assert state["state"] == [] and state["lag"] == []

    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )
    state = state_json(page_dir)
    assert state["asks"] == []
    assert state["state"] == [
        {
            "widget": "g1",
            "unit": "g1",
            "facet": "selection",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "version": 1,
            "seq": 2,
            # On every entry, and null for a page widget: the key names which of the
            # page's two documents the decision was made in, and `asks` above has
            # carried it exactly this way all along.
            "thread": None,
        }
    ]
    assert state["lag"] == [
        {
            "widget": "g1",
            "unit": "g1",
            "facet": "selection",
            "channel": "action",
            "action": "choose",
            "log": ["o-shim"],
            "markup": [],
        }
    ]
    assert state["pending"] == 1 and state["unacked"] == 1

    # Completion is an independent fact on the same widget. It stands beside
    # selection instead of superseding it, and both are visible to the agent.
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "answer",
            "detail": {},
        },
    )
    assert [
        (item["facet"], item["action"]) for item in state_json(page_dir)["state"]
    ] == [
        ("completion", "answer"),
        ("selection", "choose"),
    ]


def test_page_state_names_the_ask_region_but_keeps_state_on_its_request(page_dir):
    """The Ask list names the whole reading the reader arrives at. Its nested
    request remains the action owner, so answering it closes the broader Ask without
    moving the standing decision onto a wrapper that declares no state."""
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    ask = (
        '<lf-ask id="plan-ask"><h2>Plan</h2>'
        "<p>Choose after reading this framing.</p>"
        f"{opts}</lf-ask>"
    )
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<h2>Plan</h2>", ask))
    publish(page_dir)

    state = state_json(page_dir)
    assert state["asks"] == [{"id": "plan-ask", "tag": "lf-ask", "thread": None}]

    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )
    state = state_json(page_dir)
    assert state["asks"] == []
    assert state["state"][0]["widget"] == "g1"


def test_page_state_prefers_a_reader_action_over_a_report_on_the_same_facet(page_dir):
    """A report remains live for later absorption, but the reader's action is
    the desired state and the only record debt on their shared coordinate."""
    registry = json.loads((page_dir / "registry.json").read_text())
    options = registry["lf-options"]
    options["properties"]["overruled"] = {"type": "boolean"}
    options["x-report"] = {"choose": options["x-state"]["choose"]}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-stage"]},
        },
    )
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
        },
    )

    state = state_json(page_dir)
    assert state["state"][0]["detail"] == {"options": ["o-shim"]}
    assert state["reports"][0]["detail"] == {"options": ["o-stage"]}
    assert state["lag"] == [
        {
            "widget": "g1",
            "unit": "g1",
            "facet": "selection",
            "channel": "action",
            "action": "choose",
            "log": ["o-shim"],
            "markup": [],
        }
    ]


def test_page_state_reads_an_authored_answer_with_no_log(page_dir):
    """A version that honors a pick in its markup reads as answered with no log
    at all — the shipped examples arrive that way."""
    opts = OPTIONS.format(a=" chosen", b="", chip="", shim="s.", stage="t.")
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    assert state_json(page_dir)["asks"] == []


def test_page_state_holds_a_thread_ask_open_until_its_verb(page_dir):
    """A widget in thread markup asks like one on the page, `until` holds a
    `multiple` group open across picks, and only the named verb closes it."""
    (page_dir / "versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    root = interact.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "text": "Which mitigations?",
            "markup": '<lf-options id="gm" choose multiple>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            '<lf-option id="m-alert"><strong>Alert</strong></lf-option>'
            "</lf-options>",
        },
    )
    assert state_json(page_dir)["asks"] == [
        {"id": "gm", "tag": "lf-options", "thread": root["id"]}
    ]
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"options": ["m-cap"]},
        },
    )
    assert state_json(page_dir)["asks"] == [
        {"id": "gm", "tag": "lf-options", "thread": root["id"]}
    ]
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "gm",
            "action": "answer",
            "detail": {},
        },
    )
    assert state_json(page_dir)["asks"] == []


def test_page_state_carries_a_report_until_a_version_answers_it(page_dir):
    """A standing report closes the ask its status change resolves, stands in
    `reports` with the record lag beside it, and leaves when a note absorbs it."""
    tasks = (
        '<lf-tasks id="work"><lf-task id="t-parser" status="review">'
        "<strong>Parser</strong> Ready for eyes.</lf-task></lf-tasks>"
    )
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)
    assert state_json(page_dir)["asks"] == [
        {"id": "t-parser", "tag": "lf-task", "thread": None}
    ]
    rep = interact.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "version": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"status": "done"},
        },
    )
    state = state_json(page_dir)
    assert state["asks"] == []
    assert state["reports"] == [
        {
            "widget": "t-parser",
            "unit": "t-parser",
            "facet": "status",
            "action": "status",
            "detail": {"status": "done"},
            "version": 1,
            "seq": 2,
            "agent": "worker",
            "standing": 1,
        }
    ]
    assert state["lag"] == [
        {
            "widget": "t-parser",
            "unit": "t-parser",
            "facet": "status",
            "channel": "report",
            "action": "status",
            "log": "done",
            "markup": "review",
        }
    ]
    # The absorbing version writes the status and its note names the report.
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", "<h2>Plan</h2>" + tasks.replace('"review"', '"done"')
        )
    )
    interact.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
            "version": 2,
            "text": "absorbed",
            "settles": [{"kind": "report", "id": rep["id"]}],
        },
    )
    state = state_json(page_dir)
    assert state["reports"] == [] and state["lag"] == [] and state["asks"] == []


def test_page_state_before_first_publish(page_dir):
    """A page with only a draft has no published reading: versions say so and
    every markup-derived field is empty rather than an error."""
    state = state_json(page_dir)
    assert state["versions"] == {"published": [], "written": [1]}
    assert state["elements"] == [] and state["asks"] == []
    assert state["title"] == "t"  # from the written draft


def test_check_advises_where_a_users_aim_has_nothing_to_land_on(page_dir):
    """A block a user points at whole needs an id, or the aim falls through to
    the enclosing section — the failure item anchoring's own page shipped. Advice
    on a passing run, not a gate, and quiet where a tight wrapper (a figure around
    a table) already gives the aim something to hold."""
    blocks = (
        "<pre><code>uv run backfill --check</code></pre>"
        '<aside class="sidenote">The retry path is deliberately separate.</aside>'
        '<figure id="fig"><table><tr><td>1</td></tr></table></figure>'
    )
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + blocks).replace(
            "</main>", "<section><p>Unnamed aside.</p></section>\n</main>"
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    advice = [line for line in result.output.splitlines() if "unpointable" in line]
    assert len(advice) == 3, result.output
    assert any("<pre>" in line and "#plan" in line for line in advice)
    assert any("<aside>" in line and "#plan" in line for line in advice)
    assert any("<section>" in line for line in advice)
    assert not any(
        "<table>" in line for line in advice
    )  # the figure's id is aim enough

    # Ids minted, debt gone.
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><pre id="cmd"><code>uv run backfill --check</code></pre>'
            '<aside class="sidenote" id="retry-note">The retry path is deliberately '
            "separate.</aside>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "unpointable" not in result.output
