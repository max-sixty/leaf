"""What the margin says about agent work and receipts: tone, claims, acknowledgments,
whose turn a thread is, and where a status traces."""

import re
from datetime import datetime, timedelta

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from interact_support import append_carried_log_record, declare_idle, record_claim
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, PANEL_PAGE, live_url
from render_cases_layout import token_colour
from render_cases_navigation import go_to_address
from render_cases_widgets import (
    GENERIC_VISUAL_LAYER,
    GENERIC_VISUAL_PAGE,
    GENERIC_VISUAL_WIDGETS,
)
from render_harness import (
    BOARD_PAGE,
    leaf_page,
    margins_laid_out,
    open_page,
    panel_settled,
    panel_view,
    resized,
    select,
    sending,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.margin import (
    COMMENT_ON_OBLIGATION,
    leave_card_by_its_target,
)
from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf.served_state import context as served_context

pytestmark = pytest.mark.shifts_unsurveyed


RECEIPT_PHASES = {
    "Saved": "sent",
    "Haven't seen it yet": "waiting",
    "Got it": "pickup",
}


UNID_SELECTION_PAGE = PANEL_PAGE.replace('<p id="how-cap">', "<p>")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_margin_entry_tone_stays_distinct_from_control_and_agent_state(
    browser, serve, scheme
):
    """Tone keeps its meaning through interaction and agent-workflow states."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "margin entry tones",
                '<p id="neutral-target">Neutral target</p>'
                '<p id="positive-target">Positive target</p>'
                '<p id="negative-target">Negative target</p>',
            )
        ),
    )
    page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const tones = ['neutral', 'positive', 'negative'];
          let currentState = 'idle';
          let stage = null;
          const registrations = tones.map((tone, index) =>
            registerContribution({
              key: `tone-${tone}`, target: document.querySelector(`#${tone}-target`),
              read: () => ({entries: [contributionEntry({
                key: tone, icon: 'check', label: tone, tone, state: currentState,
                disabled: currentState === 'busy', workflowReceipt: stage ? {
                  id: `tone-${index}`,
                  subject: {kind: 'widget', id: `${tone}-target`},
                  stage,
                  condition: null,
                } : null
              })]}), activate: () => {}
            })
          );
          window.setToneState = state => {
            currentState = state;
            registrations.forEach(registration => registration.update({immediate: true}));
          };
          window.setToneReceiptPhase = next => {
            stage = next;
            registrations.forEach(registration => registration.update({immediate: true}));
          };
        }"""
    )
    buttons = [
        page.get_by_role("button", name=tone, exact=True)
        for tone in ("neutral", "positive", "negative")
    ]
    read = """button => {
      const face = getComputedStyle(button);
      const mark = getComputedStyle(button, '::after');
      return {
        shell: [face.color, face.borderTopColor, face.backgroundColor,
                face.outlineColor, face.outlineStyle, face.outlineWidth],
        mark: mark.content === 'none' ? null :
          [mark.color, mark.borderTopColor, mark.backgroundColor],
        shape: [face.borderTopStyle, face.borderRightStyle,
                face.borderBottomStyle, face.borderLeftStyle],
        animation: face.animationName,
        icon: getComputedStyle(button.querySelector('svg')).color,
        opacity: face.opacity,
      };
    }"""

    def assert_icon_only(readings):
        assert readings[0]["shell"] == readings[1]["shell"] == readings[2]["shell"]
        assert readings[0]["mark"] == readings[1]["mark"] == readings[2]["mark"]
        assert len({reading["icon"] for reading in readings}) == 3

    for state in ("idle", "engaged", "busy", "failed"):
        page.evaluate("state => window.setToneState(state)", state)
        for button in buttons:
            expect(button).to_have_attribute("data-lf-state", state)
            expect(button).to_have_css("opacity", "0.5" if state == "busy" else "1")
        readings = [button.evaluate(read) for button in buttons]
        assert all(reading["mark"] is None for reading in readings)
        assert [reading["shape"] for reading in readings] == [["solid"] * 4] * len(
            buttons
        )
        animation = "lf-runtime-4f3c2a8d-working" if state == "busy" else "none"
        assert all(reading["animation"] == animation for reading in readings)
        assert_icon_only(readings)

    page.evaluate("() => window.setToneState('busy')")
    buttons[0].evaluate("button => { button.dataset.lfAgentWorkflow = 'working'; }")
    expect(buttons[0]).to_have_css("opacity", "0.5")
    buttons[0].evaluate("button => { delete button.dataset.lfAgentWorkflow; }")

    page.evaluate("() => window.setToneState('idle')")
    ordinary = [button.evaluate(read) for button in buttons]
    page.evaluate("() => window.setToneReceiptPhase('picked_up')")
    picked_up = [button.evaluate(read) for button in buttons]
    assert [reading["shell"] for reading in picked_up] == [
        reading["shell"] for reading in ordinary
    ]
    assert [reading["icon"] for reading in picked_up] == [
        token_colour(page, "--accent"),
        ordinary[1]["icon"],
        ordinary[2]["icon"],
    ]
    page.evaluate("() => window.setToneReceiptPhase('working')")
    working = [button.evaluate(read) for button in buttons]
    assert [reading["shell"] for reading in working] == [
        reading["shell"] for reading in ordinary
    ]
    assert [reading["icon"] for reading in working] == [
        token_colour(page, "--accent"),
        ordinary[1]["icon"],
        ordinary[2]["icon"],
    ]
    page.evaluate("() => window.setToneReceiptPhase(null)")

    hovered = []
    focused = []
    for button in buttons:
        button.hover()
        hovered.append(button.evaluate(read))
        page.mouse.move(0, 0)
        button.focus()
        page.keyboard.press("Tab")
        page.keyboard.press("Shift+Tab")
        expect(button).to_be_focused()
        assert button.evaluate("node => node.matches(':focus-visible')")
        focused.append(button.evaluate(read))
    assert_icon_only(hovered)
    assert_icon_only(focused)


