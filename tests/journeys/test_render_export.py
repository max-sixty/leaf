"""Preview and offline export tests."""

import base64
import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    neighbour_page,
)
from playwright.sync_api import expect
from render_harness import (
    leaf_page,
    open_page,
    sending,
)

from leaf import cli as cli_model
from leaf import exporting as exporting_model
from leaf import server as server_model
from leaf import state as cleanup_model
from leaf.render_checks import wait_until_ready
from leaf.schema import ELEMENT_ID
from leaf.served_state.service import PageStateService

pytestmark = pytest.mark.shifts_unsurveyed

ROOT = Path(__file__).parents[2]


def test_export_omits_neighboring_pages_and_their_access_key(serve, tmp_path):
    """Sharing an offline record grants no access to the machine's other pages."""
    serve(leaf_page("Exported record", "<h1>Exported record</h1>"), packages=())
    neighbor = cleanup_model.state_home() / "pages" / "private-neighbor"
    url = neighbour_page(neighbor, title="Private neighboring page")
    live = PageStateService(serve.page_dir).page_state(1)
    assert any(row["url"] == url for row in live["others"])

    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(output)],
    )
    assert result.exit_code == 0, result.output
    exported = output.read_text(encoding="utf-8")
    assert server_model.host_key() not in exported
    assert "Private neighboring page" not in exported
    assert any(
        row["url"] == url
        for row in PageStateService(serve.page_dir).page_state(1)["others"]
    )


def _reachable(url: str) -> bool:
    """Whether a preview's published address still answers."""
    try:
        with urllib.request.urlopen(url, timeout=STATED_TIMEOUT) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


def requested_documents(page):
    """Record each document the page's main frame requests, in order.

    A reload is a document request. `framenavigated` would also count the address the
    bootstrap rewrites in place with `history.replaceState`, which loads nothing.
    """
    documents = []
    page.on(
        "request",
        lambda request: (
            documents.append(request.url)
            if request.is_navigation_request() and request.frame == page.main_frame
            else None
        ),
    )
    return documents


# ---------- export: the page as one file ----------

OFFLINE_WIDGET = """\
import { html, LeafElement } from "/runtime/widget-api.js";

customElements.define("lf-offline-test", class extends LeafElement {
  #local = 0;

  createRenderRoot() {
    return this.attachShadow({mode: "open"});
  }

  choose() {
    return this.controller.dispatch({
      kind: "action", verb: "choose", detail: {value: "chosen"},
    });
  }

  render() {
    const {state, actions} = this.reading;
    const action = actions.choose;
    const unavailable = action.unavailable;
    return html`
      <style>#local { color: rgb(12, 34, 56); }</style>
      <button id="local" @click=${() => { this.#local += 1; this.requestUpdate(); }}>
        Increment locally
      </button>
      <output id="local-value">${this.#local}</output>
      <button id="choose" ?disabled=${!action.available} @click=${this.choose}>
        Choose on host
      </button>
      <output id="choice">${state.choose.value}</output>
      ${unavailable ? html`<p id="unavailable">${unavailable}</p>` : null}
    `;
  }
});
"""

OFFLINE_REGISTRY = {
    "lf-offline-test": {
        "description": "A page-owned offline export test widget.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "choice": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-state": {
            "choose": {
                "unit": "widget",
                "record": {"kind": "value", "attr": "choice"},
            }
        },
        "x-example": (
            '<lf-offline-test id="offline-example" choice="idle"></lf-offline-test>'
        ),
    },
}


