# Terminal Codex setup

To run a terminal task on Leaf's App Server route, start a private Unix-socket
App Server and its terminal client together:

```sh
leaf codex launch
```

The launcher exports its endpoint to the task as `LEAF_CODEX_APP_SERVER` and owns
both processes. Exiting the terminal stops its App Server, so each terminal is
independent and no fixed port or separate server tab remains. Observed activity ends
with that server.

To run the two processes separately, create a private socket directory and print
its endpoint before starting App Server:

```sh
socket_dir=$(mktemp -d /tmp/leaf-codex.XXXXXX)
endpoint="unix://$socket_dir/app-server.sock"
printf '%s\n' "$endpoint"
codex app-server --listen "$endpoint"
```

In the terminal client's shell, copy that printed endpoint:

```sh
export LEAF_CODEX_APP_SERVER="<printed endpoint>"
codex --remote "$LEAF_CODEX_APP_SERVER"
```

The task inherits the endpoint, so `leaf codex start` connects to that App Server.
Each pair of processes has its own socket; parallel versions need no port assignment.

Only `unix://<absolute path>` sockets and unauthenticated loopback `ws://` endpoints
are accepted; keep a socket you supply in a directory only you can reach, as
`leaf codex launch` does. The loopback WebSocket listener is experimental; do not
expose it on a network. Keep the CLI open because it is still the interactive client for
approvals and user input. The task is still stored in Codex's task history and can be
resumed later from the CLI or desktop app after the standalone server releases its
writer; the desktop app is not a live client of this separately started server.