@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_agent_progress_stays_on_the_thread_control(browser, serve, reduced_motion):
    """Pickup and work decorate the thread's retained carrier in both map projections.

    A second thread at the same target supplies the aggregation contrast: working
    outranks picked up without growing another margin seat or changing the press.
    """
    page = open_page(
        browser,
        live_url(
            serve(
                OBLIGATION_PAGE,
                events=[
                    {**COMMENT_ON_OBLIGATION, "id": "1" * 32},
                    {
                        **COMMENT_ON_OBLIGATION,
                        "id": "2" * 32,
                        "text": "Check the return visit too.",
                    },
                ],
            )
        ),
    )
    page.emulate_media(reduced_motion=reduced_motion)
    resized(page, 1440, 900)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    cluster = page.locator('[data-lf-margin-for="bracket"]')
    marker = cluster.locator(":scope > .lf-margin-marker")
    expect(marker).to_have_attribute("data-lf-kinds", "comment")
    marker.evaluate("node => node.dataset.identityProbe = 'retained'")
    initial = marker.evaluate("""node => {
      const style = getComputedStyle(node);
      return {border: style.borderTopColor, background: style.backgroundColor,
        icon: getComputedStyle(node.querySelector(':scope > .lf-margin-entry-icon')).color};
    }""")
    colors = page.evaluate("""() => {
      const probe = document.createElement('span');
      document.body.append(probe);
      const result = {};
      for (const name of ['--accent']) {
        probe.style.color = `var(${name})`;
        result[name] = getComputedStyle(probe).color;
      }
      probe.remove();
      return result;
    }""")

    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, roots)
    told(page)
    expect(marker).to_have_attribute("data-lf-agent-workflow", "picked_up")
    picked_up = marker.evaluate("""node => {
      const style = getComputedStyle(node);
      return {border: style.borderTopColor, background: style.backgroundColor,
        icon: getComputedStyle(node.querySelector(':scope > .lf-margin-entry-icon')).color};
    }""")
    assert picked_up == {
        **initial,
        "icon": colors["--accent"],
    }, "pickup did not color only the Thread icon blue"
    page.evaluate("""() => {
      window.agentArrivals = [];
      window.agentArrivalEnds = 0;
      document.addEventListener('animationstart', event => {
        if (!event.animationName.endsWith('agent-work-arrival')) return;
        const style = getComputedStyle(event.target);
        window.agentArrivals.push({iterations: style.animationIterationCount});
      });
      document.addEventListener('animationend', event => {
        if (event.animationName.endsWith('agent-work-arrival')) window.agentArrivalEnds++;
      });
    }""")

    detail = "Checking the return visit, dispatching the diagram instructions review, and comparing every scheduling alternative before preparing the updated recommendation."
    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(serve.page_dir),
            roots[0]["id"],
            "--text",
            detail,
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    expect(marker).to_have_attribute("data-lf-agent-workflow", "working")
    working = marker.evaluate("""node => {
      const style = getComputedStyle(node);
      return {border: style.borderTopColor, background: style.backgroundColor,
        icon: getComputedStyle(node.querySelector(':scope > .lf-margin-entry-icon')).color};
    }""")
    assert working == {
        **initial,
        "icon": colors["--accent"],
    }, "work did not keep the Thread icon blue on its resting interior"
    expect(marker).to_have_attribute("data-identity-probe", "retained")
    expect(marker.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "comment"
    )
    expect(cluster.locator(".lf-margin-entry:visible")).to_have_count(1)
    expected_arrivals = 1 if reduced_motion == "no-preference" else 0
    if expected_arrivals:
        page.wait_for_function("() => window.agentArrivalEnds === 1")
        assert [
            arrival["iterations"] for arrival in page.evaluate("window.agentArrivals")
        ] == ["1"]
    else:
        expect(marker).to_have_css("animation-name", "none")
    expect(marker).not_to_have_attribute("data-lf-agent-arrival", re.compile(".*"))
    expect(marker).to_have_attribute("title", f"Threads · On it · {detail}")

    # An unchanged claim neither replays its arrival nor restates its accessible
    # workflow text. Observe every write, including a remove followed by a restore.
    def workflow_text_mutations(control):
        return control.evaluate("""async node => {
          const writes = [];
          const record = mutations => writes.push(...mutations.map(mutation => ({
            attribute: mutation.attributeName, before: mutation.oldValue,
            after: node.getAttribute(mutation.attributeName),
          })));
          const observer = new MutationObserver(record);
          observer.observe(node, {attributes: true, attributeOldValue: true,
            attributeFilter: ['title', 'aria-description']});
          for (let pass = 0; pass < 3; pass++) {
            window.dispatchEvent(new Event('resize'));
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
          }
          record(observer.takeRecords());
          observer.disconnect();
          return writes;
        }""")

    assert workflow_text_mutations(marker) == []
    expect(marker).to_have_attribute("data-lf-agent-workflow", "working")
    assert page.evaluate("window.agentArrivals.length") == expected_arrivals
    marker.focus()
    page.keyboard.press("Enter")
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("1/2")
    expect(preview).to_contain_text(COMMENT_ON_OBLIGATION["text"])
    preview.get_by_role("button", name="Next thread").click()
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("2/2")
    expect(preview.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview).to_contain_text("Check the return visit too.")
    expect(preview).not_to_contain_text(COMMENT_ON_OBLIGATION["text"])
    leave_card_by_its_target(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.locator(".lf-page-map-dialog")
    rows = dialog.locator(".lf-page-map-action").filter(
        has=page.locator('[data-lf-icon="comment"]')
    )
    expect(rows).to_have_count(2)
    expect(dialog.locator('[data-lf-map-item^="activity:"]')).to_have_count(0)
    working_row = dialog.locator('[data-lf-agent-workflow="working"]')
    expect(working_row).to_have_count(1)
    expect(working_row.locator(".lf-margin-kind")).to_have_attribute(
        "data-lf-icon", "comment"
    )
    expect(working_row.locator(".lf-margin-kind")).to_have_css(
        "color", colors["--accent"]
    )
    working_row.evaluate("node => node.blur()")
    page.mouse.move(0, 0)
    expect(working_row).to_have_css("background-color", "rgba(0, 0, 0, 0)")
    picked_up_row = dialog.locator('[data-lf-agent-workflow="picked_up"]')
    expect(picked_up_row).to_have_count(1)
    expect(picked_up_row.locator(".lf-margin-kind")).to_have_css(
        "color", colors["--accent"]
    )
    page.keyboard.press("Escape")
    # Two contributed actions fold the Thread control behind More. The visible
    # primary must retain the workflow, and its own accessible description survives it.
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      let cancelReceipt = null;
      window.agentContribution = registerContribution({
        key: 'carrier-probe', target: document.querySelector('#bracket'),
        read: () => ({entries: [
          contributionEntry({key: 'edit', icon: 'edit', label: 'Edit',
            description: 'Edit the proposed bracket', behavior: 'disclosure'}),
          contributionEntry({key: 'cancel', icon: 'cross', label: 'Cancel',
            rank: 'secondary', workflowReceipt: cancelReceipt}),
        ]}), activate: () => {}
      });
      window.setAgentCancelReceipt = receipt => {
        cancelReceipt = receipt;
        window.agentContribution.update({immediate: true});
      };
    }""")
    carrier = cluster.get_by_role("button", name="Edit", exact=True)
    expect(carrier).to_be_visible()
    expect(carrier).to_have_attribute("data-lf-agent-workflow", "working")
    expect(carrier).to_have_attribute(
        "aria-description", f"Edit the proposed bracket · On it · {detail}"
    )
    expect(carrier).to_have_css("background-color", initial["background"])
    expect(carrier).to_have_css("box-shadow", "none")
    expect(carrier).to_have_attribute("title", f"Edit · On it · {detail}")
    assert page.evaluate("window.agentArrivals.length") == expected_arrivals, (
        "moving the same work claim to another semantic carrier replayed its arrival"
    )
    # A secondary entry can publish the same canonical workflow receipt.
    page.evaluate("""async () => {
      const {readApplication} = await window.__lfCheckApi();
      const receipt = readApplication().effective.workflows.find(
        item => item.stage === 'working' && !item.condition
      );
      window.setAgentCancelReceipt(receipt);
    }""")
    cluster.locator(":scope > .lf-margin-more").click()
    proxy = cluster.locator('[data-lf-margin-entry-key="cancel"]')
    expect(proxy).to_be_visible()
    expect(proxy).to_have_attribute("title", f"Cancel · On it · {detail}")
    expect(proxy).to_have_attribute("aria-description", f"On it · {detail}")
    assert workflow_text_mutations(proxy) == []
    page.evaluate("""async () => {
      window.agentContribution.unregister();
    }""")
    expect(marker).to_be_visible()
    resized(page, 390, 760)
    working_thread = open_panel_thread(page, roots[0]["id"])
    workflow = working_thread.locator(".lf-msg-sending", has_text="On it")
    expect(workflow).to_have_text("On it")
    expect(workflow).to_have_attribute("title", f"On it · {detail}")


@pytest.mark.parametrize("annotations", ["margin", "page"])
def test_each_seat_agrees_with_the_page_map_on_a_controls_receipt(
    browser, serve, annotations
):
    """A package control's receipt reads the same wherever its target's controls sit.

    The target's agent work rides on its primary control, and every other control shows
    the receipt its contribution gave it. The contrast is a control that gives up the
    primary seat: it goes back to its own receipt, and the new primary takes the work,
    in the margin or a page's own annotation view as in the Page Map.
    """
    source = OBLIGATION_PAGE
    if annotations == "page":
        source = source.replace("<body>", '<body data-annotations="page">')
    page = open_page(
        browser,
        live_url(
            serve(
                source,
                events=[
                    {**COMMENT_ON_OBLIGATION, "id": "1" * 32},
                    {
                        **COMMENT_ON_OBLIGATION,
                        "id": "2" * 32,
                        "text": "Check the return visit too.",
                    },
                ],
            )
        ),
    )
    resized(page, 1440, 900)
    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, roots)
    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(serve.page_dir),
            roots[0]["id"],
            "--text",
            "Checking the visit.",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    if annotations == "margin":
        seat = page.locator('[data-lf-margin-for="bracket"]')
        expect(seat.locator(":scope > .lf-margin-marker")).to_have_attribute(
            "data-lf-agent-workflow", "working"
        )
    else:
        seat = page.locator("#receipt-view")
        page.evaluate("""async () => {
          const {consumeAnnotations} =
            await window.__lfWidgetApi();
          const box = document.createElement('aside');
          box.id = 'receipt-view';
          document.querySelector('#bracket').after(box);
          consumeAnnotations(box, (entries, view) => {
            box.replaceChildren();
            for (const entry of entries) {
              const row = document.createElement('div');
              row.dataset.lfGen = '1';
              box.append(row);
              row.append(...view.controls(entry));
              view.place(entry, row);
            }
          });
        }""")
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      const {readApplication} = await window.__lfCheckApi();
      const ownReceipt = readApplication().effective.workflows.find(item => item.stage === 'picked_up');
      let approving = false;
      const contribution = registerContribution({
        key: 'receipt-probe', target: document.querySelector('#bracket'),
        read: () => ({entries: [
          ...(approving ? [contributionEntry({key: 'approve', icon: 'check',
            label: 'Approve', rank: 'complete'})] : []),
          contributionEntry({key: 'edit', icon: 'edit', label: 'Edit',
            workflowReceipt: ownReceipt}),
        ]}), activate: () => {}
      });
      window.offerApproval = () => {
        approving = true;
        contribution.update({immediate: true});
      };
    }""")

    def receipts():
        seated = {
            key: seat.locator(f'[data-lf-margin-entry-key="{key}"]').get_attribute(
                "data-lf-agent-workflow"
            )
            for key in ("approve", "edit")
            if seat.locator(f'[data-lf-margin-entry-key="{key}"]').count()
        }
        page.keyboard.press("g")
        page.keyboard.press("Shift+p")
        dialog = page.locator(".lf-page-map-dialog")
        expect(dialog).to_be_visible()
        rows = dialog.locator("[data-lf-map-margin-entry]")
        mapped = {
            key: rows.filter(has_text=label).get_attribute("data-lf-agent-workflow")
            for key, label in (("approve", "Approve"), ("edit", "Edit"))
            if rows.filter(has_text=label).count()
        }
        page.keyboard.press("Escape")
        expect(dialog).to_be_hidden()
        return seated, mapped

    carrying = {"edit": "working"}
    expect(seat.locator('[data-lf-margin-entry-key="edit"]')).to_have_attribute(
        "data-lf-agent-workflow", "working"
    )
    assert receipts() == (carrying, carrying)
    page.evaluate("window.offerApproval()")
    expect(seat.locator('[data-lf-margin-entry-key="approve"]')).to_have_count(1)
    displaced = {"approve": "working", "edit": "picked_up"}
    assert receipts() == (displaced, displaced)


