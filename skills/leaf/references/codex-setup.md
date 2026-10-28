# Terminal Codex setup

Leaf's terminal App Server route connects a background adapter to the task as a
second client. This route is experimental. `harness-codex.md` owns handoff,
delivery and replies.

To run a terminal task on Leaf's App Server route, start a private App Server on a Unix
socket together with its terminal client:

```sh
leaf codex launch
```

The launcher passes the endpoint to the task as `LEAF_CODEX_APP_SERVER` and runs both
processes. Exiting the terminal stops its App Server, so each terminal is independent
and needs no fixed port or extra server tab.

To run the two processes separately, create a private socket directory and print its
endpoint before starting App Server:

```sh
socket_dir=$(mktemp -d /tmp/leaf-codex.XXXXXX)
endpoint="unix://$socket_dir/app-server.sock"
printf '%s\n' "$endpoint"
codex app-server --listen "$endpoint"
```

In the client's shell, set the printed endpoint and connect:

```sh
export LEAF_CODEX_APP_SERVER="<printed endpoint>"
codex --remote "$LEAF_CODEX_APP_SERVER"
```

The task inherits the endpoint, so `leaf page claim` connects to that App Server. Each
pair has its own socket, so parallel pairs need no port assignment.

To bind an endpoint the user supplied before serving the page, run:

```sh
LEAF_CODEX_APP_SERVER="<supplied-endpoint>" leaf page claim <page>
```

If an adapter already holds a different endpoint, follow the conflict message.
To connect a claimed page without serving it, run `leaf page claim <page>`. It
prepares the adapter before taking ownership; without an App Server endpoint, it uses
the queue route. A task or watcher already running `leaf wait` keeps that delivery loop and
answers with explicit reply commands, as `harness-codex.md` describes.

Leaf accepts only `unix://<absolute path>` sockets and unauthenticated loopback `ws://`
endpoints. Keep a socket in a directory only you can reach, as `leaf codex launch`
does. The loopback WebSocket listener is experimental; don't expose it on a network.
Keep the terminal client open: it is where you answer approvals and input requests.
Codex still saves the task in its history, so you can resume it later from the CLI or
the desktop app once the separate server has exited; the desktop app can't connect to
that server while it runs.
