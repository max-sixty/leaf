"""The page's controls and chrome: command routes, status, focus and
rings, covering surfaces, and the pages and helpers its test modules share."""

from browser_sources import browser_function
from render_harness import leaf_page

SAMPLE_STARTUP_FAILURE = """<script type="module">
if (new URL(location.href).searchParams.has('startup-failure'))
  window.dispatchEvent(new CustomEvent('lf-startup-failed', {
    detail: {reason: 'Practice could not start'},
  }));
</script>"""


LIVE_SAMPLES_PAGE = leaf_page(
    "Independent practice pages",
    """
<h1 id="host-heading">Practice without changing this page</h1>
<lf-sample id="first-practice" label="First practice">
  <template id="first-source" data-sample>
    <h1 id="child-heading">A practice decision</h1>
    <lf-ask id="child-ask"><h2>Which approach?</h2>
      <lf-options id="child-options" choose>
        <lf-option id="child-a">First approach</lf-option>
        <lf-option id="child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
  </template>
</lf-sample>
<lf-sample id="second-practice" label="Second practice">
  <template id="second-source" data-sample>
    <h1 id="child-heading">Another practice decision</h1>
    <lf-ask id="child-ask"><h2>Which approach?</h2>
      <lf-options id="child-options" choose>
        <lf-option id="child-a">First approach</lf-option>
        <lf-option id="child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
  </template>
</lf-sample>
""",
).replace("</template>", SAMPLE_STARTUP_FAILURE + "</template>")


RING_NEW_STOP = browser_function("focus_rings.js", "newStop", using="control_name.js")