def _margin_entry_paint(control):
    return control.evaluate("""node => {
      const style = getComputedStyle(node);
      return {
        background: style.backgroundColor,
        icon: getComputedStyle(
          node.querySelector(':scope > .lf-margin-entry-icon')).color,
      };
    }""")


@pytest.mark.parametrize(
    ("scheme", "target"), [("light", "bracket"), ("dark", "bracket-decision")]
)
def test_a_thread_waiting_on_the_user_colors_its_margin_entry(
    browser, serve, scheme, target
):
    """Whose turn a thread is reaches the margin as colour and as a word.

    The user's own comment is the control: one target, one retained marker, and the
    only thing that changes between the two readings is who spoke last. Pickup and work
    remain secondary when another thread on the same target still needs the user.
    Rails and pins keep that priority in both color schemes, including a target
    whose authored obligation has been handed to the agent by its comment.
    """
    comment = {**COMMENT_ON_OBLIGATION, "anchor": {"section": target}}
    source = OBLIGATION_PAGE.replace(
        "</head>",
        """<style>:root {
      --pin-on-user: light-dark(#d8f1b0, #e4e8aa);
      --pin-on-user-ink: light-dark(#244714, #334017);
    }</style></head>""",
    )
    page = open_page(
        browser, live_url(serve(source, events=[comment])), color_scheme=scheme
    )
    resized(page, 1440, 900)
    cluster = page.locator(f'[data-lf-margin-for="{target}"]')
    marker = cluster.locator(":scope > .lf-margin-marker")
    expect(marker).to_have_attribute("data-lf-kinds", "comment")
    expect(marker).not_to_have_attribute("data-lf-turn", re.compile(".+"))
    marker.evaluate("node => node.dataset.identityProbe = 'retained'")
    with_agent = _margin_entry_paint(marker)
    expect(marker.locator(".lf-margin-entry-context")).to_have_count(0)

    agent_comment = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "text": "Two of them can share a visit; the third cannot. Which two share it?",
            "obligation": True,
            "anchor": {"section": target},
        },
    )
    told(page)
    expect(marker).to_have_attribute("data-lf-turn", "user")
    expect(marker).to_have_attribute("data-identity-probe", "retained")
    expect(marker.locator(".lf-margin-entry-context")).to_have_text("Your turn")
    expect(marker).to_have_attribute(
        "aria-label", re.compile(r"^Threads \(2\), Your turn,")
    )
    on_user = _margin_entry_paint(marker)
    assert on_user == {
        "background": token_colour(page, "--turn-wash"),
        "icon": token_colour(page, "--turn-ink"),
    }, "the user's turn did not colour the Thread marker's icon and interior"
    assert with_agent["background"] != on_user["background"], with_agent

    # A reply returns the thread to the agent before pickup adds any workflow cue.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": agent_comment["id"],
            "text": "Answering the visit question.",
        },
    )
    told(page)
    expect(marker).not_to_have_attribute("data-lf-turn", re.compile(".+"))
    expect(marker).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    assert _margin_entry_paint(marker) == {
        "background": with_agent["background"],
        "icon": token_colour(page, "--accent"),
    }, "the answered thread lost its blue cue after the obligation handoff"
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": agent_comment["id"],
            "revision": 1,
            "text": "Which visit should we choose?",
            "obligation": True,
        },
    )
    told(page)
    expect(marker).to_have_attribute("data-lf-turn", "user")
    assert _margin_entry_paint(marker) == on_user

    # Page Map lists each thread on its own row, so the user's own thread is the
    # control for the agent's beside it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    rows = dialog.locator('.lf-page-map-action[data-lf-map-item^="comment:"]')
    expect(rows).to_have_count(2)
    assert rows.evaluate_all(
        """nodes => nodes.map(node => [
          node.dataset.lfTurn ?? null,
          node.querySelector('.lf-page-map-action-context')?.textContent ?? null,
        ])"""
    ) == [[None, None], ["user", "Your turn"]]
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()

    roots = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, roots)
    told(page)
    expect(marker).to_have_attribute("data-lf-agent-workflow", "picked_up")
    expect(marker).to_have_attribute("data-lf-turn", "user")
    assert _margin_entry_paint(marker) == on_user, (
        "pickup hid the user's turn on the shared carrier"
    )
    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(serve.page_dir),
            roots[0]["id"],
            "--text",
            "Checking the user comment.",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    expect(marker).to_have_attribute("data-lf-agent-workflow", "working")
    expect(marker).to_have_attribute("data-lf-turn", "user")
    assert _margin_entry_paint(marker) == on_user, (
        "work on one thread hid the user's turn on another"
    )

    resized(page, 390, 760)
    expect(cluster).to_have_attribute("data-lf-place", "pin")
    expect(marker).to_have_css("background-color", token_colour(page, "--pin-on-user"))
    expect(marker.locator(".lf-margin-entry-icon")).to_have_css(
        "color", token_colour(page, "--pin-on-user-ink")
    )
    pin_contrast = marker.evaluate("""node => {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext('2d', {willReadFrequently: true});
      const luminance = color => {
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 1, 1);
        const channels = [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)]
          .map(value => value / 255)
          .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
        return channels.reduce(
          (sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
      };
      const ground = luminance(getComputedStyle(node).backgroundColor);
      const ink = luminance(getComputedStyle(node.querySelector('.lf-margin-entry-icon')).color);
      return (Math.max(ground, ink) + .05) / (Math.min(ground, ink) + .05);
    }""")
    assert pin_contrast >= 3, f"the thread glyph lacks contrast: {pin_contrast}"

    # Answering is what ends the user's turn, and the gallery tells a developer to
    # watch for exactly that. Both agent threads have to be answered, because the
    # aggregate takes the turn of any member.
    for root in roots:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "user",
                "parent": root["id"],
                "text": "Answered, so this one is back with the agent.",
            },
        )
    told(page)
    expect(marker).not_to_have_attribute("data-lf-turn", re.compile(".+"))
    expect(marker.locator(".lf-margin-entry-context")).to_have_count(0)
    expect(marker).to_have_css("background-color", token_colour(page, "--pin-fill"))
    resized(page, 1440, 900)
    assert _margin_entry_paint(marker) == {
        "background": with_agent["background"],
        "icon": token_colour(page, "--accent"),
    }


