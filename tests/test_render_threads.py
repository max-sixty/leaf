"""Comment-panel ordering, narrowing, and thread-motion tests."""

import base64
import io
import json
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import append_command, record_claim
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import render_checks as render_checks_model
from leaf import service as service_model
from leaf import thread as thread_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    FRAME_BY_FRAME,
    HOLD_MOTION,
    LIST_ORDER,
    LIST_STATE,
    PANEL_PAGE,
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    SEATED_QUESTION_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_cases_layout import (
    COVERED_TOP,
    banner_control,
    button_radius,
    in_threads_scrollport,
    page_at_rest,
    ring_faults,
    rings_drawn,
    token_colour,
)
from render_cases_navigation import source_revision
from render_harness import (
    EXAMPLE_MEDIA,
    EXAMPLE_PACKAGES,
    EXAMPLES,
    FEATURE_GALLERY,
    LONG_PAGE,
    CutOff,
    any_owner_entry,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    primed,
    resized,
    round_trip,
    scroll_settled,
    sending,
    shortcut_bar_text,
    take_browser_errors,
    told,
    undo,
    write,
)

pytestmark = pytest.mark.nightly


def test_gallery_thread_rows_name_action_in_existing_status(browser, serve):
    page = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1440, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    asked = page.locator('.lf-thread[data-id="2be2443f0bb6cc49fc86b52f340e6073"]')
    expect(asked.locator(":scope > .lf-thread-summary .lf-thread-status")).to_have_text(
        "On you to answer"
    )
    summary = asked.locator(":scope > .lf-thread-summary")
    recency = summary.locator(".lf-thread-recency")
    expect(recency).to_have_attribute("datetime", "2026-09-02T00:12:56-07:00")
    expect(recency).to_have_text(re.compile(r"^(now|\d+[mhd])$"))
    expect(summary.locator(".lf-thread-count")).to_have_count(0)
    regular = summary.evaluate(
        """summary => {
          const box = selector => summary.querySelector(selector).getBoundingClientRect();
          const topic = box('.lf-thread-topic');
          const status = box('.lf-thread-status');
          const trailing = box('.lf-thread-trailing');
          const center = rect => rect.top + rect.height / 2;
          return {
            panelWidth: summary.closest('.lf-thread-panel').getBoundingClientRect().width,
            statusBelowTopic: status.top >= topic.bottom,
            timeBesideTopic: Math.abs(center(topic) - center(trailing)) < 2,
            timeAfterTopic: trailing.left >= topic.right,
          };
        }"""
    )
    assert regular["panelWidth"] > 400
    assert regular["statusBelowTopic"]
    assert regular["timeBesideTopic"]
    assert regular["timeAfterTopic"]
    page.evaluate(
        "document.documentElement.style.setProperty('--lf-thread-panel-width', '320px')"
    )
    narrow = summary.evaluate(
        """summary => {
          const topic = summary.querySelector('.lf-thread-topic').getBoundingClientRect();
          const status = summary.querySelector('.lf-thread-status').getBoundingClientRect();
          const trailing = summary.querySelector('.lf-thread-trailing').getBoundingClientRect();
          const row = summary.getBoundingClientRect();
          return { topicWidth: topic.width, statusBelow: status.top >= topic.bottom,
                   trailingInside: trailing.right <= row.right };
        }"""
    )
    assert narrow["topicWidth"] > 150
    assert narrow["statusBelow"]
    assert narrow["trailingInside"]
    asked.locator(":scope > .lf-thread-summary").focus()
    asked.locator(":scope > .lf-thread-summary").press("Enter")
    expect(asked).to_have_attribute("open", "")
    resolved = page.locator('.lf-thread[data-id="bab3cdfcfb8c02aacbb27da731de947a"]')
    expect(
        resolved.locator(":scope > .lf-thread-summary .lf-thread-status")
    ).to_have_text("Resolved")


def focus_panel_thread(thread):
    """Stand on a panel thread through its native disclosure title."""
    title = thread.locator(":scope > .lf-thread-summary")
    if thread.get_attribute("open") is None:
        title.click()
    else:
        title.focus()


def hold_visible_thread_presentation(page, thread_id):
    """Hold the list candidate that reveals one named thread."""
    page.evaluate(
        """(threadId) => {
          const list = document.querySelector('.lf-threads');
          const present = list.present.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let used = false;
          list.present = (model) => {
            const reveals = model.rows.some(row =>
              row.kind === 'thread' && row.descriptor.id === threadId &&
              row.descriptor.visible);
            if (!reveals) return present(model);
            if (!used) {
              used = true;
              window.visibleThreadPresentationHeld = true;
            }
            return held.then(() => present(model));
          };
          window.releaseVisibleThreadPresentation = release;
        }""",
        thread_id,
    )


# Named from the command's own answer: a page open on this directory appends a
# bookkeeping `read` of its own, so the log's tail is not reliably this summary.
def summarize_thread(page_dir, first, last, text):
    """Admit one agent summary through the public command door."""
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "summarize",
            str(page_dir),
            "--from",
            first,
            "--through",
            last,
            "--text",
            text,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def append_user_reply(page_dir, parent, text):
    return events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": parent,
            "revision": 1,
            "text": text,
        },
    )


def append_agent_reply(page_dir, parent, text, markup=None):
    event = {
        "kind": "reply",
        "author": "agent",
        "agent": "Codex",
        "session": "pytest-summary",
        "parent": parent,
        "revision": 1,
        "text": text,
    }
    if markup is not None:
        event["markup"] = markup
    return events_model.append_event(page_dir, event)


def test_a_durable_answer_retires_the_placeholder_its_attempt_reserved(
    browser, serve, request
):
    """The answer the log holds is what the panel draws, not the draft it replaced.

    `publish-site` failed on a deployed turn that published its revision and replied:
    the container held the answer, every server reading returned it, and the user's
    panel showed one agent bubble with no words in it. The provisional reply was
    retired by the response address it was sent to, while every consumer keys the
    message on the delivery attempt it was reserved under, so an answer that named
    only the attempt stood beside its own placeholder under one key and the draft is
    what got drawn.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here", {"section": "h-how"})
    claim = record_claim(
        serve.page_dir, id="codex-thread", harness="codex", agent="Codex"
    )
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)
    attempt = service_model.delivery_reply_attempt("delivery-1")
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_status("waiting", "User feedback")
        transaction.set_stream_reply(
            "codex-thread",
            "leaf-turn",
            root,
            root,
            attempt,
            None,
            "",
            "active",
        )

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(
        page.locator(f'.lf-msg[data-attempt="{attempt}"] .lf-msg-text')
    ).to_be_empty()

    # An answer that names the attempt it was reserved under and nothing else. The
    # attempt is the identity the placeholder was opened on and the one the panel
    # draws by, so this is the whole of what says the draft is finished.
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "parent": root,
            "revision": 1,
            "attempt": attempt,
            "text": "deployment verified",
        },
    )
    assert "responds" not in reply
    told(page)

    answered = page.locator(f'.lf-msg[data-attempt="{attempt}"]')
    expect(answered).to_have_count(1)
    expect(answered).to_have_attribute("data-mid", reply["id"])
    expect(answered.locator(".lf-msg-text")).to_have_text("deployment verified")


def test_a_durable_reply_completes_an_empty_stream_placeholder(browser, serve, request):
    """One retained message gains its durable prose and validated authored island.

    The stream placeholder exists before the final event, so its owner must not freeze
    the absence of markup at construction. A later prose edit keeps both that owner and
    the island the durable reply introduced.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here", {"section": "h-how"})
    claim = record_claim(
        serve.page_dir,
        id="codex-thread",
        harness="codex",
        agent="Codex",
    )
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)
    attempt = service_model.delivery_reply_attempt("delivery-1")
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_status("waiting", "User feedback")
        transaction.set_stream_reply(
            "codex-thread",
            "leaf-turn",
            root,
            root,
            attempt,
            None,
            "",
            "active",
        )

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    message = page.locator(f'.lf-msg[data-attempt="{attempt}"]')
    expect(message.locator(".lf-msg-text")).to_be_empty()
    expect(
        page.locator(f'.lf-thread[data-id="{root}"] .lf-thread-status')
    ).to_have_text("Replying")
    expect(message.locator(".lf-msg-head .lf-msg-sending")).to_have_count(0)
    page.evaluate(
        "attempt => { window.__streamMessage = document.querySelector("
        '`.lf-msg[data-attempt="${attempt}"]`); }',
        attempt,
    )

    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "The complete answer.",
        (
            '<lf-ask id="stream-reply-ask"><h3>Use this answer?</h3>'
            '<lf-options id="stream-reply-choice" choose>'
            '<lf-option id="stream-reply-now">Use it now</lf-option>'
            "</lf-options></lf-ask>"
        ),
        for_event=root,
        attempt=attempt,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")

    expect(message).to_have_attribute("data-mid", reply["id"])
    expect(message.locator(".lf-msg-text")).to_have_text("The complete answer.")
    expect(message.locator("#stream-reply-choice")).to_have_count(1)
    page.evaluate(
        "() => { window.__streamWidget = document.querySelector("
        "'#stream-reply-choice'); }"
    )

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "codex-thread",
            "message": reply["id"],
            "text": "The complete edited answer.",
        },
    )
    told(page)
    expect(message.locator(".lf-msg-text")).to_have_text("The complete edited answer.")
    assert page.evaluate(
        f"""() => window.__streamMessage === document.querySelector(
          '.lf-msg[data-mid="{reply["id"]}"]')
          && window.__streamWidget === document.querySelector('#stream-reply-choice')"""
    ), "the durable reply or its authored island was replaced after the edit"


@pytest.mark.parametrize("resolved", [False, True])
def test_an_inline_reply_link_reveals_its_thread(browser, serve, resolved):
    """A direct reply link opens and cues the exact message, even in a long thread or
    in the Resolved state. The surrounding card can span more than a viewport,
    so using it as the arrival flash obscures the destination the link named."""
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "Choose the first job.",
        '<lf-ask id="first-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="first-job" choose>'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
        for_event=root,
    )
    for i in range(8):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if i % 2 else "user",
                "parent": root,
                "revision": 1,
                "text": f"Follow-up {i}. " + "This exchange needs its context. " * 5,
            },
        )
    if resolved:
        events_model.append_event(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
    page = open_page(browser, url)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    destination = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    page.locator(".lf-page-thread-open").evaluate(
        """(open, destination) => open.addEventListener(
          'click',
          () => {
            destination.classList.add('grow');
            window.__arrival = null;
            const arrived = (event) => {
              if (event.target !== destination) return;
              window.__arrival = event.animationName;
              destination.removeEventListener('animationstart', arrived);
            };
            destination.addEventListener('animationstart', arrived);
          },
          {capture: true, once: true},
        )""",
        destination.element_handle(),
    )
    page.locator(".lf-page-thread-open").click()
    panel_settled(page)
    page.wait_for_function("() => window.__arrival !== null")
    arrival = page.evaluate("() => window.__arrival")
    assert arrival.endswith("-flash"), arrival
    expect(thread).to_be_visible()
    expect(destination.locator("#first-job")).to_be_in_viewport()
    expect(destination).to_be_focused()
    expect(thread).not_to_have_class(re.compile(r"\bflash\b"))
    expect(destination).to_have_class(re.compile(r"\bflash\b"))
    sizes = page.evaluate(
        """([thread, destination, list]) => ({
          thread: thread.getBoundingClientRect().height,
          destination: destination.getBoundingClientRect().height,
          list: list.getBoundingClientRect().height,
        })""",
        [
            thread.element_handle(),
            destination.element_handle(),
            page.locator(".lf-threads").element_handle(),
        ],
    )
    assert sizes["thread"] > sizes["list"], sizes
    assert sizes["destination"] < sizes["list"], sizes
    page.keyboard.press("Tab")
    expect(page.locator("#mounts [role=checkbox]")).to_be_focused()


def test_a_summary_folds_originals_and_a_direct_reply_link_reveals_them(browser, serve):
    """A checkpoint shortens only its admitted range and remains a route to originals.

    The messages before and after the range are controls: hiding either would mean the
    presentation collapsed by position rather than by the summary's declared ids.
    """
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(
        serve.page_dir, "Keep the opening question visible.", {"section": "jobs"}
    )
    first = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "The first job establishes the dependency.",
        None,
        for_event=root,
    )
    middle = append_user_reply(
        serve.page_dir, root, "Does that still hold for the camera?"
    )
    last = append_agent_reply(
        serve.page_dir,
        root,
        "Yes. The measured result supports it.",
        "<p>The measured result is 18 minutes.</p>",
    )
    latest = append_user_reply(
        serve.page_dir, root, "Then keep the latest exception visible."
    )
    summary = summarize_thread(
        serve.page_dir,
        first["id"],
        last["id"],
        "Checkpoint digest: the **dependency** remains and the measurement took "
        "`18 minutes`.",
    )

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    checkpoint = card.locator(
        f'.lf-thread-checkpoint[data-summary-id="{summary["id"]}"]'
    )
    expand = checkpoint.locator(".lf-summary-expand")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(expand).to_have_accessible_name("Show 3 earlier messages")
    expect(checkpoint.locator(".lf-summary-label")).to_have_text("Earlier discussion")
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "Checkpoint digest: the dependency remains and the measurement took 18 minutes."
    )
    expect(checkpoint.locator(".lf-summary-text strong")).to_have_text("dependency")
    expect(checkpoint.locator(".lf-summary-text code")).to_have_text("18 minutes")
    assert (
        checkpoint.locator(".lf-summary-text").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    assert (
        checkpoint.locator(".lf-summary-text code").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-mid="{latest["id"]}"]')).to_be_visible()
    for message in (first, middle, last):
        expect(card.locator(f'.lf-msg[data-mid="{message["id"]}"]')).to_be_hidden()

    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "true")
    for message in (first, middle, last):
        expect(card.locator(f'.lf-msg[data-mid="{message["id"]}"]')).to_be_visible()
    expect(checkpoint.locator(".lf-summary-refold")).to_have_count(0)
    expect(expand).to_have_accessible_name("Collapse 3 earlier messages")
    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(card.locator(f'.lf-msg[data-mid="{last["id"]}"]')).to_be_hidden()

    page.locator(".lf-thread-filter-toggle").click()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("checkpoint digest")
    expect(card).to_be_visible()
    expect(expand).to_have_attribute("aria-expanded", "false")
    find.fill("18 minutes")
    expect(card).to_be_visible()
    expect(checkpoint.locator(".lf-summary-expand")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-required")).to_have_text(
        "Matching messages kept open"
    )
    expect(card.locator(f'.lf-msg[data-mid="{last["id"]}"]')).to_be_visible()
    find.fill("")
    expand = checkpoint.locator(".lf-summary-expand")
    expect(expand).to_have_attribute("aria-expanded", "false")

    page.locator(".lf-page-thread-open").click()
    destination = card.locator(f'.lf-msg[data-mid="{last["id"]}"]')
    expect(destination).to_be_visible()
    expect(destination).to_be_focused()
    expect(expand).to_have_attribute("aria-expanded", "true")


def test_a_summary_gathering_the_message_the_user_is_on_keeps_them_on_it(
    browser, serve
):
    """A checkpoint arriving over the message the user stands on opens around it.

    The message moves into the checkpoint's originals, and the user moves with it
    rather than dropping to the page."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Start with the measured constraint.")
    first = append_agent_reply(serve.page_dir, root, "The constraint still applies.")
    held = append_user_reply(serve.page_dir, root, "It holds for the camera too.")
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    message = card.locator(f'.lf-msg[data-mid="{held["id"]}"]')
    message.focus()
    expect(message).to_be_focused()

    summary = summarize_thread(
        serve.page_dir, first["id"], held["id"], "The constraint was confirmed."
    )
    told(page)
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(
        checkpoint.locator(f'.lf-summary-originals > .lf-msg[data-mid="{held["id"]}"]')
    ).to_be_visible()
    expect(message).to_be_focused()


def test_a_root_summary_keeps_thread_actions_outside_its_fold(browser, serve):
    """A checkpoint may cover the root turn without hiding thread actions."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Start with the measured constraint.")
    reply = append_agent_reply(serve.page_dir, root, "The constraint still applies.")
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")
    summary = summarize_thread(
        serve.page_dir, root, reply["id"], "The constraint was confirmed."
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    events_model.append_event(
        serve.page_dir, {"kind": "unresolve", "author": "user", "parent": root}
    )

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(card.get_by_role("button", name="Resolve thread")).to_be_visible()
    expect(card.get_by_role("button", name="Close thread")).to_have_count(0)
    root_meta = card.locator(":scope > .lf-thread-root-meta")
    expect(root_meta).to_contain_text("You")
    assert root_meta.evaluate("node => !node.closest('.lf-summary-originals')"), (
        "root metadata and thread actions entered the collapsible originals"
    )
    resolve = card.get_by_role("button", name="Resolve thread")
    resolve.focus()
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": root,
            "text": "Start with the corrected measured constraint.",
        },
    )
    told(page)
    expect(checkpoint).to_have_count(0)
    expect(resolve).to_be_focused()


def test_a_later_summary_replaces_its_overlap_and_an_edit_restores_originals(
    browser, serve
):
    """The browser follows the canonical summary fold as the transcript changes."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Start with the measured constraint.")
    first = thread_model.cmd_reply(
        serve.page_dir, root, "The first constraint.", None, for_event=root
    )
    second = append_agent_reply(serve.page_dir, root, "The second constraint.")
    third = append_agent_reply(serve.page_dir, root, "The third constraint.")
    old = summarize_thread(
        serve.page_dir,
        first["id"],
        second["id"],
        "Two constraints were established.",
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    old_checkpoint = card.locator(f'[data-summary-id="{old["id"]}"]')
    expect(old_checkpoint).to_be_visible()
    old_checkpoint.locator(".lf-summary-expand").click()
    standing = card.locator(f'.lf-msg[data-mid="{second["id"]}"]')
    standing.focus()
    expect(standing).to_be_focused()

    replacement = summarize_thread(
        serve.page_dir,
        first["id"],
        third["id"],
        "All three constraints now form one decision.",
    )
    told(page)
    expect(card.locator(f'[data-summary-id="{old["id"]}"]')).to_have_count(0)
    checkpoint = card.locator(f'[data-summary-id="{replacement["id"]}"]')
    expect(checkpoint.locator(".lf-summary-expand")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(standing).to_be_visible()
    expect(standing).to_be_focused()
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "All three constraints now form one decision."
    )

    card.locator(".lf-msg[data-mid]").evaluate_all(
        """messages => {
          window.__summaryMessageGeometryReads = 0;
          for (const message of messages) {
            const clientRects = message.getClientRects.bind(message);
            const boundingRect = message.getBoundingClientRect.bind(message);
            message.getClientRects = () => {
              window.__summaryMessageGeometryReads += 1;
              return clientRects();
            };
            message.getBoundingClientRect = () => {
              window.__summaryMessageGeometryReads += 1;
              return boundingRect();
            };
          }
        }"""
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest-summary",
            "message": second["id"],
            "text": "The corrected second constraint.",
        },
    )
    told(page)
    expect(card.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(card.locator(f'.lf-msg[data-mid="{first["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-mid="{second["id"]}"]')).to_contain_text(
        "The corrected second constraint."
    )
    expect(card.locator(f'.lf-msg[data-mid="{third["id"]}"]')).to_be_visible()
    assert page.evaluate("() => window.__summaryMessageGeometryReads") == 0


def test_a_summary_cannot_hide_an_active_question(browser, serve):
    """A checkpoint with a user obligation is context, never a closed cover."""
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    question = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "Choose the first job.",
        '<lf-ask id="summary-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="summary-job" choose>'
        '<lf-option id="summary-mounts">Put the mounts back</lf-option>'
        '<lf-option id="summary-camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
        for_event=root,
    )
    summary = summarize_thread(
        serve.page_dir,
        root,
        question["id"],
        "The discussion narrowed the work to two jobs.",
    )

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(checkpoint).to_have_attribute("data-expanded", "true")
    expect(checkpoint.locator(".lf-summary-required")).to_have_text(
        "Messages kept open · current work"
    )
    expect(card.locator("#summary-job")).to_be_visible()
    expect(checkpoint.locator(".lf-summary-expand")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-refold")).to_have_count(0)
    originals = checkpoint.locator(".lf-summary-originals")
    widths = originals.evaluate(
        "originals => ({"
        "available: originals.getBoundingClientRect().width, "
        "message: originals.querySelector('.lf-msg').getBoundingClientRect().width"
        "})"
    )
    assert widths["available"] - widths["message"] < 20, widths


def test_a_held_inline_reply_reveal_yields_to_new_user_focus(browser, serve):
    """The production reply link cannot retake focus after its list reveal settles."""
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "Choose the first job.",
        '<lf-ask id="held-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="held-job" choose>'
        '<lf-option id="held-mounts">Put the mounts back</lf-option>'
        '<lf-option id="held-camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
        for_event=root,
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    destination = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    expect(thread).to_be_hidden()
    hold_visible_thread_presentation(page, root)

    page.locator(
        f'#jobs .lf-page-thread[data-thread="{root}"] .lf-page-thread-open'
    ).click()
    page.wait_for_function(
        "() => window.visibleThreadPresentationHeld === true", timeout=3000
    )
    page.locator(".lf-threads-toggle").focus()
    expect(page.locator(".lf-threads-toggle")).to_be_focused()
    page.evaluate("releaseVisibleThreadPresentation()")
    expect(thread).to_be_visible()
    rendered(page)

    expect(page.locator(".lf-threads-toggle")).to_be_focused()
    expect(destination).not_to_have_class(re.compile(r"\bflash\b"))


def test_inline_settlement_retains_focus_when_its_controls_are_replaced(browser, serve):
    """A page seat keeps focus through settlement when its controls are replaced."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Inline settlement",
                '<h1>Review the plan</h1><lf-verdict id="proposal" asks>'
                "Should these jobs share a visit?</lf-verdict>"
                '<label>Another thought <input id="later"></label>',
            ),
            layer_registry=SEATED_ASK_LAYER,
            layer_widgets=SEATED_ASK_WIDGETS,
        ),
    )
    first = page.locator("#proposal > .lf-thread-seat > .lf-say")
    write(first.locator("leaf-text"), "Please combine the jobs.")
    with sending(page, "the root comment"):
        first.get_by_role("button", name="Send", exact=True).click()
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'.lf-page-thread[data-thread="{root["id"]}"]')
    destination = thread.locator("leaf-text")
    expect(destination).to_have_count(1)
    thread.get_by_role("button", name="Resolve thread", exact=True).focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(thread.get_by_role("button", name="Reopen")).to_be_visible()
    expect(thread).to_be_focused()
    thread.get_by_role("button", name="Reopen").click()
    round_trip(page)
    expect(destination).to_be_focused()

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    for action, optimistic in (
        ("Resolve thread", "Reopen"),
        ("Reopen", "Resolve thread"),
    ):
        with page.expect_request("**/api/event"):
            thread.get_by_role("button", name=action, exact=True).click()
        expect(
            thread.get_by_role("button", name=optimistic, exact=True)
        ).to_have_attribute("aria-busy", "true")
        page.locator("#later").fill("Keep my later focus here.")
        held.pop().continue_()
        round_trip(page)
        expect(page.locator("#later")).to_be_focused()
    page.unroute("**/api/event")


@pytest.mark.parametrize("view", ["inline", "panel"])
def test_resolve_acknowledges_the_press_and_recovers_a_refusal(
    held_events, serve, view
):
    """Both thread views resolve immediately and restore a refused request."""
    browser, held = held_events
    page = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    root = events_model.read_events(serve.page_dir)[0]["id"]
    resized(page, 1440, 900)
    if view == "inline":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        thread = page.locator(".lf-margin-thread")
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-thread[data-id="{root}"]')
        thread.locator(".lf-thread-summary").click()
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_visible()
    resolve.scroll_into_view_if_needed()
    with page.expect_request("**/api/event"):
        resolve.click()
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 0")
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    if view == "inline":
        expect(thread.get_by_role("button", name="Resolve thread")).to_have_count(0)
        expect(page.locator("#bracket")).to_be_focused()
    else:
        expect(page.locator(".lf-threads")).to_contain_text("No open threads.")
        expect(page.locator(".lf-threads")).to_be_focused()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    held.pop().fulfill(
        json={"ok": False, "final": True, "error": "Please retry."},
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 1")
    if view == "inline":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        thread = page.locator(".lf-margin-thread")
        resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    else:
        thread = page.locator(f'.lf-thread[data-id="{root}"]')
        resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(resolve).to_be_enabled()
    expect(resolve).not_to_have_attribute("aria-busy", "true")
    expect(resolve).not_to_have_attribute("aria-keyshortcuts", re.compile(r".*x.*"))
    resolve.focus()
    with page.expect_request("**/api/event"):
        page.keyboard.press("Enter")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 0")
    if view == "panel":
        write(
            page.locator(".lf-general leaf-text"), "My next thought can keep its focus."
        )
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == [root]
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')).to_be_hidden()
    if view == "inline":
        expect(page.locator(".lf-thread-panel")).not_to_have_class(
            re.compile(r"\bopen\b")
        )
        expect(page.locator("#bracket")).to_be_focused()
    else:
        expect(page.locator(".lf-general leaf-text")).to_be_focused()


def test_resolving_one_of_two_threads_leaves_the_user_in_the_card(browser, serve):
    """Resolving a thread the card outlives keeps focus in the card.

    Only the last thread at an anchor closes its margin card, and only that closure hands
    focus back to the anchor. With a second thread standing, the card stays up showing
    it, so the user stays in the card rather than being carried out to the text.
    """
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "anchor": {"section": "bracket"},
    }
    page = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                {**comment, "text": "Check whether these jobs can share one visit."},
                {**comment, "text": "And whether the second visit needs a permit."},
            ],
        ),
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    card = page.locator(".lf-margin-preview")
    resolve = card.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_visible()
    resolve.focus()
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 1")
    expect(card).to_be_visible()
    expect(
        card.get_by_role("button", name="Resolve thread", exact=True)
    ).to_be_visible()
    focus = page.evaluate(
        """() => {
          const active = document.activeElement;
          return {
            inCard: document.getElementById("lf-margin-preview").contains(active),
            on: active?.outerHTML.slice(0, 80),
          };
        }"""
    )
    assert focus["inCard"], (
        f"resolving a thread the card outlives left focus on {focus}"
    )


def test_a_card_repaint_keeps_the_user_on_the_control_they_reached(browser, serve):
    """A repaint of an open card leaves the user's press where they aimed it.

    An open margin card repaints for reasons the user never asked for — a relative
    timestamp ageing, a receipt phase landing, a margin contribution changing — and each
    one re-runs the whole thread render. Nothing in that render is a reason to take the
    user off the control they have reached, so the control they were about to press
    has to still be the one the next key reaches.

    `lf-actions` is the margin's own repaint door, and its render runs inside this call,
    so the state the press reads is stated rather than waited out.
    """
    page = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    root = events_model.read_events(serve.page_dir)[0]["id"]
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const insertBefore = Node.prototype.insertBefore;
          Node.prototype.insertBefore = function(node, before) {
            if (
              this.matches?.('.lf-margin-preview-list') &&
              node.matches?.('.lf-margin-thread')
            ) {
                  window.__lfDetachedThread = Boolean(
                    node.querySelector('.lf-page-thread')
                  );
            }
            return insertBefore.call(this, node, before);
          };
        }"""
    )
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    assert page.evaluate("() => window.__lfDetachedThread"), (
        "the detached margin card reached display before its thread rendered"
    )
    resolve = page.locator(".lf-margin-thread").get_by_role(
        "button", name="Resolve thread", exact=True
    )
    expect(resolve).to_be_visible()
    resolve.focus()
    expect(resolve).to_be_focused()
    page.evaluate("() => document.dispatchEvent(new Event('lf-actions'))")
    expect(resolve).to_be_focused()
    with sending(page, "the resolve the repaint could have unseated"):
        page.keyboard.press("Enter")
    round_trip(page)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == [root]


def test_panel_settlement_moves_focus_with_optimistic_state_and_restores_a_refusal(
    held_events, serve
):
    """Panel focus follows the same optimistic Resolve/Reopen state as its cards.

    A refusal restores both the prior lifecycle view and the thread the user was
    operating. A later accepted attempt keeps the optimistic destination rather than
    moving focus again when the server answers.
    """
    browser, held = held_events
    url = serve(LONG_PAGE)
    first = panel_comment(serve.page_dir, "Keep this first thread in view.")
    second = panel_comment(serve.page_dir, "The next thread receives focus.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    first_card = page.locator(f'.lf-thread[data-id="{first}"]')
    second_card = page.locator(f'.lf-thread[data-id="{second}"]')

    focus_panel_thread(first_card)
    page.keyboard.press("r")
    holding(page, held, 1, "the refused resolve")
    expect(second_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(first_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("c")
    expect(first_card.locator(":scope > .lf-compose leaf-text")).to_be_focused()
    page.keyboard.press("Escape")

    page.keyboard.press("r")
    holding(page, held, 1, "the accepted resolve")
    expect(second_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("c")
    second_reply = second_card.locator(":scope > .lf-compose leaf-text")
    expect(second_reply).to_be_focused()
    held.pop().continue_()
    round_trip(page)
    expect(second_reply).to_be_focused()

    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    page.get_by_role("searchbox", name="Find in threads").fill("first thread")
    focus_panel_thread(first_card)
    expect(first_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("r")
    holding(page, held, 1, "the refused reopen")
    pending_reply = first_card.locator(":scope > .lf-compose leaf-text")
    expect(pending_reply).to_be_focused()
    write(pending_reply, "Keep this draft through the refusal.")
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value(
        "first thread"
    )
    expect(page.locator(".lf-threads")).to_be_focused()

    expect(first_card).to_be_visible()
    focus_panel_thread(first_card)
    page.keyboard.press("r")
    holding(page, held, 1, "the accepted reopen")
    reply = first_card.locator(":scope > .lf-compose leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Keep this draft through the refusal.")
    held.pop().continue_()
    round_trip(page)
    expect(reply).to_be_focused()


def test_a_refused_reopen_preserves_a_filter_typed_during_its_reveal(
    held_events, serve
):
    """A later user search is not the transition state that refusal may restore."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Keep the later search in view.")
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("later search")
    card = page.locator(f'.lf-thread[data-id="{root}"]:not([hidden])')
    expect(card).to_be_visible()
    card.locator(".lf-thread-summary").click()
    rendered(page)
    hold_visible_thread_presentation(page, root)

    card.get_by_role("button", name="Reopen", exact=True).click()
    holding(page, held, 1, "the refused reopen with a held reveal")
    page.wait_for_function(
        "window.visibleThreadPresentationHeld === true", timeout=3000
    )
    find.fill("newer user search")
    expect(find).to_be_focused()
    page.evaluate("releaseVisibleThreadPresentation()")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)

    expect(find).to_have_value("newer user search")
    expect(find).to_be_focused()
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )


