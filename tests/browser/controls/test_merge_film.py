"""The wt-merge example's film: its keyboard routes, step inspection and availability,
terminal seek, and its outcomes on a phone."""

import pytest
from playwright.sync_api import expect
from render_harness import open_page, resized, scroll_settled

from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("width", [1440])
def test_merge_film_keyboard_routes_hold_steps_and_respect_the_scrubber(
    browser, serve, width
):
    source = named_source("wt-merge")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    page.clock.install(time=0)
    page.clock.pause_at(1)
    play = page.locator(".film-play")
    page.locator("#step-rebase button").click()
    play.click()
    play.press("ArrowLeft")
    expect(page.locator("#step-squash")).to_have_attribute("data-now", "")
    expect(play).to_have_text("Play")
    held = page.locator(".film-scrub").input_value()
    page.locator("#step-squash button").click()
    assert page.locator(".film-scrub").input_value() == held
    play.press("ArrowRight")
    expect(page.locator("#step-rebase")).to_have_attribute("data-now", "")
    expect(play).to_have_text("Play")
    play.click()
    page.locator(".film-scrub").press("Home")
    expect(page.locator(".film-scrub")).to_have_value("0")
    expect(play).to_have_text("Play")


@pytest.mark.parametrize("width", [390])
def test_merge_film_inspection_and_step_availability_follow_the_run(
    browser, serve, width
):
    source = named_source("wt-merge")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    inspect = page.get_by_role("button", name="Inspect next element")
    inspect.click()
    expect(page.locator(".film-picked")).to_have_count(1)
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-remove", exact=True).check()
    for _ in range(8):
        inspect.click()
    expect(page.locator(".film-inspect strong")).to_have_text("ref feature")
    expect(page.locator(".film-inspect span")).to_contain_text("Kept")
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-squash", exact=True).check()
    page.get_by_label("--no-rebase", exact=True).check()
    page.locator("#step-end button").click()
    expect(page.locator(".film-caption")).to_contain_text("Rebase refused")
    expect(page.locator("#step-merge button")).to_be_disabled()
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-rebase", exact=True).uncheck()
    expect(page.locator("#step-merge button")).to_be_enabled()


# The phone's terminal; the journey then reflows to the desk and back.
@pytest.mark.parametrize("width", [390])
def test_merge_film_terminal_seeks_to_the_result_it_reports(browser, serve, width):
    source = named_source("wt-merge")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    page.locator("#step-end button").click()
    if width < 560:
        page.locator(".film-phone-terminal summary").click()
    line = page.get_by_role("button", name="✓ Squashed @ cb12e61", exact=True)
    line.focus()
    line.press("Enter")
    expect(line).to_be_visible()
    expect(line).to_be_focused()
    expect(page.locator("#step-squash")).to_have_attribute("data-now", "")
    if width < 560:
        expect(page.locator(".film-phone-latest")).to_have_text("✓ Squashed @ cb12e61")
        expect(page.locator(".film-phone-tree").last).to_contain_text("clean")
    expect(page.locator('[data-label="commit cb12e61"]:visible')).to_be_visible()
    expect(page.locator(".film-play")).to_have_text("Play")

    # Replacing the composition preserves the user's place, not only film time.
    position = page.locator(".film-scrub").input_value()
    for target in (1440 if width == 390 else 390, width):
        resized(page, target, 900)
        expect(line).to_be_focused()
        box = line.bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= 900
        assert line.evaluate("""element => {
            const box = element.getBoundingClientRect();
            return element.contains(document.elementFromPoint(
                box.x + box.width / 2, box.y + box.height / 2));
        }""")
        line.press("Space")
        expect(line).to_be_focused()
        assert page.locator(".film-scrub").input_value() == position

    resized(page, 390, 900)
    page.locator(".film-settings summary").focus()
    resized(page, 1440, 900)
    flag = page.locator("input[name=film-flag-moved]")
    expect(flag).to_be_focused()
    resized(page, 390, 900)
    expect(flag).to_be_focused()
    box = flag.bounding_box()
    assert box["y"] >= 0 and box["y"] + box["height"] <= 900
    expect(page.locator(".film-settings")).to_have_attribute("open", "")
    page.locator(".film-next").focus()
    resized(page, 1440, 900)
    expect(page.locator(".film-play")).to_be_focused()


