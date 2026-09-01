# Experiment 8: Locate the browser error

## Purpose

Repeat experiment 7 with console source locations and browser-context network
events, distinguishing an app resource failure from host teardown noise.

**Changes from experiment 7:**

- Record the URL and line supplied with each console message.
- Observe failed responses and requests on the browser context rather than only
  the host page.
- Record the method and resource type for failed requests.

**Configuration:**

- Product, transport, fixture, reference-host commit, dimensions, and browser
  actions unchanged from experiment 7.

**Expected outcomes:**

- A source URL or matching failed response should assign the generic 404 to the
  app, host, sandbox, or incidental browser behavior.
- The app behavior and model-visible tool set should remain unchanged.

## Findings

The console location identified the generic 404 as
`http://localhost:8080/favicon.ico`, an incidental missing icon in the official
reference host. No response from the Leaf app resource, sandbox, or MCP service
failed. The remaining failed request was a `fetch` POST to the MCP endpoint with
`net::ERR_ABORTED` as the host tore down and reopened its long-lived session.

The unchanged product path passed again: only `leaf_open_page` was model
visible, the compact ask fit without overflow, and keyboard activation appended
the expected ordinary Leaf action. There is no unresolved browser error in this
slice.