def test_a_refused_reopen_preserves_a_filter_typed_during_restoration(
    held_events, serve
):
    """Restoration cannot overwrite user intent that arrives during its own reveal."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Keep the restoration search in view.")
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("restoration search")
    card = page.locator(f'.lf-thread[data-id="{root}"]:not([hidden])')
    expect(card).to_be_visible()
    card.locator(".lf-thread-summary").click()
    rendered(page)

    card.get_by_role("button", name="Reopen", exact=True).click()
    holding(page, held, 1, "the refused reopen whose restoration will wait")
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(find).to_have_value("")

    hold_visible_thread_presentation(page, root)
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.wait_for_function(
        "window.visibleThreadPresentationHeld === true", timeout=3000
    )
    find.fill("newer user search")
    expect(find).to_be_focused()
    page.evaluate("releaseVisibleThreadPresentation()")
    round_trip(page)

    expect(find).to_have_value("newer user search")
    expect(find).to_be_focused()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )


def test_settlement_controls_share_one_request_across_page_and_panel(
    held_events, serve
):
    """Mirrored controls share optimistic resolution, delivery, and reopening."""
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "These jobs can share one visit.",
        },
    )["id"]
    page = open_page(browser, url)
    resized(page, 1920, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    panel = page.locator(f'.lf-thread[data-id="{root}"]')
    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Resolve thread", exact=True).click()
    pending = inline.get_by_role("button", name="Reopen", exact=True)
    expect(pending).to_be_disabled()
    expect(pending).to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-threads")).to_contain_text("No open threads.")
    pending.focus()
    page.keyboard.press("Enter")
    assert len(held) == 1
    held.pop().continue_()
    round_trip(page)
    expect(inline.get_by_role("button", name="Reopen")).to_be_visible()
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == ["resolve"]
    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Reopen").click()
    for thread in (inline, panel):
        optimistic = thread.get_by_role(
            "button", name="Resolve thread", exact=True, include_hidden=True
        )
        expect(optimistic).to_be_disabled()
        expect(optimistic).to_have_attribute("aria-busy", "true")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    for thread in (inline, panel):
        expect(
            thread.get_by_role(
                "button", name="Resolve thread", exact=True, include_hidden=True
            )
        ).to_be_enabled()
    expect(inline.locator("leaf-text")).to_be_visible()
    expect(inline.locator("leaf-text")).to_be_focused()


def test_a_poll_accounted_settlement_repaints_before_its_post_response(
    held_events, serve
):
    """A poll may prove acceptance while the original POST response remains held.

    The poll paints and accounts the receipt first. Delivery then retires the already
    accounted ledger entry, which must invalidate the unchanged thread reading;
    otherwise every mirrored settlement control stays busy until an unrelated clock
    tick or state read.
    """
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Account this resolution from the complete reading.",
        },
    )["id"]
    page = open_page(browser, url)
    resized(page, 1920, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    panel = page.locator(f'.lf-thread[data-id="{root}"]')

    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Resolve thread", exact=True).click()
    holding(page, held, 1, "the resolution whose response remains held")
    pending = inline.get_by_role("button", name="Reopen", exact=True)
    expect(pending).to_be_disabled()
    expect(pending).to_have_attribute("aria-busy", "true")

    # Let exactly the news-triggered state read through. Its receipt accounts the
    # gesture while the page's original POST still has no response, and refusing later
    # reads prevents another poll from hiding a missing local invalidation.
    reads = CutOff(lets_through=1).hold(page)
    route = held.pop()
    accepted = route.fetch()
    told(page)
    reads.cut()
    for settled in (
        inline.get_by_role("button", name="Reopen", exact=True),
        panel.locator(":scope > .lf-thread-actions > .lf-reopen"),
    ):
        expect(settled).to_be_enabled(timeout=1000)
        expect(settled).not_to_have_attribute("aria-busy", "true", timeout=1000)

    route.fulfill(response=accepted)
    page.unroute("**/api/event")
    round_trip(page)


def test_a_sent_comment_is_revealed_in_the_panel(browser, serve):
    """A send is the one gesture that produces a thread, so it gets the same answer a
    click on a page mark does: the panel scrolls the new thread into its scrollport.
    On a list long enough to scroll, the old rebuild appended the comment below the
    fold and put the scroll back where it was — the user's own words landed out of
    sight, silently. Both routes leave the user in the box they sent from."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        "        return t.scrollTop === 0 && t.scrollHeight > t.clientHeight; }"
    ), "this list starts revealed or doesn't scroll, so it proves nothing"

    box = page.locator(".lf-general leaf-text")
    write(box, "Where did my words go?")
    send = page.locator(".lf-general button")
    with sending(page, "the first comment"):
        send.click()
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == ("comment", "Where did my words go?")
    in_threads_scrollport(page, f'.lf-thread[data-id="{sent["id"]}"]')
    assert page.evaluate("() => document.querySelector('.lf-threads').scrollTop") > 0, (
        "the new thread was in view without scrolling, so the reveal proved nothing"
    )
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "")

    write(box, "And the second thought lands the same way.")
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")  # the other route, same destination
    second = events_model.read_events(serve.page_dir)[-1]
    in_threads_scrollport(page, f'.lf-thread[data-id="{second["id"]}"]')
    expect(box).to_be_focused()


def test_a_pasted_image_survives_the_reply_draft_and_renders_from_the_message(
    browser, serve
):
    """Every thread text box shares one paste path, exercised through a reply.

    The binary body becomes page media before its Markdown reference enters the normal
    draft generation. Reload and Send then prove the existing durable-text path owns the
    rest of the loop, down to the exact pixels the rendered message reads back.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Can you show me the rendering fault?",
        {"section": "how-store"},
        "agent",
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()

    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        reply.evaluate(
            """(box, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'rendering.png', {type: 'image/png'}));
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )

    image_markdown = "![Pasted image](/media/051bee487bfb5d13.png)"
    expect(reply).to_have_js_property("value", "")
    draft_image = thread.locator(".lf-composer-media img")
    expect(draft_image).to_be_visible()
    expect(draft_image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    remove = thread.locator(".lf-composer-media-remove")
    expect(remove).to_have_css("border-radius", button_radius(page))
    expect(thread.get_by_role("button", name="Send", exact=True)).to_have_attribute(
        "aria-disabled", "false"
    )

    page.reload()
    wait_until_ready(page)
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    reply = thread.locator("leaf-text")
    expect(reply).to_have_js_property("value", "")
    expect(thread.locator(".lf-composer-media img")).to_be_visible()
    # Mirroring compares the complete draft rather than the text box's projection. A
    # local keystroke must therefore keep the caret where the user put it even while
    # hidden image Markdown rides beside the visible words.
    write(reply, "Fault here")
    reply.evaluate("box => box.setSelectionRange(6, 6)")
    reply.press_sequentially("is ")
    expect(reply).to_have_js_property("value", "Fault is here")

    with sending(page, "the reply containing the pasted image"):
        thread.get_by_role("button", name="Send", exact=True).click()
    saved = events_model.read_events(serve.page_dir)[-1]
    assert (saved["kind"], saved["parent"], saved["text"]) == (
        "reply",
        root,
        f"Fault is here\n\n{image_markdown}",
    )
    image = thread.locator(".lf-msg.user .lf-msg-text img")
    expect(image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    media_open = image.locator("xpath=..")
    expect(media_open).to_have_attribute(
        "data-lf-media-url", "/media/051bee487bfb5d13.png"
    )
    page.wait_for_function(
        "image => image.naturalWidth > 0", arg=image.element_handle()
    )
    url_before = page.url
    media_open.click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    assert viewer.evaluate("dialog => dialog.matches(':modal')")
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    assert page.url == url_before
    viewer.get_by_role("button", name="Close", exact=True).click()
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    media_open.click()
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    expect(viewer.locator("img")).to_have_attribute("alt", "Pasted image")
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    assert (serve.page_dir / "media" / "051bee487bfb5d13.png").read_bytes() == pixels


def test_an_image_only_composer_names_and_lays_out_the_draft_it_keeps(browser, serve):
    """The compact composer reads the complete draft hidden behind its text box.

    Several images make its shelf overflow, proving the anchored box gets the same
    horizontal thumbnail projection as the larger thread text boxes.
    """
    page = open_page(browser, serve(LONG_PAGE))
    page.locator("#p1").click(click_count=3)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()

    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        field.evaluate(
            """(box, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              for (let index = 0; index < 4; index += 1) {
                transfer.items.add(new File(
                  [bytes], `rendering-${index}.png`, {type: 'image/png'}
                ));
              }
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )

    expect(field).to_have_js_property("value", "")
    shelf = page.locator(".lf-fab-bar .lf-composer-media")
    expect(shelf.locator("img")).to_have_count(4)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("close — draft kept")
    layout = shelf.evaluate(
        """element => ({
          display: getComputedStyle(element).display,
          overflowX: getComputedStyle(element).overflowX,
          scrolls: element.scrollWidth > element.clientWidth,
        })"""
    )
    assert layout == {"display": "flex", "overflowX": "auto", "scrolls": True}
    field.evaluate(
        """box => box.addEventListener('input', () => {
          const shelf = box.parentElement.previousElementSibling;
          window.__lfShelfAtInput = {
            hidden: shelf.hidden,
            images: shelf.querySelectorAll(':scope > .lf-composer-media-item').length,
            removeLabels: [...shelf.querySelectorAll('.lf-composer-media-remove')]
              .map(button => button.getAttribute('aria-label')),
          };
        }, {once: true})"""
    )
    shelf.get_by_role("button", name="Remove pasted image 2").click()
    assert page.evaluate("() => window.__lfShelfAtInput") == {
        "hidden": False,
        "images": 3,
        "removeLabels": [
            "Remove pasted image 1",
            "Remove pasted image 2",
            "Remove pasted image 3",
        ],
    }, "the local input event ran before Lit committed the reduced shelf"
    expect(field).to_be_focused()
    expect(shelf.locator("img")).to_have_count(3)
    assert shelf.locator(".lf-composer-media-open").evaluate_all(
        "buttons => buttons.map(button => button.getAttribute('aria-label'))"
    ) == [
        "View pasted image 1",
        "View pasted image 2",
        "View pasted image 3",
    ]
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()


def test_an_arriving_reply_leaves_the_list_where_the_user_put_it(browser, serve):
    """News has no gesture behind it, so it may move nothing the user is looking at.
    The hard case is a reply landing in a thread above the fold: the list grows over
    the user's head, and what must hold still is the thread in front of them — their
    place as a box on screen, not as a scrollTop the browser's own scroll anchoring is
    free to adjust. The old rebuild restored the offset and let the content slide under
    it."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    held = page.evaluate("""() => {
        const box = document.querySelector('.lf-threads');
        box.scrollTop = 400;
        const b = box.getBoundingClientRect();
        window.__held = [...box.querySelectorAll(':scope > .lf-thread')]
            .find(n => n.getBoundingClientRect().top >= b.top);
        return { top: window.__held.getBoundingClientRect().top,
                 scrolled: box.scrollTop > 0 };
    }""")
    assert held["scrolled"], "the list doesn't scroll, so nothing here can move"

    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "News, not a gesture.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    after = page.evaluate(
        "() => ({ connected: window.__held.isConnected,"
        "          top: window.__held.getBoundingClientRect().top })"
    )
    assert after["connected"], "the held thread was replaced, so its box says nothing"
    assert abs(after["top"] - held["top"]) < 1, (
        f"the arriving reply moved the thread the user was on: {held} -> {after}"
    )


def test_an_arriving_reply_cannot_move_resolve_out_from_under_a_press(browser, serve):
    """A state read between the two halves of a mouse press must keep its target put.

    The reply grows the preceding card after the user has pressed Resolve on the next
    one. If reconciliation lets that next card move, mouseup lands on the list instead
    of the button and the browser emits no click at all. Drive the two halves separately
    so the ordering is the test's arrangement rather than a scheduling accident."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[12:14]
    page.locator(f'.lf-thread[data-id="{target}"] .lf-thread-summary').click()
    page.locator(f'.lf-thread[data-id="{target}"]').evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    scroll = page.locator(".lf-threads").evaluate(
        "el => ({at: el.scrollTop, max: el.scrollHeight - el.clientHeight})"
    )
    assert 0 < scroll["at"] < scroll["max"], (
        f"the pressed card is at a scroll limit, so the list cannot hold it: {scroll}"
    )
    resolve = page.locator(f'.lf-thread[data-id="{target}"] .lf-resolve')
    box = resolve.bounding_box()
    point = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
    reading = """([x, y, id]) => {
      const button = document.querySelector(
        `.lf-thread[data-id="${id}"] .lf-resolve`
      );
      const hit = document.elementFromPoint(x, y);
      const list = document.querySelector('.lf-threads');
      return {
        same: hit === button,
        hit: hit && `${hit.tagName.toLowerCase()}.${hit.className}`,
        button: button.getBoundingClientRect().toJSON(),
        card: button.closest('.lf-thread').getBoundingClientRect().toJSON(),
        scrollTop: list.scrollTop,
      };
    }"""
    page.mouse.move(*point)
    page.mouse.down()
    began = page.evaluate(reading, [*point, target])
    assert began["same"], f"the press did not begin on Resolve: {began}"

    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": source,
            "text": "This arrived while Resolve was held down.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    arrived = page.evaluate(reading, [*point, target])
    assert arrived["same"], (
        f"the arriving reply moved Resolve out from under the pointer: "
        f"{began} -> {arrived}"
    )

    with page.expect_request("**/api/event"):
        page.mouse.up()
    round_trip(page)
    assert any(
        event["kind"] == "resolve" and event["parent"] == target
        for event in events_model.read_events(serve.page_dir)
    ), "mouseup did not complete the Resolve press"


def test_opening_a_thread_leaves_its_title_where_the_user_pressed_it(browser, serve):
    """The list's named disclosure closes the card that was open, and when that card is
    above the one being opened every title below it comes up by its whole open height.
    The user pressed a title, so the title is what must stay put: let it travel and the
    thread they just opened is somewhere else, and from the first visible row it leaves
    the scrollport entirely — the panel answers a press with the middle of a message and
    no title over it. Native anchoring holds whichever node it picked, which is the
    pressed card only when it happened to pick it, so the list holds the card itself.

    Press with a real pointer: the hold reads the card under it, and that is the route
    the geometry breaks on."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    above, target = roots[10:12]
    page.locator(f'.lf-thread[data-id="{above}"] > .lf-thread-summary').click()
    rendered(page)
    page.locator(f'.lf-thread[data-id="{target}"]').evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    rendered(page)
    scroll = page.locator(".lf-threads").evaluate(
        "el => ({at: el.scrollTop, max: el.scrollHeight - el.clientHeight})"
    )
    assert 0 < scroll["at"] < scroll["max"], (
        f"the pressed title is at a scroll limit, so the list has no room to hold it "
        f"and the reading below would be about the limit instead: {scroll}"
    )

    title = page.locator(f'.lf-thread[data-id="{target}"] > .lf-thread-summary')
    before = title.evaluate("el => el.getBoundingClientRect().top")
    # The room has to close above the title, or nothing below it moves and this reading
    # would pass on a list that never held anything.
    standing = page.locator(f'.lf-thread[data-id="{above}"]').evaluate(
        "el => el.getBoundingClientRect().toJSON()"
    )
    assert standing["bottom"] <= before, (
        f"the open card is not above the title being pressed, so closing it takes no "
        f"room out from under it: {standing} against {before:.1f}px"
    )
    opened = standing["height"]
    box = title.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.locator(f'.lf-thread[data-id="{target}"][open]')).to_have_count(1)
    rendered(page)

    closed = page.locator(f'.lf-thread[data-id="{above}"]').evaluate(
        "el => el.getBoundingClientRect().height"
    )
    assert opened - closed > 100, (
        f"the card above gave back {opened - closed:.0f}px, which is too little room "
        f"for this reading to say anything about holding the title still"
    )
    after = title.evaluate("el => el.getBoundingClientRect().top")
    # A few pixels are the browser's own: pressing a title focuses it, and a focus at
    # the list's edge is revealed by the list's scroll-padding.
    assert after == pytest.approx(before, abs=8), (
        f"opening the thread carried its title from {before:.1f}px to {after:.1f}px, "
        f"{opened - closed:.0f}px of room having closed above it"
    )
    in_threads_scrollport(page, f'.lf-thread[data-id="{target}"] > .lf-thread-summary')


def test_a_work_claim_cannot_move_a_later_control_under_the_pointer(browser, serve):
    """A claim-only poll grows one card without reconciling the thread list itself.

    The work-line writer shares the list's hold so provisional news arriving above a
    control cannot move that control out from under a user who is aiming at it."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[2:4]
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    target_box = target_card.bounding_box()
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + target_box["height"] / 2,
    )
    before = target_card.evaluate("el => el.getBoundingClientRect().top")

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "reading the traces",
            "--on",
            source,
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    expect(
        page.locator(f'.lf-thread[data-id="{source}"] .lf-thread-status')
    ).to_have_text("Working")
    after = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=1), (
        f"the work claim moved the later card from {before:.1f}px to {after:.1f}px"
    )


def test_a_new_sent_message_does_not_hide_work_on_an_earlier_message(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Check the capacity.", {"section": "how-cap"})
    active = CliRunner().invoke(
        cli_model.cli,
        ["status", str(serve.page_dir), "working", "checking capacity", "--on", root],
    )
    assert active.exit_code == 0, active.output
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    status = page.locator(f'.lf-thread[data-id="{root}"] .lf-thread-status')
    expect(status).to_have_text("Working")
    later = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": root,
            "text": "Also consider slower devices.",
        },
    )
    told(page)
    workflow = page.locator(f'.lf-msg[data-mid="{later["id"]}"] .lf-msg-sending')
    expect(workflow).to_have_text("Sent")
    assert workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    ), "the message status did not follow its relative timestamp"
    expect(status).to_have_text("Working")


def test_a_card_moved_on_a_board_in_a_reply_reports_delivery_on_that_reply(
    browser, serve
):
    """A board the agent sent in a reply takes a moved card as a page board does: the
    reply carrying the board reports the move's delivery, and the thread stays nobody's
    turn, since the move answers no Ask. The agent's next turn in the thread takes the
    move in, and the receipt leaves."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Lay the work out.", {"section": "how-cap"})
    board = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "responds": root,
            "text": "Here is the board.",
            "markup": '<lf-board id="fb"><lf-column id="fb-todo" label="To do">'
            '<lf-card id="fb-cache"><strong>Cache</strong></lf-card></lf-column>'
            '<lf-column id="fb-done" label="Done"></lf-column></lf-board>',
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    status = page.locator(f'.lf-thread[data-id="{root}"] .lf-thread-status')
    receipt = page.locator(f'.lf-msg[data-mid="{board["id"]}"] .lf-msg-sending')
    expect(status).to_have_count(0)

    page.locator("#fb-cache .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    with sending(page, "the card move"):
        page.keyboard.press("Enter")
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()
    expect(receipt).to_have_text("Sent")
    expect(status).to_have_count(0)

    [moved] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(transaction, [moved])
    told(page)
    expect(receipt).to_have_text("Picked up")
    expect(status).to_have_count(0)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "text": "Cache is done, then.",
        },
    )
    told(page)
    expect(receipt).to_have_count(0)
    expect(page.locator("#fb-done > #fb-cache")).to_be_visible()


def test_an_arrival_interrupts_nothing_the_user_holds(browser, serve):
    """The nodes themselves survive the poll: the thread being typed in is the same
    element afterwards, still focused, caret where the typing left it — even when the
    arrival lands inside that very thread, right above the reply box. The rebuild
    could only approximate this by saving and restoring focus and caret by hand, and
    the two send routes proved the restore had holes."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    ta = page.locator(".lf-threads > .lf-thread:not([hidden])").first.locator(
        "leaf-text"
    )
    ta.click()
    ta.type("half a thought")
    page.evaluate("""() => {
        document.activeElement.setSelectionRange(4, 4);
        window.__heldEditor = document.activeElement;
        window.__probe = document.activeElement.closest('.lf-thread');
    }""")

    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "Landing right above the box being typed in.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("""() => {
        const ta = document.activeElement;
        return ta.localName === 'leaf-text'
            && ta === window.__heldEditor
            && ta.closest('.lf-thread') === window.__probe
            && window.__probe === document.querySelector('.lf-threads > .lf-thread')
            && ta.value === 'half a thought'
            && ta.selectionStart === 4 && ta.selectionEnd === 4;
    }"""), "the poll replaced or disturbed the node the user was typing into"


def test_opening_message_reactions_does_not_reflow_the_thread_list(browser, serve):
    """The picker floats from its message corner without moving the thread.

    A reaction list used to add forty pixels to its thread only while open. That moved
    every later thread under the pointer and made choosing a reaction change the layout
    being acted on. The next card is the single-factor neighbor: opening the picker is
    the only change between these two frames."""
    url = serve(PANEL_PAGE)
    first = panel_comment(
        serve.page_dir, "Keep the route visible.", {"section": "how-store"}
    )
    events_model.append_event(
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
    second = panel_comment(
        serve.page_dir, "Keep the cap visible too.", {"section": "how-cap"}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{first}"]')
    neighbor = page.locator(f'.lf-thread[data-id="{second}"]')
    card.locator(".lf-thread-summary").click()
    trigger = card.locator(".lf-msg.agent .lf-react-trigger")
    assert trigger.evaluate("b => getComputedStyle(b).backgroundColor") == (
        "rgba(0, 0, 0, 0)"
    )
    trigger.hover()
    expect(trigger).to_have_css("background-color", token_colour(page, "--chip"))
    expect(trigger).to_have_css("border-top-color", token_colour(page, "--border-2"))
    before = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }

    trigger.click()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    palette = card.locator(".lf-react-palette")
    expect(palette).to_be_visible()
    after = {
        "card": card.bounding_box(),
        "neighbor": neighbor.bounding_box(),
    }
    assert after == before
    assert palette.bounding_box()["y"] >= (
        trigger.bounding_box()["y"] + trigger.bounding_box()["height"]
    )


def test_resolving_an_early_thread_keeps_the_rest_in_place(browser, serve):
    """A thread can move, not just appear: resolving the first one hides it from the
    Open state while every surviving node stays put. The Resolved facet updates without
    changing the user's selected state."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    page.evaluate(
        """(id) => { window.__second = document.querySelector(`.lf-thread[data-id="${id}"]`); }""",
        c2,
    )

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-thread-summary').click()
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    # The resolved node took the pressed button with it; focus lands on the thread
    # that now holds its place rather than falling to body.
    expect(
        page.locator(f'.lf-thread[data-id="{c2}"] > .lf-thread-summary')
    ).to_be_focused()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(
        page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"][hidden]')
    ).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] leaf-text')).to_have_count(0)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 2")
    # The survivor stays the same node.
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply c"
    )
    assert page.evaluate(
        """(id) => window.__second === document.querySelector(`.lf-thread[data-id="${id}"]`)""",
        c2,
    ), "renumbering rebuilt the surviving thread"

    # A thread leaving mid-list puts every survivor one place forward. Standing still
    # there is the reconcile's own duty, not the browser's: a survivor reinserted at
    # its new place is the same element and passes any identity probe, but reinsertion
    # drops the caret typing in it.
    page.locator(f'.lf-thread[data-id="{c3}"] .lf-thread-summary').click()
    ta3 = page.locator(f'.lf-thread[data-id="{c3}"] leaf-text')
    ta3.click()
    ta3.type("held mid-sentence")
    page.evaluate("() => document.activeElement.setSelectionRange(4, 4)")
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": c2}
    )
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (2)")
    expect(ta3).to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.value === 'held mid-sentence'"
        "   && document.activeElement.selectionStart === 4"
    ), "the thread after the one that resolved was reinserted under the typing"


def test_a_failed_thread_list_update_retries_one_coherent_reading(browser, serve):
    """A failed child paint restores the retained card before retrying its reading."""
    url = serve(LONG_PAGE, comments=2)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": roots[0]},
    )
    root = roots[1]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 open thread")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 1")
    page.evaluate(
        """async (id) => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          const {ThreadView} = await window.__lfRuntimeImport(
            '/runtime/thread/thread-card.js'
          );
          const list = document.querySelector('leaf-thread-list');
          const presentCard = ThreadView.prototype.present;
          let armed = true;
          ThreadView.prototype.present = function(model) {
            const node = presentCard.call(this, model);
            if (armed && model.id === id && (model.folding || model.resolved)) {
              armed = false;
              window.threadChildFailed = true;
              throw new Error('injected thread-card failure');
            }
            return node;
          };
          const presentList = list.present.bind(list);
          let release;
          const held = new Promise(done => { release = done; });
          list.present = async model => {
            const candidate = model.rows.find(row =>
              row.kind === 'thread' && row.descriptor.id === id)?.descriptor;
            if (window.threadChildFailed && candidate?.resolved &&
                !window.threadRetryReleased) {
              window.threadRetryHeld = true;
              await held;
            }
            return presentList(model);
          };
          window.releaseThreadRetry = () => {
            window.threadRetryReleased = true;
            release();
          };
          window.threadListPresentation = presentation;
          window.committedThread = document.querySelector(
            `.lf-thread[data-id="${id}"]`
          );
          window.committedMessage = committedThread.querySelector(
            `:scope > .lf-msg[data-mid="${id}"]`
          );
          window.committedEditor = committedThread.querySelector(
            ':scope > .lf-compose leaf-text'
          );
          window.committedResolve = committedThread.querySelector(
            ':scope .lf-thread-meta-actions > .lf-resolve'
          );
        }""",
        root,
    )
    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    page.evaluate(
        'id => document.querySelector(`.lf-thread[data-id="${id}"] .lf-resolve`)'
        ".click()",
        root,
    )
    page.wait_for_function(
        "() => window.threadChildFailed && window.threadRetryHeld && "
        "window.threadListPresentation.readApplicationPresentation().pending"
        ".includes('thread')",
        timeout=5000,
    )

    recovered = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(recovered).to_have_count(1)
    expect(recovered).to_be_visible()
    expect(recovered).to_have_attribute("data-resolved", "false")
    expect(recovered.locator("leaf-text")).to_have_count(1)
    expect(recovered.locator(".lf-reopen")).to_have_count(0)
    retained = page.evaluate(
        """id => {
          const thread = document.querySelector(`.lf-thread[data-id="${id}"]`);
          return {
            thread: thread === window.committedThread,
            message: thread.querySelector(`:scope > .lf-msg[data-mid="${id}"]`) === window.committedMessage,
            editor: thread.querySelector(':scope > .lf-compose leaf-text') === window.committedEditor,
            resolve: thread.querySelector(':scope .lf-thread-meta-actions > .lf-resolve') === window.committedResolve,
          };
        }""",
        root,
    )
    assert all(retained[key] for key in ("thread", "message", "editor", "resolve")), (
        f"rollback replaced a retained card, message, editor, or control: {retained}"
    )
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 open thread")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 1")

    page.evaluate("window.releaseThreadRetry()")
    page.wait_for_function(
        "() => !window.threadListPresentation.readApplicationPresentation().pending.length"
    )
    expect(recovered).to_be_hidden()
    expect(recovered).to_have_attribute("data-resolved", "true")
    expect(recovered.locator("leaf-text")).to_have_count(0)
    expect(recovered.locator(".lf-reopen")).to_have_count(1)
    assert page.evaluate(
        'id => document.querySelector(`.lf-thread[data-id="${id}"]`) '
        "=== window.committedThread",
        root,
    ), "successful retry replaced the retained card"
    expect(page.locator(".lf-thread-view-summary")).to_have_text("0 open threads")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 0")
    assert take_browser_errors(page) == [
        "leaf: Presentation failed: injected thread-card failure"
    ]
    holding(page, held_events, 2, "the gesture and the page's report of its failure")
    for route in held_events:
        route.continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_failed_narrowing_restore_has_one_owned_presentation_error(browser, serve):
    """A discarded filter repaint cannot turn its owned failure into pageerror."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate(
        """() => {
          const list = document.querySelector('leaf-thread-list');
          const render = list.render.bind(list);
          let failures = 2;
          list.render = () => {
            if (failures-- > 0) throw new Error('deliberate narrowing failure');
            return render();
          };
        }"""
    )

    page.get_by_role("searchbox", name="Find in threads").fill("comment")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expected = [
        (
            "leaf: Presentation failed: Thread list presentation and retention failed: "
            "deliberate narrowing failure; deliberate narrowing failure"
        )
    ]
    assert take_browser_errors(page) == expected

    page.get_by_role("searchbox", name="Find in threads").fill("")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )


def test_a_failed_narrowing_view_restores_its_committed_list_and_keeps_the_input(
    browser, serve
):
    """The narrowing face shares the list's checkpoint without owning native editing."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    view = page.locator("leaf-thread-narrowing")
    find = page.get_by_role("searchbox", name="Find in threads")
    page.evaluate(
        """() => {
          const view = document.querySelector('leaf-thread-narrowing');
          const present = view.present.bind(view);
          let failures = 2;
          view.present = model => {
            const result = present(model);
            if (model.summary === '1 of 2 open threads' && failures-- > 0)
              throw new Error('injected narrowing-view failure');
            return result;
          };
          window.__lfNarrowingBeforeFailure = {
            view,
            input: view.querySelector('.lf-find-box'),
            toggle: view.querySelector('.lf-thread-filter-toggle'),
            open: view.querySelector('[data-filter-value="open"]'),
          };
        }"""
    )

    find.evaluate(
        """input => {
          input.focus();
          input.value = 'Comment 0';
          input.setSelectionRange(2, 7);
          input.dispatchEvent(new InputEvent('input', {bubbles: true, composed: true}));
        }"""
    )
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )

    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    expect(page.locator(".lf-thread-view-summary")).to_have_text("2 open threads")
    expect(page.locator('[data-filter-value="open"]')).to_have_text("Open (2)")
    expect(page.locator(".lf-thread-filter-toggle")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(find).to_have_value("Comment 0")
    expect(find).to_be_focused()
    assert find.evaluate("input => [input.selectionStart, input.selectionEnd]") == [
        2,
        7,
    ]
    assert view.evaluate(
        """view => {
          const before = window.__lfNarrowingBeforeFailure;
          return before.view === view &&
            before.input === view.querySelector('.lf-find-box') &&
            before.toggle === view.querySelector('.lf-thread-filter-toggle') &&
            before.open === view.querySelector('[data-filter-value="open"]');
        }"""
    )
    assert take_browser_errors(page) == [
        (
            "leaf: Presentation failed: Thread list presentation retry failed: "
            "injected narrowing-view failure; injected narrowing-view failure"
        )
    ]

    find.fill("")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )


