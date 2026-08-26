"""Standalone export tests."""

import itertools

import pytest
from click.testing import CliRunner
from leaf_interact import cli as cli_model
from leaf_interact import render_checks as render_checks_model
from leaf_interact import rendering as rendering_model
from playwright.sync_api import expect
from render_support import (
    EXAMPLES,
    LONG_PAGE,
    REPORT_PAGE,
    leaf_page,
    primed,
    refuse,
    resized,
    serious_axe_violations,
    watched,
)

pytestmark = pytest.mark.nightly


# ---------- export: the page as one file ----------


def test_an_export_drops_a_live_widget_work_claim(browser, serve, tmp_path):
    """A local work line is live runtime chrome even though its seat is in the page.
    A standalone copy has no agent behind it, so preserving the rendered sentence
    would turn a provisional claim into a frozen lie."""
    work_page = leaf_page(
        "work export",
        """
<h1 id="h">Rollout</h1>
<lf-board id="rollout"><lf-column id="now" label="Now">
  <lf-card id="rollout-card"><strong>Ship the rollout</strong> Check the shard.</lf-card>
</lf-column></lf-board>
""",
    )
    url = serve(work_page)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the shard",
            "--on",
            "rollout-card",
        ],
    )
    assert result.exit_code == 0, result.output

    out = tmp_path / "work-copy.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator(".lf-work-line")).to_have_count(0)
    expect(page.locator("#rollout-card")).not_to_contain_text("checking the shard")
    assert errors == []
    page.close()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_exported_example_stands_on_its_own(example, browser, serve, tmp_path):
    """Every shipped example copied to a file and opened from disk, which is the whole
    contract: no server answers, so anything still reaching for one is a hole, and the
    console is where a hole says so. Driven over the corpus rather than one page because
    what a copy loses is per-widget — the gallery alone would pass while the widget only
    it lacks was the broken one.

    A copy over-promising is the other half of that, and it went unread for as long as
    there was nothing here asking. Tab into an exported decision page landed on a pick
    mark, which summoned the keyboard address for a key that answers nothing, into a row
    holding no column for it; a board's ten grips each opened a grab cursor; twenty
    options lit under a pointer that could not pick one. So the copy is asked what it
    still offers, in the three registers an offer is made in — a widget's chrome still
    holding a tab stop or a role, a control standing there with nothing left behind it,
    and a hand or a grab under the pointer — and every question is put to the markers
    rather than to any widget."""
    url = serve(example)
    out = tmp_path / "standalone.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.on("requestfailed", lambda r: errors.append(f"unfetched {r.url}"))
    page.goto(out.as_uri(), wait_until="load")
    state = page.evaluate("""() => ({
        scripts: document.querySelectorAll('script').length,
        chrome: document.querySelectorAll('.lf-chrome').length,
        toServer: [...document.querySelectorAll('[src^="/"], [href^="/"]')]
            .map(e => e.getAttribute('src') ?? e.getAttribute('href')),
        links: document.querySelectorAll('link[rel="stylesheet"]').length,
        column: getComputedStyle(document.querySelector('main')).maxWidth,
        // A page gives up a strip of its own width for what it hangs in the margin, and
        // a copy keeps only the strips whose residents came with it: a suggestion's
        // controls are gone from a file that can decide nothing, and its rail with them,
        // while sidenotes are the page's own words and stand in a copy exactly as they
        // stand on screen. So the reading is not that the column is centred — a page
        // carrying notes is deliberately not — but that no strip is held open for
        // nothing. Asked of body's padding, which is where every strip is taken from,
        // and of whatever is standing in it, whichever layer reserved it.
        empty: ((b, s) => {
            const box = b.getBoundingClientRect();
            const held = (lo, hi) => hi - lo > 1 && ![...document.querySelectorAll('main *')]
                .some(el => { const r = el.getBoundingClientRect();
                              return el.checkVisibility() && r.width > 1
                                     && r.left < hi - 1 && r.right > lo + 1; });
            return [
                held(box.left, box.left + parseFloat(s.paddingLeft)) && 'left',
                held(box.right - parseFloat(s.paddingRight), box.right) && 'right',
            ].filter(Boolean);
        })(document.body, getComputedStyle(document.body)),
        unshown: [...document.querySelectorAll('main *')]
            .filter(el => el.textContent.trim() && !el.checkVisibility()
                          // A disclosure the reader can still work, a control's own
                          // label, and an element with no box by design are all fine;
                          // what is not is the page's words with nothing to reveal them.
                          && !el.closest('details, [data-lf-offer], .lf-ui, style, script')
                          && getComputedStyle(el).display !== 'contents')
            .map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')),
        // A press a widget injected is a tab stop wearing an interactive role, and the
        // handler that answered both went with the scripts. Asked of the chrome marker
        // and of any role at all, never of a role by name: offer writes role="button"
        // and a widget keeping an ARIA pattern writes over it (lf-tabs' presses say
        // "tab"), so a list of roles here would be a list that stops at the ones it was
        // taught. The twelfth widget is covered by having used offer.
        //
        // The role a control the browser drives wears is the copy telling the truth —
        // lf-shot's label still flips its frames, its checkbox still takes the keyboard —
        // so the role half stands down for one of the platform's own controls. The tab
        // stop's half does not: offer writes that on presses of its own making and on
        // nothing else.
        pressable: [...document.querySelectorAll('[data-lf-offer][tabindex]'),
                    ...[...document.querySelectorAll('[data-lf-offer][role]')]
                        .filter(el => !el.querySelector(
                            'input, select, textarea, a[href], button'))]
            .map(el => el.className || el.tagName.toLowerCase()),
        // The claim a disarmed attribute leaves standing, since a control nothing can
        // work is still a control on the page. What a copy may show of a widget's
        // chrome is one the browser works itself and a label the page speaks through
        // (data-lf-said); the rest belonged to a runtime the file has not got, so a
        // mark reading "choose one" invites a reader who cannot answer it.
        inert: [...document.querySelectorAll('[data-lf-offer]:not([data-lf-said])')]
            .filter(el => el.checkVisibility() && el.textContent.trim()
                          && !el.matches(':has(input, select, textarea, a[href], button)')
                          && !el.closest('label, summary, a[href]'))
            .map(el => (el.className || el.tagName.toLowerCase()) + ': '
                       + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 24)),
        // The same claim in paint. A hand or a grab says a gesture lands here, and in a
        // copy one lands nowhere the browser isn't the thing acting: a label's checkbox, a
        // link, a disclosure. The exemptions are the platform's own controls, so no
        // widget is named here either.
        offering: [...document.querySelectorAll('main *')]
            .filter(el => el.checkVisibility()
                          && ['pointer', 'grab'].includes(getComputedStyle(el).cursor)
                          && !el.closest('a[href], label, summary, input, select, textarea'))
            .map(el => el.tagName.toLowerCase() + '.'
                       + String(el.className?.baseVal ?? el.className ?? '')),
    })""")
    # The gate's own reading, on the medium that most needs it: a copy is laid out by
    # rules no other medium runs, and the last two ways one went out wrong were both a
    # widget's words landing on the page's.
    covered = page.evaluate(render_checks_model.COVERED_WORDS)
    # The other direction of every question above: not what the copy still offers,
    # but what it under-delivers. BAKE is a remover, and until this ran the only
    # gates on it asked whether it removed enough — a wide diagram lost its scroll
    # stop in every copy, and no sweep read one. 420, because that is the width
    # where boxes start scrolling, and a scrolling box with no way in from the
    # keyboard is the exact class that slipped.
    resized(page, 420, 900)
    axe_violations, axe_report = serious_axe_violations(page)
    page.close()

    assert state["scripts"] == 0, "a copy with no server behind it keeps no script"
    assert state["chrome"] == 0, (
        "the runtime's layer came along — a comment box that swallows what you type"
    )
    assert state["toServer"] == [], "the copy still points at a server that isn't there"
    assert state["links"] == 0, "a stylesheet link survived, pointing at nothing"
    assert state["column"] != "none", "the theme didn't inline; the copy opens unstyled"
    assert state["empty"] == [], (
        "the copy holds a strip of its own width open with nothing standing in it, so "
        "the column sits off to one side of a page it has all of — a rail reserved for "
        f"something the file hasn't got: {state['empty']}"
    )
    assert state["unshown"] == [], (
        "the copy says less than the page did: content sitting behind a control that "
        f"needed a handler, and nothing in a file can press one — {state['unshown']}"
    )
    assert state["pressable"] == [], (
        "the copy offers a press nothing can take: Tab reaches it, a screen reader calls "
        f"it a button, and no handler is left to answer either — {state['pressable']}"
    )
    assert state["inert"] == [], (
        "the copy still shows a control the file has nothing to work with, which asks "
        f"the reader for something they cannot give: {state['inert']}"
    )
    assert state["offering"] == [], (
        "the copy draws a hand over a gesture it cannot take — the pointer promises "
        f"something the file has no script to do: {state['offering']}"
    )
    assert covered == [], f"the copy draws its own words over each other: {covered}"
    assert axe_violations == [], axe_report
    assert errors == [], f"{example.stem} needs a server to render: {errors}"