def test_authored_video_and_audio_play_seek_and_export_offline(
    browser, serve, tmp_path
):
    """Actual MP4 and MP3 decoders cross capture, HTTP ranges, CSP and offline URLs."""
    content = leaf_page(
        "Recorded media",
        """
        <h1>Recorded media</h1>
        <video id="video" controls playsinline width="320" height="180"
          aria-label="Test pattern" poster="/media/d7cf2b4e22c063dd.png"
          src="/media/2930ad3df7819c50.mp4"></video>
        <audio id="audio" controls aria-label="Test tone">
          <source src="/media/b5eb956d4548b3b0.mp3" type="audio/mpeg">
        </audio>
    """,
    )
    content = content.replace(
        "</main>",
        '<video id="repeated" controls preload="none" aria-label="Repeated recording" src="/media/2930ad3df7819c50.mp4?ignored=1#t=2"></video><video id="from-api" controls preload="none" aria-label="API recording"></video></main>',
    ).replace("</head>", '<script type="module" src="/page/media.js"></script></head>')
    url = serve(
        content,
        page_files={
            "media.js": "import { scopedMediaUrl } from '/runtime/widget-api.js'; document.querySelector('#from-api').src = scopedMediaUrl('/media/2930ad3df7819c50.mp4?ignored=1');"
        },
    )
    page = open_page(browser, url)
    media_responses = []
    page.on(
        "response",
        lambda response: (
            media_responses.append(response)
            if response.url.endswith((".mp4", ".mp3"))
            else None
        ),
    )
    exported = tmp_path / "recordings.html"
    exporting_model.cmd_export(serve.page_dir, exported, None)
    exported_source = exported.read_text()
    for filename in ("2930ad3df7819c50.mp4", "b5eb956d4548b3b0.mp3"):
        encoded = base64.b64encode(
            (serve.page_dir / "media" / filename).read_bytes()
        ).decode()
        assert exported_source.count(encoded) == 1
    for location in (url, exported.as_uri()):
        page.goto(location, wait_until="load")
        wait_until_ready(page)
        for selector in ("#video", "#audio"):
            player = page.locator(selector)
            page.wait_for_function(
                "selector => document.querySelector(selector).readyState >= 2",
                arg=selector,
            )
            assert player.evaluate("el => el.duration") == pytest.approx(8, abs=0.2)
            if selector == "#video":
                # Leaf's bar replaces the browser's controls, the same in each engine.
                assert player.get_attribute("controls") is None
                bar = page.get_by_role("group", name="Test pattern")
                bar.get_by_role("button", name="Play recording").click()
                page.wait_for_function(
                    "selector => document.querySelector(selector).currentTime > 0",
                    arg=selector,
                )
                bar.get_by_role("button", name="Pause recording").click()
                assert player.evaluate("el => el.paused")
                expect(
                    bar.get_by_role("slider", name="Recording position")
                ).to_have_attribute("aria-valuetext", re.compile(r"^0:0\d of 0:08$"))
                player.evaluate("el => { el.currentTime = 0; }")
            # Reach the player through ordinary sequential focus.
            for _ in range(20):
                page.keyboard.press("Tab")
                if player.evaluate("el => document.activeElement === el"):
                    break
            assert player.evaluate("el => document.activeElement === el")
            page.keyboard.press("Space")
            page.wait_for_function(
                "selector => document.querySelector(selector).currentTime > 0",
                arg=selector,
            )
            page.keyboard.press("Space")
            assert player.evaluate("el => el.paused")
            player.evaluate("el => { el.pause(); el.currentTime = 6; }")
            page.wait_for_function(
                "selector => { const el = document.querySelector(selector); return !el.seeking && Math.abs(el.currentTime - 6) < 0.1; }",
                arg=selector,
            )
            assert player.evaluate("el => el.error") is None
        touch = browser.new_page(has_touch=True, viewport={"width": 390, "height": 844})
        touch.goto(location, wait_until="load")
        wait_until_ready(touch)
        for selector in ("#video", "#audio"):
            player = touch.locator(selector)
            bounds = player.bounding_box()
            # A finger plays a recording by tapping its picture, and the audio player
            # by its own button.
            spot = (
                {"x": bounds["width"] / 2, "y": bounds["height"] / 3}
                if selector == "#video"
                else {"x": 24, "y": 27}
            )
            player.tap(position=spot)
            touch.wait_for_function(
                "selector => !document.querySelector(selector).paused", arg=selector
            )
            player.tap(position=spot)
            assert player.evaluate("el => el.paused")
        touch.close()
    assert media_responses
    assert all(response.status == 206 for response in media_responses)
    assert all(
        response.headers["accept-ranges"] == "bytes" for response in media_responses
    )
    video_url = page.locator("#video").get_attribute("src")
    assert video_url.startswith("blob:")
    assert page.locator("#repeated").get_attribute("src") == video_url + "#t=2"
    assert page.locator("#from-api").get_attribute("src") == video_url
    assert page.locator("#audio source").get_attribute("src").startswith("blob:")