def test_a_failed_reopen_reveal_still_processes_its_durable_answer(held_events, serve):
    """A follow-up presentation fault cannot reject the discarded click handler."""
    browser, held = held_events
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": root},
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    page.locator(".lf-thread:not([hidden]) .lf-thread-summary").click()
    rendered(page)
    page.evaluate(
        """() => {
          const list = document.querySelector('leaf-thread-list');
          const render = list.render.bind(list);
          let failures = 2;
          list.render = () => {
            const row = list.model.rows.find(({kind}) => kind === 'thread');
            if (row?.descriptor.visible && failures-- > 0)
              throw new Error('deliberate reveal failure');
            return render();
          };
          const retain = list.retainCommitted.bind(list);
          let retentions = 0;
          list.retainCommitted = (...args) => {
            if (++retentions === 2)
              throw new Error('deliberate retry retention failure');
            return retain(...args);
          };
        }"""
    )

    page.get_by_role("button", name="Reopen", exact=True).click()
    holding(page, held, 2, "the reopen and its presentation report")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expected = [
        (
            "leaf: Presentation failed: Thread list presentation and retention failed: "
            "Thread list presentation retry failed: deliberate reveal failure; "
            "deliberate reveal failure; deliberate retry retention failure"
        )
    ]
    assert take_browser_errors(page) == expected

    routes = {route.request.post_data_json["kind"]: route for route in held}
    held.clear()
    routes["error"].continue_()
    route = routes["unresolve"]
    route.fulfill(
        json={
            "ok": False,
            "final": True,
            "attempt": route.request.post_data_json["attempt"],
            "error": "Please retry.",
        }
    )
    round_trip(page)
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js');
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(f'.lf-thread[data-id="{root}"]')).to_be_visible()
    expect(
        page.get_by_role("button", name="Reopen", exact=True, include_hidden=True)
    ).to_have_count(1)


def test_an_approval_made_elsewhere_reaches_the_panel_and_the_banner(browser, serve):
    """An accepted approval is a semantic fact, so it moves the epoch on its own.

    Nothing else about this state read changes: no thread, no Ask, no widget state, no
    pending gesture of this user's. The approval is another tab's, so there is no
    receipt to account and no ledger entry to remove — the two paints that show it have
    only the published fold to hear it from.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    approve = page.locator(".lf-signoff")
    expect(approve).to_have_text("Approve version")
    expect(page.locator(".lf-threads")).not_to_contain_text("Approved")
    thread = page.locator(".lf-threads > .lf-thread")
    separator = page.locator(".lf-general").evaluate(
        "node => getComputedStyle(node).borderTopColor"
    )
    assert (
        thread.evaluate("node => getComputedStyle(node).borderBottomColor") != separator
    )

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "done",
            "author": "user",
            "version": 1,
        },
    )
    told(page)

    expect(page.locator(".lf-threads")).to_contain_text("Approved")
    expect(approve).to_have_text("✓ Version approved")
    assert (
        thread.evaluate("node => getComputedStyle(node).borderBottomColor") == separator
    )


def test_the_thread_clock_reopens_its_same_epoch_ticket(browser, serve):
    """A system-row age is presented mechanically without advancing semantic time."""
    url = serve(LONG_PAGE, comments=1)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "done",
            "author": "user",
            "version": 1,
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    system = page.locator(".lf-threads > .lf-system")
    expect(system).to_have_text("✓ Approved just now")
    before = page.evaluate(
        """async () => {
          const list = document.querySelector('leaf-thread-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.scheduleUpdate = () => {
            if (!armed) return schedule();
            armed = false;
            return held.then(schedule);
          };
          window.releaseThreadClock = release;
          window.threadPresence = await window.__lfRuntimeImport(
            '/runtime/presence.js'
          );
          window.threadPresentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          return threadPresentation.readApplicationPresentation();
        }"""
    )
    held = page.evaluate(
        """() => {
          threadPresence.observeServerNow(
            new Date(Date.now() + 60_000).toISOString()
          );
          window.threadClockTick = threadPresence.tickClock(() => {});
          window.threadClockReady = false;
          threadPresentation.whenApplicationPresented().then(() => {
            window.threadClockReady = true;
          });
          const reading = threadPresentation.readApplicationPresentation();
          return {
            pending: reading.pending,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
            ready: threadClockReady,
          };
        }"""
    )
    assert "thread" in held["pending"]
    assert held["semanticEpoch"] == before["semanticEpoch"]
    assert held["presentedEpoch"] == before["presentedEpoch"]
    assert held["ready"] is False

    page.evaluate("releaseThreadClock()")
    page.wait_for_function("threadClockReady", timeout=3000)
    page.evaluate("threadClockTick")
    expect(system).to_have_text("✓ Approved 1m ago")
    after = page.evaluate("threadPresentation.readApplicationPresentation()")
    assert after["semanticEpoch"] == before["semanticEpoch"]
    assert after["presentedEpoch"] == before["presentedEpoch"]


def test_the_panel_reads_the_thread_in_the_pages_own_order(browser, serve):
    """The list is the page's order, not the log's. A user walking a long
    thread walks it the way they walk the prose it is about, and every other
    reading of these threads already does: the marks down the page and the t/T walk. So
    the threads are written here in the reverse of the page's order and
    the panel is asked for its own, which is only the page's if something sorted it.

    A thread with nowhere in the page to be — a comment about the whole of it — comes
    after the ones that have somewhere, rather than at the moment it happened to be
    written. The list is threads alone: no heading stands among them."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    whole = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "about": "design",
            "text": "The middle third is too long.",
        },
    )["id"]
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})
    cap = panel_comment(d, "Is forty enough?", {"section": "how-cap"})
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(LIST_ORDER) == [
        lede,
        cap,
        merge,
        whole,
    ], "the panel is not reading in the page's order"
    expect(page.locator(".lf-threads > :not(.lf-thread)")).to_have_count(0)

    # A design comment about the page as a whole has an address to show but no passage
    # to return to. It is a static label, not a broken anchored-thread control.
    whole_label = page.locator(f'.lf-thread[data-id="{whole}"] .lf-quote')
    expect(whole_label).to_have_text("design · the page")
    expect(whole_label).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(whole_label).not_to_have_attribute("role", "button")

    expect(page.locator(f'.lf-thread[data-id="{lede}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    # From no place on the page the walk starts at the list's first thread; a caret a
    # click leaves is a place, as it is for `a`.
    page.evaluate(
        "() => { document.activeElement?.blur(); getSelection().removeAllRanges(); }"
    )
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()


def test_two_standard_thread_lists_share_updates_but_not_local_state(browser, serve):
    """Two registered panels follow one Thread publication while retaining their own
    search and native details group."""
    url = serve(
        PANEL_PAGE,
        events=[
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Alpha thread",
            },
            {"kind": "comment", "author": "user", "revision": 1, "text": "Beta thread"},
        ],
    )
    first_id, second_id = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    authored = thread_model.cmd_reply(
        serve.page_dir,
        first_id,
        "Choose the deployment window.",
        '<lf-ask id="two-panel-decision"><h3>Deployment window</h3>'
        '<lf-options id="two-panel-window" choose>'
        '<lf-option id="today">Today</lf-option>'
        '<lf-option id="tomorrow">Tomorrow</lf-option>'
        "</lf-options></lf-ask>",
        for_event=first_id,
    )
    page = open_page(browser, url)
    page.evaluate(
        """async () => {
          const [{ createThreadPanelElements }, { createThreadListController },
            { createThreadNarrowing }, { threadList },
            { registerThreadPanel, refreshThread }] = await Promise.all([
              window.__lfRuntimeImport('/runtime/thread/panel-elements.js'),
              window.__lfRuntimeImport('/runtime/thread/thread-list.js'),
              window.__lfRuntimeImport('/runtime/thread/narrowing.js'),
              window.__lfRuntimeImport('/runtime/thread/state.js'),
              window.__lfRuntimeImport('/runtime/application.js'),
            ]);
          const host = document.createElement('div');
          host.style.cssText = 'display:flex; gap:24px; position:relative; z-index:50';
          document.body.append(host);
          const mount = () => {
            const elements = createThreadPanelElements();
            const { panel, threadsBox, narrowingView } = elements;
            panel.style.cssText = 'position:relative; inset:auto; width:420px; height:560px; margin:0';
            host.append(panel);
            panel.show();
            const controller = createThreadListController(elements);
            let handle;
            const narrowing = createThreadNarrowing({
              view: narrowingView,
              listRoot: threadsBox,
              readThreads: threadList,
              ready: () => true,
              repaint: () => handle.update(),
            });
            narrowing.mount();
            handle = registerThreadPanel({
              controller,
              threadsBox,
              view: {
                narrowing,
                panelIsOpen: () => true,
                scrollToElement: () => {},
                setThreadCounts: () => {},
                onListChanged: () => {},
                refreshAnchorHover: () => {},
                travel: {
                  showThread: () => {},
                  retainPanelLanding: () => {},
                  retainNarrowing: () => {},
                },
              },
            });
            controller.mountThreadList(() => true);
            return { ...elements, handle };
          };
          window.__testThreadPanels = [mount(), mount()];
          await refreshThread();
        }"""
    )

    ids = page.evaluate("() => window.__testThreadPanels.map(({ panel }) => panel.id)")
    assert len({"lf-threads", *ids}) == 3
    a = page.locator(f"#{ids[0]}")
    b = page.locator(f"#{ids[1]}")
    expect(a.locator(".lf-thread")).to_have_count(2)
    expect(b.locator(".lf-thread")).to_have_count(2)
    expect(
        page.locator(
            f'#lf-threads .lf-msg[data-mid="{authored["id"]}"] #two-panel-window'
        )
    ).to_have_count(1)
    expect(a.locator("#two-panel-window")).to_have_count(0)
    expect(b.locator("#two-panel-window")).to_have_count(0)
    expect(
        a.get_by_role("button", name="Open interactive reply in Threads")
    ).to_have_count(1)
    expect(
        b.get_by_role("button", name="Open interactive reply in Threads")
    ).to_have_count(1)
    a.get_by_role("searchbox", name="Find in threads").fill("Alpha")
    expect(a.locator(f'.lf-thread[data-id="{second_id}"]')).to_be_hidden()
    expect(b.locator(f'.lf-thread[data-id="{second_id}"]')).to_be_visible()

    # A package panel may take longer to paint. It cannot hold the core Thread
    # presentation ticket or stall a sibling panel's reading.
    page.evaluate(
        """() => {
          const box = window.__testThreadPanels[0].threadsBox;
          const present = box.present.bind(box);
          const waiting = [];
          box.present = (model) => new Promise((resolve) => waiting.push({ model, resolve }));
          window.__releaseHeldPanel = () => {
            box.present = present;
            for (const { model, resolve } of waiting) resolve(present(model));
          };
        }"""
    )

    later = events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Gamma thread"},
    )
    told(page)
    expect(
        page.locator(f'#lf-threads .lf-thread[data-id="{later["id"]}"]')
    ).to_have_count(1)
    expect(a.locator(".lf-thread")).to_have_count(2)
    expect(b.locator(f'.lf-thread[data-id="{later["id"]}"]')).to_be_visible()
    pending = page.evaluate(
        """async () => {
          const { readApplicationPresentation } = await window.__lfRuntimeImport('/runtime/semantic-state.js');
          return readApplicationPresentation().pending;
        }"""
    )
    assert "thread" not in pending
    page.evaluate("() => window.__releaseHeldPanel()")
    expect(a.locator(f'.lf-thread[data-id="{later["id"]}"]')).to_be_hidden()
    expect(b.locator(f'.lf-thread[data-id="{later["id"]}"]')).to_be_visible()
    expect(a.locator(".lf-thread")).to_have_count(3)
    expect(b.locator(".lf-thread")).to_have_count(3)

    a.get_by_role("searchbox", name="Find in threads").fill("")
    first_a = a.locator(f'.lf-thread[data-id="{first_id}"]')
    second_a = a.locator(f'.lf-thread[data-id="{second_id}"]')
    first_b = b.locator(f'.lf-thread[data-id="{first_id}"]')
    second_a.locator(":scope > summary").click()
    first_b.locator(":scope > summary").click()
    expect(second_a).to_have_attribute("open", "")
    expect(first_b).to_have_attribute("open", "")
    first_a.locator(":scope > summary").click()
    expect(second_a).not_to_have_attribute("open", "")
    expect(first_b).to_have_attribute("open", "")
    assert second_a.get_attribute("name") == a.get_attribute("id")
    assert first_b.get_attribute("name") == b.get_attribute("id")

    page.evaluate("() => window.__testThreadPanels[1].handle.unregister()")
    after_removal = events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Delta thread"},
    )
    told(page)
    expect(a.locator(f'.lf-thread[data-id="{after_removal["id"]}"]')).to_be_visible()
    expect(b.locator(f'.lf-thread[data-id="{after_removal["id"]}"]')).to_have_count(0)


def test_recent_order_lists_threads_by_their_latest_message(browser, serve):
    """Order is the panel's own view, not a filter. Recent puts the thread spoken in
    last at the top. The View control keeps one label whatever is
    chosen, and a narrowed summary arriving never moves the choices under the press.
    Reset clears refinements but keeps the order, and with the panel shut t/T still
    walk the page's order."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    now = datetime.now().astimezone()

    def comment(text, anchor, days_ago):
        event = {"kind": "comment", "author": "user", "revision": 1, "text": text}
        if anchor:
            event["anchor"] = anchor
        event["ts"] = (now - timedelta(days=days_ago)).isoformat(timespec="seconds")
        return events_model.append_event(d, event)["id"]

    lede = comment("Six weeks reads long.", {"section": "lede"}, 10)
    cap = comment("Is forty enough?", {"section": "how-cap"}, 3)
    whole = comment("The whole thing needs a summary.", None, 12)
    # A reply today makes the oldest thread the most recent one.
    thread_model.cmd_reply(d, whole, "Added one at the top.", None, for_event=whole)

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    order = page.get_by_role("group", name="Order", exact=True)
    expect(order.get_by_role("button", name="Page")).to_have_attribute(
        "aria-pressed", "true"
    )
    toggle = page.locator(".lf-thread-filter-toggle")
    expect(toggle).to_have_text("View")
    order.get_by_role("button", name="Recent").click()
    expect(toggle).to_have_text("View")
    assert page.evaluate(LIST_ORDER) == [whole, cap, lede]

    # Order hides nothing, so it is not part of what Reset puts back. The summary
    # stands below the choices, not above them, so what a press changes in it moves
    # none of them.
    anchored = page.get_by_role("group", name="Location", exact=True).get_by_role(
        "button", name=re.compile(r"^Anchored")
    )
    before = anchored.bounding_box()
    reset = page.get_by_role("button", name="Reset thread filters")
    expect(reset).to_be_hidden()
    anchored.click()
    expect(reset).to_be_visible()
    assert anchored.bounding_box() == before, "the summary moved the choices"
    shown = LIST_ORDER.replace(".map(", ".filter((n) => !n.hidden).map(", 1)
    assert page.evaluate(shown)[:1] == [cap]
    page.get_by_role("button", name="Reset thread filters").click()
    assert page.evaluate(shown)[:1] == [whole]
    expect(order.get_by_role("button", name="Recent")).to_have_attribute(
        "aria-pressed", "true"
    )

    # The panel's walk follows the list it shows.
    page.locator(".lf-threads").focus()
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{whole}"] > .lf-thread-summary')
    ).to_be_focused()

    # Page order restores the page's order.
    order.get_by_role("button", name="Page").click()
    assert page.evaluate(LIST_ORDER) == [lede, cap, whole]

    # The page's walk is the page's order whatever the panel shows.
    # From no place on the page, which is where the walk starts from its first thread:
    # a caret a click leaves is a place, as it is for `a`.
    order.get_by_role("button", name="Recent").click()
    page.locator(".lf-threads-toggle").click()
    page.evaluate(
        "() => { document.activeElement?.blur(); getSelection().removeAllRanges(); }"
    )
    page.keyboard.press("t")
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    assert (
        page.evaluate(
            "() => document.activeElement.closest('[data-thread]').dataset.thread"
        )
        == lede
    )


def test_back_returns_from_a_thread_the_walk_travelled_to(browser, serve):
    """A journey of trips to threads somewhere else leaves one history entry however
    far it goes, so Back returns to the place the user was reading before it and
    Forward to where it ended. Reading somewhere else ends the journey: the next trip
    records that place."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back from a thread",
            "<h1>Back from a thread</h1>"
            "<section id=near><p>The first question sits at the top.</p></section>"
            f"<section id=above>{filler}</section>"
            "<section id=also><p>A second question sits halfway down.</p></section>"
            f"<section id=below>{filler}</section>",
        )
    )
    for section in ("near", "also"):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": section},
                "text": f"A question about {section}.",
            },
        )
    page = open_page(browser, url)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("t")
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    first = page.evaluate(
        "document.activeElement.closest('[data-thread]').dataset.thread"
    )
    page.keyboard.press("t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-thread]')?.dataset.thread"
        " !== first",
        arg=first,
    )
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked > landed + 1000
    assert page.evaluate("history.length") == entries + 1

    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )
    page.go_forward()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=walked,
    )

    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    elsewhere = page.evaluate("document.scrollingElement.scrollTop")
    assert elsewhere > walked + 1000
    # Either thread is somewhere else from here; which one Shift+t lands on depends
    # on whether the walk's card survived the traversal, and the claim does not.
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=elsewhere
    )
    scroll_settled(page)
    assert page.evaluate("history.length") == entries + 2
    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=elsewhere,
    )


def test_a_thread_on_words_a_widget_renders_stands_where_the_widget_does(
    browser, serve
):
    """A widget may render the page's words into a declared shadow tree, and a passage
    inside one is placed inside that tree. Asked to compare it with an element of the
    document, `compareDocumentPosition` answers "disconnected" in an order of its own
    choosing, and `contains` answers no across the same boundary — so the thread would
    sort and group by something the user has never seen.

    The host is the element the page holds, and where the page holds it is where those
    words are. So the thread reads after the paragraphs above the widget and before
    the ones below it."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    patch = panel_comment(
        d, "Twelve is arbitrary.", {"quote": "the ceiling doubles per approval"}
    )
    both = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # The passage really is inside the widget's shadow tree, so the reading under test is
    # the cross-tree one rather than an ordinary document comparison.
    assert page.evaluate(
        """() => {
             const root = document.getElementById('how-patch').shadowRoot;
             return Boolean(root) && [...(CSS.highlights.get('lf-mark') ?? [])]
               .some((r) => root.contains(r.startContainer));
           }"""
    ), "the fixture's passage is not marked inside a shadow tree"
    assert page.evaluate(LIST_ORDER) == [
        lede,
        patch,
        both,
    ], "the thread on the widget's words does not stand where the widget does"


def test_a_threads_passage_link_names_its_own_passage(browser, serve):
    """No heading stands over the list, so each card says where its own thread is: the
    words of the passage it is on, or the element it names, a heading included."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    merge = panel_comment(d, "On the merge rule.", {"section": "merge-both"})
    heading_thread = panel_comment(d, "On the heading.", {"section": "h-merge"})
    heading_quote_thread = panel_comment(
        d,
        "On the selected heading words.",
        {"section": "h-merge", "quote": "The merge rule"},
    )

    page = open_page(browser, url)
    resized(page, 1280, 800)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    quote = page.locator(f'.lf-thread[data-id="{merge}"] .lf-quote-label')
    expect(quote).to_contain_text("Two people editing one document")
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{merge}"]'))
    # Opening the card can restore the list's position after the click.
    scroll_settled(page, ".lf-threads")
    gutter = quote.evaluate(
        """label => { const quote = label.closest('.lf-quote');
          const box = quote.getBoundingClientRect();
          const line = parseFloat(getComputedStyle(quote).borderInlineStartWidth);
          return label.getBoundingClientRect().left - box.left - line; }"""
    )
    assert gutter >= 10, f"the quote rail leaves only {gutter}px before its text"
    for thread in (heading_thread, heading_quote_thread):
        expect(
            page.locator(f'.lf-thread[data-id="{thread}"] .lf-quote-label')
        ).to_contain_text("The merge rule")


def test_finding_narrows_the_list_and_says_how_much_of_it_is_left(browser, serve):
    """A search box is what every panel with a long list has, and the trap every one of
    them has too: the list goes quiet about the threads it is hiding. So the head says
    how much of the thread is in front of the user for as long as a narrowing
    stands, and a thread asked for by name — a mark on the page, a send that landed —
    lets the narrowing go rather than declining to appear.

    The narrowing reads the words, the part of the page, and nothing else: the count in
    the banner is the log's and does not move."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Review: six weeks reads long.", {"section": "lede"})
    cap = panel_comment(d, "Review: is forty megabytes enough?", {"section": "how-cap"})
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page = open_page(browser, url)
    # Slash belongs to the nearest search scope. Out on the prose it opens page search;
    # Escape returns to the prose, and `g T` is the route into the panel, where the same
    # press opens that list's own search instead. Read the two landings against each other.
    #
    # A plain paragraph rather than the body's own middle, which is a widget on this
    # page: `c` goes to the box belonging to whatever the user is standing in, so a
    # press made from the diff opens the composer on the diff and never reaches the panel
    # at all. Standing on prose is what "out on the prose" was always describing — and an
    # uncommented one, a click on a mark opening the thread it carries, which would be the
    # panel arriving ahead of the press that is meant to open it.
    page.locator("#how-store").click()
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_be_focused()

    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{cap}"]')).to_have_count(1)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 of 3 open threads")
    # The page's own count is the log's and says so throughout.
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 3")

    # The part of the page a thread is on is one of its words: a user looking for the
    # merge rule finds the thread in that section without its message saying so.
    page.get_by_role("searchbox", name="Find in threads").fill("merge rule")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{merge}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{lede}"]:not([hidden])')).to_have_count(0)

    # Enter accepts the filtered list's first result. From there, the same n/N grammar
    # as page search walks forward and backward through only the threads found.
    page.get_by_role("searchbox", name="Find in threads").fill("review")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    page.keyboard.press("Enter")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    search_line = shortcut_bar_text(page)
    assert re.search(r"n / N\s*search matches", search_line), search_line
    assert "show all" not in search_line
    # Search has one canonical walk in this scope; the page-level thread walk stands
    # down rather than leaving t/T as aliases for the same two movements.
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("n")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("Shift+n")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    # Leaving the panel leaves n/N's scope. Escape becomes the useful compact action
    # again because the narrowing still stands and can be cleared from the page.
    page.locator("#how-store").click()
    assert re.search(r"esc\s*show all", shortcut_bar_text(page))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)
    page.get_by_role("searchbox", name="Find in threads").fill("merge rule")

    # Asked for a thread the narrowing hides, the panel shows it rather than nothing:
    # the press came from the page, where no narrowing was ever visible.
    page.locator("#lede").click()
    expect(page.locator(f'.lf-thread[data-id="{lede}"]')).to_have_count(1)
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)

    # Escape leaves typing first, so the search remains useful for keyboard navigation.
    search = page.get_by_role("searchbox", name="Find in threads")
    search.click()
    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("back to list")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(search).to_have_value("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    page.keyboard.press("n")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(search).to_have_value("megabytes")
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()


def test_the_panel_can_show_only_what_is_waiting_on_the_user(browser, serve):
    """Which threads the user still owes an answer to is a question the log already
    answers: an agent comment asks by construction, and a reply may declare another
    ask. So the panel reads the log rather than keeping a record of what this user
    has read — nothing to go stale in a second tab, and nothing to remember across a
    reload.

    The count is the whole page's; the list is the ones it names."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    mine = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    theirs = panel_comment(d, "Is forty enough?", {"section": "how-cap"}, "agent")

    page = open_page(browser, url)
    # The key belongs to the panel, not to the page: a list the user is not looking at
    # is not a thing to narrow. Out on the prose the line never offers it and the press
    # does nothing — read against the same press landing a few lines below, which is what
    # makes the silence a rule rather than a page that happened not to react.
    #
    # A plain paragraph rather than the body's own middle, which is a widget here: `c`
    # below goes to the box belonging to whatever the user is standing in, and a press
    # made from the diff would open the composer on the diff rather than reach the panel
    # at all. Uncommented, too: a click on a mark opens the thread it carries.
    page.locator("#how-store").click()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("waiting on you")
    page.keyboard.press("w")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()

    # `g T` stands the user on the list, where the key is live and the line says so.
    # The control names it, off the row, so the two cannot come to spell it differently.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-needs")).to_have_text("You (1)")
    expect(page.locator(".lf-needs")).to_have_attribute("title", re.compile(r"\(w\)$"))
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("waiting on you")
    # `c` from that list enters the general box, and there `w` is a character like any other —
    # the typing scope claims what types one, so the row stands down and the line drops
    # it. Escape backs out onto the list and it is live again. Both directions, because
    # a key that were live in the box would type nothing and read as a dead keyboard.
    page.keyboard.press("c")
    expect(page.locator(".lf-general leaf-text")).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("waiting on you")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("waiting on you")
    page.keyboard.press("w")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{theirs}"]')).to_have_count(1)
    # Waiting-on-user is a filter, not a text search. It does not claim search-repeat
    # keys merely because the result list happens to be narrowed.
    page.keyboard.press("n")
    expect(page.locator(".lf-threads")).to_be_focused()
    # The card the narrowing hides keeps its node. A widget an agent sent in a reply is
    # instantiated once, in that card, and the banner's Asks count and the tray find it by
    # id in the document — hidden is the list's business, gone would be a claim about the
    # log (test_a_narrowing_hides_a_thread_without_taking_its_question_off_the_page).
    expect(
        page.locator(f'.lf-threads > .lf-thread[hidden][data-id="{mine}"]')
    ).to_have_count(1)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 2 open threads · On you"
    )
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")

    # Closing the owning surface retires both its narrowing frame and the g T frame below
    # it. The narrowing itself stays set for a later reopen, but Escape on the page must
    # neither advertise nor mutate a filter the user cannot see.
    page.get_by_role("button", name="Close threads", exact=True).click()
    panel_settled(page, False)
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("show all")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    page.keyboard.press("w")
    page.keyboard.press("w")

    # Answering the agent's comment takes it out of the user's list and hands the
    # next word to the agent.
    page.locator(f'.lf-thread[data-id="{theirs}"] .lf-thread-summary').click()
    reply = page.locator(f'.lf-thread[data-id="{theirs}"] leaf-text')
    reply.click()
    reply.type("Forty is plenty.")
    page.locator(f'.lf-thread[data-id="{theirs}"] .lf-thread-send').click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("You (0)")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(0)
    expect(page.locator(".lf-empty")).to_have_text("Nothing is waiting on you.")
    # The user was standing in the thread that just left. Focus lands on the list
    # rather than falling to body, where the next Space would scroll the page behind
    # the panel instead of the list in front of them.
    expect(page.locator(".lf-threads")).to_be_focused()

    # Escape unwinds the narrowing before it closes the panel, from wherever the user
    # is standing: a list that is not the whole thread is a layer they put on.
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("show all")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    expect(page.locator(f'.lf-thread[data-id="{mine}"]')).to_have_count(1)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-needs")).to_be_disabled()
    expect(page.locator(".lf-needs")).to_have_attribute(
        "title", "Nothing shown is waiting on you"
    )


