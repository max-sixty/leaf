"""Tests scheduled by the measured cost of their boundary."""

import json
import re

import pytest
from browser.projection.test_widget_actions import thread_head
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record, append_command, trial_family
from playwright.sync_api import expect
from render_cases_interaction import TWO_HOLDER_PAGE
from render_cases_navigation import painted
from render_harness import EXAMPLE_PACKAGES, REPLY_HOST_PAGE, open_page, told

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_slot_naming_two_holders_retires_under_neither_until_decided(
    browser, serve, tmp_path, monkeypatch
):
    """`owners` is a list, and the retired-slot selector is built from it. Written
    `${entry["owners"]}` the list interpolates comma-joined, so a slot naming
    two owners wrote a selector *list* whose first member was the bare owner tag: every
    instance of it read as a retired slot however the log stood, its words silenced from
    the anchor pass, while the pair that was meant matched nothing at all.

    Unreachable until this layer's licensing opened `retired-when` past the
    suggestion family, which is why the shipped vocabulary — every slot of it naming
    one holder — could never have said so. The page holds an undecided trial, so
    nothing here is retired and a quote inside it must anchor like any other."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(
        TWO_HOLDER_PAGE,
        anchored=[("th-now", "warmed on every deploy")],
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = open_page(browser, url)
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(thread_head(page, serve.page_dir)).not_to_have_attribute(
        "data-lf-detached", ""
    )
    assert painted(page, "lf-mark") != "", (
        "the quote found nothing to paint: an undecided holder read as a retired slot, "
        "so the anchor pass skipped every word inside it"
    )


def test_a_settled_holder_in_a_reply_joins_the_panel_wearing_its_mark(
    browser, serve, tmp_path, monkeypatch
):
    """The same mark on a holder an agent sent in a reply. Its markup lives in the
    log, and the thread mounts it after the projection has painted the page, so a
    paint that looks the holder up in the document finds nothing and the reply opens
    with both slots showing. The holder's node exists before either pass, so the mark
    is on it when the thread places it."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    url = serve(REPLY_HOST_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-trial",
            "author": "agent",
            "revision": 1,
            "text": (
                "Should the cache warm lazily?\n\n"
                '<lf-trial id="rq-cache">\n'
                '<lf-current><p id="rq-now">Warm on deploy.</p></lf-current>'
                '<lf-proposed><p id="rq-next">Warm on first request.</p></lf-proposed>'
                "</lf-trial>"
            ),
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "rq-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, "c-trial")
    expect(page.locator("#rq-now")).to_be_visible()
    expect(page.locator("#rq-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#rq-next")).to_be_hidden()


@pytest.mark.parametrize("shadow", [False, True])
def test_withdrawing_a_custom_settlement_clears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch, shadow
):
    """A custom deciding payload can drive a widget's presentation alongside the
    layer's retirement. Undo clears both its presentation and the retired slot."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    holder = declarations["lf-trial"]
    if shadow:
        holder["shadow"] = True
    holder["attributes"]["properties"]["decision"] = {"enum": ["open", "shelved"]}
    holder["attributes"].setdefault("required", []).append("decision")
    holder["example"] = holder["example"].replace(
        'id="trial-cache"', 'id="trial-cache" decision="open"'
    )
    decide = holder["verbs"]["decide"]
    decide["detail"]["properties"]["decision"] = {"enum": ["open", "shelved"]}
    decide["detail"]["required"].append("decision")
    registry_path.write_text(json.dumps(declarations))
    stage = "shadowStage(this, [...this.children]);" if shadow else ""
    if shadow:
        (tmp_path / ".leaf" / "widget-shadow.css").write_text(
            "lf-current, lf-proposed { display: block; }"
        )
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """import { shadowStage } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-trial", class extends LeafElement {
  setup() { STAGE }
  render() { keeps(this, "decision", this.state.decide.detail.decision ?? "open"); }
});
""".replace("STAGE", stage)
    )
    page_html = TWO_HOLDER_PAGE.replace(
        '<lf-trial id="th-cache">', '<lf-trial id="th-cache" decision="open">'
    )
    url = serve(page_html, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    decision = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve", "decision": "shelved"},
        },
    )
    page = open_page(browser, url)
    assert page.locator("#th-cache").evaluate("el => Boolean(el.shadowRoot)") is shadow
    expect(page.locator("#th-cache")).to_have_attribute("decision", "shelved")
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache lf-proposed")).to_have_attribute(
        "data-lf-retired", ""
    )
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()

    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": decision["id"]},
    )
    told(page)
    expect(page.locator("#th-cache")).to_have_attribute("decision", "open")
    expect(page.locator("#th-cache")).not_to_have_attribute(
        "data-lf-state", re.compile(r".+")
    )
    expect(page.locator("#th-cache lf-proposed")).not_to_have_attribute(
        "data-lf-retired", ""
    )
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
