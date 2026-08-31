# Experiment 7: Attribute the host 404

## Purpose

Repeat experiment 6's successful route with bounded focus evidence and failed-request URLs, so the remaining console error can be assigned to the app, host, or incidental browser chrome.

**Changes from experiment 6:**

- Record focused elements by tag/id/option address instead of full text content.
- Record URLs and status codes for HTTP failures, and URLs for failed requests.
- Record the official host's model-visible tool dropdown.

**Configuration:**

- Product, transport, fixture, reference-host commit, dimensions, and browser actions unchanged from experiment 6.

**Expected outcomes:**

- If the only 404 is host chrome such as `/favicon.ico`, the bundled app path is clean.
- If a failed request points at the `ui://` resource, MCP endpoint, or an undeclared external origin, the product slice is not yet complete.
- The result JSON should remain small after the choice and after reopen.

## Findings

The product result repeated cleanly and the bounded recorder reduced the result
from roughly 806 KB to 2.3 KB. The official host's model tool selector contained
only `leaf_open_page`; the two app-only tools remained unavailable to the model.
The app again fit a 414×354 content viewport without overflow, keyboard Enter
appended the expected `choose` event, and a teardown plus new open reconstructed
the settled state from the log.

The only failed request was `http://localhost:3001/mcp` with
`net::ERR_ABORTED`, which is consistent with the host aborting its long-lived
MCP request while the app is closed or reopened. The one generic console 404 had
no matching failed response and still lacked a source URL, so this run narrowed
the network evidence but did not attribute that message. Experiment 8 adds
console locations and context-wide request diagnostics only.