def test_the_panel_composes_state_scope_subject_and_placement_facets(browser, serve):
    """Optional status, waiting, scope, subject and placement refinements compose.
    Counts describe named subsets, and pointer and keyboard toggles clear the same
    restrictions without restoring a status the user already cleared."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    pagewide = panel_comment(d, "A page-wide content note.")
    waiting = panel_comment(
        d, "Which local wording is right?", {"section": "lede"}, "agent"
    )
    design = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "about": "design",
            "text": "The shortcut control is crowded.",
            "anchor": {"section": "lf-shortcut-bar"},
        },
    )["id"]
    gone = panel_comment(d, "The removed section still matters.", {"section": "gone"})
    resolved = panel_comment(d, "This local note is done.", {"section": "how-cap"})
    events_model.append_event(
        d, {"kind": "resolve", "author": "user", "parent": resolved}
    )

    # One open thread awaits neither party after a complete agent answer.
    settled_turn = panel_comment(d, "A complete answer is available.")
    thread_model.cmd_reply(
        d, settled_turn, "Done; nothing more is needed.", None, for_event=settled_turn
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    visible = page.locator(".lf-threads > .lf-thread:not([hidden])")

    def pick(kind, value):
        return page.locator(f'[data-filter-kind="{kind}"][data-filter-value="{value}"]')

    waiting_group = page.get_by_role("group", name="Waiting on", exact=True)
    waiting_group.evaluate("node => window.__waitingGroup = node")
    for label in ("Status", "Waiting on", "Location", "Subject"):
        expect(page.get_by_role("group", name=label, exact=True)).to_be_visible()
    expect(visible).to_have_count(5)
    expect(pick("status", "open")).to_have_text("Open (5)")
    expect(pick("status", "resolved")).to_have_text("Resolved (1)")
    expect(pick("waiting", "user")).to_have_text("You (1)")
    expect(pick("waiting", "agent")).to_have_text("Agent (3)")
    expect(pick("scope", "page")).to_have_text("Page (2)")
    expect(pick("scope", "local")).to_have_text("Anchored (3)")
    expect(pick("subject", "content")).to_have_text("Content (4)")
    expect(pick("subject", "design")).to_have_text("Design (1)")

    # Status predicts its transition: Resolved clears Waiting on, so its count is
    # still one while the current user-only selection has no resolved result.
    pick("waiting", "user").click()
    expect(visible).to_have_count(1)
    expect(pick("status", "resolved")).to_have_text("Resolved (1)")
    pick("status", "open").click()
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    pick("status", "resolved").click()
    expect(waiting_group).to_be_hidden()
    expect(visible).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{resolved}"]')).to_be_visible()
    pick("status", "resolved").click()
    expect(visible).to_have_count(6)
    expect(waiting_group).to_be_visible()
    expect(pick("status", "resolved")).to_have_attribute("aria-pressed", "false")
    pick("status", "open").click()
    expect(waiting_group).to_be_visible()
    assert waiting_group.evaluate("node => node === window.__waitingGroup"), (
        "changing status replaced the retained Waiting on group"
    )
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "agent")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(5)

    # No selected status means both open and resolved threads. The same active
    # box clears with either a pointer click or Space, without an All control.
    expect(page.get_by_role("button", name=re.compile(r"^All(?: \(|$)"))).to_have_count(
        0
    )
    pick("status", "open").click()
    expect(visible).to_have_count(6)
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("6 threads")
    pick("waiting", "user").focus()
    page.keyboard.press("Space")
    expect(visible).to_have_count(1)
    page.keyboard.press("Space")
    expect(visible).to_have_count(6)
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    # The shortcut follows the same toggle as Space, including leaving status
    # unrestricted rather than silently restoring Open when it clears waiting.
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(visible).to_have_count(1)
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("w")
    expect(visible).to_have_count(6)
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "false")
    pick("status", "open").click()
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    expect(visible).to_have_count(3)
    pick("scope", "local").click()
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    pick("scope", "page").click()
    expect(visible).to_have_count(2)
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "user")).to_be_disabled()
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(2)
    pick("scope", "page").click()
    expect(visible).to_have_count(5)

    pick("waiting", "agent").click()
    pick("scope", "local").click()
    expect(visible).to_have_count(2)
    expect(page.locator(f'.lf-thread[data-id="{pagewide}"]')).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{waiting}"]')).to_be_hidden()
    pick("subject", "content").click()
    expect(visible).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{gone}"]')).to_be_visible()
    expect(page.locator(f'.lf-thread[data-id="{design}"]')).to_be_hidden()
    pick("gone", "gone").click()
    expect(visible).to_have_count(1)
    expect(pick("gone", "gone")).to_have_text("No longer here (1)")
    page.locator(".lf-thread-filter-toggle").click()
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 5 open threads · On agent · Anchored · Content · No longer here"
    )
    page.get_by_role("button", name="Reset thread filters").click()
    expect(visible).to_have_count(5)
    expect(page.locator(".lf-thread-filter-toggle")).to_be_focused()
    page.keyboard.press("Space")

    # A search may empty the selected choice. It stays enabled so the user can
    # clear it, even though only clearing the search can recover matching results.
    pick("scope", "local").click()
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("no thread contains these words")
    expect(visible).to_have_count(0)
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_be_enabled()
    pick("scope", "local").click()
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "false")
    expect(pick("status", "open")).to_be_enabled()
    expect(page.locator(".lf-empty")).to_have_text(
        "No open threads match “no thread contains these words”."
    )
    search.fill("")
    expect(visible).to_have_count(5)
    pick("scope", "local").click()
    expect(visible).to_have_count(3)

    # The shortcut toggles only Waiting on and retains Location across both presses.
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    page.keyboard.press("w")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "false")
    expect(pick("waiting", "agent")).to_have_attribute("aria-pressed", "false")
    expect(visible).to_have_count(3)
    pick("status", "resolved").click()
    page.locator(".lf-threads").focus()
    page.keyboard.press("w")
    expect(pick("status", "open")).to_have_attribute("aria-pressed", "true")
    expect(pick("waiting", "user")).to_have_attribute("aria-pressed", "true")
    expect(pick("scope", "local")).to_have_attribute("aria-pressed", "true")
    expect(visible).to_have_count(1)
    page.keyboard.press("Escape")
    expect(visible).to_have_count(5)
    resized(page, 320, 720)
    rail_size = page.locator(".lf-thread-filters").evaluate(
        "el => ({client: el.clientWidth, scroll: el.scrollWidth})"
    )
    assert rail_size["scroll"] == rail_size["client"], rail_size


def test_an_agent_reply_says_when_the_user_owes_an_answer(browser, serve):
    """An open thread and a request to its user are different facts. A complete
    answer stays available for follow-up without entering the waiting list; a reply
    carrying an explicit prose ask enters it until the user answers. A widget ask
    needs no duplicate flag: its own standing projection enters and leaves the list."""
    url = serve(PANEL_PAGE)
    answered = panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    asked = panel_comment(serve.page_dir, "What remains?", {"section": "how-store"})
    thread_model.cmd_reply(
        serve.page_dir,
        answered,
        "Forty is what the slowest supported device can hold.",
        None,
        for_event=answered,
    )
    thread_model.cmd_reply(
        serve.page_dir,
        asked,
        "One choice remains. Which store should own the result?",
        None,
        for_event=asked,
        awaits=True,
    )
    page = open_page(
        browser,
        url,
        init_script="""(() => {
          const counts = window.__replyListeners = {drafts: 0};
          const add = Document.prototype.addEventListener;
          Document.prototype.addEventListener = function(type, ...args) {
            if (this === document && type === "lf-drafts") counts.drafts += 1;
            return add.call(this, type, ...args);
          };
          const define = customElements.define.bind(customElements);
          customElements.define = (name, ctor, options) => {
            if (name === "lf-options") {
              const connected = ctor.prototype.connectedCallback;
              ctor.prototype.connectedCallback = function() {
                if (this.id === "backend") {
                  const message = this.closest(".lf-msg");
                  window.__backendContext ??= {
                    message: Boolean(message),
                    thread: this.closest(".lf-thread")?.dataset.id ?? null,
                    saidAt: message?.querySelector("time")?.dateTime ?? null,
                  };
                }
                return connected?.call(this);
              };
            }
            return define(name, ctor, options);
          };
        })()""",
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-needs")).to_have_text("You (1)")
    expect(page.locator(".lf-thread")).to_have_count(2)
    expect(
        page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-status')
    ).to_have_text("On you to answer")
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"] .lf-thread-status')
    ).to_have_count(0)

    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{asked}"]')).to_have_count(1)
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"]:not([hidden])')
    ).to_have_count(0)

    listeners = page.evaluate("() => ({...window.__replyListeners})")
    find = page.get_by_role("searchbox", name="Find in threads")
    for key in ("r", "e", "Backspace", "Backspace"):
        find.press(key)
    assert page.evaluate("() => ({...window.__replyListeners})") == listeners, (
        "reconciling a hidden thread registered another reply-box listener"
    )
    expect(find).to_have_value("")

    # The completed thread is absent under the narrowing. A later structured ask must
    # still be projected before the filter decides whether to admit that thread, or the
    # question can never render itself into the list that would discover it.
    widget_reply = thread_model.cmd_reply(
        serve.page_dir,
        answered,
        "Choose the backend here.",
        '<lf-ask id="backend-decision"><h3>Which backend?</h3>'
        '<lf-options id="backend" choose>'
        '<lf-option id="backend-sqlite"><strong>SQLite</strong></lf-option>'
        '<lf-option id="backend-postgres"><strong>Postgres</strong></lf-option>'
        "</lf-options></lf-ask>",
        for_event=None,
    )
    told(page)
    expect(page.locator(".lf-needs")).to_have_text("You (2)")
    expect(page.locator(f'.lf-thread[data-id="{answered}"]')).to_have_count(1)
    assert page.evaluate("() => window.__backendContext") == {
        "message": True,
        "thread": answered,
        "saidAt": widget_reply["ts"],
    }

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{answered}"]'))
    page.locator("#backend-sqlite").click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("You (1)")
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"]:not([hidden])')
    ).to_have_count(0)

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{asked}"]'))
    reply = page.locator(f'.lf-thread[data-id="{asked}"] leaf-text')
    write(reply, "SQLite should own it.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-send').click()
    holding(page, held, 1, "the answer to the prose Ask")
    expect(
        page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-status')
    ).to_have_text("Sending")
    expect(page.locator('[data-filter-value="user"]')).to_have_text("You (0)")
    expect(page.locator('[data-filter-value="user"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".lf-thread:not([hidden])")).to_have_count(0)
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("You (0)")
    expect(page.locator(".lf-thread:not([hidden])")).to_have_count(0)


def test_a_host_failure_receipt_does_not_read_as_an_answer(browser, serve):
    """A reply saying no answer is coming is marked as one, in both faces of the head.

    Nothing else in the message says it: a host receipt is a reply event, written
    under the thread's own agent name, in the same bubble as a real answer, and its
    prose is the only other difference. So a user skimming a thread reads an
    apology from the agent rather than a notice that their message went nowhere, and
    the page's own record of the failure — `failure` — went unread. The mark belongs
    in the head because that is the part of a message a user takes on trust.
    """
    url = serve(THREAD_DIFF_PAGE)
    answered, unanswered = (
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "cd-q"},
            },
        )
        for text in ("Widen the north bracket?", "And the south pair?")
    )
    answer = thread_model.cmd_reply(
        serve.page_dir,
        answered["id"],
        "Widened it to forty.",
        None,
        for_event=answered["id"],
    )
    receipt = thread_model.cmd_reply(
        serve.page_dir,
        unanswered["id"],
        "The agent's turn ended without an answer to this message. "
        "Send it again to retry.",
        None,
        for_event=unanswered["id"],
        failure="turn_failed",
    )

    page = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-page-thread-msg[data-event="{receipt["id"]}"]')
    expect(inline.locator(".lf-msg-failure")).to_have_text("Not answered")
    assert inline.get_attribute("data-failure") == "turn_failed"
    # The real answer above it wears nothing, so the mark is a difference the user
    # can see rather than a decoration every agent message carries.
    real = page.locator(f'#cd-q .lf-page-thread-msg[data-event="{answer["id"]}"]')
    expect(real.locator(".lf-msg-failure")).to_have_count(0)

    # The server settled its turn, and the thread's `attention` still reads
    # `needs_user` for recovery: the margin and panel name the action owed.
    margin = page.locator('[data-lf-margin-for="cd-q"] > .lf-margin-marker')
    expect(margin).to_have_attribute("data-lf-turn", "user")
    expect(margin.locator(".lf-margin-entry-context")).to_have_text("On you to resend")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(f'.lf-msg[data-mid="{receipt["id"]}"]')
    expect(panel.locator(".lf-msg-failure")).to_have_text("Not answered")
    status = page.locator(f'.lf-thread[data-id="{unanswered["id"]}"] .lf-thread-status')
    expect(status).to_have_text("On you to resend")
    assert status.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the summary clips its failure status"
    )

    # The thread's recovery `attention` is the user filter's authority, though no
    # question or Ask is left open on it. A held resend hands the thread to
    # Sending immediately; refusal restores the same recovery and draft.
    page.locator(".lf-thread-filter-toggle").click()
    recovery = page.locator('[data-filter-value="user"]')
    expect(recovery).to_be_enabled()
    recovery.click()
    expect(page.locator(f'.lf-thread[data-id="{unanswered["id"]}"]')).to_be_visible()
    page.locator('[data-filter-value="open"]').click()
    card = page.locator(f'.lf-thread[data-id="{unanswered["id"]}"]')
    card.locator(":scope > .lf-thread-summary").click()
    draft = card.locator("leaf-text")
    write(draft, "Try the south pair again.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        card.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the recovery resend")
    expect(status).to_have_text("Sending")
    expect(recovery).to_have_text("You (0)")
    expect(recovery).to_have_attribute("aria-pressed", "true")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    expect(status).to_have_text("On you to resend")
    expect(recovery).to_have_text("You (1)")
    expect(recovery).to_be_enabled()
    expect(draft).to_have_js_property("value", "Try the south pair again.")
    page.unroute("**/api/event")

    # The failed answer remains distinct from the muted clock without a chip face.
    head = page.evaluate(
        """(id) => {
          const head = document.querySelector(`.lf-msg[data-mid="${id}"] .lf-msg-head`);
          const failure = getComputedStyle(head.querySelector(".lf-msg-failure"));
          return {
            failure: failure.color,
            border: failure.borderTopWidth,
            weight: failure.fontWeight,
            clock: getComputedStyle(head.querySelector("time")).color,
          };
        }""",
        receipt["id"],
    )
    assert head["failure"] != head["clock"]
    assert head["border"] == "0px" and int(head["weight"]) >= 600


def test_a_thread_the_agent_closed_names_who_closed_it(browser, serve):
    """Either side can close a thread and the user watches only one of them happen.
    Their own press folds the thread under their hand and leaves the outcome on the
    control they pressed, so its Resolved state needs to say nothing more. An
    agent's resolve arrives on a poll with no gesture behind it, and that thread says
    who closed it — in the row the control stood in, at the end it stood at."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]

    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Indexer", "parent": c1},
    )
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    expect(page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolved-by')).to_have_text(
        "✓ Resolved by Indexer"
    )

    page.locator('[data-filter-value="open"]').click()
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c2}"]'))
    page.locator(f'.lf-thread[data-id="{c2}"] .lf-resolve').click()
    round_trip(page)
    page.locator('[data-filter-value="resolved"]').click()
    # The settled card is what says the fold is over, so the line's absence is read
    # from a thread that has arrived rather than one still on its way.
    expect(page.locator(f'.lf-thread[data-id="{c2}"]:not([hidden])')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c2}"] .lf-resolved-by')).to_have_count(0)


def test_a_resolved_thread_can_be_reopened(browser, serve):
    """Reopening is a logged transition: the thread returns to the open list with
    its reply and resolve controls, and the state facet returns to Open."""
    page = open_page(browser, serve(LONG_PAGE, comments=18))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comment = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{comment}"]'))
    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)
    # The round trip starts the fold; the retained resolved card finishes it.
    expect(page.locator(f'.lf-thread[data-id="{comment}"][hidden]')).to_have_count(1)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    with sending(page, "the reopen"):
        focus_panel_thread(page.locator(f'.lf-thread[data-id="{comment}"]'))
        page.locator(f'.lf-thread[data-id="{comment}"] .lf-reopen').click()

    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{comment}"]')
    expect(reopened).to_be_in_viewport()
    expect(reopened.locator("leaf-text")).to_be_focused()
    expect(reopened.locator("leaf-text")).to_have_count(1)
    expect(reopened.locator(".lf-resolve")).to_have_count(1)
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 18")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"


@pytest.mark.parametrize("kind", ["unresolve", "resolve", "reply"])
@pytest.mark.parametrize("destination", ["stay", "page", "other-thread", "other-focus"])
def test_a_thread_completion_keeps_the_users_later_destination(
    browser, serve, kind, destination
):
    """A held thread operation may land only while its original intent still stands."""
    held = []

    def hold_operation(route):
        if route.request.post_data_json["kind"] == "read":
            route.continue_()
        else:
            held.append(route)

    page = open_page(
        primed(browser, lambda page: page.route("**/api/event", hold_operation)),
        serve(FEATURE_GALLERY),
    )
    resized(page, 390, 700)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = {
        event["anchor"]["section"]: event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and "token" not in event and event.get("anchor")
    }
    root = roots["bg-resolved-text" if kind == "unresolve" else "bg-thread-text"]
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    if kind == "unresolve":
        page.locator(".lf-thread-filter-toggle").click()
        page.locator('[data-filter-value="resolved"]').click()
    focus_panel_thread(thread)
    if kind == "reply":
        write(thread.locator("leaf-text"), "A reply whose delivery is held.")

    thread.get_by_role(
        "button",
        name={
            "unresolve": "Reopen",
            "resolve": "Resolve thread",
            "reply": "Send",
        }[kind],
        exact=True,
    ).click()
    holding(page, held, 1, "the thread operation")

    later = page.locator(f'.lf-thread[data-id="{roots["bg-crowded"]}"] leaf-text')
    changes = page.locator("#bg-history summary")
    if kind == "unresolve" and destination in {"other-thread", "other-focus"}:
        # Reopen has already selected Open while its delivery is held.
        expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
            "aria-pressed", "true"
        )
        expect(
            page.locator(f'.lf-thread[data-id="{roots["bg-crowded"]}"]')
        ).to_be_visible()
    if destination in {"other-thread", "other-focus"}:
        focus_panel_thread(page.locator(f'.lf-thread[data-id="{roots["bg-crowded"]}"]'))
    if destination == "page":
        page.get_by_role("button", name="Close threads", exact=True).click()
        changes.click()
    elif destination == "other-thread":
        later.click()
        write(later, "The user is working here now.")
    elif destination == "other-focus":
        # Accessibility and app focus travel need not emit a pointer or key gesture.
        later.focus()

    delivered = held.pop(0)
    attempt = delivered.request.post_data_json["attempt"]
    delivered.continue_()
    page.unroute("**/api/event")
    round_trip(page)
    told(page)
    rendered(page)
    assert (
        next(
            event
            for event in events_model.read_events(serve.page_dir)
            if event.get("attempt") == attempt
        )["kind"]
        == kind
    )
    if destination == "page":
        assert not page.get_by_role("dialog").is_visible()
        expect(changes).to_be_focused()
        expect(page.locator("#bg-history details")).to_have_attribute("open", "")
    elif destination in {"other-thread", "other-focus"}:
        expect(later).to_be_focused()
        expect(later).to_have_js_property(
            "value",
            "The user is working here now." if destination == "other-thread" else "",
        )
    elif kind in {"reply", "unresolve"}:
        expect(thread.locator("leaf-text")).to_be_focused()
    else:
        expect(
            page.locator(
                ".lf-threads > .lf-thread:not([hidden]) > .lf-thread-summary:focus"
            )
        ).to_have_count(1)


def test_a_late_reply_reopens_its_resolved_thread(browser, serve):
    """New spoken content returns to Open Threads, including after a reload."""
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    expect(thread).to_be_hidden()
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": root["id"],
            "responds": root["id"],
            "text": "This arrived after resolution.",
        },
    )
    told(page)
    expect(thread).to_be_visible()
    thread.locator(".lf-thread-summary").press("Enter")
    expect(thread.locator(".lf-msg.agent")).to_be_visible()
    expect(thread.get_by_role("button", name="Reopen", exact=True)).to_have_count(0)
    page.reload()
    told(page)
    expect(thread).to_be_visible()
    expect(thread).to_have_attribute("data-resolved", "false")


def test_a_resolved_thread_gives_its_room_back_as_motion(browser, serve):
    """Resolving a thread empties its place in the list over a fifth of a second,
    not in the frame of the press.

    The node used to go the moment the log settled it: the ✓ Resolve the user had
    just pressed took itself off the page, and every thread under it arrived
    somewhere else with no path between the two — the same pair of failures the
    suggestion's decided slot was already fixed for, in the panel this time. So the
    thread stays where it stood, states on the pressed control what was done to it,
    and folds; the retained Resolved state gets it when the fold is over.

    What the log says is true from that first frame regardless — Threads counts down
    and Resolved counts up while the pixels catch up — and a thread on its way out is
    out of the t/T walk from the same frame rather than remaining a destination that is
    about to disappear.

    Held at its first frame rather than sampled mid-flight, the way the suggestion's
    own fold is read: mid-flight is a race with the clock that passes on a fast
    machine whatever the code does, where the held frame is the fold's opening state
    for as long as the assertions need it."""
    page = open_page(browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-thread-summary').click()
    first = page.locator(f'.lf-thread[data-id="{c1}"]').bounding_box()
    stood = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    # The room the first thread holds, the gap under it included, which is what its
    # neighbour rises by once the fold has given it back.
    room = stood["y"] - first["y"]
    action_edge = page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().right"
    )

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    outcome = page.locator(f'[data-id="{c1}"] .lf-resolve')
    expect(outcome).to_have_attribute("aria-label", "Resolved")
    expect(outcome.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(page.locator(f'[data-id="{c1}"] .lf-thread-send')).to_be_hidden()
    resolved_edge = page.locator(f'[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().right"
    )
    assert resolved_edge == pytest.approx(action_edge, abs=1), (
        "the held outcome left Resolve's thread-header edge"
    )
    held = page.evaluate(LIST_STATE)
    assert held["standing"] == [c1, c2, c3], (
        "the resolved thread gave up its place in the frame it was resolved in, so "
        f"the list stood as {held['standing']} with the fold still to play"
    )
    assert held["walkable"] == [c2, c3], (
        "a thread on its way out is still walkable by t/T, so a "
        f"key can land on room that is about to go: the list offered {held['walkable']}"
    )
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "the room went back without motion carrying it"
    )
    now = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert now["y"] == stood["y"], (
        f"the thread below stood at {stood} and reads {now} in the frame the outcome "
        "was stated, so the fold started from somewhere other than the box the user "
        "was looking at"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Open threads: 2")
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(page.locator(f'[data-id="{c1}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply c"
    )

    # Half way down, the metadata-row outcome is still on screen rather than having
    # moved with the folding geometry.
    page.evaluate("() => window.__lfHeld.forEach((m) => (m.currentTime = 110))")
    clip, says = page.evaluate(
        """(id) => {
          const going = document.querySelector(`[data-id="${id}"]`);
          const outcome = going.querySelector(".lf-resolve");
          return [going.getBoundingClientRect(), outcome.getBoundingClientRect()];
        }""",
        c1,
    )
    assert says["top"] < clip["bottom"] and clip["top"] < says["bottom"], (
        f"the outcome sat at {says['top']:.0f}–{says['bottom']:.0f} with the fold "
        f"clipped to {clip['top']:.0f}–{clip['bottom']:.0f}, so the word the press "
        "left was already under the clip half way through"
    )

    # And the far end: the thread becomes a retained hidden result, once, and the room it held
    # has gone back to the threads under it.
    page.evaluate("() => window.__lfHeld.forEach((m) => m.finish())")
    expect(page.locator(f'.lf-thread[data-id="{c1}"][hidden]')).to_have_count(1)
    expect(page.locator(f'[data-id="{c1}"]')).to_have_count(1)
    risen = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert stood["y"] - risen["y"] == pytest.approx(room, abs=1), (
        f"the thread below rose {stood['y'] - risen['y']:.1f}px where the resolved "
        f"thread held {room:.1f}px"
    )


def test_a_folding_thread_keeps_the_card_under_the_pointer_put(browser, serve):
    """A remote resolution may fold above a card while the user aims inside it.

    Hold the fold so its midpoint and completion are stable states the test can inspect.
    The target card must keep the same viewport position through both; otherwise the
    animation carries new controls under a stationary pointer for its whole duration."""
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[15:17]
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    setup = page.evaluate(
        "([source, target]) => {"
        " const list = document.querySelector('.lf-threads');"
        ' const a = document.querySelector(`.lf-thread[data-id="${source}"]`)'
        "   .getBoundingClientRect();"
        ' const b = document.querySelector(`.lf-thread[data-id="${target}"]`)'
        "   .getBoundingClientRect();"
        " const view = list.getBoundingClientRect();"
        " return {scrollTop: list.scrollTop, source: a.toJSON(), target: b.toJSON(),"
        "   sourceVisible: a.bottom > view.top && a.top < view.bottom};"
        "}",
        [source, target],
    )
    assert setup["sourceVisible"], "the folding card is outside the visible reflow"
    assert setup["scrollTop"] > setup["source"]["height"], (
        "the list cannot compensate for the fold before reaching its top edge"
    )
    point = [
        setup["target"]["x"] + setup["target"]["width"] / 2,
        setup["target"]["y"] + setup["target"]["height"] / 2,
    ]
    page.mouse.move(*point)
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, target],
    ), "the pointer did not begin over the target card"

    before = page.evaluate("() => window.__lfHeld.length")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": source},
    )
    told(page)
    expect(page.locator(f'.lf-going[data-id="{source}"]')).to_have_count(1)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1, (
        "the remote resolution did not start a fold"
    )
    assert (
        page.locator(".lf-threads").evaluate(
            "el => getComputedStyle(el).overflowAnchor"
        )
        == "none"
    ), "native anchoring still has a second claim on the held fold"
    started = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert started == pytest.approx(setup["target"]["top"], abs=1)

    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)
    halfway = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert halfway == pytest.approx(setup["target"]["top"], abs=1), (
        f"the fold carried the target card from {setup['target']['top']:.1f}px "
        f"to {halfway:.1f}px under a stationary pointer"
    )

    # The hold owns reflow, not scrolling. A wheel gesture during the held animation
    # must move the user by the distance the browser accepts and stay there on the
    # next animation frame instead of being mistaken for another fold delta.
    threads = page.locator(".lf-threads")
    scroll_before = threads.evaluate("el => el.scrollTop")
    page.mouse.wheel(0, 40)
    one_frame(page)
    scroll_after = threads.evaluate("el => el.scrollTop")
    assert scroll_after > scroll_before, "the fold undid the user's wheel scroll"
    scrolled_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert scrolled_top == pytest.approx(
        halfway - (scroll_after - scroll_before), abs=1
    ), "the scroll hold changed the distance the user deliberately travelled"
    threads.evaluate("(el, top) => { el.scrollTop = top; }", scroll_before)
    one_frame(page)
    restored = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert restored == pytest.approx(setup["target"]["top"], abs=1)

    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(setup["target"]["top"], abs=1), (
        f"removing the folded card moved the target from "
        f"{setup['target']['top']:.1f}px to {finished:.1f}px"
    )
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, target],
    ), "the fold left another card under the stationary pointer"
    assert (
        page.locator(".lf-threads").evaluate(
            "el => getComputedStyle(el).overflowAnchor"
        )
        == "auto"
    ), "the manual hold disabled native anchoring after its mutation ended"


def test_a_folding_reference_hands_its_hold_to_the_next_card(browser, serve):
    """When the aimed-at card is itself leaving, its successor inherits the hold.

    A folding node remains connected until the end of its animation, so connectedness
    alone cannot identify a usable reference. The next live card must stay put from the
    first shrinking frame through the final reconciliation."""
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[15:17]
    source_card = page.locator(f'.lf-thread[data-id="{source}"]')
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    source_box = source_card.bounding_box()
    target_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    scroll_top = page.locator(".lf-threads").evaluate("el => el.scrollTop")
    assert scroll_top > source_box["height"], (
        "the list cannot compensate for the fold before reaching its top edge"
    )
    point = [
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    ]
    page.mouse.move(*point)
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, source],
    ), "the pointer did not begin over the card that will fold"

    before = page.evaluate("() => window.__lfHeld.length")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": source},
    )
    told(page)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1
    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)
    halfway = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert halfway == pytest.approx(target_top, abs=1), (
        f"the disappearing reference moved its successor from {target_top:.1f}px "
        f"to {halfway:.1f}px"
    )

    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(target_top, abs=1)