def test_a_thread_an_open_to_do_holds_says_so_beside_the_page(browser, serve):
    """A thread with no title yet, held by a to-do its agent opened, reads as
    Threads states it on every surface that shows it: the margin entry's line, which
    its name says too, and its Page Map row say To-do open as the card's status does,
    and Threads, Page Map and the activity feed name the thread by the words its
    opening renders, not that opening's Markdown, until a title names it on all of
    them."""
    comment = {
        **COMMENT_ON_OBLIGATION,
        "text": "Can **these** share one visit?",
        "anchor": {"section": "bracket"},
    }
    source = OBLIGATION_PAGE.replace(
        '<h1 id="h">Three jobs</h1>',
        '<h1 id="h">Three jobs</h1><lf-activity id="feed"></lf-activity>',
    )
    page = open_page(browser, live_url(serve(source, events=[comment])))
    resized(page, 1440, 900)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    named = "Can these share one visit?"
    # Until the agent answers, On the agent lists the answer it owes by the same name.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.locator(".lf-floating-panel .lf-fp-filters button").nth(1).click()
    queue = page.locator(panel_view("queue"))
    owed = queue.locator('.lf-fp-on-item[data-list="agent"]')
    expect(owed).to_have_count(1)
    expect(owed.get_by_role("button").locator(".lf-fp-label")).to_have_text(named)
    page.keyboard.press("Escape")
    # The agent's answer settles the comment and opens the to-do that holds it.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root["id"],
            "responds": root["id"],
            "revision": 1,
            "text": "I'll check the visit windows.",
            "todo": "Check the visit windows",
        },
    )
    told(page)
    marker = page.locator('[data-lf-margin-for="bracket"] > .lf-margin-marker')
    expect(marker.locator(".lf-margin-entry-context")).to_have_text("To-do open")
    expect(marker).to_have_attribute("aria-label", re.compile(r"^Thread, To-do open,"))

    page.locator("#feed .lf-activity-news").click()
    feed = page.locator("#feed .lf-activity-row", has_text="replied in")
    expect(feed).to_contain_text(f"replied in “{named}”")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    row = dialog.locator('.lf-page-map-action[data-lf-map-item^="comment:"]')
    expect(row.locator(".lf-page-map-action-context")).to_have_text("To-do open")
    expect(row.locator(".lf-page-map-action-label-word")).to_have_text(named)
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    panel_settled(page, view="threads")
    listed = page.locator(f'.lf-fp-thread[data-key="{root["id"]}"]')
    expect(listed.locator(".lf-fp-label")).to_have_text(named)
    expect(listed.locator(".lf-fp-value")).to_contain_text("To-do open")

    # A title names it on every surface, the margin's included.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": root["id"],
            "title": "Visit windows",
        },
    )
    told(page)
    expect(listed.locator(".lf-fp-label")).to_have_text("Visit windows")
    # The renamed row is news the feed holds until the reader asks for it.
    page.locator("#feed .lf-activity-news").click()
    expect(feed).to_contain_text("replied in “Visit windows”")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    expect(row.locator(".lf-page-map-action-label-word")).to_have_text("Visit windows")