def test_a_copy_carries_a_workers_standing_report(browser, serve, tmp_path):
    """The copy is the page as replay left it, and a report is replay's other channel —
    none of the corpus can say so, because an example is one version with an empty log.

    The gap the wait covers is real and narrow: the runtime stamps `lf-upgraded` in the
    same breath as it *starts* the first poll, never awaiting it, so the stamp export
    opens on is no promise that anything in the log has been painted. Ordinarily the
    poll goes out during load and export's own `networkidle` waits it out, which is why
    the page arrives painted however the wait is written and why the count being wrong
    stayed invisible. Refusing that first poll is the whole of the difference — replay's
    only chance is then the 2s retry, on the far side of both the stamp and networkidle,
    which is exactly where a loaded machine would have put it. Counting actions alone
    leaves nothing to wait for on a log holding one report, and the copy goes out blank.

    The refusal is served to export's own page rather than the copy's, through the
    stand-in `primed` supplies."""
    url = serve(REPORT_PAGE)
    sent = CliRunner().invoke(
        cli_model.cli,
        ["report", str(serve.page_dir), "t-parser", "status", "status=done"],
    )
    assert sent.exit_code == 0, sent.output

    def refuse_the_first_poll(page):
        polls = itertools.count()
        page.route(
            "**/api/state*",
            lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
        )

    out = tmp_path / "standalone.html"
    out.write_text(
        rendering_model.export_page(
            primed(browser, refuse_the_first_poll), url, serve.page_dir
        )
    )

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("#t-parser")).to_have_attribute("status", "done")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("2/2 done")
    page.close()