def test_merge_film_steps_have_a_keyboard_route(browser, serve):
    source = named_source("wt-merge")
    page = open_page(browser, serve(source))
    page.locator("#merge-film").evaluate("film => film.seek(1e9)")

    for _ in range(100):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement?.closest('li')?.id") == "step-setup":
            break
    assert page.evaluate("document.activeElement?.closest('li')?.id") == "step-setup"
    expect(page.locator("#step-setup button")).to_be_focused()
    expect(page.locator("#step-setup button:focus-visible")).to_have_count(1)

    for key in ("Space", "Enter"):
        page.locator("#merge-film").evaluate("film => film.seek(1e9)")
        page.keyboard.press(key)
        expect(page.locator("#step-setup")).to_have_attribute("data-now", "")
        expect(page.locator(".film-play")).to_have_text("Play")
        expect(
            page.locator('.film-stage > svg [data-label="commit b72c9e4"]')
        ).to_be_visible()

    # A step selected during playback holds its outcome so the explanation stays open.
    page.locator(".film-play").click()
    expect(page.locator(".film-play")).to_have_text("Pause")
    page.locator("#step-rebase button").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#step-rebase")).to_have_attribute("data-now", "")
    expect(page.locator(".film-play")).to_have_text("Play")
    expect(
        page.locator('.film-stage > svg [data-label="commit f62bab1"]')
    ).to_be_visible()


def test_a_step_pressed_on_a_phone_brings_the_film_into_view(browser, serve):
    """Narrow, the film stands above its steps, so holding a step glides the page to
    it. The glide sets off as the press lands, and the film and its step list then draw
    the new moment as the glide runs, which changes the heights of the film's parts and
    of the steps by different amounts: the step told before shrinks and the one pressed
    grows."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(named_source("wt-merge")), context=context)
    for step in ("merge", "setup"):
        button = page.locator(f"#step-{step} button")
        button.scroll_into_view_if_needed()
        scroll_settled(page)
        button.tap()
        scroll_settled(page)
        expect(page.locator(f"#step-{step}")).to_have_attribute("data-now", "")
        assert 0 <= page.locator("#merge-film").bounding_box()["y"] < 200, step


def test_merge_film_shows_its_whole_phone_stage_in_a_laptop_height_pane(browser, serve):
    """Where the film's pane is narrow enough for its phone layout but the workspace
    still fills an 800x720 window, the stage keeps its content's height and the pane
    scrolls to its end: the terminal below the drawing stays reachable in the window
    rather than clipped inside a squeezed stage."""
    source = named_source("wt-merge")
    page = open_page(browser, serve(source))
    resized(page, 800, 720)
    film = page.locator("#merge-film")
    expect(film).to_have_attribute("data-phone", "")
    geometry = film.evaluate(
        """film => {
          film.scrollTop = film.scrollHeight;
          const stage = film.querySelector('.film-stage');
          const terminal = stage.querySelector('.film-phone-terminal');
          return {
            clipped: stage.scrollHeight - stage.clientHeight,
            terminalBottom: terminal.getBoundingClientRect().bottom,
            stageBottom: stage.getBoundingClientRect().bottom,
            shownBottom: Math.min(
              film.getBoundingClientRect().top + film.clientTop + film.clientHeight,
              innerHeight),
          };
        }"""
    )
    assert geometry["clipped"] <= 1, geometry
    assert geometry["terminalBottom"] <= geometry["stageBottom"], geometry
    assert geometry["stageBottom"] <= geometry["shownBottom"], geometry