def test_a_render_arriving_mid_fold_keeps_the_place_the_fold_is_holding(browser, serve):
    """A fold owns the list's place until it ends; a render landing inside it joins.

    The list slides both ways around a folding card: the room closes under the cards
    below it, and the cards above come down into it as the hold gives back the scroll.
    So what is under the pointer stops naming where the user is standing the moment
    the motion starts, and a hold that reads it again mid-fold pins a card above the
    fold while everything past it — the successor the user was aiming at among it —
    goes on moving. The arrival here is another thread's reply, which is one of several:
    the two-second heartbeat repaints the receipts under the same hold, and so does a
    narrowing.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[15:17]
    source_card = page.locator(f'.lf-thread[data-id="{source}"]')
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    source_box = source_card.bounding_box()
    target_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    point = [
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    ]
    page.mouse.move(*point)

    before = page.evaluate("() => window.__lfHeld.length")
    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": source},
    )
    told(page)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1
    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)

    # Far enough down the list that its own card cannot move the target, so what the
    # arrival costs is the hold and nothing else.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": roots[5],
            "text": "Noted, and still looking.",
        },
    )
    told(page)
    one_frame(page)
    joined = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert joined == pytest.approx(target_top, abs=1), (
        f"the arriving render moved the held card from {target_top:.1f}px "
        f"to {joined:.1f}px"
    )
    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(target_top, abs=1), (
        f"the fold's last frame moved the held card from {target_top:.1f}px "
        f"to {finished:.1f}px"
    )


def test_an_external_resolution_leaves_the_user_on_the_thread_list(browser, serve):
    """A reply box becomes inert before its externally resolved card folds away. The
    list takes focus in that first frame instead of letting the deferred blur reach body."""
    page = open_page(browser, serve(LONG_PAGE, comments=1), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{root["id"]}"]'))
    reply = page.locator(f'.lf-thread[data-id="{root["id"]}"] leaf-text')
    write(reply, "This draft survives the other actor settling its thread.")
    reply.evaluate("ta => ta.setSelectionRange(8, 8)")
    expect(reply).to_be_focused()

    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "parent": root["id"]},
    )
    told(page)
    going = page.locator(f'.lf-going[data-id="{root["id"]}"]')
    expect(going).to_have_attribute("inert", "")
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "the thread left without exercising the animated inert path"
    )
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(going.locator("leaf-text")).to_have_js_property(
        "value", "This draft survives the other actor settling its thread."
    )

    page.evaluate("() => window.__lfHeld.forEach((motion) => motion.finish())")
    expect(going).to_have_count(0)


def test_an_inline_reply_link_finishes_a_resolution_fold(browser, serve):
    """A direct jump uses the resolved card, even before its outgoing fold ends."""
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(serve.page_dir, "Which job first?", {"section": "jobs"})
    reply = thread_model.cmd_reply(
        serve.page_dir,
        root,
        "Pick the first job.",
        '<lf-ask id="first-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="first-job" choose>'
        '<lf-option id="mounts">Mounts</lf-option>'
        '<lf-option id="camera">Camera</lf-option>'
        "</lf-options></lf-ask>",
        for_event=root,
    )
    page = open_page(browser, url, init_script=HOLD_MOTION)
    resized(page, 1920, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    inline.get_by_role("button", name="Resolve thread", exact=True).click()
    round_trip(page)
    expect(page.locator(f'.lf-going[data-id="{root}"]')).to_have_count(1)

    inline.get_by_role("button", name="Open interactive reply in Threads").click()
    expect(page.locator(f'.lf-going[data-id="{root}"]')).to_have_count(0)
    message = page.locator(
        f'.lf-thread:not([hidden]) .lf-msg[data-mid="{reply["id"]}"]'
    )
    expect(message).to_be_focused()
    expect(message.locator("#first-job")).to_be_in_viewport()
    # Its old animation completion must leave the canonical revealed card standing.
    page.evaluate("window.__lfHeld.forEach(animation => animation.finish())")
    expect(message).to_be_visible()
    expect(page.locator(f'.lf-thread[data-id="{root}"]')).to_have_count(1)


def test_the_fold_never_paints_a_frame_that_undoes_the_last(browser, serve):
    """A fold is a sequence, and every other check here reads a state.

    The gap that leaves is a frame that puts back what the frames before it took:
    a Web Animations effect stops applying at the end of its own interval, so
    anything holding the collapsed box open — a removal that slips a frame past
    the finish, a fill the helper stopped stating — paints the whole thread back
    at full height and full opacity for a frame before it goes. Held frames can't
    see it; each one is correct on its own. This watches the real fold at real
    speed and asks the only question a sequence can be wrong about, which is
    whether any frame is taller than the one before it.

    It is also what the first recording of this fold got wrong, in the other
    direction: sampled at exactly the duration, an animation is already past its
    own interval and reads as the element it never was."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    # Open disclosure before recording, then watch from before Resolve so the
    # frames it holds still are in the record alongside the ones that move.
    page.evaluate(FRAME_BY_FRAME, f'.lf-threads > [data-id="{c1}"]')
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    # The outgoing node becoming a retained hidden card is the fold's end and the
    # browser's own statement, so the wait is that rather than the sampler's flag.
    page.wait_for_selector(f'.lf-threads > [data-id="{c1}"]', state="hidden")
    seen = page.evaluate("() => window.__seen")

    grew = [
        (i, seen[i - 1], seen[i]) for i in range(1, len(seen)) if seen[i] > seen[i - 1]
    ]
    assert not grew, (
        "the fold painted a frame taller than the one before it: "
        + ", ".join(f"frame {i} went {was:.0f}px → {now:.0f}px" for i, was, now in grew)
    )
    # And it folded rather than vanishing between two samples, which would pass the
    # line above by having nothing to compare.
    assert any(0 < h < seen[0] for h in seen), (
        f"no frame caught the fold part way down (heights: {seen}), so a thread that "
        "went in one frame would read the same as one that folded"
    )


def test_a_user_who_asked_for_less_motion_gets_the_resolved_thread_at_once(
    browser, serve
):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the bargain the suggestion's own fold already makes, asked
    again here because the thread's is the path with somewhere to be left stranded:
    the node stays in the list until its fold ends, so a fold that never starts is a
    node that has to reach its retained resolved state by the same render that declined to play
    one."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(
        browser,
        serve(LONG_PAGE, comments=2),
        context=context,
        init_script=HOLD_MOTION,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    expect(page.locator(f'.lf-thread[data-id="{c1}"][hidden]')).to_have_count(1)
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a user who asked for less motion was given a fold to sit through"
    )
    assert page.evaluate(LIST_STATE) == {
        "standing": [c2],
        "walkable": [c2],
    }, "the thread that declined its fold was left standing in the list"


def test_a_thread_reopened_mid_fold_folds_again_when_it_settles(browser, serve):
    """A fold is a claim about a node standing in the list, and the user can take
    that node out from under it: `z` reopens the thread the fold is carrying away, and
    the render that puts the thread back drops the folding node. Held past that, the
    record would hand the spent node back the next time the thread settled — the fold
    would be over before it started, and what stood in the list for its duration would
    be the thread as it read before it reopened, one message short.

    Reachable in the product, not only here: resolve, `z` and resolve are three round
    trips through the real server in 78ms measured, against a fold of 220ms, so the
    window is the user's typing speed and nothing else. Holding the motion is what
    makes it a state instead of a race — a paused animation never settles `finished`,
    so the record stays exactly as long as the assertions need it."""
    page = open_page(browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    going = page.locator(f'.lf-threads > .lf-going[data-id="{c1}"]')

    before = page.evaluate("window.__lfHeld.length")
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going).to_have_count(1)
    folds = page.evaluate("window.__lfHeld.length")
    assert folds == before + 1, "the press drew something other than its one fold"

    undo(page)
    expect(thread).to_have_count(1)
    expect(going).to_have_count(0)
    # News the thread takes while it is open again, which the node the first fold was
    # carrying away has never held — so what folds the second time says which node it is.
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": c1,
            "text": "Reopened, and answered.",
        },
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(2)

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("window.__lfHeld.length") > folds, (
        "the second settlement drew no fold of its own"
    )

    # And the first fold runs out, which is the other half of two folds standing at
    # once: its node left the list when the thread reopened, and the record it must
    # not clear on its way is the live fold's. Cleared, the thread is pulled out of
    # the list in the middle of the motion carrying it away.
    # The await states its own end. `page.evaluate` takes no timeout in any binding, so
    # an animation that never settles `finished` is a wait nothing bounds: this one
    # didn't, and what should have been this test failing under its own name was the
    # job's whole 45-minute step, spent here, with the share of the suite already handed
    # to this worker never run. `SERVED_TIMEOUT_MS` is the patience the payload's own
    # probes give a promise they await inside `evaluate`, and the rejection comes back
    # through `evaluate` naming the motion that stopped and the bound it passed.
    page.evaluate(
        "async ([i, ranOutMs]) => { const m = window.__lfHeld[i];"
        " m.play(); m.currentTime = m.effect.getComputedTiming().duration;"
        " let timer;"
        " try {"
        "   await Promise.race([m.finished, new Promise((_, ranOut) => {"
        "     timer = setTimeout(() => ranOut(new Error("
        "       `held fold ${i} did not finish within ${ranOutMs}ms`)), ranOutMs); })]);"
        " } finally { clearTimeout(timer); } }",
        [before, render_checks_model.SERVED_TIMEOUT_MS],
    )
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)


def test_a_pages_own_element_rules_leave_the_layers_controls_alone(browser, serve):
    """A page dressing its own `button` and `a` is dressing its prose. The controls a
    widget builds and the chrome's own buttons keep Leaf's face instead: a page's
    element rule once took the family and ink of half corpus.html's widget controls,
    and the family, ink, border and padding of the banner's and thread panel's. A rule
    that names the widget is the page restyling its controls on purpose, and reaches
    them; and a face the page sets on its body reaches its prose by inheritance and
    stops at the controls and the chrome, which state their own."""
    board = (
        '<h1>t</h1><lf-board id="b"><lf-column id="c1" label="To do">'
        '<lf-card id="k1">One</lf-card><lf-card id="k2">Two</lf-card></lf-column>'
        '<lf-column id="c2" label="Done"></lf-column></lf-board>'
        '<p>See <a href="#b">the board</a>.</p>'
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "t",
                board,
                # Grouped with a member that names the board, the bare `button` is
                # still the page's own, member by member.
                head="<style>button, a, lf-board .lf-absent { font-family: cursive;"
                " color: rgb(255, 0, 0); }"
                "body { font-style: italic; letter-spacing: 3px; }"
                "lf-board button { outline: 3px solid rgb(0, 128, 0); }</style>",
            )
        ),
    )
    faces = page.evaluate("""() => {
        const face = el => { const cs = getComputedStyle(el);
            return [el.className, cs.fontFamily, cs.color, cs.fontStyle, cs.letterSpacing,
                    cs.outlineColor]; };
        return {
            controls: [...document.querySelectorAll('main button.lf-ui')].map(face),
            chrome: [...document.querySelectorAll('.lf-chrome button')].map(face),
            prose: face(document.querySelector('main p > a')),
        };
    }""")
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
    # The deliberate route: every control the board builds takes the rule naming it.
    assert {face[5] for face in faces["controls"]} == {"rgb(0, 128, 0)"}, faces[
        "controls"
    ]


def test_a_packages_rules_reach_only_inside_its_widgets(browser, serve, tmp_path):
    """A package that declares widgets styles those widgets and nothing else, whatever
    its sheet says: its rule for `p` dresses the paragraph inside its widget and leaves
    the page's own paragraphs alone, and its rule for the widget's host still reaches
    the host. The confinement is the composition's (layer.py, `widget_confinement`),
    so it holds for any package, not only the ones this repository ships."""
    package = tmp_path / ".leaf"
    package.mkdir()
    (package / "theme.css").write_text(
        "p { color: rgb(0, 128, 0); }\n"
        "em { @media screen { color: rgb(0, 128, 0); } }\n"
        "lf-shelf { display: block; border: 3px solid rgb(0, 128, 0); }\n"
    )
    url = serve(
        leaf_page(
            "t",
            '<h1>t</h1><p id="out">Outside <em id="out-em">here</em>.</p>'
            '<lf-shelf id="shelf"><p id="in">Inside <em id="in-em">here</em>.</p>'
            "</lf-shelf>",
        ),
        layer_registry={
            "lf-shelf": {
                "description": "A project-supplied box.",
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "markup",
                "x-upgrade": False,
            }
        },
    )
    page = open_page(browser, url)
    faces = page.evaluate("""() => Object.fromEntries(
        ['out', 'in', 'out-em', 'in-em', 'shelf'].map(id => {
        const cs = getComputedStyle(document.getElementById(id));
        return [id, [cs.color, cs.borderTopWidth]]; }))""")
    assert faces["in"][0] == faces["in-em"][0] == "rgb(0, 128, 0)", faces
    assert "rgb(0, 128, 0)" not in (faces["out"][0], faces["out-em"][0]), faces
    assert faces["shelf"][1] == "3px", faces


def _shadow_tree_widget(tag):
    """A declaration and module for a widget that renders one word into a declared
    shadow tree."""
    declaration = {
        "description": "A project-supplied tree.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-shadow": True,
        "x-example": f'<{tag} id="example"></{tag}>',
    }
    module = f"""
import {{shadowStage}} from '/runtime/widget-api.js';
customElements.define('{tag}', class extends HTMLElement {{
  connectedCallback() {{
    if (this.shadowRoot) return;
    const word = document.createElement('span');
    word.textContent = '{tag}';
    shadowStage(this, [word]);
  }}
}});
"""
    return declaration, module


def test_a_packages_shadow_rules_reach_only_trees_its_widgets_host(
    browser, serve, tmp_path
):
    """Every declared shadow tree receives the layer's shadow sheet, so a package's
    `shadow.css` is confined there too: its rule for `span` dresses the tree its own
    widget hosts and not the tree another package's widget hosts."""
    own, own_module = _shadow_tree_widget("lf-own-tree")
    other, other_module = _shadow_tree_widget("lf-other-tree")
    project = tmp_path / ".leaf"
    project.mkdir()
    (project / "shadow.css").write_text("span { color: rgb(0, 128, 0); }\n")
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
    page = open_page(browser, url)
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
    element in the page wearing every scoped class at once must render exactly as
    its unclassed twin, and the classes styled at document level must be exactly
    the shared vocabulary a widget wears on purpose."""
    page = open_page(
        browser,
        serve(leaf_page("t", "<h1>t</h1><section id=s><p>words</p></section>")),
    )
    surface = page.evaluate("""() => {
        // The chrome's sheet is adopted, not linked (runtime/chrome.css).
        const sheet = [...document.styleSheets, ...document.adoptedStyleSheets].find(
            s => { try { return [...s.cssRules].some(r => r instanceof CSSScopeRule); }
                   catch { return false; } });
        const classes = sel => [...(sel || "").matchAll(/\\.([A-Za-z0-9_-]+)/g)].map(m => m[1]);
        const scoped = new Set(), global_ = new Set();
        const collect = (rules, into) => { for (const r of rules) {
            if (r instanceof CSSScopeRule) collect(r.cssRules, scoped);
            else if (r.selectorText) classes(r.selectorText).forEach(c => into.add(c));
            else if (r.cssRules) collect(r.cssRules, into); } };
        collect(sheet.cssRules, global_);
        // A shared class may take its document face from the authored theme rather than
        // from the runtime sheet. It is still outside this collision probe: any movement
        // it causes in the page is that deliberate global rule, not a leaked scoped one.
        const documentGlobal = new Set(global_);
        for (const other of [...document.styleSheets, ...document.adoptedStyleSheets]
                 .filter(s => s !== sheet))
            collect(other.cssRules, documentGlobal);
        const themed = new Set([...scoped].filter(
            c => !global_.has(c) && documentGlobal.has(c)));
        const probe = document.createElement("div"), plain = document.createElement("div");
        // Minus the shared vocabulary: a word document level dresses on purpose
        // (lf-key-badge, worn by the sequence's own layer and by an option's corner alike)
        // is named by the scoped rule that says when to paint it, and it would answer
        // this question with the reach it was given rather than with a leak.
        probe.className = [...scoped]
            .filter(c => !global_.has(c) && !themed.has(c)).join(" ");
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
        body.className = "lf-page-thread-body";
        body.textContent = "Authored thread words";
        document.getElementById("s").append(body);
        return { scoped: [...scoped], global: [...global_], themed: [...themed],
                 moved: Object.keys(a).filter(p => a[p] !== b[p]),
                 bodySelection: getComputedStyle(body).userSelect,
                 plainSelection: getComputedStyle(plain).userSelect };
    }""")
    assert "lf-live" in surface["scoped"] and len(surface["scoped"]) > 20, (
        "the @scope block is missing or nearly empty — the chrome has lost its rules"
    )
    assert surface["moved"] == [], (
        f"scoped chrome rules reached an element in the page: {surface['moved']}"
    )
    # The shared message body gets selectable-island rules only inside chrome.
    # Its authored copy keeps the document's selection behavior.
    assert surface["bodySelection"] == surface["plainSelection"]
    # A second document-level face comes from the authored theme, whose shadow sheet
    # also supplies the same controls inside declared widget trees. Keep that exception
    # as explicit as the runtime sheet's shared vocabulary below.
    assert set(surface["themed"]) == {
        "agent",
        # The shared vocabulary's faces are the theme's, for the reason chrome.css's
        # header gives: stated in the adopted sheet they beat each component's own rule
        # on nothing better than that sheet arriving last. The runtime sheet still names
        # the badge inside its scope, to say where the chrome's own copies stand, and the
        # movement the theme's rule causes is that deliberate face.
        "lf-key-badge",
        # The aim floor is one plain selector list in shadow.css, so that a finger's
        # 44px reaches the document, the chrome and every declared widget tree from one
        # rule. Each name below is a press the chrome also dresses inside its scope, so
        # the floor is a second, document-level rule on a scoped name. It states a
        # minimum on two axes and nothing else. The chip and the margin entry are on
        # that list too and are not here: nothing inside the scope names them any more,
        # so they are no longer a scoped vocabulary this exception has to cover.
        "lf-command-reference-command",
        "lf-layer-reference",
        "lf-preview",
        "lf-quote",
        "lf-thread-action",
        "lf-version-diff",
        "lf-version-row",
        "lf-compose-field",
        # The hint an empty field shows is slotted into that field: shadow.css keeps
        # it on one line and the authored theme sizes the option composer's copy,
        # while the scoped rule only sets its line height in the response bar.
        "lf-compose-placeholder",
        "lf-compose-submit",
        # The one canonical composer can be seated in a widget's own Thread outlet,
        # where the chrome's scoped rules cannot reach it. The authored theme dresses
        # that seat at document level, under [data-lf-presentation="inline"], so every
        # part of the response bar the seat carries — its bar, its field's wrapper,
        # its target press and the response options behind it — wears a document face
        # for the same reason .lf-margin-projection below does.
        "lf-composer",
        # A thread keeps the authored theme's shared card and message
        # structure when the margin projects it into the chrome.
        "lf-page-thread-body",
        "lf-thread-root-meta",
        "lf-msg-meta",
        # The row that carries a message's name, time and state, and the word saying a
        # send is still going. Both are that same shared structure — the theme dresses
        # them wherever a message renders — and the scoped rules do nothing but fit the
        # row into the margin card's sticky head.
        "lf-page-thread-head",
        "lf-msg-sending",
        # The message's own box. The theme gives the authored and margin-projected copies
        # their spacing while the chrome's scoped rules dress the panel's. The runtime
        # sheet used to name it at document level too, in a `.lf-page-thread-msg.lf-ui`
        # spelling of the shared face that answered nothing once that face moved to the
        # theme: no rule anywhere states a face on this class, so the extra weight was
        # only weight.
        "lf-page-thread-msg",
        "lf-page-thread",
        "lf-edited",
        # A host receipt's mark is part of that same shared message structure: the
        # head carries it in the panel and inline, so the theme dresses it here.
        "lf-msg-failure",
        "lf-fab",
        "lf-fab-bar",
        "lf-focus-within",
        # The margin layer is chrome, and its whole document face — placement by
        # anchor, the rail and pin postures, the lanes a pane's rows stand in — is the
        # authored theme's. The runtime sheet names it only to say which plane it
        # stands on, so the movement the theme's rule causes is that deliberate face
        # rather than a leaked one.
        "lf-margin-cluster",
        # Page Map rows share the margin entry's state and icon face in theme.css.
        "lf-margin-kind",
        "lf-margin-lane",
        "lf-margin-projection",
        "lf-page-map-action",
        "lf-msg-head",
        "lf-react-open",
        "lf-react-palette",
        "lf-react-strip",
        "lf-react-trigger",
        # An icon action's glyph, sized and seated in shadow.css so a press wearing one
        # is the same object in the page, in a declared widget tree and in the chrome.
        # The scoped rules only pull the margin preview's stepper copies to its ends.
        "lf-action-icon",
        "lf-resolve",
        # The inline seat again: the composer's own row of response actions.
        "lf-response-action",
        "lf-response-action-label",
        "lf-response-action-space",
        "lf-response-control",
        "lf-response-more",
        "lf-response-open",
        "lf-response-options",
        # The same metadata action slot carries settlement in panel and inline seats;
        # the authored theme gives both views the same alignment.
        "lf-thread-meta-actions",
        # The general text box's face is the theme's (the `.lf-ui textarea` rule), so a
        # widget's own box that names the same property outranks it in the shared layer.
        # It names the compact response field only to exclude it, since that field takes
        # its whole geometry from the response controls it shares a baseline with, and
        # the focus a native label projects only as the state that rings the box.
        "lf-fab-input",
        "lf-focus",
        # Active buttons share the theme's existing .lf-btn.on state.
        "on",
        # Primary buttons keep the authored theme's accent action face when they
        # enter chrome rows whose quiet controls deliberately clear that paint.
        "primary",
        # Under a finger a reaction trigger meets the aim floor and an agent message's
        # head row holds it (shadow.css), since both stand in declared widget trees too.
        "lf-msg",
        "lf-react",
    }, "the authored-theme class surface changed: widen the exception on purpose"
    # Every one of these is worn by something the runtime puts inside the page rather
    # than inside its own container: a scoped rule cannot reach the copy in the page.
    # What is not here is the shared vocabulary, whose faces the theme states — see the
    # exception above, and chrome.css's header for why.
    assert {c for c in surface["global"] if c.startswith("lf-")} == {
        # Drawing is a body state, and an inline thread lives inside authored
        # widget markup. Both deliberately cross the chrome scope so drawing can spare
        # the thread's controls.
        "lf-thread-seat",
        "lf-ui",
        # A native label can pass through an intermediate focus target. This projects
        # the held control's focus ring until activation settles.
        "lf-focus-visible",
        "lf-btn",
        "lf-over-mark",
        "lf-mark-el",
        "lf-projected-mark",  # an element mark projects above authored paint
        "lf-mark-hover",  # the same element mark, for the one the pointer indicates
        "lf-mark-here",  # the same element mark, for the comment the user is in
        "lf-pending",
        "lf-ins-block",
        "lf-skip",  # the keyboard entry point stands before the chrome container
        "lf-aiming",
        "lf-over-item",
        # The shared textual thread box renders both in page-owned widget seats and in
        # the chrome-owned margin preview, so its pasted-image shelf is dressed here.
        # Its message rows are not: they take the shared face from the theme like every
        # other injected element, and the chrome dresses only the margin preview's copy,
        # from inside its own scope.
        "lf-say",
        # A pasted image's writing projection and inspection control cross the same
        # seam: widget thread boxes live in the page, while general comments,
        # anchored comments, and the viewer live in the chrome.
        "lf-compose",
        "lf-general",
        "lf-composer-media",
        "lf-composer-media-item",
        "lf-composer-media-open",
        "lf-composer-media-remove",
        "lf-message-media",
        "lf-media-open",
        # A standing reaction's paint on the page: the element outline and margin glyph.
        "lf-react-el",
        "lf-react-mark",
        # A visual reaction's outline on its target while its shared action bar is
        # standing.
        "lf-action-target",
        # A comparison's target paint and deletions stand inside the block they are
        # about; a text block's parent may not accept a sibling beside it.
        "lf-version-inline",
        "lf-version-inline-deletion",
    }, (
        "the document-level class surface changed: widen the shared vocabulary on purpose"
    )


# A page long enough to hold a reading position worth losing, and a change to decide
# in each document, so every reading below has the same widget in both places.
REPLY_TRAVEL_PAGE = leaf_page(
    "travel",
    "<h1 id='tv-h'>Session store</h1>"
    + "".join(
        f"<p id='tv-p{n}'>Paragraph {n}. "
        + "Words enough to wrap the column. " * 8
        + "</p>"
        for n in range(40)
    ),
)

PAGE_CHANGE = (
    '<lf-suggestion id="tv-doc-sug">'
    '<lf-old><p id="tv-doc-old">Sessions live five minutes.</p></lf-old>'
    "<lf-new><p>Sessions live ninety seconds.</p></lf-new>"
    "</lf-suggestion>"
)
CHANGE_HEAD = "<h1 id='dc-h'>Session store</h1>"
CHANGE_PAGE = leaf_page("doc-change", CHANGE_HEAD + PAGE_CHANGE)
# The same page with the change taken out of it, for the arm that carries the change
# in a message instead: the two must differ in which document holds it and in nothing
# else.
BARE_PAGE = leaf_page("doc-change", CHANGE_HEAD)
REPLY_CHANGE = PAGE_CHANGE.replace("tv-doc-", "tv-msg-")

BOTH_BOXES = """() => ({
  page: document.scrollingElement.scrollTop,
  panel: document.querySelector('.lf-threads').scrollTop,
})"""


def seed_reply(d, markup, anchor_id, chatter=0, after=0):
    """A thread whose reply carries `markup`, with a thread anchored on it.

    `chatter` is what makes the panel a scroller of its own: a travel that lands by
    accident when the whole list already fits proves nothing about which box moved.
    `after` is what makes the middle of that list reachable — a widget in the last
    message can only be brought to the end of the scroll range, which `scrollIntoView`
    reaches on its own, so a centring assertion over one asserts nothing.
    """
    for n in range(chatter):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"tv-pad{n}",
                "author": "user",
                "revision": 1,
                "text": f"Aside {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-decisioned",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "tv-decisioned",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": markup,
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-on-it",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": anchor_id},
        },
    )
    for n in range(after):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"tv-later{n}",
                "author": "user",
                "revision": 1,
                "text": f"Later {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )


def test_a_thread_on_a_widget_in_a_reply_travels_in_the_panel_that_holds_it(
    browser, serve
):
    """Pressing a thread's quote label moves the user to what it is about — in the
    box that box is in.

    An element anchor can now name a widget an agent sent, and such a widget is
    scrolled by the panel's own list and by nothing else. The travel was written with
    the document's scroller in it twice, once for the banner clearance it reads and
    once for the jump it makes, so the press spent its whole arithmetic on the page
    behind the panel: the user lost their place in the document over a thread about
    something that was never in it. The panel arrived anyway, which is what made it
    quiet — the platform's own scrollIntoView moves every ancestor box, so the widget
    came into view, nudged to the nearest edge rather than centred, while the document
    slid under it.

    The document is the control: the same press on a thread about a paragraph must
    still move the page, or this only says that nothing scrolls."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-ask id="tv-decision-region"><h3>Which store should I write up?</h3>'
        '<lf-options id="tv-decision" choose>'
        '<lf-option id="tv-redis">Redis</lf-option>'
        '<lf-option id="tv-cookie">A signed cookie</lf-option>'
        "</lf-options></lf-ask>",
        "tv-decision",
        chatter=10,
        after=10,
    )
    # A second thread, on the document, whose travel is the one that must still move
    # the page. Written after the first so the panel holds both.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-on-page",
            "author": "user",
            "revision": 1,
            "text": "This one is about the page.",
            "anchor": {"section": "tv-p30"},
        },
    )
    # Reduced motion, so both travels jump and every reading below is taken straight
    # after the press. A glide would leave the document's own scroll still running
    # while the assertion that it never started reads its first frame.
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    page.evaluate("() => { document.scrollingElement.scrollTop = 1200; }")
    page.evaluate("() => { document.querySelector('.lf-threads').scrollTop = 0; }")

    # Where the travel says it is taking the widget: centred in the list's landing band
    # (the list less its declared scroll-padding), or as near as the list can come — a
    # widget in the last message is past the middle of what the box can show, and the
    # end of the scroll range is the whole of the answer there. The same arithmetic the travel uses, so this asserts where it went and
    # not merely that something moved.
    WHERE = """() => {
      const box = document.querySelector('.lf-threads');
      const view = box.getBoundingClientRect();
      const el = document.getElementById('tv-decision').getBoundingClientRect();
      const style = getComputedStyle(box);
      const above = parseFloat(style.scrollPaddingTop) || 0;
      const below = parseFloat(style.scrollPaddingBottom) || 0;
      const room = box.clientHeight - above - below;
      return { at: el.top - view.top,
               want: box.clientTop + above + Math.max((room - el.height) / 2, 0),
               atEnd: box.scrollTop >= box.scrollHeight - box.clientHeight - 1 };
    }"""
    focus_panel_thread(page.locator('.lf-thread[data-id="tv-on-it"]'))
    thread = page.locator('.lf-thread[data-id="tv-on-it"] .lf-quote')
    thread.scroll_into_view_if_needed()
    before = page.evaluate(BOTH_BOXES)
    thread.click()
    # The exact destination is the completion fact: the target first comes into view,
    # then the region-local correction centres it.
    try:
        page.wait_for_function(
            f"() => {{ const w = ({WHERE})(); return Math.abs(w.at - w.want) < 2; }}"
        )
    except PlaywrightTimeout:
        seen = page.evaluate(WHERE)
        raise AssertionError(
            f"the widget stopped {seen['at']:.0f}px into the list where centring it "
            f"wanted {seen['want']:.0f}px — the travel never reached the box the "
            "widget is in"
        ) from None
    landed = page.evaluate(WHERE)
    after = page.evaluate(BOTH_BOXES)
    assert after["page"] == before["page"], (
        f"a thread about a widget in the panel moved the document "
        f"{before['page']}px → {after['page']}px; the user's place in the page is "
        "not this thread's to spend"
    )
    assert after["panel"] != before["panel"], (
        "the panel did not move at all, so the page holding still says nothing"
    )
    assert not landed["atEnd"], (
        "the list is at the end of its range, which scrollIntoView reaches on its own "
        "— the seed must leave messages below the one carrying the widget, or the "
        "centring below is carried by the clamp"
    )
    assert abs(landed["at"] - landed["want"]) < 2, (
        f"the widget stopped {landed['at']:.0f}px into the list where centring it "
        f"wanted {landed['want']:.0f}px — brought into view by the platform rather "
        "than travelled to"
    )

    # The control: the page's own thread still moves the page.
    focus_panel_thread(page.locator('.lf-thread[data-id="tv-on-page"]'))
    page.locator('.lf-thread[data-id="tv-on-page"] .lf-quote').click()
    page.wait_for_function(
        f"() => document.scrollingElement.scrollTop !== {before['page']}"
    )