def test_unit_claim_arrivals_share_one_window_with_the_open_page_map(browser, serve):
    """Two moved cards started together each arrive only once.

    The visible Page Map joins those same arrivals; reopening it later or repainting
    the two units cannot restart either pulse.
    """
    page = open_page(browser, live_url(serve(BOARD_PAGE)))
    resized(page, 1440, 900)
    # A receipt-only move owes no agent work. First reorder a card and open a task on
    # the board, so the two later moves change work already in hand and are delivered.
    page.locator("#card-heater .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    with sending(page, "reorder before claiming the board"):
        page.keyboard.press("Enter")
    record_claim(serve.page_dir)
    claimed = CliRunner().invoke(
        cli_model.cli,
        ["task", "create", str(serve.page_dir), "sprint", "--title", "Check the board"],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    initial_sequence = events_model.read_events(serve.page_dir)[-1]["seq"]
    for card in ("card-heater", "card-baffle"):
        page.locator(f"#{card} .lf-grip").focus()
        page.keyboard.press("Enter")
        page.keyboard.press("ArrowRight")
        with sending(page, f"move {card}"):
            page.keyboard.press("Enter")
        expect(page.locator(f"#col-done > #{card}")).to_be_visible()
    moves = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["seq"] > initial_sequence
    ]
    assert len(moves) == 2
    assert all(event["attention"] for event in moves)
    # Observe pickup separately from the task that made these moves input.
    declare_idle(serve.page_dir)
    record_claim(serve.page_dir)
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, moves)
    told(page)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.locator(".lf-page-map-dialog")
    expect(dialog).to_be_visible()
    expect(dialog.locator('[data-lf-agent-workflow="picked_up"]')).to_have_count(2)
    page.evaluate("""() => {
      window.unitArrivals = [];
      window.unitArrivalEnds = 0;
      document.addEventListener('animationstart', event => {
        if (!event.animationName.endsWith('agent-work-arrival')) return;
        const style = getComputedStyle(event.target);
        window.unitArrivals.push({
          mapped: event.target.matches('.lf-page-map-action'),
          iterations: style.animationIterationCount,
        });
      });
      document.addEventListener('animationend', event => {
        if (event.animationName.endsWith('agent-work-arrival')) window.unitArrivalEnds++;
      });
    }""")
    for move in moves:
        claim = CliRunner().invoke(
            cli_model.cli,
            [
                "task",
                "start",
                str(serve.page_dir),
                move["id"],
                "--text",
                "Checking both moved cards",
            ],
        )
        assert claim.exit_code == 0, claim.output
    told(page)
    expect(dialog.locator('[data-lf-agent-workflow="working"]')).to_have_count(2)
    page.wait_for_function("() => window.unitArrivalEnds === 4")
    arrivals = page.evaluate("window.unitArrivals")
    assert sorted(arrival["mapped"] for arrival in arrivals) == [
        False,
        False,
        True,
        True,
    ]
    assert all(arrival["iterations"] == "1" for arrival in arrivals)
    expect(page.locator("[data-lf-agent-arrival]")).to_have_count(0)

    # Alternate the two same-target receipt identities through repeated real renders.
    page.evaluate("""async () => {
      for (let pass = 0; pass < 3; pass++) {
        window.dispatchEvent(new Event('resize'));
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
      }
    }""")
    assert page.evaluate("window.unitArrivals.length") == 4
    expect(page.locator("[data-lf-agent-arrival]")).to_have_count(0)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    expect(dialog.locator('[data-lf-agent-workflow="working"]')).to_have_count(2)
    expect(dialog.locator("[data-lf-agent-arrival]")).to_have_count(0)
    assert page.evaluate("window.unitArrivals.length") == 4


