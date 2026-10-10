"""Opaque samples use ordinary native delivery and reconnect after a reload."""

from playwright.sync_api import expect
from render_harness import open_page
from test_render_controls import leaf_page


def test_samples_keep_native_loaders_forms_and_reload(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native sample delivery",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <link rel="stylesheet" href="/page/native.css">
    <img src="/page/native.svg" alt="Native resource">
    <form id="form"><button id="submit">Submit</button></form>
    <button id="popup">Open window</button>
    <lf-sample id="nested" label="Nested practice" window>
      <template id="nested-source" data-sample><h1>Nested page</h1></template>
    </lf-sample>
    <script type="module" src="/page/native.js"></script>
  </template>
</lf-sample>
""",
            ),
            page_files={
                "native.css": "h1 { color: rgb(12, 34, 56); }",
                "native.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20"/></svg>',
                "native.js": """
window.nativeModuleUrl = import.meta.url;
window.nativeXhr = () => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', new URL('native.css', import.meta.url));
  xhr.onload = () => resolve({status: xhr.status, text: xhr.responseText});
  xhr.onerror = reject;
  xhr.send();
});
window.nativeImage = () => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image.naturalWidth);
  image.onerror = reject;
  image.src = new URL('native.svg', import.meta.url);
});
document.querySelector('#form').addEventListener('submit', event => {
  event.preventDefault();
  window.submitted = true;
});
document.querySelector('#popup').addEventListener('click', () => {
  window.open('about:blank', '_blank');
});
""",
            },
        ),
    )
    sample = page.locator("#practice")
    sample.locator(":scope > iframe").wait_for(state="attached")
    child = sample.locator(":scope > iframe").element_handle().content_frame()
    child.wait_for_function(
        "document.body?.hasAttribute('data-lf-presented')", timeout=20000
    )
    sample.evaluate("async sample => await sample.ready")
    child.wait_for_function("!!window.nativeXhr")
    assert child.evaluate("nativeModuleUrl").startswith("http:")
    assert child.evaluate("nativeXhr()") == {
        "status": 200,
        "text": "h1 { color: rgb(12, 34, 56); }",
    }
    assert child.evaluate("nativeImage()") == 20
    expect(child.locator("h1").first).to_have_css("color", "rgb(12, 34, 56)")
    child.locator("#submit").click()
    assert child.evaluate("submitted")
    with page.expect_popup() as popup:
        child.locator("#popup").click()
    popup.value.close()
    nested = child.locator("#nested")
    nested.evaluate("async sample => await sample.ready")
    grandchild = nested.locator("iframe").element_handle().content_frame()
    expect(grandchild.locator("h1")).to_have_text("Nested page")
    child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      const response = await fetch('api/event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Leaf-Layer': state.layer.generation},
        body: JSON.stringify({kind: 'comment', revision: 1, text: 'Keep through reload', attempt: 'native-reload-comment'}),
      });
      if (!response.ok) throw new Error(await response.text());
    }""")
    with child.expect_navigation(wait_until="domcontentloaded"):
        child.evaluate("location.reload()")
    child.wait_for_function("document.body?.hasAttribute('data-lf-presented')")
    expect(child.locator("h1").first).to_have_text("Practice page")
    child.wait_for_function("!!window.nativeXhr")
    sample.evaluate("async sample => await sample.ready")
    assert child.evaluate("nativeXhr()")["status"] == 200
    assert child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      return state.events.some(event => event.text === 'Keep through reload');
    }""")