@pytest.mark.parametrize(
    "stem",
    ["notification-playground", "data-explorer", "code-comparison"],
)
def test_playground_examples_keep_their_offline_interaction_mode(
    browser, serve, tmp_path, stem
):
    source = ROOT / "examples" / f"{stem}.html"
    url = serve(source)
    live = open_page(browser, url)
    playground = live.locator("lf-playground")

    if stem == "notification-playground":
        playground.get_by_role("button", name="Needs attention").click()
        submit = playground.get_by_role("button", name="Create notification")
    elif stem == "data-explorer":
        live.locator('.query-row[data-filter-id="filter-2"] input').fill("80")
        submit = playground.get_by_role("button", name="Build query")
    else:
        width = playground.get_by_role("slider", name="Comparison viewport")
        for _ in range(5):
            width.press("ArrowLeft")
        playground.get_by_role("radio", name="B", exact=True).click()
        submit = playground.get_by_role("button", name="Apply treatment")
    with sending(live, f"the {stem} configuration"):
        submit.click()
    live.close()

    interactive_path = tmp_path / f"{stem}-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive_path),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    offline = browser.new_page(viewport={"width": 900, "height": 700})
    external = []
    document_url = interactive_path.as_uri()
    offline.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url
            and not request.url.startswith(("data:", "blob:"))
            else None
        ),
    )
    offline.goto(document_url, wait_until="load")
    expect(offline.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(offline.locator(".lf-chrome > #lf-media-viewer:not([open])")).to_have_count(
        1
    )
    expect(offline.locator(".lf-floating-panel")).to_have_count(0)
    expect(offline.locator(".lf-playground-submit")).to_be_disabled()
    expect(offline.locator(".lf-playground-unavailable")).to_have_text(
        "Submission unavailable: no agent or server is available."
    )
    if stem == "notification-playground":
        pressure = offline.get_by_role("slider", name="Concurrent release events")
        pressure.press("Home")
        pressure.press("ArrowRight")
        expect(offline.locator(".notification-demo-card-banner")).to_have_count(2)
    elif stem == "data-explorer":
        offline.get_by_role("button", name="Add filter").click()
        expect(offline.locator(".query-row")).to_have_count(3)
    else:
        width = offline.get_by_role("slider", name="Comparison viewport")
        width.press("Home")
        for _ in range(7):
            width.press("ArrowRight")
        expect(offline.locator('[data-candidate="A"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
        expect(offline.locator('[data-candidate="B"]')).to_have_attribute(
            "style", re.compile(r"width: 420px")
        )
    assert external == []


# What a page's own module does, attempted in turn.
POLICY_ATTEMPTS = """\
const image = (src) => new Promise((resolve) => {
  const img = new Image();
  img.onload = () => resolve("ran");
  img.onerror = () => resolve("refused");
  img.src = src;
});
const attempts = {
  eval: () => eval("'ran'"),
  "blob worker": () => new Promise((resolve) => {
    const source = new Blob(["postMessage('ran')"], {type: "text/javascript"});
    const worker = new Worker(URL.createObjectURL(source));
    worker.onmessage = (event) => resolve(event.data);
    worker.onerror = () => resolve("refused");
  }),
  "classic script": () => window.classicRan,
  "remote image": () => image("https://outside.invalid/pixel.png"),
  "remote fetch": async () => (await fetch("https://outside.invalid/data.json")).text(),
};
window.policyOutcomes = (async () => {
  const outcomes = {};
  for (const [name, attempt] of Object.entries(attempts)) {
    try {
      outcomes[name] = await attempt();
    } catch (error) {
      outcomes[name] = error.name;
    }
  }
  return outcomes;
})();
"""
# One transparent pixel, what another server answers with.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