def test_an_acknowledgment_uses_status_until_an_active_claim_restores_a_disclosure(
    browser, serve, monkeypatch
):
    """A margin entry keeps the margin entry family visible without promising a press.

    Saved, Haven't seen it yet, and Got it report a move already made. Their status
    margin entry therefore keeps the family silhouette and full ink, while leaving the
    accessibility tree as a status rather than a control and showing no hover fill.
    Hovering the status draws a soft neutral trace to the
    target without making the margin entry respond like a control. The walk still arrives,
    because the phase is what a user listening came for. A real claim — work the
    user can watch — restores the same margin entry's activation semantics, in the same
    seat, so the cluster's identity survives the change of promise. Once the handoff and
    claim are complete, the margin entry leaves instead of restating widget state.

    The group is single-choice so the pick itself answers the obligation: a tick in a
    group that waits for Done hands the agent nothing, so it has no receipt.
    """
    single = OBLIGATION_PAGE.replace(
        '<lf-options id="jobs" choose multiple>', '<lf-options id="jobs" choose>'
    )
    page = open_page(browser, live_url(serve(single)))
    page_dir = serve.page_dir
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')

    with sending(page, "the mounts choice"):
        page.locator("#job-mounts").click()
    logged_action = next(
        event
        for event in reversed(events_model.read_events(page_dir))
        if event.get("widget") == "jobs" and event.get("action") == "choose"
    )
    marker.evaluate("node => { node.dataset.identityProbe = 'kept' }")

    def face(control=marker):
        return control.evaluate(
            """node => {
              const style = getComputedStyle(node);
              const word = node.querySelector(':scope > .lf-margin-entry-label');
              const wordStyle = getComputedStyle(word);
              return {
                tag: node.tagName,
                offer: node.dataset.lfOffer,
                behavior: node.dataset.lfBehavior,
                role: node.getAttribute('role'),
                icon: node.querySelector(':scope > .lf-margin-entry-icon')
                  .dataset.lfIcon,
                word: word.querySelector(':scope > .lf-margin-entry-label-word').textContent,
                context: word.querySelector(':scope > .lf-margin-entry-context')?.textContent ?? null,
                tabIndex: node.tabIndex,
                cursor: style.cursor,
                background: style.backgroundColor,
                border: style.borderTopColor,
                borderStyle: style.borderTopStyle,
                animation: style.animationName,
                ink: style.color,
                iconInk: getComputedStyle(
                  node.querySelector(':scope > .lf-margin-entry-icon')
                ).color,
                opacity: style.opacity,
                width: style.width,
                wordOpacity: wordStyle.opacity,
                wordPosition: wordStyle.position,
                wordBackground: wordStyle.backgroundColor,
                wordInk: wordStyle.color,
              };
            }"""
        )

    def resolved_color(name):
        return page.evaluate(
            """name => {
              const probe = document.createElement('span');
              probe.style.color = `var(${name})`;
              document.body.append(probe);
              const read = getComputedStyle(probe).color;
              probe.remove();
              return read;
            }""",
            name,
        )

    expected_ink = resolved_color("--ink-2")
    expected_paper = resolved_color("--paper")
    expected_rule = resolved_color("--rule")
    expected_label_ink = resolved_color("--paper")
    expected_label_background = resolved_color("--ink")

    def words_still():
        """The label's reveal is a 90ms transition behind a 90ms delay, so the frame the
        delay ends on is a box the user can see drawn at the opacity it is leaving —
        which is what `to_be_visible` is satisfied by, and what the paint read behind it
        then reports as the status's own ink. Ask the transitions instead: the call
        flushes pending style, so a reveal that has been started is in the list on the
        first read and a control that never moves reports empty at once."""
        page.wait_for_function(
            """() => [...document.querySelectorAll('.lf-margin-entry-label')]
                 .every((label) => label.getAnimations().length === 0)"""
        )

    def assert_status(phase, context, control=marker):
        if control is marker:
            expect(marker).to_have_attribute("data-identity-probe", "kept")
        page.evaluate("() => document.activeElement.blur()")
        page.mouse.move(0, 0)
        expect(page.locator(".lf-target-trace")).to_be_hidden()
        expect(control.locator(":scope > .lf-margin-entry-label")).to_be_hidden()
        words_still()
        current = face(control)
        expect(control).to_have_attribute("data-lf-state", "idle")
        pickup_ink = resolved_color("--accent")
        assert current == {
            "tag": "SPAN",
            "offer": "",
            "behavior": "status",
            "role": "status",
            "icon": RECEIPT_PHASES[phase],
            "word": phase,
            "context": context,
            "tabIndex": -1,
            "cursor": "default",
            "background": expected_paper,
            "border": expected_rule,
            "borderStyle": "solid",
            "animation": "none",
            "ink": expected_ink,
            "iconInk": pickup_ink if phase == "Got it" else expected_ink,
            "opacity": "1",
            "width": "32px",
            "wordOpacity": "0",
            "wordPosition": "absolute",
            "wordBackground": expected_label_background,
            "wordInk": expected_label_ink,
        }
        named = re.compile(rf"^{re.escape(phase)}(?:,| for )")
        expect(page.get_by_role("button", name=named)).to_have_count(0)
        expect(page.get_by_role("status", name=named)).to_have_count(1)
        # Hover reveals the full-strength label without dimming or lifting the margin entry.
        resting_surface = {
            key: current[key]
            for key in ("background", "border", "ink", "iconInk", "opacity")
        }
        control.hover()
        trace_box = page.locator('.lf-target-trace[data-for="jobs"]')
        expect(trace_box).to_be_visible()
        label = control.locator(":scope > .lf-margin-entry-label")
        expect(label).to_be_visible()
        words_still()
        expect(label).to_have_css("opacity", "1")
        hovered = face(control)
        assert {
            key: hovered[key]
            for key in ("background", "border", "ink", "iconInk", "opacity")
        } == resting_surface
        assert hovered["wordOpacity"] == "1"
        assert hovered["wordPosition"] == "absolute"
        assert hovered["wordBackground"] != "rgba(0, 0, 0, 0)"
        # A rectangular trace uses the same outside stroke as target focus, in the
        # trace's quiet ink. Read the painted bracket, not its transparent container.
        trace = page.evaluate(
            """() => {
              const trace = document.querySelector('.lf-target-trace');
              const box = getComputedStyle(trace, '::before');
              return {
                boxWidth: box.outlineWidth,
                boxColor: box.outlineColor,
                gap: box.outlineOffset,
                leader: getComputedStyle(
                  document.querySelector('.lf-margin-cluster'), '::before',
                ).content,
              };
            }"""
        )
        assert trace == {
            "boxWidth": "2px",
            "boxColor": resolved_color("--target-trace-ink"),
            "gap": "0px",
            "leader": "none",
        }

    assert_status("Saved", "just now")
    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []
    assert page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.some(row => row.tabIndex === 0)"
    ), "no margin entry is left for Tab to enter the rail by"

    # The user listening still reaches the phase through its visible generated hint.
    address_target = marker.evaluate(
        "row => row.closest('[data-lf-margin-for]').dataset.lfMarginFor"
    )
    go_to_address(page, "Margin entry", address_target)
    expect(marker).to_be_focused()

    # Located there is not the same as being the way in. A repaint under the user
    # leaves the rail's one stop on a margin entry that acts, and the status without one.
    page.evaluate("() => window.dispatchEvent(new Event('resize'))")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame("
        "() => requestAnimationFrame(done)))"
    )
    expect(marker).to_be_focused()
    stops = page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.map(row => [row.dataset.lfBehavior, row.tabIndex])"
    )
    assert ["status", -1] in stops, stops
    assert [behavior for behavior, index in stops if index == 0] == ["disclosure"], (
        stops
    )

    # Waiting is a server-folded phase now. Advance the threaded test server's clock,
    # then let the ordinary state read advance the retained margin entry in place.
    sent_at = datetime.fromisoformat(logged_action["ts"])
    advanced = (sent_at + timedelta(minutes=3)).isoformat()

    def advanced_now():
        return advanced

    for clock_owner in (served_context, events_model, service_model):
        monkeypatch.setattr(clock_owner, "now_iso", advanced_now)
    declare_idle(page_dir)
    told(page)
    expect(marker).to_have_attribute("aria-label", re.compile(r"^Haven't seen it yet,"))
    assert_status("Haven't seen it yet", "3m ago")

    # Pickup belongs to an active agent turn; an unclaimed pickup is stale work.
    record_claim(page_dir)
    with service_model.PageTransaction(page_dir) as transaction:
        delivery_model.record_pickup(transaction, [logged_action])
    told(page)
    assert_status("Got it", "just now")

    # A surviving semantic action carries pickup itself. Removing that carrier
    # restores the status fallback with the same canonical receipt.
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          window.lfReceiptSecondary = registerContribution({
            key: 'workflow-primary-probe', target: document.querySelector('#jobs'),
            read: () => ({entries: [contributionEntry({
              key: 'edit', icon: 'edit', label: 'Edit', behavior: 'disclosure',
              className: 'lf-workflow-primary-probe'
            })]}), activate: () => {}
          });
        }"""
    )
    carrier = page.locator(".lf-workflow-primary-probe")
    expect(marker).to_be_hidden()
    expect(carrier).to_have_attribute("data-lf-agent-workflow", "picked_up")
    expect(carrier).to_have_attribute("aria-description", "Got it")
    expect(carrier.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "edit"
    )
    expect(
        page.locator('[data-lf-margin-for="jobs"] .lf-margin-entry:visible')
    ).to_have_count(1)
    carrier.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    mapped = page.locator('.lf-page-map-action[data-lf-agent-workflow="picked_up"]')
    expect(mapped).to_have_count(1)
    expect(mapped.locator(".lf-margin-kind")).to_have_attribute("data-lf-icon", "edit")
    # The row is the carrier drawn again, so pickup inks its glyph as it inks the
    # carrier's: one rule set in theme.css paints both.
    ink = "el => getComputedStyle(el).color"
    assert (
        mapped.locator(".lf-margin-kind").evaluate(ink)
        == carrier.locator(".lf-margin-entry-icon").evaluate(ink)
        != mapped.locator(".lf-page-map-action-label").evaluate(ink)
    )
    page.keyboard.press("Escape")
    page.evaluate("() => window.lfReceiptSecondary.unregister()")
    expect(marker).to_be_visible()

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(page_dir),
            logged_action["id"],
            "--text",
            "checking the mounts",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)

    expect(marker).to_have_attribute("data-identity-probe", "kept")
    working = face()
    assert working["tag"] == "SPAN"
    assert working["offer"] == "button"
    assert working["behavior"] == "disclosure"
    assert working["role"] == "button"
    assert working["icon"] == "activity"
    assert working["word"] == "On it…"
    assert working["context"] == "just now · checking the mounts"
    assert working["cursor"] == "pointer"
    assert working["opacity"] == "1"
    assert working["background"] != "rgba(0, 0, 0, 0)"
    assert working["border"] != "rgba(0, 0, 0, 0)"
    expect(page.get_by_role("button", name=re.compile(r"^On it,"))).to_have_count(1)

    honored = single.replace(
        '<lf-option id="job-mounts"', '<lf-option id="job-mounts" chosen'
    )
    stamped = stamp_page(page_dir, honored, "Honor the mounts choice")
    wait_for_revision(page, stamped["revision"])
    expect(page.locator('[data-lf-margin-for="jobs"]')).to_have_count(0)
    expect(page.locator("#job-mounts[chosen]")).to_have_count(1)


def test_a_reaction_receipt_keeps_an_unided_selected_blocks_visual_coordinate(
    browser, serve
):
    """The durable section coordinate does not pull the visible RHS receipt to its top."""
    page = open_page(browser, serve(UNID_SELECTION_PAGE))
    resized(page, 1600, 900)
    paragraph = page.locator("#s-how > p:nth-of-type(2)")
    box = paragraph.bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=12,
    )
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    page.keyboard.press("e")
    # The choices stay with the captured selection. The reaction in force that replaces
    # them must keep that same visual coordinate even though the durable section
    # coordinate belongs to the surrounding id-bearing section.
    reactions = bar.locator(":scope > .lf-response-options")
    expect(reactions).to_be_visible()

    with sending(page, "the keep reaction"):
        reactions.locator('.lf-react[data-token="keep"]').click()
    expect(bar).to_be_hidden()
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["anchor"]["section"] == "s-how" and sent["anchor"]["quote"]
    receipt = page.locator(".lf-margin-cluster").filter(
        has=page.get_by_role("button", name="keep reaction actions", exact=True)
    )
    expect(receipt).to_have_count(1)
    assert abs(receipt.bounding_box()["y"] - paragraph.bounding_box()["y"]) <= 6
    # The optimistic receipt is already on screen. Let the accepted reading
    # finish replacing it before testing the disclosure gesture.
    told(page)
    assert abs(receipt.bounding_box()["y"] - paragraph.bounding_box()["y"]) <= 6
    reaction = receipt.get_by_role("button", name="keep reaction actions", exact=True)
    reaction.click()
    expect(reaction).to_have_attribute("aria-expanded", "true")
    expect(reaction).to_have_css("border-top-color", token_colour(page, "--accent"))


def test_status_hover_trace_uses_a_registered_visual_surface(browser, serve):
    """A status follows a package's surface instead of its decorated semantic part."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    page = open_page(browser, url)
    resized(page, 1280, 720)
    page.evaluate(
        """async () => {
              const {contributionEntry, registerContribution} =
                await window.__lfWidgetApi();
          registerContribution({
            key: 'shape-status', target: document.querySelector('#outer'),
            read: () => ({entries: [contributionEntry({
              key: 'shape-status', icon: 'pickup', label: 'Delivered', behavior: 'status'
            })]}), activate: () => {}
          });
        }"""
    )
    margins_laid_out(page)

    status = page.locator('[data-lf-margin-entry-key="shape-status"]')
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_attribute("tabindex", "-1")
    assert status.evaluate("node => node.tagName") == "SPAN"
    status.hover()
    trace = page.locator('.lf-target-trace[data-for="outer"]')
    expect(trace).to_be_visible()
    expect(trace).to_have_class(re.compile(r"\blf-shaped\b"))
    assert trace.locator(".lf-target-trace-shape > g > *").evaluate_all(
        "nodes => nodes.map(node => node.localName)"
    ) == ["rect"]
    geometry = page.evaluate(
        """() => {
          const surface = document.querySelector('#outer-surface').getBoundingClientRect();
          const trace = document.querySelector('.lf-target-trace');
          const box = trace.getBoundingClientRect();
          const shape = trace.querySelector('rect');
          const style = getComputedStyle(shape);
          const swatch = document.createElement('span');
          swatch.style.color = 'var(--target-trace-ink)';
          document.head.append(swatch);
          const traceInk = getComputedStyle(swatch).color;
          swatch.remove();
          return {
            sameCenter: Math.abs(box.x + box.width / 2 - (surface.x + surface.width / 2)) < .5
              && Math.abs(box.y + box.height / 2 - (surface.y + surface.height / 2)) < .5,
            surrounds: box.width > surface.width && box.height > surface.height,
            stroke: style.stroke,
            traceInk,
            fill: style.fill,
          };
        }"""
    )
    assert geometry == {
        "sameCenter": True,
        "surrounds": True,
        "stroke": geometry["traceInk"],
        "traceInk": geometry["stroke"],
        "fill": "none",
    }

    page.mouse.move(0, 0)
    expect(trace).to_be_hidden()