def test_a_delayed_accordion_reveal_yields_to_the_users_new_thread(browser, serve):
    """A filtered Ask arrival cannot open its old target over a later row selection."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    target = question.locator(
        "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' lf-thread ')][1]"
    )
    target_id = target.get_attribute("data-id")
    page.get_by_role("searchbox", name="Find in threads").fill("stay blocked")
    expect(target).to_have_attribute("hidden", "")
    hold_visible_thread_presentation(page, target_id)
    page.locator(".lf-threads").focus()
    page.keyboard.press("a")
    page.wait_for_function(
        "window.visibleThreadPresentationHeld === true", timeout=3000
    )
    later = page.locator(".lf-thread:not([hidden])").first
    later_id = later.get_attribute("data-id")
    assert later_id != target_id
    later = page.locator(f'.lf-thread[data-id="{later_id}"]')
    later.locator(".lf-thread-summary").click()
    expect(later).to_have_attribute("open", "")
    page.evaluate("releaseVisibleThreadPresentation()")
    rendered(page)
    expect(later.locator(".lf-thread-summary")).to_be_focused()
    expect(later).to_have_attribute("open", "")
    expect(target).not_to_have_attribute("open", "")


def test_a_design_thread_about_fixed_chrome_moves_neither_box(browser, serve):
    """A part that stands over both documents is in neither, and nothing travels to it.

    Design mode lets a user comment on fixed runtime parts, and several of them are
    `position: fixed` — the shortcut bar, the banner, the composer. Such a part is on screen
    already, and it is in no scroller's flow, so its rect answers to the viewport rather
    than to either region's scroll. `scrollerFor` says which of the two regions an
    element belongs to, which is the right question for a widget in a message and no
    question at all for one of these. Spent on it, the arithmetic reads a fixed rect as
    though it were a place in a scroller and moves that scroller by a number meaning
    nothing in it: measured, pressing a thread about the shortcut bar took the document
    370px away from where the user had it, at every starting position.

    The control is a thread about the page, which must still travel."""
    url = serve(REPLY_TRAVEL_PAGE)
    d = serve.page_dir
    for n in range(14):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"fx-pad{n}",
                "author": "user",
                "revision": 1,
                "text": f"Aside {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )
    # The shape design mode writes about design: `about` says which, and the anchor
    # names the part the runtime gave an id.
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "fx-on-design",
            "author": "user",
            "revision": 1,
            "about": "design",
            "text": "The shortcut bar reads dim against the wash.",
            "anchor": {"section": "lf-shortcut-bar"},
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "fx-on-page",
            "author": "user",
            "revision": 1,
            "text": "And this one is about the page.",
            "anchor": {"section": "tv-p30"},
        },
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator('.lf-thread[data-id="fx-on-design"]')).to_have_count(1)
    expect(page.locator(".lf-shortcut-bar")).to_be_visible()

    page.evaluate("() => { document.scrollingElement.scrollTop = 1200; }")
    # Where the user is standing when they press: the thread on screen, which is
    # also what the driver's own scroll-into-view would arrange. Read after it, so the
    # baseline is the page as the press finds it rather than as the test left it.
    focus_panel_thread(page.locator('.lf-thread[data-id="fx-on-design"]'))
    thread = page.locator('.lf-thread[data-id="fx-on-design"] .lf-quote')
    thread.scroll_into_view_if_needed()
    before = page.evaluate(BOTH_BOXES)
    seen = """() => {
      const t = document.querySelector('.lf-thread[data-id="fx-on-design"]');
      const view = document.querySelector('.lf-threads').getBoundingClientRect();
      return t ? t.getBoundingClientRect().top - view.top : null;
    }"""
    stood = page.evaluate(seen)
    thread.click()
    # Reduced motion makes both region-local scroll operations instant, so the read
    # directly after the press is the whole travel.
    after = page.evaluate(BOTH_BOXES)

    assert after == before, (
        f"a design thread about fixed chrome moved something: {before} -> {after}"
    )
    assert page.evaluate(seen) == stood, (
        "the press moved the thread the user pressed, which is the surface they were "
        "looking at"
    )

    # The control: a thread about the page still travels.
    focus_panel_thread(page.locator('.lf-thread[data-id="fx-on-page"]'))
    page.locator('.lf-thread[data-id="fx-on-page"] .lf-quote').click()
    assert page.evaluate(BOTH_BOXES)["page"] != before["page"], (
        "a thread about a paragraph no longer moves the document, so the stillness "
        "above says only that nothing scrolls"
    )


def test_a_settlement_in_a_reply_leaves_its_own_anchor_on_the_page(browser, serve):
    """A decided change keeps whatever of itself is still showing, wherever it stands.

    `settledAway` asks whether a decision emptied an element: every child now a retired
    slot or the runtime's own apparatus, with no words of its own left. Asked about the
    page that test is right; asked about a change an agent sent in a reply it was asked
    the wrong way round, because the panel holding it is itself the runtime's apparatus
    and so every child of it answered yes. One accepted slot then emptied a change whose
    other half was on screen: the anchor a user had put on it stopped resolving, the
    outline came off, and the thread stood detached beside the words it was about.

    The same change on the page is the control, and the two must agree."""
    for where, markup, wid in (
        ("the page", CHANGE_PAGE, "tv-doc-sug"),
        ("a reply", BARE_PAGE, "tv-msg-sug"),
    ):
        url = serve(markup)
        d = serve.page_dir
        if wid.startswith("tv-msg"):
            seed_reply(d, REPLY_CHANGE, wid)
        else:
            events_model.append_event(
                d,
                {
                    "kind": "comment",
                    "id": "tv-on-it",
                    "author": "user",
                    "revision": 1,
                    "text": "Why ninety?",
                    "anchor": {"section": wid},
                },
            )
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": wid,
                "action": "decide",
                "detail": {"outcome": "accept"},
            },
        )
        page = open_page(browser, url)
        resized(page, 1280, 900)
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        if wid.startswith("tv-msg"):
            focus_panel_thread(page.locator('.lf-thread[data-id="tv-decisioned"]'))
            rendered(page)
        settled = page.evaluate(
            """(wid) => {
                 const el = document.getElementById(wid);
                 const quote = document.querySelector('.lf-thread[data-id="tv-on-it"] .lf-quote');
                 return { state: el?.dataset.lfState,
                          retired: [...(el?.querySelectorAll('[data-lf-retired]') ?? [])].length,
                          marked: Boolean(el?.classList.contains('lf-mark-el')),
                          detached: quote?.classList.contains('detached') };
               }""",
            wid,
        )
        assert settled["state"] == "accept" and settled["retired"] == 1, (
            f"{where}: the change did not settle, so nothing here is being read "
            f"({settled})"
        )
        assert not settled["detached"] and settled["marked"], (
            f"{where}: the accepted change took its own anchor off the page "
            f"({settled}) — its other half is still showing"
        )


def test_a_mark_in_the_layer_promises_no_press_the_layer_will_not_take(browser, serve):
    """An outline in the chrome says which element, and stops there.

    An element anchor wears its outline wherever its element stands, the layer's own
    parts included — that is what lets a design comment about the banner point at the
    banner. What the outline may not do there is offer the hand: `markAt` refuses a
    press inside the chrome on purpose, because what the chrome holds keeps its own
    presses. The Threads button opens the panel and an option takes a pick; neither
    of them opens a thread. So the pointer stood over a marked question an agent had
    asked, promising a click nothing took.

    The page's own mark is the control, and it keeps the hand it has always had."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-ask id="tv-decision-region"><h3>Which store should I write up?</h3>'
        '<lf-options id="tv-decision" choose>'
        '<lf-option id="tv-redis">Redis</lf-option>'
        "</lf-options></lf-ask>",
        "tv-decision",
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-on-page",
            "author": "user",
            "revision": 1,
            "text": "About the page.",
            "anchor": {"section": "tv-p3"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    focus_panel_thread(page.locator('.lf-thread[data-id="tv-decisioned"]'))
    rendered(page)

    marks = page.evaluate(
        """() => [...document.querySelectorAll('.lf-mark-el')].map((el) => ({
             id: el.id, chrome: Boolean(el.closest('.lf-chrome')),
             cursor: getComputedStyle(el).cursor,
           }))"""
    )
    inside = [m for m in marks if m["chrome"]]
    outside = [m for m in marks if not m["chrome"]]
    assert inside and outside, (
        f"this needs a mark in each document to compare; got {marks}"
    )
    assert all(m["cursor"] == "pointer" for m in outside), (
        f"the page's own mark lost its hand, so the reading below is about nothing: "
        f"{outside}"
    )
    assert all(m["cursor"] != "pointer" for m in inside), (
        f"a mark in the layer offers the hand and no press is taken there: {inside}"
    )
    # And the other half of the sentence, since a cursor is only a promise about a
    # press: the press itself, on the marked widget's own words, reaching no thread.
    opened = page.evaluate(
        "() => document.querySelector('.lf-thread[data-id=\"tv-on-it\"]')?.className"
    )
    page.locator("#tv-decision").click(position={"x": 4, "y": 4})
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-thread[data-id=\"tv-on-it\"]')"
            "?.className"
        )
        == opened
    ), "a press on a mark in the layer reached its thread after all"


def test_a_control_in_a_reply_holds_the_page_s_control_shape(browser, serve):
    """A change sent in a reply keeps the canonical circular control.

    A reply is upgraded inside a closed comment panel, where its box is zero, and its
    controls used to be measured there and collapse. The control's circle is fixed,
    so it is the same shape in the reply as on the page.

    The page's own change is the geometry reference."""
    reply_url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(serve.page_dir, REPLY_CHANGE, "tv-msg-sug")
    page = open_page(browser, reply_url)
    resized(page, 1280, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    focus_panel_thread(page.locator('.lf-thread[data-id="tv-decisioned"]'))
    geometries = (
        "() => [...document.querySelectorAll("
        f"'.lf-margin-entry{any_owner_entry('suggestion')}')]"
        ".map((b) => { const s = getComputedStyle(b); "
        "return [s.width, s.height, s.borderRadius]; })"
    )
    in_reply = page.evaluate(geometries)
    assert in_reply and all(shape == ["32px", "32px", "50%"] for shape in in_reply), (
        f"a control in a reply lost the canonical circle: {in_reply}"
    )
    page.close()

    # The same controls on the page, whose numbers these have to be.
    page = open_page(browser, serve(CHANGE_PAGE))
    resized(page, 1280, 900)
    on_page = page.evaluate(geometries)
    assert in_reply == on_page, (
        f"the same control measures {in_reply} in a reply and {on_page} on the page"
    )


def test_a_boxless_widget_in_a_reply_still_shows_the_parts_it_paints(
    browser, serve, tmp_path, monkeypatch
):
    """A wrapper that generates no box shows as what its contents paint — in either
    document.

    `shownParts` falls back to an element's children when the element itself has no
    box, which is what a mark hangs on and what a decision's ring hangs on. It kept the
    runtime's own apparatus out of that fallback by asking whether each child was
    under the runtime's chrome, and a widget an agent sent in a reply is: the panel
    over it answers for every child, so the fallback filtered all of them away and the
    widget showed as nothing at all. Bounded at the widget, the panel above it is no
    longer its own apparatus and the parts come back.

    `display: contents` on a widget is a project's line to write — the shipped
    vocabulary has none today, and `shownParts` exists because any layer can — so a
    project theme is what puts one here. The page's own copy is the control."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".leaf").mkdir(exist_ok=True)
    (tmp_path / ".leaf" / "theme.css").write_text(
        "/* a project styling a wrapper away, which is any layer's to do */\n"
        "lf-options { display: contents }\n"
    )
    url = serve(REPLY_TRAVEL_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    # A group reporting rather than asking: the joined control the layer draws for
    # `choose` states its own display at a weight a project's bare tag rule does not
    # reach, and the subject here is a boxless wrapper rather than a cascade fight.
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-decision">'
        '<lf-option id="tv-redis" chosen>Redis</lf-option>'
        "</lf-options>",
        "tv-decision",
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    focus_panel_thread(page.locator('.lf-thread[data-id="tv-decisioned"]'))
    parts = page.evaluate(
        """async () => {
             const { shownParts } = await window.__lfRuntimeImport('/runtime/widget-api.js');
             const el = document.getElementById('tv-decision');
             return { boxless: el.getBoundingClientRect().height === 0,
                      display: getComputedStyle(el).display,
                      parts: shownParts(el).map((p) => p.id || p.localName) };
           }"""
    )
    assert parts["boxless"], (
        f"the widget draws as {parts['display']!r}, so it has a box of its own and "
        "the fallback below was never reached — the project layer's rule lost to one "
        "the shipped theme states at a weight a bare tag selector cannot reach"
    )
    assert parts["parts"], (
        "a widget an agent sent shows as nothing: no box of its own, and every part "
        "its contents paint read as the panel's apparatus"
    )


def test_a_panel_reads_a_log_that_lost_the_message_a_reply_answers(browser, serve):
    """The browser walks the same relation as `build_threads`, and tore the same way.

    A crash tears one line and `read_events` keeps reading past it, so the events the
    server hands the browser can hold a reply whose message is gone. The panel is built
    by walking replies onto their parents, and the walk threw where the parent was
    missing — taking down not the thread but the whole reconcile, on a page whose log
    had already been read successfully by the side that wrote it. The missing id stays
    the recovered thread's identity, so a structural Ask in one surviving reply also
    stays visible after a later plain reply."""
    url = serve(REPLY_TRAVEL_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-lost",
            "author": "user",
            "revision": 1,
            "text": "the question nobody can read any more",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "id": "tv-kept",
            "author": "agent",
            "parent": "tv-lost",
            "revision": 1,
            "text": "the answer that survived it",
            "markup": (
                '<lf-ask id="tv-decision"><h2>Which recovery should we use?</h2>'
                '<lf-options id="tv-choice" choose>'
                '<lf-option id="tv-retry">Retry</lf-option>'
                '<lf-option id="tv-stop">Stop</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "id": "tv-later",
            "author": "agent",
            "parent": "tv-kept",
            "revision": 1,
            "text": "the later plain reply",
        },
    )
    log = d / "events.jsonl"
    lines = log.read_text(encoding="utf-8").split("\n")
    torn = next(i for i, line in enumerate(lines) if '"id": "tv-lost"' in line)
    lines[torn] = lines[torn][: len(lines[torn]) // 2]
    log.write_text("\n".join(lines), encoding="utf-8")

    page = open_page(browser, url)
    resized(page, 1280, 900)
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-thread")).to_contain_text("the answer that survived it")
    expect(page.locator(".lf-thread")).to_contain_text("the later plain reply")
    expect(page.locator('.lf-thread[data-id="tv-lost"]')).to_have_count(1)
    expect(page.locator(".lf-needs")).to_have_text("You (1)")

    # The lost id names the thread and no message, so the user's reply and
    # resolve address the message that opens it now, and the log admits both.
    card = page.locator('.lf-thread[data-id="tv-lost"]')
    card.locator(".lf-thread-summary").click()
    with sending(page, "a reply in the recovered thread"):
        write(card.locator("leaf-text"), "Retry is fine.")
        card.locator(".lf-thread-send").click()
    expect(card).to_contain_text("Retry is fine.")
    with sending(page, "resolving the recovered thread"):
        card.locator(".lf-resolve").click()
    addressed = [
        (event["kind"], event["parent"])
        for event in events_model.read_events(d)
        if event["kind"] in {"reply", "resolve"} and event.get("author") == "user"
    ]
    assert addressed == [("reply", "tv-kept"), ("resolve", "tv-kept")], addressed
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")


THREAD_STANDING = """() => {
  const active = document.activeElement;
  const card = active?.closest('.lf-thread');
  if (!card) return null;
  const list = card.closest('.lf-threads');
  const peer = [...list.querySelectorAll(':scope > .lf-thread:not([hidden])')]
    .find(other => other !== card && !other.matches(':focus-within'));
  const paint = getComputedStyle(card);
  const focusPaint = getComputedStyle(active);
  const resting = peer && getComputedStyle(peer);
  const box = card.getBoundingClientRect();
  const viewport = list.getBoundingClientRect();
  return {
    background: paint.backgroundColor,
    outline: focusPaint.outlineStyle,
    restingBackground: resting?.backgroundColor ?? null,
    cuts: [
      box.top < viewport.top - .5 && 'top',
      box.right > viewport.right + .5 && 'right',
      box.bottom > viewport.bottom + .5 && 'bottom',
      box.left < viewport.left - .5 && 'left',
    ].filter(Boolean),
    scrolled: list.scrollHeight > list.clientHeight,
  };
}"""


def standing_thread(page):
    """The current thread's surface paint, beside a resting thread for comparison."""
    return page.evaluate(THREAD_STANDING)


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
def test_the_thread_list_ring_paints_above_its_scrolling_contents(
    browser, serve, color_scheme
):
    """Edge-crossing threads and fields cannot cover the list's focus ring."""
    url = serve(PANEL_PAGE)
    for i in range(30):
        panel_comment(
            serve.page_dir,
            f"The list needs somewhere to land, item {i}.",
            {"section": "lede"},
        )
    panel_comment(serve.page_dir, "The next section.", {"section": "how-store"})
    context = browser.new_context(
        viewport={"width": 459, "height": 856},
        color_scheme=color_scheme,
        reduced_motion="reduce",
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    assert threads.evaluate("el => el.scrollHeight > el.clientHeight")
    resting_ground = threads.evaluate(
        "el => [getComputedStyle(el).backgroundColor, "
        "getComputedStyle(el).backgroundImage]"
    )
    page.locator('.lf-thread-panel [aria-label="Close threads"]').click()
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)

    expect(threads).to_be_focused()
    paint = threads.evaluate(
        """el => {
              const list = getComputedStyle(el);
              const frame = el.parentElement;
              const current = getComputedStyle(frame, '::after');
              const listBox = el.getBoundingClientRect();
              const ringBox = frame.getBoundingClientRect();
              const footBox = frame.nextElementSibling.getBoundingClientRect();
              const dividerBox = frame.nextElementSibling.firstElementChild
                .getBoundingClientRect();
              return {
                listOutline: list.outlineStyle,
                outline: current.outlineStyle,
                width: current.outlineWidth,
                offset: current.outlineOffset,
                ringName: current.getPropertyValue('--lf-here-ring').trim(),
                ground: [list.backgroundColor, list.backgroundImage],
                sameBox: ['left', 'top', 'right', 'bottom'].every(
                  edge => ringBox[edge] === listBox[edge]
                ),
                joinedFooter: ringBox.bottom === footBox.top
                  && ringBox.bottom === dividerBox.top,
              };
            }"""
    )
    assert paint["listOutline"] == "none"
    assert paint["outline"] == "solid"
    assert paint["width"] == "2px"
    assert paint["offset"] == "-2px"
    assert paint["ringName"] == "thread-list"
    assert paint["ground"] == resting_ground
    assert paint["sameBox"]
    assert paint["joinedFooter"], (
        "the focused list ended before the footer divider and left a second "
        "ownerless strip between their contours"
    )

    # Reproduce the reported paint order: a thread owns the pixels just inside the
    # top edge while one of the list's controls crosses the bottom edge.
    # The focus outline must remain continuous over both foreground elements. Give
    # those contents an extreme local rank too: the list's stacking context, rather
    # than today's particular z-index values, keeps all of its contents under the cue.
    collision = threads.evaluate(
        """el => {
              el.style.scrollBehavior = 'auto';
              const box = el.getBoundingClientRect();
              for (let y = 1; y <= el.scrollHeight - el.clientHeight; y += 1) {
                el.scrollTop = y;
                const top = document.elementFromPoint(box.left + box.width / 2, box.top + 1);
                const bottom = document.elementFromPoint(
                  box.left + box.width / 2, box.bottom - 2
                );
                if (top?.closest('.lf-thread') && bottom !== el && el.contains(bottom))
                  return {scrollTop: el.scrollTop, top: top.tagName, bottom: bottom.tagName};
              }
              return null;
            }"""
    )
    assert collision is not None
    threads.evaluate(
        """el => {
              const box = el.getBoundingClientRect();
              const top = document.elementFromPoint(box.left + box.width / 2, box.top + 1);
              const bottom = document.elementFromPoint(
                box.left + box.width / 2, box.bottom - 2
              );
              top.closest('.lf-thread').style.zIndex = '9999';
              bottom.style.position = 'relative';
              bottom.style.zIndex = '9999';
            }"""
    )
    # The first and last device row inside the list's own box. An element clip is
    # taken from a rect that need not land on device pixels — the list's top is
    # 247.67 at this width — so its outermost row is the panel's paint, not the ring.
    edges = threads.evaluate(
        """el => { const b = el.getBoundingClientRect();
              return [Math.ceil(b.left), Math.floor(b.right),
                      Math.ceil(b.top), Math.floor(b.bottom) - 1]; }"""
    )
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    left, right, first, last = edges
    for y in (first, last):
        assert {shot.getpixel((x, y)) for x in range(left, right)} == {accent}, (
            f"the ring is broken across row {y}"
        )

    page.keyboard.press("t")
    expect(
        page.locator(
            ".lf-threads > .lf-thread:not([hidden]) > .lf-thread-summary"
        ).first
    ).to_be_focused()
    assert (
        threads.evaluate(
            "el => getComputedStyle(el.parentElement, '::after').outlineStyle"
        )
        == "none"
    )


def thread_mark_fault(reading, ring="solid"):
    """Why a current thread is indistinguishable from a resting card, if it is.

    The card the keyboard stands on wears the inset ring every keyboard target wears,
    over the quiet ground that says the user is in it; a pointer arrival paints the
    ground alone, and its caller says so with `ring="none"`. `rings_drawn` reads whether
    a ring is whole; this reads that the marks the arrival owes are there."""
    if not reading:
        return "focus is not inside a thread"
    if reading["restingBackground"] is None:
        return "there is no resting peer to distinguish the current thread from"
    if reading["outline"] != ring:
        return f"the current thread wears a {reading['outline']} outline, not {ring}"
    if reading["background"] == reading["restingBackground"]:
        return "the current thread's surface is the same as a resting card's"
    if reading["cuts"]:
        return f"the current thread's {', '.join(reading['cuts'])} edge is cut"
    return None


def test_forced_colors_keep_current_thread_regions_distinct(browser, serve):
    """High contrast keeps the current region visible from list, card, and reply box."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The current card.", {"section": "lede"})
    panel_comment(d, "Its resting peer.", {"section": "how-store"})
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, forced_colors="active"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate("() => document.activeElement?.blur()")
    # The named address toggles the panel it names, so from a panel opened by its
    # visible control the first completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    threads = page.locator(".lf-threads")
    expect(threads).to_be_focused()
    expect(threads).to_have_css("outline-style", "none")
    assert (
        threads.evaluate(
            "el => getComputedStyle(el.parentElement, '::after').outlineStyle"
        )
        == "solid"
    )
    current = page.locator(".lf-thread").filter(has_text="The current card.")
    peer = page.locator(".lf-thread").filter(has_text="Its resting peer.")
    box = current.bounding_box()
    assert box
    page.mouse.click(box["x"] + 6, box["y"] + 6)
    expect(current.locator(".lf-thread-summary")).to_be_focused()
    assert current.evaluate("el => el.matches(':focus-within')")
    assert not current.evaluate("el => el.matches(':focus-visible')")
    assert current.evaluate("el => getComputedStyle(el).borderColor") != peer.evaluate(
        "el => getComputedStyle(el).borderColor"
    )
    reply = current.locator("leaf-text")
    reply.click()
    expect(reply).to_be_focused()
    assert current.evaluate("el => getComputedStyle(el).borderColor") != peer.evaluate(
        "el => getComputedStyle(el).borderColor"
    )


def test_no_focus_mark_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered(
    browser, serve
):
    """Where the user is standing has to be visible from wherever they walked to it.
    A walked-to thread wears the inset ring over its own quiet ground; compact controls
    inside the list draw the ring outside themselves. Either treatment can disappear at
    a scroll edge or beneath a neighbour, and the thread list has had both failures in
    both directions.

    So this walks the list the way a user does and asks the invariant at every landing,
    rather than naming the collisions one at a time. A rule stated once is a rule a new
    control inherits; a list of known collisions is a thing to keep adding to.

    Reduced motion, so a landing is a jump: what is asserted is where a walk ends, and
    the runtime reads the preference at load to decide between a glide and a jump."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    # A run per section and enough threads to make the list scroll, which is the whole
    # of what the cut half needs: a list that fits in the panel has no edge to fall off.
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})
        panel_comment(d, f"About the whole page, {i}.")

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread:not([hidden])").count()
    assert threads == 32, f"the fixture built {threads} threads, not the 32 it needs"
    assert page.evaluate(
        "() => { const l = document.querySelector('.lf-threads');"
        " return l.scrollHeight > l.clientHeight; }"
    ), "the list does not scroll, so nothing here can be cut by its edge"

    # The walk keys, not Tab: t/T opens a thread and lands its native summary.
    # Every landing on the way down and again on the way up, because
    # the two directions align opposite edges of the box with the scrollport and
    # only one of them was ever wrong at a time.
    # Standing nowhere, said rather than clicked for: `c` goes to the box belonging to
    # whatever the user is standing in, and a click on the body lands wherever the
    # middle of the document happens to be — which on this page is a diff, whose `pre`
    # takes focus. The press then opened that widget's composer and the walk below
    # typed its keys into the box, which is exactly what the non-vacuity check at the
    # end caught: thirty-two landings asserted, none of them on a thread.
    page.evaluate("() => document.activeElement?.blur()")
    # The named address toggles the panel it names, so from a panel opened by its
    # visible control the first completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    walked, faults = 0, []
    for key in ("t",) * threads + ("Shift+t",) * threads:
        page.keyboard.press(key)
        rendered(page)
        walked += 1
        mark_fault = thread_mark_fault(standing_thread(page))
        if mark_fault:
            faults.append(f"after {walked} presses, {mark_fault}")
        faults += ring_faults(rings_drawn(page), f"after {walked} presses of the walk")
        under = page.evaluate(COVERED_TOP)
        if under:
            faults.append(
                f"after {walked} presses, the thread landed past the list's "
                f"top edge: {under}"
            )
    assert not faults, "\n  ".join([f"{len(faults)} of {walked} landings:"] + faults)

    # Non-vacuity: the walk has to have been on a thread inside the scrolling list,
    # repainting its existing card, or the loop above asserted nothing at every step.
    standing = standing_thread(page)
    assert standing, "the walk ends outside a thread"
    assert standing["scrolled"], (
        "the walk ends outside a scroll region, so the cut half proved nothing"
    )

    # The list's own controls, which t and T never reach: Reply and Resolve inside a
    # card draw their rings outside themselves. They are what the room reserved at this list's edges is for — the
    # current thread's paint stays inside its card — so without this pass half of
    # that scroll-padding is unheld. Tab scrolls each stop into view itself,
    # which is the gesture that puts one against an edge.
    page.locator(".lf-threads").focus()
    # Chromium removes a closed details' contents from both the focus order and
    # checkVisibility, so this is the focus order the browser owns.
    tabbable = page.eval_on_selector_all(
        ".lf-threads *",
        "els => els.filter((e) => e.tabIndex >= 0 && e.checkVisibility()).length",
    )
    assert tabbable, "the list holds no control to tab to"
    stops = 0
    for _ in range(tabbable + 5):
        page.keyboard.press("Tab")
        rendered(page)
        if not page.evaluate(
            "() => document.querySelector('.lf-threads')"
            ".contains(document.activeElement)"
        ):
            break
        stops += 1
        faults += ring_faults(
            rings_drawn(page), f"tabbing to stop {stops} inside the list"
        )
    assert stops == tabbable, (
        f"the walk stood on {stops} of the list's {tabbable} controls, so the room "
        "it reserves at its edges is only partly held by this"
    )
    assert not faults, "\n  ".join([f"{len(faults)} faults:"] + faults)


