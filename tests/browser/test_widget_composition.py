"""Two packages written apart work together through one contract.

`tests/fixtures/packages/shortlist` owns a recorded answer: it holds its candidates and
picks as its `shortlist` output, a property of its element it says `change` for, and
takes the invoker command `--toggle`. `tests/fixtures/packages/finalists` was written
from the shipped references and the contract's text alone, without the shortlist's
source: it reads whatever its `for` names through an input of that contract and asks
for a drop with the command. Neither names the other's tag, verb or output.

The pair holds on a Leaf page, where the pick is the shortlist's own recorded action
whichever widget the user pressed, so Undo and a revision treat it as one fact, and on
a page without Leaf, where the host binds the property and the browser delivers the
command.
"""

import json
import os
import re

from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, sending, told
from smoke.test_plain_page import ROOT, host_page, install

from leaf import event_log
from leaf.revision_delivery import layer_import_map
from leaf.schema import PLUGIN_ROOT

FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "packages"
SHORTLIST = FIXTURES / "shortlist"
FINALISTS = FIXTURES / "finalists"


def candidate(key: str, name: str) -> str:
    return (
        f'<li><button type="button" commandfor="hires" command="--toggle" '
        f'value="{key}">{name}</button></li>'
    )


def pair(*candidates: tuple[str, str]) -> str:
    rows = "".join(candidate(key, name) for key, name in candidates)
    return (
        f'<lf-shortlist id="hires"><ul>{rows}</ul></lf-shortlist>'
        '<lf-finalists id="finalists" for="hires"></lf-finalists>'
    )


ADA, GRACE, KATHERINE = (
    ("ada", "Ada Lovelace"),
    ("grace", "Grace Hopper"),
    ("katherine", "Katherine Johnson"),
)


def test_a_second_package_edits_the_owner_s_answer_across_undo_and_a_revision(
    browser, serve
):
    url = live_url(
        serve(
            leaf_page("Final round", pair(ADA, GRACE)), packages=(SHORTLIST, FINALISTS)
        )
    )
    page = open_page(browser, url)
    hires, finalists = page.locator("#hires"), page.locator("#finalists")
    pick = lambda name: hires.get_by_role("button", name=name)  # noqa: E731
    drop = lambda name: finalists.get_by_role("button", name=f"Drop {name}")  # noqa: E731

    expect(finalists).to_contain_text("Nobody is picked")
    pick("Ada Lovelace").click()
    pick("Grace Hopper").click()
    expect(drop("Ada Lovelace")).to_be_visible()
    expect(drop("Grace Hopper")).to_be_visible()

    # The other package's control changes the owner's answer, and the owner records it.
    with sending(page, "the drop"):
        drop("Ada Lovelace").click()
    expect(pick("Ada Lovelace")).to_have_attribute("aria-pressed", "false")
    expect(finalists).not_to_contain_text("Ada Lovelace")
    actions = [
        (event["widget"], event["action"], event["detail"])
        for event in event_log.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert actions == [
        ("hires", "pick", {"candidate": "ada", "picked": True}),
        ("hires", "pick", {"candidate": "grace", "picked": True}),
        ("hires", "pick", {"candidate": "ada", "picked": False}),
    ]

    # Undo takes back that one action, wherever it was pressed, and both widgets follow.
    with sending(page, "the undo"):
        page.keyboard.press("z")
    expect(pick("Ada Lovelace")).to_have_attribute("aria-pressed", "true")
    expect(drop("Ada Lovelace")).to_be_visible()

    # A revision replaces the shortlist's element: the picks stand over the new markup,
    # and the finalists, which the revision left alone, read the element now standing.
    before = finalists.element_handle()
    (serve.page_dir / "index.html").write_text(
        leaf_page("Final round", pair(ADA, GRACE, KATHERINE))
    )
    told(page)
    expect(pick("Katherine Johnson")).to_be_visible()
    assert before.evaluate("node => node === document.getElementById('finalists')")
    expect(drop("Ada Lovelace")).to_be_visible()
    expect(drop("Grace Hopper")).to_be_visible()
    pick("Katherine Johnson").click()
    expect(drop("Katherine Johnson")).to_be_visible()
    drop("Grace Hopper").click()
    expect(pick("Grace Hopper")).to_have_attribute("aria-pressed", "false")


def test_the_same_two_modules_work_on_a_page_without_leaf(browser, monkeypatch):
    monkeypatch.chdir(PLUGIN_ROOT)
    packages = [f"./{os.path.relpath(package)}" for package in (SHORTLIST, FINALISTS)]
    markup = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Final round</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
</head><body>{pair(ADA, GRACE)}
<script type="module">
  // The host binds what Leaf would: the reader's input to the value its `for` holds.
  const hires = document.querySelector("#hires");
  const finalists = document.querySelector("#finalists");
  hires.addEventListener("change", () => (finalists.value = hires.shortlist));
  finalists.value = hires.shortlist;
</script>
<script type="module" src="{ROOT}/widgets/lf-finalists.js"></script>
<script type="module" src="{ROOT}/widgets/lf-shortlist.js"></script>
</body></html>"""
    with host_page(markup, install(*packages)) as url:
        page = browser.new_page()
        page.goto(url)
        assert page.evaluate("() => !window.lfRootState"), "no Leaf runtime runs here"
        hires, finalists = page.locator("#hires"), page.locator("#finalists")
        expect(finalists).to_contain_text("Nobody is picked")
        hires.get_by_role("button", name="Grace Hopper").click()
        drop = finalists.get_by_role("button", name=re.compile("Drop Grace Hopper"))
        expect(drop).to_be_visible()
        # The reader loaded first and still drew the value the owner held later.
        drop.click()
        expect(finalists).to_contain_text("Nobody is picked")
        expect(hires.get_by_role("button", name="Grace Hopper")).to_have_attribute(
            "aria-pressed", "false"
        )