def test_a_copy_wears_the_mark_and_claims_no_session(browser, serve, tmp_path):
    """A copy keeps the mark and drops the status painted on it. The live page was
    exported under a working claim — `page init` leaves one — so the tone it was wearing
    is a session that does not exist behind a file, which is the same lie the chrome is
    dropped for. Nothing else on the tab is worth losing over it: the mark still says
    which product wrote the file, and it is inlined, so it survives the copy leaving the
    machine that served it (test_an_exported_example_stands_on_its_own is what says no
    link here still points at a server)."""
    url = serve(LONG_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    # The tone is a stylesheet the runtime appends to the mark, so what says the copy is
    # wearing none is the mark carrying only the one its file was written with.
    icon = page.evaluate("""() => {
        const el = document.querySelector('link[rel=icon]');
        const prefix = 'data:image/svg+xml,';
        const href = el.getAttribute('href');
        if (!href.startsWith(prefix)) return { inlined: false };
        const svg = new DOMParser()
            .parseFromString(decodeURIComponent(href.slice(prefix.length)), 'image/svg+xml')
            .documentElement;
        return {
            inlined: true,
            rest: el.getAttribute('data-lf-rest'),
            toned: svg.querySelectorAll('style').length,
            mark: Boolean(svg.querySelector('.lf-tone')),
        };
    }""")
    page.close()

    assert icon["inlined"], "the copy's tab icon is not a mark the file carries itself"
    assert icon["mark"], "the copy lost the mark rather than the status painted on it"
    assert icon["toned"] == 1, (
        "the copy's tab wears a tone it was exported under, claiming a session no file "
        f"has — {icon['toned']} stylesheets on a mark authored with one"
    )
    assert icon["rest"] is None, "the handover attribute rode along into the copy"