def test_go_page_returns_without_unwinding_the_panel(browser, serve):
    """Leaving a panel beside the document to compare a comment is not backing out:
    the panel and its narrowing stay exactly as the user left them, while focus goes
    to the page. The address starts from the found comment after Enter leaves the find
    box, whose ordinary Escape still owns one rung of the panel stack."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})
    panel_comment(d, "The storage rule is settled.", {"section": "how-store"})

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    find = page.get_by_role("searchbox", name="Find in threads")
    find.focus()
    page.keyboard.type("capacity")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    page.keyboard.press("Enter")
    expect(
        page.locator(".lf-threads > .lf-thread:not([hidden]) > .lf-thread-summary")
    ).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("p")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "g p left the user in the panel"
    )
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(find).to_have_value("capacity")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)


def test_go_page_is_inert_while_the_panel_covers_the_page(browser, serve):
    """A covering panel locks the page scroller, so focus cannot honestly return to
    that page while keeping the panel open. Escape returns through the whole panel."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})

    context = browser.new_context(viewport={"width": 400, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    focus_panel_thread(thread)

    page.keyboard.press("g")
    page.keyboard.press("p")
    expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()


def test_the_address_sequence_places_a_focused_comment_at_either_list_edge(
    browser, serve
):
    """A focused thread is one addressable place with two useful placements. `g k`
    and `g j` move that card inside the panel without moving focus or the document,
    and the list's own scroll padding keeps the landing clear of its focus ring."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(32):
        panel_comment(d, f"Comment {i} about storage.", {"section": "how-store"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-threads")
    target = page.locator(".lf-threads > .lf-thread:not([hidden])").nth(16)
    assert box.evaluate("el => el.scrollHeight > el.clientHeight"), (
        "the list does not scroll, so its edges are not distinct places"
    )
    focus_panel_thread(target)

    before_page = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    expect(
        page.locator(
            ".lf-shortcut-bar .lf-shortcut:not([hidden])",
            has_text="thread top / bottom",
        )
    ).to_have_count(1)
    page.keyboard.press("k")
    top = page.evaluate(
        """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement.closest('.lf-thread');
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
              return {gap: card.top - view.top, clear};
            }"""
    )
    assert abs(top["gap"] - top["clear"]) < 2, (
        f"g k left the card {top['gap']:.1f}px from the list top; "
        f"the landable edge is {top['clear']:.1f}px"
    )
    expect(target.locator(":scope > .lf-thread-summary")).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("j")
    bottom = page.evaluate(
        """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement.closest('.lf-thread');
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingBottom) || 0;
              return {gap: view.bottom - card.bottom, clear};
            }"""
    )
    assert abs(bottom["gap"] - bottom["clear"]) < 2, (
        f"g j left the card {bottom['gap']:.1f}px from the list bottom; "
        f"the landable edge is {bottom['clear']:.1f}px"
    )
    expect(target.locator(":scope > .lf-thread-summary")).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_page


# What the burial below is aiming at: how far the first card stands past the list's top
# edge, the edge that depth has to match, and the box the press is aimed into.
# `COVERED_TOP` answers the covered question afterwards, about the focused card.
UNDER_EDGE = """() => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const top = list.getBoundingClientRect().top + list.clientTop;
  return {
    covered: top - card.getBoundingClientRect().top,
    edge: parseFloat(getComputedStyle(card).borderTopWidth),
    box: card.getBoundingClientRect().toJSON(),
  };
}"""

# Scroll by hand until the list's top edge cuts the card by `want`. Bounded, so a list
# that never scrolls its first card away fails the precondition rather than spinning.
BURY = """(want) => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const covered = () => list.getBoundingClientRect().top + list.clientTop
    - card.getBoundingClientRect().top;
  for (let i = 0; i < 400 && covered() < want; i++) list.scrollTop += 1;
}"""


def test_a_comment_the_pointer_lands_on_comes_back_from_the_lists_edge(browser, serve):
    """The walk above never sees this, and that is the point of having it twice: t/T
    scroll their landing into the band the list declares unlandable. A click scrolls
    nothing. The user nudges the list, its top edge cuts the first card, and takes the
    first strip of the surface that distinguishes the current card.

    So the gesture here is a real press rather than a locator click, which would scroll
    the card into view for its own actionability check and quietly perform the fix it is
    meant to test. What is asserted is the same question the walk asks — where the
    control can be seen, so can the current paint that names it — and, beside it, that
    the card actually came out, since paint reported whole while the card is still
    buried would mean the reading rather than the landing had moved."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()

    # Bury the card by exactly its reserved edge, which is the user's own case: a
    # list nudged a dozen pixels cuts its first card at the top edge. The
    # depth is one pixel rather than a comfortable number on purpose: it leaves the
    # rest of the card visible while hiding the first strip of its current ground.
    page.evaluate(BURY, page.evaluate(UNDER_EDGE)["edge"])
    rendered(page)
    buried = page.evaluate(UNDER_EDGE)
    assert buried["edge"] <= buried["covered"] <= buried["edge"] + 1, (
        f"the list's edge cuts {buried['covered']}px of the first card and its "
        f"edge is {buried['edge']}px: the setup wanted the edge buried and the rest "
        "of the card showing, and this is neither"
    )

    # Just inside the card's own corner. Its middle is prose today and one layout
    # away from being the reply box or a button, and a press that lands on a control
    # inside the card would fail this for a reason that is not its subject.
    box = buried["box"]
    page.mouse.click(box["x"] + 6, box["y"] + 80)
    rendered(page)
    assert page.evaluate(
        "() => Boolean(document.activeElement?.closest('.lf-thread'))"
    ), "the press did not land the user on a thread"
    mark_fault = thread_mark_fault(standing_thread(page), ring="none")
    assert not mark_fault, mark_fault
    assert not ring_faults(
        rings_drawn(page), "after a press on a card the list's edge cut"
    )
    # The panel's own reading of the same question, and the stronger form of it: a
    # hit test at the card's top edge rather than two rectangles subtracted, and it
    # declines outright if the press left the list.
    assert page.evaluate(COVERED_TOP) is None, (
        f"after the press the card is still past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )

    # The reply box receives the compact ring and the parent keeps its quiet current
    # ground. Reached by key this was never wrong, because landIn already lands the
    # thread around the box; a press into it went the way every other press did.
    page.evaluate(BURY, buried["edge"])
    rendered(page)
    under = page.evaluate(UNDER_EDGE)
    assert under["covered"] >= under["edge"], (
        f"the setup put the card back only {under['covered']}px under, which its "
        f"{under['edge']}px edge shows through"
    )
    reply = page.locator(".lf-threads > .lf-thread leaf-text").first
    reply_box = reply.bounding_box()
    page.mouse.click(
        reply_box["x"] + reply_box["width"] / 2,
        reply_box["y"] + reply_box["height"] / 2,
    )
    rendered(page)
    expect(reply).to_be_focused()
    assert page.evaluate(COVERED_TOP) is None, (
        "a press into the reply box left the current thread past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )


# The first closed title the list's top edge cuts, and how deep. The test above reads
# the list's first card, which it opens; a title is the box the edge cuts once every
# card but one is shut.
BURIED_TITLE = """() => {
  const list = document.querySelector('.lf-threads');
  const top = list.getBoundingClientRect().top + list.clientTop;
  for (const card of list.querySelectorAll('.lf-thread:not([open])')) {
    const title = card.querySelector('.lf-thread-summary').getBoundingClientRect();
    if (title.top < top && title.bottom > top)
      return {covered: top - title.top, box: title.toJSON(), id: card.dataset.id};
  }
  return null;
}"""


def test_a_press_that_opens_a_thread_lands_it_and_holds_it_at_once(browser, serve):
    """Two writers meet inside one press on a thread title. The press lands the thread
    back inside the list's top edge at `pointerup`, and the click that follows
    opens it, which reflows the list and brings its hold down on `scrollTop` a frame
    later. A `scrollTop` write cancels a smooth scroll rather than composing with it, so
    an animated landing is not superseded by what the gesture asks for next — it is
    dropped, and the user is left with neither: the title held exactly where the
    edge was cutting it. The landing under a press is therefore instant, which is
    also what lets the hold take its reference from where the landing put the title.

    Motion stays at its default here. The reduced-motion context the test above builds
    finishes the landing at `pointerup` and hides the collision, and that test presses a
    card's body, which opens nothing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    rendered(page)

    # Nudge until a closed title is cut a few pixels, the user's own case.
    buried = None
    for top in range(0, 400, 3):
        page.evaluate(
            "t => { document.querySelector('.lf-threads').scrollTop = t; }", top
        )
        rendered(page)
        buried = page.evaluate(BURIED_TITLE)
        if buried and 3 <= buried["covered"] <= 10:
            break
        buried = None
    assert buried, "no closed title ended up part-way past the list's top edge"

    box = buried["box"]
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.locator(f'.lf-thread[data-id="{buried["id"]}"][open]')).to_have_count(1)
    # Longer than any landing this could animate, so a cancelled smooth scroll reads as
    # a stationary title rather than one still on its way.
    page.wait_for_timeout(600)
    rendered(page)

    assert page.evaluate(COVERED_TOP) is None, (
        f"the press opened the thread but left its title past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )
    title = page.locator(f'.lf-thread[data-id="{buried["id"]}"] > .lf-thread-summary')
    after = title.evaluate("el => el.getBoundingClientRect().top")
    assert after >= box["y"], (
        f"the hold carried the pressed title up from {box['y']:.1f}px to {after:.1f}px "
        f"instead of holding it where the landing put it"
    )


def test_a_press_on_the_comment_the_user_is_already_in_brings_it_back(browser, serve):
    """The same gesture as the test above, from the state the user is actually in when
    they make it: standing in a comment, the list carried a little, the card's top run
    gone past the list's top edge. They press the card to bring it back — and a press on the
    thread that already holds the focus moves no focus at all, so a landing hung off the
    focus event hears nothing and the user presses at a card that will not come.

    Which is why the press asks where the gesture left the user rather than which
    thread the focus moved to. The keyboard half of this was already answered — `T` at
    the top of the walk lands the thread it is already on — and this is the same shape
    one scope out."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # Stand in the card first, then carry the list under it — which is the order the
    # user does it in, and the one where no later focus event is coming.
    first = page.locator(".lf-threads > .lf-thread:not([hidden])").first
    focus_panel_thread(first)
    rendered(page)
    page.evaluate(BURY, page.evaluate(UNDER_EDGE)["edge"])
    rendered(page)
    under = page.evaluate(UNDER_EDGE)
    assert under["covered"] >= under["edge"], (
        f"the list carried only {under['covered']}px past the list's top edge, which the "
        f"{under['edge']}px edge shows through — nothing here is cut yet"
    )
    assert page.evaluate(
        "() => Boolean(document.activeElement?.closest('.lf-thread'))"
    ), "the user is not standing in the card, so the press below moves focus"

    box = under["box"]
    page.mouse.click(box["x"] + 6, box["y"] + 80)
    rendered(page)
    assert page.evaluate(COVERED_TOP) is None, (
        "a press on the card the user was already standing in left it past the "
        f"list's top edge: {page.evaluate(COVERED_TOP)}"
    )
    assert not ring_faults(
        rings_drawn(page), "after a press on the card already standing in"
    )


def test_a_cancelled_panel_press_does_not_suppress_the_next_focus_landing(
    browser, serve
):
    """A touch scroll begins as a press and ends in ``pointercancel`` when the browser
    takes the gesture. Cancellation must not undo the scroll by landing the card, but it
    must end the provisional press: the next independent focus arrival still brings its
    thread back inside the list's top edge.

    Dispatch the pointer events directly so the browser does not add a mouse click or a
    default focus after the cancellation. An unrelated pointer first proves which gesture
    owns the hold; the matching cancellation and the focus after it then distinguish
    release-without-landing from both a stale hold and an ordinary pointer-up landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    first = page.locator(".lf-threads > .lf-thread:not([hidden])").first
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    page.evaluate(BURY, 20)
    rendered(page)
    before = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    assert page.evaluate(UNDER_EDGE)["covered"] >= 20, (
        "the setup did not put the first card past the list's top edge"
    )

    page.evaluate(
        """() => {
              const card = document.querySelector('.lf-threads > .lf-thread');
              card.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, isPrimary: true, pointerId: 7,
              }));
              dispatchEvent(new PointerEvent('pointercancel', {
                isPrimary: false, pointerId: 8,
              }));
            }"""
    )
    page.locator(".lf-threads").evaluate("el => el.focus({preventScroll: true})")
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    assert page.evaluate(COVERED_TOP) is not None, (
        "an unrelated pointer cancellation released the active panel gesture"
    )

    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointercancel', {
              isPrimary: true, pointerId: 7,
            }))"""
    )
    assert (
        page.evaluate("() => document.querySelector('.lf-threads').scrollTop") == before
    ), "cancelling a touch-scroll gesture landed the thread and undid the scroll"

    page.locator(".lf-threads").evaluate("el => el.focus({preventScroll: true})")
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    assert page.evaluate(COVERED_TOP) is None, (
        "the cancelled press suppressed the next focus landing and left the card "
        f"past the list's top edge: {page.evaluate(COVERED_TOP)}"
    )


def test_a_drag_across_a_quote_takes_its_words_and_not_its_passage(browser, serve):
    """The panel's quote is words and a press at once — it says which passage the comment
    is about, and pressing it travels the page there. So a user who drags across it to
    take the words gets the travel as well, and the page they were reading goes.

    `offer` has answered this for its own controls since a suggestion's Accept went dead
    under a selection that ran over it, and the answer is the same one: the selection's
    focus end is the character the button came up on, so a press that ended in these
    words was reaching for them. What is new is that the reading is now the reading and
    not that listener's own business, because the same gesture reaches two more things —
    a quote, which `offer` never made, and the list's own landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()
    page.evaluate("() => { document.querySelector('.lf-threads').scrollTop = 0; }")
    # Keep the quoted passage outside the page's readable viewport. This test is the
    # drag/plain-press contrast: a readable destination deliberately stays put now,
    # so only an offscreen passage can prove the plain press still travels.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    rendered(page)
    destination = page.evaluate(
        """() => {
              const target = document.querySelector('#merge-both').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              return {top: target.top, bottom: target.bottom,
                      banner: banner.bottom, height: innerHeight};
            }"""
    )
    assert (
        destination["bottom"] <= destination["banner"]
        or destination["top"] >= destination["height"]
    ), (
        f"the quoted passage is still readable, so a click need not travel: {destination}"
    )

    where = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(where)
    quote = page.locator(".lf-threads > .lf-thread .lf-quote").first
    span = quote.bounding_box()
    page.mouse.move(span["x"] + 4, span["y"] + 6)
    page.mouse.down()
    page.mouse.move(span["x"] + span["width"] - 6, span["y"] + 6, steps=8)
    page.mouse.up()
    page_at_rest(page)

    drawn = page.evaluate("() => getSelection().toString()")
    assert len(drawn) > 8, (
        f"the drag took {drawn!r} of the quote, so this asserts nothing about one"
    )
    after = page.evaluate(where)
    assert after == before, (
        f"the page travelled from {before} to {after} while the user was taking "
        "the quote's words, so what they were reading went with it"
    )

    # The press itself still travels: what stood down is the drag, not the control.
    # The words go first, because a press inside a standing selection is where the
    # platform holds it for a drag of its own — the user's next press is a press,
    # not the tail of the one before it.
    page.evaluate("() => getSelection().removeAllRanges()")
    quote.click()
    page_at_rest(page)
    assert page.evaluate(where) != before, (
        "a plain press on the quote no longer travels to its passage, so this took "
        "the control away rather than the drag"
    )


def test_a_drag_across_a_comments_words_leaves_the_list_where_it_was_read(
    browser, serve
):
    """The other half of landing a press, and the reason it waits for the press to end.
    Focus arrives on the way down, so a landing taken there scrolls the words out from
    under a pointer that is still selecting them — and the selection runs on to wherever
    they went, which measured about three times what the user had drawn.

    So the gesture is a real drag across a card near the top of the list, where any
    landing at all would move it, and the two things asserted are what the user has
    afterwards: the list where they were reading, and the words they actually dragged
    over. `offer` asks the same question of a click and reads the answer the same way —
    the selection's focus end is the character the button came up on."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()

    # Far enough past the list's top edge that a landing would be a visible jump, so the
    # drag below is asserting the absence of something this list would otherwise do.
    page.evaluate(BURY, 20)
    rendered(page)
    before = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    # The message's own words, not the quote above them: a quote is a control that
    # jumps to the passage, so a drag ending on one has a second reason to scroll and
    # this would not be able to say which had moved the list.
    words = page.locator(".lf-threads > .lf-thread .lf-msg-body").first
    span = words.bounding_box()
    page.mouse.move(span["x"] + 4, span["y"] + span["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        span["x"] + span["width"] - 4, span["y"] + span["height"] / 2, steps=8
    )
    page.mouse.up()
    rendered(page)

    after = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    assert after == before, (
        f"the list moved from {before} to {after} under a drag, so the words the "
        "user was selecting went with it"
    )
    drawn = page.evaluate("() => getSelection().toString()")
    assert len(drawn) > 4, (
        f"the drag selected {drawn!r}, so this asserts nothing about a selection"
    )


def test_the_line_offers_the_list_its_own_keys_rather_than_the_way_deeper_in(
    browser, serve
):
    """The two contextual chips the line paints for a user standing on the list have
    to be its exact way back and its first local action: the line is two chips and the
    More control, so an unrelated row in front of these is a row instead of them.

    `g T` brought them here, so its return frame leads and `w` is the first local action.
    The general box is where the typing scope claims every letter, which is the whole
    reason the press stops at the list. Inside a thread `THREAD` is nearer, inside a box
    `TYPING` claims the letters, and outside the panel this scope is not standing. So an
    unrelated row in front of them here spends the slot the landing exists to fill.

    Read off `:not([hidden])`, because `renderShortcutBar` leaves every live row in the DOM and
    hides the ones outside the shortlist. `to_contain_text` on the line therefore
    answers about the register rather than about the user, and passes just as well
    when the chip is one nobody can see — which is why the rest of the panel's tests
    could not have caught this.

    The second press keeps a surface of its own: the box says the key in its own
    placeholder, which the last phase reads."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(3):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which way round should this go?",
            "anchor": {"section": "how-store"},
        },
    )

    page = open_page(browser, url)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    shown = page.locator(".lf-shortcut-bar .lf-shortcut:not([hidden])")
    expect(shown).to_have_count(2)
    # The list's own first key leads and the way out of the surface follows it, which is
    # what the line is for: the user can see the panel around them, and what they came
    # here to do is the press worth naming first.
    expect(shown.nth(0)).to_contain_text("waiting on you")
    expect(shown.nth(1)).to_contain_text("close threads")

    # And the press it displaced still works, from the placeholder that advertises it.
    # The badge inside the painted placeholder is where the box states that key, and
    # it stands only while the box is hinted and empty, so reading it holds what the
    # user can see rather than how the hint's two parts happen to be joined.
    advertised = page.locator(".lf-general .lf-compose-placeholder kbd")
    expect(advertised).to_be_visible()
    expect(advertised).to_have_text("c")
    page.keyboard.press("c")
    expect(page.locator(".lf-general leaf-text")).to_be_focused()


def test_a_narrowing_hides_a_thread_without_taking_its_question_off_the_page(
    browser, serve
):
    """The banner's Asks count and the tray read the log; the panel's narrowing is a view.

    A question an agent asks in a reply is a widget instantiated once, in the panel's
    card, and every other reading of it finds that widget by id in the document. So
    when "Waiting on you" took the answered thread's card out of the list, it took the
    question out of the page: Asks 2/2 became 1/1, the tray listed one ask, and a
    minute later — the narrowing let go — both came back, with nothing in the log
    having moved. A blind drive spent a locator timeout on the flip.

    The card the narrowing hides is hidden, not gone, so the count and the tray hold."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread:not([hidden]) .lf-thread-summary").first.click()
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    question.locator("lf-option:not([chosen]) > .lf-pick").first.click()
    round_trip(page)
    question.locator(".lf-done").click()
    round_trip(page)
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/2")
    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 2 open threads · On you"
    )
    expect(
        page.locator('.lf-threads > .lf-thread[hidden][data-resolved="false"]')
    ).to_have_count(1)
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/2")
    banner_control(page, ".lf-asks").click()
    expect(page.locator(".lf-asks-row")).to_have_count(2)


def test_a_narrowing_that_hides_the_card_the_user_stands_in_lands_them_on_the_list(
    browser, serve
):
    """A hidden card is a removal to the user standing in it.

    The narrowing keeps the card, hidden, and the browser drops a focus inside a hidden
    element to body only at its next rendering step, after the reconcile has run. Read
    as still in the list, the user was left to that drop, and the next Space went to
    the page behind the panel. The disarm test in `test_render_reactions.py` covers a
    reaction list moving the focus itself; this is the plain case, with nothing in the
    card but the reply box the user is typing in."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    theirs = panel_comment(d, "Is forty enough?", {"section": "how-cap"}, "agent")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    card = page.locator(f'.lf-thread[data-id="{theirs}"]')
    card.locator(".lf-thread-summary").click()
    card.locator("leaf-text").click()
    expect(card.locator("leaf-text")).to_be_focused()
    # A remote reaction answers the question, so the narrowing no longer shows the card.
    events_model.append_event(
        d, {"kind": "reply", "author": "user", "parent": theirs, "token": "keep"}
    )
    told(page)
    expect(card).to_be_hidden()
    expect(page.locator(".lf-threads")).to_be_focused()


def test_a_growing_panel_reply_keeps_the_previous_turn_visible(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "A question with a reply.")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "The last answer remains useful while composing a response.",
        },
    )
    page = open_page(browser, url)
    resized(page, 800, 520)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(".lf-thread-summary").click()
    reply = card.locator("leaf-text")
    write(reply, "A reply that grows.\n" * 30)
    latest = card.locator(".lf-msg.agent").last
    visible = latest.evaluate(
        """message => {
          const list = document.querySelector('.lf-threads');
          const band = list.getBoundingClientRect();
          const style = getComputedStyle(list);
          return {
            tail: message.getBoundingClientRect().bottom,
            top: band.top + parseFloat(style.scrollPaddingTop),
            editor: list.querySelector('.lf-thread[open] leaf-text').getBoundingClientRect().top,
          };
        }"""
    )
    assert visible["tail"] >= visible["top"] + 20, visible
    assert visible["tail"] < visible["editor"], visible
    assert reply.evaluate("input => input.scrollTop > 0")
    in_threads_scrollport(page, f'.lf-thread[data-id="{root}"] .lf-thread-send')


LANDING_WORDS = (
    "This message has enough words in it to wrap over several lines in the panel, "
    "so that a thread of a dozen of them is taller than the list's scrollport. "
)


def seed_panel_threads(page_dir, threads, long_index=None, messages=12):
    """`threads` panel threads of two turns each, the one at `long_index` with
    `messages` turns, so it stands taller than the list's scrollport."""
    roots = []
    for i in range(threads):
        root = panel_comment(page_dir, f"Thread {i} opening. " + LANDING_WORDS)
        roots.append(root)
        for turn in range(1, messages if i == long_index else 2):
            agent = turn % 2 == 1
            events_model.append_event(
                page_dir,
                {
                    "kind": "reply",
                    "author": "agent" if agent else "user",
                    **({"agent": "Codex"} if agent else {}),
                    "parent": root,
                    "text": f"Turn {turn} of thread {i}. " + LANDING_WORDS,
                },
            )
    return roots


def open_threads_list(page, width, height):
    resized(page, width, height)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)


def test_a_bounded_log_in_an_agent_reply_follows_its_end_as_a_reading_region(
    browser, serve
):
    """A reply's markup is painted where the thread draws it, not by the page's install,
    so a log bounded at its end in a reply was neither held at its end nor the box
    scrolling its lines until some later revision swept the page."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "What did the deploy do?")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "revision": 1,
            "text": "Here is its log.",
            "markup": '<div data-bound="end">'
            + "".join(
                f"<p>Line {n}: the deploy copied shard {n} to the new key format.</p>"
                for n in range(60)
            )
            + "</div>",
        },
    )
    page = open_page(browser, url)
    open_threads_list(page, 1400, 900)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(":scope > .lf-thread-summary").click()
    log = card.locator(".lf-msg-body [data-lf-bound]")
    expect(log).to_be_visible()
    rendered(page)
    held = log.evaluate(
        """async log => {
          const { scrollerFor } = await window.__lfRuntimeImport(
            '/runtime/reading-regions.js');
          return {
            scroller: scrollerFor(log.querySelector('p')) === log,
            atEnd: log.scrollHeight > log.clientHeight
              && log.scrollHeight - log.scrollTop - log.clientHeight <= 2,
          };
        }"""
    )
    assert held == {"scroller": True, "atEnd": True}, held


def reply_by_keyboard(page, root):
    """Stand on the thread's title and press `c` into its reply box."""
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    title = card.locator(":scope > .lf-thread-summary")
    if card.get_attribute("open") is None:
        title.click()
    title.focus()
    rendered(page)
    title.press("c")
    expect(card.locator("leaf-text")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    return card


# Where a node stands against the list's landing band: its scrollport less the
# scroll padding the focus ring takes.
IN_LANDING_BAND = """node => {
  const list = document.querySelector('.lf-threads');
  const shown = list.getBoundingClientRect();
  const style = getComputedStyle(list);
  const band = [shown.top + parseFloat(style.scrollPaddingTop),
                shown.bottom - parseFloat(style.scrollPaddingBottom)];
  const box = node.getBoundingClientRect();
  return {inside: box.top >= band[0] - 1 && box.bottom <= band[1] + 1,
          box: [Math.round(box.top), Math.round(box.bottom)],
          band: band.map(Math.round)};
}"""


@pytest.mark.parametrize("size", [(1200, 900), (800, 520)])
def test_an_agent_turn_arriving_while_the_user_writes_keeps_their_box_in_view(
    browser, serve, size
):
    """The list's place hold keeps the card's top still, so a turn arriving at the
    thread's end pushed the reply box, and the Send beside it, below the list's foot
    while the user was typing in it. Following lands the thread's end instead."""
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 4, long_index=2)[2]
    page = open_page(browser, url)
    open_threads_list(page, *size)
    card = reply_by_keyboard(page, root)
    page.keyboard.type("Half a thought I am still typing")
    rendered(page)
    send = card.locator(".lf-thread-send")
    assert send.evaluate(IN_LANDING_BAND)["inside"], "Send starts outside the band"
    arrived = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "An agent answer arrives. " + LANDING_WORDS,
        },
    )
    told(page)
    expect(card.locator(".lf-msg")).to_have_count(13)
    rendered(page)
    scroll_settled(page, ".lf-threads")
    assert card.locator(f'.lf-msg[data-mid="{arrived["id"]}"]').evaluate(
        IN_LANDING_BAND
    )["inside"]
    expect(card.locator("leaf-text")).to_be_focused()
    held = send.evaluate(IN_LANDING_BAND)
    assert held["inside"], f"the arrival pushed Send out of the list's band: {held}"


@pytest.mark.parametrize("size", [(1200, 900), (800, 520)])
def test_a_thread_sent_from_the_panels_foot_lands_in_view(browser, serve, size):
    """The list's place hold finishing a render cancelled the smooth landing already
    under way, leaving the new thread below the list's foot."""
    url = serve(PANEL_PAGE)
    seed_panel_threads(serve.page_dir, 8 if size[1] < 600 else 20, long_index=0)
    page = open_page(browser, url)
    open_threads_list(page, *size)
    page.locator(".lf-threads").evaluate("list => list.scrollTop = list.scrollHeight")
    scroll_settled(page, ".lf-threads")
    write(page.locator(".lf-general leaf-text"), "What the general box says.")
    with sending(page, "the page comment"):
        page.keyboard.press("Enter")
    rendered(page)
    scroll_settled(page, ".lf-threads")
    sent = events_model.read_events(serve.page_dir)[-1]
    card = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    landed = card.locator(":scope > .lf-thread-summary").evaluate(IN_LANDING_BAND)
    assert landed["inside"], f"the new thread was left outside the band: {landed}"
    assert page.evaluate(
        "() => Boolean(document.activeElement.closest('.lf-general'))"
    ), "the send moved focus out of the general box"


@pytest.mark.parametrize("how", ["r", "button"])
def test_resolving_a_long_thread_lands_the_next_title_in_view(browser, serve, how):
    """The landing of the thread focus moved on to was measured while the resolved
    thread still stood open above it, and the fold then took that room away under a
    smooth scroll: the next title ended above the list."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    open_threads_list(page, 800, 520)
    card = page.locator(f'.lf-thread[data-id="{roots[3]}"]')
    title = card.locator(":scope > .lf-thread-summary")
    title.click()
    rendered(page)
    title.focus()
    with sending(page, "the resolve"):
        if how == "r":
            page.keyboard.press("r")
        else:
            card.locator(".lf-resolve").click()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    following = page.locator(f'.lf-thread[data-id="{roots[4]}"] > .lf-thread-summary')
    expect(following).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    landed = following.evaluate(IN_LANDING_BAND)
    assert landed["inside"], f"focus landed outside the list's band: {landed}"


def test_escape_then_enter_round_trips_a_panel_reply(browser, serve):
    """Escape hands a reply back to its thread's title, and Enter there puts the user
    back in the box. The row answering Enter asked for a focused card root, which a
    panel thread's title is not, so the round trip stopped at the title."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 3)
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, roots[1])
    page.keyboard.type("draft")
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("Enter")
    expect(card.locator("leaf-text")).to_be_focused()
    expect(card.locator("leaf-text")).to_have_js_property("value", "draft")


def test_leaving_a_long_threads_reply_keeps_the_list_where_it_was(browser, serve):
    """Escape out of the reply of a thread taller than the list focuses its title
    without landing it: the landing took the list to the thread's head, away from the
    turn the user was answering."""
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 4, long_index=2)[2]
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, root)
    before = page.locator(".lf-threads").evaluate("list => list.scrollTop")
    assert before > 0, "the reply landed without scrolling, so this proves nothing"
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    assert page.locator(".lf-threads").evaluate("list => list.scrollTop") == before
    assert card.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)["inside"]


