"""How threads are laid out and styled: message and card heads, floating surfaces
under zoom and short windows, and the chrome's rules staying apart from page and package
styles."""

import io
import json
import re
from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    live_url,
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    displayed,
    example_media,
    leaf_page,
    open_page,
    resized,
    restarting,
    round_trip,
    scroll_settled,
    select_words,
    sending,
    stamp_page,
    wait_for_revision,
    write,
)

from browser.threads import (
    LANDING_WORDS,
    _shadow_tree_widget,
    append_agent_reply,
    open_panel_thread,
    paste_image,
)
from leaf import thread as thread_model
from leaf.render_checks import one_frame, rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(("touch", "surface"), [(False, "panel"), (True, "margin")])
def test_thread_actions_share_consistently_sized_message_headers(
    browser, serve, touch, surface
):
    """Independent thread actions take the first header's spare inline room.

    Controls must not give the opening message a different metadata-to-body gap
    from later user and agent messages. Every header holds the input's target floor,
    and each body keeps the conversation's full reading width.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "testing", None if surface == "panel" else {"section": "lede"}
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "revision": 1,
            "text": "Another thought on the same passage.",
        },
    )
    append_agent_reply(serve.page_dir, root, "Testing received successfully.")
    context = browser.new_context(has_touch=touch, is_mobile=touch)
    page = open_page(browser, url, context=context)
    if surface == "panel":
        card = open_panel_thread(page, root)
    else:
        page.locator(".lf-margin-marker").first.click()
        card = page.locator(".lf-margin-preview .lf-page-thread")
        expect(card).to_be_visible()
    for width in (1440, 390):
        resized(page, width, 900)
        rendered(page)
        geometry = card.evaluate(
            """card => {
              const box = selector => card.querySelector(selector).getBoundingClientRect();
              const title = card.querySelector('.lf-thread-head')?.getBoundingClientRect();
              const head = box('.lf-msg-head');
              // The panel's Resolve stands among its view's controls, off the messages' rows.
              const action = card.querySelector('.lf-resolve')?.getBoundingClientRect()
                ?? null;
              const body = box('.lf-msg-body');
              const center = box => box.top + box.height / 2;
              return {
                headerGap: title ? head.top - title.bottom : null,
                messageGaps: [...card.querySelectorAll('.lf-msg')].map(message => {
                  const name = message.querySelector('.lf-msg-head b').getBoundingClientRect();
                  const body = message.querySelector('.lf-msg-body').getBoundingClientRect();
                  return body.top - name.bottom;
                }),
                centers: action && [center(head), center(action)],
                headRight: head.right, actionLeft: action?.left,
                bodyLeft: body.left, headLeft: head.left,
                bodyRight: body.right, actionRight: action?.right,
              };
            }"""
        )
        assert (geometry["centers"] is None) == (surface == "panel"), geometry
        if geometry["centers"] is not None:
            assert abs(geometry["centers"][0] - geometry["centers"][1]) < 1, geometry
            assert geometry["headRight"] <= geometry["actionLeft"], geometry
            assert geometry["bodyRight"] >= geometry["actionRight"], geometry
        if geometry["headerGap"] is not None:
            assert 0 <= geometry["headerGap"] <= 12, geometry
        assert len(geometry["messageGaps"]) == 3, geometry
        assert max(geometry["messageGaps"]) - min(geometry["messageGaps"]) < 0.01, (
            geometry
        )
        assert geometry["bodyLeft"] == geometry["headLeft"], geometry


@pytest.mark.parametrize("surface", ["panel", "margin"])
def test_a_message_says_its_age_only_where_it_changes(browser, serve, surface):
    """A thread says each message's age only where that age, as displayed, differs
    from the message above, the first always saying it: three messages written on one
    day three days ago read one age, and a reply written now reads its own."""
    url = serve(PANEL_PAGE)
    then = datetime.now().astimezone() - timedelta(days=3)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is the retry bounded?",
            "ts": then.isoformat(),
            **({"anchor": {"section": "lede"}} if surface == "margin" else {}),
        },
    )["id"]
    for at, (author, text) in enumerate(
        [("agent", "Yes, three tries."), ("user", "Then park it after.")], start=1
    ):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": author,
                **({"agent": "Claude"} if author == "agent" else {}),
                "parent": root,
                "revision": 1,
                "text": text,
                "ts": (then + timedelta(minutes=at)).isoformat(),
            },
        )
    append_agent_reply(serve.page_dir, root, "Parked after the third.")
    page = open_page(browser, url)
    if surface == "panel":
        card = open_panel_thread(page, root)
    else:
        page.locator(".lf-margin-marker").first.click()
        card = page.locator(".lf-margin-preview .lf-page-thread")
        expect(card).to_be_visible()
    ages = card.locator(".lf-msg-head")
    expect(ages).to_have_count(4)
    assert ages.evaluate_all(
        "heads => heads.map((head) => head.querySelector('time')?.textContent ?? null)"
    ) == ["3d ago", None, None, "just now"]


# Where a message's words may run to, and the thread's inset before its words.
WORDS_END = """message => {
  const words = message.querySelector('.lf-msg-text');
  const end = words.getBoundingClientRect().right
    - parseFloat(getComputedStyle(words).paddingInlineEnd);
  const inset = parseFloat(
    getComputedStyle(message).getPropertyValue('--lf-thread-text-inset'));
  return {end, inset};
}"""


@pytest.mark.parametrize("surface", ["panel", "seat"])
def test_the_user_s_words_end_where_the_agent_s_do(browser, serve, surface):
    """The user's own message runs to the thread's column, as the agent's under it
    does, keeping at its end only the inset its words start with, where its rewrite's
    frame stands. In the panel the user's lines stopped 86px short of the agent's, and
    41px in a thread on the page, the room Send takes in the field they were typed in,
    so every message the user sent wrapped narrower than the reply under it."""
    words = (
        "Check that these balance robust interfaces with code simplicity, deferring "
        "to standards and the browser wherever they can, and keeping the code simple."
    )
    url = serve(PANEL_PAGE if surface == "panel" else THREAD_DIFF_PAGE)
    root = panel_comment(
        serve.page_dir, words, None if surface == "panel" else {"section": "cd-q"}
    )
    append_agent_reply(serve.page_dir, root, words)
    page = open_page(browser, url)
    resized(page, 1280, 900)
    if surface == "panel":
        thread = open_panel_thread(page, root)
    else:
        thread = page.locator("#cd-q .lf-page-thread").first
    user, agent = thread.locator(".lf-msg.user"), thread.locator(".lf-msg.agent")
    expect(agent).to_contain_text("Check that these")
    rendered(page)
    mine, theirs = user.evaluate(WORDS_END), agent.evaluate(WORDS_END)
    assert theirs["end"] - mine["end"] == pytest.approx(mine["inset"], abs=0.5), (
        mine,
        theirs,
    )


def test_opening_message_reactions_does_not_reflow_the_thread(browser, serve):
    """The picker floats from its message corner without moving the thread.

    A reaction list used to add forty pixels to its thread only while open. That moved
    every later message under the pointer and made choosing a reaction change the
    layout being acted on. The next message is the single-factor neighbor: opening the
    picker is the only change between these two frames."""
    url = serve(PANEL_PAGE)
    first = panel_comment(serve.page_dir, "Keep the route visible.")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": first,
            "revision": 1,
            "text": "The route stays beside the choice.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": first,
            "revision": 1,
            "text": "Keep the cap visible too.",
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, first)
    card = view.locator(".lf-msg.agent")
    neighbor = view.locator(".lf-msg").last
    trigger = card.locator(".lf-react-trigger")
    assert trigger.evaluate("b => getComputedStyle(b).backgroundColor") == (
        "rgba(0, 0, 0, 0)"
    )
    trigger.hover()
    # The panel dresses its own presses; under the pointer the trigger takes a face.
    expect(trigger).not_to_have_css("background-color", "rgba(0, 0, 0, 0)")
    before = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }

    trigger.click()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    palette = view.locator(".lf-react-palette")
    expect(palette).to_be_visible()
    after = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }
    assert after == before
    assert palette.bounding_box()["y"] >= (
        trigger.bounding_box()["y"] + trigger.bounding_box()["height"]
    )


def test_a_pages_own_element_rules_leave_the_layers_controls_alone(browser, serve):
    """A page dressing its own `button` and `a` is dressing its prose. The controls a
    widget builds and the chrome's own buttons keep Leaf's face instead: a page's
    element rule once took the family and ink of half corpus.html's widget controls,
    and the family, ink, border and padding of the banner's and thread panel's. An
    explicitly marked stylesheet grants access for deliberate control styling. A face
    set on body reaches prose by inheritance and stops at controls and chrome, which
    state their own."""
    board = (
        '<h1>t</h1><lf-board id="b"><lf-column id="c1" label="To do">'
        '<lf-card id="k1">One</lf-card><lf-card id="k2">Two</lf-card></lf-column>'
        '<lf-column id="c2" label="Done"></lf-column></lf-board>'
        '<p>See <a href="#b">the board</a>.</p>'
        '<style id="body-controls">lf-board button { border-bottom-color: rgb(51, 102, 153); }</style>'
    )
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "t",
                    board,
                    # A selector naming a widget grants no access. Native scope is also
                    # ordinary CSS, not permission to style generated controls.
                    head="<style>button:not(lf-board), a, lf-board .lf-absent { font-family: cursive;"
                    " color: rgb(255, 0, 0); }"
                    "body { font-style: italic; letter-spacing: 3px; }"
                    "@scope (lf-board) { button { background-color: rgb(255, 0, 0); } }"
                    ":root { --control-access-proof: teal; }"
                    "html[data-lf-interactive] p > a { background-color: rgb(1, 2, 3); }"
                    "p > a::before { content: 'Kept'; }"
                    "p { border-top: 7px solid red; }</style>"
                    "<style data-controls>"
                    ":nth-child(1 of lf-board) button { outline: 3px solid rgb(0, 128, 0); }"
                    "</style>",
                )
            )
        ),
    )
    faces = page.evaluate("""() => {
        const adopted = new CSSStyleSheet();
        adopted.replaceSync('p { border-top-color: rgb(0, 0, 255); }');
        document.adoptedStyleSheets = [...document.adoptedStyleSheets, adopted];
        const face = el => { const cs = getComputedStyle(el);
            return [el.className, cs.fontFamily, cs.color, cs.fontStyle, cs.letterSpacing,
                    cs.outlineColor]; };
        return {
            controls: [...document.querySelectorAll('main button.lf-ui')].map(face),
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(face),
            prose: face(document.querySelector('main p > a')),
            rootToken: getComputedStyle(document.documentElement)
                .getPropertyValue('--control-access-proof').trim(),
            ancestor: getComputedStyle(document.querySelector('main p > a')).backgroundColor,
            pseudo: getComputedStyle(document.querySelector('main p > a'), '::before').content,
            adopted: getComputedStyle(document.querySelector('main p')).borderTopColor,
            controlBackgrounds: [...document.querySelectorAll('main button.lf-ui')].map(
                el => getComputedStyle(el).backgroundColor),
        };
    }""")
    assert faces["rootToken"] == "teal", faces
    assert faces["ancestor"] == "rgb(1, 2, 3)", faces
    assert faces["pseudo"] == '"Kept"', faces
    assert faces["adopted"] == "rgb(0, 0, 255)", faces
    assert "rgb(255, 0, 0)" not in faces["controlBackgrounds"], faces
    # The control: the page's rules reach the page's own link, by selector and by
    # inheritance.
    assert faces["prose"][1:5] == ["cursive", "rgb(255, 0, 0)", "italic", "3px"], faces[
        "prose"
    ]
    assert faces["controls"], "the board built no control to read"
    assert faces["chrome"], "the chrome built no button to read"
    reached = [
        face
        for face in faces["controls"] + faces["chrome"]
        if "cursive" in face[1]
        or face[2] == "rgb(255, 0, 0)"
        or face[3] == "italic"
        or face[4] == "3px"
    ]
    assert not reached, reached
    # The marked sheet selects the board using native nth-child selector grammar.
    assert {face[5] for face in faces["controls"]} == {"rgb(0, 128, 0)"}, faces[
        "controls"
    ]
    source = (serve.page_dir / "index.html").read_text()
    stamp_page(
        serve.page_dir,
        source.replace(
            '<style id="body-controls">', '<style id="body-controls" data-controls>'
        ),
        "Grant the body stylesheet control access",
    )
    wait_for_revision(page, 2)
    expect(page.locator("lf-board button.lf-ui").first).to_have_css(
        "border-bottom-color", "rgb(51, 102, 153)"
    )

    stamp_page(serve.page_dir, source, "Withdraw body stylesheet control access")
    wait_for_revision(page, 3)
    expect(page.locator("lf-board button.lf-ui").first).not_to_have_css(
        "border-bottom-color", "rgb(51, 102, 153)"
    )


def test_a_sheet_a_page_script_writes_later_leaves_the_layers_controls_alone(
    browser, serve
):
    """A CSS framework such as Tailwind builds its sheet in the head after the page
    loads and rewrites it as classes change, and each rewrite is a new sheet. Its
    element rules reach the page's prose and stop at Leaf's controls, as the page's
    own stylesheet's do: Tailwind's reset once took the family of every chrome
    button."""
    url = serve(
        leaf_page(
            "t",
            '<h1>t</h1><p>See <a id="prose" href="#t">the link</a>.</p>',
            head="""<style>@import url("page/author.css");</style>