def test_walking_down_the_list_shows_each_thread_under_its_title(browser, serve):
    """`t` opens the next thread and lands its title. Where the opened thread is taller
    than the list, the nearest edge put the title at the list's foot with none of the
    thread under it, on every step down the walk."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    open_threads_list(page, 800, 520)
    page.locator(".lf-threads").focus()
    landings = []
    for root in roots[:6]:
        page.keyboard.press("t")
        title = page.locator(f'.lf-thread[data-id="{root}"] > .lf-thread-summary')
        expect(title).to_be_focused()
        rendered(page)
        scroll_settled(page, ".lf-threads")
        landings.append(title.evaluate(IN_LANDING_BAND))
    assert all(landed["inside"] for landed in landings), landings
    assert all(landed["band"][1] - landed["box"][1] > 100 for landed in landings), (
        f"a title landed at the list's foot with its thread below it: {landings}"
    )


SEAT_FILLER = "".join(
    f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
    for n in range(40)
)
SEAT_WORDS = (
    "This is a longer message that wraps onto a second line at a normal reading "
    "width, so a thread of a dozen of them is taller than a short window."
)
SEAT_DIFF = (
    "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
    '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
)
THIRTY_LINES = "\n".join(f"Pasted line {n}" for n in range(30))


def bounded_seat_page(steps, bound):
    """A talk seat at the foot of a command that bounds its own height with
    `data-bound`, after `steps` plain tasks, between screens of filler."""
    tasks = "".join(
        f'<lf-task id="step-{n}" status="planned"><strong>Step {n}</strong> '
        f"{SEAT_WORDS}</lf-task>"
        for n in range(steps)
    )
    return leaf_page(
        "bounded seat",
        f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-command id="hub" '
        f'label="Before the frost" data-bound="{bound}">{tasks}<lf-task id="jobs" '
        'status="active" talk><strong>Which jobs are worth starting?</strong> The '
        f"mounts came down in January.</lf-task></lf-command>{SEAT_FILLER}",
    )


def seated_page(serve, kind):
    """A page whose seat sits past a screen of filler with more below it, and the
    selector of the widget holding it: `task` keeps its box after a send to offer
    Send & pause, `verdict` gives it up to the thread it starts. `bounded` is a task
    in a command that bounds its height and scrolls, `bounded-short` one in a block
    whose bound its contents do not yet fill."""
    if kind == "bounded":
        return serve(bounded_seat_page(6, "end")), "#jobs"
    if kind == "bounded-short":
        return serve(
            leaf_page(
                "bounded seat",
                f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-command id="hub" '
                'label="Before the frost"><lf-task id="jobs" status="active" talk '
                'data-bound="start"><strong>Which jobs are worth starting?</strong>'
                f"</lf-task></lf-command>{SEAT_FILLER}",
            )
        ), "#jobs"
    if kind == "task":
        return serve(
            leaf_page(
                "seat",
                f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-command id="hub" '
                'label="Before the frost"><lf-task id="jobs" status="active" talk>'
                "<strong>Which jobs are worth starting?</strong> The mounts came "
                f"down in January.</lf-task></lf-command>{SEAT_FILLER}",
            )
        ), "#jobs"
    return serve(
        leaf_page(
            "seat",
            f'<h1>Review the plan</h1>{SEAT_FILLER}<lf-verdict id="proposal" asks>'
            f"Should these jobs share a visit?</lf-verdict>{SEAT_FILLER}",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
    ), "#proposal"


def seated_thread(serve, kind, messages):
    """A thread of `messages` turns on a page seat (`task`, `verdict`) or on a diff
    line (`diff`, drawn inside the widget's shadow tree), and the page's URL."""
    if kind == "diff":
        url = serve(
            leaf_page(
                "diff",
                f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
                f'source="review-patch"><pre></pre></lf-diff>{SEAT_FILLER}',
            )
        )
        data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
        anchor = {
            "section": "patch",
            "datum": '["app.py","new",1]',
            "source": "review-patch",
            "source_revision": source_revision(serve.page_dir, "review-patch"),
        }
    else:
        url, host = seated_page(serve, kind)
        anchor = {"section": host[1:]}
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Opening remark. " + SEAT_WORDS,
            "anchor": anchor,
        },
    )["id"]
    for n in range(messages - 1):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if n % 2 == 0 else "user",
                "agent": "Codex",
                "parent": root,
                "revision": 1,
                "text": f"Message {n + 2}. " + SEAT_WORDS,
            },
        )
    return url, root


def paste(page, text):
    """Paste `text` into the focused box through the clipboard, as a user's paste
    arrives: one edit, which CodeMirror scrolls its caret into view for."""
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("text => navigator.clipboard.writeText(text)", text)
    page.keyboard.press("ControlOrMeta+v")
    rendered(page)


def to_window_foot(page, locator, gap):
    """Scroll the page so `locator`'s foot stands `gap` px above the window's."""
    page.evaluate(
        """([node, gap]) => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().bottom - (innerHeight - gap),
          behavior: 'instant'})""",
        [locator.element_handle(), gap],
    )
    scroll_settled(page)


def clear_of_the_bar(page, locator):
    """Whether the node is wholly in the window above the fixed shortcut bar."""
    return page.evaluate(
        """([node, bar]) => {
          const box = node.getBoundingClientRect();
          const foot = bar ? bar.getBoundingClientRect().top : innerHeight;
          return box.height > 0 && box.top >= 0 && box.bottom <= foot + 0.5;
        }""",
        [locator.element_handle(), page.locator(".lf-shortcut-bar").element_handle()],
    )


def focus_clear_of_the_bar(page):
    """Whether the focused node, through open shadow roots, shows in the window."""
    return page.evaluate(
        """() => {
          let node = document.activeElement;
          while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
          const box = node.getBoundingClientRect();
          const bar = document.querySelector('.lf-shortcut-bar');
          const foot = bar ? bar.getBoundingClientRect().top : innerHeight;
          return box.height > 0 && box.bottom > 0 && box.top < foot;
        }"""
    )


def pressed_send_surface(browser, serve, surface):
    """A page with words typed into `surface`'s box, and that box, the control that
    submits it, and the box the user continues in once it has sent."""
    if surface in {"pause", "handoff"}:
        url, host = seated_page(serve, "task" if surface == "pause" else "verdict")
        page = open_page(browser, url)
        seat = page.locator(f"{host} > .lf-thread-seat")
        box = seat.locator(":scope > .lf-say leaf-text")
        box.scroll_into_view_if_needed()
        name = "Send & pause" if surface == "pause" else "Send"
        send = seat.get_by_role("button", name=name, exact=True)
        after = (
            box
            if surface == "pause"
            else seat.locator(":scope > .lf-page-thread > .lf-say leaf-text")
        )
    else:
        url = serve(PANEL_PAGE)
        root = panel_comment(
            serve.page_dir,
            "Where should this explanation go?",
            {"section": "how-store"},
        )
        page = open_page(browser, url)
        if surface == "card":
            page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
            holder = page.locator(".lf-margin-preview")
            box = holder.locator(".lf-say leaf-text")
        elif surface == "composer":
            page.locator("#how-cap").click(click_count=3)
            page.locator(".lf-fab-input").click()
            holder = page.locator(".lf-composer")
            box = holder.locator("leaf-text")
        else:
            page.locator(".lf-threads-toggle").click()
            panel_settled(page)
            if surface == "panel":
                holder = page.locator(f'.lf-thread[data-id="{root}"]')
                holder.locator(".lf-thread-summary").click()
                box = holder.locator(":scope > .lf-compose leaf-text")
            else:
                holder = page.locator(".lf-general")
                box = holder.locator("leaf-text")
        send = holder.locator(".lf-compose-submit")
        # A first anchored comment lands the user on the thread it starts, as Enter
        # does (#961); every other box keeps them.
        after = (
            page.locator(".lf-margin-preview .lf-page-thread")
            if surface == "composer"
            else box
        )
    write(box, "Sent from the box.")
    rendered(page)
    return page, box, send, after


@pytest.mark.parametrize(
    ("surface", "how"),
    [
        (surface, how)
        for surface in ["card", "panel", "general", "pause", "handoff", "composer"]
        for how in ["pointer", "keyboard"]
        # The anchored composer's Tab walks its field and response options
        # (`response.tab`), so its Send takes no keyboard press; Enter is that route.
        if (surface, how) != ("composer", "keyboard")
    ],
)
def test_a_pressed_send_leaves_the_user_in_the_box(browser, serve, surface, how):
    """Pressing a box's submit control is its send key pressed from the box: the user
    goes on typing where Enter would leave them. A pointer press left the focus on the
    button, so the `o` and `k` of an "ok" typed next hid every mark and closed the
    margin card, and neither letter reached the box. A keyboard press on the button
    ends in the box too, so after any send the user is in it — or, where the seat gives
    its box up, in the reply of the thread it started, as after Enter. The anchored
    composer hands the user to the thread its comment starts, as Enter does there."""
    page, box, send, after = pressed_send_surface(browser, serve, surface)
    if how == "keyboard":
        # Tab reaches the control from the box; `Send & pause` stands one past `Send`.
        for _ in range(2 if surface == "pause" else 1):
            page.keyboard.press("Tab")
        expect(send).to_be_focused()
        with sending(page, "the keyboard-pressed send"):
            page.keyboard.press("Space")
    else:
        send.scroll_into_view_if_needed()
        at = send.bounding_box()
        page.mouse.move(at["x"] + at["width"] / 2, at["y"] + at["height"] / 2)
        with sending(page, "the pointer-pressed send"):
            page.mouse.down()
            # The press never takes the focus, so the box never hears it leave.
            expect(box).to_be_focused()
            page.mouse.up()
    rendered(page)
    expect(after).to_be_focused()
    if surface != "composer":
        page.keyboard.type("ok")
        expect(after).to_have_js_property("value", "ok")
    expect(after).to_be_visible()
    expect(page.locator("html")).not_to_have_attribute("data-lf-annotations", "hidden")
    sent = events_model.read_events(serve.page_dir)
    assert any(event.get("text") == "Sent from the box." for event in sent), sent


def test_a_pointer_send_finishes_the_words_an_input_method_holds(browser, serve):
    """A press on Send while an input method holds unfinished words takes the focus, as
    leaving the box is what finishes them: the send carries the finished words, and the
    box it empties stays empty. Held in the box, the words went out unfinished and the
    input method's commit afterwards wrote them back into the emptied box."""
    page, box, send, after = pressed_send_surface(browser, serve, "general")
    ended = box.evaluate_handle(
        """box => {
          const ended = {count: 0};
          box.addEventListener('compositionend', () => (ended.count += 1));
          return ended;
        }"""
    )
    ime = page.context.new_cdp_session(page)
    ime.send(
        "Input.imeSetComposition",
        {"text": "にほ", "selectionStart": 2, "selectionEnd": 2},
    )
    expect(box).to_have_js_property("value", "Sent from the box.にほ")
    at = send.bounding_box()
    page.mouse.move(at["x"] + at["width"] / 2, at["y"] + at["height"] / 2)
    with sending(page, "the send pressed mid-composition"):
        page.mouse.down()
        page.mouse.up()
    rendered(page)
    assert ended.evaluate("ended => ended.count") == 1
    expect(after).to_be_focused()
    expect(after).to_have_js_property("value", "")
    sent = events_model.read_events(serve.page_dir)
    assert any(event.get("text") == "Sent from the box.にほ" for event in sent), sent


def test_a_seat_send_puts_the_user_in_the_thread_it_started(browser, serve):
    """A seat that gives its box up to the thread its first message starts took the
    focus with it, so the next keys the user typed ran page commands."""
    url, host = seated_page(serve, "verdict")
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First thought.")
    with sending(page, "the first message"):
        page.keyboard.press("Enter")
    thread = page.locator(f"{host} > .lf-thread-seat > .lf-page-thread")
    expect(thread).to_have_count(1)
    expect(thread.locator(":scope > .lf-say leaf-text")).to_be_focused()


@pytest.mark.parametrize("kind", ["task", "verdict"])
def test_a_seat_send_at_the_window_foot_shows_the_thread_it_started(
    browser, serve, kind
):
    url, host = seated_page(serve, kind)
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First thought.")
    to_window_foot(page, box, 60)
    with sending(page, "the first message"):
        page.keyboard.press("Enter")
    rendered(page)
    scroll_settled(page)
    sent = page.locator(f"{host} .lf-page-thread .lf-page-thread-msg").last
    expect(sent).to_contain_text("First thought.")
    assert clear_of_the_bar(page, sent), "the sent message was left below the fold"
    focused = page.locator(f"{host} leaf-text:focus")
    expect(focused).to_have_count(1)
    assert clear_of_the_bar(page, focused), "the box the user is in went below the fold"


def shown_in(page, node, scroller):
    """Whether `node` shows whole inside `scroller`'s box and inside the window above
    the shortcut bar."""
    return page.evaluate(
        """([node, box, bar]) => {
          const at = node.getBoundingClientRect();
          const holder = box.getBoundingClientRect();
          const foot = bar ? bar.getBoundingClientRect().top : innerHeight;
          return at.height > 0 && at.top >= holder.top - 0.5
            && at.bottom <= holder.bottom + 0.5 && at.top >= 0 && at.bottom <= foot + 0.5;
        }""",
        [
            node.element_handle(),
            scroller.element_handle(),
            page.locator(".lf-shortcut-bar").element_handle(),
        ],
    )


@pytest.mark.parametrize("bound", ["end", "start"])
def test_a_seat_send_in_a_bounded_block_moves_the_block_and_not_the_page(
    browser, serve, bound
):
    """A block that bounds its own height scrolls a seat inside it, so each send
    landed its thread by scrolling the page too, and the block went out of the window
    after two sends. The block is the reading region the seat stands in."""
    page = open_page(browser, serve(bounded_seat_page(6, bound)))
    resized(page, 1280, 700)
    hub = page.locator("#hub")
    assert hub.evaluate("hub => hub.scrollHeight > hub.clientHeight + 100")
    # The block stands in the middle of the window, its seat scrolled into its view.
    page.evaluate(
        """hub => { const at = hub.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        hub.element_handle(),
    )
    hub.evaluate("hub => hub.scrollTop = hub.scrollHeight")
    scroll_settled(page)
    box = page.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    for n, words in enumerate(["First thought.", "Second thought."]):
        write(box, words)
        before = page.evaluate("() => document.scrollingElement.scrollTop")
        with sending(page, f"message {n + 1}"):
            page.keyboard.press("Enter")
        sent = page.locator("#jobs .lf-page-thread .lf-page-thread-msg").last
        expect(sent).to_contain_text(words)
        rendered(page)
        scroll_settled(page)
        scroll_settled(page, "#hub")
        after = page.evaluate("() => document.scrollingElement.scrollTop")
        assert after == pytest.approx(before, abs=1), (
            f"send {n + 1} moved the page {after - before}px"
        )
        assert shown_in(page, sent, hub), f"send {n + 1} left its turn out of view"
        focused = page.locator("#jobs leaf-text:focus")
        expect(focused).to_have_count(1)
        assert shown_in(page, focused, hub), f"send {n + 1} left the box out of view"


def test_a_seat_box_grown_by_a_paste_keeps_its_send_above_the_bar(browser, serve):
    """The growth reveal lived in the reply wiring alone, so a seat's own box grew
    under the shortcut bar, CodeMirror's caret scrolling knowing nothing of it."""
    url, host = seated_page(serve, "verdict")
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    send = page.locator(f"{host} > .lf-thread-seat > .lf-say .lf-compose-submit")
    assert clear_of_the_bar(page, send)


def test_a_diff_thread_reply_grown_by_a_paste_keeps_its_send_above_the_bar(
    browser, serve
):
    """A diff draws its threads in its own shadow tree. The landing's climb stopped at
    that root, never met the page's scroller, and read a thread taller than the window
    as one that fits, so the growth reveal moved nothing."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    assert clear_of_the_bar(page, thread.locator(":scope > .lf-say .lf-compose-submit"))


@pytest.mark.parametrize("kind", ["task", "diff", "bounded", "bounded-short"])
def test_an_agent_turn_arriving_holds_still_the_page_box_being_typed_in(
    browser, serve, kind
):
    """The new turn went in above the reply box the user was typing in and pushed it,
    caret and all, below the fold. News moves no control under the user's hands.
    A short bounded block grows in the page rather than scrolling, so the page takes
    the move there."""
    messages = 1 if kind == "bounded-short" else 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    to_window_foot(page, box, 50)
    before = box.evaluate("box => box.getBoundingClientRect().top")
    page_before = page.evaluate("() => document.scrollingElement.scrollTop")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "The agent's answer. " + SEAT_WORDS,
        },
    )
    told(page)
    expect(thread.locator(".lf-page-thread-msg")).to_have_count(messages + 1)
    rendered(page)
    expect(box).to_be_focused()
    assert box.evaluate("box => box.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    if kind == "bounded":
        # The block scrolls the box, so it takes the move and the page stands still.
        page_after = page.evaluate("() => document.scrollingElement.scrollTop")
        assert page_after == pytest.approx(page_before, abs=1)


@pytest.mark.parametrize("kind", ["task", "verdict"])
def test_resolving_a_long_page_thread_by_its_button_leaves_the_page_still(
    browser, serve, kind
):
    """The pressed Resolve leaves with the state it changed, and the thread took the
    focus back with a landing: the nearest edge of a thread taller than the window was
    a 700px jump to its head."""
    url, root = seated_thread(serve, kind, 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    resolve = thread.locator(".lf-resolve")
    resolve.scroll_into_view_if_needed()
    to_window_foot(page, resolve, 120)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    box = resolve.bounding_box()
    with sending(page, "the resolve"):
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    rendered(page)
    scroll_settled(page)
    expect(thread).to_be_focused()
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert abs(after - before) < 10, f"the page jumped {after - before}px"


def test_settling_a_long_diff_thread_by_key_keeps_it_in_view(browser, serve):
    """A diff thread folds to its summary when resolved and unfolds when reopened, and
    nothing landed it either way: the summary the user stood on went above the window,
    and the reopened thread with it."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    to_window_foot(page, box, 60)
    box.focus()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    rendered(page)
    scroll_settled(page)
    assert focus_clear_of_the_bar(page), "the resolved thread left the window"
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    rendered(page)
    scroll_settled(page)
    assert focus_clear_of_the_bar(page), "the reopened thread left the window"


@pytest.mark.parametrize("kind", ["task", "diff", "bounded", "bounded-short"])
def test_a_turn_arriving_leaves_a_user_who_scrolled_away_from_their_box_reading(
    browser, serve, kind
):
    """The box a turn arrives above is held still only while it is on screen. A user
    who wheeled up to read the page with focus still in the box is reading the page,
    and holding the box there moved what they were reading. A box shown inside a
    bounded block the page has scrolled away is off screen too, or the growth the
    block cannot take is handed to the page under the reader."""
    messages = 1 if kind == "bounded-short" else 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    page.evaluate(
        """node => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - innerHeight - 400,
          behavior: 'instant'})""",
        thread.element_handle(),
    )
    scroll_settled(page)
    expect(box).to_be_focused()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "The agent's answer. " + SEAT_WORDS,
        },
    )
    told(page)
    expect(thread.locator(".lf-page-thread-msg")).to_have_count(messages + 1)
    rendered(page)
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert after == pytest.approx(before, abs=1), f"the page moved {after - before}px"


def test_a_wheel_during_a_resolution_fold_outranks_the_landing_after_it(browser, serve):
    """The landing of the next title waits for the fold, and a user who scrolls the
    list meanwhile has taken it somewhere else: the deferred landing pulled the list
    back toward the title once the fold ended."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url, init_script=HOLD_MOTION)
    open_threads_list(page, 800, 520)
    title = page.locator(f'.lf-thread[data-id="{roots[3]}"] > .lf-thread-summary')
    title.click()
    rendered(page)
    title.focus()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    following = page.locator(f'.lf-thread[data-id="{roots[4]}"] > .lf-thread-summary')
    expect(following).to_be_focused()
    page.wait_for_function("() => window.__lfHeld.length > 0")
    threads = page.locator(".lf-threads")
    threads.hover()
    page.mouse.wheel(0, 300)
    scroll_settled(page, ".lf-threads")
    wheeled = threads.evaluate("list => list.scrollTop")
    page.evaluate("() => window.__lfHeld.slice().forEach(motion => motion.finish())")
    rendered(page)
    scroll_settled(page, ".lf-threads")
    expect(following).to_be_focused()
    assert threads.evaluate("list => list.scrollTop") == pytest.approx(wheeled, abs=2)


def test_a_walk_to_a_question_the_narrowing_hides_widens_the_list(browser, serve):
    """A card the narrowing hid keeps its node, so the `a` walk can still name the
    question in it — and arriving there has to show it, the way showThread does:
    focus on a card with no box is a no-op and the announcement would say "1 of 2"
    over a list that shows something else."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    card = question.locator("xpath=ancestor::*[contains(@class, 'lf-thread')][1]")
    page.get_by_role("searchbox", name="Find in threads").fill("stay blocked")
    expect(card).to_have_attribute("hidden", "")
    page.locator(".lf-threads").focus()
    page.keyboard.press("a")
    expect(card).not_to_have_attribute("hidden", "")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    assert page.evaluate(
        "() => document.activeElement.closest('.lf-thread') !== null"
    ), "the walk landed outside the card it named"


def test_a_thread_on_a_rewrite_is_named_by_its_old_and_new_words(browser, serve):
    """A rewrite's slots are two words apart on the page and no characters apart in
    the text, so a thread anchored on one was quoted as "redblue". The module that
    names its own kind (x-word) names its own words the same way."""
    url = serve(
        leaf_page(
            "rewrite",
            '<p id="p">The wall is <lf-suggestion id="swap">'
            "<lf-old>red</lf-old><lf-new>blue</lf-new></lf-suggestion> now.</p>",
        )
    )
    panel_comment(serve.page_dir, "Neither.", {"section": "swap"})
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-quote-label")).to_have_text("§ rewrite · red → blue")


def test_accordion_keyboard_travel_keeps_drafts_and_respects_narrowing(browser, serve):
    """Native focus order and thread travel keep retained threads and drafts."""
    url = serve(PANEL_PAGE)
    first = panel_comment(
        serve.page_dir, "Check the cap first.", {"section": "how-cap"}
    )
    second = panel_comment(
        serve.page_dir, "Check the merge next.", {"section": "merge-both"}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{first}"]')
    other = page.locator(f'.lf-thread[data-id="{second}"]')
    header = card.locator(".lf-thread-summary")
    expect(card).to_have_attribute("open", "")
    expect(other).not_to_have_attribute("open", "")
    header.focus()
    page.keyboard.press("Tab")
    assert page.evaluate(
        "() => document.querySelector('.lf-threads').contains(document.activeElement)"
    ), "native focus order left the thread list"
    other.locator(".lf-thread-summary").focus()
    page.keyboard.press("Enter")
    expect(other).to_have_attribute("open", "")
    expect(card).not_to_have_attribute("open", "")
    header.focus()
    page.keyboard.press("Enter")
    expect(card).to_have_attribute("open", "")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "id => document.activeElement.closest('.lf-thread')?.dataset.id === id", first
    ), "native focus order skipped the open thread"
    header.focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(card).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(card).to_have_attribute("open", "")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Panel controls similarly unwind the panel, not the unrelated disclosure.
    page.get_by_role("button", name="View", exact=True).focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(card).to_have_attribute("open", "")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    header.focus()
    page.keyboard.press("Space")
    expect(card).to_have_attribute("open", "")
    expect(other).not_to_have_attribute("open", "")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "id => document.activeElement.closest('.lf-thread')?.dataset.id === id", first
    ), "native focus order skipped the open thread"
    header.focus()
    page.keyboard.press("c")
    editor = card.get_by_role("textbox", name="Reply", exact=True)
    expect(editor).to_be_focused()
    write(editor, "Keep this unfinished answer.")
    page.keyboard.press("Home")
    expect(editor).to_be_focused()
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("t")
    expect(other).to_have_attribute("open", "")
    expect(card).not_to_have_attribute("open", "")
    page.keyboard.press("Shift+t")
    expect(editor).to_be_visible()
    expect(editor).to_have_js_property("value", "Keep this unfinished answer.")
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("merge next")
    expect(other).to_be_visible()
    expect(card).to_be_hidden()
    page.locator(".lf-threads").focus()
    page.keyboard.press("n")
    expect(other).to_have_attribute("open", "")
    expect(other.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("n")
    expect(other.locator(":scope > .lf-thread-summary")).to_be_focused()
    search.fill("")
    header.click()
    expect(editor).to_have_js_property("value", "Keep this unfinished answer.")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(editor).to_have_js_property("value", "Keep this unfinished answer.")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    header.focus()
    page.keyboard.press("c")
    expect(editor).to_be_focused()
    with sending(page, "send the retained accordion draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["text"]) == (
        "reply",
        first,
        "Keep this unfinished answer.",
    )
    assert not take_browser_errors(page)


def test_agent_titles_update_without_losing_the_users_draft(browser, serve):
    url = serve(PANEL_PAGE)
    opening = "I was wondering which space would be easier for everyone to find."
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    other = panel_comment(serve.page_dir, "Keep the filter rows compact.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    topic = thread.locator(".lf-thread-topic")
    expect(topic).to_have_text("Generating title")
    paint = """element => {
      const style = getComputedStyle(element);
      return [style.animationName, style.backgroundClip, style.color];
    }"""
    sweep, clip, _ = topic.evaluate(paint)
    assert sweep != "none" and clip == "text"
    # Without motion the words keep a fill of their own rather than the still gradient.
    page.emulate_media(reduced_motion="reduce")
    sweep, clip, fill = topic.evaluate(paint)
    assert sweep == "none" and clip != "text"
    assert fill != "rgba(0, 0, 0, 0)"
    page.emulate_media(reduced_motion="no-preference")
    focus_panel_thread(thread)
    editor = thread.locator("leaf-text")
    write(editor, "Keep this unfinished reply")
    for title in ("Workshop venue", "Terrace accessibility"):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(serve.page_dir),
                root,
                "--title",
                title,
            ],
        )
        assert result.exit_code == 0, result.output
        told(page)
        expect(thread.locator(".lf-thread-topic")).to_have_text(title)
        expect(topic).not_to_have_attribute("data-lf-pending-title", "")
        expect(editor).to_have_js_property("value", "Keep this unfinished reply")
        expect(thread.get_by_text(opening, exact=True)).to_be_visible()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("Terrace accessibility")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{other}"]')).to_be_hidden()
    expect(thread).to_be_visible()
    find.fill("")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{other}"]')).to_be_visible()
    page.reload()
    expect(
        page.locator(f'.lf-threads > .lf-thread[data-id="{root}"] .lf-thread-topic')
    ).to_have_text("Terrace accessibility")


def test_a_click_survives_an_element_whose_id_shadows_a_dom_method(browser, serve):
    """A click's composed path ends at the document and the window, and an element with
    `id="matches"` puts itself at `window.matches`, where a reader of that path expects
    Element's method. A handoff page with a "matches" section threw on every click."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "named access",
                '<h1 id="title">Pairs</h1><h2 id="matches">A pair that matches</h2>'
                "<p id='body'>Words to click.</p>",
            )
        ),
    )
    page.locator("#matches").click()
    page.locator("#body").click()


def test_the_panel_boxes_share_one_column_and_one_button_face(browser, serve):
    """Every bordered box in the Threads panel stands on one column: the find box, an
    open thread's messages and its reply box, and the page composer at the foot. The
    reply box once stood 7px wider on each side, so its words started at the messages'
    text edge while its border overhung the column everything else keeps. The View
    button beside the find box wears the chrome's own button type, as the rest of the
    panel's buttons do."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread").first
    if thread.get_attribute("open") is None:
        thread.locator(":scope > .lf-thread-summary").click()
    expect(thread.locator(".lf-compose-field")).to_be_visible()
    boxes = page.evaluate(
        """() => {
          const box = (selector, end = selector) => [
            document.querySelector(selector).getBoundingClientRect().left,
            document.querySelector(end).getBoundingClientRect().right,
          ];
          return {
            message: box('.lf-thread[open] > .lf-msg'),
            reply: box('.lf-thread[open] > .lf-compose .lf-compose-field'),
            find: box('.lf-find-box', '.lf-thread-filter-toggle'),
            general: box('.lf-general .lf-compose-field'),
          };
        }"""
    )
    left, right = boxes["message"]
    for name, (at, to) in boxes.items():
        # The find box and the page composer stand on the panel's padding, a thread's
        # boxes one transparent border inside the list's; a pixel is that border.
        assert at == pytest.approx(left, abs=1.01), (name, boxes)
        assert to == pytest.approx(right, abs=1.01), (name, boxes)
    faces = page.evaluate(
        """() => ['.lf-thread-filter-toggle', '.lf-threads-toggle'].map((selector) => {
          const style = getComputedStyle(document.querySelector(selector));
          return [style.fontSize, style.lineHeight];
        })"""
    )
    assert faces[0] == faces[1], faces


def test_typing_a_search_moves_nothing_under_the_find_box(browser, serve):
    """The view's summary and Reset stand in every view, so the first letter typed
    into the find box changes the summary's words and Reset's paint, never the list's
    place. The row used to arrive with that letter and push the list 35px down under
    the user typing above it. A search matching nothing says so where a thread's title
    would start."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    reset = page.get_by_role("button", name="Reset thread filters")
    expect(reset).to_be_hidden()
    top = page.locator(".lf-threads").evaluate("el => el.getBoundingClientRect().top")
    title = page.locator(".lf-thread-topic").first.evaluate(
        "el => el.getBoundingClientRect().left"
    )
    find = page.get_by_role("searchbox", name="Find in threads")
    find.click()
    page.keyboard.type("zq")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("0 of 2 open threads")
    expect(reset).to_be_visible()
    assert page.locator(".lf-threads").evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(top, abs=0.5), "the search moved the list"
    empty = page.locator(".lf-threads > .lf-empty")
    expect(empty).to_be_visible()
    words = empty.evaluate(
        """el => {
          const range = document.createRange();
          range.selectNodeContents(el);
          return range.getBoundingClientRect().left;
        }"""
    )
    assert words == pytest.approx(title, abs=0.5), (words, title)