<link rel="stylesheet" data-controls href="page/controls.css">
<script type="module">
const sheet = document.createElement("style");
document.head.append(sheet);
sheet.textContent = "button, a { font-family: fantasy; }";
setTimeout(() => {
  sheet.textContent = "button, a { font-family: cursive; }";
  window.rewritten = true;
}, 50);
</script>""",
        ),
        page_files={
            "author.css": "a { border-top: 7px solid red; } button { border-top: 77px solid red; }",
            "controls.css": '@import url("controls-import.css");',
            "controls-import.css": ".lf-chrome button { outline-color: rgb(0, 128, 0); }",
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => window.rewritten")
    faces = page.evaluate("""() => {
        const family = el => getComputedStyle(el).fontFamily;
        return {
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(family),
            prose: family(document.getElementById('prose')),
            imported: getComputedStyle(document.getElementById('prose')).borderTopWidth,
            chromeBorders: [...document.querySelectorAll('.lf-chrome button')].map(
                el => getComputedStyle(el).borderTopWidth),
            chromeOutlines: [...document.querySelectorAll('.lf-chrome button')].map(
                el => getComputedStyle(el).outlineColor),
        };
    }""")
    assert set(faces["chromeOutlines"]) == {"rgb(0, 128, 0)"}, faces
    assert faces["prose"] == "cursive", faces
    assert faces["imported"] == "7px", faces
    assert "77px" not in faces["chromeBorders"], faces
    assert faces["chrome"], "the chrome built no button to read"
    assert not [f for f in faces["chrome"] if f in {"cursive", "fantasy"}], faces


def test_the_chromes_adopted_sheets_stay_whole_where_style_sheets_lists_them(
    browser, serve
):
    """iOS WebKit lists adopted sheets in `document.styleSheets`, where the other
    engines leave them out. The chrome's own sheets are adopted, so narrowing page CSS
    by walking that list once took every chrome rule off the chrome on iPhones: the
    panel lost its face and its motion timings, and each animation threw."""
    url = serve(leaf_page("t", "<h1>t</h1><p>Body.</p>"))
    page = open_page(
        browser,
        live_url(url),
        init_script="""{
          const listed = Object.getOwnPropertyDescriptor(Document.prototype, "styleSheets").get;
          Object.defineProperty(Document.prototype, "styleSheets", {
            configurable: true,
            get() { return [...listed.call(this), ...this.adoptedStyleSheets]; },
          });
        }""",
    )
    # A sheet a page script writes later sends the narrowing over the list again.
    page.evaluate(
        "() => document.head.append(Object.assign(document.createElement('style'),"
        " {textContent: 'p { color: inherit; }'}))"
    )
    # The panel's own sheet declares its fold's duration on it (floating-panel.css).
    fold = page.locator(".lf-floating-panel").evaluate(
        "el => getComputedStyle(el).getPropertyValue('--lf-motion-panel-fold')"
    )
    assert fold.endswith("ms"), fold


def test_a_theme_package_styles_every_page_as_the_pages_own_sheet_does_one(
    browser, serve, tmp_path
):
    """A theme contribution, even beside a widget, outranks the Layouts and
    every widget package's defaults (layer.py, `lf-theme`), so its `main` padding beats
    the column Layout's and its plain `lf-card` rule beats the board's own `lf-card`
    rule. Like the page's own rules, its bare `button` dresses the
    page's buttons and leaves the controls the board builds alone. A separate controls.css
    sheet grants deliberate access to board controls (runtime/page-sheets.js)."""
    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "registry.json").write_text(
        json.dumps(
            {
                "lf-theme-box": {
                    "description": "A widget beside a page-wide theme.",
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                    "x-content": "markup",
                    "x-upgrade": False,
                }
            }
        )
    )
    (theme / "theme.css").write_text(
        "main { padding-top: 11px; }\n"
        "lf-card { padding-left: 13px; }\n"
        "button { font-family: cursive; }\n"
    )
    (theme / "controls.css").write_text(
        "lf-board button { outline: 3px solid rgb(0, 128, 0); }\n"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "t",
                '<h1>t</h1><p><button id="own" type="button">Own</button></p>'
                '<lf-board id="b"><lf-column id="c1" label="To do">'
                '<lf-card id="k1">One</lf-card></lf-column></lf-board>',
            ),
            packages=("./theme",),
        ),
    )
    faces = page.evaluate("""() => {
        const cs = el => getComputedStyle(el);
        return {
            main: cs(document.querySelector('main')).paddingTop,
            card: cs(document.getElementById('k1')).paddingLeft,
            own: cs(document.getElementById('own')).fontFamily,
            controls: [...document.querySelectorAll('lf-board button.lf-ui')].map(
                el => [cs(el).fontFamily, cs(el).outlineColor]),
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(
                el => cs(el).fontFamily),
        };
    }""")
    assert faces["main"] == "11px", faces
    assert faces["card"] == "13px", faces
    assert faces["own"] == "cursive", faces
    assert faces["controls"], "the board built no control to read"
    assert faces["chrome"], "the chrome built no button to read"
    assert not [f for f, _ in faces["controls"] if "cursive" in f], faces
    assert not [f for f in faces["chrome"] if "cursive" in f], faces
    assert {color for _, color in faces["controls"]} == {"rgb(0, 128, 0)"}, faces


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_a_packages_shadow_rules_reach_only_trees_its_widgets_host(
    request, serve, tmp_path, engine
):
    """Every declared shadow tree receives the layer's composed shadow sheet in every
    engine, so a package's `widget-shadow.css` rule naming its host, `:host(lf-own-tree)
    span`, dresses that widget's tree and not another package's. Each engine reads the
    composed sheet itself: Firefox once applied none of a generated `:host` scope."""
    own, own_module = _shadow_tree_widget("lf-own-tree")
    other, other_module = _shadow_tree_widget("lf-other-tree")
    project = tmp_path / ".leaf"
    project.mkdir()
    (project / "widget-shadow.css").write_text(
        ":host(lf-own-tree) span { color: rgb(0, 128, 0); }\n"
    )
    neighbour = tmp_path / "other"
    (neighbour / "widgets").mkdir(parents=True)
    (neighbour / "registry.json").write_text(json.dumps({"lf-other-tree": other}))
    (neighbour / "widgets" / "lf-other-tree.js").write_text(other_module)
    url = serve(
        leaf_page(
            "t",
            '<h1>t</h1><lf-own-tree id="own"></lf-own-tree>'
            '<lf-other-tree id="other"></lf-other-tree>',
        ),
        packages=("./other",),
        layer_registry={"lf-own-tree": own},
        layer_widgets={"lf-own-tree.js": own_module},
    )
    page = open_page(request.getfixturevalue(engine), url)
    colors = page.evaluate("""() => Object.fromEntries(['own', 'other'].map(id => [id,
        getComputedStyle(document.getElementById(id).shadowRoot.querySelector('span'))
            .color]))""")
    assert colors["own"] == "rgb(0, 128, 0)", colors
    assert colors["other"] != "rgb(0, 128, 0)", colors


def test_a_coined_class_cannot_reach_the_chromes_rules(browser, serve):
    """The chrome's private rules live in one @scope block rooted at the runtime's
    own container, so whatever name a widget or a page coins, it matches none of
    them: lf-tabs once marked itself lf-live — the chrome's name for its
    visually-hidden live region — and every tabbed page clipped to a pixel. An
    element in the page wearing every private class at once must render exactly as
    its unclassed twin.

    The chrome sheet reaches the page only through the classes its owner declares
    shared (`chromeSharedClasses`, runtime/stylesheets.js): a rule written outside the
    block that names any other class is a private rule leaking out, not a widening.
    Those classes, and the faces the authored theme states for a private name at
    document level, stay off the probe, since the movement their rules cause is the
    reach they were given on purpose."""
    page = open_page(
        browser,
        serve(leaf_page("t", "<h1>t</h1><section id=s><p>words</p></section>")),
    )
    surface = page.evaluate("""async () => {
        const {chromeSheet: sheet, chromeSharedClasses: declared} =
            await window.__lfCheckApi();
        const classes = sel => [...(sel || "").matchAll(/\\.([A-Za-z0-9_-]+)/g)].map(m => m[1]);
        const scoped = new Set(), unscoped = new Set(), themed = new Set();
        const collect = (rules, into, privateRules = null) => { for (const r of rules) {
            if (r instanceof CSSScopeRule) {
                if (privateRules) collect(r.cssRules, privateRules, privateRules);
            }
            else if (r.selectorText) classes(r.selectorText).forEach(c => into.add(c));
            else if (r.cssRules) collect(r.cssRules, into, privateRules); } };
        collect(sheet.cssRules, unscoped, scoped);
        for (const other of [...document.styleSheets, ...document.adoptedStyleSheets]
                 .filter(s => s !== sheet))
            collect(other.cssRules, themed);
        const probe = document.createElement("div"), plain = document.createElement("div");
        const worn = [...scoped].filter(c => !declared.includes(c) && !themed.has(c));
        probe.className = worn.join(" ");
        probe.textContent = plain.textContent = "probe";
        // A block after both, so neither twin stands at the section's edge, where the
        // theme trims a margin whichever classes it wears.
        const after = document.createElement("p");
        after.textContent = "after";
        document.getElementById("s").append(plain, probe, after);
        const cs = el => { const c = getComputedStyle(el), out = {};
                           for (const p of c) out[p] = c.getPropertyValue(p); return out; };
        const a = cs(probe), b = cs(plain);
        const body = document.createElement("div");
        body.className = "lf-msg-body";
        body.textContent = "Authored thread words";
        document.getElementById("s").append(body);
        return { worn, unscoped: [...unscoped], declared: [...declared],
                 moved: Object.keys(a).filter(p => a[p] !== b[p]),
                 bodySelection: getComputedStyle(body).userSelect,
                 plainSelection: getComputedStyle(plain).userSelect };
    }""")
    unscoped, declared = set(surface["unscoped"]), set(surface["declared"])
    assert not unscoped - declared, (
        "chrome rules outside its @scope block name classes the sheet does not declare "
        f"shared, so a page element wearing one meets them: {sorted(unscoped - declared)}"
        " — move the rule into the block, or add the class to chromeSharedClasses"
    )
    assert not declared - unscoped, (
        "chromeSharedClasses declares classes no rule outside the @scope block names: "
        f"{sorted(declared - unscoped)}"
    )
    assert surface["worn"], (
        "the probe wears no private class — the @scope block is missing or empty, so "
        "this compares two unclassed twins"
    )
    assert surface["moved"] == [], (
        f"scoped chrome rules reached an element in the page: {surface['moved']}"
    )
    # The shared message body gets selectable-island rules only inside chrome.
    # Its authored copy keeps the document's selection behavior.
    assert surface["bodySelection"] == surface["plainSelection"]


# Whose name the card's top row shows, and who wrote the words just under it. The row
# is the first name painted in the card: where the top falls in the gap before a
# message, a pushed-off head leaves only its blank foot above that message's name.
CARD_TOP_AUTHORS = """transcript => {
  const box = transcript.getBoundingClientRect();
  const x = box.left + 30;
  const messages = [...transcript.querySelectorAll('.lf-msg')];
  const shown = message => {
    const name = message.querySelector(':scope > .lf-msg-head b').getBoundingClientRect();
    const y = name.top + name.height / 2;
    return y > box.top && y < box.bottom
      && document.elementFromPoint(name.left + 1, y)?.closest('.lf-msg') === message;
  };
  const named = messages.find(shown);
  const head = named?.querySelector(':scope > .lf-msg-head').getBoundingClientRect();
  const sampleY = (head?.bottom ?? box.top) + 6;
  const under = document.elementFromPoint(x, sampleY)
    ?.closest('.lf-msg');
  const next = messages[messages.indexOf(named) + 1];
  const endGap = named && next &&
    named.getBoundingClientRect().bottom <= head.bottom + 0.5 &&
    next.getBoundingClientRect().top > sampleY && shown(next);
  return {named: messages.indexOf(named), under: messages.indexOf(under),
          endGap,
          row: head ? head.top - box.top < head.height : false,
          scrolled: transcript.scrollTop > 0};
}"""


def test_the_thread_card_opens_on_its_latest_message_under_its_own_name(browser, serve):
    """A card opened on a long thread shows its latest message, as a walk to it in the
    Threads list does, and its top row names whoever wrote the words under it. The
    card pinned the root's name beside its actions, so it opened at the top to keep
    that name true, leaving the newest turn out of view. A continuation fades the
    words below the moving name without fading the next message's author."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + LANDING_WORDS, {"section": "how-store"}
    )
    for turn in range(1, 12):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 else "user",
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    selector = (
        f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'
        " > .lf-thread-transcript"
    )
    transcript = page.locator(selector)
    expect(transcript).to_be_visible()
    rendered(page)
    scroll_settled(page, selector)
    assert transcript.evaluate("box => box.scrollHeight > box.clientHeight")
    latest = transcript.locator(".lf-msg").last.bounding_box()
    shown = transcript.bounding_box()
    assert latest["y"] + latest["height"] <= shown["y"] + shown["height"] + 1
    landed = transcript.evaluate(CARD_TOP_AUTHORS)
    assert landed["scrolled"] and landed["named"] > 0 and landed["row"], landed
    # At the scroll limit a sliver of the previous author can precede a clear gap,
    # with the next turn's own visible name below it (the known edge from #1763).
    assert landed["under"] == landed["named"] or (
        landed["under"] == -1 and landed["endGap"]
    ), landed
    assert not transcript.evaluate("box => box.hasAttribute('data-lf-more-below')")

    def continuation():
        """Read the fade's actual painted box, including its grid positioning."""
        reading = transcript.evaluate(
            """box => {
              const style = getComputedStyle(box.parentElement, '::after');
              return {height: parseFloat(style.height), display: style.display,
                paint: style.backgroundImage,
                heads: [...box.querySelectorAll('.lf-msg-head')]
                  .map(head => head.getBoundingClientRect().toJSON()),
                top: box.getBoundingClientRect().top + box.clientTop
                  + parseFloat(getComputedStyle(box).getPropertyValue('--lf-top'))};
            }"""
        )
        cdp = page.context.new_cdp_session(page)
        try:
            card = cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelector({json.dumps(selector)}).parentElement"
                },
            )["result"]["objectId"]
            described = cdp.send("DOM.describeNode", {"objectId": card})["node"]
            pseudo = next(
                node
                for node in described["pseudoElements"]
                if node["pseudoType"] == "after"
            )
            border = cdp.send(
                "DOM.getBoxModel", {"backendNodeId": pseudo["backendNodeId"]}
            )["model"]["border"]
            reading.update(fade_top=min(border[1::2]), fade_bottom=max(border[1::2]))
        finally:
            cdp.detach()
        return reading

    # Reading back up, the row names each message whose words stand under it.
    for index in (3, 2, 1, 0):
        transcript.evaluate(
            """(box, index) => {
              const message = box.querySelectorAll('.lf-msg')[index];
              const offset = message.getBoundingClientRect().top
                - box.getBoundingClientRect().top;
              // The message's middle stands just under the row.
              box.scrollTop += index
                ? offset + message.offsetHeight / 2 - 30
                : -box.scrollTop;
            }""",
            index,
        )
        rendered(page)
        reading = transcript.evaluate(CARD_TOP_AUTHORS)
        assert reading["named"] == reading["under"] == index and reading["row"], reading
        cue = continuation()
        if index:
            assert cue["display"] != "none" and cue["height"] > 0, cue
            assert "gradient" in cue["paint"], cue
            assert cue["fade_top"] == pytest.approx(
                cue["heads"][index]["bottom"], abs=1
            ), cue
        else:
            assert cue["height"] == 0, cue

    # Follow the outgoing header as the next author pushes it off the top, then
    # follow the transcript edge through the gap. Neither position fades a name.
    for handoff in ("pushed", "gap"):
        transcript.evaluate(
            """(box, handoff) => {
              const messages = [...box.querySelectorAll('.lf-msg')];
              const first = messages[0].getBoundingClientRect();
              const head = messages[0].querySelector('.lf-msg-head').getBoundingClientRect();
              const next = messages[1].querySelector('.lf-msg-head').getBoundingClientRect();
              const target = handoff === 'pushed'
                ? first.bottom - head.height / 2
                : (first.bottom + next.top) / 2;
              box.scrollTop += target - box.getBoundingClientRect().top - box.clientTop;
            }""",
            handoff,
        )
        rendered(page)
        cue = continuation()
        assert cue["display"] != "none" and cue["height"] > 0, cue
        if handoff == "pushed":
            assert cue["heads"][0]["top"] < cue["top"] < cue["heads"][0]["bottom"], cue
            assert cue["fade_top"] == pytest.approx(cue["heads"][0]["bottom"], abs=1), (
                cue
            )
        else:
            assert cue["heads"][0]["bottom"] <= cue["top"], cue
            assert cue["fade_top"] == pytest.approx(cue["top"], abs=1), cue
        assert cue["fade_bottom"] <= cue["heads"][1]["top"] + 1, cue


@pytest.mark.parametrize("forced", [False, True])
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_scrolled_past_a_card_head_show_nowhere_above_it(
    engine, forced, request, serve
):
    """Wherever the card's transcript is scrolled, its stuck head stands on the line
    of the card's actions, and the focus-ring room above that line shows no words,
    in forced colours too, which drop shadows. Firefox stuck a head at its subgrid
    scroller's edge, past the room, so the name stood 6px above the actions and words
    showed over Resolve; in Chromium they showed above the name."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + LANDING_WORDS, {"section": "how-store"}
    )
    for turn in range(1, 8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 else "user",
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1200, 600)
    if forced:
        page.emulate_media(forced_colors="active")
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    transcript = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'
        " > .lf-thread-transcript"
    )
    expect(transcript).to_be_visible()
    rendered(page)
    travel = transcript.evaluate("box => box.scrollHeight - box.clientHeight")
    # Through the first messages, including where one pushes the last one's head off.
    assert travel > 300, travel
    for scroll in range(0, 300, 7):
        transcript.evaluate("(box, y) => { box.scrollTop = y; }", scroll)
        rendered(page)
        reading = transcript.evaluate(
            """box => {
              const controls = box.parentElement
                .querySelector(':scope > .lf-margin-thread-controls');
              const edge = box.getBoundingClientRect().top + box.clientTop;
              const head = [...box.querySelectorAll('.lf-msg-head')]
                .find(head => head.getBoundingClientRect().bottom > edge + 1);
              const at = head.getBoundingClientRect();
              const card = box.parentElement.getBoundingClientRect();
              return {edge, head: at.top, left: card.left, right: card.right,
                pushed: at.bottom >= head.parentElement.getBoundingClientRect().bottom - 1,
                line: controls.getBoundingClientRect().top
                  + parseFloat(getComputedStyle(controls).paddingTop),
                // The focus-ring room, which the transcript's landings also keep.
                ring: parseFloat(getComputedStyle(box).scrollPaddingTop)};
            }"""
        )
        # A head the next message pushes off rises with it; every other stands on the
        # actions' line or below it.
        assert reading["pushed"] or reading["head"] >= reading["line"] - 0.5, (
            scroll,
            reading,
        )
        assert reading["line"] - reading["edge"] >= reading["ring"], reading
        room = min(reading["line"], reading["head"]) - reading["edge"]
        if room < 1:
            continue
        band = Image.open(
            io.BytesIO(
                page.screenshot(
                    clip={
                        "x": reading["left"],
                        "y": reading["edge"],
                        "width": reading["right"] - reading["left"],
                        "height": room,
                    }
                )
            )
        ).convert("L")
        assert band.getextrema()[1] - band.getextrema()[0] < 40, (scroll, reading)


@pytest.mark.parametrize(("width", "touch"), [(1200, False), (311, True)])
def test_a_stuck_card_head_keeps_the_name_and_lets_its_annotations_scroll_out(
    browser, serve, width, touch
):
    """Reading down a long reply keeps its writer and time at the top while the
    edited annotation leaves with the reply's first line."""
    url = serve(PANEL_PAGE)
    # Asked an hour before the answer, so the answer's head says an age of its own.
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Explain with examples?",
            "anchor": {"section": "how-store"},
            "ts": (datetime.now().astimezone() - timedelta(hours=1)).isoformat(),
        },
    )["id"]
    answer = thread_model.post_reply(
        serve.page_dir, {"responds": root}, LANDING_WORDS * 8
    )["id"]
    thread_model.cmd_edit(serve.page_dir, answer, "Edited. " + LANDING_WORDS * 8)
    # Later turns leave room to scroll the answer past the top in either direction.
    for turn, author in enumerate(("user", "agent")):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": author,
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS * 4,
            },
        )
    context = browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, url, context=context)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    selector = (
        f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]'
        " > .lf-thread-transcript"
    )
    transcript = page.locator(selector)
    expect(transcript).to_be_visible()
    rendered(page)
    scroll_settled(page, selector)
    message = transcript.locator(f'.lf-msg[data-event="{answer}"]')
    expect(message.locator(".lf-edited")).to_be_visible()

    def scrolled_past(distance):
        """Each part's top against the transcript's, once the answer's opening stands
        `distance` pixels above it and a rendering update has moved what scroll moves,
        and what the user sees at the name's middle."""
        transcript.evaluate(
            """(box, [selector, distance]) => {
              const message = box.querySelector(selector);
              box.scrollTop += message.getBoundingClientRect().top
                - box.getBoundingClientRect().top + distance;
            }""",
            [f'.lf-msg[data-event="{answer}"]', distance],
        )
        rendered(page)
        return transcript.evaluate(
            """(box, selector) => {
              const message = box.querySelector(selector);
              const head = message.querySelector(':scope > .lf-msg-head');
              const name = head.querySelector('b');
              const from = box.getBoundingClientRect().top;
              const top = node => node.getBoundingClientRect().top - from;
              const at = name.getBoundingClientRect();
              const time = head.querySelector('time');
              const middle = at.top + at.height / 2;
              // The name itself, and the gap between it and the time.
              const seen = [at.left + 4, time.getBoundingClientRect().left - 4]
                .map(x => document.elementFromPoint(x, middle));
              return {message: top(message), name: top(name),
                      time: top(time),
                      edited: top(head.querySelector('.lf-edited')),
                      editedBottom: head.querySelector('.lf-edited').getBoundingClientRect().bottom - from,
                      nameShown: seen.every(node => name.contains(node)),
                      head: head.offsetHeight};
            }""",
            f'.lf-msg[data-event="{answer}"]',
        )

    rest = scrolled_past(0)
    assert abs(rest["message"]) <= 1, rest
    for distance in (6, 12, 20, 30):
        reading = scrolled_past(distance)
        assert abs(reading["message"] + distance) <= 1, reading
        # The name and time stay where they stood and stay on top; the annotations
        # move with the words.
        assert abs(reading["name"] - rest["name"]) <= 1, (rest, reading)
        assert abs(reading["time"] - rest["time"]) <= 1, (rest, reading)
        assert reading["nameShown"], reading
        moved = reading["edited"] - (rest["edited"] - distance)
        assert abs(moved) <= 1, (rest, reading)
    gone = scrolled_past(2 * rest["head"])
    assert abs(gone["name"] - rest["name"]) <= 1, (rest, gone)
    assert gone["editedBottom"] <= 0, gone


@pytest.mark.parametrize("scaled", [False, True])
def test_a_short_window_keeps_media_choices_and_send_around_the_scrolling_draft(
    browser, serve, scaled
):
    """A whole-frame cap reserves the choices and Send before text scrolls; the attached
    image hangs outside the frame (annotation-chrome.css)."""
    source = LONG_PAGE
    if scaled:
        source = source.replace(
            "</head>",
            """<style>
              div.lf-chrome { position:fixed; inset:0; pointer-events:none;
                transform:scale(1.2); transform-origin:0 0; }
              .lf-fab-bar, .lf-margin-preview { zoom:1.2; }
            </style></head>""",
        )
    page = open_page(browser, serve(source))
    width, height = (315, 450) if scaled else (390, 300)
    resized(page, width, height)
    page.locator("#p1").click(click_count=3)
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    expect(bar.locator(".lf-composer-media img")).to_be_visible()
    content = "\n".join(
        f"Line {n}: the draft shares room with its picture and response choices."
        for n in range(80)
    )
    write(field, content)
    field.press("Tab")
    expect(bar.locator(".lf-react:visible")).to_have_count(6)
    rendered(page)
    expect(field).to_have_js_property("value", content)
    assert field.evaluate("el => el.scrollHeight > el.clientHeight")
    bounds = bar.evaluate("el => el.getBoundingClientRect().toJSON()")
    assert bounds["top"] >= 6
    assert bounds["bottom"] <= height - 8
    parts = bar.locator(
        ".lf-compose-field, .lf-fab-input, .lf-compose-submit, "
        ".lf-response-options, .lf-response-action:visible"
    ).evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().toJSON())")
    for part in parts:
        assert bounds["left"] <= part["left"] < part["right"] <= bounds["right"], (
            bounds,
            parts,
        )
        assert bounds["top"] <= part["top"] < part["bottom"] <= bounds["bottom"], (
            bounds,
            parts,
        )
    resized(page, width, 120)
    expect(bar).to_be_hidden()
    resized(page, width, height)
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", content)
    expect(bar.locator(".lf-composer-media img")).to_be_visible()
    expect(bar.locator(".lf-react:visible")).to_have_count(6)


def test_a_zoomed_window_places_floating_surfaces_by_their_held_edges(browser, serve):
    """Held insets use the surface's units in both window and element blocks."""
    page = open_page(browser, serve(leaf_page("Placement", "<p>Reference</p>")))
    resized(page, 605, 898)
    readings = page.evaluate(
        """async () => {
          document.documentElement.style.zoom = '1.25';
          const {floatingPlacement, floatingUi} = await window.__lfOverlayApi();
          const {computePosition, shift} = await floatingUi();
          const readings = [];
          for (const [transform, border] of [
            ['none', 0], ['scale(1.2,0.8)', 0], ['scale(1.2,0.8)', 8],
          ]) {
            const holder = document.createElement('div');
            holder.style.cssText = 'position:fixed;left:10px;top:20px;width:500px;height:600px;'
              + `transform:${transform};transform-origin:0 0;border:${border}px solid transparent`;
            document.body.append(holder);
            for (const left of [200, 440]) {
              const reference = document.createElement('div');
              reference.style.cssText = `position:fixed;left:${left}px;top:200px;width:20px;height:20px`;
              holder.append(reference);
              for (const zoom of [1, 1.2]) {
                const floating = document.createElement('div');
                floating.style.cssText = `position:fixed;width:100px;height:50px;zoom:${zoom}`;
                holder.append(floating);
                const driver = floatingPlacement({floating, update() {}});
                const answer = await driver.position(computePosition, reference,
                  {placement:'top-end', middleware:[shift({
                    boundary:[], rootBoundary:new DOMRect(8,8,589,882), padding:0,
                  })]}, () => 'window', reference);
                driver.stand(answer);
                await new Promise(requestAnimationFrame);
                const target = reference.getBoundingClientRect();
                const actual = floating.getBoundingClientRect();
                readings.push({transform, border, left, zoom, right:actual.right, bottom:actual.bottom,
                  targetRight:Math.min(target.right,597), targetTop:target.top});
                driver.stop();
                floating.remove();
              }
              reference.remove();
            }
            holder.remove();
          }
          return readings;
        }"""
    )
    for reading in readings:
        assert reading["right"] == pytest.approx(reading["targetRight"], abs=0.5), (
            reading
        )
        assert reading["bottom"] == pytest.approx(reading["targetTop"], abs=0.5), (
            reading
        )


@pytest.mark.parametrize("surface", ["card", "composer"])
def test_a_dropped_surface_keeps_its_box_until_placement_commits(
    browser, serve, surface
):
    """Release transfers the carried box without a visit to its old placement.

    Firefox drops hover during that visit, then restarts the delayed border tint.
    Read when the carry ends, before asynchronous placement can hide a gap.
    The comment box shares the same handoff even where hover happens to survive.
    """
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Keep this explanation.", {"section": "how-store"})
    page = open_page(browser, url)
    if surface == "card":
        page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
        holder = page.locator(".lf-margin-preview")
        expect(holder).to_have_attribute("data-lf-thread-placement", re.compile(".+"))
    else:
        select_words(page, "#how-cap")
        page.keyboard.press("c")
        holder = page.locator(".lf-fab-bar")
        expect(holder.locator(".lf-fab-input")).to_be_focused()
    grip = holder.locator(":scope > .lf-surface-grip")
    box = grip.bounding_box()
    x, y = box["x"] + 25, box["y"] + (6 if surface == "card" else 2)
    page.mouse.move(x, y)
    page.mouse.down()
    expect(holder).to_have_attribute("data-lf-carried", "")
    page.mouse.move(x - 100, y - 30, steps=6)
    one_frame(page)
    held = holder.bounding_box()
    holder.evaluate(
        """surface => {
          const observer = new MutationObserver(() => {
            if (surface.hasAttribute('data-lf-carried')) return;
            surface.lfDroppedBox = surface.getBoundingClientRect().toJSON();
            observer.disconnect();
          });
          observer.observe(surface, {attributes:true, attributeFilter:['data-lf-carried']});
        }"""
    )
    page.mouse.up()
    released = holder.evaluate("surface => surface.lfDroppedBox")
    assert released is not None, "the release never reached the grip"
    for axis in ("x", "y"):
        assert released[axis] == pytest.approx(held[axis], abs=0.5), (
            f"{surface} returned to its old {axis} at release: {held} -> {released}"
        )
    expect(holder).not_to_have_attribute("data-lf-carried", "")
    landed = holder.bounding_box()
    for axis in ("x", "y"):
        assert landed[axis] == pytest.approx(held[axis], abs=0.5), (held, landed)


@pytest.mark.parametrize(
    ("zoom_home", "width"),
    [("root", 605), ("transformed-holder", 315)],
)
def test_a_zoomed_floating_draft_and_sent_comment_fit_a_narrow_window(
    browser, serve, zoom_home, width
):
    """Root and local zoom keep the draft and sent card in their available room."""
    source = (
        LONG_PAGE
        if zoom_home == "root"
        else leaf_page(
            "Zoomed comments",
            """<style>
              div.lf-chrome { position:fixed; inset:0; pointer-events:none;
                transform:scale(1.2); transform-origin:0 0; }
              .lf-fab-bar, .lf-margin-preview { zoom:1.2; }
            </style>
            <h1>Fictional planning note</h1>
            <p id="p1">We will combine the setup steps into one operation, then
              check the result before continuing.</p>""",
        )
    )
    page = open_page(browser, serve(source))
    resized(page, width, 898)
    if zoom_home == "root":
        page.evaluate("document.documentElement.style.zoom = '1.25'")
    one_frame(page)
    page.locator("#p1").click(click_count=3)
    page.keyboard.press("c")
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_focused()
    content = "better; is there a way of shortening? or maybe we just remove it??"
    page.keyboard.insert_text(content)
    rendered(page)
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", content)
    bounds = bar.bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= width + 0.1, bounds
    for part in bar.locator(
        ".lf-compose-field, .lf-fab-input, .lf-compose-submit"
    ).all():
        box = part.bounding_box()
        assert bounds["x"] <= box["x"] and box["x"] + box["width"] <= (
            bounds["x"] + bounds["width"] + 0.1
        ), (bounds, box)
    with sending(page, "the zoomed narrow-window comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    expect(card.locator(".lf-msg-text").first).to_contain_text(content)
    bounds = card.bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= width + 0.1, bounds
    resized(page, 1440, 900)
    rendered(page)
    text = card.locator(".lf-msg-text").first
    assert text.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


def test_a_scaled_floating_draft_keeps_its_room_when_its_passage_scrolls_away(
    browser, serve
):
    """A scaled draft keeps its allocation and native editor until Resume reveals it."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-fab-bar").evaluate(
        """bar => {
          const holder = document.createElement('div');
          holder.style.cssText = 'position:fixed;inset:0;pointer-events:none;'
            + 'transform:scale(1.2);transform-origin:0 0';
          const home = bar.parentElement;
          home.before(holder); holder.append(home);
        }"""
    )
    resized(page, 390, 620)
    page.locator("#p1").click(click_count=3)
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    content = "\n".join(
        f"Line {n}: every word stays in the scaled editor." for n in range(80)
    )
    write(field, content)
    rendered(page)
    native_field = field.element_handle()
    before = bar.bounding_box()
    scale = bar.evaluate(
        "el => el.getBoundingClientRect().width / parseFloat(getComputedStyle(el).width)"
    )
    assert scale == pytest.approx(1.2, abs=0.001)
    page.mouse.move(20, 100)
    page.mouse.wheel(0, 1000)
    page.wait_for_function(
        "document.querySelector('#p1').getBoundingClientRect().bottom < 0"
    )
    scroll_settled(page)
    resized(page, 390, 600)
    rendered(page)
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", content)
    after = bar.bounding_box()
    assert field.evaluate("(node, original) => node === original", native_field)
    assert after["y"] + after["height"] < 0, after
    assert after["height"] <= before["height"] + 0.1, (before, after)
    assert 8 <= after["x"] and after["x"] + after["width"] <= 382.1, (before, after)
    assert after["width"] <= before["width"] + 0.1, (before, after)

    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    scroll_settled(page)
    rendered(page)
    expect(field).to_have_js_property("value", content)
    assert field.evaluate("(node, original) => node === original", native_field)
    resumed = bar.bounding_box()
    assert 8 <= resumed["x"] and resumed["x"] + resumed["width"] <= 382.1, resumed
    assert 6 <= resumed["y"] + 0.1, resumed
    assert resumed["y"] + resumed["height"] <= 592.1, resumed
